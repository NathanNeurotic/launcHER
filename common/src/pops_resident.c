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

static int cheat_is_condition(uint8_t type) {
  return (type >= 0xD0 && type <= 0xD3) || type == 0xE0 || type == 0xE1;
}

static int cheat_is_write(uint8_t type) {
  return type == 0x80 || type == 0x30 || type == 0x10 || type == 0x20;
}

/* The PS1 store a repeat's leftover write uses after a PS2 write of this
 * size: sb, sh or sw. */
static uint8_t cheat_store_of_size(unsigned size) {
  return size == 0 ? 0x30 : size == 1 ? 0x80 : POPS_CHEAT_W32;
}

/* POPStarter emits each code as a few instructions that leave values in
 * k0/k1; a $D0 loads its compare into them and its branch is emitted only
 * in front of the next PS1 write. The compiled codes keep that shape:
 * LOAD16 for the $D0, BNE in front of the code it gates, so whatever runs
 * in between (PS2 writes) changes the compare exactly as it does there. */
uint16_t pops_cheats_compile(const PopsCheatEntry *in, uint16_t count, PopsCheatEntry *out,
                             uint16_t capacity) {
  int pending = 0; /* a $D0 branch waits for the next PS1 write */
  /* After a PS2 conditional, POPStarter compiles the rest of the file in a
   * reduced copy of its loop, one per kind of conditional, that knows only
   * writes: 0 (none yet), or the conditional's type (EE, SPR, PS1SPR). */
  unsigned nested = 0;
  uint16_t n = 0;
  int repeat = -1, stash = -1;

  /* Each code yields at most two compiled ones (a write may take a branch
   * in front), plus a repeat copy and the leftover expansion at the end. */
  if (!in || !out || capacity < 2u * count + 4u)
    return 0;
  for (uint16_t i = 0; i < count; ++i) {
    if (in[i].type == 0xC0) {
      out[n] = in[i];
      out[n].address &= POPS_CHEAT_ADDR_MASK;
      out[n].value &= 0xFFFFu;
      out[n++].skip = 0;
      break;
    }
  }

  uint8_t last_write = 0;
  for (uint32_t i = 0; i <= count; ++i) {
    PopsCheatEntry e;
    if (i == count) {
      /* A repeat with no write after it still expands, onto address 0 and
       * value 0, with the store of the last write before it (or none). */
      if (repeat < 0 || !last_write)
        break;
      memset(&e, 0, sizeof(e));
      e.type = last_write;
    } else {
      e = in[i];
      e.skip = 0;
    }
    if (POPS_CHEAT_IS_PS2(e.type)) {
      unsigned kind = e.type & 0xFCu;
      if (e.cond != POPS_CHEAT_COND_NONE) {
        /* Dropped behind a pending branch, a pending repeat, or an earlier
         * PS2 conditional. Its own branch is fixed: it skips the next code. */
        if (pending || repeat >= 0 || nested)
          continue;
        nested = kind;
        e.skip = 1;
        out[n++] = e;
        continue;
      }
      if (nested) {
        /* What each reduced loop still knows: EE writes always, $S writes
         * after a $S or $T conditional, $T writes after a $T or $=/$!. */
        if ((kind == POPS_CHEAT_SPR && nested == POPS_CHEAT_EE) ||
            (kind == POPS_CHEAT_PS1SPR && nested == POPS_CHEAT_SPR))
          continue;
      } else {
        /* Dropped while a repeat waits. A $0/$1/$2 write is placed even
         * between a $D0 and its branch; a $S/$T write there is dropped. */
        if (repeat >= 0 || (pending && kind != POPS_CHEAT_EE))
          continue;
      }
      last_write = cheat_store_of_size(e.type & 3u);
      out[n++] = e;
      continue;
    }
    e.address &= e.type == 0x50 ? 0xFFFFu : POPS_CHEAT_ADDR_MASK;
    e.value &= 0xFFFFu;
    if (cheat_is_condition(e.type)) {
      /* Dropped behind a pending branch, a pending repeat or a PS2
       * conditional. */
      if (pending || repeat >= 0 || nested)
        continue;
      pending = 1;
      e.type = POPS_CHEAT_LOAD16;
      out[n++] = e;
      /* POPStarter keeps the first repeat it skipped, and an emitted
       * conditional makes it the pending repeat for the code it gates. */
      if (stash >= 0) {
        repeat = stash;
        stash = -1;
      }
    } else if (e.type == 0x50) {
      if (nested)
        continue; /* after a PS2 conditional, repeats are ignored */
      if (repeat < 0)
        repeat = (int)i;
      else if (stash < 0)
        stash = (int)i; /* skipped while the first waits, kept for later */
    } else if (cheat_is_write(e.type) || e.type == POPS_CHEAT_W32) {
      last_write = e.type;
      int block = repeat >= 0 ? 2 : 1;
      if (pending) {
        PopsCheatEntry b;
        memset(&b, 0, sizeof(b));
        b.type = POPS_CHEAT_BNE;
        b.skip = (uint8_t)block;
        out[n++] = b;
        /* After a repeat block a leftover branch compares again, in front
         * of the next PS1 write: k0/k1 then hold the block's last write
         * (never equal), or the $D0's compare when the block wrote nothing. */
        pending = block == 2;
      }
      if (repeat >= 0) {
        out[n] = in[repeat];
        out[n].address &= 0xFFFFu;
        out[n].value &= 0xFFFFu;
        out[n++].skip = 0;
      }
      out[n++] = e;
      repeat = -1;
    }
    /* $C0 is hoisted above; anything else is not a code. */
  }
  return n;
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
  h.gp1_entry = get_u32(b + 52);

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
  const uint32_t gte[] = {h.gte_scale_entry, h.gte_divide_entry, h.gte_ultra_entry, h.gp1_entry};
  for (unsigned i = 0; i < 4; ++i) {
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
  if (cfg->set_timings)
    out->flags |= POPS_RES_F_TIMINGS | POPS_RES_F_TIMINGS_SAVE;
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
    out->cheat_count = pops_cheats_compile(cfg->cheats, count, out->cheats, POPS_CHEAT_COMPILED_MAX);
    out->safe_mode = cfg->safe_mode & (POPS_SAFE_MODE_BOOT | POPS_SAFE_MODE_2);
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

int pops_resident_hook_gp1(void *staged_core, size_t core_size, uint32_t entry) {
  uint8_t *core = (uint8_t *)staged_core;
  static const uint32_t fixed[][2] = {
    {0x0021a630, 0x5060000b}, /* beql  $v1, $zero, 0x21a660 (EIE clear) */
    {0x0021a638, 0x3c030001}, /* lui   $v1, 1 */
    {0x0021a640, 0x42000039}, /* di (the jal's delay slot) */
    {0x0021a644, 0x0000040f}, /* sync.p */
    {0x0021a648, 0x40026000}, /* mfc0  $v0, Status */
    {0x0021a64c, 0x00431024}, /* and   $v0, $v0, $v1 */
  };
  if (!core)
    return -EINVAL;
  if ((entry & 3) || entry < POPS_RESIDENT_BASE || entry >= POPS_RESIDENT_LIMIT)
    return -EINVAL;
  if (core_size < 0x0021a650 - POPS_CORE_BASE)
    return -ERANGE;
  for (unsigned i = 0; i < sizeof(fixed) / sizeof(fixed[0]); ++i) {
    if (get_u32(core + fixed[i][0] - POPS_CORE_BASE) != fixed[i][1])
      return -EILSEQ;
  }
  uint8_t *site = core + POPS_GP1_HOOK_ADDR - POPS_CORE_BASE;
  uint32_t jal = 0x0c000000u | ((entry >> 2) & 0x03ffffffu);
  uint32_t cur = get_u32(site);
  if (cur != POPS_GP1_HOOK_PRISTINE && cur != jal)
    return -EILSEQ;
  put_u32(site, jal);
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
