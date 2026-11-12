#!/usr/bin/env python3
"""Print EE kernel syscall table entries and disassemble a range from a dump
whose first byte is at 0x80000000.

  python ksys.py DUMP table N [N ...]      (hex syscall numbers)
  python ksys.py DUMP dis START END        (hex addresses)
  python ksys.py DUMP str ADDR [LEN]
  python ksys.py DUMP words ADDR COUNT
"""
import struct
import sys

import capstone


def main():
    data = open(sys.argv[1], "rb").read()
    base = 0x80000000

    def u32(a):
        return struct.unpack_from("<I", data, (a & 0x1fffffff))[0]

    if sys.argv[2] == "table":
        for n in sys.argv[3:]:
            n = int(n, 16)
            print("syscall %#x -> %08x" % (n, u32(0x80014d00 + 4 * n)))
    elif sys.argv[2] == "dis":
        start, end = int(sys.argv[3], 16), int(sys.argv[4], 16)
        md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS64 | capstone.CS_MODE_LITTLE_ENDIAN)
        pos = start
        while pos < end:
            chunk = data[(pos & 0x1fffffff):(pos & 0x1fffffff) + 4]
            word = struct.unpack("<I", chunk)[0]
            ins = list(md.disasm(chunk, pos))
            text = ("%s %s" % (ins[0].mnemonic, ins[0].op_str)) if ins else ".word"
            if word == 0x42000039:
                text = "di"
            elif word == 0x42000038:
                text = "ei"
            print("%08x: %08x  %s" % (pos, word, text))
            pos += 4
    elif sys.argv[2] == "str":
        a = int(sys.argv[3], 16) & 0x1fffffff
        n = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x100
        print(repr(data[a:a + n]))
    elif sys.argv[2] == "words":
        a = int(sys.argv[3], 16)
        for i in range(int(sys.argv[4], 0)):
            print("%08x: %08x" % (a + 4 * i, u32(a + 4 * i)))


if __name__ == "__main__":
    main()
