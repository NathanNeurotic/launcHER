#!/usr/bin/env python3
"""POPStarter r13's always-on launch changes in launcHER.

POPStarter makes these on every launch, before the built-in list and the
user's commands (its launch function, 0x874780..0x874a18), and edits the
PS1 BIOS shell inside POPS unless a user BIOS.BIN or OSD was loaded
(0x878f94..0x878fc0):
  - its GP1 hook at 0x21a63c (launcHER's: pops_resident_hook_gp1),
  - nine misaligned-read guards (pops_resident_hook_guards, stubs in
    common/src/pops_resident_guards.S),
  - the exit/pad-copy pokes at 0x20c0ac..0x20c0c4 and 0x228d5c
    (pops_apply_always_on_pokes),
  - three BIOS shell edits (pops_apply_bios_shell_edits),
and, as the last thing before it enters POPS, clears the whole scratchpad
and POPS's BSS up to 0x870000, which takes in the start of POPS's heap
(launcHER's trampoline, launcher/src/pops_trampoline.S).

No external input needed: the stub source is assembled here and run against
a model of what each original site did (tools/pops_guard_model.py), and the
C functions are checked on synthetic cores. With POPSTARTER_TEST_ELF the
original's own stubs run against the same model. With POPS_TEST_ELF too, the
original's launch and BIOS blocks run over the real core and launcHER must
change the same bytes (each side's jumps go to its own stubs). With
POPS_RESIDENT_BIN (the image CMake builds) the built stubs must be the
assembled words and pass the model too; with POPS_TRAMPOLINE_BIN (the .text
of the built pops_trampoline.S object) the built trampoline must be the
assembled one. Nothing here has run on a console."""
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pops_guard_model as G  # noqa: E402
import r5900_mini as R  # noqa: E402
from r5900_mini import Machine  # noqa: E402

CORE = 0x00200000
CORE_SIZE = 0x00302E60
BASE, LIMIT = G.BASE, G.LIMIT
MAIN_BASE, GP, MEMCPY = 0x870000, 0x9B68F0, 0x918808
GP1_SITE = 0x0021A63C

POKES = {0x0020C0AC: (0x00000000, 0x0808D8A4), 0x0020C0B0: (0x00000000, 0x3C1B0086),
         0x0020C0B4: (0x00000000, 0x837BA998), 0x0020C0B8: (0x00000000, 0x3C1A0086),
         0x0020C0BC: (0x00000000, 0xA35B3990), 0x0020C0C0: (0x00000000, 0x00000000),
         0x0020C0C4: (0x1000FFFA, 0x08086DA0), 0x00228D5C: (0x08086DA0, 0x0808302C)}
POKE_CONTEXT = {0x0020C0A4: 0x0C08B44C, 0x0020C0A8: 0x24A59708, 0x0020C0C8: 0x00000000,
                0x00228D58: 0xDFBF0000, 0x00228D60: 0x27BD0010, 0x00236290: 0x27BDFFE0}
IGR_EXIT_FIX = 0x0C08D8AE
GP1_CONTEXT = {0x0021A630: 0x5060000B, 0x0021A638: 0x3C030001, 0x0021A640: 0x42000039,
               0x0021A644: 0x0000040F, 0x0021A648: 0x40026000, 0x0021A64C: 0x00431024}


class Header(c.Structure):
    _fields_ = [
        ("magic", c.c_uint32), ("version", c.c_uint16), ("header_size", c.c_uint16),
        ("file_size", c.c_uint32), ("image_size", c.c_uint32),
        ("vblank_entry", c.c_uint32), ("config_addr", c.c_uint32),
        ("display_entry", c.c_uint32), ("progressive_entry", c.c_uint32),
        ("pad_read_entry", c.c_uint32), ("pad_read_exit", c.c_uint32),
        ("gte_scale_entry", c.c_uint32), ("gte_divide_entry", c.c_uint32),
        ("gte_ultra_entry", c.c_uint32), ("gp1_entry", c.c_uint32),
        ("guard_entry", c.c_uint32 * 9),
    ]


def build():
    out = Path(tempfile.mkdtemp())
    lib = out / ("launch_hooks.dll" if os.name == "nt" else "launch_hooks.so")
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
                    "-Dferror=pops_test_ferror", "-Dfclose=pops_test_fclose",
                    "-I", str(ROOT / "common/include"), "-I", str(ROOT / "third_party/lzma")] +
                   [str(ROOT / s) for s in sources] + ["-o", str(lib)], check=True)
    lib = c.CDLL(str(lib))
    lib.pops_resident_hook_guards.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(Header)]
    lib.pops_resident_hook_gp1.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
    lib.pops_apply_always_on_pokes.argtypes = [c.c_void_p, c.c_size_t]
    lib.pops_apply_bios_shell_edits.argtypes = [c.c_void_p, c.c_size_t]
    lib.pops_apply_opcode_pass.argtypes = [c.c_void_p, c.c_size_t]
    lib.pops_core_patches_stage.argtypes = [c.c_uint32, c.c_void_p, c.c_size_t, c.c_uint32]
    lib.pops_resident_check_image.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(Header)]
    return lib


L = build()


def u32(core, addr):
    return struct.unpack_from("<I", core, addr - CORE)[0]


def put32(core, addr, value):
    struct.pack_into("<I", core, addr - CORE, value)


def buf(core):
    return (c.c_uint8 * len(core)).from_buffer(core)


def header(entries):
    h = Header()
    for i, e in enumerate(entries):
        h.guard_entry[i] = e
    return h


_RANDOM = random.Random(0x484F4F4B).randbytes(CORE_SIZE)


def synthetic_core():
    """Random bytes with POPS's words at every site the hooks check."""
    core = bytearray(_RANDOM)
    for site, pristine, nxt, _, _ in G.SITES:
        put32(core, site, pristine)
        put32(core, site + 4, nxt)
    for table in (G.CONTEXT, POKE_CONTEXT, GP1_CONTEXT):
        for a, w in table.items():
            put32(core, a, w)
    for a, (pops, _) in POKES.items():
        put32(core, a, pops)
    put32(core, GP1_SITE, 0)
    return core


ENTRIES = [BASE + 0x100 + 0x20 * i for i in range(9)]


def changed(before, after):
    return {CORE + i for i in range(len(before)) if before[i] != after[i]}


def words_at(addrs):
    return {a & ~3 for a in addrs}


class Guards(unittest.TestCase):
    def test_writes_a_jump_and_a_nop_at_each_site(self):
        core = synthetic_core()
        before = bytes(core)
        self.assertEqual(L.pops_resident_hook_guards(buf(core), len(core), header(ENTRIES)), 0)
        for (site, _, nxt, keep, _), entry in zip(G.SITES, ENTRIES):
            self.assertEqual(u32(core, site), 0x08000000 | (entry >> 2), hex(site))
            self.assertEqual(u32(core, site + 4), nxt if keep else 0, hex(site))
        want = {s[0] for s in G.SITES} | {s[0] + 4 for s in G.SITES if not s[3]}
        self.assertEqual(words_at(changed(before, core)), want)

    def test_idempotent_and_refuses_another_image(self):
        core = synthetic_core()
        self.assertEqual(L.pops_resident_hook_guards(buf(core), len(core), header(ENTRIES)), 0)
        once = bytes(core)
        self.assertEqual(L.pops_resident_hook_guards(buf(core), len(core), header(ENTRIES)), 0)
        self.assertEqual(bytes(core), once)
        other = [e + 4 for e in ENTRIES]
        self.assertEqual(L.pops_resident_hook_guards(buf(core), len(core), header(other)), -errno.EILSEQ)
        self.assertEqual(bytes(core), once)

    def test_checks_every_word_before_writing_any(self):
        targets = [s[0] for s in G.SITES] + [s[0] + 4 for s in G.SITES] + list(G.CONTEXT)
        for addr in targets:
            core = synthetic_core()
            put32(core, addr, u32(core, addr) ^ 0x00010000)
            before = bytes(core)
            self.assertEqual(L.pops_resident_hook_guards(buf(core), len(core), header(ENTRIES)),
                             -errno.EILSEQ, hex(addr))
            self.assertEqual(bytes(core), before, hex(addr))

    def test_rejects_bad_entries_and_short_cores(self):
        core = synthetic_core()
        before = bytes(core)
        for i in range(9):
            for bad in (ENTRIES[i] + 2, BASE - 4, LIMIT, 0x00200000):
                e = list(ENTRIES)
                e[i] = bad
                self.assertEqual(L.pops_resident_hook_guards(buf(core), len(core), header(e)),
                                 -errno.EINVAL, (i, hex(bad)))
        self.assertEqual(L.pops_resident_hook_guards(None, len(core), header(ENTRIES)), -errno.EINVAL)
        self.assertEqual(L.pops_resident_hook_guards(buf(core), len(core), None), -errno.EINVAL)
        need = 0x0021C770 + 4 - CORE
        self.assertEqual(L.pops_resident_hook_guards(buf(core), need - 1, header(ENTRIES)), -errno.ERANGE)
        self.assertEqual(bytes(core), before)
        self.assertEqual(L.pops_resident_hook_guards(buf(core), need, header(ENTRIES)), 0)

    def test_assembled_stubs_do_what_the_original_sites_did(self):
        # The C hook's own words, the stubs as assembled from the source.
        words, symbols = G.assembled_stubs(BASE + 0x400)
        image = b"".join(w.to_bytes(4, "little") for w in words)
        entries = [symbols[s[4]] for s in G.SITES]
        core = synthetic_core()
        self.assertEqual(L.pops_resident_hook_guards(buf(core), len(core), header(entries)), 0)
        hooked = {a: u32(core, a) for a in G.hooked_words(entries)}
        self.assertEqual(hooked, G.hooked_words(entries))
        runs = G.check_stubs(hooked, image, BASE + 0x400, random.Random(0x5354554253))
        self.assertEqual(runs, 9 * 300)

    def test_stub_source_is_built(self):
        cmake = (ROOT / "launcher/CMakeLists.txt").read_text()
        self.assertIn('set(POPS_RESIDENT_GUARDS "${CMAKE_SOURCE_DIR}/common/src/pops_resident_guards.S")',
                      cmake)
        self.assertGreaterEqual(cmake.count("${POPS_RESIDENT_GUARDS}"), 2)  # compiled and a dependency
        engine = (ROOT / "common/src/pops_resident_engine.c").read_text()
        order = [engine.index("(uint32_t)" + s[4]) for s in G.SITES]
        self.assertEqual(order, sorted(order), "header entries in POPS_GUARD_* order")


class Pokes(unittest.TestCase):
    def test_exact_words_and_nothing_else(self):
        core = synthetic_core()
        before = bytes(core)
        self.assertEqual(L.pops_apply_always_on_pokes(buf(core), len(core)), 0)
        for a, (_, new) in POKES.items():
            self.assertEqual(u32(core, a), new, hex(a))
        self.assertEqual(words_at(changed(before, core)), {a for a, (p, n) in POKES.items() if p != n})
        once = bytes(core)
        self.assertEqual(L.pops_apply_always_on_pokes(buf(core), len(core)), 0)
        self.assertEqual(bytes(core), once)

    def test_accepts_launchers_igr_exit_fix(self):
        core = synthetic_core()
        put32(core, 0x0020C0A4, IGR_EXIT_FIX)
        self.assertEqual(L.pops_apply_always_on_pokes(buf(core), len(core)), 0)
        self.assertEqual(u32(core, 0x0020C0A4), IGR_EXIT_FIX)

    def test_checks_before_writing(self):
        for addr in list(POKES) + list(POKE_CONTEXT):
            core = synthetic_core()
            put32(core, addr, u32(core, addr) ^ 0x00400000)
            before = bytes(core)
            self.assertEqual(L.pops_apply_always_on_pokes(buf(core), len(core)), -errno.EILSEQ, hex(addr))
            self.assertEqual(bytes(core), before)
        core = synthetic_core()
        self.assertEqual(L.pops_apply_always_on_pokes(None, len(core)), -errno.EINVAL)
        self.assertEqual(L.pops_apply_always_on_pokes(buf(core), 0x00236290 + 3 - CORE), -errno.ERANGE)

    def test_bios_shell_edits(self):
        core = synthetic_core()
        before = bytes(core)
        self.assertEqual(L.pops_apply_bios_shell_edits(buf(core), len(core)), 0)
        self.assertEqual(core[0x263ED6 - CORE], 0x20)
        self.assertEqual(struct.unpack_from("<H", core, 0x263D56 - CORE)[0], 0x1000)
        self.assertEqual(u32(core, 0x263DB0), 0)
        self.assertLessEqual(changed(before, core), {0x263ED6, 0x263D56, 0x263D57} |
                             set(range(0x263DB0, 0x263DB4)))
        self.assertEqual(L.pops_apply_bios_shell_edits(None, len(core)), -errno.EINVAL)
        self.assertEqual(L.pops_apply_bios_shell_edits(buf(core), 0x263ED6 - CORE), -errno.ERANGE)

    def test_opcode_pass_keeps_every_hook_word(self):
        core = synthetic_core()
        self.assertEqual(L.pops_resident_hook_gp1(buf(core), len(core), BASE + 0x80), 0)
        self.assertEqual(L.pops_resident_hook_guards(buf(core), len(core), header(ENTRIES)), 0)
        self.assertEqual(L.pops_apply_always_on_pokes(buf(core), len(core)), 0)
        hooks = [GP1_SITE] + [s[0] for s in G.SITES] + [s[0] + 4 for s in G.SITES] + list(POKES)
        before = {a: u32(core, a) for a in hooks}
        self.assertGreaterEqual(L.pops_apply_opcode_pass(buf(core), len(core)), 0)
        self.assertEqual({a: u32(core, a) for a in hooks}, before)


def main_image():
    from trace_original_pops_io import decode_main
    return decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())


def real_core():
    from trace_original_pops_warmboot import core_image
    core = core_image(os.environ["POPS_TEST_ELF"])
    return core + bytes(max(0, CORE_SIZE - len(core)))


def run_original_blocks(core):
    """The original's always-on writes over `core`, in its order: the
    0x20c0c4 poke (0x8744a0), the GP1 hook (0x874780) and the guard stubs,
    guards and pokes (0x874850..0x874a20), then the BIOS edits (0x878f94).
    Returns the machine (POPS core at 0x200000, its stubs at 0x143a000)."""
    m = Machine()
    m.write(MAIN_BASE, main_image())
    m.write(CORE, bytes(core))

    def memcpy(mm):
        dst, src, n = mm.lo(4) & 0xFFFFFFFF, mm.lo(5) & 0xFFFFFFFF, mm.lo(6) & 0xFFFFFFFF
        mm.write(dst, mm.read(src, n), True)
        mm.set_lo(2, dst)
    m.natives[MEMCPY] = memcpy
    m.set_lo(28, GP)
    for start, stop in ((0x8744A0, 0x8744B0), (0x874780, 0x874798), (0x874850, 0x874A20),
                        (0x878F94, 0x878FC4)):
        m.set_lo(29, 0x01FF0000)
        m.set_lo(30, 0x01FF0000)
        m.run(start, stop)
    return m


HAVE_MAIN = bool(os.environ.get("POPSTARTER_TEST_ELF"))
HAVE_CORE = HAVE_MAIN and bool(os.environ.get("POPS_TEST_ELF"))


class Original(unittest.TestCase):
    @unittest.skipUnless(HAVE_MAIN, "POPSTARTER_TEST_ELF not set")
    def test_original_stubs_do_what_the_model_says(self):
        m = run_original_blocks(synthetic_core())
        entries = []
        for site, _, nxt, keep, _ in G.SITES:
            word = m.u32(site)
            self.assertEqual(word >> 26, 2, hex(site))
            entries.append((word & 0x03FFFFFF) << 2)
            self.assertEqual(m.u32(site + 4), nxt if keep else 0, hex(site))
        stubs = m.read(BASE, 0x160)
        runs = G.check_stubs(G.hooked_words(entries), stubs, BASE, random.Random(0x4F524947),
                             own_scratch=(BASE + 0x100, BASE + 0x110))
        self.assertEqual(runs, 9 * 300)

    @unittest.skipUnless(HAVE_CORE, "POPS_TEST_ELF and POPSTARTER_TEST_ELF not set")
    def test_launcher_changes_the_bytes_the_original_does(self):
        pristine = real_core()
        m = run_original_blocks(pristine)
        theirs = bytearray(m.read(CORE, CORE_SIZE))
        ours = bytearray(pristine)
        self.assertEqual(L.pops_resident_hook_gp1(buf(ours), len(ours), BASE + 0x80), 0)
        self.assertEqual(L.pops_resident_hook_guards(buf(ours), len(ours), header(ENTRIES)), 0)
        self.assertEqual(L.pops_apply_always_on_pokes(buf(ours), len(ours)), 0)
        self.assertEqual(L.pops_apply_bios_shell_edits(buf(ours), len(ours)), 0)
        jumps = {GP1_SITE: 3, **{s[0]: 2 for s in G.SITES}}
        diff_t, diff_o = changed(pristine, theirs), changed(pristine, ours)
        self.assertEqual(words_at(diff_t), words_at(diff_o))
        for a in sorted(words_at(diff_t)):
            if a in jumps:   # each side jumps to its own code
                self.assertEqual((u32(theirs, a) >> 26, u32(ours, a) >> 26), (jumps[a], jumps[a]), hex(a))
                target = (u32(theirs, a) & 0x03FFFFFF) << 2
                self.assertTrue(BASE <= target < BASE + 0x160 or a == GP1_SITE, hex(a))
            else:
                self.assertEqual(u32(theirs, a), u32(ours, a), hex(a))
        self.assertEqual(len(words_at(diff_t)), 1 + 9 + 8 + 7 + 3)

    @unittest.skipUnless(os.environ.get("POPS_TEST_ELF"), "POPS_TEST_ELF not set")
    def test_real_core_takes_the_hooks_after_launchers_core_patches(self):
        core = real_core()
        self.assertEqual(L.pops_core_patches_stage(CORE, buf(core), len(core), (1 << 7) - 1), 0)
        self.assertEqual(L.pops_resident_hook_gp1(buf(core), len(core), BASE + 0x80), 0)
        self.assertEqual(L.pops_resident_hook_guards(buf(core), len(core), header(ENTRIES)), 0)
        self.assertEqual(L.pops_apply_always_on_pokes(buf(core), len(core)), 0)
        self.assertEqual(L.pops_apply_bios_shell_edits(buf(core), len(core)), 0)
        hooks = {a: u32(core, a) for a in [GP1_SITE] + [s[0] for s in G.SITES] + list(POKES)}
        self.assertGreater(L.pops_apply_opcode_pass(buf(core), len(core)), 0)
        self.assertEqual({a: u32(core, a) for a in hooks}, hooks)


class BuiltImage(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("POPS_RESIDENT_BIN"), "POPS_RESIDENT_BIN not set")
    def test_built_stubs_are_the_assembled_ones(self):
        image = bytearray(Path(os.environ["POPS_RESIDENT_BIN"]).read_bytes())
        h = Header()
        self.assertEqual(L.pops_resident_check_image(buf(image), len(image), c.byref(h)), 0)
        entries = list(h.guard_entry)
        words, symbols = G.assembled_stubs(entries[0])
        self.assertEqual([symbols[s[4]] for s in G.SITES], entries)
        start = entries[0] - BASE
        self.assertEqual(bytes(image[start:start + 4 * len(words)]),
                         b"".join(w.to_bytes(4, "little") for w in words))
        runs = G.check_stubs(G.hooked_words(entries), bytes(image), BASE, random.Random(0x4255494C))
        self.assertEqual(runs, 9 * 300)


TRAMPOLINE = ROOT / "launcher/src/pops_trampoline.S"
TRAMP_ADDR, TRAMP_ARGS, TRAMP_MAX = 0x00084000, 0x00084200, 0x180
STAGING = 0x01000000
MARK = 0xA5


def trampoline_words():
    words, symbols = R.assemble(TRAMPOLINE.read_text(), TRAMP_ADDR)
    return words, symbols


def run_trampoline(bss_address, bss_size, core, entry=0x00200008):
    """Run the trampoline with PopsTrampolineArgs at 0x84200 (as
    pops_trampoline_args_init writes them) over memory filled with MARK,
    up to its ExecPS2. Returns the machine and the syscalls it made."""
    words, _ = trampoline_words()
    m = Machine()
    m.record = False
    filled = [(0x70000000, 0x70005000), (0x000FF000, 0x00201000),
              (bss_address & ~0xFFF, 0x00872000)]
    for lo, hi in filled:
        m.write(lo, bytes([MARK]) * (hi - lo))
    m.write(TRAMP_ADDR, b"".join(w.to_bytes(4, "little") for w in words))
    args = struct.pack("<IIIIIIIi4I", entry, bss_address, bss_size, 0x3C30, STAGING,
                       CORE, len(core), 1, TRAMP_ARGS + 48, 0, 0, 0)
    m.write(TRAMP_ARGS, args + b"pops0:IMAGE.VCD\0")
    m.write(STAGING, core)
    m.gpr[4] = TRAMP_ARGS
    calls, pc = [], TRAMP_ADDR
    while True:
        try:
            m.run(pc, 0xFFFFFFFC, limit=4000000)
        except R.Syscall as call:
            calls.append((call.number, m.lo(4) & R.M32, m.lo(5) & R.M32,
                          m.lo(6) & R.M32, m.lo(7) & R.M32))
            if call.number == 7:
                return m, calls
            pc = call.pc + 4


class Trampoline(unittest.TestCase):
    """POPStarter's last writes before it enters POPS (MAIN 0x87c0f0..
    0x87c144): memset(0x70000000, 0, 0x4000), memset(0x502e60, 0, 0x36d1a0)
    (up to its own code at 0x870000) and memset(0x100000, 0, 0x100000).
    launcHER's trampoline clears the same, then copies the core."""

    def check(self, bss_address, bss_size):
        core = random.Random(bss_address).randbytes(0x400)
        m, calls = run_trampoline(bss_address, bss_size, core)
        end = max(bss_address + bss_size, 0x00870000)
        zero = lambda lo, hi: self.assertEqual(m.read(lo, hi - lo), bytes(hi - lo), hex(lo))
        kept = lambda lo, hi: self.assertEqual(m.read(lo, hi - lo), bytes([MARK]) * (hi - lo), hex(lo))
        zero(0x70000000, 0x70004000)          # the whole scratchpad
        kept(0x70004000, 0x70005000)
        zero(bss_address, end)                # BSS and the start of the heap
        kept(bss_address & ~0xFFF, bss_address)
        kept(end, 0x00872000)
        zero(0x00100000, 0x00200000)          # launcHER
        kept(0x000FF000, 0x00100000)
        self.assertEqual(m.read(CORE, len(core)), core)
        kept(CORE + len(core), 0x00201000)
        # FlushCache(0), FlushCache(2), ExecPS2(entry, NULL, 1, argv)
        self.assertEqual([call[:2] for call in calls], [(0x64, 0), (0x64, 2), (7, 0x00200008)])
        self.assertEqual(calls[2][2:], (0, 1, TRAMP_ARGS + 32))
        self.assertEqual(m.lo(29), 0x0008FFF0)
        return m

    def test_clears_what_popstarter_clears_and_copies_the_core(self):
        # POPS's BSS ends below 0x870000 (0x865940): cleared up to 0x870000.
        self.check(0x0086E000, 0x100)

    def test_a_longer_bss_is_cleared_to_its_end(self):
        self.check(0x0086FF00, 0x200)

    def test_fits_the_launchers_size_check(self):
        words, symbols = trampoline_words()
        self.assertLessEqual(4 * len(words), TRAMP_MAX)
        self.assertEqual(symbols["pops_trampoline_code"], TRAMP_ADDR)
        self.assertEqual(symbols["pops_trampoline_code_end"], TRAMP_ADDR + 4 * len(words))
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        self.assertEqual(src.count("> 0x180"), 2)

    def test_constants_match_the_header(self):
        h = (ROOT / "common/include/pops_bootstrap.h").read_text()
        self.assertIn("#define POPS_SPAD_CLEAR_SIZE     UINT32_C(0x00004000)", h)
        self.assertIn("#define POPS_CLEAR_END           UINT32_C(0x00870000)", h)
        boot = (ROOT / "common/src/pops_bootstrap.c").read_text()
        self.assertIn("if (staging_base < POPS_CLEAR_END ||", boot)

    @unittest.skipUnless(os.environ.get("POPS_TRAMPOLINE_BIN"), "POPS_TRAMPOLINE_BIN not set")
    def test_built_trampoline_is_the_assembled_one(self):
        words, _ = trampoline_words()
        built = Path(os.environ["POPS_TRAMPOLINE_BIN"]).read_bytes()
        self.assertEqual(built, b"".join(w.to_bytes(4, "little") for w in words))


class Source(unittest.TestCase):
    def test_launch_order(self):
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        body = src[src.index("int launchPOPS("):]
        order = ["res = pops_core_patches_stage(",
                 "res = pops_resident_check_image(",
                 "res = pops_resident_hook_gp1(",
                 "res = pops_resident_hook_guards(",
                 "res = pops_apply_always_on_pokes(",
                 "res = pops_builtin_apply(builtinId, (void *)stagedCore",
                 "res = pops_apply_all_config_patches(",
                 "res = pops_stage_fix_files(",
                 "res = pops_fix_finalize_video(",
                 "res = pops_apply_bios_shell_edits(",
                 "res = regionRead ? pops_apply_region(",
                 "res = pops_apply_reset_warmboot(",
                 "res = pops_apply_opcode_pass(",
                 "SifIopRebootBuffer(",
                 "res = pops_resident_install(",
                 "memcpy((void *)POPS_TRAMPOLINE_ADDR"]
        at = [body.index(s) for s in order]
        self.assertEqual(at, sorted(at), [s for s, _ in sorted(zip(order, at), key=lambda x: x[1])])
        for s in order[:5] + order[9:10]:
            self.assertEqual(body.count(s), 1, s)
        # Every POPStarter-mode launch: no flag gates the hooks or the install.
        for s in ("res = pops_resident_hook_gp1(", "res = pops_resident_hook_guards(",
                  "res = pops_apply_always_on_pokes(", "res = pops_apply_bios_shell_edits(",
                  "res = pops_resident_install("):
            line = body[body.rindex("\n", 0, body.index(s)) + 1:body.index(s)]
            self.assertIn(line, ("  ", "    "), s)
            prev = body[:body.index(s)].rstrip().splitlines()[-1].strip()
            self.assertFalse(prev.startswith("if (residentNeeded") or "flags &" in prev, (s, prev))

    def test_ember_never_reaches_the_pops_launch(self):
        common = (ROOT / "launcher/src/common.c").read_text()
        self.assertEqual(common.count("launchPOPS("), 1)
        self.assertIn("if (isPopsTarget(argv[0]))\n    return launchPOPS(argc, argv);", common)


if __name__ == "__main__":
    unittest.main()
