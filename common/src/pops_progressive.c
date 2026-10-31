#include "pops_progressive.h"

void pops_progressive_update(PopsProgressiveState *s) {
  s->display = s->fallback_display;
  if (s->blocked)
    return;

  s->mode_21af94 = 0x50;
  s->mode_70003300 = 0x50;
  s->timing_502770 = 0x8a3a2;
  s->timing_23ac08 = 0x69403;
  s->scratch = 0x69403;
  s->dy = s->source_32a8 >> 1;
  if (s->region != 'E')
    s->dy *= 3;
  s->dh = s->source_32b0 << 1;
  s->magh = 0;
  s->magv = 1;

  switch (s->source_32bc) {
  case 256:
    s->magh = 4;
    s->dx = 320;
    s->dw = s->source_32ac >> 1;
    break;
  case 320:
    s->magh = 3;
    s->dx = 320;
    s->dw = s->source_32ac >> 1;
    break;
  case 384:
    s->magh = 2;
    s->dx = 384;
    s->dw = 1152;
    break;
  case 512:
    s->magh = 1;
    s->dx = 444;
    s->dw = 1024;
    break;
  case 640:
    s->magh = 1;
    s->dx = 320;
    s->dw = 1280;
    break;
  default:
    return;
  }

  s->display = (uint64_t)(uint32_t)(s->dh - 1) << 44 |
               (uint64_t)(uint32_t)(s->dw - 1) << 32 |
               (uint64_t)s->magv << 27 | (uint64_t)s->magh << 23 |
               (uint64_t)s->dy << 12 | s->dx;
}
