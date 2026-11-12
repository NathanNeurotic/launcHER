# docs-3 (minor doc and test-text findings): independent review 2

Target: `origin/pr23/integ...origin/pr23/docs-3`, merge base 4e90fda, head
39b9977 (commits 090e3ce, 39b9977). Read-only. Detached worktree
`<scratch>/review2-docs3/tree` at 39b9977 (removed at the end). `<scratch>` =
<scratch>.
Host only: no emulator other than the tests' own Unicorn, no container build,
no console. NOT TESTED on a console. "Verified" means I ran or read it myself.

## Verdict

**merge-after-fixes**. The fixes are small doc wording changes. No C, header,
build or workflow file changed. The diff touches 9 Markdown/HTML files and
`tools/test_pops_igr_skin.py`. Every reviewer finding the task named is
addressed, and the corrected addresses and counts hold against the original
when I re-run them. CI's path (no reference inputs) is green. Four minor
inaccuracies remain, two of them added by this diff, plus two wrong counts
in the author's own report.

## What I ran (verified)

| # | What | Result |
|---|---|---|
| 1 | Full suite, all 35 tracked `tools/test_*.py`, no reference inputs, one at a time, a fresh TMP/TEMP/TMPDIR per file (`<scratch>/review2-docs3/full-without.log`) | 35 of 35 rc=0; doc_claims 19 OK (skipped=11), igr_skin 48 OK (skipped=21), user_bios 51 OK (skipped=13, expected failures=1), physical_disc 40 OK (skipped=18) |
| 2 | With POPS_TEST_ELF, POPSTARTER_TEST_ELF and POPS_TROJAN_CORPUS: igr_skin, doc_claims, user_bios, physical_disc (`with4.log`) | 48 OK (0 skipped, includes the 84-launch replay); 19 OK; 51 OK (expected failures=1); 40 OK |
| 3 | With inputs: the other 31 files (`full-with-rest.log`) | 31 of 31 rc=0 (the author did not run the suite with inputs) |
| 4 | The BIOS reviewer's `gap55.py` and `gap_mask0.py` on this tree (scripts read, not changed; `rerun.log`) | no command {0: 624}; `$UNDO_COMPATIBILITY_CODES` {-22: 294, 0: 330}, the same with an all-games BIOS.BIN; masks 0x0 3/333, 0x1 45, 0x2 3, 0x4 9, 0x8 188, 0x9 11, 0xa 23, 0x10 11, 0x28 1 (291 with modes). No 0x20-only mask. UNDO_GAME_FIXES / UNDO_LIBCRYPT_FIX 624 rc=0. Entries 109, 571, 572: only 0x21af70 0x24020064->0x24020032 |
| 5 | The disc reviewer's `builtin_sites.py` (run with `python -I`: that script folder holds a `dis.py` that shadows the stdlib `dis` module otherwise) | `entries touching a physical-disc site: {}` |
| 6 | My own capstone 5.0.7 reader over `decode_main` (`<scratch>/review2-docs3/scripts/rd.py`, `gpstr2.py`), gp = 0x9b68f0 (derived from the IGR string, cross-checked against six other strings) | see "Statements checked" |

## Statements checked against the original or the code (all hold unless a finding says otherwise)

- USER_BIOS.md size test: 0x880894 `lui v1,7`, 0x880898 `ori v1,v1,0xff8e`,
  0x88089c `slt v0,v1,v0`, 0x8808a0 `beqz v0,0x88093c`. 0x8803d0 is
  `sb v0,0x20(fp)` (it builds the path). The pfs lseek path ends with `b 0x880890`
  (0x88085c), and the mass path falls through 0x880874..0x88088c to 0x880890.
  So "both back ends" holds.
- 294 of 624 = 291 + 3 (row 4). "Each sets at least one of modes 1 to 5; one
  also mode 6" holds: 0x28 is modes 4 and 6, and there is no 0x20-only mask.
- IGR SB./XX. note: `'S'` 0x871568, `'B'` 0x87158c, `'s'` 0x8715b0, `'b'` 0x8715d4,
  `'.'` 0x871600, `sw v0(=1),0x3448(gp)` 0x871618. XX. store at 0x8719a4. A
  gp+0x3448 store scan finds exactly 0x870c64 ($zero), 0x871618 and 0x8719a4.
  0x87e508 `lw 0x3448(gp)` / `bne ...,1`, 0x87e534 a0 = gp-0x56b8 =
  "mass:/POPS/IGR_BG.TM2", 0x87e538 `jal 0x8d6c94`. As written.
- PHYSICAL_DISC.md wrong-type exit: 0x8769d8 `lw 0x3448(gp)`, 0x8769dc
  `bnez -> 0x876a0c`, then the launch type 3/4 tests and `jal 0x8d7ff8`. The
  helper does `0x9174f8(gp-0x4a10 "pfs:", 0x5003, 0,0,0,0)`, then `0x915f50`
  on "pfs0:" and "pfs1:". PDIOC_CLOSEALL = 0x5003 in the local PS2SDK
  `hdd-ioctl.h:216`.
- `$UNDO_MUTE_CDDA` arm 0x8953d8..0x895408: `0x8d6b9c(2,0x20f0b6)`,
  `0x8d6b9c(3,0x20ebf2)`, `0x8d6c04(0xae000014,0x20f0e0)`. launcHER's token
  table has the same three rows.
- Region text: in `pops_apply_region_rom`, `keep` (BIOS.BIN or the second OSD
  kind) skips 0x2649a0 for a known licence. For an unknown licence it skips
  0x264994..0x2649a3 and 0x20f6cc/0x20f6d8/0x20f6dc/0x20f6e0. `pops_apply_region`
  passes NULL. So the doc's list is right, with the existing `!force_pal`
  conditions on the 0x20f6xx bytes left implicit.
- Placement: launchPOPS calls the always-on pokes at line 1730,
  `pops_builtin_apply` at 1744, `pops_stage_igr_skin` at 1764,
  `pops_stage_user_files` at 1802, the `_rom` shell edits at 1833 and region
  at 1841, then warmboot, the slot chain at 1890, module names, padman, SLBB,
  the resident hooks and the opcode pass. The IGR doc's two new table rows
  follow that order.
- README and setup-page IGR text against `pops_stage_igr_skin` and
  `pops_igr_skin.h`. The call is unconditional. The files are read from
  `vcdDir`. The limits are 0x4c300 = 312,064 and 0x1dbc = 7,612. A larger
  file is skipped, a 0-byte file zero-fills the slot, and the content is not
  checked. Without an IGR command, launcHER's direct exit is used (IGR doc
  line 167).
- Test replay (`RealCore.launch`) against `pops_stage_user_files` /
  `pops_stage_fix_files` at 4e90fda:
  - The state is zeroed with osd_off from mode-6 bit 5, and `atCommands`
    copies it with the two look-ahead flags.
  - The commands go through `pops_apply_all_config_patches_rom`, and
    osd_off is carried back.
  - Then come the emit jumps, `init_builtin` with `cfg.compat_modes`/
    `video_mode` (no progressive requested), and `bind_progressive` with
    0x24040001 (because `$HDTVFIX` is set).
  - For each folder: BIOS.BIN stage + `rom_loaded`, then the PATCH through
    `pops_fix_stage_rom` (all-games folder only), then the -EIO flag
    comparison.
  - The ctypes layouts match `PopsUserRomState` (7 x uint8) and
    `PopsBuiltinPlan` (`PLAN[2]` = `compat_modes` after the uint16 id).
  - Left out: `pops_resident_slot_chain_possible` (read-only), the slot
    chain and the progressive hook. The replay calls display, matching
    launchPOPS's else-if. The docstrings say so.
- Historical reports: only correction notes were appended at the end. The
  original text is unchanged (diff is additions only at EOF).
- No attribution in the diff or in either commit message. The author identity
  is the owner's noreply address, not an email. No binary, byte table or
  hash: the diff is text only, with no hex run of 32+ characters. The test
  builds its BIOS.BIN from the pristine core at run time.
- Behaviour: no `.c`, `.h`, CMake or workflow file is touched. d31d4a7 is an
  ancestor of the base, so no launch (SB. or otherwise) behaves differently
  from `pr23/integ` because of this track. The track adds nothing that could
  change a launch compared with d31d4a7.

## Findings

### 1. minor: the IGR doc says the table is "the original's order", but its new row is launcHER's order

docs/POPSTARTER_IGR_SKIN.md:110-113. The new row reads "`pops_stage_user_files`:
commands, recompiler add-ons, then per folder ... the user `BIOS.BIN` and the
fix files". The next line still says "This is the original's order for a
fingerprint-matched entry". The original loads both BIOS.BIN files before it
runs the commands: loader calls are at 0x876cd8/0x876fd8, the parser at
0x8771ac/0x87724c (IGR review, finding 1 table row 1). launcHER runs the
commands first, with a look-ahead (USER_BIOS.md difference 1). The order of
the later row (slot chain after warmboot, and so on) is also launcHER's own.
The statement is right about where the skin sits, not about the rows after
it. Fix: "The skin's place (after the built-in entry, before the user's
files) is the original's; inside and after `pops_stage_user_files` the rows
give launcHER's order (`POPSTARTER_USER_BIOS.md`, difference 1)."

### 2. minor: README and setup page say the old text lasted "until the skin was merged"; it lasted until this branch

README.md:718 says "(This line said "not implemented" from November 11, 2026
until the skin was merged.)". docs/pops-setup.html:557 says "(From November 11,
2026 until the skin was merged this section said the files had no effect.)".
`git show 173d5de:README.md` (the skin merge) and
`git show origin/pr23/integ:README.md` both still contain "not implemented",
so the wrong text outlived the merge. The inventory row in the same commit
correctly says "until after this merge". Fix: "until after the skin was
merged (corrected on pr23/docs-3)", or drop the date clause.

### 3. minor: user docs say "only when the `.VCD` is in `mass:/POPS/`", but the IGR doc leaves SB. launches open

README.md:718 says "so they are found in the same place only when the `.VCD`
is in `mass:/POPS/`". pops-setup.html:557 says the same. The IGR doc's new
SB. paragraph (also in this diff) says that for an SB. launch the original
opens `mass:/POPS/`, and that whether `mass:` then names USB or the share
"was not traced, so for an SB. launch the two may or may not be the same
place". The user text states as a fact what the design doc leaves open. Fix:
add "(for SMB launches this was not traced)" or point to the IGR doc's
paragraph.

### 4. minor: the fatal-exit list in PHYSICAL_DISC.md leaves out two stores

docs/POPSTARTER_PHYSICAL_DISC.md:63-70 lists the fatal exit's steps and says
"Read from the code, not run". My read of 0x8709f8..0x870b74 matches every
listed step. It also finds `sw zero,0x33ac(gp)` and `sw zero,0x33b0(gp)` at
0x870aac/0x870ab0, right after the first two `0x9188b8` calls. Those two calls
take their lengths from those same words, and the third is the fixed
`0x9188b8(0x1ff000, 0, 0x303e60)`. The doc's own conclusion is still right:
the steps are unmeasured and the planner does not cover them. Fix: add
"clears `gp+0x33ac` and `gp+0x33b0` (the lengths of the first two clears)".

### 5. minor (author's claims): "36 of 36" and "its own fresh TMP folder"

- docs3-author.md and the claims JSON say "36 of 36 tools/test_*.py rc=0".
  There are 35 tracked test files at 090e3ce and at 39b9977
  (`git ls-files 'tools/test_*.py' | wc -l` = 35). The author's own
  `<scratch>/docs3/full-without.log` has 35 `rc=` lines plus an `exit=0`
  line. The result is right (I get 35/35); the count is wrong.
- The claims JSON says "each run with its own fresh TMP/TEMP/TMPDIR folder".
  `<scratch>/docs3/run_tests.sh` makes one fresh folder per invocation, so
  all 35 files of the full run share one folder. That is allowed by the task
  ("your own fresh folder"), but it is not what the claim says.

### 6. minor (historical note wording): "The other 330 launch"

docs/handoff/2026-11-11/bios-bin-fix-1.md, new correction note. What was
measured is that the other 330 are not refused (`pops_stage_user_files`
returns 0 on the host). Whether they launch was not run. USER_BIOS.md says
"are not refused", which is the measured form. Fix: use the same words here.

## Not this track, seen and confirmed by reading (no action asked here)

- common/include/pops_modes_patches.h:50 still says "The size test (0x8803d0)".
  The author proposes the fix for a track that may change C. The disassembly
  above supports 0x88089c.
- README.md:719 still says community TROJAN files "stop the launch". At
  4e90fda `pops_stage_fix_files` logs and `continue`s on
  `POPS_FIX_SKIP_INVALID`, `_OUTDATED` and `_UNHOSTED`
  (handler_pops.c:464-477). That text is stale since the TROJAN merge (read
  only, not measured).
- BIOS review finding 1 (major, built-in entry + `$UNDO_COMPATIBILITY_CODES`,
  294 of 624 refused) is untouched, as the task says. The counts above
  re-measure it on this tree.
- The author's proposed handoff and quirks text is consistent with these
  measurements.

## Cleanup

The worktree `<scratch>/review2-docs3/tree` was removed with
`git worktree remove --force` and `git worktree prune`. Nothing was
committed or pushed. My scripts and logs are under `<scratch>/review2-docs3/`.
The temp folders are `<scratch>/tmp-rv2d3-*`.
