# Handoff defect: static analysis

Analysis report. Copied as written.
`<scratch>` paths point at a temporary folder that no longer exists; `<workspace>` is the folder that holds the checkouts. Nothing here was run on a console unless it says so.

## summary

Static verification only (binaries + source; no emulator run by me, no console, no repository change, nothing committed; worktree the handoff worktree still clean at cfebe01). NOT TESTED on a console.

Result in one paragraph: the four-word overwrite the probe saw at 0x206360/70/80/90 is real EE-kernel ROM code (SCPH-39001 rom0 KERNEL), not an emulator artefact. ExecPS2 (syscall 7) terminates every other thread, and the kernel's thread-reset routine at 0x80003bb8 rewrites the terminated thread's initial context (gp, sp, fp, ra) into the top of that thread's stack. launcHER has exactly one extra thread (ps2sdk libkernel 'topThread', 0x400-byte static BSS stack); in both 2026-11-11 builds that stack is linked above 0x200000, so the kernel stores land inside the POPS core that the trampoline has just copied to 0x200000. In every packed artifact I could unpack from 2026-09-27 through 2026-10-30 (19 files, including build/run-tekken-fix and build/hw*-20261030) the image ended below 0x200000 and the stack was at 0x19xxxx..0x1fxxxx, so the same stores landed in the 0x100000..0x200000 area instead of POPS text. POPStarter r13 cannot have this problem: it contains no CreateThread/StartThread syscall stub at all (single thread, old ps2sdk libkernel), sits at 0x870000+, loads POPS.ELF directly to its final address, and enters POPS with a raw syscall-7 ExecPS2 while still running from its own intact code.

A second, separate defect is statically supported: the trampoline zeroes 0x100000..0x200000 (launcHER's text, including its registered INTC 11 timer handler and DMAC 5 SIF handler) with interrupts enabled and the handlers still registered. That has been so since the first trampoline commit (b137e2b, 2026-10-08), so it is not new; only the stack crossing is new. The probe's pre-ExecPS2 kernel dump is consistent with an interrupt entering zeroed handler code and sliding into 0x200000 (mechanism INFERRED).

Scratch files are under <scratch>/handoff-vstat/ . Note: build-pr23 was rebuilt by someone else at 2026-11-11 09:22 during my session; release-build addresses below are for that rebuild.

## confirmed

1. **claim:** B. The kernel rewrites a terminated thread's initial context into its stack: four 32-bit stores at stack+size-0xe0 (gp), -0xd0 (sp), -0xc0 (fp), -0xb0 (ra = thread 'root').  
   **evidence:** Disassembly of KERNEL extracted from SCPH-39001 rom0 (flat at 0x80000000). Routine 0x80003bb8: ctx = tcb.stack(+0x3c) + tcb.stackSize(+0x40) - 0x2a0; tcb.entry = tcb.entry_; tcb.stack_res = ctx; sw root,0x1f0(ctx); curPri = initPri; status = 0x10 (DORMANT); sw gpReg,0x1c0(ctx); sw (stack+size-0x20),0x1e0(ctx); sw (stack+size-0x20),0x1d0(ctx). Called from iTerminateThread 0x80003e00 (status jump table at 0x80015900) and from the ExitThread path 0x80004020. CreateThread 0x80003c50 and SetupThread 0x80005198 write the same four slots at creation.
2. **claim:** B. The probe's numbers are exactly what that code produces for launcHER's trace build.  
   **evidence:** build-pr23-trace/launcher/launcher_unc.elf: the only 'jal CreateThread' (0x12ab74, in libkernel InitThread 0x12ab00) passes func=topThread 0x12aa38, stack=0x206040 (BSS symbol 'stack'), stack_size=0x400, gp=_gp 0x203670, priority 0. top = 0x206440: top-0xe0 = 0x206360 <- gp 0x203670; top-0xd0 = 0x206370 <- 0x206420; top-0xc0 = 0x206380 <- 0x206420; top-0xb0 = 0x206390 <- root. The probe's dump shows root for that thread = 0x12c1c0 = ExitThread in the same ELF. Matches REPORT.md's 0x203670 / 0x206420 / 0x206420 / 0x12c1c0 word for word (the addresses are computed by me; the overwritten values were observed by the probe in the emulator).
3. **claim:** B. ExecPS2 (syscall 7) is what triggers it: it terminates and deletes every thread except the caller.  
   **evidence:** Syscall 7 handler 0x80002f80 -> worker 0x800057e8: cur = *(0x8001536c); loop tid 1..255 over the 0x4c-byte TCBs at 0x8001a480: skip status 0 and the current thread; if status == 0x10 (DORMANT) call 0x80003f00 (delete) only; otherwise jal 0x80003e00 (iTerminateThread, which calls the reset at 0x80003bb8) then 0x80003f00. So a thread that is already DORMANT or deleted when ExecPS2 runs gets no stack write; a live (WAIT/READY) one does.
4. **claim:** B. What else ExecPS2 resets (same ROM): all semaphores, all INTC handler lists except SBUS, all DMAC handler lists, INTC mask, timers T0-T3, alarms, GS, FPU, scratch folder; it prints '# Restart Without Memory Clear.'  
   **evidence:** 0x800057e8 calls 0x80004e68 (re-inits all 256 semaphores), 0x800021b0 (INTC causes 0..14 except 1: list heads at 0x80018cd8+12*i emptied, low-level dispatch reset; DMAC 0..15: heads at 0x80018d90+12*i emptied; handler-node pool at 0x80018e58 rebuilt), then 0x8000da90: GS init, INTC init 0x8000e3f8(0xdffd), timer init 0x8000e428 (T0/T1 mode 0xc00, T2 0xc80, T3 0xc83; alarm table of 64 slots cleared), ResetEE(0x7f) 0x8000d798 (DMAC init covers channels 0-4,8,9 only; SIF channels 5,6,7 are not reset there), FPU init, scratch folder zero 0x70000000..0x70004000. I found no code resetting the syscall table.
5. **claim:** B. Emulator dumps agree with the ROM reading (emulator data, read statically).  
   **evidence:** Post-ExecPS2 dump runs/20261111T064051-lh-interp-pin/ee_80000000_80000.bin: launcHER's tid 2 is gone, INTC 11 list empty, DMAC 5 holds POPS's own handler 0x236ef8 (gp 0x50a670), tid 1 entry_ = 0x200008. Pre-ExecPS2 dump runs/20261111T062956-lh-loose-rec-kernel/ee_80000000_80000.bin: tid 2 status 4 (WAIT) entry_ 0x12aa38 stack 0x206040 size 0x400 gp 0x203670 root 0x12c1c0; INTC 11 node handler 0x135800 (TimerHandler_callback) gp 0x203670; DMAC 5 node handler 0x12c070 (_SifCmdIntHandler); sys[0x5a] = 0x0012b040 (launcHER kCopy).
6. **claim:** C. Threads alive at handoff: exactly two. Main thread stack is at the top of RAM, outside every region the trampoline or POPS touch; topThread's stack is static BSS inside the POPS image range in both current builds.  
   **evidence:** crt0 calls SetupThread(gp, stack=-1, size=0x20000, ...); kernel SetupThread 0x80005198 computes stack = GetMemorySize() - 0x1000 - size => 0x01fdf000..0x01fff000 on 32 MB (computed from the ROM formula). There is one CreateThread syscall stub and one caller of it in each image. Trace build: topThread stack 0x206040..0x206440. Release build as rebuilt 2026-11-11 09:22 (build-pr23/launcher/launcher.elf unpacked on the host and build-pr23/launcher/launcher_unc.elf headers): CreateThread caller 0x129804, func 0x1296c8, stack 0x202980, size 0x400, gp 0x2009f0 => kernel stores at 0x202ca0 / 0x202cb0 / 0x202cc0 / 0x202cd0 (computed, not observed); image end 0x20e7a0. POPS.ELF's RX PT_LOAD is 0x200000..0x249808, so both sets of addresses are inside POPS text.
7. **claim:** C. Interrupt-side state launcHER leaves registered when it jumps to the trampoline.  
   **evidence:** Trace ELF disassembly: InitTimer 0x1354c0 is the only AddIntcHandler caller: AddIntcHandler2(11 /*INTC_TIM2*/, TimerHandler_callback 0x135800), T2 mode |= 0x300, EnableIntc(11). sceSifInitCmd 0x12b348 is the only AddDmacHandler caller (DMAC 5, _SifCmdIntHandler 0x12c070). InitAlarm 0x101b00 copies a blob to kernel 0x80076000, another to low user RAM 0x00082000 (its size was not read), and sets syscalls 0x5a (to user-space kCopy 0x12b040) and 0x5b. InitExecPS2 0x12ac78 / InitTLBFunctions 0x12ad60 patch kernel memory. launcher/src/handler_pops.c copies the trampoline to 0x00084000, FlushCache(0/2), and calls it directly from the main thread; launcher/src/pops_trampoline.S contains no DI, no handler removal and no thread cleanup.
8. **claim:** C. What ps2sdk (as linked) offers to undo each item.  
   **evidence:** In the trace ELF: TerminateLibrary 0x12bd70 = _ps2sdk_deinit_timer (StopTimerSystemTime 0x135770; EndTimer 0x135600 = DIntr, RemoveIntcHandler(11,id), DisableIntc(11), T2 mode 0xc00) followed by InitTLB. The ps2sdk ExecPS2 wrapper 0x12af98 = SetArg, TerminateLibrary, _ExecPS2 (launcHER's trampoline bypasses it with a raw syscall 7, so none of that runs on the POPS path). sceSifExitRpc 0x129df0 / sceSifExitCmd 0x12b5e8 remove the DMAC 5 handler. Threads: TerminateThread / DeleteThread syscalls; the topThread id is a libkernel static (stored at 0x20603c in the trace build), not exported.
9. **claim:** C. Layout history: the image crossed 0x200000 only after 2026-10-30. Every older packed artifact has the topThread stack below 0x200000.  
   **evidence:** Host LZMA unpack of the ps2-packer images (layout_history.py; validated on the current release build against launcher_unc.elf's PT_LOAD end 0x20e7a0). End of image / topThread stack: build/launcher 09-27 0x19c861 / 0x190e40; pr23-f92ad1d-ci 10-13 0x1b7660 / 0x1ab840; pr23-4dd2187-ci 10-14 0x1ce960 / 0x1c2b40; dependency-only-dc88150 10-20 0x1f8320 / 0x1ec900; build-trace/bootstrap 10-27 0x1fb1a0 / 0x1ef380; run-40546837239 0x1f8220 / 0x1ec400; boot-trace-v13 0x1fb420 / 0x1ef600; run-mode6-fix 0x1f8520 / 0x1ec700; run-tekken-fix 10-27 12:44 0x1f86a0 / 0x1ec880 (kernel stores would be 0x1ecba0..0x1ecbd0); run-igr-fix 0x1f8620 / 0x1ec800; run-igr-direct 0x1f88a0 / 0x1eca80; artifact_latest 0x1f8b20 / 0x1ecd00; artifact_latest boot-trace 0x1fbe20 / 0x1f0000; artifact_commit_aaf0dea 0x1f8ca0 / 0x1ece80; hw-20261030 0x1fcca0 / 0x1f0e80; hw2-20261030 0x1fd3a0 / 0x1f1580; build-hwtrace 10-30 10:38 0x1fd7a0 / 0x1f1980 (symbols: _gp 0x1f0a70, stack 0x1f1980, _end 0x1fd7a0). Then 11-11: build-pr23 0x20e7a0 / 0x202980 and build-pr23-trace 0x211e60 / 0x206040. Headroom on 10-30 was only 0x2860..0x2c60 bytes.
10. **claim:** C. The trampoline has zeroed 0x100000..0x200000 with interrupts enabled since its first commit.  
   **evidence:** git show b137e2b:launcher/src/pops_trampoline.S (2026-10-08) already has '3. Zero low RAM: 0x00100000 to 0x00200000 (clears launcHER)' followed by the core copy and raw syscall 7; the only later change (de0d50c, 2026-11-02) widened the scratch folder and BSS clears.
11. **claim:** A. POPStarter r13 is single-threaded and links an old libkernel without alarm/timer/topThread.  
   **evidence:** Unpacked r13 image (1,350,828 bytes at 0x870000, gp 0x9b68f0, via tools/trace_original_pops_io.py:decode_main). Scan of all 'li v1,N; syscall' stubs (0x91aa70..0x91abc0, 0x91cb78.., 0x91ceb0..0x91cff0, 0x91d5d0/e0): no stub for syscall 32 (CreateThread) or 34 (StartThread). crt0 at 0x870000: BSS clear 0x9b9d00..0x9ccac0; SetupThread(gp 0x9b68f0, stack -1, size 0x20000, args 0x9bba80, root 0x870144) => stack 0x01fdf000..0x01fff000 by the kernel formula; SetupHeap(0x9ccac0,-1); FlushCache(0); then only InitExecPS2 0x91ca48 (blob to 0x80074000) and InitTLBFunctions 0x91cbf8 (blob to 0x80075000). Only AddIntcHandler caller: 0x91a908, AddIntcHandler(10 /*INTC_TIM1*/, 0x91a868) with T1_MODE 0x282; only AddDmacHandler caller: 0x91ae60 (SifInitCmd).
12. **claim:** A. r13 does not copy the POPS core at handoff; it reads POPS.ELF whole to 0x1ff000 so file offset 0x1000 lands at 0x200000, patches it in place, and never moves it.  
   **evidence:** 0x87dc50 memset(0x1ff000, 0, 0x30530c); 0x87dc84 / 0x87dcac read(fd, 0x1ff000, 0x303e60) via fileXio 0x9169b0 or fio 0x91bbb8. No memcpy to 0x200000 anywhere in the tail 0x87c054..0x87c1d8.
13. **claim:** A. r13's handlers stay registered up to ExecPS2 but always point into intact code.  
   **evidence:** The tail (see original_handoff_sequence) contains no RemoveIntcHandler / DisableIntc / timer stop / DI / TerminateThread / DeleteThread and does not use the ps2sdk ExecPS2 wrapper; the T1 handler 0x91a868 and the SIF cmd handler live at 0x87xxxx..0x91xxxx, above everything r13 clears (its clears stop exactly at 0x870000).

## refuted or changed

1. **claim:** The 0x206360..0x206390 overwrite could be an emulator artefact.  
   **evidence:** Refuted for this BIOS: the stores are instructions in the SCPH-39001 ROM kernel (0x80003bb8, reached from the ExecPS2 kill loop at 0x800057e8). Any machine executing that ROM performs them. Only the observation itself was made in an emulator.
2. **claim:** Leftover launcHER INTC/DMAC handlers survive ExecPS2 and could fire inside POPS.  
   **evidence:** Refuted: 0x800021b0 empties every INTC list except SBUS and every DMAC list and rebuilds the node pool during ExecPS2; the post-ExecPS2 dump shows INTC 11 empty and only POPS's handlers. The exposure is the window before the syscall, while the trampoline is destroying launcHER's code.
3. **claim:** POPStarter is unaffected simply because it is loaded above 0x870000.  
   **evidence:** Incomplete: r13 has no second thread at all (no CreateThread/StartThread stubs), so the kernel has no thread to reset. Its load address explains only why its interrupt handlers stay valid until ExecPS2.
4. **claim:** The handoff layout is unchanged from the builds reported working on a console.  
   **evidence:** Changed: all 19 unpacked artifacts dated 09-27..10-30 end below 0x200000 with the topThread stack at 0x190e40..0x1f1980; both 11-11 builds end above 0x200000 with the stack at 0x202980 (release) / 0x206040 (trace). The crossing happened somewhere between 2026-10-30 10:38 and 2026-11-11 (exact commit not determined; no intermediate artifact).
5. **claim:** My own earlier release-build figures (stack 0x202700, kernel stores 0x202a20..0x202a50, _end 0x20e520).  
   **evidence:** Superseded: build-pr23 was rebuilt at 2026-11-11 09:22 while I worked. Current release figures are stack 0x202980, stores 0x202ca0/0x202cb0/0x202cc0/0x202cd0, end 0x20e7a0. Any author quoting release addresses must re-read the ELF it actually tests.
6. **claim:** Symbols for the PR build are in build-pr23*/launcher/launcher.elf.  
   **evidence:** Changed: launcher.elf / launcHER.elf are ps2-packer LZMA images (one PT_LOAD at 0x01cb6700, stub entry 0x01d0001c); the linked image with symbols is launcher_unc.elf (trace build only; the release one is stripped).
7. **claim:** The interrupt-enabled destruction of launcHER's handler code is a new regression.  
   **evidence:** Changed: it has been present since b137e2b (2026-10-08). It is a latent defect that also existed in the October builds; only the thread-stack overlap is new with the image growth.
8. **claim:** launcHER enters POPS exactly as r13 does.  
   **evidence:** Differences measured: r13 passes entry 0x00200000 (launcHER 0x00200008; POPS.ELF has two nops at 0x200000/4, so equivalent), r13 passes argc=1 with its own main argv pointer (launcHER builds a 'pops0:IMAGE.VCD' argv; outside my scope, noted only), r13 zeroes the scratch folder from kernel mode, and r13 runs fioExit/SifExitRpc/SifInitRpc(0)/SifLoadFileInit/SifInitCmd/fioInit immediately before ExecPS2.

## still inferred

1. NOT TESTED on a console: nothing in this answer is a console result. Which artifact(s) the owner actually ran on hardware is not something I can measure; docs/PR23_CHECKPOINT_HISTORY.md only says the Tekken exit was confirmed on a console.
2. INFERRED: the recompiler-run crash mechanism (an INTC 11 or DMAC 5 interrupt entering zeroed handler code at 0x135800 / 0x12c070 and sliding through zeroed 0x1xxxxx into 0x200000). Supporting static evidence: in the pre-ExecPS2 dump the main TCB already carries POPS's SetupThread values (gp 0x0050a670, stack 0x01eff000 size 0x100000, root 0x002001d0) while entry_ is still launcHER's 0x100fe0, topThread is still alive and the core copy had reached only offset 0x90230, i.e. POPS's _start ran without ExecPS2. I did not trace the instruction path.
3. INFERRED: how often that interrupt window is hit on real hardware. T2 overflow period computed as 65536 / (147.456 MHz / 256) = about 114 ms; the trampoline's duration on a console was not measured. The same window existed in the October builds.
4. INFERRED: what the four stray words do to POPS on hardware in the release build (0x202ca0..0x202cd0 are inside POPS text; I did not disassemble what POPS has there). The emulator probe saw a Trap exception at 0x00206360 with the trace build.
5. INFERRED: in the October builds the same kernel stores landed at e.g. 0x1ecba0..0x1ecbd0 (run-tekken-fix), i.e. four non-zero words in POPS's zero-filled RW segment 0x100000..0x200000 after the trampoline had zeroed it. Whether POPS ever reads those addresses is unknown.
6. INFERRED: other BIOS revisions behave the same. Only SCPH-39001 rom0 was disassembled.
7. INFERRED: the user-mode TerminateThread (syscall 37) path performs the same reset as iTerminateThread 0x80003e00; I disassembled the i-variant and the ExecPS2 loop, not syscall 37's entry. Also not verified: that the ps2sdk symbols TerminateThread/DeleteThread in the linked ELF are plain syscall stubs, and that TerminateLibrary is declared in a public header (the symbol exists in the ELF).
8. INFERRED: libkernel behaviour was read from the linked ELF's disassembly; the matching ps2sdk source is not on this machine, so function names for stripped/static code (topThread purpose, InitAlarm blob contents, the blob at 0x00082000 and its size) are from symbols only.
9. INFERRED: the purpose of r13's SIF exit/re-init sequence before ExecPS2, of the 0x0010000C flag gating SetVCommonHandler(8, 0x80000280), and the contents of the argv strings r13 passes. The second libkernel copy at 0x99e47c..0x9a1e40 in r13 is probably an embedded ELF and was not analysed.
10. INFERRED: Status.EIE handling across ExecPS2 (whether a DI before syscall 7 would leave interrupts disabled in the new program) was not disassembled; POPS's crt0 was not checked for an EI.
11. UNKNOWN: the exact commit at which _end crossed 0x200000 (bracketed to 2026-10-30 10:38 .. 2026-11-11), and whether October builds also fail in the emulator's recompiler (I ran no emulator).

## fix recommendation

Goal: reach the raw ExecPS2 in the state r13 is in at 0x87c1cc: one thread, and no registered handler whose code has been destroyed. r13 gets that for free (no extra thread, code above 0x870000, core loaded in place); launcHER has to produce it explicitly, in handler_pops.c, while its own image is still intact, i.e. immediately before the memcpy of the trampoline / the jump to 0x00084000 and after the last DPRINTF, file I/O and RPC. None of this depends on where the linker puts 'stack'.

Recommended (A), in this order:
1. Remove every other thread, generically: self = GetThreadId(); for tid = 1..255 (the kernel's own loop bound): if tid != self, TerminateThread(tid) then DeleteThread(tid), ignoring errors. Measured basis: the ExecPS2 loop skips slots with status 0 and only deletes (no stack write) slots that are DORMANT, so after this the kernel writes nothing at ExecPS2. TerminateThread itself performs the four stores immediately, but at that moment they land in launcHER's own still-live BSS and are later overwritten by the zero/copy, which is harmless. This covers topThread today and any thread a future ps2sdk or launcHER feature adds. Verify in the disassembly that the calls end in 'li v1,37; syscall' / 'li v1,33; syscall' (not a libkernel wrapper that defers to topThread).
2. Stop launcHER's interrupt sources, using the same teardown ps2sdk's own ExecPS2 wrapper runs: TerminateLibrary() (= _ps2sdk_deinit_timer: StopTimerSystemTime, RemoveIntcHandler(11), DisableIntc(11), T2 stopped; then InitTLB). Nothing may call sleep/usleep/SetTimerAlarm afterwards.
3. Remove the SIF DMAC 5 handler: SifExitRpc() (sceSifExitRpc -> sceSifExitCmd -> RemoveDmacHandler). This is the first half of what r13 does at 0x87c170..0x87c178. Do not copy r13's re-init half (SifInitRpc/SifLoadFileInit/SifInitCmd/fioInit): in launcHER that would re-register a handler in code the trampoline is about to zero; r13 can afford it only because its code survives. No printf/DPRINTF after this point.
4. Keep the trampoline's raw syscall-7 ExecPS2 (that is what r13 uses; the ps2sdk wrapper is not used by r13 either).

Alternative (B), most robust to future growth because the kernel does the teardown itself: make the handoff two-stage. From intact launcHER code call raw ExecPS2(entry = 0x00084000 trampoline). The ROM kernel then kills all other threads (their stack writes land in launcHER memory that is about to be cleared anyway), empties all INTC/DMAC lists, stops the timers and alarms, and enters the trampoline as a single clean thread; ExecPS2 is 'Restart Without Memory Clear', so the trampoline code at 0x84000, its args at 0x84200 and the staged core at 0x01000000 survive. The trampoline then zeroes/copies and issues the second raw ExecPS2 into POPS exactly as now. Cost: two kernel restarts instead of one (a deviation from r13's single ExecPS2) and the trampoline must take its args from the fixed address rather than a0. This needs no knowledge of which threads or handlers exist.

Guards worth adding either way: (a) in trace builds, just before the jump, walk tids with ReferThreadStatus and log any thread other than the caller that is not deleted; (b) a host check on launcher_unc.elf that fails the build if the handoff path no longer contains the teardown calls. A linker-level fix alone (forcing 'stack' or _end below 0x200000) is not recommended: headroom was already down to about 0x2c60 bytes on 2026-10-30, it leaves four stray words in POPS's 0x100000..0x200000 segment, and it does nothing for the interrupt window.

I would not use DI in the trampoline as the primary measure: whether the EIE state carries through ExecPS2 into POPS was not verified, and r13 enters POPS with interrupts enabled.

Residual, low risk: syscall 0x5a still points at launcHER's user-space kCopy (0x12b040) after ExecPS2 until POPS's own libkernel overwrites it (seen overwritten in the post-ExecPS2 dump); ps2sdk has no teardown for the alarm/TLB kernel patches. All of the above is NOT TESTED on a console and was not run in the emulator by me.

## hardware relevance

What can be said: the thread-reset stores are code in the SCPH-39001 ROM kernel, and the stack address/size/gp come from the linked launcHER ELF. A console running that ROM and that ELF executes the same instructions with the same operands, so at ExecPS2 it will store gp/sp/fp/ra at top-0xe0/-0xd0/-0xc0/-0xb0 of topThread's stack: 0x206360..0x206390 in the trace build, 0x202ca0..0x202cd0 in the current release build, both inside POPS's text segment after the trampoline's copy. That is a deterministic consequence of ROM code, not a timing effect, so it does not depend on the emulator's CPU core.

What cannot be said: NOT TESTED on a console. I do not know which kernel revision the owner's console has (only SCPH-39001 was disassembled; other revisions are INFERRED to behave the same), what POPS does when those particular words are corrupted on hardware, or whether the release build fails visibly there. The interrupt-window defect is timing dependent: whether a T2 overflow or a SIF interrupt arrives while launcHER's handler code is zeroed depends on real execution speed and phase, which static analysis cannot give; the same window existed in the October builds that the owner reported working, so on hardware it evidently does not fail every launch (owner report, not my measurement). All kernel RAM dumps I read are emulator output produced by another author; the layout history comes from host-side unpacking of build artifacts. None of it is a console observation.

## original handoff sequence

POPStarter r13, unpacked image at EE 0x870000 (gp 0x9b68f0), main at 0x870b78 (frame 0x1630; argc saved at 0x10(fp), argv at 0x14(fp), stored once at 0x870b90). Single thread; main stack 0x01fdf000..0x01fff000 (SetupThread stack=-1, size 0x20000, kernel formula). POPS.ELF was read earlier in one piece to 0x1ff000 (memset 0x87dc50, read 0x87dc84/0x87dcac), so the core is already at 0x200000 and is never copied at handoff. Last IOP reset is long before the tail (SifIopReset 'rom0:UDNL ' 0x87a78c, sync 0x87a7a8, second reset 0x87a7f4/0x87a810, raw SIF reboot with image 0x87a8dc..0x87a9e0, SifIopSync 0x87aa7c), followed by module loads.

Tail, in order:
0x87c054 SifExecModuleBuffer(0x91f680 'PFS Wrapper r6a', size gp[0x2890]) - last IOP/file-side action (result printed at 0x87c074)
0x87c08c memset(0x91f680, 0, gp[0x2890]); gp[0x2890] = 0; result <= 0 -> failure path 0x8709f8
0x87c0ac if gp[0x38b0] != 1 and gp[0x3858] != 1: delay_spin 0x87098c
0x87c0d4..0x87c0e8 mfc0 Status; Status &= ~0x18; mtc0 Status (enter kernel mode)
0x87c0f8 memset(0x70000000, 0, 0x4000) (whole scratch folder)
0x87c100..0x87c118 Status = (Status & ~0x18) | 0x10 (back to user mode)
0x87c130 memset(0x00502e60, 0, 0x0036d1a0) (POPS BSS up to exactly 0x870000)
0x87c140 memset(0x00100000, 0, 0x00100000)
0x87c158 memset(0x00972390, 0, gp[0x28e0]) (own staging buffer)
0x87c160 FlushCache(0); 0x87c168 FlushCache(2)
0x87c170 fioExit (0x91ba18)
0x87c178 SifExitRpc (0x91b7c0 -> SifExitCmd 0x91af48: DisableDmac(5), RemoveDmacHandler(5, id))
0x87c180 SifInitRpc(0) (0x91b658 -> SifInitCmd, SifAddCmdHandler 0x80000008/9/a/c, SifGetReg/SifSetReg 0x80000002)
0x87c188 SifLoadFileInit (0x91c0d0, binds RPC 0x80000006)
0x87c190 SifInitCmd (0x91acb0)
0x87c198 fioInit (0x91b908, binds 0x80000001, CreateSema)
0x87c1a0 if gp[0x3818] == 1 (byte read from 0x0010000C at 0x870bf0): 0x87c1b8 SetVCommonHandler(8, 0x80000280) via syscall-14 stub 0x91aaa0
0x87c1cc raw syscall-7 stub 0x91aa90: ExecPS2(a0 = 0x00200000, a1 = 0 (gp), a2 = 1 (argc), a3 = main's own argv loaded from 0x14(fp))
0x87c1d8 dead 'j 0x22e440'

Not present anywhere in the tail: TerminateThread/DeleteThread, DI/EI, DisableIntc/RemoveIntcHandler, timer stop, the ps2sdk ExecPS2 wrapper or TerminateLibrary, any memcpy of the core. Registered at the moment of ExecPS2: DMAC 5 SIF cmd handler (re-registered by the re-init) and INTC 10 T1 handler 0x91a868 (T1_MODE 0x282, never stopped), both in r13's intact text; the kernel drops them inside ExecPS2. Libkernel era: old ps2sdk with InitExecPS2 (0x91ca48, kernel blob 0x80074000) and InitTLBFunctions (0x91cbf8, blob 0x80075000) only; no InitAlarm, no InitThread/topThread, no T2 timer system.

## scripts written

1. <scratch>/handoff-vstat/ps_dis.py
2. <scratch>/handoff-vstat/ps_calls.py
3. <scratch>/handoff-vstat/ps_const.py
4. <scratch>/handoff-vstat/romdir.py
5. <scratch>/handoff-vstat/kern.py
6. <scratch>/handoff-vstat/tcb.py
7. <scratch>/handoff-vstat/kdiff.py
8. <scratch>/handoff-vstat/pops_hdr.py
9. <scratch>/handoff-vstat/unpack_lzma.py
10. <scratch>/handoff-vstat/layout_history.py
11. <scratch>/handoff-vstat/unpack_packed.py (abandoned unicorn attempt; the packer stub uses EE-only opcodes, superseded by unpack_lzma.py)
12. <scratch>/handoff-vstat/unpack_dbg.py (debug helper for the abandoned attempt)
