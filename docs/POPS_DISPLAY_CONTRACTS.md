# Original display command contracts — 2026-10-30

Six commands now patch the identified external POPS core without a dependency
on POPStarter's copied resident blocks. This is host staging verification;
picture quality, colour, rate and command interactions still need console
acceptance. The independent resident implementation remains unfinished.

## External identities and original execution

`tools/trace_original_pops_display.py` uses `decode_main` to require the entire
packed MAIN SHA-256
`734c813e8e8ec2c6729ec5e15dd46ab696e90deeade8d0b2ca3ad03782781aa1`
and unpacked image SHA-256
`185177c28aaef30ad1e00697ad7b6de22b55bd855253ab4ede8b1ab2dfb08aee`.
It interprets only these original EE windows:

| Command | Window (end exclusive) | Effect |
|---|---|---|
| `$SMOOTH` | `0x8864f0..0x8866a8` | 64-bit `0xa21a22a0341a0001` at `0x21af88` |
| `$LEFTADJ_n` | `0x890320..0x890a3c` | For 1..255 (1–3 decimal digits), write `0x64a50f00` at `0x21a0a4`, `0xfc450000` at `0x21a0a8`, then replace the first byte with the low byte of `4096-n` |
| `$XPOS_n` | `0x898840..0x89a2d8` | First valid 0..65535 (1–5 digits): halfwords at `0x21b128`, `0x21c114`; zero word at `0x221958` |
| `$YPOS_n` | same | First valid 0..65535 (1–5 digits): halfword at `0x21c18c`; zero words at `0x2219d0`, `0x21b130` |
| `$DWSTRETCH_n` | `0x89a2e4..0x89b60c` | 0..9999 (1–4 digits): halfwords at `0x23af40`, `0x23aff4` |
| `$DWCROP_n` | `0x89b618..0x89c920` | 0..9999 (1–4 digits): zero word at `0x221960`; halfwords at `0x21b12c`, `0x21c184` |

The initial `$SMOOTH` value was missing from the static command scan because
its constant propagator truncated registers to 32 bits and did not implement
the two `DSLL` instructions. The original constructs the full 64-bit constant
at `0x886664..0x886678`. There is no copied-code jump in this command.

The bounded interpreter preserves branch delay slots, sign extension and the
R5900 three-operand `MULT rd,rs,rt` result. It models only the original poke
and short memcpy services. Unsupported instructions, calls, reads, writes,
PCs or instruction budgets raise errors. Synthetic interpreter tests cover
the MULT result, taken-branch delay slot and rejection paths. It never enters
the original complete parser, GS, Sony runtime or console. Malformed original
numeric inputs can depend on preceding parser-local state; no full malformed
parser equivalence is claimed. launcHER accepts only bounded decimal digits
and ignores invalid values without modifying display state.

## Production integration and checks

The configuration parser retains explicit presence bits (so zero is a valid
value), first-valid X/Y state and last-valid width/left-adjust state.
`pops_apply_all_config_patches` calls the new guarded helper. Every selected
site is validated before writes; a late display guard failure also precedes
compatibility-mode writes. Expected bytes were read independently from the
whole-hash-identified Sony ELF. Repeated application of the same configuration
is idempotent. Legacy signed X/Y fields remain in the configuration structure;
only valid unsigned original directives authorize the new writes.

Reproduce from the repository root (Python standard library and host GCC):

```sh
python3 tools/test_pops_display.py
POPS_TEST_ELF=/external/POPS.ELF \
POPSTARTER_TEST_ELF=/external/MAIN/POPSTARTER.ELF \
python3 tools/test_pops_display.py
python3 tools/trace_original_pops_display.py /external/MAIN/POPSTARTER.ELF \
  '$SMOOTH' '$LEFTADJ_123' '$XPOS_65535' '$DWSTRETCH_9999'
```

Local result: all 11 tests pass with both external inputs, including **1,596
command inputs and two original one-shot states**. Each command compares the
entire staged core against the original window's measured writes, including
all 1,000 one-to-three-digit LEFTADJ numbers, decimal boundaries, leading
zeros and deterministic random position/width values. The external Sony test
verifies all 15 guarded sites. CI runs the nine synthetic tests and explicitly
skips the two external-input tests. Proprietary bytes are neither committed
nor emitted by the oracle.

PATCH video actions 6/7 remain rejected before payload/mode/context writes:
they install `j 0x2394f0` into a resident block launcHER does not install.
These direct command implementations do not unlock `$480p`, the `$DX/$DY`,
`$MAGH/$MAGV`, `$DW/$DH` family, widescreen, pads, timings or cheats.
