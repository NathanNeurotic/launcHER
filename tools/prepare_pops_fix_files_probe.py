#!/usr/bin/env python3
"""Prepare a synthetic R5900 fix-staging probe without Sony/game/save inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def prepare(out):
    if out.exists() or not out.resolve().is_relative_to((ROOT / 'build').resolve()):
        raise ValueError('use a fresh ignored build directory')
    reference = json.loads((ROOT / 'tools/fixtures/pops_compat_reference.json').read_text())['writes']
    pristine = bytearray(0x302e60)
    for address, value, width in [(0x210318, 0x8f828228, 4), (0x21032c, 0x1443fffa, 4),
                                  (0x20083c, 0x0441000a, 4), (0x20085c, 0x1000fffa, 4),
                                  (0x20de9c, 0x0c0836ee, 4), (0x21af70, 0x64, 1),
                                  (0x2525b0, 0x1bfc, 2)]:
        pristine[address-0x200000:address-0x200000+width] = value.to_bytes(width, 'little')
    expected = []
    for first in (1, 2, 3, 4, 5, 7):
        row = []
        for second in (1, 2, 3, 4, 5, 7):
            data = bytearray(pristine)
            for mode in (first, second):
                for address, value, width in reference[str(mode)]:
                    data[address-0x200000:address-0x200000+width] = value.to_bytes(width, 'little')
            # Bounded comparison checksum, not a binary identity/security gate.
            checksum = 2166136261
            for byte in data:
                checksum = ((checksum ^ byte) * 16777619) & 0xffffffff
            row.append(checksum)
        expected.append(row)
    out.mkdir(parents=True)
    files = ['tools/fixtures/pops_fix_files_ee.c', 'common/src/pops_modes_patches.c',
             'common/src/pops_external.c', 'common/include/pops_modes_patches.h',
             'common/include/pops_config.h', 'common/include/pops_external.h']
    hashes = {}
    for filename in files:
        path = ROOT / filename
        shutil.copyfile(path, out / path.name)
        hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    header = 'static const uint32_t expected_fix_results[6][6]={\n'
    header += ',\n'.join('{' + ','.join(f'0x{value:08x}' for value in row) + '}' for row in expected)
    (out / 'expected_fix_results.h').write_text(header + '\n};\n')
    config = {'project': 'pops-fix-files-probe', 'targets': [{
        'name': 'pops_fix_files', 'type': 'ee',
        'sources': ['pops_fix_files_ee.c', 'pops_modes_patches.c', 'pops_external.c'],
        'include_dirs': ['.'], 'libs': ['kernel', 'debug'], 'debug': True, 'opt': '-O2'}]}
    (out / 'ps2.yaml').write_text(json.dumps(config, indent=2) + '\n')
    (out / 'provenance.json').write_text(json.dumps(hashes, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    prepare(parser.parse_args().out)
