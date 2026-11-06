# POPStarter r13's XX. USB driver pair

Measured on the original (POPSTARTER.ELF MAIN, external input, gp
`0x9b68f0`) on 2026-11-02 by reading its code. launcHER copies it on
POPStarter launches only: the code is in the POPS handler and runs only for
`XX.` titles, so Ember and every other launch path are untouched. Nothing
here was tested on a console.

Background: Okeanos86's UDPFS Assault / BDM-UDPFS Assault notes (summarised
in REPOP `docs/OKEANOS_ASSAULT_ELFWD.md` §1-3) report that POPStarter loads
`usbd.irx` twice, around its IOP reset, and "refuses to start" without
`usbhdfsd.irx`. The code confirms the first and explains the second.

## When it runs

The title's file name prefix decides (`0x8718d8..0x8719a8`): `XX.` or `xx.`
sets `gp+0x3448 = 1`, `gp+0x3888 = 0`. (`SB.`/`sb.` sets `0x3888 = 3`, the
SMB path, which skips all of this.) launcHER's `pops_get_active_xx_launch()`
is the same gate.

## Before the IOP reset (`0x871d24..0x8721c4`)

For `usbd.irx`, then `usbhdfsd.irx`:

1. Open `mc0:/POPSTARTER/<name>`; only if that open fails, open
   `mc1:/POPSTARTER/<name>`. Lower-case names, these two paths only.
2. Size under 12 bytes: absent. If this was the mc0: file, mc1: is not
   tried (quirk 28).
3. Otherwise read the whole file into EE RAM and clear the built-in copy.
4. Start it (`0x91c248`, no arguments): the file if one was read, else the
   original's built-in `usbd` (FreeUsbd 0.1.2) / `usbhdfsd`. A start
   returning `<= 0` goes to the fatal exit `0x8709f8`.

There is no check that the two files come as a pair. A card with an
external `usbd.irx` but no `usbhdfsd.irx` starts the built-in `usbhdfsd`
on top of it; if that cannot link to the external driver (a UDPFS or BDM
"usbd.irx" exports no USBD library), the start fails and POPStarter exits.
That is the "refuses to start" users see (quirk 29).

## After the IOP reset (`0x87ac64..0x87ade8`)

The same two buffers (file or built-in) are started again, in the same
order, with the same fatal check. The card is not read again.

## launcHER

- `pops_xx_usb_read()` (`common/src/launch_args.c`): steps 1-3, per file.
- `pops_start_xx_usb()` (`launcher/src/handler_pops.c`): before the reset,
  the buffered files; after `initPopsServices`, the buffered files again,
  with launcHER's built-in `usbd_mini` / `usbmass_bd_mini` standing in for a
  missing one, usbd first. Any start returning `<= 0` stops the launch.
- With either file present, `initPopsServices` no longer loads the two
  built-in USB modules itself, so the order is the original's.
- `usbd.irx` / `usbhdfsd.irx` are no longer searched in the other BDMA
  folders or spellings (`USBD.IRX`, `<VCD dir>/IRX/`, `mc?:/POPS/`): the
  original reads only the two paths above. `usbd_bd_assault.irx` and the
  other BDMA roles are launcHER's own and stay as they were.

## Known differences

- Before the reset launcHER's own USB stack is already running (it read the
  VCD with it), so the pre-reset start of an external file lands on an IOP
  that already has `usbd_mini` / `bdm`. The original's pre-reset IOP had only
  its own modules. Expected (not run): a classic `usbd.irx` then fails to
  register its library and unloads with a positive ID, which is not fatal.
- After the reset launcHER's IOP still has a card manager, so `mc0:` is
  readable there (Okeanos's notes: in the original it is not). Recorded in
  REPOP's write-up as an intentional difference.
- Not copied: the original also accepts the pair already placed in EE RAM
  at `0x140000` (`usbd`) and `0x180000` (`usbhdfsd`) as ELF images, and
  skips the pre-reset start when either holds the word `"NULL"`. Nothing
  launches launcHER that way; not read in full.
- The original frees the `usbd` buffer after the post-reset start but then
  tests the already-cleared `usbd` size to decide whether to free the
  `usbhdfsd` one, so it never frees it. Memory only; launcHER frees both.

## Verification

- `tools/test_launch_args.py`: the read rules (paths, order, 12-byte rule,
  mc0: stub hiding mc1:, other spellings ignored).
- `tools/test_pops_external.py`: the starts are before `SifIopRebootBuffer`
  and after `initPopsServices`, both gated on `XX.`, fatal on `<= 0`.
