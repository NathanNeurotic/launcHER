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
  It does not reboot, mount backing partitions or enter POPS. No runtime caller
  exists. The storage patch skips Sony's SIO2 load to avoid loading it twice.
- Host checks and PS2SDK build jobs are configured on the development branch.

## Next work and constraints

1. Implement the external dependency/request path and isolated POPS bootstrap.
   Preserve sources, IRXs, arguments and bootstrap state outside core/BSS load
   destinations. Enter through a trampoline below 1 MiB; staging directly from
   the normal launcher would overwrite its executing code/data.
2. Reboot with the identified external IOP image, restore selected device
   services, configure/mount actual backing volumes, load the proxy, apply
   selected core patches and enter POPS with a verified argv contract.
   `utils/loader` currently has IOPRP loading disabled. Ordinary ELF handoff can
   reset away the proxy or shut down its storage; preserve Ember behavior.
3. Audit the new post-reboot helper and module lifetimes before wiring it up.
   Its caller must establish the correct external IOP; module imports, resident
   return handling, repeated initialization and cleanup still need runtime
   validation. Exact image identity is not proof of IOP compatibility.
4. Complete VMC creation/policies and save persistence, multi-disc switching,
   remaining POPSTARTER settings/patches, IGR and poweroff. The retained Sony
   poweroff thread still calls HDD/DEV9 services, so direct-storage shutdown
   needs separate handling. Proxy devctl/mount/directory enumeration remain
   unsupported; do not silently report operations as successful.
5. Test on real consoles/storage. No POPS boot, gameplay, saving, IGR or
   full-device-support result has been obtained.

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
Artifact `build/pops-ps2sdk/release/launcHER.elf`: 210,772 bytes; SHA256
`e3784706e82e9da7f7f95ef40735141a44f7767e8ca399ef4d407b76b5427add`.
Build output includes filesystem clock-skew and an existing quickboot snprintf
warning. This is target build evidence, not a console result. Build output is
ignored and is not committed.

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
