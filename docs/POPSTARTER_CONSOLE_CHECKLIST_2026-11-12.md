# PR 23 console checklist — 2026-11-12

**UNTESTED on a console. Every expected result below is a test oracle, not a
claim that the build works or is safe.** A real POPS launch removes ps2link;
a rig `hang` after that reset is not a pass or a failure. The owner must be
present to reset the PS2.

## Build and evidence

Source commit: `800d91e398830573335a6c1d43b74af0dc78da2e` (PR 23).
The earlier baseline was `412c11b5dc9e7f96c651f55498ef8a1ccf304cc6`.

| Build | File | SHA-256 |
| --- | --- | --- |
| Release | `build-pr23-osd-merge-release/release/launcHER.elf` | `c2fb1e1d32102c2746dec227093661a33a29922743a0f3082e2695467ff1952a` |
| Trace (`LAUNCHER_BOOT_TRACE=ON`, `DEBUG=ON`) | `build-pr23-osd-merge-trace/release/launcHER.elf` | `45c4788f3d42be033f27f041eaea93891a90ead8255c2270967e7d11265ec09f` |

Both container builds printed `handoff layout: OK` and
`version=800d91e39883`. The files are 333,988 and 338,148 bytes.
The baseline `ata_bd: -200` reproduction and the fixed PCSX2 evidence are in
[handoff/2026-11-12/usb-pops-services.md](handoff/2026-11-12/usb-pops-services.md).

Use the trace ELF for diagnosis and the release ELF for the final repeat of a
passing case. For every case, preserve the serial/GS output up to the Sony IOP
reset and a timestamped photo or video of the final screen. Preserve any
`popfs_trace.log` produced on the throwaway device. Keep these logs and images
outside the repository.

Use a fresh test folder and fresh dedicated VMC files. These examples use
`ata0:/PR23-20261112/TEKKEN.VCD` and `mass:/POPS/PR23USB.VCD`; record the real
mounted device if it differs. Do not open, rename, format, or overwrite an
existing card or save. Put a one-command file at
`<VCD folder>/<game base>/CHEATS.TXT`; with no command, that file must be
absent. Use the owner's existing lawful POPS dependencies and games; distribute
none of them.

## Ordered checks

1. **Smallest first test — Tekken from ATA, no commands.**
   Launch `ata0:/PR23-20261112/TEKKEN.VCD` with no per-game `CHEATS.TXT`.
   Expected: Tekken reaches gameplay and controller input works. Failure:
   launch error, trap, black screen, hang before gameplay, or dead controls.
   Save the trace and final screen. Repeat once with the release ELF.

2. **Tekken from ATA with `$ORIGINAL_OPCODES`.**
   Put `$ORIGINAL_OPCODES` in `TEKKEN/CHEATS.TXT` and repeat step 1.
   Expected: the same playable result. Failure: a regression that was absent
   without the command, a launch error, trap, hang, or dead controls. Save the
   config and both logs for comparison.

3. **Tekken from USB, no commands — service fix acceptance.**
   Launch `mass:/POPS/PR23USB.VCD` with no per-game `CHEATS.TXT`.
   The baseline `412c11b` failed with `ata_bd: -200` and failed POPS services;
   `3778466` removes that module from the USB-only Sony service load.
   Expected: Tekken reaches gameplay and controller input works. Failure:
   `ata_bd: -200`, another module/service error, trap, black screen, hang, or
   dead controls. Save the trace and final screen. PCSX2 acceptance used
   EE+IOP interpreters; the separate IOP-recompiler `psxUNK` observation is
   not a console result.

4. **Tekken from USB with `$ORIGINAL_OPCODES`.**
   Put `$ORIGINAL_OPCODES` in `PR23USB/CHEATS.TXT` and repeat step 3.
   Expected: the same playable result as step 3. Failure: `ata_bd: -200`, a
   regression that was absent without the command, another service error,
   trap, hang, or dead controls. Save both configs and logs.

5. **Reset combo without `$RESET_WARMBOOT`.**
   Start Tekken from ATA with no commands. In gameplay hold exactly
   SELECT+L2+R2+CROSS on controller 1, with no other button held.
   Expected: the PS1 reset path uses the normal BIOS entry (`0xbfc00000`) and
   the PS1 starts again. Failure: no reset, a hang/crash, or a return to
   launcHER. This is not launcHER's direct IGR exit; do not count a launcher
   return as success. Save the final screen and trace.

6. **Reset combo with `$RESET_WARMBOOT`.**
   Put `$RESET_WARMBOOT` in `TEKKEN/CHEATS.TXT`, repeat step 5, and compare
   with POPStarter r13 using the same game and command.
   Expected: the rewritten SystemErrorExit/warm-boot path runs, including
   r13's recorded target quirk; the result matches r13, not an assumed ideal
   reset. Failure: no reset, a hang/crash, a launcher return, or a result that
   differs from r13. Save both final screens and both traces.

7. **`$NOVMC0`: slot 1 hidden, slot 2 saves.**
   Use only the fresh dedicated pair
   `ata0:/PR23-20261112/TEKKEN/SLOT0.VMC` and
   `ata0:/PR23-20261112/TEKKEN/SLOT1.VMC`, with `$NOVMC0` in
   `TEKKEN/CHEATS.TXT`. Allow the launch to prepare those backing files as it
   normally would. Start Tekken, inspect its card screen, save to slot 2,
   then relaunch with the same files and reload that save.
   Expected: slot 1 is absent **from Tekken's card screen**; slot 2 is
   present and the save/reload works. Both backing files may remain:
   `$NOVMC0` hides card 0 from the game, it does not delete `SLOT0.VMC`.
   Failure: slot 1 appears in game, slot 2 is absent, save/reload fails, any
   card error, or `SLOT0.VMC` is deleted to fake the result. Record the VMC
   paths and keep the dedicated files; never substitute an owner's card.

8. **A LibCrypt title on the built-in list.**
   Candidate first: an owned Vagrant Story (`SLES-02754`) at
   `ata0:/PR23-20261112/VAGRANT.VCD`, with no per-game `CHEATS.TXT`. Before
   launch, the local host fingerprint lookup must confirm a built-in entry
   containing a LibCrypt write; record its serial and expected entry id. If
   it does not, substitute another owned LibCrypt title that meets this
   precondition and record its actual ATA path—the disc is then wrong for
   this check, not a failing product result.
   Expected: boot trace shows `POPS: Built-in entry <id>` with that id, and
   the game gets past its protection. Do not require a separate LibCrypt log
   indication: the ordinary 21-byte write has no dedicated trace line.
   Failure: no matching entry, a different id, a protection stop, or a launch
   crash. Save the serial/id metadata, boot trace, and final screen.

9. **A loaded TROJAN-fixed game.**
   Use Jade Cocoon - Story of the Tamamayu (USA) at
   `ata0:/PR23-20261112/JADE.VCD`, with its existing file at
   `ata0:/PR23-20261112/JADE/TROJAN_0.BIN` and no per-game `CHEATS.TXT`.
   The current host classifier placed this file in the 367-file loaded
   class; keep it unchanged.
   Expected: the launch does not print `NOT loaded by launcHER`, the TROJAN
   slots install, and the game reaches the same working point as under
   POPStarter r13 with the fix. Failure: a skip line, slot-install error,
   launch crash, or behaviour that differs from r13. Save the TROJAN trace and
   final screen.

Report each case as **not run**, **pass (real PS2)**, or **fail (real PS2)**,
with the exact commit, ELF hash, device, config, final boundary, and log path.
Do not turn a host, build, or PCSX2 result into a console result.
