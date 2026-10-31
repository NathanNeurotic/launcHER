# Manual GS DISPLAY contracts — 2026-10-31

The pinned original MAIN profile is SHA-256
`734c813e8e8ec2c6729ec5e15dd46ab696e90deeade8d0b2ca3ad03782781aa1`;
its unpacked image at `0x870000` is SHA-256
`185177c28aaef30ad1e00697ad7b6de22b55bd855253ab4ede8b1ab2dfb08aee`.
The external Sony POPS core is SHA-256
`59df3389c4df88a572daa720b05507c52c34eddfa0031a6fbeec55e0c2d0fcb1`.
No original code, Sony bytes or game/save data is included.

## Original behavior

The six commands `$DX_`, `$DY_`, `$MAGH_`, `$MAGV_`, `$DW_`, `$DH_`
accept one through five decimal digits, including zero and leading zeroes.
They accept 65536 through 99999; truncating to 16 bits would be incorrect.
The first valid value for each command in a file wins. The six acceptance
flags are file-local, at frame offsets `0xfc..0x110`. The numeric globals are
GP offsets `0x4fb4,0x4fb8,0x4fb0,0x4fc8,0x4fc4,0x4fc0` respectively.

Identified windows are `0x8866a8..0x888050`, `0x888050..0x8899f8`,
`0x8899f8..0x88b3e0`, `0x88b3e0..0x88cdc8`, `0x88cdc8..0x88e770`,
`0x88e770..0x890118`. The bounded interpreter executes their integer/branch
instructions; parser tokenization and poke calls are modeled. End-of-file
window `0x89e75c..0x89e884` requires all six flags before it writes anything:

```
DISPLAY = (uint64_t)(uint32_t)(DH - 1) << 44
        | (uint64_t)(uint32_t)(DW - 1) << 32
        | (uint64_t)MAGV << 27 | (uint64_t)MAGH << 23
        | (uint64_t)DY << 12 | DX
```

There is no extra field mask: even zero width/height preserve the original's
32-bit subtraction underflow. A complete later file replaces the override;
an incomplete file does not combine its fields with earlier files and does
not erase an earlier completed override. The original installs its fixed
DISPLAY entry at `0x239768`, writes its value at `0x239778`, jumps there from
`0x21a094`, and restores `andi a0,s1,1` at `0x23acb0/0x23ad0c`.

This is distinct from the progressive helper at `0x2394f0`. `$480p` and
PATCH actions 6/7 remain unimplemented; the latter still reject atomically.

## Independent production implementation

`PopsConfig` accumulates six first-valid 32-bit values. Successful file opens
reset their acceptance mask. A completed set stores the computed 64-bit
value separately, so incomplete later files preserve it. `pops_config_parse_line`
can also be used as a stream after `pops_config_init`.

The current resident image format is version 3, with a 32-byte header carrying
separate VBLANK, manual display and progressive entries, and an 8-byte-aligned
configuration. The progressive entry is not selected yet. The earlier manual
checkpoint used version 2 and a 28-byte header. Its first config
field is the DISPLAY value; a static offset assertion binds the assembly ABI.
The independent four-instruction bridge loads that value using `v0`, restores
`v0=0x12000000`, and jumps to the stock continuation at `0x21a098`. It needs
no stack, GP, kernel call or library. The displaced core instruction is
`ld a1,0x10(s0)`; its predecessor sets `v0=0x12000000`. The existing delay
slot sets `v1=0x12000000`, and stock code then writes the value to both GS
DISPLAY registers.

A completed manual file clears HDTVFIX at its end, regardless of command
order within that file; a later file can set HDTVFIX again. The parser tracks
that state and config staging restores the interlace arguments. A later
`$480p` supersedes an earlier fixed DISPLAY override. A complete manual set
in a file containing `$480p` is recognized but rejected before handoff until
the progressive core state is implemented.

The installer checks the load at `0x21a094`, its delay slot at `0x21a098`,
and both interlace argument sites before any write. It permits the current
owned jump for idempotence and the known `$HDTVFIX` value at the argument
sites, preserves their already-staged state and rejects every other value. All setup
checks occur before IOP reboot. A display-only configuration installs only
the display hook; cheats independently select the VBLANK hook. The resident
image is still copied as the last write before the trampoline.

## Verification and limits

- 228 original file cases compare all six parsed values/flags, all-or-none
  acceptance and the final 64-bit DISPLAY value. These include all 64
  incomplete/complete masks, boundaries, invalid input, duplicates and 96
  deterministic shuffled sets. Existing 1,596 direct display inputs and two
  position-state cases remain passing. Another 18 original file sequences
  check HDTVFIX/NOHDTVFIX/progressive request order before, within and after
  complete or partial manual files. The progressive state itself is not
  claimed as implemented.
- Host regressions cover file boundaries, incomplete-file preservation,
  replacement by a complete later file, all four guard failures without any
  writes, bounds, idempotence and display-only/combined resident config.
- The hook guards pass on the pinned external Sony core.
- Normal and trace/debug PS2 builds pass; the resident image uses `-Werror`.
  The original manual checkpoint was 2,704 resident bytes including configuration;
  the current image with the unselected progressive bridge is 3,936 bytes.
- Built-image Unicorn checks retain VBLANK chaining/cheat tests. The actual
  display jump, its delay slot and all 31 nonzero GPRs are checked at the
  continuation for four DISPLAY values. An optional original comparison
  executes the pinned original fixed entry and compares the same register
  results. This observes the emulator's 64-bit GPR view, not upper EE lanes.
- The aggregate external entry point passes 109 tests with both inputs;
  all 18 host entry points pass. Default CI skips six external-input cases.

These are component/host/build/emulated results. No new console run, GS
picture, scanout timing, game acceptance or 100% parity is established.

```sh
POPS_TEST_ELF=/external/POPS.ELF \
POPSTARTER_TEST_ELF=/external/MAIN/POPSTARTER.ELF \
python3 tools/test_pops_external.py
python3 tools/test_pops_resident.py
POPSTARTER_TEST_ELF=/external/MAIN/POPSTARTER.ELF \
python3 tools/check_pops_resident_image.py build/launcher/pops_resident.bin
```
