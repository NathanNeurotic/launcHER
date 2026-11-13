# POPStarter r13 `OSD.BIN`: design and evidence

Status on 2026-11-12: **implemented at host/Unicorn level; final full
verification and independent review are pending.** Work is isolated on
`pr23/osd-bin`, based on merge `308684c`. The reference is clean REPOP
`bc258e48` plus the original MAIN executed under Unicorn, not REPOP's prose
alone. Nothing is tested on a console.

## Intent and scope

Provide drop-in `OSD.BIN` behavior for POPStarter launches, bugs included,
without changing Ember. Implement a bounded `pops_osd_stage` and thin file
loading before each folder's BIOS/TROJAN/PATCH files. Use the same VCD and
per-title folders as the existing BIOS loader until the measured path-table
piece; do not start that piece here.

Implement distinct reason codes for every rejection, in the original's
order: PS-X EXE/foreign file, unsupported version, invalid header data,
invalid v1 load address, invalid v1 entrypoint, size mismatch, body too big,
missing build id and missing label. Bad API arguments are separate negative
errors, not POPStarter rejection reasons. A rejected file leaves the core
and loader state unchanged; a missing file is not an error.

## Selected approach and alternatives

**Selected: validated plan/stage plus launch wiring.** A pure validation
step gives the reader the body destination, size and exact read request. A
bounded stage then performs the core writes and state changes. This keeps
file I/O out of the common code and allows whole-core differential tests.

- Pure stage only was rejected: it would leave no user-visible drop-in path.
- A direct REPOP port was rejected: live absolute pointers and POPStarter's
  own I/O helpers do not fit launcHER's staged-core or safety model.
- A production file/command reorder is not part of this piece. Quirk 80
  remains. Any additional measured OSD ordering effect will be reported and
  indexed rather than hidden by a parity claim.

## Behavior to preserve

- Read 80 header bytes into a zeroed buffer before validation. Preserve the
  minimum size, 24-bit body size and exact size/cap precedence.
- v1 and v2 destinations and capacities, including one-byte-over rejection;
  v1's four header bytes at `0x252c30/31` and `0x252c40/41`; v2's mixed
  byte, halfword and word writes through `0x252c4b`, including its `jal` in
  a delay slot. Do not “repair” that instruction pattern. The three v2
  values at `0x252c34`, `0x252c38` and `0x252c48` are immediate instruction
  words written by `FUN_008d6c04`, not live IOP reads: `0x0ff00648`,
  `0x0ff00ad4`, and `0x01c0f809` (`0x01c00008` when the v2 flag is 1).
- Mixed all-games/game loads, including v2-then-v1 residue. The game pass
  does not test the all-games OSD flags.
- If OSD was off, enable it and clear `osd_off` before applying the header's
  four compatibility modes in order. Mode 6 can disable it again. Modes
  1/2/3/5 honor the built-in no-fix flag; unsupported mode numbers do
  nothing. The built-in plan, not later text commands, supplies that flag.
- The two per-scope success flags and `0x20079a = 0x1000`, with later shell,
  region, BIOS and undo gates continuing to use the same state.
- One unchecked body read after seeking to offset 64. For an unaligned body
  within the original boundary, request `body_size + 16`, then clear from
  `body_size` to the cap. Short/failed reads retain the original's accepted
  result and zero-filled remainder; do not turn them into a new fatal error.
- Rejection closes the file and writes no core or success flags. Existing
  debug-log versus on-screen message differences remain documented, not
  silently called identical.

Before production code, run the original handler under Unicorn with
modelled services for uncertain gates, invalid mode numbers, short headers,
read results, and return/state effects. Record any behavior that cannot be
copied safely as a numbered quirk with its RAM-visible substitute.

## Launch and guard integration

Read each scope's OSD before its BIOS and fix files. Reuse the BIOS
look-ahead pattern so the existing grouped command pass sees the loader
state it would have after the original's loads. Keep predicted BIOS state
separate from actual loads and retain the existing changed-file `-EIO`
safeguard, documenting that launcHER-only window.

The fix-file context must accept intentional OSD compatibility writes and
the OSD halfword change without accepting arbitrary live bytes. Refresh
that context from the validated staged operation, then continue with BIOS,
TROJAN and PATCH guards. Preserve the pre-load versus command-look-ahead
distinction used by the `$UNDO_` fix.

Add loader-state fields needed for integrity, no-fix and OSD entry gates.
The already validated POPS core supplies the RAM-visible successful
integrity result. Existing POPS-folder abort/folder-inspection differences
remain explicitly outside this piece and must not be described as copied.

## Verification

Test-first, with failures watched before implementation:

1. Native validation and staging: every rejection reason and precedence,
   both versions, minimum and cap boundaries, header/body short reads, OSD
   state, compatibility modes and no-fix behavior, and mixed-scope residue.
2. Whole-core differential against the original handler under Unicorn with
   both backends and modelled file services. Compare state and I/O request
   logs as well as all staged bytes; never emit proprietary contents.
3. Directed unaligned body cases at and around the extra-read boundary and
   three negative controls: EXE-versus-OSD recognition, rejection
   precedence, and failed/short header/body reads with no accidental fatal
   path or out-of-bounds write.
4. Launch-helper tests for path/open order, look-ahead consistency,
   changed-file detection, later BIOS/fix guards, and no Ember changes.
5. Seeded differential cases, both full host sweeps with and without
   reference inputs, and release/trace container builds requiring
   `handoff layout: OK`. Obtain independent review before one `--no-ff`
   merge. Mark every result host, Unicorn, build, PCSX2 or console
   separately. No console or game-boot claim without that run.

## Non-goals and open work

No production file/command reorder, path-table implementation, HDD
`__common` decision, improvement of copied bugs, physical-console claim, or
REPOP changes. `OSD.BIN` runtime behavior inside a real PS1 BIOS shell is
not established by host staging equality.
