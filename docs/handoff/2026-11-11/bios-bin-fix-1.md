# User BIOS.BIN: answer to review 1

Written by whoever answered the review. Copied as written; not re-verified.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## summary

All review findings are addressed in two new local commits on pr23/rom (worktree the rom worktree); nothing pushed, no console touched. Everything below is host or Unicorn-emulated evidence: NOT TESTED on a console.

MAJOR 1 (launch glue never executed; mutants E and H survived): reproduced (both survived at a3cab9c per the reviewer and the earlier author's run). Fixed by moving the sequence, statement for statement, out of launchPOPS into a static helper `pops_stage_user_files()` in launcher/src/handler_pops.c (look at both BIOS.BIN files -> commands with those flags -> osd_off carry-over -> $RECOMPILER_ADDON jumps -> pops_stage_fix_files -> -EIO check). The earlier author's uncommitted refactor was inspected and kept: the only reordering is that the sequence now runs after two blocks that only write to the debug log. New test class `Launch` builds the helper from handler_pops.c for the host and runs it on real files (all-games only, game only, both, neither, one byte too small, look/load disagreement -> -EIO, error paths, what reaches pops_stage_fix_files). New Original test compares the helper's final core with the original's loader + mode dispatcher + command reader chained in launch order on the real POPS core (270 scenarios). Mutants E and H are now caught, as are 17 further helper mutants.

MAJOR 2 (mutant L survived): reproduced, fixed with a native test (`test_fix_context_takes_pops_own_word_at_the_osd_site_only`): every mode other than 6 with its site at POPS's value is refused, only 0x2525b0 is taken as found. Code unchanged there. L and two variants are now caught.

MINOR: doc and C comment said the loader's entry tests are `bnez`; they compare with 1 (the launch function's tests in front are `bnez`). Docs and comments corrected, and `pops_user_bios_skipped` now uses `== 1` for the one word only the loader tests (all-games gp+0x344c); no launch changes because every store to these words in MAIN is 0 or 1. Doc section 4 item 1 is now scoped to "when a BIOS.BIN is loaded", with the measured rule and the PATCH-mode-6-then-$UNDO example added. Whole-launch equivalence is now measured as one sequence (the 270-scenario row).

Found while testing and NOT fixed (older than this track, same count before its commits): a built-in entry followed by `$UNDO_COMPATIBILITY_CODES` is refused with -EINVAL by the fix-file session, 294 of 624 built-in entries on the real core. Recorded as an expected-failure test and in the doc; see decisions_for_owner.

## commits

1. 781c356 fix(pops): run the BIOS.BIN launch sequence as one step the host tests execute
2. 8649991 docs(pops): correct the BIOS.BIN entry tests and scope the byte-equality claim

## files changed

1. launcher/src/handler_pops.c
2. common/src/pops_modes_patches.c
3. common/include/pops_modes_patches.h
4. tools/test_pops_user_bios.py
5. tools/test_pops_launch_hooks.py
6. tools/test_pops_resident.py
7. docs/POPSTARTER_USER_BIOS.md

## measured evidence

1. Launch sequence vs the original (Unicorn, real POPS core, host build of pops_stage_user_files on real files): 270 scenarios = built-in mode 6 x each folder's BIOS.BIN (none / one byte too small / loaded) x PATCH mode 6 in neither or one folder x 5 command sets. 150 with a BIOS.BIN loaded: whole core and loader words equal. 92 without: equal. 28 without: 0x2525b0 alone differs (original 0x1bfc, launcHER 0x0648), exactly the cases '$UNDO_ command, no built-in mode 6, and mode 6 from a PATCH file or from $COMPATIBILITY_0x06 written before the $UNDO_'. Original side: its BIOS.BIN loader FUN_0088019c, its mode dispatcher FUN_008dc2c4 standing in for a PATCH file's mode byte 6 (its PATCH loader was not run), then its command reader. Emulated, not a console.
2. Gate words holding other values (Unicorn): launch-function tests, loader entry tests, shell slice, mode 6 and region window with a loader word holding 1, 2, 0x80, 0xff against launcHER: 140 cases equal. The loader alone stops only for a 1; the launch function's bnez in front skips the call for every word it tests; only all-games gp+0x344c is tested by the loader alone.
3. Disassembly and store scan of unpacked MAIN (scratch scripts): loader entry tests at 0x8801b4..0x8802ac are 'addiu v0,zero,1' + beq/bne; every gp-relative store to the 7 loader words stores 0 or 1.
4. Class Launch, no reference inputs needed (host, synthetic core, real files): 432 combinations of both BIOS.BIN files x PATCH mode 6 in either folder x 12 pairs of built-in mode 6 and commands, result core and state equal to the documented order with the caller's state pre-filled with 0xff; 4 BIOS.BIN opens in order with nothing read at the two looks; 10 file-changes-between-look-and-load cases each return -EIO and 3 same-answer changes return 0; error stops at the look, at the commands, at the emit, at a refused fix file; arguments reaching pops_stage_fix_files (built-in id, mode mask, video mode, progressive entry, $HDTVFIX word).
5. Mutation runs on exported copies of the tree, tests run WITHOUT reference inputs (what CI runs): 27 mutants. Caught by tools/test_pops_user_bios.py: E (res >= 0 -> res > 0), H (memset removed), L (0x2525b0 condition dropped), L_mode4, L_none, G_gate, G_gate_game, S_seed, S_seed_bit, S_carry, S_cmdstate, S_noeio, S_eio_all_only, S_eio_game_only, S_probe_swapped, S_probe_game_scope, S_emit_dropped, S_gameflag, S_allflag, S_modes, S_builtin, S_video, S_hdtv, S_prog, P_modes, P_dirs. E is caught by 4 executing tests, H by 2 executing tests plus a text pin, L by the new native test. S_seed and S_builtin are caught by a build failure of the host wrapper plus a text pin. P_modes and P_dirs (the call line in launchPOPS) are caught by a text pin only. Survived: S_probe_after ('rom->bios_all = 0;' inserted after the command pass), which is an equivalent mutant (the field is still 0 there).
6. Known gap measured on the real core with the host library, base cfebe01 (before this track's commits) vs the worktree: of 624 built-in entries that apply, pops_fix_context_init_builtin returns -EINVAL after $UNDO_COMPATIBILITY_CODES for 294 in both trees; after $UNDO_GAME_FIXES / $UNDO_LIBCRYPT_FIX for 1 entry at base and 0 in the worktree.
7. Earlier evidence re-run unchanged with inputs: loader 224 runs (88 loads) equal; lseek results 28 equal; reader on files 14 cases + two-folder sequence equal; mode dispatcher 298 equal; parser 72 equal; region window 342 byte-for-byte + 18 outside the PAL sites; shell slice 131 equal.

## tests run

1. **command:** python tools/test_<name>.py for all 27 tools/test_*.py, POPS_TEST_ELF and POPSTARTER_TEST_ELF unset (scratch runner runall.py without)  
   **outcome:** 27 of 27 rc=0. test_pops_user_bios.py: Ran 51 tests, OK (skipped=13, expected failures=1). test_pops_launch_hooks.py: 46 OK (skipped=13). test_pops_resident.py: 75 OK (skipped=12). test_pops_fix_files.py: 31 OK (skipped=3). test_pops_external.py: 128 OK (skipped=14). test_pops_features.py: 29 OK (skipped=2). test_pops_builtin_db.py: 14 OK (skipped=14). test_pops_display.py: 21 OK (skipped=6). Others (launch_args, network_transports, popfs, breakpoint, fatfs, io_probe, modes, module_irx, opcodes, padman, progressive, read_trace, runtime_corrections, startup_calls, vmc, warmboot, smap_ipconfig, sony_ioman_layout, subq_bridge): pass.
2. **command:** same 27 files with POPS_TEST_ELF=<workspace>/POPS/POPS.ELF POPSTARTER_TEST_ELF=<workspace>/POPSLoader/bin/POPSLDR/PROFILES/MAIN/POPSTARTER.ELF (runall.py with)  
   **outcome:** 27 of 27 rc=0. test_pops_user_bios.py: Ran 51 tests, OK (expected failures=1), no skips. test_pops_launch_hooks.py: 46 OK (skipped=3). test_pops_resident.py: 75 OK. test_pops_fix_files.py: 31 OK. test_pops_external.py: 128 OK (skipped=3). test_pops_progressive.py: 8 OK (skipped=3). test_pops_builtin_db.py 14 OK, test_pops_display.py 21 OK, test_pops_features.py 29 OK, test_pops_warmboot.py 7 OK; the rest pass.
3. **command:** python mutants2.py <27 mutant names> (scratch; each mutant applied to an exported copy, tools/test_pops_user_bios.py Native Launch Source and, for some, test_pops_fix_files.py / test_pops_modes.py / test_pops_builtin_db.py / test_pops_resident.py, no reference inputs)  
   **outcome:** 26 caught, 1 survived (S_probe_after, equivalent mutant). E, H and L caught. tools/test_pops_launch_hooks.py could not be built inside the mutant export (third_party/ was left out of the copy), so its result there is not evidence either way.
4. **command:** python gap_base.py <tree> (scratch) on a git-archive export of HEAD~2 (cfebe01) and on the worktree, real POPS core  
   **outcome:** 294 of 624 built-in entries refused (-22) after $UNDO_COMPATIBILITY_CODES in both trees; 1 of 624 refused after each of the other two $UNDO_ commands at base, 0 in the worktree.
5. **command:** git diff --check; grep of the diff and both commit messages for AI attribution  
   **outcome:** clean; no attribution text. None of the six shared docs touched. No new test file, so .github/workflows/build.yml is unchanged (it already runs tools/test_pops_user_bios.py).

## ee build check

Compiler: <ps2build>/toolchain/ee/bin/mips64r5900el-ps2-elf-gcc.exe (GCC 15.3.1 20260823), run from the worktree root on the files as committed.
1. `-fsyntax-only -Wall -Wextra -Icommon/include common/src/pops_modes_patches.c`: rc 0, no warnings.
2. `-c -O2 -G0 -Wall -Wextra -Werror -Icommon/include common/src/pops_modes_patches.c`: rc 0, object written to scratch.
3. `-fsyntax-only -Wall -D_EE -Icommon/include -Ilauncher/include -I<ps2build>/packages/core/{kernel,common,cglue,filexio,debug}/include launcher/src/handler_pops.c`: rc 0, no warnings; the same with `-DLAUNCHER_BOOT_TRACE`: rc 0, no warnings.
4. `-c -O2 -G0 -Wall -D_EE` (same includes) launcher/src/handler_pops.c: rc 0, object written to scratch, 4 warnings (-Wformat-truncation x3, -Wstringop-truncation x1 at lines 1033, 1199, 1211, 1312, all in code this change does not touch); the same 4 warnings come from HEAD (a3cab9c) compiled the same way.
NOT done: no link, no launcher ELF, no CMake build (the project's CMake needs a PS2SDK layout this machine does not have), no resident image rebuild (no resident source changed). Nothing was run on a PS2.

## deviations from original

1. Commands run before the files (older launcHER order). The original loads both BIOS.BIN files and the TROJAN/PATCH files first, then runs CHEATS.TXT. launcHER looks at both BIOS.BIN files without reading them, gives the commands those two flags, then loads. If a load disagrees with the look the launch stops with -EIO (the original has no such state).
2. $UNDO_ commands are applied before the commands' modes regardless of text order, and before the files (older, not changed). Measured consequence over 270 scenarios: with no BIOS.BIN loaded, when a $UNDO_ command is given, the built-in entry did not run mode 6, and mode 6 comes from a PATCH file or from $COMPATIBILITY_0x06 written before the $UNDO_, the original ends with 0x2525b0 = 0x1bfc and launcHER with 0x0648 (28 of 270). Nothing else differed. With a BIOS.BIN loaded all 150 scenarios were equal.
3. KNOWN GAP (older, not the original's behaviour, not fixed): built-in entry + $UNDO_COMPATIBILITY_CODES. The original puts POPS's words back and continues; launcHER refuses the launch with -EINVAL (294 of 624 built-in entries on the real core, host measurement).
4. pops_user_bios_skipped combines the launch function's bnez tests and the loader's compare-with-1 tests in one function. It matches both for every value only because launcHER has no caller that reaches the loader without the launch function's tests; the original's loader called on its own would load with a word holding 2.
5. State width: the original's loader words are 32-bit; PopsUserRomState keeps each as one byte that only ever holds 0 or 1.
6. gp+0x38dc (launch given up), gp+0x3460 (game folder missing) and the eight preset compatibility slots have no counterpart in launcHER.
7. $NOBOOT / $BIOS is launcHER's own command; with a BIOS.BIN loaded it leaves 0x2525b0 alone like the original's writers of that word.
8. The original prints its BIOS.BIN and mode 6 lines through its own print routine; launcHER writes them to the debug log only (nothing on a release build).
9. Fix-file bookkeeping: launcHER checks expected words before each fix file; after a BIOS.BIN load only 0x2525b0 is taken from the core as found. The original has no such checks.
10. Size test on the low 32 bits, signed, of the file size; what the original's drivers return for a file of 2 GiB or more was not measured.
11. Folders: launcHER reads BIOS.BIN from the .VCD's folder and <folder>/<name>/, standing in for the original's POPS/ and POPS/<game>/ (same folders on a mass:/POPS/ layout).

## not done

1. The $UNDO_COMPATIBILITY_CODES-after-a-built-in-entry gap is not fixed (outside the review findings; a proper fix changes pops_fix_context_init_builtin / pops_stage_fix_files signatures that other tracks also touch). It is recorded by Launch.test_undo_compatibility_codes_after_a_built_in_entry (expectedFailure) and in docs/POPSTARTER_USER_BIOS.md. The matrices leave that combination out.
2. The one line of launchPOPS that calls pops_stage_user_files (and the arguments it passes) is still not executed by any host test; it is pinned by text only (mutants P_modes and P_dirs are caught by the pin). launchPOPS itself cannot be built for the host.
3. NOT TESTED on a console. No launcher ELF was linked or run; no CMake build.
4. The original's launch function was not run as one piece under emulation: the comparison chains its loader, mode dispatcher and command reader, each started with the loader words the previous one left. Its PATCH_n.BIN loader was not run (a file's mode byte 6 is represented by FUN_008dc2c4).
5. The 270-scenario chain uses PATCH mode 6 in at most one folder and counter-pattern files, not a PS1 BIOS; no real BIOS was used anywhere.
6. The commit message of 6a7b617 says a built-in entry 58 with a $UNDO_ command no longer fails the launch; measured, that holds for $UNDO_GAME_FIXES and $UNDO_LIBCRYPT_FIX only. History was not rewritten.
7. tools/test_pops_launch_hooks.py was not exercised against the mutants (it could not build in the mutant export, which left third_party/ out); it passes on the real tree both ways.
8. Behaviour for BIOS.BIN files of 2 GiB or more, builds other than MAIN, and the OSD loader that sets the other four loader words remain unmeasured.

## decisions for owner

1. Built-in entry + $UNDO_COMPATIBILITY_CODES is refused with -EINVAL (294 of 624 entries, older than this track). Options: (a) make the fix-file session tokens-aware (pass the $UNDO_ tokens into pops_fix_context_init_builtin so the expected site values are put back to POPS's after the entry's modes are replayed) - exact, but changes a shared signature; (b) generalise the 'take POPS's own word as found' acceptance from 0x2525b0 to every mode site - smaller, but weakens the guard the reviewer just asked to have pinned (the new native test would have to change). I recommend (a), as its own change after the tracks merge.
2. launcHER's older command order ($UNDO_ first, commands before files) still differs from the original at 0x2525b0 in the measured cases (PATCH mode 6 or an earlier $COMPATIBILITY_0x06, then a $UNDO_ command, no BIOS.BIN, no built-in mode 6). Exact parity needs the commands to run after the files in text order; that is a launch-order change pinned by tools/test_pops_launch_hooks.py and was left alone here.

## doc updates


### inventory rows

Replacement text for the user BIOS.BIN row of docs/POPSTARTER_R13_INVENTORY.md (status column: implemented, host/emulated evidence only, NOT TESTED on a console):

| User `BIOS.BIN` (`FUN_0088019c`, called at `0x876cd8` and `0x876fd8`) and the loader words it sets (`gp+0x38a4`, `gp+0x3b98`) with the gates they drive (shell edits, region pass, mode 6, `$UNDO_*`) | Implemented: `pops_user_bios_stage` / `pops_user_bios_load`, `PopsUserRomState`, and `pops_stage_user_files` (the launch sequence as one function). Measured under Unicorn on the real POPS core: loader 224 runs equal; lseek results 28 equal; gates with words holding 1/2/0x80/0xff 140 equal; mode dispatcher 298, command reader 72, shell slice 131, region window 342 equal; whole launch sequence on files 270 scenarios: 150 with a `BIOS.BIN` loaded equal, 92 without equal, 28 without differ at `0x2525b0` only (launcHER's older command order). Known gap (older): built-in entry + `$UNDO_COMPATIBILITY_CODES` is refused with `-EINVAL`. Not tested on a console; no real PS1 BIOS used. See `docs/POPSTARTER_USER_BIOS.md`. |

### quirks

Entries for docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md (no numbers):

- **Loader entry tests compare with 1, the launch function's tests are `bnez`.** `FUN_0088019c` skips a `BIOS.BIN` only when a gate word holds exactly 1; the launch function's tests in front skip for any nonzero value. Every store to these words in MAIN is 0 or 1, so nothing shows in a launch. launcHER copies both (`pops_user_bios_skipped`). Measured under Unicorn, 140 cases.

- **launcHER difference, not the original's: command order shows at `0x2525b0` without a `BIOS.BIN`.** The original runs the fix files, then the commands in text order. launcHER runs `$UNDO_` commands first, then the commands' modes, then the files. With a `$UNDO_` command, no built-in mode 6, and mode 6 from a `PATCH_n.BIN` or from a `$COMPATIBILITY_0x06` written before the `$UNDO_`, the original ends with `0x2525b0 = 0x1bfc` and launcHER with `0x0648` (28 of 270 measured scenarios; nothing else differs). To fix later: run the commands after the files, in text order.

- **launcHER bug, not the original's: built-in entry + `$UNDO_COMPATIBILITY_CODES` refuses the launch.** The original puts POPS's words back and goes on. launcHER's fix-file session still expects the entry's words and returns `-EINVAL`: 294 of the 624 built-in entries on the real core (host measurement), the same before the `BIOS.BIN` work. `Launch.test_undo_compatibility_codes_after_a_built_in_entry` in `tools/test_pops_user_bios.py` is the expected-failure test to un-mark with the fix.

- **A `BIOS.BIN` that changes during launch preparation stops the launch (`-EIO`).** launcHER looks at both files before the commands and loads them after; if a load does not match the look, the launch is refused. The original has no such window because it loads first.

### user facing

For README.md / docs/pops-setup.html (wording for the lead to place; none of this was tested on a console):

- `BIOS.BIN` next to your `.VCD` files applies to every game; `BIOS.BIN` in a game's own folder (the folder named after the `.VCD`) applies to that game and is loaded over the first. As in POPStarter the file is not checked in any way except its size: it must be at least 524,175 bytes (0x7FF8F) and only the first 524,176 bytes are used.
- With a `BIOS.BIN` in use, compatibility mode 6 is not applied (from `CHEATS.TXT`, a `PATCH_n.BIN` or the built-in list), as in POPStarter. On a release build launcHER does not print a notice about this.
- Known issue: `$UNDO_COMPATIBILITY_CODES` in `CHEATS.TXT` for a game that has a built-in fix entry currently makes the launch fail. `$UNDO_GAME_FIXES` and `$UNDO_LIBCRYPT_FIX` are not affected.
- Known difference from POPStarter: when `CHEATS.TXT` has a `$UNDO_` command together with mode 6 from a `PATCH_n.BIN` (or `$COMPATIBILITY_0x06` written above the `$UNDO_` line) and no `BIOS.BIN` is used, POPStarter ends with the BIOS shell skip off and launcHER with it on.

### hardware checklist

Console checks still owed for this feature (nothing here has been run on a PS2):
1. No `BIOS.BIN`: a game launches as before (regression check of the moved launch sequence).
2. `BIOS.BIN` (a real dump, 0x80000 bytes) in the all-games folder only: game boots; debug log shows the load; compare against POPStarter r13 with the same file.
3. `BIOS.BIN` in the game's folder only, and in both folders (game's one wins).
4. A file of 0x7FF8E bytes (one too small): not loaded, launch continues, as POPStarter.
5. `BIOS.BIN` + `$COMPATIBILITY_0x06` in `CHEATS.TXT`: mode 6 not applied, game boots through the user's BIOS.
6. `BIOS.BIN` + `$UNDO_GAME_FIXES`: launch succeeds.
7. A game with a built-in entry + `$UNDO_COMPATIBILITY_CODES`: expected to FAIL to launch today (known gap); record the on-screen result.
8. `PATCH_n.BIN` with mode byte 6 + `$UNDO_GAME_FIXES`, no `BIOS.BIN`: record whether the BIOS shell is shown on launcHER and on POPStarter (expected to differ).
9. Both storage back ends (HDD pfs and USB mass) for 2 and 3.
