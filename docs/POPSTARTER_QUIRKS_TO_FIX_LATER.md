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
| 20 | The list runs on every launch and cannot be switched off: the disc scan runs before the config files are read (no branch in the original's launch code leads from the parse back to the scan), so no command can stop it; a `$VCDID_n` with an unused id (625..9999) only selects nothing when the scan found nothing. (Corrected 2026-11-02: this said such a `$VCDID_n` made the original skip its scan.) A fingerprint match also silently disables `$VCDID_n`. | A `$NOVCDID` command, and let `$VCDID_n` override a match. |
| 21 | The 14 "breakpoint killer" entries scan up to 2 MB of PS1 RAM on every GP1 write the game makes, with the handler at `0x01460000` using POPS's `gp-0x7ff0` as scratch, exactly as the original's code does. The 134 game-fix entries run their code on every GP1 write too. | Move both to once per frame, or rewrite the handler to remember where it stopped. |
| 22 | Tokenizing differs in two small ways. `$VCDID_5<tab>` is accepted by launcHER (tokens split on any white space) but ignored by the original, which ends the digits only at a space, CR, LF or NUL. And the original starts a command at any `$`, so `x$VCDID_9999` is a command there; launcHER needs the `$` at the start of a white-space delimited token (this holds for every command, not only `$VCDID_n`). Not copied: both would need a parser change for one character. The same holds for every command: `$RESET_WARMBOOT$NOPAD0` is two commands there and none here, and a `#` line hides a command here but not there. `$FAKELC<tab>` is a command here but not there (the original ends that name only at a space, CR, LF, NUL or `$`). | Keep launcHER's. |
| 23 | With no fingerprint match, the original applies `$VCDID_n` at the point of the command, so commands before it in the files run first and commands after it run later. launcHER applies the entry before all commands; only matters when the same file both selects an entry and, before the `$VCDID_n` line, writes one of its sites (for example `$UNDO_LIBCRYPT_FIX` and then `$VCDID_n`: the original ends with the entry's LibCrypt bytes, launcHER with POPS's). `$FAKELC`'s order against `$VCDID_n` is followed since 2026-11-02 (quirk 61), so every order involving `$FAKELC` gives the original's bytes. | Record command order in the parser. |
| 24 | `$SUBCDSTATUS` makes every later `$COMPATIBILITY_0x01/02/03/05` in the files do nothing (the original's `FUN_008dc2c4` checks `gp+0x3458`); modes 4, 6 and 7 still apply. Now copied, per file order. Before this change launcHER applied them anyway. | Decide whether the skip is wanted; it looks accidental. |
| 25 | `$RESET_WARMBOOT`'s store of the reset vector is built into the slot (`0x232d08`) that a built-in entry's breakpoint handler call uses, and runs after the entry, so a game on the list with a breakpoint handler loses that handler once `$RESET_WARMBOOT` finds a SystemErrorExit stub. Copied: launcHER drops `POPS_RES_F_BREAK_CALL` in that case. | Run both: the two do not conflict in launcHER's chain. |
| 26 | `$RESET_WARMBOOT` means to make the in-game reset combo jump to the SystemErrorExit stub's PS1 ROM address (`0xbfc0d8d0` on this POPS): the code computes it (`p - 0x24bc20 + 0xbfc00000`) and then stores the other variable, `p`, the EE address of the stub inside POPS's ROM copy (`0x2594f0`). The PS1 then jumps to that address in its own space. Copied: `pops_apply_reset_warmboot` returns `p`. | Store the ROM address. |
| 27 | The in-game reset combo is port 0 reading exactly SELECT+L2+R2+CROSS (`0x507002 == 0xbcfe`), tested on every GP1 write; the resident block was always live in the original and was missing from launcHER until the `$RESET_WARMBOOT` work. Any other button held with the four cancels it. | Decide whether the combo should stay at all, and document it. |
| 28 | XX. USB drivers: a `usbd.irx` or `usbhdfsd.irx` under 12 bytes on `mc0:/POPSTARTER/` counts as absent and stops the search, so a real file on `mc1:` is never used. Copied (`pops_xx_usb_read`). | Fall through to mc1:. |
| 29 | XX. USB drivers: no check that `usbd.irx` and `usbhdfsd.irx` come as a pair. A missing file is replaced by the built-in driver, which may not link to the other, external one; the failed start is then fatal with no message about the missing file. This is the "refuses to start without usbhdfsd.irx" users report. Copied: launcHER uses its built-in `usbd_mini`/`usbmass_bd_mini` as the stand-ins and stops on a failed start. | Say which file is missing, or require both. |
| 30 | XX. USB drivers are started twice, from the same EE buffers, before and after the IOP reset; the card is read once. Copied. A driver that keeps state across the reset (BDM-UDPFS Assault's IOP RAM stash) depends on it. | Keep; document for driver authors. |
| 31 | `$LOAD_PADMAN` starts POPS's embedded padman_hsync with a length of `0xadf0` bytes, 11 bytes past the end of the ELF image (`0x2cd560..0x2d8345`). Copied; the bytes after it are POPS's own data and the loader ignores them. | Use the real length. |
| 32 | `$KILL_PADMAN` removes POPS's padman_hsync start and loads nothing in its place, so no pad driver runs unless one comes from elsewhere (a `MODULE_n.IRX`). The core pokes are unchecked in the original. Copied (the core is hash-pinned before them). | Warn when nothing replaces it. |
| 33 | `MODULE_n.IRX` name check: `IOX/File_Manager_Rpc` (fileXio) can never match, because the chain checks the prefix `IOX/File_Manager` (iomanX) first. Harmless only because neither flag is read again. Copied. | Check the longer name first, or compare whole names. |
| 34 | `MODULE_n.IRX` name check reads the name at file offset `0x8e` without checking the file is that long: a 17..162-byte file is compared against heap bytes past its `2 * size` buffer. launcHER zeroes a buffer large enough to cover the name instead, so the result is deterministic. | Require a real IRX header. |
| 35 | `MODULE_5..9.IRX` start after the `SB.` network stack, `MODULE_0..4` before it; without `SB.` all ten start together. Undocumented. Copied. | Document it for users who replace network drivers. |
| 36 | `MODULE_n.IRX` read: the read's result is not checked, and `hdd`/`pfs` arguments are chosen on three name bytes (`hddX` gets the HDD arguments). Copied. | Check the read; compare whole names. |
| 37 | The opcode pass reads 16-bit values blindly, with no instruction decoding: data that happens to look like an `lw`/`sw` upper half, or follow a `lui`-like value, is changed too. Its first range starts at an odd halfword (upper halves) but the other six start on word boundaries, so there it reads the lower halves of words. Copied exactly. | Decide per range what was meant; decode instructions. |
| 38 | `$BREAKPOINT0`'s handler turns itself off after one scan by storing over its own code (`sw zero, 0x14(k0)` on the gate's branch) with no cache write-back or instruction-cache flush, so the processor can keep running the old branch until that cache line is replaced: "once" may be "a few times". Copied. | Keep a flag in data instead of patching code, or flush the line. |
| 39 | `$BREAKPOINT0/1` silently replace a built-in entry's breakpoint handler (the list runs first and both use `0x01460000`), so on one of the 14 listed games the entry's own target is lost; `$BREAKPOINT0` also writes 12 bytes past the 292-byte handler (`0x01460124..0x0146012f`). Copied. | Warn, or run both handlers. |
| 40 | `$BREAKPOINT1`'s scan (up to 2 MB of PS1 RAM) runs on every GP1 write for as long as SELECT+L2+R2+CIRCLE is held on port 0; nothing documents the combo. Copied. | Document it; scan once per press. |
| 61 | `$FAKELC` sets a flag (`gp+0x3424`) that is never cleared while the files are read, and 216 entries test it: a `$VCDID_n` after a `$FAKELC` runs its entry with part of it skipped. 203 entries lose only their LibCrypt write, so `$FAKELC`'s bytes stay. 13 lose more: 207..216 also their game-fix code and breakpoint handler, 230 and 231 (no LibCrypt write at all) their game-fix code, 232 its game-fix code, its three sub-CD writes and the sub-CD flag. That looks accidental. A `$UNDO_LIBCRYPT_FIX` between the two puts POPS's bytes back but leaves the flag set, so the skip still happens. A fingerprint match runs before the files are read, so its entry is never cut. Copied (`POPS_BUILTIN_AFTER_FAKELC`). | Skip only the LibCrypt write. |

## Always-on launch changes (docs/POPSTARTER_LAUNCH_HOOKS.md)

| # | POPStarter behaviour (copied) | Possible fix later |
|---|---|---|
| 41 | The guard at `0x204ae0` turns the `lui $v0, 0x3c02` after the load (`0x204ae4`) into a `nop` and does it in its stub instead. But POPS's `0x204a88` also reaches `0x204ae4` from its handler path (`jalr` at `0x204abc`, then `b 0x204ae4` with `move $v1, $v0`), which now skips the `lui`: the check "is this PS1 word `lui $v0, 0x8001` (`0x3c028001`)" becomes "does it have bits `0x8001` set" for words that come from a handler. Copied. | Keep the `lui` at `0x204ae4` and branch the stub to it. |
| 42 | The guard at `0x202250` moves the store at the end of POPS's `0x2021a0` (its path for PS1 addresses above 2 MB, address formed at `0x202238..0x20224c`) to `0x00c70000` plus the address's low 16 bits. What that area is for was not worked out. Copied, with the original's leftovers: `$v0` holds the new address in all 128 bits and `$s0` holds `0x01440000`. | Find out what the redirect is for. |
| 43 | Register leftovers from the guards: `$v0` is `0xfffffffc` after `0x21c5dc`, `$s0` is `0xfffffffc` after `0x21c5a8`, and `$s0` is `0x01440000` after `0x202250`, though `$s0` is callee-saved. Harmless in this POPS: `$v0` is reloaded at `0x21c5e8`, `$s0` is restored at `0x21c678` before it is read, and the only caller of `0x2021a0` sets `$s0` again right after the call (`0x20231c`). Copied. | None needed while the core is pinned. |
| 44 | The byte copy POPStarter puts in front of POPS's `j 0x21b680` (`0x85a998` to `0x863990`, `0x20c0b0..0x20c0bc`) uses `$k0`/`$k1`, which the EE kernel's exception handlers may change at any time: an interrupt between a `lui` and the load or store that uses it would send that access to a wrong address. Rare, but it can crash. What the copy is for was not worked out. Copied. | Use registers POPS has free there, or run the copy with interrupts off. |

## In-game disc swap and DISCS.TXT (docs/POPSTARTER_LAUNCH_HOOKS.md)

Found by running the original's `DISCS.TXT` reader (`0x8d64b0..0x8d6b5c`)
and its always-live block (`0x232790..0x232c90`) under `tools/r5900_mini.py`
against launcHER's (`tools/test_pops_features.py`,
`tools/test_pops_resident.py`).

| # | POPStarter behaviour (copied) | Possible fix later |
|---|---|---|
| 45 | A `\`, `/` or `:` anywhere in a `DISCS.TXT` makes the original ignore the whole file with only a message ("An illegal character was found. Aborded."); the slots keep what they held, so a bad per-game file leaves the global file's discs in place. Copied. | Skip only the bad line, or say which file was ignored. |
| 46 | `DISCS.TXT` lines are not trimmed and there are no comments: a line of spaces or `# note` is a disc name. A line of 90 characters or more clears all four slots, the global file's too, and stops reading ("VCD %d filename exceeds 89 characters. Aborded."). Copied. | Trim, allow comments, skip only the long line. |
| 47 | The game's `DISCS.TXT` writes over the global one's slots from the first, and each line writes only `pfs0:/`, the name and one NUL. A global file with more lines than the game's leaves its later discs in the game's slots, and a shorter name leaves the end of the old one after its NUL (POPS sends those bytes to the IOP; the name ends at the NUL). Copied. | Clear the slots before each file. |
| 48 | Every pass, a slot whose first word is 0 (no `DISCS.TXT` line wrote it) gets POPS's boot path, so with fewer than four discs listed the unused directions reload the disc the game started with. Copied. | Ignore a close on an empty slot. |
| 49 | The original keeps the selected slot as the immediate of its own `ori` at `0x2328bc` and writes the `$SCANLINES` word into POPS's code, both with no cache flush: the processor can keep running the old instruction from its instruction cache, so a selection or a scanlines change may take effect late. launcHER copies the `$SCANLINES` store as it is but keeps the selection in data, so its selection takes effect at once (a stale cache line cannot be copied into data). | Flush the line after the `$SCANLINES` store. |
| 50 | The swap calls POPS's disc init (`0x210540`) from the GP1 hook with interrupts disabled, on the POPS thread's stack. Each call creates two semaphores and a thread and binds the CD RPC again, and nothing frees the previous ones, so every swap leaks them. POPS sends `0x80` bytes from the slot to the IOP by DMA, so the last slot's send reads `0x20` bytes past the slots (the original's own code; launcHER's 32 zero bytes, `disc_tail`). Copied, with two differences: the original leaves the caller-saved registers as the disc init left them, in a POPS routine that did not expect a call there, while launcHER's GP1 entry keeps them all; and launcHER's stack is `0x110` bytes deeper at the call. | Initialise once and only send the new name. |
| 51 | Where the name opens: POPStarter's PFS wrapper opens `pfs0:/<name>` as `mass:/POPS/<name>` on USB and SMB; launcHER's popfs opens it in the folder of the game it launched, which is the same folder for the usual `mass:/POPS/` layout. Through it `IMAGE.VCD` (the launched disc), `SLOT0.VMC`, `SLOT1.VMC` (and `.bak`), `ps1emu` and `disc/discN` keep launcHER's own meaning, so a `DISCS.TXT` line that is exactly one of those names does not open a file of that name. Not a POPStarter behaviour: a difference to keep in mind. | Give launcHER's probe and save names their own device so every name can be a file. |

## Recompiler hook and `$RECOMPILER_ADDON_0..4` (docs/POPSTARTER_LAUNCH_HOOKS.md)

Found by running the original's block and emit code, installed by its own
launch and command code, under `tools/r5900_mini.py` against a model
(`tools/pops_recompiler_model.py`) that launcHER's code passes too
(`tools/test_pops_launch_hooks.py`). Quirks 54, 56, 57, 58 and 59 also have
checks of their own, run on both.

| # | POPStarter behaviour (copied) | Possible fix later |
|---|---|---|
| 52 | `$RECOMPILER_ADDON_0`, and the conversion `_3` and `_4` make, go by value, not by instruction: every word in `0x8bff0001..0x8fffffff` or `0xabff0001..0xafffffff` gets `0x0c000000` added. That turns `lw` into `lwr` and `sw` into `swr`, as meant, but also `lwl $ra, n($ra)` (n from 1) into `lhu $ra, n($ra)` and `swl $ra, n($ra)` into `sdr $ra, n($ra)`, and changes any data word in those ranges. Copied. | Decode the word; change only `lw` and `sw`. |
| 53 | `_0` goes over the `0x800` bytes (512 words) before POPS's emit pointer at the end of every block, whatever the block's size. Earlier blocks are gone over again (a changed word is outside the ranges, so nothing changes twice), near the start of POPS's code buffer it reaches the words in front of it (what lies there was not worked out), and it costs 512 loads on every block. Copied. | Go over the new block only. |
| 54 | While the word at PS1 `0xb890` is nonzero, `_0` runs only after `_2`, so without `$RECOMPILER_ADDON_2` it is skipped. Only `_1` and `_2` clear that word, so `$RECOMPILER_ADDON_0` alone does nothing for as long as the word stays nonzero. POPS's PS1 BIOS writes that word (ROM `0xbfc03bc8`, `0xbfc03c40`, `0xbfc06c2c`, `0xbfc06e4c`); when, and with what, was not worked out. Copied. | Run `_0` on every pass. |
| 55 | `_1` goes by a pattern: a `break 7` or `break 6` word becomes 0 when the top byte of the word two before it is nonzero (as the branch of a compiler's divide check is), so a data word that matches is zeroed too, and a check laid out another way keeps its `break`. Copied. | Decode the divide check. |
| 56 | `_1` and `_2` stop only on the exact end address. `_1` does not test it for the word after a `break 7` it zeroed, so a zeroed `break 7` on the last word, or a length that is not a multiple of 4, makes it run on past the end through the rest of memory, zeroing matching words as it goes. `_2` tests only after moving on, so a length of 0, or one that is not a multiple of 4, does the same. Both also change the PS1 kernel's words: the top byte of `0xb878` and the word at `0xb890` become 0. Copied. | Stop at or past the end. |
| 57 | `_2`'s check for `li $t2, 0xb0` / `li $t1, 0x52` / `jr $t2` loads the third word into `$v1` and compares the first word, so that form is never patched (the other seven forms are). Copied. | Compare the second word. |
| 58 | Every `li $t2, 0xb0` that `_2` meets, except the patched `jr $t2` / `li $t1, 0x38`, `0x52` or `0x5a` and `li $t1, 0x38` / `jr $t2` forms, leaves `$v1` holding the third word after it, sign-extended. After the hook POPS stores `$v1` as the last instruction of the block it has just finished, in place of `addiu $k1, $k1, -n` (the block's cycle count). So on the pass where `_2` scans newly loaded code that holds such a call (any other B0 call, such as `jr $t2` / `li $t1, 0x3d`), that block ends with the last one's third word instead: usually `li $t1, n`, or `jr $t2` after a `li $t1`-first B0:52 or B0:5A. What that does in a game was not worked out. Copied. | Keep `$v1`. |
| 59 | The `0x206318` code loads `$gp` from the slot where the `0x205d1c` code keeps the `$gp` it found (the original saves its own `$gp` elsewhere and never reads it back). So after `0x206318` POPS's `$gp` is what `0x205d1c` last saw, or 0 if `0x205d1c` has not run yet. Whether `0x206318` ever runs first in a game was not worked out. Copied. | Give `0x206318` back its own `$gp`. |
| 60 | The emit code borrows `$k0`, `$k1` and `$at`, saving and restoring them, in code that runs with interrupts enabled; the EE kernel's exception handlers may change `$k0` and `$k1` at any time (as in quirk 44). It leaves `$ra` = `0x01440000` and the converted word in `$v0` (`0x206318`) or `$a0` (`0x205d1c`); POPS sets both again before reading them. Copied. | Use registers POPS has free there. |
