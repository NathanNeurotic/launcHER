#include "pops_progressive.h"

#ifdef POPS_PROGRESSIVE_TEST_IO
extern uint64_t pops_progressive_read(uint32_t address, unsigned width);
extern void pops_progressive_write(uint32_t address, uint64_t value, unsigned width);
#else
static uint64_t pops_progressive_read(uint32_t address, unsigned width) {
  if (width == 1)
    return *(volatile uint8_t *)(uintptr_t)address;
  if (width == 4)
    return *(volatile uint32_t *)(uintptr_t)address;
  return *(volatile uint64_t *)(uintptr_t)address;
}
static void pops_progressive_write(uint32_t address, uint64_t value, unsigned width) {
  if (width == 1)
    *(volatile uint8_t *)(uintptr_t)address = (uint8_t)value;
  else if (width == 4)
    *(volatile uint32_t *)(uintptr_t)address = (uint32_t)value;
  else
    *(volatile uint64_t *)(uintptr_t)address = value;
}
#endif

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

uint64_t pops_progressive_live(void) {
  if (pops_progressive_read(0x85a9ac, 4))
    return pops_progressive_read(0x70003290, 8);

  pops_progressive_write(0x502680, 0x50, 8);
  pops_progressive_write(0x70003300, 0x50, 1);
  pops_progressive_write(0x21af94, 0x50, 1);
  pops_progressive_write(0x502680, 0x8a3a2, 8);
  pops_progressive_write(0x502770, 0x8a3a2, 4);
  pops_progressive_write(0x502680, 0x69403, 8);
  pops_progressive_write(0x23ac08, 0x69403, 4);

  uint8_t region = (uint8_t)pops_progressive_read(0x127ff52, 1);
  uint32_t dy = (uint32_t)pops_progressive_read(0x700032a8, 4) >> 1;
  if (region != 'E')
    dy *= 3;
  pops_progressive_write(0x502690, dy, 4);
  pops_progressive_write(0x502688, 0, 4);
  pops_progressive_write(0x50269c, 1, 4);
  pops_progressive_write(0x502694, (uint32_t)pops_progressive_read(0x700032b0, 4) << 1, 4);

  uint32_t width = (uint32_t)pops_progressive_read(0x700032bc, 4);
  switch (width) {
  case 640:
    pops_progressive_write(0x502688, 1, 4);
    pops_progressive_write(0x50268c, width >> 1, 4);
    pops_progressive_write(0x502698, 1280, 4);
    break;
  case 512:
    pops_progressive_write(0x502688, 1, 4);
    pops_progressive_write(0x50268c, 444, 4);
    pops_progressive_write(0x502698, 1024, 4);
    break;
  case 384:
    pops_progressive_write(0x502688, 2, 4);
    pops_progressive_write(0x50268c, width, 4);
    pops_progressive_write(0x502698, 1152, 4);
    break;
  case 320:
  case 256:
    pops_progressive_write(0x502688, width == 320 ? 3 : 4, 4);
    pops_progressive_write(0x50268c, 320, 4);
    pops_progressive_write(0x502698, (uint32_t)pops_progressive_read(0x700032ac, 4) >> 1, 4);
    break;
  }
  if (!pops_progressive_read(0x502688, 4))
    return pops_progressive_read(0x70003290, 8);

  uint32_t dh = (uint32_t)pops_progressive_read(0x502694, 4) - 1;
  uint32_t dw = (uint32_t)pops_progressive_read(0x502698, 4) - 1;
  uint32_t magv = (uint32_t)pops_progressive_read(0x50269c, 4);
  uint32_t magh = (uint32_t)pops_progressive_read(0x502688, 4);
  dy = (uint32_t)pops_progressive_read(0x502690, 4);
  uint32_t dx = (uint32_t)pops_progressive_read(0x50268c, 4);
  return (uint64_t)dh << 44 | (uint64_t)dw << 32 | (uint64_t)magv << 27 |
         (uint64_t)magh << 23 | (uint64_t)dy << 12 | dx;
}
