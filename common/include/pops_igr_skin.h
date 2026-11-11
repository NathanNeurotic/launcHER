#ifndef LAUNCHER_POPS_IGR_SKIN_H
#define LAUNCHER_POPS_IGR_SKIN_H

/* POPStarter r13's IGR menu skin (its FUN_0087e464, called once from the
 * launch function at 0x876b18). Sony's POPS carries three complete TIM2
 * files for its own in-game reset dialog; the original copies the user's
 * IGR_BG.TM2, IGR_NO.TM2 and IGR_YES.TM2 over them, raw, in that order:
 *
 *   file          slot in POPS   slot size   largest file accepted
 *   IGR_BG.TM2    0x002feff0     0x4c300     0x4c300 (312,064)
 *   IGR_NO.TM2    0x0034b2f0     0x1dc0      0x1dbc  (7,612)
 *   IGR_YES.TM2   0x0034d0b0     0x1dc0      0x1dbc  (7,612)
 *
 * A file that fits has its whole slot zero-filled and is then read into it.
 * A larger file is refused with the slot untouched ("TOO BIG !"), a missing
 * one leaves Sony's image, and nothing is ever fatal. The original checks
 * nothing but the size: not the TIM2 magic, the picture count, the
 * dimensions or what the slot held before. A zero-length file therefore
 * wipes the slot. All of that is copied here.
 * See docs/POPSTARTER_IGR_SKIN.md. Not tested on a console. */

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  POPS_IGR_SKIN_BG = 0,
  POPS_IGR_SKIN_NO,
  POPS_IGR_SKIN_YES,
  POPS_IGR_SKIN_COUNT,
};

typedef struct {
  const char *name;   /* file name inside the POPS folder */
  uint32_t addr;      /* EE address of the slot inside POPS */
  uint32_t slot_size; /* bytes zero-filled before the copy */
  uint32_t max_size;  /* largest file the original accepts */
} PopsIgrSkinSlot;

/* The original's own order: BG, NO, YES. NULL for any other `which`. */
const PopsIgrSkinSlot *pops_igr_skin_slot(int which);

/* Put one skin file into the staged core (a flat image of POPS from
 * 0x00200000): the slot becomes `size` bytes of `data` followed by zeros.
 * `size` is the number of bytes actually read; fewer than the file holds
 * leaves what the original's unchecked read leaves (data, then zeros).
 * Returns 0, or with the core untouched:
 *   -EINVAL  no core, an unknown `which`, or no data with a nonzero size
 *   -ERANGE  the core ends before the slot does
 *   -EFBIG   `size` is above the slot's max_size (the original's TOO BIG) */
int pops_igr_skin_stage(void *staged_core, size_t core_size, int which,
                        const void *data, size_t size);

#ifdef __cplusplus
}
#endif

#endif
