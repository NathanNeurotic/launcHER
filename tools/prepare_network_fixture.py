#!/usr/bin/env python3
"""Create only a new, owned server-side folder for console filesystem tests."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

def prepare(root):
    root = root.resolve(strict=True)
    if not root.is_dir(): raise ValueError("server root must be an existing directory")
    name = "LAUNCHER-NET-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    folder = root/name
    if not folder.resolve().is_relative_to(root): raise ValueError("fixture escapes server root")
    folder.mkdir()  # no exist_ok: never reuse a folder containing an earlier test
    hashes = {}
    for name, seed in (("FIXTURE.BIN",0x31),("EXISTING.BIN",0x73)):
        data = bytes(((i*17 + seed) & 255) for i in range(8192))
        with (folder/name).open("xb") as stream: stream.write(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    return {"directory":str(folder),"relative_directory":folder.name,
            "initial_sha256":hashes,"console_created_file":"NEW.BIN"}

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    result=prepare(args.root)
    args.report.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result))
