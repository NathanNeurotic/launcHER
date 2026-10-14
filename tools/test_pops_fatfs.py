#!/usr/bin/env python3
"""Execute production FatFs filesystem callbacks with injected API failures."""
import os
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
build = root / "build/pops-host/fatfs"
build.mkdir(parents=True, exist_ok=True)
for name in ("popfs_host_sdk.h", "fatfs_host_sdk.h"):
    shutil.copyfile(root / "tools/fixtures" / name, build / name)
shutil.copyfile(root / "tools/fixtures/fatfs_host_ff.h", build / "ff.h")
for name in ("iomanX.h", "sysclib.h", "sysmem.h", "thbase.h", "thsemap.h", "bdm.h", "usbhdfsd-common.h"):
    (build / name).write_text('#include "fatfs_host_sdk.h"\n')
compiler = shutil.which(os.environ.get("CC", "gcc"))
if not compiler:
    raise RuntimeError("Host GCC-compatible compiler required")
output = build / ("test_fatfs.exe" if os.name == "nt" else "test_fatfs")
subprocess.run([compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-I", str(build),
                "-I", str(root / "launcher/iop/pops_fatfs/src/include"),
                str(root / "tools/fixtures/test_fatfs.c"), "-o", str(output)], check=True)
subprocess.run([str(output)], check=True)
