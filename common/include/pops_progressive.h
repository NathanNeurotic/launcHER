#ifndef POPS_PROGRESSIVE_H
#define POPS_PROGRESSIVE_H

#include <stdint.h>

/* Bounded state projection of the original progressive DISPLAY entry.
 * The source names identify measured scratch offsets without inventing
 * higher-level rendering semantics. This arithmetic helper does not install
 * a live hook or access PS2 hardware. */
typedef struct {
  uint64_t fallback_display;
  uint64_t display;
  uint64_t scratch;
  uint32_t source_32a8, source_32ac, source_32b0, source_32bc;
  uint32_t blocked;
  uint32_t dy, dx, dw, dh, magh, magv;
  uint32_t timing_502770, timing_23ac08;
  uint8_t region, mode_21af94, mode_70003300, reserved;
} PopsProgressiveState;

void pops_progressive_update(PopsProgressiveState *state);

/* Original-address live state adapter candidate. Not installed by the
 * launcher yet: the mid-function register bridge and loader sequencing must
 * be verified first. Host tests replace only these memory operations. */
uint64_t pops_progressive_live(void);

#endif
