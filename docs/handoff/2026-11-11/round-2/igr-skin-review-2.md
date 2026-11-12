# IGR skin (IGR_BG/NO/YES.TM2): review 2

Target: e9224cf + 173d5de (fix eb976d1), as present at ef663b2 on
codex/popstarter-replacement. Read-only review. `<scratch>` =
<scratch>/audit-igr.
All runs used a detached worktree `<scratch>/tree` at ef663b2, TMP/TEMP/TMPDIR
set to `<scratch>/tmp`, one test at a time. Nothing was run on a console or on
PCSX2. Everything called "verified" below was run by me.

## Verdict

merge-after-fixes. The code matches the original wherever it is meant to and
every first-review finding that asked for a code or test change is fixed and
holds under my own checks. Three minor findings remain, all about claims and
documents, none changes a byte of the staged core.

## First-review findings: were they fixed?

| # | Review-1 finding | State at ef663b2 | Evidence I produced |
|---|---|---|---|
| 1 | Skin staged before the built-in entry; claim of original order wrong | **Fixed.** Call is at handler_pops.c:1657, after `pops_builtin_apply` (1637) | My scan of unpacked MAIN (`<scratch>/scripts/callers.py`): `0x87e464` has one caller, `jal 0x876b18`; `0x8ff0e4` callers 0x8757d4, 0x875d70, 0x875f78, 0x8762a8, 0x876424, 0x8769ac (all below 0x876b18); BIOS.BIN loader `0x88019c` at 0x876cd8/0x876fd8 and parser `0x883270` at 0x8771ac/0x87724c (all after). Staging.test_builtin_entry_and_skin_commute passes. |
| 2 | Reader never executed; 6 of 7 mutants survived | **Fixed.** Reader class compiles `pops_stage_igr_skin` from handler_pops.c and runs it | 7 fresh mutants of my own (not in the fixer's list), no inputs: B (stop after a short count, i.e. original-like single read) CAUGHT 2 failures; C (`<` -> `<=` in core-size check) CAUGHT 2; E (64 KiB+1 requests) CAUGHT 5; J (failed size query stages zeros) CAUGHT 2; M (YES never tried) CAUGHT 11; N (no zero fill for a 0-byte file) CAUGHT 5; P (call moved below the breakpoint-area check) SURVIVED, equivalent (that check only reads and returns before any later stage). Worktree restored after each (`git status --short` empty). |
| 3 | Skin before runtime corrections makes them return -4 (fatal) | **Fixed.** Runtime corrections at handler_pops.c:1588-1595, straight after core patches, before hooks and skin | RealCore.test_a_skin_before_the_runtime_corrections_stops_the_launch and test_whole_launches_keep_the_skin pass with POPS_TEST_ELF. |
| 4 | Non-overlap claim overstated | **Fixed for the stages that existed at eb976d1**; see new finding 1 for stages the BIOS.BIN merge added | RealCore.test_stages_after_the_skin_leave_it_alone passes. |
| 5 | Short-read model mixed "per read" and "total" | **Fixed.** SkinFile has `total` and `per_read` separately; reader run in both | Reader/Original pieces and stops tests pass; my own 20 extra device runs (random `total`, `after` in {0,-5,-19}, size/data mismatch) give the original's core from the reader in 20 of 20. |
| 6 | Import error became a skip; run count not asserted; size-failed case ran only the original | **Fixed.** Original is `skipUnless(HAVE_EMU)` with HAVE_EMU = both inputs set, so a broken unicorn import errors; each Original test asserts its own count; failed-size test runs the reader | Read tools/test_pops_igr_skin.py:57-60, 1387, 1548-1572. Verbose run printed "runs of the original's loader: 141". |
| 7 | Two stand-ins for the device POPS folder | **Open, documented as owner decision** (doc "Where the files go", handoff section 8) | See new finding 3 for one launch kind the doc does not cover. |
| 8 | Wording: -666, over-reported count, scratch wording | **Fixed.** Header now names the -666 path; an over-reported count is taken as the request (`got += n > chunk ? chunk : n`); doc scratch wording corrected | Read pops_igr_skin.h:14-18, handler_pops.c:486-490; Original/Reader "extra" family (8 runs) passes. |
| U7 | "Ember launches never reach this code" untested | **Fixed.** Source.test_call_position pins `launchPOPS` as reached only behind `isPopsTarget` in common.c | Test passes. |

## Tests run (verified)

1. `python tools/test_pops_igr_skin.py` (no inputs): Ran 48, OK (skipped=21).
2. Same with POPS_TEST_ELF, POPSTARTER_TEST_ELF, POPS_IGR_SKIN_COUNTS=1, `-v`:
   Ran 48, OK, 0 skipped; "runs of the original's loader: 141". Log
   `<scratch>/withrefs.log`.
3. `tools/test_pops_launch_hooks.py`: no inputs Ran 48 OK (skipped=14);
   with inputs Ran 48 OK (skipped=3).
4. `tools/test_pops_doc_claims.py`: no inputs Ran 12 OK (skipped=7); with
   inputs Ran 12 OK.
5. Fresh-seed emulation (`<scratch>/scripts/fresh_emu.py`, seed 0xBEEF1234,
   through the test's own `Original.compare` / `reader_matches`): 60
   whole-file runs (30 random sets x 2 backends, sizes including 0, 1,
   max-1, max, max+1, slot) and 20 misbehaving-device runs. Every run: the
   emulated original equals the model, `pops_igr_skin_stage` and launcHER's
   host-compiled reader over the whole core, return 1, nothing outside
   changed, all files closed. Per-file outcomes: BG 32 LOADED / 18 NOT FOUND
   / 10 TOO BIG, NO 36/16/8, YES 40/8/12.
6. EE compile at ef663b2 (mips64r5900el-ps2-elf-gcc 15.3.1 from
   `%LOCALAPPDATA%/ps2dev`): common/src/pops_igr_skin.c with `-D_EE -O2 -G0
   -Wall -Wextra -Werror` rc 0, text 388 bytes; launcher/src/handler_pops.c
   with `-D_EE -Os -G0 -Wall` and the kernel/cglue/filexio/common/debug/
   iopreboot/sifcmd package includes, three variants (plain,
   `-DENABLE_PRINTF`, `-DLAUNCHER_BOOT_TRACE`): rc 0 each, 19/23/19
   warnings, none on the reader (lines 430-509) or the call (1640-1660);
   object references `pops_igr_skin_slot` and `pops_igr_skin_stage`. Not
   linked, no CMake or container build.
7. Mutants: listed under first-review finding 2.

## New findings

### 1. minor: the "whole launch" test and its doc claim no longer follow launchPOPS

`RealCore.launch` (tools/test_pops_igr_skin.py:1143-1194) says, through
`test_whole_launches_keep_the_skin` (docstring at 1197: "Every staging call
launchPOPS makes on the core, in its order"), and the doc says
(docs/POPSTARTER_IGR_SKIN.md:252: "21 whole launches in `launchPOPS`'s
order"), that the launch is replayed as launchPOPS runs it. Since the
BIOS.BIN merge (0945127) launchPOPS calls `pops_stage_user_files`
(handler_pops.c:1683), which runs `pops_user_bios_load`,
`pops_fix_context_rom_loaded` and `pops_fix_stage_rom`, and then
`pops_apply_bios_shell_edits_rom` / `pops_apply_region_rom` (1714, 1722).
The replay still calls `pops_fix_stage`, `pops_apply_bios_shell_edits` and
`pops_apply_region` and never loads a BIOS.BIN; ef663b2 updated only the
text pins in `Source.test_call_position`. The doc's launch-order table also
leaves BIOS.BIN out of the stages after the skin. No IGR test runs the
BIOS.BIN stage over a skin.

No byte consequence found: `<scratch>/scripts/rom_launch.py` runs, over the
real core with the skin staged by launcHER's reader, `pops_fix_context_init_builtin`,
`pops_user_bios_stage` (0x7ff90-byte file, per-game and all-games),
`pops_fix_context_rom_loaded`, `pops_fix_stage_rom`, `pops_fix_finalize_video`,
`pops_apply_bios_shell_edits_rom` and `pops_apply_region_rom` for built-in 0,
1 and 508 with no / game / all BIOS.BIN: 9 cases, every call returns 0 or 1
as expected, skin range unchanged in 9 of 9. By address, the BIOS.BIN range is
0x24bc20..0x2cbbb0 (pops_modes_patches.h:39-40), below 0x2feff0.

Fix: replay `pops_stage_user_files`'s calls (or the `_rom` functions with a
`PopsUserRomState` and a BIOS.BIN case) in `RealCore.launch`, and add BIOS.BIN
to the doc's order table and to the "later stages" list.

### 2. minor: user-facing and status documents still say the skin does not exist

At ef663b2:
- README.md:718: "Custom IGR graphics (...): not implemented. This branch has
  no code that reads them".
- docs/pops-setup.html:554: "This branch of launcHER has no code that reads
  these files, so placing them has no effect."
- docs/POPSTARTER_R13_INVENTORY.md:199: IGR menu skin row "**MISSING**: no
  code".

The code reads `<VCD folder>/IGR_*.TM2` on every POPS launch
(handler_pops.c:1657, unconditional, pinned by Source.test_call_is_unconditional).
A user who follows the README is told the files have no effect; in fact a file
there replaces Sony's picture (a 0-byte file blanks it), visible under
`$IGR0..2`. The handoff (docs/PR23_HANDOFF_2026-11-11.md:52-54) lists the
pieces whose shared documents were not updated as BIOS.BIN, SMB, disc and
config-text; the IGR skin is not in that list, although its shared rows were
not updated either (the fixer's report put the proposed text under
"doc updates" and "not done" 6). Fix: apply the fixer's proposed README,
setup-page and inventory text, or add the IGR skin to the handoff's list.

### 3. minor: the folder difference is not described for SB. launches

docs/POPSTARTER_IGR_SKIN.md "Where the files go" covers USB (`mass:/POPS/`)
and HDD (`pfs1:/POPS/`). For an SB. (SMB) launch the original sets the
backend flag to the mass value: in MAIN, the name test at 0x871568 ('S'),
0x87158c ('B'), 0x871600 ('.') (lowercase at 0x8715b0/0x8715d4) leads to
`sw $v0(=1), 0x3448($gp)` at 0x871618 and `gp+0x3888 = 3` at 0x871620; the
only other stores to gp+0x3448 are 0x870c64 (0) and 0x8719a4 (1, XX.) (my
gp-offset scan; same list as POPSTARTER_GAP_AUDIT_2026-11-11.md:179). The
IGR loader then opens the literal `mass:/POPS/IGR_*.TM2` (0x87e534 ->
wrapper 0x8d6c94 -> 0x91ba70, which copies the path into a fileXio-style
RPC without rewriting it, read at 0x91ba70..0x91bb0c). launcHER reads the
files from the SMB share's VCD folder (`vcdDir`). Whether `mass:` names a USB
device or the SMB share once POPStarter's SMB modules are up was not traced,
so the two may or may not be the same place; read from code, not run. Fix:
add SB. (and XX., which uses `mass:/POPS/` too) to "Where the files go" with
that open question.

## Checked and found right (no finding)

- Table, limits, zero fill and outcomes: equal to the emulated original in 141
  test runs and my 80 fresh runs.
- Reader on a device that over-reports, stops for good, or disagrees with its
  size query: original's slot in all runs (test families plus my 20).
- Listed differences (failed size query leaves the core alone; a file
  delivered in pieces is staged whole) behave as the doc says (tests pass).
- Scratch use: the largest skin read ends at 0x01f4c300; the loose-ELF
  scratchpad staging is at 0x01f80000 (handler_pops.c:1495). The skin copy
  happens in the same call as the read, so nothing later depends on the
  scratch contents.
- BIOS.BIN (0x24bc20..0x2cbbb0) cannot reach the slots (arithmetic and the 9
  runs in finding 1).

## Not done

- Nothing on a console or PCSX2.
- No link or target build.
- The POPS-folder check FUN_008d8958 and what `mass:` names in POPStarter's
  SMB mode were not traced.
- Only the three test files named above were run, not the full tools/ list.

## Cleanup

The worktree `<scratch>/tree` was removed with `git worktree remove --force`
followed by `git worktree prune` (prune only drops entries whose folders are
gone; the listing afterwards still shows every other worktree). The main
checkout's `git status --short` is empty.
