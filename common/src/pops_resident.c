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
  h.progressive_entry = get_u32(b + 28);
  h.pad_read_entry = get_u32(b + 32);
  h.pad_read_exit = get_u32(b + 36);
  h.gte_scale_entry = get_u32(b + 40);
  h.gte_divide_entry = get_u32(b + 44);
  h.gte_ultra_entry = get_u32(b + 48);

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
  if ((h.progressive_entry & 3) || h.progressive_entry < POPS_RESIDENT_BASE + h.header_size ||
      h.progressive_entry >= POPS_RESIDENT_BASE + h.file_size)
    return -ERANGE;
  if ((h.pad_read_entry & 3) || h.pad_read_entry < POPS_RESIDENT_BASE + h.header_size ||
      h.pad_read_entry >= POPS_RESIDENT_BASE + h.file_size)
    return -ERANGE;
  if ((h.pad_read_exit & 3) || h.pad_read_exit < POPS_RESIDENT_BASE + h.header_size ||
      h.pad_read_exit >= POPS_RESIDENT_BASE + h.file_size)
    return -ERANGE;
  const uint32_t gte[] = {h.gte_scale_entry, h.gte_divide_entry, h.gte_ultra_entry};
  for (unsigned i = 0; i < 3; ++i) {
    if ((gte[i] & 3) || gte[i] < POPS_RESIDENT_BASE + h.header_size ||
        gte[i] >= POPS_RESIDENT_BASE + h.file_size)
      return -ERANGE;
  }
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

  if (cfg->gs_mask & ~0x3f || cfg->gs_display_valid > 1 || cfg->progressive_requested > 1)
    return -EINVAL;
  if (cfg->progressive_requested || cfg->video_mode == POPS_VMODE_480P)
    out->flags |= POPS_RES_F_PROGRESSIVE;
  if (cfg->gs_display_valid) {
    out->gs_display = cfg->gs_display;
    out->flags |= POPS_RES_F_DISPLAY;
  }

  if (cfg->pad_override & ~3u)
    return -EINVAL;
  if (cfg->pad_override) {
    out->flags |= POPS_RES_F_PAD_ID;
    out->pad_override = cfg->pad_override;
    out->pad_id[0] = cfg->pad_id[0];
    out->pad_id[1] = cfg->pad_id[1];
  }
  if (cfg->pad_d2ls)
    out->flags |= POPS_RES_F_D2LS;
  if (cfg->widescreen > POPS_WIDESCREEN_EYEFINITY)
    return -EINVAL;
  if (cfg->widescreen) {
    out->flags |= POPS_RES_F_WIDESCREEN;
    out->gte_divisor = cfg->widescreen == POPS_WIDESCREEN_EYEFINITY ? 4 : 100;
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

uint32_t pops_resident_progressive_interlace(const PopsConfig *cfg) {
  if (!cfg)
    return 0;
  return cfg->hdtv_fix ? 0x24040001 :
           (cfg->original_tokens & POPS_TOK_NOHDTVFIX) ? 0x32240001 : 0x24040000;
}

int pops_resident_hook_progressive(void *staged_core, size_t core_size,
                                    uint32_t entry, uint32_t interlace) {
  uint8_t *core = staged_core;
  static const uint32_t sites[] = {0x21a094, 0x21a098, 0x21af94, 0x23acb0, 0x23ad0c};
  if (!core || (entry & 3) || entry < POPS_RESIDENT_BASE || entry >= POPS_RESIDENT_LIMIT ||
      (interlace != 0x24040000 && interlace != 0x24040001 && interlace != 0x32240001))
    return -EINVAL;
  if (core_size < sites[4] - POPS_CORE_BASE + 4)
    return -ERANGE;
  uint32_t jump = 0x08000000u | (entry >> 2);
  uint32_t expected_arg = interlace == 0x24040000 ? 0x32240001 : interlace;
  for (unsigned i = 0; i < 5; ++i) {
    uint32_t cur = i == 2 ? core[sites[i] - POPS_CORE_BASE] : get_u32(core + sites[i] - POPS_CORE_BASE);
    if (i == 0 ? (cur != 0xde050010 && cur != jump) :
        i == 1 ? cur != 0x3c031200 : i == 2 ? (cur != 2 && cur != 0x50) :
        (cur != expected_arg && cur != interlace))
      return -EILSEQ;
  }
  put_u32(core + sites[0] - POPS_CORE_BASE, jump);
  core[sites[2] - POPS_CORE_BASE] = 0x50;
  put_u32(core + sites[3] - POPS_CORE_BASE, interlace);
  put_u32(core + sites[4] - POPS_CORE_BASE, interlace);
  return 0;
}

int pops_resident_hook_pads(void *staged_core, size_t core_size, uint32_t flags,
                            uint32_t read_entry, uint32_t read_exit) {
  uint8_t *core = staged_core;
  /* The pad state references the resident code relies on. */
  static const uint32_t state_sites[][2] = {
    {0x0020c648, 0x3c070050}, /* lui   $a3, 0x50 */
    {0x0020c64c, 0x24e77000}, /* addiu $a3, $a3, 0x7000 */
    {0x0020c6c8, 0x8ce80034}, /* lw    $t0, 0x34($a3): the reported ID */
  };
  /* The pad read around the two hook words. */
  static const uint32_t read_sites[][2] = {
    {0x00237798, 0x0080382d}, /* move  $a3, $a0 */
    {0x002377a0, 0x2404001c}, /* addiu $a0, $zero, 0x1c */
    {0x00237810, 0x27bd0030}, /* addiu $sp, $sp, 0x30 (exit delay slot) */
  };
  if (!core)
    return -EINVAL;
  if (!(flags & (POPS_RES_F_PAD_ID | POPS_RES_F_D2LS)))
    return 0;
  if (core_size < POPS_PAD_READ_EXIT_ADDR + 8 - POPS_CORE_BASE)
    return -ERANGE;
  for (unsigned i = 0; i < 3; ++i) {
    if (get_u32(core + state_sites[i][0] - POPS_CORE_BASE) != state_sites[i][1])
      return -EILSEQ;
  }
  if (!(flags & POPS_RES_F_D2LS))
    return 0;

  if ((read_entry & 3) || read_entry < POPS_RESIDENT_BASE || read_entry >= POPS_RESIDENT_LIMIT ||
      (read_exit & 3) || read_exit < POPS_RESIDENT_BASE || read_exit >= POPS_RESIDENT_LIMIT)
    return -EINVAL;
  for (unsigned i = 0; i < 3; ++i) {
    if (get_u32(core + read_sites[i][0] - POPS_CORE_BASE) != read_sites[i][1])
      return -EILSEQ;
  }
  uint8_t *entry = core + POPS_PAD_READ_ENTRY_ADDR - POPS_CORE_BASE;
  uint8_t *ret = core + POPS_PAD_READ_EXIT_ADDR - POPS_CORE_BASE;
  uint32_t jump_entry = 0x08000000u | (read_entry >> 2);
  uint32_t jump_exit = 0x08000000u | (read_exit >> 2);
  uint32_t cur_entry = get_u32(entry), cur_exit = get_u32(ret);
  if ((cur_entry != 0x24030070 && cur_entry != jump_entry) ||
      (cur_exit != 0x03e00008 && cur_exit != jump_exit))
    return -EILSEQ;
  put_u32(entry, jump_entry);
  put_u32(ret, jump_exit);
  return 0;
}

int pops_resident_hook_widescreen(void *staged_core, size_t core_size, uint8_t mode,
                                  const PopsResidentHeader *hdr) {
  uint8_t *core = staged_core;
  /* Neighbours the stubs rely on: the delay slots they let run, the stores
   * they return to, and the next writes of $v0/$v1 (dead registers). */
  static const uint32_t fixed[][2] = {
    {0x002089ac, 0xac890068}, /* sw    $t1, 0x68($a0) (delay slot) */
    {0x002089b0, 0xac8a006c}, /* sw    $t2, 0x6c($a0) (resume) */
    {0x002089b8, 0x24028000}, /* addiu $v0, $zero, -0x8000 */
    {0x002089bc, 0x24037fff}, /* addiu $v1, $zero, 0x7fff */
    {0x00208a30, 0xac890028}, /* sw    $t1, 0x28($a0) (delay slot) */
    {0x00208a34, 0xac8a002c}, /* sw    $t2, 0x2c($a0) (resume) */
    {0x00208a38, 0x3402ffff}, /* ori   $v0, $zero, 0xffff */
    {0x00208a3c, 0x3c038006}, /* lui   $v1, 0x8006 */
  };
  if (!core || !hdr || mode > POPS_WIDESCREEN_EYEFINITY)
    return -EINVAL;
  if (mode == POPS_WIDESCREEN_NONE)
    return 0;
  const uint32_t entries[] = {hdr->gte_scale_entry, hdr->gte_divide_entry, hdr->gte_ultra_entry};
  for (unsigned i = 0; i < 3; ++i) {
    if ((entries[i] & 3) || entries[i] < POPS_RESIDENT_BASE || entries[i] >= POPS_RESIDENT_LIMIT)
      return -EINVAL;
  }
  if (core_size < POPS_GTE_IR1_STORE_ADDR + 0x14 - POPS_CORE_BASE)
    return -ERANGE;
  for (unsigned i = 0; i < sizeof(fixed) / sizeof(fixed[0]); ++i) {
    if (get_u32(core + fixed[i][0] - POPS_CORE_BASE) != fixed[i][1])
      return -EILSEQ;
  }
  uint32_t j_scale = 0x08000000u | (hdr->gte_scale_entry >> 2);
  uint32_t j_divide = 0x08000000u | (hdr->gte_divide_entry >> 2);
  uint32_t j_ultra = 0x08000000u | (hdr->gte_ultra_entry >> 2);
  uint8_t *mac1 = core + POPS_GTE_MAC1_STORE_ADDR - POPS_CORE_BASE;
  uint8_t *ir1 = core + POPS_GTE_IR1_STORE_ADDR - POPS_CORE_BASE;
  uint32_t cur = get_u32(mac1);
  if (cur != 0xac880064 && cur != j_scale && cur != j_divide)
    return -EILSEQ;
  cur = get_u32(ir1);
  if (cur != 0xac880024 && cur != j_ultra)
    return -EILSEQ;
  put_u32(mac1, mode == POPS_WIDESCREEN_EYEFINITY ? j_divide : j_scale);
  put_u32(ir1, mode == POPS_WIDESCREEN_ULTRA ? j_ultra : 0xac880024);
  return 0;
}
