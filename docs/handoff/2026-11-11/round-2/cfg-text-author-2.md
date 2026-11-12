# CHEATS.TXT command pass: answers to review 1 (cfg-2)

Branch `pr23/cfg-2` (worktree `launcHER.worktrees/cfg-2`), based on `ef663b2`. Pushed to `origin/pr23/cfg-2` only. Nothing was run on a console: NOT TESTED on a console. Host tests and Unicorn emulation of single routines of the original only. No emulator, no rig.

## Commits

1. `e9d1b03` wip(pops): cherry-pick of `origin/pr23/cfg` `6ced397`, message kept. The `cfg` worktree was not touched.
2. `2ccf68b` fix(pops): $FORCEPAL after $480P, $NOPAL after $FORCEPAL, token bytes as the original (C, header, tests).
3. `c05ddb6` docs(pops): docs/POPSTARTER_CONFIG_TEXT.md and tracer notes.

Files: common/src/pops_config.c, common/include/pops_config.h (new trailing field `forced_pal`), tools/test_pops_features.py (ctypes mirror gets `forced_pal`), tools/test_pops_config_text.py, tools/trace_original_pops_config_text.py, docs/POPSTARTER_CONFIG_TEXT.md. No shared launch, storage-driver or Ember code changed. None of the off-limits docs edited.

## Findings

1. **$FORCEPAL after $480P**: CMD_FORCEPAL (from 6ced397) stores nothing while `progressive_requested` is set; effect 0. Measured against the original: the tracer shows `$480P $FORCEPAL ` -> FORCEPAL 0 effects, gp+0x38a0 stays 0. Added a comparison of the three video words the region pass reads (gp+0x38a0, 0x3864, 0x4fa0, mapped through `original_video` / `launcher_video`) to every `compare()` (167 fixed, 1500 random, etc.), plus 18-text table, 600 random video texts, two files (second run with the first's gp words; launcHER through `pops_config_discover`): 6 fixed + 441 pairs, all equal.
   Also found while doing it: 6ced397 made `$NOPAL` keep NTSC2PAL after `$FORCEPAL` (correct for the original: $NOPAL clears only 0x4fa0; region pass reads 0x38a0 first, read from code 0x879034..0x8795f0), but it also changed launcHER's own `$NTSC2PAL $NOPAL` (an owner-decision token) from NOPAL to forced, which failed `Native.test_launcher_tokens_keep_their_line_rules`. Fixed with a new field `forced_pal` (the original's 0x38a0): set by $FORCEPAL, cleared by $480P (and in `pops_config_load_table` for byte 26 == 2), read by $NOPAL only. `$NTSC2PAL $NOPAL` keeps today's NOPAL.
2. **Mutants K and K3**: 47 EXPECTED rows added (generated from the original's run, then checked by `Original.test_table_is_the_original`). Mutation run (own copy per mutant via git archive of 2ccf68b, own TMP/TEMP/TMPDIR, sequential, `Native Source` only, no reference inputs, i.e. what CI runs): K CAUGHT (Native.test_table), K3 CAUGHT (Native.test_table). Further conditions of command_code_columns: C1-C4, C6-C11 CAUGHT. **C5 SURVIVED**: dropping `t[1] == '3'` from the 14-column kind; no fixed text holds a 14-column `$3` code. NOT FIXED: needs e.g. `"$30012345 1234 $NOPAL "` and `"$30212345 1234 $NOPAL "` with their EXPECTED rows from the original. Mutants C12-C18, V1-V4, T1-T3 were still running when I was stopped; their results are in `<scratch>/cfg2/mut-native-head.out` if it completed. The base run of K/K3 at ef663b2 was queued after it (`<scratch>/cfg2/mut-native-base.out`); not read.
3. **63-byte cut**: `launcher_token_run` (from 6ced397) makes a run over 63 bytes no token, tail included. Native.test_launcher_token_bytes pins 63/64 boundaries; Original.test_random_token_bytes: 500 random texts with long runs, all equal to the original.
4. **Byte classes**: `token_space`/`token_digit` (from 6ced397). Native test: `\xa04 ` -> 0, `\xa0 4 ` -> mode 4, `\x85`, `\x1c`, `\x1f`, VT/FF/CR cases. Source test: no isspace/isdigit/isalpha/isalnum/isxdigit call in pops_config.c. `toupper` remains in launcHER's cheat scanner (cheat_nibble, cheat_code_at): it only compares against ASCII, so a locale mapping of high bytes cannot change a result; not changed.
5. **Short files**: tracer `beyond` parameter (from 6ced397); the code zeroes the second half itself (0x883aa8 loop; tracer now puts 0xA5 there first and all tests still pass). Original.test_short_files: 357 texts of 1..8 bytes equal launcHER with a zero heap; with 4 heap patterns, 17 of 1428 runs step over a code at a '$' with i + 9 >= 2*size, no command changes in any run; `$800` + spaces -> 14-column code in the original, none in launcHER. Documented.
6. **Counts**: print now "5 texts x 6 starting values (30 runs)". The wrong commit message is `b205a3e`: it says "four former known differences" for test_pops_warmboot and test_pops_builtin_db; the diff changes four in test_pops_warmboot.py and five in test_pops_builtin_db.py (x$VCDID_9999 plus four $FAKELC forms), nine in all. History not rewritten.
7. **TMPDIR**: recipe with TMP, TEMP and TMPDIR in the test's docstring and in docs/POPSTARTER_CONFIG_TEXT.md. compile_shared_library not changed.

## Commands run and results

- `python tools/trace_original_pops_config_text.py` on 8 video texts (POPSTARTER_TEST_ELF set): gp stores as quoted in the doc.
- Static scans of the image (scratch scripts dis_main.py, gpscan.py): loads/stores of gp+0x3864, 0x38a0, 0x4fa0, 0x38d0, 0x3898; disassembly 0x8839d0.., 0x885a04.., 0x8987d0.., 0x879020.., 0x8792e0.., 0x882f80.., 0x871190.., 0x8716f0.., 0x883080.., 0x883150...
- `xxd` of the four profile ELFs at 0x413/0x417: MAIN 02/01, DEBUG 02/01, USBDELAY 06/01, USBDELAY_DEBUG 06/01 (confirms the doc's statement the review could only check for MAIN; no test pins it).
- `tools/test_pops_config_text.py` at the state committed as 2ccf68b (before the print-count line, which only adds a count): with POPSTARTER_TEST_ELF and POPS_TEST_ELF: Ran 32, OK, 251.8 s; prints 167 fixed texts, 1500 random (2876 commands, 399 codes, 96 MODE, 20 0x100017), 500 token texts, 300 USBDELAY (84), 30 runs, 357 short files (17 of 1428), 600 video random, 18 video table, 6 + 441 two-file pairs, VMCDIR 39/30 and 400 (212/188), 21 modes x 2. Without inputs (after the print change): Ran 32, OK (skipped=15).
- Mutant run as in finding 2.

## Not done

- **The full host-test sweep was not run** (every tools/test_*.py, twice). Only tools/test_pops_config_text.py was run. tools/test_pops_features.py (mirror changed) and the other files that load PopsConfig were not run after the struct change. NOT RUN.
- **Target build (Docker) not run.**
- C5 survivor (finding 2) not killed; remaining mutant results not read.
- Re-run of the config text test with inputs after the docs commit (only docs/tracer docstring changed).

## Proposed quirk / doc text (for the coordinator)

- Quirk: "$FORCEPAL does nothing after a $480P, also across the two CHEATS.TXT files (0x8987f0 tests gp+0x3864). Matched in launcHER (pr23/cfg-2)."
- Quirk: "$NOPAL does not undo an earlier $FORCEPAL: it clears only gp+0x4fa0, and the region pass tests the forced-PAL word first. Matched in launcHER (forced_pal)."
- Quirk: "CHEATS.TXT of 8 bytes or less: the code test reads past the 2*size buffer; whether such a '$' is a code depends on the heap. launcHER reads zeros; no command can differ (measured, 1428 runs)."
- Inventory row note: the $FORCEPAL test does not model the original's non-text sources of gp+0x3864 (0x871218, 0x871718, 0x88301c/0x8830a4/0x883174, read from the code).

## Open questions for the owner

1. (Unchanged, handoff section 8) Should launcHER-only tokens, bare digits and `MODE n` stop being read from CHEATS.TXT, and where should they be read instead? Nothing about whether they are read was changed; only how a token is split (ASCII white space, no 63-byte cut).
2. launcHER's own `$NTSC2PAL` / `$PAL2NTSC` keep "last one wins" against $NOPAL / $FORCEPAL; the video words are not compared in texts that hold them. Keep?
