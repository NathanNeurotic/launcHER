# pr23/cfg-2: answers to review 2 of the CHEATS.TXT command pass

Branch `pr23/cfg-2`, head `83ba2ac` (on top of `c05ddb6`), pushed to origin (`git push -u origin pr23/cfg-2`). No force-push, nothing pushed to codex/popstarter-replacement, EMBER or any tag. No Ember, shared launch or storage-driver code changed. None of the five shared docs was edited.

Nothing was run on a console: NOT TESTED on a console. No PCSX2, no rig. "Under emulation" below means Unicorn runs of the original's routines inside the host tests.

`83ba2ac` has a `wip(pops):` subject because I committed and pushed it before the long test runs. Its message lists what was untested at that point. All of that was run afterwards on exactly this commit (results below), and no file changed after it. Its message is now out of date on that one point. I did not rewrite it.

Files changed in `83ba2ac`: `tools/test_pops_features.py`, `tools/test_pops_config_text.py`, `common/src/pops_config.c` (comments only), `common/include/pops_config.h` (comments only), `docs/POPSTARTER_CONFIG_TEXT.md`.

## Findings

### 1. BLOCKER: test_pops_features.py fails on the head

Fixed. The test is in `test_config_parser_directives`.

- After the earlier `$480p` line, `$FORCEPAL` is now expected to change nothing: `(video_mode, forced_pal) == (4, 0)`. A comment says that the `$480p` gates it, as at `0x8987f0`.
- A fresh config (`pops_config_init`) checks `$FORCEPAL` on its own: `(2, 1)`. This keeps what the line used to test.
- The comment "PAL2NTSC/FORCENTSC are the original $NOPAL" was wrong. It now says they are launcHER's own tokens that set `POPS_VMODE_NOPAL`, last one wins, and that this is an owner question.
- Measured: `test_pops_features` Ran 29 OK (skipped=2) without inputs, and Ran 29 OK with inputs (full sweeps below).

### 2. minor: mutant C5 survives without inputs

Fixed. Two texts are added to FIXED: `"$30012345 1234 $NOPAL "` and `"$30212345 1234 $NOPAL "`. Their EXPECTED rows were recorded from the original under emulation (`<scratch>/cfg2fix/record.py`, output `<scratch>/cfg2fix/record.out`):

- `$30012345 1234 $NOPAL ` gives `([(15, '$NOPAL', True)], [(0, 14)])`.
- `$30212345 1234 $NOPAL ` gives `([(15, '$NOPAL', True)], [])`.

launcHER gave the same before the change. No FIXED text had a 14-column `3` code before.

Mutant C5, in its own git-archive copy with no reference inputs: `FAIL: Native.test_table`, `Lists differ: [] != [(0, 14)]`.

### 3. minor: mutant R4 survives (MODE digit search across LF)

Fixed. Three rows are added to `Native.test_launcher_token_bytes`: `("MODE\n3x ", 0)`, `("$MODE\n3x ", 0)` and `("MODE 3x ", 4)`. These pin today's behaviour. They do not change what is read: whether launcHER-only tokens are read at all is still an owner decision.

Mutant R4, no inputs: `FAIL: Native.test_launcher_token_bytes`, `4 != 0 : 'MODE\n3x '`. So under R4 the text gives mode 3, as the reviewer read from the code.

### 4. minor: mutant V3 survives ($480P keeps forced_pal)

Fixed. The test now checks launcHER's `forced_pal` against the original's word, rather than `video_mode`.

- `Original.compare` now asserts `cfg.forced_pal == gp+0x38a0` after the original's pass. That covers every text it compares: fixed, random, `$USBDELAY`, short files, token bytes and video random. launcHER's own video tokens do not touch `forced_pal`, so the check also holds for texts that contain them.
- `Original._two_files` asserts the same for the second file, both for the one config run through both texts and for `pops_config_discover`.
- Natively, `test_video_commands` and `test_video_two_files` assert `forced_pal == (region pass result is "forced")`. In every recorded table text the original left `gp+0x38a0` at 1 exactly where the region pass forces PAL (`record.out`). The Original tests check the word itself.
- Two texts are added to VIDEO_EXPECTED, recorded from the original: `"$FORCEPAL $480P $NOPAL "` and `"$FORCEPAL $480P $NOPAL $FORCEPAL "`, both `("off", True)`. The original's words were 0x38a0=0, 0x3864=1, 0x4fa0=0.

Mutant V3:

- No inputs: `FAIL: Native.test_video_commands` (`1 != 0 : '$FORCEPAL $480P $FORCEPAL '`) and `FAIL: Native.test_video_two_files` (`('$FORCEPAL ', '$480P ')`).
- With inputs, four Original tests fail as well: `test_fixed_texts`, `test_video_random`, `test_video_table` and `test_video_two_files`. That is 6 failures in all.

I agree with the reviewer that the launch result is probably the same either way. That is by reading, not measured. The word is pinned now anyway.

### 5. minor: wording of commit 2ccf68b

Agreed. History is not rewritten. For the PR text:

- In `2ccf68b`, "compared for every text" should read "compared for every text without a launcHER-only video token". That was 71 of the 1500 random texts, measured again in this run.
- Its subject "token bytes as the original" should read "launcHER's own token bytes: locale-independent classes, no 63-byte cut". The original has no such tokens.
- The proposed quirk "no command can differ (measured, 1428 runs)" should read "no command differed in 1428 runs; by reading, none can".

### 6. minor: comment says nothing clears gp+0x3864

Fixed. The `CMD_FORCEPAL` comment in `pops_config.c` now says the only store of zero there is the start-up clear (`0x870c90`). The `progressive_requested` comment in `pops_config.h` says the same.

I checked this with my own static scan of the decoded MAIN image (`<scratch>/cfg2fix/static_scan.py`, output `static_scan.out`). It lists every gp-based load and store of 0x3864, 0x38a0, 0x4fa0 and 0x3898. The only store of `$zero` to 0x3864 is at `0x870c90`. The other stores to it are at `0x871218`, `0x871718`, `0x88301c`, `0x8830a4`, `0x883174` and `0x8902a4`, and all store `$v0`.

### 7. minor: apply_launcher_token comment is false

Fixed. The comment now says `$PAL2NTSC`/`$FORCENTSC` set `POPS_VMODE_NOPAL` but are not the original's `$NOPAL`. They do not test `forced_pal`, so `"$FORCEPAL $PAL2NTSC"` gives no PAL, while `"$FORCEPAL $NOPAL"` stays forced PAL. It also says this is an owner decision.

Behaviour is unchanged. `docs/POPSTARTER_CONFIG_TEXT.md` now says the same in its launcHER-token paragraph.

### 8. minor: other writers of the video words not mentioned

Fixed. A line is added under "Known differences that remain" in `docs/POPSTARTER_CONFIG_TEXT.md`, marked "read from the code, not run". It lists:

- `0x883114` (load of 0x3898), then `0x883120`/`0x883124` (clears of 0x38a0 and 0x4fa0 while it is 0). Disassembled in `static_scan.out`.
- The stores to 0x3864 in that function.
- The start-up writes `0x870c80`/`0x870c90` and `0x8711ec`..`0x871230`.
- The other stores of 0 to 0x4fa0: `0x871710`, `0x883014`, `0x88309c`, `0x88316c` and `0x8f8abc`.
- That when `0x883000` runs relative to the reader was not traced.

The `forced_pal` comment in `pops_config.h` also names `0x870c80`, `0x871208` (which `pops_config_load_table` copies) and `0x883120` (not modelled).

Every address in the reviewer's finding agrees with my scan.

### 9. minor, report only: the proposed quirk overclaims

Agreed. The wording is under 5.

## Doc changes (docs/POPSTARTER_CONFIG_TEXT.md)

- Counts: 167 fixed texts became 169, and the video table went from 18 texts to 20. The evidence list now says that the forced-PAL word is compared.
- launcHER-token paragraph: `$FORCEPAL $PAL2NTSC` against `$FORCEPAL $NOPAL`, as an open owner question.
- Known differences: the line from finding 8.

## Commands run and results

All from Git Bash. TMP, TEMP and TMPDIR were each set to a fresh empty folder of mine under `<scratch>/tmp-cfgfix-*`, or under `<scratch>/cfg2fix/mut/tmp-*` for the mutants. Test files were run one at a time.

1. `git pull --ff-only`: already up to date at `c05ddb6`.
2. `python <scratch>/cfg2fix/static_scan.py tools`, with `POPSTARTER_TEST_ELF` set: output in `static_scan.out`, summarised under findings 6 and 8. It prints addresses and instructions only.
3. `python <scratch>/cfg2fix/record.py tools`, with both ELFs set: the EXPECTED and video rows above (`record.out`).
4. Without inputs: `test_pops_config_text.py` Ran 32 OK (skipped=15); `test_pops_features.py` Ran 29 OK (skipped=2).
5. `git commit` (`83ba2ac`) and `git push -u origin pr23/cfg-2`: pushed.
6. Mutants, without inputs (`<scratch>/cfg2fix/mutants.py . <scratch>/cfg2fix/mut noinputs`), each in its own `git archive HEAD` copy:
   - C5: rc=1, `Native.test_table`.
   - R4: rc=1, `Native.test_launcher_token_bytes`.
   - V3: rc=1, `Native.test_video_commands` and `Native.test_video_two_files`.
   - Results are in `<scratch>/cfg2fix/mut-noinputs.txt`.
7. Full sweep without reference inputs (`<scratch>/cfg2fix/sweep.sh noinputs`, all 32 `tools/test_*.py`): every file rc=0.
   - unittest files: test_pops_breakpoint Ran 11 OK (s=4); builtin_db 14 OK (s=14); config_text 32 OK (s=15); display 21 OK (s=6); doc_claims 12 OK (s=7); external 128 OK (s=14); features 29 OK (s=2); fix_files 31 OK (s=3); igr_skin 48 OK (s=21); io_probe 6 OK; launch_hooks 48 OK (s=14); module_irx 11 OK (s=4); opcodes 9 OK (s=3); padman 6 OK (s=3); physical_disc 40 OK (s=18); progressive 8 OK (s=5); read_trace 9 OK; resident 75 OK (s=12); runtime_corrections 8 OK; smb_config 37 OK (s=13); startup_calls 6 OK; user_bios 51 OK (s=13, expected failures=1); warmboot 7 OK (s=3).
   - Script-style files, all rc 0: launch_args, network_transports, popfs, pops_fatfs, pops_modes, pops_vmc, smap_ipconfig, sony_ioman_layout, subq_bridge.
   - Summary: `<scratch>/cfg2fix/sweep-noinputs/summary.txt`.
8. Full sweep with `POPS_TEST_ELF`, `POPSTARTER_TEST_ELF` and `POPS_TROJAN_CORPUS` set (`sweep.sh inputs`): every file rc=0.
   - test_pops_config_text: Ran 32 OK in 322 s. Its printout:
     - 169 fixed texts match the table; 20 video texts match the table; 600 random video texts; 6 fixed and 441 two-file pairs.
     - 1500 random texts: 2876 commands, 399 codes, 96 MODE, 20 writes of 0x100017; video words not compared in 71.
     - 500 token texts; 300 `$USBDELAY` texts (84 writes); 20 `$USBDELAY` table texts; 30 start-value runs.
     - 357 short files (17 of 1428 runs step over a code, no command changes).
     - VMCDIR 39/30 and 400 (212/188); 21 modes x 2.
   - Other results: features Ran 29 OK; external 128 OK (s=3); launch_hooks 48 OK (s=3); progressive 8 OK (s=3); user_bios 51 OK (expected failures=1); physical_disc 40 OK; every other file OK with no skips or rc 0.
   - Summary: `<scratch>/cfg2fix/sweep-inputs/summary.txt`.
9. Mutant V3 with inputs: rc=1, 6 failures (2 Native, 4 Original), listed under finding 4. C5 and R4 were not run with inputs: they already fail in Native tests, which also run with inputs.
10. Docker target build:
    - The worktree cannot be mounted (its `.git` file points at a Windows path, as the reviewer found), and its submodules are not checked out. So I built a standalone clone at `<scratch>/cfg2fix/buildclone`: `git clone` of the worktree, `git checkout 83ba2ac`, submodule URLs pointed at the main checkout's submodules, then `git -c protocol.file.allow=always submodule update --init`. That gave mmceman `db3e93f` and psxcore `33ff564`.
    - Command: `MSYS_NO_PATHCONV=1 docker run --rm -v "<clone>:/workspace" -w /workspace ghcr.io/ps2homebrew/ps2homebrew:main sh -c "apk add cmake >/dev/null && git config --global --add safe.directory '*' && cmake -B build-cfgfix && cmake --build build-cfgfix --target launcHER"`. I used `safe.directory '*'` instead of `/workspace` so that the submodules count as safe too.
    - Result: rc 0, 0 `error:` lines. `build-cfgfix/release/launcHER.elf` is 327,092 bytes, the same size the reviewer measured at `c05ddb6`. The C changes are comments only.
11. Hygiene greps on `c05ddb6..HEAD` added lines: 0 runs of 16+ hex digits, 0 `@`, 0 AI names or attribution. No binaries.

## Not done

- No console or emulator run.
- C5 and R4 were not run with inputs (see 9).
- The timing of the function at `0x883000` relative to the reader is still not traced.
- The PR text is not edited. The wording under finding 5 is for whoever edits it.

## Proposed quirk text (for the coordinator, reworded as the review asks)

- "$FORCEPAL after a $480P does nothing, also when the $480P is in the file for all games (0x8987f0 tests gp+0x3864). Matched in launcHER (pr23/cfg-2); measured under emulation."
- "$NOPAL does not undo an earlier $FORCEPAL: $NOPAL clears only gp+0x4fa0, and the region pass tests gp+0x38a0 first (0x879034, read from the code). Matched in launcHER (`forced_pal`, compared with gp+0x38a0 under emulation)."
- "CHEATS.TXT of 8 bytes or less: a code test reads past the 2*size buffer, and what the heap holds decides whether such a '$' is a code. launcHER reads zeros. No command differed in 1428 runs with other heap bytes; by reading, none can."

## Open questions for the owner

1. (Handoff section 8, unchanged) Should launcHER-only tokens, bare digits and `MODE n` stop being read from CHEATS.TXT? If so, where should they be read instead?
2. Should launcHER's `$NTSC2PAL`, `$PAL2NTSC` and `$FORCENTSC` keep "last one wins" against `$NOPAL` and `$FORCEPAL`? Today `$FORCEPAL $PAL2NTSC` gives no PAL, while `$FORCEPAL $NOPAL` gives forced PAL.
3. (From the review) A fix file's progressive setting is applied after the text (`handler_pops.c`). So a `$FORCEPAL` in the text keeps NTSC2PAL while progressive is set. Whether the original's fix-file progressive is applied before the text, which would gate `$FORCEPAL`, belongs to the fix-file/command order work.
