# CHEATS.TXT / $USBDELAY / VMCDIR.TXT: author's report

Written by the track's author when the stage ended. Copied as written; not re-verified.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## summary

Three local commits on pr23/cfg in the cfg worktree (nothing pushed, no PR touched, no console or rig used). (1) b205a3e: launcHER's CHEATS.TXT line parser is replaced by the original's byte-stream command pass (pops_config_parse_text, table pops_commands[] in the original's handler order); under emulation of POPStarter's own pass (0x883aa8..0x89e884) it reports the same commands at the same offsets, the same stepped-over cheat codes and the same X/Y, compatibility-mode and game-id values on 120 fixed and 1500 seeded random texts. (2) b29464b: $USBDELAY_n is parsed as the original does (one digit + terminator, byte at 0x100017); launcHER's use of the value (EE sleep) and the default (0, no added delay) are unchanged; the original's DLAY/PFS-wrapper effect is documented as a console-gated follow-up. (3) 66efcbe: VMCDIR.TXT is read as FUN_008d4f84 reads it (ignore instead of abort, no trimming, a trailing line end makes the file ignored, empty file = POPS folder), 39 fixed + 400 random files match under emulation. Item 4 is report-only (decisions_for_owner); the ata0:/LAUNCHER-TEST-20261013-A/ entry was not removed. All 27 tools/test_*.py pass both without and with the reference inputs at HEAD 66efcbe. Everything is host or Unicorn emulation of single routines on synthetic input: NOT TESTED on a console.

## commits

1. b205a3e fix(pops): recognise CHEATS.TXT commands as POPStarter does
2. b29464b fix(pops): parse $USBDELAY_n as POPStarter does
3. 66efcbe fix(pops): read VMCDIR.TXT as POPStarter does

## files changed

1. common/src/pops_config.c
2. common/include/pops_config.h
3. launcher/src/handler_pops.c (commit 3 only: VMC folder taken from cfg.vmc_dir_set; empty name = POPS folder)
4. tools/trace_original_pops_config_text.py (new: runs the original's command pass and VMCDIR reader under Unicorn; its vmcdir() function landed in commit 1 although only commit 3 uses it)
5. tools/test_pops_config_text.py (new: Native / Source / Original classes)
6. tools/test_pops_features.py (ctypes mirror: usb_delay_set, vmc_dir_set appended; pinned expectations changed on purpose: $XPOS_-15, the over-long line, VMCDIR cases)
7. tools/test_pops_resident.py (pinned safe-mode order changed on purpose)
8. tools/test_pops_display.py (pinned malformed $XPOS_/$YPOS_ changed on purpose)
9. tools/test_pops_warmboot.py (four former 'known differences' now asserted equal to the original)
10. tools/test_pops_builtin_db.py (five former 'known differences' now asserted equal to the original)
11. .github/workflows/build.yml (one step added: python tools/test_pops_config_text.py)
12. docs/POPSTARTER_CONFIG_TEXT.md (new: addresses, mapping, quirks, evidence counts)

## measured evidence

1. EMULATED (Unicorn, original MAIN decoded at 0x870000, the command pass 0x883aa8..0x89e884 on synthetic text) vs HOST (launcHER pops_config_parse_text via ctypes): 120 fixed texts: same commands at the same offsets, same cheat-code columns stepped over, same X/Y values copied to POPS, same compatibility modes, same game id, same byte at 0x100017. Result: all match.
2. Same comparison on 1500 seeded random texts (seed 0x13C0): all match; 2876 commands, 399 cheat codes stepped over; 96 texts also contained a launcHER-only MODE token (there launcHER has more compat modes than the original, by design, and the test only requires the original's modes to be a subset); 20 texts wrote 0x100017.
3. Handler table: the 66 handler names and their order read from the original image equal launcHER's pops_commands[] (66 rows after commit 2; 65 after commit 1, where $USBDELAY_ was still filtered out of the comparison).
4. Shared number temporary (fp+0x90): 5 texts x 6 injected starting values (0, 1, 15, 255, 65535, 65536) = 30 runs, emulated vs host: all match. The starting value was INJECTED into the emulated frame; that the game's own CHEATS.TXT starts at strlen(name)+1 comes from reading the code (0x883430 stores strlen(a1); 0x874ddc..0x8750e4 builds a1 as the name plus '/'), not from an end-to-end run.
5. FUN_008dc2c4 (compatibility modes) under emulation: 21 modes x 2 states (with/without $SUBCDSTATUS): pokes only for 1..7, and only 4, 6, 7 after $SUBCDSTATUS; launcHER's add_compat_mode agrees.
6. $USBDELAY_n, emulated byte at 0x100017 (preset to 0xEE) vs launcHER usb_delay/usb_delay_set: 20 fixed texts and 300 seeded random $USBDELAY texts (seed 0x100017; 84 wrote the byte): all match. E.g. $USBDELAY_5 -> 5, $USBDELAY_0 -> 0, $USBDELAY_12 / $USBDELAY_05 / $USBDELAY5 / $USBDELAY_5<TAB> -> byte untouched; the handler leaves the shared number alone ($USBDELAY_7 $XPOS_Q writes X=0).
7. $USBDELAY consumer: READ FROM THE DISASSEMBLY, NOT RUN: main 0x879cf0..0x879e58 patches the 'DLAY' word (one occurrence, image 0x91fb30, module address 0x420) of the embedded module at 0x91f680 (0xa45 bytes, 'PFS Wrapper r6a') with the byte only when gp+0x3448 != 0; 0x87c030..0x87c054 starts that module only when gp+0x3448 == 1; the only stores of 1 to gp+0x3448 are at 0x871618 (launch name starts SB./sb.) and 0x8719a4 (XX./xx.). Module code at 0: WaitSema; if word 0x540 != 0: v = word 0x420, 5 if still 'DLAY'; DelayThread(v*1000000); clear 0x540; SignalSema. File offset 0x417 (= 0x100017) is 0x01 in the four profile ELFs inspected (MAIN, DEBUG, USBDELAY, USBDELAY_DEBUG).
8. VMCDIR.TXT, EMULATED FUN_008d4f84 (USB-launch flags gp+0x3448=1, gp+0x3868=1, file services answered from synthetic bytes) vs HOST pops_config_parse_vmcdir: 39 fixed files (30 of them also run as the game's own file, a0=1, path mass:/POPS/Game Name/VMCDIR.TXT) and 400 seeded random files (seed 0x8D4F84; 212 used, 188 ignored): used/ignored and the folder name all match. Missing file: returns 0, nothing changed. Scratch run (not in the test suite): gp+0x3414 = 0, 1, 2, 3 gave identical results on 8 files each.
9. Static scan of the original image (literal byte stores in 0x870000..0x91f000 plus contiguous strings): the only .TXT names built are CHEATS.TXT, VMCDIR.TXT and DISCS.TXT; no PATCHES.TXT, MODES.TXT or NOBOOT anywhere; the CHEATS reader's path literals are 'pfs1', 'mass:/POPS/', '/CHEATS.TXT' (no mc0:/mc1: path). Static only.
10. Item 4, same text in both (emulated original pass vs host launcHER, scratch script, 13 texts): 'Infinite Lives Player 1' -> launcHER compat mode 1, original nothing; 'Level 8 unlocked' and '$MODE 8' -> launcHER mode bit 0x80 (pops_fix_plan then returns -ENOTSUP: read in the source, launch not run), original nothing; 'MODE 3', '2', $NOBOOT, $BIOS, $DITHER_OFF, $FIX_ALL, $PAL2NTSC, $NTSC2PAL, $FASTMIPS -> launcHER sets its field, original takes no command and makes no poke.

## tests run

1. **command:** python tools/test_launch_args.py  
   **outcome:** without inputs: exit 0 PASS; with inputs: exit 0 PASS
2. **command:** python tools/test_network_transports.py  
   **outcome:** without: exit 0 PASS; with: exit 0 PASS
3. **command:** python tools/test_popfs.py  
   **outcome:** without: exit 0 PASS; with: exit 0 PASS
4. **command:** python tools/test_pops_breakpoint.py  
   **outcome:** without: Ran 11 OK (skipped=4); with: Ran 11 OK
5. **command:** python tools/test_pops_builtin_db.py  
   **outcome:** without: Ran 14 OK (skipped=14); with: Ran 14 OK
6. **command:** python tools/test_pops_config_text.py  
   **outcome:** without: Ran 23 OK (skipped=10); with: Ran 23 OK (prints: 120 fixed texts match the table; 1500 random texts match (2876 commands, 399 cheat codes; 96 with a launcHER-only MODE token; 0x100017 written in 20); 30 texts x starting numbers match; $USBDELAY_n 20 texts + 300 random (84 written) match; VMCDIR 39 files match (30 also as the game's own), 400 random files match (212 taken, 188 ignored); FUN_008dc2c4 21 modes x 2 states match)
7. **command:** python tools/test_pops_display.py  
   **outcome:** without: Ran 21 OK (skipped=6); with: Ran 21 OK
8. **command:** python tools/test_pops_external.py  
   **outcome:** without: Ran 128 OK (skipped=14); with: Ran 128 OK (skipped=3)
9. **command:** python tools/test_pops_fatfs.py  
   **outcome:** without: exit 0 PASS; with: exit 0 PASS
10. **command:** python tools/test_pops_features.py  
   **outcome:** without: Ran 29 OK (skipped=2); with: Ran 29 OK
11. **command:** python tools/test_pops_fix_files.py  
   **outcome:** without: Ran 31 OK (skipped=3); with: Ran 31 OK
12. **command:** python tools/test_pops_io_probe.py  
   **outcome:** without: Ran 6 OK; with: Ran 6 OK
13. **command:** python tools/test_pops_launch_hooks.py  
   **outcome:** without: Ran 46 OK (skipped=13); with: Ran 46 OK (skipped=3). No pinned launch-order line was changed.
14. **command:** python tools/test_pops_modes.py  
   **outcome:** without: exit 0 PASS; with: exit 0 PASS
15. **command:** python tools/test_pops_module_irx.py  
   **outcome:** without: Ran 11 OK (skipped=4); with: Ran 11 OK
16. **command:** python tools/test_pops_opcodes.py  
   **outcome:** without: Ran 9 OK (skipped=3); with: Ran 9 OK
17. **command:** python tools/test_pops_padman.py  
   **outcome:** without: Ran 6 OK (skipped=3); with: Ran 6 OK
18. **command:** python tools/test_pops_progressive.py  
   **outcome:** without: Ran 8 OK (skipped=5); with: Ran 8 OK (skipped=3)
19. **command:** python tools/test_pops_read_trace.py  
   **outcome:** without: Ran 9 OK; with: Ran 9 OK
20. **command:** python tools/test_pops_resident.py  
   **outcome:** without: Ran 75 OK (skipped=12); with: Ran 75 OK
21. **command:** python tools/test_pops_runtime_corrections.py  
   **outcome:** without: Ran 8 OK; with: Ran 8 OK
22. **command:** python tools/test_pops_startup_calls.py  
   **outcome:** without: Ran 6 OK; with: Ran 6 OK
23. **command:** python tools/test_pops_vmc.py  
   **outcome:** without: exit 0 PASS; with: exit 0 PASS
24. **command:** python tools/test_pops_warmboot.py  
   **outcome:** without: Ran 7 OK (skipped=3); with: Ran 7 OK
25. **command:** python tools/test_smap_ipconfig.py  
   **outcome:** without: exit 0 PASS; with: exit 0 PASS
26. **command:** python tools/test_sony_ioman_layout.py  
   **outcome:** without: exit 0 PASS; with: exit 0 PASS
27. **command:** python tools/test_subq_bridge.py  
   **outcome:** without: exit 0 PASS; with: exit 0 PASS
28. **command:** Full list (all 27 tools/test_*.py) run once without and once with POPS_TEST_ELF/POPSTARTER_TEST_ELF at HEAD 66efcbe, sequentially, via a scratch runner  
   **outcome:** 27/27 exit 0 without inputs; 27/27 exit 0 with inputs. Earlier in the work, with-input runs found three pinned differences that the new reader removed (test_pops_config_text MODE regex, test_pops_warmboot, test_pops_builtin_db); those tests were updated deliberately in commit 1.

## ee build check

Compiler: <ps2build>/toolchain/ee/bin/mips64r5900el-ps2-elf-gcc.exe (GCC) 15.3.1 20260823, at HEAD 66efcbe. (a) common/src/pops_config.c (the only changed common/src file): compiled to an object in the scratch directory with `-c -Wall -Wextra -O2 -G0 -Icommon/include`: exit 0, no diagnostics (also done after commits 1 and 2). (b) launcher/src/handler_pops.c: `-fsyntax-only -Wall -O2 -G0 -D_EE` with the project include dirs and a hand-picked set of ps2build package include dirs (kernel, cglue, common, filexio, sifcmd, debug, iopreboot, mc, pad, hdd, elf-loader2, patches, eesync, startup): exit 0, no diagnostics. This is NOT the project's CMake configuration. NOT built: no CMake build, no link, no launcher ELF, no IRX, nothing run on EE hardware or in a PS2 emulator.

## deviations from original

1. launcHER-only tokens are still read from the same files and change the result where the original takes nothing: $NOBOOT, $BIOS, 'MODE n', '$MODE n', '$MODEn', a bare digit 1..8 as its own white-space token, $DITHER_OFF/$NODITHER, $FASTMIPS/$SLOWMIPS, $PAL2NTSC/$FORCENTSC/$NTSC2PAL, $FIX_*, $CORE_FIXES/$PSXCORE_FIXES. They keep launcHER's old line rules (white-space tokens, '#'/';' comments). Kept on purpose pending the owner's decision (item 4).
2. launcHER also reads PATCHES.TXT and MODES.TXT (POPS folder and game folder) and CHEATS.TXT/PATCHES.TXT/MODES.TXT in mc0:/POPSTARTER/, mc1:/POPSTARTER/, mc0:/POPS/, mc1:/POPS/ with the same reader; the original builds only CHEATS.TXT, VMCDIR.TXT and DISCS.TXT names and has no mc: path for them (static scan). Unchanged, item 4.
3. One cheat list and one safe-mode state for all files: the original's $SAFEMODE/$SAFEMODE2 'first one wins' flags (fp+0xec/0xf0) are per file and each file's codes are compiled with that file's gate; launcHER's cfg->safe_mode persists across files. A global file with $SAFEMODE and a game file with $SAFEMODE2 can differ.
4. The cheat codes themselves are still collected by launcHER's earlier scan_cheats, which stops at a NUL byte and steps over $C0 codes; the original's code passes go by file size and its command pass does not step over $C0. Texts with a NUL or with a code inside a $C0 code's columns can differ. Not changed (existing cheat tests kept passing).
5. Files over 1 MiB are refused (-EFBIG stops the launch); the original has no limit.
6. Gates not modelled: gp+0x3880 ($480p not tried when set; only a start-up clear store was found), and gp+0x38dc / gp+0x3460 (the original skips the game's own CHEATS.TXT and VMCDIR.TXT calls when set; what sets them was not traced).
7. $USBDELAY_n effect: the parsed digit matches, the effect does not. Original: the digit patches the DLAY word of its embedded PFS wrapper IOP module on XX. (USB) and SB. (SMB) launches only, and the module delays once by n seconds inside the IOP (1 s as shipped when no command is given; 5 s had the word never been patched); on an HDD launch the command changes nothing but the byte. launcHER: sleep(n) on the EE before the launch on every device, no delay when no command is given. Deliberately not changed in this task.
8. $USBDELAY_n previously accepted any number ($USBDELAY_12 slept 12 s, also $USBDELAY12); now only one digit is a command, like the original. A user who relied on a two-digit delay gets none.
9. pops_config_load_table / pops_config_export_table (tests only) map usb_delay to table byte 3 (0x100013); $USBDELAY_n writes 0x100017 (table byte 7, default 1). Reported, not changed.
10. VMCDIR.TXT: the HDD path of FUN_008d4f84 (gp+0x3448 == 0, other file calls) was not run; the content rules are assumed the same there. The original writes POPS strings 'pfs1:/<name>/' and 'pfs1:/<name>/SLOT%d.VMC'; launcHER builds its own paths '<vcdDir><name>/' and still also looks for <serial>.VMC0 / <game>.VMC0 beside SLOT0.VMC; with an empty VMCDIR.TXT (POPS folder itself) a NEW card is named <serial>.VMC0 by launcHER where the original's string is SLOT%d.VMC.
11. VMCDIR.TXT '.' and '..' are now accepted as folder names because the original accepts them (pfs1:/../); launcHER then uses '<vcdDir>../'. Before this change launcHER refused them with -EINVAL.
12. Game's own CHEATS.TXT starting number: launcHER uses strlen(game folder)+1 from reading the code; launcHER's PATCHES.TXT/MODES.TXT in the game folder start at 0 (the original has no such files).
13. Existing quirk kept: launcHER applies the $VCDID_n entry before all commands (quirk 23), the original where the command stands.
14. Files are found where launcHER looks (vcdDir and vcdDir/<game>/), not at the original's fixed mass:/POPS/ or pfs paths; which name the original's argv[0] holds at 0x874d84 was not traced.

## not done

1. NOT TESTED on a console: nothing in these three commits was run on a PS2 or on the rig. All evidence is host C via ctypes, Unicorn emulation of two original routines on synthetic input, or reading the disassembly (each labelled above).
2. Console-gated follow-up ($USBDELAY): reproduce the original's effect instead of the EE sleep: a one-time delay inside the IOP file wrapper on USB and SMB launches only, n seconds for $USBDELAY_n, 1 second when no command is given (byte 0x100017 ships as 1), none on HDD. Needs a console to judge (slow USB drives) and a decision on the default, since matching it adds a 1 s delay to USB/SMB launches that have none today. Not traced: that every XX./SB. launch reaches both 0x879cf0 and 0x87c030, which file operation first runs the wrapper's delay code, and what the 0x100013 byte (2 in MAIN, 6 in the USBDELAY profiles) does.
3. The original's file open/read part of the CHEATS.TXT reader (0x883270..0x883aa8) was not run under emulation (the pass was entered at 0x883aa8 with the text already in memory); the first pass ($C0 search, 0x883b80..0x8859fc) and the later code-compile passes were not part of this differential.
4. The VMCDIR reader's HDD branch (gp+0x3448 == 0) and its early exit (gp+0x3868 != 1 with FUN_008d8958() != 1 sets gp+0x38dc and returns -0x29a) were not run.
5. Item 4 extensions were not changed or removed (by instruction): see decisions_for_owner.
6. Shared docs not edited (by instruction): docs/POPSTARTER_R13_INVENTORY.md, docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md, README.md, docs/pops-setup.html, docs/CLOUD_CONTINUATION.md, docs/PR23_CHECKPOINT_HISTORY.md. Replacement text is in doc_updates. Quirk 22 in POPSTARTER_QUIRKS_TO_FIX_LATER.md ('Tokenizing differs ... Keep launcHER's') is now out of date: launcHER's reader does what the original does in every case that row lists.
7. No full EE build or link (see ee_build_check).
8. Per-file cheat/safe-mode state, the scan_cheats NUL and $C0 differences, and the card naming in the VMCDIR POPS-folder case were left as documented differences.

## decisions for owner

1. Bare digit and 'MODE n' in CHEATS.TXT (highest priority; present since 0b2d887 / 95bc06c, 2026-10-08): any white-space-delimited token '1'..'8' outside a '#'/';' line sets a compatibility mode in every file launcHER reads. Measured on the host: the plain description line 'Infinite Lives Player 1' sets mode 1, and 'Level 8 unlocked' sets mode 8, which the launch then refuses with -ENOTSUP (source read; launch not run). POPStarter takes nothing from either line. Recommendation: stop reading bare digits and MODE n from CHEATS.TXT (and PATCHES.TXT); if the MODES.TXT convenience is wanted keep it for MODES.TXT only, and drop mode 8 instead of failing the launch.
2. $NOBOOT / $BIOS (0b2d887): not POPStarter commands (emulated pass takes nothing; no such string in the image). Same CHEATS.TXT gives a different boot in launcHER. Recommendation: under 'match exactly first' remove them from CHEATS.TXT reading or move them to a launcHER-only file; if kept, list them as a launcHER extension in the inventory.
3. Other launcHER-only tokens in the same files: $DITHER_OFF/$NODITHER, $FASTMIPS/$SLOWMIPS, $PAL2NTSC/$FORCENTSC/$NTSC2PAL, $FIX_*/$CORE_FIXES/$PSXCORE_FIXES, $MODEn. Recommendation: same as $NOBOOT; at minimum $PAL2NTSC/$NTSC2PAL (they change the video mode) should not be reachable from a file POPStarter would read unchanged.
4. PATCHES.TXT / MODES.TXT (0b2d887, 12d2edd, 95bc06c) and the mc0:/POPSTARTER/, mc1:/POPSTARTER/, mc0:/POPS/, mc1:/POPS/ config directories (95bc06c): the original reads none of them for CHEATS-type config (static scan: only CHEATS.TXT, VMCDIR.TXT, DISCS.TXT names are built; reader path literals are pfs1 and mass:/POPS/). A leftover file there changes a launch that POPStarter would run unchanged. Recommendation: keep only if the owner wants them as documented launcHER extensions; otherwise remove the two extra names and the mc: directories for these files (the mc: directories stay valid for the SMB config and IRX files the original does read there).
5. Hard-coded 'ata0:/LAUNCHER-TEST-20261013-A/' in findPopsDependenciesForMode (launcher/src/handler_pops.c:153), added by bc135c7 (2026-10-27, 'feat(pops): expand dependency search directories and add title compat fallback'). It is the rig's staging directory (docs/POPSTARTER_HANDOFF.md:33, docs/evidence/*.json); no test pins it. It is the last search directory for POPS dependencies on every user's launch. Recommendation: remove it once the rig scripts pass their directory another way (argument or the existing device-derived <dev>/POPS/ entry). Not removed here, as instructed.
6. Tekken title hack from the same commit bc135c7 (handler_pops.c:994): with no modes set and no DB match, a path or title containing 'tekken' gets compatibility mode 6. The original has no title-name rule (its built-in list goes by disc fingerprint). Recommendation: remove, or replace by the measured built-in entry if one exists for those discs.
7. 63-character title truncation: common/src/launch_args.c pops_resolve_candidate_targets_bdma uses char baseTitle[64] (95bc06c) and builds '__.<title>' / 'PP.<title>' from it, while handler_pops.c uses gameBase[128]. A title longer than 63 characters is cut for candidate resolution but not for the folder lookup. The original's limit was not measured here (its name buffers are 0x80 bytes: the clear loop at 0x874d0c). Recommendation: measure the original's limit, then use one length in both places; reject rather than truncate.
8. $USBDELAY follow-up: decide whether launcHER should copy the original's effect (one-time IOP-side delay on USB/SMB only, 1 s by default) or keep its EE sleep (any device, none by default). Copying it adds a 1 s delay to USB/SMB launches that have none today. Recommendation: decide after a console comparison on a slow USB drive. Also decide whether the two-digit forms removed in b29464b should come back as a launcHER extension (recommendation: no).
9. pops_config_load_table/export_table put usb_delay in table byte 3 (0x100013); $USBDELAY_n is byte 7 (0x100017). Recommendation: fix the mapping when the table is next used for anything but its own round-trip test.
10. VMCDIR.TXT now accepts '.' and '..' like the original (66efcbe). Recommendation: keep (it is the user's own file and the original's behaviour); say so if launcHER should keep refusing them. Also decide whether, with a VMCDIR.TXT in use, launcHER should stop looking for <serial>.VMC0 / <game>.VMC0 and always use SLOT%d.VMC as the original's string does (recommendation: yes, after a console check of existing users' cards).
11. 1 MiB config file cap (-EFBIG stops the launch): the original has none. Recommendation: keep the cap but ignore the file instead of failing the launch, or leave as is; low priority.
12. Per-file safe-mode and cheat state: copying the original exactly (each file's codes compiled with that file's $SAFEMODE gate) needs a per-file gate in the cheat list. Recommendation: do it with the remaining scan_cheats work ($C0 step-over, NUL handling), as one follow-up with its own differential.

## doc updates


### inventory rows

Replace the `$USBDELAY_n` row of docs/POPSTARTER_R13_INVENTORY.md with:
| `$USBDELAY_n` | handler `0x89dbd4..0x89e13c`: `$USBDELAY_` + exactly one digit + terminator stores the digit in the byte at `0x100017` (ships as `0x01`). `main` (`0x879cf0..0x879e58`) copies that byte over the `DLAY` word (image `0x91fb30`) of the embedded `PFS Wrapper r6a` IOP module only when `gp+0x3448 != 0`, and starts the module (`0x87c030`) only when `gp+0x3448 == 1`, which is set for `XX.` (USB) and `SB.` (SMB) launch names only. The module then waits once: `DelayThread(n * 1000000)`, 5 s had the word not been patched | **PARTIAL** (2026-11-11): the parsed value is the original's (`usb_delay`, `usb_delay_set`; 120 fixed, 1500 random and 300 random `$USBDELAY` texts give the same byte at `0x100017` as the original's pass under emulation). The effect is not: launcHER sleeps `n` seconds on the EE before the launch on every device, has no IOP-side delay and no delay without the command (the original: 1 s on USB/SMB). The consumer was read from the code, not run. See [POPSTARTER_CONFIG_TEXT.md](POPSTARTER_CONFIG_TEXT.md). **NOT TESTED** on a console |

Replace the `CHEATS.TXT / PATCHES.TXT / per-title config locations` row with:
| CHEATS.TXT / PATCHES.TXT / per-title config locations | **PARTIAL** (2026-11-11): `CHEATS.TXT` commands are recognised the way the original's reader (`FUN_00883270`) recognises them: one byte-stream pass, no lines, tokens or comments, 66 handlers in the original's order (`pops_config_parse_text`, `pops_commands[]`); 120 fixed and 1500 random texts give the same commands at the same offsets, the same codes stepped over and the same X/Y, compatibility-mode, game-id and `0x100017` values as the original's pass under emulation. The game's own file is read after the one for all games, as in the original. Not the original's and still present, owner decision pending: launcHER also reads `PATCHES.TXT` and `MODES.TXT` and looks in `mc0:/POPSTARTER/`, `mc1:/POPSTARTER/`, `mc0:/POPS/`, `mc1:/POPS/` (the original builds only the names CHEATS.TXT, VMCDIR.TXT and DISCS.TXT, under the POPS folder and the game's folder), and takes its own tokens from these files (`$NOBOOT`, `$BIOS`, `MODE n`, a bare digit, `$DITHER_OFF`, `$FASTMIPS`, `$PAL2NTSC`, `$NTSC2PAL`, `$FIX_*`), so the same file can give a different result. One cheat list and one safe-mode state for all files (the original: per file). Quirks: see the new entries. See [POPSTARTER_CONFIG_TEXT.md](POPSTARTER_CONFIG_TEXT.md). **NOT TESTED** on a console |

Suggested replacement for the `VMC directory relinker (VMCDIR.TXT), SLOT0/1.VMC` row:
| VMC directory relinker (VMCDIR.TXT), SLOT0/1.VMC | **PRESENT** (2026-11-11): `VMCDIR.TXT` read as the original reads it, for all games then per game (`pops_config_parse_vmcdir`; 39 fixed and 400 random files match `FUN_008d4f84` under emulation with USB-launch flags; its HDD branch was not run). A file of 104 bytes or more, or with CR, LF, `/`, `\` or `:` anywhere, is ignored and the launch goes on; the name is not trimmed; an empty file means the POPS folder. Not the original's: launcHER also accepts `<serial>.VMC0` / `<game>.VMC0` card names in that folder. **NOT TESTED** on a console |

### quirks

New entries for docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md (numbers to be assigned by the lead). Suggested heading: 'CHEATS.TXT command recognition, $USBDELAY_n and VMCDIR.TXT (docs/POPSTARTER_CONFIG_TEXT.md)'. All copied; found by running the original's command pass and VMCDIR reader under emulation (tools/test_pops_config_text.py).

| # | POPStarter behaviour (copied) | Possible fix later |
|---|---|---|
| - | Nothing in `CHEATS.TXT` is a comment and there are no lines: a command is taken at any `$` that is not inside a cheat code's columns, whatever stands before it. `#$SMOOTH`, `; $SMOOTH` and `x$SMOOTH` all apply. | Honour `#` and `;` at the start of a line. |
| - | A command ends only at CR, LF, NUL, a space or the next `$`. A TAB after the name makes it no command (`$SMOOTH<TAB>` does nothing); `$SMOOTH$SCANLINES` is two commands. | Accept any white space. |
| - | A command inside a cheat code's columns is not seen: `$20012345 00$SMOOTH` is one 18-column code and `$SMOOTH` is lost. | None needed. |
| - | `$ORIGINAL_OPCODES` tests its terminator two columns late (column 19): any two bytes may follow the name, so `$ORIGINAL_OPCODES` + CR LF works and so does `$ORIGINAL_OPCODESXY `, but `$ORIGINAL_OPCODES` + LF + `$SMOOTH` and `$ORIGINAL_OPCODES $SMOOTH` are not taken (and then only `$SMOOTH` is). | Test the byte after the name. |
| - | `$XPOS_` / `$YPOS_` with a malformed number (`$XPOS_-15`, `$XPOS_12Q`, six digits, no digits) still write, using the number temporary all number commands share: 0 at first, the game folder name's length plus one in the game's own file, else the last value of `$LEFTADJ_n`, `$?POS_n`, `$DWSTRETCH_n`, `$DWCROP_n`, `$PADnID_0Xhh` or `$COMPATIBILITY_0Xhh`. That write also uses up the one X (or Y) write. A value above 65535 writes nothing. | Ignore a malformed number. |
| - | Only the first of `$SAFEMODE` / `$SAFEMODE2` in a file counts; the other is not tried until `$NOSAFEMODE`. `$NOSAFEMODE` with neither on is not a command. | Let the later one win. |
| - | `$COMPATIBILITY_0X08`..`0XFF` and `0X00` are taken and do nothing; a one-digit `$COMPATIBILITY_0X5` is not a command. launcHER used to turn `0X08` into mode 8 and refuse the launch. | None needed. |
| - | `$DX_`, `$DY_`, `$MAGH_`, `$MAGV_`, `$DW_`, `$DH_` each take their first well-formed value in a file and are not tried again in it; `$VCDID_n` is tried until one is not 0. | None needed. |
| - | `$USBDELAY_` takes exactly one digit: `$USBDELAY_12`, `$USBDELAY_05` and `$USBDELAY5` are not commands and leave the delay as it was. | Accept more digits. |
| - | (NOT copied, see inventory) `$USBDELAY_n` delays once inside POPStarter's PFS wrapper IOP module, on USB and SMB launches only, and 1 second even without the command (the byte ships as 1). launcHER sleeps on the EE on every device and not at all without the command. | Decide after a console comparison. |
| - | A `VMCDIR.TXT` whose name is followed by a line end is ignored: CR or LF anywhere makes the original drop the whole file with a message, like `/`, `\` and `:`. Only a file with no line end is used. Ignoring is never an abort. | Strip one trailing line end. |
| - | `VMCDIR.TXT` is not trimmed: spaces, a TAB, `#`, lower case and bytes above 0x7f are part of the folder name; a NUL ends the name but bytes after it are still checked. `.` and `..` are names. | Trim; refuse `.` and `..`. |
| - | A `VMCDIR.TXT` of 104 bytes or more (the file's size) is ignored. An empty `VMCDIR.TXT` is used and puts the cards in the POPS folder itself (`pfs1://SLOT%d.VMC`). | Treat an empty file as absent. |

Also: quirk 22 ('Tokenizing differs in two small ways ... Keep launcHER's.') is now obsolete. Suggested replacement text for its first column: 'Resolved 2026-11-11: launcHER's reader is the original's byte-stream pass (`pops_config_parse_text`), so `$VCDID_5<tab>` is ignored, `x$VCDID_9999` and `$RESET_WARMBOOT$NOPAD0` are commands and a `#` hides nothing, as in the original. See the CHEATS.TXT command recognition entries.' Quirk 23 ($VCDID_n applied before all commands) is unchanged.

### user facing

README.md (CHEATS.TXT / commands paragraph), suggested additions:
- Commands are found the way POPStarter r13 finds them: anywhere in the file, at any `$`. A `#` or `;` in front does NOT switch a command off (same as for codes): remove the `$` to disable it. A command must be followed by a space, a line end or the next `$`; a TAB after it disables it. There is no line-length limit any more (a very long line used to be an error).
- `$XPOS_n` / `$YPOS_n` take 1 to 5 plain digits. Anything else (`$XPOS_-15`, `$XPOS_12Q`) still writes a position, as in POPStarter: usually 0. Negative offsets do not exist.
- Only the first of `$SAFEMODE` / `$SAFEMODE2` in a file counts.
- Replace `$USBDELAY_<seconds>` with: `$USBDELAY_n`, one digit 0..9 exactly as in POPStarter (`$USBDELAY_12` is not a command). launcHER waits n seconds before the launch; POPStarter's own delay (inside its USB/SMB file module, 1 second by default) is not reproduced yet. Not tested on a console.
- Compatibility modes: `$COMPATIBILITY_0x08` and above are ignored, as in POPStarter (they used to stop the launch). Note: launcHER still reads its own `MODE n` / bare digit lines from these files (owner decision pending), so a plain text line containing a lone digit 1..8 can set a mode.
- Replace the VMCDIR.TXT line with: **`VMCDIR.TXT`:** one folder name (inside the POPS folder) where the memory cards are kept, read as POPStarter r13 reads it: the file must hold the name and nothing else, with NO line end after it (a file saved with Enter at the end is ignored, as in POPStarter), no `/`, `\` or `:`, at most 103 bytes. Spaces are part of the name. A file POPStarter would ignore is ignored and the game still starts with its normal card folder. An empty file means the POPS folder itself. A `VMCDIR.TXT` in the game's own subfolder is read after the one beside the games. Not tested on a console.

docs/pops-setup.html: line 306 `$USBDELAY_#`: say 'one digit, 0 to 9'. Lines 258 and 415 (VMCDIR.TXT): add 'folder name only, no line break at the end of the file, no slashes or colon; a file with a line break is ignored (POPStarter behaviour)'.

### hardware checklist

All NOT TESTED on a console. Suggested checks, each against POPStarter r13 on the same media:
1. CHEATS.TXT with `#$SMOOTH`, `$SMOOTH<TAB>`, `x$SCANLINES` and `$SMOOTH$SCANLINES`: same picture as POPStarter (smoothing on, on, scanlines on; the TAB line off).
2. `$XPOS_-15` and `$LEFTADJ_12 $XPOS_Q`: picture position equals POPStarter's (X = 0 and X = 12).
3. Game folder CHEATS.TXT containing only `$XPOS_`: X equals the folder name's length plus one in both.
4. `$ORIGINAL_OPCODES` followed by LF only and then `$SMOOTH`: neither applies in both; with CR LF both apply.
5. `$SAFEMODE $SAFEMODE2` and `$SAFEMODE2 $SAFEMODE`: cheats gate as POPStarter's (first one only).
6. `$COMPATIBILITY_0X08`: the game launches (no -ENOTSUP) and behaves as with no mode.
7. A CHEATS.TXT with a line over 254 characters followed by a command: launches and applies the command.
8. `$USBDELAY_5` on a slow USB drive: launcHER (EE sleep) against POPStarter (wrapper delay); also POPStarter's default 1 s and `$USBDELAY_0`; confirm on HDD that POPStarter shows no delay. Input for the follow-up decision.
9. VMCDIR.TXT `SAVES` with no line end: cards used from POPS/SAVES/ in both. Same file saved with CR LF: both ignore it and use the game's folder.
10. Empty VMCDIR.TXT: POPStarter uses SLOT0.VMC in the POPS folder; note which card file launcHER opens or creates there (it may create <serial>.VMC0).
11. VMCDIR.TXT of 104 bytes, and one containing `A/B`: the game still starts in both, with the normal card folder.
12. VMCDIR.TXT ` SAVES ` (spaces) and `..`: compare which folder each program uses; confirm the device drivers accept those paths.
13. Global VMCDIR.TXT `Shared` plus a game VMCDIR.TXT `Other` + CR LF: both keep `Shared`.
