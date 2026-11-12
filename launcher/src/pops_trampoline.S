.text

.set push
.set noreorder
.set noat

.globl pops_trampoline_code
.globl pops_trampoline_code_end

pops_trampoline_code:
    /* a0 contains pointer to PopsTrampolineArgs at POPS_TRAMPOLINE_ARGS (0x00084200).
     * The caller is the kernel's only thread by now (popsHandoffRetireThreads):
     * the ExecPS2 below would otherwise rewrite the initial frame of every
     * thread it terminates, inside memory this code has just given to POPS. */
    move    $s0, $a0

    /* Set stack pointer in BIOS unused RAM (0x0008fff0) */
    li      $sp, 0x0008fff0

    /* 0. Interrupts off (Status.EIE = 0) before anything of launcHER's is
     *    overwritten. launcHER's timer (INTC 11) and SIF (DMAC 5) handlers
     *    are still registered and step 3 zeroes their code; POPStarter's
     *    own handlers stay intact up to its ExecPS2 because nothing clears
     *    its code. ExecPS2 empties the handler lists and itself returns with
     *    EIE = 0 (the di at kernel 0x80002fa8), so POPS starts as it does
     *    after POPStarter. The loop is ps2sdk's DI(): a di that loses a race
     *    with an interrupt is tried again. */
0:
    di
    sync.p
    mfc0    $t0, $12            /* Status */
    lui     $t1, 0x0001         /* Status.EIE */
    and     $t0, $t0, $t1
    bnez    $t0, 0b
    nop

    /* 1. Zero the whole scratchpad, 0x70000000..0x70004000, as POPStarter
     *    r13 does before it enters POPS (memset at 0x87c0f8). POPS's own
     *    part is the first scratchpad_size (0x3c30) bytes. */
    li      $t0, 0x70000000
    li      $t2, 0x70004000
1:
    sltu    $t3, $t0, $t2
    beqz    $t3, 2f
    nop
    sw      $zero, 0($t0)
    addiu   $t0, $t0, 4
    b       1b
    nop
2:

    /* 2. Zero BSS and the start of POPS's heap: bss_address up to the
     *    larger of the BSS end and 0x00870000 (POPS_CLEAR_END). POPStarter
     *    clears 0x502e60..0x870000 (memset at 0x87c130, up to its own code),
     *    and POPS's heap starts at its BSS end (its crt0 calls
     *    SetupHeap(0x865940, -1)), so its first 42 KB start zeroed. */
    lw      $t0, 4($s0)         /* bss_address (0x00502e60) */
    lw      $t1, 8($s0)         /* bss_size (0x00362ae0) */
    addu    $t2, $t0, $t1
    li      $t1, 0x00870000
    sltu    $t3, $t2, $t1
    movn    $t2, $t1, $t3       /* end = max(BSS end, 0x00870000) */
3:
    sltu    $t3, $t0, $t2
    beqz    $t3, 4f
    nop
    sw      $zero, 0($t0)
    addiu   $t0, $t0, 4
    b       3b
    nop
4:

    /* 3. Zero low RAM: 0x00100000 to 0x00200000 (clears launcHER) */
    li      $t0, 0x00100000
    li      $t2, 0x00200000
5:
    sltu    $t3, $t0, $t2
    beqz    $t3, 6f
    nop
    sw      $zero, 0($t0)
    addiu   $t0, $t0, 4
    b       5b
    nop
6:

    /* 4. Copy core from staging_core to core_address (0x00200000) */
    lw      $t0, 16($s0)        /* staging_core (0x01000000) */
    lw      $t1, 20($s0)        /* core_address (0x00200000) */
    lw      $t2, 24($s0)        /* core_size (0x00302e60) */
    addu    $t3, $t0, $t2
7:
    sltu    $t8, $t0, $t3
    beqz    $t8, 8f
    nop
    lw      $t9, 0($t0)
    sw      $t9, 0($t1)
    addiu   $t0, $t0, 4
    addiu   $t1, $t1, 4
    b       7b
    nop
8:

    /* 5. Flush caches: FlushCache(0), FlushCache(2) via syscall 0x64 */
    li      $a0, 0
    li      $v1, 0x64
    syscall
    nop

    li      $a0, 2
    li      $v1, 0x64
    syscall
    nop

    /* 6. Enter POPS via ExecPS2(entry, NULL, argc, argv) via syscall 7 */
    lw      $a0, 0($s0)         /* entry (0x00200000, as POPStarter r13) */
    move    $a1, $zero          /* gp = NULL */
    lw      $a2, 28($s0)        /* argc = 1 */
    addiu   $a3, $s0, 32        /* argv (pointer to array of char*) */

    li      $v1, 7              /* __NR__ExecPS2 */
    syscall
    nop

9:
    b       9b
    nop

pops_trampoline_code_end:

.set pop
