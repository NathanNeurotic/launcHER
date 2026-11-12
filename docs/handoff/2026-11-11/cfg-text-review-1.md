# CHEATS.TXT / $USBDELAY / VMCDIR.TXT: review 1

Written by an independent reviewer of the track. Copied as written.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## verdict

issues

## issues

1. **severity:** major  
   **description:** The original's $FORCEPAL handler is gated and the new reader/doc treat it as a plain command. In the original (0x8987f0) $FORCEPAL stores gp+0x38a0/0x38d0/0x3898 only when gp+0x3864 is 0; gp+0x3864 is set to 1 by $480P (0x8902a4), by the config byte 0x10002a == 2 at start-up (0x871218) and at 0x88301c. So '$480P' followed by '$FORCEPAL' (same file, or $480P in the first file and $FORCEPAL in the game's file) does nothing in the original, while launcHER's CMD_PLAIN row runs apply_plain_command, sets cfg.video_mode = POPS_VMODE_NTSC2PAL (progressive_requested stays 1) and traces effect = 1. The committed test's own equality criterion fails on this text; it is simply not among the 120 fixed or 1500 random texts. The behaviour is inherited (base cfebe01 gives the same cfg), so it is not a regression, but the commit/doc claim of equality is not true for this handler and docs/POPSTARTER_CONFIG_TEXT.md lists $FORCEPAL as 'name + terminator' with no gate. Whether the launch differs was not shown: pops_fix_finalize_video and pops_apply_region are neutralised through video_auto_disabled when progressive was requested (read in the source), other consumers of cfg.video_mode were not analysed.  
   **evidence:** My oracle (whole FUN_00883270 from its entry): all 5041 ordered pairs of 71 command forms + 9 triples, the only mismatches are '$480P $FORCEPAL ', '$480P $NOPAL $FORCEPAL ', '$FORCEPAL $480P $FORCEPAL ' (C effect True, original no store). Random phase seed 0xC0FFEE77 hit it too ('$480P$FORCEPAL\r\n...'). Two-file run (439 cases, gp words of file 1 carried into file 2): 3 fails, all $FORCEPAL after a $480P in the first file. Implementer's own Original.compare('$480P $FORCEPAL ') raises: "[(0,'$480',True),(6,'$FORCEPAL',True)] != [(0,'$480',True),(6,'$FORCEPAL',False)]"; launcHER cfg after it: video_mode=2, progressive_requested=1. Disassembly: 008987f0 lw v0,0x3864(gp); 008987f4 bnez v0,0x898814; 008902a4 sw v0,0x3864(gp) in the $480P handler.  
   **suggested fix:** Give $FORCEPAL its own kind: no effect (and effect = 0) once a $480P was taken / progressive_requested is set (and document the start-up sources of gp+0x3864 as not modelled or model them); add '$480P $FORCEPAL ' and the two-file form to FIXED/EXPECTED; add the gate to the handler table in docs/POPSTARTER_CONFIG_TEXT.md.
2. **severity:** major  
   **description:** Two behaviour-relevant single-line mutants in new code (command_code_columns, common/src/pops_config.c) survive the committed tests with reference inputs. The committed code itself is right (my differential agrees with the original), but no committed test distinguishes these conditions, so a later edit can break the cheat-code column test unnoticed.  
   **evidence:** Mutant K (line 183: drop "&& t[4] == '0'" from the $5000 test) -> tools/test_pops_config_text.py Ran 23 OK, and also OK in test_pops_features.py, test_pops_resident.py, test_pops_display.py, test_pops_warmboot.py, test_pops_builtin_db.py. Mutant K3 (line 190: $S kind t[5] range '0'..'3' -> '0'..'2') -> OK in the same six test files. Both are non-equivalent: my perturbation run (12 code shapes, every column x 35 bytes, 6660 texts, 4843 codes stepped over, 0 fails against the original) contains texts where each mutant would differ, e.g. '$50010000 0000$NOPAL ' (original: not a code).  
   **suggested fix:** Add fixed texts that pin each condition of the five code tests: '$50012345 1234 $NOPAL ', '$50102345 1234 $NOPAL ', '$S0000300 12345678$NOPAL ', '$S0000400 12345678$NOPAL ', '$T0000300 ...', '$T0000400 ...' (and their expected commands/codes) to FIXED/EXPECTED.
3. **severity:** minor  
   **description:** launcHER's own token splitter (next_launcher_token) cuts a token at 63 bytes and treats the rest as a new token, so 63 non-blank bytes followed by a digit add a compatibility mode. The doc describes these tokens as 'split at white space'; the committed test's tolerance (MODE_TOKEN regex) does not model the cut, so its random comparison can fail on such a text. Inherited from the old parser (base cfebe01 gives the same result), launcHER-only (the original takes none of these tokens).  
   **evidence:** launcher('x'*63 + '1 ') -> compat_modes = 0x1; implementer's Original.compare on that text fails with 'None is not true'. Found by my random phase: '...$CODECACHE_ADDON_237980//$DY_1\x0b$ULTRA_WIDESCREEN...' (a 64-byte run ending in '1') -> C modes 0x1, original 0x0. Old parser at cfebe01: same modes=0x1.  
   **suggested fix:** Skip the remainder of an over-long run instead of starting a new token, or document the 63-byte cut; add the case to the Native test.
4. **severity:** minor  
   **description:** next_launcher_token uses isspace()/isdigit() from the C library, which are locale dependent for bytes above 0x7f. Inside the Python test process (user locale) byte 0xA0 counts as white space, so '\xa04 ' adds compatibility mode 4 on the host; a stand-alone program built with the same gcc reports isspace(0xA0) == 0, and the EE build was not run. Host results for launcHER-only tokens next to high bytes are therefore not evidence for the EE build. Inherited behaviour.  
   **evidence:** rdiff all-256 phase: '$COMPATIBILITY_0X\xa04 ' -> C modes 0x8, original 0x0; launcher(b'\xa04 ') -> 0x8 in the ctypes DLL; scratch sp2.c (isspace over 128..255) prints count=0.  
   **suggested fix:** Use explicit byte tests (space, \t, \r, \n, \v, \f; '0'..'9') in next_launcher_token and apply_launcher_token.
5. **severity:** minor  
   **description:** Undocumented difference for very short files: the original's code tests read columns 9 and 14 of the text, which lie beyond its malloc(2*size) buffer when the file is shorter than about 8 bytes, so its result depends on uninitialised heap; launcHER models zeros. The doc says only that the second half of the buffer is zeroed.  
   **evidence:** My oracle with the heap pre-filled with 0x20: file '$800' (4 bytes) is stepped over as a 14-column code by the original; with a zero heap, and in launcHER, it is not.  
   **suggested fix:** Add one line to 'Known differences that remain'.
6. **severity:** minor  
   **description:** Wording: commit b205a3e says 'test_pops_warmboot and test_pops_builtin_db (four former known differences are now equal to the original)'; the diff changes four expectations in test_pops_warmboot.py and five in test_pops_builtin_db.py (x$VCDID_9999 plus four $FAKELC forms). The test prints '30 texts x starting numbers' for 5 texts x 6 starting values (the doc's '30 text/start-value pairs' is right).  
   **evidence:** git diff cfebe01..HEAD -- tools/test_pops_warmboot.py tools/test_pops_builtin_db.py; tools/test_pops_config_text.py test_shared_number_start.  
   **suggested fix:** Correct the print string; nothing to do for the commit message unless history is rewritten on request.
7. **severity:** minor  
   **description:** Environment, not caused by these commits but it affects every test claim made with the prescribed recipe: exporting TMP/TEMP does not isolate the host DLL. The shell presets TMPDIR and Python's tempfile.gettempdir() reads TMPDIR first, so tools/test_pops_features.py:compile_shared_library writes the fixed name pops_features_test.dll into the shared <temp>. Concurrent runs then fail with a link error that looks like a test failure.  
   **evidence:** My first, un-isolated runs: tools/test_pops_breakpoint.py rc=1 and tools/test_pops_warmboot.py rc=1, both only 'ld.exe: cannot open output file <temp>\pops_features_test.dll: Permission denied'. With TMPDIR also exported to a private directory all 27 files pass (see tests_rerun).  
   **suggested fix:** Export TMPDIR as well in the run recipe, or make compile_shared_library use a per-process file name.

## independent checks

1. Own oracle, different from the implementer's: <scratch>/cfg-text-r1-review/orc.py runs FUN_00883270 from its ENTRY 0x883270 (open/seek/read/close, malloc, stat stubbed; strlen/memcpy/memset in Python), and finds effects by decoding every executed store, not from a list of helpers. Handler identity calibrated by running each of the 66 commands alone: 66 distinct loop re-entry addresses, equal to the 'ends at' addresses and the order of pops_commands[].
2. Differential C (ctypes, pops_config_parse_text with trace) vs that oracle, isolated temp dir: 16050 texts, 25536 commands, 410 codes stepped over (phases: names 44, numbers 2961, terminators 5597, hex 4204, codes 744, random 2500 seed 0xC0FFEE77). Compared: command offsets/names/effect, code columns, X/Y writes, compat modes, game id, byte at 0x100017, left adjust, stretch/crop, pad ids, GS DISPLAY value, per-file safe-mode flags. 3 mismatches: $FORCEPAL after $480P (major issue), the 63-byte token cut and the 0xA0 white space (both launcHER-only tokens). Everything else equal.
3. All ordered pairs of 71 command forms (5041) plus 9 triples: only the $480P ... $FORCEPAL texts differ.
4. Cheat-code column test: 12 code shapes, each column replaced by each of 35 bytes, plus the column after the code: 6660 texts, 4843 codes stepped over, 0 mismatches.
5. 92 hand-picked boundary texts, each as the global file and as the game's file ('Some Game Name/'): 184 runs, 0 mismatches (five- and six-digit numbers, $VCDID_0 chains, $LEFTADJ_256, X = 65535/65536, complete GS sets, $ORIGINAL_OPCODES column 19, BOM, UTF-16 text, lone '$').
6. Two reader calls in a row (first file's gp-relative stores written back before the game's file; C: one PopsConfig, gs_mask cleared between): 439 cases; 3 mismatches, all $FORCEPAL after a $480P in the first file; 2 further differences are the documented one safe-mode gate for all files ($SAFEMODE then $SAFEMODE2 in the next file: original takes it, launcHER does not).
7. Game file start value, end to end through the reader's entry (the implementer injected it): opens mass:/POPS/<name>/CHEATS.TXT and '$XPOS_' writes len(name)+1 for names of 1..39, 63, 64, 80 and 99 bytes (44 texts, 0 mismatches). That gp+0x38f0 is '<folder>/' for every launch kind is still from reading 0x874ddc..0x8750e4 only.
8. VMCDIR.TXT, own run of FUN_008d4f84 vs pops_config_parse_vmcdir: 2544 files (1746 used, 798 ignored), 0 mismatches: every single byte alone/inside a name/after a NUL, sizes 0..7, 96..111, 127..129, 255, 256, 1000, a bad byte at each position of a 103-byte file, 1500 random files (seed 0x5EED0A11), gp+0x3448 = 2 and 3, a stack pre-filled with '/', LF, 'A'. The HDD branch, which the implementer did not run, was run: 18 global and 7 game files, opens pfs1:/POPS/VMCDIR.TXT and pfs1:/POPS/My Game/VMCDIR.TXT, same decisions. Missing file: returns 0, strings kept.
9. Static checks against the decoded image: gp+0x3880 is stored only at 0x870ca4 (clear); gp+0x3448 is set to 1 only at 0x871618 and 0x8719a4; gp+0x3888 gets 3 at 0x871620 and 0 at 0x8719a8/0x870c7c; the embedded module at 0x91f680 is an ELF of 0xa45 bytes named 'PFS Wrapper r6a' with one 'DLAY' word at module address 0x420 and the word at 0x540 equal to 1; file byte 0x417 of MAIN is 0x01 and 0x413 is 0x02. These match the doc. The other three profile ELFs were not looked at.
10. Old parser (git archive cfebe01, built separately) on the suspect inputs: '$480P $FORCEPAL' -> video_mode 2, 63 bytes + '1' -> mode 1, 0xA0 as white space, cheat scan stopping at a NUL: all the same as HEAD, so none of these is a regression.
11. Numbers in docs/commits counted: FIXED 120, EXPECTED 120, VMC_EXPECTED 39 (first 30 also as game file), USB_EXPECTED 20, 5 texts x 6 start values, 17+4 = 21 modes; my run of the test prints 2876 commands, 399 codes, 96 MODE texts, 20 and 84 writes of 0x100017, 212 taken / 188 ignored. All equal to the doc.
12. EE compile, toolchain <ps2build> (mips64r5900el-ps2-elf-gcc): common/src/pops_config.c compiled with -c -Wall -Wextra -O2 -G0 -Icommon/include, rc 0, no diagnostics (object written to scratch). launcher/src/handler_pops.c with -fsyntax-only -Wall -Os -G0 and the ps2build package headers, rc 0, no diagnostics. No ELF was linked or built. NOT TESTED on a console; every result above is host or Unicorn emulation of single routines.
13. Hygiene: 12 files changed, none of the off-limits docs; no binary files; no long hex or byte tables in added lines (the tracer holds a few 32-bit instruction-pattern and address constants only); no AI attribution in the three commit messages or added lines; author/committer is the repository owner; build.yml gains one step 'python tools/test_pops_config_text.py', which passes without inputs (Ran 23, skipped=10).
14. Worktree left as committed: mutants were applied only to private 'git archive HEAD' copies under the scratch directory, never to the cfg worktree; final 'git status' there is clean at 66efcbe on pr23/cfg (only the git-ignored build/ directory the tests write).

## mutants

1. Method: 28 single-line mutants, each in its own copy of HEAD (git archive) with its own temp directory, tools/test_pops_config_text.py run with POPSTARTER_TEST_ELF and POPS_TEST_ELF; unmutated baseline in the same setup: Ran 23 OK. 23 caught, 5 survived (2 behaviour-relevant in new code, 1 in an unchanged line and caught by another test, 2 equivalent).
2. A pops_config.c:526 $ORIGINAL_OPCODES terminator rest[2] -> rest[0]: CAUGHT (4 failures: Native.test_table, test_values, Original.test_fixed_texts, test_random_texts)
3. B :652 $USBDELAY_ drop the terminator check: CAUGHT (6 failures)
4. C :1000 VMCDIR size >= 104 -> > 104: CAUGHT (4 failures)
5. D :165 command_end also accepts TAB: CAUGHT (8 failures)
6. E :667 $COMPATIBILITY_0X mode <= 7 -> <= 8: CAUGHT (Native.test_values, Original.test_fixed_texts)
7. F :1127 game file start value strlen(subfolder)+1 -> strlen(subfolder): CAUGHT (2 Source tests)
8. G :635 $SAFEMODE drop the 'one already on' gate: CAUGHT (3 failures)
9. H :1005 VMCDIR drop the ':' test: CAUGHT (4 failures)
10. I handler_pops.c:1048 cfg.vmc_dir_set -> cfg.vmc_dir[0]: CAUGHT (Source.test_vmcdir_use)
11. J :588 vcdid_set = 1 also for $VCDID_0: CAUGHT (3 failures)
12. L :390 X/Y value > 0xffff -> >= 0xffff: CAUGHT (Original.test_shared_number_start only)
13. R :642 $NOSAFEMODE drop its gate: CAUGHT (3 failures)
14. W :614 $?POS_ writes for any second byte: CAUGHT (5 failures)
15. K2 :181 $3/$8/$D drop the t[3] test: CAUGHT (3 failures)
16. K4 :195 drop the '!' code kind: CAUGHT (3 failures)
17. K5 :195 '='/'!' kind accept t[2]=='0' only: CAUGHT (3 failures)
18. K6 :187 18-column kinds '0'..'2' -> '0'..'3': CAUGHT (3 failures)
19. K7 :193 $T kind drop t[5]=='0': CAUGHT (1 failure)
20. K8 :181 drop the $D kind: CAUGHT (3 failures)
21. P2 :594 $PADnID_0X terminator rest[8] -> rest[7]: CAUGHT (5 failures)
22. P3 :573 $LEFTADJ_ applied up to 256: CAUGHT (2 failures)
23. P4 :537 GS commands 5 digits -> 4: CAUGHT (Original.test_random_texts only)
24. P5 :584 $VCDID_ 4 digits -> 5: CAUGHT (4 failures)
25. K :183 $5000 code test, drop "&& t[4] == '0'": SURVIVED test_pops_config_text.py and also test_pops_features.py, test_pops_resident.py, test_pops_display.py, test_pops_warmboot.py, test_pops_builtin_db.py. Behaviour-relevant, new code (major issue).
26. K3 :190 $S code kind, t[5] range '0'..'3' -> '0'..'2': SURVIVED the same six test files. Behaviour-relevant, new code (major issue).
27. M :919 remove 'cfg->gs_mask = 0' in load_config_file: survived test_pops_config_text.py; the line is unchanged by these commits and tools/test_pops_display.py catches it (3 failures).
28. N :1008 VMCDIR name not cut at the NUL: survived; equivalent (vmc_dir is used as a C string, so the bytes copied after the NUL are never read).
29. P1 :804 upper-casing 'c <= z' -> 'c < z': survived; equivalent for behaviour (no command, code digit or token contains the letter Z).

## tests rerun

1. Complete list, 27 files tools/test_*.py, at HEAD 66efcbe in the cfg worktree, TMP/TEMP/TMPDIR pointed at a private directory.
2. WITHOUT reference inputs: all 27 exit 0. test_launch_args, test_network_transports, test_popfs, test_pops_fatfs, test_pops_modes, test_pops_vmc, test_smap_ipconfig, test_sony_ioman_layout, test_subq_bridge: rc 0 (no unittest summary line). test_pops_breakpoint Ran 11 OK (skipped=4); test_pops_builtin_db Ran 14 OK (skipped=14); test_pops_config_text Ran 23 OK (skipped=10); test_pops_display Ran 21 OK (skipped=6); test_pops_external Ran 128 OK (skipped=14); test_pops_features Ran 29 OK (skipped=2); test_pops_fix_files Ran 31 OK (skipped=3); test_pops_io_probe Ran 6 OK; test_pops_launch_hooks Ran 46 OK (skipped=13); test_pops_module_irx Ran 11 OK (skipped=4); test_pops_opcodes Ran 9 OK (skipped=3); test_pops_padman Ran 6 OK (skipped=3); test_pops_progressive Ran 8 OK (skipped=5); test_pops_read_trace Ran 9 OK; test_pops_resident Ran 75 OK (skipped=12); test_pops_runtime_corrections Ran 8 OK; test_pops_startup_calls Ran 6 OK; test_pops_warmboot Ran 7 OK (skipped=3).
3. WITH POPSTARTER_TEST_ELF and POPS_TEST_ELF: all 27 exit 0. test_pops_breakpoint Ran 11 OK; test_pops_builtin_db Ran 14 OK; test_pops_config_text Ran 23 OK; test_pops_display Ran 21 OK; test_pops_external Ran 128 OK (skipped=3); test_pops_features Ran 29 OK; test_pops_fix_files Ran 31 OK; test_pops_io_probe Ran 6 OK; test_pops_launch_hooks Ran 46 OK (skipped=3); test_pops_module_irx Ran 11 OK; test_pops_opcodes Ran 9 OK; test_pops_padman Ran 6 OK; test_pops_progressive Ran 8 OK (skipped=3); test_pops_read_trace Ran 9 OK; test_pops_resident Ran 75 OK; test_pops_runtime_corrections Ran 8 OK; test_pops_startup_calls Ran 6 OK; test_pops_warmboot Ran 7 OK; the nine script-style files rc 0.
4. Not hidden: before TMPDIR was isolated, two runs of mine showed tools/test_pops_breakpoint.py rc=1 and tools/test_pops_warmboot.py rc=1. Both outputs are only the linker's 'cannot open output file <temp>\pops_features_test.dll: Permission denied' (the shared DLL was held by another concurrent process). The without-inputs log also carries lines from that stale un-isolated run of mine; the per-file results above are the isolated run's.
5. tools/test_pops_config_text.py with inputs, in a clean copy of HEAD: Ran 23 OK; printed 120 fixed texts, 1500 random texts (2876 commands, 399 codes, 96 MODE texts, 0x100017 written in 20), 300 random $USBDELAY texts (84), 30 start-value runs, 20 $USBDELAY texts, 39 VMCDIR files (30 as game file), 400 random files (212 taken, 188 ignored), 21 modes x 2 states.
6. EE compile check: pops_config.c -c -Wall -Wextra -O2 -G0 rc 0 without diagnostics; handler_pops.c -fsyntax-only -Wall -Os -G0 rc 0 without diagnostics. No link, no ELF, no console run.

## unsupported claims

1. docs/POPSTARTER_CONFIG_TEXT.md, handler table row '0x8984a4..0x89882c: $MUTE_ALL $NOPAL $FORCEPAL' under 'name + terminator unless noted': $FORCEPAL has a gate (gp+0x3864, set by $480P and at start-up) that the table does not note and the C table does not model.
2. Commit b205a3e subject and body ('recognise CHEATS.TXT commands as POPStarter does', 'tries 66 handlers in a fixed order'), the doc's 'launcHER copies it' and the pops_config.h comment 'effect is nonzero when it changed something': true on the 120 + 1500 tested texts, not in general. Counterexample: '$480P $FORCEPAL ' (original: $FORCEPAL stores nothing; launcHER: effect 1, video_mode becomes NTSC2PAL).
3. Doc, 'Known differences that remain' reads as the full list. Missing: the $FORCEPAL gate; the original reading past its 2*size buffer on very short files (result depends on heap contents, launcHER uses zeros); launcHER's tokens being cut at 63 bytes, so 'split at white space' is not exact.
4. Doc and commit: 'the game's own file starts with ... the name's length plus one' is stated as fact. The reader half is now shown end to end by my run (strlen of the string passed in a1); that the string at gp+0x38f0 is '<folder name>/' for every launch kind rests on reading 0x874ddc..0x8750e4 only (the implementer's report says so, the doc does not).
5. Doc: '0x100017 ... is 0x01 as shipped in the four profiles looked at (MAIN, DEBUG, USBDELAY, USBDELAY_DEBUG)' and the 0x100013 difference: I confirmed MAIN only (0x417 = 0x01, 0x413 = 0x02); the other three were not checked by me and no test in the repository checks them.
6. Doc, $USBDELAY consumer section: marked 'read from the code, not run', and it stays that. I confirmed the static facts (one DLAY word at module address 0x420, word 0x540 = 1, module name, the stores to gp+0x3448 and gp+0x3888); the IOP module's delay logic and the SB./XX. name tests were not re-derived by me.
7. Commit b205a3e: 'test_pops_warmboot and test_pops_builtin_db (four former known differences are now equal to the original)': four in test_pops_warmboot.py, five in test_pops_builtin_db.py.
8. Implementer's report, 'All 27 tools/test_*.py pass both without and with the reference inputs': confirmed by my isolated runs. Supported, with the caveat that the prescribed TMP/TEMP export does not isolate the test DLL on this machine, so that claim could not have been made under real isolation with the recipe as given.
