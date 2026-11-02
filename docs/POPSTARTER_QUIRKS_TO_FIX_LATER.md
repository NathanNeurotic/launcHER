# POPStarter quirks launcHER copies on purpose

launcHER's first goal is to behave exactly like POPStarter r13, bugs
included, so a POPStarter setup works the same in launcHER. Improvements come
later. This file lists the behaviour that was copied on purpose and that we
may want to fix once parity is done. Each entry says what POPStarter does,
how we know, and what a fix could look like. Nothing here was tested on a
console.

How these were found: POPStarter's own cheat compiler (the cheat section of
the r13 MAIN, from `0x883270`) run under emulation with
`tools/trace_original_pops_cheats.py`, and compared against launcHER by
`CheatsTxt.test_random_files_match_the_original` in
`tools/test_pops_resident.py` (external MAIN and the `unicorn` package
needed).

## CHEATS.TXT

| # | POPStarter behaviour (copied) | Possible fix later |
|---|---|---|
| 1 | A `#` or `;` in front of a code does not switch it off: codes are found anywhere in the text. Only removing the `$` turns one off. | Treat `#`/`;` lines as comments. |
| 2 | `C0` master code values of `0x8000` and up never match (it compares a sign-extended `lh` with a zero-extended `ori`), so such a master code turns every code off. | Compare 16-bit values unsigned. |
| 3 | Only the first `C0` counts, wherever it is in the file; later ones are dropped. | Keep, or support several. |
| 4 | A `D0` right after another `D0` (or while a repeat is pending) is dropped, so it gates nothing. | Chain conditionals (AND). |
| 5 | When a `D0` gates a `5000` repeat, the code after the repeat is always skipped (a leftover branch compares the last write's address and value, which never match). With a repeat count of 0 it is gated by the `D0` instead. | Skip only the gated block. |
| 6 | A second `5000` while one is pending is ignored for the next write, but the first one ignored is kept and becomes the pending repeat behind the next emitted `D0`, even one written much later. | Drop it, or apply the latest repeat. |
| 7 | A `5000` with no `80`/`30` code after it still expands, onto PS1 address 0 with value 0 and the store size of the last write before it, so it writes to low RAM. | Ignore a repeat with no target. |
| 8 | A repeat that crosses a 64 KB boundary moves every later write another 64 KB further up (the high half is bumped once per step after the running low half passes `0xFFFF`). | Write the addresses the code asks for. |
| 9 | Repeat values from `0x10000` wrap to 16 bits; from `0x20000` the generated `ori` no longer loads the value register, so the store repeats the last value that fitted. | Wrap values to 16 bits. |
| 10 | Other GameShark types (`10`, `20`, `D1`..`D3`, `E0`, `E1`) are skipped, so the code after a conditional of those types runs on its own. | Support them (launcHER's engine still can, for direct callers). |
| 11 | `80`/`D0`/`C0` at an odd address would raise an address error on the console (unaligned `sh`/`lh`). launcHER aligns the address down instead. | Keep launcHER's alignment. |
| 8b | When quirk 8 carries a repeat past the end of PS1 RAM (2 MB), the writes land in the EE RAM above it (EE `0x01000000` + address). launcHER writes there too, but never past the first 32 MB of EE RAM. | Stop at the end of PS1 RAM. |

## PS2-format codes (`$0`/`$1`/`$2`, `$S`, `$T`, `$=`, `$!`)

| # | POPStarter behaviour (copied) | Possible fix later |
|---|---|---|
| 13 | Byte and halfword conditionals (`$S`/`$T` with size 0 or 1) load the memory sign-extended (`lb`/`lh`) and compare it with the whole 32-bit value. A byte of `80` only matches `FFFFFF80`, never `00000080`. | Compare only the low 8/16 bits. |
| 14 | After the first PS2 conditional, POPStarter compiles the rest of the file with a cut-down copy of its loop that knows only writes. Every later `D0`, `5000` and conditional of any kind is dropped. Which writes survive depends on the conditional: after `$S` a `$T` write is dropped, after `$=`/`$!` a `$S` write is dropped, after `$T` both are kept. PS1 and `$0`/`$1`/`$2` writes are always kept. | One loop that handles every code type. |
| 15 | A PS2 conditional behind a pending `D0` (or behind a `D0`-gated repeat, or a pending repeat) is dropped. | Chain conditionals. |
| 16 | Between a `D0` and the write it gates, a `$S`/`$T` write is dropped, and a `$0`/`$1`/`$2` write is placed there and runs on its own. It also replaces the registers the `D0` compares, so the `D0` then compares that write's address with its value instead of the RAM it read, which in practice almost always skips the gated code. | Keep the compare apart from the writes. |
| 17 | A PS2-format write after a `5000` that has not met its PS1 write yet is dropped. | Let the repeat wait. |
| 18 | A PS2 conditional with nothing after it branches, when false, past the end of the generated code, over POPStarter's exit jump, into whatever follows in memory. launcHER just ends the pass. | Branch to the exit. |
| 19 | A PS2-format code at an address its size does not divide, or outside the memory it names, faults on the console (`sh`/`sw`/`lh`/`lw`). launcHER aligns the address down, and skips a code that falls outside EE RAM (32 MB), the scratchpad (16 KB) or the first 1 KB of the `0x5F800000` page, together with the code a skipped conditional gates. | Keep launcHER's checks. |

## Known gaps (not copyable)

- Quirk 9 also changes another CPU register. Where that happens was traced
  in the original: POPStarter replaces POPS's `jal` at `0x21a63c` with a
  call to its blob at `0x239490`, which saves only `k0`/`k1` (`sq` to
  `0x2394d0`/`0x2394e0`), runs the checks and the generated cheat code, then
  restores `k0`/`k1`, reloads `ra` with `0x21a640` and returns. Every other
  register is POPS's own, live at that call site. So, by running value:
  - `0x20000`..`0x4FFFF`: the bad `ori` overwrites POPS's `gp`, `sp` or
    `fp`, which POPS then keeps using. That almost certainly freezes or
    crashes the game in POPStarter.
  - `0x50000`..`0x5FFFF`: it overwrites `ra`, which is reloaded before the
    return. No effect, and launcHER already matches exactly.
  - `0x60000` and up: the instruction also reads `at` and can overwrite any
    register (including `k0`, which moves the store). The result depends on
    POPS's live registers.
  launcHER copies the RAM effect only. Its codes now run at the same call
  site, but its entry saves and restores every register around them, so
  POPS's registers are never changed; a file in the first or last range
  breaks POPStarter anyway. Files from `0x60000` up are left out of the
  differential test.

## Not a gap after all

- SLBB-00001 check bypass: POPStarter applies it when byte `0x100023` is 1
  (`fp+0x10e4 == 1` at `0x874c0c`). That byte is a build preset, not a user
  setting: it sits in the preset block of POPSTARTER.ELF's own segment
  (file offset `0x423`, loaded at `0x100000`), and the only code that touches
  it reads it (`0x8710c8`). It is 1 in every shipped r13 build (MAIN, DEBUG,
  USBDELAY, USBDELAY_DEBUG, USBDELAY_LONGER_DEBUG), so POPStarter always
  applies the bypass, and launcHER always applying it matches. The same
  holds for the neighbouring presets `0x100022` (exception breakpoints,
  `FUN_008dbafc`), `0x100024` (IGR exit fix, `FUN_008dbe08`), `0x100027`
  (module error checks, `FUN_008dbfd4`) and `0x100028` (HddInit exit,
  `FUN_008dc0c0`): all 1 in every build, all applied by launcHER.

## Copied: where the codes run

| # | POPStarter behaviour (copied) | Possible fix later |
|---|---|---|
| 12 | Cheats, the controller ID override and `$SET_TIMINGS` run from POPS's GP1 write path (`0x21a63c`), not once per frame: once for every GPU control-port write the game makes while interrupts are enabled. A game that writes GP1 several times a frame gets several passes; one that stops writing it (or writes it only with interrupts off) gets none, so its codes, forced pad ID and timing keys stop working. How often that happens per game was not measured. | Run them once per VBLANK as well, or instead. |

## Built-in per-game list (`$VCDID_n`, docs/POPSTARTER_BUILTIN_DB.md)

| # | POPStarter behaviour (copied) | Possible fix later |
|---|---|---|
| 20 | The list runs on every launch and cannot be switched off except by a `$VCDID_n` with an unused id (625..9999), which is what makes the original skip its scan. A fingerprint match also silently disables `$VCDID_n`. | A `$NOVCDID` command, and let `$VCDID_n` override a match. |
| 21 | The 14 "breakpoint killer" entries scan up to 2 MB of PS1 RAM on every GP1 write the game makes, with the handler at `0x01460000` using POPS's `gp-0x7ff0` as scratch, exactly as the original's code does. The 134 game-fix entries run their code on every GP1 write too. | Move both to once per frame, or rewrite the handler to remember where it stopped. |
| 22 | Tokenizing differs in two small ways. `$VCDID_5<tab>` is accepted by launcHER (tokens split on any white space) but ignored by the original, which ends the digits only at a space, CR, LF or NUL. And the original starts a command at any `$`, so `x$VCDID_9999` is a command there; launcHER needs the `$` at the start of a white-space delimited token (this holds for every command, not only `$VCDID_n`). Not copied: both would need a parser change for one character. The same holds for every command: `$RESET_WARMBOOT$NOPAD0` is two commands there and none here, and a `#` line hides a command here but not there. | Keep launcHER's. |
| 23 | With no fingerprint match, the original applies `$VCDID_n` at the point of the command, so commands before it in the files run first and commands after it run later. launcHER applies the entry before all commands; only matters when the same file both selects an entry and, before the `$VCDID_n` line, writes one of its sites. | Record command order in the parser. |
| 24 | `$SUBCDSTATUS` makes every later `$COMPATIBILITY_0x01/02/03/05` in the files do nothing (the original's `FUN_008dc2c4` checks `gp+0x3458`); modes 4, 6 and 7 still apply. Now copied, per file order. Before this change launcHER applied them anyway. | Decide whether the skip is wanted; it looks accidental. |
| 25 | `$RESET_WARMBOOT`'s store of the reset vector is built into the slot (`0x232d08`) that a built-in entry's breakpoint handler call uses, and runs after the entry, so a game on the list with a breakpoint handler loses that handler once `$RESET_WARMBOOT` finds a SystemErrorExit stub. Copied: launcHER drops `POPS_RES_F_BREAK_CALL` in that case. | Run both: the two do not conflict in launcHER's chain. |
| 26 | `$RESET_WARMBOOT` means to make the in-game reset combo jump to the SystemErrorExit stub's PS1 ROM address (`0xbfc0d8d0` on this POPS): the code computes it (`p - 0x24bc20 + 0xbfc00000`) and then stores the other variable, `p`, the EE address of the stub inside POPS's ROM copy (`0x2594f0`). The PS1 then jumps to that address in its own space. Copied: `pops_apply_reset_warmboot` returns `p`. | Store the ROM address. |
| 27 | The in-game reset combo is port 0 reading exactly SELECT+L2+R2+CROSS (`0x507002 == 0xbcfe`), tested on every GP1 write; the resident block was always live in the original and was missing from launcHER until the `$RESET_WARMBOOT` work. Any other button held with the four cancels it. | Decide whether the combo should stay at all, and document it. |
