# POPStarter r13 launch paths: measured table and difference model

This is the path evidence for `pr23/path-table`. It records the original r13
MAIN running on a host under Unicorn 2.1.4, with synthetic files and modelled
library calls, and launcHER's resolver compiled for the host. Task 2 ran all
**32 cases, 40 `argv[0]` forms and 11 non-argument differences** with no
missing-input skips. The four complete launch kinds reached the pinned
`ExecPS2` call at `0x87c1cc`.

**NOT TESTED on a console.** A modelled `ExecPS2` is not a game boot, proof
that a device exists, runtime-safety evidence, or production path parity.
This branch changes no launcher production behavior and no Ember code. The
owner selected exact HDD `hdd0:__common` / `pfs1:/POPS` mapping for later
POPStarter-only implementation; that is follow-on work, not behavior here.

The executable source of this table is `tools/test_pops_paths.py`, checked
against `tools/trace_original_pops_paths.py`. `CASE_TABLE` retains complete
original summaries, state and writes; `FORM_TABLE` compares the native
resolver; `OTHER_DIFFERENCES` pins the corresponding launcher source rules.
Negative controls reject a wrong path, unmodelled code and hidden missing
inputs. Quiet and verbose runs request the same paths.

## 1. Notation and the pure original-search model

A summary row is `<call site> <operation> <subject> -> <result>`. `{0..9}`
means ten consecutive loop iterations. A range such as `877834..8788d0`
means the first and last of ten call sites. `stop` is the tracer's deliberate
stop at `LAUNCHING POPS` (`0x879e5c`), not an original fatal outcome.

Case state is written `(type, mass, smb, disc, numbered, digit, quiet)`:
launch type at `gp+0x3414`, mass mode at `gp+0x3448`, SMB mode at
`gp+0x3888`, physical-disc mode at `gp+0x3410`, numbered-folder state at
`gp+0x381c`, its character at `gp+0x38b8`, and quiet at `gp+0x38b0`.
Launch types are 0 plain HDD name, 1 `PATINFO`/`EXECUTE`/`LAUNCHER`, 2
`PP.`/`__.`, and 3 `XX.`/`SB.`.

The pure API is `original_search(search) -> list[str]`; it does not call or
derive expectations from launcHER. The three construction rules below are
ordered rules, **not exhaustive examples of arbitrary user-content strings**.
`U(title)`, `H(title)` and `P(partition)` below mean exactly these lists.

`U("GAME")`, USB/SMB image search (`USB_SEARCH`):

```text
mass:/POPS/GAME.VCD
mass:/POPS0/GAME.VCD
mass:/POPS1/GAME.VCD
mass:/POPS2/GAME.VCD
mass:/POPS3/GAME.VCD
mass:/POPS4/GAME.VCD
mass:/POPS5/GAME.VCD
mass:/POPS6/GAME.VCD
mass:/POPS7/GAME.VCD
mass:/POPS8/GAME.VCD
mass:/POPS9/GAME.VCD
```

`H("GAME")`, plain HDD image search (`HDD_SEARCH`):

```text
hdd0:__.POPS:pfs:/GAME.VCD
hdd0:__.POPS0:pfs:/GAME.VCD
hdd0:__.POPS1:pfs:/GAME.VCD
hdd0:__.POPS2:pfs:/GAME.VCD
hdd0:__.POPS3:pfs:/GAME.VCD
hdd0:__.POPS4:pfs:/GAME.VCD
hdd0:__.POPS5:pfs:/GAME.VCD
hdd0:__.POPS6:pfs:/GAME.VCD
hdd0:__.POPS7:pfs:/GAME.VCD
hdd0:__.POPS8:pfs:/GAME.VCD
hdd0:__.POPS9:pfs:/GAME.VCD
```

`P("PP.GAME")`, single-partition search (`PART`):

```text
hdd0:PP.GAME:pfs:/IMAGE0.VCD
```

A partition search has no numbered retry and never substitutes `IMAGE.VCD`.
A negative control changes `mass:/POPS3/GAME.VCD` to an incorrect path and
requires the comparison to fail.

For native comparison, `mass0:` is equivalent to the original's `mass:`; on
an `SB.` row, `smb0:`/`smb:` names the share that the original calls `mass:`.
`at` is the index of the original's first path in launcHER's candidate list,
`None` when absent, and `-` when the original makes no image search. Native
results use `pops_resolve_candidate_targets_bdma(argv0, NULL, ..., 16, none)`.
No native list contains the original's numbered locations or `IMAGE0.VCD`.

## 2. All 40 argument forms

Every form uses the same model answers: both POPS installations are present,
every partition in `FORM_PARTITIONS` is mountable, no image exists anywhere,
and no PS1 disc is reported. Thus a completed search reaches `fatal 876a0c`
(`NO_DISC`). Earlier argument stops are `fatal 874358` (`NOT_FOUND`) or
`exit 8713c8` (`EXIT`). The native tuple is
`prefix / candidate count / first candidate / at`.

| `argv[0]` | Original `(type,mass,smb)` and ordered model answer | End | Measured launcHER result and difference |
|---|---|---|---|
| `mass:/POPS/XX.GAME.ELF` | `(3,1,0)`, `U(GAME)` | NO_DISC | `XX / 10 / mass0:/POPS/GAME.VCD / 0`. Quirk 87: no `POPS0..9` retry; adds `IMAGE.VCD` and other devices. |
| `mass:/XX.GAME.ELF` | `(3,1,0)`, `U(GAME)` | NO_DISC | `XX / 12 / mass0:/GAME.VCD / 4`. Quirk 87: original always uses `mass:/POPS`; launcHER tries the ELF folder first. |
| `mass:/POPS/xx.GAME.ELF` | `(3,1,0)`, `U(GAME)` | NO_DISC | `XX / 10 / mass0:/POPS/GAME.VCD / 0`. Lowercase is accepted by both; quirk 87 retry/list difference remains. |
| `mass:/POPS/Xx.GAME.ELF` | `(0,0,0)`, `H(Xx.GAME)` | NO_DISC | `XX / 10 / mass0:/POPS/GAME.VCD / None`. Quirks 86–87: mixed case is a plain HDD title, prefix included, for the original; launcHER selects USB. |
| `mass:/POPS/xX.GAME.ELF` | `(0,0,0)`, `H(xX.GAME)` | NO_DISC | `XX / 10 / mass0:/POPS/GAME.VCD / None`. Same mixed-case difference as the preceding row. |
| `mass:/POPS/XX.Game.elf` | `(3,1,0)`, `U(Game)` | NO_DISC | `XX / 10 / mass0:/POPS/Game.VCD / 0`. Extension case does not select another original branch; quirk 87 remains. |
| `mass:\POPS\XX.GAME.ELF` | `(3,1,0)`, `U(GAME)` | NO_DISC | `XX / 10 / mass0:\POPS/GAME.VCD / None`. Quirk 87: original normalizes to `mass:/POPS/GAME.VCD`; launcHER retains the backslash in its first four candidates. |
| `mass:XX.GAME.ELF` | `(3,1,0)`, `U(GAME)` | NO_DISC | `XX / 12 / mass0:/GAME.VCD / 4`. Quirk 87: original always uses `mass:/POPS`, not the ELF's own folder first. |
| `mass0:/POPS/XX.GAME.ELF` | `(3,1,0)`, `U(GAME)` | NO_DISC | `XX / 7 / mass0:/POPS/GAME.VCD / 0`. Quirk 87: same original USB search, shorter native list. |
| `hdd0:__common:pfs:/POPS/XX.GAME.ELF` | `(3,1,0)`, `U(GAME)` | NO_DISC | `XX / 11 / hdd0:__common:pfs:/POPS/GAME.VCD / 5`. Quirk 87: `XX.` means USB wherever the ELF is; launcHER tries its HDD folder first. |
| `XX.GAME.ELF` | `(0,0,0)`, `H(XX.GAME)` | NO_DISC | `XX / 6 / mass0:/POPS/GAME.VCD / None`. Quirk 86: without a preceding separator the original sees a plain HDD title, not an `XX.` prefix. |
| `GAME.ELF` | `(0,0,0)`, `H(GAME)` | NO_DISC | `none / 10 / hdd0:__.POPS:pfs:/GAME.VCD / 0`. Quirk 87: no numbered HDD retry; native adds `IMAGE.VCD`, `pfs0:`, `PP.GAME` and other devices. |
| `mass:/POPS/XX.GAME` | `(3,1,0)`, no image search | NOT_FOUND | `XX / 10 / mass0:/POPS/GAME.VCD / -`. Quirk 86: original stops with “Cannot set up the POPS launcher”; launcHER builds candidates. |
| `mass:/POPS/GAME.ELF` | `(0,0,0)`, `H(GAME)` | NO_DISC | `none / 14 / hdd0:__.POPS:pfs:/GAME.VCD / 0`. Quirk 87: plain name means HDD wherever the ELF is; launcHER goes on to its folder and mass. |
| `mc0:/BOOT/GAME.ELF` | `(0,0,0)`, `H(GAME)` | NO_DISC | `none / 14 / hdd0:__.POPS:pfs:/GAME.VCD / 0`. Quirk 87: original never searches mass or mc for this plain title. |
| `mass:/POPS/SB.GAME.ELF` | `(3,1,3)`, `U(GAME)` on the share | NO_DISC | `SB / 7 / smb0:/POPS/GAME.VCD / 0`. Quirk 87: same first share file, no numbered retry, then mass and HDD fallbacks. |
| `mass:/POPS/sb.GAME.ELF` | `(3,1,3)`, `U(GAME)` on the share | NO_DISC | `SB / 7 / smb0:/POPS/GAME.VCD / 0`. Lowercase `sb.` is accepted; quirk 87 remains. |
| `mc0:/POPSTARTER/SB.GAME.ELF` | `(3,1,3)`, `U(GAME)` on the share | NO_DISC | `SB / 7 / smb0:/POPS/GAME.VCD / 0`. Prefix placement does not change the original share search; quirk 87 remains. |
| `mass:/APPS/PP.GAME.ELF` | `(2,0,0)`, `P(PP.GAME)` | NO_DISC | `PP / 9 / hdd0:PP.GAME:pfs:/GAME.VCD / None`. Quirk 87: original asks only for `IMAGE0.VCD`; launcHER asks for `GAME.VCD`, `IMAGE.VCD` and others. |
| `mass:/APPS/__.GAME.ELF` | `(2,0,0)`, `P(__.GAME)` | NO_DISC | `PP / 9 / hdd0:__.GAME:pfs:/GAME.VCD / None`. Same single-partition/`IMAGE0.VCD` difference. |
| `mass:/APPS/pp.GAME.ELF` | `(0,0,0)`, `H(pp.GAME)` | NO_DISC | `PP / 9 / hdd0:PP.GAME:pfs:/GAME.VCD / None`. Quirks 86–87: lowercase `pp.` is not an original partition prefix; the prefix stays in a plain HDD title. |
| `hdd0:__common:pfs:/POPS/GAME.ELF` | `(0,0,0)`, `H(GAME)` | NO_DISC | `none / 15 / hdd0:__.POPS:pfs:/GAME.VCD / 0`. Quirk 87: no numbered retry and many additional native candidates. |
| `hdd0:PP.ALPHA:pfs:/PP.BETA.ELF` | `(2,0,0)`, `P(PP.BETA)` | NO_DISC | `PP / 9 / hdd0:PP.BETA:pfs:/BETA.VCD / None`. Quirk 87: partition comes from the ELF name and only `IMAGE0.VCD` is opened. |
| `hdd0:PP.ALPHA:pfs:/__.BETA.ELF` | `(2,0,0)`, `P(__.BETA)` | NO_DISC | `PP / 9 / hdd0:__.BETA:pfs:/BETA.VCD / None`. Same `__.` single-partition rule and native difference. |
| `hdd0:PP.ALPHA:pfs:/pp.BETA.ELF` | `(0,0,0)`, `H(pp.BETA)` | NO_DISC | `PP / 9 / hdd0:PP.BETA:pfs:/BETA.VCD / None`. Quirks 86–87: lowercase `pp.` is a plain HDD title for the original. |
| `hdd0:PP.ALPHA:pfs:/SUB/PP.BETA.ELF` | `(0,0,0)`, `H(PP.BETA)` | NO_DISC | `PP / 9 / hdd0:PP.BETA:pfs:/BETA.VCD / None`. Quirks 86–87: after a subdirectory slash this is not an original type-2 prefix. |
| `hdd0:PP.ALPHA:pfs:/EXECUTE.KELF` | `(1,0,0)`, `P(PP.ALPHA)` | NO_DISC | `none / 15 / hdd0:__.POPS:pfs:/EXECUTE.VCD / None`. Quirks 86–87: original takes the partition from `argv[0]`; launcHER treats `EXECUTE` as a title. |
| `hdd0:PP.ALPHA:pfs:/EXECUTE.ELF` | `(1,0,0)`, `P(PP.ALPHA)` | NO_DISC | `none / 15 / hdd0:__.POPS:pfs:/EXECUTE.VCD / None`. Same type-1 partition rule for `.ELF`. |
| `hdd0:PP.ALPHA:pfs:/LAUNCHER.ELF` | `(1,0,0)`, `P(PP.ALPHA)` | NO_DISC | `none / 15 / hdd0:__.POPS:pfs:/LAUNCHER.VCD / None`. Same type-1 rule for `LAUNCHER.ELF`. |
| `hdd0:PP.ALPHA:pfs:/LAUNCHER.KELF` | `(1,0,0)`, `P(PP.ALPHA)` | NO_DISC | `none / 15 / hdd0:__.POPS:pfs:/LAUNCHER.VCD / None`. Same type-1 rule for `LAUNCHER.KELF`. |
| `hdd0:PP.ALPHA:pfs:/execute.kelf` | `(0,0,0)`, `H(execute)` | NO_DISC | `none / 15 / hdd0:__.POPS:pfs:/execute.VCD / 0`. Lowercase is not original type 1; quirk 87 numbered/extra-candidate difference remains. |
| `hdd0:PP.ALPHA:pfs:/SUB/EXECUTE.KELF` | `(1,0,0)`, `P(PP.ALPHA)` | NO_DISC | `none / 15 / hdd0:__.POPS:pfs:/EXECUTE.VCD / None`. Quirks 86–87: uppercase type-1 name is recognized after `SUB`; native treats it as a title. |
| `hdd0:ALPHA:pfs:/EXECUTE.KELF` | `(1,0,0)`, `P(ALPHA)` | NO_DISC | `none / 15 / hdd0:__.POPS:pfs:/EXECUTE.VCD / None`. The original type-1 partition need not start `PP.` or `__.`. |
| `hdd0:PP.ALPHA:PATINFO` | `(1,0,0)`, `P(PP.ALPHA)` | NO_DISC | `none / 15 / hdd0:__.POPS:pfs:/PATINFO.VCD / None`. Quirk 86: launcHER main sends `:PATINFO` to its generic handler before POPS resolution. |
| `hdd0:__.ALPHA:PATINFO` | `(1,0,0)`, `P(__.ALPHA)` | NO_DISC | `none / 15 / hdd0:__.POPS:pfs:/PATINFO.VCD / None`. Same original partition selection and generic-PATINFO difference. |
| `hdd0:ALPHA:PATINFO` | `(1,0,0)`, `P(ALPHA)` | NO_DISC | `none / 15 / hdd0:__.POPS:pfs:/PATINFO.VCD / None`. Same rule without a `PP.`/`__.` partition prefix. |
| `hdd0:PP.ALPHA:patinfo` | `(0,0,0)`, no image search | NOT_FOUND | `none / 15 / hdd0:__.POPS:pfs:/patinfo.VCD / -`. Quirk 86: lowercase `patinfo` does not select original type 1 and stops; launcHER builds candidates. |
| `pfs0:/EXECUTE.KELF` | `(0,0,0)`, no image search | NOT_FOUND | `none / 12 / hdd0:__.POPS:pfs:/EXECUTE.VCD / -`. Quirk 86: original says `EXECUTE.KELF was not renamed`; launcHER builds candidates. |
| `cdrom0:\SLUS_000.00;1` | `(0,0,0)`, no image search | EXIT | `none / 14 / hdd0:__.POPS:pfs:/SLUS_000.VCD / -`. Quirk 86: original exits for `argv[0]` starting `cdrom`; native builds candidates (main's disc handler is OSDM-only). |
| `argc == 0` | `(0,0,0)`, no image search | EXIT | `none / 0 / no first candidate / -`. Quirk 86: original exits; launcHER main reports invalid launcher arguments and normalization returns `-1`. |

The complete native lists for the four principal forms are published beside
their full traces below. They are measurements of current launcHER, never a
source of original expectations.

## 3. Four complete original traces

These are full `summary(report)` comparisons, not selected path subsets. All
optional files are absent unless the model answers say otherwise. Writes are
synthetic zero-filled outputs described only by path and byte count.

### `usb`: `XX.` USB launch to POPS

Model answers: `mass:/POPS` exists; `POPS_IOX.PAK` and `GAME.VCD` open there;
both memory cards are initially absent and creation succeeds; optional files
are absent. State: `(3,1,0,0,0,"",1)`. Outcome: `ExecPS2` entry `0x200000`.
Writes: `mass:/POPS/GAME/SLOT0.VMC` and `SLOT1.VMC`, `0x20000` bytes each.
LauncHER difference: native candidates below match only the first original
location (quirks 87, 89, 94–95); package search and card naming also differ.

```text
8713d8 fioOpen rom0:PSXVER -> -2
871418 SifIopReset 'rom0:UDNL '
871470 SifIopReset 'rom0:UDNL '
871a3c SifLoadModule rom0:SIO2MAN -> loaded
871a88 SifLoadModule rom0:MCMAN -> loaded
871d6c fioOpen mc0:/POPSTARTER/usbd.irx -> -2
871e28 fioOpen mc1:/POPSTARTER/usbd.irx -> -2
871f20 fioOpen mc0:/POPSTARTER/usbhdfsd.irx -> -2
871fdc fioOpen mc1:/POPSTARTER/usbhdfsd.irx -> -2
8720ec SifExecModuleBuffer 0x6935 bytes -> started
872188 SifExecModuleBuffer 0xbecd bytes -> started
8d8a68 fioGetstat mass:/POPS -> 0
87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> ok
87d350 unpack to 0x200000 -> 0x33ebb9 bytes
8761d8 fioOpen mass:/POPS/GAME.VCD -> ok
87e538 fioOpen mass:/POPS/IGR_BG.TM2 -> -2
87e75c fioOpen mass:/POPS/IGR_NO.TM2 -> -2
87e968 fioOpen mass:/POPS/IGR_YES.TM2 -> -2
87f0d0 fioOpen mass:/POPS/OSD.BIN -> -2
8807d4 fioOpen mass:/POPS/BIOS.BIN -> -2
88114c fioOpen mass:/POPS/TROJAN_{0..9}.BIN -> -2
88249c fioOpen mass:/POPS/PATCH_{0..9}.BIN -> -2
87ee9c fioGetstat mass:/POPS/GAME/ -> -2
883840 fioOpen mass:/POPS/CHEATS.TXT -> -2
8d554c fioOpen mass:/POPS/VMCDIR.TXT -> -2
8d6280 fioOpen mass:/POPS/DISCS.TXT -> -2
877834..8788d0 fioOpen mass:/POPS/MODULE_{0..9}.IRX -> -2
8d83c0 fioGetstat mass0:/POPS/GAME -> -2
8d83d4 fioMkdir mass0:/POPS/GAME -> 0
8d8d2c fioOpen mass0:/POPS/GAME/SLOT0.VMC -> -2
8d8d2c fioOpen mass0:/POPS/GAME/SLOT0.VMC [create] -> ok
8d8d9c fioWrite mass:/POPS/GAME/SLOT0.VMC -> 0x20000 bytes
8d8d2c fioOpen mass0:/POPS/GAME/SLOT1.VMC -> -2
8d8d2c fioOpen mass0:/POPS/GAME/SLOT1.VMC [create] -> ok
8d8d9c fioWrite mass:/POPS/GAME/SLOT1.VMC -> 0x20000 bytes
87a78c SifIopReset 'rom0:UDNL '
87a7f4 SifIopReset 'rom0:UDNL '
87a900 SifLoadModuleBuffer buffer 0x100000 -> loaded
87acc4 SifExecModuleBuffer 0x6935 bytes -> started
87ad70 SifExecModuleBuffer 0xbecd bytes -> started
87c054 SifExecModuleBuffer 0xa45 bytes -> started
87c1cc ExecPS2 entry 0x200000 gp 0x0 argc 1
```

Current native candidates for `mass:/POPS/XX.GAME.ELF`, in order:

```text
mass0:/POPS/GAME.VCD
mass0:/POPS/IMAGE.VCD
mass:/POPS/GAME.VCD
mass:/POPS/IMAGE.VCD
mass0:/GAME.VCD
mass:/GAME.VCD
mass1:/POPS/GAME.VCD
mc0:/POPS/GAME.VCD
mc1:/POPS/GAME.VCD
hdd0:__.POPS:pfs:/GAME.VCD
```

### `hdd`: plain-name HDD launch to POPS

Model answers: `hdd0:__common` mounts as `pfs1:`; `POPS.ELF` and
`IOPRP252.IMG` are under `pfs1:/POPS`; `hdd0:__.POPS` mounts as `pfs0:` and
contains `GAME.VCD`; the game folder and icon files are initially absent and
creation succeeds. State: `(0,0,0,0,0,"",1)`. Outcome: `ExecPS2` entry
`0x200000`. Writes: `hdd0:__common:pfs:/POPS/GAME/icon.sys` (`0x3c4` bytes)
and `list.ico` (`0x8158` bytes). LauncHER difference: its first candidate is
the same plain-name VCD, but its list, package source, HDD per-game folder
and missing icon staging differ (quirks 87–88, 90, 92–93).

```text
8713d8 fioOpen rom0:PSXVER -> -2
871418 SifIopReset 'rom0:UDNL '
871470 SifIopReset 'rom0:UDNL '
871a3c SifLoadModule rom0:SIO2MAN -> loaded
871a88 SifLoadModule rom0:MCMAN -> loaded
871ae4 SifExecModuleBuffer 0x2a25 bytes -> started
871b34 SifExecModuleBuffer 0x23b1 bytes -> started
871b8c SifExecModuleBuffer 0xecd bytes -> started
871bdc SifExecModuleBuffer 0x3389 bytes -> started
871c2c SifExecModuleBuffer 0x3159 bytes -> started
871c7c SifExecModuleBuffer 0x7a91 bytes -> started
871ccc SifExecModuleBuffer 0xcd55 bytes -> started
8d801c fileXioDevctl pfs: 0x5003 -> 0
8d8028 fileXioUmount pfs0: -> -2
8d8034 fileXioUmount pfs1: -> -2
8d8b40 fileXioUmount pfs1: -> -2
8d8b6c fileXioMount pfs1: = hdd0:__common -> 0
8d7eac fileXioGetStat pfs1:/POPS/ -> 0
8d7fa8 fileXioChStat pfs1:/POPS/ -> 0
8d7fbc fileXioChStat pfs1:/POPS/ -> 0
87dad8 fileXioOpen pfs1:/POPS/POPS.ELF -> ok
87df88 fileXioOpen pfs1:/POPS/IOPRP252.IMG -> ok
875bec fileXioUmount pfs0: -> -2
875c20 fileXioMount pfs0: = hdd0:__.POPS -> 0
875c98 fileXioOpen pfs0:GAME.VCD -> ok
87e4f8 fileXioOpen pfs1:/POPS/IGR_BG.TM2 -> -2
87e71c fileXioOpen pfs1:/POPS/IGR_NO.TM2 -> -2
87e928 fileXioOpen pfs1:/POPS/IGR_YES.TM2 -> -2
87f0b8 fileXioOpen pfs1:/POPS/OSD.BIN -> -2
8807bc fileXioOpen pfs1:/POPS/BIOS.BIN -> -2
881134 fileXioOpen pfs1:/POPS/TROJAN_{0..9}.BIN -> -2
882484 fileXioOpen pfs1:/POPS/PATCH_{0..9}.BIN -> -2
8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> -2
8d7ed4 fileXioMkdir pfs1:/POPS/GAME/ -> 0
8d7ee4 fileXioGetStat pfs1:/POPS/GAME/ -> 0
8d7f10 fileXioChStat pfs1:/POPS/GAME/ -> 0
8d7f24 fileXioChStat pfs1:/POPS/GAME/ -> 0
883828 fileXioOpen pfs1:/POPS/CHEATS.TXT -> -2
8d5534 fileXioOpen pfs1:/POPS/VMCDIR.TXT -> -2
8d6268 fileXioOpen pfs1:/POPS/DISCS.TXT -> -2
8777f4..878890 fileXioOpen pfs1:/POPS/MODULE_{0..9}.IRX -> -2
8d878c fileXioGetStat pfs1:/POPS/GAME/ -> 0
8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> 0
8d7fa8 fileXioChStat pfs1:/POPS/GAME/ -> 0
8d7fbc fileXioChStat pfs1:/POPS/GAME/ -> 0
8d87e4 fileXioOpen pfs1:/POPS/GAME/icon.sys -> -2
8d8808 fileXioOpen pfs1:/POPS/GAME/icon.sys [create] -> ok
8d8828 fileXioWrite hdd0:__common:pfs:/POPS/GAME/icon.sys -> 0x3c4 bytes
8d8860 fileXioOpen pfs1:/POPS/GAME/list.ico -> -2
8d8884 fileXioOpen pfs1:/POPS/GAME/list.ico [create] -> ok
8d88a0 fileXioWrite hdd0:__common:pfs:/POPS/GAME/list.ico -> 0x8158 bytes
8d801c fileXioDevctl pfs: 0x5003 -> 0
8d8028 fileXioUmount pfs0: -> 0
8d8034 fileXioUmount pfs1: -> 0
87a78c SifIopReset 'rom0:UDNL '
87a7f4 SifIopReset 'rom0:UDNL '
87a900 SifLoadModuleBuffer buffer 0x100000 -> loaded
87c1cc ExecPS2 entry 0x200000 gp 0x0 argc 1
```

Current native candidates for `hdd0:__common:pfs:/POPS/GAME.ELF`, in order:

```text
hdd0:__.POPS:pfs:/GAME.VCD
hdd0:__.POPS:pfs:/IMAGE.VCD
pfs0:/GAME.VCD
pfs0:/IMAGE.VCD
hdd0:PP.GAME:pfs:/GAME.VCD
hdd0:PP.GAME:pfs:/IMAGE.VCD
hdd0:__common:pfs:/POPS/GAME.VCD
hdd0:__common:pfs:/POPS/IMAGE.VCD
hdd0:/POPS/GAME.VCD
hdd0:/POPS/IMAGE.VCD
hdd0:/GAME.VCD
mass0:/POPS/GAME.VCD
mass0:/GAME.VCD
mc0:/POPS/GAME.VCD
mc1:/POPS/GAME.VCD
```

### `hdd-pp`: one-game partition launch to POPS

Model answers are the `hdd` answers except that `hdd0:PP.GAME` mounts as
`pfs0:` and contains `IMAGE0.VCD`. State: `(2,0,0,0,0,"",1)`. Outcome and
writes are the same as `hdd`. LauncHER difference: no native candidate is
`hdd0:PP.GAME:pfs:/IMAGE0.VCD`; native starts with `GAME.VCD` and
`IMAGE.VCD` (quirk 87). HDD package, folder and icon differences are quirks
88, 90 and 92–93.

```text
8713d8 fioOpen rom0:PSXVER -> -2
871418 SifIopReset 'rom0:UDNL '
871470 SifIopReset 'rom0:UDNL '
871a3c SifLoadModule rom0:SIO2MAN -> loaded
871a88 SifLoadModule rom0:MCMAN -> loaded
871ae4 SifExecModuleBuffer 0x2a25 bytes -> started
871b34 SifExecModuleBuffer 0x23b1 bytes -> started
871b8c SifExecModuleBuffer 0xecd bytes -> started
871bdc SifExecModuleBuffer 0x3389 bytes -> started
871c2c SifExecModuleBuffer 0x3159 bytes -> started
871c7c SifExecModuleBuffer 0x7a91 bytes -> started
871ccc SifExecModuleBuffer 0xcd55 bytes -> started
8d801c fileXioDevctl pfs: 0x5003 -> 0
8d8028 fileXioUmount pfs0: -> -2
8d8034 fileXioUmount pfs1: -> -2
8d8b40 fileXioUmount pfs1: -> -2
8d8b6c fileXioMount pfs1: = hdd0:__common -> 0
8d7eac fileXioGetStat pfs1:/POPS/ -> 0
8d7fa8 fileXioChStat pfs1:/POPS/ -> 0
8d7fbc fileXioChStat pfs1:/POPS/ -> 0
87dad8 fileXioOpen pfs1:/POPS/POPS.ELF -> ok
87df88 fileXioOpen pfs1:/POPS/IOPRP252.IMG -> ok
875684 fileXioMount pfs0: = hdd0:PP.GAME -> 0
8756f4 fileXioOpen pfs0:IMAGE0.VCD -> ok
87e4f8 fileXioOpen pfs1:/POPS/IGR_BG.TM2 -> -2
87e71c fileXioOpen pfs1:/POPS/IGR_NO.TM2 -> -2
87e928 fileXioOpen pfs1:/POPS/IGR_YES.TM2 -> -2
87f0b8 fileXioOpen pfs1:/POPS/OSD.BIN -> -2
8807bc fileXioOpen pfs1:/POPS/BIOS.BIN -> -2
881134 fileXioOpen pfs1:/POPS/TROJAN_{0..9}.BIN -> -2
882484 fileXioOpen pfs1:/POPS/PATCH_{0..9}.BIN -> -2
8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> -2
8d7ed4 fileXioMkdir pfs1:/POPS/GAME/ -> 0
8d7ee4 fileXioGetStat pfs1:/POPS/GAME/ -> 0
8d7f10 fileXioChStat pfs1:/POPS/GAME/ -> 0
8d7f24 fileXioChStat pfs1:/POPS/GAME/ -> 0
883828 fileXioOpen pfs1:/POPS/CHEATS.TXT -> -2
8d5534 fileXioOpen pfs1:/POPS/VMCDIR.TXT -> -2
8d6268 fileXioOpen pfs1:/POPS/DISCS.TXT -> -2
8777f4..878890 fileXioOpen pfs1:/POPS/MODULE_{0..9}.IRX -> -2
8d878c fileXioGetStat pfs1:/POPS/GAME/ -> 0
8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> 0
8d7fa8 fileXioChStat pfs1:/POPS/GAME/ -> 0
8d7fbc fileXioChStat pfs1:/POPS/GAME/ -> 0
8d87e4 fileXioOpen pfs1:/POPS/GAME/icon.sys -> -2
8d8808 fileXioOpen pfs1:/POPS/GAME/icon.sys [create] -> ok
8d8828 fileXioWrite hdd0:__common:pfs:/POPS/GAME/icon.sys -> 0x3c4 bytes
8d8860 fileXioOpen pfs1:/POPS/GAME/list.ico -> -2
8d8884 fileXioOpen pfs1:/POPS/GAME/list.ico [create] -> ok
8d88a0 fileXioWrite hdd0:__common:pfs:/POPS/GAME/list.ico -> 0x8158 bytes
8d801c fileXioDevctl pfs: 0x5003 -> 0
8d8028 fileXioUmount pfs0: -> 0
8d8034 fileXioUmount pfs1: -> 0
87a78c SifIopReset 'rom0:UDNL '
87a7f4 SifIopReset 'rom0:UDNL '
87a900 SifLoadModuleBuffer buffer 0x100000 -> loaded
87c1cc ExecPS2 entry 0x200000 gp 0x0 argc 1
```

Current native candidates for the equivalent partition form
`hdd0:PP.ALPHA:pfs:/PP.BETA.ELF`, in order:

```text
hdd0:PP.BETA:pfs:/BETA.VCD
hdd0:PP.BETA:pfs:/IMAGE.VCD
hdd0:PP.BETA:pfs:/PP.BETA.VCD
pfs0:/BETA.VCD
pfs0:/IMAGE.VCD
pfs0:/PP.BETA.VCD
hdd0:__.POPS:pfs:/BETA.VCD
hdd0:__.POPS:pfs:/IMAGE.VCD
mass0:/POPS/BETA.VCD
```

### `smb`: `SB.` network-share launch to POPS

Model answers: `mc0:/POPSTARTER/SMBCONFIG.DAT` is valid synthetic
server/share text; the five required network modules are on `mc0:`;
`smsutils.irx` is absent; LOGON/ECHO/OPENSHARE succeed; the share appears as
`mass:` and supplies `POPS_IOX.PAK` and `GAME.VCD`; cards are created as in
`usb`. State: `(3,1,3,0,0,"",0)`. Outcome: `ExecPS2` entry `0x200000`.
Writes: the two `mass:/POPS/GAME/SLOTn.VMC` files, `0x20000` bytes each.
LauncHER difference: the first share candidate coincides, but native falls
back to other devices and has no numbered folders; package/card rules also
differ (quirks 87, 89, 94–95).

```text
8713d8 fioOpen rom0:PSXVER -> -2
871418 SifIopReset 'rom0:UDNL '
871470 SifIopReset 'rom0:UDNL '
871a3c SifLoadModule rom0:SIO2MAN -> loaded
871a88 SifLoadModule rom0:MCMAN -> loaded
872228 SifExecModuleBuffer 0x2a25 bytes -> started
872278 SifExecModuleBuffer 0x23b1 bytes -> started
8722c0 fioOpen mc0:/POPSTARTER/IPCONFIG.DAT -> -2
872380 fioOpen mc1:/POPSTARTER/IPCONFIG.DAT -> -2
87263c fioOpen mc0:/POPSTARTER/SMBCONFIG.DAT -> ok
873460 fioOpen mc0:/POPSTARTER/poweroff.irx -> ok
873588 SifExecModuleBuffer 0x1000 bytes -> started
8735c8 fioOpen mc0:/POPSTARTER/ps2dev9.irx -> ok
8736f0 SifExecModuleBuffer 0x1000 bytes -> started
873730 fioOpen mc0:/POPSTARTER/smsutils.irx -> -2
8737f8 fioOpen mc1:/POPSTARTER/smsutils.irx -> -2
8738b8 fioOpen mc0:/POPSTARTER/ps2ip.irx -> ok
8739e0 SifExecModuleBuffer 0x1000 bytes -> started
873a20 fioOpen mc0:/POPSTARTER/ps2smap.irx -> ok
873b78 SifExecModuleBuffer 0x1000 bytes -> started
873bc8 fioOpen mc0:/POPSTARTER/smbman.irx -> ok
873ec4 SifExecModuleBuffer 0x1000 bytes -> started
874140 fileXioDevctl mass0: 0xc0de0002 '192.168.0.2' -> 0
874170 fileXioDevctl mass0: 0xc0de0007 'ALIVE ECHO TEST' -> 0
8741a0 fileXioDevctl mass0: 0xc0de0005 'PS2SMB' -> 0
87421c fioOpen mass:/POPS/POPS_IOX.PAK -> ok
87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> ok
87d350 unpack to 0x200000 -> 0x33ebb9 bytes
8761d8 fioOpen mass:/POPS/GAME.VCD -> ok
87e538 fioOpen mass:/POPS/IGR_BG.TM2 -> -2
87e75c fioOpen mass:/POPS/IGR_NO.TM2 -> -2
87e968 fioOpen mass:/POPS/IGR_YES.TM2 -> -2
87f0d0 fioOpen mass:/POPS/OSD.BIN -> -2
8807d4 fioOpen mass:/POPS/BIOS.BIN -> -2
88114c fioOpen mass:/POPS/TROJAN_{0..9}.BIN -> -2
88249c fioOpen mass:/POPS/PATCH_{0..9}.BIN -> -2
87ee9c fioGetstat mass:/POPS/GAME/ -> -2
883840 fioOpen mass:/POPS/CHEATS.TXT -> -2
8d554c fioOpen mass:/POPS/VMCDIR.TXT -> -2
8d6280 fioOpen mass:/POPS/DISCS.TXT -> -2
8775b0 fioOpen mass:/POPS/iomanx.irx -> -2
8776d8 fioOpen mass:/POPS/filexio.irx -> -2
877834..8788d0 fioOpen mass:/POPS/MODULE_{0..9}.IRX -> -2
8d8418 fileXioGetStat mass0:/POPS/GAME -> -2
8d8430 fileXioMkdir mass0:/POPS/GAME -> 0
8d865c fileXioOpen mass0:/POPS/GAME/SLOT0.VMC -> -2
8d8680 fileXioOpen mass0:/POPS/GAME/SLOT0.VMC [create] -> ok
8d869c fileXioWrite mass:/POPS/GAME/SLOT0.VMC -> 0x20000 bytes
8d86e8 fileXioOpen mass0:/POPS/GAME/SLOT1.VMC -> -2
8d870c fileXioOpen mass0:/POPS/GAME/SLOT1.VMC [create] -> ok
8d8728 fileXioWrite mass:/POPS/GAME/SLOT1.VMC -> 0x20000 bytes
878f1c fileXioDevctl mass0: 0xc0de0006 -> 0
878f3c fileXioDevctl mass0: 0xc0de0003 -> 0
87a78c SifIopReset 'rom0:UDNL '
87a7f4 SifIopReset 'rom0:UDNL '
87a900 SifLoadModuleBuffer buffer 0x100000 -> loaded
87ae88 SifExecModuleBuffer 0x2a25 bytes -> started
87af5c SifExecModuleBuffer 0x23b1 bytes -> started
87b614 SifExecModuleBuffer 0x1000 bytes -> started
87b678 SifExecModuleBuffer 0x1000 bytes -> started
87b750 SifExecModuleBuffer 0x1000 bytes -> started
87b7e4 SifExecModuleBuffer 0x1000 bytes -> started
87b848 SifExecModuleBuffer 0x1000 bytes -> started
87b8b8 fileXioDevctl mass0: 0xc0de0002 '192.168.0.2' -> 0
87b8e0 fileXioDevctl mass0: 0xc0de0007 'ALIVE ECHO TEST' -> 0
87b908 fileXioDevctl mass0: 0xc0de0005 'PS2SMB' -> 0
87c054 SifExecModuleBuffer 0xa45 bytes -> started
87c1cc ExecPS2 entry 0x200000 gp 0x0 argc 1
```

Current native candidates for `mass:/POPS/SB.GAME.ELF`, in order:

```text
smb0:/POPS/GAME.VCD
smb0:/GAME.VCD
smb:/POPS/GAME.VCD
smb:/GAME.VCD
mass:/POPS/GAME.VCD
mass0:/POPS/GAME.VCD
hdd0:__.POPS:pfs:/GAME.VCD
```

## 4. Every other case: branch answers, ordered paths and outcome

The difference references below are to the numbered register in section 5.
A native resolver comparison cannot emulate an original startup failure; for
those rows it supplies the corresponding form's current candidate rule, not
a claim that launcHER has the same failure branch.

### `usb-folder`: game folder and both cards already exist

Model answers are `usb` plus an existing game folder and two valid cards.
State `(3,1,0,0,0,"",1)`; no writes; deliberate `stop` at `0x879e5c`.
LauncHER additionally accepts other card names/locations (quirk 95); its
usual `mass:/POPS` candidate is only the first row of its larger list (87).

```text
8713d8 fioOpen rom0:PSXVER -> -2
871418 SifIopReset 'rom0:UDNL '
871470 SifIopReset 'rom0:UDNL '
871a3c SifLoadModule rom0:SIO2MAN -> loaded
871a88 SifLoadModule rom0:MCMAN -> loaded
871d6c fioOpen mc0:/POPSTARTER/usbd.irx -> -2
871e28 fioOpen mc1:/POPSTARTER/usbd.irx -> -2
871f20 fioOpen mc0:/POPSTARTER/usbhdfsd.irx -> -2
871fdc fioOpen mc1:/POPSTARTER/usbhdfsd.irx -> -2
8720ec SifExecModuleBuffer 0x6935 bytes -> started
872188 SifExecModuleBuffer 0xbecd bytes -> started
8d8a68 fioGetstat mass:/POPS -> 0
87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> ok
87d350 unpack to 0x200000 -> 0x33ebb9 bytes
8761d8 fioOpen mass:/POPS/GAME.VCD -> ok
87e538 fioOpen mass:/POPS/IGR_BG.TM2 -> -2
87e75c fioOpen mass:/POPS/IGR_NO.TM2 -> -2
87e968 fioOpen mass:/POPS/IGR_YES.TM2 -> -2
87f0d0 fioOpen mass:/POPS/OSD.BIN -> -2
8807d4 fioOpen mass:/POPS/BIOS.BIN -> -2
88114c fioOpen mass:/POPS/TROJAN_{0..9}.BIN -> -2
88249c fioOpen mass:/POPS/PATCH_{0..9}.BIN -> -2
87ee9c fioGetstat mass:/POPS/GAME/ -> 0
87f0d0 fioOpen mass:/POPS/GAME/OSD.BIN -> -2
8807d4 fioOpen mass:/POPS/GAME/BIOS.BIN -> -2
88114c fioOpen mass:/POPS/GAME/TROJAN_{0..9}.BIN -> -2
88249c fioOpen mass:/POPS/GAME/PATCH_{0..9}.BIN -> -2
883840 fioOpen mass:/POPS/CHEATS.TXT -> -2
883840 fioOpen mass:/POPS/GAME/CHEATS.TXT -> -2
8d554c fioOpen mass:/POPS/VMCDIR.TXT -> -2
8d554c fioOpen mass:/POPS/GAME/VMCDIR.TXT -> -2
8d6280 fioOpen mass:/POPS/DISCS.TXT -> -2
8d6280 fioOpen mass:/POPS/GAME/DISCS.TXT -> -2
877834..8788d0 fioOpen mass:/POPS/MODULE_{0..9}.IRX -> -2
8d83c0 fioGetstat mass0:/POPS/GAME -> 0
8d8d2c fioOpen mass0:/POPS/GAME/SLOT0.VMC -> ok
8d8d2c fioOpen mass0:/POPS/GAME/SLOT1.VMC -> ok
879e5c stop
```

### `hdd-folder`: HDD game folder and icons already exist

Model answers are `hdd` plus an existing `pfs1:/POPS/GAME/` with `icon.sys`
and `list.ico`. State `(0,0,0,0,0,"",1)`; no writes; deliberate `stop`.
LauncHER uses the image folder for the game folder and has no icon creation
step (quirks 92–93).

```text
8713d8 fioOpen rom0:PSXVER -> -2
871418 SifIopReset 'rom0:UDNL '
871470 SifIopReset 'rom0:UDNL '
871a3c SifLoadModule rom0:SIO2MAN -> loaded
871a88 SifLoadModule rom0:MCMAN -> loaded
871ae4 SifExecModuleBuffer 0x2a25 bytes -> started
871b34 SifExecModuleBuffer 0x23b1 bytes -> started
871b8c SifExecModuleBuffer 0xecd bytes -> started
871bdc SifExecModuleBuffer 0x3389 bytes -> started
871c2c SifExecModuleBuffer 0x3159 bytes -> started
871c7c SifExecModuleBuffer 0x7a91 bytes -> started
871ccc SifExecModuleBuffer 0xcd55 bytes -> started
8d801c fileXioDevctl pfs: 0x5003 -> 0
8d8028 fileXioUmount pfs0: -> -2
8d8034 fileXioUmount pfs1: -> -2
8d8b40 fileXioUmount pfs1: -> -2
8d8b6c fileXioMount pfs1: = hdd0:__common -> 0
8d7eac fileXioGetStat pfs1:/POPS/ -> 0
8d7fa8 fileXioChStat pfs1:/POPS/ -> 0
8d7fbc fileXioChStat pfs1:/POPS/ -> 0
87dad8 fileXioOpen pfs1:/POPS/POPS.ELF -> ok
87df88 fileXioOpen pfs1:/POPS/IOPRP252.IMG -> ok
875bec fileXioUmount pfs0: -> -2
875c20 fileXioMount pfs0: = hdd0:__.POPS -> 0
875c98 fileXioOpen pfs0:GAME.VCD -> ok
87e4f8 fileXioOpen pfs1:/POPS/IGR_BG.TM2 -> -2
87e71c fileXioOpen pfs1:/POPS/IGR_NO.TM2 -> -2
87e928 fileXioOpen pfs1:/POPS/IGR_YES.TM2 -> -2
87f0b8 fileXioOpen pfs1:/POPS/OSD.BIN -> -2
8807bc fileXioOpen pfs1:/POPS/BIOS.BIN -> -2
881134 fileXioOpen pfs1:/POPS/TROJAN_{0..9}.BIN -> -2
882484 fileXioOpen pfs1:/POPS/PATCH_{0..9}.BIN -> -2
8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> 0
8d7fa8 fileXioChStat pfs1:/POPS/GAME/ -> 0
8d7fbc fileXioChStat pfs1:/POPS/GAME/ -> 0
87f0b8 fileXioOpen pfs1:/POPS/GAME/OSD.BIN -> -2
8807bc fileXioOpen pfs1:/POPS/GAME/BIOS.BIN -> -2
881134 fileXioOpen pfs1:/POPS/GAME/TROJAN_{0..9}.BIN -> -2
882484 fileXioOpen pfs1:/POPS/GAME/PATCH_{0..9}.BIN -> -2
883828 fileXioOpen pfs1:/POPS/CHEATS.TXT -> -2
883828 fileXioOpen pfs1:/POPS/GAME/CHEATS.TXT -> -2
8d5534 fileXioOpen pfs1:/POPS/VMCDIR.TXT -> -2
8d5534 fileXioOpen pfs1:/POPS/GAME/VMCDIR.TXT -> -2
8d6268 fileXioOpen pfs1:/POPS/DISCS.TXT -> -2
8d6268 fileXioOpen pfs1:/POPS/GAME/DISCS.TXT -> -2
8777f4..878890 fileXioOpen pfs1:/POPS/MODULE_{0..9}.IRX -> -2
8d878c fileXioGetStat pfs1:/POPS/GAME/ -> 0
8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> 0
8d7fa8 fileXioChStat pfs1:/POPS/GAME/ -> 0
8d7fbc fileXioChStat pfs1:/POPS/GAME/ -> 0
8d87e4 fileXioOpen pfs1:/POPS/GAME/icon.sys -> ok
8d8860 fileXioOpen pfs1:/POPS/GAME/list.ico -> ok
8d801c fileXioDevctl pfs: 0x5003 -> 0
8d8028 fileXioUmount pfs0: -> 0
8d8034 fileXioUmount pfs1: -> 0
879e5c stop
```

### `usb-pops4`: image only in `mass:/POPS4`

Model answers: base `mass:/POPS/GAME.VCD` and `POPS0..3` miss, `POPS4` hits;
`mass:/POPS4/GAME` already exists; both cards are created there. State
`(3,1,0,0,1,"4",1)`; writes are the two `mass:/POPS4/GAME/SLOTn.VMC` files,
`0x20000` bytes each; deliberate `stop`. LauncHER has no numbered folder and
therefore none of this suffix-driven file selection (quirks 87 and 94–95).

```text
8713d8 fioOpen rom0:PSXVER -> -2
871418 SifIopReset 'rom0:UDNL '
871470 SifIopReset 'rom0:UDNL '
871a3c SifLoadModule rom0:SIO2MAN -> loaded
871a88 SifLoadModule rom0:MCMAN -> loaded
871d6c fioOpen mc0:/POPSTARTER/usbd.irx -> -2
871e28 fioOpen mc1:/POPSTARTER/usbd.irx -> -2
871f20 fioOpen mc0:/POPSTARTER/usbhdfsd.irx -> -2
871fdc fioOpen mc1:/POPSTARTER/usbhdfsd.irx -> -2
8720ec SifExecModuleBuffer 0x6935 bytes -> started
872188 SifExecModuleBuffer 0xbecd bytes -> started
8d8a68 fioGetstat mass:/POPS -> 0
87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> ok
87d350 unpack to 0x200000 -> 0x33ebb9 bytes
8761d8 fioOpen mass:/POPS/GAME.VCD -> -2
876354 fioOpen mass:/POPS{0..3}/GAME.VCD -> -2
876354 fioOpen mass:/POPS4/GAME.VCD -> ok
87e538 fioOpen mass:/POPS/IGR_BG.TM2 -> -2
87e75c fioOpen mass:/POPS/IGR_NO.TM2 -> -2
87e968 fioOpen mass:/POPS/IGR_YES.TM2 -> -2
87f0d0 fioOpen mass:/POPS4/OSD.BIN -> -2
8807d4 fioOpen mass:/POPS4/BIOS.BIN -> -2
88114c fioOpen mass:/POPS4/TROJAN_{0..9}.BIN -> -2
88249c fioOpen mass:/POPS4/PATCH_{0..9}.BIN -> -2
87ee9c fioGetstat mass:/POPS4/GAME/ -> 0
87f0d0 fioOpen mass:/POPS4/GAME/OSD.BIN -> -2
8807d4 fioOpen mass:/POPS4/GAME/BIOS.BIN -> -2
88114c fioOpen mass:/POPS4/GAME/TROJAN_{0..9}.BIN -> -2
88249c fioOpen mass:/POPS4/GAME/PATCH_{0..9}.BIN -> -2
883840 fioOpen mass:/POPS4/CHEATS.TXT -> -2
883840 fioOpen mass:/POPS4/GAME/CHEATS.TXT -> -2
8d554c fioOpen mass:/POPS4/VMCDIR.TXT -> -2
8d554c fioOpen mass:/POPS4/GAME/VMCDIR.TXT -> -2
8d6280 fioOpen mass:/POPS4/DISCS.TXT -> -2
8d6280 fioOpen mass:/POPS4/GAME/DISCS.TXT -> -2
877834..8788d0 fioOpen mass:/POPS/MODULE_{0..9}.IRX -> -2
8d83c0 fioGetstat mass0:/POPS4/GAME -> 0
8d8d2c fioOpen mass0:/POPS4/GAME/SLOT0.VMC -> -2
8d8d2c fioOpen mass0:/POPS4/GAME/SLOT0.VMC [create] -> ok
8d8d9c fioWrite mass:/POPS4/GAME/SLOT0.VMC -> 0x20000 bytes
8d8d2c fioOpen mass0:/POPS4/GAME/SLOT1.VMC -> -2
8d8d2c fioOpen mass0:/POPS4/GAME/SLOT1.VMC [create] -> ok
8d8d9c fioWrite mass:/POPS4/GAME/SLOT1.VMC -> 0x20000 bytes
879e5c stop
```

### `usb-no-vcd`: all eleven USB locations miss, no PS1 disc

Model answers: valid IOX package, every `U(GAME)` open returns `-2`, disc
type 0. State `(3,1,0,1,0,"",1)`; no writes; fatal `0x876a0c`. LauncHER
returns `-ENOENT` after its different candidate list instead of performing
this drive fallback (quirks 87 and 97).

```text
8761d8 fioOpen mass:/POPS/GAME.VCD -> -2
876354 fioOpen mass:/POPS{0..9}/GAME.VCD -> -2
8767d4 sceCdGetDiskType (0, 0) -> 0
876a0c fatal
```

### `hdd-pops3`: image only in `__.POPS3`, with `__.POPS2` absent

Model answers: `__common` mounts; base, `__.POPS0` and `__.POPS1` mount but
miss; `__.POPS2` mount fails; `__.POPS3` mount succeeds and hits. State
`(0,0,0,0,0,"",1)`; the usual two HDD icon writes; deliberate `stop`.
LauncHER never enumerates these partitions (quirk 87) and does not use the
`__common` game folder or create its icons (92–93).

```text
8d8b6c fileXioMount pfs1: = hdd0:__common -> 0
875c20 fileXioMount pfs0: = hdd0:__.POPS -> 0
875c98 fileXioOpen pfs0:GAME.VCD -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS0 -> 0
875ea0 fileXioOpen pfs0:GAME.VCD -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS1 -> 0
875ea0 fileXioOpen pfs0:GAME.VCD -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS2 -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS3 -> 0
875ea0 fileXioOpen pfs0:GAME.VCD -> ok
8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> -2
8d7ed4 fileXioMkdir pfs1:/POPS/GAME/ -> 0
8d7ee4 fileXioGetStat pfs1:/POPS/GAME/ -> 0
8d7f10 fileXioChStat pfs1:/POPS/GAME/ -> 0
8d7f24 fileXioChStat pfs1:/POPS/GAME/ -> 0
8d878c fileXioGetStat pfs1:/POPS/GAME/ -> 0
8d7eac fileXioGetStat pfs1:/POPS/GAME/ -> 0
8d7fa8 fileXioChStat pfs1:/POPS/GAME/ -> 0
8d7fbc fileXioChStat pfs1:/POPS/GAME/ -> 0
8d87e4 fileXioOpen pfs1:/POPS/GAME/icon.sys -> -2
8d8808 fileXioOpen pfs1:/POPS/GAME/icon.sys [create] -> ok
8d8828 fileXioWrite hdd0:__common:pfs:/POPS/GAME/icon.sys -> 0x3c4 bytes
8d8860 fileXioOpen pfs1:/POPS/GAME/list.ico -> -2
8d8884 fileXioOpen pfs1:/POPS/GAME/list.ico [create] -> ok
8d88a0 fileXioWrite hdd0:__common:pfs:/POPS/GAME/list.ico -> 0x8158 bytes
879e5c stop
```

### `hdd-no-vcd`: all eleven HDD locations miss

Model answers: every base/numbered partition mounts and every `GAME.VCD`
open misses; disc type 0. State `(0,0,0,1,0,"",1)`; no writes; fatal
`0x876a0c`. LauncHER has no partition retry or physical-disc fallback
(quirks 87 and 97).

```text
8d8b6c fileXioMount pfs1: = hdd0:__common -> 0
875c20 fileXioMount pfs0: = hdd0:__.POPS -> 0
875c98 fileXioOpen pfs0:GAME.VCD -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS0 -> 0
875ea0 fileXioOpen pfs0:GAME.VCD -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS1 -> 0
875ea0 fileXioOpen pfs0:GAME.VCD -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS2 -> 0
875ea0 fileXioOpen pfs0:GAME.VCD -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS3 -> 0
875ea0 fileXioOpen pfs0:GAME.VCD -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS4 -> 0
875ea0 fileXioOpen pfs0:GAME.VCD -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS5 -> 0
875ea0 fileXioOpen pfs0:GAME.VCD -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS6 -> 0
875ea0 fileXioOpen pfs0:GAME.VCD -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS7 -> 0
875ea0 fileXioOpen pfs0:GAME.VCD -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS8 -> 0
875ea0 fileXioOpen pfs0:GAME.VCD -> -2
875e28 fileXioMount pfs0: = hdd0:__.POPS9 -> 0
875ea0 fileXioOpen pfs0:GAME.VCD -> -2
8767d4 sceCdGetDiskType (0, 0) -> 0
876a0c fatal
```

### `hdd-pp-no-vcd`: single-partition image missing

Model answers: `__common` and `PP.GAME` mount, `IMAGE0.VCD` misses, disc type
0. State `(2,0,0,1,0,"",1)`; no writes; fatal `0x876a0c`. There is no
partition retry. LauncHER never tries `IMAGE0.VCD` and returns `-ENOENT`
instead of the disc fallback (quirks 87 and 97).

```text
8d8b6c fileXioMount pfs1: = hdd0:__common -> 0
875684 fileXioMount pfs0: = hdd0:PP.GAME -> 0
8756f4 fileXioOpen pfs0:IMAGE0.VCD -> -2
8767d4 sceCdGetDiskType (0, 0) -> 0
876a0c fatal
```

### `usb-disc`: no VCD, drive reports type `0x10`

Model answers: all USB image opens miss; disc status/type calls succeed with
type `0x10`; sector reads and syncs return the pinned model values. State
`(3,1,0,1,0,"",1)`; two card writes; deliberate `stop`. LauncHER returns
`-ENOENT` and does not launch through this branch (quirk 97).

```text
8761d8 fioOpen mass:/POPS/GAME.VCD -> -2
876354 fioOpen mass:/POPS{0..9}/GAME.VCD -> -2
8767a8 sceCdInit (1, 0) -> 1
8767b0 sceCdSync (0, 0) -> 0
8767b8 sceCdStatus (0, 0) -> 0
8767d4 sceCdGetDiskType (0, 0) -> 16
876838 sceCdSync (0, 0) -> 0
876840 sceCdDiskReady (0, 0) -> 2
876848 sceCdSync (0, 0) -> 0
876860 sceCdRead (4, 1) -> 0
876868 sceCdSync (0, 1) -> 0
8ff26c sceCdSync (0, 0) -> 0
8ff274 sceCdDiskReady (0, 0) -> 2
8ff27c sceCdSync (0, 0) -> 0
8ff294 sceCdRead (16, 1) -> 0
8ff29c sceCdSync (0, 1) -> 0
8ff2dc sceCdSync (0, 0) -> 0
8ff2e4 sceCdDiskReady (0, 0) -> 2
8ff2ec sceCdSync (0, 0) -> 0
8ff304 sceCdRead (22, 1) -> 0
8ff30c sceCdSync (0, 1) -> 0
87ee9c fioGetstat mass:/POPS/GAME/ -> -2
8774d4 sceCdInit (5, 0) -> 1
8d83c0 fioGetstat mass0:/POPS/GAME -> -2
8d83d4 fioMkdir mass0:/POPS/GAME -> 0
8d8d2c fioOpen mass0:/POPS/GAME/SLOT0.VMC -> -2
8d8d2c fioOpen mass0:/POPS/GAME/SLOT0.VMC [create] -> ok
8d8d9c fioWrite mass:/POPS/GAME/SLOT0.VMC -> 0x20000 bytes
8d8d2c fioOpen mass0:/POPS/GAME/SLOT1.VMC -> -2
8d8d2c fioOpen mass0:/POPS/GAME/SLOT1.VMC [create] -> ok
8d8d9c fioWrite mass:/POPS/GAME/SLOT1.VMC -> 0x20000 bytes
879e5c stop
```

### `usb-tray`: drive status 1

Model answer: `sceCdStatus` returns 1. State `(3,1,0,1,0,"",1)`; no writes;
fatal `0x876a38`. LauncHER has no corresponding physical-disc branch
(quirk 97).

```text
8767a8 sceCdInit (1, 0) -> 1
8767b0 sceCdSync (0, 0) -> 0
8767b8 sceCdStatus (0, 0) -> 1
876a38 fatal
```

### `usb-no-pops-folder`: missing base POPS folder

Model answers: both external USB drivers miss; `mass:/POPS` stat misses and
`mass0:/POPS` mkdir succeeds. State `(0,1,0,0,0,"",1)`; no writes; fatal
`0x8740a0`. LauncHER does not create this folder and ends a package failure
with its own message (quirk 96); its native candidate difference is quirk 87.

```text
871d6c fioOpen mc0:/POPSTARTER/usbd.irx -> -2
871e28 fioOpen mc1:/POPSTARTER/usbd.irx -> -2
871f20 fioOpen mc0:/POPSTARTER/usbhdfsd.irx -> -2
871fdc fioOpen mc1:/POPSTARTER/usbhdfsd.irx -> -2
8d8a68 fioGetstat mass:/POPS -> -2
8d8a7c fioMkdir mass0:/POPS -> 0
8740a0 fatal
```

### `hdd-no-common`: `__common` mount fails

Model answer: `hdd0:__common` mount returns `-2`. State
`(0,0,0,0,0,"",1)`; no writes; fatal `0x873f88`. LauncHER has no
`__common` mapping in its launcher C sources (quirk 92).

```text
8d8b6c fileXioMount pfs1: = hdd0:__common -> -2
873f88 fatal
```

### `hdd-no-pops-folder`: missing `__common` POPS folder

Model answers: `__common` mounts, `pfs1:/POPS/` stat misses, mkdir and the
following stat/chstat calls succeed. State `(0,0,0,0,0,"",1)`; no writes;
fatal `0x8740a0`. LauncHER has neither this exact folder creation nor the
original failure branch (quirks 92 and 96).

```text
8d8b6c fileXioMount pfs1: = hdd0:__common -> 0
8d7eac fileXioGetStat pfs1:/POPS/ -> -2
8d7ed4 fileXioMkdir pfs1:/POPS/ -> 0
8d7ee4 fileXioGetStat pfs1:/POPS/ -> 0
8d7f10 fileXioChStat pfs1:/POPS/ -> 0
8d7f24 fileXioChStat pfs1:/POPS/ -> 0
8740a0 fatal
```

### `smb-no-config`: no SMBCONFIG.DAT on either card

Model answers: IPCONFIG is absent and both SMBCONFIG opens miss. State
`(0,1,3,0,0,"",0)`; no writes; fatal `0x8727d4`. The native resolver still
returns its seven share/mass/HDD candidates; it does not model this startup
branch. Current production network-file locations/connect behavior remain a
separate difference (quirks 87 and 99), not parity.

```text
8722c0 fioOpen mc0:/POPSTARTER/IPCONFIG.DAT -> -2
872380 fioOpen mc1:/POPSTARTER/IPCONFIG.DAT -> -2
87263c fioOpen mc0:/POPSTARTER/SMBCONFIG.DAT -> -2
8726fc fioOpen mc1:/POPSTARTER/SMBCONFIG.DAT -> -2
8727d4 fatal
```

### `smb-bad-config`: malformed first SMBCONFIG line

Model answer: `mc0:` IPCONFIG/`mc1:` IPCONFIG miss; `mc0:` SMBCONFIG opens
with synthetic text lacking the required space. State `(0,1,3,0,0,"",0)`;
no writes; fatal `0x872c7c`. The original branch is measured; launcHER's
candidate resolver does not implement it and its startup/config sequence is
quirks 87 and 99.

```text
8722c0 fioOpen mc0:/POPSTARTER/IPCONFIG.DAT -> -2
872380 fioOpen mc1:/POPSTARTER/IPCONFIG.DAT -> -2
87263c fioOpen mc0:/POPSTARTER/SMBCONFIG.DAT -> ok
872c7c fatal
```

### `smb-no-iox`: only the older POPS.PAK is on the share

Model answers: full SMB stack and LOGON/ECHO/OPENSHARE succeed;
`POPS_IOX.PAK` is absent and `POPS.PAK` alone is not accepted. State
`(0,1,3,0,0,"",0)`; no writes; 119 measured failed opens then fatal
`0x874210`. LauncHER also requires IOX for `SB.`, but searches its larger
package-folder list and does not reproduce this original connect/retry
sequence (quirks 89 and 99).

```text
874140 fileXioDevctl mass0: 0xc0de0002 '192.168.0.2' -> 0
874170 fileXioDevctl mass0: 0xc0de0007 'ALIVE ECHO TEST' -> 0
8741a0 fileXioDevctl mass0: 0xc0de0005 'PS2SMB' -> 0
87421c fioOpen mass:/POPS/POPS_IOX.PAK -> -2 (119 times)
874210 fatal
```

### `smb-no-modules`: required network module absent

Model answers: valid synthetic SMBCONFIG, `poweroff.irx` absent on both
cards. State `(0,1,3,0,0,"",0)`; no writes; fatal `0x873570`. LauncHER uses
its own embedded/network-module arrangement and extra configuration paths;
this is quirk 99, while its resolver list is quirk 87.

```text
8722c0 fioOpen mc0:/POPSTARTER/IPCONFIG.DAT -> -2
872380 fioOpen mc1:/POPSTARTER/IPCONFIG.DAT -> -2
87263c fioOpen mc0:/POPSTARTER/SMBCONFIG.DAT -> ok
873460 fioOpen mc0:/POPSTARTER/poweroff.irx -> -2
8734dc fioOpen mc1:/POPSTARTER/poweroff.irx -> -2
873570 fatal
```

### `usb-pak`: POPS_IOX.PAK missing, POPS.PAK accepted

Model answers: IOX misses, valid POPS.PAK opens and unpacks; GAME.VCD exists.
State `(3,1,0,0,0,"",1)`. Writes: `mass:/POPS/GAME/SLOT0.VMC` and
`mass:/POPS/GAME/SLOT1.VMC`, `0x20000` bytes each; deliberate `stop`.
LauncHER uses the same three package names in that order but searches more
folders and accepts by its own package checks (quirks 89 and 91).

```text
87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> -2
87d5a0 fioOpen mass:/POPS/POPS.PAK -> ok
87d8a0 unpack to 0x200000 -> 0x343a71 bytes
879e5c stop
```

### `usb-elf`: both packs missing, POPS.ELF accepted

Model answers: both packs miss; valid POPS.ELF and IOPRP252.IMG open;
GAME.VCD exists. State `(3,1,0,0,0,"",1)`. Writes:
`mass:/POPS/GAME/SLOT0.VMC` and `mass:/POPS/GAME/SLOT1.VMC`, `0x20000`
bytes each; deliberate `stop`. LauncHER's folder search and package acceptance differ
(quirks 89 and 91); it has no `IOPRP.IMG` fallback (90).

```text
87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> -2
87d5a0 fioOpen mass:/POPS/POPS.PAK -> -2
87db18 fioOpen mass:/POPS/POPS.ELF -> ok
87dfc8 fioOpen mass:/POPS/IOPRP252.IMG -> ok
879e5c stop
```

### `usb-iox-size`: each candidate package is one byte too long

Model answers: zero-filled POPS_IOX.PAK, POPS.PAK and POPS.ELF have sizes
`0xe50b9`, `0xe6241` and `0x30530d` respectively (one above the accepted
`0xe50b8`, `0xe6240`, `0x30530c`). State `(3,1,0,0,0,"",1)`; no writes;
fatal `0x874404`. LauncHER takes the first package that opens under its own
validation rather than this exact-size branch (quirk 91).

```text
87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> ok
87d5a0 fioOpen mass:/POPS/POPS.PAK -> ok
87db18 fioOpen mass:/POPS/POPS.ELF -> ok
874404 fatal
```

### `usb-elf-no-ioprp`: POPS.ELF has no IOP image

Model answers: both packs miss, valid POPS.ELF opens, both IOPRP names miss.
State `(3,1,0,0,0,"",1)`; no writes; fatal `0x874404`. LauncHER searches
only `IOPRP252.IMG`, so its second-name rule differs even though this
particular missing-both outcome also fails (quirk 90).

```text
87d00c fioOpen mass:/POPS/POPS_IOX.PAK -> -2
87d5a0 fioOpen mass:/POPS/POPS.PAK -> -2
87db18 fioOpen mass:/POPS/POPS.ELF -> ok
87dfc8 fioOpen mass:/POPS/IOPRP252.IMG -> -2
87e06c fioOpen mass:/POPS/IOPRP.IMG -> -2
874404 fatal
```

### `hdd-no-package`: HDD packs are not candidates

Model answers: valid POPS_IOX.PAK and POPS.PAK are present under
`hdd0:__common:pfs:/POPS`, but POPS.ELF is absent. State
`(0,0,0,0,0,"",1)`; no writes; fatal `0x874404`. The packs are never opened.
LauncHER instead runs its three-step probe in each of its search folders,
none of which is the original `__common` package folder (quirk 88).

```text
87dad8 fileXioOpen pfs1:/POPS/POPS.ELF -> -2
874404 fatal
```

### `hdd-ioprp-img`: second IOP image name succeeds

Model answers: valid POPS.ELF, IOPRP252.IMG misses, valid IOPRP.IMG opens;
GAME.VCD exists. State `(0,0,0,0,0,"",1)`. Writes:
`hdd0:__common:pfs:/POPS/GAME/icon.sys` (`0x3c4` bytes) and
`hdd0:__common:pfs:/POPS/GAME/list.ico` (`0x8158` bytes); deliberate `stop`.
LauncHER has no `IOPRP.IMG` fallback (quirk 90), and its
HDD folder/icon behavior differs (92–93).

```text
87dad8 fileXioOpen pfs1:/POPS/POPS.ELF -> ok
87df88 fileXioOpen pfs1:/POPS/IOPRP252.IMG -> -2
87e02c fileXioOpen pfs1:/POPS/IOPRP.IMG -> ok
879e5c stop
```

### `hdd-ioprp-zero`: plausible-size IOP image with wrong content

Model answers: valid POPS.ELF and zero-filled IOPRP252.IMG of plausible size
open; content validation rejects the image. State `(0,0,0,0,0,"",1)`; no
writes; fatal `0x874404`. This is the content-check half of quirk 91;
launcHER's package validation is not the original routine.

```text
87dad8 fileXioOpen pfs1:/POPS/POPS.ELF -> ok
87df88 fileXioOpen pfs1:/POPS/IOPRP252.IMG -> ok
874404 fatal
```

### `hdd-elf-zero`: plausible-size POPS.ELF with wrong content

Model answers: zero-filled POPS.ELF of size `0x30530c` opens with valid
IOPRP252.IMG present; content validation rejects POPS.ELF before an IOPRP
open appears in this focused summary. State `(0,0,0,0,0,"",1)`; no writes;
fatal `0x874404`. LauncHER uses a different acceptance rule (quirk 91).

```text
87dad8 fileXioOpen pfs1:/POPS/POPS.ELF -> ok
874404 fatal
```

### `usb-72`: 72-character USB title accepted

Model answers: valid IOX package and a VCD whose basename is exactly 72
`T` characters. State `(3,1,0,0,0,"",1)`. Writes:
`mass:/POPS/<T×72>/SLOT0.VMC` and `mass:/POPS/<T×72>/SLOT1.VMC`,
`0x20000` bytes each; deliberate `stop`. The summary below writes `T×72` as a length notation,
not as literal user text. LauncHER silently cuts this title to 63 characters
and therefore asks for another file (quirk 98).

```text
8761d8 fioOpen mass:/POPS/<T×72>.VCD -> ok
879e5c stop
```

### `usb-73`: 73-character USB title rejected before image search

Model answer: title basename is exactly 73 `T` characters; the otherwise
valid IOX/VCD model does not get as far as a VCD open. State
`(3,1,0,0,0,"",1)`; no writes; fatal `0x875aa8` (“Please shorten”).
LauncHER silently truncates to 63 instead of taking this branch (quirk 98).

```text
875aa8 fatal
```

### `hdd-72`: 72-character HDD title accepted

Model answers: valid HDD POPS.ELF/IOPRP252.IMG and a base-partition VCD with
a 72-`T` basename. State `(0,0,0,0,0,"",1)`. Writes:
`hdd0:__common:pfs:/POPS/<T×72>/icon.sys` (`0x3c4` bytes) and
`hdd0:__common:pfs:/POPS/<T×72>/list.ico` (`0x8158` bytes); deliberate `stop`.
LauncHER truncates to
63 characters and uses a different per-game folder (quirks 92 and 98).

```text
875c98 fileXioOpen pfs0:<T×72>.VCD -> ok
879e5c stop
```

### `hdd-73`: 73-character HDD title rejected before image search

Model answer: title basename is exactly 73 `T` characters; valid HDD package
inputs do not get as far as a VCD open. State `(0,0,0,0,0,"",1)`; no writes;
fatal `0x875aa8`. LauncHER silently truncates instead (quirk 98).

```text
875aa8 fatal
```

## 5. Difference register: quirks 86–99

The quirks file carries the follow-on actions. This table is the complete
measured mapping from that register to the forms/cases above. Repeated file
names are grouped by behavior class rather than assigned separate quirks.

| Quirk | Behavior class and original evidence | Measured current launcHER rule |
|---|---|---|
| 86 | **Argument recognition and dispatch.** The 40 forms in section 2 measure prefix separator/placement/case, type 1 and 2 partition selection, extension failures, `cdrom` and `argc == 0`. | Native accepts mixed-case and bare prefixes, treats type-1 names as titles, sends uppercase `:PATINFO` to generic handling before POPS, and builds candidates where the original stops or exits. Main's `cdrom` handler is OSDM-only; zero arguments normalize to `-1`. |
| 87 | **Image candidate construction and retries.** `U`, `H`, `P` in section 1; `usb-no-vcd`, `hdd-pops3`, `hdd-no-vcd`, `hdd-pp-no-vcd` and every form's `at` result. | No `POPS0..9`, `__.POPS0..9` or `IMAGE0.VCD`; adds `IMAGE.VCD`, ELF folders, `pfs0:`, other devices and title-derived partition paths. Full four-kind native lists are in section 3. |
| 88 | **POPS package on an HDD launch.** Original opens only `hdd0:__common:pfs:/POPS/POPS.ELF` with IOPRP252.IMG or IOPRP.IMG; `hdd-no-package` proves the two packs are not asked for even when present. | Runs the same three-name probe in each folder of its own list, which has no `__common` entry; source pins `hdd0:__.POPS:pfs:/` and the absence of `__common`. |
| 89 | **POPS package on a USB launch.** `usb-elf` measures only `mass:/POPS`, in order POPS_IOX.PAK, POPS.PAK, POPS.ELF; `smb-no-iox` measures the SB IOX requirement. | Same name order, but up to twelve folders: image folder first, memory cards before `mass:/POPS`, additional HDD/USB folders and the test folder. The SB `requireIox` rule is shared; its folder/retry sequence is not. |
| 90 | **IOPRP.IMG as the second name of the IOP image.** `hdd-ioprp-img` opens IOPRP252.IMG, then IOPRP.IMG in the same folder; `usb-elf-no-ioprp` measures both missing. | Source constructs only `%sIOPRP252.IMG`; no `%sIOPRP.IMG` fallback. |
| 91 | **package accepted by exact size and content.** `usb-iox-size` opens and passes over files one byte above `0xe50b8`, `0xe6240`, `0x30530c`; `hdd-ioprp-zero` and `hdd-elf-zero` reject plausible-size wrong content; no usable package is fatal at `0x874404`. | The first file that opens is considered under launcHER's own package validation. None of the three original exact-size constants appears in `handler_pops.c`; this is not the original acceptance routine. |
| 92 | **per-game folder on HDD.** `hdd`, `hdd-folder`, `hdd-pops3`, `hdd-no-pops-folder` and `hdd-no-common` measure `hdd0:__common:pfs:/POPS/<title>/` wherever the image is, including mkdir/stat/chstat and mount failures. | Uses `<image folder>/<title>/`, normally `hdd0:__.POPS:pfs:/<title>/` for a plain name. No launcher C source names `__common`. Exact `__common` mapping is selected for later implementation, not present now. |
| 93 | **icon.sys and list.ico in the HDD game folder.** `hdd` writes `0x3c4` and `0x8158` bytes when absent; `hdd-folder` leaves existing files alone. | No `icon.sys` or `list.ico` staging step in `handler_pops.c`. |
| 94 | **numbered folder moves the per-game files.** `usb-pops4` moves OSD.BIN, BIOS.BIN, TROJAN/PATCH, CHEATS.TXT, VMCDIR.TXT, DISCS.TXT, the game folder and both cards to `mass:/POPS4`; IGR skin and MODULE_n.IRX stay in `mass:/POPS`. | Resolver contains only `mass0:/POPS/%s.VCD`; no `POPS0..9` construction and no suffix-driven per-game relocation. |
| 95 | **memory cards on USB and SMB.** `usb`, `smb`, `usb-folder` and `usb-pops4` use only `<POPS folder>/<title>/SLOT0.VMC` and `SLOT1.VMC`, creating the folder and two `0x20000`-byte files when absent. | Also accepts `<title>.VMC0/.VMC1`, a `<serial>` folder and cards beside the image; creation/naming therefore differs outside the usual layout. |
| 96 | **missing POPS folder.** `usb-no-pops-folder` and `hdd-no-pops-folder` create `mass:/POPS` or `hdd0:__common:pfs:/POPS`, then stop at `0x8740a0`. | Does not create the original POPS folder; a launch without a package ends with launcHER's own missing-dependencies message. |
| 97 | **no image found.** `usb-no-vcd`, `hdd-no-vcd`, `hdd-pp-no-vcd`, `usb-disc` and `usb-tray` measure the drive probe; types `0x10` to `0x12` are accepted by the original implementation, with `0x10` traced here; type 0 is fatal at `0x876a0c`. | `launchPOPS` returns `-ENOENT` at `POPS: Cannot open target VCD`; no `sceCdGetDiskType` fallback in `handler_pops.c`. The host physical-disc planner elsewhere is not called by this launch. |
| 98 | **name length.** `usb-72`/`hdd-72` use all 72 title characters; `usb-73`/`hdd-73` stop at `0x875aa8` before opening the VCD. | `char baseTitle[64]` cuts titles to 63 characters without a message; titles of 64–73 therefore resolve differently instead of following the original boundary. |
| 99 | **SB startup files, modules and connect sequence.** `smb`, `smb-no-config`, `smb-bad-config`, `smb-no-modules` and `smb-no-iox` measure mc0/mc1 configuration, required external modules, LOGON/ECHO/OPENSHARE, disconnect/reconnect and IOX retry outcomes. | Current production uses its own embedded/network-module arrangement and additional network-config locations. Earlier SMB parser work does not establish equality of this whole startup sequence. Native resolver results in section 2 cover only image candidates. |

For quirk 89, launcHER's exact package directory order in
`findPopsDependenciesForMode` is:

```text
vcdDir
devPops                         (<device>:/POPS/)
mc0:/POPSTARTER/
mc1:/POPSTARTER/
mc0:/POPS/
mc1:/POPS/
hdd0:__.POPS:pfs:/
usb0:/POPS/
usb1:/POPS/
mass:/POPS/
mass0:/POPS/
ata0:/LAUNCHER-TEST-20261013-A/
```

The test folder remains documented current behavior; this branch does not
silently remove it or preserve it as a future default. Later implementation
must match r13 first, bugs included, for POPStarter launches only.

## 6. Coverage boundary and follow-on order

The table covers every fixed or parameterized path requested by the 32
pinned cases and all 40 argument forms. It does not claim a finite row for
every string a user can place in DISCS.TXT, VMCDIR.TXT, SMBCONFIG.DAT or
another input file. Those are represented by the measured construction rule
and directed synthetic examples. It is not an exhaustive fault matrix for
every library call: model answers vary where they change path selection,
fallback or termination. No proprietary reference bytes, real shares, BIOS
images, cards, saves or keys are included.

Follow-on behavior belongs in separately reviewed POPStarter-only branches:
first argument parsing and dispatch (86), then image candidates and length /
failure rules (87 and 98), exact device/POPS-folder mapping including the
owner-approved HDD `__common` layout (88, 92–96), package acceptance and
IOPRP fallback (89–91), physical-disc launch integration (97), and the full
SB startup/connect sequence (99). OSD differences 80–85 remain separate;
quirk 85 now points to this measured folder evidence. None of those
follow-on behavior changes is claimed or implemented by this document.
