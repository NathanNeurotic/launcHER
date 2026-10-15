#!/usr/bin/env python3
"""Read-only census of Sony POPS early-startup direct/indirect control transfers.

Operates only on the hash-pinned external POPS.ELF; emits addresses and instruction
classes, never Sony code bytes. It is a *static* upper bound, not an execution trace.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from prepare_pops_io_request_probe import POPS_SHA, segments

START = 0x002004f0
END = 0x002006fc


def scan_words(blob, origin=START):
    """Classify MIPS control transfers without inferring reachability."""
    if len(blob) % 4 or origin & 3:
        raise ValueError("control-transfer region must be word aligned")
    records = []
    for offset in range(0, len(blob), 4):
        word = struct.unpack_from("<I", blob, offset)[0]
        pc = origin + offset
        opcode = word >> 26
        kind = None
        target = None
        if opcode in (2, 3):
            kind = "jump" if opcode == 2 else "call"
            target = ((pc + 4) & 0xf0000000) | ((word & 0x03ffffff) << 2)
        elif opcode == 0 and (word & 0x3f) == 9:
            kind = "indirect-call"
        elif opcode == 1 and (word >> 16) & 0x1f in (0x10, 0x11, 0x12, 0x13):
            kind = "conditional-call"
            displacement = struct.unpack("<h", struct.pack("<H", word & 0xffff))[0] << 2
            target = pc + 4 + displacement
        if kind:
            row = {"pc": f"0x{pc:08x}", "kind": kind}
            if target is not None:
                row["target"] = f"0x{target & 0xffffffff:08x}"
            records.append(row)
    return records


def inspect(data):
    if hashlib.sha256(data).hexdigest() != POPS_SHA:
        raise ValueError("unknown external Sony POPS image; refusing address census")
    candidates = []
    for off, addr, files, _, flags in segments(data):
        if flags & 1 and addr <= START and END <= addr + files:
            candidates.append(off + START - addr)
    if len(candidates) != 1:
        raise ValueError("startup range is not uniquely mapped executable file data")
    offset = candidates[0]
    region = data[offset:offset + END - START]
    records = scan_words(region, START)
    return {
        "source_sha256": POPS_SHA,
        "address_range": [f"0x{START:08x}", f"0x{END:08x}"],
        "range_sha256": hashlib.sha256(region).hexdigest(),
        "static_control_transfers": records,
        "limits": (
            "Static word census only; unknown indirect targets and branches, "
            "not reachability or executed order. Original startup helper and "
            "runtime initialization remain unmodeled. No Sony bytes emitted."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--json", type=Path, help="metadata-only report path")
    args = parser.parse_args()
    result = inspect(args.elf.read_bytes())
    report = json.dumps(result, indent=2) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(report, encoding="utf-8")
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
