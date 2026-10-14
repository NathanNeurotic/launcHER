# Original POPStarter / Sony IOPCD evidence

## Verified intake, October 13, 2026

PR #23 continues on `codex/popstarter-replacement`. This evidence is from
external local inputs; none of their binary bytes belongs in this repository.

The archived POPSLoader MAIN profile has Git blob identity
`83dac95cf84d54364b097e17dc322f38741afa02`, size 167,700 bytes, and SHA256
`734c813e8e8ec2c6729ec5e15dd46ab696e90deeade8d0b2ca3ad03782781aa1`.
REPOP's bounded unpacker at `d900e9bed0f4eb2f1bba2cb55361010d1af572e0`
reached its expected exit at `0x00870000`. Its 1,350,828-byte output has SHA256
`185177c28aaef30ad1e00697ad7b6de22b55bd855253ab4ede8b1ab2dfb08aee`.
An independent Python liblzma raw decode produced **the identical whole buffer**:
the size word is at packed file offset `0x5f0`; reverse the following four-byte
initial range word, prepend the LZMA zero byte, and use lc=3/lp=0/pb=2.
The output is bounded by the declared length, and its complete digest is checked.

The bounded embedded-IRX inventory found eleven modules. The first, at unpacked
offset `0xaf680` (EE address `0x0091f680`), is the actual embedded wrapper:

| Property | Observed value |
| --- | --- |
| Size | 2,484 bytes |
| SHA256 | `c08a41c98301009bfd0d277dd974e244536fe0ec37df880501a919829ac21c0c` |
| ELF architecture | ELF32 little-endian MIPS, type `0xff80` |
| Description | `PFS Wrapper r6a` |
| Registered device | `pfs`, legacy IOMAN filesystem type `0x10` |
| Operations table | 17 legacy callbacks; no extended mount/umount slots |
| Backing prefix | `mass:/POPS/`, patched by the original EE loader |
| Core callbacks | open `0xd4`, close `0x154`, read `0x178`, write `0x19c`, lseek `0x1c0` |

Callback addresses are **module-relative IOP text addresses**, not EE addresses.
The read/write/lseek callbacks load the backing descriptor from the legacy file
object at offset 12 and directly call the corresponding legacy IOMAN import.
The seek callback does not add a VCD header or scale a sector number. The
bounded original-code execution below also confirms this forwarding behavior.
The original open callback prepends the backing prefix and copies the requested
path after dropping its first byte. It is not a safe implementation template for
arbitrary untrusted paths or failed opens.

## Correct Sony module location

The selected loose IOPRP252 image does **not** contain a ROMDIR `IOPCD` entry.
The selected Sony POPS ELF embeds it instead, at file offset `0xfb820`:

| Property | Observed value |
| --- | --- |
| Size | 15,951 bytes |
| SHA256 | `ccdd60e1408b7dbc4a65e9fdad53b671e7acdb69fc5acc72704a952feacd58ae` |
| Module name | `IOPCD`, recorded in `.iopmod` |
| IOMAN imports | version `0x0104`, ordinals 4=open, 5=close, 6=read, 8=lseek |
| Original symbols | `rdsector` at `0x554`, `ServerFunc` at `0x804` |
| Direct callsites | open, close, read and lseek within those functions |

The embedded IOPCD has a bounded ELF symbol table and relocation records. It is
the next execution target. An absent `IOPCD` ROMDIR entry must not be treated as
absence of Sony's file-backed disc service. The currently selected embedded
module does not declare mount/umount imports. That narrows this module's scope;
it does not prove that no other Sony or EE code performs mounts.

REPOP's current `recover_pops_io_contract.py` rejects the loose IOPRP because
it requires the last module's optional alignment padding. The image's final
STDIO raw extent is complete. launcHER's existing production ROMDIR validator
already permits omitted final padding. No firmware change or image rewrite is
needed to investigate the actual embedded IOPCD.

## Reproduction and remaining gate

`tools/trace_original_pops_io.py` now reproduces **26 passing execution cases**
with the pinned external MAIN ELF and Sony POPS ELF. It independently decodes
MAIN using liblzma and executes the original embedded wrapper and Sony IOPCD
in separate MIPS32 Unicorn machines. Their allocated sections and GP retain
their zero-based link addresses; imported kernel services are modeled. A
logical IOMAN descriptor is deliberately different from the backing descriptor.
No original instructions are embedded in the script, rewritten or exported.

Observed file-mode behavior under the supplied synthetic requests:

- `ServerFunc(0x435053, filename, length)` opens the supplied `pfs0:/IMAGE.VCD`
  read-only, then reads 1,024 TOC bytes at file offset zero. The original wrapper
  resolves that path to `mass:/POPS/IMAGE.VCD` in its default configuration.
- `rdsector(fd, request, buffer)` uses the **byte offset already supplied at
  request +12**. It records the low nine bits at request +16, seeks to the
  remaining 512-byte-aligned offset, and requests
  `(count * 2352 + skip + 512) & ~511` backing bytes. Even an exactly aligned
  byte count includes an extra 512 bytes in this original expression.
- The wrapper forwards seek/read arguments without adding 1 MiB or multiplying
  an LBA. The synthetic bytes received by IOPCD match the backing-file positions.
- The tested negative open/seek/read results propagate. A negative seek makes
  no read. Descriptor zero survives. A short TOC read closes the descriptor.
- The original close command clears its logical descriptor even when the
  modeled backend close fails. This observation is not a durability guarantee.

The selected IOPCD's exact IOMAN imports are open/close/read/lseek. Its callbacks
and the original wrapper route exercised here do not call mount/umount. This
does not answer whether other EE or IOP code mounts real HDD/PFS volumes.

The production launch path now independently hashes this complete embedded
IOPCD at **loaded-core offset `0xfa820`**, size `0x3e4f`, before reporting its
declared I/O masks (`ioman=0x170`, `iomanX=0`). This is distinct from ELF file
offset `0xfb820`: the loadable segment's file offset is `0x1000`. The old ROMDIR
diagnostics remain separate. Rejected identity leaves masks untouched and
aborts before configuration/core/TROJAN patches, save creation or IOP reset.

Host checks exercise unknown/truncated cores and both ends of the exact IRX;
external checks pass against loose ELF/IOPRP252, POPS.PAK and POPS_IOX.PAK, with
intended EE patches outside the IRX still accepted. The production POPFS fixture
also replays the recorded original seek/read argument pairs without translation.
This adds evidence-backed diagnostics and regression coverage, not new mount
or sector-remapping semantics.

```text
python -m pip install unicorn
python tools/trace_original_pops_io.py --popstarter POPSLoader/bin/POPSLDR/PROFILES/MAIN/POPSTARTER.ELF --pops-elf EXTERNAL/POPS.ELF --json build/original-io-trace.json
```

The measured metadata-only result is committed in
`docs/evidence/original_pops_io_trace.json`. Neither Sony nor POPStarter bytes
are included. The script rejects any changed input hash before execution and
bounds each callback by both an instruction count and an emulation timeout.
An unknown import or callback that fails to return aborts the probe.

**Limits:** the EE producer of `request +12` is executed separately below;
five of its observed tuples are replayed through the original IOP code. Other
example offsets are controlled stimuli, not observed console traffic. IOP services,
filesystem descriptor routing, semaphore success, delay and printf are modeled.
This establishes original callback behavior under those inputs, not Sony's
complete runtime, CDDA, media retries, actual kernel import binding or saves.
The next boundary is actual kernel binding, whole-launch integration and
same-console device/save tests.

## Native R5900 request producer

The selected Sony function `FUN_00210090`, original address
`0x00210090..0x0021021b`, constructs the packet sent to IOPCD. A separate
396-byte original-function probe preserves every instruction, including
R5900 three-operand MULT, 64-bit register saves and branch-likely delay slots.
Its complete function SHA256 is
`4a38bbb0dc66fa28825f9765d03d62b6318dd657032ddf7d8489611c22a1f0d0`.
It is **not** translated to a MIPS32 or x64 surrogate.

Both GCC and LLVM probe harnesses built with local ps2build v2026.10.13 and
passed seven cases in PCSX2 2.9.52.0. The same original function bytes execute
at their original address with original GP `0x0050a670`. Track lookup,
semaphore services, SIF RPC delivery and error logging are explicit doubles.
Every linked probe PT_LOAD extent, including BSS, is checked for overlap with
the injected function, service entry redirects and fixed globals before a run.
PCSX2 uses a fresh isolated profile with both memory cards disabled.

The same seven cases subsequently **passed on the physical PS2** through
ps2rig run `20261013T181122-0001`, with explicit `[ps2rig] exit=0`. The
console ELF SHA256 is
`651a5fcd61136aa6e701fb81692921bfeb3ec625a64de3c193149f529652fe4c`.
Its stdout and outcome are preserved in
`docs/evidence/original_pops_ee_console_probe.json`. This advances the bounded
request-producer result to hardware execution; imported services remain doubles.
It does not establish complete POPS boot, custom IOP reboot or save persistence.

| LBA | Selected final sector | Observed count | Observed byte offset |
| --- | --- | --- | --- |
| 0 | 1000 | 16 | 1048576 |
| 16 | 1000 | 16 | 1086208 |
| 1234 | 5000 | 16 | 3950944 |
| 4999 | 5000 | 2 | 12806224 |
| 5000 | 5000 | 1 | 12808576 |

These are original EE-produced `0x435056` requests. They establish the
`0x100000 + LBA * 2352` byte offset before IOPCD's alignment, a 16-sector cap,
and reduced counts at disc end under the supplied state. A cached read uses
the existing buffer plus the sector delta without another RPC. A mismatched
reply count returns NULL and clears the cached range. Both compiler harnesses
observed the same fields. The five tuples above also pass through the original
IOPCD/wrapper execution probe, preserving aligned file offsets and data bytes.

Reproduction from this repository root (use a fresh local output directory):

```text
python tools/prepare_pops_io_request_probe.py --elf EXTERNAL/POPS.ELF --out build/io-request
ps2build build -c build/io-request/ps2.yaml -o build/io-request/gcc --toolchain gcc
ps2build build -c build/io-request/ps2.yaml -o build/io-request/llvm --toolchain llvm
```

Then run `tools/run_pops_io_request_probe.ps1` with `-Elf` pointing to the
selected compiler's `bin/pops_io_request_probe.elf`, the existing local
`-Pcsx2`, `-BiosDirectory` and `-BiosFilename`, and a fresh `-OutputDirectory`.
The runner verifies injection layout automatically and bounds execution to
45 seconds. It records only ELF/BIOS hashes, emulator version and stdout
observations in `result.json`. `docs/evidence/original_pops_ee_io_probe.json`
contains the measured GCC/LLVM metadata. **Generated C arrays and ELFs contain
original code and must remain local under ignored build/, never uploaded.**

The source-only guard suite `python tools/test_pops_io_probe.py` runs in CI
without original inputs, checking identity rejection and every injection region
against file-backed and BSS overlaps. Actual original-code runs need the user's
external files and remain a separate validation level.

**Limits of this EE-only probe:** no actual SIF transport, Sony IOP kernel,
audio-track lookup or physical device is exercised. Compiler agreement is harness evidence,
not reconstructed-POPS parity or a hardware boot/save result. The measured
offset ownership argues against adding another 1 MiB/2352-byte remap in POPFS.

Use REPOP at the revision above in a separate reference checkout, preserving any
ongoing REPOP development. With external binaries already available locally:

```text
python REPOP/tools/analyze_popstarter_checkout.py POPSLoader --json build/profiles.json
python REPOP/tools/unpack_popstarter.py POPSLoader/bin/POPSLDR/PROFILES/MAIN/POPSTARTER.ELF build/main-unpacked.bin
python REPOP/tools/inspect_popstarter_embedded_irx.py build/main-unpacked.bin --json build/main-iop.json
python REPOP/tools/inspect_popstarter_embedded_irx.py EXTERNAL/POPS.ELF --json build/sony-iop.json
```

The REPOP inventory commands provide archive/decode/static-module results;
the separate bounded probe adds original callback execution. They do not establish
canonical unmodified r13 release provenance, Sony IOPCD execution on a console,
backend streaming, saves across power cycles, or full POPStarter parity. Keep
the PR draft. Preserve transparent POPFS byte offsets; do not insert another
VCD header/sector translation based on a synthetic request's LBA field.

## Actual Sony IOP image, production bridge and SIF RPC

`tools/prepare_pops_iop_binding_probe.py` prepares a separate local-only probe.
It pins the complete external POPS.ELF and IOPRP252.IMG identities, extracts
the unchanged embedded IOPCD, and copies the production iomanX/fileXio/POPFS
IRXs from a launcher build's bin2c sources. The IOP kernel and RPC services
execute in PCSX2; only the backing storage is a controlled in-memory IOP
filesystem. The probe uses the production proxy argument formatter.

Both GCC and LLVM harnesses passed with PCSX2 2.9.52.0. The observed sequence
is: reboot into the selected Sony image, load the three production services,
open both `pops0:IMAGE.VCD` and `pfs0:/IMAGE.VCD`, load original IOPCD, bind its
`0x435052` server, read the 1,024-byte TOC, and verify all five EE-produced
sector-request tuples above byte for byte. No additional offset translation
or original-kernel/IOPCD patch was needed. Both save aliases also passed
1,024-byte write/close/reopen/readback at offset 4,096. Direct backend controls
and proxy writes use different patterns so earlier control writes cannot hide
a failed proxy write. `docs/evidence/original_pops_iop_binding_probe.json`
contains only input/module/ELF hashes and measured output.

This uncovered a production defect before game testing: Sony MODLOAD supplies
a loader filename at argv[0] (`LBbyEE` for `SifExecModuleBuffer`), moving our
mode to argv[1]. The old driver rejected the real call with nonresident result
1. POPFS now strips that filename and the host contract fixture includes it.
The formatter also rejects packets larger than LOADFILE's `LF_ARG_MAX=252`
before mutation; previously the SDK would silently truncate them. Production
has a compile-time check against the SDK limit.

PCSX2 initially produced a misleading save failure. Its
[IopBios.cpp write_HLE](https://github.com/PCSX2/pcsx2/blob/master/pcsx2/IopBios.cpp)
intercepts imported IOMAN and IOMANX writes to fd 1 as console output, returns
the full requested count and bypasses the actual driver. The Sony image leaves
that descriptor available, so a proxy's nested backing open can allocate it.
The emulator fixture holds descriptors 0/1 open before testing; this workaround
is **absent from production**. The `--console-screen` hardware variant omits
the workaround and displays EE results through GS because the custom reset
removes ps2link's network services. Do not interpret a missing network exit
marker after that reset as the probe's own failure result.

Reproduce after building launcHER, using fresh ignored directories:

```text
python tools/prepare_pops_iop_binding_probe.py --elf EXTERNAL/POPS.ELF --iop-image EXTERNAL/IOPRP252.IMG --launcher-build build/pops-ps2sdk --out build/iop-binding
ps2build build -c build/iop-binding/ps2.yaml -o build/iop-binding/gcc --toolchain gcc
ps2build build -c build/iop-binding/ps2.yaml -o build/iop-binding/llvm --toolchain llvm
```

Run `tools/run_pops_iop_binding_probe.ps1` with the same emulator/BIOS/output
parameters as the EE runner, selecting `bin/pops_iop_binding_probe.elf`.
The isolated runner disables memory cards, limits execution to 45 seconds and
stops only its own PCSX2 process. Generated external arrays and probe ELFs
remain local under ignored `build/` and must never be distributed. Four
source-only input/layout guards run in CI without Sony binaries.

**Remaining acceptance:** a complete POPS game boot, actual Sony card runtime,
device streaming, audio and physical save/reload/power-cycle persistence.
In-memory close/reopen proves the bridge and RPC route, not durable saves.

The first hardware binding attempt, `20261014T004047-0013`, did **not** pass.
The physical OBS capture showed Sony reset complete, iomanX/fileXio/backend
start results 0, then `load=production-popfs` without a return or final marker.
The next diagnostic must pinpoint module-load versus driver-initialization
progress. The network-only rig labeled the run hung, as expected after the
reset removed ps2link; the incomplete screen progress is the stronger evidence.

For that boundary, preparation also accepts `--startup-trace`. It compiles a
**diagnostic copy** of current POPFS with volatile progress records, leaving
production source/IRX unchanged. An EE worker performs module loading while a
bounded watchdog reads IOP RAM directly with SDK `smem_read`; it does not need
an IOP RPC response. The watchdog prints every matching progress record for
12 one-second samples. A stage-0 record can be the uploaded IRX buffer; the
executing module changes its own record. Stages: 1 entry/argc, 2 mode string,
3 before GetDeviceList, 4 returned table, 100..131 device index and pointer,
5 path validation, 6/7 before/after clearing paths, 8 collision checks,
9/10 before/after first AddDrv, 11 alias AddDrv, 12 successful return. Reaching
stage 12 and module result 0 was verified in PCSX2. A diagnostic build's pass
does not establish the identical production module's hardware behavior.

`tools/prepare_pops_device_inventory.py --launcher-build build/pops-ps2sdk
--out build/device-inventory` prepares a separate read-only device probe.
It adds the launcher's USB/MMCE drivers to an inherited ps2link environment
without an IOP reboot, then lists bounded directories through iomanX. Never
overwrite an existing driver or choose a game/save path from stale inventory.
The first physical attempt observed two USB disks mounted by BDM/FatFs but
did not finish directory enumeration. No game or existing save was modified.

## Hardware-confirmed IOMAN layout mismatch

Watchdog run `20261014T010845-0017` repeatedly displayed executing POPFS
stage 100, value `0x00000003`: `driver_name_in_use()` index zero received
descriptor flags as a device pointer. Its trace metadata is committed in
`docs/evidence/pops_ioman_layout_console_trace.json`.

The selected loose and packed-252 images contain identical IOMAN IRXs:
12,545 bytes, SHA256
`319a8e22e7efb42d224a21af98aa7e6b3dcaa2cd206eb8357e7b26e273827baf`.
Their module version is 2.03, text/data/BSS sizes are `0x1e60/0x1f0/0x290`.
Original entry/AddDrv/cleanup instructions establish BSS-relative used-device
head `+0x0c`, 32 file slots at `+0x10` (512 bytes), and sixteen 8-byte linked
device nodes at `+0x210`. The SDK hook assumes sixteen flat device pointers
at `+0x10` and sixteen files at `+0x50`. Thus it copies the first file's mode
3 as a device pointer and clears the wrong state. PCSX2's IOMAN HLE hides
that invalid inherited state in the earlier emulator-only result.

The packed-2305A image uses IOMAN 2.01: 11,177 bytes, SHA256
`ec0097316c10bdefb1fc3cdd19843e90118a5f4e3ac579b0a6c9de1d3d597987`,
text/data/BSS `0x1b90/0x180/0x250`. Its entry explicitly clears 64 bytes of
device pointers at BSS `+0x10` and 512 file bytes at `+0x50`.

A separate licensed SDK-derived `launcher/iop/pops_iomanx` candidate snapshots
both exact layouts before export replacement, rejects unexpected metadata,
cycles and file references to unknown devices, migrates all 32 file slots,
and detaches old device ownership to avoid duplicate deinitialization.
The host regression reproduces the descriptor-mode-3 case and validates both
layouts and failure atomicity. Replacing only iomanX in the controlled probe
passes PCSX2 with unchanged production POPFS and original IOPCD. Standard
handles 0/1 survive correctly; emulator reservation then receives 2/3.
This candidate is not yet selected by the launcher pending hardware comparison.
The stock iomanX path for normal launcher/Ember initialization is untouched.

Build it with the production SDK via `make` in `launcher/iop/pops_iomanx`.
Probe preparation accepts `--iomanx-override` with the resulting IRX; metadata
and console logs mark the candidate explicitly. Use `--console-screen` for
hardware; do not use the instrumented POPFS copy for that final comparison.

Hardware comparison `20261014T012340-0018` substituted only this iomanX
candidate and the unchanged production POPFS returned start 0, resolving
the earlier startup stall. It then displayed explicit FAIL at stage 6 with
result -16; full bridge acceptance is still open. Source inspection confirms
SDK IOMANX clears only a consumed file slot's device pointer, leaving stale
`privdata` from the previous driver. POPFS incorrectly rejected such a newly
allocated slot as busy. Its open callback now initializes its own private
ownership; the manager already prevents allocating an active slot twice.
The regression starts with poisoned private data and verifies descriptor-zero
handling, active-handle exclusion and close lifetime. The rebuilt production
driver and candidate pass the controlled emulator probe; the updated hardware
comparison also reports file-service bind/open results explicitly.
