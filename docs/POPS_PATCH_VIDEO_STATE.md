# Ordered PATCH video and final region pass — 2026-10-30

The four PAL sites are now part of the fix-file session's expected state.
Initialization requires the identified core's pristine bytes, including after
text configuration, because `$FORCEPAL` is deferred until the final pass.
Every fix file verifies the expected sites before payload or mode writes,
then records the result of intentional payload/settings writes. Unexpected
drift is rejected without modifying the core or context. The final video
pass uses the same tracked expectations; an intentional payload is not
mistaken for an unrelated core version or untracked corruption.

## Original state and ordering

Original PATCH dispatch is `FUN_00881de8`; its PAL helper is `FUN_008dc218`.
The final region window is `0x879034..0x8795f0` (end exclusive), with forced
PAL gated by `gp+0x38a0 == 1` and `gp+0x3864 == 0` at its first branches.
European automatic PAL uses `gp+0x4fa0 == 1` at `0x87930c`.

| Input | Original behavior retained |
|---|---|
| `$FORCEPAL` | Records intent; final PAL runs only if PATCH has not disabled it. When that branch runs POPS reports Europe, while the BIOS retains the disc region |
| PATCH PAL (2/3) | Applies PAL if not already disabled, clears the auto selector and sets disable/manual/forced state; suppresses the later FORCEPAL branch |
| PATCH disable-auto (4/5) | Clears the auto selector and sets disable state, suppressing both final automatic PAL and FORCEPAL |
| `$NOPAL` | Clears automatic selection, but does not suppress an explicit PATCH PAL action |
| `$480p` | Its original disable-PAL state is preserved; the progressive implementation is still blocked |
| PATCH 6/7 | Reject before any payload/mode/context write: the required `0x2394f0` resident target is still absent |

Previously launcHER applied FORCEPAL before fix files and always reported
Europe afterward. A subsequent PATCH disable-auto could not suppress those
writes. Now production runs text/core patches, ordered fix files, guarded final
video, then region letters. The final video pass can still honor FORCEPAL if
the licence read failed, while the launcher skips region/BIOS letter writes in
that case. Explicit PATCH PAL on a US/Japanese disc does not change its region
letters unless the original final FORCEPAL branch actually runs.

The concurrent resident implementation at `8f40793` lives at `0x0143a000`
and implements cheats; it does not supply the progressive-video target
`0x2394f0`. Actions 6/7 remain gated after integrating that commit.

## Reproduction and evidence limits

```sh
python3 tools/test_pops_fix_files.py
POPS_TEST_ELF=/external/POPS.ELF \
POPSTARTER_TEST_ELF=/external/MAIN/POPSTARTER.ELF \
python3 tools/test_pops_external.py
```

The full input hashes and the bounded integer interpreter are documented in
[display contracts](POPS_DISPLAY_CONTRACTS.md). Its additional `region()`
fixture executes original region branch/delay-slot instructions, with the PAL
helper and poke services explicitly modeled. User-BIOS/OSD/preserve-standard
flags are zero; those replacement features are not implemented in launcHER.
This verifies region control flow under those stated inputs, not the complete
original PATCH loader, helper implementation, hardware or GS behavior.

Local results after integration with `8f40793`:

- All 26 fix-file tests pass with both external inputs.
- The final video/region output matches original region control flow for
  **60 combinations**: four text modes, three PATCH actions and five licence
  tags. The complete core is compared for each combination.
- The aggregate external test entry point passes **104 tests** with external
  inputs, including the separate 1,596 direct-display-command comparisons and
  two original one-shot states. Default CI explicitly skips external cases.
- All 18 host entry points, including argv and resident tests, pass. Normal
  and diagnostic PS2 builds pass; the built resident image passes its manual
  Unicorn entry/chaining check. No new console run occurred.

Region/video picture checks and resident cheat acceptance remain physical
gates. Save durability requires a fresh dedicated VMC with in-game save,
reload, cold power cycle and integrity evidence. Existing saves and external
Sony/game files must remain preserved.
