#!/usr/bin/env python3
"""launcHER's copy of POPStarter r13's built-in per-game list against the
original.

Needs the external POPStarter MAIN (POPSTARTER_TEST_ELF) and Unicorn; the
tests are skipped without them. Nothing from the MAIN is stored here.

Oracle: tools/trace_original_pops_vcdid.py runs the original
FUN_008e00d0(id, 3) with its helpers stubbed and recorded (memcpy, poke8,
poke32, compat, card helper, breakpoint helper). The breakpoint helper
FUN_008d6da4 is then run for real, on its own, to learn the 292 bytes it
installs at 0x01460000. From those events the test builds the core and EE
images the original leaves and the flags it sets, and compares them with
what pops_builtin_apply does for the same id. The lookup is checked
against every stored fingerprint in program order, and $VCDID_n parsing
against the original's handlers. Bounded execution of routines with
synthetic inputs, not a POPS boot or a console test.
"""
import ctypes as c
import os
import random
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

HAVE = bool(os.environ.get("POPSTARTER_TEST_ELF"))
try:
    import unicorn  # noqa: F401
except ImportError:
    HAVE = False

CORE_BASE = 0x200000
CORE_SIZE = 0x400000
EE_BASE = 0x01400000
EE_SIZE = 0x80000
MAX_ID = 624
SIG_SIZE = 144
LIBCRYPT2 = 84
GP = 0x9B68F0
BREAK_FN = 0x8D6DA4
JAL_FIX, J_LIBCRYPT2, JAL_BREAK = 0x0C504000, 0x0808E5E0, 0x0C518000
# $FAKELC (handler 0x89caf0): the flag it sets, the 21 bytes it writes into
# POPS, POPS's own bytes there ($UNDO_LIBCRYPT_FIX puts them back), and the
# id bit that asks pops_builtin_apply for an entry run after it.
FAKELC_FLAG = 0x3424
LC_AT = 0x210CF8
FAKELC_LC = bytes.fromhex("001f133c" "00007326" "fcf173ac" "ffff4224" "0000647c" "fd")
POPS_LC = bytes.fromhex("ffff4224" "0000647c" "00000000" "00000000" "00000000" "fa")
AFTER_FAKELC = 0x8000


class Plan(c.Structure):
    _fields_ = [("id", c.c_uint16), ("compat_modes", c.c_uint8), ("subcd", c.c_uint8),
                ("no_vmc1", c.c_uint8), ("no_auto_pal", c.c_uint8), ("fix_call", c.c_uint8),
                ("break_call", c.c_uint8), ("libcrypt2", c.c_uint8),
                ("libcrypt2_code", c.c_uint8 * LIBCRYPT2),
                ("fix_size", c.c_uint32), ("break_size", c.c_uint32)]


def build_lib():
    out = Path(tempfile.mkdtemp())
    lib = out / "builtin.so"
    sources = ["common/src/pops_builtin_db.c", "common/src/pops_builtin_db_data.c",
               "common/src/pops_modes_patches.c", "common/src/pops_config.c",
               "tools/fixtures/pops_config_host_io.c", "common/src/pops_compat_db.c",
               "common/src/pops_resident_engine.c", "common/src/pops_external.c",
               "common/src/pops_vcd.c"]
    subprocess.run(["gcc", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra",
                    "-Dfopen=pops_test_fopen", "-Dfgets=pops_test_fgets",
                    "-Dferror=pops_test_ferror", "-Dfclose=pops_test_fclose",
                    "-I", str(ROOT / "common/include")] +
                   [str(ROOT / s) for s in sources] + ["-o", str(lib)], check=True)
    L = c.CDLL(str(lib))
    L.pops_builtin_apply.argtypes = [c.c_uint16, c.c_void_p, c.c_size_t, c.c_void_p,
                                     c.c_uint32, c.c_size_t, c.POINTER(Plan)]
    L.pops_builtin_apply.restype = c.c_int
    L.pops_builtin_lookup.argtypes = [c.c_char_p]
    L.pops_builtin_lookup.restype = c.c_uint16
    L.pops_builtin_hash.argtypes = [c.c_char_p]
    L.pops_builtin_hash.restype = c.c_uint64
    L.pops_builtin_sig_offsets.argtypes = [c.c_uint64, c.c_uint32, c.c_uint32,
                                           c.POINTER(c.c_uint64)]
    L.pops_compat_mode_write.argtypes = [c.c_void_p, c.c_size_t, c.c_uint8]
    L.pops_compat_mode_write.restype = c.c_int
    return L


LIB = None


def setUpModule():
    global LIB
    LIB = build_lib()


def apply_launcher(n):
    core = (c.c_uint8 * CORE_SIZE)()
    ee = (c.c_uint8 * EE_SIZE)()
    plan = Plan()
    res = LIB.pops_builtin_apply(n, core, CORE_SIZE, ee, EE_BASE, EE_SIZE, c.byref(plan))
    return res, bytes(core), bytes(ee), plan


def plan_flags(plan):
    """A Plan in the shape original() returns its flags."""
    return dict(compat=plan.compat_modes, subcd=plan.subcd, novmc1=plan.no_vmc1,
                nopal=plan.no_auto_pal, fix=plan.fix_call, brk=plan.break_call,
                lc2=plan.libcrypt2, lc2code=bytes(plan.libcrypt2_code) if plan.libcrypt2 else b"",
                fix_size=plan.fix_size, break_size=plan.break_size)


def break_handler(addr, word):
    """Run FUN_008d6da4(addr, word) for real; return the bytes at 0x01460000
    and the words it wrote into the core."""
    from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
    from unicorn import mips_const as R
    import trace_original_pops_vcdid as T
    uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
    try:
        uc.ctl_set_cpu_model(R.UC_CPU_MIPS64_5KF)
    except Exception:
        pass
    uc.mem_map(0, 0x02000000)
    uc.mem_write(T.BASE, bytes(T.img))
    regs = [getattr(R, "UC_MIPS_REG_%d" % i) for i in range(32)]
    upper = [0] * 32
    END = 0xF00000

    def code(u, a, size, _):
        if a == END:
            return
        w = struct.unpack("<I", u.mem_read(a, 4))[0]
        op, rs, rt, rd = w >> 26, (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
        imm = w & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if op == 0x1C and w & 63 == 0x09 and (w >> 6) & 31 == 0x0E:  # pcpyld
            if rd:
                upper[rd] = u.reg_read(regs[rs]) & (2**64 - 1)
                u.reg_write(regs[rd], u.reg_read(regs[rt]))
        elif op == 0x1F:  # sq
            at = (u.reg_read(regs[rs]) + simm) & 0xFFFFFFF0
            u.mem_write(at, struct.pack("<QQ", u.reg_read(regs[rt]) & (2**64 - 1), upper[rt]))
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
    uc.reg_write(R.UC_MIPS_REG_GP, GP)
    uc.reg_write(R.UC_MIPS_REG_SP, T.STACK)
    uc.reg_write(R.UC_MIPS_REG_A0, addr)
    uc.reg_write(R.UC_MIPS_REG_A1, word)
    uc.reg_write(R.UC_MIPS_REG_RA, END)
    uc.emu_start(BREAK_FN, END, count=1_000_000)
    size = struct.unpack("<I", uc.mem_read(GP + 0x28C0, 4))[0]
    return bytes(uc.mem_read(0x01460000, size)), struct.unpack("<I", uc.mem_read(0x232D08, 4))[0]


def original(n, fakelc=False):
    """Expected core/EE images and flags from the original's recorded events.
    fakelc: run the entry as the original does for a $VCDID_n that comes
    after a $FAKELC, with the handler's flag gp+0x3424 set."""
    import trace_original_pops_vcdid as T
    core = bytearray(CORE_SIZE)
    ee = bytearray(EE_SIZE)
    exp = dict(compat=0, subcd=0, novmc1=0, nopal=0, fix=0, brk=0, lc2=0, lc2code=b"",
               fix_size=0, break_size=0)

    def put(addr, data):
        if CORE_BASE <= addr < CORE_BASE + CORE_SIZE:
            core[addr - CORE_BASE:addr - CORE_BASE + len(data)] = data
        elif EE_BASE <= addr < EE_BASE + EE_SIZE:
            ee[addr - EE_BASE:addr - EE_BASE + len(data)] = data
        else:
            raise AssertionError("entry %d writes %#x" % (n, addr))

    for ev in T.run(n, 3, {FAKELC_FLAG: 1} if fakelc else None):
        kind = ev[0]
        if kind == "memcpy":
            dst, _src, length, data = ev[1], ev[2], ev[3], bytes.fromhex(ev[4])
            assert len(data) == length
            if dst == 0x239780:
                exp["lc2code"] = data
                assert length == LIBCRYPT2
            else:
                put(dst, data)
                if dst == 0x01410000:
                    exp["fix_size"] = length
        elif kind == "poke32":
            val, addr = ev[1], ev[2]
            if addr == 0x2397D8:
                assert val == JAL_FIX
                exp["fix"] = 1
            elif addr == 0x238D00:
                assert val == J_LIBCRYPT2
                exp["lc2"] = 1
            else:
                put(addr, struct.pack("<I", val))
        elif kind == "poke8":
            put(ev[2], bytes([ev[1] & 0xFF]))
        elif kind == "compat":
            k = ev[1]
            if not (exp["subcd"] and k in (1, 2, 3, 5)):  # FUN_008dc2c4's gate
                exp["compat"] |= 1 << (k - 1)
                buf = (c.c_uint8 * CORE_SIZE).from_buffer_copy(core)
                assert LIB.pops_compat_mode_write(buf, CORE_SIZE, k) == 0
                core[:] = bytes(buf)
        elif kind == "f8dc12c":
            assert ev[1] == 2
            exp["novmc1"] = 1
        elif kind == "f8d6da4":
            data, slot = break_handler(ev[1], ev[2])
            assert slot == JAL_BREAK
            put(0x01460000, data)
            exp["break_size"] = len(data)
            exp["brk"] = 1
        elif kind == "store":
            addr, size, val = ev[1], ev[2], ev[3]
            if addr == GP + 0x3458 and val == 1:
                exp["subcd"] = 1
            elif addr == GP + 0x4FA0 and val == 0:
                exp["nopal"] = 1
            elif addr in (GP + 0x38C0, GP + 0x38BC) or 0x972300 <= addr < 0x984CA0:
                pass  # busy flag, card flag (paired with the helper), template edits
            else:
                raise AssertionError("entry %d stores %#x" % (n, addr))
        else:
            raise AssertionError(kind)
    return bytes(core), bytes(ee), exp


@unittest.skipUnless(HAVE, "needs POPSTARTER_TEST_ELF and unicorn")
class Entries(unittest.TestCase):
    def test_every_entry_matches_the_original(self):
        diffs = []
        for n in range(MAX_ID + 1):
            core, ee, exp = original(n)
            res, lcore, lee, plan = apply_launcher(n)
            self.assertEqual(res, 0, n)
            got = plan_flags(plan)
            if core != lcore or ee != lee or exp != got:
                diffs.append((n, exp, got, core == lcore, ee == lee))
        self.assertEqual(diffs, [], "entries differing from the original: %r" % diffs[:5])

    def test_every_entry_after_fakelc_matches_the_original(self):
        """A $VCDID_n after a $FAKELC: the original runs the entry with
        gp+0x3424 set, and 216 entries jump over part of themselves."""
        import trace_original_pops_vcdid as T
        # The handler also clears template bytes 0x972370, 0x972374 and
        # 0x972375 before its copy. They are 0 in the image, and the entries'
        # own template edits are those same three bytes, so the flag is the
        # only state an entry run after it sees differently.
        at = 0x972370 - T.BASE
        self.assertEqual(bytes(T.img[at:at + 1]) + bytes(T.img[at + 4:at + 6]), bytes(3))
        diffs, changed = [], []
        for n in range(MAX_ID + 1):
            core, ee, exp = original(n, fakelc=True)
            if (core, ee, exp) != original(n):
                changed.append(n)
            res, lcore, lee, plan = apply_launcher(n | AFTER_FAKELC)
            self.assertEqual((res, plan.id), (0, n))
            got = plan_flags(plan)
            if core != lcore or ee != lee or exp != got:
                diffs.append((n, exp, got, core == lcore, ee == lee))
        self.assertEqual(diffs, [], "entries differing from the original: %r" % diffs[:5])
        self.assertEqual(len(changed), 216)
        # 213 of them lose their LibCrypt write: 203 only that, 207..216 also
        # their game-fix code and breakpoint handler. 230 and 231 lose their
        # game-fix code, 232 that, three core writes and its sub-CD flag.
        # Entry 6 is the LibCrypt write alone.
        core, _, _ = original(6)
        self.assertEqual(core[LC_AT - CORE_BASE:LC_AT - CORE_BASE + 21],
                         bytes.fromhex("011f133c70ad7326fcf173acffff42240000647cfd"))
        self.assertEqual(original(6, fakelc=True)[0], bytes(CORE_SIZE))

    def test_ids_past_the_last_entry_are_rejected(self):
        plan = Plan()
        self.assertEqual(LIB.pops_builtin_apply(MAX_ID + 1, None, 0, None, 0, 0, c.byref(plan)), -2)

    def test_core_too_small_rejects_without_writing(self):
        core = (c.c_uint8 * 0x10000)()
        plan = Plan()
        # Entry 3 writes 0x239780-area code and 0x210cf8 (past 0x210000).
        self.assertEqual(LIB.pops_builtin_apply(3, core, 0x10000, None, 0, 0, c.byref(plan)), -34)
        self.assertEqual(bytes(core), bytes(0x10000))

    def test_plan_only_and_sizes_only_calls(self):
        for n in range(MAX_ID + 1):
            full = apply_launcher(n)[3]
            plan = Plan()
            self.assertEqual(LIB.pops_builtin_apply(n, None, 0, None, 0, 0, c.byref(plan)), 0)
            self.assertEqual(bytes(plan), bytes(full), n)


@unittest.skipUnless(HAVE, "needs POPSTARTER_TEST_ELF and unicorn")
class Lookup(unittest.TestCase):
    def test_every_stored_fingerprint_finds_its_first_id(self):
        import gen_pops_builtin_db as G
        sigs = G.signatures(G.image())
        self.assertEqual(len(sigs), 607)
        first = {}
        for i, s in sigs:
            first.setdefault(s, i)
        for i, s in sigs:
            self.assertEqual(LIB.pops_builtin_lookup(s), first[s])
        # Four stored fingerprints repeat an earlier one (ids 398/382, 461/90,
        # 528/527 and the second copy of 508), so the later copies never match.
        seen = set()
        dups = 0
        for i, s in sigs:
            dups += s in seen
            seen.add(s)
        self.assertEqual(dups, 4)
        self.assertEqual(sum(1 for i, s in sigs if first[s] != i), 3)

    def test_unknown_fingerprints_find_nothing(self):
        rng = random.Random(7)
        for _ in range(200):
            self.assertEqual(LIB.pops_builtin_lookup(bytes(rng.randrange(256) for _ in range(SIG_SIZE))), 0)
        self.assertEqual(LIB.pops_builtin_lookup(bytes(SIG_SIZE)), 0)

    def test_hash_is_fnv1a64(self):
        self.assertEqual(LIB.pops_builtin_hash(bytes(SIG_SIZE)), G_fnv(bytes(SIG_SIZE)))
        self.assertEqual(LIB.pops_builtin_hash(bytes(range(144))), G_fnv(bytes(range(144))))

    def test_offsets_are_the_originals_for_a_raw_image(self):
        out = (c.c_uint64 * 3)()
        LIB.pops_builtin_sig_offsets(0x100000, 2352, 24, out)
        self.assertEqual(list(out), [0x109340, 0x109640, 0x10CA70])
        LIB.pops_builtin_sig_offsets(0, 2048, 0, out)
        self.assertEqual(list(out), [16 * 2048 + 40, 16 * 2048 + 808, 22 * 2048 + 56])


def G_fnv(data):
    h = 0xCBF29CE484222325
    for b in data:
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


@unittest.skipUnless(HAVE, "needs POPSTARTER_TEST_ELF and unicorn")
class VcdidCommand(unittest.TestCase):
    """$VCDID_n as the original parses it (handlers 0x890f4c..0x891e78)."""

    @staticmethod
    def original_calls(text):
        import trace_original_pops_cheats as T
        from unicorn import Uc, UC_HOOK_CODE
        from unicorn import mips_const as R
        calls = []
        orig = Uc.hook_add

        def patched(self, kind, cb, *a, **k):
            if kind != UC_HOOK_CODE:
                return orig(self, kind, cb, *a, **k)

            def wrap(u, addr, size, ud):
                if addr == 0x8E00D0:
                    calls.append(u.reg_read(R.UC_MIPS_REG_A0) & 0xFFFFFFFF)
                    u.reg_write(R.UC_MIPS_REG_PC, u.reg_read(R.UC_MIPS_REG_RA))
                    return
                return cb(u, addr, size, ud)
            return orig(self, kind, wrap, *a, **k)
        Uc.hook_add = patched
        try:
            T.compile_cheats(text)
        finally:
            Uc.hook_add = orig
        return calls

    @staticmethod
    def launcher(text):
        from test_pops_features import PopsConfig
        cfg = PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        for line in text.replace("\r\n", "\n").split("\n"):
            LIB.pops_config_parse_line(c.byref(cfg), line.encode("latin-1"))
        return [cfg.vcdid] if cfg.vcdid_set else []

    def effective(self, text):
        """The entry the original's $VCDID_n commands select. Each command
        runs FUN_008e00d0 only while gp+0x38d8 is 0; $VCDID_0 runs entry 0,
        which does nothing, and leaves it 0, so at most one call does
        something."""
        calls = self.original_calls(text)
        picked = [n for n in calls if n]
        self.assertLessEqual(len(picked), 1, (text, calls))
        self.assertEqual(calls, [0] * (len(calls) - len(picked)) + picked, (text, calls))
        return picked

    def test_fixed_cases(self):
        LIB.pops_config_init.argtypes = [c.c_void_p]
        LIB.pops_config_parse_line.argtypes = [c.c_void_p, c.c_char_p]
        cases = ["$VCDID_5", "$VCDID_12", "$VCDID_123", "$VCDID_0508", "$VCDID_1234",
                 "$VCDID_12345", "$VCDID_07", "$VCDID_5x", "$VCDID_x5", "$VCDID_5\n$VCDID_6",
                 "$VCDID_999", "$VCDID_0", "$VCDID_5 ", "$VCDID_5\r\n", "$vcdid_5",
                 "$VCDID_", "$VCDID_ 5", "$VCDID_-5", "$NOPAD0 $VCDID_6",
                 "$VCDID_00005", "$VCDID_1234x", "$VCDID_0\n$VCDID_5", "$VCDID_00 $VCDID_7",
                 "$VCDID_0000\n$VCDID_0\n$VCDID_12", "$VCDID_8\n$VCDID_0\n$VCDID_9"]
        for text in cases:
            self.assertEqual(self.launcher(text), self.effective(text), repr(text))
        # $VCDID_0 runs entry 0 and leaves the id free for the next one.
        self.assertEqual(self.original_calls("$VCDID_0\n$VCDID_5"), [0, 5])
        # Known difference (quirk 22): the original starts a command at any
        # '$'; launcHER's parser needs the '$' at the start of a white-space
        # delimited token, so a '$' glued to other text is not a command.
        self.assertEqual(self.original_calls("x$VCDID_9999"), [9999])
        self.assertEqual(self.launcher("x$VCDID_9999"), [])

    def test_random_cases(self):
        LIB.pops_config_init.argtypes = [c.c_void_p]
        LIB.pops_config_parse_line.argtypes = [c.c_void_p, c.c_char_p]
        rng = random.Random(11)
        alphabet = "0123456789_$VCDIx \n"
        for _ in range(40):  # each text runs the original's whole parser
            body = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 7)))
            text = rng.choice(["$VCDID_", "$vcdid_", "$VCDID"]) + body
            if rng.random() < 0.3:
                text += "\n$VCDID_" + str(rng.randrange(0, 20000))
            self.assertEqual(self.launcher(text), self.effective(text), repr(text))


@unittest.skipUnless(HAVE, "needs POPSTARTER_TEST_ELF and unicorn")
class FakelcCommand(unittest.TestCase):
    """$FAKELC with $UNDO_LIBCRYPT_FIX and $VCDID_n, in file order, through
    the original's whole parser. POPS's own bytes are put at 0x210cf8
    first. The original runs a $VCDID_n's entry where the command stands;
    here the entry's LibCrypt write (as the original's entry makes it, with
    the flag it sees there) is put in its place. The bytes at 0x210cf8
    after the parse, and the id and flag the entry ran with, are compared
    with launcHER's: its entry first (as after a $FAKELC when one came
    before the $VCDID_n), then its config pass."""
    IDS = (3, 6, 109, 207, 232, 504, 999)  # 999: an id with no entry
    entry_lc = {}

    @classmethod
    def setUpClass(cls):
        import trace_original_pops_vcdid as T
        for n in cls.IDS:
            for flag in (0, 1):
                writes = [bytes.fromhex(ev[4]) for ev in T.run(n, 3, {FAKELC_FLAG: flag})
                          if ev[0] == "memcpy" and ev[1] == LC_AT]
                cls.entry_lc[n, flag] = writes[-1] if writes else None
        LIB.pops_config_init.argtypes = [c.c_void_p]
        LIB.pops_config_parse_line.argtypes = [c.c_void_p, c.c_char_p]
        LIB.pops_apply_all_config_patches.argtypes = [c.c_void_p, c.c_size_t, c.c_void_p]
        LIB.pops_apply_all_config_patches.restype = c.c_int

    def original(self, text):
        import trace_original_pops_cheats as P
        from unicorn import Uc, UC_HOOK_CODE
        from unicorn import mips_const as R
        calls, engines = [], []
        hook_add, emu_start = Uc.hook_add, Uc.emu_start

        def patched(uc, kind, cb, *a, **k):
            if kind != UC_HOOK_CODE:
                return hook_add(uc, kind, cb, *a, **k)

            def wrap(u, addr, size, ud):
                if addr == 0x8E00D0:
                    n = u.reg_read(R.UC_MIPS_REG_A0) & 0xFFFFFFFF
                    flag = struct.unpack("<I", u.mem_read(GP + FAKELC_FLAG, 4))[0]
                    calls.append((n, flag))
                    if n:
                        self.assertIn((n, int(flag != 0)), self.entry_lc, text)
                        data = self.entry_lc[n, int(flag != 0)]
                        if data:
                            u.mem_write(LC_AT, data)
                    u.reg_write(R.UC_MIPS_REG_PC, u.reg_read(R.UC_MIPS_REG_RA))
                    return
                return cb(u, addr, size, ud)
            return hook_add(uc, kind, wrap, *a, **k)

        def start(uc, *a, **k):
            self.assertEqual(engines, [])
            engines.append(uc)
            uc.mem_write(LC_AT, POPS_LC)
            return emu_start(uc, *a, **k)

        Uc.hook_add, Uc.emu_start = patched, start
        try:
            P.compile_cheats(text)
        finally:
            Uc.hook_add, Uc.emu_start = hook_add, emu_start
        picked = [(n, flag) for n, flag in calls if n]
        self.assertLessEqual(len(picked), 1, text)
        return bytes(engines[0].mem_read(LC_AT, 21)), picked[0] if picked else None

    def launcher(self, text):
        from test_pops_features import PopsConfig
        cfg = PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        for line in text.replace("\r\n", "\n").split("\n"):
            LIB.pops_config_parse_line(c.byref(cfg), line.encode("latin-1"))
        core = bytearray(CORE_SIZE)
        core[LC_AT - CORE_BASE:LC_AT - CORE_BASE + 21] = POPS_LC
        buf = (c.c_uint8 * CORE_SIZE).from_buffer(core)
        picked = None
        if cfg.vcdid_set:
            after = (cfg.fakelc & 0x02) != 0  # POPS_FAKELC_BEFORE_VCDID
            picked = (cfg.vcdid, int(after))
            if cfg.vcdid <= MAX_ID:
                plan = Plan()
                self.assertEqual(LIB.pops_builtin_apply(cfg.vcdid | (AFTER_FAKELC if after else 0),
                                                        buf, CORE_SIZE, None, 0, 0, c.byref(plan)), 0)
        self.assertEqual(LIB.pops_apply_all_config_patches(buf, CORE_SIZE, c.byref(cfg)), 0, text)
        del buf
        return bytes(core[LC_AT - CORE_BASE:LC_AT - CORE_BASE + 21]), picked

    def test_orders_match_the_original(self):
        self.assertEqual(self.entry_lc[6, 0], bytes.fromhex("011f133c70ad7326fcf173acffff42240000647cfd"))
        self.assertIsNone(self.entry_lc[6, 1])
        cases = {
            "$FAKELC": (FAKELC_LC, None), "$fakelc": (FAKELC_LC, None),
            "$FAKELC\r\n": (FAKELC_LC, None), "$FAKELC ": (FAKELC_LC, None),
            "$FAKELCX": (POPS_LC, None), "$FAKE_LC": (POPS_LC, None),
            "$FAKELC $FAKELC": (FAKELC_LC, None),
            "$FAKELC\n$VCDID_6": (FAKELC_LC, (6, 1)),
            "$VCDID_6\n$FAKELC": (FAKELC_LC, (6, 0)),
            "$VCDID_6": (self.entry_lc[6, 0], (6, 0)),
            "$FAKELC\n$VCDID_207": (FAKELC_LC, (207, 1)),
            "$VCDID_109 $FAKELC": (FAKELC_LC, (109, 0)),
            "$FAKELC\n$VCDID_232": (FAKELC_LC, (232, 1)),
            "$FAKELC\n$VCDID_3": (FAKELC_LC, (3, 1)),
            "$FAKELC\n$VCDID_999": (FAKELC_LC, (999, 1)),
            "$UNDO_LIBCRYPT_FIX\n$FAKELC": (FAKELC_LC, None),
            "$FAKELC\n$UNDO_LIBCRYPT_FIX": (POPS_LC, None),
            "$FAKELC $UNDO_LIBCRYPT_FIX $FAKELC": (FAKELC_LC, None),
            "$FAKELC\n$UNDO_LIBCRYPT_FIX\n$VCDID_6": (POPS_LC, (6, 1)),
            "$UNDO_LIBCRYPT_FIX\n$FAKELC\n$VCDID_6": (FAKELC_LC, (6, 1)),
            "$VCDID_6\n$FAKELC\n$UNDO_LIBCRYPT_FIX": (POPS_LC, (6, 0)),
            "$VCDID_6\n$UNDO_LIBCRYPT_FIX\n$FAKELC": (FAKELC_LC, (6, 0)),
            "$VCDID_6\n$UNDO_LIBCRYPT_FIX": (POPS_LC, (6, 0)),
            "$FAKELC\n$VCDID_6\n$UNDO_LIBCRYPT_FIX": (POPS_LC, (6, 1)),
            "$VCDID_0\n$FAKELC\n$VCDID_6": (FAKELC_LC, (6, 1)),
            "$VCDID_6\n$VCDID_0\n$FAKELC": (FAKELC_LC, (6, 0)),
            "$VCDID_504\n$FAKELC": (FAKELC_LC, (504, 0)),
        }
        for text, want in cases.items():
            self.assertEqual(self.original(text), want, repr(text))
            self.assertEqual(self.launcher(text), want, repr(text))

    def test_known_differences(self):
        # Quirk 23: the original runs the entry where $VCDID_n stands, so an
        # $UNDO_LIBCRYPT_FIX before it is overwritten by the entry's write;
        # launcHER runs the entry before every command.
        text = "$UNDO_LIBCRYPT_FIX\n$VCDID_6"
        self.assertEqual(self.original(text), (self.entry_lc[6, 0], (6, 0)))
        self.assertEqual(self.launcher(text), (POPS_LC, (6, 0)))
        # Quirk 22: the original ends the name only at a space, CR, LF, NUL
        # or '$', and starts a command at any '$', also inside a '#' line;
        # launcHER splits on any white space and needs the '$' to start a
        # token outside a comment.
        for text, original, launcher in (
                ("$FAKELC\t", POPS_LC, FAKELC_LC),
                ("$FAKELC$NOPAD0", FAKELC_LC, POPS_LC),
                ("x$FAKELC", FAKELC_LC, POPS_LC),
                ("#$FAKELC", FAKELC_LC, POPS_LC)):
            self.assertEqual(self.original(text), (original, None), repr(text))
            self.assertEqual(self.launcher(text), (launcher, None), repr(text))

    def test_random_orders(self):
        rng = random.Random(23)
        words = ["$FAKELC", "$UNDO_LIBCRYPT_FIX", "$VCDID_6", "$VCDID_207", "$VCDID_0",
                 "$VCDID_232", "$NOPAD0", "$fakelc"]
        for _ in range(60):
            text = "".join(rng.choice(words) + rng.choice([" ", "\n", "\r\n"])
                           for _ in range(rng.randrange(1, 6)))
            orig, mine = self.original(text), self.launcher(text)
            if orig == mine:
                continue
            # Only quirk 23 may differ: an $UNDO_LIBCRYPT_FIX before the
            # $VCDID_n that ran, with no $FAKELC after the entry's write.
            self.assertIsNotNone(orig[1], text)
            self.assertEqual(orig[1], mine[1], text)
            self.assertEqual(mine[0], POPS_LC, text)


if __name__ == "__main__":
    unittest.main()
