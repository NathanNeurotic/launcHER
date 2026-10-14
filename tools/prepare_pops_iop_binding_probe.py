#!/usr/bin/env python3
"""Prepare a local-only Sony IOP kernel/RPC binding probe.

External Sony bytes and generated ELFs remain in ignored build/. Production
IRXs are copied from an existing launcher build's bin2c source and hashed.
Only the backing medium is synthetic. No original kernel/IOPCD patches.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
POPS_SHA = "59df3389c4df88a572daa720b05507c52c34eddfa0031a6fbeec55e0c2d0fcb1"
IOPCD_SHA = "ccdd60e1408b7dbc4a65e9fdad53b671e7acdb69fc5acc72704a952feacd58ae"
IOPRP_SHA = "3338b238d84d7d586b716677e3a1c03b2088b882ecfa17f91fc33798931ca3ba"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def array(name, data):
    return ("/* LOCAL EXTERNAL BYTES: do not commit or distribute. */\n"
            f"unsigned int size_{name}_irx = {len(data)};\n"
            f"unsigned char {name}_irx[] __attribute__((aligned(16))) = {{\n" +
            ",\n".join(",".join(str(x) for x in data[i:i+32])
                        for i in range(0, len(data), 32)) + "\n};\n")


def prepare(elf, image, launcher_build, out, console_screen=False):
    pops, reboot = elf.read_bytes(), image.read_bytes()
    if sha(pops) != POPS_SHA or sha(reboot) != IOPRP_SHA:
        raise ValueError("unrecognized selected Sony ELF/IOPRP identity")
    iopcd = pops[0xfb820:0xfb820 + 0x3e4f]
    if sha(iopcd) != IOPCD_SHA:
        raise ValueError("unrecognized selected embedded Sony IOPCD")
    if not out.resolve().is_relative_to((ROOT / "build").resolve()) or out.exists():
        raise ValueError("use a fresh directory under ignored build/")
    modules = {}
    for name in ("iomanX", "fileXio", "popfs"):
        text = (launcher_build / "launcher" / f"{name}.irx.c").read_text()
        body = re.search(r"unsigned char\s+\w+\[\].*?=\s*\{(.*?)\};", text, re.S)
        declared = re.search(r"unsigned int\s+size_\w+\s*=\s*(\d+)", text)
        if not body or not declared:
            raise ValueError(f"invalid production bin2c source for {name}")
        data = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})\b", body[1]))
        if len(data) != int(declared[1]) or not data.startswith(b"\x7fELF"):
            raise ValueError(f"truncated production module {name}")
        modules[name] = data
    out.mkdir(parents=True)
    for filename in ("pops_iop_binding_probe.c", "pops_iop_binding_backend.c",
                     "pops_iop_binding_imports.lst"):
        shutil.copyfile(ROOT / "tools/fixtures" / filename, out / filename)
    (out / "irx_imports.h").write_text(
        "#include <irx.h>\n#include <iomanX.h>\n#include <sysclib.h>\n#include <stdio.h>\n", encoding="utf-8")
    for directory, filename in (("common/src", "pops_bootstrap.c"),
            ("common/include", "pops_bootstrap.h"), ("common/include", "pops_external.h")):
        shutil.copyfile(ROOT / directory / filename, out / filename)
    modules.update(sony_ioprp=reboot, sony_iopcd=iopcd)
    for name, data in modules.items():
        (out / f"{name}_irx.c").write_text(array(name, data), encoding="utf-8")
    config = {"project": "pops-real-iop-binding", "targets": [
        {"name": "binding_backend", "type": "iop", "sources": ["pops_iop_binding_backend.c"],
         "imports_lst": "pops_iop_binding_imports.lst", "headers": ["iomanx"],
         "include_dirs": ["."], "opt": "-O2",
         "defines": ["IOMANX_OLD_NAME_COMPATIBILITY=0", "IOMANX_OLD_NAME_ADDDELDRV=0"]},
        {"name": "pops_iop_binding_probe", "type": "ee", "sources": [
            "pops_iop_binding_probe.c", "pops_bootstrap.c"] + [f"{name}_irx.c" for name in modules],
         "include_dirs": ["."], "embed_irx": ["binding_backend"],
         "libs": ["iopreboot", "filexio", "patches"], "opt": "-O2", "debug": True}
    ]}
    if console_screen:
        config["targets"][1]["defines"] = ["POPS_BINDING_CONSOLE_SCREEN=1"]
        config["targets"][1]["libs"].append("debug")
    (out / "ps2.yaml").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (out / "provenance.json").write_text(json.dumps({
        "pops_elf_sha256": POPS_SHA, "console_screen": console_screen,
        "module_sha256": {k: sha(v) for k, v in modules.items()},
        "scope": "Actual Sony IOP kernel and IOPCD, actual SIF RPC and production bridge modules; storage medium is controlled IOP memory."
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--iop-image", type=Path, required=True)
    parser.add_argument("--launcher-build", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--console-screen", action="store_true",
                        help="Hardware capture: show EE progress on GS, do not reserve emulator stdout descriptors")
    args = parser.parse_args()
    prepare(args.elf, args.iop_image, args.launcher_build, args.out, args.console_screen)
