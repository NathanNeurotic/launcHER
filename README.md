<img width="857" height="483" alt="launcHER" src="https://github.com/user-attachments/assets/5641aed3-4695-4bc6-9436-e2a0fba8c7d5" />

# launcHER

**launcHER is a standalone PlayStation 2 forwarder built specifically to launch [Ember](https://github.com/Gageformer/Ember) from supported devices while preserving the environment Ember needs after handoff.**

It is intentionally small in scope. This is not an OSD replacement, HDD Browser project, KELF installer, or menu system. It is simply **launcHER**.

launcHER is derived from the standalone launcher in [pcm720/OSDMenu](https://github.com/pcm720/OSDMenu), stripped down and adapted for Ember launching.

## What it does

launcHER can locate `EMBER/ember.elf` on a supported PS2 storage device, prepare the required device stack, forward Ember's game-folder argument, and hand execution over to Ember.

For APA/PFS HDD launches, launcHER also provides the behavior Ember specifically needs:

- mounts the target PFS partition read/write;
- keeps `pfs0:` mounted across `ExecPS2`;
- keeps the HDD/DEV9 environment alive with `-dev9=NICHDD`;
- allows Ember to receive `pfs0:/EMBER/ember.elf` as its real `argv[0]`;
- forwards the game as a bare folder name in `argv[1]`.

This allows Ember to continue resolving its relative `games/` directory and to retain writable access for memory cards, settings, and other files after launcHER exits.

## Release files

Each release provides:

- **`launcHER.elf`** — the standalone launcher;
- **`launcHER.CNF`** — an editable quickboot template with device examples;
- **`launcHER.zip`** — ready-to-copy package containing the ELF and CNF;
- GitHub's automatic **Source code (zip)** and **Source code (tar.gz)** archives.

No KELF is required for normal launcHER use.

## Ember layout

The expected Ember layout is:

```text
EMBER/
├── ember.elf
├── bios.bin
└── games/
    └── <GAME_FOLDER>/
```

The game argument must be the **bare folder name** under `EMBER/games/`.

For example, if the game is stored at:

```text
EMBER/games/Soul Blade/
```

then Ember should receive:

```text
argv[1] = Soul Blade
```

Do not pass `games/Soul Blade`, a `.cue` path, or a full device path as the game argument.

## Quickboot configuration

Keep `launcHER.CNF` beside `launcHER.elf`. When launcHER is started without an explicit target, it automatically looks for a CNF with the same base name.

Lines beginning with `#` are comments. Uncomment only the profile you intend to use.

`arg=` lines are shared by all active `path=` lines, so device profiles that require different handoff arguments should not be mixed in the same active block.

### APA / PFS HDD

This is the hardware-verified Ember handoff.

Example using an APA partition named `__.EMBER` and a game folder named `Soul Blade`:

```ini
path=hdd0:__.EMBER:pfs:/EMBER/ember.elf
arg=pfs0:/EMBER/ember.elf
arg=Soul Blade
arg=-skip_argv0
arg=-dev9=NICHDD
```

launcHER uses:

```text
hdd0:__.EMBER:pfs:/EMBER/ember.elf
```

to locate and load Ember, while Ember itself receives:

```text
argv[0] = pfs0:/EMBER/ember.elf
argv[1] = Soul Blade
```

`-skip_argv0` removes the loader-facing `hdd0:` target from Ember's final argument list. `-dev9=NICHDD` keeps the HDD/DEV9 environment active and, in launcHER, preserves the writable `pfs0:` mount through handoff.

Replace `__.EMBER` with your actual APA partition name and `Soul Blade` with your actual Ember game-folder name.

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

### USB

```ini
path=mass?:/EMBER/ember.elf
arg=<GAME_FOLDER>
```

`usb?:` is also supported by the inherited launcher path handling.

### MX4SIO

```ini
path=mx4sio:/EMBER/ember.elf
arg=<GAME_FOLDER>
```

### Internal exFAT HDD / ATA BDM

```ini
path=ata:/EMBER/ember.elf
arg=<GAME_FOLDER>
arg=-dev9=NICHDD
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

Network configuration for UDPBD/UDPFS follows the inherited OSDMenu Launcher implementation and uses `mc?:/SYS-CONF/IPCONFIG.DAT`.

## Supported launcher transports

The standalone launcHER build enables:

- MMCE
- memory cards
- USB / mass storage
- internal exFAT HDD / ATA BDM
- APA / PFS HDD
- MX4SIO
- i.Link
- UDPBD
- UDPFS

The project no longer builds or packages the unrelated OSDMenu/HOSDMenu patchers, MBR installers, KELF payloads, CD/DVD launcher path, or XFROM support.

Compilation support does not imply that every transport has been hardware-verified with every Ember version. APA/PFS Ember launching is confirmed working with the handoff shown above.

## Direct arguments

launcHER can also be called directly by another launcher instead of using `launcHER.CNF`.

APA example:

```text
launcHER.elf hdd0:__.EMBER:pfs:/EMBER/ember.elf pfs0:/EMBER/ember.elf "Soul Blade" -skip_argv0 -dev9=NICHDD
```

The global launcHER flags belong at the end of the argument list.

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

## Project scope

launcHER deliberately does one job:

> **Get Ember launched from wherever it lives, then get out of the way without destroying the environment Ember still needs.**

Keeping the project focused also means upstream OSDMenu features that have nothing to do with this job are not part of launcHER's release target.

## Credits

- **[pcm720](https://github.com/pcm720)** — creator of [OSDMenu](https://github.com/pcm720/OSDMenu) and the standalone OSDMenu Launcher that launcHER is derived from. The device handlers, loader architecture, and foundation of this project come from that work.
- **Eliminator / eliminator1403** — PS2 hardware testing, validation, regression checking, and device-side feedback.
- **[Gageformer](https://github.com/Gageformer)** — creator of [Ember](https://github.com/Gageformer/Ember), the project launcHER exists to launch.
- **[NathanNeurotic / Ripto](https://github.com/NathanNeurotic)** — launcHER fork, Ember handoff integration, APA/PFS persistence changes, standalone build, configuration, and release packaging.
- The **PS2SDK / ps2dev** contributors and the broader PS2 homebrew community whose drivers and libraries make the supported device stack possible.

launcHER keeps its upstream lineage visible on purpose. It would not exist without pcm720's launcher work, Ember would not exist without Gageformer, and the hardware behavior would not be trustworthy without real-console testing.
