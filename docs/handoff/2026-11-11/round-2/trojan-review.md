# Independent review: pr23/trojan-2 (TROJAN_n.BIN on the PR #23 line)

Reviewed: `origin/codex/popstarter-replacement...origin/pr23/trojan-2`, head
`6732e95214d18bdf070b2fc497a6ede51485f4ca` (merge `7425303` of `pr23/trojan`
at `8f889cf`, then `5624c29`, `1d75d50`, `6732e95`). 23 files, +4,927 / -94.

Read-only toward the branch: nothing was committed or pushed. Work was done
in a detached worktree `<scratch>/review-trojan/tree`, removed at the end.
Scratch paths below are written `<scratch>`.

**Nothing here ran on a console (NOT TESTED on a console).** No PS2 emulator
was run. "Emulation" below means Unicorn / `tools/r5900_mini.py` in host tests.

## Verdict

**merge-after-fixes.** One blocker: the PR head's CI is red, because
`tools/test_pops_trojan.py` does not compile on Linux. GitHub Actions run
43124929672 on `6732e95` failed, and I reproduced the failure offline in a
Linux container. Fix that before merging. Also fix the committed POPStarter
instruction table (major). The C code, the merge resolution and the
differential results hold up under re-run. The corpus table matches the
design exactly.

## Findings

### B1 (blocker): CI fails on the PR head; test_pops_trojan.py does not build on Linux

- Evidence:
  - `gh run list --branch pr23/trojan-2`: "Build launcHER" failed on
    `6732e95` (run 43124929672) and on `1d75d50`. `pr23/trojan` failed in the
    same way (run 43106671947). The PR branch's last runs succeeded (43107880968).
  - The log shows `implicit declaration of function 'strncasecmp'` in
    `pops_compat_db.c:636` and `pops_vcd.c:267`. Then `setUpClass` errors in
    `Native` and `Source`, `FAILED (errors=2, skipped=16)`.
  - The job stops at that step. The 13 CI steps after it (resident, display,
    warmboot, ... user_bios) did not run in CI.
- Reproduced offline: I ran all 31 `run: python ...` steps of the host-tests
  job from `git archive HEAD`, in order, in local `python:3.12-bookworm`
  (`--network none`, no reference inputs). 30 pass and only
  `test_pops_trojan.py` fails.
- Two causes, both Linux-only (MinGW on Windows hides them; that is why every
  local run here and the author's runs passed):
  1. `tools/test_pops_trojan.py:249` compiles with `-std=c99 -Werror` and
     includes `pops_config.c`, `pops_compat_db.c` and `pops_vcd.c`. Those use
     `strcasecmp`/`strncasecmp`, which glibc hides under strict C99. The
     other tests that compile `pops_compat_db.c` (launch_hooks,
     physical_disc, features, ...) use the default `gnu` dialect.
  2. In the `SOURCE_WRAPPER`, `test_open` (line 397) uses `O_BINARY` before
     the `#ifndef O_BINARY / #define O_BINARY 0` fallback (line 409). This
     came in with `5624c29`'s fault injection.
- Fix, checked in the Linux container on a scratch copy only: add
  `-D_DEFAULT_SOURCE` (or use `-std=gnu99`) to the build line, and move the
  `O_BINARY` fallback above `test_open`. With both fixes the result is
  `Ran 59 tests ... OK (skipped=16)`. Either fix alone still fails.
- The author's report says "CI already runs ... so build.yml needed no
  change". The workflow lines are present, but the author did not check that
  the step passes on CI's OS.

### M1 (major): a table of POPStarter instruction words is committed

- `tools/pops_trojan_chain.py:57` `EMODE_WORDS` holds 16 words (64 bytes).
  Line 387 asserts that they equal `POPSTARTER.ELF` MAIN at `0x983150`. They
  are a copy of POPStarter code.
- That is against the binding rule (never commit byte tables copied from
  POPStarter). The trojan design itself treated reproducing POPStarter code
  as forbidden (trojan-design.md, blocker 5).
- The resident chain entry (`common/src/pops_resident_engine.c`,
  `pops_resident_gp1_chain`) reproduces the same 16 instructions, plus the
  k0/k1 save, the reset check and the restore, one instruction for each
  instruction of the original. Line 443 asserts that the built image holds
  those 16 words.
- Fix for the table: read the words from `POPSTARTER_TEST_ELF` at run time.
  Compare the image's entry with MAIN directly when the ELF is given; skip
  the check otherwise.
- The code reproduction itself is an owner decision. The author raised it as
  owner question 2, but did not mention the committed table.

### m1 (minor): FNV-1a sums of Sony POPS bytes

- `common/src/pops_resident.c:384-385` `SLOT_RUN_A/B_PRISTINE` are hashes of
  two 0x30-byte runs of Sony's POPS core.
- I checked them against the real core (`<scratch>/review-trojan/scripts/fnv_check.py`
  on `POPS_TEST_ELF`): both MATCH.
- The repo already pins Sony images by SHA-256 (`pops_external.h`), so this
  follows existing practice. It is still a hash of a Sony binary: owner
  decision (author's question 1).

### m2 (minor): two measured register differences are missing from the proposed quirks

- `docs/POPSTARTER_TROJAN.md` known differences 5 and 6:
  - on the disc swap frame, v0/a0/ra at slots 4,5,6,8,9 and v0/a0 at the
    return differ from r13;
  - ra is kept across the first C block and k0/k1 are not kept across the
    second.
- These are parity deviations, measured and pinned by
  `test_the_disc_swap_frame_is_the_known_difference`. I reproduced the
  measurement: `check_pops_resident_image.py` says "on the disc swap frame
  a0/ra/v0 differ at slots 4,5,6,8,9 and a0/v0 at the return".
- The author's quirk list (62-71) does not include them. Proposed text below.

### m3 (minor): doc says "skipped", but the install-time check aborts the launch

- `POPSTARTER_TROJAN.md` lines 258-261: when a run is no longer POPS's own,
  "nothing is written; a file that needs a slot is then skipped".
- That is true for the check when the slots are offered (in
  `pops_stage_user_files`, before the first fix file). But
  `pops_resident_hook_slot_chain` checks again at `handler_pops.c:1886-1891`.
  If something changed a run after a slot file was accepted, the launch stops
  with "TROJAN slots cannot be installed".
- Example: a root `PATCH_n.BIN` that writes into `0x2327d0..0x2327ff` or
  `0x232d08..0x232d37` after a root slot TROJAN.
- From reading the code; not measured. Not in the corpus.
- Fix: correct the doc, or re-check `chain_offered` per file / after each PATCH.

### m4 (minor): doc claims more than was measured for a failed first header read

- `POPSTARTER_TROJAN.md` lines 79-81 say that a header that does not arrive
  "reads as zeros and is Invalid".
- `Original.test_device_failures` covers only a failed header read *after* an
  earlier file (the header buffer is cleared at `0x881d24`). For the first
  file, the buffer is the original's stack, zero only in the model. The
  author's report says "in the model"; the doc does not.

### m5 (minor): stale test name

- `tools/test_pops_trojan.py:1664`
  `test_an_empty_or_short_file_is_invalid_and_one_too_large_stops` no longer
  tests a too-large file (that case now skips:
  `test_a_file_larger_than_the_read_buffer_is_skipped_not_fatal`). Rename it.

## What was checked and held

### Correctness against r13 (re-run, not taken from the author)

- `test_pops_trojan.py` with references (Windows host): 59 tests, 5 skipped
  (Chain/OriginalSlots need an image).
- With `POPS_RESIDENT_BIN` set to my container-built image and the
  references: 59 OK, 0 skipped. "Original slot chain PASS: 71 cases, 350 slot
  records"; "Original file-to-slot PASS: 5 style sets x 5 pad states, 210
  slot records".
- `test_pops_resident.py` with the image and references: 75 OK.
- `check_pops_resident_image.py <built image>` with references: rc 0, every
  section PASS, including "resident TROJAN slot chain: PASS (142 cases, 700
  slot records ...)" and "original's chain vs the built TROJAN slot chain:
  PASS (71 cases, 350 slot records ...)".
- `test_pops_trojan_corpus.py` with all three references: OK (62.6 s). The
  output gives exactly the design's table:
  - 509 TROJAN unique / 3,952 copies; 367/3,744 loaded;
  - not loaded: 120/158 for the 480p handler, 17/36 for block 2, 5/14 for the
    resident range;
  - header classes 507 x (1,0,1), 2 x (3,6,1);
  - "verdicts {'APPLIED': 509}; 367 loaded ... with the original's slot words
    and payload bytes, 142 applied there and not loaded here";
  - PATCH 10 unique / 870 copies, 10 equal over the whole POPS image (0 to
    324,236 changed bytes).
  - 3,952 + 870 = 4,822. The test asserts equal verdicts per unique file.
- The corpus test forces `offered=True`. I checked separately that a real
  launch offers the slots:
  - the FNV sums match the real core;
  - the GP1 hook is installed (handler 1719) before the fix files (1798);
  - no built-in entry writes to the core inside `0x232790..0x2397f0` (awk
    over `pops_builtin_ops`: 0 core ops there).
- Mutation check of the author's `!kind` guard: I removed it from
  `!kind && result == POPS_FIX_SKIP_INVALID`. Then
  `test_a_patch_whose_mode_6_is_skipped_is_not_called_invalid` fails and
  `test_the_loop_text` errors. File restored with `git checkout`. The
  author's claim holds.

### Merge resolution (`git show --remerge-diff 7425303`)

- The conflict resolutions are what the commit message says. The BIOS.BIN
  side is kept: the rom state still goes to `pops_fix_stage_rom` for PATCH
  files, and `pops_user_bios_load` runs before each folder.
- `chain_offered` moved from `launchPOPS` into the helper, still after the
  commands and the emit jumps and before the first fix file. Same order as on
  the trojan side.
- Nothing from either side was dropped.

### Launch no longer aborts on a file r13 skips

From reading the code, with Source tests covering it:

- Invalid and outdated files are skipped (the verdict comes before any other
  check, also for files over 1 MiB).
- Any failed open is NOT FOUND.
- A failed size query or header read is Invalid.
- What can still stop the launch for a TROJAN file:
  - a failed payload read or seek (r13 applies such a file: owner question);
  - a staged core that no longer matches the session;
  - a failed slot install or copy-out check (m3).

### Memory

- Hold memory `0x01800000..0x01ef0000` and work `0x01ef0000..0x01f00000`.
  The raw `POPS.ELF` input at `0x01800000` is last used at `handler_pops.c`
  1606 (loose ELF) / 1551 (PAK decode). `rebootIop` points into the staging
  buffer or `0x01700000`, never into the hold memory. A decoded PAK is capped
  at `POPS_STAGING_CAPACITY` 8 MiB (ends at `0x01800000`).
- MODULE_n.IRX is read at 1173, before the fix files. I found no
  fixed-address user of the hold range after the fix files.
- `POPS_TROJAN_SCAN_WORK` for a 1 MiB payload is 64 KiB, which is exactly
  the work buffer.
- A TROJAN over 512 KiB read into the `0x01f00000` buffer overwrites the
  staged scratchpad at `0x01f80000`. That is harmless: the staged scratchpad
  is only zeroed (`pops_boot_stage.c:49`) and the trampoline zeroes the real
  one. This existed before the branch (PATCH files used the same buffer),
  but it is now reachable on a launch that continues.
- Copy-out comes after the IOP reboot (2047) and the built-in code install
  (2197), and before `pops_resident_install` (2239). Its keep list covers the
  staged core, the built-in code, the resident and break handler, the hold
  memory to the top of RAM, and low RAM.

### Launches without TROJAN files

- `pops_resident_gp1` (the usual GP1 entry) is unchanged.
  `pops_resident_hotkeys` is now a wrapper of its two halves, with the same
  statements in the same order.
- `pops_resident_hook_slot_chain` returns 0 without writing when
  `set->chain` is 0. Copy-out runs only when `payload_count` is nonzero.
- The resident image grows to version 16 / 124-byte header for every launch.
  Its checks pass (above).
- Nothing outside the POPS launch path changed. The touched files are
  `common/*pops*`, `handler_pops.c`, the resident build dependency in
  `launcher/CMakeLists.txt`, the workflow, tools and docs. None of the five
  protected docs was edited. EMBER, Ember code and shared storage drivers are
  untouched.

### No corpus/Sony data and no attribution

- Diff scan:
  - no 24+-hex-digit strings;
  - no game IDs;
  - no `bytes.fromhex` or base64;
  - no `claude|anthropic|codex|co-authored|generated` in the added lines or
    in the commit messages.
- The corpus test prints counts only.
- The two exceptions are M1 (the copied instruction table) and m1 (the FNV
  sums).

### Build

- Container build (`ghcr.io/ps2homebrew/ps2homebrew:main`) of `6732e95` in my
  worktree, with mmceman initialised via `--reference` and
  `(cd / && git config --global --add safe.directory /workspace)`: passes.
  - `build-review-trojan/release/launcHER.elf` is 331,284 bytes, as the
    author claimed.
  - `pops_resident.bin` is 7,504 bytes. 34 `warning:` lines.
- The prescribed command needs the same two workarounds in a git worktree.
  This confirms the author's question 5.

## Commands run and results

All in Git Bash. Each host test ran alone, with TMP/TEMP/TMPDIR set to a
fresh `<scratch>/tmp-reviewtrojan-<mode>-<test>`.

| Command | Result |
|---|---|
| `git fetch origin`; `git worktree add --detach <scratch>/review-trojan/tree origin/pr23/trojan-2` | HEAD 6732e95 |
| `git submodule update --init --reference <main>/launcher/iop/mmceman launcher/iop/mmceman` | db3e93f |
| `<scratch>/review-trojan/run_tests.sh noref` (34 `tools/test_*.py`, one at a time, refs unset) | 34/34 rc 0. trojan 59 (16 skipped), trojan_corpus 3 (3), fix_files 31 (3), user_bios 51 (13, 1 expected failure), external 128 (14), resident 75 (12), launch_hooks 48 (14), read_trace 9, igr_skin 48 (21), physical_disc 40 (18) |
| `run_tests.sh ref` (`POPS_TEST_ELF`, `POPSTARTER_TEST_ELF`, `POPS_TROJAN_CORPUS` set) | 34/34 rc 0. trojan 59 (5 skipped), trojan_corpus 3 OK (table above), external 128 (3), launch_hooks 48 (3), progressive 8 (3), user_bios 51 (1 expected failure), others no skips |
| Container build (above) | pass; 331,284 / 7,504 bytes |
| `POPS_RESIDENT_BIN=<built> python tools/test_pops_trojan.py` (+refs) | 59 OK, 0 skipped |
| same, `test_pops_resident.py` | 75 OK |
| `python tools/check_pops_resident_image.py build-review-trojan/launcher/pops_resident.bin` (+refs) | rc 0, all PASS |
| `python <scratch>/review-trojan/scripts/fnv_check.py` | both pristine sums MATCH the real core |
| awk over `pops_builtin_ops` for CORE ops in `0x232790..0x2397f0` | 0 |
| Mutation: drop `!kind` on the Invalid check; `test_pops_trojan.py` (no refs) | 1 failure + 1 error, as expected; restored |
| `gh run list --branch pr23/trojan-2` / `gh run view 43124929672 --log-failed` | Build launcHER **failure**: test_pops_trojan.py setUpClass compile errors |
| CI host-test steps from `build.yml` in `python:3.12-bookworm`, `--network none`, on `git archive HEAD` | 30/31 pass; `test_pops_trojan.py` FAILED (errors=2) |
| Same container, scratch copy, `-D_DEFAULT_SOURCE` + `O_BINARY` fallback moved | 59 OK (16 skipped); either change alone still fails |
| `git worktree remove --force <scratch>/review-trojan/tree` | removed |

## Proposed quirk / doc text (for the coordinator)

In addition to the author's 62-71:

- **(next)** On the frame of an in-game disc swap, POPStarter's chain leaves
  the disc init call's v0, a0 and ra in the registers. A payload at the
  second run of slots sees them, and so does POPS at the return (v0, a0).
  launcHER's chain keeps POPS's values. Measured on `r5900_mini`,
  `test_the_disc_swap_frame_is_the_known_difference`. NOT TESTED on a console.
- **(next)** Inside the chain launcHER keeps ra across its first block of
  work (r13: whatever the slots left) and does not keep k0/k1 across the
  second. The comparison shows no register difference at a slot from this,
  apart from the disc swap frame.
- **(next)** A slot file accepted early can still stop the launch, if a later
  PATCH (or anything else) changes a slot run before the slots are installed.
  r13 would run. From reading the code; not measured.
- `POPSTARTER_TROJAN.md` lines 258-261 and 79-81: wording per m3 and m4.

## Open questions for the owner

1. The committed `EMODE_WORDS` table and the chain entry's reproduced
   POPStarter instructions (M1): keep the instructions (register parity) but
   drop the committed table, or something else?
2. The FNV sums of POPS bytes (m1): keep them, or check the slot runs
   against the pinned core hash instead?
3. Carried from the author, still open: what to do when a TROJAN payload
   read fails (today the launch stops; r13 applies the file), and with files
   over 1 MiB (today skipped; r13 applies them).

## Not done

- No console run, no PS2 emulator.
- I did not apply the B1/M1 fixes to the branch (review is read-only). The B1
  fix was checked only on a scratch copy.
- I did not analyse whether POPS's heap or stack reaches the arena, or how
  the payloads interact with launcHER's own core patches (also open in the
  branch doc).
