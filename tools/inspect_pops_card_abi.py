#!/usr/bin/env python3
"""Compare built card-service imports with the pinned external Sony SIO2 ABI.

Read-only: prints hashes, library versions and ordinal numbers, never Sony bytes.
This is an ABI inspection, not execution or hardware acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

POPS_SHA = "59df3389c4df88a572daa720b05507c52c34eddfa0031a6fbeec55e0c2d0fcb1"
SIO2_SHA = "1964b83bcc8c0cab9dfcf9b9637e0e313e69c23fd5c73408fe889ace91f13708"


def tables(blob, magic):
    if blob[:6] != b"\x7fELF\x01\x01":
        raise ValueError("expected ELF32 little-endian module")
    found = {}
    for off in range(0, len(blob)-20, 4):
        if struct.unpack_from("<I", blob, off)[0] != magic:
            continue
        name = blob[off+12:off+20].rstrip(b"\0").decode("ascii")
        version = struct.unpack_from("<H", blob, off+8)[0]
        ordinals = []
        if magic == 0x41e00000:
            cursor = off+20
            while cursor+8 <= len(blob):
                jump, ordinal = struct.unpack_from("<II", blob, cursor)
                if jump != 0x03e00008 or ordinal >> 16 != 0x2400:
                    break
                ordinals.append(ordinal & 0xffff)
                cursor += 8
        found[name] = {"version": version, "ordinals": ordinals}
    return found


def built(build, name):
    text = (build / "launcher" / (name+".irx.c")).read_text()
    body = re.search(r"unsigned char\s+\w+\[\].*?=\s*\{(.*?)\};", text, re.S)
    declared = re.search(r"unsigned int\s+size_\w+\s*=\s*(\d+)", text)
    if not body or not declared:
        raise ValueError("invalid bin2c module: "+name)
    data = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})\b", body[1]))
    if len(data) != int(declared[1]):
        raise ValueError("truncated module: "+name)
    return data


def inspect(elf, build):
    original = elf.read_bytes()
    if hashlib.sha256(original).hexdigest() != POPS_SHA:
        raise ValueError("requires the pinned external POPS.ELF")
    phoff = struct.unpack_from("<I", original, 28)[0]
    stride, count = struct.unpack_from("<HH", original, 42)
    segments = [struct.unpack_from("<8I", original, phoff+i*stride) for i in range(count)]
    core = next(p for p in segments if p[0] == 1 and p[2] == 0x200000)
    sony = original[core[1]+0xcbbc0:core[1]+0xcbbc0+0x1999]
    if hashlib.sha256(sony).hexdigest() != SIO2_SHA:
        raise ValueError("changed embedded Sony SIO2")
    sony_export = tables(sony, 0x41c00000)["sio2man"]
    modules = {}
    for name in ("mcman", "mcman-2000", "mcserv", "secrman"):
        blob = built(build, name)
        modules[name] = {"sha256": hashlib.sha256(blob).hexdigest(),
                         "imports": tables(blob, 0x41e00000),
                         "exports": tables(blob, 0x41c00000)}
    card = modules["mcman-2000"]
    if card["imports"]["sio2man"] != {"version": sony_export["version"], "ordinals": [24,25,26,57]}:
        raise ValueError("selected card manager does not match Sony SIO2 2.3")
    if modules["mcserv"]["imports"]["mcman"]["version"] != card["exports"]["mcman"]["version"]:
        raise ValueError("card server/manager version mismatch")
    if card["imports"]["secrman"]["version"] != modules["secrman"]["exports"]["secrman"]["version"]:
        raise ValueError("card authentication version mismatch")
    return {"sony_sio2_sha256": SIO2_SHA, "sony_sio2_export": sony_export,
            "modules": modules, "selected_abi_matches": True,
            "limits": "Static library/ordinal inspection only; not full IOP dependency or runtime acceptance."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--launcher-build", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.launcher_build), indent=2))
