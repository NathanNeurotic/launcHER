#!/usr/bin/env python3
"""Verify host-created files survived and the console wrote the owned pattern."""
import argparse,hashlib,json
from pathlib import Path

def verify(report):
    data=json.loads(report.read_text(encoding="utf-8"))
    root=Path(data["directory"])
    result={}
    for name,expected in data["initial_sha256"].items():
        actual=hashlib.sha256((root/name).read_bytes()).hexdigest()
        if actual!=expected: raise ValueError("owned fixture changed: "+name)
        result[name]=actual
    name=data["console_created_file"]
    actual=(root/name).read_bytes()
    expected=bytes(((i*17+0xa9)&255) for i in range(8192))
    if actual!=expected: raise ValueError("console readback differs on host")
    result[name]=hashlib.sha256(actual).hexdigest()
    return {"passed":True,"sha256":result,"scope":"owned diagnostic files only"}

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("report",type=Path)
    p.add_argument("--out",type=Path)
    a=p.parse_args(); result=verify(a.report)
    if a.out:a.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result))
