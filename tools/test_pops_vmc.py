#!/usr/bin/env python3
"""Exercise the production card writer with deterministic I/O failures."""
import os
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
build = root / 'build' / 'pops-host' / 'vmc'
build.mkdir(parents=True, exist_ok=True)
compiler = shutil.which(os.environ.get('CC', 'gcc'))
if not compiler:
    raise RuntimeError('Host GCC-compatible compiler required')
output = build / ('test_vmc.exe' if os.name == 'nt' else 'test_vmc')
subprocess.run([compiler, '-std=c99', '-Wall', '-Wextra', '-Werror',
                '-I', str(root / 'common/include'),
                str(root / 'tools/fixtures/test_pops_vmc.c'), '-o', str(output)], check=True)
subprocess.run([str(output)], check=True)
