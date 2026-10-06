
<p align="center">

<img width="873" height="348" alt="launcHER" src="https://github.com/user-attachments/assets/e54f9ad4-c40b-483a-acaa-2accb5aa55cc" />

<img width="400" height="92" alt="AI-Assisted-Software-Lovers-Only" src="https://github.com/user-attachments/assets/71335775-9fe3-4507-ac2c-caa851abb24c" />

</p>

# launcHER

**launcHER is a standalone PlayStation 2 forwarder built specifically to launch [Ember](https://github.com/Gageformer/Ember) from supported storage devices while preserving the environment Ember needs after handoff.**

It is not an OSD replacement, HDD Browser, game manager, KELF installer, or menu system.

It does one job:

> **Find Ember wherever you keep it, prepare that storage device correctly, pass Ember the game it should launch, and get out of the way.**

launcHER is derived from the standalone launcher in [pcm720/OSDMenu](https://github.com/pcm720/OSDMenu), stripped down and adapted specifically for Ember.

---

## HDD users — read this first

**launcHER does not require a dedicated HDD partition.**

The `__.EMBER` APA partition used in some examples is only an example. It was suggested as a convenient way to give Ember and its games their own space — **not because launcHER requires it.**

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

Ember expects the **bare folder name** underneath `EMBER/games/`.

If the game is stored at:

```text
EMBER/games/Soul Blade/
```

then the game argument is:

```text
Soul Blade
```

Do not pass:

```text
games/Soul Blade
Soul Blade/Soul Blade.cue
mass0:/EMBER/games/Soul Blade/
```

For the example above, Ember should ultimately receive:

```text
argv[1] = Soul Blade
```

---

## Quick start

Download the current release and copy:

```text
launcHER.elf
launcHER.CNF
```

to the location from which you want to start launcHER.

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

**Started from OPL or RiptOPL's APPS?** Those loaders name every BDM device `mass0:`, `mass1:`, ... whether it is a USB drive, an exFAT internal HDD, MX4SIO or i.Link. launcHER therefore looks for its `launcHER.CNF` on all of them, then reboots the IOP so your `path=` target starts with only its own device's drivers, exactly as before. (wLaunchELF passes the device's own name, such as `ata0:/`, so it never needed this.)

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

## Release files

Each release provides:

- **`launcHER.elf`** — the standalone launcher;
- **`launcHER.CNF`** — an editable quickboot template with device examples;
- **`launcHER.zip`** — ready-to-copy package containing the ELF and CNF;
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
└── launcHER.CNF
```

GitHub Actions additionally creates `launcHER.zip` from those two files for releases.

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
- launcHER version;
- game folder being launched;
- what appears on screen before failure.

The exact storage layout and configuration matter. "HDD does not work" does not provide enough information to identify which HDD path is actually being used.

---

## Project scope

launcHER deliberately does one job:

> **Get Ember launched from wherever it lives, then get out of the way without destroying the environment Ember still needs.**

Keeping the project focused means unrelated OSDMenu features are not part of the standalone launcHER release target.

The project no longer builds or packages unrelated:

- OSDMenu/HOSDMenu patchers;
- MBR installers;
- KELF payloads;
- CD/DVD launcher functionality;
- XFROM support.

---

## Credits

- **[nuno6573](https://github.com/nuno6573)** — solution, concept, and selection of the approach used for Ember's external launcher. Thanks to nuno for the information and idea.
- **[pcm720](https://github.com/pcm720)** — creator of [OSDMenu](https://github.com/pcm720/OSDMenu) and the standalone OSDMenu Launcher from which launcHER is derived. The device handlers, loader architecture, and foundation of this project come from that work.
- **Eliminator / eliminator1403** — PS2 hardware testing, validation, regression checking, device-side feedback, and the filename-independent `launcHER.CNF` quickboot refinement used for renamed OPL APPS entries.
- **[Gageformer](https://github.com/Gageformer)** — creator of [Ember](https://github.com/Gageformer/Ember), the project launcHER exists to launch.
- **[NathanNeurotic / Ripto](https://github.com/NathanNeurotic)** — launcHER fork, Ember handoff integration, APA/PFS persistence changes, standalone build, configuration, documentation, and release packaging.
- The **PS2SDK / ps2dev** contributors and broader PS2 homebrew community whose drivers and libraries make the supported storage stack possible.

launcHER keeps its upstream lineage visible intentionally. It would not exist without pcm720's launcher work, Ember would not exist without Gageformer, and its hardware behavior would not be trustworthy without real-console testing.
<img width="873" height="348" alt="launcherbanner" src="https://github.com/user-attachments/assets/e54f9ad4-c40b-483a-acaa-2accb5aa55cc" />
