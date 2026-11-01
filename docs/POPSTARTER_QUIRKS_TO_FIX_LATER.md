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
