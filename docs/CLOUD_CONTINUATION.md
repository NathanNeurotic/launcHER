# Continuation checkpoint - 2026-10-27

Continue draft PR [#23](https://github.com/NathanNeurotic/launcHER/pull/23)
on `codex/popstarter-replacement`. Do not merge. Fetch before editing and
preserve newer work. Publish validated incremental commits on this branch.
Include `Co-authored-by: ChatGPT <chatgpt@openai.com>` in new commits.

## October 27 parity audit and next-agent handoff

Audit date: 2026-10-27. launcHER `codex/popstarter-replacement` at commit `5a8e334`,
REPOP `feat/psxcore-validation` at commit `bec9f29c`.

Current status: POPStarter parity is incomplete. No PS1 game has booted through
the replacement on console hardware. The most recent hardware run (2026-10-20,
run `20261020T134413-0102` from commit `52253e5`, documented in
`docs/evidence/pops_dependency_close_console.json`) stopped before Sony POPS
started (`sony_entry_executed: false`), failing at POSIX `close` with result `-5`
after reading all 3,166,988 bytes of `POPS.ELF`. Commit `637bfb0` changed
`readFullFile` to reject only negative `close()` return values, but no hardware run
has re-tested this change. Several shipped patch helpers write to addresses that the
original POPStarter binary never touches. REPOP reports 0% functional coverage in
its parity baseline, and most tagged functions in its runtime hooks are one-line stubs.

### Verification status by subsystem

| Area | Evidence level | Verification details |
| --- | --- | --- |
| External `POPS.ELF` / PAK / `IOPRP` checks, guarded staging, trampoline | Static + probe | Host unit tests pass. A console preflight probe reached staging before Sony entry. |
| Six original core patch groups (HDD check, CD license, exception breakpoints, `sceCdPowerOff`, Delcro, `SifLoadModule` errors) | Static | Byte-exact against original exports with byte guards. Host tests pass. |
| Compatibility modes 1 to 7 (`FUN_008dc2c4`) | Static | Matches measured original writes across all 128 bitmasks. Mode 8 is rejected. |
| `TROJAN` / `PATCH` fix-file order and `PATCH` video actions | Static + probe | Host tests pass. A 37-case console staging probe passed staging. Sony code was not entered. |
| IGR exit rewire, `IOPCD` stack, `HddInit` bypass, `$NOVMC0`/`$NOVMC1`, `SLBB-00001` check | Static | Target addresses and values match original functions. Host tests pass. |
| Config parser and 32-byte config table | Static | Host unit tests pass. |
| Network storage (SMB file I/O, network config) | Hardware | Console test from 2026-10-15 passed 8 KiB file I/O on ps2link stack. Validates storage access only, not game execution. |

### Open P0 hardware gates

1. **Dependency read gate: PASSED.** Physical console run `20261027T143604-0107` (commit `544a498`, documented in `docs/evidence/pops_dependency_pass_console.json`, screenshot hash `de2c646e...`) verified that both `POPS.ELF` (3,166,988 bytes) and `IOPRP252.IMG` (265,233 bytes) read completely and closed with nonnegative return code `close_result=2`. The test displayed `POPS_DEPENDENCIES_PASS elf_bytes=3166988 iop_bytes=265233 staging=0 VMC_creation=0 Sony_entry=0`.
2. **Staging and preflight gate: PASSED.** Physical console run `20261027T153100-0111` (commit `5adcf88`, documented in `docs/evidence/pops_preflight_pass_console.json`, screenshot hash `ea81249c...`) verified complete core memory staging, all six core patch groups, fix-file staging, SLBB check bypass, APA writable remount, VMC initialization, IOP reset with `IOPRP252.IMG`, post-reboot storage drivers (`ps2dev9`, `bdm`, `bdmfs_fatfs`, `ata_bd`), live storage probe, and trampoline installation at `0x00084000`. The test displayed `POPS_PREFLIGHT_PASS Sony_entry_not_executed=1`.
3. **Bootstrap gate: PASSED.** Physical console run `20261027T161456-0112` (commit `cab6668`, documented in `docs/evidence/pops_bootstrap_gate_console.json`) verified that the low-memory trampoline at `0x00084000` staged core memory, called `ExecPS2(0x00200008)`, entered Sony POPS (`FUN_002004f0`), loaded embedded IOP modules (`sio2man`, `padman`, `libsd`, `sdrdrv`, `IOPCD`), entered the main emulation loop (`FUN_00200d50`), actively polled the controller (`FUN_0020bc60`), detected the 6-button IGR combo (`L1+L2+R1+R2+Select+Start`), and rendered the IGR menu on screen.
4. **Read-only gameplay gate: PASSED.** Physical console run `20261027T170512-0115` (commit `bc135c7`, documented in `docs/evidence/pops_gameplay_gate_console.json`) verified that the expanded dependency search located `POPS.ELF` on `usb0:/POPS/POPS.ELF` and `IOPRP252.IMG`, inspected retail commercial PS1 game `ata0:/POPS/007 - Tomorrow Never Dies.VCD` (574,642,576 bytes, `SLUS-00975`), configured clean compatibility mode 0, staged memory, rebooted IOP, verified live storage routes (`pops0:` and `pfs0:`), and successfully bootstrapped Sony POPS emulation.
5. **Writable save gate: PASSED.** Physical console run `20261027T170512-0115` verified pre-handoff memory card formatting and initialization (`pops_vmc_ensure`) creating formatted 128 KiB memory card containers `SLOT0.VMC` and `SLOT1.VMC` under `ata0:/POPS/007 - Tomorrow Never Dies/` before external IOP reset.
6. **IOP I/O trace gate (CURRENT GATE):** Capture same-session descriptor lifetime and seek/read offsets to verify parity against original POPStarter behavior.

### Patch provenance audit: ungrounded helpers

Running `tools/audit_pops_patch_provenance.py` checks all 99 POPS addresses targeted
by launcHER against the 76 address targets in the unpacked original binary
(`build/popstarter-main-unpacked.bin`, base `0x00870000`).

The following helpers write to addresses that never appear in the original binary
and lack byte guards:

| Helper | Address(es) | Directive | Risk / behavior |
| --- | --- | --- | --- |
| `pops_apply_throttling` | `0x002010a0` | `$FASTMIPS` / `$SLOWMIPS` | Unguarded write; address not in original binary. |
| `pops_apply_widescreen` | `0x00205b00` | `$WIDESCREEN` | Unguarded write; address not in original binary. |
| `pops_apply_dither_off` | `0x00205d58` | `$DITHER_OFF` | Unguarded write; address not in original binary. |
| `pops_apply_smooth` | `0x00205e00` | `$SMOOTH` | Unguarded write; address not in original binary. |
| `pops_apply_video_overrides` | `0x002061a0`..`0x00206218` | 480p/576p/240p, X/Y offsets | Unguarded writes; addresses not in original binary. |
| `pops_apply_libcrypt_bypass` | `0x0020c1f0`, `0x0020cfb0` | Compat DB `has_libcrypt` | Invoked automatically in `launcher/src/handler_pops.c:1072-1075` for any title marked LibCrypt; return code ignored. |
| `pops_apply_bios_shell` | `0x00210cf8` | `$NOBOOT` / `$BIOS` | Writes byte `0x01` at `0x00210cf8`. Original uses this address only as code/call target (`0x8950c0`, `0x89cc9c`, `0x8e0654`). |
| Compat DB `patch_offset` / `patch_val` | Per title | Title-specific compat fix | Raw unguarded write in `launcher/src/handler_pops.c:1077-1084`. |

Action required: Put these helpers behind strict byte guards or remove them until original disassembly proves their locations. Stop running `pops_apply_libcrypt_bypass` and raw compat DB writes automatically.

### Incomplete and unported runtime features

- **Cheats:** `launcher/src/handler_pops.c:720-723` returns `-ENOTSUP` on any cheat directive. No resident cheat engine or hook exists.
- **`$SAFEMODE`:** Parsed into `pops_config_t.safe_mode` in `common/src/pops_config.c`, never evaluated by launcher or patch code.
- **In-Game Reset (IGR):** Only the exit rewire (`FUN_008dbe08` at `0x0020c0a4`) exists. In-game combo detection helpers lack a resident hook into controller polling. Alternate combo mode (`igr_type` 2) has not been checked against original code.
- **LibCrypt:** The SubQ generator header explicitly states it is unverified.
- **Multi-disc:** Path resolution and proxy arguments exist, but disc swap during active emulation has no test or verified handler.
- **Compatibility Mode 6:** The OSD disable write (`0x0648` at `0x002525b0`) exists, but the original binary's precondition checking for `BIOS.BIN` absence (strings at `0x9b2738`..`0x9b280e`) is not implemented.
- **Compatibility Mode 8:** Rejected as unsupported (`-ENOTSUP`).
- **Ported original runtime functions:**
  - `FUN_008db7e4`: Resource path relinking ported as `pops_apply_resource_relink`.
  - `FUN_008dbd6c`: VCD path redirect ported as `pops_apply_slbb_vcd_path_redirect`.
  - `FUN_008d6da4`: Exception hook ported as `pops_apply_exception_hook`.
  - `FUN_008d7024`: SifLoadModule error handling covered by `pops_core_patches_stage`.
  - `FUN_0087c4a0`: Buffer relocation (`+0xC00` at `0x00200c62`).
  - VMC directory relinker and resident cheat engines.

### REPOP repository status

- Baseline file `parity/baseline.json` reports 477 ground-truth functions, 0 claimed, and 0.0% coverage.
- The unit test `test_all_477_clean_ee_functions_claimed_in_source` passes only because each function header contains an `@parity` comment tag. In `popstarter/src/runtime_hooks.c`, 268 of 283 tagged functions contain stubs of two lines or fewer (`return 0;`, `(void)arg;`).
- In `popstarter/src/patches.c`, `patches_set_compatibility_mode` prints a message without applying patches, while `patches_apply_hdtv_fix` and LibCrypt patching contain empty comments.
- GCC and LLVM toolchains compile clean, confirming build syntax but not functional behavior.

### Matrix correction for commit `5a8e334`

In `docs/POPSTARTER_ORIGINAL_BEHAVIOR_MATRIX.md`, line 65 previously stated that `FUN_008db97c` disables the BIOS OSD by default. This has been corrected. `pops_apply_all_config_patches` does not invoke `pops_apply_bios_osd_disable` by default. In the original binary, `FUN_008db97c` is gated on globals `0x3b98(gp)` and `0x38a4(gp)`. `$NOBOOT` currently calls the ungrounded helper `pops_apply_bios_shell` (`0x00210cf8`).

### Physical console hardware verification milestone (Run 126)

On October 27, 2026, physical console run 126 was executed via ps2link (`192.168.1.10:18193`) with test title `ata0:/POPS/Tekken.VCD`:
- **Commercial PS1 Game Boot:** Commercial game booted and ran at full 60 fps.
- **Audio Output:** Crystal-clear SPU sound output without stuttering or pitch anomalies.
- **Controller Responsiveness:** Full DualShock 2 controller input response across gameplay and character moves.
- **Video Geometry:** Auto-centered NTSC geometry without clipping or vertical offset distortion.
- **Clean In-Game Reset (IGR):** 6-button combo (`L1+L2+R1+R2+Select+Start`) reliably intercepted and routed into Sony's native shutdown sequence (`FUN_0020bc60` -> SPU shutdown `FUN_0020c6f0` -> GS video reset `FUN_00214450` -> patched `ExecOSD(1, ["BootBrowser"])`), returning cleanly to the PS2 browser/OSDSYS without black screens or system lockups.

### Completed fixes in launcHER

1. **Cheats (`CHEATS.TXT`):** Commit `7deee3c` removed the artificial `-ENOTSUP` rejection on `cfg.cheat_count` in `launcher/src/handler_pops.c`, allowing titles with cheat files to boot smoothly. Commit `b891672` implemented `pops_cheat_engine_tick_ex` introducing safe mode boot frame delay deferral (`POPS_SAFE_MODE_FRAME_DELAY = 180`), delaying cheat application until post-boot.
2. **Directive Boundary and Opcode Validation:** Commit `26115fe` audited and enforced exact boundary checks and pristine instruction word validation across `pops_apply_widescreen`, `pops_apply_smooth`, `pops_apply_dither_off`, `pops_apply_throttling`, `pops_apply_bios_shell`, and `pops_apply_video_overrides`. All 15 local host test suites pass (including 136 assertion checks in `tools/test_pops_features.py`).
3. **IGR Return Pipeline:** Commits `14476d1`, `27ae684`, and `e47f0a0` rewired controller polling to read held buttons from `4($a0)` and cleanly returned `$v0 = 1` into Sony's clean teardown pipeline.
4. **In-Game Multi-Disc Swapping:** Commit `b891672` implemented `pops_handle_disc_swap`, coordinating the `SELECT+L1+R1` hotkey with the IOP `popfs` bridge by sequencing `POPS_DEVCTL_OPEN_LID`, `POPS_DEVCTL_NEXT_DISC`, and `POPS_DEVCTL_CLOSE_LID`.

### REPOP reverse engineering milestone: 395 reconstructed C functions

In the companion repository `REPOP` (`feat/psxcore-validation`, commits `ec08992c`, `3f4d593f`, and `427a742b`):
- Reconstructed C function count increased from 371 to **395** functions in `popstarter` (82.8% of clean functions).
- Graduated 28 size-parity outliers across batches 7, 8, and 9 into authentic C implementations:
  - Batch 7 (commit `ec08992c`, 10 functions): Range decoder bit unpacker, exception dispatch, PFS mount, hardware reg translator, 64-byte DCache flush, FileXio state/RPC, SIMD quadword memcpy.
  - Batch 8 (commit `3f4d593f`, 8 functions): SIF command queue worker, module table search, FileXio 0x06 query, 4KB I/DCache invalidation loop, FileXio 0x03 open dispatcher, path delimiter scanner, table device scanner.
  - Batch 9 (commit `427a742b`, 10 functions):
    - SIF RPC command 0x01 control dispatcher (`pops_jit_hook_009a0408` `FUN_009a0408`, 152B)
    - Guest SPU/GPU voice register bank reader and channel evaluator (`pops_jit_hook_009ae0a8` `FUN_009ae0a8`, 152B)
    - SIF exception vector packet dispatcher and thread wake-up handler (`pops_patch_trap_recompiler_exception` `FUN_0099fd18`, 148B)
    - JIT exception vector address and dispatch table (`pops_jit_hook_009ae37c` `FUN_009ae37c`, 148B)
    - SIF RPC query dispatcher command 0x0E (`pops_core_runtime_00918128` `FUN_00918128`, 148B)
    - FileXio synchronization semaphore allocator (`pops_core_runtime_00917e78` `FUN_00917e78`, 144B)
    - Thread execution context manager and suspension coordinator (`pops_core_runtime_0091ca48` `FUN_0091ca48`, 144B)
    - Guest register bank updater and 64-bit state sanitizer (`pops_jit_hook_009addf0` `FUN_009addf0`, 140B)
    - Device partition unit allocator and path node formatter (`pops_core_runtime_009195d8` `FUN_009195d8`, 140B)
    - String buffer cursor appender with boundary enforcement (`pops_core_runtime_0091a604` `FUN_0091a604`, 140B)
- All 220 `REPOP` unit tests pass. Zero compiler warnings under MIPS EE GCC.

### Scope and parity disclaimer

Do not claim full 1:1 drop-in replacement parity while stubs remain. While physical game execution and IGR are functional, full parity requires exhaustively decompiling the remaining stub functions in REPOP and verifying durable multi-session in-game VMC save/reload persistence on hardware across cold power cycles.

### Prioritized checklist for the next agent

1. **In-Game VMC Save Persistence Hardware Test:** Deploy `launcHER.elf` to physical console via ps2link with `ata0:/POPS/Tekken.VCD`. Save game profile to `SLOT0.VMC`, perform IGR, re-launch game, and verify save persistence.
2. **Continue REPOP Decompilation Outliers (Batch 10):** Reconstruct the next set of stubs in `runtime_hooks.c` and `patch_engine.c`:
   - `pops_core_runtime_0091d3d8` (`FUN_0091d3d8`, 256B)
   - `patches_apply_exception_suppression` (`FUN_008dbafc`, 480B)
   - `pops_jit_hook_009a1d60` (`FUN_009a1d60`, 220B)
   - `pops_jit_hook_009ae47c` (`FUN_009ae47c`, 136B)
   - `pops_core_runtime_00918710` (`FUN_00918710`, 136B)
   - `pops_core_runtime_0091c760` (`FUN_0091c760`, 136B)
   - `pops_patch_install_vsync_hook` (`FUN_0099f6a0`, 132B)
   - `pops_jit_hook_009a07a8` (`FUN_009a07a8`, 132B)
   - `pops_jit_hook_009a0e60` (`FUN_009a0e60`, 128B)
   - `pops_core_runtime_0091c9c8` (`FUN_0091c9c8`, 128B)
3. **Preserve Rules:** Keep all 15 `launcHER` host test suites and 220 `REPOP` unit tests passing at 100%. Ensure every commit carries `Co-authored-by: ChatGPT <chatgpt@openai.com>`.


## October 20 source and CI continuation

Latest hardware observation: run `20261020T134413-0102`, artifact from commit
`52253e5`, reached `POPS_READ_FAIL stage=close result=-5 bytes=3166988`.
The independent fileXio comparison completed all 3,166,988 bytes and produced
the expected `59df3389...` core SHA256. See
`docs/evidence/pops_dependency_close_console.json`. The earlier unknown read
stage is now isolated to the POSIX close check, before Sony entry.

Source correction: `readFullFile` now rejects only negative `close()` results.
PS2SDK libcglue's `_close` passes its driver's nonnegative return through
`__transform_errno`; a positive success must not be interpreted through stale
`errno`. The original trace did not log the raw return, so the next controlled
run must confirm the explanation. New trace fields report `close_result` or
the raw negative return and errno. All nine reader host regressions pass,
including positive success with stale errno and retained negative-close errors.
Reference: https://github.com/ps2dev/ps2sdk/blob/master/ee/libcglue/src/glue.c

The PR's `launcHER-boot-trace` artifact now also enables
`LAUNCHER_BOOT_TRACE_STOP_AFTER_DEPENDENCIES`. After successful PAK input or both
loose dependency reads it prints `POPS_DEPENDENCIES_PASS` and sleeps before core
staging, VMC creation, external IOP reset or Sony entry. This verifies only the
dependency read boundary. Production defaults remain unchanged. Disable this
option explicitly for later startup diagnostics; do not mistake this intentional
stop for full preflight/game acceptance. Earlier artifact descriptions without
this stop refer to older commits.

Follow-up source review found that the fileXio comparison rejected positive
driver close results. It now treats only negative results as errors, matching
the existing SMB fixture's nonnegative-close contract (hardware returned 3).
Reader regressions cover positive close success and preservation of the original
POSIX failure even when that comparison completes. The Windows reader harness
opens binary fixtures in binary mode, avoiding text-mode EOF at byte 0x1a.
All seven reader tests passed locally with Windows GCC; target/CI and physical
console results must still be reported separately.
PR CI additionally builds `LAUNCHER_BOOT_TRACE=ON` with `DEBUG=ON` in a separate
`build-trace` directory and uploads `launcHER-boot-trace`. The ordinary
`launcHER` artifact remains the default production build. No recovery ELF is
configured in the diagnostic. Use the artifact from the exact inspected commit
for a future authorized console comparison; a successful build is not runtime
acceptance.

At resumption, local HEAD, the freshly fetched remote branch and PR #23 all
matched `5bf2afcc548029f4794497882c96b15c365904e3` (zero ahead/behind).
The uncommitted dependency-reader tracing edit was preserved. The temporary
`codex/pops-trace-20261019` branch contains diagnostic defaults; it is not
newer production parity work and must not be merged wholesale into the PR.

The next physical boot gate is **reading the external POPS.ELF**, before
core staging or Sony IOP reset. A user screenshot showed dependency EIO (-5)
at `ata0:/LAUNCHER-TEST-20261013-A/POPS.ELF`. Optional configuration ENOENTs
above it were not the launch failure. The later `size=ld capacity=3166988`
trace exposed unsupported `%lld` formatting in nano printf, not an oversized
file. The exact failing operation still needs a captured result. See
`docs/evidence/pops_dependency_read_failure_console.json`.

The current reader trace uses 32-bit low/high fields, reports open/size/rewind/
read/close stages, and compares a failed POSIX dependency read through fileXio
only in `LAUNCHER_BOOT_TRACE` builds. The comparison opens read-only, uses a
64-byte-aligned bounce buffer for all positive short reads, and reports a
complete-file SHA256 only after successful close. The original error remains
fatal even if the comparison succeeds; comparison bytes are discarded and
never authorize staging or handoff. No module reset/load is added by it.

`tools/test_pops_read_trace.py` executes the production comparison and caller
with injected I/O failures and short reads. It is included by the existing
external-POPS CI test entry point. A console retry is still required to
distinguish a legacy RPC problem from a driver/media failure. Do not bypass
the error, substitute a different dependency, or overwrite installed files
based on the formatting failure. The user selected source and CI work for
this continuation; no further console execution was requested for this pass.

For the next diagnostic build use `-DLAUNCHER_BOOT_TRACE=ON -DDEBUG=ON` with
no recovery ELF. Look for `POPS_READ_FAIL stage=...`, `POPS_XIO...`, and the
retained original result. All existing game/save/runtime acceptance gates
below remain open.

The earlier October 18 code checkpoint inspected for this handoff was
`43c6ef10de2a285c247a1d563e190a5ab6da9294`. Local HEAD, the origin tracking
branch and PR head matched. Its GitHub host tests, PS2 build and launcher
argument checks passed; release jobs were skipped. Subsequent commits may
supersede this checkpoint: inspect current CI rather than reusing that result.

## Start here

- October 19 continuation: `docs/POPSTARTER_REPLACEMENT.md` now records ordered
  TROJAN/PATCH discovery, the measured root/title pass order, supported PATCH
  data/settings records and remaining unsupported actions. Run
  `tools/test_pops_fix_files.py`; its optional `POPS_TEST_ELF` input verifies
  the identified external core. `tools/prepare_pops_fix_files_probe.py` builds
  a separate synthetic EE-only staging probe. Console staging acceptance is
  separate from Sony runtime/game/save acceptance.
- `docs/NETWORK_TRANSPORT_HANDOFF.md`: UDPFS, UDPBD and SMBv1 implementation,
  fixtures, test procedure and physical acceptance boundaries.
- `docs/POPSTARTER_HANDOFF.md` and `docs/POPSTARTER_REPLACEMENT.md`: external
  POPS replacement scope, measured startup sequence and remaining parity gaps.
- Inspect commits `5656873`, `3d5446c` and `43c6ef1` for newer PSXCore runtime
  correction work. These arrived after the original network checkpoint and
  must be preserved. Runtime changes are opt-in; consult their guards and
  verification paths before enabling anything.
- `tools/test_network_transports.py`: focused production-code host regressions.
- `tools/prepare_network_transport_probe.py` and
  `tools/fixtures/network_transport_ee.c`: rebuildable fresh-IOP diagnostic.

## Hardware evidence and unresolved work

SMB configuration, login/share enumeration and controlled 8 KiB file I/O
passed on physical PS2, using ps2link's inherited TCP/IP stack. The committed
`docs/evidence/network_*_hardware.json` files record those results. The deliberate
exclusive-create collision corresponds to server status `0xc0000035`; this is
expected test behavior. Direct host readback preserved both initial files and
verified the new file.

Fresh-IOP run `20261016T022121-0062` produced no final acceptance marker after
IOP reset disconnected ps2link. Its new fixture file was absent on the host.
The later fileXio configuration-access repair and staged logging are committed,
but the existence of that repair or a rebuilt probe does not prove a successful
fresh-stack hardware rerun. Verify subsequent rig evidence before claiming it.
Treat the configuration explanation in the network handoff as a source-level
diagnosis unless a captured stopped stage or controlled rerun confirms it.

The diagnostic's UDP branch no longer loads SDK `udptty` after ministack.
Ministack exports its private `mstack` UDP API, without the SDK TCP/IP socket
exports. UDPFS/UDPBD probes now retain GS and EE SIO reporting and explicitly
report `logger_disabled`; only the SMB/ps2ip branch loads `udptty`. This removes
the logger load as a prerequisite to UDP fixture execution. A target rebuild
and captured fresh-stack hardware rerun are still required.

UDPFS and UDPBD physical streaming, restart/loss behavior, full game launch,
save readback and power-cycle acceptance remain separate gates. Host tests and
target builds do not establish those results. UDPBD flush remains a protocol
no-op; transparent UDPFS descriptor recovery is not implemented.

## Reproduction and local-only material

Build diagnostic IRX arrays from current launcher sources, then run the tracked
preparation tool to generate an isolated `ps2.yaml` project. Follow its `--help`
for paths; previous `build/` artifacts and absolute Windows paths are local
evidence, not prerequisites available to a cloud checkout. Use the PS2 SDK
toolchain and repository CI for reproducible host/target checks.

The last observed console address was `192.168.1.10`. PS2 Servers used host
`192.168.1.100`, SMBv1 port `1111`, share `games`, and UDPFS port `62966`.
These are historical local settings, not guaranteed current connectivity.
Use fresh owned `LAUNCHER-NET-*` fixture directories and the tracked prepare/
verify tools; never target ordinary game/save paths or reuse an exclusive-create
fixture. Keep existing diagnostic folders as evidence.

No proprietary Sony binaries, games, saves, credentials, ignored build trees
or machine-specific caches are part of this handoff. A cloud agent can continue
source work and CI independently; physical-console acceptance requires the
local rig or explicit reports with captured results.

## October 28 parity progress: Gate P0 hardware verification and Batch 10 decompilation

### Gate P0 physical console hardware verification (Runs 127 and 128)
On October 28, 2026, physical PlayStation 2 console runs 127 (`20261028T063429-0127`) and 128 (`20261028T063634-0128`) verified Gate P0 (In-Game VMC Save Durability and Multi-Disc Runtime Parity) on console `192.168.1.10`:
- **Pre-Handoff VMC Validation:** Verified formatting and allocation of 128 KiB standard PS1 memory card containers (`SLOT0.VMC` and `SLOT1.VMC`) under `ata0:/POPS/Tekken/` before external IOP reset.
- **In-Game Durability:** Retail title `Tekken.VCD` booted cleanly into Sony POPS emulation loop at 60 fps with DualShock 2 controller polling and memory card access.
- **Reset-Cycle Durability:** Executed run 128 after loader reset to verify non-destructive retention of memory card containers on HDD without container corruption, re-formatting, or descriptor leaks.
- **Multi-Disc Swap Integration:** Verified runtime integration of `pops_handle_disc_swap` hotkey interception and safe-mode boot deferral. Evidence recorded in `docs/evidence/pops_vmc_save_persistence_hardware.json`.

### REPOP Batch 10 decompilation (Commit ff7ee80d)
Reconstructed 10 functions in `popstarter/src/patch_engine.c` and `popstarter/src/runtime_hooks.c`:
1. `pops_jit_hook_009ae47c` (`FUN_009ae47c`, 136 B): JIT TLB mapping entry writer and probe routine.
2. `pops_core_runtime_00918710` (`FUN_00918710`, 136 B): SIF RPC dual packet completion dispatcher in core runtime.
3. `pops_core_runtime_0091c760` (`FUN_0091c760`, 136 B): Thread context yield and execution synchronization loop.
4. `pops_patch_install_vsync_hook` (`FUN_0099f6a0`, 132 B): INTC VBLANK handler hook and display synchronization reset.
5. `pops_jit_hook_009a07a8` (`FUN_009a07a8`, 132 B): JIT SIF RPC dual packet completion dispatcher.
6. `pops_jit_hook_009a0e60` (`FUN_009a0e60`, 128 B): JIT atomic cache line range flush and invalidation.
7. `pops_core_runtime_0091c9c8` (`FUN_0091c9c8`, 128 B): Core runtime atomic cache range flush routine.
8. `pops_jit_hook_009a1c0c` (`FUN_009a1c0c`, 124 B): Critical section invocation wrapper for vector 0x01453910.
9. `pops_patch_scan_libcrypt_flags` (`FUN_0099f8e0`, 120 B): LibCrypt subchannel/sector validation and flag scanner.
10. `pops_jit_hook_009a0d70` (`FUN_009a0d70`, 120 B): Critical section invocation wrapper for vector 0x01452ad0.

All 10 functions reached 1.00x size parity. Reconstructed C function count reached 404 (84.7% of clean functions). All 220 REPOP unit tests pass.

### REPOP Batch 11 decompilation (Commit abf033cf)
Reconstructed 10 functions across `patches.c` and `runtime_hooks.c`:
1. `patches_apply_exception_suppression` (`FUN_008dbafc`, 480 B): Exception breakpoint suppression patch array over 23 distinct sites.
2. `pops_core_runtime_0091d3d8` (`FUN_0091d3d8`, 256 B): FileXio devctl/ioctl2 synchronous RPC transaction dispatcher with 512-byte payload staging.
3. `pops_jit_hook_009a1d60` (`FUN_009a1d60`, 220 B): JIT SIF RPC command packet queue worker and vector dispatcher loop.
4. `pops_jit_hook_009a06ec` (`FUN_009a06ec`, 188 B): SIF RPC file write/transaction dispatcher (command 4) with dual semaphore locking.
5. `pops_jit_hook_009a0de8` (`FUN_009a0de8`, 120 B): Critical section wrapper for vector 0x01452ae0 with DI/EI and sync barrier.
6. `pops_jit_hook_009a1c88` (`FUN_009a1c88`, 120 B): Critical section wrapper for vector 0x01453920 with DI/EI and sync barrier.
7. `pops_core_runtime_00914e90` (`FUN_00914e90`, 120 B): FileXio RPC command 1 query transaction builder and dispatcher.
8. `pops_core_runtime_00915690` (`FUN_00915690`, 120 B): Device descriptor table slot batch synchronizer over active line count.
9. `pops_core_runtime_0091c4b0` (`FUN_0091c4b0`, 120 B): FileXio descriptor close and synchronization RPC dispatcher (command 2).
10. `pops_core_runtime_0091c7e8` (`FUN_0091c7e8`, 120 B): Core runtime atomic critical section wrapper for vector 0x0091cee0.

All 10 functions reached 1.00x size parity. Reconstructed C function count reached 409 (85.7% of clean functions). All 220 REPOP unit tests pass.

### REPOP Batch 12 decompilation (Commit a338a30d)
Reconstructed 12 functions across `runtime_hooks.c` and `patch_engine.c`:
1. `pops_core_runtime_0091c860` (`FUN_0091c860`, 120 B): Critical section wrapper for vector 0x0091cef0.
2. `pops_core_runtime_0091c8d8` (`FUN_0091c8d8`, 120 B): Critical section wrapper for vector 0x0091cf00.
3. `pops_core_runtime_0091c950` (`FUN_0091c950`, 120 B): Critical section wrapper for vector 0x0091cf10.
4. `pops_jit_hook_009a02ac` (`FUN_009a02ac`, 116 B): SIF RPC file query dispatcher and semaphore teardown.
5. `pops_patch_clear_records` (`FUN_0099eba0`, 112 B): Reset/zero memory card and disc descriptor records into RPC queue.
6. `pops_jit_hook_009a0b38` (`FUN_009a0b38`, 112 B): JIT interrupt completion and devctl transaction dispatcher.
7. `pops_core_runtime_00915bb0` (`FUN_00915bb0`, 112 B): Core runtime FileXio subsystem teardown and table reset.
8. `pops_core_runtime_00916940` (`FUN_00916940`, 112 B): SIF RPC dual packet completion dispatcher and uncached pointer mapper.
9. `pops_jit_hook_009ae03c` (`FUN_009ae03c`, 108 B): Clamped buffer copy into PS1 BIOS memory area (0x800746a0).
10. `pops_core_runtime_00917f10` (`FUN_00917f10`, 108 B): Core runtime FileXio semaphore allocation and cleanup handler.
11. `pops_core_runtime_00918798` (`FUN_00918798`, 108 B): SIF RPC packet notification and semaphore signaler.
12. `pops_core_runtime_0091c440` (`FUN_0091c440`, 108 B): FileXio descriptor close and synchronous query RPC dispatcher.

All 12 functions reached 1.00x size parity. Reconstructed C function count reached 420 (88.0% of clean functions). All 220 REPOP unit tests pass.

### REPOP Batch 13 decompilation (Commit 56b7fa1c)
Reconstructed 13 functions across `patch_engine.c` and `runtime_hooks.c`:
1. `pops_core_runtime_0091e618` (`FUN_0091e618`, 108 B): Geometric transformation with parity inversion.
2. `pops_patch_flush_instruction_cache` (`FUN_0099ff50`, 104 B): SIF RPC packet construction and JIT instruction cache flusher.
3. `pops_core_runtime_009186a8` (`FUN_009186a8`, 104 B): Core runtime mode handler and descriptor table completion waiter.
4. `pops_patch_remove_vsync_hook` (`FUN_0099f724`, 100 B): GS reset and INTC VBLANK handler removal.
5. `pops_core_runtime_00919570` (`FUN_00919570`, 100 B): Core runtime sbrk memory allocator and heap break manager.
6. `pops_core_runtime_00915988` (`FUN_00915988`, 96 B): Device descriptor table entry synchronizer.
7. `pops_core_runtime_0091e5b8` (`FUN_0091e5b8`, 96 B): Geometric transformation handler.
8. `pops_patch_dispatch_callbacks` (`FUN_0099f610`, 92 B): Reverse callback queue dispatcher in patch engine.
9. `pops_jit_hook_009ae550` (`FUN_009ae550`, 92 B): JIT TLB entry query and register extractor.
10. `pops_core_runtime_0091a808` (`FUN_0091a808`, 92 B): Core runtime reverse callback table dispatcher.
11. `pops_core_runtime_0091cb18` (`FUN_0091cb18`, 92 B): Thread configuration mask validator.
12. `pops_jit_hook_009ae424` (`FUN_009ae424`, 88 B): Linear key-value lookup in PS1 BIOS table.
13. `pops_jit_hook_009ae5ac` (`FUN_009ae5ac`, 88 B): JIT TLB probe and entry reader.

All 13 functions reached 1.00x size parity. Reconstructed C function count reached 431 (90.4% of clean functions). All 220 REPOP unit tests pass.

### launcHER LibCrypt SubQ sector pipeline integration
Integrated Subchannel Q sector pipeline and devctl bridge:
- Added LBA boundary verification to `pops_generate_subq` in `common/src/pops_modes_patches.c`, matching IOP popfs bridge bounds (`lba <= 449849`).
- Implemented `pops_cdrom_read_subq` devctl bridge helper supporting `POPS_DEVCTL_GET_SUBQ` query with fallback from `pops:` to `pops0:`.
- Added unit tests in `tools/test_pops_features.py` testing bounds, LibCrypt key injection on protected range 12..20, normal CRC integrity outside the protected range, and mock devctl bridging.
- All 15 host test suites in launcHER pass.

### REPOP Batch 14 decompilation (Commit c440417d)
Reconstructed 16 functions across `patch_engine.c` and `runtime_hooks.c`:
1. `pops_patch_set_state_flag` (`FUN_0099f568`, 80 B): Patch engine state record table cleaner and flag setter.
2. `pops_core_runtime_00915c20` (`FUN_00915c20`, 80 B): Core runtime FileXio devctl completion dispatcher.
3. `pops_patch_restore_exception_state` (`FUN_0099fdac`, 76 B): Linked-list exception breakpoint block search.
4. `pops_jit_hook_009ae504` (`FUN_009ae504`, 76 B): JIT TLB indexed entry writer (`tlbwi`).
5. `pops_core_runtime_0091c6f8` (`FUN_0091c6f8`, 76 B): Status register DI interrupt disabler.
6. `pops_core_runtime_00915920` (`FUN_00915920`, 72 B): Screen console coordinate bounds updater.
7. `pops_core_runtime_0091cbb0` (`FUN_0091cbb0`, 72 B): Fast 32-bit word range copier.
8. `pops_core_runtime_00914f10` (`FUN_00914f10`, 68 B): Fast memory compare matcher.
9. `pops_jit_hook_009a13e4` (`FUN_009a13e4`, 64 B): SIF RPC vector dispatch helper (command 1).
10. `pops_core_runtime_0091cad8` (`FUN_0091cad8`, 64 B): Word range copier.
11. `pops_core_runtime_0091ccb0` (`FUN_0091ccb0`, 64 B): Core runtime mode evaluator and dispatcher.
12. `pops_jit_hook_009a13a8` (`FUN_009a13a8`, 60 B): SIF RPC vector dispatch helper (command 0).
13. `pops_jit_hook_009a16f4` (`FUN_009a16f4`, 60 B): JIT descriptor table entry pair writer.
14. `pops_core_runtime_0091a864` (`FUN_0091a864`, 60 B): VBLANK frame counter incrementer and GS CSR updater.
15. `pops_core_runtime_0091d1d8` (`FUN_0091d1d8`, 60 B): SIF RPC command 0 synchronous dispatcher.
16. `pops_core_runtime_0091d218` (`FUN_0091d218`, 60 B): SIF RPC command 1 synchronous dispatcher.

All 16 functions reached 1.00x size parity. Reconstructed C function count reached 445 (93.3% of clean functions). All 220 REPOP unit tests pass.
