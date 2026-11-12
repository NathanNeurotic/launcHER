# Status documents, answer to review 2: independent review

Reviewed `origin/codex/popstarter-replacement` (`ef663b2`) ... `origin/pr23/docs-2` (`8499217`), in a
detached worktree at `<scratch>/review-docs/tree` (removed afterwards with `git worktree remove`).
I did not commit or push anything. All of this is host work: Unicorn, capstone, host Python, and a
container build. No emulator of the whole machine and no PS2 rig. NOT TESTED on a console.

## Verdict

**merge-after-fixes.** I checked every statement the pass adds about the original that matters for
parity myself, against the original's bytes and in my own Unicorn runs. All of them hold. The PR
head stays green without inputs. The diff changes only four text files, and no C code, workflow or
launch-path behaviour. It adds no binary, hash or byte table, and no AI attribution.

One major finding stays open. Section 2b of the audit was rewritten to say exactly what
`tools/test_pops_doc_claims.py` pins, and it still names sentences that are only partly pinned: 9
of my 30 mutants survive inside statements that 2b lists as checked. The minor findings: gaps in
the step parser, one "in progress on a side branch" marker that no branch backs, a stale `S1..S33`
range, and counts that are not pinned.

## Scope and hygiene

- `git diff --stat ef663b2 8499217`: only `docs/CLOUD_CONTINUATION.md`,
  `docs/POPSTARTER_GAP_AUDIT_2026-11-11.md`, `docs/POPSTARTER_R13_INVENTORY.md` and
  `tools/test_pops_doc_claims.py`. Nothing else differs, so there is no C, launch-path, storage-driver,
  Ember or workflow change. The shared documents the author was told not to touch (quirks file,
  handoff doc, README, `pops-setup.html`) are untouched.
- `git diff b77a4e8 8499217 --stat`: only the audit, the inventory and the doc-claims test changed
  after `b77a4e8`. This matches what audit 19a says about the full host run.
- I grepped the added lines and all six commit messages for attribution (claude, anthropic,
  co-authored, generated with, openai, chatgpt, codex as a word) and for email addresses. No hits.
  The commit messages contain no trailers.
- Long hex runs: none of 16 or more hex digits in the added lines. The new 32-bit literals in the
  test are single MIPS instruction encodings or masks (`0x03e00008` `jr ra`, `0x2402fd66`
  `li v0,-666`, `0x24020001`, `0x1000005a`, `0x10620006`, `0x14400044`, `0x14620003`,
  `0x8fc30000`, `0xafc00008`, `0xafc00030`, `0xafc000c0`, `0x0c000000`, `0x03ffffff`, `0xffe0ffff`).
  They are not tables. `hashlib.sha256` is used only to count distinct corpus files at run time.
  No digest is stored. `SLOTS` holds addresses only.
- Owner's email: not present in the added text.

## Commands run and results

TMP/TEMP/TMPDIR were a fresh folder per pass (`<scratch>/tmp-reviewdocs-p1`, `-p2`). Every file was
run one at a time from the worktree root (`<scratch>/review-docs/run_all.sh`).

1. **Full host list, without the three reference variables (CI condition):** 32 files, each `rc=0`.
   Skips: breakpoint 4, builtin_db 14, config_text 10, display 6, doc_claims 11, external 14,
   features 2, fix_files 3, igr_skin 21, launch_hooks 14, module_irx 4, opcodes 3, padman 3,
   physical_disc 18, progressive 5, resident 12, smb_config 13, user_bios 13 (plus 1 expected
   failure), warmboot 3. This is identical to the author's section 19a list.
2. **Full host list with `POPS_TEST_ELF`, `POPSTARTER_TEST_ELF` and `POPS_TROJAN_CORPUS`:** 32 files,
   each `rc=0`. Still skipping: external 3, launch_hooks 3, progressive 3 (they need the EE image
   variables, which I did not set). `test_pops_doc_claims.py`: 17 tests, 0 skipped, OK (the corpus
   class included). `test_pops_user_bios.py`: `OK (expected failures=1)`.
3. **Bad inputs to `test_pops_doc_claims.py`:**
   - `POPSTARTER_TEST_ELF` naming a missing file: rc=1.
   - `POPSTARTER_TEST_ELF=POPS.ELF`: rc=1 (setUpClass error).
   - `POPS_TROJAN_CORPUS` naming a missing folder: rc=1.
   - `POPSTARTER_TEST_ELF=` (empty): rc=0, skipped=11, treated as unset. That is reasonable.
4. **My own BIOS handler run** (`<scratch>/review-docs/rv_bios_popsdir.py`, built on the in-repo
   `trace_original_pops_user_bios.Machine`). `FUN_008d8958` ran as shipped. The folder primitives
   `0x8d7e78`, `0x91bf80` and `0x91be68` were modelled, keyed on the path string the code passes, so
   the POPS folder and the game folder are told apart by path, not by call order. That keying is
   different from the author's model. 64 runs over scope x backend x POPS folder x game folder x
   (no file / `0x80000` bytes) x `gp+0x38b0`, plus 4 runs with `gp+0x3868 = 1`:
   - All games, POPS folder missing: return -666, 0 opens, core unchanged, and only `gp+0x38dc`,
     `gp+0x3460`, `gp+0x3868` change, each 0 to 1 (16 of 16).
   - Game, POPS folder missing:
     - game folder and file present: return 1, file loaded, `gp+0x38dc`, `gp+0x3460`,
       `gp+0x3868`, `gp+0x38e0` and `gp+0x3b98` each 0 to 1 (4 of 4);
     - no file: return 0 (4 of 4);
     - game folder missing: return -666 with 0 opens (8 of 8).
   - POPS folder present: `gp+0x3868` 0 to 1 in 32 of 32.
   - `mass:` with the POPS folder missing: `0x91be68` called on `mass0:/POPS` (16 of 16).
   - `gp+0x3868 = 1` with the POPS folder "missing": no POPS folder check is made and the file loads
     (4 of 4).

   This agrees with S30 in every count.
5. **My own IGR skin run** (`<scratch>/review-docs/rv_igr_popsdir.py`, a subclass of the in-repo
   `trace_original_pops_igr_skin.Emulator` with `FUN_008d8958` executing and only its three
   primitives modelled; 8 runs, backend x folder x quiet). Folder missing: return -666, 0 opens, core
   unchanged, `gp+0x38dc`, `gp+0x3460` and `gp+0x3868` all 1 (4 of 4), plus `0x91be68` on
   `mass0:/POPS` for `mass:`. Folder present: return 1, 3 opens, only `gp+0x3868` set (4 of 4).
   This agrees with S31.
   - A harness note for whoever reuses that tracer: `Emulator.run()` does not clear `.bss`, so
     `gp+0x3460` carries over between runs. My first pass showed a false `gp+0x3460 = 1` on
     `mass:` with the folder present until I zeroed `0x9b9d00..0x9ccac0` before each run. The
     author's S31 numbers are right, so their script must reset it. The committed tracer only ever
     runs with `gp+0x3868 = 1`, where the folder check never writes `gp+0x3460`, so its own tests
     are not affected. It is a trap for the next harness, not a defect of this diff.
6. **Static reads** (capstone, word by word, of `0x870000..0x915000`):
   - `0x880338..0x880380`: `lw 0x3868(gp)`, `jal 0x8d8958` at `0x880348`, a scope test `lw v1,0(fp)`
     at `0x880360` with `beq` at `0x880368` to `0x880384`, `sw 0x38dc(gp)` at `0x880374`,
     `li v0,-666` at `0x880378`. As section 4 says.
   - `FUN_008d8958` `0x8d8958..0x8d8b10`: returns 0 only for `gp+0x38dc == 1` or `gp+0x3868 == 1`;
     otherwise it stores `gp+0x3868 = 1` at `0x8d899c`. The `pfs1:/POPS/` failure stores
     `gp+0x38dc`/`gp+0x3460` and returns -666 (`0x8d8a20`/`0x8d8a28`/`0x8d8a2c`). The `mass:/POPS`
     failure calls `0x91be68("mass0:/POPS")`, then the same stores (`0x8d8ac0`/`0x8d8ac8`/`0x8d8acc`).
     A `gp+0x3448` other than 0 or 1 returns 1. The only stores to `gp+0x3448` in the code area
     are `0x870c64` (zero), `0x871618` (1) and `0x8719a4` (1). As S32 says.
   - `gp+0x3888`: the only nonzero store is `0x871620` (value 3, on the `SB.` path at
     `0x87160c..0x871620`, which also sets `gp+0x3448 = 1`). `0x873f90..0x873f9c` skips `main`'s
     check when it is nonzero. `0x8740a8` takes the branch for value 3. `0x87425c` stores
     `gp+0x3868 = 1` after the `mass:/POPS/POPS_IOX.PAK` open loop (`0x874218..0x87422c`, string
     at `gp-0x6d18`) succeeds. As section 4 and row 3a say.
   - `main`: `addiu sp,-0x1630` at `0x870b78`, `jr ra` at `0x87c210`, delay slot `0x87c214`, next
     function `addiu sp,-0x20` at `0x87c218`. So finding 7 of review 2 is fixed.
7. **My own mutants** (`<scratch>/review-docs/rv_mutants.py`). 30 one-line changes, each applied to
   a fresh `git archive HEAD docs README.md .github tools` copy, never to the worktree. Each was run
   without inputs and with all three inputs. The baseline passes both ways. With the inputs 16 are
   caught and 14 survive; without inputs none is caught. Caught with the inputs: R01, R07, R16, R17,
   R18, R20 to R25, R27 to R30 (section 4 exits and gates, section 6 return set, S21, S24, the slot
   list, S32's -666 stores, the inventory `$USBDELAY_n` and IGR sentences, the corpus count).
   Survivors, both ways:

   | # | Change | Claimed pinned by 2b? |
   |---|---|---|
   | R02 | section 4 POPS-exit row: "`gp+0x3460 = 1` (S32), so after" -> `gp+0x3464` | partly ("its POPS folder exit ... and the section 4 sentence"; the extra-writes sentence in the same row is not pinned) |
   | R03 | section 4: `SB.` launches (`gp+0x3888 = 3`) -> `= 2` | no |
   | R04 | S34: "Seven gate loads" -> "Six" | yes: "S34: the seven flag loads ... in order" |
   | R05 | S34: "six such branches" -> "seven" | yes: "six returns of 0" |
   | R06 | section 6: "`gp+0x3868 = 1` on every call that gets that far" -> `= 0` | yes: "the section 6 sentences on the folder check and its extra writes" |
   | R08 | inventory BIOS.BIN row: "all games returns -666, the game scope goes on" -> "both scopes return -666" | no |
   | R09 | S33: host-tests "runs 29" -> 28 | no |
   | R10 | CLOUD_CONTINUATION: "32 and CI runs 30: 29" -> "33 ... 31: 30" | no |
   | R11 | build.yml warmboot step: append `\| tee warmboot.log` | the parser rule as written does not exclude it |
   | R12 | build.yml warmboot step: `run: \|` block with `exit 0` before the test | as R11 |
   | R13 | S32: "(a `gp+0x3448` other than 0 or 1 ... also returns 1)" -> `returns 0` | yes: "the sentence that states its return values" (it is the same sentence) |
   | R14 | S30: "(16 of 16)" -> "(15 of 16)" | no (emulated runs are said not to be repeated) |
   | R15 | 3a `0x3460` row: "with `gp+0x38dc`" -> "with `gp+0x3868`" | no |
   | R19 | inventory IGR row: "and `gp+0x3868` (gap audit section 6, S23, S31)" -> `gp+0x3888` | yes: "the inventory's IGR sentence" |
   | R26 | section 6: `0x91be68` -> `0x91be6c` | yes: "its extra writes" (the author's report lists the `0x91be68` call among the extra writes) |

8. **Container build.** First I ran the exact command from the task in this git worktree, without
   the submodule:
   - `git config --global` printed `fatal: not a git repository: (null)` (rc 128);
   - the build stopped with "Directory does not exist for chdir command:
     /workspace/launcher/iop/mmceman/mmceman" (rc 2).

   This confirms the CLOUD_CONTINUATION/19a statements about worktrees. After
   `git submodule update --init launcher/iop/mmceman`, I used `cd / && git config ... && cd /workspace`
   and `cmake -B build-rvdocs`. Result: rc 0, `release/launcHER.elf` 326,772 bytes, with the warning
   "No Git revision available: writing version=unknown". Identical in size to the author's build and
   the handoff's `f22a69f` build. Not run on anything.
9. **Code citations at `8499217`** (grep of `launcher/src/handler_pops.c`):
   - `pops_stage_igr_skin` call `:1657`, after the built-in entry at `:1632..1643`;
   - `pops_stage_user_files` call `:1683`, defined at `:914`, which runs
     `pops_apply_all_config_patches_rom` (`:938`), `pops_resident_hook_recompiler_emit` (`:948`) and
     `pops_stage_fix_files` (`:956`) in that order;
   - `pops_apply_bios_shell_edits_rom` `:1714`, `pops_apply_region_rom` `:1722`,
     `pops_apply_reset_warmboot` `:1740`, `sleep(cfg.usb_delay)` `:1985`;
   - `pops_apply_undo_tokens_rom` exists in `common/src/pops_modes_patches.c`;
   - `CMD_USBDELAY` is "one digit, terminator";
   - nothing outside `common/src/pops_physical_disc.c` calls `pops_physical_disc_*` (only the
     header declares them).

   The numbers taken from the merged documents are present there: user BIOS 131 / 342 / 72 /
   270 (242 + 28) / 294 of 624; IGR skin 48 tests, 27 without inputs, 141 runs. All as the audit and
   inventory state.

## Per finding of review 2: answered?

1. Shared documents (owner decision). Correctly left to the owner: handoff section 8 lists it. The
   pass edited only its four allowed files.
2. BIOS POPS-folder -666 exit. **Answered, correct.** I reproduced it statically and in my own run
   with a different folder model (above).
3. The test pins what the audit says. **Largely answered, not fully.** The reviewer's survivors M04,
   M06, M08, M13 to M17 and M20 are now caught (the author's log `mutants2.out`; my R-series covers
   the same rows and agrees). But the new 2b paragraph again names sentences that are only partly
   pinned: finding A below.
4. Workflow steps really run. **Answered.** M11 and M23 are caught (author's run). My R11/R12 show
   two remaining parser gaps: finding B.
5. CLOUD_CONTINUATION overstatement. **Answered.** The new text matches the author's own earlier
   report and review 2's sequential run, and the old sentence is on the withdrawn list.
6. IGR -666 row. **Answered, correct.** The reachable results and the extra writes match my run.
   `0x873f9c`/`0x87425c` are confirmed statically.
7. `MAIN_FUNCTION` end, and a set but unusable input. **Answered.** Confirmed by disassembly and
   by the bad-input runs.

The update to `ef663b2`: the rows I checked against the merged code (item 9 above) are stated as far
as the code and its tests support. The handoff defect, TROJAN and CHEATS.TXT rows say "in progress
on a side branch" without guessing an outcome, with the exceptions in finding C.

## Findings

### A (major). Section 2b still names sentences the test only partly pins

The new paragraph says the test "now checks exactly the following". It lists:
- "the section 6 sentences on the folder check and its extra writes, and the inventory's IGR
  sentence";
- "the sentence that states its return values" (S32);
- "S34: the seven flag loads ... six returns of 0".

Mutants R06 (the `gp+0x3868` write in section 6), R26 (the `0x91be68` call in section 6), R19 (the
inventory IGR sentence's `gp+0x3868`), R13 (the `gp+0x3448` clause of the S32 return-value sentence)
and R04/R05 (S34's "seven" and "six") survive with all three inputs. R02 (the extra-writes sentence of
the section 4 POPS-exit row) is the same pattern.

Every one of these statements is true: my runs and disassembly confirm each. The defect is the claim
that a test guards them. That is the class of defect review 2's finding 3 was about, and the very
paragraph written to fix it has it again.

Fix (small): extend the existing `assertIn` phrases so they cover:
- in section 6, from "The check also writes:" through "on `mass0:/POPS`";
- in the inventory IGR row, through "and `gp+0x3868`";
- the whole S32 return sentence, including the parenthetical;
- the S34 row's counts and order (compare with the computed `gates`/`returns`);
- the section 4 sentence beginning "The check itself sets".

Or reword 2b to name the exact pinned phrases. Re-run the mutants above.

### B (minor). The step parser counts a test whose failure cannot fail the step

`steps_that_run()` excludes `||` but not a pipe. `run: python tools/test_pops_warmboot.py | tee x.log`
(R11) still counts as run. GitHub's default shell for `run` without `shell:` is `bash -e` without
`pipefail`, so the step passes when the test fails. A block `run: |` whose first line is `exit 0`
(R12) also counts, although the test never starts. A `push:` trigger with a branch or path filter
also counts as push.

The audit (2b) and CLOUD_CONTINUATION describe the rule exactly, so they are not false. But
CLOUD_CONTINUATION calls these "the steps the workflows really run". Fix:
- treat `|` after the command like `||`;
- stop reading a block at an unconditional `exit`;
- or name these limits next to the rule in both documents.

### C (minor). Side-branch markers

- Audit section 3, row `0x879d04..0x879e58`: "none (`sleep(cfg.usb_delay)` ... on the EE instead;
  in progress on a side branch, section 9)". I grepped the diffs of `pr23/cfg`, `pr23/cfg-2`,
  `pr23/handoff`, `pr23/handoff-2`, `pr23/trojan`, `pr23/trojan-2` and `pr23/paths` against `ef663b2`
  for `usb_delay|USBDELAY|DLAY`. The only hits are changes to the `scan_commands` signature in the
  config-text tracer and test. No branch touches the EE sleep or the wrapper patch. Section 9 itself
  correctly says only that the config-text review answers are in progress. Drop "in progress on a
  side branch" from the section 3 row, or say what is in progress (the config-text review answers).
- The audit header says the handoff defect is among the areas "marked 'in progress on a side
  branch'". No row of the audit or the inventory mentions it (grep for `handoff` and `0x206360`).
  Either add a pointer (handoff 5.1) where a reader needs it, or drop it from that sentence.

### D (minor). Stale spot-check range

Audit line 53: "`S1`..`S33` after a label refers to the spot checks in sections 2, 2a and 2b". S34
was added in `3ac02d8`. `test_cited_spot_checks_are_defined` does not check this sentence. Change
it to `S34`, or have the test derive the upper bound and compare.

### E (minor). Counts that will rot unnoticed

The S33 counts ("32 test files ... runs 29") and CLOUD_CONTINUATION's "At `ef663b2` there are 32 and
CI runs 30: 29 as `host-tests` steps" are not pinned (R09, R10 survive). The `ci-coverage` block
itself is pinned and stays correct when files are added. These counts are labelled "at `ef663b2`",
so they are not wrong today. Note only. Either pin them as "at `ef663b2`" history or leave them as
they are, and do not restate them as current.

## Not findings, but for the owner

- Unpinned and not claimed (fine as written): the inventory BIOS.BIN row's asymmetry sentence (R08),
  the 3a `0x3460` row (R15), the `gp+0x3888 = 3` statement (R03, true by my static read) and the S30
  run counts (R14). If the inventory's BIOS row should be guarded like its IGR row, add one
  `assertIn`.
- **Lead for owner question 3 (`read` only, not traced; NOT TESTED on a console).** In a whole
  launch the loaders' POPS-folder exits may never be reached:
  - `main`'s check at `0x873f9c` runs unless `gp+0x3888 != 0`, and only the `SB.` path (`0x871620`)
    sets that word nonzero;
  - the `SB.` path stores `gp+0x3868 = 1` at `0x87425c` after its PAK open loop, which retries
    (`0x874218..0x87422c`; the counter is compared with `0x78` once, then the loop continues);
  - `FUN_008d8958` sets `gp+0x3868` on entry unless `gp+0x38dc` or `gp+0x3868` is already 1;
  - with `gp+0x38dc = 1`, each loader returns at its first gate.

  So `gp+0x3868 == 0` with `gp+0x38dc == 0` at a loader call looks unreachable. I did not read
  `0x8709f8` (called when the counter reaches `0x78`) or every other path to the loaders. If this
  holds, copying the exit (and its scope asymmetry) would have no effect for any real launch. That
  bears on whether quirk text calling the asymmetry "a bug parity would copy" needs a qualifier. The
  audit's own wording ("which launches end up here has not been traced end to end (`read`)") is
  accurate.
- The README.md:718 and `docs/pops-setup.html`:552-555 "not implemented" text for the IGR skin is
  stale since `173d5de` (confirmed by grep). These files are outside this diff. The author's
  proposed replacement text is in their report.

## Proposed doc text (for the coordinator)

For handoff 5.4, after this review:

> Review 2 answered on `pr23/docs-2` (`8499217`). The independent review of that answer reproduced
> the BIOS and IGR POPS-folder results under Unicorn with its own folder model, ran 32 of 32 test
> files both ways and rebuilt the ELF (326,772 bytes). Open: section 2b still lists some sentences
> as pinned that the test pins only in part (review finding A, major); the step parser accepts a
> piped or pre-`exit`ed test (B); three small wording points (C to E). Host work only; NOT TESTED on
> a console.

No new quirk from this review. The author's two proposed quirk entries are accurate as to the
original's behaviour. The first could add: "`main` appears to set `gp+0x3868` before any loader in
every launch (static read, not traced), so the exit may be unreachable in practice."

## Open questions for the owner

1. Finding A: extend the pins (preferred, small), or reword 2b?
2. Should the step parser reject `| ...` and pre-`exit` blocks, or should the documents state those
   limits?
3. Given the lead above, should owner question 3 (copy the POPS-folder exit) wait until someone
   traces whether any real launch reaches it?

## Not done

- No console, PS2 rig or whole-machine emulator.
- I did not re-run S22, S23 or S27, the OSD, TROJAN and PATCH scope handling, or `0x8709f8`.
- I did not set the EE image variables, so external, launch_hooks and progressive each kept 3
  skips in pass 2.
- I did not re-run the author's M/N mutant script. I read its output (`<scratch>/docs2/mutants2.out`)
  and ran my own 30 mutants instead.
