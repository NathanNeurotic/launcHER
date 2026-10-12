# POPStarter replacement in launcHER

launcHER remains an application-invoked forwarder. Existing applications provide
the game selection and user interface. The project adds the POPStarter role
around an external, user-supplied Sony POPS installation alongside the existing
Ember launch path. It does not reconstruct or distribute POPS, its BIOS or its
proprietary packages. No GUI or game library is part of this work.

The objective is full POPStarter capability replacement, plus direct device
support without requiring BDMAssault. The first implementation is the external
file/container core, not a working POPS launch mode. Existing Ember arguments,
quickboot behavior and IOP handoff are unchanged.

## Current implementation

### External dependency sets and boot environment

POPS.ELF alone is not a complete POPStarter-compatible installation. Support
must cover both existing external layouts rather than require all filenames
unconditionally:

| Installation form | External input | Contents/responsibility |
|---|---|---|
| Loose files | POPS.ELF plus a compatible IOPRP252.IMG | EE executable and a separate IOP reboot image; traditionally used by the HDD workflow |
| Packed IOX | POPS_IOX.PAK | Compressed POPS memory image plus an IOPRP2305A image in the inspected specimen |
| Packed legacy | POPS.PAK | Compressed POPS memory image plus an IOPRP252 image in the inspected specimen |

Read-only decoding of the local reference packages on 2026-10-08 confirmed:

- POPS.PAK decodes to 3,422,833 bytes: a 3,157,600-byte core followed by a
  265,233-byte image containing `ioprp252`.
- POPS_IOX.PAK decodes to 3,402,681 bytes: the same-sized core followed by a
  245,081-byte image containing `ioprp2305a`.
- Both decoded cores have SHA-256
  `38ecd425324a1244e90ae68b927496b9af511fd0ed89761199fb6eb699e71ab0`.
- The loose IOPRP252.IMG and the PAK's appended IOPRP252 image have different
  hashes despite equal lengths. Filename and length do not establish equivalence.

The original loader copies the appended IOP image from 0x00502e60 into a separate
allocation and clears its staging region. The replacement must reproduce the
required dependency selection, unpacking, image identity/version handling,
IOP reboot and module interception, RPC initialization, storage bridge setup,
VMC setup, runtime patches and final handoff. Dependency discovery is not merely
an existence check for POPS.ELF.

PAK payloads are loaded memory images, not ELF files with program headers;
`pops_elf_inspect` cannot validate them as-is. The native replacement unpacker is
now implemented, together with exact reference package/image profiles.
The current research unpacker that
extracts and emulates POPStarter's own decoder is evidence tooling, not a runtime
implementation suitable for eliminating POPStarter.

Exact discovery/fallback order and IOP service lifetimes remain reconstruction
work. The replacement should produce a validated boot plan for the selected
external dependency set before changing memory or rebooting the IOP. Required
files/services that are missing or unsupported must fail explicitly. None of
these external binary components is included in launcHER's distribution.

### Implemented file and container core

`common/src/pops_profile.c` identifies the measured POPS core and all three
dependency sets by SHA256 before producing a boot plan. The loose IOPRP252 and
packed IOPRP252 remain separate variants despite their matching sizes. Unknown
cores, modified modules and unmeasured combinations fail explicitly. The hash
implementation is allocation-free and checked against hashlib across SHA256
padding/block boundaries and inputs up to one million bytes.

`common/src/pops_boot_stage.c` stages those verified dependencies into disjoint
caller-owned RAM, scratchpad and reboot-image buffers. It copies ELF load
segments or the decoded flat core, clears the ELF's low RAM reservation and
core/scratchpad BSS, and preserves the IOP image separately. Buffer capacity and
alias checks precede every write. It never writes live EE addresses itself.
All three dependency sets produce the exact same measured loaded-core hash.
The host checks cover capacity failures without mutation, destination aliasing,
preserved reboot-image bytes and canaries beyond every written range.

The reference plan enters at 0x00200008, loads the core at 0x00200000, clears
core BSS from 0x00502e60 to 0x00865940, and clears 0x3c30 scratchpad bytes.
The existing ELF trampoline is linked below 0x00100000. Its current IOPRP support
is disabled; these buffer APIs do not enable it or authorize a live handoff.

`common/src/pops_core_patches.c` stages 36 exact original writes in six selectable
groups. It requires the unmodified reference core's SHA256 and checks every
selected site before writing any site. Apply the selected groups together before
Trojan/game-specific patches. Reapplication fails closed. These are buffer
patches, not a complete POPS boot environment.

| Group | Original clean R5900 function | Writes |
|---|---|---:|
| Genuine HDD check | FUN_008db778 | 1 |
| CDROM license loop | FUN_008dba90 | 1 |
| Exception breakpoints and associated original redirects | FUN_008dbafc | 22 |
| sceCdPowerOff call fix | FUN_008dbe78 | 1 |
| Delcro's other patches | FUN_008dbf58 | 2 |
| SifLoadModuleBuffer error exit calls | FUN_008dbfd4 | 9 |

This corrects older reconstruction labels: the write at 0x00214860 is the
sceCdPowerOff fix, not the SifLoadModuleBuffer group. FUN_008dbf58 clears only
the low byte at 0x0020044c and 0x00200484; widening those writes to words destroys
the remaining instruction bytes. The original's strings confirm these group
names. An optional independent check reads the original decompiler export's
write sequence and compares the entire staged RAM buffer against its result:
all 36 writes match for each of the three dependency sets.

`common/src/pops_pak.c` decodes the length-framed PAK format using unmodified,
public-domain upstream 7-Zip LZMA sources pinned in `third_party/lzma`. It bounds
compressed and decoded inputs to 8 MiB, checks output capacity and aliasing,
and requires the exact declared output length. It converts the initial range
word's byte order and uses fixed lc=3/lp=0/pb=2 properties. Caller-owned output
may contain a partial decode on error and must then be discarded.

The IOX reference omits one final zero range-renormalization byte as well as the
LZMA end marker. SDK lookahead is padded with 20 zeros, but actual consumption
may exceed the input by at most one byte, only when the SDK reports
`MAYBE_FINISHED_WITHOUT_MARK` (zero range code). Both reference packages decode
byte-for-byte identically to Python's independent liblzma implementation.
The format has no checksum: structural decode alone cannot establish identity
or detect every corruption. Runtime authorization still needs image profiles.

`common/src/pops_iop_image.c` validates RESET/ROMDIR/EXTINFO ordering, RESET's
self-consistent aligned directory offset, a bounded directory with a zero
terminator, unique file names, every file extent and the complete EXTINFO
accounting. The final file's bytes must exist; trailing alignment padding is
optional. This follows the ROMFS layout documented by
[PS2SDK ROMDRV](https://github.com/ps2dev/ps2sdk/blob/master/iop/fs/romdrv/include/romdrv.h)
and its directory discovery rules. It does not validate module compatibility.
Both appended reference IOP images and the loose IOPRP252 image pass.

`common/src/pops_external.c` provides:

- ELF32 little-endian MIPS executable validation with program-header, file,
  memory, alignment, overlap and executable-entry checks. It accepts the external
  reference POPS's scratchpad BSS reservation without opening arbitrary MMIO
  addresses to loading. This is structural validation, not POPS identification.
- Byte-order-safe parsing of TROJAN_0..9 and PATCH_1..9 containers. Header control
  words and all 32 metadata bytes are preserved; metadata is not assumed to be
  exclusively a description string.
- Separate classification of executable Trojans, configuration-only records and
  data-bearing PATCH records.
- A staging plan that checks the payload and complete hook range before writes.
  The measured original J/JAL dispatch is implemented, including preservation of
  the existing delay instruction for JAL and optional instruction clearing for J.
- Guarded staging into a caller-owned memory buffer. Every guard/range/alias check
  precedes copying or hook installation. Header-only PATCHes cannot silently
  return a successful staging result: they need configuration handling instead.
- Decoding of PATCH control values 0..7 into the four compatibility mode bytes
  and video action intent. Control 6 remains explicitly unnamed because its
  user-facing meaning has not been established.

The source is included in the launcher build. No runtime caller is connected to
these functions yet. They do not open device files, initialize an IOP service,
flush caches, invoke a payload or transfer control. Staging into a host buffer
does not establish that any payload can execute correctly under POPS.

## Evidence and corrections

Measured on 2026-10-08 against external REPOP main
`8df3b3d21d85e541599e8c735d6249f71b5f6a2d`:

| Corpus population | Measured count |
|---|---:|
| `hugopocked-fixes/` plus `game-fixes/`, all `.bin` files | 4,820 |
| Executable Trojan containers | 3,951 |
| Header-only PATCH configuration records | 869 |
| Additional root specimens checked | 2 |

The root specimens are `TROJAN_7.BIN` and `PATCH_5.BIN`. Root PATCH_5 has a
`0x4fe80`-byte data payload at load address `0x002feff0`, with entry and hook zero.
It cannot be generalized from the header-only PATCH population.

The corpus's word at offset `0x08` has values 0 (3,947 files), 1 (865),
`0x00060000` (4), 2 (2), and 4 (2). Contrary to NEXT_AGENT_BRIEF.md's table, it
is not uniformly zero. The 869 header-only PATCH records include configuration
metadata: for example PATCH_4 records carry control 1 and mode 4 at offset 0x38.
They must not be discarded as inert stubs. Slot filename alone is also
insufficient to identify behavior; multiple artifacts can reuse the same name.

The original `FUN_00880a24` (Trojan loader) and `FUN_00881de8` (PATCH loader)
were read from the local R5900 ground-truth export. The original unpacked ELF
was inspected as well: the three J construction sites use `lui v0,0x0800`
at `0x00881b28`, `0x00881b84`, `0x00881bf8`; the default JAL site uses
`lui v0,0x0c00` at `0x00881c4c`. Low header type 2 takes the J branches;
types 1 and 3 reach JAL. Type 2 uses the control byte at offset 0x0a (not
the format byte at 0x0e) to select 1, 2 or 3 instruction writes, and falls
back to JAL for other widths. PATCH metadata at offsets 0x38..0x3b feeds the
compatibility dispatcher when control enables it.

Reference identities (metadata only; binaries remain outside this repository):

| External reference | SHA-256 |
|---|---|
| POPS.ELF | `59df3389c4df88a572daa720b05507c52c34eddfa0031a6fbeec55e0c2d0fcb1` |
| POPSTARTER_UNPACKED.elf | `92f356f96b9cae270201d322aceb1740bad62bc59b0f6623e60b20de7e2a5a96` |

The POPS ELF is 3,166,988 bytes, enters at `0x00200008`, and has four PT_LOAD
segments. One reserves scratchpad `0x70000000..0x70003c30`. These observations
apply to that image; they do not identify every POPS variant.

## Capability worklist

### Next IOP integration contract

The measured POPS `FUN_002002a0` transfers these embedded external IRX ranges
through `FUN_002001d8` (IOP allocation, SIF DMA, load/execute and result check).
Names and versions below were read independently from each ELF's `.iopmod`
section; these IRXs remain inside the external POPS core.

| Module | Version | EE source range, end exclusive | Original condition |
|---|---|---|---|
| sio2man | 2.5 | 0x002cbbc0..0x002cd559 | Always |
| padman_hsync | 4.5 | 0x002cd560..0x002d8345 | Always |
| Sound_Device_Library | 3.3 | 0x002d8350..0x002df2ed | Always |
| sdr_driver | 4.1 | 0x002df2f0..0x002e0f81 | Always |
| dev9 | 2.2 | 0x002e0f90..0x002e40d5 | Module-init parameter nonzero |
| atad | 2.4 | 0x002e40e0..0x002e6f75 | Module-init parameter nonzero |
| hdd | 2.2 | 0x002e6f80..0x002ee47d | Module-init parameter nonzero |
| pfs | 2.1 | 0x002ee480..0x002fa81d | Module-init parameter nonzero |
| IOPCD | 1.1 | 0x002fa820..0x002fe66f | Always |

The startup routine `FUN_002004f0` chooses the nonzero module-init parameter
after parsing a partition from its launch argument, then mounts `__common`
and the game partition through `FUN_00214938`. With no parsed partition it skips
that embedded storage group and calls disc initialization with a null path.
That alternate path is not an established arbitrary-device VCD launch recipe:
it also selects different disc and VMC initialization branches.

`FUN_00210540` binds RPC server 0x435052, issues initialization/image-open
requests and fetches a 0x400-byte TOC response. `FUN_0020cf00` initializes two
0x20000-byte save images when its parameter is nonzero. Preserving those
external Sony disc/audio/controller components while adapting the filesystem
and storage services is the next integration question. Launch-time device
availability alone cannot prove these services survive or remain compatible.
The old reconstructed host `pfs_wrap.c` and `vcd_bat.c` are not usable IOP
implementations: their stdio paths and speculative format handling do not
establish the original driver or RPC contracts.

Every row is part of the target. Host code, EE build, IOP behavior and console
validation are separate gates. No row below currently claims a working POPS boot.

| Capability | Implemented so far | Remaining acceptance work |
|---|---|---|
| Existing Ember forwarding | Existing implementation preserved | Regression check after adding the POPS handoff |
| Application launch contract | Existing target/argument and CNF paths inspected | Define explicit POPS installation/game request and errors without changing Ember callers |
| External POPS load | ELF/ROMDIR inspection, native PAK decode, exact reference identity, guarded core/IOP/BSS buffer staging | Dependency discovery, live placement, loader coexistence and executable handoff |
| Trojan and PATCH support | Parsing, options decoding, guarded buffer staging | Slot precedence, version gates, overlap/order policy, complete configuration semantics, resident execution and cache handling |
| Core POPS patches | Six guarded groups, 36 original writes; whole-buffer comparison against the original sequence | Remaining original patch/configuration groups, path/environment redirects, interactions and runtime dependencies |
| VCD layout and disc access | No runtime implementation | Real VCD layout, sector translation, command/RPC/DMA contracts, retries, EOF and streaming behavior |
| Direct storage without BDMA | Own IOP filesystem proxy compiles and is embedded; guarded storage-load, partition-mount and pathname redirects stage successfully | Bootstrap the proxy and backing services across external IOP reboot; validate Sony legacy IOMAN/file-service interaction and hardware streaming |
| VMCs and saves | No runtime implementation | Creation, naming, slot modes, read/write, dirty flushing, failure recovery and persistence across exit |
| Configuration and compatibility modes | Header options decoded | Defaults, global/per-game precedence, text commands and original mode effects |
| Cheats, game fixes, protection handling | External corpus can be parsed | Faithful selection and execution; distinguish POPS-memory and guest-memory targets |
| Video and controller options | PATCH action intent decoded only | Original settings and hooks, interactions, controller/multitap behavior and hardware checks |
| IGR and power-off | No runtime implementation | Runtime hooks, clean save/device flush and caller/BOOT.ELF/OSD exit behavior |

For storage, launcHER already has handlers for USB, ATA BDM, APA/PFS, MMCE,
MX4SIO, i.Link, UDPBD and UDPFS. SMB support must be assessed independently.
Those launch-time handlers do not prove POPS can keep using a device after its
IOP setup. The replacement should present POPS's required disc/save interface
through its own bridge and keep backing devices independent of that interface.
BDMA is not a required component of the proposed architecture. Which transports
share that bridge and which need additional adaptation is still to be measured.

The next implementation slice is the external image profile and IOP/storage
contract, followed by one end-to-end device boot with VMC persistence. Expanding
device coverage and reproducing the full capability set remain required work.

## Reproducing the checks

The committed checks use synthetic fixtures and compile the production C source
with a host GCC-compatible compiler. They require Python 3 and a compiler, not
PS2SDK or any proprietary files:

```text
python tools/test_pops_external.py
```

Optional read-only checks against an existing external installation:

```text
python tools/test_pops_external.py --corpus-root C:/Users/natha/Github/REPOP/popstarter --elf C:/Users/natha/Github/POPS/POPS.ELF
python tools/test_pops_external.py --pak C:/Users/natha/Github/POPS/POPS.PAK --pak C:/Users/natha/Github/POPS/POPS_IOX.PAK --iop-image C:/Users/natha/Github/POPS/IOPRP252.IMG
```

Add `--loader-source C:/Users/natha/Github/POPS/build/parity/popstarter/decompiled.c`
to compare core patch output with the measured original clean R5900 exports.
This input remains external and is never used by launcHER at runtime.

The runner preserves and checks every parsed header field against an independent
binary decode, checks every corpus staging range, and decodes every PATCH's
configuration intent. It never copies the input files into the repository.

Current validation: 28 host tests pass; all 4,820 corpus files and both root
specimens parse and plan successfully; the external reference ELF passes
structural checks. The tests cover failed guards leaving memory untouched,
malformed/truncated files, address arithmetic, source/destination aliasing, JAL
delay-instruction preservation, J variants, PATCH metadata and scratchpad bounds.

The host tests are configured in GitHub Actions alongside the PS2SDK build and
gate release publication. Local PS2SDK compilation/linking/packing passed at
code commit `01eadfe0fe5d448514277cd857e7cabb28ae5766`, using the cached
`ghcr.io/ps2homebrew/ps2homebrew:main` image
`sha256:1037f40df12cf2d1875dcfdc368ed7f70feb0eff186498c4e10ff874ef531a1b`
and GCC 15.2.0. The packed artifact is 208,884 bytes with SHA256
`101d33a1dabaf485805d02c7ca212932c10c966902d17eb1f81f901a407d3aec`,
at `build/pops-ps2sdk/release/launcHER.elf` (ignored build output).

Docker was started locally; its engine restarted during the first attempt, and
the subsequent build completed. This is a target build result, not a POPS boot
or hardware pass. GitHub CLI's saved token is invalid, so no new exact-head CI
or PR publication has been obtained. No console result has been obtained.

## Storage bridge implementation checkpoint

The new `launcher/iop/popfs` module registers `pops:` and maps Sony's fixed
`/disc/disc0` through `/disc/disc3`, `/ps1emu/card0`, `/ps1emu/card1`, and
card `.bak` aliases to explicit backing paths. The required module arguments are
disc0, card0, card1; optional arguments provide disc1 through disc3. Device
prefixes are preserved, including massN, MMCE, network and pre-mounted PFS paths.
The module does not guess a massN slot's physical device or retry another path.

Disc opens are read-only. Save writes, short I/O, underlying errors, descriptor
zero, 64-bit seeks, backup renames and handle lifetime are covered by host tests
that compile the production driver. Save-volume sync attempts both volumes and
reports backend errors. Unknown paths and cross-slot renames fail. Exact
configured card/disc and backup collisions fail at module startup; physical
aliases or case folding in an underlying filesystem are not yet detected.

The storage bridge patch group contains eleven guarded writes: one branch skips
Sony's embedded DEV9/ATAD/HDD/PFS loads, two calls bypass Sony partition mounts,
and eight four-byte path prefixes select `pops:`. The partition-mount bypass
retains the preceding poweroff thread setup and both call delay slots. Backing
volumes must already be prepared by the bootstrap; this does not grant the proxy
permission to mount Sony partition names. All changes require the exact known
unmodified core and are compared across the entire staged RAM buffer for the
loose dependency set and both packed dependency sets.

Run `python tools/test_popfs.py` for the production IOP driver's host contracts.
The PS2SDK build compiles and embeds this IRX. The current packed build is
210,244 bytes, SHA256
`3abfba1867444e86c9409168e4634d8ecaa101fee855c25608b8a4581028355b`.
The build reported filesystem clock-skew warnings; compilation, linking and
packing completed successfully. The module is not yet loaded by a POPS runtime
caller. This artifact is not a working POPSTARTER replacement or a console pass.

The bootstrap and runtime caller are now implemented:

## Runtime caller and trampoline bootstrap implementation checkpoint

The implementation adds an isolated bootstrap and runtime caller:

- `common/include/pops_bootstrap.h` and `common/src/pops_bootstrap.c`: Defines the memory
  layout contract and formats proxy arguments (`"popfs\0<disc0>\0<card0>\0<card1>\0"`).
  It initializes `PopsTrampolineArgs` with the target entry, BSS extent, scratchpad
  size, staging buffers, and an preserved `"pops0:IMAGE.VCD"` argv string in bram at
  `0x00084230`.
- `launcher/src/pops_trampoline.S`: Position-independent MIPS assembly trampoline executed
  at `0x00084000` in BIOS unused RAM (`bram`), below 1 MiB. It sets its stack pointer at
  `0x0008fff0`, zeroes the scratchpad (`0x70000000`..`0x70003c30`), zeroes POPS BSS
  (`0x00502e60`..`0x00865940`), wipes launcHER low RAM (`0x00100000`..`0x00200000`),
  copies the verified staged core from `0x01000000` to `0x00200000`, flushes instruction
  and data caches via syscall `0x64`, and transfers control to POPS via syscall 7 (`ExecPS2`).
- `launcher/include/handler_pops.h` and `launcher/src/handler_pops.c`: Runtime caller.
  Detects VCD targets via `isPopsTarget`, locates external dependencies across candidate
  directories (VCD directory, `POPS/`, memory cards, APA partition), resolves and formats
  VMC save images (creating a 128 KiB formatted blank card when missing), stages core
  and IOP images in high RAM (`0x01000000`), stages core patches and external TROJAN payloads,
  reboots IOP with the verified external image via `SifIopRebootBuffer`, invokes
  `initPopsServices`, mounts PFS if APA, sets up trampoline arguments, and jumps to the
  trampoline.
- Integrated into `launcher/src/common.c` (`launchPath`) and `launcher/src/handler_quickboot.c`.
- `launcher/CMakeLists.txt` links `iopreboot` for `SifIopRebootBuffer`.

### Validation and target build

All 30 host tests in `tools/test_pops_external.py` pass, covering trampoline argument
layout and proxy argument packing contracts. Driver contract tests in `tools/test_popfs.py` pass.

The PS2SDK Docker build completed successfully:
- Target: `launcHER`
- Packed artifact: `build/pops-ps2sdk/release/launcHER.elf` (213,924 bytes)
- SHA-256: `1b8b262b0ec02d88f9a1985f2e1fb899b27aa498d856587fb9a0d3beaa93b914`

This is a target build result. Real hardware console validation remains necessary.

## Feature parity audit status

The component names and earlier host tests overstate runtime coverage. The
replacement is not yet a faithful drop-in POPSTARTER implementation.

| Capability | Confirmed implementation | Remaining requirement |
| --- | --- | --- |
| External POPS bootstrap | Verified dependency identities, guarded core patches, staging and trampoline | Same-console boot and backend coverage |
| VCD identification | ISO9660 and raw-sector inspection helpers | Establish actual POPStarter VCD container offsets and variants |
| Configuration | Text parsing, root/title discovery and table conversion | Reconstruct original precedence and all directive semantics |
| Saves | Raw-card creation and popfs read/write/backup helpers | Console save, reload and power-cycle validation |
| Cheats | Standalone evaluator and partial parser | Resident code, actual guest RAM mapping, periodic hook, master/slide codes and SAFEMODE activation; enabled cheats currently reject launch |
| Compatibility modes | Guarded original-dispatch writes for 1..5 and 7 | Reconstruct runtime state gating and mode 6 OSD conditions; establish mode 8 provenance; validate games |
| Video, BIOS and OSD | Parsed options and unverified patch helpers | Reconstruct original instructions, widths, runtime timing and behavior |
| LibCrypt | Key database and standalone SubQ generator | Connect actual POPS request path and validate protected games |
| Multi-disc | Proxy paths and popfs devctl helpers | Resident controls and switching already-open disc handles |
| IGR | Combo helper | Resident input hook, original menu/assets, reset and shutdown paths |
| External fixes | Guarded container inspector/stager; partial TROJAN discovery | PATCH discovery, original slot/order rules, error handling and runtime integration |
| SMB / optional modules | Module loading helpers | Return-value checks, login/share mounting and backend lifecycle |

Host tests establish the component contracts they exercise. They do not prove
that POPS calls these helpers, that resident code survives handoff, or that
save writes survive a console power cycle.

## Repair checkpoint - 2026-10-09

The audit of b403d198f9881ec412814e4bf790156d647623c5 found source-level
boot failures despite passing component tests. The first repair:

- Preserves full pristine-core SHA256 checks in boot planning and core patching.
  Post-reboot service initialization now checks the exact embedded Sony SIO2
  module independently, allowing the intended EE patches while rejecting a
  changed module before executing it.
- Moves loose IOP input to 0x01780000 and its staged destination to 0x01700000,
  each bounded to 512 KiB. Both sit outside the translated RAM/BSS staging
  range ending at 0x01665940, and below raw ELF input at 0x01800000.
- Checks the SIO2 identity before/after reference patches and rejects a modified
  IRX against loose ELF/IOPRP252 and both packed dependency sets.

## Save and configuration repair checkpoint - 2026-10-09

- Existing cards are opened read-only and must have the exact 128 KiB raw-card
  size. A short, oversized, unreadable or unseekable card aborts launch without
  modification. New files use exclusive creation and complete block-zero card
  metadata; write, close and directory failures propagate. Only an incomplete
  file created by the current call is removed on failure.
- Both save-card results are checked before IOP reboot. This repairs source-level
  data-loss risks; physical storage durability and the existing popfs write path
  still require hardware testing.
- Bare hexadecimal cheat lines remain disabled, following the original `$`
  enable marker. Unsupported enabled code types and overlong configuration
  lines report errors. Config discovery ignores absent files only.
- The unsafe one-time cheat write into the staged POPS executable is removed.
  Enabled parsed cheats reject launch until a resident runtime engine exists.
  This is an explicit safety restriction, not completed cheat support.
- VMCDIR changes save destinations only: title configuration and TROJAN lookup
  retain the original title folder. Absolute save-directory extensions receive
  a trailing separator before card filenames are joined.
- Added production-code VMC fault-injection coverage and enabled both save-card
  and feature host suites in CI. Local checks: seven feature tests, VMC contracts,
  popfs contracts, 31 external-image tests and launch-argument contracts pass.

Do not describe this development branch as a drop-in parity release. Remaining
work is tracked in the capability table above. Host tests and target compilation
do not establish a PS2 runtime pass.

## Compatibility dispatcher repair checkpoint - 2026-10-09

The previous Mode 1..8 helper did not match the measured original dispatcher
`FUN_008dc2c4`. It has been replaced for Modes 1..5 and 7 with the original
38 writes, preserving widths and ascending dispatch order. All selected sites
are checked against pristine instructions before any mutation. A bounds or
instruction mismatch rejects the entire operation. Errors now propagate through
`pops_apply_all_config_patches` to the caller.

Mode 6 requires the original OSD globals and conditional halfword update at
0x002525b0, not the previous LibCrypt NOP. Mode 8 has no branch in the inspected
dispatcher; its old NOP at 0x00207ee8 destroyed the verified exception-hook
redirect. Both currently return ENOTSUP without changing the core.

`tools/test_pops_modes.py` compares whole buffers for all 64 supported masks,
checks all 192 masks containing unsupported modes, and verifies atomic guard and
bounds failures. The optional external comparison passed against both the
measured original dispatcher and external POPS ELF:

```text
python tools/test_pops_modes.py --elf C:/Users/natha/Github/POPS/POPS.ELF --decompile C:/Users/natha/Github/POPS/build/parity/popstarter/decompiled.c
```

This establishes patch-write parity for the original DAT_009b9d48 == 0 path.
It does not establish the mapping/lifecycle of that original state global,
original caller ordering across config sources, or in-game compatibility.
Video, LibCrypt and BIOS helper patches remain separately unverified.

## Runtime boundary hardening checkpoint - 2026-10-11

- Fixed a production caller/stager contract mismatch: ordinary TROJAN hooks
  require **two** verified hook words while 12-byte hooks require three. The
  caller previously passed three unconditionally, ignored staging errors, and
  logged attempted patches as successful. The launcher now plans each payload,
  matches the numbered file to the embedded slot, supplies the correct number
  of words, checks read/stage results and reports failures rather than proceeding
  as if the patch had been installed.
- Proxy argument packing now rejects invalid or skipped optional disc paths
  rather than silently dropping a disc and changing slot mapping.
- Staging bounds checking now uses subtraction without 32-bit size truncation;
  host tests cover 4 GiB wraparound attempts. popfs disc-control and SubQ
  devctls reject non-null input buffers shorter than the required structure.
- These are host-verifiable consistency and memory-safety corrections only.
  Existing slot precedence, independently sourced hook guards, PATCH dispatch,
  runtime file services, game boot and console save persistence still require
  separate validation. Neither a passing host suite nor PS2SDK compilation
  qualifies this as a POPStarter-compatible release.

## VCD container inspection checkpoint - 2026-10-11

- Fixed title serial detection on standard POPStarter/CUE2POPS VCDs. The older
  metadata reader incorrectly inspected sector zero at file byte zero, as if
  .VCD were a bare .BIN or ISO. CUE2POPS and legacy Sony variants place a
  1 MiB TOC header before 2352-byte disc sectors (the familiar signatures
  `kHn` and `SPOP` occur at file offset 0x400). PVD, root-directory and
  SYSTEM.CNF reads now apply the container's 0x100000-byte payload offset.
  The format is validated by synthetic headered images and headerless raw
  fixtures. No proprietary disc content was committed.
- Hardened bounded ISO9660 directory record parsing; rejects records too short
  for fixed fields or containing names beyond their own record boundary.
  Root-directory sector count and LBA arithmetic no longer overflow uint32.
- This repairs metadata and serial-based compatibility lookup only. It does
  not verify the POPS runtime's VCD sector-translation interface, mixed-mode
  audio, CDDA seeking or any hardware game boot. Such parity claims still
  require original-code tracing and on-console acceptance results.

## Disc-handle integrity and SYSTEM.CNF accuracy — 2026-10-11

- POPFS now tracks open/pending disc descriptors separately from save-card handles.
  SWAP_DISC and NEXT_DISC refuse to switch while a disc file is open. A
  successful disc change therefore cannot silently redirect the `disc0` alias
  while the underlying live file descriptor still reads from the old image.
  Card handles remain usable across disc changes. This is **not** resident
  in-game disc-swap parity; it is a consistent failure boundary until POPS
  close/reopen and the actual tray-event contract are implemented.
- PS1 serial discovery now requires a valid ISO9660 root-directory record and
  recognizes only non-comment `BOOT =` assignments. It skips `BOOT2` and
  commented lines; short SYSTEM.CNF reads cannot yield partial identifiers.
  Synthetic fixtures cover mixed-case BOOT assignments and decoy lines.
- These checks cover metadata and proxy contracts, not Sony runtime disc I/O.

## Optional-core-patch failure atomicity — 2026-10-11

- Validates the full memory window needed for requested optional video and
  visual patches before mutating any compatibility-mode instructions. PAL/NTSC
  conversion touches a late POPS-core word at 0x00502770, which the original
  helper could silently fail to write while returning success after changing
  earlier bytes. Undersized core buffers now reject without partial writes.
- The configuration dispatcher propagates helper failures rather than always
  returning success, and rejects unsupported video-mode values.
- This is **bounds/error-handling correctness**, not proof that the listed
  speculative graphics/BIOS/LibCrypt patch values match original POPStarter.
  Source-measured guards and actual console testing remain required.

### Disc-switch/open concurrency refinement

- POPFS now resolves the selected disc alias and reserves its live descriptor
  under the same short IOP interrupt critical section. Without that pairing,
  a concurrent disc swap could occur between alias resolution and descriptor
  reservation, leaving the old disc opened under the new active disc number.
  Underlying iomanX_open is performed after interrupts are restored. Resident
  POPS caller/IOPCD disc switching still needs hardware proof.

## Reversible preflight before IOP reset — 2026-10-11

- Packed POPFS arguments are validated **before** loading external dependencies
  or modifying Sony POPS buffers, creating VMC files, or resetting the IOP.
  Invalid paths and oversized argument lists now fail while the calling
  launcher and its existing IOP environment are still available.
- New VMC images are created only once dependency identity, core patching and
  selected TROJAN staging have succeeded. Failure earlier in the launch no
  longer leaves behind newly created blank saves. Existing VMC preservation
  and failure propagation still follow the existing VMC implementation.
- Reject all ASCII-case spellings of recursive `pops:` / `popsN:`
  backing paths in both the EE formatter and IOP POPFS driver.
- POPFS argument formatting now computes and validates the **complete** byte
  count before writing to the destination buffer. Added host tests for
  over-capacity failure without partial argument writes and production
  source-order regression coverage for validation/VMC/IOP-reset sequencing.
- This does not address failures occurring after the IOP reboot, nor prove
  the POPS executable/IOP file-service ABI on an actual PlayStation 2.

### Save/disc path alias preflight

- The EE POPFS argument formatter now mirrors the IOP POPFS driver's exact
  same-path and `.bak` alias checks between both save cards and all disc
  backing paths. Previously those would be rejected only when registering
  the POPFS IOP driver **after** an irreversible IOP reboot and potentially
  after VMC creation. They now fail in the reversible preflight.
- Added tests verifying each rejected alias does not mutate the output buffer.
  Deliberately does not invent case-insensitive/normalized path equivalence:
  storage-specific aliases still require a measured filesystem policy.

## REPOP cross-reference and post-reboot RPC contract — 2026-10-11

Cross-checked private `NathanNeurotic/REPOP` (`main`) as a supporting
reconstruction corpus, notably `docs/IRX_MODULES.md`,
`docs/POPSTARTER_ARCHITECTURE.md`, `popstarter/src/pfs_wrap.c` and
`popstarter/src/vcd_bat.c`. The latter reconstructed host implementation
uses an unverified `POPS_VCD` header/BAT layout and the PFS wrapper prototype
uses standard host `stdio`. **Neither is proof of the actual CUE2POPS VCD
wire format or PS2 resident IOP filesystem ABI**. REPOP is useful for module
roles and a source-forensics worklist but cannot replace binary/hardware
validation. No reconstructed/proprietary binaries were copied.

The original POPStarter PFS bridge is named `pfs`; launcHER's custom POPFS
device is `pops`. Proving how the original Sony IOPCD/POPS runtime resolves
its filename/service remains a **blocking parity issue**. No speculative
aliasing of `pfs` or copying reconstructed VCD-BAT math was introduced.

Direct PS2SDK code inspection also established:
- `SifIopRebootBuffer` returns **positive 1 on success**, and returns **-1**
  on a failed ROMDRV/IOP reboot payload installation. A negative result is
  not success. The launcher used to treat -1 as success because it only retried
  encrypted boot when the result was exactly zero. Both nonpositive outcomes
  now require the encrypted fallback; if that also fails, the launch returns
  an error instead of waiting for a nonexistent sync completion.
- PS2SDK's reboot routine calls `SifLoadFileExit` and increments the reboot
  counter; its `_SifLoadModuleBuffer` helper already calls
  `SifLoadFileInit` and recognizes the reboot counter. No redundant
  speculative loader RPC reset was added.
- The post-reboot `fileXioInit()` RPC bind result is now checked, and failure
  terminates service initialization. IOP module argument allocations are
  nulled after being freed to avoid retaining dangling pointers on later calls.

Source-order host checks guard these error-handling contracts. Build and host
tests still cannot demonstrate correct IOPCD/PFS service wiring on real PS2.

### Protected-game failure accounting

A missing/broken POPFS LibCrypt devctl handler previously yielded a misleading
success log and continued into the POPS trampoline with the requested key
uninstalled. The launcher now checks the IOP `fileXioDevctl` result and
rejects the launch if a database-identified protected game cannot configure
its requested key. This validates the **error boundary only**; the actual
Sony IOPCD subchannel signaling contract is not yet proven.

## POPFS trampoline filename consistency — 2026-10-11

The POPS trampoline passed `pops0:IMAGE.VCD` to the external core, but the
POPS file bridge previously recognized only `/disc/disc0` through
`/disc/disc3` (and virtual cards). The exact launch argument therefore
could not be opened through the installed bridge, even if all drivers and
backing files were otherwise healthy.

The bridge now maps read-only `IMAGE.VCD` to the same configured active-disc
path as `disc/disc0`, including after a successful disc switch. The standard
legacy HDD name `IMAGE0.VCD` is supported as another exact alias. Host tests
verify open, getstat, read-only rejection and switch behavior. These aliases
are *not* a `pfs0:` device, and do not prove that the actual Sony POPS/IOPCD
runtime uses this custom namespace or its underlying VCD sector semantics.

## Evidence-directed VCD and runtime-storage checkpoint — 2026-10-11

The original VCD author describes the 1 MiB TOC header, optional version
marker at byte 0x400, duplicated size fields at 0x408 and 0x40C, and
contiguous 2352-byte payload from byte 0x100000:
https://www.psx-place.com/threads/vcd-extra-header.25054/
This is higher-confidence evidence than REPOP's experimental `POPS_VCD`
BAT header reconstruction. The independent metadata inspector accepts
headered VCDs without a recognized marker by finding ISO9660 PVD at the
documented payload offset. It also handles positive short reads from a
streaming backend. Host tests cover both cases.

Archived POPStarter VMC instructions confirm the external filenames
`SLOT0.VMC` and `SLOT1.VMC`, with `VMCDIR.TXT` choosing the containing
directory:
https://nathanneurotic.github.io/POPSLoader/multidisc.html
POPFS now maps these exact standard card aliases, including `.bak`
variants, to the configured card0/card1 backends without touching the
original `ps1emu/cardN` aliases. The launch-time live-storage probe now
opens the documented aliases for read/write, while opening and reading
`pops0:IMAGE.VCD` read-only. This detects broken file forwarding and
unavailable write access after the external IOP reset but before the POPS
trampoline; it does not test actual card writes.

When `DISCS.TXT` names optional discs, the launch now rejects truncated
paths and verifies that *every listed disc* can be opened before the IOP
reboot. Missing secondary discs no longer cause a late file open error only
after transfer to Sony POPS.

**Blocking Sony interface issue:** The actual PS2 POPStarter wrapper
registers a `pfs:` service; the present driver registers `pops:` only.
A device alias must never hijack or unregister the genuine Sony/APA `pfs`
driver, especially on HDD. Do not claim replacement parity until the
original IOPCD import/file-service contract, mount behavior and safe
non-APA namespace registration are verified with on-console traces. A
working POPFS bridge probe does not establish that Sony IOPCD uses it.

## External IOP handoff hardening — 2026-10-11

### APA remount and recoverability

The normal `mountPFS` helper mounts `pfs0:` read-only. After the external
IOPRP reboot, the old mount cannot be assumed to survive, and live VMC
verification must not run before mounting the backing partition. The POPS
path now uses a separate `mountPFSWritable` helper (FIO_MT_RDWR), checks
both early `initPFS` and post-reboot mount errors, and remounts **before**
opening the POPFS disc and card aliases. The standard ELF launcher still
uses the original read-only mount. Hardware must confirm game-partition
layout, partition sharing, save writes and power-cycle persistence.

The external IOP reboot also invalidates launcHER's device cache. The POPS
service initialization marks `forceIOPReset` immediately, so a failed POPS
launch cannot silently let the following normal launch reuse an IOP setup
left behind by the Sony image.

### Actual SMB module results and dependency compatibility

The SMB helper previously treated finding an IRX on storage as a successful
load, even when `SifLoadModule` returned a negative error. It now marks a
module loaded only after a successful load and tries subsequent candidate
locations if one fails. For POPS, the stack is loaded and checked after the
reboot once, instead of making a second redundant call from generic module
setup. The generic launcher device initialization behavior is preserved.

The original r13 network release specifically requires `POPS_IOX.PAK`,
rather than `POPS.PAK` or the loose `POPS.ELF` + IOPRP252 pair. This
is documented by krHACKen in the 2015 beta and follow-up:
https://www.psx-place.com/threads/ps1-popstarter-r13-wip-06-beta-20160918.10793/
https://www.metagames-eu.com/forums/playstation-2/popstarter-revision-13-a-52-134569.html
For an SB. / SMB launch, dependency discovery now scans **all** candidate
locations for IOX and never silently falls back to an incompatible image.
For USB/APA and other launch modes the previous discovery options remain.

### Why the historical PFS_WRAP binary is not yet a drop-in driver

Original release notes confirm the r13 beta 8 PFS wrapper was **rewritten
and embedded** within POPStarter, no longer loaded from PFS_WRAP.BIN. The
standalone REPOP `PFS_WRAP.BIN` is therefore not the latest r13 ABI:
https://www.psx-place.com/threads/ps1-popstarter-r13-wip-06-beta-20160918.10793/

The reference PS2SDK IOMANX `iomanX_AddDrv` implementation can register
drivers without a duplicate-name check in its non-linked-list configuration.
Consequently, simply adding a second device named `pfs` is unsafe: it could
shadow real APA/PFS and corrupt or misroute HDD accesses. We discarded an
unused experimental EE proxy-mode argument change pending reliable driver
enumeration and original IOPCD path/operation traces. The working `pops`
namespace is intentionally not presented as complete Sony `pfs` parity.

### Independent resolver state and partial IOP reads

Consecutive `SB.` / `XX.` / unprefixed launch resolutions previously left
earlier `s_active_sb_launch` and `s_active_xx_launch` globals enabled. That
could incorrectly route a later USB game through SMB, require the IOX package,
or load network drivers unexpectedly after a prior failed launch. The
resolver now atomically defines the new prefix intent by clearing the
unselected mode; explicit `SB.` or `XX.` targets also override the other
mode without discarding an intentionally inherited launcher-prefix context.
The host launcher-argument tests exercise multiple resolutions in one
process, not just isolated games.

The post-reboot POPFS disc probe previously classified a short positive
`fileXioRead` result as failure, unlike the VCD metadata inspector. It
now loops over the remaining byte count with a bounded read and keeps the
read destination aligned for IOP RPC. It still fails on EOF, negative I/O
status or impossible length. No game data is written by the probe.

### First-launch APA VMC creation gate — 2026-10-11

A new PS1 game may have no existing `SLOT0.VMC`/`SLOT1.VMC`.
The first APA mount was deliberately read-only for VCD/dependency probing;
however `pops_vmc_ensure` runs **before** the external IOP reboot and
creates missing save files. A writable remount only *after* reboot could
never fix that first-launch failure.

After all external dependency and core/TROJAN preflights pass, POPS now
explicitly unmounts its old inspection partition and remounts it read-write
before creating either save. A busy/failed unmount or mount is surfaced as
an error. The existing post-reboot writable remount remains necessary
because reboot discards the earlier mount. Normal APA ELF launch semantics
remain read-only. Hardware testing must verify actual PFS write access.

### Standard Q subchannel timing and CRC — 2026-10-11

The previous synthetic Q builder duplicated track-relative MSF into the
absolute time fields and produced zero CRC bytes for unprotected sectors.
This is inconsistent with the Red Book/PlayStation position-Q structure.
Both the EE host helper and the IOP POPFS devctl now encode absolute
MSF as LBA+150 frames and track-relative time as LBA, with the standard
inverted CRC-16/CCITT across Q0..Q9. The published Q at relative sector 0
(`41 01 01 00 00 00 00 00 02 00 28 32`) is tested byte-for-byte.
Reference: https://psx-spx.consoledev.net/cdromformat/

The existing nonzero LibCrypt-key placeholder for selected low sectors is
unchanged. It is *not* true LibCrypt support: real protections modify
subchannel position and CRCs in game-specific sector patterns near minutes
3 and 9. Likewise, a single-track synthetic Q is insufficient for actual
multi-track CDDA. Hardware/I/O traces and authentic subchannel data remain
required before declaring those features compatible.

## PFS reference evidence and save/disc safeguards — 2026-10-11

### What REPOP's original wrapper actually establishes

I inspected the 8,237-byte `popstarter/PFS_WRAP.BIN` from the private
`NathanNeurotic/REPOP` reference tree (Git blob SHA:
`48dc44e02fddd90bac8b88fcc9a8dd33273cc2df`).
Its IOP ELF exposes the *legacy* `ioman` import name at file offset
0x4dc, `mass:/POPS/%s` at 0x650, and `PFS Wrapper` at 0x660.
That directly grounds the concern that our `popfs` module presently
registers `pops` via `iomanX`, which may not satisfy Sony's legacy
`pfs0:`/IOPCD calls even when `pops0:IMAGE.VCD` opens successfully.

These strings alone do **not** prove the complete call ABI, nor that a
later r13 embedded wrapper uses the same imports. No legacy driver was
hijacked or re-registered and no binary from REPOP was committed.
Before a safe alias or hook can ship, capture the original IOPCD
open/mount/read/read-ahead behavior and prove the IOMAN versus IOMANX
export relationship for the selected Sony IOPRP.

### Never truncate a VMC path into another game's save

Game-config/VMC candidate paths previously used unchecked `snprintf`
and explicit `%.700s`/`%.800s` cuts. Long game directories could thus
silently redirect a save to a different, truncated path. The launcher
now checks the game-config path length and conservatively budgets for
the directory, optional subfolder, serial/game basename, separators
and extension **before** any VMC path is selected or new file created.
The fixed-length cuts have been replaced by full-path composition.
An excessive path fails with `-ENAMETOOLONG`. A host source-level
regression check verifies the guards precede card resolution.

### Report an unavailable alternate disc

POPFS `NEXT_DISC` previously returned zero for a single-disc game,
despite leaving the same disc active. It now returns `-ENOENT` if no
different configured disc exists. The production IOP driver fixture
verifies both that error and unchanged selection; real alternate-disc
swapping and open-handle protection retain their existing behavior.

### ROMDIR evidence collection without a PFS override

Audit correction: the reference EE core's `POPS_CORE_STORAGE_BRIDGE`
patch already rewrites eight exact, SHA256-guarded literal `pfs0` and
`pfs1` references into `pops`. The full staged image is compared byte
for byte in host preflight tests. This satisfies the **known EE-side**
filename aliases; it does not prove that independently loaded Sony IOPCD
uses the same names or file manager imports.

An exact-name ROMDIR module locator is now available on the externally
identified Sony IOPRP image. It reuses the existing bounds-checked ROMDIR
validator and returns the module's original offset and size without
touching its bytes or accepting substrings. A diagnostic before IOP reset
reports whether `IOPCD` is a standalone module in the selected image.
Synthetic ROMDIR fixtures cover padded RESET extents, exact module slices,
unavailable modules, bad names, truncated images and output preservation
on error. This prepares evidence collection for the remaining IOP-side
PFS/IOPCD contract without changing the genuine APA driver.

### Plain USB must retain its built-in IOP drivers — 2026-10-11

The prior post-reboot module loop suppressed both `usbd_mini` and
`usbmass_bd_mini` whenever it found any external USB IRX filename under
a memory-card POPStarter directory. Presence alone does not load that
driver, and the external BDMA stage is not entered for a normal unprefixed
USB game. As a result, the default POPFS I/O probe could fail simply
because an unused driver file existed in the user's installation.

The skip now applies only when `Device_USB` and the explicit `XX.`/BDMA
override are selected, preserving the historical experimental external
path for opt-in users. Ordinary USB launches always install their bundled
IOP USB stack regardless of files on memory card. The regression test
checks that both required conditions guard the skip. A future verified
external IRX loader should require actual module-load success instead
of filesystem presence before replacing built-in modules.

### Read-only IOPCD file-manager evidence — 2026-10-11

The ROMDIR module locator can now perform a bounded *string-hint* scan
inside an explicitly named module payload. For a standalone `IOPCD`
in a verified IOPRP, the launcher reports whether exact null-delimited
`ioman` / `iomanX` import-name strings or path prefixes `pfs:` /
`pops:` are present. No Sony binary is saved, extracted, patched, or
committed. Negative results mean only that the literal strings were not
present; positives are **not proof** that the IOP imported or executed
those functions. The scan never crosses the validated ROMDIR file extent.
Host fixtures cover exact matches, boundaries, absent modules, truncated
images, and unchanged outputs on failure.

This prepares accurate console diagnostics for the remaining Sony
IOPCD/legacy IOMAN question. Neither an unsafe duplicate `pfs` driver
nor a speculative import override was installed.

### Structured IOP import-table evidence — 2026-10-11

PS2SDK's `iop/kernel/include/irx.h` defines a packed IRX import table:
32-bit magic `0x41e00000`, a linked-list pointer, version/mode words
and an eight-byte library name. The archived REPOP `PFS_WRAP.BIN` places
`ioman` in this exact pattern (the preceding magic is at `0x4d0`).
These bytes are stronger evidence of a legacy import than a free-standing
ASCII `ioman` string.

A second read-only ROMDIR module probe now scans complete, aligned import
table headers, reporting the exact `ioman` and `iomanX` library imports
inside `IOPCD` when it is present in the user's verified IOPRP. Its
output is a bitmask, left untouched on errors. Host fixtures cover import
headers, names without valid headers, absent modules and truncated images.
The diagnostic logs both source-string hints and structured import-table
flags, explicitly distinguishing evidence from executed calls.

No Sony dependencies or PFS wrapper binaries are added to Git, and
nothing changes the registered IOMAN/IOMANX device set. The next
implementation must still prove how the selected Sony IOPCD is loaded
and whether its legacy `pfs0:` file operations are passed through the
IOP file-manager compatibility shim.

### Negative IOP module entry results — 2026-10-11

When loading the necessary IOP modules after Sony's external reboot,
`SifExecModuleBuffer` may report a successful EE RPC and module ID even
though the invoked IOP module `_start` returned a negative error in
`iopret`. The common module loop previously rejected only `iopret==1`,
discarding other negative module-start failures. The POPS-specific loading
path now propagates negative `iopret` values, failing before the POPS
handoff when a needed IOP driver could not initialize. The generic ELF
loader's historical result handling is unchanged.

### PS2SDK legacy IOMAN hook evidence

The default `ps2dev/ps2sdk` `iomanX` Makefile sets
`IOMANX_ENABLE_LEGACY_IOMAN_HOOK`; `ioman_sbv.c` also enables
`FULL_IOMAN`, forwarding legacy IOMAN exports to iomanX and migrating
the existing driver/file tables. Thus a legacy `ioman` import in Sony
IOPCD does **not** necessarily imply an incompatible file-manager ABI.
It is still essential to verify the actual `iomanX.irx` built into
the launcHER artifact, the Sony module's resolved imports, and *which
filesystem device name* it opens; the hook does not automatically turn
`pfs0:` into `pops0:`.

Sources:
https://github.com/ps2dev/ps2sdk/blob/master/iop/system/iomanx/Makefile
https://github.com/ps2dev/ps2sdk/blob/master/iop/system/iomanx/src/ioman_sbv.c
https://github.com/ps2dev/ps2sdk/blob/master/iop/kernel/include/irx.h

The existing source-level safety rule remains: no duplicate `pfs`
registration without a verified collision check, and no hijacking
genuine APA/PFS.
