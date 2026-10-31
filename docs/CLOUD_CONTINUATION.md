# Continuation checkpoint — 2026-10-30

Continue [draft launcHER PR #23](https://github.com/NathanNeurotic/launcHER/pull/23) on `codex/popstarter-replacement`. Fetch before editing, preserve newer work, publish validated incremental commits on this same PR, and include `Co-authored-by: ChatGPT <chatgpt@openai.com>`. Keep the PR draft and unmerged.

## Current continuation (supersedes historical build/oracle blockers below)

- Synced the checkout from `33c33fc` to current PR head `ae86f3d` before editing.
- Preserved the three older uncommitted PATCH-video files in the local stash
  `preserved pre-sync PATCH video WIP 2026-10-30`. This old experiment allows
  the absent-resident action 6 jump and must not be reapplied wholesale.
- PATCH video actions 6/7 now return `-ENOTSUP` before any payload, mode or
  context mutation. The jump targets `0x2394f0`, inside POPStarter's copied
  resident block, which launcHER does not supply. The previous success tests
  only demonstrated writing that jump, not a working video mode.
- `POPS_TEST_ELF=EXTERNAL/POPS.ELF python3 tools/test_pops_fix_files.py`:
  18 tests pass including the identified external-core case.
- Fresh REPOP `feat/psxcore-validation` head is `ee87b55e`. Its newer divergence
  register R13–R18 supersedes the old incomplete-FP and build-failure notes
  below: the remote records a completed FP differential and repaired EE archive.
  Those newer results have not been independently rerun in this continuation.
  Remaining original-contract work includes `FUN_00917f80`,
  `FUN_0091acb0`, `FUN_009a1458`, and the lower SIF transport implementation.
  Use a separate current checkout; `../REPOP/checkout` is an older dirty
  branch (`feat/popstarter-iop-recovery`) and was preserved.
- No new console run. The ae86f3d region changes still need US/European disc,
  `$FORCEPAL` and `$NOPAL` hardware checks. Runtime, dedicated-new-card
  save/reload/cold-power-cycle and device acceptance remain open.

Next source slice: recover the computed video commands from the hash-pinned
original, compare original execution against production staging, and retain
explicit resident dependencies. Do not infer behavioral completion from source
coverage or an archive build. Keep incremental commits and PR comments current.

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
