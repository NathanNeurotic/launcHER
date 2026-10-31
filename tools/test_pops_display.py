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
from trace_original_pops_display import OriginalDisplay, _Window, BASE as ORIGINAL_BASE, MANUAL_WINDOWS

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
                           'pops_config.c', 'pops_resident.c')),
                        '-o', str(lib)], check=True)
        cls.lib = c.CDLL(str(lib))
        cls.lib.pops_config_init.argtypes = [c.POINTER(PopsConfig)]
        cls.lib.pops_config_parse_line.argtypes = [c.POINTER(PopsConfig), c.c_char_p]
        cls.lib.pops_config_load_file.argtypes = [c.POINTER(PopsConfig), c.c_char_p]
        cls.lib.pops_resident_hook_display.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
        cls.lib.pops_resident_hook_progressive.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32, c.c_uint32]
        cls.lib.pops_resident_progressive_interlace.argtypes = [c.POINTER(PopsConfig)]
        cls.lib.pops_resident_progressive_interlace.restype = c.c_uint32
        cls.lib.pops_fix_context_init_video.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t, c.c_uint8, c.c_uint8]
        cls.lib.pops_fix_finalize_video.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t, c.c_int, c.c_uint8]
        cls.lib.pops_apply_region.argtypes = [c.c_void_p, c.c_size_t, c.c_int, c.c_uint8, c.c_int]
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

    def test_manual_first_valid_all_six_and_ranges(self):
        cfg = self.config('$DX_100000 $DX_-1 $DX_65536 $DX_1',
                          '$DY_0 $MAGH_99999 $MAGV_00001 $DW_0')
        self.assertEqual((cfg.gs_mask, cfg.gs_display_valid), (31, 0))
        cfg = self.config('$DX_100000 $DX_-1 $DX_65536 $DX_1',
                          '$DY_0 $MAGH_99999 $MAGV_00001 $DW_0 $DH_0')
        self.assertEqual(list(cfg.gs_values), [65536, 0, 99999, 1, 0, 0])
        self.assertEqual((cfg.gs_mask, cfg.gs_display_valid), (63, 1))
        # Zero width/height preserve the original's 32-bit underflow.
        self.assertEqual(cfg.gs_display, 0xffffffff00000000 | (99999 << 23) | (1 << 27) | 65536)
        for prefix in MANUAL_WINDOWS:
            for invalid in ('', '000000', '100000', '-1', '+1', '1x', '0x10'):
                bad = self.config(prefix + invalid)
                self.assertEqual((bad.gs_mask, bad.gs_display_valid), (0, 0), prefix + invalid)

    def test_manual_flags_are_file_local_and_last_complete_file_wins(self):
        cfg = self.config()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'CHEATS.TXT'
            def load(text):
                path.write_text(text)
                self.assertEqual(self.lib.pops_config_load_file(c.byref(cfg), os.fsencode(path)), 0)
            load('$DX_10 $DY_20 $MAGH_3\n')
            load('$MAGV_1 $DW_100 $DH_200\n')
            self.assertEqual(cfg.gs_display_valid, 0)
            load('$DX_10\n$DY_20\n$MAGH_3\n$MAGV_1\n$DW_100\n$DH_200\n$DX_30\n')
            expected = (199 << 44) | (99 << 32) | (1 << 27) | (3 << 23) | (20 << 12) | 10
            self.assertEqual((cfg.gs_display_valid, cfg.gs_display), (1, expected))
            load('$DX_80\n')
            self.assertEqual(cfg.gs_display, expected)
            load('$DX_1 $DY_2 $MAGH_0 $MAGV_0 $DW_1 $DH_1\n')
            self.assertEqual(cfg.gs_display, (2 << 12) | 1)
            load('$DX_1 $DY_2 $MAGH_0 $MAGV_0 $DW_1 $DH_1 $HDTVFIX\n')
            self.assertEqual(cfg.hdtv_fix, 0)
            load('$HDTVFIX\n')
            self.assertEqual((cfg.hdtv_fix, cfg.gs_display_valid), (1, 1))
            load('$480p\n')
            self.assertEqual(cfg.gs_display_valid, 0)
            load('$480p $DX_1 $DY_2 $MAGH_0 $MAGV_0 $DW_1 $DH_1\n')
            self.assertEqual(cfg.gs_display_valid, 1)
            load('$DX_1 $DY_2 $MAGH_0 $MAGV_0 $DW_1 $DH_1 $480p\n')
            self.assertEqual(cfg.gs_display_valid, 1)

    def test_manual_hook_all_guards_atomic_and_idempotent(self):
        sites = {0x21a094: 0xde050010, 0x21a098: 0x3c031200,
                 0x23acb0: 0x32240001, 0x23ad0c: 0x24040001}
        def data():
            b = bytearray(b'\xa5') * SIZE
            for a, v in sites.items():
                patch(b, a, v, 4)
            return b
        def apply(b, size=SIZE, entry=0x143a020):
            return self.lib.pops_resident_hook_display((c.c_uint8 * SIZE).from_buffer(b), size, entry)
        b, expected = data(), data()
        for a, v in {0x21a094: 0x08000000 | (0x143a020 >> 2)}.items():
            patch(expected, a, v, 4)
        for _ in range(2):
            self.assertEqual(apply(b), 0)
            self.assertEqual(b, expected)
        for a in sites:
            b = data()
            b[a - BASE] ^= 1
            before = bytes(b)
            self.assertEqual(apply(b), -errno.EILSEQ)
            self.assertEqual(b, before)
        b = data()
        self.assertEqual(apply(b, size=0x3ad0f), -errno.ERANGE)
        self.assertEqual(apply(b, entry=0x143a021), -errno.EINVAL)
        self.assertEqual(apply(b, entry=0x1460000), -errno.EINVAL)
        self.assertEqual(b, data())

    @unittest.skipUnless(os.environ.get('POPSTARTER_TEST_ELF'), 'optional external POPStarter MAIN')
    def test_original_manual_display_differential(self):
        original = OriginalDisplay(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())
        rng = random.Random(0x4753)
        cases = []
        prefixes = list(MANUAL_WINDOWS)
        for n in (0, 1, 9, 10, 99, 100, 999, 1000, 9999, 10000, 65535, 65536, 99999, 100000):
            cases.append([p + str(n) for p in prefixes])
        for p in prefixes:
            for suffix in ('', '000000', '100000', '-1', '+1', '1x', '0x10', '00001'):
                cases.append([p + suffix])
            cases.append([p + '0', p + '99999'])
        for _ in range(96):
            commands = [p + str(rng.randrange(100000)) for p in prefixes]
            rng.shuffle(commands)
            cases.append(commands)
        for mask in range(64):
            cases.append([p + '1' for i, p in enumerate(prefixes) if mask & (1 << i)])
        for commands in cases:
            measured = original.manual(commands)
            cfg = self.config(*commands)
            self.assertEqual(list(cfg.gs_values), measured['values'], commands)
            self.assertEqual([bool(cfg.gs_mask & (1 << i)) for i in range(6)], measured['flags'], commands)
            self.assertEqual(bool(cfg.gs_display_valid), bool(measured['writes']), commands)
            if measured['writes']:
                self.assertEqual(cfg.gs_display, measured['writes'][0][1], commands)
                self.assertEqual(measured['writes'][1:], [[0x21a094, 0x0808e5da, 4],
                                                         [0x23acb0, 0x32240001, 4],
                                                         [0x23ad0c, 0x32240001, 4]])
        print(f'Original manual DISPLAY differential PASS: {len(cases)} file cases')

    @unittest.skipUnless(os.environ.get('POPSTARTER_TEST_ELF'), 'optional external POPStarter MAIN')
    def test_original_manual_option_order(self):
        original = OriginalDisplay(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())
        full = [p + '1' for p in MANUAL_WINDOWS]
        cases = []
        for option in ('$HDTVFIX', '$NOHDTVFIX', '$480p'):
            for at in (0, 3, 6):
                cases.append([full[:at] + [option] + full[at:]])
            cases.append([full, [option]])
            cases.append([[option], full])
            cases.append([full, ['$DX_2', option]])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'CHEATS.TXT'
            for files in cases:
                cfg = self.config()
                writes = {0x23acb0: 0x32240001, 0x21a094: 0xde050010}
                for commands in files:
                    path.write_text('\n'.join(commands) + '\n')
                    self.assertEqual(self.lib.pops_config_load_file(c.byref(cfg), os.fsencode(path)), 0)
                    for address, value, _ in original.manual(commands)['writes']:
                        writes[address] = value
                self.assertEqual(bool(cfg.gs_display_valid), writes[0x21a094] == 0x0808e5da, files)
                # Progressive mode is intentionally still unsupported; its
                # li a0,0 sites are not claimed by the fixed override.
                if cfg.gs_display_valid:
                    self.assertEqual(cfg.hdtv_fix, writes[0x23acb0] == 0x24040001, files)
        print(f'Original manual DISPLAY option-order PASS: {len(cases)} file sequences')

    def test_progressive_hook_guards_are_atomic(self):
        sites = {0x21a094: (0xde050010, 4), 0x21a098: (0x3c031200, 4),
                 0x21af94: (2, 1), 0x23acb0: (0x32240001, 4), 0x23ad0c: (0x32240001, 4)}
        def data():
            b = bytearray(b'\xa5') * SIZE
            for a, (v, w) in sites.items():
                patch(b, a, v, w)
            return b
        def apply(b, size=SIZE, entry=0x143a040, arg=0x24040000):
            return self.lib.pops_resident_hook_progressive((c.c_uint8 * SIZE).from_buffer(b), size, entry, arg)
        b, expected = data(), data()
        for a, v, w in ((0x21a094, 0x08000000 | (0x143a040 >> 2), 4), (0x21af94, 0x50, 1),
                        (0x23acb0, 0x24040000, 4), (0x23ad0c, 0x24040000, 4)):
            patch(expected, a, v, w)
        for _ in range(2):
            self.assertEqual(apply(b), 0)
            self.assertEqual(b, expected)
        for a in sites:
            b = data()
            b[a - BASE] ^= 1
            before = bytes(b)
            self.assertEqual(apply(b), -errno.EILSEQ)
            self.assertEqual(b, before)
        for a, v, w in ((0x21af94, 3, 1), (0x23acb0, 0x24040001, 4)):
            b = data()
            patch(b, a, v, w)
            before = bytes(b)
            self.assertEqual(apply(b), -errno.EILSEQ)
            self.assertEqual(b, before)
        b = data()
        self.assertEqual(apply(b, size=0x3ad0f), -errno.ERANGE)
        self.assertEqual(apply(b, entry=0x143a041), -errno.EINVAL)
        self.assertEqual(apply(b, arg=0x24040002), -errno.EINVAL)
        self.assertEqual(b, data())

    @unittest.skipUnless(os.environ.get('POPSTARTER_TEST_ELF'), 'optional external POPStarter MAIN')
    def test_original_progressive_text_staging(self):
        from test_pops_fix_files import Context, pristine as fix_pristine
        original = OriginalDisplay(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())
        full = [p + '1' for p in MANUAL_WINDOWS]
        options = ('$HDTVFIX', '$NOHDTVFIX', '$NOPAL', '$FORCEPAL')
        cases = [[['$480p']], [['$480p'], full], [full, ['$480p']],
                 [['$480p'] + full + ['$HDTVFIX']], [full + ['$480p']],
                 [['$480p'] + full, ['$HDTVFIX']], [full, ['$HDTVFIX', '$480p']]]
        for option in options:
            cases += [[['$480p', option]], [[option, '$480p']],
                      [['$480p'], [option]], [['$480p'] + full, [option]],
                      [[option] + full, ['$480p']], [['$480p', option] + full]]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'CHEATS.TXT'
            for files in cases:
                cfg = self.config()
                expected = {0x21a094: 0xde050010, 0x21af94: 2,
                            0x23acb0: 0x32240001, 0x23ad0c: 0x32240001}
                for commands in files:
                    path.write_text('\n'.join(commands) + '\n')
                    self.assertEqual(self.lib.pops_config_load_file(c.byref(cfg), os.fsencode(path)), 0)
                    for a, v, _ in original.manual(commands)['writes']:
                        if a in expected:
                            expected[a] = v
                self.assertEqual(cfg.progressive_requested, 1, files)
                self.assertEqual(bool(cfg.gs_display_valid), expected[0x21a094] == 0x0808e5da, files)
                b = fix_pristine()
                for a, v, w in ((0x21a094, 0xde050010, 4), (0x21a098, 0x3c031200, 4),
                                (0x21af94, 2, 1), (0x23acb0, 0x32240001, 4), (0x23ad0c, 0x32240001, 4)):
                    patch(b, a, v, w)
                pointer = (c.c_uint8 * SIZE).from_buffer(b)
                self.assertEqual(self.lib.pops_apply_all_config_patches(pointer, SIZE, c.byref(cfg)), 0, files)
                context = Context()
                # Production passes sticky progressive state to the fix-file
                # session, even if a later command selected FORCEPAL/NOPAL.
                initial_mode = 4 if cfg.progressive_requested else cfg.video_mode  # POPS_VMODE_480P
                self.assertEqual(self.lib.pops_fix_context_init_video(c.byref(context), pointer,
                                                                     SIZE, cfg.compat_modes, initial_mode), 0, files)
                self.assertEqual(context.video_auto_disabled, 1, files)
                self.assertEqual(self.lib.pops_fix_finalize_video(c.byref(context), pointer, SIZE,
                                                                 1, cfg.video_mode), 0, files)
                self.assertEqual(self.lib.pops_apply_region(pointer, SIZE, 1, cfg.video_mode,
                                                           context.video_auto_disabled), 0, files)
                # A European licence must not silently reapply PAL here.
                self.assertEqual(b[0x21af94 - BASE], 2, files)
                entry = 0x143a020 if cfg.gs_display_valid else 0x143a040
                arg = self.lib.pops_resident_progressive_interlace(c.byref(cfg))
                self.assertEqual(self.lib.pops_resident_hook_progressive(pointer, SIZE, entry, arg), 0, files)
                for a in (0x21af94, 0x23acb0, 0x23ad0c):
                    width = 1 if a == 0x21af94 else 4
                    self.assertEqual(int.from_bytes(b[a - BASE:a - BASE + width], 'little'), expected[a], files)
                self.assertEqual(struct.unpack_from('<I', b, 0x21a094 - BASE)[0], 0x08000000 | (entry >> 2))
        print(f'Original progressive text/file staging PASS: {len(cases)} sequences')

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
        # The resident manual hook uses the same measured core independently
        # of the immediate-field display commands above.
        manual = bytearray(data)
        pointer = (c.c_ubyte * SIZE).from_buffer(manual)
        self.assertEqual(self.lib.pops_resident_hook_display(pointer, SIZE, 0x143a020), 0)
        full = '$DX_10 $DY_20 $MAGH_3 $MAGV_1 $DW_100 $DH_200'
        for command in (full, '$HDTVFIX ' + full, full + ' $HDTVFIX'):
            staged, cfg = bytearray(data), self.config(command)
            pointer = (c.c_ubyte * SIZE).from_buffer(staged)
            self.assertEqual(self.lib.pops_apply_all_config_patches(pointer, SIZE, c.byref(cfg)), 0)
            self.assertEqual(self.lib.pops_resident_hook_display(pointer, SIZE, 0x143a020), 0)
            for address in (0x23acb0, 0x23ad0c):
                self.assertEqual(struct.unpack_from('<I', staged, address - BASE)[0], 0x32240001)
        for command in ('$480p', '$480p $HDTVFIX', '$NOHDTVFIX $480p', '$480p ' + full):
            staged, cfg = bytearray(data), self.config(command)
            pointer = (c.c_ubyte * SIZE).from_buffer(staged)
            self.assertEqual(self.lib.pops_apply_all_config_patches(pointer, SIZE, c.byref(cfg)), 0)
            arg = self.lib.pops_resident_progressive_interlace(c.byref(cfg))
            self.assertEqual(self.lib.pops_resident_hook_progressive(pointer, SIZE, 0x143a040, arg), 0)
            self.assertEqual(staged[0x21af94 - BASE], 0x50)
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

    def test_branch_likely_annuls_only_the_untaken_delay(self):
        # beql v0,zero,+1; addiu v1,zero,7; nop
        for value, expected in ((0, 7), (1, 0)):
            m = self.machine([0x50400001, 0x24030007, 0])
            m.reg[2] = value
            m.run()
            self.assertEqual(m.reg[3], expected)

    def test_progressive_shift_and_lq_low64_semantics(self):
        m = self.machine([(2 << 16) | (3 << 11) | 0x3f]) # dsra32 v1,v0,0
        m.reg[2] = 0x80000000ffffffff
        m.instruction(ORIGINAL_BASE)
        self.assertEqual(m.reg[3], 0xffffffff80000000)
        m = self.machine([(0x1e << 26) | (4 << 21) | (5 << 16)]) # lq a1,0(a0)
        m.reg[4] = m.FRAME
        m.store_bytes(m.FRAME, bytes(range(16)))
        m.instruction(ORIGINAL_BASE)
        self.assertEqual(m.reg[5], 0x0706050403020100)
        m.reg[4] += 1
        with self.assertRaises(ValueError):
            m.instruction(ORIGINAL_BASE)

    @unittest.skipUnless(os.environ.get('POPSTARTER_TEST_ELF'), 'optional external POPStarter MAIN')
    def test_original_patch_video_gates(self):
        original = OriginalDisplay(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())
        count = 0
        for control in range(8):
            for mask in range(16):
                disabled, custom, forced, selector = [bool(mask & (1 << i)) for i in range(4)]
                measured = original.patch_video(control, auto_disabled=disabled, custom_set=custom,
                                                 force_pal=forced, auto_selector=selector)
                expected = {'auto_disabled': disabled, 'custom_set': custom,
                            'force_pal': forced, 'auto_selector': selector, 'writes': []}
                action = control & 6
                if action == 2 and not disabled:
                    expected.update(auto_disabled=True, custom_set=True, auto_selector=False,
                                    writes=[[0x21af94, 3, 1], [0x502770, 0xa6300, 4],
                                            [0x23b018, 0x6b, 1], [0x23b01c, 0x2cb, 2]])
                elif action == 4:
                    expected.update(auto_disabled=True, auto_selector=False)
                elif action == 6 and not custom:
                    expected.update(auto_disabled=True, custom_set=True, force_pal=False,
                                    auto_selector=False,
                                    writes=[[0x21af94, 0x50, 1], [0x21a094, 0x0808e53c, 4],
                                            [0x23acb0, 0x24040000, 4], [0x23ad0c, 0x24040000, 4]])
                self.assertEqual(measured, expected, (control, mask))
                count += 1
        print(f'Original post-payload PATCH video gate matrix PASS: {count} states')

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
