#!/usr/bin/env python3
"""Dump words of the decoded r13 MAIN image, one per line with a rough decode
of the instructions that matter for the handoff tail.

  python r13_tail.py WORKTREE START END
  python r13_tail.py WORKTREE --gpw OFFSET   (who writes gp+OFFSET: sw/sb/sh with base gp)
"""
import struct
import sys

root = sys.argv[1]
sys.path.insert(0, root + "/tools")
import gen_pops_builtin_db as G  # noqa: E402

BASE = 0x870000
img = bytes(G.image())
n = len(img) // 4
words = struct.unpack("<%dI" % n, img[:n * 4])
REG = "zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra".split()


def dec(w, pc):
    op, rs, rt, rd, imm = w >> 26, (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31, w & 0xFFFF
    simm = imm - 0x10000 if imm & 0x8000 else imm
    if w == 0:
        return "nop"
    if w == 0xC:
        return "syscall"
    if op == 3:
        return "jal 0x%x" % (((pc + 4) & 0xF0000000) | ((w & 0x03FFFFFF) << 2))
    if op == 2:
        return "j 0x%x" % (((pc + 4) & 0xF0000000) | ((w & 0x03FFFFFF) << 2))
    if op == 0xF:
        return "lui %s,0x%x" % (REG[rt], imm)
    if op in (9, 0x19):
        return "addiu %s,%s,%d" % (REG[rt], REG[rs], simm)
    if op == 0xD:
        return "ori %s,%s,0x%x" % (REG[rt], REG[rs], imm)
    if op in (0x23, 0x2B, 0x28, 0x29, 0x20, 0x24, 0x37, 0x3F):
        name = {0x23: "lw", 0x2B: "sw", 0x28: "sb", 0x29: "sh", 0x20: "lb", 0x24: "lbu", 0x37: "ld", 0x3F: "sd"}[op]
        return "%s %s,%d(%s)" % (name, REG[rt], simm, REG[rs])
    if op in (4, 5):
        return "%s %s,%s,0x%x" % ("beq" if op == 4 else "bne", REG[rs], REG[rt], pc + 4 + simm * 4)
    if op == 0 and (w & 63) == 0x2D:
        return "daddu %s,%s,%s" % (REG[rd], REG[rs], REG[rt])
    if op == 0 and (w & 63) == 8:
        return "jr %s" % REG[rs]
    return ""


if sys.argv[2] == "--gpw":
    off = int(sys.argv[3], 16)
    for i, w in enumerate(words):
        op, rs, imm = w >> 26, (w >> 21) & 31, w & 0xFFFF
        if rs == 28 and imm == off and op in (0x2B, 0x28, 0x29, 0x3F, 0x23, 0x20, 0x24):
            print("0x%x: %08x %s" % (BASE + i * 4, w, dec(w, BASE + i * 4)))
else:
    lo, hi = int(sys.argv[2], 16), int(sys.argv[3], 16)
    for a in range(lo, hi, 4):
        w = words[(a - BASE) // 4]
        print("0x%x: %08x %s" % (a, w, dec(w, a)))
