# User BIOS.BIN: review 2

Target: merge 0945127 (user BIOS.BIN and the loader state), as found at ef663b2 on
codex/popstarter-replacement, and docs/POPSTARTER_USER_BIOS.md. First review:
docs/handoff/2026-11-11/bios-bin-review-1.md; answers: bios-bin-fix-1.md.

`<scratch>` = <scratch>.
Everything below is a host or Unicorn result on a detached worktree of ef663b2
(`<scratch>/audit-bios/tree`, plus `<scratch>/audit-bios/base` at 173d5de, the
parent before the merge). Both worktrees were removed when the review ended. Nothing
in any repository was changed. Nothing ran on a console. "Verified" means I ran it.

## Verdict

merge-after-fixes. The merged piece does what it says. Every first-review finding is
fixed, and I checked each fix by re-running its mutant or reading the disassembly. The
fixes listed below are doc corrections plus the 5.5 refusal, which is older than this
piece. That refusal is a real launch failure (294 of the 624 built-in entries) and
should be fixed before anyone relies on `$UNDO_COMPATIBILITY_CODES`. The measurements
below show it is a guard-only problem with a cheap fix.

## Tests run (verified)

TMP/TEMP/TMPDIR = `<scratch>/audit-bios/tmp` (tmp2 for the full run), PYTHONDONTWRITEBYTECODE=1, one file at a time.

- `python tools/test_pops_user_bios.py`, no reference inputs: `Ran 51 tests ... OK (skipped=13, expected failures=1)`.
- The same with POPSTARTER_TEST_ELF and POPS_TEST_ELF set (`-v`, log `<scratch>/audit-bios/ub_with.txt`): `Ran 51 tests ... OK (expected failures=1)`. The printed rows match doc section 5: 140 gate cases; loader 224 runs (88 loads); lseek 28; launch chain 270 (150 / 92 / 28 at 0x2525b0); dispatcher 298; parser 72; reader 14 + two-folder sequence; region 342 + 18; shell 131.
- All 32 `tools/test_*.py`, with the reference inputs (`<scratch>/audit-bios/all_with.txt`): 32 of 32 rc=0. test_pops_launch_hooks 48 OK (skipped=3), test_pops_external 128 OK (skipped=3), test_pops_progressive 8 OK (skipped=3), test_pops_igr_skin 48 OK, test_pops_doc_claims 12 OK, test_pops_fix_files 31 OK, test_pops_resident 75 OK, test_pops_user_bios 51 OK (expected failures=1).
- The full suite without the inputs was not run. Only test_pops_user_bios.py was run that way, plus 11 mutant runs.

## First-review findings, re-checked

| # | First review | State at ef663b2 | Evidence (mine) |
|---|---|---|---|
| 1 major | launch glue never executed; mutants E, H survived | FIXED | `<scratch>/audit-bios/scripts/mutants.py` on a copy of the tree, no reference inputs. E (`res >= 0` -> `res > 0` before the game look): rc=1, 4 failures (test_a_file_that_changes_under_the_launch, test_commands_and_files_in_every_combination, test_the_state_passed_in_is_not_read, test_what_the_commands_see). H (`memset(rom, 0, ...)` removed from pops_stage_user_files): rc=1, 2 failures + 1 error. The one call line in launchPOPS is still pinned by text only, as fix-1 says. |
| 2 major | mutant L (0x2525b0 restriction dropped) survived | FIXED | L: rc=1, test_fix_context_takes_pops_own_word_at_the_osd_site_only fails. It also turns the expected failure into an unexpected success; see finding 1 below. |
| 3 minor | doc said `bnez` for the loader's entry tests | FIXED | Disassembly of 0x8801b4..0x8802ac: `addiu v0, zero, 1` + beq/bne. Launch-function tests 0x876bb4..0x876cd0 and 0x876ea8..0x876fd0: `bnez` on 0x38dc/0x343c/0x3430 (all games) and 0x38dc/0x3460/0x3878/0x344c (game), then the eight preset slots. Code line 94 `state->osd_game_b == 1`. Mutant N1 (`== 1` dropped): caught by test_user_bios_entry_gates. |
| 3b | "every store is 0 or 1" (fix-1's basis for the above) | CONFIRMED | `<scratch>/audit-bios/scripts/gpstores.py`: all 50 gp-relative sb/sh/sw to the 10 loader words in unpacked MAIN store $zero or a register loaded with `addiu v0, zero, 1`. |
| 4 minor | section 4 item 1 unscoped | FIXED | Doc now says "When a BIOS.BIN is loaded ..."; the 28 no-BIOS cases are listed in difference 2 and are printed by the test. |
| 5 minor | whole-launch equivalence not measured | FIXED (pieces chained) | The 270-scenario row runs and passes. As the doc says, it chains the original's pieces, not its launch function. |

Extra mutants of mine, all caught without the reference inputs: N2 (osd_off carry-over removed), N3 (pops_fix_context_rom_loaded skipped), N4 (size test off by one: accepts 0x7ff8e), N6/N7 (region / shell pass given NULL instead of the state; caught by a source pin only), N9 (rewind removed), N10 (0x2525b0 guard blesses any value). Log: `<scratch>/audit-bios/mutants_without.txt`.

## Findings

### 1. major (older than this piece): built-in entry + `$UNDO_COMPATIBILITY_CODES` refuses the launch (handoff 5.5). Bytes are already right; only the guard is wrong.

- Run through the real helper (`pops_stage_user_files`, host build of handler_pops.c) on the real core, all 624 entries that apply (`<scratch>/audit-bios/scripts/gap55.py`). No command: 624 rc=0. `$UNDO_COMPATIBILITY_CODES`: `{-22: 294, 0: 330}`. The same with an all-games BIOS.BIN loaded: `{-22: 294, 0: 330}`. `$UNDO_GAME_FIXES` and `$UNDO_LIBCRYPT_FIX`: 624 rc=0. The refusal comes from pops_fix_context_init_builtin, which pops_stage_fix_files calls before any file is read. So the launch fails even when there is no TROJAN, PATCH or BIOS.BIN file at all.
- Older than this piece (`gap_old.py`; old order modelled as entry -> config pass -> init_builtin). At 173d5de: UNDO_COMPAT `{-22: 294, 0: 330}`, UNDO_GAME_FIXES and UNDO_LIBCRYPT_FIX 1 refusal each. At ef663b2: 294 / 0 / 0. That matches fix-1.
- Guard only (`gap_all.py`). For all 294 refused entries I ran the original's own command reader under Unicorn (`U.parser("$UNDO_COMPATIBILITY_CODES")` on the core after the entry, blob sites 0x2397d8/0x239780/0x239784 set aside). Its bytes are equal to launcHER's config pass in 294 of 294, after setting aside the 16 bytes launcHER's config pass writes with no command. So launcHER already writes what the original writes; the session just refuses to go on.
- Refused by mode mask: 0x8 188, 0x1 45, 0xa 23, 0x9 11, 0x10 11, 0x4 9, 0x0 3, 0x2 3, 0x28 1. Three entries with **no compatibility mode** (109, 571, 572) are refused too. Their direct core write sets 0x21af70 from 0x24020064 to 0x24020032, and the `$UNDO_` write puts 0x64 back (`gap_mask0.py`).
- Consequences:
  - Doc section 4, the handoff and the user-facing note say "a built-in entry with compatibility modes". That is not exactly right: 3 of the 294 have none.
  - Fix option (a) in fix-1 says "after the entry's modes are replayed". It must also cover the entry's core writes (builtin_expected's POPS_BUILTIN_OP_CORE branch), or entries 109/571/572 stay refused.
- Option (b) measured (`<scratch>/audit-bios/mutL`: mutant L, which accepts POPS's own value at every site). gap55 gives 0 refusals of 624 for every `$UNDO_` with and without a BIOS.BIN. test_pops_user_bios: only the new pin test fails, and the expected failure passes ("FAILED (failures=1, unexpected successes=1)"). So (b) needs no other change, but it gives up the guard at every site.
- Fix: option (a) with the `$UNDO_COMPATIBILITY_CODES` write list (undo_writes) applied to `candidate.expected` after the replay, covering both modes and core writes. Then remove the expectedFailure and add entries 109/571/572 as cases.

### 2. minor: doc gives the wrong address for the size test

docs/POPSTARTER_USER_BIOS.md line 23 says "Size test (`0x8803d0`)". Word-by-word disassembly (`<scratch>/audit-bios/scripts/mydis.py`):
- 0x8803d0 is `sb v0, 0x20(fp)`, which builds the "pfs" path string.
- The compare is at 0x880894..0x8808a0: `lui v1,7; ori v1,v1,0xff8e; slt v0,v1,v0; beqz v0,0x88093c`.
- The mass back end sign-extends the lseek result first (0x880874/0x880878, dsll32/dsra32).

Fix: use 0x88089c.

### 3. minor: notes on the gap say "for a game that has a built-in fix entry"

The quirks/user-facing text in fix-1 is "makes the launch fail" for any game with a built-in entry. Measured: 294 of 624 entries; mode-6-only entries and 327 others launch. Same evidence as finding 1. Fix: say "most built-in entries that set compatibility modes 1-5, and three that write mode 4's word directly".

## Fresh review: checked and found consistent (verified)

- **ROM-range writers.** Every hard-coded address in common/, launcher/src/handler_pops.c and the headers that falls in 0x24bc20..0x2cbbaf: 0x2525b0, 0x263ca8, 0x263d56, 0x263db0, 0x263ed6, 0x264994..0x2649a0, 0x2cbb4c (warm-boot scan top), 0x2cbb72. 0x263ca8 (pops_core_patches_stage, handler line 1578) runs before pops_stage_user_files. The original also writes it before its loads (FUN_008dba90 at 0x874aac, launch function 0x870b78; loader calls at 0x876cd8/0x876fd8). The rest are the gated shell/region/mode-6/undo writes. The opcode pass ends at 0x24bc1f. The IGR skin slots (0x2feff0, 0x34b2f0, 0x34d0b0) are outside the range.
- **Writers of osd_off (gp+0x3704) in MAIN.** Only FUN_0087cf68 (zero stores, called at 0x8743d8, early in the launch function), FUN_008db97c (=1; called at 0x874a84 only when preset gp+0x3438 == 1, and at 0x8dc78c in the mode-6 arm) and FUN_008dba20 (=0; called only from 0x87f950). The `$UNDO_` handlers do not store it, so the doc's "They never clear gp+0x3704" holds. gp+0x3438 is set only at 0x87109c, from byte 0x100021 (0 in MAIN per the gap audit).
- **Loader flag stores and poke.** 0x880920 (game) / 0x880930 (all), then the poke16(0x20079a, 0x1000) at 0x88099c, return 1. The too-small path at 0x88093c closes and returns 0. Matches pops_user_bios_stage.
- **Fix-context sites inside the loaded range.** Only 0x2525b0 among compat_patches. The PAL sites (0x21af94, 0x502770, 0x23b018, 0x23b01c) and the resident sites (0x21a094..0x23ad0c) are outside. So pops_fix_context_rom_loaded re-reading only in-range compat sites is complete.

## Not done

- No console or PCSX2 run, no target build or link.
- The full suite was run only with the reference inputs.
- No real PS1 BIOS was used.
- The original's launch function was not run as one piece.
