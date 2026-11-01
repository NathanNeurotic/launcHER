# POPStarter r13's built-in per-game list

POPStarter r13 identifies the game from the VCD and applies a built-in set of
fixes for it. `$VCDID_n` picks entry `n` by hand. launcHER carries the same
list, generated from the original by `tools/gen_pops_builtin_db.py` into
`common/src/pops_builtin_db_data.c` (external POPSTARTER.ELF MAIN, read at
generation time; the disc fingerprints are stored as 64-bit FNV-1a hashes,
not as disc bytes). The runtime is `common/src/pops_builtin_db.c`
(`pops_builtin_db.h`). Nothing here was tested on a console.

## How the entry is chosen

- Lookup: `FUN_008ff0e4(fd, mode)`, called from the launch paths
  (`0x8757d4`, `0x875d70`, `0x875f78`, `0x8762a8`, `0x876424`, `0x8769ac`)
  while `gp+0x385c` is 1..4, **before** the config files are parsed
  (`FUN_008883270` at `0x8771ac`/`0x87724c`, in the same function).
- `gp+0x385c` comes from preset byte `0x10002f` of POPSTARTER.ELF's own
  segment: 3 in every shipped r13 build (MAIN, DEBUG, USBDELAY,
  USBDELAY_DEBUG, USBDELAY_LONGER_DEBUG). It drops to 2 when preset
  `0x10001f` is set (0 in every build), so on every shipped build the mode
  is 3.
- Fingerprint (144 bytes, buffer from `malloc(0x120)`):
  - VCD offset `0x109340`, 0x30 bytes (sector 16, the primary volume
    descriptor, data bytes 40..87);
  - VCD offset `0x109640`, 0x20 bytes (same sector, data bytes 808..839);
  - VCD offset `0x10ca70`, 0x40 bytes (sector 22, data bytes 56..119).
  A physical-disc path (`gp+0x3410 == 1`) reads the same sector bytes
  through the CD driver. launcHER: `pops_builtin_sig_offsets` from the
  inspected VCD geometry (header, sector size, data offset).
- It is compared with 607 stored 144-byte fingerprints (MAIN data from
  `0x972490`), in program order (`0x8ff33c..0x9148e8`). The first exact
  match sets `gp+0x38d8` to that block's id (1..624, with gaps; four stored
  fingerprints repeat an earlier one, 398 = 382, 461 = 90, 528 = 527 and
  508's second copy = its first, so the later copies never match). Only while `gp+0x38d8` is still 0. launcHER: `pops_builtin_lookup`,
  same order, first hash match wins (no two different stored fingerprints
  share a hash; the generator checks).
- If an id is set, `FUN_008e00d0(id, mode)` applies it. The buffer is then
  cleared.

## `$VCDID_n`

Handlers at `0x890f4c`, `0x8912e4`, `0x8917f0`, `0x891e78`, one per digit
count 1..4 (measured on the original's parser, 2026-11-01):

- the digits must be followed by a space, CR, LF or the end of the text;
  `$VCDID_5,`, `$VCDID_5x`, `$VCDID_5<tab>` and five digits match nothing;
  leading zeros count (`$VCDID_0508` is 508, `$VCDID_00005` is five digits,
  nothing); the name is case-insensitive; a `$` anywhere starts a command;
- the handler runs only while `gp+0x38d8` is 0: a fingerprint match (made
  before the parse) **disables** `$VCDID_n`, and the first `$VCDID_n` in the
  files wins over later ones;
- it sets `gp+0x38d8 = n`, `gp+0x38c0 = 1` and calls `FUN_008e00d0(n, 3)` at
  once; an `n` past the last entry (625..9999) selects nothing but still
  sets the id, which also stops the fingerprint scan. `$VCDID_0` sets 0 and
  changes nothing.

launcHER: `PopsConfig.vcdid`/`vcdid_set` (first wins), used only when the
fingerprint matched nothing, ids past 624 select nothing. Two tokenizing
differences: launcHER's parser splits tokens on any white space, so
`$VCDID_5<tab>` is accepted, and it needs the `$` at the start of a token,
so `x$VCDID_9999` is not a command (quirk 22 in
`POPSTARTER_QUIRKS_TO_FIX_LATER.md`).

## What an entry does (`FUN_008e00d0`, `0x8e00d0..0x8ff0e4`)

One arm per id; each checks the mode (1 or 3, 2 or 3) per action. Measured
for every id 0..624 in mode 3 by running the function under Unicorn with
its helpers stubbed or run as shipped (`tools/gen_pops_builtin_db.py`,
`tools/test_pops_builtin_db.py`), 2026-11-01:

| Action | Entries | launcHER |
|---|---|---|
| `FUN_008dc2c4(k)`: compatibility mode k (1..6), skipped for k in 1,2,3,5 once `gp+0x3458` is set | 326 | `COMPAT` op: `pops_compat_mode_write`, same gate |
| `memcpy(0x210cf8, template, 21)`: LibCrypt fix, template bytes set per game | 213 | `CORE` write |
| `poke32(0x2397d8, jal 0x01410000)` plus `memcpy(0x01410000, code, n)` (36..1696 bytes; three entries then edit `0x0141001c`): game-fix code, called from the original's resident chain just before its cheat code | 134 | `EE` write at handoff, `FIX_CALL`: the resident GP1 work calls `0x01410000` before the cheats |
| `poke8 0x20e850=6`, `poke32 0x20e86c=0x24030020`, `poke32 0x20e87c=0x00431022` plus `gp+0x3458=1` | 11 | `CORE` writes, `SUBCD` |
| `poke32 0x202734=0x10000004` ($CODECACHE_ADDON's site) | 8 | `CORE` write |
| `FUN_008dc12c(2)` plus `gp+0x38bc=2`: memory card 1 off | 5 | `NOVMC1`: `cfg.no_vmc1`, the `$NOVMC1` helper |
| `memcpy(0x239780, code, 84)` plus `poke32(0x238d00, j 0x239780)`: a second LibCrypt form; the code checks a PS1 word and zeroes a block, then falls through to the fix-code slot | 5 | `LIBCRYPT2_CODE` + `LIBCRYPT2_ON`: the code is copied into the resident config with `jr ra` appended and run after `$SET_TIMINGS` |
| `poke8 0x21af70=0x32` | 3 | `CORE` write |
| `FUN_008d6da4(ps1_address, 0x14400002)`: installs a 292-byte handler at `0x01460000` (template `0x96bde0` plus the address and word) and `jal 0x01460000` at `0x232d08`, a slot of the original's own resident block right after the controller-ID stores, not an exception vector. Each GP1 write it scans PS1 RAM for a `bnez` pattern and rewrites it (the "breakpoint killer"); it uses POPS's `gp-0x7ff0` as scratch | 14 | `EE` write at handoff, `BREAK_CALL`: the GP1 work calls `0x01460000` after the controller IDs, with POPS's `gp` untouched |
| `gp+0x4fa0 = 0` (entry 504): no automatic PAL for a European disc (the region pass at `0x87930c` checks it) | 1 | `NO_AUTO_PAL`: `pops_apply_region` auto-disabled |

Every entry ends by clearing `gp+0x38c0`. Entries 485..493 edit a template in
MAIN (`0x984c88..0x984c9d`) before copying it; the copied bytes are what is
stored.

## Order against the user's commands

The list is applied before the config files are parsed, so a user's command
that touches the same site wins: `$UNDO_COMPATIBILITY_CODES`,
`$UNDO_GAME_FIXES` and `$UNDO_LIBCRYPT_FIX` exist for exactly that. launcHER
applies the entry to the staged core before `pops_apply_all_config_patches`,
tells the fix-file context what the entry changed
(`pops_fix_context_init_builtin`, computed from the entry data, not from
live bytes), and lets `pops_apply_compat_modes` accept a site the entry
already changed. `$VCDID_n` with no match applies at the point of the
command in the original; launcHER applies it before all commands (quirk 23).

`$SUBCDSTATUS` sets the same `gp+0x3458` flag an entry can set, so
compatibility commands for modes 1, 2, 3 and 5 **after** it in the files do
nothing in the original. launcHER now copies that (`PopsConfig.subcd_seen`,
`add_compat_mode`), per file order, and a matched entry's flag gates the
whole file, as in the original.

## Where launcHER's copies live

- Core writes: the staged core, before the user's commands.
- `0x01410000` (game-fix code, up to 1696 bytes) and `0x01460000` (292-byte
  handler): copied just before handoff, like the resident image. Both lie
  between the staged core (which must end below `0x01410000`; checked) and
  launcHER's resident image (`0x0143a000..0x01460000`). POPStarter uses the
  same addresses under POPS.
- The second LibCrypt code: 84 bytes inside `PopsResidentConfig`
  (`libcrypt2_code`, 4-byte aligned) plus `jr ra`, `nop`.
- The chain order in `pops_resident_gp1_work`: controller IDs, breakpoint
  handler, `$SET_TIMINGS`, LibCrypt 2, fix code, cheats; the original's
  slots are `0x232cb0..`, `0x232d08`, `0x238a90`, `0x238d00`, `0x2397d8`,
  `0x2397e8`.

## Verification

- `tools/test_pops_builtin_db.py` (needs `POPSTARTER_TEST_ELF`): for every
  id 0..624 the original `FUN_008e00d0(id, 3)` is run with recorded helpers
  (`tools/trace_original_pops_vcdid.py`) and `FUN_008d6da4` run as shipped;
  the core image, the EE images and the flags must equal
  `pops_builtin_apply`'s. Every stored fingerprint must find its first id;
  random ones none. `$VCDID_n` parsing is compared with the original's
  handlers on fixed and random texts.
- `tools/gen_pops_builtin_db.py --check` regenerates and compares the data
  file.
- `tools/check_pops_resident_image.py` runs the built GP1 entry with the
  three flags and checks the order: breakpoint handler, LibCrypt 2, fix,
  then cheats, with `gp` kept.
