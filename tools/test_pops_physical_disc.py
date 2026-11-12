#!/usr/bin/env python3
"""POPStarter r13's physical PS1 disc launch: the part that needs no drive.

The original turns to the disc drive when it found no VCD (its flag
gp+0x3410 == 1): the block at 0x8766fc..0x876a40 probes the drive, reads the
region letters from sector 4, pokes Sony's POPS and its own always-live
code, and the built-in list is then matched from sectors 16 and 22.
launcHER's pure part is common/src/pops_physical_disc.c: the planner, the
guarded core stage and the fingerprint builder. Nothing calls them yet.

Native needs nothing: every status and disc type through the planner, the
letters, the stage's writes and every refusal with the core untouched, the
fingerprint layout against the VCD offsets. With POPS_TEST_ELF the same
stage runs on the real core after launchPOPS's earlier stages. With both
reference files and unicorn the original's block runs as shipped
(tools/trace_original_pops_physical.py, the cdvd calls modelled) for every
status, every disc type and seeded drive answers: its call sequence, its
messages, its letters and the whole POPS core afterwards must equal the
planner and the stage, and the bytes it changes inside its own always-live
code must be the four documented writes. The fingerprint function runs as
shipped for every stored fingerprint, from sectors and from a VCD. The
later readers of the flag are run too. The source checks pin that this stage
wires nothing into a launch.

The modelled calls say nothing about what a PS2 drive answers. Nothing here
is a console run.
"""
import ctypes as c
import errno
import os
import random
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

CORE = 0x00200000
CORE_SIZE = 0x00302E60
SECTOR = 2048
OK, FATAL_ACCESS, FATAL_NOT_PS1 = 0, 1, 2
ACCEPTED = (0x10, 0x11, 0x12, 0x13)
MUTED = (0x11, 0x13)
TOK_MUTE_CDDA = 1 << 2

# address: (Sony's value, the value written, width)
CDINIT_ARG = {0x00200794: (0x03A0202D, 0x0000202D, 4)}
MUTE_SITES = {0x0020F0B6: (0x02, 0x00, 1), 0x0020EBF2: (0x03, 0x00, 1),
              0x0020F0E0: (0xAE000014, 0x00000000, 4)}
NAME, NAME_SIZE = 0x004F8000, 0x80

# The original's own always-live code, copied to POPS 0x232790 (0x738 bytes).
LIVE = (0x00232790, 0x00232EC8)
LIVE_WORDS = {0x002328BC: (0x34842950, 0x0000202D),   # ori a0,a0,0x2950 -> daddu a0,zero,zero
              0x002328C8: (0x3C1A0050, 0x1000001F),   # lui k0,0x50 -> b 0x232948
              0x002328CC: (0x241BFCEE, 0x00000000)}   # addiu k1,zero,-0x312 -> nop
LIVE_CLEAR = (0x002328D0, 0x74)                       # the four D-pad disc selections

MSG_ACCESS = "Cannot access (%d)!\n\n"
MSG_NOT_PS1 = "NO PS1 CDROM!\n\n"

HAVE_CORE = bool(os.environ.get("POPS_TEST_ELF"))
HAVE_MAIN = bool(os.environ.get("POPSTARTER_TEST_ELF"))
HAVE_EMU = HAVE_CORE and HAVE_MAIN
if HAVE_EMU:
    try:
        import unicorn  # noqa: F401
        import trace_original_pops_physical as T
        import gen_pops_builtin_db as G
    except Exception:
        HAVE_EMU = False


class Plan(c.Structure):
    _fields_ = [("fatal", c.c_uint8), ("type_asked", c.c_uint8), ("sector_read", c.c_uint8),
                ("mute_cdda", c.c_uint8), ("read_failed", c.c_uint8), ("region", c.c_uint8 * 4),
                ("status", c.c_int32), ("disc_type", c.c_int32)]


def build():
    out = Path(tempfile.mkdtemp())
    lib = out / ("physical_disc.dll" if os.name == "nt" else "physical_disc.so")
    pure = str(ROOT / "common/src/pops_physical_disc.c")
    include = ["-I", str(ROOT / "common/include"), "-I", str(ROOT / "third_party/lzma")]
    # The new file on its own first, with every warning an error.
    subprocess.run(["gcc", "-fsyntax-only", "-std=gnu99", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-Wshadow", "-Wconversion"] + include + [pure], check=True)
    # launchPOPS's staging functions next to it (the list of
    # tools/test_pops_launch_hooks.py), so the stage runs in their order.
    sources = ["common/src/pops_resident.c", "common/src/pops_resident_engine.c",
               "common/src/pops_config.c", "tools/fixtures/pops_config_host_io.c",
               "common/src/pops_compat_db.c", "common/src/pops_modes_patches.c",
               "common/src/pops_builtin_db.c", "common/src/pops_builtin_db_data.c",
               "common/src/pops_external.c", "common/src/pops_vcd.c",
               "common/src/pops_core_patches.c", "common/src/pops_profile.c",
               "common/src/pops_boot_stage.c", "common/src/pops_iop_image.c",
               "third_party/lzma/LzmaDec.c"]
    subprocess.run(["gcc", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra",
                    "-Dfopen=pops_test_fopen", "-Dfgets=pops_test_fgets",
                    "-Dferror=pops_test_ferror", "-Dfclose=pops_test_fclose"] + include +
                   [pure] + [str(ROOT / s) for s in sources] + ["-o", str(lib)], check=True)
    lib = c.CDLL(str(lib))
    lib.pops_physical_disc_plan.argtypes = [c.POINTER(Plan), c.c_int32, c.c_int32, c.c_void_p,
                                            c.c_int]
    lib.pops_physical_disc_message.argtypes = [c.c_int]
    lib.pops_physical_disc_message.restype = c.c_char_p
    lib.pops_physical_disc_stage.argtypes = [c.c_void_p, c.c_size_t, c.c_int]
    lib.pops_physical_disc_clear_name.argtypes = [c.c_void_p, c.c_size_t]
    lib.pops_physical_disc_fingerprint.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p]
    lib.pops_builtin_lookup.argtypes = [c.c_void_p]
    lib.pops_builtin_lookup.restype = c.c_uint16
    lib.pops_builtin_sig_offsets.argtypes = [c.c_uint64, c.c_uint32, c.c_uint32,
                                             c.POINTER(c.c_uint64)]
    lib.pops_builtin_sig_offsets.restype = None
    lib.pops_apply_original_tokens.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
    lib.pops_region_from_licence.argtypes = [c.c_void_p]
    lib.pops_apply_region.argtypes = [c.c_void_p, c.c_size_t, c.c_int, c.c_uint8, c.c_int]
    lib.pops_core_patches_stage.argtypes = [c.c_uint32, c.c_void_p, c.c_size_t, c.c_uint32]
    lib.pops_core_runtime_corrections_stage.argtypes = [c.c_uint32, c.c_void_p, c.c_size_t,
                                                        c.c_uint32]
    lib.pops_resident_hook_gp1.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
    lib.pops_resident_hook_recompiler.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
    lib.pops_apply_always_on_pokes.argtypes = [c.c_void_p, c.c_size_t]
    return lib


LIB = build()


def buf(core):
    return (c.c_uint8 * len(core)).from_buffer(core)


def changed(before, after):
    out = set()
    for off in range(0, len(before), 4096):
        if before[off:off + 4096] != after[off:off + 4096]:
            out.update(CORE + i for i in range(off, min(off + 4096, len(before)))
                       if before[i] != after[i])
    return out


def real_core():
    from trace_original_pops_warmboot import core_image
    core = core_image(os.environ["POPS_TEST_ELF"])
    return core + bytes(max(0, CORE_SIZE - len(core)))


def s32(value):
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


def plan(status, disc_type, sector, read_ok=True):
    p = Plan()
    rc = LIB.pops_physical_disc_plan(c.byref(p), s32(status), s32(disc_type), sector,
                                     1 if read_ok else 0)
    assert rc == 0, rc
    return p


def stage(core, disc_type, core_size=None):
    return LIB.pops_physical_disc_stage(buf(core), len(core) if core_size is None else core_size,
                                        disc_type)


def fingerprint(sector16, sector22):
    out = (c.c_uint8 * 144)()
    assert LIB.pops_physical_disc_fingerprint(sector16, sector22, out) == 0
    return bytes(out)


def get(core, addr, width):
    return int.from_bytes(core[addr - CORE:addr - CORE + width], "little")


def put(core, addr, value, width):
    core[addr - CORE:addr - CORE + width] = value.to_bytes(width, "little")


def sites_for(disc_type):
    out = dict(CDINIT_ARG)
    if disc_type in MUTED:
        out.update(MUTE_SITES)
    return out


def staged(core, disc_type):
    """What the stage must leave: the sites of this disc type rewritten."""
    want = bytearray(core)
    for addr, (_, new, width) in sites_for(disc_type).items():
        put(want, addr, new, width)
    return want


_NOISE = random.Random(0x50534443).randbytes(CORE_SIZE)


def synthetic_core():
    core = bytearray(_NOISE)
    for addr, (shipped, _, width) in {**CDINIT_ARG, **MUTE_SITES}.items():
        put(core, addr, shipped, width)
    return core


def sectors_with(sig, rng):
    """Sectors 16 and 22 that carry one 144-byte fingerprint."""
    s16, s22 = bytearray(rng.randbytes(SECTOR)), bytearray(rng.randbytes(SECTOR))
    s16[40:88], s16[808:840], s22[56:120] = sig[:0x30], sig[0x30:0x50], sig[0x50:]
    return bytes(s16), bytes(s22)


def vcd_with(s16, s22):
    """A raw-sector VCD (1 MiB header, 2,352-byte sectors, data at +24)."""
    vcd = bytearray(0x100000 + 23 * 2352)
    for lba, data in ((16, s16), (22, s22)):
        at = 0x100000 + lba * 2352 + 24
        vcd[at:at + SECTOR] = data
    return bytes(vcd)


class Native(unittest.TestCase):
    def test_refused_status_ends_before_the_disc_type(self):
        for disc_type in list(range(0x20)) + [0xFF, -1]:
            for sector in (None, bytes(range(256)) * 8):
                p = plan(1, disc_type, sector)
                self.assertEqual((p.fatal, p.type_asked, p.sector_read, p.mute_cdda, p.read_failed),
                                 (FATAL_ACCESS, 0, 0, 0, 0))
                self.assertEqual((bytes(p.region), p.status, p.disc_type), (bytes(4), 1, 0))

    def test_only_status_one_is_refused(self):
        refused = [s for s in list(range(-4, 0x200)) + [0x101, 0x10001, 0x7FFFFFFF, -0x80000000]
                   if plan(s, 0x10, None).fatal]
        self.assertEqual(refused, [1])
        self.assertEqual(plan(0x101, 0x10, None).status, 0x101)

    def test_disc_types(self):
        accepted, muted = [], []
        for disc_type in list(range(-4, 0x200)) + [0x110, 0x1010, 0x10010, -0x7FFFFFF0, 0x7FFFFF10]:
            p = plan(0, disc_type, None)
            self.assertEqual((p.type_asked, p.disc_type, p.status), (1, disc_type, 0))
            if p.fatal:
                self.assertEqual((p.fatal, p.sector_read, p.mute_cdda), (FATAL_NOT_PS1, 0, 0))
            else:
                self.assertEqual(p.sector_read, 1)
                accepted.append(disc_type)
                if p.mute_cdda:
                    muted.append(disc_type)
        self.assertEqual((tuple(accepted), tuple(muted)), (ACCEPTED, MUTED))

    def test_letters_are_bytes_60_to_63_whatever_the_read_returned(self):
        rng = random.Random(1)
        for _ in range(200):
            sector = rng.randbytes(SECTOR)
            for read_ok in (True, False):
                p = plan(rng.choice((0, 2, 6, 10)), rng.choice(ACCEPTED), sector, read_ok)
                self.assertEqual(bytes(p.region), sector[60:64])
                self.assertEqual((p.fatal, p.read_failed), (OK, 0 if read_ok else 1))
        # A buffer nothing was stored in: the original's four zero letters.
        for sector in (None, bytes(SECTOR)):
            self.assertEqual(bytes(plan(0, 0x10, sector, False).region), bytes(4))
        # A fatal outcome carries no letters even when a buffer is passed.
        self.assertEqual(bytes(plan(0, 0x14, b"\xAA" * SECTOR).region), bytes(4))

    def test_letters_feed_the_region_lookup(self):
        for text, region in ((b"Euro", 1), (b"Amer", 2), (b"of A", 2), (b"Inc.", 3),
                             (bytes(4), 0), (b"????", 0)):
            sector = bytearray(SECTOR)
            sector[60:64] = text
            p = plan(0, 0x10, bytes(sector))
            self.assertEqual(LIB.pops_region_from_licence(bytes(p.region)), region, text)

    def test_plan_arguments(self):
        self.assertEqual(LIB.pops_physical_disc_plan(None, 0, 0x10, None, 1), -errno.EINVAL)

    def test_messages(self):
        self.assertEqual(LIB.pops_physical_disc_message(FATAL_ACCESS), MSG_ACCESS.encode())
        self.assertEqual(LIB.pops_physical_disc_message(FATAL_NOT_PS1), MSG_NOT_PS1.encode())
        for other in (OK, 3, -1, 255):
            self.assertIsNone(LIB.pops_physical_disc_message(other))

    def test_stage_writes(self):
        for disc_type in ACCEPTED:
            core = synthetic_core()
            before = bytes(core)
            self.assertEqual(stage(core, disc_type), 0)
            self.assertEqual(core, staged(before, disc_type), hex(disc_type))
            want = {a + i for a, (old, new, w) in sites_for(disc_type).items()
                    for i in range(w) if (old >> 8 * i) & 0xFF != (new >> 8 * i) & 0xFF}
            self.assertEqual(changed(before, core), want)
        self.assertEqual(len(changed(synthetic_core(), staged(synthetic_core(), 0x10))), 2)
        self.assertEqual(len(changed(synthetic_core(), staged(synthetic_core(), 0x11))), 6)

    def test_stage_mute_is_the_mute_cdda_command(self):
        for disc_type in MUTED:
            core, other = synthetic_core(), synthetic_core()
            self.assertEqual(stage(core, disc_type), 0)
            self.assertEqual(stage(other, disc_type - 1), 0)
            self.assertNotEqual(core, other)
            self.assertEqual(LIB.pops_apply_original_tokens(buf(other), len(other), TOK_MUTE_CDDA), 0)
            self.assertEqual(core, other)

    def test_stage_refuses_other_disc_types(self):
        core = synthetic_core()
        before = bytes(core)
        for disc_type in list(range(-2, 0x10)) + list(range(0x14, 0x120)) + [0x110, 0x1010, -0x7FFFFFF0]:
            self.assertEqual(stage(core, disc_type), -errno.EINVAL, hex(disc_type))
        self.assertEqual(LIB.pops_physical_disc_stage(None, CORE_SIZE, 0x10), -errno.EINVAL)
        self.assertEqual(core, before)

    def test_stage_refuses_a_short_core(self):
        core = synthetic_core()
        before = bytes(core)
        for disc_type in ACCEPTED:
            need = max(a + w for a, (_, _, w) in sites_for(disc_type).items()) - CORE
            for size in (0, 1, 0x794, 0x797, need - 1):
                self.assertEqual(stage(core, disc_type, size), -errno.ERANGE,
                                 (hex(disc_type), hex(size)))
            self.assertEqual(core, before)
            exact = bytearray(before)
            self.assertEqual(stage(exact, disc_type, need), 0)
            self.assertEqual(exact, staged(before, disc_type))
        self.assertEqual(max(a + w for a, (_, _, w) in MUTE_SITES.items()), 0x20F0E4)

    def test_stage_refuses_a_site_that_is_not_sonys(self):
        for disc_type in ACCEPTED:
            for addr, (shipped, new, width) in sites_for(disc_type).items():
                for value in (new, shipped ^ 1, shipped ^ (0x80 << 8 * (width - 1))):
                    core = synthetic_core()
                    put(core, addr, value, width)
                    before = bytes(core)
                    self.assertEqual(stage(core, disc_type), -errno.EILSEQ, (hex(disc_type), hex(addr)))
                    self.assertEqual(core, before)
        # A disc without CD-DA neither checks nor writes the CD-DA sites.
        for disc_type in (0x10, 0x12):
            core = synthetic_core()
            for addr, (shipped, _, width) in MUTE_SITES.items():
                put(core, addr, shipped ^ 0x55, width)
            before = bytes(core)
            self.assertEqual(stage(core, disc_type), 0)
            self.assertEqual(changed(before, core), {0x200796, 0x200797})

    def test_stage_twice_is_refused(self):
        for disc_type in ACCEPTED:
            core = synthetic_core()
            self.assertEqual(stage(core, disc_type), 0)
            once = bytes(core)
            for again in ACCEPTED:
                self.assertEqual(stage(core, again), -errno.EILSEQ)
            self.assertEqual(core, once)

    def test_clear_name(self):
        core = synthetic_core()
        before = bytes(core)
        self.assertEqual(LIB.pops_physical_disc_clear_name(buf(core), len(core)), 0)
        want = bytearray(before)
        want[NAME - CORE:NAME - CORE + NAME_SIZE] = bytes(NAME_SIZE)
        self.assertEqual(core, want)
        again = bytearray(before)
        need = NAME - CORE + NAME_SIZE
        self.assertEqual(LIB.pops_physical_disc_clear_name(buf(again), need - 1), -errno.ERANGE)
        self.assertEqual(LIB.pops_physical_disc_clear_name(None, len(again)), -errno.EINVAL)
        self.assertEqual(again, before)
        self.assertEqual(LIB.pops_physical_disc_clear_name(buf(again), need), 0)
        self.assertEqual(again, want)

    def test_fingerprint_layout(self):
        rng = random.Random(2)
        for _ in range(50):
            s16, s22 = rng.randbytes(SECTOR), rng.randbytes(SECTOR)
            sig = fingerprint(s16, s22)
            self.assertEqual(sig, s16[40:88] + s16[808:840] + s22[56:120])
            # Only those bytes count.
            a, b = bytearray(rng.randbytes(SECTOR)), bytearray(rng.randbytes(SECTOR))
            a[40:88], a[808:840], b[56:120] = s16[40:88], s16[808:840], s22[56:120]
            self.assertEqual(fingerprint(bytes(a), bytes(b)), sig)
            # A sector that was not read is a zeroed buffer.
            self.assertEqual(fingerprint(None, s22), bytes(0x50) + s22[56:120])
            self.assertEqual(fingerprint(s16, None), s16[40:88] + s16[808:840] + bytes(0x40))
        self.assertEqual(fingerprint(None, None), bytes(144))
        self.assertEqual(LIB.pops_physical_disc_fingerprint(bytes(SECTOR), bytes(SECTOR), None),
                         -errno.EINVAL)

    def test_fingerprint_is_the_vcd_fingerprint(self):
        """The three VCD offsets launchPOPS reads are these sector bytes."""
        at = (c.c_uint64 * 3)()
        LIB.pops_builtin_sig_offsets(0x100000, 2352, 24, at)
        self.assertEqual(list(at), [0x109340, 0x109640, 0x10CA70])
        rng = random.Random(3)
        for _ in range(20):
            s16, s22 = rng.randbytes(SECTOR), rng.randbytes(SECTOR)
            vcd = vcd_with(s16, s22)
            from_vcd = b"".join(vcd[o:o + n] for o, n in zip(at, (0x30, 0x20, 0x40)))
            self.assertEqual(fingerprint(s16, s22), from_vcd)

    def test_unread_sectors_match_no_entry(self):
        self.assertEqual(LIB.pops_builtin_lookup(fingerprint(None, None)), 0)


@unittest.skipUnless(HAVE_CORE, "POPS_TEST_ELF not set")
class RealCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The resident header and the hook entries the other tests use
        # (this import builds that test's own library).
        import test_pops_launch_hooks as H
        cls.H = H
        LIB.pops_resident_hook_guards.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(H.Header)]
        cls.pristine = bytes(real_core())

    def launch_order(self, corrections=0):
        """launchPOPS's stages up to where the physical stage belongs."""
        H = self.H
        core = bytearray(self.pristine)
        rcs = [LIB.pops_core_patches_stage(CORE, buf(core), len(core), (1 << 7) - 1)]
        if corrections:
            rcs.append(LIB.pops_core_runtime_corrections_stage(CORE, buf(core), len(core),
                                                               corrections))
        rcs += [LIB.pops_resident_hook_gp1(buf(core), len(core), H.BASE + 0x80),
                LIB.pops_resident_hook_recompiler(buf(core), len(core), H.RECOMPILER_ENTRY),
                LIB.pops_resident_hook_guards(buf(core), len(core), H.header(H.ENTRIES)),
                LIB.pops_apply_always_on_pokes(buf(core), len(core))]
        self.assertEqual(rcs, [0] * len(rcs))
        return core

    def test_sony_ships_the_expected_values(self):
        for addr, (shipped, _, width) in {**CDINIT_ARG, **MUTE_SITES}.items():
            self.assertEqual(get(self.pristine, addr, width), shipped, hex(addr))
        # jal 0x210540 with the argument in its delay slot.
        self.assertEqual(get(self.pristine, 0x200790, 4), 0x0C000000 | (0x210540 >> 2))
        self.assertEqual(self.pristine[NAME - CORE:NAME - CORE + NAME_SIZE], bytes(NAME_SIZE))

    def test_stage_on_the_pristine_core(self):
        for disc_type in ACCEPTED:
            core = bytearray(self.pristine)
            self.assertEqual(stage(core, disc_type), 0)
            self.assertEqual(core, staged(self.pristine, disc_type))

    def test_stage_after_the_earlier_launch_stages(self):
        """Core patches, each $FIX_* correction, the hooks and the always-on
        pokes leave every site as Sony shipped it."""
        for corrections in (0, 1, 2, 4, 8, 16, 31):
            base = self.launch_order(corrections)
            for addr, (shipped, _, width) in {**CDINIT_ARG, **MUTE_SITES}.items():
                self.assertEqual(get(base, addr, width), shipped, (corrections, hex(addr)))
            for disc_type in ACCEPTED:
                core = bytearray(base)
                self.assertEqual(stage(core, disc_type), 0, (corrections, hex(disc_type)))
                self.assertEqual(core, staged(base, disc_type))

    def test_clear_name_changes_nothing_on_a_launcher_core(self):
        core = self.launch_order()
        before = bytes(core)
        self.assertEqual(LIB.pops_physical_disc_clear_name(buf(core), len(core)), 0)
        self.assertEqual(core, before)


def scan_events(log):
    return [e for e in log if e[0] in ("smod_next", "smem_read")]


def without_scan(log):
    return [e for e in log if e[0] not in ("smod_next", "smem_read")
            and not (e[0] == "memset" and e[3] == 60)]


@unittest.skipUnless(HAVE_EMU, "needs POPSTARTER_TEST_ELF, POPS_TEST_ELF and unicorn")
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.emu = T.Emulator(core=real_core())
        cls.core = cls.emu.core
        cls.buffer = T.GP + T.G_SECTOR
        cls.letters = T.GP + T.G_REGION

    # -- what the block must do, written out from the measurements --------
    def expected_log(self, case):
        quiet = case.get("quiet", 0)
        status, disc_type = s32(case.get("status", 0)), s32(case.get("disc_type", 0x10))
        found = any(m.startswith("cdvd_") for m in case.get("modules", ()))
        log = []

        def say(fmt, arg=None):
            if not quiet:
                log.append(("printf", fmt, arg))
        if found:
            say("    CDVD dvrs loaded... ")
        else:
            say("    Loading CDVD dvrs... ")
            log += [("SifLoadModule", "rom0:CDVDMAN", 0, 0), ("SifLoadModule", "rom0:CDVDFSV", 0, 0)]
        say("Init... ")
        log += [("sceCdInit", 1), ("sceCdSync", 0), ("sceCdStatus",)]
        if status == 1:
            say(MSG_ACCESS, status)
            return log + [("fatal_exit",)], "fatal"
        log.append(("sceCdGetDiskType",))
        if disc_type not in ACCEPTED:
            say(MSG_NOT_PS1)
            if not case.get("mass", 0) and case.get("launch_type", 0) not in (3, 4):
                log.append(("umount_pfs",))
            return log + [("fatal_exit",)], "fatal"
        stored = case.get("sector4") is not None and case.get("read_ok", True)
        log += [("memset", self.buffer, 0, 0x1260), ("sceCdSync", 0), ("sceCdDiskReady", 0),
                ("sceCdSync", 0), ("sceCdRead", 4, 1, self.buffer, "20010000", int(stored)),
                ("sceCdSync", 0), ("memcpy", self.letters, self.buffer + 60, 4),
                ("memset", self.buffer, 0, 0x1260), ("memset", LIVE_CLEAR[0], 0, LIVE_CLEAR[1])]
        say("\n")
        if case.get("auto", 0) in (1, 2, 3, 4):
            log.append(("fingerprint", 0, case["auto"]))
        return log, "end"

    def check(self, case):
        """One run of the block against the planner and the stage."""
        r = self.emu.block(**case)
        label = {k: (v if k != "sector4" else "...") for k, v in case.items()}
        want_log, want_end = self.expected_log(case)
        self.assertEqual(r["end"], want_end, label)
        self.assertEqual(without_scan(r["log"]), want_log, label)
        stored = case.get("sector4") is not None and case.get("read_ok", True)
        seen = case["sector4"] if stored else bytes(SECTOR)   # the buffer as the read left it
        p = plan(case.get("status", 0), case.get("disc_type", 0x10), seen, stored)
        calls = [e[0] for e in r["log"]]
        self.assertEqual(p.fatal != OK, want_end == "fatal", label)
        self.assertEqual(p.type_asked, int("sceCdGetDiskType" in calls), label)
        self.assertEqual(p.sector_read, int("sceCdRead" in calls), label)
        memory = r["memory"]
        self.assertEqual(bytes(p.region), memory[self.letters:self.letters + 4], label)
        if p.fatal:
            message = LIB.pops_physical_disc_message(p.fatal).decode()
            if not case.get("quiet", 0):
                self.assertEqual(r["prints"][-1],
                                 (message, p.status if p.fatal == FATAL_ACCESS else None), label)
            self.assertTrue(r["core"] == self.core, label)
            want = bytearray(self.core)
        else:
            # Sony's POPS: exactly the stage. The original's own code:
            # exactly the four documented writes.
            want = bytearray(self.core)
            self.assertEqual(stage(want, p.disc_type), 0, label)
            self.assertEqual(bool(p.mute_cdda), p.disc_type in MUTED)
            for addr, (_, new) in LIVE_WORDS.items():
                put(want, addr, new, 4)
            want[LIVE_CLEAR[0] - CORE:LIVE_CLEAR[0] - CORE + LIVE_CLEAR[1]] = bytes(LIVE_CLEAR[1])
            self.assertTrue(r["core"] == bytes(want), label)
        # Everything else in memory: the letters, the scan's flag, and the
        # sector buffer back to zero.
        found = any(m.startswith("cdvd_") for m in case.get("modules", ()))
        allowed = set(range(self.letters, self.letters + 4))
        if found:
            allowed.add(T.GP + T.G_CDVD_SEEN)
        touched = {a + i for a, d in r["other_writes"] for i in range(len(d))}
        self.assertLessEqual(touched, allowed, label)
        self.assertEqual(memory[T.GP + T.G_CDVD_SEEN], int(found), label)
        self.assertEqual(memory[self.buffer:self.buffer + 0x1260], bytes(0x1260), label)
        return r, p

    def test_always_live_code_before_the_block(self):
        """The words the block overwrites are the lid-close argument and the
        first D-pad disc selection of the original's own code."""
        for addr, (old, _) in LIVE_WORDS.items():
            self.assertEqual(get(self.core, addr, 4), old, hex(addr))
        self.assertEqual(get(self.core, 0x2328B8, 4), 0x3C040023)                    # lui a0,0x23
        self.assertEqual(get(self.core, 0x2328C0, 4), 0x0C000000 | (0x210540 >> 2))  # jal 0x210540
        self.assertEqual(get(self.core, 0x232948, 4), 0x10000061)                    # b 0x232ad0
        # 0x1000001f at 0x2328c8 lands on that branch.
        self.assertEqual(0x2328C8 + 4 + 0x1F * 4, 0x232948)
        # The four selections store a slot address into the argument's low half.
        stores = [a for a in range(0x2328D0, 0x232948, 4) if get(self.core, a, 4) == 0xA75B28BC]
        self.assertEqual(stores, [0x2328E4, 0x232904, 0x232924, 0x232944])
        slots = [get(self.core, a - 4, 4) & 0xFFFF for a in stores]
        self.assertEqual(slots, [0x2950, 0x29B0, 0x2A10, 0x2A70])
        # The always-live block is the original's, not Sony's.
        pristine = real_core()
        self.assertNotEqual(pristine[LIVE[0] - CORE:LIVE[1] - CORE],
                            self.core[LIVE[0] - CORE:LIVE[1] - CORE])
        self.assertEqual(pristine[:LIVE[0] - CORE], self.core[:LIVE[0] - CORE])
        self.assertEqual(pristine[LIVE[1] - CORE:], self.core[LIVE[1] - CORE:])

    def test_every_disc_type(self):
        sector = bytearray(random.Random(4).randbytes(SECTOR))
        sector[60:64] = b"Amer"
        sector = bytes(sector)
        count, accepted = 0, []
        for disc_type in list(range(256)) + [0x110, 0x1010, 0x10010, 0x80000010, 0xFFFFFFFF, 0xFFFFFF10]:
            r, p = self.check(dict(status=0, disc_type=disc_type, sector4=sector))
            count += 1
            if not p.fatal:
                accepted.append(disc_type)
                self.assertEqual(bytes(p.region), b"Amer")
        self.assertEqual(tuple(accepted), ACCEPTED)
        print("Original physical-disc block PASS: %d disc types" % count)

    def test_every_status(self):
        sector = bytes(random.Random(5).randbytes(SECTOR))
        count, refused = 0, []
        for status in list(range(256)) + [0x101, 0x10001, 0x80000001, 0xFFFFFFFF]:
            for disc_type in (0x10, 0x13, 0x14) if status < 8 else (0x10,):
                r, p = self.check(dict(status=status, disc_type=disc_type, sector4=sector))
                count += 1
                if p.fatal == FATAL_ACCESS:
                    refused.append(status)
        self.assertEqual(sorted(set(refused)), [1])
        print("Original physical-disc block PASS: %d status/type pairs" % count)

    def test_seeded_drive_answers(self):
        rng = random.Random(0x44495343)
        names = ["sifman", "sifcmd", "cdvd_driver", "cdvd_ee_driver", "cdvd", "CDVD_x", "xcdvd_",
                 "cdvdman", "atad_driver", "cdvd_", "dev9", ""]
        ends = {"end": 0, "fatal": 0}
        for _ in range(400):
            case = dict(
                status=rng.choice([0, 0, 0, 0, 2, 6, 10, 1, rng.randrange(256), rng.getrandbits(32)]),
                disc_type=rng.choice(list(ACCEPTED) * 3 + [0, 1, 2, 3, 0x14, 0xFC, 0xFD, 0xFE, 0xFF,
                                                           rng.randrange(256), rng.getrandbits(32)]),
                sector4=rng.choice([rng.randbytes(SECTOR), rng.randbytes(SECTOR), None]),
                read_ok=rng.random() < 0.75,
                modules=tuple(rng.choice(names) for _ in range(rng.randrange(6))),
                quiet=rng.randrange(2), launch_type=rng.randrange(5), mass=rng.randrange(2),
                auto=rng.randrange(6), load_result=rng.choice([1, 0, -1, -203]),
                init_result=rng.randrange(2), ready_result=rng.choice([2, 6, 0]))
            r, _ = self.check(case)
            ends[r["end"]] += 1
        self.assertGreater(min(ends.values()), 60)
        print("Original physical-disc block PASS: 400 seeded cases (%d reach POPS, %d fatal)"
              % (ends["end"], ends["fatal"]))

    def test_unchecked_results(self):
        """Nothing the block calls can stop it except the status and the type."""
        sector = bytes(SECTOR)
        for load in (1, 0, -1, -203):
            for init in (0, 1):
                for ready in (0, 2, 6):
                    for read_ok in (True, False):
                        r, p = self.check(dict(disc_type=0x11, sector4=sector, read_ok=read_ok,
                                               load_result=load, init_result=init,
                                               ready_result=ready))
                        self.assertEqual((r["end"], p.fatal), ("end", OK))

    def test_failed_read_gives_four_zero_letters(self):
        sector = bytearray(SECTOR)
        sector[60:64] = b"Euro"
        r, p = self.check(dict(disc_type=0x10, sector4=bytes(sector), read_ok=False))
        self.assertEqual((bytes(p.region), p.read_failed), (bytes(4), 1))
        r, p = self.check(dict(disc_type=0x10, sector4=bytes(sector), read_ok=True))
        self.assertEqual((bytes(p.region), p.read_failed), (b"Euro", 0))

    def test_block_is_skipped_unless_the_flag_is_one_and_no_vcd(self):
        for flag, found in ((0, 0), (2, 0), (0xFFFFFFFF, 0), (1, 1), (1, 2), (0, 1)):
            r = self.emu.block(flag=flag, vcd_found=found, disc_type=0x10, sector4=bytes(SECTOR))
            self.assertEqual((r["end"], r["log"], r["core_writes"], r["other_writes"]),
                             ("end", [], [], []), (flag, found))

    def test_module_scan(self):
        """A loaded module whose name starts "cdvd_" stops the scan and the
        two rom0 modules are not loaded."""
        for modules, found in (((), False), (("sifman", "sifcmd"), False),
                               (("cdvd_driver",), True), (("sifman", "cdvd_ee_driver", "dev9"), True),
                               (("cdvd_", "sifman"), True), (("cdvd", "cdvdman", "CDVD_x", "xcdvd_", ""), False),
                               (("a", "b", "c", "d", "cdvd_x"), True)):
            r, _ = self.check(dict(disc_type=0x10, sector4=bytes(SECTOR), modules=modules))
            read = [e[1] for e in r["log"] if e[0] == "smem_read"]
            stop = next((i for i, m in enumerate(modules) if m.startswith("cdvd_")), None)
            self.assertEqual(read, list(modules if stop is None else modules[:stop + 1]))
            self.assertEqual(any(e[0] == "SifLoadModule" for e in r["log"]), not found)
            walked = [e[1] for e in r["log"] if e[0] == "smod_next"]
            self.assertEqual(walked, list(range(len(read))) + ([None] if stop is None else []))

    def test_fatal_exit_and_the_pfs_unmount(self):
        for launch_type in range(5):
            for mass in (0, 1):
                r, p = self.check(dict(disc_type=0x14, launch_type=launch_type, mass=mass))
                self.assertEqual(p.fatal, FATAL_NOT_PS1)
                self.assertEqual(("umount_pfs",) in r["log"], mass == 0 and launch_type not in (3, 4))
                r, p = self.check(dict(status=1, launch_type=launch_type, mass=mass))
                self.assertEqual(p.fatal, FATAL_ACCESS)
                self.assertNotIn(("umount_pfs",), r["log"])

    def test_letters_reach_the_region_pass(self):
        """The four letters the block stores are the four bytes the original's
        region pass reads (gp+0x3cb0), and launcHER's region pass makes the
        same writes from the planner's letters."""
        from trace_original_pops_display import OriginalDisplay
        original = OriginalDisplay(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
        pristine = bytes(real_core())
        for text, ok, region in ((b"Euro", True, 1), (b"Amer", True, 2), (b"of A", True, 2),
                                 (b"Inc.", True, 3), (b"ABCD", True, 0), (b"Euro", False, 0)):
            sector = bytearray(SECTOR)
            sector[60:64] = text
            r, p = self.check(dict(disc_type=0x10, sector4=bytes(sector), read_ok=ok))
            letters = bytes(p.region)
            self.assertEqual(letters, text if ok else bytes(4))
            self.assertEqual(LIB.pops_region_from_licence(letters), region)
            want = bytearray(pristine)
            for address, value, width in original.region(letters.decode("ascii"), False, False, True):
                put(want, address, value, width)
            core = bytearray(pristine)
            self.assertEqual(LIB.pops_apply_region(buf(core), len(core), region, 0, 0), 0)
            self.assertTrue(core == want, (text, ok))

    def test_fingerprint_of_every_stored_entry(self):
        """Each stored fingerprint, planted in sectors 16 and 22: the original
        dispatches the entry launcHER's lookup names, from the bytes the
        builder returns."""
        rng = random.Random(6)
        sigs = G.signatures(self.emu.main)
        self.assertEqual(len(sigs), 607)
        first = {}
        for ident, sig in sigs:
            first.setdefault(sig, ident)
        vcd_runs = 0
        for index, (_, sig) in enumerate(sigs):
            s16, s22 = sectors_with(sig, rng)
            built = fingerprint(s16, s22)
            self.assertEqual(built, sig)
            ident = LIB.pops_builtin_lookup(built)
            self.assertEqual(ident, first[sig])
            mode = 1 + index % 4
            r = self.emu.fingerprint(sector16=s16, sector22=s22, mode=mode)
            self.assertEqual((r["end"], r["ret"]), ("returned", 1))
            self.assertEqual(r["sig"], built)
            self.assertEqual((r["applied"], r["list_id"]), ([("apply_entry", ident, mode)], ident))
            self.assertEqual([(e[1], e[2]) for e in r["log"] if e[0] == "sceCdRead"], [(16, 1), (22, 1)])
            self.assertEqual(r["core_writes"], [])
            if index % 6 == 0:
                # The same sectors inside a VCD, through both file backends.
                for mass in (0, 1):
                    v = self.emu.fingerprint(flag=0, vcd=vcd_with(s16, s22), mass=mass, mode=mode)
                    seek, read = ("lseek_mass", "read_mass") if mass else ("lseek", "read")
                    self.assertEqual([e for e in v["log"] if e[0] in ("lseek", "lseek_mass")],
                                     [(seek, 3, 0x109340, 0), (seek, 3, 0x109640, 0),
                                      (seek, 3, 0x10CA70, 0)])
                    self.assertEqual([(e[0], e[3], e[4]) for e in v["log"] if e[0] in ("read", "read_mass")],
                                     [(read, 0x30, 0x30), (read, 0x20, 0x20), (read, 0x40, 0x40)])
                    self.assertEqual((v["sig"], v["applied"]), (built, r["applied"]))
                    self.assertFalse(any(e[0].startswith("sceCd") for e in v["log"]))
                    vcd_runs += 1
        print("Original fingerprint PASS: %d stored fingerprints from sectors, %d from a VCD"
              % (len(sigs), vcd_runs))

    def test_fingerprint_of_unknown_and_unread_discs(self):
        rng = random.Random(7)
        for _ in range(40):
            s16, s22 = rng.randbytes(SECTOR), rng.randbytes(SECTOR)
            bad = rng.choice([(), (16,), (22,), (16, 22)])
            built = fingerprint(None if 16 in bad else s16, None if 22 in bad else s22)
            r = self.emu.fingerprint(sector16=s16, sector22=s22, bad_lbas=bad, quiet=0)
            self.assertEqual((r["end"], r["ret"], r["sig"]), ("returned", 1, built))
            self.assertEqual((r["applied"], r["list_id"], LIB.pops_builtin_lookup(built)), ([], 0, 0))
            self.assertEqual(r["prints"], [("\n    Identifying the game...", None), (" Unknown\n", None)])
            self.assertEqual([(e[1], e[5]) for e in r["log"] if e[0] == "sceCdRead"],
                             [(16, int(16 not in bad)), (22, int(22 not in bad))])
        # A flag that is neither 0 nor 1 reads nothing: the chain compares
        # whatever the fresh allocation held.
        r = self.emu.fingerprint(flag=2)
        self.assertEqual([e[0] for e in r["log"]], ["malloc", "memset"])

    def test_later_readers_of_the_flag(self):
        emu = self.emu
        # 0x8774c4: the drive is shut down again before the IOP work.
        for flag in (0, 1, 2, 0xFFFFFFFF):
            r = emu.cdexit(flag)
            self.assertEqual((r["end"], r["log"]), ("end", [("sceCdInit", 5)] if flag == 1 else []))
            self.assertEqual((r["core_writes"], r["other_writes"]), ([], []))
        # 0x878ab4: no partition and no image line, and POPS's name buffer is cleared.
        core = bytearray(self.core)
        core[NAME - CORE:NAME - CORE + NAME_SIZE] = b"N" * NAME_SIZE
        core[0x4F8080 - CORE:0x4F8090 - CORE] = b"/POPS/GAME/\0\0\0\0\0"
        core[0x4F8100 - CORE:0x4F8110 - CORE] = b"/POPS/SLOT0\0\0\0\0\0"
        core = bytes(core)
        for quiet in (0, 1):
            r = emu.banner(flag=1, quiet=quiet, core=core)
            want = bytearray(core)
            self.assertEqual(LIB.pops_physical_disc_clear_name(buf(want), len(want)), 0)
            self.assertTrue(r["core"] == bytes(want))
            self.assertEqual(r["calls"], [("memset", NAME, 0, NAME_SIZE)])
            lines = [fmt for fmt, _ in r["prints"]]
            self.assertEqual(lines, [] if quiet else ["    VMCs              : hdd0:__common:%s\n",
                                                      "    Game resource dir : hdd0:__common:%s\n",
                                                      "\n"])
            r = emu.banner(flag=0, quiet=quiet, core=core)
            self.assertTrue(r["core"] == core)
            self.assertEqual(r["calls"], [])
            if not quiet:
                self.assertEqual([fmt for fmt, _ in r["prints"]][:3],
                                 ["    Game partition    : %s\n", "\n",
                                  "    User VCD image    : pfs0:/%s\n"])
            r = emu.banner(flag=2, quiet=quiet, core=core)
            self.assertEqual((r["log"], r["core_writes"]), ([], []))
        # FUN_008d5cf8: DISCS.TXT is not read at all.
        skipped = ["    D-Pad button assignment (DISCS.TXT) skipped.\n",
                   "    Emulating lid open/close with triangle/square.\n",
                   "    Only for refreshing the physical PS1 CDROM TOC.\n"]
        for quiet in (0, 1):
            r = emu.discs(flag=1, quiet=quiet)
            self.assertEqual(r["end"], "returned")
            self.assertEqual(r["log"], [] if quiet else [("printf", s, None) for s in skipped])
            for flag in (2, 0xFFFFFFFF):
                r = emu.discs(flag=flag, quiet=quiet)
                self.assertEqual((r["end"], r["log"]), ("returned", []))
            r = emu.discs(flag=0, quiet=quiet)
            self.assertIn(("open", "pfs1:/POPS/DISCS.TXT", 1, -2), r["log"])

    def test_the_flag_is_set_by_a_failed_vcd_probe(self):
        """Launch types 1/2 (the partition argv[0] names), type 0 (eleven
        partitions) and type 3 (eleven folders): no VCD leaves the flag at 1,
        a VCD leaves 0 and reads the letters from its offset 0x102514."""
        emu = self.emu
        vcd = bytearray(0x102600)
        vcd[0x102514:0x102518] = b"Inc."
        vcd = bytes(vcd)
        part = "hdd0:PP.GAME"
        r = emu.probe(1, argv0=part.encode(), vcd_path=b"pfs0:/IMAGE0.VCD")
        self.assertEqual((r["end"], r["flag"], r["found"]), ("end", 1, 0))
        self.assertEqual(r["calls"], [("mount", "pfs0:", part, 1, -19)])
        r = emu.probe(1, argv0=part.encode(), vcd_path=b"pfs0:/IMAGE0.VCD", partitions={part})
        self.assertEqual((r["end"], r["flag"], r["found"]), ("end", 1, 0))
        self.assertEqual(r["calls"], [("mount", "pfs0:", part, 1, 0),
                                      ("open", "pfs0:/IMAGE0.VCD", 1, -2), ("close", -2)])
        r = emu.probe(1, argv0=part.encode(), vcd_path=b"pfs0:/IMAGE0.VCD", partitions={part},
                      files={"pfs0:/IMAGE0.VCD": vcd})
        self.assertEqual((r["end"], r["flag"], r["found"]), ("end", 0, 1))
        self.assertEqual(r["calls"][2:4], [("lseek", 3, 0x102514, 0), ("read", 3, self.letters, 4, 4)])
        self.assertEqual(r["memory"][self.letters:self.letters + 4], b"Inc.")
        # Type 0: "hdd0:__.POPS", then "hdd0:__.POPS0" .. "hdd0:__.POPS9".
        ten = ["hdd0:__.POPS"] + ["hdd0:__.POPS%d" % i for i in range(10)]
        argv0 = b"hdd0:__common/POPS/GAME.ELF"
        r = emu.probe(0, argv0=argv0, vcd_path=b"pfs0:/GAME.VCD")
        self.assertEqual((r["end"], r["flag"], r["found"], r["argv0"]), ("end", 1, 0, b"hdd0:__.POPS9"))
        self.assertEqual([e[2] for e in r["calls"] if e[0] == "mount"], ten)
        r = emu.probe(0, argv0=argv0, vcd_path=b"pfs0:/GAME.VCD", partitions=set(ten))
        self.assertEqual((r["flag"], r["found"]), (1, 0))
        self.assertEqual(len([e for e in r["calls"] if e[0] == "open"]), 11)
        r = emu.probe(0, argv0=argv0, vcd_path=b"pfs0:/GAME.VCD", partitions=set(ten),
                      files={("hdd0:__.POPS", "pfs0:/GAME.VCD"): vcd})
        self.assertEqual((r["end"], r["flag"], r["found"], r["argv0"]), ("end", 0, 1, b"hdd0:__.POPS"))
        self.assertEqual(len([e for e in r["calls"] if e[0] == "mount"]), 1)
        r = emu.probe(0, argv0=argv0, vcd_path=b"pfs0:/GAME.VCD", partitions=set(ten),
                      files={("hdd0:__.POPS7", "pfs0:/GAME.VCD"): vcd})
        self.assertEqual((r["end"], r["flag"], r["found"], r["argv0"]), ("end", 0, 1, b"hdd0:__.POPS7"))
        self.assertEqual(r["memory"][self.letters:self.letters + 4], b"Inc.")
        self.assertEqual(r["other_writes"], [(self.letters, b"Inc.")])
        # Type 3 (XX. and SB.): "mass:/POPS/<name>", then "mass:/POPS0/" ..
        # "mass:/POPS9/"; argv[0] becomes the original's fixed partition name.
        folders = ["mass:/POPS/"] + ["mass:/POPS%d/" % i for i in range(10)]
        argv0 = b"mass:/POPS/XX.GAME.ELF"
        r = emu.probe(3, argv0=argv0, vcd_path=b"GAME.VCD")
        self.assertEqual((r["end"], r["flag"], r["found"]), ("end", 1, 0))
        self.assertEqual([e[1] for e in r["calls"] if e[0] == "open_mass"],
                         [f + "GAME.VCD" for f in folders])
        self.assertEqual((r["argv0"], r["path"]), (b"hdd0:PP.POPS-00001", b"mass:/POPS9/GAME.VCD"))
        self.assertEqual(r["core_writes"], [])
        r = emu.probe(3, argv0=argv0, vcd_path=b"GAME.VCD", files={"mass:/POPS/GAME.VCD": vcd})
        self.assertEqual((r["end"], r["flag"], r["found"], r["path"]),
                         ("end", 0, 1, b"mass:/POPS/GAME.VCD"))
        self.assertEqual(r["calls"][1:], [("open_mass", "mass:/POPS/GAME.VCD", 1, 3),
                                          ("lseek_mass", 3, 0x102514, 0),
                                          ("read_mass", 3, self.letters, 4, 4), ("close_mass", 3)])
        r = emu.probe(3, argv0=argv0, vcd_path=b"GAME.VCD", files={"mass:/POPS4/GAME.VCD": vcd})
        self.assertEqual((r["end"], r["flag"], r["path"]), ("end", 0, b"mass:/POPS4/GAME.VCD"))
        self.assertEqual(len([e for e in r["calls"] if e[0] == "open_mass"]), 6)
        self.assertEqual(r["memory"][self.letters:self.letters + 4], b"Inc.")


class Source(unittest.TestCase):
    def setUp(self):
        self.pure = (ROOT / "common/src/pops_physical_disc.c").read_text()
        self.header = (ROOT / "common/include/pops_physical_disc.h").read_text()

    def test_nothing_is_wired_into_a_launch_yet(self):
        """This stage adds functions only: no file a launch runs through
        mentions them, so no launch, PS1 or not, behaves differently."""
        mine = {ROOT / "common/src/pops_physical_disc.c", ROOT / "common/include/pops_physical_disc.h"}
        for folder in ("launcher/src", "launcher/include", "common/src", "common/include"):
            for path in sorted((ROOT / folder).glob("*")):
                if path in mine or path.suffix not in (".c", ".h", ".S", ".ld"):
                    continue
                self.assertNotIn("pops_physical_disc", path.read_text(errors="replace"), path.name)

    def test_a_missing_vcd_still_ends_the_launch(self):
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        body = src[src.index("int launchPOPS("):]
        at = body.index('msg("POPS: Cannot open target VCD: %s\\n", vcdPath);')
        self.assertEqual(body[at:].split(";")[1].strip(), "return -ENOENT")
        # The entry the owner asked to keep.
        self.assertIn('"ata0:/LAUNCHER-TEST-20261013-A/"', src)

    def test_pure_file_does_no_io(self):
        for word in ("#include <stdio.h>", "#include <fcntl.h>", "#include <unistd.h>", "sceCd",
                     "SifLoadModule", "open(", "read(", "printf("):
            self.assertNotIn(word, self.pure, word)
        self.assertIn("pops_apply_original_tokens(core, core_size, POPS_TOK_MUTE_CDDA)", self.pure)
        # Guards before the first store.
        body = self.pure[self.pure.index("int pops_physical_disc_stage("):
                         self.pure.index("int pops_physical_disc_clear_name(")]
        self.assertLess(body.rindex("return -EILSEQ;"), body.index("store_le32("))
        self.assertLess(body.rindex("return -ERANGE;"), body.index("store_le32("))
        self.assertLess(body.index("store_le32("), body.index("pops_apply_original_tokens("))

    def test_build_lists(self):
        cmake = (ROOT / "launcher/CMakeLists.txt").read_text()
        self.assertEqual(cmake.count("../common/src/pops_physical_disc.c"), 1)
        ci = (ROOT / ".github/workflows/build.yml").read_text()
        self.assertEqual(ci.count("run: python tools/test_pops_physical_disc.py"), 1)

    def test_no_reference_bytes_in_the_repository(self):
        """Addresses, single words and two message texts; no tables."""
        self.assertLess(len(self.pure), 7000)
        self.assertLess(self.pure.count("0x"), 40)
        self.assertNotIn("uint8_t pops_physical", self.pure)
        self.assertIn("Not tested on a console.", self.header)


if __name__ == "__main__":
    unittest.main()
