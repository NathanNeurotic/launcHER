/* Independent mid-function bridge for the progressive DISPLAY adapter.
 * No register argument is borrowed from the interrupted Sony function.
 * All GPRs including opaque upper lanes and both HI/LO banks are saved.
 * a1 low 64 bits receives DISPLAY; stock continuation consumes it with SD.
 * Entered only after guarded static setup of the identified Sony core. */
.set push
.set noreorder
.set noat
.text
.align 2
.globl pops_resident_progressive
.ent pops_resident_progressive
pops_resident_progressive:
    addiu $29, $29, -544
    sq $29, 528($29)
    sq $1, 0($29)
    sq $2, 16($29)
    sq $3, 32($29)
    sq $4, 48($29)
    sq $5, 64($29)
    sq $6, 80($29)
    sq $7, 96($29)
    sq $8, 112($29)
    sq $9, 128($29)
    sq $10, 144($29)
    sq $11, 160($29)
    sq $12, 176($29)
    sq $13, 192($29)
    sq $14, 208($29)
    sq $15, 224($29)
    sq $16, 240($29)
    sq $17, 256($29)
    sq $18, 272($29)
    sq $19, 288($29)
    sq $20, 304($29)
    sq $21, 320($29)
    sq $22, 336($29)
    sq $23, 352($29)
    sq $24, 368($29)
    sq $25, 384($29)
    sq $26, 400($29)
    sq $27, 416($29)
    sq $28, 432($29)
    sq $30, 448($29)
    sq $31, 464($29)
    mfhi $2
    sd $2, 480($29)
    mflo $2
    sd $2, 488($29)
    mfhi1 $2
    sd $2, 496($29)
    mflo1 $2
    sd $2, 504($29)
    jal pops_progressive_live
    nop
    sd $2, 512($29)
    ld $2, 480($29)
    mthi $2
    ld $2, 488($29)
    mtlo $2
    ld $2, 496($29)
    mthi1 $2
    ld $2, 504($29)
    mtlo1 $2
    lq $1, 0($29)
    lq $2, 16($29)
    lq $3, 32($29)
    lq $4, 48($29)
    lq $5, 64($29)
    lq $6, 80($29)
    lq $7, 96($29)
    lq $8, 112($29)
    lq $9, 128($29)
    lq $10, 144($29)
    lq $11, 160($29)
    lq $12, 176($29)
    lq $13, 192($29)
    lq $14, 208($29)
    lq $15, 224($29)
    lq $16, 240($29)
    lq $17, 256($29)
    lq $18, 272($29)
    lq $19, 288($29)
    lq $20, 304($29)
    lq $21, 320($29)
    lq $22, 336($29)
    lq $23, 352($29)
    lq $24, 368($29)
    lq $25, 384($29)
    lq $26, 400($29)
    lq $27, 416($29)
    lq $28, 432($29)
    lq $30, 448($29)
    lq $31, 464($29)
    ld $5, 512($29)
    lq $29, 528($29)
    addiu $29, $29, 544
    j 0x0021a098
    lui $2, 0x1200
.end pops_resident_progressive
.set pop
