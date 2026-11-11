# Physical PS1 disc (host part): author's report

Written by the track's author when the stage ended. Copied as written; not re-verified.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## summary

Host-verifiable part of POPStarter r13's physical PS1 disc path is done and committed locally on pr23/disc (1f8c525) in the disc worktree. Nothing was pushed, no PR touched, no console/rig used. NOT TESTED on a console: every result is a host test or the original's code run under Unicorn with libcdvd, SifLoadModule, file I/O and printf replaced by models (a model returns what the test tells it to; it shows what the original does with an answer, never what a PS2 drive answers).

What exists now:
- common/src/pops_physical_disc.c + common/include/pops_physical_disc.h (pure buffer logic, no I/O): pops_physical_disc_plan (the drive block's decision), pops_physical_disc_message (the two fatal texts), pops_physical_disc_stage(core, core_size, disc_type) (0x200794 = 0x0000202d plus the $MUTE_CDDA writes through the existing pops_apply_original_tokens(POPS_TOK_MUTE_CDDA); checks Sony's bytes at every site first, -EILSEQ/-ERANGE/-EINVAL with no partial write), pops_physical_disc_fingerprint (144 bytes from sectors 16 and 22, fed to the existing pops_builtin_lookup), pops_physical_disc_clear_name (memset 0x4f8000, 0x80).
- tools/trace_original_pops_physical.py (Unicorn harness: block 0x8766fc..0x876a40, module scan, fingerprint function, all later flag readers, the VCD probes of launch types 0, 1/2 and 3) and tools/test_pops_physical_disc.py (40 tests: Native 17, RealCore 4, Original 14, Source 5), wired into .github/workflows/build.yml; the C file is listed once in launcher/CMakeLists.txt.
- docs/POPSTARTER_PHYSICAL_DISC.md: the measured behaviour, addresses, what launcHER has, what is not done, what needs a console, evidence table.

NOTHING IS WIRED. No file under launcher/src, launcher/include, common/src or common/include other than the new pair mentions pops_physical_disc (pinned by a Source test). launchPOPS still returns -ENOENT at "Cannot open target VCD" (handler_pops.c:888-891) exactly as at d31d4a7. I changed no line of launcher/src/main.c, launcher/src/init.c, common/src/launch_args.c, launcher/src/handler_pops.c, the resident sources, or any of the docs I was told not to edit, so there are no hunks to list there and non-POPS launches run none of the new code. The "ata0:/LAUNCHER-TEST-20261013-A/" entry is untouched (pinned by a Source test).

Main measured facts (emulated): the flag gp+0x3410 (0x9b9d00) is set to 1 only by a failed VCD probe; the block runs only with flag == 1 and the "VCD found" local == 0; it scans for a module named cdvd_*, else loads rom0:CDVDMAN and rom0:CDVDFSV (results unchecked); sceCdInit(1), sceCdSync(0), sceCdStatus(); status == 1 is fatal ("Cannot access (%d)!", type never asked, no unmount, no retry); sceCdGetDiskType() must be 0x10..0x13 else "NO PS1 CDROM!" fatal; one sector read at LBA 4 gives the region letters from bytes 60..63 (a failed read is not an error: four zero letters); writes 0x200794=0x0000202d, for types 0x11/0x13 the three $MUTE_CDDA writes, and in its own always-live block 0x2328bc=0x0000202d, 0x2328c8=0x1000001f, 0x2328cc=0, 0x2328d0..0x232943 zeroed; then the built-in list from sectors 16 and 22 when the list level is 1..4. Later readers: sceCdInit(5) at 0x8774c4/0x8774d4, banner (no partition/VCD lines, memset 0x4f8000), DISCS.TXT reader prints three lines and opens nothing, fingerprint reads the drive instead of the VCD.

All 28 tools/test_*.py pass both without and with the reference inputs (per-file outcomes in tests_run). EE: the new C file compiles with the EE gcc as an object only; the launcher ELF was not built or linked.

## commits

1. 1f8c525 feat(pops): physical PS1 disc planner, core stage and fingerprint (host part)

## files changed

1. common/include/pops_physical_disc.h (new, 136 lines)
2. common/src/pops_physical_disc.c (new, 143 lines)
3. tools/trace_original_pops_physical.py (new, 585 lines)
4. tools/test_pops_physical_disc.py (new, 918 lines)
5. docs/POPSTARTER_PHYSICAL_DISC.md (new, 251 lines)
6. launcher/CMakeLists.txt (+1 line: ../common/src/pops_physical_disc.c after ../common/src/pops_igr_skin.c in EE_SOURCES)
7. .github/workflows/build.yml (+2 lines: step 'Test POPS physical PS1 disc planner, core stage and fingerprint' running python tools/test_pops_physical_disc.py, after the IGR skin step)

## measured evidence

1. All items below are EMULATED (Unicorn 2.1.4, original MAIN at 0x870000 with gp 0x9b68f0, Sony POPS core at 0x200000, natives modelled by address, memory diffed after each run, no live write hook) or host ctypes runs. None is a console result.
2. Block 0x8766fc..0x876a40, every disc type 0..255 plus 6 wide values with status 0: 262 cases; call sequence, printed text, region letters, the whole POPS core and all other memory compared with the planner + stage. Result: match. Only 0x10, 0x11, 0x12, 0x13 reach POPS; 0x110 is refused (full-word compare).
3. Block, every drive status 0..255 plus 0x101, 0x10001, 0x80000001, 0xFFFFFFFF (type 0x10 for all; types 0x13 and 0x14 as well for status 0..7): 276 status/type pairs. Result: match. Only status exactly 1 is fatal; status 0x101 passes.
4. Block, 400 seeded cases mixing status, type, sector 4 content, read result, module list, quiet flag, launch type, mass flag, list level and the unchecked call results: 192 reach POPS, 208 fatal. Result: match.
5. Block, every combination of the unchecked results (SifLoadModule, sceCdInit, sceCdDiskReady, sceCdRead): 48 cases. Result: POPS is reached every time; a failed sector 4 read leaves four zero letters.
6. Block entry condition: 6 flag/found pairs. Result: runs only with flag == 1 and found == 0; otherwise no call and no write.
7. Module scan FUN_00870150: 7 module lists. Result: first name starting 'cdvd_' sets 0x9ae914 = 1 and stops; no such module loads rom0:CDVDMAN then rom0:CDVDFSV with (0, 0) arguments.
8. Fatal exits and the pfs unmount helper 0x8d7ff8: 20 cases (launch type 0..4 x mass flag 0/1 x both fatal reasons). Result: the status-1 path never unmounts; the wrong-type path calls the helper only when gp+0x3448 == 0 and the launch type is not 3 or 4. The helper itself was read, not run.
9. Region letters end to end: 6 cases (Euro, Amer, 'of A', Inc., an unknown text, a failed read). The block's letters fed to the original's region window write the same bytes as pops_region_from_licence + pops_apply_region from the planner's letters. Result: match.
10. Built-in list fingerprint FUN_008ff0e4 from sectors: all 607 stored fingerprints planted in otherwise random sectors 16/22. Result: the 144 bytes the original compares equal pops_physical_disc_fingerprint's output, the original dispatches the same entry, and pops_builtin_lookup names the same entry, 607 of 607.
11. Fingerprint from a VCD (flag 0): 204 of the stored fingerprints, through both of the original's file backends. Result: same entry; offsets 0x109340 (0x30 bytes), 0x109640 (0x20), 0x10ca70 (0x40) are sector 16 bytes 40..87 and 808..839 and sector 22 bytes 56..119.
12. Fingerprint for unknown and unread discs: 40 cases. Result: ' Unknown', no entry; a failed read compares zeros; with the flag at 2 nothing is read.
13. Later readers of gp+0x3410 (all eight load sites found by a gp-relative scan of MAIN: 0x8766fc, 0x8774c4, 0x878ab4, 0x878c78, 0x8d5d24, 0x8d5d90, 0x8ff12c, 0x8ff24c): 4 runs of 0x8774c4, 6 of the banner, 8 of the DISCS.TXT reader. Result: flag 1 gives sceCdInit(5); the banner omits the partition and VCD lines and does memset(0x4f8000, 0, 0x80); the DISCS.TXT reader prints three lines and opens nothing.
14. VCD probes that set the flag: 10 runs (types 1/2: 3, type 0: 4, type 3: 3). Result: type 0 mounts hdd0:__.POPS then hdd0:__.POPS0..9 (11 mounts, argv[0] overwritten, left at hdd0:__.POPS9 when none has the VCD); types 1/2 mount the partition argv[0] names and open once; type 3 opens mass:/POPS/<name> then mass:/POPS0..9/<name> (11 opens, argv[0] overwritten with hdd0:PP.POPS-00001, last built path mass:/POPS9/<name>). A found VCD reads the 4 letters from offset 0x102514 and leaves the flag 0. The VCD path for types 0/1/2 was supplied by the test, not built by the original in these runs. Type 4 was not measured.
15. Always-live code words before the block's writes, asserted from the original's image: 0x2328bc = 0x34842950, 0x2328c8 = 0x3c1a0050, 0x2328cc = 0x241bfcee, 0x232948 = 0x10000061.
16. Real Sony core (host ctypes, needs POPS_TEST_ELF): after pops_core_patches_stage, each $FIX_* correction mask (0, 1, 2, 4, 8, 16, 31), the resident hooks and pops_apply_always_on_pokes, all four sites the stage guards still hold Sony's values and the stage succeeds for 0x10, 0x11, 0x12, 0x13. 0x4f8000..0x4f807f is zero on that staged core. This did not run launchPOPS itself or its later stages (config patches, fix files, BIOS edits).
17. Test sensitivity: a scratch copy with four deliberate mutations (licence offset 61, NULL-argument word 0x0000202c, sector 22 offset 57, type 0x14 accepted) gave FAILED (failures=21) of 40, in Native, RealCore and Original. That copy was taken a few minutes before the last small test edit (one extra type-0 probe case).

## tests run

1. **command:** python tools/test_pops_physical_disc.py (no reference inputs)  
   **outcome:** rc=0, Ran 40 tests, OK (skipped=18)
2. **command:** POPS_TEST_ELF=... POPSTARTER_TEST_ELF=... python tools/test_pops_physical_disc.py  
   **outcome:** rc=0, Ran 40 tests, OK, no skips. Printed: 262 disc types; 276 status/type pairs; 607 stored fingerprints from sectors, 204 from a VCD; 400 seeded cases (192 reach POPS, 208 fatal)
3. **command:** python tools/test_launch_args.py  
   **outcome:** without: rc=0, PASS line. with: rc=0, PASS line (script-style test, no unittest count)
4. **command:** python tools/test_network_transports.py  
   **outcome:** without: rc=0. with: rc=0 (script-style, PASS lines)
5. **command:** python tools/test_popfs.py  
   **outcome:** without: rc=0. with: rc=0 (script-style, PASS line)
6. **command:** python tools/test_pops_breakpoint.py  
   **outcome:** without: 11 tests OK (skipped=4). with: 11 OK
7. **command:** python tools/test_pops_builtin_db.py  
   **outcome:** without: 14 tests OK (skipped=14). with: 14 OK
8. **command:** python tools/test_pops_display.py  
   **outcome:** without: 21 tests OK (skipped=6). with: 21 OK
9. **command:** python tools/test_pops_external.py  
   **outcome:** without: 128 tests OK (skipped=14). with: 128 OK (skipped=3; that file also reads POPS_RESIDENT_BIN / POPS_TRAMPOLINE_BIN / POPS_EE_CC, which I did not set)
10. **command:** python tools/test_pops_fatfs.py  
   **outcome:** without: rc=0. with: rc=0 (script-style, PASS line)
11. **command:** python tools/test_pops_features.py  
   **outcome:** without: 29 tests OK (skipped=2). with: 29 OK
12. **command:** python tools/test_pops_fix_files.py  
   **outcome:** without: 31 tests OK (skipped=3). with: 31 OK
13. **command:** python tools/test_pops_igr_skin.py  
   **outcome:** without: 30 tests OK (skipped=16). with: 30 OK
14. **command:** python tools/test_pops_io_probe.py  
   **outcome:** without: 6 tests OK. with: 6 OK
15. **command:** python tools/test_pops_launch_hooks.py  
   **outcome:** without: 48 tests OK (skipped=14). with: 48 OK (skipped=3, inputs other than the two reference ELFs)
16. **command:** python tools/test_pops_modes.py  
   **outcome:** without: rc=0. with: rc=0 (script-style, PASS line)
17. **command:** python tools/test_pops_module_irx.py  
   **outcome:** without: 11 tests OK (skipped=4). with: 11 OK
18. **command:** python tools/test_pops_opcodes.py  
   **outcome:** without: 9 tests OK (skipped=3). with: 9 OK
19. **command:** python tools/test_pops_padman.py  
   **outcome:** without: 6 tests OK (skipped=3). with: 6 OK
20. **command:** python tools/test_pops_progressive.py  
   **outcome:** without: 8 tests OK (skipped=5). with: 8 OK (skipped=3, inputs other than the two reference ELFs)
21. **command:** python tools/test_pops_read_trace.py  
   **outcome:** without: 9 tests OK. with: 9 OK
22. **command:** python tools/test_pops_resident.py  
   **outcome:** without: 75 tests OK (skipped=12). with: 75 OK
23. **command:** python tools/test_pops_runtime_corrections.py  
   **outcome:** without: 8 tests OK. with: 8 OK
24. **command:** python tools/test_pops_startup_calls.py  
   **outcome:** without: 6 tests OK. with: 6 OK
25. **command:** python tools/test_pops_vmc.py  
   **outcome:** without: rc=0, PASS line. with: rc=0, PASS line
26. **command:** python tools/test_pops_warmboot.py  
   **outcome:** without: 7 tests OK (skipped=3). with: 7 OK
27. **command:** python tools/test_smap_ipconfig.py  
   **outcome:** without: rc=0, PASS line. with: rc=0, PASS line
28. **command:** python tools/test_sony_ioman_layout.py  
   **outcome:** without: rc=0, PASS line. with: rc=0, PASS line
29. **command:** python tools/test_subq_bridge.py  
   **outcome:** without: rc=0, PASS line. with: rc=0, PASS line
30. **command:** Full sweep of all 28 tools/test_*.py, once without and once with POPS_TEST_ELF/POPSTARTER_TEST_ELF, on the working tree that was then committed unchanged as 1f8c525 (TMP/TEMP/TMPDIR set, PYTHONDONTWRITEBYTECODE=1)  
   **outcome:** 56 runs, all rc=0; no log contains a Traceback or a line starting FAIL/ERROR. The two sweeps overlapped in time on a heavily loaded machine; wall times were 1 s to 345 s per file
31. **command:** python tools/test_pops_physical_disc.py in a scratch copy with four deliberate mutations, with reference inputs  
   **outcome:** FAILED (failures=21) of 40, as intended (the test notices each mutation)

## ee build check

Compiled exactly one file for EE: common/src/pops_physical_disc.c, with <ps2build>/toolchain/ee/bin/mips64r5900el-ps2-elf-gcc.exe (GCC 15.3.1 20260823). Commands and results: `-Os -G0 -Wall -Wextra -Werror -D_EE -I common/include -fsyntax-only common/src/pops_physical_disc.c` rc=0; the same flags with `-c` to an object in the scratch folder rc=0 (text 940, data 0, bss 0; defined: pops_physical_disc_plan, _message, _stage, _clear_name, _fingerprint; undefined: memcpy, memset, pops_apply_original_tokens). -Os -G0 -Wall are the launcher target's flags in launcher/CMakeLists.txt; -Wextra -Werror are stricter than the project uses. The header is covered through that compile. NOT built: the launcher ELF (no CMake configure, no link), so I did not confirm that the link resolves pops_apply_original_tokens from pops_modes_patches.c in the real build or how many bytes the ELF grows; launcher/CMakeLists.txt has no -ffunction-sections/--gc-sections, so I expect the roughly 940 bytes of uncalled code to be kept, but that is an expectation, not a measurement. No other common/src file was changed. Nothing was run on a PS2 or in a PS2 emulator.

## deviations from original

1. Nothing is called. The original falls back to the drive when no VCD is found; launcHER at 1f8c525 still fails such a launch with "Cannot open target VCD" / -ENOENT. This is the deliberate scope of this stage.
2. pops_physical_disc_stage checks that 0x200794 holds 0x03a0202d and (types 0x11/0x13) that 0x20f0b6, 0x20ebf2, 0x20f0e0 hold 0x02, 0x03, 0xae000014 before writing, and writes nothing otherwise (-EILSEQ). The original pokes through its helpers (0x87c298, 0x87c300) without looking. On Sony's core after launcHER's earlier host-testable stages the guard passes for all four types, so the bytes written are the same.
3. The original's four writes into its own always-live block (0x2328bc = 0x0000202d, 0x2328c8 = 0x1000001f, 0x2328cc = 0, memset 0x2328d0..0x232943) are not reproduced. launcHER has no such block; the equivalent is behaviour in the resident engine, which this track was told not to touch (see not_done).
4. The planner makes the decision only: it does not scan modules, load rom0:CDVDMAN/CDVDFSV, call libcdvd, print, honour the quiet flag (gp+0x38b0), unmount pfs or exit. The caller has to do those in the measured order; none of it exists.
5. The planner takes a NULL sector 4 pointer as four zero letters and records read_ok without acting on it. The original has no such notion: it zeroes its buffer, ignores sceCdRead's result and copies bytes 60..63 whatever happened. Equivalent only if the future caller zeroes the buffer before the read, as the header says. A failed read that leaves partial data in the buffer was not modelled.
6. pops_physical_disc_fingerprint takes a NULL sector as zeros for the same reason; the original reads into a zeroed buffer and ignores the result.
7. pops_physical_disc_clear_name writes 0x80 zero bytes at 0x4f8000 as the original's banner code does (0x878c88), but on launcHER's staged core that buffer is already zero in the host-tested stages, so it changes nothing there. Whether a later launchPOPS stage writes that buffer was not checked.
8. Region: for a physical disc the original always runs its region pass, with four zero letters after a failed read (writes the unknown-region values). launcHER's existing VCD path skips pops_apply_region when the licence cannot be read (handler_pops.c:1567, regionRead). Unchanged here; a physical launch must not copy that skip.
9. The original accepts disc types 0x12 and 0x13 (PS2 CD) as PS1 discs and refuses the SDK's still-detecting values 0x01..0x04 without waiting. The planner copies both on purpose (exact parity first).
10. Harness limits, not code deviations: every native is a model; the sceCdRead mode bytes 20 01 00 00 were read from the disassembly (0x870c20..0x870c34) and supplied by the harness; the probe windows were given their VCD path by the test for types 0/1/2; launch type 4 was not measured; the type-3 branch for a VCD found in mass:/POPSn/ (copies the folder name into an embedded module image at 0x91fb50) was seen but only its flag, path and letters are pinned; which flag-store site each probe case went through was not traced address by address; what POPS does after 0x210540 is called with NULL was not looked at.

## not done

1. No drive access anywhere: no scan for a cdvd_* module, no SifLoadModule of rom0:CDVDMAN / rom0:CDVDFSV, no sceCdInit(1)/sceCdSync/sceCdStatus/sceCdGetDiskType/sceCdDiskReady/sceCdRead of sectors 4, 16, 22, as the task required for this stage.
2. No launch path without a VCD. launchPOPS (handler_pops.c:813 onward) takes its paths, serial, fingerprint, region, memory-card folder, DISCS slots and popfs registration from the VCD file; the VCD-assuming line groups are listed in decisions_for_owner.
3. Resident, lid close (for the other track; I did not edit it): common/src/pops_resident_engine.c, pops_resident_hotkeys, lines 339-342: `mem->cd_init((const char *)cfg->disc_slot[cfg->disc_selected & (POPS_MAX_DISCS - 1)]);` must call cd_init(NULL) in physical mode. Original: 0x2328bc 0x34842950 (ori a0,a0,0x2950) -> 0x0000202d (daddu a0,zero,zero) in front of jal 0x210540 at 0x2328c0.
4. Resident, disc selections: same function, lines 344-351, the four `POPS_COMBO_DISC_1..4` tests must not run in physical mode. Original: 0x2328c8 0x3c1a0050 -> 0x1000001f (b 0x232948), 0x2328cc 0x241bfcee -> 0, memset(0x2328d0, 0, 0x74) over the four selections (0x2328d0..0x232943).
5. Resident: both need a physical-disc flag in PopsResidentConfig and a resident version bump; the lid-open hotkey stays as it is (the original does not change 0x2327f8..0x232880).
6. DISCS.TXT skip for a physical launch with the original's three lines ('    D-Pad button assignment (DISCS.TXT) skipped.', '    Emulating lid open/close with triangle/square.', '    Only for refreshing the physical PS1 CDROM TOC.'); original reader FUN_008d5cf8, flag tests at 0x8d5d24 and 0x8d5d90. launcHER's reader is inside pops_config_discover (handler_pops.c:992).
7. sceCdInit(5) (SCECdEXIT) before the IOP work when the flag is 1: original 0x8774c4 (test) / 0x8774d4 (call), just after FUN_008dc9ac.
8. The banner changes for a physical launch (no 'Game partition' / 'User VCD image' lines) and the call to pops_physical_disc_clear_name at the matching place (original 0x878ab4, 0x878c78, memset at 0x878c88).
9. Always running pops_apply_region with the planner's letters for a physical launch (handler_pops.c:1567 skips it today when the licence is unread).
10. POPS's own disc layer was not examined: what Sony's 0x210540 does with a NULL name, what launcHER's core patches (which point POPS at its popfs device) do to that path, and whether POPS's IOP image has a usable cdvdman after launcHER's IOP reset / IOPRP. Until that is looked at there is no evidence a launcHER-staged POPS can read a real disc at all.
11. Launch type 4, how the original builds the VCD path (gp+0x3470) before the probes, and where the original looks for per-game files (VMCs, 'Game resource dir') after every probe has failed were not measured. Known from the runs: type 0 leaves argv[0] at hdd0:__.POPS9 and type 3 leaves the last built path at mass:/POPS9/<name>, which may decide those folders.
12. No lookup-folder function was added, because nothing in this stage changes where any file is looked up. The function I propose for the lead is described in decisions_for_owner.
13. No full launcher ELF build or link, no PS2 emulator run, no console run. docs/POPSTARTER_R13_INVENTORY.md, docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md, README.md and docs/pops-setup.html were not edited; text for them is in doc_updates.

## decisions for owner

1. How a physical-disc launch is requested. In the original nobody requests it: any launch whose VCD probes all fail continues with the drive (emulated: type 0 = HDD by ELF name, 11 partitions hdd0:__.POPS, __.POPS0..9; types 1/2 = the partition in argv[0], one open; type 3 = XX./SB., mass:/POPS/<name> then mass:/POPS0..9/<name>; type 4 not measured). So with the original a mistyped or missing VCD spins up the drive and ends in 'NO PS1 CDROM!' or 'Cannot access'. Decide: (a) exact parity, automatic fallback for POPStarter-style launches, or (b) an explicit request (a target name or flag) with the automatic fallback left out or added later.
2. Recommendation for the smallest change that gives a renamed-ELF drop-in the original's behaviour (option a): one new entry point in launcher/src/handler_pops.c, for example `int launchPOPSPhysical(const char *namePath, int argc, char *argv[])`, called from exactly one place per candidate loop, immediately before the existing failure: launcher/src/main.c line 99 (`fail("Failed to launch %s: %d", origArg, -ENOENT)` after the loop at 89-98) and the three loops in launcher/src/handler_quickboot.c (around lines 214, 235, 276). Gate it so only POPStarter-style launches reach it: the XX./SB. flags main.c already sets at lines 71-74, or a PP./__. target, or the renamed-ELF self-launch that launcher_normalize_args produces (I did not trace that function; the lead must pick the exact predicate), AND every candidate having failed at the VCD existence check (launchPOPS would need to report that case distinctly from other -ENOENT results; today they are indistinguishable). Pass candidates[0] as namePath so the title, folder, gameConfigDir and memory-card names are the ones a VCD launch of the same name would have used. With that gate a non-POPS target reaches no new code, and the only launches whose outcome changes are ones that fail today. This needs a test that main.c behaves byte-for-byte as before for non-POPS targets; I wrote none because I changed nothing there.
3. Proposed single lookup function (not implemented; for routing the other tracks' readers: BIOS.BIN/OSD.BIN, TROJAN, CHEATS/VMCDIR, IGR skin, fix files): move handler_pops.c lines 935-950 (vcdDir / gameBase / gameConfigDir from the VCD path) into one function, e.g. `static void pops_launch_dirs(const char *namePath, char *vcdDir, char *gameBase, char *gameConfigDir)`, taking the VCD path for a VCD launch and candidates[0] for a physical launch. Every reader that uses vcdDir or gameConfigDir then needs no change. Caveat: where the original itself looks after failed probes was not measured (type 0 ends on hdd0:__.POPS9, type 3 on mass:/POPS9/), so exact folder parity for a physical launch is an open measurement.
4. launchPOPS lines that assume a VCD exists (handler_pops.c at d31d4a7 = 1f8c525, grouped). Target identity: isPopsTarget 51-57 (requires '.vcd'; reached from launcher/src/common.c:622-623); 819-862 argv[0] treated as the VCD path; 887-891 existence check and -ENOENT. Files next to the VCD: 894-904 findPopsDependenciesForMode(vcdPath,...); 935-950 vcdDir/gameBase/gameConfigDir; 992 pops_config_discover (includes DISCS.TXT); 1469 pops_stage_igr_skin(vcdDir); 1525 fix files (vcdDir, gameConfigDir). Content read from the VCD: 921-933 pops_vcd_inspect_path; 959-981 built-in fingerprint from the VCD; 1044-1073 compatibility DB / serial heuristics; 1075-1095 region licence read; 1567 `regionRead ? pops_apply_region(...) : 0`. Memory cards: 1097-1216 VMC paths derived from the VCD. Disc slots and popfs: 1218-1258 DISCS slots, discArgs[0] = vcdPath, popfs proxy arguments. Handing the image to POPS: 1684-1686 and 1874 trampoline name 'pops0:IMAGE.VCD'; 1703-1709 and 1834-1840 APA remount by argv[0]; 1755 initPopsServices; 1789/1805/1819 module loaders; 1842-1858 pvdSample + pops_probe_live_storage. A physical launch needs a replacement or a skip for each group; the stage belongs after pops_apply_always_on_pokes (1459) and before pops_stage_igr_skin (1469).
5. Existing overlap to be aware of: OSDM builds already have a `cdrom` target (launcher/src/main.c:49-50, launcher/src/handler_cdrom.c, options ps1fast/ps1smooth/ps1vneg) that starts a PS1 disc through the console's own PS1 driver. That is a different mechanism from POPStarter's fallback (which runs the disc under POPS). I did not read that handler beyond its option names. Decide whether POPS-from-disc is wanted at all given that path exists.
6. Before any wiring, decide whether to spend console time on the open question in not_done: whether a launcHER-staged POPS (popfs core patches, launcHER's IOP image) can read a real disc after 0x210540 is called with NULL. If it cannot, the whole feature needs more than the measured block.
7. Parity choices to confirm when wiring (all copied in the planner today): PS2-format CD types 0x12/0x13 accepted; still-detecting types 0x01..0x04 and tray-open status 1 are immediately fatal with no wait or retry; CD-DA muted for types 0x11/0x13 with no way to keep it; a failed sector 4 read silently gives the unknown-region writes; fatal messages hidden when quiet. Each has a quirk entry in doc_updates.
8. Memory-card naming for a physical launch: launcHER derives VMC paths from the VCD (1097-1216); with no VCD the name has to come from the launch name (candidates[0]) to stay a drop-in. What the original does there was not measured.

## doc updates


### inventory rows

docs/POPSTARTER_R13_INVENTORY.md line 203, replace the whole row with:

| Physical PS1 disc. Not a mode anyone selects: it is what the original does when every VCD probe fails (`gp+0x3410` = 1; set at `0x8756a4`, `0x875734`, `0x875d98`, `0x876690`). Probes: type 0 mounts `hdd0:__.POPS` then `hdd0:__.POPS0..9` (11 mounts), types 1/2 the partition `argv[0]` names (one open), type 3 opens `mass:/POPS/<name>` then `mass:/POPS0..9/<name>` (11 opens); type 4 not measured. Block `0x8766fc..0x876a40`, entered only with the flag at 1 and no VCD found: scan for a `cdvd_*` module, else `rom0:CDVDMAN` + `rom0:CDVDFSV` (results unchecked); `sceCdInit(1)`; drive status 1 is fatal (`Cannot access (%d)!`, no retry); disc type must be `0x10..0x13` (`NO PS1 CDROM!`); region letters are sector 4 bytes 60..63 and a failed read gives four zero letters, not an error; `0x200794=0x0000202d`; `$MUTE_CDDA` writes for types `0x11`/`0x13`; in its own always-live block `0x2328bc=0x0000202d`, `0x2328c8=0x1000001f`, `0x2328cc=0`, `0x2328d0..0x232943` zeroed; then the built-in list from sectors 16 and 22. Later: `sceCdInit(5)` at `0x8774d4`, banner without the partition/VCD lines plus `memset(0x4f8000,0,0x80)`, `DISCS.TXT` skipped with three lines (`2x`: the audit's run and `tools/trace_original_pops_physical.py`, natives modelled; 262 disc types, 276 status/type pairs, 400 seeded cases, 607 fingerprints, see `docs/POPSTARTER_PHYSICAL_DISC.md`. In-game reads are Sony's IOPCD, `1x`/`inferred`) | **PARTIAL, host part only, nothing wired**: `common/src/pops_physical_disc.c` has the planner (`pops_physical_disc_plan`), the guarded core stage (`pops_physical_disc_stage`: `0x200794` and the `$MUTE_CDDA` sites, refuses unless they hold Sony's bytes), the fingerprint builder (`pops_physical_disc_fingerprint`) and `pops_physical_disc_clear_name`, compared with the original by `tools/test_pops_physical_disc.py`. Nothing calls them: no module load, no libcdvd call, no sector read, and `launchPOPS` still returns `-ENOENT` at "Cannot open target VCD" (`handler_pops.c:888-891`). Missing: the drive part, a launch path without a VCD, the resident changes (lid close with NULL, the four disc selections off), the `DISCS.TXT` skip, `sceCdInit(5)`. Needs the owner's decision on how a physical launch is requested. Not tested on a console |

Line 184 (launch type row), append to the first cell: "Run under emulation on 2026-11-11 (`tools/trace_original_pops_physical.py`, mount/open modelled, VCD path supplied by the test for types 0/1/2): type 0 tries `hdd0:__.POPS` and then `hdd0:__.POPS0` .. `hdd0:__.POPS9`, writing each name over `argv[0]`; type 3 tries `mass:/POPS/<name>` and then `mass:/POPS0/<name>` .. `mass:/POPS9/<name>` with `<name>` read from POPS `0x4f8003`, and overwrites `argv[0]` with `hdd0:PP.POPS-00001`. Type 4 and the classifier `FUN_008d8db8` itself were not run."

Lines 247-248 (item j), replace with: "(j) Physical disc fallback: planner, guarded core stage and fingerprint builder done on a host (`common/src/pops_physical_disc.c`, not wired). Still open: the drive part, the launch path without a VCD and the resident changes, all untested on a console."

### quirks

New section for docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md (numbers left for the lead). Note above the table: these are copied in the planner and core stage of `common/src/pops_physical_disc.c`, which nothing calls yet; measured under emulation with modelled drive calls (`tools/trace_original_pops_physical.py`, `tools/test_pops_physical_disc.py`), not on a console.

## Physical PS1 disc (docs/POPSTARTER_PHYSICAL_DISC.md)

| # | POPStarter behaviour (copied) | Possible fix later |
|---|---|---|
| | A physical disc is never requested: any launch whose VCD probes all fail goes to the drive, so a missing or misnamed VCD ends in `NO PS1 CDROM!` or `Cannot access (%d)!` instead of a file-not-found message. (Not copied yet: launcHER has no fallback.) | Say which VCD was not found; make the disc an explicit choice. |
| | Disc types `0x12` and `0x13` (PS2 CD, PS2 CD with CD-DA in the SDK headers) are accepted as PS1 discs along with `0x10` and `0x11`. | Accept only `0x10`/`0x11`. |
| | The SDK's still-detecting types `0x01..0x04` are refused at once as `NO PS1 CDROM!`; drive status 1 (tray open) is fatal at once as `Cannot access (%d)!`. There is no wait and no retry. | Wait for detection to finish; ask for the tray to be closed. |
| | Both compares use the whole 32-bit value: status `0x101` passes, type `0x110` is refused. | Nothing to fix unless the drive can return such values. |
| | The results of `SifLoadModule` (`rom0:CDVDMAN`, `rom0:CDVDFSV`), `sceCdInit`, `sceCdDiskReady` and `sceCdRead` are never looked at. | Check them and report. |
| | A failed read of sector 4 is not an error: the region letters are four zero bytes and the region pass writes its unknown-region values. | Retry, then report the read error. |
| | A failed read of sector 16 or 22 leaves zeros in that part of the 144-byte fingerprint; the disc is then `Unknown` to the built-in list, with no message about the read. | Retry; say the disc could not be identified. |
| | For types `0x11` and `0x13` CD audio is always muted (the three `$MUTE_CDDA` writes); no command keeps it. | Honour `$UNDO_MUTE_CDDA`, or decide from what POPS can play from a disc. |
| | `DISCS.TXT` is skipped with three lines of text; SELECT+L2+R2+SQUARE only calls POPS's disc start-up again with NULL, and the four D-pad disc selections are removed. | Keep as is, or support a swap to a VCD. |
| | With the quiet flag set (`gp+0x38b0` = 1) the two fatal messages are not printed either. | Always show fatal messages. |
| | The status-1 exit does not unmount `pfs0:`/`pfs1:`; the wrong-type exit does (unless launch type 3/4 or the mass flag). | Unmount on both. |
| | The module-scan result word (`0x9ae914`) is set and never cleared. | None needed in launcHER (no such word). |

Not a copied quirk but worth recording next to them: launcHER's `pops_physical_disc_stage` is stricter than the original. It writes only when every site holds Sony's bytes and returns `-EILSEQ` otherwise; the original pokes without looking.

### user facing

README.md / docs/pops-setup.html, one note where POPStarter differences are listed: "Physical PS1 discs: POPStarter r13 falls back to the disc drive when it cannot find the VCD. launcHER does not do this yet. A launch whose VCD is missing fails with 'Cannot open target VCD'. The parts of the fallback that need no drive (the decision logic, the POPS changes and the disc fingerprint) exist and are host-tested against the original, but nothing reads the drive and none of it has been tested on a console." No other user-facing behaviour changed in this commit.

### hardware checklist

For a console session, once a drive part exists (none of this has been run):
1. Right after sceCdInit(1) + sceCdSync(0): the values sceCdStatus() and sceCdGetDiskType() return for a PS1 data disc, a PS1 disc with CD-DA tracks, a PS2 CD, a PS2 DVD, an audio CD, no disc, tray open, and a disc inserted seconds before launch (is the type still 0x01..0x04 'detecting' at that moment?).
2. Whether rom0:CDVDMAN / rom0:CDVDFSV load, and what happens when cdvd modules are already loaded under another name (the original only looks for names starting 'cdvd_').
3. sceCdRead of LBA 4, 16 and 22 with mode bytes 20 01 00 00: return values, and that sector 4 bytes 60..63 are the licence letters on real discs of each region.
4. That the 144 bytes from sectors 16 and 22 of a real listed disc select the same built-in entry as its VCD.
5. Whether POPS boots from the disc at all after 0x200794 = 0x0000202d: what 0x210540 does with NULL under launcHER's core patches and IOP image, and whether cdvdman is usable after the IOP reset.
6. In-game reads, FMV and loading on a real disc.
7. CD-DA with and without the three $MUTE_CDDA writes on a type 0x11 disc.
8. The lid hotkeys with a real tray: SELECT+L2+R2+TRIANGLE then a real disc change then SELECT+L2+R2+SQUARE (the original's text says this refreshes the TOC).
9. sceCdInit(5) before the IOP work: effect on the drive and on the later POPS start.
10. Both fatal paths end as the original's do (message, exit), with quiet on and off.
