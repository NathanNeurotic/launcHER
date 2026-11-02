# POPStarter r13's `MODULE_0..9.IRX`

Measured on the original (POPSTARTER.ELF MAIN, external input, gp
`0x9b68f0`) on 2026-11-02 by reading its code, and copied into launcHER for
POPStarter launches (`launchPOPS`). Ember launches never reach this code.
Nothing here was tested on a console.

`tools/test_pops_module_irx.py` checks launcHER against the original's own
instructions when `POPSTARTER_TEST_ELF` is set: the name table, the pokes,
the start arguments and the start order.

## 1. Reading, before the IOP reset (`0x8777c4..`, one block per slot)

For n = 0..9, from the game device's `POPS` folder only:

- HDD (`gp+0x3448 == 0`): `pfs1:/POPS/MODULE_n.IRX` through fileXio.
- `mass:` launches (`gp+0x3448 == 1`): `mass:/POPS/MODULE_n.IRX`.
- Size under 17 bytes (`slti 0x11`): ignored. Otherwise read whole into a
  heap buffer of `2 * size` bytes; the read's result is not checked. A
  failed open prints a message and goes on.

**launcHER:** reads `MODULE_n.IRX` from the folder its POPS files
(`POPS_IOX.PAK`, `POPS.PAK` or `POPS.ELF`) were found in, which is the
`POPS` folder of the game's device in the normal layouts. The same size
rule, no read check. The buffer is `2 * size` bytes, or enough to cover the
name if that is larger, and zeroed (see quirk 34).

## 2. Name check, still before the reset (`FUN_008d7024`)

For each buffered module, the IOP module name at file offset `0x8e` is
compared (ps2sdk `.iopmod` at `0x74`, name at `+0x1a`). It is an else-if
chain of prefix compares with no terminator check; the first match wins.
A match removes POPS's own start of the same embedded module with the same
two pokes as `$KILL_PADMAN` (call word = 0, high half of the following
word = `0x1000`):

| Name (prefix) | POPS call site poked | Flag |
|---|---|---|
| `sio2man` | `0x200324` / `0x20032e` | `gp+0x3814` |
| `padman` | `0x200358` / `0x200362` | `gp+0x3824` |
| `Sound_Device_Library` (libsd) | `0x200388` / `0x200392` | none |
| `sdr_driver` | `0x2003b8` / `0x2003c2` | none |
| `dev9` | `0x2003f0` / `0x2003fa` | `gp+0x3418` |
| `atad` | `0x200420` / `0x20042a` | `gp+0x38b4` |
| `hdd` | `0x200450` / `0x20045a` | `gp+0x388c` |
| `pfs` | `0x200480` / `0x20048a` | `gp+0x3874` |
| `IOX/File_Manager` (iomanX) | none | `gp+0x38ac` |
| `IOX/File_Manager_Rpc` (fileXio) | none, never matches (quirk 33) | `gp+0x3440` |
| `Poweroff_Handler` | none | `gp+0x3428` |

Only `0x3814` and `0x3824` are loaded again anywhere in MAIN (the test
checks that no `lw` of the others exists), so launcHER keeps only those two.

**launcHER:** `pops_module_irx_name_apply()` (common/src/pops_modes_patches.c),
the same table in the same order, on the staged core next to the
`$LOAD_PADMAN` pokes.

## 3. After the reset

- If no module was named `sio2man` and at least one was read, POPStarter
  starts POPS's embedded sio2man itself (`0x2cbbc0`, `0x19a0` bytes).
  **launcHER** always starts POPS's sio2man itself (`0x1999` bytes) because
  its memory card and MMCE services need it; that predates this work and is
  unchanged. A user module named `sio2man` still has its name check and is
  still started in its slot.
- `$LOAD_PADMAN` starts padman_hsync only while no module was named
  `padman` (`gp+0x3824`). **Copied.**
- Then the `XX.` USB pair, and for `SB.` launches iomanx/filexio.
- `MODULE_0..4` start from their buffers in slot order (`0x87afa0..`), fatal
  on an ID `<= 0`, then each buffer is cleared.
- For `SB.` launches the network stack starts here (`0x87b5f4..`, gated on
  `gp+0x3888 == 3`).
- `MODULE_5..9` start the same way (`0x87b9dc..`). Without `SB.` the ten
  starts run back to back (quirk 35).
- Arguments by name, three bytes compared: `hdd...` gets `-o 8 -n 128`
  (12 bytes at `0x9aef50`), `pfs...` gets `-m 8 -o 8 -n 127` (17 bytes at
  `0x9aef60`), everything else none.

**launcHER:** `pops_start_module_irx(0, 4)` after the `XX.` USB pair (and
launcHER's own `XX.` BDMA drivers), then its SMB stack for `SB.`/SMB
launches, then `pops_start_module_irx(5, 9)`; fatal on an ID `<= 0`; the
same arguments (`pops_module_irx_args`).

## What changed for users

Before, launcHER searched `MODULE_n.IRX` in the VMC folder, the VCD folder,
`<VCD folder>/IRX/`, `mc?:/POPSTARTER/` and `mc?:/POPS/`, started each by
path with no name check and ignored failed starts. Those extra folders are
gone; a module now has to sit next to the POPS files, as under POPStarter,
and a module that fails to start stops the launch, as under POPStarter.

launcHER's own named peripheral drivers (`USBMOUSE.IRX` ... `SIO2MAN.IRX`)
and its `MODULES.TXT` / `IRX.TXT` manifests are launcHER-only extras that
the original does not have. They are still loaded, after `MODULE_9`, and
are listed in the PR as the next thing to decide.
