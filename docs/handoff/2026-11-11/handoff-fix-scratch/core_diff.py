#!/usr/bin/env python3
"""Compare the live POPS image of a run with the staged core of the same run.

  python core_diff.py RUN_DIR [--list N]

RUN_DIR holds ee_00200000_302e60.bin (live, from 0x200000) and
ee_01000000_302e60.bin (the staging area the trampoline copied from, read at
the same moment).  Reports, for .text (0x200000..0x249808) and for the whole
core image, how many 32-bit words differ, and lists the differing .text words.
Also checks the 0x2a0 bytes below the end of ps2sdk's helper stack and the SIF
receive buffer given with --watch LO:HI (hex, repeatable).
"""
import struct
import sys

TEXT = 0x49808
BASE = 0x200000


def words(buf):
    n = len(buf) // 4
    return struct.unpack("<%dI" % n, buf[:n * 4])


def main():
    run = sys.argv[1]
    limit = int(sys.argv[sys.argv.index("--list") + 1]) if "--list" in sys.argv else 40
    live = open(run + "/ee_00200000_302e60.bin", "rb").read()
    staged = open(run + "/ee_01000000_302e60.bin", "rb").read()
    a, b = words(live), words(staged)
    diff = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
    text = [i for i in diff if i * 4 < TEXT]
    print("words compared: %d (.text %d)" % (min(len(a), len(b)), TEXT // 4))
    print("differing words, whole core image: %d" % len(diff))
    print("differing words, .text 0x%x..0x%x: %d" % (BASE, BASE + TEXT, len(text)))
    for i in text[:limit]:
        print("  %08x: live %08x staged %08x" % (BASE + 4 * i, a[i], b[i]))
    # Where the non-text differences are (POPS writes its own .data at run time).
    runs, start, prev = [], None, None
    for i in diff:
        if i * 4 < TEXT:
            continue
        if start is None or i != prev + 1:
            if start is not None:
                runs.append((start, prev))
            start = i
        prev = i
    if start is not None:
        runs.append((start, prev))
    print("differing runs outside .text: %d; first ones:" % len(runs))
    for lo, hi in runs[:12]:
        print("  %08x..%08x (%d words)" % (BASE + 4 * lo, BASE + 4 * hi + 4, hi - lo + 1))
    args = sys.argv[2:]
    for k, arg in enumerate(args):
        if arg == "--watch":
            lo, hi = (int(x, 16) for x in args[k + 1].split(":"))
            bad = [i for i in range((lo - BASE) // 4, (hi - BASE + 3) // 4) if a[i] != b[i]]
            print("watch 0x%08x..0x%08x: %d differing word(s)" % (lo, hi, len(bad)))


main()
