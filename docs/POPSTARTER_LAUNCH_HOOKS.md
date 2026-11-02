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
| `0x874764` | copies `0x738` bytes of its own code to `0x232790`: the always-live block the GP1 hook runs (pad hotkeys, slot copies, `$NOVMC0/1` and controller ID stores, the reset combo, the chain slots) | launcHER's own resident GP1 work. The reset combo, controller IDs and chain calls are in it; the pad hotkeys are not yet (below) |
| `0x87477c` | copies `0xd60` bytes to `0x238a90`: its `$SET_TIMINGS`, LibCrypt 2 and cheat code area, entered at `0x239490` | launcHER's own resident code |
| `0x874790` | `0x21a63c = jal 0x239490`: the GP1 hook | `pops_resident_hook_gp1`, **now on every launch** (it was only with cheats, controller IDs or `$SET_TIMINGS`) |
| `0x8747ec` | `0x2075e8..0x2075ef = j 0x143a160; nop` (over two `ld`s near the end of a POPS routine that builds an instruction word and stores it, `sw $v1, 0($a2)` at `0x2075f8`), into the code copied at `0x874808` | **not copied yet** (below) |
| `0x874808` | copies `0x5ea0` bytes to `0x143a160`, the code `0x2075e8` jumps to; the `$RECOMPILER_ADDON_n` commands change it | **not copied yet** |
| `0x874864` | copies `0x160` bytes to `0x143a000`: the nine guard stubs | launcHER's own stubs, `common/src/pops_resident_guards.S` |
| `0x874878..0x874998` | the nine misaligned-read guards (below) | `pops_resident_hook_guards` |
| `0x8749ac..0x874a18` | the exit and byte-copy pokes (below) | `pops_apply_always_on_pokes` |
| `0x876a50`, `0x876a7c` | copies its exit program to `0x1450000` and writes `j 0x1450000` at `0x2362fc` (POPS's `ExecOSD` tail call) | not copied: launcHER keeps its own exit, which the owner confirmed on a console (Tekken) |
| `0x878f9c..0x878fbc` | three edits to the PS1 BIOS shell inside POPS (below), skipped only when a user `BIOS.BIN` or OSD replacement was loaded | `pops_apply_bios_shell_edits`; launcHER loads neither, so it always makes them |
| `0x87c0f8` | `memset(0x70000000, 0, 0x4000)`: the whole scratchpad | the trampoline, step 1 (it cleared POPS's `0x3c30` bytes only) |
| `0x87c130` | `memset(0x502e60, 0, 0x36d1a0)`: POPS's BSS and on up to `0x870000`, where POPStarter's own code starts | the trampoline, step 2: up to `0x870000` too (it stopped at POPS's BSS end, `0x865940`) |
| `0x87c140` | `memset(0x100000, 0, 0x100000)` | the trampoline, step 3 (already the same) |

The three writes gated by `gp+0x3884` (`0x8747b0`, `0x874828`, `0x874848`)
never run in a shipped build: that flag only ever holds the build preset
byte `0x100008`, which is 0 in all five r13 builds (MAIN, DEBUG, USBDELAY,
USBDELAY_DEBUG, USBDELAY_LONGER_DEBUG).

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
they change in the shell's behaviour was not worked out. When launcHER
gains `BIOS.BIN` or OSD support, they must be skipped for those, as the
original does (`gp+0x3b98`, `gp+0x38a4`, `gp+0x344c`, `gp+0x3430`).

## Not copied yet

- **The pad hotkeys and slot copies in the always-live block**
  (`0x232790..0x232c90`), run on every GP1 write in the original. Read
  from its code so far: SELECT+L2+R1 and SELECT+R2+L1 set a byte at
  `0x70003390` to 0 or 1; SELECT+R2+R1 and SELECT+L2+L1 write the
  `$SCANLINES` word at `0x21e454` on and back off; SELECT+L2+R2+TRIANGLE
  sets the halfword at `0x59c200` to `0x1000`, and SELECT+L2+R2+SQUARE
  then sets it to `0x200` and calls POPS's `0x210540` with one of four
  `0x60`-byte slots (`0x232950..0x232ad0`), picked by SELECT+L2+R2 and a
  D-pad direction; four slot copies follow. Every pass also writes 1 to
  `+0x28` of both pad blocks (`0x507028`, `0x5070b8`). Being worked out
  next, then copied with an emulation test against the original block.
- **The recompiler hook** at `0x2075e8` and the `0x5ea0` bytes behind it,
  which the `$RECOMPILER_ADDON_0..4` commands change. It runs on every
  launch in the original. Followed through the copied block (MAIN
  `0x96c070`, run at `0x143a160`): it reads the word at `0x0100b890`, and
  when that is 0 it takes 2,847 branches through the block (all delay
  slots `nop`), reloads `$s0..$s5` from POPS's stack frame (the two
  replaced `ld`s, plus four that POPS makes or already made with the same
  values) and returns to `0x2075f4`, where POPS reloads `$ra`. So without
  an addon it leaves every register and memory word as POPS's own code
  would, and costs only time: about 5,700 instructions, through a block
  larger than the EE's 16 KB instruction cache, on each call of that POPS
  routine. When the word is not 0 it takes another path (`0x143a274`),
  not worked out yet; the only stores to that word found in MAIN write 0.
  Next after the hotkeys, with the `$RECOMPILER_ADDON` commands.

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
