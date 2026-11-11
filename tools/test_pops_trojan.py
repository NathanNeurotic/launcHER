#!/usr/bin/env python3
"""TROJAN_n.BIN handling against POPStarter r13's loader, on synthetic files.

Native: the pure C logic (common/src), built for the host.
Original: the same files through the original's loader FUN_00880a24 under
  Unicorn (tools/trace_original_pops_trojan.py). Needs POPSTARTER_TEST_ELF,
  POPS_TEST_ELF and unicorn; skipped otherwise.
Source: the launcher's own loop (launcher/src/handler_pops.c), compiled for
  the host with its file reads.

Every file here is generated. Nothing is a console run.
"""
import ctypes as c
import errno
import os
from pathlib import Path
import random
import re
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
APPLY, INVALID, OUTDATED = 0, 1, 2
SKIP_INVALID, SKIP_OUTDATED, SKIP_UNHOSTED = 1, 2, 3
(NO_UNALIGNED, NO_ENTRY, NO_RANGE, NO_HOOK, NO_SPACE, NO_SLOT, NO_480P, NO_BLOCK2, NO_BUILTIN,
 NO_OWNED, NO_BLOCK1, NO_MAIN) = range(1, 13)
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
          'pops_builtin_db_data.c', 'pops_external.c']


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
                ('payload', Payload * 20)]


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
    lib.pops_trojan_reason_text.restype = c.c_char_p
    lib.pops_trojan_reason_text.argtypes = [c.c_uint]
    lib.pops_trojan_scan.argtypes = [c.c_void_p, c.c_uint32, c.c_uint32, c.c_uint32, c.c_void_p,
                                     c.c_size_t, c.POINTER(c.c_uint32)]
    lib.pops_trojan_in_arena.argtypes = [c.c_uint32, c.c_uint32]
    lib.pops_trojan_copy_out.argtypes = [c.POINTER(TrojanSet), c.c_void_p, c.c_uint32, c.c_uint32,
                                         c.POINTER(Keep), c.c_uint]
    return lib


class Session:
    """A staged core, its fix-file context and one launch's TROJAN set."""

    def __init__(self, test, core, builtin=0, hold=0x40000, work=0x10000):
        self.test, self.lib = test, test.lib
        self.memory = bytearray(core)
        self.pointer = (c.c_ubyte * len(self.memory)).from_buffer(self.memory)
        self.hold = (c.c_ubyte * hold)() if hold else None
        self.work = (c.c_ubyte * work)() if work else None
        self.context = Context()
        self.state = TrojanSet(fingerprint_id=builtin, hold_size=hold, work_size=work,
                               hold=c.cast(self.hold, c.c_void_p) if hold else None,
                               work=c.cast(self.work, c.c_void_p) if work else None)
        test.assertEqual(self.lib.pops_fix_context_init(c.byref(self.context), self.pointer,
                                                        len(self.memory), 0), 0)

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
static int fail_reads;
static ssize_t test_read(int fd, void *buffer, size_t size) {
  if (fail_reads) { errno = EIO; return -1; }
  return read(fd, buffer, size);
}
#define read test_read
%s
int test_fix_files(void *core, size_t size, const char *root, const char *title,
                   unsigned fingerprint, PopsTrojanSet *set) {
  PopsFixContext state;
  memset(set, 0, sizeof(*set));
  set->fingerprint_id = (uint16_t)fingerprint;
  set->hold = host_hold;
  set->hold_size = sizeof(host_hold);
  set->work = host_work;
  set->work_size = sizeof(host_work);
  log_used = 0;
  log_text[0] = 0;
  return pops_stage_fix_files(core, size, root, title, 0, 0, 0, 0, 0, &state, set);
}
const char *test_log(void) { return log_text; }
const unsigned char *test_hold(void) { return host_hold; }
int test_dependency(const char *path, void *buffer, size_t size, size_t *read_size) {
  return readPopsDependency(path, buffer, size, read_size);
}
void test_fail_reads(int fail) { fail_reads = fail; }
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


class Source(Built):
    def setUp(self):
        self.lib.test_fix_files.argtypes = [c.c_void_p, c.c_size_t, c.c_char_p, c.c_char_p,
                                            c.c_uint, c.POINTER(TrojanSet)]
        self.lib.test_log.restype = c.c_char_p
        self.lib.test_fail_reads(0)
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

    def run_files(self, fingerprint=0):
        result = self.lib.test_fix_files(self.pointer, SIZE, (str(self.root) + '/').encode(),
                                         (str(self.title) + '/').encode(), fingerprint,
                                         c.byref(self.state))
        return result, self.lib.test_log().decode()

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

    def test_the_outdated_rule_needs_a_fingerprint_entry(self):
        (self.root / 'TROJAN_2.BIN').write_bytes(trojan(slot=2, fmt=3, ba=5, load=0x2f1000,
                                                        hook=0x2f0104))
        result, log = self.run_files(fingerprint=0)
        self.assertEqual((result, log), (0, ''))
        self.assertEqual(struct.unpack_from('<I', self.memory, 0xf0104)[0], jal(0x2f1000))

    def test_a_read_error_still_stops_the_launch(self):
        (self.root / 'TROJAN_0.BIN').write_bytes(trojan(be=0))
        (self.root / 'TROJAN_1.BIN').write_bytes(trojan(slot=1, load=0x2f0000, hook=0x2f0100))
        self.lib.test_fail_reads(1)
        result, log = self.run_files()
        self.assertEqual(result, -errno.EIO)
        self.assertIn('Fix file rejected', log)
        self.assertEqual(self.memory, pristine())

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
        # Nothing reads the raw input after the fix files are staged.
        staged = source.index('res = pops_stage_fix_files(')
        self.assertNotIn('POPS_LOAD_RAW_BUF', source[staged:])
        self.assertLess(source.rindex('POPS_LOAD_RAW_BUF'), staged)
        # Copied after the built-in code and $BREAKPOINT, before the resident
        # image and the trampoline, with the staged core among what is kept.
        copy = source.index('res = pops_trojan_copy_out(&trojanSet, (uint8_t *)0, 0, 0x02000000u, keep,')
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
        for needle in ('if (result == POPS_FIX_SKIP_INVALID) {', 'if (result == POPS_FIX_SKIP_OUTDATED) {',
                       'if (result == POPS_FIX_SKIP_UNHOSTED) {'):
            block = text[text.index(needle):]
            self.assertLess(block.index('continue;'), block.index('}'), needle)


if __name__ == '__main__':
    unittest.main()
