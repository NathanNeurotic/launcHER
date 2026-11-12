# IGR skin: answer to review 1

Written by whoever answered the review. Copied as written; not re-verified.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## summary

FIXER pass on the IGR skin (IGR_BG/NO/YES.TM2) in the igr worktree, branch pr23/igr. Everything below is a host or emulator result; NOT TESTED on a console.

State I found: HEAD was d31d4a7 (runtime corrections moved before the hooks; already on the lead's branch, not mine). The earlier fixer's uncommitted edits to handler_pops.c, the test and the tracer were present but the test file did not pass: 3 errors and 2 failures with the reference inputs (label passed as the core argument in two Reader tests; an index past BG's six boundary sizes; a seeded coverage assertion that the seed did not meet; the progressive hook run with an interlace word its setting had not staged, returning -42). I repaired those, kept the rest after checking it, finished the doc and header, and committed eb976d1.

Per finding:
1. Order (major): REAL, reproduced with my own scan of the unpacked MAIN (six FUN_008ff0e4 call sites 0x8757d4..0x8769ac all below the skin call 0x876b18; last one continues `b 0x876a40` into the call's gate; no branch crosses the call either way; no jr through a register in the launch function). Fixed by moving the call after pops_builtin_apply. Comment, doc and tests corrected; the order is decoded from the original in OriginalCode and pinned in Source. For a $VCDID_n entry the original applies it after the skin and launcHER before; all 624 entries applied in both orders give the same core.
2. Reader never executed (major): REAL. The test now compiles pops_stage_igr_skin from handler_pops.c on the host (only the scratch address replaced, the four I/O calls redirected) and runs it without inputs against a model of the original, and with inputs against the emulated original. The reviewer's surviving mutants R1-R7 and 20 more now all fail the test file without reference inputs.
3. Runtime corrections (major): REAL, reproduced on the real core (a 1-byte skin makes all six masks return -4). The skin is staged after that stage (which d31d4a7 had already moved to straight after the core patches); tests run 21 whole launch orders with a skin and the refused skin-first order; the doc records it.
4. Overstated non-overlap claim (major): REAL. Every later core-writing stage launchPOPS runs is now executed over a core with a skin and must both succeed and keep it; the doc lists what was run.
5-8 (minor): the device model separates total-ever-delivered from bytes-per-read and launcHER's real reader is run in those tests; a missing unicorn with both inputs is an error; each Original test asserts its own run count; the failed-size-query case runs the reader; header wording fixed; an over-reported read count is now taken as the request (was: load abandoned), which matches the original; scratch-buffer wording fixed; the two stand-in folders are documented and left for the owner.

One caveat about my own run: I ran the two complete test passes in parallel and they collided on the in-tree build/pops-host output (test_popfs without inputs and test_pops_external with inputs failed with 'Permission denied' from the linker). Both pass when rerun alone, both ways.

## commits

1. eb976d1 fix(pops): stage the IGR skin after the built-in entry; run its reader in tests
2. (already present, not made in this session) d31d4a7 fix(pops): stage the $FIX_* runtime corrections before the launch hooks

## files changed

1. launcher/src/handler_pops.c
2. common/include/pops_igr_skin.h
3. tools/test_pops_igr_skin.py
4. tools/trace_original_pops_igr_skin.py
5. docs/POPSTARTER_IGR_SKIN.md

## measured evidence

1. Order in the original (own scan, <scratch>/igr-f1-fix/f1_order.py, and OriginalCode.test_the_builtin_list_runs_before_the_skin_and_vcdid_after): FUN_008ff0e4 has 6 callers, all in the launch function and below 0x876b18; FUN_0087e464 has 1 caller; FUN_008e00d0 has 5 callers (1 inside the lookup, 4 after the parser's entry 0x883270 with no return or stack-adjust prologue in between); the parser's 2 callers (0x8771ac, 0x87724c) are after the skin call; 0 branches from before the gate to past the call, 0 back, 0 register jumps. That the four parser-side callers are the $VCDID_n path is taken from docs/POPSTARTER_BUILTIN_DB.md, not re-derived.
2. Original's loader emulated as shipped over the real POPS core (unicorn, file I/O modelled): 141 runs, every one equal to the Python model over the whole core, with prints, return value 1, no other memory changed, all files closed. 47 runs with files delivered whole (18 boundary, 24 random, 2 no file, 2 noise core, 1 quiet) also equal pops_igr_skin_stage and launcHER's host-compiled reader. 80 runs on misbehaving devices (stops for good 48, size/data disagree 14, failed rewind 8, over-reported count 8, single whole piece 2; both backends) also equal launcHER's reader. 4 further runs cover the gates.
3. Listed differences measured on both sides: failed size query, 8 runs (-1, -5, -16, -4096 x 2 backends, three files each): the original prints LOADED and zeroes the slots and that many bytes below IGR_BG's slot (live POPS bytes for -4096); launcHER's reader leaves the core untouched and closes the file. File handed over in pieces, 6 runs: the original keeps the first piece, launcHER's reader stages the whole file.
4. launcHER's reader without reference inputs against the model: 16 boundary runs, 41 absent/random runs, 3 zero-byte, 9 too-big (0 read calls, core untouched), 80 misbehaving-device runs (40 x 2 path prefixes), 4 failed size query, 3 pieces, 4 short-core sizes, over-long folder; call discipline checked in each of those except the over-long-folder run.
5. Runtime corrections on the real core: after a 1-byte skin in any of the 3 slots all 6 masks return -4 with nothing written (18 cases); in launchPOPS's order 21 whole launches (7 mask choices x 3 built-in choices: none, 1, 508) succeed at every step and keep the skin; skin-before-corrections is refused for all 6 masks.
6. Later stages over a real core with a skin read by the reader, each returning success and leaving 0x2feff0..0x34ee70 unchanged: 80 command lines, 4 recompiler add-on emits, 36 fix-context/progressive/video passes, PS1 BIOS shell edits, 72 region changes, $RESET_WARMBOOT, 11 MODULE_n.IRX names, $LOAD_PADMAN, SLBB bypass, 3 pad, 3 widescreen, 3 progressive, 1 display hook, opcode pass. A PATCH file aimed elsewhere keeps the skin; one aimed at a slot changes only its 8 bytes.
7. Built-in list: 906 operations, 257 core writes, highest end 0x21af71; 624 entries applied over a marked core leave the slots alone, and entry-then-skin equals skin-then-entry for all 624.
8. Mutants, final tree, copies of the worktree, without reference inputs (<scratch>/igr-f1-fix/mutants_final_norefs.txt): unchanged tree passes (48 tests, 21 skipped); 27 of 27 single edits fail the test file: 6 in pops_igr_skin.c, 21 in handler_pops.c including the reviewer's R1-R7, three more ways of gating the call, three leaked handles, a larger request, limit off by one, over-reported count believed, staging the reported size, failed size query accepted, reverse file order, call moved above the built-in entry, call moved above the runtime corrections. Not run with the reference inputs.

## tests run

1. **command:** python tools/test_pops_igr_skin.py (no inputs)  
   **outcome:** rc 0, Ran 48, OK (skipped=21)
2. **command:** python tools/test_pops_igr_skin.py (POPS_TEST_ELF + POPSTARTER_TEST_ELF)  
   **outcome:** rc 0, Ran 48, OK, 0 skipped; 141 runs of the original's loader counted
3. **command:** all 27 tools/test_*.py, no inputs (run in parallel with the with-inputs pass)  
   **outcome:** 26 rc 0; test_popfs rc 1 from a linker 'Permission denied' on build/pops-host/popfs/test_popfs.exe caused by my two passes sharing the in-tree build directory; rerun alone: rc 0 (PASS line printed)
4. **command:** all 27 tools/test_*.py, with both inputs (run in parallel with the no-inputs pass)  
   **outcome:** 26 rc 0; test_pops_external rc 1 from the same collision on build/pops-host/pops_external.dll; rerun alone: rc 0, Ran 128 OK (skipped=3)
5. **command:** test_launch_args, test_network_transports, test_pops_fatfs, test_pops_modes, test_pops_vmc, test_smap_ipconfig, test_sony_ioman_layout, test_subq_bridge  
   **outcome:** rc 0 both ways (no unittest counts printed)
6. **command:** test_popfs  
   **outcome:** with inputs rc 0 in the parallel pass and rc 0 alone; without inputs rc 0 alone (rc 1 only in the collided run)
7. **command:** test_pops_breakpoint  
   **outcome:** without: Ran 11 OK (skipped=4); with: Ran 11 OK
8. **command:** test_pops_builtin_db  
   **outcome:** without: Ran 14 OK (skipped=14); with: Ran 14 OK
9. **command:** test_pops_display  
   **outcome:** without: Ran 21 OK (skipped=6); with: Ran 21 OK
10. **command:** test_pops_external  
   **outcome:** without: Ran 128 OK (skipped=14), in the parallel pass and again alone; with: Ran 128 OK (skipped=3) alone
11. **command:** test_pops_features  
   **outcome:** without: Ran 29 OK (skipped=2); with: Ran 29 OK
12. **command:** test_pops_fix_files  
   **outcome:** without: Ran 31 OK (skipped=3); with: Ran 31 OK
13. **command:** test_pops_io_probe  
   **outcome:** Ran 6 OK both ways
14. **command:** test_pops_launch_hooks (not edited by me)  
   **outcome:** without: Ran 48 OK (skipped=14); with: Ran 48 OK (skipped=3)
15. **command:** test_pops_module_irx  
   **outcome:** without: Ran 11 OK (skipped=4); with: Ran 11 OK
16. **command:** test_pops_opcodes  
   **outcome:** without: Ran 9 OK (skipped=3); with: Ran 9 OK
17. **command:** test_pops_padman  
   **outcome:** without: Ran 6 OK (skipped=3); with: Ran 6 OK
18. **command:** test_pops_progressive  
   **outcome:** without: Ran 8 OK (skipped=5); with: Ran 8 OK (skipped=3)
19. **command:** test_pops_read_trace  
   **outcome:** Ran 9 OK both ways
20. **command:** test_pops_resident  
   **outcome:** without: Ran 75 OK (skipped=12); with: Ran 75 OK
21. **command:** test_pops_runtime_corrections  
   **outcome:** Ran 8 OK both ways
22. **command:** test_pops_startup_calls  
   **outcome:** Ran 6 OK both ways
23. **command:** test_pops_warmboot  
   **outcome:** without: Ran 7 OK (skipped=3); with: Ran 7 OK
24. **command:** python tools/trace_original_pops_igr_skin.py (with inputs, manual tool)  
   **outcome:** ran to the end and printed its cases
25. **command:** python f1_mutants.py (28 copies of the tree, no inputs)  
   **outcome:** BASE rc 0; 27 of 27 mutants rc 1

## ee build check

mips64r5900el-ps2-elf-gcc 15.3.1 20260823 from <ps2build>, run after the last source edit. common/src/pops_igr_skin.c (unchanged .c, changed header) compiled to an object with -D_EE -O2 -G0 -Wall -Wextra -Werror -Icommon/include: rc 0, text 388 bytes, undefined symbols memcpy and memset only. launcher/src/handler_pops.c compiled to an object with -D_EE -Os -G0 -Wall against common/include, launcher/include and the ps2build SDK include dirs kernel, cglue, filexio, common, debug, iopreboot, sifcmd, in three variants (plain, -DENABLE_PRINTF, -DLAUNCHER_BOOT_TRACE): rc 0 each, 19 / 23 / 19 warnings, 0 errors, none of the warnings in the reader (lines 355-430) or at the call site; the object references pops_igr_skin_slot and pops_igr_skin_stage. NOT done: link, CMake or container target build, resident image build, anything on a console or emulator of the PS2.

## deviations from original

1. Order for a $VCDID_n entry: the original applies it in the config parser, after the skin; launcHER applies either kind of built-in entry before the skin. No byte difference: all 624 entries commute with a skin.
2. Folder: the original reads pfs1:/POPS/ or mass:/POPS/; launcHER reads the launched VCD's folder (same folder as the all-games TROJAN_n.BIN/PATCH_n.BIN). On HDD a skin in __common/POPS/ is not found. MODULE_n.IRX uses a different stand-in (the folder POPS.ELF came from).
3. No gate: no shared abort flag, no preset byte 0x10002d, no POPS-folder check and so no fatal -666 path; launcHER always tries the three files.
4. Failed size query: the original takes the negative result as a size, prints LOADED and zeroes the slot and that many bytes below it (POPS data for IGR_BG.TM2). launcHER closes the file and leaves the core alone. Deliberate; measured on both sides.
5. Device that returns a short count and has more on the next call: the original's one unchecked read keeps the first piece; launcHER reads in requests of at most 64 KiB until the size has arrived and stages the whole file. Measured on both sides.
6. Failed seek back to the start that leaves the position anywhere but the end of the file: launcHER stages 0 bytes; the original reads from wherever the position is. Read from the code, not run (the device model leaves the position at the end, where both give an all-zero slot).
7. A read that fails after storing some bytes: not modelled on either side.
8. Messages: debug lines with different text, not the original's screen log.
9. Visibility: launcHER's default in-game reset is its own direct exit, so the skin shows only under $IGR0..2; under the original the default opens Sony's dialog.
10. launcHER-only ordering constraint with no counterpart in the original: the skin must come after the $FIX_* runtime corrections.

## not done

1. Nothing was run on a console. Untested there: that POPS shows a replaced image, that YES/NO in Sony's dialog work under launcHER's resident code with $IGR0..2, and how launcHER's I/O stack delivers a 312 KiB file.
2. No link, CMake or container target build (only the object compiles above).
3. The complete host test list was not rerun end to end in a single clean sequential pass: the two passes ran in parallel, two files collided on the in-tree build directory and were rerun alone (both pass). The other 25 files per pass were not rerun.
4. Mutants were run only without the reference inputs.
5. The folder question (VCD folder vs the device POPS folder vs the folder POPS came from) is left as it was; no code change.
6. The shared docs (inventory, quirks, README, pops-setup.html, continuation, checkpoint history) were not edited; text is in doc_updates.
7. FUN_008d8958 (the POPS-folder check) was not traced; that the four parser-side callers of FUN_008e00d0 are the $VCDID_n path was not re-derived here.
8. The failed-rewind-elsewhere and read-error-after-partial-store cases were not run on either side.

## decisions for owner

1. Which folder the skin is read from. Now: the VCD's folder (vcdDir). The original: the device POPS folder (pfs1:/POPS/ = __common on HDD, or mass:/POPS/). MODULE_n.IRX already uses a different stand-in (popsDir). Pick one stand-in for both, or wait for the __common layout.
2. Reader shape. Now: looped reads of at most 64 KiB, which stage a whole file on a device that returns short counts. Exact parity would be one unchecked read of the slot size after zeroing the buffer, as pops_module_irx_read already does for MODULE_n.IRX; that would also remove the failed-rewind difference. I kept the loop because launcHER's own I/O stack is not the original's and a single 312 KiB read on it has not been tried on a console.
3. Failed size query: keep launcHER's safe behaviour (core untouched), or copy the original's write below the slot as a quirk. I recommend keeping it: the original's result overwrites POPS data.
4. Whether the skin should be visible by default. It only shows under $IGR0..2 because launcHER's default reset is the direct exit.
5. Whether launcHER should have an equivalent of preset byte 0x10002d to switch the skin loader off.

## doc updates


### inventory rows

Replace the row at docs/POPSTARTER_R13_INVENTORY.md:199 with:
| IGR menu skin (IGR_BG/NO/YES.TM2). `FUN_0087e464`, one caller `0x876b18`, after the fingerprint-matched built-in entry (`FUN_008ff0e4`, six sites `0x8757d4..0x8769ac`) and before the config parser: from `pfs1:/POPS/` or `mass:/POPS/` only (no per-game folder), raw copy over Sony's own TIM2 files at `0x2feff0` (max `0x4c300` bytes), `0x34b2f0` and `0x34d0b0` (max 7,612 bytes each), rest of the slot zeroed, no TIM2 check, never fatal (`2x`) | **PARTIAL**: `pops_igr_skin_stage` (`common/src/pops_igr_skin.c`) and the reader `pops_stage_igr_skin` (`handler_pops.c`), staged after the built-in entry and after the `$FIX_*` runtime corrections. Same table, limits, zero fill and outcomes as the original in 141 emulated runs; the reader itself is compiled on the host and equals the original in 127 of them, the other 14 being the two listed differences. Differences: read from the VCD's folder, not the device `POPS` folder (not found in `__common/POPS/` on HDD); no preset gate and no POPS-folder check; a failed size query leaves the core alone; a file a device hands over in pieces is staged whole; only visible under `$IGR0..2` because the default reset is launcHER's direct exit. NOT TESTED on a console. `docs/POPSTARTER_IGR_SKIN.md` |

In the row at :193 (preset block) the IGR skin byte `0x10002d` stays unimplemented: launcHER always tries the three files.
In the list at :234, item (c) 'IGR skin staging' is done (host and emulator only).

### quirks

Entries, no numbers:
- IGR skin, copied: a 0-byte IGR_BG.TM2 / IGR_NO.TM2 / IGR_YES.TM2 is LOADED and replaces Sony's image with zeros.
- IGR skin, copied: nothing but the size is checked (no TIM2 signature, picture count, dimensions); any file up to the limit is copied raw.
- IGR skin, copied: IGR_NO.TM2 and IGR_YES.TM2 are limited to 7,612 bytes (0x1dbc) although the slot is 7,616 (0x1dc0); a file padded to the slot size is refused as TOO BIG.
- IGR skin, copied: the files are loaded even when the IGR setting means Sony's dialog can never open.
- IGR skin, copied: a device that delivers part of a file and then nothing leaves that part followed by zeros; no error is raised.
- IGR skin, original bug NOT copied: a failed size query (negative lseek result) is taken as a size; the original prints LOADED and zeroes the slot and that many bytes below it, which for IGR_BG.TM2 is POPS's own data. launcHER leaves the core alone. Measured under emulation for -1, -5, -16, -4096.
- IGR skin, original behaviour NOT copied: one unchecked read of the whole slot, so a device returning a short count leaves only the first piece. launcHER reads until the size has arrived.
- launcHER-only constraint: the IGR skin has to be staged after the $FIX_* runtime corrections, which refuse (-4, fatal) any core that is not the pristine or core-patched image.

### user facing

README.md:718, replace with:
- **Custom IGR graphics (`IGR_BG.TM2`, `IGR_YES.TM2`, `IGR_NO.TM2`): loaded, not tested on a console.** launcHER copies the three files over the pictures of Sony's exit confirmation screen, with POPStarter's size limits (`IGR_BG.TM2` up to 312,064 bytes, the other two up to 7,612 bytes each; a larger file is skipped). Two differences from POPStarter: launcHER reads them from the folder the game's VCD is in, not from the device's `POPS` folder (the same place only when the VCD is in `mass:/POPS/`), and the pictures are only seen with `$IGR0`, `$IGR1` or `$IGR2` in the game's config, because launcHER's default reset exits directly without showing that screen. The files are not checked: a file that is not a valid TIM2 image of the right size will be shown as it is.

docs/pops-setup.html:554, replace the paragraph with the same content: the three files go beside the game's VCD; size limits as above; add `$IGR0`, `$IGR1` or `$IGR2` to see them; not tested on a console.

### hardware checklist

- With $IGR0 (and separately $IGR1, $IGR2): place valid IGR_BG.TM2 (400x260), IGR_NO.TM2 and IGR_YES.TM2 (74x34) beside the VCD, open Sony's dialog with the combo, confirm the three pictures show, and that YES exits and NO resumes.
- Same launch without the files: Sony's own pictures.
- IGR_BG.TM2 at exactly 312,064 bytes on USB and on SMB/HDD: confirm the whole image arrives (launcHER's I/O stack with a 312 KiB file is untested).
- One file one byte over its limit: Sony's picture stays and the launch continues.
- A launch with no IGR command and the files present: the launch is unaffected and the direct exit still works.
- A launch with a $FIX_* runtime correction and the skin files present: starts (this order failed with -4 before the reorder, on the host).
- A game with a built-in entry (by fingerprint and by $VCDID_n) plus the skin files: both take effect.

## Correction (added later)

This report is kept as written. "21 whole launches in launchPOPS's order"
was true of the test at the time. The user `BIOS.BIN` merge (`0945127`)
then moved launchPOPS's commands and fix files into `pops_stage_user_files`
and switched the shell edits and the region pass to the `_rom` functions,
which the test's replay did not follow. The replay now follows them, adds
a user `BIOS.BIN` in either folder or both (84 launches), and names the two
calls it leaves out (the TROJAN slot chain and the progressive hook).
