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
| Direct storage without BDMA | No runtime implementation | Own POPS-facing IOP bridge backed by supported device services; establish behavior across POPS IOP setup |
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

The host tests run in GitHub Actions alongside the PS2SDK build and gate release
publication. At this stage no new exact-head CI, PS2 build or console result has
been obtained. Local Docker's Linux daemon was unavailable during implementation.
