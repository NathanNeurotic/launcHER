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
