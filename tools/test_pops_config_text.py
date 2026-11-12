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

The host library is linked to a fixed file name in Python's temp folder
(test_pops_features.compile_shared_library), and tempfile reads TMPDIR
before TMP and TEMP. To keep two runs apart, set all three:

    export TMP=<empty dir> TEMP=<same> TMPDIR=<same>
    python tools/test_pops_config_text.py
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
# Where launcHER's own MODE n / bare digit can stand (its white space is the
# six ASCII bytes, whatever the locale; a run over 63 bytes is no token).
MODE_TOKEN = re.compile(r"(?:^|[ \t\n\v\f\r\0])(?:\$?MODE[ \t\n\v\f\r]*[0-9]|[1-8](?:$|[ \t\n\v\f\r\0]))")
# launcHER's own video tokens: the video state is not compared where one
# stands (they are not POPStarter's; owner decision, docs/PR23_HANDOFF).
LAUNCHER_VIDEO = re.compile(r"PAL2NTSC|NTSC2PAL|FORCENTSC")
# The original's three video words (gp-relative), as its region pass
# reads them at 0x879034..0x87930c (read from the code): forced PAL is
# 0x38a0 == 1 with 0x3864 == 0; otherwise a European disc goes PAL only
# while 0x4fa0 == 1. 0x3864 is the 480p flag $480P sets.
FORCED_PAL, PROGRESSIVE, AUTO_PAL = 0x38A0, 0x3864, 0x4FA0
# What the pass finds in them: off, off, and the automatic PAL selector on
# (the start-up value when the byte at 0x10002a is 1, 0x8711ec). No
# handler of the pass reads 0x4fa0 (its one load is at 0x87930c).
GP_START = {FORCED_PAL: 0, PROGRESSIVE: 0, AUTO_PAL: 1}
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


def original(text, number=0, gp_words=None, beyond=b""):
    import trace_original_pops_config_text as T
    words = dict(GP_START if gp_words is None else gp_words)
    scan = T.scan_commands(text, usb_delay=USB_BEFORE, number=number, gp_words=words, beyond=beyond)
    scan.gp_after = {**words, **scan.flags}
    return scan, [(offset, name, effects > 0) for offset, name, _, effects in scan.events], scan.skips


def original_video(words):
    """What the original's region pass does with its three words: 'forced'
    (PAL whatever the disc), 'auto' (PAL for a European disc), 'off' (no
    PAL), and whether the 480p flag is set."""
    progressive = words.get(PROGRESSIVE, 0) != 0
    if words.get(FORCED_PAL, 0) == 1 and not progressive:
        return "forced", progressive
    return ("auto" if words.get(AUTO_PAL, 0) == 1 else "off"), progressive


def launcher_video(cfg):
    """The same for launcHER's config, as the launch reads it: handler_pops.c
    passes POPS_VMODE_480P when progressive_requested is set, else
    video_mode; pops_modes_patches.c forces PAL for POPS_VMODE_NTSC2PAL and
    leaves a European disc at PAL unless it is POPS_VMODE_NOPAL or
    POPS_VMODE_480P."""
    progressive = bool(cfg.progressive_requested)
    mode = 4 if progressive else cfg.video_mode  # POPS_VMODE_480P
    if mode == 2:  # POPS_VMODE_NTSC2PAL
        return "forced", progressive
    return ("off" if mode in (3, 4) else "auto"), progressive  # NOPAL, 480P


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
    # $FORCEPAL is taken but does nothing once a $480P was taken; $NOPAL
    # does not undo a $FORCEPAL (Native.test_video_commands has the state).
    "$480P $FORCEPAL ", "$480P $NOPAL $FORCEPAL ", "$FORCEPAL $480P $FORCEPAL ", "$FORCEPAL $NOPAL ",
    "$NOPAL $FORCEPAL ", "$480p\r\n$forcepal\r\n", "$FORCEPAL\t$480P $FORCEPAL$FORCEPAL",
    # Each condition of the five code tests, from both sides. A command in
    # the columns of a code is not seen; where the columns are no code, it is.
    "$500$480P 1234 ", "$50002345 1234 $NOPAL ", "$50012345 1234 $NOPAL ", "$50102345 1234 $NOPAL ",
    "$50010000 0000$NOPAL ", "$51002345 1234 $NOPAL ", "$3A012345 1234 $NOPAL ",
    "$80112345 1234 $NOPAL ", "$D0212345 1234 $NOPAL ", "$80012345$1234 $NOPAL ",
    "$S0003000 $SMOOTH $NOPAL ", "$S0004000 $SMOOTH $NOPAL ", "$S2203000 $SMOOTH $NOPAL ",
    "$S3000000 $SMOOTH $NOPAL ", "$S0300000 $SMOOTH $NOPAL ", "$S0010000 $SMOOTH $NOPAL ",
    "$S0003000 12345678$NOPAL ", "$S0004000 12345678$NOPAL ", "$S0000400 12345678$NOPAL ",
    "$T0000300 $SMOOTH $NOPAL ", "$T0000400 $SMOOTH $NOPAL ", "$T2200300 $SMOOTH $NOPAL ",
    "$T0001000 $SMOOTH $NOPAL ", "$T3000000 $SMOOTH $NOPAL ", "$T0300000 $SMOOTH $NOPAL ",
    "$T0010000 $SMOOTH $NOPAL ", "$T0000300 12345678$NOPAL ", "$T0000400 12345678$NOPAL ",
    "$=1012345 $SMOOTH $NOPAL ", "$=2012345 $SMOOTH $NOPAL ", "$!0012345 $SMOOTH $NOPAL ",
    "$!2012345 $SMOOTH $NOPAL ", "$20012345 $SMOOTH $NOPAL ", "$30012345 $SMOOTH $NOPAL ",
    "$00012345 $SMOOTH $NOPAL ", "$20012345\t$SMOOTH $NOPAL ",
    # launcHER's own tokens next to a 63-byte cut or a byte above 0x7f: still
    # nothing to the original, and no stray mode in launcHER.
    "x" * 63 + "1 ", "x" * 62 + " 1 ", "\xa04 ", "$MODE3" + "x" * 60 + " ",
    # The 14-column test's '3' kind from both sides (column 3 is 0 or 1).
    "$30012345 1234 $NOPAL ", "$30212345 1234 $NOPAL ",
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

# $480P, $NOPAL, $FORCEPAL: what the original's region pass makes of its
# three words after the text (original_video), from its run under
# emulation (Original.test_video_table). $FORCEPAL stores nothing once
# $480P set 0x3864 (0x8987f0); $NOPAL clears 0x4fa0 only, so it does not
# undo an earlier $FORCEPAL.
VIDEO_EXPECTED = {
    "": ("auto", False), "$SMOOTH ": ("auto", False), "$FORCEPAL ": ("forced", False),
    "$NOPAL ": ("off", False), "$480P ": ("off", True), "$480P $FORCEPAL ": ("off", True),
    "$480P $NOPAL $FORCEPAL ": ("off", True), "$FORCEPAL $480P $FORCEPAL ": ("off", True),
    "$FORCEPAL $NOPAL ": ("forced", False), "$NOPAL $FORCEPAL ": ("forced", False),
    "$480p\r\n$forcepal\r\n": ("off", True), "$FORCEPAL\t$480P $FORCEPAL$FORCEPAL": ("off", True),
    "$FORCEPAL $480P ": ("off", True), "$480PX $FORCEPAL ": ("forced", False),
    "$FORCEPAL\t": ("auto", False), "$FORCEPAL\t$NOPAL ": ("off", False),
    "$480P $NOPAL ": ("off", True), "$NOPAL $480P ": ("off", True),
    "$FORCEPAL $480P $NOPAL ": ("off", True), "$FORCEPAL $480P $NOPAL $FORCEPAL ": ("off", True),
}
# Two files, the one for all games and then the game's own, as
# (first, second, result): the words carry over from one to the next.
VIDEO_TWO_FILES = [
    ("$480P ", "$FORCEPAL ", ("off", True)), ("$FORCEPAL ", "$480P ", ("off", True)),
    ("$FORCEPAL ", "$NOPAL ", ("forced", False)), ("$NOPAL ", "$FORCEPAL ", ("forced", False)),
    ("$480P $NOPAL ", "$FORCEPAL ", ("off", True)), ("$NOPAL ", "", ("off", False)),
]

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
    ([(0, '$480', True), (6, '$FORCEPAL', False)], []),
    ([(0, '$480', True), (6, '$NOPAL', True), (13, '$FORCEPAL', False)], []),
    ([(0, '$FORCEPAL', True), (10, '$480', True), (16, '$FORCEPAL', False)], []),
    ([(0, '$FORCEPAL', True), (10, '$NOPAL', True)], []),
    ([(0, '$NOPAL', True), (7, '$FORCEPAL', True)], []),
    ([(0, '$480', True), (7, '$FORCEPAL', False)], []),
    ([(10, '$480', True), (16, '$FORCEPAL', False), (25, '$FORCEPAL', False)], []),
    ([(4, '$480', True)], []),
    ([(15, '$NOPAL', True)], [(0, 14)]),
    ([(15, '$NOPAL', True)], []),
    ([(15, '$NOPAL', True)], []),
    ([(14, '$NOPAL', True)], []),
    ([(15, '$NOPAL', True)], []),
    ([(15, '$NOPAL', True)], []),
    ([(15, '$NOPAL', True)], [(0, 14)]),
    ([(15, '$NOPAL', True)], []),
    ([(15, '$NOPAL', True)], []),
    ([(18, '$NOPAL', True)], [(0, 18)]),
    ([(10, '$SMOOTH', True), (18, '$NOPAL', True)], []),
    ([(18, '$NOPAL', True)], [(0, 18)]),
    ([(10, '$SMOOTH', True), (18, '$NOPAL', True)], []),
    ([(10, '$SMOOTH', True), (18, '$NOPAL', True)], []),
    ([(10, '$SMOOTH', True), (18, '$NOPAL', True)], []),
    ([(18, '$NOPAL', True)], [(0, 18)]),
    ([(18, '$NOPAL', True)], []),
    ([(18, '$NOPAL', True)], [(0, 18)]),
    ([(18, '$NOPAL', True)], [(0, 18)]),
    ([(10, '$SMOOTH', True), (18, '$NOPAL', True)], []),
    ([(18, '$NOPAL', True)], [(0, 18)]),
    ([(10, '$SMOOTH', True), (18, '$NOPAL', True)], []),
    ([(10, '$SMOOTH', True), (18, '$NOPAL', True)], []),
    ([(10, '$SMOOTH', True), (18, '$NOPAL', True)], []),
    ([(10, '$SMOOTH', True), (18, '$NOPAL', True)], []),
    ([(18, '$NOPAL', True)], [(0, 18)]),
    ([(18, '$NOPAL', True)], []),
    ([(18, '$NOPAL', True)], [(0, 18)]),
    ([(10, '$SMOOTH', True), (18, '$NOPAL', True)], []),
    ([(18, '$NOPAL', True)], [(0, 18)]),
    ([(10, '$SMOOTH', True), (18, '$NOPAL', True)], []),
    ([(18, '$NOPAL', True)], [(0, 18)]),
    ([(10, '$SMOOTH', True), (18, '$NOPAL', True)], []),
    ([(18, '$NOPAL', True)], [(0, 18)]),
    ([(10, '$SMOOTH', True), (18, '$NOPAL', True)], []),
    ([], []),
    ([], []),
    ([], []),
    ([], []),
    ([(15, '$NOPAL', True)], [(0, 14)]),
    ([(15, '$NOPAL', True)], []),
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

    def test_video_commands(self):
        """$480P / $NOPAL / $FORCEPAL as the original's words end up."""
        for text, want in VIDEO_EXPECTED.items():
            _, cfg, _, _ = launcher(text)
            self.assertEqual(launcher_video(cfg), want, repr(text))
            # forced_pal is the original's gp+0x38a0. In every text of the
            # table the original left it 1 exactly where the region pass
            # forces PAL (Original.compare checks the word itself).
            self.assertEqual(cfg.forced_pal, int(want[0] == "forced"), repr(text))
        # The review's case: after $480P, $FORCEPAL changes nothing at all.
        for text in ("$480P ", "$480P $FORCEPAL ", "$480P $FORCEPAL $FORCEPAL "):
            _, cfg, commands, _ = launcher(text)
            self.assertEqual((cfg.video_mode, cfg.progressive_requested), (4, 1), repr(text))
            self.assertTrue(all(not effect for _, name, effect in commands if name == "$FORCEPAL"))

    def test_video_two_files(self):
        """The 480p flag of the file for all games also stops the game's
        own $FORCEPAL (pops_config_discover reads both)."""
        import tempfile
        for first, second, want in VIDEO_TWO_FILES:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "Game").mkdir()
                (root / "CHEATS.TXT").write_bytes(first.encode("latin-1"))
                (root / "Game" / "CHEATS.TXT").write_bytes(second.encode("latin-1"))
                cfg = F.PopsConfig()
                LIB.pops_config_init(c.byref(cfg))
                self.assertEqual(LIB.pops_config_discover(c.byref(cfg), (str(root) + "/").encode(), b"Game"), 0)
                self.assertEqual(launcher_video(cfg), want, (first, second))
                self.assertEqual(cfg.forced_pal, int(want[0] == "forced"), (first, second))

    def test_launcher_token_bytes(self):
        """launcHER's own tokens: white space is the six ASCII bytes
        (space, TAB, LF, VT, FF, CR) whatever the host's locale, and a run of
        more than 63 non-blank bytes is no token, its tail included. Whether
        these tokens are read from CHEATS.TXT at all is the owner's call
        (docs/PR23_HANDOFF_2026-11-11.md section 8); this pins how."""
        for text, want in (
                ("x" * 63 + "1 ", 0), ("x" * 64 + "1 ", 0), ("x" * 200 + "7", 0),
                ("x" * 62 + " 1 ", 1), ("x" * 63 + " 1 ", 1),
                ("$MODE3" + "x" * 57 + " ", 4), ("$MODE3" + "x" * 58 + " ", 0),
                ("MODE 3" + "x" * 57 + " ", 4), ("MODE 3" + "x" * 58 + " ", 0),
                ("\xa04 ", 0), ("\xa0 4 ", 8), ("4\xa0 ", 0), ("\x854 ", 0), ("\x1c4 ", 0),
                ("\x1f4 ", 0), ("\xff4\xff ", 0), ("\v4 ", 8), ("\f4\f", 8), ("\r4\r", 8),
                ("MODE\v3 ", 4), ("MODE\xa03 ", 0), ("$MODE\xa03 ", 0),
                # The MODE digit search stops at a line end: "3x" on the
                # next line is a token of its own, and no bare digit.
                ("MODE\n3x ", 0), ("$MODE\n3x ", 0), ("MODE 3x ", 4)):
            _, cfg, commands, _ = launcher(text)
            self.assertEqual(cfg.compat_modes, want, repr(text))
            self.assertEqual(commands, [], repr(text))

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

    def test_usb_delay_default_and_existing_sleep(self):
        """An explicit digit keeps the existing EE sleep. With no command,
        USB/SB launches default to one second at that same place."""
        handler = (ROOT / "launcher/src/handler_pops.c").read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertIn("  if ((device == Device_USB || isSbLaunch) && !cfg.usb_delay_set)\n", handler)
        self.assertIn("    cfg.usb_delay = 1;\n", handler)
        self.assertIn("  if (cfg.usb_delay > 0) {\n", handler)
        self.assertIn("    sleep(cfg.usb_delay);\n", handler)
        self.assertEqual(handler.count("usb_delay"), 5)
        self.assertNotIn("strtol(token + 10", SOURCE)

    def test_no_line_reader_is_left(self):
        self.assertNotIn("parse_directives", SOURCE)
        self.assertNotIn("length > 254", SOURCE)
        loader = SOURCE[SOURCE.index("static int load_config_file("):]
        loader = loader[:loader.index("\n}\n")]
        self.assertIn("pops_config_parse_text(cfg, text, size, value, NULL, NULL)", loader)
        self.assertIn('fopen(filepath, "rb")', loader)

    def test_token_bytes_are_spelt_out(self):
        """No locale-dependent byte class in the reader: the host test
        process and the EE build read the same bytes the same way."""
        self.assertIsNone(re.search(r"\bis(space|digit|alpha|alnum|xdigit)\s*\(", SOURCE))
        self.assertIn("static int token_space(unsigned char c) {\n"
                      "  return c == ' ' || (c >= '\\t' && c <= '\\r'); /* TAB LF VT FF CR */\n",
                      SOURCE.replace("\r\n", "\n"))

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
    launcher_video_texts = 0

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
        # The forced-PAL word itself (launcHER's own video tokens do not
        # touch forced_pal, so this holds for every text).
        self.assertEqual(cfg.forced_pal, scan.gp_after.get(FORCED_PAL, 0), repr(text))
        # $480P / $NOPAL / $FORCEPAL: the three words the region pass reads.
        if LAUNCHER_VIDEO.search(text.upper()):
            self.launcher_video_texts += 1
        else:
            self.assertEqual(launcher_video(cfg), original_video(scan.gp_after), repr(text))
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
        texts = ("$XPOS_ ", "$YPOS_Q $XPOS_ ", "$XPOS_123456 $YPOS_5 ", "$LEFTADJ_7 $XPOS_ ",
                 "$ZPOS_ $YPOS_ ")
        numbers = (0, 1, 15, 255, 65535, 65536)
        for text in texts:
            for number in numbers:
                self.compare(text, number)
        print("original command pass: %d texts x %d starting values (%d runs) match"
              % (len(texts), len(numbers), len(texts) * len(numbers)))

    def test_random_texts(self):
        rng = random.Random(0x13C0)
        count = commands = codes = 0
        for _ in range(1500):
            text = random_text(rng)
            found = self.compare(text)
            count, commands, codes = count + 1, commands + found[0], codes + found[1]
        print("original command pass: %d random texts match (%d commands, %d cheat codes; "
              "%d texts also had a launcHER-only MODE token; the byte at 0x100017 was "
              "written in %d; video words not compared in %d with a launcHER-only video token)"
              % (count, commands, codes, self.launcher_modes, self.usb_delays,
                 self.launcher_video_texts))

    def test_video_table(self):
        """$480P / $NOPAL / $FORCEPAL: the original's three words after the
        pass, against VIDEO_EXPECTED and launcHER."""
        for text, want in VIDEO_EXPECTED.items():
            scan, _, _ = original(text)
            self.assertEqual(original_video(scan.gp_after), want, repr(text))
            self.compare(text)
        print("original video words: %d texts match the table" % len(VIDEO_EXPECTED))

    def test_video_random(self):
        rng = random.Random(0x8987F0)
        forms = ("$480P", "$480p", "$480PX", "$480", "$FORCEPAL", "$forcepal", "$FORCEPALX",
                 "$NOPAL", "$nopal", "$NOPALX", "$SMOOTH", "$20012345 00", "x", "#")
        for _ in range(600):
            text = "".join(rng.choice(forms) + rng.choice(ENDS + ["\t", "X"])
                           for _ in range(rng.randrange(1, 6)))
            self.compare(text)
        print("original video words: 600 random texts match")

    def _two_files(self, first, second):
        """The original run twice, its gp words carried from the file for
        all games to the game's own; launcHER through pops_config_discover
        and, for each command's effect, one config through both texts."""
        import tempfile
        scan1, commands1, codes1 = original(first)
        scan2, commands2, codes2 = original(second, number=5, gp_words=scan1.gp_after)
        cfg = F.PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        _, _, got1, got_codes1 = launcher(first, cfg=cfg)
        cfg.gs_mask = 0  # load_config_file: the six GS flags are per file
        _, _, got2, got_codes2 = launcher(second, number=5, cfg=cfg)
        self.assertEqual((got1, got_codes1, got2, got_codes2),
                         (commands1, codes1, commands2, codes2), (first, second))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Game").mkdir()
            (root / "CHEATS.TXT").write_bytes(first.encode("latin-1"))
            (root / "Game" / "CHEATS.TXT").write_bytes(second.encode("latin-1"))
            whole = F.PopsConfig()
            LIB.pops_config_init(c.byref(whole))
            self.assertEqual(LIB.pops_config_discover(c.byref(whole), (str(root) + "/").encode(), b"Game"), 0)
        want = original_video(scan2.gp_after)
        self.assertEqual(launcher_video(cfg), want, (first, second))
        self.assertEqual(launcher_video(whole), want, (first, second))
        word = scan2.gp_after.get(FORCED_PAL, 0)
        self.assertEqual((cfg.forced_pal, whole.forced_pal), (word, word), (first, second))
        return want

    def test_video_two_files(self):
        for first, second, want in VIDEO_TWO_FILES:
            self.assertEqual(self._two_files(first, second), want, (first, second))
        forms = ("$480P ", "$FORCEPAL ", "$NOPAL ", "$SMOOTH ")
        files = [""] + list(forms) + [a + b for a in forms for b in forms]
        for first in files:
            for second in files:
                self._two_files(first, second)
        print("original video words, two files: %d fixed and %d pairs match"
              % (len(VIDEO_TWO_FILES), len(files) ** 2))

    def test_short_files(self):
        """A file of a few bytes. The original's buffer is malloc(2 * size)
        (0x8839f0) with its second half zeroed (0x883aa8), but a code test
        at a '$' reads columns up to 14 from it, so for a '$' at i with
        i + 9 >= 2 * size it reads past the buffer: what the heap holds
        there decides whether the '$' starts a code. launcHER reads zeros
        there. Measured: with zeros the original equals launcHER; with
        other bytes only that kind of '$' can be stepped over as a code,
        and no command changes."""
        seeds = [code[:k] for code in CODES for k in range(1, 9)]
        seeds += [name[:k] for name in PLAIN + NUMBERED for k in range(1, 9)]
        seeds += ["$800", "$8000", "$30", "$D01", "$5000", "$S00", "$T000", "$=0", "$!1", "$0",
                  "$$", "$", " $", "x$8", "$480P", "$IGR0", "$D2LS", "$DX_1", "$IGR0$", "$80$80"]
        texts = sorted({s for s in seeds if 1 <= len(s) <= 8})
        heaps = (b" " * 32, b"0" * 32, b"  0 $ 1 2 X" * 3, b"\xff" * 32)
        differ = 0
        for text in texts:
            self.compare(text)
            _, base_commands, base_codes = original(text)
            n = len(text)
            for heap in heaps:
                _, commands, codes = original(text, beyond=heap)
                self.assertEqual(commands, base_commands, (text, heap))
                extra = [code for code in codes if code not in base_codes]
                for offset, _ in extra:
                    self.assertGreaterEqual(offset + 9, 2 * n, (text, heap))
                self.assertEqual([code for code in codes if code in base_codes], base_codes, (text, heap))
                differ += bool(extra)
        _, _, codes = original("$800", beyond=b" " * 32)
        self.assertEqual(codes, [(0, 14)])
        self.assertEqual(launcher("$800")[3], [])
        print("original command pass, short files: %d texts of 1..8 bytes equal launcHER with a "
              "zero heap; %d of %d runs with other heap bytes step over a code there, no command "
              "changes" % (len(texts), differ, len(texts) * len(heaps)))

    def test_random_token_bytes(self):
        """launcHER's own tokens beside long runs, bytes above 0x7f and the
        control bytes: the original takes none of them, and launcHER adds a
        mode only for a whole token of at most 63 bytes."""
        rng = random.Random(0x63A0)
        pieces = LAUNCHER_ONLY + ["1", "4", "8", "MODE", "$MODE", "$SMOOTH", "$NOPAL"]
        blanks = [" ", "\t", "\r\n", "\n", "\v", "\f", "\xa0", "\x85", "\x1c", "\xff", "\0"]
        for _ in range(500):
            parts = []
            for _ in range(rng.randrange(1, 6)):
                kind = rng.randrange(4)
                if kind == 0:
                    piece = "x" * rng.choice((57, 58, 61, 62, 63, 64, 65, 70))
                elif kind == 1:
                    piece = "".join(rng.choice("\xa0\x85\xe9\xff\x80") for _ in range(rng.randrange(1, 3)))
                else:
                    piece = rng.choice(pieces)
                parts.append(piece + rng.choice(blanks + [""]))
            self.compare("".join(parts))
        print("original command pass: 500 random texts with long runs and high bytes match")

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
