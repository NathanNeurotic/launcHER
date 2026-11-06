# POPStarter r13's opcode pass and `$ORIGINAL_OPCODES`

Measured on the original (POPSTARTER.ELF MAIN, external input) on
2026-11-02 and copied into launcHER for POPStarter launches. Ember launches
never reach this code. Nothing here was tested on a console.

## What the original does

On **every** launch, late, before the IOP reset (`0x87a64c`), POPStarter
calls `0x87c4a0` unless `$ORIGINAL_OPCODES` set `gp+0x38c4`. That function
walks seven ranges of the loaded POPS image in steps of 4 bytes, reading the
16-bit value at each address:

| Range (inclusive) | Note |
|---|---|
| `0x200c62..0x24bc1f` | POPS's code up to its PS1 BIOS copy; starts at an odd halfword, so it reads the upper half of each instruction |
| `0x4ede20..0x4f320f`, `0x4f3a48..0x4f40c7`, `0x4f4210..0x4f4c97`, `0x4f5260..0x4f5537`, `0x4f58d0..0x4f5f4b`, `0x4f6098..0x4f677f` | start on word boundaries, so they read the lower half of each word (quirk 37) |

- A value `0x8c00..0x8fff` or `0xac00..0xafff` (the upper half of `lw` /
  `sw`) gets `0xc00` added, which makes it `lwr` / `swr`. For an aligned
  address these load or store the same whole word; for a misaligned one they
  do a partial access instead of raising an address error.
- Otherwise a value `0x3c01..0x3c1f` (`lui` with `rs` 0 and `rt` 1..31) has
  the same test and change applied to the 16 bits just before it, the
  `lui`'s immediate. POPS's recompiler builds the code it emits from such
  templates, so the code it generates for the game uses `lwr` / `swr` too.

On the reference POPS core this changes **10,210** halfwords.

`$ORIGINAL_OPCODES` (`0x894254`) only sets the flag; the pass is skipped and
POPS keeps its own instructions.

## launcHER

`pops_apply_opcode_pass()` (common/src/pops_modes_patches.c), run by
`launchPOPS` unless `$ORIGINAL_OPCODES` is in the config, as the last change
to the staged core: after fix files, the built-in list, `$RESET_WARMBOOT`,
the `MODULE_n.IRX` name pokes and the resident hooks, so no launcHER guard
ever compares against its result. Before this, launcHER never ran the pass:
every launcHER launch behaved like a POPStarter launch with
`$ORIGINAL_OPCODES`.

Evidence: `tools/test_pops_opcodes.py` (in CI). Native cases cover every
boundary; with `POPSTARTER_TEST_ELF` and unicorn the original's function runs
as shipped and launcHER's result is byte-identical on two random cores
seeded with boundary values and, with `POPS_TEST_ELF`, on the real core (all
10,210 changes).
