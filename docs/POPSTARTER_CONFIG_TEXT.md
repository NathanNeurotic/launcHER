# POPStarter r13's text files: how CHEATS.TXT commands are recognised

Measured on the original (POPSTARTER.ELF MAIN, external input, decoded image
at `0x870000`) on 2026-11-11, by reading its code and by running that code
under emulation on synthetic text (`tools/trace_original_pops_config_text.py`,
`tools/test_pops_config_text.py`). launcHER copies it. Nothing here was
tested on a console.

## The reader (`FUN_00883270`)

Called twice: at `0x8771ac` with `a0 = 0` (the CHEATS.TXT "for all games")
and at `0x87724c` with `a0 = 1` and `a1 = gp+0x38f0` (the game's own). The
second call is skipped when `gp+0x38dc` or `gp+0x3460` is set.

- The file is read whole: size from a seek to the end, `malloc(2 * size)`,
  one read. An empty file returns early. There is no size or line limit.
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
| `0x89030c` | `$480` + `P` + terminator (not tried when `gp+0x3880` is set; the only store to it found in the image is the start-up clear at `0x870ca4`) |
| `0x890a34` | `$LEFTADJ_` + 1..3 digits; applied for 1..255 only |
| `0x890c48` | `$SCANLINES` |
| `0x891e98` | `$VCDID_` + 1..4 digits; not tried once `gp+0x38d8` is nonzero, so `$VCDID_0` does not stop the next one |
| `0x892118`..`0x894240` | `$SUBCDSTATUS` `$RESET_WARMBOOT` `$MUTE_CDDA` `$MUTE_VAB` `$CODECACHE_ADDON_0..2` `$RECOMPILER_ADDON_0..4` |
| `0x894528` | `$ORIGINAL_OPCODES`: the terminator is tested at column 19, not 17 (see quirks) |
| `0x894aa4`..`0x897ca8` | `$UNDO_COMPATIBILITY_CODES` `$UNDO_GAME_FIXES` `$UNDO_LIBCRYPT_FIX` `$UNDO_MUTE_CDDA` `$WIDESCREEN` `$ULTRA_WIDESCREEN` `$EYEFINITY` `$ROLLBACK` `$SET_TIMINGS` `$BREAKPOINT0` `$BREAKPOINT1` `$NOVMC0` `$NOVMC1` `$NOPAD0` `$NOPAD1` `$D2LS` `$D2LS_ALT` `$IGR0`..`$IGR5` `$NOIGR` |
| `0x8982b4` | `$PAD` + `0` or `1` + `ID_0X` + two bytes + terminator at column 12; applied only when both bytes are hex digits |
| `0x8984a4`..`0x89882c` | `$MUTE_ALL` `$NOPAL` `$FORCEPAL` |
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

## launcHER

- `pops_config_parse_text()` (`common/src/pops_config.c`): the same pass on
  an upper-cased copy of the file: the five code tests, then the handler
  table in the original's order (`pops_commands[]`), one byte on after each.
  `load_config_file()` reads the file in binary and has no line limit.
- The shared number temporary is the function's `value` argument: 0, or
  `strlen(game folder) + 1` for `<game>/CHEATS.TXT` (`pops_config_discover`).
  So a game folder `Game` with `$XPOS_` and nothing after it writes X = 5.
- launcHER's own tokens (`$NOBOOT`, `$BIOS`, `MODE n`, `$MODE n`, `$MODEn`, a
  bare digit, `$DITHER_OFF`, `$NODITHER`, `$FASTMIPS`, `$SLOWMIPS`,
  `$PAL2NTSC`, `$FORCENTSC`, `$NTSC2PAL`, `$FIX_*`, `$CORE_FIXES`,
  `$PSXCORE_FIXES`) are not POPStarter's: the original takes none of them.
  They keep launcHER's earlier rules (split at white space, `#` or `;`
  starts a comment) and are applied in file order with the original's
  commands.

### Known differences that remain

- launcHER keeps one cheat list and one safe-mode gate for all files; the
  original compiles each file's codes with that file's own gate.
- The cheat codes themselves are still found by launcHER's earlier scan
  (`scan_cheats`), which stops at a NUL byte and also steps over `$C0`
  codes; the original's passes go by the file size. Texts with a NUL byte
  or with a code inside a `$C0` code's columns can differ.
- Files over 1 MiB are refused (`-EFBIG`); the original has no limit.
- `gp+0x3880` (the `$480p` gate) is not modelled.

## Evidence (host and emulation only)

`python tools/test_pops_config_text.py` with `POPSTARTER_TEST_ELF`:

- the handler names and their order, read from the image, equal
  `pops_commands[]`;
- 100 fixed texts: the original's pass and launcHER's reader report the
  same commands at the same offsets, the same codes stepped over, and the
  same X, Y, compatibility-mode and game-id values;
- 1500 seeded random texts: the same;
- 30 text/start-value pairs for the shared number temporary;
- `FUN_008dc2c4`: 21 modes, with and without `$SUBCDSTATUS`.

NOT TESTED on a console.
