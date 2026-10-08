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
| External POPS load | Structural ELF inspection | Image identity/profile, PAK unpacking, placement, BSS, loader coexistence and executable handoff |
| Trojan and PATCH support | Parsing, options decoding, guarded buffer staging | Slot precedence, version gates, overlap/order policy, complete configuration semantics, resident execution and cache handling |
| Core POPS patches | Reference locations available | Reconstruct verified expected/replacement words and dependencies for each supported image |
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
```

The runner preserves and checks every parsed header field against an independent
binary decode, checks every corpus staging range, and decodes every PATCH's
configuration intent. It never copies the input files into the repository.

Initial validation: 20 host tests pass; all 4,820 corpus files and both root
specimens parse and plan successfully; the external reference ELF passes
structural checks. The tests cover failed guards leaving memory untouched,
malformed/truncated files, address arithmetic, source/destination aliasing, JAL
delay-instruction preservation, J variants, PATCH metadata and scratchpad bounds.

The host tests run in GitHub Actions alongside the PS2SDK build and gate release
publication. At this stage no new exact-head CI, PS2 build or console result has
been obtained. Local Docker's Linux daemon was unavailable during implementation.
