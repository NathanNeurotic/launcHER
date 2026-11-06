#!/usr/bin/env python3
"""Check every POPS address launcHER writes against the original POPStarter.

Reads an externally unpacked POPSTARTER MAIN image (base 0x00870000, see
REPOP tools/unpack_popstarter.py). The image is never copied into the repo.

Pass 1 collects the addresses the original passes (as a1) to its write
helpers 0x8dc8e4/0x8dc918/0x8dc94c/0x8dc97c. Pass 2 searches the whole image
for any lui/ori|addiu|load|store reference to each unmatched address. An
address with no reference anywhere has no grounding in the original binary.
"""
import argparse
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x870000
HELPERS = {0x8dc8e4: 1, 0x8dc918: 2, 0x8dc94c: 4, 0x8dc97c: 8}
SOURCES = ("common/src/pops_modes_patches.c", "common/src/pops_core_patches.c")


def helper_sites(words):
    sites = {}
    for i, ins in enumerate(words):
        if ins >> 26 != 3 or ((ins & 0x3ffffff) << 2) not in HELPERS:
            continue
        hi = lo = None
        for j in range(max(0, i - 6), min(len(words), i + 2)):
            x = words[j]
            op, rs, rt, imm = x >> 26, (x >> 21) & 31, (x >> 16) & 31, x & 0xffff
            if op == 0x0f and rt == 5:
                hi = imm
            elif op == 0x0d and rs == rt == 5:
                lo = imm
            elif op == 0x09 and rs == rt == 5:
                lo = imm - 0x10000 if imm & 0x8000 else imm
        if hi is not None and lo is not None:
            sites[((hi << 16) + lo) & 0xffffffff] = HELPERS[(ins & 0x3ffffff) << 2]
    return sites


def any_reference(words, address):
    hi, lo = address >> 16, address & 0xffff
    hits = []
    for i, x in enumerate(words):
        if x >> 26 != 0x0f or (x & 0xffff) != hi:
            continue
        rt = (x >> 16) & 31
        for j in range(i + 1, min(i + 6, len(words))):
            y = words[j]
            if ((y >> 21) & 31) == rt and (y >> 26) in (0x0d, 0x09, 0x20, 0x23, 0x24, 0x28, 0x29, 0x2b) \
                    and (y & 0xffff) == lo:
                hits.append(BASE + j * 4)
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", type=Path, default=ROOT / "build/popstarter-main-unpacked.bin")
    args = ap.parse_args()
    if not args.binary.is_file():
        ap.error(f"Binary not found: {args.binary}. Unpack popstarter main image to this path or pass --binary.")
    data = args.binary.read_bytes()
    words = struct.unpack_from("<%dI" % (len(data) // 4), data)
    sites = helper_sites(words)

    refs = {}
    for name in SOURCES:
        text = (ROOT / name).read_text()
        for m in re.finditer(r"0x00?([2-5][0-9a-fA-F]{5})\b", text):
            address = int(m.group(1), 16)
            if 0x200000 < address < 0x503000:
                refs.setdefault(address, []).append(f"{Path(name).name}:{text[:m.start()].count(chr(10)) + 1}")

    print(f"original helper write sites: {len(sites)}")
    print(f"launcHER POPS addresses: {len(refs)}; matched helper sites: {sum(a in sites for a in refs)}")
    print("unmatched addresses (any_reference = other code references in the original):")
    for address in sorted(a for a in refs if a not in sites):
        hits = any_reference(words, address)
        status = "referenced" if hits else "NO REFERENCE"
        print(f"  0x{address:08x} {status:12} {', '.join(hex(h) for h in hits[:3]):32} {', '.join(refs[address][:3])}")


if __name__ == "__main__":
    main()
