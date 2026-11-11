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
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from test_pops_fix_files import BASE, SIZE, Context, pristine  # noqa: E402

HAVE_ORIGINAL = bool(os.environ.get('POPSTARTER_TEST_ELF') and os.environ.get('POPS_TEST_ELF'))
APPLY, INVALID, OUTDATED = 0, 1, 2
SKIP_INVALID, SKIP_OUTDATED, SKIP_UNHOSTED = 1, 2, 3
NO_UNALIGNED, NO_ENTRY, NO_RANGE, NO_HOOK = 1, 2, 3, 4
WORDS = {APPLY: 'APPLIED', INVALID: 'INVALID', OUTDATED: 'OUTDATED'}
COMMON = ['pops_modes_patches.c', 'pops_resident_engine.c', 'pops_builtin_db.c',
          'pops_builtin_db_data.c', 'pops_external.c']


class Info(c.Structure):
    _fields_ = [('slot', c.c_uint8), ('format', c.c_uint8), ('width', c.c_uint8),
                ('hook_words', c.c_uint8), ('load', c.c_uint32), ('entry', c.c_uint32),
                ('hook', c.c_uint32), ('size', c.c_uint32), ('hook_word', c.c_uint32 * 3)]


class TrojanSet(c.Structure):
    _fields_ = [('fingerprint_id', c.c_uint16), ('reason', c.c_uint8)]


def trojan(slot=0, fmt=1, ba=0, be=1, load=0x01500000, entry=None, hook=0x2327d8, size=0x20,
           name=b'probe', patch=None, filesize=None):
    """A TROJAN_n.BIN whose payload is `jr ra; nop` repeated."""
    payload = (struct.pack('<2I', 0x03e00008, 0) * ((size + 7) // 8))[:size]
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
    return lib


def release(lib):
    if os.name == 'nt' and getattr(lib, '_handle', None):
        c.windll.kernel32.FreeLibrary.argtypes = [c.c_void_p]
        c.windll.kernel32.FreeLibrary(lib._handle)


class Built(unittest.TestCase):
    EXTRA = ''

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.lib = build(cls.temp.name, cls.EXTRA)

    @classmethod
    def tearDownClass(cls):
        release(cls.lib)
        cls.temp.cleanup()

    def verdict(self, data, slot=0, builtin=0):
        info = Info()
        result = self.lib.pops_trojan_verdict(data, len(data), slot, builtin, c.byref(info))
        return result, info

    def staged(self, core, data, slot=0, builtin=0):
        """-> (result, reason, core after)."""
        memory = bytearray(core)
        pointer = (c.c_ubyte * len(memory)).from_buffer(memory)
        context, state = Context(), TrojanSet(builtin, 0)
        self.assertEqual(self.lib.pops_fix_context_init(c.byref(context), pointer, len(memory), 0), 0)
        result = self.lib.pops_fix_stage_trojan(c.byref(context), c.byref(state), pointer,
                                                len(memory), data, len(data), slot)
        del pointer
        return result, state.reason, bytes(memory)


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
                 NO_RANGE)]:
            with self.subTest(label):
                data = trojan(**arguments)
                self.assertEqual(self.verdict(data)[0], APPLY)
                result, got, after = self.staged(core, data)
                self.assertEqual((result, got), (SKIP_UNHOSTED, reason))
                self.assertEqual(after, core)
                self.assertNotIn(b'unknown', self.lib.pops_trojan_reason_text(reason))

    def test_a_changed_tracked_site_is_an_error_not_a_skip(self):
        memory = pristine()
        pointer = (c.c_ubyte * SIZE).from_buffer(memory)
        context = Context()
        self.assertEqual(self.lib.pops_fix_context_init(c.byref(context), pointer, SIZE, 0), 0)
        memory[0x210318 - BASE] ^= 1
        before = bytes(memory)
        data = trojan(load=0x2f0000, hook=0x2f0100)
        self.assertLess(self.lib.pops_fix_stage_trojan(c.byref(context), None, pointer, SIZE,
                                                       data, len(data), 0), 0)
        self.assertEqual(bytes(memory), before)
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
  log_used = 0;
  log_text[0] = 0;
  return pops_stage_fix_files(core, size, root, title, 0, 0, 0, 0, 0, &state, set);
}
const char *test_log(void) { return log_text; }
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


class Source(Built):
    EXTRA = SOURCE_WRAPPER % handler_fragment()

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

    def test_the_loop_text(self):
        text = handler_fragment()
        self.assertIn('pops_fix_stage_trojan(&context, trojanSet, stagedCore, coreSize,', text)
        for needle in ('if (result == POPS_FIX_SKIP_INVALID) {', 'if (result == POPS_FIX_SKIP_OUTDATED) {',
                       'if (result == POPS_FIX_SKIP_UNHOSTED) {'):
            block = text[text.index(needle):]
            self.assertLess(block.index('continue;'), block.index('}'), needle)


if __name__ == '__main__':
    unittest.main()
