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
END = 0x002006fc  # hardware-executed parser prefix only
FUNCTION_END = 0x00200924  # 1076-byte Ghidra original function extent


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



def parse_function_metadata(raw):
    """Validate provided Ghidra metadata, retaining ambiguous overlaps."""
    entries = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(entries, list) or len(entries) > 20000:
        raise ValueError("invalid Ghidra function inventory")
    functions = []
    for row in entries:
        if not isinstance(row, dict):
            raise ValueError("invalid Ghidra function entry")
        address, size, name = row.get("address"), row.get("size"), row.get("name")
        if (not isinstance(address, str) or len(address) != 8
                or any(x not in "0123456789abcdefABCDEF" for x in address)
                or type(size) is not int or not 0 < size <= 0x100000
                or not isinstance(name, str) or not name or len(name) > 128):
            raise ValueError("invalid Ghidra function entry")
        start = int(address, 16)
        if start + size > 0x100000000:
            raise ValueError("Ghidra function address overflow")
        functions.append((start, start + size, name))
    return sorted(functions)


def annotate_ground_truth(records, functions):
    """Show candidate original function ranges, never inferred execution."""
    result = []
    for record in records:
        row = dict(record)
        if "target" in row:
            target = int(row["target"], 16)
            row["ground_truth_candidates"] = [
                {"name": name, "offset": target - low, "at_entry": target == low}
                for low, high, name in functions if low <= target < high
            ]
        result.append(row)
    return result


def inspect(data, whole_function=False, functions=None):
    if hashlib.sha256(data).hexdigest() != POPS_SHA:
        raise ValueError("unknown external Sony POPS image; refusing address census")
    end = FUNCTION_END if whole_function else END
    candidates = []
    for off, addr, files, _, flags in segments(data):
        if flags & 1 and addr <= START and end <= addr + files:
            candidates.append(off + START - addr)
    if len(candidates) != 1:
        raise ValueError("startup range is not uniquely mapped executable file data")
    offset = candidates[0]
    region = data[offset:offset + end - START]
    records = scan_words(region, START)
    if functions is not None:
        records = annotate_ground_truth(records, functions)
    return {
        "source_sha256": POPS_SHA,
        "address_range": [f"0x{START:08x}", f"0x{end:08x}"],
        "scope": "original_whole_function_static" if whole_function else "hardware_parser_prefix_static",
        "range_sha256": hashlib.sha256(region).hexdigest(),
        "static_control_transfers": records,
        "limits": (
            "Static word census only; original function ranges may overlap. "
            "Unknown indirect targets and branches, "
            "not reachability or executed order. Original startup helper and "
            "runtime initialization remain unmodeled. No Sony bytes emitted."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--json", type=Path, help="metadata-only report path")
    parser.add_argument("--whole-function", action="store_true", help="include Ghidra's full original function")
    parser.add_argument("--functions", type=Path, help="optional REPOP Ghidra functions.json")
    args = parser.parse_args()
    raw = args.functions.read_bytes() if args.functions else None
    functions = parse_function_metadata(raw) if raw is not None else None
    result = inspect(args.elf.read_bytes(), whole_function=args.whole_function,
                     functions=functions)
    if raw is not None:
        result["function_inventory_sha256"] = hashlib.sha256(raw).hexdigest()
        result["function_inventory_scope"] = "User-provided function intervals, not an executed call graph"
    report = json.dumps(result, indent=2) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(report, encoding="utf-8")
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
