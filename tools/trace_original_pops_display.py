#!/usr/bin/env python3
"""Bounded original POPStarter display-command execution (external MAIN only).

Executes original branch/delay-slot/arithmetic instructions with a small,
fail-closed R5900 integer interpreter. Poke and memcpy services are modeled;
this is neither a complete parser nor a PS2/GS/console emulator. Original
bytes stay in memory. Returned records contain only patch/state metadata.
No Capstone or Unicorn dependency is needed.
"""
import argparse
import json
from pathlib import Path
import struct

from trace_original_pops_io import decode_main, MAIN_SHA, UNPACKED_SHA

BASE = 0x870000
WINDOWS = {
    '$SMOOTH': (0x8864f0, 0x8866a8),
    '$LEFTADJ_': (0x890320, 0x890a3c),
    '$XPOS_': (0x898840, 0x89a2d8),
    '$YPOS_': (0x898840, 0x89a2d8),
    '$DWSTRETCH_': (0x89a2e4, 0x89b60c),
    '$DWCROP_': (0x89b618, 0x89c920),
}
LOOP = 0x885a04
MASK64 = (1 << 64) - 1


def signed(value, bits):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


class _Window:
    """Only the integer subset present in the five identified windows."""
    FRAME, INPUT, GP = 0x100000, 0x110000, 0x120000

    def __init__(self, image, lo, hi, command, x_set=False, y_set=False):
        self.image, self.lo, self.hi = image, lo, hi
        self.reg = [0] * 32
        self.reg[30], self.reg[28], self.reg[2] = self.FRAME, self.GP, self.INPUT
        self.memory = {}
        for base, size in ((self.FRAME, 0x200), (self.INPUT, 0x100),
                           (self.GP + 0x34f0, 4), (self.GP + 0x3974, 4)):
            self.memory.update((base + i, 0) for i in range(size))
        data = command.encode('ascii') + b'\0'
        if len(data) > 0x100:
            raise ValueError('command too long')
        self.store_bytes(self.INPUT, data)
        self.store(self.FRAME + 0x98, self.INPUT, 4)
        self.store(self.GP + 0x34f0, int(x_set), 4)
        self.store(self.GP + 0x3974, int(y_set), 4)
        self.writes = []

    def load_bytes(self, address, width):
        try:
            return bytes(self.memory[address + i] for i in range(width))
        except KeyError as exc:
            raise ValueError(f'out-of-window read {address:#x}+{width}') from exc

    def load(self, address, width):
        return int.from_bytes(self.load_bytes(address, width), 'little')

    def store_bytes(self, address, data):
        if any(address + i not in self.memory for i in range(len(data))):
            raise ValueError(f'out-of-window write {address:#x}+{len(data)}')
        self.memory.update((address + i, v) for i, v in enumerate(data))

    def store(self, address, value, width):
        self.store_bytes(address, (value & ((1 << (width * 8)) - 1)).to_bytes(width, 'little'))

    def put(self, reg, value):
        if reg:
            self.reg[reg] = value & MASK64

    def instruction(self, pc, delay=False):
        if not self.lo <= pc < self.hi or pc & 3:
            raise ValueError(f'PC outside command window: {pc:#x}')
        word, = struct.unpack_from('<I', self.image, pc - BASE)
        op, rs, rt, rd, shift, fn = word >> 26, (word >> 21) & 31, (word >> 16) & 31, \
            (word >> 11) & 31, (word >> 6) & 31, word & 63
        imm = signed(word, 16)
        a, b = self.reg[rs], self.reg[rt]
        transfer = None
        if op == 0:
            if fn == 0 and word == 0:
                pass
            elif fn == 0x21:  # addu (32-bit sign-extended result)
                self.put(rd, signed(a + b, 32))
            elif fn == 0x23:
                self.put(rd, signed(a - b, 32))
            elif fn == 0x2d:  # daddu / move
                self.put(rd, a + b)
            elif fn == 0x25:
                self.put(rd, a | b)
            elif fn == 0x18:  # R5900 MULT rd,rs,rt, unlike standard MIPS
                self.put(rd, signed(signed(a, 32) * signed(b, 32), 32))
            elif fn == 0x2a:
                self.put(rd, int(signed(a, 64) < signed(b, 64)))
            elif fn == 0x38:
                self.put(rd, b << shift)
            else:
                raise ValueError(f'unsupported SPECIAL {word:#x} at {pc:#x}')
        elif op == 0x09:
            self.put(rt, signed(a + imm, 32))
        elif op == 0x0d:
            self.put(rt, a | (word & 0xffff))
        elif op == 0x0f:
            self.put(rt, signed((word & 0xffff) << 16, 32))
        elif op == 0x0a:
            self.put(rt, int(signed(a, 64) < imm))
        elif op == 0x0b:
            self.put(rt, int(a < (imm & MASK64)))
        elif op in (0x23, 0x24):
            width = 4 if op == 0x23 else 1
            value = self.load((a + imm) & 0xffffffff, width)
            self.put(rt, signed(value, 32) if width == 4 else value)
        elif op in (0x28, 0x2b):
            self.store((a + imm) & 0xffffffff, b, 1 if op == 0x28 else 4)
        elif op in (4, 5, 6):
            taken = a == b if op == 4 else a != b if op == 5 else signed(a, 64) <= 0
            transfer = ('branch', pc + 4 + (imm << 2) if taken else pc + 8)
        elif op == 3:
            self.put(31, pc + 8)
            transfer = ('call', ((pc + 4) & 0xf0000000) | ((word & 0x3ffffff) << 2))
        else:
            raise ValueError(f'unsupported opcode {word:#x} at {pc:#x}')
        if delay and transfer is not None:
            raise ValueError('branch in delay slot')
        return transfer

    def service(self, target):
        a0, a1, a2 = self.reg[4:7]
        if target in (0x8d6c04, 0x8d6c34):
            width = 4 if target == 0x8d6c04 else 8
            address, value = a1, a0 & ((1 << (width * 8)) - 1)
        elif target == 0x918808:
            if a2 not in (1, 2):
                raise ValueError(f'unexpected copy width {a2}')
            address, value, width = a0, self.load(a1, a2), a2
            self.put(2, a0)  # memcpy returns its destination
        else:
            raise ValueError(f'unmodeled call {target:#x}')
        if not 0x200000 <= address <= 0x502e60 - width:
            raise ValueError(f'patch outside core {address:#x}')
        self.writes.append([address, value, width])

    def run(self):
        pc = self.lo
        for _ in range(20000):
            if pc in (LOOP, self.hi):
                return {'writes': self.writes,
                        'x_set': bool(self.load(self.GP + 0x34f0, 4)),
                        'y_set': bool(self.load(self.GP + 0x3974, 4))}
            transfer = self.instruction(pc)
            if transfer is None:
                pc += 4
                continue
            self.instruction(pc + 4, delay=True)
            kind, target = transfer
            if kind == 'call':
                self.service(target)
                pc += 8
            else:
                pc = target
        raise ValueError('instruction budget exceeded')


class OriginalDisplay:
    def __init__(self, packed):
        self.image = decode_main(packed)  # full packed and unpacked hash/size pins

    def run(self, command, x_set=False, y_set=False):
        prefix = next((p for p in WINDOWS if command.startswith(p)), None)
        if prefix is None:
            raise ValueError('command outside supported windows')
        return _Window(self.image, *WINDOWS[prefix], command, x_set, y_set).run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('popstarter', type=Path)
    parser.add_argument('commands', nargs='+')
    args = parser.parse_args()
    original = OriginalDisplay(args.popstarter.read_bytes())
    print(json.dumps({'packed_sha256': MAIN_SHA, 'image_sha256': UNPACKED_SHA,
                      'results': {c: original.run(c) for c in args.commands}}, indent=2))


if __name__ == '__main__':
    main()
