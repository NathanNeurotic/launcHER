#!/usr/bin/env python3
"""Prepare bounded original Sony argument parsing; original arrays stay local."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from prepare_pops_io_request_probe import segments, POPS_SHA, ROOT

REGIONS=[(0x2004f0,0x2006fc),(0x2414a0,0x241630),(0x501f00,0x502030)]
RESERVED=REGIONS+[(0x23dae0,0x23dae8),(0x22faf0,0x22faf8),
                  (0x502710,0x502714),(0x5030c8,0x5033c8)]

def prepare(elf,out):
    data=elf.read_bytes()
    if hashlib.sha256(data).hexdigest()!=POPS_SHA:
        raise ValueError("unknown external POPS identity")
    if out.exists() or not out.resolve().is_relative_to((ROOT/"build").resolve()):
        raise ValueError("use a fresh ignored build directory")
    blobs=[]
    for start,end in REGIONS:
        matches=[off+start-address for off,address,files,_,_ in segments(data)
                 if address<=start and end<=address+files]
        if len(matches)!=1: raise ValueError("original region is not uniquely file-backed")
        blobs.append(data[matches[0]:matches[0]+end-start])
    out.mkdir(parents=True)
    for name in ("pops_startup_args_entry.S","pops_startup_args_probe.c"):
        shutil.copyfile(ROOT/"tools/fixtures"/name,out/name)
    source='/* LOCAL ORIGINAL BYTES: DO NOT COMMIT OR DISTRIBUTE. */\n#include <stdint.h>\n#include <string.h>\n#include <kernel.h>\nextern void pops_startup_stop(void),pops_startup_noop(void);\n'
    for i,blob in enumerate(blobs):
        source+=f'static const unsigned char original_{i}[]={{'+','.join(map(str,blob))+'};\n'
    source+='void pops_startup_install(void){\n'
    for i,(start,_) in enumerate(REGIONS):
        source+=f'memcpy((void *)0x{start:x},original_{i},sizeof(original_{i}));\n'
    for address,name in ((0x23dae0,'pops_startup_noop'),(0x22faf0,'pops_startup_stop')):
        source+=f'*(volatile uint32_t *)0x{address:x}=0x08000000u|(((uintptr_t){name}>>2)&0x03ffffffu);\n*(volatile uint32_t *)0x{address+4:x}=0;\n'
    source+='FlushCache(0);FlushCache(2);}\n'
    (out/'original_parser.c').write_text(source)
    (out/'ps2.yaml').write_text(json.dumps({'project':'pops-startup-args','targets':[
        {'name':'startup_args','type':'ee','sources':['pops_startup_args_probe.c',
         'pops_startup_args_entry.S','original_parser.c'],'debug':True,'opt':'-O2'}]},indent=2)+'\n')
    (out/'provenance.json').write_text(json.dumps({'original_elf_sha256':POPS_SHA,
        'regions':[{'start':start,'end':end,'sha256':hashlib.sha256(blob).hexdigest()}
                   for (start,end),blob in zip(REGIONS,blobs)],
        'services':{'0x23dae0':'modeled no-op','0x22faf0':'stop before runtime initialization'},
        'limits':'Original parser prefix and original R5900 string routine; no Sony CRT, IOP, game or save acceptance.'},indent=2)+'\n')

def verify(path):
    for _,address,_,memory,_ in segments(path.read_bytes()):
        if any(address<high and address+memory>low for low,high in RESERVED):
            raise ValueError("startup probe overlaps original code/data/service regions")

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--elf',type=Path);p.add_argument('--out',type=Path)
    p.add_argument('--verify-probe',type=Path)
    a=p.parse_args()
    if a.verify_probe: verify(a.verify_probe)
    elif a.elf and a.out: prepare(a.elf,a.out)
    else: p.error('supply --elf/--out or --verify-probe')
