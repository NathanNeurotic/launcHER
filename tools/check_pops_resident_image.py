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
import os, struct, sys
from unicorn import *
from unicorn.mips_const import *

img = open(sys.argv[1], 'rb').read()
BASE = 0x0143A000
magic, ver, hs, fsz, isz, entry, cfga, display_entry, progressive_entry = struct.unpack_from('<IHHIIIIII', img, 0)
assert magic == 0x5352484C and fsz == len(img), (hex(magic), fsz, len(img))
assert ver == 3 and hs == 32

mu = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
mu.mem_map(0x00000000, 0x02000000)      # EE RAM
mu.mem_map(0x40000000, 0x00200000)      # PS1 RAM as POPS maps it
mu.mem_map(0x70000000, 0x00004000)      # scratchpad
mu.mem_write(BASE, img + bytes(isz - fsz))

# Fake POPS VBLANK_START handler at 0x21cd68: counts calls in 0x1000, returns -1.
code = [0x3c020000, 0x8c431000, 0x24630001, 0xac431000, 0x03e00008, 0x2402ffff]
mu.mem_write(0x0021CD68, b''.join(struct.pack('<I', w) for w in code))

def config(codes, safe=0):
    blob = struct.pack('<QIIIIHH', 0, 1, 0x0021CD68, 0x70003364, 0, safe, len(codes))
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

# Mid-function display entry: no call/return ABI and no stack/gp dependency.
# Exercise the real jump and delay slot from the Sony hook location, then
# inspect all registers at its continuation before stock code resumes.
mu.mem_write(0x21a094, struct.pack('<II', 0x08000000 | (display_entry >> 2), 0x3c031200))
display_seen = False
active_display_entry = display_entry
def display_stop(uc, pc, size, unused):
    global display_seen
    if pc == active_display_entry:
        display_seen = True
    elif pc == 0x21a098 and display_seen:
        uc.emu_stop()
display_hook = mu.hook_add(UC_HOOK_CODE, display_stop)
entries = [(display_entry, cfga)]
if os.environ.get('POPSTARTER_TEST_ELF'):
    from pathlib import Path
    from trace_original_pops_io import decode_main
    original = decode_main(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())
    # Original loader copies 0xd60 bytes from 0x983890 to 0x238a90.
    # This optional comparison executes its fixed DISPLAY entry in memory.
    mu.mem_write(0x238a90, original[0x983890 - 0x870000:0x983890 - 0x870000 + 0xd60])
    entries.append((0x239768, 0x239778))
for value in (0, 1, 0xffffffffffffffff, 0x001bf9ff01832280):
    outcomes = []
    for active_display_entry, value_addr in entries:
        mu.mem_write(0x21a094, struct.pack('<II', 0x08000000 | (active_display_entry >> 2), 0x3c031200))
        mu.ctl_remove_cache(0x21a094, 0x21a09c)
        mu.mem_write(value_addr, struct.pack('<Q', value))
        before = {}
        for i in range(1, 32):
            reg = globals()['UC_MIPS_REG_' + str(i)]
            before[reg] = 0x10000000 + 0x100 * i
            mu.reg_write(reg, before[reg])
        # Verified predecessor at 0x21a090, not an arbitrary incoming v0.
        before[UC_MIPS_REG_V0] = 0x12000000
        mu.reg_write(UC_MIPS_REG_V0, 0x12000000)
        resident_before = bytes(mu.mem_read(BASE, isz))
        display_seen = False
        mu.emu_start(0x21a094, 0x00080000, count=32)
        assert display_seen and mu.reg_read(UC_MIPS_REG_PC) == 0x21a098
        actual = {reg: mu.reg_read(reg) for reg in before}
        for reg, old in before.items():
            want = {UC_MIPS_REG_V0: 0x12000000, UC_MIPS_REG_V1: 0x12000000,
                    UC_MIPS_REG_A1: value}.get(reg, old)
            assert actual[reg] == want, (reg, hex(actual[reg]), hex(want))
        assert bytes(mu.mem_read(BASE, isz)) == resident_before
        outcomes.append(actual)
    if len(outcomes) == 2:
        assert outcomes[0] == outcomes[1]
mu.hook_del(display_hook)
print('resident display bridge: PASS (hook, delay slot, 31 register checks x 4 values)')
if len(entries) == 2:
    print('original fixed DISPLAY entry vs built bridge: PASS (4 values; 64-bit GPR view)')
