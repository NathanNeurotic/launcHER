/* POPStarter r13 makes the same nine changes to POPS on every launch (its
 * launch function, 0x874864..0x874998, no command or build flag skips
 * them): eight loads and stores become a jump into its resident code,
 * which first forces the base register to a word boundary (the 0x202250
 * store is instead moved into 0x00c70000..0x00c7ffff), and one branch is
 * redirected (0x204160). These are launcHER's own stubs for the same nine
 * places; pops_resident_hook_guards writes the jumps.
 *
 * Each stub leaves the registers and POPS's memory exactly as the
 * original's does, including the values the original leaves in the
 * registers it uses as scratch ($2 at 0x21c5dc, $16 at 0x21c5a8 and
 * 0x202250; all three are dead there). The original also writes 16 bytes
 * of scratch inside its own resident area at 0x202250; POPS never reads
 * that area and launcHER needs no scratch. Each base register ends as its
 * low 32 bits with the two low bits cleared, sign-extended: the original
 * gets there with and/dsll32/dsra32 (mask 0x00000000fffffffc), launcHER
 * with srl/sll by 2, which give the same value for every input.
 *
 * Registers are numbered (POPS's o32 names: $2 v0, $3 v1, $4 a0, $5 a1,
 * $6 a2, $7 a3, $10 t2, $16 s0, $31 ra); this toolchain's EABI names
 * $8..$11 differently. */
.set push
.set noreorder
.set noat
.text
.align 2

/* 0x21c58c: lw $2,0($4) / addiu $4,$4,4; resumes at 0x21c594. */
.globl pops_resident_guard_21c58c
pops_resident_guard_21c58c:
    srl $4, $4, 2
    sll $4, $4, 2
    lw $2, 0($4)
    j 0x0021c594
    addiu $4, $4, 4

/* 0x21c768: lw $4,0($2) / addiu $2,$2,4; resumes at 0x21c770. */
.globl pops_resident_guard_21c768
pops_resident_guard_21c768:
    srl $2, $2, 2
    sll $2, $2, 2
    lw $4, 0($2)
    j 0x0021c770
    addiu $2, $2, 4

/* 0x2082a0: lw $6,0($3) / bnez $6,0x2082b4 (delay slot nop at 0x2082a8);
 * goes on at 0x2082b4 when the word is nonzero, else at 0x2082ac. */
.globl pops_resident_guard_2082a0
pops_resident_guard_2082a0:
    srl $3, $3, 2
    sll $3, $3, 2
    lw $6, 0($3)
    bnez $6, 1f
    nop
    j 0x002082ac
    nop
1:  j 0x002082b4
    nop

/* 0x204ae0: lw $3,0($3) / lui $2,0x3c02; resumes at 0x204ae8. */
.globl pops_resident_guard_204ae0
pops_resident_guard_204ae0:
    srl $3, $3, 2
    sll $3, $3, 2
    lw $3, 0($3)
    j 0x00204ae8
    lui $2, 0x3c02

/* 0x204178: lw $5,0($3) / srl $7,$5,26; resumes at 0x204180. The branch
 * at 0x204160 (b 0x20417c, delay slot move $5,$2) used to run the srl at
 * 0x20417c, which is now the jump's delay slot (nop): it jumps to the
 * second entry instead, as in the original. */
.globl pops_resident_guard_204178
pops_resident_guard_204178:
    srl $3, $3, 2
    sll $3, $3, 2
    lw $5, 0($3)
.globl pops_resident_guard_204160
pops_resident_guard_204160:
    j 0x00204180
    srl $7, $5, 26

/* 0x202250: jr $31 / sw $10,0($2), the end of POPS's PS1 store for
 * addresses past PS1 RAM (0x2021a0). The store address becomes
 * 0x00c70000 | ($2 & 0xffff), all 128 bits of $2 hold it (the original
 * loads it with lq), and $16 is left at 0x01440000 (its scratch; the
 * only caller, 0x202314, sets $16 again before reading it). */
.globl pops_resident_guard_202250
pops_resident_guard_202250:
    andi $2, $2, 0xffff
    lui $16, 0x00c7
    or $2, $2, $16
    pcpyld $2, $0, $2
    lui $16, 0x0144
    jr $31
    sw $10, 0($2)

/* 0x21c5dc: sw $5,0x2260($16) / sw $3,0x2270($16); resumes at 0x21c5e4.
 * $2 is left at 0x00000000fffffffc (the original's scratch; POPS loads
 * $2 again at 0x21c5e8). */
.globl pops_resident_guard_21c5dc
pops_resident_guard_21c5dc:
    srl $16, $16, 2
    sll $16, $16, 2
    daddiu $2, $0, -4
    dsll32 $2, $2, 0
    dsrl32 $2, $2, 0
    sw $5, 0x2260($16)
    j 0x0021c5e4
    sw $3, 0x2270($16)

/* 0x21c5a8: sw $2,0x2288($10) / sw $5,0x2260($10); resumes at 0x21c5b0.
 * $16 is left at 0x00000000fffffffc (the original's scratch; POPS reloads
 * $16 from its stack at 0x21c678 before using it). */
.globl pops_resident_guard_21c5a8
pops_resident_guard_21c5a8:
    srl $10, $10, 2
    sll $10, $10, 2
    daddiu $16, $0, -4
    dsll32 $16, $16, 0
    dsrl32 $16, $16, 0
    sw $2, 0x2288($10)
    j 0x0021c5b0
    sw $5, 0x2260($10)

.set pop
