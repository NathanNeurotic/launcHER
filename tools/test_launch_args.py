#!/usr/bin/env python3
"""Exercise the production launcher argv normalization without PS2SDK."""
import ctypes as c
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
build = root / 'build/launch-args-host'
build.mkdir(parents=True, exist_ok=True)
library = build / ('launch_args.dll' if os.name == 'nt' else 'launch_args.so')
compiler = shutil.which(os.environ.get('CC', 'gcc'))
if not compiler:
    raise RuntimeError('GCC-compatible host compiler required')
subprocess.run([compiler, '-std=c99', '-Wall', '-Wextra', '-Werror', '-pedantic',
                '-shared', '-fPIC', '-I', str(root / 'common/include'),
                str(root / 'common/src/launch_args.c'), '-o', str(library)], check=True)
lib = c.CDLL(str(library))
lib.launcher_normalize_args.argtypes = [c.c_int, c.POINTER(c.c_char_p)]
lib.launcher_normalize_args.restype = c.c_int

def check(arguments, expected):
    argv = (c.c_char_p * len(arguments))(*[a.encode() if a is not None else None for a in arguments])
    result = lib.launcher_normalize_args(len(arguments), argv)
    if expected is None:
        assert result == -1, (arguments, result)
    else:
        actual = [argv[i].decode() for i in range(result)]
        assert actual == expected, (arguments, actual, expected)

self = 'hdd0:__common:pfs0:/OPL/APPS/Looney Tunes Racing [SLES_031.27]/launcHER.elf'
bare = self.split('__common:')[1]
check([self, bare], [self])
check([self, bare, ''], [self, ''])
check([self, bare, bare, 'mass0:/Ember.elf', 'Game'], [self, 'mass0:/Ember.elf', 'Game'])
check([self, bare, 'mc0:/config.cnf'], [self, 'mc0:/config.cnf'])
check([self, bare, '-dev9=NICHDD'], [self, '-dev9=NICHDD'])
check([self, bare.replace('/', '\\')], [self])
check([self.replace('pfs0:', 'pfs:'), bare], [self.replace('pfs0:', 'pfs:')])
for target in ('pfs1:/OPL/APPS/Looney Tunes Racing [SLES_031.27]/launcHER.elf',
               'hdd0:OTHER:pfs0:/OPL/APPS/Looney Tunes Racing [SLES_031.27]/launcHER.elf',
               'pfs0:/OTHER/launcHER.elf', 'pfs0:/EMBER/ember.elf', 'Game'):
    check([self, target], [self, target])
for path in ('mass0:/APPS/renamed.elf', 'mmce1:/launcHER.elf', 'mc0:/BOOT.ELF'):
    check([path], [path])
    check([path, path, ''], [path, ''])
check(['mass0:/APPS/renamed.elf', 'mass1:/APPS/renamed.elf'],
      ['mass0:/APPS/renamed.elf', 'mass1:/APPS/renamed.elf'])
check([bare, bare], [bare])  # Cannot invent the missing HDD partition.
check([self, None], None)
check([''], None)
assert lib.launcher_normalize_args(0, None) == -1

# XX. prefix check and active launch tracking
lib.pops_is_xx_prefix.argtypes = [c.c_char_p]
lib.pops_is_xx_prefix.restype = c.c_int
lib.pops_set_active_xx_launch.argtypes = [c.c_int]
lib.pops_set_active_xx_launch.restype = None
lib.pops_get_active_xx_launch.argtypes = []
lib.pops_get_active_xx_launch.restype = c.c_int

assert lib.pops_is_xx_prefix(b"XX.Crash Bandicoot.ELF") == 1
assert lib.pops_is_xx_prefix(b"mass0:/APPS/XX.Crash Bandicoot.ELF") == 1
assert lib.pops_is_xx_prefix(b"XX.Crash") == 1
assert lib.pops_is_xx_prefix(b"Crash Bandicoot.ELF") == 0
assert lib.pops_is_xx_prefix(b"SB.Crash Bandicoot.ELF") == 0
assert lib.pops_is_xx_prefix(None) == 0

lib.pops_set_active_xx_launch(0)
assert lib.pops_get_active_xx_launch() == 0
lib.pops_set_active_xx_launch(1)
assert lib.pops_get_active_xx_launch() == 1
lib.pops_set_active_xx_launch(0)

# SB. prefix check and active launch tracking
lib.pops_is_sb_prefix.argtypes = [c.c_char_p]
lib.pops_is_sb_prefix.restype = c.c_int
lib.pops_set_active_sb_launch.argtypes = [c.c_int]
lib.pops_set_active_sb_launch.restype = None
lib.pops_get_active_sb_launch.argtypes = []
lib.pops_get_active_sb_launch.restype = c.c_int

assert lib.pops_is_sb_prefix(b"SB.Crash Bandicoot.ELF") == 1
assert lib.pops_is_sb_prefix(b"smb0:/POPS/SB.Crash Bandicoot.ELF") == 1
assert lib.pops_is_sb_prefix(b"SB.Crash") == 1
assert lib.pops_is_sb_prefix(b"Crash Bandicoot.ELF") == 0
assert lib.pops_is_sb_prefix(b"XX.Crash Bandicoot.ELF") == 0
assert lib.pops_is_sb_prefix(None) == 0

lib.pops_set_active_sb_launch(0)
assert lib.pops_get_active_sb_launch() == 0
lib.pops_set_active_sb_launch(1)
assert lib.pops_get_active_sb_launch() == 1
lib.pops_set_active_sb_launch(0)

# External USB and SMB stack checks
lib.pops_has_external_usb_modules.argtypes = []
lib.pops_has_external_usb_modules.restype = c.c_int
lib.pops_has_smb_stack.argtypes = []
lib.pops_has_smb_stack.restype = c.c_int

# PP. prefix check
lib.pops_is_pp_prefix.argtypes = [c.c_char_p]
lib.pops_is_pp_prefix.restype = c.c_int

assert lib.pops_is_pp_prefix(b"PP.Crash Bandicoot.ELF") == 1
assert lib.pops_is_pp_prefix(b"__.Hidden Game.ELF") == 1
assert lib.pops_is_pp_prefix(b"PP.Crash") == 1
assert lib.pops_is_pp_prefix(b"Crash Bandicoot.ELF") == 0
assert lib.pops_is_pp_prefix(b"XX.Crash Bandicoot.ELF") == 0
assert lib.pops_is_pp_prefix(b"SB.Crash Bandicoot.ELF") == 0
assert lib.pops_is_pp_prefix(None) == 0

# BDMA mode parsing tests
lib.pops_parse_bdma_mode.argtypes = [c.c_char_p]
lib.pops_parse_bdma_mode.restype = c.c_int

assert lib.pops_parse_bdma_mode(b"ATA") == 2
assert lib.pops_parse_bdma_mode(b"ata0") == 2
assert lib.pops_parse_bdma_mode(b"EXFAT") == 2
assert lib.pops_parse_bdma_mode(b"HDD") == 2
assert lib.pops_parse_bdma_mode(b"MX4SIO") == 3
assert lib.pops_parse_bdma_mode(b"mc2sio") == 3
assert lib.pops_parse_bdma_mode(b"MMCE") == 4
assert lib.pops_parse_bdma_mode(b"mmce1") == 4
assert lib.pops_parse_bdma_mode(b"ILINK") == 5
assert lib.pops_parse_bdma_mode(b"ilink0") == 5
assert lib.pops_parse_bdma_mode(b"USB") == 1
assert lib.pops_parse_bdma_mode(b"fat32") == 1
assert lib.pops_parse_bdma_mode(b"GENERIC") == 6
assert lib.pops_parse_bdma_mode(b"bdma") == 6
assert lib.pops_parse_bdma_mode(b"unknown") == 0
assert lib.pops_parse_bdma_mode(b"# comment") == 0
assert lib.pops_parse_bdma_mode(None) == 0

# BDMA detection tests via test root
lib.pops_set_bdma_test_root.argtypes = [c.c_char_p]
lib.pops_set_bdma_test_root.restype = None
lib.pops_detect_bdma_mode.argtypes = []
lib.pops_detect_bdma_mode.restype = c.c_int

with tempfile.TemporaryDirectory() as tmpdir:
    td = Path(tmpdir)
    lib.pops_set_bdma_test_root(str(td).encode())
    # Empty dir: NONE
    assert lib.pops_detect_bdma_mode() == 0
    assert lib.pops_has_external_usb_modules() == 0
    assert lib.pops_has_smb_stack() == 0

    # bdma_mode.txt with ATA
    pop_dir = td / "POPSTARTER"
    pop_dir.mkdir(parents=True, exist_ok=True)
    mode_file = pop_dir / "bdma_mode.txt"
    mode_file.write_text("ATA\n")
    assert lib.pops_detect_bdma_mode() == 2

    # bdma_mode.txt with MX4SIO
    mode_file.write_text("MX4SIO\n")
    assert lib.pops_detect_bdma_mode() == 3

    # bdma_mode.txt with MMCE
    mode_file.write_text("MMCE\n")
    assert lib.pops_detect_bdma_mode() == 4

    mode_file.unlink()

    # bdma_config.txt (RiptOPL marker) with ata and ilink
    cfg_marker = pop_dir / "bdma_config.txt"
    cfg_marker.write_text("ata\n")
    assert lib.pops_detect_bdma_mode() == 2
    cfg_marker.write_text("ilink\n")
    assert lib.pops_detect_bdma_mode() == 5
    cfg_marker.unlink()

    # Presence of driver: bdm_assault.irx -> GENERIC
    driver_file = pop_dir / "bdm_assault.irx"
    driver_file.write_bytes(b"\x00" * 16)
    assert lib.pops_detect_bdma_mode() == 6

    driver_file.unlink()

    # External USB drivers presence
    usbd_file = pop_dir / "USBD.IRX"
    usbd_file.write_bytes(b"\x00" * 16)
    assert lib.pops_has_external_usb_modules() == 1
    usbd_file.unlink()

    # SMB stack presence
    smb_file = pop_dir / "SMBCONFIG.DAT"
    smb_file.write_text("192.168.1.69:445 PS2SMB\nuser\npass\n")
    assert lib.pops_has_smb_stack() == 1
    smb_file.unlink()

    # Reset test root
    lib.pops_set_bdma_test_root(None)

# Candidate target resolution tests
lib.pops_resolve_candidate_targets.argtypes = [c.c_char_p, c.c_char_p, c.POINTER(c.c_char * 512), c.c_int]
lib.pops_resolve_candidate_targets.restype = c.c_int
lib.pops_resolve_candidate_targets_bdma.argtypes = [c.c_char_p, c.c_char_p, c.POINTER(c.c_char * 512), c.c_int, c.c_int]
lib.pops_resolve_candidate_targets_bdma.restype = c.c_int

def resolve(launcher, arg, max_c=16):
    buf = ((c.c_char * 512) * max_c)()
    lp = launcher.encode() if launcher is not None else None
    a = arg.encode() if arg is not None else None
    count = lib.pops_resolve_candidate_targets(lp, a, buf, max_c)
    return [bytes(buf[i]).split(b'\x00')[0].decode() for i in range(count)]

def resolve_bdma(launcher, arg, mode, max_c=16):
    buf = ((c.c_char * 512) * max_c)()
    lp = launcher.encode() if launcher is not None else None
    a = arg.encode() if arg is not None else None
    count = lib.pops_resolve_candidate_targets_bdma(lp, a, buf, max_c, mode)
    return [bytes(buf[i]).split(b'\x00')[0].decode() for i in range(count)]

# 1. No prefix bare title: defaults to POPS APA partition first
cands = resolve('mass0:/APPS/launcHER.elf', 'Crash Bandicoot')
assert cands[0] == 'hdd0:__.POPS:pfs:/Crash Bandicoot.VCD', cands
assert cands[1] == 'hdd0:__.POPS:pfs:/IMAGE.VCD', cands
assert 'mass0:/APPS/Crash Bandicoot.VCD' in cands
assert 'mass0:/POPS/Crash Bandicoot.VCD' in cands

# 2. No prefix renamed ELF (Quickboot): defaults to POPS APA partition first
cands = resolve('hdd0:+OPL:pfs:/APPS/Crash Bandicoot.ELF', None)
assert cands[0] == 'hdd0:__.POPS:pfs:/Crash Bandicoot.VCD', cands
assert cands[1] == 'hdd0:__.POPS:pfs:/IMAGE.VCD', cands

# 3. With XX. prefix in ELF name: USB mass targets take priority over APA
cands = resolve('mass0:/APPS/XX.Crash Bandicoot.ELF', None)
assert cands[0] == 'mass0:/APPS/Crash Bandicoot.VCD', cands
assert cands[1] == 'mass0:/APPS/IMAGE.VCD', cands
assert cands[2] == 'mass0:/POPS/Crash Bandicoot.VCD', cands

# 4. With XX. prefix in argument: USB mass targets take priority over APA
cands = resolve('mass0:/APPS/launcHER.elf', 'XX.Crash Bandicoot')
assert cands[0] == 'mass0:/APPS/Crash Bandicoot.VCD', cands
assert cands[1] == 'mass0:/APPS/IMAGE.VCD', cands
assert cands[2] == 'mass0:/POPS/Crash Bandicoot.VCD', cands

# 5. Full explicit device path: preserved directly
cands = resolve('mc0:/BOOT/BOOT.ELF', 'mass0:/POPS/Crash Bandicoot.VCD')
assert cands == ['mass0:/POPS/Crash Bandicoot.VCD'], cands

# 6. ATA BDMA mode with XX. prefix
cands = resolve_bdma('mass0:/APPS/XX.Crash Bandicoot.ELF', None, 2)
assert cands[0] == 'ata:/POPS/Crash Bandicoot.VCD', cands
assert cands[1] == 'ata:/POPS/IMAGE.VCD', cands
assert cands[2] == 'ata:/Crash Bandicoot.VCD', cands

# 7. MX4SIO BDMA mode with XX. prefix
cands = resolve_bdma('mass0:/APPS/launcHER.elf', 'XX.Crash Bandicoot', 3)
assert cands[0] == 'mx4sio:/POPS/Crash Bandicoot.VCD', cands
assert cands[1] == 'mx4sio:/POPS/IMAGE.VCD', cands
assert cands[2] == 'mx4sio:/Crash Bandicoot.VCD', cands

# 8. MMCE BDMA mode with XX. prefix
cands = resolve_bdma('mass0:/APPS/XX.Crash Bandicoot.ELF', None, 4)
assert cands[0] == 'mmce0:/POPS/Crash Bandicoot.VCD', cands
assert cands[1] == 'mmce0:/POPS/IMAGE.VCD', cands
assert cands[2] == 'mmce0:/Crash Bandicoot.VCD', cands
assert cands[3] == 'mmce1:/POPS/Crash Bandicoot.VCD', cands

# 9. Generic BDMA mode with XX. prefix: probes USB, ATA, MX4SIO, iLink, MMCE
cands = resolve_bdma('mass0:/APPS/XX.Crash Bandicoot.ELF', None, 6)
assert cands[0] == 'mass0:/POPS/Crash Bandicoot.VCD', cands
assert 'ata:/POPS/Crash Bandicoot.VCD' in cands, cands
assert 'mx4sio:/POPS/Crash Bandicoot.VCD' in cands, cands
assert 'ilink:/POPS/Crash Bandicoot.VCD' in cands, cands
assert 'mmce0:/POPS/Crash Bandicoot.VCD' in cands, cands

# 10. SB. prefix (SMB network share)
cands = resolve('smb0:/POPS/SB.Crash Bandicoot.ELF', None)
assert cands[0] == 'smb0:/POPS/Crash Bandicoot.VCD', cands
assert cands[1] == 'smb0:/Crash Bandicoot.VCD', cands
assert cands[2] == 'smb:/POPS/Crash Bandicoot.VCD', cands

# 11. SB. prefix in argument: routes to SMB network share
cands = resolve('mass0:/APPS/launcHER.elf', 'SB.Crash Bandicoot')
assert cands[0] == 'smb0:/POPS/Crash Bandicoot.VCD', cands
assert cands[1] == 'smb0:/Crash Bandicoot.VCD', cands
assert cands[2] == 'smb:/POPS/Crash Bandicoot.VCD', cands
assert lib.pops_get_active_sb_launch() == 1
lib.pops_set_active_sb_launch(0)

# 12. RiptOPL BDM selector: bare mass:/POPS/XX.<title>.ELF expands to mass0: and mass:
cands = resolve('mass:/POPS/XX.Crash Bandicoot.ELF', None)
assert 'mass0:/POPS/Crash Bandicoot.VCD' in cands, cands
assert 'mass:/POPS/Crash Bandicoot.VCD' in cands, cands

# 13. RiptOPL SMB selector: bare smb:/POPS/SB.<title>.ELF
cands = resolve('smb:/POPS/SB.Crash Bandicoot.ELF', None)
assert cands[0] == 'smb0:/POPS/Crash Bandicoot.VCD', cands
assert 'smb:/POPS/Crash Bandicoot.VCD' in cands, cands

# 14. RiptOPL APA HDD single-game partition: PP.<title>.ELF
cands = resolve('PP.Crash Bandicoot.ELF', None)
assert cands[0] == 'hdd0:PP.Crash Bandicoot:pfs:/Crash Bandicoot.VCD', cands
assert cands[1] == 'hdd0:PP.Crash Bandicoot:pfs:/IMAGE.VCD', cands
assert 'pfs0:/Crash Bandicoot.VCD' in cands, cands
assert 'hdd0:__.POPS:pfs:/Crash Bandicoot.VCD' in cands, cands

# 15. RiptOPL APA HDD hidden single-game partition: __.<title>.ELF
cands = resolve('__.Hidden Game.ELF', None)
assert cands[0] == 'hdd0:__.Hidden Game:pfs:/Hidden Game.VCD', cands
assert cands[1] == 'hdd0:__.Hidden Game:pfs:/IMAGE.VCD', cands
assert 'pfs0:/Hidden Game.VCD' in cands, cands

# 16. RiptOPL APA HDD pooled-container game: <title>.ELF
cands = resolve('Crash Bandicoot.ELF', None)
assert cands[0] == 'hdd0:__.POPS:pfs:/Crash Bandicoot.VCD', cands
assert cands[1] == 'hdd0:__.POPS:pfs:/IMAGE.VCD', cands
assert 'pfs0:/Crash Bandicoot.VCD' in cands, cands
assert 'hdd0:PP.Crash Bandicoot:pfs:/Crash Bandicoot.VCD' in cands, cands

# 17. i.Link BDMA mode with XX. prefix
cands = resolve_bdma('mass0:/APPS/launcHER.elf', 'XX.Crash Bandicoot', 5)
assert cands[0] == 'ilink:/POPS/Crash Bandicoot.VCD', cands
assert cands[1] == 'ilink:/POPS/IMAGE.VCD', cands
assert cands[2] == 'ilink:/Crash Bandicoot.VCD', cands
assert 'ilink0:/POPS/Crash Bandicoot.VCD' in cands, cands

print('Launcher argv compatibility PASS: duplicated self paths, partition identity, explicit targets, malformed argv, pops candidate resolution, bdma detection and routing')
