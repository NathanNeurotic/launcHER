# POPStarter capability audit and recovered continuation — 2026-10-28

Full POPStarter drop-in parity is incomplete. Continue [draft PR #23](https://github.com/NathanNeurotic/launcHER/pull/23) on `codex/popstarter-replacement`; keep it draft and unmerged. This audit supersedes conflicting completion claims in earlier continuation notes and evidence metadata.

## Recovered workthread

Antigravity conversation `12f3836d-b37b-4e06-8305-b8eb38960027` stopped during an audit of earlier Gemini reports. Its last user request was to push all relevant work, post what is done and left on this PR, and verify claims. The broad objective remains an independent POPStarter replacement, with REPOP research available for a future cloud agent.

At recovery, launcHER local and remote head were `8c27b0c72091708103f820c2edda97ba764b3b90`. The actual REPOP continuation checkout was branch `feat/psxcore-validation`, local and remote `c440417d4780467abd75a13985837d022db6e9eb`; the separate older `POPS` checkout was not its current source.

## Evidence reviewed

| Area | What is established | What is not established |
| --- | --- | --- |
| Dependency reads | User screenshot SHA-256 `de2c646e71006c08f93173e1213ab2e09191c44bb762c162abee2084dbd31cb9` visibly shows complete ELF/IOPRP reads, `close_result=2`, and `POPS_DEPENDENCIES_PASS`. The screenshot was re-inspected and its hash recomputed. | No game, save or resident feature acceptance follows from this diagnostic stop. |
| Preflight | Screenshot SHA-256 `ea81249c55436db43f68e43aaea6965e5226d59cdc54473d33a1fbe1be2f7e4a` visibly shows post-reset drivers and `POPS_PREFLIGHT_PASS Sony_entry_not_executed=1`. The screenshot was re-inspected and its hash recomputed. | The explicit marker says Sony entry was not executed. It does not prove gameplay. |
| Tekken controls and IGR | Run `20261028T012047-0126`, ELF SHA-256 `b1227bb14d645237ceeca330d3c45864e3c3aa37731a816f0433b3b0ab04155d`. Recovered user response at `2026-10-28T02:28:13Z`: “It worked!”, following a request to test gameplay controls, trigger IGR and check clean return to the browser. | No instrumented 60 fps measurement, audio/CDDA quality or latency measurement; no general device/game compatibility claim. The rig's `hang` status is not an independent pass marker. |
| Save durability | Existing production VMC host contracts pass; isolated earlier I/O probes have their own documented limits. | Runs 127 and 128 do not establish an in-game save, reload, card identity/content checks or a cold power cycle. The previous P0 durability/multi-disc completion claim is withdrawn. |
| Cheats, safe mode and disc swapping | Parsers and standalone helpers exist and pass their current host tests. | No production caller installs/evaluates the cheat tick or invokes the disc-swap helper during Sony execution. Helpers alone are not a resident engine. |
| LibCrypt/SubQ | An EE helper and IOP devctl support exist; synthetic payload/CRC tests pass. | No production caller of `pops_cdrom_read_subq` and no observed Sony request/response integration proving protected-game behavior. |
| REPOP decompilation | The eligible original EE denominator is 477 functions / 139,144 bytes. Research source and original-call evidence remain available. | “445 reconstructed / 93.3%” and repeated “1.00x size parity” are not verified progress. The interrupted source fails EE compilation and its size snapshot was manually assigned expected values. |

The timing above uses UTC to match the preserved run records; the user confirmation was October 27 at 7:28 pm America/Los_Angeles. Screenshots remain user/local evidence; no unrelated desktop images or proprietary binaries are added to the repository.

## Corrections to previous reports

The two VMC runs were retrieved from ps2rig again:

- `20261028T063429-0127`: `hang`, 120-second observation, ELF SHA-256 `e5477ea222797e26989df26b11d5a300d26db44124aed2ee6ab6cba9ce2be016`, stdout limited to loading banners and `ata0:/POPS/Tekken.VCD`.
- `20261028T063634-0128`: `hang`, 30-second observation, same ELF, no stdout.

Neither record contains save or swap results. Sony reset may remove ps2link, so absence of output does not prove game failure; it also cannot be promoted to success. [Corrected save evidence](evidence/pops_vmc_save_persistence_hardware.json) retains the run identities and explicitly leaves the gates open.

The earlier `007 - Tomorrow Never Dies` run 115 likewise has only loader/path stdout. Its report no longer calls a successful end-to-end gameplay/save gate. The later Tekken user confirmation is recorded separately in [its limited observation report](evidence/pops_tekken_user_confirmation.json).

Recovered REPOP scripts write hard-coded expected symbol sizes into `ee_sizes.json`, without obtaining them from a compiled artifact. A new native ps2build `v2026.10.15` GCC build of the interrupted working tree fails with **59 compiler errors and five warnings**. Separate syntax checks of the two committed `c440417d` translation units reproduce **50 errors** (four in `patch_engine.c`, 46 in `runtime_hooks.c`). Header/definition conflicts, inconsistent local extern declarations and incomplete types are application-source defects. These results do not identify an SDK fault.

The unfinished REPOP Batch 15 edits were preserved verbatim in `docs/recovery/ANTIGRAVITY_BATCH15_2026-10-28.patch`, SHA-256 `c0961f234face0fc4d8865ed929e5e91b878b0dd51b31529aac31ebb782e81f0`, before returning the active source to its committed checkpoint. No unfinished edit was discarded. The snapshot is invalidated and the report rejects invalidated data even when symbol values remain. Read the [REPOP continuation](https://github.com/NathanNeurotic/REPOP/blob/feat/psxcore-validation/docs/POPSTARTER_CONTINUATION.md) and its structured diagnostics before resuming reconstruction.

## Reproduced validation

- All **15 launcHER `tools/test_*.py` entry points pass** on the recovered source. External suite: 85 tests, one skipped without explicit external inputs. Standalone fix-file suite: 18 tests, one skipped. Feature helpers: 21 tests. Some entry points invoke other suites; these counts must not be added as distinct acceptance cases.
- An initial sandbox run encountered Windows temporary-directory access errors. Running the same suites outside that sandbox succeeded; this was a host-environment limitation, not a source failure or an SDK defect.
- At the recovered PR head `8c27b0c`, GitHub checks confirm normal build, diagnostic build, host tests, arguments and packaging passed. Release and CodeRabbit review were skipped. Check any later head separately.
- REPOP's original Python suite reports **220 tests, ten skipped, zero failures/errors**: 210 executed. It does not compile the two failing reconstruction files. The snapshot invalidation regression adds one test to the historical total. No new REPOP EE build success or functional-equivalence claim is made.
- This audit reads existing console records and screenshots. It performs no new console run, save write or power cycle.

## Work still required

### First redo checkpoint

REPOP now replaces two constant-input FP demonstrations with original-instruction-derived candidates (`FUN_0091ea70`, `FUN_0091eca0`), isolated in a separately buildable source file. Their EE archive builds and four focused host tests pass. Actual measured symbol sizes are 168 and 236 bytes. The full final REPOP Python suite reports **225 tests, ten skipped, zero failures/errors** (215 executed).

The original-code differential run is **incomplete**: fresh Unicorn CPUs progressed beyond the 6,144-pattern marker, then raised an unhandled CPU exception. It is not a parity pass. The next agent must identify the exact failing input/PC and distinguish harness/CPU-model behavior from candidate defects. Whole-reconstruction build blockers remain. See [the FP contract handoff](https://github.com/NathanNeurotic/REPOP/blob/feat/psxcore-validation/docs/POPSTARTER_FP_CONTRACTS.md). No new console test or parity-baseline promotion occurred.

1. Restore a real REPOP EE build from original function/callsite contracts; audit existing candidates before adding another batch. Reconstruct real inputs, state and side effects instead of constant-input examples and invented globals. Measure fresh artifacts, then use original-vs-reconstruction differential probes. Keep claims, build measurements and semantic verification separate.
2. Establish a resident execution contract before claiming cheats, safe-mode timing, in-game disc swapping or Sony-consumed LibCrypt responses. Prove guest RAM mapping and resident code/data lifetime, guarded hooks and original call order. `ExecPS2` handoff makes a normal launcher helper's existence insufficient.
3. Use a **new dedicated VMC** for a real in-game save/reload/cold-power-cycle test with content hashes and integrity checks. Preserve existing cards and installed games. Formatting a 128 KiB container is not save persistence.
4. Verify original PATCH/TROJAN state/precedence and video actions, original-supported USB/APA/SMB behavior, loss/restart handling, CDDA/video/controllers, representative games and Ember forwarding. Extensions and inherited-stack network probes remain separate from original runtime parity.
5. Keep this PR and REPOP's continuation evidence synchronized. Publish validated incremental work with `Co-authored-by: ChatGPT <chatgpt@openai.com>`. No automatic merge, proprietary Sony/game/save files, paid services or workflow enabling.
