# POPStarter r13's IGR menu skin (`IGR_BG.TM2`, `IGR_NO.TM2`, `IGR_YES.TM2`)

Measured on the original (POPSTARTER.ELF MAIN and POPS.ELF, external inputs)
on 2026-11-11 and copied into launcHER's `launchPOPS`, which is reached only
for a POPS target (`isPopsTarget`, pinned by the test). Nothing here was
tested on a console: every result below is a host test or the original's
code run under an emulator with its file I/O modelled.

## What the original does

Sony's POPS carries three TIM2 files for its own in-game reset dialog, back
to back in its data. POPStarter's loader `FUN_0087e464` (`0x87e464..0x87eb20`)
copies three user files raw over them:

| File | POPS address | Slot | Largest file accepted | Sony's own file in the slot |
|---|---|---|---|---|
| `IGR_BG.TM2` | `0x002feff0` | `0x4c300` | `0x4c300` (312,064 bytes) | 400x260, picture type 2, 312,048 bytes of TIM2 data after the 16-byte file header, no padding |
| `IGR_NO.TM2` | `0x0034b2f0` | `0x1dc0` | `0x1dbc` (7,612 bytes) | 74x34, picture type 2, 7,596 bytes after the file header, then 4 zero bytes |
| `IGR_YES.TM2` | `0x0034d0b0` | `0x1dc0` | `0x1dbc` (7,612 bytes) | as `IGR_NO.TM2` |

The three slots are one run, `0x2feff0..0x34ee70`.

The loader has one caller, the `jal` at `0x876b18` in the launch function
(no other `jal`, `j` or pointer to it in MAIN). The call is made when the
shared abort flag `gp+0x38dc` is 0 (`0x876a84`) and the launch function's
local at `fp+0x1108` is 1 (`0x876a90`); that local is set at `0x8712ec` when
the preset byte at `0x10002d` is 1, which it is in the MAIN profile's file.

### Where the call sits in the launch function

- After the built-in list. The fingerprint lookup-and-apply `FUN_008ff0e4`
  is called only from the launch function, at six sites (`0x8757d4`,
  `0x875d70`, `0x875f78`, `0x8762a8`, `0x876424`, `0x8769ac`), all below
  `0x876b18`; the last one continues with `b 0x876a40`, which runs into the
  call's gate. No branch from before the gate lands past the call, none from
  past the call goes back to those sites, and the function has no `jr`
  through a register other than `ra`.
- Before the config parser `FUN_00883270` (called at `0x8771ac` and
  `0x87724c`). The apply function `FUN_008e00d0` has four more callers
  (`0x890f4c`, `0x8912e4`, `0x8917f0`, `0x891e78`), all inside that parser;
  `docs/POPSTARTER_BUILTIN_DB.md` gives them to `$VCDID_n`. So an entry
  chosen by fingerprint is applied before the skin and one chosen by
  `$VCDID_n` after it.
- The earlier mapping of the function puts the call after the POPS core is
  in memory and the always-on pokes, and before the OSD image, `BIOS.BIN`,
  the fix files and the commands. That part was not read again here.

Inside:

1. If `gp+0x38dc` is 1, return 0.
2. Unless `gp+0x3868` is 1, call the POPS-folder check `FUN_008d8958`; if it
   fails set `gp+0x38dc` to 1 and return -666. (The check itself was not
   traced here; the tests model it as pass or fail.)
3. For `IGR_BG.TM2`, `IGR_NO.TM2`, `IGR_YES.TM2`, in that order, each with its
   own inline copy of the same code:
   - print `    Opening <path>... ` unless `gp+0x38b0` is 1;
   - open `pfs1:/POPS/<name>` (`gp+0x3448` = 0) or `mass:/POPS/<name>`
     (`gp+0x3448` = 1); a negative result prints `NOT FOUND` and moves on;
   - size = seek to the end. `IGR_BG.TM2`: size greater than `0x4c300`
     prints `TOO BIG !`. The other two: size not below `0x1dbd` prints
     `TOO BIG !`. Nothing is read from a file that is too big;
   - seek to the start (result not checked), zero the whole slot, issue one
     read of `slot` bytes into it (count not checked), zero from
     `slot + size` to the end of the slot again, print `LOADED`;
   - close.
4. Return 1.

Nothing is checked about the file's contents or about what the slot held:
no `TIM2` signature, no dimensions, no picture type. A file of 0 bytes is
`LOADED` and leaves the slot all zeros.

A missing or too big file is never fatal; the only fatal path is the folder
check in step 2.

### Where POPS uses the three files

Read from POPS's code, not executed: the dialog's draw function
`FUN_00226768` passes `0x2feff0`, `0x34d0b0` and `0x34b2f0` to its TIM2
upload helper at `0x226d60`. The dialog is opened by the combo check
`FUN_002289e0`: `0x228a20 andi 0x904`, `0x228a50 li 0x904`,
`0x228a54 bne` over the four words at `0x228a5c..0x228a68` that open it.
What POPS does with a slot that does not hold a valid TIM2 file was not run.

## launcHER

- `pops_igr_skin_stage()` and `pops_igr_skin_slot()` in
  `common/src/pops_igr_skin.c` (header `common/include/pops_igr_skin.h`)
  hold the table and the copy: zero the slot, copy `size` bytes. No I/O.
  Returns `-EINVAL` for a bad argument, `-ERANGE` when the staged core does
  not contain the whole slot, `-EFBIG` when the file is larger than the
  original accepts; in each case the core is untouched. As in the original,
  neither the file nor the slot is inspected.
- `pops_stage_igr_skin()` in `launcher/src/handler_pops.c` reads the files:
  open, size by seeking to the end, close and move on if that fails or the
  size is above the limit (nothing is read), seek to the start, read into
  the scratch area at `0x01f00000` in requests of at most 64 KiB until the
  size has arrived or a read returns 0 or an error, close, stage what
  arrived. The largest skin read ends at `0x01f4c300`; the loose-ELF path's
  scratchpad staging at `0x01f80000` is above that. Nothing in the reader
  stops the launch; each outcome is a debug line.
- It is called once in `launchPOPS`, unconditionally:

  | Order in `launchPOPS` | |
  |---|---|
  | core patches | |
  | runtime corrections (`$FIX_*`, launcHER's own) | must come before any other write, see below |
  | always-on hooks and pokes | |
  | built-in entry | fingerprint match or `$VCDID_n` |
  | **IGR skin** | |
  | `pops_stage_user_files`: commands, recompiler add-ons, then per folder (all games, then the game) the user `BIOS.BIN` and the fix files | the `BIOS.BIN` range is `0x24bc20..0x2cbbaf`, below the slots |
  | progressive check, video, PS1 BIOS shell edits and region (both through the `_rom` functions with the loader state), `$RESET_WARMBOOT`, TROJAN slot chain, `MODULE_n.IRX` names, `$LOAD_PADMAN`, SLBB bypass, resident pad/widescreen/progressive/display hooks, opcode pass | |

  This is the original's order for a fingerprint-matched entry. For a
  `$VCDID_n` entry the original applies the entry after the skin and
  launcHER before it; the two orders leave the same core because no
  built-in operation writes inside the three slots (all 624 entries applied
  in both orders, see Evidence).

### The runtime corrections have to come first

`pops_core_runtime_corrections_stage` accepts only the pristine or the
core-patched POPS image as a whole (SHA-256). One skin byte makes it return
-4 with nothing written, and `launchPOPS` treats that as fatal ("Runtime
corrections staging failed"). Measured on the real core: after a 1-byte
file in any of the three slots, all six masks (1, 2, 4, 8, 16, 31) are
refused; in `launchPOPS`'s order, with the stage straight after the core
patches, all six succeed with a skin staged later. The first version of
this feature staged the skin before that stage; the test now pins the order
and runs both.

### Where the files go

The original reads the device's `POPS` folder: `pfs1:/POPS/` on its HDD
backend (which partition is mounted as `pfs1:` was not traced here; the
project's notes say `hdd0:__common`) or `mass:/POPS/`. launcHER reads the
three files from the folder the launched VCD is in, the same folder it reads
the all-games `TROJAN_n.BIN` and `PATCH_n.BIN` from. This is a stand-in
until launcHER has the HDD `__common` layout. When the VCD itself is in
`mass:/POPS/` the two are the same folder. On HDD they are not: a skin kept
in `__common/POPS/`, where POPStarter users have it, is not found.

For `SB.` (SMB) and `XX.` launches the original uses `mass:/POPS/` too.
Its launch function sets the back-end word `gp+0x3448` to 1 for a name
that starts `SB.` or `sb.` (`0x871568..0x871604`, the store at `0x871618`)
and for `XX.` or `xx.` (the store at `0x8719a4`); the only other store to that word
in MAIN is the 0 at `0x870c64`. The loader then opens the literal
`mass:/POPS/IGR_*.TM2` (`0x87e508` tests the word, `0x87e538` opens
through `0x8d6c94`). launcHER reads from the folder of the VCD path it
launches (`vcdDir`), on whatever device that path names. Whether `mass:`
in POPStarter's SMB mode names a USB device or the SMB share was not
traced, so for an `SB.` launch the two may or may not be the same place.
Read from the code, not run.

launcHER has a second stand-in for the same original folder: `MODULE_n.IRX`
is read from the folder POPS.ELF came from (`popsDir`), not from the VCD's
folder. Which of the two the skin should follow is the owner's call.

### When the skin is visible

The skin only shows in Sony's own dialog. launcHER's default in-game reset
is unchanged by this work, and it never opens that dialog. Measured on a
synthetic core and, with `POPS_TEST_ELF`, on the real core through
`pops_apply_all_config_patches`:

| IGR setting | What launcHER leaves at `0x228a54..0x228a68` | Sony's dialog |
|---|---|---|
| no IGR command | launcHER's direct exit written over `0x228a5c..0x228a68` | never opens: the skin is loaded but not shown |
| `$NOIGR` | branch at `0x228a54` made unconditional | never opens |
| `$IGR0`, `$IGR1`, `$IGR2` | POPS's own four words, combo mask `0x404f`, `0x0900` or `0x090f` | reachable: the skin is shown |
| `$IGR3`, `$IGR4`, `$IGR5` | `j 0x20c08c` at `0x228a5c` | never opens |

So a user who wants the skin has to add `$IGR0`, `$IGR1` or `$IGR2`. The
files are still loaded under every setting, as in the original.

## Copied as it is

- No check of the file's contents. Anything up to the size limit is copied.
- A 0-byte file replaces Sony's image with zeros.
- The limit for `IGR_NO.TM2` and `IGR_YES.TM2` is 7,612 bytes although the
  slot is 7,616: a file padded to the slot size is refused.
- The files are loaded even when the dialog can never open.
- A device that delivers part of the file and then nothing more (end of
  file or an error) leaves that part followed by zeros.
- A size query that disagrees with the data: the slot gets the first `size`
  bytes the device delivers, then zeros.
- A read that reports more bytes than were asked for: the count is not
  believed (the original never looks at it).
- A failed seek back to the start that leaves the position at the end of
  the file: the slot is all zeros.

## Not the same as the original

- No gate: launcHER has no shared abort flag and no preset byte `0x10002d`,
  so it always tries the three files. The POPS-folder check and its fatal
  -666 path are not copied.
- The folder (above).
- A failed size query. The original takes the negative result as a size:
  it prints `LOADED`, zeroes the slot and that many bytes below it. For
  `IGR_NO.TM2` and `IGR_YES.TM2` those are the end of the previous slot;
  for `IGR_BG.TM2` they are POPS's own data in front of the first slot
  (run for -1, -5, -16 and -4096 on all three files and both backends).
  launcHER asks nothing more of the file, closes it and leaves the core
  alone.
- A device that returns a short count and has more to give on the next
  call. The original issues one read of the whole slot and does not look at
  the count, so it keeps the first piece only. launcHER asks again until the
  file's size has arrived and stages the whole file. Run on both sides.
- A failed seek back to the start that leaves the position anywhere but the
  end: launcHER stages 0 bytes (slot all zeros); the original reads from
  wherever the position is. Read from its code; not run, because the device
  model leaves the position at the end.
- A read that fails after storing some bytes: not modelled on either side.
- Messages are debug output with different text, not the original's screen
  log.
- launcHER's default in-game reset is its own direct exit, so without
  `$IGR0..2` the skin is never seen. Under the original the default opens
  Sony's dialog.

## Evidence

`tools/test_pops_igr_skin.py` (in CI), 48 tests; 27 need no inputs. The
device model both sides run on is `SkinFile` in
`tools/trace_original_pops_igr_skin.py`: a size the seek to the end
reports, a total the device ever delivers and what a read returns after
that, a most-per-read, a failing rewind, an over-reported count.

- Native (6, no inputs): the table; sizes 0, 1, max-1, max, max+1, slot and
  slot+1 for each of the three files (12 accepted, 7 refused, the rest of
  the core untouched); `-ERANGE` on short cores; arguments.
- Reader (11, no inputs): `pops_stage_igr_skin` itself, the function's text
  taken from `handler_pops.c` and compiled on the host with only its
  scratch address replaced and `open`/`lseek`/`read`/`close` handed to the
  device model. Compared with a Python model of the original (the model is
  held to the original in the Original class below): 16 boundary-size runs
  over both path prefixes, 41 runs with absent files and seeded random sets,
  0-byte files, too-big files (no read call, core untouched), and 40
  misbehaving-device runs on each of two prefixes, three files to a run
  (stops for good 24, size and data disagree 7, failed rewind 4,
  over-reported count 4, one piece that is the whole file 1). The two
  differences are run too: 4 failed-size-query runs (core untouched, file
  closed) and 3 runs with the file in pieces (whole file staged). Every one
  of those runs also checks the calls: the three files in the original's
  order, read
  only, the size asked first, nothing read from a refused file, every
  request at most 64 KiB and inside the file's size, every handle closed
  once, the scratch area never written past the largest file.
- Dialog (2; 1 needs `POPS_TEST_ELF`): the table in "When the skin is
  visible".
- Staging (4, no inputs): the built-in list (257 core writes of 906
  operations, the highest ending at `0x21af71`; all 624 entries applied,
  and applied before and after a skin with the same result), the always-on
  hooks and pokes, the opcode pass and the `$RESET_WARMBOOT` scan on
  synthetic cores write nothing inside `0x2feff0..0x34ee70`.
- Real core (7, `POPS_TEST_ELF`): Sony's three TIM2 headers and that their
  sizes are the original's limits; the stages before the skin leave the
  slots alone, with each runtime-corrections mask as well; the runtime
  corrections refuse a core with a skin; each later stage run on its own
  over a core with a skin read by the reader keeps the skin: 80 command
  lines, the recompiler add-on emit (4), the fix-file context with its
  progressive check and video pass (36 region and video combinations), the
  PS1 BIOS shell edits, 72 region changes, `$RESET_WARMBOOT`, 11
  `MODULE_n.IRX` names, `$LOAD_PADMAN`, the SLBB bypass, the resident pad
  (3), widescreen (3), progressive (3) and display hooks, the opcode pass,
  every one returning success; a fix file aimed elsewhere keeps the skin and
  one aimed at a slot replaces exactly its bytes; 84 launches in
  `launchPOPS`'s order (7 masks by 3 built-in choices by 4 user `BIOS.BIN`
  choices: none, all-games folder, game's folder, both) keep the skin. That
  replay calls the common functions `launchPOPS` calls, with
  `pops_stage_user_files`'s steps written out (commands and fix files
  through the `_rom` variants with the loader state, `pops_user_bios_stage`
  and `pops_fix_context_rom_loaded` for each `BIOS.BIN`); it leaves out the
  TROJAN slot chain (no TROJAN file) and the progressive hook. The same
  launch with the skin staged before the runtime corrections is refused for
  all 6 masks.
- Original's instructions (4, `POPSTARTER_TEST_ELF`): the three paths for
  both backends, fill and read addresses and lengths and the size tests are
  decoded from the loader and equal launcHER's table; one caller; the gate
  words; the order facts in "Where the call sits"; the three message
  strings.
- Original run (9, both inputs and unicorn; a missing unicorn is an error,
  not a skip): the loader runs as shipped over the real core. 141 runs, each
  held to the model over the whole core, with its prints, return value 1,
  nothing else in memory changed and every file closed:
  - 47 with files a device delivers whole (18 boundary, 24 seeded random
    with each outcome forced once per file per backend, 2 with no file, 2
    over a core of noise, 1 quiet): also equal to `pops_igr_skin_stage` and
    to launcHER's reader run on the same files;
  - 80 on misbehaving devices where launcHER is meant to match (the 40 runs
    above on both backends): also equal to launcHER's reader;
  - 8 with a failed size query and 6 with the file in pieces: the original
    and launcHER's reader each do what "Not the same" says.
  Four more runs cover the gates.
- Source (5, no inputs): one call in `launchPOPS`, a bare statement with no
  condition, block or preprocessor conditional around it, after the core
  patches, the runtime corrections, the hooks and the built-in entry and
  before every later stage; the reader is static with that one caller and
  `launchPOPS` is called only behind `isPopsTarget`; the reader's own order
  of calls; the file is in the CMake list and CI.

Mutants (run once, 2026-11-11, on copies of the tree, without the reference
inputs): 27 single edits, 6 in `pops_igr_skin.c` and 21 in
`handler_pops.c` (inverted rewind test, count not accumulated, too-big file
falling through, 0-byte file skipped, loop not ending at end of file, four
ways of gating the call, `break` on an over-long path, a larger request,
three leaked handles, limit off by one, over-reported count believed,
staging the reported size, failed size query accepted, files in reverse
order, the call moved above the built-in entry, the call moved above the
runtime corrections). All 27 fail the test file; the unchanged tree passes.

Not measured: anything on a console. In particular that POPS shows a
replaced image correctly, that YES and NO in Sony's dialog behave under
launcHER's resident code with `$IGR0..2`, and how launcHER's own I/O stack
delivers a 312 KiB file, are untested.
