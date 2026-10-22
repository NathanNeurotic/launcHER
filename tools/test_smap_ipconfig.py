#!/usr/bin/env python3
"""Compile and execute the actual SMAP address parser on the host."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
compiler = os.environ.get("CC", "cc")
if not shutil.which(compiler):
    raise SystemExit("C compiler unavailable for SMAP parser regression")
with tempfile.TemporaryDirectory(prefix="launcher-smap-") as folder:
    output = Path(folder) / ("test_smap.exe" if os.name == "nt" else "test_smap")
    subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic",
                    "-I", str(root / "launcher/include"),
                    str(root / "tools/fixtures/test_smap_ipconfig.c"),
                    "-o", str(output)], check=True)
    subprocess.run([str(output)], check=True, timeout=15)
