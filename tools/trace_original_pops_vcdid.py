#!/usr/bin/env python3
"""Run POPStarter r13's built-in per-game routine (FUN_008e00d0) for one id.

Needs the external POPStarter MAIN (POPSTARTER_TEST_ELF) and Unicorn. No
original bytes are included or written. Helpers are stubbed and recorded:
memcpy, poke8, poke32, compatibility mode (FUN_008dc2c4), memory card off
(FUN_008dc12c) and the exception hook (FUN_008d6da4); prints are skipped.
Direct stores outside the stack are recorded too. See
docs/POPSTARTER_BUILTIN_DB.md. Bounded execution of one routine, not a POPS
boot or a console test.

    python tools/trace_original_pops_vcdid.py MODE ID [ID...]
"""
import sys, os, struct, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_original_pops_io import decode_main

from unicorn import *
from unicorn.mips_const import *

BASE = 0x870000
GP = 0x9B68F0
FN = 0x8E00D0
STACK = 0x1F00000
HELPERS = {0x915708: 'print', 0x918808: 'memcpy', 0x914930: 'poke8', 0x914964: 'poke32',
           0x8dc2c4: 'compat', 0x8dc12c: 'f8dc12c', 0x8d6da4: 'f8d6da4'}
img = decode_main(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())

def run(n, mode, globs=None):
    uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
    try:
        uc.ctl_set_cpu_model(UC_CPU_MIPS64_5KF)
    except Exception:
        pass
    uc.mem_map(0, 0x02000000)
    uc.mem_write(BASE, bytes(img))
    for off, val in (globs or {}).items():
        uc.mem_write(GP + off, struct.pack('<I', val))
    events = []
    END = 0x00F00000
    def code(u, addr, size, _):
        if addr in HELPERS:
            a = [u.reg_read(r) & 0xffffffff for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3)]
            name = HELPERS[addr]
            if name == 'memcpy':
                data = bytes(u.mem_read(a[1], a[2])) if a[2] < 0x100000 else b''
                events.append([name, a[0], a[1], a[2], data.hex()])
            elif name != 'print':
                events.append([name] + a[:2])
            u.reg_write(UC_MIPS_REG_V0, 0)
            u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
        elif not (FN <= addr < 0x8ff0e4) and addr != END:
            raise SystemExit('left fn at %#x' % addr)
    def mw(u, access, address, size, value, _):
        if not (STACK - 0x10000 <= address < STACK + 0x100):
            pc = u.reg_read(UC_MIPS_REG_PC)
            events.append(['store', address, size, value & ((1 << (8 * size)) - 1)])
    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_WRITE, mw)
    uc.reg_write(UC_MIPS_REG_GP, GP)
    uc.reg_write(UC_MIPS_REG_SP, STACK)
    uc.reg_write(UC_MIPS_REG_A0, n)
    uc.reg_write(UC_MIPS_REG_A1, mode)
    uc.reg_write(UC_MIPS_REG_RA, END)
    uc.emu_start(FN, END, count=5_000_000)
    return events

if __name__ == '__main__':
    for n in map(int, sys.argv[2:]):
        print(n, json.dumps(run(n, int(sys.argv[1]))))
