#!/usr/bin/env python3
import ctypes as c
import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class CheatEntry(c.Structure):
    _fields_ = [
        ("address", c.c_uint32),
        ("value", c.c_uint16),
        ("type", c.c_uint8),
    ]

class PopsConfig(c.Structure):
    _fields_ = [
        ("video_mode", c.c_uint8),
        ("hdtv_fix", c.c_uint8),
        ("x_offset", c.c_int16),
        ("y_offset", c.c_int16),
        ("smooth", c.c_uint8),
        ("widescreen", c.c_uint8),
        ("dither_off", c.c_uint8),
        ("fast_mips", c.c_uint8),
        ("slow_mips", c.c_uint8),
        ("no_boot", c.c_uint8),
        ("no_igr", c.c_uint8),
        ("igr_type", c.c_uint8),
        ("safe_mode", c.c_uint8),
        ("usb_delay", c.c_uint8),
        ("compat_modes", c.c_uint8),
        ("disc_count", c.c_uint8),
        ("discs", (c.c_char * 128) * 4),
        ("vmc_dir", c.c_char * 128),
        ("cheat_count", c.c_uint16),
        ("cheats", CheatEntry * 256),
    ]

class PopsCompatEntry(c.Structure):
    _fields_ = [
        ("serial", c.c_char_p),
        ("title", c.c_char_p),
        ("default_modes", c.c_uint8),
        ("has_libcrypt", c.c_uint8),
        ("libcrypt_key", c.c_uint16),
        ("patch_offset", c.c_uint32),
        ("patch_val", c.c_uint32),
    ]

class PopsVcdInfo(c.Structure):
    _fields_ = [
        ("sector_size", c.c_uint32),
        ("data_offset", c.c_uint32),
        ("pvd_lba", c.c_uint32),
        ("root_lba", c.c_uint32),
        ("root_size", c.c_uint32),
        ("raw_serial", c.c_char * 32),
        ("normalized_serial", c.c_char * 32),
    ]

def compile_shared_library():
    so_name = "pops_features_test.dll" if os.name == "nt" else "pops_features_test.so"
    so_path = Path(tempfile.gettempdir()) / so_name
    sources = [
        str(ROOT / "common/src/pops_config.c"),
        str(ROOT / "tools/fixtures/pops_config_host_io.c"),
        str(ROOT / "common/src/pops_compat_db.c"),
        str(ROOT / "common/src/pops_modes_patches.c"),
        str(ROOT / "common/src/pops_vcd.c"),
    ]
    cmd = ["gcc", "-shared", "-fPIC", "-O2", "-Dfopen=pops_test_fopen", "-I", str(ROOT / "common/include")] + sources + ["-o", str(so_path)]
    subprocess.check_call(cmd)
    return c.CDLL(str(so_path))

LIB = None

class FeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global LIB
        LIB = compile_shared_library()
        LIB.pops_config_init.argtypes = [c.POINTER(PopsConfig)]
        LIB.pops_config_parse_line.argtypes = [c.POINTER(PopsConfig), c.c_char_p]
        LIB.pops_config_parse_line.restype = c.c_int
        LIB.pops_config_load_table.argtypes = [c.POINTER(PopsConfig), c.POINTER(c.c_uint8 * 32)]
        LIB.pops_config_load_table.restype = c.c_int
        LIB.pops_config_export_table.argtypes = [c.POINTER(PopsConfig), c.POINTER(c.c_uint8 * 32)]
        LIB.pops_config_export_table.restype = None
        LIB.pops_compat_db_lookup.argtypes = [c.c_char_p]
        LIB.pops_compat_db_lookup.restype = c.POINTER(PopsCompatEntry)
        LIB.pops_compat_db_count.restype = c.c_size_t
        LIB.pops_apply_compat_modes.argtypes = [c.c_void_p, c.c_size_t, c.c_uint8]
        LIB.pops_apply_compat_modes.restype = c.c_int
        LIB.pops_apply_video_overrides.argtypes = [c.c_void_p, c.c_size_t, c.c_uint8, c.c_uint8, c.c_int16, c.c_int16]
        LIB.pops_apply_video_overrides.restype = c.c_int
        LIB.pops_apply_smooth.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_smooth.restype = c.c_int
        LIB.pops_apply_widescreen.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_widescreen.restype = c.c_int
        LIB.pops_apply_dither_off.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_dither_off.restype = c.c_int
        LIB.pops_apply_throttling.argtypes = [c.c_void_p, c.c_size_t, c.c_uint8, c.c_uint8]
        LIB.pops_apply_throttling.restype = c.c_int
        LIB.pops_apply_bios_shell.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_bios_shell.restype = c.c_int
        LIB.pops_apply_libcrypt_bypass.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_libcrypt_bypass.restype = c.c_int
        LIB.pops_apply_cheats.argtypes = [c.c_void_p, c.POINTER(CheatEntry), c.c_uint16]
        LIB.pops_apply_cheats.restype = c.c_int
        LIB.pops_check_igr_combo.argtypes = [c.c_uint16]
        LIB.pops_check_igr_combo.restype = c.c_int
        LIB.pops_check_igr_combo_type.argtypes = [c.c_uint16, c.c_uint8]
        LIB.pops_check_igr_combo_type.restype = c.c_int
        LIB.pops_check_disc_swap_combo.argtypes = [c.c_uint16]
        LIB.pops_check_disc_swap_combo.restype = c.c_int
        LIB.pops_generate_subq.argtypes = [c.c_uint32, c.c_uint16, c.POINTER(c.c_uint8 * 12)]
        LIB.pops_generate_subq.restype = c.c_int
        LIB.pops_cheat_engine_tick.argtypes = [c.c_void_p, c.POINTER(CheatEntry), c.c_uint16]
        LIB.pops_cheat_engine_tick.restype = c.c_int
        LIB.pops_vcd_normalize_serial.argtypes = [c.c_char_p, c.c_char_p, c.c_size_t]
        LIB.pops_vcd_normalize_serial.restype = c.c_int
        LIB.pops_vcd_inspect_path.argtypes = [c.c_char_p, c.POINTER(PopsVcdInfo)]
        LIB.pops_vcd_inspect_path.restype = c.c_int

    def test_vcd_serial_normalization(self):
        norm = c.create_string_buffer(32)
        # Standard PS1 format
        self.assertEqual(LIB.pops_vcd_normalize_serial(b"cdrom0:\\SLUS_008.70;1", norm, 32), 0)
        self.assertEqual(norm.value.decode("ascii"), "SLUS-00870")

        self.assertEqual(LIB.pops_vcd_normalize_serial(b"SCES_014.22;1", norm, 32), 0)
        self.assertEqual(norm.value.decode("ascii"), "SCES-01422")

        # Already normalized format
        self.assertEqual(LIB.pops_vcd_normalize_serial(b"SLES-02529", norm, 32), 0)
        self.assertEqual(norm.value.decode("ascii"), "SLES-02529")

        # Lowercase / spaces
        self.assertEqual(LIB.pops_vcd_normalize_serial(b"  slps_013.00;1 \n", norm, 32), 0)
        self.assertEqual(norm.value.decode("ascii"), "SLPS-01300")

    def test_vcd_image_inspection(self):
        # Create a synthetic Mode 2 Form 1 raw 2352-byte sector VCD image in a temp file
        temp_vcd = Path(tempfile.gettempdir()) / "test_game.vcd"
        sector_size = 2352
        data_offset = 24
        total_sectors = 20

        sync_hdr = b"\x00\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\x00"
        mode2_hdr = b"\x00\x02\x00\x02"  # Mode 2
        sub_hdr = b"\x00\x00\x08\x00\x00\x00\x08\x00"

        with open(temp_vcd, "wb") as f:
            for s in range(total_sectors):
                sector = bytearray(sector_size)
                # Sync & headers
                sector[0:12] = sync_hdr
                sector[12:16] = mode2_hdr
                sector[16:24] = sub_hdr

                if s == 16:  # PVD
                    pvd = bytearray(2048)
                    pvd[0] = 0x01
                    pvd[1:6] = b"CD001"
                    pvd[6] = 0x01
                    # Root directory record at offset 156
                    root_rec = bytearray(34)
                    root_rec[0] = 34  # length
                    struct.pack_into("<I", root_rec, 2, 17)   # Root LBA = 17
                    struct.pack_into(">I", root_rec, 6, 17)
                    struct.pack_into("<I", root_rec, 10, 2048) # Root size = 2048
                    struct.pack_into(">I", root_rec, 14, 2048)
                    pvd[156:156+34] = root_rec
                    sector[data_offset:data_offset+2048] = pvd

                elif s == 17:  # Root Directory
                    dir_sec = bytearray(2048)
                    # Directory entry for SYSTEM.CNF;1
                    name = b"SYSTEM.CNF;1"
                    rec_len = 33 + len(name)
                    rec = bytearray(rec_len)
                    rec[0] = rec_len
                    struct.pack_into("<I", rec, 2, 18)   # LBA = 18
                    struct.pack_into(">I", rec, 6, 18)
                    struct.pack_into("<I", rec, 10, 64)  # File size = 64
                    struct.pack_into(">I", rec, 14, 64)
                    rec[25] = 0  # file flags
                    rec[32] = len(name)
                    rec[33:33+len(name)] = name
                    dir_sec[0:rec_len] = rec
                    sector[data_offset:data_offset+2048] = dir_sec

                elif s == 18:  # SYSTEM.CNF content
                    cnf = bytearray(2048)
                    text = b"BOOT = cdrom0:\\SLUS_008.70;1\r\nTCB = 4\r\nEVENT = 16\r\nSTACK = 801FFFF0\r\n"
                    cnf[0:len(text)] = text
                    sector[data_offset:data_offset+2048] = cnf

                f.write(sector)

        info = PopsVcdInfo()
        res = LIB.pops_vcd_inspect_path(str(temp_vcd).encode("utf-8"), c.byref(info))
        self.assertEqual(res, 0)
        self.assertEqual(info.sector_size, 2352)
        self.assertEqual(info.data_offset, 24)
        self.assertEqual(info.root_lba, 17)
        self.assertEqual(info.raw_serial.decode("ascii"), "cdrom0:\\SLUS_008.70;1")
        self.assertEqual(info.normalized_serial.decode("ascii"), "SLUS-00870")
        temp_vcd.unlink()

    def test_cheat_disable_errors_and_redirected_configuration(self):
        cfg = PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        for line in (b"80001234 5678", b"50000202 0001", b"C0000000 0000"):
            self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), line), 0)
        self.assertEqual(cfg.cheat_count, 0)
        for line in (b"$50000202 0001", b"$C0000000 0000"):
            self.assertLess(LIB.pops_config_parse_line(c.byref(cfg), line), 0)
        for _ in range(256):
            self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$80001234 5678"), 0)
        self.assertLess(LIB.pops_config_parse_line(c.byref(cfg), b"$80001234 5678"), 0)

        LIB.pops_config_discover.argtypes = [c.POINTER(PopsConfig), c.c_char_p, c.c_char_p]
        LIB.pops_config_load_file.argtypes = [c.POINTER(PopsConfig), c.c_char_p]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            title = root / 'Game'
            saves = root / 'Shared'
            title.mkdir()
            saves.mkdir()
            (root / 'VMCDIR.TXT').write_text('Shared')
            (title / 'CHEATS.TXT').write_text('$80001234 5678\n')
            (saves / 'CHEATS.TXT').write_text('$50000202 0001\n')
            LIB.pops_config_init(c.byref(cfg))
            self.assertEqual(LIB.pops_config_discover(c.byref(cfg),
                             (str(root) + '/').encode(), b'Game'), 0)
            self.assertEqual(cfg.cheat_count, 1)
            self.assertEqual(cfg.vmc_dir, b'Shared')
            (title / 'VMCDIR.TXT').write_text('Other')
            self.assertEqual(LIB.pops_config_discover(c.byref(cfg),
                             (str(root) + '/').encode(), b'Game'), 0)
            self.assertEqual(cfg.vmc_dir, b'Other')
            (title / 'CHEATS.TXT').write_text('$C0000000 0000\n')
            self.assertLess(LIB.pops_config_discover(c.byref(cfg),
                            (str(root) + '/').encode(), b'Game'), 0)
            oversized = root / 'long.txt'
            oversized.write_text('$80001234 5678' + ' ' * 300)
            self.assertLess(LIB.pops_config_load_file(c.byref(cfg), str(oversized).encode()), 0)

    def test_auxiliary_config_bounds(self):
        cfg = PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        for name in ('pops_config_load_discs', 'pops_config_load_vmcdir'):
            getattr(LIB, name).argtypes = [c.POINTER(PopsConfig), c.c_char_p]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.txt'
            encoded = str(path).encode()
            path.write_text('\n  \n# comment\nDisc1.VCD\nDisc2.VCD\n')
            self.assertEqual(LIB.pops_config_load_discs(c.byref(cfg), encoded), 0)
            self.assertEqual(cfg.disc_count, 2)
            self.assertEqual(bytes(cfg.discs[0]).split(b'\0')[0], b'Disc1.VCD')
            for content in ('X' * 128, 'Disc.VCD\n' * 5, 'X' * 300):
                path.write_text(content)
                self.assertLess(LIB.pops_config_load_discs(c.byref(cfg), encoded), 0)
            cfg.vmc_dir = b'Keep'
            path.write_text('X' * 128)
            self.assertLess(LIB.pops_config_load_vmcdir(c.byref(cfg), encoded), 0)
            self.assertEqual(cfg.vmc_dir, b'Keep')
            path.write_text('\n')
            self.assertEqual(LIB.pops_config_load_vmcdir(c.byref(cfg), encoded), 0)
            self.assertEqual(cfg.vmc_dir, b'Keep')

    def test_config_parser_directives(self):
        cfg = PopsConfig()
        LIB.pops_config_init(c.byref(cfg))

        # Directives
        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$480p"), 0)
        self.assertEqual(cfg.video_mode, 4)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$HDTVFIX"), 0)
        self.assertEqual(cfg.hdtv_fix, 1)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$SMOOTH"), 0)
        self.assertEqual(cfg.smooth, 1)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$FASTMIPS"), 0)
        self.assertEqual(cfg.fast_mips, 1)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$NOIGR"), 0)
        self.assertEqual(cfg.no_igr, 1)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$NOBOOT"), 0)
        self.assertEqual(cfg.no_boot, 1)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$XPOS_-15"), 0)
        self.assertEqual(cfg.x_offset, -15)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$YPOS_20"), 0)
        self.assertEqual(cfg.y_offset, 20)

        # Modes
        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$COMPATIBILITY_0x02"), 0)
        self.assertTrue(cfg.compat_modes & (1 << 1))

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"MODE 4"), 0)
        self.assertTrue(cfg.compat_modes & (1 << 3))

        # Only dollar-prefixed codes are enabled; bare codes remain disabled.
        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"8009A120 0004"), 0)
        self.assertEqual(cfg.cheat_count, 0)
        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$8009A120 0004"), 0)
        self.assertEqual(cfg.cheat_count, 1)
        self.assertEqual(cfg.cheats[0].address, 0x09A120)
        self.assertEqual(cfg.cheats[0].value, 0x0004)
        self.assertEqual(cfg.cheats[0].type, 0x80)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$8009A122 0005"), 0)
        self.assertEqual(cfg.cheat_count, 2)
        self.assertEqual(cfg.cheats[1].address, 0x09A122)
        self.assertEqual(cfg.cheats[1].value, 0x0005)
        self.assertEqual(cfg.cheats[1].type, 0x80)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$3009A124 0012"), 0)
        self.assertEqual(cfg.cheat_count, 3)
        self.assertEqual(cfg.cheats[2].type, 0x30)
        self.assertEqual(cfg.cheats[2].value, 0x12)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$1009A126 0034"), 0)
        self.assertEqual(cfg.cheat_count, 4)
        self.assertEqual(cfg.cheats[3].type, 0x10)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$2009A128 0056"), 0)
        self.assertEqual(cfg.cheat_count, 5)
        self.assertEqual(cfg.cheats[4].type, 0x20)

        # Multi-directive line
        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$SAFEMODE $WIDESCREEN $DITHER_OFF"), 0)
        self.assertEqual(cfg.safe_mode, 1)
        self.assertEqual(cfg.widescreen, 1)
        self.assertEqual(cfg.dither_off, 1)

        # Additional video directives and aliases
        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$240p"), 0)
        self.assertEqual(cfg.video_mode, 8)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$FORCEPAL"), 0)
        self.assertEqual(cfg.video_mode, 2)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$FORCENTSC"), 0)
        self.assertEqual(cfg.video_mode, 1)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$VMODE_4"), 0)
        self.assertEqual(cfg.video_mode, 4)

        # Delays and IGR mode
        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$USBDELAY_5"), 0)
        self.assertEqual(cfg.usb_delay, 5)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$IGR2"), 0)
        self.assertEqual(cfg.no_igr, 0)
        self.assertEqual(cfg.igr_type, 2)

        # 32-byte table export and reload
        tbl = (c.c_uint8 * 32)()
        LIB.pops_config_export_table(c.byref(cfg), c.byref(tbl))
        self.assertEqual(tbl[2], 1)   # hdtv_fix
        self.assertEqual(tbl[9], 1)   # mode 2
        self.assertEqual(tbl[11], 1)  # mode 4
        self.assertEqual(tbl[17], 1)  # no_boot ($421)

        cfg2 = PopsConfig()
        LIB.pops_config_init(c.byref(cfg2))
        self.assertEqual(LIB.pops_config_load_table(c.byref(cfg2), c.byref(tbl)), 0)
        self.assertEqual(cfg2.hdtv_fix, 1)
        self.assertTrue(cfg2.compat_modes & (1 << 1))
        self.assertTrue(cfg2.compat_modes & (1 << 3))
        self.assertEqual(cfg2.no_boot, 1)

    def test_compat_db_lookup(self):
        count = LIB.pops_compat_db_count()
        self.assertGreater(count, 500)

        # Lookup by normalized serial
        entry_ptr = LIB.pops_compat_db_lookup(b"SCES-01492")  # MediEvil
        self.assertTrue(bool(entry_ptr))
        entry = entry_ptr.contents
        self.assertEqual(entry.serial.decode("ascii"), "SCES-01492")
        self.assertEqual(entry.title.decode("ascii"), "MediEvil")
        self.assertEqual(entry.has_libcrypt, 1)
        self.assertEqual(entry.libcrypt_key, 0xD16A)
        self.assertTrue(entry.default_modes & 0x01)  # Mode 1

        # Resident Evil 3 (SLES-02530)
        entry_re3 = LIB.pops_compat_db_lookup(b"SLES-02530")
        self.assertTrue(bool(entry_re3))
        self.assertEqual(entry_re3.contents.has_libcrypt, 1)
        self.assertEqual(entry_re3.contents.libcrypt_key, 0x7C23)

        # Lookup by raw PS1 serial
        entry_ptr2 = LIB.pops_compat_db_lookup(b"SCES_014.92")
        self.assertTrue(bool(entry_ptr2))
        self.assertEqual(entry_ptr2.contents.serial.decode("ascii"), "SCES-01492")

        # Tekken 3
        entry_tk = LIB.pops_compat_db_lookup(b"SLUS-00402")
        self.assertTrue(bool(entry_tk))
        self.assertTrue(entry_tk.contents.default_modes & 0x02)  # Mode 2

    def test_modes_and_patches_application(self):
        core_size = 0x303000
        buf = bytearray(core_size)
        core_ptr = (c.c_uint8 * core_size).from_buffer(buf)

        # Original dispatcher modes 1/2/7: seed pristine guard instructions.
        for offset, value in ((0x10318, 0x8f828228), (0x1032c, 0x1443fffa),
                              (0x83c, 0x0441000a), (0x85c, 0x1000fffa),
                              (0xde9c, 0x0c0836ee)):
            struct.pack_into('<I', buf, offset, value)
        mask = (1 << 0) | (1 << 1) | (1 << 6)
        self.assertEqual(LIB.pops_apply_compat_modes(core_ptr, core_size, mask), 0)
        self.assertEqual(struct.unpack_from('<I', buf, 0x10318)[0], 0x240322e8)
        self.assertEqual(struct.unpack_from('<I', buf, 0x850)[0], 0xa503c200)
        self.assertEqual(buf[0x1e45c], 0x40)
        before = bytes(buf)
        for unsupported in (1 << 5, 1 << 7, 0xff):
            self.assertLess(LIB.pops_apply_compat_modes(core_ptr, core_size, unsupported), 0)
            self.assertEqual(bytes(buf), before)
        # A guard mismatch leaves every selected site unchanged.
        self.assertLess(LIB.pops_apply_compat_modes(core_ptr, core_size, mask), 0)
        self.assertEqual(bytes(buf), before)

        # Test PAL2NTSC video override
        res = LIB.pops_apply_video_overrides(core_ptr, core_size, 1, 1, -10, 20)
        self.assertEqual(res, 0)
        val_ntsc = buf[0x1AF94]  # 0x0021af94 - 0x00200000
        self.assertEqual(val_ntsc, 3)
        val_vsync = struct.unpack_from("<I", buf, 0x302770)[0]  # 0x00502770 - 0x00200000 = 0x302770
        self.assertEqual(val_vsync, 0x000a6300)

        # Test 240p video override (POPS_VMODE_240P = 8)
        res = LIB.pops_apply_video_overrides(core_ptr, core_size, 8, 0, 0, 0)
        self.assertEqual(res, 0)
        val_240p = struct.unpack_from("<I", buf, 0x002061A0 - 0x00200000)[0]
        self.assertEqual(val_240p, 0x24020000)

        # Test Widescreen patch (0x00205B00)
        res = LIB.pops_apply_widescreen(core_ptr, core_size)
        self.assertEqual(res, 0)
        val_ws = struct.unpack_from("<I", buf, 0x00205B00 - 0x00200000)[0]
        self.assertEqual(val_ws, 0x24020C00)

        # Test Dither disable patch (0x00205D58)
        res = LIB.pops_apply_dither_off(core_ptr, core_size)
        self.assertEqual(res, 0)
        val_dither = struct.unpack_from("<I", buf, 0x00205D58 - 0x00200000)[0]
        self.assertEqual(val_dither, 0x00000000)

        # Test LibCrypt bypass
        res = LIB.pops_apply_libcrypt_bypass(core_ptr, core_size)
        self.assertEqual(res, 0)
        val_lc = struct.unpack_from("<I", buf, 0x0020C1F0 - 0x00200000)[0]
        self.assertEqual(val_lc, 0x00000000)
        val_lcret = struct.unpack_from("<I", buf, 0x0020CFB0 - 0x00200000)[0]
        self.assertEqual(val_lcret, 0x24020000)

        # Test Controller IGR and Disc Swap combo checkers
        igr_active_low = (~(0x0400 | 0x0100 | 0x0800 | 0x0200 | 0x0001 | 0x0008)) & 0xFFFF
        self.assertEqual(LIB.pops_check_igr_combo(0xFFFF), 0)
        self.assertEqual(LIB.pops_check_igr_combo(igr_active_low), 1)

        # Test IGR types (0: disabled, 1: normal, 2: alternate with CROSS)
        self.assertEqual(LIB.pops_check_igr_combo_type(igr_active_low, 0), 0)
        self.assertEqual(LIB.pops_check_igr_combo_type(igr_active_low, 1), 1)
        igr2_active_low = (~(0x0400 | 0x0100 | 0x0800 | 0x0200 | 0x0001 | 0x4000)) & 0xFFFF
        self.assertEqual(LIB.pops_check_igr_combo_type(igr2_active_low, 2), 1)

        swap_active_low = (~(0x0001 | 0x0400 | 0x0800)) & 0xFFFF
        self.assertEqual(LIB.pops_check_disc_swap_combo(0xFFFF), 0)
        self.assertEqual(LIB.pops_check_disc_swap_combo(swap_active_low), 1)

        # Test Subchannel Q generator
        subq = (c.c_uint8 * 12)()
        self.assertEqual(LIB.pops_generate_subq(15, 0x7C23, c.byref(subq)), 0)
        self.assertEqual(subq[0], 0x41)
        self.assertEqual(subq[1], 0x01)
        self.assertEqual(subq[2], 0x01)
        self.assertEqual(subq[10], 0x7C)
        self.assertEqual(subq[11], 0x23)

        # Test GameShark cheat RAM injector with 0xD0..0xD3 and 0xE0..0xE1 conditionals
        ram_size = 0x200000
        ram_buf = bytearray(ram_size)
        ram_ptr = (c.c_uint8 * ram_size).from_buffer(ram_buf)
        cheats_arr = (CheatEntry * 8)(
            CheatEntry(0x0009A120, 0x1234, 0x10),  # write 0x1234 to 0x9A120 (type 0x10)
            CheatEntry(0x0009A120, 0x1234, 0xD0),  # if *(u16 *)0x9A120 == 0x1234:
            CheatEntry(0x0009A124, 0x56, 0x20),    #   write 0x56 to 0x9A124 (type 0x20)
            CheatEntry(0x0009A120, 0x9999, 0xD0),  # if *(u16 *)0x9A120 == 0x9999 (false):
            CheatEntry(0x0009A124, 0xAA, 0x30),    #   write 0xAA (should be skipped!)
            CheatEntry(0x0009A124, 0x56, 0xE0),    # if *(u8 *)0x9A124 == 0x56 (true 8-bit):
            CheatEntry(0x0009A126, 0x77, 0x30),    #   write 0x77 to 0x9A126
            CheatEntry(0x0009A124, 0x56, 0xE1),    # if *(u8 *)0x9A124 != 0x56 (false 8-bit):
        )
        res = LIB.pops_cheat_engine_tick(ram_ptr, cheats_arr, 8)
        self.assertEqual(res, 0)
        self.assertEqual(struct.unpack_from("<H", ram_buf, 0x9A120)[0], 0x1234)
        self.assertEqual(ram_buf[0x9A124], 0x56)
        self.assertEqual(ram_buf[0x9A126], 0x77)

        # Out-of-bounds rejection
        self.assertLess(LIB.pops_apply_compat_modes(core_ptr, 0x10000, 1), 0)

if __name__ == "__main__":
    unittest.main()
