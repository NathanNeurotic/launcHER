# OSD.BIN implementation evidence

Branch `pr23/osd-bin`, based on `308684c`. Owner-approved design and plan:
`docs/POPSTARTER_OSD.md` and
`docs/superpowers/plans/2026-11-12-osd-bin.md`.

**Evidence level: host tests, original code under Unicorn with modelled
services, and PS2SDK container builds. NOT TESTED on a console. No game was
booted and no drop-in-parity claim is made.**

## Implementation and review

- `4b7fce7`: approved design and implementation plan.
- `6581b83`: original-handler oracle, directed boundaries and 256 seeded
  synthetic cases, registered in CI.
- `e80fc9e`: pure validation, v1/v2 staging and loader state.
- `0ed8411`: exact launcher file reader.
- `352aae2`: per-scope look-ahead and actual OSD loading before BIOS, built-in
  no-fix propagation, changed-file `-EIO`, and fix-context refresh.
- `cf20444`: separate sequential loader state from post-command effects;
  selective, bounds-checked guard updates after independent review.
- `d67c16f`: alternate host wrappers preserve their no-OSD-look-ahead behavior.
- `34fd531`: carry actual root PATCH mode-6 transitions into the later game
  OSD, including the returned state and a game-BIOS variant, after re-review.

The first independent review required fixes for built-in mode-6 state,
unrelated guard-byte acceptance and short-core reads. The second required the
root-PATCH transition. The final re-review returned `merge` with no remaining
findings, by inspection of the complete branch diff.

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
- Built-in, root/game, text and root-PATCH mode-6 sequences, including BIOS
  interactions and preservation of post-command effects.
- Only header-selected compatibility writes refresh the fix context;
  unrelated corruption fails atomically. Short cores return `-ERANGE` before
  compatibility reads, checked with an inaccessible memory page.

## Tests run

- `tools/test_pops_osd.py`: **37 tests with references and 37 without (17
  optional skips)**. This includes 256 whole-core seeded differentials,
  every rejection, cap boundaries, both backend I/O models, read faults,
  mixed scopes, launch ordering, root PATCH, changed files and guard checks.
- `tools/test_pops_user_bios.py`: 55 tests with references and 55 without
  (13 optional skips), including the existing 270-scenario chain. The same
  28 differences attributable to grouped order remain.
- `tools/test_pops_trojan.py`: 59 tests with references and 59 without
  (5 and 16 optional skips respectively).
- `tools/test_pops_igr_skin.py`: 48 tests with references and 48 without
  (21 optional skips). `tools/test_pops_fix_files.py`: 31 tests without
  references (3 skips).
- On `406ddfd`, `tools/test_pops_fix_order.py` passed 7 tests in 643.747
  seconds. Both orders accepted all 624 entries with matching accepted
  final-core hashes; the separate 16 original-order and 28 current-launcHER
  ordering differences remained.
- On `352aae2`, both full host sweeps passed **37 of 37 files**. Those are
  pre-review results, not evidence for the revised tree.
- Pre-review release and trace container builds printed `handoff layout: OK`
  and `version=352aae2588d2`:
  - release: 333,556 bytes, SHA-256
    `e347fdd2d5f141db9a6386efaea294bc87629286ed14452fa0b13fb80c864540`;
  - trace: 338,148 bytes, SHA-256
    `f178f88546daa6c7434ab3a6b78831955737ed802e7fb7d66ab5335aa9ffc71d`.
- Revised `406ddfd` release and trace builds both print `handoff layout: OK`
  and `version=406ddfdc956b`:
  - release: 333,988 bytes, SHA-256
    `c2fb1e1d32102c2746dec227093661a33a29922743a0f3082e2695467ff1952a`;
  - trace: 338,148 bytes, SHA-256
    `45c4788f3d42be033f27f041eaea93891a90ead8255c2270967e7d11265ec09f`.

## Remaining differences and limits

- Quirk 80: grouped file/command order still differs from the original.
- Quirk 81: OSD is opened for look-ahead and again for the actual load;
  changed valid plans/results/state return `-EIO`. The original has no
  look-ahead window or fix-context guard. Debug logging also differs from
  the original's on-screen text.
- Quirk 82: safe `-ENAMETOOLONG` replaces attempting to copy a possible
  fixed-buffer overflow. Original overlong-path behavior was not emulated.
- Quirk 83: the integrity result comes from launcHER's validated POPS core,
  not a fresh execution of the original integrity routine on each package.
- Quirk 84: original POPS-folder inspection, once flags and some
  abort/folder-error paths remain uncopied. `game_dir_missing` is modeled
  where supplied, but its inspection is not performed.
- Quirk 85: the VCD/per-title folders stand in for the original device
  POPS/per-game folders; the owner approved exact HDD `__common` mapping for
  the follow-on path work, not a launcHER-only folder default.
- No PCSX2 or physical-console run was made for this piece. Runtime behavior
  of an actual replacement PS1 BIOS shell is unverified.

On `406ddfd`, both full host sweeps passed **37 of 37 files**, without and
with reference inputs. Independent re-review returned `merge`. The piece
landed in draft PR #23 as `800d91e398830573335a6c1d43b74af0dc78da2e`,
whose tree is identical to `ce6332d`. Final release and trace builds on that
merge print `handoff layout: OK` and `version=800d91e39883`; their artifact
sizes and hashes are the revised values above. PR #23 remains draft and is
not merged into EMBER.
