# POPStarter r13's `TROJAN_n.BIN` files, and which of them launcHER loads

A `TROJAN_n.BIN` is a piece of EE code a user puts next to a game (or in the
`POPS` folder, for every game). POPStarter copies it into memory and writes
one call to it into POPS. This page says what the original does with such a
file, what launcHER does, and where the two differ.

**Status: PARTIAL. Nothing on this page was tested on a console.** Every
result below comes from a host computer: launcHER's C code built for the
host, the original's loader run under Unicorn, and the two GP1 chains run on
`tools/r5900_mini.py`. Where a statement was read from the original's
disassembly and is not exercised by a test, it says so.

The original is the user's own `POPSTARTER.ELF` (MAIN) and `POPS.ELF`. Tests
that need them are skipped unless `POPSTARTER_TEST_ELF` and `POPS_TEST_ELF`
name them. No byte of either, and no byte, name or hash of any fix file, is
in this repository.

## The file

| Offset | Size | Meaning | The original's rule |
|---|---|---|---|
| `0x00` | 8 | `TROJAN_` and the digit of the file being read | anything else: Invalid |
| `0x08`, `0x09`, `0x0b`, `0x0d`, `0x0f` | 1 each | unused | nonzero: Invalid |
| `0x0a` | 1 | format 2: hook width; format 3: revision | format 1 with a nonzero value: Invalid |
| `0x0c` | 1 | format | not 1, 2 or 3: Invalid |
| `0x0e` | 1 | unknown | zero: Invalid; any other value passes |
| `0x10` | 4 | load address | zero: Invalid |
| `0x14` | 4 | entry address | zero: Invalid |
| `0x18` | 4 | hook address | not checked at all |
| `0x1c` | 3 | payload size | `0x40` + size must be the file size |
| `0x1f` | 1 | unused | nonzero: Invalid |
| `0x20` | 20 | name, printed | first byte zero: Invalid |
| `0x34` | 12 | unused | any byte nonzero: Invalid |
| `0x40` | size | payload | |

A file shorter than `0x44` bytes is Invalid, an empty one included.

## The original's loader

`FUN_00880a24` (a0 = 0 for the `POPS` folder, 1 for the game's folder). It
tries `TROJAN_0.BIN` to `TROJAN_9.BIN` in that order and returns 1 whatever
happened; its callers ignore the result. For each file that opens:

- **Invalid** by the table above: prints `Invalid`, goes on to the next
  number.
- **Format 3 with a revision below 6** when the disc matched an entry of
  the built-in list by its fingerprint: prints `Skipped (outdated)`, goes
  on. Without a fingerprint match the same file is applied. (`6` is the
  loader's own revision, `gp+0x345c`.)
- **Otherwise** it copies the payload with `memcpy` to the load address
  and writes the hook, then prints `Hooked :` and the name:
  - format 1, format 3, and format 2 with width 0 or above 3: one word,
    `jal entry`;
  - format 2 with width 1, 2 or 3: `j entry`, then width - 1 zero words.

It checks no address: not alignment, not whether the load range or the hook
is inside anything, not whether the entry is inside the payload. A hook of 0
writes the word at address 0.

The launch calls it for the `POPS` folder, then the PATCH loader for the
`POPS` folder, then both again for the game's folder (call sites
`0x876d6c`, `0x876e00`, `0x877078`, `0x877118`; read from the disassembly).
A game's file therefore overwrites what a `POPS` folder file put at the same
hook.

Measured under Unicorn (`tools/test_pops_trojan.py`, class `Original`): the
verdict, the printed words, every changed byte of all 32 MiB and the order
of the ten opens, for 41 generated files; files of 0, 1, `0x40` and `0x43`
bytes; an Invalid and an outdated file between two good ones. The rule
addresses (`0x881270..0x881904`) are from the disassembly; the tests check
the behaviour, not the addresses. That the payload buffer (`malloc` of
twice the size) is never freed is also read from the disassembly only.

Device failures, measured the same way with failures put into the modelled
file calls (`Original.test_device_failures`): a failed open, whatever the
error, prints `NOT FOUND` and the next number is read; a failed size query
(the `lseek` to the end) leaves a size below `0x44`, so the file is
Invalid; the rewind and the header read are not checked, and the header
buffer is cleared after every file, so a header that does not arrive reads
as zeros and is Invalid; the payload read is not checked either, so a file
whose payload read fails is still applied, with whatever the buffer held.
The check addresses (open `0x88115c`, size and header `0x881188..0x881230`,
payload `0x881a1c`, clearing `0x881d24`) are from the disassembly. A file of
1 MiB of payload is applied like any other; the original has no size limit.

## The ten slots

POPStarter overwrites two parts of the POPS core with code of its own
(`0x232790..0x232ec8` and `0x238a90..0x2397f0`) and points POPS's GP1 path
at it (`jal 0x239490` at `0x21a63c`). That code runs every time the game
writes GP1 with interrupts enabled. It holds ten two-word slots, each
`beq zero,zero,+1; nop` (skip to the next slot) until a file writes its hook
there:

| Order in the chain | Slot address | File number that hooks it in the files examined |
|---|---|---|
| 1 | `0x2327d0` | 7 |
| 2 | `0x2327d8` | 0 |
| 3 | `0x2327e0` | 1 |
| 4 | `0x2327e8` | 2 |
| 5 | `0x2327f0` | 3 |
| 6 | `0x232d08` | 4 |
| 7 | `0x232d10` | 5 |
| 8 | `0x232d18` | 6 |
| 9 | `0x232d20` | 8 |
| 10 | `0x232d28` | 9 |

The loader does not tie a file number to a slot: the hook address is in the
file. The third column is what the 509 files of the collection described
below do, without exception.

Around the slots the original's chain does this, in order:

1. `0x239490`: saves `k0` and `k1` whole, sets `ra = 0x21a640`.
2. `0x232790`: its "emode" checks.
3. `0x2327d0`: slots 1 to 5.
4. A first block of its own work, ending with the controller-ID stores.
5. `0x232ce8`: the in-game reset check
   ([POPSTARTER_RESET_WARMBOOT.md](POPSTARTER_RESET_WARMBOOT.md)).
6. `0x232d08`: slots 6 to 10.
7. A second block of its own work (`$SET_TIMINGS`, the built-in fix calls
   and the cheat codes are in it), then `0x2394b0`: restores `k0` and `k1`
   and returns to `0x21a640`.

`0x21a640` is the `di` in the delay slot of the hooked `jal`, so that `di`
runs twice.

The slot at `0x232d08` has other writers. In the original's write order,
last one wins: a fingerprint entry's breakpoint handler call
(`jal 0x01460000`), then a TROJAN file's hook, then the breakpoint call
again from `$BREAKPOINT0`/`$BREAKPOINT1` or a `$VCDID_n` entry, then
`$RESET_WARMBOOT`, whose store takes the slot's place. This order is read
from where each writer sits in the original's launch function; no test runs
the original's whole launch to confirm it.

## What launcHER does

### Reading (same as the original)

`pops_trojan_verdict` (`common/src/pops_external.c`) gives the original's
verdict by the original's rules. The launcher's loop
(`pops_stage_fix_files` in `launcher/src/handler_pops.c`) reads root TROJAN,
root PATCH, title TROJAN, title PATCH, numbers 0 to 9, and for a TROJAN
file:

- Invalid: prints `POPS: <path>: Invalid` and reads the next number.
- Outdated: prints `POPS: <path>: Skipped (outdated)` and reads the next.
- A file that does not open, for any reason, is `NOT FOUND` (debug log
  only) and the next number is read.

A TROJAN file is read as the original reads it (`pops_read_trojan`): the
size from the `lseek` to the end, a failure reading as size 0; the first
`0x40` bytes, with whatever does not arrive left zero; the verdict from
those two (`pops_fix_trojan_header`). So a file whose size or header cannot
be read is Invalid there and here. Only a file that will be applied has its
payload read.

Before this work an Invalid file stopped the launch, and the outdated rule
did not exist.

The skip results share a number with a PATCH result: `POPS_MODE6_SKIPPED`
(a PATCH file's mode 6 not applied under a user `BIOS.BIN`) has the value of
`POPS_FIX_SKIP_INVALID`. The loop only reads the skip results for a TROJAN
file, so such a PATCH file is still applied and not called Invalid
(`test_a_patch_whose_mode_6_is_skipped_is_not_called_invalid`).

### Hosting (where launcHER is stricter)

The original writes any payload to any address. launcHER loads a file only
when it can place it without damaging POPS or itself, and only when the
payload does not name code that exists under POPStarter and not under
launcHER. A file the original would apply and launcHER will not load is
skipped with one line, and the game starts without that fix:

```
POPS: <path> is valid for POPStarter but NOT loaded by launcHER: <reason>
```

A file is loaded when all of these hold:

- load address, entry, hook and size are multiples of 4, and the entry is
  inside the payload;
- the payload lies wholly inside the POPS core (and off POPStarter's two
  parts), or wholly inside the arena `0x01420000..0x01600000` and off
  launcHER's own `0x0143a000..0x01460200`;
- the hook is a word of the POPS core outside the payload, and either
  outside POPStarter's two parts or exactly one of the ten slots (with
  format 2's extra zero words not running past the fifth slot of a run);
- the payload scan (below) finds no reference to POPStarter's 480p
  handler (`0x2394f0..0x239758`), the rest of its second part, the rest of
  its first part, a built-in entry's fix code at `0x01410000`, POPStarter's
  code at `0x0143a000..0x014601ff`, or POPStarter's own program
  (`0x00870000..0x00b00000`);
- when the file hooks a slot or its payload names one: the launch can
  offer the slots (below);
- there is room: at most 20 payloads and `0x6f0000` bytes above the image
  per launch;
- the file is at most 1 MiB, the fix file read buffer. A larger file is
  skipped with the line above ("larger than launcHER's 1 MiB fix file
  buffer"), not read; the original has no limit.

The payload scan (`pops_trojan_scan`) follows the code from the entry and
from every address inside the payload that a jump can reach. It sees direct
`j`/`jal`, constants built with `lui` and `ori`/`addiu`/`addi`/`daddiu`/
`daddi`, loads and stores through such a constant or through POPS's `gp`,
and `jr`/`jalr` of one. **It is a static reading.** An address a payload
computes any other way is not seen, so a file that passes is not proven
independent of POPStarter. `tools/pops_trojan_model.py` is the same scan in
Python; the tests require the two to agree.

### Payloads above the POPS image

A payload inside the core is written into the staged core at once. One in
the arena cannot be written while the launcher is still running there, so
its bytes wait in holding memory and are copied to their address at handoff
(`pops_trojan_copy_out`): after the IOP reboot and the built-in fix code,
before the resident image is installed and the caches are flushed. Every
record is checked again before the first byte is written (inside the arena,
off the staged core, the built-in fix code, the resident image and
breakpoint handler, the holding memory and low memory); if one fails,
nothing is written and the launch stops. Payloads are copied in the order
the files were read, so where two overlap the later file wins, as with the
original's `memcpy`.

| Range | Use during a launcHER launch |
|---|---|
| `0x01000000..` | staged POPS core |
| `0x01410000..0x01420000` | built-in entry's fix code |
| `0x01420000..0x01600000` | TROJAN arena |
| `0x0143a000..0x01460000` | launcHER's resident image (inside the arena, never given to a payload) |
| `0x01460000..0x01460200` | breakpoint handler (same) |
| `0x01700000`, `0x01780000` | IOP buffers |
| `0x01800000..0x01ef0000` | raw `POPS.ELF` input until the core is staged; then the TROJAN holding memory |
| `0x01ef0000..0x01f00000` | work memory of the payload scan |
| `0x01f00000..0x02000000` | fix file read buffer (1 MiB) |

Other work on this branch must not start using `0x01800000..0x01f00000`
between fix-file staging and handoff.

### The slots under launcHER

launcHER has none of POPStarter's code in the POPS core. For a launch in
which a loaded file hooks a slot or names one, it:

- writes the two runs at POPStarter's addresses (`0x2327d0` and `0x232d08`,
  `0x30` bytes each): the five slot pairs, then `j <resume>; nop` back
  into the resident image. Both runs lie inside a function of POPS
  (`0x232790`) that POPStarter also overwrites. A static reading of the
  owner's POPS core finds no `j`/`jal`, no address word and no
  `lui`+`addiu`/`ori` pair that points into `0x232790..0x232ec8`, and the
  function before it ends with `jr ra` (`OriginalSlots`, needs
  `POPS_TEST_ELF`); that is the whole basis for calling the function
  unused;
- re-points the GP1 hook at `0x21a63c` from the usual resident entry to
  the chain entry (`gp1_chain_entry` in the resident header).

Both runs are checked first: their `0x30` bytes must still be POPS's own
(an FNV-1a sum of each), and the GP1 hook must be the expected `jal`.
Otherwise nothing is written; a file that needs a slot is then skipped with
the line above. A launch with no such file is not touched: no run is
written and the GP1 hook keeps its usual target.

The chain entry (`pops_resident_gp1_chain` in
`common/src/pops_resident_engine.c`) does the same work in the same order
as launcHER's usual GP1 entry, with the two runs called where the original
has them. The instructions that decide what a payload finds in `k0`, `k1`
and `ra` (the save at `0x239490`, the emode checks, the reset check, the
restore at `0x2394b0`) are the original's, instruction for instruction; the
rest is launcHER's C code, called with every caller-saved register, `HI`
and `LO` kept.

The slot at `0x232d08` follows the original's write order given above. When
`$RESET_WARMBOOT` or a breakpoint command replaces a file's hook there,
launcHER says so in the launch log.

Resident image version 16, header 124 bytes (three new words:
`gp1_chain_entry`, `gp1_resume_a`, `gp1_resume_b`).

## A collection of real files

`tools/test_pops_trojan_corpus.py` reads every `TROJAN_<n>.BIN` and
`PATCH_<n>.BIN` below the folder `POPS_TROJAN_CORPUS` names (never writes,
never copies) and prints counts. On the owner's collection, 2026-11-11:

| | Unique (content + file number) | Copies |
|---|---|---|
| TROJAN files | 509 | 3,952 |
| Loaded by launcHER | 367 | 3,744 |
| Not loaded: uses POPStarter's 480p handler | 120 | 158 |
| Not loaded: uses POPStarter code at `0x238a90..0x2397ef` | 17 | 36 |
| Not loaded: uses POPStarter code at `0x0143a000..0x014601ff` | 5 | 14 |

- All 509 hook one of the ten slots, so all 367 loaded files need the slot
  chain. 507 are format 1; 2 are format 3 revision 6.
- Payloads load at `0x01431000..0x0152c3c0`; files are 112 to 770,304
  bytes.
- Through the original's loader (Unicorn): 509 of 509 applied. For the 367
  launcHER loads: the same slot words, the same payload bytes at the same
  address, and no other byte changed.
- PATCH files: 10 unique (870 copies). All 10 are applied by launcHER and
  leave the whole POPS image equal to what the original's PATCH loader
  (`FUN_00881de8`) leaves. PATCH handling was not changed by this work;
  this is the check that it still comes out the same.

"Loaded" means placed and hooked as the original places and hooks it. What
a payload then does while the game runs was not run anywhere: not on a
console, not in an emulator.

## Evidence

| What | How | Result |
|---|---|---|
| Verdict rules, hook words | `test_pops_trojan.py` `Native`, 41 generated files; each of the 64 header bytes changed alone | as the rules above |
| Same files on the original | `Original`, Unicorn | same verdict, same hook words, same changed bytes |
| Short files | `Original` and `Source`: 0, 1, `0x40`, `0x43` bytes | Invalid, next number read, on both |
| Slot words after the loader | `OriginalSlots`, Unicorn | launcHER's set equals the original's ten slot pairs |
| Slot chain, built image alone | `check_pops_resident_image.py` section "resident TROJAN slot chain" | PASS, 142 cases, 700 slot records |
| Slot chain against the original's | same tool with the reference inputs | PASS, 71 cases, 350 slot records; one known difference (below) |
| Installing the slots | `Native`, on made-up bytes with the expected sums | the two runs and the GP1 `jal` written, nothing else |
| Handoff copy | `Native` | every record checked before the first write; null pointer refused |
| The launcher's loop | `Source`: the real loop compiled for the host with real files | skip lines, order, read errors |
| Device failures | `Source` with failing `open`, `lseek` and `read` put in; `Original.test_device_failures` on the original | not found, Invalid, payload read error, as listed under the loader and below |
| Real files | `test_pops_trojan_corpus.py` | table above |

The resident image was built by the project's container build
(`ghcr.io/ps2homebrew/ps2homebrew:main`, 7,504 bytes); the whole
`launcHER.elf` built there is 331,284 bytes. The build's warnings are all
in code this work did not change.

## Known differences from the original

1. **142 of the 509 files examined (208 of 3,952 copies) are not loaded.**
   They use POPStarter's own code, which launcHER does not contain. The
   launch goes on without them and says so.
2. launcHER refuses addresses the original accepts: anything not a multiple
   of 4, an entry outside the payload, a payload or hook outside the places
   listed above, a hook of 0.
3. A TROJAN file whose payload read fails stops the launch. The original
   does not check that read and applies the file with whatever its buffer
   held. Every earlier failure (open, size, header) is handled as the
   original handles it. A PATCH file's read error also stops the launch;
   PATCH reading was not changed by this work.
4. A TROJAN file over 1 MiB is skipped with the line above (the read
   buffer's size). The original has no such limit and applies it. The
   largest file examined is 770,304 bytes.
5. On the frame of a disc swap, a payload at slots 6 to 10 finds `a0`, `ra`
   and `v0` different from the original's, and `a0` and `v0` differ at the
   return; the stores are the same. Measured on `r5900_mini`; every other
   case and register is equal.
6. Inside the chain launcHER keeps `ra` across its first block of work,
   where in the original it is whatever the slots left, and does not keep
   `k0` and `k1` across the second (the original's own code there uses
   them too). The comparison found no register difference at any slot
   from this, apart from item 5. It covers what a payload finds at its
   slot and at the return, not a payload that reads these registers later
   through some other hook of its own.
7. The original's payload buffer leak (`malloc` never freed) is not
   reproduced; launcHER allocates nothing.
8. PATCH files that the original would call Invalid still stop the launch.
   Only TROJAN reading was changed.

## Not done, not known

- No console run of any of this. The first one should be a file from the
  loaded class on a slot, then an unloaded file (the skip line), then a
  launch without any TROJAN file (must be unchanged).
- Hosting the 142 unloaded files needs POPStarter's 480p handler and the
  rest of its second part, or equivalents of them. Not started.
- Whether POPS's own heap or stack ever reaches the arena was not
  measured. The original puts the same payloads at the same addresses, so
  the risk is the same as there, but it was not looked at.
- launcHER patches POPS core words that POPStarter leaves alone or patches
  differently. Whether any loaded payload reads or rewrites one of those
  words was not analysed.
- The scan is static (see above).
- The image checkers (`tools/check_pops_resident_image.py`,
  `tools/check_pops_progressive_image.py`) need an EE compiler and are not
  run in CI.

## Running the tests

```
python tools/test_pops_trojan.py
python tools/test_pops_trojan_corpus.py
python tools/check_pops_resident_image.py <pops_resident.bin>
```

Optional inputs: `POPSTARTER_TEST_ELF` and `POPS_TEST_ELF` (the original's
side), `POPS_RESIDENT_BIN` or `POPS_EE_CC` (the built resident image),
`POPS_TROJAN_CORPUS` (a folder of fix files). Without them the matching
tests are skipped and say so.
