# POPS resident lifecycle evidence — 2026-10-30

Status: host-verified mechanisms and their evidence limits. No claim in this
document has passed a console run; Phase 6 hardware validation is a separate,
explicitly authorized gate.

## 1. The handoff fact

`launcher/src/pops_trampoline.S` zeroes scratchpad, Sony BSS, and all launcHER
EE RAM below `0x00200000`, copies the staged Sony core to `0x00200000`, flushes
caches (`FlushCache(0)`, `FlushCache(2)`), and enters Sony via
`ExecPS2(0x00200008, ...)`. Two corollaries govern every resident feature:

1. **Nothing launcHER-owned survives below `0x00200000`.** launcHER EE code and
   data are gone the moment Sony runs.
2. **Only two execution substrates survive:** byte patches already written into
   the staged Sony image (executed because they are Sony code paths now), and
   IOP-resident modules loaded before the foreign IOP reboot (`popfs`,
   `pops_iomanx`, Sony's own module set).

The IGR patch at `0x0020c0a4` (redirecting a call inside Sony's own pad-check
routine, guarded by the original opcode word) is the proven model for substrate
1. `popfs` devctl handling is the proven substrate for 2.

## 2. Disc swap — IOP-resident (new)

- **Mechanism:** `pops_pad_swap` (`launcher/iop/popfs/src/pops_pad_swap.c`), a
  debounced SELECT+L1+R1 detector (matching `POPS_SWAP_COMBO`), armed only when
  two or more disc images are configured at module start. On fire it runs the
  internal OPEN_LID -> NEXT_DISC -> CLOSE_LID sequence directly on popfs state,
  bracketed so a polling observer sees an eject/insert pair.
- **Caller:** the sio2man export-table interposition in `pops_pad_sio2.c`
  (vendored ioplib subset, mmceman precedent), fed by Sony's own padman
  transfers. popfs never owns the pad; it snoops replies.
- **Guards:** busy state (`active_disc_handles != 0`) returns `-EBUSY`; the
  detector requires a full combo release between fires; single-disc
  configurations disarm it; runtime state resets on module (re)start.
- **Host evidence:** `tools/test_popfs.py` — state machine debounce/refire/
  invalid-poll contracts plus the resident fire path on real popfs state
  (GET_DISC advances 0->1->0 through the fire callback).
- **Open gate:** reply-frame parsing (`0x5A` marker scan) and cohabitation with
  Sony `padman_hsync` need a console trace; popfs runtime-state reset on
  restart is host-verified only.

## 3. LibCrypt SubQ — iomanX interception bridge (new)

- **Mechanism:** `pops_subq_bridge` (`launcher/iop/pops_iomanx/src/`). While
  configured, `iomanX_devctl(name, cmd)` pairs matching the policy are answered
  from popfs's existing `POPS_DEVCTL_GET_SUBQ` Q generator, which carries the
  key the launcher forwarded with `POPS_DEVCTL_SET_LIBCRYPT`
  (`launcher/src/handler_pops.c`).
- **Lifetime:** pops_iomanx is the substituted iomanX on the Sony path, loaded
  before the reboot and resident thereafter; interception state is module
  state, unaffected by the trampoline.
- **Guards:** policy is prefix + exact command; recursion answers through the
  normal `pops:` device path; popfs failures (e.g. `-ERANGE`) propagate
  untouched; unconfigured bridge intercepts nothing.
- **Host evidence:** `tools/test_subq_bridge.py` — policy matching, popfs
  GET_SUBQ forwarding, and error propagation. IOP syntax check of the iomanX
  hook against ps2build headers.
- **Open gate (explicit):** the intercepted pair `devctl("cdrom0:", 0x05)` is a
  documented hypothesis — the evidence docs leave Sony IOPCD's actual
  subchannel request path unconfirmed ("Open evidence gates", launcHER
  POPSTARTER_REPLACEMENT.md line 468 row). A Phase 6 hardware trace must
  confirm or retarget the policy (`pops_subq_bridge_configure` is callable at
  runtime for that purpose). Protected-game behavior is NOT claimed.

## 4. Cheats — design spike conclusion

- **POPSTARTER parity scope:** POPSTARTER's cheat-class capability is the
  TROJAN/PATCH fix-file execution path, which launcHER implements
  (`pops_stage_fix_files` chain, guarded staging, slot precedence) and which is
  resident by construction: the staged payloads become part of the patched
  Sony image and execute as Sony code. Cache handling exists at staging
  (`handler_pops.c` FlushCache) and in the trampoline. Host suites
  `test_pops_fix_files.py` / `test_pops_external.py` / `test_pops_modes.py`
  pass.
- **Built-in CHEATS.TXT engine:** the interpreter (`pops_cheat_engine_tick`) is
  host-tested but has no resident caller, and per the audit's no-guessed-hooks
  rule it gets none this round. Spike finding from REPOP `POPS_HOT_PATH.md`
  (section 3.9/3.15): the PS1 guest RAM host base is a **runtime pointer**
  inside POPS's dispatch context (`*(base+0x2D0)`), not a fixed EE address, so a
  resident engine must resolve the base from POPS state after boot — i.e. it
  needs an evidenced postboot hook anchor (cf. the existing
  `pops_patch_exec_postboot_hooks` vocabulary in patch_engine) plus the
  dispatch-context address, neither of which is confirmed. Deferred until that
  evidence exists; tracked as an open item.

## 5. Synchronized claims

| Feature | Resident substrate | Host-verified | Console-verified |
|---|---|---|---|
| Disc swap | IOP (sio2 interposition) | yes (contract + fire path) | no |
| LibCrypt SubQ | IOP (iomanX bridge) | yes (policy + Q path) | no (request pair unconfirmed) |
| Fix-file patches | in-image | yes (staging suites) | partial (dependency/preflight gates on prior runs) |
| Built-in cheat engine | none yet (deferred) | interpreter only | no |

Every "working" claim for the first two rows stays banned until the Phase 6
gate: new dedicated test VMC, preserved saves, in-game observation, recorded
runs and hashes.
