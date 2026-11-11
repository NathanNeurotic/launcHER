#!/usr/bin/env python3
"""Wrap a single-track MODE2/2352 .bin in the CUE2POPS-style 0x100000-byte VCD header.

Layout follows launcHER tools/test_pops_features.py (marker 'kHn ' at 0x400,
sector count at 0x408/0x40C, disc payload at 0x100000) plus a one-track TOC.
"""
import struct, sys

def bcd(v): return ((v // 10) << 4) | (v % 10)
def msf(lba):
    return bcd(lba // 4500), bcd(lba // 75 % 60), bcd(lba % 75)

src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
if len(data) % 2352: sys.exit("not a raw 2352-byte image")
sectors = len(data) // 2352
h = bytearray(0x100000)
h[0:10] = bytes([0x41, 0, 0xA0, 0, 0, 0, 0, 0x01, 0x20, 0])
h[10:20] = bytes([0x41, 0, 0xA1, 0, 0, 0, 0, 0x01, 0, 0])
m, s, f = msf(sectors + 150)
h[20:30] = bytes([0x41, 0, 0xA2, 0, 0, 0, 0, m, s, f])
h[30:40] = bytes([0x41, 0, 0x01, 0, 0, 0, 0, 0x00, 0x02, 0x00])
h[0x400:0x404] = b"kHn "
struct.pack_into("<II", h, 0x408, sectors, sectors)
with open(dst, "wb") as out:
    out.write(h); out.write(data)
print("sectors", sectors, "bytes", len(h) + len(data))
