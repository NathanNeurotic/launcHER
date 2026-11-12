# Gap audit and status documents: review 2 (NOT answered)

Written by an independent reviewer of the track. Copied as written.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## verdict

issues

## issues

1. **severity:** major  
   **description:** Shared documents that the track rules list as off-limits were edited again. Commit db36890 changes README.md, docs/CLOUD_CONTINUATION.md, docs/POPSTARTER_R13_INVENTORY.md and docs/pops-setup.html. The implementer admits this and leaves the decision to the lead.  
   **evidence:** git show --stat db36890: README.md 2, docs/CLOUD_CONTINUATION.md 75, docs/POPSTARTER_R13_INVENTORY.md 9, docs/pops-setup.html 2. Mitigating facts I measured: git diff 3d42449 codex/popstarter-replacement (tip d31d4a7) shows none of the four files changed on the tip, and git merge-tree --write-tree HEAD codex/popstarter-replacement reports no conflict. On that merged tree tools/test_pops_doc_claims.py passes (12 tests, 7 skipped without inputs; 12, 0 skipped with).  
   **suggested fix:** Lead decides: either accept db36890 as this track's own lines, or drop its hunks for the four files and apply doc_updates by hand. After the merge the '27 test files' and 'no skin code / MISSING' statements are stale (the merged tree has 28 test files and an IGR skin loader).
2. **severity:** major  
   **description:** The gap audit's BIOS.BIN section omits one of the handler's three -666 exits. The fix commit added the game-folder exit only. The handler also runs the POPS folder check FUN_008d8958 when gp+0x3868 is not 1; for the all-games scope a result other than 1 sets gp+0x38dc = 1 and returns -666 with nothing opened. For the game scope the same failed check is ignored and the file still loads. Section 4 and S22 never mention FUN_008d8958 for this handler.  
   **evidence:** Static: li v0,-666 at 0x880378, 0x880558 and 0x8805a4 inside 0x88019c..0x880a24; 0x880338..0x880380 reads gp+0x3868, calls 0x8d8958, skips the exit when scope == 1, else sw gp+0x38dc and -666. My Unicorn run with FUN_008d8958 executing for real (8 runs): scope 0 with POPS folder missing gives -666, 0 opens, gp+0x38dc/0x3460/0x3868 all 0 to 1 (2 of 2); scope 1 with POPS folder missing gives return 1, file loaded, same three flags set plus gp+0x38e0 (2 of 2). grep of the audit for 8d8958 finds only the IGR rows. The same three-site pattern exists in the OSD (0x87ec68, 0x87ee84, 0x87eed0), TROJAN (0x880adc, 0x880d18, 0x880d64) and PATCH (0x881ea0, 0x8820d8, 0x882124) loaders. Host emulation only; not tested on a console.  
   **suggested fix:** Add a row to section 4 (and the quirk text) for the POPS-folder exit at 0x880338..0x880380 with its scope asymmetry, and say that main normally runs the same check earlier (jal 0x8d8958 at 0x873f9c, skipped when gp+0x3888 != 0).
3. **severity:** major  
   **description:** The new test does not pin several statements the audit and commit message say it compares with the document's wording. 12 of my 23 single-line mutants survive with the reference input. Four of them are in rows the test claims to cover: a wrong TROJAN-loader census count, a moved BIOS print site, the S24 statement flipped to 'main reads the return value', and the section 9 delay changed from 'once' to 'on every call'.  
   **evidence:** Mutants applied to a git-archive copy of HEAD, test run without and with POPSTARTER_TEST_ELF. Survived both ways: M13 'TROJAN loader: 20, 1 without' -> '20, 2 without' (the check is assertIn('1 without'), which '21 without' satisfies); M14 0x880984 -> 0x880978 in the gp+0x38b0 row (address still present in S21); M16; M17 (only the token `0x876b20` is checked). Also M08: file number 4 slot 0x232d08 -> 0x232d30 survives because the test only checks membership in the 60 pairs.  
   **suggested fix:** Assert whole row phrases (label, count and 'without' together), the exact number-to-slot list, and the S24 and section 9 sentences; or reword the audit paragraph to say only a few phrases are pinned.
4. **severity:** major  
   **description:** The Native CI-coverage check counts a test file as run if its name appears anywhere in a workflow file. A commented-out step or a step under 'if: false' still counts, so the check that the documents call machine-checked can pass while CI no longer runs a test.  
   **evidence:** workflow_coverage() uses re.findall(r"tools/(test_\w+\.py)") on the raw YAML text. Mutant M11 (comment out the run line of test_pops_warmboot.py in build.yml) and M23 (add 'if: false' to that step): test exits 0 both without and with inputs. Controls: deleting the doc-claims step's own run line (M18), an unwired new test file (M22) and a wrong documented list (M10) are caught.  
   **suggested fix:** Parse only uncommented 'run:' lines of the host-tests job, or state the limitation beside the ci-coverage block.
5. **severity:** minor  
   **description:** docs/CLOUD_CONTINUATION.md says of the correction pass '27 files, all exited 0 in both passes'. By the implementer's own report the second pass had test_pops_external.py exit 1 (link collision from running the passes in parallel) and it passed only when re-run alone; both passes also ran on the uncommitted tree before the three commits.  
   **evidence:** Implementer report tests_run: 'Pass 2 ... 26 exit 0; test_pops_external.py exit 1 at the link step'. Document text added by db36890: 'the list was run again: 27 files, all exited 0 in both passes'. My sequential run at ed30f55 does give 27 of 27 exit 0 both ways, so the end state is true; the description of what was run is not.  
   **suggested fix:** Say '26 of 27 in the second pass plus test_pops_external.py re-run alone', or replace it with a sequential run at the committed head.
6. **severity:** minor  
   **description:** The IGR skin -666 row is incomplete, and S23 forced folder-check results that cannot occur. Run for real, FUN_008d8958 at that call returns only 1 or -666, and on failure it also sets gp+0x3460 = 1 and gp+0x3868 = 1 (and, on mass:, calls 0x91be68 on mass0:/POPS). The audit's open question about gp+0x3868 has a static lead it does not use.  
   **evidence:** My run with FUN_008d8958 executing and only 0x8d7e78 / 0x91bf80 / 0x91be68 modelled: folder missing gives -666, nothing opened, gp+0x38dc, gp+0x3460 and gp+0x3868 each 0 to 1 (4 of 4, both backends); folder present gives return 1, three opens, only gp+0x3868 changes (4 of 4). Disassembly 0x8d8958..0x8d8b10: returns 0 only when gp+0x38dc == 1 or gp+0x3868 == 1, which the caller has already excluded. main calls 0x8d8958 itself at 0x873f9c (unless gp+0x3888 != 0) and sets gp+0x3868 = 1 at 0x87425c, both before the skin call at 0x876b18.  
   **suggested fix:** State the reachable results and the extra flag writes in the section 6 row, and cite 0x873f9c / 0x87425c for when gp+0x3868 is already 1.
7. **severity:** minor  
   **description:** Small test-file defects: MAIN_FUNCTION ends one word too far, and a set but undecodable POPSTARTER_TEST_ELF silently skips the Original class instead of failing.  
   **evidence:** main ends with jr ra at 0x87c210 and its delay slot at 0x87c214; 0x87c218 is the first instruction of the next function (addiu sp,-0x20; it is the jal target at 0x8712cc). The test uses (0x870b78, 0x87c21c); counts are unaffected (295 and 21 either way). The import block catches (Exception, SystemExit) and sets HAVE = False.  
   **suggested fix:** Use 0x87c218 as the end; fail when the variable is set but the image cannot be decoded.

## independent checks

1. Scope: the three commits (85084b1, db36890, ed30f55) change documents, one new test and one workflow step. git diff cfebe01 HEAD -- common launcher tools (minus the new test) is empty, so there is no new C code; I checked the documents' claims about the original and the existing pops_fix_stage instead. All of it is host work (Unicorn 2.1.4, capstone, host gcc, EE gcc). NOT TESTED on a console.
2. My harness is separate from the repo's Machine/Module and from other authors' scripts; only decode_main is reused. It maps 32 MB of EE RAM with the real POPS.ELF segments loaded, plants jr ra at modelled callees, polices stray execution with a block hook and finds memory effects by snapshot diff. memset/memcpy/strlen are native models because the original's versions use R5900 MMI opcodes Unicorn cannot run.
3. $USBDELAY_ handler: disassembly 0x89dbd4..0x89dc60 shows the lbu at 0x89dbe0 and li v0,'$' at 0x89dbe4. Agrees with the audit and inventory.
4. Print-call census with a different pattern (any lw of gp+0x38b0 followed within 3 instructions by any conditional branch past the call): BIOS 14 sites, 2 without (0x8805b4, 0x880984); OSD 41, 3 (0x87eee0, 0x87f27c, 0x87f3a8); IGR 15, 0; TROJAN 20, 1 (0x881cec); main 295, 21; code area 2,031, 145. Identical to S21. No jal to the print routine beyond 0x915000 and no plain j to it.
5. gp+0x38e0 over the whole image, any load/store opcode: 7 lw and 8 sw at exactly the addresses the audit lists.
6. Always-live block (source 0x983150, 0x738 bytes): 60 b+8/nop pairs, 5 at 0x2327d0..0x2327f0 and 55 at 0x232d08..0x232eb8. Agrees with S26.
7. main: fp+0x1108 has writers 0x870ce8 (sw zero) and 0x8712ec and one reader 0x876a90; gp+0x38dc is tested at 0x876a84 and read again at 0x876b20 after jal 0x87e464; v0 is not used. Agrees with S24.
8. IGR skin function 0x87e464, 67 runs, both backends, FUN_008d8958 executing for real. Abort flag set: return 0, nothing opened, no memory or gp change (8 of 8). Size boundary: BG accepted at 0x4c300 and rejected above; NO/YES accepted at 0x1dbc (7,612) and rejected at 0x1dbd; accepted slots equal file plus zero fill; nothing outside the slot changes (48 runs, all return 1). Preset byte 0, 2, 0xff: still three opens, return 1 (3 of 3). Agrees with the audit, except the incompleteness reported as an issue.
9. BIOS handler 0x88019c, 92 runs. Size 0x7ff8e rejected, 0x7ff8f accepted (return 1, file bytes at 0x24bc20, flag gp+0x38a4 or gp+0x3b98, and a call of helper 0x8d6bd0 with (0x1000, 0x20079a), which I modelled, so the halfword write itself was not observed). Game folder missing: -666, gp+0x3460 = 1, gp+0x38e0 = 1, nothing opened (4 of 4). gp+0x38e0 already 1: folder not checked, file loads (4 of 4). Quiet flag set: prints only from 0x8805b4 ('DONE\n') and 0x880984 ('\n'), in 20 of 32 inputs. Gates match section 4. Agrees with S22; the extra -666 exit is the issue above.
10. Wrapper IRX with my own section loader and import models (MIPS32, base 0): device record at 0x588 = 0x430, 0x10, 1, 0x410, 0x544 (name 'pfs'), 17-entry table at 0x544, entry 3 = 0xd4, single DLAY at IRX offset 0x4b0 = EE 0x91fb30. 78 random callback sequences over 13 patch values (unpatched, 0..9, 0x35, 255): thbase 33 called exactly once, at the first open, before the backend ioman open, with n x 1,000,000 or 5,000,000 unpatched (63 of 63 sequences containing an open); no thbase call in sequences with no open (15 of 15). Agrees with S28. No IOP kernel ran; the wait was not observed.
11. Fix-file corpus under REPOP popstarter/ (read-only): 3,952 TROJAN files, 509 distinct; 870 PATCH, 10 distinct. Agrees with S15.
12. Original TROJAN loader 0x880a24 on all 509 distinct files (alternating pfs1/mass, always-live block copied in first): return 1 for 509 of 509; exactly one changed run in 0x100000..0x870000 per file, the slot word going from 10000001 00000000 to a jal; no Invalid/Skipped/FAIL message; 0 stray-execution stops. Slot per file number: 0 0x2327d8, 1 0x2327e0, 2 0x2327e8, 3 0x2327f0, 4 0x232d08, 5 0x232d10, 6 0x232d18, 7 0x2327d0, 8 0x232d20, 9 0x232d28. Identical to the audit's table. No payload was executed.
13. launcHER pops_fix_stage (host gcc build of this worktree's common/src, through ctypes, on the real POPS core bytes): TROJAN returns -3 for 509 of 509 with the core unchanged; PATCH returns 0 for 10 of 10.
14. Original PATCH loader 0x881de8 with the mode routines 0x8db97c..0x8dc9ac executing for real: return 1 for 10 of 10; for all 10 the changed byte runs and their values equal launcHER's. The 327,360-byte PATCH_5 changes 0x2feff4..0x34ee6c, inside the three skin slots; a PATCH_6 changes halfword 0x2525b0; no PATCH run falls in 0x262b80..0x2afc20. Agrees with S27.
15. REPOP read-only: origin/main = bc258e48; the pr23 worktree branch was created from it at 04:26:42, first local commit cdbfeb9d at 06:25:53, 0a440b01 is its sixth commit. It has moved again since the audit was written: now 10 commits ahead (6f7f638b) and clean, consistent with 'not a stable reference'. I did not re-run parity_report.py.
16. Workflows: at cfebe01 26 test files, 23 named in build.yml, test_launch_args.py in launch-args.yml; at HEAD 27 files and 24 build.yml steps; eight test files reference build/pops-host and they are the eight the document names. Agrees with S29 and CLOUD_CONTINUATION.
17. EE check: no C file changed, so nothing new to compile. I re-ran the documented resident-image recipe with ps2build's mips64r5900el-ps2-elf-gcc 15.3.1: gcc exit 0, objcopy exit 0, 6,688 bytes, tools/check_pops_resident_image.py 12 PASS lines, exit 0. Not built: the launcHER ELF, any IRX, the CMake project, the container build.
18. Hygiene: no assistant attribution in the three commit messages or added lines (the only hit is an existing REPOP branch name in the S18 row); tools/test_pops_doc_claims.py has no hex run of 24 or more digits, only single instruction words and addresses; docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md and docs/PR23_CHECKPOINT_HISTORY.md untouched; new test is the first step of host-tests and passes without inputs. Worktree left at ed30f55, git status clean (only ignored build/).

## mutants

1. No C code was added, so mutants are single-line changes to the documents and workflow that the new test reads. They were applied to a git-archive copy of HEAD in scratch, never to the worktree. Baseline green before and after. 23 mutants: with the reference input 11 caught, 12 survived; without it 5 caught.
2. M01 audit cites handler 0x89dbe4 (audit only): CAUGHT both ways.
3. M02 audit and inventory both cite 0x89dbe4: CAUGHT both ways (a third citation in the audit's S25 row still differs).
4. M03 S28 fallback argument 5,000,000 -> 1,000,000: survived without inputs, CAUGHT with.
5. M04 section 4: BIOS game-folder exit 'returns -666' -> 'returns 0': SURVIVED both ways.
6. M05 section 6: IGR 'returns -666' -> 'returns -1': survived without, CAUGHT with.
7. M06 inventory IGR row 'returns 0' -> 'returns 1' with the abort flag set: SURVIVED both ways (inventory text is not checked).
8. M07 README 'uses 1 second' -> 'uses 5 seconds': SURVIVED both ways (README is checked only for withdrawn phrases).
9. M08 audit slot table, file number 4 0x232d08 -> 0x232d30: SURVIVED both ways.
10. M09 audit '509 of 509 return 1' -> '508 of 509': SURVIVED both ways (the corpus is outside the test; expected).
11. M10 continuation: test_pops_progressive.py removed from the no-workflow list: CAUGHT both ways.
12. M11 build.yml: run line of test_pops_warmboot.py commented out: SURVIVED both ways.
13. M12 S21 '2,031, 145 without' -> '144': survived without, CAUGHT with.
14. M13 S21 'TROJAN loader: 20, 1 without' -> '20, 2 without': SURVIVED both ways.
15. M14 gp+0x38b0 row: 0x880984 -> 0x880978: SURVIVED both ways.
16. M15 section 4: 'always leaves gp+0x38e0 = 1' -> '= 0': SURVIVED both ways.
17. M16 section 9: delay called 'once, on that entry's first call' -> 'on every call': SURVIVED both ways.
18. M17 S24: 'main reads gp+0x38dc, not the return value' flipped: SURVIVED both ways.
19. M18 build.yml: the doc-claims step's own run line replaced by 'echo skipped': CAUGHT without inputs (not run with).
20. M19 section 12 'holds 60 such pairs' -> '59': survived without, CAUGHT with.
21. M20 inventory '(5,000,000 if unpatched)' -> '1,000,000': SURVIVED both ways.
22. M21 not run.
23. M22 a new tools/test_new_thing.py wired into no workflow: CAUGHT without inputs (not run with).
24. M23 build.yml: 'if: false' added to the warmboot step: SURVIVED without inputs (not run with).

## tests rerun

1. All 27 tools/test_*.py at ed30f55, run sequentially in the worktree with TMP/TEMP isolated, pass 1 without reference inputs, then pass 2 with POPS_TEST_ELF and POPSTARTER_TEST_ELF. Every file exited 0 in both passes.
2. Pass 1 (no inputs), tests/skipped: breakpoint 11/4, builtin_db 14/14, display 21/6, doc_claims 12/7, external 128/14, features 29/2, fix_files 31/3, io_probe 6/0, launch_hooks 46/13, module_irx 11/4, opcodes 9/3, padman 6/3, progressive 8/5, read_trace 9/0, resident 75/12, runtime_corrections 8/0, startup_calls 6/0, warmboot 7/3. Script-style files exit 0: launch_args, network_transports, popfs, pops_fatfs, pops_modes, pops_vmc, smap_ipconfig, sony_ioman_layout, subq_bridge.
3. Pass 2 (with inputs), tests/skipped: breakpoint 11/0, builtin_db 14/0, display 21/0, doc_claims 12/0, external 128/3, features 29/0, fix_files 31/0, io_probe 6/0, launch_hooks 46/3, module_irx 11/0, opcodes 9/0, padman 6/0, progressive 8/3, read_trace 9/0, resident 75/0, runtime_corrections 8/0, startup_calls 6/0, warmboot 7/0. The nine script-style files exit 0. The remaining skips need POPS_EE_CC / POPS_RESIDENT_BIN / POPS_TRAMPOLINE_BIN, which I did not set for these passes.
4. tools/test_pops_doc_claims.py on the would-be merge of HEAD with codex/popstarter-replacement (tree from git merge-tree, extracted to scratch, 28 test files): 12 tests, 7 skipped, OK without inputs; 12 tests, 0 skipped, OK with.
5. Resident image by the recipe in docs/CLOUD_CONTINUATION.md with EE GCC 15.3.1: exit 0, 6,688 bytes, checker 12 PASS, exit 0. The trampoline was not assembled and the three files were not re-run with POPS_EE_CC / POPS_RESIDENT_BIN / POPS_TRAMPOLINE_BIN, so the implementer's '46 tests, 0 skipped' result for launch_hooks is not re-verified.

## unsupported claims

1. docs/CLOUD_CONTINUATION.md: 'the list was run again: 27 files, all exited 0 in both passes'. The implementer's own run had test_pops_external.py exit 1 in the second pass (parallel-run link collision) and pass only on a separate re-run, and both passes preceded the commits. The end state is true (my sequential run at ed30f55: 27 of 27 both ways).
2. Audit section 2a: the test 'recomputes S21, S25, S26, the static parts of S23, S24 ... repeats the wrapper run of S28, and compares each with the wording of this document'. The recomputation is real, but the comparison is by presence of a few phrases: flipped S24 and section 9 sentences, a wrong TROJAN-loader count and a moved BIOS print site all pass.
3. Commit ed30f55 and the audit: '13 of 13 fail with the reference input'. True only of the implementer's own 13 mutants (I counted 13 entries in their script and did not re-run it). Of my 23, 12 survive with the reference input.
4. Commit 85084b1: 'the BIOS handler's game-folder once-flag gp+0x38e0 and its -666 exit'. The handler has three -666 stores (0x880378, 0x880558, 0x8805a4); the POPS-folder exit at 0x880378 for the all-games scope is not described anywhere in section 4 or S22.
5. Audit section 6 and S23: the -666 path is supported only with FUN_008d8958's result forced to 0, 2 or -1, values that call cannot return. The row's conclusion holds (my run with the real check: -666, 4 of 4), but it leaves out that the check also sets gp+0x3460 and gp+0x3868.
6. CLOUD_CONTINUATION calls the CI coverage list one the test 'compares with the workflow files and fails when they disagree'. It does not fail when a step is commented out or disabled with 'if: false'.
7. Not re-verified by me, so still resting on the implementer's word: the parity_report.py figures on a clean export of bc258e48 (466 / 138,664 / 434 / 93.1% / 90.2%); the exact S22 and S23 run counts (their inputs differ from mine; the behaviour agrees); the launch_hooks/progressive/external results with hand-built EE images; and every row the audit itself marks as not re-derived (OSD handler, physical disc, XX./SB. scan, SMB parsers, launch-type parser, sections 11 and 13, the section 12 rule-difference table).
8. Everything above is host emulation with file, folder and print calls modelled. No statement in these commits or in this review is a console result.
