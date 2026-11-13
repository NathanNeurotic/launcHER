# What POPStarter r13 changes on every launch

Measured on the original (POPSTARTER.ELF MAIN, external input, gp
`0x9b68f0`) on 2026-11-02 by listing every write its launch makes to POPS,
to its own resident area and to memory, and by running its blocks over the
real POPS core. Copied into launcHER for POPStarter launches (`launchPOPS`)
only; Ember launches never reach this code. **Nothing here was tested on a
console.**

Most of what POPStarter does depends on a command or a file. The writes
below do not: no command and no shipped build skips them. Before this
change launcHER made only some of them, and one gap broke features that
were already copied.

## The gap this closes

POPStarter always writes `jal 0x239490` over the `nop` at `0x21a63c` in
POPS's GP1 write path (`0x874790`). Everything its resident chain does runs
from there: the in-game reset combo (SELECT+L2+R2+CROSS, quirk 27), the
built-in list's game-fix code, second LibCrypt code and breakpoint handler
([POPSTARTER_BUILTIN_DB.md](POPSTARTER_BUILTIN_DB.md)), `$BREAKPOINT0/1`
([POPSTARTER_BREAKPOINT.md](POPSTARTER_BREAKPOINT.md)), the controller ID
override, `$SET_TIMINGS` and the cheats.

launcHER installed its own hook at that site only when cheats, a
controller ID command or `$SET_TIMINGS` were in the files. On any other
launch, the reset combo, the built-in list's code calls and `$BREAKPOINT`
were set up but never ran. launcHER now copies its resident image and
writes the GP1 hook on every POPStarter launch, as the original does.

## Every write POPStarter makes on every launch

In the order its launch function makes them. Addresses on the left are in
POPSTARTER.ELF MAIN.

| Original | What it does | launcHER |
|---|---|---|
| `0x8744a8` | `0x20c0c4 = 0` (later replaced by `0x874a04`) | same end result, `pops_apply_always_on_pokes` |
| `0x874764` | copies `0x738` bytes of its own code to `0x232790`: the always-live block the GP1 hook runs (pad hotkeys, slot copies, `$NOVMC0/1` and controller ID stores, the reset combo, the chain slots) | launcHER's own resident GP1 work: the pad hotkeys and in-game disc swap (below), the `$NOVMC0/1` card stores, the controller ID stores, the reset combo and the chain calls |
| `0x87477c` | copies `0xd60` bytes to `0x238a90`: its `$SET_TIMINGS`, LibCrypt 2 and cheat code area, entered at `0x239490` | launcHER's own resident code |
| `0x874790` | `0x21a63c = jal 0x239490`: the GP1 hook | `pops_resident_hook_gp1`, **now on every launch** (it was only with cheats, controller IDs or `$SET_TIMINGS`) |
| `0x8747ec` | `0x2075e8..0x2075ef = j 0x143a160; nop` (over two `ld`s at the end of POPS's recompiler routine, which then stores the block's last instruction, `sw $v1, 0($a2)` at `0x2075f8`), into the code copied at `0x874808` | `pops_resident_hook_recompiler`, to launcHER's own code, on every launch (below) |
| `0x874808` | copies `0x5ea0` bytes to `0x143a160`, the code `0x2075e8` jumps to; the `$RECOMPILER_ADDON_n` commands change it | launcHER's own code for the same behaviour, `common/src/pops_resident_recompiler.S` (below) |
| `0x874864` | copies `0x160` bytes to `0x143a000`: the nine guard stubs | launcHER's own stubs, `common/src/pops_resident_guards.S` |
| `0x874878..0x874998` | the nine misaligned-read guards (below) | `pops_resident_hook_guards` |
| `0x8749ac..0x874a18` | the exit and byte-copy pokes (below) | `pops_apply_always_on_pokes` |
| `0x876a50`, `0x876a7c` | copies its exit program to `0x1450000` and writes `j 0x1450000` at `0x2362fc` (POPS's `ExecOSD` tail call) | not copied: launcHER keeps its own exit, which the owner confirmed on a console (Tekken) |
| `0x878f9c..0x878fbc` | three edits to the PS1 BIOS shell inside POPS (below), skipped only when a user `BIOS.BIN` or OSD replacement was loaded | `pops_apply_bios_shell_edits_rom` with the loader state: skipped after a user `BIOS.BIN` ([POPSTARTER_USER_BIOS.md](POPSTARTER_USER_BIOS.md)); skipped after a user `BIOS.BIN` or `OSD.BIN` ([POPSTARTER_USER_BIOS.md](POPSTARTER_USER_BIOS.md), [POPSTARTER_OSD.md](POPSTARTER_OSD.md)) |
| `0x87c0f8` | `memset(0x70000000, 0, 0x4000)`: the whole scratchpad | the trampoline, step 1 (it cleared POPS's `0x3c30` bytes only) |
| `0x87c130` | `memset(0x502e60, 0, 0x36d1a0)`: POPS's BSS and on up to `0x870000`, where POPStarter's own code starts | the trampoline, step 2: up to `0x870000` too (it stopped at POPS's BSS end, `0x865940`) |
| `0x87c140` | `memset(0x100000, 0, 0x100000)` | the trampoline, step 3 (already the same) |

The three writes gated by `gp+0x3884` (`0x8747b0`, `0x874828`, `0x874848`)
run on every launch of a shipped build: the code skips them only when that
word is nonzero, and it only ever holds the build preset byte `0x100008`,
which is 0 in all five r13 builds (MAIN, DEBUG, USBDELAY, USBDELAY_DEBUG,
USBDELAY_LONGER_DEBUG). This note used to say they never run; it read the
test the wrong way round (corrected 2026-11-02). Each turns one slot of a
chain of `b`-to-the-next-slot into a jump:

- `0x232d30 = j 0x238a90`: the always-live block goes on to the
  `$SET_TIMINGS` check at the start of the `0x238a90` area;
- `0x238d00 = j 0x2397d8`: the second LibCrypt code's slot goes straight
  on to the game-fix slot (the built-in list's `LIBCRYPT2_ON` writes its
  own jump there);
- `0x143a720 = j 0x143ffdc`: the recompiler block jumps past the rest of
  its slots, all empty `b`s, to its exit, so with no command it takes 22
  instructions instead of about 5,700 (below).

launcHER's resident code runs in the order these jumps make
(`pops_resident_gp1_work`, `pops_resident_recompiler.S`), so there is
nothing more to copy for them.

### The nine guards

Each replaces a POPS load or store with `j stub` and turns the word after
it into a `nop` (except at `0x204160`, a branch whose delay slot stays).
Seven stubs force the base register to a word boundary (`& 0xfffffffc`,
sign-extended) and then do what POPS did, so a misaligned pointer reads or
writes the word below instead of raising an address error, and the
register keeps the rounded value. In POPStarter's order:

| Site | POPS's words | Stub |
|---|---|---|
| `0x21c58c` | `lw $v0, 0($a0)` / `addiu $a0, $a0, 4` | aligned load, back to `0x21c594` |
| `0x21c768` | `lw $a0, 0($v0)` / `addiu $v0, $v0, 4` | aligned load, back to `0x21c770` |
| `0x2082a0` | `lw $a2, 0($v1)` / `bnez $a2, 0x2082b4` | aligned load, then `0x2082b4` if nonzero, else `0x2082ac` |
| `0x204ae0` | `lw $v1, 0($v1)` / `lui $v0, 0x3c02` | aligned load and the `lui`, back to `0x204ae8` (quirk 41) |
| `0x204178` | `lw $a1, 0($v1)` / `srl $a3, $a1, 26` | aligned load and the `srl`, back to `0x204180` |
| `0x204160` | `b 0x20417c` / `move $a1, $v0` | the branch goes to the end of the `0x204178` stub (the `srl`), since `0x20417c` is now a `nop` |
| `0x202250` | `jr $ra` / `sw $t2, 0($v0)` | the store goes to `0x00c70000` + the address's low 16 bits instead (quirk 42) |
| `0x21c5dc` | `sw $a1, 0x2260($s0)` / `sw $v1, 0x2270($s0)` | aligned stores, back to `0x21c5e4` (quirk 43) |
| `0x21c5a8` | `sw $v0, 0x2288($t2)` / `sw $a1, 0x2260($t2)` | aligned stores, back to `0x21c5b0` (quirk 43) |

launcHER's stubs are its own code, written from that behaviour, not
POPStarter's bytes. They leave the same registers as the original's,
including the values the original leaves behind by accident (quirks 42 and
43); the original's one memory side effect, a 16-byte scratch store inside
its own resident area (`0x143a100`), is not copied, since that area holds
launcHER's code.

### The exit and byte-copy pokes

- `0x20c0ac = j 0x236290`: when POPS's exit to the browser (`jal 0x22d130`
  with `"BootBrowser"` at `0x20c0a4`, or the IGR exit fix's call) returns,
  POPS used to spin at `0x20c0b0..0x20c0c4`; now it calls POPS's own
  `exit()` (the atexit work, then the Exit syscall).
- The spin loop becomes: copy the byte at `0x85a998` to `0x863990`
  (`lui $k1`/`lb $k1`/`lui $k0`/`sb $k1`), then `j 0x21b680`.
- `0x228d5c`: the tail call `j 0x21b680` that ends POPS's `0x228c80` goes
  through that copy first (quirk 44).

`0x85a998` is a word POPS keeps between 0 and `0x80` (written at
`0x228c08` and `0x228c40`); `0x863990` lies in the block POPS clears at
`0x237330`. What the copy is for was not worked out.

### The BIOS shell edits

The PS1 BIOS ROM copy inside POPS starts at `0x24bc20` (PS1 `0xbfc00000`);
these bytes belong to its shell, which runs from PS1 RAM `0x80030000`:

- byte `0x263ed6 = 0x20`: `sw $v0, 0xad0($at)` at `0x263ed4` stores `$zero`,
  so PS1 `0x80050ad0` gets 0 instead of 1;
- halfword `0x263d56 = 0x1000`: `bnez $v0` at `0x263d54` becomes `b`, so the
  function at `0x263d3c` returns -1 right after its first call;
- word `0x263db0 = 0`: removes a `jal 0x3e260` in that function.

They are made after the fix files and the user's commands and before the
region pass, without checking the words first, as in the original. What
they change in the shell's behaviour was not worked out. They are skipped
when any of `gp+0x3b98`, `gp+0x38a4`, `gp+0x344c`, `gp+0x3430` is set, as in
the original: the first two are a loaded user `BIOS.BIN`
([POPSTARTER_USER_BIOS.md](POPSTARTER_USER_BIOS.md)); the other two belong to
the original's OSD loader, which launcHER does not have.

Added 2026-11-11 from
[the gap audit](POPSTARTER_GAP_AUDIT_2026-11-11.md) (host measurements, no
console run): the same four flags also change the region pass that follows,
and by more than one write (known licence: only `0x2649a0` is skipped;
unknown licence: `0x264994..0x2649a0` and the four zero bytes at `0x20f6cc`,
`0x20f6d8`, `0x20f6dc`, `0x20f6e0`); the two OSD flags `gp+0x343c` and
`gp+0x3878` alone skip nothing. Also, within "after the fix files and the
user's commands" the two orders differ: the original runs the fix files
first and `CHEATS.TXT` second, launcHER the other way round
(`handler_pops.c:1419`, `:1450`). Whether any input ends differently because
of that has not been measured.

## The pad hotkeys and the in-game disc swap

The first thing the GP1 hook runs, on every GP1 write, is the always-live
block (`0x232790..0x232c90`). It reads controller 1's buttons (`0x507002`,
active low) and compares them with exact values, so another button held
with a combo cancels it. Every check reads the buttons again, except the
first two, which share one read. In its order:

| Controller 1, nothing else held | What the original does | launcHER |
|---|---|---|
| SELECT+L2+R1, SELECT+R2+L1 | the byte at `0x70003390` (scratchpad, read by POPS) = 0, 1 | same |
| SELECT+L2+R2+TRIANGLE | POPS's lid halfword `0x59c200` = `0x1000`: lid open | same |
| any (every pass) | `+0x28` of both pad blocks (`0x507028`, `0x5070b8`) = 1 | same |
| SELECT+R2+R1, SELECT+L2+L1 | the `$SCANLINES` word at `0x21e454` = `0x22b50006` (on), POPS's own `0x8ca42158` (off), with no cache flush | same, no flush |
| SELECT+L2+R2+SQUARE, while the lid is open | lid = `0x200` (closed), then POPS's disc init (`0x210540`) with the selected slot | same |
| SELECT+L2+R2+UP, RIGHT, DOWN, LEFT | selects slot 0, 1, 2, 3 for the next close, by rewriting the immediate of the `ori` at `0x2328bc` (its own code, no cache flush) | same slots; the selection is a word in the resident config (quirk 49) |
| any (every pass) | each slot whose first word is 0 gets `0x60` bytes from POPS's boot path (`0x1ffecb0`) | same |

So the in-game disc swap is: SELECT+L2+R2+TRIANGLE (open the lid), then
SELECT+L2+R2 and a direction (pick the disc), then SELECT+L2+R2+SQUARE
(close it, load the disc). The four slots (`0x232950..0x232ad0`, `0x60`
bytes each) hold `pfs0:/` and a `DISCS.TXT` line. With no `DISCS.TXT` the
slots are empty, so each gets the boot path and a swap reloads the disc the
game started with.

**DISCS.TXT.** The original reads it at launch (`0x8d5cf8`), first the one
for all games, then the game's own (skipped when the word `gp+0x38dc` or
`gp+0x3460` is set), each from slot 0 over what was there; never in
physical-disc mode (`gp+0x3410` = 1). In a file:

- an empty file changes nothing;
- a `\`, `/` or `:` anywhere and the whole file is ignored (its message:
  "An illegal character was found. Aborded."), the slots keep what they
  held;
- CR and LF end lines and empty lines are skipped; nothing is trimmed and
  there are no comments, so a line of spaces or `# note` is a disc name;
- each of the first four lines becomes `pfs0:/` + the line + one NUL in
  its slot; the slot's other bytes stay; lines after the fourth are not
  read;
- a line of 90 characters or more clears all four slots and stops
  ("VCD %d filename exceeds 89 characters. Aborded."): `pfs0:/`, 89
  characters and the NUL fill a slot exactly.

launcHER: `pops_config_parse_discs`, the same rules byte for byte, in the
same order (global, then per game); the slots go to the resident config,
`PopsResidentConfig.disc_slot` (resident image v13), 16-byte aligned like
the original's because POPS sends the name to the IOP by DMA straight from
the slot. Quirks 45 to 48.

**The disc init.** The original calls POPS's `0x210540` straight from the
GP1 hook, with interrupts disabled, on the POPS thread's stack; launcHER
does the same from its resident code (quirk 50).

**Where the disc opens.** POPS's disc init sends the name to its IOP CD
module, which opens it. On the HDD, `pfs0:/<name>` is a file in the game's
partition. On USB and SMB, POPStarter's PFS wrapper opens `pfs0:/<name>` as
`mass:/POPS/<name>`. launcHER's popfs registers a `pfs` name off the HDD
(`virtualPfs`) that opens `<name>` in the folder of the game it launched,
read-only like every disc. Through it a few names keep launcHER's own
meaning: `IMAGE.VCD` (the launched disc; launcHER's live storage probe
opens `pfs0:IMAGE.VCD`), `SLOT0.VMC`, `SLOT1.VMC` (and `.bak`), `ps1emu`
and `disc/discN`. `IMAGE0.VCD` to `IMAGE3.VCD` are plain files there, so a
`DISCS.TXT` that names its discs `IMAGE1.VCD`, `IMAGE2.VCD` opens those
files (quirk 51).

**launcHER's own swap, removed.** popfs used to have a disc swap of its
own, SELECT+L1+R1, armed when two or more discs were mapped and fed by an
interposition on the SIO2 controller reads. It could switch only while no
disc file was open, and POPS's CD module keeps the disc open while the game
runs, so in game it never switched. It was removed on 2026-11-02 at the
owner's request: popfs no longer touches controller reads, and POPStarter's
combos above are the only disc swap.

## The recompiler hook and `$RECOMPILER_ADDON_0..4`

POPS turns PS1 code into EE code a block at a time. When it has finished a
block, its routine ends at `0x2075c4..0x207600`: it reloads `$s5`, `$s0`,
`$s1`, `$s2`, `$s3`, `$s4` and `$ra` from its frame and stores the block's
last instruction, `$v1` (`addiu $k1, $k1, -n`, the block's cycle count),
at `$a2` (`0x2075f8`). On every launch POPStarter writes
`j 0x143a160; nop` over the `$s2`/`$s3` loads (`0x8747ec`) and copies its
block there (`0x874808`, MAIN `0x96c070`). The block reads the word at PS1
`0xb890` (EE `0x0100b890`), runs what the commands copied into it, reloads
`$s0..$s5` from the frame (the two replaced `ld`s, plus four that POPS
makes or already made with the same values) and returns to `0x2075f4`
with `$ra = 0x2075f4`, where POPS reloads `$ra`. With no command it changes
nothing and takes 22 or 23 instructions, thanks to the launch's own
`j 0x143ffdc` at `0x143a720` (above). Before 2026-11-02 this note said 2,847
branches (about 5,700 instructions, through a block larger than the EE's
16 KB instruction cache): that is the path without that jump, which no
shipped build takes.

The commands are `$RECOMPILER_ADDON_0` to `_4` (handlers `0x89316c`,
`0x893494`, `0x8937bc`, `0x893ae4`, `0x893e4c`). `_0`, `_1` and `_2` copy
code into the block (`0x8d6f64`, `0x8d6fa4`, `0x8d6fe4`), which runs it in
this order:

- word at `0xb890` nonzero: `_1`, then `_2`, then `_0`, but `_0` only after
  `_2`: without `_2` it is skipped on that pass (quirk 54);
- word zero: `_0`.

| Command | What the original's code does |
|---|---|
| `$RECOMPILER_ADDON_0` | the `0x800` bytes before `$a2`, the code POPS emitted last: every word in `0x8bff0001..0x8fffffff` or `0xabff0001..0xafffffff` gets `0x0c000000` added and is stored back with `swr`, so `lw` becomes `lwr` and `sw` becomes `swr` (quirks 52, 53) |
| `$RECOMPILER_ADDON_1` | clears the top byte of PS1 `0xb878` (the start of the code the PS1 side loaded), reads it and the length at `0xb87c`, zeroes `0xb890`, then scans that code, both ends included: a `break 7` (`0x0007000d`) or `break 6` (`0x0006000d`) becomes 0 when the top byte of the word two before it is nonzero (quirks 55, 56) |
| `$RECOMPILER_ADDON_2` | reads the start (its top byte as it is) and the length, clears that byte and `0xb890`, then scans the code, the end excluded, for PS1 BIOS calls: `li $t2, 0xa0` / `jr $t2` / `li $t1, 0x3a`, and `li $t2, 0xb0` / `jr $t2` / `li $t1, 0x38`, `0x52` or `0x5a`, plus the forms with the `li $t1` before the `jr` for A0:3A, B0:38 and B0:5A. Each becomes `jr $ra` / `nop` / `nop` (quirks 56 to 58) |
| `$RECOMPILER_ADDON_3` | POPS's two emit points jump to its code instead: `0x206318` (`sw $v0, 0($s1)` / `addiu $s1, $s1, 4`) and `0x205d1c` (`or $a0, $a0, $v0` / `sw $a0, 0($t4)`). The word POPS emits there is converted as `_0` does it and stored as 0, the word, 0, 0 with `swr`, so it takes 16 bytes instead of 4 (quirks 52, 59, 60) |
| `$RECOMPILER_ADDON_4` | the same jumps, storing the converted word alone. Both commands write the same jumps and `_4` also changes the code they reach, so with both, `_4`'s code runs |

launcHER, POPStarter launches only (Ember launches never reach it):

- `pops_resident_hook_recompiler` writes `j pops_resident_recompiler; nop`
  at `0x2075e8` on every launch, right after the GP1 hook, after checking
  the rest of the epilogue. It is idempotent, and anything else there
  stops the launch.
- `common/src/pops_resident_recompiler.S` is launcHER's own code, written
  from the behaviour above, not POPStarter's bytes. The commands set bits
  in the resident configuration (`POPS_RES_F_RECOMPILER_0/1/2`, resident
  image v14) instead of copying code. On every path it leaves the same
  registers and memory as the original's, the leftovers included. It
  takes fewer instructions (with no command 17 to 19 against the
  original's 22 or 23; with `_0`, about 4,100 per block against about
  9,200), so it is quicker, not slower; the time is not copied.
- `$RECOMPILER_ADDON_3/4`: `pops_resident_hook_recompiler_emit` writes `j`
  and a `nop` at both emit points, to launcHER's `_4` code when that
  command came, else its `_3` code, with the user's other command writes
  (before the opcode pass, as in the original). It checks POPS's words
  first, which the original does not, and a mismatch stops the launch.
- The command names are matched as whole words in any case (quirk 22).

## Not copied yet

- Nothing from the always-live block any more: its `$NOVMC0/1` stores
  (`0x232c90` and `0x232ca0`, branches over a store of 0 to byte `0x507920`
  and to byte `0x527930`, turned on by the handlers writing byte 1 into the
  branch's offset) are copied since 2026-11-02, right after the slot copies
  in `pops_resident_hotkeys`, and checked against the original's block
  through `0x232cb0` (`test_pops_resident.py`). See the inventory.

## Verification

`tools/test_pops_launch_hooks.py` (CI), no external input needed:

- `tools/r5900_mini.py`, a small pure-Python R5900 interpreter (128-bit
  registers, delay slots, address errors on misaligned accesses) and
  assembler, runs the guard stubs from their POPS sites against
  `tools/pops_guard_model.py`, a model of what each original site did, on
  random registers and memory (2,700 runs), and checks the C hooks on
  synthetic cores: exact words, nothing else changed, every word checked
  before any write, idempotent.
- It runs `launcher/src/pops_trampoline.S` with memory filled with a marker
  and checks that it clears exactly what POPStarter clears and copies the
  core; the old trampoline fails this.
- The launch order in `handler_pops.c`: the hooks right after the core
  patches and before the built-in list and the user's commands, the BIOS
  edits right before the region pass, and nothing gating the hooks or the
  resident install.

With `POPSTARTER_TEST_ELF`, the original's own guard stubs pass the same
model. With `POPS_TEST_ELF` too, the original's launch blocks
(`0x8744a0..0x8744b0`, `0x874780..0x874798`, `0x874850..0x874a20`) and its
BIOS block (`0x878f94..0x878fc4`) run over the real core under the
interpreter: launcHER changes the same 28 words, and the jumps differ only
in their targets (each side's own code). The real core also takes the hooks
after launcHER's core patches. With `POPS_RESIDENT_BIN` (the image CMake
builds), the built stubs are the assembled words and pass the model;
`tools/check_pops_resident_image.py` checks the same. With
`POPS_TRAMPOLINE_BIN` (the `.text` of the built `pops_trampoline.S`
object), the built trampoline is the assembled one.

The recompiler hook, in CI (`tools/test_pops_launch_hooks.py`):

- `tools/pops_recompiler_model.py` models the block and the emit code,
  quirks included. launcHER's `pops_resident_recompiler.S`, assembled by
  `tools/r5900_mini.py`, runs from `0x2075e8` on 240 random states of
  registers and memory, 30 for each set of `_0`, `_1` and `_2` (236 run;
  the 4 where the scan would never stop, as the original's would not, are
  left out and have checks of their own), and from both emit points with
  `_3`, `_4` and both, 180 times one to four emits in a row (436 emits).
  All 128 bits of every register and every byte of memory must be the
  model's.
- The C hooks on synthetic cores: the exact words, every word checked
  before anything is written, idempotent, either command's jumps accepted,
  and the opcode pass leaves them alone. The command parser and the
  configuration bits, and the five quirk checks (quirks 54, 56, 57, 58,
  59) on launcHER's code.

With `POPSTARTER_TEST_ELF`, the original's own launch code
(`0x8747e0..0x874830`) and command code install its block on a machine,
and that code passes the same model (238 of 240 random states, the
other 2 never stop; 444 emits) and the same five quirk checks;
launcHER's installers write the same POPS words as the original's for
nine command combinations. With `POPS_RESIDENT_BIN`, the built code is the
assembled code and passes the model; `tools/check_pops_resident_image.py`
(section 9) checks the same.

The pad hotkeys and the disc swap, in CI:

- `tools/test_pops_features.py` checks every `DISCS.TXT` rule above on
  `pops_config_parse_discs` and on the global-then-per-game order of
  `pops_config_discover`. With `POPSTARTER_TEST_ELF` it runs the original's
  reader (`0x8d64b0..0x8d6b5c`) under the interpreter on the same text:
  258 cases, single files and two-file sequences over random earlier
  slots, the same slots byte for byte.
- `tools/test_pops_resident.py` (`Hotkeys`) checks each combo, the exact
  match, the lid order and the boot path copies on
  `pops_resident_hotkeys`. With `POPSTARTER_TEST_ELF` it runs the
  original's always-live block at `0x232790`, as its launch copies it,
  pass for pass beside launcHER's: 150 random button sequences (3,075
  passes, 145 swaps), with the same scratchpad byte, lid, pad flags,
  scanlines word, selected slot, four slots and disc init calls.
- `tools/check_pops_resident_image.py` (section 7b, manual, needs unicorn)
  runs the built image's GP1 entry with a stand-in for POPS's disc init
  at `0x210540` that records its argument, `$gp` and `$sp`: each of the
  four swaps passes its slot, 16-byte aligned with the DMA window inside
  the config, with the lid closed and POPS's `$gp`.
- `tools/test_popfs.py`: through the `pfs` name a `DISCS.TXT` name opens
  in the game's folder, `IMAGE0.VCD` to `IMAGE3.VCD` included, read-only;
  the `pops` name keeps its disc slots.
