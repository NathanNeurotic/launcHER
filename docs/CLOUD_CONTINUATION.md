# Continuation checkpoint — 2026-10-30

Continue [draft launcHER PR #23](https://github.com/NathanNeurotic/launcHER/pull/23) on `codex/popstarter-replacement`. Fetch before editing, preserve newer work, publish validated incremental commits on this same PR, and include `Co-authored-by: ChatGPT <chatgpt@openai.com>`. Keep the PR draft and unmerged.

## Current continuation (supersedes historical build/oracle blockers below)

This continuation published `5dc8076` (PATCH 6/7 guard), `4ac9d30` (six direct
display commands), and the current PATCH-state/region-ordering change. The
concurrent `8f40793` resident-engine commit was fetched and integrated before
that last change. Continue from current HEAD, fetching again before editing.

- PATCH 6/7 still reject before any payload/mode/context writes. The resident
  cheat image at `0x0143a000` does not supply their `0x2394f0` video target.
- `$SMOOTH`, `$LEFTADJ_`, `$XPOS_`, `$YPOS_`, `$DWSTRETCH_`, `$DWCROP_` have
  guarded production staging. [Display contracts](POPS_DISPLAY_CONTRACTS.md)
  record the exact values, original windows, hashes and 1,596 original-command
  input comparisons plus two first-position-state checks.
- PATCH sessions now guard all four PAL sites across ordered payloads. Text
  `$480p` state suppresses explicit PATCH PAL; `$NOPAL` still permits explicit
  PATCH PAL. FORCEPAL now waits until after fix files, so PATCH PAL/disable-auto
  suppresses its final branch as in the original. Intentional payload changes
  are tracked through final video. [State contracts](POPS_PATCH_VIDEO_STATE.md)
  document the 60-combination original region-control-flow comparison.
- The integrated external test entry point passes **104 tests**, with both
  external inputs. All **18 host entry points** (including argv and resident)
  pass. Normal and `LAUNCHER_BOOT_TRACE=ON,DEBUG=ON` PS2 builds pass. The built
  2,672-byte resident image passes its Unicorn entry/chaining check. These are
  host/target-build/emulated results; no new physical console run occurred.
- REPOP `feat/psxcore-validation` is now **`8d2714d5`**. R20 replaces the
  zero CDVD gate, invented semaphore/pending state, and eight return-zero
  kernel wrappers. **49 original-vs-compiled-EE component cases pass** with
  modeled kernel/SIF callees and final RAM auditing. Full Python suite:
  **237 tests, 13 skipped, zero failures/errors**. All 11 EE units compile
  with existing warnings. The full-archive query is now 124 bytes and the gate
  428 bytes; the old eight-byte-query blocker is superseded. Read REPOP's
  `POPSTARTER_CD_GATE_CONTRACT.md` and R20 before making runtime claims.
  Original-uninitialized semaphore fields are zeroed and excluded from strict
  byte equivalence. Lower SIF/init behavior, global-state ownership, complete
  runtime link and physical acceptance remain open; no baseline was promoted.
  The independent FP run remains **16,393 patterns / 32,786 calls pass**.
  **Next work:** the original four-argument `FUN_00917f80` mode/packet/cache
  contract, then lower SIF/init dependencies and launcHER resident features.
  Existing `FUN_0091a604` bounds warning is still open.
- The user explicitly requested sustained work until 100% verified parity.
  The thread goal is active. Continue making validated increments; do not
  treat a checkpoint or green CI as completion of the full objective.

## Reproduction and preserved local work

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

## Next work and physical gates

1. Validate the resident cheat hook with a known code and safe-mode case;
   compare US/European video, FORCEPAL, NOPAL and PATCH PAL/disable-auto on
   hardware. Host/emulated checks do not establish picture or gameplay results.
2. Extend independently implemented resident services for progressive output,
   pads, timings, widescreen and the remaining cheat commands. The three
   `$RECOMPILER_ADDON_0/1/2` helpers also copy original code into `0x143xxxx`
   (helpers at `0x8d6f64/0x8d6fa4/0x8d6fe4`); they are not direct fixed patches.
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

Recovered remote heads: launcHER `8c27b0c72091708103f820c2edda97ba764b3b90`; REPOP `feat/psxcore-validation` at `c440417d4780467abd75a13985837d022db6e9eb`. Recheck live heads. REPOP's current continuation is a separate checkout from the older `POPS` checkout. Read its [current handoff](https://github.com/NathanNeurotic/REPOP/blob/feat/psxcore-validation/docs/POPSTARTER_CONTINUATION.md).

## Verified acceptance limits

- Dependency and preflight screenshots were re-inspected and their recorded SHA-256 values reproduced. The latter explicitly says `Sony_entry_not_executed=1`.
- For Tekken run `20261028T012047-0126`, the user confirmed “It worked!” after a specific gameplay-controls/IGR/browser-return test request. Retain that limited user-observed result. It does not establish a measured frame rate, CDDA quality, latency or broad compatibility.
- VMC runs `20261028T063429-0127` and `20261028T063634-0128` contain no save/reload, card digest, cold-power-cycle or disc-change evidence. Their durability/multi-disc completion claim is withdrawn. A rig `hang` after Sony reset is neither independent failure proof nor success proof.
- Cheat evaluation, disc swapping and SubQ EE helpers have host tests, but no production caller installs/invokes them during Sony execution. Their presence does not establish resident runtime support. Current cheat-file acceptance can therefore be silent even though its parser succeeds.
- All 15 launcHER host entry points pass. Recovered-head GitHub normal/diagnostic builds, packaging and argument checks passed. Check later-head CI separately. No new hardware run occurred during this audit.
- REPOP's later size snapshot was manually assigned expected values and is invalidated. Its interrupted EE build fails with 59 errors; committed checkpoint syntax checks reproduce 50 errors across two reconstruction files. Passing Python tests do not compile those files. The exact unfinished Batch 15 diff is preserved as a recovery patch in REPOP, rather than silently discarded or promoted as implemented code.

## Next implementation steps

**Latest redo checkpoint:** REPOP's two FP helper candidates now compile in isolation for EE and pass four focused host tests. Final REPOP suite: 225 tests, ten skipped, zero failures/errors. The original-code differential run remains incomplete after a Unicorn exception beyond the 6,144-pattern progress marker; no semantic-parity pass is claimed. Start with [the exact FP handoff](https://github.com/NathanNeurotic/REPOP/blob/feat/psxcore-validation/docs/POPSTARTER_FP_CONTRACTS.md), diagnose the failing original input/PC, then resume the build/signature repair below. The entire reconstruction still has build blockers.

1. Repair REPOP's EE build using original function/callsite contracts; audit existing candidates before adding batches. Replace constant-input demonstrations and invented state. Measure fresh artifacts and compare original/reconstruction behavior; source annotations and similar code size do not establish semantic parity.
2. Prove guest RAM mapping, resident code/data lifetime across handoff, hook guards and call order before wiring cheats, safe mode, disc change or Sony-consumed LibCrypt replies. Avoid guessed memory addresses or hooks.
3. Run a specifically authorized in-game save/reload/cold-power-cycle test on a **new dedicated VMC**, with content/integrity evidence. Preserve existing cards, installed games, external Sony files and firmware.
4. Complete original PATCH/TROJAN gating and config precedence; compare original-supported USB/APA/SMB behavior. Verify fresh-stack network streaming/failure/restart, CDDA/video/controllers, representative games and Ember forwarding separately.
5. Keep this PR and REPOP's handoff current after each verified increment. No paid services, unrequested workflow enabling, automatic merge or proprietary binary distribution.

Related sources: [original-behavior matrix](POPSTARTER_ORIGINAL_BEHAVIOR_MATRIX.md), [IOP/EE I/O contract](POPS_IO_CONTRACT.md), [runtime implementation diary](POPSTARTER_REPLACEMENT.md), [hardware handoff](POPSTARTER_HANDOFF.md), [network handoff](NETWORK_TRANSPORT_HANDOFF.md).
