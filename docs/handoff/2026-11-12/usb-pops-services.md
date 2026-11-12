# USB POPS service repair — 2026-11-12

**Evidence level: host tests, container builds, and PCSX2 only. NOT TESTED on a
console. No run went into a game.** The independent reviewer returned `merge`
after the XX/BDMA ordering correction and the no-config release acceptance run.
Final full host sweeps are recorded below when they finish.

## Baseline and cause

The unmodified PR tree at `fb50a72a43d55e275f29c1b2c3497582170174f9`
(code-identical to `412c11b`) failed on the throwaway USB fixture with the EE
interpreter:

- `IOP: loaded ata_bd id=-200 start=0`
- `ERROR: Failed to initialize module ata_bd: -200`
- `POPS: Failed initializing services: -200`

Log: `runs/20261112T115022-baseline-fb50-usb-native/emulog.txt` in the private
harness. The generic module mask selects `ata_bd` for USB, but the Sony POPS
service load has no DEV9 for it.

The first `ata_bd`-only change reached POPFS and then failed its first disc open
with `-19` before USB mounting finished. The final change keeps the launch on
r13's default one-second delay for USB/SB when no `$USBDELAY_n` was taken. It
uses the existing post-driver sleep, not a new readiness probe.

## Final code

- `launcher/src/init.c`: skip `ata_bd` only for `sonySio2` + USB-only, with no
  ATA/APA bit. The pre-reset table, ATA/APA, XX/BDMA, Ember, and other non-Sony
  loads are unchanged.
- `launcher/src/handler_pops.c`: when `usb_delay_set` is false, set
  `cfg.usb_delay = 1` only for USB/SB. Explicit values, including zero, keep
  precedence. The assignment is after the XX pair, BDMA roles, and custom
  modules, so those backends exist before the existing storage probe.

There is no extra `fileXioOpen` readiness loop. The remaining `$USBDELAY`
difference is still the EE sleep, not r13's one-time IOP delay on the first
wrapped popfs open.

## Acceptance evidence

| Check | Result |
| --- | --- |
| Baseline trace, USB, EE interpreter | `ata_bd: -200`, as above |
| Final trace, USB, EE interpreter | PASS to POPS `Interlaced (FIELD)`, no service failure/trap (`20261112T131758-fixed-trace-default-delay`) |
| Final trace, ATA, EE interpreter | PASS to the same marker; `ata_bd` still loads (`20261112T131930-fixed-ata-default-delay`) |
| Final release, USB, EE+IOP interpreters, no config file | PASS to the same marker (`20261112T133913-fixed-default-iop-interpreter`) |
| Final release, USB, EE interpreter, empty `CHEATS.TXT` | PASS (`20261112T131206-fixed-default-empty-config`) |
| Final release, USB, EE interpreter, `$USBDELAY_1` | PASS (`20261112T130652-fixed-default-explicit-delay`) |
| Guard-only control with existing `$USBDELAY_1` | PASS (`20261112T125151-control-guard-delay`) |

The no-config release with EE interpretation and IOP recompilation stops after
SDR with `psxUNK` (`20261112T130337-fixed-release-default-delay` and
`20261112T130813-fixed-default-no-config-repeat`). Enabling the IOP interpreter
makes the same ELF pass. This is an emulator-backend-specific result, not proof
of a launch-code defect and not console evidence. The mechanism is not claimed
to be understood.

Final artifact identities:

- release `launcHER.elf`: 332,196 bytes, SHA-256
  `eabd72a33026640c6106c5fc562392bbc976362ad2f98eeac8ab998c347fadb7`
- trace `launcHER.elf`: 336,468 bytes, SHA-256
  `417a69be955087955afa7c20be68cc66328b52c9d8a78edea884ea998987a4f8`

Both container builds printed `handoff layout: OK` and the worktree
`version=unknown` warning. All disk and card images were throwaway. The private
emulator used program/support files only; BIOS ROMs were referenced without
copying their contents and NVM/MEC state was fresh. No real cards, saves, or
share were used.

## Host verification

- `tools/test_pops_external.py`: 130 tests, 14 optional skips, pass.
- `tools/test_pops_config_text.py`: 32 tests, 15 skips without references;
  32 tests, no skips with references.
- `tools/test_pops_doc_claims.py`: 19 tests, 11 skips without references;
  19 tests, no skips with references.
- Full sequential host sweeps: 35 of 35 files pass without reference inputs
  and 35 of 35 with `POPS_TEST_ELF`, `POPSTARTER_TEST_ELF` and
  `POPS_TROJAN_CORPUS`. `test_pops_user_bios.py` keeps its one expected
  failure (the `$UNDO_COMPATIBILITY_CODES` refusal).

## Open limits

- No real PS2 run, no game boot, and no claim that the build is safe.
- The IOP-recompiler `psxUNK` case is an emulator-specific open observation,
  not a console result.
- `$USBDELAY` still uses the existing EE sleep. Moving the one-time delay into
  popfs remains later work.
- The earlier readiness-loop and initial-delay experiments were removed and are
  not part of the final diff. Independent review checked the final code and
  returned `merge`.
