#!/usr/bin/env python3
"""Host tests for launcHER's POPS resident code (common/include/pops_resident.h).

The per-frame logic and the launcher-side install/hook helpers are compiled
natively; the EE image itself is built by CMake. Nothing here has run on a
console."""
import ctypes as c
import errno
import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = 0x0143A000
LIMIT = 0x01460000
CORE = 0x00200000
LUI, ADDIU = 0x0021B184, 0x0021B18C
LUI_PRISTINE, ADDIU_PRISTINE = 0x3C050022, 0x24A5CD68
MAX_CHEATS = 256


class CheatEntry(c.Structure):
    _fields_ = [("address", c.c_uint32), ("value", c.c_uint16), ("type", c.c_uint8)]


class ResidentConfig(c.Structure):
    _fields_ = [
        ("gs_display", c.c_uint64),
        ("flags", c.c_uint32),
        ("pops_vblank", c.c_uint32),
        ("ram_base_ptr", c.c_uint32),
        ("frame", c.c_uint32),
        ("safe_delay", c.c_uint16),
        ("cheat_count", c.c_uint16),
        ("cheats", CheatEntry * MAX_CHEATS),
    ]


class Header(c.Structure):
    _fields_ = [
        ("magic", c.c_uint32), ("version", c.c_uint16), ("header_size", c.c_uint16),
        ("file_size", c.c_uint32), ("image_size", c.c_uint32),
        ("vblank_entry", c.c_uint32), ("config_addr", c.c_uint32),
        ("display_entry", c.c_uint32),
        ("progressive_entry", c.c_uint32),
    ]


def build():
    out = Path(tempfile.mkdtemp())
    lib = out / ("resident.dll" if os.name == "nt" else "resident.so")
    sources = ["common/src/pops_resident.c", "common/src/pops_resident_engine.c",
               "common/src/pops_config.c", "tools/fixtures/pops_config_host_io.c",
               "common/src/pops_compat_db.c", "common/src/pops_modes_patches.c",
               "common/src/pops_external.c", "common/src/pops_vcd.c"]
    subprocess.run(["gcc", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra",
                    "-Dfopen=pops_test_fopen", "-Dfgets=pops_test_fgets",
                    "-Dferror=pops_test_ferror", "-Dfclose=pops_test_fclose",
                    "-I", str(ROOT / "common/include")] +
                   [str(ROOT / s) for s in sources] + ["-o", str(lib)], check=True)
    return c.CDLL(str(lib))


L = build()
L.pops_resident_cheat_pass.argtypes = [c.c_void_p, c.POINTER(CheatEntry), c.c_uint16]
L.pops_resident_cheat_pass.restype = None
L.pops_resident_frame.argtypes = [c.POINTER(ResidentConfig), c.c_void_p]
L.pops_resident_check_image.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(Header)]
L.pops_resident_hook_core.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
L.pops_resident_hook_display.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
L.pops_resident_install.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32, c.c_void_p, c.c_size_t,
                                    c.POINTER(ResidentConfig)]
L.pops_resident_build_config.argtypes = [c.POINTER(ResidentConfig), c.c_void_p]
L.pops_config_init.argtypes = [c.c_void_p]
L.pops_config_parse_line.argtypes = [c.c_void_p, c.c_char_p]
L.pops_config_parse_line.restype = c.c_int


def cheats(*codes):
    arr = (CheatEntry * len(codes))()
    for i, (addr, val) in enumerate(codes):
        arr[i].address = addr & 0x1FFFFF
        arr[i].type = addr >> 24
        arr[i].value = val
    return arr


class CheatPass(unittest.TestCase):
    def run_codes(self, ram, *codes):
        arr = cheats(*codes)
        L.pops_resident_cheat_pass(c.addressof(ram), arr, len(codes))

    def test_writes(self):
        ram = (c.c_uint8 * 0x200000)()
        self.run_codes(ram, (0x80001000, 0xBEEF), (0x30001003, 0x12A5), (0x80000FFF, 0x1234))
        self.assertEqual(bytes(ram[0x1000:0x1004]), bytes([0xEF, 0xBE, 0, 0xA5]))
        # Odd 16-bit address writes the aligned halfword, as before.
        self.assertEqual(bytes(ram[0xFFE:0x1000]), bytes([0x34, 0x12]))

    def test_conditionals_gate_the_next_code(self):
        ram = (c.c_uint8 * 0x200000)()
        struct.pack_into("<H", ram, 0x10, 7)
        ram[0x20] = 3
        self.run_codes(ram,
                       (0xD0000010, 7), (0x30000100, 1),    # true: runs
                       (0xD1000010, 7), (0x30000101, 1),    # false: skipped
                       (0xD2000010, 8), (0x30000102, 1),    # 7 < 8: runs
                       (0xD3000010, 8), (0x30000103, 1),    # 7 > 8: skipped
                       (0xE0000020, 3), (0x30000104, 1),
                       (0xE1000020, 3), (0x30000105, 1),
                       (0x30000106, 1))                     # unconditional
        self.assertEqual(list(ram[0x100:0x107]), [1, 0, 1, 0, 1, 0, 1])

    def test_out_of_range_is_skipped(self):
        ram = (c.c_uint8 * 0x200000)()
        self.run_codes(ram, (0x801FFFFF, 0xFFFF), (0xD01FFFFF, 0), (0x30000000, 9))
        self.assertEqual(ram[0x1FFFFE], 0)
        self.assertEqual(ram[0], 0)  # the failed conditional skipped it
        self.run_codes(ram, (0x301FFFFF, 0x55))
        self.assertEqual(ram[0x1FFFFF], 0x55)

    def test_matches_the_launcher_side_engine(self):
        a = (c.c_uint8 * 0x200000)()
        b = (c.c_uint8 * 0x200000)()
        codes = cheats((0x80000010, 0x1111), (0xE0000010, 0x11), (0x30000020, 0x22))
        L.pops_resident_cheat_pass(c.addressof(a), codes, 3)
        L.pops_cheat_engine_tick.argtypes = [c.c_void_p, c.POINTER(CheatEntry), c.c_uint16]
        L.pops_cheat_engine_tick(c.addressof(b), codes, 3)
        self.assertEqual(bytes(a[:0x40]), bytes(b[:0x40]))


class Frame(unittest.TestCase):
    def config(self, *codes, safe=0):
        cfg = ResidentConfig()
        cfg.flags = 1
        cfg.safe_delay = safe
        cfg.cheat_count = len(codes)
        for i, e in enumerate(cheats(*codes)):
            cfg.cheats[i] = e
        return cfg

    def test_runs_every_frame(self):
        ram = (c.c_uint8 * 0x200000)()
        cfg = self.config((0x30000000, 5))
        self.assertEqual(L.pops_resident_frame(c.byref(cfg), c.addressof(ram)), 1)
        ram[0] = 0
        self.assertEqual(L.pops_resident_frame(c.byref(cfg), c.addressof(ram)), 1)
        self.assertEqual(ram[0], 5)
        self.assertEqual(cfg.frame, 2)

    def test_safe_mode_waits(self):
        ram = (c.c_uint8 * 0x200000)()
        cfg = self.config((0x30000000, 5), safe=180)
        for _ in range(180):
            self.assertEqual(L.pops_resident_frame(c.byref(cfg), c.addressof(ram)), 0)
        self.assertEqual(ram[0], 0)
        self.assertEqual(L.pops_resident_frame(c.byref(cfg), c.addressof(ram)), 1)
        self.assertEqual(ram[0], 5)

    def test_no_ram_base_yet_or_disabled(self):
        cfg = self.config((0x30000000, 5))
        self.assertEqual(L.pops_resident_frame(c.byref(cfg), None), 0)
        cfg.flags = 0
        ram = (c.c_uint8 * 0x200000)()
        self.assertEqual(L.pops_resident_frame(c.byref(cfg), c.addressof(ram)), 0)
        self.assertEqual(cfg.frame, 2)

    def test_frame_counter_saturates(self):
        cfg = self.config()
        cfg.frame = 0xFFFFFFFF
        L.pops_resident_frame(c.byref(cfg), None)
        self.assertEqual(cfg.frame, 0xFFFFFFFF)


class BuildConfig(unittest.TestCase):
    def parsed(self, *lines):
        buf = (c.c_uint8 * 0x10000)()
        L.pops_config_init(c.addressof(buf))
        for line in lines:
            self.assertEqual(L.pops_config_parse_line(c.addressof(buf), line.encode()), 0, line)
        return buf

    def test_no_cheats_no_resident(self):
        out = ResidentConfig()
        self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(self.parsed())), 0)

    def test_cheats_and_safe_mode(self):
        out = ResidentConfig()
        cfg = self.parsed("$80012345 00FF", "$D0001000 0001", "$30001001 0002", "$SAFEMODE")
        self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 1)
        self.assertEqual(out.flags, 1)
        self.assertEqual(out.cheat_count, 3)
        self.assertEqual((out.cheats[0].type, out.cheats[0].address, out.cheats[0].value),
                         (0x80, 0x012345, 0xFF))
        self.assertEqual(out.safe_delay, 180)
        self.assertEqual(out.pops_vblank, 0x0021CD68)
        self.assertEqual(out.ram_base_ptr, 0x70003364)

    def test_display_without_cheats_and_combined(self):
        out = ResidentConfig()
        manual = '$DX_10 $DY_20 $MAGH_3 $MAGV_1 $DW_100 $DH_200'
        cfg = self.parsed(manual)
        self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 1)
        self.assertEqual(out.flags, 2)
        self.assertEqual(out.gs_display, (199 << 44) | (99 << 32) | (1 << 27) | (3 << 23) | (20 << 12) | 10)
        self.assertEqual(out.cheat_count, 0)
        cfg = self.parsed(manual, '$30000010 0001')
        self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 1)
        self.assertEqual((out.flags, out.cheat_count), (3, 1))
        cfg = self.parsed('$480p', manual)
        self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 1)
        self.assertEqual(out.flags, 6)
        cfg = self.parsed('$480p $NOPAL $FORCEPAL')
        self.assertEqual(L.pops_resident_build_config(c.byref(out), c.addressof(cfg)), 1)
        self.assertEqual(out.flags, 4)


def core_with(lui=LUI_PRISTINE, addiu=ADDIU_PRISTINE, size=0x1C000):
    core = bytearray(size)
    struct.pack_into("<I", core, LUI - CORE, lui)
    struct.pack_into("<I", core, ADDIU - CORE, addiu)
    return core


class HookCore(unittest.TestCase):
    def hook(self, core, entry, size=None):
        buf = (c.c_uint8 * len(core)).from_buffer(core)
        return L.pops_resident_hook_core(buf, len(core) if size is None else size, entry)

    def words(self, core):
        return struct.unpack_from("<I", core, LUI - CORE)[0], struct.unpack_from("<I", core, ADDIU - CORE)[0]

    def test_patches_both_words(self):
        core = core_with()
        self.assertEqual(self.hook(core, 0x0143A208), 0)
        self.assertEqual(self.words(core), (0x3C050144, 0x24A5A208))
        # lui/addiu sign carry: a low half below 0x8000 needs no carry.
        core = core_with()
        self.assertEqual(self.hook(core, 0x01447F00), 0)
        self.assertEqual(self.words(core), (0x3C050144, 0x24A57F00))
        self.assertEqual(self.hook(core, 0x01447F00), 0)  # idempotent

    def test_refuses_unknown_core_untouched(self):
        core = core_with(addiu=0x24A5CD6C)
        before = bytes(core)
        self.assertEqual(self.hook(core, 0x0143A208), -errno.EILSEQ)
        self.assertEqual(bytes(core), before)

    def test_bounds(self):
        core = core_with()
        self.assertEqual(self.hook(core, 0x0143A208, size=ADDIU - CORE + 3), -errno.ERANGE)
        self.assertEqual(self.hook(core, 0x0143A20A), -errno.EINVAL)
        self.assertEqual(self.hook(core, LIMIT), -errno.EINVAL)
        self.assertEqual(self.hook(core, 0x00200000), -errno.EINVAL)


def image(file_size=0x60, image_size=0x900, entry=BASE + 0x40, config=BASE + 0x60, magic=0x5352484C):
    img = bytearray(file_size)
    struct.pack_into("<IHHIIIIII", img, 0, magic, 3, 32, file_size, image_size, entry, config, BASE + 0x44, BASE + 0x48)
    img[0x40:0x44] = b"\x08\x00\xe0\x03"
    return img


class Install(unittest.TestCase):
    def check(self, img):
        buf = (c.c_uint8 * len(img)).from_buffer(img)
        h = Header()
        return L.pops_resident_check_image(buf, len(img), c.byref(h)), h

    def test_valid_image(self):
        res, h = self.check(image())
        self.assertEqual(res, 0)
        self.assertEqual((h.file_size, h.image_size, h.vblank_entry), (0x60, 0x900, BASE + 0x40))

    def test_rejects_bad_images(self):
        self.assertEqual(self.check(image(magic=0))[0], -errno.EINVAL)
        self.assertEqual(self.check(image(image_size=0x50))[0], -errno.ERANGE)
        self.assertEqual(self.check(image(image_size=LIMIT - BASE + 4))[0], -errno.ERANGE)
        self.assertEqual(self.check(image(entry=BASE + 0x60))[0], -errno.ERANGE)
        self.assertEqual(self.check(image(entry=BASE + 0x42))[0], -errno.ERANGE)
        self.assertEqual(self.check(image(entry=BASE + 0x10))[0], -errno.ERANGE)
        self.assertEqual(self.check(image(config=BASE + 0x900 - 8))[0], -errno.ERANGE)
        self.assertEqual(self.check(image(config=BASE + 0x64))[0], -errno.ERANGE)
        for offset in (24, 28):
            img = image()
            struct.pack_into('<I', img, offset, BASE + len(img))
            self.assertEqual(self.check(img)[0], -errno.ERANGE)
        img = image()
        buf = (c.c_uint8 * len(img)).from_buffer(img)
        self.assertEqual(L.pops_resident_check_image(buf, len(img) - 4, None), -errno.ERANGE)

    def test_install_copies_zeroes_and_configures(self):
        img = image()
        dest = (c.c_uint8 * 0x1000)(*([0xCC] * 0x1000))
        cfg = ResidentConfig()
        cfg.flags, cfg.cheat_count = 1, 1
        cfg.cheats[0].address, cfg.cheats[0].type, cfg.cheats[0].value = 0x10, 0x30, 0x7F
        buf = (c.c_uint8 * len(img)).from_buffer(img)
        self.assertEqual(L.pops_resident_install(dest, 0x1000, BASE, buf, len(img), c.byref(cfg)), 0)
        raw = bytes(dest)
        self.assertEqual(raw[:0x60], bytes(img))
        got = ResidentConfig.from_buffer_copy(raw[0x60:0x60 + c.sizeof(ResidentConfig)])
        self.assertEqual((got.flags, got.cheat_count, got.cheats[0].value), (1, 1, 0x7F))
        end = 0x60 + c.sizeof(ResidentConfig)
        self.assertEqual(raw[end:0x900], bytes(0x900 - end))
        self.assertEqual(raw[0x900:], b"\xcc" * (0x1000 - 0x900))

    def test_install_refuses_short_destination_or_wrong_base(self):
        img = image()
        buf = (c.c_uint8 * len(img)).from_buffer(img)
        dest = (c.c_uint8 * 0x8FF)()
        cfg = ResidentConfig()
        self.assertEqual(L.pops_resident_install(dest, 0x8FF, BASE, buf, len(img), c.byref(cfg)), -errno.ERANGE)
        self.assertEqual(bytes(dest), bytes(0x8FF))
        dest = (c.c_uint8 * 0x1000)()
        self.assertEqual(L.pops_resident_install(dest, 0x1000, BASE + 0x10, buf, len(img), c.byref(cfg)),
                         -errno.EINVAL)


class Layout(unittest.TestCase):
    def test_config_fits_in_the_reserved_range(self):
        self.assertEqual(c.sizeof(Header), 32)
        self.assertLess(c.sizeof(ResidentConfig) + 0x1000, LIMIT - BASE)

    def test_launcher_installs_after_the_last_staging_read(self):
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        hook = src.index("pops_resident_hook_core(")
        reboot = src.index("SifIopRebootBuffer(")
        install = src.index("pops_resident_install(")
        trampoline = src.index("memcpy((void *)POPS_TRAMPOLINE_ADDR")
        self.assertLess(hook, reboot, "hook and checks must fail before the IOP reboot")
        self.assertLess(install, trampoline)
        self.assertGreater(install, reboot)


if __name__ == "__main__":
    unittest.main()
