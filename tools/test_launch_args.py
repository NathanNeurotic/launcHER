#!/usr/bin/env python3
"""Exercise the production launcher argv normalization without PS2SDK."""
import ctypes as c
import os
from pathlib import Path
import shutil
import subprocess

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

# A selected CUE is one opaque game argument; preserve its folder, slash and spaces.
# The folder name need not describe the chosen disc (it may still say Disc 1).
game = 'Driver 2 - Back on the Streets (Disc 1) [SLES_029.94]'
cue = game + '/Driver 2 - Back on the Streets (Disc 2).cue'
for argument in (game, cue):
    forwarded = ['hdd0:__.EMBER:pfs:/EMBER/ember.elf', 'pfs0:/EMBER/ember.elf',
                 argument, '-skip_argv0', '-dev9=NICHDD']
    check([self, bare] + forwarded, [self] + forwarded)
    check(['mass0:/APPS/renamed.elf', 'mass0:/APPS/renamed.elf',
           'mass0:/EMBER/ember.elf', argument],
          ['mass0:/APPS/renamed.elf', 'mass0:/EMBER/ember.elf', argument])
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
print('Launcher argv compatibility PASS: duplicated self paths, partition identity, explicit targets, malformed argv')
