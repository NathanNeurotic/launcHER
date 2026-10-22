#!/usr/bin/env python3
"""Compile the production IOP proxy with host API mocks and exercise contracts."""
import os
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
build = root / "build" / "pops-host" / "popfs"
build.mkdir(parents=True, exist_ok=True)
shutil.copyfile(root / "tools/fixtures/popfs_host_sdk.h", build / "popfs_host_sdk.h")
for header in ("irx.h", "iomanX.h", "sysclib.h", "intrman.h", "loadcore.h"):
    (build / header).write_text('#include "popfs_host_sdk.h"\n')
compiler = shutil.which(os.environ.get("CC", "gcc"))
if not compiler:
    raise RuntimeError("Host GCC-compatible compiler required")
output = build / ("test_popfs.exe" if os.name == "nt" else "test_popfs")
subprocess.run([compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-I", str(build),
                str(root / "tools/fixtures/test_popfs.c"), "-o", str(output)], check=True)
subprocess.run([str(output)], check=True)
