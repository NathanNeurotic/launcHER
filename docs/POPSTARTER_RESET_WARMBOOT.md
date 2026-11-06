# POPStarter r13's `$RESET_WARMBOOT` and the in-game reset combo

Measured on the original (POPSTARTER.ELF MAIN, external input) on
2026-11-01 by running its own code under emulation. launcHER copies it,
bugs included. Nothing here was tested on a console.

## The command

- Handler `0x8923a4`: sets `gp+0x3894 = 1` and nothing else. The name must be
  followed by a space, CR, LF, NUL or `$` (a tab does not end it); it is
  found anywhere a `$` starts, like every command of the original
  (quirk 22 lists where launcHER's tokenizer differs).
- The flag is read once, in the launch function, right after the region
  pass: block `0x8795f0..0x879cf4`.

## What the pass does

It walks POPS's embedded PS1 BIOS ROM copy from `0x2cbb4c` down to (not
including) `0x24bc20`, 4 bytes at a time, looking for the BIOS call stubs

```
addiu $t2, $zero, 0xA0 | 0xB0 | 0xC0
jr    $t2
addiu $t1, $zero, func
```

and rewrites a fixed list of them so they call A0:A0 (`_boot`, a warm boot)
instead. Each change is one-byte pokes (`0x87c298`):

| Table | Functions rewritten | Bytes poked |
|---|---|---|
| A0 | 3A 40 4F 50 53 9A 9B A1 | function byte (`+8`) = `0xA0` |
| B0 | 1A 1B 1C 1D 1E 1F 21 22 23 2A 2B 38 52 5A | table byte (`+0`) and function byte (`+8`) = `0xA0` |
| C0 | 0B 14 | table byte and function byte = `0xA0` |

On the owner's POPS that is 48 bytes in 24 stubs (two copies of most
stubs, at `0x2594f0..` and `0x2621a8..`).

For each A0:3A (SystemErrorExit) stub it also edits its own resident block
at `0x232ce8`, the in-game reset described below: it computes the stub's PS1
ROM address (`p - 0x24bc20 + 0xbfc00000`, `0xbfc0d8d0` here) and then stores
`p` itself, the EE address of the stub inside POPS's copy (`0x2594f0`), as
the word the reset makes the PS1 jump to (quirk 26). The scan walks
downward and every match rewrites the same slot, so the lowest stub wins.
The store is built into `0x232d00..0x232d08`, which is also the slot a
built-in entry's breakpoint handler call uses; since the pass runs after
the entry, that handler is gone for the game (quirk 25).

## The in-game reset combo (always on)

The original's resident block, reached from its GP1 hook every time the game
writes GP1 with interrupts enabled, contains (`0x232ce8..0x232d04`):

```
lh  k0, 0x507002     ; port 0 buttons, active low
bne k0, 0xbcfe, skip ; exactly SELECT + L2 + R2 + CROSS
lui k0, 0x7000
lui k1, 0xbfc0       ; $RESET_WARMBOOT: lui/ori of its stored address
sw  k1, 0(k0)        ; scratchpad word 0: POPS's PS1 jump word
```

This runs in every launch, with or without `$RESET_WARMBOOT`, and launcHER
did not have it. It now does: `pops_resident_gp1_work` stores
`PopsResidentConfig.reset_vector` (default `0xbfc00000`) to scratchpad word
0 while port 0 reads exactly `0xbcfe`, right after the controller-ID stores,
where the original has it (quirk 27).

## launcHER

- `PopsConfig.reset_warmboot` (parser), `pops_apply_reset_warmboot()` (the
  scan and pokes, `pops_modes_patches.c`), called in `handler_pops.c` right
  after `pops_apply_region`, as in the original.
- When the pass finds a SystemErrorExit stub, its address becomes
  `cfg.reset_vector` and the built-in breakpoint handler call is dropped.
- Resident image v11: `PopsResidentConfig.reset_vector`.

## Verification

- `tools/trace_original_pops_warmboot.py`: runs the original's block as
  shipped on a POPS core (external `POPSTARTER_TEST_ELF`, `POPS_TEST_ELF`).
- `tools/test_pops_warmboot.py`: native tests (rewrites, lowest stub wins,
  scan bounds, parser) plus, with the external inputs, the original's block
  against `pops_apply_reset_warmboot` on the real core and on random cores
  (every core byte outside the resident block equal; the stored address
  equal), and the command's parsing against the original's handler.
- `tools/check_pops_resident_image.py` section 7: the built image's GP1
  entry stores the vector only for the exact combo.
