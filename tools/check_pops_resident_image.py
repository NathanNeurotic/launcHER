#!/usr/bin/env python3
"""Run the built POPS resident image under emulation, called the way POPS
calls it: the VBLANK_START entry through its registration, and the cheat and
$SET_TIMINGS entry through the jal launcHER writes at 0x21a63c in POPS's GP1
write path (where POPStarter runs them).

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
import unicorn.mips_const as _mips

img = open(sys.argv[1], 'rb').read()
BASE = 0x0143A000
(magic, ver, hs, fsz, isz, entry, cfga, display_entry, progressive_entry,
 pad_read_entry, pad_read_exit, gte_scale, gte_divide, gte_ultra,
 gp1_entry) = struct.unpack_from('<IHHIIIIIIIIIIII', img, 0)
assert magic == 0x5352484C and fsz == len(img), (hex(magic), fsz, len(img))
assert ver == 11 and hs == 56

mu = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
# The R5900 has MIPS IV's movz/movn, which unicorn's default R4000 model
# rejects. The 5Kf model accepts them and runs the rest unchanged.
mu.ctl_set_cpu_model(UC_CPU_MIPS64_5KF)

# The R5900's three-operand mult/multu (rd = LO as well) is not MIPS64;
# GCC uses it, e.g. to index the 12-byte cheat entries. Modelled here.
_MREGS = [getattr(_mips, 'UC_MIPS_REG_%d' % r) for r in range(32)]
def _r5900_mult(u, addr, size, _):
    word = struct.unpack('<I', u.mem_read(addr, 4))[0]
    if word >> 26 or (word & 63) not in (0x18, 0x19) or not (word >> 11) & 31:
        return
    rs, rt, rd = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
    a, b = u.reg_read(_MREGS[rs]) & 0xFFFFFFFF, u.reg_read(_MREGS[rt]) & 0xFFFFFFFF
    if word & 63 == 0x18:
        a, b = a - ((a & 0x80000000) << 1), b - ((b & 0x80000000) << 1)
    prod = (a * b) & 0xFFFFFFFFFFFFFFFF
    sx = lambda v: (v & 0xFFFFFFFF) - ((v & 0x80000000) << 1)
    lo, hi = sx(prod) & 0xFFFFFFFFFFFFFFFF, sx(prod >> 32) & 0xFFFFFFFFFFFFFFFF
    u.reg_write(UC_MIPS_REG_LO, lo); u.reg_write(UC_MIPS_REG_HI, hi)
    u.reg_write(_MREGS[rd], lo)
    u.reg_write(UC_MIPS_REG_PC, addr + 4)
mu.hook_add(UC_HOOK_CODE, _r5900_mult)
mu.mem_map(0x00000000, 0x02000000)      # EE RAM
mu.mem_map(0x40000000, 0x00200000)      # PS1 RAM as POPS maps it
mu.mem_map(0x70000000, 0x00004000)      # scratchpad
mu.mem_map(0x5F800000, 0x00001000)      # page $T codes address
mu.mem_write(BASE, img + bytes(isz - fsz))

# Fake POPS VBLANK_START handler at 0x21cd68: counts calls in 0x1000, returns -1.
code = [0x3c020000, 0x8c431000, 0x24630001, 0xac431000, 0x03e00008, 0x2402ffff]
mu.mem_write(0x0021CD68, b''.join(struct.pack('<I', w) for w in code))

def config(codes, safe=0, flags=1, pads=(0, 0, 0), divisor=0):
    blob = struct.pack('<QIIIIHHBBBB', 0, flags, 0x0021CD68, 0x70003364, 0, safe, len(codes), *pads, divisor)
    for code in codes:
        if len(code) == 2:  # PS1 code: (type << 24 | address, value)
            addr, val = code
            code = (addr >> 24, addr & 0x1FFFFF, val, 0, 0)
        kind, addr, val, cond, skip = code
        blob += struct.pack('<IIBBBx', addr, val, kind, cond, skip)
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

# The GP1 entry, reached by "jal entry" at 0x21a63c with di in the delay
# slot. POPS needs $v1 (0x10000) afterwards; the entry keeps every register
# it is given, and HI/LO, and returns to $ra (0x21a640 on the console).
GP1_REGS = [UC_MIPS_REG_AT, UC_MIPS_REG_V0, UC_MIPS_REG_V1] + \
    [getattr(_mips, 'UC_MIPS_REG_%d' % r) for r in range(4, 26)] + \
    [UC_MIPS_REG_GP, UC_MIPS_REG_FP]
def gp1():
    SENT = 0x0021A640
    mu.mem_write(SENT, struct.pack('<I', 0x42000039))
    want = {}
    for i, r in enumerate(GP1_REGS):
        v = 0x0123456789AB0000 + (i << 8) + 0x11
        if r == UC_MIPS_REG_V1:
            v = 0x10000
        mu.reg_write(r, v)
        want[r] = v
    mu.reg_write(UC_MIPS_REG_HI, 0x4848); mu.reg_write(UC_MIPS_REG_LO, 0x4c4c)
    mu.reg_write(UC_MIPS_REG_SP, 0x0008FF00)
    mu.reg_write(UC_MIPS_REG_RA, SENT)
    mu.emu_start(gp1_entry, SENT, count=200000)
    assert mu.reg_read(UC_MIPS_REG_PC) == SENT
    for r, v in want.items():
        assert mu.reg_read(r) == v, ('register %d changed' % r, hex(mu.reg_read(r)))
    assert (mu.reg_read(UC_MIPS_REG_HI), mu.reg_read(UC_MIPS_REG_LO)) == (0x4848, 0x4c4c), 'HI/LO'
    assert mu.reg_read(UC_MIPS_REG_SP) == 0x0008FF00, 'sp not restored'
    assert mu.reg_read(UC_MIPS_REG_RA) == SENT

# 1. Before POPS stores its RAM base: no writes, POPS handler still runs.
config([(0x30000010, 0x5A)])
gp1(); assert calls() == 0
assert mu.mem_read(0x40000010, 1) == b'\x00'
# 2. With the base: codes apply, every frame.
mu.mem_write(0x70003364, struct.pack('<I', 0x40000000))
mu.mem_write(0x40000020, struct.pack('<H', 7))
config([(0x30000010, 0x5A), (0x80000100, 0xBEEF), (0xD0000020, 7), (0x30000011, 1),
        (0xD0000020, 8), (0x30000012, 1)])
gp1(); assert calls() == 0
assert bytes(mu.mem_read(0x40000010, 3)) == b'\x5a\x01\x00'
assert bytes(mu.mem_read(0x40000100, 2)) == b'\xef\xbe'
mu.mem_write(0x40000010, b'\x00')
gp1()
assert mu.mem_read(0x40000010, 1) == b'\x5a' and calls() == 0
# VBLANK no longer runs the codes (POPStarter does not run them there).
mu.mem_write(0x40000010, b'\x00')
assert vblank() == 0xffffffff and calls() == 1
assert mu.mem_read(0x40000010, 1) == b'\x00'
mu.mem_write(0x1000, b'\x00' * 4)
# 3. $SAFEMODE: the codes are skipped while PS1 RAM 0x1ffea0 reads "STEM".
mu.mem_write(0x40000010, b'\x00')
config([(0x30000010, 0x5A)], safe=1)
mu.mem_write(0x401FFEA0, struct.pack('<I', 0x4D455453))
for _ in range(3):
    gp1()
assert mu.mem_read(0x40000010, 1) == b'\x00'
mu.mem_write(0x401FFEA0, b'\x00' * 4)
gp1()
assert mu.mem_read(0x40000010, 1) == b'\x5a' and calls() == 0
# $SAFEMODE2: skipped while 0x1ffdf4 is 2.
mu.mem_write(0x40000010, b'\x00')
config([(0x30000010, 0x5A)], safe=2)
mu.mem_write(0x401FFDF4, struct.pack('<I', 2))
gp1()
assert mu.mem_read(0x40000010, 1) == b'\x00'
mu.mem_write(0x401FFDF4, struct.pack('<I', 3))
gp1()
assert mu.mem_read(0x40000010, 1) == b'\x5a' and calls() == 0
# 4. PS2-format codes: an EE word write, a scratchpad halfword compare that
# gates the next code, and a byte write to the 0x5F800000 page.
mu.mem_write(0x70000100, struct.pack('<H', 0x1234))
ps2 = [(0x92, 0x00100000, 0xDEADBEEF, 0, 0), (0x95, 0x100, 0x1234, 1, 1),
       (0x98, 0x10, 0x77, 0, 0), (0x30000010, 0x5A)]
mu.mem_write(0x40000010, b'\x00')
config(ps2)
gp1()
assert bytes(mu.mem_read(0x00100000, 4)) == struct.pack('<I', 0xDEADBEEF)
assert mu.mem_read(0x5F800010, 1) == b'\x77' and mu.mem_read(0x40000010, 1) == b'\x5a'
mu.mem_write(0x5F800010, b'\x00')
mu.mem_write(0x70000100, struct.pack('<H', 0x1235))
gp1()
assert mu.mem_read(0x5F800010, 1) == b'\x00', 'gated $T write ran'
print('resident image under emulation: PASS (VBLANK entry %#x, GP1 entry %#x, config %#x, %d bytes resident; registers kept)' % (entry, gp1_entry, cfga, isz))

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


# Pad commands. ID override: written through the GP1 entry (where POPStarter
# writes it) into the two per-port state blocks, nothing else touched;
# VBLANK_START no longer writes it.
PAD = 0x00507000
mu.mem_write(PAD, bytes(range(256)) * 2)
before = bytes(mu.mem_read(PAD, 0x120))
config([], flags=1 << 3, pads=(2, 0x41, 0x73))
vblank()
assert bytes(mu.mem_read(PAD, 0x120)) == before, 'VBLANK must not write the ID'
n = calls()
gp1()
after = bytes(mu.mem_read(PAD, 0x120))
assert after[0x90 + 0x34] == 0x73 and after[0x34] == before[0x34], 'port selection'
assert sum(a != b for a, b in zip(before, after)) == 1 and calls() == n
config([], flags=(1 << 3) | 1, pads=(3, 0x01, 0x41))
gp1()
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


# Widescreen family. POPS's GTE perspective transform stores MAC1 at
# 0x2089a8 and IR1 at 0x208a2c (both sw $8, ...($a0)); the hooks replace
# those stores and their delay slots (sw $9) still run. Expected values use
# the original's arithmetic: 32-bit product x * 75, then a 32-bit signed
# division truncating toward zero.
def s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v >> 31 else v

def div_trunc(a, d):
    q = abs(a) // abs(d)
    return q if (a < 0) == (d < 0) else -q

def gte_words(mac1_store, ir1_store):
    words = {0x2089A8: mac1_store, 0x2089AC: 0xAC890068, 0x2089B0: 0xAC8A006C,
             0x208A2C: ir1_store, 0x208A30: 0xAC890028, 0x208A34: 0xAC8A002C}
    for a, w in words.items():
        mu.mem_write(a, struct.pack('<I', w))
    mu.ctl_remove_cache(0x2089A0, 0x208A40)

GTE = 0x00090000
REGS = [getattr(sys.modules['unicorn.mips_const'], 'UC_MIPS_REG_%d' % i) for i in range(1, 32)]

def gte_store(start, stop, x, y):
    mu.mem_write(GTE, b'\xa5' * 0x100)
    before = {}
    for i, reg in enumerate(REGS, 1):
        before[i] = (0x11110000 + i) & 0xFFFFFFFFFFFFFFFF
        mu.reg_write(reg, before[i])
    mu.reg_write(UC_MIPS_REG_A0, GTE)
    before[4] = GTE
    mu.reg_write(UC_MIPS_REG_8, x & 0xFFFFFFFFFFFFFFFF)
    before[8] = x & 0xFFFFFFFFFFFFFFFF
    mu.reg_write(UC_MIPS_REG_9, 0x0BADF00D)
    before[9] = 0x0BADF00D
    # Stop with a code hook: unicorn's `until` misbehaves when consecutive
    # runs start inside the same translated block.
    mu.ctl_remove_cache(0x208900, 0x208B00)
    h = mu.hook_add(UC_HOOK_CODE, lambda uc, pc, size, u: uc.emu_stop(), begin=stop, end=stop)
    mu.emu_start(start, 0x00080000, count=64)
    mu.hook_del(h)
    assert mu.reg_read(UC_MIPS_REG_PC) == stop, (hex(start), hex(mu.reg_read(UC_MIPS_REG_PC)), x)
    for i, reg in enumerate(REGS, 1):
        if i not in (2, 3, 8):
            assert mu.reg_read(reg) == before[i], ('register clobbered', i)
    return s32(mu.reg_read(UC_MIPS_REG_8)), bytes(mu.mem_read(GTE, 0x100))

rng = random.Random(0x57494445)
xs = [0, 1, -1, 99, -99, 100, -100, 0x7FFF, -0x8000, 28633115, 28633116, -28633116,
      0x7FFFFFFF, -0x80000000] + [s32(rng.getrandbits(32)) for _ in range(200)] + \
     [rng.randrange(-0x10000, 0x10000) for _ in range(200)]
cases = 0
for mode, divisor in (('16:9', 100), ('ultra', 100), ('eyefinity', 4)):
    config([], flags=1 << 5, divisor=divisor)
    mac1 = gte_divide if mode == 'eyefinity' else gte_scale
    gte_words(0x08000000 | (mac1 >> 2), 0x08000000 | (gte_ultra >> 2) if mode == 'ultra' else 0xAC880024)
    for x in xs:
        want = div_trunc(x if mode == 'eyefinity' else s32(x * 75), divisor)
        t0, mem = gte_store(0x2089A8, 0x2089B0, x, 0)
        assert t0 == want, (mode, x, t0, want)
        assert struct.unpack_from('<i', mem, 0x64)[0] == want and mem[0x68:0x6C] == b'\x0d\xf0\xad\x0b'
        assert mem[:0x64] == b'\xa5' * 0x64 and mem[0x6C:] == b'\xa5' * 0x94
        t0, mem = gte_store(0x208A2C, 0x208A34, x, 0)
        if mode == 'ultra':
            want2 = div_trunc(s32(x * 75), 100)
            assert t0 == want2 and struct.unpack_from('<i', mem, 0x64)[0] == want2
            assert mem[0x24:0x28] == b'\xa5' * 4, 'ultra leaves IR1 unstored, like the original'
        else:
            assert t0 == s32(x) and struct.unpack_from('<i', mem, 0x24)[0] == s32(x)
        assert mem[0x28:0x2C] == b'\x0d\xf0\xad\x0b'
        cases += 1
# Zero divisor: x passes through unscaled except for the product.
config([], flags=1 << 5, divisor=0)
gte_words(0x08000000 | (gte_divide >> 2), 0xAC880024)
assert gte_store(0x2089A8, 0x2089B0, 12345, 0)[0] == 12345
print('resident widescreen GTE stubs: PASS (%d values x 3 modes, both sites, 28 registers kept)' % len(xs))


# $SET_TIMINGS through the built GP1 entry: waits for the slot 0 VMC
# image, restores a saved copy once, then adjusts from the pads every frame.
# Without the save flag the card copy is not written; with it (the launcher
# sets it for $SET_TIMINGS) new values are mirrored there, as in POPStarter.
TREADY = cfga + 32 + (2 * 256 + 4) * 12
u32 = lambda a: struct.unpack('<I', mu.mem_read(a, 4))[0]
w32 = lambda a, v: mu.mem_write(a, struct.pack('<I', v & 0xffffffff))
timings = lambda: (u32(0x502770), u32(0x700033e0), u32(0x700033e4))
card = lambda: tuple(u32(0x508130 + 4 * i) for i in range(4))
def pads(p0, p1):
    mu.mem_write(0x507002, struct.pack('<H', p0))
    mu.mem_write(0x507092, struct.pack('<H', p1))
for save in (0, 1):
    mu.mem_write(0x507930, bytes(0x1000))
    mu.mem_write(TREADY, b'\x00')
    w32(0x502770, 0x100); w32(0x700033e0, 0x200); w32(0x700033e4, 0x300)
    if not save:
        for i, v in enumerate((0x3e2d3130, 0x111, 0x222, 0x333)):
            w32(0x508130 + 4 * i, v)
    config([], flags=(1 << 6) | (save << 7))
    pads(0xfbff, 0xfbff)
    n = calls()
    gp1()
    assert timings() == (0x100, 0x200, 0x300) and calls() == n, 'waits for the VMC image'
    w32(0x507930, 0x434d)
    gp1()
    want = (0x111, 0x222, 0x333) if not save else (0x100, 0x200, 0x300)
    assert timings() == want, [hex(v) for v in timings()]
    base = list(want)
    for p0, p1, idx, step in ((0xfbff, 0xffff, 1, 1), (0xfeff, 0xffff, 1, -1), (0xf7ff, 0xffff, 2, 1),
                              (0xfdff, 0xffff, 2, -1), (0xffff, 0xfbff, 0, 1), (0xffff, 0xfeff, 0, -1),
                              (0xffff, 0xf7ff, 0, 0x10), (0xffff, 0xfdff, 0, -0x10), (0xfbff, 0xf7ff, 1, 1),
                              (0xfaff, 0xffff, None, 0), (0xffff, 0xffff, None, 0)):
        pads(p0, p1)
        gp1()
        if idx is not None:
            base[idx] = (base[idx] + step) & 0xffffffff
        assert timings() == tuple(base), (hex(p0), hex(p1), [hex(v) for v in timings()])
    expect_card = (0x3e2d3130, 0x111, 0x222, 0x333) if not save else (0x3e2d3130, *base)
    assert card() == expect_card, [hex(v) for v in card()]
print('resident $SET_TIMINGS: PASS (VMC wait, restore, 11 pad cases, card untouched unless save flag)')

# 6. The built-in per-game list's chain work (pops_builtin_db.h), in the
# original's order: breakpoint handler (0x01460000) after the controller
# IDs, the second LibCrypt code from the config after $SET_TIMINGS, the
# game-fix code (0x01410000) just before the cheats. Each piece appends its
# number to a log word; the fix code and a cheat write the same PS1 byte so
# the cheat's value shows it ran last. All three are k0/k1-only leaves,
# like the original's. gp is left alone (the breakpoint handler uses POPS's).
LC2 = cfga + 32 + (2 * 256 + 4) * 12 + 4  # after timings_ready + reserved[3]
def leaf(n, extra=()):
    words = [0x8c1a1204, 0x001ad100, 0x375a0000 | n, 0xac1a1204] + list(extra) + [0x03e00008, 0]
    return b''.join(struct.pack('<I', w) for w in words)
mu.mem_write(0x01460000, leaf(1))
mu.mem_write(0x01410000, leaf(3, (0x241b0011, 0x3c1a4000, 0xa35b0010)))  # PS1 0x10 = 0x11
mu.mem_write(0x1204, b'\0' * 4)
mu.mem_write(0x40000010, b'\0')
config([(0x30000010, 0x5A)], flags=1 | (1 << 8) | (1 << 9) | (1 << 10))
lc2 = leaf(2)
mu.mem_write(LC2, lc2 + b'\0' * (92 - len(lc2)))
gp1()  # checks every register, gp included, comes back unchanged
assert u32(0x1204) == 0x123, hex(u32(0x1204))
assert mu.mem_read(0x40000010, 1) == b'\x5a', 'cheats must run after the fix code'
# Without the flags none of them runs.
mu.mem_write(0x1204, b'\0' * 4)
config([(0x30000010, 0x5A)])
gp1()
assert u32(0x1204) == 0
print('resident built-in chain calls: PASS (break, LibCrypt 2, fix, then cheats; gp kept)')

# 7. The in-game reset (the original's block at 0x232ce8, always live):
# while port 0's buttons read exactly 0xbcfe (SELECT+L2+R2+CROSS), the EE
# scratchpad word 0 is set to reset_vector; any other reading leaves it.
# $RESET_WARMBOOT only changes the vector (pops_apply_reset_warmboot).
RESET_VECTOR = LC2 + 23 * 4
config([(0x30000010, 0x5A)])
mu.mem_write(RESET_VECTOR, struct.pack('<I', 0xBFC0D8D0))
mu.mem_write(0x70000000, b'\0' * 4)
mu.mem_write(PAD + 2, struct.pack('<H', 0xBCFE))
gp1()
assert u32(0x70000000) == 0xBFC0D8D0, hex(u32(0x70000000))
mu.mem_write(0x70000000, b'\0' * 4)
for other in (0xBCFF, 0xFFFF, 0x3CFE, 0x0000):
    mu.mem_write(PAD + 2, struct.pack('<H', other))
    gp1()
    assert u32(0x70000000) == 0, hex(other)
mu.mem_write(PAD + 2, struct.pack('<H', 0xFFFF))
print('resident in-game reset: PASS (combo stores the vector to scratchpad 0, nothing else does)')
