# POPSTARTER replacement handoff — 2026-10-08

Branch: `codex/popstarter-replacement`, based on `EMBER` and including merged
OPL argument compatibility PR #19 (`c616e0cdccc2af24fd2e4e956fff167f822da4bf`).
This branch is unfinished development. Do not merge or publish it as working
POPS support without completing the runtime and console validation.

## User's intended outcome

launcHER remains an application-invoked launcher without a GUI. Support external
Ember and external Sony POPS from one launcher. Replace POPSTARTER's setup,
patching and runtime responsibilities with full parity and better direct device
support, without requiring BDMAssault. Do not implement a new POPS emulator or
include proprietary POPS, IOP images, extracted Sony IRXs or game payloads.

## Implemented

- `common/src/pops_external.c`: ELF/TROJAN/PATCH inspection, guarded payload
  staging and configuration intent. Native PAK decode in `pops_pak.c` uses pinned
  public-domain LZMA SDK files; input/output limits and truncation checks apply.
- `pops_iop_image.c`, `pops_profile.c`, `pops_boot_stage.c`: bounded ROMDIR checks,
  exact SHA256 reference identities and caller-owned core/IOP/BSS staging.
- `pops_core_patches.c`: six original core groups (36 writes) plus a storage
  bridge group (12 writes). All selected guards are checked before any writes;
  apply selected groups together to the identified unmodified core.
- `launcher/iop/popfs`: own compiled/embedded IOP filesystem proxy. Explicit
  backing paths for four discs and two cards; Sony disc/card/backup aliases map
  to these paths. Read-only discs, underlying errors, short I/O, descriptor zero,
  64-bit seeks, save-volume sync and handle lifetime have host coverage.
- `initPopsServices()` in `launcher/src/init.c`: post-reboot service helper.
  Identifies the unmodified core, loads its external Sony SIO2 module, reuses the
  selected backend module list while skipping SDK SIO2, then loads the proxy.
- `common/include/pops_bootstrap.h`, `common/src/pops_bootstrap.c`: defines memory
  layout boundaries, formats proxy argument strings, and initializes trampoline
  arguments with preserved argv string `"pops0:IMAGE.VCD"` in bram at `0x00084230`.
- `launcher/src/pops_trampoline.S`: position-independent MIPS trampoline executed
  at `0x00084000` in BIOS unused RAM (`bram`), below 1 MiB. Sets stack pointer to
  `0x0008fff0`, zeroes scratchpad, zeroes POPS BSS (`0x00502e60`..`0x00865940`),
  wipes launcHER low RAM (`0x00100000`..`0x00200000`), copies staged core from
  `0x01000000` to `0x00200000`, flushes caches via syscall `0x64`, and enters POPS
  via syscall 7 (`ExecPS2`).
- `launcher/include/handler_pops.h`, `launcher/src/handler_pops.c`: runtime caller
  integrated into `launchPath` and `handleQuickboot`. Identifies VCD targets,
  discovers external dependencies, sets up VMC files (formatting 128 KiB card if
  missing), stages core and IOPRP in high RAM (`0x01000000`), applies guarded core
  patches and TROJAN payloads, reboots IOP with verified external image via
  `SifIopRebootBuffer`, invokes `initPopsServices`, mounts PFS if APA, and transfers
  control to the trampoline.
- Host checks and PS2SDK build jobs are configured on the development branch.

## Next work and constraints

1. Test on real PS2 hardware and diverse storage backends (USB, internal HDD/APA,
   MX4SIO, MMCE).
2. Validate in-game VMC saving and persistence across console power cycles.
3. Validate multi-disc switching and additional TROJAN patch slots.
4. Test IGR and clean console poweroff. The retained Sony poweroff thread calls
   HDD/DEV9 services, so direct-storage shutdown needs separate handling.
5. Audit module lifetimes and SIF RPC re-initialization during repeated launches.

Sony POPS binds FILEIO RPC `0x80000001`; installed SDK fileXio uses
`0x0b0b0b00`, so a same-ID conflict was not established. SDK iomanX's legacy hook
bridges old imports, including stat conversion. Verify its layout assumptions
and behavior with the external Sony IOMAN. Modern fileXio is not a replacement
for Sony's FILEIO protocol.

The storage group preserves delay slots, skips Sony DEV9/ATAD/HDD/PFS loads,
bypasses only two partition-mount calls (retaining poweroff thread setup), and
redirects eight fixed `pfs0`/`pfs1` prefixes to `pops`. Backing volumes must
already be prepared; their identity comes from explicit paths. Never interpret
`massN` as USB identity or invent a missing APA partition.

## Evidence and reproduction

Current local checks pass:

```text
python tools/test_launch_args.py
python tools/test_popfs.py
python tools/test_pops_external.py --elf C:/Users/natha/Github/POPS/POPS.ELF --iop-image C:/Users/natha/Github/POPS/IOPRP252.IMG
```

Earlier full external checks passed 4,820 corpus files plus two root specimens,
both PAK variants, loose ELF/IOP dependencies, independent decompression and
36-write original-source whole-buffer comparison. The final SIO2-skip addition
was checked against the loose dependency set in this handoff; rerun both PAK
variants and source parity using the commands in `POPSTARTER_REPLACEMENT.md`.

Latest local PS2SDK compile/link/pack passed with the cached image
`ghcr.io/ps2homebrew/ps2homebrew:main`, image ID
`sha256:1037f40df12cf2d1875dcfdc368ed7f70feb0eff186498c4e10ff874ef531a1b`.
Artifact `build/pops-ps2sdk/release/launcHER.elf`: 213,924 bytes; SHA256
`1b8b262b0ec02d88f9a1985f2e1fb899b27aa498d856587fb9a0d3beaa93b914`.
Build output includes filesystem clock-skew and format truncation warnings.
This is target build evidence, not a console result. Build output is ignored
and is not committed.

External references are read-only, not dependencies to distribute:

- `C:/Users/natha/Github/POPS/build/parity/popstarter/decompiled.c`: measured
  clean R5900 original loader exports.
- `C:/Users/natha/Github/POPS/build/parity/pops/decompiled.c`: measured Sony core;
  inspect FUN_002002a0, FUN_002004f0, FUN_00210540, FUN_0020cf00, FUN_00214938.
- `C:/Users/natha/Github/POPS/popstarter/PFS_WRAP.BIN`: original proxy reference.
- `C:/Users/natha/Github/REPOP/popstarter`: external patch corpus. Older REPOP
  reconstruction has wrong patch labels/widths and speculative filesystem/VCD
  code; use the measured original exports instead.

Read `docs/POPSTARTER_REPLACEMENT.md` for detailed hashes, dependency sets,
module ranges, capability gaps and validation boundaries. GitHub CLI's default
saved token is stale, but Git credential manager successfully authenticated Git
push and GitHub operations for PR #19. Never print credentials in logs.
