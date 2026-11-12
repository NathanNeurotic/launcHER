# Review 2: SMB rule switch fix (findings 1 and 2), pr23/smb-2

Target: `origin/pr23/integ...origin/pr23/smb-2`. integ is `4e90fda`; smb-2 is `b654ae6`, with commits `4f497eb` (code and tests) and `b654ae6` (doc only).
Files: common.c (+8/-2), handler_smb.c (+13/-5), init.c (+2), handler_smb.h, init.h, tools/test_pops_smb_config.py (+287/-16), docs/POPSTARTER_SMB_CONFIG.md.
`<s>` = <scratch>. Reviewer files are under `<s>/review2-smb/`. The detached worktree `tree` was removed at the end.

Verdict: **merge**. Findings 1 and 2 are fixed. I reproduced both with my own harness, which runs the real decision code cut out of each revision. Every non-SB.-PS1 sequence I tried gives the calls that d31d4a7 gives for the same files. The one exception is the documented extra reload after an SB. PS1 attempt. CI stays green, including on Linux. I have two minor remarks: one on the doc's wording, one on a test gap. Everything here is host-only. NOT TESTED on a console or an emulator.

## What I ran (measured)

1. **My own sequence harness**, `<s>/review2-smb/sim.py`, output in `<s>/review2-smb/sim-out.txt`.
   - It does not use the author's Python model of the decision. For each revision (d31d4a7, integ, smb-2) it cuts the real text out of that revision's sources: the `case Device_SMB:` block of `common.c`, `isPopsTarget`, and `launchPOPS`'s prefix override from `handler_pops.c`.
   - It compiles that text in C together with the same revision's `handler_smb.c` and `launch_args.c` (the real `pops_is_sb_prefix` and `pops_is_xx_prefix`), plus the repo fixture.
   - It mirrors in C how init.c caches modules: the `loadModules` guard, `forceIOPReset`, and `loadModuleList`'s reset, arguments and connect. The cut-out `initModulesReload` is compiled in.

   Results, "calls" being the trace summary:

   | sequence (launcher SB.-named?) | d31d4a7 | integ | smb-2 |
   |---|---|---|---|
   | F1: `smb:/POPS/Game.VCD` (missing), then `smb:/EMBER/ember.elf` (yes) | ELF cached, session made under launcHER's rules | ELF cached, **session made under POPStarter's rules** (tcpip 29, ptype 0, echo) | ELF **reloaded**: tcpip 32, LOGON guest ptype -1, OPENSHARE, connect 0 (a fresh launcHER load) |
   | F1b: `smb:/POPS/SB.Game.VCD`, launchPOPS stops before the reboot, then the ELF (no) | cached (launcHER) | cached (launcHER, because the first stage was launcHER's: finding 2) | ELF reloaded under launcHER's rules |
   | F2: `smb:/POPS/SB.Game.VCD` full launch (no) | 32 / 32 | stage 1 tcpip 32 ptype -1, stage 2 tcpip 29 ptype 0 + echo | **both stages** tcpip 29, ptype 0, echo |
   | F2, no IPCONFIG.DAT | stage 1 fails (tcpip NULL) | stage 1 fails (tcpip NULL), stage 2 tcpip 0 | stage 1 and stage 2 both tcpip 0, LOGON 'POPStarter' |
   | F2, a fourth SMBCONFIG line / a host name | connect -22 | stage 1 connect -22, stage 2 ok | both stages ok, the same calls |
   | fresh ELF (yes / no) | 32, ptype -1 | same | same |
   | ELF then ELF (yes) | 2nd cached | same | same |
   | plain VCD full launch (no) | 32 / 32 | same | same |
   | XX. VCD from an SB.-named launcher | 32 / 32 | **29 / 32** | 32 / 32 (= d31d4a7) |
   | SB.-named launcher, plain VCD | 32 / 32 | 29 / 29 | 29 / 29 |
   | `SB.A.VCD` fails, then `B.VCD` (no) | B cached (launcHER) | B cached (launcHER) | B reloaded under launcHER's rules |
   | `A.VCD` fails, then `SB.B.VCD` (no) | cached | cached (launcHER) | reloaded under POPStarter's rules |

   For every target that is not an SB. PS1 launch, smb-2's calls equal d31d4a7's fresh load for the same files. Where d31d4a7 reused a session made under launcHER's rules, smb-2 makes the same calls again after a reload.
2. **Tests fail on integ.** I exported integ (`git archive`), copied in the new test file and fetched d31d4a7 so that Unchanged runs: `FAILED (failures=5, skipped=13)`. The failures are 3 Dispatch tests, `Source.test_sb_launches_use_the_originals_rules` and `Unchanged.test_a_launch_after_an_sb_launch`. This matches the author's claim. Log: `<s>/review2-smb/integ-run.txt`.
3. **Mutation checks** (`<s>/review2-smb/mutate.py`, output `mutate-out.txt`), each run once on an export of smb-2:
   - Removing the `liveRules` record, making `set_target` return 0, or moving the record after the SB. branch: 3 failures each (the Dispatch finding-1 test, Unchanged after-SB, the Source pin).
   - Removing `liveRules = -1` from `launcher_smb_reset`: only the Source pin fails (see minor finding 2).
4. **CI equivalence on Linux.** I ran `tools/test_pops_smb_config.py` from a `git archive` export of smb-2 (no git history, like a shallow CI checkout) in `ghcr.io/ps2homebrew/ps2homebrew:main` (Alpine, gcc, python3): `Ran 43 tests ... OK (skipped=16)`. All 5 Dispatch tests pass there. The new `-std=c99 -Werror` host build of `launch_args.c` matches what `tools/test_launch_args.py` already does on ubuntu CI.
5. **Full host suite**: all 35 `tools/test_*.py`, one at a time, from the review worktree, each with its own fresh TMP/TEMP/TMPDIR under `<s>/tmp-r2-*`. Logs: `<s>/review2-smb/logs-noref/`, `<s>/review2-smb/logs-ref/`.
   - Without the reference variables: all 35 exit 0; smb_config `Ran 43 ... OK (skipped=13)`.
   - With POPS_TEST_ELF, POPSTARTER_TEST_ELF and POPS_TROJAN_CORPUS: all 35 exit 0; smb_config `Ran 43 tests in 12.984s OK`, no skips (some other files keep their own skips, e.g. external skipped=3, trojan skipped=5).
6. **Container build** of `b654ae6` from a local clone (`<s>/review2-smb/clone`), with the mmceman submodule initialised and the given docker command: `rc=0`, `[100%] Built target launcHER`, producing `build-r2/release/launcHER.elf` (332260 bytes).
   - `handler_smb.c.obj` and `common.c.obj` built with no warning.
   - The only warning in the touched files is `init.c:332` (comparison between pointer and integer). It is in `moduleResident`, which this diff does not touch. I did not rebuild integ to compare.
   - Log: `<s>/review2-smb/build.log`.
7. **Code reading** (line numbers are smb-2's):
   - The decision in common.c:186-189 is the same as the update in launchPOPS (handler_pops.c:1082-1089) for the same `argv[0]`. handleGenericPath passes argv unchanged to LoadELFFromFile, and from there to launchPOPS (common.c:632-633).
   - Nothing between dispatch and launchPOPS changes the SB. state. Every `pops_set_active_sb_launch` call site is in main.c, handler_quickboot.c, launch_args.c's resolver (all before dispatch) or launchPOPS.
   - Stage 2 is `initPopsServices` -> `loadModuleList`. It calls `launcher_smb_reset`, then `initTCPIPArguments` under the frozen `targetRules`, then connect (init.c:368, 507, 474). So freezing the rules at dispatch gives the same result as integ's lazy `popsTarget && sb`, except for the XX. case. There integ was mixed and smb-2 is launcHER's rules in both stages.
   - `liveRules` is cleared on every module load (init.c:368) and set only in `initTCPIPArguments`. Any setup that includes SMB is therefore recorded, including the CNF-device load (handler_quickboot.c:247) and `initModulesAny`. A setup that excludes SMB leaves `currentDevice` without SMB, so the next smb: dispatch reloads anyway.

## Against the review findings

- **Finding 1: fixed.** The reviewer's sequence and the pre-reboot launchPOPS failure both now give a fresh load under launcHER's rules (table rows F1, F1b). The reverse direction (ELF, then SB. VCD) also reloads.
- **Finding 2: fixed.** An SB. VCD with SB. only in its own name uses POPStarter's rules in stage 1, with the same calls as stage 2. That holds for all four file sets the reviewer used (rows F2).
- **Finding 3:** recorded as an open question in the doc, as asked.

## Against r13

The parser and the SB. calls are unchanged by this diff (`sb_tcpip_arguments` and `sb_connect` are not touched). The SB. rule only decides when they run. For an SB. VCD on smb:, one launch now logs on under one identity only, as a single r13 run does. With refs, the Original class (unicorn, the original's blocks) passes: `Ran 43 ... OK` with no skips.

## Findings

1. (minor, doc wording, read but not run) The new paragraph about an SB. VCD on another device says "Either way the `smb:` driver is not loaded for that device, so at most the failure message differs". The SMB modules can still be resident. After an smb: load, a `mass:` dispatch takes the BDM live-stack path in loadModules (init.c:265-276), which does no IOP reset, so the SMB IRXs stay on the IOP. `loadModuleList` only clears `connected`.
   The stage-1 `pops_load_smb_stack` (handler_pops.c:1116-1120) can then really log on under the stale rule set. The launch still fails after the reboot: `initPopsServices(device)` (handler_pops.c:2066) loads no SMB for a mass: VCD, so the stage-2 `pops_load_smb_stack` (:2114) fails. The end result (the launch fails) holds; the wording does not.
   Suggested text: "...is connected under the rules of the last target dispatched from the share (0 on a fresh boot); the share's modules may still be resident from that earlier load, but they are not loaded after the IOP reboot, so such a launch fails either way. Not changed here."
2. (minor, test coverage) Removing `liveRules = -1` from `launcher_smb_reset` is caught only by the Source text pin, not by a behaviour test. The `Boot` model always runs `initTCPIPArguments` after the reset, so the stale value is overwritten before anything reads it.
   The real effect of that mutation would be extra IOP reboots after a load without SMB, not wrong rules, so the impact is small. A Boot step for "a module load without SMB" (reset only, no arguments), followed by an smb: dispatch that must not request a reload, would pin it behaviourally.

## Notes (not findings)

- **Owner question 1 (XX. side effect).** The change is not only acceptable but is what the task's rule requires. An XX. VCD from an SB.-named launcher is not an SB. PS1 launch (launchPOPS turns SB. off), and smb-2 now gives exactly d31d4a7's calls for it (row "XX. VCD"). integ's stage 1 used POPStarter's rules, which broke "a launch that is not an SB. PS1 launch behaves as before". I suggest the doc call it a correction rather than a side effect.
- **Owner question 2 (extra reboot).** The extra IOP reboot happens only on an smb: dispatch whose required rules differ from the loaded setup. It is the only difference from d31d4a7 for a non-SB. launch, and the doc states it. It has not been run anywhere: no console, no emulator.
- **Owner question 3 (quirk number).** 62 is free. The highest number in docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md is 61 on every fetched `origin/pr23/*` branch and on `origin/codex/popstarter-replacement`. The file has no IPCONFIG/SMBCONFIG entry yet. The author's proposed row 62 matches what the harness shows (31-byte text, 2 separators, 29-byte block).
- **Doc claims checked against the code.** The two `#include` lines and the one launchPath hunk in common.c, and `initModulesReload` in init.c, match `git diff d31d4a7 origin/pr23/smb-2`. main.c, handler_quickboot.c and handler_pops.c are not touched by this track. The test counts (43; 30 with no inputs, 3 of which need d31d4a7) match the skips: 13 without refs and with git, 16 without git.
- **Attribution and binaries.** The commit messages, the diff and the author identity contain no AI attribution and no email beyond the git author header. The diff adds or changes no binaries, byte tables or hashes (numstat is text only).
- **Ember.** No Ember file is touched. Ember from mass, ata or hdd never reaches the `Device_SMB` case. Ember from smb: gives the same calls as d31d4a7 on a fresh boot. After an SB. PS1 attempt it gets a fresh launcHER setup, where integ reused the POPStarter setup.

## Proposed text for files I must not edit

- docs/PR23_HANDOFF_2026-11-11.md, the review-state cell of the `21c3476` row:

  > Reviewed twice. Findings 1 and 2 (major) are fixed on `pr23/smb-2` (`b654ae6`): the rule set is decided at dispatch, and a setup made under the other rules is loaded again. The second review reproduced both fixes with the real decision code on the host. Finding 3 (minor, `ps2ip_nm` with a gateway that has no NUL) is an open question in POPSTARTER_SMB_CONFIG.md. Host tests only; NOT TESTED on a console.

- docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md: the author's row 62, as proposed. The number is free on every fetched branch.
