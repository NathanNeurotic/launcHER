# User BIOS.BIN: author's report

Written by the track's author when the stage ended. Copied as written; not re-verified.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## summary

POPStarter r13's user BIOS.BIN loading and the gates its flags drive are implemented in two local commits on branch pr23/rom of the rom worktree (nothing pushed, no PR touched, no console/rig used). Everything below is from host tests and from running the original's own code under Unicorn; NOTHING WAS TESTED ON A CONSOLE, and no real PS1 BIOS was used (every test file is a counter pattern).

Step A (6a7b617): PopsUserRomState names the original's loader words (gp+0x38a4 bios_all, gp+0x3b98 bios_game, the four OSD words gp+0x343c/0x3430/0x3878/0x344c, and gp+0x3704 osd_off). The BIOS shell edits, the region pass, compatibility mode 6 and the 0x2525b0 row of the three $UNDO_ commands take it and skip what the original skips; with every word zero the bytes are unchanged.

Step B (a3cab9c): pops_user_bios_stage (pure buffer logic, common/src/pops_modes_patches.c) and pops_user_bios_load (file side, launcher/src/handler_pops.c). Per folder, after the built-in entry and before that folder's TROJAN/PATCH files; all-games folder (vcdDir) first, then the game's (gameConfigDir). A file whose size, as a signed 32-bit value, is at least 0x7ff8f has its first 0x7ff90 bytes copied over 0x24bc20..0x2cbbaf, bytes 00 10 written at 0x20079a (unchecked, as the original) and its flag set. There is no content or integrity check in the original, so none here; the inventory row name 'User BIOS.BIN with integrity check' is wrong.

Measured facts about the original that shaped it: the loader is FUN_0088019c; it does open, lseek END, lseek SET (result ignored), size test, one read of 0x7ff90 bytes straight into POPS (result ignored); BIOS flags do not gate a second load (the game's file loads over the all-games one). The only later stage that needed a fix for a replaced ROM range was the fix-file session's expected word at 0x2525b0 (new pops_fix_context_rom_loaded); shell edits are skipped, region writes are unchecked, the warm-boot pass is a pure scan, the opcode pass ranges do not overlap the ROM range or 0x20079a.

Because launcHER runs the user's commands before the fix files (pre-existing difference; the original runs them after both loads), the launch first probes both files (pops_user_bios_load with a NULL core: open, size, close, nothing read or written) and gives the commands those two flags; if the later real loads disagree the launch stops with -EIO.

All 27 tools/test_*.py files pass both without and with the reference inputs (per-file outcomes in tests_run). New doc: docs/POPSTARTER_USER_BIOS.md. The six shared docs were not edited; replacement text is in doc_updates.

## commits

1. 6a7b6171a6c2276a463103cc6c4bfdc3cee35837 feat(pops): POPStarter's loader state and the gates it drives
2. a3cab9c feat(pops): POPStarter's user BIOS.BIN

## files changed

1. common/include/pops_modes_patches.h
2. common/src/pops_modes_patches.c
3. launcher/src/handler_pops.c
4. tools/test_pops_user_bios.py (new, 38 tests: Native, Reader, Original, Source)
5. tools/trace_original_pops_user_bios.py (new tracer for the original's loader, gates, mode dispatcher, region and shell slices)
6. docs/POPSTARTER_USER_BIOS.md (new)
7. docs/POPSTARTER_LAUNCH_HOOKS.md (Step A: text for the gated stages)
8. .github/workflows/build.yml (step: python tools/test_pops_user_bios.py)
9. tools/test_pops_launch_hooks.py (deliberate: launch-order pins now name the _rom call variants; same commit as the handler change, 6a7b617)
10. tools/test_pops_resident.py (pin updated to pops_apply_all_config_patches_rom()
11. tools/test_pops_fix_files.py (three wrapper calls pass NULL for the new rom parameter)

## measured evidence

1. All of the following are the original's own code (POPSTARTER.ELF MAIN, unpacked at 0x870000, gp 0x9b68f0) run under Unicorn 2.1.4 on the real POPS core, compared with launcHER's host-compiled functions. They are emulated/host results, NOT console results.
2. Loader FUN_0088019c vs pops_user_bios_stage: 2 folders x 2 back ends (pfs1:/mass:) x sizes {absent, 0, 0x7ff8e, 0x7ff8f, 0x7ff90, 0x80000, 0x100000} x {no flag, each of 7 flags} = 224 runs (88 loads): return value, whole core and flags equal.
3. Loader with the lseek result forced (-5, -1, 0x7ff8e, 0x7ff8f, 0x7fffffff, 0x80000000, 0xffffffff): 28 cases equal. Accept iff signed 32-bit result > 0x7ff8e.
4. Loader vs the launcher's own reader (handler_pops.c text from readFullFile to pops_stage_fix_files built for the host with open/lseek/read/close shims) on real files: 14 cases plus the two-folder sequence through pops_stage_fix_files, whole core equal.
5. Launch-function gates plus loader entry gates vs pops_user_bios_skipped: 16 flag cases; 8 preset slots x values {5,6} x 2 folders (only a 6 skips the call). The eight preset bytes (0x100018..0x10001f of the ELF's own segment) were read from the MAIN file and are all zero; the test asserts it.
6. Shell-edit slice 0x878f64..0x878fc4: 131 flag cases, bytes equal.
7. Region window 0x879034..0x8795f0: 342 cases byte-for-byte equal; 18 more (European licence, auto video disabled, selector set, which launcHER's two inputs cannot express) equal outside the four PAL sites only.
8. Mode dispatcher FUN_008dc2c4: 298 cases (mode 6 with all 128 flag combinations and both words, other modes with each flag): bytes, gp+0x3704 and the notice equal.
9. $COMPATIBILITY_0x06 and the three $UNDO_ commands through the original's command reader with loader flags preset: 72 command/flag/word cases, bytes and gp+0x3704 equal.
10. Shell slice, region window (4 licences) and the $RESET_WARMBOOT pass over a core the loader replaced: 1 load, whole core equal.
11. I/O sequence of the loader (scratch probe, not a committed test): open flags 1; lseek(0,END); lseek(0,SET); read(fd, 0x24bc20, 0x7ff90); close. Word at 0x200798 goes 0x14400005 -> 0x10000005. A 0x7ff8f-byte file leaves POPS's byte at 0x2cbbaf; nothing past 0x2cbbaf is written.
12. Mutation check of the new tests (7 mutants of the Step B code, each run with the reference inputs, source restored after each): minimum size changed -> 11 failures; branch halfword wrong -> 11; fix-context follow-up removed -> 3; reader reads past 0x7ff90 -> 2; all-games gate missing osd_game_b -> 5; flag set for the wrong folder -> 9; clamp removed from stage -> 1. All 7 were detected. A mutant that moves the load to a different position in the launch was NOT run (the order is covered by a Source pin and a Reader test with PATCH payloads inside the ROM range, but that was not mutation-checked).
13. Without the reference inputs the same file runs 27 tests (11 skipped): the functions on synthetic cores, the handler's reader on files of each size in each folder, and the source pins.

## tests run

1. **command:** Environment for every run: TMP/TEMP = <scratch>/tmp-rom-bios, PYTHONDONTWRITEBYTECODE=1; 'with refs' = POPS_TEST_ELF=<workspace>/POPS/POPS.ELF and POPSTARTER_TEST_ELF=<workspace>/POPSLoader/bin/POPSLDR/PROFILES/MAIN/POPSTARTER.ELF; 'without' = both unset. Files run one at a time, sequentially, on the Step B content (git status clean, no diff against a3cab9c).  
   **outcome:** 27 of 27 files exit 0 without refs; 27 of 27 exit 0 with refs. No failures, no errors.
2. **command:** python tools/test_launch_args.py  
   **outcome:** without: rc=0; with: rc=0
3. **command:** python tools/test_network_transports.py  
   **outcome:** without: rc=0; with: rc=0
4. **command:** python tools/test_popfs.py  
   **outcome:** without: rc=0; with: rc=0
5. **command:** python tools/test_pops_breakpoint.py  
   **outcome:** without: 11 tests OK (skipped=4); with: 11 tests OK
6. **command:** python tools/test_pops_builtin_db.py  
   **outcome:** without: 14 tests OK (skipped=14); with: 14 tests OK
7. **command:** python tools/test_pops_display.py  
   **outcome:** without: 21 tests OK (skipped=6); with: 21 tests OK
8. **command:** python tools/test_pops_external.py  
   **outcome:** without: 128 tests OK (skipped=14); with: 128 tests OK (skipped=3, reason printed: 'optional EE compiler and original MAIN')
9. **command:** python tools/test_pops_fatfs.py  
   **outcome:** without: rc=0; with: rc=0
10. **command:** python tools/test_pops_features.py  
   **outcome:** without: 29 tests OK (skipped=2); with: 29 tests OK
11. **command:** python tools/test_pops_fix_files.py  
   **outcome:** without: 31 tests OK (skipped=3); with: 31 tests OK
12. **command:** python tools/test_pops_io_probe.py  
   **outcome:** without: 6 tests OK; with: 6 tests OK
13. **command:** python tools/test_pops_launch_hooks.py  
   **outcome:** without: 46 tests OK (skipped=13); with: 46 tests OK (skipped=3; the same 3 were skipped before this work, reasons not printed by that runner)
14. **command:** python tools/test_pops_modes.py  
   **outcome:** without: rc=0; with: rc=0
15. **command:** python tools/test_pops_module_irx.py  
   **outcome:** without: 11 tests OK (skipped=4); with: 11 tests OK
16. **command:** python tools/test_pops_opcodes.py  
   **outcome:** without: 9 tests OK (skipped=3); with: 9 tests OK
17. **command:** python tools/test_pops_padman.py  
   **outcome:** without: 6 tests OK (skipped=3); with: 6 tests OK
18. **command:** python tools/test_pops_progressive.py  
   **outcome:** without: 8 tests OK (skipped=5); with: 8 tests OK (skipped=3, 'optional EE compiler and original MAIN')
19. **command:** python tools/test_pops_read_trace.py  
   **outcome:** without: 9 tests OK; with: 9 tests OK
20. **command:** python tools/test_pops_resident.py  
   **outcome:** without: 75 tests OK (skipped=12); with: 75 tests OK
21. **command:** python tools/test_pops_runtime_corrections.py  
   **outcome:** without: 8 tests OK; with: 8 tests OK
22. **command:** python tools/test_pops_startup_calls.py  
   **outcome:** without: 6 tests OK; with: 6 tests OK
23. **command:** python tools/test_pops_user_bios.py (new)  
   **outcome:** without: 38 tests OK (skipped=11); with: 38 tests OK, 0 skipped
24. **command:** python tools/test_pops_vmc.py  
   **outcome:** without: rc=0; with: rc=0
25. **command:** python tools/test_pops_warmboot.py  
   **outcome:** without: 7 tests OK (skipped=3); with: 7 tests OK
26. **command:** python tools/test_smap_ipconfig.py  
   **outcome:** without: rc=0; with: rc=0
27. **command:** python tools/test_sony_ioman_layout.py  
   **outcome:** without: rc=0; with: rc=0
28. **command:** python tools/test_subq_bridge.py  
   **outcome:** without: rc=0; with: rc=0
29. **command:** python <scratch>/rom-bios/mutate.py (7 source mutants, each followed by python tools/test_pops_user_bios.py with refs, source restored)  
   **outcome:** All 7 mutants made the test file fail (1 to 11 failing tests each); sources restored, diffstat unchanged afterwards.

## ee build check

Run again on the committed tree (a3cab9c) with <ps2build>/toolchain/ee/bin/mips64r5900el-ps2-elf-gcc.exe:
1. `-fsyntax-only -Wall -Wextra -Icommon/include common/src/pops_modes_patches.c` -> rc=0, no diagnostics.
2. `-c -O2 -G0 -Wall -Wextra -Icommon/include common/src/pops_modes_patches.c -o <scratch>/rom-bios/eeobj/pops_modes_patches.o` -> rc=0 (a real EE object; earlier inspection showed the symbols pops_user_bios_stage, pops_user_bios_skipped, pops_user_bios_size_ok, pops_fix_context_rom_loaded and the pops_user_rom_* helpers).
3. `-fsyntax-only -Wall -D_EE -Ilauncher/include -Icommon/include` plus `-isystem` for ps2build packages/core/{kernel,cglue,common,filexio,debug,pad,iopreboot}/include on launcher/src/handler_pops.c, in three configurations: default -> rc=0, 0 warnings; -DENABLE_PRINTF -> rc=0, 4 warnings (the -Wformat warnings at pre-existing DPRINTF lines seen before this work); -DLAUNCHER_BOOT_TRACE -> rc=0, 0 warnings. (An earlier run with -Wextra in the default configuration showed 6 pre-existing -Wempty-body warnings from empty DPRINTF bodies.)
The only changed common/src file is pops_modes_patches.c. NOT done: no link, no CMake build, no launcher ELF was produced, handler_pops.c was syntax-checked only (not compiled to an object), and the restricted include set is mine, not the project's build flags (adding every package include dir made loadcore's sys/types.h shadow newlib's).

## deviations from original

1. Commands before files (pre-existing): the original runs the user's commands after both BIOS loads; launcHER runs them before its fix files. To give mode 6 and the $UNDO_ commands the flags they would see, the launch probes both files first (open, lseek, close; nothing read) and stops with -EIO if the later real loads disagree. So each BIOS.BIN is opened twice, and a launch can fail with -EIO where the original has no such failure.
2. Text order of $COMPATIBILITY_0x and $UNDO_ (pre-existing, NOT changed): the original runs them in the order written; launcHER applies $UNDO_ first, then the modes. With $COMPATIBILITY_0x06 written before a $UNDO_ command and no BIOS.BIN, the original ends with 0x2525b0=0x1bfc and launcHER with 0x0648. common/include/pops_config.h:46, README.md:682 and docs/pops-setup.html:302 say this matches the original; measured, it does not.
3. Folders: launcHER reads BIOS.BIN from the folder the .VCD is in (all games) and from <that folder>/<VCD name>/ (one game), the same stand-ins it uses for TROJAN/PATCH files, not literally pfs1:/POPS/ and mass:/POPS/. Same folders on a mass:/POPS/ layout.
4. Read: the original issues one read of 0x7ff90 bytes straight into POPS at 0x24bc20; launcHER reads in a loop into the fix-file scratch buffer at 0x01f00000 and then copies. A short or failed read still counts as a load of what arrived, as in the original, but with a device that returns short reads launcHER keeps reading until 0x7ff90 or n<=0 where the original would stop after one call.
5. Fix-file bookkeeping has no counterpart in the original: after a load pops_fix_context_rom_loaded takes the expected word at 0x2525b0 from the core (the one tracked site inside the ROM range); every site outside the range is still verified, and a mismatch there fails the launch.
6. Words not kept: gp+0x38dc (launch given up) and gp+0x3460 (game folder missing) have no launcHER state; a missing game folder is simply a file that does not open. The eight preset compatibility slots (a 6 in any skips both loader calls in the original) do not exist in launcHER; they are zero in the MAIN build, other builds were not looked at.
7. Messages: the original prints 'Opening <path>... NOT FOUND/DONE', '<path> is too small', 'User BIOS == <path>' and the mode 6 'please delete BIOS.BIN' notice through its own print routine; launcHER writes them with DPRINTF only, which is empty unless ENABLE_PRINTF or LAUNCHER_BOOT_TRACE, so a release build shows nothing.
8. $NOBOOT / $BIOS is launcHER's own command (0x2525b0 back to 0x1bfc); with a BIOS.BIN loaded it now leaves the word alone, by analogy with every writer of that word in the original. There is no original behaviour to match.
9. launcHER's own automatic mode 6 (Tekken, MENU/.EXE serials, compatibility DB) goes through the same gate and is skipped under a user BIOS; the original has no such automatic list.
10. Path too long: pops_user_bios_load returns -ENAMETOOLONG and the launch fails; the original has fixed buffers and no such check.
11. Size of files of 2 GiB or more: the test is made on the low 32 bits of the lseek result as a signed value, mirroring the original's compare on its 32-bit result; what the original's drivers actually return for such files was not measured.
12. Region pass: the combination (auto video disabled, selector set) for a European licence cannot be expressed by launcHER's two inputs (pre-existing); 18 such cases differ from the original in the four PAL sites.
13. The OSD loader that sets the other four words is not implemented, so in a real launch only bios_all, bios_game and osd_off are ever set; the functions follow all seven and were compared with all seven.

## not done

1. No console test of any kind. Nothing here was run on a PS2.
2. No real PS1 BIOS dump was used; what POPS does with a user ROM, or with a file that is not a PS1 BIOS, was not observed.
3. No full EE build or link; no launcher ELF produced (see ee_build_check).
4. The effect at runtime of the 0x20079a write (POPS's 'xCdInit failed' path never taken) was not worked out.
5. The OSD replacement loader (the four other words) is not implemented.
6. Builds of POPStarter other than MAIN were not looked at (preset slots, loader address).
7. A mutant that moves the load position in the launch was not run.
8. The pre-existing text-order difference of $UNDO_ vs $COMPATIBILITY_0x was not fixed, and the claims about it in common/include/pops_config.h:46, README.md:682 and docs/pops-setup.html:302 were not corrected (README and pops-setup.html are off limits; text is in doc_updates).
9. The six shared docs were not edited; their text is returned in doc_updates.
10. tools/test_pops_builtin_db.py and tools/test_pops_progressive.py are still not steps in .github/workflows/build.yml (pre-existing; not part of this task, left alone).
11. Three tests in each of test_pops_external.py, test_pops_progressive.py and test_pops_launch_hooks.py are skipped even with the reference inputs (they need an optional EE compiler setting); unchanged by this work.

## decisions for owner

1. $NOBOOT / $BIOS under a user BIOS: I made it leave 0x2525b0 alone (and otherwise behave as before, clearing osd_off). It is launcHER's own command, so there is no original to match; say if it should write regardless.
2. osd_off (gp+0x3704) is seeded from the built-in entry's mode 6. Consequence: built-in entry 58 + a $UNDO_ command + a later mode 6 now ends at 0x1bfc as the original does. pops_fix_context_init_builtin now also accepts POPS's own 0x1bfc at 0x2525b0, which fixes a pre-existing -EINVAL launch failure for entry 58 with a $UNDO_ command.
3. launcHER's own automatic mode 6 (Tekken, MENU/.EXE serials, compatibility DB) is skipped under a user BIOS like any mode 6. Confirm that is wanted.
4. The 0x20079a write is unchecked, as the original's and as the shell edits. This is exact-match over the house rule that guarded writes check expected bytes first. A guard (expect 0x1440 or 0x1000) would be a one-line change if preferred.
5. Probe-then-load with -EIO on disagreement is the price of running commands before fix files. The alternative that removes the probe is to move the commands after the fix files as the original does, which is a larger change to launch order.
6. Folder mapping: vcdDir and gameConfigDir stand in for POPS/ and POPS/<game>/. Confirm, or name the folders BIOS.BIN should come from on each device.
7. No preset-slot gate was added (the bytes are zero in MAIN). Say if other POPStarter builds matter.
8. Notices are DPRINTF only, so a release build tells the user nothing when a BIOS.BIN is loaded, too small, or when mode 6 is left out because of it. A visible message would be an improvement beyond the original.
9. Any open failure of BIOS.BIN is treated as 'not found' and is not fatal (as the original), unlike fix files where a read error fails the launch.
10. A NULL rom argument to pops_stage_fix_files means a local zero state (used by existing tests); the launch always passes its state.
11. The text-order difference between $UNDO_ and $COMPATIBILITY_0x is real and the repository's comment and user docs claim the opposite. Decide whether to fix the order (exact parity) or correct the text.
12. tools/test_pops_builtin_db.py and tools/test_pops_progressive.py are not run by .github/workflows/build.yml.

## doc updates


### inventory rows

docs/POPSTARTER_R13_INVENTORY.md

(1) Replace the row `| User BIOS.BIN with integrity check | **MISSING** |` (line 155) with:

| User `BIOS.BIN` (all games, and per game). There is no integrity check: the original's only test is the size (at least `0x7ff8f` bytes, signed 32-bit compare) | **PRESENT** (2026-11-11): `BIOS.BIN` in the folder the `.VCD` is in (all games) and in the folder named after the `.VCD` (one game), each read before that folder's `TROJAN`/`PATCH` files and after the built-in entry, the game's over the all-games one. First `0x7ff90` bytes over `0x24bc20..0x2cbbaf`, `0x1000` at `0x20079a`, loader flag set (`gp+0x38a4` / `gp+0x3b98`). With a flag set the three shell edits, the region write at `0x2649a0` (and the unknown-licence writes), compatibility mode 6 and the `0x2525b0` row of the `$UNDO_` commands are left out as the original leaves them out. Loader `FUN_0088019c` run under emulation against `pops_user_bios_stage`: 224 runs (88 loads), whole core and flags equal; the handler's own reader on files: 14 cases, whole core equal. See [POPSTARTER_USER_BIOS.md](POPSTARTER_USER_BIOS.md). **NOT TESTED** on a console, and not with a real PS1 BIOS |

(2) In the `$UNDO_COMPATIBILITY_CODES`, `$UNDO_GAME_FIXES`, `$UNDO_LIBCRYPT_FIX` row (line 90), replace the status text `every core write matches the original's handlers (interpreter test, external MAIN), applied before `$COMPATIBILITY_0x` as in the original.` with:

every core write matches the original's handlers (interpreter test, external MAIN); with a user `BIOS.BIN` loaded the `0x2525b0=0x1bfc` write is left out, as in the original (72 command/flag cases through the original's command reader). launcHER applies the `$UNDO_` commands before `$COMPATIBILITY_0x`; the original runs both in the order they are written, so `$COMPATIBILITY_0x06` written before a `$UNDO_` command ends with `0x2525b0=0x1bfc` there and `0x0648` here (not changed yet).

(3) After the sentence `` `$NOBOOT` keeps only the real `0x2525b0=0x1bfc` OSD write.`` (line 120) add:

With a user `BIOS.BIN` loaded `$NOBOOT` writes nothing, like every writer of that word in the original (`$NOBOOT` is launcHER's own command).

(4) Replace the sentence `The BIOS write is skipped only when a user BIOS/OSD file was loaded.` (line 131) with:

When a user `BIOS.BIN` (or, in the original, an OSD file) was loaded: for a known licence the write at `0x2649a0` is left out and the letters at `0x2cbb72` and `0x20f6cc` and the PAL change are still made; for an unknown licence `0x264994`, `0x264998`, `0x26499c`, `0x2649a0` and the zero bytes at `0x20f6cc`, `0x20f6d8`, `0x20f6dc`, `0x20f6e0` are left out and `0x2cbb72` is still written (inside the user's file, offset `0x7ff52`). 342 cases against the original's region code, byte for byte.

(5) Replace list item 4 (lines 178-180) with:

4. IGR skin, OSD replacement and physical disc boot. `BIOS.BIN` is carried ([POPSTARTER_USER_BIOS.md](POPSTARTER_USER_BIOS.md)); the stages that follow already take the OSD loader's four words, so an OSD loader only has to set them.

### quirks

docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md — new section, entries to be numbered by the owner:

## User `BIOS.BIN` (docs/POPSTARTER_USER_BIOS.md)

Found by running the original's loader `FUN_0088019c` and its launch code under Unicorn on the real POPS core (`tools/test_pops_user_bios.py`). Not console runs.

| # | POPStarter behaviour (copied) | Possible fix later |
|---|---|---|
| | The only test on `BIOS.BIN` is its size. No byte is looked at: any file of `0x7ff8f` bytes or more replaces POPS's PS1 ROM. Copied. | Check for a PS1 BIOS (size `0x80000`, known strings or a hash list) and say when the file is refused. |
| | Only the first `0x7ff90` bytes are loaded (`0x24bc20..0x2cbbaf`). The last `0x70` bytes of a `0x80000`-byte dump are never loaded; POPS's own bytes stay there. A larger file loads its first `0x7ff90` bytes. Copied. | Work out why POPS's ROM copy stops there before changing it. |
| | The smallest file that loads is `0x7ff8f` bytes, one short of what is read: it leaves POPS's own byte at `0x2cbbaf`. Copied. | Require `0x7ff90`. |
| | The size test is a signed 32-bit compare on the lseek result: a failed lseek (negative) and a result of `0x80000000` or more are reported as "too small". Copied (launcHER tests the low 32 bits the same way; what the original's drivers return for 2 GiB or more was not measured). | Report an lseek error as an error. |
| | The results of the rewind and of the read are not looked at: a short or failed read still sets the flag and makes the `0x20079a` write, with part of POPS's ROM left in place. Copied (launcHER reads in pieces and counts what arrived, but still treats it as loaded). | Fail the launch, or leave POPS's ROM whole, when fewer than `0x7ff90` bytes arrive. |
| | After a load the halfword at `0x20079a` is set to `0x1000` without looking at what was there (`0x14400005` becomes `0x10000005` at `0x200798`): the branch after POPS's disc init always skips the path with POPS's `xCdInit failed` message. What that does in a launch was not worked out. Copied, unchecked. | Check the word first; find out what the branch protects. |
| | The game's `BIOS.BIN` loads over the all-games one, over anything the all-games `TROJAN`/`PATCH` files wrote into `0x24bc20..0x2cbbaf`, over the earlier write at `0x263ca8` and over a built-in entry's `0x2525b0`. Copied. | Load one file (the game's if present) before any patch. |
| | With a `BIOS.BIN` loaded, compatibility mode 6 writes nothing and only prints a notice asking for the file to be deleted; the `$UNDO_` commands leave `0x2525b0` alone. When a `PATCH` file's mode 6 ran before the game's `BIOS.BIN` loaded, `gp+0x3704` stays set although the load replaced the word. Copied. launcHER's notice goes to the debug log only. | Show the notice on screen; clear the word's state on a load. |
| | The region letter at `0x2cbb72` is written into the user's file (offset `0x7ff52`) on every launch, and `$RESET_WARMBOOT` scans and rewrites the user's bytes as it does POPS's own. Copied. | Leave a user ROM untouched, or check the bytes first. |
| | Not a POPStarter behaviour: launcHER runs the user's commands before the fix files, so it looks at both `BIOS.BIN` files first to give the commands the flags, and stops the launch (`-EIO`) if the files changed in between. | Run the commands after the fix files, as the original does. |

### user facing

For README.md (POPS section) and docs/pops-setup.html:

**Your own PS1 BIOS (`BIOS.BIN`), POPStarter launches only. Not yet tested on a console, and not yet tried with a real BIOS dump.**

- Put `BIOS.BIN` next to your `.VCD` files to use it for every game in that folder, or in the folder named after one game (`<VCD name>/BIOS.BIN`, where that game's `CHEATS.TXT` and `PATCH_n.BIN` go) to use it for that game only. If both exist, the game's file is the one that ends up loaded.
- The file must be at least 524,175 bytes (`0x7ff8f`). Only its first 524,176 bytes (`0x7ff90`) are used; a normal 512 KB dump is larger than that, and its last 112 bytes are not loaded. This is how POPStarter does it.
- Nothing else about the file is checked, exactly as in POPStarter: a wrong file of the right size is loaded all the same and the game will most likely not start. A file that is too small is ignored and POPS's built-in BIOS is used.
- With a `BIOS.BIN` loaded, launcHER (like POPStarter) no longer makes its edits to the built-in BIOS shell, and `$COMPATIBILITY_0x06`, `$NOBOOT` and the boot-logo part of the `$UNDO_` commands do nothing: the boot screen is whatever your BIOS shows. To use compatibility mode 6, remove `BIOS.BIN`.
- launcHER does not include a PS1 BIOS; you must supply your own dump. This file is unrelated to `EMBER/bios.bin`.
- On a release build nothing on screen says whether the file was loaded.

Correction for README.md line 682 and docs/pops-setup.html line 302: replace `They run before `$COMPATIBILITY_0x`, so a compatibility mode you set still applies.` with `In launcHER they run before `$COMPATIBILITY_0x`, so a compatibility mode you set still applies; POPStarter itself runs them in the order they are written in the file.`

### hardware checklist

Console checks for the user BIOS.BIN (none done; each compared with POPStarter r13 on the same files where possible):

1. Regression: no BIOS.BIN anywhere; a known-good game boots as before (shell edits, region, mode 6 unchanged).
2. Real PS1 BIOS dump as BIOS.BIN next to the .VCD (all games): game boots; boot screen is the dump's.
3. Real dump in the game's folder only: that game uses it, another game in the same folder does not.
4. Different dumps in both folders: the game's one is used.
5. File of 0x7ff8e bytes: ignored, POPS's BIOS used. File of 0x7ff8f bytes: loaded.
6. `$COMPATIBILITY_0x06` in CHEATS.TXT with a BIOS.BIN: boot screen not removed; same without BIOS.BIN: removed.
7. A title launcHER applies mode 6 to by itself (Tekken, a MENU/.EXE serial) with a BIOS.BIN.
8. A European LibCrypt title and an unknown-licence disc with a BIOS.BIN (region letter written into the user's ROM; `0x2649a0` left alone).
9. `$RESET_WARMBOOT` with a BIOS.BIN.
10. `$UNDO_COMPATIBILITY_CODES` with a built-in entry that sets mode 6, with and without BIOS.BIN.
11. Each device reading the file: USB, internal HDD (PFS), SMB, MX4SIO; note whether a read ever comes back short.
12. A wrong file of the right size (expect no boot; confirm launcHER and POPStarter fail the same way).
13. Disc swap (`DISCS.TXT`) and in-game reset with a BIOS.BIN loaded.
14. Whether the `0x20079a` change has any visible effect (the `xCdInit failed` path).
