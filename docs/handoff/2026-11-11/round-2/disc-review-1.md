# Review: physical PS1 disc planner, core stage and fingerprint (host part)

Target: merge f22a69f (feature commit 1f8c525), reviewed at ef663b2 on codex/popstarter-replacement.
Files: common/include/pops_physical_disc.h, common/src/pops_physical_disc.c,
tools/trace_original_pops_physical.py, tools/test_pops_physical_disc.py,
docs/POPSTARTER_PHYSICAL_DISC.md, launcher/CMakeLists.txt (+1), .github/workflows/build.yml (+2),
and the author report docs/handoff/2026-11-11/disc-author.md.
First review. Read-only: nothing in any repository was changed. Scratch work was done in a detached
worktree at `<scratch>/audit-disc/tree` (removed at the end), with TMP/TEMP/TMPDIR set to `<scratch>/audit-disc/tmp`.
Reference inputs: POPSTARTER_TEST_ELF = POPSLoader/bin/POPSLDR/PROFILES/MAIN/POPSTARTER.ELF,
POPS_TEST_ELF = POPS/POPS.ELF. Nothing here was run on a console. Every original-side result is
a static read of MAIN (capstone 5.0.7 over `decode_main`) or a Unicorn 2.1.4 run with the tracer's
modelled callees.

## Verdict

**merge** (the merge stands). The C code is correct against the original for everything I checked.
It is also unwired: no launch path reaches it. The four findings are all minor and are about
documentation. One of them is a wrong claim about the original in the author's proposed quirk text,
and it matters when the code gets wired.

## What I ran (verified)

| # | Command | Result |
|---|---|---|
| 1 | `python tools/test_pops_physical_disc.py -v` with both reference ELFs | `Ran 40 tests in 99.294s OK`. Printed: 262 disc types; 276 status/type pairs; 607 stored fingerprints from sectors, 204 from a VCD; 400 seeded cases (192 reach POPS, 208 fatal); rc=0 |
| 2 | same, no reference inputs (CI path) | `Ran 40 tests in 0.131s OK (skipped=18)` |
| 3 | `python tools/trace_original_pops_physical.py` | rc=0. 21 demo runs. The 0x13 failed-read case shows `sceCdRead(4,1,…,'20010000',0)`, letters copied from buffer+60, the writes 0x200796, 0x20ebf2, 0x20f0b6, 0x20f0e0..e3, 0x2328bc, 0x2328c8.., and 0x2328d0..0x232943 zeroed. Type-0 probe: 22 mount/umount log entries |
| 4 | Independent fuzz `<scratch>/audit-disc/scripts/fuzz.py`: 300 cases, seed 0xC0FFEE. Status is drawn from {1, 0, 2, 0x101, 0x80000001, random 32-bit, 1\|(rand<<8)} and type from {0x10..0x14, 0x10\|(rand<<8), 0x80000013, random 32-bit, 0x0f, 0x01}. 20% NULL sector, 30% failed reads, 7 module lists. For each case the original block is compared with `pops_physical_disc_plan` + `pops_physical_disc_stage` + the 4 always-live writes: fatal/not, letters at gp+0x3cb0, whole POPS core | `cases 300 reach POPS 95 mismatches 0` |
| 5 | Module scan with lists (), (cdvd_x), (CDVD_MAN), (cdvdman), (xcdvd_), (sio2man, cdvd_), (cdvd) | SifLoadModule count 2,0,2,2,2,0,2: case-sensitive prefix `cdvd_` only, as documented |
| 6 | Mutation run (no reference inputs) on a temp edit of pops_physical_disc.c in the scratch worktree, restored afterwards (`git status` clean). Mutations: M1 fingerprint offset 808->809, M2 mute on 0x12 not 0x13, M3 write 0x200794 before checking the mute sites (partial write), M5 status compared as `&0xff`, M6 licence offset 61 | all caught: M1 FAILED(2), M2 FAILED(5), M3 FAILED(2), M5 FAILED(1), M6 FAILED(2) |
| 7 | `<scratch>/audit-disc/scripts/builtin_sites.py`: every built-in entry 1..624 applied with `pops_builtin_apply` over a core marked 0xA5 and over one marked 0x5A | `entries touching a physical-disc site: {}`. No entry writes 0x200794, 0x20f0b6, 0x20ebf2, 0x20f0e0, 0x2328bc..0x2328cf or 0x2328d0..0x232943 |
| 8 | EE gcc 15.3.1 (`ps2build/toolchain/ee/bin/mips64r5900el-ps2-elf-gcc`) `-Os -G0 -Wall -Wextra -D_EE -c pops_physical_disc.c` | rc=0, text 940, data 0, bss 0; U memcpy, memset, pops_apply_original_tokens. Launcher ELF not built or linked |
| 9 | `python tools/test_pops_doc_claims.py` | `Ran 12 tests OK (skipped=7)` |

## Static checks against the original (read with capstone, not run unless noted)

- Block 0x8766fc..0x876a40 (`<scratch>/audit-disc/block.dis`, 209 lines): entry `bne gp+0x3410,1` and
  `bnez 0x10b8($fp)`. Status: `beq v1,1 -> 0x876a1c` on the whole word. Type: four full-word `beq` against 0x10..0x13.
  Sector buffer gp+0x3cc0, memset 0x1260. `sceCdRead(4,1,gp+0x3cc0,gp+0x3978)`. memcpy(gp+0x3cb0, gp+0x3cfc, 4), so bytes 60..63.
  Then `0x87c300(0x202d, 0x200794)`, the three always-live words, mute only for 0x11/0x13 (0x87c298 for
  the two bytes, 0x87c300 for 0x20f0e0), the unconditional memset(0x2328d0,0,0x74), and the fingerprint
  for level 1..4. The poke helpers 0x87c298 and 0x87c300 are plain `sb`/`sw` with no read. All of this
  matches `pops_physical_disc_plan`/`_stage` and the header.
- Strings: gp-0x6858 = `"NO PS1 CDROM!\n\n"` and gp-0x6848 = `"Cannot access (%d)!\n\n"`, the same as
  `pops_physical_disc_message`. Also gp-0x68c8, -0x6888 and -0x6868 are the "Loading/loaded/Init" texts, and
  gp-0x68a8/-0x6898 are `rom0:CDVDMAN`/`rom0:CDVDFSV`.
- Read mode: 0x870c20..0x870c34 stores 0x20, 1, 0, 0 at gp+0x3978..0x397b.
- Always-live copy: 0x874754..0x874768 does memcpy(0x232790, 0x983150, 0x738). MAIN 0x98327c = 0x34842950
  (`ori a0,a0,0x2950`) and is followed by `jal 0x210540` at 0x983280 (POPS 0x2328c0).
- Fingerprint FUN_008ff0e4: with the flag at 1, sector 16 is copied from gp+0x3ce8 (buffer+40, 0x30 bytes) and gp+0x3fe8
  (buffer+808, 0x20), and sector 22 from gp+0x3cf8 (buffer+56, 0x40). The VCD offsets are 0x109340/0x109640/0x10ca70 through
  both backends (0x916c08/0x9169b0 and 0x91bdc8/0x91bbb8). This matches `pops_physical_disc_fingerprint`.
- A gp-relative scan of MAIN (`<scratch>/audit-disc/scripts/gpscan.py 0x3410`) finds exactly the 10 store sites
  and 8 load sites the doc lists.
- sceCdInit(5): 0x8774c4..0x8774d8 runs after the DISCS.TXT reader (0x8774b4) and FUN_008dc9ac (0x8774bc).
- 0x4f8000: the original writes `"%s/"` (0x002f7325) there at 0x875964 and the name at 0x4f8003. The
  memset at 0x878c88 clears that. launcHER writes nothing there (its argument is passed as
  `pops0:IMAGE.VCD` through the trampoline argv, `pops_bootstrap.c:145`), so the header's "changes nothing on a
  launcHER core" holds.

## Findings

### 1. minor: the proposed quirk "CD audio is always muted; no command keeps it" is wrong about the original

Where: docs/handoff/2026-11-11/disc-author.md:192 (quirk row) and :161 (decision 7, "CD-DA muted for
types 0x11/0x13 with no way to keep it").

Evidence (read, not run):
- The command parser starts at 0x883270 and is called at 0x8771ac and 0x87724c. Both calls are inside the launch function
  0x870b78, after the block (0x8766fc..0x876a40). The guard before them is `lw gp+0x38dc; bnez` at
  0x877120. There is no test of gp+0x3410 there: the gp scan above has no load of 0x3410 between 0x876a40 and 0x8774c4.
- The `$UNDO_MUTE_CDDA` arm in that parser (0x8953d8..0x895408) calls `0x8d6b9c(2, 0x20f0b6)`,
  `0x8d6b9c(3, 0x20ebf2)` and `0x8d6c04(0xae000014, 0x20f0e0)`. Those are Sony's values, put back.

So, read from the code, a user's `$UNDO_MUTE_CDDA` runs after the block's mute and undoes it for a type 0x11/0x13 disc,
provided the parser finds a command file in physical mode. That last condition was not run.
Consequences:
- The quirk row and decision 7 would record behaviour the original does not have.
- When this gets wired, `pops_physical_disc_stage` has to stay before `pops_stage_user_files` (handler_pops.c:1690 at
  ef663b2). The header already says so, and its guard needs that order anyway. A test should then pin
  that `$UNDO_MUTE_CDDA` after the stage restores the three sites.

Fix: drop "no command keeps it" and "Honour $UNDO_MUTE_CDDA" from the quirk proposal, and reword decision 7. When wiring,
add the order test.

### 2. minor: the doc says to call `pops_apply_region`; the merged launch uses `pops_apply_region_rom` with the user-ROM state

Where: docs/POPSTARTER_PHYSICAL_DISC.md:146 ("a physical launch must always run `pops_apply_region` with the
planner's letters"). The author report gives the same instruction (not_done 9, deviations 8) and cites `handler_pops.c:1567`.

Evidence (read): at ef663b2 handler_pops.c:1722 is
`regionRead ? pops_apply_region_rom(..., cfg.disc_region, cfg.video_mode, ..., &romState) : 0`.
`pops_apply_region` (pops_modes_patches.c:1078) forwards `rom = NULL`. With NULL, `pops_user_rom_keeps_shell`
returns 0 (:81-82), so the BIOS shell words 0x2649a0 and 0x264994..0x26499c are written even when a
user BIOS.BIN/OSD was loaded. The `_rom` variant skips them in that case (:1108-1118). Someone who wires
the physical path as the doc says would lose the user-BIOS rule that the 0945127 merge added.
The region test (`Original.test_letters_reach_the_region_pass`) only uses `pops_apply_region` with no user ROM.
For that case it is right; it does not cover this one.

Fix: say "the existing region call (`pops_apply_region_rom` with `romState`), unconditionally" and
drop the line-number references.

### 3. minor: line references in the author report are stale at the merge

Where: docs/handoff/2026-11-11/disc-author.md, summary and decisions 4/2: handler_pops.c 888-891, 1459, 1469,
1479 order, 1567, 992 and others.

Evidence (`git show <rev>:launcher/src/handler_pops.c | grep -n`):

| | 1f8c525 | f22a69f / ef663b2 |
|---|---|---|
| "Cannot open target VCD" | 890 | 1049 |
| always-on pokes | 1459 | 1623 |
| IGR skin | 1469 | 1657 |
| region | 1567 (`pops_apply_region`) | 1722 (`pops_apply_region_rom`) |
| built-in apply | 1479 (after the skin) | 1637 (before the skin) |

The order also changed: the built-in entry now sits between the always-on pokes and the skin. The
author's placement "after pops_apply_always_on_pokes and before pops_stage_igr_skin" is now ambiguous.
Run 7 shows no built-in entry touches any physical-disc site, so either placement gives the same bytes.
The original's order is block, then fingerprint/entry (0x8769ac), then skin, so "before `pops_builtin_apply`" is the exact one.
The file itself says "copied as written; not re-verified", so this is a note for whoever wires the code.

Fix: when wiring, place the stage right after `pops_apply_always_on_pokes` and before `pops_builtin_apply`. Re-derive the line numbers.

### 4. minor: the description of the wrong-type exit is imprecise

Where: docs/POPSTARTER_PHYSICAL_DISC.md:65-67.

Evidence (read): 0x8769d8 `lw gp+0x3448; bnez -> 0x876a0c` skips the helper for any nonzero mass flag,
not only for 1. The helper 0x8d7ff8 first calls `0x9174f8("pfs:", 0x5003, 0,0,0,0)` (gp-0x4a10 = `"pfs:"`;
0x5003 is the pfs close-all devctl) and then unmounts `pfs0:` (gp-0x4a08) and `pfs1:` (gp-0x4a00). The doc says only
"it unmounts pfs0: and pfs1:". The fatal exit 0x8709f8 also does more than exit: it runs a devctl with
0xc0de0006/0xc0de0003 when gp+0x3450 == 1, calls FUN_008dc9ac unless gp+0x3828 == 3, calls FUN_00870700(1), and runs memsets.
The planner does not cover these, and they are not described anywhere. The future caller needs them.

Fix: "unless gp+0x3448 is nonzero". List the close-all devctl. Record that the fatal exit's own
steps are unmeasured.

## Checked and found correct (no finding)

- `pops_physical_disc_stage` checks the range, then Sony's bytes at every site it will write, and only then writes.
  `pops_apply_original_tokens(POPS_TOK_MUTE_CDDA)` (pops_modes_patches.c:1144-1146, 1180-1196) writes exactly the
  three sites with the original's values, and its own range check cannot fail after the stage's. I found no partial-write path,
  and mutation M3 confirms the test notices one.
- The planner's whole-word compares (0x101 passes, 0x110 refused) match the `lw`/`beq` code. Fatal outcomes carry no letters.
  A NULL sector gives four zero letters.
- The build wiring: CMakeLists is the only EE build list that names pops_igr_skin.c, and the new file is added next to it.
  The CI step runs the test without reference inputs, which pass (run 2).
- Nothing is wired: `Source.test_nothing_is_wired_into_a_launch_yet` and `test_a_missing_vcd_still_ends_the_launch`
  pass, and the resident engine still calls `cd_init(disc_slot[...])` at pops_resident_engine.c:341.

## Not checked

Launch type 4. The VCD-path builder (gp+0x3470). Where per-game files are looked up after every probe fails.
What 0x210540 does with NULL on a launcHER-staged core. Full launcher ELF link. Anything on a console.
