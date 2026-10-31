#!/usr/bin/env python3
"""Production fix-file staging and discovery, using only synthetic containers."""
import ctypes as c
import errno
import hashlib
import itertools
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SIZE = 0x302e60
BASE = 0x200000
WRITES = json.loads((ROOT / 'tools/fixtures/pops_compat_reference.json').read_text())['writes']


class Context(c.Structure):
    _fields_ = [('expected', c.c_uint32 * 39),
                ('video_auto_disabled', c.c_uint8),
                ('video_custom_set', c.c_uint8)]


def pristine():
    data = bytearray(SIZE)
    for address, value, width in [(0x210318, 0x8f828228, 4), (0x21032c, 0x1443fffa, 4),
                                  (0x20083c, 0x0441000a, 4), (0x20085c, 0x1000fffa, 4),
                                  (0x20de9c, 0x0c0836ee, 4), (0x21af70, 0x64, 1),
                                  (0x2525b0, 0x1bfc, 2)]:
        data[address-BASE:address-BASE+width] = value.to_bytes(width, 'little')
    return data


def apply_modes(data, modes):
    for mode in modes:
        for address, value, width in WRITES.get(str(mode), []):
            data[address-BASE:address-BASE+width] = value.to_bytes(width, 'little')


def patch(slot=1, modes=(), payload=b'', address=0, control=None):
    if control is None:
        control = 1 if modes else 0
    header = bytearray(64)
    header[:8] = f'PATCH_{slot}\0'.encode()
    struct.pack_into('<6I', header, 8, control, 0x10001, address, 0, 0, len(payload))
    header[32:37] = b'owned'
    header[56:56+len(modes)] = bytes(modes)
    return bytes(header) + payload


def trojan(slot=0, payload=b'ABCD', address=0x220000, hook=0x220100):
    header = bytearray(64)
    header[:8] = f'TROJAN_{slot}'.encode()
    struct.pack_into('<6I', header, 8, 0, 0x10001, address, address, hook, len(payload))
    return bytes(header) + payload


class FixFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        directory = Path(cls.temp.name)
        source = (ROOT / 'launcher/src/handler_pops.c').read_text()
        start = source.index('static int readFullFile(')
        end = source.index('/* Driver names within one role', start)
        # Only the EE scratch address changes. Discovery, file reads, failure
        # propagation and per-file staging execute the actual launcher code.
        functions = source[start:end].replace('(void *)0x01f00000', 'host_fix_buffer')
        wrapper = directory / 'loader.c'
        wrapper.write_text('''
#include "pops_modes_patches.h"
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#define PATH_MAX 1024
#define DPRINTF(...) ((void)0)
#define msg(...) ((void)0)
static char host_fix_buffer[0x100000];
static int fail_reads, fail_closes;
static ssize_t test_read(int fd, void *buffer, size_t size) {
  if (fail_reads) { errno=EIO; return -1; }
  return read(fd, buffer, size > 7 ? 7 : size);
}
static int test_close(int fd) {
  int result=close(fd);
  if (fail_closes) { errno=EIO; return -1; }
  return result;
}
#define read test_read
#define close test_close
''' + functions + '''
int test_directory(void *core, size_t size, const char *root, const char *title) {
  int auto_disabled = -1;
  int result = pops_stage_fix_files(core, size, root, title, 0, &auto_disabled);
  return !result && auto_disabled != 0 && auto_disabled != 1 ? -1000 : result;
}
int test_dependency(const char *path, void *buffer, size_t size, size_t *read_size) {
  return readPopsDependency(path, buffer, size, read_size);
}
void test_io_failures(int reads, int closes) { fail_reads=reads; fail_closes=closes; }
''')
        library = directory / ('fixes.dll' if os.name == 'nt' else 'fixes.so')
        subprocess.run(['gcc', '-shared', '-fPIC', '-std=c99', '-Wall', '-Wextra', '-Werror',
                        '-I', str(ROOT / 'common/include'), str(wrapper),
                        str(ROOT / 'common/src/pops_modes_patches.c'),
                        str(ROOT / 'common/src/pops_external.c'), '-o', str(library)], check=True)
        cls.lib = c.CDLL(str(library))
        cls.lib.pops_fix_context_init.argtypes = [c.POINTER(Context), c.c_void_p, c.c_size_t, c.c_uint8]
        cls.lib.pops_fix_stage.argtypes = [c.POINTER(Context), c.c_void_p, c.c_size_t,
                                          c.c_void_p, c.c_size_t, c.c_uint, c.c_int]
        cls.lib.test_directory.argtypes = [c.c_void_p, c.c_size_t, c.c_char_p, c.c_char_p]
        cls.lib.test_io_failures.argtypes = [c.c_int, c.c_int]

    @classmethod
    def tearDownClass(cls):
        if os.name == 'nt' and hasattr(cls, 'lib') and getattr(cls.lib, '_handle', None):
            c.windll.kernel32.FreeLibrary.argtypes = [c.c_void_p]
            c.windll.kernel32.FreeLibrary(cls.lib._handle)
        cls.temp.cleanup()

    def setUp(self):
        self.memory = pristine()
        self.pointer = (c.c_ubyte * SIZE).from_buffer(self.memory)
        self.context = Context()
        self.assertEqual(self.lib.pops_fix_context_init(c.byref(self.context), self.pointer, SIZE, 0), 0)
        self.lib.test_io_failures(0, 0)

    def stage(self, blob, slot=1, is_trojan=0):
        return self.lib.pops_fix_stage(c.byref(self.context), self.pointer, SIZE,
                                       blob, len(blob), slot, is_trojan)

    def assert_rejected_without_writes(self, blob, slot=1, is_trojan=0):
        before = bytes(self.memory), bytes(self.context)
        self.assertLess(self.stage(blob, slot, is_trojan), 0)
        self.assertEqual((bytes(self.memory), bytes(self.context)), before)

    def test_ordered_modes_and_repeated_files(self):
        # Independent original-dispatch table; compare the entire staged core.
        for sequence in itertools.product((1, 2, 3, 4, 5, 7), repeat=2):
            with self.subTest(sequence=sequence):
                self.setUp()
                expected = pristine()
                for modes in (sequence, tuple(reversed(sequence)), sequence):
                    self.assertEqual(self.stage(patch(modes=modes)), 0)
                    apply_modes(expected, modes)
                    self.assertEqual(self.memory, expected)

    def test_four_mode_bytes_keep_order_and_duplicates(self):
        expected = pristine()
        modes = (2, 1, 3, 1)
        self.assertEqual(self.stage(patch(modes=modes)), 0)
        apply_modes(expected, modes)
        self.assertEqual(self.memory, expected)

    def test_initial_config_mask_and_guard_failures(self):
        for mask in (1, 2, 7, 0x5f):
            data = pristine()
            apply_modes(data, [i+1 for i in range(8) if mask & (1 << i)])
            pointer = (c.c_ubyte * SIZE).from_buffer(data)
            ctx = Context()
            self.assertEqual(self.lib.pops_fix_context_init(c.byref(ctx), pointer, SIZE, mask), 0)
        self.memory[0x210318-BASE] ^= 1
        self.assert_rejected_without_writes(patch(modes=(1,)))
        before = bytes(self.context)
        self.assertLess(self.lib.pops_fix_context_init(c.byref(self.context), self.pointer, SIZE, 0), 0)
        self.assertEqual(bytes(self.context), before)

    def test_payload_precedes_modes_and_updates_next_guards(self):
        payload = b'\xaa\xbb\xcc\xdd'
        self.assertEqual(self.stage(patch(payload=payload, address=0x210318)), 0)
        self.assertEqual(self.memory[0x10318:0x1031c], payload)
        self.assertEqual(self.stage(patch(modes=(2, 1))), 0)
        self.assertEqual(struct.unpack_from('<I', self.memory, 0x10318)[0], 0x24030082)
        self.assertEqual(self.stage(patch(modes=(3,), payload=payload, address=0x210318)), 0)
        self.assertEqual(struct.unpack_from('<I', self.memory, 0x10318)[0], 0x240300c1)

    def test_trojan_then_patch_can_override_explicit_bytes(self):
        self.assertEqual(self.stage(trojan(), 0, 1), 0)
        self.assertEqual(self.memory[0x20000:0x20004], b'ABCD')
        self.assertEqual(self.stage(patch(payload=b'WXYZ', address=0x220000)), 0)
        self.assertEqual(self.memory[0x20000:0x20004], b'WXYZ')
        self.assertEqual(struct.unpack_from('<I', self.memory, 0x20100)[0], 0x0c088000)

    def test_invalid_and_unsupported_files_are_atomic(self):
        for blob, slot, kind in [(patch(modes=(8,)), 1, 0),
                                  (patch(modes=(255,)), 1, 0),
                                  (patch(control=8), 1, 0),
                                  (patch(modes=(1,)), 2, 0),
                                  (patch(modes=(1,)), 1, 1), (trojan(), 0, 0),
                                  (patch(payload=b'DATA', address=0x800000), 1, 0),
                                  (patch(payload=b'DATA', address=0x220000)[:-1], 1, 0)]:
            self.assert_rejected_without_writes(blob, slot, kind)

    def test_slot_zero_supported_and_aliasing_rejected(self):
        self.assertEqual(self.stage(patch(slot=0, modes=(4,)), 0), 0)
        blob = patch(modes=(1,))
        self.memory[0x20000:0x20000+len(blob)] = blob
        before = bytes(self.memory), bytes(self.context)
        self.assertLess(self.lib.pops_fix_stage(c.byref(self.context), self.pointer, SIZE,
                        c.byref(self.pointer, 0x20000), len(blob), 1, 0), 0)
        self.assertEqual((bytes(self.memory), bytes(self.context)), before)

    def test_production_directory_order_and_slot_priority(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            title = root / 'title'
            title.mkdir()
            (root / 'TROJAN_0.BIN').write_bytes(trojan())
            (root / 'PATCH_0.BIN').write_bytes(patch(slot=0, payload=b'root', address=0x220000, modes=(2,)))
            (root / 'PATCH_9.BIN').write_bytes(patch(slot=9, modes=(3,)))
            (title / 'TROJAN_0.BIN').write_bytes(trojan(payload=b'titl'))
            (title / 'PATCH_1.BIN').write_bytes(patch(payload=b'last', address=0x220000, modes=(1,)))
            self.assertEqual(self.lib.test_directory(self.pointer, SIZE,
                             os.fsencode(str(root)+'/'), os.fsencode(str(title)+'/')), 0)
            self.assertEqual(self.memory[0x20000:0x20004], b'last')
            expected = pristine()
            apply_modes(expected, (2, 3, 1))
            expected[0x20000:0x20004] = b'last'
            struct.pack_into('<I', expected, 0x20100, 0x0c088000)
            self.assertEqual(self.memory, expected)

    def test_production_missing_files_and_io_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = os.fsencode(str(root)+'/'), os.fsencode(str(root / 'missing')+'/')
            self.assertEqual(self.lib.test_directory(self.pointer, SIZE, *paths), 0)
            (root / 'PATCH_1.BIN').write_bytes(patch(modes=(4,)))
            for reads, closes in ((1, 0), (0, 1)):
                self.lib.test_io_failures(reads, closes)
                before = bytes(self.memory)
                self.assertEqual(self.lib.test_directory(self.pointer, SIZE, *paths), -errno.EIO)
                self.assertEqual(self.memory, before)

    @unittest.skipUnless(os.environ.get('POPS_TEST_ELF'), 'external Sony input is optional')
    def test_identified_external_core(self):
        elf = Path(os.environ['POPS_TEST_ELF']).read_bytes()
        self.assertEqual(hashlib.sha256(elf).hexdigest(),
                         '59df3389c4df88a572daa720b05507c52c34eddfa0031a6fbeec55e0c2d0fcb1')
        data = bytearray(SIZE)
        phoff = struct.unpack_from('<I', elf, 28)[0]
        ents, count = struct.unpack_from('<HH', elf, 42)
        for i in range(count):
            typ, off, va, _, fs, _, _, _ = struct.unpack_from('<8I', elf, phoff+i*ents)
            if typ == 1 and BASE <= va < BASE+SIZE and fs:
                self.assertLessEqual(va+fs, BASE+SIZE)
                data[va-BASE:va-BASE+fs] = elf[off:off+fs]
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         '38ecd425324a1244e90ae68b927496b9af511fd0ed89761199fb6eb699e71ab0')
        expected = bytearray(data)
        pointer = (c.c_ubyte * SIZE).from_buffer(data)
        ctx = Context()
        self.assertEqual(self.lib.pops_fix_context_init(c.byref(ctx), pointer, SIZE, 0), 0)
        blob = patch(modes=(2, 1, 5, 3))
        self.assertEqual(self.lib.pops_fix_stage(c.byref(ctx), pointer, SIZE, blob, len(blob), 1, 0), 0)
        apply_modes(expected, (2, 1, 5, 3))
        self.assertEqual(data, expected)



    def test_mode_6_disables_osd(self):
        self.assertEqual(self.stage(patch(modes=(6,))), 0)
        self.assertEqual(struct.unpack_from('<H', self.memory, 0x2525b0 - BASE)[0], 0x0648)

    def test_video_action_pal(self):
        self.assertEqual(self.stage(patch(control=2)), 0)
        self.assertEqual(self.memory[0x21af94 - BASE], 3)
        self.assertEqual(struct.unpack_from('<I', self.memory, 0x502770 - BASE)[0], 0x000a6300)
        self.assertEqual(self.memory[0x23b018 - BASE], 0x6b)
        self.assertEqual(struct.unpack_from('<H', self.memory, 0x23b01c - BASE)[0], 0x02cb)

    def test_video_action_disable_auto(self):
        self.assertEqual(self.stage(patch(control=4)), 0)
        self.assertEqual(self.memory, pristine())

    def test_video_action_control6(self):
        for control in (6, 7):
            blob = patch(control=control, modes=(1,) if control == 7 else (),
                         payload=b'DATA', address=0x220000)
            self.assertEqual(self.stage(blob), -errno.ENOTSUP)
            self.assert_rejected_without_writes(blob)

    def test_video_action_with_modes(self):
        self.assertEqual(self.stage(patch(control=3, modes=(6, 1))), 0)
        self.assertEqual(struct.unpack_from('<H', self.memory, 0x2525b0 - BASE)[0], 0x0648)
        self.assertEqual(struct.unpack_from('<I', self.memory, 0x210314 - BASE)[0], 0x3c02005a)
        self.assertEqual(self.memory[0x21af94 - BASE], 3)
        self.assertEqual(struct.unpack_from('<I', self.memory, 0x502770 - BASE)[0], 0x000a6300)

    def test_video_action_disable_auto_prevents_subsequent_pal(self):
        self.assertEqual(self.stage(patch(control=4, slot=0), slot=0), 0)
        self.assertEqual(self.memory, pristine())
        self.assertEqual(self.stage(patch(control=2, slot=1), slot=1), 0)
        self.assertEqual(self.memory, pristine())

    def test_video_action_pal_prevents_subsequent_control6(self):
        self.assertEqual(self.stage(patch(control=2, slot=0), slot=0), 0)
        self.assertEqual(self.memory[0x21af94 - BASE], 3)
        self.assert_rejected_without_writes(patch(control=6, slot=1))
        self.assertEqual(self.memory[0x21af94 - BASE], 3)

    def test_rejected_control6_does_not_disable_subsequent_pal(self):
        self.assert_rejected_without_writes(patch(control=6, slot=0), slot=0)
        self.assertEqual(self.stage(patch(control=2, slot=1), slot=1), 0)
        self.assertEqual(self.memory[0x21af94 - BASE], 3)

if __name__ == '__main__':
    unittest.main()
