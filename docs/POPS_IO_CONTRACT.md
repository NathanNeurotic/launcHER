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

`tools/trace_original_pops_io.py` now reproduces **21 passing execution cases**
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

```text
python -m pip install unicorn
python tools/trace_original_pops_io.py --popstarter POPSLoader/bin/POPSLDR/PROFILES/MAIN/POPSTARTER.ELF --pops-elf EXTERNAL/POPS.ELF --json build/original-io-trace.json
```

The measured metadata-only result is committed in
`docs/evidence/original_pops_io_trace.json`. Neither Sony nor POPStarter bytes
are included. The script rejects any changed input hash before execution and
bounds each callback by both an instruction count and an emulation timeout.
An unknown import or callback that fails to return aborts the probe.

**Limits:** the EE producer of `request +12` is not executed here. The example
offsets are controlled stimuli, not observed console traffic. IOP services,
filesystem descriptor routing, semaphore success, delay and printf are modeled.
This establishes original callback behavior under those inputs, not Sony's
complete runtime, CDDA, media retries, actual kernel import binding or saves.
The next boundary is EE request production and same-console device/save tests.

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
