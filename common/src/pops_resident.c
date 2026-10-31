#include "pops_resident.h"
#include "pops_modes_patches.h"
#include <errno.h>
#include <string.h>

#define POPS_CORE_BASE UINT32_C(0x00200000)

static uint32_t get_u32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void put_u32(uint8_t *p, uint32_t v) {
  p[0] = (uint8_t)v;
  p[1] = (uint8_t)(v >> 8);
  p[2] = (uint8_t)(v >> 16);
  p[3] = (uint8_t)(v >> 24);
}

int pops_resident_check_image(const void *image, size_t image_len, PopsResidentHeader *out) {
  const uint8_t *b = (const uint8_t *)image;
  if (!b || image_len < sizeof(PopsResidentHeader))
    return -EINVAL;

  PopsResidentHeader h;
  h.magic = get_u32(b);
  h.version = (uint16_t)(b[4] | (b[5] << 8));
  h.header_size = (uint16_t)(b[6] | (b[7] << 8));
  h.file_size = get_u32(b + 8);
  h.image_size = get_u32(b + 12);
  h.vblank_entry = get_u32(b + 16);
  h.config_addr = get_u32(b + 20);
  h.display_entry = get_u32(b + 24);

  if (h.magic != POPS_RESIDENT_MAGIC || h.version != POPS_RESIDENT_VERSION ||
      h.header_size != sizeof(PopsResidentHeader))
    return -EINVAL;
  if (h.file_size != image_len || h.file_size > h.image_size ||
      h.image_size > POPS_RESIDENT_LIMIT - POPS_RESIDENT_BASE)
    return -ERANGE;
  /* The entry must be code inside the image, word aligned. */
  if ((h.vblank_entry & 3) || h.vblank_entry < POPS_RESIDENT_BASE + h.header_size ||
      h.vblank_entry >= POPS_RESIDENT_BASE + h.file_size)
    return -ERANGE;
  if ((h.display_entry & 3) || h.display_entry < POPS_RESIDENT_BASE + h.header_size ||
      h.display_entry >= POPS_RESIDENT_BASE + h.file_size)
    return -ERANGE;
  /* The configuration must fit inside the image, in its zeroed part or not. */
  if ((h.config_addr & 7) || h.config_addr < POPS_RESIDENT_BASE + h.header_size ||
      h.config_addr > POPS_RESIDENT_BASE + h.image_size - sizeof(PopsResidentConfig))
    return -ERANGE;

  if (out)
    *out = h;
  return 0;
}

int pops_resident_build_config(PopsResidentConfig *out, const PopsConfig *cfg) {
  if (!out || !cfg)
    return -EINVAL;
  memset(out, 0, sizeof(*out));
  out->pops_vblank = POPS_VBLANK_HANDLER;
  out->ram_base_ptr = POPS_PS1_RAM_BASE_PTR;

  if (cfg->gs_mask & ~0x3f || cfg->gs_display_valid > 1)
    return -EINVAL;
  if (cfg->gs_display_valid) {
    /* The progressive request also changes core video state. Do not present
     * a fixed DISPLAY bridge as its still-unimplemented resident service. */
    if (cfg->video_mode == POPS_VMODE_480P)
      return -ENOTSUP;
    out->gs_display = cfg->gs_display;
    out->flags |= POPS_RES_F_DISPLAY;
  }

  uint16_t count = cfg->cheat_count;
  if (count > POPS_MAX_CHEATS)
    return -ERANGE;
  if (count) {
    out->flags |= POPS_RES_F_CHEATS;
    out->cheat_count = count;
    memcpy(out->cheats, cfg->cheats, count * sizeof(PopsCheatEntry));
    out->safe_delay = cfg->safe_mode ? POPS_SAFE_MODE_FRAME_DELAY : 0;
  }
  return out->flags ? 1 : 0;
}

int pops_resident_hook_core(void *staged_core, size_t core_size, uint32_t entry) {
  uint8_t *core = (uint8_t *)staged_core;
  if (!core)
    return -EINVAL;
  if (core_size < POPS_VBLANK_ADDIU_ADDR - POPS_CORE_BASE + 4)
    return -ERANGE;
  if ((entry & 3) || entry < POPS_RESIDENT_BASE || entry >= POPS_RESIDENT_LIMIT)
    return -EINVAL;

  uint8_t *lui = core + (POPS_VBLANK_LUI_ADDR - POPS_CORE_BASE);
  uint8_t *addiu = core + (POPS_VBLANK_ADDIU_ADDR - POPS_CORE_BASE);
  uint16_t hi = (uint16_t)((entry + 0x8000) >> 16);
  uint16_t lo = (uint16_t)entry;
  uint32_t want_lui = 0x3c050000u | hi;
  uint32_t want_addiu = 0x24a50000u | lo;

  uint32_t cur_lui = get_u32(lui);
  uint32_t cur_addiu = get_u32(addiu);
  if (cur_lui == want_lui && cur_addiu == want_addiu)
    return 0;
  if (cur_lui != POPS_VBLANK_LUI_PRISTINE || cur_addiu != POPS_VBLANK_ADDIU_PRISTINE)
    return -EILSEQ;

  put_u32(lui, want_lui);
  put_u32(addiu, want_addiu);
  return 0;
}

int pops_resident_install(void *dest, size_t dest_len, uint32_t dest_addr,
                          const void *image, size_t image_len,
                          const PopsResidentConfig *rcfg) {
  PopsResidentHeader h;
  if (!dest || !rcfg || dest_addr != POPS_RESIDENT_BASE)
    return -EINVAL;
  int res = pops_resident_check_image(image, image_len, &h);
  if (res)
    return res;
  if (dest_len < h.image_size)
    return -ERANGE;

  uint8_t *d = (uint8_t *)dest;
  memcpy(d, image, h.file_size);
  memset(d + h.file_size, 0, h.image_size - h.file_size);
  memcpy(d + (h.config_addr - dest_addr), rcfg, sizeof(*rcfg));
  return 0;
}

int pops_resident_hook_display(void *staged_core, size_t core_size, uint32_t entry) {
  uint8_t *core = staged_core;
  static const uint32_t sites[] = {0x21a094, 0x21a098, 0x23acb0, 0x23ad0c};
  if (!core || (entry & 3) || entry < POPS_RESIDENT_BASE || entry >= POPS_RESIDENT_LIMIT)
    return -EINVAL;
  if (core_size < sites[3] - POPS_CORE_BASE + 4)
    return -ERANGE;
  uint32_t jump = 0x08000000u | (entry >> 2);
  for (unsigned i = 0; i < 4; ++i) {
    uint32_t cur = get_u32(core + sites[i] - POPS_CORE_BASE);
    if (i == 0 ? (cur != 0xde050010 && cur != jump) :
        i == 1 ? cur != 0x3c031200 : (cur != 0x32240001 && cur != 0x24040001))
      return -EILSEQ;
  }
  put_u32(core + sites[0] - POPS_CORE_BASE, jump);
  /* Config staging already restores these for a complete manual file.
   * Preserve a later file's explicit HDTVFIX instead of undoing it here. */
  return 0;
}
