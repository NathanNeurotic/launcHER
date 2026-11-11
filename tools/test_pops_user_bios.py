#!/usr/bin/env python3
"""POPStarter r13's user BIOS.BIN and the gates its loader flags drive.

Native checks need nothing. The Original checks need POPSTARTER_TEST_ELF,
POPS_TEST_ELF and unicorn: the original's own code is run on the real core
(tools/trace_original_pops_user_bios.py) and launcHER's functions must leave
the same bytes and the same loader flags. Source checks pin where the launch
calls them. No original, POPS, BIOS or game byte is stored here. Nothing here
is a console run.
"""
import ctypes as c
import errno
import itertools
import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pops_features as F  # noqa: E402  (builds the host library)

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x200000
SIZE = 0x302E60
OSD_SITE = 0x2525B0
SKIPPED = 1  # POPS_MODE6_SKIPPED

FLAG_NAMES = ("bios_all", "bios_game", "osd_all_a", "osd_all_b", "osd_game_a", "osd_game_b",
              "osd_off")
REPLACED = ("bios_all", "bios_game")                       # gates of 0x2525b0's writers
KEEPS_SHELL = ("bios_all", "bios_game", "osd_all_b", "osd_game_b")  # shell edits, region


class Rom(c.Structure):
    """PopsUserRomState."""
    _fields_ = [(name, c.c_uint8) for name in FLAG_NAMES]


class Context(c.Structure):
    """PopsFixContext."""
    _fields_ = [("expected", c.c_uint32 * 39),
                ("video_expected", c.c_uint32 * 4),
                ("video_auto_disabled", c.c_uint8),
                ("video_custom_set", c.c_uint8),
                ("resident_entry", c.c_uint32),
                ("resident_expected", c.c_uint32 * 4),
                ("progressive_set", c.c_uint8)]


LIB = F.compile_shared_library()
P, Z = c.c_void_p, c.c_size_t
ROMP, CTXP = c.POINTER(Rom), c.POINTER(Context)
for name, args in (
        ("pops_user_rom_replaced", [ROMP]),
        ("pops_user_rom_keeps_shell", [ROMP]),
        ("pops_apply_bios_shell_edits", [P, Z]),
        ("pops_apply_bios_shell_edits_rom", [P, Z, ROMP]),
        ("pops_apply_region", [P, Z, c.c_int, c.c_uint8, c.c_int]),
        ("pops_apply_region_rom", [P, Z, c.c_int, c.c_uint8, c.c_int, ROMP]),
        ("pops_apply_undo_tokens", [P, Z, c.c_uint32]),
        ("pops_apply_undo_tokens_rom", [P, Z, c.c_uint32, ROMP]),
        ("pops_apply_compat_modes", [P, Z, c.c_uint8]),
        ("pops_apply_compat_modes_rom", [P, Z, c.c_uint8, ROMP]),
        ("pops_apply_all_config_patches", [P, Z, c.POINTER(F.PopsConfig)]),
        ("pops_apply_all_config_patches_rom", [P, Z, c.POINTER(F.PopsConfig), ROMP]),
        ("pops_fix_context_init_builtin", [CTXP, P, Z, c.c_uint16, c.c_uint8, c.c_uint8]),
        ("pops_fix_stage", [CTXP, P, Z, c.c_char_p, Z, c.c_uint, c.c_int]),
        ("pops_fix_stage_rom", [CTXP, P, Z, c.c_char_p, Z, c.c_uint, c.c_int, ROMP]),
        ("pops_builtin_apply", [c.c_uint16, P, Z, P, Z, c.c_uint32, P]),
        ("pops_config_parse_line", [c.POINTER(F.PopsConfig), c.c_char_p])):
    getattr(LIB, name).argtypes = args
    getattr(LIB, name).restype = c.c_int
LIB.pops_config_init.argtypes = [c.POINTER(F.PopsConfig)]
LIB.pops_config_init.restype = None

HAVE = bool(os.environ.get("POPSTARTER_TEST_ELF")) and bool(os.environ.get("POPS_TEST_ELF"))
if HAVE:
    try:
        import unicorn  # noqa: F401
        import trace_original_pops_user_bios as U
    except Exception:
        HAVE = False


def buf(data):
    return (c.c_uint8 * len(data)).from_buffer(data)


def rom(**flags):
    return Rom(**flags)


def flags_of(state):
    return {name: getattr(state, name) for name in FLAG_NAMES}


def put(core, address, value, width):
    core[address - BASE:address - BASE + width] = value.to_bytes(width, "little")


def get(core, address, width):
    return int.from_bytes(core[address - BASE:address - BASE + width], "little")


def synthetic(fill=0xA5):
    """A core-sized buffer of one byte with POPS's words at the mode 6 site
    and at the four sites the PAL change checks."""
    core = bytearray([fill]) * SIZE
    for address, value, width in ((OSD_SITE, 0x1BFC, 2), (0x21AF94, 2, 1), (0x502770, 0x8A3A2, 4),
                                  (0x23B018, 0x48, 1), (0x23B01C, 0x290, 2)):
        put(core, address, value, width)
    return core


def pristine_sites():
    """Zeroes plus the words the fix context and the compat modes check
    (the values tools/test_pops_fix_files.py uses)."""
    core = bytearray(SIZE)
    for address, value, width in ((0x210318, 0x8F828228, 4), (0x21032C, 0x1443FFFA, 4),
                                  (0x20083C, 0x0441000A, 4), (0x20085C, 0x1000FFFA, 4),
                                  (0x20DE9C, 0x0C0836EE, 4), (0x21AF70, 0x64, 1),
                                  (OSD_SITE, 0x1BFC, 2), (0x21AF94, 2, 1),
                                  (0x502770, 0x8A3A2, 4), (0x23B018, 0x48, 1),
                                  (0x23B01C, 0x290, 2)):
        put(core, address, value, width)
    return core


def patch(modes, slot=1):
    """A PATCH_n.BIN that only asks for compatibility modes (synthetic)."""
    header = bytearray(64)
    header[:8] = ("PATCH_%d\0" % slot).encode()
    struct.pack_into("<6I", header, 8, 1, 0x10001, 0, 0, 0, 0)
    header[32:37] = b"owned"
    header[56:56 + len(modes)] = bytes(modes)
    return bytes(header)


def changed(a, b, step=4096):
    """Offsets at which two equally long buffers differ."""
    for start in range(0, len(a), step):
        if a[start:start + step] != b[start:start + step]:
            for i in range(start, min(start + step, len(a))):
                if a[i] != b[i]:
                    yield i


def all_flag_sets():
    """Every combination of the seven flags (128)."""
    for bits in itertools.product((0, 1), repeat=len(FLAG_NAMES)):
        yield {name: bit for name, bit in zip(FLAG_NAMES, bits) if bit}


SINGLE_FLAG_SETS = [{}] + [{name: 1} for name in FLAG_NAMES] + [{"bios_all": 1, "bios_game": 1}]


class Native(unittest.TestCase):
    def test_state_layout_and_predicates(self):
        self.assertEqual(c.sizeof(Rom), 7)
        self.assertEqual(LIB.pops_user_rom_replaced(None), 0)
        self.assertEqual(LIB.pops_user_rom_keeps_shell(None), 0)
        for flags in all_flag_sets():
            state = rom(**flags)
            self.assertEqual(bool(LIB.pops_user_rom_replaced(c.byref(state))),
                             any(flags.get(n) for n in REPLACED), flags)
            self.assertEqual(bool(LIB.pops_user_rom_keeps_shell(c.byref(state))),
                             any(flags.get(n) for n in KEEPS_SHELL), flags)
        # The original tests each word with bnez: any nonzero value is "set".
        self.assertEqual(LIB.pops_user_rom_replaced(c.byref(rom(bios_game=2))), 1)
        self.assertEqual(LIB.pops_user_rom_keeps_shell(c.byref(rom(osd_all_b=0x80))), 1)

    def test_no_state_and_zero_state_are_the_functions_as_they_were(self):
        """The old names are the new ones with no state; all flags zero is the
        same bytes and the same result."""
        zero = rom()

        def same(old, new, *args, core=None):
            results = []
            for call in (lambda b: old(b, SIZE, *args), lambda b: new(b, SIZE, *args, None),
                         lambda b: new(b, SIZE, *args, c.byref(zero))):
                data = bytearray(core if core is not None else synthetic())
                results.append((call(buf(data)), bytes(data)))
            self.assertEqual(results[0], results[1], (old.__name__, args))
            self.assertEqual(results[0], results[2], (old.__name__, args))
            return results[0][0]

        self.assertEqual(same(LIB.pops_apply_bios_shell_edits, LIB.pops_apply_bios_shell_edits_rom), 0)
        for region, video, disabled in itertools.product(range(4), range(7), (0, 1)):
            same(LIB.pops_apply_region, LIB.pops_apply_region_rom, region, video, disabled)
        for tokens in (1 << 12, 1 << 13, 1 << 14, 7 << 12, 0x0FFF):
            self.assertEqual(same(LIB.pops_apply_undo_tokens, LIB.pops_apply_undo_tokens_rom, tokens), 0)
        for mask in list(range(0, 0x80)) + [0x80]:
            zero.osd_off = 0
            same(LIB.pops_apply_compat_modes, LIB.pops_apply_compat_modes_rom, mask,
                 core=pristine_sites())
        zero.osd_off = 0
        for lines in ((), (b"$COMPATIBILITY_0x06",), (b"$UNDO_COMPATIBILITY_CODES",),
                      (b"$UNDO_GAME_FIXES", b"$COMPATIBILITY_0x06", b"$NOBOOT"),
                      (b"$UNDO_LIBCRYPT_FIX", b"$COMPATIBILITY_0x04")):
            cfg = F.PopsConfig()
            LIB.pops_config_init(c.byref(cfg))
            for line in lines:
                self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), line), 0, line)
            out = []
            for state in (False, None, rom()):
                data = pristine_sites()
                if state is False:
                    rc = LIB.pops_apply_all_config_patches(buf(data), SIZE, c.byref(cfg))
                else:
                    rc = LIB.pops_apply_all_config_patches_rom(
                        buf(data), SIZE, c.byref(cfg), None if state is None else c.byref(state))
                out.append((rc, bytes(data)))
            self.assertEqual(out[0][0], 0, lines)
            self.assertEqual(out[0], out[1], lines)
            self.assertEqual(out[0], out[2], lines)

    def test_shell_edits_gate(self):
        for flags in all_flag_sets():
            core = synthetic()
            before = bytes(core)
            state = rom(**flags)
            self.assertEqual(LIB.pops_apply_bios_shell_edits_rom(buf(core), SIZE, c.byref(state)), 0)
            if any(flags.get(n) for n in KEEPS_SHELL):
                self.assertEqual(bytes(core), before, flags)
            else:
                self.assertEqual(core[0x263ED6 - BASE], 0x20, flags)
                self.assertEqual(get(core, 0x263D56, 2), 0x1000, flags)
                self.assertEqual(get(core, 0x263DB0, 4), 0, flags)
            self.assertEqual(flags_of(state), flags_of(rom(**flags)))  # read only
        # Arguments are rejected before the gate, with nothing written.
        state = rom(bios_all=1)
        self.assertEqual(LIB.pops_apply_bios_shell_edits_rom(None, SIZE, c.byref(state)), -errno.EINVAL)
        core = synthetic()
        self.assertEqual(LIB.pops_apply_bios_shell_edits_rom(buf(core), 0x263ED6 - BASE, c.byref(state)),
                         -errno.ERANGE)

    def test_region_table(self):
        """The measured table: a known licence keeps 0x2649a0; an unknown one
        keeps 0x264994..0x2649a3 and 0x20f6cc/d8/dc/e0; the rest is written."""
        bios_sites = [(0x264994, 4), (0x264998, 4), (0x26499C, 4), (0x2649A0, 4)]
        cd_sites = [(0x20F6CC, 1), (0x20F6D8, 1), (0x20F6DC, 1), (0x20F6E0, 1)]
        for region, video, disabled in itertools.product(range(4), (0, 2, 3, 4), (0, 1)):
            plain = synthetic()
            self.assertEqual(LIB.pops_apply_region_rom(buf(plain), SIZE, region, video, disabled, None), 0)
            for flags in SINGLE_FLAG_SETS[1:]:
                core = synthetic()
                state = rom(**flags)
                self.assertEqual(LIB.pops_apply_region_rom(buf(core), SIZE, region, video, disabled,
                                                           c.byref(state)), 0)
                expected = bytearray(plain)
                if any(flags.get(n) for n in KEEPS_SHELL):
                    kept = bios_sites[3:] if region else bios_sites + cd_sites
                    for address, width in kept:
                        expected[address - BASE:address - BASE + width] = b"\xA5" * width
                self.assertEqual(core, expected, (region, video, disabled, flags))
                # Whatever the flags: the POPS letter is written.
                self.assertNotEqual(core[0x2CBB72 - BASE], 0xA5)

    def test_undo_keeps_the_osd_word_under_a_user_bios_only(self):
        for tokens, flags in itertools.product((1 << 12, 1 << 13, 1 << 14, 7 << 12),
                                               SINGLE_FLAG_SETS):
            plain, core = synthetic(), synthetic()
            put(plain, OSD_SITE, 0x0648, 2)
            put(core, OSD_SITE, 0x0648, 2)
            self.assertEqual(LIB.pops_apply_undo_tokens(buf(plain), SIZE, tokens), 0)
            state = rom(**flags)
            self.assertEqual(LIB.pops_apply_undo_tokens_rom(buf(core), SIZE, tokens, c.byref(state)), 0)
            self.assertEqual(get(plain, OSD_SITE, 2), 0x1BFC)
            if any(flags.get(n) for n in REPLACED):
                self.assertEqual(get(core, OSD_SITE, 2), 0x0648, (tokens, flags))
                put(core, OSD_SITE, 0x1BFC, 2)
            self.assertEqual(core, plain, (tokens, flags))  # every other write is made

    def test_mode_6_gate(self):
        for flags in all_flag_sets():
            for start in (0x1BFC, 0x0648):
                core = pristine_sites()
                put(core, OSD_SITE, start, 2)
                before = bytes(core)
                state = rom(**flags)
                rc = LIB.pops_apply_compat_modes_rom(buf(core), SIZE, 1 << 5, c.byref(state))
                after = flags_of(state)
                if any(flags.get(n) for n in REPLACED):
                    self.assertEqual(rc, SKIPPED, flags)
                    self.assertEqual(bytes(core), before, flags)
                    self.assertEqual(after, flags_of(rom(**flags)))
                elif flags.get("osd_off"):
                    self.assertEqual(rc, 0, flags)
                    self.assertEqual(bytes(core), before, flags)
                    self.assertEqual(after, flags_of(rom(**flags)))
                else:
                    self.assertEqual(rc, 0, flags)
                    self.assertEqual(get(core, OSD_SITE, 2), 0x0648, flags)
                    self.assertEqual(after, dict(flags_of(rom(**flags)), osd_off=1))
        # A skipped mode 6 does not check its site either (it may be the
        # user's BIOS there); an applied one still does.
        for flags, expected in (({"bios_all": 1}, SKIPPED), ({"osd_off": 1}, 0), ({}, -errno.EINVAL)):
            core = pristine_sites()
            put(core, OSD_SITE, 0x1234, 2)
            state = rom(**flags)
            self.assertEqual(LIB.pops_apply_compat_modes_rom(buf(core), SIZE, 1 << 5, c.byref(state)),
                             expected, flags)
            self.assertEqual(get(core, OSD_SITE, 2), 0x1234)
        # The other modes do not read the state: same bytes with every flag set.
        everything = rom(**{name: 1 for name in FLAG_NAMES})
        for mask in range(1, 0x80):
            if mask & (1 << 5):
                continue
            plain, core = pristine_sites(), pristine_sites()
            a = LIB.pops_apply_compat_modes(buf(plain), SIZE, mask)
            b = LIB.pops_apply_compat_modes_rom(buf(core), SIZE, mask, c.byref(everything))
            self.assertEqual((a, plain), (b, core), mask)
        # With mode 6 skipped the rest of the mask is applied.
        plain, core = pristine_sites(), pristine_sites()
        self.assertEqual(LIB.pops_apply_compat_modes(buf(plain), SIZE, 1 << 3), 0)
        state = rom(bios_game=1)
        self.assertEqual(LIB.pops_apply_compat_modes_rom(buf(core), SIZE, (1 << 3) | (1 << 5),
                                                         c.byref(state)), SKIPPED)
        self.assertEqual(core, plain)

    def test_patch_file_mode_6_follows_the_same_gate(self):
        for flags in SINGLE_FLAG_SETS:
            core = pristine_sites()
            context, state = Context(), rom(**flags)
            self.assertEqual(LIB.pops_fix_context_init_builtin(c.byref(context), buf(core), SIZE, 0, 0, 0), 0)
            blob = patch((4, 6))
            rc = LIB.pops_fix_stage_rom(c.byref(context), buf(core), SIZE, blob, len(blob), 1, 0,
                                        c.byref(state))
            self.assertEqual(get(core, 0x21AF70, 1), 0, flags)  # mode 4 is applied either way
            if any(flags.get(n) for n in REPLACED):
                self.assertEqual((rc, get(core, OSD_SITE, 2), state.osd_off),
                                 (SKIPPED, 0x1BFC, flags.get("osd_off", 0)), flags)
            elif flags.get("osd_off"):
                self.assertEqual((rc, get(core, OSD_SITE, 2), state.osd_off), (0, 0x1BFC, 1), flags)
            else:
                self.assertEqual((rc, get(core, OSD_SITE, 2), state.osd_off), (0, 0x0648, 1), flags)
            # The context follows what was written, so the next file is accepted.
            blob = patch((4,), slot=2)
            self.assertEqual(LIB.pops_fix_stage_rom(c.byref(context), buf(core), SIZE, blob, len(blob),
                                                    2, 0, c.byref(state)), 0, flags)
        # No state: as before.
        plain, core = pristine_sites(), pristine_sites()
        one, two = Context(), Context()
        blob = patch((6,))
        for data, context in ((plain, one), (core, two)):
            self.assertEqual(LIB.pops_fix_context_init_builtin(c.byref(context), buf(data), SIZE, 0, 0, 0), 0)
        self.assertEqual(LIB.pops_fix_stage(c.byref(one), buf(plain), SIZE, blob, len(blob), 1, 0), 0)
        self.assertEqual(LIB.pops_fix_stage_rom(c.byref(two), buf(core), SIZE, blob, len(blob), 1, 0, None), 0)
        self.assertEqual(core, plain)
        self.assertEqual(bytes(one), bytes(two))

    def config(self, *lines):
        cfg = F.PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        for line in lines:
            self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), line), 0, line)
        return cfg

    def test_config_pass_with_the_state(self):
        base = pristine_sites()
        self.assertEqual(LIB.pops_apply_all_config_patches(buf(base), SIZE, c.byref(self.config())), 0)
        # Mode 6: written and remembered; skipped and reported under a BIOS.BIN.
        for flags, rc, word, off in (({}, 0, 0x0648, 1), ({"bios_all": 1}, SKIPPED, 0x1BFC, 0),
                                     ({"bios_game": 1}, SKIPPED, 0x1BFC, 0),
                                     ({"osd_off": 1}, 0, 0x1BFC, 1), ({"osd_game_b": 1}, 0, 0x0648, 1)):
            core, state = pristine_sites(), rom(**flags)
            self.assertEqual(LIB.pops_apply_all_config_patches_rom(
                buf(core), SIZE, c.byref(self.config(b"$COMPATIBILITY_0x06")), c.byref(state)), rc, flags)
            self.assertEqual((get(core, OSD_SITE, 2), state.osd_off), (word, off), flags)
            put(core, OSD_SITE, 0x1BFC, 2)
            self.assertEqual(core, base, flags)
        # $UNDO_*: the 0x2525b0 row only.
        for line in (b"$UNDO_COMPATIBILITY_CODES", b"$UNDO_GAME_FIXES", b"$UNDO_LIBCRYPT_FIX"):
            for flags in SINGLE_FLAG_SETS:
                plain, core, state = pristine_sites(), pristine_sites(), rom(**flags)
                put(plain, OSD_SITE, 0x0648, 2)
                put(core, OSD_SITE, 0x0648, 2)
                self.assertEqual(LIB.pops_apply_all_config_patches(buf(plain), SIZE, c.byref(self.config(line))), 0)
                self.assertEqual(LIB.pops_apply_all_config_patches_rom(
                    buf(core), SIZE, c.byref(self.config(line)), c.byref(state)), 0)
                kept = any(flags.get(n) for n in REPLACED)
                self.assertEqual(get(core, OSD_SITE, 2), 0x0648 if kept else 0x1BFC, (line, flags))
                put(core, OSD_SITE, 0x1BFC, 2)
                self.assertEqual(core, plain, (line, flags))
                self.assertEqual(flags_of(state), flags_of(rom(**flags)))  # $UNDO_ leaves gp+0x3704

    def test_noboot_leaves_a_user_bios_alone(self):
        """$NOBOOT/$BIOS is launcHER's own: 0x0648 -> 0x1bfc, except under a
        user BIOS.BIN. Without one it also clears the mode 6 flag."""
        for flags, word, off in (({}, 0x1BFC, 0), ({"osd_off": 1}, 0x1BFC, 0),
                                 ({"bios_all": 1}, 0x0648, 0), ({"bios_game": 1, "osd_off": 1}, 0x0648, 1),
                                 ({"osd_all_b": 1}, 0x1BFC, 0)):
            core, state = pristine_sites(), rom(**flags)
            put(core, OSD_SITE, 0x0648, 2)
            self.assertEqual(LIB.pops_apply_all_config_patches_rom(
                buf(core), SIZE, c.byref(self.config(b"$NOBOOT")), c.byref(state)), 0, flags)
            self.assertEqual((get(core, OSD_SITE, 2), state.osd_off), (word, off), flags)
        # No state: as before.
        core = pristine_sites()
        put(core, OSD_SITE, 0x0648, 2)
        self.assertEqual(LIB.pops_apply_all_config_patches(buf(core), SIZE, c.byref(self.config(b"$NOBOOT"))), 0)
        self.assertEqual(get(core, OSD_SITE, 2), 0x1BFC)

    def mode_6_entry(self):
        """The id of a built-in entry that runs compatibility mode 6."""
        plan = (c.c_uint8 * 4096)()
        for entry in range(1, 2000):
            core = pristine_sites()
            if LIB.pops_builtin_apply(entry, buf(core), SIZE, None, 0, 0, plan):
                continue
            if get(core, OSD_SITE, 2) == 0x0648:
                return entry
        self.fail("no built-in entry runs mode 6")

    def test_fix_context_accepts_the_osd_word_put_back(self):
        """The fix-file session starts after the user's commands: 0x2525b0 may
        hold POPS's own word again ($UNDO_*), or still (mode 6 not applied)."""
        context = Context()
        for modes, word, expected in ((0x20, 0x0648, 0), (0x20, 0x1BFC, 0), (0, 0x1BFC, 0),
                                      (0, 0x0648, -errno.EINVAL), (0x20, 0x1234, -errno.EINVAL),
                                      (0, 0x1234, -errno.EINVAL)):
            core = pristine_sites()
            put(core, OSD_SITE, word, 2)
            self.assertEqual(LIB.pops_fix_context_init_builtin(c.byref(context), buf(core), SIZE, 0, modes, 0),
                             expected, (modes, hex(word)))
        entry = self.mode_6_entry()
        plan = (c.c_uint8 * 4096)()
        for tokens in (0, 1 << 13, 1 << 14):
            core = pristine_sites()
            self.assertEqual(LIB.pops_builtin_apply(entry, buf(core), SIZE, None, 0, 0, plan), 0)
            self.assertEqual(LIB.pops_apply_undo_tokens(buf(core), SIZE, tokens), 0)
            self.assertEqual(get(core, OSD_SITE, 2), 0x1BFC if tokens else 0x0648)
            self.assertEqual(LIB.pops_fix_context_init_builtin(c.byref(context), buf(core), SIZE, entry, 0, 0),
                             0, tokens)
            # ... and the session it starts stages a file.
            blob = patch((4,))
            self.assertEqual(LIB.pops_fix_stage(c.byref(context), buf(core), SIZE, blob, len(blob), 1, 0),
                             0, tokens)


@unittest.skipUnless(HAVE, "POPSTARTER_TEST_ELF, POPS_TEST_ELF and unicorn are needed")
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = U.core_image()
        assert len(cls.core) == SIZE

    def state_after(self, flags_after):
        return {name: flags_after[name] for name in FLAG_NAMES}

    def test_shell_slice_with_every_flag_combination(self):
        count = 0
        for flags in all_flag_sets():
            expected = U.shell(self.core, flags)
            ours = bytearray(self.core)
            state = rom(**flags)
            self.assertEqual(LIB.pops_apply_bios_shell_edits_rom(buf(ours), SIZE, c.byref(state)), 0)
            self.assertEqual(ours, expected, flags)
            count += 1
        # The two words main never passes on but that sit beside them.
        for extra in ("abort", "game_dir_missing", "preset_osd_off"):
            ours = bytearray(self.core)
            self.assertEqual(LIB.pops_apply_bios_shell_edits_rom(buf(ours), SIZE, None), 0)
            self.assertEqual(ours, U.shell(self.core, {extra: 1}), extra)
            count += 1
        print("Original shell-edit slice 0x878f64..0x878fc4: %d flag cases, bytes equal" % count)

    PAL_SITES = ((0x21AF94, 1), (0x502770, 4), (0x23B018, 1), (0x23B01C, 2))

    def test_region_window_with_the_flags(self):
        """5 licences x force_pal x auto_disabled x selector x 9 flag sets.
        launcHER's inputs are (video mode, auto disabled): force_pal is
        $FORCEPAL, the selector cleared is $NOPAL. Two of the eight
        combinations (auto disabled with the selector still set) cannot be
        given to pops_apply_region; they differ for a European licence only,
        in the PAL change, and those four sites are left out there."""
        licences = ((b"Euro", 1), (b"Amer", 2), (b"of A", 2), (b"Inc.", 3), (b"????", 0))
        full = partial = 0
        for (licence, region), force_pal, disabled, selector, flags in itertools.product(
                licences, (0, 1), (0, 1), (0, 1), SINGLE_FLAG_SETS):
            expected = U.region(self.core, licence, force_pal, disabled, selector, flags)
            video = 2 if force_pal else (0 if selector else 3)
            ours = bytearray(self.core)
            state = rom(**flags)
            self.assertEqual(LIB.pops_apply_region_rom(buf(ours), SIZE, region, video, disabled,
                                                       c.byref(state)), 0)
            case = (licence, force_pal, disabled, selector, flags)
            if region == 1 and disabled and selector:
                for address, width in self.PAL_SITES:
                    put(ours, address, get(expected, address, width), width)
                partial += 1
            else:
                full += 1
            self.assertEqual(ours, expected, case)
        print("Original region window 0x879034..0x8795f0: %d cases byte-for-byte, %d more "
              "(European licence, auto disabled, selector set) outside the PAL sites" % (full, partial))

    def test_mode_dispatcher_with_every_flag_combination(self):
        """FUN_008dc2c4: mode 6 for all 128 combinations and both words the
        site can hold; the other modes with each flag."""
        count = 0
        for flags in all_flag_sets():
            for start in (0x1BFC, 0x0648):
                core = bytearray(self.core)
                put(core, OSD_SITE, start, 2)
                expected, after, messages = U.mode(core, 6, flags, quiet=0)
                ours = bytearray(core)
                state = rom(**flags)
                rc = LIB.pops_apply_compat_modes_rom(buf(ours), SIZE, 1 << 5, c.byref(state))
                self.assertEqual(ours, expected, (flags, start))
                self.assertEqual({k: bool(v) for k, v in flags_of(state).items()},
                                 {k: bool(v) for k, v in self.state_after(after).items()}, flags)
                notice = any(b"BIOS.BIN" in line for line in messages)
                self.assertEqual(rc, SKIPPED if notice else 0, (flags, messages))
                count += 1
        for number in (1, 2, 3, 4, 5, 7):
            plain = U.mode(self.core, number)[0]
            for name in FLAG_NAMES:
                self.assertEqual(U.mode(self.core, number, {name: 1})[0], plain, (number, name))
                ours = bytearray(self.core)
                state = rom(**{name: 1})
                self.assertEqual(LIB.pops_apply_compat_modes_rom(buf(ours), SIZE, 1 << (number - 1),
                                                                 c.byref(state)), 0)
                self.assertEqual(ours, plain, (number, name))
                count += 1
        print("Original mode dispatcher FUN_008dc2c4: %d cases, bytes, gp+0x3704 and notice equal" % count)

    BLOB_SITES = (0x2397D8, 0x239780, 0x239784)  # the original's own resident blob

    def test_parser_commands_with_the_flags(self):
        """$COMPATIBILITY_0x06 and the three $UNDO_ commands through the
        original's CHEATS.TXT section, one command per text, with each flag
        preset and both words at 0x2525b0, against launcHER's config pass.
        launcHER's pass also makes its own launch writes; those are taken
        from a run of the same pass with no command."""
        count = 0
        for command, flags, start in itertools.product(
                ("$COMPATIBILITY_0x06", "$UNDO_COMPATIBILITY_CODES", "$UNDO_GAME_FIXES",
                 "$UNDO_LIBCRYPT_FIX"), SINGLE_FLAG_SETS, (0x1BFC, 0x0648)):
            core = bytearray(self.core)
            put(core, OSD_SITE, start, 2)
            theirs, after = U.parser(command + "\n", core, flags)
            for address in self.BLOB_SITES:
                put(theirs, address, get(core, address, 4), 4)

            def ours(lines):
                cfg = F.PopsConfig()
                LIB.pops_config_init(c.byref(cfg))
                for line in lines:
                    self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), line), 0, line)
                data, state = bytearray(core), rom(**flags)
                rc = LIB.pops_apply_all_config_patches_rom(buf(data), SIZE, c.byref(cfg), c.byref(state))
                self.assertGreaterEqual(rc, 0, (lines, flags))
                return data, state

            base, _ = ours(())
            data, state = ours((command.encode(),))
            expected = bytearray(base)
            for i in changed(theirs, core):
                self.assertEqual(base[i], core[i], hex(BASE + i))  # no overlap with launch writes
                expected[i] = theirs[i]
            # A same-value write is invisible above; the site itself is compared outright.
            put(expected, OSD_SITE, get(theirs, OSD_SITE, 2), 2)
            self.assertEqual(data, expected, (command, flags, hex(start)))
            self.assertEqual(bool(state.osd_off), bool(after["osd_off"]), (command, flags))
            count += 1
        print("Original parser with loader flags: %d command/flag/word cases equal" % count)


class Source(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "launcher/src/handler_pops.c").read_text()
        self.body = self.src[self.src.index("int launchPOPS("):]

    def test_one_state_reaches_every_gated_stage(self):
        body = self.body
        declared = body.index("PopsUserRomState romState;")
        seeded = body.index("romState.osd_off = (builtinPlan.compat_modes & (1 << 5)) != 0;")
        calls = ["res = pops_apply_all_config_patches_rom((void *)stagedCore, plan.core_size, &cfg, &romState);",
                 "&romState, &fixContext);",
                 "res = pops_apply_bios_shell_edits_rom((void *)stagedCore, plan.core_size, &romState);",
                 "&romState)\n                   : 0;"]
        at = [body.index(text) for text in calls]
        self.assertEqual(at, sorted(at))
        self.assertLess(body.index("res = pops_builtin_apply(builtinId, (void *)stagedCore"), declared)
        self.assertLess(declared, seeded)
        self.assertLess(seeded, at[0])
        self.assertEqual(body.count("PopsUserRomState romState;"), 1)
        # The fix files are staged with the same state.
        self.assertIn("result = pops_fix_stage_rom(&context, stagedCore, coreSize, buffer, size,\n"
                      "                                       slot, !kind, rom);", self.src)
        self.assertNotIn("pops_fix_stage(", self.src)

    def test_state_struct_names_the_original_words(self):
        header = (ROOT / "common/include/pops_modes_patches.h").read_text()
        for field, word in (("bios_all", "gp+0x38a4"), ("bios_game", "gp+0x3b98"),
                            ("osd_all_a", "gp+0x343c"), ("osd_all_b", "gp+0x3430"),
                            ("osd_game_a", "gp+0x3878"), ("osd_game_b", "gp+0x344c"),
                            ("osd_off", "gp+0x3704")):
            line = [text for text in header.splitlines() if ("uint8_t %s;" % field) in text]
            self.assertEqual(len(line), 1, field)
            self.assertIn(word, line[0])


if __name__ == "__main__":
    unittest.main()
