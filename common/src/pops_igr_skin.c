#include "pops_igr_skin.h"
#include <errno.h>
#include <string.h>

#define POPS_IGR_SKIN_CORE_BASE UINT32_C(0x00200000)

/* Addresses and limits as the original's FUN_0087e464 has them: the BG
 * test is `size > 0x4c300` (0x87e5b8..0x87e5c0), the NO and YES tests are
 * `!(size < 0x1dbd)` (0x87e7dc, 0x87e9e8); the zero fill and the read both
 * use the slot size (0x87e630/0x87e654, 0x87e850/0x87e870, 0x87ea5c/
 * 0x87ea7c). The limits are the sizes of Sony's own three files. */
static const PopsIgrSkinSlot igr_skin_slots[POPS_IGR_SKIN_COUNT] = {
  {"IGR_BG.TM2", UINT32_C(0x002feff0), UINT32_C(0x4c300), UINT32_C(0x4c300)},
  {"IGR_NO.TM2", UINT32_C(0x0034b2f0), UINT32_C(0x1dc0), UINT32_C(0x1dbc)},
  {"IGR_YES.TM2", UINT32_C(0x0034d0b0), UINT32_C(0x1dc0), UINT32_C(0x1dbc)},
};

const PopsIgrSkinSlot *pops_igr_skin_slot(int which) {
  if (which < 0 || which >= POPS_IGR_SKIN_COUNT)
    return NULL;
  return &igr_skin_slots[which];
}

int pops_igr_skin_stage(void *staged_core, size_t core_size, int which,
                        const void *data, size_t size) {
  const PopsIgrSkinSlot *slot = pops_igr_skin_slot(which);
  uint8_t *at;
  size_t offset;
  if (!staged_core || !slot || (!data && size))
    return -EINVAL;
  offset = (size_t)(slot->addr - POPS_IGR_SKIN_CORE_BASE);
  if (core_size < offset || core_size - offset < slot->slot_size)
    return -ERANGE;
  if (size > slot->max_size)
    return -EFBIG;
  /* No check of what the slot holds or of the file's contents: the
   * original makes none. Zero fill first, then the file, as there. */
  at = (uint8_t *)staged_core + offset;
  memset(at, 0, slot->slot_size);
  if (size)
    memcpy(at, data, size);
  return 0;
}
