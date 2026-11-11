# Gap audit and status documents: review 1

Written by an independent reviewer of the track. Copied as written.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## verdict

issues

## issues

1. **severity:** minor  
   **description:** Hygiene check 'shared docs listed as off-limits untouched' fails literally: the commit edits four of the six files the generic track rules say not to edit (docs/POPSTARTER_R13_INVENTORY.md, docs/CLOUD_CONTINUATION.md, README.md, docs/pops-setup.html). docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md and docs/PR23_CHECKPOINT_HISTORY.md are untouched. The commit's stated job is 'status-doc truth-up', so this may be the docs track's mandate; I cannot verify that from the worktree. Rated minor only because of that; if the docs track was not authorised to own these files this is a process violation the lead must resolve.  
   **evidence:** git show --stat 3d42449 in the docs worktree: 8 files, +1081/-55: README.md, docs/CLOUD_CONTINUATION.md, docs/POPSTARTER_GAP_AUDIT_2026-11-11.md (new), docs/POPSTARTER_LAUNCH_HOOKS.md, docs/POPSTARTER_R13_INVENTORY.md, docs/POPS_PARITY_AUDIT_2026-10-28.md, docs/history/CLOUD_CONTINUATION_2026-10-28_UNVERIFIED.md, docs/pops-setup.html. No file under common/, launcher/, tools/ or .github/ changed.  
   **suggested fix:** Lead confirms the docs track owns these four files for this round and merges it before applying other tracks' doc_updates text to the same files (inventory rows, README notes), otherwise conflicts or silent overwrites are likely.
2. **severity:** minor  
   **description:** Claim about another checkout is stale and was already false at commit time: the audit (S18 and section 17) and docs/CLOUD_CONTINUATION.md say the worktree REPOP.worktrees/pr23 is at origin/main bc258e48 and tell the reader to 'Use the worktree REPOP.worktrees/pr23'. That worktree is on branch pr23/popstarter-batch26 with newer commits; following the instruction gives different parity_report numbers than the ones the audit quotes.  
   **evidence:** git -C REPOP: log: cdbfeb9d 2026-11-11 06:25, e161e957 06:33, now 0a440b01 07:30 on branch pr23/popstarter-batch26; docs commit 3d42449 is 06:28:19. parity_report in that worktree at e161e957 printed 440 / 94.4% / 91.2%. I exported bc258e48 with git archive into my scratch directory and ran python tools/parity_report.py popstarter there: 466 / 138,664 / 434 / 93.1% / 90.2%, which matches the audit, so the numbers are right for bc258e48 only.  
   **suggested fix:** Drop 'the worktree is at that commit' and 'use the worktree'; say 'a clean checkout of REPOP main at bc258e48' and label the worktree state as volatile.
3. **severity:** minor  
   **description:** Section 3a of docs/POPSTARTER_GAP_AUDIT_2026-11-11.md says every banner printf is skipped while gp+0x38b0 is 1. In my runs of the BIOS.BIN handler 0x88019c with gp+0x38b0=1 the printf stub at 0x915708 was still called (a newline and a 'DONE' line), so 'every' is too strong.  
   **evidence:** Own unicorn harness (<scratch>/docs-r1-review/t_bios.py, t_bios2.py), 48 cases; printf calls recorded with the quiet flag set.  
   **suggested fix:** Say 'most banner printfs' or list the ungated ones.
4. **severity:** minor  
   **description:** Section 6 says of the IGR skin function 0x87e464 'no outcome is fatal; the function returns 1'. With gp+0x38dc set it returns 0. Section 4 also does not mention that the BIOS.BIN handler's scope-1 path writes gp+0x38e0=1.  
   **evidence:** Own unicorn run of 0x87e464 (t_igr.py, 22 cases): return value 1 in all cases with gp+0x38dc=0, 0 with gp+0x38dc=1. BIOS run memory diff shows gp+0x38e0 changed to 1 in the scope-1 cases.  
   **suggested fix:** Add the gp+0x38dc return value and the gp+0x38e0 write, or label them not examined.
5. **severity:** minor  
   **description:** Handler address for $USBDELAY_ is given two ways: S14 says 0x89dbe0, section 9 and docs/POPSTARTER_R13_INVENTORY.md say 0x89dbe4.  
   **evidence:** Disassembly: the block starts at 0x89dbd4 and the '$' compare sits at 0x89dbe0/0x89dbe4; tools/popstarter_r13_commands.py prints 0x89dbe0.  
   **suggested fix:** Use one address (the tool's 0x89dbe0) everywhere.
6. **severity:** minor  
   **description:** Ranked increment 2 speaks of 'fifteen call slots' while section 12 says 'ten fixed call slots, one per file number'; the fifteen is not defined anywhere in the audit.  
   **evidence:** docs/POPSTARTER_GAP_AUDIT_2026-11-11.md line 496 versus line 699. My corpus census and emulation confirm ten slots (0x2327d0..0x2327f0 and 0x232d08..0x232d28) hooked by TROJAN_0..9.  
   **suggested fix:** Define the other five slots or say ten.
7. **severity:** minor  
   **description:** docs/CLOUD_CONTINUATION.md says CI's host-tests job runs 23 of the 26 test files and that test_launch_args.py is not a step there. True for that job, but test_launch_args.py does run in CI through .github/workflows/launch-args.yml, so 24 of 26 run in CI; only test_pops_builtin_db.py and test_pops_progressive.py run nowhere.  
   **evidence:** .github/workflows/build.yml host-tests job has 23 test steps; .github/workflows/launch-args.yml runs python tools/test_launch_args.py on push and pull_request.  
   **suggested fix:** Add the launch-args workflow to the sentence.
8. **severity:** minor  
   **description:** README.md line 688 and docs/pops-setup.html line 306 say, as 'read from its code', that POPStarter 'delays inside its USB/SMB file driver on first use'. The audit section 9 labels the nature of that delay (that the import is a thread delay and that the caller is the open path) as 'inferred'. The user pages state it one notch more firmly than the audit does.  
   **evidence:** docs/POPSTARTER_GAP_AUDIT_2026-11-11.md line 310 versus README.md:688. My own static read of 0x879d04..0x879e58 confirms only the EE side: when gp+0x3448 is nonzero the DLAY word at 0x91fb30 is replaced by the preset byte and three zeros. I did not run the IOP wrapper.  
   **suggested fix:** Say 'appears to delay once inside the file wrapper used for USB/SMB' or carry the 'inferred' qualifier.
9. **severity:** minor  
   **description:** The audit lists as not examined whether PATCH payloads write inside the IGR skin slots. One corpus file does: PATCH_5.BIN of 327,296 bytes loads at 0x2feff0 and ends at 0x34ee70, covering all three skin slots, and launcHER's pops_fix_stage accepts it. So IGR pictures can already change through a PATCH file; the README line 'Custom IGR graphics: not implemented' is true only for the three TM2 files it names.  
   **evidence:** Own corpus census over REPOP:popstarter/ (870 PATCH files, 10 distinct) and own ctypes build of common/src: PATCH result 0 for 10/10.  
   **suggested fix:** Add one sentence to section 15 and, if wanted, to the README note.

## independent checks

1. Scope: commit 3d42449 changes 8 documentation files only (no C, no tests, no workflow). All re-derivations below used my own scripts under <scratch>/docs-r1-review/ (rvemu.py, rvlib.py, t_*.py, corpus*.py, census.py, igrscan.py, preset.py). Everything is host emulation (unicorn) or host gcc via ctypes. NOT TESTED on a console, not run in an emulator of the whole machine.
2. Static spot checks S1..S13 re-derived from the binaries: packed MAIN 167,700 bytes, unpacked 1,350,828 bytes at 0x870000, hashes, the four profiles differing only at file offsets 0x410 and 0x413, one DLAY occurrence at 0x91fb30, BIOS size-test instructions, caller lists, IGR size immediates, the four function sizes summing to 597,012 and the 17.0% arithmetic, TIM2 headers, gp flag reader counts. All match the audit.
3. BIOS.BIN handler 0x88019c, own unicorn run, 48 cases: accepted exactly when the signed size is above 0x7ff8e (0x7ff8e rejected, 0x7ff8f accepted, negative rejected); reads 0x7ff90 bytes to 0x24bc20; the only other core change is halfword 0x20079a = 0x1000; flags gp+0x38a4 / gp+0x3b98 as documented; folder paths as documented; missing game folder returns -666. Matches section 4.
4. IGR skin function 0x87e464, own run, 22 cases: BG accepted up to 0x4c300 bytes and rejected at 0x4c301; NO/YES accepted up to 0x1dbc and rejected at 0x1dbd; slot becomes file plus zeros; zero-length file wipes the slot; nothing outside the three slots changes; literal pfs1:/POPS/ or mass:/POPS/ paths. Matches section 6 except the return value when gp+0x38dc is set (issue above).
5. Fix-file corpus census (own code): 3,952 TROJAN files / 509 distinct, 870 PATCH / 10 distinct; 507 format 1 and 2 format 3; load addresses 0x1431000..0x1470300, none inside the core; hook slot per file number as tabulated. Matches section 12.
6. Original TROJAN loader 0x880a24, own unicorn run over all 509 distinct files: 509/509 return 1, payload written at its load address, slot word becomes a jal to the entry, no 'Invalid' message. Original PATCH loader 0x881de8 accepts 10/10. This independently confirms the audit's headline claim that the original accepts all 509, which the audit labels measured once and under re-verification; it can now be labelled measured twice.
7. launcHER pops_fix_stage through my own ctypes build of common/src: TROJAN result -3 for 509/509 with no core change; PATCH result 0 for 10/10. handler_pops.c:316-318 returns the error, so a rejected file ends the launch. Matches the README and inventory wording.
8. Rule-difference table of section 12 re-checked on the original with synthetic files: an invalid file is skipped and the next slot still loads; formats 1/2/3 accepted and 0/4 invalid for TROJAN; format 2 writes a j instead of a jal for small header values; format 3 'Skipped (outdated)' path; PATCH formats 2/3 invalid; entry outside payload, odd payload size and PATCH payload outside the core all accepted. All as documented.
9. Config text rules (section 13) run on the original parser 0x883270 and on launcHER's pops_config_load_file with the same 19 probe texts: commands recognised after '#', ';' or a letter in the original and ignored by launcHER; '$SMOOTH$SCANLINES' and TAB separation differ as documented; $NOBOOT, $BIOS, '$MODE 3' do nothing in the original; $USBDELAY_ takes one digit plus terminator and writes 0x100017, default 1; launcHER accepts 12 and the no-underscore form, default 0. Matches.
10. VMCDIR.TXT rules run on the original reader 0x8d4f84 and on launcHER's pops_config_load_vmcdir with 11 texts (CRLF, slash, backslash, colon, second line, 103 and 104 bytes, spaces, empty). Differences are as documented.
11. Region pass 0x879034..0x8795f0, own flagged-versus-unflagged run: 6 licence values x 8 combinations of three other flags x 6 flags. Known licence: only the 4 bytes at 0x2649a0 are skipped. Unknown licence: 0x264994..0x2649a3 skipped plus the single bytes 0x20f6cc/d8/dc/e0 in every combination where the unflagged run writes them. gp+0x343c and gp+0x3878 alone skip nothing. The four flags gp+0x3b98, 0x38a4, 0x344c, 0x3430 behaved identically in all 48 combinations. Matches section 5a. I did not map my three varied flags to the named commands.
12. Static scan of every lui+ori / lui+addiu address construction: all 33 sites building 0x228a20..0x228a6b lie inside the $IGR0..5 / $NOIGR handlers; 0x20c0a4, 0x2362fc and 0x200794 are each built at one site. Supports the default-IGR and one-writer statements.
13. launcHER file:line citations at cfebe01: about 70 cited lines in handler_pops.c, pops_config.c, pops_modes_patches.c, pops_external.c, launch_args.c, handler_smb.c, network_config.c, main.c, popfs.c, pops_resident_engine.c and test_pops_launch_hooks.py were opened and matched the audit's description, including the $USBDELAY sleep at handler_pops.c:1751-1753 after the IOP reset at :1665.
14. REPOP citations at bc258e48 hold; parity_report on a git-archive export of bc258e48 prints 466 / 138,664 / 434 / 93.1% / 90.2% as the audit says.
15. Test numbers in docs/CLOUD_CONTINUATION.md match my runs: 26 test files, all exit 0 in both passes; with reference inputs exactly three files skip three tests each (test_pops_launch_hooks.py, test_pops_progressive.py, test_pops_external.py).
16. Hygiene: no payload bytes or long hex tables in the new document; no AI attribution or co-author trailer in the commit or the changed files (the commit author is the repository owner); the three withdrawn-instruction notes are present; working tree clean at 3d42449 at the end (git status --short empty).
17. Not re-derived by me: the OSD.BIN handler, the physical-disc block, the XX./SB. device scan, the SMB config parsers, the launch-type parser, the IOP-side delay wrapper, and most statements labelled 'read' in section 10. Those rest on the audit's own labels.

## mutants

1. None applied. The commit contains no C code and no test code (8 documentation files only), and no test in tools/ reads files under docs/ or README.md, so there is no code to mutate and no test that could catch a documentation mutant. The required four mutants are not applicable to this commit.

## tests rerun

1. Pass 1, no reference inputs, all 26 tools/test_*.py: every file exit code 0. Skips: test_pops_breakpoint 4 of 11, test_pops_builtin_db 14 of 14, test_pops_display 6 of 21, test_pops_external 14 of 128, test_pops_features 2 of 29, test_pops_fix_files 3 of 31, test_pops_launch_hooks 13 of 46, test_pops_module_irx 4 of 11, test_pops_opcodes 3 of 9, test_pops_padman 3 of 6, test_pops_progressive 5 of 8, test_pops_resident 12 of 75, test_pops_warmboot 3 of 7. No skips in test_launch_args, test_network_transports, test_popfs, test_pops_fatfs, test_pops_io_probe, test_pops_modes, test_pops_read_trace, test_pops_runtime_corrections, test_pops_startup_calls, test_pops_vmc, test_smap_ipconfig, test_sony_ioman_layout, test_subq_bridge.
2. Pass 2, with POPS_TEST_ELF and POPSTARTER_TEST_ELF, all 26 files: every file exit code 0. Remaining skips: test_pops_external 3 of 128, test_pops_launch_hooks 3 of 46, test_pops_progressive 3 of 8 (all need built EE images or an EE compiler on PATH). All other files 0 skipped.
3. EE compile check: no C file changed in the commit. I re-ran the resident-image recipe that docs/CLOUD_CONTINUATION.md documents: EE GCC 15.3.1 compiled with exit code 0, image 6,688 bytes, checker printed 12 PASS lines and exited 0. This matches the document. No full PS2 target build was run.
4. All of the above are host results. NOT TESTED on a console.

## unsupported claims

1. Audit S18 / section 17 and docs/CLOUD_CONTINUATION.md: 'the worktree REPOP.worktrees/pr23 is at bc258e48' and 'use the worktree'. False at commit time and now (worktree is on pr23/popstarter-batch26 with later commits and prints different parity numbers). The numbers quoted are right only for a clean bc258e48.
2. Audit section 3a: 'every banner printf is skipped while gp+0x38b0 is 1'. My runs show ungated printf calls in the BIOS.BIN handler.
3. Audit section 6: 'the function returns 1' for the IGR skin function. It returns 0 when gp+0x38dc is set.
4. README.md:688 and docs/pops-setup.html:306: POPStarter 'delays inside its USB/SMB file driver on first use', presented as read from its code. The audit itself labels the delay import and the calling path as inferred; neither the implementer nor I executed the IOP wrapper.
5. docs/CLOUD_CONTINUATION.md: the sentence on CI coverage implies test_launch_args.py is not run by CI. It is, by .github/workflows/launch-args.yml; 24 of 26 files run in CI, not 23.
6. Audit increment 2: 'fifteen call slots' has no support in the audit; section 12 and my runs show ten.
7. Labels of '2x' on statements about the OSD.BIN handler, the physical-disc block, the device scan and the SMB parsers were not re-derived by me; I can neither confirm nor refute the second measurement for those.
8. Understated rather than overstated: 'the original accepts all 509 TROJAN files' is labelled measured once / under re-verification in the audit, README and inventory. My independent run confirms it (509/509), so the label can be raised.
