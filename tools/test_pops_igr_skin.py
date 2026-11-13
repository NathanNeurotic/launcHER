#!/usr/bin/env python3
"""POPStarter r13's IGR menu skin (IGR_BG.TM2, IGR_NO.TM2, IGR_YES.TM2).

The original's loader (FUN_0087e464, called at 0x876b18) copies the three
files raw over the TIM2 files Sony's POPS carries for its own in-game reset
dialog; launcHER's pure part is pops_igr_skin_stage (common/src/
pops_igr_skin.c) and its reader is pops_stage_igr_skin in handler_pops.c.

No inputs needed (Native, Reader, Dialog, Staging, Source): the table, the
limits, the zero fill and what is refused; launcHER's reader itself,
compiled on the host from handler_pops.c with open/lseek/read/close handed
to a modelled device (tools/trace_original_pops_igr_skin.py: SkinFile) and
compared with a model of the original for well-behaved and misbehaving
devices; which IGR settings leave Sony's dialog reachable; that the built-in
list, the always-on hooks and the unguarded scans write nothing inside the
three slots; where launchPOPS makes the call.
With POPS_TEST_ELF (RealCore): Sony's own three files fill the slots
exactly, and launchPOPS's other stages are run on the real core around a
staged skin, one by one and in launchPOPS's order (user BIOS.BIN included;
the TROJAN slot chain and the progressive hook left out).
With POPSTARTER_TEST_ELF (OriginalCode): the table, the call's gates and
the order of the original's built-in list against the skin call are decoded
from its instructions.
With both and unicorn (Original): the original's loader runs as shipped over
the core with the same modelled device, and the whole core must equal the
model, pops_igr_skin_stage and, wherever launcHER is meant to match,
launcHER's reader; the listed differences are measured on both sides.
Nothing here is a console run.
"""
import ctypes as c
import errno
import os
import random
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pops_launch_hooks as H  # noqa: E402  (builds the library with every staging function)
import trace_original_pops_igr_skin as T  # noqa: E402  (its device model needs no inputs)

CORE = 0x00200000
CORE_SIZE = 0x00302E60
MAIN_BASE = 0x870000
BG, NO, YES = 0, 1, 2
# name, slot address, slot size, largest file accepted
SLOTS = [("IGR_BG.TM2", 0x002FEFF0, 0x4C300, 0x4C300),
         ("IGR_NO.TM2", 0x0034B2F0, 0x1DC0, 0x1DBC),
         ("IGR_YES.TM2", 0x0034D0B0, 0x1DC0, 0x1DBC)]
FIRST, END = 0x002FEFF0, 0x0034EE70   # the three slots are back to back

HAVE_CORE = bool(os.environ.get("POPS_TEST_ELF"))
HAVE_MAIN = bool(os.environ.get("POPSTARTER_TEST_ELF"))
# With both inputs set the Original class runs: a missing or broken unicorn
# is then an error there, not a skip.
HAVE_EMU = HAVE_CORE and HAVE_MAIN


class Slot(c.Structure):
    _fields_ = [("name", c.c_char_p), ("addr", c.c_uint32), ("slot_size", c.c_uint32),
                ("max_size", c.c_uint32)]


class Op(c.Structure):
    _fields_ = [("kind", c.c_uint8), ("arg", c.c_uint8), ("len", c.c_uint16),
                ("addr", c.c_uint32), ("data", c.c_uint32)]


# launcHER's reader runs on the host as written: the slice of handler_pops.c
# is compiled between these two pieces. Only its scratch address changes;
# its four I/O calls go to the device model and its debug text is kept.
O_RDONLY, PATH_MAX, SCRATCH_SIZE, READ_CAP = 0x5A, 1024, 0x100000, 4096
READER_HEAD = r'''
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "pops_igr_skin.h"
#undef PATH_MAX
#define PATH_MAX %d
typedef long long host_off_t;
typedef long long host_ssize_t;
#define off_t host_off_t
#define ssize_t host_ssize_t
#undef O_RDONLY
#undef SEEK_SET
#undef SEEK_END
#define O_RDONLY %d
#define SEEK_SET 0
#define SEEK_END 2
typedef int (*host_open_fn)(const char *, int);
typedef host_off_t (*host_lseek_fn)(int, host_off_t, int);
typedef host_ssize_t (*host_read_fn)(int, void *, size_t);
typedef int (*host_close_fn)(int);
static host_open_fn host_open;
static host_lseek_fn host_lseek;
static host_read_fn host_read;
static host_close_fn host_close;
#define open(path, flags) host_open((path), (flags))
#define lseek(fd, offset, whence) host_lseek((fd), (offset), (whence))
#define read(fd, buffer, size) host_read((fd), (buffer), (size))
#define close(fd) host_close((fd))
static char host_log[16384];
static size_t host_log_length;
static void host_printf(const char *format, ...) {
  va_list arguments;
  va_start(arguments, format);
  int n = vsnprintf(host_log + host_log_length, sizeof(host_log) - host_log_length, format,
                    arguments);
  va_end(arguments);
  if (n > 0 && host_log_length + (size_t)n < sizeof(host_log))
    host_log_length += (size_t)n;
}
#define DPRINTF(...) host_printf(__VA_ARGS__)
#define HOST_SCRATCH %d
#define HOST_GUARD 4096
#define HOST_FILL 0xc3
static uint8_t host_area[HOST_GUARD + HOST_SCRATCH + HOST_GUARD];
''' % (PATH_MAX, O_RDONLY, SCRATCH_SIZE)
READER_TAIL = r'''
#undef open
#undef lseek
#undef read
#undef close
void igr_reader_callbacks(host_open_fn o, host_lseek_fn l, host_read_fn r, host_close_fn cl) {
  host_open = o;
  host_lseek = l;
  host_read = r;
  host_close = cl;
}
const char *igr_reader_run(void *core, size_t core_size, const char *dir) {
  host_log_length = 0;
  host_log[0] = 0;
  memset(host_area, HOST_FILL, sizeof(host_area));
  pops_stage_igr_skin(core, core_size, dir);
  return host_log;
}
const uint8_t *igr_reader_scratch(void) { return host_area + HOST_GUARD; }
/* One past the highest scratch byte that no longer holds the fill. */
long igr_reader_high_water(void) {
  long i;
  for (i = HOST_SCRATCH; i > 0; --i)
    if (host_area[HOST_GUARD + i - 1] != HOST_FILL)
      break;
  return i;
}
int igr_reader_guards_intact(void) {
  for (size_t i = 0; i < HOST_GUARD; ++i)
    if (host_area[i] != HOST_FILL || host_area[HOST_GUARD + HOST_SCRATCH + i] != HOST_FILL)
      return 0;
  return 1;
}
'''
READER_BEGIN, READER_END = "static void pops_stage_igr_skin(", "/* POPStarter's XX. driver pair"
SCRATCH_LITERAL = "(uint8_t *)0x01f00000"


def reader_source():
    src = (ROOT / "launcher/src/handler_pops.c").read_text()
    return src[src.index(READER_BEGIN):src.index(READER_END)]


def build():
    out = Path(tempfile.mkdtemp())
    reader = reader_source()
    assert reader.count(SCRATCH_LITERAL) == 1, "the reader's scratch address"
    shim = out / "igr_reader.c"
    shim.write_text(READER_HEAD + reader.replace(SCRATCH_LITERAL, "(host_area + HOST_GUARD)") +
                    READER_TAIL)
    lib = out / ("igr_skin.dll" if os.name == "nt" else "igr_skin.so")
    subprocess.run(["gcc", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-I", str(ROOT / "common/include"),
                    str(ROOT / "common/src/pops_igr_skin.c"), str(shim), "-o", str(lib)], check=True)
    lib = c.CDLL(str(lib))
    lib.pops_igr_skin_slot.argtypes = [c.c_int]
    lib.pops_igr_skin_slot.restype = c.POINTER(Slot)
    lib.pops_igr_skin_stage.argtypes = [c.c_void_p, c.c_size_t, c.c_int, c.c_void_p, c.c_size_t]
    lib.pops_igr_skin_stage.restype = c.c_int
    lib.igr_reader_run.argtypes = [c.c_void_p, c.c_size_t, c.c_char_p]
    lib.igr_reader_run.restype = c.c_char_p
    lib.igr_reader_scratch.restype = c.c_void_p
    lib.igr_reader_high_water.restype = c.c_long
    lib.igr_reader_guards_intact.restype = c.c_int
    lib.igr_reader_callbacks.restype = None
    return lib


LIB = build()
L = H.L
L.pops_apply_all_config_patches.argtypes = [c.c_void_p, c.c_size_t, c.c_void_p]
L.pops_builtin_apply.argtypes = [c.c_uint16, c.c_void_p, c.c_size_t, c.c_void_p, c.c_uint32,
                                 c.c_size_t, c.c_void_p]
L.pops_apply_region.argtypes = [c.c_void_p, c.c_size_t, c.c_int, c.c_uint8, c.c_int]
L.pops_apply_reset_warmboot.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(c.c_uint32)]
L.pops_apply_padman.argtypes = [c.c_void_p, c.c_size_t]
L.pops_core_runtime_corrections_stage.argtypes = [c.c_uint32, c.c_void_p, c.c_size_t, c.c_uint32]
L.pops_fix_context_init_builtin.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t, c.c_uint16,
                                            c.c_uint8, c.c_uint8]
L.pops_fix_bind_progressive.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t, c.c_uint32, c.c_uint32]
L.pops_fix_require_progressive.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t]
L.pops_fix_finalize_video.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t, c.c_int, c.c_uint8]
L.pops_fix_stage.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t, c.c_void_p, c.c_size_t,
                             c.c_uint, c.c_int]
L.pops_module_irx_name_apply.argtypes = [c.c_void_p, c.c_size_t, c.c_void_p, c.c_size_t,
                                         c.POINTER(c.c_uint)]
L.pops_apply_slbb_vcd_check_bypass.argtypes = [c.c_void_p, c.c_size_t]
L.pops_resident_hook_pads.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32, c.c_uint32, c.c_uint32]
L.pops_resident_hook_widescreen.argtypes = [c.c_void_p, c.c_size_t, c.c_uint8, c.POINTER(H.Header)]
L.pops_resident_hook_progressive.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32, c.c_uint32]
L.pops_resident_progressive_interlace.argtypes = [c.c_void_p]
L.pops_resident_progressive_interlace.restype = c.c_uint32
L.pops_resident_hook_display.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]


class Rom(c.Structure):
    """PopsUserRomState (common/include/pops_modes_patches.h)."""
    _fields_ = [(name, c.c_uint8) for name in ("bios_all", "bios_game", "osd_all_a", "osd_all_b",
                                                "osd_game_a", "osd_game_b", "osd_off", "integrity",
                                                "no_fix", "abort", "game_dir_missing")]


L.pops_apply_all_config_patches_rom.argtypes = [c.c_void_p, c.c_size_t, c.c_void_p, c.POINTER(Rom)]
L.pops_user_bios_stage.argtypes = [c.c_void_p, c.c_size_t, c.c_void_p, c.c_size_t, c.c_int64,
                                   c.c_int, c.POINTER(Rom)]
L.pops_fix_context_rom_loaded.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t]
L.pops_fix_stage_rom.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t, c.c_void_p, c.c_size_t,
                                 c.c_uint, c.c_int, c.POINTER(Rom)]
L.pops_apply_bios_shell_edits_rom.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(Rom)]
L.pops_apply_region_rom.argtypes = [c.c_void_p, c.c_size_t, c.c_int, c.c_uint8, c.c_int,
                                    c.POINTER(Rom)]
USER_BIOS_ADDR, USER_BIOS_READ = 0x0024BC20, 0x0007FF90   # pops_modes_patches.h


def stage(core, which, data, size=None, core_size=None):
    buf = (c.c_uint8 * len(core)).from_buffer(core)
    raw = bytes(data)
    return LIB.pops_igr_skin_stage(buf, len(core) if core_size is None else core_size, which,
                                   raw, len(raw) if size is None else size)


def slot_bytes(core, which):
    _, addr, size, _ = SLOTS[which]
    return bytes(core[addr - CORE:addr - CORE + size])


def skin_range(core):
    return bytes(core[FIRST - CORE:END - CORE])


def boundary_sizes(which):
    _, _, slot, biggest = SLOTS[which]
    return sorted({0, 1, biggest - 1, biggest, biggest + 1, slot, slot + 1})


_NOISE = random.Random(0x49475253).randbytes(CORE_SIZE)


class Native(unittest.TestCase):
    def test_table(self):
        for which, (name, addr, slot, biggest) in enumerate(SLOTS):
            got = LIB.pops_igr_skin_slot(which).contents
            self.assertEqual((got.name, got.addr, got.slot_size, got.max_size),
                             (name.encode(), addr, slot, biggest))
        self.assertFalse(LIB.pops_igr_skin_slot(-1))
        self.assertFalse(LIB.pops_igr_skin_slot(3))
        # Back to back, in file order BG, NO, YES.
        self.assertEqual(SLOTS[BG][1], FIRST)
        self.assertEqual(SLOTS[BG][1] + SLOTS[BG][2], SLOTS[NO][1])
        self.assertEqual(SLOTS[NO][1] + SLOTS[NO][2], SLOTS[YES][1])
        self.assertEqual(SLOTS[YES][1] + SLOTS[YES][2], END)

    def test_boundary_sizes(self):
        rng = random.Random(1)
        accepted = refused = 0
        for which, (_, addr, slot, biggest) in enumerate(SLOTS):
            for size in boundary_sizes(which):
                core = bytearray(_NOISE)
                data = rng.randbytes(size)
                rc = stage(core, which, data)
                off = addr - CORE
                if size <= biggest:
                    self.assertEqual(rc, 0, (which, size))
                    self.assertEqual(slot_bytes(core, which), data + bytes(slot - size), (which, size))
                    self.assertEqual(bytes(core[:off]), _NOISE[:off])
                    self.assertEqual(bytes(core[off + slot:]), _NOISE[off + slot:])
                    accepted += 1
                else:
                    self.assertEqual(rc, -errno.EFBIG, (which, size))
                    self.assertEqual(bytes(core), _NOISE, (which, size))
                    refused += 1
        # BG: 0, 1, max-1, max accepted, max+1 (= slot+1) refused; its slot is
        # its max. NO and YES: four accepted, max+1, slot, slot+1 refused.
        self.assertEqual((accepted, refused), (12, 7))

    def test_short_core_is_refused_untouched(self):
        for which, (_, addr, slot, biggest) in enumerate(SLOTS):
            end = addr - CORE + slot
            for core_size in (0, addr - CORE - 1, addr - CORE, end - 1):
                core = bytearray(_NOISE[:end])
                self.assertEqual(stage(core, which, b"\x55" * 16, core_size=core_size), -errno.ERANGE)
                # Too big as well: still the range error, still untouched.
                self.assertEqual(stage(core, which, bytes(biggest + 1), core_size=core_size),
                                 -errno.ERANGE)
                self.assertEqual(bytes(core), _NOISE[:end])
            core = bytearray(_NOISE[:end])
            self.assertEqual(stage(core, which, b"\x55" * 16), 0)   # the slot is the last thing in it
            self.assertEqual(slot_bytes(core, which), b"\x55" * 16 + bytes(slot - 16))

    def test_arguments(self):
        core = bytearray(_NOISE)
        buf = (c.c_uint8 * len(core)).from_buffer(core)
        self.assertEqual(LIB.pops_igr_skin_stage(None, len(core), BG, b"x", 1), -errno.EINVAL)
        self.assertEqual(LIB.pops_igr_skin_stage(buf, len(core), -1, b"x", 1), -errno.EINVAL)
        self.assertEqual(LIB.pops_igr_skin_stage(buf, len(core), 3, b"x", 1), -errno.EINVAL)
        self.assertEqual(LIB.pops_igr_skin_stage(buf, len(core), NO, None, 1), -errno.EINVAL)
        self.assertEqual(bytes(core), _NOISE)
        # A zero-length file needs no data pointer, and wipes the slot (quirk).
        self.assertEqual(LIB.pops_igr_skin_stage(buf, len(core), NO, None, 0), 0)
        self.assertEqual(slot_bytes(core, NO), bytes(SLOTS[NO][2]))

    def test_neither_the_slot_nor_the_file_is_inspected(self):
        """No TIM2 magic is wanted in the slot or in the file (the original
        checks neither)."""
        for fill in (b"\x00", b"\xff"):
            core = bytearray(fill * CORE_SIZE)
            self.assertEqual(stage(core, YES, b"not a TIM2 file"), 0)
            self.assertEqual(slot_bytes(core, YES), b"not a TIM2 file" + bytes(SLOTS[YES][2] - 15))

    def test_three_files_fill_one_run_and_nothing_else(self):
        rng = random.Random(2)
        core = bytearray(_NOISE)
        want = b""
        for which, (_, _, slot, biggest) in enumerate(SLOTS):
            data = rng.randbytes(rng.randrange(1, biggest + 1))
            self.assertEqual(stage(core, which, data), 0)
            want += data + bytes(slot - len(data))
        self.assertEqual(skin_range(core), want)
        self.assertEqual(bytes(core[:FIRST - CORE]), _NOISE[:FIRST - CORE])
        self.assertEqual(bytes(core[END - CORE:]), _NOISE[END - CORE:])


# ---------------------------------------------------------------------------
# The original's loader as a model, and what launcHER's reader is meant to
# leave. Both work on the device model in trace_original_pops_igr_skin.py.
# The model of the original is checked against the original itself in the
# Original class; without the inputs it stands for what was measured there.

def original_file(which, value):
    """One file through the original's code: (what it prints, the slot's new
    bytes or None, how many bytes below the slot it also zeroes)."""
    _, _, slot, biggest = SLOTS[which]
    if value is None:
        return "NOT FOUND", None, 0
    handle = T.as_file(value).open()
    size = handle.lseek(0, T.SEEK_END)
    if size > biggest:                    # signed; a negative size passes
        return "TOO BIG", None, 0
    handle.lseek(0, T.SEEK_SET)           # result not checked
    _count, chunk = handle.read(slot)     # one read of the whole slot, count not checked
    filled = bytearray(chunk + bytes(slot - len(chunk)))
    if size >= 0:
        filled[size:] = bytes(slot - size)   # memset(slot + size, 0, slot - size)
        return "LOADED", bytes(filled), 0
    return "LOADED", bytes(slot), -size      # the same fill, started below the slot


def original_model(core, files):
    """files: {which: bytes or SkinFile}. The core the original leaves and
    its three outcomes, BG, NO, YES in that order."""
    out = bytearray(core)
    outcomes = []
    for which, (_, addr, slot, _) in enumerate(SLOTS):
        outcome, filled, below = original_file(which, files.get(which))
        outcomes.append(outcome)
        if filled is not None:
            off = addr - CORE
            out[off - below:off + slot] = bytes(below) + filled
    return bytes(out), outcomes


SAME, SIZE_FAILED, PIECES = "same", "size query failed", "pieces"


def launcher_file(which, value):
    """What launcHER's reader is meant to do with one file: (outcome, the
    slot's new bytes or None). The original's result, except:
      - a failed size query leaves the slot alone (the original zeroes the
        slot and bytes below it);
      - the file is read until its size has arrived or the device returns
        nothing, so a device that hands it over in pieces fills the slot
        (the original's one unchecked read keeps the first piece only)."""
    _, _, slot, biggest = SLOTS[which]
    if value is None:
        return "NOT FOUND", None
    f = T.as_file(value)
    size = len(f.data) if f.size is None else f.size
    if size < 0:
        return SIZE_FAILED, None
    if size > biggest:
        return "TOO BIG", None
    got = 0
    if f.rewind is None and f.per_read != 0:
        got = min(size, len(f.data), size if f.total is None else f.total)
    return "LOADED", f.data[:got] + bytes(slot - got)


def launcher_expect(core, files):
    out = bytearray(core)
    outcomes = []
    for which, (_, addr, slot, _) in enumerate(SLOTS):
        outcome, filled = launcher_file(which, files.get(which))
        outcomes.append(outcome)
        if filled is not None:
            out[addr - CORE:addr - CORE + slot] = filled
    return bytes(out), outcomes


def device_cases():
    """(family, which, SkinFile, relation) for devices that misbehave.
    relation: SAME where launcHER's reader must leave the original's slot,
    SIZE_FAILED and PIECES for the two listed differences."""
    rng = random.Random(0x44455649)
    out = []
    for which, (_, _, slot, biggest) in enumerate(SLOTS):
        middle = 70000 if which == BG else 100          # BG: more than one 64 KiB request
        # The device stops for good, with end of file or an error after.
        for size in (biggest, biggest // 2 + 1, middle):
            for total in (0, 1, size // 2, size - 1):
                for after in (0, -5):
                    out.append(("stops", which,
                                T.SkinFile(rng.randbytes(size), total=total, after=after), SAME))
        # The size query and the data disagree.
        for length, size in ((100, biggest), (biggest, 100), (50, 0), (0, 50),
                             (biggest + 1, biggest), (16, biggest + 1), (2 * slot, 1)):
            out.append(("size", which, T.SkinFile(rng.randbytes(length), size=size), SAME))
        # The seek back to the start fails; the position stays at the end.
        for rewind in (-1, -5):
            for size in (biggest, 1):
                out.append(("rewind", which, T.SkinFile(rng.randbytes(size), rewind=rewind), SAME))
        # Reads report more than was asked for.
        for extra in (1, 4096):
            for size in (biggest, 9):
                out.append(("extra", which, T.SkinFile(rng.randbytes(size), extra=extra), SAME))
        # One piece is the whole file: nothing differs.
        out.append(("pieces", which, T.SkinFile(rng.randbytes(middle), per_read=middle), SAME))
        # The size query fails.
        for result in (-1, -5, -16, -4096):
            out.append(("size failed", which, T.SkinFile(rng.randbytes(64), size=result), SIZE_FAILED))
        # The device hands the file over in pieces.
        for size, per_read in ((biggest, 4096), (middle, 7 if which else 65536), (300, 1)):
            out.append(("pieces", which, T.SkinFile(rng.randbytes(size), per_read=per_read), PIECES))
    return out


def device_runs():
    """The cases three to a run, one file per slot: [(family, relation,
    {which: SkinFile})]."""
    cases = device_cases()
    per = [[case for case in cases if case[1] == which] for which in range(3)]
    assert len(per[0]) == len(per[1]) == len(per[2])
    runs = []
    for bg, no, yes in zip(*per):
        assert bg[0] == no[0] == yes[0] and bg[3] == no[3] == yes[3]
        runs.append((bg[0], bg[3], {BG: bg[2], NO: no[2], YES: yes[2]}))
    return runs


def named(files, prefix):
    return {prefix + SLOTS[which][0]: data for which, data in files.items()}


OPEN_FN = c.CFUNCTYPE(c.c_int, c.c_char_p, c.c_int)
LSEEK_FN = c.CFUNCTYPE(c.c_longlong, c.c_int, c.c_longlong, c.c_int)
READ_FN = c.CFUNCTYPE(c.c_longlong, c.c_int, c.c_void_p, c.c_size_t)
CLOSE_FN = c.CFUNCTYPE(c.c_int, c.c_int)
READER_OUTCOME = {"NOT FOUND": "NOT FOUND", "TOO BIG !": "TOO BIG", "LOADED": "LOADED",
                  "size query failed": SIZE_FAILED, "not staged": "NOT STAGED",
                  "path too long": "PATH TOO LONG"}


class ReaderHost:
    """launcHER's pops_stage_igr_skin over a {path: bytes or SkinFile} table."""

    def __init__(self):
        self._callbacks = (OPEN_FN(self._open), LSEEK_FN(self._lseek), READ_FN(self._read),
                           CLOSE_FN(self._close))
        LIB.igr_reader_callbacks(*self._callbacks)
        self.scratch = LIB.igr_reader_scratch()

    def _open(self, path, flags):
        path = path.decode("latin1")
        f = self.files.get(path)
        fd = -2
        if f is not None:
            fd = self.next_fd
            self.next_fd += 1
            self.handles[fd] = T.as_file(f).open()
        self.events.append(("open", path, flags, fd))
        return fd

    def _lseek(self, fd, offset, whence):
        if fd not in self.handles:
            self.events.append(("lseek on a closed handle", fd))
            return -1
        pos = self.handles[fd].lseek(offset, whence)
        self.events.append(("lseek", fd, offset, whence, pos))
        return pos

    def _read(self, fd, buffer, want):
        self.reads += 1
        if fd not in self.handles or self.reads > READ_CAP:
            self.runaway = True       # a reader that never stops, or reads a closed handle
            return -1
        count, chunk = self.handles[fd].read(want)
        if chunk:
            c.memmove(buffer, chunk, len(chunk))
        self.events.append(("read", fd, buffer - self.scratch, want, count))
        return count

    def _close(self, fd):
        self.events.append(("close", fd, fd in self.handles))
        self.handles.pop(fd, None)
        return 0

    def run(self, core, files, directory, core_size=None):
        self.files, self.handles, self.events = files, {}, []
        self.next_fd, self.reads, self.runaway = 3, 0, False
        out = bytearray(core)
        array = (c.c_uint8 * len(out)).from_buffer(out)
        log = LIB.igr_reader_run(array, len(out) if core_size is None else core_size,
                                 directory.encode("latin1")).decode("latin1")
        del array
        outcomes = []
        for line in log.splitlines():
            text = line.rsplit(": ", 1)[1] if ": " in line else line
            key = [k for k in READER_OUTCOME if text.startswith(k)]
            outcomes.append(READER_OUTCOME[key[0]] if key else line)
        return {"core": bytes(out), "events": self.events, "log": log, "outcomes": outcomes,
                "left_open": sorted(self.handles), "runaway": self.runaway,
                "high_water": LIB.igr_reader_high_water(),
                "guards_intact": LIB.igr_reader_guards_intact()}


READER = ReaderHost()


def check_reader_calls(test, r, files, directory, label=None):
    """What every run of the reader must keep to, whatever the device does:
    the three files in the original's order, read only, each opened handle
    closed once and never used after; the size asked before anything is
    read; nothing read from a file that is too big or whose size query
    failed; every read inside the file's limit; the scratch buffer never
    written past the largest file."""
    test.assertFalse(r["runaway"], label)
    test.assertEqual(r["left_open"], [], label)
    test.assertTrue(r["guards_intact"], label)
    test.assertLessEqual(r["high_water"], max(s[3] for s in SLOTS), label)
    events = r["events"]
    opens = [e for e in events if e[0] == "open"]
    test.assertEqual([(e[1], e[2]) for e in opens],
                     [(directory + s[0], O_RDONLY) for s in SLOTS], label)
    position = 0
    for which, (name, _, _, biggest) in enumerate(SLOTS):
        test.assertEqual(events[position][:2], ("open", directory + name), label)
        fd = events[position][3]
        position += 1
        if (directory + name) not in files:
            test.assertLess(fd, 0, label)
            continue
        mine = []
        while position < len(events) and events[position][0] != "open":
            mine.append(events[position])
            position += 1
        test.assertTrue(all(e[1] == fd for e in mine), (label, mine))
        test.assertEqual(mine[0][:4], ("lseek", fd, 0, T.SEEK_END), label)
        test.assertEqual(mine[-1], ("close", fd, True), label)
        test.assertEqual([e[0] for e in mine].count("close"), 1, label)
        size = mine[0][4]
        middle = mine[1:-1]
        if size < 0 or size > biggest:
            test.assertEqual(middle, [], (label, name))      # nothing but the size was asked
            continue
        test.assertTrue(middle, (label, name))                # an accepted file is rewound
        test.assertEqual(middle[0][:4], ("lseek", fd, 0, T.SEEK_SET), (label, name))
        got = 0
        for e in middle[1:]:
            test.assertEqual(e[0], "read", (label, name))
            _, _, offset, want, count = e
            test.assertEqual(offset, got, (label, name))      # contiguous from the buffer's start
            test.assertTrue(0 < want <= 65536 and got + want <= size, (label, name, e))
            got += min(count, want) if count > 0 else 0
    test.assertEqual(position, len(events), label)


class Reader(unittest.TestCase):
    """launcHER's reader, executed: pops_stage_igr_skin as handler_pops.c has
    it, on the host, over modelled devices. No inputs needed; the model of
    the original used here is the one the Original class holds the original
    to."""

    def run_reader(self, files, prefix, core=_NOISE, core_size=None, label=None):
        r = READER.run(core, named(files, prefix), prefix, core_size=core_size)
        check_reader_calls(self, r, named(files, prefix), prefix, label)
        return r

    def same_as_the_original(self, files, prefix, label):
        want, outcomes = original_model(_NOISE, files)
        self.assertEqual(launcher_expect(_NOISE, files), (want, outcomes), label)
        r = self.run_reader(files, prefix, label=label)
        self.assertEqual(r["outcomes"], outcomes, label)
        self.assertTrue(r["core"] == want, label)
        return r

    def test_boundary_sizes(self):
        rng = random.Random(0x52454144)
        sizes = [boundary_sizes(which) + [SLOTS[which][2] * 2] for which in range(3)]
        seen, used = {}, set()
        for prefix in T.PREFIX.values():
            for i in range(8):
                files = {}
                for which in range(3):
                    size = sizes[which][(i + 2 * which) % len(sizes[which])]
                    files[which] = rng.randbytes(size)
                    used.add((which, size))
                r = self.same_as_the_original(files, prefix, (prefix, i))
                for which, outcome in enumerate(r["outcomes"]):
                    seen[(which, outcome)] = seen.get((which, outcome), 0) + 1
        # Every boundary size was used (BG's slot is its limit, so it has
        # six distinct sizes, the other two eight), and both outcomes were
        # seen for each file.
        self.assertEqual([len(pool) for pool in sizes], [6, 8, 8])
        self.assertEqual(used, {(which, size) for which in range(3) for size in sizes[which]})
        for which in range(3):
            self.assertGreaterEqual(seen[(which, "LOADED")], 8, which)
            self.assertGreaterEqual(seen[(which, "TOO BIG")], 4, which)

    def test_absent_files_and_random_sets(self):
        rng = random.Random(0x52534554)
        r = self.same_as_the_original({}, "mass:/POPS/", "none")
        self.assertEqual((r["core"], r["outcomes"]), (_NOISE, ["NOT FOUND"] * 3))
        for n in range(40):
            files = {}
            for which, (_, _, slot, biggest) in enumerate(SLOTS):
                pick = rng.random()
                if pick < 0.3:
                    continue
                size = rng.randrange(0, biggest + 1) if pick < 0.85 else rng.randrange(biggest + 1, 2 * slot)
                files[which] = rng.randbytes(size)
            self.same_as_the_original(files, rng.choice(["mass:/POPS/", "pfs1:/POPS/", "mass:/"]), n)

    def test_a_zero_byte_file_wipes_the_slot(self):
        """The copied quirk, through the reader: opened, sized, staged."""
        for which in range(3):
            r = self.same_as_the_original({which: b""}, "mass:/POPS/", which)
            self.assertEqual(slot_bytes(r["core"], which), bytes(SLOTS[which][2]))
            self.assertEqual(r["outcomes"][which], "LOADED")

    def test_a_file_that_is_too_big_is_never_read(self):
        for which, (_, _, slot, biggest) in enumerate(SLOTS):
            for size in (biggest + 1, slot + 1, 2 * slot):
                r = self.same_as_the_original({which: bytes([which + 1]) * size}, "mass:/POPS/",
                                              (which, size))
                self.assertEqual(r["core"], _NOISE)
                self.assertEqual([e[0] for e in r["events"]].count("read"), 0)
                self.assertEqual(r["high_water"], 0)

    def test_misbehaving_devices_where_launcher_matches(self):
        """A device that stops for good (end of file or an error), a size
        query that disagrees with the data, a failed seek back to the start,
        reads that over-report: the original's slot, byte for byte."""
        families = {}
        for family, relation, files in device_runs():
            if relation != SAME:
                continue
            for prefix in T.PREFIX.values():
                self.same_as_the_original(files, prefix, (family, prefix))
            families[family] = families.get(family, 0) + 1
        self.assertEqual(families, {"stops": 24, "size": 7, "rewind": 4, "extra": 4, "pieces": 1})

    def test_a_failed_size_query_leaves_the_core_alone(self):
        """Not the original's result (it zeroes the slot and bytes below
        it): launcHER asks nothing more of the file and closes it."""
        ran = 0
        for family, relation, files in device_runs():
            if relation != SIZE_FAILED:
                continue
            r = self.run_reader(files, "mass:/POPS/", label=family)
            self.assertEqual(r["core"], _NOISE)
            self.assertEqual(r["outcomes"], [SIZE_FAILED] * 3)
            self.assertEqual(launcher_expect(_NOISE, files)[0], _NOISE)
            self.assertNotEqual(original_model(_NOISE, files)[0], _NOISE)
            ran += 1
        self.assertEqual(ran, 4)

    def test_a_file_delivered_in_pieces_is_read_to_its_end(self):
        """Not the original's result (its one read keeps the first piece):
        launcHER asks again until the file's size has arrived."""
        ran = 0
        for family, relation, files in device_runs():
            if relation != PIECES:
                continue
            want, outcomes = launcher_expect(_NOISE, files)
            r = self.run_reader(files, "pfs1:/POPS/", label=family)
            self.assertTrue(r["core"] == want, family)
            self.assertEqual(r["outcomes"], outcomes)
            for which, f in files.items():
                self.assertEqual(slot_bytes(r["core"], which),
                                 f.data + bytes(SLOTS[which][2] - len(f.data)))
                first = slot_bytes(original_model(_NOISE, files)[0], which)
                self.assertEqual(first, f.data[:f.per_read] + bytes(SLOTS[which][2] - f.per_read))
            ran += 1
        self.assertEqual(ran, 3)

    def test_requests_are_at_most_64k_and_stop_at_the_size(self):
        data = random.Random(7).randbytes(SLOTS[BG][3])
        r = self.run_reader({BG: data}, "mass:/POPS/")
        reads = [(e[2], e[3], e[4]) for e in r["events"] if e[0] == "read"]
        want = [(off, min(65536, len(data) - off), min(65536, len(data) - off))
                for off in range(0, len(data), 65536)]
        self.assertEqual(reads, want)
        self.assertEqual(r["high_water"], len(data))
        self.assertEqual(slot_bytes(r["core"], BG), data)

    def test_a_short_core_is_left_alone_and_the_files_closed(self):
        files = {which: bytes([0x40 + which]) * 32 for which in range(3)}
        for core_size in (0, FIRST - CORE, SLOTS[BG][1] - CORE + SLOTS[BG][2] - 1,
                          SLOTS[NO][1] - CORE + SLOTS[NO][2]):
            r = self.run_reader(files, "mass:/POPS/", core_size=core_size, label=core_size)
            want = bytearray(_NOISE)
            staged = []
            for which, (_, addr, slot, _) in enumerate(SLOTS):
                if core_size >= addr - CORE + slot:
                    want[addr - CORE:addr - CORE + slot] = files[which] + bytes(slot - 32)
                    staged.append("LOADED")
                else:
                    staged.append("NOT STAGED")
            self.assertTrue(r["core"] == bytes(want), core_size)
            self.assertEqual(r["outcomes"], staged, core_size)

    def test_an_over_long_folder_opens_nothing(self):
        files = {which: b"\x01" * 8 for which in range(3)}
        # BG and NO are ten characters, YES eleven: at this length the first
        # two paths are the longest that fit and the third does not.
        folder = "mass:/" + "d" * (PATH_MAX - 1 - 10 - 7) + "/"
        self.assertEqual(len(folder) + 10, PATH_MAX - 1)
        r = READER.run(_NOISE, named(files, folder), folder)
        self.assertEqual([e[1] for e in r["events"] if e[0] == "open"],
                         [folder + SLOTS[BG][0], folder + SLOTS[NO][0]])
        self.assertEqual(r["outcomes"], ["LOADED", "LOADED", "PATH TOO LONG"])
        self.assertEqual(slot_bytes(r["core"], YES), slot_bytes(_NOISE, YES))
        self.assertEqual((r["left_open"], r["runaway"]), ([], False))
        r = READER.run(_NOISE, {}, folder + "d")
        self.assertEqual((r["events"], r["core"] == _NOISE), ([], True))
        self.assertEqual(r["outcomes"], ["PATH TOO LONG"] * 3)

    def test_the_slice_compiled_here_is_the_reader(self):
        """The host build takes the function whole, changing only the
        scratch address; nothing else in the slice does I/O."""
        reader = reader_source()
        self.assertTrue(reader.startswith(READER_BEGIN))
        self.assertEqual(reader.count("\nstatic "), 0)          # one function
        self.assertEqual(reader.count(SCRATCH_LITERAL), 1)
        for call, count in (("open(", 1), ("lseek(", 2), ("read(", 1), ("close(", 3)):
            self.assertEqual(len(re.findall(r"(?<![A-Za-z0-9_])" + re.escape(call), reader)),
                             count, call)


# Words of POPS's pad-combination check (FUN_002289e0) that the IGR commands
# and launcHER's direct exit rewrite. The dialog is opened by the code at
# 0x228a5c, reached when the `bne` at 0x228a54 falls through.
IGR_WORDS = {0x00228A20: 0x30A30904, 0x00228A50: 0x24020904, 0x00228A54: 0x14620018,
             0x00228A58: 0x0000102D, 0x00228A5C: 0x3C110086, 0x00228A60: 0x24030080,
             0x00228A64: 0x2622A980, 0x00228A68: 0x0000202D, 0x0020C0A4: 0x0C08B44C}
OPENS_DIALOG = (0x3C110086, 0x24030080, 0x2622A980, 0x0000202D)
DIRECT_EXIT = (0x24020001, 0x10000015, 0x00000000, 0x00000000)
IGR_SETTINGS = [("", "direct"), ("$NOIGR", "off"), ("$IGR0", "dialog"), ("$IGR1", "dialog"),
                ("$IGR2", "dialog"), ("$IGR3", "jump"), ("$IGR4", "jump"), ("$IGR5", "jump")]


def config(line):
    cfg = H.F.PopsConfig()
    L.pops_config_init(c.byref(cfg))
    if line:
        L.pops_config_parse_line(c.byref(cfg), line.encode())
    return cfg


def igr_outcome(core):
    """What the staged pad-combination check does once the combination is
    held: 'dialog' (Sony's dialog, where the skin shows), 'direct'
    (launcHER's immediate exit), 'jump' ($IGR3..5: straight to 0x20c08c) or
    'off' (the branch at 0x228a54 is always taken)."""
    branch = H.u32(core, 0x00228A54)
    tail = tuple(H.u32(core, a) for a in (0x00228A5C, 0x00228A60, 0x00228A64, 0x00228A68))
    if branch >> 16 == 0x1000:
        return "off"
    if branch != 0x14620018:
        return "unknown"
    if tail == OPENS_DIALOG:
        return "dialog"
    if tail == DIRECT_EXIT:
        return "direct"
    if tail[:2] == (0x08083023, 0x00000000):
        return "jump"
    return "unknown"


class Dialog(unittest.TestCase):
    """The skin is only seen when Sony's dialog is: under $IGR0..2."""

    def check(self, make_core):
        for line, want in IGR_SETTINGS:
            core = make_core()
            cfg = config(line)
            self.assertEqual(L.pops_apply_all_config_patches(H.buf(core), len(core), c.byref(cfg)), 0, line)
            self.assertEqual(igr_outcome(core), want, line)

    def test_synthetic_core(self):
        def make():
            core = bytearray(CORE_SIZE)
            for addr, word in IGR_WORDS.items():
                H.put32(core, addr, word)
            return core
        self.assertEqual(igr_outcome(make()), "dialog")   # POPS as shipped
        self.check(make)

    @unittest.skipUnless(HAVE_CORE, "POPS_TEST_ELF not set")
    def test_real_core(self):
        pristine = H.real_core()
        for addr, word in IGR_WORDS.items():
            self.assertEqual(H.u32(pristine, addr), word, hex(addr))
        self.check(lambda: bytearray(pristine))


PLAN = (c.c_uint8 * 512)()   # room for a PopsBuiltinPlan; its contents are not used here


def overlaps(addr, length):
    return addr < END and addr + length > FIRST


class Staging(unittest.TestCase):
    """Nothing else launcHER stages may land in the slots, or the order of
    the skin against it would matter."""

    def test_builtin_entries_write_outside_the_slots(self):
        count = c.c_uint16.in_dll(L, "pops_builtin_op_count").value
        ops = (Op * count).in_dll(L, "pops_builtin_ops")
        core_ops = [op for op in ops if op.kind == 0]
        self.assertGreater(len(core_ops), 200)
        for op in core_ops:
            self.assertFalse(overlaps(op.addr, op.len), hex(op.addr))
        # All of them end far below the first slot.
        self.assertLess(max(op.addr + op.len for op in core_ops), 0x0021B000)
        # And applied: every entry over a marked core.
        marked = b"\xa5" * CORE_SIZE
        for entry in range(1, 625):
            core = bytearray(marked)
            self.assertEqual(L.pops_builtin_apply(entry, H.buf(core), len(core), None, 0, 0, PLAN), 0, entry)
            self.assertEqual(skin_range(core), skin_range(marked), entry)

    def test_builtin_entry_and_skin_commute(self):
        """The original applies a fingerprint-matched entry before the skin
        and a $VCDID_n entry after it; launcHER applies either before. Both
        orders leave the same core, for every entry."""
        rng = random.Random(0x434F4D4D)
        skin = [rng.randbytes(s[3]) for s in SLOTS]
        marked = bytes(b"\xa5" * CORE_SIZE)
        for entry in range(1, 625):
            first = bytearray(marked)
            self.assertEqual(L.pops_builtin_apply(entry, H.buf(first), len(first), None, 0, 0, PLAN), 0)
            second = bytearray(marked)
            for which in range(3):
                self.assertEqual(stage(first, which, skin[which]), 0)
                self.assertEqual(stage(second, which, skin[which]), 0)
            self.assertEqual(L.pops_builtin_apply(entry, H.buf(second), len(second), None, 0, 0, PLAN), 0)
            self.assertTrue(first == second, entry)

    def test_always_on_hooks_write_outside_the_slots(self):
        core = H.synthetic_core()
        before = bytes(core)
        self.assertEqual(L.pops_resident_hook_gp1(H.buf(core), len(core), H.BASE + 0x80), 0)
        self.assertEqual(L.pops_resident_hook_recompiler(H.buf(core), len(core), H.RECOMPILER_ENTRY), 0)
        self.assertEqual(L.pops_resident_hook_guards(H.buf(core), len(core), H.header(H.ENTRIES)), 0)
        self.assertEqual(L.pops_apply_always_on_pokes(H.buf(core), len(core)), 0)
        self.assertNotEqual(bytes(core), before)
        self.assertEqual(skin_range(core), skin_range(before))

    def test_unguarded_scans_stay_outside_the_slots(self):
        # The opcode pass rewrites every `lw`/`sw` upper halfword it scans:
        # a core made of nothing else shows its whole reach.
        core = bytearray(struct.pack("<HH", 0x0000, 0x8C00) * (CORE_SIZE // 4))
        before = bytes(core)
        self.assertGreater(L.pops_apply_opcode_pass(H.buf(core), len(core)), 70000)
        self.assertEqual(skin_range(core), skin_range(before))
        # $RESET_WARMBOOT rewrites listed BIOS call stubs: a core made of one.
        stub = struct.pack("<III", 0x240A00B0, 0x01400008, 0x24090052)
        core = bytearray((stub * (CORE_SIZE // 12 + 1))[:CORE_SIZE])
        before = bytes(core)
        vector = c.c_uint32(0)
        self.assertGreaterEqual(L.pops_apply_reset_warmboot(H.buf(core), len(core), c.byref(vector)), 0)
        self.assertNotEqual(bytes(core), before)
        self.assertEqual(skin_range(core), skin_range(before))


# One line per command family the parser knows; what matters here is only
# where the staged writes land.
COMMANDS = (["$COMPATIBILITY_0x%02X" % n for n in range(1, 8)] +
            ["$IGR%d" % n for n in range(6)] +
            ["$RECOMPILER_ADDON_%d" % n for n in range(5)] +
            ["$CODECACHE_ADDON_%d" % n for n in range(3)] +
            ["$NOIGR", "$HDTVFIX", "$NOHDTVFIX", "$FORCEPAL", "$FORCENTSC", "$NOPAL", "$NTSC2PAL",
             "$PAL2NTSC", "$FAKELC", "$SUBCDSTATUS", "$NOVMC0", "$NOVMC1",
             "$UNDO_COMPATIBILITY_CODES", "$UNDO_GAME_FIXES", "$UNDO_LIBCRYPT_FIX",
             "$UNDO_MUTE_CDDA", "$MUTE_ALL", "$MUTE_CDDA", "$MUTE_VAB", "$NOBOOT", "$NODITHER",
             "$DITHER_OFF", "$SMOOTH", "$SCANLINES", "$WIDESCREEN", "$ULTRA_WIDESCREEN",
             "$EYEFINITY", "$SAFEMODE", "$SAFEMODE2", "$NOSAFEMODE", "$CACHE1", "$FASTMIPS",
             "$SLOWMIPS", "$D2LS", "$D2LS_ALT", "$XPOS_8", "$YPOS_8", "$DX_8", "$DY_8",
             "$DW_640", "$DH_448", "$MAGH_3", "$MAGV_1", "$LEFTADJ_8", "$DWSTRETCH_8",
             "$DWCROP_8", "$SET_TIMINGS", "$RESET_WARMBOOT", "$KILL_PADMAN", "$LOAD_PADMAN",
             "$ORIGINAL_OPCODES", "$BREAKPOINT0", "$BREAKPOINT1", "$NOPAD0", "$NOPAD1",
             "$PAD0ID_0X41", "$PAD1ID_0X73", "$ROLLBACK", "$BIOS"])

MODULE_NAMES = ["sio2man", "padman", "Sound_Device_Library", "sdr_driver", "dev9", "atad", "hdd",
                "pfs", "IOX/File_Manager", "IOX/File_Manager_Rpc", "Poweroff_Handler"]
RES_F_PAD_ID, RES_F_D2LS = 1 << 3, 1 << 4
RUNTIME_MASKS = (1, 2, 4, 8, 16, 31)


def resident_header():
    """Entry addresses inside the resident area; the hooks only form jumps
    to them."""
    h = H.header(H.ENTRIES)
    for n, field in enumerate(("display_entry", "progressive_entry", "pad_read_entry",
                               "pad_read_exit", "gte_scale_entry", "gte_divide_entry",
                               "gte_ultra_entry")):
        setattr(h, field, H.BASE + 0x1000 + 0x40 * n)
    for i, entry in enumerate(H.EMIT_ENTRIES):
        h.recompiler_emit[i] = entry
    return h


def fix_file(kind, slot, modes=(), payload=b"", address=0, hook=0):
    """A synthetic PATCH_n.BIN or TROJAN_n.BIN (the 64-byte header
    tools/test_pops_fix_files.py builds, and a payload)."""
    header = bytearray(64)
    if kind == "PATCH":
        header[:8] = ("PATCH_%d\0" % slot).encode()
        struct.pack_into("<6I", header, 8, 1 if modes else 0, 0x10001, address, 0, 0, len(payload))
        header[32:37] = b"owned"
        header[56:56 + len(modes)] = bytes(modes)
    else:
        header[:8] = ("TROJAN_%d" % slot).encode()
        struct.pack_into("<6I", header, 8, 0, 0x10001, address, address, hook, len(payload))
    return bytes(header) + payload


def module_irx(name):
    data = bytearray(0x200)
    data[0x8E:0x8E + len(name)] = name.encode()
    return data


def always_on(core):
    return [L.pops_resident_hook_gp1(H.buf(core), len(core), H.BASE + 0x80),
            L.pops_resident_hook_recompiler(H.buf(core), len(core), H.RECOMPILER_ENTRY),
            L.pops_resident_hook_guards(H.buf(core), len(core), H.header(H.ENTRIES)),
            L.pops_apply_always_on_pokes(H.buf(core), len(core))]


@unittest.skipUnless(HAVE_CORE, "POPS_TEST_ELF not set")
class RealCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pristine = bytes(H.real_core())
        core = bytearray(cls.pristine)
        # launchPOPS's order up to where the skin is staged (no runtime
        # corrections and no built-in entry here; both are added below).
        cls.steps = [("core patches", L.pops_core_patches_stage(CORE, H.buf(core), len(core), (1 << 7) - 1))]
        cls.patched = bytes(core)
        cls.steps += list(zip(("gp1 hook", "recompiler hook", "guards", "always-on pokes"), always_on(core)))
        cls.staged = bytes(core)

    def test_sonys_own_files_fill_the_slots(self):
        """POPS carries three complete TIM2 files exactly where the original
        writes, and the original's size limits are their sizes."""
        for which, (_, addr, slot, biggest) in enumerate(SLOTS):
            off = addr - CORE
            magic, version, fmt, pictures = struct.unpack_from("<4sBBH", self.pristine, off)
            self.assertEqual((magic, pictures), (b"TIM2", 1), hex(addr))
            total, clut, image, header = struct.unpack_from("<IIIH", self.pristine, off + 16)
            self.assertEqual(16 + total, biggest, hex(addr))
            self.assertEqual(total, header + image + clut)
            self.assertEqual(self.pristine[off + biggest:off + slot], bytes(slot - biggest))
            image_type, width, height = struct.unpack_from("<BHH", self.pristine, off + 16 + 19)
            self.assertEqual((image_type, width, height),
                             (2, 400, 260) if which == BG else (2, 74, 34))
        self.assertEqual(self.pristine[END - CORE:END - CORE + 4], b"TIM2")   # Sony's next file

    def test_stages_before_the_skin_leave_the_slots_alone(self):
        for name, rc in self.steps:
            self.assertEqual(rc, 0, name)
        self.assertNotEqual(self.staged, self.pristine)
        self.assertEqual(skin_range(self.staged), skin_range(self.pristine))
        # With every runtime-corrections mask as well (their place is
        # straight after the core patches).
        for mask in RUNTIME_MASKS:
            core = bytearray(self.patched)
            self.assertEqual(L.pops_core_runtime_corrections_stage(CORE, H.buf(core), len(core), mask), 0)
            self.assertEqual(always_on(core), [0, 0, 0, 0], mask)
            self.assertNotEqual(bytes(core), self.staged)
            self.assertEqual(skin_range(core), skin_range(self.pristine), mask)

    def skin_files(self):
        rng = random.Random(3)
        return {which: rng.randbytes(SLOTS[which][3] - which) for which in range(3)}

    def staged_with_skin(self, base=None):
        """The skin as launchPOPS stages it: through the reader."""
        files = self.skin_files()
        r = READER.run(self.staged if base is None else base, named(files, "mass:/POPS/"), "mass:/POPS/")
        check_reader_calls(self, r, named(files, "mass:/POPS/"), "mass:/POPS/")
        self.assertEqual(r["outcomes"], ["LOADED"] * 3)
        self.assertEqual(skin_range(r["core"]),
                         b"".join(files[w] + bytes(SLOTS[w][2] - len(files[w])) for w in range(3)))
        return bytearray(r["core"])

    def test_runtime_corrections_refuse_a_core_with_a_skin(self):
        """Why the skin has to come after them: the stage takes only the
        pristine or the core-patched image as a whole. One skin byte makes
        it refuse (-4, nothing written), which launchPOPS treats as fatal."""
        for which in range(3):
            core = bytearray(self.patched)
            self.assertEqual(stage(core, which, b"x"), 0)
            before = bytes(core)
            for mask in RUNTIME_MASKS:
                self.assertEqual(L.pops_core_runtime_corrections_stage(CORE, H.buf(core), len(core), mask),
                                 -4, (which, mask))
                self.assertEqual(bytes(core), before)

    def test_stages_after_the_skin_leave_it_alone(self):
        """Each later stage on its own over the staged core with a skin in
        place: the three slots keep the skin."""
        base = self.staged_with_skin()
        want = skin_range(base)
        self.assertNotEqual(want, skin_range(self.pristine))
        ran, interlaces = {}, []
        header = resident_header()

        def run(name, call):
            core = bytearray(base)
            rc = call(core)
            self.assertEqual(skin_range(core), want, name)
            ran.setdefault(name.split()[0], []).append(rc)
            return rc, core

        for line in COMMANDS:
            cfg = config(line)
            run("command " + line,
                lambda core: L.pops_apply_all_config_patches(H.buf(core), len(core), c.byref(cfg)))
        for addons in (0, 8, 16, 24):
            run("emit %d" % addons,
                lambda core: L.pops_resident_hook_recompiler_emit(H.buf(core), len(core), addons, header))
        # The fix-file stage with no file: its context, its progressive
        # check and its video pass.
        for region in range(4):
            for video in range(9):
                def fix_pass(core):
                    context = c.create_string_buffer(4096)
                    results = [L.pops_fix_context_init_builtin(context, H.buf(core), len(core), 0, 0, video),
                               L.pops_fix_require_progressive(context, H.buf(core), len(core)),
                               L.pops_fix_finalize_video(context, H.buf(core), len(core), region, video)]
                    return results
                run("fixpass %d %d" % (region, video), fix_pass)
        run("shell edits", lambda core: L.pops_apply_bios_shell_edits(H.buf(core), len(core)))
        for region in range(4):
            for video in range(9):
                for auto_off in (0, 1):
                    run("region %d %d %d" % (region, video, auto_off),
                        lambda core: L.pops_apply_region(H.buf(core), len(core), region, video, auto_off))
        vector = c.c_uint32(0)
        run("warmboot", lambda core: L.pops_apply_reset_warmboot(H.buf(core), len(core), c.byref(vector)))
        for name in MODULE_NAMES:
            irx = module_irx(name)
            flags = c.c_uint(0)
            run("module " + name,
                lambda core: L.pops_module_irx_name_apply(H.buf(core), len(core), H.buf(irx), len(irx),
                                                          c.byref(flags)))
        run("padman", lambda core: L.pops_apply_padman(H.buf(core), len(core)))
        run("slbb", lambda core: L.pops_apply_slbb_vcd_check_bypass(H.buf(core), len(core)))
        for flags in (RES_F_PAD_ID, RES_F_D2LS, RES_F_PAD_ID | RES_F_D2LS):
            run("pads %d" % flags,
                lambda core: L.pops_resident_hook_pads(H.buf(core), len(core), flags,
                                                       header.pad_read_entry, header.pad_read_exit))
        for mode in (1, 2, 3):
            run("widescreen %d" % mode,
                lambda core: L.pops_resident_hook_widescreen(H.buf(core), len(core), mode, header))
        # The progressive hook wants the interlace words its setting leaves:
        # the commands are staged first, as in launchPOPS.
        for line in ("", "$HDTVFIX", "$NOHDTVFIX"):
            cfg = config(line)
            interlace = L.pops_resident_progressive_interlace(c.byref(cfg))

            def progressive(core):
                return [L.pops_apply_all_config_patches(H.buf(core), len(core), c.byref(cfg)),
                        L.pops_resident_hook_progressive(H.buf(core), len(core),
                                                         header.progressive_entry, interlace)]
            run("progressive %#x" % interlace, progressive)
            interlaces.append(interlace)
        run("display", lambda core: L.pops_resident_hook_display(H.buf(core), len(core), header.display_entry))
        rc, _ = run("opcodes", lambda core: L.pops_apply_opcode_pass(H.buf(core), len(core)))
        self.assertGreater(rc, 10000)
        # What actually ran (a refusal writes nothing and proves nothing).
        self.assertEqual(ran["command"], [0] * len(COMMANDS))
        self.assertEqual(ran["emit"], [0] * 4)
        self.assertEqual(ran["fixpass"], [[0, 0, 0]] * 36)
        self.assertEqual(ran["shell"], [0])
        self.assertEqual(ran["region"], [0] * 72)
        self.assertEqual(ran["warmboot"], [1])
        self.assertEqual(ran["module"], [0] * len(MODULE_NAMES))
        self.assertEqual(ran["padman"], [0])
        self.assertEqual(ran["slbb"], [0])
        self.assertEqual(ran["pads"], [0] * 3)
        self.assertEqual(ran["widescreen"], [0] * 3)
        self.assertEqual(ran["progressive"], [[0, 0]] * 3)
        self.assertEqual(interlaces, [0x24040000, 0x24040001, 0x32240001])
        self.assertEqual(ran["display"], [0])

    def test_user_fix_files_come_after_the_skin(self):
        """TROJAN_n.BIN / PATCH_n.BIN are staged after the skin, as in the
        original (its fix loaders are called after 0x876b18), and may write
        anywhere: one aimed elsewhere leaves the skin, one aimed at a slot
        replaces those bytes."""
        base = self.staged_with_skin()
        want = skin_range(base)

        def staged(blob, slot, trojan):
            core = bytearray(base)
            context = c.create_string_buffer(4096)
            self.assertEqual(L.pops_fix_context_init_builtin(context, H.buf(core), len(core), 0, 0, 0), 0)
            rc = L.pops_fix_stage(context, H.buf(core), len(core), blob, len(blob), slot, trojan)
            return rc, core

        rc, core = staged(fix_file("PATCH", 1, modes=(4,)), 1, 0)
        self.assertEqual((rc, skin_range(core) == want), (0, True))
        self.assertNotEqual(bytes(core), bytes(base))
        rc, core = staged(fix_file("PATCH", 2, payload=b"\x5a" * 8, address=0x00240000), 2, 0)
        self.assertEqual((rc, skin_range(core) == want), (0, True))
        self.assertEqual(bytes(core[0x40000:0x40008]), b"\x5a" * 8)
        inside = SLOTS[NO][1] + 0x100
        rc, core = staged(fix_file("PATCH", 3, payload=b"\x5a" * 8, address=inside), 3, 0)
        self.assertEqual(rc, 0)
        self.assertEqual(bytes(core[inside - CORE:inside - CORE + 8]), b"\x5a" * 8)
        changed = [i for i in range(FIRST - CORE, END - CORE) if core[i] != base[i]]
        self.assertTrue(set(changed) <= set(range(inside - CORE, inside - CORE + 8)))

    def launch(self, mask, builtin, bios=(), skin_first=False):
        """launchPOPS's staging calls on one core, in its order, through the
        common functions it calls; pops_stage_user_files's steps are written
        out here (its look-ahead at the two BIOS.BIN files becomes the flags
        `bios` names: "all" for the all-games folder, "game" for the game's).
        Not replayed: the TROJAN slot chain (no TROJAN file here) and the
        progressive hook (not asked for). Returns 0 and the core, or the
        runtime corrections' result when the skin was staged first."""
        core = bytearray(self.pristine)
        header = resident_header()

        def ok(name, rc, want=0):
            self.assertEqual(rc, want, (name, mask, builtin, bios))

        ok("core patches", L.pops_core_patches_stage(CORE, H.buf(core), len(core), (1 << 7) - 1))
        if skin_first:
            core = self.staged_with_skin(bytes(core))
        if mask:
            rc = L.pops_core_runtime_corrections_stage(CORE, H.buf(core), len(core), mask)
            if skin_first:
                return rc, core
            ok("runtime corrections", rc)
        ok("always-on hooks", always_on(core), [0, 0, 0, 0])
        modes = 0
        if builtin:
            ok("built-in entry", L.pops_builtin_apply(builtin, H.buf(core), len(core), None, 0, 0, PLAN))
            modes = PLAN[2]   # PopsBuiltinPlan.compat_modes
        core = self.staged_with_skin(bytes(core))
        want = skin_range(core)
        cfg = config("$IGR0")
        L.pops_config_parse_line(c.byref(cfg), b"$COMPATIBILITY_0x04")
        L.pops_config_parse_line(c.byref(cfg), b"$HDTVFIX")
        # pops_stage_user_files: the state, the commands with the flags the
        # loads will set, the emit jumps, then pops_stage_fix_files.
        rom = Rom(osd_off=1 if modes & (1 << 5) else 0)
        at_commands = Rom(bios_all="all" in bios, bios_game="game" in bios, osd_off=rom.osd_off)
        ok("commands", L.pops_apply_all_config_patches_rom(H.buf(core), len(core), c.byref(cfg),
                                                           c.byref(at_commands)))
        rom.osd_off = at_commands.osd_off
        self.assertEqual(igr_outcome(core), "dialog")
        ok("emit", L.pops_resident_hook_recompiler_emit(H.buf(core), len(core), 24, header))
        context = c.create_string_buffer(4096)
        ok("fix context", L.pops_fix_context_init_builtin(context, H.buf(core), len(core), builtin,
                                                          cfg.compat_modes, cfg.video_mode))
        ok("fix bind", L.pops_fix_bind_progressive(context, H.buf(core), len(core),
                                                   header.progressive_entry, 0x24040001))
        # Each folder's BIOS.BIN, then its fix files: all games, then the game.
        # The file is POPS's own ROM copy with its first 16 bytes changed.
        user_bios = bytearray(self.pristine[USER_BIOS_ADDR - CORE:USER_BIOS_ADDR - CORE + USER_BIOS_READ])
        user_bios[:16] = b"\x5a" * 16
        user_bios = bytes(user_bios)
        for scope, folder in enumerate(("all", "game")):
            if folder in bios:
                ok("BIOS.BIN " + folder,
                   L.pops_user_bios_stage(H.buf(core), len(core), user_bios, len(user_bios), 0x80000,
                                          scope, c.byref(rom)), 1)
                ok("BIOS.BIN context", L.pops_fix_context_rom_loaded(context, H.buf(core), len(core)))
            if not scope:
                blob = fix_file("PATCH", 0, payload=b"\x5a" * 8, address=0x00240000)
                ok("fix file", L.pops_fix_stage_rom(context, H.buf(core), len(core), blob, len(blob),
                                                    0, 0, c.byref(rom)))
        self.assertEqual((rom.bios_all, rom.bios_game), (at_commands.bios_all, at_commands.bios_game))
        if bios:
            self.assertEqual(H.u32(core, USER_BIOS_ADDR), 0x5A5A5A5A)
        ok("fix progressive", L.pops_fix_require_progressive(context, H.buf(core), len(core)))
        ok("fix video", L.pops_fix_finalize_video(context, H.buf(core), len(core), 1, cfg.video_mode))
        ok("shell edits", L.pops_apply_bios_shell_edits_rom(H.buf(core), len(core), c.byref(rom)))
        ok("region", L.pops_apply_region_rom(H.buf(core), len(core), 1, cfg.video_mode, 0, c.byref(rom)))
        vector = c.c_uint32(0)
        ok("warmboot", L.pops_apply_reset_warmboot(H.buf(core), len(core), c.byref(vector)), 1)
        irx = module_irx("sio2man")
        flags = c.c_uint(0)
        ok("module name", L.pops_module_irx_name_apply(H.buf(core), len(core), H.buf(irx), len(irx),
                                                       c.byref(flags)))
        ok("padman", L.pops_apply_padman(H.buf(core), len(core)))
        ok("slbb", L.pops_apply_slbb_vcd_check_bypass(H.buf(core), len(core)))
        ok("pads", L.pops_resident_hook_pads(H.buf(core), len(core), RES_F_PAD_ID | RES_F_D2LS,
                                             header.pad_read_entry, header.pad_read_exit))
        ok("widescreen", L.pops_resident_hook_widescreen(H.buf(core), len(core), 1, header))
        ok("display", L.pops_resident_hook_display(H.buf(core), len(core), header.display_entry))
        self.assertGreater(L.pops_apply_opcode_pass(H.buf(core), len(core)), 10000)
        self.assertEqual(skin_range(core), want, (mask, builtin))
        return 0, core

    def test_whole_launches_keep_the_skin(self):
        """launchPOPS's staging calls on the core in its order (see launch
        for the two it leaves out), with and without runtime corrections, a
        built-in entry and a user BIOS.BIN in either folder or both: each
        call succeeds and the skin read by the reader is still in place."""
        runs = 0
        for mask in (0,) + RUNTIME_MASKS:
            for builtin in (0, 1, 508):
                for bios in ((), ("all",), ("game",), ("all", "game")):
                    rc, _ = self.launch(mask, builtin, bios)
                    self.assertEqual(rc, 0)
                    runs += 1
        self.assertEqual(runs, 84)

    def test_a_skin_before_the_runtime_corrections_stops_the_launch(self):
        """The order the first version of this stage would have had once the
        corrections ran: refused, where launchPOPS returns the error."""
        for mask in RUNTIME_MASKS:
            rc, _ = self.launch(mask, 0, skin_first=True)
            self.assertEqual(rc, -4, mask)


def _words(main, addr, n=1):
    off = addr - MAIN_BASE
    return list(struct.unpack_from("<%dI" % n, main, off))


def _cstr(main, addr):
    off = addr - MAIN_BASE
    return bytes(main[off:main.index(b"\0", off)]).decode("ascii")


def _branch_target(addr, word):
    """Target of a branch or plain jump (not a call), else None."""
    op = word >> 26
    if op == 2:
        return ((addr + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
    rt = (word >> 16) & 0x1F
    if op in (4, 5, 6, 7, 20, 21, 22, 23) or (op == 1 and rt in (0, 1, 2, 3)) or \
            (op == 17 and (word >> 21) & 0x1F == 8):
        offset = word & 0xFFFF
        return addr + 4 + 4 * (offset - 0x10000 if offset & 0x8000 else offset)
    return None


@unittest.skipUnless(HAVE_MAIN, "POPSTARTER_TEST_ELF not set")
class OriginalCode(unittest.TestCase):
    """The table, read out of the original's own instructions."""

    FUNC, FUNC_END, GP = 0x87E464, 0x87EB24, 0x9B68F0
    LAUNCH, LAUNCH_END, SKIN_CALL = 0x870B78, 0x87C218, 0x876B18

    @classmethod
    def setUpClass(cls):
        from trace_original_pops_io import decode_main
        cls.raw = Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes()
        cls.main = bytes(decode_main(cls.raw))
        cls.words = _words(cls.main, cls.FUNC, (cls.FUNC_END - cls.FUNC) // 4)
        cls.all_words = struct.unpack_from("<%dI" % (len(cls.main) // 4), cls.main)

    def callers(self, target):
        jal = 0x0C000000 | (target >> 2)
        return [MAIN_BASE + 4 * i for i, word in enumerate(self.all_words) if word == jal]

    def decode(self):
        """Per file block, in address order: the two paths it opens (pfs,
        mass), its size test, and the address and length of its zero fill
        and of its two reads."""
        blocks = []
        cur = None
        w = self.words
        for i, word in enumerate(w):
            target = (word & 0x03FFFFFF) << 2 if word >> 26 == 3 else None
            if target in (0x916758, 0x8D6C94):                       # open
                path_word = w[i - 2] if target == 0x916758 else w[i - 1]
                self.assertEqual(path_word >> 16, 0x2784)              # addiu a0, gp, imm
                path = _cstr(self.main, self.GP + ((path_word & 0xFFFF) ^ 0x8000) - 0x8000)
                if target == 0x916758:
                    cur = {"paths": [path], "fills": [], "reads": [], "limit": None}
                    blocks.append(cur)
                    self.assertEqual(w[i - 1], 0x24050001)             # a1 = 1 (read only)
                    self.assertEqual(w[i + 1], 0x0000302D)             # a2 = 0
                else:
                    cur["paths"].append(path)
                    self.assertEqual(w[i + 1], 0x24050001)
            elif target in (0x9188B8, 0x9169B0, 0x8D6D24):           # memset, read, read
                reg = 4 if target == 0x9188B8 else 5
                prior = w[max(0, i - 6):i]
                lui = [x for x in prior if x >> 16 == (0x3C00 | reg)]
                ori = [x for x in prior if x >> 16 == (0x3400 | reg << 5 | reg)]
                delay = w[i + 1]
                if not lui:          # the tail fill: a0 = slot + size, computed
                    continue
                addr = (lui[-1] & 0xFFFF) << 16 | (ori[-1] & 0xFFFF)
                if delay >> 16 == 0x2406:                              # addiu a2, zero, imm
                    length = delay & 0xFFFF
                else:                                                  # lui a2 ; ori a2 (delay slot)
                    self.assertEqual(delay >> 16, 0x34C6)
                    length = (w[i - 1] & 0xFFFF) << 16 | (delay & 0xFFFF)
                    self.assertEqual(w[i - 1] >> 16, 0x3C06)
                cur["fills" if target == 0x9188B8 else "reads"].append((addr, length))
            elif word >> 16 == 0x2842:                                 # slti v0, v0, imm
                cur["limit"] = ("lt", word & 0xFFFF)
            elif word == 0x0062102A:                                   # slt v0, v1, v0
                self.assertEqual(w[i - 2] >> 16, 0x3C03)
                self.assertEqual(w[i - 1] >> 16, 0x3463)
                cur["limit"] = ("gt", (w[i - 2] & 0xFFFF) << 16 | (w[i - 1] & 0xFFFF))
        return blocks

    def test_table_is_the_originals(self):
        blocks = self.decode()
        self.assertEqual(len(blocks), 3)
        for which, (block, (name, addr, slot, biggest)) in enumerate(zip(blocks, SLOTS)):
            self.assertEqual(block["paths"], ["pfs1:/POPS/" + name, "mass:/POPS/" + name])
            self.assertEqual(block["fills"], [(addr, slot)])
            self.assertEqual(block["reads"], [(addr, slot), (addr, slot)])
            kind, value = block["limit"]
            # BG: too big when size > value. NO, YES: loaded when size < value.
            self.assertEqual(kind, "gt" if which == BG else "lt")
            self.assertEqual(value if kind == "gt" else value - 1, biggest)
            got = LIB.pops_igr_skin_slot(which).contents
            self.assertEqual((got.name.decode(), got.addr, got.slot_size, got.max_size),
                             (name, addr, slot, biggest))

    def test_one_caller_and_its_gates(self):
        words = self.all_words
        self.assertEqual(self.callers(self.FUNC), [self.SKIN_CALL])
        self.assertNotIn(0x08000000 | (self.FUNC >> 2), words)        # no plain jump
        self.assertNotIn(self.FUNC, words)                            # no pointer
        # Gate 1: the shared abort flag gp+0x38dc. Gate 2: fp+0x1108 == 1.
        self.assertEqual(_words(self.main, 0x876A84, 2), [0x8F8238DC, 0x14400025])
        self.assertEqual(_words(self.main, 0x876A90, 3), [0x8FC31108, 0x24020001, 0x14620021])
        # fp+0x1108 is 1 iff the preset byte at 0x10002d is 1 ...
        self.assertEqual(_words(self.main, 0x8712C8, 3), [0x3C040010, 0x0C21F086, 0x3484002D])
        self.assertEqual(_words(self.main, 0x8712E0)[0], 0x14620003)
        self.assertEqual(_words(self.main, 0x8712EC)[0], 0xAFC21108)
        stores = [MAIN_BASE + 4 * i for i, word in enumerate(words)
                  if word & 0xFFE0FFFF == 0xAFC01108 and 0x870B78 <= MAIN_BASE + 4 * i < 0x87C218]
        self.assertEqual(stores, [0x870CE8, 0x8712EC])
        # ... and it is 1 in this build (packed ELF, segment at 0x100000).
        phoff, = struct.unpack_from("<I", self.raw, 0x1C)
        _type, offset, vaddr = struct.unpack_from("<III", self.raw, phoff)
        self.assertEqual(vaddr, 0x100000)
        self.assertEqual(self.raw[offset + 0x2D], 1)

    def test_the_builtin_list_runs_before_the_skin_and_vcdid_after(self):
        """Where launchPOPS puts the skin against its built-in entry: the
        original's fingerprint lookup-and-apply (FUN_008ff0e4) is called
        only from the launch function, at six sites all below the skin
        call, and nothing branches from before the call's gate to past the
        call or from past the call back to them. The apply function's other
        callers ($VCDID_n) are in the parser, which the launch function
        calls only after the skin."""
        lookup, apply, parser = 0x8FF0E4, 0x8E00D0, 0x883270
        sites = self.callers(lookup)
        self.assertEqual(sites, [0x8757D4, 0x875D70, 0x875F78, 0x8762A8, 0x876424, 0x8769AC])
        self.assertTrue(all(self.LAUNCH <= a < self.SKIN_CALL for a in sites))
        applies = self.callers(apply)
        self.assertEqual(applies, [0x890F4C, 0x8912E4, 0x8917F0, 0x891E78, 0x9148D8])
        self.assertTrue(lookup <= applies[-1] < 0x9148E8)             # the lookup's own apply
        # The other four: after the parser's entry, with no other function
        # start (stack adjust) or return in between.
        between = [a for a in range(parser + 4, applies[3], 4)
                   if self.all_words[(a - MAIN_BASE) // 4] == 0x03E00008 or
                   (self.all_words[(a - MAIN_BASE) // 4] >> 16 == 0x27BD and
                    self.all_words[(a - MAIN_BASE) // 4] & 0x8000)]
        self.assertEqual(between, [])
        self.assertEqual(self.callers(parser), [0x8771AC, 0x87724C])
        self.assertTrue(all(a > self.SKIN_CALL for a in self.callers(parser)))
        # Control flow in the launch function around the call.
        gate = 0x876A84
        forward, backward, indirect = [], [], []
        for addr in range(self.LAUNCH, self.LAUNCH_END, 4):
            word = self.all_words[(addr - MAIN_BASE) // 4]
            if word & 0xFC1FFFFF == 0x00000008 and (word >> 21) & 0x1F != 31:
                indirect.append(addr)                                 # jr through a register
            target = _branch_target(addr, word)
            if target is None:
                continue
            if addr < gate and target >= self.SKIN_CALL + 4:
                forward.append((addr, target))
            if addr >= self.SKIN_CALL and self.LAUNCH <= target <= sites[-1] + 4:
                backward.append((addr, target))
        self.assertEqual((forward, backward, indirect), ([], [], []))
        # The last site runs on into the gate: `b 0x876a40` in its return.
        self.assertEqual(_words(self.main, sites[-1] + 8)[0], 0x10000022)
        self.assertEqual(_branch_target(sites[-1] + 8, 0x10000022), 0x876A40)

    def test_messages(self):
        for off, text in ((-0x56A0, "NOT FOUND\n"), (-0x5690, "TOO BIG !\n"), (-0x5680, "LOADED\n")):
            self.assertEqual(_cstr(self.main, self.GP + off), text)


PRINTS = {"NOT FOUND": "NOT FOUND\n", "TOO BIG": "TOO BIG !\n", "LOADED": "LOADED\n"}


@unittest.skipUnless(HAVE_EMU, "needs POPSTARTER_TEST_ELF and POPS_TEST_ELF")
class Original(unittest.TestCase):
    """The original's loader, run as shipped, against the model of it,
    pops_igr_skin_stage and launcHER's reader."""

    @classmethod
    def setUpClass(cls):
        from trace_original_pops_warmboot import core_image
        cls.core = bytes(core_image(os.environ["POPS_TEST_ELF"]))
        assert len(cls.core) == CORE_SIZE
        cls.emu = T.Emulator(cls.core)
        cls.runs = 0

    @classmethod
    def tearDownClass(cls):
        if os.environ.get("POPS_IGR_SKIN_COUNTS"):
            print("\nruns of the original's loader: %d" % cls.runs, file=sys.stderr)

    def original(self, files, backend, core=None, quiet=0):
        """One run of the original, held to the model: whole core, prints,
        return value, nothing else in memory, every file closed."""
        core = self.core if core is None else core
        r = self.emu.run(named(files, T.PREFIX[backend]), backend=backend, core=core, quiet=quiet)
        type(self).runs += 1
        want, outcomes = original_model(core, files)
        prints = []
        for which, (name, addr, slot, _) in enumerate(SLOTS):
            prints += ["    Opening %s%s... " % (T.PREFIX[backend], name), PRINTS[outcomes[which]]]
            if outcomes[which] == "TOO BIG":   # refused on its size alone: nothing zero-filled or read
                touched = [e for e in r["log"]
                           if (e[0] == "memset" and e[1] == addr and e[3]) or (e[0] == "read" and e[2] == addr)]
                self.assertEqual(touched, [], name)
        self.assertEqual(r["ret"], 1)
        self.assertEqual(r["prints"], [] if quiet else prints)
        self.assertEqual(r["outside"], [])
        self.assertEqual(r["open_fds"], [])
        self.assertTrue(r["core"] == want, {k: len(T.as_file(v).data) for k, v in files.items()})
        opened = [e[2] for e in r["log"] if e[0] == "open"]
        self.assertEqual(opened, [T.PREFIX[backend] + s[0] for s in SLOTS])
        r["outcomes"] = outcomes
        return r

    def compare(self, files, backend, core=None, quiet=0):
        """The original against launcHER for files a device delivers whole:
        the pure function fed the file, and the reader run on the same
        device. files: {which: bytes}."""
        core = self.core if core is None else core
        r = self.original(files, backend, core, quiet)
        ours = bytearray(core)
        for which in sorted(files):
            rc = stage(ours, which, files[which])
            self.assertEqual(rc, -errno.EFBIG if r["outcomes"][which] == "TOO BIG" else 0)
        self.assertTrue(r["core"] == bytes(ours))
        self.reader_matches(r, files, backend, core)
        return r

    def reader_matches(self, r, files, backend, core=None):
        core = self.core if core is None else core
        prefix = T.PREFIX[backend]
        mine = READER.run(core, named(files, prefix), prefix)
        check_reader_calls(self, mine, named(files, prefix), prefix)
        self.assertEqual(mine["outcomes"], r["outcomes"])
        self.assertTrue(mine["core"] == r["core"])
        return mine

    def test_boundary_sizes_on_both_backends(self):
        rng = random.Random(0x424F554E)
        sizes = [boundary_sizes(which) + [SLOTS[which][2] * 2] for which in range(3)]
        seen, outcomes, runs = set(), {}, 0
        for backend in (0, 1):
            for i in range(9):
                files = {}
                for which in range(3):
                    pool = sizes[which]
                    files[which] = rng.randbytes(pool[(i + 2 * which) % len(pool)])
                if i == 8:
                    del files[backend]                                # and one file absent
                for which, data in files.items():
                    seen.add((backend, which, len(data)))
                r = self.compare(files, backend)
                runs += 1
                for which, outcome in enumerate(r["outcomes"]):
                    outcomes[(backend, which, outcome)] = outcomes.get((backend, which, outcome), 0) + 1
        self.assertEqual(runs, 18)
        for backend in (0, 1):
            for which in range(3):
                for size in sizes[which]:
                    self.assertIn((backend, which, size), seen)
                for outcome in ("TOO BIG", "LOADED"):
                    self.assertGreaterEqual(outcomes.get((backend, which, outcome), 0), 2,
                                            (backend, which, outcome))

    def test_random_files_on_both_backends(self):
        rng = random.Random(0x52414E44)
        outcomes = {}
        for backend in (0, 1):
            for n in range(12):
                files = {}
                for which, (_, _, slot, biggest) in enumerate(SLOTS):
                    pick = rng.random()
                    if n < 3:                                        # each outcome once for each file
                        pick = (0.1, 0.5, 0.95)[(n + which) % 3]
                    if pick < 0.25:
                        continue                                     # absent
                    size = rng.randrange(0, biggest + 1) if pick < 0.85 else rng.randrange(biggest + 1, 2 * slot)
                    files[which] = rng.randbytes(size)
                r = self.compare(files, backend)
                for which, outcome in enumerate(r["outcomes"]):
                    outcomes[(backend, which, outcome)] = outcomes.get((backend, which, outcome), 0) + 1
        # The first three sets put each file through each outcome; the rest
        # are whatever the seed gives.
        for backend in (0, 1):
            for which in range(3):
                for outcome in ("NOT FOUND", "TOO BIG", "LOADED"):
                    self.assertTrue(outcomes.get((backend, which, outcome)), (backend, which, outcome))

    def test_no_file_changes_nothing(self):
        for backend in (0, 1):
            r = self.compare({}, backend)
            self.assertEqual(r["core"], self.core)
            self.assertEqual(r["outcomes"], ["NOT FOUND"] * 3)

    def test_slot_contents_are_not_checked(self):
        """Over a core of noise (no TIM2 anywhere) the files load the same."""
        rng = random.Random(0x4E4F4953)
        noise = rng.randbytes(CORE_SIZE)
        for backend in (0, 1):
            self.compare({BG: rng.randbytes(1000), NO: b"", YES: rng.randbytes(SLOTS[YES][3])},
                         backend, core=noise)

    def test_quiet_flag_only_silences(self):
        rng = random.Random(5)
        self.compare({BG: rng.randbytes(64), NO: rng.randbytes(9000)}, 0, quiet=1)

    def test_gates(self):
        files = named({BG: b"\x11" * 64}, T.PREFIX[0])
        r = self.emu.run(files, abort=1)                             # already aborting
        self.assertEqual((r["ret"], r["log"], r["core"] == self.core), (0, [], True))
        r = self.emu.run(files, checked=0, dircheck=-666)            # POPS folder check fails
        self.assertEqual((r["ret"], r["log"], r["abort"]), (-666, [("dircheck",)], 1))
        self.assertEqual(r["core"], self.core)
        r = self.emu.run(files, checked=0, dircheck=1)               # passes: loads
        self.assertEqual((r["ret"], r["prints"][1]), (1, "LOADED\n"))
        r = self.emu.run(files, checked=1)                           # checked earlier: not called
        self.assertNotIn(("dircheck",), r["log"])
        self.assertEqual(r["ret"], 1)

    def test_misbehaving_devices_where_launcher_matches(self):
        """The device stops for good, the size query disagrees with the
        data, the seek back fails, reads over-report: the original, the
        model and launcHER's reader leave the same core."""
        families = {}
        for family, relation, files in device_runs():
            if relation != SAME:
                continue
            for backend in (0, 1):
                r = self.original(files, backend)
                self.reader_matches(r, files, backend)
            families[family] = families.get(family, 0) + 2
        self.assertEqual(families, {"stops": 48, "size": 14, "rewind": 8, "extra": 8, "pieces": 2})

    def test_a_failed_size_query_is_where_launcher_differs(self):
        """Measured, and deliberately not reproduced: the original takes a
        negative lseek result as the size, so its last fill starts that many
        bytes below the slot; for IGR_BG.TM2 those are POPS's own data.
        launcHER's reader leaves the whole core alone."""
        ran = 0
        for family, relation, files in device_runs():
            if relation != SIZE_FAILED:
                continue
            for backend in (0, 1):
                r = self.original(files, backend)
                self.assertEqual(r["outcomes"], ["LOADED"] * 3)
                result = files[BG].size
                below = self.core[FIRST - CORE + result:FIRST - CORE]
                self.assertEqual(r["core"][FIRST - CORE + result:END - CORE], bytes(END - FIRST - result))
                self.assertEqual(r["core"][:FIRST - CORE + result], self.core[:FIRST - CORE + result])
                if result == -4096:
                    self.assertNotEqual(below, bytes(4096))          # live bytes of POPS, wiped there
                prefix = T.PREFIX[backend]
                mine = READER.run(self.core, named(files, prefix), prefix)
                check_reader_calls(self, mine, named(files, prefix), prefix)
                self.assertEqual(mine["core"], self.core)
                self.assertEqual(mine["outcomes"], [SIZE_FAILED] * 3)
                ran += 1
        self.assertEqual(ran, 8)

    def test_a_file_in_pieces_is_where_launcher_differs(self):
        """Measured on both sides: the original's one read keeps the first
        piece and zeros follow; launcHER's reader asks again and stages the
        whole file."""
        ran = 0
        for family, relation, files in device_runs():
            if relation != PIECES:
                continue
            for backend in (0, 1):
                r = self.original(files, backend)
                prefix = T.PREFIX[backend]
                mine = READER.run(self.core, named(files, prefix), prefix)
                check_reader_calls(self, mine, named(files, prefix), prefix)
                self.assertTrue(mine["core"] == launcher_expect(self.core, files)[0])
                for which, f in files.items():
                    slot = SLOTS[which][2]
                    self.assertEqual(slot_bytes(r["core"], which),
                                     f.data[:f.per_read] + bytes(slot - f.per_read))
                    self.assertEqual(slot_bytes(mine["core"], which), f.data + bytes(slot - len(f.data)))
                ran += 1
        self.assertEqual(ran, 6)


def strip_c(text):
    """C source with comments and string/character literals blanked (the
    newlines stay), for counting braces and finding statement ends."""
    out, i, n = [], 0, len(text)
    while i < n:
        two = text[i:i + 2]
        if two == "/*":
            j = text.index("*/", i + 2) + 2
            out.append("".join(ch if ch == "\n" else " " for ch in text[i:j]))
            i = j
        elif two == "//":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif text[i] in "\"'":
            quote, j = text[i], i + 1
            while text[j] != quote:
                j += 2 if text[j] == "\\" else 1
            out.append(quote + " " * (j - i - 1) + quote)
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


class Source(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "launcher/src/handler_pops.c").read_text()
        self.body = self.src[self.src.index("int launchPOPS("):]

    def test_call_position(self):
        body = self.body
        call = "pops_stage_igr_skin((void *)stagedCore, plan.core_size, vcdDir);"
        self.assertEqual(body.count("pops_stage_igr_skin("), 1)
        # The reader is static with that one caller, and launchPOPS has one
        # caller of its own, behind isPopsTarget.
        self.assertEqual(self.src.count("pops_stage_igr_skin("), 2)
        self.assertEqual(len(re.findall(r"^static void pops_stage_igr_skin\(", self.src, re.M)), 1)
        users = [path.name for path in sorted((ROOT / "launcher/src").glob("*.c"))
                 if "launchPOPS(" in path.read_text()]
        self.assertEqual(users, ["common.c", "handler_pops.c"])
        common = (ROOT / "launcher/src/common.c").read_text()
        self.assertEqual(common.count("launchPOPS("), 1)
        self.assertIn("if (isPopsTarget(argv[0]))\n    return launchPOPS(argc, argv);", common)
        at = body.index(call)
        # After the runtime corrections (they refuse a core with a skin),
        # the always-on hooks and the built-in entry (the original's order
        # for a fingerprint match); before the commands, the fix files and
        # everything later.
        before = ["res = pops_core_patches_stage(", "pops_core_runtime_corrections_stage(",
                  "res = pops_resident_hook_guards(",
                  "res = pops_apply_always_on_pokes(",
                  'msg("POPS: POPStarter launch hooks failed: %d\\n", res);',
                  "res = pops_builtin_apply(builtinId, (void *)stagedCore",
                  'msg("POPS: Applying built-in entry %u failed: %d\\n"']
        # The commands, the $RECOMPILER_ADDON_3/4 jumps and the fix files are
        # one helper, called once (tools/test_pops_launch_hooks.py pins its
        # inner order).
        after = ["res = pops_stage_user_files(",
                 "res = pops_apply_bios_shell_edits_rom(",
                 "res = regionRead ? pops_apply_region_rom(",
                 "res = pops_apply_reset_warmboot(",
                 "res = pops_module_irx_apply_names(",
                 "res = pops_apply_slbb_vcd_check_bypass(",
                 "res = pops_resident_hook_pads(",
                 "res = pops_apply_opcode_pass(",
                 "SifIopRebootBuffer("]
        for s in before:
            self.assertLess(body.index(s), at, s)
        for s in after:
            self.assertGreater(body.index(s), at, s)
        # The same folder as the all-games (root) TROJAN_n.BIN / PATCH_n.BIN.
        self.assertIn("res = pops_stage_user_files((void *)stagedCore, plan.core_size, vcdDir, "
                      "gameConfigDir,", body)
        helper = self.src[self.src.index("static int pops_stage_user_files("):
                          self.src.index("int launchPOPS(")]
        self.assertIn("res = pops_stage_fix_files(stagedCore, coreSize, vcdDir, titleDir, builtinId,",
                      helper)
        fix = self.src[self.src.index("static int pops_stage_fix_files("):
                       self.src.index("/* Driver names within one role")]
        self.assertIn("const char *dirs[] = {vcdDir, titleDir};", fix)

    def test_call_is_unconditional(self):
        """A bare statement directly in launchPOPS's body: no result, no
        `if`/`else`/loop over it on its own line or the one before, no
        preprocessor conditional around it, nothing that fails on it."""
        code = strip_c(self.body)
        at = code.index("pops_stage_igr_skin(")
        before = code[:at]
        self.assertEqual(before.count("{") - before.count("}"), 1)
        self.assertIn(before.rstrip()[-1], ";}")
        self.assertEqual(code[at:code.index(";", at) + 1],
                         "pops_stage_igr_skin((void *)stagedCore, plan.core_size, vcdDir);")
        self.assertEqual(self.body[self.body.rindex("\n", 0, at) + 1:at], "  ")
        conditionals = re.findall(r"^[ \t]*#[ \t]*(if|ifdef|ifndef|endif)\b", before, re.M)
        self.assertEqual(sum(1 for d in conditionals if d != "endif"), conditionals.count("endif"))
        # The check itself: a guard on the line before is seen.
        guarded = code.replace("  pops_stage_igr_skin(", "  if (cfg.compat_modes)\n  pops_stage_igr_skin(", 1)
        self.assertEqual(guarded[:guarded.index("pops_stage_igr_skin(")].rstrip()[-1], ")")

    def test_reader_follows_the_original(self):
        begin = self.src.index(READER_BEGIN)
        reader = self.src[begin:self.src.index(READER_END)]
        # tools/test_pops_fix_files.py compiles this slice of the file on
        # the host; the reader must stay outside it.
        self.assertNotIn("pops_igr_skin", self.src[self.src.index("static int readFullFile("):
                                                   self.src.index("/* Driver names within one role")])
        self.assertGreater(begin, self.src.index("/* Driver names within one role"))
        self.assertIn("for (int which = 0; which < POPS_IGR_SKIN_COUNT; ++which)", reader)
        self.assertIn('snprintf(path, sizeof(path), "%s%s", dir, slot->name)', reader)
        order = ["open(path, O_RDONLY)", "lseek(fd, 0, SEEK_END)",
                 "if (size > (off_t)slot->max_size)", "lseek(fd, 0, SEEK_SET)",
                 "read(fd, buffer + got, chunk)",
                 "pops_igr_skin_stage(stagedCore, coreSize, which, buffer, got)"]
        at = [reader.index(s) for s in order]
        self.assertEqual(at, sorted(at))
        for s in order:
            self.assertEqual(reader.count(s), 1, s)
        # Never fatal: nothing is returned and no launch error is raised.
        self.assertNotIn("return", reader)
        self.assertNotIn("msg(", reader)

    def test_build_lists(self):
        cmake = (ROOT / "launcher/CMakeLists.txt").read_text()
        self.assertEqual(cmake.count("../common/src/pops_igr_skin.c"), 1)
        ci = (ROOT / ".github/workflows/build.yml").read_text()
        self.assertEqual(ci.count("run: python tools/test_pops_igr_skin.py"), 1)

    def test_no_reference_bytes_in_the_repository(self):
        """The pure file holds the table and nothing else."""
        pure = (ROOT / "common/src/pops_igr_skin.c").read_text()
        self.assertLess(len(pure), 4000)
        self.assertNotIn("TIM2", pure)


if __name__ == "__main__":
    unittest.main()
