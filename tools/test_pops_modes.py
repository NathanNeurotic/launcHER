#!/usr/bin/env python3
"""Compare complete compatibility-patched buffers with original dispatch writes.

Optional --elf and --decompile verify the reference against external specimens.
No proprietary payload is embedded in these tests.
"""
import argparse
import ctypes as c
import json
import os
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--elf', type=Path)
parser.add_argument('--decompile', type=Path)
args = parser.parse_args()
reference = json.loads((ROOT / 'tools/fixtures/pops_compat_reference.json').read_text())['writes']
if args.decompile:
    text = args.decompile.read_text()
    text = text[text.index('void FUN_008dc2c4('):]
    text = text[:text.index('/* ---------------------------------------------------------------- */')]
    for mode, expected in reference.items():
        branch = re.search(r'(?:if|else if) \(\(?param_1 == ' + mode +
                           r'\).*?\{(.*?)(?=\n    \}\n)', text, re.S).group(1)
        actual = [[int(a, 16), int(v, 16) & (0xffffffff if fn == '008dc94c' else 255),
                   4 if fn == '008dc94c' else 1]
                  for fn, v, a in re.findall(
                      r'FUN_(008dc94c|008dc8e4)\((0x[0-9a-f]+|0),(0x[0-9a-f]+)\)', branch)]
        assert actual == expected, mode
size = 0x302e60
pristine = bytearray(size)
# Independent pristine instruction values at all nonzero guarded sites.
for address, value, width in [(0x210318, 0x8f828228, 4), (0x21032c, 0x1443fffa, 4),
                              (0x20083c, 0x0441000a, 4), (0x20085c, 0x1000fffa, 4),
                              (0x20de9c, 0x0c0836ee, 4), (0x21af70, 0x64, 1)]:
    pristine[address - 0x200000:address - 0x200000 + width] = value.to_bytes(width, 'little')
if args.elf:
    elf = args.elf.read_bytes()
    phoff = struct.unpack_from('<I', elf, 28)[0]
    ents, count = struct.unpack_from('<HH', elf, 42)
    pristine = bytearray(size)
    found = False
    for i in range(count):
        typ, off, va, _, fs, _, _, _ = struct.unpack_from('<8I', elf, phoff + i * ents)
        if typ == 1 and 0x200000 <= va < 0x200000 + size and fs:
            assert va + fs <= 0x200000 + size
            pristine[va - 0x200000:va - 0x200000 + fs] = elf[off:off + fs]
            found = True
    assert found, 'Supported external core segments missing'
build = ROOT / 'build/pops-host/modes'
build.mkdir(parents=True, exist_ok=True)
library = build / ('modes.dll' if os.name == 'nt' else 'modes.so')
subprocess.run(['gcc', '-shared', '-fPIC', '-O2', '-I', str(ROOT / 'common/include'),
                str(ROOT / 'common/src/pops_modes_patches.c'), '-o', str(library)], check=True)
lib = c.CDLL(str(library))
lib.pops_apply_compat_modes.argtypes = [c.c_void_p, c.c_size_t, c.c_uint8]
for mask in range(256):
    memory = bytearray(pristine)
    pointer = (c.c_uint8 * size).from_buffer(memory)
    result = lib.pops_apply_compat_modes(pointer, size, mask)
    if mask & 0xa0:
        assert result < 0 and memory == pristine, mask
        continue
    expected = bytearray(pristine)
    for mode, writes in reference.items():
        if mask & (1 << (int(mode) - 1)):
            for address, value, width in writes:
                offset = address - 0x200000
                expected[offset:offset + width] = value.to_bytes(width, 'little')
    assert result == 0 and memory == expected, mask
# Late guard failure must preserve even earlier selected sites.
memory = bytearray(pristine)
memory[0x1e45c] ^= 1
before = bytes(memory)
pointer = (c.c_uint8 * size).from_buffer(memory)
assert lib.pops_apply_compat_modes(pointer, size, 0x5f) < 0 and memory == before
assert lib.pops_apply_compat_modes(pointer, 0x100, 0x01) < 0 and memory == before
print('Compatibility dispatch PASS: 64 whole-buffer combinations, 192 unsupported masks, guards and bounds' +
      ('; external original dispatcher and ELF verified' if args.elf and args.decompile else ''))
