# SMB config piece: fixes for review findings 1 and 2

Branch `pr23/smb-2` (from `pr23/integ` 4e90fda), pushed. Head `b654ae6`.
Worktree: <workspace>/launcHER.worktrees/smb-2

Commits:
- `4f497eb` fix(smb): code and host tests
- `b654ae6` docs(smb): docs/POPSTARTER_SMB_CONFIG.md

**NOT TESTED on a console or an emulator.** Everything below is host tests,
plus one container build.

## The change

The code changes stay inside the SMB rule switch.

- `launcher/src/common.c`, in `launchPath`'s `case Device_SMB:`, before
  `handleGenericPath` (so before `initModules`). The rule set is now decided
  for the dispatched target:
  `isPopsTarget(argv[0]) && (pops_is_sb_prefix(argv[0]) || (!pops_is_xx_prefix(argv[0]) && pops_get_active_sb_launch()))`.
  This is the rule `launchPOPS` applies later to the same target: an
  explicit SB./XX. prefix decides, otherwise the earlier state stays. If
  `launcher_smb_set_target(...)` returns nonzero, the case calls
  `initModulesReload()`. The file also gains `#include "launch_args.h"`.
- `launcher/src/handler_smb.c`:
  - `popsTarget` and `launcher_smb_set_pops_target` are replaced by
    `targetRules` and `int launcher_smb_set_target(int popstarter)`.
  - `sb_rules()` returns `targetRules`. handler_smb.c no longer calls
    `pops_get_active_sb_launch`.
  - `liveRules` records which rule set the loaded network module and its
    session were set up with. It is set at the top of `initTCPIPArguments`
    and is -1 after `launcher_smb_reset`, which `loadModuleList` calls on
    every load.
  - `launcher_smb_set_target` returns `liveRules >= 0 && liveRules != targetRules`.
- `launcher/src/init.c`: one new line, `void initModulesReload(void) { forceIOPReset = 1; }`,
  declared in `init.h`. The next `initModules` then reboots the IOP and
  loads the share's modules again under the target's rules, instead of
  returning early because they are already loaded.
- No external symbols were added to handler_smb.c, so the probe fixtures
  that compile it (network_transport_ee.c, pops_device_inventory_ee.c,
  test_smb_session.c) still link. Their `pops_get_active_sb_launch` stub is
  now unused, and they still get launcHER's rules (`targetRules` is 0).

Finding 1: after a setup made for an SB. PS1 attempt, a later non-SB. PS1
target in the same boot (e.g. `smb:/EMBER/ember.elf`) gets an IOP reboot
and a fresh load under launcHER's rules. That covers two cases: the VCD is
missing, or `launchPOPS` stops before the IOP reboot. The reverse direction
works the same way. Two targets that need the same rules keep the loaded
setup, as before.

Finding 2: an SB. VCD whose SB. comes only from its own name (quickboot CNF
or OSDM path) now gets POPStarter's rules in stage 1. Stage 1 and the load
after the IOP reboot make identical calls.

Side effect, measured on the host: an XX. VCD from an SB.-named launcher.
Before the fix, stage 1 used POPStarter's rules and stage 2 launcHER's. Now
both stages use launcHER's.

Ember: on its own devices (mass, ata, hdd) Ember never reaches this code.
An Ember launch from smb: that is not preceded by an SB. PS1 attempt
behaves as before: no reload, and the same rules as d31d4a7. After such an
attempt it gets one extra IOP reboot and module load. Its calls are then
the ones d31d4a7 makes for a module load of that target (see the Unchanged
test below). Nothing in Ember was touched.

## Tests (measured)

`tools/test_pops_smb_config.py` goes from 37 to 43 tests.

- New class `Dispatch` (needs no inputs). `Boot` models one boot as
  handler_smb.c sees it: `init.c`'s module cache and reload,
  `case Device_SMB:`, `launchPOPS`'s SB. update plus `pops_load_smb_stack`,
  and the load after the IOP reboot. The prefix tests come from the real
  `common/src/launch_args.c`, built for the host. `common.c`, `init.c` and
  `handler_pops.c` are not run on the host; their relevant text is pinned
  by `Source`. The tests:
  - `test_the_decision`
  - `test_a_setup_under_popstarters_rules_is_not_reused`. This is the
    reviewer's sequence. Path 2 now gives `['tcpip 32', "LOGON user='guest' ptype=-1", 'OPENSHARE ptype=-1', 'connect 0']`,
    the same as a fresh boot. The same holds after `launchPOPS` fails
    before the reboot, and in the reverse order.
  - `test_the_same_rules_keep_the_setup`
  - `test_an_sb_vcd_uses_popstarters_rules_from_the_first_stage`. It covers
    the reviewer's four file sets: plain, no IPCONFIG.DAT, a fourth
    SMBCONFIG line, a host name. For each, stage 1 matches the calls of an
    SB. launch (e.g. `tcpip 29`, LOGON user `POPStarter`, ECHO, OPENSHARE,
    `connect 0`, or `tcpip 0` with no IPCONFIG.DAT), and the post-reboot
    load makes the same calls.
  - `test_an_xx_vcd_keeps_the_launchers_rules_in_both_stages`
- New `Unchanged.test_a_launch_after_an_sb_launch` (needs d31d4a7 in the
  checkout): the ELF after an SB. attempt gets exactly the calls that
  d31d4a7's handler makes on a module load for it.
- `Source` pins:
  - the new handler_smb.c lines
  - the exact `case Device_SMB:` text
  - `initModulesReload`
  - the `loadModules` cache test
  - `launcher_smb_reset` at the start of `loadModuleList`
  - `isPopsTarget`'s body
  - `launchPOPS`'s prefix override
- `session()` now goes through `launcher_smb_set_target` when the handler
  has it.

Fails on pr23/integ: I made a detached worktree at 4e90fda and copied in
only the new test file. 5 tests fail:
- Dispatch: the finding 1 test (path 2 trace `[]`, the cached session reused)
- Dispatch: the finding 2 test (stage 1 `tcpip 32`, LOGON user `''`, launcHER's rules)
- Dispatch: the XX test (stage 1 `tcpip 29`)
- `Unchanged.test_a_launch_after_an_sb_launch`
- the Source pin

Log: <scratch>/smbfix/integ-run.txt

Mutation checks, each run once on the host. Either of these makes the
finding-1 Dispatch test, the Unchanged test and the Source pin fail:
- removing `liveRules = sb_rules();`
- making `launcher_smb_set_target` always return 0

Full suite, all 35 `tools/test_*.py` run one at a time from the worktree
root at b654ae6, with TMP/TEMP/TMPDIR set to fresh folders:
- without the reference variables: all 35 exit 0;
  test_pops_smb_config `Ran 43 ... OK (skipped=13)`;
- with POPS_TEST_ELF, POPSTARTER_TEST_ELF and POPS_TROJAN_CORPUS: all 35
  exit 0; test_pops_smb_config `Ran 43 ... OK` with no skips.

Per-file logs are in
<scratch>/smbfix/tests
(summary-plain.txt, summary-refs.txt).

## Build (measured)

I initialised the mmceman submodule, then ran the container command from
the task (`cmake -B build-smbfix`, target launcHER) on commit 4f497eb. The
build gave exit 0 and `[100%] Built target launcHER`, producing
build-smbfix/release/launcHER.elf. common.c and handler_smb.c compiled with
no warnings. The one warning in init.c (:332, `slib_get_exp_lib`
comparison) was already there on integ.

Inside the container git did not resolve the worktree, so the version is
"unknown" (CMake warning). The build itself worked, so I did not redo it
from a local clone. The b654ae6 commit only changes the doc.

## Not done / open

- No console, emulator or SMB server run. The IOP reboot and reload
  between two launch attempts were not run anywhere.
- Finding 3 (minor) is kept as an open question in the doc's "Not
  measured". For `10.0.0.9 255.255.255.0 10.0.0.1`, the 29-byte block
  reaches `ps2ip_nm` ending in the gateway's first 7 bytes with no NUL.
  What `ps2ip_nm` does with that, or with no arguments, is unknown.
- One stale case is unchanged and now documented. An SB. VCD on another
  device (`mass:`) that reaches `pops_load_smb_stack` uses the rules of the
  last target dispatched from the share. Before the fix it used that
  target's PS1 flag combined with the current SB. state. The smb: driver is
  not loaded there either way, so at most the failure message differs.
- The `Dispatch` model of `common.c`/`init.c`/`handler_pops.c` is checked
  against their source text, not by running them.

## Proposed text for files I must not edit

docs/PR23_HANDOFF_2026-11-11.md, the review-state cell of the `21c3476` row:

> Reviewed once (three findings). Findings 1 and 2 (major) are fixed on
> `pr23/smb-2`: the rule set is decided at dispatch, and a setup made under
> the other rules is loaded again. Finding 3 (minor, `ps2ip_nm` with a
> gateway that has no NUL) is an open question in POPSTARTER_SMB_CONFIG.md.
> Host tests only.

docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md: possible next entry. 61 is the last
number on this branch; check that other tracks have not taken 62.

> | 62 | `IPCONFIG.DAT`: the argument length is the file size minus the number of space/CR/LF bytes, so the block handed to the network module stops that many bytes before the end of the text and its last part (normally the gateway) loses its last characters and its NUL. Copied for `SB.` launches; what launcHER's `ps2ip_nm` does with it is not measured. | Pass the whole text with each separator turned into NUL, ending in a NUL. |
