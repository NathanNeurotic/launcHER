#!/usr/bin/env python3
"""POPStarter r13's opcode pass and $ORIGINAL_OPCODES (external inputs optional).

Native checks need nothing. With POPSTARTER_TEST_ELF and unicorn the
original's pass (0x87c4a0) runs as shipped over a synthetic core (and with
POPS_TEST_ELF over the real one) and launcHER's pops_apply_opcode_pass must
leave the same bytes. The source check pins where the launch runs it. No
console run.
"""
import ctypes as c
import os
import random
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pops_features as F  # noqa: E402  (builds the host library)

LIB = F.compile_shared_library()
LIB.pops_apply_opcode_pass.argtypes = [c.c_void_p, c.c_size_t]
LIB.pops_apply_opcode_pass.restype = c.c_int
LIB.pops_config_init.argtypes = [c.POINTER(F.PopsConfig)]
LIB.pops_config_parse_line.argtypes = [c.POINTER(F.PopsConfig), c.c_char_p]
LIB.pops_config_parse_line.restype = c.c_int

CORE = 0x200000
LAST = 0x4F677F
SIZE = LAST + 2 - CORE
RANGES = [(0x200C62, 0x24BC1F), (0x4EDE20, 0x4F320F), (0x4F3A48, 0x4F40C7),
          (0x4F4210, 0x4F4C97), (0x4F5260, 0x4F5537), (0x4F58D0, 0x4F5F4B),
          (0x4F6098, 0x4F677F)]
PASS = 0x87C4A0
MAIN_BASE = 0x870000
GP = 0x9B68F0
MEMCPY = 0x918808

HAVE_MAIN = bool(os.environ.get("POPSTARTER_TEST_ELF"))
HAVE_CORE = HAVE_MAIN and bool(os.environ.get("POPS_TEST_ELF"))
try:
    import unicorn  # noqa: F401
    HAVE_UC = True
except ImportError:
    HAVE_UC = False


def apply(core):
    buf = (c.c_uint8 * len(core)).from_buffer(core)
    return LIB.pops_apply_opcode_pass(buf, len(core))


def h16(core, addr):
    return struct.unpack_from("<H", core, addr - CORE)[0]


def put16(core, addr, value):
    struct.pack_into("<H", core, addr - CORE, value)


def parse(text):
    cfg = F.PopsConfig()
    LIB.pops_config_init(c.byref(cfg))
    for line in text.split("\n"):
        LIB.pops_config_parse_line(c.byref(cfg), line.encode("latin-1"))
    return cfg.original_opcodes


def seeded_core(seed):
    """Random bytes, plus many values on and next to the pass's edges."""
    rng = random.Random(seed)
    core = bytearray(rng.getrandbits(8) for _ in range(SIZE))
    edges = [0x8BFF, 0x8C00, 0x8FFF, 0x9000, 0xABFF, 0xAC00, 0xAFFF, 0xB000,
             0x3C00, 0x3C01, 0x3C1F, 0x3C20]
    for start, end in RANGES:
        for _ in range(400):
            a = start + 4 * rng.randrange((end - start) // 4 + 1)
            put16(core, a, rng.choice(edges))
            if rng.random() < 0.5:
                put16(core, a - 2, rng.choice(edges))
    return core


class Native(unittest.TestCase):
    def test_load_store_upper_halves(self):
        core = bytearray(SIZE)
        a = 0x200C62
        for value, want in ((0x8C00, 0x9800), (0x8FFF, 0x9BFF), (0xAC00, 0xB800),
                            (0xAFFF, 0xBBFF), (0x8BFF, 0x8BFF), (0x9000, 0x9000),
                            (0xABFF, 0xABFF), (0xB000, 0xB000)):
            put16(core, a, value)
            apply(core)
            self.assertEqual(h16(core, a), want, hex(value))
            put16(core, a, 0)

    def test_lui_template_changes_the_immediate(self):
        core = bytearray(SIZE)
        a = 0x200C66 + 4 * 10
        put16(core, a, 0x3C02)       # lui v0
        put16(core, a - 2, 0x8C00)   # its immediate: lw template
        self.assertEqual(apply(core), 1)
        self.assertEqual(h16(core, a - 2), 0x9800)
        self.assertEqual(h16(core, a), 0x3C02)
        for lui in (0x3C00, 0x3C20):  # rt 0, or rs set: no change
            put16(core, a, lui)
            put16(core, a - 2, 0xAC00)
            self.assertEqual(apply(core), 0)
            self.assertEqual(h16(core, a - 2), 0xAC00)

    def test_only_the_walked_halfwords(self):
        core = bytearray(SIZE)
        put16(core, 0x200C60, 0x8C00)          # low half of the first word: not walked
        put16(core, 0x200C5E, 0x8C00)          # before the first range
        put16(core, 0x24BC22, 0x8C00)          # after it
        put16(core, 0x4EDE22, 0x8C00)          # high half in a word-aligned range
        put16(core, LAST - 3, 0x8C00)          # last walked address of the last range
        put16(core, 0x24BC1E, 0x8C00)          # last walked address of the first range
        self.assertEqual(apply(core), 2)
        self.assertEqual(h16(core, LAST - 3), 0x9800)
        self.assertEqual(h16(core, 0x24BC1E), 0x9800)
        for a in (0x200C60, 0x200C5E, 0x24BC22, 0x4EDE22):
            self.assertEqual(h16(core, a), 0x8C00, hex(a))

    def test_bounds(self):
        self.assertEqual(apply(bytearray(SIZE - 1)), -34)
        self.assertEqual(apply(bytearray(SIZE)), 0)
        self.assertEqual(LIB.pops_apply_opcode_pass(None, SIZE), -22)

    def test_command_parses(self):
        self.assertEqual(parse(""), 0)
        self.assertEqual(parse("$ORIGINAL_OPCODES"), 1)
        self.assertEqual(parse("$original_opcodes"), 1)
        self.assertEqual(parse("$ORIGINAL_OPCODE"), 0)


def run_original(core):
    from trace_original_pops_io import decode_main
    from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
    from unicorn.mips_const import (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_GP,
                                    UC_MIPS_REG_SP, UC_MIPS_REG_PC, UC_MIPS_REG_RA, UC_MIPS_REG_V0)
    main = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
    uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
    try:
        uc.ctl_set_cpu_model(5)
    except Exception:
        pass
    uc.mem_map(0, 0x02000000)
    uc.mem_write(MAIN_BASE, bytes(main))
    uc.mem_write(CORE, bytes(core))
    sentinel = 0x1E00000

    def code(u, addr, size, _):
        a0, a1, a2 = (u.reg_read(r) & 0xFFFFFFFF for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2))
        u.mem_write(a0, bytes(u.mem_read(a1, a2)))
        u.reg_write(UC_MIPS_REG_V0, a0)
        u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))

    uc.hook_add(UC_HOOK_CODE, code, begin=MEMCPY, end=MEMCPY)
    uc.reg_write(UC_MIPS_REG_GP, GP)
    uc.reg_write(UC_MIPS_REG_SP, 0x1F00000)
    uc.reg_write(UC_MIPS_REG_RA, sentinel)
    uc.emu_start(PASS, sentinel, count=400_000_000)
    return bytearray(uc.mem_read(CORE, len(core)))


@unittest.skipUnless(HAVE_MAIN and HAVE_UC, "needs POPSTARTER_TEST_ELF and unicorn")
class Original(unittest.TestCase):
    def test_gate_and_call(self):
        from trace_original_pops_io import decode_main
        main = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
        w = struct.unpack_from("<4I", main, 0x87A64C - MAIN_BASE)
        self.assertEqual(w[0], 0x8F8238C4)                     # lw v0, 0x38c4(gp)
        self.assertEqual(w[1] >> 16, 0x1440)                   # bnez v0 (skip)
        self.assertEqual(w[3], 0x0C000000 | (PASS >> 2))       # jal 0x87c4a0

    def test_synthetic_cores_match(self):
        for seed in (1, 2):
            core = seeded_core(seed)
            want = run_original(core)
            got = bytearray(core)
            n = apply(got)
            self.assertEqual(got, want, seed)
            self.assertEqual(n, sum(1 for i in range(0, len(core), 2) if core[i:i + 2] != want[i:i + 2]))

    @unittest.skipUnless(HAVE_CORE, "needs POPS_TEST_ELF")
    def test_real_core_matches(self):
        import trace_original_pops_warmboot as W
        core = W.core_image(os.environ["POPS_TEST_ELF"])
        want = run_original(core)
        got = bytearray(core)
        n = apply(got)
        self.assertEqual(got, want)
        print("\nOriginal opcode pass vs launcHER on the real core: %d halfwords, identical" % n)
        self.assertGreater(n, 10000)


class Source(unittest.TestCase):
    def test_pass_is_the_last_core_change_and_gated(self):
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        body = src[src.index("int launchPOPS("):]
        gate = body.index("if (!cfg.original_opcodes) {")
        call = body.index("res = pops_apply_opcode_pass((void *)stagedCore, plan.core_size);")
        hooks = body.index("res = pops_resident_hook_display(")
        warm = body.index("res = pops_apply_reset_warmboot(")
        names = body.index("res = pops_module_irx_apply_names(")
        handoff = body.index("res = pops_trampoline_args_init(&handoffCheck")
        reboot = body.index("res = SifIopRebootBuffer(")
        self.assertLess(gate, call)
        for earlier in (hooks, warm, names):
            self.assertLess(earlier, call)
        self.assertLess(call, handoff)
        self.assertLess(call, reboot)
        # No later write into the core's walked ranges.
        tail = body[call:]
        for writer in ("pops_resident_hook_", "pops_apply_", "pops_fix_stage(", "pops_compat_mode_write("):
            self.assertNotIn(writer, tail[len("res = pops_apply_opcode_pass("):], writer)


if __name__ == "__main__":
    unittest.main()
