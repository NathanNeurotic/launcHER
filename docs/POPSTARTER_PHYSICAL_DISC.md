# POPStarter r13's physical PS1 disc launch

Measured on the original (POPSTARTER.ELF MAIN and POPS.ELF, external inputs)
on 2026-11-11. **Nothing here was tested on a console.** Every result below
is a host test or the original's own code run under an emulator with the
calls it makes (libcdvd, module loading, file I/O, printf) replaced by a
model. A model returns whatever the test tells it to: it shows what the
original does with an answer, never what a PS2 drive answers.

launcHER has the drive-free part only: a planner, a guarded core stage and a
fingerprint builder in `common/src/pops_physical_disc.c`. **Nothing calls
them.** A launch whose VCD is missing still ends at "Cannot open target VCD"
(`launchPOPS`, `-ENOENT`), exactly as before this work. Ember and every
non-PS1 launch run no line of it.

## How the original gets there

A physical disc is not something the user selects. The original's launch
function looks for the VCD; when it finds none it sets the word at
`gp+0x3410` (`0x9b9d00`) to 1 and carries on with the disc drive instead.

| Launch type (`gp+0x3414`) | What is probed before the flag is set | Flag set at | How this was established |
|---|---|---|---|
| 0 (HDD, by ELF name) | `hdd0:__.POPS`, then `hdd0:__.POPS0` .. `hdd0:__.POPS9`, each mounted on `pfs0` (the name is written over `argv[0]`) and the VCD path opened; 11 mounts in all | `0x875d98`, cleared again on a later "FOUND" | window `0x875ab0..0x875fa4` run under Unicorn, mount/open modelled. The VCD path itself (`gp+0x3470`) is built earlier and was supplied by the test |
| 1 and 2 (a game partition) | the partition `argv[0]` names, mounted on `pfs0`; one open | `0x8756a4` (mount failed), `0x875734` (open failed) | window `0x875678..0x8757ec` run; the path was supplied by the test |
| 3 (`XX.` and `SB.`) | `mass:/POPS/<name>`, then `mass:/POPS0/<name>` .. `mass:/POPS9/<name>`; 11 opens. `<name>` is read from POPS `0x4f8003`; `argv[0]` is overwritten with `hdd0:PP.POPS-00001` | `0x876690` (with `gp+0x381c` = 0) | window `0x875fa4..0x8766fc` run, open modelled |
| 4 | not looked at | | not measured |

When a VCD is found the four region letters are read from its offset
`0x102514` into `gp+0x3cb0` and the flag stays 0.

In the type 3 window a VCD found in `mass:/POPSn/` (not `mass:/POPS/`) takes
a further path that copies the folder name into an embedded module image at
`0x91fb50` and leaves the launch function's "found" local at 0. That path was
seen once under emulation and is outside this work.

The flag is cleared at `0x870bc8` and on each "FOUND" (`0x875780`,
`0x875d1c`, `0x875f24`, `0x876254`, `0x8763d0`). The store sites were read
from the disassembly. The emulated cases cover a found and a not-found
outcome of each window, and for types 0 and 3 a VCD on the first candidate
and on a later one; which store each case went through was not traced
address by address.

## The drive probe, `0x8766fc..0x876a40`

Entered only when the flag is exactly 1 and the launch function's "VCD
found" local (`0x10b8($fp)`) is 0; any other pair skips the whole block
(6 pairs run).

1. `FUN_00870150` walks the IOP module list and reads 60 bytes of each
   module's name. The first name that starts `cdvd_` sets the word at
   `0x9ae914` to 1 and ends the walk. Nothing ever clears that word.
2. No such module: print `    Loading CDVD dvrs... `, then
   `SifLoadModule("rom0:CDVDMAN", 0, 0)` and
   `SifLoadModule("rom0:CDVDFSV", 0, 0)`. Their results are not looked at.
   Otherwise print `    CDVD dvrs loaded... ` and load nothing.
3. Print `Init... `, then `sceCdInit(1)`, `sceCdSync(0)`, `sceCdStatus()`.
   The result of `sceCdInit` is not looked at.
4. Status equal to 1 (the tray-open value in the SDK headers): print
   `Cannot access (%d)!` with the status and take the fatal exit
   (`0x8709f8`). The disc type is never asked for. Nothing is unmounted on
   this path, and there is no retry or wait.
5. `sceCdGetDiskType()`. Anything but `0x10`, `0x11`, `0x12`, `0x13` (the
   SDK's PS1 CD, PS1 CD with CD-DA, PS2 CD, PS2 CD with CD-DA): print
   `NO PS1 CDROM!`, call the helper `0x8d7ff8` unless `gp+0x3448` is 1 or
   the launch type is 3 or 4, then take the fatal exit. (The helper was read,
   not run: it unmounts `pfs0:` and `pfs1:`.)
   The SDK's "still detecting" values `0x01..0x04` are refused like any
   other; the original does not wait for detection to finish.
6. Zero the sector buffer (`0x9ba5b0`, `0x1260` bytes), `sceCdSync(0)`,
   `sceCdDiskReady(0)`, `sceCdSync(0)`, `sceCdRead(4, 1, buffer, mode)`,
   `sceCdSync(0)`. The mode bytes are `20 01 00 00` (32 tries, spindle
   control 1, 2,048-byte sectors; set at `0x870c20..0x870c34`, read from the
   disassembly and supplied by the harness). Neither `sceCdDiskReady` nor
   `sceCdRead` has its result looked at.
7. Copy buffer bytes 60..63 to `gp+0x3cb0`: the region letters. Zero the
   buffer again. **A failed read is not an error**: the buffer is still zero,
   so the letters are four zero bytes.
8. The writes listed below.
9. Print a newline. If the built-in list level `gp+0x385c` is 1, 2, 3 or 4,
   call the fingerprint function `FUN_008ff0e4(0, level)`.

Both compares are on the whole 32-bit value: status `0x101` passes and type
`0x110` is not a PS1 disc. With `gp+0x38b0` = 1 (quiet; the gap audit
records that as the MAIN profile's setting) none of the messages is printed,
the fatal ones included.

### What it writes

Sony's POPS:

| Address | Sony's value | Written | Meaning |
|---|---|---|---|
| `0x200794` | `0x03a0202d` (`move a0,sp`) | `0x0000202d` (`daddu a0,zero,zero`) | delay slot of `jal 0x210540` at `0x200790`: POPS's disc layer is started with NULL in place of the image name |
| `0x20f0b6` | `0x02` | `0x00` | types `0x11` and `0x13` only: the three `$MUTE_CDDA` writes |
| `0x20ebf2` | `0x03` | `0x00` | |
| `0x20f0e0` | `0xae000014` | `0x00000000` | |

The original's own always-live code (the `0x738` bytes it copied to POPS
`0x232790` earlier, at `0x874754`):

| Address | Before | Written | Meaning |
|---|---|---|---|
| `0x2328bc` | `0x34842950` (`ori a0,a0,0x2950`) | `0x0000202d` | the lid-close hotkey calls `0x210540` with NULL instead of a `DISCS.TXT` slot |
| `0x2328c8` | `0x3c1a0050` | `0x1000001f` (`b 0x232948`) | jump over the four D-pad disc selections |
| `0x2328cc` | `0x241bfcee` | `0x00000000` | that branch's delay slot |
| `0x2328d0..0x232943` | the four selections | zeros (`memset`, `0x74` bytes) | the last word of the fourth selection, the `sh` at `0x232944`, stays but is jumped over |

Elsewhere in memory the block changes only the four letters at `gp+0x3cb0`
and, when the scan found a module, the word at `0x9ae914`. The sector buffer
is zero again when it returns. On either fatal path POPS is untouched.

## Later readers of the flag

All eight load sites of `gp+0x3410` (`0x8766fc`, `0x8774c4`, `0x878ab4`,
`0x878c78`, `0x8d5d24`, `0x8d5d90`, `0x8ff12c`, `0x8ff24c`) were found by a
scan of MAIN for gp-relative accesses and each was run.

| Site | With the flag at 1 | With other values |
|---|---|---|
| `0x8774c4` | `sceCdInit(5)` (the SDK's exit code) just after `FUN_008dc9ac`, before the IOP work | nothing (0, 2 and `0xffffffff` run) |
| `0x878ab4`, `0x878c78` (the "POPS ENVIRONMENT" lines) | the "Game partition" and "User VCD image" lines are not printed; `memset(0x4f8000, 0, 0x80)` clears POPS's image-name buffer; the "VMCs" and "Game resource dir" lines follow as usual | 0: all lines, no write. 2: nothing at all |
| `0x8d5d24`, `0x8d5d90` (`FUN_008d5cf8`, the `DISCS.TXT` reader, called at `0x877414` and `0x8774b4`) | three lines (`D-Pad button assignment (DISCS.TXT) skipped.`, `Emulating lid open/close with triangle/square.`, `Only for refreshing the physical PS1 CDROM TOC.`) and return; the file is never opened | 0: the file is opened. Any other value: silent return |
| `0x8ff12c`, `0x8ff24c` (`FUN_008ff0e4`, the fingerprint) | sectors 16 and 22 are read from the drive, see below | 0: the VCD is read. Any other value: nothing is read and the compare runs on an uninitialised allocation |

So with a physical disc `DISCS.TXT` does nothing and the two lid hotkeys
remain: SELECT+L2+R2+TRIANGLE opens the lid, SELECT+L2+R2+SQUARE closes it
and calls POPS's disc start-up again with NULL. What that call does to a
real drive (the messages say it refreshes the TOC) was not looked at.

## Region letters

The region pass (`0x879034..0x8795f0`, measured earlier for
`pops_apply_region`) reads nothing but the four bytes at `gp+0x3cb0`. For a
VCD they come from file offset `0x102514`; for a disc they are sector 4
bytes 60..63, which is the same place (raw sector 4 of a VCD behind its
1 MiB header puts data byte 60 at `0x102514`).

Run end to end for `Euro`, `Amer`, `of A`, `Inc.`, an unknown text and a
failed read: the block's letters, fed to the original's region window, write
the same bytes as `pops_region_from_licence` + `pops_apply_region` from the
planner's letters. One difference from launcHER's VCD path matters when this
is wired: launcHER skips the region pass when it cannot read the licence,
while the original, after a failed disc read, runs it with four zero letters
and so writes the unknown-region values. To match, a physical launch must
always run `pops_apply_region` with the planner's letters.

## Built-in list fingerprint

`FUN_008ff0e4(fd, level)` builds the 144 bytes it compares with its 607
stored fingerprints:

| Part | From a VCD (flag 0) | From a disc (flag 1) |
|---|---|---|
| bytes 0..47 | file offset `0x109340` | sector 16 bytes 40..87 |
| bytes 48..79 | file offset `0x109640` | sector 16 bytes 808..839 |
| bytes 80..143 | file offset `0x10ca70` | sector 22 bytes 56..119 |

Each disc sector is read like sector 4 (buffer zeroed, `sceCdSync`,
`sceCdDiskReady(0)`, `sceCdSync`, `sceCdRead(lba, 1, ...)`, `sceCdSync`), and
again no result is looked at: a failed read leaves zeros in its part, and a
disc with both reads failed is "Unknown" like any unlisted disc. A match
prints ` DONE`, stores the entry number at `gp+0x38d8` and calls
`FUN_008e00d0(entry, level)`; the function returns 1 either way.

`pops_physical_disc_fingerprint(sector16, sector22, out)` builds the same
144 bytes, and `pops_builtin_lookup(out)` then names the same entry: run for
every one of the 607 stored fingerprints planted in otherwise random
sectors, and for 204 of them again inside a VCD through both of the
original's file backends.

## What launcHER has

`common/include/pops_physical_disc.h`:

- `pops_physical_disc_plan(plan, drive_status, disc_type, sector4, read_ok)`:
  the block's decision. `plan->fatal` is `POPS_PHYSICAL_FATAL_ACCESS` or
  `POPS_PHYSICAL_FATAL_NOT_PS1` (`pops_physical_disc_message` gives the
  original's text), otherwise the letters and whether to mute CD-DA. The
  caller passes the buffer as the read left it and must have zeroed it
  first, as the original does; `read_ok` is recorded and changes nothing.
- `pops_physical_disc_stage(core, core_size, disc_type)`: the four writes
  into Sony's POPS above. Unlike the original it checks first that every
  site it is about to write holds Sony's value and writes nothing otherwise
  (`-EILSEQ`). The CD-DA writes go through the existing `$MUTE_CDDA` writer.
  Its place in `launchPOPS` is after `pops_apply_always_on_pokes` and before
  `pops_stage_igr_skin`: the original's order is always-on changes, this
  block (with the built-in entry at its end), IGR skin, user files. On the
  real core, launcHER's earlier stages (core patches, each `$FIX_*`
  correction, the hooks, the always-on pokes) leave all four sites as Sony
  shipped them.
- `pops_physical_disc_clear_name(core, core_size)`: the `memset` at
  `0x878c88`. Sony ships that buffer zero and launcHER does not write it, so
  today this changes nothing.
- `pops_physical_disc_fingerprint(sector16, sector22, out)`: above.

## Not done

- **No drive access and no launch path.** Nothing loads `rom0:CDVDMAN` /
  `rom0:CDVDFSV`, calls libcdvd or reads a sector for a POPS launch, and
  `launchPOPS` cannot start without a VCD: it takes its paths, serial,
  fingerprint, region, memory-card folder and popfs registration from the VCD
  file.
- **The resident part.** The original's writes into its always-live code
  map to `pops_resident_hotkeys` in `common/src/pops_resident_engine.c`,
  which this work did not touch: with a physical disc the lid close must call
  POPS's disc start-up with NULL (the original's `0x2328bc = 0x0000202d`)
  and the four `POPS_COMBO_DISC_1..4` selections must not run (the
  original's `0x2328c8 = 0x1000001f`, `0x2328cc = 0`, `0x2328d0..0x232943`
  zeroed). That needs a flag in the resident configuration and a new
  resident version.
- **`DISCS.TXT`** must be skipped for a physical launch, with the three
  lines above.
- **`sceCdInit(5)`** before the IOP work (the original's `0x8774d4`).
- **POPS's own disc layer.** `0x200794` makes POPS call `0x210540` with NULL.
  What Sony's code does from there, what launcHER's core patches (which point
  POPS at its own popfs device) do to that path, and whether POPS's IOP image
  has a usable cdvdman after the IOP reset were not looked at.

## What needs a console

Everything that involves the drive: what `sceCdStatus` and
`sceCdGetDiskType` return right after `sceCdInit(1)` for each kind of disc
(including whether a type is still "detecting" at that moment), the read of
sectors 4, 16 and 22, CD-DA with and without the mute writes, whether POPS
boots from the disc at all after its IOP reset, in-game reads, and the lid
hotkeys with a real tray.

## Evidence

`tools/trace_original_pops_physical.py` runs the windows;
`tools/test_pops_physical_disc.py` compares. With the reference files:

| What | Cases | Compared |
|---|---|---|
| Block, every disc type 0..255 plus 6 wide values, status 0 | 262 | call sequence, messages, letters, whole POPS core, all other memory |
| Block, every status 0..255 plus 4 wide values (types `0x10`; also `0x13` and `0x14` for status 0..7) | 276 | same |
| Block, seeded status/type/sector/read result/module list/quiet/launch type/mass flag/list level/call results | 400 | same |
| Block, every combination of the unchecked results | 48 | reaches POPS every time |
| Block not entered | 6 | no call, no write |
| Module scan | 7 lists | names read, where it stops, modules loaded |
| Fatal exit and pfs unmount | 20 | launch type 0..4, mass flag 0/1, both fatal reasons |
| Letters into the region pass | 6 | original region window against `pops_apply_region` |
| Fingerprint from sectors | 607 | bytes compared, entry dispatched, `pops_builtin_lookup` |
| Fingerprint from a VCD | 204 | same entry, the three offsets and lengths |
| Fingerprint, unknown and unread discs | 40 | bytes, "Unknown", no entry |
| Later readers (`0x8774c4`, banner, `DISCS.TXT` reader) | 4, 6 and 8 runs | calls, messages, core |
| VCD probes, types 0, 1/2 and 3 | 10 | paths tried, flag, letters |

Without the reference files only the planner, the stage, the fingerprint
layout and the source checks run.
