#!/usr/bin/env python3
"""No proprietary inputs: validate startup control-transfer census bounds."""
import struct
import unittest
from inspect_pops_startup_calls import START, scan_words, inspect


def j(target, op=3):
    return (op << 26) | ((target >> 2) & 0x03ffffff)


class StartupTransferCensusTests(unittest.TestCase):
    def test_direct_calls_jump_and_indirect_unresolved(self):
        words = [j(0x22faf0), j(0x200700, 2), 0x0120f809,
                 0x04310001, 0, 0]
        blob = b"".join(struct.pack("<I", x) for x in words)
        got = scan_words(blob, START)
        self.assertEqual([v["kind"] for v in got],
                         ["call", "jump", "indirect-call", "conditional-call"])
        self.assertEqual(got[0]["target"], "0x0022faf0")
        self.assertEqual(got[1]["target"], "0x00200700")
        self.assertNotIn("target", got[2])
        self.assertEqual(got[3]["target"], f"0x{START + 16 + 4:08x}")

    def test_reject_unaligned_and_unknown_original(self):
        for origin, blob in ((START + 1, b"\0" * 4), (START, b"\0" * 3)):
            with self.assertRaisesRegex(ValueError, "word aligned"):
                scan_words(blob, origin)
        with self.assertRaisesRegex(ValueError, "unknown external"):
            inspect(bytes(512))
        self.assertEqual(scan_words(b"\x00\x00\x00\x00"), [])

    def test_sign_extended_conditional_call(self):
        blob = struct.pack("<I", 0x0431ffff)
        rec = scan_words(blob, START)
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0]["target"], f"0x{START:08x}")


if __name__ == "__main__":
    unittest.main()
