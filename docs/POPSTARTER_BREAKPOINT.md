# POPStarter r13's `$BREAKPOINT0` and `$BREAKPOINT1`

Measured on the original (POPSTARTER.ELF MAIN, external input, gp
`0x9b68f0`) on 2026-11-02 by reading and running its code, and copied into
launcHER for POPStarter launches (`launchPOPS`). Ember launches never reach
this code. Nothing here was tested on a console.

`tools/test_pops_breakpoint.py` runs the original's own function under
emulation for every order of up to three of these commands, on an empty
area and over a built-in entry's handler, and launcHER's bytes must be the
same.

## What the original does

Both are config commands found by the same stream scan as the others
(`$BREAKPOINT0` at `0x8960c4`, `$BREAKPOINT1` at `0x896310`; the name must
end in a space, CR, LF, NUL or `$`). Each one, where it stands in the files,
calls `FUN_008d6da4`, the same function the built-in list uses for its 14
"breakpoint killer" entries ([POPSTARTER_BUILTIN_DB.md](POPSTARTER_BUILTIN_DB.md)):

- `$BREAKPOINT0`: `FUN_008d6da4(0, 0)`
- `$BREAKPOINT1`: `FUN_008d6da4(1, 1)`

That function always stores `jal 0x01460000` at `0x232d08` (a slot in the
original's resident chain, right after the controller-ID stores) and copies
the 292-byte handler template from `0x96bde0` to `0x01460000`. The template
scans PS1 RAM for compiler divide checks (`bne`, `nop`, `break`) and turns
each `bne` into an always-taken branch, so the `break` never runs. It runs
on every GP1 write the game makes (quirk 21).

Then, with 128-bit stores:

**(0, 0), `$BREAKPOINT0`:** the first 32 bytes become a gate: run the scan
only while the PS1 word at `0x1ffdf4` is not 2 (the same word `$SAFEMODE2`
tests). The scan's end (`0x080`, its `jr ra`) becomes `b 0x120`, and
`0x120..0x12f` (the last 12 bytes past the 292 copied) become `lui k0, 0x146;
sw zero, 0x14(k0); jr ra; nop`: the first full scan clears the gate's
branch, so the handler returns at once from then on. One scan, then never
again (but see quirk 38).

**(1, 1), `$BREAKPOINT1`:** the first 32 bytes become a gate on the EE
halfword at `0x507002` being `0xdcfe`, which is POPS's port 0 button word
(the in-game reset reads the same word, quirk 27) with exactly
SELECT+L2+R2+CIRCLE held. The scan runs while that combo is held, on every
GP1 write.

Any other arguments store them as the template's target address and word
(the built-in entries' use).

Each call copies the template afresh, so the last command decides. The
only leftover is the 12 bytes `$BREAKPOINT0` writes past the copy
(`0x124..0x12f`), which stay when a `$BREAKPOINT1` follows; nothing reaches
them in that case.

The built-in list runs before the config files are parsed, so a
`$BREAKPOINT` replaces a matched entry's handler (quirk 39). `$RESET_WARMBOOT`
runs after the parse and, when it finds its stub, overwrites the same
`0x232d08` slot, so the handler is never called (quirk 25).

## launcHER

- `pops_config.c`: `$BREAKPOINT0` / `$BREAKPOINT1` set
  `PopsConfig.breakpoint` (which came last, and whether a `$BREAKPOINT0`
  came at all).
- `pops_breakpoint_build()` (`pops_builtin_db.c`) builds the bytes: the
  template taken from the built-in list's own data (the same 292 bytes in
  all 14 entries, with the entry's two data words cleared), then the
  original's stores, word for word.
- `launchPOPS` sets the chain call (`POPS_RES_F_BREAK_CALL`, the built-in
  path's flag) after the config is parsed and before `$RESET_WARMBOOT`,
  which still drops it as in the original; checks the staged core ends
  below `0x01460000`; and writes the handler at handoff right after any
  built-in entry's code, before the resident image.
