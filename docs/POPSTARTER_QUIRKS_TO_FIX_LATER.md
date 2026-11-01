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

- Quirk 9 also changes another CPU register in POPStarter's cheat routine
  (gp, sp, fp, ra from `0x20000`; from `0x60000` the instruction also reads
  another register, so the result depends on CPU state). launcHER copies
  only the RAM effect. What the changed register does on a console is
  unknown; files that reach `0x60000` are left out of the differential test.

## Elsewhere

- Always-on SLBB-00001 check bypass: POPStarter applies it only when its
  config byte `0x100023` is 1 (`fp+0x10e4 == 1` at `0x874c0c`). launcHER
  applies it always. This one is a parity gap still to close, not a fix.
