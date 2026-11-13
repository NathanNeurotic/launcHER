# Fix files versus commands: differential report

**Evidence level: host code and original blocks under Unicorn with modelled file
services. NOT TESTED on a console.** No production launch order or `$UNDO_` fix
is changed by this piece.

## Method

`tools/test_pops_fix_order.py` runs the original BIOS, TROJAN, PATCH and
CHEATS.TXT blocks under Unicorn, then compares final cores for:

- original files-before-commands versus original commands-before-files;
- original files-before-commands versus launcHER's current helper;
- original commands-before-files versus launcHER's current helper;
- original files-before-commands versus a test-only files-first alternate;
- original commands-before-files versus the alternate.

The alternate replays only the matrix's compatibility mode 6 and the three
`$UNDO_` commands in text order. Other commands retain the full config pass's
existing behavior and are rejected explicitly if added to the replay list.
The original TROJAN and PATCH loaders execute as shipped. The three words of
the original parser's resident blob are restored after parsing, as in the BIOS
harness; that is the only excluded write set. Reports contain addresses only,
not original or replacement code bytes.

Blank current and alternate cores must be identical. The blank launcher ROM
range must equal the original's, and every original change outside ROM must be
unmodified in the blank launcher baseline. This is checked for both original
orders before any normalization.

## Measured results

The 270-scenario control reproduces the older 150/92/28 breakdown and separately
counts the original-order effect:

- 150 cases with a BIOS loaded: final cores and loader words equal;
- 92 cases without a loaded BIOS: final cores equal;
- 16 original-order differences at `0x2525b0..0x2525b1`;
- 28 current launcHER differences at the same halfword.

The alternate files-first path has no final-core differences from the original
files-first path in the control. The two current comparisons may differ only at
that halfword, and the current difference is exactly the union of the original
order difference and the current-versus-original-commands difference.

Two negative controls pin both outcomes: equal original orders, and a real
original-order difference with PATCH plus `$UNDO_COMPATIBILITY_CODES`.
A separate open-order check selects the fixture paths from all ten probes:
root TROJAN, root PATCH, title TROJAN, title PATCH. It is not TROJAN payload
parity evidence.

## Built-in `$UNDO_COMPATIBILITY_CODES`

All 624 applicable built-in entries were run in both orders. Accepted final-core
SHA-256 values were compared with the normalized original parser output:

- current commands-first: 294 refused, 330 accepted;
- alternate files-first: 0 refused, 624 accepted.

Entries 109, 571 and 572, whose direct core writes must not be overlooked, are
refused only in current order. Accepted entries in both orders have final-core
hashes matching the original. This is a measurement of the guard and its order,
not an implementation of either owner-option fix.

## Final verification

Full reference-backed run: 7 tests pass in 525 seconds. Independent code
review: `merge` on inspection. Full sequential host sweeps: 36 of 36 files
pass without reference inputs and 36 of 36 with `POPS_TEST_ELF`,
`POPSTARTER_TEST_ELF` and `POPS_TROJAN_CORPUS`. `test_pops_user_bios.py`
keeps its one expected `$UNDO_COMPATIBILITY_CODES` failure.
