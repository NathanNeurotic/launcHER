#!/usr/bin/env python3
"""Original r13 OSD.BIN behavior, then launcHER's matching implementation.

Only synthetic files are constructed. Originals run under Unicorn with
modelled services; nothing here is a console run or emits reference bytes.
"""
import os
import random
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import trace_original_pops_osd as T  # noqa: E402
import trace_original_pops_user_bios as U  # noqa: E402

HAVE = bool(os.environ.get("POPSTARTER_TEST_ELF")) and bool(os.environ.get("POPS_TEST_ELF"))
if HAVE:
    try:
        import unicorn  # noqa: F401
    except Exception:
        HAVE = False


def rejection_cases():
    cases = []

    def add(name, data, reason):
        cases.append((name, data, reason))

    add("exe", T.make_osd(magic=b"PS-X EXE"), "NOT_FILE")
    add("foreign", T.make_osd(magic=b"NOT AN OSD"), "NOT_FILE")
    add("short-file", T.make_osd(body_size=3), "NOT_FILE")
    add("version-zero", T.make_osd(version=0), "NOT_FILE")
    add("version-three", T.make_osd(version=3), "VERSION")
    reserved = bytearray(T.make_osd())
    reserved[8] = 1
    add("reserved", bytes(reserved), "HEADER")
    add("load-low", T.make_osd(load=1), "LOAD")
    add("load-high-zero", T.make_osd(load=0), "LOAD")
    add("entry-low", T.make_osd(entry=1), "ENTRY")
    mismatch = bytearray(T.make_osd(body_size=16))
    struct.pack_into("<I", mismatch, 0x1C, 17)
    add("size-mismatch", bytes(mismatch), "SIZE")
    add("v1-too-big", T.make_osd(body_size=T.V1_CAP + 1), "TOO_BIG")
    add("v2-too-big", T.make_osd(version=2, body_size=T.V2_CAP + 1), "TOO_BIG")
    add("no-build", T.make_osd(build=0), "BUILD")
    add("no-label", T.make_osd(label=0), "LABEL")
    precedence = bytearray(T.make_osd(body_size=T.V1_CAP + 1, build=0))
    precedence[8] = 1
    add("first-reason", bytes(precedence), "HEADER")
    size_before_big = bytearray(T.make_osd(body_size=T.V1_CAP - 1))
    struct.pack_into("<I", size_before_big, 0x1C, T.V1_CAP)
    add("size-before-big", bytes(size_before_big), "SIZE")
    add("big-before-build", T.make_osd(body_size=T.V1_CAP + 1, build=0), "TOO_BIG")
    return cases


def seeded_cases(count=256):
    rng = random.Random(0x05D)
    out = []
    for _ in range(count):
        version = rng.choice((1, 2))
        data = bytearray(T.make_osd(version=version, body_size=rng.randrange(0, 65),
                                    seed=rng.randrange(256), modes=tuple(rng.randrange(10) for _ in range(4)),
                                    flag=rng.randrange(2) if version == 2 else 0))
        for _ in range(rng.randrange(4)):
            data[rng.randrange(len(data))] ^= 1 << rng.randrange(8)
        out.append(bytes(data))
    return out


class OsdTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = U.core_image()

    def probe(self, data, **kwargs):
        return T.run_osd(self.core, data=data, **kwargs)

    def body_reads(self, result):
        return [event for event in result["io"] if event[0] == "read" and event[1] == "body"]

    def assert_rejected(self, result, reason):
        self.assertEqual((result["ret"], result["reason"], result["core"]),
                         (0, reason, self.core))


@unittest.skipUnless(HAVE, "POPSTARTER_TEST_ELF, POPS_TEST_ELF and unicorn are needed")
class OriginalProbe(OsdTest):
    def test_valid_v1_v2_and_missing(self):
        for version, address, cap in ((1, T.V1_ADDR, T.V1_CAP), (2, T.V2_ADDR, T.V2_CAP)):
            for backend in (0, 1):
                with self.subTest(version=version, backend=backend):
                    data = T.make_osd(version=version, body_size=32)
                    result = self.probe(data, backend=backend)
                    self.assertEqual((result["ret"], result["reason"]), (1, None))
                    self.assertEqual(result["core"][address - U.CORE_BASE:address - U.CORE_BASE + 32], data[64:])
                    self.assertEqual(result["core"][address - U.CORE_BASE + 32:address - U.CORE_BASE + cap], bytes(cap - 32))
                    self.assertEqual(T.get(result["core"], 0x20079A, 2), 0x1000)
                    self.assertEqual(result["flags"]["osd_all_a"], 1)
                    self.assertEqual(result["flags"]["osd_all_b"], 1)
                    self.assertEqual(result["flags"]["osd_game_a"], 0)
                    self.assertEqual(result["flags"]["osd_game_b"], 0)
        result = self.probe(None)
        self.assertEqual((result["ret"], result["core"]), (1, self.core))

    def test_every_rejection_reason_and_precedence(self):
        for name, data, reason in rejection_cases():
            with self.subTest(name=name):
                self.assert_rejected(self.probe(data), reason)

    def test_size_cap_and_extra_read_boundaries(self):
        for version, cap in ((1, T.V1_CAP), (2, T.V2_CAP)):
            for backend in (0, 1):
                for size in (3, 4, 15, 16, 17, cap - 17, cap - 16, cap - 15, cap):
                    with self.subTest(version=version, backend=backend, size=size):
                        result = self.probe(T.make_osd(version=version, body_size=size), backend=backend)
                        expected_ret = 0 if size == 3 else 1
                        self.assertEqual(result["ret"], expected_ret)
                        if size == 3:
                            self.assertEqual(result["reason"], "NOT_FILE")
                            self.assertEqual(self.body_reads(result), [])
                            continue
                        expected = size + 16 if size <= cap - 16 and size & 0xF else size
                        self.assertEqual(self.body_reads(result), [("read", "body", expected, size)])

    def test_short_and_failed_reads(self):
        data = T.make_osd(body_size=31)
        result = self.probe(data, read_faults={"body": 1})
        self.assertEqual(result["ret"], 1)
        self.assertEqual(result["core"][T.V1_ADDR - U.CORE_BASE], data[64])
        self.assertEqual(result["core"][T.V1_ADDR - U.CORE_BASE + 1:T.V1_ADDR - U.CORE_BASE + T.V1_CAP],
                         bytes(T.V1_CAP - 1))
        result = self.probe(data, read_faults={"body": -5})
        self.assertEqual(result["ret"], 1)
        self.assertEqual(result["core"][T.V1_ADDR - U.CORE_BASE:T.V1_ADDR - U.CORE_BASE + T.V1_CAP],
                         bytes(T.V1_CAP))
        result = self.probe(data, read_faults={"header": 64})
        self.assertEqual(result["ret"], 1)
        result = self.probe(data, read_faults={"header": -5})
        self.assert_rejected(result, "NOT_FILE")

    def test_v2_immediate_words_and_flag(self):
        for flag, final in ((0, 0x01C0F809), (1, 0x01C00008)):
            result = self.probe(T.make_osd(version=2, body_size=16, flag=flag))
            self.assertEqual(result["ret"], 1)
            self.assertEqual(T.get(result["core"], 0x252C34, 4), 0x0FF00648)
            self.assertEqual(T.get(result["core"], 0x252C38, 4), 0x0FF00AD4)
            self.assertEqual(T.get(result["core"], 0x252C48, 4), final)

    def test_modes_no_fix_and_osd_off(self):
        result = self.probe(T.make_osd(modes=(1, 2, 3, 5)), flags={"no_fix": 1})
        self.assertEqual(result["ret"], 1)
        for address, width in ((0x210314, 4), (0x20083C, 4), (0x20085C, 4)):
            self.assertEqual(T.get(result["core"], address, width), T.get(self.core, address, width))
        result = self.probe(T.make_osd(modes=(4, 7, 8, 255)))
        self.assertEqual(result["ret"], 1)
        self.assertEqual(T.get(result["core"], 0x21AF70, 1), 0)
        self.assertEqual(T.get(result["core"], 0x21E45C, 1), 0x40)
        result = self.probe(T.make_osd(modes=(6,)), flags={"osd_off": 1})
        self.assertEqual(result["ret"], 1)
        self.assertEqual((T.get(result["core"], 0x2525B0, 2), result["flags"]["osd_off"]), (0x0648, 1))
        result = self.probe(T.make_osd(), flags={"osd_off": 1})
        self.assertEqual(result["ret"], 1)
        self.assertEqual((T.get(result["core"], 0x2525B0, 2), result["flags"]["osd_off"]), (0x1BFC, 0))

    def test_mixed_v2_then_v1_scopes(self):
        root = self.probe(T.make_osd(version=2, body_size=64, seed=1), scope=0)
        self.assertEqual(root["ret"], 1)
        result = T.run_osd(root["core"], scope=1, data=T.make_osd(version=1, body_size=32, seed=2),
                           flags=root["flags"])
        self.assertEqual(result["ret"], 1)
        self.assertEqual(result["core"][T.V2_ADDR - U.CORE_BASE:T.V1_ADDR - U.CORE_BASE], root["core"][T.V2_ADDR - U.CORE_BASE:T.V1_ADDR - U.CORE_BASE])
        self.assertEqual(result["flags"]["osd_all_b"], 1)
        self.assertEqual(result["flags"]["osd_game_a"], 1)
        self.assertEqual(result["flags"]["osd_game_b"], 1)

    def test_entry_gates(self):
        data = T.make_osd()
        result = self.probe(data, flags={"integrity": 0})
        self.assertEqual((result["ret"], result["core"]), (0, self.core))
        self.assertFalse(any(event[0] == "open" for event in result["io"]))
        result = self.probe(data, flags={"abort": 1})
        self.assertEqual((result["ret"], result["core"]), (0, self.core))
        result = self.probe(data, scope=1, game_dir_ok=False)
        self.assertEqual((result["ret"], result["core"]), (-666, self.core))
        self.assertEqual(result["flags"]["game_dir_missing"], 1)

    def test_seeded_cases(self):
        for index, data in enumerate(seeded_cases()):
            with self.subTest(index=index):
                result = self.probe(data)
                self.assertIn(result["ret"], (0, 1))
                if result["ret"] == 0:
                    self.assertEqual(result["core"], self.core)


class Fixtures(unittest.TestCase):
    def test_synthetic_files(self):
        for version in (1, 2):
            data = T.make_osd(version=version, body_size=17)
            self.assertEqual(len(data), 81)
            self.assertEqual(data[:8], b"PS-X OSD")
            self.assertEqual(struct.unpack_from("<I", data, 0x1C)[0], 17)

    def test_ci_runs_this_file(self):
        workflow = (ROOT / ".github/workflows/build.yml").read_text()
        self.assertIn("run: python tools/test_pops_osd.py", workflow)


if __name__ == "__main__":
    unittest.main()
