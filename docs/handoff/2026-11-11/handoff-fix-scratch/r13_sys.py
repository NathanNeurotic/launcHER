#!/usr/bin/env python3
"""Syscall stubs in the decoded r13 MAIN image and the callers of some.

  python r13_sys.py WORKTREE [NUM...]
Lists every `addiu $v1,$zero,N ; syscall` pair (N and address), then for the
given numbers the jal sites that call the stub and the 12 words before each.
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
stubs = {}
for i in range(n - 1):
    w = words[i]
    if (w & 0xFFFF0000) == 0x24030000 and words[i + 1] == 0x0000000C:
        stubs.setdefault(w & 0xFFFF, []).append(BASE + i * 4)
print("image size 0x%x" % len(img))
print("syscall numbers with a stub:", " ".join("%x" % k for k in sorted(stubs)))
print("raw `syscall` words:", sum(1 for w in words if w == 0xC))
for arg in sys.argv[2:]:
    num = int(arg, 16)
    for addr in stubs.get(num, []):
        jal = 0x0C000000 | ((addr >> 2) & 0x03FFFFFF)
        sites = [BASE + i * 4 for i, w in enumerate(words) if w == jal]
        print("syscall 0x%x stub at 0x%x, called from %s" % (num, addr, [hex(s) for s in sites]))
        print("   stub context:", " ".join("%08x" % words[(addr - BASE) // 4 + k] for k in range(-2, 4)))
        for s in sites[:4]:
            i = (s - BASE) // 4
            print("   before 0x%x:" % s, " ".join("%08x" % words[k] for k in range(i - 12, i + 2)))
