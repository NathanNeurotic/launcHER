# POPStarter Measured Path Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a verified table of every launch-selected path POPStarter r13 requests, a deterministic pure comparison model, and the exact launcHER differences, without changing launch behavior.

**Architecture:** Import the committed `f04ef91` tracer/test state, then execute the original MAIN under Unicorn with modelled library services. Pin original event sequences independently of launcHER's resolver, render those sequences into a reviewed document, and compare them with the existing native resolver and source. This branch is measurement-only; production path changes follow in separate reviewed branches.

**Tech Stack:** Python 3 `unittest`, Unicorn MIPS64, host C through `ctypes`/GCC, PS2SDK CMake/Docker for regression builds.

**Spec:** `docs/superpowers/specs/2026-11-13-popstarter-path-table-design.md` (owner-approved), including its coverage boundary, private-reference identity and exact-HDD follow-on decision.

## Global Constraints

- Match POPStarter r13 exactly first, bugs included; do not preserve a launcHER-only path rule as the default.
- This branch changes no launcher production behavior. Ember must not change.
- Use only the committed `f04ef91` tracer/test input; leave `launcHER.worktrees/paths` untouched.
- Never commit, print or log proprietary reference contents, BIOS images, cards, saves, real shares or keys. Logs contain synthetic paths, operation metadata, addresses and counts only.
- Original-dependent tests skip only for their documented missing inputs and report skip counts; a skip is not a full-coverage pass.
- Every remaining behavior class is indexed as a numbered quirk beginning at 86. Follow-on path implementation uses the owner-approved exact HDD `__common` layout for POPStarter only.
- One independent whole-branch review before one `--no-ff` merge into `codex/popstarter-replacement`; PR #23 stays draft and is never marked ready here.
- Label evidence host, Unicorn or PS2SDK build. No PCSX2, game-boot, runtime-safety or physical-console claim.

## Review Focus

- A missing model must not silently invent a path: Task 2 makes an unmodelled library call and an unsupported EE instruction fail loudly.
- A missing optional input must not become hidden coverage: Tasks 1 and 2 assert named skips and report their counts.
- A self-generated wrong expectation must not pass: Task 2 corrupts one literal expected path and requires the comparison to fail.
- Quiet/verbose profiles and different model answers must preserve/change exactly the measured paths: Task 2 checks the original report, not a copied rule.
- Parameterized filename rules must not be mistaken for exhaustive user-content examples: Task 3 pins `original_search` to literal `IMAGE0.VCD` and `POPS0..9` candidates and documents that boundary.

---

### Task 1: Import and characterize the committed tracer

**Files:**
- Create: `tools/trace_original_pops_paths.py` from `f04ef91`
- Create: `tools/test_pops_paths.py` from `f04ef91`
- Reference: `docs/superpowers/specs/2026-11-13-popstarter-path-table-design.md`

**Interfaces:**
- Consumes: committed `f04ef91` versions only; `POPSTARTER_TEST_ELF` and `POPS_TEST_ELF` from the spec.
- Produces: baseline failure/skip records, with case name, first differing summary line and whether the cause is tracer model, pinned expectation or missing document/CI registration. No production changes.

- [ ] **Step 1: Refresh the base without rewriting history**

Run `git merge --no-ff codex/popstarter-replacement` to bring the current PR head, including `docs/PR23_HANDOFF_2026-11-13.md`, into this branch. Do not rebase. Require a clean resulting worktree except for this plan's new file.

- [ ] **Step 2: Import the two files byte-for-byte from the committed source**

Run `git show f04ef91:tools/trace_original_pops_paths.py` and `git show f04ef91:tools/test_pops_paths.py`, writing those exact outputs to the corresponding new files. Require `git diff --exit-code f04ef91 -- tools/trace_original_pops_paths.py tools/test_pops_paths.py` to produce no diff and return zero. Do not copy from the old worktree.

- [ ] **Step 3: Run the untouched baseline without references**

Run `env -u POPS_TEST_ELF -u POPSTARTER_TEST_ELF -u POPS_TROJAN_CORPUS python tools/test_pops_paths.py` with fresh `TMP`/`TEMP`/`TMPDIR`.

Expected: `Source.test_document` fails because `docs/POPSTARTER_PATHS.md` is absent and `Source.test_ci_runs_this_file` fails because the workflow has no path test step. Native tests must pass before any edits. Record all other failures verbatim for Task 2; do not create the document yet.

- [ ] **Step 4: Run the untouched baseline with the specified references**

Run the same file with `POPS_TEST_ELF=C:/Users/natha/Github/POPS/POPS.ELF` and `POPSTARTER_TEST_ELF=C:/Users/natha/Github/POPSLoader/bin/POPSLDR/PROFILES/MAIN/POPSTARTER.ELF`.

Expected: every available original `CASES`/`FORMS` result is compared with the pinned table; failures identify case and first mismatch. Missing companion files produce named skips and their counts are recorded, never called full coverage. Save the output outside the repository.

- [ ] **Step 5: Commit the unmodified baseline**

Commit only the two imported files with `test(pops): import original launch path tracer`. The body records that execution/fixes are pending and `NOT TESTED on a console`.

### Task 2: Prove the original tracer and its negative controls

**Files:**
- Modify: `tools/trace_original_pops_paths.py` only for a demonstrated model defect
- Modify: `tools/test_pops_paths.py`

**Interfaces:**
- Consumes: `trace(argv, files, ...)`, `run_case(name, watch=())`, `run_form(argv0)`, `summary(report, focus=None)`, `missing_inputs(files)` and the Task 1 failure records.
- Produces: deterministic original reports/summaries for all `CASES`, `FORMS` and `OTHER_DIFFERENCES`; a `Negative` test class with `test_bad_table_entry_fails`, `test_unmodelled_code_fails`, `test_missing_inputs_name_skips`, `test_branch_answer_changes_summary` and `test_quiet_does_not_change_paths`.

- [ ] **Step 1: Add failing negative-control tests before changing the tracer**

Add tests that: corrupt one literal expected path and require mismatch; invoke an unmodelled library address and an unsupported EE instruction and require an exception; require a missing optional input to name its skip; require two different branch answers to produce different summary rows; require quiet and verbose reports to have the same paths. Reuse the existing tracer API and synthetic files; do not weaken full-summary comparison to a subset.

- [ ] **Step 2: Verify the controls fail for the intended reason**

Run `python tools/test_pops_paths.py Original Negative` without and with references. Expected: any missing assertion fails; any already-valid control passes and is recorded as a characterization, not a new fix. Baseline failures from Task 1 must fail at the same case and first differing line, never be hidden by these tests.

- [ ] **Step 3: Fix only demonstrated model or expectation defects**

For each Task 1 mismatch, inspect the original instruction path and the model boundary. Classify it as model defect or wrong pinned expectation before editing. Add the focused failing regression first, then make the smallest repair. Preserve `main = 0x870b78`, original call order, synthetic file contents and loud failure on unmodelled code. Do not change launcHER's resolver.

- [ ] **Step 4: Run all original and native comparisons**

Run `python tools/test_pops_paths.py Original Native Source.test_tracer` in both reference modes. Expected: all original cases/forms and native comparisons pass, with only documented original-input skips. The four complete runs end in `ExecPS2` at `0x87c1cc`; quiet/verbose paths match.

- [ ] **Step 5: Commit the verified tracer**

Commit `test(pops): verify original launch path traces`, listing cases, skips, negative controls and any model/expectation corrections. `NOT TESTED on a console`.

### Task 3: Publish the measured table and pure difference model

**Files:**
- Create: `docs/POPSTARTER_PATHS.md`
- Modify: `tools/test_pops_paths.py`
- Modify: `.github/workflows/build.yml`
- Modify: `docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md`
- Modify: `docs/POPSTARTER_R13_INVENTORY.md`
- Modify: `docs/POPSTARTER_GAP_AUDIT_2026-11-11.md`
- Modify: `docs/CLOUD_CONTINUATION.md`
- Modify: `docs/PR23_HANDOFF_2026-11-13.md`

**Interfaces:**
- Consumes: Task 2 reports, `summary`, `CASE_TABLE`, `FORM_TABLE`, `OTHER_DIFFERENCES`, `native_candidates(argv0)` and `original_search(search)`.
- Produces: a complete reviewed path/difference document; pure `original_search(search) -> list[str]` rules for partition `IMAGE0.VCD`, USB `POPS0..9`, and HDD `__.POPS0..9`; CI registration; numbered remaining differences.

- [ ] **Step 1: Add document/model tests before writing the document**

Require every `T.CASES` name, every summary line for `USB`, `HDD`, `PP_IMAGE`, `SMB`, every `FORM_TABLE` argument and every `OTHER_DIFFERENCES` name to appear in `docs/POPSTARTER_PATHS.md`. Add literal assertions that `original_search(USB_SEARCH, "GAME")` returns `mass:/POPS/GAME.VCD` followed by `mass:/POPS0/GAME.VCD` through `mass:/POPS9/GAME.VCD`, `original_search(HDD_SEARCH, "GAME")` returns `hdd0:__.POPS:pfs:/GAME.VCD` followed by `hdd0:__.POPS0:pfs:/GAME.VCD` through `hdd0:__.POPS9:pfs:/GAME.VCD`, and partition search returns `hdd0:PP.GAME:pfs:/IMAGE0.VCD`. Add a negative control showing one wrong path is rejected.

- [ ] **Step 2: Verify document/model tests fail for missing content**

Run `python tools/test_pops_paths.py Source Native` without references. Expected: only document and CI-registration failures identified in Task 1; existing pure/native behavior is unchanged.

- [ ] **Step 3: Write the measured path document and difference register**

Use Task 2's actual summaries to document every fixed and parameterized path in order, the model answer selecting each branch, outcome/state, and launcHER's measured current rule. Include all cases, argument forms and `OTHER_DIFFERENCES`; distinguish parameterized construction rules from arbitrary user-content strings. Assign sequential quirks beginning at 86 to remaining behavior classes and update inventory/audit/handoff rows without implying production path parity. Record the exact-HDD decision as follow-on work, not as behavior in this branch. Add `run: python tools/test_pops_paths.py` beside the OSD test in `.github/workflows/build.yml`.

- [ ] **Step 4: Run path and document checks in both reference modes**

Run `python tools/test_pops_paths.py` and `python tools/test_pops_doc_claims.py`, each without and with references. Expected: all pass, with only documented original-input skips; no stale "no table" or "no OSD loader" claims remain.

- [ ] **Step 5: Commit the measured table**

Commit `docs(pops): publish measured launch path table`, listing the case/form counts, quirk range and evidence level. `NOT TESTED on a console`.

### Task 4: Full verification, independent review and reversible merge

**Files:**
- Create: `docs/handoff/2026-11-13/popstarter-path-table.md`
- Modify: `docs/PR23_HANDOFF_2026-11-13.md`
- Modify: draft PR #23 description after the merge

**Interfaces:**
- Consumes: all preceding commits and the approved spec.
- Produces: one reviewed branch ready for a single merge, exact artifact hashes, open follow-on work and evidence levels.

- [ ] **Step 1: Run complete sequential host sweeps**

Run every `tools/test_*.py` one file at a time, without references and then with the spec's references, using fresh separate `TMP`/`TEMP`/`TMPDIR` directories. Expected: **38/38 files pass in each mode**. Preserve logs and record all optional-input skips.

- [ ] **Step 2: Build release and trace in the standard container**

Initialize `launcher/iop/mmceman`, mount the worktree and main checkout with POSIX paths, and resolve Git metadata as in the OSD build. Build release and `-DLAUNCHER_BOOT_TRACE=ON -DDEBUG=ON` variants. Expected: both print `handoff layout: OK` and the actual branch revision. Record sizes and SHA-256 values; do not call them safe or run them on a console.

- [ ] **Step 3: Finalize evidence and obtain independent review**

Create the evidence report with branch heads, case/form counts, every remaining difference, and exact host/Unicorn/build levels. Give a fresh reviewer the complete diff, spec, plan, review focus and test evidence. Answer every finding and re-review as needed; no merge on a `merge-after-fixes` verdict.

- [ ] **Step 4: Merge once and update draft PR #23**

After green verification and a `merge` verdict, merge with `git merge --no-ff`, verify merge-tree identity with the tested branch, and verify the resulting build. Push the PR and side branch, update only the draft description with evidence and `NOT TESTED on a console`, and update the handoff. Do not merge PR #23 or mark it ready. Next pieces are the measured launch-argument, resolver, exact HDD/device-folder and IOPRP rules.
