#!/usr/bin/env python3
"""Prepare an owned-child test of production trampoline relocation/ExecPS2."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from prepare_pops_io_request_probe import segments

ROOT=Path(__file__).resolve().parents[1]

def prepare(out,linkfile,disable):
    if out.exists() or not out.resolve().is_relative_to((ROOT/"build").resolve()):
        raise ValueError("use a fresh ignored build directory")
    script=linkfile.read_text()
    if script.count(".text 0x00100000:")!=1:
        raise ValueError("unexpected SDK linker script")
    out.mkdir(parents=True)
    (out/"child.ld").write_text(script.replace(".text 0x00100000:",".text 0x00200000:"))
    for name in ("pops_trampoline_parent.c","pops_trampoline_child.c"):
        shutil.copyfile(ROOT/"tools/fixtures"/name,out/name)
    shutil.copyfile(ROOT/"launcher/src/pops_trampoline.S",out/"pops_trampoline.S")
    for name in ("pops_bootstrap.h","pops_external.h"):
        shutil.copyfile(ROOT/"common/include"/name,out/name)
    config={"project":"pops-owned-trampoline","targets":[
        {"name":"child","type":"ee","sources":["pops_trampoline_child.c"],
         "linkfile":"child.ld","libs":["debug"],"ldflags":["-s"]},
        {"name":"parent","type":"ee","sources":["pops_trampoline_parent.c","pops_trampoline.S"],
         "embed_irx":["child"],"libs":["debug"],"include_dirs":["."],
         "defines":[f"PROBE_DISABLE_INTERRUPTS={int(disable)}"],"debug":True}]}
    (out/"ps2.yaml").write_text(json.dumps(config,indent=2)+"\n")
    (out/"provenance.json").write_text(json.dumps({
        "trampoline_source_sha256":hashlib.sha256((out/"pops_trampoline.S").read_bytes()).hexdigest(),
        "disable_interrupts":disable,"scope":"Owned child plus actual trampoline/kernel; no Sony, game or save inputs."
    },indent=2)+"\n")

def verify(path):
    for _,address,_,memory,_ in segments(path.read_bytes()):
        if address<0x100000 or address+memory>0x200000:
            raise ValueError(f"parent load/BSS {address:#x}..{address+memory:#x} does not fit its intentionally cleared low-RAM region")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path)
    p.add_argument("--linkfile",type=Path)
    p.add_argument("--disable-interrupts",action="store_true")
    p.add_argument("--verify-parent",type=Path)
    a=p.parse_args()
    if a.verify_parent: verify(a.verify_parent)
    elif a.out and a.linkfile: prepare(a.out,a.linkfile,a.disable_interrupts)
    else: p.error("supply --out/--linkfile or --verify-parent")
