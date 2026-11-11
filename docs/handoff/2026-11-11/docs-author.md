# Gap audit and status documents: author's report

Written by the track's author when the stage ended. Copied as written; not re-verified.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## summary

Docs track finished: one local docs-only commit (3d42449) on branch pr23/docs in the docs worktree. Nothing pushed, no PR touched, no console or emulator used, no code file changed.

What was written:
1. New docs/POPSTARTER_GAP_AUDIT_2026-11-11.md (770 lines, 19 sections). Per area it gives the original's behaviour with addresses, launcHER's behaviour with file:line (at cfebe01), the gap, a label on every statement (2x = two independent runs, 1x = measured once, read, inferred), whether it is host-verifiable, the critic's not-examined list, settled contradictions, and a 16-item ranked increment list. Where the critic marked a feature report wrong (region-pass skips, folder for new files) the critic's version is the one written. Everything that comes only from the device/file report (06, never seen by the critic) is labelled 1x at best. Section 2 lists the 19 spot checks I made myself (S1..S19).
2. docs/POPSTARTER_R13_INVENTORY.md corrected: $UNDO_, default IGR, $USBDELAY_n, $NOBOOT paragraph, region paragraph, POPS package, launch paths, SMB, rename messages, config locations, VMCDIR.TXT, TROJAN/PATCH, IGR skin, OSD.BIN, BIOS.BIN, physical disc; ten new rows; "Remaining work" item 4 replaced by a 13-step list. Three rows went PRESENT -> PARTIAL (POPS package, config locations, VMCDIR.TXT); none was upgraded. A pre-existing table row that was split over two lines ($RESET_WARMBOOT) was joined.
3. docs/CLOUD_CONTINUATION.md: new "Current state - 2026-11-11" section at the top (heads, local verification recipe, three test tiers, ranked next work, the 2026-11-11 test result); older sections retitled "Historical"; nothing deleted.
4. REPOP links changed from feat/psxcore-validation to main in 4 places: docs/CLOUD_CONTINUATION.md (2: POPSTARTER_CONTINUATION.md link in "Recovered cutoff", POPSTARTER_FP_CONTRACTS.md link in the R28 section) and docs/POPS_PARITY_AUDIT_2026-10-28.md (2: lines 38 and 54). Plain-text mentions of the branch in historical paragraphs were left. docs/PR23_CHECKPOINT_HISTORY.md:97 links are pinned to commit 15b8727f and were left.
5. Instructions asking for an AI co-author trailer removed/corrected in 3 places: docs/POPS_PARITY_AUDIT_2026-10-28.md line 60; docs/history/CLOUD_CONTINUATION_2026-10-28_UNVERIFIED.md line 10 and line 153 (now 155). Each is replaced by a dated note that the instruction is withdrawn. docs/CLOUD_CONTINUATION.md now states the no-attribution rule near the top.
6. Additional corrections I judged necessary for accuracy (within docs/ and README.md): README.md and docs/pops-setup.html told users IGR_*.TM2 skins and TROJAN files work; skins are not implemented and community TROJAN files currently stop the launch, so both pages now say so, and also describe $USBDELAY, $NOBOOT/$BIOS and PATCHES.TXT/MODES.TXT as what they are. docs/POPSTARTER_LAUNCH_HOOKS.md got a dated note on the region-pass skips and on fix-file/command order.

Most important finding carried into the docs: every unique TROJAN_n.BIN in the community fix-pack corpus (509) loads outside the POPS core; launcHER's pops_fix_stage returns -3 for all of them (I re-measured this on a host, so launcHER's side is 2x), and handler_pops.c:316-318 ends the launch on a rejected fix file (read). That the ORIGINAL accepts all 509 is measured once (report 06 only) and is labelled "measured once and under re-verification" everywhere. NOT TESTED on a console. New precise detail found while checking: the header parser accepts these files; the rejection is the window pops_fix_stage passes (common/src/pops_modes_patches.c:387-388, core only) to window_offset (common/src/pops_external.c:138-144). The manual check_corpus option of tools/test_pops_external.py plans the same files against 0x100000..0x2000000, which is why older "corpus passes" notes exist.

One mapping-report error corrected in the audit: launcHER's $USBDELAY sleep is after the IOP reset (handler_pops.c:1753 vs SifIopRebootBuffer at :1665), not before.

Things seen but not changed (outside my allowed files or other repositories): launcher/iop/smbman/README.md:15 and launcher/iop/smbman/SMB-NOTICES.txt:10 carry an existing "ChatGPT/OpenAI assistance" credit line; REPOP docs/POPSTARTER_CONTINUATION.md line 256 still asks for an AI co-author trailer; REPOP docs/CONFIG_TABLE.md has three wrong preset rows. The REPOP worktree REPOP: showed uncommitted source changes (patch_engine.c/.h, runtime_hooks.c/.h, runtime_symbols.ld) late in this session and an ignored build/popstarter_unpacked.bin; I only read from that worktree, so those are another track's.

## commits

1. 3d42449813ee5d00242beb7afddf9eb75d265c00 docs(pops): POPStarter r13 gap audit and inventory truth-up (2026-11-11)  [local only, branch pr23/docs, parent cfebe01, not pushed, no attribution trailer]

## files changed

1. docs/POPSTARTER_GAP_AUDIT_2026-11-11.md (new, 770 lines)
2. docs/POPSTARTER_R13_INVENTORY.md
3. docs/CLOUD_CONTINUATION.md
4. docs/POPS_PARITY_AUDIT_2026-10-28.md
5. docs/history/CLOUD_CONTINUATION_2026-10-28_UNVERIFIED.md
6. docs/POPSTARTER_LAUNCH_HOOKS.md
7. docs/pops-setup.html
8. README.md

## measured evidence

1. S1 file identity: packed MAIN 167,700 bytes sha256 734c813e...; unpacked by tools/trace_original_pops_io.py:decode_main to 1,350,828 bytes sha256 185177c2... (1 file, matches the inventory header)
2. S2 preset block: file bytes 0x408..0x42f compared across the 4 POPSLoader profiles (MAIN, DEBUG, USBDELAY, USBDELAY_DEBUG, all 167,700 bytes): they differ only at 0x410 (00/ff) and 0x413 (02/06); byte 0x417 ($USBDELAY) is 1 in all four
3. S3 'DLAY' byte string: exactly 1 occurrence in the unpacked image, at 0x91fb30
4. S4 BIOS.BIN size test: disassembled 0x880894..0x8808a0 = lui 7 / ori 0xff8e / slt / beqz (accept only when size > 0x7ff8e)
5. S5 pristine POPS.ELF words read at 10 addresses (0x200794=03a0202d, 0x200798=14400005, 0x2525b0=0ff01bfc, 0x228a20=30a30904, 0x228a50=24020904, 0x228a5c=3c110086, 0x228a60=24030080, 0x263c28=0c00fa0c, 0x2362fc=0808bb10, 0x21a63c=0)
6. S6 jal callers: scanned 0x870000..0x91ef00 for jal to 13 functions; each caller list matches the mapping reports (e.g. 0x87e464 <- 0x876b18 only; 0x88019c <- 0x876cd8, 0x876fd8; 0x87eb24 <- 0x876bac, 0x876ea0; 0x880a24 <- 0x876d6c, 0x877078; 0x883270 <- 0x8771ac, 0x87724c; 0x87cf68 <- 0x8743d8)
7. S7 IGR skin size limits: 0x87e5b8/0x87e5bc lui 4 / ori 0xc300; 0x87e7dc and 0x87e9e8 slti 0x1dbd (3 sites)
8. S8 four functions missing from REPOP ground truth: prologue and epilogue checked for 0x870b78, 0x883270, 0x8e00d0, 0x8ff0e4; sizes 46,752 + 335,124 + 126,996 + 88,140 = 597,012 bytes; 125,048 / (138,664 + 597,012 - 968) = 17.0%
9. S9 Sony TIM2 files inside POPS.ELF at the 3 skin slots: 0x2feff0 400x260 total 0x4c300; 0x34b2f0 and 0x34d0b0 74x34 total 7,612 bytes; next TIM2 at 0x34ee70 (limits in the original equal Sony's file sizes)
10. S10 argv 'cdrom' exit: immediates in 0x871328..0x8713c4 spell cdrom; 0x8713c4 li v1,4 / syscall (static read, 1 block)
11. S11 gp-relative flag readers/writers counted by scanning lw/sw: gp+0x3b98 16 readers 2 writers; gp+0x38a4 16 readers 2 writers; gp+0x3410 8 readers 10 writers; gp+0x3448 3 writers
12. S12 immediate 0x079a (the 0x20079a poke) occurs at exactly 2 sites: 0x8800a0 (OSD handler) and 0x8809a0 (BIOS handler)
13. S13 $USBDELAY consumer: 0x879d84/0x879da4/0x879dc4/0x879de4 load 'D','L','A','Y' (4 instructions)
14. S14 command census: python tools/popstarter_r13_commands.py on MAIN prints 72 lines; none contains NOBOOT or BIOS; $USBDELAY_ handler writes byte 0x100017 = 0..9; the 3 $UNDO_ handlers list w16[0x2525b0]=0x1bfc
15. S15 fix-file corpus headers (every TROJAN_n.BIN / PATCH_n.BIN under REPOP popstarter/): 3,952 TROJAN files, 509 unique; 870 PATCH files, 10 unique; 0 of 509 unique TROJAN payloads lie inside the core window 0x200000..0x502e60 (load 0x1431000 .. end 0x152c3c0); 507 format 1, 2 format 3; hook address per slot number as tabulated in the audit
16. S16 launcHER side of the corpus, re-measured by me: pops_fix_stage built from cfebe01 sources with host gcc, each unique file on a fresh pristine core: TROJAN -> -3 for 509 of 509; PATCH -> 0 for 10 of 10. The ORIGINAL loader was NOT re-run by me; 'the original accepts all 509' remains measured once (mapping report 06)
17. S17 launcHER source references: about 45 file:line citations re-checked with grep/sed at cfebe01 (handler_pops.c 50, 153, 161-186, 282-326, 317, 747, 824, 870-884, 1419, 1450, 1456-1457, 1480-1484, 1492, 1508, 1665, 1753; pops_config.c 319, 479-486, 931, 956; pops_modes_patches.c 387-388, 1279-1299, 1554, 1579; pops_external.c 104-106, 138-144, 162-169; launch_args.c 93, 549, 633-694; handler_smb.c 52-54; pops_resident_engine.c 316, 341; main.c:56). Absent by grep in common/ and launcher/ sources: __common, IOPRP.IMG, numbered POPS folders, TM2/IGR_BG, 0x200794, 0x20079a
18. S18 REPOP state (read-only): worktree HEAD = origin/main = bc258e48; feat/psxcore-validation d3452068 is an ancestor of the branch squash-merged as 0d5ca939; python tools/parity_report.py popstarter prints 466 functions / 138,664 bytes / 434 claimed / 93.1% / 90.2%; README 67.5% figure, main.c:1225-1236 'done flag' comment, ForceFunctions.java HARD_OVERSIZE=32768 and the co-author line at docs/POPSTARTER_CONTINUATION.md:256 all read and confirmed
19. S19 correction: launcHER's $USBDELAY sleep is at handler_pops.c:1753, after SifIopRebootBuffer at :1665 (one mapping report said 'before the IOP reset')
20. PR state (read-only, gh pr view 23): draft, head cfebe01e, title unchanged; its 'Still open' item 5 still links REPOP feat/psxcore-validation
21. Docs self-check: a throwaway script found consistent column counts in every markdown table of the 7 changed .md files and no broken relative links; one pre-existing split table row in the inventory was found this way and joined
22. No test or CI step reads docs/ or README.md (grep of tools/test_*.py and .github/workflows), so the documentation edits cannot change test outcomes
23. Host test list: 26 files x 2 passes = 52 runs, 52 exit code 0, no traceback in any log (details in tests_run)

## tests run

1. **command:** python tools/test_launch_args.py (pass 1: no reference inputs; pass 2: POPS_TEST_ELF + POPSTARTER_TEST_ELF set)  
   **outcome:** rc=0 both passes; prints 'Launcher argv compatibility PASS'
2. **command:** python tools/test_network_transports.py (both passes)  
   **outcome:** rc=0 both passes; SMB and UDPFS contract lines PASS
3. **command:** python tools/test_popfs.py (both passes)  
   **outcome:** rc=0 both passes
4. **command:** python tools/test_pops_breakpoint.py (both passes)  
   **outcome:** no refs: Ran 11, OK (skipped=4); with refs: Ran 11, OK, 0 skipped
5. **command:** python tools/test_pops_builtin_db.py (both passes)  
   **outcome:** no refs: Ran 14, OK (skipped=14, i.e. nothing compared); with refs: Ran 14, OK, 0 skipped
6. **command:** python tools/test_pops_display.py (both passes)  
   **outcome:** no refs: Ran 21, OK (skipped=6); with refs: Ran 21, OK, 0 skipped
7. **command:** python tools/test_pops_external.py (both passes)  
   **outcome:** no refs: Ran 128, OK (skipped=14); with refs: Ran 128, OK (skipped=3: the three progressive tests that need an EE compiler, 'optional EE compiler and original MAIN')
8. **command:** python tools/test_pops_fatfs.py (both passes)  
   **outcome:** rc=0 both passes; prints PASS
9. **command:** python tools/test_pops_features.py (both passes)  
   **outcome:** no refs: Ran 29, OK (skipped=2); with refs: Ran 29, OK, 0 skipped
10. **command:** python tools/test_pops_fix_files.py (both passes)  
   **outcome:** no refs: Ran 31, OK (skipped=3); with refs: Ran 31, OK, 0 skipped
11. **command:** python tools/test_pops_io_probe.py (both passes)  
   **outcome:** Ran 6, OK in both passes
12. **command:** python tools/test_pops_launch_hooks.py (both passes)  
   **outcome:** no refs: Ran 46, OK (skipped=13); with refs: Ran 46, OK (skipped=3: two need POPS_RESIDENT_BIN, one needs POPS_TRAMPOLINE_BIN, built EE images not supplied)
13. **command:** python tools/test_pops_modes.py (both passes)  
   **outcome:** rc=0 both passes; 'Compatibility dispatch PASS: 128 whole-buffer combinations, 128 unsupported masks'
14. **command:** python tools/test_pops_module_irx.py (both passes)  
   **outcome:** no refs: Ran 11, OK (skipped=4); with refs: Ran 11, OK, 0 skipped
15. **command:** python tools/test_pops_opcodes.py (both passes)  
   **outcome:** no refs: Ran 9, OK (skipped=3); with refs: Ran 9, OK, 0 skipped
16. **command:** python tools/test_pops_padman.py (both passes)  
   **outcome:** no refs: Ran 6, OK (skipped=3); with refs: Ran 6, OK, 0 skipped
17. **command:** python tools/test_pops_progressive.py (both passes)  
   **outcome:** no refs: Ran 8, OK (skipped=5); with refs: Ran 8, OK (skipped=3: need an EE compiler on PATH or POPS_EE_CC)
18. **command:** python tools/test_pops_read_trace.py (both passes)  
   **outcome:** Ran 9, OK in both passes
19. **command:** python tools/test_pops_resident.py (both passes)  
   **outcome:** no refs: Ran 75, OK (skipped=12); with refs: Ran 75, OK, 0 skipped
20. **command:** python tools/test_pops_runtime_corrections.py (both passes)  
   **outcome:** Ran 8, OK in both passes
21. **command:** python tools/test_pops_startup_calls.py (both passes)  
   **outcome:** Ran 6, OK in both passes
22. **command:** python tools/test_pops_vmc.py (both passes)  
   **outcome:** rc=0 both passes; 'VMC production contracts PASS'
23. **command:** python tools/test_pops_warmboot.py (both passes)  
   **outcome:** no refs: Ran 7, OK (skipped=3); with refs: Ran 7, OK, 0 skipped
24. **command:** python tools/test_smap_ipconfig.py (both passes)  
   **outcome:** rc=0 both passes; 'SMAP IPCONFIG bounded IPv4 parser PASS'
25. **command:** python tools/test_sony_ioman_layout.py (both passes)  
   **outcome:** rc=0 both passes; 'Sony IOMAN layout PASS'
26. **command:** python tools/test_subq_bridge.py (both passes)  
   **outcome:** rc=0 both passes; 'POPFS-iomanX SubQ bridge contract PASS'
27. **command:** python tools/popstarter_r13_commands.py <MAIN POPSTARTER.ELF>  
   **outcome:** 72 lines; no NOBOOT or BIOS command; used for S14
28. **command:** python tools/parity_report.py popstarter (in REPOP:, read-only)  
   **outcome:** 466 functions, 138,664 bytes, 434 claimed, 93.1% / 90.2%; size parity NOT MEASURED
29. **command:** throwaway scripts spot.py, corpus.py, corpus_lh.py, check_tables.py under <scratch>/docs/  
   **outcome:** produced S1-S16 and the docs self-check; not in the repository
30. **command:** git diff --name-only cfebe01 HEAD; git status --short (worktree docs)  
   **outcome:** 8 paths, all under docs/ or README.md; working tree clean after commit

## ee build check

Nothing was compiled for the EE by this track. The commit changes only documentation (7 files under docs/ and README.md); no file under common/, launcher/, tools/ or .github/ changed, so there is no new EE code to build. The resident-image compile recipe quoted in docs/CLOUD_CONTINUATION.md (ps2build EE GCC 15.3.1, 6,688-byte image, checker passed 12 sections) was run once by the architecture mapping author, not by me, and is described there as such. The Docker full-build command in that file is labelled inferred and not run. The host tests that compare against built EE images (POPS_RESIDENT_BIN, POPS_TRAMPOLINE_BIN, EE compiler) were skipped in my runs for lack of those inputs.

## deviations from original

1. No code was added or changed, so this commit introduces no new deviation. The deviations below already exist at cfebe01 and are what the documents now record (details and labels in docs/POPSTARTER_GAP_AUDIT_2026-11-11.md).
2. TROJAN files: launcHER plans every fix file against the POPS core only; all 509 unique community TROJAN files load outside it and are rejected (-3, measured twice on a host); a rejected fix file ends the launch where the original prints Invalid/Skipped and continues (read). Original accepting all 509: measured once, under re-verification.
3. Order: the original runs TROJAN/PATCH files before the CHEATS.TXT parser; launcHER applies config commands (handler_pops.c:1419) before fix files (:1450). Effect on real inputs not measured.
4. No BIOS.BIN, OSD.BIN or IGR skin loader; the six loader flags do not exist, so the shell edits (handler_pops.c:1484) and region pass (:1492) run unconditionally.
5. Default IGR: launcHER rewrites 0x228a5c..0x228a68 to exit directly; the original writes nothing there without a command (deliberate, owner-confirmed on Tekken).
6. $USBDELAY: launcHER accepts multi-digit and no-underscore forms, defaults to 0 and sleeps on the EE after the IOP reset on any device; the original takes one digit, defaults to 1 and patches a one-time delay into its PFS wrapper IRX on XX./SB. launches only. The second, preset-driven EE busy-wait (0x100013) has no launcHER equivalent.
7. $NOBOOT/$BIOS, MODE n/$MODE n, PATCHES.TXT, MODES.TXT, mc0:/mc1: config folders: launcHER-only; the original ignores them. $NOBOOT changes 0x2525b0 after a mode 6 where the original would not.
8. Config text: the original recognises a command at any '$' (so '#$SMOOTH' applies) and treats '$' as a terminator and TAB as not one; launcHER differs (measured once). VMCDIR.TXT acceptance rules differ; launcHER aborts on some inputs the original ignores (measured once).
9. Paths: no hdd0:__common (pfs1:/POPS/) layout, no POPS0..9 / __.POPS0..9 folders, IMAGE.VCD instead of IMAGE0.VCD, no IOPRP.IMG fallback, extra package search folders including a leftover test folder (handler_pops.c:153), 63-character silent title cut instead of the original's 80-character fatal message.
10. XX./SB. prefix matching: launcHER looks only at the last path component, accepts mixed case and a bare name; the original requires a separator, exact-case pairs, and accepts any path component.
11. SMB: launcHER requires IPCONFIG.DAT, uses its own parser (12 of 20 probe texts differ, measured once), embedded modules, 'smb:' device and no ECHO step.
12. Physical PS1 disc fallback absent; no icon.sys/list.ico on HDD; no rename messages; no argc==0/'cdrom' exit; no preset block (pops_config_load_table has a different mapping and is unused).

## not done

1. The original's TROJAN/PATCH loaders were not re-run by me. 'The original accepts all 509 corpus TROJANs' and the fix-file rule-difference table remain measured once (report 06) and are labelled so.
2. The original's config parser, VMCDIR.TXT reader and IPCONFIG/SMBCONFIG parsers were not re-run; sections 11 and 13 of the audit are measured once.
3. No emulation of the BIOS.BIN, OSD.BIN, IGR or physical-disc handlers by me; those rest on the feature authors' runs and the critic's re-runs as labelled. My spot checks there are static (instruction words, call sites, flag readers).
4. No console run, no RIPPCSX2 run, no full PS2 target build, no resident-image compile by this track. No RIPPCSX2 run recipe exists yet; CLOUD_CONTINUATION.md says so.
5. docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md was not edited: no behaviour was copied in this commit, so there is no new quirk to log. Candidate entries for when the features land are in doc_updates.quirks (next free number is 62).
6. The PR #23 body was not edited (not allowed); the proposed text is in doc_updates.user_facing. The PR body's 'Still open' item 5 still links REPOP feat/psxcore-validation.
7. REPOP was not changed: its docs/POPSTARTER_CONTINUATION.md co-author instruction, docs/CONFIG_TABLE.md errors and the missing four-function note are listed in the audit section 17 for a separate REPOP pull request.
8. launcher/iop/smbman/README.md:15 and launcher/iop/smbman/SMB-NOTICES.txt:10 ('with ChatGPT/OpenAI assistance') are outside docs/ and README.md and are existing credit lines, not instructions; left untouched.
9. README.md's IGR combo line (L1+L2+R1+R2+SELECT+START) was not checked against the default mask 0x0904, whose button meaning is only inferred; left as is.
10. Device rows of docs/POPS_PARITY_AUDIT_2026-10-28.md and docs/POPSTARTER_REPLACEMENT.md were not cross-checked against the new findings (only links and the co-author instruction were changed there).
11. tools/test_pops_external.py's manual check_corpus (--corpus-root) was read, not run.
12. Whether launcHER's always-on patches equal exactly what the MAIN preset bytes select was not re-checked; the inventory row says so.

## decisions for owner

1. TROJAN priority: real-world TROJAN files currently stop a launcHER launch. Do you want the small safety change first (a fix file the original would skip is skipped, not fatal) ahead of full TROJAN parity, once the original-side corpus result is re-verified?
2. HDD folder mapping: the original takes everything except the VCD from hdd0:__common (pfs1:/POPS/). launcHER reads per-game files from the VCD's own folder. Should launcHER mount __common and follow the original on HDD, keep its own layout, or look in both?
3. Fix files versus commands: the original runs TROJAN/PATCH before CHEATS.TXT; launcHER the other way round, pinned by tools/test_pops_launch_hooks.py:837-870. Reorder to match (after measuring whether results differ), or keep?
4. Default IGR: keep launcHER's direct exit (confirmed by you on Tekken) or write nothing as the original does (Sony's yes/no dialog; needed for an IGR skin to be visible without $IGR0..2; the dialog's YES path under launcHER's exit has never been run on a console)?
5. launcHER-only inputs: keep as documented extensions or remove for exact parity: $NOBOOT/$BIOS (acts where the original ignores it), MODE n/$MODE n, PATCHES.TXT, MODES.TXT, mc0:/mc1: config folders, multi-digit and no-underscore $USBDELAY, mixed-case/bare-name XX./SB./PP. matching?
6. Second USB delay: copy the original's CPU-speed EE busy-wait (preset byte 0x100013: 2 in MAIN, 6 in the USBDELAY profile), replace it with a timed wait, or leave it out?
7. Physical PS1 disc: in the original it is only the fallback when no VCD is found. launcHER's target is a .vcd path, so how should a physical-disc launch be requested, if at all?
8. Hard-coded test folder ata0:/LAUNCHER-TEST-20261013-A/ in the production POPS package search list (launcher/src/handler_pops.c:153): remove?
9. Existing credit lines outside docs: launcher/iop/smbman/README.md:15 and launcher/iop/smbman/SMB-NOTICES.txt:10 say 'with ChatGPT/OpenAI assistance'. Your rule forbids adding AI attribution and also says not to remove existing attribution unless you ask. Keep or remove?
10. REPOP follow-up (separate repository, separate PR): remove the AI co-author instruction at docs/POPSTARTER_CONTINUATION.md:256; fix docs/CONFIG_TABLE.md rows $410/$413/$417; record the four functions missing from the ground truth and the 17.0% figure beside 90.2%; fix the 'done flag' comment at popstarter/src/main.c:1225-1236.
11. REPOP worktree REPOP: had uncommitted source changes (patch_engine.c/.h, runtime_hooks.c/.h, runtime_symbols.ld) and an ignored build/popstarter_unpacked.bin by the end of this session. I did not write there; check they belong to another track before anything is committed from it.
12. The local docs commit 3d42449 is on branch pr23/docs only. Whoever integrates it should cherry-pick or merge it onto codex/popstarter-replacement; its SHA will change and the PR-body text below refers to it by description.

## doc updates


### inventory rows

Changed in docs/POPSTARTER_R13_INVENTORY.md (statuses in brackets; nothing upgraded):
- Header: dated correction note explaining labels 2x/1x/read/inferred and that all of it is host work.
- $UNDO_COMPATIBILITY_CODES / $UNDO_GAME_FIXES / $UNDO_LIBCRYPT_FIX [PRESENT, unchanged]: the 0x2525b0=0x1bfc write is skipped when a user BIOS.BIN was loaded (gp+0x38a4 or gp+0x3b98; readers 0x8948f0, 0x894d4c, 0x895088); launcHER has no such exception because it has no BIOS.BIN loader.
- no IGR command [PARTIAL, unchanged]: original writes nothing at 0x228a20..0x228a68 (Sony's combo mask 0x0904 and dialog stay); launcHER rewrites 0x228a5c..0x228a68 to exit directly (pops_modes_patches.c:1279-1299); dialog+YES under launcHER's exit never run on a console; owner decision.
- $USBDELAY_n [PARTIAL, unchanged]: handler 0x89dbe4, one digit, byte 0x100017 (default 1), consumer 0x879d04..0x879e58 patches 'DLAY' (0x91fb30) in the PFS wrapper on XX./SB. only; launcHER accepts other forms, defaults to 0, sleeps on the EE after the IOP reset (handler_pops.c:1751-1753).
- $NOBOOT paragraph: $NOBOOT/$BIOS are not r13 commands (72-line census); the 0x2525b0 write is launcHER's own; MODE n, PATCHES.TXT, MODES.TXT are launcHER-only.
- Region paragraph: with any of gp+0x3b98/0x38a4/0x344c/0x3430 set, known licence skips only 0x2649a0; unknown licence skips 0x264994..0x2649a0 and the four zero bytes at 0x20f6cc/d8/dc/e0; shell edits skipped under the same flags; launcHER runs both unconditionally.
- POPS package [PRESENT -> PARTIAL]: IOPRP.IMG fallback not implemented; SHA-256 instead of the original's size/signature checks; extra search folders incl. test folder at handler_pops.c:153.
- Launch paths row rewritten as 'Launch type from argv[0]' [PARTIAL]: types 0..3, IMAGE0.VCD vs launcHER's IMAGE.VCD, PATINFO handling.
- SMB config [PARTIAL, unchanged]: original's file rules, external IRX set, smbman renamed to 'mass', LOGON/ECHO/OPENSHARE; launcHER requires IPCONFIG.DAT, own parser (12 of 20 probe texts differ, 1x), no ECHO.
- Rename messages [MISSING, unchanged]: shown only off hdd0: and only on non-quiet profiles; MAIN never shows them.
- CHEATS.TXT / config locations [PRESENT -> PARTIAL]: command recognised at any '$' in the original; launcHER ignores commands after '#', ';' or other text and splits on TAB (1x); PATCHES.TXT/MODES.TXT/mc folders launcHER-only.
- VMCDIR.TXT [PRESENT -> PARTIAL, 1x]: acceptance rules differ; launcHER aborts on some inputs the original ignores.
- TROJAN/PATCH [PARTIAL, unchanged]: corpus result added (3,952/509 TROJAN, 870/10 PATCH; launcHER rejects all 509 unique TROJANs with -3 and accepts all 10 PATCH, 2x; original accepting all 509 'measured once and under re-verification'; rejected file ends the launch; further rule differences 1x; order vs CHEATS.TXT; folder difference).
- IGR skin [MISSING]: FUN_0087e464 rules (folder, slots, limits, no TIM2 check, never fatal).
- OSD.BIN [MISSING]: FUN_0087eb24 header format, destinations, caps; no real sample available.
- User BIOS.BIN [MISSING], retitled: size test only (> 0x7ff8e), first 0x7ff90 bytes to 0x24bc20, 0x20079a=0x1000, flags; NO integrity check on the user's file (the message belongs to the OSD handler's gate gp+0x3890).
- Physical PS1 disc [MISSING], retitled: it is the no-VCD fallback (gp+0x3410), not a selected mode; block 0x8766fc..0x876a40 summarised.
- New rows: XX./SB. scan rules [PARTIAL]; argc==0 / 'cdrom' exit [MISSING]; numbered folders POPS0..9 / __.POPS0..9 [MISSING]; HDD hdd0:__common layout [MISSING]; icon.sys/list.ico on HDD [MISSING]; 80-character name limit [MISSING]; preset block 0x100008..0x10002f [PARTIAL]; second USB delay 0x100013 [MISSING].
- $RESET_WARMBOOT row: formatting only (a row split over two lines was joined).
- 'Remaining work, in order' item 4 replaced by steps (a)-(m): (a) skip-not-abort then TROJAN parity; (b) path table and folder mapping decision; (c) IGR skin; (d) loader flags then BIOS.BIN; (e) fix files before commands, measured first; (f) OSD.BIN; (g) $USBDELAY parser/default, preset table, command context, VMCDIR rules; (h) launch-argument rules, resolver candidates, IOPRP.IMG, remove test folder; (i) SMB parsers; (j) physical disc; (k) $USBDELAY delay in popfs; (l) HDD __common, icon.sys/list.ico; (m) SMB external modules; default IGR is an owner decision.

### quirks

docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md was NOT edited (no behaviour was copied in this commit). Candidate entries to log, unnumbered, when the matching feature is implemented (next free number is 62):
- BIOS.BIN: only the first 0x7ff90 bytes are read, so a normal 0x80000-byte dump loses its last 0x70 bytes; any file larger than 0x7ff8e bytes is accepted with no content check (2x).
- BIOS.BIN/OSD.BIN: with a known licence the region pass still writes the region letters at 0x2cbb72 and 0x20f6cc into a user BIOS (2x).
- BIOS.BIN handler called with a game name lacking the trailing '/' opens a truncated folder name (2x).
- OSD.BIN: a compat mode 6 in the file's own header turns the OSD it just installed off again (2x); the game pass ignores the all-games OSD flags, so a v2 all-games file followed by a v1 game file leaves mixed code and 0x10a0 bytes of the v2 body (1x); the v2 code leaves a jal in a jal's delay slot at 0x252c34/0x252c38 (2x for the words, behaviour unknown).
- Mode 6 and $UNDO_ read only the BIOS flags, never the OSD flags (1x).
- IGR skin: a zero-length file is accepted and wipes Sony's image; no TIM2 validation; a negative seek result is not rejected (read, do not copy); the POPS<n> suffix is not applied to the skin folder (2x).
- TROJAN format 3 with hdr[0x0a] < 6 is skipped as 'outdated' while a built-in entry is active (1x).
- IPCONFIG.DAT: the argument length passed to ps2smap counts non-separator bytes only, so a three-address line is passed short by two (1x). SMBCONFIG.DAT: a server token of up to 21 characters is copied into a 16-byte field; port 0 allowed; no IPv4 validation (1x).
- $USBDELAY: only a single digit is a command; the delay exists only on XX./SB. launches; unpatched wrapper waits 5 s (2x for the patch, inferred for the wait itself).
- Physical disc: PS2 CD types 0x12/0x13 are accepted as PS1 discs; types 0x11/0x13 get the $MUTE_CDDA writes for no known reason (2x, callees modelled).
- Config text: a command after '#' or ';' still applies; TAB is not a terminator (1x).

### hardware checklist

No new hardware check is created by this commit (no code changed). Nothing in it was run on a console; every item below is NOT TESTED on a console.

Worth doing now on the existing build (cfebe01), because the docs now make a user-facing claim from host evidence only:
1. Put one community TROJAN_n.BIN (from a POPStarter fix pack for a game you own) in a game's subfolder and launch through launcHER. Host prediction: the launch stops with 'POPS: Fix file rejected ... (-3)'. Then the same game under POPStarter r13 for comparison (prediction, measured once on a host: it loads the file). Note: a real POPS launch strands the ps2rig (Sony's IOP reset removes ps2link; the rig reports 'hang'), so this is a hands-on check, not a rig run.
2. A PATCH_n.BIN from the same packs in the same place (host prediction: accepted).

To add when the corresponding increment lands (from the audit, section 16):
- IGR skin: IGR_BG/NO/YES.TM2 in the device POPS folder, with $IGR0 (the dialog only shows under $IGR0..2 while launcHER's direct exit is the default); also Sony's dialog followed by YES under launcHER's own exit, which has never been run.
- BIOS.BIN: a user PS1 BIOS in the POPS folder and in a game folder; boot, region behaviour on a US and a European disc, $UNDO_ and mode 6 with it.
- OSD.BIN: only if a real sample file can be found; none was available.
- $USBDELAY_n on an XX. (USB) launch with a slow drive, with and without the command, against POPStarter.
- Physical PS1 disc with no VCD present; CD-DA audio; a PS2 CD (types 0x12/0x13) and a non-PS1 disc for the two fatal messages.
- HDD: files in hdd0:__common /POPS/ (CHEATS.TXT, fix files, VMCs, MODULE_n.IRX), icon.sys/list.ico creation.
- SMB: external IRX set from mc?:/POPSTARTER/, SMBCONFIG.DAT forms the original accepts and launcHER currently rejects (share password, port 0, two-line file).
- Numbered folders POPS0..9 on USB and __.POPS0..9 on HDD.

Still open from before (unchanged): the November 2 hardware list in the PR body (plain launch, $NOVMC0, $FAKELC, recompiler add-ons, disc swap, reset combo, cheats, PAL/NTSC, pads, widescreen, $SET_TIMINGS, XX. USB pair, padman commands) and the save/reload/cold-power-cycle proof on a new dedicated VMC.

### user facing

Proposed replacement for the PR #23 body sections "Current checkpoint" and "Still open, in order". Not applied (this track may not edit the PR). `<docs commit>` stands for the SHA this docs commit gets once it is on `codex/popstarter-replacement` (local: `3d42449` on `pr23/docs`).

## Current checkpoint — November 11, 2026 (Pacific)

- **Documentation checkpoint, no code change since `cfebe01`.** `<docs commit>` adds [POPSTARTER_GAP_AUDIT_2026-11-11.md](https://github.com/NathanNeurotic/launcHER/blob/codex/popstarter-replacement/docs/POPSTARTER_GAP_AUDIT_2026-11-11.md) and corrects the inventory, the continuation notes, the README and the setup page from it. **Nothing in it was run on a console or in an emulator of the whole machine.** "Measured" below means a block of the original was run on a host with its library calls modelled, or launcHER's C code was built with host gcc and called. Each statement in the audit is labelled: measured by two independent runs, measured once, read from disassembly or source, or inferred.
- **Most important for users: TROJAN files from community fix packs stop the launch.** Every distinct `TROJAN_n.BIN` found in the community packs kept in REPOP (509 distinct files, 3,952 copies) loads its code outside the POPS image. launcHER rejects all 509 (measured twice on a host) and ends the launch when a fix file is rejected (read from the launch code). That POPStarter itself accepts all 509 was measured once on a host and is being re-verified. The 10 distinct `PATCH_n.BIN` files are accepted. **NOT TESTED on a console.** Until this is fixed, take TROJAN files out of the game folders if a launch stops with "Fix file rejected".
- **Corrections to earlier statements in this PR and its documents:**
  - IGR skins (`IGR_BG/NO/YES.TM2`): the README said to place them beside the game. launcHER has no code for them. POPStarter reads them only from the device's `POPS` folder (measured twice on a host).
  - "User BIOS.BIN with integrity check": there is no integrity check on the user's file. POPStarter accepts any file larger than `0x7ff8e` bytes and copies its first `0x7ff90` bytes over POPS's BIOS (measured twice on a host). The "integrity" message is about POPS's own built-in BIOS and belongs to the OSD loader. launcHER has neither loader.
  - POPS package: the inventory said PRESENT including `IOPRP.IMG`. The `IOPRP.IMG` fallback is not implemented; the row is now PARTIAL.
  - `$NOBOOT` / `$BIOS`, `MODE n`, `PATCHES.TXT`, `MODES.TXT` are launcHER's own; POPStarter r13 has none of them (command census of the binary).
  - `$USBDELAY_n`: launcHER waits on the main CPU after the reset, on any device, default none. POPStarter takes one digit, default 1, and on USB/SMB launches patches a one-time wait into its file driver (the patch measured twice on a host; that the driver then waits is inferred). NOT TESTED on a console.
  - Order: POPStarter runs TROJAN/PATCH files before `CHEATS.TXT`; launcHER runs them after. Whether any real config ends differently has not been measured.
  - Physical PS1 disc is not a mode in POPStarter; it is what it does when no VCD is found. launcHER has no such path.
  - Hard disk: POPStarter takes everything except the VCD (POPS files, fix files, text files, memory cards) from `hdd0:__common`, folder `/POPS/` (read from the code, not run). launcHER reads per-game files from the VCD's own folder and never mounts `__common`. The HDD locations have not been compared file by file.
- **Also missing, now listed in the inventory:** `OSD.BIN`, numbered folders (`POPS0..9`, `__.POPS0..9`), `IMAGE0.VCD` for partition launches, the original's `XX.`/`SB.` name rules, its SMB file rules, `icon.sys`/`list.ico` on HDD, the 80-character name limit, the build-time preset block. Three inventory rows went from PRESENT to PARTIAL (POPS package, config file locations, `VMCDIR.TXT`); none was upgraded.
- **REPOP:** the live line is `main` at `bc258e48`; `feat/psxcore-validation` was merged into it (squash `0d5ca939`) and is superseded. REPOP's own report says 434 of 466 functions and 90.2% of bytes, but its function list leaves out four large functions (597,012 bytes, including `main` and the config parser). Counting them, byte coverage is 17.0%. REPOP is a reference source, not a runnable r13.
- **Evidence for this checkpoint:** 19 spot checks against the original binary, Sony's POPS and the sources are listed in section 2 of the audit. All 26 `tools/test_*.py` files exit 0 locally without and with the reference inputs (code unchanged); with the inputs, the tests that need built EE images or an EE compiler were skipped. No EE build was made for this checkpoint. **No console run.**
- The November 2 checkpoint (`fced49d` `$NOVMC0/1`, `b0a65d8` `$FAKELC`) and everything before it: [PR23_CHECKPOINT_HISTORY.md](https://github.com/NathanNeurotic/launcHER/blob/codex/popstarter-replacement/docs/PR23_CHECKPOINT_HISTORY.md). (Move the two November 2 bullets there when this text is applied.)
- Start with [POPSTARTER_R13_INVENTORY.md](https://github.com/NathanNeurotic/launcHER/blob/codex/popstarter-replacement/docs/POPSTARTER_R13_INVENTORY.md) for status per feature, the gap audit for addresses and evidence, and [CLOUD_CONTINUATION.md](https://github.com/NathanNeurotic/launcHER/blob/codex/popstarter-replacement/docs/CLOUD_CONTINUATION.md) for how to verify locally.

## Still open, in order

Items 1 to 10 can be checked on a host. A host result is never a console result; every item stays "NOT TESTED on a console" until someone runs it on one.

1. **Fix files must not stop the launch.** First re-verify on the original that it accepts the community TROJAN files (measured once so far). Then: a fix file POPStarter would skip is skipped, not fatal; then TROJAN parity (the original's header rules, code loaded outside the POPS image, its ten call slots).
2. **One path table measured from the original** for every per-folder file (POPS files, fix files, `CHEATS.TXT`, `VMCDIR.TXT`, `DISCS.TXT`, skins, `BIOS.BIN`, `OSD.BIN`, memory cards), and a written decision on how each folder maps to launcHER's, hard disk included. No behaviour change. *Needs an owner decision on the HDD layout.*
3. **IGR skin** loading.
4. **`BIOS.BIN`**, together with the flags it sets and what they switch off later (PS1 BIOS shell edits, parts of the region pass, the `$UNDO_` write, mode 6).
5. **Fix files before commands:** measure both orders on real configs, then decide whether to reorder.
6. **`OSD.BIN`.** No real sample file was available; the format is known only from the loader's checks.
7. **`$USBDELAY` parsing and default, the preset table, command recognition in config text, `VMCDIR.TXT` rules.** *Needs an owner decision on which launcHER-only commands and files stay.*
8. **Launch-name rules and VCD lookup** (`XX.`/`SB.` rules, `IMAGE0.VCD`, `POPS0..9`, `__.POPS0..9`, name length), the `IOPRP.IMG` fallback, and removing a leftover test folder from the POPS search list.
9. **SMB config file rules** as in the original.
10. **Physical PS1 disc fallback:** the planning and POPS changes on a host; the drive part cannot be verified without a console. *Needs an owner decision on how such a launch is requested.*
11. **Console or emulator needed from here:** the `$USBDELAY` wait itself; the hard disk `__common` layout and `icon.sys`/`list.ico`; SMB with POPStarter's external module set.
12. **Default IGR** (launcHER exits directly; POPStarter shows Sony's yes/no dialog): owner decision. Sony's dialog followed by YES under launcHER's own exit has never been run on a console.
13. **Hardware checks from November 2:** unchanged and all still open. Keep the existing paragraph ("Hardware checks: ...") as it stands, and add at its front: a community TROJAN file in a game folder (host prediction: launcHER stops with "Fix file rejected"; POPStarter loads it).
14. Verify manual GS DISPLAY on hardware.
15. REPOP: record the four missing functions and the 17.0% figure in its documents, correct its preset table, and continue from `main`. [Current continuation](https://github.com/NathanNeurotic/REPOP/blob/main/docs/POPSTARTER_CONTINUATION.md). (This link replaces the old one to `feat/psxcore-validation`.)
16. Prove in-game save/reload/cold-power-cycle persistence on a **new dedicated VMC**, preserving existing saves; device/transport runtime, CDDA, controllers, representative games and Ember-forwarding acceptance.
17. Later, after parity: work through [POPSTARTER_QUIRKS_TO_FIX_LATER.md](https://github.com/NathanNeurotic/launcHER/blob/codex/popstarter-replacement/docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md).

Keep continuation on this PR and synchronize REPOP evidence. Original Sony/game/save binaries stay external.
