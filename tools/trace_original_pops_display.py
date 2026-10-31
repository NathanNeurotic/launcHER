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
MANUAL_WINDOWS = {
    '$DX_': (0x8866a8, 0x888050), '$DY_': (0x888050, 0x8899f8),
    '$MAGH_': (0x8899f8, 0x88b3e0), '$MAGV_': (0x88b3e0, 0x88cdc8),
    '$DW_': (0x88cdc8, 0x88e770), '$DH_': (0x88e770, 0x890118),
}
MANUAL_GLOBALS = (0x4fb4, 0x4fb8, 0x4fb0, 0x4fc8, 0x4fc4, 0x4fc0)
MANUAL_OPTIONS = {'$HDTVFIX': (0x89d354, 0x89d53c),
                  '$NOHDTVFIX': (0x89d53c, 0x89d764),
                  '$480p': (0x890118, 0x890308)}
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
            elif fn == 0:
                self.put(rd, signed(b << shift, 32))
            elif fn == 2:
                self.put(rd, signed((b & 0xffffffff) >> shift, 32))
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
            elif fn == 0x3c:
                self.put(rd, b << (shift + 32))
            elif fn == 0x3e:
                self.put(rd, b >> (shift + 32))
            elif fn == 0x3f:
                self.put(rd, signed(b, 64) >> (shift + 32))
            elif fn == 0x3a:
                self.put(rd, b >> shift)
            else:
                raise ValueError(f'unsupported SPECIAL {word:#x} at {pc:#x}')
        elif op == 0x09:
            self.put(rt, signed(a + imm, 32))
        elif op == 0x0d:
            self.put(rt, a | (word & 0xffff))
        elif op == 0x0c:
            self.put(rt, a & (word & 0xffff))
        elif op == 0x0f:
            self.put(rt, signed((word & 0xffff) << 16, 32))
        elif op == 0x0a:
            self.put(rt, int(signed(a, 64) < imm))
        elif op == 0x0b:
            self.put(rt, int(a < (imm & MASK64)))
        elif op in (0x23, 0x24, 0x37, 0x1e):
            width = {0x23: 4, 0x24: 1, 0x37: 8, 0x1e: 16}[op]
            if op == 0x1e and (a + imm) & 15:
                raise ValueError('unaligned LQ outside modeled progressive entry')
            value = self.load((a + imm) & 0xffffffff, width)
            self.put(rt, signed(value, 32) if width == 4 else value)
        elif op in (0x28, 0x2b, 0x3f):
            self.store((a + imm) & 0xffffffff, b, {0x28: 1, 0x2b: 4, 0x3f: 8}[op])
        elif op in (4, 5, 6, 0x14):
            taken = a == b if op in (4, 0x14) else a != b if op == 5 else signed(a, 64) <= 0
            if op == 0x14 and not taken:
                transfer = ('annul', pc + 8)
            else:
                transfer = ('branch', pc + 4 + (imm << 2) if taken else pc + 8)
        elif op == 2:
            transfer = ('branch', ((pc + 4) & 0xf0000000) | ((word & 0x3ffffff) << 2))
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
        if target in (0x8d6b9c, 0x8d6c04, 0x8d6c34):
            width = {0x8d6b9c: 1, 0x8d6c04: 4, 0x8d6c34: 8}[target]
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
            if pc in (LOOP, self.hi, *getattr(self, 'stops', ())):
                return {'writes': self.writes,
                        'x_set': bool(self.load(self.GP + 0x34f0, 4)),
                        'y_set': bool(self.load(self.GP + 0x3974, 4))}
            transfer = self.instruction(pc)
            if transfer is None:
                pc += 4
                continue
            kind, target = transfer
            if kind != 'annul':
                self.instruction(pc + 4, delay=True)
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

    def manual(self, commands):
        """One file's six first-valid values and end-of-file display writes.

        Executes identified command handlers and their final all-six check;
        tokenization/file I/O and poke services remain modeled.
        """
        m = _Window(self.image, 0x89e75c, 0x89e884, '')
        m.memory.update((m.GP + i, 0) for i in range(0x3400, 0x4fcc))
        for command in commands:
            windows = MANUAL_WINDOWS | MANUAL_OPTIONS
            prefix = next((p for p in windows if command.startswith(p)), None)
            if prefix is None:
                raise ValueError('command outside manual display windows')
            m.store_bytes(m.INPUT, bytes(0x100))
            m.store_bytes(m.INPUT, command.encode('ascii') + b'\0')
            m.store(m.FRAME + 0x94, 0, 4)
            m.lo, m.hi = windows[prefix]
            m.run()
        values = [m.load(m.GP + off, 4) for off in MANUAL_GLOBALS]
        flags = [m.load(m.FRAME + 0xfc + 4 * i, 4) for i in range(6)]
        m.lo, m.hi = 0x89e75c, 0x89e884
        m.run()
        return {'values': values, 'flags': flags, 'writes': m.writes}

    def progressive(self, state):
        """Original 0x2394f0 entry at its source location, 64-bit GPR view.

        The original loader copies the block from 0x983890 to 0x238a90.
        Relative branches work at either location; the final J is absolute.
        LQ's low 64 bits are observed; no upper-lane equivalence is claimed.
        """
        class ProgressiveWindow(_Window):
            GP = 0x50a670  # pinned Sony ELF REGINFO
        m = ProgressiveWindow(self.image, 0x9842f0, 0x984558, '')
        m.stops = (0x21a098,)
        fields = {
            'fallback_display': (0x70003290, 8),
            'source_32a8': (0x700032a8, 4), 'source_32ac': (0x700032ac, 4),
            'source_32b0': (0x700032b0, 4), 'source_32bc': (0x700032bc, 4),
            'blocked': (0x85a9ac, 4), 'region': (0x127ff52, 1),
            'scratch': (0x502680, 8), 'magh': (0x502688, 4), 'dx': (0x50268c, 4),
            'dy': (0x502690, 4), 'dh': (0x502694, 4), 'dw': (0x502698, 4),
            'magv': (0x50269c, 4), 'timing_502770': (0x502770, 4),
            'timing_23ac08': (0x23ac08, 4), 'mode_21af94': (0x21af94, 1),
            'mode_70003300': (0x70003300, 1),
        }
        m.memory.update((a, 0xa5) for a in range(0x70003290, 0x70003310))
        for name, (address, width) in fields.items():
            m.memory.update((address + i, 0) for i in range(width))
            m.store(address, state[name], width)
        before = dict(m.memory)
        m.run()
        result = dict(state)
        result.update((name, m.load(address, width)) for name, (address, width) in fields.items())
        result['display'] = m.reg[5]
        outputs = ('scratch', 'magh', 'dx', 'dy', 'dh', 'dw', 'magv',
                   'timing_502770', 'timing_23ac08', 'mode_21af94', 'mode_70003300')
        allowed = {fields[name][0] + i for name in outputs for i in range(fields[name][1])}
        if any(before[a] != value and a not in allowed for a, value in m.memory.items()):
            raise ValueError('unexpected progressive memory change')
        return result

    def region(self, licence, force_pal=False, auto_disabled=False, auto_selector=True):
        """Original region control flow; PAL helper/pokes modeled explicitly.

        User BIOS/OSD and preserve-standard flags are zero (launcHER has no
        implementation of those inputs). PATCH PAL/disable-auto clears the
        selector as well as setting auto_disabled before this window runs.
        """
        if len(licence) != 4:
            raise ValueError('licence must contain four ASCII bytes')
        machine = _RegionWindow(self.image, 0x879034, 0x8795f0, '')
        for offset in (0x38a0, 0x3864, 0x4fa0, 0x3cb0, 0x3b98, 0x38a4, 0x344c, 0x3430):
            machine.memory.update((machine.GP + offset + i, 0) for i in range(4))
        machine.store(machine.GP + 0x38a0, int(force_pal), 4)
        machine.store(machine.GP + 0x3864, int(auto_disabled), 4)
        machine.store(machine.GP + 0x4fa0, int(auto_selector), 4)
        machine.store_bytes(machine.GP + 0x3cb0, licence.encode('ascii'))
        return machine.run()['writes']


class _RegionWindow(_Window):
    def service(self, target):
        if target == 0x8dc218:
            # FUN_008dc218, with preserve-standard=0 and logging modeled.
            self.writes.extend([[0x21af94, 3, 1], [0x502770, 0xa6300, 4],
                                [0x23b018, 0x6b, 1], [0x23b01c, 0x2cb, 2]])
        elif target in (0x87c298, 0x87c300):
            width = 1 if target == 0x87c298 else 4
            value, address = self.reg[4], self.reg[5]
            if not 0x200000 <= address <= 0x502e60 - width:
                raise ValueError('region poke outside core')
            self.writes.append([address, value & ((1 << (width * 8)) - 1), width])
        else:
            raise ValueError(f'unmodeled region service {target:#x}')


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
