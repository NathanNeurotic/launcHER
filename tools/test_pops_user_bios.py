#!/usr/bin/env python3
"""POPStarter r13's user BIOS.BIN and the gates its loader flags drive.

Native checks need nothing; Reader runs the launcher's own file code from
handler_pops.c on the host, on files it makes up. The Original checks need
POPSTARTER_TEST_ELF, POPS_TEST_ELF and unicorn: the original's own code is run
on the real core (tools/trace_original_pops_user_bios.py) and launcHER's
functions must leave the same bytes and the same loader flags. Source checks
pin where the launch calls them. No original, POPS, BIOS or game byte is
stored here: every "BIOS.BIN" below is a counter pattern. Nothing here is a
console run.
"""
import array
import atexit
import ctypes as c
import errno
import itertools
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pops_features as F  # noqa: E402  (builds the host library)

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x200000
SIZE = 0x302E60
OSD_SITE = 0x2525B0
SKIPPED = 1  # POPS_MODE6_SKIPPED

FLAG_NAMES = ("bios_all", "bios_game", "osd_all_a", "osd_all_b", "osd_game_a", "osd_game_b",
              "osd_off")
REPLACED = ("bios_all", "bios_game")                       # gates of 0x2525b0's writers
KEEPS_SHELL = ("bios_all", "bios_game", "osd_all_b", "osd_game_b")  # shell edits, region


class Rom(c.Structure):
    """PopsUserRomState."""
    _fields_ = [(name, c.c_uint8) for name in FLAG_NAMES]


class Context(c.Structure):
    """PopsFixContext."""
    _fields_ = [("expected", c.c_uint32 * 39),
                ("video_expected", c.c_uint32 * 4),
                ("video_auto_disabled", c.c_uint8),
                ("video_custom_set", c.c_uint8),
                ("resident_entry", c.c_uint32),
                ("resident_expected", c.c_uint32 * 4),
                ("progressive_set", c.c_uint8)]


LIB = F.compile_shared_library()
P, Z = c.c_void_p, c.c_size_t
ROMP, CTXP = c.POINTER(Rom), c.POINTER(Context)
for name, args in (
        ("pops_user_rom_replaced", [ROMP]),
        ("pops_user_rom_keeps_shell", [ROMP]),
        ("pops_apply_bios_shell_edits", [P, Z]),
        ("pops_apply_bios_shell_edits_rom", [P, Z, ROMP]),
        ("pops_apply_region", [P, Z, c.c_int, c.c_uint8, c.c_int]),
        ("pops_apply_region_rom", [P, Z, c.c_int, c.c_uint8, c.c_int, ROMP]),
        ("pops_apply_undo_tokens", [P, Z, c.c_uint32]),
        ("pops_apply_undo_tokens_rom", [P, Z, c.c_uint32, ROMP]),
        ("pops_apply_compat_modes", [P, Z, c.c_uint8]),
        ("pops_apply_compat_modes_rom", [P, Z, c.c_uint8, ROMP]),
        ("pops_apply_all_config_patches", [P, Z, c.POINTER(F.PopsConfig)]),
        ("pops_apply_all_config_patches_rom", [P, Z, c.POINTER(F.PopsConfig), ROMP]),
        ("pops_fix_context_init_builtin", [CTXP, P, Z, c.c_uint16, c.c_uint8, c.c_uint8]),
        ("pops_fix_stage", [CTXP, P, Z, c.c_char_p, Z, c.c_uint, c.c_int]),
        ("pops_fix_stage_rom", [CTXP, P, Z, c.c_char_p, Z, c.c_uint, c.c_int, ROMP]),
        ("pops_builtin_apply", [c.c_uint16, P, Z, P, Z, c.c_uint32, P]),
        ("pops_user_bios_skipped", [c.c_int, ROMP]),
        ("pops_user_bios_size_ok", [c.c_int64]),
        ("pops_user_bios_stage", [P, Z, P, Z, c.c_int64, c.c_int, ROMP]),
        ("pops_fix_context_rom_loaded", [CTXP, P, Z]),
        ("pops_fix_finalize_video", [CTXP, P, Z, c.c_int, c.c_uint8]),
        ("pops_apply_reset_warmboot", [P, Z, c.POINTER(c.c_uint32)]),
        ("pops_config_parse_line", [c.POINTER(F.PopsConfig), c.c_char_p])):
    getattr(LIB, name).argtypes = args
    getattr(LIB, name).restype = c.c_int
LIB.pops_config_init.argtypes = [c.POINTER(F.PopsConfig)]
LIB.pops_config_init.restype = None

HAVE = bool(os.environ.get("POPSTARTER_TEST_ELF")) and bool(os.environ.get("POPS_TEST_ELF"))
if HAVE:
    try:
        import unicorn  # noqa: F401
        import trace_original_pops_user_bios as U
    except Exception:
        HAVE = False


def buf(data):
    return (c.c_uint8 * len(data)).from_buffer(data)


def rom(**flags):
    return Rom(**flags)


def flags_of(state):
    return {name: getattr(state, name) for name in FLAG_NAMES}


def put(core, address, value, width):
    core[address - BASE:address - BASE + width] = value.to_bytes(width, "little")


def get(core, address, width):
    return int.from_bytes(core[address - BASE:address - BASE + width], "little")


def synthetic(fill=0xA5):
    """A core-sized buffer of one byte with POPS's words at the mode 6 site
    and at the four sites the PAL change checks."""
    core = bytearray([fill]) * SIZE
    for address, value, width in ((OSD_SITE, 0x1BFC, 2), (0x21AF94, 2, 1), (0x502770, 0x8A3A2, 4),
                                  (0x23B018, 0x48, 1), (0x23B01C, 0x290, 2)):
        put(core, address, value, width)
    return core


def pristine_sites():
    """Zeroes plus the words the fix context and the compat modes check
    (the values tools/test_pops_fix_files.py uses)."""
    core = bytearray(SIZE)
    for address, value, width in ((0x210318, 0x8F828228, 4), (0x21032C, 0x1443FFFA, 4),
                                  (0x20083C, 0x0441000A, 4), (0x20085C, 0x1000FFFA, 4),
                                  (0x20DE9C, 0x0C0836EE, 4), (0x21AF70, 0x64, 1),
                                  (OSD_SITE, 0x1BFC, 2), (0x21AF94, 2, 1),
                                  (0x502770, 0x8A3A2, 4), (0x23B018, 0x48, 1),
                                  (0x23B01C, 0x290, 2)):
        put(core, address, value, width)
    return core


def patch(modes, slot=1):
    """A PATCH_n.BIN that only asks for compatibility modes (synthetic)."""
    header = bytearray(64)
    header[:8] = ("PATCH_%d\0" % slot).encode()
    struct.pack_into("<6I", header, 8, 1, 0x10001, 0, 0, 0, 0)
    header[32:37] = b"owned"
    header[56:56 + len(modes)] = bytes(modes)
    return bytes(header)


def changed(a, b, step=4096):
    """Offsets at which two equally long buffers differ."""
    for start in range(0, len(a), step):
        if a[start:start + step] != b[start:start + step]:
            for i in range(start, min(start + step, len(a))):
                if a[i] != b[i]:
                    yield i


def all_flag_sets():
    """Every combination of the seven flags (128)."""
    for bits in itertools.product((0, 1), repeat=len(FLAG_NAMES)):
        yield {name: bit for name, bit in zip(FLAG_NAMES, bits) if bit}


SINGLE_FLAG_SETS = [{}] + [{name: 1} for name in FLAG_NAMES] + [{"bios_all": 1, "bios_game": 1}]

ROM = 0x24BC20       # POPS_USER_BIOS_ADDR: POPS's copy of the PS1 ROM
ROM_READ = 0x7FF90   # POPS_USER_BIOS_READ: what the loader asks read() for
ROM_MIN = 0x7FF8F    # POPS_USER_BIOS_MIN_SIZE: the smallest size it accepts
BRANCH = 0x20079A    # high half of POPS's bnez after its xCdInit call
SIZES = (0, 0x7FF8E, 0x7FF8F, 0x7FF90, 0x80000, 0x100000)
GATE_ALL = ("osd_all_a", "osd_all_b", "osd_game_b")   # the loader's own entry gates
GATE_GAME = ("osd_game_a", "osd_game_b")

_FILES = {}


def bios_file(size, seed=1):
    """A made-up BIOS.BIN: little-endian 32-bit counters, so a byte put at
    the wrong offset shows. Not a BIOS and not derived from one."""
    if seed not in _FILES:
        start = 0x40000000 | ((seed * 0x9E3779) & 0xFFFFFF)
        words = array.array("I", range(start, start + 0x100000 // 4))
        if sys.byteorder != "little":
            words.byteswap()
        _FILES[seed] = words.tobytes()
    return _FILES[seed][:size]


def after_load(core, data):
    """What one accepted load leaves: the first 0x7ff90 bytes delivered, over
    the ROM, and 0x1000 at 0x20079a. Nothing else."""
    out = bytearray(core)
    count = min(len(data), ROM_READ)
    out[ROM - BASE:ROM - BASE + count] = data[:count]
    put(out, BRANCH, 0x1000, 2)
    return out


def stage(core, data, file_size, scope, state):
    """pops_user_bios_stage as the reader calls it: the bytes a read of
    0x7ff90 bytes returns, and the size lseek reported."""
    count = min(len(data), ROM_READ)
    return LIB.pops_user_bios_stage(buf(core), SIZE, bytes(data[:count]) if count else None, count,
                                    file_size, scope, c.byref(state))


def patch_file(slot, modes=(), payload=b"", address=0):
    """A synthetic PATCH_n.BIN with a payload (tools/test_pops_fix_files.py's layout)."""
    header = bytearray(64)
    header[:8] = ("PATCH_%d\0" % slot).encode()
    struct.pack_into("<6I", header, 8, 1 if modes else 0, 0x10001, address, 0, 0, len(payload))
    header[32:37] = b"owned"
    header[56:56 + len(modes)] = bytes(modes)
    return bytes(header) + payload


READER_WRAPPER = r'''
#include "pops_modes_patches.h"
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#ifndef O_BINARY
#define O_BINARY 0
#endif
#define PATH_MAX 1024
#define DPRINTF(...) ((void)0)
#define msg(...) ((void)0)
static char host_fix_buffer[0x100000];
static int open_fails, read_fails, seek_set;
static unsigned read_limit;
static long long seek_value;
static int opens, reads, closes;
static unsigned bytes_read;
static int test_open(const char *path, int flags) {
  ++opens;
  if (open_fails) { errno = EIO; return -1; }
  return open(path, flags | O_BINARY);
}
static off_t test_lseek(int fd, off_t offset, int whence) {
  off_t result = lseek(fd, offset, whence);
  return whence == SEEK_END && seek_set ? (off_t)seek_value : result;
}
static ssize_t test_read(int fd, void *buffer, size_t size) {
  ++reads;
  if (read_fails) { errno = EIO; return -1; }
  ssize_t result = read(fd, buffer, read_limit && size > read_limit ? read_limit : size);
  if (result > 0) bytes_read += (unsigned)result;
  return result;
}
static int test_close(int fd) { ++closes; return close(fd); }
#define open test_open
#define lseek test_lseek
#define read test_read
#define close test_close
%s
int test_stage(void *core, size_t size, const char *root, const char *title,
               PopsUserRomState *rom) {
  PopsFixContext state;
  return pops_stage_fix_files(core, size, root, title, 0, 0, 0, 0, 0, rom, &state);
}
int test_load(void *core, size_t size, const char *dir, int per_game, PopsUserRomState *rom) {
  return pops_user_bios_load(core, size, dir, per_game, rom);
}
int test_dependency(const char *path, void *buffer, size_t size, size_t *read_size) {
  return readPopsDependency(path, buffer, size, read_size);
}
void test_io(int fail_open, int fail_read, unsigned limit, int set_seek, long long seek) {
  open_fails = fail_open; read_fails = fail_read; read_limit = limit;
  seek_set = set_seek; seek_value = seek;
  opens = reads = closes = 0; bytes_read = 0;
}
void test_counts(unsigned *out) {
  out[0] = (unsigned)opens; out[1] = (unsigned)reads; out[2] = (unsigned)closes; out[3] = bytes_read;
}
'''

_READER = {}


def _reader_close():
    lib = _READER.pop("lib", None)
    if os.name == "nt" and lib is not None and getattr(lib, "_handle", None):
        c.windll.kernel32.FreeLibrary.argtypes = [c.c_void_p]
        c.windll.kernel32.FreeLibrary(lib._handle)
    temp = _READER.pop("temp", None)
    if temp is not None:
        temp.cleanup()


def reader_library():
    """The launcher's own file code, handler_pops.c from readFullFile to the
    end of pops_stage_fix_files, built for the host the way
    tools/test_pops_fix_files.py builds it. Only the EE scratch address is
    replaced; open, lseek, read and close go through counters and switches."""
    if "lib" in _READER:
        return _READER["lib"]
    temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    _READER["temp"] = temp
    atexit.register(_reader_close)
    directory = Path(temp.name)
    source = (ROOT / "launcher/src/handler_pops.c").read_text()
    start = source.index("static int readFullFile(")
    end = source.index("/* Driver names within one role", start)
    functions = source[start:end].replace("(void *)0x01f00000", "host_fix_buffer")
    wrapper = directory / "reader.c"
    wrapper.write_text(READER_WRAPPER % functions)
    library = directory / ("reader.dll" if os.name == "nt" else "reader.so")
    subprocess.run(["gcc", "-shared", "-fPIC", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-I", str(ROOT / "common/include"), str(wrapper),
                    str(ROOT / "common/src/pops_modes_patches.c"),
                    str(ROOT / "common/src/pops_resident_engine.c"),
                    str(ROOT / "common/src/pops_builtin_db.c"),
                    str(ROOT / "common/src/pops_builtin_db_data.c"),
                    str(ROOT / "common/src/pops_external.c"), "-o", str(library)], check=True)
    lib = c.CDLL(str(library))
    lib.test_stage.argtypes = [P, Z, c.c_char_p, c.c_char_p, ROMP]
    lib.test_load.argtypes = [P, Z, c.c_char_p, c.c_int, ROMP]
    lib.test_io.argtypes = [c.c_int, c.c_int, c.c_uint, c.c_int, c.c_longlong]
    lib.test_io.restype = None
    lib.test_counts.argtypes = [c.POINTER(c.c_uint)]
    lib.test_counts.restype = None
    _READER["lib"] = lib
    return lib


class Native(unittest.TestCase):
    def test_state_layout_and_predicates(self):
        self.assertEqual(c.sizeof(Rom), 7)
        self.assertEqual(LIB.pops_user_rom_replaced(None), 0)
        self.assertEqual(LIB.pops_user_rom_keeps_shell(None), 0)
        for flags in all_flag_sets():
            state = rom(**flags)
            self.assertEqual(bool(LIB.pops_user_rom_replaced(c.byref(state))),
                             any(flags.get(n) for n in REPLACED), flags)
            self.assertEqual(bool(LIB.pops_user_rom_keeps_shell(c.byref(state))),
                             any(flags.get(n) for n in KEEPS_SHELL), flags)
        # The original tests each word with bnez: any nonzero value is "set".
        self.assertEqual(LIB.pops_user_rom_replaced(c.byref(rom(bios_game=2))), 1)
        self.assertEqual(LIB.pops_user_rom_keeps_shell(c.byref(rom(osd_all_b=0x80))), 1)

    def test_no_state_and_zero_state_are_the_functions_as_they_were(self):
        """The old names are the new ones with no state; all flags zero is the
        same bytes and the same result."""
        zero = rom()

        def same(old, new, *args, core=None):
            results = []
            for call in (lambda b: old(b, SIZE, *args), lambda b: new(b, SIZE, *args, None),
                         lambda b: new(b, SIZE, *args, c.byref(zero))):
                data = bytearray(core if core is not None else synthetic())
                results.append((call(buf(data)), bytes(data)))
            self.assertEqual(results[0], results[1], (old.__name__, args))
            self.assertEqual(results[0], results[2], (old.__name__, args))
            return results[0][0]

        self.assertEqual(same(LIB.pops_apply_bios_shell_edits, LIB.pops_apply_bios_shell_edits_rom), 0)
        for region, video, disabled in itertools.product(range(4), range(7), (0, 1)):
            same(LIB.pops_apply_region, LIB.pops_apply_region_rom, region, video, disabled)
        for tokens in (1 << 12, 1 << 13, 1 << 14, 7 << 12, 0x0FFF):
            self.assertEqual(same(LIB.pops_apply_undo_tokens, LIB.pops_apply_undo_tokens_rom, tokens), 0)
        for mask in list(range(0, 0x80)) + [0x80]:
            zero.osd_off = 0
            same(LIB.pops_apply_compat_modes, LIB.pops_apply_compat_modes_rom, mask,
                 core=pristine_sites())
        zero.osd_off = 0
        for lines in ((), (b"$COMPATIBILITY_0x06",), (b"$UNDO_COMPATIBILITY_CODES",),
                      (b"$UNDO_GAME_FIXES", b"$COMPATIBILITY_0x06", b"$NOBOOT"),
                      (b"$UNDO_LIBCRYPT_FIX", b"$COMPATIBILITY_0x04")):
            cfg = F.PopsConfig()
            LIB.pops_config_init(c.byref(cfg))
            for line in lines:
                self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), line), 0, line)
            out = []
            for state in (False, None, rom()):
                data = pristine_sites()
                if state is False:
                    rc = LIB.pops_apply_all_config_patches(buf(data), SIZE, c.byref(cfg))
                else:
                    rc = LIB.pops_apply_all_config_patches_rom(
                        buf(data), SIZE, c.byref(cfg), None if state is None else c.byref(state))
                out.append((rc, bytes(data)))
            self.assertEqual(out[0][0], 0, lines)
            self.assertEqual(out[0], out[1], lines)
            self.assertEqual(out[0], out[2], lines)

    def test_shell_edits_gate(self):
        for flags in all_flag_sets():
            core = synthetic()
            before = bytes(core)
            state = rom(**flags)
            self.assertEqual(LIB.pops_apply_bios_shell_edits_rom(buf(core), SIZE, c.byref(state)), 0)
            if any(flags.get(n) for n in KEEPS_SHELL):
                self.assertEqual(bytes(core), before, flags)
            else:
                self.assertEqual(core[0x263ED6 - BASE], 0x20, flags)
                self.assertEqual(get(core, 0x263D56, 2), 0x1000, flags)
                self.assertEqual(get(core, 0x263DB0, 4), 0, flags)
            self.assertEqual(flags_of(state), flags_of(rom(**flags)))  # read only
        # Arguments are rejected before the gate, with nothing written.
        state = rom(bios_all=1)
        self.assertEqual(LIB.pops_apply_bios_shell_edits_rom(None, SIZE, c.byref(state)), -errno.EINVAL)
        core = synthetic()
        self.assertEqual(LIB.pops_apply_bios_shell_edits_rom(buf(core), 0x263ED6 - BASE, c.byref(state)),
                         -errno.ERANGE)

    def test_region_table(self):
        """The measured table: a known licence keeps 0x2649a0; an unknown one
        keeps 0x264994..0x2649a3 and 0x20f6cc/d8/dc/e0; the rest is written."""
        bios_sites = [(0x264994, 4), (0x264998, 4), (0x26499C, 4), (0x2649A0, 4)]
        cd_sites = [(0x20F6CC, 1), (0x20F6D8, 1), (0x20F6DC, 1), (0x20F6E0, 1)]
        for region, video, disabled in itertools.product(range(4), (0, 2, 3, 4), (0, 1)):
            plain = synthetic()
            self.assertEqual(LIB.pops_apply_region_rom(buf(plain), SIZE, region, video, disabled, None), 0)
            for flags in SINGLE_FLAG_SETS[1:]:
                core = synthetic()
                state = rom(**flags)
                self.assertEqual(LIB.pops_apply_region_rom(buf(core), SIZE, region, video, disabled,
                                                           c.byref(state)), 0)
                expected = bytearray(plain)
                if any(flags.get(n) for n in KEEPS_SHELL):
                    kept = bios_sites[3:] if region else bios_sites + cd_sites
                    for address, width in kept:
                        expected[address - BASE:address - BASE + width] = b"\xA5" * width
                self.assertEqual(core, expected, (region, video, disabled, flags))
                # Whatever the flags: the POPS letter is written.
                self.assertNotEqual(core[0x2CBB72 - BASE], 0xA5)

    def test_undo_keeps_the_osd_word_under_a_user_bios_only(self):
        for tokens, flags in itertools.product((1 << 12, 1 << 13, 1 << 14, 7 << 12),
                                               SINGLE_FLAG_SETS):
            plain, core = synthetic(), synthetic()
            put(plain, OSD_SITE, 0x0648, 2)
            put(core, OSD_SITE, 0x0648, 2)
            self.assertEqual(LIB.pops_apply_undo_tokens(buf(plain), SIZE, tokens), 0)
            state = rom(**flags)
            self.assertEqual(LIB.pops_apply_undo_tokens_rom(buf(core), SIZE, tokens, c.byref(state)), 0)
            self.assertEqual(get(plain, OSD_SITE, 2), 0x1BFC)
            if any(flags.get(n) for n in REPLACED):
                self.assertEqual(get(core, OSD_SITE, 2), 0x0648, (tokens, flags))
                put(core, OSD_SITE, 0x1BFC, 2)
            self.assertEqual(core, plain, (tokens, flags))  # every other write is made

    def test_mode_6_gate(self):
        for flags in all_flag_sets():
            for start in (0x1BFC, 0x0648):
                core = pristine_sites()
                put(core, OSD_SITE, start, 2)
                before = bytes(core)
                state = rom(**flags)
                rc = LIB.pops_apply_compat_modes_rom(buf(core), SIZE, 1 << 5, c.byref(state))
                after = flags_of(state)
                if any(flags.get(n) for n in REPLACED):
                    self.assertEqual(rc, SKIPPED, flags)
                    self.assertEqual(bytes(core), before, flags)
                    self.assertEqual(after, flags_of(rom(**flags)))
                elif flags.get("osd_off"):
                    self.assertEqual(rc, 0, flags)
                    self.assertEqual(bytes(core), before, flags)
                    self.assertEqual(after, flags_of(rom(**flags)))
                else:
                    self.assertEqual(rc, 0, flags)
                    self.assertEqual(get(core, OSD_SITE, 2), 0x0648, flags)
                    self.assertEqual(after, dict(flags_of(rom(**flags)), osd_off=1))
        # A skipped mode 6 does not check its site either (it may be the
        # user's BIOS there); an applied one still does.
        for flags, expected in (({"bios_all": 1}, SKIPPED), ({"osd_off": 1}, 0), ({}, -errno.EINVAL)):
            core = pristine_sites()
            put(core, OSD_SITE, 0x1234, 2)
            state = rom(**flags)
            self.assertEqual(LIB.pops_apply_compat_modes_rom(buf(core), SIZE, 1 << 5, c.byref(state)),
                             expected, flags)
            self.assertEqual(get(core, OSD_SITE, 2), 0x1234)
        # The other modes do not read the state: same bytes with every flag set.
        everything = rom(**{name: 1 for name in FLAG_NAMES})
        for mask in range(1, 0x80):
            if mask & (1 << 5):
                continue
            plain, core = pristine_sites(), pristine_sites()
            a = LIB.pops_apply_compat_modes(buf(plain), SIZE, mask)
            b = LIB.pops_apply_compat_modes_rom(buf(core), SIZE, mask, c.byref(everything))
            self.assertEqual((a, plain), (b, core), mask)
        # With mode 6 skipped the rest of the mask is applied.
        plain, core = pristine_sites(), pristine_sites()
        self.assertEqual(LIB.pops_apply_compat_modes(buf(plain), SIZE, 1 << 3), 0)
        state = rom(bios_game=1)
        self.assertEqual(LIB.pops_apply_compat_modes_rom(buf(core), SIZE, (1 << 3) | (1 << 5),
                                                         c.byref(state)), SKIPPED)
        self.assertEqual(core, plain)

    def test_patch_file_mode_6_follows_the_same_gate(self):
        for flags in SINGLE_FLAG_SETS:
            core = pristine_sites()
            context, state = Context(), rom(**flags)
            self.assertEqual(LIB.pops_fix_context_init_builtin(c.byref(context), buf(core), SIZE, 0, 0, 0), 0)
            blob = patch((4, 6))
            rc = LIB.pops_fix_stage_rom(c.byref(context), buf(core), SIZE, blob, len(blob), 1, 0,
                                        c.byref(state))
            self.assertEqual(get(core, 0x21AF70, 1), 0, flags)  # mode 4 is applied either way
            if any(flags.get(n) for n in REPLACED):
                self.assertEqual((rc, get(core, OSD_SITE, 2), state.osd_off),
                                 (SKIPPED, 0x1BFC, flags.get("osd_off", 0)), flags)
            elif flags.get("osd_off"):
                self.assertEqual((rc, get(core, OSD_SITE, 2), state.osd_off), (0, 0x1BFC, 1), flags)
            else:
                self.assertEqual((rc, get(core, OSD_SITE, 2), state.osd_off), (0, 0x0648, 1), flags)
            # The context follows what was written, so the next file is accepted.
            blob = patch((4,), slot=2)
            self.assertEqual(LIB.pops_fix_stage_rom(c.byref(context), buf(core), SIZE, blob, len(blob),
                                                    2, 0, c.byref(state)), 0, flags)
        # No state: as before.
        plain, core = pristine_sites(), pristine_sites()
        one, two = Context(), Context()
        blob = patch((6,))
        for data, context in ((plain, one), (core, two)):
            self.assertEqual(LIB.pops_fix_context_init_builtin(c.byref(context), buf(data), SIZE, 0, 0, 0), 0)
        self.assertEqual(LIB.pops_fix_stage(c.byref(one), buf(plain), SIZE, blob, len(blob), 1, 0), 0)
        self.assertEqual(LIB.pops_fix_stage_rom(c.byref(two), buf(core), SIZE, blob, len(blob), 1, 0, None), 0)
        self.assertEqual(core, plain)
        self.assertEqual(bytes(one), bytes(two))

    def config(self, *lines):
        cfg = F.PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        for line in lines:
            self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), line), 0, line)
        return cfg

    def test_config_pass_with_the_state(self):
        base = pristine_sites()
        self.assertEqual(LIB.pops_apply_all_config_patches(buf(base), SIZE, c.byref(self.config())), 0)
        # Mode 6: written and remembered; skipped and reported under a BIOS.BIN.
        for flags, rc, word, off in (({}, 0, 0x0648, 1), ({"bios_all": 1}, SKIPPED, 0x1BFC, 0),
                                     ({"bios_game": 1}, SKIPPED, 0x1BFC, 0),
                                     ({"osd_off": 1}, 0, 0x1BFC, 1), ({"osd_game_b": 1}, 0, 0x0648, 1)):
            core, state = pristine_sites(), rom(**flags)
            self.assertEqual(LIB.pops_apply_all_config_patches_rom(
                buf(core), SIZE, c.byref(self.config(b"$COMPATIBILITY_0x06")), c.byref(state)), rc, flags)
            self.assertEqual((get(core, OSD_SITE, 2), state.osd_off), (word, off), flags)
            put(core, OSD_SITE, 0x1BFC, 2)
            self.assertEqual(core, base, flags)
        # $UNDO_*: the 0x2525b0 row only.
        for line in (b"$UNDO_COMPATIBILITY_CODES", b"$UNDO_GAME_FIXES", b"$UNDO_LIBCRYPT_FIX"):
            for flags in SINGLE_FLAG_SETS:
                plain, core, state = pristine_sites(), pristine_sites(), rom(**flags)
                put(plain, OSD_SITE, 0x0648, 2)
                put(core, OSD_SITE, 0x0648, 2)
                self.assertEqual(LIB.pops_apply_all_config_patches(buf(plain), SIZE, c.byref(self.config(line))), 0)
                self.assertEqual(LIB.pops_apply_all_config_patches_rom(
                    buf(core), SIZE, c.byref(self.config(line)), c.byref(state)), 0)
                kept = any(flags.get(n) for n in REPLACED)
                self.assertEqual(get(core, OSD_SITE, 2), 0x0648 if kept else 0x1BFC, (line, flags))
                put(core, OSD_SITE, 0x1BFC, 2)
                self.assertEqual(core, plain, (line, flags))
                self.assertEqual(flags_of(state), flags_of(rom(**flags)))  # $UNDO_ leaves gp+0x3704

    def test_noboot_leaves_a_user_bios_alone(self):
        """$NOBOOT/$BIOS is launcHER's own: 0x0648 -> 0x1bfc, except under a
        user BIOS.BIN. Without one it also clears the mode 6 flag."""
        for flags, word, off in (({}, 0x1BFC, 0), ({"osd_off": 1}, 0x1BFC, 0),
                                 ({"bios_all": 1}, 0x0648, 0), ({"bios_game": 1, "osd_off": 1}, 0x0648, 1),
                                 ({"osd_all_b": 1}, 0x1BFC, 0)):
            core, state = pristine_sites(), rom(**flags)
            put(core, OSD_SITE, 0x0648, 2)
            self.assertEqual(LIB.pops_apply_all_config_patches_rom(
                buf(core), SIZE, c.byref(self.config(b"$NOBOOT")), c.byref(state)), 0, flags)
            self.assertEqual((get(core, OSD_SITE, 2), state.osd_off), (word, off), flags)
        # No state: as before.
        core = pristine_sites()
        put(core, OSD_SITE, 0x0648, 2)
        self.assertEqual(LIB.pops_apply_all_config_patches(buf(core), SIZE, c.byref(self.config(b"$NOBOOT"))), 0)
        self.assertEqual(get(core, OSD_SITE, 2), 0x1BFC)

    def mode_6_entry(self):
        """The id of a built-in entry that runs compatibility mode 6."""
        plan = (c.c_uint8 * 4096)()
        for entry in range(1, 2000):
            core = pristine_sites()
            if LIB.pops_builtin_apply(entry, buf(core), SIZE, None, 0, 0, plan):
                continue
            if get(core, OSD_SITE, 2) == 0x0648:
                return entry
        self.fail("no built-in entry runs mode 6")

    def test_fix_context_accepts_the_osd_word_put_back(self):
        """The fix-file session starts after the user's commands: 0x2525b0 may
        hold POPS's own word again ($UNDO_*), or still (mode 6 not applied)."""
        context = Context()
        for modes, word, expected in ((0x20, 0x0648, 0), (0x20, 0x1BFC, 0), (0, 0x1BFC, 0),
                                      (0, 0x0648, -errno.EINVAL), (0x20, 0x1234, -errno.EINVAL),
                                      (0, 0x1234, -errno.EINVAL)):
            core = pristine_sites()
            put(core, OSD_SITE, word, 2)
            self.assertEqual(LIB.pops_fix_context_init_builtin(c.byref(context), buf(core), SIZE, 0, modes, 0),
                             expected, (modes, hex(word)))
        entry = self.mode_6_entry()
        plan = (c.c_uint8 * 4096)()
        for tokens in (0, 1 << 13, 1 << 14):
            core = pristine_sites()
            self.assertEqual(LIB.pops_builtin_apply(entry, buf(core), SIZE, None, 0, 0, plan), 0)
            self.assertEqual(LIB.pops_apply_undo_tokens(buf(core), SIZE, tokens), 0)
            self.assertEqual(get(core, OSD_SITE, 2), 0x1BFC if tokens else 0x0648)
            self.assertEqual(LIB.pops_fix_context_init_builtin(c.byref(context), buf(core), SIZE, entry, 0, 0),
                             0, tokens)
            # ... and the session it starts stages a file.
            blob = patch((4,))
            self.assertEqual(LIB.pops_fix_stage(c.byref(context), buf(core), SIZE, blob, len(blob), 1, 0),
                             0, tokens)

    # -- BIOS.BIN itself -------------------------------------------------------

    def test_user_bios_size_rule(self):
        """Accepted from 0x7ff8f bytes up. The compare is on the size as a
        signed 32-bit value, so a failed lseek is "too small" too."""
        self.assertEqual((ROM, ROM_READ, ROM_MIN, ROM + ROM_READ), (0x24BC20, 0x7FF90, 0x7FF8F, 0x2CBBB0))
        for size, ok in ((-5, 0), (-1, 0), (0, 0), (1, 0), (0x7FF8E, 0), (0x7FF8F, 1), (0x7FF90, 1),
                         (0x80000, 1), (0x100000, 1), (0x7FFFFFFF, 1), (0x80000000, 0),
                         (0xFFFFFFFF, 0), (0x100000000, 0), (0x10007FF8F, 1)):
            self.assertEqual(LIB.pops_user_bios_size_ok(size), ok, hex(size))

    def test_user_bios_entry_gates(self):
        self.assertEqual(LIB.pops_user_bios_skipped(0, None), 0)
        self.assertEqual(LIB.pops_user_bios_skipped(1, None), 0)
        for flags in all_flag_sets():
            state = rom(**flags)
            self.assertEqual(bool(LIB.pops_user_bios_skipped(0, c.byref(state))),
                             any(flags.get(n) for n in GATE_ALL), flags)
            self.assertEqual(bool(LIB.pops_user_bios_skipped(1, c.byref(state))),
                             any(flags.get(n) for n in GATE_GAME), flags)

    def test_user_bios_stage_sizes(self):
        for scope, size in itertools.product((0, 1), SIZES):
            data = bios_file(size)
            core, state = synthetic(), rom()
            before = bytes(core)
            rc = stage(core, data, size, scope, state)
            if size < ROM_MIN:
                self.assertEqual((rc, bytes(core) == before, flags_of(state)), (0, True, flags_of(rom())),
                                 (scope, hex(size)))
                continue
            self.assertEqual(rc, 1, (scope, hex(size)))
            self.assertEqual(core, after_load(before, data), (scope, hex(size)))
            self.assertEqual(flags_of(state), flags_of(rom(**{"bios_game" if scope else "bios_all": 1})))
            # The last byte of the range is the file's only from 0x7ff90 bytes
            # up, and nothing past 0x2cbbaf is ever written.
            last = ROM + ROM_READ - 1 - BASE
            self.assertEqual(core[last] == 0xA5, size == ROM_MIN, hex(size))
            self.assertEqual(core[last + 1], 0xA5)
            self.assertEqual(get(core, BRANCH - 2, 4), 0x1000A5A5)

    def test_user_bios_stage_copies_what_the_read_delivered(self):
        """The original does not look at read's result: the size test is on
        the lseek result alone and whatever arrived is what is loaded."""
        data = bios_file(0x80000)
        for delivered in (0, 1, 0x1000, ROM_READ - 1, ROM_READ, ROM_READ + 1, 0x80000):
            core, state = synthetic(), rom()
            before = bytes(core)
            self.assertEqual(LIB.pops_user_bios_stage(buf(core), SIZE, data, delivered, 0x80000, 0,
                                                      c.byref(state)), 1, hex(delivered))
            self.assertEqual(core, after_load(before, data[:delivered]), hex(delivered))
            self.assertEqual(state.bios_all, 1)
        core, state = synthetic(), rom()
        before = bytes(core)
        self.assertEqual(LIB.pops_user_bios_stage(buf(core), SIZE, None, 0, ROM_MIN, 1, c.byref(state)), 1)
        self.assertEqual(core, after_load(before, b""))
        self.assertEqual(state.bios_game, 1)

    def test_user_bios_stage_gates_and_second_load(self):
        data = bios_file(0x80000)
        for scope, flags in itertools.product((0, 1), all_flag_sets()):
            core, state = synthetic(), rom(**flags)
            before = bytes(core)
            rc = stage(core, data, 0x80000, scope, state)
            if any(flags.get(n) for n in (GATE_GAME if scope else GATE_ALL)):
                self.assertEqual((rc, bytes(core) == before, flags_of(state)),
                                 (0, True, flags_of(rom(**flags))), (scope, flags))
            else:
                self.assertEqual(rc, 1, (scope, flags))
                self.assertEqual(core, after_load(before, data), (scope, flags))
                self.assertEqual(flags_of(state),
                                 dict(flags_of(rom(**flags)), **{"bios_game" if scope else "bios_all": 1}))
        # A flag already set does not stop a load: the game's file goes over
        # the all-games one, and a shorter second file leaves the first's tail.
        core, state = synthetic(), rom()
        before = bytes(core)
        first, second = bios_file(0x80000, 1), bios_file(ROM_MIN, 2)
        self.assertEqual(stage(core, first, 0x80000, 0, state), 1)
        self.assertEqual(stage(core, second, ROM_MIN, 1, state), 1)
        self.assertEqual(core, after_load(after_load(before, first), second))
        self.assertEqual(core[ROM + ROM_READ - 1 - BASE], first[ROM_READ - 1])
        self.assertEqual((state.bios_all, state.bios_game), (1, 1))

    def test_user_bios_stage_rejects_bad_arguments_without_writing(self):
        data = bios_file(0x80000)
        core, state = synthetic(), rom()
        before = bytes(core)
        memory = buf(core)
        need = ROM - BASE + ROM_READ
        inside = c.addressof(memory) + 0x1000
        for args, expected in (((None, SIZE, data, ROM_READ, 0x80000, 0, c.byref(state)), -errno.EINVAL),
                               ((memory, SIZE, data, ROM_READ, 0x80000, 0, None), -errno.EINVAL),
                               ((memory, SIZE, None, 1, 0x80000, 0, c.byref(state)), -errno.EINVAL),
                               ((memory, need - 1, data, ROM_READ, 0x80000, 0, c.byref(state)), -errno.ERANGE),
                               ((memory, 0, data, ROM_READ, 0x80000, 1, c.byref(state)), -errno.ERANGE),
                               ((memory, SIZE, inside, ROM_READ, 0x80000, 0, c.byref(state)), -errno.EINVAL)):
            self.assertEqual(LIB.pops_user_bios_stage(*args), expected, args[1:])
            self.assertEqual(bytes(core), before)
            self.assertEqual(flags_of(state), flags_of(rom()))
        # Bad arguments are reported even when a gate or the size test would
        # have left the file alone.
        gated = rom(osd_game_b=1)
        self.assertEqual(LIB.pops_user_bios_stage(memory, need - 1, data, ROM_READ, 0, 0, c.byref(gated)),
                         -errno.ERANGE)
        # A core that just reaches the end of the ROM range is enough.
        self.assertEqual(LIB.pops_user_bios_stage(memory, need, data, ROM_READ, 0x80000, 0,
                                                  c.byref(state)), 1)
        del memory

    def test_fix_session_goes_on_over_a_loaded_rom(self):
        """Mode 6's site, 0x2525b0, is inside the replaced range. Without
        pops_fix_context_rom_loaded the next fix file would be refused for a
        word the user's own file put there."""
        data = bios_file(0x80000)
        user_word, = struct.unpack_from("<H", data, OSD_SITE - ROM)
        self.assertNotIn(user_word, (0x1BFC, 0x0648))
        core, state, context = pristine_sites(), rom(), Context()
        self.assertEqual(LIB.pops_fix_context_init_builtin(c.byref(context), buf(core), SIZE, 0, 0, 0), 0)
        self.assertEqual(stage(core, data, 0x80000, 0, state), 1)
        blob = patch((4,))
        refused, stale = bytearray(core), Context.from_buffer_copy(context)
        self.assertEqual(LIB.pops_fix_stage_rom(c.byref(stale), buf(refused), SIZE, blob, len(blob), 1, 0,
                                                c.byref(state)), -errno.EINVAL)
        self.assertEqual(refused, core)
        # Bad arguments and a site outside the range that drifted: no change.
        kept = bytes(context)
        self.assertEqual(LIB.pops_fix_context_rom_loaded(None, buf(core), SIZE), -errno.EINVAL)
        self.assertEqual(LIB.pops_fix_context_rom_loaded(c.byref(context), None, SIZE), -errno.EINVAL)
        self.assertEqual(LIB.pops_fix_context_rom_loaded(c.byref(context), buf(core), OSD_SITE - BASE + 1),
                         -errno.ERANGE)
        drifted = bytearray(core)
        put(drifted, 0x21AF70, 0x77, 1)
        self.assertEqual(LIB.pops_fix_context_rom_loaded(c.byref(context), buf(drifted), SIZE), -errno.EINVAL)
        self.assertEqual(bytes(context), kept)
        self.assertEqual(LIB.pops_fix_context_rom_loaded(c.byref(context), buf(core), SIZE), 0)
        # Mode 4 is applied, mode 6 is not and says so; the user's word stays.
        blob = patch((4, 6))
        self.assertEqual(LIB.pops_fix_stage_rom(c.byref(context), buf(core), SIZE, blob, len(blob), 1, 0,
                                                c.byref(state)), SKIPPED)
        self.assertEqual((get(core, 0x21AF70, 1), get(core, OSD_SITE, 2), state.osd_off), (0, user_word, 0))
        # The stages after the fix files: final video, shell edits (none over
        # a user BIOS), the region pass and the $RESET_WARMBOOT scan.
        self.assertEqual(LIB.pops_fix_finalize_video(c.byref(context), buf(core), SIZE, 1, 0), 0)
        snapshot = bytes(core)
        self.assertEqual(LIB.pops_apply_bios_shell_edits_rom(buf(core), SIZE, c.byref(state)), 0)
        self.assertEqual(bytes(core), snapshot)
        self.assertEqual(LIB.pops_apply_region_rom(buf(core), SIZE, 1, 0, 0, c.byref(state)), 0)
        self.assertEqual(sorted(BASE + i for i in changed(core, snapshot)), [0x20F6CC, 0x2CBB72])
        # The POPS letter lands inside the user's BIOS, as in the original.
        self.assertEqual((core[0x2CBB72 - BASE], ROM <= 0x2CBB72 < ROM + ROM_READ), (ord("E"), True))
        vector = c.c_uint32(0)
        self.assertEqual(LIB.pops_apply_reset_warmboot(buf(core), SIZE, c.byref(vector)), 0)


class Reader(unittest.TestCase):
    """handler_pops.c's reader and its place among the fix files, on the host."""

    @classmethod
    def setUpClass(cls):
        cls.lib = reader_library()

    def setUp(self):
        self.lib.test_io(0, 0, 0x3001, 0, 0)
        temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.game = self.root / "GAME"
        self.game.mkdir()

    def folder(self, scope):
        return os.fsencode(str(self.game if scope else self.root) + "/")

    def put_bios(self, scope, data):
        path = (self.game if scope else self.root) / "BIOS.BIN"
        if data is None:
            if path.exists():
                path.unlink()
        else:
            path.write_bytes(data)

    def counts(self):
        """(opens, reads, closes, bytes delivered) since the last test_io."""
        values = (c.c_uint * 4)()
        self.lib.test_counts(values)
        return tuple(values)

    def load(self, core, scope, state, probe=False):
        if probe:
            return self.lib.test_load(None, 0, self.folder(scope), scope, c.byref(state))
        return self.lib.test_load(buf(core), SIZE, self.folder(scope), scope, c.byref(state))

    def test_each_size_in_each_folder(self):
        for scope, size in itertools.product((0, 1), (None,) + SIZES):
            data = None if size is None else bios_file(size)
            self.put_bios(scope, data)
            case = (scope, size)
            # First with no core: the answer the launch needs before the
            # user's commands run. Nothing is read and the state is left.
            self.lib.test_io(0, 0, 0x3001, 0, 0)
            state = rom()
            loads = size is not None and size >= ROM_MIN
            self.assertEqual(self.load(None, scope, state, probe=True), int(loads), case)
            self.assertEqual(self.counts(), (1, 0, 0 if size is None else 1, 0), case)
            self.assertEqual(flags_of(state), flags_of(rom()), case)
            # Then the load.
            self.lib.test_io(0, 0, 0x3001, 0, 0)
            core = pristine_sites()
            before = bytes(core)
            self.assertEqual(self.load(core, scope, state), int(loads), case)
            if not loads:
                self.assertEqual(bytes(core), before, case)
                self.assertEqual(flags_of(state), flags_of(rom()), case)
                self.assertEqual(self.counts(), (1, 0, 0 if size is None else 1, 0), case)
                continue
            self.assertEqual(core, after_load(before, data), case)
            self.assertEqual(flags_of(state), flags_of(rom(**{"bios_game" if scope else "bios_all": 1})), case)
            # Only the first 0x7ff90 bytes are ever asked for, however big the file.
            opens, reads, closes, delivered = self.counts()
            self.assertEqual((opens, closes, delivered), (1, 1, min(size, ROM_READ)), case)
            self.assertGreater(reads, 1)  # 0x3001 bytes a call here: the loop is exercised
            # The same bytes as the pure function on the same inputs.
            pure, pure_state = bytearray(before), rom()
            self.assertEqual(stage(pure, data, size, scope, pure_state), 1)
            self.assertEqual(core, pure, case)
            self.put_bios(scope, None)

    def test_gates_leave_the_file_closed(self):
        data = bios_file(0x80000)
        for scope in (0, 1):
            self.put_bios(scope, data)
            for name in FLAG_NAMES:
                for probe in (True, False):
                    self.lib.test_io(0, 0, 0, 0, 0)
                    core, state = pristine_sites(), rom(**{name: 1})
                    before = bytes(core)
                    gated = name in (GATE_GAME if scope else GATE_ALL)
                    rc = self.load(core, scope, state, probe)
                    self.assertEqual(rc, 0 if gated else 1, (scope, name, probe))
                    self.assertEqual(self.counts()[0], 0 if gated else 1, (scope, name, probe))
                    if gated or probe:
                        self.assertEqual(bytes(core), before, (scope, name, probe))

    def test_size_is_the_seek_result_and_the_read_is_not_checked(self):
        data = bios_file(0x80000)
        self.put_bios(0, data)
        # What lseek(END) reports decides, as a signed 32-bit value.
        for value, loads in ((-1, 0), (-5, 0), (0x7FF8E, 0), (0x7FF8F, 1), (0x7FFFFFFF, 1)):
            self.lib.test_io(0, 0, 0, 1, value)
            core, state = pristine_sites(), rom()
            before = bytes(core)
            self.assertEqual(self.load(core, 0, state), loads, hex(value))
            self.assertEqual(core, after_load(before, data) if loads else before, hex(value))
            self.assertEqual(self.counts()[2], 1)  # closed either way
        # A short file that lseek calls big enough: what arrived is loaded.
        self.put_bios(0, data[:0x123])
        self.lib.test_io(0, 0, 0, 1, ROM_MIN)
        core, state = pristine_sites(), rom()
        before = bytes(core)
        self.assertEqual(self.load(core, 0, state), 1)
        self.assertEqual(core, after_load(before, data[:0x123]))
        # A read that fails outright: still "loaded", with no byte replaced.
        self.put_bios(0, data)
        self.lib.test_io(0, 1, 0, 0, 0)
        core, state = pristine_sites(), rom()
        before = bytes(core)
        self.assertEqual(self.load(core, 0, state), 1)
        self.assertEqual(core, after_load(before, b""))
        self.assertEqual((state.bios_all, self.counts()[1:3]), (1, (1, 1)))
        # A file that cannot be opened is "not found", whatever the error.
        self.lib.test_io(1, 0, 0, 0, 0)
        core, state = pristine_sites(), rom()
        before = bytes(core)
        self.assertEqual(self.load(core, 0, state), 0)
        self.assertEqual((bytes(core) == before, state.bios_all), (True, 0))

    def test_path_that_does_not_fit(self):
        state = rom()
        long_folder = b"x" * 1016 + b"/"
        core = pristine_sites()
        self.assertEqual(self.lib.test_load(buf(core), SIZE, long_folder, 0, c.byref(state)),
                         -errno.ENAMETOOLONG)
        self.assertEqual(self.lib.test_load(None, 0, long_folder, 1, c.byref(state)), -errno.ENAMETOOLONG)
        self.assertEqual(self.counts()[0], 0)

    def run_launch_stage(self, state):
        core = pristine_sites()
        rc = self.lib.test_stage(buf(core), SIZE, self.folder(0), self.folder(1),
                                 None if state is None else c.byref(state))
        return rc, core

    def test_each_folder_loads_before_its_own_fix_files(self):
        """All-games BIOS.BIN, all-games TROJAN/PATCH, game BIOS.BIN, game
        TROJAN/PATCH: a payload written into the ROM range by a folder's PATCH
        file stays over that folder's BIOS.BIN and is replaced by the next
        folder's."""
        one, two = bios_file(0x80000, 1), bios_file(0x80000, 2)
        root_patch = patch_file(0, modes=(4,), payload=b"ALLGAMES", address=0x250000)
        game_patch = patch_file(1, payload=b"GAME", address=0x250100)
        for root_bios, game_bios in itertools.product((None, one), (None, two)):
            self.put_bios(0, root_bios)
            self.put_bios(1, game_bios)
            (self.root / "PATCH_0.BIN").write_bytes(root_patch)
            (self.game / "PATCH_1.BIN").write_bytes(game_patch)
            state = rom()
            rc, core = self.run_launch_stage(state)
            self.assertEqual(rc, 0)
            expected = pristine_sites()
            if root_bios:
                expected = after_load(expected, root_bios)
            expected[0x250000 - BASE:0x250008 - BASE] = b"ALLGAMES"
            put(expected, 0x21AF70, 0, 1)  # mode 4
            if game_bios:
                expected = after_load(expected, game_bios)
            expected[0x250100 - BASE:0x250104 - BASE] = b"GAME"
            case = (bool(root_bios), bool(game_bios))
            self.assertEqual(core, expected, case)
            self.assertEqual((state.bios_all, state.bios_game), (int(bool(root_bios)), int(bool(game_bios))))
            # The all-games payload is gone exactly when the game has a BIOS.BIN.
            self.assertEqual(bytes(core[0x250000 - BASE:0x250008 - BASE]) == b"ALLGAMES", not game_bios, case)
        # Without a state the stage keeps its own: same bytes.
        rc, core = self.run_launch_stage(None)
        self.assertEqual((rc, core), (0, expected))

    def test_mode_6_from_a_patch_file_over_a_bios(self):
        data = bios_file(0x80000)
        user_word, = struct.unpack_from("<H", data, OSD_SITE - ROM)
        (self.root / "PATCH_0.BIN").write_bytes(patch_file(0, modes=(6,)))
        (self.root / "PATCH_1.BIN").write_bytes(patch_file(1, modes=(4,)))
        (self.game / "PATCH_2.BIN").write_bytes(patch_file(2, modes=(6, 4)))
        for scope, loaded in ((None, False), (0, True), (1, True)):
            self.put_bios(0, data if scope == 0 else None)
            self.put_bios(1, data if scope == 1 else None)
            state = rom()
            rc, core = self.run_launch_stage(state)
            self.assertEqual(rc, 0, scope)
            self.assertEqual(get(core, 0x21AF70, 1), 0, scope)
            if scope == 0:
                # Never written: the user's word, and no mode 6 flag.
                self.assertEqual((get(core, OSD_SITE, 2), state.osd_off), (user_word, 0))
            elif scope == 1:
                # The all-games PATCH wrote it before the game's BIOS.BIN
                # replaced the range; the flag it set stays, as in the original.
                self.assertEqual((get(core, OSD_SITE, 2), state.osd_off), (user_word, 1))
            else:
                self.assertEqual((get(core, OSD_SITE, 2), state.osd_off), (0x0648, 1))


@unittest.skipUnless(HAVE, "POPSTARTER_TEST_ELF, POPS_TEST_ELF and unicorn are needed")
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = U.core_image()
        assert len(cls.core) == SIZE

    def state_after(self, flags_after):
        return {name: flags_after[name] for name in FLAG_NAMES}

    def test_shell_slice_with_every_flag_combination(self):
        count = 0
        for flags in all_flag_sets():
            expected = U.shell(self.core, flags)
            ours = bytearray(self.core)
            state = rom(**flags)
            self.assertEqual(LIB.pops_apply_bios_shell_edits_rom(buf(ours), SIZE, c.byref(state)), 0)
            self.assertEqual(ours, expected, flags)
            count += 1
        # The two words main never passes on but that sit beside them.
        for extra in ("abort", "game_dir_missing", "preset_osd_off"):
            ours = bytearray(self.core)
            self.assertEqual(LIB.pops_apply_bios_shell_edits_rom(buf(ours), SIZE, None), 0)
            self.assertEqual(ours, U.shell(self.core, {extra: 1}), extra)
            count += 1
        print("Original shell-edit slice 0x878f64..0x878fc4: %d flag cases, bytes equal" % count)

    PAL_SITES = ((0x21AF94, 1), (0x502770, 4), (0x23B018, 1), (0x23B01C, 2))

    def test_region_window_with_the_flags(self):
        """5 licences x force_pal x auto_disabled x selector x 9 flag sets.
        launcHER's inputs are (video mode, auto disabled): force_pal is
        $FORCEPAL, the selector cleared is $NOPAL. Two of the eight
        combinations (auto disabled with the selector still set) cannot be
        given to pops_apply_region; they differ for a European licence only,
        in the PAL change, and those four sites are left out there."""
        licences = ((b"Euro", 1), (b"Amer", 2), (b"of A", 2), (b"Inc.", 3), (b"????", 0))
        full = partial = 0
        for (licence, region), force_pal, disabled, selector, flags in itertools.product(
                licences, (0, 1), (0, 1), (0, 1), SINGLE_FLAG_SETS):
            expected = U.region(self.core, licence, force_pal, disabled, selector, flags)
            video = 2 if force_pal else (0 if selector else 3)
            ours = bytearray(self.core)
            state = rom(**flags)
            self.assertEqual(LIB.pops_apply_region_rom(buf(ours), SIZE, region, video, disabled,
                                                       c.byref(state)), 0)
            case = (licence, force_pal, disabled, selector, flags)
            if region == 1 and disabled and selector:
                for address, width in self.PAL_SITES:
                    put(ours, address, get(expected, address, width), width)
                partial += 1
            else:
                full += 1
            self.assertEqual(ours, expected, case)
        print("Original region window 0x879034..0x8795f0: %d cases byte-for-byte, %d more "
              "(European licence, auto disabled, selector set) outside the PAL sites" % (full, partial))

    def test_mode_dispatcher_with_every_flag_combination(self):
        """FUN_008dc2c4: mode 6 for all 128 combinations and both words the
        site can hold; the other modes with each flag."""
        count = 0
        for flags in all_flag_sets():
            for start in (0x1BFC, 0x0648):
                core = bytearray(self.core)
                put(core, OSD_SITE, start, 2)
                expected, after, messages = U.mode(core, 6, flags, quiet=0)
                ours = bytearray(core)
                state = rom(**flags)
                rc = LIB.pops_apply_compat_modes_rom(buf(ours), SIZE, 1 << 5, c.byref(state))
                self.assertEqual(ours, expected, (flags, start))
                self.assertEqual({k: bool(v) for k, v in flags_of(state).items()},
                                 {k: bool(v) for k, v in self.state_after(after).items()}, flags)
                notice = any(b"BIOS.BIN" in line for line in messages)
                self.assertEqual(rc, SKIPPED if notice else 0, (flags, messages))
                count += 1
        for number in (1, 2, 3, 4, 5, 7):
            plain = U.mode(self.core, number)[0]
            for name in FLAG_NAMES:
                self.assertEqual(U.mode(self.core, number, {name: 1})[0], plain, (number, name))
                ours = bytearray(self.core)
                state = rom(**{name: 1})
                self.assertEqual(LIB.pops_apply_compat_modes_rom(buf(ours), SIZE, 1 << (number - 1),
                                                                 c.byref(state)), 0)
                self.assertEqual(ours, plain, (number, name))
                count += 1
        print("Original mode dispatcher FUN_008dc2c4: %d cases, bytes, gp+0x3704 and notice equal" % count)

    BLOB_SITES = (0x2397D8, 0x239780, 0x239784)  # the original's own resident blob

    def test_parser_commands_with_the_flags(self):
        """$COMPATIBILITY_0x06 and the three $UNDO_ commands through the
        original's CHEATS.TXT section, one command per text, with each flag
        preset and both words at 0x2525b0, against launcHER's config pass.
        launcHER's pass also makes its own launch writes; those are taken
        from a run of the same pass with no command."""
        count = 0
        for command, flags, start in itertools.product(
                ("$COMPATIBILITY_0x06", "$UNDO_COMPATIBILITY_CODES", "$UNDO_GAME_FIXES",
                 "$UNDO_LIBCRYPT_FIX"), SINGLE_FLAG_SETS, (0x1BFC, 0x0648)):
            core = bytearray(self.core)
            put(core, OSD_SITE, start, 2)
            theirs, after = U.parser(command + "\n", core, flags)
            for address in self.BLOB_SITES:
                put(theirs, address, get(core, address, 4), 4)

            def ours(lines):
                cfg = F.PopsConfig()
                LIB.pops_config_init(c.byref(cfg))
                for line in lines:
                    self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), line), 0, line)
                data, state = bytearray(core), rom(**flags)
                rc = LIB.pops_apply_all_config_patches_rom(buf(data), SIZE, c.byref(cfg), c.byref(state))
                self.assertGreaterEqual(rc, 0, (lines, flags))
                return data, state

            base, _ = ours(())
            data, state = ours((command.encode(),))
            expected = bytearray(base)
            for i in changed(theirs, core):
                self.assertEqual(base[i], core[i], hex(BASE + i))  # no overlap with launch writes
                expected[i] = theirs[i]
            # A same-value write is invisible above; the site itself is compared outright.
            put(expected, OSD_SITE, get(theirs, OSD_SITE, 2), 2)
            self.assertEqual(data, expected, (command, flags, hex(start)))
            self.assertEqual(bool(state.osd_off), bool(after["osd_off"]), (command, flags))
            count += 1
        print("Original parser with loader flags: %d command/flag/word cases equal" % count)

    # -- the BIOS.BIN loader, FUN_0088019c ------------------------------------

    def truth(self, flags_after):
        return {name: bool(flags_after[name]) for name in FLAG_NAMES}

    def test_handler_differential(self):
        """Both folders x both back ends x {no file, 0, 0x7ff8e, 0x7ff8f,
        0x7ff90, 0x80000, 0x100000 bytes} x each loader flag: the return
        value, the whole core and the flags, against pops_user_bios_stage
        given what the launcher's reader gives it."""
        runs = loads = 0
        for scope, size, flags in itertools.product((0, 1), (None,) + SIZES,
                                                    [{}] + [{name: 1} for name in FLAG_NAMES]):
            data = None if size is None else bios_file(size)
            theirs = [U.handler(self.core, scope, backend, data, flags) for backend in (0, 1)]
            case = (scope, size, flags)
            for key in ("ret", "core", "flags"):
                self.assertEqual(theirs[0][key], theirs[1][key], (key, case))  # back ends agree
            for backend, result in enumerate(theirs):
                opens = [event for event in result["io"] if event[0] == "open"]
                state = rom(**flags)
                self.assertEqual(bool(LIB.pops_user_bios_skipped(scope, c.byref(state))), not opens, case)
                if opens:
                    self.assertEqual(opens[0][2:], (U.bios_path(scope, backend), 1), case)
                ours = bytearray(self.core)
                # No file: the reader stops at its open and stages nothing.
                rc = 0 if data is None else stage(ours, data, size, scope, state)
                self.assertEqual(rc, result["ret"], case)
                self.assertEqual(ours, result["core"], case)
                self.assertEqual(self.truth(flags_of(state)), self.truth(result["flags"]), case)
                text = b"\n".join(result["prints"])
                if rc == 1:
                    self.assertIn(b"User BIOS == ", text, case)
                    reads = [event for event in result["io"] if event[0] == "read"]
                    self.assertEqual([event[2:4] for event in reads], [(ROM, ROM_READ)], case)
                    self.assertEqual(result["core"], after_load(self.core, data), case)
                    loads += 1
                else:
                    self.assertEqual(result["core"], self.core, case)
                    self.assertFalse([event for event in result["io"] if event[0] == "read"], case)
                    if opens:
                        self.assertIn(b"NOT FOUND" if data is None else b"is too small", text, case)
                runs += 1
        print("Original BIOS.BIN loader FUN_0088019c: %d runs (%d loads), return value, whole core "
              "and flags equal" % (runs, loads))

    def test_handler_seek_results(self):
        """The size it tests is whatever lseek returned, compared signed."""
        data = bios_file(0x80000)
        count = 0
        for scope, backend, end in itertools.product(
                (0, 1), (0, 1), (-5, -1, 0x7FF8E, 0x7FF8F, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)):
            theirs = U.handler(self.core, scope, backend, data, lseek_end=end)
            ours, state = bytearray(self.core), rom()
            self.assertEqual(stage(ours, data, end, scope, state), theirs["ret"], (scope, backend, hex(end)))
            self.assertEqual(ours, theirs["core"], hex(end))
            self.assertEqual(self.truth(flags_of(state)), self.truth(theirs["flags"]), hex(end))
            self.assertEqual(theirs["ret"], int(end in (0x7FF8F, 0x7FFFFFFF)), hex(end))
            count += 1
        print("Original BIOS.BIN loader, lseek results: %d cases equal" % count)

    def test_game_file_loads_over_the_all_games_file(self):
        first, second = bios_file(0x80000, 1), bios_file(ROM_MIN, 2)
        one = U.handler(self.core, 0, 0, first)
        two = U.handler(one["core"], 1, 0, second, {"bios_all": 1})
        ours, state = bytearray(self.core), rom()
        self.assertEqual((stage(ours, first, 0x80000, 0, state), one["ret"]), (1, 1))
        self.assertEqual(ours, one["core"])
        self.assertEqual((stage(ours, second, ROM_MIN, 1, state), two["ret"]), (1, 1))
        self.assertEqual(ours, two["core"])
        self.assertEqual(self.truth(flags_of(state)), self.truth(two["flags"]))
        self.assertEqual((state.bios_all, state.bios_game), (1, 1))

    def test_words_the_launcher_has_no_counterpart_for(self):
        """gp+0x38dc (a launch already given up) and gp+0x3460 (the game's
        folder is missing) also stop the original's loader. launcHER returns
        from the launch in the first case and finds no file in the second."""
        data = bios_file(0x80000)
        for scope, backend in itertools.product((0, 1), (0, 1)):
            plain = U.handler(self.core, scope, backend, data)
            self.assertEqual(plain["ret"], 1)
            for name, stops in (("abort", True), ("game_dir_missing", scope == 1),
                                ("preset_osd_off", False)):
                result = U.handler(self.core, scope, backend, data, {name: 1})
                if stops:
                    self.assertEqual((result["ret"], result["io"], result["core"]), (0, [], self.core), name)
                else:
                    self.assertEqual((result["ret"], result["core"]), (1, plain["core"]), name)
            # The loader finds the missing folder itself (game scope only).
            result = U.handler(self.core, scope, backend, data, game_dir_ok=False)
            if scope == 1:
                self.assertEqual((result["ret"], result["io"], result["core"]), (-666, [], self.core))
                self.assertTrue(result["flags"]["game_dir_missing"])
            else:
                self.assertEqual((result["ret"], result["core"]), (1, plain["core"]))

    def test_main_calls_the_loader_unless_gated(self):
        """The launch function's own tests in front of both calls
        (0x876bb4..0x876ce0, 0x876ea8..0x876fe0) and the loader's entry tests
        together are pops_user_bios_skipped. Its eight preset compatibility
        slots (a 6 in any skips both calls) are bytes 0x100018..0x10001f of
        POPSTARTER.ELF's own segment: all zero in this build."""
        for scope in (0, 1):
            call = U.main_gate(scope)
            self.assertIsNotNone(call)
            self.assertEqual(call[0] == 1, scope == 1)
            for flags in [{}] + [{name: 1} for name in FLAG_NAMES]:
                called = U.main_gate(scope, flags) is not None
                opened = bool(U.handler(self.core, scope, 0, None, flags)["io"])
                state = rom(**flags)
                self.assertEqual(called and opened,
                                 not LIB.pops_user_bios_skipped(scope, c.byref(state)), (scope, flags))
            for name, stops in (("abort", True), ("game_dir_missing", scope == 1)):
                self.assertEqual(U.main_gate(scope, {name: 1}) is None, stops, (scope, name))
            for slot in U.PRESET_SLOTS:
                self.assertIsNone(U.main_gate(scope, None, {slot: 6}), hex(slot))
                self.assertIsNotNone(U.main_gate(scope, None, {slot: 5}), hex(slot))
        elf = Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes()
        phoff, = struct.unpack_from("<I", elf, 0x1C)
        phnum, = struct.unpack_from("<H", elf, 0x2C)
        found = 0
        for index in range(phnum):
            kind, offset, vaddr, _, filesz = struct.unpack_from("<5I", elf, phoff + 32 * index)
            if kind == 1 and vaddr <= 0x100018 and 0x100020 <= vaddr + filesz:
                self.assertEqual(elf[offset + 0x100018 - vaddr:offset + 0x100020 - vaddr], bytes(8))
                found += 1
        self.assertEqual(found, 1)

    def test_reader_on_the_real_core(self):
        """The launcher's reader (handler_pops.c built for the host) on files,
        against the original's loader on the same bytes; then both folders
        through pops_stage_fix_files against its two calls in order."""
        lib = reader_library()
        count = 0
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            root = Path(temp)
            game = root / "GAME"
            game.mkdir()
            folders = [os.fsencode(str(root) + "/"), os.fsencode(str(game) + "/")]
            for scope, size in itertools.product((0, 1), (None,) + SIZES):
                path = (game if scope else root) / "BIOS.BIN"
                data = None if size is None else bios_file(size)
                if data is not None:
                    path.write_bytes(data)
                theirs = U.handler(self.core, scope, 0, data)
                lib.test_io(0, 0, 0, 0, 0)
                ours, state = bytearray(self.core), rom()
                rc = lib.test_load(buf(ours), SIZE, folders[scope], scope, c.byref(state))
                self.assertEqual(rc, theirs["ret"], (scope, size))
                self.assertEqual(ours, theirs["core"], (scope, size))
                self.assertEqual(self.truth(flags_of(state)), self.truth(theirs["flags"]), (scope, size))
                if path.exists():
                    path.unlink()
                count += 1
            first, second = bios_file(0x100000, 1), bios_file(ROM_MIN, 2)
            (root / "BIOS.BIN").write_bytes(first)
            (game / "BIOS.BIN").write_bytes(second)
            one = U.handler(self.core, 0, 0, first)
            two = U.handler(one["core"], 1, 0, second, {"bios_all": 1})
            ours, state = bytearray(self.core), rom()
            self.assertEqual(lib.test_stage(buf(ours), SIZE, folders[0], folders[1], c.byref(state)), 0)
            self.assertEqual(ours, two["core"])
            self.assertEqual(self.truth(flags_of(state)), self.truth(two["flags"]))
        print("Original BIOS.BIN loader against the launcher's reader on files: %d cases and the "
              "two-folder sequence, whole core equal" % count)

    def test_later_passes_over_a_loaded_rom(self):
        """After a load the original's shell slice, region window and
        $RESET_WARMBOOT pass run over the user's bytes; launcHER's functions,
        given the flag the load set, must leave the same core."""
        import trace_original_pops_warmboot as W
        data = bytearray(bios_file(0x80000))
        # PS1 BIOS call stubs (li t2,table; jr t2; li t1,function), so the
        # warmboot scan has something to find in the made-up file.
        for offset, table, function in ((0x100, 0xA0, 0x3A), (0x200, 0xB0, 0x52), (0x8000, 0xA0, 0x3A),
                                        (0x9000, 0xC0, 0x0B), (0x9100, 0xA0, 0x41)):
            struct.pack_into("<III", data, offset, 0x240A0000 | table, 0x01400008, 0x24090000 | function)
        data = bytes(data)
        loaded = U.handler(self.core, 1, 0, data)
        flags = {"bios_game": 1}
        ours, state = bytearray(self.core), rom()
        self.assertEqual(stage(ours, data, len(data), 1, state), 1)
        self.assertEqual(ours, loaded["core"])
        theirs = U.shell(loaded["core"], flags)
        self.assertEqual(theirs, loaded["core"])  # no shell edit over a user BIOS
        self.assertEqual(LIB.pops_apply_bios_shell_edits_rom(buf(ours), SIZE, c.byref(state)), 0)
        self.assertEqual(ours, theirs)
        for licence, region in ((b"Euro", 1), (b"Amer", 2), (b"Inc.", 3), (b"????", 0)):
            expected = U.region(theirs, licence, 0, 0, 1, flags)
            mine = bytearray(ours)
            self.assertEqual(LIB.pops_apply_region_rom(buf(mine), SIZE, region, 0, 0, c.byref(state)), 0)
            self.assertEqual(mine, expected, licence)
            # The POPS letter is written into the user's bytes all the same.
            self.assertIn(mine[0x2CBB72 - BASE], b"EAJT")
            self.assertNotEqual(mine[0x2CBB72 - BASE], ours[0x2CBB72 - BASE])
        _events, after, _blob, slot = W.run(bytes(ours))
        vector = c.c_uint32(0)
        rc = LIB.pops_apply_reset_warmboot(buf(ours), SIZE, c.byref(vector))
        blob = range(0x232CE8 - BASE, 0x232D10 - BASE)  # the original's own resident block
        for index in changed(ours, after):
            self.assertIn(index, blob, hex(BASE + index))
        self.assertEqual((rc, vector.value), (1, struct.unpack("<I", slot)[0]))
        self.assertEqual(vector.value, ROM + 0x100)
        self.assertNotEqual(bytes(ours), bytes(loaded["core"]))  # the stubs were rewritten


class Source(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "launcher/src/handler_pops.c").read_text()
        self.body = self.src[self.src.index("int launchPOPS("):]

    def test_one_state_reaches_every_gated_stage(self):
        body = self.body
        declared = body.index("PopsUserRomState romState;")
        seeded = body.index("romState.osd_off = (builtinPlan.compat_modes & (1 << 5)) != 0;")
        calls = ["res = pops_apply_all_config_patches_rom((void *)stagedCore, plan.core_size, &cfg,\n"
                 "                                          &romAtCommands);",
                 "romState.osd_off = romAtCommands.osd_off;",
                 "&romState, &fixContext);",
                 "res = pops_apply_bios_shell_edits_rom((void *)stagedCore, plan.core_size, &romState);",
                 "&romState)\n                   : 0;"]
        at = [body.index(text) for text in calls]
        self.assertEqual(at, sorted(at))
        self.assertLess(body.index("res = pops_builtin_apply(builtinId, (void *)stagedCore"), declared)
        self.assertLess(declared, seeded)
        self.assertLess(seeded, at[0])
        self.assertEqual(body.count("PopsUserRomState romState;"), 1)
        # The fix files are staged with the same state.
        self.assertIn("result = pops_fix_stage_rom(&context, stagedCore, coreSize, buffer, size,\n"
                      "                                       slot, !kind, rom);", self.src)
        self.assertNotIn("pops_fix_stage(", self.src)

    def test_bios_is_read_where_the_original_reads_it(self):
        """Per folder, before that folder's TROJAN and PATCH files; the
        all-games folder (vcdDir) first, then the game's (gameConfigDir);
        after the built-in entry. The commands, which launcHER runs earlier
        than the original, get the two flags from a look at the files."""
        src, body = self.src, self.body
        stage = src[src.index("static int pops_stage_fix_files("):src.index("/* Driver names within one role")]
        order = ["pops_fix_context_init_builtin(&context, stagedCore, coreSize, builtinId,",
                 "const char *dirs[] = {vcdDir, titleDir};",
                 "for (unsigned scope = 0; scope < 2; ++scope) {",
                 "result = pops_user_bios_load(stagedCore, coreSize, dirs[scope], scope, rom);",
                 "result = pops_fix_context_rom_loaded(&context, stagedCore, coreSize);",
                 "for (unsigned kind = 0; kind < 2; ++kind) {",
                 'kind ? "PATCH" : "TROJAN", slot);',
                 "result = pops_fix_stage_rom(&context, stagedCore, coreSize, buffer, size,"]
        at = [stage.index(text) for text in order]
        self.assertEqual(at, sorted(at))
        self.assertEqual(stage.count("pops_user_bios_load("), 1)
        launch = ["res = pops_builtin_apply(builtinId, (void *)stagedCore",
                  "PopsUserRomState romAtCommands = romState;",
                  "res = pops_user_bios_load(NULL, 0, vcdDir, 0, &romAtCommands);",
                  "romAtCommands.bios_all = res > 0;",
                  "res = pops_user_bios_load(NULL, 0, gameConfigDir, 1, &romAtCommands);",
                  "romAtCommands.bios_game = res > 0;",
                  "res = pops_apply_all_config_patches_rom(",
                  "res = pops_stage_fix_files((void *)stagedCore, plan.core_size, vcdDir,\n"
                  "                              gameConfigDir, builtinId, cfg.compat_modes,",
                  "if (romState.bios_all != romAtCommands.bios_all ||\n"
                  "      romState.bios_game != romAtCommands.bios_game) {",
                  "res = pops_apply_bios_shell_edits_rom(",
                  "res = regionRead ? pops_apply_region_rom(",
                  "if (cfg.reset_warmboot) {"]
        at = [body.index(text) for text in launch]
        self.assertEqual(at, sorted(at))
        self.assertEqual(body.count("pops_user_bios_load("), 2)
        self.assertEqual(src.count("pops_user_bios_load("), 4)  # the definition and three calls

    def test_reader_asks_for_the_first_0x7ff90_bytes_only(self):
        src = self.src
        reader = src[src.index("static int pops_user_bios_load("):src.index("static int pops_stage_fix_files(")]
        order = ["if (pops_user_bios_skipped(perGame, rom))",
                 'snprintf(path, sizeof(path), "%sBIOS.BIN", dir);',
                 "int fd = open(path, O_RDONLY);",
                 "off_t size = lseek(fd, 0, SEEK_END);",
                 "lseek(fd, 0, SEEK_SET);",
                 "if (!pops_user_bios_size_ok(size)) {",
                 "if (!stagedCore) {",
                 "while (total < POPS_USER_BIOS_READ) {",
                 "size_t chunk = POPS_USER_BIOS_READ - total;",
                 "ssize_t n = read(fd, (char *)buffer + total, chunk);",
                 "int result = pops_user_bios_stage(stagedCore, coreSize, buffer, total, size, perGame, rom);"]
        at = [reader.index(text) for text in order]
        self.assertEqual(at, sorted(at))
        # Not the whole-file reader, which refuses a file larger than its buffer.
        self.assertNotIn("readFullFile(", reader)
        self.assertEqual(reader.count("read(fd,"), 1)
        header = (ROOT / "common/include/pops_modes_patches.h").read_text()
        for line in ("#define POPS_USER_BIOS_ADDR 0x0024bc20", "#define POPS_USER_BIOS_READ 0x0007ff90",
                     "#define POPS_USER_BIOS_MIN_SIZE 0x0007ff8f"):
            self.assertIn(line, header)
        pure = (ROOT / "common/src/pops_modes_patches.c").read_text()
        stage = pure[pure.index("int pops_user_bios_stage("):pure.index("/* FUN_008dc2c4's mode 6 arm")]
        for call in ("open(", "read(", "lseek(", "fopen(", "printf("):
            self.assertNotIn(call, stage)  # buffer logic only

    def test_state_struct_names_the_original_words(self):
        header = (ROOT / "common/include/pops_modes_patches.h").read_text()
        for field, word in (("bios_all", "gp+0x38a4"), ("bios_game", "gp+0x3b98"),
                            ("osd_all_a", "gp+0x343c"), ("osd_all_b", "gp+0x3430"),
                            ("osd_game_a", "gp+0x3878"), ("osd_game_b", "gp+0x344c"),
                            ("osd_off", "gp+0x3704")):
            line = [text for text in header.splitlines() if ("uint8_t %s;" % field) in text]
            self.assertEqual(len(line), 1, field)
            self.assertIn(word, line[0])


if __name__ == "__main__":
    unittest.main()
