#!/usr/bin/env python3
"""Compile the real SubQ bridge with host mocks and exercise its contracts."""
import os
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / "build" / "pops-host" / "subq-bridge"
out.mkdir(parents=True, exist_ok=True)
compiler = shutil.which(os.environ.get("CC", "gcc"))
if not compiler:
    raise RuntimeError("Host GCC-compatible compiler required")
binary = out / ("test_subq_bridge.exe" if os.name == "nt" else "test_subq_bridge")
subprocess.run([compiler, "-std=c99", "-Wall", "-Wextra", "-Werror",
                str(root / "tools" / "fixtures" / "test_subq_bridge.c"),
                str(root / "launcher" / "iop" / "pops_iomanx" / "src" / "pops_subq_bridge.c"),
                "-o", str(binary)], check=True)
subprocess.run([str(binary)], check=True)
