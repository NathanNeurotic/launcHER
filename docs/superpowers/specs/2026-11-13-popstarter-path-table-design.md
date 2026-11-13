# POPStarter r13 measured path table

## Intent

Finish the existing original-under-Unicorn launch tracer and publish a
reproducible table of every path POPStarter r13 requests, in request order,
for every supported launch kind and modelled fallback. Compare that table
with launcHER's resolver and file staging. This branch produces evidence and
a pure path model; it does not change launch behavior.

The purpose is drop-in parity, not preservation of launcHER-only path rules.
Later pieces will implement the measured behavior, bugs included, for
POPStarter launches only. Ember must not change.

## Owner decisions already made

- Trace every launch kind; do not limit the work to USB/SMB.
- The end state for HDD POPStarter launches is r13's `hdd0:__common` mount
  and `pfs1:/POPS/...` layout, including its per-game folders. Ember is
  excluded.
- PR #23 remains draft. Each implementation piece is independently reviewed
  and lands with one reversible `--no-ff` merge; nothing is merged into the
  PR's base branch or marked ready.

## Current state

`pr23/paths` at `f04ef91`, based on `d31d4a7`, contains committed but
unverified tracer changes and a first test file. Its earlier `029f153`
created `tools/trace_original_pops_paths.py`, which starts the original
`main` at `0x870b78` and models its statically linked library calls. The
tracer records file paths, mounts, directory operations, module calls and
launch outcomes without executing the library or entering Sony POPS.

The test file already pins four complete launch traces (`usb`, `hdd`,
`hdd-pp`, `smb`), failure/fallback cases, `argv[0]` forms, quiet/verbose
comparison, a native-resolver comparison and source checks. Its document
check expects `docs/POPSTARTER_PATHS.md`, which does not exist. The old
worktree stays untouched: only the committed state is imported into this
branch. No claim is made that the existing table is correct until the
original runs pass on the imported code.

## Coverage boundary and reference identity

"Every path" means every fixed or parameterized filename the original
constructs for the covered launch kinds, argument forms and modelled branch
answers, in request order. It does not mean a finite row for every possible
string a user can put in `DISCS.TXT`, `VMCDIR.TXT` or another input file.
Content-dependent paths are represented by their construction rule plus
directed examples. All existing `CASES`, `FORMS` and `OTHER_DIFFERENCES` are
included, with new cases only where they distinguish a path rule or expose
a modelling gap. `argc == 0` and the existing single-target forms are in
scope; if the original reads another argument count, that rule is measured
and documented rather than left implicit. This is not an exhaustive fault
matrix for every library call: failure responses are varied when they change
path selection, termination or a fallback branch.

The authoritative original is the owner's private r13 MAIN at
`C:/Users/natha/Github/POPSLoader/bin/POPSLDR/PROFILES/MAIN/POPSTARTER.ELF`,
through `POPSTARTER_TEST_ELF`, with Sony's `POPS.ELF` at
`C:/Users/natha/Github/POPS/POPS.ELF` through `POPS_TEST_ELF`. Package cases
use the companion `POPS_IOX.PAK`, `POPS.PAK` and `IOPRP252.IMG` files already
required by the tracer's `missing_inputs` checks beside `POPS.ELF`. Reuse the
existing decoder/loader identity, size and ISA checks and record their
results; do not introduce a new unverified reference profile or print binary
contents. The implementer and independent reviewer receive the same
environment-variable paths on this PC. If a reviewer cannot run the same
reference inputs, that review is labelled code-only and is not counted as
independent original-execution evidence. Missing companion inputs skip only
their documented cases and preclude a full-coverage claim until supplied.

## Approaches considered

1. **Selected: finish and independently verify the existing tracer, then
   publish the measured table and pure path model.** It executes the
   original's own launch code and exposes wrong assumptions instead of
   preserving them. Model boundaries and skipped cases remain explicit.
2. **Transcribe disassembly or REPOP prose into a table.** Rejected as the
   primary evidence: it is not an execution result and would repeat the
   project's known coverage and reporting errors. Clean REPOP `bc258e48`
   remains a reference only.
3. **Implement launch-path changes immediately and use launcHER's resulting
   paths as the specification.** Rejected: that would encode the current
   resolver before proving the original's behavior and could change Ember.

## Scope of this branch

- Import the two committed tracer/test files from `f04ef91` without
  importing unrelated history or uncommitted files.
- Run the existing tests first. Treat every failure as either a tracer
  modelling defect, an incorrect pinned expectation, or an incorrect table;
  identify which before editing. Do not make a test green by weakening its
  comparison or deleting a case.
- Complete missing model/case coverage needed for every path the original
  requests. Unmodelled library instructions must stop with an error rather
  than silently produce a plausible trace.
- Publish `docs/POPSTARTER_PATHS.md`: every path and relevant call in order
  for each launch kind and fallback, the model answers that select each
  branch, and the corresponding launcHER path/rule. Include the original
  launch-type/prefix rules and the exact remaining differences.
- Provide a deterministic pure comparison/model API for path rules, used by
  host tests, rather than deriving expected values from launcHER's current
  resolver. This is test infrastructure, not a new launch path.
- Register `tools/test_pops_paths.py` in CI and update the inventory, gap
  audit and handoff to distinguish measured, implemented and still-open
  behavior. Record remaining behavior classes as numbered quirks beginning
  at 86; do not create a separate quirk for every repeated filename.
- Keep this branch behavior-neutral in launcher production code. Follow-on
  branches implement launch-argument rules, `IMAGE0.VCD`, `POPS0..9`, the
  `IOPRP.IMG` fallback, and exact per-device/POPS-folder mapping.

## Follow-on behavior order

1. Launch-argument parsing as a pure function, including `XX.`/`SB.` prefix
   placement/case, launch types, and the original `cdrom` exit.
2. Resolver candidates and length/failure rules, including `IMAGE0.VCD`,
   `POPS0..9`, and HDD partition retries.
3. Exact device/POPS-folder selection, including numbered folders and the
   owner-approved HDD `__common` mount and per-game paths.
4. `IOPRP.IMG` fallback and the original package search rules.
5. Independent review and one merge per piece, with every remaining
   difference indexed rather than called parity.

## Evidence and negative controls

- Host tests without reference inputs must exercise native and source
  checks; original-dependent cases must report explicit skips.
- With `POPSTARTER_TEST_ELF` and, where needed, `POPS_TEST_ELF`, compare the
  complete original event/path sequences, state and outcome. Do not compare
  only a subset of paths that happens to match.
- Include quiet versus verbose runs, all four complete launch kinds,
  missing packages/files, numbered-folder fallbacks, malformed arguments,
  long names, and every existing `OTHER_DIFFERENCES` case.
- Negative controls: an unmodelled library call or unsupported EE
  instruction must fail loudly; a missing optional input must be reported as
  a skip; an incorrect table entry must fail rather than be regenerated and
  accepted in the same run; two model responses that select different paths
  must produce different table rows.
- Logs contain synthetic paths, operation metadata, addresses and counts,
  never proprietary binary contents, BIOS images, cards, saves, real shares
  or key material.
- Run full host sweeps with and without reference inputs serially. Build
  release and trace variants as regression checks even though this branch
  intends no production behavior change. Label all results host, Unicorn or
  PS2SDK build; no emulator or physical-console claim.

## Constraints and non-goals

- No changes to Ember, launch execution, physical devices, real PCSX2
  cards/shares, or `RIPPCSX2` itself.
- No `ps2rig` or physical-console run without the owner present and a
  specific authorized test.
- No Sony/POPStarter binaries, disc images, corpus files or keys committed.
- No merging PR #23 or any other PR, no ready-for-review transition, no
  force-push/history rewrite, and no deleting older branches/worktrees.
- No claim that a modelled full launch proves a real game boots, that a path
  exists on a real device, or that staging equality proves runtime parity.

## Builder decisions

- Whether a failure is in the tracer model or the pinned table must be
  proven from the original instruction path and model boundary.
- Exact report formatting may follow the existing tracer's deterministic
  summaries; generated tables must be reviewed before being accepted.
- Optional-reference tests may skip only when their documented inputs are
  absent, and the final report must give those skip counts.
- Minor quirk wording and grouping may follow the existing register's
  conventions without changing the measured difference.

## Acceptance

The path document contains every pinned original path and the measured
launcHER difference, all original/native/source tests pass in both reference
modes, negative controls prove the harness cannot silently agree, full host
sweeps and both builds pass, and independent review returns `merge`.
Production path behavior is unchanged in this branch. Remaining work and
owner decisions are listed explicitly; no drop-in or console-safety claim is
made.
