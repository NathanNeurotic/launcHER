#!/usr/bin/env python3
"""POPStarter r13's $BREAKPOINT0 / $BREAKPOINT1 (external inputs optional).

Native checks need nothing. With POPSTARTER_TEST_ELF and unicorn the
original's FUN_008d6da4 runs as shipped, once per command in file order,
and pops_breakpoint_build must leave the same bytes at 0x01460000 (and the
original must poke the chain call at 0x232d08 that launcHER's resident
chain makes). The source check pins where the launch uses it. No console
run.
"""
import ctypes as c
import itertools
import os
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pops_features as F  # noqa: E402  (builds the host library)

LIB = F.compile_shared_library()
LIB.pops_breakpoint_build.argtypes = [c.c_uint8, c.c_void_p, c.c_size_t]
LIB.pops_breakpoint_build.restype = c.c_int
LIB.pops_config_init.argtypes = [c.POINTER(F.PopsConfig)]
LIB.pops_config_parse_line.argtypes = [c.POINTER(F.PopsConfig), c.c_char_p]
LIB.pops_config_parse_line.restype = c.c_int

BP0, BP1, SEEN0 = 0x01, 0x02, 0x04
SIZE = 0x130
TEMPLATE = 292
AREA = 0x01460000
MAIN_BASE = 0x870000
GP = 0x9B68F0
BREAK_FN = 0x8D6DA4
MEMCPY = 0x918808

HAVE_MAIN = bool(os.environ.get("POPSTARTER_TEST_ELF"))
try:
    import unicorn  # noqa: F401
    HAVE_UC = True
except ImportError:
    HAVE_UC = False


def build(state, size=SIZE, fill=0xA5):
    buf = (c.c_uint8 * size)(*([fill] * size))
    n = LIB.pops_breakpoint_build(state, buf, size)
    return n, bytes(buf)


def parse(text):
    cfg = F.PopsConfig()
    LIB.pops_config_init(c.byref(cfg))
    for line in text.split("\n"):
        LIB.pops_config_parse_line(c.byref(cfg), line.encode("latin-1"))
    return cfg.breakpoint


def state_after(commands):
    """PopsConfig.breakpoint after these commands in file order."""
    return parse("\n".join("$BREAKPOINT%d" % k for k in commands))


def words(blob, at, n):
    return list(struct.unpack_from("<%dI" % n, blob, at))


class Native(unittest.TestCase):
    def test_commands_parse(self):
        self.assertEqual(parse(""), 0)
        self.assertEqual(parse("$BREAKPOINT0"), BP0 | SEEN0)
        self.assertEqual(parse("$breakpoint1"), BP1)
        self.assertEqual(parse("$BREAKPOINT0\n$BREAKPOINT1"), BP1 | SEEN0)
        self.assertEqual(parse("$BREAKPOINT1\n$BREAKPOINT0"), BP0 | SEEN0)
        self.assertEqual(parse("$BREAKPOINT"), 0)
        self.assertEqual(parse("$BREAKPOINT2"), 0)
        self.assertEqual(parse("$BREAKPOINT01"), 0)

    def test_none_and_bad_arguments(self):
        self.assertEqual(build(0)[0], 0)
        self.assertEqual(build(SEEN0)[0], 0)
        self.assertEqual(build(BP0 | BP1)[0], -22)
        self.assertEqual(LIB.pops_breakpoint_build(BP0, None, SIZE), -22)
        self.assertEqual(build(BP0, SIZE - 1)[0], -34)
        self.assertEqual(build(BP1, TEMPLATE - 1)[0], -34)
        self.assertEqual(build(BP1 | SEEN0, SIZE - 1)[0], -34)

    def test_sizes_and_untouched_bytes(self):
        n, b = build(BP1)
        self.assertEqual(n, TEMPLATE)
        self.assertEqual(b[TEMPLATE:], bytes([0xA5]) * (SIZE - TEMPLATE))
        self.assertEqual(build(BP0)[0], SIZE)
        self.assertEqual(build(BP1 | SEEN0)[0], SIZE)

    def test_bp0_shape(self):
        _, b = build(BP0)
        self.assertEqual(words(b, 0, 8), [0x3C1A0120, 0x8F5AFDF4, 0x3C1B0000, 0x377B0002,
                                          0, 0x175B0002, 0, 0x03E00008])
        self.assertEqual(words(b, 0x80, 1), [0x10000027])
        self.assertEqual(words(b, 0x11C, 5), [0, 0x3C1A0146, 0xAF400014, 0x03E00008, 0])

    def test_bp1_shape(self):
        _, b = build(BP1)
        self.assertEqual(words(b, 0, 8), [0x3C1A0050, 0x875A7002, 0x241BDCFE, 0x175B001C,
                                          0, 0, 0, 0])
        self.assertEqual(words(b, 0x11C, 2), [0, 0])
        _, b0 = build(BP0)
        _, b1 = build(BP1 | SEEN0)
        # After a $BREAKPOINT0 the words it wrote past the copy stay.
        self.assertEqual(b1[TEMPLATE:], b0[TEMPLATE:])
        self.assertEqual(b1[:TEMPLATE], b[:TEMPLATE])

    def test_template_matches_every_builtin_handler(self):
        """The rest of the bytes are the built-in handlers' template."""
        _, b = build(BP1)
        tmpl = bytearray(b[:TEMPLATE])
        tmpl[0:0x20] = b"\0" * 0x20
        found = 0
        # Read the template back from the generated data through the C API.
        LIB.pops_builtin_entry_ops.argtypes = [c.c_uint16, c.c_void_p, c.c_void_p]
        LIB.pops_builtin_entry_ops.restype = c.c_int

        class Op(c.Structure):
            _fields_ = [("kind", c.c_uint8), ("arg", c.c_uint8), ("len", c.c_uint16),
                        ("addr", c.c_uint32), ("data", c.c_uint32)]

        data = (c.c_uint8 * 1).in_dll(LIB, "pops_builtin_data")
        base = c.addressof(data)
        for n in range(625):
            ops = c.POINTER(Op)()
            count = c.c_uint()
            if LIB.pops_builtin_entry_ops(n, c.byref(ops), c.byref(count)):
                continue
            for i in range(count.value):
                op = ops[i]
                if op.kind == 1 and op.addr == AREA:
                    h = bytearray(c.string_at(base + op.data, op.len))
                    self.assertEqual(len(h), TEMPLATE)
                    h[0:0x20] = b"\0" * 0x20
                    h[0x11C:0x124] = b"\0" * 8
                    self.assertEqual(h, tmpl, n)
                    found += 1
        self.assertEqual(found, 14)


def run_original(commands, before=None):
    """FUN_008d6da4 per command, in order, as the original's parse calls it."""
    from trace_original_pops_io import decode_main
    from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
    from unicorn import mips_const as R
    main = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
    uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
    try:
        uc.ctl_set_cpu_model(R.UC_CPU_MIPS64_5KF)
    except Exception:
        pass
    uc.mem_map(0, 0x02000000)
    uc.mem_write(MAIN_BASE, bytes(main))
    if before:
        uc.mem_write(AREA, bytes(before))
    regs = [getattr(R, "UC_MIPS_REG_%d" % i) for i in range(32)]
    upper = [0] * 32
    end = 0xF00000

    def code(u, a, size, _):
        if a == end:
            return
        if a == MEMCPY:
            a0, a1, a2 = (u.reg_read(regs[r]) & 0xFFFFFFFF for r in (4, 5, 6))
            u.mem_write(a0, bytes(u.mem_read(a1, a2)))
            u.reg_write(regs[2], a0)
            u.reg_write(R.UC_MIPS_REG_PC, u.reg_read(regs[31]))
            return
        w = struct.unpack("<I", u.mem_read(a, 4))[0]
        op, rs, rt, rd, sa = w >> 26, (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31, (w >> 6) & 31
        imm = w & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        m64 = 2**64 - 1
        if op == 0x1C and w & 63 == 0x09 and sa == 0x0E:  # pcpyld rd, rs, rt
            if rd:
                upper[rd] = u.reg_read(regs[rs]) & m64 if rs else 0
                u.reg_write(regs[rd], u.reg_read(regs[rt]) if rt else 0)
        elif op == 0x1C and w & 63 == 0x29 and sa == 0x12:  # por rd, rs, rt
            if rd:
                lo = (u.reg_read(regs[rs]) if rs else 0) | (u.reg_read(regs[rt]) if rt else 0)
                hi = (upper[rs] if rs else 0) | (upper[rt] if rt else 0)
                u.reg_write(regs[rd], lo & m64)
                upper[rd] = hi
        elif op == 0x1F:  # sq
            at = (u.reg_read(regs[rs]) + simm) & 0xFFFFFFF0
            u.mem_write(at, struct.pack("<QQ", u.reg_read(regs[rt]) & m64 if rt else 0,
                                        upper[rt] if rt else 0))
        elif op == 0x1E:  # lq
            at = (u.reg_read(regs[rs]) + simm) & 0xFFFFFFF0
            lo, hi = struct.unpack("<QQ", u.mem_read(at, 16))
            if rt:
                u.reg_write(regs[rt], lo)
                upper[rt] = hi
        elif op == 0x1C:
            raise AssertionError("unmodelled MMI %#010x at %#x" % (w, a))
        else:
            return
        u.reg_write(R.UC_MIPS_REG_PC, a + 4)

    uc.hook_add(UC_HOOK_CODE, code)
    for k in commands:
        uc.reg_write(R.UC_MIPS_REG_GP, GP)
        uc.reg_write(R.UC_MIPS_REG_SP, 0x1F00000)
        uc.reg_write(regs[4], k)
        uc.reg_write(regs[5], k)
        uc.reg_write(regs[31], end)
        uc.emu_start(BREAK_FN, end, count=1_000_000)
    size = struct.unpack("<I", uc.mem_read(GP + 0x28C0, 4))[0]
    return (bytes(uc.mem_read(AREA, SIZE)), struct.unpack("<I", uc.mem_read(0x232D08, 4))[0], size)


@unittest.skipUnless(HAVE_MAIN and HAVE_UC, "needs POPSTARTER_TEST_ELF and unicorn")
class Original(unittest.TestCase):
    def test_handlers_call_it(self):
        from trace_original_pops_io import decode_main
        main = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())

        def w(addr):
            return struct.unpack_from("<I", main, addr - MAIN_BASE)[0]

        jal = 0x0C000000 | (BREAK_FN >> 2)
        # $BREAKPOINT0: move a0, zero / jal / move a1, zero
        self.assertEqual((w(0x8962E4), w(0x8962E8), w(0x8962EC)), (0x0000202D, jal, 0x0000282D))
        # $BREAKPOINT1: a0 = a1 = 1 around the jal
        self.assertEqual((w(0x896530), w(0x896534), w(0x896538)), (0x24040001, jal, 0x24050001))
        # The two names, compared one byte at a time.
        for start, name in ((0x8960D4, b"$BREAKPOINT0"), (0x896320, b"$BREAKPOINT1")):
            got = []
            a = start
            while len(got) < len(name):
                v = w(a)
                if v >> 16 == 0x2402:  # addiu v0, zero, imm
                    got.append(v & 0xFF)
                a += 4
            self.assertEqual(bytes(got), name)

    def test_template_size(self):
        self.assertEqual(run_original([0])[2], TEMPLATE)

    def test_every_order_matches(self):
        for n in range(1, 4):
            for seq in itertools.product((0, 1), repeat=n):
                want, chain, _ = run_original(list(seq))
                self.assertEqual(chain, 0x0C518000, seq)  # jal 0x01460000
                got_n, got = build(state_after(seq), fill=0)
                self.assertEqual(got[:got_n], want[:got_n], seq)
                # Past what launcHER writes the original wrote nothing either.
                self.assertEqual(want[got_n:], bytes(SIZE - got_n), seq)

    def test_over_a_builtin_handler(self):
        """The list runs first; a $BREAKPOINT after it replaces its handler."""
        before = bytearray(build(BP1)[1][:TEMPLATE])
        struct.pack_into("<II", before, 0x11C, 0x8001234, 0x14400002)
        for seq in ([0], [1], [0, 1]):
            want, _, _ = run_original(seq, before)
            got_n, got = build(state_after(seq), fill=0)
            self.assertEqual(got[:got_n], want[:got_n], seq)


class Source(unittest.TestCase):
    def test_launch_order(self):
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        body = src[src.index("int launchPOPS("):]
        discover = body.index("res = pops_config_discover(&cfg, vcdDir, gameBase);")
        builtin = body.index("cfg.builtin_break_call = builtinPlan.break_call;")
        mark = body.index("if (cfg.breakpoint & (POPS_BREAKPOINT_0 | POPS_BREAKPOINT_1)) {\n"
                          "    cfg.builtin_break_call = 1;")
        warm = body.index("cfg.builtin_break_call = 0;")
        builtin_install = body.index("res = pops_builtin_apply(builtinId, NULL, 0, (uint8_t *)0,")
        install = body.index("res = pops_breakpoint_build(cfg.breakpoint,")
        resident = body.index("res = pops_resident_install(")
        build_cfg = body.index("pops_resident_build_config(&residentCfg, &cfg);")
        self.assertLess(discover, mark)
        self.assertLess(builtin, mark)
        self.assertLess(mark, warm)          # $RESET_WARMBOOT still drops the call (quirk 25)
        self.assertLess(warm, build_cfg)
        self.assertLess(builtin_install, install)
        self.assertLess(install, resident)


if __name__ == "__main__":
    unittest.main()
