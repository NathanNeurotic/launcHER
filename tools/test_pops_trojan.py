#!/usr/bin/env python3
"""TROJAN_n.BIN handling against POPStarter r13's loader, on synthetic files.

Native: the pure C logic (common/src), built for the host.
Original: the same files through the original's loader FUN_00880a24 under
  Unicorn (tools/trace_original_pops_trojan.py). Needs POPSTARTER_TEST_ELF,
  POPS_TEST_ELF and unicorn; skipped otherwise.
Source: the launcher's own loop (launcher/src/handler_pops.c), compiled for
  the host with its file reads.
Chain: the built resident image's slot chain entry, on tools/r5900_mini.py;
  with the two inputs above also against the original's own chain, and from
  file bytes to what a payload finds at its slot. The image is the file
  POPS_RESIDENT_BIN names, or is built here when an EE compiler is found
  (POPS_EE_CC, or mips64r5900el-ps2-elf-gcc on the path); skipped otherwise.

Every file here is generated. Nothing is a console run.
"""
import ctypes as c
import errno
import functools
import os
from pathlib import Path
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import pops_trojan_model as model  # noqa: E402
from test_pops_fix_files import BASE, SIZE, Context, pristine  # noqa: E402

HAVE_ORIGINAL = bool(os.environ.get('POPSTARTER_TEST_ELF') and os.environ.get('POPS_TEST_ELF'))
EE_CC = os.environ.get('POPS_EE_CC') or shutil.which('mips64r5900el-ps2-elf-gcc')
HAVE_IMAGE = bool(os.environ.get('POPS_RESIDENT_BIN') or EE_CC)
NO_IMAGE = 'POPS_RESIDENT_BIN not set and no EE compiler (POPS_EE_CC)'
RESIDENT_SOURCES = ['pops_resident_engine.c', 'pops_progressive.c', 'pops_progressive_bridge.S',
                    'pops_resident_guards.S', 'pops_resident_recompiler.S']
_IMAGE = []


def resident_image():
    """The resident image: POPS_RESIDENT_BIN's file, or built with the EE
    compiler the way launcher/CMakeLists.txt builds it."""
    if _IMAGE:
        return _IMAGE[0]
    if os.environ.get('POPS_RESIDENT_BIN'):
        _IMAGE.append(Path(os.environ['POPS_RESIDENT_BIN']).read_bytes())
        return _IMAGE[0]
    objcopy = Path(EE_CC).with_name(Path(EE_CC).name.replace('gcc', 'objcopy'))
    with tempfile.TemporaryDirectory() as directory:
        elf, binary = Path(directory) / 'resident.elf', Path(directory) / 'resident.bin'
        subprocess.run([EE_CC, '-Os', '-G0', '-fno-pic', '-mno-abicalls', '-ffreestanding',
                        '-fno-builtin', '-nostdlib', '-nostartfiles', '-Wall', '-Wextra', '-Werror',
                        '-DPOPS_RESIDENT_IMAGE', '-I', str(ROOT / 'common/include'),
                        '-Wl,-T,' + str(ROOT / 'common/src/pops_resident.ld'), '-Wl,--build-id=none',
                        '-o', str(elf)] + [str(ROOT / 'common/src' / name)
                                           for name in RESIDENT_SOURCES], check=True)
        subprocess.run([str(objcopy), '-O', 'binary', str(elf), str(binary)], check=True)
        _IMAGE.append(binary.read_bytes())
    return _IMAGE[0]


EMPTY_RUNS = [[0x10000001, 0] * 5, [0x10000001, 0] * 5]
BREAK_CALL = 0x0c518000
SLOT4_AS_FILES, SLOT4_BREAK_CALL, SLOT4_RESET_STORE = 0, 1, 2
GP1_HOOK = 0x21a63c
APPLY, INVALID, OUTDATED = 0, 1, 2
SKIP_INVALID, SKIP_OUTDATED, SKIP_UNHOSTED = 1, 2, 3
(NO_UNALIGNED, NO_ENTRY, NO_RANGE, NO_HOOK, NO_SPACE, NO_SLOT, NO_480P, NO_BLOCK2, NO_BUILTIN,
 NO_OWNED, NO_BLOCK1, NO_MAIN, NO_LARGE) = range(1, 14)
K0, K1, GP, RA = 26, 27, 28, 31
JR_RA = [0x03e00008, 0]


def lui(rt, imm):
    return 0x3c000000 | rt << 16 | imm


def ori(rt, rs, imm):
    return 0x34000000 | rs << 21 | rt << 16 | imm


def addiu(rt, rs, imm):
    return 0x24000000 | rs << 21 | rt << 16 | imm & 0xffff


def sw(rt, offset, base):
    return 0xac000000 | base << 21 | rt << 16 | offset & 0xffff


def lw(rt, offset, base):
    return 0x8c000000 | base << 21 | rt << 16 | offset & 0xffff


def beq(rs, rt, words):
    return 0x10000000 | rs << 21 | rt << 16 | words & 0xffff


def jr(rs):
    return rs << 21 | 8


def code(*words):
    return struct.pack('<%dI' % len(words), *words)
WORDS = {APPLY: 'APPLIED', INVALID: 'INVALID', OUTDATED: 'OUTDATED'}
COMMON = ['pops_modes_patches.c', 'pops_resident_engine.c', 'pops_builtin_db.c',
          'pops_builtin_db_data.c', 'pops_external.c', 'pops_resident.c', 'pops_config.c',
          'pops_compat_db.c', 'pops_vcd.c']


class Info(c.Structure):
    _fields_ = [('slot', c.c_uint8), ('format', c.c_uint8), ('width', c.c_uint8),
                ('hook_words', c.c_uint8), ('load', c.c_uint32), ('entry', c.c_uint32),
                ('hook', c.c_uint32), ('size', c.c_uint32), ('hook_word', c.c_uint32 * 3)]


class Payload(c.Structure):
    _fields_ = [('address', c.c_uint32), ('size', c.c_uint32), ('hold', c.c_uint32)]


class TrojanSet(c.Structure):
    _fields_ = [('fingerprint_id', c.c_uint16), ('reason', c.c_uint8),
                ('payload_count', c.c_uint8), ('refs', c.c_uint32),
                ('hold', c.c_void_p), ('hold_size', c.c_uint32), ('hold_used', c.c_uint32),
                ('work', c.c_void_p), ('work_size', c.c_uint32),
                ('chain_offered', c.c_uint8), ('chain', c.c_uint8),
                ('slot_word', c.c_uint32 * 10 * 2),
                ('payload', Payload * 20)]


class ResidentHeader(c.Structure):
    _fields_ = [('magic', c.c_uint32), ('version', c.c_uint16), ('header_size', c.c_uint16),
                ('file_size', c.c_uint32), ('image_size', c.c_uint32),
                ('vblank_entry', c.c_uint32), ('config_addr', c.c_uint32),
                ('display_entry', c.c_uint32), ('progressive_entry', c.c_uint32),
                ('pad_read_entry', c.c_uint32), ('pad_read_exit', c.c_uint32),
                ('gte', c.c_uint32 * 3), ('gp1_entry', c.c_uint32),
                ('guard_entry', c.c_uint32 * 9), ('recompiler_entry', c.c_uint32),
                ('recompiler_emit', c.c_uint32 * 4), ('gp1_chain_entry', c.c_uint32),
                ('gp1_resume_a', c.c_uint32), ('gp1_resume_b', c.c_uint32)]


def fake_header(gp1=0x0143a100, chain=0x0143a200, resume_a=0x0143a240, resume_b=0x0143a280):
    return ResidentHeader(gp1_entry=gp1, gp1_chain_entry=chain, gp1_resume_a=resume_a,
                          gp1_resume_b=resume_b)


class Keep(c.Structure):
    _fields_ = [('start', c.c_uint32), ('end', c.c_uint32)]


def trojan(slot=0, fmt=1, ba=0, be=1, load=0x01500000, entry=None, hook=0x2327d8, size=0x20,
           name=b'probe', patch=None, filesize=None, payload=None):
    """A TROJAN_n.BIN whose payload is `jr ra; nop` repeated, or the one given."""
    if payload is None:
        payload = (struct.pack('<2I', 0x03e00008, 0) * ((size + 7) // 8))[:size]
    size = len(payload)
    header = bytearray(0x40)
    header[0:8] = b'TROJAN_%d' % slot
    header[0x0a], header[0x0c], header[0x0e] = ba, fmt, be
    struct.pack_into('<3I', header, 0x10, load, load if entry is None else entry, hook)
    header[0x1c:0x1f] = struct.pack('<I', size)[:3]
    header[0x20:0x20 + len(name)] = name
    for offset, value in (patch or {}).items():
        header[offset] = value
    data = bytes(header) + payload
    if filesize is not None:
        data = data[:filesize] + bytes(max(0, filesize - len(data)))
    return data


def jal(entry):
    return 0x0c000000 | (entry >> 2) & 0x03ffffff


def jump(entry):
    return 0x08000000 | (entry >> 2) & 0x03ffffff


E = 0x01500000
# (label, generator arguments, fingerprint built-in id, verdict, hook words)
# The verdict and the words are what the rules in pops_external.h say; the
# Original class runs the same files through the original's loader.
CASES = [
    ('format 1', {}, 0, APPLY, [jal(E)]),
    ('byte 0x0e = 2', dict(be=2), 0, APPLY, [jal(E)]),
    ('byte 0x0e = 0xff', dict(be=0xff), 0, APPLY, [jal(E)]),
    ('byte 0x0e = 0', dict(be=0), 0, INVALID, None),
    ('format 1 with byte 0x0a = 1', dict(ba=1), 0, INVALID, None),
    ('format 0', dict(fmt=0), 0, INVALID, None),
    ('format 4', dict(fmt=4), 0, INVALID, None),
    ('format 2 width 0', dict(fmt=2, ba=0), 0, APPLY, [jal(E)]),
    ('format 2 width 1', dict(fmt=2, ba=1), 0, APPLY, [jump(E)]),
    ('format 2 width 2', dict(fmt=2, ba=2), 0, APPLY, [jump(E), 0]),
    ('format 2 width 3', dict(fmt=2, ba=3), 0, APPLY, [jump(E), 0, 0]),
    ('format 2 width 4', dict(fmt=2, ba=4), 0, APPLY, [jal(E)]),
    ('format 3 revision 6, no built-in', dict(fmt=3, ba=6), 0, APPLY, [jal(E)]),
    ('format 3 revision 5, no built-in', dict(fmt=3, ba=5), 0, APPLY, [jal(E)]),
    ('format 3 revision 5, built-in 7', dict(fmt=3, ba=5), 7, OUTDATED, None),
    ('format 3 revision 6, built-in 7', dict(fmt=3, ba=6), 7, APPLY, [jal(E)]),
    ('format 3 revision 0, built-in 7', dict(fmt=3, ba=0), 7, OUTDATED, None),
    ('format 1, built-in 7', {}, 7, APPLY, [jal(E)]),
    ('load not a multiple of 4', dict(load=E + 2), 0, APPLY, [jal(E + 2)]),
    ('hook not a multiple of 4', dict(hook=0x2327da), 0, APPLY, [jal(E)]),
    ('size not a multiple of 4', dict(size=0x22), 0, APPLY, [jal(E)]),
    ('hook 0', dict(hook=0), 0, APPLY, [jal(E)]),
    ('load 0', dict(load=0, entry=E), 0, INVALID, None),
    ('entry 0', dict(entry=0), 0, INVALID, None),
    ('entry outside the payload', dict(entry=0x01600000), 0, APPLY, [jal(0x01600000)]),
    ('hook inside the payload', dict(hook=E + 8), 0, APPLY, [jal(E)]),
    ('payload inside the core', dict(load=0x2f0000), 0, APPLY, [jal(0x2f0000)]),
    ('no name', dict(name=b''), 0, INVALID, None),
    ('byte 0x08 = 1', dict(patch={0x08: 1}), 0, INVALID, None),
    ('byte 0x09 = 1', dict(patch={0x09: 1}), 0, INVALID, None),
    ('byte 0x0b = 1', dict(patch={0x0b: 1}), 0, INVALID, None),
    ('byte 0x0d = 1', dict(patch={0x0d: 1}), 0, INVALID, None),
    ('byte 0x0f = 1', dict(patch={0x0f: 1}), 0, INVALID, None),
    ('byte 0x1f = 1', dict(patch={0x1f: 1}), 0, INVALID, None),
    ('byte 0x34 = 1', dict(patch={0x34: 1}), 0, INVALID, None),
    ('byte 0x3f = 1', dict(patch={0x3f: 1}), 0, INVALID, None),
    ('byte 0x33 = 1, inside the name', dict(patch={0x33: 1}), 0, APPLY, [jal(E)]),
    ('another slot\'s name', dict(patch={7: ord('1')}), 0, INVALID, None),
    ('size field is not the file size', dict(filesize=0x40 + 0x24), 0, INVALID, None),
    ('file of 0x43 bytes', dict(size=0, filesize=0x43), 0, INVALID, None),
    ('size 0', dict(size=0), 0, INVALID, None),
]
# Files the original applies and launcHER can place inside the staged core.
IN_CORE = [
    ('format 1', {}),
    ('byte 0x0e = 2', dict(be=2)),
    ('format 3 revision 0', dict(fmt=3, ba=0)),
    ('format 2 width 0', dict(fmt=2, ba=0)),
    ('format 2 width 1', dict(fmt=2, ba=1)),
    ('format 2 width 2', dict(fmt=2, ba=2)),
    ('format 2 width 3', dict(fmt=2, ba=3)),
    ('format 2 width 4', dict(fmt=2, ba=4)),
]


def build(directory, extra=''):
    wrapper = Path(directory) / 'wrapper.c'
    wrapper.write_text(extra or 'int unused_wrapper;\n')
    library = Path(directory) / ('trojan.dll' if os.name == 'nt' else 'trojan.so')
    subprocess.run(['gcc', '-shared', '-fPIC', '-std=c99', '-Wall', '-Wextra', '-Werror',
                    '-I', str(ROOT / 'common/include'), str(wrapper)] +
                   [str(ROOT / 'common/src' / name) for name in COMMON] +
                   ['-o', str(library)], check=True)
    lib = c.CDLL(str(library))
    lib.pops_trojan_verdict.argtypes = [c.c_void_p, c.c_size_t, c.c_uint, c.c_uint,
                                        c.POINTER(Info)]
    lib.pops_fix_context_init.argtypes = [c.POINTER(Context), c.c_void_p, c.c_size_t, c.c_uint8]
    lib.pops_fix_stage_trojan.argtypes = [c.POINTER(Context), c.POINTER(TrojanSet), c.c_void_p,
                                          c.c_size_t, c.c_void_p, c.c_size_t, c.c_uint]
    lib.pops_fix_trojan_header.argtypes = [c.POINTER(TrojanSet), c.c_void_p, c.c_size_t, c.c_uint,
                                           c.c_size_t]
    lib.pops_trojan_reason_text.restype = c.c_char_p
    lib.pops_trojan_reason_text.argtypes = [c.c_uint]
    lib.pops_trojan_scan.argtypes = [c.c_void_p, c.c_uint32, c.c_uint32, c.c_uint32, c.c_void_p,
                                     c.c_size_t, c.POINTER(c.c_uint32)]
    lib.pops_trojan_in_arena.argtypes = [c.c_uint32, c.c_uint32]
    lib.pops_trojan_copy_out.argtypes = [c.POINTER(TrojanSet), c.c_void_p, c.c_uint32, c.c_uint32,
                                         c.POINTER(Keep), c.c_uint]
    lib.pops_trojan_set_init.argtypes = [c.POINTER(TrojanSet), c.c_uint, c.c_int]
    lib.pops_trojan_set_init.restype = None
    lib.pops_resident_check_image.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(ResidentHeader)]
    lib.pops_resident_hook_gp1.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
    lib.pops_resident_slot_chain_possible.argtypes = [c.c_void_p, c.c_size_t,
                                                      c.POINTER(ResidentHeader)]
    lib.pops_resident_hook_slot_chain.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(ResidentHeader),
                                                  c.POINTER(TrojanSet), c.c_uint]
    return lib


class Session:
    """A staged core, its fix-file context and one launch's TROJAN set."""

    def __init__(self, test, core, builtin=0, hold=0x40000, work=0x10000, offered=False,
                 fingerprint_break=False):
        self.test, self.lib = test, test.lib
        self.memory = bytearray(core)
        self.pointer = (c.c_ubyte * len(self.memory)).from_buffer(self.memory)
        self.hold = (c.c_ubyte * hold)() if hold else None
        self.work = (c.c_ubyte * work)() if work else None
        self.context = Context()
        self.state = TrojanSet()
        self.lib.pops_trojan_set_init(c.byref(self.state), builtin, int(fingerprint_break))
        self.state.chain_offered = int(offered)
        self.state.hold_size, self.state.work_size = hold, work
        self.state.hold = c.cast(self.hold, c.c_void_p) if hold else None
        self.state.work = c.cast(self.work, c.c_void_p) if work else None
        test.assertEqual(self.lib.pops_fix_context_init(c.byref(self.context), self.pointer,
                                                        len(self.memory), 0), 0)

    def slot_words(self):
        return [list(run) for run in self.state.slot_word]

    def install(self, header, slot4=SLOT4_AS_FILES):
        return self.lib.pops_resident_hook_slot_chain(self.pointer, len(self.memory),
                                                      c.byref(header), c.byref(self.state), slot4)

    def stage(self, data, slot=0):
        return self.lib.pops_fix_stage_trojan(c.byref(self.context), c.byref(self.state),
                                              self.pointer, len(self.memory), data, len(data), slot)

    def records(self):
        return [(p.address, p.size, p.hold) for p in self.state.payload[:self.state.payload_count]]

    def copy_out(self, ram, base, keep=()):
        """-> (result, ram after)."""
        array = (c.c_ubyte * len(ram)).from_buffer_copy(ram)
        ranges = (Keep * max(1, len(keep)))(*[Keep(a, b) for a, b in keep])
        result = self.lib.pops_trojan_copy_out(c.byref(self.state), array, base, base + len(ram),
                                               ranges, len(keep))
        return result, bytes(array)


FNV_PRIME, M32 = 0x01000193, 0xffffffff


def fnv1a(data):
    value = 0x811c9dc5
    for byte in data:
        value = ((value ^ byte) * FNV_PRIME) & M32
    return value


@functools.lru_cache(maxsize=None)
def run_with_sum(target, seed):
    """0x30 made-up bytes whose FNV-1a sum is `target`: 44 from `seed`, then
    four found by meeting in the middle (two bytes forward, two back)."""
    inverse = pow(FNV_PRIME, -1, 1 << 32)
    generator = random.Random(seed)
    while True:
        head = bytes(generator.randrange(256) for _ in range(44))
        start = fnv1a(head)
        forward = {}
        for a in range(256):
            first = ((start ^ a) * FNV_PRIME) & M32
            for b in range(256):
                forward[((first ^ b) * FNV_PRIME) & M32] = (a, b)
        for d in range(256):
            third = ((target * inverse) & M32) ^ d
            for e in range(256):
                second = ((third * inverse) & M32) ^ e
                if second in forward:
                    data = head + bytes(forward[second] + (e, d))
                    assert fnv1a(data) == target and len(data) == 0x30
                    return data


def release(lib):
    if os.name == 'nt' and getattr(lib, '_handle', None):
        c.windll.kernel32.FreeLibrary.argtypes = [c.c_void_p]
        c.windll.kernel32.FreeLibrary(lib._handle)


SOURCE_WRAPPER = '''
#include "pops_modes_patches.h"
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#define PATH_MAX 1024
#define DPRINTF(...) ((void)0)
static char host_fix_buffer[0x100000];
static unsigned char host_hold[0x1000], host_work[0x10000];
static char log_text[0x4000];
static size_t log_used;
static void msg(const char *format, ...) {
  va_list arguments;
  va_start(arguments, format);
  int wrote = vsnprintf(log_text + log_used, sizeof(log_text) - log_used, format, arguments);
  va_end(arguments);
  if (wrote > 0 && (size_t)wrote < sizeof(log_text) - log_used) log_used += (size_t)wrote;
}
/* Failures the device can give. fail_reads: the n-th read call from now
 * and every one after it fails (0: none). fault_name / fault_kind: the
 * file whose name ends so fails its open (1) or its size query (2). */
static int fail_reads, read_calls, fault_kind, fault_fd = -1;
static char fault_name[64];
static ssize_t test_read(int fd, void *buffer, size_t size) {
  if (fail_reads && ++read_calls >= fail_reads) { errno = EIO; return -1; }
  return read(fd, buffer, size);
}
static int test_open(const char *path, int flags) {
  size_t length = strlen(path), name = strlen(fault_name);
  int match = fault_kind && length >= name && !strcmp(path + length - name, fault_name);
  if (match && fault_kind == 1) { errno = EIO; return -1; }
  int fd = open(path, flags | O_BINARY);
  if (match && fault_kind == 2) fault_fd = fd;
  return fd;
}
static off_t test_lseek(int fd, off_t offset, int whence) {
  if (fd == fault_fd && whence == SEEK_END) { errno = EIO; return -1; }
  return lseek(fd, offset, whence);
}
static int test_close(int fd) {
  if (fd == fault_fd) fault_fd = -1;
  return close(fd);
}
#ifndef O_BINARY
#define O_BINARY 0
#endif
#define read test_read
#define open test_open
#define lseek test_lseek
#define close test_close
%s
int test_fix_files(void *core, size_t size, const char *root, const char *title,
                   unsigned fingerprint, PopsTrojanSet *set, int offered) {
  PopsFixContext state;
  pops_trojan_set_init(set, fingerprint, 0);
  set->chain_offered = (uint8_t)offered;
  set->hold = host_hold;
  set->hold_size = sizeof(host_hold);
  set->work = host_work;
  set->work_size = sizeof(host_work);
  log_used = 0;
  log_text[0] = 0;
  return pops_stage_fix_files(core, size, root, title, 0, 0, 0, 0, 0, NULL, &state, set);
}
const char *test_log(void) { return log_text; }
const unsigned char *test_hold(void) { return host_hold; }
int test_dependency(const char *path, void *buffer, size_t size, size_t *read_size) {
  return readPopsDependency(path, buffer, size, read_size);
}
void test_fail_reads(int fail) { fail_reads = fail; read_calls = 0; }
void test_fault(const char *name, int kind) {
  strncpy(fault_name, name, sizeof(fault_name) - 1);
  fault_kind = kind;
  fault_fd = -1;
}
'''


def handler_fragment():
    source = (ROOT / 'launcher/src/handler_pops.c').read_text()
    start = source.index('static int readFullFile(')
    end = source.index('/* Driver names within one role', start)
    return source[start:end].replace('(void *)0x01f00000', 'host_fix_buffer')


_BUILT = []


def tearDownModule():
    while _BUILT:
        temp, lib = _BUILT.pop()
        release(lib)
        temp.cleanup()


class Built(unittest.TestCase):
    """One host library for every class: the common sources and the launcher's loop."""

    @classmethod
    def setUpClass(cls):
        if not _BUILT:
            temp = tempfile.TemporaryDirectory()
            _BUILT.append((temp, build(temp.name, SOURCE_WRAPPER % handler_fragment())))
        cls.lib = _BUILT[0][1]

    def verdict(self, data, slot=0, builtin=0):
        info = Info()
        result = self.lib.pops_trojan_verdict(data, len(data), slot, builtin, c.byref(info))
        return result, info

    def staged(self, core, data, slot=0, builtin=0):
        """-> (result, reason, core after)."""
        session = Session(self, core, builtin)
        result = session.stage(data, slot)
        return result, session.state.reason, bytes(session.memory)

    def scan(self, payload, load, entry=None):
        work = (c.c_ubyte * max(8, len(payload) // 16 + 8))()
        flags = c.c_uint32(0xdead)
        result = self.lib.pops_trojan_scan(payload, len(payload), load,
                                           load if entry is None else entry, work, len(work),
                                           c.byref(flags))
        return None if result else flags.value


class Native(Built):
    def test_verdict_and_hook_words(self):
        for label, arguments, builtin, verdict, words in CASES:
            with self.subTest(label):
                data = trojan(**arguments)
                result, info = self.verdict(data, 0, builtin)
                self.assertEqual(result, verdict)
                if verdict == INVALID:
                    self.assertEqual(bytes(info), bytes(Info()), 'output written for an Invalid file')
                    continue
                load, entry, hook = struct.unpack_from('<3I', data, 0x10)
                self.assertEqual((info.load, info.entry, info.hook, info.size, info.slot),
                                 (load, entry, hook, len(data) - 0x40, 0))
                if words is not None:
                    self.assertEqual(list(info.hook_word)[:info.hook_words], words)

    def test_every_slot_reads_its_own_name_only(self):
        for slot in range(10):
            for named in range(10):
                result, _ = self.verdict(trojan(slot=named), slot)
                self.assertEqual(result, APPLY if slot == named else INVALID)
        info = Info()
        data = trojan()
        self.assertLess(self.lib.pops_trojan_verdict(data, len(data), 10, 0, c.byref(info)), 0)
        self.assertLess(self.lib.pops_trojan_verdict(None, 0x60, 0, 0, c.byref(info)), 0)
        self.assertLess(self.lib.pops_trojan_verdict(data, len(data), 0, 0, None), 0)

    def test_each_header_byte_alone(self):
        # One byte of a good header changed at a time: which bytes matter.
        good = trojan()
        # The name (its first byte only has to stay nonzero) and byte 0x0e,
        # which passes with any nonzero value.
        ignored = set(range(0x20, 0x34)) | {0x0e}
        for offset in range(0x40):
            data = bytearray(good)
            data[offset] ^= 0x40
            result, _ = self.verdict(bytes(data))
            if offset in ignored or offset in range(0x10, 0x1c):
                self.assertEqual(result, APPLY, hex(offset))
            else:
                self.assertEqual(result, INVALID, hex(offset))

    def test_skips_write_nothing(self):
        core = bytes(pristine())
        for label, arguments, builtin, verdict, _ in CASES:
            if verdict == APPLY:
                continue
            with self.subTest(label):
                result, _, after = self.staged(core, trojan(**arguments), 0, builtin)
                self.assertEqual(result, SKIP_INVALID if verdict == INVALID else SKIP_OUTDATED)
                self.assertEqual(after, core)

    def test_in_core_payload_and_hook_words(self):
        core = bytes(pristine())
        for label, arguments in IN_CORE:
            with self.subTest(label):
                data = trojan(load=0x2f0000, hook=0x2f0100, **arguments)
                result, _, after = self.staged(core, data)
                self.assertEqual(result, 0)
                _, info = self.verdict(data)
                expected = bytearray(core)
                expected[0xf0000:0xf0020] = data[0x40:]
                struct.pack_into('<%dI' % info.hook_words, expected, 0xf0100,
                                 *list(info.hook_word)[:info.hook_words])
                self.assertEqual(after, bytes(expected))

    def test_files_the_original_applies_and_launcher_does_not(self):
        core = bytes(pristine())
        for label, arguments, reason in [
                ('load not a multiple of 4', dict(load=0x2f0002, hook=0x2f0100), NO_UNALIGNED),
                ('hook not a multiple of 4', dict(load=0x2f0000, hook=0x2f0102), NO_UNALIGNED),
                ('size not a multiple of 4', dict(load=0x2f0000, hook=0x2f0100, size=0x22),
                 NO_UNALIGNED),
                ('entry outside the payload', dict(load=0x2f0000, entry=0x2f0020, hook=0x2f0100),
                 NO_ENTRY),
                ('hook 0', dict(load=0x2f0000, hook=0), NO_HOOK),
                ('hook inside the payload', dict(load=0x2f0000, hook=0x2f0008), NO_HOOK),
                ('width 3 hook ending past the core', dict(load=0x2f0000, fmt=2, ba=3,
                                                           hook=BASE + SIZE - 8), NO_HOOK),
                ('payload ending past the core', dict(load=BASE + SIZE - 0x10, hook=0x2f0100),
                 NO_RANGE),
                ('payload between the core and the arena', dict(load=0x01300000, hook=0x2f0100),
                 NO_RANGE),
                ('payload crossing the arena start', dict(load=0x0141fff0, hook=0x2f0100), NO_RANGE),
                ('payload over the resident image', dict(load=0x0143a000, hook=0x2f0100), NO_RANGE),
                ('payload running into the resident image', dict(load=0x01439ff0, hook=0x2f0100),
                 NO_RANGE),
                ('payload over the breakpoint handler', dict(load=0x014601f0, hook=0x2f0100),
                 NO_RANGE),
                ('payload past the arena end', dict(load=0x015ffff0, hook=0x2f0100), NO_RANGE),
                ('payload in POPStarter\'s first part of the core', dict(load=0x232e00,
                                                                       hook=0x2f0100), NO_RANGE),
                ('payload in POPStarter\'s second part', dict(load=0x2397e0, hook=0x2f0100),
                 NO_RANGE),
                ('hook in POPStarter\'s first part, not a slot', dict(hook=0x232790), NO_HOOK),
                ('hook on a slot\'s second word', dict(hook=0x2327d4), NO_HOOK),
                ('hook on the word after the slots', dict(hook=0x2327f8), NO_HOOK),
                ('hook on the jump after the second five', dict(hook=0x232d30), NO_HOOK),
                ('hook in POPStarter\'s second part', dict(hook=0x2397d8), NO_HOOK),
                ('width 2 hook running into the first part', dict(fmt=2, ba=2, hook=0x23278c),
                 NO_HOOK)]:
            with self.subTest(label):
                data = trojan(**arguments)
                self.assertEqual(self.verdict(data)[0], APPLY)
                result, got, after = self.staged(core, data)
                self.assertEqual((result, got), (SKIP_UNHOSTED, reason))
                self.assertEqual(after, core)
                self.assertNotIn(b'unknown', self.lib.pops_trojan_reason_text(reason))

    def test_a_changed_tracked_site_is_an_error_not_a_skip(self):
        for load in (0x2f0000, 0x01500000):
            session = Session(self, pristine())
            session.memory[0x210318 - BASE] ^= 1
            before = bytes(session.memory)
            self.assertLess(session.stage(trojan(load=load, hook=0x2f0100)), 0)
            self.assertEqual(bytes(session.memory), before)
            self.assertEqual((session.state.payload_count, session.state.hold_used), (0, 0))

    def test_without_a_set_nothing_is_hosted(self):
        memory = pristine()
        pointer = (c.c_ubyte * SIZE).from_buffer(memory)
        context = Context()
        self.assertEqual(self.lib.pops_fix_context_init(c.byref(context), pointer, SIZE, 0), 0)
        for data, expected in ((trojan(load=0x2f0000, hook=0x2f0100), SKIP_UNHOSTED),
                               (trojan(be=0), SKIP_INVALID)):
            self.assertEqual(self.lib.pops_fix_stage_trojan(c.byref(context), None, pointer, SIZE,
                                                            data, len(data), 0), expected)
        self.assertEqual(memory, pristine())
        del pointer

    def test_the_header_decision(self):
        state = TrojanSet()
        self.lib.pops_trojan_set_init(c.byref(state), 0, 0)
        good = trojan(size=0x100)
        for data, size, capacity, expected in (
                (good[:0x40], len(good), 0x100000, 0),
                (good[:0x40], len(good), len(good), 0),
                (good[:0x40], len(good), len(good) - 1, SKIP_UNHOSTED),
                (good[:0x40], len(good) + 4, 0x100000, SKIP_INVALID),
                (good[:0x40], 0x43, 0x100000, SKIP_INVALID),
                (bytes(0x40), len(good), 0x100000, SKIP_INVALID),
                (trojan(fmt=3, ba=5)[:0x40], 0x60, 0x10, SKIP_UNHOSTED)):
            state.reason = 0
            self.assertEqual(self.lib.pops_fix_trojan_header(c.byref(state), data, size, 0, capacity),
                             expected, (size, capacity))
            self.assertEqual(state.reason, NO_LARGE if expected == SKIP_UNHOSTED else 0)
        # The outdated rule reads the set's fingerprint entry.
        self.lib.pops_trojan_set_init(c.byref(state), 7, 0)
        self.assertEqual(self.lib.pops_fix_trojan_header(c.byref(state), trojan(fmt=3, ba=5)[:0x40],
                                                         0x60, 0, 0x10), SKIP_OUTDATED)
        self.assertEqual(self.lib.pops_fix_trojan_header(None, good[:0x40], len(good), 0, 0), SKIP_UNHOSTED)
        self.assertEqual(self.lib.pops_fix_trojan_header(None, None, len(good), 0, 0), -errno.EINVAL)
        self.assertEqual(self.lib.pops_fix_trojan_header(None, good[:0x40], len(good), 10, 0x100000),
                         -errno.EINVAL)
        self.assertNotIn(b'unknown', self.lib.pops_trojan_reason_text(NO_LARGE))

    def test_arena(self):
        for address, size, expected in [
                (0x01420000, 4, 1), (0x0141fffc, 8, 0), (0x01439ffc, 4, 1), (0x01439ffc, 8, 0),
                (0x0143a000, 4, 0), (0x014601fc, 4, 0), (0x01460200, 4, 1), (0x015ffffc, 4, 1),
                (0x015ffffc, 8, 0), (0x01600000, 4, 0), (0x01420000, 0, 0),
                (0x01420000, 0x1e0000, 0), (0x01460200, 0x19fe00, 1), (0x01500000, 0xfffffff0, 0),
                (0x00200000, 4, 0)]:
            with self.subTest(hex(address)):
                self.assertEqual(self.lib.pops_trojan_in_arena(address, size), expected)
                self.assertEqual(model.in_arena(address, size), bool(expected))

    def test_payload_above_the_image_is_held_and_copied_at_handoff(self):
        session = Session(self, pristine())
        first = trojan(load=0x01500000, hook=0x2f0100, payload=code(*range(0x100, 0x110)))
        second = trojan(slot=1, load=0x01500020, hook=0x2f0104, entry=0x01500020,
                        payload=code(*range(0x200, 0x210)))
        low = trojan(slot=2, load=0x01420000, hook=0x2f0108)
        self.assertEqual([session.stage(first), session.stage(second, 1), session.stage(low, 2)],
                         [0, 0, 0])
        expected = pristine()
        struct.pack_into('<3I', expected, 0xf0100, jal(0x01500000), jal(0x01500020),
                         jal(0x01420000))
        self.assertEqual(session.memory, expected)
        self.assertEqual(session.records(), [(0x01500000, 0x40, 0), (0x01500020, 0x40, 0x40),
                                             (0x01420000, 0x20, 0x80)])
        self.assertEqual(bytes(session.hold[:0xa0]), first[0x40:] + second[0x40:] + low[0x40:])
        ram = bytes([0xa5]) * 0x200000
        result, after = session.copy_out(ram, 0x01400000, keep=[(0x01000000, 0x01302e60),
                                                                (0x0143a000, 0x01460200)])
        self.assertEqual(result, 3)
        wanted = bytearray(ram)
        wanted[0x100000:0x100040] = first[0x40:]
        wanted[0x100020:0x100060] = second[0x40:]  # the later file wins where they overlap
        wanted[0x20000:0x20020] = low[0x40:]
        self.assertEqual(after, bytes(wanted))

    def test_copy_out_checks_every_record_before_the_first_write(self):
        ram = bytes([0xa5]) * 0x200000

        def session():
            made = Session(self, pristine())
            for slot, load in enumerate((0x01500000, 0x01510000)):
                self.assertEqual(made.stage(trojan(slot=slot, load=load, hook=0x2f0100 + 4 * slot),
                                            slot), 0)
            return made

        self.assertEqual(session().copy_out(ram, 0x01400000)[0], 2)
        for label, change, base, keep in [
                ('second record inside the resident image',
                 lambda s: setattr(s.state.payload[1], 'address', 0x0143a000), 0x01400000, ()),
                ('second record below the arena',
                 lambda s: setattr(s.state.payload[1], 'address', 0x01410000), 0x01400000, ()),
                ('second record not a multiple of 4',
                 lambda s: setattr(s.state.payload[1], 'address', 0x01510002), 0x01400000, ()),
                ('second record longer than what is held',
                 lambda s: setattr(s.state.payload[1], 'size', 0x24), 0x01400000, ()),
                ('second record held past the used part',
                 lambda s: setattr(s.state.payload[1], 'hold', 0x40), 0x01400000, ()),
                ('more records than the set holds',
                 lambda s: setattr(s.state, 'payload_count', 21), 0x01400000, ()),
                ('more held than the holding memory',
                 lambda s: setattr(s.state, 'hold_used', 0x40001), 0x01400000, ()),
                ('second record on a range to keep', lambda s: None, 0x01400000,
                 [(0x01000000, 0x01302e60), (0x0151001c, 0x01510020)]),
                ('memory that starts above the first record', lambda s: None, 0x01500004, ()),
                ('memory that ends below the second record',
                 lambda s: None, 0x01400000 - 0xf0000 - 4, ())]:
            with self.subTest(label):
                made = session()
                change(made)
                result, after = made.copy_out(ram, base, keep)
                self.assertLess(result, 0)
                self.assertEqual(after, ram)
        made = session()
        made.state.hold = None
        self.assertLess(made.copy_out(ram, 0x01400000)[0], 0)
        self.assertEqual(Session(self, pristine()).copy_out(ram, 0x01400000), (0, ram))

    def test_copy_out_refuses_a_null_pointer(self):
        # On the console address 0 is real memory and a pointer to all of RAM
        # is null: the launcher must hand over the arena instead.
        made = Session(self, pristine())
        self.assertEqual(made.stage(trojan(load=0x01500000, hook=0x2f0100)), 0)
        self.assertLess(self.lib.pops_trojan_copy_out(c.byref(made.state), None, 0, 0x02000000,
                                                      None, 0), 0)
        ram = bytes(0x1e0000)
        result, after = made.copy_out(ram, 0x01420000)
        self.assertEqual(result, 1)
        self.assertEqual(after[0xe0000:0xe0020], trojan()[0x40:])

    def test_copy_out_refuses_a_destination_inside_the_holding_memory(self):
        made = Session(self, pristine())
        self.assertEqual(made.stage(trojan(load=0x01500000, hook=0x2f0100)), 0)
        # The memory handed over is the holding memory itself.
        base = 0x01500000 - 0x100
        result = self.lib.pops_trojan_copy_out(c.byref(made.state), made.hold, base,
                                               base + len(made.hold), None, 0)
        self.assertLess(result, 0)
        self.assertEqual(bytes(made.hold[0x100:0x120]), bytes(0x20))

    def test_holding_memory_limits(self):
        session = Session(self, pristine(), hold=0x30)
        self.assertEqual(session.stage(trojan(load=0x01500000, hook=0x2f0100)), 0)
        self.assertEqual(session.stage(trojan(slot=1, load=0x01510000, hook=0x2f0104), 1),
                         SKIP_UNHOSTED)
        self.assertEqual((session.state.reason, session.state.payload_count,
                          session.state.hold_used), (NO_SPACE, 1, 0x20))
        self.assertEqual(session.stage(trojan(slot=2, load=0x01510000, hook=0x2f0104, size=0x10),
                                       2), 0)
        session = Session(self, pristine())
        for index in range(20):
            self.assertEqual(session.stage(trojan(load=0x01500000 + 0x100 * index,
                                                  hook=0x2f0100)), 0)
        before = bytes(session.memory)
        self.assertEqual(session.stage(trojan(load=0x01508000, hook=0x2f0104)), SKIP_UNHOSTED)
        self.assertEqual((session.state.reason, session.state.payload_count), (NO_SPACE, 20))
        self.assertEqual(bytes(session.memory), before)
        # No holding memory: nothing above the image. No work memory: nothing at all.
        session = Session(self, pristine(), hold=0)
        self.assertEqual(session.stage(trojan(load=0x01500000, hook=0x2f0100)), SKIP_UNHOSTED)
        self.assertEqual(session.state.reason, NO_RANGE)
        self.assertEqual(session.stage(trojan(load=0x2f0000, hook=0x2f0100)), 0)
        session = Session(self, pristine(), work=0)
        self.assertEqual(session.stage(trojan(load=0x2f0000, hook=0x2f0100)), SKIP_UNHOSTED)
        self.assertEqual(session.state.reason, NO_SPACE)
        session = Session(self, pristine(), work=8)
        self.assertEqual(session.stage(trojan(load=0x2f0000, hook=0x2f1000, size=0x400)),
                         SKIP_UNHOSTED)
        self.assertEqual(session.state.reason, NO_SPACE)

    SCANS = [
        ('nothing named', [lui(K0, 0x0021), ori(K0, K0, 0xa63c), sw(K1, 0, K0)] + JR_RA, 0),
        ('j into the 480p handler', [0x08000000 | 0x2394f0 >> 2, 0], model.REF_480P),
        ('jal into the second part', [0x0c000000 | 0x2397d8 >> 2, 0] + JR_RA, model.REF_BLOCK2),
        ('store to a slot through lui and ori',
         [lui(K0, 0x0023), ori(K0, K0, 0x27e0), sw(K1, 0, K0)] + JR_RA, model.REF_SLOT),
        ('store to a slot through lui and an offset', [lui(K0, 0x0023), sw(K1, 0x2d10, K0)] + JR_RA,
         model.REF_SLOT),
        ('load from a slot\'s second word', [lui(K0, 0x0023), lw(K1, 0x27dc, K0)] + JR_RA,
         model.REF_SLOT),
        ('return to the word after the slots',
         [lui(RA, 0x0023), ori(RA, RA, 0x27f8), jr(RA), 0], model.REF_SLOT),
        ('store to the word after the slots', [lui(K0, 0x0023), sw(K1, 0x27f8, K0)] + JR_RA,
         model.REF_BLOCK1),
        ('load from the jump after the second five', [lui(K0, 0x0023), lw(K1, 0x2d34, K0)] + JR_RA,
         model.REF_BLOCK1),
        ('store into the first part', [lui(K0, 0x0023), sw(K1, 0x2790, K0)] + JR_RA,
         model.REF_BLOCK1),
        ('a constant that is jal to the built-in fix',
         [lui(K1, 0x0c50), ori(K1, K1, 0x4000)] + JR_RA, model.REF_BUILTIN),
        ('a constant made with addiu from a negative half',
         [lui(K1, 0x0144), addiu(K1, K1, -0x5a28)] + JR_RA, model.REF_OWNED),
        ('a constant made in another register',
         [lui(K0, 0x0146), ori(K1, K0, 0x0100)] + JR_RA, model.REF_OWNED),
        ('store into launcHER\'s resident range', [lui(K0, 0x0144), sw(K1, -0x5a28, K0)] + JR_RA,
         model.REF_OWNED),
        ('jal into POPStarter\'s program', [0x0c000000 | 0x880a24 >> 2, 0] + JR_RA, model.REF_MAIN),
        ('a plain constant inside POPStarter\'s program',
         [lui(K0, 0x0088), ori(K0, K0, 0x0a24)] + JR_RA, 0),
        ('load through gp', [lw(K0, -0x7dd8, GP)] + JR_RA, 0),
        ('a word after the return is data', JR_RA + [0x08000000 | 0x2394f0 >> 2, 0], 0),
        ('a branch target is read', [beq(1, 2, 3), 0] + JR_RA + [0x08000000 | 0x2394f0 >> 2, 0],
         model.REF_480P),
        ('a branch out of the payload', [beq(1, 2, -0x100), 0] + JR_RA, 0),
        ('the delay slot of the return is read',
         [lui(K0, 0x0023), jr(RA), sw(K1, 0x27e0, K0)], model.REF_SLOT),
        ('constants are forgotten after a branch',
         [lui(K0, 0x0023), beq(1, 2, 1), 0, sw(K1, 0x27e0, K0)] + JR_RA, 0),
        ('constants are forgotten after a call',
         [lui(K0, 0x0023), 0x0c000000 | 0x210540 >> 2, 0, sw(K1, 0x27e0, K0)] + JR_RA, 0),
        ('a register written by something else is forgotten',
         [lui(K0, 0x0023), 0x0000d021, sw(K1, 0x27e0, K0)] + JR_RA, 0),
        ('a j word the payload builds for its own routine makes that routine read',
         [lui(K1, 0x0800 | 0x01500020 >> 18), ori(K1, K1, (0x01500020 >> 2) & 0xffff)] + JR_RA +
         [0, 0, 0, 0, 0x08000000 | 0x2394f0 >> 2, 0], model.REF_480P),
        ('jr to a constant inside the payload makes it read',
         [lui(K0, 0x0150), ori(K0, K0, 0x0020), jr(K0), 0, 0, 0, 0, 0,
          0x0c000000 | 0x238a90 >> 2, 0] + JR_RA, model.REF_BLOCK2),
        ('several', [lui(K0, 0x0023), sw(K1, 0x27e0, K0), 0x0c000000 | 0x2394f0 >> 2, 0,
                     lui(K0, 0x0141), sw(K1, 0, K0)] + JR_RA,
         model.REF_SLOT | model.REF_480P | model.REF_BUILTIN),
    ]

    def test_scan_flags(self):
        for label, words, flags in self.SCANS:
            with self.subTest(label):
                payload = code(*words)
                self.assertEqual(self.scan(payload, 0x01500000), flags)
                self.assertEqual(model.scan(payload, 0x01500000, 0x01500000), flags)

    def test_scan_never_counts_the_payload_itself(self):
        payload = code(lui(K0, 0x0024), sw(K1, -0x6b00, K0), 0x08000000 | 0x239508 >> 2, 0)
        self.assertEqual(self.scan(payload, 0x239500), 0)
        self.assertEqual(self.scan(payload, 0x01500000), model.REF_480P)

    def test_scan_refuses_bad_arguments(self):
        good = code(*JR_RA)
        for payload, load, entry in [(good, 0x01500002, 0x01500002), (good[:6], 0x01500000, None),
                                     (good, 0x01500000, 0x01500008), (good, 0x01500000, 0x014ffffc),
                                     (good, 0x01500000, 0x01500002), (good, 0xfffffffc, 0xfffffffc)]:
            self.assertIsNone(self.scan(payload, load, entry))
            self.assertIsNone(model.scan(payload, load, load if entry is None else entry))
        flags = c.c_uint32(7)
        work = (c.c_ubyte * 64)()
        big = code(*([0] * 64))
        self.assertLess(self.lib.pops_trojan_scan(big, len(big), E, E, work, 15, c.byref(flags)), 0)
        self.assertLess(self.lib.pops_trojan_scan(big, 0, E, E, work, 64, c.byref(flags)), 0)
        self.assertLess(self.lib.pops_trojan_scan(None, len(big), E, E, work, 64, c.byref(flags)), 0)
        self.assertLess(self.lib.pops_trojan_scan(big, len(big), E, E, None, 64, c.byref(flags)), 0)
        self.assertEqual(flags.value, 7)
        self.assertEqual(self.lib.pops_trojan_scan(big, len(big), E, E, work, 16, c.byref(flags)), 0)

    def test_scan_matches_the_python_twin_on_random_programs(self):
        # Words biased towards what the scan reads, around the places it flags.
        rng = random.Random(0x7a0)
        highs = [0x0023, 0x0024, 0x0141, 0x0144, 0x0146, 0x0150, 0x0088, 0x0021, 0x0c50, 0x0808,
                 0x0c08, 0x0854]
        lows = [0x2790, 0x27d0, 0x27e0, 0x27f8, 0x2d08, 0x2d30, 0x94f0, 0x9758, 0x97d8, 0x8a90,
                0xa000, 0x0000, 0x0100, 0x0020, 0x0040, 0xe53c, 0xe5d6]
        seen = set()
        for _ in range(1500):
            count = rng.randrange(4, 64)
            words = []
            for _ in range(count):
                kind = rng.randrange(12)
                rs, rt = rng.choice((0, 26, 27, 28, 31, 2)), rng.choice((0, 26, 27, 31, 2))
                if kind < 2:
                    words.append(lui(rt, rng.choice(highs)))
                elif kind < 4:
                    words.append(rng.choice((ori, addiu))(rt, rs, rng.choice(lows)))
                elif kind < 6:
                    words.append(rng.choice((sw, lw))(rt, rng.choice(lows), rs))
                elif kind == 6:
                    words.append(rng.choice((0x08000000, 0x0c000000)) |
                                 rng.choice((0x2394f0, 0x2327e0, 0x2327f8, 0x238a90, 0x01410000,
                                             0x01500000 + 4 * rng.randrange(count), 0x210540)) >> 2)
                elif kind == 7:
                    words.append(beq(rs, rt, rng.randrange(-count, count)))
                elif kind == 8:
                    words.append(rng.choice((jr(rs), rs << 21 | 31 << 11 | 9)))
                elif kind == 9:
                    words.append(0)
                else:
                    words.append(rng.getrandbits(32))
            payload = code(*words)
            entry = 0x01500000 + 4 * rng.randrange(count)
            got = self.scan(payload, 0x01500000, entry)
            self.assertEqual(got, model.scan(payload, 0x01500000, entry), words)
            seen.add(got)
        self.assertGreater(len(seen), 12)

    def test_files_refused_for_what_their_payload_names(self):
        for label, words, flags in self.SCANS:
            reason = {model.REF_480P: NO_480P, model.REF_BLOCK2: NO_BLOCK2,
                      model.REF_BUILTIN: NO_BUILTIN, model.REF_OWNED: NO_OWNED,
                      model.REF_BLOCK1: NO_BLOCK1, model.REF_MAIN: NO_MAIN,
                      0: 0}.get(model.refusal(flags), None)
            if flags == model.REF_SLOT:
                reason = NO_SLOT
            with self.subTest(label):
                for load in (0x01500000, 0x2f0000):
                    payload = code(*words)
                    if load != 0x01500000 and self.scan(payload, load) != flags:
                        continue  # the program's own addresses are part of it
                    session = Session(self, pristine())
                    result = session.stage(trojan(load=load, hook=0x2f0100, payload=payload))
                    self.assertEqual((result, session.state.reason, session.state.refs),
                                     (SKIP_UNHOSTED if reason else 0, reason, flags))
                    if reason:
                        self.assertEqual(session.memory, pristine())
                        self.assertEqual(session.state.payload_count, 0)
                        self.assertNotIn(b'unknown', self.lib.pops_trojan_reason_text(reason))

    def test_a_slot_hook_needs_the_slot_chain(self):
        for hook in model.SLOT_HOOKS.values():
            session = Session(self, pristine())
            self.assertEqual(session.stage(trojan(hook=hook)), SKIP_UNHOSTED)
            self.assertEqual(session.state.reason, NO_SLOT)
            self.assertEqual(session.memory, pristine())
            self.assertEqual((session.state.chain, session.state.payload_count), (0, 0))
            self.assertEqual(session.slot_words(), EMPTY_RUNS)

    def test_a_new_set_holds_ten_empty_slots(self):
        state = TrojanSet(reason=9, payload_count=3, chain=1, chain_offered=1)
        self.lib.pops_trojan_set_init(c.byref(state), 321, 0)
        self.assertEqual(bytes(state)[2:8], bytes(6))
        self.assertEqual((state.fingerprint_id, state.chain, state.chain_offered), (321, 0, 0))
        self.assertEqual([list(run) for run in state.slot_word], EMPTY_RUNS)
        # A fingerprint entry with a breakpoint handler: its call is in the
        # first slot of the second run before any file is read.
        self.lib.pops_trojan_set_init(c.byref(state), 7, 1)
        self.assertEqual([list(run) for run in state.slot_word],
                         [EMPTY_RUNS[0], [BREAK_CALL, 0] + EMPTY_RUNS[1][2:]])
        self.lib.pops_trojan_set_init(None, 0, 0)

    def test_a_slot_hook_goes_to_the_set_and_never_to_the_core(self):
        for slot, hook in model.SLOT_HOOKS.items():
            with self.subTest(slot=slot):
                session = Session(self, pristine(), offered=True)
                self.assertEqual(session.stage(trojan(hook=hook)), 0)
                self.assertEqual(session.memory, pristine())
                self.assertEqual((session.state.chain, session.state.payload_count), (1, 1))
                expected = [list(run) for run in EMPTY_RUNS]
                run, index = (0, hook - 0x2327d0) if hook < 0x232d08 else (1, hook - 0x232d08)
                expected[run][index // 4] = jal(E)
                self.assertEqual(session.slot_words(), expected)

    def test_format_2_zero_words_and_the_end_of_a_run(self):
        # Width 2 and 3 write zero words after the jump, as the original
        # does: over the slot's own second word, then over the next slot's
        # first, which then falls through. Past the fifth slot they would
        # land on what follows the slots: not hosted.
        for base in (0x2327d0, 0x232d08):
            run = 0 if base == 0x2327d0 else 1
            for position in range(5):
                for width in (1, 2, 3):
                    with self.subTest(base=hex(base), position=position, width=width):
                        session = Session(self, pristine(), offered=True)
                        result = session.stage(trojan(fmt=2, ba=width, hook=base + 8 * position))
                        fits = 2 * position + width <= 10
                        self.assertEqual(result, 0 if fits else SKIP_UNHOSTED)
                        expected = [list(r) for r in EMPTY_RUNS]
                        if fits:
                            expected[run][2 * position:2 * position + width] = \
                                [jump(E)] + [0] * (width - 1)
                        else:
                            self.assertEqual(session.state.reason, NO_SLOT)
                        self.assertEqual(session.slot_words(), expected)
                        self.assertEqual((session.state.chain, session.state.payload_count),
                                         (int(fits), int(fits)))
                        self.assertEqual(session.memory, pristine())

    def test_the_last_file_on_a_slot_wins(self):
        session = Session(self, pristine(), offered=True, fingerprint_break=True)
        self.assertEqual(session.slot_words()[1][0], BREAK_CALL)
        for slot, load in ((0, 0x01500000), (3, 0x01510000), (9, 0x01520000)):
            self.assertEqual(session.stage(trojan(slot=slot, load=load, hook=0x232d08), slot), 0)
            self.assertEqual(session.slot_words()[1][:2], [jal(load), 0])
        self.assertEqual(session.stage(trojan(fmt=2, ba=3, load=0x01530000, hook=0x232d08)), 0)
        self.assertEqual(session.slot_words(),
                         [EMPTY_RUNS[0], [jump(0x01530000), 0, 0, 0] + EMPTY_RUNS[1][4:]])
        self.assertEqual(session.state.payload_count, 4)
        self.assertEqual(session.memory, pristine())

    def test_a_payload_that_names_a_slot_needs_the_chain_too(self):
        payload = code(lui(K0, 0x23), ori(K0, K0, 0x27d8), lw(K1, 0, K0), *JR_RA)
        self.assertEqual(self.scan(payload, E), model.REF_SLOT)
        for offered in (False, True):
            session = Session(self, pristine(), offered=offered)
            result = session.stage(trojan(hook=0x2f0100, payload=payload))
            self.assertEqual((result, session.state.reason, session.state.chain),
                             (0, 0, 1) if offered else (SKIP_UNHOSTED, NO_SLOT, 0))
            expected = pristine()
            if offered:  # its hook is ordinary POPS code: written as before
                struct.pack_into('<I', expected, 0xf0100, jal(E))
            self.assertEqual(session.memory, expected)
            self.assertEqual(session.slot_words(), EMPTY_RUNS)

    def test_the_slot_chain_is_not_installed_on_anything_but_pops(self):
        header = fake_header()
        core = pristine()
        struct.pack_into('<I', core, GP1_HOOK - BASE, jal(header.gp1_entry))
        pointer = (c.c_ubyte * SIZE).from_buffer(core)
        self.assertEqual(self.lib.pops_resident_slot_chain_possible(pointer, SIZE, c.byref(header)), 0)
        self.assertEqual(self.lib.pops_resident_slot_chain_possible(None, SIZE, c.byref(header)), 0)
        self.assertEqual(self.lib.pops_resident_slot_chain_possible(pointer, SIZE, None), 0)
        del pointer
        session = Session(self, core, offered=True)
        self.assertEqual(session.stage(trojan(hook=0x2327d8)), 0)
        before = bytes(session.memory)
        # Not POPS's bytes in the two runs.
        self.assertEqual(session.install(header), -errno.EILSEQ)
        for bad in (fake_header(chain=0x0143a202), fake_header(resume_a=0x01439ffc),
                    fake_header(resume_b=0x01460000), fake_header(gp1=0)):
            self.assertEqual(session.install(bad), -errno.EINVAL)
        self.assertEqual(session.install(header, 3), -errno.EINVAL)
        self.assertEqual(self.lib.pops_resident_hook_slot_chain(None, SIZE, c.byref(header),
                                                                c.byref(session.state), 0),
                         -errno.EINVAL)
        self.assertEqual(self.lib.pops_resident_hook_slot_chain(session.pointer, SIZE, None,
                                                                c.byref(session.state), 0),
                         -errno.EINVAL)
        self.assertEqual(self.lib.pops_resident_hook_slot_chain(session.pointer, SIZE,
                                                                c.byref(header), None, 0),
                         -errno.EINVAL)
        self.assertEqual(self.lib.pops_resident_hook_slot_chain(
            session.pointer, 0x232d08 + 0x30 - BASE - 1, c.byref(header), c.byref(session.state), 0),
            -errno.ERANGE)
        # Needed but never offered: a caller's mistake, not a skip.
        session.state.chain_offered = 0
        self.assertEqual(session.install(header), -errno.EINVAL)
        self.assertEqual(bytes(session.memory), before)
        # No file needs it: nothing to do, whatever the core holds.
        idle = Session(self, core, offered=True)
        self.assertEqual(idle.install(header), 0)
        self.assertEqual(idle.install(header, SLOT4_BREAK_CALL), 0)
        self.assertEqual(bytes(idle.memory), bytes(core))
        self.assertEqual(idle.slot_words(), EMPTY_RUNS)

    def stand_in_core(self, header):
        """A core whose two runs are made-up bytes with the sums the install
        expects of POPS's own (this class has no POPS image; OriginalSlots
        runs the same install on the real one), and the launcher's GP1 jal."""
        source = (ROOT / 'common/src/pops_resident.c').read_text()
        sums = [int(re.search(r'#define SLOT_RUN_%s_PRISTINE UINT32_C\((0x[0-9a-f]{8})\)' % run,
                              source).group(1), 16) for run in 'AB']
        core = pristine()
        for base, target in zip((0x2327d0, 0x232d08), sums):
            core[base - BASE:base - BASE + 0x30] = run_with_sum(target, base)
        struct.pack_into('<I', core, GP1_HOOK - BASE, jal(header.gp1_entry))
        return core

    def test_installing_the_slots_writes_the_two_runs_and_the_gp1_jal(self):
        header = fake_header()
        possible = self.lib.pops_resident_slot_chain_possible
        for slot4, first in ((SLOT4_AS_FILES, jal(E)), (SLOT4_BREAK_CALL, BREAK_CALL),
                             (SLOT4_RESET_STORE, 0x10000001)):
            with self.subTest(slot4=slot4):
                core = self.stand_in_core(header)
                session = Session(self, core, offered=True)
                self.assertEqual(possible(session.pointer, SIZE, c.byref(header)), 1)
                self.assertEqual(session.stage(trojan(hook=0x232d08)), 0)
                self.assertEqual(session.stage(trojan(slot=1, fmt=2, ba=2, hook=0x2327e8,
                                                      load=E + 0x1000), 1), 0)
                # Staging the files wrote nothing to the core.
                self.assertEqual(bytes(session.memory), bytes(core))
                self.assertEqual(session.install(header, slot4), 1)
                expected = bytearray(core)
                struct.pack_into('<12I', expected, 0x2327d0 - BASE,
                                 *(EMPTY_RUNS[0][:6] + [jump(E + 0x1000), 0] + EMPTY_RUNS[0][8:]),
                                 jump(header.gp1_resume_a), 0)
                struct.pack_into('<12I', expected, 0x232d08 - BASE, first, 0, *EMPTY_RUNS[1][2:],
                                 jump(header.gp1_resume_b), 0)
                struct.pack_into('<I', expected, GP1_HOOK - BASE, jal(header.gp1_chain_entry))
                self.assertEqual(bytes(session.memory), bytes(expected))
                self.assertEqual(session.slot_words()[1][0], first)
                # Once: the runs no longer hold the expected bytes.
                self.assertEqual(possible(session.pointer, SIZE, c.byref(header)), 0)
                self.assertEqual(session.install(header, slot4), -errno.EILSEQ)
                self.assertEqual(bytes(session.memory), bytes(expected))
        # The fingerprint entry's call stays when no file takes the slot.
        session = Session(self, self.stand_in_core(header), 7, offered=True, fingerprint_break=True)
        self.assertEqual(session.stage(trojan(hook=0x2327d0)), 0)
        self.assertEqual(session.install(header), 1)
        self.assertEqual(struct.unpack_from('<2I', session.memory, 0x232d08 - BASE), (BREAK_CALL, 0))
        # Any changed byte of either run, or a GP1 word that is not the
        # launcher's jal: not possible, refused, nothing written.
        for address in (0x2327d0, 0x2327f7, 0x2327ff, 0x232d08, 0x232d37, GP1_HOOK):
            with self.subTest(changed=hex(address)):
                core = self.stand_in_core(header)
                core[address - BASE] ^= 1
                session = Session(self, core, offered=True)
                self.assertEqual(possible(session.pointer, SIZE, c.byref(header)), 0)
                self.assertEqual(session.stage(trojan(hook=0x2327d0)), 0)
                self.assertEqual(session.install(header), -errno.EILSEQ)
                self.assertEqual(bytes(session.memory), bytes(core))
        # The bytes next to the runs are not part of the check.
        for address in (0x2327cf, 0x232800, 0x232d07, 0x232d38):
            core = self.stand_in_core(header)
            core[address - BASE] ^= 1
            pointer = (c.c_ubyte * SIZE).from_buffer(core)
            self.assertEqual(possible(pointer, SIZE, c.byref(header)), 1, hex(address))
            del pointer


@unittest.skipUnless(HAVE_ORIGINAL, 'POPSTARTER_TEST_ELF and POPS_TEST_ELF are optional inputs')
class Original(Built):
    # What the loader's own stack, heap and image may change is not compared.
    COMPARED = ((0, 0x870000), (0xb00000, 0x01a00000), (0x01e00000, 0x01f70000))

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('unicorn is not installed')
        import trace_original_pops_trojan as tracer
        cls.tracer = tracer
        cls.loader = tracer.Loader()
        cls.core = tracer.pops_core()

    def assert_memory(self, after, expected):
        for start, end in self.COMPARED:
            self.assertEqual(after[start:end], bytes(expected[start:end]),
                             'memory %#x..%#x' % (start, end))

    def test_verdict_and_every_changed_byte(self):
        for label, arguments, builtin, verdict, _ in CASES:
            with self.subTest(label):
                data = trojan(**arguments)
                returned, events, after = self.loader.run({b'mass:/POPS/TROJAN_0.BIN': data},
                                                          builtin=builtin)
                self.assertEqual(returned, 1)
                self.assertEqual(self.tracer.verdicts(events), [WORDS[verdict]])
                result, info = self.verdict(data, 0, builtin)
                self.assertEqual(result, verdict)
                expected = bytearray(self.loader.before)
                if verdict == APPLY:
                    # The payload first, then the hook words, as the C result says.
                    expected[info.load:info.load + info.size] = data[0x40:]
                    struct.pack_into('<%dI' % info.hook_words, expected, info.hook,
                                     *list(info.hook_word)[:info.hook_words])
                self.assert_memory(after, expected)

    def test_messages(self):
        _, events, _ = self.loader.run({b'mass:/POPS/TROJAN_0.BIN': trojan(be=0),
                                        b'mass:/POPS/TROJAN_1.BIN': trojan(slot=1, hook=0x2327e0),
                                        b'mass:/POPS/TROJAN_2.BIN': trojan(slot=2, fmt=3)},
                                       builtin=7)
        text = [e[1] for e in events if e[0] == 'msg']
        self.assertIn('Invalid', text)
        self.assertIn('Skipped (outdated)', text)
        self.assertEqual(sum(1 for line in text if line.startswith('Hooked')), 1)
        self.assertEqual(text.count('NOT FOUND'), 7)

    def test_an_invalid_file_does_not_stop_the_slots_after_it(self):
        files = {b'mass:/POPS/TROJAN_0.BIN': trojan(be=0),
                 b'mass:/POPS/TROJAN_1.BIN': trojan(slot=1, hook=0x2327e0),
                 b'mass:/POPS/TROJAN_5.BIN': trojan(slot=5, fmt=3, ba=0),
                 b'mass:/POPS/TROJAN_9.BIN': trojan(slot=9, load=0x01510000, hook=0x232d28)}
        returned, events, after = self.loader.run(files, builtin=7)
        self.assertEqual(returned, 1)
        self.assertEqual(self.tracer.verdicts(events), ['INVALID', 'APPLIED', 'OUTDATED', 'APPLIED'])
        self.assertEqual([e[1] for e in events if e[0] == 'open'],
                         [b'mass:/POPS/TROJAN_%d.BIN' % slot for slot in range(10)])
        self.assertEqual(struct.unpack_from('<I', after, 0x2327e0)[0], jal(E))
        self.assertEqual(struct.unpack_from('<I', after, 0x232d28)[0], jal(0x01510000))

    def test_files_under_0x44_bytes_are_invalid_and_the_next_slot_is_read(self):
        good = trojan(slot=1, hook=0x2327e0)
        for data in (b'', b'T', trojan(size=0)[:0x40], trojan(size=0, filesize=0x43)):
            with self.subTest(len(data)):
                returned, events, after = self.loader.run({b'mass:/POPS/TROJAN_0.BIN': data,
                                                           b'mass:/POPS/TROJAN_1.BIN': good})
                self.assertEqual(returned, 1)
                self.assertEqual(self.tracer.verdicts(events), ['INVALID', 'APPLIED'])
                self.assertEqual(len([e for e in events if e[0] == 'open']), 10)
                self.assertEqual(struct.unpack_from('<I', after, 0x2327e0)[0], jal(E))
        returned, events, after = self.loader.run({b'mass:/POPS/TROJAN_0.BIN': trojan(size=4)})
        self.assertEqual(self.tracer.verdicts(events), ['APPLIED'])

    def test_device_failures(self):
        # The modelled device fails one call; what the original then does.
        # Not a console run: the failures are the tracer's (faults=).
        path = lambda slot: b'mass:/POPS/TROJAN_%d.BIN' % slot
        good = {path(0): trojan(slot=0, hook=0x2327d8), path(1): trojan(slot=1, hook=0x2327e0)}
        for code in (-1, -2, -5, -19):
            with self.subTest(open=code):
                # Any failed open: NOT FOUND, and the next slot is read.
                returned, events, after = self.loader.run(good, faults={path(0): {'open': code}})
                self.assertEqual(returned, 1)
                self.assertEqual(self.tracer.verdicts(events), ['APPLIED'])
                self.assertEqual([e[1] for e in events if e[0] == 'msg'].count('NOT FOUND'), 9)
                self.assertEqual(after[0x2327d8:0x2327dc], self.loader.before[0x2327d8:0x2327dc])
                self.assertEqual(struct.unpack_from('<I', after, 0x2327e0)[0], jal(E))
        # A failed size query: Invalid.
        _, events, _ = self.loader.run(good, faults={path(0): {'size': -5}})
        self.assertEqual(self.tracer.verdicts(events), ['INVALID', 'APPLIED'])
        # A failed header read after a file: the cleared header, Invalid.
        _, events, _ = self.loader.run(good, faults={path(1): {'read': [-5]}})
        self.assertEqual(self.tracer.verdicts(events), ['APPLIED', 'INVALID'])
        # A failed payload read: not checked, the file is applied.
        _, events, after = self.loader.run({path(0): good[path(0)]},
                                           faults={path(0): {'read': [None, -5]}})
        self.assertEqual(self.tracer.verdicts(events), ['APPLIED'])
        self.assertEqual(struct.unpack_from('<I', after, 0x2327d8)[0], jal(E))
        # No size limit: a payload of 1 MiB is applied.
        big = trojan(size=0x100000, hook=0x2327d8)
        _, events, after = self.loader.run({path(0): big})
        self.assertEqual(self.tracer.verdicts(events), ['APPLIED'])
        self.assertEqual(after[E:E + 0x100000], big[0x40:])

    def test_title_scope_reads_ten_files_of_another_folder(self):
        # How the caller forms the folder name it passes is not examined here.
        _, events, _ = self.loader.run({}, scope=1, title=b'GAME')
        opened = [e[1] for e in events if e[0] == 'open']
        self.assertEqual(len(opened), 10)
        for slot, path in enumerate(opened):
            self.assertTrue(path.endswith(b'/TROJAN_%d.BIN' % slot), path)
            self.assertNotEqual(path, b'mass:/POPS/TROJAN_%d.BIN' % slot)

    def test_in_core_files_leave_the_same_core(self):
        for label, arguments in IN_CORE:
            with self.subTest(label):
                data = trojan(load=0x2f0000, hook=0x2f0100, **arguments)
                _, events, after = self.loader.run({b'mass:/POPS/TROJAN_0.BIN': data})
                self.assertEqual(self.tracer.verdicts(events), ['APPLIED'])
                result, _, staged = self.staged(self.core, data)
                self.assertEqual(result, 0)
                self.assertEqual(staged, after[BASE:BASE + SIZE])


def stub_file(chain, index, style):
    # A TROJAN file whose payload is tools/pops_trojan_chain.py's stub for
    # slot `index` (chain order), hooked the way that style is: format 1
    # writes `jal entry`, format 2 width 1 writes `j entry`.
    arguments = dict(fmt=1) if style == 'jal' else dict(fmt=2, ba=1)
    return trojan(slot=index, load=chain.STUBS + 0x40 * index, hook=chain.SLOTS[index],
                  payload=chain.stub_bytes(style, index), **arguments)


STYLE_SETS = [('jal',) * 10, ('j',) * 10, ('jra',) * 10,
              ('jal', 'empty', 'j', 'empty', 'jra', 'jra', 'empty', 'j', 'empty', 'jal'),
              ('empty', 'j', 'empty', 'jra', 'empty', 'empty', 'jal', 'empty', 'jra', 'empty'),
              ('empty',) * 4 + ('jra',) + ('empty',) * 4 + ('j',)]


@unittest.skipUnless(HAVE_ORIGINAL, 'POPSTARTER_TEST_ELF and POPS_TEST_ELF are optional inputs')
class OriginalSlots(Built):
    '''POPStarter's ten slots: what its loader leaves in them, and what a
    payload finds there, against launcHER's copy of the slots and (with
    a resident image) its chain. Emulated; not a console.'''

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('unicorn is not installed')
        import pops_trojan_chain as chain
        import trace_original_pops_trojan as tracer
        from trace_original_pops_io import decode_main
        cls.chain, cls.tracer = chain, tracer
        cls.main = decode_main(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())
        cls.core = tracer.pops_core()
        # The loader on a core that already holds POPStarter's two parts,
        # as the launch places them, and the jump between them.
        cls.loader = tracer.Loader()
        baseline = bytearray(cls.loader.baseline)
        for source, target, size in (chain.BLOCK1, chain.BLOCK2):
            baseline[target:target + size] = cls.main[source - 0x870000:source - 0x870000 + size]
        struct.pack_into('<I', baseline, 0x232d30, chain.j(chain.BLOCK2[1]))
        cls.loader.baseline = bytes(baseline)
        cls.image = resident_image() if HAVE_IMAGE else None

    def original_runs(self, after):
        return [list(struct.unpack_from('<10I', after, base)) for base in (0x2327d0, 0x232d08)]

    def header(self):
        header = ResidentHeader()
        image = bytearray(self.image)
        self.assertEqual(self.lib.pops_resident_check_image(
            (c.c_ubyte * len(image)).from_buffer(image), len(image), c.byref(header)), 0)
        return header

    def hooked_core(self, header):
        core = bytearray(self.core)
        pointer = (c.c_ubyte * len(core)).from_buffer(core)
        self.assertEqual(self.lib.pops_resident_hook_gp1(pointer, len(core), header.gp1_entry), 0)
        self.assertEqual(self.lib.pops_resident_slot_chain_possible(pointer, len(core),
                                                                    c.byref(header)), 1)
        del pointer
        return core

    def test_the_shipped_slots_are_ten_empty_pairs(self):
        at = self.chain.BLOCK1[0] - 0x870000
        for base in (0x2327d0, 0x232d08):
            words = struct.unpack_from('<10I', self.main, at + base - 0x232790)
            self.assertEqual(list(words), EMPTY_RUNS[0], hex(base))
        # The real core's bytes there are what the launcher's check expects,
        # and only with the GP1 hook already written.
        header = fake_header()
        core = bytearray(self.core)
        pointer = (c.c_ubyte * len(core)).from_buffer(core)
        possible = self.lib.pops_resident_slot_chain_possible
        self.assertEqual(possible(pointer, len(core), c.byref(header)), 0)
        self.assertEqual(self.lib.pops_resident_hook_gp1(pointer, len(core), header.gp1_entry), 0)
        self.assertEqual(possible(pointer, len(core), c.byref(header)), 1)
        for address in (0x2327d0, 0x2327f7, 0x2327ff, 0x232d08, 0x232d37):
            core[address - BASE] ^= 1
            self.assertEqual(possible(pointer, len(core), c.byref(header)), 0, hex(address))
            core[address - BASE] ^= 1
        self.assertEqual(possible(pointer, len(core), c.byref(header)), 1)

    def test_nothing_in_pops_points_into_the_function_the_runs_lie_in(self):
        # launcHER writes the two runs over part of POPS's function at
        # 0x232790 (POPStarter overwrites all of it). The basis for calling
        # it unused: no j/jal from outside it, no word holding one of its
        # addresses, no lui with addiu/ori that builds one, and no way to
        # fall into it. A static reading of the image; an address made any
        # other way is not seen.
        low, high = 0x232790, 0x232ec8
        words = struct.unpack_from('<%dI' % (len(self.core) // 4), self.core)
        found = []
        for index, word in enumerate(words):
            at = BASE + 4 * index
            if low <= at < high:
                continue
            if word >> 26 in (2, 3):
                target = (at + 4) & 0xf0000000 | (word & 0x03ffffff) << 2
                if low <= target < high:
                    found.append(('jump', hex(at)))
            if low <= word < high:
                found.append(('address word', hex(at)))
            if word >> 26 == 15:
                for following in words[index + 1:index + 4]:
                    if following >> 26 in (9, 13) and (following >> 21 & 31) == (word >> 16 & 31):
                        low16 = following & 0xffff
                        if following >> 26 == 9 and low16 & 0x8000:
                            low16 -= 0x10000
                        if low <= (((word & 0xffff) << 16) + low16) & 0xffffffff < high:
                            found.append(('lui pair', hex(at)))
                        break
        self.assertEqual(found, [])
        # The function before it ends with jr ra, its delay slot and a nop.
        self.assertEqual(words[(low - BASE) // 4 - 3], 0x03e00008)
        self.assertEqual(words[(low - BASE) // 4 - 1], 0)

    FILE_SETS = [
        ('one format 1 file per slot', [dict(slot=n, hook=h, load=E + 0x1000 * n)
                                        for n, h in sorted(model.SLOT_HOOKS.items())]),
        ('format 2 widths on the first run', [dict(slot=0, fmt=2, ba=1, hook=0x2327d0),
                                              dict(slot=1, fmt=2, ba=2, hook=0x2327d8),
                                              dict(slot=2, fmt=2, ba=3, hook=0x2327e0)]),
        ('format 2 width 3 before a format 1 file on the next slot',
         [dict(slot=0, fmt=2, ba=3, hook=0x232d08), dict(slot=1, hook=0x232d10, load=E + 0x1000)]),
        ('format 1 before a width 3 file on the slot before it',
         [dict(slot=0, hook=0x232d10, load=E + 0x1000), dict(slot=1, fmt=2, ba=3, hook=0x232d08)]),
        ('width 2 on the fifth slot of each run', [dict(slot=3, fmt=2, ba=2, hook=0x2327f0),
                                                   dict(slot=9, fmt=2, ba=2, hook=0x232d28,
                                                        load=E + 0x1000)]),
        ('three files on one slot', [dict(slot=0, hook=0x232d08),
                                     dict(slot=5, hook=0x232d08, load=E + 0x1000),
                                     dict(slot=9, fmt=2, ba=1, hook=0x232d08, load=E + 0x2000)]),
        ('an invalid and an outdated file among them', [dict(slot=0, be=0, hook=0x2327d0),
                                                        dict(slot=1, hook=0x2327d8),
                                                        dict(slot=2, fmt=3, ba=0, hook=0x2327e0)]),
        ('format 2 width 0 and width 4', [dict(slot=0, fmt=2, ba=0, hook=0x2327d0),
                                          dict(slot=1, fmt=2, ba=4, hook=0x2327d8)]),
        ('byte 0x0e = 2', [dict(slot=6, be=2, hook=0x232d18)]),
    ]

    def test_slot_words_are_the_loaders(self):
        for label, files in self.FILE_SETS:
            for builtin in (0, 7):
                with self.subTest(label, builtin=builtin):
                    data = {f['slot']: trojan(**f) for f in files}
                    _, events, after = self.loader.run(
                        {b'mass:/POPS/TROJAN_%d.BIN' % n: d for n, d in data.items()},
                        builtin=builtin)
                    session = Session(self, self.core, builtin, offered=True)
                    results = [session.stage(data[n], n) for n in sorted(data)]
                    self.assertEqual([{0: 'APPLIED', SKIP_INVALID: 'INVALID',
                                       SKIP_OUTDATED: 'OUTDATED'}[r] for r in results],
                                     self.tracer.verdicts(events))
                    self.assertEqual(session.slot_words(), self.original_runs(after))
                    self.assertEqual(bytes(session.memory), self.core)
                    # The payloads: held here, copied there, the same bytes.
                    ram = bytes(0x200000)
                    count, ram = session.copy_out(ram, 0x01420000, keep=[(0x0143a000, 0x01460200)])
                    self.assertEqual(count, results.count(0))
                    for address, size, _ in session.records():
                        self.assertEqual(ram[address - 0x01420000:address - 0x01420000 + size],
                                         after[address:address + size])

    def test_root_then_title_scope(self):
        # One loader call per scope; the launcher's loop reads the root
        # folder's ten files, then the title folder's.
        root = {0: trojan(hook=0x2327d0), 4: trojan(slot=4, hook=0x232d08, load=E + 0x1000)}
        title = {2: trojan(slot=2, fmt=2, ba=2, hook=0x232d08, load=E + 0x2000),
                 3: trojan(slot=3, hook=0x232d28, load=E + 0x3000)}
        _, _, after = self.loader.run({b'mass:/POPS/TROJAN_%d.BIN' % n: d for n, d in root.items()})
        runs = self.original_runs(after)
        names = []
        _, events, after = self.loader.run({}, scope=1, title=b'GAME')
        names = [e[1] for e in events if e[0] == 'open']
        _, _, after = self.loader.run({names[n]: d for n, d in title.items()}, scope=1, title=b'GAME')
        for run, words in enumerate(self.original_runs(after)):
            for i, word in enumerate(words):
                if word != EMPTY_RUNS[run][i]:
                    runs[run][i] = word
        session = Session(self, self.core, offered=True)
        for files in (root, title):
            for n in sorted(files):
                self.assertEqual(session.stage(files[n], n), 0)
        self.assertEqual(session.slot_words(), runs)
        self.assertEqual(runs[1][:2], [jump(E + 0x2000), 0])

    @unittest.skipUnless(HAVE_IMAGE, NO_IMAGE)
    def test_installing_the_slots_changes_three_places(self):
        header = self.header()
        for slot4, first in ((SLOT4_AS_FILES, jal(E)), (SLOT4_BREAK_CALL, BREAK_CALL),
                             (SLOT4_RESET_STORE, 0x10000001)):
            with self.subTest(slot4=slot4):
                core = self.hooked_core(header)
                session = Session(self, core, offered=True)
                self.assertEqual(session.stage(trojan(hook=0x232d08)), 0)
                self.assertEqual(session.stage(trojan(slot=1, fmt=2, ba=2, hook=0x2327e8,
                                                      load=E + 0x1000), 1), 0)
                self.assertEqual(bytes(session.memory), bytes(core))
                self.assertEqual(session.install(header, slot4), 1)
                expected = bytearray(core)
                struct.pack_into('<12I', expected, 0x2327d0 - BASE,
                                 *(EMPTY_RUNS[0][:6] + [jump(E + 0x1000), 0] + EMPTY_RUNS[0][8:]),
                                 jump(header.gp1_resume_a), 0)
                struct.pack_into('<12I', expected, 0x232d08 - BASE, first, 0, *EMPTY_RUNS[1][2:],
                                 jump(header.gp1_resume_b), 0)
                struct.pack_into('<I', expected, GP1_HOOK - BASE, jal(header.gp1_chain_entry))
                self.assertEqual(bytes(session.memory), bytes(expected))
                self.assertEqual(session.slot_words()[1][0], first)
                # Once: the runs no longer hold POPS's bytes.
                self.assertEqual(session.install(header, slot4), -errno.EILSEQ)
                self.assertEqual(bytes(session.memory), bytes(expected))
        # The fingerprint entry's call stays when no file takes the slot.
        core = self.hooked_core(header)
        session = Session(self, core, 7, offered=True, fingerprint_break=True)
        self.assertEqual(session.stage(trojan(hook=0x2327d0)), 0)
        self.assertEqual(session.install(header), 1)
        self.assertEqual(struct.unpack_from('<2I', session.memory, 0x232d08 - BASE), (BREAK_CALL, 0))
        # Without the GP1 jal the launcher wrote: refused, nothing written.
        session = Session(self, self.core, offered=True)
        self.assertEqual(session.stage(trojan(hook=0x2327d0)), 0)
        self.assertEqual(session.install(header), -errno.EILSEQ)
        self.assertEqual(bytes(session.memory), self.core)

    @unittest.skipUnless(HAVE_IMAGE, NO_IMAGE)
    def test_the_chain_gives_a_payload_what_the_originals_does(self):
        cases, slots = self.chain.compare(self.image, self.main, self.core)
        self.assertEqual((cases, slots), (71, 350))
        print('Original slot chain PASS: %d cases, %d slot records, 34 registers and the '
              'chain\'s stores at each' % (cases, slots))

    @unittest.skipUnless(HAVE_IMAGE, NO_IMAGE)
    def test_the_disc_swap_frame_is_the_known_difference(self):
        # On the frame POPStarter's block calls POPS's disc init, between
        # the two runs, the original leaves that call's v0, a0 and ra in the
        # registers; launcHER's C code keeps POPS's. Pinned so that a change
        # shows up; nothing else may differ.
        for styles in (('j',) * 10, ('jal',) * 10, ('jra',) * 10):
            at_slots, at_return, stores = self.chain.swap_frame(self.image, self.main, self.core,
                                                                styles)
            self.assertTrue(stores)
            self.assertEqual(at_return, {'v0', 'a0'})
            self.assertEqual(sorted(at_slots), [4, 5, 6, 8, 9])
            for slot, names in at_slots.items():
                self.assertLessEqual(names, {'v0', 'a0', 'ra'}, slot)
                self.assertLessEqual({'v0', 'a0'}, names, slot)

    @unittest.skipUnless(HAVE_IMAGE, NO_IMAGE)
    def test_from_file_bytes_to_what_the_payload_finds(self):
        # The same generated TROJAN files through both: the original's
        # loader and then its chain; launcHER's staging, slot install and
        # payload copy and then the built chain.
        header = self.header()
        records = 0
        for styles in STYLE_SETS:
            files = {index: stub_file(self.chain, index, style)
                     for index, style in enumerate(styles) if style != 'empty'}
            _, events, after = self.loader.run(
                {b'mass:/POPS/TROJAN_%d.BIN' % n: d for n, d in files.items()})
            self.assertEqual(self.tracer.verdicts(events), ['APPLIED'] * len(files))
            session = Session(self, self.hooked_core(header), offered=True)
            for index in sorted(files):
                self.assertEqual(session.stage(files[index], index), 0, (styles, index))
            self.assertEqual(session.install(header), 1 if files else 0)
            if not files:
                continue
            count, arena = session.copy_out(bytes(0x200000), 0x01420000,
                                            keep=[(0x0143a000, 0x01460200)])
            self.assertEqual(count, len(files))
            for pad in (0xffff, 0xf6fe, 0xf9fe, 0xbcfe, 0xecfe):
                with self.subTest(styles=styles, pad=hex(pad)):
                    want = self.chain.original_launched(after[BASE:BASE + SIZE],
                                                        after[0x01420000:0x01620000], pad, styles)
                    got = self.chain.launched(self.image, bytes(session.memory), arena, pad, styles)
                    self.assertEqual([r[0] for r in want[0]],
                                     [i for i, style in enumerate(styles) if style != 'empty'])
                    self.assertEqual(got, want)
                    records += len(want[0])
        print('Original file-to-slot PASS: %d style sets x 5 pad states, %d slot records'
              % (len(STYLE_SETS) - 1, records))


@unittest.skipUnless(HAVE_IMAGE, NO_IMAGE)
class Chain(Built):
    '''The built image's slot chain entry on its own (tools/pops_trojan_chain.py).'''

    def test_the_built_chain(self):
        import pops_trojan_chain as chain
        image = resident_image()
        header = ResidentHeader()
        copy = bytearray(image)
        self.assertEqual(self.lib.pops_resident_check_image(
            (c.c_ubyte * len(copy)).from_buffer(copy), len(copy), c.byref(header)), 0)
        self.assertEqual(chain.header(image)[2:],
                         (header.gp1_chain_entry, header.gp1_resume_a, header.gp1_resume_b))
        cases, slots = chain.self_check(image)
        self.assertEqual((cases, slots), (142, 700))
        # A damaged image is noticed: the two resume entries swapped.
        damaged = bytearray(image)
        struct.pack_into('<2I', damaged, 116, header.gp1_resume_b, header.gp1_resume_a)
        with self.assertRaises(AssertionError):
            chain.self_check(bytes(damaged))


class Source(Built):
    def setUp(self):
        self.lib.test_fix_files.argtypes = [c.c_void_p, c.c_size_t, c.c_char_p, c.c_char_p,
                                            c.c_uint, c.POINTER(TrojanSet), c.c_int]
        self.lib.test_log.restype = c.c_char_p
        self.lib.test_fail_reads(0)
        self.lib.test_fault.argtypes = [c.c_char_p, c.c_int]
        self.lib.test_fault(b'', 0)
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name) / 'POPS'
        self.title = self.root / 'GAME'
        self.title.mkdir(parents=True)
        self.memory = pristine()
        self.pointer = (c.c_ubyte * SIZE).from_buffer(self.memory)
        self.state = TrojanSet()

    def tearDown(self):
        del self.pointer
        self.folder.cleanup()

    def run_files(self, fingerprint=0, offered=0):
        result = self.lib.test_fix_files(self.pointer, SIZE, (str(self.root) + '/').encode(),
                                         (str(self.title) + '/').encode(), fingerprint,
                                         c.byref(self.state), offered)
        return result, self.lib.test_log().decode()

    def test_slot_hooks_are_collected_root_first_then_title(self):
        (self.root / 'TROJAN_0.BIN').write_bytes(trojan(hook=0x2327d0))
        (self.root / 'TROJAN_4.BIN').write_bytes(trojan(slot=4, load=0x01510000, hook=0x232d08))
        (self.root / 'TROJAN_7.BIN').write_bytes(trojan(slot=7, fmt=2, ba=3, load=0x01520000,
                                                        hook=0x2327f0))
        (self.title / 'TROJAN_2.BIN').write_bytes(trojan(slot=2, fmt=2, ba=2, load=0x01530000,
                                                         hook=0x232d08))
        (self.title / 'TROJAN_3.BIN').write_bytes(trojan(slot=3, load=0x01540000, hook=0x232d28))
        result, log = self.run_files(offered=1)
        self.assertEqual(result, 0)
        self.assertEqual(self.memory, pristine())
        self.assertEqual([list(run) for run in self.state.slot_word],
                         [[jal(E)] + EMPTY_RUNS[0][1:],
                          [jump(0x01530000), 0] + EMPTY_RUNS[1][2:8] + [jal(0x01540000), 0]])
        self.assertEqual((self.state.chain, self.state.payload_count), (1, 4))
        self.assertEqual(len(log.splitlines()), 1)
        self.assertIn('TROJAN_7.BIN is valid for POPStarter but NOT loaded by launcHER', log)
        # Not offered: every one of them is skipped with a line, and the launch goes on.
        result, log = self.run_files(offered=0)
        self.assertEqual(result, 0)
        self.assertEqual(len(log.splitlines()), 5)
        self.assertEqual([list(run) for run in self.state.slot_word], EMPTY_RUNS)
        self.assertEqual((self.state.chain, self.state.payload_count), (0, 0))

    def test_slot_chain_text(self):
        source = (ROOT / 'launcher/src/handler_pops.c').read_text()
        gp1 = source.index('res = pops_resident_hook_gp1((void *)stagedCore, plan.core_size, '
                           'residentHdr.gp1_entry);')
        init = source.index('pops_trojan_set_init(&trojanSet, POPS_BUILTIN_ID(fingerprintId),')
        staged = source.index('res = pops_stage_user_files((void *)stagedCore, plan.core_size, '
                              'vcdDir, gameConfigDir,')
        self.assertIn('&romState, &fixContext, &trojanSet);', source[staged:staged + 300])
        warmboot = source.index('res = pops_apply_reset_warmboot(')
        install = source.index('res = pops_resident_hook_slot_chain((void *)stagedCore, '
                               'plan.core_size, &residentHdr,')
        # The helper offers the slots after the user's commands and the emit
        # jumps and before the first fix file, as the launch did before the
        # helper existed.
        helper = source[source.index('static int pops_stage_user_files('):
                        source.index('int launchPOPS(')]
        order = ['res = pops_apply_all_config_patches_rom(',
                 'res = pops_resident_hook_recompiler_emit(',
                 'trojanSet->chain_offered =\n'
                 '        (uint8_t)pops_resident_slot_chain_possible(stagedCore, coreSize, residentHdr);',
                 'res = pops_stage_fix_files(']
        at = [helper.index(text) for text in order]
        self.assertEqual(at, sorted(at))
        self.assertIn('rom, finalContext, trojanSet);', helper)
        self.assertEqual(source.count('chain_offered ='), 1)
        # The GP1 jal the check expects is written first; the set is made
        # before the helper; the slots are installed after the last thing
        # that decides the slot at 0x232d08, and before the resident flags
        # are built and POPStarter's opcode pass runs over the core.
        self.assertLess(gp1, init)
        self.assertLess(init, staged)
        self.assertLess(staged, warmboot)
        self.assertLess(warmboot, install)
        self.assertLess(install, source.index('int residentNeeded = pops_resident_build_config('))
        self.assertLess(install, source.index('pops_apply_opcode_pass((void *)stagedCore'))
        block = source[source.rindex('unsigned slot4 = POPS_SLOT4_AS_FILES;', 0, install):install]
        self.assertLess(block.index('if (resetStore)'), block.index('slot4 = POPS_SLOT4_RESET_STORE;'))
        self.assertIn('(!fingerprintId && builtinId && builtinPlan.break_call)', block)
        after = source[install:install + 900]
        self.assertIn('cfg.builtin_break_call = trojanSet.slot_word[1][0] == POPS_TROJAN_BREAK_CALL;',
                      after)
        self.assertLess(after.index('if (res < 0) {'), after.index('return res;'))
        engine = (ROOT / 'common/src/pops_resident_engine.c').read_text()
        chain = engine[engine.index('.globl pops_resident_gp1_chain'):]
        self.assertLess(chain.index('j 0x002327d0'), chain.index('.globl pops_resident_gp1_resume_a'))
        self.assertLess(chain.index('.globl pops_resident_gp1_resume_a'), chain.index('j 0x00232d08'))
        self.assertLess(chain.index('j 0x00232d08'), chain.index('.globl pops_resident_gp1_resume_b'))

    def test_invalid_and_outdated_files_are_skipped_and_the_rest_is_read(self):
        (self.root / 'TROJAN_0.BIN').write_bytes(trojan(be=0))
        (self.root / 'TROJAN_1.BIN').write_bytes(trojan(slot=1, load=0x2f0000, hook=0x2f0100))
        (self.root / 'TROJAN_2.BIN').write_bytes(trojan(slot=2, fmt=3, ba=5, load=0x2f1000,
                                                        hook=0x2f0104))
        (self.root / 'TROJAN_3.BIN').write_bytes(trojan(slot=3, load=0x2f2002, hook=0x2f0108))
        (self.title / 'TROJAN_9.BIN').write_bytes(trojan(slot=9, load=0x2f3000, hook=0x2f010c))
        expected = pristine()
        expected[0xf0000:0xf0020] = trojan()[0x40:]
        expected[0xf3000:0xf3020] = trojan()[0x40:]
        struct.pack_into('<I', expected, 0xf0100, jal(0x2f0000))
        struct.pack_into('<I', expected, 0xf010c, jal(0x2f3000))
        result, log = self.run_files(fingerprint=7)
        self.assertEqual(result, 0)
        self.assertEqual(self.memory, expected)
        lines = log.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].endswith('TROJAN_0.BIN: Invalid'), lines[0])
        self.assertTrue(lines[1].endswith('TROJAN_2.BIN: Skipped (outdated)'), lines[1])
        self.assertIn('TROJAN_3.BIN is valid for POPStarter but NOT loaded by launcHER: '
                      'an address or the size is not a multiple of 4', lines[2])

    def test_an_empty_or_short_file_is_invalid_and_one_too_large_stops(self):
        # Measured on the original's loader (Original class, the same sizes):
        # 0, 1, 0x40 and 0x43 bytes are "Invalid" and the next slot is read.
        good = trojan(slot=4, load=0x2f0000, hook=0x2f0100)
        for slot, data in enumerate((b'', b'T', trojan(size=0)[:0x40],
                                     trojan(size=0, filesize=0x43))):
            (self.root / ('TROJAN_%d.BIN' % slot)).write_bytes(data)
        (self.root / 'TROJAN_4.BIN').write_bytes(good)
        result, log = self.run_files()
        self.assertEqual(result, 0)
        lines = log.splitlines()
        self.assertEqual(len(lines), 4)
        for slot, line in enumerate(lines):
            self.assertTrue(line.endswith('TROJAN_%d.BIN: Invalid' % slot), line)
        self.assertEqual(struct.unpack_from('<I', self.memory, 0xf0100)[0], jal(0x2f0000))
        # An empty PATCH file is not this rule: PATCH reading is unchanged.
        self.memory[:] = pristine()
        (self.root / 'PATCH_0.BIN').write_bytes(b'')
        result, log = self.run_files()
        self.assertEqual(result, -errno.EINVAL)
        self.assertIn('Fix file rejected', log)
        (self.root / 'PATCH_0.BIN').unlink()

    def test_a_file_larger_than_the_read_buffer_is_skipped_not_fatal(self):
        # The original applies a file of any size (Original class, a payload
        # of 1 MiB). launcHER reads fix files into 1 MiB: a file it would
        # apply is skipped with a line, one it calls Invalid is Invalid, and
        # the slots after it are read.
        (self.root / 'TROJAN_0.BIN').write_bytes(trojan(size=0x100000))
        (self.root / 'TROJAN_1.BIN').write_bytes(trojan(slot=1, size=0x100000, be=0))
        (self.root / 'TROJAN_2.BIN').write_bytes(trojan(slot=2, load=0x2f0000, hook=0x2f0100))
        result, log = self.run_files()
        self.assertEqual(result, 0)
        lines = log.splitlines()
        self.assertEqual(len(lines), 2, lines)
        self.assertIn("TROJAN_0.BIN is valid for POPStarter but NOT loaded by launcHER: the file is "
                      "larger than launcHER's 1 MiB fix file buffer", lines[0])
        self.assertTrue(lines[1].endswith('TROJAN_1.BIN: Invalid'), lines[1])
        expected = pristine()
        expected[0xf0000:0xf0020] = trojan()[0x40:]
        struct.pack_into('<I', expected, 0xf0100, jal(0x2f0000))
        self.assertEqual(self.memory, expected)
        self.assertEqual(self.state.payload_count, 0)
        # Exactly the buffer's size is read and staged.
        self.memory[:] = pristine()
        (self.root / 'TROJAN_0.BIN').write_bytes(trojan(load=0x2f1000, hook=0x2f0104,
                                                       size=0x100000 - 0x40))
        (self.root / 'TROJAN_1.BIN').unlink()
        result, log = self.run_files()
        self.assertEqual((result, log), (0, ''))
        self.assertEqual(struct.unpack_from('<I', self.memory, 0xf0104)[0], jal(0x2f1000))

    def test_the_outdated_rule_needs_a_fingerprint_entry(self):
        (self.root / 'TROJAN_2.BIN').write_bytes(trojan(slot=2, fmt=3, ba=5, load=0x2f1000,
                                                        hook=0x2f0104))
        result, log = self.run_files(fingerprint=0)
        self.assertEqual((result, log), (0, ''))
        self.assertEqual(struct.unpack_from('<I', self.memory, 0xf0104)[0], jal(0x2f1000))

    def test_a_header_that_cannot_be_read_is_invalid(self):
        # The original does not check its header read: what did not arrive
        # is its cleared header, which is Invalid (Original class).
        (self.root / 'TROJAN_0.BIN').write_bytes(trojan(load=0x2f0000, hook=0x2f0100))
        (self.root / 'TROJAN_1.BIN').write_bytes(trojan(slot=1, load=0x2f1000, hook=0x2f0104))
        self.lib.test_fail_reads(1)
        result, log = self.run_files()
        self.assertEqual(result, 0)
        lines = log.splitlines()
        self.assertEqual(len(lines), 2, lines)
        for slot, line in enumerate(lines):
            self.assertTrue(line.endswith('TROJAN_%d.BIN: Invalid' % slot), line)
        self.assertEqual(self.memory, pristine())

    def test_a_payload_read_error_still_stops_the_launch(self):
        # The original copies whatever its buffer holds (Original class);
        # launcHER does not stage a payload it could not read.
        (self.root / 'TROJAN_0.BIN').write_bytes(trojan(load=0x2f0000, hook=0x2f0100))
        self.lib.test_fail_reads(2)
        result, log = self.run_files()
        self.assertEqual(result, -errno.EIO)
        self.assertIn('Fix file rejected', log)
        self.assertEqual(self.memory, pristine())

    def test_a_file_that_cannot_be_opened_is_not_found(self):
        # Any failed open is "NOT FOUND" in the original and the next slot is
        # read (Original class); before this it stopped the launch here.
        (self.root / 'TROJAN_0.BIN').write_bytes(trojan(load=0x2f0000, hook=0x2f0100))
        (self.root / 'TROJAN_1.BIN').write_bytes(trojan(slot=1, load=0x2f1000, hook=0x2f0104))
        self.lib.test_fault(b'POPS/TROJAN_0.BIN', 1)
        result, log = self.run_files()
        self.assertEqual((result, log), (0, ''))
        expected = pristine()
        expected[0xf1000:0xf1020] = trojan()[0x40:]
        struct.pack_into('<I', expected, 0xf0104, jal(0x2f1000))
        self.assertEqual(self.memory, expected)

    def test_a_file_whose_size_cannot_be_read_is_invalid(self):
        (self.root / 'TROJAN_0.BIN').write_bytes(trojan(load=0x2f0000, hook=0x2f0100))
        (self.root / 'TROJAN_1.BIN').write_bytes(trojan(slot=1, load=0x2f1000, hook=0x2f0104))
        self.lib.test_fault(b'POPS/TROJAN_0.BIN', 2)
        result, log = self.run_files()
        self.assertEqual(result, 0)
        self.assertEqual(len(log.splitlines()), 1)
        self.assertTrue(log.splitlines()[0].endswith('TROJAN_0.BIN: Invalid'), log)
        self.assertEqual(struct.unpack_from('<I', self.memory, 0xf0104)[0], jal(0x2f1000))

    def test_a_patch_read_error_still_stops_the_launch(self):
        (self.root / 'PATCH_1.BIN').write_bytes(bytes(0x40))
        self.lib.test_fault(b'POPS/PATCH_1.BIN', 1)
        result, log = self.run_files()
        self.assertEqual(result, -errno.EIO)
        self.assertIn('Fix file rejected', log)

    def test_payloads_above_the_image_are_recorded_in_file_order(self):
        first = trojan(slot=2, load=0x01500000, hook=0x2f0100)
        second = trojan(slot=0, load=0x01431000, hook=0x2f0104, size=0x40)
        refused = trojan(slot=1, load=0x01500000, hook=0x2f0108,
                         payload=code(0x08000000 | 0x2394f0 >> 2, 0))
        (self.root / 'TROJAN_2.BIN').write_bytes(first)
        (self.root / 'TROJAN_1.BIN').write_bytes(refused)
        (self.title / 'TROJAN_0.BIN').write_bytes(second)
        result, log = self.run_files()
        self.assertEqual(result, 0)
        self.assertEqual([(p.address, p.size, p.hold) for p in
                          self.state.payload[:self.state.payload_count]],
                         [(0x01500000, 0x20, 0), (0x01431000, 0x40, 0x20)])
        self.lib.test_hold.restype = c.POINTER(c.c_ubyte * 0x60)
        self.assertEqual(bytes(self.lib.test_hold().contents), first[0x40:] + second[0x40:])
        expected = pristine()
        struct.pack_into('<2I', expected, 0xf0100, jal(0x01500000), jal(0x01431000))
        self.assertEqual(self.memory, expected)
        self.assertEqual(len(log.splitlines()), 1)
        self.assertIn('TROJAN_1.BIN is valid for POPStarter but NOT loaded by launcHER: it uses '
                      'POPStarter\'s 480p handler', log)

    def test_handoff_text(self):
        source = (ROOT / 'launcher/src/handler_pops.c').read_text()
        number = {name: int(value, 16) for name, value in re.findall(
            r'#define (POPS_TROJAN_\w+)\s+\(?(?:\(\w+ \*\))?(0x[0-9a-f]+)u?\)?', source)}
        # The holding memory is the dead raw-ELF input, then the scan's work
        # memory, then the buffer fix files are read into.
        self.assertEqual(number['POPS_TROJAN_HOLD_BUF'], 0x01800000)
        self.assertIn('#define POPS_LOAD_RAW_BUF   ((void *)0x01800000)', source)
        self.assertEqual(number['POPS_TROJAN_HOLD_BUF'] + number['POPS_TROJAN_HOLD_SIZE'],
                         number['POPS_TROJAN_WORK_BUF'])
        self.assertEqual(number['POPS_TROJAN_WORK_BUF'] + number['POPS_TROJAN_WORK_SIZE'], 0x01f00000)
        self.assertIn('void *buffer = (void *)0x01f00000;', source)
        self.assertGreaterEqual(number['POPS_TROJAN_WORK_SIZE'], (0x100000 // 4 + 7) // 8 * 2)
        # Nothing reads the raw input after the fix files are staged (the
        # helper that stages them sits above launchPOPS and does not name it).
        staged = source.index('res = pops_stage_user_files(')
        helper = source[source.index('static int pops_stage_user_files('):
                        source.index('int launchPOPS(')]
        self.assertNotIn('POPS_LOAD_RAW_BUF', helper)
        self.assertNotIn('POPS_LOAD_RAW_BUF', source[staged:])
        self.assertLess(source.rindex('POPS_LOAD_RAW_BUF'), staged)
        # Copied after the built-in code and $BREAKPOINT, before the resident
        # image and the trampoline, with the staged core among what is kept.
        # The memory handed over is the arena, by its address: the function
        # refuses a null pointer, which is what all of RAM from address 0 is
        # on the console (Native.test_copy_out_refuses_a_null_pointer).
        self.assertNotIn('pops_trojan_copy_out(&trojanSet, (uint8_t *)0', source)
        copy = source.index('res = pops_trojan_copy_out(&trojanSet, '
                            '(uint8_t *)(uintptr_t)POPS_TROJAN_ARENA_BASE,')
        self.assertIn('POPS_TROJAN_ARENA_BASE, POPS_TROJAN_ARENA_LIMIT, keep,',
                      source[copy:copy + 200])
        self.assertLess(source.index('res = pops_breakpoint_build(cfg.breakpoint'), copy)
        self.assertLess(copy, source.index('res = pops_resident_install((void *)POPS_RESIDENT_BASE'))
        self.assertLess(copy, source.index('memcpy((void *)POPS_TRAMPOLINE_ADDR'))
        block = source[source.rindex('if (trojanSet.payload_count) {', 0, copy):copy]
        for kept in ('{(uint32_t)(uintptr_t)stagedCore, (uint32_t)(uintptr_t)stagedCore + plan.core_size}',
                     '{POPS_BUILTIN_FIX_ADDR, POPS_BUILTIN_FIX_LIMIT}',
                     '{POPS_RESIDENT_BASE, POPS_BUILTIN_BREAK_LIMIT}',
                     '{(uint32_t)(uintptr_t)POPS_TROJAN_HOLD_BUF, 0x02000000u}',
                     '{0, 0x00200000u}'):
            self.assertIn(kept, block)
        failed = source[copy:copy + 400]
        self.assertLess(failed.index('if (res < 0) {'), failed.index('return -EFAULT;'))

    def test_the_loop_text(self):
        text = handler_fragment()
        self.assertIn('pops_fix_stage_trojan(&context, trojanSet, stagedCore, coreSize,', text)
        # The skip results are TROJAN results: POPS_MODE6_SKIPPED, a PATCH
        # result, has the value of POPS_FIX_SKIP_INVALID.
        for needle in ('if (!kind && result == POPS_FIX_SKIP_INVALID) {',
                       'if (!kind && result == POPS_FIX_SKIP_OUTDATED) {',
                       'if (!kind && result == POPS_FIX_SKIP_UNHOSTED) {'):
            block = text[text.index(needle):]
            self.assertLess(block.index('continue;'), block.index('}'), needle)
        self.assertNotIn('if (result == POPS_FIX_SKIP_', text)

    def test_a_patch_whose_mode_6_is_skipped_is_not_called_invalid(self):
        # A user BIOS.BIN in the folder: a PATCH file's mode 6 is not applied
        # and pops_fix_stage_rom returns POPS_MODE6_SKIPPED (1), the value of
        # POPS_FIX_SKIP_INVALID. The file is still applied, not "Invalid", and
        # a TROJAN file after the BIOS.BIN is still read.
        (self.root / 'BIOS.BIN').write_bytes(bytes(0x7ff90))
        header = bytearray(0x40)
        header[:8] = b'PATCH_1\0'
        struct.pack_into('<6I', header, 8, 1, 0x10001, 0, 0, 0, 0)
        header[32:37] = b'owned'
        header[56] = 6
        (self.root / 'PATCH_1.BIN').write_bytes(bytes(header))
        (self.root / 'TROJAN_0.BIN').write_bytes(trojan(load=0x2f0000, hook=0x2f0100))
        result, log = self.run_files()
        self.assertEqual((result, log), (0, ''))
        self.assertEqual(struct.unpack_from('<I', self.memory, 0xf0100)[0], jal(0x2f0000))


if __name__ == '__main__':
    unittest.main()
