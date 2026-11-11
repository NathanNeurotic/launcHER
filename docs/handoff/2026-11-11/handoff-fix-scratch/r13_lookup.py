#!/usr/bin/env python3
"""What does POPStarter r13's built-in game lookup do for a given VCD?

  python r13_lookup.py WORKTREE VCD

r13 reads a 144-byte fingerprint (VCD offsets 0x109340+0x30, 0x109640+0x20,
0x10ca70+0x40) and compares it with the 607 fingerprints stored in its MAIN
image (docs/POPSTARTER_BUILTIN_DB.md).  This reads those fingerprints from the
external POPSTARTER_TEST_ELF with the repository's generator and compares.
Also scans the decoded MAIN image for a few title strings, to see whether r13
carries any title text at all.  Static comparison of data, not an execution.
"""
import sys

root, vcd = sys.argv[1], sys.argv[2]
sys.path.insert(0, root + "/tools")
import gen_pops_builtin_db as G  # noqa: E402

img = G.image()
sigs = G.signatures(img)
data = open(vcd, "rb")
fp = b""
for off, n in ((0x109340, 0x30), (0x109640, 0x20), (0x10CA70, 0x40)):
    data.seek(off)
    fp += data.read(n)
print("fingerprint bytes read:", len(fp), "stored fingerprints:", len(sigs))
hits = [i for i, s in sigs if s == fp]
print("ids whose stored fingerprint equals the VCD's:", hits)
blob = bytes(img)
for needle in (b"Test Drive", b"TEST DRIVE", b"Tekken", b"TEKKEN", b"SLES-00948", b"SLES_009.48", b"TONYHAX"):
    print("%-14s in r13 MAIN image: %d occurrence(s)" % (needle.decode(), blob.count(needle)))
