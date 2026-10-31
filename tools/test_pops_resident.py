#!/usr/bin/env python3
"""Host tests for launcHER's POPS resident code (common/include/pops_resident.h).

The per-frame logic and the launcher-side install/hook helpers are compiled
natively; the EE image itself is built by CMake. Nothing here has run on a
console."""
import ctypes as c
import errno
import os
import random
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
        ("pad_override", c.c_uint8),
        ("pad_id", c.c_uint8 * 2),
        ("pad_reserved", c.c_uint8),
        ("cheats", CheatEntry * MAX_CHEATS),
    ]


class Header(c.Structure):
    _fields_ = [
        ("magic", c.c_uint32), ("version", c.c_uint16), ("header_size", c.c_uint16),
        ("file_size", c.c_uint32), ("image_size", c.c_uint32),
        ("vblank_entry", c.c_uint32), ("config_addr", c.c_uint32),
        ("display_entry", c.c_uint32),
        ("progressive_entry", c.c_uint32),
        ("pad_read_entry", c.c_uint32),
        ("pad_read_exit", c.c_uint32),
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
L.pops_resident_pad_ids.argtypes = [c.POINTER(ResidentConfig), c.c_void_p]
L.pops_resident_pad_ids.restype = None
L.pops_resident_d2ls.argtypes = [c.c_void_p, c.c_uint32]
L.pops_resident_d2ls.restype = None
L.pops_resident_hook_pads.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32, c.c_uint32, c.c_uint32]
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
    struct.pack_into("<IHHIIIIIIII", img, 0, magic, 4, 40, file_size, image_size, entry, config,
                     BASE + 0x44, BASE + 0x48, BASE + 0x4C, BASE + 0x50)
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
        for offset in (24, 28, 32, 36):
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


PAD_STATE_SITES = {0x20C648: 0x3C070050, 0x20C64C: 0x24E77000, 0x20C6C8: 0x8CE80034}
PAD_READ_SITES = {0x237798: 0x0080382D, 0x23779C: 0x24030070, 0x2377A0: 0x2404001C,
                  0x23780C: 0x03E00008, 0x237810: 0x27BD0030}
F_PAD_ID, F_D2LS = 1 << 3, 1 << 4


class PadCommands(unittest.TestCase):
    def parsed(self, *lines):
        return BuildConfig.parsed(self, *lines)

    def resident(self, *lines):
        out = ResidentConfig()
        res = L.pops_resident_build_config(c.byref(out), c.addressof(self.parsed(*lines)))
        return res, out

    def test_nopad_and_pad_id(self):
        res, out = self.resident("$NOPAD1")
        self.assertEqual((res, out.flags, out.pad_override, out.pad_id[1]), (1, F_PAD_ID, 2, 1))
        res, out = self.resident("$NOPAD0 $PAD1ID_0X73")
        self.assertEqual((out.pad_override, list(out.pad_id)), (3, [1, 0x73]))
        res, out = self.resident("$NOPAD0", "$PAD0ID_0X5A")  # later command wins
        self.assertEqual((out.pad_override, list(out.pad_id)), (1, [0x5A, 0]))

    def test_malformed_pad_id_is_ignored(self):
        for token in ("$PAD0ID_0X7", "$PAD0ID_0X733", "$PAD0ID_0XG1", "$PAD2ID_0X41", "$NOPAD2"):
            res, out = self.resident(token)
            self.assertEqual((res, out.flags), (0, 0), token)

    def test_d2ls_forces_digital_and_swaps(self):
        res, out = self.resident("$D2LS")
        self.assertEqual((out.flags, out.pad_override, list(out.pad_id)), (F_PAD_ID | F_D2LS, 3, [0x41, 0x41]))

    def test_d2ls_alt_follows_the_original_order(self):
        # Alone: swap only, the real controller ID stays.
        res, out = self.resident("$D2LS_ALT")
        self.assertEqual((out.flags, out.pad_override), (F_D2LS, 0))
        # After $D2LS: the overrides are switched off again.
        res, out = self.resident("$D2LS", "$D2LS_ALT")
        self.assertEqual((out.flags, out.pad_override), (F_D2LS, 0))
        # After $NOPAD0 without $D2LS: the override stays and now reports 0x41.
        res, out = self.resident("$NOPAD0", "$D2LS_ALT")
        self.assertEqual((out.flags, out.pad_override, out.pad_id[0]), (F_PAD_ID | F_D2LS, 1, 0x41))

    def test_pad_ids_write_only_the_selected_ports(self):
        state = (c.c_uint8 * 0x120)(*([0xEE] * 0x120))
        cfg = ResidentConfig()
        cfg.pad_override, cfg.pad_id[0], cfg.pad_id[1] = 2, 0x41, 0x73
        L.pops_resident_pad_ids(c.byref(cfg), state)
        self.assertEqual((state[0x34], state[0x90 + 0x34]), (0xEE, 0x73))
        self.assertEqual(sum(1 for b in state if b != 0xEE), 1)

    def d2ls(self, buttons, lx, ly, right=0, left=0, up=0, down=0, n=20):
        pad = (c.c_uint8 * 20)(0, 0x79, buttons & 0xFF, buttons >> 8, 0x80, 0x80, lx, ly,
                               right, left, up, down)
        L.pops_resident_d2ls(pad, n)
        return list(pad)

    def test_d2ls_stick_drives_the_dpad(self):
        pad = self.d2ls(0xFFFF, 0x80, 0x80)
        self.assertEqual(pad[2:4], [0xFF, 0xFF])  # centred: released
        self.assertEqual(pad[8:12], [0, 0, 0, 0])
        pad = self.d2ls(0xFF0F, 0x80, 0x80)       # real D-pad is replaced
        self.assertEqual(pad[2], 0xFF)
        pad = self.d2ls(0xFFFF, 0x00, 0x00)       # full up-left
        self.assertEqual(pad[2], 0xFF & ~0x10 & ~0x80)
        self.assertEqual(pad[8:12], [0, 0xFE, 0xFE, 0])
        pad = self.d2ls(0xFFFF, 0xFF, 0xFF)       # full down-right
        self.assertEqual(pad[2], 0xFF & ~0x20 & ~0x40)
        self.assertEqual(pad[8:12], [0xFE, 0, 0, 0xFE])
        # Thresholds: a quarter of the travel either way.
        self.assertEqual(self.d2ls(0xFFFF, 0x41, 0x40)[2], 0xFF & ~0x10)
        self.assertEqual(self.d2ls(0xFFFF, 0xBE, 0xBF)[2], 0xFF & ~0x40)
        # Other buttons are untouched.
        self.assertEqual(self.d2ls(0x1234 | 0xF0, 0x80, 0x80)[2:4], [0x34 | 0xF0, 0x12])

    def test_d2ls_dpad_pressure_drives_the_stick(self):
        pad = self.d2ls(0xFFFF, 0x80, 0x80, up=0xFF, left=0x80)
        self.assertEqual((pad[6], pad[7]), (0x7F - 0x40, 0x00))
        pad = self.d2ls(0xFFFF, 0x80, 0x80, up=0xFF, down=0xFF, right=0x02)
        self.assertEqual((pad[6], pad[7]), (0x81, 0xFF))  # down/right win over up/left
        pad = self.d2ls(0xFFFF, 0x10, 0x10)
        self.assertEqual((pad[6], pad[7]), (0x80, 0x80))  # D-pad released: centred

    def test_d2ls_short_readings(self):
        pad = self.d2ls(0xFF0F, 0x00, 0x00, n=4)    # digital mode: untouched
        self.assertEqual(pad[2], 0x0F)
        self.assertEqual(pad[6:8], [0, 0])
        pad = self.d2ls(0xFFFF, 0x00, 0x80, up=0xFF, n=8)  # no pressure data
        self.assertEqual(pad[2], 0xFF & ~0x80)
        self.assertEqual((pad[6], pad[7]), (0x80, 0x80))

    def core(self):
        core = bytearray(0x40000)
        for a, v in {**PAD_STATE_SITES, **PAD_READ_SITES}.items():
            struct.pack_into("<I", core, a - CORE, v)
        return core

    def hook(self, core, flags, entry=BASE + 0x80, ret=BASE + 0x90, size=None):
        buf = (c.c_uint8 * len(core)).from_buffer(core)
        return L.pops_resident_hook_pads(buf, len(core) if size is None else size, flags, entry, ret)

    def test_hook_pads(self):
        core = self.core()
        before = bytes(core)
        self.assertEqual(self.hook(core, F_PAD_ID), 0)
        self.assertEqual(bytes(core), before)  # ID override needs no core write
        self.assertEqual(self.hook(core, F_PAD_ID | F_D2LS), 0)
        self.assertEqual(struct.unpack_from("<I", core, 0x23779C - CORE)[0], 0x08000000 | ((BASE + 0x80) >> 2))
        self.assertEqual(struct.unpack_from("<I", core, 0x23780C - CORE)[0], 0x08000000 | ((BASE + 0x90) >> 2))
        self.assertEqual(self.hook(core, F_D2LS), 0)  # idempotent

    def test_hook_pads_refuses_unknown_core_untouched(self):
        for site in list(PAD_STATE_SITES) + list(PAD_READ_SITES):
            core = self.core()
            struct.pack_into("<I", core, site - CORE, 0)
            before = bytes(core)
            self.assertEqual(self.hook(core, F_D2LS), -errno.EILSEQ, hex(site))
            self.assertEqual(bytes(core), before)
        core = self.core()
        self.assertEqual(self.hook(core, F_D2LS, entry=BASE + 0x82), -errno.EINVAL)
        self.assertEqual(self.hook(core, F_D2LS, ret=LIMIT), -errno.EINVAL)
        self.assertEqual(self.hook(core, F_D2LS, size=0x237810 - CORE), -errno.ERANGE)
        self.assertEqual(self.hook(core, 0, size=16), 0)  # no pad command: nothing checked

    @unittest.skipUnless(os.environ.get("POPS_TEST_ELF"), "optional external Sony core")
    def test_identified_external_core(self):
        import hashlib
        elf = Path(os.environ["POPS_TEST_ELF"]).read_bytes()
        self.assertEqual(hashlib.sha256(elf).hexdigest(),
                         "59df3389c4df88a572daa720b05507c52c34eddfa0031a6fbeec55e0c2d0fcb1")
        core = bytearray(0x302E60)
        at = struct.unpack_from("<I", elf, 28)[0]
        ents, count = struct.unpack_from("<HH", elf, 42)
        for i in range(count):
            kind, off, va, _, fs, _, _, _ = struct.unpack_from("<8I", elf, at + i * ents)
            if kind == 1 and CORE <= va and va + fs <= CORE + len(core):
                core[va - CORE:va - CORE + fs] = elf[off:off + fs]
        for a, v in {**PAD_STATE_SITES, **PAD_READ_SITES}.items():
            self.assertEqual(struct.unpack_from("<I", core, a - CORE)[0], v, hex(a))
        self.assertEqual(self.hook(core, F_PAD_ID | F_D2LS), 0)

    def test_launcher_hooks_vblank_for_pad_ids(self):
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        self.assertIn("POPS_RES_F_CHEATS | POPS_RES_F_PAD_ID", src)
        self.assertLess(src.index("pops_resident_hook_pads("), src.index("SifIopRebootBuffer("))


# Original pad command handlers and the bytes they patch in the code the
# original copies into POPS: per port, a branch whose offset byte is 1 when
# the ID override runs (6 skips it) and the immediate of the ID it stores.
PAD_WINDOWS = {"$NOPAD0": (0x8968D8, 0x896A98), "$NOPAD1": (0x896A98, 0x896C58),
               "$D2LS_ALT": (0x896E30, 0x8970B4), "$D2LS": (0x896C58, 0x896E30),
               "$PAD": (0x897CBC, 0x8982BC)}
PAD_BRANCH, PAD_IMMEDIATE = (0x232CB0, 0x232CCC), (0x232CBC, 0x232CD4)
PAD_SWAP_SITE, PAD_SWAP_JUMP = 0x23779C, 0x0808C7B4


class OriginalPadCommands(unittest.TestCase):
    """Runs the original's own pad command handlers (external MAIN only) and
    compares the state they leave with launcHER's parsed configuration."""

    @unittest.skipUnless(os.environ.get("POPSTARTER_TEST_ELF"), "optional external POPStarter MAIN")
    def test_sequences_match_the_original(self):
        from trace_original_pops_display import _Window
        from trace_original_pops_io import decode_main

        image = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())

        class PadWindow(_Window):
            def __init__(self, lo, hi, command, state):
                super().__init__(image, lo, hi, command)
                self.state = state
                self.memory.update((self.GP + 0x28E0 + i, 0) for i in range(4))
                self.store(self.GP + 0x28E0, 0xF4, 4)

            def service(self, target):
                a0, a1, a2 = self.reg[4:7]
                if target == 0x8D6B74:  # read a core word
                    self.put(2, self.state.get(a0 & 0xFFFFFFFF, 0))
                    return
                if target == 0x918808 and a2 == 0xF4:  # the copied swap routine
                    self.writes.append([a0, None, a2])
                    self.put(2, a0)
                    return
                super().service(target)

        def original(commands):
            state = {PAD_BRANCH[0]: 6, PAD_BRANCH[1]: 6, PAD_IMMEDIATE[0]: 1,
                     PAD_IMMEDIATE[1]: 1, PAD_SWAP_SITE: 0x24030070}
            for command in commands:
                prefix = next(p for p in PAD_WINDOWS if command.upper().startswith(p))
                w = PadWindow(*PAD_WINDOWS[prefix], command, state)
                w.run()
                for address, value, width in w.writes:
                    if value is not None and address in state:
                        state[address] = value
            override = sum(1 << n for n in range(2) if state[PAD_BRANCH[n]] == 1)
            ids = [state[PAD_IMMEDIATE[n]] if override >> n & 1 else None for n in range(2)]
            return override, ids, int(state[PAD_SWAP_SITE] == PAD_SWAP_JUMP)

        tokens = ["$NOPAD0", "$NOPAD1", "$D2LS", "$D2LS_ALT", "$PAD0ID_0X73",
                  "$PAD1ID_0X5A", "$PAD0ID_0XF0", "$PAD1ID_0X12", "$PAD0ID_0XG1", "$PAD0ID_0X7"]
        rng = random.Random(0x5041)
        cases = [[t] for t in tokens] + [[a, b] for a in tokens for b in tokens]
        cases += [rng.sample(tokens, 4) for _ in range(200)]
        for commands in cases:
            cfg = BuildConfig.parsed(self, " ".join(commands))
            out = ResidentConfig()
            L.pops_resident_build_config(c.byref(out), c.addressof(cfg))
            ids = [out.pad_id[n] if out.pad_override >> n & 1 else None for n in range(2)]
            mine = (out.pad_override, ids, int(bool(out.flags & F_D2LS)))
            self.assertEqual(mine, original(commands), commands)
        print("Original pad command sequences PASS: %d" % len(cases))


class Layout(unittest.TestCase):
    def test_config_fits_in_the_reserved_range(self):
        self.assertEqual(c.sizeof(Header), 40)
        self.assertEqual(ResidentConfig.cheats.offset, 32)
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
