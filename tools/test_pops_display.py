#!/usr/bin/env python3
"""Guarded display staging; optional differential with external original MAIN.

POPS_TEST_ELF enables exact Sony-core guard verification.
POPSTARTER_TEST_ELF enables bounded original-command differential execution.
Neither external binary is required or distributed by CI.
"""
import ctypes as c
import errno
import hashlib
import os
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import unittest

from test_pops_features import PopsConfig
from trace_original_pops_display import OriginalDisplay, _Window, BASE as ORIGINAL_BASE

ROOT = Path(__file__).resolve().parents[1]
BASE, SIZE = 0x200000, 0x302e60
# Measured on the identified external Sony core, independently of C tables.
SITES = [(0x21af88, 0x0c0903d8, 4), (0x21af8c, 0x2484f1d8, 4),
         (0x21a0a4, 0xfc450000, 4), (0x21a0a8, 0x0220202d, 4),
         (0x21b128, 0x0200, 2), (0x21c114, 0x0200, 2), (0x221958, 0xae2421b4, 4),
         (0x21c18c, 0x0010, 2), (0x2219d0, 0xae2421b8, 4), (0x21b130, 0xae2821b8, 4),
         (0x23af40, 0x09ff, 2), (0x23aff4, 0x09ff, 2),
         (0x221960, 0xae2321bc, 4), (0x21b12c, 0x0a00, 2), (0x21c184, 0x0a00, 2)]


def patch(data, address, value, width):
    data[address - BASE:address - BASE + width] = value.to_bytes(width, 'little')


def pristine():
    # Nonzero filler detects unintended zeroing outside the actual writes.
    data = bytearray(b'\xa5') * SIZE
    for address, value, width in SITES:
        patch(data, address, value, width)
    return data


class DisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        lib = Path(cls.tmp.name) / ('display.dll' if os.name == 'nt' else 'display.so')
        subprocess.run(['gcc', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I', str(ROOT / 'common/include'),
                        *(str(ROOT / 'common/src' / name) for name in
                          ('pops_modes_patches.c', 'pops_resident_engine.c', 'pops_external.c',
                           'pops_config.c')),
                        '-o', str(lib)], check=True)
        cls.lib = c.CDLL(str(lib))
        cls.lib.pops_config_init.argtypes = [c.POINTER(PopsConfig)]
        cls.lib.pops_config_parse_line.argtypes = [c.POINTER(PopsConfig), c.c_char_p]
        for name in ('pops_apply_display_config', 'pops_apply_all_config_patches'):
            getattr(cls.lib, name).argtypes = [c.c_void_p, c.c_size_t, c.POINTER(PopsConfig)]

    @classmethod
    def tearDownClass(cls):
        if os.name == 'nt':
            c.windll.kernel32.FreeLibrary.argtypes = [c.c_void_p]
            c.windll.kernel32.FreeLibrary(cls.lib._handle)
        cls.tmp.cleanup()

    def config(self, *lines):
        cfg = PopsConfig()
        self.lib.pops_config_init(c.byref(cfg))
        for line in lines:
            self.assertEqual(self.lib.pops_config_parse_line(c.byref(cfg), line.encode()), 0)
        return cfg

    def apply(self, data, cfg, size=None):
        pointer = (c.c_ubyte * len(data)).from_buffer(data)
        return self.lib.pops_apply_display_config(pointer, len(data) if size is None else size,
                                                 c.byref(cfg))

    def test_exact_writes_and_idempotence(self):
        data, expected = pristine(), pristine()
        cfg = self.config('$SMOOTH $LEFTADJ_123 $XPOS_65535 $YPOS_0',
                          '$DWSTRETCH_9999 $DWCROP_0123')
        for a, v, w in [(0x21af88, 0xa21a22a0341a0001, 8),
                        (0x21a0a4, 0x64a50f85, 4), (0x21a0a8, 0xfc450000, 4),
                        (0x21b128, 65535, 2), (0x21c114, 65535, 2), (0x221958, 0, 4),
                        (0x21c18c, 0, 2), (0x2219d0, 0, 4), (0x21b130, 0, 4),
                        (0x23af40, 9999, 2), (0x23aff4, 9999, 2),
                        (0x221960, 0, 4), (0x21b12c, 123, 2), (0x21c184, 123, 2)]:
            patch(expected, a, v, w)
        for _ in range(2):
            self.assertEqual(self.apply(data, cfg), 0)
            self.assertEqual(data, expected)

    def test_digit_ranges_and_invalid_commands(self):
        for prefix, invalid in [('$LEFTADJ_', ('', '0', '256', '999', '0001')),
                                ('$XPOS_', ('', '65536', '99999', '000000')),
                                ('$YPOS_', ('', '65536', '99999', '000000')),
                                ('$DWSTRETCH_', ('', '10000', '00000')),
                                ('$DWCROP_', ('', '10000', '00000'))]:
            for suffix in (*invalid, '-1', '+1', '1x', '0x10'):
                cfg = self.config(prefix + suffix)
                data = pristine()
                self.assertEqual(self.apply(data, cfg), 0)
                self.assertEqual(data, pristine(), prefix + suffix)

    def test_first_valid_position_and_last_valid_width(self):
        cfg = self.config('$XPOS_99999 $XPOS_0 $XPOS_100', '$YPOS_65535 $YPOS_10',
                          '$DWSTRETCH_100 $DWSTRETCH_200 $DWSTRETCH_99999',
                          '$DWCROP_1 $DWCROP_2', '$LEFTADJ_1 $LEFTADJ_255')
        self.assertEqual((cfg.display_x, cfg.display_y, cfg.display_stretch,
                          cfg.display_crop, cfg.left_adjust, cfg.display_mask),
                         (0, 65535, 200, 2, 255, 15))

    def test_every_selected_guard_failure_is_atomic(self):
        cfg = self.config('$SMOOTH $LEFTADJ_1 $XPOS_10 $YPOS_20 $DWSTRETCH_30 $DWCROP_40')
        for address, _, _ in SITES:
            data = pristine()
            data[address - BASE] ^= 0x80
            before = bytes(data)
            self.assertEqual(self.apply(data, cfg), -errno.EILSEQ, hex(address))
            self.assertEqual(data, before)
        for size in (0, 0x1af8f, 0x3aff5):
            data = pristine()
            before = bytes(data)
            self.assertEqual(self.apply(data, cfg, size), -errno.ERANGE)
            self.assertEqual(data, before)

    def test_invalid_config_and_null_inputs(self):
        cfg, data = self.config(), pristine()
        cfg.display_mask = 16
        self.assertEqual(self.apply(data, cfg), -errno.EINVAL)
        cfg.display_mask, cfg.display_stretch = 4, 10000
        self.assertEqual(self.apply(data, cfg), -errno.EINVAL)
        self.assertEqual(data, pristine())
        self.assertEqual(self.lib.pops_apply_display_config(None, SIZE, c.byref(cfg)), -errno.EINVAL)
        self.assertEqual(self.lib.pops_apply_display_config((c.c_char * 1)(), 1, None), -errno.EINVAL)

    def test_aggregate_prechecks_display_before_compatibility_writes(self):
        from test_pops_fix_files import pristine as compat_pristine
        cfg = self.config('$MODE4 $SMOOTH $DWCROP_10')
        data = compat_pristine()
        for address, value, width in SITES:
            patch(data, address, value, width)
        data[0x21c184 - BASE] ^= 1
        before = bytes(data)
        pointer = (c.c_ubyte * SIZE).from_buffer(data)
        self.assertEqual(self.lib.pops_apply_all_config_patches(pointer, SIZE, c.byref(cfg)), -errno.EILSEQ)
        self.assertEqual(data, before)
        data[0x21c184 - BASE] ^= 1
        self.assertEqual(self.lib.pops_apply_all_config_patches(pointer, SIZE, c.byref(cfg)), 0)
        self.assertEqual(data[0x21af70 - BASE], 0)
        self.assertEqual(struct.unpack_from('<Q', data, 0x21af88 - BASE)[0], 0xa21a22a0341a0001)

    @unittest.skipUnless(os.environ.get('POPS_TEST_ELF'), 'optional external Sony core')
    def test_identified_external_core_guards(self):
        elf = Path(os.environ['POPS_TEST_ELF']).read_bytes()
        self.assertEqual(hashlib.sha256(elf).hexdigest(),
                         '59df3389c4df88a572daa720b05507c52c34eddfa0031a6fbeec55e0c2d0fcb1')
        data = bytearray(SIZE)
        at = struct.unpack_from('<I', elf, 28)[0]
        ents, count = struct.unpack_from('<HH', elf, 42)
        for i in range(count):
            kind, off, va, _, fs, _, _, _ = struct.unpack_from('<8I', elf, at + i * ents)
            if kind == 1 and BASE <= va and va + fs <= BASE + SIZE:
                data[va - BASE:va - BASE + fs] = elf[off:off + fs]
        for address, value, width in SITES:
            self.assertEqual(int.from_bytes(data[address - BASE:address - BASE + width], 'little'), value)
        cfg = self.config('$SMOOTH $LEFTADJ_255 $XPOS_0 $YPOS_65535 $DWSTRETCH_9999 $DWCROP_0')
        self.assertEqual(self.apply(data, cfg), 0)

    @unittest.skipUnless(os.environ.get('POPSTARTER_TEST_ELF'), 'optional external POPStarter MAIN')
    def test_original_command_differential(self):
        original = OriginalDisplay(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())
        rng = random.Random(0x13)
        commands = ['$SMOOTH'] + [f'$LEFTADJ_{i}' for i in range(1000)]
        for prefix, limit in (('$XPOS_', 65535), ('$YPOS_', 65535),
                              ('$DWSTRETCH_', 9999), ('$DWCROP_', 9999)):
            values = set(range(11)) | {99, 100, 101, 255, 256, 999, 1000, 9999, limit, limit + 1}
            values |= {rng.randrange(limit + 1) for _ in range(128)}
            commands += [prefix + str(i) for i in sorted(values)]
            commands += [prefix + '0' * (len(str(limit)) - 1) + '1']
        for command in commands:
            expected, data = pristine(), pristine()
            measured = original.run(command)
            for address, value, width in measured['writes']:
                patch(expected, address, value, width)
            cfg = self.config(command)
            self.assertEqual(self.apply(data, cfg), 0, command)
            self.assertEqual(data, expected, command)
        # Original X/Y globals prevent a second position command, independently.
        for command, xs, ys in (('$XPOS_123', True, False), ('$YPOS_123', False, True)):
            self.assertEqual(original.run(command, xs, ys)['writes'], [])
        print(f'Original display differential PASS: {len(commands)} command inputs + 2 one-shot states')


class InterpreterTests(unittest.TestCase):
    def machine(self, words):
        data = struct.pack('<' + 'I' * len(words), *words)
        return _Window(data, ORIGINAL_BASE, ORIGINAL_BASE + len(data), '')

    def test_r5900_mult_writes_rd_and_sign_extends(self):
        m = self.machine([(2 << 21) | (3 << 16) | (4 << 11) | 0x18])
        m.reg[2], m.reg[3] = 0xffffffff, 100
        m.instruction(ORIGINAL_BASE)
        self.assertEqual(m.reg[4], (1 << 64) - 100)

    def test_branch_delay_slot_executes_before_taken_target(self):
        # beq zero,zero,+2; addiu v0,zero,7; addiu v0,zero,9
        m = self.machine([0x10000002, 0x24020007, 0x24020009])
        m.run()
        self.assertEqual(m.reg[2], 7)

    def test_unmodeled_instruction_and_memory_fail_closed(self):
        m = self.machine([0xffffffff])
        with self.assertRaises(ValueError):
            m.run()
        with self.assertRaises(ValueError):
            m.load(0x200000, 4)
        with self.assertRaises(ValueError):
            m.service(0x123456)
        with self.assertRaises(ValueError):
            OriginalDisplay(b'not the pinned image')


if __name__ == '__main__':
    unittest.main()
