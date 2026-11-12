# Handoff author report: ExecPS2 handoff fix (handoff doc 3.2 / 5.1)

Branch `pr23/handoff-2` (worktree `<workspace>/launcHER.worktrees/handoff-2`),
created from `ef663b2`. Pushed to origin. Head: see the end of this report.
The handoff worktree (`launcHER.worktrees/handoff`) was not modified.

**NOT TESTED on a console.** Host tests, Unicorn emulation of the original
code and PCSX2 runs only. No rig was used.

## 1. What "v2" was, and whether 72660f3 contains it

v2 is the tree of 72660f3. The trace ELF built from the handoff worktree's
`build-handoff-trace` directory has the same sha256 as the v2 build in the
first author's run log, and every file that 72660f3 changes predates that
build. So 72660f3 contains v2. Its measured runs (first author's scratch):
POPS thread ids from 2 (unfixed: from 3), report words showing success.

## 2. Commits

| Commit | What |
| --- | --- |
| `6a9353d` | wip(pops): 72660f3 ported onto ef663b2 (cherry-pick, build.yml conflict resolved by keeping both sides' steps). Left out: 72660f3's change to the pops_compat_db title lookup (exact title) and its test in test_pops_features.py (see owner questions). A comment in handler_pops.c reworded so test_pops_launch_hooks's `%ll` check does not match the comment. |
| `77d1a40` | test(pops): `tools/trace_original_pops_handoff.py` runs r13's MAIN 0x87c0d4..0x87c1d0 as shipped under Unicorn; `tools/test_pops_handoff.py` gets a `Differential` class comparing it with the trampoline. |
| `890a6a3` | docs(pops): `docs/POPSTARTER_HANDOFF.md` gets a new top section "ExecPS2 handoff (2026-11-11)"; the October content stays below, unchanged, as history. |

Files the fix consists of (all inside the POPS launch path):
`common/include/pops_handoff.h`, `common/src/pops_handoff.c`,
`launcher/include/pops_handoff_ee.h`, `launcher/src/pops_handoff_ee.c`,
`launcher/src/handler_pops.c` (one call before the jump, one DPRINTF format),
`launcher/src/pops_trampoline.S` (DI loop), `launcher/CMakeLists.txt` (new
sources, POST_BUILD layout check), `tools/check_pops_handoff_layout.py`,
`tools/r5900_mini.py`, `tools/test_pops_handoff.py`,
`tools/trace_original_pops_handoff.py`, `tools/test_pops_launch_hooks.py`
(one test), `.github/workflows/build.yml` (step "Test the POPS handoff (one
thread left, interrupts off before the clears)" after test_pops_user_bios.py).
No shared launch, storage-driver or Ember code changed.

## 3. The fix and its justification

Each step, with the kernel (SCPH-39001, EE RAM dump) or r13 address it rests on:

1. Defect: ExecPS2 (syscall 7: 0x80002f80 → 0x800057e8) loops tids 1..255;
   a non-DORMANT thread goes through iTerminateThread 0x80003e00, whose reset
   routine 0x80003bb8 writes gp/sp/fp/ra at stack+size-0xe0/-0xd0/-0xc0/-0xb0.
   A DORMANT thread is only deleted (0x80003f00). launcHER's one extra thread
   is ps2sdk libkernel's `topThread` (0x400-byte BSS stack, above 0x200000 in
   current builds), so the words land in the freshly copied POPS core.
2. Retire before the trampoline: TerminateThread (syscall 0x25 → 0x80003140)
   when not DORMANT, then DeleteThread (0x21 → 0x80002fc0), for every other
   tid 1..255. The rewrite then lands in launcHER memory that the core copy
   overwrites. A pre-check refuses (-EFAULT, nothing changed) if any such
   frame overlaps the protected ranges 0x80000..0x100000 and the staging area.
3. Slot order: free queue is FIFO (take 0x80005b00 = head->prev; add
   0x80005bb0 = head->next). Deleting tid 2 puts it at the back, so POPS's
   first CreateThread would get 3 instead of 2 (measured on the unfixed
   build). The code drains all free slots with DORMANT placeholders
   (CreateThread 0x20 → 0x80003c50), verifies the retired slots came out
   last in retirement order, deletes those first and the rest after; the
   queue is then 2..255 as before topThread existed. Otherwise it releases in
   reverse (queue as found) and reports mode 2.
4. Interrupts: the trampoline zeroes 0x100000..0x200000 (launcHER's code,
   including its TIM2 INTC 11 and SIF0 DMAC 5 handlers). A ps2sdk-style DI
   loop now runs before the first store. ExecPS2 empties the INTC lists
   (except SBUS) and DMAC lists and returns via di at 0x80002fa8, so POPS
   starts with EIE = 0 either way, as after r13. FlushCache (syscall 0x64 →
   0x80002a40) does not ei.
5. r13 parity: r13 has no CreateThread/StartThread/TerminateThread/
   DeleteThread stubs, so it reaches ExecPS2 as the only thread; it calls
   ExecPS2 once (single restart), which is why the two-stage ExecPS2
   alternative was rejected.

## 4. Builds (Docker, ghcr.io/ps2homebrew/ps2homebrew:main)

Command (per build; `<scratch>/hs/build.sh SRC DIR KIND LOG`):

    MSYS_NO_PATHCONV=1 docker run --rm -v "$(cygpath -w SRC):/workspace" -w /workspace \
      ghcr.io/ps2homebrew/ps2homebrew:main sh -c "apk add cmake >/dev/null && \
      git config --global --add safe.directory /workspace && \
      cmake -B DIR [-DLAUNCHER_BOOT_TRACE=ON -DDEBUG=ON] && cmake --build DIR --target launcHER"

| Build | Source | rc | Time | Warnings | launcHER.elf | sha256 (prefix) |
| --- | --- | --- | --- | --- | --- | --- |
| unfixed trace | `<scratch>/src-ef663b2` (git archive of ef663b2 + submodule content) | 0 | 78 s | 35 | 331,572 | d7575603 |
| fixed release | handoff-2 @ 6a9353d sources | 0 | 81 s | 34 | 327,700 | e67f512c |
| fixed trace | handoff-2 @ 6a9353d sources | 0 | 70 s | 24 | 332,292 | c635c750 |

77d1a40 changed only tools/, so these ELFs are the head's firmware.
The first archive build failed (missing submodules, mmceman chdir); fixed by
`git submodule update --init` and copying submodule content.

POST_BUILD layout check output:
- release: image 0x00100000..0x00210ea0, trampoline 288 bytes at 0x0010ad78,
  AddIntcHandler 1 site, AddDmacHandler 1 site, CreateThread 2 sites, no
  symbols; OK.
- trace: image 0x00100000..0x00214c60; helper stack reset frame
  0x208fa0..0x209240, placeholder frame 0x203db0..0x204050, SIF pktbuf
  0x209580..0x209600, all inside POPS memory (reported, not failed); OK.
- Disassembly of the fixed trace ELF: plain syscall stubs TerminateThread
  0x12b2a0 (0x25), DeleteThread 0x12b290 (0x21), CreateThread 0x12b280,
  ReferThreadStatus 0x12b2c0 (0x30), GetThreadId 0x12b2b0 (0x2f).

## 5. Emulator runs (PCSX2, private tier folder only, one at a time)

Harness: `<tier>/run_tier.py` via `<scratch>/hs/run_lh.sh NAME ELF TIER MODE`
(`<tier>` = the private pcsx2-tier folder). All runs: `--gameargs
ata:/POPS/TEST.VCD --hdd-image images/hdd_fat32_vmc.img`; interpreter =
`--set EmuCore/CPU/Recompiler:EnableEE=false`.
- t1: `--timeout 150 --marker "Transferring control to trampoline" --fail-marker "[ps2rig] exit=1"`
- t2: `--timeout 200 --after "<AFTER>" --marker "<MARKER>" --fail-marker "Trap exception at" --fail-marker "[ps2rig] exit=1" --fail-marker "TLB Miss, pc=0x0 " --fail-marker "Jump to unaligned" --linger 8 --dump 80000000:100000 --dump 200000:302e60`
  (AFTER default "Transferring control to trampoline", release: "SDR driver version"; MARKER default "Interlaced (FIELD)")
- park: as t2 with `--poke-on "POPS: Rebooting IOP with external image" --poke 1000008=1000ffff --poke 100000c=0 --poke-repeat 60 --poke-interval 0.005`, MARKER "# Restart Without Memory Clear Done.", plus `--dump 1000000:302e60`.

| Time | Run | ELF | Tier/CPU | rc | Wall | Verdict | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 15:37:47 | unfixed-t2-interp-1 | unfixed trace | t2 interp | 1 | 60 s | FAIL (Trap exception at) after 57.1 s | "Trap exception at 0x00208660" 0.36 s after the handoff line; = topThread stack 0x208340 + 0x320 (stack+size-0xe0) |
| 15:43:52 | fixed-t1-rec-1 | fixed trace | t1 rec | 0 | 27 s | PASS after 23.6 s | |
| 15:44:31 | fixed-t1-rec-2 | fixed trace | t1 rec | 0 | 29 s | PASS after 24.8 s | |
| 15:45:06 | fixed-t1-rec-3 | fixed trace | t1 rec | 0 | 27 s | PASS after 24.3 s | |
| 15:45:55 | fixed-t2-interp-1 | fixed trace | t2 interp | 0 | 44 s | PASS after 41.6 s | report OK; POPS tids 2,3,4,5,8,9 |
| 15:46:41 | fixed-t2-interp-2 | fixed trace | t2 interp | 0 | 44 s | PASS after 41.1 s | same |
| 15:47:31 | fixed-t2-interp-3 | fixed trace | t2 interp | 0 | 45 s | PASS after 42.7 s | same |
| 15:48:28 | fixedrel-t2-interp-1 | fixed release | t2 interp, AFTER "SDR driver version" | 0 | 51 s | PASS after 47.2 s | same |
| 15:49:28 | fixed-park-interp-1 | fixed trace | park interp | 0 | 52 s | PASS after 47.9 s | live core 0x200000.. vs staged core: 0 words differ |
| 15:50:16 | unfixed-park-interp-1 | unfixed trace | park interp | 0 | 42 s | PASS after 38.4 s | 4 words differ: 0x208660 = 0x00205970 (_gp), 0x208670 and 0x208680 = 0x00208720 (stack+0x3e0), 0x208690 = 0x0012daf0 (ExitThread) |
| 15:51:37 | fixed-t2-rec-1 | fixed trace | t2 rec, MARKER "# Restart Without Memory Clear Done." | 0 | 40 s | PASS after 35.3 s | report OK |
| 15:52:12 | unfixed-t2-rec-1 | unfixed trace | same | 1 | 29 s | FAIL (TLB Miss, pc=0x0) after 25.0 s | right after the handoff line; no kernel restart line; thread 1 still launcHER's main (entry_ 0x100fe0), tid 2 = topThread (stack 0x208340). INFERRED: an interrupt handler ran after its code was zeroed. |

Report words (0x84300) in every fixed run: magic 0x464f4850, result 0,
self 1, retired 1, first 2, drained 254, queue 1 (restored), failed 0.
(The unfixed build has no report code; its words there are unrelated.)

Thread ids: the fixed runs show POPS's threads at 2,3,4,5,8,9. The only
POPStarter control with a kernel dump is a USB run (`20261111T103853-vdyn-
control-usb-interp`, earlier session): 2,3,4,7,8 (one thread fewer, the ATA
device thread is absent), the same pattern from 2. No ATA control run with a
kernel dump exists; one was not made here.

Emulator-tier note: runs 1..9 (batch1) and 10..11 (batch2) ran from
`<scratch>/hs/batch1.sh` and `batch2.sh`; each run's harness log is in
`<scratch>/logs/run_<name>.txt`, the list in `<scratch>/hs/runs.log`. The
run's hdd.raw copy was deleted after each run. Another PCSX2 process (not
mine, a different folder and PINE slot) was running; it was not touched.

## 6. Host tests

Runner: `<scratch>/hs/hosttests.sh LABEL without|with`. It runs each of
the 33 `tools/test_*.py` one at a time from the worktree root with Git Bash
and `python tools/<test>.py`. TMP, TEMP and TMPDIR are set to a freshly
emptied `<scratch>/tmp-handoff-2`. Per-file logs are in
`<scratch>/hs/hostlogs-<label>/`, summaries in `<scratch>/hs/hosttests-<label>.log`.
Both passes ran at head 890a6a3, after all emulator runs, never alongside
another test.

- **Without reference variables** (POPS_TEST_ELF, POPSTARTER_TEST_ELF,
  POPS_TROJAN_CORPUS, POPS_HANDOFF_ELF unset, as in CI): 33/33 files rc=0.
  test_pops_handoff: 27 tests OK, 8 skipped (Original, Differential and
  BuiltImage need inputs). test_pops_user_bios has 1 expected failure, which
  was there before this work.
- **With them set** (the three reference inputs, plus
  POPS_HANDOFF_ELF=`<scratch>/elfs/fixed-trace_unc.elf`): 33/33 files rc=0.
  test_pops_handoff: 27 tests OK, 0 skipped. That includes the four
  Differential tests against r13 and BuiltImage on the fixed trace ELF.
  The remaining skips are in other files: test_pops_external 3,
  test_pops_launch_hooks 3, test_pops_progressive 3. test_pops_user_bios
  still has 1 expected failure.

Per file, with inputs (seconds): launch_args 5, network_transports 8,
popfs 6, pops_breakpoint 22, builtin_db 46, config_text 197, display 23,
doc_claims 3, external 57, fatfs 4, features 31, fix_files 13, handoff 16,
igr_skin 45, io_probe 1, launch_hooks 49, modes 14, module_irx 25,
opcodes 16, padman 22, physical_disc 146, progressive 15, read_trace 16,
resident 57, runtime_corrections 19, smb_config 27, startup_calls 1,
user_bios 57, vmc 2, warmboot 37, smap_ipconfig 1, sony_ioman_layout 2,
subq_bridge 5.

Mutation check (`<scratch>/hs/mutate.sh`): each mutation was applied to
`launcher/src/pops_trampoline.S`, `python -m unittest tools.test_pops_handoff`
was run with the reference inputs, and the file was restored with git.

| Mutation | Result |
| --- | --- |
| low-RAM clear ends at 0x1f0000 | FAIL: Differential.test_same_memory_below_the_original_when_execps2_is_called and Trampoline.test_interrupts_are_off_before_the_first_store |
| di replaced with nop | FAIL/ERROR: Differential.test_interrupts and three Trampoline/Source tests |
| FlushCache(2) changed to FlushCache(1) | FAIL: Differential.test_same_calls_up_to_execps2_apart_from_the_service_reinit |

The worktree was clean afterwards.

Earlier in the session: after the cherry-pick, test_pops_launch_hooks first
failed. Its `%ll` check matched a comment, and the comment was reworded.
The Differential class first raised a TypeError, fixed with staticmethod.
After 77d1a40, test_pops_handoff with inputs gave 27 OK with 1 skip
(BuiltImage, POPS_HANDOFF_ELF unset at the time).

## 7. What is not done

- No console run (no rig used, as instructed). NOT TESTED on a console.
- No ATA POPStarter control run with a kernel dump, so the exact thread id
  set is compared only against a USB control.
- No full game boot beyond POPS's video setup / "SDR driver version".
- Release build ran tier 2 once (as asked), not three times.
- r13's six service re-init calls are not copied (owner question).
- The 6a9353d commit message still starts "wip(pops):" (history not
  rewritten). The later commits complete it; nothing on the branch is
  untested on the host or in PCSX2, everything is untested on a console.

## Branch head

`pr23/handoff-2` at `890a6a3d8a835c8074b858cddfbbb5f24c835ffe`, pushed (no
force). Commits since ef663b2: 6a9353d, 77d1a40, 890a6a3. Checked for AI
attribution: none.

## 8. Proposed quirk text (for docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md; coordinator numbers it)

**SIF command buffer left in POPS memory at the handoff (INFERRED).**
launcHER does not repeat r13's fioExit, SifExitRpc, SifInitRpc(0),
SifLoadFileInit, SifInitCmd, fioInit between FlushCache(2) and ExecPS2
(r13 MAIN 0x87c0d4..0x87c1d0). The IOP's last-known EE address of the SIF
command packet buffer is therefore launcHER's, inside the memory POPS takes
(fixed trace build 0x209580..0x209600; unfixed ef663b2 trace 0x208a80).
r13's SifInitCmd re-init points it at r13's own memory, which survives.
Not measured to cause a fault; the IOP is rebooted by POPS soon after.

**Thread id parity holds only for extra threads taken in id order.**
popsHandoffRetireThreads restores the free queue exactly when launcHER's
extra threads were taken from the front of the queue in id order (true for
the one helper thread in current builds). If a future build creates and
deletes threads in another order, the queue is released as found and POPS's
thread ids may differ from r13's (report word queue = 2).

## 9. Proposed status rows

| Item | Status | Evidence |
| --- | --- | --- |
| ExecPS2 rewrites the helper thread frame inside POPS's core (3.2/5.1) | Fixed on `pr23/handoff-2`; host + Unicorn differential + PCSX2 (recompiler t1 3/3, interpreter t2 3/3, release t2 1/1, park 0-word diff); NOT TESTED on a console | this report, docs/POPSTARTER_HANDOFF.md |
| Interrupts live while the trampoline zeroes launcHER | Fixed (DI before first store); unfixed recompiler run crashes at pc 0 right after the handoff, fixed passes; cause INFERRED; NOT TESTED on a console | same |
| POPS thread ids after the handoff | 2,3,4,5,8,9 in PCSX2 (ATA), from 2 as in a USB r13 control; unfixed gives ids from 3 | same |
| r13 service re-init before ExecPS2 | Not copied; owner question | same |

## 10. Owner questions

1. 72660f3 also changed the pops_compat_db title lookup to an exact title
   match (tied to the tekken rule) with a test in test_pops_features.py. It
   is not part of the handoff defect and was left out here. Keep it out, or
   take it in a separate branch?
2. docs/POPSTARTER_HANDOFF.md: the new section is prepended and the October
   content kept unchanged below as history. Acceptable, or move the October
   content to docs/history/?
3. r13's six service re-init calls (fioExit, SifExitRpc, SifInitRpc(0),
   SifLoadFileInit, SifInitCmd, fioInit) before ExecPS2 are not copied.
   Parity says copy them; launcHER's trampoline runs after its own code is
   zeroed, so they would have to run before the trampoline (from C), which
   changes when the RPC services go away. Copy them?
4. A two-stage handoff (ExecPS2 into a stub, then a second ExecPS2 into
   POPS) would avoid the thread work but gives two kernel restarts where r13
   gives one; rejected here for parity. Confirm.
