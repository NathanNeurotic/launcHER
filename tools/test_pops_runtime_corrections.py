#!/usr/bin/env python3
"""Exercise PSXCore runtime corrections staging, bounds, atomicity and guards."""

import argparse
import ctypes as c
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

POPS_FILE_OK = 0
POPS_FILE_INVALID = -1
POPS_FILE_UNSUPPORTED = -2
POPS_FILE_RANGE = -3
POPS_FILE_GUARD = -4

POPS_FIX_TEXTURE_WINDOW   = 1 << 0
POPS_FIX_GPU_DMA_ZERO     = 1 << 1
POPS_FIX_CDDA_SETMODE     = 1 << 2
POPS_FIX_SPU_ENABLE_RESET = 1 << 3
POPS_FIX_GTE_RES1         = 1 << 4
POPS_FIX_ALL              = (1 << 5) - 1

CORRECTIONS = [
    ("TEXTURE_WINDOW",   POPS_FIX_TEXTURE_WINDOW,   0x0021d6a4, 0x240f0001, 0x240f0000),
    ("GPU_DMA_ZERO",     POPS_FIX_GPU_DMA_ZERO,     0x0020ac5c, 0x54800006, 0x10000006),
    ("CDDA_SETMODE",     POPS_FIX_CDDA_SETMODE,     0x0020ead4, 0x10400009, 0x00000000),
    ("SPU_ENABLE_RESET", POPS_FIX_SPU_ENABLE_RESET, 0x00213c20, 0x0c084f80, 0x00000000),
    ("GTE_RES1",         POPS_FIX_GTE_RES1,         0x0024a94c, 0x00000003, 0x00000000),
]

CANONICAL_CORE_HASH = "38ecd425324a1244e90ae68b927496b9af511fd0ed89761199fb6eb699e71ab0"
CANONICAL_ELF_HASH = "59df3389c4df88a572daa720b05507c52c34eddfa0031a6fbeec55e0c2d0fcb1"

MOCK_LIB = None
PROD_LIB = None


class ElfInfo(c.Structure):
    _fields_ = [("entry", c.c_uint32), ("load_segments", c.c_uint16)]


class BootPlan(c.Structure):
    _fields_ = [("source", c.c_int), ("iop_variant", c.c_int)] + [
        (name, c.c_uint32) for name in ("entry", "core_address", "core_size",
        "bss_address", "bss_size", "scratchpad_size", "iop_offset", "iop_size")
    ]


class BootBuffers(c.Structure):
    _fields_ = [("ram_base", c.c_uint32), ("ram", c.c_void_p), ("ram_size", c.c_size_t),
                ("scratchpad", c.c_void_p), ("scratchpad_size", c.c_size_t),
                ("iop", c.c_void_p), ("iop_size", c.c_size_t)]


def build_libraries():
    compiler = shutil.which(os.environ.get("CC", "gcc"))
    if not compiler:
        raise RuntimeError("Host GCC-compatible compiler required")
    build_dir = ROOT / "build" / "pops-host"
    build_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".dll" if os.name == "nt" else ".so"

    mock_path = build_dir / f"pops_runtime_mock{suffix}"
    subprocess.run([
        compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic",
        "-shared", "-fPIC", "-I", str(ROOT / "common/include"),
        str(ROOT / "common/src/pops_core_patches.c"),
        str(ROOT / "tools/fixtures/test_pops_runtime_corrections.c"),
        "-o", str(mock_path)
    ], check=True)

    prod_path = build_dir / f"pops_runtime_prod{suffix}"
    subprocess.run([
        compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic",
        "-shared", "-fPIC", "-I", str(ROOT / "common/include"),
        "-I", str(ROOT / "third_party/lzma"),
        str(ROOT / "common/src/pops_core_patches.c"),
        str(ROOT / "common/src/pops_profile.c"),
        str(ROOT / "common/src/pops_external.c"),
        str(ROOT / "common/src/pops_boot_stage.c"),
        str(ROOT / "common/src/pops_iop_image.c"),
        str(ROOT / "third_party/lzma/LzmaDec.c"),
        "-o", str(prod_path)
    ], check=True)

    mock = c.CDLL(str(mock_path))
    mock.pops_core_runtime_corrections_stage.argtypes = [
        c.c_uint32, c.c_void_p, c.c_size_t, c.c_uint32
    ]
    mock.pops_core_runtime_corrections_stage.restype = c.c_int
    mock.test_set_mock_identify_status.argtypes = [c.c_int]
    mock.test_set_mock_identify_status.restype = None
    mock.pops_core_image_identify_baseline_patched.argtypes = [c.c_void_p, c.c_size_t]
    mock.pops_core_image_identify_baseline_patched.restype = c.c_int

    prod = c.CDLL(str(prod_path))
    prod.pops_core_runtime_corrections_stage.argtypes = [
        c.c_uint32, c.c_void_p, c.c_size_t, c.c_uint32
    ]
    prod.pops_core_runtime_corrections_stage.restype = c.c_int
    prod.pops_core_image_identify.argtypes = [c.c_void_p, c.c_size_t]
    prod.pops_core_image_identify.restype = c.c_int
    prod.pops_core_image_identify_baseline_patched.argtypes = [c.c_void_p, c.c_size_t]
    prod.pops_core_image_identify_baseline_patched.restype = c.c_int
    prod.pops_core_patches_stage.argtypes = [c.c_uint32, c.c_void_p, c.c_size_t, c.c_uint32]
    prod.pops_core_patches_stage.restype = c.c_int
    prod.pops_elf_inspect.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(ElfInfo)]
    prod.pops_elf_inspect.restype = c.c_int
    prod.pops_boot_plan_elf.argtypes = [
        c.c_void_p, c.c_size_t, c.c_void_p, c.c_size_t, c.POINTER(BootPlan)
    ]
    prod.pops_boot_plan_elf.restype = c.c_int
    prod.pops_boot_stage_elf.argtypes = [
        c.c_void_p, c.c_size_t, c.c_void_p, c.c_size_t, c.POINTER(BootBuffers)
    ]
    prod.pops_boot_stage_elf.restype = c.c_int

    return mock, prod


class RuntimeCorrectionsUnitTests(unittest.TestCase):
    def setUp(self):
        MOCK_LIB.test_set_mock_identify_status(0)
        self.base = 0x100000
        self.span = 0x402e60
        self.buf = c.create_string_buffer(self.span)
        for _, _, addr, expected, _ in CORRECTIONS:
            offset = addr - self.base
            struct.pack_into("<I", self.buf, offset, expected)

    def test_invalid_mask_and_null_buffer(self):
        self.assertEqual(
            MOCK_LIB.pops_core_runtime_corrections_stage(self.base, None, self.span, POPS_FIX_ALL),
            POPS_FILE_INVALID
        )
        self.assertEqual(
            MOCK_LIB.pops_core_runtime_corrections_stage(self.base, self.buf, self.span, 0),
            POPS_FILE_INVALID
        )
        self.assertEqual(
            MOCK_LIB.pops_core_runtime_corrections_stage(self.base, self.buf, self.span, POPS_FIX_ALL + 1),
            POPS_FILE_INVALID
        )
        self.assertEqual(
            MOCK_LIB.pops_core_runtime_corrections_stage(self.base, self.buf, self.span, 0x80000000),
            POPS_FILE_INVALID
        )

    def test_range_bounds(self):
        self.assertEqual(
            MOCK_LIB.pops_core_runtime_corrections_stage(0x0, self.buf, self.span, POPS_FIX_ALL),
            POPS_FILE_RANGE
        )
        self.assertEqual(
            MOCK_LIB.pops_core_runtime_corrections_stage(0x0FFFFF, self.buf, self.span, POPS_FIX_ALL),
            POPS_FILE_RANGE
        )
        self.assertEqual(
            MOCK_LIB.pops_core_runtime_corrections_stage(0x200001, self.buf, self.span, POPS_FIX_ALL),
            POPS_FILE_RANGE
        )
        self.assertEqual(
            MOCK_LIB.pops_core_runtime_corrections_stage(self.base, self.buf, 0x502e60 - self.base - 1, POPS_FIX_ALL),
            POPS_FILE_RANGE
        )
        self.assertEqual(
            MOCK_LIB.pops_core_runtime_corrections_stage(0x200000, self.buf, 0x302e5f, POPS_FIX_ALL),
            POPS_FILE_RANGE
        )
        self.assertEqual(
            MOCK_LIB.pops_core_runtime_corrections_stage(self.base, self.buf, 0x2000000 - self.base + 1, POPS_FIX_ALL),
            POPS_FILE_RANGE
        )

    def test_identify_failure_rejects_without_mutation(self):
        MOCK_LIB.test_set_mock_identify_status(-4)
        snapshot = bytes(self.buf.raw)
        res = MOCK_LIB.pops_core_runtime_corrections_stage(self.base, self.buf, self.span, POPS_FIX_ALL)
        self.assertEqual(res, POPS_FILE_GUARD)
        self.assertEqual(self.buf.raw, snapshot)

    def test_production_library_rejects_unknown_identity_without_mutation(self):
        unknown = c.create_string_buffer(self.span)
        snapshot = bytes(unknown.raw)
        res = PROD_LIB.pops_core_runtime_corrections_stage(self.base, unknown, self.span, POPS_FIX_ALL)
        self.assertEqual(res, POPS_FILE_GUARD)
        self.assertEqual(unknown.raw, snapshot)

    def test_single_byte_guard_failure_rejects_atomically_without_mutation(self):
        for name, _, addr, _, _ in CORRECTIONS:
            offset = addr - self.base
            for byte_pos in range(4):
                corrupted = bytearray(self.buf.raw)
                corrupted[offset + byte_pos] ^= 0x5A
                test_buf = c.create_string_buffer(bytes(corrupted), len(corrupted))
                snapshot = bytes(test_buf.raw)

                res = MOCK_LIB.pops_core_runtime_corrections_stage(
                    self.base, test_buf, self.span, POPS_FIX_ALL
                )
                self.assertEqual(
                    res, POPS_FILE_GUARD,
                    f"Guard failure not triggered for {name} byte {byte_pos}"
                )
                self.assertEqual(
                    test_buf.raw, snapshot,
                    f"Buffer mutated on guard failure for {name} byte {byte_pos}"
                )

    def test_unselected_guards_ignored(self):
        last_name, _, last_addr, _, _ = CORRECTIONS[-1]
        corrupted = bytearray(self.buf.raw)
        corrupted[last_addr - self.base] ^= 0xFF
        test_buf = c.create_string_buffer(bytes(corrupted), len(corrupted))

        first_name, first_mask, first_addr, _, first_repl = CORRECTIONS[0]
        res = MOCK_LIB.pops_core_runtime_corrections_stage(
            self.base, test_buf, self.span, first_mask
        )
        self.assertEqual(res, POPS_FILE_OK)
        val = struct.unpack_from("<I", test_buf, first_addr - self.base)[0]
        self.assertEqual(val, first_repl)
        # Corrupted byte at unselected patch remains untouched.
        self.assertEqual(test_buf[last_addr - self.base], bytes([corrupted[last_addr - self.base]]))

    def test_individual_corrections_application(self):
        for name, mask, addr, _, repl in CORRECTIONS:
            test_buf = c.create_string_buffer(bytes(self.buf.raw), len(self.buf.raw))
            snapshot = bytearray(self.buf.raw)
            struct.pack_into("<I", snapshot, addr - self.base, repl)

            res = MOCK_LIB.pops_core_runtime_corrections_stage(
                self.base, test_buf, self.span, mask
            )
            self.assertEqual(res, POPS_FILE_OK, f"Failed applying {name}")
            self.assertEqual(
                test_buf.raw, bytes(snapshot),
                f"Memory mutation mismatch when applying single correction {name}"
            )

    def test_combined_application_and_reapplication_guard(self):
        test_buf = c.create_string_buffer(bytes(self.buf.raw), len(self.buf.raw))
        expected_memory = bytearray(self.buf.raw)
        for _, _, addr, _, repl in CORRECTIONS:
            struct.pack_into("<I", expected_memory, addr - self.base, repl)

        res = MOCK_LIB.pops_core_runtime_corrections_stage(
            self.base, test_buf, self.span, POPS_FIX_ALL
        )
        self.assertEqual(res, POPS_FILE_OK)
        self.assertEqual(test_buf.raw, bytes(expected_memory))

        # Reapplication fails closed because guards are now the replacement opcodes.
        res2 = MOCK_LIB.pops_core_runtime_corrections_stage(
            self.base, test_buf, self.span, POPS_FIX_ALL
        )
        self.assertEqual(res2, POPS_FILE_GUARD)
        self.assertEqual(test_buf.raw, bytes(expected_memory))


def exercise_canonical_pops_elf(elf_path):
    print(f"Exercising canonical POPS ELF: {elf_path}")
    elf_data = elf_path.read_bytes()
    elf_sha = hashlib.sha256(elf_data).hexdigest()
    if elf_sha != CANONICAL_ELF_HASH:
        raise RuntimeError(f"Unexpected POPS ELF hash {elf_sha}; expected {CANONICAL_ELF_HASH}")

    iop_path = elf_path.parent / "IOPRP252.IMG"
    if iop_path.is_file():
        iop_data = iop_path.read_bytes()
        plan = BootPlan()
        if PROD_LIB.pops_boot_plan_elf(elf_data, len(elf_data), iop_data, len(iop_data), c.byref(plan)):
            raise RuntimeError("pops_boot_plan_elf failed on canonical POPS ELF and IOPRP252.IMG")

        ram_base = 0x100000
        ram_size = plan.bss_address + plan.bss_size - ram_base
        ram = c.create_string_buffer(ram_size)
        scratch = c.create_string_buffer(0x4000)
        iop_buf = c.create_string_buffer(len(iop_data) + 16)
        buffers = BootBuffers(
            ram_base, c.addressof(ram), ram_size,
            c.addressof(scratch), len(scratch),
            c.addressof(iop_buf), len(iop_data)
        )

        if PROD_LIB.pops_boot_stage_elf(elf_data, len(elf_data), iop_data, len(iop_data), c.byref(buffers)):
            raise RuntimeError("pops_boot_stage_elf failed on canonical POPS ELF")
        core_size = plan.core_size
    else:
        ram_base = 0x100000
        ram_size = 0x800000
        ram = c.create_string_buffer(ram_size)
        phoff = struct.unpack_from("<I", elf_data, 28)[0]
        phnum = struct.unpack_from("<H", elf_data, 44)[0]
        for i in range(phnum):
            p_type, p_offset, p_vaddr, _, p_filesz, _, _, _ = struct.unpack_from(
                "<8I", elf_data, phoff + i * 32
            )
            if p_type == 1 and p_filesz > 0:
                ram[p_vaddr - ram_base : p_vaddr - ram_base + p_filesz] = elf_data[p_offset : p_offset + p_filesz]
        core_size = 0x302e60

    core_start = 0x200000 - ram_base
    core_bytes = ram.raw[core_start:core_start + core_size]
    core_sha = hashlib.sha256(core_bytes).hexdigest()
    if core_sha != CANONICAL_CORE_HASH:
        raise RuntimeError(f"Staged core SHA256 mismatch: {core_sha} != {CANONICAL_CORE_HASH}")
    if PROD_LIB.pops_core_image_identify(core_bytes, len(core_bytes)):
        raise RuntimeError("pops_core_image_identify rejected staged canonical core")

    # 1. Verify exact pristine opcodes in canonical POPS.ELF
    for name, _, addr, expected, _ in CORRECTIONS:
        offset = addr - ram_base
        val = struct.unpack_from("<I", ram, offset)[0]
        if val != expected:
            raise RuntimeError(f"Canonical site mismatch for {name} at 0x{addr:08x}: actual 0x{val:08x} != expected 0x{expected:08x}")
    print(f"Canonical POPS core opcode verification PASS ({len(CORRECTIONS)} sites verified)")

    # 2. Guard failure test on real core
    before = bytes(ram.raw)
    ram[CORRECTIONS[0][2] - ram_base] = b'\x00'
    corrupted = bytes(ram.raw)
    res = PROD_LIB.pops_core_runtime_corrections_stage(ram_base, ram, ram_size, POPS_FIX_ALL)
    if res != POPS_FILE_GUARD or ram.raw != corrupted:
        raise RuntimeError("Guard failure on canonical core did not reject cleanly without mutation")
    ram.raw = before

    # 3. Individual correction verification against canonical core
    for name, mask, addr, expected, repl in CORRECTIONS:
        test_ram = c.create_string_buffer(before, len(before))
        expected_buf = bytearray(before)
        struct.pack_into("<I", expected_buf, addr - ram_base, repl)
        res = PROD_LIB.pops_core_runtime_corrections_stage(ram_base, test_ram, ram_size, mask)
        if res != POPS_FILE_OK:
            raise RuntimeError(f"Failed applying single correction {name} on canonical core: {res}")
        if test_ram.raw != bytes(expected_buf):
            raise RuntimeError(f"Single correction {name} produced unexpected memory mutation")
    print("Individual runtime correction applications PASS on canonical POPS core")

    # 4. Combined POPS_FIX_ALL on canonical core
    test_ram = c.create_string_buffer(before, len(before))
    expected_buf = bytearray(before)
    for _, _, addr, _, repl in CORRECTIONS:
        struct.pack_into("<I", expected_buf, addr - ram_base, repl)

    res = PROD_LIB.pops_core_runtime_corrections_stage(ram_base, test_ram, ram_size, POPS_FIX_ALL)
    if res != POPS_FILE_OK:
        raise RuntimeError(f"Combined POPS_FIX_ALL failed on canonical core: {res}")
    if test_ram.raw != bytes(expected_buf):
        raise RuntimeError("Combined POPS_FIX_ALL produced unexpected memory mutation")
    print("Combined POPS_FIX_ALL PASS: all 5 sites updated, entire RAM compared")

    # 5. Reapplication fails closed
    res = PROD_LIB.pops_core_runtime_corrections_stage(ram_base, test_ram, ram_size, POPS_FIX_ALL)
    if res != POPS_FILE_GUARD or test_ram.raw != bytes(expected_buf):
        raise RuntimeError("Reapplication on patched canonical core did not fail closed")
    print("Reapplication on patched canonical core fails closed PASS")

    # 6. Baseline core patches followed by runtime corrections (production launcher order)
    test_ram_seq = c.create_string_buffer(before, len(before))
    res_base = PROD_LIB.pops_core_patches_stage(ram_base, test_ram_seq, ram_size, 0x7F)
    if res_base != POPS_FILE_OK:
        raise RuntimeError(f"Baseline core patches failed on canonical core: {res_base}")
    patched_core_bytes = test_ram_seq.raw[core_start:core_start + core_size]
    if PROD_LIB.pops_core_image_identify_baseline_patched(patched_core_bytes, len(patched_core_bytes)) != POPS_FILE_OK:
        raise RuntimeError("pops_core_image_identify_baseline_patched rejected baseline-patched canonical core")
    res_corr = PROD_LIB.pops_core_runtime_corrections_stage(ram_base, test_ram_seq, ram_size, POPS_FIX_ALL)
    if res_corr != POPS_FILE_OK:
        raise RuntimeError(f"pops_core_runtime_corrections_stage failed after baseline patches: {res_corr}")
    for _, _, addr, _, repl in CORRECTIONS:
        val = struct.unpack_from("<I", test_ram_seq, addr - ram_base)[0]
        if val != repl:
            raise RuntimeError(f"Sequential staging correction site mismatch at 0x{addr:08x}: actual 0x{val:08x} != repl 0x{repl:08x}")
    print("Sequential staging (baseline patches + runtime corrections) PASS on canonical POPS core")


def find_default_pops_elf():
    candidates = [
        os.environ.get("POPS_ELF"),
        Path("C:/Users/natha/Github/POPS/POPS.ELF"),
        ROOT.parent / "POPS" / "POPS.ELF",
    ]
    for c_path in candidates:
        if c_path:
            p = Path(c_path)
            if p.is_file():
                return p
    return None


def main():
    global MOCK_LIB, PROD_LIB
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, help="Optional canonical POPS.ELF for end-to-end verification")
    args = parser.parse_args()

    MOCK_LIB, PROD_LIB = build_libraries()

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeCorrectionsUnitTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        return 1

    elf_target = args.elf or find_default_pops_elf()
    if elf_target:
        exercise_canonical_pops_elf(elf_target)
    else:
        print("No canonical POPS.ELF supplied or detected; skipped external binary tests.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
