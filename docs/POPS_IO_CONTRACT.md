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
The seek callback does not add a VCD header or scale a sector number. This is
static original-code evidence; bounded execution probes are the next step.
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

Use REPOP at the revision above in a separate reference checkout, preserving any
ongoing REPOP development. With external binaries already available locally:

```text
python REPOP/tools/analyze_popstarter_checkout.py POPSLoader --json build/profiles.json
python REPOP/tools/unpack_popstarter.py POPSLoader/bin/POPSLDR/PROFILES/MAIN/POPSTARTER.ELF build/main-unpacked.bin
python REPOP/tools/inspect_popstarter_embedded_irx.py build/main-unpacked.bin --json build/main-iop.json
python REPOP/tools/inspect_popstarter_embedded_irx.py EXTERNAL/POPS.ELF --json build/sony-iop.json
```

These are measured archive/decode/static-module results. They do not establish
canonical unmodified r13 release provenance, Sony IOPCD execution on a console,
backend streaming, saves across power cycles, or full POPStarter parity. Keep
the PR draft. Trace the original IOPCD and embedded wrapper with bounded IOP
execution and controlled file-service responses before changing POPFS semantics.
