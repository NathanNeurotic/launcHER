#include "pops_modes_patches.h"
#include <errno.h>
#include <string.h>

#define POPS_CORE_BASE_ADDR 0x00200000

static int write_u8(void *base, size_t size, uint32_t addr, uint8_t val) {
  if (addr < POPS_CORE_BASE_ADDR)
    return -EINVAL;
  uint32_t off = addr - POPS_CORE_BASE_ADDR;
  if (off + 1 > size)
    return -ERANGE;
  ((uint8_t *)base)[off] = val;
  return 0;
}

static int write_u16(void *base, size_t size, uint32_t addr, uint16_t val) {
  if (addr < POPS_CORE_BASE_ADDR)
    return -EINVAL;
  uint32_t off = addr - POPS_CORE_BASE_ADDR;
  if (off + 2 > size)
    return -ERANGE;
  *(uint16_t *)((uint8_t *)base + off) = val;
  return 0;
}

static int write_u32(void *base, size_t size, uint32_t addr, uint32_t val) {
  if (addr < POPS_CORE_BASE_ADDR)
    return -EINVAL;
  uint32_t off = addr - POPS_CORE_BASE_ADDR;
  if (off + 4 > size)
    return -ERANGE;
  *(uint32_t *)((uint8_t *)base + off) = val;
  return 0;
}

/* Measured POPSTARTER FUN_008dc2c4: modes 1..5 and 7, widths and
 * order retained. Expected bytes are from the supported external POPS ELF.
 * Mode 6 needs original OSD state; mode 8 has no branch in this dispatcher. */
typedef struct {
  uint8_t mode;
  uint32_t address, expected, replacement;
  uint8_t width;
} CompatPatch;
static const CompatPatch compat_patches[] = {
  {1, 0x00210314, 0x00000000, 0x3c02005a, 4},
  {1, 0x00210318, 0x8f828228, 0x24030082, 4},
  {1, 0x0021031c, 0x00000000, 0xa043c201, 4},
  {1, 0x00210320, 0x00000000, 0x2403ffff, 4},
  {1, 0x00210324, 0x00000000, 0x8f828228, 4},
  {1, 0x00210328, 0x00000000, 0x00000000, 4},
  {1, 0x0021032c, 0x1443fffa, 0x1443fffd, 4},
  {2, 0x00210314, 0x00000000, 0x3c02005a, 4},
  {2, 0x00210318, 0x8f828228, 0x240322e8, 4},
  {2, 0x0021031c, 0x00000000, 0xa443c200, 4},
  {2, 0x00210320, 0x00000000, 0x2403ffff, 4},
  {2, 0x00210324, 0x00000000, 0x8f828228, 4},
  {2, 0x00210328, 0x00000000, 0x00000000, 4},
  {2, 0x0021032c, 0x1443fffa, 0x1443fffd, 4},
  {2, 0x0020083c, 0x0441000a, 0x1000000a, 4},
  {2, 0x0020085c, 0x1000fffa, 0x00000000, 4},
  {2, 0x00200844, 0x00000000, 0x3c08005a, 4},
  {2, 0x00200848, 0x00000000, 0x240322c0, 4},
  {2, 0x00200850, 0x00000000, 0xa503c200, 4},
  {2, 0x00200858, 0x00000000, 0x0c0836ee, 4},
  {2, 0x00200860, 0x00000000, 0x10003590, 4},
  {2, 0x0020de9c, 0x0c0836ee, 0x1000ca69, 4},
  {3, 0x00210314, 0x00000000, 0x3c02005a, 4},
  {3, 0x00210318, 0x8f828228, 0x240300c1, 4},
  {3, 0x0021031c, 0x00000000, 0xa043c200, 4},
  {3, 0x00210320, 0x00000000, 0x2403ffff, 4},
  {3, 0x00210324, 0x00000000, 0x8f828228, 4},
  {3, 0x00210328, 0x00000000, 0x00000000, 4},
  {3, 0x0021032c, 0x1443fffa, 0x1443fffd, 4},
  {4, 0x0021af70, 0x00000064, 0x00000000, 1},
  {5, 0x0020083c, 0x0441000a, 0x1000000a, 4},
  {5, 0x00200850, 0x00000000, 0x3c05005a, 4},
  {5, 0x00200854, 0x00000000, 0x24030022, 4},
  {5, 0x00200858, 0x00000000, 0xa0a3c201, 4},
  {5, 0x0020085c, 0x1000fffa, 0x00000000, 4},
  {5, 0x00200860, 0x00000000, 0x10002d13, 4},
  {5, 0x0020bcac, 0x00000000, 0x1000d2e8, 4},
  {7, 0x0021e45c, 0x00000000, 0x00000040, 1},
};

int pops_apply_compat_modes(void *staged_core, size_t core_size, uint8_t modes_mask) {
  uint8_t *bytes = staged_core;
  size_t i;
  unsigned j;
  if (!bytes)
    return -EINVAL;
  if (modes_mask & ((1 << 5) | (1 << 7)))
    return -ENOTSUP;
  /* Validate all sites before changing any. Overlapping modes deliberately
   * retain original ascending dispatch order, with later writes winning. */
  for (i = 0; i < sizeof(compat_patches) / sizeof(compat_patches[0]); ++i) {
    const CompatPatch *p = &compat_patches[i];
    uint32_t actual = 0;
    size_t offset = p->address - POPS_CORE_BASE_ADDR;
    if (!(modes_mask & (1 << (p->mode - 1))))
      continue;
    if (offset > core_size || p->width > core_size - offset)
      return -ERANGE;
    for (j = 0; j < p->width; ++j)
      actual |= (uint32_t)bytes[offset + j] << (8 * j);
    if (actual != p->expected)
      return -EINVAL;
  }
  for (i = 0; i < sizeof(compat_patches) / sizeof(compat_patches[0]); ++i) {
    const CompatPatch *p = &compat_patches[i];
    if (!(modes_mask & (1 << (p->mode - 1))))
      continue;
    for (j = 0; j < p->width; ++j)
      bytes[p->address - POPS_CORE_BASE_ADDR + j] = (uint8_t)(p->replacement >> (8 * j));
  }
  return 0;
}

int pops_apply_video_overrides(void *staged_core, size_t core_size,
                               uint8_t video_mode, uint8_t hdtv_fix,
                               int16_t x_offset, int16_t y_offset) {
  if (!staged_core || core_size < 0x250000)
    return -EINVAL;

  /* PAL to NTSC conversion */
  if (video_mode == POPS_VMODE_PAL2NTSC) {
    write_u8(staged_core, core_size, 0x0021af94, 3);
    write_u32(staged_core, core_size, 0x00502770, 0x000a6300);
    write_u8(staged_core, core_size, 0x0023b018, 0x6b);
    write_u16(staged_core, core_size, 0x0023b01c, 0x02cb);
  } else if (video_mode == POPS_VMODE_NTSC2PAL) {
    write_u8(staged_core, core_size, 0x0021af94, 2);
    write_u32(staged_core, core_size, 0x00502770, 0x000c7200);
    write_u8(staged_core, core_size, 0x0023b018, 0x7f);
    write_u16(staged_core, core_size, 0x0023b01c, 0x0357);
  } else if (video_mode == POPS_VMODE_480P) {
    write_u32(staged_core, core_size, 0x002061A0, 0x24020001); /* progressive */
    write_u32(staged_core, core_size, 0x002061E0, 0x24050000); /* non-interlaced */
  } else if (video_mode == POPS_VMODE_480I) {
    write_u32(staged_core, core_size, 0x002061A0, 0x24020002);
  } else if (video_mode == POPS_VMODE_576P) {
    write_u32(staged_core, core_size, 0x002061A0, 0x24020003);
  } else if (video_mode == POPS_VMODE_576I) {
    write_u32(staged_core, core_size, 0x002061A0, 0x24020004);
  } else if (video_mode == POPS_VMODE_240P) {
    write_u32(staged_core, core_size, 0x002061A0, 0x24020000); /* 240p progressive */
    write_u32(staged_core, core_size, 0x002061E0, 0x24050000); /* non-interlaced */
  }

  if (hdtv_fix) {
    write_u32(staged_core, core_size, 0x002061DC, 0x24040001);
  }

  if (x_offset != 0) {
    write_u16(staged_core, core_size, 0x00206214, (uint16_t)x_offset);
  }
  if (y_offset != 0) {
    write_u16(staged_core, core_size, 0x00206218, (uint16_t)y_offset);
  }

  return 0;
}

int pops_apply_smooth(void *staged_core, size_t core_size) {
  if (!staged_core || core_size < 0x250000)
    return -EINVAL;
  /* Modify GS texture filter flag (TEX0.TFX bilinear) */
  return write_u32(staged_core, core_size, 0x00205E00, 0x24020001);
}

int pops_apply_widescreen(void *staged_core, size_t core_size) {
  if (!staged_core || core_size < 0x250000)
    return -EINVAL;
  /* Horizontal 16:9 projection aspect factor patch */
  return write_u32(staged_core, core_size, 0x00205B00, 0x24020C00);
}

int pops_apply_dither_off(void *staged_core, size_t core_size) {
  if (!staged_core || core_size < 0x250000)
    return -EINVAL;
  /* Disable Graphics Synthesizer dithering */
  return write_u32(staged_core, core_size, 0x00205D58, 0x00000000);
}

int pops_apply_throttling(void *staged_core, size_t core_size, uint8_t fast_mips, uint8_t slow_mips) {
  if (!staged_core || core_size < 0x250000)
    return -EINVAL;

  if (fast_mips) {
    /* NOP throttle wait loop */
    return write_u32(staged_core, core_size, 0x002010A0, 0x00000000);
  } else if (slow_mips) {
    /* Multiplier for throttle wait loop */
    return write_u32(staged_core, core_size, 0x002010A0, 0x24040004);
  }
  return 0;
}

int pops_apply_bios_shell(void *staged_core, size_t core_size) {
  if (!staged_core || core_size < 0x250000)
    return -EINVAL;
  /* Force boot into the PS1 BIOS shell */
  return write_u8(staged_core, core_size, 0x00210cf8, 0x01);
}

int pops_apply_libcrypt_bypass(void *staged_core, size_t core_size) {
  if (!staged_core || core_size < 0x250000)
    return -EINVAL;
  /* NOP subchannel check routine and force success return */
  write_u32(staged_core, core_size, 0x0020C1F0, 0x00000000);
  write_u32(staged_core, core_size, 0x0020CFB0, 0x24020000);
  return 0;
}

int pops_check_igr_combo_type(uint16_t buttons_active_low, uint8_t igr_type) {
  if (igr_type == 0)
    return 0;
  uint16_t pressed = (uint16_t)(~buttons_active_low);
  uint16_t target = (igr_type == 2) ? POPS_IGR2_COMBO : POPS_IGR_COMBO;
  return ((pressed & target) == target);
}

int pops_check_igr_combo(uint16_t buttons_active_low) {
  return pops_check_igr_combo_type(buttons_active_low, 1);
}

int pops_check_disc_swap_combo(uint16_t buttons_active_low) {
  uint16_t pressed = (uint16_t)(~buttons_active_low);
  return ((pressed & POPS_SWAP_COMBO) == POPS_SWAP_COMBO);
}

int pops_generate_subq(uint32_t lba, uint16_t libcrypt_key, uint8_t out_subq[12]) {
  if (!out_subq)
    return -EINVAL;

  memset(out_subq, 0, 12);
  out_subq[0] = 0x41; /* Track 1, Mode 1 data */
  out_subq[1] = 0x01;
  out_subq[2] = 0x01;

  uint32_t sec = lba / 75;
  uint32_t frm = lba % 75;
  uint32_t min = sec / 60;
  sec %= 60;

  uint8_t m_bcd = (uint8_t)(((min / 10) << 4) | (min % 10));
  uint8_t s_bcd = (uint8_t)(((sec / 10) << 4) | (sec % 10));
  uint8_t f_bcd = (uint8_t)(((frm / 10) << 4) | (frm % 10));

  out_subq[3] = m_bcd;
  out_subq[4] = s_bcd;
  out_subq[5] = f_bcd;
  out_subq[6] = 0x00;
  out_subq[7] = m_bcd;
  out_subq[8] = s_bcd;
  out_subq[9] = f_bcd;

  if (libcrypt_key != 0 && lba >= 12 && lba <= 20) {
    out_subq[10] = (uint8_t)(libcrypt_key >> 8);
    out_subq[11] = (uint8_t)(libcrypt_key & 0xFF);
  }
  return 0;
}

int pops_cheat_engine_tick(void *ps1_ram_base, const PopsCheatEntry *cheats, uint16_t cheat_count) {
  if (!ps1_ram_base || !cheats || cheat_count == 0)
    return 0;

  uint16_t i = 0;
  while (i < cheat_count) {
    uint32_t addr = cheats[i].address & 0x001FFFFF;
    uint8_t type = cheats[i].type;
    uint16_t val = cheats[i].value;

    /* 16-bit conditionals */
    if (type == 0xD0 || type == 0xD1 || type == 0xD2 || type == 0xD3) {
      if (addr + 2 > 0x00200000) {
        i += 2;
        continue;
      }
      uint16_t cur = *(uint16_t *)((uint8_t *)ps1_ram_base + (addr & ~1U));
      int cond = 0;
      if (type == 0xD0) cond = (cur == val);
      else if (type == 0xD1) cond = (cur != val);
      else if (type == 0xD2) cond = (cur < val);
      else if (type == 0xD3) cond = (cur > val);

      if (!cond) {
        i += 2;
        continue;
      }
      i++;
      continue;
    }

    /* 8-bit conditionals */
    if (type == 0xE0 || type == 0xE1) {
      if (addr + 1 > 0x00200000) {
        i += 2;
        continue;
      }
      uint8_t cur = *(uint8_t *)((uint8_t *)ps1_ram_base + addr);
      uint8_t target = (uint8_t)val;
      int cond = 0;
      if (type == 0xE0) cond = (cur == target);
      else if (type == 0xE1) cond = (cur != target);

      if (!cond) {
        i += 2;
        continue;
      }
      i++;
      continue;
    }

    /* 16-bit writes */
    if (type == 0x80 || type == 0x10) {
      if (addr + 2 <= 0x00200000) {
        *(uint16_t *)((uint8_t *)ps1_ram_base + (addr & ~1U)) = val;
      }
    }
    /* 8-bit writes */
    else if (type == 0x30 || type == 0x20) {
      if (addr + 1 <= 0x00200000) {
        *(uint8_t *)((uint8_t *)ps1_ram_base + addr) = (uint8_t)val;
      }
    }

    i++;
  }
  return 0;
}

int pops_apply_cheats(void *ps1_ram_base, const PopsCheatEntry *cheats, uint16_t cheat_count) {
  return pops_cheat_engine_tick(ps1_ram_base, cheats, cheat_count);
}

int pops_apply_all_config_patches(void *staged_core, size_t core_size, const PopsConfig *cfg) {
  if (!staged_core || !cfg)
    return -EINVAL;

  if (cfg->compat_modes) {
    int result = pops_apply_compat_modes(staged_core, core_size, cfg->compat_modes);
    if (result)
      return result;
  }

  if (cfg->video_mode || cfg->hdtv_fix || cfg->x_offset || cfg->y_offset)
    pops_apply_video_overrides(staged_core, core_size, cfg->video_mode, cfg->hdtv_fix,
                               cfg->x_offset, cfg->y_offset);

  if (cfg->smooth)
    pops_apply_smooth(staged_core, core_size);

  if (cfg->widescreen)
    pops_apply_widescreen(staged_core, core_size);

  if (cfg->dither_off)
    pops_apply_dither_off(staged_core, core_size);

  if (cfg->fast_mips || cfg->slow_mips)
    pops_apply_throttling(staged_core, core_size, cfg->fast_mips, cfg->slow_mips);

  if (cfg->no_boot)
    pops_apply_bios_shell(staged_core, core_size);

  return 0;
}
