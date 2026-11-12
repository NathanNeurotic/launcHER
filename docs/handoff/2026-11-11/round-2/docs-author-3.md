# Gap audit and status documents: answer to review 2

Branch `pr23/docs-2`, from `ef663b2`, pushed. Head `8499217`. Commits:

- `34814ea` wip(pops): second correction pass of the gap audit: header, S21 wording and section 2b
- `549be01` wip(pops): audit and inventory rows brought up to `ef663b2`
- `b77a4e8` wip(pops): doc-claims test pins the audit's phrases and parses the workflow steps
- `dd34b43` wip(pops): pin the BIOS handler gates and the once-flag condition
- `3ac02d8` wip(pops): S34 for the BIOS handler gates; pin main's range sentence
- `8499217` docs(pops): audit section 19a for the second correction pass

Files changed: `docs/POPSTARTER_GAP_AUDIT_2026-11-11.md`, `docs/POPSTARTER_R13_INVENTORY.md`,
`docs/CLOUD_CONTINUATION.md` and `tools/test_pops_doc_claims.py`. No other files changed. No C
source changed. I did not edit README.md, `docs/pops-setup.html`,
`docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md` or `docs/PR23_HANDOFF_2026-11-11.md`; text proposed for
them is below. Everything here is host work. NOT TESTED on a console. No emulator of the whole
machine was run.

## Per finding

1. **Shared documents edited (db36890).** This is an owner/lead decision under handoff section 8.
   I made no change and recorded the question below. This pass edits only the four files it was
   allowed to edit. The stale facts the reviewer listed are fixed in those files: the test-file
   count (now 32/30, S33) and the IGR skin status (MISSING to PARTIAL). The same staleness in
   README.md and `pops-setup.html` is handled by the proposed text below.
2. **The BIOS handler's POPS-folder -666 exit.** This is now in section 4 as its own row, placed
   before the game-folder row (`0x880338..0x880380`). The row covers:
   - the `gp+0x3868` test and the `jal` at `0x880348`;
   - the scope test at `0x880360..0x880368`;
   - `sw gp+0x38dc` at `0x880374` and `-666` at `0x880378`;
   - the scope asymmetry (all games returns -666; game goes on and loads);
   - the extra writes of the check itself;
   - `main`'s earlier call at `0x873f9c` (skipped when `gp+0x3888 != 0`) and its store at
     `0x87425c`.

   I verified it under Unicorn with `FUN_008d8958` executing and only its callees modelled. That
   is S30: 64 + 4 runs, and every outcome matched the reviewer's. The static checks are S32
   (seven callers, the -666 stores of all five loaders, the return values of `FUN_008d8958`) and
   S34 (the gates come before both exits; the once-flag read at `0x8804ec` is the only one).

   In the process I found and fixed one overstatement of my own. The game-folder row said a
   game-scope call "always" leaves `gp+0x38e0 = 1`, but the gates at `0x8801b4..0x880334`
   return 0 before the flag is read. The row now states that condition.

   Also changed:
   - The inventory BIOS.BIN row and the section 4 launcHER paragraph say the exit is not copied
     by `0945127`.
   - The 3a `gp+0x3868` row lists the seven call sites (an earlier draft of this pass said six;
     corrected).
   - OSD, TROJAN and PATCH have the same call-plus-`-666` pattern. Their scope handling is
     stated as not traced.
3. **Pin every statement the test claims to pin.** `tools/test_pops_doc_claims.py` was rewritten.
   - Each claim is now compared as a whole phrase computed from the original's bytes, not a
     token: the S21 census per range, the slot list against `SLOTS` entry by entry, the S24
     sentence, the section 9 sentence and the S28 sentences.
   - New pins:
     - the BIOS exits, gates and once-flag condition;
     - S32 callers, stores and returns;
     - the IGR return values and section 6 sentences;
     - the inventory IGR sentence and the inventory `$USBDELAY_n` sentence;
     - the `gp+0x38e0` sites;
     - `main`'s range and frame;
     - the S15 and section 12 corpus counts with `POPS_TROJAN_CORPUS`.
   - The audit paragraph "What tools/test_pops_doc_claims.py checks" was rewritten to list
     exactly what is pinned and what is not.
   - Mutants, 40 in all (the reviewer's 22 plus 18 new): with the inputs 38 are caught.
     - The reviewer's M04, M06, M08, M13, M14, M15, M16, M17 and M20 used to survive and are now
       caught.
     - M07 (README) and M09 (the S27 result count) still survive. That is expected, and section
       19a says why.
4. **Real workflow step parsing.** There is a small hand-written YAML parser (PyYAML is not a CI
   dependency) plus `steps_that_run()`. A test file counts as run only if all of these hold:
   - an uncommented `run:` line starts `python|python3|py tools/<file>`, also after `&&` or `;`;
   - there is no `||` on that line;
   - the step and the job have no `if:` other than `always()`, `success()` or `true`;
   - there is no `continue-on-error`;
   - the trigger is push or pull_request.

   "Every other file" must be a step of `build.yml` job `host-tests`. A test of the parser itself
   covers these synthetic cases:
   - a commented-out step and run line;
   - `if: false`, `if: ${{ false }}`, another condition and `if: always()`;
   - `continue-on-error`, `|| true`, an `echo` mention and a job-level `if:`;
   - a manual trigger, a flow-list trigger and a block-scalar `run:`.

   Mutants M11 and M23, and N01..N05 (`${{ false }}`, `continue-on-error`, `|| true`, echo,
   push-only `if:`), are caught without inputs.
5. **Overstated CLOUD_CONTINUATION sentence.** Replaced with what was run:
   - the first correction pass ran on the uncommitted tree: 27 files, 26 exit 0 in pass 2 plus
     `test_pops_external.py` exiting 1 at the link step and passing when re-run alone;
   - the reviewer's sequential run at `ed30f55` gave 27/27 both ways;
   - this pass's runs are in audit section 19a.

   The old sentence is in the test's withdrawn list (mutant N16 puts it back and is caught both
   ways).
6. **IGR -666 row.** The section 6 row now covers:
   - the reachable results at that call: only 1 or -666, because the function has already tested
     both flags;
   - the extra writes on failure: `gp+0x3460` and `gp+0x3868`, plus `0x91be68` on
     `mass0:/POPS` for `mass:`;
   - `0x873f9c`/`0x87425c` for when `gp+0x3868` is already 1;
   - that S23 forced results which cannot occur.

   I verified it under Unicorn (S31, 8 runs, matching the reviewer's). The inventory IGR row says
   the same and is pinned.
7. **Test-file defects.**
   - `MAIN_FUNCTION = (0x870b78, 0x87c218)` is now an exclusive end. The test checks `jr ra` at
     `0x87c210`, the delay slot `0x87c214` and the next function's frame at `0x87c218`. The audit
     says `main` is `0x870b78..0x87c214` (last instruction).
   - A set but unusable `POPSTARTER_TEST_ELF` is now an error, not a skip. Checked:
     - a missing path exits 1;
     - `POPS.ELF` given as `POPSTARTER_TEST_ELF` exits 1;
     - capstone missing is a failure;
     - a `POPS_TROJAN_CORPUS` that is not a folder exits 1.

Brought up to `ef663b2`:
- The audit header and the inventory header list the five merges (`95ba812`, `173d5de`,
  `0945127`, `21c3476`, `f22a69f`).
- The launcHER paragraphs of sections 3, 4, 5a, 6, 8, 9, 11, 13, 14 and 16 describe them, only
  as far as the merged code and its tests show.
- Inventory status changes:
  - the IGR skin and `BIOS.BIN` go from MISSING to PARTIAL;
  - `$UNDO_` goes from PRESENT to PARTIAL, citing the expected-failure test in
    `test_pops_user_bios.py`;
  - `$USBDELAY_n`: the parser is fixed and the default is 0;
  - SMB `SB.` and the physical disc host part are noted.
- The handoff defect, TROJAN and CHEATS.TXT rows say only "in progress on a side branch".

## Commands and results

All runs are from the worktree root, `<workspace>/launcHER.worktrees/docs-2`, in Git
Bash. TMP, TEMP and TMPDIR were set to `<scratch>/tmp-docs2`.

- **Full host list, run 1.** Ran `sh <scratch>/docs2/run_all.sh` in the background: every
  `tools/test_*.py`, one at a time, in two passes, at `b77a4e8`. After `b77a4e8` only the
  documents and `test_pops_doc_claims.py` changed. Results are in
  `<scratch>/docs2/runs/summary.txt` and the per-file logs `p1_*.log`/`p2_*.log`.
  - Pass 1, with the reference variables unset: 32 files, each exit 0. Skip counts are listed in
    audit section 19a; doc_claims skipped 11.
  - Pass 2, with `POPS_TEST_ELF` and `POPSTARTER_TEST_ELF` set: 32 files, each exit 0. Still
    skipping: `test_pops_external.py`, `test_pops_launch_hooks.py` and
    `test_pops_progressive.py`, 3 each (inputs not given), and doc_claims 1 (the corpus class).
  - `test_pops_user_bios.py` reports `OK (expected failures=1)` in both passes. That is its
    known-gap `$UNDO_` test.
- **`python tools/test_pops_doc_claims.py` at `8499217`:**
  - With no inputs: 17 tests, `OK (skipped=11)`, exit 0.
  - With `POPS_TEST_ELF`, `POPSTARTER_TEST_ELF` and `POPS_TROJAN_CORPUS`: 17 tests, `OK`, exit 0.
  - With `POPSTARTER_TEST_ELF=C:/nonexistent/POPSTARTER.ELF`: exit 1.
  - With `POPSTARTER_TEST_ELF=<POPS.ELF>`: exit 1.
  - With `POPS_TROJAN_CORPUS=C:/nonexistent`: exit 1.
- **Mutants.** Ran `python -I <scratch>/docs2/mutants.py` at `3ac02d8`. Each mutant goes into a
  fresh `git archive HEAD docs README.md .github tools` copy and is run without inputs and with
  all three. The baseline passes both ways.
  - 40 mutants. With the inputs, 38 are caught and M07 and M09 survive. Without inputs, 12 are
    caught: M01, M10, M11, M18, M22, M23, N01..N05 and N16.
  - An earlier run at `dd34b43` was the same except for N12 (main's range sentence), which
    survived; I then added the `main` range pin.
  - Output: `<scratch>/docs2/mutants2.out` (and `mutants.out` for the earlier run).
- **S30.** `python -I <scratch>/docs2/bios_popsdir.py` gave the BIOS handler 64 + 4 runs; the
  results are in audit S30 (`<scratch>/docs2/bios_popsdir.out`).
- **S31.** `python -I <scratch>/docs2/igr_popsdir.py` gave the IGR skin function 8 runs; the
  results are in audit S31 (`<scratch>/docs2/igr_popsdir.out`).
- **S32.** `python -I <scratch>/docs2/scan3868.py`, plus capstone disassembly
  (`<scratch>/docs2/disasm.py`) of `0x8d8958..0x8d8b10`, `0x880338..0x880380` and the loaders.
- **S34.** Disassembly of `0x8801b4..0x880338` and `0x880a0c..0x880a30` (the shared return
  `lw v0,0xc0(fp)`).
- **Corpus.** `python -I <scratch>/docs2/corpus.py`: 3,952 TROJAN / 509 unique and 870 PATCH /
  10 unique; each hook word at offset 24 matches `SLOTS`.
- **Container build:**
  - `MSYS_NO_PATHCONV=1 docker run --rm -v <worktree>:/workspace -w /workspace ghcr.io/ps2homebrew/ps2homebrew:main sh -c "apk add cmake && cd / && git config --global --add safe.directory /workspace && cd /workspace && cmake -B build-docs2 && cmake --build build-docs2 --target launcHER"`
  - The first try stopped at 28% (`mmceman.irx`) because the worktree had no submodule checkout.
    I ran `git submodule update --init launcher/iop/mmceman` and ran the build again: exit 0,
    `release/launcHER.elf` 326,772 bytes, warning "No Git revision available: writing
    version=unknown".
  - Not run on anything. `build-docs2/` was removed afterwards. The submodule checkout is still
    initialised in the worktree, with no tracked change.
- **Pushes:** `git push -u origin pr23/docs-2`, then `git push origin pr23/docs-2` after each
  commit. The remote ref equals `8499217`.
- **Hygiene:** a grep of the added lines and commit messages for AI attribution and email
  addresses found nothing. The test has no hex run of 24 or more digits.

## Not done

- No console run, no PS2 rig, no whole-machine emulator.
- S22, S23 and S27 were not re-run by this pass. S30 and S31 are host Unicorn runs with modelled
  callees.
- The OSD, TROJAN and PATCH scope handling after the POPS folder check was not traced; the audit
  says so.
- Not traced end to end: which real launches reach the BIOS/IGR POPS-folder exit, that is, where
  `main`'s check at `0x873f9c` is skipped and `gp+0x3868` is not set.
- The launcHER paragraphs of sections 4 to 14 describe the merged code from reading it and its
  tests. No test checks them against the code.
- README.md (line 718) and `docs/pops-setup.html` (lines 552-555) still say the IGR skin is not
  implemented. They were not edited (off-limits); text is proposed below.
- Finding 1 is left to the owner/lead.
- The mutant survivors M07 and M09 remain by design. The test does not read README.md beyond the
  withdrawn sentences, and it does not re-run the S27 loaders.

## Proposed text for files this track may not edit

**README.md, line 718.** It says "not implemented" for the IGR graphics, which is stale since
`173d5de`. Replace the bullet with:

> - **Custom IGR graphics (`IGR_BG.TM2`, `IGR_YES.TM2`, `IGR_NO.TM2`):** read from the same folder
>   as the game's `.VCD` (POPStarter reads them from the device's `POPS` folder; the two are the
>   same when the VCD sits in `POPS`). Each file is copied over Sony's own picture if it is no
>   larger than the slot (`IGR_BG.TM2` 312,064 bytes, the other two 7,612 bytes); a missing or
>   too large file leaves Sony's picture. They show only with `$IGR0`..`$IGR2`, because without an
>   IGR command launcHER exits directly and the confirmation screen never opens. Not yet tested
>   on a console.

README.md and `docs/pops-setup.html` do not mention `BIOS.BIN` (I grepped both), so nothing there
is stale on it. Whether to document the `0945127` stage for users is left to the owner.

**`docs/pops-setup.html`, lines 552-555.** Replace the "not implemented" heading and paragraph
with:

```html
<h3>Custom IGR Background Graphics</h3>
<p>
  <code>IGR_BG.TM2</code>, <code>IGR_YES.TM2</code> and <code>IGR_NO.TM2</code> replace the pictures of the
  exit confirmation screen. launcHER reads them from the folder that holds the game's <code>.VCD</code>
  (POPStarter reads them from the device's <code>POPS</code> folder). A file larger than its slot is ignored.
  They are shown only with <code>$IGR0</code> to <code>$IGR2</code> in <code>CHEATS.TXT</code>. Not yet tested on a console.
</p>
```

**`docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md`, quirk candidates.** These are for the owner/lead; I
did not add them.

> ### POPS folder exit of the `BIOS.BIN` and IGR skin loaders (not copied)
> POPStarter's BIOS handler (`0x880338..0x880380`) and IGR skin function (`0x87e48c..0x87e4c4`)
> call the POPS folder check `FUN_008d8958` when `gp+0x3868` is not 1. On a missing folder the
> check sets `gp+0x38dc` (abort, every later current-game loader skipped), `gp+0x3460` and
> `gp+0x3868`. The IGR function and an all-games `BIOS.BIN` call then return -666 with nothing
> opened. A game `BIOS.BIN` call ignores the failure and still loads (scope asymmetry, a bug in
> the original that parity would copy). `main` normally makes the check first (`0x873f9c`,
> skipped when `gp+0x3888 != 0`, e.g. `SB.` launches), so the loaders' exits are reached only
> where that was skipped. launcHER's `0945127` and `173d5de` stages do neither the check nor the
> writes. Gap audit section 4 and section 6, S30, S31, S32. Host emulation only.
>
> ### `FUN_008d8958` writes two more flags on failure
> Besides the abort flag, a failed POPS folder check sets `gp+0x3460` (the game-folder-missing
> flag the later loaders test) and `gp+0x3868`, and on `mass:` calls `0x91be68` on
> `mass0:/POPS`. Any copy of the check must copy these writes. Gap audit S32.

**`docs/PR23_HANDOFF_2026-11-11.md`.** Suggested status line for doc 5.4:

> Review 2 answered on `pr23/docs-2` (`8499217`): findings 2 to 7 changed in the four allowed
> files and the doc-claims test (38 of 40 mutants caught with the inputs); finding 1 is an
> owner/lead decision.

## Owner questions

1. Finding 1: should db36890's edits to README.md, `docs/pops-setup.html`,
   `docs/CLOUD_CONTINUATION.md` and the inventory stay as this track's own lines, or be dropped
   and redone by hand (handoff section 8)? And who updates README.md and `pops-setup.html` with
   the text above?
2. Is `$UNDO_` now PARTIAL, rather than PRESENT, acceptable? The expected-failure test in
   `test_pops_user_bios.py` is a launch that fails where the original goes on.
3. Should launcHER copy the BIOS/IGR POPS folder exit, including the scope asymmetry? It reads
   these files from the `.VCD`'s folder, not `POPS/`, and that path decision (increment 2) is
   still open.
