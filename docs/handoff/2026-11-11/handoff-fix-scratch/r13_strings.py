#!/usr/bin/env python3
"""Show where a string sits in the decoded r13 MAIN image and who refers to it.

  python r13_strings.py WORKTREE NEEDLE [NEEDLE...]
For each occurrence: address, the whole C string, and the code addresses that
build its address with lui/addiu (v0..t9 pairs within 8 instructions).
"""
import struct
import sys

root = sys.argv[1]
sys.path.insert(0, root + "/tools")
import gen_pops_builtin_db as G  # noqa: E402

BASE = 0x870000
img = bytes(G.image())
words = struct.unpack("<%dI" % (len(img) // 4), img[:len(img) // 4 * 4])


def refs(addr):
    out = []
    hi_want = ((addr + 0x8000) >> 16) & 0xFFFF
    lo_want = addr & 0xFFFF
    for i, w in enumerate(words):
        if (w >> 26) == 0x0F and (w & 0xFFFF) == hi_want:
            rt = (w >> 16) & 31
            for j in range(i + 1, min(i + 9, len(words))):
                v = words[j]
                if (v >> 26) == 0x09 and ((v >> 21) & 31) == rt and (v & 0xFFFF) == lo_want:
                    out.append(BASE + j * 4)
                    break
    return out


for needle in sys.argv[2:]:
    n = needle.encode()
    pos = img.find(n)
    while pos >= 0:
        start = img.rfind(b"\0", 0, pos) + 1
        end = img.find(b"\0", pos)
        s = img[start:end]
        print("%s at 0x%x: string at 0x%x %r refs %s" % (needle, BASE + pos, BASE + start, s[:70],
                                                        [hex(r) for r in refs(BASE + start)][:6]))
        pos = img.find(n, pos + 1)
