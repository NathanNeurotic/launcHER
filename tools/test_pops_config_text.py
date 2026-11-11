#!/usr/bin/env python3
"""CHEATS.TXT commands and VMCDIR.TXT: launcHER's readers against POPStarter r13's own.

Native checks need nothing: they hold launcHER's reader
(pops_config_parse_text) to the table below, which is what the original's
command pass did with each text when it was run under emulation.

With POPSTARTER_TEST_ELF and Unicorn, the Original class runs that pass
again (tools/trace_original_pops_config_text.py: the original's own code
from 0x883aa8 to 0x89e884, on synthetic text) and requires, for the table's
texts and for seeded random texts, the same commands at the same offsets,
the same cheat codes stepped over, and the same numbers reaching the
position, compatibility-mode and game-id handlers.

The VMCDIR.TXT reader (FUN_008d4f84) is run the same way: which files it
takes, which it ignores, and the folder name it puts in POPS's two path
strings.

This is bounded emulation of two routines. It is not a POPS boot and not a
console test.
"""
import ctypes as c
import os
import random
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pops_features as F  # noqa: E402  (builds the host library)

HAVE_MAIN = bool(os.environ.get("POPSTARTER_TEST_ELF"))
try:
    import unicorn  # noqa: F401
    HAVE_UNICORN = True
except Exception:  # pragma: no cover - optional
    HAVE_UNICORN = False

LIB = F.compile_shared_library()
TRACE = c.CFUNCTYPE(None, c.c_void_p, c.c_size_t, c.c_char_p, c.c_int)
LIB.pops_config_init.argtypes = [c.POINTER(F.PopsConfig)]
LIB.pops_config_parse_text.argtypes = [c.POINTER(F.PopsConfig), c.c_char_p, c.c_size_t,
                                       c.c_uint32, TRACE, c.c_void_p]
LIB.pops_config_parse_text.restype = c.c_int
LIB.pops_config_parse_line.argtypes = [c.POINTER(F.PopsConfig), c.c_char_p]
LIB.pops_config_parse_line.restype = c.c_int
LIB.pops_config_parse_vmcdir.argtypes = [c.POINTER(F.PopsConfig), c.c_char_p, c.c_size_t]
LIB.pops_config_parse_vmcdir.restype = c.c_int
LIB.pops_config_load_vmcdir.argtypes = [c.POINTER(F.PopsConfig), c.c_char_p]
LIB.pops_config_load_vmcdir.restype = c.c_int
LIB.pops_config_discover.argtypes = [c.POINTER(F.PopsConfig), c.c_char_p, c.c_char_p]
LIB.pops_config_discover.restype = c.c_int

# Where the original's $XPOS_n and $YPOS_n copy their 16-bit value in POPS.
X_SITE, Y_SITE = 0x21B128, 0x21C18C
SOURCE = (ROOT / "common/src/pops_config.c").read_text(encoding="utf-8")

PLAIN = [
    "$SMOOTH", "$SCANLINES", "$SUBCDSTATUS", "$RESET_WARMBOOT", "$MUTE_CDDA", "$MUTE_VAB",
    "$CODECACHE_ADDON_0", "$CODECACHE_ADDON_1", "$CODECACHE_ADDON_2", "$RECOMPILER_ADDON_0",
    "$RECOMPILER_ADDON_1", "$RECOMPILER_ADDON_2", "$RECOMPILER_ADDON_3", "$RECOMPILER_ADDON_4",
    "$UNDO_COMPATIBILITY_CODES", "$UNDO_GAME_FIXES", "$UNDO_LIBCRYPT_FIX", "$UNDO_MUTE_CDDA",
    "$WIDESCREEN", "$ULTRA_WIDESCREEN", "$EYEFINITY", "$ROLLBACK", "$SET_TIMINGS",
    "$BREAKPOINT0", "$BREAKPOINT1", "$NOVMC0", "$NOVMC1", "$NOPAD0", "$NOPAD1", "$D2LS",
    "$D2LS_ALT", "$IGR0", "$IGR1", "$IGR2", "$IGR3", "$IGR4", "$IGR5", "$NOIGR", "$MUTE_ALL",
    "$NOPAL", "$FORCEPAL", "$CACHE1", "$FAKELC", "$SAFEMODE", "$SAFEMODE2", "$NOSAFEMODE",
    "$HDTVFIX", "$NOHDTVFIX", "$LOAD_PADMAN", "$KILL_PADMAN", "$ORIGINAL_OPCODES", "$480P",
]
NUMBERED = ["$DX_", "$DY_", "$MAGH_", "$MAGV_", "$DW_", "$DH_", "$LEFTADJ_", "$VCDID_",
            "$XPOS_", "$YPOS_", "$ZPOS_", "$DWSTRETCH_", "$DWCROP_", "$USBDELAY_"]
HEXED = ["$PAD0ID_0X", "$PAD1ID_0X", "$PAD2ID_0X", "$COMPATIBILITY_0X"]
LAUNCHER_ONLY = ["$NOBOOT", "$BIOS", "MODE 3", "$MODE 4", "$MODE5", "7", "$DITHER_OFF",
                 "$FASTMIPS", "$PAL2NTSC", "$NTSC2PAL", "$FIX_ALL", "$480i"]
CODES = ["$80012345 1234", "$30112345 0012", "$D0012345 1234", "$50000102 0001",
         "$C0012345 0000", "$20012345 12345678", "$10012345 12345678", "$00012345 12345678",
         "$S0100234 12345678", "$T0100023 12345678", "$=0012345 12345678",
         "$!1012345 12345678", "$80212345 1234", "$E0012345 1234"]
MODE_TOKEN = re.compile(r"(?:^|[\s\0])(?:\$?MODE\s*[0-9]|[1-8](?:$|[\s\0]))")
ENDS = ["\r\n", "\n", " ", "$", "\0", ""]
NOT_ENDS = ["\t", "X", "_", "2", "#", ";", ",", "\x80"]


# VMCDIR.TXT: file contents and the folder name the original's reader
# (FUN_008d4f84) put in POPS's path strings, None where it ignored the file
# and changed nothing. From its run under emulation.
VMC_EXPECTED = [
    (b"", b""), (b"SAVES", b"SAVES"), (b"saves", b"saves"), (b" SAVES ", b" SAVES "),
    (b"\tSAVES", b"\tSAVES"), (b"SA VES", b"SA VES"), (b"#SAVES", b"#SAVES"), (b" ", b" "),
    (b".", b"."), (b"..", b".."), (b"\xe9t\xe9", b"\xe9t\xe9"),
    # A line end anywhere, also after the name, and the file is ignored.
    (b"SAVES\r\n", None), (b"SAVES\n", None), (b"SAVES\r", None), (b"SAVES\r\nJUNK", None),
    (b"SAVES\nJUNK", None), (b"SAVES\r\n\r\n", None), (b"\r\n", None), (b"\n", None),
    (b"A/B", None), (b"A\\B", None), (b"A:B", None), (b"A\nB/C", None),
    # A NUL ends the name, but the bytes after it are still looked at.
    (b"SAVES\0JUNK", b"SAVES"), (b"\0", b""), (b"A\0/B", None), (b"A\0\nB", None),
    (b"A\0:B", None), (b"\0/", None), (b"A\0\0\\", None),
    # 103 bytes are taken, 104 are not: the file's size, not the name's.
    (b"x" * 102, b"x" * 102), (b"x" * 103, b"x" * 103), (b"x" * 104, None), (b"x" * 300, None),
    (b"SAVES\0" + b"x" * 97, b"SAVES"), (b"SAVES\0" + b"x" * 98, None),
    (b"SAVES\0" + b"x" * 200, None), (b"\0" + b"x" * 102, b""), (b"\0" + b"x" * 103, None),
]
VMC_KEEP = b"Keep"


def launcher_vmcdir(data):
    """launcHER's reader on one file's bytes: the folder name, or None."""
    cfg = F.PopsConfig()
    LIB.pops_config_init(c.byref(cfg))
    cfg.vmc_dir = VMC_KEEP
    taken = LIB.pops_config_parse_vmcdir(c.byref(cfg), bytes(data), len(data))
    if not taken:
        assert (cfg.vmc_dir, cfg.vmc_dir_set) == (VMC_KEEP, 0), data
        return None
    assert (taken, cfg.vmc_dir_set) == (1, 1), data
    return cfg.vmc_dir


def original_vmcdir(data, game=None):
    """The original's reader on one file's bytes: (folder name or None, the
    path it opened)."""
    import trace_original_pops_config_text as T
    before = {T.VMCDIR_PATHS[0]: b"pfs1:/TITLE/".ljust(0x80, b"\0"),
              T.VMCDIR_PATHS[1]: b"pfs1:/TITLE/SLOT%d.VMC".ljust(0x80, b"\0")}
    run = T.vmcdir(data, game, before)
    if run.result != 1:
        assert run.result == 0 and not run.paths, (data, run)
        return None, run.opens
    folder, card = run.paths[T.VMCDIR_PATHS[0]], run.paths[T.VMCDIR_PATHS[1]]
    assert folder.startswith(b"pfs1:/") and folder.endswith(b"/"), (data, run)
    assert card == folder + b"SLOT%d.VMC", (data, run)
    return folder[6:-1], run.opens


def random_vmcdir(rng):
    kind = rng.randrange(8)
    if kind == 0:
        length = rng.choice((100, 101, 102, 103, 104, 105, 127, 128, 200))
    else:
        length = rng.randrange(0, 24)
    alphabet = b"SAVESaves_ -.#\t0123456789\xe9"
    if kind in (1, 2):
        alphabet += b"\r\n/\\:\0"
    data = bytearray(rng.choice(alphabet) for _ in range(length))
    if kind == 3 and data:
        data[rng.randrange(len(data))] = rng.choice(b"\r\n/\\:\0")
    if kind == 4:
        data += rng.choice((b"\r\n", b"\n", b"\r", b"\0", b"\0\n", b"/"))
    return bytes(data)


def launcher(text, number=0, cfg=None):
    """launcHER's reader on one text: (result, cfg, commands, cheat codes)."""
    data = text.encode("latin-1") if isinstance(text, str) else bytes(text)
    if cfg is None:
        cfg = F.PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
    commands, codes = [], []

    def trace(_, offset, name, effect):
        if name is None:
            codes.append((offset, effect))
        else:
            commands.append((offset, name.decode("ascii"), bool(effect)))

    result = LIB.pops_config_parse_text(c.byref(cfg), data, len(data), number, TRACE(trace), None)
    return result, cfg, commands, codes


def original(text, number=0):
    import trace_original_pops_config_text as T
    scan = T.scan_commands(text, usb_delay=USB_BEFORE, number=number)
    return scan, [(offset, name, effects > 0) for offset, name, _, effects in scan.events], scan.skips


def random_text(rng):
    parts = []
    for _ in range(rng.randrange(1, 9)):
        kind = rng.randrange(12)
        if kind < 3:
            piece = rng.choice(PLAIN)
        elif kind < 6:
            piece = rng.choice(NUMBERED) + "".join(
                rng.choice("0123456789") for _ in range(rng.choice((0, 1, 1, 2, 3, 4, 5, 6))))
        elif kind == 6:
            piece = rng.choice(HEXED) + "".join(
                rng.choice("0123456789ABCDEFabcdefGx ") for _ in range(rng.choice((2, 2, 2, 1, 3))))
        elif kind == 7:
            piece = rng.choice(CODES)
        elif kind == 8:
            piece = rng.choice(LAUNCHER_ONLY)
        elif kind == 9:
            piece = rng.choice(PLAIN + NUMBERED + HEXED)
            piece = piece[:rng.randrange(1, len(piece) + 1)]
        elif kind == 10:
            piece = rng.choice(("#", ";", "# ", "; ", "//", "x", "$", "$$", "\t"))
        else:
            piece = "".join(rng.choice("$ \r\n\t\0AZaz09_#;XPOS") for _ in range(rng.randrange(1, 6)))
        if rng.randrange(4) == 0:
            piece = piece.lower()
        if rng.randrange(8) == 0 and len(piece) > 2:
            at = rng.randrange(len(piece))
            piece = piece[:at] + rng.choice("$ X0\t") + piece[at + 1:]
        parts.append(piece + (rng.choice(ENDS) if rng.randrange(5) else rng.choice(NOT_ENDS)))
    return "".join(parts)


FIXED = [
    # A command is taken at any '$', whatever precedes it; '$' also ends one.
    "$SMOOTH\r\n", "$smooth\r\n", "#$SMOOTH\r\n", "; $SMOOTH\r\n", "x$SMOOTH\r\n",
    "$SMOOTH$SCANLINES\r\n", "$SMOOTH\t$SCANLINES\r\n", "$SMOOTH", "$SMOOTH\0$SCANLINES",
    "$SMOOTHX $SCANLINES",
    # $ORIGINAL_OPCODES: the terminator is tested at column 19.
    "$ORIGINAL_OPCODES\r\n", "$ORIGINAL_OPCODES\n$SMOOTH\n", "$ORIGINAL_OPCODES\r\n$SMOOTH\r\n",
    "$ORIGINAL_OPCODESXY ", "$ORIGINAL_OPCODES", "$ORIGINAL_OPCODES\n", "$ORIGINAL_OPCODES $SMOOTH ",
    "$VCDID_12$SMOOTH", "$VCDID_12345 ", "$VCDID_0 $VCDID_7 $VCDID_8 ", "$VCDID_ ", "$VCDID_1Q ",
    "$COMPATIBILITY_0X05\r\n", "$COMPATIBILITY_0x5\r\n", "$COMPATIBILITY_0X5G ",
    "$COMPATIBILITY_0X\r\n", "$COMPATIBILITY_0X08 ", "$COMPATIBILITY_0XFF ", "$COMPATIBILITY_0x0a ",
    "$SUBCDSTATUS $COMPATIBILITY_0X01 $COMPATIBILITY_0X04 ",
    # Cheat codes are stepped over, with whatever their columns hold.
    "$80012345 1234\r\n$SMOOTH", "$20012345 00$SMOOTH\n$SCANLINES", "$C0012345 0000$SMOOTH",
    "$D0012345 1234 $SMOOTH", "$50000102 0001$SMOOTH", "$S0100234 12345678 $SMOOTH",
    "$T0100023 12345678 $SMOOTH", "$=0012345 12345678 $SMOOTH", "$!1012345 12345678$SMOOTH",
    "$80212345 1234\r\n", "$30012345 12$NOPAL  ",
    "$DX_1 $DX_2 $DY_3", "$DX_ ", "$DX_Q", "$DX_123456 ", "$DX_12Q ", "$DX_Q $DX_1 ",
    "$DX_1 $DY_2 $MAGH_3 $MAGV_4 $DW_5 $DH_6 ",
    # $XPOS_ / $YPOS_ and the shared number temporary.
    "$XPOS_-15 ", "$XPOS_70000 $XPOS_5 $XPOS_6 ", "$ZPOS_5 ", "$XPOS_123456 ", "$XPOS_12Q ",
    "$XPOS_5 $XPOS_Q ", "$XPOS_Q $XPOS_5 ", "$YPOS_6 ", "$LEFTADJ_12 $XPOS_Q ",
    "$COMPATIBILITY_0X21 $XPOS_ $YPOS_ ", "$XPOS_70000 $YPOS_ ", "$ZPOS_44 $YPOS_ ",
    "$DWSTRETCH_31 $XPOS_ ", "$DWCROP_32 $XPOS_ ", "$LEFTADJ_300 $XPOS_ ", "$PAD0ID_0X41 $XPOS_ ",
    "$DX_31 $XPOS_ ", "$VCDID_77 $XPOS_ ",
    "$PAD0ID_0X41 $PAD1ID_0XZZ $PAD2ID_0X41 ", "$PAD0ID_0X41X", "$PAD0ID_0X4 ", "$PAD1ID_0Xaf ",
    "$480p ", "$480P ", "$480i ", "$480PX ", "$480P $480P ",
    # Only the first of $SAFEMODE / $SAFEMODE2 counts; $NOSAFEMODE needs one.
    "$SAFEMODE $SAFEMODE2 $SAFEMODE ", "$SAFEMODE2 $SAFEMODE ",
    "$SAFEMODE $NOSAFEMODE $SAFEMODE2 ", "$NOSAFEMODE ",
    # launcHER's own tokens are nothing to the original.
    "$MODE 3\n", "MODE 3\n", "$NOBOOT\n", "$DITHER_OFF $FIX_ALL 7\n",
    "$LEFTADJ_0 $LEFTADJ_256 $LEFTADJ_12 ", "$LEFTADJ_1234 ", "$LEFTADJ_ ",
    "$DWSTRETCH_12345 ", "$DWCROP_Q", "$DWSTRETCH_100 $DWCROP_9999$SMOOTH",
    "$IGR6 ", "$IGR0X", "$IGR3 ", "$NOIGR ", "$D2LS $D2LS_ALT ", "$NOPAD0 $NOPAD1 $NOPAD2 ",
    # No line is too long, and there are no comments.
    "$80001234 5678" + " " * 300 + "$SMOOTH",
    "# " + "x" * 300 + " $SCANLINES\r\n; $NOPAL",
    "\r\n".join(PLAIN) + "\r\n",
    "".join(PLAIN),
    "\t".join(PLAIN) + "\t",
    # $USBDELAY_: exactly one digit and a terminator; the last one wins.
    "$USBDELAY_5", "$USBDELAY_5 ", "$USBDELAY_12 ", "$USBDELAY_ ", "$USBDELAY_A ", "$USBDELAY_5\t",
    "$USBDELAY_5$SMOOTH", "$usbdelay_9\r\n", "$USBDELAY5 ", "$USBDELAY_0 ", "$USBDELAY_3 $USBDELAY_8 ",
    "$LEFTADJ_12 $USBDELAY_7 $XPOS_Q ", "$USBDELAY_7 $XPOS_Q ", "$USBDELAY_ 5 ", "$USBDELAY_05 ",
    "x$USBDELAY_4\n", "#$USBDELAY_6\n", "$USBDELAY_-1 ", "$USBDELAY_9\0", "$USBDELAY_2 $USBDELAY_44 ",
]

# What the byte at 0x100017 holds before the original's pass in these tests:
# nothing the $USBDELAY_ handler can write (it writes one digit, 0..9).
USB_BEFORE = 0xEE
# The $USBDELAY_ texts above: the digit the original left in 0x100017, or
# None where it left the byte alone.
USB_EXPECTED = {
    "$USBDELAY_5": 5, "$USBDELAY_5 ": 5, "$USBDELAY_12 ": None, "$USBDELAY_ ": None,
    "$USBDELAY_A ": None, "$USBDELAY_5\t": None, "$USBDELAY_5$SMOOTH": 5, "$usbdelay_9\r\n": 9,
    "$USBDELAY5 ": None, "$USBDELAY_0 ": 0, "$USBDELAY_3 $USBDELAY_8 ": 8,
    "$LEFTADJ_12 $USBDELAY_7 $XPOS_Q ": 7, "$USBDELAY_7 $XPOS_Q ": 7, "$USBDELAY_ 5 ": None,
    "$USBDELAY_05 ": None, "x$USBDELAY_4\n": 4, "#$USBDELAY_6\n": 6, "$USBDELAY_-1 ": None,
    "$USBDELAY_9\0": 9, "$USBDELAY_2 $USBDELAY_44 ": 2,
}

# What the original's pass did with each FIXED text, in the same order:
# (commands [(offset, name, it changed something)], cheat codes [(offset, columns)]).
EXPECTED = [
    ([(0, '$SMOOTH', True)], []),
    ([(0, '$SMOOTH', True)], []),
    ([(1, '$SMOOTH', True)], []),
    ([(2, '$SMOOTH', True)], []),
    ([(1, '$SMOOTH', True)], []),
    ([(0, '$SMOOTH', True), (7, '$SCANLINES', True)], []),
    ([(8, '$SCANLINES', True)], []),
    ([(0, '$SMOOTH', True)], []),
    ([(0, '$SMOOTH', True), (8, '$SCANLINES', True)], []),
    ([(9, '$SCANLINES', True)], []),
    ([(0, '$ORIGINAL_OPCODES', True)], []),
    ([(18, '$SMOOTH', True)], []),
    ([(0, '$ORIGINAL_OPCODES', True), (19, '$SMOOTH', True)], []),
    ([(0, '$ORIGINAL_OPCODES', True)], []),
    ([(0, '$ORIGINAL_OPCODES', True)], []),
    ([(0, '$ORIGINAL_OPCODES', True)], []),
    ([(18, '$SMOOTH', True)], []),
    ([(0, '$VCDID_', True), (9, '$SMOOTH', True)], []),
    ([(0, '$VCDID_', False)], []),
    ([(0, '$VCDID_', True), (9, '$VCDID_', True)], []),
    ([(0, '$VCDID_', False)], []),
    ([(0, '$VCDID_', False)], []),
    ([(0, '$COMPATIBILITY_0X', True)], []),
    ([(0, '$COMPATIBILITY_0X', False)], []),
    ([(0, '$COMPATIBILITY_0X', False)], []),
    ([(0, '$COMPATIBILITY_0X', False)], []),
    ([(0, '$COMPATIBILITY_0X', True)], []),
    ([(0, '$COMPATIBILITY_0X', True)], []),
    ([(0, '$COMPATIBILITY_0X', True)], []),
    ([(0, '$SUBCDSTATUS', True), (13, '$COMPATIBILITY_0X', True), (33, '$COMPATIBILITY_0X', True)],
    []),
    ([(16, '$SMOOTH', True)], [(0, 14)]),
    ([(20, '$SCANLINES', True)], [(0, 18)]),
    ([(14, '$SMOOTH', True)], []),
    ([(15, '$SMOOTH', True)], [(0, 14)]),
    ([(14, '$SMOOTH', True)], [(0, 14)]),
    ([(19, '$SMOOTH', True)], [(0, 18)]),
    ([(19, '$SMOOTH', True)], [(0, 18)]),
    ([(19, '$SMOOTH', True)], [(0, 18)]),
    ([(18, '$SMOOTH', True)], [(0, 18)]),
    ([], []),
    ([(12, '$NOPAL', True)], []),
    ([(0, '$DX_', True), (12, '$DY_', True)], []),
    ([(0, '$DX_', False)], []),
    ([(0, '$DX_', False)], []),
    ([(0, '$DX_', False)], []),
    ([(0, '$DX_', False)], []),
    ([(0, '$DX_', False), (6, '$DX_', True)], []),
    ([(0, '$DX_', True), (6, '$DY_', True), (12, '$MAGH_', True), (20, '$MAGV_', True), (28, '$DW_',
    True), (34, '$DH_', True)], []),
    ([(0, '$?POS_', True)], []),
    ([(0, '$?POS_', False), (12, '$?POS_', True), (20, '$?POS_', False)], []),
    ([(0, '$?POS_', False)], []),
    ([(0, '$?POS_', True)], []),
    ([(0, '$?POS_', True)], []),
    ([(0, '$?POS_', True), (8, '$?POS_', False)], []),
    ([(0, '$?POS_', True), (8, '$?POS_', False)], []),
    ([(0, '$?POS_', True)], []),
    ([(0, '$LEFTADJ_', True), (12, '$?POS_', True)], []),
    ([(0, '$COMPATIBILITY_0X', True), (20, '$?POS_', True), (27, '$?POS_', True)], []),
    ([(0, '$?POS_', False), (12, '$?POS_', False)], []),
    ([(0, '$?POS_', False), (9, '$?POS_', True)], []),
    ([(0, '$DWSTRETCH_', True), (14, '$?POS_', True)], []),
    ([(0, '$DWCROP_', True), (11, '$?POS_', True)], []),
    ([(0, '$LEFTADJ_', False), (13, '$?POS_', True)], []),
    ([(0, '$PAD', True), (13, '$?POS_', True)], []),
    ([(0, '$DX_', True), (7, '$?POS_', True)], []),
    ([(0, '$VCDID_', True), (10, '$?POS_', True)], []),
    ([(0, '$PAD', True), (13, '$PAD', False)], []),
    ([], []),
    ([(0, '$PAD', False)], []),
    ([(0, '$PAD', True)], []),
    ([(0, '$480', True)], []),
    ([(0, '$480', True)], []),
    ([], []),
    ([], []),
    ([(0, '$480', True), (6, '$480', True)], []),
    ([(0, '$SAFEMODE', True)], []),
    ([(0, '$SAFEMODE2', True)], []),
    ([(0, '$SAFEMODE', True), (10, '$NOSAFEMODE', True), (22, '$SAFEMODE2', True)], []),
    ([], []),
    ([], []),
    ([], []),
    ([], []),
    ([], []),
    ([(0, '$LEFTADJ_', False), (11, '$LEFTADJ_', False), (24, '$LEFTADJ_', True)], []),
    ([(0, '$LEFTADJ_', False)], []),
    ([(0, '$LEFTADJ_', False)], []),
    ([(0, '$DWSTRETCH_', False)], []),
    ([(0, '$DWCROP_', False)], []),
    ([(0, '$DWSTRETCH_', True), (15, '$DWCROP_', True), (27, '$SMOOTH', True)], []),
    ([], []),
    ([], []),
    ([(0, '$IGR3', True)], []),
    ([(0, '$NOIGR', True)], []),
    ([(0, '$D2LS', True), (6, '$D2LS_ALT', True)], []),
    ([(0, '$NOPAD0', True), (8, '$NOPAD1', True)], []),
    ([(314, '$SMOOTH', True)], [(0, 14)]),
    ([(303, '$SCANLINES', True), (317, '$NOPAL', True)], []),
    ([(0, '$SMOOTH', True), (9, '$SCANLINES', True), (21, '$SUBCDSTATUS', True), (35,
    '$RESET_WARMBOOT', True), (52, '$MUTE_CDDA', True), (64, '$MUTE_VAB', True), (75,
    '$CODECACHE_ADDON_0', True), (95, '$CODECACHE_ADDON_1', True), (115, '$CODECACHE_ADDON_2',
    True), (135, '$RECOMPILER_ADDON_0', True), (156, '$RECOMPILER_ADDON_1', True), (177,
    '$RECOMPILER_ADDON_2', True), (198, '$RECOMPILER_ADDON_3', True), (219, '$RECOMPILER_ADDON_4',
    True), (240, '$UNDO_COMPATIBILITY_CODES', True), (267, '$UNDO_GAME_FIXES', True), (285,
    '$UNDO_LIBCRYPT_FIX', True), (305, '$UNDO_MUTE_CDDA', True), (322, '$WIDESCREEN', True), (335,
    '$ULTRA_WIDESCREEN', True), (354, '$EYEFINITY', True), (366, '$ROLLBACK', True), (377,
    '$SET_TIMINGS', True), (391, '$BREAKPOINT0', True), (405, '$BREAKPOINT1', True), (419,
    '$NOVMC0', True), (428, '$NOVMC1', True), (437, '$NOPAD0', True), (446, '$NOPAD1', True), (455,
    '$D2LS', True), (462, '$D2LS_ALT', True), (473, '$IGR0', True), (480, '$IGR1', True), (487,
    '$IGR2', True), (494, '$IGR3', True), (501, '$IGR4', True), (508, '$IGR5', True), (515,
    '$NOIGR', True), (523, '$MUTE_ALL', True), (534, '$NOPAL', True), (542, '$FORCEPAL', True),
    (553, '$CACHE1', True), (562, '$FAKELC', True), (571, '$SAFEMODE', True), (594, '$NOSAFEMODE',
    True), (607, '$HDTVFIX', True), (617, '$NOHDTVFIX', True), (629, '$LOAD_PADMAN', True), (643,
    '$KILL_PADMAN', True), (657, '$ORIGINAL_OPCODES', True), (676, '$480', True)], []),
    ([(0, '$SMOOTH', True), (7, '$SCANLINES', True), (17, '$SUBCDSTATUS', True), (29,
    '$RESET_WARMBOOT', True), (44, '$MUTE_CDDA', True), (54, '$MUTE_VAB', True), (63,
    '$CODECACHE_ADDON_0', True), (81, '$CODECACHE_ADDON_1', True), (99, '$CODECACHE_ADDON_2', True),
    (117, '$RECOMPILER_ADDON_0', True), (136, '$RECOMPILER_ADDON_1', True), (155,
    '$RECOMPILER_ADDON_2', True), (174, '$RECOMPILER_ADDON_3', True), (193, '$RECOMPILER_ADDON_4',
    True), (212, '$UNDO_COMPATIBILITY_CODES', True), (237, '$UNDO_GAME_FIXES', True), (253,
    '$UNDO_LIBCRYPT_FIX', True), (271, '$UNDO_MUTE_CDDA', True), (286, '$WIDESCREEN', True), (297,
    '$ULTRA_WIDESCREEN', True), (314, '$EYEFINITY', True), (324, '$ROLLBACK', True), (333,
    '$SET_TIMINGS', True), (345, '$BREAKPOINT0', True), (357, '$BREAKPOINT1', True), (369,
    '$NOVMC0', True), (376, '$NOVMC1', True), (383, '$NOPAD0', True), (390, '$NOPAD1', True), (397,
    '$D2LS', True), (402, '$D2LS_ALT', True), (411, '$IGR0', True), (416, '$IGR1', True), (421,
    '$IGR2', True), (426, '$IGR3', True), (431, '$IGR4', True), (436, '$IGR5', True), (441,
    '$NOIGR', True), (447, '$MUTE_ALL', True), (456, '$NOPAL', True), (462, '$FORCEPAL', True),
    (471, '$CACHE1', True), (478, '$FAKELC', True), (485, '$SAFEMODE', True), (504, '$NOSAFEMODE',
    True), (515, '$HDTVFIX', True), (523, '$NOHDTVFIX', True), (533, '$LOAD_PADMAN', True), (545,
    '$KILL_PADMAN', True), (574, '$480', True)], []),
    ([], []),
    ([(0, '$USBDELAY_', True)], []),
    ([(0, '$USBDELAY_', True)], []),
    ([], []),
    ([], []),
    ([], []),
    ([], []),
    ([(0, '$USBDELAY_', True), (11, '$SMOOTH', True)], []),
    ([(0, '$USBDELAY_', True)], []),
    ([], []),
    ([(0, '$USBDELAY_', True)], []),
    ([(0, '$USBDELAY_', True), (12, '$USBDELAY_', True)], []),
    ([(0, '$LEFTADJ_', True), (12, '$USBDELAY_', True), (24, '$?POS_', True)], []),
    ([(0, '$USBDELAY_', True), (12, '$?POS_', True)], []),
    ([], []),
    ([], []),
    ([(1, '$USBDELAY_', True)], []),
    ([(1, '$USBDELAY_', True)], []),
    ([], []),
    ([(0, '$USBDELAY_', True)], []),
    ([(0, '$USBDELAY_', True)], []),
]


def position_writes(scan):
    """(x, y) the original copied to POPS, None for none."""
    out = {X_SITE: None, Y_SITE: None}
    for name, address, data in scan.calls:
        if name == "memcpy" and address in out and len(data) == 2:
            out[address] = int.from_bytes(data, "little")
    return out[X_SITE], out[Y_SITE]


def launcher_positions(cfg):
    return (cfg.display_x if cfg.display_mask & 1 else None,
            cfg.display_y if cfg.display_mask & 2 else None)


def compat_modes(commands, calls):
    """The modes FUN_008dc2c4 applies for the pass's calls: 1..7, and after
    $SUBCDSTATUS not 1, 2, 3 or 5 (test_compat_function measures the rule)."""
    modes, subcd, calls = 0, False, list(calls)
    for _, name, effect in commands:
        if name == "$SUBCDSTATUS":
            subcd = True
        elif name == "$COMPATIBILITY_0X" and effect:
            mode = calls.pop(0)
            if 1 <= mode <= 7 and not (subcd and mode in (1, 2, 3, 5)):
                modes |= 1 << (mode - 1)
    return modes


class Native(unittest.TestCase):
    def test_table(self):
        self.assertEqual(len(EXPECTED), len(FIXED))
        for text, (commands, codes) in zip(FIXED, EXPECTED):
            result, _, got_commands, got_codes = launcher(text)
            self.assertEqual(result, 0, text)
            self.assertEqual(got_commands, [tuple(x) for x in commands], repr(text))
            self.assertEqual(got_codes, [tuple(x) for x in codes], repr(text))

    def test_shared_number(self):
        """A malformed $XPOS_ / $YPOS_ writes the last number another command
        left, or the value the pass started with."""
        for text, number, want in (
                ("$XPOS_ ", 0, (0, None)), ("$XPOS_ $YPOS_Q", 9, (9, 9)),
                ("$LEFTADJ_12 $XPOS_Q ", 0, (12, None)), ("$LEFTADJ_300 $YPOS_ ", 0, (None, 300)),
                ("$COMPATIBILITY_0X21 $XPOS_ $YPOS_ ", 0, (0x21, 0x21)),
                ("$PAD1ID_0XAF $XPOS_ ", 0, (0xAF, None)), ("$ZPOS_44 $YPOS_ ", 0, (None, 44)),
                ("$DWSTRETCH_31 $XPOS_ ", 0, (31, None)), ("$DWCROP_32 $XPOS_ ", 0, (32, None)),
                ("$XPOS_70000 $YPOS_ ", 0, (None, None)), ("$XPOS_70000 $XPOS_5 ", 0, (5, None)),
                ("$DX_31 $VCDID_77 $XPOS_ ", 3, (3, None)), ("$XPOS_ ", 70000, (None, None)),
                ("$XPOS_-15 $XPOS_15 ", 0, (0, None))):
            _, cfg, _, _ = launcher(text, number)
            self.assertEqual(launcher_positions(cfg), want, text)

    def test_values(self):
        for text, field, want in (
                ("$VCDID_0 $VCDID_7 $VCDID_8 ", "vcdid", 7), ("$VCDID_12345 $VCDID_0012$", "vcdid", 12),
                ("$COMPATIBILITY_0X05 $COMPATIBILITY_0x07$COMPATIBILITY_0X08 ", "compat_modes", 0x50),
                ("$COMPATIBILITY_0X5 $COMPATIBILITY_0X09 $COMPATIBILITY_0X00 ", "compat_modes", 0),
                ("$SUBCDSTATUS $COMPATIBILITY_0X01 $COMPATIBILITY_0X04 ", "compat_modes", 8),
                ("$LEFTADJ_0 $LEFTADJ_256 $LEFTADJ_12 $LEFTADJ_0", "left_adjust", 12),
                ("$SAFEMODE $SAFEMODE2 ", "safe_mode", 1), ("$SAFEMODE2 $SAFEMODE ", "safe_mode", 2),
                ("$SAFEMODE $NOSAFEMODE $SAFEMODE2 ", "safe_mode", 2), ("$NOSAFEMODE", "safe_mode", 0),
                ("$ORIGINAL_OPCODES\n$SMOOTH\n", "original_opcodes", 0),
                ("$ORIGINAL_OPCODES\r\n$SMOOTH\r\n", "original_opcodes", 1),
                ("#$LOAD_PADMAN", "load_padman", 1), ("; $KILL_PADMAN$", "kill_padman", 1),
                ("$SMOOTH\t", "smooth", 0), ("$20012345 00$SMOOTH\n", "smooth", 0),
                ("$IGR5\r\n", "igr_type", 6), ("$IGR6\r\n", "igr_type", 0)):
            _, cfg, _, _ = launcher(text)
            self.assertEqual(getattr(cfg, field), want, text)
        _, cfg, _, _ = launcher("$PAD0ID_0X41 $PAD1ID_0Xaf $PAD1ID_0XZZ $PAD2ID_0X41 ")
        self.assertEqual((cfg.pad_override, cfg.pad_id[0], cfg.pad_id[1]), (3, 0x41, 0xAF))

    def test_launcher_tokens_keep_their_line_rules(self):
        """$NOBOOT, MODE n and the rest are launcHER's own (the original
        takes none of them: see the table), read as before."""
        for text, field, want in (
                ("$NOBOOT\n", "no_boot", 1), ("# $NOBOOT\n", "no_boot", 0), ("x $BIOS", "no_boot", 1),
                ("MODE 3\n", "compat_modes", 4), ("$MODE 4 MODE 2\n", "compat_modes", 10),
                ("MODE\n3\n", "compat_modes", 4), ("MODE 9\n", "compat_modes", 0),
                ("$MODE5 7\n", "compat_modes", 0x50), ("; MODE 3\n$MODE6", "compat_modes", 0x20),
                ("$DITHER_OFF $FASTMIPS\n", "dither_off", 1), ("$FIX_ALL", "runtime_corrections", 0x1F)):
            _, cfg, commands, _ = launcher(text)
            self.assertEqual(getattr(cfg, field), want, text)
            self.assertEqual(commands, [], text)
        # In file order with the original's commands: the last one decides.
        for text, want in (("$NOPAL\n$NTSC2PAL\n", "$FORCEPAL"), ("$NTSC2PAL\n$NOPAL\n", "$NOPAL"),
                           ("$FORCEPAL $PAL2NTSC", "$NOPAL")):
            expected = launcher(want)[1].video_mode
            self.assertEqual(launcher(text)[1].video_mode, expected, text)

    def test_usb_delay(self):
        """$USBDELAY_n: one digit and a terminator, nothing else."""
        for text in USB_EXPECTED:
            self.assertIn(text, FIXED)
        for text, want in USB_EXPECTED.items():
            result, cfg, _, _ = launcher(text)
            self.assertEqual(result, 0, repr(text))
            self.assertEqual((cfg.usb_delay_set, cfg.usb_delay),
                             (0, 0) if want is None else (1, want), repr(text))
        # Without the command nothing is asked for: no delay is added.
        cfg = F.PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        self.assertEqual((cfg.usb_delay_set, cfg.usb_delay), (0, 0))
        # It leaves the shared number alone.
        self.assertEqual(launcher_positions(launcher("$LEFTADJ_12 $USBDELAY_7 $XPOS_Q ")[1]), (12, None))

    def test_vmcdir(self):
        """VMCDIR.TXT: taken or ignored, and the name, as the table says."""
        for data, want in VMC_EXPECTED:
            self.assertEqual(launcher_vmcdir(data), want, data[:24])
        # NULL text with no bytes is the empty file.
        cfg = F.PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        self.assertEqual(LIB.pops_config_parse_vmcdir(c.byref(cfg), None, 0), 1)
        self.assertEqual((cfg.vmc_dir, cfg.vmc_dir_set), (b"", 1))

    def test_vmcdir_files(self):
        """An ignored file is not an error, and the game's own file is read
        after the one for all games."""
        import errno
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Game").mkdir()
            path = root / "VMCDIR.TXT"
            for data, want in VMC_EXPECTED:
                path.write_bytes(data)
                cfg = F.PopsConfig()
                LIB.pops_config_init(c.byref(cfg))
                cfg.vmc_dir = VMC_KEEP
                self.assertEqual(LIB.pops_config_load_vmcdir(c.byref(cfg), str(path).encode()), 0, data[:24])
                self.assertEqual((cfg.vmc_dir, cfg.vmc_dir_set),
                                 (VMC_KEEP, 0) if want is None else (want, 1), data[:24])
            path.unlink()
            self.assertEqual(LIB.pops_config_load_vmcdir(c.byref(cfg), str(path).encode()), -errno.ENOENT)

            def discover():
                cfg = F.PopsConfig()
                LIB.pops_config_init(c.byref(cfg))
                self.assertEqual(LIB.pops_config_discover(c.byref(cfg), (str(root) + "/").encode(), b"Game"), 0)
                return (cfg.vmc_dir, cfg.vmc_dir_set)

            self.assertEqual(discover(), (b"", 0))
            path.write_bytes(b"Shared")
            self.assertEqual(discover(), (b"Shared", 1))
            (root / "Game" / "VMCDIR.TXT").write_bytes(b"Other")
            self.assertEqual(discover(), (b"Other", 1))
            # The game's file with a line end is ignored: the first one stays.
            (root / "Game" / "VMCDIR.TXT").write_bytes(b"Other\r\n")
            self.assertEqual(discover(), (b"Shared", 1))
            # An empty one is taken: the POPS folder itself.
            (root / "Game" / "VMCDIR.TXT").write_bytes(b"")
            self.assertEqual(discover(), (b"", 1))
            path.write_bytes(b"Shared\n")
            (root / "Game" / "VMCDIR.TXT").unlink()
            self.assertEqual(discover(), (b"", 0))

    def test_parse_line_is_the_same_reader(self):
        cfg = F.PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"# $smooth$DWCROP_7\tx"), 0)
        self.assertEqual((cfg.smooth, cfg.display_mask), (1, 0))


class Source(unittest.TestCase):
    def test_vmcdir_use(self):
        """The launcher takes the folder only from a file that was used, and
        an empty name is the POPS folder itself."""
        handler = (ROOT / "launcher/src/handler_pops.c").read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertIn('  if (cfg.vmc_dir_set) {\n', handler)
        self.assertIn('    if (cfg.vmc_dir[0])\n'
                      '      snprintf(vmcDir, sizeof(vmcDir), "%s%s/", vcdDir, cfg.vmc_dir);\n'
                      '    else\n'
                      '      snprintf(vmcDir, sizeof(vmcDir), "%s", vcdDir);\n', handler)
        self.assertNotIn("if (cfg.vmc_dir[0]) {", handler)
        reader = SOURCE[SOURCE.index("int pops_config_load_vmcdir("):SOURCE.index("int pops_config_load_cheats(")]
        self.assertIn('fopen(filepath, "rb")', reader)
        self.assertNotIn("EOVERFLOW", reader)
        self.assertNotIn("EINVAL;\n  }", reader)
        self.assertNotIn("trim_line", SOURCE)

    def test_usb_delay_use_is_unchanged(self):
        """The parsed digit matches the original; what launcHER does with it
        (an EE sleep before the launch, only when it is above 0) is as it was."""
        handler = (ROOT / "launcher/src/handler_pops.c").read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertIn("  if (cfg.usb_delay > 0) {\n", handler)
        self.assertIn("    sleep(cfg.usb_delay);\n", handler)
        self.assertEqual(handler.count("usb_delay"), 3)
        self.assertNotIn("strtol(token + 10", SOURCE)

    def test_no_line_reader_is_left(self):
        self.assertNotIn("parse_directives", SOURCE)
        self.assertNotIn("length > 254", SOURCE)
        loader = SOURCE[SOURCE.index("static int load_config_file("):]
        loader = loader[:loader.index("\n}\n")]
        self.assertIn("pops_config_parse_text(cfg, text, size, value, NULL, NULL)", loader)
        self.assertIn('fopen(filepath, "rb")', loader)

    def test_game_file_starts_with_the_name_length(self):
        discover = SOURCE[SOURCE.index("int pops_config_discover("):]
        self.assertIn("result = load_config_file(cfg, path, 0, (uint32_t)strlen(subfolder) + 1);",
                      discover)

    def test_game_file_number_reaches_the_position(self):
        import tempfile
        LIB.pops_config_discover.argtypes = [c.POINTER(F.PopsConfig), c.c_char_p, c.c_char_p]
        LIB.pops_config_discover.restype = c.c_int
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Game").mkdir()
            (root / "CHEATS.TXT").write_bytes(b"$YPOS_Q\r\n")
            (root / "Game" / "CHEATS.TXT").write_bytes(b"$XPOS_\r\n")
            cfg = F.PopsConfig()
            LIB.pops_config_init(c.byref(cfg))
            self.assertEqual(LIB.pops_config_discover(c.byref(cfg), (str(root) + "/").encode(), b"Game"), 0)
            # "for all games": 0. The game's own: strlen("Game") + 1.
            self.assertEqual(launcher_positions(cfg), (5, 0))


def table_names():
    return re.findall(r'^  CMD\("([^"]+)", CMD_', SOURCE, re.M)


@unittest.skipUnless(HAVE_MAIN and HAVE_UNICORN, "needs POPSTARTER_TEST_ELF and unicorn")
class Original(unittest.TestCase):
    def test_handler_table(self):
        """launcHER's table is the original's handlers, in its order."""
        import trace_original_pops_config_text as T
        handlers = T.handlers()
        names = [handlers[address] for address in sorted(handlers)]
        self.assertEqual(table_names(), names)
        self.assertEqual(len(names), 66)

    def test_table_is_the_original(self):
        self.assertEqual(len(EXPECTED), len(FIXED))
        for text, (commands, codes) in zip(FIXED, EXPECTED):
            _, got_commands, got_codes = original(text)
            self.assertEqual(got_commands, [tuple(x) for x in commands], repr(text))
            self.assertEqual(got_codes, [tuple(x) for x in codes], repr(text))
        print("original command pass: %d fixed texts match the table" % len(FIXED))

    launcher_modes = 0
    usb_delays = 0

    def compare(self, text, number=0):
        scan, commands, codes = original(text, number)
        result, cfg, got_commands, got_codes = launcher(text, number)
        self.assertEqual(result, 0, repr(text))
        self.assertEqual(got_commands, commands, repr(text))
        self.assertEqual(got_codes, codes, repr(text))
        self.assertEqual(launcher_positions(cfg), position_writes(scan), repr(text))
        calls = [a0 for name, a0, _ in scan.calls if name == "compat"]
        modes = compat_modes(commands, calls)
        if cfg.compat_modes != modes:
            # More modes only from launcHER's own "MODE n" tokens, which the
            # original does not have.
            self.assertEqual(cfg.compat_modes & modes, modes, repr(text))
            self.assertTrue(MODE_TOKEN.search(text.upper()), repr(text))
            self.launcher_modes += 1
        ids = [a0 for name, a0, _ in scan.calls if name == "vcdid"]
        self.assertEqual(cfg.vcdid, ids[-1] if ids else 0, repr(text))
        # The byte at 0x100017: the digit, or untouched.
        self.assertEqual(cfg.usb_delay if cfg.usb_delay_set else USB_BEFORE, scan.usb_delay, repr(text))
        if not cfg.usb_delay_set:
            self.assertEqual(cfg.usb_delay, 0, repr(text))
        self.usb_delays += cfg.usb_delay_set
        return len(commands), len(codes)

    def test_fixed_texts(self):
        for text in FIXED:
            self.compare(text)

    def test_vmcdir_fixed(self):
        for data, want in VMC_EXPECTED:
            got, opens = original_vmcdir(data)
            self.assertEqual(got, want, data[:24])
            self.assertEqual(opens, [b"mass:/POPS/VMCDIR.TXT"], data[:24])
            self.assertEqual(launcher_vmcdir(data), got, data[:24])
        # The game's own file: the same rules.
        for data, want in VMC_EXPECTED[:30]:
            got, opens = original_vmcdir(data, b"Game Name/")
            self.assertEqual(got, want, data[:24])
            self.assertEqual(opens, [b"mass:/POPS/Game Name/VMCDIR.TXT"], data[:24])
        # No file: nothing changes.
        import trace_original_pops_config_text as T
        run = T.vmcdir(None)
        self.assertEqual((run.result, run.paths, run.opens), (0, {}, [b"mass:/POPS/VMCDIR.TXT"]))
        print("original VMCDIR.TXT reader: %d files match the table (%d of them also as the "
              "game's own file)" % (len(VMC_EXPECTED), 30))

    def test_vmcdir_random(self):
        rng = random.Random(0x8D4F84)
        taken = 0
        for _ in range(400):
            data = random_vmcdir(rng)
            got, _ = original_vmcdir(data)
            self.assertEqual(launcher_vmcdir(data), got, data[:40])
            taken += got is not None
        print("original VMCDIR.TXT reader: 400 random files match (%d taken, %d ignored)"
              % (taken, 400 - taken))

    def test_usb_delay_byte(self):
        """$USBDELAY_n: the byte at 0x100017 after the original's pass."""
        for text, want in USB_EXPECTED.items():
            scan, _, _ = original(text)
            self.assertEqual(scan.usb_delay, USB_BEFORE if want is None else want, repr(text))
            self.compare(text)
        print("original $USBDELAY_n: %d texts, byte at 0x100017 matches" % len(USB_EXPECTED))

    def test_random_usb_delay(self):
        rng = random.Random(0x100017)
        for _ in range(300):
            text = "".join(
                rng.choice(("", "", "x", "#", "$SMOOTH ", "$LEFTADJ_9 ", "$XPOS_Q ", "\r\n")) +
                rng.choice(("$USBDELAY_", "$usbdelay_", "$USBDELAY", "$USBDELAY_")) +
                "".join(rng.choice("0123456789 \t\r\n$_-xX\0") for _ in range(rng.randrange(0, 4))) +
                rng.choice(ENDS)
                for _ in range(rng.randrange(1, 4)))
            self.compare(text)
        print("original $USBDELAY_n: 300 random texts match, the byte at 0x100017 was written in %d"
              % self.usb_delays)

    def test_shared_number_start(self):
        for text in ("$XPOS_ ", "$YPOS_Q $XPOS_ ", "$XPOS_123456 $YPOS_5 ", "$LEFTADJ_7 $XPOS_ ",
                     "$ZPOS_ $YPOS_ "):
            for number in (0, 1, 15, 255, 65535, 65536):
                self.compare(text, number)
        print("original command pass: 30 texts x starting numbers match")

    def test_random_texts(self):
        rng = random.Random(0x13C0)
        count = commands = codes = 0
        for _ in range(1500):
            text = random_text(rng)
            found = self.compare(text)
            count, commands, codes = count + 1, commands + found[0], codes + found[1]
        print("original command pass: %d random texts match (%d commands, %d cheat codes; "
              "%d texts also had a launcHER-only MODE token; the byte at 0x100017 was "
              "written in %d)"
              % (count, commands, codes, self.launcher_modes, self.usb_delays))

    def test_compat_function(self):
        """FUN_008dc2c4, as the pass calls it: which modes poke anything."""
        import trace_original_pops_config_text as T
        alone = len(T.scan_commands("$SUBCDSTATUS ").writes)
        for mode in list(range(0, 17)) + [0x21, 0x7F, 0x80, 0xFF]:
            command = "$COMPATIBILITY_0X%02X " % mode
            plain = T.scan_commands(command)
            after = T.scan_commands("$SUBCDSTATUS " + command)
            self.assertEqual([call[:2] for call in plain.calls], [("compat", mode)])
            self.assertEqual(bool(plain.writes), 1 <= mode <= 7, mode)
            self.assertEqual(len(after.writes) > alone, mode in (4, 6, 7), mode)
        print("original FUN_008dc2c4: 21 modes x 2 states match")


if __name__ == "__main__":
    unittest.main()
