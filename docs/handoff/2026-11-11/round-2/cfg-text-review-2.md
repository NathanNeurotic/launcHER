# Review of pr23/cfg-2 (CHEATS.TXT command pass, answers to review 1)

Reviewed: `origin/codex/popstarter-replacement...origin/pr23/cfg-2`, head `c05ddb6` (commits `e9d1b03`, `2ccf68b`, `c05ddb6`). Read-only: nothing committed or pushed. Detached worktree `<scratch>/review-cfg/tree`, removed at the end (`git worktree list` no longer shows it). Nothing was run on a console: NOT TESTED on a console. No emulator, no rig. "Under emulation" below means Unicorn runs of the original's routines inside host tests.

## Verdict

merge-after-fixes. One blocker: `tools/test_pops_features.py` fails on the PR head, with and without reference inputs, and CI runs it. The fix is one test line. Everything else in the code change agrees with the original in every differential I ran.

## Findings

### 1. BLOCKER: tools/test_pops_features.py fails on the head (CI goes red)

- `tools/test_pops_features.py:948`, `test_config_parser_directives`: `AssertionError: 4 != 2`.
- Cause: the test feeds `$480p` to the same config earlier (line ~877). Since `2ccf68b`, `$FORCEPAL` does nothing after a `$480P`, which matches the original. The test still expects the old `video_mode == 2`.
- The new behaviour is right. The test expectation is stale.
- CI runs this file (`.github/workflows/build.yml:32`, without reference inputs).
- Measured:
  - Head without inputs: `Ran 29 ... FAILED (failures=1, skipped=2)`.
  - Head with inputs: `FAILED (failures=1)`, same assertion.
  - Base `origin/codex/popstarter-replacement` (git archive copy) without inputs: `Ran 29 OK (skipped=2)`.
  - Head with only line 948 changed to `4`: `Ran 29 OK (skipped=2)` without inputs and `Ran 29 OK` with inputs. Only this assertion breaks.
- The author's report says the full sweep was not run.
- Fix: change the expectation to 4 and add a comment saying `$FORCEPAL` is gated by the earlier `$480p`. Or call `pops_config_init` before the `$FORCEPAL` line if that line is meant to test `$FORCEPAL` alone (it would then still expect 2).

### 2. minor: mutant C5 survives the CI run

- C5 drops `t[1] == '3' ||` from the 14-column code test (`common/src/pops_config.c`, `command_code_columns`).
- Without reference inputs it survives: `Ran 32 OK (skipped=15)`.
- With inputs it is caught, by `Original.test_random_texts` only.
- The author's report says this openly.
- Fix: add `"$30012345 1234 $NOPAL "` and `"$30212345 1234 $NOPAL "` to FIXED, with EXPECTED rows recorded from the original.

### 3. minor: mutant R4 survives both runs (launcHER-only token code)

- R4 drops `text[digit] != '\n' &&` from the MODE-digit search in `next_launcher_token`. That line was changed only from `isspace` to `token_space`.
- It survives both runs (with inputs: `Ran 32 OK`).
- It is not equivalent:
  - Measured on the head: `MODE 3x ` gives modes 4 and `MODE\n3x ` gives modes 0.
  - With R4, by reading the code, `MODE\n3x` would join into `$MODE3X` and set mode 3.
- This is launcHER-only token code, which the owner still has to decide about (handoff section 8). So it is low priority.
- Fix: add `("MODE\n3x ", 0)` to `Native.test_launcher_token_bytes`.

### 4. minor: mutant V3 survives both runs

- V3 removes `cfg->forced_pal = 0;` from the `$480P` case.
- It changes `cfg.video_mode`. Measured on the head: `$FORCEPAL $480P $NOPAL ` gives `vm=3 prog=1 fp=0`. With V3, by reading, it would give `vm=4`.
- By my reading the launch does the same either way:
  - `pops_stage_fix_files` gets `POPS_VMODE_480P` because `progressive_requested` is set.
  - `pops_fix_finalize_video` and `pops_apply_region_rom` treat NOPAL and 480P alike (no PAL).
- So this is nearly an equivalent mutant. A Native assertion on `video_mode` for that text would pin the line.

### 5. minor: wording in commit 2ccf68b

- It says "the video words the region pass reads are compared for every text".
- Texts that hold a launcHER-only video token are left out (`LAUNCHER_VIDEO`). That was 71 of the 1500 random texts in my run ("video words not compared in 71 ...").
- The doc says this correctly. The commit does not.
- The subject "token bytes as the original" is also misleading: the original has no such tokens.
- Do not rewrite history. Note it in the PR text.

### 6. minor: code comment says nothing clears gp+0x3864

- The `CMD_FORCEPAL` comment in `run_command` says "$480P sets it (0x8902a4) and nothing clears it".
- My static scan of the decoded image finds a start-up store of zero at `0x870c90` (`sw zero,0x3864(gp)`). The comment's list in `pops_config.h` leaves it out too.
- The doc's "nothing in the pass clears it" is correct.
- Fix: say "nothing after start-up clears it (0x870c90 is the start-up clear)".

### 7. minor: apply_launcher_token comment is now false

- The comment says `$PAL2NTSC`/`$FORCENTSC` "is the original's $NOPAL".
- That no longer holds after a `$FORCEPAL`. Measured on the head:
  - `$FORCEPAL $PAL2NTSC ` gives vm=3 (NOPAL).
  - `$FORCEPAL $NOPAL ` gives vm=2 (forced PAL).
- This belongs to the author's owner question 2. The comment should not claim equality.

### 8. minor: other writers of the forced-PAL and automatic-PAL words are not mentioned

- The doc's region-pass argument holds only if nothing writes gp+0x38a0 or gp+0x4fa0 between the text and the region pass.
- My static scan of gp-based stores finds these writers outside the text handlers:
  - gp+0x38a0: `0x870c80`, `0x871208`, and `0x883120`.
  - gp+0x4fa0: `0x8711ec`, `0x87120c`, `0x871210`, `0x871710`, `0x883014`, `0x88309c`, `0x883124`, `0x88316c`, `0x8f8abc`.
- `0x883114..0x883124` clears both words while gp+0x3898 is 0, in the function before the reader. `$FORCEPAL` and `$480P` set gp+0x3898.
- The doc and header list that function's stores to gp+0x3864 and say its timing was not traced. They do not list its stores to 0x38a0/0x4fa0, or the 0x3898 gate.
- Fix: add one line to "Known differences that remain" (read from the code, not run).

### 9. minor, report only: the proposed quirk text overclaims

- The author's proposed quirk says "no command can differ (measured, 1428 runs)".
- 1428 runs show none differed. The doc's argument (a command needs at least 5 bytes) is reasoning, not measurement.
- Suggested wording: "no command differed in 1428 runs; by reading, none can".

## What I checked and found right

- **Cherry-pick:** `e9d1b03` has the same +/- lines as `6ced397`. The parent `66efcbe` is already in the base. The cfg worktree is untouched: still at `6ced397`, `git status` clean.
- **Buffer zeroing:** with 0xA5 put in the second half of the buffer, the tracer's run leaves that half all zero for 4 texts (`<scratch>/review-cfg/check_zero.py`). The bytes after the buffer (`beyond`) stay as put. So the original's code does zero it, as the doc says.
- **Static scan of the decoded MAIN image** (`static_scan.py`, `disasm.py`), all gp-based loads and stores:
  - gp+0x38a0 is loaded only at `0x879034`. gp+0x4fa0 is loaded only at `0x87930c`. This confirms the doc's "only loads".
  - Stores to gp+0x3864 are at `0x870c90` (zero), `0x871218`, `0x871718`, `0x88301c`, `0x8830a4`, `0x883174` and `0x8902a4`. The handler test is at `0x8987f0` (`lw; bnez 0x898814`, which skips the three stores at `0x898800/808/810`).
  - Region pass, read and not run:
    - `0x879034..0x87904c`: forced PAL only when 0x38a0 == 1 and 0x3864 == 0.
    - Every exit of the forced path branches to `0x8795f0` (14 branches listed), so it never reaches `0x87930c`.
    - `0x87930c`: auto PAL while 0x4fa0 == 1.
    - This matches `original_video` and the doc.
  - `0x883a50/54`: the read length is `size + 0x10`, which matches the doc's "size + 16".
- **Handler stores under emulation** (my run of `scan_commands`):
  - `$480P `: 0x38a0=0, 0x4fa0=0, 0x38d0=1, 0x3864=1, 0x3898=1, 4 pokes.
  - `$NOPAL `: 0x4fa0=0 only.
  - `$FORCEPAL `: 0x38a0, 0x38d0 and 0x3898 = 1.
  - `$480P $FORCEPAL `: the `$FORCEPAL` event has 0 effects.
  - All as the doc says.
- **My own differential** (`own_diff.py`, run on a copy of the head with inputs; it uses the test's `compare`, `_two_files` and the tracer):
  - Every sequence of 1..4 of `$480P $FORCEPAL $NOPAL $SMOOTH $480PX "$FORCEPAL\t"`, with separators space/CRLF/`$` for lengths 1..2 and space for 3..4: 1638 texts, 0 mismatches.
  - Two files, all pairs of 0..2 forms: 441 pairs, 0 mismatches.
  - 1500 random texts, seed 0xBEEF2026, with video forms, MODE/digit tokens, 63/64-byte runs and 0xA0 spliced in: 0 mismatches.
  - `compare` checks commands, offsets, effects, codes, X/Y, compat modes, game id, 0x100017 and the video words. It does not check GS values, stretch/crop, pad ids or left adjust.
- **Printed counts** in my with-inputs run match the doc and the commits:
  - 167 fixed texts; 1500 random (2876 commands, 399 codes, 96 MODE, 20 writes of 0x100017).
  - 500 token texts; 300 $USBDELAY texts (84); 5 x 6 = 30 runs.
  - 357 short files (17 of 1428); 600 random video texts; 18-text video table; 6 + 441 two-file pairs.
  - VMCDIR 39/30 and 400 (212/188); 21 modes x 2.
  - The tables hold FIXED 167 = EXPECTED 167, VIDEO_EXPECTED 18, VIDEO_TWO_FILES 6, no duplicate FIXED. No FIXED text holds a launcHER-only video token.
- **Scope:**
  - `pops_config.c` is built only into the launcher target (`launcher/CMakeLists.txt:49`).
  - Every user of `PopsConfig` is POPS code: handler_pops, pops_modes_patches, pops_resident, pops_builtin_db, pops_physical_disc.
  - The only ctypes mirror of the struct is `tools/test_pops_features.py`, and it was updated.
  - `cfg` in `handler_pops.c` is set up with `pops_config_init` (memset), so `forced_pal` starts at 0.
  - No Ember, shared launch or storage-driver code changed.
- **Hygiene:**
  - No binary files in the diff (numstat).
  - No hex runs of 16+ digits and no `\x` byte tables in added lines.
  - No AI attribution in added lines or in the three commit messages.
  - No email address in added lines. Author: the noreply address.
  - None of the five off-limits docs changed.
  - No push to codex/popstarter-replacement: the branch is `pr23/cfg-2`.
- **Review-1 findings:**
  - (1) Fixed: `$480P $FORCEPAL`, `$480P $NOPAL $FORCEPAL`, `$FORCEPAL $480P $FORCEPAL` and the two-file forms equal the original.
  - (2) K and K3 are now caught without inputs by `Native.test_table`. C5: see finding 2.
  - (3) and (4) Fixed: Native, Source and random token tests pass. My mutants W1, W2, R1, R2 and R3 are caught.
  - (5) Documented and tested.
  - (6) The print is fixed. The report names the wrong count in `b205a3e` (4 in warmboot + 5 in builtin_db).
  - (7) TMPDIR is in the docstring and the doc.

## Mutants (my own)

Method: each mutant in its own `git archive HEAD` copy with its own TMP/TEMP/TMPDIR, run one after another. `tools/test_pops_config_text.py` without reference inputs, then the survivors with `POPS_TEST_ELF` and `POPSTARTER_TEST_ELF`. Results: `<scratch>/review-cfg/mut/mutants-*.txt`.

Without inputs, 26 of 30 caught.

Code-column test:

| Mutant | Change | Result |
|---|---|---|
| K | $5000 test, drop `&& t[4]=='0'` | caught |
| K18 | $5000 test, drop `t[3]=='0'` | caught |
| K3 | $S kind, t[5] range '0'..'3' -> '0'..'2' | caught |
| C5 | drop `t[1]=='3'` | **survived** |
| C5b | drop `t[1]=='8'` | caught |
| C5c | drop `t[1]=='D'` | caught |
| C6 | `t[3]` 0/1 -> 0 only | caught |
| C7 | drop the `t[2]!='0'` test | caught |
| C9 | 18-column kinds 0..2 -> 0..1 | caught |
| S2, S3, S4 | $S kind: t[2] range, t[3] range, `t[4]=='0'` | caught |
| T2, T3, T4, T6 | $T kind: t[2] range, t[3] range, `t[4]=='0'`, t[6] range | caught |
| EQ | '='/'!' kind, t[2] 0/1 -> 0 | caught |

Video commands:

| Mutant | Change | Result |
|---|---|---|
| V1 | no `$FORCEPAL` gate | caught |
| V2 | `$NOPAL` ignores `forced_pal` | caught |
| V3 | `$480P` keeps `forced_pal` | **survived** |
| V4 | `$FORCEPAL` does not set `forced_pal` | caught |
| V5 | no terminator test for `$FORCEPAL` | caught |
| V6 | effect = 1 while gated | caught |

launcHER's own tokens:

| Mutant | Change | Result |
|---|---|---|
| W1 | white space TAB..CR -> TAB..FF | caught |
| W2 | white space TAB..CR -> LF..CR | caught (Source test only) |
| W3 | digits '0'..'8' | **survived**; equivalent, since mode 9 is ignored either way |
| R1 | token limit 62 | caught |
| R2 | a long run still counts as a token | caught |
| R3 | MODE n with a long run still counts | caught |
| R4 | MODE digit search across LF | **survived** |

With inputs:

- C5 is caught (`Original.test_random_texts`).
- V3, W3 and R4 survive (`Ran 32 OK`).

## Commands run and results

All from Git Bash. TMP, TEMP and TMPDIR were each set to an empty folder of mine under `<scratch>/tmp-cfgreview-*`.

1. `git fetch origin` and `git worktree add --detach <scratch>/review-cfg/tree origin/pr23/cfg-2`: HEAD `c05ddb6`.
2. Full sweep without reference inputs: `<scratch>/review-cfg/sweep.sh noinputs`, all 32 `tools/test_*.py`, one after another.
   - 31 pass.
   - `test_pops_features` fails: rc=1, `Ran 29 FAILED (failures=1, skipped=2)`.
   - Others: test_pops_config_text Ran 32 OK (skipped=15); test_pops_user_bios Ran 51 OK (skipped=13, expected failures=1); test_pops_launch_hooks Ran 48 OK (skipped=14); test_pops_igr_skin Ran 48 OK (skipped=21); test_pops_external Ran 128 OK (skipped=14); every script-style file rc 0.
   - Logs: `<scratch>/review-cfg/out/noinputs-*.out`, `summary-noinputs.txt`.
3. Full sweep with `POPS_TEST_ELF`, `POPSTARTER_TEST_ELF` and `POPS_TROJAN_CORPUS` set: 31 of 32 pass, `test_pops_features` fails on the same assertion.
   - test_pops_config_text: Ran 32 OK in 164 s.
   - test_pops_user_bios: Ran 51 OK (expected failures=1), the known 5.5 case.
   - test_pops_external: Ran 128 OK (skipped=3).
   - test_pops_launch_hooks: Ran 48 OK (skipped=3).
4. Base `test_pops_features.py` (git archive of origin/codex/popstarter-replacement), without inputs: Ran 29 OK (skipped=2).
5. Head with line 948 expecting 4: Ran 29 OK (skipped=2) without inputs, Ran 29 OK with inputs.
6. Docker target build, in a standalone local clone at `c05ddb6` with submodules from the local repository:
   - The detached worktree cannot be built in the container ("fatal: not a git repository", because its .git file points at a Windows path).
   - build rc 0, no `error:` lines; `release/launcHER.elf` is 327,092 bytes. The handoff gives 326,772 bytes at `f22a69f`.
   - Build folder and clone removed.
7. `check_zero.py`, `static_scan.py`, `disasm.py` and `own_diff.py`: results as in "What I checked".
8. Mutants: as above.
9. Hygiene greps on the diff and commit messages: nothing found.
10. `git worktree remove <scratch>/review-cfg/tree`: removed.

## Not done

- No console run, no PCSX2 run.
- The other three POPStarter profiles were not looked at.
- The behaviour of the function at `0x883000..0x883188`, and when it runs relative to the reader, was not traced.

## Proposed doc and quirk text (for the coordinator)

- **Quirk** (the author's, reworded): "$FORCEPAL after a $480P does nothing, also when the $480P is in the file for all games (0x8987f0 tests gp+0x3864). Matched in launcHER (pr23/cfg-2); measured under emulation."
- **Quirk:** "$NOPAL does not undo an earlier $FORCEPAL: $NOPAL clears only gp+0x4fa0, and the region pass tests gp+0x38a0 first (0x879034, read from the code). Matched in launcHER (`forced_pal`)."
- **Quirk:** "CHEATS.TXT of 8 bytes or less: a code test reads past the 2*size buffer; what the heap holds decides whether such a '$' is a code. launcHER reads zeros. None of 1428 runs with other heap bytes changed a command."
- **Known-differences line for docs/POPSTARTER_CONFIG_TEXT.md:** "Read from the code, not run: the function before the reader clears gp+0x38a0 and gp+0x4fa0 at 0x883120/0x883124 while gp+0x3898 is 0 (which $FORCEPAL and $480P set), and sets gp+0x3864 at 0x88301c/0x8830a4/0x883174. Start-up writes are at 0x870c80/0x870c90 and 0x871208..0x871230. When the function at 0x883000 runs relative to the reader was not traced, so whether it changes the video result of a text was not measured."

## Open questions for the owner

1. (Handoff section 8, unchanged) Should launcHER-only tokens, bare digits and `MODE n` stop being read from CHEATS.TXT?
2. The author's question: should launcHER's `$NTSC2PAL`, `$PAL2NTSC` and `$FORCENTSC` keep "last one wins" against `$NOPAL` and `$FORCEPAL`? Today `$FORCEPAL $PAL2NTSC` is no PAL, but `$FORCEPAL $NOPAL` is forced PAL.
3. A fix file that sets progressive is applied after the text (`handler_pops.c`). A `$FORCEPAL` in the text therefore keeps `video_mode = NTSC2PAL` while progressive is set, and `pops_fix_finalize_video` and `pops_apply_region_rom` receive NTSC2PAL. Whether the original's fix-file progressive runs before the text (which would gate `$FORCEPAL`) belongs to the not-started fix-file/command order work.
