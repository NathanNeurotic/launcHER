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
        ("fast_mips", c.c_uint8),
        ("slow_mips", c.c_uint8),
        ("no_boot", c.c_uint8),
        ("no_igr", c.c_uint8),
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
        str(ROOT / "common/src/pops_compat_db.c"),
        str(ROOT / "common/src/pops_modes_patches.c"),
        str(ROOT / "common/src/pops_vcd.c"),
    ]
    cmd = ["gcc", "-shared", "-fPIC", "-O2", "-I", str(ROOT / "common/include")] + sources + ["-o", str(so_path)]
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
        LIB.pops_apply_throttling.argtypes = [c.c_void_p, c.c_size_t, c.c_uint8, c.c_uint8]
        LIB.pops_apply_throttling.restype = c.c_int
        LIB.pops_apply_bios_shell.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_bios_shell.restype = c.c_int
        LIB.pops_apply_libcrypt_bypass.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_libcrypt_bypass.restype = c.c_int
        LIB.pops_apply_cheats.argtypes = [c.c_void_p, c.POINTER(CheatEntry), c.c_uint16]
        LIB.pops_apply_cheats.restype = c.c_int
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

        # GameShark cheat
        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"8009A120 0004"), 0)
        self.assertEqual(cfg.cheat_count, 1)
        self.assertEqual(cfg.cheats[0].address, 0x09A120)
        self.assertEqual(cfg.cheats[0].value, 0x0004)
        self.assertEqual(cfg.cheats[0].type, 0x80)

        # 32-byte table export and reload
        tbl = (c.c_uint8 * 32)()
        LIB.pops_config_export_table(c.byref(cfg), c.byref(tbl))
        self.assertEqual(tbl[2], 1)   # hdtv_fix
        self.assertEqual(tbl[9], 1)   # mode 2
        self.assertEqual(tbl[11], 1)  # mode 4
        self.assertEqual(tbl[17], 1)  # no_boot ($421)
        self.assertEqual(tbl[18], 0)  # no_igr ($422)

        cfg2 = PopsConfig()
        LIB.pops_config_init(c.byref(cfg2))
        self.assertEqual(LIB.pops_config_load_table(c.byref(cfg2), c.byref(tbl)), 0)
        self.assertEqual(cfg2.hdtv_fix, 1)
        self.assertTrue(cfg2.compat_modes & (1 << 1))
        self.assertTrue(cfg2.compat_modes & (1 << 3))
        self.assertEqual(cfg2.no_boot, 1)
        self.assertEqual(cfg2.no_igr, 1)

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
        self.assertTrue(entry.default_modes & 0x01)  # Mode 1

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

        # Test Mode 1 (0x002148A0 -> NOP), Mode 2 (0x00207EC0 -> NOP), Mode 7 (0x002010A0 -> addiu)
        mask = (1 << 0) | (1 << 1) | (1 << 6)
        res = LIB.pops_apply_compat_modes(core_ptr, core_size, mask)
        self.assertEqual(res, 0)

        # Check Mode 1 at offset 0x002148A0 - 0x00200000 = 0x148A0
        val_m1 = struct.unpack_from("<I", buf, 0x148A0)[0]
        self.assertEqual(val_m1, 0x00000000)

        # Check Mode 2 at offset 0x00207EC0 - 0x00200000 = 0x7EC0
        val_m2 = struct.unpack_from("<I", buf, 0x7EC0)[0]
        self.assertEqual(val_m2, 0x00000000)

        # Check Mode 7 at offset 0x002010A0 - 0x00200000 = 0x10A0
        val_m7 = struct.unpack_from("<I", buf, 0x10A0)[0]
        self.assertEqual(val_m7, 0x24040002)

        # Test PAL2NTSC video override
        res = LIB.pops_apply_video_overrides(core_ptr, core_size, 1, 1, -10, 20)
        self.assertEqual(res, 0)
        val_ntsc = buf[0x1AF94]  # 0x0021af94 - 0x00200000
        self.assertEqual(val_ntsc, 3)
        val_vsync = struct.unpack_from("<I", buf, 0x302770)[0]  # 0x00502770 - 0x00200000 = 0x302770
        self.assertEqual(val_vsync, 0x000a6300)

        # Test LibCrypt bypass
        res = LIB.pops_apply_libcrypt_bypass(core_ptr, core_size)
        self.assertEqual(res, 0)
        val_lc = struct.unpack_from("<I", buf, 0x0020C1F0 - 0x00200000)[0]
        self.assertEqual(val_lc, 0x00000000)
        val_lcret = struct.unpack_from("<I", buf, 0x0020CFB0 - 0x00200000)[0]
        self.assertEqual(val_lcret, 0x24020000)

        # Test GameShark cheat RAM injector
        ram_size = 0x200000
        ram_buf = bytearray(ram_size)
        ram_ptr = (c.c_uint8 * ram_size).from_buffer(ram_buf)
        cheats_arr = (CheatEntry * 2)(
            CheatEntry(0x0009A120, 0x1234, 0x80),
            CheatEntry(0x0009A124, 0x56, 0x30),
        )
        res = LIB.pops_apply_cheats(ram_ptr, cheats_arr, 2)
        self.assertEqual(res, 0)
        self.assertEqual(struct.unpack_from("<H", ram_buf, 0x9A120)[0], 0x1234)
        self.assertEqual(ram_buf[0x9A124], 0x56)

        # Out-of-bounds rejection
        self.assertEqual(LIB.pops_apply_compat_modes(core_ptr, 0x10000, 1), -22) # -EINVAL

if __name__ == "__main__":
    unittest.main()
