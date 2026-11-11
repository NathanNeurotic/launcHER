#!/usr/bin/env python3
"""POPStarter r13's IGR menu skin (IGR_BG.TM2, IGR_NO.TM2, IGR_YES.TM2).

The original's loader (FUN_0087e464, called at 0x876b18) copies the three
files raw over the TIM2 files Sony's POPS carries for its own in-game reset
dialog; launcHER's pure part is pops_igr_skin_stage (common/src/
pops_igr_skin.c) and its reader is pops_stage_igr_skin in handler_pops.c.

Native and Staging need nothing: the table, the limits, the zero fill, what
is refused, which IGR settings leave Sony's dialog reachable, and that the
built-in list, the always-on hooks and the unguarded scans write nothing
inside the three slots. With POPS_TEST_ELF the same is checked on the real
core for launcHER's guarded stages, and Sony's own three files must fill the
slots exactly. With POPSTARTER_TEST_ELF the table is decoded from the
original's instructions. With both and unicorn the original's loader runs as
shipped over the core (tools/trace_original_pops_igr_skin.py, file I/O
modelled) and the whole core must equal what pops_igr_skin_stage leaves, for
boundary and seeded random sizes on both of its backends. The source checks
pin where handler_pops.c reads and stages the files. Nothing here is a
console run.
"""
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pops_launch_hooks as H  # noqa: E402  (builds the library with every staging function)

CORE = 0x00200000
CORE_SIZE = 0x00302E60
MAIN_BASE = 0x870000
BG, NO, YES = 0, 1, 2
# name, slot address, slot size, largest file accepted
SLOTS = [("IGR_BG.TM2", 0x002FEFF0, 0x4C300, 0x4C300),
         ("IGR_NO.TM2", 0x0034B2F0, 0x1DC0, 0x1DBC),
         ("IGR_YES.TM2", 0x0034D0B0, 0x1DC0, 0x1DBC)]
FIRST, END = 0x002FEFF0, 0x0034EE70   # the three slots are back to back

HAVE_CORE = bool(os.environ.get("POPS_TEST_ELF"))
HAVE_MAIN = bool(os.environ.get("POPSTARTER_TEST_ELF"))
HAVE_EMU = HAVE_CORE and HAVE_MAIN
if HAVE_EMU:
    try:
        import unicorn  # noqa: F401
        import trace_original_pops_igr_skin as T
    except Exception:
        HAVE_EMU = False


class Slot(c.Structure):
    _fields_ = [("name", c.c_char_p), ("addr", c.c_uint32), ("slot_size", c.c_uint32),
                ("max_size", c.c_uint32)]


class Op(c.Structure):
    _fields_ = [("kind", c.c_uint8), ("arg", c.c_uint8), ("len", c.c_uint16),
                ("addr", c.c_uint32), ("data", c.c_uint32)]


def build():
    out = Path(tempfile.mkdtemp())
    lib = out / ("igr_skin.dll" if os.name == "nt" else "igr_skin.so")
    subprocess.run(["gcc", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-I", str(ROOT / "common/include"),
                    str(ROOT / "common/src/pops_igr_skin.c"), "-o", str(lib)], check=True)
    lib = c.CDLL(str(lib))
    lib.pops_igr_skin_slot.argtypes = [c.c_int]
    lib.pops_igr_skin_slot.restype = c.POINTER(Slot)
    lib.pops_igr_skin_stage.argtypes = [c.c_void_p, c.c_size_t, c.c_int, c.c_void_p, c.c_size_t]
    lib.pops_igr_skin_stage.restype = c.c_int
    return lib


LIB = build()
L = H.L
L.pops_apply_all_config_patches.argtypes = [c.c_void_p, c.c_size_t, c.c_void_p]
L.pops_builtin_apply.argtypes = [c.c_uint16, c.c_void_p, c.c_size_t, c.c_void_p, c.c_uint32,
                                 c.c_size_t, c.c_void_p]
L.pops_apply_region.argtypes = [c.c_void_p, c.c_size_t, c.c_int, c.c_uint8, c.c_int]
L.pops_apply_reset_warmboot.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(c.c_uint32)]
L.pops_apply_padman.argtypes = [c.c_void_p, c.c_size_t]
L.pops_core_runtime_corrections_stage.argtypes = [c.c_uint32, c.c_void_p, c.c_size_t, c.c_uint32]


def stage(core, which, data, size=None, core_size=None):
    buf = (c.c_uint8 * len(core)).from_buffer(core)
    raw = bytes(data)
    return LIB.pops_igr_skin_stage(buf, len(core) if core_size is None else core_size, which,
                                   raw, len(raw) if size is None else size)


def slot_bytes(core, which):
    _, addr, size, _ = SLOTS[which]
    return bytes(core[addr - CORE:addr - CORE + size])


def skin_range(core):
    return bytes(core[FIRST - CORE:END - CORE])


def boundary_sizes(which):
    _, _, slot, biggest = SLOTS[which]
    return sorted({0, 1, biggest - 1, biggest, biggest + 1, slot, slot + 1})


_NOISE = random.Random(0x49475253).randbytes(CORE_SIZE)


class Native(unittest.TestCase):
    def test_table(self):
        for which, (name, addr, slot, biggest) in enumerate(SLOTS):
            got = LIB.pops_igr_skin_slot(which).contents
            self.assertEqual((got.name, got.addr, got.slot_size, got.max_size),
                             (name.encode(), addr, slot, biggest))
        self.assertFalse(LIB.pops_igr_skin_slot(-1))
        self.assertFalse(LIB.pops_igr_skin_slot(3))
        # Back to back, in file order BG, NO, YES.
        self.assertEqual(SLOTS[BG][1], FIRST)
        self.assertEqual(SLOTS[BG][1] + SLOTS[BG][2], SLOTS[NO][1])
        self.assertEqual(SLOTS[NO][1] + SLOTS[NO][2], SLOTS[YES][1])
        self.assertEqual(SLOTS[YES][1] + SLOTS[YES][2], END)

    def test_boundary_sizes(self):
        rng = random.Random(1)
        accepted = refused = 0
        for which, (_, addr, slot, biggest) in enumerate(SLOTS):
            for size in boundary_sizes(which):
                core = bytearray(_NOISE)
                data = rng.randbytes(size)
                rc = stage(core, which, data)
                off = addr - CORE
                if size <= biggest:
                    self.assertEqual(rc, 0, (which, size))
                    self.assertEqual(slot_bytes(core, which), data + bytes(slot - size), (which, size))
                    self.assertEqual(bytes(core[:off]), _NOISE[:off])
                    self.assertEqual(bytes(core[off + slot:]), _NOISE[off + slot:])
                    accepted += 1
                else:
                    self.assertEqual(rc, -errno.EFBIG, (which, size))
                    self.assertEqual(bytes(core), _NOISE, (which, size))
                    refused += 1
        # BG: 0, 1, max-1, max accepted, max+1 (= slot+1) refused; its slot is
        # its max. NO and YES: four accepted, max+1, slot, slot+1 refused.
        self.assertEqual((accepted, refused), (12, 7))

    def test_short_core_is_refused_untouched(self):
        for which, (_, addr, slot, biggest) in enumerate(SLOTS):
            end = addr - CORE + slot
            for core_size in (0, addr - CORE - 1, addr - CORE, end - 1):
                core = bytearray(_NOISE[:end])
                self.assertEqual(stage(core, which, b"\x55" * 16, core_size=core_size), -errno.ERANGE)
                # Too big as well: still the range error, still untouched.
                self.assertEqual(stage(core, which, bytes(biggest + 1), core_size=core_size),
                                 -errno.ERANGE)
                self.assertEqual(bytes(core), _NOISE[:end])
            core = bytearray(_NOISE[:end])
            self.assertEqual(stage(core, which, b"\x55" * 16), 0)   # the slot is the last thing in it
            self.assertEqual(slot_bytes(core, which), b"\x55" * 16 + bytes(slot - 16))

    def test_arguments(self):
        core = bytearray(_NOISE)
        buf = (c.c_uint8 * len(core)).from_buffer(core)
        self.assertEqual(LIB.pops_igr_skin_stage(None, len(core), BG, b"x", 1), -errno.EINVAL)
        self.assertEqual(LIB.pops_igr_skin_stage(buf, len(core), -1, b"x", 1), -errno.EINVAL)
        self.assertEqual(LIB.pops_igr_skin_stage(buf, len(core), 3, b"x", 1), -errno.EINVAL)
        self.assertEqual(LIB.pops_igr_skin_stage(buf, len(core), NO, None, 1), -errno.EINVAL)
        self.assertEqual(bytes(core), _NOISE)
        # A zero-length file needs no data pointer, and wipes the slot (quirk).
        self.assertEqual(LIB.pops_igr_skin_stage(buf, len(core), NO, None, 0), 0)
        self.assertEqual(slot_bytes(core, NO), bytes(SLOTS[NO][2]))

    def test_neither_the_slot_nor_the_file_is_inspected(self):
        """No TIM2 magic is wanted in the slot or in the file (the original
        checks neither)."""
        for fill in (b"\x00", b"\xff"):
            core = bytearray(fill * CORE_SIZE)
            self.assertEqual(stage(core, YES, b"not a TIM2 file"), 0)
            self.assertEqual(slot_bytes(core, YES), b"not a TIM2 file" + bytes(SLOTS[YES][2] - 15))

    def test_three_files_fill_one_run_and_nothing_else(self):
        rng = random.Random(2)
        core = bytearray(_NOISE)
        want = b""
        for which, (_, _, slot, biggest) in enumerate(SLOTS):
            data = rng.randbytes(rng.randrange(1, biggest + 1))
            self.assertEqual(stage(core, which, data), 0)
            want += data + bytes(slot - len(data))
        self.assertEqual(skin_range(core), want)
        self.assertEqual(bytes(core[:FIRST - CORE]), _NOISE[:FIRST - CORE])
        self.assertEqual(bytes(core[END - CORE:]), _NOISE[END - CORE:])


# Words of POPS's pad-combination check (FUN_002289e0) that the IGR commands
# and launcHER's direct exit rewrite. The dialog is opened by the code at
# 0x228a5c, reached when the `bne` at 0x228a54 falls through.
IGR_WORDS = {0x00228A20: 0x30A30904, 0x00228A50: 0x24020904, 0x00228A54: 0x14620018,
             0x00228A58: 0x0000102D, 0x00228A5C: 0x3C110086, 0x00228A60: 0x24030080,
             0x00228A64: 0x2622A980, 0x00228A68: 0x0000202D, 0x0020C0A4: 0x0C08B44C}
OPENS_DIALOG = (0x3C110086, 0x24030080, 0x2622A980, 0x0000202D)
DIRECT_EXIT = (0x24020001, 0x10000015, 0x00000000, 0x00000000)
IGR_SETTINGS = [("", "direct"), ("$NOIGR", "off"), ("$IGR0", "dialog"), ("$IGR1", "dialog"),
                ("$IGR2", "dialog"), ("$IGR3", "jump"), ("$IGR4", "jump"), ("$IGR5", "jump")]


def config(line):
    cfg = H.F.PopsConfig()
    L.pops_config_init(c.byref(cfg))
    if line:
        L.pops_config_parse_line(c.byref(cfg), line.encode())
    return cfg


def igr_outcome(core):
    """What the staged pad-combination check does once the combination is
    held: 'dialog' (Sony's dialog, where the skin shows), 'direct'
    (launcHER's immediate exit), 'jump' ($IGR3..5: straight to 0x20c08c) or
    'off' (the branch at 0x228a54 is always taken)."""
    branch = H.u32(core, 0x00228A54)
    tail = tuple(H.u32(core, a) for a in (0x00228A5C, 0x00228A60, 0x00228A64, 0x00228A68))
    if branch >> 16 == 0x1000:
        return "off"
    if branch != 0x14620018:
        return "unknown"
    if tail == OPENS_DIALOG:
        return "dialog"
    if tail == DIRECT_EXIT:
        return "direct"
    if tail[:2] == (0x08083023, 0x00000000):
        return "jump"
    return "unknown"


class Dialog(unittest.TestCase):
    """The skin is only seen when Sony's dialog is: under $IGR0..2."""

    def check(self, make_core):
        for line, want in IGR_SETTINGS:
            core = make_core()
            cfg = config(line)
            self.assertEqual(L.pops_apply_all_config_patches(H.buf(core), len(core), c.byref(cfg)), 0, line)
            self.assertEqual(igr_outcome(core), want, line)

    def test_synthetic_core(self):
        def make():
            core = bytearray(CORE_SIZE)
            for addr, word in IGR_WORDS.items():
                H.put32(core, addr, word)
            return core
        self.assertEqual(igr_outcome(make()), "dialog")   # POPS as shipped
        self.check(make)

    @unittest.skipUnless(HAVE_CORE, "POPS_TEST_ELF not set")
    def test_real_core(self):
        pristine = H.real_core()
        for addr, word in IGR_WORDS.items():
            self.assertEqual(H.u32(pristine, addr), word, hex(addr))
        self.check(lambda: bytearray(pristine))


PLAN = (c.c_uint8 * 512)()   # room for a PopsBuiltinPlan; its contents are not used here


def overlaps(addr, length):
    return addr < END and addr + length > FIRST


class Staging(unittest.TestCase):
    """Nothing else launcHER stages may land in the slots, or the order of
    the skin against it would matter."""

    def test_builtin_entries_write_outside_the_slots(self):
        count = c.c_uint16.in_dll(L, "pops_builtin_op_count").value
        ops = (Op * count).in_dll(L, "pops_builtin_ops")
        core_ops = [op for op in ops if op.kind == 0]
        self.assertGreater(len(core_ops), 200)
        for op in core_ops:
            self.assertFalse(overlaps(op.addr, op.len), hex(op.addr))
        # All of them end far below the first slot.
        self.assertLess(max(op.addr + op.len for op in core_ops), 0x0021B000)
        # And applied: every entry over a marked core.
        marked = b"\xa5" * CORE_SIZE
        for entry in range(1, 625):
            core = bytearray(marked)
            self.assertEqual(L.pops_builtin_apply(entry, H.buf(core), len(core), None, 0, 0, PLAN), 0, entry)
            self.assertEqual(skin_range(core), skin_range(marked), entry)

    def test_always_on_hooks_write_outside_the_slots(self):
        core = H.synthetic_core()
        before = bytes(core)
        self.assertEqual(L.pops_resident_hook_gp1(H.buf(core), len(core), H.BASE + 0x80), 0)
        self.assertEqual(L.pops_resident_hook_recompiler(H.buf(core), len(core), H.RECOMPILER_ENTRY), 0)
        self.assertEqual(L.pops_resident_hook_guards(H.buf(core), len(core), H.header(H.ENTRIES)), 0)
        self.assertEqual(L.pops_apply_always_on_pokes(H.buf(core), len(core)), 0)
        self.assertNotEqual(bytes(core), before)
        self.assertEqual(skin_range(core), skin_range(before))

    def test_unguarded_scans_stay_outside_the_slots(self):
        # The opcode pass rewrites every `lw`/`sw` upper halfword it scans:
        # a core made of nothing else shows its whole reach.
        core = bytearray(struct.pack("<HH", 0x0000, 0x8C00) * (CORE_SIZE // 4))
        before = bytes(core)
        self.assertGreater(L.pops_apply_opcode_pass(H.buf(core), len(core)), 70000)
        self.assertEqual(skin_range(core), skin_range(before))
        # $RESET_WARMBOOT rewrites listed BIOS call stubs: a core made of one.
        stub = struct.pack("<III", 0x240A00B0, 0x01400008, 0x24090052)
        core = bytearray((stub * (CORE_SIZE // 12 + 1))[:CORE_SIZE])
        before = bytes(core)
        vector = c.c_uint32(0)
        self.assertGreaterEqual(L.pops_apply_reset_warmboot(H.buf(core), len(core), c.byref(vector)), 0)
        self.assertNotEqual(bytes(core), before)
        self.assertEqual(skin_range(core), skin_range(before))


# One line per command family the parser knows; what matters here is only
# where the staged writes land.
COMMANDS = (["$COMPATIBILITY_0x%02X" % n for n in range(1, 8)] +
            ["$IGR%d" % n for n in range(6)] +
            ["$RECOMPILER_ADDON_%d" % n for n in range(5)] +
            ["$CODECACHE_ADDON_%d" % n for n in range(3)] +
            ["$NOIGR", "$HDTVFIX", "$NOHDTVFIX", "$FORCEPAL", "$FORCENTSC", "$NOPAL", "$NTSC2PAL",
             "$PAL2NTSC", "$FAKELC", "$SUBCDSTATUS", "$NOVMC0", "$NOVMC1",
             "$UNDO_COMPATIBILITY_CODES", "$UNDO_GAME_FIXES", "$UNDO_LIBCRYPT_FIX",
             "$UNDO_MUTE_CDDA", "$MUTE_ALL", "$MUTE_CDDA", "$MUTE_VAB", "$NOBOOT", "$NODITHER",
             "$DITHER_OFF", "$SMOOTH", "$SCANLINES", "$WIDESCREEN", "$ULTRA_WIDESCREEN",
             "$EYEFINITY", "$SAFEMODE", "$SAFEMODE2", "$NOSAFEMODE", "$CACHE1", "$FASTMIPS",
             "$SLOWMIPS", "$D2LS", "$D2LS_ALT", "$XPOS_8", "$YPOS_8", "$DX_8", "$DY_8",
             "$DW_640", "$DH_448", "$MAGH_3", "$MAGV_1", "$LEFTADJ_8", "$DWSTRETCH_8",
             "$DWCROP_8", "$SET_TIMINGS", "$RESET_WARMBOOT", "$KILL_PADMAN", "$LOAD_PADMAN",
             "$ORIGINAL_OPCODES", "$BREAKPOINT0", "$BREAKPOINT1", "$NOPAD0", "$NOPAD1",
             "$PAD0ID_0X41", "$PAD1ID_0X73", "$ROLLBACK", "$BIOS"])


@unittest.skipUnless(HAVE_CORE, "POPS_TEST_ELF not set")
class RealCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pristine = bytes(H.real_core())
        core = bytearray(cls.pristine)
        cls.steps = []

        def step(name, rc):
            cls.steps.append((name, rc))
            return rc
        # launchPOPS's order up to where the skin is staged.
        step("core patches", L.pops_core_patches_stage(CORE, H.buf(core), len(core), (1 << 7) - 1))
        step("gp1 hook", L.pops_resident_hook_gp1(H.buf(core), len(core), H.BASE + 0x80))
        step("recompiler hook", L.pops_resident_hook_recompiler(H.buf(core), len(core), H.RECOMPILER_ENTRY))
        step("guards", L.pops_resident_hook_guards(H.buf(core), len(core), H.header(H.ENTRIES)))
        step("always-on pokes", L.pops_apply_always_on_pokes(H.buf(core), len(core)))
        cls.staged = bytes(core)

    def test_sonys_own_files_fill_the_slots(self):
        """POPS carries three complete TIM2 files exactly where the original
        writes, and the original's size limits are their sizes."""
        for which, (_, addr, slot, biggest) in enumerate(SLOTS):
            off = addr - CORE
            magic, version, fmt, pictures = struct.unpack_from("<4sBBH", self.pristine, off)
            self.assertEqual((magic, pictures), (b"TIM2", 1), hex(addr))
            total, clut, image, header = struct.unpack_from("<IIIH", self.pristine, off + 16)
            self.assertEqual(16 + total, biggest, hex(addr))
            self.assertEqual(total, header + image + clut)
            self.assertEqual(self.pristine[off + biggest:off + slot], bytes(slot - biggest))
            image_type, width, height = struct.unpack_from("<BHH", self.pristine, off + 16 + 19)
            self.assertEqual((image_type, width, height),
                             (2, 400, 260) if which == BG else (2, 74, 34))
        self.assertEqual(self.pristine[END - CORE:END - CORE + 4], b"TIM2")   # Sony's next file

    def test_stages_before_the_skin_leave_the_slots_alone(self):
        for name, rc in self.steps:
            self.assertEqual(rc, 0, name)
        self.assertNotEqual(self.staged, self.pristine)
        self.assertEqual(skin_range(self.staged), skin_range(self.pristine))

    def staged_with_skin(self):
        rng = random.Random(3)
        core = bytearray(self.staged)
        for which, (_, _, _, biggest) in enumerate(SLOTS):
            self.assertEqual(stage(core, which, rng.randbytes(biggest - which)), 0)
        return core

    def test_stages_after_the_skin_leave_it_alone(self):
        """Each later stage on its own over the staged core with a skin in
        place: whatever it returns, the three slots keep the skin."""
        base = self.staged_with_skin()
        want = skin_range(base)
        self.assertNotEqual(want, skin_range(self.pristine))
        ran = {}

        def run(name, call):
            core = bytearray(base)
            rc = call(core)
            self.assertEqual(skin_range(core), want, name)
            ran.setdefault(name.split()[0], []).append(rc)
            return rc, core

        for entry in range(1, 625):
            run("builtin %d" % entry,
                lambda core: L.pops_builtin_apply(entry, H.buf(core), len(core), None, 0, 0, PLAN))
        for line in COMMANDS:
            cfg = config(line)
            run("command " + line,
                lambda core: L.pops_apply_all_config_patches(H.buf(core), len(core), c.byref(cfg)))
        run("shell edits", lambda core: L.pops_apply_bios_shell_edits(H.buf(core), len(core)))
        for region in range(4):
            for video in range(9):
                for auto_off in (0, 1):
                    run("region %d %d %d" % (region, video, auto_off),
                        lambda core: L.pops_apply_region(H.buf(core), len(core), region, video, auto_off))
        vector = c.c_uint32(0)
        run("warmboot", lambda core: L.pops_apply_reset_warmboot(H.buf(core), len(core), c.byref(vector)))
        run("padman", lambda core: L.pops_apply_padman(H.buf(core), len(core)))
        rc, _ = run("opcodes", lambda core: L.pops_apply_opcode_pass(H.buf(core), len(core)))
        self.assertGreater(rc, 10000)
        # What actually ran (a refusal writes nothing and proves nothing).
        self.assertEqual(ran["builtin"], [0] * 624)
        self.assertEqual(ran["shell"], [0])
        self.assertEqual(ran["padman"], [0])
        self.assertEqual(ran["warmboot"], [1])
        self.assertEqual(ran["command"], [0] * len(COMMANDS))
        self.assertEqual(ran["region"], [0] * 72)

    def test_one_whole_launch_keeps_the_skin(self):
        """The stages in launchPOPS's order on one core: a built-in entry,
        commands, the shell edits, the region pass, $RESET_WARMBOOT, padman
        and the opcode pass, all succeeding, with the skin still in place."""
        core = self.staged_with_skin()
        want = skin_range(core)
        self.assertEqual(L.pops_builtin_apply(1, H.buf(core), len(core), None, 0, 0, PLAN), 0)
        cfg = config("$IGR0")
        L.pops_config_parse_line(c.byref(cfg), b"$COMPATIBILITY_0x04")
        L.pops_config_parse_line(c.byref(cfg), b"$HDTVFIX")
        self.assertEqual(L.pops_apply_all_config_patches(H.buf(core), len(core), c.byref(cfg)), 0)
        self.assertEqual(igr_outcome(core), "dialog")
        self.assertEqual(L.pops_apply_bios_shell_edits(H.buf(core), len(core)), 0)
        self.assertEqual(L.pops_apply_region(H.buf(core), len(core), 1, 0, 0), 0)
        vector = c.c_uint32(0)
        self.assertEqual(L.pops_apply_reset_warmboot(H.buf(core), len(core), c.byref(vector)), 1)
        self.assertEqual(L.pops_apply_padman(H.buf(core), len(core)), 0)
        self.assertGreater(L.pops_apply_opcode_pass(H.buf(core), len(core)), 10000)
        self.assertEqual(skin_range(core), want)


def _words(main, addr, n=1):
    off = addr - MAIN_BASE
    return list(struct.unpack_from("<%dI" % n, main, off))


def _cstr(main, addr):
    off = addr - MAIN_BASE
    return bytes(main[off:main.index(b"\0", off)]).decode("ascii")


@unittest.skipUnless(HAVE_MAIN, "POPSTARTER_TEST_ELF not set")
class OriginalCode(unittest.TestCase):
    """The table, read out of the original's own instructions."""

    FUNC, FUNC_END, GP = 0x87E464, 0x87EB24, 0x9B68F0

    @classmethod
    def setUpClass(cls):
        from trace_original_pops_io import decode_main
        cls.raw = Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes()
        cls.main = bytes(decode_main(cls.raw))
        cls.words = _words(cls.main, cls.FUNC, (cls.FUNC_END - cls.FUNC) // 4)

    def decode(self):
        """Per file block, in address order: the two paths it opens (pfs,
        mass), its size test, and the address and length of its zero fill
        and of its two reads."""
        blocks = []
        cur = None
        w = self.words
        for i, word in enumerate(w):
            target = (word & 0x03FFFFFF) << 2 if word >> 26 == 3 else None
            if target in (0x916758, 0x8D6C94):                       # open
                path_word = w[i - 2] if target == 0x916758 else w[i - 1]
                self.assertEqual(path_word >> 16, 0x2784)              # addiu a0, gp, imm
                path = _cstr(self.main, self.GP + ((path_word & 0xFFFF) ^ 0x8000) - 0x8000)
                if target == 0x916758:
                    cur = {"paths": [path], "fills": [], "reads": [], "limit": None}
                    blocks.append(cur)
                    self.assertEqual(w[i - 1], 0x24050001)             # a1 = 1 (read only)
                    self.assertEqual(w[i + 1], 0x0000302D)             # a2 = 0
                else:
                    cur["paths"].append(path)
                    self.assertEqual(w[i + 1], 0x24050001)
            elif target in (0x9188B8, 0x9169B0, 0x8D6D24):           # memset, read, read
                reg = 4 if target == 0x9188B8 else 5
                prior = w[max(0, i - 6):i]
                lui = [x for x in prior if x >> 16 == (0x3C00 | reg)]
                ori = [x for x in prior if x >> 16 == (0x3400 | reg << 5 | reg)]
                delay = w[i + 1]
                if not lui:          # the tail fill: a0 = slot + size, computed
                    continue
                addr = (lui[-1] & 0xFFFF) << 16 | (ori[-1] & 0xFFFF)
                if delay >> 16 == 0x2406:                              # addiu a2, zero, imm
                    length = delay & 0xFFFF
                else:                                                  # lui a2 ; ori a2 (delay slot)
                    self.assertEqual(delay >> 16, 0x34C6)
                    length = (w[i - 1] & 0xFFFF) << 16 | (delay & 0xFFFF)
                    self.assertEqual(w[i - 1] >> 16, 0x3C06)
                cur["fills" if target == 0x9188B8 else "reads"].append((addr, length))
            elif word >> 16 == 0x2842:                                 # slti v0, v0, imm
                cur["limit"] = ("lt", word & 0xFFFF)
            elif word == 0x0062102A:                                   # slt v0, v1, v0
                self.assertEqual(w[i - 2] >> 16, 0x3C03)
                self.assertEqual(w[i - 1] >> 16, 0x3463)
                cur["limit"] = ("gt", (w[i - 2] & 0xFFFF) << 16 | (w[i - 1] & 0xFFFF))
        return blocks

    def test_table_is_the_originals(self):
        blocks = self.decode()
        self.assertEqual(len(blocks), 3)
        for which, (block, (name, addr, slot, biggest)) in enumerate(zip(blocks, SLOTS)):
            self.assertEqual(block["paths"], ["pfs1:/POPS/" + name, "mass:/POPS/" + name])
            self.assertEqual(block["fills"], [(addr, slot)])
            self.assertEqual(block["reads"], [(addr, slot), (addr, slot)])
            kind, value = block["limit"]
            # BG: too big when size > value. NO, YES: loaded when size < value.
            self.assertEqual(kind, "gt" if which == BG else "lt")
            self.assertEqual(value if kind == "gt" else value - 1, biggest)
            got = LIB.pops_igr_skin_slot(which).contents
            self.assertEqual((got.name.decode(), got.addr, got.slot_size, got.max_size),
                             (name, addr, slot, biggest))

    def test_one_caller_and_its_gates(self):
        n = len(self.main) // 4
        words = struct.unpack_from("<%dI" % n, self.main)
        jal = 0x0C000000 | (self.FUNC >> 2)
        calls = [MAIN_BASE + 4 * i for i, word in enumerate(words) if word == jal]
        self.assertEqual(calls, [0x876B18])
        self.assertNotIn(0x08000000 | (self.FUNC >> 2), words)        # no plain jump
        self.assertNotIn(self.FUNC, words)                            # no pointer
        # Gate 1: the shared abort flag gp+0x38dc. Gate 2: fp+0x1108 == 1.
        self.assertEqual(_words(self.main, 0x876A84, 2), [0x8F8238DC, 0x14400025])
        self.assertEqual(_words(self.main, 0x876A90, 3), [0x8FC31108, 0x24020001, 0x14620021])
        # fp+0x1108 is 1 iff the preset byte at 0x10002d is 1 ...
        self.assertEqual(_words(self.main, 0x8712C8, 3), [0x3C040010, 0x0C21F086, 0x3484002D])
        self.assertEqual(_words(self.main, 0x8712E0)[0], 0x14620003)
        self.assertEqual(_words(self.main, 0x8712EC)[0], 0xAFC21108)
        stores = [MAIN_BASE + 4 * i for i, word in enumerate(words)
                  if word & 0xFFE0FFFF == 0xAFC01108 and 0x870B78 <= MAIN_BASE + 4 * i < 0x87C218]
        self.assertEqual(stores, [0x870CE8, 0x8712EC])
        # ... and it is 1 in this build (packed ELF, segment at 0x100000).
        phoff, = struct.unpack_from("<I", self.raw, 0x1C)
        _type, offset, vaddr = struct.unpack_from("<III", self.raw, phoff)
        self.assertEqual(vaddr, 0x100000)
        self.assertEqual(self.raw[offset + 0x2D], 1)

    def test_messages(self):
        for off, text in ((-0x56A0, "NOT FOUND\n"), (-0x5690, "TOO BIG !\n"), (-0x5680, "LOADED\n")):
            self.assertEqual(_cstr(self.main, self.GP + off), text)


def named(files, backend):
    return {T.PREFIX[backend] + SLOTS[which][0]: data for which, data in files.items()}


@unittest.skipUnless(HAVE_EMU, "needs POPSTARTER_TEST_ELF, POPS_TEST_ELF and unicorn")
class Original(unittest.TestCase):
    """The original's loader, run as shipped, against pops_igr_skin_stage."""

    @classmethod
    def setUpClass(cls):
        from trace_original_pops_warmboot import core_image
        cls.core = bytes(core_image(os.environ["POPS_TEST_ELF"]))
        assert len(cls.core) == CORE_SIZE
        cls.emu = T.Emulator(cls.core)
        cls.runs = 0
        cls.outcomes = {}

    @classmethod
    def tearDownClass(cls):
        if os.environ.get("POPS_IGR_SKIN_COUNTS"):
            print("\nwhole-core comparisons: %d; (backend, file, outcome): %s"
                  % (cls.runs, sorted(cls.outcomes.items())), file=sys.stderr)
        if cls.runs == 45:   # every comparing test ran: each outcome was seen for each file
            for backend in (0, 1):
                for which in range(3):
                    for outcome in ("NOT FOUND", "TOO BIG", "LOADED"):
                        assert cls.outcomes.get((backend, which, outcome)), (backend, which, outcome)

    def count(self, backend, which, outcome):
        key = (backend, which, outcome)
        self.outcomes[key] = self.outcomes.get(key, 0) + 1

    def compare(self, files, backend, core=None, quiet=0):
        """files: {which: bytes}. Whole core, prints, return value, and
        nothing else in memory."""
        core = self.core if core is None else core
        r = self.emu.run(named(files, backend), backend=backend, core=core, quiet=quiet)
        type(self).runs += 1
        ours = bytearray(core)
        prints = []
        for which, (name, addr, _, _) in enumerate(SLOTS):
            prints.append("    Opening %s%s... " % (T.PREFIX[backend], name))
            if which not in files:
                prints.append("NOT FOUND\n")
                self.count(backend, which, "NOT FOUND")
                continue
            rc = stage(ours, which, files[which])
            self.assertIn(rc, (0, -errno.EFBIG))
            prints.append("LOADED\n" if rc == 0 else "TOO BIG !\n")
            self.count(backend, which, "LOADED" if rc == 0 else "TOO BIG")
            if rc:   # refused on its size alone: nothing zero-filled or read
                touched = [e for e in r["log"]
                           if (e[0] == "memset" and e[1] == addr and e[3]) or (e[0] == "read" and e[2] == addr)]
                self.assertEqual(touched, [], name)
        self.assertEqual(r["ret"], 1)
        self.assertEqual(r["prints"], [] if quiet else prints)
        self.assertEqual(r["outside"], [])
        self.assertEqual(r["open_fds"], [])
        self.assertTrue(r["core"] == bytes(ours), {k: len(v) for k, v in files.items()})
        opened = [e[2] for e in r["log"] if e[0] == "open"]
        self.assertEqual(opened, [T.PREFIX[backend] + s[0] for s in SLOTS])
        return r

    def test_boundary_sizes_on_both_backends(self):
        rng = random.Random(0x424F554E)
        sizes = [boundary_sizes(which) + [SLOTS[which][2] * 2] for which in range(3)]
        seen = set()
        for backend in (0, 1):
            for i in range(8):
                files = {}
                for which in range(3):
                    pool = sizes[which]
                    size = pool[(i + 2 * which) % len(pool)]
                    files[which] = rng.randbytes(size)
                    seen.add((backend, which, size))
                self.compare(files, backend)
        for backend in (0, 1):
            for which in range(3):
                for size in sizes[which]:
                    self.assertIn((backend, which, size), seen)

    def test_random_files_on_both_backends(self):
        rng = random.Random(0x52414E44)
        for backend in (0, 1):
            for _ in range(12):
                files = {}
                for which, (_, _, slot, biggest) in enumerate(SLOTS):
                    pick = rng.random()
                    if pick < 0.25:
                        continue                                     # absent
                    size = rng.randrange(0, biggest + 1) if pick < 0.85 else rng.randrange(biggest + 1, 2 * slot)
                    files[which] = rng.randbytes(size)
                self.compare(files, backend)

    def test_no_file_changes_nothing(self):
        for backend in (0, 1):
            r = self.compare({}, backend)
            self.assertEqual(r["core"], self.core)

    def test_slot_contents_are_not_checked(self):
        """Over a core of noise (no TIM2 anywhere) the files load the same."""
        rng = random.Random(0x4E4F4953)
        noise = rng.randbytes(CORE_SIZE)
        for backend in (0, 1):
            self.compare({BG: rng.randbytes(1000), NO: b"", YES: rng.randbytes(SLOTS[YES][3])},
                         backend, core=noise)

    def test_quiet_flag_only_silences(self):
        rng = random.Random(5)
        self.compare({BG: rng.randbytes(64), NO: rng.randbytes(9000)}, 0, quiet=1)

    def test_gates(self):
        files = named({BG: b"\x11" * 64}, 0)
        r = self.emu.run(files, abort=1)                             # already aborting
        self.assertEqual((r["ret"], r["log"], r["core"] == self.core), (0, [], True))
        r = self.emu.run(files, checked=0, dircheck=-666)            # POPS folder check fails
        self.assertEqual((r["ret"], r["log"], r["abort"]), (-666, [("dircheck",)], 1))
        self.assertEqual(r["core"], self.core)
        r = self.emu.run(files, checked=0, dircheck=1)               # passes: loads
        self.assertEqual((r["ret"], r["prints"][1]), (1, "LOADED\n"))
        r = self.emu.run(files, checked=1)                           # checked earlier: not called
        self.assertNotIn(("dircheck",), r["log"])
        self.assertEqual(r["ret"], 1)

    def test_a_short_read_leaves_what_arrived_then_zeros(self):
        """The original zero-fills, reads without checking, and zero-fills
        from the file's size on: staging the bytes that arrived is the same."""
        rng = random.Random(6)
        for which, limit, size in ((BG, 1000, 70000), (NO, 0, 500), (YES, 7, 7612)):
            data = rng.randbytes(size)
            r = self.emu.run(named({which: data}, 1), backend=1, read_limit=limit)
            ours = bytearray(self.core)
            self.assertEqual(stage(ours, which, data[:limit]), 0)
            self.assertTrue(r["core"] == bytes(ours), which)
            self.assertEqual(r["ret"], 1)

    def test_a_failed_size_query_is_not_copied(self):
        """Measured, and deliberately not reproduced: the original takes a
        negative lseek result as the size, so its last fill starts that many
        bytes below the slot. launcHER's reader leaves the slot alone."""
        for which, result in ((NO, -5), (YES, -1)):
            _, addr, slot, _ = SLOTS[which]
            r = self.emu.run(named({which: b"\x77" * 64}, 0), seek_end=result)
            want = bytearray(self.core)
            want[addr + result - CORE:addr - CORE + slot] = bytes(slot - result)
            self.assertTrue(r["core"] == bytes(want), which)
            self.assertEqual((r["ret"], r["prints"][2 * which + 1]), (1, "LOADED\n"))


class Source(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "launcher/src/handler_pops.c").read_text()
        self.body = self.src[self.src.index("int launchPOPS("):]

    def test_call_position(self):
        body = self.body
        call = "pops_stage_igr_skin((void *)stagedCore, plan.core_size, vcdDir);"
        self.assertEqual(body.count("pops_stage_igr_skin("), 1)
        at = body.index(call)
        # A bare statement: no result, nothing gates it, nothing fails on it.
        self.assertEqual(body[body.rindex("\n", 0, at) + 1:at], "  ")
        before = ["res = pops_core_patches_stage(", "pops_core_runtime_corrections_stage(",
                  "res = pops_resident_hook_guards(",
                  "res = pops_apply_always_on_pokes(",
                  'msg("POPS: POPStarter launch hooks failed: %d\\n", res);']
        after = ["res = pops_builtin_apply(builtinId, (void *)stagedCore",
                 "res = pops_apply_all_config_patches(",
                 "res = pops_resident_hook_recompiler_emit(",
                 "res = pops_stage_fix_files(",
                 "res = pops_apply_bios_shell_edits(",
                 "res = regionRead ? pops_apply_region(",
                 "res = pops_apply_reset_warmboot(",
                 "res = pops_apply_opcode_pass(",
                 "SifIopRebootBuffer("]
        for s in before:
            self.assertLess(body.index(s), at, s)
        for s in after:
            self.assertGreater(body.index(s), at, s)
        # The same folder as the all-games (root) TROJAN_n.BIN / PATCH_n.BIN.
        self.assertIn("res = pops_stage_fix_files((void *)stagedCore, plan.core_size, vcdDir,", body)
        fix = self.src[self.src.index("static int pops_stage_fix_files("):
                       self.src.index("/* Driver names within one role")]
        self.assertIn("const char *dirs[] = {vcdDir, titleDir};", fix)

    def test_reader_follows_the_original(self):
        begin = self.src.index("static void pops_stage_igr_skin(")
        reader = self.src[begin:self.src.index("/* POPStarter's XX. driver pair")]
        # tools/test_pops_fix_files.py compiles this slice of the file on
        # the host; the reader must stay outside it.
        self.assertNotIn("pops_igr_skin", self.src[self.src.index("static int readFullFile("):
                                                   self.src.index("/* Driver names within one role")])
        self.assertGreater(begin, self.src.index("/* Driver names within one role"))
        self.assertIn("for (int which = 0; which < POPS_IGR_SKIN_COUNT; ++which)", reader)
        self.assertIn('snprintf(path, sizeof(path), "%s%s", dir, slot->name)', reader)
        order = ["open(path, O_RDONLY)", "lseek(fd, 0, SEEK_END)",
                 "if (size > (off_t)slot->max_size)", "lseek(fd, 0, SEEK_SET)",
                 "read(fd, buffer + got, chunk)",
                 "pops_igr_skin_stage(stagedCore, coreSize, which, buffer, got)"]
        at = [reader.index(s) for s in order]
        self.assertEqual(at, sorted(at))
        for s in order:
            self.assertEqual(reader.count(s), 1, s)
        # Never fatal: nothing is returned and no launch error is raised.
        self.assertNotIn("return", reader)
        self.assertNotIn("msg(", reader)
        # Every path that opened the file closes it.
        self.assertEqual(reader.count("close(fd);"), 3)

    def test_build_lists(self):
        cmake = (ROOT / "launcher/CMakeLists.txt").read_text()
        self.assertEqual(cmake.count("../common/src/pops_igr_skin.c"), 1)
        ci = (ROOT / ".github/workflows/build.yml").read_text()
        self.assertEqual(ci.count("run: python tools/test_pops_igr_skin.py"), 1)

    def test_no_reference_bytes_in_the_repository(self):
        """The pure file holds the table and nothing else."""
        pure = (ROOT / "common/src/pops_igr_skin.c").read_text()
        self.assertLess(len(pure), 4000)
        self.assertNotIn("TIM2", pure)


if __name__ == "__main__":
    unittest.main()
