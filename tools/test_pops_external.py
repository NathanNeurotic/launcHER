#!/usr/bin/env python3
"""Compile and exercise the production C inspector without PS2SDK or Sony files.

Optional --corpus-root reads an external REPOP popstarter/ tree; --elf reads an
external ELF. Neither input is copied into the repository or executed.
"""

import argparse
import collections
import ctypes as c
import hashlib
import lzma
import os
import re
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
INVALID, UNSUPPORTED, RANGE = -1, -2, -3
TROJAN, CONFIG, DATA = 0, 1, 2


class Container(c.Structure):
    _fields_ = [("kind", c.c_int), ("slot", c.c_uint8)] + [
        (name, c.c_uint32) for name in
        ("control", "flags", "load", "entry", "hook", "payload_size")
    ] + [("metadata", c.c_uint8 * 32)]


class Plan(c.Structure):
    _fields_ = [("container", Container), ("payload_offset", c.c_size_t),
               ("hook_offset", c.c_size_t), ("hook_instruction", c.c_uint32),
               ("hook_size", c.c_uint8)]


class PatchOptions(c.Structure):
    _fields_ = [("modes", c.c_uint8 * 4), ("video", c.c_int)]


class ElfInfo(c.Structure):
    _fields_ = [("entry", c.c_uint32), ("load_segments", c.c_uint16)]


class IopImage(c.Structure):
    _fields_ = [("directory_offset", c.c_uint32), ("directory_size", c.c_uint32),
               ("extinfo_size", c.c_uint32), ("files", c.c_uint16)]


class BootPlan(c.Structure):
    _fields_ = [("source", c.c_int), ("iop_variant", c.c_int)] + [
        (name, c.c_uint32) for name in ("entry", "core_address", "core_size",
        "bss_address", "bss_size", "scratchpad_size", "iop_offset", "iop_size")]


class BootBuffers(c.Structure):
    _fields_ = [("ram_base", c.c_uint32), ("ram", c.c_void_p), ("ram_size", c.c_size_t),
               ("scratchpad", c.c_void_p), ("scratchpad_size", c.c_size_t),
               ("iop", c.c_void_p), ("iop_size", c.c_size_t)]


def check_boot_staging(plan, source, iop=None, original_writes=None):
    ram_size = plan.bss_address + plan.bss_size - 0x100000
    ram = c.create_string_buffer(b'x' * (ram_size + 16), ram_size + 16)
    scratch = c.create_string_buffer(b'x' * 0x4000, 0x4000)
    reboot = c.create_string_buffer(b'x' * (plan.iop_size + 16), plan.iop_size + 16)
    buffers = BootBuffers(0x100000, c.addressof(ram), ram_size,
                          c.addressof(scratch), len(scratch), c.addressof(reboot), plan.iop_size)
    def stage():
        if iop is None:
            return LIB.pops_boot_stage_pak(source, len(source), c.byref(buffers))
        return LIB.pops_boot_stage_elf(source, len(source), iop, len(iop), c.byref(buffers))
    for member in ('ram_size', 'scratchpad_size', 'iop_size'):
        saved = getattr(buffers, member)
        setattr(buffers, member, 1)
        if stage() != RANGE or ram.raw != b'x' * len(ram) or scratch.raw != b'x' * len(scratch) or reboot.raw != b'x' * len(reboot):
            raise RuntimeError(f"Boot buffer bounds failure wrote data: {member}")
        setattr(buffers, member, saved)
    saved = buffers.iop
    buffers.iop = buffers.ram
    if stage() != RANGE or ram.raw != b'x' * len(ram):
        raise RuntimeError("Boot destination aliasing was not rejected before writes")
    buffers.iop = saved
    if stage():
        raise RuntimeError("Known dependency staging failed")
    core_start = plan.core_address - 0x100000
    bss_start = plan.bss_address - 0x100000
    core = ram.raw[core_start:bss_start]
    if hashlib.sha256(core).hexdigest() != '38ecd425324a1244e90ae68b927496b9af511fd0ed89761199fb6eb699e71ab0':
        raise RuntimeError("Staged core differs from the measured loaded image")
    expected_iop = iop if iop is not None else source[plan.iop_offset:]
    if reboot.raw[:plan.iop_size] != expected_iop:
        raise RuntimeError("Reboot image was not preserved separately")
    if (any(ram.raw[:core_start]) or any(ram.raw[bss_start:ram_size]) or
            any(scratch.raw[:plan.scratchpad_size]) or ram.raw[ram_size:] != b'x' * 16 or
            scratch.raw[plan.scratchpad_size:] != b'x' * (0x4000 - plan.scratchpad_size) or
            reboot.raw[plan.iop_size:] != b'x' * 16):
        raise RuntimeError("BSS clearing or boot destination boundaries are incorrect")
    print("Guarded boot buffer staging PASS: core, separate IOP, BSS and canaries")
    before = ram.raw
    # Corrupt the last original module-error guard and prove there are no earlier
    # patch writes on rejection. The full core identity guard also must fail.
    ram[0x2004be - 0x100000] = b'\0'
    corrupted = ram.raw
    if LIB.pops_core_patches_stage(0x100000, ram, ram_size, 0x3f) != -4 or ram.raw != corrupted:
        raise RuntimeError("Core patch guard failure changed memory")
    ram.raw = before
    if LIB.pops_core_patches_stage(0x100000, ram, ram_size, 0x3f):
        raise RuntimeError("Reference core patches rejected")
    if original_writes is not None:
        expected = bytearray(before)
        for address, value, width in original_writes:
            offset = address - 0x100000
            expected[offset:offset + width] = value.to_bytes(width, 'little')
        if ram.raw != bytes(expected):
            raise RuntimeError("Core patch output differs from original write sequence")
        print(f"Original-source core patch parity PASS: {len(original_writes)} writes, entire RAM compared")
    # Original Delcro routine writes only the low byte of each instruction.
    for address in (0x20044c, 0x200484):
        offset = address - 0x100000
        if ram.raw[offset] != 0 or ram.raw[offset + 1:offset + 4] != before[offset + 1:offset + 4]:
            raise RuntimeError("Original byte patch widened into an instruction overwrite")
    patched = ram.raw
    if LIB.pops_core_patches_stage(0x100000, ram, ram_size, 0x3f) != -4 or ram.raw != patched:
        raise RuntimeError("Core patch reapplication did not fail closed")
    print("Guarded core patch staging PASS: original byte widths, rejection without mutation")


def read_original_writes(path):
    text = path.read_text()
    writes = []
    for name, expected_count in [('008db778', 1), ('008dba90', 1), ('008dbafc', 22),
                                 ('008dbe78', 1), ('008dbf58', 2), ('008dbfd4', 9)]:
        marker = f'/* FUN_{name} @'
        if text.count(marker) != 1:
            raise RuntimeError(f"Missing or ambiguous original export: {name}")
        block = text.split(marker)[1].split('/* ---------------------------------------------------------------- */')[0]
        found = re.findall(r'FUN_(008dc8e4|008dc918|008dc94c)\((0x[0-9a-f]+|0),(0x[0-9a-f]+)\)', block)
        if len(found) != expected_count:
            raise RuntimeError(f"Unexpected original write count in {name}")
        for helper, value, address in found:
            writes.append((int(address, 0), int(value, 0),
                           {'008dc8e4': 1, '008dc918': 2, '008dc94c': 4}[helper]))
    return writes


def container(magic=b"TROJAN_7", control=0x60000, flags=0x10003,
              load=0x146FFF0, entry=0x1470020, hook=0x2327D0,
              payload=b"\0" * 64, metadata=b"Cumulative r7"):
    return (magic + struct.pack("<6I", control, flags, load, entry, hook, len(payload))
            + metadata.ljust(32, b"\0") + payload)


def elf(segments=None, entry=0x200000):
    # Synthetic ET_EXEC image; BSS is larger than the file-backed text.
    if segments is None:
        segments = [(1, 0x100, 0x200000, 0, 16, 32, 5, 16)]
    ident = b"\x7fELF\x01\x01\x01" + b"\0" * 9
    header = struct.pack("<16sHHIIIIIHHHHHH", ident, 2, 8, 1, entry, 52, 0,
                         0, 52, 32, len(segments), 0, 0, 0)
    return (header + b"".join(struct.pack("<8I", *s) for s in segments)).ljust(0x110, b"\0")


def word(data, offset, value):
    result = bytearray(data)
    struct.pack_into("<I", result, offset, value)
    return bytes(result)


def inspect(data):
    out = Container()
    status = LIB.pops_container_inspect(data, len(data), c.byref(out))
    return status, out


def inspect_elf(data):
    out = ElfInfo()
    status = LIB.pops_elf_inspect(data, len(data), c.byref(out))
    return status, out


class InspectorTests(unittest.TestCase):
    def test_core_patch_bounds_flags_and_unknown_identity(self):
        memory = c.create_string_buffer(0x302e60)
        before = memory.raw
        self.assertEqual(LIB.pops_core_patches_stage(0x200000, memory, len(memory), 0), INVALID)
        self.assertEqual(LIB.pops_core_patches_stage(0x200000, memory, len(memory), 64), INVALID)
        self.assertEqual(LIB.pops_core_patches_stage(0x200000, memory, 1, 1), RANGE)
        self.assertEqual(LIB.pops_core_patches_stage(0x200004, memory, len(memory), 1), RANGE)
        self.assertEqual(LIB.pops_core_patches_stage(0x200000, memory, len(memory), 1), -4)
        self.assertEqual(memory.raw, before)

    def test_sha256_matches_hashlib_across_padding_and_block_boundaries(self):
        for size in (0, 1, 3, 55, 56, 63, 64, 65, 119, 120, 127, 128,
                     1000, 65536, 1000000):
            data = bytes((i * 31 + 7) & 255 for i in range(size))
            result = (c.c_uint8 * 32)()
            self.assertEqual(LIB.pops_image_sha256(data, len(data), result), 0)
            self.assertEqual(bytes(result), hashlib.sha256(data).digest())
        result = (c.c_uint8 * 32)(*([99] * 32))
        self.assertEqual(LIB.pops_image_sha256(None, 1, result), INVALID)
        self.assertEqual(LIB.pops_image_sha256(b'x', 0x800001, result), RANGE)
        self.assertEqual(bytes(result), b'c' * 32)

    def test_unknown_boot_images_fail_without_changing_plan(self):
        data = b'\0' * (0x302e60 + 245081)
        result = BootPlan()
        result.entry = 0x12345678
        self.assertEqual(LIB.pops_boot_plan_pak(data, len(data), c.byref(result)), -4)
        self.assertEqual(LIB.pops_boot_plan_pak(data, len(data) - 1, c.byref(result)), UNSUPPORTED)
        image = self.iop_image()
        self.assertEqual(LIB.pops_boot_plan_elf(elf(), len(elf()), image,
                                              len(image), c.byref(result)), -4)
        self.assertEqual(result.entry, 0x12345678)

    @staticmethod
    def iop_image(reset_size=0):
        def entry(name, ext, size):
            return struct.pack('<10sHI', name, ext, size)
        directory = (entry(b'RESET', 4, reset_size) + entry(b'ROMDIR', 0, 80)
                     + entry(b'EXTINFO', 0, 4) + entry(b'LOADCORE', 0, 7)
                     + b'\0' * 16)
        return (b'x' * reset_size).ljust((reset_size + 15) & ~15, b'\0') + directory + b'\0' * 16 + b'module!'

    def test_iop_romdir_and_reset_extent(self):
        for reset_size in (0, 23):
            data = self.iop_image(reset_size)
            result = IopImage()
            self.assertEqual(LIB.pops_iop_image_inspect(data, len(data), c.byref(result)), 0)
            self.assertEqual((result.directory_offset, result.directory_size,
                              result.extinfo_size, result.files),
                             ((reset_size + 15) & ~15, 80, 4, 4))

    def test_iop_image_rejects_unbounded_or_inconsistent_directory(self):
        data = self.iop_image()
        for malformed in (data[:-1], word(data, 28, 0xfffffff0),
                          word(data, 12, 1), word(data, 44, 0),
                          word(data, 64, 1), word(data, 60, 0xffffffff),
                          data[:48] + data[16:26] + data[58:]):
            result = IopImage(123, 456, 789, 10)
            self.assertNotEqual(LIB.pops_iop_image_inspect(malformed, len(malformed),
                                                        c.byref(result)), 0)
            self.assertEqual(result.directory_offset, 123)

    @staticmethod
    def pak(payload):
        stream = lzma.compress(payload, format=lzma.FORMAT_RAW,
                               filters=[dict(id=lzma.FILTER_LZMA1, dict_size=1 << 23,
                                             lc=3, lp=0, pb=2)])
        assert stream[0] == 0
        return struct.pack('<I', len(payload)) + stream[1:5][::-1] + stream[5:]

    def test_pak_decode_matches_independent_encoder(self):
        payload = bytes(range(256)) * 1000 + b'IOPRP image'
        data = self.pak(payload)
        output = c.create_string_buffer(len(payload))
        length = c.c_size_t(99)
        self.assertEqual(LIB.pops_pak_decode(data, len(data), output,
                                           len(output), c.byref(length)), 0)
        self.assertEqual(length.value, len(payload))
        self.assertEqual(output.raw, payload)

    def test_pak_truncation_and_allocation_limits(self):
        data = self.pak(bytes(range(256)) * 100)
        output = c.create_string_buffer(25600)
        length = c.c_size_t(99)
        for malformed in (data[:7], data[:12], word(data, 0, 0),
                          word(data, 0, 0x800001), word(data, 4, 0xffffffff)):
            self.assertNotEqual(LIB.pops_pak_decode(malformed, len(malformed),
                                                  output, len(output), c.byref(length)), 0)
            self.assertEqual(length.value, 99)
        output.raw = b'x' * len(output)
        self.assertEqual(LIB.pops_pak_decode(data, len(data), output, 3,
                                           c.byref(length)), RANGE)
        self.assertEqual(output.raw, b'x' * len(output))

    def test_pak_rejects_aliasing_before_write(self):
        data = self.pak(b'a' * 1000)
        buffer = c.create_string_buffer(data, 2000)
        before = buffer.raw
        length = c.c_size_t(99)
        self.assertEqual(LIB.pops_pak_decode(buffer, len(data), buffer,
                                           len(buffer), c.byref(length)), RANGE)
        self.assertEqual(buffer.raw, before)

    def test_cumulative_entry_differs_from_load(self):
        status, result = inspect(container())
        self.assertEqual(status, 0)
        self.assertEqual((result.kind, result.slot, result.control, result.flags),
                         (TROJAN, 7, 0x60000, 0x10003))
        self.assertEqual((result.load, result.entry, result.hook),
                         (0x146FFF0, 0x1470020, 0x2327D0))

    def test_configuration_metadata_is_not_discarded(self):
        metadata = b"Compat. Mode 0x04".ljust(24, b"\0") + struct.pack("<I", 4) + b"\0" * 4
        status, result = inspect(container(b"PATCH_4\0", 1, 0x10001,
                                          0, 0, 0, b"", metadata))
        self.assertEqual(status, 0)
        self.assertEqual((result.kind, result.control), (CONFIG, 1))
        self.assertEqual(bytes(result.metadata), metadata)

    def test_data_patch_has_no_executable_entry(self):
        status, result = inspect(container(b"PATCH_5\0", 0, 0x10001,
                                          0x2FEFF0, 0, 0, b"driver data"))
        self.assertEqual(status, 0)
        self.assertEqual(result.kind, DATA)

    def test_unaligned_input_buffer(self):
        data = container()
        buf = c.create_string_buffer(b"x" + data)
        out = Container()
        self.assertEqual(LIB.pops_container_inspect(c.byref(buf, 1), len(data), c.byref(out)), 0)

    def test_truncation_and_unexpected_trailer(self):
        data = container()
        for broken in (data[:63], data[:-1], data + b"x", word(data, 28, 0xFFFFFFFF)):
            self.assertEqual(inspect(broken)[0], INVALID)

    def test_unknown_container_and_flags(self):
        self.assertEqual(inspect(container(magic=b"PATCH_0\0"))[0], UNSUPPORTED)
        self.assertEqual(inspect(container(flags=0x10005))[0], UNSUPPORTED)
        self.assertEqual(inspect(container(flags=0x20002))[0], UNSUPPORTED)

    def test_payload_entry_hook_and_overlap_bounds(self):
        data = container()
        for broken in (word(data, 16, 0xFFFFFFF0), word(data, 20, 0x1470030),
                       word(data, 24, 0x1FFFFFC), word(data, 24, 0x146FFF0)):
            self.assertEqual(inspect(broken)[0], RANGE)
        self.assertEqual(inspect(word(data, 20, 0x1470021))[0], INVALID)
        self.assertEqual(inspect(word(data, 20, 0x1470030 - 4))[0], 0)

    def test_plan_requires_payload_and_hook_in_same_window(self):
        data = container()
        plan = Plan()
        self.assertEqual(LIB.pops_container_plan(data, len(data), 0x200000,
                                               0x1300000, c.byref(plan)), 0)
        self.assertEqual((plan.payload_offset, plan.hook_offset), (0x126FFF0, 0x327D0))
        self.assertEqual((plan.hook_instruction, plan.hook_size), (0x0C51C008, 4))
        # Payload fits; hook does not. A loader must not install it anyway.
        c.memset(c.byref(plan), 0xA5, c.sizeof(plan))
        before = bytes(plan)
        self.assertEqual(LIB.pops_container_plan(data, len(data), 0x146FFF0,
                                               64, c.byref(plan)), RANGE)
        self.assertEqual(bytes(plan), before)

    def test_guarded_staging_preserves_jal_delay_instruction(self):
        payload = b"0123456789abcdef"
        data = container(control=0, flags=0x10001, load=0x100040,
                         entry=0x100040, hook=0x100010, payload=payload)
        memory = c.create_string_buffer(128)
        c.memset(memory, 0xA5, 128)
        expected = (c.c_uint32 * 2)(0xA5A5A5A5, 0xA5A5A5A5)
        self.assertEqual(LIB.pops_container_stage(data, len(data), 0x100000,
                                                memory, 128, expected, 2), 0)
        self.assertEqual(memory.raw[64:80], payload)
        self.assertEqual(struct.unpack_from("<I", memory.raw, 16)[0], 0x0C040010)
        self.assertEqual(memory.raw[20:24], b"\xa5" * 4)

    def test_guard_failure_or_missing_guard_writes_nothing(self):
        data = container(control=0, flags=0x10001, load=0x100040,
                         entry=0x100040, hook=0x100010, payload=b"x" * 16)
        memory = c.create_string_buffer(128)
        before = memory.raw
        wrong = (c.c_uint32 * 2)(1, 0)
        self.assertEqual(LIB.pops_container_stage(data, len(data), 0x100000,
                                                memory, 128, wrong, 2), -4)
        self.assertEqual(memory.raw, before)
        self.assertEqual(LIB.pops_container_stage(data, len(data), 0x100000,
                                                memory, 128, None, 0), INVALID)
        self.assertEqual(memory.raw, before)

    def test_jump_variants_clear_only_the_requested_instruction_slots(self):
        for count in (1, 2, 3):
            data = container(control=count << 16, flags=0x10002, load=0x100040,
                             entry=0x100040, hook=0x100010, payload=b"x" * 16)
            memory = c.create_string_buffer(128)
            c.memset(memory, 0xA5, 128)
            expected = (c.c_uint32 * 3)(*[0xA5A5A5A5] * 3)
            self.assertEqual(LIB.pops_container_stage(data, len(data), 0x100000,
                                                    memory, 128, expected,
                                                    3 if count == 3 else 2), 0)
            self.assertEqual(struct.unpack_from("<I", memory.raw, 16)[0], 0x08040010)
            self.assertEqual(memory.raw[20:16 + count * 4], b"\0" * ((count - 1) * 4))
            self.assertEqual(memory.raw[16 + count * 4], 0xA5)
        # Third instruction would overlap the payload even though the first two do not.
        data = container(control=0x30000, flags=0x10002, load=0x100018,
                         entry=0x100018, hook=0x100010, payload=b"x" * 16)
        plan = Plan()
        self.assertEqual(LIB.pops_container_plan(data, len(data), 0x100000,
                                               128, c.byref(plan)), RANGE)

    def test_type2_without_a_jump_width_uses_original_jal_fallback(self):
        data = container(control=0, flags=0x10002, load=0x100040,
                         entry=0x100040, hook=0x100010, payload=b"x" * 16)
        plan = Plan()
        self.assertEqual(LIB.pops_container_plan(data, len(data), 0x100000,
                                               128, c.byref(plan)), 0)
        self.assertEqual((plan.hook_instruction, plan.hook_size), (0x0C040010, 4))

    def test_config_requires_option_handling_and_data_can_stage_without_hook(self):
        memory = c.create_string_buffer(128)
        config = container(b"PATCH_4\0", 1, 0x10001, 0, 0, 0, b"")
        self.assertEqual(LIB.pops_container_stage(config, len(config), 0x100000,
                                                memory, 128, None, 0), UNSUPPORTED)
        data = container(b"PATCH_5\0", 0, 0x10001, 0x100040, 0, 0, b"data")
        self.assertEqual(LIB.pops_container_stage(data, len(data), 0x100000,
                                                memory, 128, None, 0), 0)
        self.assertEqual(memory.raw[64:68], b"data")

    def test_staging_rejects_source_destination_alias(self):
        data = container(control=0, flags=0x10001, load=0x100040,
                         entry=0x100040, hook=0x100010, payload=b"x" * 16)
        memory = c.create_string_buffer(data, 128)
        before = memory.raw
        expected = (c.c_uint32 * 2)(0x100040, 0x100040)
        self.assertEqual(LIB.pops_container_stage(memory, len(data), 0x100000,
                                                memory, 128, expected, 2), RANGE)
        self.assertEqual(memory.raw, before)

    def test_patch_control_modes_and_video_intent(self):
        for control in range(8):
            modes = bytes([1, 4, 6, 8]) if control & 1 else b"\0" * 4
            metadata = b"profile".ljust(24, b"\0") + modes + b"\0" * 4
            status, result = inspect(container(b"PATCH_4\0", control, 0x10001,
                                              0, 0, 0, b"", metadata))
            self.assertEqual(status, 0)
            options = PatchOptions()
            self.assertEqual(LIB.pops_patch_options(c.byref(result), c.byref(options)), 0)
            self.assertEqual(bytes(options.modes), modes)
            self.assertEqual(options.video, control >> 1)
        result.control = 8
        self.assertEqual(LIB.pops_patch_options(c.byref(result), c.byref(options)), UNSUPPORTED)

    def test_failed_inspection_leaves_output_unchanged(self):
        out = Container()
        c.memset(c.byref(out), 0xA5, c.sizeof(out))
        before = bytes(out)
        self.assertEqual(LIB.pops_container_inspect(b"bad", 3, c.byref(out)), INVALID)
        self.assertEqual(bytes(out), before)
        self.assertEqual(LIB.pops_container_inspect(None, 64, c.byref(out)), INVALID)

    def test_elf_with_bss_and_no_section_table(self):
        status, info = inspect_elf(elf())
        self.assertEqual(status, 0)
        self.assertEqual((info.entry, info.load_segments), (0x200000, 1))

    def test_pops_scratchpad_bss_is_not_mmio_load_permission(self):
        segments = [(1, 0x100, 0x200000, 0, 16, 32, 5, 16),
                    (1, 0x100, 0x70000000, 0, 0, 0x3C30, 6, 16)]
        self.assertEqual(inspect_elf(elf(segments))[0], 0)
        for field, value in ((2, 0x10000000), (4, 4), (5, 0x4001), (6, 5)):
            bad = list(segments[1])
            bad[field] = value
            self.assertEqual(inspect_elf(elf([segments[0], tuple(bad)]))[0], RANGE)

    def test_elf_architecture_and_program_table(self):
        data = elf()
        for offset, value in ((4, 2), (5, 2), (18, 62)):
            broken = bytearray(data)
            broken[offset] = value
            self.assertEqual(inspect_elf(bytes(broken))[0], UNSUPPORTED)
        self.assertEqual(inspect_elf(word(data, 28, 0xFFFFFFF0))[0], INVALID)
        self.assertEqual(inspect_elf(data[:60])[0], INVALID)

    def test_elf_file_memory_and_entry_boundaries(self):
        data = elf()
        self.assertEqual(inspect_elf(word(data, 52 + 16, 33))[0], INVALID)
        self.assertEqual(inspect_elf(word(data, 52 + 4, 0x108))[0], INVALID)
        self.assertEqual(inspect_elf(word(data, 52 + 8, 0x1FFFFF0))[0], RANGE)
        # Entry in BSS, misaligned entry and non-executable text are invalid.
        for broken in (word(data, 24, 0x200010), word(data, 24, 0x200001),
                       word(data, 52 + 24, 4), word(data, 52 + 28, 3),
                       word(data, 52 + 16, 3)):
            self.assertEqual(inspect_elf(broken)[0], INVALID)
        overlapping = elf([(1, 0x100, 0x200000, 0, 16, 32, 5, 16),
                           (1, 0x100, 0x200010, 0, 16, 16, 6, 16)])
        self.assertEqual(inspect_elf(overlapping)[0], RANGE)


def check_corpus(root):
    roots = [root / "hugopocked-fixes", root / "game-fixes"]
    if any(not p.is_dir() for p in roots):
        raise RuntimeError("--corpus-root must contain hugopocked-fixes/ and game-fixes/")
    files = sorted(p for d in roots for p in d.rglob("*")
                   if p.is_file() and p.suffix.lower() == ".bin")
    if not files:
        raise RuntimeError("No external corpus files found")
    kinds, controls = collections.Counter(), collections.Counter()
    for path in files + [root / "TROJAN_7.BIN", root / "PATCH_5.BIN"]:
        data = path.read_bytes()
        status, result = inspect(data)
        if status:
            raise RuntimeError(f"Rejected external specimen {path}: {status}")
        plan = Plan()
        status = LIB.pops_container_plan(data, len(data), 0x100000, 0x1F00000, c.byref(plan))
        if status:
            raise RuntimeError(f"Cannot stage external specimen {path}: {status}")
        # Independent binary decode verifies every field, including opaque metadata.
        raw = struct.unpack_from("<6I", data, 8)
        actual = (result.control, result.flags, result.load, result.entry,
                  result.hook, result.payload_size)
        if actual != raw or bytes(result.metadata) != data[32:64]:
            raise RuntimeError(f"Field mismatch: {path}")
        if result.kind != TROJAN:
            options = PatchOptions()
            if LIB.pops_patch_options(c.byref(result), c.byref(options)):
                raise RuntimeError(f"Unsupported PATCH options: {path}")
        if path in files:
            kinds[result.kind] += 1
            controls[result.control] += 1
    print(f"External corpus PASS: {len(files)} files + 2 root specimens")
    print(f"Kinds: {dict(kinds)} (0=Trojan, 1=config, 2=data)")
    print(f"Control words: {dict(controls)}")


def main():
    global LIB
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", type=Path)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--pak", type=Path, action="append", default=[])
    parser.add_argument("--iop-image", type=Path, action="append", default=[])
    parser.add_argument("--loader-source", type=Path,
                        help="Optional measured original R5900 export for independent patch parity")
    args = parser.parse_args()
    compiler = shutil.which(os.environ.get("CC", "gcc"))
    if not compiler:
        raise RuntimeError("A host GCC-compatible C compiler is required (set CC)")
    build = ROOT / "build" / "pops-host"
    build.mkdir(parents=True, exist_ok=True)
    library = build / ("pops_external.dll" if os.name == "nt" else "pops_external.so")
    subprocess.run([compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic",
                    "-shared", "-fPIC", "-I", str(ROOT / "common/include"),
                    "-I", str(ROOT / "third_party/lzma"),
                    str(ROOT / "common/src/pops_external.c"),
                    str(ROOT / "common/src/pops_pak.c"),
                    str(ROOT / "common/src/pops_iop_image.c"),
                    str(ROOT / "common/src/pops_profile.c"),
                    str(ROOT / "common/src/pops_boot_stage.c"),
                    str(ROOT / "common/src/pops_core_patches.c"),
                    str(ROOT / "third_party/lzma/LzmaDec.c"), "-o", str(library)], check=True)
    LIB = c.CDLL(str(library))
    LIB.pops_container_inspect.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(Container)]
    LIB.pops_container_plan.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32,
                                      c.c_size_t, c.POINTER(Plan)]
    LIB.pops_container_stage.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32,
                                       c.c_void_p, c.c_size_t,
                                       c.POINTER(c.c_uint32), c.c_size_t]
    LIB.pops_patch_options.argtypes = [c.POINTER(Container), c.POINTER(PatchOptions)]
    LIB.pops_elf_inspect.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(ElfInfo)]
    LIB.pops_pak_inspect.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(c.c_uint32)]
    LIB.pops_pak_decode.argtypes = [c.c_void_p, c.c_size_t, c.c_void_p,
                                  c.c_size_t, c.POINTER(c.c_size_t)]
    LIB.pops_iop_image_inspect.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(IopImage)]
    LIB.pops_image_sha256.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(c.c_uint8)]
    LIB.pops_boot_plan_pak.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(BootPlan)]
    LIB.pops_boot_plan_elf.argtypes = [c.c_void_p, c.c_size_t, c.c_void_p,
                                     c.c_size_t, c.POINTER(BootPlan)]
    LIB.pops_boot_stage_pak.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(BootBuffers)]
    LIB.pops_boot_stage_elf.argtypes = [c.c_void_p, c.c_size_t, c.c_void_p,
                                      c.c_size_t, c.POINTER(BootBuffers)]
    LIB.pops_core_patches_stage.argtypes = [c.c_uint32, c.c_void_p, c.c_size_t, c.c_uint32]
    LIB.pops_core_image_identify.argtypes = [c.c_void_p, c.c_size_t]
    for name in ("pops_container_inspect", "pops_container_plan", "pops_elf_inspect",
                 "pops_container_stage", "pops_patch_options", "pops_pak_inspect",
                 "pops_pak_decode", "pops_iop_image_inspect", "pops_image_sha256",
                 "pops_boot_plan_pak", "pops_boot_plan_elf", "pops_boot_stage_pak",
                 "pops_boot_stage_elf", "pops_core_patches_stage", "pops_core_image_identify"):
        getattr(LIB, name).restype = c.c_int
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(InspectorTests))
    if not result.wasSuccessful():
        return 1
    original_writes = read_original_writes(args.loader_source) if args.loader_source else None
    if args.corpus_root:
        check_corpus(args.corpus_root)
    if args.elf:
        status, info = inspect_elf(args.elf.read_bytes())
        if status:
            raise RuntimeError(f"External ELF rejected: {status}")
        print(f"External MIPS ELF structure PASS: entry=0x{info.entry:08x}, "
              f"load segments={info.load_segments}; POPS identity not established")
    for path in args.pak:
        data = path.read_bytes()
        length = c.c_uint32()
        if LIB.pops_pak_inspect(data, len(data), c.byref(length)):
            raise RuntimeError(f"External PAK header rejected: {path}")
        output = c.create_string_buffer(length.value)
        decoded = c.c_size_t()
        if LIB.pops_pak_decode(data, len(data), output, len(output), c.byref(decoded)):
            raise RuntimeError(f"External PAK decode rejected: {path}")
        reference = lzma.LZMADecompressor(format=lzma.FORMAT_RAW,
            filters=[dict(id=lzma.FILTER_LZMA1, dict_size=1 << 23, lc=3, lp=0, pb=2)])
        expected = reference.decompress(b'\0' + data[4:8][::-1] + data[8:],
                                        max_length=length.value)
        if output.raw != expected or decoded.value != length.value:
            raise RuntimeError(f"Independent PAK decoder mismatch: {path}")
        print(f"External PAK decode PASS: {path.name}, {decoded.value} bytes, "
              f"SHA256={hashlib.sha256(output.raw).hexdigest()}")
        # This offset belongs to the measured reference core, not arbitrary PAKs.
        core_size = 0x302e60
        image = output.raw[core_size:]
        info = IopImage()
        if LIB.pops_iop_image_inspect(image, len(image), c.byref(info)):
            raise RuntimeError(f"Reference PAK appended IOP image rejected: {path}")
        print(f"Reference appended IOP structure PASS: {info.files} ROMDIR files")
        plan = BootPlan()
        if LIB.pops_boot_plan_pak(output, len(output), c.byref(plan)):
            raise RuntimeError(f"External PAK profile rejected: {path}")
        expected_variant = 1 if len(image) == 265233 else 2
        if (plan.source, plan.iop_variant, plan.entry, plan.core_size,
            plan.iop_offset, plan.iop_size) != (1, expected_variant, 0x200008,
                                               core_size, core_size, len(image)):
            raise RuntimeError(f"External PAK plan mismatch: {path}")
        # A valid ROMDIR does not authorize a modified module or POPS core.
        for offset in (0x100, core_size + 0x1000):
            altered = bytearray(output.raw)
            altered[offset] ^= 1
            rejected = BootPlan()
            rejected.entry = 0x12345678
            if not LIB.pops_boot_plan_pak(bytes(altered), len(altered), c.byref(rejected)):
                raise RuntimeError(f"Modified external image accepted: {path}")
            if rejected.entry != 0x12345678:
                raise RuntimeError("Failed profile check changed its output")
        print(f"External PAK identity and guarded boot plan PASS: variant={plan.iop_variant}")
        check_boot_staging(plan, output.raw, original_writes=original_writes)
    for path in args.iop_image:
        image = path.read_bytes()
        info = IopImage()
        if LIB.pops_iop_image_inspect(image, len(image), c.byref(info)):
            raise RuntimeError(f"External IOP image rejected: {path}")
        print(f"External IOP structure PASS: {path.name}, {info.files} ROMDIR files")
        if args.elf:
            executable = args.elf.read_bytes()
            plan = BootPlan()
            if LIB.pops_boot_plan_elf(executable, len(executable), image,
                                      len(image), c.byref(plan)):
                raise RuntimeError(f"Loose dependency profile rejected: {path}")
            if (plan.source, plan.iop_variant, plan.entry, plan.iop_size) != (0, 0, 0x200008, len(image)):
                raise RuntimeError("Loose dependency boot plan mismatch")
            print("Loose ELF/IOPRP identity and guarded boot plan PASS")
            check_boot_staging(plan, executable, image, original_writes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
