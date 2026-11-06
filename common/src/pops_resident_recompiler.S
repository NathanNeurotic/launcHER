/* POPStarter r13's recompiler hook and its $RECOMPILER_ADDON_0..4
 * commands, launcHER's own code for the same behaviour.
 *
 * On every launch POPStarter writes "j <its block>; nop" over two of the
 * loads that restore POPS's saved registers when POPS's recompiler has
 * finished a block (0x2075e8: ld $s2,0x20($sp) / ld $s3,0x28($sp); its
 * launch function, 0x8747ec). Its block reads the flag word at PS1 0xb890
 * and then runs what the commands put in it, in this order:
 *   flag nonzero: ADDON_1, then ADDON_2, then ADDON_0 (but only after
 *                 ADDON_2: without it, ADDON_0 is skipped this time);
 *   flag zero:    ADDON_0.
 * Then it reloads $s0..$s5 from POPS's frame (0x10..0x38($sp)) and returns
 * to 0x2075f4 (ld $ra,0x40($sp)) with $ra = 0x2075f4. Without a command it
 * only reads the flag. pops_resident_hook_recompiler writes the jump to
 * pops_resident_recompiler; the flags in the resident configuration say
 * which commands came (POPS_RES_F_RECOMPILER_n).
 *
 *   ADDON_0: the 0x800 bytes before $a2 (where POPS stores the block's last
 *            instruction, at 0x2075f8): every word in 0x8bff0001..0x8fffffff
 *            or 0xabff0001..0xafffffff gets 0x0c000000 added (lw -> lwr,
 *            sw -> swr), stored with swr.
 *   ADDON_1: clears the top byte of the word at PS1 0xb878 (the loaded
 *            code's start), then reads it and the length at 0xb87c, zeroes
 *            the flag, and scans start..start+length, both ends included:
 *            a break 7 (0x0007000d) or break 6 (0x0006000d) is zeroed when
 *            the top byte of the word two before it is nonzero. After a
 *            zeroed break 7 the next word follows without the end check.
 *   ADDON_2: reads the start (top byte as it is), the length, then clears
 *            that byte and the flag, and scans start..start+length, the end
 *            excluded, for PS1 BIOS call stubs: li $t2,0xa0 / jr $t2 /
 *            li $t1,0x3a, and li $t2,0xb0 / jr $t2 / li $t1,0x38, 0x52 or
 *            0x5a, plus the li $t1 before the jr for A0:3A, B0:38 and
 *            B0:5A. Each becomes jr $ra / nop / nop. The original's check
 *            for li-first B0:52 loads the third word into $v1 and compares
 *            the first, so it never matches; every B0 stub that gets that
 *            far leaves $v1 at its third word, and POPS stores $v1 at $a2
 *            after the hook. Copied as it is.
 *   ADDON_3: POPS's two emit points 0x206318 (sw $v0,0($s1) / addiu
 *            $s1,$s1,4) and 0x205d1c (or $a0,$a0,$v0 / sw $a0,0($t4)) jump
 *            here instead (pops_resident_hook_recompiler_emit). The word is
 *            converted as ADDON_0 does it and stored as 0, word, 0, 0 with
 *            swr ($s1 or $t4 moves 16 bytes; at 0x205d1c the last 4 come
 *            from the addiu in the delay slot POPS resumes with).
 *   ADDON_4: the same, storing only the converted word (4 bytes).
 * The emit code borrows $k0, $k1 and $at and gives back all 128 bits, as
 * the original does. It leaves $ra at 0x01440000 and the converted word
 * in $v0 (or $a0), as the original does; POPS reloads both before using
 * them. The 0x205d1c code keeps the $gp it found in a slot, and the
 * 0x206318 code loads $gp from that slot: the original's does the same
 * (it saves its own $gp elsewhere and never reads it back), so $gp is zero
 * there until 0x205d1c has run once. Copied as it is.
 *
 * Registers are numbered: POPS's o32 names are $2 v0, $3 v1, $4 a0,
 * $6 a2, $12 t4, $16..$21 s0..s5, $26 k0, $27 k1, $28 gp, $29 sp, $31 ra;
 * this toolchain names $8..$11 differently. tools/test_pops_launch_hooks.py
 * assembles this file with tools/r5900_mini.py and runs it against
 * tools/pops_recompiler_model.py, and so does it for the original's code
 * when POPSTARTER_TEST_ELF is set; keep to what that assembler reads. */
#include "pops_resident_abi.h"

.set push
.set noreorder
.set noat
.text
.align 2

.globl pops_resident_recompiler
pops_resident_recompiler:
    lui $18, 0x0101
    lw $18, -0x4770($18)            /* the flag (PS1 0xb890) */
    lui $31, %hi(pops_resident_config)
    addiu $31, $31, %lo(pops_resident_config)
    beqz $18, .Lrc_behind
    lw $31, POPS_RESIDENT_FLAGS_OFFSET($31)

    /* Flag set: ADDON_1, then ADDON_2 (and from there ADDON_0). */
    andi $16, $31, POPS_RES_F_RECOMPILER_1
    beqz $16, .Lrc_stubs
    nop
    lui $20, 0x0101
    sb $0, -0x4785($20)             /* the start word's top byte (0xb87b) */
    lw $16, -0x4788($20)            /* start (0xb878), read after that */
    lw $19, -0x4784($20)            /* length (0xb87c) */
    lui $17, 0x0100
    addu $16, $16, $17              /* PS1 address -> EE address */
    sw $0, -0x4770($20)             /* flag */
    addu $19, $16, $19              /* the last word scanned */
    lui $20, 0x0007
    ori $20, $20, 0x000d            /* break 7 */
    lui $21, 0x0006
    ori $21, $21, 0x000d            /* break 6 */
.Lrc_break_next:
    lw $18, 0($16)
    beq $18, $20, .Lrc_break7
    nop
    bne $18, $21, .Lrc_break_end
    nop
    lb $18, -5($16)
    beqz $18, .Lrc_break_end
    nop
    b .Lrc_break_end
    sw $0, 0($16)
.Lrc_break7:
    lb $18, -5($16)
    beqz $18, .Lrc_break_end
    nop
    sw $0, 0($16)
    b .Lrc_break_next               /* as the original: no end check here */
    addiu $16, $16, 4
.Lrc_break_end:
    bne $16, $19, .Lrc_break_next
    addiu $16, $16, 4

.Lrc_stubs:
    andi $16, $31, POPS_RES_F_RECOMPILER_2
    beqz $16, .Lrc_exit
    nop
    lui $20, 0x0101
    lw $16, -0x4788($20)            /* start, top byte as it is */
    lw $19, -0x4784($20)            /* length */
    sb $0, -0x4785($20)             /* then the start word's top byte */
    lui $17, 0x0100
    addu $16, $16, $17
    sw $0, -0x4770($20)             /* flag */
    addu $19, $16, $19              /* end, not scanned */
    lui $20, 0x0140
    ori $20, $20, 0x0008            /* jr $t2 */
.Lrc_stub_next:
    lw $18, 0($16)
    lui $17, 0x240a
    ori $17, $17, 0x00a0            /* li $t2, 0xa0 */
    beq $18, $17, .Lrc_stub_a0
    ori $17, $17, 0x00b0            /* li $t2, 0xb0 */
    bne $18, $17, .Lrc_stub_end
    nop
    lw $17, 4($16)
    lw $18, 8($16)
    lui $21, 0x2409
    bne $17, $20, .Lrc_b0_li_first
    ori $21, $21, 0x0038            /* li $t1, 0x38 */
    beq $18, $21, .Lrc_patch        /* jr $t2 / li $t1, 0x38 */
    addiu $21, $21, 0x1a            /* li $t1, 0x52 */
    beq $18, $21, .Lrc_patch
    addiu $21, $21, 0x8             /* li $t1, 0x5a */
    beq $18, $21, .Lrc_patch
    nop
    b .Lrc_b0_v1
    nop
.Lrc_b0_li_first:
    bne $18, $20, .Lrc_b0_v1
    nop
    beq $17, $21, .Lrc_patch        /* li $t1, 0x38 / jr $t2 */
    nop
.Lrc_b0_v1:
    lw $3, 8($16)                   /* the original's never-matching B0:52 check */
    bne $18, $20, .Lrc_stub_end
    lui $21, 0x2409
    ori $21, $21, 0x005a
    beq $17, $21, .Lrc_patch        /* li $t1, 0x5a / jr $t2 */
    nop
    b .Lrc_stub_end
    nop
.Lrc_stub_a0:
    lw $17, 4($16)
    lw $18, 8($16)
    lui $21, 0x2409
    bne $17, $20, .Lrc_a0_li_first
    ori $21, $21, 0x003a            /* li $t1, 0x3a */
    beq $18, $21, .Lrc_patch        /* jr $t2 / li $t1, 0x3a */
    nop
.Lrc_a0_li_first:
    bne $18, $20, .Lrc_stub_end
    nop
    bne $17, $21, .Lrc_stub_end
    nop
.Lrc_patch:
    lui $17, 0x03e0
    ori $17, $17, 0x0008            /* jr $ra */
    sw $17, 0($16)
    sw $0, 4($16)
    sw $0, 8($16)
.Lrc_stub_end:
    addiu $16, $16, 4
    bne $16, $19, .Lrc_stub_next
    nop

.Lrc_behind:
    andi $16, $31, POPS_RES_F_RECOMPILER_0
    beqz $16, .Lrc_exit
    nop
    lui $19, 0x7400
    ori $19, $19, 0xffff            /* word + this: 0..0x0400fffe for 0x8bff0001.. */
    lui $20, 0x5400
    ori $20, $20, 0xffff            /* ... and for 0xabff0001.. */
    lui $21, 0x0401
    addiu $21, $21, -1              /* 0x0400ffff */
    lui $31, 0x0c00                 /* lw -> lwr, sw -> swr */
    addiu $16, $6, -0x800
.Lrc_behind_next:
    lw $18, 0($16)
    addu $17, $18, $19
    sltu $17, $17, $21
    bnez $17, .Lrc_behind_convert
    addu $17, $18, $20
    sltu $17, $17, $21
    beqz $17, .Lrc_behind_end
    nop
.Lrc_behind_convert:
    addu $18, $18, $31
    swr $18, 0($16)
.Lrc_behind_end:
    addiu $16, $16, 4
    bne $16, $6, .Lrc_behind_next
    nop

.Lrc_exit:
    ld $16, 0x10($29)
    ld $17, 0x18($29)
    ld $18, 0x20($29)
    ld $19, 0x28($29)
    ld $20, 0x30($29)
    ld $21, 0x38($29)
    lui $31, 0x0020
    ori $31, $31, 0x75f4
    jr $31
    nop

/* ADDON_3 at 0x206318: $v0, converted, goes out as 0, $v0, 0, 0 at $s1. */
.globl pops_resident_recompiler_addon3_206318
pops_resident_recompiler_addon3_206318:
    lui $31, %hi(pops_resident_recompiler_save)
    addiu $31, $31, %lo(pops_resident_recompiler_save)
    sq $26, 0x00($31)
    sq $27, 0x10($31)
    sq $1, 0x20($31)
    lui $26, 0x7400
    ori $26, $26, 0xffff
    addu $26, $2, $26
    lui $27, 0x5400
    ori $27, $27, 0xffff
    addu $27, $2, $27
    lui $1, 0x0401
    addiu $1, $1, -1
    sltu $26, $26, $1
    sltu $27, $27, $1
    or $26, $26, $27
    beqz $26, 1f
    lui $27, 0x0c00
    addu $2, $2, $27
1:  swr $0, 0($17)
    swr $2, 4($17)
    swr $0, 8($17)
    swr $0, 12($17)
    lq $26, 0x00($31)
    lq $27, 0x10($31)
    lq $1, 0x20($31)
    lq $28, 0x30($31)               /* the $gp the 0x205d1c code kept */
    lui $31, 0x0144
    j 0x00206320
    addiu $17, $17, 0x10

/* ADDON_3 at 0x205d1c: $a0 |= $v0 (the or the jump replaced), converted,
 * goes out as 0, $a0, 0, 0 at $t4; 0x205d28 adds the last 4 to $t4. */
.globl pops_resident_recompiler_addon3_205d1c
pops_resident_recompiler_addon3_205d1c:
    lui $31, %hi(pops_resident_recompiler_save)
    addiu $31, $31, %lo(pops_resident_recompiler_save)
    sq $26, 0x00($31)
    sq $27, 0x10($31)
    sq $1, 0x20($31)
    sq $28, 0x30($31)
    or $4, $4, $2
    lui $26, 0x7400
    ori $26, $26, 0xffff
    addu $26, $4, $26
    lui $27, 0x5400
    ori $27, $27, 0xffff
    addu $27, $4, $27
    lui $1, 0x0401
    addiu $1, $1, -1
    sltu $26, $26, $1
    sltu $27, $27, $1
    or $26, $26, $27
    beqz $26, 1f
    lui $27, 0x0c00
    addu $4, $4, $27
1:  swr $0, 0($12)
    swr $4, 4($12)
    swr $0, 8($12)
    swr $0, 12($12)
    lq $26, 0x00($31)
    lq $27, 0x10($31)
    lq $1, 0x20($31)
    lui $31, 0x0144
    j 0x00205d24
    addiu $12, $12, 0xc

/* ADDON_4 at 0x206318: only the converted $v0, at $s1. */
.globl pops_resident_recompiler_addon4_206318
pops_resident_recompiler_addon4_206318:
    lui $31, %hi(pops_resident_recompiler_save)
    addiu $31, $31, %lo(pops_resident_recompiler_save)
    sq $26, 0x00($31)
    sq $27, 0x10($31)
    sq $1, 0x20($31)
    lui $26, 0x7400
    ori $26, $26, 0xffff
    addu $26, $2, $26
    lui $27, 0x5400
    ori $27, $27, 0xffff
    addu $27, $2, $27
    lui $1, 0x0401
    addiu $1, $1, -1
    sltu $26, $26, $1
    sltu $27, $27, $1
    or $26, $26, $27
    beqz $26, 1f
    lui $27, 0x0c00
    addu $2, $2, $27
1:  swr $2, 0($17)
    lq $26, 0x00($31)
    lq $27, 0x10($31)
    lq $1, 0x20($31)
    lq $28, 0x30($31)               /* the $gp the 0x205d1c code kept */
    lui $31, 0x0144
    j 0x00206320
    addiu $17, $17, 4

/* ADDON_4 at 0x205d1c: only the converted $a0, at $t4; 0x205d28 adds 4. */
.globl pops_resident_recompiler_addon4_205d1c
pops_resident_recompiler_addon4_205d1c:
    lui $31, %hi(pops_resident_recompiler_save)
    addiu $31, $31, %lo(pops_resident_recompiler_save)
    sq $26, 0x00($31)
    sq $27, 0x10($31)
    sq $1, 0x20($31)
    sq $28, 0x30($31)
    or $4, $4, $2
    lui $26, 0x7400
    ori $26, $26, 0xffff
    addu $26, $4, $26
    lui $27, 0x5400
    ori $27, $27, 0xffff
    addu $27, $4, $27
    lui $1, 0x0401
    addiu $1, $1, -1
    sltu $26, $26, $1
    sltu $27, $27, $1
    or $26, $26, $27
    beqz $26, 1f
    lui $27, 0x0c00
    addu $4, $4, $27
1:  swr $4, 0($12)
    lq $26, 0x00($31)
    lq $27, 0x10($31)
    lq $1, 0x20($31)
    lui $31, 0x0144
    j 0x00205d24
    nop

.set pop
