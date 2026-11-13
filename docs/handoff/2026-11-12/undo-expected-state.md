# Token-aware `$UNDO_` expected state

Branch `pr23/undo-expected-state`, based on `36475d7`. This implements the
owner's selected option (a) for the built-in-entry guard failure. It does not
change production file/command order, Ember, or the remaining differences in
quirks 72 to 79. The order gap is now indexed as quirk 80.

**Evidence level: host tests and the original under Unicorn with modelled
services. NOT TESTED on a console. No game was booted.**

## Cause and change

`pops_apply_all_config_patches_rom` had already restored the core words, but
`pops_fix_context_init_builtin` reconstructed its expected state only from
the built-in entry and text compatibility mask. It therefore rejected 294 of
624 applicable entries after `$UNDO_COMPATIBILITY_CODES`. Three of those
entries (109, 571 and 572) make a direct core write rather than requesting a
compatibility mode.

`pops_stage_fix_files` now receives `cfg->original_tokens` and calls
`pops_fix_context_init_builtin_rom` with those tokens and the current loader
state. The expected state is reconstructed in this order:

1. built-in compatibility modes and direct core writes, in entry order;
2. the selected writes from the existing `undo_writes` table;
3. the text compatibility mask.

That is the existing grouped command pass's order, including when a text
mode follows an undo command. The actual `$UNDO_` OSD writer tests only the
replaced-BIOS flags. Expected mode-6 state is also preserved because this
initializer has pre-load state rather than the command pass's BIOS
look-ahead; the original-word fallback handles an undo that restores POPS's
word. A focused built-in-mode-6/predicted-BIOS regression pins that rule.
The fallback also covers a mode 6 skipped over a replaced BIOS. No other
mode site is generally accepted merely because it contains POPS's original
word. The old initializer remains as a wrapper with no tokens and no loader
state for its existing callers.

## Measurements

- The former count was **294 refused / 330 accepted** in current
  commands-first order and **0 refused / 624 accepted** in the test-only
  files-first alternate.
- `tools/test_pops_fix_order.py` now reports **0 refused / 624 accepted in
  both orders**, including entries 109, 571 and 572. Every accepted
  final-core SHA-256 matches the normalized original result. The final run
  passed 7 tests in 612.786 seconds.
- The separate control still reports 150 scenarios with a loaded BIOS, 92
  without, 16 original-order differences and 28 current-launcHER differences
  at `0x2525b0`. This change does not claim to fix that ordering gap.
- `tools/test_pops_user_bios.py`: 55 tests pass with reference inputs,
  including the former expected failure, three direct-write entries,
  combined undo/text ordering and BIOS-skipped mode 6. The same 55 pass
  without references with 13 optional skips.
- The guard test rejects incomplete and complete restores with missing or
  wrong tokens, accepts only the matching `$UNDO_COMPATIBILITY_CODES`
  restore, and rejects a subsequent changed non-OSD word. Every failure
  case checks that a nonzero caller-context canary is unchanged. Replacing
  token replay with zero tokens makes its positive case fail.
- The first reference sweep containing the two added edge cases returned
  35/36 files: `test_pops_user_bios.py` failed exactly those cases with
  `-EINVAL`. Moving undo replay before text modes and restoring the existing
  BIOS/mode-6 fallback corrected them; their focused regressions pass.
- Focused reference-backed runs: fix files 31 tests pass; TROJAN 59 tests
  pass with 5 optional skips for unprovided build artifacts.
- Document claims: 19 tests pass without references (11 optional skips) and
  19 pass with references.
- Pre-review sequential host sweep: 36 of 36 files passed without
  references. The final post-review sweep is listed below.

## Final verification

- Final sequential host sweep without references: **36 of 36 files pass**.
- Final sequential host sweep with references: **36 of 36 files pass**.
- Final release container build: `handoff layout: OK`;
  `version=36475d7c1a4f`; `launcHER.elf` 332,356 bytes, SHA-256
  `803344cdd0de74000d99ca3e7edff6b0d3197c0a448d963b1960a878f3b4e83b`.
- Final trace container build: `handoff layout: OK`;
  `version=36475d7c1a4f`; `launcHER.elf` 336,532 bytes, SHA-256
  `6856c914bdd752e0af380a14c0943cc695e3eb19c88cf38f07d650058c5987e7`.
- The builds emit warnings in existing MMCE, init, quickboot, formatting and
  trace code; none names a line changed by this piece. No compiler failure.
- Independent review: initial verdict `merge-after-fixes` identified the
  undo/text order, replaced-BIOS fallback, weak wrong-token negative and
  historical/current documentation ambiguity. All four were answered.
  Re-review found no new issues and returned `merge` on source and test
  inspection; the reviewer did not rerun tests or claim console evidence.

## Limits

The census normalizes the already-audited launch-only writes as the order
harness describes; it is not an unqualified whole-launch or hardware proof.
The original blocks run under Unicorn with modelled file services. No real
PS1 BIOS, proprietary file, real card, save, share or console was used.
`OSD.BIN` remains a separate piece and was not started here.
