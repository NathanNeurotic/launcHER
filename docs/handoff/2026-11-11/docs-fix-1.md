# Gap audit and status documents: answer to review 1

Written by whoever answered the review. Copied as written; not re-verified.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## summary

Fixer pass for the docs track (worktree the docs worktree, branch pr23/docs). The earlier fixer had left all its work uncommitted (6 modified files plus a new tools/test_pops_doc_claims.py). I did not trust it: I re-ran its scratch harnesses and static scans myself against the original and the corpus, disassembled the cited ranges, re-checked the REPOP state read-only, compared every number with the text, corrected what did not hold, then ran the whole host test list both ways and committed three local commits (head ed30f55, tree clean). Documentation, one new test file and one workflow step only; no C source and no existing test changed. Everything is host work (Unicorn, host gcc, EE gcc for a compile check). NOT TESTED on a console; no whole-machine emulator run; no full target build.

All nine review findings were reproduced and are real:
1 (shared docs edited): real and not resolvable by me. See decisions_for_owner. The fix commits again touch README.md, docs/CLOUD_CONTINUATION.md, docs/POPSTARTER_R13_INVENTORY.md and docs/pops-setup.html, because the faulty sentences are in lines this track wrote in 3d42449 and the branch tip has not changed those four files since (git diff 3d42449 codex/popstarter-replacement shows only build.yml differing among them).
2 (REPOP worktree stale): real. The worktree is on a local working branch created from origin/main at 04:26:42; its first local commit is 06:25:53, the docs commit was 06:28:19. Now six commits past bc258e48 with one uncommitted change. Audit S18/S20/section 17 and CLOUD_CONTINUATION now say to use a clean export of bc258e48. I corrected the earlier fixer's wording, which implied the branch itself began at 06:25.
3 ("every banner printf"): real. BIOS handler with gp+0x38b0=1 still prints from 0x8805b4 ("DONE") and 0x880984 (newline). Now "most, not all" with counts.
4 (IGR function return, gp+0x38e0): real. Returns 0 when gp+0x38dc is 1, -666 (and sets gp+0x38dc) after a failed folder check, 1 otherwise; BIOS game-scope call sets gp+0x38e0. Both documented.
5 ($USBDELAY_ handler address): real; 0x89dbe0 everywhere now (0x89dbe4 is the next instruction).
6 ("fifteen call slots"): real; replaced by "at least the ten the corpus uses", with the count of empty pairs in the block (60).
7 (CI coverage): real; 24 of 26 ran in CI at cfebe01. Replaced by a machine-checked list.
8 (README/setup page $USBDELAY wording): real; both now say the wrapper "appears to wait" and that the wait was never observed.
9 (PATCH file over the IGR slots): real; added to audit sections 6 and 15 and the inventory IGR row. README:718 and pops-setup.html:554 deliberately left alone (text in doc_updates.user_facing).
The reviewer's "understated" point is also applied: "the original accepts all 509" is no longer labelled measured once.

One harness incident, not a test failure: I ran the two passes in parallel and test_pops_external.py failed in the reference pass at the link step (Permission denied on build/pops-host/pops_external.dll, held by the other pass). Re-run alone it passed. Eight test files build into build/pops-host under fixed names inside the checkout, so the TMP isolation does not cover them; CLOUD_CONTINUATION now warns about it.

## commits

1. 85084b1 docs(pops): correct the gap audit after independent review
2. db36890 docs(pops): correct status documents after the gap-audit review
3. ed30f55 test(pops): check status-document statements against workflows and the original

## files changed

1. docs/POPSTARTER_GAP_AUDIT_2026-11-11.md
2. README.md
3. docs/pops-setup.html
4. docs/POPSTARTER_R13_INVENTORY.md
5. docs/CLOUD_CONTINUATION.md
6. tools/test_pops_doc_claims.py (new)
7. .github/workflows/build.yml (one new step in host-tests)

## measured evidence

1. BIOS.BIN handler 0x88019c under Unicorn (file, folder and print calls modelled): 20 inputs x quiet flag 1 and 0. With gp+0x38b0=1: 18 print calls in 14 of 20 inputs, only from 0x8805b4 (10) and 0x880984 (8). With 0: 84 calls. gp+0x38e0 goes 0 to 1 in 10 of 10 game-scope runs and 0 of 10 all-games runs. Game folder missing: return -666, gp+0x3460=1, nothing opened, POPS unchanged, 4 of 4 (both backends). gp+0x38e0 already 1: folder not checked, file loads, 4 of 4.
2. IGR skin function 0x87e464 under Unicorn: 50 runs. gp+0x38dc=1: return 0, nothing opened, POPS unchanged, 24 of 24. gp+0x38dc=0 with gp+0x3868=1: return 1, 16 of 16. gp+0x3868=0 with the folder check FUN_008d8958 forced: result 1 gives load and return 1 (2 of 2); results 0, 2, -1 give return -666, gp+0x38dc=1, nothing opened (6 of 6). Preset byte 0x10002d set to 0 or 2 does not stop the function itself (2 of 2). The -666 path was reached only with a forced folder-check result.
3. Static pattern scan of every jal 0x915708 for a preceding gp+0x38b0 test (a pattern, not flow analysis): BIOS handler 14 sites, 2 untested; OSD handler 41, 3; IGR skin function 15, 0; TROJAN loader 20, 1; main 295, 21; code area 0x870000..0x915000 2,031, 145.
4. Disassembly read by me: 0x8712c8..0x8712ec, 0x876a84..0x876a98, 0x876b18..0x876b24 (main tests gp+0x38dc and frame word 0x1108 before the skin call and reads gp+0x38dc after it, not the return value), 0x87e474..0x87e4c4, 0x87eb04..0x87eb0c, 0x8804ec..0x880500, 0x89dbd4..0x89dbe8.
5. gp+0x38e0 access sites over 0x870000..0x91ef00: 7 lw and 8 sw (clear at 0x870c58, then seven lw/sw pairs 0x14 apart), as the audit lists.
6. Fix-file corpus (REPOP popstarter/, read-only): 3,952 TROJAN files, 509 distinct; 870 PATCH, 10 distinct. Original loaders under Unicorn on every distinct file: TROJAN 509 of 509 return 1, payload found at its load address, slot word changes from b+8 to jal entry, no other POPS change, no Invalid/Skipped message, 0 unmodelled calls; PATCH 10 of 10 return 1. Hook slot per file number as tabulated (ten slots).
7. launcHER pops_fix_stage (host gcc build of this worktree's common/src) on the same files: TROJAN -3 for 509 of 509 with the core unchanged; PATCH 0 for 10 of 10, and for 10 of 10 the changed core bytes and values equal the original loader's.
8. One corpus PATCH_5.BIN (327,360 bytes, payload 327,296) loads at 0x2feff0..0x34ee70, the three skin slots (324,236 bytes actually change, same in the original and launcHER). One PATCH_6.BIN changes halfword 0x2525b0 inside the ROM copy. No corpus PATCH changes a byte in 0x262b80..0x2afc20.
9. Embedded PFS wrapper IRX: static read of .text 0..0x140 (thsemap 8, flag at 0x540, word at 0x420, 5 if still DLAY, x1,000,000, thbase 33, thsemap 6; single caller at .text 0x124 inside table entry 3). Callbacks run under Unicorn through tools/trace_original_pops_io.py with imports modelled: unpatched, first open calls thbase 33 with 5,000,000 before ioman open, no later thbase call; patched n=0..9, argument n x 1,000,000 once, 10 of 10; read/seek/close before any open make no thbase call, the first open after them does (1 of 1). Not an IOP kernel; the wait itself was never observed.
10. Always-live block (source 0x983150, 0x738 bytes): 60 b+8/nop pairs, 5 at 0x2327d0..0x2327f0 and 55 at 0x232d08..0x232eb8 (recomputed by the new test with the reference input).
11. REPOP, read-only: origin/main = bc258e48; worktree REPOP.worktrees/pr23 on a local branch created 04:26:42, first local commit 06:25:53, now 6 commits past bc258e48 (head 0a440b01) with one uncommitted file. My own git archive export of bc258e48 into scratch: python tools/parity_report.py popstarter prints 466 / 138,664 / 434 / 93.1% / 90.2%.
12. Workflows against tools/test_*.py at the branch tip (read via git grep on the ref, 27 test files there): the same three files are not build.yml steps (test_launch_args.py, which launch-args.yml runs; test_pops_builtin_db.py and test_pops_progressive.py, run by no workflow), so the new Native coverage check would hold after a merge with the current tip.
13. Mutants against tools/test_pops_doc_claims.py (13 deliberate changes to documents or the workflow, each restored; run twice, the second time on the final text): 13 of 13 fail with POPSTARTER_TEST_ELF, 7 of 13 without (the other six contradict only the original's bytes). Working tree byte-identical before and after.

## tests run

1. **command:** Pass 1, no reference inputs: python tools/test_<x>.py for all 27 files (run on the working tree before the commits; only documentation text changed afterwards)  
   **outcome:** All 27 exit 0. unittest counts (tests/skipped): breakpoint 11/4, builtin_db 14/14, display 21/6, doc_claims 12/7, external 128/14, features 29/2, fix_files 31/3, io_probe 6/0, launch_hooks 46/13, module_irx 11/4, opcodes 9/3, padman 6/3, progressive 8/5, read_trace 9/0, resident 75/12, runtime_corrections 8/0, startup_calls 6/0, warmboot 7/3. Script-style files exit 0: launch_args, network_transports, popfs, pops_fatfs, pops_modes, pops_vmc, smap_ipconfig, sony_ioman_layout, subq_bridge.
2. **command:** Pass 2, with POPS_TEST_ELF and POPSTARTER_TEST_ELF: all 27 files, run in parallel with pass 1  
   **outcome:** 26 exit 0; test_pops_external.py exit 1 at the link step (ld: cannot open output file build/pops-host/pops_external.dll: Permission denied) because pass 1 was using the same DLL. Harness collision caused by my parallel run, no test executed. Counts (tests/skipped): breakpoint 11/0, builtin_db 14/0, display 21/0, doc_claims 12/0, features 29/0, fix_files 31/0, io_probe 6/0, launch_hooks 46/3, module_irx 11/0, opcodes 9/0, padman 6/0, progressive 8/3, read_trace 9/0, resident 75/0, runtime_corrections 8/0, startup_calls 6/0, warmboot 7/0; the nine script-style files exit 0.
3. **command:** python tools/test_pops_external.py with the reference inputs, alone, after both passes had finished  
   **outcome:** exit 0, 128 tests, 3 skipped (the progressive tests that need an EE compiler).
4. **command:** Extra, beyond the two required passes: reference inputs plus POPS_EE_CC (ps2build EE GCC 15.3.1), POPS_RESIDENT_BIN and POPS_TRAMPOLINE_BIN (images I built by hand in scratch) for test_pops_launch_hooks.py, test_pops_progressive.py, test_pops_external.py  
   **outcome:** launch_hooks 46 tests, 0 skipped, exit 0. progressive 8 tests, 1 skipped (test_built_progressive_bridge: 'optional EE objcopy', the test looks for mips64r5900el-ps2-elf-objcopy without .exe), exit 0. external 128 tests, 1 skipped, exit 0. Hand-built images, not CMake's; compiler is not CI's.
5. **command:** python tools/test_pops_doc_claims.py at the committed head ed30f55, without and with the reference inputs  
   **outcome:** Without: 12 tests, 7 skipped, OK. With: 12 tests, 0 skipped, OK. This is the only test that reads the documents, so it was re-run after the last text edits.
6. **command:** mutants.py (scratch) against tools/test_pops_doc_claims.py, without and with the reference inputs, twice  
   **outcome:** 7 of 13 caught without the reference input, 13 of 13 with it; baseline green before and after; files restored byte-for-byte.

## ee build check

No common/src or launcher/src file changed in this track (git diff 3d42449 HEAD -- common launcher is empty), so there is no changed C file to compile. As a check that the tree still builds what it built before, I compiled the resident image with <ps2build>/toolchain/ee/bin/mips64r5900el-ps2-elf-gcc.exe (GCC 15.3.1 20260823) using the recipe in docs/CLOUD_CONTINUATION.md (-Os -G0 -fno-pic -mno-abicalls -ffreestanding -fno-builtin -nostdlib -nostartfiles -Wall -Wextra -Werror -DPOPS_RESIDENT_IMAGE, linker script common/src/pops_resident.ld, sources pops_resident_engine.c, pops_progressive.c, pops_progressive_bridge.S, pops_resident_guards.S, pops_resident_recompiler.S): exit 0, objcopy exit 0, image 6,688 bytes, tools/check_pops_resident_image.py printed 12 PASS lines and exited 0. I also assembled launcher/src/pops_trampoline.S (gcc -c -G0 -Icommon/include -Ilauncher/include, objcopy -O binary -j .text): 260 bytes, and test_pops_launch_hooks.py accepted both images (46 tests, none skipped). Outputs went to scratch only. NOT built: the launcHER ELF, any IRX, the CMake project, the container target build. That compiler is not CI's.

## deviations from original

1. No launcHER code changed in this track, so no new deviation was introduced and none was removed.
2. Deviations the corrected documents now state more exactly (unchanged in code): $USBDELAY is parsed with several digits and without the underscore, defaults to 0, and sleeps on the EE on any device, where the original takes one digit, defaults to 1, and on XX./SB. launches passes it to its file wrapper.
3. launcHER rejects all 509 distinct corpus TROJAN files (-3) and a rejected fix file ends the launch; the original's loader accepts all 509 (host emulation, file calls modelled, no payload executed).
4. This worktree's code has no IGR skin loader (true at cfebe01; the branch tip has since merged one, see decisions_for_owner).

## not done

1. Finding 1 (shared docs listed as off-limits were edited by this track) cannot be settled from here; the fix commits edit the same four shared files again. The lead has to confirm ownership or re-apply by hand from doc_updates.
2. README.md:718 and docs/pops-setup.html:554 (custom IGR graphics note) were NOT given the PATCH_5 sentence, to avoid clobbering the IGR track's replacement of those lines. Text is in doc_updates.user_facing.
3. Not re-derived by me or by the reviewer: the OSD.BIN handler, the physical-disc block, the XX./SB. device scan, the SMB config parsers, the launch-type parser. The '2x' labels on those rows still rest on the mapping run plus the critic's run as the audit states; I neither confirmed nor refuted them.
4. The rule-difference table of audit section 12 and sections 11 and 13 were not re-run by me; the audit says so and records the review's re-runs as reported, not as mine.
5. The -666 exit of the IGR skin function was reached only by forcing the folder check's result; whether gp+0x3868 can still be 0 when main reaches the call was not examined.
6. That thbase import 33 is DelayThread and table entry 3 is open is inferred from PS2SDK numbering; no IOP kernel ran and the wait was never observed.
7. tools/test_pops_progressive.py test_built_progressive_bridge skips on Windows even with POPS_EE_CC set, because it looks for the objcopy name without .exe. Existing test, outside this task; not changed.
8. The two full passes ran on the working tree before the three commits (HEAD 3d42449 plus the uncommitted work). After them only documentation text changed; I re-ran the one test that reads documents at ed30f55, not the other 26 files.
9. No console run, no whole-machine emulator run, no full PS2 target build, no push, no PR edit.
10. After a merge with the branch tip the documents will be stale in known places (see decisions_for_owner): the statements that launcHER has no skin code, and '27 test files'.

## decisions for owner

1. Ownership of README.md, docs/CLOUD_CONTINUATION.md, docs/POPSTARTER_R13_INVENTORY.md and docs/pops-setup.html for this round: this track edited them in 3d42449 (already on the branch as merge a957647) and again in db36890. If the docs track does not own them, drop db36890's hunks for those files and apply doc_updates by hand. At the time of writing the branch tip had not changed these four files since 3d42449, so db36890 applies cleanly today; other tracks' pending doc_updates for the same rows (IGR skin row, README:718) will have to be merged with it.
2. The branch tip has merged the IGR skin (4a5196c). The audit (section 6 'launcHER: no skin code'), the inventory IGR row ('MISSING') and README:718 describe cfebe01 and are stale on the tip. When the IGR track's row replaces the inventory row, keep the three facts added here: return 0 with gp+0x38dc set, -666 after a failed folder check, and that a corpus PATCH_5.BIN replaces the same three pictures in the original and in launcHER.
3. tools/test_pops_doc_claims.py now fails CI when a tools/test_*.py file exists that is neither a build.yml step nor named in the ci-coverage block of docs/CLOUD_CONTINUATION.md. That is intended, but it means every track that adds a test must add its step (the IGR track did). With the reference input it also pins wording of the audit; rewording those sentences needs the test updated in the same commit.
4. test_pops_builtin_db.py and test_pops_progressive.py run in no workflow. In CI builtin_db would skip 14 of 14 without the reference input, so adding it changes little; progressive would run 3 of 8. Your call whether to add them.
5. Eight test files build into build/pops-host inside the checkout under fixed names, so two passes in one checkout collide whatever TMP is set to. Either keep the rule 'one pass at a time per checkout' (now written in CLOUD_CONTINUATION) or move those outputs under TMP in a later change.
6. New mentions of the REPOP working branch were written without its name ('a local working branch') because the name carries an assistant prefix; the older S18 row that names another REPOP branch was left as it was.

## doc updates


### inventory rows

Already applied in db36890; repeated here in case the lead applies by hand.

(1) `$USBDELAY_n` row, first cell after the name, full replacement:
handler `0x89dbe0`: `$USBDELAY_` + exactly one digit + a terminator writes byte `0x100017` (shipped value 1 in all four profiles, `2x`). Only consumer `0x879d04..0x879e58`: on `XX.`/`SB.` launches only, the byte replaces the word `DLAY` (`0x91fb30`) in the embedded PFS wrapper IRX. Run on a host with its imports modelled, the wrapper calls `thbase` import 33 once, with n x 1,000,000 (5,000,000 if unpatched), before its first backend open and in none of the later callbacks run (`2x` for the patch and the wrapper's arithmetic; `1x` for the call sequence, gap audit S28; that this is a `DelayThread` wait of n seconds on a real IOP is `inferred`, the wait itself was never observed)
(status cell unchanged: PARTIAL ...)

(2) TROJAN_n.BIN / PATCH_n.BIN row: replace the sentence "That the original's loader accepts all 509 is **measured once and under re-verification** on another track." with:
That the original's loader accepts all 509 was measured on a host three times with three separate harnesses (`2x`; gap audit S27); file calls were models and no payload was executed.

(3) IGR menu skin row, description cell: replace "no TIM2 check, never fatal (`2x`)" with:
no TIM2 check, no file outcome is an error (`2x`). The function returns 1 then; it returns 0 without opening anything when the abort flag `gp+0x38dc` is set, and -666 with that flag set after a failed POPS folder check (gap audit section 6, S23). A community `PATCH_5.BIN` also replaces these three pictures, in the original and in launcHER (S27)
(The status cell still says MISSING in this worktree; the IGR track's status replaces it.)

(4) Ranked increment (a): replace "Waits on the re-verification of the corpus result." with:
The corpus result it rests on has been re-run (gap audit S27).

### quirks

No behaviour changed, so no quirk became live. Candidate entries (no numbers) for when the features land:

- `$USBDELAY_n`: POPStarter takes exactly one digit; without the command the shipped value is 1; if the wrapper's delay word is never patched (launch that is not `XX.`/`SB.`) the wrapper's own fallback is 5. The value is used once, before the wrapper's first open. Copy as is. Host emulation of the wrapper only; the wait was never observed. NOT TESTED on a console.

- IGR skin and PATCH files: a `PATCH_n.BIN` whose payload covers `0x2feff0..0x34ee70` replaces the three IGR pictures. In POPStarter the skin call (`0x876b18`) comes before both PATCH passes (`0x876e00`, `0x877118`), so such a PATCH wins over `IGR_*.TM2`. The order is inferred from the call sites; the two were not run in sequence. One file in the community corpus does this.

- Quiet mode (MAIN profile) is not fully quiet: some print calls are not behind the `gp+0x38b0` test, among them `DONE` and a newline in the BIOS.BIN handler. Cosmetic; nothing to copy unless launcHER reproduces POPStarter's console output.

- BIOS.BIN, game scope: the first current-game loader that runs checks the game folder once (`gp+0x38e0`); a missing folder sets `gp+0x3460` and returns -666 before any file is opened. Copy with the six loader flags.

### hardware checklist

Nothing here was run on a console. Items this round adds or sharpens:

- `$USBDELAY`, USB and SMB: with original POPStarter r13, time from launch to the first disc read with no command, `$USBDELAY_0`, `$USBDELAY_5`, `$USBDELAY_9`. Expected from the code (never observed): about 1 s, 0 s, 5 s, 9 s, once. Then the same with launcHER, which today sleeps on the EE on any device and not at all without the command.
- A game with a real community `TROJAN_n.BIN` beside it: confirm launcHER stops with "Fix file rejected" and POPStarter runs the game.
- The community `PATCH_5.BIN` that carries IGR pictures: confirm the exit dialog shows them under `$IGR0..2`, in POPStarter and in launcHER.
- BIOS.BIN in a game folder that does not exist on the device: POPStarter's behaviour after the -666 return (main's handling was not run).

### user facing

Already applied in db36890 (README.md:688 and docs/pops-setup.html:306), `$USBDELAY` wording:
"POPStarter accepts a single digit, uses 1 second without the command, and on USB and SMB launches passes the number to its own file wrapper, which appears to wait that many seconds once, before the first file it opens. That description comes from POPStarter's code, read and partly run on a PC with the console's services replaced by models; the wait itself has never been observed. Not tested on a console."

NOT applied, for the lead to add after the IGR track's text for README.md:718 and docs/pops-setup.html:554:
"A `PATCH_n.BIN` fix file can also replace these three pictures: one file in the community fix packs (a `PATCH_5.BIN`) does, and launcHER's fix-file code writes the same bytes for it as POPStarter's loader (compared on a PC; not tested on a console)."

docs/CLOUD_CONTINUATION.md (applied): use a clean export of REPOP `bc258e48`, not the worktree; a machine-checked list of which test files no workflow runs; run the two test passes one after the other in one checkout; results of the second run of the day (27 files, all exit 0 both ways).
