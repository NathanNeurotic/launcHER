#!/usr/bin/env python3
"""Compare live POPS images (EE RAM from 0x200000) with each other / with the pristine POPS.ELF text.
usage: diff_text.py <dumpA> <dumpB|POPS.ELF> [limit]"""
import struct, sys
BASE = 0x200000
TEXT = 0x49808
def load(path):
    d = open(path, "rb").read()
    if d[:4] == b"\x7fELF":
        return d[0x1000:0x1000 + TEXT]   # .text segment file offset 0x1000 -> 0x200000
    return d[:TEXT]
a, b = load(sys.argv[1]), load(sys.argv[2])
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 60
diffs = [(BASE + i, struct.unpack_from("<I", a, i)[0], struct.unpack_from("<I", b, i)[0])
         for i in range(0, TEXT - 3, 4) if a[i:i+4] != b[i:i+4]]
print("differing words in .text:", len(diffs))
def lwswr(x, y):  # the opcode pass: lw->lwr, sw->swr (upper half +0x0c00)
    return (x ^ y) == 0x14000000 and (y >> 26) in (0x23, 0x2b) and (x >> 26) in (0x26, 0x2e)
other = [d for d in diffs if not (lwswr(d[1], d[2]) or lwswr(d[2], d[1]))]
print("of which not a plain lw/sw <-> lwr/swr change:", len(other))
for addr, x, y in other[:limit]:
    print("  %08x: A=%08x B=%08x" % (addr, x, y))
