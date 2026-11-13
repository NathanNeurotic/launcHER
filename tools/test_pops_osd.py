#!/usr/bin/env python3
"""Original r13 OSD.BIN behavior, then launcHER's matching implementation.

Only synthetic files are constructed. Originals run under Unicorn with
modelled services; nothing here is a console run or emits reference bytes.
"""
import ctypes as c
import errno
import mmap
import os
import random
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import trace_original_pops_osd as T  # noqa: E402
import trace_original_pops_user_bios as U  # noqa: E402
import test_pops_user_bios as B  # noqa: E402

HAVE = bool(os.environ.get("POPSTARTER_TEST_ELF")) and bool(os.environ.get("POPS_TEST_ELF"))
if HAVE:
    try:
        import unicorn  # noqa: F401
    except Exception:
        HAVE = False


def path_key(path):
    return os.path.normcase(os.path.normpath(os.fsdecode(path)))


ROM_FIELDS = ("bios_all", "bios_game", "osd_all_a", "osd_all_b", "osd_game_a", "osd_game_b",
              "osd_off", "integrity", "no_fix", "abort", "game_dir_missing")
REASON_NAMES = {0: None, 2: "NOT_FILE", 3: "VERSION", 4: "HEADER", 5: "LOAD", 6: "ENTRY",
                7: "SIZE", 8: "TOO_BIG", 9: "BUILD", 10: "LABEL"}
REASON_CODES = {name: code for code, name in REASON_NAMES.items() if name is not None}


class Plan(c.Structure):
    _fields_ = [("header", c.c_uint8 * 64), ("file_size", c.c_int64),
                ("body_size", c.c_uint32), ("body_request", c.c_uint32),
                ("body_address", c.c_uint32), ("body_capacity", c.c_uint32)]


class Rom(c.Structure):
    _fields_ = [(name, c.c_uint8) for name in ROM_FIELDS]


_LIB = None


def library():
    global _LIB
    if _LIB is None:
        _LIB = B.LIB
        _LIB.pops_osd_plan.argtypes = [c.c_void_p, c.c_size_t, c.c_int64, c.POINTER(Plan)]
        _LIB.pops_osd_plan.restype = c.c_int
        _LIB.pops_osd_stage.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(Plan), c.c_void_p,
                                        c.c_size_t, c.c_int, c.POINTER(Rom)]
        _LIB.pops_osd_stage.restype = c.c_int
        _LIB.pops_user_osd_skipped.argtypes = [c.c_int, c.POINTER(Rom)]
        _LIB.pops_user_osd_skipped.restype = c.c_int
        _LIB.pops_fix_context_osd_loaded.argtypes = [c.POINTER(B.Context), c.c_void_p, c.c_size_t,
                                                     c.POINTER(Plan), c.POINTER(Rom)]
        _LIB.pops_fix_context_osd_loaded.restype = c.c_int
    return _LIB


def buf(data):
    return (c.c_uint8 * len(data)).from_buffer(data)


def state_dict(state):
    return {name: getattr(state, name) for name in ROM_FIELDS}


def stage_file(core, data, scope=0, flags=None, body_read=None):
    lib = library()
    after = bytearray(core)
    state = Rom(**{name: (flags or {}).get(name, 0) for name in ROM_FIELDS})
    if not flags or "integrity" not in flags:
        state.integrity = 1
    header = bytearray(80)
    header[:min(len(data), 80)] = data[:80]
    plan = Plan()
    rc = lib.pops_osd_plan(buf(header), len(header), len(data), c.byref(plan))
    if rc:
        return {"ret": 0, "reason": REASON_NAMES[rc], "core": after, "flags": state_dict(state),
                "plan": plan, "rc": rc}
    body = bytearray(data[64:])
    if body_read is None:
        body_read = len(body)
    if body_read < 0:
        body, body_read = bytearray(), 0
    rc = lib.pops_osd_stage(buf(after), len(after), c.byref(plan), buf(body), body_read,
                            scope, c.byref(state))
    return {"ret": rc, "reason": None, "core": after, "flags": state_dict(state), "plan": plan, "rc": 0}


class Event(c.Structure):
    _fields_ = [("kind", c.c_int), ("fd", c.c_int), ("a", c.c_longlong),
                ("b", c.c_longlong), ("result", c.c_longlong), ("path", c.c_char * 1024)]


_READER = {}
OSD_IO_C = r'''
typedef struct {
  int kind, fd;
  long long a, b, result;
  char path[1024];
} OsdEvent;
static OsdEvent osd_events[64];
static unsigned osd_event_count, osd_limit_read, osd_limit;
static int osd_fail_read;
static void osd_event(int kind, int fd, long long a, long long b, long long result,
                      const char *path) {
  OsdEvent *event;
  if (osd_event_count >= 64) return;
  event = &osd_events[osd_event_count++];
  memset(event, 0, sizeof(*event));
  event->kind = kind; event->fd = fd; event->a = a; event->b = b; event->result = result;
  if (path) snprintf(event->path, sizeof(event->path), "%%s", path);
}
static int test_open(const char *path, int flags) {
  size_t length = strlen(path);
  if (length >= 7 && !strcmp(path + length - 7, "OSD.BIN")) {
    ++bios_opens;
    if (on_bios_open) on_bios_open(path, bios_opens);
  }
  int fd = test_open_original(path, flags);
  osd_event(1, fd, flags, 0, fd, path);
  return fd;
}
static off_t test_lseek(int fd, off_t offset, int whence) {
  off_t result = test_lseek_original(fd, offset, whence);
  osd_event(2, fd, offset, whence, result, NULL);
  return result;
}
static ssize_t test_read(int fd, void *buffer, size_t size) {
  unsigned previous_limit = read_limit;
  int previous_fails = read_fails;
  ssize_t result;
  if (osd_fail_read && osd_fail_read == reads + 1) read_fails = 1;
  if (osd_limit_read == (unsigned)(reads + 1)) read_limit = osd_limit;
  if (osd_limit_read == (unsigned)(reads + 1) && !osd_limit && !read_fails) {
    ++reads;
    osd_event(3, fd, size, 0, 0, NULL);
    read_fails = previous_fails;
    read_limit = previous_limit;
    return 0;
  }
  result = test_read_original(fd, buffer, size);
  read_fails = previous_fails;
  read_limit = previous_limit;
  osd_event(3, fd, size, 0, result, NULL);
  return result;
}
static int test_close(int fd) {
  int result = test_close_original(fd);
  osd_event(4, fd, 0, 0, result, NULL);
  return result;
}
void test_osd_read_rule(int fail, unsigned which, unsigned limit) {
  osd_fail_read = fail < 0 ? (int)which : fail;
  osd_limit_read = which; osd_limit = limit;
}
int test_osd_event(unsigned index, OsdEvent *out) {
  if (!out) return -1;
  if (index >= osd_event_count) return 0;
  *out = osd_events[index];
  return 1;
}
'''


def reader_library():
    if "lib" not in _READER:
        wrapper = B.READER_WRAPPER
        for name in ("open", "lseek", "read", "close"):
            wrapper = wrapper.replace("static int test_%s(" % name if name in ("open", "close") else
                                      "static off_t test_lseek(" if name == "lseek" else
                                      "static ssize_t test_read(",
                                      ("static int test_%s_original(" % name) if name in ("open", "close") else
                                      "static off_t test_lseek_original(" if name == "lseek" else
                                      "static ssize_t test_read_original(")
        wrapper = wrapper.replace("#define open test_open", OSD_IO_C + "\n#define open test_open")
        wrapper = wrapper.replace("opens = reads = closes = bios_opens = 0; bytes_read = 0;",
                                  "opens = reads = closes = bios_opens = 0; bytes_read = 0;\n"
                                  "  osd_event_count = osd_fail_read = osd_limit_read = 0; osd_limit = 0;")
        B.READER_WRAPPER = wrapper
        _READER["lib"] = B.reader_library()
        lib = _READER["lib"]
        lib.test_osd_load.argtypes = [c.c_void_p, c.c_size_t, c.c_char_p, c.c_int,
                                      c.POINTER(Rom), c.POINTER(Plan)]
        lib.test_osd_load.restype = c.c_int
        lib.test_osd_read_rule.argtypes = [c.c_int, c.c_uint, c.c_uint]
        lib.test_osd_read_rule.restype = None
        lib.test_osd_event.argtypes = [c.c_uint, c.POINTER(Event)]
        lib.test_osd_event.restype = c.c_int
    return _READER["lib"]


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

    def test_root_patch_mode6_before_game_osd(self):
        core, flags, _ = U.mode(self.core, 6)
        result = T.run_osd(core, scope=1, data=T.make_osd(), flags=flags)
        self.assertEqual(result["ret"], 1)
        self.assertEqual(T.get(result["core"], 0x2525B0, 2), 0x1BFC)
        self.assertEqual(result["flags"]["osd_off"], 0)

    def test_bios_state_precedes_header_mode6(self):
        core = bytearray(self.core)
        B.put(core, 0x2525B0, 0x8956, 2)
        for off, expected in ((0, 0x8956), (1, 0x1BFC)):
            with self.subTest(off=off):
                result = T.run_osd(core, scope=1, data=T.make_osd(modes=(6,)),
                                   flags={"bios_all": 1, "osd_off": off})
                self.assertEqual(result["ret"], 1)
                self.assertEqual(T.get(result["core"], 0x2525B0, 2), expected)
                self.assertEqual(result["flags"]["osd_off"], 0)

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


class Guard(unittest.TestCase):
    def refresh(self, context, core, plan, state=None):
        state = Rom(integrity=1) if state is None else state
        return library().pops_fix_context_osd_loaded(c.byref(context), B.buf(core), len(core),
                                                     c.byref(plan), c.byref(state))

    def test_refresh_accepts_only_the_validated_osd_writes(self):
        lib = library()
        core = B.pristine_sites()
        context = B.Context()
        self.assertEqual(lib.pops_fix_context_init_builtin(c.byref(context), B.buf(core), B.SIZE,
                                                          0, 0, 0), 0)
        pal = list(context.video_expected)
        resident = (context.resident_entry, list(context.resident_expected), context.progressive_set)
        staged = stage_file(core, T.make_osd(modes=(4,)), flags={"integrity": 1})
        self.assertEqual(staged["ret"], 1)
        core = staged["core"]
        blob = B.patch((1,))
        self.assertEqual(lib.pops_fix_stage(c.byref(context), B.buf(core), B.SIZE,
                                            blob, len(blob), 1, 0), -errno.EINVAL)
        self.assertEqual(self.refresh(context, core, staged["plan"]), 0)
        self.assertEqual(list(context.video_expected), pal)
        self.assertEqual((context.resident_entry, list(context.resident_expected), context.progressive_set), resident)
        self.assertEqual(lib.pops_fix_stage(c.byref(context), B.buf(core), B.SIZE,
                                            blob, len(blob), 1, 0), 0)
        other = B.patch((2,), slot=2)
        self.assertEqual(lib.pops_fix_stage(c.byref(context), B.buf(core), B.SIZE,
                                            other, len(other), 2, 0), 0)
        core[0x210318 - U.CORE_BASE] ^= 1
        before = bytes(context)
        self.assertEqual(self.refresh(context, core, staged["plan"]), -errno.EINVAL)
        self.assertEqual(bytes(context), before)
        self.assertEqual(lib.pops_fix_stage(c.byref(context), B.buf(core), B.SIZE,
                                            other, len(other), 2, 0), -errno.EINVAL)
        core[0x21AF94 - U.CORE_BASE] ^= 1
        self.assertEqual(self.refresh(context, core, staged["plan"]), -errno.EINVAL)
        self.assertEqual(bytes(context), before)


class GuardShortCore(unittest.TestCase):
    def test_preflight_happens_before_any_compatibility_read(self):
        if os.environ.get("POPS_OSD_SHORT_CORE_CHILD") != "1":
            env = os.environ.copy()
            env["POPS_OSD_SHORT_CORE_CHILD"] = "1"
            isolated = Path(tempfile.gettempdir()) / ("pops_osd_short_core_%d" % os.getpid())
            isolated = isolated.with_suffix(".dll" if os.name == "nt" else ".so")
            env["POPS_TEST_HOST_LIBRARY"] = str(isolated)
            try:
                result = subprocess.run([sys.executable, str(Path(__file__)), "GuardShortCore"],
                                        cwd=ROOT, env=env, capture_output=True, text=True)
            finally:
                isolated.unlink(missing_ok=True)
            self.assertEqual(result.returncode, 0,
                             "short-core child failed (the old code reads into the guard page):\n" +
                             result.stdout[-2000:] + result.stderr[-2000:])
            return
        lib = library()
        full = B.pristine_sites()
        context = B.Context()
        self.assertEqual(lib.pops_fix_context_init_builtin(c.byref(context), B.buf(full), B.SIZE,
                                                          0, 0, 0), 0)
        before = bytes(context)
        header = bytearray(80)
        header[:80] = T.make_osd()[:80]
        plan = Plan()
        self.assertEqual(lib.pops_osd_plan(buf(header), len(header), 80, c.byref(plan)), 0)
        page = mmap.PAGESIZE
        memory = mmap.mmap(-1, page + 0x52600)
        self.addCleanup(memory.close)
        memory[page - 32:page] = b"\xA5" * 32
        address = c.addressof(c.c_char.from_buffer(memory))
        core = address + page - 32
        if os.name == "nt":
            old = c.c_uint32()
            protect = c.windll.kernel32.VirtualProtect
            protect.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32, c.POINTER(c.c_uint32)]
            protect.restype = c.c_int
            self.assertNotEqual(protect(address + page, len(memory) - page, 1, c.byref(old)), 0)
        else:
            self.assertEqual(c.CDLL(None).mprotect(c.c_void_p(address + page), len(memory) - page, 0), 0)
        state = Rom(integrity=1)
        self.assertEqual(lib.pops_fix_context_osd_loaded(c.byref(context), core, 32,
                                                         c.byref(plan), c.byref(state)), -errno.ERANGE)
        self.assertEqual(bytes(context), before)
        self.assertEqual(c.string_at(core, 32), b"\xA5" * 32)


class Launch(OsdTest):
    @classmethod
    def setUpClass(cls):
        cls.lib = reader_library()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "GAME").mkdir()
        self.core = U.core_image() if HAVE else B.pristine_sites()

    def put(self, data, scope=0):
        folder = self.root / "GAME" if scope else self.root
        path = folder / "OSD.BIN"
        if data is None:
            if path.exists():
                path.unlink()
        else:
            path.write_bytes(data)

    def events(self):
        out = []
        for index in range(64):
            event = Event()
            if self.lib.test_osd_event(index, c.byref(event)) != 1:
                break
            out.append(event)
        return out

    def launch(self, lines=(), builtin=0, modes=0, state=None, context=None, builtin6=False):
        self.core = U.core_image() if HAVE else B.pristine_sites()
        if builtin6:
            builtin = B.mode_6_entry()
            modes = self.lib.test_builtin(builtin, B.buf(self.core), len(self.core))
            self.assertEqual(modes & 0x20, 0x20)
            self.assertEqual(T.get(self.core, 0x2525B0, 2), 0x0648)
        self.lib.test_io(0, 0, 0, 0, 0)
        cfg = B.config(*lines)
        if state is None:
            state = B.rom(**{name: 0xFF for name in ROM_FIELDS})
        rc = self.lib.test_launch(B.buf(self.core), len(self.core), os.fsencode(str(self.root) + "/"),
                                  os.fsencode(str(self.root / "GAME") + "/"), builtin, modes,
                                  c.byref(cfg), None, 0, c.byref(state),
                                  None if context is None else c.byref(context))
        return rc, state_dict(state)

    def launch_builtin6(self, lines=()):
        return self.launch(lines=lines, builtin6=True)

    def osd_opens(self):
        return [path_key(event.path) for event in self.events()
                if event.kind == 1 and event.path.endswith(b"OSD.BIN")]

    def test_root_game_order_state_and_residue(self):
        self.put(T.make_osd(version=2, body_size=64, seed=1), scope=0)
        self.put(T.make_osd(version=1, body_size=32, seed=2), scope=1)
        rc, flags = self.launch()
        self.assertEqual(rc, 0)
        self.assertEqual((flags["osd_all_a"], flags["osd_all_b"], flags["osd_game_a"],
                          flags["osd_game_b"], flags["bios_all"], flags["bios_game"],
                          flags["integrity"], flags["osd_off"]), (1, 1, 1, 1, 0, 0, 1, 0))
        expected = [self.root / "OSD.BIN", self.root / "GAME" / "OSD.BIN",
                    self.root / "OSD.BIN", self.root / "GAME" / "OSD.BIN"]
        self.assertEqual(self.osd_opens(), [path_key(path) for path in expected])
        root_body = T.make_osd(version=2, body_size=64, seed=1)[64:]
        self.assertEqual(self.core[T.V2_ADDR - U.CORE_BASE:T.V1_ADDR - U.CORE_BASE],
                         root_body + bytes(T.V1_ADDR - T.V2_ADDR - len(root_body)))
        self.assertEqual(self.core[T.V1_ADDR - U.CORE_BASE:T.V1_ADDR - U.CORE_BASE + 32],
                         T.make_osd(version=1, body_size=32, seed=2)[64:])

    def test_commands_see_osd_state_and_no_fix(self):
        self.put(T.make_osd(modes=(6,)), scope=0)
        rc, flags = self.launch((b"$UNDO_GAME_FIXES",))
        self.assertEqual(rc, 0)
        self.assertEqual((T.get(self.core, 0x2525B0, 2), flags["osd_off"]), (0x0648, 1))
        self.put(T.make_osd(modes=(1, 2, 3, 5)), scope=0)
        self.put(T.make_osd(modes=(4, 7)), scope=1)
        rc, flags = self.launch(modes=0x80)
        self.assertEqual(rc, 0)
        self.assertEqual(flags["no_fix"], 1)
        self.assertEqual(T.get(self.core, 0x210314, 4), T.get(B.pristine_sites(), 0x210314, 4))
        self.assertEqual(T.get(self.core, 0x20083C, 4), T.get(B.pristine_sites(), 0x20083C, 4))
        self.assertEqual(T.get(self.core, 0x21AF70, 1), 0)
        self.assertEqual(T.get(self.core, 0x21E45C, 1), 0x40)

    def test_builtin_mode6_osd_restores_before_each_scope(self):
        for scope in (0, 1):
            with self.subTest(scope=scope):
                self.put(None, scope=0)
                self.put(None, scope=1)
                self.put(T.make_osd(), scope=scope)
                rc, flags = self.launch_builtin6()
                self.assertEqual(rc, 0)
                self.assertEqual(T.get(self.core, 0x2525B0, 2), 0x1BFC)
                self.assertEqual(flags["osd_off"], 0)

    def test_sequential_mode6_and_post_command_state(self):
        cases = (
            ((6,), (), (), 0x1BFC, 0),
            ((), (6,), (), 0x0648, 1),
            ((6,), (6,), (), 0x0648, 1),
            ((), None, (B.MODE_6_LINE,), 0x1BFC, 1),
            ((6,), (), (B.MODE_6_LINE,), 0x1BFC, 1),
        )
        for root_modes, game_modes, lines, word, off in cases:
            with self.subTest(root=root_modes, game=game_modes, lines=lines):
                self.put(None if root_modes is None else T.make_osd(modes=root_modes), scope=0)
                self.put(None if game_modes is None else T.make_osd(modes=game_modes), scope=1)
                rc, flags = self.launch_builtin6(lines)
                self.assertEqual(rc, 0)
                self.assertEqual(T.get(self.core, 0x2525B0, 2), word)
                self.assertEqual(flags["osd_off"], off)

    def test_game_osd_sees_the_root_bios_state(self):
        bios = B.bios_file(B.ROM_MIN, 2)
        user_word = T.get(bios, 0x2525B0 - B.ROM + B.BASE, 2)
        for builtin6, expected, off in ((0, user_word, 0), (1, 0x1BFC, 0)):
            with self.subTest(builtin6=builtin6):
                self.put(None, scope=0)
                self.put(T.make_osd(modes=(6,)), scope=1)
                (self.root / "BIOS.BIN").write_bytes(bios)
                rc, flags = self.launch_builtin6() if builtin6 else self.launch()
                self.assertEqual(rc, 0)
                self.assertEqual(T.get(self.core, 0x2525B0, 2), expected)
                self.assertEqual(flags["osd_off"], off)
                self.assertEqual(flags["bios_all"], 1)

    def test_root_patch_mode6_feeds_game_osd(self):
        for with_bios in (False, True):
            with self.subTest(game_bios=with_bios):
                self.put(None, scope=0)
                self.put(T.make_osd(), scope=1)
                (self.root / "PATCH_3.BIN").write_bytes(B.patch_file(3, modes=(6,)))
                if with_bios:
                    (self.root / "GAME" / "BIOS.BIN").write_bytes(B.bios_file(B.ROM_MIN, 2))
                rc, flags = self.launch()
                self.assertEqual(rc, 0)
                self.assertEqual(T.get(self.core, 0x2525B0, 2), 0x1BFC)
                self.assertEqual(flags["osd_off"], 0)
                self.assertEqual(flags["bios_game"], 0)

    def test_changed_files_between_probe_and_load(self):
        original = T.make_osd(body_size=31, seed=1)
        for replacement in (T.make_osd(body_size=47, seed=2), None):
            with self.subTest(replacement=None if replacement is None else len(replacement)):
                self.put(original, scope=0)
                self.put(None, scope=1)
                counts = {}

                def change(path, _number):
                    name = path_key(path)
                    counts[name] = counts.get(name, 0) + 1
                    if name == path_key(self.root / "OSD.BIN") and counts[name] == 2:
                        self.put(replacement, scope=0)

                hook = B.BIOS_OPEN_HOOK(change)
                self.addCleanup(lambda: self.lib.test_on_bios_open(None))
                self.lib.test_on_bios_open(c.cast(hook, c.c_void_p))
                rc, flags = self.launch()
                self.assertEqual(rc, -errno.EIO)
        self.put(original, scope=0)
        counts = {}

        def same_plan(path, _number):
            name = path_key(path)
            counts[name] = counts.get(name, 0) + 1
            if name == path_key(self.root / "OSD.BIN") and counts[name] == 2:
                self.put(T.make_osd(body_size=31, seed=2), scope=0)

        hook = B.BIOS_OPEN_HOOK(same_plan)
        self.addCleanup(lambda: self.lib.test_on_bios_open(None))
        self.lib.test_on_bios_open(c.cast(hook, c.c_void_p))
        rc, flags = self.launch()
        self.assertEqual(rc, 0)


class Reader(OsdTest):
    @classmethod
    def setUpClass(cls):
        cls.lib = reader_library()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "GAME").mkdir()
        self.core = U.core_image() if HAVE else B.pristine_sites()

    def put(self, data, scope=0):
        folder = self.root / "GAME" if scope else self.root
        path = folder / "OSD.BIN"
        if data is None:
            if path.exists():
                path.unlink()
        else:
            path.write_bytes(data)

    def load(self, data, scope=0, flags=None, probe=False, read_rule=None):
        self.put(data, scope)
        self.lib.test_io(0, 0, 0, 0, 0)
        if read_rule:
            self.lib.test_osd_read_rule(*read_rule)
        core = bytearray(self.core)
        state = Rom(**{name: (flags or {}).get(name, 0) for name in ROM_FIELDS})
        if not flags or "integrity" not in flags:
            state.integrity = 1
        plan = Plan()
        folder = self.root / "GAME" if scope else self.root
        rc = self.lib.test_osd_load(None if probe else buf(core), 0 if probe else len(core),
                                    os.fsencode(str(folder) + "/"), scope, c.byref(state), c.byref(plan))
        return {"ret": rc, "core": core, "flags": state_dict(state), "plan": plan}

    def events(self):
        out = []
        for index in range(64):
            event = Event()
            if self.lib.test_osd_event(index, c.byref(event)) != 1:
                break
            out.append(event)
        return out

    def test_valid_read_sequence_and_state_probe(self):
        for version, address, cap in ((1, T.V1_ADDR, T.V1_CAP), (2, T.V2_ADDR, T.V2_CAP)):
            for size in (16, 17):
                with self.subTest(version=version, size=size):
                    data = T.make_osd(version=version, body_size=size)
                    result = self.load(data)
                    self.assertEqual(result["ret"], 1)
                    self.assertEqual(result["core"][address - U.CORE_BASE:address - U.CORE_BASE + size], data[64:])
                    self.assertEqual(result["core"][address - U.CORE_BASE + size:address - U.CORE_BASE + cap],
                                     bytes(cap - size))
                    self.assertEqual(result["flags"]["osd_all_a"], 1)
                    self.assertEqual(result["flags"]["osd_all_b"], 1)
                    events = self.events()
                    self.assertEqual([event.kind for event in events], [1, 2, 2, 3, 2, 3, 4])
                    expected = size + 16 if size & 0xF else size
                    self.assertEqual([event.a for event in events if event.kind == 3], [80, expected])
                    self.assertEqual([(event.a, event.b) for event in events if event.kind == 2],
                                     [(0, 2), (0, 0), (64, 0)])
                    probe = self.load(data, probe=True)
                    self.assertEqual(probe["ret"], 1)
                    self.assertEqual(probe["flags"], result["flags"])
                    self.assertEqual(probe["core"], self.core)
                    self.assertEqual([event.a for event in self.events() if event.kind == 3], [80])

    def test_missing_gates_and_rejections(self):
        result = self.load(None)
        self.assertEqual((result["ret"], result["core"]), (0, self.core))
        self.assertEqual([event.kind for event in self.events()], [1])
        for flags, expected in (({"integrity": 0}, 0), ({"abort": 1}, 0),
                                ({"game_dir_missing": 1}, -666)):
            result = self.load(T.make_osd(), scope=1, flags=flags)
            self.assertEqual((result["ret"], result["core"]), (expected, self.core))
            self.assertEqual(self.events(), [])
        for name, data, reason in rejection_cases():
            with self.subTest(name=name):
                result = self.load(data)
                self.assertEqual((result["ret"], result["core"]), (REASON_CODES[reason], self.core))
                events = self.events()
                self.assertEqual([event.kind for event in events], [1, 2, 2, 3, 2, 4])
                self.assertEqual(events[-2].a, 64)
                self.assertEqual(len([event for event in events if event.kind == 3]), 1)

    def test_short_and_failed_reads(self):
        data = T.make_osd(body_size=31)
        result = self.load(data, read_rule=(0, 2, 1))
        self.assertEqual(result["ret"], 1)
        self.assertEqual(result["core"][T.V1_ADDR - U.CORE_BASE], data[64])
        self.assertEqual(result["core"][T.V1_ADDR - U.CORE_BASE + 1:T.V1_ADDR - U.CORE_BASE + T.V1_CAP],
                         bytes(T.V1_CAP - 1))
        result = self.load(data, read_rule=(-5, 2, 0))
        self.assertEqual(result["ret"], 1)
        self.assertEqual(result["core"][T.V1_ADDR - U.CORE_BASE:T.V1_ADDR - U.CORE_BASE + T.V1_CAP],
                         bytes(T.V1_CAP))
        result = self.load(data, read_rule=(0, 1, 64))
        self.assertEqual(result["ret"], 1)
        result = self.load(data, read_rule=(-5, 1, 0))
        self.assertEqual((result["ret"], result["core"]), (REASON_CODES["NOT_FILE"], self.core))

    def test_long_path_is_a_safe_known_difference(self):
        state = Rom(integrity=1)
        plan = Plan()
        core = bytearray(self.core)
        rc = self.lib.test_osd_load(buf(core), len(core), b"x" * 1016 + b"/", 0,
                                    c.byref(state), c.byref(plan))
        self.assertEqual(rc, -errno.ENAMETOOLONG)
        self.assertEqual(core, self.core)

    @unittest.skipUnless(HAVE, "original inputs and unicorn are needed")
    def test_original_reader_differential(self):
        for version in (1, 2):
            for backend in (0, 1):
                for fault in (None, 1, 0, -5):
                    with self.subTest(version=version, backend=backend, fault=fault):
                        data = T.make_osd(version=version, body_size=31)
                        original = self.probe(data, backend=backend,
                                              read_faults={} if fault is None else {"body": fault})
                        rule = None if fault is None else ((-5 if fault < 0 else 0), 2, max(fault, 0))
                        actual = self.load(data, read_rule=rule)
                        self.assertEqual(actual["ret"], original["ret"])
                        self.assertEqual(actual["core"], original["core"])
                        for name in ROM_FIELDS:
                            self.assertEqual(actual["flags"][name], original["flags"][name], name)
                        original_reads = [event for event in original["io"] if event[0] == "read"]
                        actual_reads = [event for event in self.events() if event.kind == 3]
                        self.assertEqual(len(actual_reads), len(original_reads))
                        for expected, actual_event in zip(original_reads, actual_reads):
                            self.assertEqual(actual_event.a, expected[2])
                            if expected[3] < 0:
                                self.assertLess(actual_event.result, 0)
                            else:
                                self.assertEqual(actual_event.result, expected[3])
                        original_seeks = [(event[2], event[3], event[4]) for event in original["io"]
                                          if event[0] == "lseek"]
                        actual_seeks = [(event.a, event.b, event.result) for event in self.events()
                                        if event.kind == 2]
                        self.assertEqual(actual_seeks, original_seeks)


class Native(unittest.TestCase):
    def setUp(self):
        self.lib = library()
        self.core = B.pristine_sites()

    def test_plan_rejections_are_exact_and_atomic(self):
        for name, data, reason in rejection_cases():
            with self.subTest(name=name):
                header = bytearray(80)
                header[:min(len(data), 80)] = data[:80]
                canary = b"\xA5" * c.sizeof(Plan)
                plan = Plan.from_buffer_copy(canary)
                rc = self.lib.pops_osd_plan(buf(header), len(header), len(data), c.byref(plan))
                self.assertEqual(rc, REASON_CODES[reason])
                self.assertEqual(bytes(plan), canary)

    def test_valid_plan_fields_and_body_requests(self):
        for version, address, cap in ((1, T.V1_ADDR, T.V1_CAP), (2, T.V2_ADDR, T.V2_CAP)):
            for size in (4, 16, 17, cap - 17, cap - 16, cap - 15, cap):
                data = T.make_osd(version=version, body_size=size)
                header = bytearray(80)
                header[:80] = data[:80]
                plan = Plan()
                self.assertEqual(self.lib.pops_osd_plan(buf(header), 80, len(data), c.byref(plan)), 0)
                expected = size + 16 if size <= cap - 16 and size & 0xF else size
                self.assertEqual((plan.body_size, plan.body_request, plan.body_address,
                                  plan.body_capacity, plan.file_size),
                                 (size, expected, address, cap, len(data)))
                self.assertEqual(bytes(plan.header), data[:64])

    def test_stage_matches_original_values_and_state_only_probe(self):
        for version in (1, 2):
            data = T.make_osd(version=version, body_size=31, modes=(6,))
            actual = stage_file(self.core, data, flags={"osd_off": 1})
            self.assertEqual(actual["ret"], 1)
            self.assertEqual(T.get(actual["core"], 0x2525B0, 2), 0x0648)
            self.assertEqual(actual["flags"]["osd_off"], 1)
            header = bytearray(80)
            header[:80] = data[:80]
            plan = Plan()
            self.assertEqual(self.lib.pops_osd_plan(buf(header), 80, len(data), c.byref(plan)), 0)
            state = Rom(osd_off=1, integrity=1)
            self.assertEqual(self.lib.pops_osd_stage(None, 0, c.byref(plan), None, 0, 0,
                                                     c.byref(state)), 1)
            self.assertEqual(state_dict(state), actual["flags"])

    def test_gate_rules(self):
        for per_game in (0, 1, 2):
            self.assertEqual(self.lib.pops_user_osd_skipped(per_game, Rom(integrity=1)), 0)
            self.assertEqual(self.lib.pops_user_osd_skipped(per_game, Rom()), 1)
            self.assertEqual(self.lib.pops_user_osd_skipped(per_game, Rom(integrity=1, abort=1)), 1)
            self.assertEqual(self.lib.pops_user_osd_skipped(per_game, Rom(integrity=1, game_dir_missing=1)),
                             int(per_game == 1))
            self.assertEqual(self.lib.pops_user_osd_skipped(per_game, Rom(integrity=1, osd_game_b=1)),
                             int(per_game != 1))

    def test_bad_arguments_are_atomic(self):
        data = T.make_osd(body_size=17)
        header = bytearray(80)
        header[:80] = data[:80]
        plan = Plan()
        canary = b"\xA5" * c.sizeof(Plan)
        invalid = Plan.from_buffer_copy(canary)
        self.assertEqual(self.lib.pops_osd_plan(None, 1, len(data), c.byref(invalid)), -errno.EINVAL)
        self.assertEqual(self.lib.pops_osd_plan(buf(header), 80, len(data), None), -errno.EINVAL)
        self.assertEqual(self.lib.pops_osd_plan(buf(header), 81, len(data), c.byref(invalid)), -errno.ERANGE)
        self.assertEqual(bytes(invalid), canary)
        self.assertEqual(self.lib.pops_osd_plan(buf(header), 80, len(data), c.byref(plan)), 0)
        state = Rom(integrity=1)
        before = state_dict(state)
        self.assertEqual(self.lib.pops_osd_stage(None, 0, None, None, 0, 0, c.byref(state)), -errno.EINVAL)
        self.assertEqual(self.lib.pops_osd_stage(None, 0, c.byref(plan), None, 0, 0, None), -errno.EINVAL)
        small = bytearray(32)
        self.assertEqual(self.lib.pops_osd_stage(buf(small), len(small), c.byref(plan), None, 0, 0,
                                                 c.byref(state)), -errno.ERANGE)
        self.assertEqual(small, bytes(32))
        self.assertEqual(self.lib.pops_osd_stage(buf(self.core), len(self.core), c.byref(plan), None, 1, 0,
                                                 c.byref(state)), -errno.EINVAL)
        self.assertEqual(state_dict(state), before)


@unittest.skipUnless(HAVE, "POPSTARTER_TEST_ELF, POPS_TEST_ELF and unicorn are needed")
class OriginalDifferential(OsdTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lib = library()

    def assert_same(self, original, actual):
        self.assertEqual(actual["ret"], original["ret"])
        self.assertEqual(actual["reason"], original["reason"])
        self.assertEqual(actual["core"], original["core"])
        for name in ROM_FIELDS:
            self.assertEqual(actual["flags"][name], original["flags"][name], name)

    def test_rejections(self):
        for name, data, reason in rejection_cases():
            with self.subTest(name=name):
                original = self.probe(data)
                self.assert_rejected(original, reason)
                self.assert_same(original, stage_file(self.core, data))

    def test_valid_versions_and_cap_boundaries(self):
        for version, cap in ((1, T.V1_CAP), (2, T.V2_CAP)):
            for size in (4, 16, 17, cap - 17, cap - 16, cap - 15, cap):
                with self.subTest(version=version, size=size):
                    data = T.make_osd(version=version, body_size=size)
                    self.assert_same(self.probe(data), stage_file(self.core, data))

    def test_short_and_failed_reads(self):
        data = T.make_osd(body_size=31)
        for fault in (1, 0, -5):
            with self.subTest(fault=fault):
                original = self.probe(data, read_faults={"body": fault})
                self.assert_same(original, stage_file(self.core, data, body_read=fault))

    def test_modes_gates_and_mixed_scopes(self):
        cases = (
            (T.make_osd(modes=(1, 2, 3, 5)), {"no_fix": 1}),
            (T.make_osd(modes=(4, 7, 8, 255)), None),
            (T.make_osd(modes=(6,)), {"osd_off": 1}),
            (T.make_osd(), {"osd_off": 1}),
            (T.make_osd(version=2, flag=1), None),
            (T.make_osd(), {"integrity": 0}),
            (T.make_osd(), {"abort": 1}),
        )
        for index, (data, flags) in enumerate(cases):
            with self.subTest(index=index):
                original = self.probe(data, flags=flags)
                self.assert_same(original, stage_file(self.core, data, flags=flags))
        root_data = T.make_osd(version=2, body_size=64, seed=1)
        game_data = T.make_osd(version=1, body_size=32, seed=2)
        root = self.probe(root_data, scope=0)
        original = T.run_osd(root["core"], scope=1, data=game_data, flags=root["flags"])
        self.assert_same(original, stage_file(root["core"], game_data, scope=1, flags=root["flags"]))
        original = self.probe(T.make_osd(), scope=1, game_dir_ok=False)
        self.assert_same(original, stage_file(self.core, T.make_osd(), scope=1,
                                              flags={"game_dir_missing": 1}))

    def test_seeded_whole_core_differential(self):
        for index, data in enumerate(seeded_cases()):
            with self.subTest(index=index):
                self.assert_same(self.probe(data), stage_file(self.core, data))


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
