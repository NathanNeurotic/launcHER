#!/usr/bin/env python3
"""Run POPStarter r13's own CHEATS.TXT compiler and the code it emits.

Needs the external POPStarter MAIN (POPSTARTER_TEST_ELF) and Python's
Unicorn package. No original bytes are included or written: the MAIN is read
at run time, the same way trace_original_pops_io.py reads it.

compile_cheats(text) runs the original's cheat section, from the point where
the file text is in its buffer (0x883aa8) to the point where it leaves the
section (0x8d4e30, or 0x8d4f6c when nothing was recognised), and returns the
MIPS it wrote at its code cursor (0x01a00000). Prints are switched off (the
original's quiet flag, gp+0x38b0). The few EE-only instructions the section
uses (pcpyld, pcpyh, pcpyud, por, lq, sq, three-operand mult/multu) are
modelled in a code hook, since Unicorn's MIPS64 core lacks them.

run_codes(code, ram) executes that emitted code once, as the original's
resident chain would on one pass, against a PS1 RAM image (mapped at EE
0x01000000) and returns the RAM afterwards. The pass ends at the end of the
code or at the original's exit jump (0x2394b0). k0/k1 start at zero.

This is bounded execution of one routine with synthetic inputs, not a POPS
boot or a console test.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_original_pops_io import decode_main  # noqa: E402

BASE = 0x870000
LIMIT = 0xA00000
GP = 0x9B68F0
BSS = (0x9B9D00, 0x9CCAC0)
FP = 0x1F80000
TEXT = 0x1E00000
CURSOR = 0x01A00000
START = 0x883AA8
STOPS = (0x8D4E30, 0x8D4F6C)
EXIT = 0x2394B0
PS1_RAM = 0x01000000
PS1_RAM_SIZE = 0x200000

_IMAGE = None


def _image():
    global _IMAGE
    if _IMAGE is None:
        _IMAGE = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
    return _IMAGE


def compile_cheats(text: bytes | str):
    """Return (code, recognised_count) for one CHEATS.TXT text."""
    from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
    from unicorn import mips_const as R

    data = text.encode("latin-1") if isinstance(text, str) else bytes(text)
    if len(data) > 0x40000:
        raise ValueError("text too long")
    uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
    try:
        uc.ctl_set_cpu_model(R.UC_CPU_MIPS64_5KF)
    except Exception:
        pass
    uc.mem_map(0, 0x02000000)
    uc.mem_write(BASE, bytes(_image()[: LIMIT - BASE]))
    uc.mem_write(BSS[0], b"\0" * (BSS[1] - BSS[0]))
    uc.mem_write(TEXT, data + b"\0" * (len(data) + 16))

    def put(address, value):
        uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    put(FP + 0x98, TEXT)
    put(FP + 0xE8, len(data))
    put(FP + 0xDC, CURSOR)
    put(FP + 0xE0, CURSOR)
    # Templates the section's prologue stores (0x883288..0x8832f4).
    put(FP + 0xB4, 0x875A0000)  # lh k0,0(k0)
    put(FP + 0xBC, 0x0808E52C)  # j 0x2394b0
    put(FP + 0xE4, 0x002397E8)
    put(GP + 0x38B0, 1)  # quiet
    uc.reg_write(R.UC_MIPS_REG_GP, GP)
    uc.reg_write(R.UC_MIPS_REG_FP, FP)
    uc.reg_write(R.UC_MIPS_REG_SP, FP - 0x100)

    regs = [getattr(R, "UC_MIPS_REG_%d" % i) for i in range(32)]
    upper = [0] * 32
    stopped = []
    failure = []

    def get(r):
        return uc.reg_read(regs[r]) & 0xFFFFFFFFFFFFFFFF

    def sx32(v):
        v &= 0xFFFFFFFF
        return v | 0xFFFFFFFF00000000 if v & 0x80000000 else v

    def hook(u, addr, size, _):
        try:
            if addr in STOPS:
                stopped.append(addr)
                u.emu_stop()
                return
            if not BASE <= addr < LIMIT:
                raise RuntimeError("left the image at %#x" % addr)
            word = struct.unpack("<I", u.mem_read(addr, 4))[0]
            op = word >> 26
            rs, rt, rd = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
            imm = word & 0xFFFF
            simm = imm - 0x10000 if imm & 0x8000 else imm
            fn, sa = word & 63, (word >> 6) & 31
            if op == 0 and fn in (0x18, 0x19) and rd:
                a, b = get(rs) & 0xFFFFFFFF, get(rt) & 0xFFFFFFFF
                if fn == 0x18:
                    a = a - (1 << 32) if a & 0x80000000 else a
                    b = b - (1 << 32) if b & 0x80000000 else b
                prod = (a * b) & 0xFFFFFFFFFFFFFFFF
                u.reg_write(R.UC_MIPS_REG_LO, sx32(prod))
                u.reg_write(R.UC_MIPS_REG_HI, sx32(prod >> 32))
                u.reg_write(regs[rd], sx32(prod))
            elif op == 0x1C and fn == 0x09 and sa == 0x0E:  # pcpyld
                lo, hi = get(rt), get(rs)
                if rd:
                    u.reg_write(regs[rd], lo)
                    upper[rd] = hi
            elif op == 0x1C and fn == 0x29 and sa == 0x1B:  # pcpyh
                def rep(x):
                    h = x & 0xFFFF
                    return h | h << 16 | h << 32 | h << 48
                if rd:
                    u.reg_write(regs[rd], rep(get(rt)))
                    upper[rd] = rep(upper[rt])
            elif op == 0x1C and fn == 0x29 and sa == 0x0E:  # pcpyud
                if rd:
                    u.reg_write(regs[rd], upper[rs])
                    upper[rd] = upper[rt]
            elif op == 0x1C and fn == 0x29 and sa == 0x12:  # por
                if rd:
                    u.reg_write(regs[rd], get(rs) | get(rt))
                    upper[rd] = upper[rs] | upper[rt]
            elif op == 0x1C:
                raise RuntimeError("unmodelled MMI %#010x at %#x" % (word, addr))
            elif op == 0x1F:  # sq
                a = (get(rs) + simm) & 0xFFFFFFF0
                u.mem_write(a, struct.pack("<QQ", get(rt), upper[rt] if rt else 0))
            elif op == 0x1E:  # lq
                a = (get(rs) + simm) & 0xFFFFFFF0
                lo, hi = struct.unpack("<QQ", u.mem_read(a, 16))
                if rt:
                    u.reg_write(regs[rt], lo)
                    upper[rt] = hi
            else:
                return
            u.reg_write(R.UC_MIPS_REG_PC, addr + 4)
        except Exception as exc:  # surface hook errors instead of a bare stop
            failure.append(exc)
            u.emu_stop()

    uc.hook_add(UC_HOOK_CODE, hook)
    uc.emu_start(START, 0xFFFFFFFF, count=50_000_000)
    if failure:
        raise failure[0]
    if not stopped:
        raise RuntimeError("the cheat section did not finish")
    cursor = struct.unpack("<I", uc.mem_read(FP + 0xDC, 4))[0]
    count = struct.unpack("<I", uc.mem_read(FP + 0x9C, 4))[0]
    return bytes(uc.mem_read(CURSOR, cursor - CURSOR)), count


def run_codes(code: bytes, ram: bytes, k0: int = 0, k1: int = 0):
    """Execute emitted code once against a PS1 RAM image; return new RAM."""
    from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
    from unicorn import mips_const as R

    if len(ram) != PS1_RAM_SIZE:
        raise ValueError("PS1 RAM image must be 2 MB")
    uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 + UC_MODE_LITTLE_ENDIAN)
    uc.mem_map(0, 0x02000000)
    uc.mem_write(PS1_RAM, bytes(ram))
    uc.mem_write(CURSOR, bytes(code))
    uc.reg_write(R.UC_MIPS_REG_K0, k0)
    uc.reg_write(R.UC_MIPS_REG_K1, k1)
    end = CURSOR + len(code)

    def hook(u, addr, size, _):
        if addr == EXIT:
            u.emu_stop()

    uc.hook_add(UC_HOOK_CODE, hook)
    if code:
        uc.emu_start(CURSOR, end, count=1_000_000)
    return bytes(uc.mem_read(PS1_RAM, PS1_RAM_SIZE))


def main(argv):
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 + CS_MODE_LITTLE_ENDIAN)
    for text in argv:
        text = text.replace("\\n", "\n").replace("\\r", "\r")
        code, count = compile_cheats(text)
        print("== %r: %d recognised, %d bytes" % (text, count, len(code)))
        for insn in md.disasm(code, CURSOR):
            print("   %#x %s %s" % (insn.address, insn.mnemonic, insn.op_str))


if __name__ == "__main__":
    main(sys.argv[1:])
