# POPStarter r13's text files: CHEATS.TXT commands, `$USBDELAY_n`, VMCDIR.TXT

Measured on the original (POPSTARTER.ELF MAIN, external input, decoded image
at `0x870000`) on 2026-11-11, by reading its code and by running that code
under emulation on synthetic text (`tools/trace_original_pops_config_text.py`,
`tools/test_pops_config_text.py`). launcHER copies it, with the differences
listed under "Known differences that remain". What is only read from the
code, not run, says so. Nothing here was tested on a console.

## The reader (`FUN_00883270`)

Called twice: at `0x8771ac` with `a0 = 0` (the CHEATS.TXT "for all games")
and at `0x87724c` with `a0 = 1` and `a1 = gp+0x38f0` (the game's own). The
second call is skipped when `gp+0x38dc` or `gp+0x3460` is set.

- The file is read whole: size from a seek to the end, `malloc(2 * size)`
  (`0x8839f0`), one read of `size + 16` bytes (`0x883a50..0x883a60`). An
  empty file returns early. There is no size or line limit.
- `0x883aa8`: the second half of the buffer is zeroed and the text is
  upper-cased in place (`a`..`z` only).
- A first pass (`0x883b80..0x8859fc`) looks for the `$C0` master code and
  does not change the text.
- The command pass (`0x885a04..0x89e75c`) walks the text one byte at a
  time. At each index:
  1. five cheat-code tests (`0x885a20`, `0x885ccc`, `0x885e28`, `0x8860b4`,
     `0x886360`): a code's columns (14 for `$80`/`$30`/`$D0`/`$5000`, 18 for
     the 8-digit kinds) are stepped over and left for the later code
     passes. A `$C0` code is not stepped over;
  2. otherwise 66 handlers are tried in a fixed order; the first whose
     compare chain holds runs, zeroes the byte at the index and moves ONE
     byte on;
  3. otherwise the byte is zeroed and the scan moves one byte on.
- After the pass (`0x89e75c..0x89e884`) a complete manual GS DISPLAY set is
  written.
- **A file of a few bytes is read past its buffer.** A code test at a `$`
  reads up to column 14 from it (column 9 after columns 1..3), and only
  `2 * size` bytes are the buffer. For a `$` at offset `i` with
  `i + 9 >= 2 * size` (so only in files of 8 bytes or less) the bytes it
  reads are whatever the heap holds after the buffer, and they decide
  whether that `$` starts a code. Measured with other bytes put there: 357
  texts of 1..8 bytes, 4 heap patterns: in 17 of the 1428 runs such a `$`
  is stepped over as a code (`$800` with spaces after the buffer is a
  14-column code); no command is taken or lost in any of them (a command
  needs at least 5 bytes, which leaves no room for such a `$` before it).
  Whether the later code passes then compile such a code was not run.

So there are no lines, no tokens and no comments:

- a command is taken at any `$` that is not inside a cheat code's columns,
  whatever precedes it: `#$SMOOTH`, `; $SMOOTH` and `x$SMOOTH` all apply;
- a command ends at CR, LF, NUL, a space or the next `$`
  (`$SMOOTH$SCANLINES` is two commands); a TAB does not end one
  (`$SMOOTH<TAB>` is nothing);
- a command inside a code's columns is not seen
  (`$20012345 00$SMOOTH` is one 18-column code);
- lower case is the same as upper case.

## The 66 handlers, in order

`name` + terminator unless noted. The address is where the handler ends.

| Ends at | Form |
| --- | --- |
| `0x8866a0` | `$SMOOTH` |
| `0x888048`..`0x890110` | `$DX_` `$DY_` `$MAGH_` `$MAGV_` `$DW_` `$DH_` + 1..5 digits. Each handler is not tried again in the same file once it took a value (`fp+0xfc..0x110`) |
| `0x89030c` | `$480` + `P` + terminator (not tried when `gp+0x3880` is set; the only store to it found in the image is the start-up clear at `0x870ca4`). Stores `gp+0x38a0` = 0 (forced PAL off), `gp+0x4fa0` = 0 (automatic PAL off), `gp+0x3864` = 1 (480p), `gp+0x38d0` = `gp+0x3898` = 1, and makes four pokes |
| `0x890a34` | `$LEFTADJ_` + 1..3 digits; applied for 1..255 only |
| `0x890c48` | `$SCANLINES` |
| `0x891e98` | `$VCDID_` + 1..4 digits; not tried once `gp+0x38d8` is nonzero, so `$VCDID_0` does not stop the next one |
| `0x892118`..`0x894240` | `$SUBCDSTATUS` `$RESET_WARMBOOT` `$MUTE_CDDA` `$MUTE_VAB` `$CODECACHE_ADDON_0..2` `$RECOMPILER_ADDON_0..4` |
| `0x894528` | `$ORIGINAL_OPCODES`: the terminator is tested at column 19, not 17 (see quirks) |
| `0x894aa4`..`0x897ca8` | `$UNDO_COMPATIBILITY_CODES` `$UNDO_GAME_FIXES` `$UNDO_LIBCRYPT_FIX` `$UNDO_MUTE_CDDA` `$WIDESCREEN` `$ULTRA_WIDESCREEN` `$EYEFINITY` `$ROLLBACK` `$SET_TIMINGS` `$BREAKPOINT0` `$BREAKPOINT1` `$NOVMC0` `$NOVMC1` `$NOPAD0` `$NOPAD1` `$D2LS` `$D2LS_ALT` `$IGR0`..`$IGR5` `$NOIGR` |
| `0x8982b4` | `$PAD` + `0` or `1` + `ID_0X` + two bytes + terminator at column 12; applied only when both bytes are hex digits |
| `0x8984a4` | `$MUTE_ALL` |
| `0x898628` | `$NOPAL`: one store, `gp+0x4fa0` = 0 (`0x89860c`) |
| `0x89882c` | `$FORCEPAL`: always taken; its three stores (`gp+0x38a0`, `gp+0x38d0`, `gp+0x3898` = 1) are made only while `gp+0x3864` is 0 (`0x8987f0`), see quirks |
| `0x89a2d0` | `$` + any byte + `POS_` + 1..5 digits; the second byte (`X` or `Y`) is looked at afterwards (see quirks) |
| `0x89b604`, `0x89c918` | `$DWSTRETCH_`, `$DWCROP_` + 1..4 digits |
| `0x89cae8`, `0x89ccc0` | `$CACHE1` `$FAKELC` |
| `0x89cec8`, `0x89d0f0` | `$SAFEMODE`, `$SAFEMODE2`: neither is tried while one of the two is on in this file (`fp+0xec`, `fp+0xf0`) |
| `0x89d34c` | `$NOSAFEMODE`: not tried unless `gp+0x386c` is 1 |
| `0x89d534`..`0x89dbcc` | `$HDTVFIX` `$NOHDTVFIX` `$LOAD_PADMAN` `$KILL_PADMAN` |
| `0x89e13c` | `$USBDELAY_` + exactly one digit + terminator |
| `0x89e734` | `$COMPATIBILITY_0X` + two bytes + terminator at column 19; the mode function `FUN_008dc2c4` is called only when both bytes are hex digits, and pokes something only for 1..7 (after `$SUBCDSTATUS`: 4, 6, 7) |

A numbered command whose digits are missing, too many, or not followed by a
terminator does nothing (the scan still moves one byte on). The exception is
`$XPOS_` / `$YPOS_`.

## Quirks (copied)

- **`$ORIGINAL_OPCODES` tests the terminator two columns late.** Any two
  bytes may follow the name. `$ORIGINAL_OPCODES` + CR LF + a command is
  taken; `$ORIGINAL_OPCODES` + LF + `$SMOOTH`, and `$ORIGINAL_OPCODES` +
  space + `$SMOOTH`, are not (column 19 is a letter). `$ORIGINAL_OPCODESXY `
  is taken. At the end of a file it is taken.
- **`$XPOS_` / `$YPOS_` with a malformed number write a stale value.** The
  number commands share one temporary (`fp+0x90`). When the digits are not
  1..5 digits and a terminator, the X or Y write still runs with what the
  temporary holds: 0 at first (the game's own file starts with the length
  of the string at `gp+0x38f0`, `0x883430`; that string is the game's
  folder name plus a `/`, built at `0x874ddc..0x8750e4`, so the start is
  the name's length plus one), else the last value of a well-formed
  `$LEFTADJ_n` (any n), `$?POS_n` (also `$ZPOS_n`), `$DWSTRETCH_n`,
  `$DWCROP_n`, `$PADnID_0Xhh` or `$COMPATIBILITY_0Xhh`. So `$XPOS_-15`
  writes X = 0, `$LEFTADJ_12 $XPOS_Q` writes X = 12, and either takes the one
  X write. A value above 65535 writes nothing and does not take it.
- **Only the first of `$SAFEMODE` / `$SAFEMODE2` in a file counts**;
  `$NOSAFEMODE` re-opens both.
- **`$COMPATIBILITY_0X08`..`0XFF` and `0X00` do nothing**, as does a
  one-digit `$COMPATIBILITY_0X5`.
- **Nothing is a comment.** `#` and `;` hide nothing.
- **`$USBDELAY_` takes one digit only.** `$USBDELAY_12`, `$USBDELAY_05`,
  `$USBDELAY5` and `$USBDELAY_` are not commands.
- **`$FORCEPAL` does nothing after a `$480P`.** `$480P` sets `gp+0x3864`
  and nothing in the pass clears it, so a later `$FORCEPAL`, in the same
  file or in the game's own file after a `$480P` in the one for all games,
  is taken and stores nothing: `$480P $FORCEPAL` is 480p without forced PAL.
  `$FORCEPAL $480P` ends the same way, since `$480P` clears the forced-PAL
  word.
- **`$NOPAL` does not undo `$FORCEPAL`.** It clears only the automatic-PAL
  word. The region pass (read from the code, not run) tests the forced-PAL
  word first: `gp+0x38a0` == 1 with `gp+0x3864` == 0
  (`0x879034..0x879048`) takes the forced-PAL path, which ends at
  `0x8795f0` without reading `gp+0x4fa0`; otherwise a European disc goes
  PAL only while `gp+0x4fa0` is 1 (`0x87930c`). So `$FORCEPAL $NOPAL` and
  `$NOPAL $FORCEPAL` are both forced PAL. These are the only loads of
  `gp+0x38a0` and `gp+0x4fa0` in the image.

## `$USBDELAY_n`

### The command (run under emulation)

Handler `0x89dbd4..0x89e13c`: `$USBDELAY_` + one digit `0`..`9` + a
terminator. It stores the digit in the byte at `0x100017` and nothing
else; the shared number temporary is left alone. The last one in the files
wins. 20 fixed texts and the random texts of
`tools/test_pops_config_text.py` compare that byte with launcHER's
`usb_delay` / `usb_delay_set`.

`0x100017` is file offset `0x417` of POPSTARTER.ELF. It is `0x01` as shipped
in the four profiles looked at (MAIN, DEBUG, USBDELAY, USBDELAY_DEBUG), so a
launch with no `$USBDELAY_n` has 1 there. The USBDELAY profiles differ from
MAIN at `0x100013` (`0x06` against `0x02`), which is another byte.

### What the original does with the byte (read from the code, not run)

All in `main` (`0x870b78`):

- `0x879cf0..0x879e58`: if `gp+0x3888` is 1 the byte is set to 0 first (the
  stores to `gp+0x3888` found in the image write 0 or 3, never 1). Then, only
  when `gp+0x3448` is not 0, the embedded module at image `0x91f680`
  (`gp+0x2890` = `0xa45` bytes) is searched four bytes at a time for the
  bytes `D` `L` `A` `Y`; where they stand, the word becomes the byte from
  `0x100017` followed by three zero bytes. The module has one such word, at
  image `0x91fb30` (module address `0x420`).
- `0x87c030..0x87c054`: only when `gp+0x3448` is 1, that module is started
  from memory (`0x91c248`), then wiped.
- `gp+0x3448` is set to 1 in two places only: `0x871618` (the launch name
  after the last `:`, `/` or `\` starts with `SB.` or `sb.`) and `0x8719a4`
  (`XX.` or `xx.`). So the word is patched and the module is started for
  the USB (`XX.`) and SMB (`SB.`) launch names and for no other; an HDD
  launch does neither, and `$USBDELAY_n` then changes nothing but the byte.
  That every `XX.` / `SB.` launch reaches both places was not traced.

The module is an IOP module named `PFS Wrapper r6a`. Its code at module
address 0: `WaitSema`; if the word at `0x540` (1 as shipped) is not 0: take
the word at `0x420`; if it is still the four letters `DLAY`
(`0x59414c44`), use 5; `DelayThread(value * 1000000)`; clear the word at
`0x540`; `SignalSema`. So the delay happens once, in the IOP module, the
first time that code runs: n seconds after a patch (1 as shipped, 0 for
`$USBDELAY_0`), 5 seconds had the word never been patched. What calls that
code (which file operation) was not traced.

### launcHER

- The parsed value is the original's: `usb_delay` is the digit and
  `usb_delay_set` says one was taken. Without the command `usb_delay` stays
  0; the original's shipped 1 is not modelled.
- What launcHER does with it is NOT the original's and was not changed
  here: `handler_pops.c` calls `sleep(cfg.usb_delay)` on the EE before the
  launch when the value is above 0, for every device. There is no patched
  wrapper word and no delay in an IOP module. Matching the original's
  timing (a one-time IOP delay on USB and SMB launches only, 1 second when
  no command is given) needs a console to judge and is a follow-up.
- `pops_config_load_table` / `pops_config_export_table` (used by tests
  only) put `usb_delay` in table byte 3 (`0x100013`). `$USBDELAY_n` writes
  `0x100017`, which is table byte 7. Reported, not changed.

## launcHER

- `pops_config_parse_text()` (`common/src/pops_config.c`): the same pass on
  an upper-cased copy of the file: the five code tests, then the handler
  table in the original's order (`pops_commands[]`), one byte on after each.
  `load_config_file()` reads the file in binary and has no line limit. The
  copy has 32 zero bytes after the text, so a short file reads zeros where
  the original reads its heap.
- The three video words are `video_mode` and `progressive_requested` as
  the launch reads them (`handler_pops.c` passes `POPS_VMODE_480P` when
  `progressive_requested` is set; `pops_modes_patches.c` forces PAL for
  `POPS_VMODE_NTSC2PAL` and keeps a European disc at PAL unless the mode is
  `POPS_VMODE_NOPAL` or `POPS_VMODE_480P`), plus `forced_pal` for the
  original's forced-PAL word, which only `$NOPAL` reads. `$FORCEPAL` does
  nothing while `progressive_requested` is set; `$NOPAL` keeps
  `POPS_VMODE_NTSC2PAL` while `forced_pal` is set. Whether every other
  reader of `video_mode` in launcHER agrees with that mapping was not
  analysed.
- The shared number temporary is the function's `value` argument: 0, or
  `strlen(game folder) + 1` for `<game>/CHEATS.TXT` (`pops_config_discover`).
  So a game folder `Game` with `$XPOS_` and nothing after it writes X = 5.
- launcHER's own tokens (`$NOBOOT`, `$BIOS`, `MODE n`, `$MODE n`, `$MODEn`, a
  bare digit, `$DITHER_OFF`, `$NODITHER`, `$FASTMIPS`, `$SLOWMIPS`,
  `$PAL2NTSC`, `$FORCENTSC`, `$NTSC2PAL`, `$FIX_*`, `$CORE_FIXES`,
  `$PSXCORE_FIXES`) are not POPStarter's: the original takes none of them.
  They keep launcHER's earlier rules (split at white space, `#` or `;`
  starts a comment) and are applied in file order with the original's
  commands. White space there is space, TAB, LF, VT, FF and CR, tested as
  bytes (not with the C library's `isspace`, which follows the locale for
  bytes above `0x7f`), and a run of more than 63 non-blank bytes is no
  token at all (it used to be cut at 63 bytes and its tail read as a new
  token, so 63 bytes and a `1` set mode 1). Their video tokens set
  `video_mode` only: `$NTSC2PAL $NOPAL` gives `POPS_VMODE_NOPAL`, as before.
  So they are not the original's `$NOPAL` / `$FORCEPAL`: `$FORCEPAL
  $PAL2NTSC` gives no PAL, while `$FORCEPAL $NOPAL` stays forced PAL.
  Whether they should follow the original's commands is an open owner
  question.
  Whether these tokens are read from CHEATS.TXT at all is an open owner
  decision (`docs/PR23_HANDOFF_2026-11-11.md`, section 8); that was not
  changed.

### Known differences that remain

- launcHER keeps one cheat list and one safe-mode gate for all files; the
  original compiles each file's codes with that file's own gate.
- The cheat codes themselves are still found by launcHER's earlier scan
  (`scan_cheats`), which stops at a NUL byte and also steps over `$C0`
  codes; the original's passes go by the file size. Texts with a NUL byte
  or with a code inside a `$C0` code's columns can differ.
- Files over 1 MiB are refused (`-EFBIG`); the original has no limit.
- `gp+0x3880` (the `$480p` gate) is not modelled.
- The `$FORCEPAL` test knows only the `$480P` commands of the text. The
  original also sets `gp+0x3864` outside the text (read from the code, not
  run): at start-up when the byte at `0x10002a` is 2 (`0x871218`), at
  `0x871718` after a word compare, and at `0x88301c`, `0x8830a4` and
  `0x883174` in the function before the reader. launcHER does not model
  these for `$FORCEPAL`; it applies a fix file's progressive setting after
  the text (`handler_pops.c`). Whether a launch then differs was not
  measured.
- The forced-PAL and automatic-PAL words also have writers outside the
  text (read from the code, not run). The function before the reader
  clears `gp+0x38a0` and `gp+0x4fa0` at `0x883120`/`0x883124` while
  `gp+0x3898` is 0 (`0x883114`; `$FORCEPAL` and `$480P` set that word), and
  sets `gp+0x3864` at `0x88301c`/`0x8830a4`/`0x883174`. Start-up writes are
  at `0x870c80`/`0x870c90` and `0x8711ec`..`0x871230`; further stores of 0
  to `gp+0x4fa0` are at `0x871710`, `0x883014`, `0x88309c`, `0x88316c` and
  `0x8f8abc`. When the function at `0x883000` runs relative to the reader
  was not traced, so whether it changes the video result of a text was not
  measured. The comparison of the video words above holds for the words as
  the text pass leaves them.
- Files of 8 bytes or less: where the original reads its heap after the
  buffer (see above), launcHER reads zeros. Only whether such a `$` is
  stepped over as a code can differ; no command does.

## VMCDIR.TXT (`FUN_008d4f84`)

Run under emulation as a USB launch (`gp+0x3448 = 1`, `gp+0x3868 = 1`) with
the file services answered from synthetic bytes. The HDD path of the same
function (other file calls) was not run.

Called at `0x8772e0` with `a0 = 0` (opens `mass:/POPS/VMCDIR.TXT`, "for all
games") and at `0x877380` with `a0 = 1` (opens
`mass:/POPS/<game>/VMCDIR.TXT`), after the two CHEATS.TXT calls. The second
is skipped when `gp+0x38dc` or `gp+0x3460` is set.

What one file does:

| File | Result |
| --- | --- |
| missing | returns 0, nothing changes |
| 104 bytes or more (the file's size) | message `0x9b1a90`, returns 0, nothing changes |
| CR, LF, `/`, `\` or `:` anywhere in the file, also after a NUL | message `0x9b1ac0`, returns 0, nothing changes |
| anything else, the empty file included | returns 1; POPS's strings at `0x4F8080` and `0x4F8100` become `pfs1:/<name>/` and `pfs1:/<name>/SLOT%d.VMC` |

`<name>` is every byte of the file up to a NUL or the end, as it stands.

- **A name followed by a line end is ignored.** `SAVES` + CR LF, `SAVES` +
  LF and `SAVES` + CR all leave the saves where they were. Only a file with
  no line end at all is used.
- **Ignored is never an abort.** The launch goes on with what it had: the
  game's folder, or the folder a first VMCDIR.TXT gave.
- **Nothing is trimmed.** A space, a TAB, `#`, lower case and bytes above
  `0x7f` are part of the name (` SAVES ` gives `pfs1:/ SAVES /`).
- **`.` and `..` are names** (`pfs1:/../`).
- **An empty file is used**: the strings become `pfs1://` and
  `pfs1://SLOT%d.VMC`, the POPS folder itself.
- The limit is on the file's size: `SAVES`, a NUL and 97 more bytes (103)
  is `SAVES`; with 98 more (104) it is ignored.
- The game's own file follows the same rules and, when used, replaces what
  the first file gave; when ignored, the first file's folder stays.

### launcHER

- `pops_config_parse_vmcdir()` is the same decision on a buffer;
  `pops_config_load_vmcdir()` reads at most 104 bytes in binary and returns
  0 for a file that is ignored (it used to stop the launch with
  `-EOVERFLOW` or `-EINVAL`, to trim the name, to take `SAVES` + CR LF and
  to refuse `.` and `..`).
- `vmc_dir_set` says a file was used; `vmc_dir` may then be empty.
  `handler_pops.c` puts the cards in `<POPS folder>/<name>/`, or in the POPS
  folder itself for the empty name.
- Not the original's: launcHER still looks for cards named
  `<serial>.VMC0` / `<game>.VMC0` beside `SLOT0.VMC` in that folder, and in
  the POPS folder itself a new card is named `<serial>.VMC0`, where the
  original's string is `SLOT%d.VMC`.

## Evidence (host and emulation only)

`python tools/test_pops_config_text.py` with `POPSTARTER_TEST_ELF`:

- the 66 handler names and their order, read from the image, equal
  `pops_commands[]`;
- 169 fixed texts: the original's pass and launcHER's reader report the
  same commands at the same offsets (and whether each changed something),
  the same codes stepped over, the same X, Y, compatibility-mode, game-id
  and `0x100017` values, the same forced-PAL word (`gp+0x38a0`, launcHER's
  `forced_pal`), and the same three video words as the region pass
  reads them. Among them: each condition of the five code tests from both
  sides, and the orders of `$480P`, `$NOPAL` and `$FORCEPAL`;
- 1500 seeded random texts: the same (2876 commands, 399 codes stepped
  over; 96 texts also had a launcHER-only `MODE` token, 20 wrote
  `0x100017`; the video words are not compared in texts that hold a
  launcHER-only video token);
- the video words: 20 texts against a table, 600 seeded random texts, and
  two files (the second run with the first's gp words; launcHER through
  `pops_config_discover`): 6 fixed and 441 pairs;
- 357 files of 1..8 bytes: equal with zeros after the original's buffer;
  with 4 other heap patterns see "A file of a few bytes is read past its
  buffer";
- 500 seeded random texts with runs of 57..70 bytes, bytes above `0x7f` and
  control bytes next to launcHER's own tokens;
- 300 seeded random `$USBDELAY` texts: the same (84 wrote `0x100017`);
- VMCDIR.TXT: 39 fixed files (30 of them also as the game's own file) and
  400 seeded random files (212 used, 188 ignored): used or ignored, and
  the name, are the same;
- 30 text/start-value pairs (5 texts, 6 start values) for the shared
  number temporary;
- `FUN_008dc2c4`: 21 modes, with and without `$SUBCDSTATUS`.

Without `POPSTARTER_TEST_ELF` (as in CI) only the table checks run: the
fixed texts against the recorded results, and launcHER's own tokens.

Set all three temp variables, or two runs share one host library file
(Python's `tempfile` reads `TMPDIR` before `TMP` and `TEMP`):

```sh
export TMP=<empty dir> TEMP=<same> TMPDIR=<same>
python tools/test_pops_config_text.py
```

NOT TESTED on a console.
