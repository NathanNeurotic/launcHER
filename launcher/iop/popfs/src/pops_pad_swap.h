#ifndef POPS_PAD_SWAP_H
#define POPS_PAD_SWAP_H
/*
 * Pad-combo disc-swap detector for the popfs IOP bridge.
 *
 * The state machine is protocol-agnostic and host-testable: the sio2
 * interposition glue (pops_pad_sio2.c, IOP-only) translates controller reply
 * frames into 16-bit active-low button words and feeds them here. When the
 * SELECT+L1+R1 combo (matching POPS_SWAP_COMBO in pops_modes_patches.h) is
 * held for the debounce window, the registered fire callback runs the
 * internal OPEN_LID -> NEXT_DISC -> CLOSE_LID sequence.
 *
 * No Unicorn/console behavior is implied; the glue needs hardware validation.
 */
#include <stddef.h>
#include <stdint.h>

#define POPS_PAD_BTN_SELECT 0x0001u
#define POPS_PAD_BTN_L1     0x0400u
#define POPS_PAD_BTN_R1     0x0800u
#define POPS_PAD_SWAP_COMBO (POPS_PAD_BTN_SELECT | POPS_PAD_BTN_L1 | POPS_PAD_BTN_R1)

typedef int (*pops_pad_swap_fire_fn)(void *ctx);

typedef struct {
  pops_pad_swap_fire_fn fire;
  void *ctx;
  unsigned required_frames;
  unsigned held;
  int armed;
  int waiting_release;
} pops_pad_swap;

void pops_pad_swap_init(pops_pad_swap *sw, pops_pad_swap_fire_fn fire, void *ctx,
                        unsigned required_frames, int armed);
/* Feed one observed pad poll. `buttons` is the 16-bit active-low word;
 * valid == 0 means no readable pad this poll (treated as release).
 * Returns 1 when the swap fired, the fire callback's code on failure,
 * and 0 otherwise. */
int pops_pad_swap_feed(pops_pad_swap *sw, uint16_t buttons, int valid);
void pops_pad_swap_disarm(pops_pad_swap *sw);

/* Provided by popfs.c: the armed module-level detector, or NULL when
 * fewer than two disc images are configured. */
pops_pad_swap *pops_pad_swap_instance(void);

#endif /* POPS_PAD_SWAP_H */
