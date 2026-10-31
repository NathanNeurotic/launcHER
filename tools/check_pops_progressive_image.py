#!/usr/bin/env python3
"""Execute the built owned progressive bridge, with explicit EE-only adapters.

Unicorn executes the real C adapter, branches and ordinary MIPS instructions.
Only owned bridge LQ/SQ and HI1/LO1 transfers use private NOP translation slots
and explicit semantics outside hooks. Opaque upper GPR lanes are poisoned on
C entry to verify restoration, not claimed as a general R5900 emulator.
Original instructions execute in the separate pinned bounded interpreter.
"""
import argparse
import os
from pathlib import Path
import random
import struct

import unicorn as u
from unicorn import mips_const as r

from test_pops_progressive import FIELDS, cases, record
from trace_original_pops_display import OriginalDisplay

BASE, CONT, HOOK = 0x143a000, 0x21a098, 0x21a094
MASK = (1 << 64) - 1


def inspect(image):
    magic, ver, hs, fsz, isz, _, _, _, entry = struct.unpack_from('<IHHIIIIII', image)
    assert (magic, ver, hs, fsz) == (0x5352484c, 4, 40, len(image))
    assert fsz <= isz <= 0x26000 and BASE + hs <= entry < BASE + fsz
    words = {BASE + i: struct.unpack_from('<I', image, i)[0] for i in range(0, fsz, 4)}
    end = next(pc + 8 for pc in range(entry, BASE + fsz, 4) if words[pc] == 0x08086826)
    assert words[end - 4] == 0x3c021200
    calls = [((w & 0x3ffffff) << 2) for pc, w in words.items() if entry <= pc < end and w >> 26 == 3]
    assert len(calls) == 1 and BASE + hs <= calls[0] < BASE + fsz
    special = {pc: w for pc, w in words.items() if entry <= pc < end and
               (w >> 26 in (0x1e, 0x1f) or w >> 26 == 0x1c and w & 63 in (0x10, 0x11, 0x12, 0x13))}
    assert len(special) == 66  # 31 SQ, 31 LQ, four HI1/LO1 transfers
    private = bytearray(image)
    for pc in special:
        struct.pack_into('<I', private, pc - BASE, 0)
    return entry, calls[0], isz, special, bytes(private)


def execute(image, state, expected_display, seed):
    entry, callee, isz, special, private = inspect(image)
    mu = u.Uc(u.UC_ARCH_MIPS, u.UC_MODE_MIPS64 | u.UC_MODE_LITTLE_ENDIAN)
    mu.mem_map(0, 0x2000000)
    mu.mem_map(0x70000000, 0x4000)
    mu.mem_write(BASE, private + bytes(isz - len(private)))
    mu.mem_write(HOOK, struct.pack('<II', 0x08000000 | (entry >> 2), 0x3c031200))
    for name, (address, width) in FIELDS.items():
        mu.mem_write(address, int(getattr(state, name)).to_bytes(width, 'little'))
    rng = random.Random(seed)
    saved_low = [rng.getrandbits(32) for _ in range(32)]
    saved_high = [rng.getrandbits(64) for _ in range(32)]
    upper = saved_high.copy()
    saved_low[2], saved_low[28], saved_low[29] = 0x12000000, 0x50a670, 0x1d0000
    mu.mem_write(saved_low[29] - 0x1000, b'\xa5' * 0x1010)
    for i in range(1, 32):
        mu.reg_write(getattr(r, 'UC_MIPS_REG_' + str(i)), saved_low[i])
    saved_acc = [rng.getrandbits(64) for _ in range(4)]
    mu.reg_write(r.UC_MIPS_REG_HI, saved_acc[0])
    mu.reg_write(r.UC_MIPS_REG_LO, saved_acc[1])
    banks = saved_acc[2:]
    pending, entered, poisoned = None, False, False

    def hook(uc, pc, size, unused):
        nonlocal pending, entered
        if pc == entry:
            entered = True
        if pc in special:
            pending = ('special', pc)
            uc.emu_stop()
        elif pc == callee and not poisoned:
            pending = ('poison', pc)
            uc.emu_stop()
        elif pc == CONT and entered:
            pending = ('done', pc)
            uc.emu_stop()
    mu.hook_add(u.UC_HOOK_CODE, hook)
    pc = HOOK
    for _ in range(100):
        pending = None
        mu.emu_start(pc, 0x1f0000, count=20000)
        assert pending is not None, ('unexpected exit', hex(mu.reg_read(r.UC_MIPS_REG_PC)))
        kind, pc = pending
        if kind == 'done':
            break
        if kind == 'poison':
            poisoned = True
            for i in range(1, 32):
                upper[i] = rng.getrandbits(64)
                if i not in (29, 31):
                    mu.reg_write(getattr(r, 'UC_MIPS_REG_' + str(i)), 0x50000000 + i)
            mu.reg_write(r.UC_MIPS_REG_HI, rng.getrandbits(64))
            mu.reg_write(r.UC_MIPS_REG_LO, rng.getrandbits(64))
            banks[:] = [rng.getrandbits(64), rng.getrandbits(64)]
            continue
        word = special[pc]
        op, rs, rt, rd, fn = word >> 26, (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31, word & 63
        if op in (0x1e, 0x1f):
            imm = (word & 0x7fff) - (word & 0x8000)
            address = (mu.reg_read(getattr(r, 'UC_MIPS_REG_' + str(rs))) + imm) & 0xffffffff
            assert address & 15 == 0 and saved_low[29] - 0x800 <= address <= saved_low[29] - 16
            reg = getattr(r, 'UC_MIPS_REG_' + str(rt))
            if op == 0x1f:
                mu.mem_write(address, struct.pack('<QQ', mu.reg_read(reg) & MASK, upper[rt]))
            else:
                low, upper[rt] = struct.unpack('<QQ', mu.mem_read(address, 16))
                mu.reg_write(reg, low)
        elif fn in (0x10, 0x12):
            mu.reg_write(getattr(r, 'UC_MIPS_REG_' + str(rd)), banks[fn == 0x12])
        elif fn in (0x11, 0x13):
            banks[fn == 0x13] = mu.reg_read(getattr(r, 'UC_MIPS_REG_' + str(rs))) & MASK
        else:
            raise AssertionError('unmodeled owned instruction')
        pc += 4
    else:
        raise AssertionError('bridge adapter budget exhausted')
    assert poisoned and mu.reg_read(r.UC_MIPS_REG_PC) == CONT
    for i in range(1, 32):
        want = expected_display if i == 5 else 0x12000000 if i in (2, 3) else saved_low[i]
        assert mu.reg_read(getattr(r, 'UC_MIPS_REG_' + str(i))) == want, ('GPR', i)
        if i != 5:  # a1 upper lane is dead before the next Sony call uses a1
            assert upper[i] == saved_high[i], ('opaque upper lane', i)
    assert [mu.reg_read(r.UC_MIPS_REG_HI), mu.reg_read(r.UC_MIPS_REG_LO), *banks] == saved_acc
    # Preserve image/config and stack guards; the original-address adapter's
    # complete final RAM audit is performed by test_pops_progressive.py.
    assert bytes(mu.mem_read(BASE, isz)) == private + bytes(isz - len(private))
    assert bytes(mu.mem_read(saved_low[29] - 0x1000, 0x800)) == b'\xa5' * 0x800
    assert bytes(mu.mem_read(saved_low[29], 16)) == b'\xa5' * 16
    return mu


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--original', type=Path, default=os.environ.get('POPSTARTER_TEST_ELF'))
    args = parser.parse_args()
    if not args.original:
        parser.error('requires external --original or POPSTARTER_TEST_ELF')
    original = OriginalDisplay(Path(args.original).read_bytes())
    image = args.image.read_bytes()
    inputs = cases()
    for i, state in enumerate(inputs):
        expected = original.progressive(record(state))
        mu = execute(image, state, expected['display'], i)
        for name, (address, width) in FIELDS.items():
            assert int.from_bytes(mu.mem_read(address, width), 'little') == expected[name], (i, name)
    # Demonstrate that the lane/register oracle rejects a damaged restoration.
    _, _, _, slots, _ = inspect(image)
    gp_load = next(pc for pc, word in slots.items() if word >> 26 == 0x1e and (word >> 16) & 31 == 28)
    damaged = bytearray(image)
    struct.pack_into('<I', damaged, gp_load - BASE, slots[gp_load] - 16)
    try:
        execute(bytes(damaged), inputs[0], original.progressive(record(inputs[0]))['display'], 0)
    except AssertionError:
        pass
    else:
        raise AssertionError('damaged GP restoration escaped the oracle')
    print(f'Built progressive bridge PASS: {len(inputs)} cases; GPR/opaque-lane/HI-LO/SP restoration; damaged-GP negative check')


if __name__ == '__main__':
    main()
