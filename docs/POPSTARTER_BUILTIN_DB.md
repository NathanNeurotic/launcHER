# POPStarter r13's built-in per-game list

POPStarter r13 identifies the game from the VCD and applies a built-in set of
fixes for it. `$VCDID_n` picks entry `n` by hand. This file records what was
measured in the original (external POPSTARTER.ELF MAIN, read at run time;
nothing from it is stored here). launcHER does not implement this yet. Nothing
here was tested on a console.

## How the entry is chosen

- Lookup: `FUN_008ff0e4(fd, mode)`, called from the launch paths
  (`0x8757d4`, `0x875d70`, `0x875f78`, `0x8762a8`, `0x876424`, `0x8769ac`)
  while `gp+0x385c` is 1..4.
- `gp+0x385c` comes from preset byte `0x10002f` of POPSTARTER.ELF's own
  segment: 3 in every shipped r13 build. It drops to 2 when preset `0x10001f`
  is set (0 in every build), so on every shipped build the mode is 3.
- Fingerprint (144 bytes, buffer from `malloc(0x120)`):
  - VCD offset `0x109340`, 0x30 bytes (sector 16, the primary volume
    descriptor, data bytes 40..87);
  - VCD offset `0x109640`, 0x20 bytes (same sector, data bytes 808..839);
  - VCD offset `0x10ca70`, 0x40 bytes (sector 22, data bytes 56..119).
  A physical-disc path (`gp+0x3410 == 1`) reads the same sector bytes
  through the CD driver.
- It is compared with 607 stored 144-byte fingerprints (MAIN data from
  `0x972490`), in program order (`0x8ff33c..0x9148e8`). The first exact
  match sets `gp+0x38d8` to that block's id (1..624, with gaps; id 508 has
  two fingerprints; 4 fingerprints are duplicates, so the later copies never
  match). Only while `gp+0x38d8` is still 0.
- If an id is set, `FUN_008e00d0(id, mode)` applies it. The buffer is then
  cleared.

## `$VCDID_n`

The handlers at `0x890f4c`, `0x8912e4`, `0x8917f0`, `0x891e78` read the decimal
digits after `$VCDID_` (one handler per length, apparently 1 to 4; not yet
checked digit by digit), set `gp+0x38d8 = n` and `gp+0x38c0 = 1`, and
call `FUN_008e00d0(n, 3)` at once. Because `gp+0x38d8` is then non-zero, the
later lookup skips the fingerprint scan but calls `FUN_008e00d0(n, mode)`
again.

## What an entry does (`FUN_008e00d0`, `0x8e00d0..0x8ff0e4`)

One arm per id; each checks the mode (1 or 3, 2 or 3) per action. Measured
for every id 0..625 in mode 3 by running the function under Unicorn with its
helpers stubbed (`print`, `memcpy 0x918808`, `poke8 0x914930`,
`poke32 0x914964`, and the three below), 2026-11-01:

| Action | Entries | launcHER counterpart |
|---|---|---|
| `FUN_008dc2c4(k)`: compatibility mode k (1..6) | 326 | `$COMPATIBILITY_0k` code, present |
| `memcpy(0x210cf8, template, 21)`: LibCrypt fix, template bytes set per game | 213 | the LibCrypt site launcHER already guards |
| `poke32(0x2397d8, jal 0x01410000)` plus `memcpy(0x01410000, code, n)` (36..1696 bytes): game-fix code, called from the original's resident chain just before its cheat code | 134 | **none**: needs a call from launcHER's GP1 entry |
| `poke8 0x20e850=6`, `poke32 0x20e86c=0x24030020`, `poke32 0x20e87c=0x00431022` | 11 | `$SUBCDSTATUS`, present |
| `poke32 0x202734=0x10000004` | 8 | new |
| `FUN_008dc12c(2)`: memory card 1 off | 5 | `$NOVMC1` helper, present |
| `memcpy(0x239780, template, 84)` plus `poke32(0x238d00, j 0x239780)`: second LibCrypt form | 5 | new |
| `poke32 0x0141001c=0` (edits the game-fix code) | 3 | with the game-fix code |
| `poke8 0x21af70=0x32` | 3 | new |
| `FUN_008d6da4(ps1_address, 0x14400002)`: exception hook with a target | 14 | launcHER's hook takes no target yet |

## Still to find out

- Order against the user's own commands (both write some of the same sites).
- The game-fix code's calling convention (it is reached by `jal` from the
  original's chain, which saves only `k0`/`k1`).
- How to store the fingerprints in launcHER without copying disc data:
  plan is a hash of each 144-byte fingerprint, matched in the same order.
