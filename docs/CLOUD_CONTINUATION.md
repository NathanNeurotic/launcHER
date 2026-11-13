# Continuation checkpoint

Continue [draft launcHER PR #23](https://github.com/NathanNeurotic/launcHER/pull/23) on `codex/popstarter-replacement`. Fetch before editing, preserve newer work, publish validated incremental commits on this same PR, and keep the PR draft and unmerged.

Commits, PR text and documents carry no AI or assistant attribution of any
kind (no co-author trailer, no "generated with" line). Earlier instructions
in this folder that asked for such a trailer were withdrawn on 2026-11-11.

## Current state — 2026-11-11

This section is the current one. Everything under "History" further down is
kept for the record and is not a description of today's state.

### Heads

- launcHER: `codex/popstarter-replacement` at `cfebe01` when the 2026-11-11
  session started, and at `ef663b2` when the second correction pass of the
  gap audit began (after the merges `95ba812` config text, `173d5de` IGR
  skin, `0945127` `BIOS.BIN`, `21c3476` `SB.` network files, `f22a69f`
  physical disc host part, and the handoff commit). Fetch and recheck.
  PR #23 is draft, base `EMBER`. Work that was in progress on side branches
  at `ef663b2` (the handoff defect, TROJAN files, the review answers for the
  config-text merge) is described in
  [PR23_HANDOFF_2026-11-11.md](PR23_HANDOFF_2026-11-11.md); this document
  does not anticipate its outcome. Later the same day all three were merged,
  with the SMB review answers and the review corrections; that file's
  section 2 lists the merges. The rest of this document was not rewritten
  after them.
- REPOP: the live line is `main` at `bc258e48`. To reproduce the REPOP
  numbers quoted in the gap audit, use a clean checkout or a `git archive`
  export of that commit. The worktree `REPOP.worktrees/pr23` is not a
  stable reference: it is on a local working branch that has had commits
  newer than `bc258e48` since 06:25 (-0800) on 2026-11-11, and REPOP's
  `tools/parity_report.py` prints other numbers there.
- REPOP `feat/psxcore-validation` (`d3452068`) is fully superseded: it is an
  ancestor of the branch that was squash-merged into `main` as `0d5ca939`
  (REPOP PR #53). Do not continue on it. The older checkout
  `C:/Users/natha/Github/REPOP` still has it checked out; leave that
  checkout alone. Every link in `docs/` that pointed at that branch now
  points at `main`.

### What is known and what is not

Read [POPSTARTER_GAP_AUDIT_2026-11-11.md](POPSTARTER_GAP_AUDIT_2026-11-11.md)
first. It lists, per area, what the original does with addresses, what
launcHER does with file and line, the gap, and how well each statement is
supported. [POPSTARTER_R13_INVENTORY.md](POPSTARTER_R13_INVENTORY.md) was
corrected from it on the same day. Both were brought up to `ef663b2` by a
second correction pass (audit header and section 2b). Nothing in either was
run on a console.

The finding that matters most to users: every TROJAN file found in the
community fix packs loads outside the POPS core, launcHER rejects all of
them, and a rejected fix file ends the launch. launcHER's side of that was
measured on a host by three separate runs, and so was the original's side
(its loader accepts all 509 distinct files): the mapping run, an
independent review's run and a correction pass, each with its own harness
(gap audit, S27). In all of them file calls are models and no payload was
executed. NOT TESTED on a console.

### Local verification recipe (Windows, Git Bash)

Host tests, from the repository root. The two reference files stay outside
the repository.

```sh
export PYTHONDONTWRITEBYTECODE=1
# first pass: no reference inputs (what CI runs)
for t in tools/test_*.py; do python "$t" || echo "FAILED $t"; done
# second pass: with the reference inputs
export POPS_TEST_ELF="C:/Users/natha/Github/POPS/POPS.ELF"
export POPSTARTER_TEST_ELF="C:/Users/natha/Github/POPSLoader/bin/POPSLDR/PROFILES/MAIN/POPSTARTER.ELF"
for t in tools/test_*.py; do python "$t" || echo "FAILED $t"; done
```

Needs Python with `unicorn` and `capstone`, and a host `gcc` (each test
builds `common/src` into a shared library). At `cfebe01` there were 26
`tools/test_*.py` files and CI ran 24 of them, all without the reference
inputs: 23 as steps of the `host-tests` job in `build.yml` and
`test_launch_args.py` in its own workflow. At `ef663b2` there are 32 and CI
runs 30: 29 as `host-tests` steps and `test_launch_args.py` (gap audit
S33). The list below is the current one; `tools/test_pops_doc_claims.py`
compares it with the workflow steps that start each file in a way whose
failure fails the step, as far as a text parser can tell (an uncommented
`run:` line that starts `python tools/<file>`, with no `||`, pipe or
background `&` on it and no `exit` or `set +e` before it; in a step and job
with no `if:` other than `always()`/`success()`/`true`, no
`continue-on-error` and the default shell, `bash` or `sh`; in a workflow
triggered by push or pull request without filters; the rule and what it
cannot see are in gap audit section 2b) and fails when they disagree, so
change both together. Where `cfebe01` and `ef663b2` are in the clone (not
in CI's shallow checkout) it also recounts the two sentences above from
those commits. Optional third input for that test: `POPS_TROJAN_CORPUS`, a
folder of community `TROJAN_n.BIN`/`PATCH_n.BIN` files (REPOP's
`popstarter/` folder was used); it checks the audit's corpus counts and
hook slots.

<!-- ci-coverage:begin -->
- Run by no workflow: `test_pops_builtin_db.py`, `test_pops_progressive.py`.
- Run by `launch-args.yml`, not by `build.yml`: `test_launch_args.py`.
- Every other `tools/test_*.py` file is a step of the `host-tests` job in `build.yml`.
<!-- ci-coverage:end -->

Without the reference inputs the Original classes are skipped, so a green
CI run says nothing about agreement with POPStarter. On a busy machine the
two passes take tens of minutes. Run them one after the other, not at the
same time in one checkout: eight test files build into `build/pops-host/`
under fixed names (`test_popfs.py`, `test_pops_external.py`,
`test_pops_fatfs.py`, `test_pops_modes.py`,
`test_pops_runtime_corrections.py`, `test_pops_vmc.py`,
`test_sony_ioman_layout.py`, `test_subq_bridge.py`), and a second run that
overlaps can fail at the link step with "Permission denied" (seen on
2026-11-11 with `test_pops_external.py`; a harness collision, not a test
failure).

Result on 2026-11-11, code at `cfebe01`: all 26 files exited 0 in both
passes. With the reference inputs three files still skipped three tests
each: `test_pops_launch_hooks.py` (needs `POPS_RESIDENT_BIN` and
`POPS_TRAMPOLINE_BIN`, the built EE images), `test_pops_progressive.py`
(needs an EE compiler on `PATH` or `POPS_EE_CC`) and
`test_pops_external.py` (it includes the progressive suite). So the
comparisons against built EE images did not run in those passes.

After the first correction pass of the same day (documents, the new
`tools/test_pops_doc_claims.py` and its workflow step; no C source
changed) the list was run again, on the uncommitted tree before its
commits: 27 files. In the second pass 26 exited 0 and
`test_pops_external.py` exited 1 at the link step (the two passes had been
run at the same time, the collision described above); run again alone it
exited 0. The same three files skipped three tests each in the second
pass. The independent review then ran the 27 files one after another at the
committed head `ed30f55`: all exited 0 in both passes. (An earlier version
of this paragraph said all 27 exited 0 in both passes of the correction
pass itself; that described the end state, not what was run.)

At `ef663b2` the handoff records its own runs of the 32 files on the merged
tree ([PR23_HANDOFF_2026-11-11.md](PR23_HANDOFF_2026-11-11.md), section 6).
The second correction pass of the gap audit ran them again on its branch
`pr23/docs-2`, one file at a time, temp folders isolated; the result is in
the audit's section 19.
Those three files were then run once more with the reference inputs plus
`POPS_EE_CC` set to ps2build's EE GCC 15.3.1 and `POPS_RESIDENT_BIN` /
`POPS_TRAMPOLINE_BIN` pointing at images made by hand with that compiler
(the resident image by the recipe below; the trampoline `.text` from
`launcher/src/pops_trampoline.S` with `gcc -c -G0 -Icommon/include
-Ilauncher/include` and `objcopy -O binary -j .text`, 260 bytes):
`test_pops_launch_hooks.py` 46 tests, none skipped;
`test_pops_progressive.py` and `test_pops_external.py` one skip each, the
built progressive bridge, because that test looks for
`mips64r5900el-ps2-elf-objcopy` without the `.exe` suffix the Windows
toolchain has. These images are not CMake's and the compiler is not CI's.
All of it is host work. NOT TESTED on a console.

Resident image without a full build (compiled this way on 2026-11-11 with
ps2build's EE GCC 15.3.1, by the first pass, the review and the correction
pass; 6,688-byte image each time; the checker passed its 12 sections):

```sh
TC=/c/Users/natha/AppData/Local/ps2build/toolchain/ee/bin; OUT=<a scratch directory>
$TC/mips64r5900el-ps2-elf-gcc.exe -Os -G0 -fno-pic -mno-abicalls \
  -ffreestanding -fno-builtin -nostdlib -nostartfiles -Wall -Wextra -Werror \
  -DPOPS_RESIDENT_IMAGE -Icommon/include -Wl,-T,common/src/pops_resident.ld \
  -Wl,--build-id=none -o $OUT/pops_resident.elf \
  common/src/pops_resident_engine.c common/src/pops_progressive.c \
  common/src/pops_progressive_bridge.S common/src/pops_resident_guards.S \
  common/src/pops_resident_recompiler.S
$TC/mips64r5900el-ps2-elf-objcopy.exe -O binary $OUT/pops_resident.elf $OUT/pops_resident.bin
python tools/check_pops_resident_image.py $OUT/pops_resident.bin
```

That compiler is not CI's, so the bytes may differ from a CI build even
when the checker passes. The checker is a manual script, not a CI step.

Full target build. ps2build cannot build the CMake project as written (the
project expects the PS2SDK layout). The container route below was not run
by the first correction pass. The handoff reports a container build of
`f22a69f` that built, `release/launcHER.elf` 326,772 bytes
([PR23_HANDOFF_2026-11-11.md](PR23_HANDOFF_2026-11-11.md), section 6).
The second correction pass ran it in a git worktree of its branch (C code
as at `ef663b2`). The first try stopped at 28% of the build, at
`mmceman.irx`, because a new worktree has no checkout of the
`launcher/iop/mmceman` submodule. After `git submodule update --init
launcher/iop/mmceman` it built: `release/launcHER.elf` 326,772 bytes, with
CMake's warning "No Git revision available: writing version=unknown". In a
worktree the `git config --global` step has to run from `/` (`cd / && git
config ...`): inside `/workspace` git stops with "not a git repository",
because the worktree's `.git` file names a Windows path, and for the same
reason the build cannot read its revision. The route, needing Docker
Desktop:

```sh
docker run --rm -v C:/Users/natha/Github/launcHER:/workspace -w /workspace \
  ghcr.io/ps2homebrew/ps2homebrew:main sh -c "apk add cmake && \
  git config --global --add safe.directory /workspace && \
  cmake -B build-pr23 && cmake --build build-pr23 --target launcHER"
```

The boot-trace build adds `-DLAUNCHER_BOOT_TRACE=ON -DDEBUG=ON`. Use new
build directory names; the existing `build*/` folders are evidence from
earlier runs. If no local target build is made, rely on the PR's GitHub
Actions build jobs and say so; do not claim a local build. The
`mcman-2000.irx` note in the 2026-10-31 section below describes a cloud SDK
and does not apply to this machine.

### Three test tiers, and what each can show

1. **Host tests** (`tools/test_*.py`). They show that launcHER's C code
   writes the same bytes as a block of the original run under emulation
   with its library calls modelled. They cannot show that a PS2 boots,
   draws, reads a disc or saves.
2. **Whole-machine emulator** (`C:/Users/natha/Github/RIPPCSX2`). An
   install exists there. It was not used on 2026-11-11 and no launcHER run
   recipe for it is recorded in this repository yet; the first person to
   use it should write one down here. An emulator result is not a console
   result and must not be reported as one.
3. **Console rig** (ps2rig, the owner's hardware). A real POPS launch
   strands the rig: Sony's IOP reset removes ps2link, so the rig reports
   `hang` and the console needs a physical reset. A `hang` after that
   reset is neither a pass nor a fail (see
   [POPSTARTER_HANDOFF.md](POPSTARTER_HANDOFF.md)). Run on the rig only
   when the owner asks for a specific test.

Every claim in a PR or document says which tier it comes from. "NOT TESTED
on a console" stays on a row until tier 3 evidence exists.

### Next work, ranked

From section 16 of the gap audit; details, dependencies, effort and the
state at `ef663b2` are there. For the order the lead set after `ef663b2`
see [PR23_HANDOFF_2026-11-11.md](PR23_HANDOFF_2026-11-11.md), section 7.

1. Fix files the original would skip must not end the launch; then TROJAN
   parity. The corpus result it rests on has been re-run (gap audit, S27).
   In progress on a side branch at `ef663b2`.
2. One path table measured from the original for every per-folder file,
   and a written decision on how each original folder maps to launcHER's
   (HDD `hdd0:__common` included). No behaviour change.
3. IGR skin staging. Landed in `173d5de` (reads the `.VCD`'s folder; no
   POPS folder exit).
4. The loader flags and the passes they gate, then `BIOS.BIN`. Landed in
   `0945127` for `BIOS.BIN` (no POPS folder exit; OSD flags never set).
5. Fix files before commands: measure both orders, then decide.
6. `OSD.BIN`: implemented `pops_osd_plan` / `pops_osd_stage`, the exact
   reader and per-scope launch look-ahead; 30 tests with references and 30
   without (15 skips), including 256 whole-core seeded differentials and
   both backend request models. Remaining differences are quirks 80 to 84.
   Host/Unicorn only, not a console run.
7. `$USBDELAY` parser and default, the preset table, command recognition
   context, `VMCDIR.TXT` rules. Parser, recognition and `VMCDIR.TXT` landed
   in `95ba812`; the default and the preset table are open; the review
   answers are in progress on a side branch.
8. The `$USBDELAY` delay itself in popfs (needs tier 2 or 3 to call
   working).
9. Launch-argument rules, resolver candidates, the `IOPRP.IMG` fallback,
   removing the test folder from the package search list.
10. SMB config parsers. Landed in `21c3476` for `SB.` launches of PS1
    games; not reviewed.
11. Physical disc fallback. Host part landed in `f22a69f`, not called by
    the launch; not reviewed.
12. HDD `__common` layout; SMB external modules and connect order (tier 3).
13. REPOP documentation follow-up, as a separate REPOP pull request.

Owner decisions that block or shape the above are named in the gap audit
(sections 7, 8, 9, 10 and 14): the default IGR, how a physical-disc
launch is requested, whether to copy the CPU-speed USB wait, which
launcHER-only commands and files stay, and the HDD folder mapping.

## History

Everything from here on is an older checkpoint, kept unchanged apart from
the corrections noted inline. Counts, heads and "current" statements below
describe the date in each heading, not today.

## Historical: R27 continuation, 2026-10-31

- **Text `$480p` is now selected through the guarded owned resident bridge.**
  [Progressive contracts](POPS_PROGRESSIVE_CONTRACTS.md) and metadata record
  428 original/native ordered-write cases, 428 compiled EE final-memory cases,
  428 built context-bridge cases, and 31 original text/file sequences. The
  image is v3, 32-byte header, 3,936 resident bytes. Context checks model
  EE-only quad/secondary accumulator transfers explicitly; no full hardware
  or independent full EE/MMI execution is claimed.
- Progressive intent is sticky across NOPAL/FORCEPAL. The production fix
  session retains disable-PAL state, then region processing finishes before
  guarded static setup. Manual all-six file priority and HDTVFIX/NOHDTVFIX
  order match original sequences. All five static sites are checked before
  any hook write. Conflicting payload changes reject and discard that launch.
- PATCH actions 6/7 dispatch to the owned progressive bridge since `a8da126`
  (see the R28 checkpoint below); without a bound entry they still reject.
- Manual `$DX/$DY/$MAGH/$MAGV/$DW/$DH`: 228 original file cases, 18 option-order
  sequences, first valid 0..99999 in each file, all six required per file.
  Six direct display commands retain 1,596 original inputs plus two one-shot
  states. Ordered PAL/region retains 60 original combinations. Read the linked
  contracts; these are component proofs, not gameplay or picture acceptance.
- Current validation: **121 aggregate external tests**, default 12 optional
  skips; **23 host entry points**; normal and trace/debug target builds.
  Existing VBLANK/manual image checks and the built progressive bridge pass.
  No new console run occurred. Latest published bridge checkpoint `9bf4fc6`
  has green build/host/argv CI; check current-head CI after publishing R27.
- Catch-up base merge `b34affc` includes EMBER through `f0e5948` (CUE argument
  coverage/docs and credit links). Older uncommitted video work remains in
  its preserved stash. Current REPOP checkout is separate from the older
  dirty checkout; do not overwrite either.
- REPOP source recovery remains `15b8727f` (R22): 169 original-vs-compiled-EE
  CD component cases, 243 tests / 13 skips, all 11 EE units compile. Lower
  memcpy/kernel/SIF/cache hardware, callback relocation/global ownership and
  full runtime remain open. R23–R26 docs through `727460f2` synchronize manual
  and progressive recovery. Update that handoff after this R27 increment.
  No baseline promotion; existing `FUN_0091a604` bounds warning remains open.
- The user explicitly requested sustained work until **100% verified parity**.
  This goal remains incomplete. Keep publishing validated increments and both
  handoffs. Remaining pad/cheat forms, built-in per-game data, BIOS/OSD/IGR skin,
  modules, physical disc, transports/game/controller/CDDA and fresh-VMC save /
  reload / cold-power-cycle evidence are separate acceptance gates.

## Historical (2026-10-31): reproduction and preserved local work

The paths in this section describe a cloud session's temporary files. For
this machine use the recipe in the 2026-11-11 section above.

```sh
POPS_TEST_ELF=/external/POPS.ELF \
POPSTARTER_TEST_ELF=/external/MAIN/POPSTARTER.ELF \
python3 tools/test_pops_external.py
python3 tools/test_pops_resident.py
python3 tools/test_launch_args.py
```

The local PS2SDK v2.0.0 lacked mcman-2000.irx. The successful target builds use
`/tmp/pr23-sdk-overlay` with that module compiled from official PS2SDK
`2a18d15da1332665451a9bcf9a0d4df9029c9490`, leaving the installed SDK unchanged.
The base toolchain is under `../POPSLoader/artifacts/local/ps2dev`; CMake and
Unicorn are in `/tmp/launcher-parity-venv`. These temporary paths are local
conveniences, not cloud prerequisites. Use the normal repository CI/current
PS2SDK for reproducible targets. Existing transport/path-format warnings remain;
there are no new warnings in the changed common display/configuration code.

The older uncommitted PATCH-video experiment is preserved in local stash
`preserved pre-sync PATCH video WIP 2026-10-30`; it permits the absent-resident
jump and must not be applied wholesale. `../REPOP/checkout` is an older dirty
`feat/popstarter-iop-recovery` checkout and was preserved. The current clean
REPOP continuation was cloned separately to `/tmp/repop-pr23-continuation` and
pushed; use its branch, not the older checkout. Original Sony/game/save bytes
stay external. No merge or release was performed.

## Historical (2026-10-31 to 2026-11-02): next work and physical gates

Superseded by "Next work, ranked" above. The physical gates listed here
(items 1 and 4) are still open.

1. Validate the resident cheat hook with a known code and safe-mode case;
   compare US/European video, FORCEPAL, NOPAL and PATCH PAL/disable-auto on
   hardware. Host/emulated checks do not establish picture or gameplay results.
2. Extend independently implemented resident services for progressive output,
   pads, timings, widescreen and the remaining cheat commands. The
   `$RECOMPILER_ADDON_0..4` commands now run from launcHER's own resident
   recompiler hook (2026-11-02; see `docs/POPSTARTER_LAUNCH_HOOKS.md`), and
   `$FAKELC` is copied, with the built-in list entries it cuts (2026-11-02;
   see `docs/POPSTARTER_BUILTIN_DB.md`), and the always-live block's
   `$NOVMC0/1` per-pass stores (2026-11-02; `$NOVMC0` no longer turns off
   both cards; `check_pops_resident_image.py` checks the two stores).
   Paused there on 2026-11-02 to save tokens; next is a hardware check
   that a `$NOVMC0` game finds no card in slot 1 and still saves to slot 2.
3. Recover the built-in per-game DB and remaining BIOS/OSD/IGR-skin/module and
   physical-disc behavior from original contracts. Do not infer completion
   from annotation coverage or an archive build.
4. Prove in-game save/reload/cold-power-cycle persistence on a fresh dedicated
   VMC, preserving existing cards. Device/network runtime, CDDA, controllers,
   representative games and Ember forwarding remain separate acceptance gates.
5. Keep this draft PR and REPOP evidence synchronized after each verified
   increment; fetch before publishing to preserve concurrent continuation.

## Historical October 28 audit

[The verified October 28 audit](POPS_PARITY_AUDIT_2026-10-28.md) supersedes earlier contradictory claims. Full POPStarter drop-in parity is incomplete. The old accumulated diary is preserved as [unverified history](history/CLOUD_CONTINUATION_2026-10-28_UNVERIFIED.md); its claims of complete resident engines, save durability and repeated exact size parity are withdrawn.

## Recovered cutoff

Antigravity conversation `12f3836d-b37b-4e06-8305-b8eb38960027` stopped while verifying earlier Gemini claims. The last user request was to push relevant work and post a verified done/left summary on this PR. Earlier instructions retain the broad objective of full POPStarter capability parity and cloud continuation in both launcHER and REPOP.

Recovered remote heads: launcHER `8c27b0c72091708103f820c2edda97ba764b3b90`; REPOP `feat/psxcore-validation` at `c440417d4780467abd75a13985837d022db6e9eb`. Recheck live heads. REPOP's current continuation is a separate checkout from the older `POPS` checkout. Read its [current handoff](https://github.com/NathanNeurotic/REPOP/blob/main/docs/POPSTARTER_CONTINUATION.md) (link changed on 2026-11-11 from `feat/psxcore-validation`, which was merged into `main` and is superseded; the heads named in this paragraph are the ones recovered on 2026-10-28).

## Verified acceptance limits

- Dependency and preflight screenshots were re-inspected and their recorded SHA-256 values reproduced. The latter explicitly says `Sony_entry_not_executed=1`.
- For Tekken run `20261028T012047-0126`, the user confirmed “It worked!” after a specific gameplay-controls/IGR/browser-return test request. Retain that limited user-observed result. It does not establish a measured frame rate, CDDA quality, latency or broad compatibility.
- VMC runs `20261028T063429-0127` and `20261028T063634-0128` contain no save/reload, card digest, cold-power-cycle or disc-change evidence. Their durability/multi-disc completion claim is withdrawn. A rig `hang` after Sony reset is neither independent failure proof nor success proof.
- Cheat evaluation, disc swapping and SubQ EE helpers have host tests, but no production caller installs/invokes them during Sony execution. Their presence does not establish resident runtime support. Current cheat-file acceptance can therefore be silent even though its parser succeeds.
- All 23 launcHER host entry points pass. Recovered-head GitHub normal/diagnostic builds, packaging and argument checks passed. Check later-head CI separately. No new hardware run occurred during this audit.
- REPOP's later size snapshot was manually assigned expected values and is invalidated. Its interrupted EE build fails with 59 errors; committed checkpoint syntax checks reproduce 50 errors across two reconstruction files. Passing Python tests do not compile those files. The exact unfinished Batch 15 diff is preserved as a recovery patch in REPOP, rather than silently discarded or promoted as implemented code.

## Historical: next implementation steps (2026-10-28 to 2026-10-31)

## Historical: R28 PATCH progressive dispatch checkpoint (2026-10-31)

PATCH action 6 is now implemented as a guarded, resident-bound progressive
dispatch: it preserves the original custom-video gate, writes the owned jump
and `li a0, 0` arguments only when that gate permits it, and refuses payload
ordering or later-drift cases that would invalidate the bridge. The original
bounded interpreter covers 128 control/flag states; host differential coverage
also exercises 100 ordered PATCH-action sequences. Both normal and trace PS2
builds succeeded and the external aggregate suite passed with the supplied
Sony and MAIN POPSTARTER inputs. This is not hardware/video validation and
does not establish full PATCH/TROJAN or POPStarter parity.

The next agent should begin from this committed checkpoint, re-run the external
suite, inspect current PR CI, then pursue the remaining physical and resident
runtime gates below. Do not claim 100% completion.

**Latest redo checkpoint:** REPOP's two FP helper candidates now compile in isolation for EE and pass four focused host tests. Final REPOP suite: 225 tests, ten skipped, zero failures/errors. The original-code differential run remains incomplete after a Unicorn exception beyond the 6,144-pattern progress marker; no semantic-parity pass is claimed. Start with [the exact FP handoff](https://github.com/NathanNeurotic/REPOP/blob/main/docs/POPSTARTER_FP_CONTRACTS.md) (link changed on 2026-11-11 to `main`), diagnose the failing original input/PC, then resume the build/signature repair below. The entire reconstruction still has build blockers.

1. Repair REPOP's EE build using original function/callsite contracts; audit existing candidates before adding batches. Replace constant-input demonstrations and invented state. Measure fresh artifacts and compare original/reconstruction behavior; source annotations and similar code size do not establish semantic parity.
2. Prove guest RAM mapping, resident code/data lifetime across handoff, hook guards and call order before wiring cheats, safe mode, disc change or Sony-consumed LibCrypt replies. Avoid guessed memory addresses or hooks.
3. Run a specifically authorized in-game save/reload/cold-power-cycle test on a **new dedicated VMC**, with content/integrity evidence. Preserve existing cards, installed games, external Sony files and firmware.
4. Complete original PATCH/TROJAN gating and config precedence; compare original-supported USB/APA/SMB behavior. Verify fresh-stack network streaming/failure/restart, CDDA/video/controllers, representative games and Ember forwarding separately.
5. Keep this PR and REPOP's handoff current after each verified increment. No paid services, unrequested workflow enabling, automatic merge or proprietary binary distribution.

Related sources: [original-behavior matrix](POPSTARTER_ORIGINAL_BEHAVIOR_MATRIX.md), [IOP/EE I/O contract](POPS_IO_CONTRACT.md), [runtime implementation diary](POPSTARTER_REPLACEMENT.md), [hardware handoff](POPSTARTER_HANDOFF.md), [network handoff](NETWORK_TRANSPORT_HANDOFF.md).
