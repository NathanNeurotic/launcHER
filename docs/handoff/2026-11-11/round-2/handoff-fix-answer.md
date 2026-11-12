# Handoff review follow-up: `pr23/handoff-2`

Branch `pr23/handoff-2`, pushed without force. It was at 890a6a3 after
`git pull --ff-only` (already up to date). Two commits on top:

- `da77546` wip(pops): enter POPS at 0x200000 as r13; pin the low-RAM layout
  at compile time. The subject still says wip because the host suite, the
  builds and the emulator had not run when it was committed. All of them ran
  afterwards on exactly this tree; see below.
- `1287592` docs(pops): handoff review follow-up (docs/POPSTARTER_HANDOFF.md).

Head: `128759275ef80f3df4d127c79b5bd12af176a497`.

**NOT TESTED on a console.** Every result below comes from a host test,
Unicorn emulation, or PCSX2. A PCSX2 pass is an emulator result.

## Per finding

Beyond the findings, the review's own section 6 raises a parity point
(6b): launcHER entered POPS at 0x00200008, r13 at 0x00200000. Section 8 of
the handoff doc does not list it as an owner decision, so under the parity
rule I changed it. Details under finding 6.

1. **The doc overstated the layout checker. Fixed.** The checker
   paragraph in docs/POPSTARTER_HANDOFF.md now lists only what
   tools/check_pops_handoff_layout.py checks. That list was read from the
   checker: the image range, the assembled trampoline appears once and is
   at most 0x180 bytes, di comes before the first store and syscall, the
   five thread stubs exist and are called, the magic is built once, plus the
   DEBUG-only notes. The doc also says what the checker does not check. I
   also added the static asserts the review suggested, in
   `common/src/pops_handoff.c`, so both the EE build and the host gcc build
   compile them:
   - `POPS_TRAMPOLINE_ADDR + 0x180 <= POPS_TRAMPOLINE_ARGS`
   - `POPS_TRAMPOLINE_ARGS + sizeof(PopsTrampolineArgs) <= POPS_HANDOFF_REPORT_ADDR`
   - `POPS_HANDOFF_REPORT_ADDR + 8*sizeof(int32_t) <= 0x0008fff0` (the
     trampoline's stack top)

   Mutation check by hand, on a scratch copy at `<scratch>/hfix/mut`: with
   the report address set to 0x84280, or with arg_strings grown to 256
   bytes, gcc stops with "static assertion failed: the trampoline's
   arguments would run into the handoff report words". The unchanged copy
   passes with -Wall -Wextra -Werror. New host test
   `Native.test_the_pieces_below_1_mib_are_kept_apart_at_compile_time`
   pins that the asserts are present and checks the arithmetic
   (0x84200 + 176 = 0x842b0, which is at most 0x84300).
2. **The doc counted the park run among the thread-id runs. Fixed.** The
   doc now says the ids 2,3,4,5,8,9 hold in the ten fixed runs where POPS
   got past its entry. They do not hold in the park run, which has only
   tid 0 and tid 1. I re-decoded every dump with kstate.py. The 890a6a3
   runs are interp 1..3, release, rec and park; the da77546 runs are
   interp 1..3, release and rec. Report words: result 0, retired 1, first
   2, drained 254, queue 1 in all 11 fixed runs that have dumps. Ids
   2,3,4,5,8,9 in all except the park run. The unfixed run gives
   3,4,5,6,9,10.
3. **The report words are a launcHER-only residue in release builds.
   Documented, not changed. Owner question.** It is now listed under "Not
   the same as r13" with the reasoning. 0x80000..0x90000 holds launcHER's
   trampoline (0x84000), its arguments (0x84200) and its stack in every
   build, and r13 has none of that. So writing the words only in trace
   builds would still not make that memory match r13, and the release build
   would lose its only check after the handoff. Proposed quirk text is
   below.
4. **The tier-1 runs end before the fixed code. Fixed in the doc.** The
   PCSX2 table row now says the tier-1 marker is printed before the retire
   call and the trampoline, so those runs end before the fixed code. This
   round adds no tier-1 runs, because tier 1 cannot exercise this change.
5. **The thread-id parity was stated as fact. Qualified.** The comment in
   `common/include/pops_handoff.h` and the docstring of
   `tools/test_pops_handoff.py` now say what was measured: PCSX2 gives ids
   from 3 unfixed and from 2 fixed. The match with POPStarter on ATA is
   INFERRED, because the only r13 control is from USB. I made no ATA r13
   control. The tier image is a FAT32 HDD image, and POPStarter r13's HDD
   path expects its own HDD layout, which that image does not provide. I
   did not try. This is still open.
6. **Parity gaps older than this branch.**
   - (b) **Entry at 0x200008 instead of r13's 0x200000. Fixed for parity.**
     `pops_trampoline_args_init` (`common/src/pops_bootstrap.c`) now passes
     `POPS_CORE_ADDR` (0x00200000) to ExecPS2. r13's tail passes that
     constant. Its Unicorn run, with memory below MAIN filled with 0xA5,
     still calls ExecPS2(0x200000), so the value is not read from the ELF
     or from memory. POPS.ELF's e_entry is still validated as 0x200008 or
     0x200000. The two words before 0x200008 are zero (nops) in POPS.ELF
     (test) and in the staged core of the emulator dumps. Measured
     (PCSX2): in all five da77546 runs the kernel's TCB has thread 1
     `entry_ 0x00200000`. The 890a6a3 runs had 0x00200008. The r13 USB
     control has 0x00200000. Tests updated:
     - test_pops_handoff `Differential` now asserts launcHER's ExecPS2
       entry equals r13's.
     - `test_entering_at_the_core_start_runs_the_elf_entry_code` replaces
       the old "eight bytes on" test and also checks e_entry 0x200008.
     - test_pops_external asserts entry 0x200000 for an ELF entry of
       0x200008 or 0x200000, and rejects 0x200004.
     - The trampoline models in test_pops_handoff and
       test_pops_launch_hooks use 0x200000.

     This invalidates any older console evidence that relied on
     ExecPS2(0x00200008), such as the withdrawn bootstrap gate note in
     docs/history and docs/evidence/pops_resident_lifecycle.md. Those docs
     describe what ran then and were not edited.
   - (a) **Six service re-init calls. Not changed; owner question
     (already the author's question 3).** Evidence against copying them as
     the fix: the effect r13 gets from SifInitCmd (the IOP's view of the
     SIF packet buffer moves into memory that survives) would not happen in
     launcHER. launcHER's `pktbuf` is in its own BSS, inside POPS memory
     (the layout check reports 0x209580..0x209600 in the trace build).
     Re-running SifInitCmd would just point there again. The calls would
     also have to run from C before the trampoline, which changes when the
     RPC services go away. The doc says this now.
   - (c) **di versus EIE on.** Already justified (kernel 0x80002fa8). The
     doc lists it under "Not the same as r13".
7. **The 6a9353d message is stale.** History is not rewritten (no
   force-push). The 1287592 message says that 6a9353d's "wip(pops):" subject
   and its "Untested here" line are stale, and that da77546 is complete.
   Proposed PR-text line is below. I did not edit the PR, because publishing
   was not asked for.
8. **The %ll scan was too wide. Fixed.**
   `test_trace_lines_use_no_long_long_conversion` now scans only
   `launcher/src/handler_pops.c`, `launcher/src/pops_*.c` and
   `common/src/pops_*.c`. It asserts that more than 10 files are scanned, so
   an empty glob cannot pass silently. No source has a `%ll` today (grep).
9. **The POST_BUILD check is skipped silently without python3. Improved,
   not made mandatory.** CMake now gives `message(WARNING ...)` instead of
   STATUS when python3 is missing. It is not made fatal: that would affect
   every local build, which is shared ground. Both new Docker builds
   printed "handoff layout: OK".
10. **Failure after the retire loop has run. Documented, behaviour
    unchanged. Owner question.** I added a comment in `handler_pops.c`
    above the call. The doc's fix section now says that -EFAULT comes
    before any thread is touched (host test), and that -EBUSY and -EIO can
    come after the helper thread is gone, with the trampoline and the
    staging area installed, and that the menu after that is untested. Why
    not "stop": r13 has no such path. Either choice is untested. A stop is
    a certain hang; a return probably works. Neither failure has been seen.

## Commands and results

Host tests: `<scratch>/hfix/hosttests.sh LABEL with|without [HANDOFF_ELF] [tests]`.
It runs each tools/test_*.py on its own from the worktree root, in Git Bash,
with TMP, TEMP and TMPDIR set to a fresh `<scratch>/tmp-handoff-fix-LABEL`.

- `quick with`, run after the first edits on test_pops_handoff, external
  and launch_hooks: all rc=0.
- `without` (full suite, no reference variables, tree = da77546): **33/33
  rc=0**. test_pops_handoff: 28 tests, OK, 8 skipped. test_pops_user_bios:
  1 expected failure, as before.
- `with1` (full suite, POPS_TEST_ELF, POPSTARTER_TEST_ELF and
  POPS_TROJAN_CORPUS set, POPS_HANDOFF_ELF = da77546 trace
  launcher_unc.elf): **33/33 rc=0**. test_pops_handoff: 28 OK, 0 skipped,
  including Differential and BuiltImage. Other skips: external 3,
  launch_hooks 3, progressive 3. user_bios: 1 expected failure.
- `relelf with` (test_pops_handoff with the release launcher_unc.elf):
  28 OK.
- After the last doc edits, `final-without` / `final-with` for
  test_pops_doc_claims and test_pops_handoff: OK (7 and 8 skipped without
  inputs; 0 skipped with them). The rest of the suite did not change from
  da77546 to 1287592; only the doc changed.
- Static-assert mutation: see finding 1.

Container builds, run on the da77546 tree with
`sh <scratch>/hs/build.sh <worktree> build-hfix-{rel,trace} {release,trace} <log>`
(ghcr.io/ps2homebrew/ps2homebrew:main):

| Build | rc | Time | Warnings | launcHER.elf | sha256 |
| --- | --- | --- | --- | --- | --- |
| release | 0 | 60 s | 23 | 327,652 B | dfbbe0ba...b457ac |
| trace (-DLAUNCHER_BOOT_TRACE=ON -DDEBUG=ON) | 0 | 60 s | 24 | 332,292 B | 05d5e7cb...990ece |

Both printed "handoff layout: OK". In the trace build: trampoline 288 bytes
at 0x10bbd8, helper reset frame 0x208fa0..0x209240, placeholder
0x203db0..0x204050, SIF pktbuf 0x209580..0x209600. The ELFs were copied to
`<scratch>/hfix/elfs/`.

Emulator: run from the private tier folder only, through the author's
`<scratch>/hs/run_lh.sh`. The batch is `<scratch>/hfix/batch.sh`, the log
`<scratch>/hfix/runs.log`. Before the batch I checked Win32_Process: no
pcsx2 or run_tier process was running. One run at a time. hdd.raw was
deleted after each run. RIPPCSX2 and pcsx2-tier-ember were not touched.

| Run | Build | CPU | End point | Verdict | Time |
| --- | --- | --- | --- | --- | --- |
| 20261111T171339-hs-hfix-t2-interp-1 | trace | interp | "Interlaced (FIELD)" after the handoff | PASS | 75.3 s |
| 20261111T171502-hs-hfix-t2-interp-2 | trace | interp | same | PASS | 42.5 s |
| 20261111T171553-hs-hfix-t2-interp-3 | trace | interp | same | PASS | 72.2 s |
| 20261111T171711-hs-hfixrel-t2-interp-1 | release | interp | same, after "SDR driver version" | PASS | 39.9 s |
| 20261111T171759-hs-hfix-t2-rec-1 | trace | rec | "# Restart Without Memory Clear Done." after the handoff | PASS | 32.8 s |

Runs 1 and 3 were slower because host-test runs were going at the same
time (the without suite at the end of run 1, the with suite during run 3).
They are not separate emulator runs; the verdicts are unaffected. Every
run's kernel dump shows report words result 0, self 1, retired 1, first 2,
drained 254, queue 1, failed 0; thread 1 entry_ 0x00200000; POPS tids
2,3,4,5,8,9.

## Not done

- No console run. NOT TESTED on a console.
- No ATA POPStarter control with a kernel dump (finding 5).
- No new park run for da77546. The trampoline's copy loop did not change.
  The park harness pokes 0x01000008, which is still reached through the two
  nops.
- No tier-1 reruns: tier 1 ends before the changed code.
- No full game boot past POPS's video setup.
- Not changed, owner questions: the six re-init calls (6a), the report
  words in release builds (3), stopping on a post-terminate failure (10).

## Proposed quirk text (coordinator numbers them; for docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md)

- **Handoff report words left in POPS's address space.** launcHER writes
  eight words at 0x00084300..0x00084320 before the trampoline, in release
  builds too: magic 0x464f4850, result, self, retired, first retired,
  drained, queue mode, failed id. POPStarter r13 leaves that memory as it
  found it. Not measured to matter. 0x80000..0x90000 holds launcHER's
  trampoline, arguments and stack in any case.
- **The six service re-init calls are not repeated (INFERRED effect).**
  This is the author's earlier text, still valid, plus one sentence:
  copying the calls would not move the IOP's view of the SIF packet buffer
  out of POPS memory, because launcHER's buffer is in its own BSS.
- **Fixed (for the status list, not a quirk):** ExecPS2 entry 0x00200008
  became 0x00200000 as in r13 (da77546). The kernel TCB entry matches the
  r13 control in PCSX2.

## Proposed status rows

| Item | Status | Evidence |
| --- | --- | --- |
| ExecPS2 entry | 0x00200000 as r13 (da77546); TCB entry_ 0x00200000 in 5 PCSX2 runs, r13 USB control the same; NOT TESTED on a console | test_pops_handoff Differential, test_pops_external; `<scratch>/hfix/runs.log` |
| POPS thread ids after the handoff | 2,3,4,5,8,9 in PCSX2 (ATA, 10 runs past POPS entry, 890a6a3 and da77546, incl. release); r13 control only on USB (2,3,4,7,8, one thread fewer, the same threads by entry address); ATA parity INFERRED; NOT TESTED on a console | kstate.py on the run dumps |
| Low-RAM layout (trampoline, args, report words, stack) | static asserts in pops_handoff.c (EE and host build); layout check covers the image and the trampoline | test_pops_handoff Native, build logs |
| Report words at 0x84300 | written in all builds; launcHER-only residue; owner question | finding 3 |
| r13 service re-init before ExecPS2 | not copied; owner question | finding 6a |
| Retire failure after a terminate | returns to the menu; untested; owner question | finding 10 |

## Proposed PR-text line (finding 7)

"6a9353d's subject still starts with wip(pops):, and its 'Untested here'
line is stale: 77d1a40, 890a6a3, da77546 and 1287592 complete it, and the
host suite, the container builds and PCSX2 were run on da77546. History
was not rewritten."

## Owner questions

1. Copy r13's six service re-init calls (from C, before the trampoline), or
   keep the recorded difference? (Same as the author's question 3; see 6a
   for why copying would not reproduce r13's effect.)
2. Keep the handoff report words in release builds (the only check of the
   release build after the handoff), or write them only in trace builds?
3. On a retire failure after the helper thread is gone: return to the menu
   (today) or stop?
4. The entry change to 0x00200000 was made under the parity rule. Confirm,
   given that older console notes describe ExecPS2(0x00200008).
5. The questions the author already raised and that are still open: the
   compat-db title change left out, the doc layout (new section prepended),
   the rejected two-stage ExecPS2.
