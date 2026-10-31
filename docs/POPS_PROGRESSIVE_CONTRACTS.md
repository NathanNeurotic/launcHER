# Progressive DISPLAY component — 2026-10-31

**Current state:** text `$480p` now selects the guarded independent resident
bridge. Its component and staging proofs are recorded below; no console/GS
acceptance is claimed. PATCH actions 6/7 still reject pending their separate
dispatch sequencing. The [manual DISPLAY hook](POPS_MANUAL_DISPLAY_CONTRACTS.md)
is a separate entry. Earlier candidate checkpoints below are historical.

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


## Original-address adapter checkpoint — 2026-10-31

`pops_progressive_live()` now implements the same state operations at the
original addresses, including all three intermediate scratch doubleword
writes and the exact ordered byte/word/doubleword stores. Its production form
uses volatile memory operations. Host tests replace only those operations
with a bounded memory map; no arithmetic or branch behavior is stubbed.
The blocked path performs no stores, while unknown widths keep stale DX/DW.

All **428 native adapter traces match original write addresses, values,
widths and order**, and return the same DISPLAY. The actual compiled EE adapter
also passes **428 cases** using its real loads/stores, with full final-memory
comparison across 32 MiB RAM plus 16 KiB scratchpad. Only a bounded 0x400-byte
C working-stack window is excluded; saved GPRs, restored SP and the 64-bit
return are checked. Earlier pure-state native/EE cases remain passing.
[Live-adapter metadata](evidence/pops_progressive_live_component_2026-10-31.json)
records current source and compiled function hashes. The earlier component
report remains pinned to its historical source checkpoint.

This adapter is **still not installed in the launcher**. The next bridge must
preserve the interrupted Sony function's register context (including opaque
upper lanes), HI/LO banks and stack, then resume at 0x21a098 with DISPLAY in
a1 and v0=0x12000000. It also needs static core guards and the original sticky
progressive/manual-display/text/PATCH sequencing. No scanout or console result
is established by memory comparisons. Reads are stable fixture inputs; this
does not claim equivalence under concurrent modification of the source fields.

Aggregate external suite: 118 tests with original/core/compiler/Unicorn;
default CI skips 10 optional cases. The native adapter runs in default CI.


## Built context bridge checkpoint — 2026-10-31

`common/src/pops_progressive_bridge.S` now calls the real compiled adapter
from a mid-function entry. The owned image is **version 3**, with a 32-byte
header and a separate progressive entry. It is built and embedded, but the
launcher **does not select that entry yet**. Text/PATCH enablement and static
mode guards remain the next integration step.

The bridge allocates its 544-byte frame before any save, avoiding a write
below the unadjusted stack pointer. It saves/restores all GPRs with quadword
moves, including opaque upper lanes, and both HI/LO banks. It calls the
adapter, preserves its 64-bit result, restores context, puts DISPLAY in a1,
sets v0=0x12000000 and rejoins 0x21a098. Stock code uses a1 only in two SDs
before the callee at 0x21a4f8 overwrites it; a0 is set from s1 at 0x21a0a8
and a2 is overwritten at 0x21a504. No original code block is copied.

`tools/check_pops_progressive_image.py` runs the actual owned image for all
428 state cases. On C entry it poisons GPR values/opaque upper lanes and all
four accumulator halves, preserving only the low SP and return address needed
to execute C. It verifies restoration, stack boundary guards, unchanged owned
image/config, original-address final fields and the stock resume contract.
A deliberately damaged GP restore is rejected. The actual linked C and its
ordinary instructions run in Unicorn. Only owned-bridge LQ/SQ and secondary
HI1/LO1 transfer slots are replaced in private CPU memory by NOP translations
and modeled explicitly outside hooks. The source/image files are unchanged.
These adapters model preservation of opaque upper lanes, **not a complete
R5900/MMI implementation or independent upper-lane hardware execution**.

[Bridge metadata](evidence/pops_progressive_bridge_2026-10-31.json) records
source/image hashes, the 344-byte entry, and 3,936 resident bytes including
configuration. Normal/trace target builds pass, and both existing VBLANK and
manual DISPLAY image checks still pass. The aggregate external suite passes
119 tests with all prerequisites; default CI skips 11 optional cases. The
bridge build/comparison is included in that aggregate optional entry point.

```sh
POPSTARTER_TEST_ELF=/external/MAIN/POPSTARTER.ELF \
python3 tools/check_pops_progressive_image.py build/launcher/pops_resident.bin
```

No live progressive hook, GS scanout, console run or parity completion is
claimed at this checkpoint. Preserve PATCH 6/7 rejection until its remaining
loader-state dependencies are handled separately.


## Guarded text selection — 2026-10-31 (current)

The launcher now selects the owned progressive entry for text `$480p`.
A separate `progressive_requested` bit remains set across `$NOPAL` and
`$FORCEPAL`; those region choices cannot silently remove the earlier video
hook or its disable-PAL state. The production fix-file session receives that
sticky state, and final PAL/region processing runs before static progressive
setup. A complete manual DISPLAY file selects the fixed entry instead, while
retaining progressive static mode state. A later `$480p` can select the dynamic
entry again. All setup remains before IOP reboot and save creation.

The resident installer validates all five sites before any selected write:
load `0x21a094`, its `0x21a098` delay slot, mode byte `0x21af94`, and argument
words `0x23acb0/0x23ad0c`. It writes the owned jump and mode byte `0x50`, plus
`li a0,0` by default. A later HDTVFIX selects `li a0,1`; NOHDTVFIX or same-file
completed manual DISPLAY restores `andi a0,s1,1`. Repeated installation is
idempotent. Unknown or conflicting payload changes reject atomically at this
step; the caller discards that staged launch. This preserves explicit conflicts
rather than replacing them under an unproven payload-ordering assumption.

31 original text/file sequences compare the configured mode, argument writes
and fixed/dynamic entry choice. The native pipeline additionally initializes
the fix session, finalizes video and processes a European licence, verifying
PAL suppression even when the final region directive is FORCEPAL/NOPAL.
All five guard corruptions, conflicting known values, bounds and idempotence
are covered. Guards and representative full-config staging also pass on the
pinned external Sony ELF. [Current metadata](evidence/pops_progressive_text_2026-10-31.json)
records source hashes and exact limits.

Aggregate external suite: **121 tests** with all inputs/compiler/Unicorn;
default CI skips 12 optional cases. All **19 host entry points**, normal and
trace target builds pass. Existing VBLANK/manual checks and the 428-case built
progressive context check remain passing. The owned image remains v3, 3,936
resident bytes. No console run, GS picture/rate/timing, broad game acceptance,
save durability or 100% parity is established. **PATCH 6/7 remain rejected**:
their mode/session sequencing and owned-entry dispatch must be implemented
and compared separately before those actions can be accepted.
