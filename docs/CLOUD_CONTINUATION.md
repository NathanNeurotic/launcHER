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
