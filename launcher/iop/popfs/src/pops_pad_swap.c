#include "pops_pad_swap.h"

void pops_pad_swap_init(pops_pad_swap *sw, pops_pad_swap_fire_fn fire, void *ctx,
                        unsigned required_frames, int armed) {
  if (!sw)
    return;
  sw->fire = fire;
  sw->ctx = ctx;
  sw->required_frames = required_frames ? required_frames : 1;
  sw->held = 0;
  sw->armed = armed;
  sw->waiting_release = 0;
}

void pops_pad_swap_disarm(pops_pad_swap *sw) {
  if (!sw)
    return;
  sw->armed = 0;
  sw->held = 0;
  sw->waiting_release = 0;
}

int pops_pad_swap_feed(pops_pad_swap *sw, uint16_t buttons, int valid) {
  uint16_t pressed;
  if (!sw || !sw->fire)
    return 0;
  pressed = (uint16_t)(~buttons);
  if (!valid || (pressed & POPS_PAD_SWAP_COMBO) != POPS_PAD_SWAP_COMBO) {
    /* Release (or unreadable pad): re-arm only after the full combo lifts. */
    sw->held = 0;
    sw->waiting_release = 0;
    return 0;
  }
  if (sw->waiting_release || !sw->armed)
    return 0;
  if (++sw->held < sw->required_frames)
    return 0;
  {
    int res = sw->fire(sw->ctx);
    /* Success or failure, one attempt per press: a failed swap (e.g. busy
     * while the game reads the disc) waits for the combo to lift. */
    sw->waiting_release = 1;
    sw->held = 0;
    return res == 0 ? 1 : res;
  }
}
