# REPOP batch 26: author's report

Written by the track's author when the stage ended. Copied as written; not re-verified.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## summary

Batch 26 is done and committed locally (6 commits on pr23/popstarter-batch26, base bc258e48; nothing pushed). Worktree: REPOP:. NOT TESTED on a console; every result below is host, emulator (Unicorn) or compiler output.

What changed: six functions of the code main() copies to 0x01450000 are rebuilt from the r13 disassembly: FUN_009a0178 (pops_jit_hook_009a0178, file I/O RPC client init with the wait loop), FUN_009a02ac (pops_jit_hook_009a02ac, its teardown), FUN_0099fbb0 (pops_patch_verify_checksum, close through the hook word), FUN_0099ed70 (pops_patch_read_disc_header, module-name match), FUN_0099ee60 (pops_patch_alloc_block, export-table walk) and FUN_0099efa0 (pops_patch_inject_cd_filter, export-library copy). The four linker names in popstarter/runtime_symbols.ld (pops_jit_check_ready_01451d68, pops_libcrypt_validate_entry, pops_jit_rpc_call, pops_runtime_01450960) now bind to C functions and the "Not rebuilt yet" block is deleted. The three callers (FUN_0099e968, FUN_0099eba0, FUN_0099f8e0) use corrected prototypes.

Measured on the final tree: audit 367 claims, 0 partial/missing/disjoint/runtime-missing/runtime-unchecked, 3 hollow, bare-run-address callers 0 (was 3). parity_report 440 of 466 (94.4%), 91.2% of bytes (was 434, 93.1%, 90.2%). parity_check "Parity held." New compiled-EE differential: 174 cases pass, all 8 deliberately wrong candidates rejected. CD gate 247 cases pass. Full unittest: 296 tests OK (25 skipped) with EE compiler and reference files, 296 OK (27 skipped) without. Native ps2build archive build exit 0; Docker CI-equivalent 7 of 7 BUILD OK.

Docs updated in the same branch: batch 26 section and corrected "Where this stopped" table (FUN_00914800 is a tail piece: 26 functions 12,648 B + 6 chunks 968 B) in docs/POPSTARTER_CLAIM_AUDIT_2026-11-01.md; a new section recording that 0x00883270, 0x008E00D0 and 0x008FF0E4 are oversized real functions the ground truth omits like main(), with the all-four figure (17.2% after, 17.0% before) next to 91.2%/90.2%; README and docs/RECOMPILATION_PROOF.md counts; docs/CONFIG_TABLE.md corrections for $410, $413, $417; "done flag" comments for gp+0x38DC changed to "abort flag"; docs/POPSTARTER_CONTINUATION.md dated 2026-11-11 section (main is the live line, feat/psxcore-validation superseded) and the AI co-author trailer instruction replaced with the owner's no-attribution rule.

The compiled forms of the six do not match r13 instruction for instruction (five of six differ in size); the differences are listed under deviations and in the audit doc. Behavioural equivalence is measured only for the standalone-compiled functions in Unicorn with modeled services, not for the production-inlined forms and not on hardware.

## commits

1. 0a440b01 test(popstarter): say what the service stubs work around
2. 33a0554a docs(popstarter): record batch 26 and the four functions the ground truth omits
3. 8f57231d docs(popstarter): the word at $gp+0x38DC is a shared abort flag
4. a10b3319 docs(popstarter): correct three config table entries from the files and r13
5. e161e957 test(popstarter): compiled-EE differential for the six rebuilt copy functions
6. cdbfeb9d feat(popstarter): rebuild the six copy functions behind the bare run addresses

## files changed

1. REPOP:popstarter/src/patch_engine.c
2. REPOP:popstarter/src/runtime_hooks.c
3. REPOP:popstarter/include/patch_engine.h
4. REPOP:popstarter/include/runtime_hooks.h
5. REPOP:popstarter/runtime_symbols.ld
6. REPOP:tools/verify_popstarter_copy_leaves.py (new)
7. REPOP:tools/tests/test_popstarter_copy_leaves.py (new)
8. REPOP:.github/workflows/ci.yml
9. REPOP:docs/POPSTARTER_CLAIM_AUDIT_2026-11-01.md
10. REPOP:docs/POPSTARTER_CONTINUATION.md
11. REPOP:docs/RECOMPILATION_PROOF.md
12. REPOP:docs/CONFIG_TABLE.md
13. REPOP:README.md
14. REPOP:popstarter/src/main.c (comments only)
15. REPOP:popstarter/src/pfs_wrap.c (comments only)
16. REPOP:popstarter/src/trojan.c (comments only)
17. REPOP:popstarter/src/config.c (comments only)
18. REPOP:popstarter/include/config.h (comments only)

## measured evidence

1. Compiled EE vs original r13 (sha256 185177c2...08aee), tools/verify_popstarter_copy_leaves.py: the production source of nine functions (the six rebuilt plus three already-rebuilt callees) cut from patch_engine.c/runtime_hooks.c, compiled alone with EE GCC 15.3.1 -O2 -G0, run in Unicorn against the original copy code at 0x0145xxxx. 174 cases (teardown 27, fioinit 17, fclose 77, modname 15, explist 19, explib 19). Compared per case: return value, ordered service calls with arguments and nine watched words at each call, Status bits 3-4, wait-loop pass count, and final memory outside the stack window. Result: all 174 identical.
2. Same verifier with 8 deliberately wrong candidates (teardown-flag-after-memset, fioinit-wrong-rpc-id, fioinit-second-descriptor-not-rewritten, fclose-errno-1-on-hook-failure, modname-signed-id, explist-sign-extended-low-half, explist-store-before-second-read, explib-copies-terminator): each one rejected with an AssertionError (8 of 8).
3. Claim audit (tools/audit_popstarter_claims.py against build/popstarter_unpacked.bin): 367 claims, 125,236 B; 254 calls-match, 110 leaf, 3 hollow, 0 calls-partial, 0 calls-missing, 0 calls-disjoint, 0 runtime-missing, 0 runtime-unchecked; claims calling a bare run address: 0. Before this batch: 361 claims, 249/109/3, 3 bare-run callers. The audit itself states calls-match and leaf are call-shape checks, not proof of equivalence.
4. parity_report popstarter: 440 of 466 ground-truth functions (94.4%), 126,420 of 138,664 bytes (91.2%). Before: 434 (93.1%), 90.2%. This counts source annotations, not verified behaviour.
5. parity_check against parity/baseline.json: all pillars held or improved, final line "Parity held.", exit 0.
6. CD gate (existing compiled-EE differential): 247 component cases pass on the final tree (run inside the full unittest suite; also run standalone earlier in the session, pass).
7. Linked ELF from the Docker build (popstarter/POPSTARTER.ELF, nm): pops_jit_check_ready_01451d68 = pops_jit_hook_009a0178 at 0x0010faf8; pops_libcrypt_validate_entry = pops_patch_verify_checksum at 0x00109fb8; pops_jit_rpc_call = pops_patch_inject_cd_filter at 0x00109790; pops_runtime_01450960 = pops_patch_read_disc_header at 0x00109638; 0 symbols at 0x0145xxxx. Earlier in the session the six functions in the linked ELF were compared word for word (call targets masked) with the native archive: identical.
8. Compiled sizes from the fresh native archive (nm -S) vs r13: FUN_009a0178 444 B vs 308; FUN_009a02ac 116 vs 116; FUN_0099fbb0 176 vs 160; FUN_0099ed70 340 vs 160; FUN_0099ee60 348 vs 320; FUN_0099efa0 420 vs 308. Five of six differ in size; the objdump read of all six and the form differences are recorded in the audit doc.
9. Oversized functions re-derived from the image (4 cases): main 0x00870B78-0x0087C218 46,752 B; 0x00883270-0x008D4F84 335,124 B; 0x008E00D0-0x008FF0E4 126,996 B; 0x008FF0E4-0x00914930 88,140 B. Each has one prologue, one jr ra with a matching epilogue, and no EE jal into its interior. Total 597,012 B; six CLEAN pieces inside them 968 B; denominator with all four 734,708 B, giving 17.02% before and 17.21% after this batch (main-only 67.46% to 68.20%).
10. FUN_00914800 (1 case): first word is nop, no jal targets it, a branch at 0x009147FC enters at 0x0091481C, and its only stack adjustment is the +0x30 epilogue at 0x0091492C. It is the tail of the function at 0x008FF0E4, not a function.
11. Config bytes read in four profile files (167,700 B each): MAIN $410=0x00, $413=0x02, $417=0x01; DEBUG $410=0xFF; USBDELAY $413=0x06; USBDELAY_DEBUG has both; no other differences among the four.

## tests run

1. **command:** python tools/audit_popstarter_claims.py --image build/popstarter_unpacked.bin  
   **outcome:** exit 0. 367 claims: 254 calls-match, 110 leaf, 3 hollow, 0 partial/missing/disjoint/runtime-missing/runtime-unchecked; bare-run-address callers 0.
2. **command:** python tools/parity_report.py popstarter  
   **outcome:** 440 of 466 (94.4%), 91.2% of bytes (126,420 of 138,664).
3. **command:** python tools/parity_check.py --baseline parity/baseline.json  
   **outcome:** exit 0, "Parity held." (popstarter and pops improved, others held).
4. **command:** python tools/verify_popstarter_copy_leaves.py --image build/popstarter_unpacked.bin (EE GCC 15.3.1 on PATH)  
   **outcome:** exit 0, result pass, 174 cases (teardown 27, fioinit 17, fclose 77, modname 15, explist 19, explib 19).
5. **command:** python -m unittest discover -s tools/tests -p 'test_*.py' (EE compiler on PATH, POPS_TEST_ELF and POPSTARTER_TEST_ELF set), on HEAD 0a440b01  
   **outcome:** Ran 296 tests in 265.8 s, OK (skipped=25). Printed: CD gate PASS 247 component cases; copy-leaf differential PASS 174 cases, 8 wrong candidates rejected.
6. **command:** python -m unittest discover -s tools/tests -p 'test_*.py' (no EE compiler on PATH, no reference env)  
   **outcome:** Ran 296 tests in 58.9 s, OK (skipped=27). The compiled differentials skip in this mode.
7. **command:** ps2build build --config ps2.yaml --out-dir build/popstarter-batch26 --toolchain gcc (fresh, after rm -rf of the out dir; tree at 33a0554a)  
   **outcome:** exit 0, 53 of 53 steps; popstarter warnings 2 (pfs_wrap.c strncpy truncation; runtime_hooks.c s_last_translated set but unused).
8. **command:** MSYS_NO_PATHCONV=1 docker run --rm -v "REPOP::/workspace" -w /workspace ghcr.io/ps2homebrew/ps2homebrew:main bash /workspace/build/ee_build_test.sh (tree at 33a0554a)  
   **outcome:** exit 0. pops, popstarter (errors=0 warnings=2, POPSTARTER.ELF MIPS R3000), DKWDRV, superpsx-experiment, PS2PSXe/ee, PS2PSXe/iop, ember: all RESULT: BUILD OK (7 of 7). git status clean afterwards.
9. **command:** mips64r5900el-ps2-elf-objdump / nm read of the six functions in build/popstarter-batch26/lib/libpopstarter.a and popstarter/POPSTARTER.ELF  
   **outcome:** Read; form-only differences listed in the audit doc and under deviations. Sizes 444/116/176/340/348/420 B.
10. **command:** tools/ci/smoke_host.sh  
   **outcome:** NOT RUN: no make on this Windows host.

## ee build check

Two EE builds, both on the committed tree at 33a0554a (the one later commit, 0a440b01, changes a Python comment only). (1) Native: ps2build build --config ps2.yaml --out-dir build/popstarter-batch26 --toolchain gcc with EE GCC 15.3.1, fresh out dir, exit 0, 53 of 53 steps, producing lib/libpopstarter.a, lib/libpops_core.a and bin/repop_ee_probe.elf; popstarter warnings 2 (pfs_wrap.c strncpy truncation, runtime_hooks.c unused s_last_translated). (2) Docker CI-equivalent (ghcr.io/ps2homebrew/ps2homebrew:main, EE GCC 15.2.0 as reported by the first run, build/ee_build_test.sh): exit 0, 7 of 7 projects BUILD OK, popstarter errors=0 warnings=2, popstarter/POPSTARTER.ELF linked (MIPS R3000 ELF). In that ELF the four former bare-address names resolve to the C functions and no symbol sits at 0x0145xxxx. Nothing was loaded or run on a PS2: NOT TESTED on a console.

## deviations from original

1. Size and form: five of the six compiled functions are not the same size as r13 (444/176/340/348/420 B vs 308/160/160/320/308); only FUN_009a02ac is 116 B in both. None is claimed instruction-identical.
2. FUN_009a0178 (production build): frame 0x50 vs r13 0x40; FUN_009a02ac is inlined into it; the wait loop's delay slot is a nop where r13 has lui a1,0x8000; one extra nop before the first pass.
3. FUN_009a0178 after the bind call: the production build emits bnez v0 where r13 has bltz. GCC derives this from the rebuilt FUN_009A1748 returning only 0 or negative. If the original bind could return a positive value, r13 would continue and this build would not. The standalone differential models bind and does not exercise this production form.
4. FUN_009a02ac: no frame on the early-return path; the second DeleteSema is a tail jump.
5. FUN_0099fbb0: frame 0x10 vs 0x20; the hook is called with jalr t9; the result test is bltz.
6. FUN_0099ed70: frame 0x90 vs 0x80; FUN_0099ed20 and the compare are inlined; the shared-memory read is called twice and inlined once; the compare pointer lives in a stack slot.
7. FUN_0099ee60: frame 0x10 vs 0x50; a pointer walk replaces r13's indexed loop.
8. FUN_0099efa0: frame 0x340 vs 0x390; memcpy length computed as (count+5)<<2.
9. This build does not copy the 0xE880-byte blob to 0x01450000, so the copy's data at 0x0145xxxx is not populated. The close hook word at 0x01453C8C is therefore empty here and FUN_009a0408 (what it points at in r13) is not rebuilt; FUN_0099fbb0's hook-present path only works in the differential, where the harness writes the word.
10. The differential compiles the functions standalone, so it does not cover the production inlining and inter-procedural forms above; it is evidence for the source, not for the linked object.
11. Cases that read stack bytes the original never wrote are not run (module name longer than 60 bytes; export table with no zero word within 0x300 bytes), so behaviour there is unmeasured.
12. The emulator is Unicorn MIPS64 (not an R5900); DI, EI, memcpy, memset, strlen, CreateSema, DeleteSema, sceSifInitRpc, sceSifBindRpc and the close hook are Python models; the CreateSema model overwrites descriptor words; IOP RAM is a 2 MB model reached only through memcpy from 0xBC000000.
13. The existing C names (pops_patch_verify_checksum, pops_patch_read_disc_header, pops_patch_alloc_block, pops_patch_inject_cd_filter, pops_jit_*) do not describe what the code does; they were kept to avoid a rename in this batch.
14. popstarter/src/config.c still initialises debug_display to 0xFF, while the MAIN profile file has $410 = 0x00 (0xFF only in DEBUG). Only the comments and docs/CONFIG_TABLE.md were corrected.

## not done

1. NOT TESTED on a console: nothing from this batch was run on a PS2 or on the rig.
2. Host smoke script tools/ci/smoke_host.sh not run (no make on this machine).
3. The new CI step in .github/workflows/ci.yml has not run in CI (nothing pushed); it was only run locally as the unittest module.
4. No differential mode for the production object: the linked forms (inlining, bnez after bind) are read by objdump, not executed against the original.
5. Ground truth not regenerated for the three additional oversized functions (0x00883270, 0x008E00D0, 0x008FF0E4); they are documented as omitted, with the 17.2% figure, but parity_report still uses the 138,664 B denominator.
6. 20 EE functions remain unclaimed (11,276 B) plus 6 chunks (968 B), including FUN_0087cf68 (5,240 B), FUN_0099df08, FUN_0099e404 and FUN_009a0408.
7. parity/baseline.json not promoted; the stale "Reconstruction coverage" paragraph in docs/RECOMPILATION_PROOF.md (0.20% pops, 0.00% elsewhere) was left as is.
8. The $USBDELAY_n text command was traced in the image (0x0089DBE4-0x0089E124) but no command file was used to verify it end to end.
9. Variables named done that hold the abort flag were not renamed; only comments changed.
10. Nothing pushed, no PR opened or edited.

## decisions for owner

1. config.c default: change debug_display's built-in default from 0xFF to MAIN's 0x00, or keep 0xFF? Left unchanged because it alters behaviour.
2. The bnez-vs-bltz after bind in FUN_009a0178 depends on the rebuilt FUN_009A1748 never returning a positive value. Accept as form-only, or force the r13 test (for example a noinline/opaque return) so the linked code matches regardless?
3. Ground-truth rule for functions of 32 KB and more: regenerate the ground truth to include the four oversized functions (headline byte coverage would read about 17.2% instead of 91.2%), or keep them documented beside the headline as now?
4. Promote parity/baseline.json to the new 94.4% / 91.2% so later regressions are caught?
5. Rename the misleading C names of the six functions (and the done variables that are an abort flag) in a separate commit?
6. Rewrite or delete the stale "Reconstruction coverage" paragraph in docs/RECOMPILATION_PROOF.md?
7. Whether the build should eventually populate the copy's data at 0x0145xxxx (or relocate those references), since the close hook word and other copy data are empty in this build.

## doc updates


### hardware checklist

No hardware item can be ticked from this batch: nothing was run on a console. Candidates to add for a later rig run: the file I/O client init and teardown path (FUN_009a0178/FUN_009a02ac), close through the hook word (FUN_0099fbb0), and the module-name and export-table paths used by FUN_0099e968, FUN_0099eba0 and FUN_0099f8e0. All are currently emulator-only evidence.

### inventory rows

popstarter: 440 of 466 ground-truth functions claimed (94.4%), 91.2% of bytes (126,420 of 138,664); with main() counted 68.2%; with all four oversized functions counted 17.2% (126,420 of 734,708). Unclaimed: 20 functions (11,276 B) and 6 chunks (968 B). Audit: 367 claims, 254 calls-match, 110 leaf, 3 hollow, 0 bare-run-address callers. Compiled-EE differentials: CD gate 247 cases, copy functions 174 cases.

### quirks

Recorded in the batch 26 section of docs/POPSTARTER_CLAIM_AUDIT_2026-11-01.md as original behaviours kept: the close function reports errno 0 when the hook fails; the module-name comparison is a prefix match; the export count is not bounded; the export address is joined with OR from two halves; a positive bind result is treated like 0. Also recorded: the word at $gp+0x38DC is a shared abort flag (main clears it at 0x00870C38, eight functions set it), not a done flag; this build populates nothing at the copy's data addresses.

### user facing

docs/CONFIG_TABLE.md corrected from the profile files and r13: $410 default is 0x00 on MAIN (0xFF only in DEBUG); $413 is a busy-loop count (n << 24 passes, 0x02 on MAIN, 0x06 on USBDELAY), not a time; $417 is live, the PFS wrapper delay (DLAY) patched into the embedded wrapper. README status line now reads 440 of 466 (94.4%), 91.2%, dated 2026-11-11, with the 68.2% and 17.2% figures.
