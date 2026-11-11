# IGR skin: author's report

Written by the track's author when the stage ended. Copied as written; not re-verified.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## summary

POPStarter r13's IGR menu skin loading is implemented and committed locally on branch pr23/igr in the igr worktree (one commit, not pushed). NOT TESTED on a console: every result is a host test or the original's code run under unicorn with its file I/O modelled.

What was measured on the original (MAIN, external input): loader FUN_0087e464 (0x87e464..0x87eb20) has one caller, the jal at 0x876b18, gated by gp+0x38dc == 0 and fp+0x1108 == 1 (set from preset byte 0x10002d, which is 1 in the MAIN file). It copies IGR_BG.TM2 to 0x2feff0 (slot 0x4c300, largest file 0x4c300 = 312,064 bytes), IGR_NO.TM2 to 0x34b2f0 and IGR_YES.TM2 to 0x34d0b0 (slot 0x1dc0, largest file 0x1dbc = 7,612 bytes), from pfs1:/POPS/ or mass:/POPS/. Per file: open, size by seek to end, too big is skipped without reading, else zero the slot, one unchecked read, zero the tail. No TIM2 or any other content check, so the pure function has no TIM2 guard either. Missing or too big is never fatal.

What launcHER now does: pops_igr_skin_stage()/pops_igr_skin_slot() in a NEW pure file common/src/pops_igr_skin.c (+ header). A new file was chosen because no existing test's gcc source list had to change and pops_modes_patches.c/.h (edited by other tracks) stay untouched; the only shared edits are one line in launcher/CMakeLists.txt and one CI step. The reader pops_stage_igr_skin() in launcher/src/handler_pops.c checks the size before reading, reads from vcdDir (the folder the all-games TROJAN_n.BIN/PATCH_n.BIN come from, stand-in for the original's device POPS folder), and is called once right after the always-on hooks/pokes and before runtime corrections, built-in list, commands, fix files, shell edits, region, warmboot and the opcode pass. launcHER's default direct IGR exit is unchanged.

Visibility (measured on a synthetic core and on the real core via pops_apply_all_config_patches): Sony's dialog, and so the skin, is reachable only with $IGR0, $IGR1 or $IGR2. With no IGR command (launcHER direct exit), $NOIGR and $IGR3..5 the dialog never opens; the files are still loaded, as in the original.

One thing went wrong on the way and is fixed: my first placement of the reader was inside the slice of handler_pops.c that tools/test_pops_fix_files.py compiles on the host, which broke that test and tools/test_pops_external.py (which imports it). The first full run caught it; the reader was moved below that slice, a source check now pins this, and the complete list was rerun both ways: all 27 files pass.

New doc: docs/POPSTARTER_IGR_SKIN.md. Shared docs were not edited; texts for them are in doc_updates.

## commits

1. e9224cf5419d2c1701476f5e461a7fcd77dea90f feat(pops): POPStarter's IGR menu skin (IGR_BG/NO/YES.TM2)

## files changed

1. common/include/pops_igr_skin.h (new)
2. common/src/pops_igr_skin.c (new)
3. launcher/src/handler_pops.c (include, pops_stage_igr_skin reader placed after pops_load_bdma_group, one call in launchPOPS)
4. launcher/CMakeLists.txt (one EE_SOURCES line)
5. .github/workflows/build.yml (one host-test step)
6. tools/test_pops_igr_skin.py (new, 30 tests)
7. tools/trace_original_pops_igr_skin.py (new, unicorn harness for the original's loader)
8. docs/POPSTARTER_IGR_SKIN.md (new)

## measured evidence

1. Original loader vs pops_igr_skin_stage, whole POPS core (0x302e60 bytes) compared after each run, original run as shipped under unicorn with open/lseek/read/close/printf/memset/folder-check modelled: 45 runs (16 boundary-size runs covering sizes 0, 1, max-1, max, max+1, slot, slot+1 and 2*slot for each file on each backend; 24 seeded random runs; 2 no-file runs; 2 runs over a core of random noise; 1 quiet-flag run), both backends gp+0x3448 = 0 (pfs1:) and 1 (mass:). Result: byte-identical core in all 45; printed outcome maps NOT FOUND / TOO BIG ! / LOADED to absent / -EFBIG / 0; return value 1; no memory outside the core and stack changed; every opened file closed; each of the three outcomes seen for each file on each backend (counts per (backend, file, outcome) between 2 and 17).
2. Original gates, 4 emulator runs: abort flag set returns 0 with no I/O and core unchanged; folder check failing returns -666, sets gp+0x38dc, core unchanged; folder check passing loads; gp+0x3868 == 1 skips the folder check.
3. Original short read, 3 emulator runs (mass backend; read limited to 1000 of 70000, 0 of 500, 7 of 7612 bytes): core equals pops_igr_skin_stage(data[:delivered]) in all 3.
4. Original failed size query, 2 emulator runs (lseek-end returning -5 on IGR_NO.TM2, -1 on IGR_YES.TM2): the original zeroes the slot and 5 / 1 bytes below it and prints LOADED. Not reproduced by launcHER on purpose. Not run for IGR_BG.TM2.
5. Static decode of the original's instructions (3 file blocks): both paths per file, zero-fill and read (address, length) pairs and the size tests equal launcHER's table; exactly one jal to 0x87e464 (at 0x876b18), no j and no word equal to its address in MAIN; gate words at 0x876a84/0x876a90/0x8712c8..0x8712ec; preset byte at packed-file offset of vaddr 0x10002d is 1; the three message strings.
6. Sony's own files in the real POPS core (3 slots): all 'TIM2', 1 picture; IGR_BG 400x260, image 312,000 bytes (= 400*260*3), total+16 = 0x4c300; IGR_NO/IGR_YES 74x34, image 7,548 bytes (= 74*34*3), total+16 = 0x1dbc, then 4 zero bytes. Their sizes equal the original's limits.
7. IGR setting vs dialog reachability, 8 settings (none, $NOIGR, $IGR0..5) on a synthetic core and on the real core: none = launcHER direct exit over 0x228a5c..68; $NOIGR = branch made unconditional; $IGR0/1/2 = POPS's own four words with masks 0x404f/0x0900/0x090f (dialog reachable); $IGR3/4/5 = j 0x20c08c.
8. Nothing else launcHER stages writes inside 0x2feff0..0x34ee70. Without inputs: built-in DB op table (257 core writes of 906 ops, all end below 0x21b000) and all 624 built-in entries applied (rc 0 each) to a 0xa5-filled core; always-on hooks and pokes on a synthetic core; opcode pass (>70,000 changes on a crafted core) and $RESET_WARMBOOT scan on crafted cores. With POPS_TEST_ELF on the real core: core patches, gp1/recompiler/guard hooks, always-on pokes (rc 0), 624 built-in entries, 80 command lines (rc 0 each), PS1 BIOS shell edits, 72 region/video combinations (rc 0 each), warmboot, padman, opcode pass, and one whole launch order with a skin staged: skin range unchanged by every later stage.
9. Native boundary cases for pops_igr_skin_stage: 19 size cases across the three slots (12 accepted, 7 refused with -EFBIG and core untouched); -ERANGE at core sizes 0, slot offset-1, slot offset and slot end-1 (core untouched); -EINVAL argument cases.
10. Host measurement outside this task (scratch diagnostic, not a repo test): pops_core_runtime_corrections_stage returned -4 for masks 1, 2, 4, 8, 16 and 31 when called on the real core after the always-on hooks (the order launchPOPS uses), and 0 right after the core patches. See decisions_for_owner.

## tests run

1. **command:** python tools/test_pops_igr_skin.py  
   **outcome:** without refs: Ran 30, OK (skipped=16); with POPS_TEST_ELF + POPSTARTER_TEST_ELF: Ran 30, OK (0 skipped)
2. **command:** python tools/test_launch_args.py  
   **outcome:** without refs: PASS (rc 0); with refs: PASS (rc 0)
3. **command:** python tools/test_network_transports.py  
   **outcome:** without refs: PASS (rc 0); with refs: PASS (rc 0)
4. **command:** python tools/test_popfs.py  
   **outcome:** without refs: PASS (rc 0); with refs: PASS (rc 0)
5. **command:** python tools/test_pops_breakpoint.py  
   **outcome:** without refs: Ran 11, OK (skipped=4); with refs: Ran 11, OK
6. **command:** python tools/test_pops_builtin_db.py  
   **outcome:** without refs: Ran 14, OK (skipped=14); with refs: Ran 14, OK
7. **command:** python tools/test_pops_display.py  
   **outcome:** without refs: Ran 21, OK (skipped=6); with refs: Ran 21, OK
8. **command:** python tools/test_pops_external.py  
   **outcome:** without refs: Ran 128, OK (skipped=14); with refs: Ran 128, OK (skipped=3, reason 'optional EE compiler and original MAIN'). First run, before the reader was moved: FAILED (errors=1, setUpClass of the imported test_pops_fix_files); fixed and rerun.
9. **command:** python tools/test_pops_fatfs.py  
   **outcome:** without refs: PASS (rc 0); with refs: PASS (rc 0)
10. **command:** python tools/test_pops_features.py  
   **outcome:** without refs: Ran 29, OK (skipped=2); with refs: Ran 29, OK
11. **command:** python tools/test_pops_fix_files.py  
   **outcome:** without refs: Ran 31, OK (skipped=3); with refs: Ran 31, OK. First run, before the reader was moved: FAILED (Ran 0, errors=1: host compile of the handler_pops.c slice failed on my new function); fixed and rerun.
12. **command:** python tools/test_pops_io_probe.py  
   **outcome:** without refs: Ran 6, OK; with refs: Ran 6, OK
13. **command:** python tools/test_pops_launch_hooks.py  
   **outcome:** without refs: Ran 46, OK (skipped=13); with refs: Ran 46, OK (skipped=3). Not edited: no pinned launch-order line changed.
14. **command:** python tools/test_pops_modes.py  
   **outcome:** without refs: PASS (rc 0); with refs: PASS (rc 0)
15. **command:** python tools/test_pops_module_irx.py  
   **outcome:** without refs: Ran 11, OK (skipped=4); with refs: Ran 11, OK
16. **command:** python tools/test_pops_opcodes.py  
   **outcome:** without refs: Ran 9, OK (skipped=3); with refs: Ran 9, OK
17. **command:** python tools/test_pops_padman.py  
   **outcome:** without refs: Ran 6, OK (skipped=3); with refs: Ran 6, OK
18. **command:** python tools/test_pops_progressive.py  
   **outcome:** without refs: Ran 8, OK (skipped=5); with refs: Ran 8, OK (skipped=3)
19. **command:** python tools/test_pops_read_trace.py  
   **outcome:** without refs: Ran 9, OK; with refs: Ran 9, OK
20. **command:** python tools/test_pops_resident.py  
   **outcome:** without refs: Ran 75, OK (skipped=12); with refs: Ran 75, OK
21. **command:** python tools/test_pops_runtime_corrections.py  
   **outcome:** without refs: Ran 8, OK; with refs: Ran 8, OK
22. **command:** python tools/test_pops_startup_calls.py  
   **outcome:** without refs: Ran 6, OK; with refs: Ran 6, OK
23. **command:** python tools/test_pops_vmc.py  
   **outcome:** without refs: PASS (rc 0); with refs: PASS (rc 0)
24. **command:** python tools/test_pops_warmboot.py  
   **outcome:** without refs: Ran 7, OK (skipped=3); with refs: Ran 7, OK
25. **command:** python tools/test_smap_ipconfig.py  
   **outcome:** without refs: PASS (rc 0); with refs: PASS (rc 0)
26. **command:** python tools/test_sony_ioman_layout.py  
   **outcome:** without refs: PASS (rc 0); with refs: PASS (rc 0)
27. **command:** python tools/test_subq_bridge.py  
   **outcome:** without refs: PASS (rc 0); with refs: PASS (rc 0)
28. **command:** Whole list, final run on the committed content (27 files, each run from the worktree root, first with POPS_TEST_ELF/POPSTARTER_TEST_ELF unset, then set)  
   **outcome:** 27 of 27 rc 0 without refs; 27 of 27 rc 0 with refs; no FAILED/ERROR/Traceback in any log. Note: for part of the no-refs pass a stopped earlier run's leftover loop was still running the same tests in the same worktree; its results were also all rc 0, and the outcomes above are read from the final run's per-file logs.

## ee build check

Compiler: <ps2build>/toolchain/ee/bin/mips64r5900el-ps2-elf-gcc.exe (GCC 15.3.1 20260823). (1) common/src/pops_igr_skin.c compiled to an object with -D_EE -O2 -G0 -Wall -Wextra -Werror -Icommon/include: rc 0, no warnings, text 388 bytes, defines pops_igr_skin_slot and pops_igr_skin_stage, needs only memcpy and memset. (2) launcher/src/handler_pops.c (final content, after the reader was moved) compiled to an object with -D_EE -Os -G0 -Wall against the ps2build SDK headers (packages/core kernel, common, cglue, filexio, debug include dirs plus launcher/include, common/include, launcher/iop/smbman/include, third_party/lzma) in three variants: plain, -DENABLE_PRINTF and -DLAUNCHER_BOOT_TRACE. All rc 0. Warnings: 19 -Wformat-truncation in each, plus 4 -Wformat with ENABLE_PRINTF; none are in the new code, and the unmodified HEAD file gives the same counts (19 and 23) with the same commands. The object references pops_igr_skin_slot and pops_igr_skin_stage. NOT done: no link, no CMake or container build of the launcHER target, no boot-trace target build, nothing run on a console or emulator. The include set is hand-picked, not the project's CMake configuration.

## deviations from original

1. No gate: the original calls the loader only when its abort flag gp+0x38dc is 0 and preset byte 0x10002d is 1 (it is 1 in MAIN); launcHER always tries the three files. Other POPStarter profiles' preset byte was not checked.
2. The original's POPS-folder check FUN_008d8958 and its fatal -666 path are not copied (the check itself was not traced, only modelled as pass/fail).
3. Folder: the original reads pfs1:/POPS/ or mass:/POPS/; launcHER reads the launched VCD's folder (vcdDir, where the all-games TROJAN_n.BIN/PATCH_n.BIN are read). Same folder only when the VCD is in mass:/POPS/. Which partition the original mounts as pfs1: was not traced here.
4. Failed size query (negative lseek): the original zero-fills the slot and that many bytes below it and reports LOADED (measured for -5 and -1); launcHER leaves the slot alone.
5. Read: the original issues one read of the whole slot size and ignores the result; launcHER reads the file's size in pieces of at most 64 KiB and stops at the first short or failed read, then stages what arrived. Same slot when the device delivers everything or stops for good (3 emulated short-read cases); a device that returns short counts but would deliver more on later calls gives a fuller slot in launcHER.
6. Failed seek back to the start: launcHER stages 0 bytes (slot all zeros); the original does not check that seek and reads from the current position (read from its code, not run).
7. A file whose size does not fit launcHER's compare as a positive off_t is handled by the generic size checks rather than the original's 32-bit signed compares; not exercised.
8. Messages: debug-build DPRINTF text, not the original's on-screen log lines; a path longer than PATH_MAX is skipped with a debug line (no such case in the original's fixed paths).
9. Default IGR: under the original no IGR command leaves POPS's own dialog reachable, so the skin shows; launcHER's default is its own direct exit (owner-confirmed, unchanged), so the skin is only seen with $IGR0..2.
10. -ERANGE (staged core too short for the slot) exists only in launcHER; the original writes to fixed addresses.

## not done

1. No console run of anything: that POPS draws a replaced image correctly, that the dialog opens under $IGR0..2 with launcHER's resident code installed, and that YES/NO then behave, are all NOT TESTED.
2. No full target build or link (see ee_build_check).
3. Shared docs not edited (README.md, docs/pops-setup.html, docs/POPSTARTER_R13_INVENTORY.md, docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md, docs/CLOUD_CONTINUATION.md, docs/PR23_CHECKPOINT_HISTORY.md); replacement texts are in doc_updates. README.md line 718 and docs/pops-setup.html currently describe the skin files as going 'beside the game' / 'game directory or VMC folder' without the $IGR0..2 condition or size limits.
4. What POPS does with a slot that is not a valid TIM2 file (for example after a 0-byte file) was not run; only the upload call sites in FUN_00226768 were read.
5. The order of the original's OSD/BIOS/fix-file/command stages after 0x876b18 was taken from the earlier mapping; only the call site and its gates were re-read.
6. Not checked against the skin range 0x2feff0..0x34ee70: user fix files (TROJAN_n.BIN/PATCH_n.BIN can write anywhere; they run after the skin, as in the original), the resident display/widescreen/progressive/pad hooks, MODULE_n.IRX name pokes, pops_resident_hook_recompiler_emit, the runtime corrections on a real launch path, and fix-file finalize video writes.
7. The IGR button combinations behind masks 0x404f / 0x0900 / 0x090f were not decoded into button names.
8. HDD __common layout for the original's device POPS folder is not implemented (vcdDir stand-in).
9. The original's loader was not run with IGR_BG.TM2 and a failed size query, nor with a failed rewind.

## decisions for owner

1. Inventory status wording: I propose PRESENT for 'IGR menu skin' (same convention as MODULE_n.IRX, which also uses a stand-in folder). If the folder stand-in or the default-IGR invisibility should count against it, use PARTIAL instead.
2. Should the skin files also be looked up in the per-game folder or the folder POPS came from? The original has exactly one location (the device's POPS folder); I kept one location (vcdDir) as the task specified.
3. Pre-existing, not caused by this work and not fixed: on the host, pops_core_runtime_corrections_stage returns -4 for every mask when called on the real core after the always-on hooks, which is where launchPOPS calls it; it returns 0 right after the core patches. If that reflects the console path, any launch with $FIX_*/$PSXCORE_FIXES stops at 'Runtime corrections staging failed'. Separately, if that stage keeps a whole-core identity check and stays after the skin stage, a staged skin would also change the core it compares. Needs a look by whoever owns runtime corrections.
4. tools/test_pops_fix_files.py compiles the slice of handler_pops.c from 'static int readFullFile(' to '/* Driver names within one role' on the host with -Werror. Any track that adds a function inside that slice which uses headers or functions outside its source list breaks that test and test_pops_external.py. I hit this and moved my reader below the slice.
5. The temp-isolation one-liner in the task (export TMP=... TEMP="$TMP") did not isolate Python on this machine: tempfile still used the shared user temp dir because Git Bash sets TMPDIR, which takes priority. Exporting TMP, TEMP and TMPDIR separately works. Other tracks using fixed-name files in temp may collide.
6. Whether to keep copying the original's lack of any TIM2 check (a wrong file blanks or corrupts the dialog art) or guard it later is listed in the quirk entries.

## doc updates


### inventory rows

docs/POPSTARTER_R13_INVENTORY.md, replace line 153 (`| IGR menu skin (IGR_BG/NO/YES.TM2) | **MISSING** |`) with:

| IGR menu skin (IGR_BG/NO/YES.TM2) | **PRESENT** (2026-11-11): the three files are copied raw over Sony's dialog images at `0x2feff0` / `0x34b2f0` / `0x34d0b0` with the original's limits (312,064 / 7,612 / 7,612 bytes), zero fill and no content check (`pops_igr_skin_stage`), staged right after the always-on launch hooks. The original's loader `FUN_0087e464`, run under emulation with its file I/O modelled, leaves a byte-identical core in 45 runs over both of its backends (every boundary size, random sizes and contents, no files); 9 more runs cover its gates, a short read and a failed size query. Read from the launched VCD's folder, where the all-games `TROJAN_n.BIN` / `PATCH_n.BIN` are read (the original: the device's `POPS` folder). Shown only with `$IGR0..2`: launcHER's default direct exit, `$NOIGR` and `$IGR3..5` never open Sony's dialog. The original's preset/abort gate and POPS-folder check are not copied. See [POPSTARTER_IGR_SKIN.md](POPSTARTER_IGR_SKIN.md). **NOT TESTED** on a console |

Line 101 (`| no IGR command | POPS default | ...`), append to the status cell: `; Sony's dialog never opens in this case, so the IGR skin is not shown without `$IGR0..2``

Remaining work item 4, replace its first sentence with: `OSD replacement, BIOS.BIN and physical disc boot.` (the rest of the item unchanged).

### quirks

Entries for docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md, table format `| # | POPStarter behaviour (copied) | Possible fix later |`, numbers left for the lead:

| | The IGR skin loader (`FUN_0087e464`) checks only the file's size. No `TIM2` signature, version, dimensions or picture type is tested, and the slot's old contents are not looked at: any file up to the limit replaces Sony's image. Copied. What POPS draws from a file that is not a matching TIM2 was not run. | Accept only a TIM2 file whose picture matches Sony's (400x260 for the background, 74x34 for the buttons, picture type 2) and keep Sony's image otherwise. |
| | A 0-byte `IGR_BG.TM2`, `IGR_NO.TM2` or `IGR_YES.TM2` counts as loaded: the slot is zero-filled and Sony's image is gone. Copied. | Treat an empty file as missing. |
| | The limit for `IGR_NO.TM2` and `IGR_YES.TM2` is `0x1dbc` (7,612 bytes) although their slot is `0x1dc0` (7,616); the background's limit equals its slot. A button file padded to the slot size is `TOO BIG !`. Copied. | Accept up to the slot size. |
| | The slot is zero-filled before the file is read and the read's result is not checked, so a read that fails or delivers less than the file's size leaves what arrived followed by zeros and still counts as loaded. Copied (launcHER stages the bytes that arrived). | Read the whole file first and keep Sony's image unless all of it arrived. |
| | The three files are loaded whatever the IGR setting, also when the dialog can never open (`$NOIGR`, `$IGR3..5`; in launcHER also with no IGR command, where its own direct exit is used). Copied. | Skip the reads when Sony's dialog is unreachable. |

For the record, NOT copied (see docs/POPSTARTER_IGR_SKIN.md): a failed size query makes the original zero-fill the slot and that many bytes below it; launcHER leaves the slot alone.

### hardware checklist

IGR skin (NOT TESTED on a console): put a visibly different `IGR_BG.TM2` (TIM2, 400x260, 24-bit, at most 312,064 bytes) and `IGR_YES.TM2` / `IGR_NO.TM2` (TIM2, 74x34, 24-bit, at most 7,612 bytes each) in the folder that holds the game's VCD; add `$IGR0` to the game's config; in game hold the `$IGR0` combo and check that Sony's reset dialog opens with the replaced background and buttons, that NO returns to the game and YES exits. Then: (a) remove `$IGR0` and confirm launcHER's default reset combo still exits directly with no dialog; (b) with `$IGR0`, make one file one byte larger than its limit and confirm Sony's own image is kept for that file and the game still starts; (c) with no skin files, confirm the dialog shows Sony's images. A debug build logs NOT FOUND / TOO BIG ! / LOADED per file.

### user facing

README.md line 718, replace `- **Custom UI graphics:** Place `IGR_BG.TM2`, `IGR_YES.TM2`, or `IGR_NO.TM2` beside the game.` with:

- **Custom reset-dialog graphics (POPStarter's IGR skin, not yet tested on a console):** put `IGR_BG.TM2` (at most 312,064 bytes), `IGR_YES.TM2` and `IGR_NO.TM2` (at most 7,612 bytes each) in the folder that holds the game's `.VCD`, next to the all-games `TROJAN_n.BIN` / `PATCH_n.BIN`. They replace the pictures of Sony's own reset dialog, which launcHER only shows when the game's config has `$IGR0`, `$IGR1` or `$IGR2`. With the default reset combo the game exits directly and the pictures are never shown. The files are copied as they are, with no check: use TIM2 files like Sony's (background 400x260, buttons 74x34, 24-bit). A file over its size limit is ignored and Sony's picture stays.

docs/pops-setup.html, section 'Custom IGR Background Graphics', replace the paragraph before the list with:

<p>
  Not yet tested on a console. Place TIM2 image files in the folder that holds the game's VCD (the folder the all-games <code>TROJAN_n.BIN</code> / <code>PATCH_n.BIN</code> are read from) to replace the pictures of Sony's own reset dialog. launcHER only shows that dialog when the game's configuration has <code>$IGR0</code>, <code>$IGR1</code> or <code>$IGR2</code>; with the default reset combo the game exits directly and the pictures are never shown. Files are copied without any check, so use TIM2 files like Sony's: 24-bit, 400x260 for the background and 74x34 for the buttons. A file over its limit is ignored.
</p>

and the list with:

<ul>
  <li><code>IGR_BG.TM2</code>: dialog background, at most 312,064 bytes.</li>
  <li><code>IGR_YES.TM2</code>: YES button picture, at most 7,612 bytes.</li>
  <li><code>IGR_NO.TM2</code>: NO button picture, at most 7,612 bytes.</li>
</ul>

(The existing list's wording 'Selected confirmation / cancellation button texture' was not verified; which state of each button the picture is used for was not measured.)
