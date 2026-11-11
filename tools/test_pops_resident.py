#!/usr/bin/env python3
"""Host tests for launcHER's POPS resident code (common/include/pops_resident.h).

The per-frame logic and the launcher-side install/hook helpers are compiled
natively; the EE image itself is built by CMake. Nothing here has run on a
console."""
import ctypes as c
import errno
import os
import random
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = 0x0143A000
LIMIT = 0x01460000
CORE = 0x00200000
LUI, ADDIU = 0x0021B184, 0x0021B18C
LUI_PRISTINE, ADDIU_PRISTINE = 0x3C050022, 0x24A5CD68
MAX_CHEATS = 256
COMPILED_MAX = 2 * MAX_CHEATS + 4


class CheatEntry(c.Structure):
    _fields_ = [("address", c.c_uint32), ("value", c.c_uint32), ("type", c.c_uint8),
                ("cond", c.c_uint8), ("skip", c.c_uint8), ("reserved", c.c_uint8)]


class ResidentConfig(c.Structure):
    _fields_ = [
        ("gs_display", c.c_uint64),
        ("flags", c.c_uint32),
        ("pops_vblank", c.c_uint32),
        ("ram_base_ptr", c.c_uint32),
        ("frame", c.c_uint32),
        ("safe_mode", c.c_uint16),
        ("cheat_count", c.c_uint16),
        ("pad_override", c.c_uint8),
        ("pad_id", c.c_uint8 * 2),
        ("gte_divisor", c.c_uint8),
        ("cheats", CheatEntry * COMPILED_MAX),
        ("timings_ready", c.c_uint8),
        ("reserved", c.c_uint8 * 3),
        ("libcrypt2_code", c.c_uint32 * 23),
        ("reset_vector", c.c_uint32),
        ("disc_selected", c.c_uint32),
        ("disc_align", c.c_uint8 * 8),  # disc_slot is 16-byte aligned
        ("disc_slot", (c.c_uint8 * 0x60) * 4),
        ("disc_tail", c.c_uint32 * 8),
    ]


class CheatMemory(c.Structure):
    _fields_ = [("ps1", c.c_void_p), ("ee", c.c_void_p), ("ee_size", c.c_uint32),
                ("spr", c.c_void_p), ("ps1spr", c.c_void_p)]


class Header(c.Structure):
    _fields_ = [
        ("magic", c.c_uint32), ("version", c.c_uint16), ("header_size", c.c_uint16),
        ("file_size", c.c_uint32), ("image_size", c.c_uint32),
        ("vblank_entry", c.c_uint32), ("config_addr", c.c_uint32),
        ("display_entry", c.c_uint32),
        ("progressive_entry", c.c_uint32),
        ("pad_read_entry", c.c_uint32),
        ("pad_read_exit", c.c_uint32),
        ("gte_scale_entry", c.c_uint32),
        ("gte_divide_entry", c.c_uint32),
        ("gte_ultra_entry", c.c_uint32),
        ("gp1_entry", c.c_uint32),
        ("guard_entry", c.c_uint32 * 9),
        ("recompiler_entry", c.c_uint32),
        ("recompiler_emit", c.c_uint32 * 4),
    ]


def build():
    out = Path(tempfile.mkdtemp())
    lib = out / ("resident.dll" if os.name == "nt" else "resident.so")
    sources = ["common/src/pops_resident.c", "common/src/pops_resident_engine.c",
               "common/src/pops_config.c", "tools/fixtures/pops_config_host_io.c",
               "common/src/pops_compat_db.c", "common/src/pops_modes_patches.c",
               "common/src/pops_builtin_db.c", "common/src/pops_builtin_db_data.c",
               "common/src/pops_external.c", "common/src/pops_vcd.c"]
    subprocess.run(["gcc", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra",
                    "-Dfopen=pops_test_fopen", "-Dfgets=pops_test_fgets",
                    "-Dferror=pops_test_ferror", "-Dfclose=pops_test_fclose",
                    "-I", str(ROOT / "common/include")] +
                   [str(ROOT / s) for s in sources] + ["-o", str(lib)], check=True)
    return c.CDLL(str(lib))


L = build()
L.pops_resident_cheat_pass.argtypes = [c.c_void_p, c.POINTER(CheatEntry), c.c_uint16]
L.pops_resident_cheat_pass.restype = None
L.pops_resident_frame.argtypes = [c.POINTER(ResidentConfig), c.c_void_p]
L.pops_resident_frame_mem.argtypes = [c.POINTER(ResidentConfig), c.POINTER(CheatMemory)]
L.pops_resident_check_image.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(Header)]
L.pops_resident_hook_core.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
L.pops_resident_hook_gp1.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
L.pops_resident_hook_display.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
L.pops_resident_install.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32, c.c_void_p, c.c_size_t,
                                    c.POINTER(ResidentConfig)]
L.pops_resident_pad_ids.argtypes = [c.POINTER(ResidentConfig), c.c_void_p]
L.pops_resident_pad_ids.restype = None
L.pops_resident_d2ls.argtypes = [c.c_void_p, c.c_uint32]
L.pops_resident_d2ls.restype = None
L.pops_resident_hook_pads.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32, c.c_uint32, c.c_uint32]
L.pops_resident_hook_widescreen.argtypes = [c.c_void_p, c.c_size_t, c.c_uint8, c.POINTER(Header)]
L.pops_resident_timings.argtypes = [c.POINTER(ResidentConfig), c.c_size_t, c.c_size_t]
L.pops_resident_timings.restype = None
L.pops_resident_build_config.argtypes = [c.POINTER(ResidentConfig), c.c_void_p]
L.pops_config_init.argtypes = [c.c_void_p]
L.pops_config_parse_line.argtypes = [c.c_void_p, c.c_char_p]
L.pops_config_parse_line.restype = c.c_int
L.pops_config_parse_discs.argtypes = [c.c_void_p, c.c_char_p, c.c_size_t]
L.pops_config_parse_discs.restype = None

HOTKEY_CD_INIT = c.CFUNCTYPE(c.c_int, c.c_void_p)


class HotkeyMemory(c.Structure):
    _fields_ = [("pad", c.c_size_t), ("emode", c.c_size_t), ("lid", c.c_size_t),
                ("scanlines", c.c_size_t), ("boot_path", c.c_size_t), ("card_state", c.c_size_t),
                ("cd_init", HOTKEY_CD_INIT)]


L.pops_resident_hotkeys.argtypes = [c.POINTER(ResidentConfig), c.POINTER(HotkeyMemory)]
L.pops_resident_hotkeys.restype = None


def assert_gp1_hook_always(test, src):
    """POPStarter hooks POPS's GP1 path on every launch (0x874790); so does
    launcHER, before the built-in entry and the user's commands, and it
    installs the resident image on every launch."""
    body = src[src.index("int launchPOPS("):]
    hook = "\n  res = pops_resident_hook_gp1((void *)stagedCore, plan.core_size, residentHdr.gp1_entry);\n"
    test.assertEqual(body.count("pops_resident_hook_gp1("), 1)
    test.assertIn(hook, body)
    at = body.index(hook)
    test.assertLess(body.index("res = pops_core_patches_stage("), at)
    test.assertLess(at, body.index("res = pops_builtin_apply(builtinId, (void *)stagedCore"))
    # The user's commands run inside pops_stage_user_files.
    test.assertLess(at, body.index("res = pops_stage_user_files("))
    test.assertIn("res = pops_apply_all_config_patches_rom(",
                  src[src.index("static int pops_stage_user_files("):src.index("int launchPOPS(")])
    test.assertIn("\n  res = pops_resident_install((void *)POPS_RESIDENT_BASE,", body)
    test.assertNotIn("if (residentNeeded) {\n    res = pops_resident_install(", body)


def cheats(*codes):
    arr = (CheatEntry * len(codes))()
    for i, (addr, val) in enumerate(codes):
        arr[i].address = addr & 0x1FFFFF
        arr[i].type = addr >> 24
        arr[i].value = val
    return arr


class CheatPass(unittest.TestCase):
    def run_codes(self, ram, *codes):
        arr = cheats(*codes)
        L.pops_resident_cheat_pass(c.addressof(ram), arr, len(codes))

    def test_writes(self):
        ram = (c.c_uint8 * 0x200000)()
        self.run_codes(ram, (0x80001000, 0xBEEF), (0x30001003, 0x12A5), (0x80000FFF, 0x1234))
        self.assertEqual(bytes(ram[0x1000:0x1004]), bytes([0xEF, 0xBE, 0, 0xA5]))
        # Odd 16-bit address writes the aligned halfword, as before.
        self.assertEqual(bytes(ram[0xFFE:0x1000]), bytes([0x34, 0x12]))

    def test_conditionals_gate_the_next_code(self):
        ram = (c.c_uint8 * 0x200000)()
        struct.pack_into("<H", ram, 0x10, 7)
        ram[0x20] = 3
        self.run_codes(ram,
                       (0xD0000010, 7), (0x30000100, 1),    # true: runs
                       (0xD1000010, 7), (0x30000101, 1),    # false: skipped
                       (0xD2000010, 8), (0x30000102, 1),    # 7 < 8: runs
                       (0xD3000010, 8), (0x30000103, 1),    # 7 > 8: skipped
                       (0xE0000020, 3), (0x30000104, 1),
                       (0xE1000020, 3), (0x30000105, 1),
                       (0x30000106, 1))                     # unconditional
        self.assertEqual(list(ram[0x100:0x107]), [1, 0, 1, 0, 1, 0, 1])

    def test_out_of_range_is_skipped(self):
        ram = (c.c_uint8 * 0x200000)()
        self.run_codes(ram, (0x801FFFFF, 0xFFFF), (0xD01FFFFF, 0), (0x30000000, 9))
        # An odd 16-bit write is aligned down (quirk 11), so it stays inside.
        self.assertEqual(ram[0x1FFFFE], 0xFF)
        self.assertEqual(ram[0], 0)  # the failed conditional skipped it
        self.run_codes(ram, (0x301FFFFF, 0x55))
        self.assertEqual(ram[0x1FFFFF], 0x55)

    def test_matches_the_launcher_side_engine(self):
        a = (c.c_uint8 * 0x200000)()
        b = (c.c_uint8 * 0x200000)()
        codes = cheats((0x80000010, 0x1111), (0xE0000010, 0x11), (0x30000020, 0x22))
        L.pops_resident_cheat_pass(c.addressof(a), codes, 3)
        L.pops_cheat_engine_tick.argtypes = [c.c_void_p, c.POINTER(CheatEntry), c.c_uint16]
        L.pops_cheat_engine_tick(c.addressof(b), codes, 3)
        self.assertEqual(bytes(a[:0x40]), bytes(b[:0x40]))


class Frame(unittest.TestCase):
    def config(self, *codes, safe=0):
        cfg = ResidentConfig()
        cfg.flags = 1
        cfg.safe_mode = safe
        cfg.cheat_count = len(codes)
        for i, e in enumerate(cheats(*codes)):
            cfg.cheats[i] = e
        return cfg

    def test_runs_every_frame(self):
        ram = (c.c_uint8 * 0x200000)()
        cfg = self.config((0x30000000, 5))
        self.assertEqual(L.pops_resident_frame(c.byref(cfg), c.addressof(ram)), 1)
        ram[0] = 0
        self.assertEqual(L.pops_resident_frame(c.byref(cfg), c.addressof(ram)), 1)
        self.assertEqual(ram[0], 5)
        self.assertEqual(cfg.frame, 2)

    def test_safe_mode_gates(self):
        """$SAFEMODE skips the codes while PS1 RAM 0x1ffea0 reads "STEM",
        $SAFEMODE2 while 0x1ffdf4 is 2; $SAFEMODE wins when both are set."""
        for safe, word, value, other in ((1, 0x1FFEA0, 0x4D455453, 0x1FFDF4),
                                         (2, 0x1FFDF4, 2, 0x1FFEA0),
                                         (3, 0x1FFEA0, 0x4D455453, 0x1FFDF4)):
            ram = (c.c_uint8 * 0x200000)()
            cfg = self.config((0x30000000, 5), safe=safe)
            struct.pack_into("<I", ram, word, value)
            struct.pack_into("<I", ram, other, 2 if other == 0x1FFDF4 else 0x4D455453)
            for _ in range(3):
                self.assertEqual(L.pops_resident_frame(c.byref(cfg), c.addressof(ram)), 0, safe)
            self.assertEqual(ram[0], 0)
            struct.pack_into("<I", ram, word, value ^ 1)
            self.assertEqual(L.pops_resident_frame(c.byref(cfg), c.addressof(ram)), 1, safe)
            self.assertEqual(ram[0], 5)
        # No gate: the gate words do not matter.
        ram = (c.c_uint8 * 0x200000)()
        struct.pack_into("<I", ram, 0x1FFEA0, 0x4D455453)
        struct.pack_into("<I", ram, 0x1FFDF4, 2)
        cfg = self.config((0x30000000, 5))
        self.assertEqual(L.pops_resident_frame(c.byref(cfg), c.addressof(ram)), 1)

    @unittest.skipUnless(os.environ.get("POPSTARTER_TEST_ELF"), "optional external POPStarter MAIN")
    def test_gates_match_the_original(self):
        """The original emits a four-word test in front of its codes:
        lui k0,0x0120; lw k0,off(k0); lui k1,hi; ori k1,k1,lo, then
        bne k0,k1 over a jump to its exit. Rebuild those words from the
        constants it assembles and compare with launcHER's gates."""
        from trace_original_pops_io import decode_main
        image = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
        word = lambda va: struct.unpack_from("<I", image, va - 0x870000)[0]
        imm = lambda va: word(va) & 0xFFFF

        def gate(hi_at, lo_at):
            # hi64 = (lui<<48 | ori<<32 | ori<<16 | [ori]) ; lo64 likewise
            hi = [imm(a) for a in hi_at]
            lo = [imm(a) for a in lo_at]
            w2, w3 = (hi[2] << 16) | (hi[3] if len(hi) > 3 else 0), (hi[0] << 16) | hi[1]
            w0, w1 = (lo[2] << 16) | lo[3], (lo[0] << 16) | lo[1]
            return w0, w1, w2, w3

        safe = gate((0x89E964, 0x89E968, 0x89E970, 0x89E978), (0x89E980, 0x89E984, 0x89E98C, 0x89E994))
        safe2 = gate((0x89E9EC, 0x89E9F0, 0x89E9F8), (0x89EA04, 0x89EA08, 0x89EA10, 0x89EA18))
        def decoded(w):
            lui_k0, lw_k0, lui_k1, ori_k1 = w
            self.assertEqual((lui_k0 >> 16, lw_k0 >> 16, lui_k1 >> 16, ori_k1 >> 16),
                             (0x3C1A, 0x8F5A, 0x3C1B, 0x377B))
            off = lw_k0 & 0xFFFF
            addr = ((lui_k0 & 0xFFFF) << 16) + (off - 0x10000 if off & 0x8000 else off)
            return addr - 0x01000000, ((lui_k1 & 0xFFFF) << 16) | (ori_k1 & 0xFFFF)
        self.assertEqual(decoded(safe), (0x1FFEA0, 0x4D455453))
        self.assertEqual(decoded(safe2), (0x1FFDF4, 2))
        # The second block: nop; bne k0,k1,+2; nop; j <exit> (skip the codes).
        tail_hi = (imm(0x89E9A8) << 16 | imm(0x89E9AC))
        tail_lo = imm(0x89E9B8) << 16 | imm(0x89E9BC)
        self.assertEqual((tail_lo, tail_hi), (0x175B0002, 0x0808E52C))
        # $SAFEMODE is tested first, then $SAFEMODE2 (0xec, then 0xf0).
        self.assertEqual((word(0x89E954), word(0x89E9DC)), (0x8FC300EC, 0x8FC300F0))

    def test_no_ram_base_yet_or_disabled(self):
        cfg = self.config((0x30000000, 5))
        self.assertEqual(L.pops_resident_frame(c.byref(cfg), None), 0)
        cfg.flags = 0
        ram = (c.c_uint8 * 0x200000)()
        self.assertEqual(L.pops_resident_frame(c.byref(cfg), c.addressof(ram)), 0)
        self.assertEqual(cfg.frame, 2)

    def test_frame_counter_saturates(self):
        cfg = self.config()
        cfg.frame = 0xFFFFFFFF
        L.pops_resident_frame(c.byref(cfg), None)
        self.assertEqual(cfg.frame, 0xFFFFFFFF)


L.pops_config_load_file.argtypes = [c.c_void_p, c.c_char_p]
L.pops_config_load_file.restype = c.c_int


def apply_cheats_txt(text, ram):
    """Load a CHEATS.TXT text the way the launcher does, build the resident
    config and run one cheat pass over a copy of ram. Returns (ram, rc)."""
    buf = (c.c_uint8 * 0x10000)()
    L.pops_config_init(c.addressof(buf))
    with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".TXT") as f:
        f.write(text.encode("latin-1"))
        path = f.name
    try:
        rc = L.pops_config_load_file(c.addressof(buf), path.encode())
    finally:
        os.unlink(path)
    if rc:
        return None, rc
    out = ResidentConfig()
    L.pops_resident_build_config(c.byref(out), c.addressof(buf))
    work = (c.c_uint8 * len(ram)).from_buffer_copy(ram)
    out.flags |= 1
    L.pops_resident_frame(c.byref(out), c.addressof(work))
    return bytes(work), 0


def resident_config_for(text):
    buf = (c.c_uint8 * 0x10000)()
    L.pops_config_init(c.addressof(buf))
    with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".TXT") as f:
        f.write(text.encode("latin-1"))
        path = f.name
    try:
        rc = L.pops_config_load_file(c.addressof(buf), path.encode())
    finally:
        os.unlink(path)
    if rc:
        return None, rc
    out = ResidentConfig()
    L.pops_resident_build_config(c.byref(out), c.addressof(buf))
    out.flags |= 1
    return out, 0


EE_SIZE = 0x02000000
EE_PS1 = 0x01000000


def apply_cheats_txt_mem(text, ee, spr, ps1spr):
    """apply_cheats_txt over the whole memory a PS2-format code can reach:
    EE RAM (32 MB, PS1 RAM at 0x01000000 inside it, as on the console), the
    EE scratchpad and the page at 0x5F800000. Returns ((ee, spr, ps1spr), rc)."""
    out, rc = resident_config_for(text)
    if rc:
        return None, rc
    work_ee = (c.c_uint8 * len(ee)).from_buffer_copy(ee)
    work_spr = (c.c_uint8 * len(spr)).from_buffer_copy(spr)
    work_ps1spr = (c.c_uint8 * len(ps1spr)).from_buffer_copy(ps1spr)
    mem = CheatMemory(c.addressof(work_ee) + EE_PS1, c.addressof(work_ee), EE_SIZE,
                      c.addressof(work_spr), c.addressof(work_ps1spr))
    L.pops_resident_frame_mem(c.byref(out), c.byref(mem))
    return (bytes(work_ee), bytes(work_spr), bytes(work_ps1spr)), 0


class CheatsTxt(unittest.TestCase):
    """CHEATS.TXT read and run the way POPStarter r13 compiles it. Each rule
    here was taken from the original's own cheat compiler run under
    emulation (tools/trace_original_pops_cheats.py)."""

    def run_text(self, text, setup=()):
        ram = bytearray(0x200000)
        for addr, val in setup:
            struct.pack_into("<H", ram, addr, val)
        got, rc = apply_cheats_txt(text, bytes(ram))
        self.assertEqual(rc, 0, text)
        return got

    def half(self, ram, addr):
        return struct.unpack_from("<H", ram, addr)[0]

    def test_codes_are_found_anywhere_in_the_text(self):
        ram = self.run_text("# $80001000 1234\nnote $30001002 0056\n"
                            "$80001004 abcd$80001006 0001\r\n$8000100A 0002 trailing\n")
        self.assertEqual([self.half(ram, a) for a in (0x1000, 0x1004, 0x1006, 0x100A)],
                         [0x1234, 0xABCD, 0x0001, 0x0002])
        self.assertEqual(ram[0x1002], 0x56)

    def test_layout_is_checked_column_by_column(self):
        ram = self.run_text("$80201000 1111\n$80001004  2222\n$80001006\t3333\n"
                            "$80001008 44445\n$85001000 5555\n80001010 6666\n"
                            "$C1001000 0000\n$50010202 0001\n$80001012 7777\n")
        self.assertEqual(ram[0x1000:0x1012], bytes(0x12))
        self.assertEqual(self.half(ram, 0x1012), 0x7777)
        # A character that is not hex counts as 0, in the address and value.
        ram = self.run_text("$8000100Z 1G2Z\n")
        self.assertEqual(self.half(ram, 0x1000), 0x1020)

    def test_master_code_gates_every_code(self):
        text = "$80001000 0001\n$C0002000 0007\n$C0002002 0009\n"
        self.assertEqual(self.half(self.run_text(text, [(0x2000, 7)]), 0x1000), 1)
        self.assertEqual(self.half(self.run_text(text, [(0x2000, 6)]), 0x1000), 0)
        # POPStarter compares a signed load with an unsigned value: 0x8000 and
        # up never match, so such a master code blocks everything.
        text = "$C0002000 8007\n$80001000 0001\n"
        self.assertEqual(self.half(self.run_text(text, [(0x2000, 0x8007)]), 0x1000), 0)

    def test_repeat_code(self):
        ram = self.run_text("$50000302 0001\n$80001000 0010\n$80001010 0005\n")
        self.assertEqual([self.half(ram, a) for a in (0x1000, 0x1002, 0x1004, 0x1006)],
                         [0x10, 0x11, 0x12, 0])
        self.assertEqual(self.half(ram, 0x1010), 5)
        # The first pending repeat wins; one with no write after it still
        # expands onto address 0 with the last write's store.
        ram = self.run_text("$50000202 0001\n$50000402 0001\n$80001000 0010\n"
                            "$30001100 0001\n$50000304 0003\n")
        self.assertEqual([self.half(ram, a) for a in (0x1000, 0x1002, 0x1004)], [0x10, 0x11, 0])
        self.assertEqual((ram[4], ram[8]), (3, 6))

    def test_repeat_copies_popstarters_bugs(self):
        # Crossing a 64 KB boundary: every later write lands 64 KB further up.
        ram = self.run_text("$50000604 0001\n$8007FFF8 0010\n")
        self.assertEqual([self.half(ram, a) for a in (0x7FFF8, 0x7FFFC, 0x80000)],
                         [0x10, 0x11, 0x12])
        self.assertEqual([self.half(ram, a) for a in (0x90004, 0xA0008, 0xB000C)],
                         [0x13, 0x14, 0x15])
        self.assertEqual(self.half(ram, 0x80004), 0)
        # Values: 0x10000..0x1FFFF wrap; from 0x20000 the store repeats the
        # last value that still fitted.
        ram = self.run_text("$50000402 8000\n$80001000 F000\n")
        self.assertEqual([self.half(ram, 0x1000 + 2 * k) for k in range(4)],
                         [0xF000, 0x7000, 0xF000, 0xF000])

    def test_other_gameshark_types_are_skipped(self):
        text = "$D1002000 0005\n$10001000 0001\n$20001002 0002\n$E0002000 0000\n$80001004 0003\n"
        ram = self.run_text(text)
        self.assertEqual(ram[0x1000:0x1004], bytes(4))
        self.assertEqual(self.half(ram, 0x1004), 3)

    def test_conditional(self):
        text = "$D0002000 0005\n$80001000 0001\n$80001002 0002\n"
        ram = self.run_text(text, [(0x2000, 5)])
        self.assertEqual((self.half(ram, 0x1000), self.half(ram, 0x1002)), (1, 2))
        ram = self.run_text(text, [(0x2000, 6)])
        self.assertEqual((self.half(ram, 0x1000), self.half(ram, 0x1002)), (0, 2))
        # A second conditional right after the first is dropped.
        text = "$D0002000 0005\n$D0002002 0009\n$80001000 0001\n"
        self.assertEqual(self.half(self.run_text(text, [(0x2000, 5)]), 0x1000), 1)
        # Values of 0x8000 and up compare correctly.
        text = "$D0002000 8005\n$80001000 0001\n"
        self.assertEqual(self.half(self.run_text(text, [(0x2000, 0x8005)]), 0x1000), 1)

    def test_conditional_repeat_block_drops_the_next_code(self):
        text = "$D0002000 0005\n$50000202 0001\n$80001000 0010\n$80001010 0001\n$80001020 0002\n"
        ram = self.run_text(text, [(0x2000, 5)])
        self.assertEqual([self.half(ram, a) for a in (0x1000, 0x1002, 0x1010, 0x1020)],
                         [0x10, 0x11, 0, 2])
        ram = self.run_text(text, [(0x2000, 6)])
        self.assertEqual([self.half(ram, a) for a in (0x1000, 0x1010, 0x1020)], [0, 0, 2])

    def test_skipped_repeat_returns_behind_a_conditional(self):
        text = ("$50000204 0002\n$50000402 0001\n$80001100 3A2A\n"
                "$D0002000 0005\n$80001000 0001\n")
        ram = self.run_text(text, [(0x2000, 5)])
        self.assertEqual((self.half(ram, 0x1100), self.half(ram, 0x1104)), (0x3A2A, 0x3A2C))
        self.assertEqual([self.half(ram, a) for a in (0x1000, 0x1002, 0x1004, 0x1006)],
                         [1, 2, 3, 4])

    @unittest.skipUnless(os.environ.get("POPSTARTER_TEST_ELF"), "optional external POPStarter MAIN")
    def test_random_files_match_the_original(self):
        try:
            import unicorn  # noqa: F401
        except ImportError:
            self.skipTest("needs the unicorn package")
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from trace_original_pops_cheats import compile_cheats, run_codes
        rng = random.Random(0x5C0DE)
        for _ in range(int(os.environ.get("POPS_CHEAT_FUZZ_CASES", "150"))):
            text, ram = random_cheats_txt(rng)
            code, _ = compile_cheats(text)
            if original_reads_unknown_registers(code):
                continue
            want = run_codes(code, ram)
            got, rc = apply_cheats_txt(text, ram)
            self.assertEqual(rc, 0, text)
            if got != want:
                first = next(a for a in range(len(ram)) if got[a] != want[a])
                self.fail("%r differs from POPStarter at %#x" % (text, first))

    @unittest.skipUnless(os.environ.get("POPSTARTER_TEST_ELF"), "optional external POPStarter MAIN")
    def test_random_ps2_format_files_match_the_original(self):
        try:
            import unicorn  # noqa: F401
        except ImportError:
            self.skipTest("needs the unicorn package")
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from trace_original_pops_cheats import compile_cheats, run_codes_mem
        rng = random.Random(0x95C0DE)
        names = ("EE RAM", "scratchpad", "0x5F800000 page")
        for _ in range(int(os.environ.get("POPS_CHEAT_FUZZ_CASES", "150"))):
            text, mem = random_cheats_txt(rng, ps2=True)
            code, _ = compile_cheats(text)
            if original_reads_unknown_registers(code):
                continue
            want = run_codes_mem(code, *mem)
            got, rc = apply_cheats_txt_mem(text, *mem)
            self.assertEqual(rc, 0, text)
            for name, g, w in zip(names, got, want):
                if g != w:
                    first = next(a for a in range(len(w)) if g[a] != w[a])
                    self.fail("%r differs from POPStarter in %s at %#x (got %02x, want %02x)"
                              % (text, name, first, g[first], w[first]))


def original_reads_unknown_registers(code):
    """POPStarter builds a repeat's values into "ori k1,zero,value" words.
    From 0x20000 up the excess changes the register fields; launcHER copies
    the RAM effect of that (the store repeats k1's last value). From 0x60000
    up the source register is no longer zero, so the result depends on CPU
    registers this harness does not model; those files are left out."""
    for (word,) in struct.iter_unpack("<I", code):
        if word >> 26 == 0x0D and (word >> 21) & 31:
            return True
    return False


CHEAT_WINDOWS = (0x097B00, 0x07FFE0, 0x1FFF80)
CHEAT_JUNK = ("# comment", "; note", "$NOBOOT", "", "   ", "$8009ZB00 12G4",
              "$80297B00 1234", "$C1097B00 1234", "$85097B00 1234",
              "$80097B00  1234", "$80097B00\t1234", "$80097B00 12345",
              "80097B00 1234", "$50010202 0001", "$10097B00 1234",
              "$20097B01 0012", "$D1097B00 1234", "$E0097B00 0012")


def random_cheat(rng, ram, win):
    kind = rng.choice(["80", "80", "30", "30", "D0", "D0", "C0", "50", "50"])
    if kind == "50":
        inc = rng.randrange(0x10000) if rng.random() < 0.2 else rng.randrange(4)
        times = rng.randrange(5) if rng.random() < 0.85 else rng.randrange(5, 0x30)
        return "$5000%02X%02X %04X" % (times, rng.choice([0, 2, 4, 6]), inc)
    # 16-bit codes stay aligned: POPStarter's sh/lh would fault on the console.
    addr = win + rng.randrange(0, 0x40, 1 if kind == "30" else 2)
    val = ram[addr] | ram[addr + 1] << 8 if rng.random() < 0.5 else rng.randrange(0x10000)
    if kind == "30" and rng.random() < 0.8:
        val &= 0xFF
    return "$%s%06X %04X" % (kind, addr, val)


# PS2-format codes reach EE RAM directly. These windows sit in PS1 RAM (as
# EE 0x01000000 + address, so they meet the PS1 codes) and in plain EE RAM,
# away from where the original's emitted code runs (0x01a00000).
PS2_EE_WINDOWS = (0x00100000, 0x01097B00, 0x0107FFE0)
PS2_JUNK = ("$01097B00 1234567", "$31097B00 12345678", "$S3000000 12345678",
            "$S0004000 12345678", "$T0001400 12345678", "$T0010000 12345678",
            "$=2097B00 12345678", "$S0030000 12345678", "$01097B00 12345678 x")


def random_ps2_cheat(rng, mem, wins):
    """One PS2-format line: $0/$1/$2 EE writes, $S/$T scratchpad writes and
    conditionals, $=/$! word compares. Kept aligned, as an unaligned access
    faults in the original."""
    ee, spr, ps1spr = mem
    kind = rng.choice(["W", "W", "S", "S", "T", "T", "=", "!"])
    size = rng.randrange(3)
    if kind in "=!":
        size = 2
    n = 1 << size
    if kind in "W=!":
        win = rng.choice(wins)
        addr = win + rng.randrange(0, 0x40, n)
        cur = int.from_bytes(ee[addr:addr + n], "little")
    elif kind == "S":
        addr = rng.choice((0, 0x3FC0)) + rng.randrange(0, 0x40, n)
        cur = int.from_bytes(spr[addr:addr + n], "little")
    else:
        addr = rng.choice((0, 0x3C0)) + rng.randrange(0, 0x40, n)
        cur = int.from_bytes(ps1spr[addr:addr + n], "little")
    r = rng.random()
    if r < 0.4:
        val = cur  # often true when compared
        if rng.random() < 0.5 and cur >> (8 * n - 1):
            val |= (0xFFFFFFFF << (8 * n)) & 0xFFFFFFFF  # sign-extended form
    elif r < 0.6:
        val = rng.randrange(1 << (8 * n))
    else:
        val = rng.randrange(1 << 32)
    if kind == "W":
        return "$%d%07X %08X" % (size, addr, val)
    if kind in "=!":
        return "$%s%07X %08X" % (kind, addr, val)
    cond = rng.choice((0, 0, 1, 2))
    if kind == "S":
        return "$S%d%d0%04X %08X" % (size, cond, addr, val)
    return "$T%d%d00%03X %08X" % (size, cond, addr, val)


def random_cheats_txt(rng, ps2=False):
    ram = bytearray(0x200000)
    win = rng.choice(CHEAT_WINDOWS)
    for i in range(0x80):
        ram[win + i] = rng.randrange(256)
    if ps2:
        ee = bytearray(EE_SIZE)
        spr, ps1spr = bytearray(0x4000), bytearray(0x1000)
        wins = (PS2_EE_WINDOWS[0], EE_PS1 + win)
        for i in range(0x80):
            ee[wins[0] + i] = rng.randrange(256)
            spr[i] = rng.randrange(256)
            spr[0x3F80 + i] = rng.randrange(256)
            ps1spr[i] = rng.randrange(256)
            ps1spr[0x380 + i] = rng.randrange(256)
        ee[EE_PS1:EE_PS1 + len(ram)] = ram
        mem = (ee, spr, ps1spr)
    lines = []
    for _ in range(rng.randrange(1, 11)):
        r = rng.random()
        if r < 0.12:
            lines.append(rng.choice(CHEAT_JUNK + (PS2_JUNK if ps2 else ())))
            continue
        if ps2 and rng.random() < 0.5:
            line = random_ps2_cheat(rng, mem, wins)
        else:
            line = random_cheat(rng, ram, win)
        if r < 0.2:
            line = line.lower()
        elif r < 0.26:
            line = "# " + line
        elif r < 0.32:
            line += random_cheat(rng, ram, win)
        elif r < 0.36:
            line += " trailing"
        lines.append(line)
    eol = "\r\n" if rng.random() < 0.3 else "\n"
    text = eol.join(lines) + (eol if rng.random() < 0.8 else "")
    if ps2:
        return text, tuple(bytes(m) for m in mem)
    return text, bytes(ram)


class BuildConfig(unittest.TestCase):
    def parsed(self, *lines):
        buf = (c.c_uint8 * 0x10000)()
        L.pops_config_init(c.addressof(buf))
        for line in lines:
            self.assertEqual(L.pops_config_parse_line(c.addressof(buf), line.encode()), 0, line)
        return buf

    def test_no_cheats_no_resident(self):
        out = ResidentConfig()
        # Hold the parsed buffer: c.addressof() keeps no reference to it.
        cfg = self.parsed()
        self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 0)

    def test_recompiler_addons_set_the_hooks_flags(self):
        # $RECOMPILER_ADDON_0/1/2 are flags the resident recompiler hook reads
        # (bits 11..13); 3 and 4 are jumps written into POPS, no flag.
        for lines, flags in ((["$RECOMPILER_ADDON_0"], 0x0800), (["$RECOMPILER_ADDON_1"], 0x1000),
                             (["$RECOMPILER_ADDON_2"], 0x2000),
                             (["$RECOMPILER_ADDON_0 $RECOMPILER_ADDON_1 $RECOMPILER_ADDON_2"], 0x3800),
                             (["$RECOMPILER_ADDON_3", "$RECOMPILER_ADDON_4"], 0)):
            out = ResidentConfig()
            cfg = self.parsed(*lines)
            self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 1 if flags else 0, lines)
            self.assertEqual(out.flags, flags, lines)

    def test_novmc_sets_the_block_flags(self):
        # $NOVMC0 / $NOVMC1 arm the always-live block's card stores (bits 14
        # and 15); a built-in entry's card 1 off (builtin_no_vmc1) is a core
        # write only, as in the original, and is not read here.
        for lines, flags in ((["$NOVMC0"], NOVMC0), (["$NOVMC1"], NOVMC1),
                             (["$NOVMC1 $NOVMC0"], NOVMC0 | NOVMC1), (["$novmc0"], NOVMC0),
                             (["$NOVMC0X", "$NOVMC2"], 0)):
            out = ResidentConfig()
            cfg = self.parsed(*lines)
            self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)),
                             1 if flags else 0, lines)
            self.assertEqual(out.flags, flags, lines)
        src = (ROOT / "common/src/pops_resident.c").read_text()
        body = src[src.index("int pops_resident_build_config("):]
        body = body[:body.index("\n}\n")]
        code = "".join(part.split("*/", 1)[-1] for part in body.split("/*"))
        self.assertIn("cfg->no_vmc0", code)
        self.assertNotIn("builtin_no_vmc1", code)

    def test_cheats_and_safe_mode(self):
        out = ResidentConfig()
        cfg = self.parsed("$80012345 00FF", "$D0001000 0001", "$30001001 0002", "$SAFEMODE")
        self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 1)
        self.assertEqual(out.flags, 1)
        # The $D0 compiles to a load and a branch in front of the write it gates.
        self.assertEqual(out.cheat_count, 4)
        self.assertEqual([out.cheats[i].type for i in range(4)], [0x80, 0x02, 0x01, 0x30])
        self.assertEqual((out.cheats[0].type, out.cheats[0].address, out.cheats[0].value),
                         (0x80, 0x012345, 0xFF))
        self.assertEqual(out.safe_mode, 1)
        self.assertEqual(out.pops_vblank, 0x0021CD68)
        self.assertEqual(out.ram_base_ptr, 0x70003364)

    def test_safe_mode_commands(self):
        for lines, want in ((["$SAFEMODE2"], 2), (["$SAFEMODE $SAFEMODE2"], 3),
                            (["$SAFEMODE", "$NOSAFEMODE"], 0), (["$NOSAFEMODE $SAFEMODE2"], 2),
                            (["$SAFEMODE2X", "$XSAFEMODE"], 0)):
            out = ResidentConfig()
            cfg = self.parsed("$30001001 0002", *lines)
            L.pops_resident_build_config(c.byref(out), c.addressof(cfg))
            self.assertEqual(out.safe_mode, want, lines)

    def test_display_without_cheats_and_combined(self):
        out = ResidentConfig()
        manual = '$DX_10 $DY_20 $MAGH_3 $MAGV_1 $DW_100 $DH_200'
        cfg = self.parsed(manual)
        self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 1)
        self.assertEqual(out.flags, 2)
        self.assertEqual(out.gs_display, (199 << 44) | (99 << 32) | (1 << 27) | (3 << 23) | (20 << 12) | 10)
        self.assertEqual(out.cheat_count, 0)
        cfg = self.parsed(manual, '$30000010 0001')
        self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 1)
        self.assertEqual((out.flags, out.cheat_count), (3, 1))
        cfg = self.parsed('$480p', manual)
        self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 1)
        self.assertEqual(out.flags, 6)
        cfg = self.parsed('$480p $NOPAL $FORCEPAL')
        self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 1)
        self.assertEqual(out.flags, 4)


def core_with(lui=LUI_PRISTINE, addiu=ADDIU_PRISTINE, size=0x1C000):
    core = bytearray(size)
    struct.pack_into("<I", core, LUI - CORE, lui)
    struct.pack_into("<I", core, ADDIU - CORE, addiu)
    return core


class HookCore(unittest.TestCase):
    def hook(self, core, entry, size=None):
        buf = (c.c_uint8 * len(core)).from_buffer(core)
        return L.pops_resident_hook_core(buf, len(core) if size is None else size, entry)

    def words(self, core):
        return struct.unpack_from("<I", core, LUI - CORE)[0], struct.unpack_from("<I", core, ADDIU - CORE)[0]

    def test_patches_both_words(self):
        core = core_with()
        self.assertEqual(self.hook(core, 0x0143A208), 0)
        self.assertEqual(self.words(core), (0x3C050144, 0x24A5A208))
        # lui/addiu sign carry: a low half below 0x8000 needs no carry.
        core = core_with()
        self.assertEqual(self.hook(core, 0x01447F00), 0)
        self.assertEqual(self.words(core), (0x3C050144, 0x24A57F00))
        self.assertEqual(self.hook(core, 0x01447F00), 0)  # idempotent

    def test_refuses_unknown_core_untouched(self):
        core = core_with(addiu=0x24A5CD6C)
        before = bytes(core)
        self.assertEqual(self.hook(core, 0x0143A208), -errno.EILSEQ)
        self.assertEqual(bytes(core), before)

    def test_bounds(self):
        core = core_with()
        self.assertEqual(self.hook(core, 0x0143A208, size=ADDIU - CORE + 3), -errno.ERANGE)
        self.assertEqual(self.hook(core, 0x0143A20A), -errno.EINVAL)
        self.assertEqual(self.hook(core, LIMIT), -errno.EINVAL)
        self.assertEqual(self.hook(core, 0x00200000), -errno.EINVAL)


# POPS's GP1 write path around the hook (0x21a630..0x21a64c, pinned core).
GP1_SITES = {0x21A630: 0x5060000B, 0x21A638: 0x3C030001, 0x21A63C: 0,
             0x21A640: 0x42000039, 0x21A644: 0x0000040F, 0x21A648: 0x40026000,
             0x21A64C: 0x00431024}


def gp1_core(**changes):
    core = bytearray(0x1C000)
    words = dict(GP1_SITES)
    words.update({int(k[1:], 16): v for k, v in changes.items()})
    for addr, word in words.items():
        struct.pack_into("<I", core, addr - CORE, word)
    return core


class HookGp1(unittest.TestCase):
    def hook(self, core, entry, size=None):
        buf = (c.c_uint8 * len(core)).from_buffer(core)
        return L.pops_resident_hook_gp1(buf, len(core) if size is None else size, entry)

    def site(self, core):
        return struct.unpack_from("<I", core, 0x21A63C - CORE)[0]

    def test_writes_a_jal_over_the_nop(self):
        core = gp1_core()
        self.assertEqual(self.hook(core, 0x0143A208), 0)
        self.assertEqual(self.site(core), 0x0C000000 | (0x0143A208 >> 2))
        self.assertEqual(self.hook(core, 0x0143A208), 0)  # idempotent
        # Same encoding as POPStarter's own hook word, jal 0x239490.
        core = gp1_core()
        self.assertEqual(self.hook(core, 0x0143A000), 0)
        self.assertEqual(0x0C000000 | (0x239490 >> 2), 0x0C08E524)

    def test_refuses_anything_else_untouched(self):
        for addr in GP1_SITES:
            core = gp1_core(**{"x%X" % addr: GP1_SITES[addr] ^ 0x10})
            before = bytes(core)
            self.assertEqual(self.hook(core, 0x0143A208), -errno.EILSEQ, hex(addr))
            self.assertEqual(bytes(core), before)
        # Another jal there already (POPStarter's, say) is not ours to replace.
        core = gp1_core(x21A63C=0x0C08E524)
        self.assertEqual(self.hook(core, 0x0143A208), -errno.EILSEQ)

    def test_bounds(self):
        core = gp1_core()
        self.assertEqual(self.hook(core, 0x0143A208, size=0x21A64C - CORE), -errno.ERANGE)
        self.assertEqual(self.hook(core, 0x0143A20A), -errno.EINVAL)
        self.assertEqual(self.hook(core, LIMIT), -errno.EINVAL)
        self.assertEqual(self.hook(core, 0x00200000), -errno.EINVAL)

    def test_real_core_has_the_pristine_site(self):
        path = os.environ.get("POPS_TEST_ELF")
        if not path or not Path(path).is_file():
            self.skipTest("POPS_TEST_ELF not set")
        data = Path(path).read_bytes()
        for addr, word in GP1_SITES.items():
            self.assertEqual(struct.unpack_from("<I", data, 0x1000 + addr - 0x200000)[0], word, hex(addr))


def image(file_size=0xC0, image_size=0x2000, entry=BASE + 0x70, config=BASE + 0xC0, magic=0x5352484C):
    img = bytearray(file_size)
    struct.pack_into("<IHHIIIIIIIIIIII9II4I", img, 0, magic, 15, 112, file_size, image_size, entry, config,
                     BASE + 0x74, BASE + 0x78, BASE + 0x7C, BASE + 0x80, BASE + 0x84, BASE + 0x88,
                     BASE + 0x8C, BASE + 0x70, *[BASE + 0x90 + 4 * i for i in range(9)],
                     BASE + 0xB4, BASE + 0xB8, BASE + 0xBC, BASE + 0x70, BASE + 0x74)
    img[0x70:0x74] = b"\x08\x00\xe0\x03"
    return img


class Install(unittest.TestCase):
    def check(self, img):
        buf = (c.c_uint8 * len(img)).from_buffer(img)
        h = Header()
        return L.pops_resident_check_image(buf, len(img), c.byref(h)), h

    def test_valid_image(self):
        res, h = self.check(image())
        self.assertEqual(res, 0)
        self.assertEqual((h.file_size, h.image_size, h.vblank_entry), (0xC0, 0x2000, BASE + 0x70))
        self.assertEqual(list(h.guard_entry), [BASE + 0x90 + 4 * i for i in range(9)])
        self.assertEqual((h.recompiler_entry, list(h.recompiler_emit)),
                         (BASE + 0xB4, [BASE + 0xB8, BASE + 0xBC, BASE + 0x70, BASE + 0x74]))

    def test_rejects_bad_images(self):
        self.assertEqual(self.check(image(magic=0))[0], -errno.EINVAL)
        self.assertEqual(self.check(image(image_size=0xB0))[0], -errno.ERANGE)
        self.assertEqual(self.check(image(image_size=LIMIT - BASE + 4))[0], -errno.ERANGE)
        self.assertEqual(self.check(image(entry=BASE + 0xC0))[0], -errno.ERANGE)
        self.assertEqual(self.check(image(entry=BASE + 0x72))[0], -errno.ERANGE)
        self.assertEqual(self.check(image(entry=BASE + 0x10))[0], -errno.ERANGE)
        self.assertEqual(self.check(image(config=BASE + 0x2000 - 8))[0], -errno.ERANGE)
        self.assertEqual(self.check(image(config=BASE + 0xC4))[0], -errno.ERANGE)
        # 16-byte aligned: POPS DMAs the disc names straight from the slots.
        self.assertEqual(self.check(image(config=BASE + 0xC8))[0], -errno.ERANGE)
        # Every entry, the nine guard stubs and the recompiler code included,
        # must be code in the image (after the header).
        for offset in range(24, 112, 4):
            for bad in (BASE + len(img_ok := image()), BASE + 0x6C, BASE + 0x72):
                img = image()
                struct.pack_into('<I', img, offset, bad)
                self.assertEqual(self.check(img)[0], -errno.ERANGE, (offset, hex(bad)))
            self.assertEqual(self.check(img_ok)[0], 0)
        for version in (13, 14, 16):
            img = image()
            struct.pack_into('<H', img, 4, version)
            self.assertEqual(self.check(img)[0], -errno.EINVAL, version)
        img = image()
        struct.pack_into('<H', img, 6, 56)
        self.assertEqual(self.check(img)[0], -errno.EINVAL)
        img = image()
        buf = (c.c_uint8 * len(img)).from_buffer(img)
        self.assertEqual(L.pops_resident_check_image(buf, len(img) - 4, None), -errno.ERANGE)

    def test_install_copies_zeroes_and_configures(self):
        img = image()
        dest = (c.c_uint8 * 0x3000)(*([0xCC] * 0x3000))
        cfg = ResidentConfig()
        cfg.flags, cfg.cheat_count = 1, 1
        cfg.cheats[0].address, cfg.cheats[0].type, cfg.cheats[0].value = 0x10, 0x30, 0x7F
        buf = (c.c_uint8 * len(img)).from_buffer(img)
        self.assertEqual(L.pops_resident_install(dest, 0x3000, BASE, buf, len(img), c.byref(cfg)), 0)
        raw = bytes(dest)
        self.assertEqual(raw[:0xC0], bytes(img))
        got = ResidentConfig.from_buffer_copy(raw[0xC0:0xC0 + c.sizeof(ResidentConfig)])
        self.assertEqual((got.flags, got.cheat_count, got.cheats[0].value), (1, 1, 0x7F))
        end = 0xC0 + c.sizeof(ResidentConfig)
        self.assertEqual(raw[end:0x2000], bytes(0x2000 - end))
        self.assertEqual(raw[0x2000:], b"\xcc" * (0x3000 - 0x2000))

    def test_install_refuses_short_destination_or_wrong_base(self):
        img = image()
        buf = (c.c_uint8 * len(img)).from_buffer(img)
        dest = (c.c_uint8 * 0x1FFF)()
        cfg = ResidentConfig()
        self.assertEqual(L.pops_resident_install(dest, 0x1FFF, BASE, buf, len(img), c.byref(cfg)), -errno.ERANGE)
        self.assertEqual(bytes(dest), bytes(0x1FFF))
        dest = (c.c_uint8 * 0x3000)()
        self.assertEqual(L.pops_resident_install(dest, 0x3000, BASE + 0x10, buf, len(img), c.byref(cfg)),
                         -errno.EINVAL)


PAD_STATE_SITES = {0x20C648: 0x3C070050, 0x20C64C: 0x24E77000, 0x20C6C8: 0x8CE80034}
PAD_READ_SITES = {0x237798: 0x0080382D, 0x23779C: 0x24030070, 0x2377A0: 0x2404001C,
                  0x23780C: 0x03E00008, 0x237810: 0x27BD0030}
F_PAD_ID, F_D2LS = 1 << 3, 1 << 4


class PadCommands(unittest.TestCase):
    def parsed(self, *lines):
        return BuildConfig.parsed(self, *lines)

    def resident(self, *lines):
        out = ResidentConfig()
        # Hold the parsed buffer: c.addressof() keeps no reference to it, so a
        # temporary is freed before the C function reads it.
        cfg = self.parsed(*lines)
        res = L.pops_resident_build_config(c.byref(out), c.addressof(cfg))
        return res, out

    def test_nopad_and_pad_id(self):
        res, out = self.resident("$NOPAD1")
        self.assertEqual((res, out.flags, out.pad_override, out.pad_id[1]), (1, F_PAD_ID, 2, 1))
        res, out = self.resident("$NOPAD0 $PAD1ID_0X73")
        self.assertEqual((out.pad_override, list(out.pad_id)), (3, [1, 0x73]))
        res, out = self.resident("$NOPAD0", "$PAD0ID_0X5A")  # later command wins
        self.assertEqual((out.pad_override, list(out.pad_id)), (1, [0x5A, 0]))

    def test_malformed_pad_id_is_ignored(self):
        for token in ("$PAD0ID_0X7", "$PAD0ID_0X733", "$PAD0ID_0XG1", "$PAD2ID_0X41", "$NOPAD2"):
            res, out = self.resident(token)
            self.assertEqual((res, out.flags), (0, 0), token)

    def test_d2ls_forces_digital_and_swaps(self):
        res, out = self.resident("$D2LS")
        self.assertEqual((out.flags, out.pad_override, list(out.pad_id)), (F_PAD_ID | F_D2LS, 3, [0x41, 0x41]))

    def test_d2ls_alt_follows_the_original_order(self):
        # Alone: swap only, the real controller ID stays.
        res, out = self.resident("$D2LS_ALT")
        self.assertEqual((out.flags, out.pad_override), (F_D2LS, 0))
        # After $D2LS: the overrides are switched off again.
        res, out = self.resident("$D2LS", "$D2LS_ALT")
        self.assertEqual((out.flags, out.pad_override), (F_D2LS, 0))
        # After $NOPAD0 without $D2LS: the override stays and now reports 0x41.
        res, out = self.resident("$NOPAD0", "$D2LS_ALT")
        self.assertEqual((out.flags, out.pad_override, out.pad_id[0]), (F_PAD_ID | F_D2LS, 1, 0x41))

    def test_pad_ids_write_only_the_selected_ports(self):
        state = (c.c_uint8 * 0x120)(*([0xEE] * 0x120))
        cfg = ResidentConfig()
        cfg.pad_override, cfg.pad_id[0], cfg.pad_id[1] = 2, 0x41, 0x73
        L.pops_resident_pad_ids(c.byref(cfg), state)
        self.assertEqual((state[0x34], state[0x90 + 0x34]), (0xEE, 0x73))
        self.assertEqual(sum(1 for b in state if b != 0xEE), 1)

    def d2ls(self, buttons, lx, ly, right=0, left=0, up=0, down=0, n=20):
        pad = (c.c_uint8 * 20)(0, 0x79, buttons & 0xFF, buttons >> 8, 0x80, 0x80, lx, ly,
                               right, left, up, down)
        L.pops_resident_d2ls(pad, n)
        return list(pad)

    def test_d2ls_stick_drives_the_dpad(self):
        pad = self.d2ls(0xFFFF, 0x80, 0x80)
        self.assertEqual(pad[2:4], [0xFF, 0xFF])  # centred: released
        self.assertEqual(pad[8:12], [0, 0, 0, 0])
        pad = self.d2ls(0xFF0F, 0x80, 0x80)       # real D-pad is replaced
        self.assertEqual(pad[2], 0xFF)
        pad = self.d2ls(0xFFFF, 0x00, 0x00)       # full up-left
        self.assertEqual(pad[2], 0xFF & ~0x10 & ~0x80)
        self.assertEqual(pad[8:12], [0, 0xFE, 0xFE, 0])
        pad = self.d2ls(0xFFFF, 0xFF, 0xFF)       # full down-right
        self.assertEqual(pad[2], 0xFF & ~0x20 & ~0x40)
        self.assertEqual(pad[8:12], [0xFE, 0, 0, 0xFE])
        # Thresholds: a quarter of the travel either way.
        self.assertEqual(self.d2ls(0xFFFF, 0x41, 0x40)[2], 0xFF & ~0x10)
        self.assertEqual(self.d2ls(0xFFFF, 0xBE, 0xBF)[2], 0xFF & ~0x40)
        # Other buttons are untouched.
        self.assertEqual(self.d2ls(0x1234 | 0xF0, 0x80, 0x80)[2:4], [0x34 | 0xF0, 0x12])

    def test_d2ls_dpad_pressure_drives_the_stick(self):
        pad = self.d2ls(0xFFFF, 0x80, 0x80, up=0xFF, left=0x80)
        self.assertEqual((pad[6], pad[7]), (0x7F - 0x40, 0x00))
        pad = self.d2ls(0xFFFF, 0x80, 0x80, up=0xFF, down=0xFF, right=0x02)
        self.assertEqual((pad[6], pad[7]), (0x81, 0xFF))  # down/right win over up/left
        pad = self.d2ls(0xFFFF, 0x10, 0x10)
        self.assertEqual((pad[6], pad[7]), (0x80, 0x80))  # D-pad released: centred

    def test_d2ls_short_readings(self):
        pad = self.d2ls(0xFF0F, 0x00, 0x00, n=4)    # digital mode: untouched
        self.assertEqual(pad[2], 0x0F)
        self.assertEqual(pad[6:8], [0, 0])
        pad = self.d2ls(0xFFFF, 0x00, 0x80, up=0xFF, n=8)  # no pressure data
        self.assertEqual(pad[2], 0xFF & ~0x80)
        self.assertEqual((pad[6], pad[7]), (0x80, 0x80))

    def core(self):
        core = bytearray(0x40000)
        for a, v in {**PAD_STATE_SITES, **PAD_READ_SITES}.items():
            struct.pack_into("<I", core, a - CORE, v)
        return core

    def hook(self, core, flags, entry=BASE + 0x80, ret=BASE + 0x90, size=None):
        buf = (c.c_uint8 * len(core)).from_buffer(core)
        return L.pops_resident_hook_pads(buf, len(core) if size is None else size, flags, entry, ret)

    def test_hook_pads(self):
        core = self.core()
        before = bytes(core)
        self.assertEqual(self.hook(core, F_PAD_ID), 0)
        self.assertEqual(bytes(core), before)  # ID override needs no core write
        self.assertEqual(self.hook(core, F_PAD_ID | F_D2LS), 0)
        self.assertEqual(struct.unpack_from("<I", core, 0x23779C - CORE)[0], 0x08000000 | ((BASE + 0x80) >> 2))
        self.assertEqual(struct.unpack_from("<I", core, 0x23780C - CORE)[0], 0x08000000 | ((BASE + 0x90) >> 2))
        self.assertEqual(self.hook(core, F_D2LS), 0)  # idempotent

    def test_hook_pads_refuses_unknown_core_untouched(self):
        for site in list(PAD_STATE_SITES) + list(PAD_READ_SITES):
            core = self.core()
            struct.pack_into("<I", core, site - CORE, 0)
            before = bytes(core)
            self.assertEqual(self.hook(core, F_D2LS), -errno.EILSEQ, hex(site))
            self.assertEqual(bytes(core), before)
        core = self.core()
        self.assertEqual(self.hook(core, F_D2LS, entry=BASE + 0x82), -errno.EINVAL)
        self.assertEqual(self.hook(core, F_D2LS, ret=LIMIT), -errno.EINVAL)
        self.assertEqual(self.hook(core, F_D2LS, size=0x237810 - CORE), -errno.ERANGE)
        self.assertEqual(self.hook(core, 0, size=16), 0)  # no pad command: nothing checked

    def load_external_core(self):
        import hashlib
        elf = Path(os.environ["POPS_TEST_ELF"]).read_bytes()
        self.assertEqual(hashlib.sha256(elf).hexdigest(),
                         "59df3389c4df88a572daa720b05507c52c34eddfa0031a6fbeec55e0c2d0fcb1")
        core = bytearray(0x302E60)
        at = struct.unpack_from("<I", elf, 28)[0]
        ents, count = struct.unpack_from("<HH", elf, 42)
        for i in range(count):
            kind, off, va, _, fs, _, _, _ = struct.unpack_from("<8I", elf, at + i * ents)
            if kind == 1 and CORE <= va and va + fs <= CORE + len(core):
                core[va - CORE:va - CORE + fs] = elf[off:off + fs]
        return core

    @unittest.skipUnless(os.environ.get("POPS_TEST_ELF"), "optional external Sony core")
    def test_identified_external_core(self):
        core = self.load_external_core()
        for a, v in {**PAD_STATE_SITES, **PAD_READ_SITES}.items():
            self.assertEqual(struct.unpack_from("<I", core, a - CORE)[0], v, hex(a))
        self.assertEqual(self.hook(core, F_PAD_ID | F_D2LS), 0)

    def test_launcher_hooks_gp1_for_pad_ids(self):
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        assert_gp1_hook_always(self, src)
        self.assertNotIn("pops_resident_hook_core(", src)
        self.assertLess(src.index("pops_resident_hook_pads("), src.index("SifIopRebootBuffer("))


# Original pad command handlers and the bytes they patch in the code the
# original copies into POPS: per port, a branch whose offset byte is 1 when
# the ID override runs (6 skips it) and the immediate of the ID it stores.
PAD_WINDOWS = {"$NOPAD0": (0x8968D8, 0x896A98), "$NOPAD1": (0x896A98, 0x896C58),
               "$D2LS_ALT": (0x896E30, 0x8970B4), "$D2LS": (0x896C58, 0x896E30),
               "$PAD": (0x897CBC, 0x8982BC)}
PAD_BRANCH, PAD_IMMEDIATE = (0x232CB0, 0x232CCC), (0x232CBC, 0x232CD4)
PAD_SWAP_SITE, PAD_SWAP_JUMP = 0x23779C, 0x0808C7B4


class OriginalPadCommands(unittest.TestCase):
    """Runs the original's own pad command handlers (external MAIN only) and
    compares the state they leave with launcHER's parsed configuration."""

    @unittest.skipUnless(os.environ.get("POPSTARTER_TEST_ELF"), "optional external POPStarter MAIN")
    def test_sequences_match_the_original(self):
        from trace_original_pops_display import _Window
        from trace_original_pops_io import decode_main

        image = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())

        class PadWindow(_Window):
            def __init__(self, lo, hi, command, state):
                super().__init__(image, lo, hi, command)
                self.state = state
                self.memory.update((self.GP + 0x28E0 + i, 0) for i in range(4))
                self.store(self.GP + 0x28E0, 0xF4, 4)

            def service(self, target):
                a0, a1, a2 = self.reg[4:7]
                if target == 0x8D6B74:  # read a core word
                    self.put(2, self.state.get(a0 & 0xFFFFFFFF, 0))
                    return
                if target == 0x918808 and a2 == 0xF4:  # the copied swap routine
                    self.writes.append([a0, None, a2])
                    self.put(2, a0)
                    return
                super().service(target)

        def original(commands):
            state = {PAD_BRANCH[0]: 6, PAD_BRANCH[1]: 6, PAD_IMMEDIATE[0]: 1,
                     PAD_IMMEDIATE[1]: 1, PAD_SWAP_SITE: 0x24030070}
            for command in commands:
                prefix = next(p for p in PAD_WINDOWS if command.upper().startswith(p))
                w = PadWindow(*PAD_WINDOWS[prefix], command, state)
                w.run()
                for address, value, width in w.writes:
                    if value is not None and address in state:
                        state[address] = value
            override = sum(1 << n for n in range(2) if state[PAD_BRANCH[n]] == 1)
            ids = [state[PAD_IMMEDIATE[n]] if override >> n & 1 else None for n in range(2)]
            return override, ids, int(state[PAD_SWAP_SITE] == PAD_SWAP_JUMP)

        tokens = ["$NOPAD0", "$NOPAD1", "$D2LS", "$D2LS_ALT", "$PAD0ID_0X73",
                  "$PAD1ID_0X5A", "$PAD0ID_0XF0", "$PAD1ID_0X12", "$PAD0ID_0XG1", "$PAD0ID_0X7"]
        rng = random.Random(0x5041)
        cases = [[t] for t in tokens] + [[a, b] for a in tokens for b in tokens]
        cases += [rng.sample(tokens, 4) for _ in range(200)]
        for commands in cases:
            cfg = BuildConfig.parsed(self, " ".join(commands))
            out = ResidentConfig()
            L.pops_resident_build_config(c.byref(out), c.addressof(cfg))
            ids = [out.pad_id[n] if out.pad_override >> n & 1 else None for n in range(2)]
            mine = (out.pad_override, ids, int(bool(out.flags & F_D2LS)))
            self.assertEqual(mine, original(commands), commands)
        print("Original pad command sequences PASS: %d" % len(cases))


GTE_SITES = {0x2089A8: 0xAC880064, 0x2089AC: 0xAC890068, 0x2089B0: 0xAC8A006C,
             0x2089B8: 0x24028000, 0x2089BC: 0x24037FFF, 0x208A2C: 0xAC880024,
             0x208A30: 0xAC890028, 0x208A34: 0xAC8A002C, 0x208A38: 0x3402FFFF,
             0x208A3C: 0x3C038006}
F_WIDESCREEN = 1 << 5
WIDE_HDR = dict(gte_scale_entry=BASE + 0x100, gte_divide_entry=BASE + 0x118,
                gte_ultra_entry=BASE + 0x140)


def jump(target):
    return 0x08000000 | (target >> 2)


class Widescreen(unittest.TestCase):
    def resident(self, *lines):
        out = ResidentConfig()
        cfg = BuildConfig.parsed(self, *lines)
        return L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), out, cfg

    def test_last_command_wins(self):
        for lines, mode, divisor in ((["$WIDESCREEN"], 1, 100), (["$ULTRA_WIDESCREEN"], 2, 100),
                                     (["$EYEFINITY"], 3, 4), (["$EYEFINITY", "$WIDESCREEN"], 1, 100),
                                     (["$WIDESCREEN $EYEFINITY"], 3, 4)):
            res, out, cfg = self.resident(*lines)
            mode_byte = cfg[7]  # after video_mode, hdtv_fix, x/y offsets, smooth
            self.assertEqual((res, out.flags, out.gte_divisor, mode_byte), (1, F_WIDESCREEN, divisor, mode), lines)

    def core(self):
        core = bytearray(0x10000)
        base = 0x200000 + 0x8000
        for a, v in GTE_SITES.items():
            struct.pack_into("<I", core, a - base, v)
        return core, base

    def hook(self, core, base, mode, **over):
        hdr = Header(**{**WIDE_HDR, **over})
        # The helper takes the staged core base at 0x200000; offset the buffer.
        full = bytearray(0x10000 + (base - 0x200000))
        full[base - 0x200000:] = core
        buf = (c.c_uint8 * len(full)).from_buffer(full)
        res = L.pops_resident_hook_widescreen(buf, len(full), mode, c.byref(hdr))
        core[:] = full[base - 0x200000:]
        return res

    def word(self, core, base, a):
        return struct.unpack_from("<I", core, a - base)[0]

    def test_hook_modes(self):
        core, base = self.core()
        self.assertEqual(self.hook(core, base, 2), 0)  # ULTRA
        self.assertEqual(self.word(core, base, 0x2089A8), jump(BASE + 0x100))
        self.assertEqual(self.word(core, base, 0x208A2C), jump(BASE + 0x140))
        self.assertEqual(self.hook(core, base, 3), 0)  # then EYEFINITY: IR1 store restored
        self.assertEqual(self.word(core, base, 0x2089A8), jump(BASE + 0x118))
        self.assertEqual(self.word(core, base, 0x208A2C), 0xAC880024)
        self.assertEqual(self.hook(core, base, 1), 0)
        self.assertEqual(self.word(core, base, 0x2089A8), jump(BASE + 0x100))
        before = bytes(core)
        self.assertEqual(self.hook(core, base, 0), 0)
        self.assertEqual(bytes(core), before)

    def test_hook_refuses_unknown_core_untouched(self):
        for site in GTE_SITES:
            core, base = self.core()
            struct.pack_into("<I", core, site - base, 0)
            before = bytes(core)
            self.assertEqual(self.hook(core, base, 2), -errno.EILSEQ, hex(site))
            self.assertEqual(bytes(core), before)
        core, base = self.core()
        self.assertEqual(self.hook(core, base, 4), -errno.EINVAL)
        self.assertEqual(self.hook(core, base, 1, gte_ultra_entry=BASE + 2), -errno.EINVAL)

    @unittest.skipUnless(os.environ.get("POPS_TEST_ELF"), "optional external Sony core")
    def test_identified_external_core(self):
        core = PadCommands.load_external_core(self)
        for a, v in GTE_SITES.items():
            self.assertEqual(struct.unpack_from("<I", core, a - CORE)[0], v, hex(a))

    @unittest.skipUnless(os.environ.get("POPSTARTER_TEST_ELF"), "optional external POPStarter MAIN")
    def test_original_handlers(self):
        """The original's handlers rewrite the same sites in full each time,
        which is why the last command wins."""
        from trace_original_pops_display import _Window
        from trace_original_pops_io import decode_main
        image = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())

        class Win(_Window):
            def service(self, target):
                if target == 0x8D6B9C and self.reg[5] == 0x143A6C0:  # resident divisor byte
                    self.writes.append([self.reg[5], self.reg[4] & 0xFF, 1])
                    return
                super().service(target)

        windows = {"$WIDESCREEN": (0x895438, 0x895690), "$ULTRA_WIDESCREEN": (0x895690, 0x8959A8),
                   "$EYEFINITY": (0x8959A8, 0x895BE0)}
        expect = {"$WIDESCREEN": (0x0850E9AE, 0xAC880024, 100),
                  "$ULTRA_WIDESCREEN": (0x0850E9AE, 0x0850E9B8, 100),
                  "$EYEFINITY": (0x0850E9B0, 0xAC880024, 4)}
        for command, window in windows.items():
            w = Win(image, *window, command)
            w.run()
            got = {a: v for a, v, _ in w.writes}
            self.assertEqual((got[0x2089A8], got[0x208A2C], got[0x143A6C0]), expect[command], command)
            self.assertEqual(set(got), {0x2089A8, 0x208A2C, 0x143A6C0}, command)


F_TIMINGS, F_TIMINGS_SAVE = 1 << 6, 1 << 7
VMC0, SAVE, TIMING_A, SPR_B, SPR_C = 0x507930, 0x508130, 0x502770, 0x33E0, 0x33E4
PAD0, PAD1 = 0x507002, 0x507092
L1, L2, R1, R2 = 0xFBFF, 0xFEFF, 0xF7FF, 0xFDFF
TIMING_BLOCK = (0x983890, 0x238A90, 0x270)  # original source VA, core address, size


class _TimingMachine:
    """Fake EE RAM (address 0 up) and scratchpad for pops_resident_timings."""

    def __init__(self):
        self.ee = (c.c_uint8 * 0x509000)()
        self.spr = (c.c_uint8 * 0x4000)()

    def ee32(self, a, v=None):
        if v is not None:
            struct.pack_into("<I", self.ee, a, v & 0xFFFFFFFF)
        return struct.unpack_from("<I", self.ee, a)[0]

    def spr32(self, a, v=None):
        if v is not None:
            struct.pack_into("<I", self.spr, a, v & 0xFFFFFFFF)
        return struct.unpack_from("<I", self.spr, a)[0]

    def pads(self, p0, p1):
        struct.pack_into("<H", self.ee, PAD0, p0)
        struct.pack_into("<H", self.ee, PAD1, p1)

    def timings(self):
        return self.ee32(TIMING_A), self.spr32(SPR_B), self.spr32(SPR_C)

    def copy(self):
        return tuple(self.ee32(SAVE + 4 * i) for i in range(4))

    def run(self, cfg):
        L.pops_resident_timings(c.byref(cfg), c.addressof(self.ee), c.addressof(self.spr))


class _OriginalTimingBlock:
    """Interprets the original's copied $SET_TIMINGS block (k0/k1 only) from
    the external MAIN, with the two words its command handler writes."""

    def __init__(self, image, machine):
        src, self.base, size = TIMING_BLOCK
        off = src - 0x870000
        self.code = {self.base + i: struct.unpack_from("<I", image, off + i)[0] for i in range(0, size, 4)}
        self.code[0x238A90] = 0x1000006F
        self.code[0x238CFC] = 0xAF408A90
        self.m = machine

    def load(self, a, width):
        if a in self.code:
            return self.code[a]
        if a >= 0x70000000:
            buf, a = self.m.spr, a - 0x70000000
        else:
            buf = self.m.ee
        v = struct.unpack_from("<I" if width == 4 else "<H", buf, a)[0]
        return v - 0x10000 if width == 2 and v & 0x8000 else v

    def store(self, a, v):
        v &= 0xFFFFFFFF
        if a in self.code:
            self.code[a] = v
        elif a >= 0x70000000:
            self.m.spr32(a - 0x70000000, v)
        else:
            self.m.ee32(a, v)

    def run(self):
        r = {0: 0, 26: 0, 27: 0}
        pc, steps = self.base, 0
        while pc != 0x238D00:
            steps += 1
            assert steps < 1000 and pc in self.code, hex(pc)
            w = self.code[pc]
            op, rs, rt = w >> 26, w >> 21 & 31, w >> 16 & 31
            imm = w & 0xFFFF
            simm = imm - 0x10000 if imm & 0x8000 else imm
            nxt = pc + 4
            if w == 0:
                pass
            elif op == 0x0F:
                r[rt] = imm << 16
            elif op == 0x09:
                r[rt] = (r[rs] + simm) & 0xFFFFFFFF
            elif op == 0x0D:
                r[rt] = r[rs] | imm
            elif op in (0x21, 0x23):
                r[rt] = self.load((r[rs] + simm) & 0xFFFFFFFF, 2 if op == 0x21 else 4) & 0xFFFFFFFF
            elif op == 0x2B:
                self.store((r[rs] + simm) & 0xFFFFFFFF, r[rt])
            elif op in (4, 5):
                taken = (r[rs] == r[rt]) == (op == 4)
                assert self.code[pc + 4] == 0, "delay slot"
                nxt = pc + 4 + (simm << 2) if taken else pc + 8
            else:
                raise AssertionError("unhandled %08x at %x" % (w, pc))
            r[0] = 0
            pc = nxt


class SetTimings(unittest.TestCase):
    def config(self, flags=F_TIMINGS):
        cfg = ResidentConfig()
        cfg.flags = flags
        return cfg

    def test_parse_and_flag(self):
        out = ResidentConfig()
        cfg = BuildConfig.parsed(self, "$SET_TIMINGS")
        self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 1)
        self.assertEqual(out.flags, F_TIMINGS | F_TIMINGS_SAVE)  # saves like POPStarter
        cfg = BuildConfig.parsed(self, "$set_timings")
        L.pops_resident_build_config(c.byref(out), c.addressof(cfg))
        self.assertEqual(out.flags, F_TIMINGS | F_TIMINGS_SAVE)
        for line in ("$SET_TIMINGS1", "$SET_TIMING"):
            cfg = BuildConfig.parsed(self, line)
            self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 0, line)

    def test_waits_for_the_vmc_image_then_restores(self):
        m, cfg = _TimingMachine(), self.config()
        m.ee32(TIMING_A, 7); m.spr32(SPR_B, 8); m.spr32(SPR_C, 9)
        m.ee32(SAVE, 0x3E2D3130); m.ee32(SAVE + 4, 0x100); m.ee32(SAVE + 8, 0x200); m.ee32(SAVE + 12, 0x300)
        m.pads(L1, L1)
        m.run(cfg)  # no VMC image yet: nothing, not even the adjust
        self.assertEqual((m.timings(), cfg.timings_ready), ((7, 8, 9), 0))
        m.ee32(VMC0, 0x6F53)
        m.run(cfg)  # restore pass, no adjust on it
        self.assertEqual((m.timings(), cfg.timings_ready), ((0x100, 0x200, 0x300), 1))
        m.run(cfg)  # pad 1 wins over pad 2
        self.assertEqual(m.timings(), (0x100, 0x201, 0x300))
        self.assertEqual(m.copy(), (0x3E2D3130, 0x100, 0x200, 0x300))  # card untouched

    def test_never_writes_the_card_without_the_save_flag(self):
        m, cfg = _TimingMachine(), self.config()
        m.ee32(VMC0, 1)
        m.ee32(TIMING_A, 5)
        for pads in [(0xFFFF, 0xFFFF)] + [(p, 0xFFFF) for p in (L1, L2, R1, R2)] + \
                    [(0xFFFF, p) for p in (L1, L2, R1, R2)]:
            m.pads(*pads)
            m.run(cfg)
        self.assertEqual(m.copy(), (0, 0, 0, 0))
        self.assertEqual(m.timings(), (5, 0, 0))  # +1 -1 +0x10 -0x10 on A, +1-1 on B and C

    def test_adjust_needs_exactly_one_button(self):
        m, cfg = _TimingMachine(), self.config()
        m.ee32(VMC0, 1)
        m.run(cfg)
        for p0, p1, want in ((L1 & R1, 0xFFFF, (0, 0, 0)), (0xFFFF, R1, (0x10, 0, 0)),
                             (0xFFFF, R2, (0, 0, 0)), (R1, 0xFFFF, (0, 0, 1)),
                             (L2, 0xFFFF, (0, 0xFFFFFFFF, 1)), (R2, 0xFFFF, (0, 0xFFFFFFFF, 0)),
                             (0xFFFF, L2, (0xFFFFFFFF, 0xFFFFFFFF, 0))):
            m.pads(p0, p1)
            m.run(cfg)
            self.assertEqual(m.timings(), want, (hex(p0), hex(p1)))

    def test_disabled_does_nothing(self):
        m, cfg = _TimingMachine(), self.config(0)
        m.ee32(VMC0, 1); m.ee32(SAVE, 0x3E2D3130); m.ee32(SAVE + 4, 9)
        m.pads(L1, L1)
        m.run(cfg); m.run(cfg)
        self.assertEqual((m.timings(), cfg.timings_ready), ((0, 0, 0), 0))

    def test_launcher_hooks_gp1_for_cheats_and_timings(self):
        # POPStarter runs $SET_TIMINGS and its cheat code from POPS's GP1
        # write path (0x21a63c), not from VBLANK; launcHER does the same.
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        assert_gp1_hook_always(self, src)
        engine = (ROOT / "common/src/pops_resident_engine.c").read_text()
        vblank = engine[engine.index("int pops_resident_vblank(int cause) {"):]
        vblank = vblank[:vblank.index("\n}\n")]
        self.assertNotIn("pops_resident_timings", vblank)
        self.assertNotIn("pops_resident_frame", vblank)
        self.assertNotIn("pops_resident_pad_ids", vblank)

    @unittest.skipUnless(os.environ.get("POPSTARTER_TEST_ELF"), "optional external POPStarter MAIN")
    def test_original_handler_writes(self):
        from trace_original_pops_display import _Window
        from trace_original_pops_io import decode_main
        image = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
        w = _Window(image, 0x895E68, 0x8960D0, "$SET_TIMINGS")
        w.run()
        got = {a: v for a, v, _ in w.writes}
        self.assertEqual(got, {0x238A90: 0x1000006F, 0x238CFC: 0xAF408A90})

    @unittest.skipUnless(os.environ.get("POPSTARTER_TEST_ELF"), "optional external POPStarter MAIN")
    def test_matches_the_original_block(self):
        """Random frames through the original's own block and launcHER's,
        with and without the card-writing flag. The card copy is compared
        only for the flag that writes it."""
        from trace_original_pops_io import decode_main
        image = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
        rng = random.Random(0x5354)
        buttons = [0xFFFF, L1, L2, R1, R2, L1 & R1, 0xFFFE, 0x0000]
        cases = 0
        for case in range(120):
            for flags in (F_TIMINGS | F_TIMINGS_SAVE, F_TIMINGS):
                ours, theirs = _TimingMachine(), _TimingMachine()
                orig = _OriginalTimingBlock(image, theirs)
                cfg = self.config(flags)
                start = [rng.getrandbits(32) for _ in range(3)]
                signed = case % 3 == 0
                for m in (ours, theirs):
                    m.ee32(TIMING_A, start[0]); m.spr32(SPR_B, start[1]); m.spr32(SPR_C, start[2])
                    if signed:
                        m.ee32(SAVE, 0x3E2D3130 if case % 2 else 0x00003130)
                        for i in range(3):
                            m.ee32(SAVE + 4 + 4 * i, start[i] ^ 0x5A5A5A5A)
                ready_at = rng.randrange(0, 4)
                for frame in range(40):
                    pads = (rng.choice(buttons), rng.choice(buttons))
                    for m in (ours, theirs):
                        if frame == ready_at:
                            m.ee32(VMC0, 0x434D)
                        m.pads(*pads)
                    ours.run(cfg)
                    orig.run()
                    self.assertEqual(ours.timings(), theirs.timings(), (case, flags, frame))
                    if flags & F_TIMINGS_SAVE:
                        self.assertEqual(ours.copy(), theirs.copy(), (case, frame))
                    elif not signed:
                        self.assertEqual(ours.copy(), (0, 0, 0, 0))
                cases += 1
        print("Original $SET_TIMINGS block PASS: %d runs x 40 frames" % cases)


class OriginalPresets(unittest.TestCase):
    """POPStarter gates some core patches on bytes of a preset block in its
    own ELF segment (file offset 0x410.., loaded at 0x100000), not on user
    commands. launcHER applies those patches always; that is only right
    while every gating preset is 1."""

    @unittest.skipUnless(os.environ.get("POPSTARTER_TEST_ELF"), "optional external POPStarter ELF")
    def test_gating_presets_are_on(self):
        elf = Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes()
        phoff = struct.unpack_from("<I", elf, 0x1C)[0]
        _, off, vaddr = struct.unpack_from("<III", elf, phoff)
        self.assertEqual((off, vaddr), (0x400, 0x100000))
        # 0x22 exception breakpoints, 0x23 SLBB-00001 bypass, 0x24 IGR exit
        # fix, 0x27 module error checks, 0x28 HddInit exit (0x8710a0..).
        for preset in (0x22, 0x23, 0x24, 0x27, 0x28):
            self.assertEqual(elf[off + preset], 1, hex(0x100000 + preset))


COMBO_EMODE_0, COMBO_EMODE_1, COMBO_LID_OPEN = 0xF6FE, 0xF9FE, 0xECFE
COMBO_SCANLINES_ON, COMBO_SCANLINES_OFF, COMBO_LID_CLOSE = 0xF5FE, 0xFAFE, 0x7CFE
COMBO_DISC = (0xFCEE, 0xFCDE, 0xFCBE, 0xFC7E)
LID_OPEN, LID_CLOSED = 0x1000, 0x0200
SCANLINES_ON, SCANLINES_OFF = 0x22B50006, 0x8CA42158
SLOT = 0x60
# POPS's card state: card 0's word, card 1's POPS_CARD_STATE_STRIDE later.
CARD_STATE, CARD_STRIDE = 0x00507920, 0x20010
NOVMC0, NOVMC1 = 1 << 14, 1 << 15


def disc_slots(*names):
    """Slots as POPStarter's DISCS.TXT reader writes them."""
    out = bytearray(4 * SLOT)
    for n, name in enumerate(names):
        if name is not None:
            out[n * SLOT:n * SLOT + 7 + len(name)] = b"pfs0:/" + name + b"\0"
    return bytes(out)


class _HotkeyMachine:
    """launcHER's pops_resident_hotkeys over host memory standing in for
    POPS's: the two pad state blocks, the emode byte, the lid halfword, the
    $SCANLINES word, main's boot path and the disc init (recorded)."""

    def __init__(self, slots=bytes(4 * SLOT), lid=LID_CLOSED, boot=bytes(SLOT), emode=0x55,
                 scanlines=SCANLINES_OFF, flags=0, cards=(0, 0)):
        self.cfg = ResidentConfig()
        self.cfg.flags = flags
        c.memmove(c.addressof(self.cfg.disc_slot), slots, 4 * SLOT)
        self.pad = (c.c_uint8 * (2 * 0x90))()
        self.emode = c.c_uint8(emode)
        self.lid = c.c_uint16(lid)
        self.scanlines = c.c_uint32(scanlines)
        self.boot = (c.c_uint8 * SLOT).from_buffer_copy(boot)
        self.card = (c.c_uint8 * (CARD_STRIDE + 4))()
        self.set_cards(cards)
        self.calls = []
        self._cd_init = HOTKEY_CD_INIT(self.cd_init)
        self.mem = HotkeyMemory(c.addressof(self.pad), c.addressof(self.emode), c.addressof(self.lid),
                                c.addressof(self.scanlines), c.addressof(self.boot),
                                c.addressof(self.card), self._cd_init)

    def set_cards(self, words):
        for n, word in enumerate(words):
            struct.pack_into("<I", self.card, n * CARD_STRIDE, word)

    def cards(self):
        return tuple(struct.unpack_from("<I", self.card, n * CARD_STRIDE)[0] for n in range(2))

    def cd_init(self, path):
        slot, rest = divmod(path - c.addressof(self.cfg.disc_slot), SLOT)
        assert rest == 0 and 0 <= slot < 4, (slot, rest)
        # POPS sends 0x80 bytes from there to the IOP by DMA: the slot and
        # what follows it, which must still be the configuration.
        assert path + 0x80 <= c.addressof(self.cfg) + c.sizeof(self.cfg)
        assert path % 16 == 0
        self.calls.append((slot, c.string_at(path, SLOT)))
        return 0

    def frame(self, buttons):
        struct.pack_into("<H", self.pad, 2, buttons)
        L.pops_resident_hotkeys(c.byref(self.cfg), c.byref(self.mem))

    def slots(self):
        return c.string_at(c.addressof(self.cfg.disc_slot), 4 * SLOT)

    def state(self):
        return (self.emode.value, self.lid.value, self.pad[0x28], self.pad[0x90 + 0x28],
                self.scanlines.value, self.cfg.disc_selected, self.slots(), self.cards())


class _OriginalHotkeys:
    """POPStarter's always-live block as shipped (its resident blob, MAIN
    0x983150, which the launch copies to 0x232790), from 0x232790 to the
    controller ID stores at 0x232cb0, on tools/r5900_mini.py. The selected
    slot lives in the immediate of the ori at 0x2328bc. $NOVMC0 / $NOVMC1
    are set the way their handlers set them: byte 1 into the branches at
    0x232c90 / 0x232ca0."""
    SRC, RUN, END = 0x983150, 0x232790, 0x232CB0
    SLOTS, ORI = 0x232950, 0x2328BC

    def __init__(self, image, slots=bytes(4 * SLOT), lid=LID_CLOSED, boot=bytes(SLOT), emode=0x55,
                 scanlines=SCANLINES_OFF, flags=0, cards=(0, 0)):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from r5900_mini import M32, Machine
        self.m = m = Machine()
        m.record = False
        m.write(self.RUN, bytes(image[self.SRC - 0x870000:self.SRC - 0x870000 + self.END - self.RUN]))
        m.write(self.SLOTS, slots)
        m.write(0x70003390, bytes([emode]))
        m.write(0x0059C200, struct.pack("<H", lid))
        m.put32(0x0021E454, scanlines)
        m.write(0x01FFECB0, boot)
        if flags & NOVMC0:
            m.write(0x232C90, b"\x01")
        if flags & NOVMC1:
            m.write(0x232CA0, b"\x01")
        self.set_cards(cards)
        self.calls = []

        def cd_init(mm):
            path = mm.lo(4) & M32
            slot, rest = divmod(path - self.SLOTS, SLOT)
            assert rest == 0 and 0 <= slot < 4, hex(path)
            self.calls.append((slot, mm.read(path, SLOT)))
            mm.set_lo(2, 0)

        m.natives[0x00210540] = cd_init

    def frame(self, buttons):
        self.m.write(0x00507002, struct.pack("<H", buttons))
        self.m.steps = 0
        self.m.run(self.RUN, self.END, limit=5000)

    def set_cards(self, words):
        for n, word in enumerate(words):
            self.m.put32(CARD_STATE + n * CARD_STRIDE, word)

    def cards(self):
        return tuple(self.m.u32(CARD_STATE + n * CARD_STRIDE) for n in range(2))

    def slots(self):
        return self.m.read(self.SLOTS, 4 * SLOT)

    def state(self):
        m = self.m
        selected, rest = divmod(struct.unpack("<H", m.read(self.ORI, 2))[0] - 0x2950, SLOT)
        assert rest == 0 and 0 <= selected < 4
        return (m.read(0x70003390, 1)[0], struct.unpack("<H", m.read(0x0059C200, 2))[0],
                m.read(0x00507028, 1)[0], m.read(0x005070B8, 1)[0], m.u32(0x0021E454), selected,
                self.slots(), self.cards())


class Hotkeys(unittest.TestCase):
    """POPStarter's always-live block: emode, lid, $SCANLINES, the in-game
    disc swap and the $NOVMC0/1 card stores (pops_resident_hotkeys). Host
    memory, no console."""

    def test_emode_scanlines_lid_and_pad_flags(self):
        m = _HotkeyMachine(emode=0x55)
        m.frame(0xFFFF)
        self.assertEqual(m.state()[:5], (0x55, LID_CLOSED, 1, 1, SCANLINES_OFF))
        for buttons, emode in ((COMBO_EMODE_0, 0), (0xFFFF, 0), (COMBO_EMODE_1, 1), (0x1234, 1)):
            m.frame(buttons)
            self.assertEqual(m.emode.value, emode, hex(buttons))
        m.frame(COMBO_SCANLINES_ON)
        self.assertEqual(m.scanlines.value, SCANLINES_ON)
        m.frame(COMBO_SCANLINES_OFF)
        self.assertEqual(m.scanlines.value, SCANLINES_OFF)
        m.frame(COMBO_LID_OPEN)
        self.assertEqual(m.lid.value, LID_OPEN)
        # Every pass sets +0x28 of both pad blocks, whatever the buttons.
        m.pad[0x28] = m.pad[0xB8] = 0
        m.frame(0x0000)
        self.assertEqual((m.pad[0x28], m.pad[0xB8]), (1, 1))
        self.assertEqual(m.calls, [])

    def test_buttons_must_match_exactly(self):
        for buttons in (0xF6FF, 0x76FE, 0xECFF, 0xECFC, 0x7CFF, 0x7CFC, 0xF5FF, 0xFAFF, 0xFCEF,
                        0xFCFE, 0xFCEC, 0x0000, 0xFFFF):
            m = _HotkeyMachine(lid=LID_OPEN, slots=disc_slots(b"A.VCD"), emode=0x55)
            m.frame(buttons)
            self.assertEqual(m.state()[:6], (0x55, LID_OPEN, 1, 1, SCANLINES_OFF, 0), hex(buttons))
            self.assertEqual(m.calls, [])

    def test_swap_loads_the_selected_slot_with_the_lid_open(self):
        names = (b"Game (Disc 1).VCD", b"Game (Disc 2).VCD", b"Game (Disc 3).VCD", b"Game (Disc 4).VCD")
        slots = disc_slots(*names)
        m = _HotkeyMachine(slots=slots)
        m.frame(COMBO_LID_CLOSE)  # the lid is closed: nothing to close
        self.assertEqual((m.lid.value, m.calls), (LID_CLOSED, []))
        for want in (2, 1, 3, 0, 3):
            m.frame(COMBO_DISC[want])
            self.assertEqual(m.cfg.disc_selected, want)
            m.frame(COMBO_LID_OPEN)
            m.frame(COMBO_LID_CLOSE)
            self.assertEqual(m.lid.value, LID_CLOSED)
            self.assertEqual(m.calls[-1], (want, slots[want * SLOT:(want + 1) * SLOT]))
        m.frame(COMBO_LID_CLOSE)
        self.assertEqual(len(m.calls), 5)
        # Any lid value other than open: no swap.
        m.lid.value = 0x1001
        m.frame(COMBO_LID_CLOSE)
        self.assertEqual((m.lid.value, len(m.calls)), (0x1001, 5))
        self.assertEqual(m.slots(), slots)

    def test_empty_slots_take_the_boot_path(self):
        boot = b"pops:/disc/disc0".ljust(SLOT, b"\0")
        slots = bytearray(disc_slots(b"A.VCD"))
        slots[2 * SLOT:3 * SLOT] = bytes(4) + b"x" * (SLOT - 4)  # first word zero: empty
        slots[3 * SLOT:4 * SLOT] = b"\0abc" + bytes(SLOT - 4)     # first word not zero: kept
        m = _HotkeyMachine(slots=bytes(slots), boot=boot)
        m.frame(0xFFFF)
        got = m.slots()
        self.assertEqual(got[:SLOT], bytes(slots[:SLOT]))
        self.assertEqual(got[SLOT:3 * SLOT], boot * 2)
        self.assertEqual(got[3 * SLOT:], bytes(slots[3 * SLOT:]))
        # A boot path whose first word is zero is copied again every pass.
        m = _HotkeyMachine(boot=bytes(4) + b"y" * (SLOT - 4))
        m.frame(0xFFFF)
        m.boot[4] = ord("z")
        m.frame(0xFFFF)
        self.assertEqual(m.slots()[4:6], b"zy")

    def test_close_comes_before_the_slot_copies(self):
        """On the first pass a close loads the still empty slot; the copy
        after it fills the slot for the next one."""
        boot = b"pops:/disc/disc0".ljust(SLOT, b"\0")
        m = _HotkeyMachine(lid=LID_OPEN, boot=boot)
        m.frame(COMBO_LID_CLOSE)
        self.assertEqual(m.calls, [(0, bytes(SLOT))])
        self.assertEqual(m.slots(), boot * 4)
        m.frame(COMBO_LID_OPEN)
        m.frame(COMBO_LID_CLOSE)
        self.assertEqual(m.calls[-1], (0, boot))

    def test_novmc_clears_the_card_state_bytes_every_pass(self):
        """$NOVMC0 / $NOVMC1: the low byte of card 0's / card 1's state word
        becomes 0 on every pass, whatever the buttons; the other three bytes
        and the other card stay. POPS sets bit 0 again only when it reads
        the card's file, but the store does not depend on that."""
        for flags in (0, NOVMC0, NOVMC1, NOVMC0 | NOVMC1):
            m = _HotkeyMachine(flags=flags, cards=(0xA5A5A503, 0x5A5A5A03))
            for buttons in (0xFFFF, COMBO_LID_OPEN, 0x0000):
                m.set_cards((0xA5A5A503, 0x5A5A5A03))
                m.frame(buttons)
                want = (0xA5A5A500 if flags & NOVMC0 else 0xA5A5A503,
                        0x5A5A5A00 if flags & NOVMC1 else 0x5A5A5A03)
                self.assertEqual(m.cards(), want, (hex(flags), hex(buttons)))
            # Nothing else in the block depends on them.
            plain = _HotkeyMachine(cards=(0xA5A5A503, 0x5A5A5A03))
            for buttons in (0xFFFF, COMBO_LID_OPEN, 0x0000):
                plain.frame(buttons)
            self.assertEqual(m.state()[:7], plain.state()[:7], hex(flags))

    def test_build_config_carries_the_slots(self):
        cfg = BuildConfig.parsed(self)
        text = b"A.VCD\nB.VCD"
        L.pops_config_parse_discs(c.addressof(cfg), c.create_string_buffer(text, len(text) + 1), len(text))
        out = ResidentConfig()
        out.disc_selected, out.disc_tail[0] = 3, 7
        L.pops_resident_build_config(c.byref(out), c.addressof(cfg))
        self.assertEqual(c.string_at(c.addressof(out.disc_slot), 4 * SLOT), disc_slots(b"A.VCD", b"B.VCD"))
        self.assertEqual((out.disc_selected, list(out.disc_tail)), (0, [0] * 8))
        self.assertEqual(ResidentConfig.disc_slot.offset % 16, 0)
        self.assertEqual(ResidentConfig.disc_tail.offset, ResidentConfig.disc_slot.offset + 4 * SLOT)

    def test_gp1_work_runs_it_first(self):
        """In the original the block is the first thing after the GP1 hook's
        jump: before the controller IDs, the reset and the break slot."""
        src = (ROOT / "common/src/pops_resident_engine.c").read_text()
        body = src[src.index("void pops_resident_gp1_work(void) {"):]
        body = body[:body.index("\n}\n")]
        at = body.index("pops_resident_hotkeys(cfg, &keys);")
        for later in ("pops_resident_pad_ids(", "POPS_RESET_COMBO", "POPS_BUILTIN_BREAK_ADDR",
                      "pops_resident_timings("):
            self.assertLess(at, body.index(later), later)
        self.assertEqual(body.count("pops_resident_hotkeys("), 1)
        self.assertNotIn("if (", body[:at])

    @unittest.skipUnless(os.environ.get("POPSTARTER_TEST_ELF"), "optional external POPStarter MAIN")
    def test_matches_the_original_block(self):
        from trace_original_pops_io import decode_main

        image = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
        self.assertEqual(struct.unpack_from("<3I", image, 0x983150 - 0x870000),
                         (0x3C1A0050, 0x241BF6FE, 0x875A7002))
        rng = random.Random(0x484B4559)
        combos = [COMBO_EMODE_0, COMBO_EMODE_1, COMBO_LID_OPEN, COMBO_LID_OPEN, COMBO_SCANLINES_ON,
                  COMBO_SCANLINES_OFF, COMBO_LID_CLOSE, COMBO_LID_CLOSE, *COMBO_DISC, 0xFFFF, 0xBCFE,
                  0xFCFE, 0x7CFF, 0xECFF]

        def slot():
            kind = rng.random()
            if kind < 0.3:
                return bytes(SLOT)
            if kind < 0.7:
                name = bytes(rng.choice(b"ABCD ()._-0123456789") for _ in range(rng.randint(1, 40)))
                return (b"pfs0:/" + name + b"\0").ljust(SLOT, bytes([rng.getrandbits(8)]))
            if kind < 0.78:  # first word zero: empty
                return bytes(4) + bytes(rng.getrandbits(8) for _ in range(SLOT - 4))
            if kind < 0.86:  # first byte zero, first word not: kept
                return b"\0" + bytes(rng.randint(1, 255) for _ in range(3)) + bytes(SLOT - 4)
            return bytes(rng.getrandbits(8) for _ in range(SLOT))

        frames = swaps = cleared = 0
        seen_flags = set()
        for case in range(150):
            setup = dict(slots=b"".join(slot() for _ in range(4)),
                         lid=rng.choice([LID_OPEN, LID_CLOSED, 0, rng.getrandbits(16)]),
                         boot=rng.choice([b"pops:/disc/disc0".ljust(SLOT, b"\0"), bytes(SLOT),
                                          bytes(rng.getrandbits(8) for _ in range(SLOT))]),
                         emode=rng.getrandbits(8),
                         scanlines=rng.choice([SCANLINES_ON, SCANLINES_OFF, rng.getrandbits(32)]),
                         flags=(NOVMC0 if case % 4 & 1 else 0) | (NOVMC1 if case % 4 & 2 else 0),
                         cards=(rng.getrandbits(32), rng.getrandbits(32)))
            seen_flags.add(setup["flags"])
            ours, theirs = _HotkeyMachine(**setup), _OriginalHotkeys(image, **setup)
            for frame in range(rng.randint(1, 40)):
                buttons = rng.choice(combos) if rng.random() < 0.85 else rng.getrandbits(16)
                if rng.random() < 0.3:  # POPS changed the card words since the last pass
                    cards = (rng.getrandbits(32), rng.getrandbits(32))
                    ours.set_cards(cards)
                    theirs.set_cards(cards)
                    cleared += bool(setup["flags"]) and any(w & 0xFF for w in cards)
                ours.frame(buttons)
                theirs.frame(buttons)
                where = (case, frame, hex(buttons), hex(setup["flags"]))
                self.assertEqual(ours.state(), theirs.state(), where)
                self.assertEqual(ours.calls, theirs.calls, where)
                frames += 1
            swaps += len(ours.calls)
        self.assertGreater(swaps, 50)
        self.assertEqual(seen_flags, {0, NOVMC0, NOVMC1, NOVMC0 | NOVMC1})
        self.assertGreater(cleared, 100)
        print("Original always-live block PASS: %d passes, %d swaps, %d card stores checked"
              % (frames, swaps, cleared))


class Layout(unittest.TestCase):
    def test_config_fits_in_the_reserved_range(self):
        self.assertEqual(c.sizeof(Header), 112)
        self.assertEqual(Header.guard_entry.offset, 56)
        self.assertEqual((Header.recompiler_entry.offset, Header.recompiler_emit.offset), (92, 96))
        self.assertEqual(ResidentConfig.cheats.offset, 32)
        self.assertLess(c.sizeof(ResidentConfig) + 0x1000, LIMIT - BASE)

    def test_launcher_installs_after_the_last_staging_read(self):
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        hook = src.index("pops_resident_hook_gp1(")
        reboot = src.index("SifIopRebootBuffer(")
        install = src.index("pops_resident_install(")
        trampoline = src.index("memcpy((void *)POPS_TRAMPOLINE_ADDR")
        self.assertLess(hook, reboot, "hook and checks must fail before the IOP reboot")
        self.assertLess(install, trampoline)
        self.assertGreater(install, reboot)


if __name__ == "__main__":
    unittest.main()
