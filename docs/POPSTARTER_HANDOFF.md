# POPSTARTER replacement handoff — 2026-10-08

## Verified hardware checkpoint — October 13, 2026

Physical run `20261014T050940-0020` displayed `POPS_IOP_BINDING_PASS` and
`[ps2rig] exit=0` in the OBS console capture. The actual selected Sony IOP
image, original IOPCD and real SIF RPC passed both disc aliases, all five
sector-read tuples and four distinct card write/close/reopen/readback checks
(two direct, two through production POPFS). Storage was controlled IOP memory;
this does not establish actual-device persistence or a complete game boot.
Metadata: `docs/evidence/pops_ioman_fixed_console_probe.json`.

Two causal repairs resolved the earlier hardware failures below: private
`pops_iomanx` migrates Sony's identified linked/flat IOMAN layouts and all 32
file slots; POPFS accepts newly allocated recycled slots with stale private
data. The launcher now builds/embeds this compatibility module and selects it
only in the identified Sony post-reset initialization. Normal/Ember loading
continues to use stock SDK iomanX. The probe clears its final result screen so
progress output cannot hide acceptance markers. Its network rig outcome can
still be `hang`, because the foreign reset removes ps2link; the explicit GS
result is recorded separately.

Device inventory is now complete enough to select a real game. Run
`20261014T055003-0024` loaded the production ATA/MX4SIO drivers and found many
VCDs on the ATA exFAT partition. Earlier USB/MMCE-only inventories did not
cover those devices. The stable `ata0:/POPS/Tekken.VCD` alias and VCD metadata
were verified in `20261014T055350-0025`; never reuse the transient `mass2:`
number across resets. The original title folder has an existing VMCDIR.

Run `20261014T055930-0026` created fresh console directory
`ata0:/LAUNCHER-TEST-20261013-A/`, copied Tekken as `TEST.VCD` (115654480 bytes),
and copied the known loose `POPS.ELF` and `IOPRP252.IMG` from `usb0:/POPS/`.
Every copied byte was compared after close/reopen. Original title/config/save
files were preserved. The next production boot target is
`ata0:/LAUNCHER-TEST-20261013-A/TEST.VCD`; cards should be created under its
new `TEST/` folder. Sony input files remain console/local data, never distributed.
See the three metadata-only device/inspection/staging reports in docs/evidence.

`prepare_pops_device_inventory.py` defaults to read-only enumeration; explicit
`--inspect` ELF arguments run bounded VCD/config inspection, while explicit
`--stage-test VCD POPS_DIRECTORY NEW_DIRECTORY` creates only one fresh
`ata0:/LAUNCHER-TEST-*` directory and refuses reuse. No write mode runs by
default. Next: full production boot, then actual Sony card runtime and test-save
persistence across power cycles. Earlier checkpoints below are historical.

The first exact-CI-artifact game attempt (`20261014T060154-0027`) did not boot.
Opt-in trace run `20261014T061203-0030` then confirmed that ATA initialization,
the root and VCD opens, loose dependency discovery and VCD metadata all succeed;
configuration discovery returns -6 before any Sony handoff. The earlier
mount-failure interpretation was incorrect. See the metadata-only configuration
failure report. Next: identify the exact optional config path and preserve real
read/parse failures when fixing unavailable search locations.

For physical diagnosis, configure `-DLAUNCHER_BOOT_TRACE=ON -DDEBUG=ON` in a
separate build directory. It retains ten recent GS/EE-serial messages and stops
on errors. The default build is unchanged. Optional
`-DLAUNCHER_BOOT_TRACE_RECOVERY_ELF=mc0:/ps2link/PS2LINK.ELF` attempts relaunch
after 15 seconds, but reliable soft recovery has not been established; use the
user's automatic ps2link boot setup after a physical reboot if needed.
The inventory fixture also accepts `--inspect-config VCD_DIRECTORY GAME_BASE`
to exercise production configuration discovery without replacing ps2link's IOP.

## Current local continuation — October 13, 2026

Local development was fast-forwarded to PR #23 head
`472ae61a2f69d9f8eec7b8f3d9b77a4dc074b760`; pre-existing untracked scratch
files were preserved. Continue committing and pushing on this same PR branch.

The archived MAIN decoder now ran successfully. Its complete output also
matches an independent liblzma decode. Eleven embedded IOP modules validate,
including the actual 2,484-byte `PFS Wrapper r6a`. Sony's selected IOPCD is
embedded in POPS.ELF, **not** a ROMDIR entry in the loose IOPRP252 image.
Read `docs/POPS_IO_CONTRACT.md` for identities, locations and reproduction.
The self-contained `tools/trace_original_pops_io.py` now executes the original
IOPCD and wrapper with controlled imported services: 26 cases pass, including
TOC reads, aligned sector requests, descriptor zero, errors and close behavior.
The metadata-only trace is committed under `docs/evidence/`. The wrapper forwards
raw file-byte offsets; Sony IOPCD aligns the caller's supplied byte offset.
Production diagnostics now hash and inspect the **core-embedded** IOPCD before
patching/reset, and the POPFS host fixture replays the observed read/seek tuples.
Local validation passed: 56 external-core tests plus all three real dependency
sets, POPFS, VMC, 64 supported/192 unsupported mode masks, launch arguments and
eight feature tests. The feature assertion now uses host `errno.ENOTSUP`
instead of a Linux-only numeric value, so it also runs on Windows.
The existing GCC PS2SDK Docker compile/link/pack also passed; it still reports
pre-existing path-truncation warnings. Exact-head GitHub CI supersedes local
dirty-checkout artifact identities.

The original EE producer `FUN_00210090` now also ran unchanged in PCSX2:
seven cases pass with both GCC and LLVM harnesses. It constructs
`byte_offset = 0x100000 + LBA * 2352`, caps requests at 16 sectors, handles
disc-end counts and cache hits, and rejects mismatched reply counts. Five
observed EE tuples are replayed in the IOP probe. Preparation, overlap checks,
isolated runner and metadata-only GCC/LLVM reports are all committed; no
original-byte probe ELF/C array is distributed. Three synthetic input/layout
guard tests are also in CI. See `docs/POPS_IO_CONTRACT.md` for exact reproduction.

The actual Sony IOP image and SIF RPC binding probe now passes in isolated
PCSX2 with the production iomanX/fileXio/POPFS modules and original IOPCD.
It exposed a production startup error: MODLOAD supplies `LBbyEE` at argv[0],
so POPFS must read its packed mode from argv[1]. The host fixture now models
that real loader contract. Proxy argument packets are also limited to the
SDK LOADFILE RPC's 252 bytes; larger configurations fail before side effects
instead of being silently truncated. The 57 external-core tests and updated
POPFS contracts pass. The real-kernel probe also checks both card aliases with
different direct/bridged write patterns and close/reopen byte verification on
controlled IOP memory. This does not establish physical-media persistence.

Next: one end-to-end device boot and VMC save/reload/power-cycle test, plus
full runtime patch/parity acceptance. Do not introduce a second VCD offset
remap. See `docs/POPS_IO_CONTRACT.md` for the real-kernel probe and an important
PCSX2 descriptor-1 console interception caveat.

Physical-console continuation: the user enabled ps2link. The native original EE
request probe passed all seven cases in ps2rig run `20261013T181122-0001`
with `[ps2rig] exit=0`. This is actual R5900 hardware execution with modeled
imported services, not a full POPS boot or save test. The source now prints rig
exit markers and the metadata-only console result is committed. Continue with
real IOP-kernel/RPC binding; a custom IOP reset removes ps2link services, so
validate the foreign-image probe in isolated PCSX2 before console deployment.

The older sections below are historical checkpoints, not current acceptance.

Hardware binding attempt `20261014T004047-0013` subsequently rebooted into
Sony's image and displayed successful iomanX/fileXio/backend module returns
on the physical capture. It stopped at `load=production-popfs`, without a
return status or PASS/FAIL marker. This hardware boundary remains unresolved;
the emulator pass must not be substituted for it. The metadata-only attempt
is committed under `docs/evidence/original_pops_iop_console_attempt.json`.
The user authorized selecting any installed VCD and restarted ps2link.
A read-only inventory loaded production USB/MMCE stacks and observed two USB
disks mounted by BDM/FatFs, but no completed directory/game selection yet.

The startup watchdog now pinpointed the physical stall: run
`20261014T010845-0017` repeatedly showed POPFS device-check index 0 with
pointer `0x00000003`. Sony IOMAN 2.03 uses linked device nodes where the SDK
legacy hook expects an array; the hook copies file flags as device pointers.
Both 252 profiles share that module; the 2305A profile has the older flat
2.01 layout. A separate SDK-derived `pops_iomanx` candidate now validates and
migrates both layouts and all 32 descriptors. Host regressions and the
controlled PCSX2 bridge pass with only iomanX replaced. It remains a candidate,
not selected by production yet. Next: compare on hardware using unchanged
production POPFS and original IOPCD, then integrate only in Sony post-reset
initialization if that passes. The prepared local hardware comparison is
`build/pops-iomanx-candidate-console/gcc/bin/pops_iop_binding_probe.elf`.

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

## Current continuation checkpoint (2026-10-09)

The published boot repair is `16aa41cc24806bf00a0259be3c6d4f18afa33d0a`.
Its GitHub Actions run 37938178727 passed host checks and PS2 target packaging.
The older local artifact/hash above is historical, not the current artifact.

The next repair protects existing VMCs, formats new raw cards, checks both card
results, separates title configuration/fixes from save redirection, and rejects
enabled cheats before the unsafe staged-core write. The resident cheat engine
is still missing. See the revised capability matrix and repair checkpoint in
`POPSTARTER_REPLACEMENT.md`; earlier component descriptions are not parity proof.

Original PATCH loader evidence begins near line 3206 in the measured POPSTARTER
decompile: numbered PATCH files use a 64-byte header and additional original
validation/dispatch, separate from TROJAN handling near line 2822. Reconstruct
these rules before connecting the generic container stager to runtime discovery.

Compatibility continuation: Modes 1..5 and 7 now use guarded measured writes
from FUN_008dc2c4, verified against complete external-core buffers for every
supported mask. Modes 6/8 reject without mutation. Trace original DAT_009b9d48
state/caller ordering and Mode 6 OSD globals next; do not reuse speculative
`POPS/popstarter/src/runtime_hooks.c` mode switches (they were the source of the
incorrect single-write implementations). Optional reference reproduction is in
`POPSTARTER_REPLACEMENT.md`. No new hardware result has been obtained.
