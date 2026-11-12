#!/usr/bin/env python3
"""$RESET_WARMBOOT: launcHER's pass against POPStarter r13's own (external inputs).

Native checks need nothing. The differential checks need POPSTARTER_TEST_ELF,
POPS_TEST_ELF and unicorn: the original's block 0x8795f0..0x879cf4 is run on the
real core and on random synthetic cores (tools/trace_original_pops_warmboot.py)
and its bytes must equal pops_apply_reset_warmboot's; its parser is run on
fixed texts and must set the flag when launcHER does. Nothing here is a
console run.
"""
import ctypes as c
import os
import random
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pops_features as F  # noqa: E402  (builds the host library)

LIB = F.compile_shared_library()
LIB.pops_apply_reset_warmboot.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(c.c_uint32)]
LIB.pops_apply_reset_warmboot.restype = c.c_int
LIB.pops_config_init.argtypes = [c.POINTER(F.PopsConfig)]
LIB.pops_config_parse_line.argtypes = [c.POINTER(F.PopsConfig), c.c_char_p]
LIB.pops_config_parse_line.restype = c.c_int

CORE = 0x200000
ROM_BASE = 0x24BC20
SCAN_TOP = 0x2CBB4C
A0 = [0x3a, 0x40, 0x4f, 0x50, 0x53, 0x9a, 0x9b, 0xa1]
B0 = [0x52, 0x5a, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f, 0x21, 0x22, 0x23, 0x2a, 0x2b, 0x38]
C0 = [0x0b, 0x14]

HAVE = bool(os.environ.get("POPSTARTER_TEST_ELF")) and bool(os.environ.get("POPS_TEST_ELF"))
if HAVE:
    try:
        import unicorn  # noqa: F401
        import trace_original_pops_warmboot as W
    except Exception:
        HAVE = False


def stub(table, func):
    return struct.pack("<III", 0x240a0000 | table, 0x01400008, 0x24090000 | func)


def apply(core):
    buf = (c.c_uint8 * len(core)).from_buffer(core)
    vec = c.c_uint32(0xDEADBEEF)
    rc = LIB.pops_apply_reset_warmboot(buf, len(core), c.byref(vec))
    return rc, vec.value


class Native(unittest.TestCase):
    def test_rewrites_the_listed_stubs_and_finds_the_exit_stub(self):
        core = bytearray(0x303000)
        at = {}
        p = ROM_BASE + 0x100
        for table, funcs in ((0xa0, A0 + [0x41, 0x00]), (0xb0, B0 + [0x19, 0x53]), (0xc0, C0 + [0x0a])):
            for f in funcs:
                core[p - CORE:p - CORE + 12] = stub(table, f)
                at[(table, f)] = p
                p += 16
        second = ROM_BASE + 0x8000  # a second SystemErrorExit stub, higher up
        core[second - CORE:second - CORE + 12] = stub(0xa0, 0x3a)
        before = bytes(core)
        rc, vec = apply(core)
        self.assertEqual(rc, 1)
        # The lowest-address A0:3A stub wins (the scan walks downward and
        # each match overwrites the recorded address). The recorded value is
        # the stub's EE address, as the original stores it (quirk 26).
        self.assertEqual(vec, at[(0xa0, 0x3a)])
        for (table, f), q in at.items():
            got = core[q - CORE:q - CORE + 12]
            want = bytearray(before[q - CORE:q - CORE + 12])
            listed = f in {0xa0: A0, 0xb0: B0, 0xc0: C0}[table]
            if listed:
                want[8] = 0xa0
                if table != 0xa0:
                    want[0] = 0xa0
            self.assertEqual(bytes(got), bytes(want), (hex(table), hex(f)))
        self.assertEqual(core[second - CORE + 8], 0xa0)
        # Everything else untouched.
        touched = set()
        for (table, f), q in at.items():
            touched.update(range(q - CORE, q - CORE + 12))
        touched.update(range(second - CORE, second - CORE + 12))
        for i in range(len(core)):
            if i not in touched:
                self.assertEqual(core[i], before[i], hex(CORE + i))

    def test_no_exit_stub_returns_zero(self):
        core = bytearray(0x303000)
        p = ROM_BASE + 0x40
        core[p - CORE:p - CORE + 12] = stub(0xb0, 0x52)
        rc, vec = apply(core)
        self.assertEqual((rc, vec), (0, 0))
        self.assertEqual(core[p - CORE], 0xa0)
        self.assertEqual(core[p - CORE + 8], 0xa0)

    def test_bounds(self):
        core = bytearray(0x303000)
        # The bottom address itself is not scanned (the loop stops there).
        core[ROM_BASE - CORE:ROM_BASE - CORE + 12] = stub(0xa0, 0x3a)
        # The top address is.
        core[SCAN_TOP - CORE:SCAN_TOP - CORE + 12] = stub(0xa0, 0x40)
        rc, vec = apply(core)
        self.assertEqual((rc, vec), (0, 0))
        self.assertEqual(core[ROM_BASE - CORE + 8], 0x3a)
        self.assertEqual(core[SCAN_TOP - CORE + 8], 0xa0)
        small = bytearray(SCAN_TOP - CORE)
        self.assertEqual(apply(small)[0], -34)  # -ERANGE
        self.assertEqual(LIB.pops_apply_reset_warmboot(None, 0x303000, None), -22)

    def test_command_parses(self):
        for text, want in (("$RESET_WARMBOOT", 1), ("$reset_warmboot", 1), ("$RESET_WARMBOOTX", 0),
                           ("$RESET_WARMBOO", 0), ("$RESET_WARMBOOT $NOPAD0", 1)):
            cfg = F.PopsConfig()
            LIB.pops_config_init(c.byref(cfg))
            LIB.pops_config_parse_line(c.byref(cfg), text.encode())
            self.assertEqual(cfg.reset_warmboot, want, text)
            if "NOPAD0" in text:
                self.assertEqual(cfg.pad_override & 1, 1)


@unittest.skipUnless(HAVE, "needs POPSTARTER_TEST_ELF, POPS_TEST_ELF and unicorn")
class Original(unittest.TestCase):
    """The original's pass (run as shipped) against launcHER's, byte for byte."""

    BLOB = range(0x232CE8 - CORE, 0x232D10 - CORE)

    def compare(self, core):
        events, after, _blob, gp_slot = W.run(bytes(core))
        ours = bytearray(core)
        rc, vec = apply(ours)
        # The original's resident-block edits (0x232cf4..0x232d08) are not
        # core edits in launcHER: the GP1 work stores the vector itself.
        for i in range(len(core)):
            if i in self.BLOB:
                continue
            self.assertEqual(ours[i], after[i], hex(CORE + i))
        p, = struct.unpack("<I", gp_slot)
        if p:
            self.assertEqual(rc, 1)
            self.assertEqual(vec, p)  # the EE address, not the ROM one (quirk 26)
            # Its blob edits: branch over the store (offset 6), lui hi, ori lo, sw.
            self.assertEqual(after[0x232CF4 - CORE], 6)
            self.assertEqual(struct.unpack_from("<H", after, 0x232D00 - CORE)[0], vec >> 16)
            self.assertEqual(struct.unpack_from("<H", after, 0x232D06 - CORE)[0], 0x377b)
            self.assertEqual(struct.unpack_from("<H", after, 0x232D04 - CORE)[0], vec & 0xffff)
            self.assertEqual(struct.unpack_from("<I", after, 0x232D08 - CORE)[0], 0xaf5b0000)
        else:
            self.assertEqual((rc, vec), (0, 0))
            for i in self.BLOB:
                self.assertEqual(ours[i], after[i], hex(CORE + i))
        return rc, vec

    def test_real_core(self):
        core = W.core_image(os.environ["POPS_TEST_ELF"])
        rc, vec = self.compare(core)
        self.assertEqual(rc, 1)
        self.assertEqual(vec, 0x2594F0)  # the owner's POPS: lowest A0:3A stub (ROM 0xbfc0d8d0)

    def test_random_cores(self):
        rng = random.Random(0x5741524d)
        funcs = sorted(set(A0 + B0 + C0 + [0x00, 0x19, 0x41, 0x53, 0x5b, 0xa0, 0xa2]))
        for _ in range(8):
            core = bytearray(rng.getrandbits(8) for _ in range(0x1000)) * (0x303000 // 0x1000)
            # Random words are never stubs; plant some, overlapping allowed.
            for _ in range(rng.randrange(1, 40)):
                p = rng.randrange(ROM_BASE - 8, SCAN_TOP + 12, 4)
                table = rng.choice([0xa0, 0xa0, 0xb0, 0xb0, 0xc0, 0xc0, 0x90, 0x00])
                s = stub(table, rng.choice(funcs))
                core[p - CORE:p - CORE + 12] = s
            self.compare(core)

    def test_command_matches_the_original(self):
        import trace_original_pops_cheats as T
        from unicorn import Uc, UC_HOOK_CODE
        from unicorn import mips_const as R

        def original(text):
            hits = []
            orig = Uc.hook_add

            def patched(self, kind, cb, *a, **k):
                if kind != UC_HOOK_CODE:
                    return orig(self, kind, cb, *a, **k)

                def wrap(u, addr, size, ud):
                    if addr == 0x8923A4:
                        hits.append(1)
                    return cb(u, addr, size, ud)
                return orig(self, kind, wrap, *a, **k)
            Uc.hook_add = patched
            try:
                T.compile_cheats(text)
            finally:
                Uc.hook_add = orig
            return 1 if hits else 0

        def launcher(text):
            cfg = F.PopsConfig()
            LIB.pops_config_init(c.byref(cfg))
            for line in text.replace("\r\n", "\n").split("\n"):
                LIB.pops_config_parse_line(c.byref(cfg), line.encode("latin-1"))
            return cfg.reset_warmboot

        same = ["$RESET_WARMBOOT", "$reset_warmboot", "$RESET_WARMBOOT\n", "$RESET_WARMBOOT\r\n",
                "$RESET_WARMBOOT $NOPAD0", "$NOPAD0 $RESET_WARMBOOT", "$RESET_WARMBOOTX",
                "$RESET_WARMBOO",
                # The original ends the name at a space, CR, LF, NUL or '$'
                # (a tab does not end it), starts a command at any '$', and
                # a '#' does not hide one. These four were launcHER
                # differences until its reader became the original's
                # (tools/test_pops_config_text.py).
                "$RESET_WARMBOOT\t", "x$RESET_WARMBOOT", "$RESET_WARMBOOT$NOPAD0",
                "# $RESET_WARMBOOT"]
        for text in same:
            self.assertEqual(launcher(text), original(text), repr(text))
        self.assertEqual([original(text) for text in same[-4:]], [0, 1, 1, 1])


if __name__ == "__main__":
    unittest.main()
