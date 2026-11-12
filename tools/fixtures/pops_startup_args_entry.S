.set noreorder
.text
.globl pops_startup_call
.globl pops_startup_stop
.globl pops_startup_noop
.bss
.align 4
startup_saved_sp: .space 4
.text
pops_startup_call:
  addiu $sp,$sp,-64
  sd $ra,0($sp)
  sd $gp,8($sp)
  sd $s0,16($sp)
  sd $s1,24($sp)
  sd $s2,32($sp)
  sd $s3,40($sp)
  lui $t0,%hi(startup_saved_sp)
  sw $sp,%lo(startup_saved_sp)($t0)
  lui $gp,0x51
  addiu $gp,$gp,-0x5990
  jal 0x002004f0
  nop
pops_startup_stop:
  lui $t0,%hi(startup_saved_sp)
  lw $sp,%lo(startup_saved_sp)($t0)
  ld $s3,40($sp)
  ld $s2,32($sp)
  ld $s1,24($sp)
  ld $s0,16($sp)
  ld $gp,8($sp)
  ld $ra,0($sp)
  jr $ra
  addiu $sp,$sp,64
pops_startup_noop:
  jr $ra
  move $v0,$zero
