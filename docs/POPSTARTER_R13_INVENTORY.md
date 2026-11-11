# POPStarter r13 feature inventory (2026-10-31)

What "100% POPStarter" means, measured against the original binary rather than
against wikis or memory. Ground truth is POPSLoader's
`bin/POPSLDR/PROFILES/MAIN/POPSTARTER.ELF` (sha256 `734c813e…`), unpacked by
`tools/trace_original_pops_io.py:decode_main` to a 1,350,828-byte image at EE
`0x870000`. `tools/popstarter_r13_commands.py` reproduces the command table
below from that file (metadata only; needs capstone).

**Nothing in this document has been run on a console. Every row marked
PRESENT is NOT TESTED unless the Evidence column says otherwise.**

Status key: **PRESENT** (launcHER does what the original does), **PARTIAL**
(some of it, or an equivalent), **MISSING**, **BLOCKED** (needs POPStarter's
own resident code, see below).

**Corrected 2026-11-11** from
[POPSTARTER_GAP_AUDIT_2026-11-11.md](POPSTARTER_GAP_AUDIT_2026-11-11.md),
with no code change (base `cfebe01`): the rows for `$UNDO_`, the default
IGR, `$USBDELAY_n`, the POPS package, launch paths, SMB, config locations,
`VMCDIR.TXT`, TROJAN/PATCH, the IGR skin, `OSD.BIN`, `BIOS.BIN` and the
physical disc, the `$NOBOOT` and region paragraphs, new rows for things this
table did not list, and the work order at the end. Three rows went from
PRESENT to PARTIAL (the POPS package, config locations, `VMCDIR.TXT`); no
row was upgraded. Where a corrected row
carries a label, it is the audit's: `2x` measured by two independent runs,
`1x` measured once and not independently re-run, `read` read from
disassembly or source, `inferred`. All of it is host work; none of it was
run on a console.

**Brought up to `ef663b2` on 2026-11-11** (second correction pass of the gap
audit; documents only). The rows that the merges `95ba812` (config text),
`173d5de` (IGR skin), `0945127` (`BIOS.BIN` and its loader state),
`21c3476` (`SB.` network files) and `f22a69f` (physical disc, host part)
change say so, as far as the merged code and its tests show; nothing here
was re-measured beyond the audit's S30..S33. Changed status: the IGR skin
and `BIOS.BIN` from MISSING to PARTIAL, `$UNDO_` from PRESENT to PARTIAL
(a launch that fails where the original goes on); the config-text and
`VMCDIR.TXT` rows stay PARTIAL with smaller differences. Work on TROJAN
files and on the review findings for the config-text merge is in progress
on side branches; the rows concerned say only that.

## Why some commands are BLOCKED, and launcHER's resident code

At launch the original copies two blocks of its own code into the POPS image
(`0x738` bytes to `0x232790`, `0xd60` bytes to `0x238a90`) and keeps more
resident at `0x143xxxx`. Several commands only set flags or install jumps into
that code: `$480p` (jump to `0x2394f0`), `$SET_TIMINGS`, `$D2LS(_ALT)`,
`$NOPAD0/1`, `$PAD0ID_0Xhh`/`$PAD1ID_0Xhh`, the `0x232c90` flag of `$NOVMC0`, `$WIDESCREEN`,
`$ULTRA_WIDESCREEN`, `$EYEFINITY`, `$RECOMPILER_ADDON_3/4` and `$FAKELC`
(copies 0x15 bytes from the original's image). Copying that code would ship
POPStarter itself, so these need an independent resident implementation.
(`$FAKELC` turned out to need none: its 21 bytes go into POPS's own LibCrypt
loop, not into resident code, and they are the built-in list's LibCrypt
template, which the generated list already carries; see its row.)

**launcHER now has one** (`common/include/pops_resident.h`,
`common/src/pops_resident_engine.c`). It is built as a small flat image linked
at `0x0143a000`, inside the range the original also keeps for itself, and
copied there as the launcher's last write before handoff, on every
POPStarter launch, as the original copies its own (before 2026-11-02 only
when a command needed it; see
[POPSTARTER_LAUNCH_HOOKS.md](POPSTARTER_LAUNCH_HOOKS.md)). The controller ID
override, `$SET_TIMINGS` and the cheat code run from the same place as in
POPStarter: POPS's GP1 write path (`0x0021a568`, reached from the GPU
register handler `0x0020b4d8` when the game writes `0x1f801814`) has a `nop`
at `0x0021a63c`, reached only while interrupts are enabled, with `di` after
it. POPStarter writes `jal 0x239490` there (its pad checks, controller ID
stores, `$SET_TIMINGS` check and cheat code, in that order, then a return to
`0x0021a640`); launcHER writes a `jal` to its own entry, after checking the
words around it. The `di` runs in the delay slot in both, so the code runs
with interrupts disabled, on the POPS thread's stack. launcHER's entry keeps
every register POPS has (POPS needs `$v1` afterwards); the original keeps
only `k0`/`k1`, the only ones its code uses. launcHER used to run this work
from POPS's VBLANK_START handler instead (the `lui`/`addiu` pair at
`0x0021b184`/`0x0021b18c`); that hook is no longer installed. Like the
original's, the GP1 hook is now written on every launch: until 2026-11-02
launcHER wrote it only for cheats, controller IDs or `$SET_TIMINGS`, so the
reset combo, the built-in list's code calls and `$BREAKPOINT` did not run on
other launches. The PS1 RAM base comes from the word POPS itself stores at
`0x70003364` (`0x0021af98`), so nothing assumes how POPS maps that RAM. The
code is launcHER's own; the original also hooks other places (its code at
`0x01450000`, reached from POPS's `ExecOSD` tail call at `0x002362fc`, is its
exit program, not a cheat engine).

The resident code runs the cheat engine, an independent manual GS DISPLAY
bridge, the text `$480p` progressive bridge, the pad commands, the
widescreen family and `$SET_TIMINGS` (below). [Manual DISPLAY contracts](POPS_MANUAL_DISPLAY_CONTRACTS.md) record
all-six, per-file acceptance and the guarded bridge. No command is BLOCKED
any more (the last one, `$FAKELC`, since 2026-11-02, and it needed no
resident code); the `$NOVMC0/1` per-pass stores are in it since 2026-11-02.

## CHEATS.TXT commands

| Command | Original effect | launcHER |
|---|---|---|
| `$80`, `$30`, `$D0`, `$C0`, `$5000` codes | cheat section from `0x883270` compiles them to MIPS at `0x01a00000`, run from its hook at `0x0021a63c` (POPS's GP1 write path). Stream scan for `$` (case folded, `#` does not hide a code); fixed columns (pos 9 space, pos 14 CR/LF/NUL/space/`$`, non-hex counts as 0); first `C0` hoisted to the front, later ones dropped, values `>= 0x8000` never match (signed `lh` vs `ori`); `D0` after `D0` dropped; first pending `5000` wins, a skipped one comes back as the pending repeat behind the next emitted `D0`; a repeat with no write expands onto address 0 with the last store; the code after a `D0`-gated repeat is always skipped | **PRESENT**: launcHER parses the same columns and compiles the same order (`pops_cheats_compile`); differential test runs random CHEATS.TXT files through the original's own compiler under emulation and compares PS1 RAM (0 differences). Its repeat bugs are copied: after a running low half passes `0xFFFF` each later step adds another 64 KB, and from a running value of `0x20000` the generated `ori` no longer loads k1, so the store repeats k1's last value. Not copyable: the other register that `ori` then changes (from `0x60000` up it also reads one), whose effect on a console is unknown; the test leaves out the files that reach that range. Every copied quirk is listed in [POPSTARTER_QUIRKS_TO_FIX_LATER.md](POPSTARTER_QUIRKS_TO_FIX_LATER.md). **NOT TESTED** on a console |
| `$10/$20/$D1..$D3/$E0/$E1` codes | not POPStarter codes: skipped by its scan | **PRESENT**: skipped the same way |
| PS2-format `$0/$1/$2AAAAAAA VVVVVVVV`, `$S…`, `$T…`, `$=…`, `$!…` | same scan, 18 columns (8-digit value; column 14 must not end the code). `$0/$1/$2`: EE `sb/sh/sw` at a 7-digit address. `$S` (size, cond, `0`, offset `0000`..`3FFF`) on the scratchpad at `0x70000000`; `$T` (size, cond, `00`, offset `000`..`3FF`) at `0x5F800000`; cond 0 write, 1 run next if equal, 2 if not equal, loads signed. `$=`/`$!`: 32-bit compare at an address below `0x02000000`. A PS2 conditional branches over the next code and switches the rest of the file to a reduced loop that knows only writes (which ones depends on the conditional); interactions with `D0` and `5000` as listed in the quirks file | **PRESENT**: launcHER parses the same columns and compiles the same order (`pops_cheats_compile`); its resident code runs them against EE RAM, the scratchpad and the `0x5F800000` page from the same GP1 hook. A second differential test runs random files mixing PS1 and PS2-format codes through the original's compiler under emulation and compares EE RAM, the scratchpad and the page (0 differences). Unaligned or out-of-range codes, which fault in the original, are aligned down or skipped. Quirks 13 to 19 in [POPSTARTER_QUIRKS_TO_FIX_LATER.md](POPSTARTER_QUIRKS_TO_FIX_LATER.md). **NOT TESTED** on a console |
| `$SMOOTH` | `0x21af88=0xa21a22a0341a0001` (64-bit) | **PRESENT**: guarded, original-command differential; no console run |
| `$DX_n $DY_n $MAGH_n $MAGV_n $DW_n $DH_n` | all-six, first-valid per file; fixed GS DISPLAY override | **PRESENT**: independent guarded resident bridge; 228 original file cases plus built-image comparison; no console run |
| `$480p` | static mode/arguments plus resident DISPLAY updates | **PRESENT**: guarded owned context bridge; 31 original text/file sequences and 428 component/bridge cases; no console run; conflicting payloads reject |
| `$LEFTADJ_` | `1..255`: `0x21a0a4=0x64a50f00 + ((4096-n)&255)`, `0x21a0a8=0xfc450000` | **PRESENT**: guarded, original-command differential; no console run |
| `$SCANLINES` | `0x21e454=0x22b50006` | **PRESENT**. In game, SELECT+R2+R1 and SELECT+L2+L1 on controller 1 write the same word on and back off on every launch (the original's always-live block, copied with the disc swap below) |
| `$VCDID_n` | selects a built-in per-game DB entry (handlers `0x890f4c..0x891e78`: 1..4 digits, first command wins, ignored after a fingerprint match) | **PRESENT**: parsed as the original does (fixed + random texts vs the original's handlers), applies the entry when the fingerprint matched nothing; see [POPSTARTER_BUILTIN_DB.md](POPSTARTER_BUILTIN_DB.md). No console run |
| `$SUBCDSTATUS` | `0x20e850/0x20e86c/0x20e87c` | **PRESENT** |
| `$RESET_WARMBOOT` | flag `gp+0x3894` (handler `0x8923a4`), read after the region pass (`0x8795f0..0x879cf4`): walks POPS's embedded PS1 BIOS ROM copy (`0x24bc20..0x2cbb4c`) and rewrites 24 BIOS call stubs (A0: 3A 40 4F 50 53 9A 9B A1; B0: 1A..1F 21 22 23 2A 2B 38 52 5A; C0: 0B 14) to A0:A0 `_boot`, and changes what the in-game reset combo makes the PS1 jump to: instead of `0xbfc00000` it stores the SystemErrorExit (A0:3A) stub's address, meaning to use its PS1 ROM address but storing the EE address of the stub inside POPS's copy (quirk 26), through its own resident block (`0x232cf4..0x232d08`, which takes over the breakpoint handler's slot, quirk 25) | **PRESENT**: `pops_apply_reset_warmboot` (same scan, same pokes, same stored address) plus `PopsResidentConfig.reset_vector`; the reset combo itself (SELECT+L2+R2+CROSS on port 0 sets the PS1 jump word at scratchpad 0, always live in the original) is now in the GP1 work too, live on every launch since the GP1 hook is (2026-11-02). Differential test on the real core and random cores against the original's block run as shipped; see [POPSTARTER_RESET_WARMBOOT.md](POPSTARTER_RESET_WARMBOOT.md). **NOT TESTED** on a console |
| `$MUTE_CDDA` / `$UNDO_MUTE_CDDA` | `0x20f0b6`, `0x20ebf2`, `0x20f0e0` | **PRESENT** |
| `$MUTE_VAB` | five SPU sites | **PRESENT** |
| `$MUTE_ALL` | `0x213ff4=0` | **PRESENT** |
| `$CODECACHE_ADDON_0/1/2` | `0x202734` | **PRESENT** |
| `$RECOMPILER_ADDON_0/1/2` | helpers at `0x8d6f64/0x8d6fa4/0x8d6fe4` copy code into the block behind the recompiler hook at `0x2075e8` (written on every launch). Word at PS1 `0xb890` nonzero: `_1` (zero guarded `break 7`/`break 6` in the loaded code), then `_2` (PS1 BIOS call stubs there become `jr $ra`), then `_0`; zero: `_0` (`lw`/`sw` in the `0x800` bytes POPS emitted last become `lwr`/`swr`) | **PRESENT**: launcHER's own resident code (`pops_resident_recompiler.S`, resident image v14), the commands set its flags. It and the original's own code pass the same model on 240 random states each (the few where the scan never stops left out), with the same leftovers, and five quirk checks. Quirks 52 to 58. See [POPSTARTER_LAUNCH_HOOKS.md](POPSTARTER_LAUNCH_HOOKS.md). **NOT TESTED** on a console |
| `$RECOMPILER_ADDON_3/4` | POPS's emit points `0x206318` and `0x205d1c` jump to resident code that converts the emitted word as `_0` does and stores it with `swr`: `_3` as 0, word, 0, 0; `_4` alone (`_4` wins when both are given) | **PRESENT**: `pops_resident_hook_recompiler_emit` writes the same POPS words as the original (checked first); launcHER's emit code passes the same model as the original's, every emit sequence. Quirks 52, 59, 60. **NOT TESTED** on a console |
| `$ORIGINAL_OPCODES` | flag `gp+0x38c4`; skips the opcode pass `0x87c4a0` that otherwise runs on every launch (POPS's `lw`/`sw` and recompiler templates become `lwr`/`swr`, 10,210 halfwords on the reference core) | **PRESENT**: the pass now runs on every POPStarter launch (it never ran before), identical to the original's on the real core; `$ORIGINAL_OPCODES` skips it. See [POPSTARTER_OPCODE_PASS.md](POPSTARTER_OPCODE_PASS.md). No console run |
| `$UNDO_COMPATIBILITY_CODES`, `$UNDO_GAME_FIXES`, `$UNDO_LIBCRYPT_FIX` | handlers `0x89453c/0x894ab8/0x894db4`: all write `0x2525b0=0x1bfc` (BIOS OSD on), but skip that one write when a user `BIOS.BIN` was loaded (`gp+0x38a4` or `gp+0x3b98` set; read at `0x8948f0`, `0x894d4c`, `0x895088`; `2x` for the reader sites, `1x` for the skip); UNDO_COMPAT writes 22 compat-mode sites (pristine words, plus `0x20083c=0x1000000a`, `0x20085c=0` as modes 2/5), which also restores `$SUBCDSTATUS`'s sites; UNDO_LIBCRYPT rewrites `0x210cf8..0x210d0c` with pristine words | **PRESENT**: every core write matches the original's handlers (interpreter test, external MAIN), applied before `$COMPATIBILITY_0x` as in the original. Left out: `$UNDO_GAME_FIXES` `0x2397d8` and `$UNDO_LIBCRYPT_FIX` `0x239780/0x239784`, which land in the original's own resident blob, not POPS code. Since `0945127` the `BIOS.BIN` exception is in launcHER (`pops_apply_undo_tokens_rom` follows the loader state; `tools/test_pops_user_bios.py`, 72 cases through the original's command reader, equal). **PARTIAL** since `ef663b2` (was PRESENT): a built-in entry with compatibility modes followed by `$UNDO_COMPATIBILITY_CODES` is refused with `-EINVAL` for 294 of the 624 built-in entries that apply to the real core, where the original puts POPS's words back and goes on (`docs/POPSTARTER_USER_BIOS.md`, known gap; the test marks it as an expected failure). The order of `$UNDO_` against fix files still differs at `0x2525b0` (28 of 270 launch-sequence scenarios, that document's difference 2). No console run |
| `$WIDESCREEN`, `$ULTRA_WIDESCREEN`, `$EYEFINITY` | hooks POPS's GTE perspective transform (RTPS/RTPT): the MAC1 store at `0x2089a8` becomes x·75/100 (`$WIDESCREEN`, 16:9) or x/4 (`$EYEFINITY`, 48:9); `$ULTRA_WIDESCREEN` also scales again at the IR1 store `0x208a2c` (x·0.5625 overall), writing the result to MAC1 and leaving IR1 unstored. Each handler rewrites all sites, so the last command wins | **PRESENT**: own guarded stubs, same arithmetic (32-bit product, truncating division) and the same ULTRA register effect; handler writes checked against the original, built stubs run under emulation on 414 values per mode; **NOT TESTED** on a console |
| `$ROLLBACK` | restores 10 breakpoint sites | **PRESENT** |
| `$SET_TIMINGS` | enables a pass in its copied code (`0x238a90` = `b 0x238c50`, then `0x238cfc` NOPs that branch after the first pass). First pass, once POPS has loaded the slot 0 VMC image (word `0x507930` nonzero): if offset `0x800` of that image (`0x508130`) holds `"01"`, restore the timing words `0x502770`, `0x700033e0`, `0x700033e4` from `+4/+8/+12`; otherwise write `"01->"` and the current values there. Later passes: pad 1 alone holding L1/L2 adds ±1 to `0x700033e0`, R1/R2 ±1 to `0x700033e4`; otherwise pad 2 alone holding L1/L2 adds ±1 and R1/R2 ±0x10 to `0x502770`; each new value is also copied into the VMC image | **PRESENT**: resident code, from the same GP1 hook as the original. Restores a saved copy and, like the original, writes the `"01->"` copy and every new value into the slot 0 VMC image (user decision 2026-10-31; `POPS_RES_F_TIMINGS_SAVE`). Handler writes checked against the original; 240 random 40-frame runs match the original's own block (timings and the card copy); the built image is run under emulation. Both run once per GP1 write made with interrupts enabled, so the adjust speed follows the game the same way; **NOT TESTED** on a console |
| `$BREAKPOINT0/1` | handlers `0x8960c4` / `0x896310` call `FUN_008d6da4(0,0)` / `(1,1)`: chain call at `0x232d08` plus the built-in list's breakpoint-killer template at `0x01460000` with a new gate: `$BREAKPOINT0` scans once while PS1 RAM `0x1ffdf4 != 2`, then disables itself; `$BREAKPOINT1` scans while port 0 holds SELECT+L2+R2+CIRCLE. Last one wins; replaces a built-in entry's handler | **PRESENT**: `pops_breakpoint_build` (same bytes as the original for every order of up to three commands, under emulation), the built-in path's chain call, `$RESET_WARMBOOT` still drops it. See [POPSTARTER_BREAKPOINT.md](POPSTARTER_BREAKPOINT.md). Quirks 38 to 40. **NOT TESTED** on a console |
| `$NOVMC0` | its handler (`0x8966dc`) writes byte 1 into the branch at `0x232c90` in the always-live block (`0x8d6b9c`), turning on its store: byte `0x507920` = 0 on every GP1 write. That is the low byte of POPS's card 0 state word, whose bit 0 says the card is there: the game then finds no card 0, and POPS's card writer leaves it alone. POPS still opens (and if missing creates) card 0's file | **PRESENT** since 2026-11-02: the same store every pass in launcHER's resident code (`POPS_RES_F_NOVMC0`, image v15); SLOT0.VMC prepared as on any launch. Before that launcHER wrote `0x2007b4=0` (the original's other helper, FUN_008dc12c(1), which r13 never calls), which made POPS skip its whole card setup: both cards were gone. No console run |
| `$NOVMC1` | the same at `0x232ca0` (byte `0x527930` = 0 on every GP1 write), plus `0x20d0e0=li a0,0` (POPS's card setup stops after card 0). A built-in entry's card 1 off (FUN_008dc12c(2)) is that core write only. On `XX.`/`SB.` launches POPStarter itself makes SLOT0/SLOT1.VMC before POPS runs (`0x8d8050`, failures ignored), skipping SLOT1 only after a built-in entry's card 1 off, not after `$NOVMC1` | **PRESENT** since 2026-11-02: core write, per-pass store (`POPS_RES_F_NOVMC1`); a built-in entry's card 1 off is the core write only (`builtin_no_vmc1`). SLOT1.VMC: not made after a built-in card 1 off; after `$NOVMC1` alone made on non-HDD launches, a failure ignored, and not on the HDD, as in the original. No console run |
| `$NOPAD0/1`, `$PAD0ID_0Xhh`, `$PAD1ID_0Xhh` | enable a store in its copied code that forces the controller ID POPS reports for that port (`0x507034`/`0x5070c4`): 1 for `$NOPADn`, `hh` (two hex digits) for `$PADnID` | **PRESENT**: resident code writes the same ID from the same GP1 hook as the original; 310 command sequences match the original's own handlers; **NOT TESTED** on a console |
| `$D2LS`, `$D2LS_ALT` | `$D2LS`: both ports report 0x41 (digital) and POPS's pad read (`0x237798`) swaps the D-pad and the left stick. `$D2LS_ALT`: the swap only; it switches the ID override back off when the swap was already on, and otherwise makes an earlier override report 0x41 | **PRESENT**: own hooks at the pad read's entry and return (guarded); the built image matches the original's swap on 604 readings under emulation; digital-mode readings are left alone (the original would cancel the real D-pad there); **NOT TESTED** on a console |
| `$IGR0..$IGR5` | combo masks `0x404f/0x900/0x90f` at `0x228a20/0x228a50`; 3..5 jump to `0x20c08c` | **PRESENT** (was: `$IGR0` meant "IGR off") |
| `$NOIGR` | `0x228a56=0x1000` + pristine `0x228a5c/60` | **PRESENT** |
| no IGR command | nothing is written at `0x228a20..0x228a68`: Sony's combo test (mask `0x0904`) and Sony's yes/no dialog stay as shipped (`read`: the command table shows only `$IGR0..5`/`$NOIGR` writing there). After YES the original leaves through its own exit program at `0x1450000` | **PARTIAL**, a deliberate difference: launcHER rewrites `0x228a5c..0x228a68` to exit directly (`pops_modes_patches.c:1279-1299`), so the dialog never opens and an IGR skin could only show under `$IGR0..2`. The owner confirmed the direct exit on Tekken. Sony's dialog followed by YES under launcHER's own exit has never been run on a console. Changing the default is an owner decision |
| `$NOPAL` | stops European auto PAL | **PRESENT**; `$PAL2NTSC`/`$FORCENTSC` are now aliases |
| `$FORCEPAL` | PAL patch + region letter `E` | **PRESENT**; was invented values. The first review of the config-text merge `95ba812` reports one difference in when the command is taken (after a `$480P`); the answer is in progress on a side branch, and this row is not changed until it lands |
| `$XPOS_n`, `$YPOS_n`, `$DWSTRETCH_n`, `$DWCROP_n` | unsigned decimal immediate fields plus store suppression; X/Y first valid command wins | **PRESENT**: guarded, original-command differential; X/Y 0..65535 (up to 5 digits), width commands 0..9999 (up to 4 digits); no console run |
| `$CACHE1` | `0x20fff4`, `0x210120`, `0x2101ac` | **PRESENT** |
| `$FAKELC` | handler `0x89caf0`: clears the per-game bytes of the built-in list's LibCrypt template and copies its 21 bytes over POPS's LibCrypt loop at `0x210cf8` where the command stands (the bytes `$UNDO_LIBCRYPT_FIX` puts back are POPS's own, so the later of the two wins); sets `gp+0x3424`, never cleared, so a `$VCDID_n` after it runs its entry with 216 arms skipping part of themselves (213 lose their LibCrypt write; 207..216 also their game-fix code and breakpoint handler, 230/231 their game-fix code, 232 that, three core writes and its sub-CD flag) | **PRESENT** (2026-11-02): `pops_apply_fakelc` in the config pass, after the `$UNDO_` writes unless an `$UNDO_LIBCRYPT_FIX` comes later; the cut runs generated from the original (`POPS_BUILTIN_AFTER_FAKELC`). All 625 entries run after it match the original, and 27 fixed plus 60 random orders of `$FAKELC`, `$UNDO_LIBCRYPT_FIX` and `$VCDID_n` match through the original's whole parser (`tools/test_pops_builtin_db.py`). Also fixed: `$VCDID_0` no longer blocks a later `$VCDID_n`. Quirk 61 (and 22, 23). See [POPSTARTER_BUILTIN_DB.md](POPSTARTER_BUILTIN_DB.md#after-a-fakelc). **NOT TESTED** on a console |
| `$SAFEMODE` | cheat gate: skip codes while PS1 RAM `0x1ffea0` reads `"STEM"` (`0x4d455453`) | **PRESENT**: same address and value as the original's emitted gate (0x89e954); host + unicorn checked; no console run |
| `$SAFEMODE2`, `$NOSAFEMODE` | `$SAFEMODE2`: skip codes while PS1 RAM `0x1ffdf4 == 2`; `$NOSAFEMODE` clears both (`$SAFEMODE` is tested first) | **PRESENT**: same gate and order as the original; no console run |
| `$HDTVFIX` / `$NOHDTVFIX` | `0x23acb0/0x23ad0c` = `li a0,1` / pristine | **PRESENT**; `$HDTVFIX` was writing an invented site |
| `$LOAD_PADMAN`, `$KILL_PADMAN` | flags `gp+0x38a8` / `gp+0x3870`; after the IOP reset both poke `0x200358=0` and `0x200362=0x1000` (POPS no longer starts its embedded padman_hsync); `$LOAD_PADMAN` starts it itself first (`0x2cd560`, `0xadf0` bytes, fatal on failure) | **PRESENT**: same pokes, same module start, skipped when a `MODULE_n.IRX` is named "padman" (`gp+0x3824`). See [POPSTARTER_PADMAN.md](POPSTARTER_PADMAN.md). No console run |
| `$USBDELAY_n` | handler `0x89dbe0`: `$USBDELAY_` + exactly one digit + a terminator writes byte `0x100017` (shipped value 1 in all four profiles, `2x`). Only consumer `0x879d04..0x879e58`: on `XX.`/`SB.` launches only, the byte replaces the word `DLAY` (`0x91fb30`) in the embedded PFS wrapper IRX. Run on a host with its imports modelled, the wrapper calls `thbase` import 33 once, with n x 1,000,000 (5,000,000 if unpatched), before its first backend open and in none of the later callbacks run (`2x` for the patch and the wrapper's arithmetic; `1x` for the call sequence, gap audit S28; that this is a `DelayThread` wait of n seconds on a real IOP is `inferred`, the wait itself was never observed) | **PARTIAL**: since `95ba812` the command is parsed as the original parses it (one digit and a terminator; `CMD_USBDELAY` in `pops_config.c`, `tools/test_pops_config_text.py`). Still different: the default is 0, not 1, and launcHER sleeps `n` seconds on the EE after the module loads, on any device (`sleep(cfg.usb_delay)`, `handler_pops.c:1985`). No delay in popfs. Review answers for that merge are in progress on a side branch. NOT TESTED on a console |
| `$COMPATIBILITY_0x01..0x07` | FUN_008dc2c4 modes | **PRESENT** (Mode 8 has no branch in the original either) |

Removed because the original has no such command and the patches were
invented: `$480i $576p $576i $240p $VMODE_n` (core writes at `0x2061A0/0x2061E0`),
`$DITHER_OFF/$NODITHER` (NOP at `0x205D58`), `$FASTMIPS/$SLOWMIPS` (NOP at
`0x2010A0`) and the `$NOBOOT` "BIOS shell" byte at `0x210cf8`, which is inside
the LibCrypt routine (the original's `$UNDO_LIBCRYPT_FIX` restores
`0x2442ffff` there). They still parse, so old files load, but they write
nothing. `$NOBOOT` keeps only the `0x2525b0=0x1bfc` OSD write.

Correction 2026-11-11: `$NOBOOT` and `$BIOS` are not r13 commands at all.
`tools/popstarter_r13_commands.py` lists 72 command lines for MAIN and none
contains either name (`2x`). The original ignores the token; the
`0x2525b0` write is launcHER's own (`pops_config.c:319`,
`pops_modes_patches.c:1575-1582`), so after a mode 6 a file containing
`$NOBOOT` ends differently in launcHER. `MODE n` / `$MODE n`, `PATCHES.TXT`
and `MODES.TXT` are launcHER-only too. Whether these stay as documented
extensions is an owner decision.

## Region and video (0x879034..0x8795f0)

The original reads 4 bytes at VCD offset `0x102514`: the licence text in
sector 4 (`Euro`, `Amer`, `of A`, `Inc.`). POPS itself runs NTSC; the "to PAL"
patch (FUN_008dc218: `0x21af94=3`, `0x502770=0xa6300`, `0x23b018=0x6b`,
`0x23b01c=0x2cb`, the same values a PATCH file's PAL action writes) is applied
to European discs unless `$NOPAL`/`$480p`, and for `$FORCEPAL`. It also writes
region letters at `0x2cbb72` (E/A/J/T), `0x20f6cc` (E/A/I) and the PS1 BIOS
region check at `0x2649a0` (`li a0,'E'/'A'/'I'`, or four zeroed checks for an
unknown disc).

When a user `BIOS.BIN` or an `OSD.BIN` was loaded (any one of the flags
`gp+0x3b98`, `gp+0x38a4`, `gp+0x344c`, `gp+0x3430`), the pass skips more
than one write, and what it skips depends on the licence (`2x`, corrected
2026-11-11; the earlier sentence here said only "the BIOS write is
skipped"):

- known licence: only the `0x2649a0` write is skipped. The letters at
  `0x2cbb72` and `0x20f6cc` are still written.
- unknown licence: `0x264994`, `0x264998`, `0x26499c` and `0x2649a0` are
  skipped, and so are the four zero bytes at `0x20f6cc`, `0x20f6d8`,
  `0x20f6dc`, `0x20f6e0` in every arm where the unflagged run writes them.

The three PS1 BIOS shell edits before the pass (`0x878f64..0x878fc4`) are
skipped under the same four flags. At `cfebe01` launcHER set none of these
flags and ran both steps unconditionally. Since `0945127`
`pops_apply_bios_shell_edits_rom` and `pops_apply_region_rom` take the loader
state (`PopsUserRomState`) and follow all four flags
(`tools/test_pops_user_bios.py`: 131 flag combinations for the shell slice,
342 region cases, equal to the original under Unicorn). Only the two
`BIOS.BIN` flags are ever set in a launch: launcHER has no `OSD.BIN` loader,
so the OSD flags stay 0.

launcHER before this change auto-applied the PAL values to every US/Japanese
disc on an NTSC console (labelled "PAL2NTSC"), wrote no region letters, and
had no European auto PAL. `pops_apply_region` now follows the original, after
the fix files so a PATCH file's disable-auto still wins. FORCEPAL is now
deferred to that pass as well. [Ordered PATCH state contracts](POPS_PATCH_VIDEO_STATE.md)
record 60 original region-control-flow combinations. **No console test.**

## Launcher, file and device features

| Original feature (from its banners and paths) | launcHER |
|---|---|
| POPS_IOX.PAK / POPS.PAK / POPS.ELF + IOPRP252.IMG / IOPRP.IMG. Original (`FUN_0087cf68`, `read`, not emulated): `XX.`/`SB.` take `mass:/POPS/POPS_IOX.PAK` (exactly `0xe50b8` bytes), on USB then `POPS.PAK` (`0xe6240`), then `POPS.ELF` (`0x30530c`) with `IOPRP252.IMG` or `IOPRP.IMG`; HDD takes only `pfs1:/POPS/POPS.ELF` with `IOPRP252.IMG` or `IOPRP.IMG` | **PARTIAL** (was PRESENT; corrected 2026-11-11): `POPS_IOX.PAK`, `POPS.PAK` and `POPS.ELF` + `IOPRP252.IMG` are found (`handler_pops.c:161-186`) and accepted by SHA-256 instead of the original's size and signature checks. The `IOPRP.IMG` fallback is **not implemented**. launcHER searches more folders than the original, and its list still holds a test folder (`ata0:/LAUNCHER-TEST-20261013-A/`, `handler_pops.c:153`) |
| Launch type from `argv[0]` (`FUN_008d8db8`, `read`, never executed): 1 = `hdd0:...:PATINFO` or `:pfs:/` with `LAUNCHER`/`EXECUTE` `.ELF`/`.KELF`; 2 = `PP.`/`__.`; 3 = `XX.`/`SB.`; else 0. Types 1 and 2 open `pfs0:IMAGE0.VCD` in the launch partition; type 0 opens `<name>.VCD` in `hdd0:__.POPS`; type 3 opens `mass:/POPS/<name>.VCD` | **PARTIAL**: launcHER's target is a `.vcd` path and its own resolver (`common/src/launch_args.c`) builds the candidates. It uses `IMAGE.VCD` (`:633-694`), not `IMAGE0.VCD`; `hdd0:...:PATINFO` goes to launcHER's generic PATINFO handler (`launcher/src/main.c:56`), not to a type 1 POPS launch. Per device see `POPS_PARITY_AUDIT_2026-10-28.md` (its device rows were not re-checked on 2026-11-11) |
| `XX.`/`SB.` scan of `argv[0]` (`0x8714b8..0x8719c4`): a `:`, `/` or `\` must precede the three characters; all-upper or all-lower only; any path component qualifies (`2x` for `XX.`, 12 strings; the `SB.` half is `read` only) | **PARTIAL**: `extract_base_name` (`launch_args.c:93-122`) looks only at the last component, accepts mixed case and accepts a bare name with no separator |
| `argc == 0`, or `argv[0]` beginning `cdrom`: Exit (`0x871328..0x8713c8`, `2x` static) | **MISSING**. It may not apply to a launcher whose target is a `.vcd` path; decide with the launch-argument work |
| Numbered folders (`read`, partly undecoded): type 3 retries `mass:/POPS0/`..`mass:/POPS9/` (`0x8762cc..0x876690`) and uses the digit for the per-game files; type 0 retries ten partition names (`0x875d94..0x875fa4`; `__.POPS0`..`__.POPS9` `inferred`) | **MISSING**: no numbered folder or partition candidates |
| HDD layout (`read`): everything except the VCD comes from `hdd0:__common` mounted as `pfs1`: `pfs1:/POPS/POPS.ELF`, IOPRP, `MODULE_n.IRX`, IGR skin, `OSD.BIN`, `BIOS.BIN`, fix files, `CHEATS.TXT`, `VMCDIR.TXT`, `DISCS.TXT`, and `pfs1:/POPS/<title>/` with the VMCs. A failed mount is fatal | **MISSING**: `__common` does not occur in launcHER's sources. launcHER reads per-game files from the VCD's own folder (`handler_pops.c:870-884`), which is the original's folder only when the VCD sits in the device POPS folder on USB/SMB. The HDD locations have not been compared file by file |
| `icon.sys` and `list.ico` written into the game's folder on HDD launches when absent (`FUN_008d8050` branch at `0x8d8738`; `read`, only the tail of the function examined) | **MISSING** |
| Name length: `<folder>/<name>.VCD` reaching 80 characters is fatal ("Please shorten ...", `0x875a34..0x875aa8`, `read`) | **MISSING**: launcHER cuts the title to 63 characters without a message (`launch_args.c:549`) |
| SMB config from `mc?:/POPSTARTER/` (SMBCONFIG.DAT, IPCONFIG.DAT, IRX set). Original (`read`; parsers `1x`): `mc0:` then `mc1:`; `IPCONFIG.DAT` optional (7..127 bytes), `SMBCONFIG.DAT` required (7..4095 bytes, `server[:port] share[:sharepassword]`, then optional user and password lines); external `poweroff`, `ps2dev9`, `smsutils` (optional), `ps2ip`, `ps2smap`, `smbman` IRX files, `smbman` patched in RAM to register as `mass`; LOGON, ECHO, OPENSHARE, then up to 120 tries for `mass:/POPS/POPS_IOX.PAK` | **PARTIAL**: launcHER's own network config and embedded modules. `IPCONFIG.DAT` is required (`handler_smb.c:52-54`), `SMBCONFIG.DAT` goes through launcHER's own parser, the share is `smb:`, and there is no ECHO. launcHER's parser gave a different result from the original's on 12 of 20 probe texts (`1x`). That is still every SMB launch except one kind: since `21c3476` a launch whose target is a PS1 disc image and whose name carries `SB.` uses the original's parsers for both files (`common/src/pops_smb_config.c`), `IPCONFIG.DAT` optional, LOGON, ECHO, OPENSHARE, `mc0:`/`mc1:` `POPSTARTER/` first; differences and evidence in [POPSTARTER_SMB_CONFIG.md](POPSTARTER_SMB_CONFIG.md). External IRX set, `mass` rename and the connect loop not copied. Not reviewed. No console run |
| LAUNCHER.ELF / EXECUTE.ELF must be renamed (messages). Shown only when `argv[0]` is not on `hdd0:` (or in mass mode) and names one of those files, and only on non-quiet profiles: MAIN never shows them (`read`) | **MISSING** (cosmetic) |
| Preset block `0x100008..0x10002f` (file offsets `0x408..0x42f`, read at `0x870bd0..0x871324`): 40 build-time bytes that select debug output, the eight forced compat modes, the always-on core patches, the IGR skin, the `MODULE_n.IRX` loader, the auto-patch level and the two USB delays. The four POPSLoader profiles differ only at `0x100010` and `0x100013` (`2x`); per-byte table in the gap audit, section 9 | **PARTIAL**: launcHER has no preset block and behaves as one fixed setting. `pops_config_load_table`/`pops_config_export_table` (`pops_config.c:931`, `:956`) describe a different 32-byte mapping and are called only by a test. Whether launcHER applies exactly the core patches the MAIN values select was not re-checked on 2026-11-11 |
| Second USB delay: preset byte `0x100013` (2 in MAIN, 6 in the USBDELAY profiles) shifted left 24 is the count of an EE busy loop after the USB drivers start (`0x8721c4`, `0x87add8`; `1x`) | **MISSING**. Copying a CPU-speed loop is an owner decision |
| VMC directory relinker (VMCDIR.TXT), SLOT0/1.VMC | **PARTIAL** (was PRESENT; `1x`): at `cfebe01` the acceptance rules for `VMCDIR.TXT` differed: the original ignores a file over 103 bytes or containing `\`, `/`, `:`, CR or LF and continues, launcHER aborted the launch for some of those and trimmed text the original keeps or rejects. Since `95ba812` `pops_config_parse_vmcdir` takes a file as the original does (ignored files never abort, nothing trimmed, an empty file means the POPS folder; [POPSTARTER_CONFIG_TEXT.md](POPSTARTER_CONFIG_TEXT.md)). Still different: launcHER also looks for cards named `<serial>.VMC0` / `<game>.VMC0` beside `SLOT0.VMC`, and names a new card in the POPS folder `<serial>.VMC0`. Review answers for that merge are in progress on a side branch |
| DISCS.TXT disc swap, D-pad assignment, lid emulation | **PRESENT** (2026-11-02): `DISCS.TXT` read as the original reads it, global then per game (`pops_config_parse_discs`; 258 cases match the original's reader under emulation), and the original's in-game swap from the resident GP1 work on every launch: SELECT+L2+R2+TRIANGLE opens the lid, SELECT+L2+R2 and UP/RIGHT/DOWN/LEFT pick disc 1 to 4, SELECT+L2+R2+SQUARE closes it and loads that disc through POPS's own disc init (150 random button sequences, 3,075 passes, match the original's always-live block). The disc opens through popfs's `pfs` name in the launched game's folder (POPStarter: `mass:/POPS/` off the HDD). Quirks 45 to 51. See [POPSTARTER_LAUNCH_HOOKS.md](POPSTARTER_LAUNCH_HOOKS.md). **NOT TESTED** on a console |
| CHEATS.TXT / per-title config locations. The original builds names only for `OSD.BIN`, `BIOS.BIN`, `TROJAN_n.BIN`, `PATCH_n.BIN`, `CHEATS.TXT`, `VMCDIR.TXT` and `DISCS.TXT`, all under the game device's POPS folder (`1x`). It recognises a command at any `$`, whatever precedes it (`#$SMOOTH` applies), treats `$` as a terminator and TAB as not one (`1x`) | **PARTIAL** (was PRESENT; corrected 2026-11-11): at `cfebe01` launcHER ignored a command that follows `#`, `;` or other text and split on TAB. Since `95ba812` `pops_config_parse_text` makes the original's pass (a command at any `$`, the original's terminators and handler order; [POPSTARTER_CONFIG_TEXT.md](POPSTARTER_CONFIG_TEXT.md)). Still different: launcHER's own tokens (`$NOBOOT`, `MODE n`, `$FIX_*` and others) are still read with launcHER's earlier rules, one cheat list and one safe-mode gate for all files, files over 1 MiB refused, and the differences the first review of that merge reports (answers in progress on a side branch). `PATCHES.TXT`, `MODES.TXT` and the `mc0:`/`mc1:` config folders are launcHER-only. On HDD the folder differs (see the HDD layout row) |
| TROJAN_n.BIN / PATCH_n.BIN, all games and per game | **PARTIAL**: payload, modes, PAL, disable-auto and video actions 6/7 (since `a8da126` these jump to launcHER's own resident progressive entry, behind the original's custom-video gate; `test_pops_fix_files.py` matches the original on 100 ordered file sequences). Only the PATCH format-1 record the original's loader was measured with is accepted; other formats are rejected. **Corpus result 2026-11-11:** of the fix files shipped in community packs (REPOP `popstarter/`: 3,952 TROJAN files, 509 unique; 870 PATCH, 10 unique; `2x`), every unique TROJAN loads outside the POPS core (`0x1431000` upward) and hooks one of ten call slots in the original's always-live block; launcHER's `pops_fix_stage` rejects all 509 with -3 and accepts all 10 PATCH files (`2x`). That the original's loader accepts all 509 was measured on a host three times with three separate harnesses (`2x`; gap audit S27); file calls were models and no payload was executed. A rejected fix file ends the launcHER launch (`handler_pops.c:316-318`), where the original prints "Invalid" and goes on. Further rule differences (`1x`): TROJAN formats 2 and 3, `hdr[0x0e]`, payload alignment, entry outside the payload, ignored PATCH bytes, the format-3 "outdated" skip. The original also runs fix files before `CHEATS.TXT`; launcHER runs them after (both inside `pops_stage_user_files` since `0945127`). Folders: the original uses the device POPS folder, launcHER the VCD's folder. TROJAN work is in progress on a side branch; this row describes the merged code at `ef663b2`. No console run |
| IGR menu skin (IGR_BG/NO/YES.TM2). `FUN_0087e464`, one caller `0x876b18`: from `pfs1:/POPS/` or `mass:/POPS/` only (no per-game folder), raw copy over Sony's own TIM2 files at `0x2feff0` (max `0x4c300` bytes), `0x34b2f0` and `0x34d0b0` (max 7,612 bytes each), rest of the slot zeroed, no TIM2 check, no file outcome is an error (`2x`). The function returns 1 then; it returns 0 without opening anything when the abort flag `gp+0x38dc` is set, and -666 with that flag set after a failed POPS folder check, which also sets `gp+0x3460` (every later current-game loader is skipped) and `gp+0x3868` (gap audit section 6, S23, S31). A community `PATCH_5.BIN` also replaces these three pictures, in the original and in launcHER (S27) | **PARTIAL** since `173d5de` (was MISSING): `pops_stage_igr_skin` stages the three files after the built-in entry, size checked first, never fatal, compared with the original under Unicorn by `tools/test_pops_igr_skin.py` (48 tests, 141 runs of the original with `gp+0x3868 = 1`). Differences ([POPSTARTER_IGR_SKIN.md](POPSTARTER_IGR_SKIN.md)): read from the `.VCD`'s folder, not `POPS/`; no `gp+0x38dc` gate; the POPS folder check and its -666 path (with its writes of `gp+0x3460` and `gp+0x3868`, gap audit S31) not copied; a failed size query leaves the slot alone. Visible only under `$IGR0..2` (default IGR row). README and the setup page said "not supported" from 2026-11-11 until this merge; they have not been updated since. No console run |
| Replacement OSD image (`OSD.BIN`). `FUN_0087eb24`, callers `0x876bac`/`0x876ea0`: `0x40`-byte header (`PS-X OSD`, version 1 or 2, build id, load, entry, 24-bit size, label, up to four compat modes), body to `0x263c20` (v1, max `0x4c000`) or `0x262b80` (v2, max `0x4d0a0`), POPS code at `0x252c28..0x252c4b` rewritten, `0x20079a=0x1000` (`2x` for format and writes, `1x` for the full rejection list). No real sample file was available | **MISSING** |
| User BIOS.BIN. `FUN_0088019c`, callers `0x876cd8`/`0x876fd8`: the only test is file size > `0x7ff8e`; the first `0x7ff90` bytes replace POPS's ROM copy at `0x24bc20`; `0x20079a=0x1000`; sets `gp+0x38a4` or `gp+0x3b98` (`2x`). **There is no integrity check on the user's file**: the "integrity check" message belongs to the OSD handler's gate `gp+0x3890` and is about POPS's own built-in BIOS | **PARTIAL** since `0945127` (was MISSING): `pops_user_bios_load` / `pops_user_bios_stage` with the size rule and a partial read, the two flags in `PopsUserRomState`, and the shell edits, region pass, `$UNDO_` and mode 6 following them; compared with the original under Unicorn by `tools/test_pops_user_bios.py` with `gp+0x3868 = 1` ([POPSTARTER_USER_BIOS.md](POPSTARTER_USER_BIOS.md)). Differences listed there (commands before files with a look-ahead, order at `0x2525b0` in 28 of 270 scenarios, no `gp+0x38dc`/`gp+0x3460`, debug-log messages, `.VCD` folder as the stand-in), plus one not named there: the handler's POPS folder exit (`0x880338..0x880380`; all games returns -666, the game scope goes on; gap audit section 4, S30) is not copied. No console run |
| MODULE_0..9.IRX resident modules | **PRESENT**: read from the folder POPS came from (the original: the device's `POPS` folder), 17-byte rule, the original's name table and core pokes, slot-order starts with its `hdd`/`pfs` arguments, `MODULE_5..9` after the `SB.` network stack, fatal start check. launcHER still starts POPS's sio2man itself in all cases. See [POPSTARTER_MODULE_IRX.md](POPSTARTER_MODULE_IRX.md). No console run |
| Physical PS1 disc. Not a mode anyone selects: it is what the original does when every VCD probe fails (`gp+0x3410`, set at `0x8756a4`, `0x875734`, `0x875d98`, `0x876690`). Block `0x8766fc..0x876a40`: cdvd modules, `sceCdInit(1)`, disc type must be `0x10..0x13`, region letters from LBA 4, `0x200794=0x0000202d` plus four changes in its own always-live block, `$MUTE_CDDA` writes for types `0x11`/`0x13`; `DISCS.TXT` skipped (`2x` for the block with its callees modelled; in-game reads are Sony's IOPCD, `1x`/`inferred`) | **MISSING**: `launchPOPS` returns `-ENOENT` at "Cannot open target VCD". Also needs a decision on how a physical launch is requested. Since `f22a69f` the host part exists (`common/src/pops_physical_disc.c`: the probe's decision, the four core writes, the name clear, the sector fingerprint; [POPSTARTER_PHYSICAL_DISC.md](POPSTARTER_PHYSICAL_DISC.md)) and is built into the launcher, but nothing in `launcher/` calls it. Not reviewed |
| Built-in per-game DB (LibCrypt list, breakpoint killer, compat modes, VMC1-off for some titles) | **PRESENT**: the original's list (607 fingerprints as hashes, 625 entries) generated from MAIN by `tools/gen_pops_builtin_db.py`; every entry's core/EE writes and flags equal the original's `FUN_008e00d0`, also when run after a `$FAKELC` (`tools/test_pops_builtin_db.py`); game-fix code, breakpoint handler and second LibCrypt code run from the resident chain in the original's order (on every launch since 2026-11-02; before that only when cheats, controller IDs or `$SET_TIMINGS` were also set). launcHER's own serial DB still runs beside it. See [POPSTARTER_BUILTIN_DB.md](POPSTARTER_BUILTIN_DB.md). No console run |
| padman_hsync | **PRESENT** with `$LOAD_PADMAN` / `$KILL_PADMAN` above; otherwise POPS starts it itself, as under POPStarter |
| Always-on launch changes: GP1 hook, nine misaligned-read guards, exit and byte-copy pokes, PS1 BIOS shell edits, the final scratchpad/BSS/heap clears | **PRESENT**, the recompiler hook at `0x2075e8` included since 2026-11-02 (the always-live block's pad hotkeys, disc swap and `$NOVMC0/1` stores are copied since 2026-11-02): launcHER changes the same 28 POPS words as the original's blocks run over the real core, and its own guard stubs pass the same model as the original's. Its exit program (`0x1450000`) is not copied on purpose. Quirks 41 to 44. See [POPSTARTER_LAUNCH_HOOKS.md](POPSTARTER_LAUNCH_HOOKS.md). No console run |
| XX. external USB pair (`mc?:/POPSTARTER/usbd.irx`, `usbhdfsd.irx`), started before and after the IOP reset | **PRESENT**: same paths, order, 12-byte rule and fatal start check; built-in stand-ins are launcHER's USB modules; EE-RAM handoff at `0x140000` not copied. See [POPSTARTER_XX_USB_DRIVERS.md](POPSTARTER_XX_USB_DRIVERS.md). No console run |

## Remaining work, in order

1. Hardware check of this change: a US disc and a European disc on an NTSC
   console, plus `$FORCEPAL` and `$NOPAL` (picture rate and colour).
2. Grow the resident code (cheats, manual/progressive display and pad
   commands, widescreen and `$SET_TIMINGS` exist, NOT TESTED on a console). PATCH video
   actions 6/7 dispatch exists since `a8da126` (stale note corrected 2026-11-02);
   text `$480p` works at the component/staging level. [Progressive contracts](POPS_PROGRESSIVE_CONTRACTS.md).
3. Every original command is now at least PARTIAL (the recompiler hook with
   `$RECOMPILER_ADDON_0..4`, `$FAKELC` and the `$NOVMC0/1` stores are copied
   since 2026-11-02). See [POPSTARTER_LAUNCH_HOOKS.md](POPSTARTER_LAUNCH_HOOKS.md).
   The six manual DISPLAY commands now have an independent resident bridge
   and 228 original file cases; see [manual contracts](POPS_MANUAL_DISPLAY_CONTRACTS.md).
   The six direct display commands now have a bounded original differential;
   see [display contracts](POPS_DISPLAY_CONTRACTS.md).
4. The gaps found on 2026-11-11, from the ranked list in
   [the gap audit](POPSTARTER_GAP_AUDIT_2026-11-11.md#16-ranked-increments),
   regrouped so the host-verifiable items come first (a to j can be
   verified on a host; k to m need a console):
   - (a) Fix files the original would skip must not end the launch; then
      TROJAN parity (the original's header rules, payloads outside the core,
      the call slots). The corpus result it rests on has been re-run (gap
      audit S27). In progress on a side branch.
   - (b) One path table measured from the original for every per-folder file,
      and a written decision of how each original folder maps to
      launcHER's, HDD included. No behaviour change.
   - (c) IGR skin staging. Landed in `173d5de` (PARTIAL, see its row).
   - (d) The six loader flags and what they gate (shell edits, region pass,
      `$UNDO_`, mode 6), then `BIOS.BIN` with a partial-file reader. Landed
      in `0945127` for `BIOS.BIN` (PARTIAL, see its row). Neither (c) nor
      (d) copies the loaders' POPS folder exit (gap audit S30, S31).
   - (e) Fix files before commands: measure both orders first, reorder only if
      results differ. Updates `tools/test_pops_launch_hooks.py` order test.
   - (f) `OSD.BIN`.
   - (g) `$USBDELAY` parser and default, the preset table, command
      recognition context, `VMCDIR.TXT` rules; decide which launcHER-only
      forms stay. Parser, recognition and `VMCDIR.TXT` landed in `95ba812`;
      the default, the preset table and the review answers are open (the
      answers in progress on a side branch).
   - (h) Launch-argument rules and resolver candidates (`IMAGE0.VCD`,
      `POPS0..9`, `__.POPS0..9`, name length), the `IOPRP.IMG` fallback,
      removing the test folder from the search list.
   - (i) SMB config parsers to the original's rules. Landed in `21c3476`
      for `SB.` launches of PS1 games only; not reviewed.
   - (j) Physical disc fallback: planner and core writes on a host; the drive
      part later and marked untested. Host part landed in `f22a69f`, not
      called by the launch; not reviewed.
   - (k) The `$USBDELAY` delay itself in popfs (host test with a fake delay;
      working only after a console or emulator run).
   - (l) HDD `__common` layout, `icon.sys`/`list.ico`.
   - (m) SMB external IRX set, `mass` rename, connect order. The default IGR
      (write nothing, as the original) is an owner decision.
