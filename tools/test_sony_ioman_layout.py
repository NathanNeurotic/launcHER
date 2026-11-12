#!/usr/bin/env python3
"""Compile the real Sony-state migration helper with bounded synthetic memory."""
import os
from pathlib import Path
import shutil
import subprocess
root = Path(__file__).resolve().parents[1]
out = root / "build/pops-host/sony-ioman"
out.mkdir(parents=True, exist_ok=True)
compiler = shutil.which(os.environ.get("CC", "gcc"))
if not compiler:
    raise RuntimeError("Host GCC-compatible compiler required")
binary = out / ("test_layout.exe" if os.name == "nt" else "test_layout")
subprocess.run([compiler, "-std=c99", "-Wall", "-Wextra", "-Werror",
    str(root / "tools/fixtures/test_sony_ioman_layout.c"), "-o", str(binary)], check=True)
subprocess.run([str(binary)], check=True)
