#!/usr/bin/env python3
"""Compile and exercise the production C inspector without PS2SDK or Sony files.

Optional --corpus-root reads an external REPOP popstarter/ tree; --elf reads an
external ELF. Neither input is copied into the repository or executed.
"""

import argparse
import collections
import ctypes as c
import os
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
    args = parser.parse_args()
    compiler = shutil.which(os.environ.get("CC", "gcc"))
    if not compiler:
        raise RuntimeError("A host GCC-compatible C compiler is required (set CC)")
    build = ROOT / "build" / "pops-host"
    build.mkdir(parents=True, exist_ok=True)
    library = build / ("pops_external.dll" if os.name == "nt" else "pops_external.so")
    subprocess.run([compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic",
                    "-shared", "-fPIC", "-I", str(ROOT / "common/include"),
                    str(ROOT / "common/src/pops_external.c"), "-o", str(library)], check=True)
    LIB = c.CDLL(str(library))
    LIB.pops_container_inspect.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(Container)]
    LIB.pops_container_plan.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32,
                                      c.c_size_t, c.POINTER(Plan)]
    LIB.pops_container_stage.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32,
                                       c.c_void_p, c.c_size_t,
                                       c.POINTER(c.c_uint32), c.c_size_t]
    LIB.pops_patch_options.argtypes = [c.POINTER(Container), c.POINTER(PatchOptions)]
    LIB.pops_elf_inspect.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(ElfInfo)]
    for name in ("pops_container_inspect", "pops_container_plan", "pops_elf_inspect",
                 "pops_container_stage", "pops_patch_options"):
        getattr(LIB, name).restype = c.c_int
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(InspectorTests))
    if not result.wasSuccessful():
        return 1
    if args.corpus_root:
        check_corpus(args.corpus_root)
    if args.elf:
        status, info = inspect_elf(args.elf.read_bytes())
        if status:
            raise RuntimeError(f"External ELF rejected: {status}")
        print(f"External MIPS ELF structure PASS: entry=0x{info.entry:08x}, "
              f"load segments={info.load_segments}; POPS identity not established")
    return 0


if __name__ == "__main__":
    sys.exit(main())
