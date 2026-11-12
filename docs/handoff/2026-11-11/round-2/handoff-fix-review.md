# Review: ExecPS2 handoff fix, `pr23/handoff-2`

Reviewed: `origin/codex/popstarter-replacement` (ef663b2) ... `origin/pr23/handoff-2`
(890a6a3d8a835c8074b858cddfbbb5f24c835ffe). Three commits: 6a9353d (port of
72660f3), 77d1a40 (r13 differential under Unicorn), 890a6a3 (docs).

Read-only toward the branch: nothing committed or pushed. Work was done in a
detached worktree `<scratch>/review-handoff/tree`, which was removed at the end.

**NOT TESTED on a console.** Everything below is host tests, Unicorn emulation,
a reading of an SCPH-39001 kernel RAM dump, or PCSX2 runs. A PCSX2 pass is an
emulator result.

**Verdict: merge after fixes.** All the findings are minor: wording in the
documents, notes about parity, and gaps that were already there and are now
pinned. I found no correctness defect in the fix. I reproduced every central
claim myself.

## 1. What I checked, and the results

### 1.1 Host tests (33 files, one at a time, Git Bash, from the worktree root)

Runner: `<scratch>/review-handoff/run_tests.sh`. Each run used fresh empty
TMP/TEMP/TMPDIR folders: `<scratch>/tmp-review-handoff-noinputs` and
`<scratch>/tmp-review-handoff-inputs`.

- **Without reference inputs** (POPS_TEST_ELF, POPSTARTER_TEST_ELF,
  POPS_TROJAN_CORPUS and POPS_HANDOFF_ELF unset, as in CI): **33/33 rc=0**.
  test_pops_handoff: 27 tests, OK, 8 skipped. test_pops_user_bios: OK
  (13 skipped, 1 expected failure, the known case in handoff doc 5.5).
  Log: `<scratch>/review-handoff/logs-noinputs.txt` (+ per-file `.out`).
- **With reference inputs** (the three reference variables, plus
  POPS_HANDOFF_ELF = my own trace build's `launcher_unc.elf`): **33/33
  rc=0**. test_pops_handoff: 27 tests, OK, 0 skipped. That includes the four
  Differential tests against r13 under Unicorn and BuiltImage on my ELF. Log:
  `<scratch>/review-handoff/logs-inputs.txt`.
- unicorn 2.1.4 is installed on this host. CI's `host-tests` job does not
  install it and sets no reference variables, so Original, Differential and
  BuiltImage skip there. The Native/Trampoline/Source parts need only gcc and
  Python, which ubuntu-latest has. The new step is in the `host-tests` job,
  after test_pops_user_bios.py. Expect the PR head to stay green in CI.

### 1.2 Mutations (my own, with reference inputs; tree restored with git afterwards, `git status` clean)

Script: `<scratch>/review-handoff/mutate.py`.

| Mutation | Result |
| --- | --- |
| trampoline `di` -> `nop` | rc=1: Differential.test_interrupts FAIL, 3 Trampoline/Source ERROR |
| trampoline scratchpad clear ends at 0x70003f00 | rc=1: Differential.test_same_memory_below_the_original_when_execps2_is_called FAIL |
| pops_handoff.c: retired slots not released in the FIFO branch | rc=1: 5 Native tests FAIL |
| pops_handoff.c: pre-check ignores the protected ranges | rc=1: Native.test_a_frame_in_prepared_memory_is_refused_before_anything_changes FAIL |

The tests pin both the trampoline and the retire logic.

### 1.3 Target builds (Docker, ghcr.io/ps2homebrew/ps2homebrew:main)

Source: a `git archive` of 890a6a3, plus `git archive` of the two submodules
at the recorded commits (db3e93f mmceman, 33ff564 psxcore), in
`<scratch>/review-handoff/src`. Builds used the author's script
`<scratch>/hs/build.sh` with build folders `build-rvh-trace` and
`build-rvh-rel`.

| Build | rc | Time | launcHER.elf | sha256 |
| --- | --- | --- | --- | --- |
| trace (-DLAUNCHER_BOOT_TRACE=ON -DDEBUG=ON) | 0 | 70 s | 332,292 B | c635c750...ac2d0, **identical** to the author's fixed trace |
| release | 0 | 60 s | 327,700 B | e67f512c...38269, **identical** to the author's fixed release |

The POST_BUILD layout check printed "handoff layout: OK" on both builds. The
trace build reports: helper-thread reset frame 0x208fa0..0x209240,
placeholder frame 0x203db0..0x204050, SIF pktbuf 0x209580..0x209600, all
inside POPS memory (reported, not failed), and trampoline 288 bytes at
0x10bbd8. Release: trampoline at 0x10ad78, no symbols. My warning counts (35
trace, 23 release) differ from the author's (24 trace), because the author
built in a worktree with earlier build state. This does not matter.

### 1.4 Emulator (one run, as allowed)

No pcsx2 process and no run_tier/pcsx2-tier process were running before the
run (checked with Win32_Process). I ran one tier-2 interpreter run of my own
trace build from the private tier folder (`<scratch>/review-handoff/emu_t2.sh`):

    python run_tier.py --elf <my trace launcHER.elf> --gameargs "ata:/POPS/TEST.VCD" \
      --hdd-image images/hdd_fat32_vmc.img --timeout 200 \
      --set EmuCore/CPU/Recompiler:EnableEE=false \
      --after "Transferring control to trampoline" --marker "Interlaced (FIELD)" \
      --fail-marker "Trap exception at" --fail-marker "[ps2rig] exit=1" \
      --fail-marker "TLB Miss, pc=0x0 " --fail-marker "Jump to unaligned" --linger 8 \
      --dump 80000000:100000 --dump 200000:302e60 --name review-handoff-t2-interp --tail 3

Result: **PASS after 44.2 s** (wall 49 s), run `20261111T164010-review-handoff-t2-interp`.
The handoff line came at 32.65 s, the kernel restart at 32.75 s and POPS's
"Interlaced (FIELD)" at 34.39 s. There was no trap. The harness's hdd.raw
copy was deleted afterwards, as the author did.

From its dumps (decoded with the author's `<scratch>/hs/kstate.py`):
- Report words at 0x84300: magic 0x464f4850, result 0, self 1, retired 1,
  first 2, drained 254, queue 1 (restored), failed 0.
- POPS threads: tid 2,3,4,5,8,9 (entries 0x236448, 0x2147f0, 0x210220,
  0x20c838, 0x23aa90, 0x21c6a0).
- The four words the kernel writes in the unfixed case (0x208660, 0x208670,
  0x208680, 0x208690): in my live core they equal POPS.ELF's core. In the
  author's unfixed run they are 0x00205970, 0x00208720, 0x00208720 and
  0x0012daf0. Comparing the first MiB of each live core with POPS.ELF: 11,279
  words differ in mine and 11,283 in the unfixed run. The difference is
  exactly those 4 words; the rest are launcHER's core patches, present in
  both.

### 1.5 The author's emulator evidence, re-read from the run folders

I decoded the kernel dumps of all the author's fixed interpreter runs.
- fixed-t2-interp-1/2/3 and fixedrel-t2-interp-1: report words as above.
  POPS tids 2,3,4,5,8,9. Confirmed.
- fixed-park-interp-1: report words as above. **Only tids 0 and 1 exist**,
  because POPS is parked at its entry (see finding 2).
- unfixed-t2-interp-1: POPS tids 3,4,5,6,9,10. Confirmed "from 3".
- r13 USB control `20261111T103853-vdyn-control-usb-interp`: tids 2,3,4,7,8.
  By entry address the threads match launcHER's one for one, except the one
  at 0x2147f0 (launcHER's tid 3), which is absent there. 2,3,4,(5,6
  transient),7,8 against 2,3,4,5,(6,7 transient),8,9 is what a FIFO free
  queue gives with one thread fewer. This supports the doc's "same pattern
  from 2", as an inference for ATA.
- Syscall table after POPS start: 0x8, 0x55..0x5c, 0x3c and 0x3d are
  identical in my fixed run and in the r13 control (0x5a -> 0x2354a0 in both).
  launcHER's ps2sdk patches leave nothing behind that POPS does not replace.
  This was not claimed anywhere; it is an extra data point.
- Unfixed trace emulog: "POPS: Disc region 3 (licence at 0xlx)"; fixed:
  "... 0x102514". Confirms the reason for the `%ll` change.

### 1.6 Kernel facts the fix rests on (SCPH-39001, read from the fixed run's EE RAM dump with the committed `docs/handoff/2026-11-11/handoff-fix-scratch/ksys.py`)

- Syscall 7 -> 0x80002f80. That routine calls 0x800057e8, then returns
  through `di` at 0x80002fa8, `mfc0`/`ori 0x13`/`mtc0` Status, and `eret`.
  POPS therefore starts with EIE = 0 whatever the caller's EIE was.
  Confirmed.
- 0x800057e8 loops s1 = 1 .. 0xff: a DORMANT slot (status 0x10) gets
  `jal 0x80003f00` (delete) only; any other non-free slot gets
  `jal 0x80003e00` (terminate) then `jal 0x80003f00`. Confirmed.
- The reset routine at 0x80003bb8 stores at +0x1c0, +0x1d0, +0x1e0 and
  +0x1f0 from the frame base (stack + size - 0x2a0). Confirmed.
- Free list: 0x80005b00 takes head->prev; 0x80005bb0 inserts after head
  (head->next). So it is first in, first out. Confirmed.
- Syscall 0x20 -> 0x80003c50, 0x21 -> 0x80002fc0, 0x25 -> 0x80003140,
  0x64 -> 0x80002a40. The FlushCache body has no ei and no Status write.
  Confirmed.
- Status 0x70030c11 (EDI set, so the user-mode di loop works): the value is
  from the earlier emulator probe in `handoff-defect-emulator.md`.

### 1.7 Code review

- `common/src/pops_handoff.c`: bounds are correct (at most 254 retired,
  creates capped at 255, all ids checked to be 1..255 and unique). The
  pre-check runs before anything is terminated. A failed terminate shows up
  as a failed delete (-EBUSY). On a FIFO free list, the restore order
  (retired slots first, then the rest) gives back the queue as it was before
  launcHER's live threads were created. The final sweep guarantees no
  leftover thread. No defect found.
- `launcher/src/pops_handoff_ee.c`: the glue is plain syscall stubs (the
  checker verified this on both builds). The placeholders share one
  0x400-byte BSS stack and are never started. The protected ranges cover the
  trampoline, its arguments, its stack and the report words
  (0x80000..0x100000), and the staging, built-in fix, breakpoint and
  resident areas (0x1000000..0x1800000). Report words are at
  0x84300..0x84320; PopsTrampolineArgs ends at 0x842b0; the trampoline,
  limited to 0x180 bytes, ends at most at 0x84180. No overlap.
- `launcher/src/pops_trampoline.S`: `move s0,a0; li sp; di` loop, then the
  same clears, copy, FlushCache(0/2) and ExecPS2 as before. One ExecPS2, as
  in r13.
- `handler_pops.c`: the retire call comes after the preflight stop and right
  before the jump, with only its error check between them (pinned by
  Source.test_threads_are_retired_right_before_the_jump).
- Port fidelity: compared with 72660f3, pops_handoff.c, pops_handoff_ee.c,
  pops_trampoline.S and the checker are byte-identical apart from one doc
  path in a comment. The compat-db title change is left out, as stated.
- Outside the POPS launch path: no runtime behaviour change. Things that
  touch shared ground: the POST_BUILD layout check (a build-wide gate, see
  finding 9), the `%ll` scan in test_pops_launch_hooks (finding 8), and the
  COP0 support in r5900_mini (a test tool; all its users pass). No Ember,
  storage-driver or shared launch code changed.
- Binaries, hashes, tables: no binary file in the diff, no hash and no long
  hex string (grep for 32+ hex characters, sha/md5/base64: none). The tests
  assert about 20 single r13 instruction words at named addresses
  (`Original` class). This follows the existing practice in
  `tools/test_pops_doc_claims.py`; it is not a table.
- Attribution, email: none in the diff or in the three commit messages.
  Author identity is the noreply address.

## 2. Findings

1. **minor**: `docs/POPSTARTER_HANDOFF.md` says the layout checker "fails
   the build if the trampoline, its arguments, the report words or the
   placeholder stack frame would collide with memory that must survive". The
   checker
   (`tools/check_pops_handoff_layout.py`) checks the image range, that the
   trampoline appears once and is at most 0x180 bytes, that di comes before
   the first store and syscall, that the five syscall stubs exist and are
   called, and that the magic is built once. It never looks at
   PopsTrampolineArgs or the report-word address. The placeholder frame is
   covered only indirectly, through the image range. Fix: reword ("fails the
   build if the image leaves 0x100000..0x1000000, the trampoline is not the
   source or is over 0x180 bytes, ..."), or add a static assert that
   `POPS_TRAMPOLINE_ARGS + sizeof(PopsTrampolineArgs) <= POPS_HANDOFF_REPORT_ADDR`.
2. **minor**: the doc says "In all five fixed interpreter runs ... POPS's
   threads have ids 2, 3, 4, 5, 8, 9." The park run's kernel dump has only
   tids 0 and 1, because POPS is parked at its entry and never creates a
   thread. The ids hold for 4 of the 5 runs. The report words do hold for
   all 5. The author's summary ("Every fixed run ... POPS's thread ids are
   2,3,4,5,8,9") also stretches it: the t1 runs have no dumps. Fix: "in the
   four interpreter runs that reached POPS's video setup".
3. **minor**: the report words are a new launcHER-only residue, in release
   builds too: 32 bytes at 0x84300 that r13 leaves as found (the r13 control
   dump shows unrelated older content there). They are not listed in "Not
   the same as r13". Fix: list them there (and as a quirk), or write them
   only in trace builds. The release emulator run used them, so a trace-only
   choice would lose that check.
4. **minor**: the three tier-1 recompiler runs end at "Transferring control
   to trampoline". launcHER prints that line before
   `popsHandoffRetireThreads()` and before the trampoline runs, so these
   runs do not exercise the fix. Only one recompiler run (fixed-t2-rec-1)
   goes past the handoff. The task asked for tier 1, so the runs are
   legitimate. The doc table should say they end before the fixed code, so
   readers do not count them as fix evidence.
5. **minor**: code comments and docstrings state the thread-id parity as a
   fact: `common/include/pops_handoff.h` ("POPS's threads would get ids one
   higher than after POPStarter") and the docstring of
   `tools/test_pops_handoff.py` ("so POPS's threads get the ids they get
   after POPStarter"). It was measured only against a USB r13 control with
   one thread fewer (INFERRED for ATA, see 1.5). The doc body qualifies it
   correctly. Fix: qualify the comments too, or make an ATA r13 control run
   with a kernel dump.
6. **minor (parity, older than this branch, now pinned by tests)**: three
   r13 differences stay. (a) r13's six service re-init calls are not copied
   (the author raised this as an owner question). (b) Entry at 0x200008
   instead of r13's 0x200000. The kernel TCB shows it: entry_ 0x200008
   against 0x200000 in the r13 control. (c) EIE on at r13's ExecPS2 against
   off in launcHER; the end state is identical, as confirmed in 1.6. None of
   these is in section 8 of the handoff doc. Under the parity rule (a) and
   (b) should be changed or entered as quirks. (c) is justified by the
   zeroed handlers. Fix: record (a) and (b) in the quirks list and the
   status rows.
7. **minor**: 6a9353d keeps its "wip(pops):" subject and its
   "Untested here: the other host tests, the container build, the emulator"
   line. Later commits and my reruns make that stale. Not rewritten (no
   force-push), which is correct. Mention it in the merge commit or the PR
   text.
8. **minor**: `test_trace_lines_use_no_long_long_conversion` scans every
   `launcher/src/*.c` and `common/src/*.c`, not only the POPS files. A
   non-POPS change, including shared code that Ember also builds, using
   `%ll` would fail a POPS test. The claim behind it is measured (1.5).
   Fix: limit the scan to the POPS sources, or keep it and record the rule
   in the build notes.
9. **minor**: the POST_BUILD layout check is a gate for the whole build of
   `launcher_unc` (not only POPS launches). It is silently skipped when no
   `python3` is on PATH. It ran in the CI image (my builds show its output).
   Note only. If it should be mandatory in CI, fail configuration when
   python3 is missing there.
10. **minor**: on the rare failure paths after the retire loop has run
    (-EBUSY or -EIO from deletes or creates), launchPOPS returns to the menu
    with ps2sdk's helper thread already deleted, and with the trampoline
    and staging installed. Behaviour after that is not tested. The -EFAULT
    pre-check path changes nothing, as tested. Fix: note it in the doc, or
    treat any post-terminate failure as fatal (e.g. stop rather than return
    to the menu).

## 3. Claims checked against measurements

| Claim (doc / commit / summary) | Status |
| --- | --- |
| 72660f3 is v2; port fidelity | Port fidelity confirmed by diff. The v2 sha comes from the author's logs (not re-derived). |
| 33/33 host tests both ways; handoff 27 OK, 8 skipped / 0 skipped | Reproduced |
| Mutations make Differential fail | Reproduced with my own mutations |
| Release sha e67f512c, trace sha c635c750, sizes | Reproduced bit-identically |
| Unfixed t2 traps at 0x208660 = stack + 0x320 | Not rerun. The park dump of the unfixed run shows exactly those 4 words; consistent. |
| Fixed t2 interp passes | Reproduced (1 run) |
| Report words, retired 1, drained 254, queue 1 | Reproduced (my run plus the author's 5 dumps) |
| POPS tids 2,3,4,5,8,9 in all five fixed interp runs | Partly: 4 of 5 (finding 2) |
| Kernel addresses (0x800057e8 loop, 0x80003bb8 frame, FIFO list, di at 0x80002fa8) | Confirmed by disassembly of a dump |
| Layout check prevents collisions of args and report words | Not backed (finding 1) |
| Same pattern as the r13 USB control | Supported as an inference (1.5) |
| NOT TESTED on a console | Stated throughout; correct |

## 4. Commands run (summary)

- `git fetch origin`; `git worktree add --detach <scratch>/review-handoff/tree origin/pr23/handoff-2`
- `git log`, `git diff origin/codex/popstarter-replacement...origin/pr23/handoff-2`, `git diff 72660f3 origin/pr23/handoff-2 -- ...`, `git diff --check` (clean)
- `sh <scratch>/review-handoff/run_tests.sh noinputs ...`: 33/33
- `sh <scratch>/hs/build.sh <src> build-rvh-trace trace ...`: rc 0, 70 s
- `sh <scratch>/hs/build.sh <src> build-rvh-rel release ...`: rc 0, 60 s
- `HANDOFF_ELF=<trace unc> sh run_tests.sh inputs ...`: 33/33
- `python mutate.py <tree> {di-nop,spad-short,fifo-order,no-precheck}`: all 4 caught
- `sh <scratch>/review-handoff/emu_t2.sh`: PASS 44.2 s
- `python -I kstate.py` on 7 dumps, `python -I ksys.py` (table and dis) on one dump, a word comparison of the live cores against POPS.ELF
- `git worktree remove` of the review tree at the end

## 5. Proposed doc and quirk text (for the coordinator)

- Quirk: "launcHER leaves eight report words at 0x00084300 (release builds
  too) that POPStarter r13 does not write; POPS starts with them in its
  address space. Not measured to matter."
- Quirk: "launcHER enters POPS at 0x00200008 (ELF entry), r13 at
  0x00200000; the two words in between are nops, but the kernel thread
  table records the different entry for thread 1."
- Status row: "POPS thread ids after the handoff: 2,3,4,5,8,9 in PCSX2 (ATA,
  4 runs incl. release); r13 control only on USB (2,3,4,7,8, one thread
  fewer, matching by entry address); ATA r13 control not made; NOT TESTED
  on a console."
- Doc fix wording for findings 1, 2 and 4, as given above.

## 6. Open questions for the owner

1. Copy r13's six service re-init calls (from C, before the trampoline), or
   record the difference as a quirk? (Same as the author's question 3.)
2. Enter POPS at 0x200000 as r13 does?
3. Keep the report words in release builds?
4. On a failure after the helper thread is gone, return to the menu (today)
   or stop?
