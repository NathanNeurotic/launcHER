.set noreorder
.text
.globl pops_probe_call
.ent pops_probe_call
pops_probe_call:
  addiu $sp, $sp, -32
  sd $ra, 0($sp)
  sd $gp, 8($sp)
  lui $gp, 0x51
  addiu $gp, $gp, -0x5990
  jal 0x00210090
  nop
  ld $gp, 8($sp)
  ld $ra, 0($sp)
  jr $ra
  addiu $sp, $sp, 32
.end pops_probe_call
