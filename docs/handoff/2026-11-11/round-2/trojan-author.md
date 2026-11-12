# TROJAN_n.BIN on the PR #23 line: pr23/trojan-2

Scratch paths are written `<scratch>` (the session scratchpad).

- Branch: `pr23/trojan-2`, worktree `<workspace>/launcHER.worktrees/trojan-2`, from `ef663b2`.
- Pushed: yes, `origin/pr23/trojan-2`. Head `6732e95`.
- Commits (first parent):
  - `7425303` merge: TROJAN_n.BIN by POPStarter's rules, hosting and slot chain (pr23/trojan), a real merge of `origin/pr23/trojan` at `8f889cf` (7 commits on `cfebe01`).
  - `5624c29` fix(pops): read a TROJAN file as POPStarter does: a failed open, size or header read skips it.
  - `1d75d50` docs(pops): TROJAN reading on device failures, the 1 MiB skip and the container build.
  - `6732e95` test(pops): end the read trace test's handler fragment before the TROJAN reader.
- The trojan branch's own worktree (`launcHER.worktrees/trojan`) was not touched. Nothing was pushed to `codex/popstarter-replacement`, EMBER, a tag or a release. No force-push.
- Host tests and Unicorn emulation only. **NOT TESTED on a console.** No PS2 emulator (PCSX2 or similar) was run.

## 1. What changed

### 1.1 Merge resolution (`7425303`)

- `common/src/pops_modes_patches.c`: both functions kept. HEAD's `pops_fix_context_rom_loaded` (BIOS.BIN state) stays as it was; the trojan side's `fix_context_refresh`, `fix_in_core`, `fix_ranges_meet`, `fix_slot_hook`, the `_Static_assert` and `pops_fix_stage_trojan` follow it. `pops_fix_stage_rom` (the PATCH path, with the BIOS.BIN `rom` state) ends with `fix_context_refresh(context, bytes); return mode6_skipped ? POPS_MODE6_SKIPPED : 0;` and refuses a TROJAN call (`expected_trojan` gives `-EINVAL`): TROJAN files go through `pops_fix_stage_trojan` only.
- `launcher/src/handler_pops.c`: `pops_stage_fix_files(..., PopsUserRomState *rom, PopsFixContext *finalContext, PopsTrojanSet *trojanSet)`; the loop calls `kind ? pops_fix_stage_rom(&context, ..., slot, 0, rom) : pops_fix_stage_trojan(&context, trojanSet, ...)`. `pops_stage_user_files` takes the `PopsTrojanSet *` and sets `chain_offered` from `pops_resident_slot_chain_possible` just before staging the fix files. `launchPOPS` owns `romState`, `fixContext` and `trojanSet` (`pops_trojan_set_init` with the fingerprint's built-in id and whether the built-in plan has a break call; hold and work memory set) and passes all three. The BIOS.BIN loader still runs before each folder's files, as before; its comment is kept.
- `tools/test_pops_fix_files.py`, `tools/test_pops_user_bios.py`: harnesses pass a host `PopsTrojanSet`; source-text checks follow the merged call lines.
- **Bug found in review and fixed in the merge:** `POPS_MODE6_SKIPPED` (a PATCH file whose mode 6 is not applied under a user BIOS.BIN) has the value 1, the same as `POPS_FIX_SKIP_INVALID`. With the trojan branch's loop, such a PATCH file would have been printed "Invalid" and treated as skipped. The three skip checks are now `!kind && result == ...`, and rejection is `result < 0 || (!kind && result)`. Test `test_a_patch_whose_mode_6_is_skipped_is_not_called_invalid` (mutation-checked: it fails with the guard removed).

### 1.2 Review against r13 and the fix (`5624c29`)

The trojan branch read TROJAN files with `readFullFile`, so an open error other than ENOENT, a size or read error, and any file over the 1 MiB buffer stopped the launch. The task's rule "the launch must no longer abort on a TROJAN file the original skips" needed the original's behaviour on device failures, so it was measured:

- `tools/trace_original_pops_trojan.py`: `Loader.run(..., faults=...)` puts failures into the modelled file calls (`{path: {"open": rc} | {"size": rc} | {"read": [rc or None, ...]}}`); handles track their path and read count.
- Measured on the original (`POPSTARTER_TEST_ELF`, Unicorn), `Original.test_device_failures`:
  - a failed open (-1, -2, -5, -19) prints `NOT FOUND`; the next number is read;
  - a failed size query is Invalid (size below 0x44);
  - a header read that fails after an earlier file is Invalid (the original clears its header buffer after every file, `0x881d24`); a failed first header read is also Invalid in the model;
  - a failed payload read is not checked: the file is applied with whatever the buffer held;
  - a file with 1 MiB of payload is applied.
  - Check addresses read from the disassembly: open `0x88115c`, size/header `0x881188..0x881230` (results unchecked), payload `0x881a1c`.
- New `pops_fix_trojan_header` (`common/src/pops_modes_patches.c`, declared in `pops_modes_patches.h`): verdict from the header and the file's size; Invalid/outdated as `pops_trojan_verdict` says; a file to apply that is larger than the caller's buffer is `POPS_FIX_SKIP_UNHOSTED` with the new reason `POPS_TROJAN_NO_LARGE` (13, "the file is larger than launcHER's 1 MiB fix file buffer").
- New `pops_read_trojan` in `handler_pops.c`: size by `lseek` to the end (negative or above 0x7fffffff reads as 0), unchecked rewind, 0x40-byte header zeroed then read until it arrives or a read returns <= 0, decision, then the payload read only for a file to apply. A failed payload read returns a negative error (still fatal: deviation, see 4.8). The loop opens TROJAN files itself; a failed open is `NOT FOUND` (DPRINTF) and `continue`. PATCH still uses `readFullFile`. The trojan branch's empty-file reopen hack is gone.
- `pops_trojan_verdict` doc: only the first 0x40 bytes are read; `size` is the file's size.
- `tools/test_pops_trojan.py`: the `Source` wrapper gains fault injection (n-th read and later fail; open failure; SEEK_END failure); new tests `test_a_file_larger_than_the_read_buffer_is_skipped_not_fatal`, `test_a_header_that_cannot_be_read_is_invalid`, `test_a_payload_read_error_still_stops_the_launch`, `test_a_file_that_cannot_be_opened_is_not_found`, `test_a_file_whose_size_cannot_be_read_is_invalid`, `test_a_patch_read_error_still_stops_the_launch`, `Native.test_the_header_decision`, `Original.test_device_failures`; `test_slot_chain_text`, `test_handoff_text`, `test_the_loop_text` follow the new structure.

### 1.3 Doc (`1d75d50`)

`docs/POPSTARTER_TROJAN.md` (the branch's own doc): device-failure behaviour of the original; launcHER's reader; the mode-6/Invalid collision; the 1 MiB skip in the hosting list; evidence row for device failures; known differences 3 and 4 rewritten; the container build's sizes replace "the whole ELF was not built". None of the five protected docs was edited.

### 1.4 Read-trace test fragment (`6732e95`)

`tools/test_pops_read_trace.py` compiled `handler_pops.c` from `readFullFile` up to the fix file loop's comment; `pops_read_trojan` now lies in that range, so its host build failed. The fragment now ends at the TROJAN reader's comment. Nothing else in the test changed.

### 1.5 CI

`.github/workflows/build.yml` already runs `tools/test_pops_trojan.py` and `tools/test_pops_trojan_corpus.py` (from the trojan branch, merged). The new tests are methods in `test_pops_trojan.py`, so no workflow change was needed.

## 2. Commands and results

All in Git Bash from the worktree root unless noted. Test runs used `<scratch>/trojan2/run_tests.sh noref|ref <logdir> [tests]`, which runs each `tools/test_*.py` one at a time with TMP, TEMP and TMPDIR set to a fresh empty `<scratch>/tmp-trojan2/<mode>` and the three reference variables unset (`noref`) or set (`ref`).

| Command | Result |
|---|---|
| `git worktree add -b pr23/trojan-2 ../launcHER.worktrees/trojan-2 ef663b2` | created |
| `git merge --no-ff origin/pr23/trojan` | conflicts in `common/src/pops_modes_patches.c`, `launcher/src/handler_pops.c`, `tools/test_pops_fix_files.py`; resolved by hand and with `<scratch>/trojan2/resolve_handler.py`, `fix_*.py` |
| Host tests on the merge (no refs): fix_files, user_bios, trojan, launch_hooks, igr_skin, resident, doc_claims | 31 OK (3 skipped); 51 OK (13 skipped, 1 expected failure); 59 OK (16 skipped); 48 OK (14 skipped); 48 OK (21 skipped); 75 OK (12 skipped); 12 OK (7 skipped) |
| `test_pops_trojan.py` with refs, on the merge | 59 OK, 5 skipped (Chain, OriginalSlots: no resident image) |
| `test_pops_trojan_corpus.py` with refs, on `7425303` | OK, 80 s, the design's table (section 3) |
| `python <scratch>/trojan2/probe_faults.py` (original under Unicorn with faults) | the behaviour in 1.2 |
| `git commit` + `git push -u origin pr23/trojan-2` (`7425303`, `5624c29`) | pushed |
| Container build, the prescribed command | failed: `fatal: not a git repository` (the worktree's `.git` file names a Windows path; `git config --global --add safe.directory` run inside `/workspace` fails) |
| Same, with `(cd / && git config --global --add safe.directory /workspace)` | failed: `Directory does not exist for chdir command: /workspace/launcher/iop/mmceman/mmceman` (submodule not initialised in a new worktree) |
| `git -c protocol.file.allow=always submodule update --init --reference <workspace>/launcHER/launcher/iop/mmceman launcher/iop/mmceman` | checked out `db3e93f` |
| Container build again, on `5624c29` (log `<scratch>/trojan2/build1.log`; later commits change only a doc and a test) | **PASS**. `build-trojan2/release/launcHER.elf` 331,284 bytes (PR branch baseline 326,772: +4,512); `pops_resident.bin` 7,504 bytes. 34 compiler warnings, all in code this work did not change (mmceman, init.c, handler_quickboot.c, the VMC `snprintf`s in handler_pops.c); one CMake warning "No Git revision available: writing version=unknown" (same worktree cause) |
| `python tools/check_pops_resident_image.py build-trojan2/launcher/pops_resident.bin` | rc 0, every section PASS, incl. "resident TROJAN slot chain: PASS (142 cases, 700 slot records ...)" |
| `POPS_RESIDENT_BIN=<built image>` + refs: `test_pops_trojan.py`, `test_pops_resident.py` | 59 OK, 0 skipped ("Original slot chain PASS: 71 cases, 350 slot records"; "Original file-to-slot PASS: 5 style sets x 5 pad states, 210 slot records"); 75 OK |
| Scan of `git diff ef663b2 HEAD` for 32+ hex-digit strings, game IDs, attribution | none |
| `git commit` + push (`1d75d50`) | pushed |
| Every `tools/test_*.py`, no refs, on `1d75d50` | 34 files, all rc 0 (log `<scratch>/trojan2/logs-final2-noref`). With skips: breakpoint 11 (4 skipped), builtin_db 14 (14), config_text 23 (10), display 21 (6), doc_claims 12 (7), external 128 (14), features 29 (2), fix_files 31 (3), igr_skin 48 (21), io_probe 6, launch_hooks 48 (14), module_irx 11 (4), opcodes 9 (3), padman 6 (3), physical_disc 40 (18), progressive 8 (5), read_trace 9, resident 75 (12), runtime_corrections 8, smb_config 37 (13), startup_calls 6, trojan 59 (16), trojan_corpus 3 (3), user_bios 51 (13 skipped, 1 expected failure), warmboot 7 (3); launch_args, network_transports, popfs, fatfs, modes, vmc, smap_ipconfig, sony_ioman_layout, subq_bridge rc 0 (no unittest summary). An earlier no-ref run on `1d75d50` failed `test_pops_read_trace` and `test_pops_external` (which runs it): the read-trace test compiles handler_pops.c from `readFullFile` to the loop's comment, and `pops_read_trojan` now sits there and needs `PopsTrojanSet`. Fixed in `6732e95` (test fragment ends at the TROJAN reader's comment); this row is the rerun on `6732e95`. During that fix `test_pops_read_trace.py` was also run once on its own (9 OK, own empty tmp folder) while the earlier run was still finishing: the only time two tests ran at once. |
| Every `tools/test_*.py`, with refs, on `1d75d50` | 34 files, all rc 0, on `6732e95` content (log `<scratch>/trojan2/logs-final-ref`; the read-trace fix was in place before the run reached those two files): breakpoint 11, builtin_db 14, config_text 23, display 21, doc_claims 12, external 128 (3 skipped), features 29, fix_files 31, igr_skin 48, io_probe 6, launch_hooks 48 (3), module_irx 11, opcodes 9, padman 6, physical_disc 40, progressive 8 (3), read_trace 9, resident 75, runtime_corrections 8, smb_config 37, startup_calls 6, trojan 59 (5: Chain/OriginalSlots without POPS_RESIDENT_BIN; 0 skipped with it, row above), trojan_corpus 3, user_bios 51 (1 expected failure), warmboot 7; the rest rc 0. |

## 3. The design's table

`test_pops_trojan_corpus.py` with `POPS_TROJAN_CORPUS`, `POPSTARTER_TEST_ELF`, `POPS_TEST_ELF`:

Run in the reference pass on the head (55 s, OK):

```
TROJAN corpus: 509 files by content and slot number, 3952 copies
launcHER, slots offered:
    367 files   3744 copies  loaded
    120 files    158 copies  not loaded: it uses POPStarter's 480p handler, which launcHER does not have
     17 files     36 copies  not loaded: it uses POPStarter code at 0x238a90..0x2397ef, which launcHER does not have
      5 files     14 copies  not loaded: it uses POPStarter code at 0x0143a000..0x014601ff, where launcHER keeps its own
  of the loaded: 367 needs the slots; hooks on one of the ten slots: 509 of 509 applied files
  header (format, byte 0x0a, byte 0x0e): 507 x (1, 0, 1), 2 x (3, 6, 1)
TROJAN corpus vs the original loader: 509 files, verdicts {'APPLIED': 509}; 367 loaded by launcHER with the original's slot words and payload bytes, 142 applied there and not loaded here
PATCH corpus vs the original loader: 10 files by content and slot number, 870 copies; 10 applied by launcHER with the whole POPS image equal to the original's (0 to 324236 changed bytes), not applied here: none
```

- 4,822 files: 3,952 TROJAN + 870 PATCH copies. **Matches.**
- 509 TROJAN and 10 PATCH unique. **Matches.**
- Equal verdicts for every unique file: the test asserts launcHER's verdict equals the original's printed verdict per file (`assertEqual(self.tracer.verdicts(events), [words[verdict]], path)`); all 509 APPLIED on both. **Matches.**
- PATCH 10 of 10 identical (whole POPS image). **Matches.**
- The 142 "applied by the original, not loaded here" are launcHER hosting refusals (POPStarter code launcHER lacks), not verdict differences; each is skipped with a line and the launch goes on (known difference 1).
- The test prints counts only; no corpus byte, name or hash is written anywhere in the repository (diff scanned, row in section 2).

## 4. Proposed text for the shared docs (coordinator to number and place)

### 4.1 `docs/POPSTARTER_R13_INVENTORY.md`, TROJAN row

Keep **PARTIAL**. Proposed cell: "TROJAN_n.BIN: verdicts equal to r13 for every file of the owner's collection (509 unique) and for generated files, device failures included (Unicorn). 367 of 509 loaded with r13's slot words and payload bytes; 142 not loaded (they use POPStarter code launcHER lacks) and skipped with a line. Slot chain differential-tested under Unicorn. NOT TESTED on a console. docs/POPSTARTER_TROJAN.md."

### 4.2 `docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md`, from 62

- **62** r13 accepts any nonzero header byte `0x0e`; only zero is Invalid. launcHER matches.
- **63** r13 checks no address: no alignment, no range for load, entry or hook. launcHER refuses what it cannot place safely (known difference 2 in POPSTARTER_TROJAN.md).
- **64** A hook of 0 makes r13 write `jal`/`j` at address 0. launcHER refuses it.
- **65** r13 `malloc`s twice the file size per file and never frees it. launcHER allocates nothing.
- **66** "Skipped (outdated)" (format 3, revision below 6) only when the disc matched a built-in entry by fingerprint; without a match the same file is applied. launcHER matches.
- **67** r13 runs `di` twice on the path around the slot chain (read from the disassembly; launcHER's chain keeps the original's instructions there).
- **68** launcHER's hosting refusals: a file r13 would apply is skipped with "valid for POPStarter but NOT loaded by launcHER: <reason>" when it names POPStarter code, falls outside the core/arena, overlaps launcHER, or exceeds 20 payloads / 0x6f0000 bytes.
- **69** r13 does not check the TROJAN payload read and applies the file with whatever its buffer held. launcHER stops the launch on a payload read error (owner question 5.3).
- **70** r13 has no size limit; launcHER skips a TROJAN file over 1 MiB (its fix file read buffer) with a line (owner question 5.4).
- **71** launcHER-only bug, fixed: `POPS_MODE6_SKIPPED` equals `POPS_FIX_SKIP_INVALID`; without the `!kind` guard a PATCH file with a skipped mode 6 under a user BIOS.BIN would be printed Invalid. Fixed on pr23/trojan-2 with a test.

### 4.3 `docs/PR23_HANDOFF_2026-11-11.md` sections 3.1 / 5.2

"TROJAN support merged on pr23/trojan-2 (merge 7425303, reader fix 5624c29, doc 1d75d50). Container build passes (launcHER.elf 331,284 bytes). Corpus table as designed. A TROJAN file r13 skips (Invalid, outdated, not found, unreadable size or header) no longer stops the launch; a failed payload read still does. NOT TESTED on a console."

## 5. Questions for the owner

1. **FNV-1a sums of POPS bytes.** `SLOT_RUN_A_PRISTINE`/`SLOT_RUN_B_PRISTINE` in `common/src/pops_resident.c` (from the trojan branch) are FNV-1a sums of two 0x30-byte runs of Sony's POPS core, used to confirm the runs are untouched before writing the slots. The rule says no hashes copied from Sony binaries. Existing practice already SHA-256-pins the core and embeds guard words. Keep, or replace with a check against the pinned core hash?
2. **Reproduced instruction sequences.** The resident chain entry repeats POPStarter's instructions around the slots (k0/k1 save at `0x239490`, emode checks, reset check, restore at `0x2394b0`) for register parity. Acceptable as written?
3. **Failed payload read**: stop the launch (today), or apply like r13 (garbage bytes), or skip with a line?
4. **Files over 1 MiB**: skip with a line (today) or grow the buffer / stream into hold memory for parity?
5. **Build command**: the prescribed container command fails in a git worktree (`.git` file with a Windows path) and with an uninitialised mmceman submodule. Used `(cd / && git config --global --add safe.directory /workspace)` and initialised the submodule. Update the documented command?
6. Pre-existing, noticed only: the scratchpad staging at `0x01f80000` and `POPS_BOOT_PATH_ADDR` `0x01ffecb0` lie inside the 1 MiB fix file read buffer (`0x01f00000..0x02000000`). Not changed; worth a look.

## 6. Not done

- No console run; no PS2 emulator run.
- The 142 files that need POPStarter's 480p handler or other POPStarter code are not hosted.
- PATCH reading unchanged: a PATCH read error, a PATCH over 1 MiB, or a PATCH r13 would call Invalid still stops the launch (known difference 8).
- `third_party/psxcore` submodule not initialised in this worktree (the build did not need it).
- Whether POPS's heap/stack reaches the arena; whether loaded payloads touch POPS words launcHER patches differently: not analysed (as in the doc).
