# POPStarter r13 feature inventory (2026-10-30)

What "100% POPStarter" means, measured against the original binary rather than
against wikis or memory. Ground truth is POPSLoader's
`bin/POPSLDR/PROFILES/MAIN/POPSTARTER.ELF` (sha256 `734c813e…`), unpacked by
`tools/trace_original_pops_io.py:decode_main` to a 1,350,828-byte image at EE
`0x870000`. `tools/popstarter_r13_commands.py` reproduces the command table
below from that file (metadata only; needs capstone).

**Nothing in this document has been run on a console. Every row marked
PRESENT is NOT TESTED unless the Evidence column says otherwise.**

Status key: **PRESENT** (launcHER does what the original does), **PARTIAL**
(some of it, or an equivalent), **MISSING**, **BLOCKED** (needs POPStarter's
own resident code, see below).

## Why some commands are BLOCKED

At launch the original copies two blocks of its own code into the POPS image
(`0x738` bytes to `0x232790`, `0xd60` bytes to `0x238a90`) and keeps more
resident at `0x143xxxx`. Several commands only set flags or install jumps into
that code: `$480p` (jump to `0x2394f0`), `$SET_TIMINGS`, `$D2LS(_ALT)`,
`$NOPAD0/1`, `$PAD01ID_0X`, the `0x232c90` flag of `$NOVMC0`, `$WIDESCREEN`,
`$ULTRA_WIDESCREEN`, `$EYEFINITY`, `$RECOMPILER_ADDON_3/4` and `$FAKELC`
(copies 0x15 bytes from the original's image). Copying that code would ship
POPStarter itself, so these need an independent resident implementation
first (the "resident stub" item under Remaining work).

## CHEATS.TXT commands

| Command | Original effect | launcHER |
|---|---|---|
| `$Cxxxxxxx`, `$8/3/1/2/D0..D3/E0/E1` codes, `$S…`, `$T…` | resident cheat engine | **PARTIAL**: codes parse; no resident engine runs during POPS |
| `$SMOOTH` | `0x21af88=0xa21a22a0341a0001` (64-bit) | **PRESENT**: guarded, original-command differential; no console run |
| `$DX_n $DY_n $MAGH_n $MAGV_n $DW_n $DH_n` | display registers via resident code | **MISSING** |
| `$480p` | flags + `0x21af94=0x50`, `0x23acb0/0x23ad0c=li a0,0`, jump into resident code | **BLOCKED**; parsed, disables European auto PAL as in the original, no core writes |
| `$LEFTADJ_` | `1..255`: `0x21a0a4=0x64a50f00 + ((4096-n)&255)`, `0x21a0a8=0xfc450000` | **PRESENT**: guarded, original-command differential; no console run |
| `$SCANLINES` | `0x21e454=0x22b50006` | **PRESENT** |
| `$VCDID_n` | selects a built-in per-game DB entry | **MISSING** |
| `$SUBCDSTATUS` | `0x20e850/0x20e86c/0x20e87c` | **PRESENT** |
| `$RESET_WARMBOOT` | flag in the original's own exit path | **MISSING** |
| `$MUTE_CDDA` / `$UNDO_MUTE_CDDA` | `0x20f0b6`, `0x20ebf2`, `0x20f0e0` | **PRESENT** |
| `$MUTE_VAB` | five SPU sites | **PRESENT** |
| `$MUTE_ALL` | `0x213ff4=0` | **PRESENT** |
| `$CODECACHE_ADDON_0/1/2` | `0x202734` | **PRESENT** |
| `$RECOMPILER_ADDON_0/1/2` | calls into the original | **MISSING** |
| `$RECOMPILER_ADDON_3/4` | jumps into resident code | **BLOCKED** |
| `$ORIGINAL_OPCODES` | flag | **MISSING** |
| `$UNDO_COMPATIBILITY_CODES`, `$UNDO_GAME_FIXES`, `$UNDO_LIBCRYPT_FIX` | restore sites the built-in DB patched | **MISSING** (no built-in DB to undo) |
| `$WIDESCREEN`, `$ULTRA_WIDESCREEN`, `$EYEFINITY` | GTE hooks into resident code | **BLOCKED**; the old invented `0x205B00` patch is removed |
| `$ROLLBACK` | restores 10 breakpoint sites | **PRESENT** |
| `$SET_TIMINGS` | writes inside the copied code | **BLOCKED** |
| `$BREAKPOINT0/1` | exception hook | **MISSING** |
| `$NOVMC0` | flag at `0x232c90` | **PARTIAL**: launcHER uses the original's other VMC-off helper (FUN_008dc12c slot 1, `0x2007b4=0`) |
| `$NOVMC1` | flag + `0x20d0e0=li a0,0` | **PRESENT** (the core write) |
| `$NOPAD0/1`, `$D2LS`, `$D2LS_ALT`, `$PAD01ID_0X` | resident pad code | **BLOCKED** |
| `$IGR0..$IGR5` | combo masks `0x404f/0x900/0x90f` at `0x228a20/0x228a50`; 3..5 jump to `0x20c08c` | **PRESENT** (was: `$IGR0` meant "IGR off") |
| `$NOIGR` | `0x228a56=0x1000` + pristine `0x228a5c/60` | **PRESENT** |
| no IGR command | POPS default | **PARTIAL**: launcHER's own direct exit stays the default; the user confirmed it on Tekken |
| `$NOPAL` | stops European auto PAL | **PRESENT**; `$PAL2NTSC`/`$FORCENTSC` are now aliases |
| `$FORCEPAL` | PAL patch + region letter `E` | **PRESENT**; was invented values |
| `$XPOS_n`, `$YPOS_n`, `$DWSTRETCH_n`, `$DWCROP_n` | unsigned decimal immediate fields plus store suppression; X/Y first valid command wins | **PRESENT**: guarded, original-command differential; X/Y 0..65535 (up to 5 digits), width commands 0..9999 (up to 4 digits); no console run |
| `$CACHE1` | `0x20fff4`, `0x210120`, `0x2101ac` | **PRESENT** |
| `$FAKELC` | copies LibCrypt code from the original | **BLOCKED** |
| `$SAFEMODE`, `$SAFEMODE2`, `$NOSAFEMODE` | cheat-engine timing | **MISSING** (no resident engine) |
| `$HDTVFIX` / `$NOHDTVFIX` | `0x23acb0/0x23ad0c` = `li a0,1` / pristine | **PRESENT**; `$HDTVFIX` was writing an invented site |
| `$LOAD_PADMAN`, `$KILL_PADMAN` | IOP module choice | **MISSING** |
| `$USBDELAY_n` | config byte `0x100017` | **PARTIAL** (parsed) |
| `$COMPATIBILITY_0x01..0x07` | FUN_008dc2c4 modes | **PRESENT** (Mode 8 has no branch in the original either) |

Removed because the original has no such command and the patches were
invented: `$480i $576p $576i $240p $VMODE_n` (core writes at `0x2061A0/0x2061E0`),
`$DITHER_OFF/$NODITHER` (NOP at `0x205D58`), `$FASTMIPS/$SLOWMIPS` (NOP at
`0x2010A0`) and the `$NOBOOT` "BIOS shell" byte at `0x210cf8`, which is inside
the LibCrypt routine (the original's `$UNDO_LIBCRYPT_FIX` restores
`0x2442ffff` there). They still parse, so old files load, but they write
nothing. `$NOBOOT` keeps only the real `0x2525b0=0x1bfc` OSD write.

## Region and video (0x879034..0x8795f0)

The original reads 4 bytes at VCD offset `0x102514`: the licence text in
sector 4 (`Euro`, `Amer`, `of A`, `Inc.`). POPS itself runs NTSC; the "to PAL"
patch (FUN_008dc218: `0x21af94=3`, `0x502770=0xa6300`, `0x23b018=0x6b`,
`0x23b01c=0x2cb`, the same values a PATCH file's PAL action writes) is applied
to European discs unless `$NOPAL`/`$480p`, and for `$FORCEPAL`. It also writes
region letters at `0x2cbb72` (E/A/J/T), `0x20f6cc` (E/A/I) and the PS1 BIOS
region check at `0x2649a0` (`li a0,'E'/'A'/'I'`, or four zeroed checks for an
unknown disc). The BIOS write is skipped only when a user BIOS/OSD file was
loaded.

launcHER before this change auto-applied the PAL values to every US/Japanese
disc on an NTSC console (labelled "PAL2NTSC"), wrote no region letters, and
had no European auto PAL. `pops_apply_region` now follows the original, after
the fix files so a PATCH file's disable-auto still wins. **NOT TESTED.**

## Launcher, file and device features

| Original feature (from its banners and paths) | launcHER |
|---|---|
| POPS_IOX.PAK / POPS.PAK / POPS.ELF + IOPRP252.IMG / IOPRP.IMG | **PRESENT** (hash-pinned core) |
| Partition launch (`PP.`/`__.`, PATINFO, `pfs:`), USB, SMB, old/new launchers | **PARTIAL**: per device, see `POPS_PARITY_AUDIT_2026-10-28.md` |
| SMB config from `mc?:/POPSTARTER/` (SMBCONFIG.DAT, IPCONFIG.DAT, IRX set) | **PARTIAL**: launcHER's own network config |
| LAUNCHER.ELF / EXECUTE.ELF must be renamed (messages) | **MISSING** (cosmetic) |
| VMC directory relinker (VMCDIR.TXT), SLOT0/1.VMC | **PRESENT** |
| DISCS.TXT disc swap, D-pad assignment, lid emulation | **PARTIAL**: discs map; no resident swap during play |
| CHEATS.TXT / PATCHES.TXT / per-title config locations | **PRESENT** (parsing) |
| TROJAN_n.BIN / PATCH_n.BIN, all games and per game | **PARTIAL**: payload/modes/PAL/disable-auto stage; video actions 6/7 reject atomically until independent resident code exists |
| IGR menu skin (IGR_BG/NO/YES.TM2) | **MISSING** |
| Replacement OSD image | **MISSING** |
| User BIOS.BIN with integrity check | **MISSING** |
| MODULE_0..9.IRX resident modules | **PARTIAL** (see audit) |
| Physical PS1 disc boot | **MISSING** |
| Built-in per-game DB (LibCrypt list, breakpoint killer, compat modes, VMC1-off for some titles) | **PARTIAL**: launcHER's own compat DB, not the original's table |
| padman_hsync | **MISSING** |

## Remaining work, in order

1. Hardware check of this change: a US disc and a European disc on an NTSC
   console, plus `$FORCEPAL` and `$NOPAL` (picture rate and colour).
2. An independent resident stub in free POPS memory, so the BLOCKED commands
   (pads, `$480p`, widescreen, timings) and the cheat engine can run.
3. Recover the remaining resident display-register commands (`$DX/$DY`,
   `$MAGH/$MAGV`, `$DW/$DH`), `$PAD01ID` and built-in per-game DB at `0x8e00d0`.
   The six direct display commands now have a bounded original differential;
   see [display contracts](POPS_DISPLAY_CONTRACTS.md).
4. IGR skin, OSD replacement, BIOS.BIN and physical disc boot.
