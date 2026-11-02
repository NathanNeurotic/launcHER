# POPStarter r13's `$LOAD_PADMAN` and `$KILL_PADMAN`

Measured on the original (POPSTARTER.ELF MAIN, external input) on
2026-11-02 by reading its code. launcHER copies it. Nothing here was tested
on a console.

## The commands

- `$LOAD_PADMAN` (sets `gp+0x38a8`, store at `0x89d988`) and `$KILL_PADMAN`
  (sets `gp+0x3870`, store at `0x89dbc0`) are flags only.

## What happens after the IOP reset (`0x87aba8..0x87ac64`)

POPS normally starts its own embedded pad driver: at `0x200358` it calls its
module loader (`jal 0x2001d8`) with the padman_hsync ELF at `0x2cd560`
(ends `0x2d8345`), and the `bgezl` at `0x200360` skips its error message.

- `$LOAD_PADMAN`, while `gp+0x3824` is 0: POPStarter starts that same image
  itself (`0x91c248`, address `0x2cd560`, length `0xadf0`, no arguments);
  a start returning `<= 0` is fatal. Then it pokes `0x200358 = 0` (the call
  becomes a `nop`) and the high half `0x200362 = 0x1000` (the `bgezl`
  becomes `beq zero, zero`, always past the error).
- `$KILL_PADMAN`: the same two pokes, nothing started (quirk 32).
- `gp+0x3824` is set by the original's `MODULE_n.IRX` scan when one of those
  modules is named `padman`; that scan does the same two pokes itself.
  launcHER copies that scan now (see POPSTARTER_MODULE_IRX.md), so
  `$LOAD_PADMAN` skips its start when a `MODULE_n.IRX` is named `padman`.

The order around it: the pad driver starts after POPStarter's other
post-reset modules and before the `XX.` USB pair.

## launcHER

- Parser: `PopsConfig.load_padman`, `kill_padman`.
- `pops_apply_padman()` (`pops_modes_patches.c`): the two pokes on the
  staged core (the same bytes POPS runs), unchecked like the original's;
  bounds only.
- `handler_pops.c`: `$LOAD_PADMAN` starts the module from the staged core
  after `initPopsServices`, before the `XX.` USB pair; fatal on `<= 0`.

## Verification

`tools/test_pops_padman.py`: native pokes, bounds and parsing; with
`POPSTARTER_TEST_ELF`, the original's own instructions (gates, pokes,
module address and length) equal launcHER's constants; with `POPS_TEST_ELF`
as well, the real core's call site is POPS's padman_hsync start and only
those bytes change.
