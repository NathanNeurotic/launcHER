.text

.set push
.set noreorder
.set noat

.globl pops_trampoline_code
.globl pops_trampoline_code_end

pops_trampoline_code:
    /* a0 contains pointer to PopsTrampolineArgs at POPS_TRAMPOLINE_ARGS (0x00084200) */
    move    $s0, $a0

    /* Set stack pointer in BIOS unused RAM (0x0008fff0) */
    li      $sp, 0x0008fff0

    /* 1. Zero scratchpad 0x70000000..0x70003c30 */
    li      $t0, 0x70000000
    lw      $t1, 12($s0)        /* scratchpad_size */
    addu    $t2, $t0, $t1
1:
    sltu    $t3, $t0, $t2
    beqz    $t3, 2f
    nop
    sw      $zero, 0($t0)
    addiu   $t0, $t0, 4
    b       1b
    nop
2:

    /* 2. Zero BSS: bss_address to bss_address + bss_size */
    lw      $t0, 4($s0)         /* bss_address (0x00502e60) */
    lw      $t1, 8($s0)         /* bss_size (0x00362ae0) */
    addu    $t2, $t0, $t1
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
    lw      $a0, 0($s0)         /* entry (0x00200008) */
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
