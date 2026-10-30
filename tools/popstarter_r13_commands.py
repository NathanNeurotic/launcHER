#!/usr/bin/env python3
"""List POPStarter r13's CHEATS.TXT commands and the POPS writes each makes.

Research aid, not run by CI. It reads the pinned POPSLoader MAIN profile
(POPSLDR/PROFILES/MAIN/POPSTARTER.ELF) that you supply, unpacks it with the
decoder in trace_original_pops_io.py and prints metadata only: command names,
handler addresses and (address, width, value) writes. No original bytes are
written anywhere.

The original compares command names byte by byte (lbu / li / bne chains), so
they are not plain strings. Its writes go through poke helpers taking
a0 = value and a1 = address; tracking constant a0/a1 before each jal gives
every static write. Values the scan cannot resolve print as '?'.

Writes into 0x232790..0x232ec8 and 0x238a90..0x2397f0 land in code that the
original copies from its own image into POPS at launch; 0x143xxxx is
POPStarter's resident area. Neither exists under launcHER.

Requires capstone (pip install capstone).

    python tools/popstarter_r13_commands.py POPSTARTER.ELF [--json out.json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_original_pops_io import decode_main  # noqa: E402

try:
    from capstone import CS_ARCH_MIPS, CS_MODE_LITTLE_ENDIAN, CS_MODE_MIPS64, Cs
    from capstone.mips import MIPS_OP_MEM, MIPS_OP_REG, MIPS_REG_A0, MIPS_REG_A1, \
        MIPS_REG_A2, MIPS_REG_A3, MIPS_REG_GP, MIPS_REG_V0, MIPS_REG_V1, MIPS_REG_ZERO
except ImportError:
    sys.exit("capstone is required: pip install capstone")

BASE = 0x870000
PARSER = (0x883000, 0x8a0000)
POKE = {0x8dc8e4: 8, 0x8dc918: 16, 0x8dc94c: 32, 0x8dc97c: 64,
        0x87c298: 8, 0x87c2cc: 16, 0x87c300: 32, 0x87c330: 64,
        0x8d6b9c: 8, 0x8d6bd0: 16, 0x8d6c04: 32, 0x8d6c34: 64, 0x8d6c64: 128}
MEMCPY = 0x918808
ARGS = (MIPS_REG_V0, MIPS_REG_V1, MIPS_REG_A0, MIPS_REG_A1, MIPS_REG_A2, MIPS_REG_A3)


def disassembler(detail):
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS64 + CS_MODE_LITTLE_ENDIAN)
    md.skipdata = True
    md.detail = detail
    return md


def command_chains(image):
    """(address, text) for each byte-compare chain in the parser."""
    ins = list(disassembler(False).disasm(image[PARSER[0] - BASE:PARSER[1] - BASE], PARSER[0]))
    chains, cur, start, last = [], [], None, 0
    for a, b, c in zip(ins, ins[1:], ins[2:]):
        if a.mnemonic == 'lbu' and b.mnemonic == 'addiu' and '$zero' in b.op_str \
                and c.mnemonic in ('bne', 'beq'):
            value = int(b.op_str.split(',')[2], 0) & 0xff
            if a.address - last > 40 and cur:
                chains.append((start, ''.join(cur)))
                cur = []
            if not cur:
                start = a.address
            cur.append(chr(value) if 32 < value < 127 else '')
            last = a.address
    if cur:
        chains.append((start, ''.join(cur)))
    return [(a, t) for a, t in chains if re.match(r'\$[A-Z0-9?][A-Za-z0-9_]{2,}', t)]


def handler_events(image, start, end):
    regs, pending, events = {}, None, []
    for i in disassembler(True).disasm(image[start - BASE:end - BASE], start):
        m = i.mnemonic
        try:
            o = i.operands
        except Exception:
            o = []

        def put(reg, value):
            if value is None:
                regs.pop(reg, None)
            else:
                regs[reg] = value & 0xffffffff
        try:
            if m == 'lui':
                put(o[0].reg, o[1].imm << 16)
            elif m == 'ori':
                src = 0 if o[1].reg == MIPS_REG_ZERO else regs.get(o[1].reg)
                put(o[0].reg, None if src is None else src | (o[2].imm & 0xffff))
            elif m in ('addiu', 'daddiu'):
                src = 0 if o[1].reg == MIPS_REG_ZERO else regs.get(o[1].reg)
                put(o[0].reg, None if src is None else src + o[2].imm)
            elif m == 'move':
                put(o[0].reg, 0 if o[1].reg == MIPS_REG_ZERO else regs.get(o[1].reg))
            elif m in ('sw', 'sb', 'sh') and o[1].type == MIPS_OP_MEM \
                    and o[1].mem.base == MIPS_REG_GP:
                value = 0 if o[0].reg == MIPS_REG_ZERO else regs.get(o[0].reg)
                events.append({'kind': 'flag', 'gp': o[1].mem.disp, 'value': value})
            elif m == 'jal':
                pending = o[0].imm
                continue
            elif o and o[0].type == MIPS_OP_REG and not m.startswith(('s', 'b', 'j')):
                put(o[0].reg, None)
        except Exception:
            pass
        if pending is not None:
            if pending in POKE:
                events.append({'kind': 'write', 'width': POKE[pending],
                               'address': regs.get(MIPS_REG_A1), 'value': regs.get(MIPS_REG_A0)})
            elif pending == MEMCPY:
                events.append({'kind': 'copy', 'dest': regs.get(MIPS_REG_A0),
                               'source': regs.get(MIPS_REG_A1), 'size': regs.get(MIPS_REG_A2)})
            else:
                events.append({'kind': 'call', 'target': pending})
            for reg in ARGS:
                regs.pop(reg, None)
            pending = None
    unique = []
    for event in events:
        if event not in unique:
            unique.append(event)
    return unique


def fmt(value):
    return '?' if value is None else hex(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('popstarter', type=Path)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    image = decode_main(args.popstarter.read_bytes())
    chains = command_chains(image)
    commands = []
    for index, (address, text) in enumerate(chains):
        end = chains[index + 1][0] if index + 1 < len(chains) else address + 0x1000
        commands.append({'command': text, 'handler': address,
                         'events': handler_events(image, address, end)})
    for item in commands:
        parts = []
        for e in item['events']:
            if e['kind'] == 'write':
                parts.append('w%d[%s]=%s' % (e['width'], fmt(e['address']), fmt(e['value'])))
            elif e['kind'] == 'flag':
                parts.append('gp[%#x]=%s' % (e['gp'], fmt(e['value'])))
            elif e['kind'] == 'copy':
                parts.append('copy(%s<-%s,%s)' % (fmt(e['dest']), fmt(e['source']), fmt(e['size'])))
            else:
                parts.append('call %#x' % e['target'])
        print('%#x %-26s %s' % (item['handler'], item['command'], ' '.join(parts)))
    if args.json:
        args.json.write_text(json.dumps(commands, indent=1) + '\n')


if __name__ == '__main__':
    main()
