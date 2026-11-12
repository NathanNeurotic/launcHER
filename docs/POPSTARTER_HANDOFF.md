# POPSTARTER replacement handoff

This file has two parts. The first, "ExecPS2 handoff (2026-11-11)", is the
current state of the jump from launcHER into POPS. Everything below it is the
October hardware handoff, kept unchanged as history; its claims keep their
own, older evidence scope.

## ExecPS2 handoff (2026-11-11)

**NOT TESTED on a console.** Every result in this section is a host test, an
emulation of the original code under Unicorn, or a PCSX2 run. A PCSX2 pass is
an emulator result, not a console result.

### The defect

launcHER reaches POPS through a trampoline at 0x00084000
(`launcher/src/pops_trampoline.S`). It zeroes the scratchpad, POPS's BSS up
to 0x870000 and 0x100000..0x200000, copies the staged core from 0x01000000
to 0x00200000, calls FlushCache(0) and FlushCache(2), and calls ExecPS2.

Read from the SCPH-39001 kernel (EE RAM 0x80000000.., addresses below):

- ExecPS2 (syscall 7, 0x80002f80 → 0x800057e8) walks thread ids 1..255.
  Each thread that is not DORMANT goes through iTerminateThread
  (0x80003e00), whose reset routine (0x80003bb8) writes gp, sp, fp and ra
  into the thread's initial frame at stack + size - 0xe0, -0xd0, -0xc0 and
  -0xb0. A DORMANT thread is only deleted (0x80003f00) and nothing is
  written.
- So ExecPS2 writes four words into the stack of every thread still alive,
  after the trampoline has copied POPS's core.

launcHER has such a thread at that point: ps2sdk libkernel's helper thread
(`topThread`), with a 0x400-byte stack in launcHER's BSS. In current builds
that stack is above 0x200000, inside the memory the core is copied to. In the
ef663b2 trace build the stack is at 0x208340; the four words land at
0x208660, 0x208670, 0x208680 and 0x208690 (launcHER's _gp, stack+0x3e0
twice, and ExitThread's address).

A second weakness: the trampoline zeroed 0x100000..0x200000, launcHER's own
code, while launcHER's timer (INTC 11) and SIF (DMAC 5) handlers were still
registered and interrupts were on.

POPStarter r13 does not hit either. It has no CreateThread, StartThread,
TerminateThread or DeleteThread stub (checked on the shipped image by
`tools/test_pops_handoff.py`), so it reaches its ExecPS2 as the kernel's only
thread, and nothing it clears holds its own interrupt handlers.

### The fix

Three parts, all inside the POPS launch path. ExecPS2 is still called once,
as in r13.

1. Before the jump to the trampoline, `popsHandoffRetireThreads()`
   (`launcher/src/pops_handoff_ee.c`, logic in `common/src/pops_handoff.c`):
   - Look first. If the frame the kernel would rewrite for a thread that is
     not DORMANT overlaps memory that is already prepared for POPS (the
     trampoline area 0x80000..0x100000 and the staging area), nothing is
     touched and the launch fails with -EFAULT.
   - Every other thread, ids 1..255 (the kernel's own bound): TerminateThread
     when not DORMANT, then DeleteThread. The kernel's frame rewrite now
     happens here, into launcHER memory the core copy overwrites afterwards.
   - Put the slots back in order. The kernel's free-slot queue is first in,
     first out (take at 0x80005b00 from head->prev, add at 0x80005bb0 at
     head->next). Deleting launcHER's thread puts its slot at the back, so
     POPS's first thread would get id 3 instead of 2. The code takes every
     free slot with DORMANT placeholder threads (never started), checks that
     the retired slots came out last in retirement order, then deletes the
     retired slots first and the rest after them. The queue is then in the
     order it had before launcHER's thread existed. If the order is not the
     measured FIFO order it releases in reverse, which leaves the queue as it
     was found, and says so in the report.
   - Last check: no thread other than the caller is left.
   - Eight report words are left at 0x00084300 (magic 0x464f4850, result,
     self, retired, first retired, drained, queue mode, failed id) for RAM
     dumps; no trace line can follow. Release builds write them too.
   - On failure launchPOPS returns to the menu, as for every other launch
     failure. -EFAULT comes before any thread is touched (host test).
     -EBUSY and -EIO can come after ps2sdk's helper thread is gone, with the
     trampoline and the staging area installed; the menu after that is
     untested. Neither has been seen: a kernel call would have to fail.
2. At the top of the trampoline, before the first store: interrupts off. The
   loop is ps2sdk's DI() (di, sync.p, read Status, retry while EIE is set).
   ExecPS2 empties the INTC and DMAC handler lists itself and returns with
   EIE = 0 (the di at 0x80002fa8), so POPS starts with interrupts as it does
   after r13. The handlers are no longer live while their code is zeroed.
3. ExecPS2's entry is 0x00200000, the core's first word, as in r13 (its tail
   passes that constant). Before, launcHER passed POPS.ELF's e_entry
   0x00200008. The two words between are nops, so the same code runs; the
   kernel's record of POPS's main thread (thread 1) now has r13's entry.
   This difference is older than the handoff fix; it was found by the
   review of it.

Build-time checks:

- `tools/check_pops_handoff_layout.py` runs after every link of
  launcher_unc.elf (POST_BUILD in `launcher/CMakeLists.txt`). It fails the
  build if the image leaves 0x100000..0x1000000; if the trampoline as
  assembled from its source is not in the image exactly once, or is over
  0x180 bytes; if a store or syscall comes before the di; if one of the five
  thread syscall stubs the retire code uses is missing or never called; or
  if the report magic is not built in code exactly once. In builds with
  symbols (DEBUG) it also prints where the helper thread's and the
  placeholders' reset frames and the SIF packet buffer are (reported, not
  failed). It does not look at the trampoline's arguments or the report
  words; the static asserts below do. Without python3 on the build host CMake
  warns and the check does not run; the ps2homebrew image has python3.
- Static asserts in `common/src/pops_handoff.c` (EE build and the host
  tests' gcc build) keep the trampoline (0x84000, at most 0x180 bytes), its
  arguments (0x84200..0x842b0), the report words (0x84300..0x84320) and the
  trampoline's stack top (0x8fff0) in that order without overlap.

### Not the same as r13 (recorded, not changed)

- r13 calls six service functions between its FlushCache calls and ExecPS2:
  fioExit, SifExitRpc, SifInitRpc(0), SifLoadFileInit, SifInitCmd, fioInit.
  launcHER's trampoline does not. One effect, INFERRED and not measured:
  launcHER's SIF command packet buffer stays where the IOP was last told it
  is, inside POPS's memory (0x209580..0x209600 in the fixed trace build).
  r13's SifInitCmd moves the IOP's view to r13's own memory, which survives.
  Copying the six calls into launcHER (they would have to run from C, before
  the trampoline zeroes launcHER) would not give that effect: launcHER's own
  buffer is in its BSS, inside POPS's memory (the layout check's report),
  and fioInit's RPC bind would depend on the IOP image running then (not
  measured). Owner
  question; not changed.
- Thread ids match r13 only when launcHER's extra threads were taken in id
  order from the front of the queue. That holds for the one helper thread
  in current builds.
- launcHER leaves the eight report words at 0x00084300, in release builds
  too; r13 leaves that memory as it found it. The area 0x80000..0x90000 is
  launcHER's trampoline, arguments and stack in any case, which r13 does not
  have either, so writing the words only in trace builds would not make that
  memory match r13. It would lose the one check of the release build after
  the handoff. Owner question.
- The interrupt state on the way: r13 calls ExecPS2 with EIE on, launcHER
  with EIE off. The kernel's ExecPS2 returns through its own di, so POPS
  starts with EIE off after both (kernel read, Differential test).

### What was measured, and where

Host (no inputs needed; in CI):

- `tools/test_pops_handoff.py`: the retire-and-restore logic, compiled from
  `common/src/pops_handoff.c`, against a model of the kernel's FIFO queue
  (after it, the free queue is 2..255 in order, as before launcHER's helper
  existed; DORMANT threads are deleted without a frame write; a frame in
  prepared memory is refused before anything changes; every failure path).
  The trampoline under a small R5900 model (`tools/r5900_mini.py`): no store
  before the di takes, including when the di loses the race 1 or 7 times;
  the clears and the core copy; FlushCache(0), FlushCache(2) and ExecPS2 on
  the trampoline's own stack with EIE off. The sources: the call sits right
  before the jump. On the original image (needs POPSTARTER_TEST_ELF): r13
  has no thread stubs and calls ExecPS2 once. The static asserts are present
  (moving the report words to 0x84280, or growing the arguments' strings to
  256 bytes, was checked by hand to stop the compile).
- `tools/test_pops_external.py`: pops_trampoline_args_init gives ExecPS2
  0x00200000 for an ELF entry of 0x00200008 or 0x00200000 and refuses
  others.
- `tools/test_pops_launch_hooks.py`: trace lines in the POPS launch path's
  sources (handler_pops.c and the pops_*.c files) use no `ll` conversion
  (the EE printf printed a bare "lx").

Differential, under Unicorn, against the original binary (needs
POPSTARTER_TEST_ELF and POPS_TEST_ELF; `tools/trace_original_pops_handoff.py`
runs r13's MAIN 0x87c0d4..0x87c1d0 as shipped):

- at the ExecPS2 call, both leave the same bytes in 0x90000..0x200000, from
  the end of the core to 0x870000, and in the scratchpad; 0x80000..0x90000
  is launcHER's trampoline area, which r13 leaves alone;
- the same FlushCache(0), FlushCache(2), ExecPS2 sequence, gp 0 and argc 1,
  apart from r13's six service calls and the clear of r13's own staging
  buffer (in r13's memory);
- interrupts: r13 calls ExecPS2 with EIE on and never turns it off; launcHER
  turns it off first and makes every call with it off. The kernel's ExecPS2
  returns through its di either way;
- both enter POPS at 0x200000 (the test asserts launcHER's ExecPS2 entry is
  r13's); POPS.ELF's e_entry is 0x200008 and the two words before it are
  nops (needs POPS_TEST_ELF).

PCSX2 (emulator only; ATA image, `ata:/POPS/TEST.VCD`). "Fixed" is
890a6a3 (handoff fix, entry still 0x200008); "fixed + entry" is da77546
(the same plus the 0x200000 entry and the review follow-ups):

| Build | CPU | End point | Runs | Result |
| --- | --- | --- | --- | --- |
| ef663b2 trace (unfixed) | interpreter | POPS video setup | 1 | Trap exception at 0x00208660 |
| fixed trace | recompiler | "Transferring control to trampoline" (printed before the retire call and the trampoline, so these runs end before the fixed code) | 3 | 3 PASS |
| fixed trace | interpreter | POPS's "Interlaced (FIELD)" after the handoff | 3 | 3 PASS, no trap |
| fixed release | interpreter | POPS's "Interlaced (FIELD)" after "SDR driver version" | 1 | PASS, no trap |
| fixed trace | recompiler | kernel's "Restart Without Memory Clear Done." after the handoff | 1 | PASS |
| ef663b2 trace (unfixed) | recompiler | same | 1 | FAIL: "TLB Miss, pc=0x0" right after the handoff line, no restart, thread 1 still launcHER's |
| fixed trace, POPS parked at entry | interpreter | live core = staged core | 1 | 0 words differ |
| ef663b2 trace, POPS parked at entry | interpreter | live core = staged core | 1 | 4 words differ, 0x208660..0x208690 |
| fixed + entry, trace | interpreter | POPS's "Interlaced (FIELD)" after the handoff | 3 | 3 PASS, no trap |
| fixed + entry, release | interpreter | POPS's "Interlaced (FIELD)" after "SDR driver version" | 1 | PASS, no trap |
| fixed + entry, trace | recompiler | kernel's "Restart Without Memory Clear Done." after the handoff | 1 | PASS |

Read from the kernel dumps of the runs that have them:

- Report words: result 0, one thread retired (id 2), 254 slots drained,
  queue restored, in all eleven fixed runs past the handoff with a dump (the
  five 890a6a3 interpreter runs including the park run, the 890a6a3
  recompiler run, and the five da77546 runs).
- POPS's threads have ids 2, 3, 4, 5, 8, 9 in the ten of those runs in
  which POPS got past its entry (in the park run POPS spins on its first
  instruction and only threads 0 and 1 exist). The unfixed build gives
  3, 4, 5, 6, 9, 10.
- Thread 1's recorded entry is 0x00200008 in the 890a6a3 runs and
  0x00200000 in the da77546 runs, the same as in the POPStarter control.
- The POPStarter control run from USB (different device, one thread fewer)
  shows POPS's threads at 2, 3, 4, 7, 8: by entry address the same threads
  as launcHER's, except the one launcHER has as thread 3, which the USB run
  does not create. That is what the queue model predicts for one thread
  fewer, so ids "as after POPStarter" on ATA are INFERRED. No ATA control
  run with a kernel dump was made.

The unfixed recompiler run fails before ExecPS2 runs at all: the kernel
never prints its restart lines and the dump still shows launcHER's main
thread. A jump to address 0 while the trampoline clears 0x100000..0x200000
fits an interrupt handler running after its code was zeroed (the second
weakness). That cause is INFERRED, not traced; the fixed build turns
interrupts off first (and also retires the helper thread) and passes the same run.

"Parked" means the staged core's entry word was replaced with a branch to
itself once launcHER printed "Rebooting IOP with external image", so POPS
spun on its first instruction; then the copied core at 0x200000 was compared
with the staged one. The fixed build leaves the copy intact; the unfixed
build has exactly the four words the kernel writes.

Not tested: a console; any other storage device under emulation; a full
game boot past POPS's video setup.

# POPSTARTER replacement handoff — 2026-10-08

> **Current continuation — 2026-10-28:** Read [the verified audit](POPS_PARITY_AUDIT_2026-10-28.md) and [current checkpoint](CLOUD_CONTINUATION.md). Later full-durability, resident-feature and exact-size completion claims are withdrawn. Earlier sections below retain their original, limited evidence scope.

## Verified hardware checkpoint — October 13, 2026

Physical run `20261014T050940-0020` displayed `POPS_IOP_BINDING_PASS` and
`[ps2rig] exit=0` in the OBS console capture. The actual selected Sony IOP
image, original IOPCD and real SIF RPC passed both disc aliases, all five
sector-read tuples and four distinct card write/close/reopen/readback checks
(two direct, two through production POPFS). Storage was controlled IOP memory;
this does not establish actual-device persistence or a complete game boot.
Metadata: `docs/evidence/pops_ioman_fixed_console_probe.json`.

Two causal repairs resolved the earlier hardware failures below: private
`pops_iomanx` migrates Sony's identified linked/flat IOMAN layouts and all 32
file slots; POPFS accepts newly allocated recycled slots with stale private
data. The launcher now builds/embeds this compatibility module and selects it
only in the identified Sony post-reset initialization. Normal/Ember loading
continues to use stock SDK iomanX. The probe clears its final result screen so
progress output cannot hide acceptance markers. Its network rig outcome can
still be `hang`, because the foreign reset removes ps2link; the explicit GS
result is recorded separately.

Device inventory is now complete enough to select a real game. Run
`20261014T055003-0024` loaded the production ATA/MX4SIO drivers and found many
VCDs on the ATA exFAT partition. Earlier USB/MMCE-only inventories did not
cover those devices. The stable `ata0:/POPS/Tekken.VCD` alias and VCD metadata
were verified in `20261014T055350-0025`; never reuse the transient `mass2:`
number across resets. The original title folder has an existing VMCDIR.

Run `20261014T055930-0026` created fresh console directory
`ata0:/LAUNCHER-TEST-20261013-A/`, copied Tekken as `TEST.VCD` (115654480 bytes),
and copied the known loose `POPS.ELF` and `IOPRP252.IMG` from `usb0:/POPS/`.
Every copied byte was compared after close/reopen. Original title/config/save
files were preserved. The next production boot target is
`ata0:/LAUNCHER-TEST-20261013-A/TEST.VCD`; cards should be created under its
new `TEST/` folder. Sony input files remain console/local data, never distributed.
See the three metadata-only device/inspection/staging reports in docs/evidence.

`prepare_pops_device_inventory.py` defaults to read-only enumeration; explicit
`--inspect` ELF arguments run bounded VCD/config inspection, while explicit
`--stage-test VCD POPS_DIRECTORY NEW_DIRECTORY` creates only one fresh
`ata0:/LAUNCHER-TEST-*` directory and refuses reuse. No write mode runs by
default. Next: full production boot, then actual Sony card runtime and test-save
persistence across power cycles. Earlier checkpoints below are historical.

The first exact-CI-artifact game attempt (`20261014T060154-0027`) did not boot.
Opt-in trace run `20261014T061203-0030` then confirmed that ATA initialization,
the root and VCD opens, loose dependency discovery and VCD metadata all succeed;
configuration discovery returns -6 before any Sony handoff. The earlier
mount-failure interpretation was incorrect. See the metadata-only configuration
failure report. Next: identify the exact optional config path and preserve real
read/parse failures when fixing unavailable search locations.

For physical diagnosis, configure `-DLAUNCHER_BOOT_TRACE=ON -DDEBUG=ON` in a
separate build directory. It retains ten recent GS/EE-serial messages and stops
on errors. The default build is unchanged. Optional
`-DLAUNCHER_BOOT_TRACE_RECOVERY_ELF=mc0:/ps2link/PS2LINK.ELF` attempts relaunch
after 15 seconds, but reliable soft recovery has not been established; use the
user's automatic ps2link boot setup after a physical reboot if needed.
The inventory fixture also accepts `--inspect-config VCD_DIRECTORY GAME_BASE`
to exercise production configuration discovery without replacing ps2link's IOP.

Host regression subsequently confirmed that an unavailable optional global
memory-card root (`ENODEV`/`ENXIO` at open) aborts configuration discovery.
The fix treats those failed global opens like an absent optional file, while
preserving permission failures, selected-title device failures, malformed
configuration and every read failure after a successful open (including a
device removed during reading). Nine feature tests pass with injected open
and post-open read failures; the 57 external tests and both normal/trace target
builds pass. Hardware acceptance of this fix is pending: runs
`20261014T061522-0031` and `20261014T062342-0032` returned no console stdout.
Do not infer game boot or successful configuration parsing from them.
Physical run `20261014T075656-0033` subsequently confirmed that the global-card
fix works. It reaches the absent ATA PATCHES.TXT and fails with errno 4: the
stock BDM FatFs driver returns raw FRESULT values instead of errno. See
`docs/evidence/pops_ata_configuration_errno_console.json`. The next correction
belongs in the driver, preserving real I/O errors. A licensed source baseline
and exact dependency identities are saved in `launcher/iop/pops_fatfs/`;
this checkpoint is unintegrated. The new PSXCore reference is also unlinked.

The source-level FatFs correction now builds and is selected for both initial
preflight and post-Sony-reset I/O. It translates FRESULT to negative errno,
preserves read/write/readdir errors, and makes exclusive create win over
truncate/append. FatFs is fetched from the exact hash-pinned archive documented
in the module README; no SDK source checkout is required.

Physical run `20261014T121822-0034` passes production configuration discovery
with `POPS_CONFIG result=0` and exit 0. Missing ATA configs now report ENOENT.
Physical run `20261014T122201-0037` creates a fresh 8192-byte diagnostic file,
rejects an EXCL|TRUNC|APPEND collision with -EEXIST, and compares all bytes after
close/reopen with true EOF. Original games/saves remain untouched. Metadata is
in `pops_fatfs_configuration_console.json` and `pops_fatfs_exclusive_console.json`.
This is filesystem acceptance, not Sony gameplay or power-cycle persistence.
Runs 0035/0036 had no program result; a user reboot preceded passing run 0037.

All nine host suites (including the new production FatFs callback fixture) and
launcher argv regression pass; normal and persistent-trace GCC builds pass.
On Windows set TEMP/TMP to the existing workspace build/test-tmp directory;
the sandbox's default temp directory otherwise causes unrelated permission errors.
The next game diagnostic is `build/pops-boot-trace/release/launcHER.elf`, with
recovery disabled so the error screen remains visible. Its build predates this
documentation commit; use exact-head CI artifacts for distributable provenance.

The traced full launch with repaired FatFs reached the Sony IOP reset and then
failed loading stock SDK mcman with -200 (`20261014T122341-0038`). Static ABI
inspection identifies Sony SIO2 2.3 versus stock mcman's SIO2 1.2 imports;
multitap changed from ordinal 55 to 57. The SDK's mcman-2000 explicitly targets
SIO2 2.3 and exports mcman 2.3 for the existing mcserv. The candidate selects
mcman-2000 and loads its secrman 1.4 dependency only in the Sony path.
Normal launcher/Ember module selection is unchanged.

Reproduce the metadata-only ABI inspection with
`python tools/inspect_pops_card_abi.py --elf EXTERNAL/POPS.ELF --launcher-build BUILD`.
See `docs/evidence/pops_card_service_abi.json`. Do not fix this by simply
rewriting an import version: the multitap ordinal also changes.
Candidate run `20261014T123524-0039` was uploaded/launched but the final console
capture was black, with no explicit acceptance marker. It proves neither full
service initialization nor game boot. The error and candidate reports preserve
that distinction. Normal and diagnostic target builds pass, as do 57 external
host tests. The FatFs commit c48e087 has all four GitHub CI runs passing.

An additional opt-in diagnostic
`-DLAUNCHER_BOOT_TRACE=ON -DLAUNCHER_BOOT_TRACE_STOP_BEFORE_HANDOFF=ON`
stops only after production service initialization, live disc/card checks and
trampoline preparation. It displays `POPS_PREFLIGHT_PASS` and explicitly says
Sony entry has not executed. This option defaults OFF; disable it for gameplay.
The current local trace build enables this stop and disables soft recovery.
Physical run `20261014T134640-0040` now displays
`POPS_PREFLIGHT_PASS Sony_entry_not_executed=1`. Thus the complete production
preflight passed with the actual Sony IOP reset and ATA disc/VMC route. The rig
reports hang because the reset removes ps2link; acceptance is the persistent GS
marker. See `docs/evidence/pops_production_preflight_console.json`.
Sony EE entry was deliberately not executed. The unchanged production
trampoline subsequently passed with an owned child in isolated PCSX2 and on
physical PS2 (`20261014T135833-0041`, exit 0). The child receives argc=1 and
`pops0:IMAGE.VCD` through the actual kernel ExecPS2 path. This does not execute
Sony startup or reproduce every post-reset EE lifetime condition. No speculative
interrupt change was made. See `docs/evidence/pops_owned_trampoline_probe.json`.

Reproduce with `prepare_pops_trampoline_probe.py --out build/FRESH --linkfile
SDK_STARTUP_EE_LINKFILE`, then [ps2build](https://ps2build.dev/) GCC. Validate `--verify-parent` before
running: its full load/BSS must fit 0x100000..0x200000, disjoint from destination
and staging. The embedded child is stripped to avoid spilling the parent into
the child destination. The isolated runner accepts `-ResultPrefix POPS_TRAMPOLINE`.
The next boundary is Sony's early startup/runtime calls; full game boot remains
unverified. Existing entry/argument code is not changed on the basis of a black screen.

The original startup parser prefix now also executes in isolated PCSX2 and on
physical PS2 (`20261014T205627-0043`, exit 0), using the original R5900 string
routine and character table. The current `pops0:IMAGE.VCD` produces name `VCD`
and route `pops0:IMAGE.VCD`; `hdd0:PART:pfs0:/POPS/Tekken.VCD` produces name
`VCD` and route `hdd0:PART`. Missing colon/extension produces empty fields.
The fixture asserts all five measured outputs plus argc=0. Initial helper is
modeled and the probe stops before runtime initialization, so this does not
prove later mount/file-service acceptance. Metadata:
`docs/evidence/pops_original_startup_args.json`.

Reproduce with `prepare_pops_startup_args_probe.py --elf EXTERNAL/POPS.ELF
--out build/FRESH`, native ps2build GCC, then `--verify-probe` before execution.
The isolated runner accepts `-ResultPrefix POPS_STARTUP_ARGS`. Generated original
arrays and ELFs remain local. Six host guard tests pass, including identity,
file bounds and full load/BSS overlap checks. Run 0042 had no program result;
only run 0043 is hardware parser acceptance.

The earlier read-only configuration probe is
`build/pops-device-config-v13/gcc/bin/inventory.elf` with ELF arguments
`--inspect-config ata0:/LAUNCHER-TEST-20261013-A/ TEST`.

### Next original startup boundary: read-only callsite census

The original parser has passed hardware acceptance, but the next runtime
initialization stage is not yet isolated. Run this **offline** against the
same user-supplied hash-pinned Sony ELF:

```sh
python tools/inspect_pops_startup_calls.py --elf EXTERNAL/POPS.ELF \
  --json build/pops-startup-calls.json
python tools/test_pops_startup_calls.py
```

The original function inventory in REPOP places
`FUN_002004f0` at `0x002004f0..0x00200924` (1,076 bytes). The
hardware-executed parser probe covered only the first 524 bytes through
`0x002006fc`. The inspector defaults to that observed prefix. To statically
census the whole function and annotate direct targets with candidate
original Ghidra function ranges, run:

```sh
python tools/inspect_pops_startup_calls.py --elf EXTERNAL/POPS.ELF --whole-function --functions ../REPOP/pops/ghidra/output/functions.json --json build/pops-startup-calls-full.json
```

Ghidra intervals may overlap, and all candidates remain visible rather
than guessing a unique callee. The second half has not been demonstrated
on hardware. REPOP previously misidentified this address as a SIF RPC
dispatcher; that unsupported attribution is corrected in its source
provenance notes.

The tool emits only direct MIPS J/JAL and conditional-link targets and marks
JALR as unresolved, across the bounded original `0x002004f0..0x002006fc`
prefix. It requires the complete known external ELF digest and a unique
executable segment covering that region. The report records a digest of the
inspected range but no original Sony instruction bytes or generated ELF.
The caller must cross-reference candidate targets with REPOP function
boundaries before deciding what to model or trace. **This is not a dynamic
call graph**: embedded data, unreachable instructions, delay slots and
indirect targets remain limitations. It does not justify mutating POPS
startup, disabling interrupts or changing the verified launcher arguments.

## Current local continuation — October 13, 2026

Local development was fast-forwarded to PR #23 head
`472ae61a2f69d9f8eec7b8f3d9b77a4dc074b760`; pre-existing untracked scratch
files were preserved. Continue committing and pushing on this same PR branch.

The archived MAIN decoder now ran successfully. Its complete output also
matches an independent liblzma decode. Eleven embedded IOP modules validate,
including the actual 2,484-byte `PFS Wrapper r6a`. Sony's selected IOPCD is
embedded in POPS.ELF, **not** a ROMDIR entry in the loose IOPRP252 image.
Read `docs/POPS_IO_CONTRACT.md` for identities, locations and reproduction.
The self-contained `tools/trace_original_pops_io.py` now executes the original
IOPCD and wrapper with controlled imported services: 26 cases pass, including
TOC reads, aligned sector requests, descriptor zero, errors and close behavior.
The metadata-only trace is committed under `docs/evidence/`. The wrapper forwards
raw file-byte offsets; Sony IOPCD aligns the caller's supplied byte offset.
Production diagnostics now hash and inspect the **core-embedded** IOPCD before
patching/reset, and the POPFS host fixture replays the observed read/seek tuples.
Local validation passed: 56 external-core tests plus all three real dependency
sets, POPFS, VMC, 64 supported/192 unsupported mode masks, launch arguments and
eight feature tests. The feature assertion now uses host `errno.ENOTSUP`
instead of a Linux-only numeric value, so it also runs on Windows.
The existing GCC PS2SDK Docker compile/link/pack also passed; it still reports
pre-existing path-truncation warnings. Exact-head GitHub CI supersedes local
dirty-checkout artifact identities.

The original EE producer `FUN_00210090` now also ran unchanged in PCSX2:
seven cases pass with both GCC and LLVM harnesses. It constructs
`byte_offset = 0x100000 + LBA * 2352`, caps requests at 16 sectors, handles
disc-end counts and cache hits, and rejects mismatched reply counts. Five
observed EE tuples are replayed in the IOP probe. Preparation, overlap checks,
isolated runner and metadata-only GCC/LLVM reports are all committed; no
original-byte probe ELF/C array is distributed. Three synthetic input/layout
guard tests are also in CI. See `docs/POPS_IO_CONTRACT.md` for exact reproduction.

The actual Sony IOP image and SIF RPC binding probe now passes in isolated
PCSX2 with the production iomanX/fileXio/POPFS modules and original IOPCD.
It exposed a production startup error: MODLOAD supplies `LBbyEE` at argv[0],
so POPFS must read its packed mode from argv[1]. The host fixture now models
that real loader contract. Proxy argument packets are also limited to the
SDK LOADFILE RPC's 252 bytes; larger configurations fail before side effects
instead of being silently truncated. The 57 external-core tests and updated
POPFS contracts pass. The real-kernel probe also checks both card aliases with
different direct/bridged write patterns and close/reopen byte verification on
controlled IOP memory. This does not establish physical-media persistence.

Next: one end-to-end device boot and VMC save/reload/power-cycle test, plus
full runtime patch/parity acceptance. Do not introduce a second VCD offset
remap. See `docs/POPS_IO_CONTRACT.md` for the real-kernel probe and an important
PCSX2 descriptor-1 console interception caveat.

Physical-console continuation: the user enabled ps2link. The native original EE
request probe passed all seven cases in ps2rig run `20261013T181122-0001`
with `[ps2rig] exit=0`. This is actual R5900 hardware execution with modeled
imported services, not a full POPS boot or save test. The source now prints rig
exit markers and the metadata-only console result is committed. Continue with
real IOP-kernel/RPC binding; a custom IOP reset removes ps2link services, so
validate the foreign-image probe in isolated PCSX2 before console deployment.

The older sections below are historical checkpoints, not current acceptance.

Hardware binding attempt `20261014T004047-0013` subsequently rebooted into
Sony's image and displayed successful iomanX/fileXio/backend module returns
on the physical capture. It stopped at `load=production-popfs`, without a
return status or PASS/FAIL marker. This hardware boundary remains unresolved;
the emulator pass must not be substituted for it. The metadata-only attempt
is committed under `docs/evidence/original_pops_iop_console_attempt.json`.
The user authorized selecting any installed VCD and restarted ps2link.
A read-only inventory loaded production USB/MMCE stacks and observed two USB
disks mounted by BDM/FatFs, but no completed directory/game selection yet.

The startup watchdog now pinpointed the physical stall: run
`20261014T010845-0017` repeatedly showed POPFS device-check index 0 with
pointer `0x00000003`. Sony IOMAN 2.03 uses linked device nodes where the SDK
legacy hook expects an array; the hook copies file flags as device pointers.
Both 252 profiles share that module; the 2305A profile has the older flat
2.01 layout. A separate SDK-derived `pops_iomanx` candidate now validates and
migrates both layouts and all 32 descriptors. Host regressions and the
controlled PCSX2 bridge pass with only iomanX replaced. It remains a candidate,
not selected by production yet. Next: compare on hardware using unchanged
production POPFS and original IOPCD, then integrate only in Sony post-reset
initialization if that passes. The prepared local hardware comparison is
`build/pops-iomanx-candidate-console/gcc/bin/pops_iop_binding_probe.elf`.

Branch: `codex/popstarter-replacement`, based on `EMBER` and including merged
OPL argument compatibility PR #19 (`c616e0cdccc2af24fd2e4e956fff167f822da4bf`).
This branch is unfinished development. Do not merge or publish it as working
POPS support without completing the runtime and console validation.

## User's intended outcome

launcHER remains an application-invoked launcher without a GUI. Support external
Ember and external Sony POPS from one launcher. Replace POPSTARTER's setup,
patching and runtime responsibilities with full parity and better direct device
support, without requiring BDMAssault. Do not implement a new POPS emulator or
include proprietary POPS, IOP images, extracted Sony IRXs or game payloads.

## Implemented

- `common/src/pops_external.c`: ELF/TROJAN/PATCH inspection, guarded payload
  staging and configuration intent. Native PAK decode in `pops_pak.c` uses pinned
  public-domain LZMA SDK files; input/output limits and truncation checks apply.
- `pops_iop_image.c`, `pops_profile.c`, `pops_boot_stage.c`: bounded ROMDIR checks,
  exact SHA256 reference identities and caller-owned core/IOP/BSS staging.
- `pops_core_patches.c`: six original core groups (36 writes) plus a storage
  bridge group (12 writes). All selected guards are checked before any writes;
  apply selected groups together to the identified unmodified core.
- `launcher/iop/popfs`: own compiled/embedded IOP filesystem proxy. Explicit
  backing paths for four discs and two cards; Sony disc/card/backup aliases map
  to these paths. Read-only discs, underlying errors, short I/O, descriptor zero,
  64-bit seeks, save-volume sync and handle lifetime have host coverage.
- `initPopsServices()` in `launcher/src/init.c`: post-reboot service helper.
  Identifies the unmodified core, loads its external Sony SIO2 module, reuses the
  selected backend module list while skipping SDK SIO2, then loads the proxy.
- `common/include/pops_bootstrap.h`, `common/src/pops_bootstrap.c`: defines memory
  layout boundaries, formats proxy argument strings, and initializes trampoline
  arguments with preserved argv string `"pops0:IMAGE.VCD"` in bram at `0x00084230`.
- `launcher/src/pops_trampoline.S`: position-independent MIPS trampoline executed
  at `0x00084000` in BIOS unused RAM (`bram`), below 1 MiB. Sets stack pointer to
  `0x0008fff0`, zeroes scratchpad, zeroes POPS BSS (`0x00502e60`..`0x00865940`),
  wipes launcHER low RAM (`0x00100000`..`0x00200000`), copies staged core from
  `0x01000000` to `0x00200000`, flushes caches via syscall `0x64`, and enters POPS
  via syscall 7 (`ExecPS2`).
- `launcher/include/handler_pops.h`, `launcher/src/handler_pops.c`: runtime caller
  integrated into `launchPath` and `handleQuickboot`. Identifies VCD targets,
  discovers external dependencies, sets up VMC files (formatting 128 KiB card if
  missing), stages core and IOPRP in high RAM (`0x01000000`), applies guarded core
  patches and TROJAN payloads, reboots IOP with verified external image via
  `SifIopRebootBuffer`, invokes `initPopsServices`, mounts PFS if APA, and transfers
  control to the trampoline.
- Host checks and PS2SDK build jobs are configured on the development branch.

## Next work and constraints

1. Test on real PS2 hardware and diverse storage backends (USB, internal HDD/APA,
   MX4SIO, MMCE).
2. Validate in-game VMC saving and persistence across console power cycles.
3. Validate multi-disc switching and additional TROJAN patch slots.
4. Test IGR and clean console poweroff. The retained Sony poweroff thread calls
   HDD/DEV9 services, so direct-storage shutdown needs separate handling.
5. Audit module lifetimes and SIF RPC re-initialization during repeated launches.

Sony POPS binds FILEIO RPC `0x80000001`; installed SDK fileXio uses
`0x0b0b0b00`, so a same-ID conflict was not established. SDK iomanX's legacy hook
bridges old imports, including stat conversion. Verify its layout assumptions
and behavior with the external Sony IOMAN. Modern fileXio is not a replacement
for Sony's FILEIO protocol.

The storage group preserves delay slots, skips Sony DEV9/ATAD/HDD/PFS loads,
bypasses only two partition-mount calls (retaining poweroff thread setup), and
redirects eight fixed `pfs0`/`pfs1` prefixes to `pops`. Backing volumes must
already be prepared; their identity comes from explicit paths. Never interpret
`massN` as USB identity or invent a missing APA partition.

## Evidence and reproduction

Current local checks pass:

```text
python tools/test_launch_args.py
python tools/test_popfs.py
python tools/test_pops_external.py --elf C:/Users/natha/Github/POPS/POPS.ELF --iop-image C:/Users/natha/Github/POPS/IOPRP252.IMG
```

Earlier full external checks passed 4,820 corpus files plus two root specimens,
both PAK variants, loose ELF/IOP dependencies, independent decompression and
36-write original-source whole-buffer comparison. The final SIO2-skip addition
was checked against the loose dependency set in this handoff; rerun both PAK
variants and source parity using the commands in `POPSTARTER_REPLACEMENT.md`.

Latest local PS2SDK compile/link/pack passed with the cached image
`ghcr.io/ps2homebrew/ps2homebrew:main`, image ID
`sha256:1037f40df12cf2d1875dcfdc368ed7f70feb0eff186498c4e10ff874ef531a1b`.
Artifact `build/pops-ps2sdk/release/launcHER.elf`: 213,924 bytes; SHA256
`1b8b262b0ec02d88f9a1985f2e1fb899b27aa498d856587fb9a0d3beaa93b914`.
Build output includes filesystem clock-skew and format truncation warnings.
This is target build evidence, not a console result. Build output is ignored
and is not committed.

External references are read-only, not dependencies to distribute:

- `C:/Users/natha/Github/POPS/build/parity/popstarter/decompiled.c`: measured
  clean R5900 original loader exports.
- `C:/Users/natha/Github/POPS/build/parity/pops/decompiled.c`: measured Sony core;
  inspect FUN_002002a0, FUN_002004f0, FUN_00210540, FUN_0020cf00, FUN_00214938.
- `C:/Users/natha/Github/POPS/popstarter/PFS_WRAP.BIN`: original proxy reference.
- `C:/Users/natha/Github/REPOP/popstarter`: external patch corpus. Older REPOP
  reconstruction has wrong patch labels/widths and speculative filesystem/VCD
  code; use the measured original exports instead.

Read `docs/POPSTARTER_REPLACEMENT.md` for detailed hashes, dependency sets,
module ranges, capability gaps and validation boundaries. GitHub CLI's default
saved token is stale, but Git credential manager successfully authenticated Git
push and GitHub operations for PR #19. Never print credentials in logs.

## Current continuation checkpoint (2026-10-09)

The published boot repair is `16aa41cc24806bf00a0259be3c6d4f18afa33d0a`.
Its GitHub Actions run 37938178727 passed host checks and PS2 target packaging.
The older local artifact/hash above is historical, not the current artifact.

The next repair protects existing VMCs, formats new raw cards, checks both card
results, separates title configuration/fixes from save redirection, and rejects
enabled cheats before the unsafe staged-core write. The resident cheat engine
is still missing. See the revised capability matrix and repair checkpoint in
`POPSTARTER_REPLACEMENT.md`; earlier component descriptions are not parity proof.

Original PATCH loader evidence begins near line 3206 in the measured POPSTARTER
decompile: numbered PATCH files use a 64-byte header and additional original
validation/dispatch, separate from TROJAN handling near line 2822. Reconstruct
these rules before connecting the generic container stager to runtime discovery.

Compatibility continuation: Modes 1..5 and 7 now use guarded measured writes
from FUN_008dc2c4, verified against complete external-core buffers for every
supported mask. Modes 6/8 reject without mutation. Trace original DAT_009b9d48
state/caller ordering and Mode 6 OSD globals next; do not reuse speculative
`POPS/popstarter/src/runtime_hooks.c` mode switches (they were the source of the
incorrect single-write implementations). Optional reference reproduction is in
`POPSTARTER_REPLACEMENT.md`. No new hardware result has been obtained.

## POPS early startup sequence and storage bridge census (2026-10-16)

Static whole-function callsite census on original `FUN_002004f0`
(`0x002004f0..0x00200924`) against `POPS.ELF` and REPOP Ghidra functions
(`build/pops-startup-calls-full.json`) establishes the core sequence:

1. `FUN_002004f0`: Validates arguments, extracts title identity and partition route.
2. `FUN_002149e0()`: Performs pre-mount hardware initialization.
3. `FUN_002002a0(1)`: Embedded IRX loader. `FUN_002003d8` branches around Sony's
   DEV9/ATAD/HDD/PFS loading when non-HDD paths are active.
4. `FUN_00214938()`: Mounts partitions. `0x00214968` mounts `hdd0:__common` as
   `pfs1:`, and `0x002149a0` mounts the title partition as `pfs0:`.
   `POPS_CORE_STORAGE_BRIDGE` NOPs both partition mounts and redirects literal
   `pfs0:` and `pfs1:` path references to `pops:`.
5. `FUN_00210540()`: Binds IOPCD RPC `0x435052` and retrieves the disc TOC.
6. `FUN_0020cf00(1)`: Sets up memory card handling.

POPStarter decompilation confirms that its main routine (`0x00874400..0x00874ce8`)
directly executes these patch groups before jumping to the core entrypoint:
- `FUN_008dc2c4`: Patch dispatcher.
- `FUN_008db778`: HDD check bypass.
- `FUN_008db7e4`: PFS and file path redirection.
- `FUN_008dbafc`: Exception breakpoints.
- `FUN_008dbd6c`: Disc string rewrite.
- `FUN_008dbfd4`: SifLoadModule error bypass.

