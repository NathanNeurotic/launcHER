#ifndef POPS_RESIDENT_ABI_H
#define POPS_RESIDENT_ABI_H

/* The parts of the resident image's layout that its assembly reads
 * (pops_resident_recompiler.S), as plain numbers so assembler and C share
 * them. pops_resident.h builds on these; pops_resident_engine.c checks
 * them against the C structure. */

/* PopsResidentConfig.flags: offset in the structure. */
#define POPS_RESIDENT_FLAGS_OFFSET 8

/* POPStarter's $RECOMPILER_ADDON_0/1/2: what the recompiler hook runs
 * (pops_resident_recompiler.S). Bits of PopsResidentConfig.flags. */
#define POPS_RES_F_RECOMPILER_0 0x0800 /* lw/sw -> lwr/swr behind the emit pointer */
#define POPS_RES_F_RECOMPILER_1 0x1000 /* zero guarded break 7 / break 6 in the loaded code */
#define POPS_RES_F_RECOMPILER_2 0x2000 /* BIOS call stubs in the loaded code -> jr ra */

#endif
