#!/usr/bin/env python3
"""Run POPStarter r13's $RESET_WARMBOOT pass over a POPS core (external inputs only).

The command's handler (0x8923a4) only sets gp+0x3894. The work happens later in
the launch function, 0x8795f0..0x879cf4: a scan of POPS's embedded PS1 BIOS ROM
copy (0x24bc20..0x2cbb4c, walked downward) that rewrites selected BIOS call
stubs (`addiu t2,zero,0xA0/B0/C0; jr t2; addiu t1,zero,func`) to A0:A0 and
builds a store of the SystemErrorExit stub's ROM address into the original's
own resident block (0x232cf4..0x232d08).

This runs that block as shipped under Unicorn, with POPSTARTER MAIN and the
POPS core mapped at their own addresses, memcpy modeled, and returns every
store it makes outside its stack frame, in order. Needs POPSTARTER_TEST_ELF
and POPS_TEST_ELF. Nothing here is a console run.
"""
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_original_pops_io import decode_main  # noqa: E402

BASE = 0x870000
GP = 0x9B68F0
START = 0x8795F0
END = 0x879CF4
FLAG = 0x3894
STACK = 0x1F00000
MEMCPY = 0x918808
CORE_BASE = 0x200000


def pops_segments(path):
    data = Path(path).read_bytes()
    phoff, = struct.unpack_from('<I', data, 0x1c)
    phnum, = struct.unpack_from('<H', data, 0x2c)
    out = []
    for i in range(phnum):
        p_type, off, vaddr, _pa, filesz, memsz = struct.unpack_from('<IIIIII', data, phoff + 32 * i)
        if p_type == 1 and filesz:
            out.append((vaddr, data[off:off + filesz]))
    return out


def core_image(path):
    """The POPS core as launcHER stages it: one flat image from 0x200000."""
    segs = [s for s in pops_segments(path) if s[0] >= CORE_BASE and s[0] < 0x01000000]
    end = max(va + len(b) for va, b in segs)
    img = bytearray(end - CORE_BASE)
    for va, b in segs:
        img[va - CORE_BASE:va - CORE_BASE + len(b)] = b
    return img


def run(core, flag=1, count=50_000_000):
    from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn.mips_const import (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_GP,
                                    UC_MIPS_REG_SP, UC_MIPS_REG_FP, UC_MIPS_REG_PC, UC_MIPS_REG_RA,
                                    UC_MIPS_REG_V0)
    main = decode_main(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())
    uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
    try:
        uc.ctl_set_cpu_model(5)  # UC_CPU_MIPS64_5KF, as the other tracers
    except Exception:
        pass
    uc.mem_map(0, 0x02000000)
    uc.mem_write(BASE, bytes(main))
    uc.mem_write(CORE_BASE, bytes(core))
    uc.mem_write(GP + FLAG, struct.pack('<I', flag))
    events = []
    # The block keeps its locals at 0x1c($fp)/0x20($fp): give it a frame.
    fp = STACK - 0x2000

    def code(u, addr, size, _):
        if addr == MEMCPY:
            a0, a1, a2 = (u.reg_read(r) & 0xffffffff for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2))
            data = bytes(u.mem_read(a1, a2))
            u.mem_write(a0, data)
            u.reg_write(UC_MIPS_REG_V0, a0)
            u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
        elif not (START <= addr < END) and not (0x87c244 <= addr < 0x87c330) and addr != END:
            raise SystemExit('left the block at %#x' % addr)

    def mw(u, access, address, size, value, _):
        if STACK - 0x10000 <= address < STACK + 0x100:
            return
        events.append((address, size, value & ((1 << (8 * size)) - 1)))

    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_WRITE, mw)
    uc.reg_write(UC_MIPS_REG_GP, GP)
    uc.reg_write(UC_MIPS_REG_SP, STACK - 0x100)
    uc.reg_write(UC_MIPS_REG_FP, fp)
    uc.reg_write(UC_MIPS_REG_RA, END)
    uc.emu_start(START, END, count=count)
    after = bytearray(uc.mem_read(CORE_BASE, len(core)))
    blob = bytes(uc.mem_read(0x232ce8, 0x28))
    gp_slot = bytes(uc.mem_read(GP + 0x3cb0, 4))
    return events, after, blob, gp_slot


def main():
    core = core_image(os.environ['POPS_TEST_ELF'])
    events, after, blob, gp_slot = run(core)
    print('stores:', len(events))
    for a, s, v in events:
        print('  %#010x %d %#x' % (a, s, v))
    diff = [i for i in range(len(core)) if core[i] != after[i]]
    print('core bytes changed:', len(diff))
    print('gp+0x3cb0:', gp_slot.hex())
    print('blob 0x232ce8:', ' '.join('%08x' % w for w in struct.unpack('<10I', blob)))
    events0, after0, _, _ = run(core, flag=0)
    print('flag 0 stores:', len(events0), 'changed:', sum(1 for i in range(len(core)) if core[i] != after0[i]))


if __name__ == '__main__':
    main()
