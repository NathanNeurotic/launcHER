# Status documents: answer to the review of the second correction pass

Branch `pr23/docs-2`, worktree `<workspace>/launcHER.worktrees/docs-2`.
Before: `8499217`. After: `310aab3` (pushed). Commits:

- `f0344aa` wip(pops): doc-claims test pins the review-3 sentences; stricter step parser; history counts
- `51c9693` wip(pops): doc-claims test leaves audit section 2b out of the compared text
- `310aab3` docs(pops): audit section 19b for the third correction pass

Only `docs/POPSTARTER_GAP_AUDIT_2026-11-11.md`, `docs/CLOUD_CONTINUATION.md` and
`tools/test_pops_doc_claims.py` changed in this round. The inventory did not need a change.
No C source, workflow, launch path, storage driver or Ember code changed. No binary, hash
or byte table was added. The new literals are single MIPS words and gp offsets, the same
kind as before. The added lines and the commit messages have no AI attribution and no
email address (grep). All of this is host work. NOT TESTED on a console.

## Per finding

### A (major): section 2b named sentences the test pinned only in part. Fixed.

The test now compares each named sentence whole, with its values computed from the
original's bytes where the original fixes them:

- **Section 6, the "extra writes" sentence:** compared whole, from "The check also writes:"
  through "on `mass0:/POPS`.". The offsets come from the check's stores, and each store is
  checked to write 1. The callee comes from the third `jal`. The two paths are the strings
  the check passes in `a0` (`mass:/POPS`, `mass0:/POPS`). The `bgez v0` after the
  `mass:/POPS` stat leads to that callee. (Mutants R06, R26, F04, F14.)
- **Inventory IGR sentence:** compared through "and `gp+0x3868` (gap audit section 6, S23,
  S31)". (Mutants R19, F15.)
- **S32 return-value sentence:** compared whole, including the parenthetical. Two things
  are now checked statically:
  - the `gp+0x3448` branch structure: `0x8d89a0`/`0x8d89a4` `bnez`, then `0x8d8a38..0x8d8a40`
    `bne` to the shared return of 1, whose `li v0,1`/`sw v0,0x30(fp)` is checked;
  - the three stores of `gp+0x3448` in the code area, with their values: `0x870c64` 0,
    `0x871618` 1, `0x8719a4` 1.

  The "0 or 1" in the sentence is computed from those values. The 3a `gp+0x3448` row's list
  of writers is pinned too. (Mutants R13, F05, F06.)
- **S34 counts and order:** the row is compared whole. "Seven" and "six" are number words
  computed from the gate loads and from the branches to `0x880a0c`. The gate groups and
  scopes are computed. The pair that shares a return is computed. So is the count of
  returns that come after a `SKIPPED` print. (Mutants R04, R05, F01, F02.)
- **Section 4, the sentence starting "The check itself sets":** compared whole, with the
  check's stores. (Mutants R02, F16.)
- **Cheap additions** the review listed as unpinned but not claimed:
  - the inventory `BIOS.BIN` asymmetry sentence (R08, F07);
  - the 3a `gp+0x3460` row (R15);
  - `main` skipping its check on `SB.` launches with `gp+0x3888 = 3` (R03) and the 3a
    `gp+0x3888` row (F08). The writes of `gp+0x3888` are 0/3/0, and the 3 is in the block
    that also sets `gp+0x3448`;
  - the OSD, BIOS, TROJAN and PATCH loaders each read `gp+0x3460` once, and the IGR skin
    function never.

Section 2b was rewritten to say exactly what is compared, which parts are text only (for
example the `SB.`/`XX.` labels, "S11", "skips every later current-game loader" beyond the
BIOS gates), and what is not compared (for example "only when the `SB.` PAK loop succeeds").

**Found while doing this:** 2b now quotes some compared phrases. Before this fix, a quote in
2b could satisfy `assertIn` even after the original sentence was changed. My first run hit
it: R03 and R07 no longer applied uniquely. The test now leaves section 2b out of the text
it compares (`audit_text()`), and 2b says so. F17 and F18 check the effect on two phrases
that 2b quotes.

**Found while doing this, an error in the author's own S34 text:** the old row said all six
returns came "each after an optional SKIPPED print". The first one does not. The
`gp+0x38dc` gate at `0x8801b4..0x8801c8` branches to `0x880a0c` with no print: capstone read
of `0x88019c..0x880230`, and the event scan in the test. The row now reads "the first
(`gp+0x38dc`) at once, the other five after an optional `SKIPPED` print gated by
`gp+0x38b0`".

### B (minor): the step parser counted a test whose failure cannot fail its step. Fixed.

`run_steps()`/`steps_that_run()` now refuse:
- a line with `||`, a pipe, or a background `&` (redirections like `2>&1` are allowed);
- a test after an `exit`, `return`, `exec` or `set +e` line in the same `run:`;
- a step, job or workflow shell other than the default, `bash` or `sh`, also through
  `defaults`;
- a push or pull_request trigger with any filter (branches, paths, tags, types).

Synthetic cases were added for each, with counted controls: `2>&1`, `exit 0` after the
test, `shell: bash`. The remaining limit (it reads text and runs no shell) is stated in 2b.
`CLOUD_CONTINUATION.md` no longer says "the steps the workflows really run". It now says
"the workflow steps that start each file in a way whose failure fails the step, as far as a
text parser can tell" and lists the rule. Mutants R11 and R12 (the reviewer's) and F10 to
F13 are caught both ways.

### C (minor): side-branch markers. Fixed.

- Section 3, row `0x879d04..0x879e58`: the "in progress on a side branch" marker is
  dropped. I did not re-grep the side branches; I accepted the reviewer's grep evidence. The
  row now ends "(... on the EE instead; section 9)".
- Handoff defect: the last row of section 3 (`0x879e5c..0x87c1e0`, "`j 0x22e440`") now
  points to handoff sections 3.2 and 5.1 and says the fix is in progress on a side branch
  (`pr23/handoff`). It does not guess the outcome. The header sentence names that row. The
  inventory has no row about the handoff into POPS, so it is unchanged.

### D (minor): the stale range `S1`..`S33`. Fixed.

The range is now `S1`..`S34`. `test_cited_spot_checks_are_defined` reads the stated upper
bound and requires it to equal the highest defined row. Mutant F03 is caught both ways.

### E (minor): counts that would rot. Pinned as history.

A new `History` class runs when `cfebe01` and `ef663b2` are in the clone. It recounts those
commits' own `tools/test_*.py` files and their workflows' run steps (`git ls-tree`/`git show`
plus the same parser). It compares the result with:
- `CLOUD_CONTINUATION.md`'s two sentences ("At `cfebe01` there were 26 ... 24 ... 23" and
  "At `ef663b2` there are 32 and CI runs 30: 29");
- the S33 result whole: "each as an unconditional step of its own" means one file per step,
  and the files run by no workflow are listed;
- that no workflow at either commit sets a reference input.

The class skips when the commits are missing, which is the case in CI's `actions/checkout`
depth-1 clone. Checked with `git clone --depth 1`: 19 tests, `OK (skipped=13)`. Locally, in
the worktree, it runs. The reviewer's R09 and R10, plus F09, are caught both ways when run
in a `git worktree` copy. They cannot be caught in a `git archive` copy, which has no
history.

## Commands and results

TMP, TEMP and TMPDIR were set to `<scratch>/tmp-docsfix` for single runs and to a fresh
`<scratch>/tmp-docsfix-run` for the full list. Git Bash throughout.

1. `git pull --ff-only` in the worktree: already up to date at `8499217`.
2. Capstone reads (`<scratch>/docs2/disasm.py`) of:
   - `0x8d8958..0x8d8b14`, the folder check: branches, stores, the `a0` strings
     `pfs1:/POPS/`, `mass:/POPS`, `mass0:/POPS`;
   - `0x870c58..0x870c6c`, `0x871600..0x871628`, `0x871990..0x8719a8`: the
     `gp+0x3448`/`gp+0x3888` stores (0/1/1 and 0/3/0);
   - `0x88019c..0x880230`: the first BIOS gate returns with no print.

   I also listed the `gp+0x3460` loads per loader (IGR none; OSD `0x87ebf4`, BIOS
   `0x880304`, TROJAN `0x880a68`, PATCH `0x881e2c`) and the print formats in
   `0x8801b4..0x880338` (five `"    > SKIPPED !!!\n"`).
3. `python tools/test_pops_doc_claims.py` at `310aab3`:
   - without inputs: 19 tests, `OK (skipped=11)`, exit 0;
   - with `POPS_TEST_ELF`, `POPSTARTER_TEST_ELF` and `POPS_TROJAN_CORPUS`: 19 tests, `OK`,
     exit 0;
   - shallow clone of `51c9693`, without inputs: `OK (skipped=13)`.
4. Mutants (`<scratch>/docsfix/fx_mutants.py`, built on the reviewer's `rv_mutants.py`; output
   `<scratch>/docsfix/fx_mutants.out`), on `51c9693`. 48 one-line changes: R01..R30 with R03/R07
   anchored to the body text, plus F01..F18. Each was applied to a `git archive` copy, or to a
   temporary `git worktree` for R09/R10/F09 (removed afterwards; `git worktree list` is
   clean), and run without inputs and with all three. Baseline rc 0 both ways.
   - With inputs: 47 caught, 1 survivor (R14, an S30 run count; emulated runs are not
     repeated, by design and as 2b says).
   - Without inputs: 10 caught (R09, R10, R11, R12, F03, F09, F10, F11, F12, F13).

   A first attempt on `f0344aa` was stopped after R09, once R03/R07 showed the quoting
   problem. Its partial results are not used.
5. Full host list (`<scratch>/docsfix/run_all.sh`; summary in `<scratch>/docsfix/runs/summary.txt`),
   at `51c9693`, every `tools/test_*.py` one at a time:
   - **Pass 1, the three variables unset:** 32 files, each exit 0. Skips: breakpoint 4,
     builtin_db 14, config_text 10, display 6, doc_claims 11, external 14, features 2,
     fix_files 3, igr_skin 21, launch_hooks 14, module_irx 4, opcodes 3, padman 3,
     physical_disc 18, progressive 5, resident 12, smb_config 13, user_bios 13 plus 1
     expected failure, warmboot 3.
   - **Pass 2, with POPS_TEST_ELF, POPSTARTER_TEST_ELF and POPS_TROJAN_CORPUS:** 32 files,
     each exit 0. Still skipping: external 3, launch_hooks 3, progressive 3 (the EE image
     inputs were not given). user_bios: `OK (expected failures=1)`.
   - After `51c9693` only audit section 19b changed. `test_pops_doc_claims.py` was re-run
     both ways on `310aab3` (item 3).
6. Container build:
   `MSYS_NO_PATHCONV=1 docker run --rm -v "<worktree>:/workspace" -w /workspace ghcr.io/ps2homebrew/ps2homebrew:main sh -c "apk add cmake >/dev/null && cd / && git config --global --add safe.directory /workspace && cd /workspace && cmake -B build-docsfix && cmake --build build-docsfix --target launcHER"`.
   - The `cd /` around `git config` avoids the worktree `.git` error the reviewer saw. The
     `mmceman` submodule was already initialised.
   - Result: rc 0, `build-docsfix/release/launcHER.elf` 326,772 bytes, with the warning
     "No Git revision available: writing version=unknown".
   - Not run on anything. `build-docsfix/` was removed.

## Not done

- No console, PS2 rig or whole-machine emulator. NOT TESTED on a console.
- S22, S23, S27, S30 and S31 were not re-run. R14 survives for that reason.
- I did not trace whether any real launch reaches the BIOS/IGR POPS-folder exit. Neither
  the reviewer's lead (`main` may always set `gp+0x3868` before any loader; `0x8709f8` is
  unread) nor its opposite was checked.
- I did not re-grep the side branches for finding C. I relied on the reviewer's grep.
- The launcHER paragraphs of sections 4 to 14 are still not checked by any test.
- README.md:718 and `docs/pops-setup.html`:552-555 still say the IGR skin is not
  implemented. They are off-limits for this track. The replacement text proposed in
  `<scratch>/reports/docs-author.md` still applies.

## Proposed text for the coordinator

For handoff 5.4, after the line the reviewer proposed:

> Review of the second pass answered on `pr23/docs-2` (`310aab3`). Section 2b now names
> each compared phrase. The test compares those sentences whole, with values computed from
> the original, and leaves 2b out of the compared text. The step parser refuses pipes,
> background jobs, steps after `exit`/`set +e`, other shells and filtered triggers. The
> `cfebe01`/`ef663b2` counts are recounted from those commits when they are in the clone.
> 47 of 48 one-line changes are caught with the inputs. 32 of 32 test files pass both ways.
> ELF rebuilt (326,772 bytes). The S34 row was corrected: the first gate returns with no
> print. Host work only; NOT TESTED on a console.

No new quirk from this round. For the author's proposed POPS-folder-exit quirk I support
the reviewer's qualifier: "`main` appears to set `gp+0x3868` before any loader in every
launch (static read, not traced), so the exit may be unreachable in practice."

## Open questions for the owner

1. Owner questions 1 to 3 from `docs-author.md` stand: who owns db36890's shared-document
   edits; the `$UNDO_` PRESENT-to-PARTIAL move; whether to copy the POPS-folder exit. For
   question 3 the reviewer's lead suggests tracing reachability first.
2. The History class does not run in CI (shallow checkout). Should CI fetch those two
   commits (`fetch-depth: 0` or a targeted fetch)? That is a workflow change, so this track
   did not make it.
