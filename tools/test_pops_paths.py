#!/usr/bin/env python3
"""Where POPStarter r13 looks for things at launch, and where launcHER looks.

Three kinds of check, as in the other tools/test_pops_*.py files:

  Original  re-runs tools/trace_original_pops_paths.py (the original's own
            `main` under Unicorn with a modelled library and synthetic
            files) on its fixed case list and on every argv[0] form, and
            compares the result with the table pinned here. Skipped unless
            POPSTARTER_TEST_ELF is set and unicorn is installed; a case that
            needs Sony's POPS files is skipped unless POPS_TEST_ELF points
            at POPS.ELF with POPS_IOX.PAK, POPS.PAK and IOPRP252.IMG beside
            it. No original bytes are in this file.
  Native    compiles common/src/launch_args.c for the host and calls
            launcHER's own resolver on the same argv[0] forms, the way
            handleQuickboot() calls it for a renamed launcHER
            (launcher path = argv[0], no explicit argument, 16 slots; the
            BDMA mode is fixed to "none" so the result does not depend on
            the host's files).
  Source    pins the launcHER source lines the comparison relies on, and
            that the document lists what is pinned here.

FORM_TABLE and OTHER_DIFFERENCES together are the expected-difference list:
stage 1 of this work changes no launcHER behaviour, so every row records a
place where launcHER today does not do what the original does. Nothing here
has run on a console: the "original" column is an emulated run of one
function, the "launcHER" column is a host build of one source file.
See docs/POPSTARTER_PATHS.md.
"""
import ctypes as c
import os
import subprocess
import sys
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import trace_original_pops_paths as T  # noqa: E402

HAVE_MAIN = bool(os.environ.get("POPSTARTER_TEST_ELF"))
if HAVE_MAIN:
    try:
        import unicorn  # noqa: F401
    except Exception:
        HAVE_MAIN = False


def _lines(text):
    return [line.strip() for line in text.strip().splitlines()]


# ---------------------------------------------------------------------------
# The measured table: the four launch kinds, run through to ExecPS2
# ---------------------------------------------------------------------------
# Each line is "<call site> <call> <subject> -> <result>" as
# trace_original_pops_paths.summary() prints it. {0..9} is ten consecutive
# calls from one loop; "a..b" as a call site is ten separate call sites.

START = _lines("""
    8713d8 fioOpen rom0:PSXVER -> -2
    871418 SifIopReset 'rom0:UDNL '
    871470 SifIopReset 'rom0:UDNL '
    871a3c SifLoadModule rom0:SIO2MAN -> loaded
    871a88 SifLoadModule rom0:MCMAN -> loaded
""")

# argv[0] = mass:/POPS/XX.GAME.ELF, POPS_IOX.PAK and GAME.VCD in mass:/POPS,
# nothing optional present.
USB = START + _lines("""
    871d6c fioOpen mc0:/POPSTARTER/usbd.irx -> -2
    871e28 fioOpen mc1:/POPSTARTER/usbd.irx -> -2
    871f20 fioOpen mc0:/POPSTARTER/usbhdfsd.irx -> -2
    871fdc fioOpen mc1:/POPSTARTER/usbhdfsd.irx -> -2
    8720ec SifExecModuleBuffer 0x6935 bytes -> started
    872188 SifExecModuleBuffer 0xbecd bytes -> started
    8d8a68 fioGetstat mass:/POPS -> 0
    87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> ok
    87d350 unpack to 0x200000 -> 0x33ebb9 bytes
    8761d8 fioOpen mass:/POPS/GAME.VCD -> ok
    87e538 fioOpen mass:/POPS/IGR_BG.TM2 -> -2
    87e75c fioOpen mass:/POPS/IGR_NO.TM2 -> -2
    87e968 fioOpen mass:/POPS/IGR_YES.TM2 -> -2
    87f0d0 fioOpen mass:/POPS/OSD.BIN -> -2
    8807d4 fioOpen mass:/POPS/BIOS.BIN -> -2
    88114c fioOpen mass:/POPS/TROJAN_{0..9}.BIN -> -2
    88249c fioOpen mass:/POPS/PATCH_{0..9}.BIN -> -2
    87ee9c fioGetstat mass:/POPS/GAME/ -> -2
    883840 fioOpen mass:/POPS/CHEATS.TXT -> -2
    8d554c fioOpen mass:/POPS/VMCDIR.TXT -> -2
    8d6280 fioOpen mass:/POPS/DISCS.TXT -> -2
    877834..8788d0 fioOpen mass:/POPS/MODULE_{0..9}.IRX -> -2
    8d83c0 fioGetstat mass0:/POPS/GAME -> -2
    8d83d4 fioMkdir mass0:/POPS/GAME -> 0
    8d8d2c fioOpen mass0:/POPS/GAME/SLOT0.VMC -> -2
    8d8d2c fioOpen mass0:/POPS/GAME/SLOT0.VMC [create] -> ok
    8d8d9c fioWrite mass:/POPS/GAME/SLOT0.VMC -> 0x20000 bytes
    8d8d2c fioOpen mass0:/POPS/GAME/SLOT1.VMC -> -2
    8d8d2c fioOpen mass0:/POPS/GAME/SLOT1.VMC [create] -> ok
    8d8d9c fioWrite mass:/POPS/GAME/SLOT1.VMC -> 0x20000 bytes
    87a78c SifIopReset 'rom0:UDNL '
    87a7f4 SifIopReset 'rom0:UDNL '
    87a900 SifLoadModuleBuffer buffer 0x100000 -> loaded
    87acc4 SifExecModuleBuffer 0x6935 bytes -> started
    87ad70 SifExecModuleBuffer 0xbecd bytes -> started
    87c054 SifExecModuleBuffer 0xa45 bytes -> started
    87c1cc ExecPS2 entry 0x200000 gp 0x0 argc 1
""")

# argv[0] = hdd0:__common:pfs:/POPS/GAME.ELF, POPS.ELF and IOPRP252.IMG in
# hdd0:__common:pfs:/POPS, GAME.VCD in hdd0:__.POPS, no game folder yet.
HDD = START + _lines("""
    871ae4 SifExecModuleBuffer 0x2a25 bytes -> started
    871b34 SifExecModuleBuffer 0x23b1 bytes -> started
    871b8c SifExecModuleBuffer 0xecd bytes -> started
    871bdc SifExecModuleBuffer 0x3389 bytes -> started
    871c2c SifExecModuleBuffer 0x3159 bytes -> started
    871c7c SifExecModuleBuffer 0x7a91 bytes -> started
    871ccc SifExecModuleBuffer 0xcd55 bytes -> started
    8d801c fileXioDevctl pfs: 0x5003 -> 0
    8d8028 fileXioUmount pfs0: -> -2
    8d8034 fileXioUmount pfs1: -> -2
    8d8b40 fileXioUmount pfs1: -> -2
    8d8b6c fileXioMount pfs1: = hdd0:__common -> 0
    8d7eac fileXioGetStat pfs1:/POPS/ -> 0
    8d7fa8 fileXioChStat pfs1:/POPS/ -> 0
    8d7fbc fileXioChStat pfs1:/POPS/ -> 0
    87dad8 fileXioOpen pfs1:/POPS/POPS.ELF -> ok
    87df88 fileXioOpen pfs1:/POPS/IOPRP252.IMG -> ok
    875bec fileXioUmount pfs0: -> -2
    875c20 fileXioMount pfs0: = hdd0:__.POPS -> 0
    875c98 fileXioOpen pfs0:GAME.VCD -> ok
    87e4f8 fileXioOpen pfs1:/POPS/IGR_BG.TM2 -> -2
    87e71c fileXioOpen pfs1:/POPS/IGR_NO.TM2 -> -2
    87e928 fileXioOpen pfs1:/POPS/IGR_YES.TM2 -> -2
    87f0b8 fileXioOpen pfs1:/POPS/OSD.BIN -> -2
    8807bc fileXioOpen pfs1:/POPS/BIOS.BIN -> -2
    881134 fileXioOpen pfs1:/POPS/TROJAN_{0..9}.BIN -> -2
    882484 fileXioOpen pfs1:/POPS/PATCH_{0..9}.BIN -> -2
    8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> -2
    8d7ed4 fileXioMkdir pfs1:/POPS/GAME/ -> 0
    8d7ee4 fileXioGetStat pfs1:/POPS/GAME/ -> 0
    8d7f10 fileXioChStat pfs1:/POPS/GAME/ -> 0
    8d7f24 fileXioChStat pfs1:/POPS/GAME/ -> 0
    883828 fileXioOpen pfs1:/POPS/CHEATS.TXT -> -2
    8d5534 fileXioOpen pfs1:/POPS/VMCDIR.TXT -> -2
    8d6268 fileXioOpen pfs1:/POPS/DISCS.TXT -> -2
    8777f4..878890 fileXioOpen pfs1:/POPS/MODULE_{0..9}.IRX -> -2
    8d878c fileXioGetStat pfs1:/POPS/GAME/ -> 0
    8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> 0
    8d7fa8 fileXioChStat pfs1:/POPS/GAME/ -> 0
    8d7fbc fileXioChStat pfs1:/POPS/GAME/ -> 0
    8d87e4 fileXioOpen pfs1:/POPS/GAME/icon.sys -> -2
    8d8808 fileXioOpen pfs1:/POPS/GAME/icon.sys [create] -> ok
    8d8828 fileXioWrite hdd0:__common:pfs:/POPS/GAME/icon.sys -> 0x3c4 bytes
    8d8860 fileXioOpen pfs1:/POPS/GAME/list.ico -> -2
    8d8884 fileXioOpen pfs1:/POPS/GAME/list.ico [create] -> ok
    8d88a0 fileXioWrite hdd0:__common:pfs:/POPS/GAME/list.ico -> 0x8158 bytes
    8d801c fileXioDevctl pfs: 0x5003 -> 0
    8d8028 fileXioUmount pfs0: -> 0
    8d8034 fileXioUmount pfs1: -> 0
    87a78c SifIopReset 'rom0:UDNL '
    87a7f4 SifIopReset 'rom0:UDNL '
    87a900 SifLoadModuleBuffer buffer 0x100000 -> loaded
    87c1cc ExecPS2 entry 0x200000 gp 0x0 argc 1
""")

# The plain-name image search of HDD, and what replaces it for argv[0] =
# hdd0:PP.GAME:pfs:/PP.GAME.ELF with IMAGE0.VCD in hdd0:PP.GAME. Everything
# else of that run is the HDD list above, line for line.
HDD_IMAGE = _lines("""
    875bec fileXioUmount pfs0: -> -2
    875c20 fileXioMount pfs0: = hdd0:__.POPS -> 0
    875c98 fileXioOpen pfs0:GAME.VCD -> ok
""")
PP_IMAGE = _lines("""
    875684 fileXioMount pfs0: = hdd0:PP.GAME -> 0
    8756f4 fileXioOpen pfs0:IMAGE0.VCD -> ok
""")

# argv[0] = mass:/POPS/SB.GAME.ELF, SMBCONFIG.DAT and the five required
# network modules on mc0:/POPSTARTER, the share (seen as mass:) holding
# POPS/POPS_IOX.PAK and POPS/GAME.VCD.
SMB = START + _lines("""
    872228 SifExecModuleBuffer 0x2a25 bytes -> started
    872278 SifExecModuleBuffer 0x23b1 bytes -> started
    8722c0 fioOpen mc0:/POPSTARTER/IPCONFIG.DAT -> -2
    872380 fioOpen mc1:/POPSTARTER/IPCONFIG.DAT -> -2
    87263c fioOpen mc0:/POPSTARTER/SMBCONFIG.DAT -> ok
    873460 fioOpen mc0:/POPSTARTER/poweroff.irx -> ok
    873588 SifExecModuleBuffer 0x1000 bytes -> started
    8735c8 fioOpen mc0:/POPSTARTER/ps2dev9.irx -> ok
    8736f0 SifExecModuleBuffer 0x1000 bytes -> started
    873730 fioOpen mc0:/POPSTARTER/smsutils.irx -> -2
    8737f8 fioOpen mc1:/POPSTARTER/smsutils.irx -> -2
    8738b8 fioOpen mc0:/POPSTARTER/ps2ip.irx -> ok
    8739e0 SifExecModuleBuffer 0x1000 bytes -> started
    873a20 fioOpen mc0:/POPSTARTER/ps2smap.irx -> ok
    873b78 SifExecModuleBuffer 0x1000 bytes -> started
    873bc8 fioOpen mc0:/POPSTARTER/smbman.irx -> ok
    873ec4 SifExecModuleBuffer 0x1000 bytes -> started
    874140 fileXioDevctl mass0: 0xc0de0002 '192.168.0.2' -> 0
    874170 fileXioDevctl mass0: 0xc0de0007 'ALIVE ECHO TEST' -> 0
    8741a0 fileXioDevctl mass0: 0xc0de0005 'PS2SMB' -> 0
    87421c fioOpen mass:/POPS/POPS_IOX.PAK -> ok
    87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> ok
    87d350 unpack to 0x200000 -> 0x33ebb9 bytes
    8761d8 fioOpen mass:/POPS/GAME.VCD -> ok
    87e538 fioOpen mass:/POPS/IGR_BG.TM2 -> -2
    87e75c fioOpen mass:/POPS/IGR_NO.TM2 -> -2
    87e968 fioOpen mass:/POPS/IGR_YES.TM2 -> -2
    87f0d0 fioOpen mass:/POPS/OSD.BIN -> -2
    8807d4 fioOpen mass:/POPS/BIOS.BIN -> -2
    88114c fioOpen mass:/POPS/TROJAN_{0..9}.BIN -> -2
    88249c fioOpen mass:/POPS/PATCH_{0..9}.BIN -> -2
    87ee9c fioGetstat mass:/POPS/GAME/ -> -2
    883840 fioOpen mass:/POPS/CHEATS.TXT -> -2
    8d554c fioOpen mass:/POPS/VMCDIR.TXT -> -2
    8d6280 fioOpen mass:/POPS/DISCS.TXT -> -2
    8775b0 fioOpen mass:/POPS/iomanx.irx -> -2
    8776d8 fioOpen mass:/POPS/filexio.irx -> -2
    877834..8788d0 fioOpen mass:/POPS/MODULE_{0..9}.IRX -> -2
    8d8418 fileXioGetStat mass0:/POPS/GAME -> -2
    8d8430 fileXioMkdir mass0:/POPS/GAME -> 0
    8d865c fileXioOpen mass0:/POPS/GAME/SLOT0.VMC -> -2
    8d8680 fileXioOpen mass0:/POPS/GAME/SLOT0.VMC [create] -> ok
    8d869c fileXioWrite mass:/POPS/GAME/SLOT0.VMC -> 0x20000 bytes
    8d86e8 fileXioOpen mass0:/POPS/GAME/SLOT1.VMC -> -2
    8d870c fileXioOpen mass0:/POPS/GAME/SLOT1.VMC [create] -> ok
    8d8728 fileXioWrite mass:/POPS/GAME/SLOT1.VMC -> 0x20000 bytes
    878f1c fileXioDevctl mass0: 0xc0de0006 -> 0
    878f3c fileXioDevctl mass0: 0xc0de0003 -> 0
    87a78c SifIopReset 'rom0:UDNL '
    87a7f4 SifIopReset 'rom0:UDNL '
    87a900 SifLoadModuleBuffer buffer 0x100000 -> loaded
    87ae88 SifExecModuleBuffer 0x2a25 bytes -> started
    87af5c SifExecModuleBuffer 0x23b1 bytes -> started
    87b614 SifExecModuleBuffer 0x1000 bytes -> started
    87b678 SifExecModuleBuffer 0x1000 bytes -> started
    87b750 SifExecModuleBuffer 0x1000 bytes -> started
    87b7e4 SifExecModuleBuffer 0x1000 bytes -> started
    87b848 SifExecModuleBuffer 0x1000 bytes -> started
    87b8b8 fileXioDevctl mass0: 0xc0de0002 '192.168.0.2' -> 0
    87b8e0 fileXioDevctl mass0: 0xc0de0007 'ALIVE ECHO TEST' -> 0
    87b908 fileXioDevctl mass0: 0xc0de0005 'PS2SMB' -> 0
    87c054 SifExecModuleBuffer 0xa45 bytes -> started
    87c1cc ExecPS2 entry 0x200000 gp 0x0 argc 1
""")


def upto(lines, last):
    """The list through the line `last`, inclusive."""
    return lines[:lines.index(last) + 1]


def swapped(lines, old, new):
    at = lines.index(old[0])
    assert lines[at:at + len(old)] == old
    return lines[:at] + new + lines[at + len(old):]


USB_VMC = {"mass:/POPS/GAME/SLOT0.VMC": 0x20000, "mass:/POPS/GAME/SLOT1.VMC": 0x20000}
HDD_ICON = {"hdd0:__common:pfs:/POPS/GAME/icon.sys": 0x3C4,
            "hdd0:__common:pfs:/POPS/GAME/list.ico": 0x8158}
T72, T73 = "T" * 72, "T" * 73

# Every case of T.CASES: (focus, lines, state, files written).
#   focus  FULL: every line of the run is compared; CASE: the case's own
#          focus (T.CASES[name]["focus"], the lines that case is about).
#   state  launch type (gp+0x3414), mass mode (gp+0x3448), SB (gp+0x3888),
#          physical disc (gp+0x3410), numbered folder in use (gp+0x381c),
#          its digit (gp+0x38b8), quiet (gp+0x38b0).
FULL, CASE = "full", "case"
CASE_TABLE = {
    "usb": (FULL, USB, (3, 1, 0, 0, 0, "", 1), USB_VMC),
    "hdd": (FULL, HDD, (0, 0, 0, 0, 0, "", 1), HDD_ICON),
    "hdd-pp": (FULL, swapped(HDD, HDD_IMAGE, PP_IMAGE), (2, 0, 0, 0, 0, "", 1), HDD_ICON),
    "smb": (FULL, SMB, (3, 1, 3, 0, 0, "", 0), USB_VMC),
    # The game's folder is there, with both memory cards: the per-game
    # copies of the optional files are asked for, and nothing is written.
    "usb-folder": (FULL, upto(USB, "88249c fioOpen mass:/POPS/PATCH_{0..9}.BIN -> -2") + _lines("""
        87ee9c fioGetstat mass:/POPS/GAME/ -> 0
        87f0d0 fioOpen mass:/POPS/GAME/OSD.BIN -> -2
        8807d4 fioOpen mass:/POPS/GAME/BIOS.BIN -> -2
        88114c fioOpen mass:/POPS/GAME/TROJAN_{0..9}.BIN -> -2
        88249c fioOpen mass:/POPS/GAME/PATCH_{0..9}.BIN -> -2
        883840 fioOpen mass:/POPS/CHEATS.TXT -> -2
        883840 fioOpen mass:/POPS/GAME/CHEATS.TXT -> -2
        8d554c fioOpen mass:/POPS/VMCDIR.TXT -> -2
        8d554c fioOpen mass:/POPS/GAME/VMCDIR.TXT -> -2
        8d6280 fioOpen mass:/POPS/DISCS.TXT -> -2
        8d6280 fioOpen mass:/POPS/GAME/DISCS.TXT -> -2
        877834..8788d0 fioOpen mass:/POPS/MODULE_{0..9}.IRX -> -2
        8d83c0 fioGetstat mass0:/POPS/GAME -> 0
        8d8d2c fioOpen mass0:/POPS/GAME/SLOT0.VMC -> ok
        8d8d2c fioOpen mass0:/POPS/GAME/SLOT1.VMC -> ok
        879e5c stop
    """), (3, 1, 0, 0, 0, "", 1), {}),
    # The game's folder is there with icon.sys and list.ico: nothing is
    # made or written, and no SLOTn.VMC is asked for on this kind.
    "hdd-folder": (FULL, upto(HDD, "882484 fileXioOpen pfs1:/POPS/PATCH_{0..9}.BIN -> -2") + _lines("""
        8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> 0
        8d7fa8 fileXioChStat pfs1:/POPS/GAME/ -> 0
        8d7fbc fileXioChStat pfs1:/POPS/GAME/ -> 0
        87f0b8 fileXioOpen pfs1:/POPS/GAME/OSD.BIN -> -2
        8807bc fileXioOpen pfs1:/POPS/GAME/BIOS.BIN -> -2
        881134 fileXioOpen pfs1:/POPS/GAME/TROJAN_{0..9}.BIN -> -2
        882484 fileXioOpen pfs1:/POPS/GAME/PATCH_{0..9}.BIN -> -2
        883828 fileXioOpen pfs1:/POPS/CHEATS.TXT -> -2
        883828 fileXioOpen pfs1:/POPS/GAME/CHEATS.TXT -> -2
        8d5534 fileXioOpen pfs1:/POPS/VMCDIR.TXT -> -2
        8d5534 fileXioOpen pfs1:/POPS/GAME/VMCDIR.TXT -> -2
        8d6268 fileXioOpen pfs1:/POPS/DISCS.TXT -> -2
        8d6268 fileXioOpen pfs1:/POPS/GAME/DISCS.TXT -> -2
        8777f4..878890 fileXioOpen pfs1:/POPS/MODULE_{0..9}.IRX -> -2
        8d878c fileXioGetStat pfs1:/POPS/GAME/ -> 0
        8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> 0
        8d7fa8 fileXioChStat pfs1:/POPS/GAME/ -> 0
        8d7fbc fileXioChStat pfs1:/POPS/GAME/ -> 0
        8d87e4 fileXioOpen pfs1:/POPS/GAME/icon.sys -> ok
        8d8860 fileXioOpen pfs1:/POPS/GAME/list.ico -> ok
        8d801c fileXioDevctl pfs: 0x5003 -> 0
        8d8028 fileXioUmount pfs0: -> 0
        8d8034 fileXioUmount pfs1: -> 0
        879e5c stop
    """), (0, 0, 0, 0, 0, "", 1), {}),
    # The image is only in mass:/POPS4, and mass:/POPS4/GAME exists: the
    # digit moves everything except the IGR skin and MODULE_n.IRX.
    "usb-pops4": (FULL, upto(USB, "87d350 unpack to 0x200000 -> 0x33ebb9 bytes") + _lines("""
        8761d8 fioOpen mass:/POPS/GAME.VCD -> -2
        876354 fioOpen mass:/POPS{0..3}/GAME.VCD -> -2
        876354 fioOpen mass:/POPS4/GAME.VCD -> ok
        87e538 fioOpen mass:/POPS/IGR_BG.TM2 -> -2
        87e75c fioOpen mass:/POPS/IGR_NO.TM2 -> -2
        87e968 fioOpen mass:/POPS/IGR_YES.TM2 -> -2
        87f0d0 fioOpen mass:/POPS4/OSD.BIN -> -2
        8807d4 fioOpen mass:/POPS4/BIOS.BIN -> -2
        88114c fioOpen mass:/POPS4/TROJAN_{0..9}.BIN -> -2
        88249c fioOpen mass:/POPS4/PATCH_{0..9}.BIN -> -2
        87ee9c fioGetstat mass:/POPS4/GAME/ -> 0
        87f0d0 fioOpen mass:/POPS4/GAME/OSD.BIN -> -2
        8807d4 fioOpen mass:/POPS4/GAME/BIOS.BIN -> -2
        88114c fioOpen mass:/POPS4/GAME/TROJAN_{0..9}.BIN -> -2
        88249c fioOpen mass:/POPS4/GAME/PATCH_{0..9}.BIN -> -2
        883840 fioOpen mass:/POPS4/CHEATS.TXT -> -2
        883840 fioOpen mass:/POPS4/GAME/CHEATS.TXT -> -2
        8d554c fioOpen mass:/POPS4/VMCDIR.TXT -> -2
        8d554c fioOpen mass:/POPS4/GAME/VMCDIR.TXT -> -2
        8d6280 fioOpen mass:/POPS4/DISCS.TXT -> -2
        8d6280 fioOpen mass:/POPS4/GAME/DISCS.TXT -> -2
        877834..8788d0 fioOpen mass:/POPS/MODULE_{0..9}.IRX -> -2
        8d83c0 fioGetstat mass0:/POPS4/GAME -> 0
        8d8d2c fioOpen mass0:/POPS4/GAME/SLOT0.VMC -> -2
        8d8d2c fioOpen mass0:/POPS4/GAME/SLOT0.VMC [create] -> ok
        8d8d9c fioWrite mass:/POPS4/GAME/SLOT0.VMC -> 0x20000 bytes
        8d8d2c fioOpen mass0:/POPS4/GAME/SLOT1.VMC -> -2
        8d8d2c fioOpen mass0:/POPS4/GAME/SLOT1.VMC [create] -> ok
        8d8d9c fioWrite mass:/POPS4/GAME/SLOT1.VMC -> 0x20000 bytes
        879e5c stop
    """), (3, 1, 0, 0, 1, "4", 1),
        {"mass:/POPS4/GAME/SLOT0.VMC": 0x20000, "mass:/POPS4/GAME/SLOT1.VMC": 0x20000}),
    # -- the image search when nothing is found -----------------------------
    "usb-no-vcd": (CASE, _lines("""
        8761d8 fioOpen mass:/POPS/GAME.VCD -> -2
        876354 fioOpen mass:/POPS{0..9}/GAME.VCD -> -2
        8767d4 sceCdGetDiskType (0, 0) -> 0
        876a0c fatal
    """), (3, 1, 0, 1, 0, "", 1), {}),
    # hdd0:__.POPS2 does not exist: the failed mount goes on to the next digit.
    "hdd-pops3": (CASE, _lines("""
        8d8b6c fileXioMount pfs1: = hdd0:__common -> 0
        875c20 fileXioMount pfs0: = hdd0:__.POPS -> 0
        875c98 fileXioOpen pfs0:GAME.VCD -> -2
        875e28 fileXioMount pfs0: = hdd0:__.POPS0 -> 0
        875ea0 fileXioOpen pfs0:GAME.VCD -> -2
        875e28 fileXioMount pfs0: = hdd0:__.POPS1 -> 0
        875ea0 fileXioOpen pfs0:GAME.VCD -> -2
        875e28 fileXioMount pfs0: = hdd0:__.POPS2 -> -2
        875e28 fileXioMount pfs0: = hdd0:__.POPS3 -> 0
        875ea0 fileXioOpen pfs0:GAME.VCD -> ok
        8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> -2
        8d7ed4 fileXioMkdir pfs1:/POPS/GAME/ -> 0
        8d7ee4 fileXioGetStat pfs1:/POPS/GAME/ -> 0
        8d7f10 fileXioChStat pfs1:/POPS/GAME/ -> 0
        8d7f24 fileXioChStat pfs1:/POPS/GAME/ -> 0
        8d878c fileXioGetStat pfs1:/POPS/GAME/ -> 0
        8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> 0
        8d7fa8 fileXioChStat pfs1:/POPS/GAME/ -> 0
        8d7fbc fileXioChStat pfs1:/POPS/GAME/ -> 0
        8d87e4 fileXioOpen pfs1:/POPS/GAME/icon.sys -> -2
        8d8808 fileXioOpen pfs1:/POPS/GAME/icon.sys [create] -> ok
        8d8828 fileXioWrite hdd0:__common:pfs:/POPS/GAME/icon.sys -> 0x3c4 bytes
        8d8860 fileXioOpen pfs1:/POPS/GAME/list.ico -> -2
        8d8884 fileXioOpen pfs1:/POPS/GAME/list.ico [create] -> ok
        8d88a0 fileXioWrite hdd0:__common:pfs:/POPS/GAME/list.ico -> 0x8158 bytes
        879e5c stop
    """), (0, 0, 0, 0, 0, "", 1), HDD_ICON),
    "hdd-no-vcd": (CASE, _lines("""
        8d8b6c fileXioMount pfs1: = hdd0:__common -> 0
        875c20 fileXioMount pfs0: = hdd0:__.POPS -> 0
        875c98 fileXioOpen pfs0:GAME.VCD -> -2
    """) + [line for digit in range(10) for line in (
        "875e28 fileXioMount pfs0: = hdd0:__.POPS%d -> 0" % digit,
        "875ea0 fileXioOpen pfs0:GAME.VCD -> -2")] + _lines("""
        8767d4 sceCdGetDiskType (0, 0) -> 0
        876a0c fatal
    """), (0, 0, 0, 1, 0, "", 1), {}),
    "hdd-pp-no-vcd": (CASE, _lines("""
        8d8b6c fileXioMount pfs1: = hdd0:__common -> 0
        875684 fileXioMount pfs0: = hdd0:PP.GAME -> 0
        8756f4 fileXioOpen pfs0:IMAGE0.VCD -> -2
        8767d4 sceCdGetDiskType (0, 0) -> 0
        876a0c fatal
    """), (2, 0, 0, 1, 0, "", 1), {}),
    # -- no image, a disc the drive reports as type 0x10 --------------------
    "usb-disc": (CASE, _lines("""
        8761d8 fioOpen mass:/POPS/GAME.VCD -> -2
        876354 fioOpen mass:/POPS{0..9}/GAME.VCD -> -2
        8767a8 sceCdInit (1, 0) -> 1
        8767b0 sceCdSync (0, 0) -> 0
        8767b8 sceCdStatus (0, 0) -> 0
        8767d4 sceCdGetDiskType (0, 0) -> 16
        876838 sceCdSync (0, 0) -> 0
        876840 sceCdDiskReady (0, 0) -> 2
        876848 sceCdSync (0, 0) -> 0
        876860 sceCdRead (4, 1) -> 0
        876868 sceCdSync (0, 1) -> 0
        8ff26c sceCdSync (0, 0) -> 0
        8ff274 sceCdDiskReady (0, 0) -> 2
        8ff27c sceCdSync (0, 0) -> 0
        8ff294 sceCdRead (16, 1) -> 0
        8ff29c sceCdSync (0, 1) -> 0
        8ff2dc sceCdSync (0, 0) -> 0
        8ff2e4 sceCdDiskReady (0, 0) -> 2
        8ff2ec sceCdSync (0, 0) -> 0
        8ff304 sceCdRead (22, 1) -> 0
        8ff30c sceCdSync (0, 1) -> 0
        87ee9c fioGetstat mass:/POPS/GAME/ -> -2
        8774d4 sceCdInit (5, 0) -> 1
        8d83c0 fioGetstat mass0:/POPS/GAME -> -2
        8d83d4 fioMkdir mass0:/POPS/GAME -> 0
        8d8d2c fioOpen mass0:/POPS/GAME/SLOT0.VMC -> -2
        8d8d2c fioOpen mass0:/POPS/GAME/SLOT0.VMC [create] -> ok
        8d8d9c fioWrite mass:/POPS/GAME/SLOT0.VMC -> 0x20000 bytes
        8d8d2c fioOpen mass0:/POPS/GAME/SLOT1.VMC -> -2
        8d8d2c fioOpen mass0:/POPS/GAME/SLOT1.VMC [create] -> ok
        8d8d9c fioWrite mass:/POPS/GAME/SLOT1.VMC -> 0x20000 bytes
        879e5c stop
    """), (3, 1, 0, 1, 0, "", 1), USB_VMC),
    "usb-tray": (CASE, _lines("""
        8767a8 sceCdInit (1, 0) -> 1
        8767b0 sceCdSync (0, 0) -> 0
        8767b8 sceCdStatus (0, 0) -> 1
        876a38 fatal
    """), (3, 1, 0, 1, 0, "", 1), {}),
    # -- what stops a launch before the image is looked for -----------------
    "usb-no-pops-folder": (CASE, _lines("""
        871d6c fioOpen mc0:/POPSTARTER/usbd.irx -> -2
        871e28 fioOpen mc1:/POPSTARTER/usbd.irx -> -2
        871f20 fioOpen mc0:/POPSTARTER/usbhdfsd.irx -> -2
        871fdc fioOpen mc1:/POPSTARTER/usbhdfsd.irx -> -2
        8d8a68 fioGetstat mass:/POPS -> -2
        8d8a7c fioMkdir mass0:/POPS -> 0
        8740a0 fatal
    """), (0, 1, 0, 0, 0, "", 1), {}),
    "hdd-no-common": (CASE, _lines("""
        8d8b6c fileXioMount pfs1: = hdd0:__common -> -2
        873f88 fatal
    """), (0, 0, 0, 0, 0, "", 1), {}),
    "hdd-no-pops-folder": (CASE, _lines("""
        8d8b6c fileXioMount pfs1: = hdd0:__common -> 0
        8d7eac fileXioGetStat pfs1:/POPS/ -> -2
        8d7ed4 fileXioMkdir pfs1:/POPS/ -> 0
        8d7ee4 fileXioGetStat pfs1:/POPS/ -> 0
        8d7f10 fileXioChStat pfs1:/POPS/ -> 0
        8d7f24 fileXioChStat pfs1:/POPS/ -> 0
        8740a0 fatal
    """), (0, 0, 0, 0, 0, "", 1), {}),
    "smb-no-config": (CASE, _lines("""
        8722c0 fioOpen mc0:/POPSTARTER/IPCONFIG.DAT -> -2
        872380 fioOpen mc1:/POPSTARTER/IPCONFIG.DAT -> -2
        87263c fioOpen mc0:/POPSTARTER/SMBCONFIG.DAT -> -2
        8726fc fioOpen mc1:/POPSTARTER/SMBCONFIG.DAT -> -2
        8727d4 fatal
    """), (0, 1, 3, 0, 0, "", 0), {}),
    # First line of SMBCONFIG.DAT without a space between address and share.
    "smb-bad-config": (CASE, _lines("""
        8722c0 fioOpen mc0:/POPSTARTER/IPCONFIG.DAT -> -2
        872380 fioOpen mc1:/POPSTARTER/IPCONFIG.DAT -> -2
        87263c fioOpen mc0:/POPSTARTER/SMBCONFIG.DAT -> ok
        872c7c fatal
    """), (0, 1, 3, 0, 0, "", 0), {}),
    # Only POPS.PAK on the share: SB. takes POPS_IOX.PAK or nothing.
    "smb-no-iox": (CASE, _lines("""
        874140 fileXioDevctl mass0: 0xc0de0002 '192.168.0.2' -> 0
        874170 fileXioDevctl mass0: 0xc0de0007 'ALIVE ECHO TEST' -> 0
        8741a0 fileXioDevctl mass0: 0xc0de0005 'PS2SMB' -> 0
        87421c fioOpen mass:/POPS/POPS_IOX.PAK -> -2 (119 times)
        874210 fatal
    """), (0, 1, 3, 0, 0, "", 0), {}),
    "smb-no-modules": (CASE, _lines("""
        8722c0 fioOpen mc0:/POPSTARTER/IPCONFIG.DAT -> -2
        872380 fioOpen mc1:/POPSTARTER/IPCONFIG.DAT -> -2
        87263c fioOpen mc0:/POPSTARTER/SMBCONFIG.DAT -> ok
        873460 fioOpen mc0:/POPSTARTER/poweroff.irx -> -2
        8734dc fioOpen mc1:/POPSTARTER/poweroff.irx -> -2
        873570 fatal
    """), (0, 1, 3, 0, 0, "", 0), {}),
    # -- POPS package search and acceptance ---------------------------------
    "usb-pak": (CASE, _lines("""
        87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> -2
        87d5a0 fioOpen mass:/POPS/POPS.PAK -> ok
        87d8a0 unpack to 0x200000 -> 0x343a71 bytes
        879e5c stop
    """), (3, 1, 0, 0, 0, "", 1), USB_VMC),
    "usb-elf": (CASE, _lines("""
        87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> -2
        87d5a0 fioOpen mass:/POPS/POPS.PAK -> -2
        87db18 fioOpen mass:/POPS/POPS.ELF -> ok
        87dfc8 fioOpen mass:/POPS/IOPRP252.IMG -> ok
        879e5c stop
    """), (3, 1, 0, 0, 0, "", 1), USB_VMC),
    # Zero-filled files one byte longer than the accepted sizes
    # (0xe50b8, 0xe6240, 0x30530c): each is opened and passed over.
    "usb-iox-size": (CASE, _lines("""
        87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> ok
        87d5a0 fioOpen mass:/POPS/POPS.PAK -> ok
        87db18 fioOpen mass:/POPS/POPS.ELF -> ok
        874404 fatal
    """), (3, 1, 0, 0, 0, "", 1), {}),
    "usb-elf-no-ioprp": (CASE, _lines("""
        87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> -2
        87d5a0 fioOpen mass:/POPS/POPS.PAK -> -2
        87db18 fioOpen mass:/POPS/POPS.ELF -> ok
        87dfc8 fioOpen mass:/POPS/IOPRP252.IMG -> -2
        87e06c fioOpen mass:/POPS/IOPRP.IMG -> -2
        874404 fatal
    """), (3, 1, 0, 0, 0, "", 1), {}),
    # Both packs are in hdd0:__common:pfs:/POPS; neither is asked for.
    "hdd-no-package": (CASE, _lines("""
        87dad8 fileXioOpen pfs1:/POPS/POPS.ELF -> -2
        874404 fatal
    """), (0, 0, 0, 0, 0, "", 1), {}),
    "hdd-ioprp-img": (CASE, _lines("""
        87dad8 fileXioOpen pfs1:/POPS/POPS.ELF -> ok
        87df88 fileXioOpen pfs1:/POPS/IOPRP252.IMG -> -2
        87e02c fileXioOpen pfs1:/POPS/IOPRP.IMG -> ok
        879e5c stop
    """), (0, 0, 0, 0, 0, "", 1), HDD_ICON),
    # Zero-filled files of plausible size: content is checked, not only size.
    "hdd-ioprp-zero": (CASE, _lines("""
        87dad8 fileXioOpen pfs1:/POPS/POPS.ELF -> ok
        87df88 fileXioOpen pfs1:/POPS/IOPRP252.IMG -> ok
        874404 fatal
    """), (0, 0, 0, 0, 0, "", 1), {}),
    "hdd-elf-zero": (CASE, _lines("""
        87dad8 fileXioOpen pfs1:/POPS/POPS.ELF -> ok
        874404 fatal
    """), (0, 0, 0, 0, 0, "", 1), {}),
    # -- name length: a title of 72 characters is the longest accepted ------
    "usb-72": (CASE, ["8761d8 fioOpen mass:/POPS/%s.VCD -> ok" % T72, "879e5c stop"],
               (3, 1, 0, 0, 0, "", 1),
               {"mass:/POPS/%s/SLOT0.VMC" % T72: 0x20000, "mass:/POPS/%s/SLOT1.VMC" % T72: 0x20000}),
    "usb-73": (CASE, ["875aa8 fatal"], (3, 1, 0, 0, 0, "", 1), {}),
    "hdd-72": (CASE, ["875c98 fileXioOpen pfs0:%s.VCD -> ok" % T72, "879e5c stop"],
               (0, 0, 0, 0, 0, "", 1),
               {"hdd0:__common:pfs:/POPS/%s/icon.sys" % T72: 0x3C4,
                "hdd0:__common:pfs:/POPS/%s/list.ico" % T72: 0x8158}),
    "hdd-73": (CASE, ["875aa8 fatal"], (0, 0, 0, 0, 0, "", 1), {}),
}

# ---------------------------------------------------------------------------
# argv[0] forms: the original's result, launcHER's result, the difference
# ---------------------------------------------------------------------------
# Original (measured with both POPS installations present, every partition
# mountable and no image anywhere, so a run walks its whole search):
#   type    gp+0x3414: 0 plain name, 1 PATINFO/EXECUTE/LAUNCHER, 2 PP./__.,
#           3 XX./SB.
#   mass    gp+0x3448; smb: gp+0x3888 (3 on SB.)
#   search  (USB, title)   mass:/POPS/<title>.VCD, then mass:/POPS0/ ..
#                          mass:/POPS9/<title>.VCD
#           (HDD, title)   hdd0:__.POPS:pfs:/<title>.VCD, then hdd0:__.POPS0
#                          .. hdd0:__.POPS9
#           (PART, name)   hdd0:<name>:pfs:/IMAGE0.VCD and nothing else
#           None           it stops before looking for an image
#   end     where the run ended: NO_DISC is the "no image, no PS1 disc" stop
#           every complete search reaches in this setting.
# launcHER (pops_resolve_candidate_targets_bdma(argv0, NULL, .., 16, none)):
#   prefix  what pops_is_xx/sb/pp_prefix say; count: candidates returned;
#   first   the first candidate
#   at      index of the original's first location in launcHER's list, None
#           when it is not there, "-" when the original has no search. Unit
#           0 of mass is taken as mass (mass0: == mass:), and on SB. rows
#           launcHER's share names smb0:/smb: are taken as the original's
#           mass:, which is the share there.
# The original's ten numbered locations are in none of launcHER's lists
# (Native.test_numbered_locations_are_never_candidates).
USB_SEARCH, HDD_SEARCH, PART = "usb", "hdd", "part"
NO_DISC, NOT_FOUND, EXIT = "fatal 876a0c", "fatal 874358", "exit 8713c8"
Form = namedtuple("Form", "argv type mass smb search end prefix count first at difference")

D_RETRY_USB = "launcHER has no mass:/POPS0..9 retry; it adds IMAGE.VCD and other devices"
D_RETRY_HDD = ("launcHER has no hdd0:__.POPS0..9 retry; it adds IMAGE.VCD, pfs0:, "
               "hdd0:PP.<title> and other devices")
D_MIXED = ("the original accepts XX. and xx. only: this name is a plain HDD title for it, "
           "prefix included; launcHER takes it as XX.")
D_DIR = ("the original always looks in mass:/POPS; launcHER tries the ELF's own folder "
         "first")
D_SMB = ("same first file (the share's POPS folder); launcHER has no POPS0..9 retry and "
         "falls back to mass and hdd0:__.POPS")
D_PP = ("the original opens only IMAGE0.VCD in the partition named by the ELF; launcHER "
        "asks for <title>.VCD, IMAGE.VCD and others, never IMAGE0.VCD")
D_PP_LOWER = ("the original accepts PP. only in upper case, directly under :pfs:/ or after "
              "a / off hdd0: here it is a plain HDD title, prefix included; launcHER takes "
              "it as PP.")
D_TYPE1 = ("the original takes the partition from argv[0] and opens its IMAGE0.VCD; "
           "launcHER treats EXECUTE/LAUNCHER as a title")
D_PATINFO = ("the original takes the partition from argv[0] and opens its IMAGE0.VCD; "
             "launcHER's main() hands every ':PATINFO' argv[0] to its generic PATINFO "
             "handler before any POPS resolution")
D_STOP = "the original stops (\"Cannot set up the POPS launcher\"); launcHER builds candidates"

FORM_TABLE = [
    Form("mass:/POPS/XX.GAME.ELF", 3, 1, 0, (USB_SEARCH, "GAME"), NO_DISC,
         "XX", 10, "mass0:/POPS/GAME.VCD", 0, D_RETRY_USB),
    Form("mass:/XX.GAME.ELF", 3, 1, 0, (USB_SEARCH, "GAME"), NO_DISC,
         "XX", 12, "mass0:/GAME.VCD", 4, D_DIR),
    Form("mass:/POPS/xx.GAME.ELF", 3, 1, 0, (USB_SEARCH, "GAME"), NO_DISC,
         "XX", 10, "mass0:/POPS/GAME.VCD", 0, D_RETRY_USB),
    Form("mass:/POPS/Xx.GAME.ELF", 0, 0, 0, (HDD_SEARCH, "Xx.GAME"), NO_DISC,
         "XX", 10, "mass0:/POPS/GAME.VCD", None, D_MIXED),
    Form("mass:/POPS/xX.GAME.ELF", 0, 0, 0, (HDD_SEARCH, "xX.GAME"), NO_DISC,
         "XX", 10, "mass0:/POPS/GAME.VCD", None, D_MIXED),
    Form("mass:/POPS/XX.Game.elf", 3, 1, 0, (USB_SEARCH, "Game"), NO_DISC,
         "XX", 10, "mass0:/POPS/Game.VCD", 0, D_RETRY_USB),
    Form("mass:\\POPS\\XX.GAME.ELF", 3, 1, 0, (USB_SEARCH, "GAME"), NO_DISC,
         "XX", 10, "mass0:\\POPS/GAME.VCD", None,
         "the original builds mass:/POPS/GAME.VCD whatever the separators; launcHER keeps "
         "the backslash of the ELF's folder in its first four candidates"),
    Form("mass:XX.GAME.ELF", 3, 1, 0, (USB_SEARCH, "GAME"), NO_DISC,
         "XX", 12, "mass0:/GAME.VCD", 4, D_DIR),
    Form("mass0:/POPS/XX.GAME.ELF", 3, 1, 0, (USB_SEARCH, "GAME"), NO_DISC,
         "XX", 7, "mass0:/POPS/GAME.VCD", 0, D_RETRY_USB),
    Form("hdd0:__common:pfs:/POPS/XX.GAME.ELF", 3, 1, 0, (USB_SEARCH, "GAME"), NO_DISC,
         "XX", 11, "hdd0:__common:pfs:/POPS/GAME.VCD", 5,
         "XX. means USB for the original wherever the ELF is; launcHER tries the ELF's own "
         "HDD folder first"),
    Form("XX.GAME.ELF", 0, 0, 0, (HDD_SEARCH, "XX.GAME"), NO_DISC,
         "XX", 6, "mass0:/POPS/GAME.VCD", None,
         "without a ':', '/' or '\\' before it the original does not see the prefix: a "
         "plain HDD title \"XX.GAME\"; launcHER takes it as XX."),
    Form("GAME.ELF", 0, 0, 0, (HDD_SEARCH, "GAME"), NO_DISC,
         "none", 10, "hdd0:__.POPS:pfs:/GAME.VCD", 0, D_RETRY_HDD),
    Form("mass:/POPS/XX.GAME", 3, 1, 0, None, NOT_FOUND,
         "XX", 10, "mass0:/POPS/GAME.VCD", "-", D_STOP),
    Form("mass:/POPS/GAME.ELF", 0, 0, 0, (HDD_SEARCH, "GAME"), NO_DISC,
         "none", 14, "hdd0:__.POPS:pfs:/GAME.VCD", 0,
         "a plain name means hdd0:__.POPS for the original wherever the ELF is, and it "
         "never looks on mass:; launcHER goes on to the ELF's folder and mass"),
    Form("mc0:/BOOT/GAME.ELF", 0, 0, 0, (HDD_SEARCH, "GAME"), NO_DISC,
         "none", 14, "hdd0:__.POPS:pfs:/GAME.VCD", 0,
         "a plain name means hdd0:__.POPS for the original wherever the ELF is; launcHER "
         "goes on to the ELF's folder, mc and mass"),
    Form("mass:/POPS/SB.GAME.ELF", 3, 1, 3, (USB_SEARCH, "GAME"), NO_DISC,
         "SB", 7, "smb0:/POPS/GAME.VCD", 0, D_SMB),
    Form("mass:/POPS/sb.GAME.ELF", 3, 1, 3, (USB_SEARCH, "GAME"), NO_DISC,
         "SB", 7, "smb0:/POPS/GAME.VCD", 0, D_SMB),
    Form("mc0:/POPSTARTER/SB.GAME.ELF", 3, 1, 3, (USB_SEARCH, "GAME"), NO_DISC,
         "SB", 7, "smb0:/POPS/GAME.VCD", 0, D_SMB),
    Form("mass:/APPS/PP.GAME.ELF", 2, 0, 0, (PART, "PP.GAME"), NO_DISC,
         "PP", 9, "hdd0:PP.GAME:pfs:/GAME.VCD", None, D_PP),
    Form("mass:/APPS/__.GAME.ELF", 2, 0, 0, (PART, "__.GAME"), NO_DISC,
         "PP", 9, "hdd0:__.GAME:pfs:/GAME.VCD", None, D_PP),
    Form("mass:/APPS/pp.GAME.ELF", 0, 0, 0, (HDD_SEARCH, "pp.GAME"), NO_DISC,
         "PP", 9, "hdd0:PP.GAME:pfs:/GAME.VCD", None, D_PP_LOWER),
    Form("hdd0:__common:pfs:/POPS/GAME.ELF", 0, 0, 0, (HDD_SEARCH, "GAME"), NO_DISC,
         "none", 15, "hdd0:__.POPS:pfs:/GAME.VCD", 0, D_RETRY_HDD),
    Form("hdd0:PP.ALPHA:pfs:/PP.BETA.ELF", 2, 0, 0, (PART, "PP.BETA"), NO_DISC,
         "PP", 9, "hdd0:PP.BETA:pfs:/BETA.VCD", None, D_PP),
    Form("hdd0:PP.ALPHA:pfs:/__.BETA.ELF", 2, 0, 0, (PART, "__.BETA"), NO_DISC,
         "PP", 9, "hdd0:__.BETA:pfs:/BETA.VCD", None, D_PP),
    Form("hdd0:PP.ALPHA:pfs:/pp.BETA.ELF", 0, 0, 0, (HDD_SEARCH, "pp.BETA"), NO_DISC,
         "PP", 9, "hdd0:PP.BETA:pfs:/BETA.VCD", None, D_PP_LOWER),
    Form("hdd0:PP.ALPHA:pfs:/SUB/PP.BETA.ELF", 0, 0, 0, (HDD_SEARCH, "PP.BETA"), NO_DISC,
         "PP", 9, "hdd0:PP.BETA:pfs:/BETA.VCD", None, D_PP_LOWER),
    Form("hdd0:PP.ALPHA:pfs:/EXECUTE.KELF", 1, 0, 0, (PART, "PP.ALPHA"), NO_DISC,
         "none", 15, "hdd0:__.POPS:pfs:/EXECUTE.VCD", None, D_TYPE1),
    Form("hdd0:PP.ALPHA:pfs:/EXECUTE.ELF", 1, 0, 0, (PART, "PP.ALPHA"), NO_DISC,
         "none", 15, "hdd0:__.POPS:pfs:/EXECUTE.VCD", None, D_TYPE1),
    Form("hdd0:PP.ALPHA:pfs:/LAUNCHER.ELF", 1, 0, 0, (PART, "PP.ALPHA"), NO_DISC,
         "none", 15, "hdd0:__.POPS:pfs:/LAUNCHER.VCD", None, D_TYPE1),
    Form("hdd0:PP.ALPHA:pfs:/LAUNCHER.KELF", 1, 0, 0, (PART, "PP.ALPHA"), NO_DISC,
         "none", 15, "hdd0:__.POPS:pfs:/LAUNCHER.VCD", None, D_TYPE1),
    Form("hdd0:PP.ALPHA:pfs:/execute.kelf", 0, 0, 0, (HDD_SEARCH, "execute"), NO_DISC,
         "none", 15, "hdd0:__.POPS:pfs:/execute.VCD", 0, D_RETRY_HDD),
    Form("hdd0:PP.ALPHA:pfs:/SUB/EXECUTE.KELF", 1, 0, 0, (PART, "PP.ALPHA"), NO_DISC,
         "none", 15, "hdd0:__.POPS:pfs:/EXECUTE.VCD", None, D_TYPE1),
    Form("hdd0:ALPHA:pfs:/EXECUTE.KELF", 1, 0, 0, (PART, "ALPHA"), NO_DISC,
         "none", 15, "hdd0:__.POPS:pfs:/EXECUTE.VCD", None, D_TYPE1),
    Form("hdd0:PP.ALPHA:PATINFO", 1, 0, 0, (PART, "PP.ALPHA"), NO_DISC,
         "none", 15, "hdd0:__.POPS:pfs:/PATINFO.VCD", None, D_PATINFO),
    Form("hdd0:__.ALPHA:PATINFO", 1, 0, 0, (PART, "__.ALPHA"), NO_DISC,
         "none", 15, "hdd0:__.POPS:pfs:/PATINFO.VCD", None, D_PATINFO),
    Form("hdd0:ALPHA:PATINFO", 1, 0, 0, (PART, "ALPHA"), NO_DISC,
         "none", 15, "hdd0:__.POPS:pfs:/PATINFO.VCD", None, D_PATINFO),
    Form("hdd0:PP.ALPHA:patinfo", 0, 0, 0, None, NOT_FOUND,
         "none", 15, "hdd0:__.POPS:pfs:/patinfo.VCD", "-", D_STOP),
    Form("pfs0:/EXECUTE.KELF", 0, 0, 0, None, NOT_FOUND,
         "none", 12, "hdd0:__.POPS:pfs:/EXECUTE.VCD", "-",
         "the original stops (\"EXECUTE.KELF was not renamed\"); launcHER builds candidates"),
    Form("cdrom0:\\SLUS_000.00;1", 0, 0, 0, None, EXIT,
         "none", 14, "hdd0:__.POPS:pfs:/SLUS_000.VCD", "-",
         "the original calls Exit for an argv[0] starting \"cdrom\"; launcHER's resolver "
         "builds candidates (its main() sends \"cdrom\" to the disc handler only in OSDM "
         "builds)"),
    Form(None, 0, 0, 0, None, EXIT, "none", 0, None, "-",
         "argc == 0: the original calls Exit; launcHER's main() stops with \"Invalid "
         "launcher arguments\" (launcher_normalize_args() returns -1)"),
]


USB_GAME_SEARCH = [
    "mass:/POPS/GAME.VCD", "mass:/POPS0/GAME.VCD", "mass:/POPS1/GAME.VCD",
    "mass:/POPS2/GAME.VCD", "mass:/POPS3/GAME.VCD", "mass:/POPS4/GAME.VCD",
    "mass:/POPS5/GAME.VCD", "mass:/POPS6/GAME.VCD", "mass:/POPS7/GAME.VCD",
    "mass:/POPS8/GAME.VCD", "mass:/POPS9/GAME.VCD",
]


def original_search(search):
    """The pinned search of a row as the ordered list of locations."""
    if search is None:
        return []
    kind, name = search
    if kind == PART:
        return ["hdd0:%s:pfs:/IMAGE0.VCD" % name]
    if kind == USB_SEARCH:
        return ["mass:/POPS%s/%s.VCD" % (n, name) for n in [""] + list(range(10))]
    return ["hdd0:__.POPS%s:pfs:/%s.VCD" % (n, name) for n in [""] + list(range(10))]


# ---------------------------------------------------------------------------
# Differences that are not about argv[0]
# ---------------------------------------------------------------------------
# name; what the original does and the case lines that show it; what launcHER
# does and the source text that shows it (present: must be in the file,
# absent: must not be). Paths are relative to the repository.
Other = namedtuple("Other", "name original case lines launcher file present absent")
HANDLER = "launcher/src/handler_pops.c"
RESOLVER = "common/src/launch_args.c"

OTHER_DIFFERENCES = [
    Other("POPS package on an HDD launch",
          "only hdd0:__common:pfs:/POPS/POPS.ELF with IOPRP252.IMG or IOPRP.IMG; the two "
          "packs are not asked for there even when present",
          "hdd-no-package",
          ["87dad8 fileXioOpen pfs1:/POPS/POPS.ELF -> -2", "874404 fatal"],
          "the same three-step probe in every folder of its list, which has no "
          "hdd0:__common entry",
          HANDLER, ['searchDirs[searchCount++] = "hdd0:__.POPS:pfs:/";'], ["__common"]),
    Other("POPS package on a USB launch",
          "only mass:/POPS, in the order POPS_IOX.PAK, POPS.PAK, POPS.ELF",
          "usb-elf",
          ["87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> -2",
           "87d5a0 fioOpen mass:/POPS/POPS.PAK -> -2",
           "87db18 fioOpen mass:/POPS/POPS.ELF -> ok"],
          "the same order, but in up to twelve folders, the image's own folder first and "
          "the memory cards before mass:/POPS",
          HANDLER, ['searchDirs[searchCount++] = "mc0:/POPSTARTER/";',
                    'searchDirs[searchCount++] = "ata0:/LAUNCHER-TEST-20261013-A/";'], []),
    Other("IOPRP.IMG as the second name of the IOP image",
          "POPS.ELF takes IOPRP252.IMG, else IOPRP.IMG from the same folder",
          "hdd-ioprp-img",
          ["87df88 fileXioOpen pfs1:/POPS/IOPRP252.IMG -> -2",
           "87e02c fileXioOpen pfs1:/POPS/IOPRP.IMG -> ok"],
          "only IOPRP252.IMG",
          HANDLER, ['"%sIOPRP252.IMG"'], ["IOPRP.IMG"]),
    Other("package accepted by exact size and content",
          "a file of the wrong size is opened and passed over (sizes 0xe50b8, 0xe6240, "
          "0x30530c); no usable package is fatal at 0x874404",
          "usb-iox-size",
          ["87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> ok",
           "87d5a0 fioOpen mass:/POPS/POPS.PAK -> ok",
           "87db18 fioOpen mass:/POPS/POPS.ELF -> ok", "874404 fatal"],
          "the first file that opens is the package; none of the three sizes is in the "
          "source",
          HANDLER, ['snprintf(testPath, sizeof(testPath), "%sPOPS_IOX.PAK", dir);'],
          ["0xe50b8", "0xE50B8", "0xe6240", "0xE6240", "0x30530c", "0x30530C"]),
    Other("per-game folder on HDD",
          "hdd0:__common:pfs:/POPS/<title>/ for every launch from the HDD, wherever the "
          "image is; made when missing",
          "hdd",
          ["8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> -2",
           "8d7ed4 fileXioMkdir pfs1:/POPS/GAME/ -> 0"],
          "the image's own folder (<image folder>/<title>/), so hdd0:__.POPS:pfs:/<title>/ "
          "for a plain name",
          HANDLER, ['"%s%s/SLOT0.VMC", vcdDir, gameBase'], ["__common"]),
    Other("icon.sys and list.ico in the HDD game folder",
          "written when absent (0x3c4 and 0x8158 bytes), left alone when present",
          "hdd",
          ["8d8828 fileXioWrite hdd0:__common:pfs:/POPS/GAME/icon.sys -> 0x3c4 bytes",
           "8d88a0 fileXioWrite hdd0:__common:pfs:/POPS/GAME/list.ico -> 0x8158 bytes"],
          "no such step",
          HANDLER, [], ["list.ico", "icon.sys"]),
    Other("numbered folder moves the per-game files",
          "an image found in mass:/POPSn takes OSD.BIN, BIOS.BIN, the fix files, the three "
          "text files, the game folder and both memory cards from mass:/POPSn; the IGR "
          "skin and MODULE_n.IRX stay in mass:/POPS",
          "usb-pops4",
          ["876354 fioOpen mass:/POPS4/GAME.VCD -> ok",
           "883840 fioOpen mass:/POPS4/CHEATS.TXT -> -2",
           "87e538 fioOpen mass:/POPS/IGR_BG.TM2 -> -2",
           "877834..8788d0 fioOpen mass:/POPS/MODULE_{0..9}.IRX -> -2",
           "8d8d9c fioWrite mass:/POPS4/GAME/SLOT0.VMC -> 0x20000 bytes"],
          "no numbered folder exists in the resolver",
          RESOLVER, ['"mass0:/POPS/%s.VCD"'], ["POPS%d", "POPS0", "POPS%c"]),
    Other("memory cards on USB and SMB",
          "<POPS folder>/<title>/SLOT0.VMC and SLOT1.VMC only; the folder and both files "
          "(0x20000 bytes each) are made before POPS starts when absent",
          "usb",
          ["8d83d4 fioMkdir mass0:/POPS/GAME -> 0",
           "8d8d9c fioWrite mass:/POPS/GAME/SLOT0.VMC -> 0x20000 bytes",
           "8d8d9c fioWrite mass:/POPS/GAME/SLOT1.VMC -> 0x20000 bytes"],
          "also accepts <title>.VMC0/.VMC1, a <serial> folder and cards beside the image",
          HANDLER, ['"%s%s/%s.VMC0", vcdDir, gameBase, gameBase', '"%sSLOT0.VMC", vcdDir'], []),
    Other("missing POPS folder",
          "mass:/POPS or hdd0:__common:pfs:/POPS is made, then the launch stops at "
          "0x8740a0",
          "usb-no-pops-folder",
          ["8d8a68 fioGetstat mass:/POPS -> -2", "8d8a7c fioMkdir mass0:/POPS -> 0",
           "8740a0 fatal"],
          "makes no POPS folder; a launch without a package ends with its own message",
          HANDLER, ['msg("POPS: Missing POPS dependencies'], []),
    Other("no image found",
          "the drive is asked for a PS1 disc (types 0x10 to 0x13 go on; only 0x10 "
          "traced in this path suite), otherwise fatal at 0x876a0c",
          "usb-no-vcd",
          ["8767d4 sceCdGetDiskType (0, 0) -> 0", "876a0c fatal"],
          "launchPOPS returns -ENOENT",
          HANDLER, ['msg("POPS: Cannot open target VCD: %s\\n", vcdPath);'], ["sceCdGetDiskType"]),
    Other("name length",
          "a title of 72 characters is used whole; 73 is fatal at 0x875aa8 (\"Please "
          "shorten\")",
          "usb-73", ["875aa8 fatal"],
          "titles are cut to 63 characters without a message, so a 64 to 72 character "
          "title asks for a different file than the original",
          RESOLVER, ["char baseTitle[64] = {0};"], []),
]

# launcHER's package search list, in order (handler_pops.c,
# findPopsDependenciesForMode). vcdDir is the image's folder, devPops is
# "<device>:/POPS/". The test folder is to stay until the owner removes it.
SEARCH_DIRS = ["vcdDir", "devPops", '"mc0:/POPSTARTER/"', '"mc1:/POPSTARTER/"',
               '"mc0:/POPS/"', '"mc1:/POPS/"', '"hdd0:__.POPS:pfs:/"', '"usb0:/POPS/"',
               '"usb1:/POPS/"', '"mass:/POPS/"', '"mass0:/POPS/"',
               '"ata0:/LAUNCHER-TEST-20261013-A/"']


# ---------------------------------------------------------------------------
# launcHER's resolver on the host
# ---------------------------------------------------------------------------
MAX_CANDIDATES = 16            # what handleQuickboot() and main() pass
POPS_BDMA_NONE = 0
Candidates = (c.c_char * 512) * MAX_CANDIDATES


def build():
    out = Path(tempfile.mkdtemp())
    lib = out / ("launch_args.dll" if os.name == "nt" else "launch_args.so")
    subprocess.run([os.environ.get("CC", "gcc"), "-std=c99", "-shared", "-fPIC", "-O2",
                    "-Wall", "-Wextra", "-Werror", "-pedantic",
                    "-I", str(ROOT / "common/include"),
                    str(ROOT / "common/src/launch_args.c"), "-o", str(lib)], check=True)
    lib = c.CDLL(str(lib))
    lib.pops_resolve_candidate_targets_bdma.argtypes = [
        c.c_char_p, c.c_char_p, c.POINTER(Candidates), c.c_int, c.c_int]
    lib.pops_resolve_candidate_targets_bdma.restype = c.c_int
    for name in ("pops_is_xx_prefix", "pops_is_sb_prefix", "pops_is_pp_prefix"):
        getattr(lib, name).argtypes = [c.c_char_p]
        getattr(lib, name).restype = c.c_int
    lib.launcher_normalize_args.argtypes = [c.c_int, c.POINTER(c.c_char_p)]
    lib.launcher_normalize_args.restype = c.c_int
    return lib


LIB = build()


def native_prefix(argv0):
    raw = argv0.encode("latin-1") if argv0 is not None else None
    for name, call in (("XX", LIB.pops_is_xx_prefix), ("SB", LIB.pops_is_sb_prefix),
                       ("PP", LIB.pops_is_pp_prefix)):
        if call(raw):
            return name
    return "none"


def native_candidates(argv0):
    raw = argv0.encode("latin-1") if argv0 is not None else None
    out = Candidates()
    count = LIB.pops_resolve_candidate_targets_bdma(raw, None, c.byref(out), MAX_CANDIDATES,
                                                    POPS_BDMA_NONE)
    return [out[i].value.decode("latin-1") for i in range(count)]


def same_place(candidate, smb):
    """launcHER's candidate under the original's device names."""
    if smb and candidate.startswith(("smb0:", "smb:")):
        return "mass:" + candidate.split(":", 1)[1]
    if candidate.startswith("mass0:"):
        return "mass:" + candidate[6:]
    return candidate


class Native(unittest.TestCase):
    def test_form_table(self):
        for row in FORM_TABLE:
            with self.subTest(argv=row.argv):
                found = native_candidates(row.argv)
                self.assertEqual(native_prefix(row.argv), row.prefix)
                self.assertEqual((len(found), found[0] if found else None),
                                 (row.count, row.first))
                wanted = original_search(row.search)
                if not wanted:
                    self.assertEqual(row.at, "-")
                    continue
                places = [same_place(path, row.smb) for path in found]
                at = places.index(wanted[0]) if wanted[0] in places else None
                self.assertEqual(at, row.at)

    def test_numbered_locations_are_never_candidates(self):
        """mass:/POPS0..9 and hdd0:__.POPS0..9, and IMAGE0.VCD, are in no list."""
        for row in FORM_TABLE:
            places = [same_place(path, row.smb) for path in native_candidates(row.argv)]
            for wanted in original_search(row.search)[1:]:
                self.assertNotIn(wanted, places, row.argv)
            self.assertFalse([path for path in places if "IMAGE0.VCD" in path], row.argv)

    def test_every_form_differs(self):
        """Stage 1 changes nothing: no form of the list resolves the way the
        original does, and each row says how."""
        self.assertEqual([row.argv for row in FORM_TABLE], list(T.FORMS))
        for row in FORM_TABLE:
            places = [same_place(path, row.smb) for path in native_candidates(row.argv)]
            self.assertTrue(row.difference, row.argv)
            if row.argv is None:
                # argc == 0: neither side looks for anything.
                self.assertEqual((places, row.end), ([], EXIT))
                self.assertEqual(LIB.launcher_normalize_args(0, None), -1)
            else:
                self.assertNotEqual(places, original_search(row.search), row.argv)

    def test_full_lists(self):
        """Four whole candidate lists, one per kind."""
        self.assertEqual(native_candidates("mass:/POPS/XX.GAME.ELF"), [
            "mass0:/POPS/GAME.VCD", "mass0:/POPS/IMAGE.VCD", "mass:/POPS/GAME.VCD",
            "mass:/POPS/IMAGE.VCD", "mass0:/GAME.VCD", "mass:/GAME.VCD",
            "mass1:/POPS/GAME.VCD", "mc0:/POPS/GAME.VCD", "mc1:/POPS/GAME.VCD",
            "hdd0:__.POPS:pfs:/GAME.VCD"])
        self.assertEqual(native_candidates("hdd0:__common:pfs:/POPS/GAME.ELF"), [
            "hdd0:__.POPS:pfs:/GAME.VCD", "hdd0:__.POPS:pfs:/IMAGE.VCD", "pfs0:/GAME.VCD",
            "pfs0:/IMAGE.VCD", "hdd0:PP.GAME:pfs:/GAME.VCD", "hdd0:PP.GAME:pfs:/IMAGE.VCD",
            "hdd0:__common:pfs:/POPS/GAME.VCD", "hdd0:__common:pfs:/POPS/IMAGE.VCD",
            "hdd0:/POPS/GAME.VCD", "hdd0:/POPS/IMAGE.VCD", "hdd0:/GAME.VCD",
            "mass0:/POPS/GAME.VCD", "mass0:/GAME.VCD", "mc0:/POPS/GAME.VCD",
            "mc1:/POPS/GAME.VCD"])
        self.assertEqual(native_candidates("hdd0:PP.ALPHA:pfs:/PP.BETA.ELF"), [
            "hdd0:PP.BETA:pfs:/BETA.VCD", "hdd0:PP.BETA:pfs:/IMAGE.VCD",
            "hdd0:PP.BETA:pfs:/PP.BETA.VCD", "pfs0:/BETA.VCD", "pfs0:/IMAGE.VCD",
            "pfs0:/PP.BETA.VCD", "hdd0:__.POPS:pfs:/BETA.VCD", "hdd0:__.POPS:pfs:/IMAGE.VCD",
            "mass0:/POPS/BETA.VCD"])
        self.assertEqual(native_candidates("mass:/POPS/SB.GAME.ELF"), [
            "smb0:/POPS/GAME.VCD", "smb0:/GAME.VCD", "smb:/POPS/GAME.VCD", "smb:/GAME.VCD",
            "mass:/POPS/GAME.VCD", "mass0:/POPS/GAME.VCD", "hdd0:__.POPS:pfs:/GAME.VCD"])

    def test_name_length(self):
        """The original uses a 72-character title whole and stops at 73;
        launcHER cuts both to 63 characters."""
        for title in (T72, T73, "T" * 64):
            found = native_candidates("mass:/POPS/XX.%s.ELF" % title)
            self.assertEqual(found[0], "mass0:/POPS/%s.VCD" % ("T" * 63))
            self.assertFalse([path for path in found if title in path])
        found = native_candidates("mass:/POPS/XX.%s.ELF" % ("T" * 63))
        self.assertEqual(found[0], "mass0:/POPS/%s.VCD" % ("T" * 63))

    def test_original_search_literal_order(self):
        self.assertEqual(original_search((USB_SEARCH, "GAME")), USB_GAME_SEARCH)
        self.assertEqual(original_search((HDD_SEARCH, "GAME")), [
            "hdd0:__.POPS:pfs:/GAME.VCD", "hdd0:__.POPS0:pfs:/GAME.VCD",
            "hdd0:__.POPS1:pfs:/GAME.VCD", "hdd0:__.POPS2:pfs:/GAME.VCD",
            "hdd0:__.POPS3:pfs:/GAME.VCD", "hdd0:__.POPS4:pfs:/GAME.VCD",
            "hdd0:__.POPS5:pfs:/GAME.VCD", "hdd0:__.POPS6:pfs:/GAME.VCD",
            "hdd0:__.POPS7:pfs:/GAME.VCD", "hdd0:__.POPS8:pfs:/GAME.VCD",
            "hdd0:__.POPS9:pfs:/GAME.VCD",
        ])
        self.assertEqual(original_search((PART, "PP.GAME")),
                         ["hdd0:PP.GAME:pfs:/IMAGE0.VCD"])

    def test_original_search_rejects_wrong_path(self):
        wrong = list(USB_GAME_SEARCH)
        wrong[4] = "mass:/POPS3/WRONG.VCD"
        with self.assertRaises(AssertionError) as mismatch:
            self.assertEqual(original_search((USB_SEARCH, "GAME")), wrong)
        self.assertIn("mass:/POPS3/WRONG.VCD", str(mismatch.exception))
        self.assertEqual(original_search((USB_SEARCH, "GAME")), USB_GAME_SEARCH)


@unittest.skipUnless(HAVE_MAIN, "needs POPSTARTER_TEST_ELF and unicorn")
class Original(unittest.TestCase):
    """The pinned table against the original's own code. One run per case
    and per argv[0] form, each from the first instruction of main."""
    reports = {}
    forms = {}

    @classmethod
    def report(cls, name):
        if name not in cls.reports:
            cls.reports[name] = T.run_case(name)
        return cls.reports[name]

    @classmethod
    def form(cls, argv0):
        if argv0 not in cls.forms:
            cls.forms[argv0] = T.run_form(argv0)
        return cls.forms[argv0]

    def needs(self, files):
        missing = T.missing_inputs(files)
        if missing:
            self.skipTest("POPS_TEST_ELF folder lacks " + ", ".join(missing))

    def test_cases(self):
        self.assertEqual(sorted(CASE_TABLE), sorted(T.CASES))
        ran = 0
        omitted = []
        for name, (focus, lines, state, written) in CASE_TABLE.items():
            case = T.CASES[name]
            missing = T.missing_inputs(case["files"])
            if missing:
                omitted.append((name, missing))
                continue
            with self.subTest(case=name):
                report = self.report(name)
                self.assertEqual(
                    T.summary(report, None if focus == FULL else case["focus"]), lines)
                got = report["state"]
                self.assertEqual(
                    (got["launch_type"], got["mass_mode"], got["smb_mode"],
                     got["physical_disc"], got["suffix_in_use"],
                     chr(got["suffix_char"]) if got["suffix_char"] else "", got["quiet"]),
                    state)
                self.assertEqual(report["written"], written)
            ran += 1
        if omitted:
            details = "; ".join("%s [%s]" % (name, ", ".join(missing))
                                for name, missing in omitted)
            self.skipTest("%d cases compared; %d cases omitted: %s" %
                          (ran, len(omitted), details))

    def test_complete_runs_end_in_pops(self):
        """The four launch kinds reach ExecPS2 at 0x87c1cc with POPS's entry."""
        for name in ("usb", "hdd", "hdd-pp", "smb"):
            self.needs(T.CASES[name]["files"])
            end = self.report(name)["end"]
            self.assertEqual((end["kind"], end["site"]), ("exec", 0x87C1CC), name)

    def test_forms(self):
        self.needs(dict(T.USB_PACK, **T.HDD_POPS))
        for row in FORM_TABLE:
            with self.subTest(argv=row.argv):
                got = self.form(row.argv)
                self.assertEqual((got["type"], got["mass"], got["smb"], got["end"]),
                                 (row.type, row.mass, row.smb, row.end))
                self.assertEqual(got["tries"], original_search(row.search))

    def test_other_differences(self):
        ran = 0
        omitted = []
        for item in OTHER_DIFFERENCES:
            case = T.CASES[item.case]
            missing = T.missing_inputs(case["files"])
            if missing:
                omitted.append((item, missing))
                continue
            with self.subTest(name=item.name):
                lines = T.summary(self.report(item.case))
                for line in item.lines:
                    self.assertIn(line, lines)
            ran += 1
        if omitted:
            details = "; ".join("%s (%s) [%s]" %
                                (item.name, item.case, ", ".join(missing))
                                for item, missing in omitted)
            self.skipTest("%d differences compared; %d differences omitted: %s" %
                          (ran, len(omitted), details))

    def test_quiet_and_verbose_ask_for_the_same(self):
        """The profile byte that turns the messages on (0x100010) does not
        change one path, call site or result."""
        case = T.CASES["usb-no-vcd"]
        self.needs(case["files"])
        files = {path: T._content(spec) for path, spec in case["files"].items()}
        loud = T.trace(case["argv"], files, preset={0x100010: 0xFF}, stop_at=case["stop"])
        self.assertEqual(T.summary(loud), T.summary(self.report("usb-no-vcd")))
        self.assertIn("NO PS1 CDROM!\n\n", [item["text"] for item in loud["prints"]])
        # MAIN is not entirely silent: these two come out on its XX. launch.
        self.assertEqual([(item["site"], item["text"])
                          for item in self.report("usb-no-vcd")["prints"]],
                         [(0x8DB7F8, "    Resource paths re-linking... "), (0x8DB960, "DONE\n")])


class Negative(unittest.TestCase):
    @unittest.skipUnless(HAVE_MAIN, "needs POPSTARTER_TEST_ELF and unicorn")
    def test_bad_table_entry_fails(self):
        name = "usb-no-pops-folder"
        rows = T.summary(T.run_case(name), T.CASES[name]["focus"])
        expected = CASE_TABLE[name][1]
        self.assertEqual(rows, expected)
        corrupt = list(expected)
        good = "8d8a68 fioGetstat mass:/POPS -> -2"
        corrupt[corrupt.index(good)] = "8d8a68 fioGetstat mass:/NOT_POPS -> -2"
        with self.assertRaises(AssertionError) as mismatch:
            self.assertEqual(rows, corrupt)
        self.assertIn("mass:/NOT_POPS", str(mismatch.exception))

    @unittest.skipUnless(HAVE_MAIN, "needs POPSTARTER_TEST_ELF and unicorn")
    def test_unmodelled_code_fails(self):
        with self.subTest(kind="library"):
            address = 0x91C528
            library = dict(T.LIBRARY)
            del T.LIBRARY[address]
            try:
                with self.assertRaisesRegex(RuntimeError,
                                            "unmodelled library code at 0x91c528"):
                    T.trace(["mass:/POPS/XX.GAME.ELF"], {})
            finally:
                T.LIBRARY.clear()
                T.LIBRARY.update(library)
        with self.subTest(kind="EE instruction"):
            image, loader = T._inputs()
            image = bytearray(image)
            image[T.MAIN - T.BASE:T.MAIN - T.BASE + 4] = (0x70000000).to_bytes(4, "little")
            run = T.Original(image, loader, [], T.Files())
            with self.assertRaisesRegex(RuntimeError,
                                        "unmodelled MMI 0x70000000 at 0x870b78"):
                run.run(limit=100)

    def test_missing_inputs_name_skips(self):
        old = os.environ.get("POPS_TEST_ELF")
        with tempfile.TemporaryDirectory() as folder:
            os.environ["POPS_TEST_ELF"] = str(Path(folder) / "POPS.ELF")
            try:
                files = T.CASES["usb-pak"]["files"]
                self.assertEqual(T.missing_inputs(files), ["POPS.PAK"])
                case = Original("test_cases")
                with self.assertRaises(unittest.SkipTest) as skipped:
                    case.needs(files)
                self.assertEqual(str(skipped.exception),
                                 "POPS_TEST_ELF folder lacks POPS.PAK")
            finally:
                if old is None:
                    del os.environ["POPS_TEST_ELF"]
                else:
                    os.environ["POPS_TEST_ELF"] = old

    @unittest.skipUnless(HAVE_MAIN, "needs POPSTARTER_TEST_ELF and unicorn")
    def test_partial_inputs_name_all_skips(self):
        old_env = os.environ.get("POPS_TEST_ELF")
        old_reports, old_forms = Original.reports, Original.forms
        real_run_case = T.run_case
        called = []

        def counted_run_case(name):
            called.append(name)
            return real_run_case(name)

        with tempfile.TemporaryDirectory() as folder:
            os.environ["POPS_TEST_ELF"] = str(Path(folder) / "POPS.ELF")
            T.run_case = counted_run_case
            try:
                with self.subTest(method="test_cases"):
                    Original.reports = {}
                    called.clear()
                    with self.assertRaises(unittest.SkipTest) as skipped:
                        Original("test_cases").test_cases()
                    self.assertEqual(called, ["usb-no-pops-folder", "hdd-no-common",
                                              "hdd-no-pops-folder", "usb-iox-size"])
                    omitted = [(name, T.missing_inputs(T.CASES[name]["files"]))
                               for name in CASE_TABLE if name not in called]
                    self.assertEqual(len(omitted), 28)
                    message = str(skipped.exception)
                    self.assertIn("4 cases compared; 28 cases omitted", message)
                    for name, missing in omitted:
                        self.assertTrue(missing, name)
                        self.assertIn(name + " [" + ", ".join(missing) + "]", message)

                with self.subTest(method="test_other_differences"):
                    Original.reports = {}
                    called.clear()
                    with self.assertRaises(unittest.SkipTest) as skipped:
                        Original("test_other_differences").test_other_differences()
                    self.assertEqual(called, ["usb-iox-size", "usb-no-pops-folder"])
                    omitted = [(item, T.missing_inputs(T.CASES[item.case]["files"]))
                               for item in OTHER_DIFFERENCES if item.case not in called]
                    self.assertEqual(len(omitted), 9)
                    message = str(skipped.exception)
                    self.assertIn("2 differences compared; 9 differences omitted", message)
                    for item, missing in omitted:
                        self.assertTrue(missing, item.name)
                        self.assertIn(item.name + " (" + item.case + ") [" +
                                      ", ".join(missing) + "]", message)
            finally:
                T.run_case = real_run_case
                Original.reports, Original.forms = old_reports, old_forms
                if old_env is None:
                    del os.environ["POPS_TEST_ELF"]
                else:
                    os.environ["POPS_TEST_ELF"] = old_env

        self.assertIs(T.run_case, real_run_case)
        self.assertIs(Original.reports, old_reports)
        self.assertIs(Original.forms, old_forms)
        self.assertEqual(os.environ.get("POPS_TEST_ELF"), old_env)

    @unittest.skipUnless(HAVE_MAIN, "needs POPSTARTER_TEST_ELF and unicorn")
    def test_branch_answer_changes_summary(self):
        argv = ["hdd0:__common:pfs:/POPS/GAME.ELF"]
        partitions = ["hdd0:__common"]
        failed = T.trace(argv, {}, partitions=partitions,
                         results={("mount", "hdd0:__common"): -2}, stop_at=T.LAUNCHING)
        mounted = T.trace(argv, {}, partitions=partitions, stop_at=T.LAUNCHING)
        failed_rows = T.summary(failed)
        mounted_rows = T.summary(mounted)
        self.assertIn("8d8b6c fileXioMount pfs1: = hdd0:__common -> -2", failed_rows)
        self.assertIn("8d8b6c fileXioMount pfs1: = hdd0:__common -> 0", mounted_rows)
        self.assertIn("873f88 fatal", failed_rows)
        self.assertIn("8d7eac fileXioGetStat pfs1:/POPS/ -> -2", mounted_rows)
        self.assertNotIn("8d7eac fileXioGetStat pfs1:/POPS/ -> -2", failed_rows)
        self.assertNotEqual(failed_rows, mounted_rows)

    @unittest.skipUnless(HAVE_MAIN, "needs POPSTARTER_TEST_ELF and unicorn")
    def test_quiet_does_not_change_paths(self):
        case = T.CASES["usb-no-pops-folder"]
        quiet = T.run_case("usb-no-pops-folder")
        loud = T.trace(case["argv"], {}, preset={0x100010: 0xFF}, stop_at=case["stop"])
        self.assertEqual(T.summary(loud), T.summary(quiet))
        self.assertNotEqual(loud["prints"], quiet["prints"])


class Source(unittest.TestCase):
    def read(self, path):
        return (ROOT / path).read_text(encoding="utf-8")

    def test_pinned_tables_are_consistent(self):
        """The tables above describe the tracer's own lists, with or without
        the inputs."""
        self.assertEqual(sorted(CASE_TABLE), sorted(T.CASES))
        self.assertEqual([row.argv for row in FORM_TABLE], list(T.FORMS))
        for name, (focus, lines, state, written) in CASE_TABLE.items():
            self.assertEqual(focus == FULL, T.CASES[name]["focus"] is None, name)
            self.assertTrue(lines, name)
        # A complete run ends at ExecPS2, a search without a find at the
        # "no PS1 disc" stop, a stopped run at "LAUNCHING POPS".
        for name in ("usb", "hdd", "hdd-pp", "smb"):
            self.assertIsNone(T.CASES[name]["stop"])
            self.assertEqual(CASE_TABLE[name][1][-1], "87c1cc ExecPS2 entry 0x200000 gp 0x0 argc 1")
        self.assertEqual(T.LAUNCHING, 0x879E5C)
        self.assertEqual((T.MAIN, T.FATAL, T.GP), (0x870B78, 0x8709F8, 0x9B68F0))
        self.assertEqual({T.STATE[key] for key in ("launch_type", "mass_mode", "smb_mode")},
                         {0x3414, 0x3448, 0x3888})
        for item in OTHER_DIFFERENCES:
            self.assertIn(item.case, T.CASES, item.name)

    def test_package_search_list(self):
        source = self.read(HANDLER)
        body = source[source.index("static int findPopsDependenciesForMode("):
                      source.index("int findPopsDependencies(")]
        found = [line.split("=", 1)[1].strip().rstrip(";") for line in body.splitlines()
                 if "searchDirs[searchCount++] =" in line]
        self.assertEqual(found, SEARCH_DIRS)
        self.assertIn("const char *searchDirs[16];", body)
        self.assertIn('snprintf(devPops, sizeof(devPops), "%s/POPS/", devPrefix);', body)
        order = ['snprintf(testPath, sizeof(testPath), "%sPOPS_IOX.PAK", dir);',
                 "if (requireIox)\n      continue;",
                 'snprintf(testPath, sizeof(testPath), "%sPOPS.PAK", dir);',
                 'snprintf(testPath, sizeof(testPath), "%sPOPS.ELF", dir);',
                 'snprintf(testIop, sizeof(testIop), "%sIOPRP252.IMG", dir);',
                 "if (!tryFile(testPath) && !tryFile(testIop)) {"]
        at = [body.index(text) for text in order]
        self.assertEqual(at, sorted(at))
        # The SB. rule the original has too: POPS_IOX.PAK or nothing
        # (case smb-no-iox).
        self.assertIn("ioprpPath, sizeof(ioprpPath), isSbLaunch);", source)

    def test_other_differences_launcher_side(self):
        for item in OTHER_DIFFERENCES:
            source = self.read(item.file)
            with self.subTest(name=item.name):
                for text in item.present:
                    self.assertIn(text, source)
                for text in item.absent:
                    self.assertNotIn(text, source)
        # Nothing in launcHER's own C sources names the partition the
        # original keeps POPS and the game folders in.
        for folder in ("common/src", "common/include", "launcher/src", "launcher/include"):
            for path in sorted((ROOT / folder).glob("*.[chS]")):
                self.assertNotIn("__common", path.read_text(encoding="utf-8", errors="replace"),
                                 path.name)

    def test_launcher_dispatch(self):
        """How a renamed launcHER reaches the resolver (launcher/src)."""
        main = self.read("launcher/src/main.c")
        patinfo = main.index('if (strstr(argv[0], ":PATINFO"))')
        quickboot = main.index('fail("Quickboot failed: %d", handleQuickboot(argv[0]));')
        self.assertLess(patinfo, quickboot)
        self.assertIn('fail("PATINFO failed: %d", handlePATINFO(argc, argv));', main)
        cdrom = main.index('if (!strncmp("cdrom", argv[0], 5))')
        self.assertNotIn("#endif", main[main.rindex("#ifdef OSDM", 0, cdrom):cdrom])
        self.assertIn("int count = pops_resolve_candidate_targets(launcherPath, argv[0], "
                      "candidates, 16);", main)
        quick = self.read("launcher/src/handler_quickboot.c")
        self.assertEqual(quick.count(
            "pops_resolve_candidate_targets(originalTarget, NULL, candidates, 16);"), 3)
        resolver = self.read(RESOLVER)
        self.assertIn("return pops_resolve_candidate_targets_bdma(launcher_path, arg, "
                      "candidates, max_candidates, mode);", resolver)

    def test_tracer(self):
        source = self.read("tools/trace_original_pops_paths.py")
        # Unicorn 2.1.4: a live memory-write hook is not usable here.
        self.assertNotIn("UC_HOOK_MEM_WRITE", source)
        self.assertEqual(len(T.LIBRARY), 67)
        self.assertEqual(source.count('os.environ["POPSTARTER_TEST_ELF"]'), 1)
        self.assertIn('os.environ.get("POPS_TEST_ELF")', source)
        # Every library entry has a model method.
        for name in set(T.LIBRARY.values()):
            self.assertTrue(hasattr(T.Original, "lib_" + name), name)

    def test_document(self):
        text = self.read("docs/POPSTARTER_PATHS.md")
        self.assertIn("NOT TESTED on a console", text)
        for name in T.CASES:
            self.assertIn("`%s`" % name, text, name)
        # Every complete summary row, not only its call site, is published.
        for lines in (USB, HDD, PP_IMAGE, SMB):
            for line in lines:
                self.assertIn(line, text, line)
        for row in FORM_TABLE:
            argument = "argc == 0" if row.argv is None else row.argv
            self.assertIn("`%s`" % argument, text, argument)
        for item in OTHER_DIFFERENCES:
            self.assertIn(item.name, text)
        other = next(item for item in OTHER_DIFFERENCES if item.name == "no image found")
        self.assertIn("types 0x10 to 0x13 go on; only 0x10 traced in this path suite",
                      other.original)
        self.assertIn("types `0x10` to `0x13` are accepted by the original implementation, "
                      "with only `0x10` traced here", text)
        self.assertNotIn("types `0x10` to `0x12`", text)

    def test_ci_runs_this_file(self):
        workflow = self.read(".github/workflows/build.yml")
        self.assertIn("run: python tools/test_pops_paths.py", workflow)


if __name__ == "__main__":
    unittest.main()
