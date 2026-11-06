#!/usr/bin/env python3
"""Prepare/verify a local native R5900 request probe from a pinned external ELF.

Original binary bytes are generated only under ignored build/. The original
function remains unchanged at its original address; only external service
entries redirect to the explicitly named doubles. Do not upload generated
ELFs or C arrays. Commit metadata and stdout observations only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[1]
POPS_SHA = "59df3389c4df88a572daa720b05507c52c34eddfa0031a6fbeec55e0c2d0fcb1"
START, END = 0x210090, 0x21021c
SERVICES = {0x20fde0: "pops_probe_track", 0x22e860: "pops_probe_wait",
            0x22e840: "pops_probe_signal", 0x230330: "pops_probe_rpc",
            0x240f60: "pops_probe_log"}
RESERVED = [(START, END), (0x50289c, 0x5028a0), (0x502f0c, 0x502f10),
            (0x59f680, 0x5a8dc0), (0x5a8dc0, 0x5a9200)] + [
                (address, address + 8) for address in SERVICES]


def segments(data):
    if len(data) < 52 or data[:6] != b"\x7fELF\x01\x01" or struct.unpack_from("<H", data, 18)[0] != 8:
        raise ValueError("expected ELF32 little-endian MIPS")
    offset = struct.unpack_from("<I", data, 28)[0]
    size, count = struct.unpack_from("<HH", data, 42)
    if size < 32 or not 0 < count <= 128 or offset + size * count > len(data):
        raise ValueError("invalid ELF program headers")
    result = []
    for i in range(count):
        kind, off, addr, _, files, memory, flags, _ = struct.unpack_from("<8I", data, offset + size * i)
        if kind != 1:
            continue
        if files > memory or off + files > len(data) or addr + memory > 0x100000000:
            raise ValueError("invalid ELF load segment")
        result.append((off, addr, files, memory, flags))
    if not result:
        raise ValueError("ELF has no load segments")
    return result


def verify(probe):
    for _, addr, _, memory, _ in segments(probe.read_bytes()):
        if any(addr < high and addr + memory > low for low, high in RESERVED):
            raise ValueError("probe PT_LOAD/BSS overlaps original code, services or fixed globals")
    print("POPS_EE_IO_LAYOUT_PASS " + hashlib.sha256(probe.read_bytes()).hexdigest())


def prepare(elf, out):
    data = elf.read_bytes()
    if hashlib.sha256(data).hexdigest() != POPS_SHA:
        raise ValueError("unknown external POPS identity")
    matches = [(off + START - addr, off + END - addr)
               for off, addr, files, _, flags in segments(data)
               if flags & 1 and addr <= START and END <= addr + files]
    if len(matches) != 1:
        raise ValueError("original function is not uniquely mapped executable data")
    begin, end = matches[0]
    blob = data[begin:end]
    if not out.resolve().is_relative_to((ROOT / "build").resolve()) or out.exists():
        raise ValueError("use a fresh output directory under ignored build/")
    out.mkdir(parents=True)
    for name in ("pops_io_request_probe.c", "pops_io_request_entry.S"):
        shutil.copyfile(ROOT / "tools" / "fixtures" / name, out / name)
    source = ('/* LOCAL ORIGINAL BYTES - NEVER COMMIT OR DISTRIBUTE. */\n'
              '#include <stdint.h>\n#include <string.h>\n#include <kernel.h>\n')
    for name in SERVICES.values():
        source += f'extern void {name}(void);\n'
    source += 'static const unsigned char original[] = {\n'
    source += ',\n'.join(', '.join(f'0x{x:02x}' for x in blob[i:i+16])
                          for i in range(0, len(blob), 16)) + '\n};\n'
    source += 'void pops_probe_install_original(void) {\n'
    source += f' memcpy((void *)0x{START:08x}u, original, sizeof(original));\n'
    for address, name in SERVICES.items():
        source += f' *(volatile uint32_t *)0x{address:08x}u = 0x08000000u | (((uintptr_t){name} >> 2) & 0x03ffffffu);\n'
        source += f' *(volatile uint32_t *)0x{address + 4:08x}u = 0;\n'
    source += ' FlushCache(0); FlushCache(2);\n}\n'
    (out / "original_function.c").write_text(source, encoding="utf-8")
    (out / "ps2.yaml").write_text(json.dumps({"project": "pops-original-io-request", "targets": [{
        "name": "pops_io_request_probe", "type": "ee", "sources": [
            "pops_io_request_probe.c", "pops_io_request_entry.S", "original_function.c"],
        "opt": "-O2", "debug": True,
    }]}, indent=2) + "\n", encoding="utf-8")
    (out / "provenance.json").write_text(json.dumps({
        "original_elf_sha256": POPS_SHA, "function_start": START, "function_end": END,
        "function_sha256": hashlib.sha256(blob).hexdigest(),
        "modeled_service_entries": {hex(k): v for k, v in SERVICES.items()},
        "limits": "Single original R5900 function, synthetic TOC/RPC/semaphore state; no console or save acceptance.",
    }, indent=2) + "\n", encoding="utf-8")
    print("Prepared local original-byte probe. Verify the linked ELF before execution.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, help="external Sony POPS ELF")
    parser.add_argument("--out", type=Path, help="fresh ignored output directory")
    parser.add_argument("--verify-probe", type=Path, help="check every linked PT_LOAD/BSS against injections")
    args = parser.parse_args()
    if args.verify_probe:
        verify(args.verify_probe)
    elif args.elf and args.out:
        prepare(args.elf, args.out)
    else:
        parser.error("supply --elf and --out, or --verify-probe")
