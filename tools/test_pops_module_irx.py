#!/usr/bin/env python3
"""POPStarter r13's MODULE_0..9.IRX handling (external inputs optional).

Native checks need nothing. With POPSTARTER_TEST_ELF the original's name
check (FUN_008d7024), its start arguments and the order of its post-reset
module starts are decoded from its own instructions and must equal
launcHER's. The source checks pin where handler_pops.c reads, checks and
starts the modules. No console run.
"""
import ctypes as c
import os
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pops_features as F  # noqa: E402  (builds the host library)

LIB = F.compile_shared_library()
LIB.pops_module_irx_name_apply.argtypes = [c.c_void_p, c.c_size_t, c.c_void_p, c.c_size_t,
                                           c.POINTER(c.c_uint)]
LIB.pops_module_irx_name_apply.restype = c.c_int
LIB.pops_module_irx_args.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(c.c_void_p)]
LIB.pops_module_irx_args.restype = c.c_int

CORE = 0x200000
NAME_AT = 0x8E
MAIN_BASE = 0x870000
GP = 0x9B68F0
SIO2MAN, PADMAN = 1, 2

# The original's chain, in order: (name, call site or None, flag kept here).
TABLE = [
    ("sio2man", 0x200324, SIO2MAN),
    ("padman", 0x200358, PADMAN),
    ("Sound_Device_Library", 0x200388, 0),
    ("sdr_driver", 0x2003B8, 0),
    ("dev9", 0x2003F0, 0),
    ("atad", 0x200420, 0),
    ("hdd", 0x200450, 0),
    ("pfs", 0x200480, 0),
    ("IOX/File_Manager", None, 0),
    ("IOX/File_Manager_Rpc", None, 0),
    ("Poweroff_Handler", None, 0),
]
HDD_ARGS = b"-o\x008\x00-n\x00128\x00"
PFS_ARGS = b"-m\x008\x00-o\x008\x00-n\x00127\x00"

HAVE_MAIN = bool(os.environ.get("POPSTARTER_TEST_ELF"))


def irx_named(name, size=0x200):
    data = bytearray(size)
    raw = name.encode()
    data[NAME_AT:NAME_AT + len(raw)] = raw[:max(0, size - NAME_AT)]
    return data


def apply(core, irx, avail=None):
    cbuf = (c.c_uint8 * len(core)).from_buffer(core)
    ibuf = (c.c_uint8 * len(irx)).from_buffer(irx)
    flags = c.c_uint(0)
    res = LIB.pops_module_irx_name_apply(cbuf, len(core), ibuf,
                                         len(irx) if avail is None else avail, c.byref(flags))
    return res, flags.value


def args_of(irx):
    ibuf = (c.c_uint8 * len(irx)).from_buffer(irx)
    out = c.c_void_p()
    n = LIB.pops_module_irx_args(ibuf, len(irx), c.byref(out))
    return n, (c.string_at(out, n) if out.value else None)


def changed(core):
    return [i for i, b in enumerate(core) if b != 0xAA]


def site_bytes(site):
    off = site - CORE
    return [off, off + 1, off + 2, off + 3, off + 10, off + 11]


class Native(unittest.TestCase):
    def test_each_name_pokes_its_site_and_sets_its_flag(self):
        for name, site, flag in TABLE:
            core = bytearray(b"\xAA" * 0x1000)
            res, got = apply(core, irx_named(name))
            self.assertEqual(res, 0, name)
            if name == "IOX/File_Manager_Rpc":
                # "IOX/File_Manager" is checked first and wins (quirk).
                self.assertEqual(changed(core), [], name)
                continue
            self.assertEqual(got, flag, name)
            if site is None:
                self.assertEqual(changed(core), [], name)
            else:
                self.assertEqual(changed(core), site_bytes(site), name)
                off = site - CORE
                self.assertEqual(core[off:off + 4], b"\0\0\0\0")
                self.assertEqual(core[off + 10:off + 12], b"\x00\x10")

    def test_prefix_match_without_terminator(self):
        core = bytearray(b"\xAA" * 0x1000)
        self.assertEqual(apply(core, irx_named("padman_hsync")), (0, PADMAN))
        self.assertEqual(changed(core), site_bytes(0x200358))
        core = bytearray(b"\xAA" * 0x1000)
        self.assertEqual(apply(core, irx_named("pad")), (0, 0))
        self.assertEqual(apply(core, irx_named("Padman")), (0, 0))
        self.assertEqual(changed(core), [])

    def test_bytes_past_the_buffer_read_as_zero(self):
        core = bytearray(b"\xAA" * 0x1000)
        irx = irx_named("sio2man")
        # Only "sio2m" is readable: no match.
        self.assertEqual(apply(core, irx, avail=NAME_AT + 5), (0, 0))
        self.assertEqual(apply(core, irx, avail=NAME_AT + 7), (0, SIO2MAN))

    def test_bounds_and_errors(self):
        last = 0x200480
        self.assertEqual(apply(bytearray(last - CORE + 11), irx_named("pfs"))[0], -34)
        self.assertEqual(apply(bytearray(last - CORE + 12), irx_named("pfs"))[0], 0)
        # A flag-only name needs no core.
        self.assertEqual(apply(bytearray(16), irx_named("Poweroff_Handler")), (0, 0))
        flags = c.c_uint(0)
        self.assertEqual(LIB.pops_module_irx_name_apply(None, 0, None, 0, c.byref(flags)), -22)

    def test_start_arguments(self):
        self.assertEqual(args_of(irx_named("hdd")), (12, HDD_ARGS))
        self.assertEqual(args_of(irx_named("hddX")), (12, HDD_ARGS))
        self.assertEqual(args_of(irx_named("pfs")), (17, PFS_ARGS))
        self.assertEqual(args_of(irx_named("pfsfoo")), (17, PFS_ARGS))
        self.assertEqual(args_of(irx_named("padman")), (0, None))
        self.assertEqual(args_of(irx_named("hd")), (0, None))


def _w(main, addr, n=1):
    off = addr - MAIN_BASE
    return list(struct.unpack("<%dI" % n, main[off:off + 4 * n]))


@unittest.skipUnless(HAVE_MAIN, "needs POPSTARTER_TEST_ELF")
class OriginalCode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from trace_original_pops_io import decode_main
        cls.main = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())

    def decode_chain(self):
        """FUN_008d7024: each entry compares name bytes at NAME_AT+k, then
        pokes (jal 32-bit / 16-bit with a1 = 0x20xxxx) and stores a gp flag,
        and branches to the common exit 0x8d7c28."""
        start, end = 0x8D7024, 0x8D7C28
        words = _w(self.main, start, (end - start) // 4)
        entries, cur = [], {"name": {}, "pokes": [], "values": [], "flag": None}
        offset = value = a0 = None
        for i, w in enumerate(words):
            addr = start + 4 * i
            if w >> 16 == 0x2442:                       # addiu v0, v0, imm
                offset = w & 0xFFFF
            elif w >> 16 == 0x2402:                     # addiu v0, zero, imm
                value = w & 0xFFFF
            elif w >> 16 == 0x1462:                     # bne v1, v0
                cur["name"][offset] = value
            elif w == 0x0000202D:                       # move a0, zero
                a0 = 0
            elif w >> 16 == 0x2404:                     # addiu a0, zero, imm
                a0 = w & 0xFFFF
            elif w >> 16 == 0x34A5:                     # ori a1, a1, imm (delay slot)
                jal = words[i - 1]
                width = {0x8D8C88: 32, 0x8D8C54: 16}[(jal & 0x3FFFFFF) << 2]
                cur["pokes"].append((0x200000 | (w & 0xFFFF), width, a0))
            elif w >> 16 == 0xAF82:                     # sw v0, imm(gp)
                cur["flag"] = w & 0xFFFF
            elif w >> 16 == 0x1000:                     # b
                target = addr + 4 + (((w & 0xFFFF) ^ 0x8000) - 0x8000) * 4
                if target == end:
                    entries.append(cur)
                    cur = {"name": {}, "pokes": [], "values": [], "flag": None}
        entries.append(cur)  # the last entry falls through to the exit
        return entries

    def test_name_chain_equals_launchers_table(self):
        entries = self.decode_chain()
        self.assertEqual(len(entries), len(TABLE))
        for entry, (name, site, flag) in zip(entries, TABLE):
            keys = sorted(entry["name"])
            self.assertEqual(keys, list(range(NAME_AT, NAME_AT + len(keys))), name)
            self.assertEqual("".join(chr(entry["name"][k]) for k in keys), name)
            if site is None:
                self.assertEqual(entry["pokes"], [], name)
            else:
                self.assertEqual(entry["pokes"], [(site, 32, 0), (site + 10, 16, 0x1000)], name)
        flags = {name: e["flag"] for e, (name, _, _) in zip(entries, TABLE)}
        self.assertEqual(flags["sio2man"], 0x3814)
        self.assertEqual(flags["padman"], 0x3824)

    def test_only_sio2man_and_padman_flags_are_read_again(self):
        """lw of the other flags appears nowhere in MAIN."""
        others = (0x3418, 0x38B4, 0x388C, 0x3874, 0x38AC, 0x3440, 0x3428)
        n = len(self.main) // 4
        words = struct.unpack("<%dI" % n, self.main[:4 * n])
        loads = {w & 0xFFFF for w in words if (w >> 21) == ((0x23 << 5) | 28)}  # lw *, imm(gp)
        self.assertIn(0x3814, loads)
        self.assertIn(0x3824, loads)
        for flag in others:
            self.assertNotIn(flag, loads, hex(flag))

    def test_start_arguments_bytes(self):
        off = GP - 0x79A0 - MAIN_BASE
        self.assertEqual(bytes(self.main[off:off + 12]), HDD_ARGS)
        off = GP - 0x7990 - MAIN_BASE
        self.assertEqual(bytes(self.main[off:off + 17]), PFS_ARGS)
        # slot 0's start: 12 bytes for "hdd", 17 for "pfs"
        self.assertEqual(_w(self.main, 0x87B000)[0], 0x2406000C)  # addiu a2, zero, 12
        self.assertEqual(_w(self.main, 0x87B068)[0], 0x24060011)  # addiu a2, zero, 17

    def test_slots_5_to_9_start_after_the_sb_stack(self):
        def size_load(slot):
            return 0x8FC20000 | (0x1174 + 4 * slot)              # lw v0, size(fp)
        sb_gate = 0x87B5F4
        self.assertEqual(_w(self.main, sb_gate, 2), [0x8F833888, 0x24020003])  # 0x3888 == 3
        firsts = []
        for slot in range(10):
            want = size_load(slot)
            lo = 0x87AFA0
            hits = [a for a in range(lo, 0x87C000, 4) if _w(self.main, a)[0] == want]
            firsts.append(hits[0])
        for slot in range(9):
            self.assertLess(firsts[slot], firsts[slot + 1])
        self.assertLess(firsts[4], sb_gate)
        self.assertGreater(firsts[5], sb_gate)
        self.assertEqual(firsts[0], 0x87AFA0)
        self.assertEqual(firsts[5], 0x87B9DC)   # the SB. gate's skip target
        self.assertEqual(_w(self.main, sb_gate + 8)[0] & 0xFFFF,
                         (0x87B9DC - (sb_gate + 12)) // 4)


class Source(unittest.TestCase):
    def test_read_check_and_start_order(self):
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        launch = src.index("int launchPOPS(")
        body = src[launch:]
        read = body.index("res = pops_module_irx_read(popsDir);")
        deps = body.index("res = findPopsDependenciesForMode(vcdPath, popsPath")
        names = body.index("res = pops_module_irx_apply_names(")
        padman = body.index("res = pops_apply_padman(")
        reboot = body.index("res = SifIopRebootBuffer(")
        services = body.index("res = initPopsServices(")
        load_padman = body.index("if (cfg.load_padman && !(moduleIrxFlags & POPS_MODULE_IRX_PADMAN))")
        xx = body.index('pops_start_xx_usb("post-reset", 1)')
        first = body.index("res = pops_start_module_irx(0, 4);")
        smb = body.index("res = pops_load_smb_stack(vcdDir, vmcDir);", services)
        second = body.index("res = pops_start_module_irx(5, POPS_MODULE_IRX_SLOTS - 1);")
        custom = body.index("res = pops_load_custom_modules(vcdDir, vmcDir);")
        self.assertLess(deps, read)
        self.assertLess(read, names)
        self.assertLess(names, padman)
        self.assertLess(padman, reboot)
        self.assertLess(reboot, services)
        self.assertLess(services, load_padman)
        self.assertLess(load_padman, xx)
        self.assertLess(xx, first)
        self.assertLess(first, smb)
        self.assertLess(smb, second)
        self.assertLess(second, custom)

    def test_reader_and_starter_follow_the_original(self):
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        reader = src[src.index("static int pops_module_irx_read("):
                     src.index("static int pops_module_irx_apply_names(")]
        self.assertIn('"%sMODULE_%d.IRX"', reader)
        self.assertIn("if (size < POPS_MODULE_IRX_MIN_SIZE)", reader)
        starter = src[src.index("static int pops_start_module_irx("):
                      src.index("#define POPS_BDMA_NAMES")]
        self.assertIn("if (id <= 0)", starter)
        self.assertIn("pops_module_irx_args(", starter)
        custom = src[src.index("int pops_load_custom_modules("):
                     src.index("static int pops_probe_live_storage(")]
        self.assertNotIn("MODULE_%d", custom)


if __name__ == "__main__":
    unittest.main()
