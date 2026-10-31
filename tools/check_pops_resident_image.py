#!/usr/bin/env python3
"""Run the built POPS resident image under emulation, called the way POPS's
VBLANK_START registration calls it.

Manual check, not run by CI: needs `pip install unicorn` and the image CMake
builds (build/launcher/pops_resident.bin).

    python tools/check_pops_resident_image.py build/launcher/pops_resident.bin

It checks that the entry chains to POPS's handler (a stub here) every time,
preserves $s0/$sp, does nothing before POPS has stored its PS1 RAM base,
applies codes and conditionals, and honours the $SAFEMODE delay. Passing
here is not a console test."""
import struct, sys
from unicorn import *
from unicorn.mips_const import *

img = open(sys.argv[1], 'rb').read()
BASE = 0x0143A000
magic, ver, hs, fsz, isz, entry, cfga = struct.unpack_from('<IHHIIII', img, 0)
assert magic == 0x5352484C and fsz == len(img), (hex(magic), fsz, len(img))

mu = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
mu.mem_map(0x00000000, 0x02000000)      # EE RAM
mu.mem_map(0x40000000, 0x00200000)      # PS1 RAM as POPS maps it
mu.mem_map(0x70000000, 0x00004000)      # scratchpad
mu.mem_write(BASE, img + bytes(isz - fsz))

# Fake POPS VBLANK_START handler at 0x21cd68: counts calls in 0x1000, returns -1.
code = [0x3c020000, 0x8c431000, 0x24630001, 0xac431000, 0x03e00008, 0x2402ffff]
mu.mem_write(0x0021CD68, b''.join(struct.pack('<I', w) for w in code))

def config(codes, safe=0):
    blob = struct.pack('<IIIIHH', 1, 0x0021CD68, 0x70003364, 0, safe, len(codes))
    for addr, val in codes:
        blob += struct.pack('<IHBx', addr & 0x1FFFFF, val, addr >> 24)
    mu.mem_write(cfga, blob)

def vblank(cause=2):
    SENT = 0x00080000
    mu.mem_write(SENT, b'\x00' * 4)
    mu.reg_write(UC_MIPS_REG_SP, 0x0008FF00)
    mu.reg_write(UC_MIPS_REG_A0, cause)
    mu.reg_write(UC_MIPS_REG_RA, SENT)
    mu.reg_write(UC_MIPS_REG_S0, 0x1234)
    mu.emu_start(entry, SENT, count=200000)
    assert mu.reg_read(UC_MIPS_REG_PC) == SENT
    assert mu.reg_read(UC_MIPS_REG_S0) == 0x1234, 's0 not preserved'
    assert mu.reg_read(UC_MIPS_REG_SP) == 0x0008FF00, 'sp not restored'
    return mu.reg_read(UC_MIPS_REG_V0) & 0xffffffff

calls = lambda: struct.unpack('<I', mu.mem_read(0x1000, 4))[0]

# 1. Before POPS stores its RAM base: no writes, POPS handler still runs.
config([(0x30000010, 0x5A)])
assert vblank() == 0xffffffff and calls() == 1
assert mu.mem_read(0x40000010, 1) == b'\x00'
# 2. With the base: codes apply, every frame.
mu.mem_write(0x70003364, struct.pack('<I', 0x40000000))
mu.mem_write(0x40000020, struct.pack('<H', 7))
config([(0x30000010, 0x5A), (0x80000100, 0xBEEF), (0xD0000020, 7), (0x30000011, 1),
        (0xD0000020, 8), (0x30000012, 1)])
assert vblank() == 0xffffffff and calls() == 2
assert bytes(mu.mem_read(0x40000010, 3)) == b'\x5a\x01\x00'
assert bytes(mu.mem_read(0x40000100, 2)) == b'\xef\xbe'
mu.mem_write(0x40000010, b'\x00')
vblank()
assert mu.mem_read(0x40000010, 1) == b'\x5a' and calls() == 3
# 3. $SAFEMODE: 3-frame delay here.
mu.mem_write(0x40000010, b'\x00')
config([(0x30000010, 0x5A)], safe=3)
for _ in range(3):
    vblank()
assert mu.mem_read(0x40000010, 1) == b'\x00'
vblank()
assert mu.mem_read(0x40000010, 1) == b'\x5a' and calls() == 7
print('resident image under emulation: PASS (entry %#x, config %#x, %d bytes resident)' % (entry, cfga, isz))
