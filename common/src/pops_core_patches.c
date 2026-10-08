#include "pops_external.h"

/* Exact write widths/values from the measured original loader's clean R5900
 * exports. Guards come from the SHA256-scoped external reference POPS core.
 * This table contains patch metadata, not a resident POPStarter payload. */
typedef struct {
  uint32_t group, address, expected, replacement;
  uint8_t width;
} CorePatch;

static const CorePatch patches[] = {
  /* Skip only embedded DEV9/ATAD/HDD/PFS loads. Keep Sony controller, audio
   * and IOPCD loads, and preserve the branch delay slot. Redirect the fixed
   * filesystem aliases to the separately configured launcHER IOP proxy. */
  {POPS_CORE_STORAGE_BRIDGE, 0x002003d8, 0x12000031, 0x10000031, 4},
  /* Backing volumes must already be mounted by the bootstrap. Bypass only
   * the two Sony partition-mount calls; retain poweroff thread setup and
   * both delay slots. The proxy has no authority to mount an arbitrary HDD. */
  {POPS_CORE_STORAGE_BRIDGE, 0x00214968, 0x0c08cd94, 0x00001021, 4},
  {POPS_CORE_STORAGE_BRIDGE, 0x002149a0, 0x0c08cd94, 0x00001021, 4},
  {POPS_CORE_STORAGE_BRIDGE, 0x004f9838, 0x31736670, 0x73706f70, 4},
  {POPS_CORE_STORAGE_BRIDGE, 0x004f9888, 0x31736670, 0x73706f70, 4},
  {POPS_CORE_STORAGE_BRIDGE, 0x004f98a0, 0x31736670, 0x73706f70, 4},
  {POPS_CORE_STORAGE_BRIDGE, 0x004ffe88, 0x30736670, 0x73706f70, 4},
  {POPS_CORE_STORAGE_BRIDGE, 0x00502708, 0x30736670, 0x73706f70, 4},
  {POPS_CORE_STORAGE_BRIDGE, 0x00502798, 0x31736670, 0x73706f70, 4},
  {POPS_CORE_STORAGE_BRIDGE, 0x005028e0, 0x31736670, 0x73706f70, 4},
  {POPS_CORE_STORAGE_BRIDGE, 0x005028e8, 0x30736670, 0x73706f70, 4},
  {POPS_CORE_HDD_CHECK, 0x002e5ad8, 0x0c0003b7, 0x00000000, 4}, /* FUN_008db778 */
  {POPS_CORE_CDROM_LICENSE, 0x00263ca8, 0x1440fffd, 0x00000000, 4}, /* FUN_008dba90 */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x0020838c, 0x0000000d, 0x00000000, 4}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x0023af4c, 0x000001cd, 0x00000000, 2}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x0023afb0, 0x000001cd, 0x00000000, 2}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x0023b000, 0x000001cd, 0x00000000, 2}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x0023b084, 0x000001cd, 0x00000000, 2}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00208a84, 0x000001cd, 0x00000000, 2}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00204790, 0x0000000d, 0x00000000, 2}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00207e2c, 0x0c08bea4, 0x0c0903d8, 4}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00207e6c, 0x0c08bea4, 0x0c0903d8, 4}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00207eb0, 0x0c08bea4, 0x0c0903d8, 4}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00207ee8, 0x0c08bea4, 0x0c0903d8, 4}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00207f4c, 0x0c08bea4, 0x0c0903d8, 4}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x0020b908, 0x0000000d, 0x00000000, 1}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00207e34, 0x0000000d, 0x08081fbf, 4}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00207e74, 0x0000000d, 0x08081fbf, 4}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00207eb8, 0x0000000d, 0x08081fbf, 4}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00207ebc, 0x1000009c, 0x00000000, 4}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00207f54, 0x0000000d, 0x08081fbf, 4}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00207f58, 0x10000075, 0x00000000, 4}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00207e9c, 0x0000000a, 0x00000022, 1}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x00208136, 0x00000098, 0x0000009c, 1}, /* FUN_008dbafc */
  {POPS_CORE_EXCEPTION_BREAKPOINTS, 0x0020813e, 0x00000018, 0x0000001c, 1}, /* FUN_008dbafc */
  {POPS_CORE_POWER_OFF, 0x00214860, 0x0442fff9, 0x00000000, 4}, /* FUN_008dbe78 */
  {POPS_CORE_DELCRO, 0x0020044c, 0x0000000b, 0x00000000, 1}, /* FUN_008dbf58 */
  {POPS_CORE_DELCRO, 0x00200484, 0x00000010, 0x00000000, 1}, /* FUN_008dbf58 */
  {POPS_CORE_MODULE_ERRORS, 0x0020032e, 0x00000443, 0x00001000, 2}, /* FUN_008dbfd4 */
  {POPS_CORE_MODULE_ERRORS, 0x00200362, 0x00000443, 0x00001000, 2}, /* FUN_008dbfd4 */
  {POPS_CORE_MODULE_ERRORS, 0x00200392, 0x00000443, 0x00001000, 2}, /* FUN_008dbfd4 */
  {POPS_CORE_MODULE_ERRORS, 0x002003c2, 0x00000441, 0x00001000, 2}, /* FUN_008dbfd4 */
  {POPS_CORE_MODULE_ERRORS, 0x002003fa, 0x00000443, 0x00001000, 2}, /* FUN_008dbfd4 */
  {POPS_CORE_MODULE_ERRORS, 0x0020042a, 0x00000443, 0x00001000, 2}, /* FUN_008dbfd4 */
  {POPS_CORE_MODULE_ERRORS, 0x0020045a, 0x00000443, 0x00001000, 2}, /* FUN_008dbfd4 */
  {POPS_CORE_MODULE_ERRORS, 0x0020048a, 0x00000443, 0x00001000, 2}, /* FUN_008dbfd4 */
  {POPS_CORE_MODULE_ERRORS, 0x002004be, 0x00000443, 0x00001000, 2}, /* FUN_008dbfd4 */
};

int pops_core_patches_stage(uint32_t base, void *memory, size_t span, uint32_t groups) {
  uint8_t *bytes = memory;
  size_t i;
  int status;
  if (!bytes || !groups || (groups & ~POPS_CORE_ALL))
    return POPS_FILE_INVALID;
  if (base < 0x100000 || base > 0x200000 || span > 0x2000000 - base ||
      span < 0x502e60 - base)
    return POPS_FILE_RANGE;
  status = pops_core_image_identify(bytes + 0x200000 - base, 0x302e60);
  if (status)
    return status;
  /* Check every selected site before writing any of them. Apply the selected
   * groups together, before any game-specific/Trojan modifications. */
  for (i = 0; i < sizeof(patches) / sizeof(patches[0]); ++i) {
    const CorePatch *patch = patches + i;
    uint32_t actual = 0;
    unsigned j;
    if (!(groups & patch->group))
      continue;
    for (j = 0; j < patch->width; ++j)
      actual |= (uint32_t)bytes[patch->address - base + j] << (j * 8);
    if (actual != patch->expected)
      return POPS_FILE_GUARD;
  }
  for (i = 0; i < sizeof(patches) / sizeof(patches[0]); ++i) {
    const CorePatch *patch = patches + i;
    unsigned j;
    if (!(groups & patch->group))
      continue;
    for (j = 0; j < patch->width; ++j)
      bytes[patch->address - base + j] = (uint8_t)(patch->replacement >> (j * 8));
  }
  return POPS_FILE_OK;
}
