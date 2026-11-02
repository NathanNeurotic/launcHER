# POPStarter r13's `MODULE_0..9.IRX` (research; not yet copied)

Measured on the original (POPSTARTER.ELF MAIN, external input, gp
`0x9b68f0`) on 2026-11-02 by reading its code. launcHER does not do this
yet: its `pops_load_custom_modules()` searches other folders, uses
`SifLoadModule` by path and never looks at module names. This note is the
plan for copying it. Nothing here was tested on a console.

## 1. Reading, before the IOP reset (`0x8777c4..`, one block per slot)

For n = 0..9, from the game device's `POPS` folder only:

- HDD (`gp+0x3448 == 0`): `pfs1:/POPS/MODULE_n.IRX` through fileXio
  (`0x916758` open, `0x916c08` lseek, `0x9169b0` read, `0x916878` close).
- `mass:` launches (`gp+0x3448 == 1`, i.e. `XX.`/`SB.` style): `mass:/POPS/MODULE_n.IRX`
  through the EE file calls (`0x87c390` open, `0x87c460` lseek,
  `0x87c420` read, `0x87c3f0` close).
- Size under 17 bytes (`slti 0x11`): ignored. Otherwise read whole into a
  heap buffer (`malloc(2*size)`). Slot n's buffer/size live at
  `fp+0x1124+4n` / `fp+0x1174+4n`. A failed open just prints a message.

## 2. Name check, still before the reset (`0x879e9c..`, `FUN_008d7024`)

For each buffered module, the IOP module name at file offset `0x8e`
(ps2sdk `.iopmod`: 0x74 + 0x1a) is compared. A match removes POPS's own
start of the same embedded module from the core, with the same two pokes
as `$KILL_PADMAN` (call word = 0, high half of the following `bgezl` =
`0x1000`):

| Name | POPS call site poked | Flag set |
|---|---|---|
| `sio2man` | `0x200324` / `0x20032e` | `gp+0x3814` |
| `padman` | `0x200358` / `0x200362` | `gp+0x3824` (skips `$LOAD_PADMAN`) |
| `Sound_Device_Library` (libsd) | `0x200388` / `0x200392` | none |
| `sdr_driver` | `0x2003b8` / `0x2003c2` | none |
| `dev9` | `0x2003f0` / `0x2003fa` | `gp+0x3418` |
| `atad` | `0x200420` / `0x20042a` | `gp+0x38b4` |
| `hdd` | `0x200450` / `0x20045a` | `gp+0x388c` |
| `pfs` | `0x200480` / `0x20048a` | `gp+0x3874` |
| `IOX/File_Manager` (iomanX) | none | `gp+0x38ac` |
| `IOX/File_Manager_Rpc` (fileXio) | none | `gp+0x3440` |
| `Poweroff_Handler` | none | `gp+0x3428` |

Only `0x3814` and `0x3824` are read anywhere afterwards (no `lw` of the
others was found); the rest appear unused.

## 3. After the reset (`0x87aa84..0x87b???`)

- If no module was named `sio2man` and at least one `MODULE_n.IRX` was
  read, POPStarter starts POPS's embedded sio2man itself (`0x2cbbc0`,
  `0x19a0` bytes) and pokes its call site away (`0x200324`/`0x20032e`);
  fatal on failure. (launcHER always does this, with `0x1999` bytes.)
- Then `$LOAD_PADMAN` / `$KILL_PADMAN` (see POPSTARTER_PADMAN.md).
- Later (`0x87afa0..`), each buffered module in slot order is started from
  its buffer (`0x91c248`), fatal on an ID `<= 0`, then the buffer is
  cleared. Arguments by name: `hdd` gets `-o 8 -n 128` (12 bytes at
  `0x9aef50`), `pfs` gets `-m 8 -o 8 -n 127` (17 bytes at `0x9aef60`),
  everything else none.

## Open before copying

- Where launcHER's "POPS folder" is per device (the folder its
  `POPS_IOX.PAK` came from is the natural equivalent of `mass:/POPS/` and
  `pfs1:/POPS/`), and what the original does for SMB/UDPFS.
- What to do with launcHER's own extra module sources (VMC/VCD folders,
  `IRX/`, `mc?:/POPSTARTER/`, named peripheral drivers, `MODULES.TXT` /
  `IRX.TXT`), which the original does not have. Under the parity rule they
  go; that changes behaviour for anyone using them, so it needs the owner's
  call.
- The exact position of the module starts relative to the `XX.` USB pair
  and the network stack (read `0x87ade8..0x87af84`).
