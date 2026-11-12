# pr23/trojan-2: answers to the independent review

Branch `pr23/trojan-2`, head `70ed0473625589d0bf1d18e11ff0fa17af1283f0` (one
commit on top of the reviewed `6732e95`), pushed to origin. Nothing was
force-pushed. `codex/popstarter-replacement`, EMBER, tags and releases were not
touched. Scratch paths are written `<scratch>`.

**Nothing here ran on a console (NOT TESTED on a console).** No PS2 emulator or
rig was used. "Emulation" means Unicorn and `tools/r5900_mini.py` in host tests.

## Per finding

### B1 (blocker): CI red, test_pops_trojan.py does not build on Linux — FIXED

- `tools/test_pops_trojan.py` `build()`: added `-D_DEFAULT_SOURCE` to the gcc
  line, which stays `-std=c99`. glibc hides `strcasecmp`/`strncasecmp` under
  strict C99, and `pops_config.c`, `pops_compat_db.c` and `pops_vcd.c` use
  them. A comment says why.
- `SOURCE_WRAPPER`: the `#ifndef O_BINARY / #define O_BINARY 0` fallback now
  comes right after the includes, before `test_open` uses it.
- Linux check: I ran every `run: python tools/...` step of build.yml's
  host-tests job, in order, on `git archive HEAD` (70ed047). It ran in local
  `python:3.12-bookworm` (Python 3.12.15, gcc 12.2.0) with `--network none`
  and no reference inputs. Result: 31 of 31 rc 0, with
  `test_pops_trojan.py OK (skipped=16)`.
- GitHub Actions on 70ed047:
  - "Build launcHER" run 43132861664: success (build 46 s, host-tests 51 s).
  - "Launcher argument compatibility" run 43132861688: success.

### M1 (major): committed table of POPStarter instruction words — FIXED (table); code reproduction left to the owner

- `tools/pops_trojan_chain.py`: `EMODE_WORDS`, a table of 16 POPStarter
  words, is gone. In its place is `EMODE_AT = 0x18`, the offset of the emode
  checks inside launcHER's own chain entry.
- `compare()`, which runs only with POPSTARTER_TEST_ELF, now compares the
  image's 64 bytes at `chain entry + 0x18` with the user's POPSTARTER.ELF MAIN
  at `0x983150`, read at run time. The old assertion compared the ELF with the
  committed table.
- `self_check()`, which runs without the ELF, no longer checks the words. It
  has nothing to check them against. Its behaviour checks stay: emode stores,
  k0/k1/ra at each slot, pad flags, the reset store and cheats.
- Mutation check (`<scratch>/ci-trojanfix/mutate_emode.py`, with
  POPSTARTER_TEST_ELF): on the built image, `compare` gives PASS, 71 cases and
  350 slot records. With one bit flipped in the entry's fourth emode word,
  `compare` raises "the entry's emode checks are not the original's words".
  The check still works without the table.
- Not changed:
  - The table stays in git history (commits from `pr23/trojan`). Removing it
    would mean rewriting published history, which needs the owner.
  - `pops_resident_gp1_chain` (`common/src/pops_resident_engine.c`) still
    reproduces POPStarter's instruction sequence: the k0/k1 save, the emode
    checks, the reset check and the restore. That is the author's owner
    question 2. The register parity measured by the differential tests depends
    on it, so I left it as it is.
- I scanned the branch diff (`ef663b2..HEAD`) for other word tables: lines
  with four or more 8-digit hex constants, `.word`/`.long`, and 24+-digit hex
  runs. What remains is addresses, launcHER's own test stubs (`lui k0,0xdead`
  and so on) and `POPS_TROJAN_BREAK_CALL` (`jal 0x01460000`, launcHER's own
  break handler).

### m1 (minor): FNV-1a sums of Sony POPS bytes — NOT CHANGED (owner decision)

- `SLOT_RUN_A/B_PRISTINE` in `common/src/pops_resident.c` stay as they are.
  The reviewer measured that they match the real core.
- Replacing them would change what launcHER checks at launch. It is the
  author's owner question 1, and it is recorded again below.

### m2 (minor): two measured register differences missing from the proposed quirks — TEXT BELOW

The text is in "Proposed quirk text" below. The quirk docs are protected, so I
did not edit them. I re-measured the difference on the container-built image
(`check_pops_resident_image.py`, with references): "on the disc swap frame
a0/ra/v0 differ at slots 4,5,6,8,9 and a0/v0 at the return, stores equal".

### m3 (minor): doc says "skipped", but the install-time check aborts — FIXED (doc)

- `docs/POPSTARTER_TROJAN.md`, "The ten slots": the slot check now has two
  parts. When the slots are offered (after the commands and emit jumps, before
  the first fix file), a failure means nothing is written and a slot file is
  skipped. The check is repeated at install, after every fix file. If
  something changed a run or the hook in between, the launch stops with "TROJAN
  slots cannot be installed".
- Added known difference 9: a slot file accepted early can still stop the
  launch, where r13 would run. Found by reading the code
  (`handler_pops.c` around the `pops_resident_hook_slot_chain` call, and
  `slot_chain_check`). Not measured. No corpus file does this.
- The code was not changed. A behaviour that matches r13 here needs a
  measurement of what r13 does when a PATCH writes into
  `0x2327d0..`/`0x232d08..`, and I did not make one. Recorded as an open
  question.

### m4 (minor): doc claims more than was measured for a failed first header read — FIXED (doc)

The device-failures paragraph now says the zeroed header after a failed read
was measured for the second file only. For the first file, the buffer is the
original's stack, which is zero in the model and not measured on a console.

### m5 (minor): stale test name — FIXED

`test_an_empty_or_short_file_is_invalid_and_one_too_large_stops` is renamed to
`test_an_empty_or_short_file_is_invalid_and_an_empty_patch_stops`. That name
matches the body: short TROJAN files are Invalid, and an empty PATCH still
stops the launch. The too-large case is already its own test
(`test_a_file_larger_than_the_read_buffer_is_skipped_not_fatal`).

## Files changed (70ed047)

- `tools/test_pops_trojan.py`: B1, m5
- `tools/pops_trojan_chain.py`: M1
- `docs/POPSTARTER_TROJAN.md`: m3, m4, known difference 9

There is no C change. The built `pops_resident.bin` is byte-identical to the
one built from 5624c29 (`cmp`). None of the five protected docs was edited, and
`.github/workflows/build.yml` did not need a change. The diff contains no
corpus bytes, names or hashes. A scan of the added lines and the commit
message for AI attribution found none.

## Commands run and results

All in Git Bash. Each host test ran on its own, with TMP, TEMP and TMPDIR set
to a fresh `<scratch>/tmp-trojanfix/<mode>-<test>`. Runner:
`<scratch>/ci-trojanfix/run_host.sh`.

| Command | Result |
|---|---|
| `git pull --ff-only` | already up to date (6732e95) |
| commit 70ed047; `git push -u origin pr23/trojan-2` | `6732e95..70ed047` |
| CI host steps from build.yml in `python:3.12-bookworm`, `--network none`, on `git archive HEAD` (`<scratch>/ci-trojanfix/run_ci.sh`) | 31/31 rc 0; test_pops_trojan OK (skipped=16) |
| `gh run list --branch pr23/trojan-2` / `gh run view 43132861664` | Build launcHER: success (build, host-tests); argument compatibility: success |
| `run_host.sh noref`: 34 `tools/test_*.py`, references unset | 34/34 rc 0. Selected: trojan 59 (16 skipped), trojan_corpus 3 (3 skipped), fix_files 31 (3), user_bios 51 (13, 1 expected failure), external 128 (14), resident 75 (12), launch_hooks 48 (14), read_trace 9, igr_skin 48 (21), physical_disc 40 (18), progressive 8 (5) |
| `run_host.sh ref`: POPS_TEST_ELF, POPSTARTER_TEST_ELF, POPS_TROJAN_CORPUS set | 34/34 rc 0. Skips only in: trojan 59 (5), external 128 (3), launch_hooks 48 (3), progressive 8 (3); user_bios has 1 expected failure. trojan_corpus 3 OK (49.5 s) |
| Container build (prescribed command, with `(cd / && git config --global --add safe.directory /workspace)`, folder `build-trojanfix`) | rc 0. `build-trojanfix/release/launcHER.elf` 331,284 bytes; `pops_resident.bin` 7,504 bytes; 23 `warning:` lines, all in unchanged code; CMake "version=unknown" warning |
| `cmp` new vs earlier `pops_resident.bin` | identical |
| `POPS_RESIDENT_BIN=<built> python tools/test_pops_trojan.py` (+refs) | 59 OK, 0 skipped. "Original file-to-slot PASS: 5 style sets x 5 pad states, 210 slot records"; "Original slot chain PASS: 71 cases, 350 slot records" |
| same, `tools/test_pops_resident.py` | 75 OK |
| `python tools/check_pops_resident_image.py build-trojanfix/launcher/pops_resident.bin` (+refs) | rc 0, every section PASS, including "resident TROJAN slot chain: PASS (142 cases, 700 slot records ...)" and "original's chain vs the built TROJAN slot chain: PASS (71 cases, 350 slot records ...)" |
| `python <scratch>/ci-trojanfix/mutate_emode.py` (POPSTARTER_TEST_ELF) | built image PASS 71/350; one bit flipped in an emode word: compare fails as expected |

The corpus test with all three references gives the design's table:

- TROJAN:
  - 509 unique files, 3,952 copies;
  - 367 files (3,744 copies) are loaded;
  - not loaded: 120/158 for the 480p handler, 17/36 for code at `0x238a90..`,
    5/14 for code at `0x0143a000..`;
  - verdicts `{'APPLIED': 509}` on both sides. The 367 loaded files have the
    original's slot words and payload bytes.
- PATCH: 10 unique files, 870 copies. All 10 leave the whole POPS image equal
  to the original's.
- 3,952 + 870 = 4,822 files in total.

## Proposed quirk text (for the coordinator to number)

In addition to the author's drafts 62 to 71:

- On the frame of an in-game disc swap, POPStarter's chain leaves the disc
  init call's v0, a0 and ra in the registers. A payload at the second run of
  slots sees them: slots 4, 5, 6, 8 and 9 as `check_pops_resident_image.py`
  numbers them ("slots 6 to 10" in `POPSTARTER_TROJAN.md`). POPS sees v0 and a0 at
  the return. launcHER's chain keeps POPS's values. The stores are equal.
  Measured on `r5900_mini` and pinned by
  `test_the_disc_swap_frame_is_the_known_difference`. NOT TESTED on a console.
- Inside the chain, launcHER keeps ra across its first block of work, where
  r13 has whatever the slots left. launcHER does not keep k0/k1 across the
  second block. The differential comparison shows no register difference at
  any slot or at the return from this, apart from the disc swap frame. It does
  not cover a payload that reads these registers later through another hook.
  NOT TESTED on a console.
- A slot file accepted when the slots are offered can still stop the launch.
  If a later fix file (for example a root PATCH writing into
  `0x2327d0..0x2327ff` or `0x232d08..0x232d37`) changes a slot run or the GP1
  hook before install, the install check fails ("TROJAN slots cannot be
  installed"). r13 would run. Found by reading the code; not measured, and no
  corpus file does this.

Inventory row for TROJAN_n.BIN: still PARTIAL, as the author proposed. 142 of
509 unique files are not hosted, and nothing has run on a console.

## Not done

- No console run and no PS2 emulator. NOT TESTED on a console.
- m3 code behaviour: unchanged (see above).
- The resident chain's reproduced POPStarter instruction sequence and the FNV
  sums: unchanged, owner decisions.
- The removed `EMODE_WORDS` table is still in git history.
- Still open from the author: what to do on a failed TROJAN payload read, and
  with files over 1 MiB. Also not analysed: whether POPS's heap or stack
  reaches the arena, and how payloads interact with launcHER's own core
  patches.

## Open questions for the owner

1. The resident chain entry reproduces POPStarter's k0/k1 save, emode checks,
   reset check and restore, one instruction for each instruction of the
   original. Keep it (the register parity depends on it), or rewrite it? The
   committed copy of the words in tools/ is gone; the table is still in
   history. Should that history be rewritten? (I would not do that without an
   explicit request.)
2. `SLOT_RUN_A/B_PRISTINE` (FNV-1a sums of two 0x30-byte runs of POPS):
   keep them, or check the runs against the pinned core hash instead?
3. When a later fix file changes a slot run after a slot TROJAN was accepted:
   stop the launch (today), skip the slot files with a line, or measure r13
   first and follow it?
4. Still open from the author: a failed TROJAN payload read (stop, as today;
   or apply, as r13 does), and files over 1 MiB (skip, as today; or apply, as
   r13 does).
5. The documented container command needs `(cd / && git config ...)` inside
   a git worktree. Should it change?
