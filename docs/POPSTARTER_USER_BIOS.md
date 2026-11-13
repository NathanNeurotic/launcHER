# POPStarter r13's user `BIOS.BIN`

Measured on the original (POPSTARTER.ELF MAIN, external input, gp
`0x9b68f0`) on 2026-11-11 by running its own code under Unicorn on the real
POPS core (`tools/trace_original_pops_user_bios.py`), and copied into
launcHER for POPStarter launches (`launchPOPS`). Ember launches never reach
this code. Nothing here was tested on a console, and no PS1 BIOS was used:
every file in the tests is a counter pattern.

There is no integrity check. The only test the original makes on the file
is its size.

## 1. The loader (`FUN_0088019c`, `0x88019c..0x880a20`)

`a0` is the folder (1 = the game's folder, anything else = the all-games
folder), `a1` the game's name.

| Step | What it does |
|---|---|
| Path | `pfs1:/POPS/BIOS.BIN` or `pfs1:/POPS/<game>/BIOS.BIN` on the HDD (`gp+0x3448 == 0`), `mass:/POPS/...` otherwise. Measured with the plain `POPS` folder (`gp+0x381c == 0`) |
| Open | flags 1 (read only). A failed open prints `NOT FOUND` and returns 0 |
| Size | `lseek(fd, 0, END)`, then `lseek(fd, 0, SET)`, whose result is not looked at |
| Size test (`0x88089c`: `slt` against `0x7ff8e`, built at `0x880894..0x880898`, branch at `0x8808a0`; both back ends) | loads when the END result, as a signed 32-bit value, is more than `0x7ff8e`. Otherwise prints `<path> is too small`, closes and returns 0. A failed lseek (`-1`, `-5`) and `0x80000000` or more are "too small"; `0x7fffffff` loads |
| Read | one `read(fd, 0x24bc20, 0x7ff90)` straight into POPS. Its result is not looked at |
| After | sets `gp+0x38a4` (all-games) or `gp+0x3b98` (game), writes halfword `0x1000` at `0x20079a` without looking at what was there, prints `User BIOS == <path>`, closes, returns 1 |

So:

- The smallest file that loads is `0x7ff8f` bytes; it leaves POPS's own byte
  at `0x2cbbaf`. A file of `0x7ff90` bytes or more fills
  `0x24bc20..0x2cbbaf`, and nothing past that is ever written: the last
  `0x70` bytes of a `0x80000`-byte dump are not loaded, and a `0x100000`-byte
  file loads its first `0x7ff90` bytes.
- No byte of the file is checked. Any file of that size is loaded.
- Outside the ROM range the only change is the word at `0x200798`:
  `0x14400005` becomes `0x10000005`. That is the `bnez v0` after POPS's
  call of its disc init (`0x210540`), the branch that skips the path with
  POPS's `xCdInit failed` message, so after a load that path is never
  taken. What that does in a launch was not worked out.
- Both back ends give the same bytes, return value and flags.

Entry tests, before anything is opened (`0x8801b4..0x8802ac`). The loader
compares each word with 1 (`addiu v0, zero, 1`, then `beq`/`bne`); it is the
launch function's tests in front of the call (section 2) that are `bnez`.

| Folder | Returns 0 without opening when any of these holds 1 |
|---|---|
| all games | `gp+0x38dc` (launch given up), `gp+0x343c`, `gp+0x3430` (all-games OSD replacement), `gp+0x344c` (the game's OSD replacement) |
| game | `gp+0x38dc`, `gp+0x3878`, `gp+0x344c` (the game's OSD replacement), `gp+0x3460` (the game's folder is missing) |

Every `gp`-relative store to the seven loader words of section 3 in MAIN
stores 0 or 1, so in a launch "holds 1" and "is set" are the same thing.
With another value forced into a word (2, `0x80`, `0xff`) the loader on its
own goes on and loads; the launch function's `bnez` in front still skips
the call for every word it tests. `gp+0x344c` for the all-games folder is
the one word only the loader tests, so there, and only there, a value other
than 0 or 1 does not skip the file.

For the game's folder it first looks for the folder itself; when that is
missing it sets `gp+0x3460` and returns `-666` without opening anything.
The two BIOS flags are not entry tests: a second load goes over the first.

## 2. Where the launch calls it

In this order (the calls of the launch function):

| Address | Call |
|---|---|
| `0x876cd8` | `BIOS.BIN` of the all-games folder |
| `0x876d6c`, `0x876e00` | `TROJAN_n.BIN`, `PATCH_n.BIN` of the all-games folder |
| `0x876fd8` | `BIOS.BIN` of the game's folder |
| `0x877078`, `0x877118` | `TROJAN_n.BIN`, `PATCH_n.BIN` of the game's folder |
| later | the user's commands (`CHEATS.TXT`), the shell edits, the region pass |

The built-in entry for the disc has already run by then. The game's
`BIOS.BIN` therefore loads over the all-games one, over whatever the
all-games `TROJAN`/`PATCH` files wrote into `0x24bc20..0x2cbbaf`, and over
the write at `0x263ca8` (`FUN_008dba90`, called at `0x874aac`, earlier in
the launch function) and a built-in entry's `0x2525b0`.

The launch function has its own tests in front of each call
(`0x876bb4..0x876ce0`, `0x876ea8..0x876fe0`): the all-games call is skipped
for `gp+0x38dc`, `gp+0x343c`, `gp+0x3430`; the game's call for `gp+0x38dc`,
`gp+0x3460`, `gp+0x3878`, `gp+0x344c`. Both are also skipped when any of
eight preset compatibility slots (`gp+0x3434`, `0x3444`, `0x38c8`, `0x389c`,
`0x3708`, `0x397c`, `0x387c`, `0x38d4`) holds 6. Those slots are bytes
`0x100018..0x10001f` of POPSTARTER.ELF's own segment, all zero in MAIN (the
test reads them), so in this build the test never fires. Other builds were
not looked at.

## 3. What the two flags change afterwards

`A` = `gp+0x38a4` or `gp+0x3b98` (a `BIOS.BIN` was loaded). The original's
OSD loader sets four more words; `B` = `A`, `gp+0x3430` or `gp+0x344c`.

| Where | With the flag set |
|---|---|
| Shell edits (`0x878f64..0x878fc4`) | `B`: none of the three (`0x263ed6`, `0x263d56`, `0x263db0`) is made |
| Region pass (`0x879034..0x8795f0`), known licence | `B`: `0x2649a0` is not written. The letters at `0x2cbb72` and `0x20f6cc` and the PAL change are made as always |
| Region pass, unknown licence | `B`: `0x264994`, `0x264998`, `0x26499c`, `0x2649a0` and the zero bytes at `0x20f6cc`, `0x20f6d8`, `0x20f6dc`, `0x20f6e0` are not written. `0x2cbb72` is |
| Compatibility mode 6 (`FUN_008dc2c4`) | `A`: nothing is written; it prints "In order to apply the compatibility mode 0x06, please delete BIOS.BIN from the POPS directory" (or "VMC directory", or both). Without `A`: nothing when `gp+0x3704` or the preset `gp+0x3438` is set; otherwise `0x2525b0 = 0x0648` and `gp+0x3704 = 1` |
| `$UNDO_COMPATIBILITY_CODES`, `$UNDO_GAME_FIXES`, `$UNDO_LIBCRYPT_FIX` | `A`: their `0x2525b0 = 0x1bfc` write is left out; every other write is made. They never clear `gp+0x3704` |

`0x2cbb72` is inside the loaded range (file offset `0x7ff52`): the region
letter is written into the user's file. `0x2525b0` is file offset `0x6990`.
`$RESET_WARMBOOT` scans and rewrites the user's bytes like POPS's own.

## 4. launcHER

- `PopsUserRomState` (`common/include/pops_modes_patches.h`) holds the
  seven words: `bios_all`, `bios_game`, the four OSD words and `osd_off`
  (`gp+0x3704`). launcHER has no OSD loader, so only the BIOS flags and
  `osd_off` are ever set in a launch; the functions follow all of them.
- `pops_user_bios_stage()` is the loader after its open: the entry tests,
  the size test, the copy of what the read delivered (at most `0x7ff90`
  bytes), the `0x20079a` write and the flag. `pops_user_bios_skipped()` and
  `pops_user_bios_size_ok()` are its two tests on their own. The first is
  the launch function's tests and the loader's together: set for every
  word, equal to 1 for the all-games folder's `gp+0x344c`.
- `pops_user_bios_load()` (`launcher/src/handler_pops.c`) is the file side:
  open, lseek, the size test on the lseek result, a read of the first
  `0x7ff90` bytes only (in pieces, into the fix-file scratch buffer), then
  the stage call. As in the original a file that is missing, cannot be
  opened or is too small is not an error, the rewind is not checked, and a
  short or failed read still counts as a load of what arrived.
- Folders: launcHER reads `BIOS.BIN` where it reads `TROJAN_n.BIN` and
  `PATCH_n.BIN`. All games: the folder the `.VCD` is in. One game: the
  folder named after the `.VCD` inside it (`<folder>/<name>/BIOS.BIN`).
  These stand in for the original's `POPS/` and `POPS/<game>/`; on a
  `mass:/POPS/` layout they are the same folders.
- Order: inside `pops_stage_fix_files`, each folder's `BIOS.BIN` before
  that folder's `TROJAN` and `PATCH` files, all-games folder first, after
  the built-in entry, as in section 2.
- `pops_stage_user_files()` (`launcher/src/handler_pops.c`) is the part of
  `launchPOPS` that runs the user's commands and reads the user's files,
  as one function so that the host tests can run it on files: the look at
  both `BIOS.BIN` files, the commands, the `$RECOMPILER_ADDON_3/4` jumps,
  `pops_stage_fix_files`, and the check of difference 1 below. It clears
  the state it is given and sets `osd_off` from the built-in entry's mode
  mask. `launchPOPS` calls it once, after the built-in entry, and passes
  the state on to the shell edits and the region pass.
- The shell edits, the region pass, mode 6 (from a command, a `PATCH`
  file, the built-in entry or launcHER's own serial list) and the `$UNDO_`
  commands follow section 3 (`pops_apply_bios_shell_edits_rom`,
  `pops_apply_region_rom`, `pops_apply_compat_modes_rom`,
  `pops_fix_stage_rom`, `pops_apply_undo_tokens_rom`).

Differences from the original:

1. **The commands run before the files.** The original runs the user's
   commands after both loads; launcHER runs them before its fix files (an
   older difference). So that mode 6 and the `$UNDO_` commands see the
   flags they would see there, the launch first asks
   `pops_user_bios_load()` (with no core: nothing is read or written)
   whether each file would load, and gives the commands those two flags.
   If the later loads disagree with that answer the launch stops with
   `-EIO`. When a `BIOS.BIN` is loaded the bytes come out the same,
   because the only command writes inside the loaded range are the
   `0x2525b0` ones and with a load both sides leave them out. When none is
   loaded the order still shows at `0x2525b0`, as it did before this work:
   see 2.
2. **Order of the commands among themselves and against the files**
   (older, not changed here): the original runs the files, then
   `$COMPATIBILITY_0x..` and `$UNDO_..` in the order they are written;
   launcHER applies the `$UNDO_` commands first, then the commands' modes,
   then the files. Over the 270 scenarios of section 5, with no `BIOS.BIN`
   loaded the two end differently in exactly these: a `$UNDO_` command is
   given, the built-in entry did not run mode 6, and mode 6 comes from a
   `PATCH_n.BIN` or from a `$COMPATIBILITY_0x06` written before the
   `$UNDO_` command. The original ends with `0x2525b0 = 0x1bfc` (its
   `$UNDO_` ran last), launcHER with `0x0648`; nothing else differs and
   `gp+0x3704` is 1 on both sides. Examples: a `PATCH_n.BIN` with mode
   byte 6 and `$UNDO_GAME_FIXES` in `CHEATS.TXT`; `$COMPATIBILITY_0x06`
   followed by `$UNDO_LIBCRYPT_FIX`.
3. **Fix-file bookkeeping.** launcHER checks the words its compatibility
   modes replace before each fix file. `0x2525b0` is inside the loaded
   range, so after a load `pops_fix_context_rom_loaded()` takes that one
   word from the core; every site outside the range is still checked. No
   other later stage looks at bytes in the range before writing.
4. **`$NOBOOT` / `$BIOS`** is launcHER's own command (`0x2525b0` back to
   `0x1bfc`). With a `BIOS.BIN` loaded it leaves the word alone, like every
   writer of that word in the original.
5. **Words with no counterpart.** `gp+0x38dc` and `gp+0x3460` are not kept:
   launcHER leaves a launch it gave up on, and a missing game folder is a
   file that does not open. The preset slots do not exist.
6. **Messages.** The original prints its lines through its own print
   routine (unless `gp+0x38b0` is 1); launcHER writes them to its debug log
   only, so on a release build nothing says that a file was loaded, was too
   small, or that mode 6 was left out.
7. **Size of very large files.** The size test is made on the low 32 bits
   of the size, signed, as the original's compare is on its 32-bit lseek
   result. What the original's drivers return for a file of 2 GiB or more
   was not measured.
8. **Width of the state.** The original's words are 32 bits; launcHER
   keeps each as one byte that only ever holds 0 or 1.

The former `$UNDO_COMPATIBILITY_CODES` guard failure was fixed on
2026-11-12 by the owner-selected token-aware expected-state option.
`pops_stage_fix_files` now passes the parsed `$UNDO_` tokens and the BIOS
loader state to `pops_fix_context_init_builtin_rom`. That function replays
the entry's compatibility modes and direct core writes, then the command's
own writes, then the text modes—the order of the existing grouped command
pass. The undo OSD write has the same replaced-BIOS gate as the command
pass; expected mode-6 state is preserved for the command pass's BIOS
look-ahead, and the existing original-word fallback is preserved. Other
unexpected words are still rejected. In particular, the direct writes of
entries 109, 571 and 572 are covered.

Before this fix 294 of 624 applicable entries were refused with `-EINVAL`.
The reference-backed census now accepts all 624 in either command order and
every accepted final-core hash matches the original. The older refusal is
historical evidence in `docs/handoff/2026-11-11/bios-bin-fix-1.md`; it is no
longer an expected test failure. `$UNDO_GAME_FIXES` and
`$UNDO_LIBCRYPT_FIX` retain their OSD behavior. The separate command/file
ordering difference above remains.

## 5. Evidence

`tools/test_pops_user_bios.py`, with `POPSTARTER_TEST_ELF` and
`POPS_TEST_ELF` set (the original's code under Unicorn against launcHER's
functions on the same core; not console runs):

| Compared | Cases | Result |
|---|---|---|
| Loader, 2 folders x 2 back ends x {no file, 0, `0x7ff8e`, `0x7ff8f`, `0x7ff90`, `0x80000`, `0x100000` bytes} x {no flag, each of the 7 flags}: return value, whole core, flags, against `pops_user_bios_stage` | 224 runs, 88 loads | equal |
| Loader with the lseek result forced (`-5`, `-1`, `0x7ff8e`, `0x7ff8f`, `0x7fffffff`, `0x80000000`, `0xffffffff`) | 28 | equal |
| The launcher's reader, built for the host from `handler_pops.c`, on files, against the loader | 14, and both folders through `pops_stage_fix_files` | whole core equal |
| Launch-function tests and loader entry tests together, against `pops_user_bios_skipped`; each preset slot holding 5 and 6 | 16 flag cases; 8 slots x 2 values x 2 folders | equal; only a 6 skips the call |
| Shell-edit slice with every combination of the 7 flags | 131 | bytes equal |
| Region window, 5 licences x `$FORCEPAL` x auto disabled x `$NOPAL` x 9 flag sets | 342, and 18 more outside the four PAL sites | bytes equal |
| Mode dispatcher, mode 6 with all 128 flag combinations and both words, the other modes with each flag | 298 | bytes, `gp+0x3704` and the notice equal |
| `$COMPATIBILITY_0x06` and the three `$UNDO_` commands through the original's command reader, flags preset | 72 | bytes and `gp+0x3704` equal |
| Shell slice, region window (4 licences) and `$RESET_WARMBOOT` pass over a core the loader replaced | 1 load | whole core equal |
| The launch sequence: `pops_stage_user_files` on files against the original's chain (per folder its loader and, for a `PATCH` file's mode byte 6, its mode dispatcher; then its command reader), built-in mode 6 x each folder's `BIOS.BIN` (none, one byte too small, loaded) x `PATCH` mode 6 in neither or one folder x 5 command sets | 270 | 150 with a `BIOS.BIN` loaded: whole core and loader words equal. 92 without: equal. 28 without: `0x2525b0` alone differs (difference 2) |
| Built-in entry + `$UNDO_COMPATIBILITY_CODES`, through `pops_stage_user_files` and the original parser, in both command orders (`tools/test_pops_fix_order.py`) | 624 applicable entries in each order | 0 refused / 624 accepted in each; accepted final-core hashes match the original |
| Launch-function tests, loader entry tests, shell slice, mode 6 and region window with a loader word holding 1, 2, `0x80`, `0xff` | 140 | equal |

The 18 region cases are European licence with auto video disabled and
`$NOPAL` not given, which launcHER's two inputs cannot express; they differ
from the original only in the four PAL sites.

In the launch-sequence row the original's `PATCH_n.BIN` loader is not run:
a file's mode byte 6 is represented by the dispatcher that byte reaches
(`FUN_008dc2c4`). launcHER's side reads a real `PATCH_n.BIN` file.
launcHER's own launch writes (taken from a run with no command and no
file) are set aside; the test checks that they stay outside the loaded
range and outside everything the original's chain changed. The separate
all-entry `$UNDO_COMPATIBILITY_CODES` census is no longer excluded or
expected to fail: its 624 accepted results in each order are listed above.

Without the two inputs the same file checks the functions against the
tables above on synthetic cores, runs the reader from `handler_pops.c` on
files of each size, pins the call order in the source, and runs
`pops_stage_user_files` itself on files (class `Launch`): 432 combinations
of the two `BIOS.BIN` files (none, one byte too small, loaded), `PATCH`
mode 6 in either folder, and 12 pairs of built-in mode 6 and commands,
against what the order of section 4 must leave;
the four `BIOS.BIN` opens in order, with nothing read at the two looks; ten
ways a file can change between the look and the load (each `-EIO`) and
three changes that leave the answer as it was (no error); where the launch
stops on each kind of error; and what is handed to `pops_stage_fix_files`.

Not measured: a console; a real PS1 BIOS in place of POPS's; what POPS does
with a file that is not a PS1 BIOS; the OSD loader that sets the other four
words; builds other than MAIN; the original's launch function run as one
piece (the chain above is its pieces, each started with the words the one
before left); the line of `launchPOPS` that calls `pops_stage_user_files`,
which no host test executes (its text is pinned).
