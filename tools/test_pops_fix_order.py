#!/usr/bin/env python3
"""Differential of fix files before commands versus commands before fix files.

The original BIOS, TROJAN, PATCH and CHEATS.TXT blocks run under Unicorn with
modelled file services. launcHER's current helper runs on the host, and a
Test-only alternate helper runs its files before its commands. No production
order changes are made. Comparisons cover the whole final core except the
original parser's three resident-blob words, which are restored after parsing
as in the existing BIOS harness. Reports contain only addresses, never original
or replacement code bytes.
"""
import ctypes as c
import hashlib
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import test_pops_user_bios as B  # noqa: E402
import test_pops_trojan as TT  # noqa: E402
import trace_original_pops_trojan as T  # noqa: E402

BASE = B.BASE
SIZE = B.SIZE
GP = T.GP if hasattr(T, "GP") else 0x9B68F0
CORE_BASE = T.CORE_BASE
OSD_SITE = B.OSD_SITE
OSD_DIFF = [OSD_SITE, OSD_SITE + 1]
HAVE = bool(os.environ.get("POPSTARTER_TEST_ELF")) and bool(os.environ.get("POPS_TEST_ELF"))
if HAVE:
    try:
        import unicorn  # noqa: F401
        import trace_original_pops_user_bios as U  # noqa: E402
    except Exception:
        HAVE = False

ALT_C = r'''
static int pops_stage_user_files_alt(void *stagedCore, size_t coreSize,
                                     const char *vcdDir, const char *titleDir,
                                     uint16_t builtinId, uint8_t builtinModes,
                                     const PopsConfig *cfg,
                                     const PopsResidentHeader *residentHdr,
                                     PopsUserRomState *rom, PopsFixContext *finalContext,
                                     PopsTrojanSet *trojanSet, const char *ordered_lines) {
  int res;
  memset(rom, 0, sizeof(*rom));
  rom->integrity = 1;
  rom->no_fix = (builtinModes & 0x80) != 0;
  rom->osd_off = (builtinModes & (1 << 5)) != 0;
  if (trojanSet)
    trojanSet->chain_offered =
        (uint8_t)pops_resident_slot_chain_possible(stagedCore, coreSize, residentHdr);
  res = pops_stage_fix_files(stagedCore, coreSize, vcdDir, titleDir, builtinId,
                             cfg->compat_modes,
                             cfg->progressive_requested ? POPS_VMODE_480P : cfg->video_mode,
                             residentHdr->progressive_entry,
                             cfg->hdtv_fix ? 0x24040001 : 0x32240001,
                             0, NULL, NULL, NULL, rom, finalContext, trojanSet);
  if (res)
    return res;
  {
    PopsConfig ordered = *cfg;
    ordered.original_tokens = 0;
    ordered.compat_modes = 0;
    res = pops_apply_all_config_patches_rom(stagedCore, coreSize, &ordered, rom);
  }
  if (res < 0) {
    msg("POPS: Applying config patches failed: %%d\n", res);
    return res;
  }
  if (res == POPS_MODE6_SKIPPED) {
    DPRINTF("POPS: Compatibility mode 6 is not applied over a user BIOS.BIN\n");
  }
  for (const char *at = ordered_lines; at && *at;) {
    const char *end = strchr(at, '\n');
    size_t length = end ? (size_t)(end - at) : strlen(at);
#define ORDER_IS(text) (length == sizeof(text) - 1 && !memcmp(at, text, length))
    if (ORDER_IS("$COMPATIBILITY_0x06"))
      res = pops_apply_compat_modes_rom(stagedCore, coreSize, 1 << 5, rom);
    else if (ORDER_IS("$UNDO_COMPATIBILITY_CODES"))
      res = pops_apply_undo_tokens_rom(stagedCore, coreSize, 1 << 12, rom);
    else if (ORDER_IS("$UNDO_GAME_FIXES"))
      res = pops_apply_undo_tokens_rom(stagedCore, coreSize, 1 << 13, rom);
    else if (ORDER_IS("$UNDO_LIBCRYPT_FIX"))
      res = pops_apply_undo_tokens_rom(stagedCore, coreSize, 1 << 14, rom);
    else
      res = -ENOTSUP;
#undef ORDER_IS
    if (res < 0) {
      msg("POPS: Applying ordered config patches failed: %%d\n", res);
      return res;
    }
    if (!end)
      break;
    at = end + 1;
  }
  res = pops_resident_hook_recompiler_emit(stagedCore, coreSize, cfg->recompiler_addons,
                                           residentHdr);
  if (res) {
    msg("POPS: $RECOMPILER_ADDON_3/4 failed: %%d\n", res);
    return res;
  }
  return 0;
}
int test_launch_alt(void *core, size_t size, const char *root, const char *title,
                    unsigned builtin_id, unsigned builtin_modes, const PopsConfig *cfg,
                    const uint32_t *emit, uint32_t progressive, PopsUserRomState *rom,
                    PopsFixContext *context, const char *ordered_lines) {
  PopsResidentHeader header;
  PopsFixContext local;
  PopsTrojanSet set;
  host_set(&set);
  memset(&header, 0, sizeof(header));
  for (unsigned i = 0; emit && i < POPS_EMIT_COUNT; ++i) header.recompiler_emit[i] = emit[i];
  header.progressive_entry = progressive;
  return pops_stage_user_files_alt(core, size, root, title, (uint16_t)builtin_id,
                                   (uint8_t)builtin_modes, cfg, &header, rom,
                                   context ? context : &local, &set, ordered_lines);
}
/* The built-in entry as launchPOPS applies it'''

_ALT = {}


def alt_library():
    if "lib" in _ALT:
        return _ALT["lib"]
    temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    _ALT["temp"] = temp
    source = (ROOT / "launcher/src/handler_pops.c").read_text()
    start = source.index("static int readFullFile(")
    end = source.index("/* Driver names within one role", start)
    helper = source[source.index(B.LAUNCH_HELPER):source.index("int launchPOPS(")]
    functions = (source[start:end] + helper).replace("(void *)0x01f00000", "host_fix_buffer")
    wrapper = B.READER_WRAPPER.replace("/* The built-in entry as launchPOPS applies it", ALT_C)
    path = Path(temp.name) / "reader_alt.c"
    path.write_text(wrapper % functions)
    library = Path(temp.name) / ("reader_alt.dll" if os.name == "nt" else "reader_alt.so")
    subprocess.run(["gcc", "-shared", "-fPIC", "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-I", str(ROOT / "common/include"), str(path),
                    str(ROOT / "common/src/pops_modes_patches.c"),
                    str(ROOT / "common/src/pops_resident_engine.c"),
                    str(ROOT / "common/src/pops_resident.c"),
                    str(ROOT / "common/src/pops_builtin_db.c"),
                    str(ROOT / "common/src/pops_builtin_db_data.c"),
                    str(ROOT / "common/src/pops_external.c"), "-o", str(library)], check=True)
    lib = c.CDLL(str(library))
    lib.test_launch.argtypes = B.reader_library().test_launch.argtypes
    lib.test_launch_alt.argtypes = lib.test_launch.argtypes + [c.c_char_p]
    lib.test_builtin.argtypes = [c.c_uint, B.P, B.Z]
    _ALT["lib"] = lib
    return lib


def changed(before, after):
    return list(B.changed(before, after))


def normalized(base, original_base, original_final):
    expected = bytearray(base)
    lo, hi = B.ROM - BASE, B.ROM - BASE + B.ROM_READ
    expected[lo:hi] = original_final[lo:hi]
    for offset in changed(original_base, original_final):
        expected[offset] = original_final[offset]
    return expected


def diff(expected, actual):
    return [BASE + offset for offset in changed(expected, actual)]


def validate_baseline(original_base, original_final, base_current, base_alt):
    if base_current != base_alt:
        raise AssertionError("blank current and alternate cores differ")
    lo, hi = B.ROM - BASE, B.ROM - BASE + B.ROM_READ
    if base_current[lo:hi] != original_base[lo:hi]:
        raise AssertionError("blank launcher and original ROM ranges differ")
    rest = bytearray(original_final)
    rest[lo:hi] = original_base[lo:hi]
    for offset in changed(rest, original_base):
        if base_current[offset] != original_base[offset]:
            raise AssertionError("launch write overlaps an original change at 0x%x" % (BASE + offset))


def original_fix(loader, scope, core, flags, trojan_data, patch_data, which):
    files = {}
    folder = b"GAME/" if scope else b""
    for kind, data, slot in ((b"TROJAN", trojan_data, 0 if scope == 0 else 1),
                             (b"PATCH", patch_data, 3 if scope == 0 else 7)):
        if data is not None:
            files[b"mass:/POPS/" + folder + b"%s_%d.BIN" % (kind, slot)] = data
    baseline = bytearray(loader.loader.baseline)
    baseline[CORE_BASE:CORE_BASE + len(core)] = core
    for name, offset in U.FLAGS.items():
        struct.pack_into("<I", baseline, GP + offset, flags.get(name, 0) & 0xFFFFFFFF)
    loader.loader.baseline = bytes(baseline)
    ret, events, after = loader.loader.run(files, scope=scope, title=b"GAME/",
                                    builtin=flags.get("builtin_id", 0),
                                    loader=T.TROJAN_LOADER if which == "trojan" else T.PATCH_LOADER)
    loader.open_paths.extend(event[1] for event in events if event[0] == "open")
    assert ret == 1, (which, scope, ret)
    core = after[CORE_BASE:CORE_BASE + len(core)]
    new_flags = dict(flags)
    for name, offset in U.FLAGS.items():
        new_flags[name] = struct.unpack_from("<I", after, GP + offset)[0]
    return core, new_flags


def original_parser(core, flags, scope, lines):
    if not lines:
        return core, flags
    before = bytearray(core)
    text = b"".join(line + b"\n" for line in lines)
    parser_flags = {name: value for name, value in flags.items() if name in U.FLAGS}
    core, flags = U.parser(text, core, parser_flags)
    for address in B.Original.BLOB_SITES:
        B.put(core, address, B.get(before, address, 4), 4)
    return core, flags


def original_files(loader, core, flags, case):
    for scope in (0, 1):
        if case["bios"][scope] is not None:
            result = U.handler(core, scope, 1, case["bios"][scope],
                               {name: value for name, value in flags.items() if name in U.FLAGS})
            core, flags = result["core"], result["flags"]
        core, flags = original_fix(loader, scope, core, flags,
                                   case["trojan"][scope], case["patch"][scope], "trojan")
        core, flags = original_fix(loader, scope, core, flags,
                                   case["trojan"][scope], case["patch"][scope], "patch")
    return core, flags


def original_sequence(loader, order, start, flags, case):
    core, flags = bytearray(start), dict(flags)
    if order == "commands":
        core, flags = original_parser(core, flags, case["parser_scope"], case["lines"])
        core, flags = original_files(loader, core, flags, case)
    else:
        core, flags = original_files(loader, core, flags, case)
        core, flags = original_parser(core, flags, case["parser_scope"], case["lines"])
    return core, flags


def host_sequence(lib, alternate, start, case):
    core, state = bytearray(start), B.rom(**{name: 0xFF for name in B.FLAG_NAMES})
    root, game = case["folders"]
    cfg = B.config(*case["lines"])
    table = (c.c_uint32 * 4)(*case.get("emit", ())) if case.get("emit") else None
    if alternate:
        ordered = b"\n".join(case["lines"]) if case["lines"] else None
        rc = lib.test_launch_alt(B.buf(core), SIZE, root, game, case["builtin"], case["modes"],
                                 c.byref(cfg), table, 0, c.byref(state), None, ordered)
    else:
        rc = lib.test_launch(B.buf(core), SIZE, root, game, case["builtin"], case["modes"],
                             c.byref(cfg), table, 0, c.byref(state), None)
    return rc, core, state


def comparison(loader, start, flags, case):
    original_base = {}
    for order in ("files", "commands"):
        blank = dict(case)
        blank.update(bios=(None, None), trojan=(None, None), patch=(None, None), lines=())
        original_base[order] = original_sequence(loader, order, start, flags, blank)[0]
    originals = {order: original_sequence(loader, order, start, flags, case)[0]
                 for order in ("files", "commands")}
    rc_current, current, _ = host_sequence(loader.lib, False, start, case)
    rc_alt, alternate, _ = host_sequence(loader.lib, True, start, case)
    base_current = host_sequence(loader.lib, False, start, dict(case, bios=(None, None),
                                                               trojan=(None, None), patch=(None, None), lines=(),
                                                               folders=case["unused"]))[1]
    base_alt = host_sequence(loader.lib, True, start, dict(case, bios=(None, None),
                                                          trojan=(None, None), patch=(None, None), lines=(),
                                                          folders=case["unused"]))[1]
    validate_baseline(original_base["files"], originals["files"], base_current, base_alt)
    validate_baseline(original_base["commands"], originals["commands"], base_current, base_alt)
    results = {"of_vs_oc": diff(originals["files"], originals["commands"]),
               "of_vs_lc": diff(normalized(base_current, original_base["files"], originals["files"]), current),
               "oc_vs_lc": diff(normalized(base_current, original_base["commands"], originals["commands"]), current),
               "of_vs_la": diff(normalized(base_alt, original_base["files"], originals["files"]), alternate),
               "oc_vs_la": diff(normalized(base_alt, original_base["commands"], originals["commands"]), alternate)}
    return results, (rc_current, rc_alt)


class LoaderWrap:
    def __init__(self):
        self.loader = T.Loader()
        self.lib = alt_library()
        self.open_paths = []


def case_from(builtin6, root_bios, game_bios, patch6, lines, root, game, unused, entry):
    start = bytearray(U.core_image())
    builtin, modes, flags = 0, 0, {}
    if builtin6:
        builtin = entry
        modes = alt_library().test_builtin(builtin, B.buf(start), SIZE)
        flags = {"osd_off": 1, "builtin_id": builtin}
    return {"start": start, "flags": flags, "builtin": builtin, "modes": modes,
            "bios": (root_bios, game_bios), "trojan": (None, None), "patch": patch6,
            "lines": lines, "parser_scope": 0, "folders": (root, game), "unused": unused}


@unittest.skipUnless(HAVE, "POPSTARTER_TEST_ELF, POPS_TEST_ELF and unicorn are needed")
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wrap = LoaderWrap()
        cls.entry = B.mode_6_entry()

    def scenario(self, name, case):
        results, rc = comparison(self.wrap, case.pop("start"), case.pop("flags"), case)
        self.assertEqual(results["of_vs_la"], [], results)
        self.assertEqual(results["of_vs_oc"], results["oc_vs_la"], results)
        self.assertEqual(set(results["of_vs_lc"]), set(results["of_vs_oc"]) | set(results["oc_vs_lc"]), results)
        for key in ("of_vs_lc", "oc_vs_lc"):
            self.assertIn(results[key], ([], OSD_DIFF), results)
        if any(results.values()):
            print(name + ": " + "; ".join(
                "%s=%s" % (key, "none" if not value else ",".join("0x%x" % a for a in value))
                for key, value in results.items() if value))
        return results, rc

    def test_270_scenario_control(self):
        small, big, exact = B.bios_file(B.ROM_MIN - 1, 3), B.bios_file(0x80000, 1), B.bios_file(B.ROM_MIN, 2)
        commands = {0: ((), (B.MODE_6_LINE,), (B.UNDO_LINES[0],), (B.UNDO_LINES[1], B.MODE_6_LINE),
                        (B.MODE_6_LINE, B.UNDO_LINES[2])),
                    1: ((), (B.MODE_6_LINE,), (B.UNDO_LINES[1],), (B.UNDO_LINES[2], B.MODE_6_LINE),
                        (B.MODE_6_LINE, B.UNDO_LINES[1]))}
        loaded = plain = older = order_diffs = current_diffs = 0
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            root, empty = Path(temp) / "POPS", Path(temp) / "EMPTY"
            game = root / "GAME"
            game.mkdir(parents=True)
            (empty / "GAME").mkdir(parents=True)
            used = [os.fsencode(str(root) + "/"), os.fsencode(str(game) + "/")]
            unused = [os.fsencode(str(empty) + "/"), os.fsencode(str(empty / "GAME") + "/")]
            for builtin6 in (0, 1):
                for root_bios, game_bios in __import__("itertools").product((None, small, big),
                                                                            (None, small, exact)):
                    for patch6 in ((0, 0), (1, 0), (0, 1)):
                        for lines in commands[builtin6]:
                            case = case_from(builtin6, root_bios, game_bios,
                                             tuple(B.patch_file(3 if i == 0 else 7, modes=(6,)) if bit else None
                                                   for i, bit in enumerate(patch6)),
                                             lines, used[0], used[1], unused, self.entry)
                            if root_bios is not None:
                                (root / "BIOS.BIN").write_bytes(root_bios)
                            elif (root / "BIOS.BIN").exists():
                                (root / "BIOS.BIN").unlink()
                            if game_bios is not None:
                                (game / "BIOS.BIN").write_bytes(game_bios)
                            elif (game / "BIOS.BIN").exists():
                                (game / "BIOS.BIN").unlink()
                            for scope, path in ((0, root / "PATCH_3.BIN"), (1, game / "PATCH_7.BIN")):
                                if patch6[scope]:
                                    path.write_bytes(B.patch_file(3 if scope == 0 else 7, modes=(6,)))
                                elif path.exists():
                                    path.unlink()
                            results, rc = self.scenario(
                                "control/b%d/root=%s/game=%s/patch=%s/lines=%s" %
                                (builtin6, root_bios and len(root_bios), game_bios and len(game_bios), patch6, lines), case)
                            self.assertEqual(rc, (0, 0), results)
                            order_diffs += bool(results["of_vs_oc"])
                            current_diffs += bool(results["of_vs_lc"])
                            has_bios = (root_bios is big) or (game_bios is exact)
                            undo = [n for n, line in enumerate(lines) if line in B.UNDO_LINES]
                            mode6_first = bool(undo) and B.MODE_6_LINE in lines[:undo[0]]
                            is_older = (not has_bios and bool(undo) and not builtin6 and
                                        (any(patch6) or mode6_first))
                            if has_bios:
                                loaded += 1
                            elif is_older:
                                older += 1
                            else:
                                plain += 1
                            self.assertEqual(results["of_vs_la"], [], results)
                            self.assertEqual(results["of_vs_oc"], results["oc_vs_la"], results)
                            for key in ("of_vs_lc", "oc_vs_lc"):
                                self.assertIn(results[key], ([], OSD_DIFF), results)
                            if is_older:
                                self.assertEqual(results["of_vs_lc"], OSD_DIFF, results)
        self.assertEqual((loaded, plain, older, order_diffs, current_diffs), (150, 92, 28, 16, 28))
        print("270-scenario control: %d with BIOS loaded, %d without, %d original-order differences; "
              "%d current launcHER differences at 0x2525b0" % (loaded, plain, order_diffs, current_diffs))

    def test_fix_file_open_order(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            root = Path(temp) / "POPS"
            game = root / "GAME"
            game.mkdir(parents=True)
            used = [os.fsencode(str(root) + "/"), os.fsencode(str(game) + "/")]
            (root / "TROJAN_0.BIN").write_bytes(TT.trojan(slot=0, payload=b"\0" * 4))
            (root / "PATCH_3.BIN").write_bytes(B.patch_file(3, modes=(6,)))
            (game / "TROJAN_1.BIN").write_bytes(TT.trojan(slot=1, payload=b"\0" * 4))
            (game / "PATCH_7.BIN").write_bytes(B.patch_file(7, modes=(6,)))
            self.wrap.open_paths.clear()
            case = case_from(0, None, None,
                             (B.patch_file(3, modes=(6,)), B.patch_file(7, modes=(6,))),
                             (), used[0], used[1], used, self.entry)
            case["trojan"] = (TT.trojan(slot=0, payload=b"\0" * 4),
                              TT.trojan(slot=1, payload=b"\0" * 4))
            original_files(self.wrap, case["start"], case["flags"], case)
            expected = [b"mass:/POPS/TROJAN_0.BIN", b"mass:/POPS/PATCH_3.BIN",
                        b"mass:/POPS/GAME/TROJAN_1.BIN", b"mass:/POPS/GAME/PATCH_7.BIN"]
            self.assertEqual([path for path in self.wrap.open_paths if path in expected], expected)
            source = (ROOT / "launcher/src/handler_pops.c").read_text()
            self.assertIn("Preserve original root/title and TROJAN/PATCH ordering.", source)

    def test_builtin_undo_census(self):
        refused = {False: [], True: []}
        accepted = {False: [], True: []}
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            root = Path(temp) / "POPS"
            game = root / "GAME"
            game.mkdir(parents=True)
            used = [os.fsencode(str(root) + "/"), os.fsencode(str(game) + "/")]
            for entry in range(1, 625):
                start = bytearray(U.core_image())
                modes = self.wrap.lib.test_builtin(entry, B.buf(start), SIZE)
                if modes < 0:
                    continue
                case = case_from(0, None, None, (None, None), (B.UNDO_LINES[0],),
                                 used[0], used[1], used, self.entry)
                case.update(start=start, builtin=entry, modes=modes,
                            flags={"builtin_id": entry})
                blank = dict(case, bios=(None, None), trojan=(None, None), patch=(None, None), lines=())
                original_base = original_sequence(self.wrap, "files", start, case["flags"], blank)[0]
                original_final = original_sequence(self.wrap, "files", start, case["flags"], case)[0]
                base_current = host_sequence(self.wrap.lib, False, start, blank)[1]
                base_alt = host_sequence(self.wrap.lib, True, start, blank)[1]
                validate_baseline(original_base, original_final, base_current, base_alt)
                for alternate in (False, True):
                    rc, core, _ = host_sequence(self.wrap.lib, alternate, start, case)
                    (refused if rc else accepted)[alternate].append(entry)
                    if not rc:
                        base = base_alt if alternate else base_current
                        expected = normalized(base, original_base, original_final)
                        self.assertEqual(hashlib.sha256(core).digest(), hashlib.sha256(expected).digest(),
                                         (entry, alternate))
        self.assertEqual((len(refused[False]), len(accepted[False])), (0, 624))
        self.assertEqual((len(refused[True]), len(accepted[True])), (0, 624))
        self.assertFalse({109, 571, 572} & set(refused[False]))
        self.assertFalse({109, 571, 572} & set(refused[True]))
        print("Built-in + UNDO_COMPATIBILITY_CODES: current %d refused / %d accepted; "
              "alternate %d refused / %d accepted; accepted final-core hashes match the original" %
              (len(refused[False]), len(accepted[False]), len(refused[True]), len(accepted[True])))

    def test_negative_controls(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            root = Path(temp) / "POPS"
            game = root / "GAME"
            game.mkdir(parents=True)
            (root / "PATCH_3.BIN").write_bytes(B.patch_file(3, modes=(6,)))
            empty = root / "EMPTY"
            (empty / "GAME").mkdir(parents=True)
            used = [os.fsencode(str(root) + "/"), os.fsencode(str(game) + "/")]
            unused = [os.fsencode(str(empty) + "/"), os.fsencode(str(empty / "GAME") + "/")]
            case = case_from(0, None, None, (B.patch_file(3, modes=(6,)), None),
                             (B.MODE_6_LINE, B.UNDO_LINES[1]), used[0], used[1], unused, self.entry)
            results, rc = self.scenario("negative/mode6-then-undo", case)
            self.assertEqual(rc, (0, 0), results)
            self.assertEqual(results["of_vs_oc"], [], results)
            self.assertEqual(results["of_vs_la"], [], results)
            self.assertEqual(results["of_vs_lc"], OSD_DIFF, results)
            self.assertEqual(results["oc_vs_lc"], OSD_DIFF, results)
            self.assertEqual(results["oc_vs_la"], [], results)

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            root = Path(temp) / "POPS"
            game = root / "GAME"
            game.mkdir(parents=True)
            (root / "PATCH_3.BIN").write_bytes(B.patch_file(3, modes=(6,)))
            empty = root / "EMPTY"
            (empty / "GAME").mkdir(parents=True)
            used = [os.fsencode(str(root) + "/"), os.fsencode(str(game) + "/")]
            unused = [os.fsencode(str(empty) + "/"), os.fsencode(str(empty / "GAME") + "/")]
            case = case_from(0, None, None, (B.patch_file(3, modes=(6,)), None),
                             (B.UNDO_LINES[0],), used[0], used[1], unused, self.entry)
            results, rc = self.scenario("negative/patch-then-undo-compat", case)
            self.assertEqual(rc, (0, 0), results)
            self.assertEqual(results["of_vs_oc"], OSD_DIFF, results)
            self.assertEqual(results["of_vs_la"], [], results)
            self.assertEqual(results["of_vs_lc"], OSD_DIFF, results)
            self.assertEqual(results["oc_vs_lc"], [], results)
            self.assertEqual(results["oc_vs_la"], OSD_DIFF, results)


class Source(unittest.TestCase):
    def test_production_order_is_not_changed(self):
        source = (ROOT / "launcher/src/handler_pops.c").read_text()
        helper = source[source.index(B.LAUNCH_HELPER):source.index("int launchPOPS(")]
        self.assertLess(helper.index("res = pops_apply_all_config_patches_rom"),
                        helper.index("res = pops_stage_fix_files"))
        self.assertNotIn("pops_stage_user_files_alt", source)

    def test_alternate_is_test_only_and_runs_real_loader(self):
        text = (ROOT / "tools/test_pops_fix_order.py").read_text()
        self.assertIn("static int pops_stage_user_files_alt", text)
        self.assertIn("T.PATCH_LOADER", text)
        self.assertIn("T.TROJAN_LOADER", text)
        self.assertIn("res = -ENOTSUP;", text)

    def test_ci_runs_this_file(self):
        workflow = (ROOT / ".github/workflows/build.yml").read_text()
        self.assertIn("run: python tools/test_pops_fix_order.py", workflow)


if __name__ == "__main__":
    unittest.main()
