# POPStarter r13 gap audit (2026-11-11)

What POPStarter r13 does that launcHER does not yet do, or does differently,
with the addresses needed to continue. Written so the next person does not
have to rediscover it. Base commits: launcHER `cfebe01`, REPOP main
`bc258e48`.

**Brought up to launcHER `ef663b2` (second correction pass, section 2b).**
Five pieces merged after `cfebe01`: `CHEATS.TXT` command recognition with
`$USBDELAY_n` and `VMCDIR.TXT` (`95ba812`), the IGR skin (`173d5de`), the
user `BIOS.BIN` and its loader state (`0945127`), the `SB.` network files
(`21c3476`) and the drive-free part of the physical disc (`f22a69f`). The
launcHER paragraphs of sections 3, 4, 5a, 6, 8, 9, 11, 13, 14 and 16 say
what those merges changed, only as far as the merged code and its tests
show it. Three areas are being changed on side branches while this is
written and are marked "in progress on a side branch": the handoff defect
(`pr23/handoff`), TROJAN files (`pr23/trojan`) and the answers to the first
review of the `CHEATS.TXT` pass (`pr23/cfg`). What those branches will end
with is not described here.

**Nothing in this document was run on a console or in an emulator of the
whole machine.** "Measured" means: the named block of the original was run on
a host under Unicorn (or the in-repo R5900 interpreter) with its library
calls modelled, or launcHER's C code was built with host gcc and called.
That establishes what the block writes and in which order. It does not
establish what a PS2 does afterwards.

## 1. Inputs, labels, limits

Ground truth: POPSLoader `POPSLDR/PROFILES/MAIN/POPSTARTER.ELF` (167,700
bytes, sha256 `734c813e…`), unpacked by
`tools/trace_original_pops_io.py:decode_main` to 1,350,828 bytes at EE
`0x870000` (sha256 `185177c2…`), `gp = 0x9b68f0`. Sony `POPS.ELF` is
3,166,988 bytes (`0x30530c`, sha256 `59df3389…`); its core occupies
`0x200000..0x502e60`. Neither file is in the repository and no bytes of them
are reproduced here beyond single instruction words and configuration
values.

This audit condenses nine read-only mapping reports made on 2026-11-11 (one
per area, plus a critic that re-derived the main claims of seven of them with
its own scripts). The critic did not see the device/file report, so
everything that comes only from that report is labelled `1x` at best.

Confidence labels, used on every statement:

| Label | Meaning |
|---|---|
| `2x` | measured by two independent runs: the area's own run and the critic's separate re-run, or (where an `S` number follows) the area's run and a check made while writing this document |
| `1x` | measured once, by one agent, not independently re-run |
| `read` | read from disassembly or source, not executed |
| `inferred` | a conclusion drawn from the above, not observed |

`S1`..`S33` after a label refers to the spot checks in sections 2, 2a and
2b.
"Host" in a table says whether the statement, or the launcHER code that
would implement it, can be checked on a host without a console: `yes`,
`partly`, or `no`.

launcHER line numbers are for commit `cfebe01`. Rows changed by the second
correction pass name launcHER functions instead of lines; the `cfebe01`
line numbers that remain in other rows were not re-checked at `ef663b2`
and many have moved.

`S1`..`S19` were made for the first version of this document. An
independent review of that version re-derived most of it with its own
scripts and found statements that were wrong, too strong or stale, here
and in the status documents corrected with it. A correction pass on the
same day reproduced each finding and added `S20`..`S29` (section 2a).
Where a row below was changed by that pass it cites one of those numbers.

## 2. Spot checks made for this document

Each was run on 2026-11-11 against the external files or the sources named.
The scripts are throwaway and not in the repository.

| # | Check | Result |
|---|---|---|
| S1 | size and sha256 of packed and unpacked MAIN | 167,700 / `734c813e…`; 1,350,828 / `185177c2…` |
| S2 | file bytes `0x408..0x42f` of the four POPSLoader profiles (MAIN, DEBUG, USBDELAY, USBDELAY_DEBUG) | all four files 167,700 bytes; they differ only at `0x410` (`00`/`ff`) and `0x413` (`02`/`06`); values as in section 9 |
| S3 | occurrences of the bytes `DLAY` in the unpacked image | one, at `0x91fb30` |
| S4 | instructions at `0x880894..0x8808a0` | `lui v1,7` / `ori v1,v1,0xff8e` / `slt v0,v1,v0` / `beqz`: accept only when size > `0x7ff8e` |
| S5 | pristine `POPS.ELF` words | `0x200794=03a0202d`, `0x200798=14400005`, `0x2525b0=0ff01bfc`, `0x228a20=30a30904`, `0x228a50=24020904`, `0x228a5c=3c110086`, `0x228a60=24030080`, `0x263c28=0c00fa0c`, `0x2362fc=0808bb10`, `0x21a63c=00000000` |
| S6 | every `jal` to thirteen functions, scanning `0x870000..0x91ef00` | `0x87e464`: `0x876b18`. `0x88019c`: `0x876cd8`, `0x876fd8`. `0x87eb24`: `0x876bac`, `0x876ea0`. `0x880a24`: `0x876d6c`, `0x877078`. `0x881de8`: `0x876e00`, `0x877118`. `0x883270`: `0x8771ac`, `0x87724c`. `0x870b78`: `0x8700f0`. `0x8e00d0`: five sites. `0x8ff0e4`: six sites in main. `0x87cf68`: `0x8743d8`. `0x8d8db8`: `0x87432c`. `0x8d8050`: `0x878ebc`. `0x8dc9ac`: `0x870a6c`, `0x8774bc` |
| S7 | IGR skin size tests | `0x87e5b8` `lui 4` / `ori 0xc300` / `slt`; `0x87e7dc` and `0x87e9e8` `slti v0,v0,0x1dbd` |
| S8 | the four functions missing from REPOP's ground truth | each starts with its only stack allocation (`-0x1630`, `-0x180`, `-0x30`, `-0x30`) and ends with `jr ra` and the matching release; sizes 46,752 + 335,124 + 126,996 + 88,140 = 597,012 bytes |
| S9 | TIM2 headers inside `POPS.ELF` at the skin slots | `0x2feff0`: 400x260 type 2, total `0x4c2f0` + 16; `0x34b2f0` and `0x34d0b0`: 74x34 type 2, total `0x1dac` + 16 = 7,612; next TIM2 at `0x34ee70` |
| S10 | `0x871328..0x8713c8` | byte compares spell `cdrom`; `0x8713c4` is `li v1,4` / `syscall` |
| S11 | every `lw`/`sw` with base `gp` and offset `0x3b98`, `0x38a4`, `0x3410`, `0x3448` | `0x3b98`: 16 readers (`0x878f64`, eight in `0x8790a8..0x879540`, `0x8948f0`, `0x894d4c`, `0x895088`, `0x8db98c`, `0x8dc75c`, `0x8dc7c4`, `0x8dc800`), writers `0x870c4c`, `0x880920`. `0x38a4`: 16 readers at the matching sites, writers `0x870c48`, `0x880930`. `0x3410`: 8 readers, 10 writers, as in section 8. `0x3448`: writers `0x870c64`, `0x871618`, `0x8719a4` only |
| S12 | instructions carrying the immediate `0x079a` | `0x8800a0` and `0x8809a0` only (the OSD and BIOS handlers) |
| S13 | `0x879d84..0x879de4` | four `li` of `0x44`, `0x4c`, `0x41`, `0x59` (`D`, `L`, `A`, `Y`) |
| S14 | `python tools/popstarter_r13_commands.py` on MAIN | 72 lines; none contains `NOBOOT` or `BIOS`; `$USBDELAY_` handler `0x89dbe0` writes byte `0x100017` = 0..9; the three `$UNDO_` handlers list `w16[0x2525b0]=0x1bfc` |
| S15 | headers of every `TROJAN_n.BIN` / `PATCH_n.BIN` under REPOP `popstarter/` | 3,952 TROJAN files, 509 unique; 870 PATCH files, 10 unique; details in section 12 |
| S16 | launcHER `pops_fix_stage` (sources at `cfebe01`, host gcc) on each unique corpus file over a fresh pristine core | TROJAN: `-3` for 509 of 509. PATCH: `0` for 10 of 10 |
| S17 | launcHER source lines cited in this document | all found at the cited lines; one correction, see S19 |
| S18 | REPOP heads and `python tools/parity_report.py popstarter` | `origin/main` = `bc258e48`; `feat/psxcore-validation` (`d3452068`) is an ancestor of `claude/popstarter-validation`; `0d5ca939` is in main; report prints 466 / 138,664 / 434 / 93.1% / 90.2%. The first version of this row also said the worktree `REPOP.worktrees/pr23` was at `bc258e48`. That stopped being true before this document was committed: see S20 |
| S19 | where launcHER's `$USBDELAY` sleep runs | `handler_pops.c:1751-1753`, which is after `SifIopRebootBuffer` at `:1665`. One mapping report said "before the IOP reset"; that is wrong |

S1..S19 include no emulation of the original's handlers. Except where a
row cites S22, S23 or S27, the handler behaviour below rests on the mapping
agents' runs and the critic's re-runs as labelled.

### 2a. Checks added by the correction pass

Made on 2026-11-11 after the review, with scripts separate from the mapping
agents', the critic's and the reviewer's (throwaway, not in the
repository). The emulated ones run one function of the original under
Unicorn with its file, folder and print calls replaced by models; memory
effects were found by comparing snapshots. All of it is host work. NOT
TESTED on a console.

| # | Check | Result |
|---|---|---|
| S20 | REPOP heads again | `origin/main` is still `bc258e48`. The worktree `REPOP.worktrees/pr23` is not at that commit. It is on a local working branch (not in `main`), created from `origin/main` at 04:26:42 (-0800) on 2026-11-11; the branch's reflog shows it at `bc258e48` until its first local commit at 06:25:53 (the first version of this document was committed at 06:28:19). When looked at again it was six commits past `bc258e48`, head `0a440b01`, with one uncommitted change. `python tools/parity_report.py popstarter` on a `git archive` export of `bc258e48`: 466 / 138,664 / 434 / 93.1% / 90.2% |
| S21 | every `jal 0x915708` (the print call) classed by a pattern: is there, in the 12 instructions before it, a `lw v1,0x38b0(gp)` / `li v0,1` / `beq v1,v0` that jumps past the call. A pattern scan, not a flow analysis. Call sites and the number without the test, per range | BIOS handler: 14, 2 without (`0x8805b4`, format `DONE\n`; `0x880984`, format `\n`). OSD handler: 41, 3 without (`0x87eee0`, `0x87f27c`, `0x87f3a8`). IGR skin function: 15, 0 without. TROJAN loader: 20, 1 without (`0x881cec`). `main` (`0x870b78..0x87c214`): 295, 21 without. Whole code area `0x870000..0x915000`: 2,031, 145 without |
| S22 | BIOS handler `0x88019c` emulated: 20 inputs (scope x `pfs1`/`mass` x no file and four sizes), each with `gp+0x38b0` 1 and 0; 8 more with the game folder present or missing; 4 more with `gp+0x38e0` already 1 | With `gp+0x38b0 = 1`: 18 print calls, in 14 of the 20 inputs, all from the two sites S21 names. With 0: 84 calls. Every game-scope run changes `gp+0x38e0` from 0 to 1 (10 of 10); no all-games run does (0 of 10). Game folder missing: return -666, `gp+0x3460 = 1`, nothing opened, POPS unchanged (4 of 4, both backends). With `gp+0x38e0` already 1 the folder is not checked and the file loads (4 of 4) |
| S23 | IGR skin function `0x87e464` emulated: 32 runs with `gp+0x3868 = 1` (backend x `gp+0x38dc` x four file sets x in-limit/oversize), 16 runs with `gp+0x3868 = 0` and the folder check `FUN_008d8958` forced to return 1, 0, 2 or -1, 2 runs with preset byte `0x10002d` 0 and 2 | `gp+0x38dc = 1`: return 0, nothing opened, POPS unchanged (24 of 24). `gp+0x38dc = 0`, `gp+0x3868 = 1`: return 1 (16 of 16, whatever the files). `gp+0x38dc = 0`, `gp+0x3868 = 0`: folder check 1 gives the normal load and return 1 (2 of 2); any other result gives return -666, `gp+0x38dc = 1`, nothing opened (6 of 6). The preset byte does not matter inside the function (2 of 2 still open the three files). Instructions: `0x87e474..0x87e488`, `0x87e48c..0x87e4c4`, `0x87eb04..0x87eb0c` |
| S24 | `main` `0x8712c8..0x8712ec` and `0x876a84..0x876b24` | preset `0x10002d` equal to 1 sets the frame word `0x1108(fp)` (its only writers are `0x870ce8`, zero, and `0x8712ec`). The call at `0x876b18` is skipped when `gp+0x38dc` is nonzero (`0x876a84`) or that word is not 1 (`0x876a90`, its only reader). After the call `main` reads `gp+0x38dc` (`0x876b20`), not the return value |
| S25 | `$USBDELAY_` handler address | `tools/popstarter_r13_commands.py` prints `0x89dbe0`, the `lbu` that fetches the first character; the compare with `$` (`li v0,0x24`) is the next instruction, `0x89dbe4`; the block starts at `0x89dbd4`. This document and the inventory now use `0x89dbe0` only |
| S26 | the original's always-live block (source `0x983150`, `0x738` bytes, running at `0x232790..0x232ec8`) scanned for the word pair `10000001 00000000` (`b +8` / `nop`) | 60 pairs: 5 at `0x2327d0..0x2327f0` and 55 at `0x232d08..0x232eb8`, which is the end of the block |
| S27 | the fix-file corpus again: the original's loaders `0x880a24` / `0x881de8` emulated on every unique file, and launcHER's `pops_fix_stage` (host gcc, sources at `cfebe01`) on the same files over a fresh pristine core | Original, TROJAN: 509 of 509 return 1, the payload is found at its load address, the slot word changes from `b +8` to `jal entry`, nothing else in POPS changes, no "Invalid" or "Skipped" message. Original, PATCH: 10 of 10 return 1. launcHER: TROJAN -3 for 509 of 509 with the core unchanged; PATCH 0 for 10 of 10, and for each of the 10 the changed core bytes and their values equal the original's. One PATCH file (a `PATCH_5.BIN` of 327,360 bytes, payload 327,296 bytes) loads at `0x2feff0..0x34ee70`, exactly the three IGR skin slots. One config-only PATCH (a `PATCH_6.BIN`) changes the halfword `0x2525b0`, which lies in the ROM copy. No corpus PATCH file changes a byte in the OSD areas |
| S28 | the embedded PFS wrapper IRX at `0x91f680`: first read statically (import tables and `.text`), then its callbacks run on a host | the routine at `.text` 0 calls `thsemap` import 8, tests a flag word at `0x540`, reads the word at `0x420` (the only `DLAY` in the image), uses 5 instead if it still reads `DLAY`, multiplies by 1,000,000 (shifts and adds), calls `thbase` import 33, clears the flag, calls `thsemap` import 6. Its only caller is `.text` `0x124`, inside the function at `0xd4`, which is the fourth pointer of the 17-pointer table at `0x544`. The five words after the table are `0x430`, `0x10`, `1`, `0x410`, `0x544`: the shape of an ioman device record whose last word points back at the table. Then the wrapper's own callbacks were run under Unicorn through the classes of `tools/trace_original_pops_io.py`, every import call recorded in order. Word left as `DLAY`: the first call of table entry 3 makes the import calls `sysclib` 23, `thsemap` 8, `thbase` 33 with argument 5,000,000, `thsemap` 6, then `ioman` 4 (open of `mass:/POPS/IMAGE.VCD`); the following read, seek, close, second open and close make no `thbase` call. Word replaced by `n, 0, 0, 0` for n = 0..9: the same sequence with argument n x 1,000,000, once, before the first backend open, and none in six later callbacks (10 of 10). Read, seek and close called before any open make no `thbase` call; the first open after them does (1 of 1) |
| S29 | `.github/workflows/*.yml` against `tools/test_*.py` at `cfebe01` | 26 test files. `build.yml` job `host-tests` runs 23. `launch-args.yml` runs `test_launch_args.py` on push and pull request. `test_pops_builtin_db.py` and `test_pops_progressive.py` are named in no workflow |

### 2b. Checks added by the second correction pass (`ef663b2`)

Made on 2026-11-11 after the second review of this document, with scratch
scripts (not in the repository) built on the in-repo tracers
`tools/trace_original_pops_user_bios.py` and
`tools/trace_original_pops_igr_skin.py`. Unlike those tracers as committed,
both runs let the POPS folder check `FUN_008d8958` (`0x8d8958..0x8d8b10`)
execute; only its callees are models: `0x8d7e78` (the `pfs1:` folder
check), `0x91bf80` (the `mass:` stat call), `0x91be68` (called on
`mass0:/POPS` after a failed stat) and the print routine. Host work only.
NOT TESTED on a console.

| # | Check | Result |
|---|---|---|
| S30 | BIOS handler `0x88019c` with `gp+0x3868 = 0`: scope (all games, game) x backend x POPS folder present or missing x game folder present or missing x file absent or `0x80000` bytes x `gp+0x38b0` 1 and 0 (64 runs), plus 4 runs with `gp+0x3868 = 1` and the POPS folder missing | All games, POPS folder missing: return -666, nothing opened, core unchanged, `gp+0x38dc`, `gp+0x3460` and `gp+0x3868` each 0 to 1 (16 of 16). Game, POPS folder missing: the failed check is ignored and the handler goes on. Game folder and file present: the file loads, return 1, and `gp+0x38dc`, `gp+0x3460`, `gp+0x3868`, `gp+0x38e0`, `gp+0x3b98` are all 1 afterwards (4 of 4). Game folder present, no file: return 0 (4 of 4). Game folder missing: -666 from the game-folder exit (8 of 8). POPS folder present: the results of S22, and `gp+0x3868` goes 0 to 1 (32 of 32). On `mass:` a failed check also calls `0x91be68` on `mass0:/POPS`. With `gp+0x3868 = 1` the check is not made and the file loads although the folder model says missing (4 of 4) |
| S31 | IGR skin function `0x87e464` with `gp+0x3868 = 0`: backend x POPS folder present or missing x `gp+0x38b0` 1 and 0 (8 runs) | Folder missing: return -666, nothing opened, core unchanged, `gp+0x38dc`, `gp+0x3460`, `gp+0x3868` each 0 to 1 (4 of 4); on `mass:` also the call of `0x91be68` on `mass0:/POPS`. Folder present: return 1, three opens, of those words only `gp+0x3868` changes (4 of 4) |
| S32 | static: every `jal 0x8d8958` in `0x870000..0x915000`, and every `li v0,-666` inside the five file loaders | Callers: `0x873f9c` (`main`), `0x87e49c` (IGR skin), `0x87ec38` (OSD), `0x880348` (BIOS), `0x880aac` (TROJAN), `0x881e70` (PATCH), `0x8d4fac` (the `VMCDIR.TXT` reader). `-666` stores: IGR `0x87e4bc`; OSD `0x87ec68`, `0x87ee84`, `0x87eed0`; BIOS `0x880378`, `0x880558`, `0x8805a4`; TROJAN `0x880adc`, `0x880d18`, `0x880d64`; PATCH `0x881ea0`, `0x8820d8`, `0x882124`. Disassembly of `0x8d8958..0x8d8b10`: it returns 0 only when `gp+0x38dc` or `gp+0x3868` is 1 on entry; otherwise it sets `gp+0x3868 = 1` first and returns 1, or -666 with `gp+0x38dc = 1` and `gp+0x3460 = 1` (a `gp+0x3448` other than 0 or 1, which no store writes, S11, also returns 1) |
| S33 | `.github/workflows/*.yml` against `tools/test_*.py` at `ef663b2`, read by the step parser of `tools/test_pops_doc_claims.py` | 32 test files. `build.yml` job `host-tests` runs 29, each as an unconditional step of its own. `launch-args.yml` runs `test_launch_args.py`. `test_pops_builtin_db.py` and `test_pops_progressive.py` are run by no workflow |
| S34 | static: the BIOS handler `0x88019c` from its first gate to the POPS folder exit (`0x8801b4..0x880338`), and every read of `gp+0x38e0` in the handler | Seven gate loads, in this order: `gp+0x38dc` (any scope), `gp+0x343c` and `gp+0x344c` (all games), `gp+0x3878` (game), `gp+0x3430` (all games), `gp+0x344c` and `gp+0x3460` (game); the scope is the frame word `0(fp)`, 1 for the game. A gate that is set branches to the shared return `0x880a0c` (`lw v0,0xc0(fp)`) with `sw zero,0xc0(fp)` in the delay slot: six such branches, the `gp+0x343c`/`gp+0x344c` pair sharing one, each after an optional SKIPPED print gated by `gp+0x38b0`. The handler reads `gp+0x38e0` once, at `0x8804ec`, after all of them |

### What `tools/test_pops_doc_claims.py` checks

The test was added by the first correction pass. The second review showed
that it pinned less than this paragraph then said (12 of the reviewer's 23
one-line changes to the documents survived it). The second pass rewrote it;
it now checks exactly the following, and nothing else in this document is
read by a test. The results of the deliberate changes tried against it are
in section 19.

Without the reference inputs (as in CI):

- The `ci-coverage` list in `CLOUD_CONTINUATION.md` against the workflows.
  A test file counts as run only when an uncommented line of a step's
  `run:` begins a command `python tools/<file>` (or `python3`, `py`, also
  after `&&` or `;`), not followed by `||` on that line; the step and its
  job have no `if:` other than `always()`, `success()` or `true` and no
  `continue-on-error`; and the workflow is triggered by push or pull
  request. The parser is a small hand-written one for the YAML the
  workflows use (PyYAML is not a CI dependency). "Every other file" must be
  a step of the job the block names (`host-tests` in `build.yml`). The
  parser is itself tested on synthetic texts: a commented-out step and run
  line, `if: false`, `if: ${{ false }}`, another condition, `if: always()`,
  `continue-on-error: true`, `|| true`, a mention inside `echo`, a job-level
  `if:`, a manual-only trigger, a flow-list trigger and a block-scalar
  `run:`.
- One address for the `$USBDELAY_` handler in every document; every `S`
  number cited here is defined, once; eight withdrawn sentences are gone
  from README.md, `docs/pops-setup.html` and every `docs/*.md`.

With `POPSTARTER_TEST_ELF` (a value that is set but cannot be used, or no
capstone, is a failure, not a skip), from the original's bytes, each
compared with whole phrases of this document or the inventory:

- the S21 census, one exact phrase per range (count, number without the
  test, and the sites when there are one to three, with the format string
  of each for the BIOS handler), `main` ending at `0x87c214` (`jr ra` and
  its delay slot, then the next function's frame) with section 3's
  sentence on `main`'s range and frame size, and the counts and two
  sites in the `gp+0x38b0` row;
- S25: the handler address `tools/popstarter_r13_commands.py` prints, the
  compare one word on, and every `$USBDELAY_` handler citation;
- `FUN_008d8958` (S32): its entry tests, its stores of `gp+0x3868`,
  `gp+0x38dc` and `gp+0x3460`, its two `-666` sites, its three callees and
  the sentence that states its return values; its seven callers in S32 and
  in the `gp+0x3868` row; `main`'s own call with the `gp+0x3888` gate and
  its one store of `gp+0x3868` (`0x87425c`);
- the `-666` stores of the five loaders, as one phrase, each after the
  loader's single call of the folder check;
- the BIOS handler's gates (S34: the seven flag loads of
  `0x8801b4..0x880334` in order, with the scope each is tested in, six returns of 0, and the
  section 4 gates sentence), its POPS folder exit (the instructions at
  `0x880338`, `0x880348`, `0x880360`, `0x880368`, `0x880374`, `0x880378`
  and the section 4 sentence) and its game-folder exit (the once-flag read
  at `0x8804ec`, the only one in the handler, the store at `0x880500`, the
  two calls, stores and `-666` sites, and their sentences, including the
  condition on "always leaves `gp+0x38e0 = 1`");
- the IGR skin function's return values 1, 0 and -666, the instructions
  that decide them, the section 6 sentences on the folder check and its
  extra writes, and the inventory's IGR sentence;
- S24: the frame word's writers and reader, the two `gp+0x38dc` reads
  around the call with a `nop` in the delay slot, and the S24 sentence
  whole;
- the `gp+0x38e0` sites (section 3a), in the order the row names them;
- S26 and the slot list of section 12, entry by entry, against a list kept
  in the test (`SLOTS`);
- the wrapper run of S28, with the S28 sentences, the section 9 sentence on
  when the delay is called, and the inventory's `$USBDELAY_n` sentence.

With `POPS_TROJAN_CORPUS` (a folder of community fix files; a value that is
not a folder is a failure): the file counts of S15 and section 12, and that
every `TROJAN_n.BIN` header's hook word (offset 24) is the slot `SLOTS`
gives for its file number.

It does not repeat the emulated runs S22, S23, S27, S30 and S31, it does
not check the launcHER paragraphs of sections 4 to 14 against launcHER's
code, and it does not read README.md or `docs/pops-setup.html` beyond the
withdrawn sentences.

## 3. Order of the original's launch function, and launcHER's

The original's `main` is `0x870b78..0x87c214` (frame `0x1630`; an earlier
version of this sentence gave `0x87c218`, which is the first instruction of
the next function). It is
unoptimised straight-line code. The critic listed every backward branch and
every `j` in it: 33 backward branches, none spanning a loader call site
between `0x876a40` and `0x879d04`, and one `j` (the jump into POPS at
`0x87c1d8`). So for the loaders, execution order equals call-site address
order (`1x` for the branch scan; call sites `2x S6`). `main` has never been
executed end to end by anyone.

| Original site | What | launcHER (`launcher/src/handler_pops.c`) |
|---|---|---|
| `0x870bd0..0x871324` | reads the preset block (section 9) | none |
| `0x871328..0x8713c4` | `argc == 0` or `argv[0]` begins `cdrom`: Exit | none |
| `0x8714b8..0x8719c4` | `SB.` / `XX.` scan of `argv[0]` | `:755-762`, different rules (section 10) |
| `0x8719f0..0x873ef0` | `mc?:/POPSTARTER/` modules, `IPCONFIG.DAT` / `SMBCONFIG.DAT` | `handler_smb.c` with `common/src/pops_smb_config.c` since `21c3476` (section 11) |
| `0x873ef0..0x8743d8` | `hdd0:__common` mount to `pfs1`, POPS folder check, SMB logon; launch type parser `FUN_008d8db8` called at `0x87432c` | no `__common`; own resolver in `common/src/launch_args.c` |
| `0x8743d8` | POPS load `FUN_0087cf68` | `:830` search, `:1203-1281` load and SHA-256 pin |
| `0x874754` | copies its always-live block `0x983150` to `0x232790` (`0x738` bytes) | own resident image, `:1363-1379` |
| `0x874a24..0x874c94` | preset-driven core patches | `:1379` `pops_apply_always_on_pokes` |
| `0x8754e0..0x876690` | VCD probes per launch type | `:823` (the target is already a `.vcd` path) |
| `0x8766fc..0x876a40` | physical disc fallback (section 8) | none: `common/src/pops_physical_disc.c` is built into the launcher since `f22a69f` but nothing calls it |
| `0x8757d4..0x8769ac` | built-in fingerprint `FUN_008ff0e4` (six call sites) | `:896-924`, `:1404` |
| `0x876a50`, `0x876a7c` | exit program copy to `0x1450000`, `j 0x1450000` at `0x2362fc` | not copied on purpose |
| `0x876b18` | IGR skin (section 6) | `pops_stage_igr_skin` (`:1657`), after the built-in entry, since `173d5de` |
| `0x876bac`, `0x876cd8`, `0x876d6c`, `0x876e00` | all games: OSD, BIOS, TROJAN, PATCH | BIOS, TROJAN and PATCH (no OSD), in `pops_stage_fix_files` inside `pops_stage_user_files` (`:1683`), after the commands |
| `0x876ea0`, `0x876fd8`, `0x877078`, `0x877118` | current game: OSD, BIOS, TROJAN, PATCH | as the row above |
| `0x8771ac`, `0x87724c` | `CHEATS.TXT`, all games then current game (`FUN_00883270`) | read in `launchPOPS`; applied by `pops_apply_all_config_patches_rom` inside `pops_stage_user_files`, before the files |
| `0x8772e0`/`0x877380`, `0x877414`/`0x8774b4` | `VMCDIR.TXT`, `DISCS.TXT` | `:926` |
| `0x878ebc` | VMC preparation `FUN_008d8050` | `:1639-1661` |
| `0x878f64` | PS1 BIOS shell edits, gated on four flags | `pops_apply_bios_shell_edits_rom` (`:1714`), gated on the loader state since `0945127` |
| `0x879034` | region pass | `pops_apply_region_rom` (`:1722`) |
| `0x8795f0` | `$RESET_WARMBOOT` pass | `pops_apply_reset_warmboot` (`:1740`) |
| `0x879d04..0x879e58` | `$USBDELAY` byte patched into the PFS wrapper | none (`sleep(cfg.usb_delay)` at `:1985` on the EE instead; in progress on a side branch, section 9) |
| `0x879e5c..0x87c1e0` | IOP resets, module starts, final clears, `j 0x22e440` | `:1665` onwards |

**Order difference that already exists.** The original runs TROJAN and PATCH
files (all games, then the game) before the `CHEATS.TXT` parser. launcHER
runs the user's commands before its fix files. At `ef663b2` both are inside
`pops_stage_user_files` (`handler_pops.c`): `pops_apply_all_config_patches_rom`,
then `pops_resident_hook_recompiler_emit`, then `pops_stage_fix_files`, and
`tools/test_pops_launch_hooks.py` (`Source.test_launch_order`) pins that order
by text. For the BIOS flags the merge `0945127` added a look-ahead so the
commands see the flags the original's commands would see
(`docs/POPSTARTER_USER_BIOS.md` difference 1). With no `BIOS.BIN` loaded the
order still shows at `0x2525b0`: 28 of that document's 270 launch-sequence
scenarios end differently, all through a `$UNDO_` command (its difference
2; Unicorn on the host). Other inputs ending differently because of this
have not been measured. One case cannot occur yet because there is no OSD
loader: `$COMPATIBILITY_0x06` in `CHEATS.TXT` plus an `OSD.BIN` ends with
the OSD off in the original and would end with it on if the OSD were
staged after the commands.

At `cfebe01` the same test required `res = pops_apply_bios_shell_edits(` with
no flag gate. Since `0945127` it pins `res = pops_apply_bios_shell_edits_rom(`
and `res = regionRead ? pops_apply_region_rom(` instead, which take the
loader state; reordering the fix files would still break the test by design
and has to update it in the same commit.

## 3a. The original's state flags used below

All are words at `gp + offset`.

| Offset | Meaning | Label |
|---|---|---|
| `0x3448` | 1 on `XX.` and `SB.` launches ("mass mode"), else 0; written only at `0x870c64` (0), `0x871618` (`SB.`), `0x8719a4` (`XX.`) | `2x S11` |
| `0x3888` | 3 on `SB.` launches, else 0 | `read` |
| `0x3414` | launch type 0..3 (section 10) | `read` |
| `0x3410` | 1 when no VCD was found: physical disc mode | `2x S11` |
| `0x38dc` | shared abort flag: 15 readers in `main`, set by the POPS folder check and several loaders. Not a per-function "done" flag (REPOP's comment at `popstarter/src/main.c:1225-1236` says so wrongly) | `2x` |
| `0x3868` | POPS folder already checked. Set to 1 by the check `FUN_008d8958` itself on entry (`0x8d899c`) and by `main` at `0x87425c` (`SB.` PAK loop success). `main`'s own check at `0x873f9c` is skipped when `gp+0x3888 != 0`. Seven call sites of `FUN_008d8958`: `0x873f9c` (`main`), `0x87e49c` (IGR), `0x87ec38` (OSD), `0x880348` (BIOS), `0x880aac` (TROJAN), `0x881e70` (PATCH), `0x8d4fac` (VMCDIR reader) | `read` for the meaning; callers and stores `1x S32` |
| `0x3460` | the game's folder is missing; skips every later current-game loader. Also set to 1, with `gp+0x38dc`, by `FUN_008d8958` when the POPS folder is missing | `1x`; the folder-check store `2x S30 S31` |
| `0x381c`, `0x38b8` | a one-character suffix after `POPS` in folder names is in use, and the character (`POPS0`..`POPS9`) | `read`; one emulated open with suffix `3` (`1x`) |
| `0x38f0` | game folder name ending in `/` | `2x` |
| `0x3890` | "built-in BIOS integrity": 1 on both PAK load paths; on the `POPS.ELF` path three checks each overwrite it, so only the last (`0x2525b0 == 0x0ff01bfc`) decides | `1x` (two agents ran the same slice with the same result; the critic did not) |
| `0x3438` | preset OSD-off (byte `0x100021`) | `read` |
| `0x3704` | the OSD is currently off (mode 6 was applied) | `2x` |
| `0x38a4`, `0x3b98` | user `BIOS.BIN` loaded: all games, current game | `2x S11` |
| `0x343c` + `0x3430`, `0x3878` + `0x344c` | `OSD.BIN` loaded: all games, current game | `2x` |
| `0x38b0` | quiet: 1 when preset `0x100010` is 0 (MAIN). Most print calls are skipped while it is 1, not all: by the pattern scan of S21, 1,886 of the 2,031 call sites stand behind this test and 145 do not. Two of the 145 are in the BIOS handler (`DONE\n` at `0x8805b4`, `\n` at `0x880984`) and were seen printing with the flag set. An `SB.` launch clears the flag at `0x871634` | `1x` for the meaning and the `SB.` clear; `2x S21 S22` for "not all" (the reviewer's run and S22); the counts are `1x S21` |
| `0x38e0` | once-flag of the current-game loaders: cleared at `0x870c58`; read and then set to 1 at seven places (`0x87ee18` OSD handler, `0x8804ec` BIOS handler, `0x880c90` TROJAN loader, `0x882050` PATCH loader, `0x88348c` in the `CHEATS.TXT` parser, `0x8d5204` in the `VMCDIR.TXT` reader `0x8d4f84`, `0x8d5f04` in the function `0x8d5cf8..0x8d6b70` that builds the `DISCS.TXT` name). In the BIOS handler the first game-scope call sets it and checks that the game folder exists; a missing folder sets `gp+0x3460` and returns -666 | `2x S22` for the BIOS handler (the reviewer's run and S22); `read` for the other six sites (the same `lw`/`sw` pair, not executed here) |
| `0x385c` | auto-patch level from preset `0x10002f` | `read` |

## 4. User BIOS.BIN

Handler `FUN_0088019c(scope, name)`, `0x88019c..0x880a20`; callers
`0x876cd8` (all games) and `0x876fd8` (current game).

| Statement | Label | Host |
|---|---|---|
| Path: `pfs1:/POPS<s>/BIOS.BIN` or `pfs1:/POPS<s>/<game>/BIOS.BIN`; `mass:` instead of `pfs1:` when `gp+0x3448` is 1. One path per call, no fallback. The name is built byte by byte (`0x8803cc..0x880780`), so there is no `BIOS.BIN` file-name string | `2x` (suffix variant `1x`) | yes |
| The game name must end in `/`: called with `GAME` it opens `.../POPS/GAM/BIOS.BIN` | `2x` | yes |
| Only test: signed file size > `0x7ff8e` (minimum 524,175 bytes). No upper limit, no checksum, no content check | `2x S4` | yes |
| Then `read(fd, 0x24bc20, 0x7ff90)`: the file's first `0x7ff90` bytes replace POPS's ROM copy `0x24bc20..0x2cbbb0`. A normal `0x80000`-byte dump loses its last `0x70` bytes | `2x` | yes |
| On accept: flag `gp+0x38a4` (all games) or `gp+0x3b98` (game), and halfword `0x20079a = 0x1000`, which turns POPS's `bnez v0` at `0x200798` into an unconditional branch past its "xCdInit failed" exit | `2x S5 S12` | yes |
| Missing file or too small: return 0, nothing written to POPS and no BIOS flag set | `2x` | yes |
| Both scopes, before the game-folder check: the POPS folder exit (`0x880338..0x880380`). The handler reads `gp+0x3868` and, if it is not 1, calls the POPS folder check `FUN_008d8958` (`jal` at `0x880348`). A result of 1 goes on. Otherwise all games returns -666 (`sw` of 1 to `gp+0x38dc` at `0x880374`, `li v0,-666` at `0x880378`) and the game scope goes on (the scope test at `0x880360..0x880368`). The check itself sets `gp+0x3868 = 1`, and on a missing folder `gp+0x38dc = 1` and `gp+0x3460 = 1` (S32), so after a missing POPS folder a game-scope load still runs while every later current-game loader is skipped. `main` normally makes the same check much earlier (`jal 0x8d8958` at `0x873f9c`, skipped when `gp+0x3888 != 0`) and sets `gp+0x3868`, so in a whole launch this exit is reached only where that earlier check was skipped and `gp+0x3868` was not set otherwise. `main` skips it on `SB.` launches (`gp+0x3888 = 3`) and sets `gp+0x3868` itself at `0x87425c` only when the `SB.` PAK loop succeeds; which launches end up here has not been traced end to end (`read`). OSD, TROJAN and PATCH also call the check and have a `-666` store right after it (S32); their scope handling was not traced | `2x S30 S32` (S30 run here; the reviewer reported it first) | yes |
| Game scope only, before the file is opened: the handler reads the once-flag `gp+0x38e0` (`0x8804ec`). If it is not 1 it sets it to 1 and checks that the game folder exists (`FUN_008d7e78` on `pfs1:`, the stat call `0x91bf80` on `mass:`). A missing folder sets `gp+0x3460 = 1` and returns -666 with nothing opened (`pfs1:` call at `0x880538`, store at `0x880554`, `-666` at `0x880558`; `mass:` call at `0x880570`, store at `0x8805a0`, `-666` at `0x8805a4`). If the flag is already 1 the folder is not checked. So a game-scope call that gets past the gates of the next row always leaves `gp+0x38e0 = 1`, also when the file is missing or too small. A call those gates stop returns 0 before the once-flag is read (the gates are `0x8801b4..0x880334`, the read is `0x8804ec`); the first version of this row said "always" without that condition | `2x S22 S34` (the reviewer's run and S22, both without a gate set; S34 for the gates coming first) | yes |
| Gates inside the handler, in this order, each returning 0 (`0x8801b4..0x880334`, before both exits): any scope `gp+0x38dc`; all games `gp+0x343c`, `gp+0x344c`; game `gp+0x3878`; all games `gp+0x3430`; game `gp+0x344c`, `gp+0x3460`. A game BIOS is not blocked by an all-games OSD, and loads over an all-games BIOS | `2x S34` | yes |
| Extra gate in `main` (`0x876bb4..0x876cd8`, `0x876ea8..0x876fd8`): skipped when any of the eight preset compat slots (`0x100018..0x10001f`) equals 6. They are all 0 in the four profiles, so this never fires there | `1x`; preset values `2x S2` | yes |
| Readers of the two BIOS flags: the shell edits, the eight region groups, the three `$UNDO_` handlers (`0x8948f0`, `0x894d4c`, `0x895088`), `FUN_008db97c` (`0x8db98c`), mode 6 in `FUN_008dc2c4` (`0x8dc75c..0x8dc83c`). The `$RESET_WARMBOOT` pass reads none, so it scans a user BIOS too | `2x S11` | yes |
| With a BIOS flag set, the three `$UNDO_` commands skip their `0x2525b0 = 0x1bfc` write, and mode 6 writes nothing and prints "please delete BIOS.BIN ..." (only on non-quiet profiles) | `1x` (reader sites `2x S11`) | yes |
| There is no integrity check on the user's file. The message "Built-in BIOS integrity check was not passed" belongs to the OSD handler's gate `gp+0x3890` and is about POPS's own ROM copy | `2x` | yes |

launcHER at `cfebe01` had nothing here. Since the merge `0945127` (at
`ef663b2`) it has a loader, described with its evidence in
`docs/POPSTARTER_USER_BIOS.md`; what follows is taken from that document and
from the code, not re-measured by this pass:

- `PopsUserRomState` (`common/include/pops_modes_patches.h`) holds the
  BIOS flags, the OSD words and `osd_off`; `pops_user_bios_stage()` is the
  loader after its open (entry tests, size test, copy of at most `0x7ff90`
  bytes, `0x20079a`, flag); `pops_user_bios_load()` in `handler_pops.c` is
  the file side with a partial read. `pops_stage_user_files()` (called at
  `handler_pops.c:1683`) runs it for both folders, and the shell edits
  (`pops_apply_bios_shell_edits_rom`, `:1714`) and the region pass
  (`pops_apply_region_rom`, `:1722`) now take the flags.
- `tools/test_pops_user_bios.py` compares it with the original under
  Unicorn (with `gp+0x3868 = 1`, so without the POPS folder exit); its
  launch-sequence row is 270 scenarios, 242 equal and 28 differing only at
  `0x2525b0` (that document's difference 2).
- Differences that document lists: the commands run before the files (with
  a look-ahead so the commands see the flags); the order of commands among
  themselves; fix-file bookkeeping; `$NOBOOT`/`$BIOS`; no `gp+0x38dc` or
  `gp+0x3460`; messages to the debug log only; size test on the low 32
  bits; one-byte state. Its folders are the `.VCD`'s folder and
  `<folder>/<name>/`, standing in for `POPS/` and `POPS/<game>/`.
- Not copied: the POPS folder exit above. That document's difference 5
  says `gp+0x38dc` and `gp+0x3460` are not kept, but does not name this
  exit. launcHER keeps no `gp+0x3868`, `gp+0x38dc` or
  `gp+0x3460`, so an all-games `BIOS.BIN` call never returns -666 for a
  missing POPS folder and a missing folder never stops the later
  current-game loaders. Proposed as a quirk entry in this pass's report;
  the quirks file is not edited here.
- Known gap that document records: a built-in entry with compatibility
  modes followed by `$UNDO_COMPATIBILITY_CODES` is refused with `-EINVAL`
  for 294 of 624 entries; the test marks it as an expected failure.

Host tests and Unicorn runs only. NOT TESTED on a console.

Not known: how POPS behaves with a different PS1 BIOS. Console only.

## 5. OSD.BIN (replacement PS1 BIOS shell)

Handler `FUN_0087eb24(scope, name)`, `0x87eb24..0x880198`; callers
`0x876bac` (all games) and `0x876ea0` (current game). ROM base `0x24bc20` is
PS1 `0xbfc00000`; the shell is at `0x263c20`.

No real `OSD.BIN` sample was available. The format is known only from the
handler's checks.

| Statement | Label | Host |
|---|---|---|
| Path: `<dev>:/POPS<s>/OSD.BIN` or `<dev>:/POPS<s>/<game>/OSD.BIN`, `<dev>` as for BIOS.BIN; name built at `0x87ecf8..0x87f07c` | `2x` (suffix `read`) | yes |
| A missing file returns 1 with no writes | `2x` | yes |
| Header `0x40` bytes: magic `PS-X OSD` at 0 (`PS-X EXE` is rejected first); version 1 or 2 at `0x0c`; build id at `0x0e` nonzero; load at `0x10`, entry at `0x14`; 24-bit body size at `0x1c`; label at `0x20`, first byte nonzero; up to four compat modes at `0x38..0x3b`; flag at `0x3c` (version 2 only). File size must equal body size + `0x40` and be at least `0x44` | `2x` for the fields the critic's own file builder used; `1x` for the complete rule list | yes |
| Body cap `0x4c000` (v1, to `0x263c20`) and `0x4d0a0` (v2, to `0x262b80`); one byte more is "too big". Both areas end at `0x2afc20` | `2x` | yes |
| Version 1 needs the low 16 bits of load and entry zero and the high 16 nonzero | `2x` (load rule; entry rule `1x`) | yes |
| Must-be-zero bytes `0x08-0x0b`, `0x0d`, `0x0f`, `0x18-0x1b`, `0x1f`, `0x34-0x37`, `0x3d-0x3f`; check order: EXE magic; size/magic/version nonzero; version 1 or 2; zero bytes; v1 load; v1 entry; size match; too big; build id; label. Every rejection returns 0 and writes nothing | `1x` (the OSD agent's model matched the original on 6,000 of 6,000 seeded cases; the critic did not re-run that) | yes |
| Writes on accept, in order: if `gp+0x3704` is 1, halfword `0x2525b0 = 0x1bfc` and clear the flag; v1: bytes `0x252c30/31` and `0x252c40/41` from the header, zero `0x263c20` for `0x4c000`; v2: rewrite `0x252c28..0x252c4b` (full 32-bit load and entry, `jalr` or, with flag 1, `jr`), zero `0x262b80` for `0x4d0a0`; then the header's compat modes through `FUN_008dc2c4`; then the body; then the flags; then halfword `0x20079a = 0x1000` | `2x` | yes |
| A header mode 6 turns the OSD the file just installed off again (`0x2525b0 = 0x0648`, `gp+0x3704 = 1`) | `2x` | yes |
| Flags: all games `gp+0x343c` and `gp+0x3430`; game `gp+0x3878` and `gp+0x344c` | `2x` | yes |
| Gates: `gp+0x3890 == 0` (prints the integrity message, opens nothing); `gp+0x38dc == 1`; all games with `gp+0x344c == 1`; game with `gp+0x3460 == 1` | `2x` for `gp+0x3890`; rest `1x` | yes |
| The game pass does not look at the all-games OSD flags: a v2 all-games file followed by a v1 game file leaves mixed code and `0x10a0` bytes of the v2 body | `1x` | yes |
| `FUN_008db97c`, mode 6 and the `$UNDO_` handlers read only the BIOS flags, never the OSD ones. Mode 6 after an OSD load still writes `0x2525b0 = 0x0648` | `1x` | yes |
| The v2 code leaves a `jal` in a `jal`'s delay slot (`0x252c34`/`0x252c38`). What POPS's recompiler does with that is unknown | `2x` for the words; behaviour unknown | no |

launcHER: still no OSD loader at `ef663b2`. Since `0945127` the four OSD
words live in `PopsUserRomState` and the shell edits, region pass, mode 6
and `$UNDO_` functions follow them (`docs/POPSTARTER_USER_BIOS.md`
section 4), but nothing sets them in a launch. Wiring points:
`pops_stage_fix_files` and `pops_stage_user_files` (`handler_pops.c`), the
`PopsUserRomState` the launch passes to `pops_apply_bios_shell_edits_rom`
and `pops_apply_region_rom`.

### 5a. What the BIOS and OSD flags change later (shared by sections 4 and 5)

| Statement | Label | Host |
|---|---|---|
| Shell edits `0x878f64..0x878fc4` (`0x263ed6 = 0x20` byte, `0x263d56 = 0x1000` halfword, `0x263db0 = 0` word) are skipped when any of `gp+0x3b98`, `gp+0x38a4`, `gp+0x344c`, `gp+0x3430` is set. `gp+0x343c` or `gp+0x3878` alone do not skip them | `2x` | yes |
| Region pass `0x879034..0x8795f0`, any one of the same four flags set, known licence (`Euro`, `Amer`, `of A`, `Inc.`): only the `0x2649a0` write is skipped. The letters at `0x2cbb72` and `0x20f6cc` are still written, so the region letter goes into a user BIOS | `2x` | yes |
| Same, unknown licence: `0x264994`, `0x264998`, `0x26499c`, `0x2649a0` are skipped, and the four zero bytes at `0x20f6cc`, `0x20f6d8`, `0x20f6dc`, `0x20f6e0` are skipped in every arm where the unflagged run writes them. That includes `$FORCEPAL` together with a PATCH disable-auto. Only `$FORCEPAL` without disable-auto never writes them in the first place | `2x`. An earlier wording, "skipped without FORCEPAL", is wrong and must not be implemented | yes |
| All four flags behave identically in the region pass | `2x` | yes |

The current `docs/POPSTARTER_LAUNCH_HOOKS.md` and the inventory's region
paragraph say only "skipped when a user BIOS/OSD file was loaded"; the table
above is the measured rule.

Two implementation plans disagreed on where the six flags live. Settled by
the merge `0945127`: they are fields of `PopsUserRomState`
(`common/include/pops_modes_patches.h`), and
`tools/test_pops_user_bios.py` compares the shell slice (131 flag
combinations) and the region window (342 cases) with the original under
Unicorn (`docs/POPSTARTER_USER_BIOS.md` section 5; not re-run by this pass
beyond the full host run of section 19). NOT TESTED on a console.

## 6. IGR skin (IGR_BG.TM2, IGR_NO.TM2, IGR_YES.TM2)

Function `FUN_0087e464`, `0x87e464..0x87eb20`, single caller `0x876b18`.

| Statement | Label | Host |
|---|---|---|
| One folder per launch, no fallback, no per-game or VCD-folder lookup: `pfs1:/POPS/` when `gp+0x3448` is 0, `mass:/POPS/` otherwise. These are literal strings; the `POPS<n>` suffix is not applied | `2x` | yes |
| Order BG, NO, YES. Per file: open; size by seek; BG rejected above `0x4c300` bytes, NO and YES rejected from `0x1dbd` (largest accepted 7,612); otherwise the slot is zeroed, the file read into it, and the rest zero | `2x S7` | yes |
| Slots: BG `0x2feff0`, `0x4c300` bytes; NO `0x34b2f0` and YES `0x34d0b0`, `0x1dc0` bytes each. These hold Sony's own TIM2 files in `POPS.ELF`, and the limits equal Sony's file sizes | `2x S9` | yes |
| The file is copied raw. No TIM2 check of any kind. A zero-length file is accepted and wipes Sony's image | `2x` | yes |
| Nothing else in POPS changes. No file outcome (missing, too big, accepted) is an error: once past its two entry tests the function returns 1 | `2x S23` | yes |
| Two other return values exist. With `gp+0x38dc` equal to 1 the function returns 0 at once and opens nothing (`0x87e474..0x87e488`). With `gp+0x3868` not 1 it first runs the POPS folder check `FUN_008d8958` (`jal` at `0x87e49c`); a result other than 1 sets the abort flag `gp+0x38dc = 1` and returns -666 (`0x87e4bc`), again opening nothing (`0x87e48c..0x87e4c4`). At that call the check returns only 1 or -666, because the function has just tested `gp+0x38dc` and `gp+0x3868` itself. The check also writes: `gp+0x3868 = 1` on every call that gets that far, and on a missing folder `gp+0x3460 = 1` (which skips every later current-game loader) as well as `gp+0x38dc = 1`. On `mass:` a failed stat of `mass:/POPS` is followed by a call of `0x91be68` on `mass0:/POPS`. The first version of this row said only "the function returns 1"; the second did not list the extra writes | return 0: `2x S23` (the reviewer's run and S23). The -666 path and the writes: `2x S31 S32` (S31 with the check executed; the reviewer's second review first). Whether `gp+0x3868` can still be 0 when `main` reaches the call: `main` sets it through its own check at `0x873f9c` (skipped when `gp+0x3888 != 0`) and at `0x87425c` (`SB.` PAK loop success); not traced end to end (`read`) | yes |
| `main` does not use the return value. It tests `gp+0x38dc` before the call (`0x876a84`) and reads it again after (`0x876b20`), so the function's own `gp+0x38dc` test repeats one that `main` has just made | `read S24` | yes |
| Gates: preset byte `0x10002d` must be 1 (it is in all four profiles) and `gp+0x38dc` must be 0. Both are tested in `main` before the call (`0x876a84..0x876a98`); the function itself repeats only the `gp+0x38dc` test, and called directly with the preset byte 0 or 2 it still opens the three files | preset values `2x S2`; where the tests sit `read S24`, `1x S23` | yes |
| The skin loads before any config file is parsed, so `$IGRn` and `$NOIGR` do not affect loading | `read` | yes |
| POPS re-uploads the three files from those addresses on each frame the dialog is shown (`0x226768`, `0x226d60`); it reads picture count, header size, width, height and type from the file and never compares the `TIM2` magic. With a wiped slot it takes an "Illegal image no." path with no NULL check | `read` | no |
| A negative seek result is not rejected and would make the second zero fill start below the slot | `read`, not executed; do not copy | yes |
| The three `IGR_*.TM2` files are not the only way these pictures change. One fix file in the community corpus, a `PATCH_5.BIN` of 327,360 bytes, carries a 327,296-byte payload for `0x2feff0..0x34ee70`, which is exactly the three slots. The original's PATCH loader writes it there, and so does launcHER's `pops_fix_stage` today (same bytes) | `2x S27` (the reviewer's census and S27) | yes |
| In the original the skin call (`0x876b18`) comes before both PATCH passes (`0x876e00`, `0x877118`), so such a PATCH file overwrites whatever the skin loader put there | `inferred` from the call-site order (`2x S6`) and the row above; the two were not run in sequence | yes |

launcHER at `cfebe01` had no skin code (S17). Since the merge `173d5de` (at
`ef663b2`) `launchPOPS` calls `pops_stage_igr_skin` (`handler_pops.c:1657`)
after the built-in entry; `docs/POPSTARTER_IGR_SKIN.md` describes it and
`tools/test_pops_igr_skin.py` (48 tests, 141 runs of the original under
Unicorn with `gp+0x3868 = 1`) compares it. What this pass read in the code,
not measured further:

- It reads the three files from the `.VCD`'s folder (`vcdDir`), not from
  `POPS/`; it has no `gp+0x38dc` gate and no -666 path (no POPS folder
  check), and no return value the launch looks at.
- Its place after the built-in entry and before the fix files keeps the
  original's order against `PATCH_n.BIN` (a `PATCH` file still overwrites
  the slots).
- A skin is visible only under `$IGR0..2`, because of the default described
  next.
- The POPS folder exit above is not copied; that document lists this
  among its differences, but not the check's writes of `gp+0x3460` and
  `gp+0x3868`, and the quirks file has no entry for it. A quirk entry is
  proposed in this pass's report.

Before this audit README.md and `docs/pops-setup.html` told users to place
these files beside the game; the first pass corrected both to "not
supported". With the merge that correction is out of date again: the
report of this pass proposes the new text (those two files are not edited
here). Host tests and Unicorn runs only. NOT TESTED on a console.

## 7. The default IGR (no `$IGR` command)

| Statement | Label | Host |
|---|---|---|
| The original writes nothing at `0x228a20..0x228a68` without a command. Sony's combo test (mask `0x0904` at `0x228a20`/`0x228a50`) and Sony's yes/no dialog stay as shipped | `read S5 S14` (the command table shows only `$IGR0..5`/`$NOIGR` writing there; that no other code path writes there was not exhaustively proven) | yes |
| The original's IGR exit fix (`0x20c0a4 = jal 0x2362b8`) is applied when preset byte `0x100024` is 1, which it is in all four profiles | `read`; preset value `2x S2` | yes |
| After YES the original leaves through its exit program at `0x1450000` (`j 0x1450000` written at `0x2362fc`) | `read` | no |
| launcHER, with no command, rewrites `0x228a5c..0x228a68` to `li v0,1` / `b 0x228ab8` / `nop` / `nop` (`common/src/pops_modes_patches.c:1279-1299`, called from `:1549-1557`). The mask stays `0x0904`; the dialog is never opened | `read S17` | yes |
| launcHER does not copy the exit program and leaves `0x2362fc` pristine. Sony's dialog followed by YES under launcHER's own exit has never been run on a console. The direct exit has (owner, Tekken) | `read` | no |
| Mask `0x0904` means SELECT+START+L1 under the standard PS1 pad bit layout | `inferred`, not observed | no |

Gap: a deliberate launcHER difference, confirmed by the owner on hardware.
Changing it is an owner decision, not a bug fix.

## 8. Physical PS1 disc

It is not a mode anyone selects. It is what the original does when no VCD
is found.

| Statement | Label | Host |
|---|---|---|
| Flag `gp+0x3410` is set to 1 when the VCD probes for the launch type fail: `0x8756a4`, `0x875734` (types 1/2), `0x875d98` (type 0), `0x876690` (type 3). It is cleared at `0x870bc8` and after each "FOUND" (`0x875780`, `0x875d1c`, `0x875f24`, `0x876254`, `0x8763d0`). Readers: `0x8766fc`, `0x8774c4`, `0x878ab4`, `0x878c78`, `0x8d5d24`, `0x8d5d90`, `0x8ff12c`, `0x8ff24c` | `2x S11` | yes |
| No name prefix, argument or `cdrom0:` path selects it. Launching POPStarter itself from a path beginning `cdrom` exits at once (section 10) | `2x S10` | yes |
| Block `0x8766fc..0x876a40`, in order: scan IOP modules for a name starting `cdvd_`; if none, load `rom0:CDVDMAN` and `rom0:CDVDFSV`; `sceCdInit(1)`; status; disc type; read LBA 4; copy the 4 region letters from data offset `0x3c` | `2x` (callees modelled) | yes |
| Status 1 is fatal ("Cannot access (1)!"). A disc type outside `0x10..0x13` is fatal ("NO PS1 CDROM!"). PS2 CD types `0x12`/`0x13` are accepted | `2x` | yes |
| POPS writes: `0x200794 = 0x0000202d` (Sony's disc init is called with NULL instead of a path); in the original's own always-live block `0x2328bc = 0x0000202d`, `0x2328c8 = 0x1000001f`, `0x2328cc = 0`, and `0x2328d0..0x232943` zeroed (lid close re-inits with NULL; the four D-pad disc selections are removed) | `2x S5` | yes |
| Disc types `0x11`/`0x13` also get the three `$MUTE_CDDA` writes (`0x20f0b6`, `0x20ebf2`, `0x20f0e0`). Why is not known | `2x` | yes |
| Later: built-in fingerprint from 2,048-byte sectors 16 and 22 (`0x8ff24c..0x8ff338`), equal to VCD offsets `0x109340`/`0x109640`/`0x10ca70`; `sceCdInit(5)` at `0x8774d4`; `DISCS.TXT` skipped with three messages (`0x8d5d24`); POPS's name buffer `0x4f8000` zeroed (`0x878c88`) | `read` | yes |
| In game, reads are Sony's: POPS's embedded IOPCD in real mode calls cdvdman (`sceCdRead` in 2,340-byte mode, ordinal 76 for audio). The cdvdman it imports comes from the IOPRP image POPS reboots with | `1x` for the IOPCD call sequence (modelled imports; the critic did not re-run it); `inferred` that the post-reset IOP loads those modules | no |
| REPOP's four `POPSTARTER_CD_*_CONTRACT` documents cover the original's statically linked EE libcdvd. Its only callers are this probe and the fingerprint (`0x8767a8..0x876868`, `0x8774d4`, `0x8ff26c..0x8ff30c`), none in game | `2x` for the `sceCdRead` callers, `1x` for the rest | yes |

launcHER: no such path. `launchPOPS` returns `-ENOENT` at "Cannot open
target VCD" (`handler_pops.c:824`); `isPopsTarget` (`:50`) requires `.vcd`;
nothing patches `0x200794` (S17); the resident lid close always passes a
disc slot (`common/src/pops_resident_engine.c:340`).
`launcher/src/handler_cdrom.c` is a separate PS1DRV/DKWDRV disc booter and
is unrelated.

Since the merge `f22a69f` (at `ef663b2`), `common/src/pops_physical_disc.c`
holds the host part, described in `docs/POPSTARTER_PHYSICAL_DISC.md`: the
probe's decision (`pops_physical_disc_plan`), the four core writes
(`pops_physical_disc_stage`, which checks Sony's values first), the name
clear and the sector fingerprint. The file is built into the launcher, but
nothing in `launcher/` calls these functions, so a launch still needs a VCD
and the paragraph above still holds. That document's "Not done" list
(drive access and a launch path, the resident part, `DISCS.TXT`,
`sceCdInit(5)`, POPS's own disc layer) is unchanged by this pass. The
merge has not been reviewed. Host tests only; NOT TESTED on a console.

Gap: the whole feature, plus a product decision (how is a physical launch
requested when launcHER's target is a `.vcd` path), plus threading an
optional VCD through about 1,100 lines of `launchPOPS`. Drive reads, CDDA
and disc-type detection need a console or a whole-machine emulator with a
PS1 image mounted.

## 9. $USBDELAY and the preset block 0x100008..0x10002f

### `$USBDELAY_n`

| Statement | Label | Host |
|---|---|---|
| Handler `0x89dbe0` (S25): `$USBDELAY_` + exactly one digit + a terminator, then byte `0x100017` = digit | `2x S14` for the write; the exact terminator set (NUL, CR, LF, space, `$`) `1x` each from two agents, not re-derived by the critic | yes |
| `$USBDELAY_12` and `$USBDELAY5` are not commands in the original | `1x` | yes |
| Shipped default of byte `0x100017` is 1 in all four profiles | `2x S2` | yes |
| Only consumer: `0x879d04..0x879e58`. Only when `gp+0x3448 != 0` (`XX.` or `SB.`) it replaces the bytes `DLAY` in the embedded PFS wrapper image (image `0x91f680`, the word at `0x91fb30`) with that byte and three zeros | `2x S3 S13` | yes |
| The wrapper (IRX `.text` 0, one caller at `.text` `0x124`) on its first use reads that word, substitutes 5 if it still says `DLAY`, multiplies by 1,000,000 and calls one import once | `2x` for the arithmetic and the first-use flag | partly |
| That import is `thbase` number 33. It is called from device-table entry 3 only, once, on that entry's first call, before the wrapper's own backend open, with n x 1,000,000 as its argument (5,000,000 if the word still reads `DLAY`). Later calls of entry 3 and the read, seek and close entries do not call it | `1x S28`: the wrapper's code run on a host under Unicorn with its imports modelled (unpatched, n = 0..9, and one sequence with other entries first). Not an IOP kernel, not a console | yes |
| `thbase` 33 is `DelayThread` with an argument in microseconds, and device-table entry 3 is `open` | `inferred` from the PS2SDK import numbering and the ioman device-table layout. The in-repo `tools/trace_original_pops_io.py` makes the same two assumptions (it routes Sony's `ioman` open to entry 3 and models `thbase` 33 as `DelayThread`) | no |
| So: a one-time delay of n seconds on the IOP at the wrapper's first open, 1 second with no command, on `XX.`/`SB.` launches only | `inferred` from the rows above. Nobody has observed the wait itself: no IOP kernel was involved in any run | no |

launcHER at `cfebe01`: `$USBDELAY_<any digits>` and `$USBDELAY<digits>`
accepted (S19). Since the merge `95ba812` (at `ef663b2`) the parser takes
exactly one digit and a terminator, as the original (`CMD_USBDELAY` in
`common/src/pops_config.c`; `tools/test_pops_config_text.py`). Unchanged:
the default is 0 where the original's byte is 1, and `handler_pops.c:1985`
does `sleep(cfg.usb_delay)` on the EE, after the module loads, on any
device. Nothing in `launcher/iop/popfs` delays.

Gap: the default; where and when the delay runs (needs a console or
emulator run to call working). The first review of `95ba812` has open
findings; the answers are in progress on a side branch, so this paragraph
states only the merged code.

### A second, separate USB delay

Preset byte `0x100013` (2 in MAIN and DEBUG, 6 in USBDELAY and
USBDELAY_DEBUG), shifted left 24, is the count of an EE busy loop
(`FUN_00870930`) run after the USB drivers start: at `0x8721c4` before the
IOP reset (`XX.` only) and at `0x87add8` after it (`1x`; values `2x S2`).
Its wall-clock length is unknown. launcHER has no equivalent. Whether to
copy a CPU-speed loop is an owner decision.

### The preset block

Forty bytes inside POPSTARTER.ELF's own segment at `0x100008..0x10002f`
(file offsets `0x408..0x42f`), read at `0x870bd0..0x871324`. The four
profiles differ only at `0x100010` and `0x100013` (`2x S2`). The "Gates"
column is `read` throughout, and for most rows it comes from the banner
text of the function the byte gates, not from reading that function.

| Byte | MAIN | Gates | Note |
|---|---|---|---|
| `0x100008` | 0 | `gp+0x3884` | effect not identified |
| `0x100009` | 0 | `gp+0x38c4`, the flag `$ORIGINAL_OPCODES` sets | |
| `0x10000c` | 0 | `gp+0x3818`; 1 calls `0x91aaa0(8, 0x80000280)` | effect not identified |
| `0x100010` | 0 | debug output: 0 quiet (`gp+0x38b0 = 1`), `0xff` unpaced, else paced | `0xff` in the DEBUG profiles |
| `0x100011` | 0 | halt on error (read in the fatal handler at `0x870b44`) | |
| `0x100012` | 0 | the two `$HDTVFIX` words at `0x23acb0`/`0x23ad0c` | |
| `0x100013` | 2 | USB busy-wait count, see above | 6 in the USBDELAY profiles |
| `0x100014` | `0x40` | stored to a frame slot | no reader found: unused (`inferred`) |
| `0x100015` | 0 | VMC user digit `'0'..'9'` in the SLOT name block `0x874e00..0x8750ac` | the digit variant may drop the game name's trailing slash (`inferred`, never run) |
| `0x100016` | 3 | stored to a frame slot | no reader found: unused (`inferred`) |
| `0x100017` | 1 | `$USBDELAY` seconds, see above | |
| `0x100018..0x10001f` | 0 | eight forced compatibility mode numbers, each passed to `FUN_008dc2c4` | each byte is a mode number, not a boolean |
| `0x100020` | 1 | not mass mode: `FUN_008db778` ("genuine HDD check") | |
| `0x100021` | 0 | `gp+0x3438`, `FUN_008db97c` (OSD off) | |
| `0x100022` | 1 | `FUN_008dbafc` | |
| `0x100023` | 1 | `FUN_008dbcdc`, else `FUN_008dbd6c` | |
| `0x100024` | 1 | `FUN_008dbe08` (IGR exit fix) | |
| `0x100025` | 1 | mass mode only: `FUN_008dbee4` | |
| `0x100026` | 1 | mass mode only: `FUN_008dbf58` | |
| `0x100027` | 1 | `FUN_008dbfd4` | |
| `0x100028` | 1 | `FUN_008dc0c0` | |
| `0x100029` | 0 | nonzero: `FUN_008dc12c(value)` (card count) | |
| `0x10002a` | 1 | video: 1 sets `gp+0x4fa0`; 2 sets the `$480p` flags and pokes | |
| `0x10002b` | 1 | `MODULE_n.IRX` loader; forced to 1 on `SB.` at `0x871610` | |
| `0x10002c` | 1 | `FUN_008dbe78` | |
| `0x10002d` | 1 | IGR skin (section 6) | |
| `0x10002e` | 1 | `FUN_008dba90` (`0x263ca8 = 0`) unless `gp+0x3438` is 1 | |
| `0x10002f` | 3 | `gp+0x385c`, auto-patch level; 4 is "TEST MODE" | |

launcHER: `pops_config_load_table` / `pops_config_export_table`
(`common/src/pops_config.c`) describe a 32-byte table with a
different mapping (`table[3]` as `$USBDELAY`, where the original has the
busy-wait there and `$USBDELAY` at index 7; `table[8+i]` as booleans; a
default starting `0xff`, which is the DEBUG value). Nothing in `launcher/`
calls them; only `tools/test_pops_features.py` does (S17). Whether launcHER
applies exactly the set of core patches the MAIN presets select was claimed
by older launcHER documents and not re-checked in this audit.

## 10. Launch type, argv rules and device paths

Almost everything here is `read` from flow dumps and byte-store chains, and
part of it from REPOP's superseded Ghidra export used as a lead. Only the
`XX.` scan was run. Treat this section as the least certain one.

| Statement | Label | Host |
|---|---|---|
| `argc == 0`, or `argv[0]` beginning `cdrom`: Exit (syscall 4) | `2x S10` (static both times) | yes |
| `SB.`/`XX.` scan (`0x8714b8..0x8719c4`): index from the end down to 1; a `:`, `/` or `\` must stand before the three characters; `XX.` or `xx.` exactly, mixed case does not match; any path component qualifies, not only the file name; a bare name with no separator never matches | `2x` for `XX.` (12 strings emulated by the critic). The `SB.` half and `gp+0x3888 = 3` are `read` only: the critic's harness crashed on `SB.` inputs because that path runs extra debug code at `0x871624..0x8716c4` | yes |
| Launch type `gp+0x3414` (`FUN_008d8db8`, `0x8d8db8..0x8db770`, 10,688 bytes): 1 for `hdd0:...:PATINFO` or `hdd0:...:pfs:/` with `LAUNCHER.ELF`/`.KELF` or `EXECUTE.ELF`/`.KELF`; 2 for `:pfs:/PP.` or `:pfs:/__.`, or a non-`hdd0` path with `/PP.` or `/__.`; 3 for mass mode; else 0 | `read`, never executed | yes |
| The "was not renamed" messages fire only when `argv[0]` is not on `hdd0:` (or in mass mode) and names `LAUNCHER`/`EXECUTE` `.ELF`/`.KELF` after a separator. From `hdd0:...:pfs:/LAUNCHER.ELF` the same names select type 1 with no message. On MAIN no message is ever shown (quiet) | `read` | yes |
| Types 1 and 2 mount `hdd0:<partition>` on `pfs0` and open `pfs0:IMAGE0.VCD` (`0x87551c`, `0x8754e0..0x875780`) | `read` | yes |
| Type 0 mounts `hdd0:__.POPS` and opens `pfs0:<ELF base name>.VCD`; on failure it retries ten times, incrementing one byte of the partition name (`0x875d94..0x875fa4`). The names `__.POPS0`..`__.POPS9` are `inferred` from the byte writes | `read` / `inferred` | yes |
| Type 3 opens `mass:/POPS/<name>.VCD`, then `mass:/POPS0/`..`mass:/POPS9/` (`0x8762cc..0x876690`); the loop also patches a path inside the PFS wrapper image with the folder found. Nobody decoded that loop or what the wrapper then serves | `read`, partly undecoded | yes |
| Name length: `<folder>/<name>.VCD` reaching 80 characters is fatal ("Please shorten ...", `0x875a34..0x875aa8`) | `read` | yes |
| On HDD, everything except the VCD comes from `hdd0:__common` mounted as `pfs1` (`FUN_008d8b14`, string xref `0x8d8b68`): `pfs1:/POPS/POPS.ELF`, the IOPRP image, `MODULE_n.IRX`, the IGR skin, `OSD.BIN`, `BIOS.BIN`, fix files, `CHEATS.TXT`, `VMCDIR.TXT`, `DISCS.TXT`, and the per-game folder `pfs1:/POPS/<title>/` with `SLOT%d.VMC`. The mount itself was read, not traced | `read` (paths for IGR/OSD/BIOS `2x`) | partly |
| A failed `__common` mount is fatal ("Please create a __common partition manually...", `0x873f64`) | `read` | no |
| POPS package (`FUN_0087cf68`, 5,240 bytes, caller `0x8743d8`): `XX.`/`SB.` try `mass:/POPS/POPS_IOX.PAK` (exactly `0xe50b8` bytes), then on USB only `POPS.PAK` (`0xe6240`), then `POPS.ELF` (`0x30530c`) with `IOPRP252.IMG` or `IOPRP.IMG`; `SB.` fails without the IOX pack; HDD uses only `pfs1:/POPS/POPS.ELF` with `IOPRP252.IMG` or `IOPRP.IMG`. There is no `pfs1` variant of either PAK | `read` from a superseded decompile plus strings; not emulated. Its identity checks (`305_`, `/kHn`, ` 4.5`) and failure handling are unmeasured | yes |
| On HDD launches the VMC step (`FUN_008d8050`, branch at `0x8d8738`) creates the game folder if missing and writes `icon.sys` and `list.ico` into it when they are absent (xrefs `0x8d87cc`, `0x8d8848`; icon data at `0x9639b4`) | `read`; only the tail of the function was examined | partly |
| The inventory's statement that SLOT VMC pre-creation is `XX.`/`SB.` only has not been checked against that HDD branch | open | yes |

Paths the original opens, assembled from the rows above and sections 4 to 6:

| File | HDD | `XX.` / `SB.` | Builder |
|---|---|---|---|
| VCD, types 1/2 | `pfs0:IMAGE0.VCD` in `hdd0:<partition>` | n/a | `0x87551c` |
| VCD, type 0 | `pfs0:<name>.VCD` in `hdd0:__.POPS`, then ten retries | n/a | `0x875ac4` |
| VCD, type 3 | n/a | `mass:/POPS/<name>.VCD`, then `POPS0..9` | `0x875fbc` |
| POPS package | `pfs1:/POPS/POPS.ELF` + IOPRP | `mass:/POPS/` PAK or ELF + IOPRP | `FUN_0087cf68` |
| `IGR_*.TM2` | `pfs1:/POPS/` | `mass:/POPS/` | `0x87e4c8` (literal) |
| `OSD.BIN` | `pfs1:/POPS<s>/[<game>/]` | `mass:/POPS<s>/[<game>/]` | `0x87ecf8` |
| `BIOS.BIN` | same | same | `0x8803cc` |
| `TROJAN_n.BIN` | same | same | `0x880b60` |
| `PATCH_n.BIN` | same | same | `0x881f24` |
| `CHEATS.TXT` | same | same | `0x883360` |
| `VMCDIR.TXT` | same | same | `0x8d50d8` |
| `DISCS.TXT` | same | same | `0x8d5dd8` |
| `MODULE_n.IRX` | `pfs1:/POPS/` | `mass:/POPS/` | strings |
| `SLOT%d.VMC` | `pfs1:/POPS/<title>/` | `mass:/POPS<s>/<title>/` (`read`) | `0x874d78` |
| SMB files, USB pair | `mc0:/POPSTARTER/`, then `mc1:` | same | `0x871d68..0x873c40` |

`<s>` is the optional `POPS0..9` digit. No report produced this table from
one measurement; a tool that records every open for backend x scope x
suffix is increment 3 in section 16.

launcHER:

- Prefix test `extract_base_name` (`common/src/launch_args.c:93-122`): only
  the last path component, any case mix per letter, and a bare name with no
  separator matches. Differs from the original in all three (`read S17`).
- Title buffer `baseTitle[64]` (`launch_args.c:549`): a long title is cut to
  63 characters where the original stops with a message (`read`).
- Candidates use `IMAGE.VCD` (`launch_args.c:633-770`); there is no
  `IMAGE0.VCD` launch candidate (the name appears only as a popfs alias,
  `launcher/iop/popfs/src/popfs.c:110-127`), no `POPS0..9` and no
  `__.POPS0..9` (S17 grep).
- No `__common` anywhere in `common/` or `launcher/` C sources (S17 grep).
  All per-game files are looked up relative to the VCD's own folder
  (`vcdDir`, `gameConfigDir`, `handler_pops.c:870-884`). On USB/SMB with the
  VCD in the POPS folder that is the same folder as the original's. On HDD
  it is not. Nobody has compared the HDD locations file by file.
- POPS package search (`handler_pops.c:114-196`): per folder
  `POPS_IOX.PAK`, `POPS.PAK`, `POPS.ELF` + `IOPRP252.IMG`. There is no
  `IOPRP.IMG` fallback (S17 grep). Folders: the VCD's, `<dev>:/POPS/`,
  `mc0:`/`mc1:` `POPSTARTER/` and `POPS/`, `hdd0:__.POPS:pfs:/`,
  `usb0:`/`usb1:`/`mass:`/`mass0:` `/POPS/`, and at `:153` a leftover test
  folder `ata0:/LAUNCHER-TEST-20261013-A/` in the production list.
- Packages are accepted by SHA-256 (`common/src/pops_profile.c`), not by
  the original's size and signature checks.
- `hdd0:...:PATINFO` goes to launcHER's generic PATINFO handler
  (`launcher/src/main.c`), not to a type 1 POPS launch.
- No `icon.sys`/`list.ico` writer for POPS; no rename messages; no `cdrom`
  exit.

## 11. SMB: configuration files and module set

Everything in this section comes from the one report the critic did not
see. Nothing was run on a console.

| Statement | Label | Host |
|---|---|---|
| `SB.` pre-reset sequence (`0x8721cc..0x873f00`): built-in iomanx and filexio; `IPCONFIG.DAT`; `SMBCONFIG.DAT`; `poweroff.irx`; `ps2dev9.irx`; `smsutils.irx` (optional); `ps2ip.irx`; `ps2smap.irx` (gets the IPCONFIG arguments); `smbman.irx`. Each is `mc0:/POPSTARTER/<name>`, else `mc1:`. A missing required file or a start result <= 0 is fatal | `read` | partly |
| `smbman.irx` is patched in RAM before it starts: every 4-aligned `smb\0SMB\0` becomes `mass\0\0\0\0`, so the share is the device `mass` (`0x873ce0..0x873eb4`) | `read` | yes |
| `IPCONFIG.DAT`: optional; size 7..127 or fatal; fewer than two separators (space, CR, LF; TAB is not one) is "SYNTAX ERROR !"; separators become NUL; the argument length passed on is the count of non-separator bytes, so a three-address line is passed short by its two separators | `1x` | yes |
| `SMBCONFIG.DAT`: required; size 7..4095; line 1 `server[:port] share[:sharepassword]` split at the first space of the whole file; port 1..5 digits, at most 65535, 0 allowed; user and password only when two LFs are each followed by a non-NUL byte, otherwise the user stays `POPStarter`; no IPv4 validation; a server token of up to 21 characters is copied into a 16-byte field | `1x` (34 texts) | yes |
| Connect (`0x874128..0x874268`): devctl on `mass0:` LOGON, ECHO, OPENSHARE, then up to 120 opens of `mass:/POPS/POPS_IOX.PAK` | `read` | no |
| In `SB.` mode it also buffers optional `mass:/POPS/iomanx.irx` and `mass:/POPS/filexio.irx` from the share (`0x877564..0x8777c4`) | `read` | no |
| The post-reset SMB sequence (`0x87b648..0x87b9ac`) was only skimmed | open | no |

launcHER: embedded network modules; `IPCONFIG.DAT` required
(`launcher/src/handler_smb.c:52-54`); `SMBCONFIG.DAT` read into a 1,024-byte
buffer (`:65-70`); LOGON then OPENSHARE on `smb:` with no ECHO (`:87-89`);
its own parser `launcher_parse_smb_config`
(`common/src/network_config.c:37`). Run on 20 probe texts against the
original's parser, 12 gave a different result (`1x`): launcHER rejects the
share-password form, port 0, a non-IPv4 server, `/` in the share and extra
lines, canonicalises the IP, trims the share, and treats a two-line file as
a named user where the original stays guest.

That paragraph is launcHER at `cfebe01`, and it is still what every SMB
launch except one kind does at `ef663b2`. Since the merge `21c3476` a launch
whose target is a PS1 disc image and whose name carries `SB.` takes the
original's rules instead: `common/src/pops_smb_config.c` (parsers for both
files, defaults, the echo request, the file lookup), switched in by
`sb_rules()` in `launcher/src/handler_smb.c`; `IPCONFIG.DAT` is optional;
LOGON, ECHO, OPENSHARE in that order; `mc0:`/`mc1:` `POPSTARTER/` first,
launcHER's own places after. `docs/POPSTARTER_SMB_CONFIG.md` lists what is
copied, what is not (values that would leave a structure are refused,
launcHER's modules and `smb:` device, no 119-try loop, launcHER's own `SB.`
test, and others) and the evidence (host tests and the original's code
under Unicorn, `tools/test_pops_smb_config.py`). The merge has not been
reviewed; this pass did not re-measure it. NOT TESTED on a console.

Gap: the external IRX set, the `mass` rename, the connect loop and the
original's `SB.` test (section 10) are still not copied; they need a console
or a decision.

## 12. TROJAN_n.BIN / PATCH_n.BIN

Loaders `FUN_00880a24` (TROJAN) and `FUN_00881de8` (PATCH); callers in
section 3.

**State at `ef663b2`.** The launcHER side of this section is unchanged by
the merged code: the rows below still describe it. Work on TROJAN files is
in progress on a side branch; this document does not anticipate its
outcome. The corpus counts and the ten hook slots were re-counted by this
pass from the corpus headers (S15 numbers again: 3,952 / 509 TROJAN,
870 / 10 PATCH, one hook per file number), and
`tools/test_pops_doc_claims.py` now checks them when `POPS_TROJAN_CORPUS`
is set.

### Corpus result (the largest gap found)

The corpus is every `TROJAN_n.BIN` and `PATCH_n.BIN` under REPOP
`popstarter/` (community fix packs). It shows what exists in the wild; it
is not exhaustive.

| Statement | Label |
|---|---|
| 3,952 TROJAN files, 509 unique by content; 870 PATCH files, 10 unique | `2x S15` |
| All 509 unique TROJANs load outside the POPS core image: load addresses `0x1431000..0x1470300`, payloads 48 to 770,240 bytes, highest end `0x152c3c0`. 507 are format 1; 2 are format 3 with header byte `0x0a` = 6 | `2x S15` |
| Each hooks one of ten fixed call slots, one per file number: 0 `0x2327d8`, 1 `0x2327e0`, 2 `0x2327e8`, 3 `0x2327f0`, 4 `0x232d08`, 5 `0x232d10`, 6 `0x232d18`, 7 `0x2327d0`, 8 `0x232d20`, 9 `0x232d28`. These are inside the original's own always-live block (copied to `0x232790`), not in Sony's code. Each slot is a `b +8` / `nop` pair that the loader turns into `jal entry`. The block holds 60 such pairs (5 at `0x2327d0..0x2327f0`, 55 at `0x232d08..0x232eb8`); the corpus uses these ten. Whether the loader would accept a hook address other than these ten was not examined | `2x S15` for the header values; `2x S27` for the slot word before and after; `1x S26` for the count of 60 |
| launcHER's `pops_fix_stage` returns `POPS_FILE_RANGE` (-3) for all 509, and 0 for all 10 PATCH files | `2x S16` |
| The original's loader accepts all 509 TROJANs and all 10 PATCH files | `2x S27`. Three host runs with three separate harnesses agree: the mapping agent's (a scratch extension of the in-repo R5900 interpreter), the reviewer's (Unicorn, 509 of 509 and 10 of 10 as reported by the review) and S27 (Unicorn). The first version of this row said "measured once". In all three the file calls are models, and no payload was executed |
| The PATCH files launcHER accepts change the same bytes as in the original: for each of the 10 unique corpus PATCH files, the set of changed core bytes and their values are equal | `1x S27` |
| In launcHER a rejected fix file ends the launch: `pops_stage_fix_files` returns on any nonzero result (`handler_pops.c:316-318`, `:1456-1457`). The original prints "Invalid" or "Skipped (outdated)", closes the file and goes on to the next slot | `read S17` for launcHER; `read` plus probe runs (`1x`) for the original |

Taken together: with a real-world TROJAN file in the game's folder (or in
the folder beside the games), a launcHER launch stops with "Fix file
rejected", where POPStarter applies the file. Measured on a host; NOT TESTED
on a console.

Where the -3 comes from (`read`, lines checked for this document): the
header parser itself takes these files. `pops_fix_stage` plans every fix
file against the staged core only
(`common/src/pops_modes_patches.c:387-388`, base `0x200000`, span the core
size), and `window_offset` (`common/src/pops_external.c:138-144`) returns
`POPS_FILE_RANGE` for a load address outside that window. The hook slots
are inside the window; the payloads are not. The manual corpus check in
`tools/test_pops_external.py` (`check_corpus`, the `--corpus-root` option,
not part of the normal test run and not run for this document) plans the
same files against `0x100000..0x2000000` instead, which is why the older
"corpus passes" notes in `POPSTARTER_REPLACEMENT.md` and this result do not
contradict each other: that check exercises the parser, not the launch
path.

launcHER has no counterpart for the slots: the comment at
`common/src/pops_resident_engine.c:314-316` says the five at
`0x2327d0..0x2327f0` "do nothing in r13". They do nothing only while no
TROJAN is installed.

Not examined: whether corpus payloads depend on POPStarter state beyond
being called from a slot (registers, its resident data, its code at
`0x143xxxx`/`0x146xxxx`). Some load at `0x1431000..0x1433fff`, next to
launcHER's resident base `0x0143a000`; one ends at `0x152c3c0`. `TROJAN_4`
hooks `0x232d08`, the slot the built-in breakpoint handler and
`$BREAKPOINT` also use; precedence in the original was not traced.

### Rule differences (all `1x`, from the same report, synthetic headers)

| Case | Original | launcHER |
|---|---|---|
| PATCH format byte (`hdr[0x0c]`) 2 or 3 | Invalid | rejected: launcHER's format-1-only rule for PATCH is correct |
| TROJAN formats 1, 2, 3 | accepted; format 2 with `hdr[0x0a]` 1/2/3 writes `j entry` plus 0/4/8 zero bytes, otherwise `jal entry` | the header parser takes flag words `0x00010001`, `0x00010002`, `0x00010003` and builds the `j` form for format 2 (`pops_external.c:104-106`, `:162-169`; `read`); not compared with the original case by case |
| TROJAN `hdr[0x0e]` = 2 | accepted | -2 |
| TROJAN entry outside the payload | accepted | -3 |
| TROJAN payload size not a multiple of 4 | accepted | -1 |
| TROJAN or PATCH payload outside `0x200000..0x502e60` | accepted | -3 |
| PATCH nonzero bytes at `0x18..0x1b` | accepted (ignored) | -2 |
| Config-only PATCH with a nonzero load address | accepted (ignored) | -1 |
| Format-3 TROJAN with `hdr[0x0a]` < 6 while a built-in entry is active (`gp+0x38d8 != 0`, `gp+0x345c = 6`) | Skipped (outdated) | applied |
| Folders | `<dev>:/POPS[n]/` and `<dev>:/POPS[n]/<title>/` | the VCD's folder and `<vcdDir><gameBase>/` (`handler_pops.c:299-307`) |

Existing coverage that still stands: `tools/test_pops_fix_files.py` matches
the original on 100 ordered sequences of PATCH files (payload, modes, PAL,
disable-auto, video actions 6/7). That test never fed a TROJAN that loads
outside the core, which is why it did not show this.

## 13. Config-text recognition

The "Original" column is all `1x`, from the report the critic did not see:
the original's parser section (`0x883aa8` onwards, inside `FUN_00883270`)
and `FUN_008d4f84` run on the R5900 interpreter, against launcHER's
`pops_config_load_file` built on host. The "launcHER at `cfebe01`" column is
that run. The last column is the merged code at `ef663b2` (merge
`95ba812`), taken from `docs/POPSTARTER_CONFIG_TEXT.md` and
`tools/test_pops_config_text.py`, not re-run by this pass beyond the host
run of section 19. The first review of that merge has open findings and
the answers are in progress on a side branch; the column states only the
merged code. The command census (`2x S14`) is separate: every command in the
binary has an inventory row, and no inventory command is missing from the
binary apart from the aliases and removed names already listed there.

| Input | Original | launcHER at `cfebe01` (`common/src/pops_config.c:570-649` then) | launcHER at `ef663b2` |
|---|---|---|---|
| `#$SMOOTH`, `; $SMOOTH`, `x$SMOOTH` | applied: a command is recognised at any `$`, whatever precedes it | ignored | applied, as the original |
| `$SMOOTH$SCANLINES` | both applied: `$` is a terminator | neither | both, as the original |
| `$SMOOTH<TAB>$SCANLINES` | only `$SCANLINES`: TAB is not a terminator | both | the original's handler pass and terminator set (`pops_config_parse_text`); this exact text not checked by this pass |
| `$MODE 3`, `MODE 3`, `$NOBOOT` | nothing | compat mode 3; `no_boot` | unchanged: launcHER's own tokens are still read, with launcHER's earlier rules |
| `VMCDIR.TXT` over 103 bytes, or containing `\`, `/`, `:`, CR or LF | file ignored, launch continues | launch aborted for `A/B`, a second line, or 104 bytes (`:809-835`, `:891-903` then) | file ignored, launch continues (`pops_config_parse_vmcdir`) |
| `VMCDIR.TXT` `SAVES<CR><LF>` or ` SAVES ` | ignored (illegal character) / spaces kept | accepted and trimmed | as the original |
| empty `VMCDIR.TXT` | directory becomes the POPS root | | the POPS folder itself, as the original; card names still differ (`<serial>.VMC0` beside `SLOT0.VMC`) |

File names: the only config files the original builds names for are
`OSD.BIN`, `BIOS.BIN`, `TROJAN_n.BIN`, `PATCH_n.BIN`, `CHEATS.TXT`,
`VMCDIR.TXT` and `DISCS.TXT`, all under the game device's POPS folder
(`1x`, a scan of character-store chains; a name built another way would be
missed).

Note on the cheat-code scan: the inventory already records that `#` does
not hide a `$` cheat code and that launcHER matches that. The rows above
are about commands, where launcHER does not.

## 14. launcHER-only behaviour (not in POPStarter r13)

Collected so nobody mistakes these for copied behaviour. Each is `read`
from launcHER's sources (S17 for the lines).

- `PATCHES.TXT` and `MODES.TXT` (`pops_config.c:853-915`), `MODE n` /
  `$MODE n` (`:598`, `:629`), bare digits in `MODES.TXT`.
- `$NOBOOT` / `$BIOS`: not r13 commands. launcHER acts on them: it
  rewrites `0x2525b0` to `0x1bfc` when it reads `0x0648` (since `0945127`
  not when a `BIOS.BIN` was loaded). After a mode 6 this ends differently
  from the original, which ignores the token.
- Aliases `$PAL2NTSC`, `$FORCENTSC`, `$NTSC2PAL`.
- The EE sleep for `$USBDELAY_n` and its default 0. (`$USBDELAY` with
  several digits or without the underscore was also launcHER-only at
  `cfebe01`; since `95ba812` the parser takes one digit, as the original.)
- Since `173d5de` and `0945127`: the IGR skin and `BIOS.BIN` are read from
  the `.VCD`'s folder (and `<folder>/<name>/` for a game's `BIOS.BIN`), not
  from `POPS/`; neither has the original's POPS folder exit.
- Since `21c3476`: on an `SB.` launch of a PS1 game, the network files are
  also looked for in ten places after the original's two
  (`pops_netconfig_path`).
- Config files from `mc0:`/`mc1:` `POPSTARTER/` and `POPS/`
  (`pops_config.c:848-867`).
- POPS package search folders beyond the device POPS folder, and SHA-256
  pinning of the package.
- Mixed-case and bare-name `XX.`/`SB.`/`PP.` matching; silent 63-character
  title cut.
- The default direct IGR exit (section 7); `pops_apply_igr_pad_control`
  (`pops_modes_patches.c:1301`), which only tests call.
- launcHER's own serial compat DB beside the built-in list; its custom IRX
  manifest (`pops_load_custom_modules`); embedded network modules.
- `pops_config_load_table` / `pops_config_export_table` (section 9).
- The launch target is a `.vcd` path, not a renamed ELF.
- Its own exit instead of the original's exit program at `0x1450000`.
- The stale test folder in the package search list (`handler_pops.c:153`).

## 15. Parts of the original nobody has examined

From the critic's list, unchanged in substance. "Examined" here means read
closely or executed; strings-only passes do not count.

- `POPS<n>` folder variant on type 3: `0x8762cc..0x876690` sets
  `gp+0x381c`, stores `/` pairs at `gp+0x347a`/`0x347b`, loops over the
  embedded PFS wrapper image (refs to `0x91f680` at `0x876458` and
  `0x8765b4`) and stores a byte into `gp+0x38b8`. It looks like the
  wrapper's own path is patched with the folder digit. Not decoded.
- HDD retry loop `0x875d94..0x875fa4` and the old-launcher path
  `0x87551c..0x875780`: names read from byte stores only, not executed.
- HDD file locations as a whole (`pfs1:/POPS/` in `hdd0:__common`) against
  where launcHER looks.
- `FUN_0087cf68` (5,240 bytes): only its three-probe integrity tail was
  examined. The `IOPRP.IMG` fallback, the PAK identity checks and failure
  handling are unmeasured. Also unclaimed in REPOP.
- `main` `0x8719f0..0x873ef0`: `mc?:/POPSTARTER/` module loading and the
  two network config parsers, beyond the parser runs in section 11.
- `main` `0x873ef0..0x8743d8`: `__common` mount, POPS folder check, SMB
  logon sequence. Strings and gates only.
- `main` `0x874cc0..0x8752e0`: game-name and `SLOT%d.VMC` name
  construction, the "shorten your game name" limits, the `0x100015` digit
  variant.
- `FUN_008d8050` (2,312 bytes, VMC preparation): only its tail.
  `FUN_008d7c40` (568 bytes, called from it at `0x8d8810`): not at all.
- `FUN_008d8db8` (10,688 bytes): read from flow dumps, never executed.
- `main` `0x879e5c..0x87c1e0` ("LAUNCHING POPS"): the ten `FUN_008d7024`
  calls, the IOPRP module-name compare chains `0x87a074..0x87a610`, the
  `crap:` device and its small embedded IRX (copied five times at
  `0x871674..0x8716c4`), both `rom0:UDNL` resets, and the full post-reset
  module start order (sio2man, padman_hsync, usbd, usbhdfsd, iomanx,
  filexio, `MODULE_0..4`, poweroff, ps2dev9, smsutils, ps2ip, ps2smap,
  smbman, smb connect, `MODULE_5..9`, PFS wrapper) plus the final clears and
  the jump. Existing launcHER documents cover `MODULE_n` and the opcode
  pass; the rest was not re-examined.
- Fatal/exit path: `FUN_008709f8`, `FUN_00870500` (424 bytes),
  `FUN_00870230` (720 bytes): the order of `mass:/BOOT.ELF`,
  `mc0:/BOOT/BOOT.ELF` and the browser was not traced. The exit program
  copied to `0x01450000` (source `0x99e410`) is not copied by launcHER; its
  behaviour after IGR YES is unverified; 16 of its functions are unclaimed
  in REPOP.
- The preset-driven core patch helpers called at `0x874a24..0x874c94`
  (`FUN_008dbafc`, `008dbcdc`/`008dbd6c`, `008dbe08`, `008dbe78`,
  `008dbee4`, `008dbf58`, `008dbfd4`, `008dc0c0`, `008dc12c`, `008db778`):
  mapped to preset bytes by banner text only.
- Preset bytes `0x100008`, `0x100009`, `0x10000c`, `0x100014`, `0x100016`
  and the `XBRA` RAM scan (`0x8716cc`; on non-quiet profiles a hit in
  `0x80000..0xfffff` sets the `$480p` flags): effect or reader not
  identified.
- `FUN_00870700` (eight memsets over `0x9200d0..0x936b50`) and the
  wall-clock length of the `0x100013` busy-wait.
- Sony's side of the new features: POPS with a foreign BIOS or OSD body,
  the v2 OSD's `jal` in a delay slot, POPS's TIM2 upload with odd files,
  IOPCD real-disc reads. Read or modelled only.
- The TROJAN/PATCH loaders and the parser were not re-examined by the
  critic. The loaders have since been re-run on the whole corpus twice
  (the review and S27); the rule-difference table of section 12 and
  sections 11 and 13 are still `1x` in this document's own terms (the
  review reports re-running parts of them, see the end of section 19).
- Embedded data never touched: icon data at `0x9639b4`, the second copied
  block (`0xd60` bytes to `0x238a90`, refs `0x87476c` and `0x896084`), the
  inner unpacker `0x99de44`/`0x99df08`, the crt0 entry. The block
  `0x9add3c..0x9ae604` is referenced only from library code (`inferred`:
  SDK kernel patches).
- launcHER-side behaviour that was read, never executed, by the feature
  reports: `pops_apply_reset_warmboot` over arbitrary BIOS bytes; the
  `PopsFixContext` guards against a replaced ROM range; trampoline
  preflight hashing; whether `plan.core_size` covers offset `0x14ee70` for
  every accepted package.
- Whether any of the 625 built-in entries or the always-on pokes write
  inside the ROM range `0x24bc20..0x2cbbb0`, the OSD areas
  `0x262b80..0x2afc20` or the skin slots `0x2feff0..0x34ee70`. This decides
  whether staging order matters, and is cheap to measure from the generated
  list. Partly measured since `173d5de`, on launcHER's copy of the list:
  `tools/test_pops_igr_skin.py` checks that every core write of that list
  ends below `0x21b000` (so below the ROM range, the OSD areas and the
  slots), applies entries 1..624 over a marked core with the slots
  unchanged, and applies each with the skin in both orders with equal
  results. Writes of the list's other kinds were not checked by that test,
  and the original's own list was not compared. For the corpus fix files the answer is now known (S27): one PATCH
  file covers the three skin slots exactly, one config-only PATCH changes
  the halfword `0x2525b0` in the ROM range, no PATCH file touches the OSD
  areas, and every TROJAN payload loads outside the core, changing only
  its slot word at load time. What a TROJAN payload writes once it runs was
  not examined.
- Documents no report cross-checked: the device rows of
  `POPS_PARITY_AUDIT_2026-10-28.md`, `POPSTARTER_REPLACEMENT.md`.

Examined and found irrelevant, listed so it is not rediscovered:
`FUN_008dc9ac` (14,116 bytes, called at `0x8774bc` and from the fatal
handler) sets `gp+0x3828 = 3` and zeroes 688 records of `0x90` bytes at
`0x972310..0x98b5c0`, the original's own fingerprint table. It touches no
POPS memory, so launcHER needs nothing for it (`1x`; callers `2x S6`).

## 16. Ranked increments

`C n` is the critic's rank. `D x` is an item from the device/file report,
which the critic never saw; where those sit in the order is this
document's proposal, not the critic's.

| # | Increment | Source | Host-verifiable | Effort | Depends on | State at `ef663b2` |
|---|---|---|---|---|---|---|
| 1 | Correct the status documents (this commit) | C1 | n/a | small | none | first pass `cfebe01`; second pass this commit |
| 2 | Fix files the original would skip must not end the launch: treat its "Invalid" and "Skipped (outdated)" outcomes as skip-and-continue in `pops_stage_fix_files`. Then TROJAN parity proper: the original's header rules, payloads outside the core written at their EE address at handoff (after checking them against launcHER's own regions), and the call slots in the resident GP1 work: at least the ten the corpus uses (section 12). An earlier wording said "fifteen"; it came from one mapping report's reading of the block as five slots plus ten, which the count in S26 (5 plus 55 empty pairs) does not support | D A | yes for classification and slot order (add the corpus classifier to `tools/test_pops_fix_files.py`, skipped without the external corpus); a payload actually running needs a console | large | none (the corpus result has been re-run, S27) | not landed; TROJAN work in progress on a side branch |
| 3 | One path table measured from the original: a tool that records every open for backend x scope x suffix x name, a pure function that returns the same strings, and a written decision of how each original folder maps to launcHER's per device, HDD included. No behaviour change | C2 | yes | medium | owner decision on HDD mapping | not landed |
| 4 | IGR skin staging: `pops_igr_skin_stage`, size checked before reading, never fatal, staged after the always-on pokes; default exit unchanged | C3 | yes | small | 3 for the folder | landed `173d5de`: reads the `.VCD`'s folder, not `POPS/`; no POPS folder exit (sections 6, 3) |
| 5 | The six loader flags and the three downstream gates (section 5a, `$UNDO_`, mode 6, launcHER's `$NOBOOT` path), then `BIOS.BIN` with a partial reader | C4 | yes | medium | 3; one home for the flags | landed `0945127` for `BIOS.BIN` and the flags' home (`PopsUserRomState`); OSD words exist but nothing sets them (sections 4, 5a) |
| 6 | Fix files before commands: first a test that runs both orders and records every differing final core; reorder only if it shows differences. Touches the pinned order test | C5 | yes | medium | before 7 | not landed; `docs/POPSTARTER_USER_BIOS.md` measured 28 of 270 scenarios differing at `0x2525b0` |
| 7 | `OSD.BIN`: `pops_osd_stage` with one reason code per rejection, whole-core differential, directed boundary cases plus three negative controls (random cases caught two of three deliberate mutants in only 1 to 3 of 600) | C6 | yes | medium | 3, 5, 6 | not landed |
| 8 | `$USBDELAY` parser (one digit, the original's terminators, default 1) and the preset table (fix or delete `pops_config_load_table`); command recognition context and `VMCDIR.TXT` rules; decide which launcHER-only forms stay as documented extensions | C7, D C | yes | small | none | parser, command recognition and `VMCDIR.TXT` landed `95ba812`; default still 0, preset table unchanged; review answers in progress on a side branch |
| 9 | The `$USBDELAY` effect: a one-time delay on the first wrapped call in popfs, `XX.`/`SB.` only, replacing the EE sleep | C7, D D | host test with a fake delay; working only after a console or emulator run | medium | 8 | not landed |
| 10 | Launch-argument rules as a pure function (prefix scan, launch type, `cdrom` exit) and resolver candidates (`IMAGE0.VCD`, `POPS0..9`, `__.POPS0..9`, fail instead of truncating); `IOPRP.IMG` fallback; remove the test folder from the search list | C8, D B | yes | medium | a decision on where a `.vcd`-target launcher consults ELF-name rules | not landed |
| 11 | SMB config parsers to the original's rules | D E | yes | small | none | landed `21c3476` for `SB.` launches of PS1 games only; not reviewed |
| 12 | Physical disc fallback: planner, guarded `0x200794` row, CDDA mute for types `0x11`/`0x13`, resident physical flag; device part later and marked untested | C9 | partly | large | last of the features; a decision on how it is requested | host part landed `f22a69f` (planner, core stage, fingerprint), not called by the launch; not reviewed |
| 13 | HDD layout: mount `hdd0:__common` and take POPS files, fix files, text files and VMCs from `/POPS/` there; `icon.sys`/`list.ico` | D F | no | medium | 3; console | not landed |
| 14 | IGR default: write nothing without a command, as the original | D G | yes for the write set | trivial | owner decision; the dialog's YES path under launcHER's exit is untested on a console | not landed; owner decision |
| 15 | SMB external IRX set, `mass` rename, LOGON/ECHO/OPENSHARE order | D E | no | medium | console | not landed |
| 16 | REPOP documentation follow-up (section 17) | C10 | n/a | small | separate repository and PR | not in this repository |

## 17. REPOP status

REPOP is the companion reconstruction of POPStarter. It is a reference
source, not a runnable r13.

| Statement | Label |
|---|---|
| The live line is `origin/main` at `bc258e48` (2026-11-02). To reproduce the numbers in this section use a clean checkout or a `git archive` export of that commit. The worktree `REPOP.worktrees/pr23` is not a stable reference: it is on a local working branch that was at `bc258e48` early on 2026-11-11 and has had newer local commits since 06:25 (-0800) that day; the tool prints other numbers there (the review got 440 / 94.4% / 91.2% at `e161e957`) | `2x S18 S20` for `origin/main`; `2x S20` for the worktree having moved (the review and S20); the 440 figure is the review's, not re-run |
| `feat/psxcore-validation` (`d3452068`) is fully superseded: it is an ancestor of the head of PR #53, which was squash-merged as `0d5ca939`. The older checkout `C:/Users/natha/Github/REPOP` is still on that branch and must not be used | `2x S18` for the ancestry; `1x` for "no file exists only on the branch" |
| `python tools/parity_report.py popstarter` at `bc258e48`: 434 of 466 functions (93.1%), 125,048 of 138,664 bytes (90.2%); size parity not measured (snapshot invalidated) | `2x S18 S20` (also the review's run on its own export of `bc258e48`) |
| That ground truth omits four real functions, 597,012 bytes, because `tools/ghidra/ForceFunctions.java` drops anything of 32 KB or more as data: `main` `0x870b78` (46,752), the config/command/cheat parser `0x883270` (335,124), the built-in per-game routine `0x8e00d0` (126,996), the built-in lookup `0x8ff0e4` (88,140). REPOP's documents acknowledge only `main` | `2x S8` |
| Counting them, byte coverage is 125,048 / (138,664 + 597,012 - 968) = 125,048 / 734,708 = 17.0%, not 90.2%, and not the 67.5% in REPOP's README | arithmetic `2x`; it assumes the four functions replace six fragment entries (968 bytes) in the denominator |
| 32 functions (13,616 bytes) are unclaimed. Six of them are pieces of larger functions and can never be claimed (`FUN_0087c1e0`, `FUN_008d4e30`, `FUN_008e034c`, `FUN_008ff000`, `FUN_008ff064`, `FUN_00914800`); 26 real ones remain, the largest being the POPS loader `FUN_0087cf68` | `1x`; the `FUN_00914800` point `2x` |
| REPOP's own `main()` (`popstarter/src/main.c:1314`) is a five-line stand-in, so its `POPSTARTER.ELF` is a compile-and-link artifact | `read` |
| The three loaders are already rebuilt and reported to agree with the binary: `popstarter_load_user_osd` (`main.c:734`), `popstarter_load_user_bios` (`:1090`), `popstarter_load_igr_bg` (`:1237`). No REPOP source change is needed for those features | `read` (compared by reading, not diffed mechanically) |
| Branch `claude/popstarter-batch26-28-wip` (`745cc0e5`) holds nine unreviewed drafts; its own README says not for merging | `read` |
| Claims are checked for call shape and by reading; REPOP's audit tool itself says its "calls-match" and "leaf" classes are not proven equivalent. Only the CD path has a compiled-EE differential (247 cases, taken from PR text, not re-run on 2026-11-11) | `read` |

REPOP documentation errors found (for a separate REPOP pull request):

- `docs/CONFIG_TABLE.md`: `$417` is called "Legacy / Reserved"; it is live
  (the `$USBDELAY` seconds). `$413` is called a delay in seconds; it is a
  busy-loop count shifted left 24. `$410` default is given as `0xFF`, which
  is the DEBUG profile; MAIN has `0x00`.
- `popstarter/src/main.c:1225-1236` calls `gp+0x38dc` a "done flag".
- The parity documents should record the four omitted functions and the
  17.0% figure beside 90.2%.
- `docs/POPSTARTER_CONTINUATION.md` (item 6 of its list near line 255) asks
  for an AI co-author trailer on every commit. The owner's rule is no AI
  attribution anywhere; do not add it.

Later the same day the working branch in `REPOP.worktrees/pr23` (local,
not in `main`) gained
commits whose subjects name the first three items: "correct three config
table entries from the files and r13" (`a10b3319`), "the word at
$gp+0x38DC is a shared abort flag" (`8f57231d`), "record batch 26 and the
four functions the ground truth omits" (`33a0554a`). Only the subjects were
read for this document (S20); the changes themselves were not reviewed
here.

## 18. Contradictions between the reports, as settled

| Topic | Settled as |
|---|---|
| Region pass, unknown licence, the four zero bytes | skipped in every arm where the unflagged run writes them (section 5a), not "without FORCEPAL" |
| Folder for `BIOS.BIN` / `OSD.BIN` / skin | the original's device POPS folder (`pfs1:/POPS/` on HDD, `mass:/POPS<s>/` otherwise), not launcHER's `vcdDir`. The two are the same only when the VCD sits in the POPS folder on USB/SMB. The merged `BIOS.BIN` (`0945127`) and skin (`173d5de`) stages use the `.VCD`'s folder as a stand-in, each listed as a difference in its own document; the path decision of increment 3 is still open |
| Reading `BIOS.BIN` with `readFullFile` | cannot express the size rule; a partial reader is needed. `readFullFile` is fine for `OSD.BIN` and the TM2 files if the size is checked first. Since `0945127` `pops_user_bios_load` is that partial reader, and the skin stage checks the size before reading |
| Fix files and commands | the original runs fix files first (section 3). Two feature plans assumed different workarounds; decide the order question (increment 6) before `OSD.BIN` |
| `$NOBOOT` | not an original token at all; the `0x2525b0` write is launcHER's own |
| "BIOS.BIN with integrity check" | size test only; the message is the OSD handler's |
| `gp+0x38dc` | shared abort flag |
| `cdrom` | launching POPStarter from `cdrom...` exits; the physical-disc path is only the no-VCD fallback |
| REPOP coverage | 90.2% by its tool, 17.0% once the four omitted functions are counted |
| ps2build version | one report read toolchain v2026.11.04 / sdk-core v2026.11.05, another ps2build v2026.11.06. Not resolved; both agree no local full target build is current |
| Where `$USBDELAY` sleeps in launcHER | after the IOP reset (S19) |

## 19. What this audit did not do

- No console run, no whole-machine emulator run, no full PS2 target build.
- No change to any source file. The host test list was run before and
  after the documentation change only to show nothing else moved.
- The original's parser, SMB parsers and `VMCDIR.TXT` reader were not
  re-run for this document, neither for its first version nor by the
  correction pass; sections 11 and 13 and the rule-difference table of
  section 12 are measured once in this document's own terms. The fix-file
  loaders were re-run on the corpus (S27).
- `main` was not executed end to end.
- The correction pass ran four functions of the original (`0x88019c`,
  `0x87e464` and the two fix-file loaders `0x880a24` and `0x881de8`) and
  read the rest statically.
  It did not re-run the OSD handler, the region pass, the physical-disc
  block or the device scan.

What the independent review reports having re-run with its own scripts,
with results matching this document (recorded as reported; the correction
pass repeated only the items marked S): the static checks S1..S13; the BIOS
handler on 48 cases (S22 repeats part); the IGR skin function on 22 cases
(S23 repeats part); the corpus census and both loaders on every unique file
(S27 repeats); `pops_fix_stage` on the corpus (S27 repeats); the
rule-difference table of section 12 on synthetic files; the config-text
rules of section 13 on 19 probe texts and the `VMCDIR.TXT` rules on 11; the
region pass of section 5a on 48 flag combinations; the single-site
construction of `0x20c0a4`, `0x2362fc`, `0x200794` and the 33 sites that
build `0x228a20..0x228a6b`, all inside the `$IGR0..5` / `$NOIGR` handlers.
The review did not re-derive the OSD handler, the physical-disc block, the
`XX.`/`SB.` scan, the SMB parsers, the launch-type parser, the wrapper on
the IOP side, or most `read` statements of section 10. All of it is host
work. NOT TESTED on a console.
