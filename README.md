
<p align="center">

<img width="873" height="348" alt="launcHER" src="https://github.com/user-attachments/assets/e54f9ad4-c40b-483a-acaa-2accb5aa55cc" />

<img width="400" height="92" alt="AI-Assisted-Software-Lovers-Only" src="https://github.com/user-attachments/assets/71335775-9fe3-4507-ac2c-caa851abb24c" />

</p>

# launcHER

**launcHER is a standalone PlayStation 2 forwarder built to launch [Ember](https://github.com/Gageformer/Ember) and Sony POPS (PlayStation 1) games from supported storage devices while preserving the environment each runtime needs after handoff.**

It is not an OSD replacement, HDD Browser, game manager, KELF installer, or menu system.

It handles two primary boot roles:

1. **Ember Launching:** Finds Ember wherever you keep it, prepares storage drivers, passes Ember the game folder to boot, preserves DEV9 power, and steps aside.
2. **Sony POPS Launching (POPStarter Replacement):** Finds user-supplied Sony POPS packages, mounts the storage device, extracts game serials from ISO9660 volume descriptors, stages runtime compatibility modes and LibCrypt bypasses, and executes `.VCD` disc images directly.

launcHER is derived from the standalone launcher in [pcm720/OSDMenu](https://github.com/pcm720/OSDMenu), adapted for Ember and Sony POPS.

---

## HDD users: read this first

**launcHER does not require a dedicated HDD partition.**

The `__.EMBER` APA partition used in some examples is only an example. It was suggested as a convenient way to give Ember and its games their own space, not because launcHER requires it.

You do **not** need to create `__.EMBER` just to use launcHER.

"HDD" can also mean several completely different storage setups on a PS2. Use the path that matches **where Ember actually lives**:

| Where Ember is stored | launcHER path |
|---|---|
| USB flash drive | `mass?:/EMBER/ember.elf` |
| USB HDD / USB SSD | `mass?:/EMBER/ember.elf` |
| Internal HDD using exFAT | `ata:/EMBER/ember.elf` |
| APA-Jail / mixed APA+exFAT HDD, Ember on the exFAT side | `ata:/EMBER/ember.elf` |
| Internal APA/PFS HDD | `hdd0:<PARTITION>:pfs:/EMBER/ember.elf` |
| APA-Jail HDD, Ember inside a PFS partition | `hdd0:<PARTITION>:pfs:/EMBER/ember.elf` |

```text
Where is Ember?

USB flash drive / USB HDD / USB SSD
└── mass?:/EMBER/ember.elf

Internal HDD — exFAT
└── ata:/EMBER/ember.elf

Internal HDD — APA Jail / mixed APA + exFAT
├── Ember on exFAT side
│   └── ata:/EMBER/ember.elf
│
└── Ember inside a PFS partition
    └── hdd0:<PARTITION>:pfs:/EMBER/ember.elf

Traditional APA/PFS HDD
└── hdd0:<PARTITION>:pfs:/EMBER/ember.elf
```

The important part is simple:

> **Choose the path that matches where Ember actually lives. launcHER does not require you to reorganize your HDD around it.**

---

## What launcHER does

Ember is not launched like an ordinary standalone ELF. It expects information from the application launching it, including the game folder to boot and, for some devices, a usable storage environment that must remain available after the launcher exits.

launcHER handles that handoff.

It can:

- locate `EMBER/ember.elf` on supported storage;
- initialize the correct storage stack;
- pass Ember the requested game folder;
- preserve DEV9 when required;
- preserve an APA/PFS mount when Ember is launched from PFS;
- launch Ember with the argument layout it expects.

For most storage devices, configuration is simple. APA/PFS is the special case because Ember must continue seeing the mounted partition as `pfs0:` after launcHER hands execution over.

---

## Ember layout

Wherever you decide to store Ember, the expected structure is:

```text
EMBER/
├── ember.elf
├── bios.bin
└── games/
    └── <GAME_FOLDER>/
```

Examples:

```text
USB HDD:
mass0:/EMBER/

Internal exFAT HDD:
ata:/EMBER/

APA/PFS partition after mounting:
pfs0:/EMBER/
```

The storage device changes. The Ember folder structure does not.

### Game argument

Pass the **game folder name** underneath `EMBER/games/` for a normal folder launch.

If the game is stored at:

```text
EMBER/games/Soul Blade/
```

then the game argument is:

```text
Soul Blade
```

To choose a specific CUE with an Ember build supporting explicit file selection,
append its filename to that folder in the **same argument**:

```ini
arg=Final Fantasy VII/Final Fantasy VII (Disc 2).cue
```

This selects `EMBER/games/Final Fantasy VII/Final Fantasy VII (Disc 2).cue`.
Use the actual folder and filename, including spaces, without quotes in the CNF.
Replace the folder-only game argument with this value; do not add the CUE on a
second `arg=` line. launcHER forwards the value unchanged and does not interpret
disc numbers or select discs itself. Settings and saves remain in the game folder.
See [Ember's argument interface](https://github.com/Gageformer/Ember#launching-ember-from-homebrew).

The same replacement works in every storage profile. For APA/PFS:

```ini
path=hdd0:__.EMBER:pfs:/EMBER/ember.elf
arg=pfs0:/EMBER/ember.elf
arg=Final Fantasy VII/Final Fantasy VII (Disc 2).cue
arg=-skip_argv0
arg=-dev9=NICHDD
```

Keep the existing ELF-path argument and launcher flags. Only the game argument changes.

Do not include the `games/` prefix, an absolute device path, or a CUE without its folder:

```text
games/Soul Blade
Soul Blade.cue
mass0:/EMBER/games/Soul Blade/
```

For the folder-only Soul Blade example, Ember should ultimately receive:

```text
argv[1] = Soul Blade
```

---

## Quick start

Download the current release and copy:

```text
launcHER.elf
launcHER.CNF
version.txt
```

to the location from which you want to start launcHER. The `version.txt` file is optional at runtime; keep it with the ELF when reporting bugs so the exact build can be identified.

Keep `launcHER.CNF` beside the launcHER ELF. Then edit `launcHER.CNF`, enable the storage profile matching **where Ember is stored**, and replace `<GAME_FOLDER>` with the actual folder name from `EMBER/games/`.

Basic USB example:

```ini
path=mass?:/EMBER/ember.elf
arg=Soul Blade
```

Start `launcHER.elf`.

---

## Quickboot configuration

When launcHER starts without an explicit target passed on its command line, it looks for:

```text
launcHER.CNF
```

in the same directory from which the launcHER ELF itself was started.

The ELF filename does **not** need to be `launcHER.elf`. For example:

```text
Soul Blade.ELF
launcHER.CNF
```

works correctly.

**Started from OPL or RiptOPL's APPS?** Those loaders name every BDM device `mass0:`, `mass1:`, ... whether it is a USB drive, an exFAT internal HDD, MX4SIO or i.Link. launcHER therefore asks the device behind that number which driver it is (the same check RiptOPL makes on its own `massN:` boot) and carries on under that device's own name, exactly as if it had been started as `ata0:/…` or `mx4sio0:/…`. Your `path=` target still starts with only its own device's drivers. (wLaunchELF passes the device's own name, such as `ata0:/`, so it never needed this.)

Lines beginning with `#` are comments.

- `path=` tells launcHER where Ember is located.
- `arg=` specifies arguments used during the Ember handoff.
- `arg=` lines are shared by all active `path=` lines, so profiles requiring different handoff arguments should not be mixed accidentally.

Unless you intentionally want fallback paths that share the same arguments, keep only the profile you are using enabled.

---

## Storage profiles

### USB flash drive / USB HDD / USB SSD

A USB HDD is still a USB mass-storage device. You do not need an HDD-specific configuration simply because the physical device contains a hard disk or SSD.

```ini
path=mass?:/EMBER/ember.elf
arg=<GAME_FOLDER>
```

Example:

```ini
path=mass?:/EMBER/ember.elf
arg=Soul Blade
```

`usb?:` is also supported by the inherited launcher path handling:

```ini
path=usb?:/EMBER/ember.elf
arg=Soul Blade
```

### Internal exFAT HDD

If Ember is stored on the exFAT filesystem of an internal PS2 HDD, use the ATA BDM path:

```ini
path=ata:/EMBER/ember.elf
arg=<GAME_FOLDER>
arg=-dev9=NICHDD
```

Example:

```ini
path=ata:/EMBER/ember.elf
arg=Soul Blade
arg=-dev9=NICHDD
```

There is no APA/PFS partition requirement for this mode.

### APA Jail / mixed APA + exFAT HDD

If your internal HDD contains both APA and exFAT storage, the path depends on **which side contains Ember**.

If Ember is on the exFAT side:

```ini
path=ata:/EMBER/ember.elf
arg=<GAME_FOLDER>
arg=-dev9=NICHDD
```

If Ember is inside one of the APA/PFS partitions, use the APA/PFS configuration below.

The fact that the physical drive also contains APA partitions does not mean Ember must be launched through APA.

### Internal APA / PFS HDD

APA/PFS is the special case. This profile is needed when **Ember itself is stored inside a PFS partition**.

A dedicated partition is **not required**. You may use any suitable PFS partition containing your Ember installation.

`__.EMBER` appears in examples because a dedicated partition can be convenient for organization and free space. It is not a technical requirement.

Example using a partition named `__.EMBER`:

```ini
path=hdd0:__.EMBER:pfs:/EMBER/ember.elf
arg=pfs0:/EMBER/ember.elf
arg=Soul Blade
arg=-skip_argv0
arg=-dev9=NICHDD
```

If Ember instead lives in an existing PFS partition such as `__common`, use that partition name:

```ini
path=hdd0:__common:pfs:/EMBER/ember.elf
arg=pfs0:/EMBER/ember.elf
arg=Soul Blade
arg=-skip_argv0
arg=-dev9=NICHDD
```

Replace the partition name with the partition where **your** `EMBER/` folder actually exists.

### Why APA/PFS looks different

APA/PFS requires two different paths during launch.

launcHER first needs a loader-facing path identifying the APA partition that contains Ember:

```text
hdd0:<PARTITION>:pfs:/EMBER/ember.elf
```

After that partition is mounted, Ember needs to see itself through:

```text
pfs0:/EMBER/ember.elf
```

So this configuration:

```ini
path=hdd0:__.EMBER:pfs:/EMBER/ember.elf
arg=pfs0:/EMBER/ember.elf
arg=Soul Blade
arg=-skip_argv0
arg=-dev9=NICHDD
```

lets launcHER locate Ember through the `hdd0:` target while Ember ultimately receives:

```text
argv[0] = pfs0:/EMBER/ember.elf
argv[1] = Soul Blade
```

`-skip_argv0` removes the loader-facing `hdd0:` target from Ember's final argument list.

`-dev9=NICHDD` keeps the HDD/DEV9 environment active and allows launcHER to preserve the writable `pfs0:` mount through the final handoff.

This lets Ember continue resolving its relative `games/` directory and retain writable access to files it needs after launcHER exits.

---

## Other supported device profiles

### MMCE

```ini
path=mmce?:/EMBER/ember.elf
arg=<GAME_FOLDER>
```

### Memory card

```ini
path=mc?:/EMBER/ember.elf
arg=<GAME_FOLDER>
```

### MX4SIO

```ini
path=mx4sio:/EMBER/ember.elf
arg=<GAME_FOLDER>
```

### i.Link

```ini
path=ilink:/EMBER/ember.elf
arg=<GAME_FOLDER>
```

### UDPBD

```ini
path=udpbd:/EMBER/ember.elf
arg=<GAME_FOLDER>
arg=-dev9=NIC
```

### UDPFS

```ini
path=udpfs:/EMBER/ember.elf
arg=<GAME_FOLDER>
arg=-dev9=NIC
```

Network configuration for UDPBD/UDPFS follows the inherited OSDMenu Launcher implementation and uses:

```text
mc?:/SYS-CONF/IPCONFIG.DAT
```

### SMBv1

```ini
path=smb0:/EMBER/ember.elf
arg=<GAME_FOLDER>
arg=-dev9=NIC
```

The SMB share root contains `EMBER/ember.elf`, `EMBER/bios.bin` and
`EMBER/games/<GAME_FOLDER>/`. The share name belongs in `SMBCONFIG.DAT`,
not in the `smb0:` path. `smb:/` also addresses the same share.

launcHER embeds DEV9, NetMan, the SDK SMAP/TCP-IP stack and an SDK-derived
SMBv1 client. It establishes the session and opens the share itself. It does
not depend on a connection inherited from OPL or loose network IRX files.
Ember receives the mounted filesystem with DEV9 kept powered.

Put `IPCONFIG.DAT` and `SMBCONFIG.DAT` in `mc0:/POPSTARTER/` or
`mc1:/POPSTARTER/`. The fallback directories, in order, are `mc0:/POPS/`,
`mc1:/POPS/`, `mc0:/SYS-CONF/`, and `mc1:/SYS-CONF/`. Each file is searched
independently. Existing RiptOPL POPStarter network settings use this format.

`IPCONFIG.DAT` contains the console's static IP, netmask and gateway:

```text
192.168.1.10 255.255.255.0 192.168.1.1
```

`SMBCONFIG.DAT` contains the server IP and share on its first line, then the
username and password on separate lines. The server port defaults to 445;
an explicit port uses `192.168.1.100:1445`. For a guest share, leave both
credential lines empty. The following values are examples:

```text
192.168.1.100 PS2SMB
example-user
example-password
```

This implementation requires static addressing and a server offering SMBv1.
SMBv2/v3-only servers cannot negotiate with it. Select one network profile
per launch; SMB's TCP/IP stack cannot run alongside the UDP ministack on
the same adapter. UDPFS exposes server files directly; UDPBD exposes a
server block image through the launcher's FatFs driver. They are different
server modes, with different roots.

The transport code has host regression coverage and builds for PS2. Full
Ember playback, network interruption recovery during a game, and save
persistence on physical hardware still need acceptance testing for each
transport. Sony POPS over these backends also depends on the ongoing POPS
runtime work; SMB POPS currently retains the `POPS_IOX.PAK` requirement.

The SMB client includes software developed by Eric Young
(`eay@mincom.oz.au`). Its source, changes and original license notices are
in `launcher/iop/smbman/`; distributed binaries include `SMB-NOTICES.txt`.

---

## OPL APPS layout

launcHER does **not** require its ELF filename to match its CNF filename.

A copy of `launcHER.elf` may be renamed to the game title for OPL while the configuration filename remains constant:

```text
+OPL/
└── APPS/
    └── Soul Blade/
        ├── Soul Blade.ELF   <- renamed copy of launcHER
        └── launcHER.CNF
```

When `Soul Blade.ELF` starts without explicit target arguments, it resolves the directory it was launched from and opens:

```text
<launch directory>/launcHER.CNF
```

The ELF may therefore be named `Soul Blade.ELF`, `Pepsi Man.ELF`, `Final Fantasy VII.ELF`, or anything else. The quickboot configuration remains `launcHER.CNF`.

Explicit `.CNF` or `.CFG` paths passed to launcHER are still honored as supplied.

### Where launcHER lives vs. where Ember lives

These do not need to be the same location.

The directory containing:

```text
launcHER.elf
launcHER.CNF
```

is where the launcher and its configuration live.

The `path=` entry inside `launcHER.CNF` tells launcHER where **Ember** lives.

For example, launcHER itself could be started from an OPL APPS directory while Ember is on the internal exFAT HDD:

```ini
path=ata:/EMBER/ember.elf
arg=Soul Blade
arg=-dev9=NICHDD
```

launcHER and Ember do not need to live beside each other or even on the same device.

---

## Supported launcher transports

The standalone launcHER build enables:

- MMCE
- memory cards
- USB / mass storage, including USB HDDs and SSDs
- internal exFAT HDD / ATA BDM
- APA / PFS HDD
- mixed APA+exFAT / APA-Jail configurations
- MX4SIO
- i.Link
- UDPBD
- UDPFS

The physical device and filesystem are intentionally treated separately.

A **USB HDD** is USB mass storage from launcHER's point of view.

An **internal HDD** may be using ATA BDM/exFAT, APA/PFS, or a mixed layout. Choose the path according to where Ember is stored, not simply according to the word "HDD."

Compilation support does not imply that every transport has been hardware-verified with every Ember version. The APA/PFS Ember handoff documented above is confirmed working.

---

## What you do NOT need

Using launcHER does **not** automatically require:

- a dedicated `__.EMBER` partition;
- a newly created APA partition;
- an APA-formatted HDD;
- OPL or RiptOPL;
- WinHIIP or an HDL-style installed game;
- a KELF installation;
- an HDD Browser installation;
- moving Ember away from an existing supported location.

If Ember is already on a supported device or filesystem, point launcHER at it.

That is the intended design.

---

## Direct arguments

launcHER can also be called directly by another launcher instead of using `launcHER.CNF`.

APA example:

```text
launcHER.elf hdd0:__.EMBER:pfs:/EMBER/ember.elf pfs0:/EMBER/ember.elf "Soul Blade" -skip_argv0 -dev9=NICHDD
```

Again, `__.EMBER` is only the partition used in this example. If Ember lives in `__common`, the loader-facing target can instead be:

```text
hdd0:__common:pfs:/EMBER/ember.elf
```

Global launcHER flags belong at the end of the argument list.

---

## Sony POPS (PlayStation 1) setup

> **Draft status (PR #23):** launcHER's independent POPStarter-r13 replacement work is in progress, not a completed drop-in replacement or a broadly hardware-verified launch mode. When pointed at a `.VCD` disc image, this branch loads user-supplied Sony POPS, mounts storage, applies compatibility patches and LibCrypt handling, and starts the game. Current host and component checks do not establish compatibility across games or devices. See [the current capability inventory](docs/POPSTARTER_R13_INVENTORY.md) for partial and missing features and the exact console-evidence limits.

### External dependencies

launcHER does not distribute Sony's proprietary emulator binaries or PlayStation 1 BIOS images. You must provide clean copies from your own PlayStation 2 installations.

launcHER accepts three dependency formats:

| Format | Required Files | Notes |
|---|---|---|
| **Packed IOX (Recommended)** | `POPS_IOX.PAK` | Compressed POPS core bundled with updated `ioprp2305a`. Best compatibility on modern storage. |
| **Packed Legacy** | `POPS.PAK` | Compressed POPS core bundled with `ioprp252`. Standard POPStarter format. |
| **Loose Files** | `POPS.ELF` + `IOPRP252.IMG` | Uncompressed executable paired with a standalone IOP reboot image. |

### Dependency search locations

When booting a `.VCD` game, launcHER searches for your POPS dependency files in this priority order:

1. The folder holding the active `.VCD` disc (e.g. `mass0:/POPS/`).
2. `<device>:/POPS/` on the storage volume containing the game (e.g. `ata:/POPS/`).
3. Memory Card slot 1: `mc0:/POPS/`.
4. Memory Card slot 2: `mc1:/POPS/`.
5. Internal APA partition: `hdd0:__.POPS:pfs:/`.

Placing `POPS_IOX.PAK` in `mc0:/POPS/` or your main `POPS/` folder allows all games to share one package.

### Game disc preparation

Convert original PlayStation 1 disc dumps (BIN/CUE) to Virtual CD (`.VCD`) format using tools such as **CUE2POPS**. POPS expects raw Mode 2 Form 1 sectors (2,352 bytes per sector).

Keep `.VCD` images directly in `POPS/`. Per-game subfolders are for TROJAN fixes, cheats and virtual memory cards; VCD lookup does not scan those subfolders. Name each per-game folder after its VCD filename without the `.VCD` extension.

Example directory structure:

```text
POPS/
├── POPS_IOX.PAK
├── Crash Bandicoot.VCD
├── Spyro the Dragon.VCD
├── Metal Gear Solid (Disc 1).VCD
├── Metal Gear Solid (Disc 2).VCD
└── Crash Bandicoot/
    ├── TROJAN_0.BIN
    ├── CHEATS.TXT
    ├── SLOT0.VMC
    └── SLOT1.VMC
```

### launcHER.CNF configuration for POPS

Point the `path=` directive directly to your `.VCD` file:

```ini
# USB storage
path=mass?:/POPS/Crash Bandicoot.VCD

# Internal exFAT HDD (ATA BDM)
path=ata:/POPS/Crash Bandicoot.VCD
arg=-dev9=NICHDD

# Internal APA/PFS partition
path=hdd0:__.POPS:pfs:/Crash Bandicoot.VCD
arg=-dev9=NICHDD

# MMCE (Memory Card SD adapter)
path=mmce?:/POPS/Crash Bandicoot.VCD

# MX4SIO
path=mx4sio:/POPS/Crash Bandicoot.VCD

# i.Link (FireWire)
path=ilink:/POPS/Crash Bandicoot.VCD

# UDPBD / UDPFS network streaming
path=udpbd:/POPS/Crash Bandicoot.VCD
arg=-dev9=NIC
```

### Quickboot via POPStarter naming (OPL APPS)

If you launch without a `launcHER.CNF` file, launcHER identifies adjacent game images based on its own filename:

- **Renamed ELF:** Renaming the binary to `Crash Bandicoot.ELF` boots `Crash Bandicoot.VCD` in the same directory.
- **Prefix stripping:** POPStarter prefixes such as `XX.` or `SB.` are stripped automatically. `XX.Crash Bandicoot.ELF` boots `Crash Bandicoot.VCD`.
- **Default name:** If the filename does not match, launcHER checks for `IMAGE.VCD` in the same directory.

### Per-game configuration directives

Place optional configuration files alongside your `.VCD` image or inside its per-game subfolder (for example, `POPS/Crash Bandicoot/` for `POPS/Crash Bandicoot.VCD`). `VMCDIR.TXT` redirects save files only; cheats and TROJAN fixes remain in the original per-game folder (TROJAN files from community packs currently stop the launch; see the fix-files note under the hotkeys below). Multiple directives can share a line (e.g. `$NOPAL $HDTVFIX`). The full list of original POPStarter commands and what launcHER does with each is in [docs/POPSTARTER_R13_INVENTORY.md](docs/POPSTARTER_R13_INVENTORY.md):

- **`PATCHES.TXT` / `MODES.TXT`:** Directives and compatibility modes. These two file names are launcHER's own; POPStarter takes commands from `CHEATS.TXT`, which launcHER also reads.
  - Video: European discs switch to PAL automatically, as in POPStarter. `$NOPAL` (aliases `$PAL2NTSC`, `$FORCENTSC`) keeps them at 60 Hz; `$FORCEPAL` (alias `$NTSC2PAL`) runs any disc in PAL. `$HDTVFIX` / `$NOHDTVFIX`. `$480p` selects launcHER's independent guarded progressive bridge; host and component checks pass, but progressive picture output on a physical console remains unverified.
  - Sound and core: `$SCANLINES`, `$SUBCDSTATUS`, `$MUTE_CDDA`, `$UNDO_MUTE_CDDA`, `$MUTE_VAB`, `$MUTE_ALL`, `$CODECACHE_ADDON_0`..`2`, `$ROLLBACK`, `$CACHE1`.
  - Undo commands (not yet tested on a console): `$UNDO_COMPATIBILITY_CODES`, `$UNDO_GAME_FIXES`, `$UNDO_LIBCRYPT_FIX` make POPStarter's writes. All three keep the PS1 BIOS boot logo; `$UNDO_COMPATIBILITY_CODES` also cancels `$SUBCDSTATUS`. They run before `$COMPATIBILITY_0x`, so a compatibility mode you set still applies.
  - IGR: `$IGR0`..`$IGR5` (POPStarter's combo choices; 3 to 5 exit straight away) and `$NOIGR`. Without one, launcHER's direct exit is used.
  - Widescreen (not yet tested on a console): `$WIDESCREEN` (16:9), `$ULTRA_WIDESCREEN` (about 21:9), `$EYEFINITY` (three 16:9 screens). They squeeze 3D geometry horizontally, as in POPStarter; set the TV to stretch. The last one listed wins.
  - Timing adjust (not yet tested on a console): `$SET_TIMINGS`. While the game runs, controller 1 alone holding L1/L2 or R1/R2 nudges two of POPS's timing values, and controller 2 alone holding L1/L2 (small steps) or R1/R2 (big steps) nudges a third. Like POPStarter, it keeps the values on the slot 0 memory card (a small entry in the card's header area) and loads them next time.
  - Picture: `$SMOOTH`, `$XPOS_`/`$YPOS_`, `$DWSTRETCH_`, `$DWCROP_`, `$LEFTADJ_` and the manual `$DX_`..`$DH_` set make POPStarter's changes (not yet tested on a console). Not POPStarter commands, ignored: `$480i`, `$576p`, `$576i`, `$240p`, `$VMODE_n`, `$DITHER_OFF`, `$FASTMIPS`, `$SLOWMIPS`. `$NOBOOT` / `$BIOS` keeps the PS1 boot logo (launcHER's own commands; POPStarter r13 has neither).
  - Controllers (not yet tested on a console): `$NOPAD0` / `$NOPAD1` make the game see no controller in that port; `$PAD0ID_0Xhh` / `$PAD1ID_0Xhh` make the port report controller ID `hh` (for example `0X41` digital, `0X73` analog); `$D2LS` swaps the D-pad and the left stick and presents both ports as digital pads; `$D2LS_ALT` swaps them and keeps the real controller type.
  - Delays and stability: `$SAFEMODE` (cheats wait while the PS1 BIOS boot is still running, as in POPStarter), `$SAFEMODE2` (POPStarter's second cheat gate), `$NOSAFEMODE` (turns both off), `$USBDELAY_<seconds>`. The safe modes are not yet tested on a console. `$USBDELAY` does not yet work as in POPStarter: launcHER pauses that many seconds once before starting POPS, on any device, and not at all without the command. POPStarter accepts a single digit, uses 1 second without the command, and on USB and SMB launches passes the number to its own file wrapper, which appears to wait that many seconds once, before the first file it opens. That description comes from POPStarter's code, read and partly run on a PC with the console's services replaced by models; the wait itself has never been observed. Not tested on a console.
  - Compatibility modes: `$COMPATIBILITY_0x01` through `0x07`, or bare digits `1`..`7` in `MODES.TXT` (Mode 8 has no branch in the original and is refused).
- **`DISCS.TXT`:** The discs of a multi-disc game, one file name per line (up to 4), read as POPStarter r13 reads them: names of files beside the launched game, not paths (a `/`, `\` or `:` anywhere and the whole file is ignored), no comments, at most 89 characters a line. A `DISCS.TXT` beside the games applies to all of them; one in the game's own subfolder (named like the game) is read after it and replaces its lines from the first. Change discs in game with POPStarter's combos (see the hotkeys below; not yet tested on a console).
- **`CHEATS.TXT`:** GameShark / Action Replay codes written POPStarter style, `$` then the code (`$8009A120 0004`), read the way POPStarter r13 reads them. Remove the `$` to switch a code off; a `#` in front does not, because POPStarter finds `$` codes anywhere on a line. A line that is not a valid code is skipped and never stops the launch. POPStarter's types work as it compiles them: `80` / `30` writes, `D0` (gates the next code), `C0` master code (the first one gates every code; values `8000` and up never match, as in POPStarter) and `5000nnss vvvv` repeats. Other GameShark types (`10`, `20`, `D1`..`D3`, `E0`, `E1`) are skipped, as in POPStarter, and POPStarter's two repeat bugs are copied too (see the setup page). POPStarter's PS2-format codes work too: `$0`/`$1`/`$2` EE RAM writes, `$S` / `$T` scratchpad writes and conditionals, and `$=` / `$!` 32-bit compares, with POPStarter's quirks (see the setup page). launcHER's own resident code applies the codes from the same place in POPS as POPStarter, each time the game writes the GPU control port, so not exactly once per frame (not yet tested on a console). See [docs/pops-setup.html](docs/pops-setup.html#step-9-cheats).
- **`VMCDIR.TXT`:** Redirects Virtual Memory Card save files to a custom folder path.

### Custom IRX driver replacement and peripherals

`MODULE_0.IRX` through `MODULE_9.IRX` work as in POPStarter r13: put them in the same folder as your POPS files (`POPS_IOX.PAK` / `POPS.PAK`), normally the device's `POPS` folder. Each file is read before the IOP reset; a module named like one of POPS's own (`sio2man`, `padman`, libsd, `sdr_driver`, `dev9`, `atad`, `hdd`, `pfs`) replaces POPS's copy. After the reset they start in numerical order (`hdd` and `pfs` get POPStarter's arguments) and a module that fails to start stops the launch. For `SB.` launches modules 5 to 9 start after the network stack. Details: [docs/POPSTARTER_MODULE_IRX.md](docs/POPSTARTER_MODULE_IRX.md). Not yet tested on a console.

launcHER-only extras, loaded after the numbered modules:

- **Named peripherals:** Specialty drivers load when present: `USBMOUSE.IRX` / `USB_MOUSE.IRX`, `USBKBD.IRX`, `USBGUN.IRX` / `GUNCON.IRX`, `MULTITAP.IRX`, `DS3.IRX` / `DS4.IRX`, `PADMAN.IRX`, `SIO2MAN.IRX`.
- **Manifest lists:** `MODULES.TXT` and `IRX.TXT` specify arbitrary module file paths to load.
- **Search locations for these two:** `vmcDir`, `vcdDir`, `vcdDir/IRX/`, `mc0:/POPSTARTER/`, `mc1:/POPSTARTER/`, `mc0:/POPS/`, and `mc1:/POPS/`.

### Built-in compatibility database and LibCrypt

launcHER carries POPStarter r13's own built-in per-game list: the disc is identified from 144 bytes of the VCD (stored as hashes), and the matching entry's compatibility modes, LibCrypt fix, game-fix code, breakpoint handler or memory card 1 switch are applied as the original applies them, before your own commands, which can still undo them (`$UNDO_*`). `$VCDID_n` picks an entry by hand when nothing matched. Details and the measured behaviour are in [docs/POPSTARTER_BUILTIN_DB.md](docs/POPSTARTER_BUILTIN_DB.md); not yet tested on a console. `$RESET_WARMBOOT` is carried the same way: POPStarter's rewrite of the PS1 BIOS error and exit stubs to a warm boot, and its change to the in-game reset combo (SELECT+L2+R2+CROSS), bugs included ([docs/POPSTARTER_RESET_WARMBOOT.md](docs/POPSTARTER_RESET_WARMBOOT.md)). Like POPStarter, every launch also runs its opcode pass over POPS (about 10,000 load/store instructions become their unaligned-safe forms); `$ORIGINAL_OPCODES` turns it off ([docs/POPSTARTER_OPCODE_PASS.md](docs/POPSTARTER_OPCODE_PASS.md), not yet tested on a console). It also makes POPStarter's other changes that no command switches off: its hook in POPS's GPU write path (where the in-game reset combo, the built-in list's code and the cheats run), nine guards against misaligned memory reads, its exit and byte-copy changes, three edits to the PS1 BIOS shell, and the same memory clearing before POPS starts ([docs/POPSTARTER_LAUNCH_HOOKS.md](docs/POPSTARTER_LAUNCH_HOOKS.md), not yet tested on a console). Beside it, launcHER contains an internal catalogue of 568 verified game profiles and 229 validated 16-bit LibCrypt keys. When launching a `.VCD`, launcHER extracts the title serial from `SYSTEM.CNF` inside the ISO9660 volume descriptor, sets required compatibility modes, and programs hardware Subchannel Q emulation into the driver. The built-in list is measured against the original handlers, but protected European game compatibility remains unverified on a physical console. `$BREAKPOINT0` (run that breakpoint killer once, early) and `$BREAKPOINT1` (run it while SELECT+L2+R2+CIRCLE is held) are copied too ([docs/POPSTARTER_BREAKPOINT.md](docs/POPSTARTER_BREAKPOINT.md)).

### Virtual Memory Cards (VMC)

launcHER looks for card saves using `<SERIAL>.VMC0` and `<SERIAL>.VMC1` (or `<GAME_BASE>.VMC0` and `SLOT0.VMC`). If the files do not exist, launcHER creates both formatted 128 KiB card images automatically.

### In-Game Reset and controller hotkeys

- **In-Game Reset (IGR):** `L1 + L2 + R1 + R2 + SELECT + START` (returns to OSDSYS, OPL, or wLaunchELF).
- **Disc Swap (POPStarter's, controller 1, not yet tested on a console):** `SELECT + L2 + R2 + TRIANGLE` opens the virtual lid; `SELECT + L2 + R2` with `UP`, `RIGHT`, `DOWN` or `LEFT` picks disc 1, 2, 3 or 4 of `DISCS.TXT`; `SELECT + L2 + R2 + SQUARE` closes the lid and loads that disc. Hold nothing else with a combo. Without `DISCS.TXT` it reloads the disc the game started with.
- **Other POPStarter hotkeys (controller 1):** `SELECT + R2 + R1` / `SELECT + L2 + L1` turn scanlines on / off; `SELECT + L2 + R2 + CROSS` resets the PS1.
- **launcHER's older disc swap** (`SELECT + L1 + R1`) was removed on November 2, 2026: it could never switch while the game had the disc open, which is all the time in game. POPStarter's combos above are the only disc swap.
- **Custom IGR graphics (`IGR_BG.TM2`, `IGR_NO.TM2`, `IGR_YES.TM2`), NOT TESTED on a console:** on every POPS launch launcHER looks for the three files in the folder the `.VCD` is in and copies each one it finds, unchecked, over the picture Sony's POPS carries for its in-game reset dialog, as POPStarter does. `IGR_BG.TM2` may be up to 312,064 bytes, `IGR_NO.TM2` and `IGR_YES.TM2` up to 7,612 bytes each; a larger file is skipped, and a 0-byte file blanks that picture. POPStarter reads them from the device's `POPS` folder (`mass:/POPS/`, or `pfs1:/POPS/` on its HDD back end), so they are found in the same place only when the `.VCD` is in `mass:/POPS/`. The dialog, and with it the pictures, only appears with `$IGR0`, `$IGR1` or `$IGR2`; without an IGR command launcHER exits directly and the dialog never opens. Details: [docs/POPSTARTER_IGR_SKIN.md](docs/POPSTARTER_IGR_SKIN.md). (This line said "not implemented" from November 11, 2026 until the skin was merged.)
- **Fix files (`TROJAN_0.BIN`..`TROJAN_9.BIN`, `PATCH_0.BIN`..`PATCH_9.BIN`):** read from beside the game and from the game's subfolder. **TROJAN files from community fix packs do not work yet and stop the launch:** on a host, this branch rejected all 509 distinct TROJAN files found in a collection of community fix packs, and a rejected fix file ends the launch with "Fix file rejected". If a launch stops with that message, take the TROJAN files out of the game's folders. The 10 distinct PATCH files in the same collection were accepted. The rejection was measured on a host and the stop was read from the launch code on November 11, 2026; neither was tested on a console. Details: [docs/POPSTARTER_GAP_AUDIT_2026-11-11.md](docs/POPSTARTER_GAP_AUDIT_2026-11-11.md), section 12.

For full technical documentation, see the [POPS & PS1 Setup Guide](docs/pops-setup.html).

---

## Release files

Each release provides:

- **`launcHER.elf`**: the standalone launcher;
- **`launcHER.CNF`**: an editable quickboot template with device examples;
- **`version.txt`**: a one-line build identifier (`version=<12-character Git commit>` for rolling builds, or `version=vX.Y.Z` for tagged releases);
- **`launcHER.zip`**: ready-to-copy package containing the ELF, CNF and version file;
- GitHub's automatic **Source code (zip)** and **Source code (tar.gz)** archives.

No KELF is required for normal launcHER use.

---

## Building

A PS2SDK/ps2dev environment and CMake are required.

```bash
cmake -B build
cmake --build build --target launcHER
```

The finished package is generated under:

```text
build/release/
├── launcHER.elf
├── launcHER.CNF
└── version.txt
```

GitHub Actions additionally creates `launcHER.zip` from those three files for releases. `version.txt` is regenerated on each build, so repeated builds after a commit do not reuse a stale identifier. A local build from a source archive without Git metadata uses `version=unknown`; CI rejects unknown versions for published packages.

---

## Hardware verification and bug reports

Device support is compiled directly into the standalone launcHER build, but support existing in the launcher does not mean every device, adapter, storage implementation, and Ember version has been tested in every possible combination.

The APA/PFS Ember handoff documented above has been hardware verified.

If you encounter a problem, please include:

- PS2 model;
- storage device;
- storage filesystem;
- adapter, if applicable;
- exact Ember location;
- exact `launcHER.CNF`;
- Ember version;
- launcHER version (the exact `version=...` line from `version.txt`);
- game folder being launched;
- what appears on screen before failure.

The exact storage layout and configuration matter. "HDD does not work" does not provide enough information to identify which HDD path is actually being used.

---

## Project scope

launcHER deliberately does one job:

> **Launch Ember or Sony POPS games from supported storage, then step aside without destroying the environment each runtime needs.**

Keeping the project focused means unrelated OSDMenu features are not part of the standalone launcHER release target.

The project no longer builds or packages unrelated:

- OSDMenu/HOSDMenu patchers;
- MBR installers;
- KELF payloads;
- CD/DVD launcher functionality;
- XFROM support.

---

## Credits

- **[nuno6573](https://github.com/nuno6573)** — solution, concept, and selection of the approach used for [Ember](https://github.com/Gageformer/Ember)'s external launcher. Thanks to nuno for the information and idea.
- **[pcm720](https://github.com/pcm720)** — creator of [OSDMenu](https://github.com/pcm720/OSDMenu) and the standalone OSDMenu Launcher from which launcHER is derived. The device handlers, loader architecture, and foundation of this project come from that work.
- **Eliminator / eliminator1403** — PS2 hardware testing, validation, regression checking, device-side feedback, and the filename-independent `launcHER.CNF` quickboot refinement used for renamed OPL APPS entries.
- **[Gageformer](https://github.com/Gageformer)** — creator of [Ember](https://github.com/Gageformer/Ember), the project launcHER exists to launch.
- **[NathanNeurotic / Ripto](https://github.com/NathanNeurotic)** — launcHER fork, [Ember](https://github.com/Gageformer/Ember) handoff integration, POPStarter replacement, APA/PFS persistence changes, standalone build, configuration, documentation, and release packaging.
- The **PS2SDK / ps2dev** contributors and broader PS2 homebrew community whose drivers and libraries make the supported storage stack possible.

launcHER keeps its upstream lineage visible intentionally. It would not exist without [pcm720](https://github.com/pcm720)'s launcher work, [Ember](https://github.com/Gageformer/Ember) would not exist without [Gageformer](https://github.com/Gageformer), and its hardware behavior would not be trustworthy without real-console testing.
<img width="873" height="348" alt="launcherbanner" src="https://github.com/user-attachments/assets/e54f9ad4-c40b-483a-acaa-2accb5aa55cc" />
