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
(magic, ver, hs, fsz, isz, entry, cfga, display_entry, progressive_entry,
 pad_read_entry, pad_read_exit) = struct.unpack_from('<IHHIIIIIIII', img, 0)
assert magic == 0x5352484C and fsz == len(img), (hex(magic), fsz, len(img))
assert ver == 4 and hs == 40

mu = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
# The R5900 has MIPS IV's movz/movn, which unicorn's default R4000 model
# rejects. The 5Kf model accepts them and runs the rest unchanged.
mu.ctl_set_cpu_model(UC_CPU_MIPS64_5KF)
mu.mem_map(0x00000000, 0x02000000)      # EE RAM
mu.mem_map(0x40000000, 0x00200000)      # PS1 RAM as POPS maps it
mu.mem_map(0x70000000, 0x00004000)      # scratchpad
mu.mem_write(BASE, img + bytes(isz - fsz))

# Fake POPS VBLANK_START handler at 0x21cd68: counts calls in 0x1000, returns -1.
code = [0x3c020000, 0x8c431000, 0x24630001, 0xac431000, 0x03e00008, 0x2402ffff]
mu.mem_write(0x0021CD68, b''.join(struct.pack('<I', w) for w in code))

def config(codes, safe=0, flags=1, pads=(0, 0, 0)):
    blob = struct.pack('<QIIIIHHBBBx', 0, flags, 0x0021CD68, 0x70003364, 0, safe, len(codes), *pads)
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


# Pad commands. ID override: written every VBLANK_START into the two
# per-port state blocks, nothing else touched, POPS's handler still runs.
PAD = 0x00507000
mu.mem_write(PAD, bytes(range(256)) * 2)
before = bytes(mu.mem_read(PAD, 0x120))
config([], flags=1 << 3, pads=(2, 0x41, 0x73))
n = calls()
vblank()
after = bytes(mu.mem_read(PAD, 0x120))
assert after[0x90 + 0x34] == 0x73 and after[0x34] == before[0x34], 'port selection'
assert sum(a != b for a, b in zip(before, after)) == 1 and calls() == n + 1
config([], flags=(1 << 3) | 1, pads=(3, 0x01, 0x41))
vblank()
assert mu.mem_read(PAD + 0x34, 1) == b'\x01' and mu.mem_read(PAD + 0xC4, 1) == b'\x41'
print('resident pad ID override: PASS')

# $D2LS: POPS's pad read at 0x237798 with both hook words patched the way
# pops_resident_hook_pads writes them. The body between them is a stand-in
# that opens the 0x30 frame, records $v1 (restored to 0x70) and returns 20
# bytes read, like a pressure-mode reading.
def pad_read_core(entry_jump, exit_jump):
    words = {0x237798: 0x0080382D, 0x23779C: entry_jump, 0x2377A0: 0x2404001C,
             0x2377A4: 0x27BDFFD0, 0x2377A8: 0x24020014, 0x2377AC: 0xAC031100,
             0x2377B0: 0x08000000 | (0x23780C >> 2), 0x2377B4: 0,
             0x23780C: exit_jump, 0x237810: 0x27BD0030}
    for a, w in words.items():
        mu.mem_write(a, struct.pack('<I', w))
    mu.ctl_remove_cache(0x237798, 0x237818)

def pad_read(buf):
    SENT = 0x00080000
    mu.reg_write(UC_MIPS_REG_SP, 0x0008FF00)
    mu.reg_write(UC_MIPS_REG_A0, 0)
    mu.reg_write(UC_MIPS_REG_A1, 0)
    mu.reg_write(UC_MIPS_REG_A2, buf)
    mu.reg_write(UC_MIPS_REG_RA, SENT)
    for i, reg in enumerate((UC_MIPS_REG_S0, UC_MIPS_REG_S1, UC_MIPS_REG_GP, UC_MIPS_REG_FP)):
        mu.reg_write(reg, 0x5000 + i)
    mu.mem_write(0x1100, b'\0' * 4)
    mu.emu_start(0x237798, SENT, count=20000)
    assert mu.reg_read(UC_MIPS_REG_PC) == SENT
    assert mu.reg_read(UC_MIPS_REG_V0) == 20, 'pad read result lost'
    assert mu.reg_read(UC_MIPS_REG_SP) == 0x0008FF00, 'sp not restored'
    for i, reg in enumerate((UC_MIPS_REG_S0, UC_MIPS_REG_S1, UC_MIPS_REG_GP, UC_MIPS_REG_FP)):
        assert mu.reg_read(reg) == 0x5000 + i, 'callee-saved register clobbered'
    assert struct.unpack('<I', mu.mem_read(0x1100, 4))[0] == 0x70, '$v1 not restored'

import random
rng = random.Random(0x44324C53)
samples = [bytes([0, 0x79, 0xFF, 0xFF, 0x80, 0x80, 0x80, 0x80] + [0] * 12),
           bytes([0, 0x79, 0x0F, 0xFF, 0x80, 0x80, 0x00, 0xFF, 0, 0xFF, 0, 0x80] + [0] * 8)]
samples += [bytes(rng.randrange(256) for _ in range(20)) for _ in range(300)]

pad_read_core(0x08000000 | (pad_read_entry >> 2), 0x08000000 | (pad_read_exit >> 2))
config([], flags=1 << 4)
built = []
for data in samples:
    for port in (0, 1):
        mu.mem_write(PAD + 0x90 * port, data)
        pad_read(PAD + 0x90 * port)
        out = bytes(mu.mem_read(PAD + 0x90 * port, 20))
        assert out[:2] == data[:2] and out[3:6] == data[3:6] and out[12:] == data[12:]
        assert out[2] & 0x0F == data[2] & 0x0F
        built.append(out)
# Not a pad state block, or $D2LS off: the reading is left alone.
mu.mem_write(0x00600000, samples[1])
pad_read(0x00600000)
assert bytes(mu.mem_read(0x00600000, 20)) == samples[1]
config([], flags=0)
mu.mem_write(PAD, samples[1])
pad_read(PAD)
assert bytes(mu.mem_read(PAD, 20)) == samples[1]
print('resident D2LS pad read hooks: PASS (%d readings, registers, result, frame)' % len(built))

if os.environ.get('POPSTARTER_TEST_ELF'):
    # Optional: the original copies its swap routine (0xf4 bytes from
    # 0x972390) to 0x231ed0 and jumps to 0x231ed0/0x231edc from the same two
    # sites. Run it on the same readings in memory and compare results.
    mu.mem_write(0x231ED0, original[0x972390 - 0x870000:0x972390 - 0x870000 + 0xF4])
    pad_read_core(0x0808C7B4, 0x0808C7B7)
    theirs = []
    for data in samples:
        for port in (0, 1):
            mu.mem_write(PAD + 0x90 * port, data)
            pad_read(PAD + 0x90 * port)
            theirs.append(bytes(mu.mem_read(PAD + 0x90 * port, 20)))
    assert theirs == built, next((s.hex(), a.hex(), b.hex()) for s, a, b in
                                 zip([d for d in samples for _ in (0, 1)], built, theirs) if a != b)
    print('original D2LS swap vs built resident: PASS (%d readings)' % len(theirs))
