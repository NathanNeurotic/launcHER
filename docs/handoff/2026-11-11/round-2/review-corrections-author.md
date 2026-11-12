# docs-3: minor document and test-text findings of the IGR, BIOS.BIN and disc reviews

Branch `pr23/docs-3` (from `pr23/integ` at `4e90fda`), worktree
`<workspace>/launcHER.worktrees/docs-3`. No C code or behaviour
changed. Everything below is a host result or a static read of the
original; nothing was run on a console or in an emulator. NOT TESTED on a
console.

Commits (both pushed to origin/pr23/docs-3, no force): 090e3ce (all
changes), 39b9977 (two wording fixes in the IGR doc). HEAD 39b9977.

## What was changed, finding by finding

### IGR review (igr-review.md)

1. Finding 1 (whole-launch replay and doc claim). Made the test true where
   cheap and corrected the claim for the rest.
   - `tools/test_pops_igr_skin.py`, `RealCore.launch`: now writes out
     `pops_stage_user_files`'s steps with the common functions launchPOPS
     calls: `PopsUserRomState` (new `Rom` ctypes struct, `osd_off` from the
     built-in entry's mode 6 bit), `pops_apply_all_config_patches_rom` with
     the look-ahead flags, the emit jumps, `pops_fix_context_init_builtin`,
     `pops_fix_bind_progressive` (as `pops_stage_fix_files` does), per folder
     (all games, then game) `pops_user_bios_stage` + `pops_fix_context_rom_loaded`
     when a BIOS.BIN is chosen, the PATCH file through `pops_fix_stage_rom`,
     the `-EIO` flag comparison, then `pops_apply_bios_shell_edits_rom` and
     `pops_apply_region_rom` with the state. The BIOS.BIN is POPS's own ROM
     copy from the pristine core with its first 16 bytes set to 0x5a (built
     at run time, nothing committed); the test asserts the load landed.
   - `test_whole_launches_keep_the_skin`: 7 masks x 3 built-ins x 4 BIOS
     choices (none, all-games, game, both) = 84 launches, count asserted.
   - Docstrings now say what is replayed and name the two calls left out
     (TROJAN slot chain, progressive hook). Module docstring updated the same way.
   - `docs/POPSTARTER_IGR_SKIN.md`: order table splits the later stages into
     `pops_stage_user_files` (commands, add-ons, per-folder BIOS.BIN and fix
     files) and the rest (with the `_rom` shell edits/region and the TROJAN
     slot chain added); Evidence says 84 launches and what the replay leaves out.
2. Finding 2 (user docs say the skin is not implemented).
   - README.md and docs/pops-setup.html: replaced with what is read (the three
     files, unchecked, size limits 312,064 / 7,612 / 7,612, larger skipped,
     0 bytes blanks), from where (the `.VCD`'s folder; POPStarter's `POPS`
     folder, same only for `mass:/POPS/`), visible only under `$IGR0..2`,
     NOT TESTED on a console.
   - The inventory row was already updated by the docs track; its last sentence
     ("have not been updated since") is now corrected.
   - Handoff section 2's list: cannot edit; proposed text below.
3. Finding 3 (SB. folder). Added to "Where the files go": SB./sb. and XX./xx.
   set gp+0x3448 = 1, loader opens literal `mass:/POPS/IGR_*.TM2`, launcHER
   reads `vcdDir`; whether `mass:` names USB or the share in SMB mode not
   traced; read, not run.

### BIOS review (bios-review.md)

- Finding 1 (major, `$UNDO_COMPATIBILITY_CODES` refusal): NOT done, owner
  decision. Re-measured only, for the wording below.
- Finding 2: docs/POPSTARTER_USER_BIOS.md size test address 0x8803d0 -> 0x88089c
  (with 0x880894..0x880898 and the branch at 0x8808a0; both back ends join at 0x880890).
- Finding 3: the gap wording in POPSTARTER_USER_BIOS.md section 4, the gap audit's
  BIOS.BIN section and the inventory's `$UNDO_` row now say 294 of 624: the 291 that
  set compatibility modes (each sets one of modes 1 to 5; one also mode 6) and three
  (109, 571, 572) that set none but write mode 4's byte at 0x21af70 directly; the
  other 330 are not refused. A correction note was appended to
  docs/handoff/2026-11-11/bios-bin-fix-1.md for its user-facing note and for fix
  option (a) needing to cover the entry's direct core writes.

### Disc review (disc-review.md)

- Finding 1 (proposed quirk "no command keeps it" wrong): correction note
  appended to docs/handoff/2026-11-11/disc-author.md. POPSTARTER_PHYSICAL_DISC.md
  now says the stage must stay before `pops_stage_user_files` because the
  original's `$UNDO_MUTE_CDDA` runs after the block (read, not run).
- Finding 2: POPSTARTER_PHYSICAL_DISC.md region section now says to run the
  existing `pops_apply_region_rom` call with `romState`, and why not
  `pops_apply_region`; no line numbers.
- Finding 3: placement now "after `pops_apply_always_on_pokes` and before
  `pops_builtin_apply`", with the equal-bytes note (measured) and the
  original's order; note appended to disc-author.md for its stale line numbers.
- Finding 4: wrong-type exit now "unless gp+0x3448 is nonzero (bnez; tests run
  0 and 1)", the helper's close-all devctl (`0x9174f8("pfs:", 0x5003, ...)`,
  PS2SDK `PDIOC_CLOSEALL`) before the two unmounts, and the fatal exit's own
  steps listed as read and unmeasured.

Also: docs/handoff/2026-11-11/igr-skin-fix-1.md got a short note that its
"21 whole launches in launchPOPS's order" stopped being true after the
BIOS.BIN merge, and what the replay does now.

## Verification of each corrected statement (what I ran)

All MAIN reads below are my own capstone 5.0.7 runs over
`trace_original_pops_io.decode_main` of POPSTARTER_TEST_ELF (scratch scripts
`<scratch>/docs3/dis.py`, `strs.py`, `gpstores.py`).

- Size test: 0x880894 `lui v1,7`, 0x880898 `ori v1,v1,0xff8e`, 0x88089c
  `slt v0,v1,v0`, 0x8808a0 `beqz v0,0x88093c`; 0x8803d0 is `sb v0,0x20(fp)`.
  The loader 0x88019c..0x880a20 has no other compare against 0x7ff8e. Both
  back-end lseek paths (0x916c08 and 0x8d6d64) join at 0x880890.
- 294/624: the reviewer's `gap55.py` and `gap_mask0.py` (pops_stage_user_files
  host build, real core) run on this worktree at 4e90fda: no command 624 rc=0;
  `$UNDO_COMPATIBILITY_CODES` {-22: 294, 0: 330}, same with an all-games
  BIOS.BIN; `$UNDO_GAME_FIXES`, `$UNDO_LIBCRYPT_FIX` 624 rc=0. Refused by mode
  mask: 0x1 45/45, 0x2 3/3, 0x4 9/9, 0x8 188/188, 0x9 11/11, 0xa 23/23, 0x10
  11/11, 0x28 1/1, 0x0 3/333 (entries 109, 571, 572, each changes only
  0x21af70 0x24020064 -> 0x24020032). 0x21af70 is mode 4's site in
  pops_modes_patches.c's mode table. No entry has a mode-6-only mask.
- SB./XX.: 0x871568 'S', 0x87158c 'B', 0x8715b0 's', 0x8715d4 'b', 0x871600
  '.', `sw v0(=1), 0x3448(gp)` at 0x871618; XX./xx. tests 0x8718e0..0x87197c,
  store at 0x8719a4. gp-relative store scan of gp+0x3448: exactly 0x870c64
  ($0), 0x871618, 0x8719a4. IGR loader: 0x87e508 `lw 0x3448(gp)`, `bne ...,1`;
  0x87e534 a0 = gp-0x56b8 = "mass:/POPS/IGR_BG.TM2", `jal 0x8d6c94`.
- Wrong-type exit: 0x8769d8 `lw 0x3448(gp)`, 0x8769dc `bnez -> 0x876a0c`,
  then launch type 3/4 tests, `jal 0x8d7ff8`, `jal 0x8709f8`. Helper: a0 =
  gp-0x4a10 "pfs:", a1 = 0x5003, four zero args, `jal 0x9174f8`; then
  `jal 0x915f50` with "pfs0:" and "pfs1:". PDIOC_CLOSEALL = 0x5003 in the
  local PS2SDK hdd-ioctl.h. Fatal exit 0x8709f8: gp+0x3450 == 1 ->
  0x9174f8("mass0:" = gp-0x7ea0, 0xc0de0006 / 0xc0de0003), clears the word;
  gp+0x3828 != 3 -> FUN_008dc9ac; FUN_00870700(1); three 0x9188b8(addr, 0, len);
  0x87098c x5 unless gp+0x38b0 == 1; 0x91aaf0 if gp-0x7fe8 == 1; FUN_00870500.
  The test only records the exit call (test_pops_physical_disc.py
  `test_fatal_exit_and_the_pfs_unmount`, mass 0/1).
- `$UNDO_MUTE_CDDA` handler 0x8953d8..0x895408: 0x8d6b9c(2, 0x20f0b6),
  0x8d6b9c(3, 0x20ebf2), 0x8d6c04(0xae000014, 0x20f0e0). launcHER's
  pops_modes_patches.c has the same three restore rows.
- Built-in entries vs physical-disc sites: the disc reviewer's
  `builtin_sites.py`, run here: 1248 applies (624 x 2 markers), all rc 0,
  no entry touches 0x200794, 0x20f0b6, 0x20ebf2, 0x20f0e0, 0x2328bc..0x2328cf
  or 0x2328d0..0x232943.
- launchPOPS order (read, handler_pops.c at 4e90fda): always-on pokes 1730,
  `pops_builtin_apply` 1744, `pops_stage_igr_skin` 1764,
  `pops_stage_user_files` 1802, require_progressive, finalize_video,
  `pops_apply_bios_shell_edits_rom` 1833, `pops_apply_region_rom` 1841,
  warmboot, slot chain 1890, module names, padman, SLBB, resident hooks,
  opcode pass. `pops_stage_fix_files`: init_builtin, bind_progressive, per
  folder BIOS.BIN (+ rom_loaded), TROJAN, PATCH (`pops_fix_stage_rom`).

## Tests run

TMP/TEMP/TMPDIR each a fresh folder under the scratchpad
(`tmp-docs3-<name>`), one test at a time from the worktree root, Git Bash.
"with" = POPS_TEST_ELF, POPSTARTER_TEST_ELF, POPS_TROJAN_CORPUS set.

- Full suite, no inputs, at 090e3ce (first commit; the second commit
  changes two lines of docs/POPSTARTER_IGR_SKIN.md only): 36 of 36 files rc=0
  (log `<scratch>/docs3/full-without.log`). Notables: doc_claims 19 OK
  (skipped=11), igr_skin 48 OK (skipped=21), launch_hooks 49 OK (skipped=14),
  user_bios 51 OK (skipped=13, expected failures=1), physical_disc 40 OK
  (skipped=18), trojan 59 OK (skipped=16).
- At HEAD 39b9977, without inputs: test_pops_doc_claims.py 19 OK
  (skipped=11); test_pops_igr_skin.py 48 OK (skipped=21).
- At HEAD 39b9977, with inputs: test_pops_doc_claims.py 19 OK;
  test_pops_igr_skin.py 48 OK (0 skipped; RealCore 7 incl. the 84-launch
  replay); test_pops_user_bios.py 51 OK (expected failures=1, the 5.5 gap);
  test_pops_physical_disc.py 40 OK.
- Full suite with inputs: not run (only the four files above).
- No container build: no C changed.

## Proposed text for files I may not edit

docs/PR23_HANDOFF_2026-11-11.md, section 2, the paragraph after the merge
table, replace the first sentence with:

> The shared status documents (README, `POPSTARTER_R13_INVENTORY.md`,
> `POPSTARTER_QUIRKS_TO_FIX_LATER.md`, `pops-setup.html`,
> `CLOUD_CONTINUATION.md`) were **not** brought up to date for the IGR skin,
> BIOS.BIN, SMB, disc and config-text pieces. (Since then `pr23/docs-3`
> updated README and `pops-setup.html` for the IGR skin.)

docs/PR23_HANDOFF_2026-11-11.md, section 5.5, first sentence:

> A built-in entry followed by `$UNDO_COMPATIBILITY_CODES` is refused with
> -EINVAL by the fix-file session: 294 of 624 built-in entries on the real
> core, the 291 that set compatibility modes and three (109, 571, 572) that
> write mode 4's byte at `0x21af70` directly.

docs/PR23_HANDOFF_2026-11-11.md, section 8, the `$UNDO_COMPATIBILITY_CODES`
bullet, add: "Option (a) must also cover the entry's direct core writes
(entries 109, 571, 572)."

docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md: nothing proposed from these three
reviews; if the disc author's quirk row is ever added, drop "no command
keeps it" and "Honour `$UNDO_MUTE_CDDA`" from it (disc review finding 1).

common/include/pops_modes_patches.h (C header comment, not changed because
the task forbids C changes): `/* The size test (0x8803d0): ...` should read
`(0x88089c)`.

## Not done / for the owner

- BIOS review finding 1 (major): built-in entry + `$UNDO_COMPATIBILITY_CODES`
  is still refused for 294 of 624 entries. Owner decision between fix (a)
  (covering modes and direct core writes) and (b). Not touched.
- The IGR replay still leaves out the TROJAN slot chain and the progressive
  hook; named in the docstring and the doc.
- The handoff index (docs/handoff/2026-11-11/README.md) still lists the
  physical disc as "Not reviewed"; the three reviews live in the scratchpad
  and were not copied into the repository (not asked).
- Seen, not in these reviews, not changed: README's fix-file bullet still
  says TROJAN files from community packs stop the launch; the TROJAN merge
  (bc67659) changed that behaviour. Not verified here; for the TROJAN or docs
  track.
- No container build (no C changed), no emulator, no console.

## Correction (added after review 2)

- The full suite has 35 tracked `tools/test_*.py` files, not 36. The
  result was 35 of 35 rc=0.
- The first-round runner made one fresh TMP/TEMP/TMPDIR folder per
  invocation, shared by every file in that run, not one per file. The
  review-2 fix round (docs3-fix2.md) uses one fresh folder per file.
