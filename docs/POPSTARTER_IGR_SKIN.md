# POPStarter r13's IGR menu skin (`IGR_BG.TM2`, `IGR_NO.TM2`, `IGR_YES.TM2`)

Measured on the original (POPSTARTER.ELF MAIN and POPS.ELF, external inputs)
on 2026-11-11 and copied into launcHER for POPStarter launches. Ember
launches never reach this code. Nothing here was tested on a console: every
result below is a host test or the original's code run under an emulator
with its file I/O modelled.

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
(no other `jal`, `j` or pointer to it in MAIN). The earlier mapping of that
function puts the call after the POPS core is in memory and before the OSD
image, `BIOS.BIN`, the fix files and the commands; only the call and its
gates were read again here. The call is made when the shared
abort flag `gp+0x38dc` is 0 (`0x876a84`) and the launch function's local at
`fp+0x1108` is 1 (`0x876a90`); that local is set at `0x8712ec` when the
preset byte at `0x10002d` is 1, which it is in the MAIN profile's file.

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
   - seek to the start, zero the whole slot, read `slot` bytes into it
     (result not checked), zero from `slot + size` to the end of the slot
     again, print `LOADED`;
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
  open, size by seeking to the end, refuse a size above the limit before
  anything is read, seek to the start, read into the 1 MiB scratch buffer at
  `0x01f00000`, stage what arrived. Missing, too big or unreadable is logged
  in debug builds and never stops the launch.
- It is called once in `launchPOPS`, right after the always-on launch hooks
  and pokes and before the runtime corrections, the built-in list, the
  commands, the fix files, the PS1 BIOS shell edits, the region change,
  `$RESET_WARMBOOT` and the opcode pass. This is the original's position
  relative to the stages launcHER has; the OSD image and `BIOS.BIN`, which
  the original handles next, do not exist in launcHER yet.

### Where the files go

The original reads the device's `POPS` folder: `pfs1:/POPS/` on its HDD
backend (which partition is mounted as `pfs1:` was not traced here; the
project's notes say `hdd0:__common`) or `mass:/POPS/`. launcHER reads the
three files from the folder the launched VCD is in, the same folder it reads
the all-games `TROJAN_n.BIN` and `PATCH_n.BIN` from. This is a stand-in
until launcHER has the HDD `__common` layout. When the VCD itself is in
`mass:/POPS/` the two are the same folder.

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
- A read that delivers less than the file's size leaves what arrived
  followed by zeros.

## Not the same as the original

- No gate: launcHER has no shared abort flag and no preset byte `0x10002d`,
  so it always tries the three files. The POPS-folder check and its fatal
  -666 path are not copied.
- The folder (above).
- A failed size query. The original takes the negative result as a size:
  it zeroes the slot and that many bytes below it and prints `LOADED`
  (measured for -5 on `IGR_NO.TM2` and -1 on `IGR_YES.TM2`, where the bytes
  below are the end of the previous slot; not run for `IGR_BG.TM2`, where
  they would be POPS data before the first slot). launcHER leaves the slot
  alone.
- The original issues one read of the whole slot size. launcHER reads the
  file's size in pieces of at most 64 KiB and stops at the first short or
  failed read. A device that returns a short count and would deliver more on
  a second call gives a fuller slot in launcHER than in the original.
- A failed seek back to the start: launcHER stages 0 bytes (slot all zeros).
  The original does not check that seek and reads from wherever the file
  position is (read from its code; this case was not run).
- Messages are debug output with different text, not the original's screen
  log.
- launcHER's default in-game reset is its own direct exit, so without
  `$IGR0..2` the skin is never seen. Under the original the default opens
  Sony's dialog.

## Evidence

`tools/test_pops_igr_skin.py` (in CI), 30 tests; 14 need no inputs.

- Native: the table; sizes 0, 1, max-1, max, max+1, slot and slot+1 for each
  of the three files (12 accepted, 7 refused, the rest of the core
  untouched); `-ERANGE` on short cores; arguments.
- Original's instructions (`POPSTARTER_TEST_ELF`): the three paths for both
  backends, fill and read addresses and lengths and the size tests are
  decoded from the loader and equal launcHER's table; one caller; the gate
  words; the three message strings.
- Original run (`POPSTARTER_TEST_ELF`, `POPS_TEST_ELF`, unicorn): the loader
  runs as shipped over the real core with open, seek, read and close
  modelled (`tools/trace_original_pops_igr_skin.py`). In 45 runs over both
  backends, with every boundary size, seeded random sizes and contents, no
  files, and a core filled with noise, the whole core after the run is
  byte-identical to what `pops_igr_skin_stage` leaves, the printed outcome
  maps to launcHER's result (`NOT FOUND` / `TOO BIG !` / `LOADED` to absent /
  `-EFBIG` / 0; each outcome seen for each file on each backend), nothing
  outside the core and the stack changes and every file is closed. Nine
  more runs cover the gates (4), a short read (3) and a failed size query
  (2).
- Sony's own files (`POPS_TEST_ELF`): the three TIM2 headers in the real
  core and that their sizes are the original's limits.
- Nothing else launcHER stages writes inside `0x2feff0..0x34ee70`: the
  built-in list (257 core writes of 906 operations, all below `0x21b000`;
  all 624 entries applied), the always-on hooks and pokes, the opcode pass
  and the `$RESET_WARMBOOT` scan on synthetic cores; with `POPS_TEST_ELF`
  also the core patches, 80 command lines, the PS1 BIOS shell edits, 72
  region and video combinations, `$LOAD_PADMAN` and one whole launch order
  with a skin staged. Not checked: user fix files (`TROJAN_n.BIN`,
  `PATCH_n.BIN`), which can write anywhere and run after the skin as in the
  original, and the resident display, widescreen and progressive hooks.
- Source: one call in `launchPOPS` at the position above; the reader tests
  the size before it reads; the file is in the CMake list and CI.

Not measured: anything on a console. In particular that POPS shows a
replaced image correctly, and that YES and NO in Sony's dialog behave under
launcHER's resident code with `$IGR0..2`, are untested.
