#!/usr/bin/env python3
"""No proprietary inputs: validate startup control-transfer census bounds."""
import json
import struct
import unittest
from inspect_pops_startup_calls import (START, END, FUNCTION_END, scan_words,
                                         inspect, parse_function_metadata,
                                         annotate_ground_truth)


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

    def test_extended_original_function_extent_is_distinct(self):
        self.assertEqual(END - START, 524)
        self.assertEqual(FUNCTION_END - START, 1076)
        self.assertEqual((END - START) % 4, 0)
        self.assertEqual((FUNCTION_END - END) % 4, 0)

    def test_ground_truth_candidates_keep_overlaps_visible(self):
        rows = [
            {"name": "FUN_002004f0", "address": "002004f0", "size": 1076},
            {"name": "nested_overlap", "address": "00200500", "size": 16},
            {"name": "other", "address": "0022faf0", "size": 64},
        ]
        functions = parse_function_metadata(json.dumps(rows).encode())
        results = annotate_ground_truth([
            {"pc": "0x002004f0", "kind": "call", "target": "0x00200504"},
            {"pc": "0x002004f4", "kind": "call", "target": "0x0022faf0"},
            {"pc": "0x002004f8", "kind": "indirect-call"},
        ], functions)
        self.assertEqual(len(results[0]["ground_truth_candidates"]), 2)
        self.assertEqual(results[0]["ground_truth_candidates"][0]["name"], "FUN_002004f0")
        self.assertFalse(results[0]["ground_truth_candidates"][0]["at_entry"])
        self.assertEqual(results[1]["ground_truth_candidates"],
                         [{"name": "other", "offset": 0, "at_entry": True}])
        self.assertNotIn("ground_truth_candidates", results[2])

    def test_reject_broken_ground_truth_inventory(self):
        invalid = [
            {"name": "x", "address": "002004f0", "size": True},
            {"name": "x", "address": "002004f0", "size": 0},
            {"name": "x", "address": "002004fx", "size": 4},
            {"name": "x", "address": "ffffffff", "size": 8},
        ]
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(ValueError):
                parse_function_metadata(json.dumps([row]).encode())
        with self.assertRaises(ValueError):
            parse_function_metadata(b"{}")

    def test_sign_extended_conditional_call(self):
        blob = struct.pack("<I", 0x0431ffff)
        rec = scan_words(blob, START)
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0]["target"], f"0x{START:08x}")


if __name__ == "__main__":
    unittest.main()
