# OSD.BIN implementation evidence

Branch `pr23/osd-bin`, based on `308684c`. Owner-approved design and plan:
`docs/POPSTARTER_OSD.md` and
`docs/superpowers/plans/2026-11-12-osd-bin.md`.

**Evidence level: host tests, original code under Unicorn with modelled
services, and PS2SDK container builds. NOT TESTED on a console. No game was
booted and no drop-in-parity claim is made.**

## Landed pieces so far

- `4b7fce7`: approved design and implementation plan.
- `6581b83`: original-handler oracle, directed boundaries and 256 seeded
  synthetic cases, registered in CI.
- `e80fc9e`: pure validation, v1/v2 staging and loader state.
- `0ed8411`: exact launcher file reader.
- `352aae2`: per-scope look-ahead and actual OSD loading before BIOS, built-in
  no-fix propagation, changed-file `-EIO`, and failure-atomic fix-context
  refresh. Independent whole-branch review is pending.

The implementation uses synthetic files only. No real OSD.BIN, BIOS image,
proprietary reference content, real card, save or share was used.

## Measured behavior

- Distinct rejection codes and original precedence, including EXE/foreign,
  unsupported version, invalid header/load/entry, size mismatch, too big,
  missing build and missing label. Rejection is atomic.
- v1/v2 destinations and capacities, v1 header bytes, v2 immediate
  instruction words (not live IOP reads), and mixed v2-then-v1 residue.
- Both all-games success flags and both game success flags, OSD-off
  transitions, built-in no-fix and ignored unsupported modes.
- An 80-byte zero-filled header read, exact seeks, one unchecked body read,
  and the unaligned `body_size + 16` request within the measured boundary.
  Short/failed body reads keep the accepted result and zero-filled tail.
- Per-scope look-ahead and actual loading before BIOS, with changed valid
  plans/results/state returning `-EIO` and same-plan body changes accepted.
- Validated OSD compatibility writes refresh the fix context; subsequent
  corruption is still rejected.

## Tests run

- `tools/test_pops_osd.py`: **35 tests with references and 35 without (16
  optional skips)**. This includes 256 whole-core seeded differentials,
  every rejection, cap boundaries, both backend I/O models, read faults,
  mixed scopes, launch ordering, changed files and guard checks.
- `tools/test_pops_user_bios.py`: 55 tests with references and 55 without
  (13 optional skips), including the existing 270-scenario chain.
- `tools/test_pops_igr_skin.py`: 48 tests with references and 48 without
  (21 optional skips).
- `tools/test_pops_fix_order.py`: 7 tests pass in 598.706 seconds. Both
  orders accept all 624 entries with matching accepted final-core hashes;
  the separate 16 original-order and 28 current-launcHER ordering differences
  remain unchanged.
- Release and trace container builds both print `handoff layout: OK` and
  `version=352aae2588d2`:
  - release: 333,556 bytes, SHA-256
    `e347fdd2d5f141db9a6386efaea294bc87629286ed14452fa0b13fb80c864540`;
  - trace: 338,148 bytes, SHA-256
    `f178f88546daa6c7434ab3a6b78831955737ed802e7fb7d66ab5335aa9ffc71d`.

## Remaining differences and limits

- Quirk 80: grouped file/command order still differs from the original.
- Quirk 81: OSD is opened for look-ahead and again for the actual load;
  changed valid plans/results/state return `-EIO`. The original has no
  look-ahead window or fix-context guard.
- Quirk 82: safe `-ENAMETOOLONG` replaces attempting to copy a possible
  fixed-buffer overflow. Original overlong-path behavior was not emulated.
- Quirk 83: the integrity result comes from launcHER's validated POPS core,
  not a fresh execution of the original integrity routine on each package.
- Quirk 84: original POPS-folder inspection, once flags and some
  abort/folder-error paths remain uncopied. `game_dir_missing` is modeled
  where supplied, but its inspection is not performed.
- Debug logging is not identical to the original's on-screen text (quirk 81).
- No PCSX2 or physical-console run was made for this piece. Runtime behavior
  of an actual replacement PS1 BIOS shell is unverified.

The final no-reference sweep passes **37 of 37 files**. The reference-backed
sweep, independent review and the reversible merge are pending.
