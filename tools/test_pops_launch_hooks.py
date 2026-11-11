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
import pops_recompiler_model as RC  # noqa: E402
import test_pops_features as F  # noqa: E402  (its PopsConfig; the module builds nothing on import)
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
# POPS's recompiler epilogue around the hook, and the words around its two
# emit points (pops_resident_hook_recompiler / _emit check them).
RECOMPILER_CONTEXT = {0x002075C4: 0xDFB50038, 0x002075D8: 0xDFB00010, 0x002075E0: 0xDFB10018,
                      0x002075E4: 0x24C20004, 0x002075F0: 0xDFB40030, 0x002075F4: 0xDFBF0040,
                      0x002075F8: 0xACC30000}
EMIT_CONTEXT = {0x00206314: 0x00431025, 0x00206320: 0x8CC20000, 0x00205D24: 0x12CB0008,
                0x00205D28: 0x258C0004}


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
        ("recompiler_entry", c.c_uint32), ("recompiler_emit", c.c_uint32 * 4),
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
    lib.pops_resident_hook_recompiler.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
    lib.pops_resident_hook_recompiler_emit.argtypes = [c.c_void_p, c.c_size_t, c.c_uint8,
                                                       c.POINTER(Header)]
    lib.pops_apply_always_on_pokes.argtypes = [c.c_void_p, c.c_size_t]
    lib.pops_apply_bios_shell_edits.argtypes = [c.c_void_p, c.c_size_t]
    lib.pops_apply_opcode_pass.argtypes = [c.c_void_p, c.c_size_t]
    lib.pops_core_patches_stage.argtypes = [c.c_uint32, c.c_void_p, c.c_size_t, c.c_uint32]
    lib.pops_resident_check_image.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(Header)]
    lib.pops_config_init.argtypes = [c.c_void_p]
    lib.pops_config_parse_line.argtypes = [c.c_void_p, c.c_char_p]
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
    for table in (G.CONTEXT, POKE_CONTEXT, GP1_CONTEXT, RECOMPILER_CONTEXT, EMIT_CONTEXT):
        for a, w in table.items():
            put32(core, a, w)
    put32(core, RC.HOOK, RC.HOOK_PRISTINE[0])
    put32(core, RC.HOOK + 4, RC.HOOK_PRISTINE[1])
    for site, (_, _, _, words) in RC.EMITS.items():
        put32(core, site, words[0])
        put32(core, site + 4, words[1])
    for a, (pops, _) in POKES.items():
        put32(core, a, pops)
    put32(core, GP1_SITE, 0)
    return core


ENTRIES = [BASE + 0x100 + 0x20 * i for i in range(9)]


def changed(before, after):
    out = set()
    for off in range(0, len(before), 4096):
        if before[off:off + 4096] != after[off:off + 4096]:
            out.update(CORE + i for i in range(off, min(off + 4096, len(before))) if before[i] != after[i])
    return out


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


RC_CODE, RC_CONFIG, RC_SAVE = BASE + 0x400, BASE + 0x2000, BASE + 0x3000
EMIT_ENTRIES = [BASE + 0x800 + 0x40 * i for i in range(4)]
RECOMPILER_ENTRY = BASE + 0x700


def emit_header(entries=EMIT_ENTRIES):
    h = Header()
    for i, e in enumerate(entries):
        h.recompiler_emit[i] = e
    return h


def launcher_loader(image, image_base, entry, emits, config):
    """load(addons) for the recompiler model's runners: launcHER's code
    (`image` at `image_base`), the flags the commands set in its
    configuration (at `config`), and the POPS words launcHER's two
    installers write for those commands on a synthetic core."""
    hooked = {}
    for addons in (0, 8, 16, 24):
        core = synthetic_core()
        assert L.pops_resident_hook_recompiler(buf(core), len(core), entry) == 0
        assert L.pops_resident_hook_recompiler_emit(buf(core), len(core), addons, emit_header(emits)) == 0
        hooked[addons] = {a: bytes(core[a - CORE:a - CORE + 8]) for a in [RC.HOOK] + list(RC.EMITS)}

    def load(addons):
        pre = {image_base: image, config + RC.FLAGS_OFFSET: RC.config_flags(addons).to_bytes(4, "little")}
        pre.update(hooked[addons & 24])
        return pre
    return load


def assembled_recompiler():
    """launcHER's recompiler code assembled from its source: (load, gp slot, scratch)."""
    words, symbols = RC.assembled(RC_CODE, RC_CONFIG, RC_SAVE)
    image = b"".join(w.to_bytes(4, "little") for w in words)
    load = launcher_loader(image, RC_CODE, symbols["pops_resident_recompiler"],
                           [symbols[s] for s in RC.EMIT_SYMBOLS], RC_CONFIG)
    return load, RC_SAVE + 0x30, ((RC_SAVE, RC_SAVE + 0x40),)


class Recompiler(unittest.TestCase):
    """pops_resident_hook_recompiler / _emit, and launcHER's code
    (common/src/pops_resident_recompiler.S) against the model."""

    def test_hook_writes_a_jump_and_a_nop(self):
        core = synthetic_core()
        before = bytes(core)
        self.assertEqual(L.pops_resident_hook_recompiler(buf(core), len(core), RECOMPILER_ENTRY), 0)
        self.assertEqual((u32(core, RC.HOOK), u32(core, RC.HOOK + 4)), (RC.jump(RECOMPILER_ENTRY), 0))
        self.assertEqual(words_at(changed(before, core)), {RC.HOOK, RC.HOOK + 4})
        once = bytes(core)
        self.assertEqual(L.pops_resident_hook_recompiler(buf(core), len(core), RECOMPILER_ENTRY), 0)
        self.assertEqual(bytes(core), once)
        self.assertEqual(L.pops_resident_hook_recompiler(buf(core), len(core), RECOMPILER_ENTRY + 4),
                         -errno.EILSEQ)
        self.assertEqual(bytes(core), once)

    def test_hook_checks_every_word_before_writing(self):
        for addr in list(RECOMPILER_CONTEXT) + [RC.HOOK, RC.HOOK + 4]:
            core = synthetic_core()
            put32(core, addr, u32(core, addr) ^ 0x00010000)
            before = bytes(core)
            self.assertEqual(L.pops_resident_hook_recompiler(buf(core), len(core), RECOMPILER_ENTRY),
                             -errno.EILSEQ, hex(addr))
            self.assertEqual(bytes(core), before, hex(addr))

    def test_hook_rejects_bad_entries_and_short_cores(self):
        core = synthetic_core()
        before = bytes(core)
        for bad in (RECOMPILER_ENTRY + 2, BASE - 4, LIMIT, 0x00200000):
            self.assertEqual(L.pops_resident_hook_recompiler(buf(core), len(core), bad), -errno.EINVAL, hex(bad))
        self.assertEqual(L.pops_resident_hook_recompiler(None, len(core), RECOMPILER_ENTRY), -errno.EINVAL)
        need = 0x002075F8 + 4 - CORE
        self.assertEqual(L.pops_resident_hook_recompiler(buf(core), need - 1, RECOMPILER_ENTRY), -errno.ERANGE)
        self.assertEqual(bytes(core), before)
        self.assertEqual(L.pops_resident_hook_recompiler(buf(core), need, RECOMPILER_ENTRY), 0)

    def test_emit_hook_writes_what_the_commands_ask_for(self):
        sites = list(RC.EMITS)
        for addons in range(32):
            core = synthetic_core()
            before = bytes(core)
            self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(core), len(core), addons, emit_header()),
                             0, addons)
            if not addons & 24:
                self.assertEqual(bytes(core), before, addons)
                continue
            pick = 2 if addons & 16 else 0      # ADDON_4 is ADDON_3 plus changes to its code
            for i, site in enumerate(sites):
                self.assertEqual((u32(core, site), u32(core, site + 4)),
                                 (RC.jump(EMIT_ENTRIES[pick + i]), 0), (addons, hex(site)))
            self.assertEqual(words_at(changed(before, core)), {a + k for a in sites for k in (0, 4)}, addons)

    def test_emit_hook_takes_either_commands_jumps_and_nothing_else(self):
        core = synthetic_core()
        self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(core), len(core), 8, emit_header()), 0)
        once = bytes(core)
        self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(core), len(core), 8, emit_header()), 0)
        self.assertEqual(bytes(core), once)
        self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(core), len(core), 16, emit_header()), 0)
        self.assertEqual(u32(core, 0x00206318), RC.jump(EMIT_ENTRIES[2]))
        other = [e + 0x100 for e in EMIT_ENTRIES]
        hooked = bytes(core)
        self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(core), len(core), 8, emit_header(other)),
                         -errno.EILSEQ)
        self.assertEqual(bytes(core), hooked)

    def test_emit_hook_checks_every_word_before_writing(self):
        targets = list(EMIT_CONTEXT) + [a + k for a in RC.EMITS for k in (0, 4)]
        for addr in targets:
            core = synthetic_core()
            put32(core, addr, u32(core, addr) ^ 0x00010000)
            before = bytes(core)
            self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(core), len(core), 8, emit_header()),
                             -errno.EILSEQ, hex(addr))
            self.assertEqual(bytes(core), before, hex(addr))

    def test_emit_hook_rejects_bad_arguments(self):
        core = synthetic_core()
        before = bytes(core)
        for i in range(4):
            for bad in (EMIT_ENTRIES[i] + 2, BASE - 4, LIMIT, 0x00200000):
                e = list(EMIT_ENTRIES)
                e[i] = bad
                self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(core), len(core), 8, emit_header(e)),
                                 -errno.EINVAL, (i, hex(bad)))
        self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(core), len(core), 0x20, emit_header()),
                         -errno.EINVAL)
        self.assertEqual(L.pops_resident_hook_recompiler_emit(None, len(core), 8, emit_header()), -errno.EINVAL)
        self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(core), len(core), 8, None), -errno.EINVAL)
        need = 0x00206320 + 4 - CORE
        self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(core), need - 1, 8, emit_header()),
                         -errno.ERANGE)
        self.assertEqual(bytes(core), before)
        self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(core), need, 8, emit_header()), 0)

    def test_opcode_pass_keeps_the_hooks(self):
        core = synthetic_core()
        self.assertEqual(L.pops_resident_hook_recompiler(buf(core), len(core), RECOMPILER_ENTRY), 0)
        self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(core), len(core), 8, emit_header()), 0)
        hooks = [RC.HOOK, RC.HOOK + 4] + [a + k for a in RC.EMITS for k in (0, 4)]
        before = {a: u32(core, a) for a in hooks}
        self.assertGreaterEqual(L.pops_apply_opcode_pass(buf(core), len(core)), 0)
        self.assertEqual({a: u32(core, a) for a in hooks}, before)

    def test_assembled_code_does_what_the_model_says(self):
        load, slot, scratch = assembled_recompiler()
        runs, skipped = RC.check_block(load, random.Random(0x52435452), 30)
        self.assertGreaterEqual(runs, 8 * 30 - 8)
        self.assertGreater(RC.check_emit(load, slot, scratch, random.Random(0x454D4954), 60), 3 * 60)

    def test_commands_parse(self):
        def parse(*lines):
            cfg = F.PopsConfig()
            L.pops_config_init(c.addressof(cfg))
            for line in lines:
                L.pops_config_parse_line(c.addressof(cfg), line.encode())
            return cfg.recompiler_addons
        self.assertEqual(parse(), 0)
        for n in range(5):
            self.assertEqual(parse("$RECOMPILER_ADDON_%d" % n), 1 << n, n)
        self.assertEqual(parse("$recompiler_addon_2"), 4)
        self.assertEqual(parse("$RECOMPILER_ADDON_0 $RECOMPILER_ADDON_3", "$RECOMPILER_ADDON_4"), 0x19)
        # Whole tokens, as the original's handlers want a space, CR, LF, NUL
        # or "$" after the digit (0x8936f4..0x893780).
        for bad in ("$RECOMPILER_ADDON_5", "$RECOMPILER_ADDON_", "$RECOMPILER_ADDON_10",
                    "$RECOMPILER_ADDON_1X", "$RECOMPILER_ADDON", "RECOMPILER_ADDON_1"):
            self.assertEqual(parse(bad), 0, bad)

    def test_source_is_built_and_named_in_the_header(self):
        cmake = (ROOT / "launcher/CMakeLists.txt").read_text()
        self.assertIn('set(POPS_RESIDENT_RECOMPILER "${CMAKE_SOURCE_DIR}/common/src/pops_resident_recompiler.S")',
                      cmake)
        self.assertGreaterEqual(cmake.count("${POPS_RESIDENT_RECOMPILER}"), 2)
        engine = (ROOT / "common/src/pops_resident_engine.c").read_text()
        order = [engine.index("(uint32_t)" + s) for s in ["pops_resident_recompiler,"] + RC.EMIT_SYMBOLS]
        self.assertEqual(order, sorted(order), "header entries in POPS_EMIT_* order")


class RecompilerQuirks:
    """What the original does that a fix would change, kept on purpose
    (docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md). Run on launcHER's code, and
    on the original's with POPSTARTER_TEST_ELF."""
    A2 = 0x00600800                     # $a2: ADDON_0 looks at the 0x800 bytes before it

    def code(self):
        raise NotImplementedError

    def block(self, addons, words, flag=1, length=0, v1=0x5A5A5A5A_00000000_11111111_22222222,
              runs_on=False):
        """One pass of the hook; with `runs_on`, it must not come back
        (stopped after 3000 instructions)."""
        load, _, _ = self.code()
        m = RC.machine(load(addons))
        m.set_lo(29, RC.STACK)
        m.set_lo(6, self.A2)
        m.set_full(3, v1)
        m.put32(RC.FLAG, flag)
        m.put32(RC.START, 0x00010000)
        m.put32(RC.LENGTH, length)
        for addr, w in words.items():
            m.put32(addr, w)
        m.steps = 0
        if runs_on:
            with self.assertRaisesRegex(RuntimeError, "step limit"):
                m.run(RC.HOOK, RC.RESUME, limit=3000)
        else:
            m.run(RC.HOOK, RC.RESUME, limit=200000)
        return m

    def test_addon0_waits_for_addon2_while_the_flag_is_set(self):
        lw = {self.A2 - 4: 0x8C820000}
        for addons, flag, converted in ((1, 1, False), (3, 1, False), (5, 1, True), (7, 1, True),
                                        (1, 0, True), (3, 0, True)):
            m = self.block(addons, lw, flag=flag, length=4)
            self.assertEqual(m.u32(self.A2 - 4), 0x98820000 if converted else 0x8C820000, (addons, flag))

    def test_addon1_runs_on_after_a_zeroed_break_7_at_its_end(self):
        words = {0x01010000: 0xFF000000, 0x01010008: RC.BREAK7, 0x01010018: 0xFF000000, 0x01010020: RC.BREAK6}
        m = self.block(2, words, length=8, runs_on=True)
        self.assertEqual((m.u32(0x01010008), m.u32(0x01010020)), (0, 0))     # past its end
        m = self.block(2, words, length=12)       # the break 7 one word earlier: it stops
        self.assertEqual((m.u32(0x01010008), m.u32(0x01010020)), (0, RC.BREAK6))

    def test_addon2_with_length_0_runs_on(self):
        stub = {0x01010010: RC.LI_T2_B0, 0x01010014: RC.JR_T2, 0x01010018: RC.li_t1(0x38)}
        m = self.block(4, stub, length=0, runs_on=True)
        self.assertEqual(m.u32(0x01010010), RC.JR_RA)
        m = self.block(4, stub, length=4)
        self.assertEqual(m.u32(0x01010010), RC.LI_T2_B0)

    def test_addon2_b0_stubs_leave_v1_at_their_third_word(self):
        v1 = 0x5A5A5A5A_00000000_11111111_22222222
        hi = v1 & ~R.M64
        for words, patched, want_v1 in (
                ((RC.LI_T2_B0, RC.li_t1(0x52), RC.JR_T2), False, RC.JR_T2),   # never matches
                ((RC.LI_T2_B0, RC.JR_T2, RC.li_t1(0x3D)), False, RC.li_t1(0x3D)),
                ((RC.LI_T2_B0, RC.li_t1(0x5A), RC.JR_T2), True, RC.JR_T2),
                ((RC.LI_T2_B0, RC.JR_T2, RC.li_t1(0x38)), True, None),
                ((RC.LI_T2_B0, RC.li_t1(0x38), RC.JR_T2), True, None),
                ((RC.LI_T2_A0, RC.li_t1(0x3A), RC.JR_T2), True, None)):
            m = self.block(4, {0x01010000 + 4 * i: w for i, w in enumerate(words)}, length=4, v1=v1)
            self.assertEqual(m.u32(0x01010000) == RC.JR_RA, patched, [hex(w) for w in words])
            self.assertEqual(m.gpr[3], v1 if want_v1 is None else hi | R.sext32(want_v1), [hex(w) for w in words])

    def test_206318_takes_gp_from_the_205d1c_slot(self):
        load, slot, _ = self.code()
        m = RC.machine(load(8))
        gps = [0x1111 << 100 | 0x22, 0x3333 << 100 | 0x44, 0x5555 << 100 | 0x66]
        m.set_lo(17, 0x00700000)
        m.set_lo(12, 0x00700100)
        m.set_full(28, gps[0])
        m.run(0x00206318, 0x00206320, limit=200)
        self.assertEqual(m.gpr[28], 0)     # nothing kept yet
        m.set_full(28, gps[1])
        m.run(0x00205D1C, 0x00205D24, limit=200)
        self.assertEqual(m.gpr[28], gps[1])
        m.set_full(28, gps[2])
        m.run(0x00206318, 0x00206320, limit=200)
        self.assertEqual(m.gpr[28], gps[1])
        self.assertEqual(m.lo(31), 0x01440000)


class LauncherRecompilerQuirks(RecompilerQuirks, unittest.TestCase):
    def code(self):
        return assembled_recompiler()


def main_image():
    from trace_original_pops_io import decode_main
    return decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())


def real_core():
    from trace_original_pops_warmboot import core_image
    core = core_image(os.environ["POPS_TEST_ELF"])
    return core + bytes(max(0, CORE_SIZE - len(core)))


def run_original_blocks(core):
    """The original's always-on writes over `core`, in its order: the
    0x20c0c4 poke (0x8744a0), the GP1 hook (0x874780), the recompiler block
    and its hook (0x8747e0), the guard stubs, guards and pokes
    (0x874850..0x874a20), then the BIOS edits (0x878f94).
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
    for start, stop in ((0x8744A0, 0x8744B0), (0x874780, 0x874798), (0x8747E0, 0x874830),
                        (0x874850, 0x874A20), (0x878F94, 0x878FC4)):
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
        self.assertEqual(L.pops_resident_hook_recompiler(buf(ours), len(ours), RECOMPILER_ENTRY), 0)
        self.assertEqual(L.pops_resident_hook_guards(buf(ours), len(ours), header(ENTRIES)), 0)
        self.assertEqual(L.pops_apply_always_on_pokes(buf(ours), len(ours)), 0)
        self.assertEqual(L.pops_apply_bios_shell_edits(buf(ours), len(ours)), 0)
        jumps = {GP1_SITE: 3, RC.HOOK: 2, **{s[0]: 2 for s in G.SITES}}
        diff_t, diff_o = changed(pristine, theirs), changed(pristine, ours)
        self.assertEqual(words_at(diff_t), words_at(diff_o))
        for a in sorted(words_at(diff_t)):
            if a in jumps:   # each side jumps to its own code
                self.assertEqual((u32(theirs, a) >> 26, u32(ours, a) >> 26), (jumps[a], jumps[a]), hex(a))
                target = (u32(theirs, a) & 0x03FFFFFF) << 2
                self.assertTrue(BASE <= target < BASE + 0x160 or a == GP1_SITE or
                                (a == RC.HOOK and target == RC.ORIGINAL_ENTRY), hex(a))
            else:
                self.assertEqual(u32(theirs, a), u32(ours, a), hex(a))
        self.assertEqual(len(words_at(diff_t)), 1 + 2 + 9 + 8 + 7 + 3)

    @unittest.skipUnless(os.environ.get("POPS_TEST_ELF"), "POPS_TEST_ELF not set")
    def test_real_core_takes_the_hooks_after_launchers_core_patches(self):
        core = real_core()
        self.assertEqual(L.pops_core_patches_stage(CORE, buf(core), len(core), (1 << 7) - 1), 0)
        self.assertEqual(L.pops_resident_hook_gp1(buf(core), len(core), BASE + 0x80), 0)
        self.assertEqual(L.pops_resident_hook_recompiler(buf(core), len(core), RECOMPILER_ENTRY), 0)
        self.assertEqual(L.pops_resident_hook_guards(buf(core), len(core), header(ENTRIES)), 0)
        self.assertEqual(L.pops_apply_always_on_pokes(buf(core), len(core)), 0)
        self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(core), len(core), 16, emit_header()), 0)
        self.assertEqual(L.pops_apply_bios_shell_edits(buf(core), len(core)), 0)
        hooks = {a: u32(core, a) for a in [GP1_SITE, RC.HOOK, RC.HOOK + 4] + [s[0] for s in G.SITES] +
                 list(POKES) + [a + k for a in RC.EMITS for k in (0, 4)]}
        self.assertGreater(L.pops_apply_opcode_pass(buf(core), len(core)), 0)
        self.assertEqual({a: u32(core, a) for a in hooks}, hooks)

    @unittest.skipUnless(HAVE_MAIN, "POPSTARTER_TEST_ELF not set")
    def test_original_recompiler_code_does_what_the_model_says(self):
        load = RC.original_loader(main_image())
        self.assertEqual(load(0)[RC.HOOK], RC.jump(RC.ORIGINAL_ENTRY).to_bytes(4, "little") + bytes(4))
        for n in (3, 4):
            for site, entry in zip(RC.EMITS, RC.ORIGINAL_EMITS[n]):
                self.assertEqual(load(1 << n)[site], RC.jump(entry).to_bytes(4, "little") + bytes(4))
        runs, skipped = RC.check_block(load, random.Random(0x4F524352), 30)
        self.assertGreaterEqual(runs, 8 * 30 - 8)
        self.assertGreater(RC.check_emit(load, RC.ORIGINAL_GP_SLOT, RC.ORIGINAL_SCRATCH,
                                         random.Random(0x4F454D54), 60), 3 * 60)
        print("Original recompiler block PASS: %d passes (%d that run on skipped)" % (runs, skipped))

    @unittest.skipUnless(HAVE_MAIN, "POPSTARTER_TEST_ELF not set")
    def test_launcher_writes_the_original_recompiler_words(self):
        # Given the original's code addresses, launcHER's two installers write
        # the very POPS words the original's own install does, per command set.
        main = main_image()
        emits = RC.ORIGINAL_EMITS[3] + RC.ORIGINAL_EMITS[4]
        for addons in (0, 1, 2, 4, 7, 8, 16, 24, 31):
            core = synthetic_core()
            theirs = bytearray(RC.original_install(main, addons, bytes(core)).read(CORE, CORE_SIZE))
            ours = bytearray(core)
            self.assertEqual(L.pops_resident_hook_recompiler(buf(ours), len(ours), RC.ORIGINAL_ENTRY), 0)
            self.assertEqual(L.pops_resident_hook_recompiler_emit(buf(ours), len(ours), addons,
                                                                  emit_header(emits)), 0)
            want = {RC.HOOK, RC.HOOK + 4} | ({a + k for a in RC.EMITS for k in (0, 4)} if addons & 24 else set())
            self.assertEqual(words_at(changed(core, theirs)), want, addons)
            self.assertEqual(theirs, ours, addons)


@unittest.skipUnless(HAVE_MAIN, "POPSTARTER_TEST_ELF not set")
class OriginalRecompilerQuirks(RecompilerQuirks, unittest.TestCase):
    loaded = None

    def code(self):
        if OriginalRecompilerQuirks.loaded is None:
            OriginalRecompilerQuirks.loaded = RC.original_loader(main_image())
        return OriginalRecompilerQuirks.loaded, RC.ORIGINAL_GP_SLOT, RC.ORIGINAL_SCRATCH


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

    @unittest.skipUnless(os.environ.get("POPS_RESIDENT_BIN"), "POPS_RESIDENT_BIN not set")
    def test_built_recompiler_code_is_the_assembled_code(self):
        image = bytearray(Path(os.environ["POPS_RESIDENT_BIN"]).read_bytes())
        h = Header()
        self.assertEqual(L.pops_resident_check_image(buf(image), len(image), c.byref(h)), 0)
        entry, emits = h.recompiler_entry, list(h.recompiler_emit)
        # pops_resident_recompiler_save, from the first emit code's lui/addiu.
        hi, lo = struct.unpack_from("<II", image, emits[0] - BASE)
        self.assertEqual((hi >> 16, lo >> 16), (0x3C1F, 0x27FF))
        save = ((hi & 0xFFFF) << 16) + R.sext16(lo)
        self.assertEqual(save % 16, 0)
        self.assertTrue(BASE + h.header_size <= save and save + 0x40 <= BASE + h.image_size, hex(save))
        words, symbols = RC.assembled(entry, h.config_addr, save)
        self.assertEqual([symbols[s] for s in RC.EMIT_SYMBOLS], emits)
        start = entry - BASE
        self.assertEqual(bytes(image[start:start + 4 * len(words)]),
                         b"".join(w.to_bytes(4, "little") for w in words))
        full = bytes(image) + bytes(h.image_size - len(image))      # installed: the rest zeroed
        load = launcher_loader(full, BASE, entry, emits, h.config_addr)
        runs, _ = RC.check_block(load, random.Random(0x42524352), 20)
        self.assertGreaterEqual(runs, 8 * 20 - 8)
        self.assertGreater(RC.check_emit(load, save + 0x30, ((save, save + 0x40),),
                                         random.Random(0x42454D54), 40), 3 * 40)


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
                 "res = pops_resident_hook_recompiler(",
                 "res = pops_resident_hook_guards(",
                 "res = pops_apply_always_on_pokes(",
                 "res = pops_builtin_apply(builtinId, (void *)stagedCore",
                 "res = pops_apply_all_config_patches(",
                 "res = pops_resident_hook_recompiler_emit(",
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
        for s in order[:6] + order[8:9] + order[11:12]:
            self.assertEqual(body.count(s), 1, s)
        # Every POPStarter-mode launch: no flag gates the hooks or the install.
        for s in ("res = pops_resident_hook_gp1(", "res = pops_resident_hook_recompiler(",
                  "res = pops_resident_hook_guards(", "res = pops_resident_hook_recompiler_emit(",
                  "res = pops_apply_always_on_pokes(", "res = pops_apply_bios_shell_edits(",
                  "res = pops_resident_install("):
            line = body[body.rindex("\n", 0, body.index(s)) + 1:body.index(s)]
            self.assertIn(line, ("  ", "    "), s)
            prev = body[:body.index(s)].rstrip().splitlines()[-1].strip()
            self.assertFalse(prev.startswith("if (residentNeeded") or "flags &" in prev, (s, prev))

    def test_trace_lines_use_no_long_long_conversion(self):
        # The EE libc's printf does not know %ll: a traced launch printed
        # "POPS: Disc region 3 (licence at 0xlx)" (emulator, trace build).
        import re
        for path in sorted((ROOT / "launcher/src").glob("*.c")) + sorted((ROOT / "common/src").glob("*.c")):
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertIsNone(re.search(r'"[^"\n]*%[-+ #0-9.]*ll[diouxX]', text), path.name)
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        self.assertIn('DPRINTF("POPS: Disc region %u (licence at 0x%lx)\\n", (unsigned)cfg.disc_region,\n'
                      '            (unsigned long)licence);', src)

    def test_ember_never_reaches_the_pops_launch(self):
        common = (ROOT / "launcher/src/common.c").read_text()
        self.assertEqual(common.count("launchPOPS("), 1)
        self.assertIn("if (isPopsTarget(argv[0]))\n    return launchPOPS(argc, argv);", common)


if __name__ == "__main__":
    unittest.main()
