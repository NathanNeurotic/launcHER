#!/usr/bin/env python3
"""Proprietary-input-free guards for the original-code execution tooling."""
import contextlib
import io
from pathlib import Path
import struct
import tempfile
import unittest

from prepare_pops_io_request_probe import RESERVED, prepare, segments, verify
from trace_original_pops_io import decode_main
from prepare_pops_iop_binding_probe import prepare as prepare_binding
from prepare_pops_trampoline_probe import verify as verify_trampoline


def elf(address=0x100000, file_size=4, memory_size=4):
    header = b"\x7fELF\x01\x01\x01" + bytes(9)
    header += struct.pack("<HHIIIIIHHHHHH", 2, 8, 1, address, 52, 0, 0,
                          52, 32, 1, 40, 0, 0)
    ph = struct.pack("<8I", 1, 84, address, address, file_size, memory_size, 5, 4)
    return header + ph + bytes(file_size)


class ProbeGuards(unittest.TestCase):
    def test_trampoline_parent_rejects_child_staging_and_bss_overlap(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "parent.elf"
            for address, memory in ((0xffffc, 4), (0x1ffffc, 8),
                                    (0x200000, 4), (0x1000000, 4)):
                path.write_bytes(elf(address, 4, memory))
                with self.assertRaisesRegex(ValueError, "parent load/BSS"):
                    verify_trampoline(path)
            for address, memory in ((0x100000, 4), (0x1ffffc, 4),
                                    (0x100000, 0x100000)):
                path.write_bytes(elf(address, 4, memory))
                verify_trampoline(path)

    def test_reject_unknown_binding_inputs_before_output(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            original, image, output = root / "unknown.elf", root / "unknown.img", root / "output"
            original.write_bytes(elf())
            image.write_bytes(bytes(64))
            with self.assertRaisesRegex(ValueError, "unrecognized selected Sony"):
                prepare_binding(original, image, root, output)
            self.assertFalse(output.exists())

    def test_reject_unknown_original_before_output(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            original, output = root / "unknown.elf", root / "output"
            original.write_bytes(elf())
            with self.assertRaisesRegex(ValueError, "unknown external POPS"):
                prepare(original, output)
            self.assertFalse(output.exists())
        for blob in (b"", b"\0" * 167700):
            with self.assertRaisesRegex(ValueError, "pinned POPSLoader MAIN"):
                decode_main(blob)

    def test_program_header_file_and_memory_bounds(self):
        valid = elf()
        self.assertEqual(segments(valid), [(84, 0x100000, 4, 4, 5)])
        for offset, value in ((28, 0xfffffff0), (56, 0xfffffff0),
                              (68, 0xffffffff), (72, 3), (60, 0xfffffffe)):
            damaged = bytearray(valid)
            struct.pack_into("<I", damaged, offset, value)
            with self.assertRaises(ValueError):
                segments(bytes(damaged))
        with self.assertRaises(ValueError):
            segments(valid[:-1])

    def test_full_load_and_bss_must_not_overlap_any_original_region(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "probe.elf"
            for low, high in RESERVED:
                # An overlap at either boundary, including BSS-only bytes,
                # must abort before a generated probe can overwrite itself.
                for start, files, memory in ((low, 4, 4), (high - 1, 1, 1),
                                              (low - 8, 4, 12)):
                    path.write_bytes(elf(start, files, memory))
                    with self.assertRaisesRegex(ValueError, "overlaps original"):
                        verify(path)
            path.write_bytes(elf())
            with contextlib.redirect_stdout(io.StringIO()):
                verify(path)


if __name__ == "__main__":
    unittest.main()
