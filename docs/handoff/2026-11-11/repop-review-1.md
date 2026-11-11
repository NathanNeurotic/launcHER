# REPOP batch 26: review 1

Written by an independent reviewer of the track. Copied as written.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## verdict

issues

## issues

1. **severity:** major  
   **description:** Three single-line mutants of pops_patch_alloc_block (FUN_0099EE60, slib_exp_lib_list) in popstarter/src/patch_engine.c pass all 9 tests of tools/tests/test_popstarter_copy_leaves.py, including the 174-case compiled differential, although each changes behaviour against r13. The accept/reject boundary of the export-table search is therefore not pinned by the repository's own tests. (G) not-found test `if (i >= 0x200)` -> `if (i > 0x200)`; (N) table magic compared on the low 16 bits only; (O) `lui` test ignoring the rs field (`hi & 0xfc1f0000`). The production code itself is correct on all of these inputs in my independent run; the gap is in the committed evidence.  
   **evidence:** Mutation driver on the worktree with EE gcc on PATH and build/popstarter_unpacked.bin present: G 'SURVIVED (189 s) Ran 9 tests ... OK', N 'SURVIVED (202 s) Ran 9 tests ... OK', O 'SURVIVED (233 s) Ran 9 tests ... OK'. Same mutants built into a production-flag link and run in my own Unicorn harness against the r13 copy: G 73 of 300 random explist cases different and 84 of 260 directed cases (candidate returns the list address or faults where r13 returns 0); N 43 of 200 directed cases different (v0 orig 0x0, cand 0x1453c80); O 34 of 200 different. Unmutated HEAD: 0 different on the same cases. The verifier's 19 explist cases put the table only at offsets 0, 4, 0x40, 0x1f8, 0x1fc, use one wrong-magic value and one wrong-lui value, and its not-found cases happen to read zeros beyond +0x200.  
   **suggested fix:** Add explist scenarios to tools/verify_popstarter_copy_leaves.py: (a) a fully valid table and valid lui/addiu function placed at offset 0x200 and 0x204 (must return 0 without touching the list words); (b) a table whose magic is 0x830 in the low half with a non-zero high half and a correct name and function; (c) a function whose first word is 0x3c02xxxx with a non-zero rs field (e.g. 0x3c620000). Add G, N and O (or equivalents) to MUTATIONS so the bound stays pinned, and update the 174/19 counts in the docs and commit text.
2. **severity:** major  
   **description:** README.md was edited in commit 33a0554a (the POPStarter status paragraph). README.md is on the reviewer brief's list of shared docs that must stay untouched. The other five files on that list do not exist in this repository, so the list may have been written for a different checkout; if it does apply here this is a process violation. The numbers in the edited paragraph themselves check out (440 of 466, 94.4%, 91.2%, 597,012, 68.2%, 17.2%, 20 left).  
   **evidence:** `git show --stat 33a0554a`: 'README.md | 2 +-'. docs/POPSTARTER_R13_INVENTORY.md, docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md, docs/CLOUD_CONTINUATION.md, docs/PR23_CHECKPOINT_HISTORY.md and docs/pops-setup.html are absent from the tree at HEAD and none was added.  
   **suggested fix:** Either drop the README.md hunk from the branch and hand the paragraph back as text for the owner of that file, or have the orchestrator confirm that this repository's README.md is not covered by the off-limits list.
3. **severity:** minor  
   **description:** The repository's differential compiles nine functions cut out of the two C files standalone (-O2 -G0 -ffreestanding -fno-builtin). Nothing in the repository executes the production objects, the linker bindings in runtime_symbols.ld, or the three callers; those are only text-pinned. The shipped fio init differs from the tested candidate (bnez after the bind where the candidate and r13 have bltz), and a mutant that writes the production form into the source (`r < 0` -> `r != 0`) is rejected by the repository's test, so the test would fail the code that actually ships if it could see it. The doc discloses this limit. My independent run of the production link found no reachable difference.  
   **evidence:** Mutant M 'CAUGHT ... "kind": "fioinit"'. Production prod.elf / CI ELF: pops_jit_hook_009a0178 is 444 B with bnez; my harness kind fioinit_pos (bind stub returns a positive value): 14 of 20 cases different. r13 bind at run 0x01453338 returns only 0, -0xD610, -0xD611, -0xD602, so the input is unreachable in r13.  
   **suggested fix:** Optionally add a second candidate mode that links the real objects (or compiles the whole translation units with production flags) and runs the same scenarios through the linker names; state in the source comment at the bind test that the build's form depends on the rebuilt bind never returning a positive value.
4. **severity:** minor  
   **description:** The compiled differential is gated on build/popstarter_unpacked.bin (a gitignored local file) plus the EE compiler on PATH, not on POPSTARTER_TEST_ELF. Setting the reference-input variables alone does not enable it; it skips silently with 'external original and EE compiler required'. In CI it always skips, so CI exercises only the eight source/contract tests of the new file.  
   **evidence:** tools/tests/test_popstarter_copy_leaves.py: `image = ROOT / 'build/popstarter_unpacked.bin'; if not image.exists() or not shutil.which('mips64r5900el-ps2-elf-gcc'): self.skipTest(...)`. Run with unicorn/capstone blocked and no compiler: 'Ran 9 tests ... OK (skipped=1)'.  
   **suggested fix:** Unpack from POPSTARTER_TEST_ELF when it is set (as other tests in tools/tests do), or name the exact preparation command in the skip message.
5. **severity:** minor  
   **description:** docs/POPSTARTER_CLAIM_AUDIT_2026-11-01.md says 'EE build 7 of 7 OK in the CI container'. The CI script tools/ci/build_ee.sh reports nine results, not seven; the 7 comes from a local, untracked loop over seven directories (build/ee_build_test.sh).  
   **evidence:** My run of `bash tools/ci/build_ee.sh` on a clean `git archive HEAD` export inside ghcr.io/ps2homebrew/ps2homebrew:main (GCC 15.2.0): SUMMARY lists PASS for pops, popstarter, dkwdrv, superpsx, ps2psxe-ee, ps2psxe-iop, ember, ember-launcher, tonyhax; rc 0; popstarter warnings 2 (pfs_wrap.c:65 strncpy truncation, runtime_hooks.c:4792 unused variable).  
   **suggested fix:** Quote the CI script's own count (9 of 9 PASS) or name the script the 7 came from.
6. **severity:** minor  
   **description:** FUN_0099FBB0 tests the close hook's result as a 32-bit value (nor / srl 31) while the build tests the 64-bit register with bltz. They agree for every sign-extended 32-bit result; they would differ only for a hook returning a non-sign-extended 64-bit value. Theoretical; not observed in any run.  
   **evidence:** blob disassembly at run 0x014517A0 versus prod.dis of pops_patch_verify_checksum (176 B). 800 of 800 fclose cases and 150 of 150 fcloseall cases identical in my harness with sign-extended hook results.  
   **suggested fix:** None needed beyond a note in the function comment.
7. **severity:** minor  
   **description:** Mutant A (`for (i = 0; i < 0x200; ...)` -> `i <= 0x200`) also survives the repository's tests, but it is observationally equivalent: the following `if (i >= 0x200) return NULL` still rejects, and the only effect is one extra in-buffer read. Recorded so it is not mistaken for a fourth gap.  
   **evidence:** Repo tests: 'SURVIVED (245 s)'. My harness on a production link of the mutant: 0 different in 300 random and 60 directed offset-0x200 cases.  
   **suggested fix:** None.

## independent checks

1. All results below are host/Unicorn results. NOT TESTED on a console; nothing here is a console result.
2. Read the full diff bc258e48..0a440b01 (18 files, +1578/-158) and both new files. Hand-read the r13 disassembly of the six functions (objdump mips:5900 of the 0xE880-byte copy at run 0x01450000, taken from the unpacked image sha256 185177c2...08aee) against the new C: call order, delay-slot stores, OR-join of the lui/addiu halves, both list words read before either store, errno = negated comparison, types 0/1/2/0x20 -> -1, zero-extended module id, unbounded export count, memcpy of 0x14 + count*4. No mismatch found.
3. Own differential harness (rv_harness.py in the reviewer scratch dir; own stubs, own generators, seed 0xb26a11ce; no code from the implementer's verifier). Original side: the r13 copy at its run address with Python models for DI/EI/CreateSema/DeleteSema/sceSifInitRpc/sceSifBindRpc/close hook/memcpy/memset/strlen (the original memcpy/memset/strlen use lq/sq/MMI and cannot run in Unicorn). Candidate side: all 12 popstarter sources compiled with the production flags and linked with popstarter/runtime_symbols.ld, entered through the four rebound linker names and through the three callers. Compared: v0 (64 bit), ordered service calls with arguments, a digest of 0x01453B00..0x0145E880 and scratch at each call, final memory, IOP RAM digest, Status, callee-saved registers, wait-loop passes.
4. Harness results, production objects vs r13: teardown 200/200 identical; fio init 200/200; fclose 800/800; smod_get_mod_by_name 500/500; slib_exp_lib_list 769 identical + 31 where both sides fault identically (of 800); slib_get_exp_lib 498 + 2 both-fault (of 500); caller FUN_0099F8E0 150/150; caller FUN_0099EBA0 200/200; caller FUN_0099E968 292 + 8 both-fault (of 300); fio init with waits 6/6 with equal pass counts. Total 3,656 random cases, 0 different. Added directed cases: table at offsets 0x1f8/0x1fc/0x200/0x204 60/60 identical; wrong-magic-high-half, lui-with-rs, wrong addiu/lui variants 200/200 identical.
5. Only difference found: a positive bind result (14 of 20 forced cases). The build returns it (bnez) where r13 continues (bltz). r13's bind at run 0x01453338 returns only 0, -0xD610, -0xD611, -0xD602, so it is unreachable; the doc's table discloses it.
6. Sizes of the six in the production link: 444/116/176/340/348/420 bytes, matching the doc's table. Compared the nine entry functions and every same-file callee reached from them between my ps2build link (GCC 15.3.1) and the POPSTARTER.ELF I built in the CI container (GCC 15.2.0): instruction words identical with call targets matched by symbol name for all six rebuilt functions, the three callers, pops_patch_memcpy/memset, smem helpers (differences only in address immediates of two unrelated functions and in my libc stand-ins). The harness results therefore apply to the container-built code.
7. Doc numbers re-derived from the image: main 0x00870B78-0x0087C218 46,752 B frame 0x1630; 0x00883270-0x008D4F84 335,124 B; 0x008E00D0-0x008FF0E4 126,996 B; 0x008FF0E4-0x00914930 88,140 B; one prologue, one jr ra, no jal into the interior from code (one jal-looking word at 0x977BFC is ISO descriptor data); callers as listed; total 597,012; 734,708; 17.2%/17.0%, 68.2%/67.5%, 91.2%/90.2%; six chunks 968 B; FUN_00914800 claims hold. 1372 bytes added = sum of the six GT sizes; 20 unclaimed functions sum to 11,276 B.
8. Config claims re-derived: four profiles 167,700 B each, MAIN sha256 734c813e..., differences only at 0x410/0x413 as tabled; load segment file 0x400 -> 0x00100000; 0x00870DA4 reads 0x100010, 0x00870E4C reads 0x100013; FUN_00870930 copies the word at 0x009AE90C and counts to -1 (0x02000001 passes at default); main 0x00879D50-0x00879E58 scans the module at 0x0091F680 for 'DLAY' in 4-byte steps up to the word at $gp+0x2890 (0xA45) and writes byte 0x100017 plus three zeros; marker at 0x0091FB30; 0x0089DBE4-0x0089E124 compares '$USBDELAY_' and digits 0-9 and calls FUN_008D6B9C(n, 0x100017).
9. Abort-flag comment claims re-derived: one clearing store in main (0x00870C38), ten `li v0,1` stores in eight functions, seven early reads outside main, 15 reads in main.
10. Git claims in the continuation doc checked (69/12 commit counts, not an ancestor, tip d3452068, nine draft files on the wip branch).
11. Hygiene: commits 8f57231d and a10b3319 change comments only in C files; 0a440b01 changes a Python comment only. No binary files added; the only long hex string added is a sha256 pin; scenario data in the verifier is generated, not copied. All six commits authored by the repository owner; no co-author or tool trailers; added text contains no assistant attribution (two existing branch names beginning `claude/` are referenced as refs). The earlier co-author instruction in the continuation doc was replaced by the no-attribution rule. build/popstarter_unpacked.bin and popstarter/POPSTARTER.ELF are gitignored and untracked.
12. CI wiring: new step in the host-smoke job runs the new test file; with unicorn/capstone unavailable and no compiler it runs 9 tests, 1 skipped, OK.
13. Worktree left as committed: `git status` clean at 0a440b01 on pr23/popstarter-batch26; every mutant reverted with git checkout; the container build ran on a `git archive` export in the scratch directory.

## mutants

1. A patch_engine.c explist loop bound `i < 0x200` -> `i <= 0x200`: SURVIVED the repo tests; equivalent mutant (0 differences in my harness, 360 cases).
2. B patch_engine.c fclose `fd >= 0` -> `fd > 0`: CAUGHT (kind fclose).
3. C patch_engine.c module name read length 0x3c -> 0x40: CAUGHT (kind modname).
4. D patch_engine.c explib head test `list[1] == 0` -> `list[0] == 0`: CAUGHT (kind explib).
5. E runtime_hooks.c fio init first CreateSema `id < 0` -> `id <= 0`: CAUGHT (kind fioinit).
6. F runtime_hooks.c teardown second semaphore `id >= 0` -> `id > 0`: CAUGHT (kind teardown).
7. G patch_engine.c explist not-found test `i >= 0x200` -> `i > 0x200`: SURVIVED the repo tests; real behaviour change (my harness: 73/300 random and 84/260 directed cases different).
8. I patch_engine.c explist addiu test reduced to opcode only: CAUGHT (kind explist).
9. M runtime_hooks.c fio init bind test `r < 0` -> `r != 0` (the form the production build compiles to): CAUGHT (kind fioinit).
10. N patch_engine.c explist magic compared on the low 16 bits only: SURVIVED the repo tests; real behaviour change (my harness: 43/200 directed cases different).
11. O patch_engine.c explist lui test ignoring the rs field: SURVIVED the repo tests; real behaviour change (my harness: 34/200 directed cases different).

## tests rerun

1. python -m unittest discover -s tools/tests -p 'test_*.py' without reference variables and without the EE compiler on PATH: Ran 296 tests in 179.5 s, OK (skipped=27).
2. Same with POPSTARTER_TEST_ELF, POPS_TEST_ELF set and the ps2build EE gcc on PATH: Ran 296 tests, OK (skipped=25); 'Compiled EE copy-leaf differential PASS: 174 component cases, 8 wrong candidates rejected'; 'Compiled EE CDVD ... PASS: 247 component cases'.
3. tools/tests/test_popstarter_copy_leaves.py alone with compiler and image: Ran 9 tests in 223 s, OK. Alone with unicorn/capstone blocked and no compiler: Ran 9 tests, OK (skipped=1).
4. Top-level tools/test_*.py with inputs: test_analyze_pfs_wrap 5 OK; test_analyze_popstarter_checkout 4 OK; test_compare_popstarter_profiles 5 OK; test_inspect_popstarter_embedded_irx 8 OK; test_recover_pops_io_contract 8 OK; test_unpack_popstarter_loader 2 OK.
5. python tools/audit_popstarter_claims.py --image build/popstarter_unpacked.bin: 367 claims; 254 calls-match, 110 leaf, 3 hollow, 0 partial/missing/disjoint; 0 claims calling a bare run address.
6. python tools/parity_report.py popstarter: 466 GT functions, 138,664 bytes, 440 claimed, 94.4% / 91.2%.
7. python tools/parity_check.py --baseline parity/baseline.json: 'Parity held.'
8. EE compile check: all 12 popstarter/src/*.c compiled with the production flags using the ps2build toolchain (GCC 15.3.1), rc 0, 2 warnings, and linked with runtime_symbols.ld into a scratch ELF.
9. bash tools/ci/build_ee.sh in ghcr.io/ps2homebrew/ps2homebrew:main (GCC 15.2.0) on a clean export of HEAD in the scratch directory: rc 0, nine PASS lines (pops, popstarter, dkwdrv, superpsx, ps2psxe-ee, ps2psxe-iop, ember, ember-launcher, tonyhax); popstarter warnings 2.

## unsupported claims

1. 'Eight deliberately wrong candidates ... are each rejected by that function's cases' is true as measured, but it must not be read as the cases pinning each function: three further single-line behaviour changes in FUN_0099EE60's C (not-found bound, magic width, lui rs field) pass all 174 cases.
2. 'EE build 7 of 7 OK in the CI container' (claim audit doc and the implementer's report): the CI script reports nine results; my run was 9 of 9 PASS. The count of 7 is not what tools/ci/build_ee.sh prints.
3. 'the ps2build archive build OK' / the report's ps2build build count: not re-run through ps2build by me. I only compiled the 12 popstarter sources with that toolchain's compiler and the production flags (rc 0) and linked them in scratch.
4. The doc's case table for FUN_0099EE60 ('the table at five offsets, wrong magic, ... wrong lui') describes what the cases contain accurately, but the offsets stop at 0x1fc and one wrong value each is used, so it does not support the bound at 0x200 or the full-width compares.
5. $410 row of docs/CONFIG_TABLE.md: the pause-count semantics for 0x01-0xFE and 0xFF (FUN_0087098C, flags at $gp+0x38B0 and $gp+0x3858) were not re-derived by me beyond the read at 0x00870DA4; the $413 and $417 rows were re-derived and hold.
6. Nothing in the batch was run on a console, and the docs and commit messages say so; no console claim is made. All verification, the implementer's and mine, is component execution under Unicorn with modeled services.
