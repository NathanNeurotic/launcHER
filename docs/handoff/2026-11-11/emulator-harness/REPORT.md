# PCSX2 tier probe report (2026-11-11) - LEADS TO RE-VERIFY, not truth

`<T>` = this directory. Runner: `<T>/run_tier.py` (kills only its own emulator PID; exit 0 marker seen, 1 fail marker, 2 timeout, 3 setup error). Emulator copy: `<T>/emu` (never run or modify <workspace>/RIPPCSX2 itself; never touch pcsx2 processes started from any other directory, e.g. `run3-9c10dee`).

## Commands (run from `<T>`)

- Underlying emulator command (written to `command.txt` in each run folder):
  `<T>\emu\pcsx2-qtx64-avx2.exe -batch -nogui -fastboot -logfile <run>\emulog.txt -elf <run>\host\launcHER.elf -gameargs ata:/POPS/TEST.VCD`
- Headless boot: `python run_tier.py --elf <launcHER.elf> --timeout 30`
- Tier 1, up to the handoff (EE recompiler, 27-39 s):
  `python run_tier.py --elf <trace build launcHER.elf> --gameargs "ata:/POPS/TEST.VCD" --hdd-image images/hdd_fat32_vmc.img --timeout 120 --marker "Transferring control to trampoline" --fail-marker "[ps2rig] exit=1"`
- Tier 2, POPS entry (EE interpreter, 47-81 s; at cfebe01 exits 1 on `Trap exception at`):
  `python run_tier.py --elf <same> --gameargs "ata:/POPS/TEST.VCD" --hdd-image images/hdd_fat32_vmc.img --timeout 150 --set "EmuCore/CPU/Recompiler:EnableEE=false" --after "Transferring control to trampoline" --marker "Interlaced (FIELD)" --fail-marker "Trap exception at" --fail-marker "[ps2rig] exit=1"`
- Tier 2 with the defect masked (experiment aid): add
  `--pin-after "Rebooting IOP with external image" --pin 206360=dfb10038 --pin 206370=dfb50058 --pin 206380=03e00008 --pin 206390=24020001`
- Control (original POPSTARTER.ELF, same emulator):
  `python run_tier.py --elf control/XX.TEST.ELF --usb-image images/fat32_pak.img --timeout 150 --set "EmuCore/CPU/Recompiler:EnableEE=false"`
- Other runner options: `--dump ADDR:LEN` (EE RAM via PINE on port 28711), `--set SECTION:KEY=VALUE`, `--linger`, `--usb-image`, `--in-place`. `filter_log.sh <emulog>` strips I/O chatter.
- Fixtures: VCD from the tonyhax homebrew boot CD (`make_vcd.py`), FAT32 image via `make_fat_image.sh` in an alpine container; `images/hdd_fat32_vmc.img` = same image plus preloaded `POPS/TEST/SLOT0.VMC`, `SLOT1.VMC` (creating VMCs on the emulated ATA disk is flaky: -5 in 1 of 12 runs; keep `EECycleRate=0`).
- The trace build used: `build-pr23-trace/release/launcHER.elf` (prints the BDM:/IOP:/POPS: trace); the release build prints almost nothing.
- Only ONE emulator run at a time (single PINE port, shared emu directory).

## Measured

1. Storage: launcHER has no `host:` device. USB msd mounts and runs through patching and the Sony IOP reboot, then fails: `IOP: loaded ata_bd id=-200 start=0`, `ERROR: Failed to initialize module ata_bd: -200`, `POPS: Failed initializing services: -200` (init.c loads `ata_bd` for `Device_USB` but not `ps2dev9`; tolerated before the reset, non-tolerant in `initPopsServices` after it). `ata:/POPS/TEST.VCD` on a raw MBR+FAT32 image attached as the DEV9 HDD works.
2. EE recompiler: reaches `POPS: Transferring control to trampoline at 0x00084000`; ~65 ms later `TLB Miss, pc=0x0 addr=0x0 [load]`, `R5900 Exception: Jump to unaligned address (PC: 0x00440017)`. RAM at that moment (two runs identical): 0x100000-0x200000 all zero, core copy to 0x200000 complete only up to offset 0x90230 -> dies during the trampoline copy loop, before FlushCache/ExecPS2. Kernel handler nodes still point into zeroed launcHER code: 0x80018e70 holds 0x00135800 (`TimerHandler_callback`), 0x80018ed0 holds 0x0012c070 (`_SifCmdIntHandler`), both with gp 0x203670.
3. EE interpreter: Sony POPS starts (`# Restart Without Memory Clear.`, `SDR driver version 4.0.1`, TOC lines, `A tlb refill handler is set`, `Set GS CRTC configuration. NTSC 640x448 ... Progressive (FRAME)`, `Invalid access(not hardware): epc=00f71b98 bva=1f000084`) then `Trap exception at 0x00206360`; EE dead (`padman: DMA Busy` repeats). The control prints the same `bva=1f000084` line, does not trap, continues to `Pad: DS2 Config Finished`, `gpu: general read !!!gcount=0!!!`, `Set GS CRTC ... Interlaced (FIELD)`.
4. Cause of the trap: four POPS code words overwritten after the copy:

| Address | Staged POPS word | Live word at trap | What the live value is |
|---|---|---|---|
| 0x00206360 | dfb10038 | 00203670 | launcHER `_gp` |
| 0x00206370 | dfb50058 | 00206420 | inside launcHER's libkernel `stack` symbol (0x206040..0x206440) |
| 0x00206380 | 03e00008 | 00206420 | same |
| 0x00206390 | 24020001 | 0012c1c0 | launcHER `ExitThread` |

   Only these four POPS .text words differ from the staged core at the trap; the control's are pristine. A pin run saw them hold the POPS values after the copy, then be overwritten ~40-100 ms later. With them restored there is no trap (twice): POPS goes on to `Pad: DS2 Config Finished`, `Invalid access(not hardware): epc=00f7bccc bva=1f000004`, `Set GS CRTC ... Interlaced (FIELD)`, then quiet. The kernel thread table after ExecPS2 still has an entry with stack 0x206040, size 0x400.
5. Symbols in build-pr23-trace/launcher/launcher.elf (lead re-checked with nm): `_ftext` 0x100000, `topThread` 0x12aa38, `_SifCmdIntHandler` 0x12c070, `ExitThread` 0x12c1c0, `TimerHandler_callback` 0x135800, `_fbss` 0x1fb700, `_gp` 0x203670, `stack` 0x206040 (BSS), `_end` 0x211e60.

## INFERRED (unproven)

- ExecPS2 in the BIOS kernel resets launcHER's leftover ps2sdk helper thread (`topThread`) and rewrites its initial gp/sp/fp/ra into that thread's stack, which now lies inside the POPS image. POPStarter is unaffected because it lives above 0x870000.
- Because this is real SCPH-39001 kernel code, the same overwrite would happen on hardware.
- The recompiler crash mid-copy fits an interrupt entering zeroed launcHER code (cause not proven).
- Untested fix ideas: terminate/delete other threads before the handoff; keep launcHER thread stacks outside 0x200000..0x870000; ExecPS2 into the trampoline first so the kernel's thread reset happens before the core copy; disable interrupts or remove timer/SIF handlers before the trampoline.

## Not verified / side observations

- No screenshot taken: "PS1 picture is up" is not established.
- After the pinned run's pad config it diverges from the control (no `gpu: general read`, `bva=1f000004` 30 ms after pad config vs ~5 s) - control used POPSTARTER with PAK files on USB, not like for like.
- `POPS: Matched title in DB: Test Drive 4 (SLES-00948)` for a disc whose detected serial is `TONYHAX.EXE`.
- `POPS: Disc region 3 (licence at 0xlx)` has an unexpanded format specifier.
- `Opcode pass changed 10200 instructions`; docs/POPSTARTER_OPCODE_PASS.md says 10,210.
