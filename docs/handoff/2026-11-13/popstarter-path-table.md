# POPStarter measured path table: verification evidence

**Evidence level: host tests, original MAIN under Unicorn with modelled
services, and PS2SDK container builds. NOT TESTED on a console.** No game was
booted, no ELF was run on a console, and no production path parity or
runtime-safety claim is made. This branch changes no launcher production
behavior and no Ember code.

## Branch identity and scope

| Ref | Revision | Role |
| --- | --- | --- |
| `codex/popstarter-replacement` | `0fa2c38e44bf56fbc65766c09f61876c5b8be0f5` | Draft PR integration base and merge base used for the branch diff |
| `pr23/path-table` | `87c5f0d007faff0e1141bddfb82dd8e9c6f50cfa` | Review-fixed source revision used for the final 38-file host sweeps and both clean container builds |
| `pr23/path-table` | this commit, directly after `87c5f0d` | Final documentation-only evidence head; exact commit ID is in Git history and the Task 4 report |

The branch publishes [POPSTARTER_PATHS.md](../../POPSTARTER_PATHS.md), a pure
`original_search(search) -> list[str]` comparison model, host/source checks and
CI registration. It does not add a production path implementation or a
launcHER-only path default. Later POPStarter-only work must match r13 first,
bugs included; Ember is excluded.

The controller's final verdict and merge gate remain open. This handoff records
the verification evidence and scoped re-review outcome, not a final `merge`
verdict. No merge, push, PR-ready transition or PR description update was made
with this evidence.

## Complete serial host verification

On `87c5f0d`, both final sweeps ran every `tools/test_*.py` file sequentially,
one file at a time, with a fresh `TMP`/`TEMP`/`TMPDIR` directory for each file
and separate roots for the two modes. Unittest files used verbose logs. Each
mode ran **38/38 files successfully**. Across the 27 unittest files there were
**826 tests** in each mode; the other 11 files are standalone host scripts.
These are new full runs, not a reuse of the earlier `733a3fc` evidence.

| Mode | Files | Unittest tests | Optional skips | Result |
| --- | ---: | ---: | ---: | --- |
| Reference variables unset | 38/38 | 826 | 236 | PASS, driver exit 0, 235.022 seconds |
| `POPS_TEST_ELF`, `POPSTARTER_TEST_ELF`, `POPS_TROJAN_CORPUS` set | 38/38 | 826 | 15 | PASS, driver exit 0, 1,626.300 seconds |

The remaining 15 referenced-mode skips require other optional inputs, not the
three specified references:

- Three in `test_pops_external` and three in `test_pops_progressive`: optional
  EE compiler and original MAIN.
- One in `test_pops_handoff`: `POPS_HANDOFF_ELF` not set.
- Three in `test_pops_launch_hooks`: two `POPS_RESIDENT_BIN` and one
  `POPS_TRAMPOLINE_BIN` skips.
- Five in `test_pops_trojan`: `POPS_RESIDENT_BIN` and no EE compiler.

Every named skip in both final modes, every per-file exit/timing, the driver
identity and all log paths are in the Task 4 report and its distinct
`task4-final87-*` logs. The no-reference count increased by exactly one test
and one named skip: the new partial-reference Negative regression. The
referenced skip inventory is byte-identical to the earlier 15-line inventory.
One pre-existing standalone test, `test_pops_runtime_corrections.py`,
auto-detects the canonical POPS path through its own fallback even when
`POPS_TEST_ELF` is unset. The first mode is therefore precisely a
reference-variables-unset sweep, not a claim that local auto-detection is
impossible.

Selected measured checks within the complete final referenced sweep:

| Check | Result |
| --- | --- |
| `test_pops_paths.py` | 25/25, zero skips, 142.105 seconds; all 32 cases, 40 forms, 11 other differences and negative controls |
| `test_pops_doc_claims.py` | 19/19, zero skips, 2.938 seconds |
| `test_pops_fix_order.py` | 7/7, zero skips, 627.056 seconds; 0 refused / 624 accepted in both orders and matching accepted final-core hashes |
| `test_pops_trojan_corpus.py` | 3/3, zero skips, 52.232 seconds; 509 TROJAN and 10 PATCH files by content and slot number, aggregate counts only |
| `test_pops_osd.py` | 37/37, zero skips |
| `test_pops_user_bios.py` | 55/55, zero skips |

Without reference variables, the corresponding optional-skip counts are 10 for
paths, 11 for document claims, 4 for fix order, 3 for TROJAN corpus, 17 for OSD
and 13 for user BIOS. These skips are explicit coverage boundaries, not hidden
passes. With the specified references, every path/document/corpus original
comparison ran. The order differential's separately reported 16 original-order
and 28 current-launcHER differences remain unchanged.

## Whole-branch review fixes and scoped re-review

After the `20d8cdd` evidence head, `87c5f0d` added a real partial-reference
regression. With MAIN available and Sony companions absent, it proves four
synthetic-only cases and two differences are compared before skips name all 28
omitted cases and nine omitted differences with every missing companion.
Environment and report caches are restored. With no MAIN, the explicit
`needs POPSTARTER_TEST_ELF and unicorn` reason remains.

The accepted disc range in the measured table is corrected to `0x10` through
`0x13`, including type `0x13`; only `0x10` was traced in this path suite. A
focused source/document assertion rejects the former `0x10` through `0x12`
wording.

The scoped fix evidence before the final full sweeps was:

| Mode | `test_pops_paths.py` | `test_pops_doc_claims.py` |
| --- | --- | --- |
| Reference variables unset | 25 run, 15 passed, 10 named skips | 19 run, 8 passed, 11 named skips |
| All three specified references set | 25/25, zero skips, 144.538 seconds | 19/19, zero skips, 2.895 seconds |

The controller's scoped re-review marked both findings **ADDRESSED** and
reported no new breakage. The final 38-file sweeps documented above then ran
on `87c5f0d`: path tests again passed 25/25 with references and 25 run/10 named
skips without, and document claims passed 19/19 with references and 19 run/11
named skips without. These final totals supersede the earlier 825-test full
sweeps; no console test was run.

## Measured path coverage and evidence boundary

The measured table contains **32 cases, 40 `argv[0]` forms and 11 other
differences**. The four complete modelled launch kinds (`usb`, `hdd`, `hdd-pp`,
`smb`) reach the pinned `ExecPS2` at `0x87c1cc`. Quiet and verbose profiles
request the same paths. The independently anchored wrong-path control,
unmodelled-code controls, branch-answer control, missing-input control and
quiet/verbose control all passed in the referenced path test.

This is original code running on a host under Unicorn with synthetic file
systems and modelled library calls, plus host-native resolver/source checks.
A modelled `ExecPS2` is not a real launch, proof of a device path, a game boot
or console evidence. Parameterized filename construction is covered by rules
and directed synthetic examples; arbitrary user-content strings and every
possible library fault are not exhaustively enumerated. No proprietary
reference contents, BIOS images, cards, saves, real shares or keys are in the
handoff or logs.

## PS2SDK container artifacts

`launcher/iop/mmceman` was initialized at
`db3e93f0fdbcf882f88da110cbd9b7db188ec17a`. Both final variants used
`ghcr.io/ps2homebrew/ps2homebrew:main`, the worktree mounted at `/workspace`,
the main checkout mounted at `/c/Users/natha/Github/launcHER`, and explicit
`GIT_DIR`/`GIT_WORK_TREE` values. A container Git preflight resolved the full
revision `87c5f0d007faff0e1141bddfb82dd8e9c6f50cfa`, and both version files
contain `version=87c5f0d007fa`. Fresh build directories preserve the earlier
artifacts separately.

| Variant | Build directory and artifact | Size | SHA-256 | Layout/version/result |
| --- | --- | ---: | --- | --- |
| Release | `build-pr23-path-final87-release/release/launcHER.elf` | 333,988 bytes | `c2fb1e1d32102c2746dec227093661a33a29922743a0f3082e2695467ff1952a` | `handoff layout: OK`; `version=87c5f0d007fa`; exit 0, 50.238 seconds |
| Trace, `-DLAUNCHER_BOOT_TRACE=ON -DDEBUG=ON` | `build-pr23-path-final87-trace/release/launcHER.elf` | 338,148 bytes | `45c4788f3d42be033f27f041eaea93891a90ead8255c2270967e7d11265ec09f` | `handoff layout: OK`; `version=87c5f0d007fa`; exit 0, 53.077 seconds |

Both final builds reached `[100%] Built target launcHER`. These are PS2SDK
build/layout results only; neither artifact was run.

## Remaining differences: quirks 86–99

All 14 measured path/staging behavior classes remain open. The detailed case
evidence and exact ordered paths are in `POPSTARTER_PATHS.md`; follow-on actions
are in `POPSTARTER_QUIRKS_TO_FIX_LATER.md`.

| Quirk | Remaining difference |
| --- | --- |
| 86 | Argument recognition and dispatch: prefix separator/placement/case, partition selection, stop/exit forms, `cdrom` and zero arguments |
| 87 | Image candidate construction and retries: `POPS0..9`, `__.POPS0..9`, `IMAGE0.VCD`, mounts and native extra candidates |
| 88 | HDD POPS package source: original `hdd0:__common:pfs:/POPS/POPS.ELF` plus IOPRP versus launcHER's folder list |
| 89 | USB/SMB package folders and order, including the SB IOX requirement |
| 90 | Second-name `IOPRP.IMG` fallback after `IOPRP252.IMG` |
| 91 | Original exact-size/content package acceptance versus launcHER's package validation |
| 92 | HDD per-game folder under `__common` rather than the image folder |
| 93 | Create-if-absent HDD `icon.sys` and `list.ico` staging |
| 94 | Numbered-folder selection and relocation of per-game files/cards, with fixed base-folder exceptions |
| 95 | USB/SMB `SLOT0.VMC`/`SLOT1.VMC` names, folder and creation behavior |
| 96 | Missing device POPS-folder creation and original stop order |
| 97 | No-image physical-disc probe/fallback and launch integration |
| 98 | Preserve 72 title characters and reject 73 rather than truncating to 63 |
| 99 | Complete SB startup files, modules, LOGON/ECHO/OPENSHARE, reconnect and IOX retry sequence |

OSD differences 80–85 remain separate. The owner approved exact HDD
`hdd0:__common` mounting and `pfs1:/POPS/...` layout, including per-game
folders, for later POPStarter-only implementation. That decision is **not
implemented here** and must not become an Ember or launcHER-wide default.

Follow-on order is argument parsing/dispatch (86); image candidates and
length/failure rules (87, 98); exact device/POPS-folder mapping (88, 92–96);
package acceptance and IOPRP fallback (89–91); physical-disc integration (97);
and the full SB startup/connect sequence (99). Each implementation piece needs
separate evidence and independent review. The immediate gate for this branch
is the controller's final verdict and merge decision; no merge was performed
in Task 4.
