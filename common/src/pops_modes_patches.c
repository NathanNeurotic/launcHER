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

int pops_apply_compat_modes(void *staged_core, size_t core_size, uint8_t modes_mask) {
  if (!staged_core || core_size < 0x250000)
    return -EINVAL;

  /* Mode 1: SPU2 DMA sync & wait timing adjustment (0x002148A0 -> NOP) */
  if (modes_mask & (1 << 0)) {
    write_u32(staged_core, core_size, 0x002148A0, 0x00000000);
  }

  /* Mode 2: Force CD-ROM fast sector cache (0x00207EC0 -> NOP) */
  if (modes_mask & (1 << 1)) {
    write_u32(staged_core, core_size, 0x00207EC0, 0x00000000);
  }

  /* Mode 3: Disable alternate audio channel mixer (0x00210850 -> NOP) */
  if (modes_mask & (1 << 2)) {
    write_u32(staged_core, core_size, 0x00210850, 0x00000000);
  }

  /* Mode 4: Skip GPU FIFO sync locks (0x00205B10 -> NOP) */
  if (modes_mask & (1 << 3)) {
    write_u32(staged_core, core_size, 0x00205B10, 0x00000000);
  }

  /* Mode 5: Force progressive display timing (0x002061A0 -> li $v0, 1) */
  if (modes_mask & (1 << 4)) {
    write_u32(staged_core, core_size, 0x002061A0, 0x24020001);
  }

  /* Mode 6: Alternate LibCrypt subchannel emulation (0x0020C1F0 -> NOP) */
  if (modes_mask & (1 << 5)) {
    write_u32(staged_core, core_size, 0x0020C1F0, 0x00000000);
  }

  /* Mode 7: Throttle R3000A CPU cycle counter (0x002010A0 -> addiu $a0, $zero, 2) */
  if (modes_mask & (1 << 6)) {
    write_u32(staged_core, core_size, 0x002010A0, 0x24040002);
  }

  /* Mode 8: CD-DA streaming buffer adjustments (0x00207EE8 -> NOP) */
  if (modes_mask & (1 << 7)) {
    write_u32(staged_core, core_size, 0x00207EE8, 0x00000000);
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

int pops_apply_cheats(void *ps1_ram_base, const PopsCheatEntry *cheats, uint16_t cheat_count) {
  if (!ps1_ram_base || !cheats || cheat_count == 0)
    return 0;

  for (uint16_t i = 0; i < cheat_count; ++i) {
    uint32_t addr = cheats[i].address & 0x001FFFFF;
    if (cheats[i].type == 0x80) {
      /* 16-bit constant write */
      *(uint16_t *)((uint8_t *)ps1_ram_base + addr) = cheats[i].value;
    } else if (cheats[i].type == 0x30) {
      /* 8-bit constant write */
      *(uint8_t *)((uint8_t *)ps1_ram_base + addr) = (uint8_t)cheats[i].value;
    }
  }
  return 0;
}

int pops_apply_all_config_patches(void *staged_core, size_t core_size, const PopsConfig *cfg) {
  if (!staged_core || !cfg)
    return -EINVAL;

  if (cfg->compat_modes)
    pops_apply_compat_modes(staged_core, core_size, cfg->compat_modes);

  if (cfg->video_mode || cfg->hdtv_fix || cfg->x_offset || cfg->y_offset)
    pops_apply_video_overrides(staged_core, core_size, cfg->video_mode, cfg->hdtv_fix,
                               cfg->x_offset, cfg->y_offset);

  if (cfg->smooth)
    pops_apply_smooth(staged_core, core_size);

  if (cfg->fast_mips || cfg->slow_mips)
    pops_apply_throttling(staged_core, core_size, cfg->fast_mips, cfg->slow_mips);

  if (cfg->no_boot)
    pops_apply_bios_shell(staged_core, core_size);

  return 0;
}
