#!/usr/bin/env python3
"""Prepare a read-only USB/MMCE inventory probe with production launcher IRXs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
from prepare_pops_iop_binding_probe import ROOT, array


def module_name(data):
    phoff = struct.unpack_from("<I", data, 28)[0]
    stride, count = struct.unpack_from("<HH", data, 42)
    headers = [struct.unpack_from("<8I", data, phoff + i * stride) for i in range(count)]
    def offset(address):
        for kind, file_offset, virtual, _, size, *_ in headers:
            if kind == 1 and virtual <= address < virtual + size:
                return file_offset + address - virtual
        raise ValueError("module ID points outside file-backed load segment")
    info = next((ph for ph in headers if ph[0] == 0x70000080), None)
    if info is None:
        raise ValueError("IOP module header missing")
    identifier = struct.unpack_from("<I", data, info[1])[0]
    if identifier == 0xffffffff:
        return ""  # iomanX has no IRX_ID; its library is checked instead.
    pointer = struct.unpack_from("<I", data, offset(identifier))[0]
    start = offset(pointer)
    end = data.find(b"\0", start, start + 96)
    if end < 0:
        raise ValueError("unterminated module name")
    return data[start:end].decode("ascii")


def prepare(launcher_build, out):
    if out.exists() or not out.resolve().is_relative_to((ROOT / "build").resolve()):
        raise ValueError("use a fresh directory under ignored build/")
    modules = {}
    for name in ("iomanX", "fileXio", "sio2man", "mcman", "mcserv", "bdm", "bdmfs_fatfs",
                 "usbd_mini", "usbmass_bd_mini", "mmceman", "mx4sio_bd_mini", "ata_bd"):
        source = (launcher_build / "launcher" / f"{name}.irx.c").read_text()
        body = re.search(r"unsigned char\s+\w+\[\].*?=\s*\{(.*?)\};", source, re.S)
        declared = re.search(r"unsigned int\s+size_\w+\s*=\s*(\d+)", source)
        if not body or not declared:
            raise ValueError(f"invalid bin2c module {name}")
        data = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})\b", body[1]))
        if len(data) != int(declared[1]) or not data.startswith(b"\x7fELF"):
            raise ValueError(f"truncated module {name}")
        modules[name] = data
    out.mkdir(parents=True)
    for name in ("pops_device_inventory_ee.c",):
        shutil.copyfile(ROOT / "tools/fixtures" / name, out / name)
    shutil.copyfile(ROOT / "common/src/pops_vcd.c", out / "pops_vcd.c")
    shutil.copyfile(ROOT / "common/include/pops_vcd.h", out / "pops_vcd.h")
    for name, data in modules.items():
        (out / f"{name}_irx.c").write_text(array(name, data))
    (out / "production_names.h").write_text("\n".join(
        f"#define MODULE_NAME_{name} {json.dumps(module_name(data))}" for name, data in modules.items()) + "\n")
    config = {"project": "pops-device-inventory", "targets": [
        {"name": "inventory", "type": "ee", "sources": ["pops_device_inventory_ee.c", "pops_vcd.c"] +
         [f"{name}_irx.c" for name in modules], "include_dirs": ["."],
         "libs": ["patches", "filexio", "debug"], "debug": True}]}
    (out / "ps2.yaml").write_text(json.dumps(config, indent=2) + "\n")
    (out / "provenance.json").write_text(json.dumps(
        {name: hashlib.sha256(data).hexdigest() for name, data in modules.items()}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher-build", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.launcher_build, args.out)
