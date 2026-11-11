#!/usr/bin/env python3
"""Compare the trampoline linked into launcher_unc.elf with what
tools/r5900_mini.py assembles from launcher/src/pops_trampoline.S.

  python tramp_cmp.py WORKTREE ELF
"""
import struct
import sys

root, elf = sys.argv[1], sys.argv[2]
sys.path.insert(0, root + "/tools")
import r5900_mini as R  # noqa: E402

words, _ = R.assemble(open(root + "/launcher/src/pops_trampoline.S").read(), 0x84000)
blob = b"".join(w.to_bytes(4, "little") for w in words)
data = open(elf, "rb").read()
hits = []
pos = data.find(blob)
while pos >= 0:
    hits.append(pos)
    pos = data.find(blob, pos + 1)
print("assembled words:", len(words), "bytes:", len(blob))
print("occurrences in ELF file:", len(hits), [hex(h) for h in hits])
# file offset -> vaddr via program headers
e_phoff, = struct.unpack_from("<I", data, 0x1c)
e_phentsize, e_phnum = struct.unpack_from("<HH", data, 0x2a)
for h in hits:
    for i in range(e_phnum):
        p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz = struct.unpack_from("<6I", data, e_phoff + i * e_phentsize)
        if p_type == 1 and p_offset <= h < p_offset + p_filesz:
            print("  at vaddr 0x%08x" % (p_vaddr + h - p_offset))
