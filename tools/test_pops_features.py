#!/usr/bin/env python3
import ctypes as c
import errno
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
        ("no_vmc0", c.c_uint8),
        ("no_vmc1", c.c_uint8),
        ("compat_modes", c.c_uint8),
        ("runtime_corrections", c.c_uint8),
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
        ("image_offset", c.c_uint32),
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
        str(ROOT / "common/src/pops_external.c"),
        str(ROOT / "common/src/pops_vcd.c"),
    ]
    cmd = ["gcc", "-shared", "-fPIC", "-O2", "-Dfopen=pops_test_fopen",
           "-Dfgets=pops_test_fgets", "-Dferror=pops_test_ferror", "-Dfclose=pops_test_fclose",
           "-I", str(ROOT / "common/include")] + sources + ["-o", str(so_path)]
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
        LIB.pops_compat_db_lookup_title.argtypes = [c.c_char_p]
        LIB.pops_compat_db_lookup_title.restype = c.POINTER(PopsCompatEntry)
        LIB.pops_compat_db_count.restype = c.c_size_t
        LIB.pops_apply_compat_modes.argtypes = [c.c_void_p, c.c_size_t, c.c_uint8]
        LIB.pops_apply_compat_modes.restype = c.c_int
        LIB.pops_apply_all_config_patches.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(PopsConfig)]
        LIB.pops_apply_all_config_patches.restype = c.c_int
        LIB.pops_apply_video_overrides.argtypes = [c.c_void_p, c.c_size_t, c.c_uint8, c.c_uint8, c.c_int16, c.c_int16]
        LIB.pops_apply_video_overrides.restype = c.c_int
        LIB.pops_apply_smooth.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_smooth.restype = c.c_int
        LIB.pops_apply_widescreen.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_widescreen.restype = c.c_int
        LIB.pops_apply_dither_off.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_dither_off.restype = c.c_int
        LIB.pops_apply_igr_exit.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_igr_exit.restype = c.c_int
        LIB.pops_apply_iopcd_stack_size.argtypes = [c.c_void_p, c.c_size_t, c.c_uint8]
        LIB.pops_apply_iopcd_stack_size.restype = c.c_int
        LIB.pops_apply_hdd_init_exit.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_hdd_init_exit.restype = c.c_int
        LIB.pops_apply_vmc0_disable.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_vmc0_disable.restype = c.c_int
        LIB.pops_apply_vmc1_disable.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_vmc1_disable.restype = c.c_int
        LIB.pops_apply_slbb_vcd_check_bypass.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_slbb_vcd_check_bypass.restype = c.c_int
        LIB.pops_apply_slbb_vcd_path_redirect.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_slbb_vcd_path_redirect.restype = c.c_int
        LIB.pops_apply_resource_relink.argtypes = [c.c_void_p, c.c_size_t, c.c_int]
        LIB.pops_apply_resource_relink.restype = c.c_int
        LIB.pops_apply_exception_hook.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_exception_hook.restype = c.c_int
        LIB.pops_apply_bios_osd_disable.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_bios_osd_disable.restype = c.c_int
        LIB.pops_apply_bios_osd_enable.argtypes = [c.c_void_p, c.c_size_t]
        LIB.pops_apply_bios_osd_enable.restype = c.c_int
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
        cls.Reader = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_void_p, c.c_size_t)
        cls.Seeker = c.CFUNCTYPE(c.c_int64, c.c_void_p, c.c_int64, c.c_int)
        LIB.pops_vcd_inspect_stream.argtypes = [c.c_void_p, cls.Reader, cls.Seeker, c.POINTER(PopsVcdInfo)]
        LIB.pops_vcd_inspect_stream.restype = c.c_int

    def test_config_patch_preflight_is_atomic(self):
        # A compatibility-mode write is valid in this small buffer, but a
        # separately requested visual patch needs the complete POPS core.
        # Rejection must precede any mode mutation.
        cfg = PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        cfg.compat_modes = 1
        cfg.smooth = 1
        small = bytearray(0x180000)
        struct.pack_into("<I", small, 0x00210318 - 0x00200000, 0x8F828228)
        struct.pack_into("<I", small, 0x0021032C - 0x00200000, 0x1443FFFA)
        buf = (c.c_uint8 * len(small)).from_buffer(small)
        before = bytes(small)
        self.assertLess(LIB.pops_apply_all_config_patches(buf, len(small), c.byref(cfg)), 0)
        self.assertEqual(small, before)

        # PAL/NTSC writes a late word at 0x00502770. Previous code could
        # update earlier mode bytes, ignore the late write error and return 0.
        cfg = PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        cfg.video_mode = 1
        almost = bytearray(0x302000)
        ptr = (c.c_uint8 * len(almost)).from_buffer(almost)
        before = bytes(almost)
        self.assertLess(LIB.pops_apply_video_overrides(ptr, len(almost),
                        1, 0, 0, 0), 0)
        self.assertEqual(almost, before)
        self.assertLess(LIB.pops_apply_all_config_patches(ptr, len(almost),
                        c.byref(cfg)), 0)
        self.assertEqual(almost, before)

        # Reject out-of-range video modes without touching the core.
        cfg.video_mode = 255
        self.assertEqual(LIB.pops_apply_all_config_patches(
            ptr, len(almost), c.byref(cfg)), -errno.ENOTSUP)
        self.assertEqual(almost, before)

        # Mode 6 is accepted, writing 0x0648 at 0x002525b0
        cfg = PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        cfg.compat_modes = 1 << 5
        core_m6 = bytearray(almost)
        struct.pack_into("<H", core_m6, 0x002525b0 - 0x00200000, 0x1bfc)
        buf_m6 = (c.c_uint8 * len(core_m6)).from_buffer(core_m6)
        self.assertEqual(LIB.pops_apply_all_config_patches(buf_m6, len(core_m6), c.byref(cfg)), 0)
        self.assertEqual(struct.unpack_from("<H", core_m6, 0x002525b0 - 0x00200000)[0], 0x0648)

        # Mode 8 remains unsupported and fails closed
        cfg.compat_modes = 1 << 7
        before_m8 = bytes(core_m6)
        self.assertEqual(LIB.pops_apply_all_config_patches(buf_m6, len(core_m6), c.byref(cfg)), -errno.ENOTSUP)
        self.assertEqual(core_m6, before_m8)

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
                    root_rec[25] = 0x02  # directory flag
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
        self.assertEqual(info.image_offset, 0)
        self.assertEqual(info.root_lba, 17)
        self.assertEqual(info.raw_serial.decode("ascii"), "cdrom0:\\SLUS_008.70;1")
        self.assertEqual(info.normalized_serial.decode("ascii"), "SLUS-00870")

        # Real POPStarter/CUE2POPS VCDs prepend a 0x100000-byte TOC header.
        # Both observed header families must leave sector/PVD/CNF addressing
        # relative to the disc payload, not the beginning of the VCD file.
        bare_disc = temp_vcd.read_bytes()
        for marker in (b"kHn ", b"SPOP", b"POPS"):
            toc = bytearray(0x100000)
            toc[0x400:0x404] = marker
            struct.pack_into("<II", toc, 0x408, total_sectors, total_sectors)
            temp_vcd.write_bytes(toc + bare_disc)
            info = PopsVcdInfo()
            self.assertEqual(LIB.pops_vcd_inspect_path(
                str(temp_vcd).encode("utf-8"), c.byref(info)), 0)
            self.assertEqual(info.image_offset, 0x100000)
            self.assertEqual(info.sector_size, 2352)
            self.assertEqual(info.data_offset, 24)
            self.assertEqual(info.raw_serial.decode("ascii"), "cdrom0:\\SLUS_008.70;1")
            self.assertEqual(info.normalized_serial.decode("ascii"), "SLUS-00870")

        toc[0x400:0x404] = b"NONE"
        temp_vcd.write_bytes(toc + bare_disc)
        info = PopsVcdInfo()
        self.assertEqual(LIB.pops_vcd_inspect_path(
            str(temp_vcd).encode("utf-8"), c.byref(info)), 0)
        self.assertEqual(info.image_offset, 0x100000)
        self.assertEqual(info.normalized_serial.decode("ascii"), "SLUS-00870")

        # Neither Sony marker byte order may accept a truncated VCD or
        # misidentify its header as a standalone ISO payload.
        for marker in (b"SPOP", b"POPS"):
            toc[0x400:0x404] = marker
            temp_vcd.write_bytes(toc + bare_disc[:-sector_size])
            info = PopsVcdInfo()
            self.assertNotEqual(LIB.pops_vcd_inspect_path(
                str(temp_vcd).encode('utf-8'), c.byref(info)), 0)
            temp_vcd.write_bytes(toc)
            info = PopsVcdInfo()
            self.assertNotEqual(LIB.pops_vcd_inspect_path(
                str(temp_vcd).encode("utf-8"), c.byref(info)), 0)

        cursor = [0]
        @self.Reader
        def read_in_chunks(user, dst, amount):
            n = min(int(amount), 13, len(bare_disc) - cursor[0])
            if n > 0:
                c.memmove(dst, bare_disc[cursor[0]:cursor[0]+n], n)
                cursor[0] += n
            return n
        @self.Seeker
        def seek_in_memory(user, offset, whence):
            dest = offset if whence == 0 else cursor[0] + offset
            if dest < 0:
                return -1
            cursor[0] = dest
            return dest
        info = PopsVcdInfo()
        self.assertEqual(LIB.pops_vcd_inspect_stream(
            c.c_void_p(1), read_in_chunks, seek_in_memory, c.byref(info)), 0)
        self.assertEqual(info.normalized_serial.decode('ascii'), 'SLUS-00870')

        # A backend may report a nonnegative but *incorrect* seek position
        # (for example a truncated 32-bit offset). Never accept metadata
        # read from a different position, even if its bytes look valid.
        # The reader deliberately returns the real PVD bytes to show that
        # the reported seek result, not the content, must be authoritative.
        for memory_data in (bare_disc, bytes(toc) + bare_disc):
            cursor = [0]

            @self.Reader
            def read_lied_seek(user, dst, amount):
                n = min(int(amount), 13, len(memory_data) - cursor[0])
                if n > 0:
                    c.memmove(dst, memory_data[cursor[0]:cursor[0] + n], n)
                    cursor[0] += n
                return n

            @self.Seeker
            def seek_lied_position(user, offset, whence):
                dest = offset if whence == 0 else cursor[0] + offset
                if dest < 0:
                    return -1
                cursor[0] = dest
                return dest - 1 if dest > 0 else 0

            info = PopsVcdInfo()
            self.assertEqual(LIB.pops_vcd_inspect_stream(
                c.c_void_p(1), read_lied_seek, seek_lied_position, c.byref(info)), -5)

        # Even an *optional* signature probe cannot treat an incorrect
        # nonnegative SEEK_SET result as "marker absent" and then classify
        # different bytes as a bare disc image.
        memory_data = bare_disc
        cursor = [0]

        @self.Reader
        def read_marker_lie(user, dst, amount):
            n = min(int(amount), 13, len(memory_data) - cursor[0])
            if n > 0:
                c.memmove(dst, memory_data[cursor[0]:cursor[0] + n], n)
                cursor[0] += n
            return n

        @self.Seeker
        def seek_marker_lie(user, offset, whence):
            dest = offset if whence == 0 else cursor[0] + offset
            if dest < 0:
                return -1
            cursor[0] = dest
            return 0x3ff if whence == 0 and dest == 0x400 else dest

        info = PopsVcdInfo()
        self.assertEqual(LIB.pops_vcd_inspect_stream(
            c.c_void_p(1), read_marker_lie, seek_marker_lie, c.byref(info)), -5)

        # The recognized container declares 20 sectors, but only 19 exist.
        # A backend that falsely reports success at 0x408 must not cause the
        # inspector to *skip* the sector-count integrity check.
        short_vcd = bytes(toc) + bare_disc[:-sector_size]
        cursor = [0]

        @self.Reader
        def read_bad_toc(user, dst, amount):
            n = min(int(amount), 13, len(short_vcd) - cursor[0])
            if n > 0:
                c.memmove(dst, short_vcd[cursor[0]:cursor[0] + n], n)
                cursor[0] += n
            return n

        @self.Seeker
        def seek_bad_toc(user, offset, whence):
            if whence == 2:
                dest = len(short_vcd) + offset
            elif whence == 0:
                dest = offset
            else:
                dest = cursor[0] + offset
            if dest < 0:
                return -1
            cursor[0] = dest
            return dest - 1 if whence == 0 and dest == 0x408 else dest

        info = PopsVcdInfo()
        self.assertEqual(LIB.pops_vcd_inspect_stream(
            c.c_void_p(1), read_bad_toc, seek_bad_toc, c.byref(info)), -5)

        # A BOOT2 line and commented BOOT assignments are not PS1 boot keys.
        # The BOOT parser must honor line boundaries and exact directive names.
        modified = bytearray(bare_disc)
        cnf_offset = 18 * sector_size + data_offset
        boot_lines = (b"# BOOT = cdrom0:\\\\FAKE_999.99;1\r\n"
                      b"BOOT2 = cdrom0:\\\\WRONG_999.99;1\r\n"
                      b"  boot = cdrom0:\\\\SLUS_008.70;1\r\n")
        modified[cnf_offset:cnf_offset+2048] = boot_lines.ljust(2048, b'\0')
        # Directory record defines a 64-byte SYSTEM.CNF, so extend its extent
        # before testing all three lines.
        struct.pack_into("<I", modified, 17 * sector_size + data_offset + 10, len(boot_lines))
        temp_vcd.write_bytes(modified)
        info = PopsVcdInfo()
        self.assertEqual(LIB.pops_vcd_inspect_path(
            str(temp_vcd).encode("utf-8"), c.byref(info)), 0)
        self.assertEqual(info.normalized_serial.decode("ascii"), "SLUS-00870")

        # Reject short/malformed ISO directory records before reading fields
        # outside their declared bounds, even when the rest of the sector is OK.
        malformed = bytearray(bare_disc)
        malformed[17 * sector_size + data_offset] = 20
        temp_vcd.write_bytes(malformed)
        self.assertEqual(LIB.pops_vcd_inspect_path(
            str(temp_vcd).encode("utf-8"), c.byref(info)), -22)
        malformed[17 * sector_size + data_offset] = 33
        malformed[17 * sector_size + data_offset + 32] = 200
        temp_vcd.write_bytes(malformed)
        self.assertEqual(LIB.pops_vcd_inspect_path(
            str(temp_vcd).encode("utf-8"), c.byref(info)), -22)
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

    def test_unavailable_optional_global_cards_preserve_title_configuration(self):
        LIB.pops_test_set_card_error.argtypes = [c.c_int]
        LIB.pops_test_set_card_read_error.argtypes = [c.c_int]
        LIB.pops_config_discover.argtypes = [c.POINTER(PopsConfig), c.c_char_p, c.c_char_p]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'Game').mkdir()
            (root / 'Game' / 'MODES.TXT').write_text('MODE 2\n')
            try:
                for missing in (errno.ENOENT, errno.ENODEV, errno.ENXIO):
                    LIB.pops_test_set_card_error(missing)
                    cfg = PopsConfig()
                    LIB.pops_config_init(c.byref(cfg))
                    self.assertEqual(LIB.pops_config_discover(c.byref(cfg),
                                     (str(root) + '/').encode(), b'Game'), 0)
                    self.assertEqual(cfg.compat_modes, 2)
                for failure in (errno.EIO, errno.EACCES):
                    LIB.pops_test_set_card_error(failure)
                    cfg = PopsConfig()
                    LIB.pops_config_init(c.byref(cfg))
                    self.assertEqual(LIB.pops_config_discover(c.byref(cfg),
                                     (str(root) + '/').encode(), b'Game'), -failure)
                LIB.pops_test_set_card_error(errno.ENOENT)
                cfg = PopsConfig()
                LIB.pops_config_init(c.byref(cfg))
                self.assertEqual(LIB.pops_config_discover(c.byref(cfg),
                                 b'unavailable:/', b'Game'), -errno.ENODEV)
                for read_failure in (errno.ENODEV, errno.ENXIO, errno.EIO):
                    LIB.pops_test_set_card_read_error(read_failure)
                    cfg = PopsConfig()
                    LIB.pops_config_init(c.byref(cfg))
                    self.assertEqual(LIB.pops_config_discover(c.byref(cfg),
                                     (str(root) + '/').encode(), b'Game'), -read_failure)
            finally:
                LIB.pops_test_set_card_error(errno.ENOENT)
                LIB.pops_test_set_card_read_error(0)

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
            for value in ('X' * 104, 'Shared\nOther', 'Saves:Other'):
                path.write_text(value)
                self.assertLess(LIB.pops_config_load_vmcdir(
                    c.byref(cfg), encoded), 0)
                self.assertEqual(cfg.vmc_dir, b'Keep')
            path.write_text('Shared_Saves\n')
            self.assertEqual(LIB.pops_config_load_vmcdir(c.byref(cfg), encoded), 0)
            self.assertEqual(cfg.vmc_dir, b'Shared_Saves')
            cfg.vmc_dir = b'Keep'
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
        # Runtime core corrections directives
        self.assertEqual(cfg.runtime_corrections, 0)
        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$FIX_TEXTURE_WINDOW"), 0)
        self.assertEqual(cfg.runtime_corrections, 1)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$FIX_GPU_DMA"), 0)
        self.assertEqual(cfg.runtime_corrections, 3)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$FIX_CDDA"), 0)
        self.assertEqual(cfg.runtime_corrections, 7)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$FIX_SPU_RESET"), 0)
        self.assertEqual(cfg.runtime_corrections, 15)

        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$FIX_GTE_RES1"), 0)
        self.assertEqual(cfg.runtime_corrections, 31)

        cfg.runtime_corrections = 0
        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), b"$PSXCORE_FIXES"), 0)
        self.assertEqual(cfg.runtime_corrections, 31)

        # 32-byte table export and reload
        cfg.usb_delay = 5
        cfg.igr_type = 2
        tbl = (c.c_uint8 * 32)()
        LIB.pops_config_export_table(c.byref(cfg), c.byref(tbl))
        self.assertEqual(tbl[2], 1)   # hdtv_fix
        self.assertEqual(tbl[3], 5)   # usb_delay ($413)
        self.assertEqual(tbl[9], 1)   # mode 2
        self.assertEqual(tbl[11], 1)  # mode 4
        self.assertEqual(tbl[17], 1)  # no_boot ($421)
        self.assertEqual(tbl[20], 2)  # igr_type ($424)

        cfg2 = PopsConfig()
        LIB.pops_config_init(c.byref(cfg2))
        self.assertEqual(LIB.pops_config_load_table(c.byref(cfg2), c.byref(tbl)), 0)
        self.assertEqual(cfg2.hdtv_fix, 1)
        self.assertEqual(cfg2.usb_delay, 5)
        self.assertTrue(cfg2.compat_modes & (1 << 1))
        self.assertTrue(cfg2.compat_modes & (1 << 3))
        self.assertEqual(cfg2.no_boot, 1)
        self.assertEqual(cfg2.igr_type, 2)

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

        # Title substring lookup
        entry_tk_title = LIB.pops_compat_db_lookup_title(b"Tekken 3")
        self.assertTrue(bool(entry_tk_title))
        self.assertTrue(entry_tk_title.contents.default_modes & 0x02)

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
        # Unprotected standard track-1 position Q is CRC-protected, and
        # absolute time starts at 00:02:00 when relative LBA = 0.
        self.assertEqual(LIB.pops_generate_subq(0, 0, c.byref(subq)), 0)
        self.assertEqual(bytes(subq), bytes.fromhex("410101000000000002002832"))
        self.assertEqual(LIB.pops_generate_subq(75, 0, c.byref(subq)), 0)
        self.assertEqual(tuple(subq[3:6]), (0x00, 0x01, 0x00))
        self.assertEqual(tuple(subq[7:10]), (0x00, 0x03, 0x00))

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

    def test_novmc_directives(self):
        cfg = PopsConfig()
        LIB.pops_config_init(c.byref(cfg))
        self.assertEqual(cfg.no_vmc0, 0)
        self.assertEqual(cfg.no_vmc1, 0)

        line = b"$NOVMC0\n"
        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), line), 0)
        self.assertEqual(cfg.no_vmc0, 1)

        line = b"$NOVMC1\n"
        self.assertEqual(LIB.pops_config_parse_line(c.byref(cfg), line), 0)
        self.assertEqual(cfg.no_vmc1, 1)

    def test_igr_exit_patch(self):
        buf_size = 0x100000
        buf = bytearray(buf_size)
        ptr = (c.c_uint8 * buf_size).from_buffer(buf)

        # Mismatch guard test
        self.assertEqual(LIB.pops_apply_igr_exit(ptr, buf_size), -errno.EINVAL)

        # Pristine site: 0x0020c0a4 has 0x0c08b44c
        off = 0x0020c0a4 - 0x00200000
        struct.pack_into("<I", buf, off, 0x0c08b44c)
        self.assertEqual(LIB.pops_apply_igr_exit(ptr, buf_size), 0)
        self.assertEqual(struct.unpack_from("<I", buf, off)[0], 0x0c08d8ae)

        # Buffer too small
        self.assertEqual(LIB.pops_apply_igr_exit(ptr, off), -errno.ERANGE)

    def test_iopcd_stack_size_patch(self):
        buf_size = 0x150000
        buf = bytearray(buf_size)
        ptr = (c.c_uint8 * buf_size).from_buffer(buf)

        # Mismatch guard test
        self.assertEqual(LIB.pops_apply_iopcd_stack_size(ptr, buf_size, 0x40), -errno.EINVAL)

        # Pristine site: 0x002fb599 has 0x08 (2 KiB stack)
        off = 0x002fb599 - 0x00200000
        buf[off] = 0x08
        self.assertEqual(LIB.pops_apply_iopcd_stack_size(ptr, buf_size, 0x40), 0)
        self.assertEqual(buf[off], 0x40)

        # Custom stack size
        buf[off] = 0x08
        self.assertEqual(LIB.pops_apply_iopcd_stack_size(ptr, buf_size, 0x20), 0)
        self.assertEqual(buf[off], 0x20)

    def test_hdd_init_exit_patch(self):
        buf_size = 0x10000
        buf = bytearray(buf_size)
        ptr = (c.c_uint8 * buf_size).from_buffer(buf)

        # Mismatch guard test
        self.assertEqual(LIB.pops_apply_hdd_init_exit(ptr, buf_size), -errno.EINVAL)

        # Pristine site: 0x00200766 has 0x1040 (beqz v0)
        off = 0x00200766 - 0x00200000
        struct.pack_into("<H", buf, off, 0x1040)
        self.assertEqual(LIB.pops_apply_hdd_init_exit(ptr, buf_size), 0)
        self.assertEqual(struct.unpack_from("<H", buf, off)[0], 0x1000)

    def test_vmc_disable_patches(self):
        buf_size = 0x20000
        buf = bytearray(buf_size)
        ptr = (c.c_uint8 * buf_size).from_buffer(buf)

        # VMC0 disable: 0x002007b4 has 0x01
        off0 = 0x002007b4 - 0x00200000
        self.assertEqual(LIB.pops_apply_vmc0_disable(ptr, buf_size), -errno.EINVAL)
        buf[off0] = 0x01
        self.assertEqual(LIB.pops_apply_vmc0_disable(ptr, buf_size), 0)
        self.assertEqual(buf[off0], 0x00)

        # VMC1 disable: 0x0020d0e0 has 0x1480ffc1
        off1 = 0x0020d0e0 - 0x00200000
        self.assertEqual(LIB.pops_apply_vmc1_disable(ptr, buf_size), -errno.EINVAL)
        struct.pack_into("<I", buf, off1, 0x1480ffc1)
        self.assertEqual(LIB.pops_apply_vmc1_disable(ptr, buf_size), 0)
        self.assertEqual(struct.unpack_from("<I", buf, off1)[0], 0x24040000)

    def test_slbb_vcd_check_bypass_patch(self):
        buf_size = 0x10000
        buf = bytearray(buf_size)
        ptr = (c.c_uint8 * buf_size).from_buffer(buf)

        # Mismatch guard test
        self.assertEqual(LIB.pops_apply_slbb_vcd_check_bypass(ptr, buf_size), -errno.EINVAL)

        # Pristine sites:
        # 0x00200834 has 0x0c08b520 (JAL 0x0022d480)
        # 0x0020083c has 0x0441000a (bgez v1, +10)
        # 0x0020085c has 0x1000fffa (b -6)
        off_834 = 0x00200834 - 0x00200000
        off_83c = 0x0020083c - 0x00200000
        off_85c = 0x0020085c - 0x00200000
        struct.pack_into("<I", buf, off_834, 0x0c08b520)
        struct.pack_into("<I", buf, off_83c, 0x0441000a)
        struct.pack_into("<I", buf, off_85c, 0x1000fffa)

        self.assertEqual(LIB.pops_apply_slbb_vcd_check_bypass(ptr, buf_size), 0)
        self.assertEqual(struct.unpack_from("<I", buf, off_834)[0], 0x00000000)
        self.assertEqual(struct.unpack_from("<I", buf, off_83c)[0], 0x1000000a)
        self.assertEqual(struct.unpack_from("<I", buf, off_85c)[0], 0x00000000)

        # Compatibility with Mode 2 / Mode 5 pre-patched state
        struct.pack_into("<I", buf, off_834, 0x0c08b520)
        struct.pack_into("<I", buf, off_83c, 0x1000000a)
        struct.pack_into("<I", buf, off_85c, 0x00000000)
        self.assertEqual(LIB.pops_apply_slbb_vcd_check_bypass(ptr, buf_size), 0)
        self.assertEqual(struct.unpack_from("<I", buf, off_834)[0], 0x00000000)

    def test_unported_runtime_patches(self):
        buf_size = 0x300000
        buf = bytearray(buf_size)
        ptr = (c.c_uint8 * buf_size).from_buffer(buf)

        # 1. SLBB VCD path redirect (FUN_008dbd6c)
        res = LIB.pops_apply_slbb_vcd_path_redirect(ptr, buf_size)
        self.assertEqual(res, 0)
        self.assertEqual(buf[0x004ffe8b - 0x00200000], 0x31)
        self.assertEqual(buf[0x004ffe8e - 0x00200000], 0x50)
        self.assertEqual(buf[0x004ffe8f - 0x00200000], 0x4f)
        self.assertEqual(struct.unpack_from("<H", buf, 0x004ffe90 - 0x00200000)[0], 0x5350)

        # 2. Resource relinking (FUN_008db7e4)
        res = LIB.pops_apply_resource_relink(ptr, buf_size, 0)
        self.assertEqual(res, 0)
        self.assertEqual(struct.unpack_from("<H", buf, 0x00200784 - 0x00200000)[0], 0x8000)
        self.assertEqual(struct.unpack_from("<H", buf, 0x0020cf58 - 0x00200000)[0], 0x8080)
        self.assertEqual(struct.unpack_from("<H", buf, 0x0020c920 - 0x00200000)[0], 0x8100)
        target = buf[0x004f8080 - 0x00200000:0x004f8080 - 0x00200000 + 12]
        self.assertEqual(target.split(b"\0")[0], b"pfs1:/POPS/")

        # 3. Exception hook (FUN_008d6da4)
        res = LIB.pops_apply_exception_hook(ptr, buf_size)
        self.assertEqual(res, 0)
        self.assertEqual(struct.unpack_from("<I", buf, 0x00232d08 - 0x00200000)[0], 0x0c518000)

    def test_bios_osd_control_patches(self):
        buf_size = 0x60000
        buf = bytearray(buf_size)
        ptr = (c.c_uint8 * buf_size).from_buffer(buf)

        off = 0x002525b0 - 0x00200000

        # Mismatch guard test
        self.assertEqual(LIB.pops_apply_bios_osd_disable(ptr, buf_size), -errno.EINVAL)
        self.assertEqual(LIB.pops_apply_bios_osd_enable(ptr, buf_size), -errno.EINVAL)

        # Disable OSD (0x1bfc -> 0x0648)
        struct.pack_into("<H", buf, off, 0x1bfc)
        self.assertEqual(LIB.pops_apply_bios_osd_disable(ptr, buf_size), 0)
        self.assertEqual(struct.unpack_from("<H", buf, off)[0], 0x0648)

        # Enable OSD (0x0648 -> 0x1bfc)
        self.assertEqual(LIB.pops_apply_bios_osd_enable(ptr, buf_size), 0)
        self.assertEqual(struct.unpack_from("<H", buf, off)[0], 0x1bfc)

if __name__ == "__main__":
    unittest.main()
