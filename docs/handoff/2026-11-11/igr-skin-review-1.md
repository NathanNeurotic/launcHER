# IGR skin: review 1

Written by an independent reviewer of the track. Copied as written.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## verdict

issues

## issues

1. **severity:** major  
   **description:** Wrong claim about the original's order, pinned by the test: in the original the built-in list is applied BEFORE the IGR skin; launcHER stages the skin BEFORE pops_builtin_apply and says this is the original's position. No byte difference results today (the two stages write disjoint ranges), so this is a wrong claim and a wrong pin, not wrong output.  
   **evidence:** Reviewer scan of the unpacked MAIN: FUN_008ff0e4 (built-in lookup+apply; its only callers in MAIN) is called at 0x8757d4, 0x875d70, 0x875f78, 0x8762a8, 0x876424, 0x8769ac, all in the launch function and all below the skin call at 0x876b18; 0x8769b4 is `b 0x876a40`, which runs into the exit-program copy and then the skin call; the apply function FUN_008e00d0 is called at 0x9148d8 inside FUN_008ff0e4; no branch in [0x870b78,0x876a84) lands at or after 0x876b1c. docs/POPSTARTER_BUILTIN_DB.md lines 13-16 and 37 already say the same. Against that: launcher/src/handler_pops.c:1451-1455 ('next in its launch function (0x876b18), before everything below'), docs/POPSTARTER_IGR_SKIN.md:82-87 ('before the runtime corrections, the built-in list ... This is the original's position relative to the stages launcHER has'), commit message ('before every later stage'), and tools/test_pops_igr_skin.py test_call_position, whose `after` list requires the skin before 'res = pops_builtin_apply('. Byte-neutral: 257 built-in core writes all end at or below 0x21af71 (recounted).  
   **suggested fix:** Either move the call to after the built-in entry is applied (original order: always-on pokes, built-in entry, skin, then fix files/commands), which also takes it past the runtime-corrections identity check, or keep the position and correct the handler comment, the doc and the test to say the original applies the built-in entry first and that the two stages commute because no built-in op writes inside 0x2feff0..0x34ee70.
2. **severity:** major  
   **description:** The reader pops_stage_igr_skin and its call site are never executed by any repo test; they are pinned by source text only. 6 of 7 single-line mutants in that code survive tools/test_pops_igr_skin.py with the reference inputs, 5 of them changing behaviour against the original.  
   **evidence:** Survivors (feature test rc 0, 'Ran 30 ... OK'): R1 rewind test inverted (every accepted file staged as zeros); R2 `got = n` instead of `+=` (files over 64 KiB truncated); R3 too-big file falls through (slot wiped instead of kept); R4 `size <= 0` skipped (0-byte file no longer wipes the slot, the copied quirk); R5 `n < 0` instead of `n <= 0` (loop never ends when the file is shorter than reported); R6 `if (cfg.compat_modes)` on the line before the call (the 'bare statement' pin only looks at the call's own line). R7 (`break` on over-long path) is benign. The reviewer's host build of the extracted reader with open/lseek/read/close redirected catches R1-R5 (48, 14, 30, 3, 12 mismatches of 113). As committed the reader is right: 246 of 246 cases equal to the emulated original (see independent_checks).  
   **suggested fix:** Compile the reader slice on the host the way tools/test_pops_fix_files.py compiles readFullFile (I/O redirected to a modelled file table, scratch address replaced) and compare it with the emulated original under the same file model: boundary sizes, 0-byte, too big, permanent short delivery, read error, failed rewind, failed size query. Make the call-site pin reject a guard on the preceding line.
3. **severity:** major  
   **description:** The skin is staged before pops_core_runtime_corrections_stage, which requires an exact whole-core SHA-256 (pristine or baseline-patched). Any accepted skin file alone makes that stage return -4, which launchPOPS treats as fatal ('Runtime corrections staging failed'). Masked today by a pre-existing failure, and not mentioned in the commit or the new doc, which say the skin 'never stops the launch'.  
   **evidence:** Host measurement on the real core (rv_runtime.py): core patches then runtime corrections = 0; core patches + always-on hooks then runtime corrections = -4 for masks 1, 2, 4, 8, 16, 31 (pre-existing, not caused by this commit: every $FIX_*/$PSXCORE_FIXES launch would stop there if the console path behaves like the host); core patches + one 1-byte IGR_NO skin, no hooks, then runtime corrections = -4. common/src/pops_core_patches.c:141-143. The implementer raised this only in decisions_for_owner; tools/test_pops_igr_skin.py line 90 sets the function's argtypes but never calls it.  
   **suggested fix:** Run the runtime corrections before the hooks and the skin (it is a launcHER-only stage), or stage the skin after it; add a test that a launch order with a skin and a runtime-corrections mask succeeds; record the interaction in docs/POPSTARTER_IGR_SKIN.md. The pre-existing -4 after the hooks needs its own fix by whoever owns that stage.
4. **severity:** major  
   **description:** Commit message overstates the non-overlap evidence: 'the other stages are checked not to write inside 0x2feff0..0x34ee70'. Several stages launchPOPS runs after the skin are not checked, and the doc's 'Not checked' list names only some of them.  
   **evidence:** Not exercised by any test in the file: pops_stage_fix_files / pops_fix_stage, pops_fix_require_progressive, pops_fix_finalize_video, pops_resident_hook_recompiler_emit (appears only in the order pin), pops_module_irx_apply_names, pops_apply_slbb_vcd_check_bypass, pops_resident_hook_pads / widescreen / progressive / display, pops_core_runtime_corrections_stage. docs/POPSTARTER_IGR_SKIN.md:181-183 lists only user fix files and the display, widescreen and progressive hooks. Reviewer's lexical scan of common/src, common/include and handler_pops.c (builtin data excluded) found no address literal in 0x2f0000..0x34ffff other than the skin table and 0x002fb599 (below the slots); that is a text scan, not proof for computed addresses.  
   **suggested fix:** Reword the commit/doc claim to the stages actually run, or add the missing stages to RealCore.test_stages_after_the_skin_leave_it_alone and complete the 'Not checked' list.
5. **severity:** minor  
   **description:** Original.test_a_short_read_leaves_what_arrived_then_zeros models a per-read limit and compares the original with the pure function fed a hand-cut prefix. Under that same device model launcHER's real reader gives a different slot, so the test's docstring ('staging the bytes that arrived is the same') does not describe what launcHER does.  
   **evidence:** trace_original_pops_igr_skin.py: read_limit is 'most bytes one read delivers'. Reviewer measurement with 4096 bytes per read call, 6 cases: original slot = first 4096 bytes + zeros, launcHER reader slot = whole file + zeros. The doc does list this deviation (lines 138-141). For a device that stops for good the reader does match the original (36 of 36 reviewer cases).  
   **suggested fix:** Model 'total bytes the device ever delivers' separately from 'bytes per read call', and run launcHER's reader, not a prefix, in that test.
6. **severity:** minor  
   **description:** Test robustness: a broken tracer import is turned into a skip; the per-outcome coverage assertion only runs when the run counter is exactly 45 and the counter itself is not asserted; the 'not copied' test never runs launcHER's side.  
   **evidence:** tools/test_pops_igr_skin.py:50-55 (`except Exception: HAVE_EMU = False` with both inputs set), 580-589 (`if cls.runs == 45:`), 699-709 (test_a_failed_size_query_is_not_copied runs only the original). Reviewer ran the reader on 24 failed-size-query cases: core untouched and file closed in all.  
   **suggested fix:** Let an import error fail when both inputs are set; assert the run count; run the reader for the failed-size-query case.
7. **severity:** minor  
   **description:** Two different stand-ins now exist for the original's single device POPS folder: MODULE_n.IRX is read from the folder POPS came from (popsDir), the skin from the VCD's folder (vcdDir). On HDD the original's folder is pfs1:/POPS/, so a skin placed where POPStarter users keep it is not found by launcHER.  
   **evidence:** launcher/src/handler_pops.c:906-913 (comment: 'launcHER's equivalent is the folder POPS came from') versus :1455 (vcdDir). The original opens only pfs1:/POPS/IGR_*.TM2 or mass:/POPS/IGR_*.TM2 (strings at 0x9b11f8, 0x9b1238 and the two later pairs). The doc records the folder as a deviation and the implementer flagged it for the owner.  
   **suggested fix:** Owner decision; if vcdDir stays, say in the doc that MODULE_n.IRX uses a different stand-in.
8. **severity:** minor  
   **description:** Small wording and undocumented-detail points.  
   **evidence:** (1) common/include/pops_igr_skin.h:17 'nothing is ever fatal' omits the original's -666 folder-check path (the doc has it). (2) The reader drops a chunk when read() returns more than was asked for (`(size_t)n > chunk` breaks before counting); the original keeps whatever was written. Reviewer: 6 of 6 such cases differ; not in the doc's deviation list; only a broken driver does this. (3) docs/POPSTARTER_IGR_SKIN.md:79 calls 0x01f00000 a '1 MiB scratch buffer'; the loose-ELF path places a staging buffer at 0x01f80000 inside it. The skin's largest read ends at 0x01f4c300, so there is no overlap for this feature.  
   **suggested fix:** Adjust the wording; list the over-return case with the other read deviations or drop the extra condition.

## independent checks

1. Everything below is a host or emulator result. NOT TESTED on a console.
2. Own disassembly (capstone) of the unpacked MAIN 0x87e464..0x87eb20: three inline blocks; BG test `slt` with 0x4c300 (too big when size > 0x4c300), NO/YES `slti 0x1dbd`; zero-fill and read lengths 0x4c300 / 0x1dc0 / 0x1dc0 at 0x2feff0 / 0x34b2f0 / 0x34d0b0; tail fill memset(slot+size, 0, slot-size); read result unused; mass backend sign-extends the lseek result; wrappers 0x8d6c94..0x8d6da0 are pass-throughs; memset 0x9188b8 takes an unsigned length. Matches the table in common/src/pops_igr_skin.c.
3. Own emulator (different mechanism from the implementer's: callee entries overwritten with `jr ra`, one hook per entry, own POPS.ELF flattener, own file model, own seeds; scripts in <scratch>/igr-r1-review/ : rv_emu.py, rv_host.py, rv_diff.py). 288 runs of the original loader over the real POPS core (0x302e60 bytes) and a noise core, both backends.
4. Three-way comparison, whole core after each run: 100 single-file boundary cases (14 sizes for BG, 18 each for NO/YES, x2 backends), 80 random combinations (20 on a noise core), 66 device cases (36 permanent short delivery with 0 or -5 afterwards, 18 size query larger/smaller/huge versus the data, 6 failed rewind, 6 with fd 0). Original == reviewer model == pops_igr_skin_stage in 186 of 186; original == launcHER's reader (pops_stage_igr_skin extracted from handler_pops.c, host-compiled, I/O redirected) in 246 of 246. Return value 1, no stray memory writes, no handle left open, in all. Every outcome (NOT FOUND / TOO BIG / LOADED) seen at least 15 times per file per backend.
5. Deviations measured rather than assumed: per-read short counts, 6 cases: original = first chunk + zeros, launcHER = whole file (documented). Failed size query (-1, -5, -16, -4096; 3 files x 2 backends = 24 runs, including IGR_BG.TM2 which the implementer did not run): the original zeroes the slot and that many bytes below it and prints LOADED in 24 of 24; for IGR_BG.TM2 with -4096 the zeroed bytes are live POPS data. launcHER's reader leaves the whole core alone and closes the file in 24 of 24. Failed rewind with the position left at the end: both give an all-zero slot (6 of 6), so that listed deviation shows no difference under this model.
6. Gates on the original (6 runs): abort flag set returns 0 with no calls and core unchanged; folder check returning 0 or -666 returns -666, sets gp+0x38dc, core unchanged; passing check loads; gp+0x3868 == 1 skips the check; quiet flag prints nothing.
7. Call site: exactly one `jal 0x87e464` (0x876b18), no `j`, no pointer word, no byte-level pointer, no lui/addiu or lui/ori pair forming the address; no branch in [0x870b78,0x876a84) lands at or after 0x876b1c; return value unused; gates gp+0x38dc == 0 and fp+0x1108 == 1 (stores only at 0x870ce8 and 0x8712ec). Preset byte 0x10002d is 1 in the four profiles on this machine (MAIN, DEBUG, USBDELAY, USBDELAY_DEBUG).
8. Order in the original: built-in list call sites 0x8757d4..0x8769ac precede the skin call; next loader at 0x876bac; config parser at 0x8771ac / 0x87724c. See the first issue.
9. Reader-only properties (host build): scratch high-water mark never above the file limit (6 of 6, also when the file is longer than reported); too big means no read call, core untouched, file closed (3 of 3); short core means untouched and closed (3 of 3); opens BG, NO, YES in order; over-long directory means no open.
10. Scratch buffer: largest skin read ends at 0x01f4c300; staged core is 0x01000000..0x01302e60, IOP staging 0x01700000, raw input 0x01800000 (no longer needed by then), loose-path scratch folder staging 0x01f80000. No overlap found by reading handler_pops.c.
11. Runtime-corrections interaction measured on the real core (rv_runtime.py): 0 after core patches; -4 after hooks (pre-existing); -4 after a skin alone.
12. POPS side, read from the core: FUN_00226768 loads 0x30xxxx / 0x35xxxx pointers before three calls to 0x226d60 at 0x2267dc / 0x226800 / 0x226824; pad-combination words 0x228a20 = 30a30904, 0x228a50 = 24020904, 0x228a54 = 14620018, 0x228a5c..68 as the test lists them.
13. Numbers recounted: 30 tests (Native 6, Dialog 2, Staging 3, RealCore 4, OriginalCode 3, Original 8, Source 4), 16 skipped without inputs; 45 whole-core comparing runs (16 + 24 + 2 + 2 + 1) plus 9 more (4 + 3 + 2); per-outcome counts 2..17; built-in table 906 ops, 257 core writes, highest end 0x21af71; 80 command lines; 72 region/video combinations. All match the doc, the commit message and the report.
14. EE compile rerun (mips64r5900el-ps2-elf-gcc 15.3.1 20260823): common/src/pops_igr_skin.c with -D_EE -O2 -G0 -Wall -Wextra -Werror: rc 0, text 388 bytes, needs only memcpy and memset. launcher/src/handler_pops.c with -D_EE -Os -G0 -Wall against the ps2build SDK include dirs (kernel, common, cglue, filexio, debug) in three variants (plain, -DENABLE_PRINTF, -DLAUNCHER_BOOT_TRACE): rc 0 each, 19 / 23 / 19 warnings, none in the new code; the object references pops_igr_skin_slot and pops_igr_skin_stage. NOT done: link, CMake or container build, anything on a console or emulator.
15. Hygiene: no original, Sony or game bytes and no long hex tables in the 8 changed files (the test holds 9 POPS words and 10 POPStarter gate words as pins); no AI attribution in the commit message or added lines; the six off-limits shared docs untouched (the only docs change is the new docs/POPSTARTER_IGR_SKIN.md); the CI step is present and the test passes without inputs; index line endings LF for all changed files; `git diff HEAD~1 HEAD --check` clean.
16. Tree state: `git status` clean on pr23/igr at e9224cf. One difference from how I found it: common/src/pops_igr_skin.c was LF in the working copy and is now CRLF, because `git checkout --` with core.autocrlf=true rewrote it after the in-tree mutant; content equals HEAD (same hash with CR stripped). The ignored build/ directory predates this review and was refreshed by the existing tests.

## mutants

1. Method: all 13 mutants plus an unmodified baseline were applied to `git archive HEAD` exports under the scratch folder (worktree untouched) and tools/test_pops_igr_skin.py was run with POPS_TEST_ELF and POPSTARTER_TEST_ELF set. P2 and R1 were then repeated in the worktree itself and reverted with `git checkout -- <file>`: same results. Baseline: Ran 30, OK.
2. P1 pops_igr_skin.c: BG limit 0x4c300 -> 0x4c2ff. CAUGHT (6 failures: Native table and boundary, Original boundary, OriginalCode table, RealCore).
3. P2 pops_igr_skin.c: `size > slot->max_size` -> `>=`. CAUGHT (5 failures), in the export and in the worktree.
4. P3 pops_igr_skin.c: zero fill uses max_size instead of slot_size. CAUGHT (6 failures).
5. P4 pops_igr_skin.c: bounds check uses max_size instead of slot_size. CAUGHT (1 failure, test_short_core_is_refused_untouched).
6. P5 pops_igr_skin.c: YES limit 0x1dbc -> 0x1dc0. CAUGHT (4 failures).
7. P6 pops_igr_skin.c: `if (size)` -> `if (size > 1)` before memcpy. CAUGHT (2 failures).
8. R1 handler_pops.c reader: `lseek(fd, 0, SEEK_SET) == 0` -> `!= 0` (every accepted file staged as zeros). SURVIVED (rc 0), in the export and in the worktree. Reviewer harness: 48 of 113 mismatches.
9. R2 handler_pops.c reader: `got += n` -> `got = n` (files over 64 KiB truncated). SURVIVED. Reviewer harness: 14 mismatches.
10. R3 handler_pops.c reader: too-big branch `continue` -> `size = 0` (falls through, slot wiped). SURVIVED. Reviewer harness: 30 mismatches.
11. R4 handler_pops.c reader: `if (size < 0)` -> `if (size <= 0)` (0-byte file skipped; the original wipes the slot). SURVIVED. Reviewer harness: 3 mismatches.
12. R5 handler_pops.c reader: `n <= 0` -> `n < 0` (end of file before the reported size never leaves the loop). SURVIVED. Reviewer harness: 12 mismatches (runaway detected).
13. R6 handler_pops.c launchPOPS: `if (cfg.compat_modes)` added on the line before the call. SURVIVED (the 'nothing gates it' pin checks only the call's own line).
14. R7 handler_pops.c reader: `continue` -> `break` on an over-long path. SURVIVED; benign in practice (all three names are nearly the same length).

## tests rerun

1. Complete list, 27 files, each run from the worktree root on the committed tree with TMP/TEMP/TMPDIR isolated, first without and then with POPS_TEST_ELF / POPSTARTER_TEST_ELF. Result: 27 of 27 rc 0 without inputs, 27 of 27 rc 0 with inputs; no FAILED, ERROR: or Traceback in any log (logs in <scratch>/igr-r1-review/logs-norefs and logs-refs).
2. test_pops_igr_skin.py: without Ran 30 OK (skipped=16); with Ran 30 OK (0 skipped). Verbose run with POPS_IGR_SKIN_COUNTS=1: 45 whole-core comparisons, per-outcome counts 2..17.
3. test_launch_args.py, test_network_transports.py, test_popfs.py, test_pops_fatfs.py, test_pops_modes.py, test_pops_vmc.py, test_smap_ipconfig.py, test_sony_ioman_layout.py, test_subq_bridge.py: rc 0 both ways (not unittest-style; no counts printed).
4. test_pops_breakpoint.py: without Ran 11 OK (skipped=4); with Ran 11 OK.
5. test_pops_builtin_db.py: without Ran 14 OK (skipped=14); with Ran 14 OK.
6. test_pops_display.py: without Ran 21 OK (skipped=6); with Ran 21 OK.
7. test_pops_external.py: without Ran 128 OK (skipped=14); with Ran 128 OK (skipped=3).
8. test_pops_features.py: without Ran 29 OK (skipped=2); with Ran 29 OK.
9. test_pops_fix_files.py: without Ran 31 OK (skipped=3); with Ran 31 OK.
10. test_pops_io_probe.py: Ran 6 OK both ways.
11. test_pops_launch_hooks.py: without Ran 46 OK (skipped=13); with Ran 46 OK (skipped=3). Not edited by the commit.
12. test_pops_module_irx.py: without Ran 11 OK (skipped=4); with Ran 11 OK.
13. test_pops_opcodes.py: without Ran 9 OK (skipped=3); with Ran 9 OK.
14. test_pops_padman.py: without Ran 6 OK (skipped=3); with Ran 6 OK.
15. test_pops_progressive.py: without Ran 8 OK (skipped=5); with Ran 8 OK (skipped=3, 'optional EE compiler and original MAIN').
16. test_pops_read_trace.py: Ran 9 OK both ways.
17. test_pops_resident.py: without Ran 75 OK (skipped=12); with Ran 75 OK.
18. test_pops_runtime_corrections.py: Ran 8 OK both ways.
19. test_pops_startup_calls.py: Ran 6 OK both ways.
20. test_pops_warmboot.py: without Ran 7 OK (skipped=3); with Ran 7 OK.
21. EE compile of both changed C files rerun: rc 0 (details in independent_checks). No link or target build.

## unsupported claims

1. handler_pops.c:1451-1454 ('next in its launch function (0x876b18), before everything below'), docs/POPSTARTER_IGR_SKIN.md:82-87 ('This is the original's position relative to the stages launcHER has') and the commit message ('before every later stage'): contradicted for the built-in list, which the original applies before the skin (call sites 0x8757d4..0x8769ac).
2. Commit message: 'the other stages are checked not to write inside 0x2feff0..0x34ee70'. Not checked: fix-file staging and its finalize/progressive steps, pops_resident_hook_recompiler_emit, pops_module_irx_apply_names, pops_apply_slbb_vcd_check_bypass, the resident pad/widescreen/progressive/display hooks, runtime corrections. The doc's 'Not checked' list is incomplete.
3. Commit message and doc: the reader tests the size before anything is read, closes every file, and 'never stops the launch'. No repo test executes pops_stage_igr_skin; these are source-text pins (6 mutants survive). The reviewer's host run of the reader found them true for the reader in isolation. Separately, a staged skin makes the runtime-corrections stage return -4 (currently masked by the pre-existing -4 after the hooks).
4. Doc 'Copied as it is: a read that delivers less than the file's size leaves what arrived followed by zeros' and report 'Same slot when the device delivers everything or stops for good (3 emulated short-read cases)': those 3 runs compare the original with the pure function fed a hand-cut prefix, under a per-read-limit model for which launcHER's real reader gives a different slot. The claim holds for a device that stops for good (reviewer: 36 of 36), but the repo's tests do not show it.
5. Report and doc: the failed size query is 'not reproduced by launcHER'. The repo test with that name runs only the original. Reviewer measured it: 24 of 24 cases leave the core alone.
6. Doc: a failed rewind is listed as a difference (launcHER zeros; the original 'reads from wherever the file position is', not run). With the position left at the end by the size query, the original also leaves an all-zero slot (6 of 6 reviewer runs); a difference exists only if a failed seek leaves the position elsewhere.
7. Doc line 4-5: 'Ember launches never reach this code'. Not tested by this commit (same phrase as docs/POPSTARTER_LAUNCH_HOOKS.md).
