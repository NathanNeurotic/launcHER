# Progressive DISPLAY component — 2026-10-31

This is a measured arithmetic/state candidate, **not a production progressive
hook**. `$480p` and PATCH actions 6/7 remain unfinished. The earlier independent
[manual DISPLAY hook](POPS_MANUAL_DISPLAY_CONTRACTS.md) is separate.

The original loader copies `0xd60` bytes from `0x983890` to `0x238a90`.
The progressive entry is at source `0x9842f0` / runtime `0x2394f0`, and rejoins
Sony code at `0x21a098`. Whole original hashes are pinned in the bounded
interpreter and [metadata-only evidence](evidence/pops_progressive_component_2026-10-31.json).
Sony REGINFO identifies GP `0x50a670`. No copied code or proprietary bytes
are distributed.

## Observed state contract

If the word at `0x85a9ac` is nonzero, the original uses the low 64 bits of its
quadword load from `0x70003290` and skips the state writes below. Its flag's
higher-level meaning is not inferred. Otherwise it:

- Writes `0x50` to `0x70003300` and `0x21af94`, `0x8a3a2` to `0x502770`,
  and `0x69403` to `0x23ac08`. Its scratch doubleword at `0x502680` ends at
  `0x69403`, after intermediate values `0x50` and `0x8a3a2`.
- Computes DY from logical `word[0x700032a8] >> 1`, tripling it with 32-bit
  wrap unless byte `0x127ff52` is `E`. DH is `word[0x700032b0] << 1`, with
  32-bit wrap. MAGV is 1 and MAGH starts at 0.
- Uses the width word at `0x700032bc` as follows. The source names identify
  addresses rather than assuming their higher-level rendering roles.

| Source width | MAGH | DX | DW |
|---|---:|---:|---:|
| 256 | 4 | 320 | `word[0x700032ac] >> 1` |
| 320 | 3 | 320 | `word[0x700032ac] >> 1` |
| 384 | 2 | 384 | 1152 |
| 512 | 1 | 444 | 1024 |
| 640 | 1 | 320 | 1280 |
| Other | 0 | unchanged | unchanged |

For an unknown width it uses the existing DISPLAY at `0x70003290`, after
the preceding state writes. For a known width it packs DISPLAY with the same
32-bit DW/DH subtraction and 64-bit shifts/ORs as the manual contract. There
are no invented masks or clamps. The projected output words are MAGH, DX,
DY, DH, DW and MAGV at `0x502688..0x50269c`.

## Candidate and checks

`common/src/pops_progressive.c` updates an explicit 80-byte state structure;
it makes no hardware accesses, and is intentionally not linked into the
production resident image yet. The source reads and computes from caller
inputs, including stale DX/DW and preexisting state for the blocked branch.
This replaces neither the loader nor the live original helper.

428 cases cover known/unknown widths, region bytes, zero/nonzero block flags,
zero/high-bit/all-one operands, overflow and deterministic random states.
Native C and the actual compiled EE function both match the bounded original
instruction execution. Original execution rejects unknown instructions,
out-of-window PCs, calls and memory, and audits unexpected mapped writes.
The compiled function runs in Unicorn; all mapped 2 MiB outside its 80-byte
state must remain byte-identical, and saved GPRs/SP must be preserved.

Unicorn 2.1.4's memory-write hook produced a CPU exception for a taken branch
with SD in its delay slot; this was reproduced independently of the candidate.
The compiled runner uses fresh CPUs and compares memory after execution,
without that hook. It executes the actual compiled branch, store and return.

The integrated external test entry point passes **115 tests**, with both
external inputs, the EE compiler and Unicorn. Default CI skips eight optional
external/compiler cases. No target build is needed to reproduce native tests:

```sh
python3 tools/test_pops_progressive.py
POPSTARTER_TEST_ELF=/external/MAIN/POPSTARTER.ELF \
POPS_EE_CC=/toolchain/bin/mips64r5900el-ps2-elf-gcc \
python3 tools/test_pops_progressive.py
```

The original interpreter observes 64-bit GPR values; LQ's upper lane is not
compared. Final-state equivalence does not establish transient write ordering,
register effects of a new live bridge, GS output, timing or physical acceptance.
Next work is the live wrapper's displaced-load/delay-slot/register contract,
ordered state writes, static core guards and text/PATCH sequencing. Preserve
PATCH 6/7 rejection until those production dependencies exist and are verified.
