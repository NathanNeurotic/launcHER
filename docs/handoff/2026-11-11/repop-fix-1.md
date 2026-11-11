# REPOP batch 26: answer to review 1

Written by whoever answered the review. Copied as written; not re-verified.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## summary

All results are host/Unicorn results. NOT TESTED on a console; nothing here is a console result.

Worktree REPOP:, branch pr23/popstarter-batch26, HEAD 6f7f638b, clean. Four new local commits on top of the reviewed 0a440b01; nothing pushed.

Resume: the earlier fixer left no commits, only an uncommitted edit of tools/verify_popstarter_copy_leaves.py (25 more cases, 8 more wrong candidates, a --built mode) and scratch scripts. I re-verified that edit myself before keeping it, then wrote the test changes, source comments, docs and README restore.

Major 1 (three mutants of FUN_0099EE60 pass all tests): REAL, reproduced. Against the committed tool, G (`i > 0x200`), N (magic low 16 bits) and O (lui ignoring rs) all pass. Fixed in tests, not in production code (the C was already right):
- 21 more cases for FUN_0099EE60 and 4 more for FUN_009A0178: 199 cases, all identical to r13 (was 174).
- G, N, O plus five more that I confirmed also passed the committed 174 cases are now wrong candidates the test requires the cases to reject by a difference: 16 in all (was 8).
- New test that needs no inputs and so runs in CI: a Python description of FUN_0099EE60 written from the function comment; five wrong variants must each give another answer on at least one case. On the first 19 cases none did, so this test would have caught the gap. With the original present its return value and list words equal r13's on 39 of 40 cases (the 40th reads the copy's own data).
- A 72-mutant run against the 199 cases: 60 rejected by a difference, 6 by a fault or compile error, 6 pass (listed in deviations/not_done).

Major 2 (README.md edited): REAL. README.md is restored byte for byte to its bc258e48 state in a new commit; the paragraph is returned in doc_updates.user_facing.

Minor 3 (nothing runs the production objects): addressed. --built runs the same cases on a linked POPSTARTER.ELF through the linker names. On the ELF I built in the CI container: 198 of 199 identical; the one difference is the positive bind result (build returns 5, r13 goes on), reported and not required. A source comment at the bind test states the dependency. The three callers are still not run.
Minor 4 (gating): the test now unpacks POPSTARTER_TEST_ELF into a temp dir when build/popstarter_unpacked.bin is absent, and the skip message names the command. Verified on a clean export.
Minor 5 ("7 of 7 in the CI container"): doc now names both scripts with counts I measured: tools/ci/build_ee.sh 9 of 9 PASS, build/ee_build_test.sh 7 of 7 BUILD OK. Note build/ee_build_test.sh is tracked, not untracked as the review said.
Minor 6 (64-bit vs bit-31 test in FUN_0099FBB0): confirmed by disassembly of both; noted in the function comment. Not run.
Minor 7 (mutant A): confirmed equivalent; recorded in the doc.

One thing to know about history: I recreated my own first three commits once (git reset to 0a440b01, same trees, recommitted) to correct two imprecise phrases in a commit message. The five reviewed commits were not touched.

## commits

1. 38a55b39 test(popstarter): pin the export-list search bound and run the built ELF
2. a3409a67 docs(popstarter): two result tests the build compiles in another form than r13
3. 791bdc9f docs: take the batch 26 status paragraph back out of README.md
4. 6f7f638b docs(popstarter): batch 26 after review: 199 cases, the built ELF run, the build counts

## files changed

1. REPOP:tools/verify_popstarter_copy_leaves.py
2. REPOP:tools/tests/test_popstarter_copy_leaves.py
3. REPOP:popstarter/src/patch_engine.c (comment only)
4. REPOP:popstarter/src/runtime_hooks.c (comment only)
5. REPOP:docs/POPSTARTER_CLAIM_AUDIT_2026-11-01.md
6. REPOP:docs/POPSTARTER_CONTINUATION.md
7. REPOP:README.md (restored to its bc258e48 content)

## measured evidence

1. Reproduction of the major finding: reviewer mutants A, G, N, O run against the committed tool (git show HEAD:tools/verify_popstarter_copy_leaves.py at 0a440b01, 19 explist cases): 4 of 4 pass. Against the new tool: G, N, O rejected by a difference; A still passes (equivalent).
2. Five further single-line changes (addiu ignoring rs, text size not read, generation compared with <, flag compared with 1, first semaphore id tested before stored) run against the committed 174-case tool: 5 of 5 pass. Against the new tool: 5 of 5 rejected by a difference.
3. Compiled-EE differential, cut-out candidate (ps2build GCC 15.3.1) vs r13 copy under Unicorn: 199 cases (teardown 27, fioinit 21, fclose 77, modname 15, explist 40, explib 19), 199 identical; 16 of 16 wrong candidates rejected by AssertionError, not by a fault.
4. 72 single-line mutants (reviewer's 4 + 68 from the earlier fixer's list, rerun by me) against the 199 cases: 60 rejected by a difference, 6 by a fault or compile error, 6 pass. The 6: loop bound `i <= 0x200`, loop bound `i < 0x204`, halves joined with +, bit 15 of the lui immediate dropped, export count bounded at 186, export count bounded at 187.
5. Python description of FUN_0099EE60 vs r13 under Unicorn (no C involved): return value and both list words, 39 cases, 39 equal. Without any input: 39 of 40 cases answerable, 15 return the list, 24 return 0; each of 5 wrong variants differs on at least one case; all differing cases are among the 21 new ones.
6. Built-ELF mode on the POPSTARTER.ELF I built with tools/ci/build_ee.sh in ghcr.io/ps2homebrew/ps2homebrew:main (GCC 15.2.0) from an export of the code tree (sha256 f5f13b30...19bd7): 199 cases, 198 identical, 1 different (positive bind result: build returns 5 after rpc_init+bind, r13 returns 0 after both CreateSema calls). 2 of 2 wrong ELFs (one instruction word changed) rejected. Same result on the earlier local popstarter/POPSTARTER.ELF (sha256 cfcb6602...).
7. .text of my container ELF vs .text of the ELF the reviewer built from 0a440b01: identical (both sha256 a5e5aa54...4fae6). The two comment edits changed no code.
8. Built-ELF mode with caller-saved registers overwritten after each service: 5 kinds pass, explib fails (returns 0xFFFFFFFFDEAD010A, the value written to $12). This is why that mode leaves them alone, and it is a stated limit.
9. r13 bind function at run 0x01453338, disassembled in full (296 bytes): returns 0, 0xFFFF29F0 (-0xD610), 0xFFFF29EF (-0xD611) or 0xFFFF29FE (-0xD602) only. The rebuilt C returns the same four.
10. r13 FUN_0099FBB0 at run 0x014517EC: `nor v0,zero,v0; srl v1,v0,31`. Build: `bltz v0` after the jalr. Build FUN_009A0178: `bnez v0` after the jal to the bind. Read from objdump of the container ELF and capstone of the image.
11. tools/unpack_popstarter.py on POPSTARTER_TEST_ELF: 1,350,828 bytes, sha256 185177c2...08aee, equal to the tool's pin; about 6 s.
12. python tools/audit_popstarter_claims.py --image build/popstarter_unpacked.bin: 367 claims, 254 calls-match, 110 leaf, 3 hollow, 0 partial/missing/disjoint, 0 calling a bare run address. python tools/parity_report.py popstarter: 466 functions, 440 claimed, 94.4% / 91.2%. python tools/parity_check.py --baseline parity/baseline.json: Parity held. All unchanged from the review.

## tests run

1. **command:** Clean `git archive` export of 791bdc9f (same code as HEAD; HEAD adds two docs), no reference variables, no EE compiler on PATH, no build/popstarter_unpacked.bin: python -m unittest discover -s tools/tests -p 'test_*.py' -v  
   **outcome:** Ran 301 tests, OK (skipped=31)
2. **command:** Same clean export, same conditions: python tools/test_analyze_pfs_wrap.py, test_analyze_popstarter_checkout.py, test_compare_popstarter_profiles.py, test_inspect_popstarter_embedded_irx.py, test_recover_pops_io_contract.py, test_unpack_popstarter_loader.py  
   **outcome:** 5, 4, 5, 8, 8, 2 tests; all OK
3. **command:** Worktree at 791bdc9f code state, POPS_TEST_ELF and POPSTARTER_TEST_ELF set, ps2build EE gcc on PATH, POPSTARTER_BUILT_ELF = container-built ELF, build/popstarter_unpacked.bin present: python -m unittest discover -s tools/tests -p 'test_*.py' -v  
   **outcome:** Ran 301 tests in 493 s, OK (skipped=25). Printed: Compiled EE copy-leaf differential PASS 199 cases, 16 wrong candidates rejected; Built-ELF copy-leaf differential PASS 198 cases, positive bind result differs as recorded, 2 wrong ELFs rejected; CD gate 247 cases PASS. The 25 skips are pre-existing (12 'POPS.ELF not found', 9 POSIX host, 2 host cc/make, 1 Linux non-PIE, 1 'POPS.ELF not found on system'); POPS_TEST_ELF is not what those tests look for.
4. **command:** Worktree, same with-inputs conditions: the six tools/test_*.py files  
   **outcome:** 5, 4, 5, 8, 8, 2 tests; all OK
5. **command:** Final state, worktree at HEAD 6f7f638b, no variables, no compiler on PATH (build/popstarter_unpacked.bin present): discover over tools/tests plus the six tools/test_*.py  
   **outcome:** Ran 301 tests, OK (skipped=28); six top-level files all OK
6. **command:** Clean export, only POPSTARTER_TEST_ELF set plus EE gcc on PATH (no build image): python -m unittest discover -s tools/tests -p test_popstarter_copy_leaves.py -v  
   **outcome:** Ran 14 tests, OK (skipped=1, the built-ELF test). The image was unpacked to a temp dir; nothing written into the tree.
7. **command:** python tools/verify_popstarter_copy_leaves.py --image build/popstarter_unpacked.bin [--built <container ELF>] [--built-mutation ...]  
   **outcome:** default: 199 pass. --built: 198 pass, 1 reported. Both --built-mutation runs exit 1 with AssertionError as intended.

## ee build check

Three things, all on the final code (the only C changes are two comments).
1. ps2build toolchain (mips64r5900el-ps2-elf-gcc 15.3.1): all 12 popstarter/src/*.c compiled to objects with the flags recorded in build/popstarter-batch26/compile_commands.json (-D_EE -G0 -O2 -Wall -ffunction-sections -gdwarf-2 -gz). 12 of 12 rc 0, 2 warnings (pfs_wrap.c:65 strncpy truncation, runtime_hooks.c:4798 unused variable; both pre-existing). Not linked, and the ps2build project/archive build was NOT rerun.
2. CI container ghcr.io/ps2homebrew/ps2homebrew:main (GCC 15.2.0), on a git archive export of the code tree: bash tools/ci/build_ee.sh rc 0, 9 of 9 PASS (pops, popstarter, dkwdrv, superpsx, ps2psxe-ee, ps2psxe-iop, ember, ember-launcher, tonyhax); popstarter warnings 2.
3. Same container session: sh build/ee_build_test.sh rc 0, 7 of 7 BUILD OK (pops, popstarter, DKWDRV, superpsx-experiment, PS2PSXe/ee, PS2PSXe/iop, ember).
The export was of my first two commits' tree, which is identical to a3409a67's tree; the later commits change README.md and two docs only. The lead's own container build after merging is still needed for the merged tree.

## deviations from original

1. FUN_009A0178 (pops_jit_hook_009a0178), build form: the linked build tests the bind result with bnez where r13 has bltz. Measured: a positive bind result makes the build return it (5) while r13 goes on to both CreateSema calls. Neither r13's bind nor the rebuilt one returns a positive value, so it is not reachable today; it becomes a real difference if the bind function ever changes. Left as is; comment added.
2. FUN_0099FBB0 (pops_patch_verify_checksum): r13 takes bit 31 of the close hook's result, the build tests the sign of the 64-bit register. They differ only for a result with bit 31 set and the upper half clear. Read from disassembly; that input is NOT run by any test.
3. Form only, unchanged from the reviewed state: the six functions are 444/116/176/340/348/420 bytes in the build against 308/116/160/160/320/308 in r13, with different frames and inlining.
4. Unchanged from the reviewed state and not fixed here: the six read and write the copy's data at run addresses 0x01453C80-0x01454084, 0x0145DFC0 and 0x01454280, and this build copies nothing there; the close-hook word at 0x01453C8C is never written in this build. The differential gives both sides the image's data, so it does not see this.
5. Inputs where equivalence is not shown because they are not run: a name over 60 bytes in FUN_0099ED70; an export table with no zero word in 0x300 bytes in FUN_0099EFA0 (a mutant that bounds the count there passes); a lui immediate with bit 15 set is run in one case only, and a mutant that drops that bit passes because Unicorn maps 0x8xxxxxxx onto the low addresses.

## not done

1. NOT TESTED on a console. Every result is component execution under Unicorn with modeled services, or a host/container build.
2. The three callers (FUN_0099F8E0, FUN_0099EBA0, FUN_0099E968) are still not executed by any repository test, in either mode. The reviewer's own harness ran them; the repository does not.
3. CI still runs neither differential: both need the original image. CI now runs 12 of the 14 tests in the file, including the Python description that pins the search bound.
4. The built-ELF test only runs when POPSTARTER_BUILT_ELF names an ELF, and the tool does not check that ELF was built from the current tree.
5. Built-ELF mode leaves caller-saved registers untouched after a modeled service, so a build that wrongly relied on one across a call into another file would not be seen.
6. The 72-mutant list and driver are not in the repository (scratch: <scratch>/repop-b26-f1-fix/mut.py, extra2.py, camp3.out). Only the 16 wrong candidates are committed.
7. The ps2build project/archive build was not rerun; the doc no longer claims it for this state. The earlier commit message of 33a0554a and the implementer's report still carry that claim.
8. The reviewer's unsupported-claim note on the $410 row of docs/CONFIG_TABLE.md (pause-count semantics) was not re-derived by me and is unchanged.
9. 'EE build 7 of 7 OK' in the batch sections before batch 26 is left as written; the batch 26 paragraph now says which script that count comes from.
10. The temp-dir isolation in the brief did not take effect for Python's tempfile in at least one of my runs (it printed a path under <temp>). No collision occurred; two full runs ran concurrently and both passed.

## decisions for owner

1. README.md: I restored it to its bc258e48 content because the brief lists it as off-limits. If REPOP's README is not covered by that list (the other five listed files do not exist in this repository), reapply the paragraph in doc_updates.user_facing; as it stands the README says 434 of 466, dated 2026-11-02, while the docs say 440.
2. FUN_009A0178 bnez vs bltz: leave it as a documented form difference (what I did), or force the r13 form in the build, for example by keeping GCC from seeing the bind function's return range. That would change other callers' code generation, so I did not do it unasked.
3. Whether to commit the 72-mutant campaign as a tools/ deliverable so the surviving-mutant list can be regenerated.
4. I recreated my own three in-session commits once to correct a commit message (trees unchanged, reviewed commits untouched). Say if you would rather that never be done, even for unpushed commits of the same session.

## doc updates


### user facing

README.md status paragraph, removed from the branch and handed back as text (numbers as the reviewer re-derived them; I reran only the 440/466, 94.4%, 91.2% figures):

> **POPStarter status, 2026-11-11:** The reconstruction builds for EE again. A call-shape audit against the original removed every claim it showed wrong, and the functions have since been rebuilt from the disassembly: coverage is now 440 of 466 functions (94.4%), 91.2% of the ground truth's bytes (the pre-audit claim was 416 of 477; 11 entries have since been found to be IOP code and left the EE count). That byte figure is the share of the functions the ground truth kept. It leaves out four functions of 32 KB or more, 597,012 bytes together: `main()` (46,752 bytes) and three larger ones. Counting `main()`, byte coverage is 68.2%; counting all four, 17.2% ([measured here](docs/POPSTARTER_CLAIM_AUDIT_2026-11-01.md#not-in-the-ground-truth-three-more-oversized-functions-2026-11-11)). No linker name points at a bare run address any more ([batch 26](docs/POPSTARTER_CLAIM_AUDIT_2026-11-01.md#rebuilt-from-the-leaves-up-batch-26-2026-11-11-the-four-bare-run-addresses)); 20 functions are left. See [the claim audit](docs/POPSTARTER_CLAIM_AUDIT_2026-11-01.md) and [the continuation record](docs/POPSTARTER_CONTINUATION.md). Earlier 445-function / 1.00x-size and full-runtime claims stay withdrawn. Nothing has been run on a console.

### inventory rows

No launcHER inventory row changes from this fix. The fix changed tests, two source comments and two REPOP docs; it changed no behaviour. If an inventory row cites the batch 26 differential, the figures are now: 199 component cases (was 174), 16 wrong candidates rejected (was 8), and 198 of 199 identical on the container-built POPSTARTER.ELF. NOT TESTED on a console.

### quirks

Entries without numbers, both about how the REPOP build differs from r13 in form, not r13 quirks:

- REPOP build, file I/O client init (FUN_009A0178): the build tests sceSifBindRpc's result with `bnez` where r13 has `bltz`. A positive bind result would be returned by the build and treated as success by r13. Neither bind function returns a positive value (r13's returns 0, -0xD610, -0xD611 or -0xD602). Measured under Unicorn on the container-built ELF; not reachable today.

- REPOP build, fclose (FUN_0099FBB0): r13 takes bit 31 of the close hook's result; the build tests the sign of the 64-bit register. Same for every sign-extended result. Read from disassembly only; not run.

### hardware checklist

Nothing in this batch or this fix has been run on a console. Still to check on hardware once the copy's data is in place at 0x01450000: the fio client init and teardown (FUN_009A0178, FUN_009A02AC) against a real IOP reset; fclose through the real close hook at 0x01453C8C (FUN_009A0408, not rebuilt); smod_get_mod_by_name, slib_exp_lib_list and slib_get_exp_lib against real IOP RAM, including that the loadcore export table is found within the 0x200 bytes before the first module's text end.
