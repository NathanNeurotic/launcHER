#!/usr/bin/env python3
"""$LOAD_PADMAN / $KILL_PADMAN against POPStarter r13 (external inputs optional).

Native checks need nothing. With POPSTARTER_TEST_ELF the original's
post-reset block (0x87aba8..0x87ac64) is decoded and its pokes, module
address and length must equal launcHER's constants; with POPS_TEST_ELF as
well, the real core's call site must be POPS's start of padman_hsync and
pops_apply_padman must change exactly those 6 bytes; with unicorn the
original's parser must set the same flags as launcHER's. No console run.
"""
import ctypes as c
import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pops_features as F  # noqa: E402  (builds the host library)

LIB = F.compile_shared_library()
LIB.pops_apply_padman.argtypes = [c.c_void_p, c.c_size_t]
LIB.pops_apply_padman.restype = c.c_int
LIB.pops_config_init.argtypes = [c.POINTER(F.PopsConfig)]
LIB.pops_config_parse_line.argtypes = [c.POINTER(F.PopsConfig), c.c_char_p]
LIB.pops_config_parse_line.restype = c.c_int

CORE = 0x200000
SITE = 0x200358
IRX_ADDR = 0x2CD560
IRX_SIZE = 0xADF0
MAIN_BASE = 0x870000

HAVE_MAIN = bool(os.environ.get("POPSTARTER_TEST_ELF"))
HAVE_CORE = HAVE_MAIN and bool(os.environ.get("POPS_TEST_ELF"))


def apply(core):
    buf = (c.c_uint8 * len(core)).from_buffer(core)
    return LIB.pops_apply_padman(buf, len(core))


def parse(text):
    cfg = F.PopsConfig()
    LIB.pops_config_init(c.byref(cfg))
    for line in text.replace("\r\n", "\n").split("\n"):
        LIB.pops_config_parse_line(c.byref(cfg), line.encode("latin-1"))
    return cfg.load_padman, cfg.kill_padman


class Native(unittest.TestCase):
    def test_pokes(self):
        core = bytearray(b"\xAA" * 0x1000)
        self.assertEqual(apply(core), 0)
        off = SITE - CORE
        self.assertEqual(core[off:off + 4], b"\0\0\0\0")
        self.assertEqual(core[off + 4:off + 10], b"\xAA" * 6)
        self.assertEqual(core[off + 10:off + 12], b"\x00\x10")
        changed = [i for i, b in enumerate(core) if b != 0xAA]
        self.assertEqual(changed, [off, off + 1, off + 2, off + 3, off + 10, off + 11])

    def test_bounds(self):
        self.assertEqual(apply(bytearray(SITE - CORE + 11)), -34)  # -ERANGE
        self.assertEqual(apply(bytearray(SITE - CORE + 12)), 0)
        self.assertEqual(LIB.pops_apply_padman(None, 0x1000), -22)

    def test_commands_parse(self):
        self.assertEqual(parse(""), (0, 0))
        self.assertEqual(parse("$LOAD_PADMAN"), (1, 0))
        self.assertEqual(parse("$kill_padman"), (0, 1))
        self.assertEqual(parse("$LOAD_PADMAN $KILL_PADMAN"), (1, 1))
        self.assertEqual(parse("$LOAD_PADMANX\n$KILL_PADMA"), (0, 0))


@unittest.skipUnless(HAVE_MAIN, "needs POPSTARTER_TEST_ELF")
class OriginalBlock(unittest.TestCase):
    """The original's own instructions give launcHER's constants."""

    @classmethod
    def setUpClass(cls):
        from trace_original_pops_io import decode_main
        cls.main = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())

    def words(self, addr, n):
        off = addr - MAIN_BASE
        return list(struct.unpack("<%dI" % n, self.main[off:off + 4 * n]))

    def test_load_padman_block(self):
        w = self.words(0x87ABA8, 0x10)
        self.assertEqual(w[0], 0x8F8338A8)            # lw v1, 0x38a8(gp)
        self.assertEqual(w[4], 0x8F823824)            # lw v0, 0x3824(gp)
        self.assertEqual(w[7], 0x3C04002C)            # lui a0, 0x2c
        self.assertEqual(w[8], 0x3484D560)            # ori a0, a0, 0xd560
        self.assertEqual(w[9], 0x3405ADF0)            # ori a1, zero, 0xadf0
        self.assertEqual(w[12], 0x0C000000 | (0x91C248 >> 2))  # jal start-module-buffer
        self.assertEqual((0x2C << 16) | 0xD560, IRX_ADDR)
        self.assertEqual(0xADF0, IRX_SIZE)

    def test_both_commands_poke_the_same_two_sites(self):
        for start, flag in ((0x87ABE4, 0x38A8), (0x87AC44, 0x3870)):
            w = self.words(start, 8)
            self.assertEqual(w[0], 0x0000202D, hex(start))   # move a0, zero (daddu)
            self.assertEqual(w[1], 0x3C050020)               # lui a1, 0x20
            self.assertEqual(w[2], 0x0C000000 | (0x87C300 >> 2))  # 32-bit poke
            self.assertEqual(w[3], 0x34A50358)               # ori a1, a1, 0x358
            self.assertEqual(w[4], 0x24041000)               # addiu a0, zero, 0x1000
            self.assertEqual(w[5], 0x3C050020)
            self.assertEqual(w[6], 0x0C000000 | (0x87C2CC >> 2))  # 16-bit poke
            self.assertEqual(w[7], 0x34A50362)               # ori a1, a1, 0x362
        # $KILL_PADMAN's gate
        self.assertEqual(self.words(0x87AC34, 1)[0], 0x8F833870)


@unittest.skipUnless(HAVE_CORE, "needs POPSTARTER_TEST_ELF and POPS_TEST_ELF")
class RealCore(unittest.TestCase):
    def test_call_site_is_pops_padman_start(self):
        import trace_original_pops_warmboot as W
        core = W.core_image(os.environ["POPS_TEST_ELF"])
        off = SITE - CORE
        w = struct.unpack("<6I", bytes(core[off - 0x10:off + 8]))
        self.assertEqual(w[4], 0x0C000000 | (0x2001D8 >> 2))   # jal 0x2001d8
        self.assertEqual(w[0], 0x3C05002E)                    # lui a1, 0x2e
        self.assertEqual(w[1], 0x2484D560)                    # addiu a0, a0, -0x2aa0 (0x2cd560)
        self.assertEqual(w[2], 0x24A58345)                    # addiu a1, a1, -0x7cbb (0x2d8345)
        self.assertEqual(w[5], 0x0000382D)                    # move a3, zero
        self.assertLessEqual(0x2D8345 - IRX_ADDR, IRX_SIZE)   # original reads 11 bytes more
        nxt = struct.unpack("<I", bytes(core[off + 8:off + 12]))[0]
        self.assertEqual(nxt >> 16, 0x0443)                   # bgezl v0
        self.assertEqual(core[IRX_ADDR - CORE:IRX_ADDR - CORE + 4], b"\x7fELF")
        before = bytes(core)
        self.assertEqual(apply(core), 0)
        diff = [i for i in range(len(before)) if before[i] != core[i]]
        self.assertTrue(set(diff) <= {off, off + 1, off + 2, off + 3, off + 10, off + 11}, diff)
        self.assertEqual(struct.unpack("<I", bytes(core[off:off + 4]))[0], 0)
        self.assertEqual(struct.unpack("<I", bytes(core[off + 8:off + 12]))[0] >> 16, 0x1000)


if __name__ == "__main__":
    unittest.main()
