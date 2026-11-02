#include "pops_modes_patches.h"
#include "pops_builtin_db.h"
#include "pops_resident.h"
#include "pops_external.h"
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

static uint8_t read_u8(const void *base, size_t size, uint32_t addr) {
  if (addr < POPS_CORE_BASE_ADDR)
    return 0;
  uint32_t off = addr - POPS_CORE_BASE_ADDR;
  if (off + 1 > size)
    return 0;
  return ((const uint8_t *)base)[off];
}

static uint16_t read_u16(const void *base, size_t size, uint32_t addr) {
  if (addr < POPS_CORE_BASE_ADDR)
    return 0;
  uint32_t off = addr - POPS_CORE_BASE_ADDR;
  if (off + 2 > size)
    return 0;
  return *(const uint16_t *)((const uint8_t *)base + off);
}

static uint32_t read_u32(const void *base, size_t size, uint32_t addr) {
  if (addr < POPS_CORE_BASE_ADDR)
    return 0;
  uint32_t off = addr - POPS_CORE_BASE_ADDR;
  if (off + 4 > size)
    return 0;
  return *(const uint32_t *)((const uint8_t *)base + off);
}

/* Measured POPSTARTER FUN_008dc2c4: modes 1..7, widths and
 * order retained. Expected bytes are from the supported external POPS ELF.
 * Mode 8 has no branch in this dispatcher. */
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
  {6, 0x002525b0, 0x00001bfc, 0x00000648, 2},
  {7, 0x0021e45c, 0x00000000, 0x00000040, 1},
};

typedef char compat_site_count_must_match[
    sizeof(compat_patches) / sizeof(compat_patches[0]) == POPS_COMPAT_SITE_COUNT ? 1 : -1];

static uint32_t compat_read(const uint8_t *bytes, const CompatPatch *patch) {
  uint32_t value = 0;
  for (unsigned j = 0; j < patch->width; ++j)
    value |= (uint32_t)bytes[patch->address - POPS_CORE_BASE_ADDR + j] << (8 * j);
  return value;
}

/* The PAL helper's four original writes; expected values are from the
 * identified external core. Track them across explicit payload mutations,
 * just like compatibility sites, rather than trusting arbitrary live bytes. */
static const struct {
  uint32_t address, pristine, pal;
  uint8_t width;
} fix_pal_sites[POPS_PATCH_PAL_SITE_COUNT] = {
  {0x21af94, 0x02, 0x03, 1},
  {0x502770, 0x0008a3a2, 0x000a6300, 4},
  {0x23b018, 0x48, 0x6b, 1},
  {0x23b01c, 0x0290, 0x02cb, 2},
};

static uint32_t fix_pal_read(const uint8_t *bytes, unsigned index) {
  uint32_t value = 0;
  for (unsigned j = 0; j < fix_pal_sites[index].width; ++j)
    value |= (uint32_t)bytes[fix_pal_sites[index].address - POPS_CORE_BASE_ADDR + j] << (8 * j);
  return value;
}

static int fix_pal_context_check(const PopsFixContext *context,
                                  const uint8_t *bytes, size_t size) {
  for (unsigned i = 0; i < POPS_PATCH_PAL_SITE_COUNT; ++i) {
    size_t offset = fix_pal_sites[i].address - POPS_CORE_BASE_ADDR;
    if (offset > size || fix_pal_sites[i].width > size - offset)
      return -ERANGE;
    if (fix_pal_read(bytes, i) != context->video_expected[i])
      return -EINVAL;
  }
  return 0;
}

static const uint32_t fix_resident_sites[POPS_PATCH_RESIDENT_SITE_COUNT] = {
  0x21a094, 0x21a098, 0x23acb0, 0x23ad0c
};

static uint32_t fix_resident_read(const uint8_t *bytes, unsigned i) {
  size_t at = fix_resident_sites[i] - POPS_CORE_BASE_ADDR;
  return (uint32_t)bytes[at] | (uint32_t)bytes[at + 1] << 8 |
         (uint32_t)bytes[at + 2] << 16 | (uint32_t)bytes[at + 3] << 24;
}

static int fix_resident_context_check(const PopsFixContext *context,
                                       const uint8_t *bytes, size_t size) {
  if (!context->resident_entry)
    return context->progressive_set ? -EINVAL : 0;
  if ((context->resident_entry & 3) || context->resident_entry < POPS_RESIDENT_BASE ||
      context->resident_entry >= POPS_RESIDENT_LIMIT || context->progressive_set > 1)
    return -EINVAL;
  for (unsigned i = 0; i < POPS_PATCH_RESIDENT_SITE_COUNT; ++i) {
    size_t at = fix_resident_sites[i] - POPS_CORE_BASE_ADDR;
    if (at > size || 4 > size - at)
      return -ERANGE;
    if (fix_resident_read(bytes, i) != context->resident_expected[i])
      return -EINVAL;
  }
  return 0;
}

static int compat_context_check(const PopsFixContext *context,
                                 const uint8_t *bytes, size_t size) {
  for (unsigned i = 0; i < POPS_COMPAT_SITE_COUNT; ++i) {
    const CompatPatch *patch = &compat_patches[i];
    size_t offset = patch->address - POPS_CORE_BASE_ADDR;
    if (offset > size || patch->width > size - offset)
      return -ERANGE;
    if (compat_read(bytes, patch) != context->expected[i])
      return -EINVAL;
  }
  int result = fix_pal_context_check(context, bytes, size);
  return result ? result : fix_resident_context_check(context, bytes, size);
}

static void fix_pal_write(uint8_t *bytes) {
  for (unsigned i = 0; i < POPS_PATCH_PAL_SITE_COUNT; ++i)
    for (unsigned j = 0; j < fix_pal_sites[i].width; ++j)
      bytes[fix_pal_sites[i].address - POPS_CORE_BASE_ADDR + j] =
          (uint8_t)(fix_pal_sites[i].pal >> (8 * j));
}

static int fix_alias(const void *a, size_t asize, const void *b, size_t bsize) {
  uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
  return x <= y ? y - x < asize : x - y < bsize;
}

int pops_fix_context_init(PopsFixContext *context, const void *staged_core,
                           size_t core_size, uint8_t initial_modes) {
  return pops_fix_context_init_video(context, staged_core, core_size,
                                      initial_modes, POPS_VMODE_DEFAULT);
}

int pops_fix_context_init_video(PopsFixContext *context, const void *staged_core,
                                 size_t core_size, uint8_t initial_modes,
                                 uint8_t initial_video_mode) {
  return pops_fix_context_init_builtin(context, staged_core, core_size, 0,
                                       initial_modes, initial_video_mode);
}

/* Replay one built-in entry over the expected compat site values: its
 * compatibility modes (skipping 1/2/3/5 once its gp+0x3458 flag is set, as
 * FUN_008dc2c4 does) and any core write that lands on a site. */
static int builtin_expected(PopsFixContext *candidate, uint16_t id) {
  const PopsBuiltinOp *ops;
  unsigned count, subcd = 0;
  int result = pops_builtin_entry_ops(id, &ops, &count);
  if (result)
    return result;
  for (unsigned n = 0; n < count; ++n) {
    const PopsBuiltinOp *op = &ops[n];
    if (op->kind == POPS_BUILTIN_OP_SUBCD)
      subcd = 1;
    if (op->kind == POPS_BUILTIN_OP_COMPAT) {
      if (subcd && (op->arg == 1 || op->arg == 2 || op->arg == 3 || op->arg == 5))
        continue;
      for (unsigned i = 0; i < POPS_COMPAT_SITE_COUNT; ++i)
        if (compat_patches[i].mode == op->arg)
          for (unsigned j = 0; j < POPS_COMPAT_SITE_COUNT; ++j)
            if (compat_patches[j].address == compat_patches[i].address)
              candidate->expected[j] = compat_patches[i].replacement;
    }
    if (op->kind == POPS_BUILTIN_OP_CORE) {
      for (unsigned j = 0; j < POPS_COMPAT_SITE_COUNT; ++j) {
        const CompatPatch *p = &compat_patches[j];
        if (p->address < op->addr || p->address + p->width > op->addr + op->len)
          continue;
        uint32_t value = 0;
        for (unsigned k = 0; k < p->width; ++k)
          value |= (uint32_t)pops_builtin_data[op->data + (p->address - op->addr) + k] << (8 * k);
        candidate->expected[j] = value;
      }
    }
  }
  return 0;
}

int pops_fix_context_init_builtin(PopsFixContext *context, const void *staged_core,
                                  size_t core_size, uint16_t builtin_id,
                                  uint8_t initial_modes, uint8_t initial_video_mode) {
  PopsFixContext candidate;
  if (!context || !staged_core ||
      fix_alias(context, sizeof(*context), staged_core, core_size))
    return -EINVAL;
  if (initial_modes & 0x80)
    return -ENOTSUP;
  if (initial_video_mode > POPS_VMODE_240P)
    return -ENOTSUP;
  memset(&candidate, 0, sizeof(candidate));
  for (unsigned i = 0; i < POPS_COMPAT_SITE_COUNT; ++i)
    candidate.expected[i] = compat_patches[i].expected;
  if (builtin_id) {
    int replayed = builtin_expected(&candidate, builtin_id);
    if (replayed)
      return replayed;
  }
  for (unsigned i = 0; i < POPS_PATCH_PAL_SITE_COUNT; ++i)
    candidate.video_expected[i] = fix_pal_sites[i].pristine;
  candidate.video_auto_disabled = initial_video_mode == POPS_VMODE_480P;
  candidate.video_custom_set = initial_video_mode == POPS_VMODE_NTSC2PAL ||
                               initial_video_mode == POPS_VMODE_480P;
  /* The initial text/database mask uses the existing ascending dispatcher.
   * Calculate its result independently; do not bless arbitrary current bytes. */
  for (unsigned i = 0; i < POPS_COMPAT_SITE_COUNT; ++i) {
    const CompatPatch *patch = &compat_patches[i];
    if (initial_modes & (1 << (patch->mode - 1))) {
      for (unsigned j = 0; j < POPS_COMPAT_SITE_COUNT; ++j)
        if (compat_patches[j].address == patch->address)
          candidate.expected[j] = patch->replacement;
    }
  }
  /* $UNDO_COMPATIBILITY_CODES writes 0x20083c/0x20085c with the values
   * modes 2 and 5 use, whatever the mask. Accept exactly those values. */
  for (unsigned i = 0; i < POPS_COMPAT_SITE_COUNT; ++i) {
    const CompatPatch *patch = &compat_patches[i];
    if ((patch->address == 0x0020083c || patch->address == 0x0020085c) &&
        patch->address - POPS_CORE_BASE_ADDR + patch->width <= core_size &&
        compat_read(staged_core, patch) == patch->replacement)
      candidate.expected[i] = patch->replacement;
  }
  int result = compat_context_check(&candidate, staged_core, core_size);
  if (result)
    return result;
  *context = candidate;
  return 0;
}

int pops_fix_finalize_video(PopsFixContext *context, void *staged_core,
                             size_t core_size, int region, uint8_t video_mode) {
  if (!context || !staged_core || region < POPS_REGION_UNKNOWN ||
      region > POPS_REGION_JAPAN ||
      fix_alias(context, sizeof(*context), staged_core, core_size))
    return -EINVAL;
  if (video_mode > POPS_VMODE_240P)
    return -ENOTSUP;
  int result = compat_context_check(context, staged_core, core_size);
  if (result)
    return result;
  if (!context->video_auto_disabled &&
      (video_mode == POPS_VMODE_NTSC2PAL ||
       (region == POPS_REGION_EUROPE && video_mode != POPS_VMODE_NOPAL &&
        video_mode != POPS_VMODE_480P))) {
    fix_pal_write(staged_core);
    for (unsigned i = 0; i < POPS_PATCH_PAL_SITE_COUNT; ++i)
      context->video_expected[i] = fix_pal_sites[i].pal;
  }
  return 0;
}

int pops_fix_bind_progressive(PopsFixContext *context, const void *staged_core,
                              size_t core_size, uint32_t entry, uint32_t initial_interlace) {
  if (!context || !staged_core || context->resident_entry || (entry & 3) ||
      entry < POPS_RESIDENT_BASE || entry >= POPS_RESIDENT_LIMIT ||
      (initial_interlace != 0x32240001 && initial_interlace != 0x24040001) ||
      fix_alias(context, sizeof(*context), staged_core, core_size))
    return -EINVAL;
  int result = compat_context_check(context, staged_core, core_size);
  if (result)
    return result;
  PopsFixContext candidate = *context;
  candidate.resident_entry = entry;
  candidate.resident_expected[0] = 0xde050010;
  candidate.resident_expected[1] = 0x3c031200;
  candidate.resident_expected[2] = candidate.resident_expected[3] = initial_interlace;
  result = fix_resident_context_check(&candidate, staged_core, core_size);
  if (!result)
    *context = candidate;
  return result;
}

int pops_fix_require_progressive(const PopsFixContext *context, const void *staged_core,
                                 size_t core_size) {
  if (!context || !staged_core || fix_alias(context, sizeof(*context), staged_core, core_size))
    return -EINVAL;
  int result = compat_context_check(context, staged_core, core_size);
  if (result || !context->progressive_set)
    return result;
  uint32_t want[] = {0x08000000u | (context->resident_entry >> 2), 0x3c031200,
                      0x24040000, 0x24040000};
  if (context->video_expected[0] != 0x50)
    return -EINVAL;
  for (unsigned i = 0; i < POPS_PATCH_RESIDENT_SITE_COUNT; ++i)
    if (context->resident_expected[i] != want[i])
      return -EINVAL;
  return 0;
}

int pops_fix_stage(PopsFixContext *context, void *staged_core, size_t core_size,
                    const void *file, size_t file_size, unsigned slot,
                    int expected_trojan) {
  PopsContainerPlan plan;
  PopsPatchOptions options = {{0}, POPS_PATCH_VIDEO_NONE};
  uint8_t *bytes = staged_core;
  uint32_t hook[3];
  if (!context || !bytes || !file || slot > 9 ||
      fix_alias(context, sizeof(*context), bytes, core_size) ||
      fix_alias(context, sizeof(*context), file, file_size) ||
      fix_alias(file, file_size, bytes, core_size))
    return -EINVAL;
  int result = pops_container_plan(file, file_size, POPS_CORE_BASE_ADDR,
                                    core_size, &plan);
  if (result)
    return result;
  if (plan.container.slot != slot ||
      (plan.container.kind == POPS_CONTAINER_TROJAN) != !!expected_trojan)
    return -EINVAL;
  if (!expected_trojan) {
    /* Only the original PATCH format-1 record is grounded by this loader. */
    if (plan.container.flags != 0x00010001)
      return -ENOTSUP;
    result = pops_patch_options(&plan.container, &options);
    if (result)
      return result;
    /* Actions 6/7 require an explicitly bound owned image entry. */
    if (options.video == POPS_PATCH_VIDEO_CONTROL6 && !context->resident_entry)
      return -ENOTSUP;
    if (options.video == POPS_PATCH_VIDEO_PAL &&
        core_size < (size_t)(0x00502770 - POPS_CORE_BASE_ADDR + 4))
      return -ERANGE;
    for (unsigned i = 0; i < 4; ++i)
      if (options.modes[i] > 7)
        return -ENOTSUP;
  }
  result = compat_context_check(context, bytes, core_size);
  if (result)
    return result;
  if (options.video == POPS_PATCH_VIDEO_CONTROL6 && !context->video_custom_set) {
    /* A payload may replace the original delay slot. Predict this field
     * before the first write; the owned bridge requires its known LUI. */
    uint32_t delay = 0;
    for (unsigned j = 0; j < 4; ++j) {
      uint32_t address = 0x21a098 + j;
      uint8_t byte = bytes[address - POPS_CORE_BASE_ADDR];
      if (address >= plan.container.load &&
          address - plan.container.load < plan.container.payload_size)
        byte = ((const uint8_t *)file)[plan.payload_offset + address - plan.container.load];
      delay |= (uint32_t)byte << (8 * j);
    }
    if (delay != 0x3c031200)
      return -EILSEQ;
  }
  /* All bounds/options/guards precede the first payload write. Trojan hooks
   * retain the existing snapshot guards; they are not independent pristine
   * profiles. Explicit payload changes become the next session's expectation. */
  if (plan.container.kind != POPS_CONTAINER_CONFIG) {
    size_t count = plan.hook_size > 8 ? 3 : 2;
    if (expected_trojan)
      memcpy(hook, bytes + plan.hook_offset, count * sizeof(hook[0]));
    result = pops_container_stage(file, file_size, POPS_CORE_BASE_ADDR, bytes,
                                    core_size, expected_trojan ? hook : NULL,
                                    expected_trojan ? count : 0);
    if (result)
      return result;
  }
  for (unsigned mode = 0; mode < 4; ++mode) {
    if (!options.modes[mode])
      continue;
    for (unsigned i = 0; i < POPS_COMPAT_SITE_COUNT; ++i) {
      const CompatPatch *patch = &compat_patches[i];
      if (patch->mode == options.modes[mode])
        for (unsigned j = 0; j < patch->width; ++j)
          bytes[patch->address - POPS_CORE_BASE_ADDR + j] =
              (uint8_t)(patch->replacement >> (8 * j));
    }
  }
  switch (options.video) {
  case POPS_PATCH_VIDEO_NONE:
    break;
  case POPS_PATCH_VIDEO_DISABLE_AUTO:
    context->video_auto_disabled = 1;
    break;
  case POPS_PATCH_VIDEO_PAL:
    if (!context->video_auto_disabled) {
      fix_pal_write(bytes);
      context->video_auto_disabled = 1;
      context->video_custom_set = 1;
    }
    break;
  case POPS_PATCH_VIDEO_CONTROL6:
    if (!context->video_custom_set) {
      write_u8(bytes, core_size, 0x21af94, 0x50);
      write_u32(bytes, core_size, 0x21a094, 0x08000000u | (context->resident_entry >> 2));
      write_u32(bytes, core_size, 0x23acb0, 0x24040000);
      write_u32(bytes, core_size, 0x23ad0c, 0x24040000);
      context->progressive_set = 1;
      context->video_auto_disabled = 1;
      context->video_custom_set = 1;
    }
    break;
  }
  for (unsigned i = 0; i < POPS_COMPAT_SITE_COUNT; ++i)
    context->expected[i] = compat_read(bytes, &compat_patches[i]);
  for (unsigned i = 0; i < POPS_PATCH_PAL_SITE_COUNT; ++i)
    context->video_expected[i] = fix_pal_read(bytes, i);
  if (context->resident_entry)
    for (unsigned i = 0; i < POPS_PATCH_RESIDENT_SITE_COUNT; ++i)
      context->resident_expected[i] = fix_resident_read(bytes, i);
  return 0;
}

static int compat_site_value_known(uint32_t address, uint32_t value) {
  for (size_t i = 0; i < sizeof(compat_patches) / sizeof(compat_patches[0]); ++i)
    if (compat_patches[i].address == address &&
        (compat_patches[i].replacement == value || compat_patches[i].expected == value))
      return 1;
  return address == 0x0021af70 && value == 0x32;
}

int pops_compat_mode_write(void *staged_core, size_t core_size, uint8_t mode) {
  uint8_t *bytes = staged_core;
  if (!bytes || mode < 1 || mode > 7)
    return -EINVAL;
  for (size_t i = 0; i < sizeof(compat_patches) / sizeof(compat_patches[0]); ++i) {
    const CompatPatch *p = &compat_patches[i];
    if (p->mode != mode)
      continue;
    if (p->address - POPS_CORE_BASE_ADDR + p->width > core_size)
      return -ERANGE;
  }
  for (size_t i = 0; i < sizeof(compat_patches) / sizeof(compat_patches[0]); ++i) {
    const CompatPatch *p = &compat_patches[i];
    if (p->mode == mode)
      for (unsigned j = 0; j < p->width; ++j)
        bytes[p->address - POPS_CORE_BASE_ADDR + j] = (uint8_t)(p->replacement >> (8 * j));
  }
  return 0;
}

/* $RESET_WARMBOOT: see pops_modes_patches.h. The scan and its pokes follow
 * the original's loop (0x87960c..0x879cf4) step for step: p walks down by 4,
 * a stub is `addiu $t2,$zero,table ; jr $t2 ; addiu $t1,$zero,func`, and
 * each case pokes single bytes (0x87c298), so a poke can change what a
 * lower p later reads, as there. */
static const uint8_t warmboot_a0_funcs[] = {0x3a, 0x40, 0x4f, 0x50, 0x53, 0x9a, 0x9b, 0xa1};
static const uint8_t warmboot_b0_funcs[] = {0x52, 0x5a, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f,
                                            0x21, 0x22, 0x23, 0x2a, 0x2b, 0x38};
static const uint8_t warmboot_c0_funcs[] = {0x0b, 0x14};

static int warmboot_listed(const uint8_t *list, size_t n, uint32_t func_word) {
  for (size_t i = 0; i < n; ++i)
    if (func_word == (0x24090000u | list[i]))
      return 1;
  return 0;
}

static uint32_t warmboot_word(const uint8_t *at) {
  return (uint32_t)at[0] | ((uint32_t)at[1] << 8) | ((uint32_t)at[2] << 16) | ((uint32_t)at[3] << 24);
}

int pops_apply_padman(void *staged_core, size_t core_size) {
  uint8_t *at;
  if (!staged_core)
    return -EINVAL;
  if (core_size < (size_t)(POPS_PADMAN_CALL_SITE + 12 - POPS_CORE_BASE_ADDR))
    return -ERANGE;
  at = (uint8_t *)staged_core + (POPS_PADMAN_CALL_SITE - POPS_CORE_BASE_ADDR);
  at[0] = at[1] = at[2] = at[3] = 0;   /* sw 0 at 0x200358 */
  at[10] = 0x00;                        /* sh 0x1000 at 0x200362 */
  at[11] = 0x10;
  return 0;
}

/* FUN_008d7024's chain, in the original's order. site 0: flag only. */
static const struct {
  const char *name;
  uint32_t site;
  unsigned flag;
} module_irx_names[] = {
  {"sio2man", 0x00200324, POPS_MODULE_IRX_SIO2MAN},
  {"padman", 0x00200358, POPS_MODULE_IRX_PADMAN},
  {"Sound_Device_Library", 0x00200388, 0},
  {"sdr_driver", 0x002003b8, 0},
  {"dev9", 0x002003f0, 0},
  {"atad", 0x00200420, 0},
  {"hdd", 0x00200450, 0},
  {"pfs", 0x00200480, 0},
  {"IOX/File_Manager", 0, 0},
  {"IOX/File_Manager_Rpc", 0, 0},
  {"Poweroff_Handler", 0, 0},
};

static uint8_t module_irx_byte(const void *irx, size_t irx_size, size_t at) {
  return at < irx_size ? ((const uint8_t *)irx)[at] : 0;
}

static int module_irx_prefix(const void *irx, size_t irx_size, const char *name) {
  size_t i;
  for (i = 0; name[i]; ++i)
    if (module_irx_byte(irx, irx_size, POPS_MODULE_IRX_NAME_AT + i) != (uint8_t)name[i])
      return 0;
  return 1;
}

int pops_module_irx_name_apply(void *staged_core, size_t core_size,
                               const void *irx, size_t irx_size, unsigned *flags) {
  size_t i;
  if (!staged_core || !irx || !flags)
    return -EINVAL;
  for (i = 0; i < sizeof(module_irx_names) / sizeof(module_irx_names[0]); ++i) {
    uint8_t *at;
    if (!module_irx_prefix(irx, irx_size, module_irx_names[i].name))
      continue;
    if (module_irx_names[i].site) {
      if (core_size < (size_t)(module_irx_names[i].site + 12 - POPS_CORE_BASE_ADDR))
        return -ERANGE;
      at = (uint8_t *)staged_core + (module_irx_names[i].site - POPS_CORE_BASE_ADDR);
      at[0] = at[1] = at[2] = at[3] = 0;
      at[10] = 0x00;
      at[11] = 0x10;
    }
    *flags |= module_irx_names[i].flag;
    return 0;
  }
  return 0;
}

int pops_module_irx_args(const void *irx, size_t irx_size, const char **args) {
  static const char hdd_args[12] = "-o\0" "8\0" "-n\0" "128";
  static const char pfs_args[17] = "-m\0" "8\0" "-o\0" "8\0" "-n\0" "127";
  if (!args)
    return -EINVAL;
  *args = NULL;
  if (!irx)
    return -EINVAL;
  if (module_irx_prefix(irx, irx_size, "hdd")) {
    *args = hdd_args;
    return (int)sizeof(hdd_args);
  }
  if (module_irx_prefix(irx, irx_size, "pfs")) {
    *args = pfs_args;
    return (int)sizeof(pfs_args);
  }
  return 0;
}

int pops_apply_reset_warmboot(void *staged_core, size_t core_size, uint32_t *exit_vector) {
  uint8_t *bytes = staged_core;
  uint32_t p;
  if (!bytes || !exit_vector)
    return -EINVAL;
  *exit_vector = 0;
  if (core_size < (size_t)(POPS_WARMBOOT_SCAN_TOP + 12 - POPS_CORE_BASE_ADDR))
    return -ERANGE;
  for (p = POPS_WARMBOOT_SCAN_TOP; p != POPS_WARMBOOT_ROM_BASE; p -= 4) {
    uint8_t *at = bytes + (p - POPS_CORE_BASE_ADDR);
    uint32_t w0 = warmboot_word(at), w1 = warmboot_word(at + 4), w2 = warmboot_word(at + 8);
    if ((w0 >> 16) != 0x240a || w1 != 0x01400008)
      continue;
    switch (w0 & 0xffff) {
    case 0xa0:
      if (warmboot_listed(warmboot_a0_funcs, sizeof(warmboot_a0_funcs), w2)) {
        at[8] = 0xa0;
        /* The original computes the stub's PS1 ROM address here
         * (p - 0x24bc20 + 0xbfc00000) and then stores p itself, the EE
         * address inside POPS's ROM copy, into its resident block. Copied
         * as is (quirk 26). */
        if (w2 == 0x2409003a)
          *exit_vector = p;
      }
      break;
    case 0xb0:
      if (warmboot_listed(warmboot_b0_funcs, sizeof(warmboot_b0_funcs), w2)) {
        at[0] = 0xa0;
        at[8] = 0xa0;
      }
      break;
    case 0xc0:
      if (warmboot_listed(warmboot_c0_funcs, sizeof(warmboot_c0_funcs), w2)) {
        at[0] = 0xa0;
        at[8] = 0xa0;
      }
      break;
    default:
      break;
    }
  }
  return *exit_vector ? 1 : 0;
}

int pops_apply_compat_modes(void *staged_core, size_t core_size, uint8_t modes_mask) {
  uint8_t *bytes = staged_core;
  size_t i;
  unsigned j;
  if (!bytes)
    return -EINVAL;
  if (modes_mask & (1 << 7))
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
    /* $UNDO_COMPATIBILITY_CODES (applied first, as in the original) leaves
     * 0x20083c/0x20085c at the very values modes 2 and 5 write, and the
     * built-in per-game list (also first) may have left any mode's value,
     * or its own 0x32 at 0x21af70. */
    if (actual != p->expected && !compat_site_value_known(p->address, actual))
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

/* POPStarter MAIN: SMOOTH at 0x886664, LEFTADJ at 0x8909c8,
 * X/Y at 0x89a1a8, DWSTRETCH at 0x89a2e4, DWCROP at 0x89b618.
 * The original's decimal calculations feed these immediate fields directly.
 * Unlike $DX/$DY/$MAG*, these commands do not call resident code. */
static int display_config(void *core, size_t size, const PopsConfig *cfg, int apply) {
  if (!core || !cfg)
    return -EINVAL;
  if ((cfg->display_mask & ~POPS_DISPLAY_ALL) ||
      ((cfg->display_mask & POPS_DISPLAY_STRETCH) && cfg->display_stretch > 9999) ||
      ((cfg->display_mask & POPS_DISPLAY_CROP) && cfg->display_crop > 9999))
    return -EINVAL;
  const struct {
    uint32_t address, pristine, value;
    uint8_t width, selected;
  } sites[] = {
    {0x21af88, 0x0c0903d8, 0x341a0001, 4, cfg->smooth},
    {0x21af8c, 0x2484f1d8, 0xa21a22a0, 4, cfg->smooth},
    {0x21a0a4, 0xfc450000, 0x64a50f00 | ((0x1000u - cfg->left_adjust) & 0xff), 4, cfg->left_adjust},
    {0x21a0a8, 0x0220202d, 0xfc450000, 4, cfg->left_adjust},
    {0x21b128, 0x0200, cfg->display_x, 2, cfg->display_mask & POPS_DISPLAY_X},
    {0x21c114, 0x0200, cfg->display_x, 2, cfg->display_mask & POPS_DISPLAY_X},
    {0x221958, 0xae2421b4, 0, 4, cfg->display_mask & POPS_DISPLAY_X},
    {0x21c18c, 0x0010, cfg->display_y, 2, cfg->display_mask & POPS_DISPLAY_Y},
    {0x2219d0, 0xae2421b8, 0, 4, cfg->display_mask & POPS_DISPLAY_Y},
    {0x21b130, 0xae2821b8, 0, 4, cfg->display_mask & POPS_DISPLAY_Y},
    {0x23af40, 0x09ff, cfg->display_stretch, 2, cfg->display_mask & POPS_DISPLAY_STRETCH},
    {0x23aff4, 0x09ff, cfg->display_stretch, 2, cfg->display_mask & POPS_DISPLAY_STRETCH},
    {0x221960, 0xae2321bc, 0, 4, cfg->display_mask & POPS_DISPLAY_CROP},
    {0x21b12c, 0x0a00, cfg->display_crop, 2, cfg->display_mask & POPS_DISPLAY_CROP},
    {0x21c184, 0x0a00, cfg->display_crop, 2, cfg->display_mask & POPS_DISPLAY_CROP},
  };
  uint8_t *bytes = core;
  for (unsigned i = 0; i < sizeof(sites) / sizeof(sites[0]); ++i) {
    if (!sites[i].selected)
      continue;
    size_t offset = sites[i].address - POPS_CORE_BASE_ADDR;
    if (offset > size || sites[i].width > size - offset)
      return -ERANGE;
    uint32_t current = 0;
    for (unsigned j = 0; j < sites[i].width; ++j)
      current |= (uint32_t)bytes[offset + j] << (8 * j);
    if (current != sites[i].pristine && current != sites[i].value)
      return -EILSEQ;
  }
  if (apply)
    for (unsigned i = 0; i < sizeof(sites) / sizeof(sites[0]); ++i)
      if (sites[i].selected)
        for (unsigned j = 0; j < sites[i].width; ++j)
          bytes[sites[i].address - POPS_CORE_BASE_ADDR + j] =
              (uint8_t)(sites[i].value >> (8 * j));
  return 0;
}

int pops_apply_display_config(void *core, size_t size, const PopsConfig *cfg) {
  return display_config(core, size, cfg, 1);
}

/* POPStarter r13 FUN_008dc218, the "to PAL" patch. The original applies it
 * to European discs (unless $NOPAL) and for $FORCEPAL; POPS is NTSC
 * otherwise. Accepted current bytes were measured on the reference core. */
static int apply_pal_patch(void *staged_core, size_t core_size) {
  uint8_t m = read_u8(staged_core, core_size, 0x0021af94);
  uint32_t vs = read_u32(staged_core, core_size, 0x00502770);
  uint8_t x = read_u8(staged_core, core_size, 0x0023b018);
  uint16_t y = read_u16(staged_core, core_size, 0x0023b01c);
  if (core_size < (size_t)(0x00502770 - POPS_CORE_BASE_ADDR + 4))
    return -ERANGE;
  if ((m != 0x02 && m != 0x64 && m != 0x03) ||
      (vs != 0x0008a3a2 && vs != 0x000c7200 && vs != 0x000a6300) ||
      (x != 0x48 && x != 0x7f && x != 0x6b) ||
      (y != 0x0290 && y != 0x0357 && y != 0x02cb))
    return -EILSEQ;
  write_u8(staged_core, core_size, 0x0021af94, 3);
  write_u32(staged_core, core_size, 0x00502770, 0x000a6300);
  write_u8(staged_core, core_size, 0x0023b018, 0x6b);
  write_u16(staged_core, core_size, 0x0023b01c, 0x02cb);
  return 0;
}

int pops_apply_video_overrides(void *staged_core, size_t core_size,
                               uint8_t video_mode, uint8_t hdtv_fix,
                               int16_t x_offset, int16_t y_offset) {
  int result;
  if (!staged_core)
    return -EINVAL;
  if (video_mode > POPS_VMODE_240P)
    return -ENOTSUP;
  /* $480p is installed later through the validated resident image/header.
   * This helper cannot install that dependency. Other modes and offsets
   * still have no grounded writes. */
  if (video_mode >= POPS_VMODE_480P || x_offset || y_offset)
    return -ENOTSUP;
  if (hdtv_fix && core_size < (size_t)(0x0023ad0c - POPS_CORE_BASE_ADDR + 4))
    return -ERANGE;
  if (video_mode == POPS_VMODE_NTSC2PAL) {
    result = apply_pal_patch(staged_core, core_size);
    if (result)
      return result;
  }
  if (hdtv_fix) {
    /* $HDTVFIX: li a0,1 over the original andi a0,s1,1 (see $NOHDTVFIX) */
    static const uint32_t sites[] = {0x0023acb0, 0x0023ad0c};
    for (unsigned i = 0; i < 2; ++i) {
      uint32_t cur = read_u32(staged_core, core_size, sites[i]);
      if (cur != 0x32240001 && cur != 0x24040001)
        return -EILSEQ;
    }
    for (unsigned i = 0; i < 2; ++i)
      write_u32(staged_core, core_size, sites[i], 0x24040001);
  }
  return 0;
}

int pops_region_from_licence(const char tag[4]) {
  if (!tag)
    return POPS_REGION_UNKNOWN;
  if (!memcmp(tag, "Euro", 4))
    return POPS_REGION_EUROPE;
  if (!memcmp(tag, "Amer", 4) || !memcmp(tag, "of A", 4))
    return POPS_REGION_AMERICA;
  if (!memcmp(tag, "Inc.", 4))
    return POPS_REGION_JAPAN;
  return POPS_REGION_UNKNOWN;
}

/* POPStarter r13 region pass (0x879034..0x8795f0). 0x2649a0 is the region
 * check of the PS1 BIOS inside POPS; the original skips those writes only
 * when a user BIOS/OSD replacement was loaded, which launcHER never does. */
int pops_apply_region(void *staged_core, size_t core_size, int region,
                      uint8_t video_mode, int auto_video_disabled) {
  static const uint8_t pops_letter[] = {'T', 'E', 'A', 'J'};
  static const uint8_t cd_letter[] = {0, 'E', 'A', 'I'};
  static const uint32_t bios_li[] = {0, 0x34040045, 0x34040041, 0x34040049};
  int force_pal = video_mode == POPS_VMODE_NTSC2PAL && !auto_video_disabled;
  int result;
  if (!staged_core)
    return -EINVAL;
  if (region < POPS_REGION_UNKNOWN || region > POPS_REGION_JAPAN)
    return -EINVAL;
  if (core_size < (size_t)(0x002cbb72 - POPS_CORE_BASE_ADDR + 1))
    return -ERANGE;
  if (force_pal || (region == POPS_REGION_EUROPE && !auto_video_disabled &&
                   video_mode != POPS_VMODE_NOPAL && video_mode != POPS_VMODE_480P)) {
    result = apply_pal_patch(staged_core, core_size);
    if (result)
      return result;
  }
  /* $FORCEPAL reports Europe to POPS whatever the disc says. */
  write_u8(staged_core, core_size, 0x002cbb72,
           force_pal ? 'E' : pops_letter[region]);
  if (!force_pal)
    write_u8(staged_core, core_size, 0x0020f6cc, cd_letter[region]);
  if (region != POPS_REGION_UNKNOWN) {
    write_u32(staged_core, core_size, 0x002649a0, bios_li[region]);
  } else {
    write_u32(staged_core, core_size, 0x00264994, 0x34050000);
    write_u32(staged_core, core_size, 0x00264998, 0x34020000);
    write_u32(staged_core, core_size, 0x0026499c, 0x34030000);
    write_u32(staged_core, core_size, 0x002649a0, 0x34040000);
    if (!force_pal) {
      write_u8(staged_core, core_size, 0x0020f6d8, 0);
      write_u8(staged_core, core_size, 0x0020f6dc, 0);
      write_u8(staged_core, core_size, 0x0020f6e0, 0);
    }
  }
  return 0;
}

/* Fixed-value POPStarter r13 commands. Values are the original handlers'
 * writes; where the original restores a site ($UNDO_MUTE_CDDA, $NOHDTVFIX,
 * $ROLLBACK) that value is the pristine POPS byte. The core is SHA-256
 * pinned before any of these run. */
typedef struct {
  uint32_t flag;
  uint32_t address;
  uint32_t value;
  uint8_t width;
} TokenWrite;
static const TokenWrite token_writes[] = {
  {POPS_TOK_SCANLINES, 0x0021e454, 0x22b50006, 4},
  {POPS_TOK_SUBCDSTATUS, 0x0020e850, 0x06, 1},
  {POPS_TOK_SUBCDSTATUS, 0x0020e86c, 0x24030020, 4},
  {POPS_TOK_SUBCDSTATUS, 0x0020e87c, 0x00431022, 4},
  {POPS_TOK_MUTE_CDDA, 0x0020f0b6, 0x00, 1},
  {POPS_TOK_MUTE_CDDA, 0x0020ebf2, 0x00, 1},
  {POPS_TOK_MUTE_CDDA, 0x0020f0e0, 0x00000000, 4},
  {POPS_TOK_UNDO_MUTE_CDDA, 0x0020f0b6, 0x02, 1},
  {POPS_TOK_UNDO_MUTE_CDDA, 0x0020ebf2, 0x03, 1},
  {POPS_TOK_UNDO_MUTE_CDDA, 0x0020f0e0, 0xae000014, 4},
  {POPS_TOK_MUTE_VAB, 0x00210e7c, 0x00, 1},
  {POPS_TOK_MUTE_VAB, 0x00210ed6, 0x00, 1},
  {POPS_TOK_MUTE_VAB, 0x002120ca, 0xa0, 1},
  {POPS_TOK_MUTE_VAB, 0x00213abc, 0x00, 1},
  {POPS_TOK_MUTE_VAB, 0x002110b6, 0x1000, 2},
  {POPS_TOK_MUTE_ALL, 0x00213ff4, 0x00000000, 4},
  {POPS_TOK_CODECACHE_ADDON0, 0x00202734, 0x10000004, 4},
  {POPS_TOK_CODECACHE_ADDON1, 0x00202734, 0x00000000, 4},
  {POPS_TOK_CODECACHE_ADDON2, 0x00202734, 0x14600004, 4},
  {POPS_TOK_ROLLBACK, 0x0020b908, 0x0d, 1},
  {POPS_TOK_ROLLBACK, 0x00207e34, 0x0000000d, 4},
  {POPS_TOK_ROLLBACK, 0x00207e74, 0x0000000d, 4},
  {POPS_TOK_ROLLBACK, 0x00207eb8, 0x0000000d, 4},
  {POPS_TOK_ROLLBACK, 0x00207ebc, 0x1000009c, 4},
  {POPS_TOK_ROLLBACK, 0x00207f54, 0x0000000d, 4},
  {POPS_TOK_ROLLBACK, 0x00207f58, 0x10000075, 4},
  {POPS_TOK_ROLLBACK, 0x00207e9c, 0x0a, 1},
  {POPS_TOK_ROLLBACK, 0x00208a84, 0x01cd, 2},
  {POPS_TOK_ROLLBACK, 0x00204790, 0x000d, 2},
  {POPS_TOK_CACHE1, 0x0020fff4, 0x01, 1},
  {POPS_TOK_CACHE1, 0x00210120, 0x01, 1},
  {POPS_TOK_CACHE1, 0x002101ac, 0x0c20, 2},
  {POPS_TOK_NOHDTVFIX, 0x0023acb0, 0x32240001, 4},
  {POPS_TOK_NOHDTVFIX, 0x0023ad0c, 0x32240001, 4},
};

static void write_width(void *core, size_t size, uint32_t address,
                        uint32_t value, uint8_t width) {
  if (width == 1)
    write_u8(core, size, address, (uint8_t)value);
  else if (width == 2)
    write_u16(core, size, address, (uint16_t)value);
  else
    write_u32(core, size, address, value);
}

int pops_apply_original_tokens(void *staged_core, size_t core_size, uint32_t tokens) {
  if (!staged_core)
    return -EINVAL;
  if (tokens >> POPS_TOK_COUNT)
    return -ENOTSUP;
  for (size_t i = 0; i < sizeof(token_writes) / sizeof(token_writes[0]); ++i)
    if ((tokens & token_writes[i].flag) &&
        token_writes[i].address + token_writes[i].width >
            POPS_CORE_BASE_ADDR + core_size)
      return -ERANGE;
  /* $UNDO_COMPATIBILITY_CODES runs after $SUBCDSTATUS in the original and
   * puts all of its sites back, so $SUBCDSTATUS has no effect with it. */
  if (tokens & POPS_TOK_UNDO_COMPAT)
    tokens &= ~POPS_TOK_SUBCDSTATUS;
  /* Table order is the original command order, so later commands win. */
  for (size_t i = 0; i < sizeof(token_writes) / sizeof(token_writes[0]); ++i)
    if (tokens & token_writes[i].flag)
      write_width(staged_core, core_size, token_writes[i].address,
                  token_writes[i].value, token_writes[i].width);
  return 0;
}

/* The original's $UNDO_* handler writes, in handler order. Every value but
 * 0x20083c/0x20085c (the same values compat modes 2 and 5 write) equals
 * the shipped POPS word: they undo what the original's built-in per-game
 * table applied before the commands ran. All three re-enable the BIOS OSD
 * (0x2525b0 = 0x1bfc). Left out, because they land inside POPStarter's own
 * resident blob rather than POPS code: $UNDO_GAME_FIXES 0x2397d8 =
 * 0x10000001 and $UNDO_LIBCRYPT_FIX 0x239780 = 0x10000014, 0x239784 = 0. */
static const TokenWrite undo_writes[] = {
  {POPS_TOK_UNDO_COMPAT, 0x002525b0, 0x1bfc, 2},
  {POPS_TOK_UNDO_COMPAT, 0x0020083c, 0x1000000a, 4},
  {POPS_TOK_UNDO_COMPAT, 0x00200844, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x00200848, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x00200850, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x00200854, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x00200858, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x0020085c, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x00200860, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x0020bcac, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x0020de9c, 0x0c0836ee, 4},
  {POPS_TOK_UNDO_COMPAT, 0x00210314, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x00210318, 0x8f828228, 4},
  {POPS_TOK_UNDO_COMPAT, 0x0021031c, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x00210320, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x00210324, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x00210328, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x0021032c, 0x1443fffa, 4},
  {POPS_TOK_UNDO_COMPAT, 0x0021af70, 0x64, 1},
  {POPS_TOK_UNDO_COMPAT, 0x0021e45c, 0x00, 1},
  {POPS_TOK_UNDO_COMPAT, 0x0020e850, 0x07, 1},
  {POPS_TOK_UNDO_COMPAT, 0x0020e86c, 0x00000000, 4},
  {POPS_TOK_UNDO_COMPAT, 0x0020e87c, 0x34420020, 4},
  {POPS_TOK_UNDO_GAME_FIXES, 0x002525b0, 0x1bfc, 2},
  {POPS_TOK_UNDO_LIBCRYPT, 0x002525b0, 0x1bfc, 2},
  {POPS_TOK_UNDO_LIBCRYPT, 0x00210cf8, 0x2442ffff, 4},
  {POPS_TOK_UNDO_LIBCRYPT, 0x00210cfc, 0x7c640000, 4},
  {POPS_TOK_UNDO_LIBCRYPT, 0x00210d00, 0x00000000, 4},
  {POPS_TOK_UNDO_LIBCRYPT, 0x00210d04, 0x00000000, 4},
  {POPS_TOK_UNDO_LIBCRYPT, 0x00210d08, 0x00000000, 4},
  {POPS_TOK_UNDO_LIBCRYPT, 0x00210d0c, 0xfa, 1},
};

int pops_apply_undo_tokens(void *staged_core, size_t core_size, uint32_t tokens) {
  if (!staged_core)
    return -EINVAL;
  if (tokens >> POPS_TOK_COUNT)
    return -ENOTSUP;
  for (size_t i = 0; i < sizeof(undo_writes) / sizeof(undo_writes[0]); ++i)
    if ((tokens & undo_writes[i].flag) &&
        undo_writes[i].address + undo_writes[i].width >
            POPS_CORE_BASE_ADDR + core_size)
      return -ERANGE;
  for (size_t i = 0; i < sizeof(undo_writes) / sizeof(undo_writes[0]); ++i)
    if (tokens & undo_writes[i].flag)
      write_width(staged_core, core_size, undo_writes[i].address,
                  undo_writes[i].value, undo_writes[i].width);
  return 0;
}

/* POPStarter r13 $IGR0..$IGR5 (igr_type 1..6) and $NOIGR. Masks select the
 * pad combination; $IGR3..5 jump straight to 0x20c08c instead of the dialog. */
int pops_apply_igr_original(void *staged_core, size_t core_size,
                            uint8_t igr_type, uint8_t no_igr) {
  static const uint16_t masks[] = {0x404f, 0x0900, 0x090f};
  if (!staged_core)
    return -EINVAL;
  if (!no_igr && (igr_type < 1 || igr_type > 6))
    return -EINVAL;
  if (core_size < (size_t)(0x00228a64 - POPS_CORE_BASE_ADDR))
    return -ERANGE;
  if (read_u32(staged_core, core_size, 0x00228a64) != 0x2622a980)
    return -EILSEQ;
  if (no_igr) {
    write_u32(staged_core, core_size, 0x00228a5c, 0x3c110086);
    write_u32(staged_core, core_size, 0x00228a60, 0x24030080);
    write_u16(staged_core, core_size, 0x00228a56, 0x1000);
    return 0;
  }
  write_u16(staged_core, core_size, 0x00228a56, 0x1462);
  if (igr_type <= 3) {
    write_u32(staged_core, core_size, 0x00228a5c, 0x3c110086);
    write_u32(staged_core, core_size, 0x00228a60, 0x24030080);
  } else {
    write_u32(staged_core, core_size, 0x00228a5c, 0x08083023);
    write_u32(staged_core, core_size, 0x00228a60, 0x00000000);
  }
  write_u16(staged_core, core_size, 0x00228a20, masks[(igr_type - 1) % 3]);
  write_u16(staged_core, core_size, 0x00228a50, masks[(igr_type - 1) % 3]);
  return 0;
}

int pops_apply_libcrypt_bypass(void *staged_core, size_t core_size) {
  if (!staged_core)
    return -EINVAL;
  if (core_size < (size_t)(0x0020CFB0 - POPS_CORE_BASE_ADDR + 4))
    return -ERANGE;
  if (read_u32(staged_core, core_size, 0x0020C1F0) != 0x3463ffff ||
      read_u32(staged_core, core_size, 0x0020CFB0) != 0x24020001)
    return -EILSEQ;
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

int pops_handle_disc_swap(uint16_t buttons_active_low,
                          int (*devctl_fn)(const char *dev, int cmd, void *arg, size_t arglen, void *buf, size_t buflen)) {
  if (!pops_check_disc_swap_combo(buttons_active_low)) {
    return 0; /* Combo not active */
  }
  if (!devctl_fn) {
    return -EINVAL;
  }

  /* 1. Open virtual CD-ROM lid */
  const char *dev = "pops:";
  int res = devctl_fn(dev, POPS_DEVCTL_OPEN_LID, NULL, 0, NULL, 0);
  if (res < 0) {
    dev = "pops0:";
    res = devctl_fn(dev, POPS_DEVCTL_OPEN_LID, NULL, 0, NULL, 0);
  }
  if (res < 0) return res;

  /* 2. Advance active disc index modulo configured disc count */
  res = devctl_fn(dev, POPS_DEVCTL_NEXT_DISC, NULL, 0, NULL, 0);
  if (res < 0) {
    /* If next disc failed (e.g. busy or single disc), close lid and return error */
    devctl_fn(dev, POPS_DEVCTL_CLOSE_LID, NULL, 0, NULL, 0);
    return res;
  }

  /* 3. Close virtual CD-ROM lid */
  res = devctl_fn(dev, POPS_DEVCTL_CLOSE_LID, NULL, 0, NULL, 0);
  if (res < 0) return res;

  return 1; /* Swap successfully triggered */
}

/* Red Book Subchannel Q CRC-16/CCITT, init 0, inverted, big-endian.
 * Standard data-track Q uses track-relative MSF and absolute LBA+150 MSF.
 * See psx-spx CD-ROM format (Q positional frames). */
static uint16_t pops_subq_crc(const uint8_t q[12]) {
  uint16_t crc = 0;
  for (int i = 0; i < 10; ++i) {
    crc ^= (uint16_t)q[i] << 8;
    for (int bit = 0; bit < 8; ++bit)
      crc = (uint16_t)((crc << 1) ^ ((crc & 0x8000) ? 0x1021 : 0));
  }
  return (uint16_t)~crc;
}

static uint8_t pops_bcd(uint32_t n) {
  return (uint8_t)(((n / 10) << 4) | (n % 10));
}

int pops_generate_subq(uint32_t lba, uint16_t libcrypt_key, uint8_t out_subq[12]) {
  if (!out_subq)
    return -EINVAL;

  /* Both Q time fields are two-digit BCD minutes. Reject positions
   * past absolute 99:59:74 instead of wrapping LBA+150 or emitting
   * corrupted track time and CRC. Never modify output on failure. */
  if (lba > UINT32_C(449849))
    return -ERANGE;

  memset(out_subq, 0, 12);
  out_subq[0] = 0x41; /* Track 1, Mode 1 data */
  out_subq[1] = 0x01;
  out_subq[2] = 0x01;

  uint32_t relative_seconds = lba / 75;
  uint32_t absolute_seconds = (lba + 150) / 75;
  out_subq[3] = pops_bcd(relative_seconds / 60);
  out_subq[4] = pops_bcd(relative_seconds % 60);
  out_subq[5] = pops_bcd(lba % 75);
  out_subq[6] = 0;
  out_subq[7] = pops_bcd(absolute_seconds / 60);
  out_subq[8] = pops_bcd(absolute_seconds % 60);
  out_subq[9] = pops_bcd((lba + 150) % 75);
  uint16_t crc = pops_subq_crc(out_subq);
  out_subq[10] = (uint8_t)(crc >> 8);
  out_subq[11] = (uint8_t)crc;

  /* Subchannel Q LibCrypt key injection for protected lead sectors (LBA 12..20) */
  if (libcrypt_key != 0 && lba >= 12 && lba <= 20) {
    out_subq[10] = (uint8_t)(libcrypt_key >> 8);
    out_subq[11] = (uint8_t)(libcrypt_key & 0xFF);
  }
  return 0;
}

int pops_cdrom_read_subq(int (*devctl_fn)(const char *dev, int cmd, void *arg, size_t arglen, void *buf, size_t buflen),
                         uint32_t lba, uint8_t out_subq[12]) {
  if (!devctl_fn || !out_subq)
    return -EINVAL;
  const char *dev = "pops:";
  int res = devctl_fn(dev, POPS_DEVCTL_GET_SUBQ, &lba, sizeof(lba), out_subq, 12);
  if (res < 0) {
    dev = "pops0:";
    res = devctl_fn(dev, POPS_DEVCTL_GET_SUBQ, &lba, sizeof(lba), out_subq, 12);
  }
  return res;
}

int pops_cheat_engine_tick(void *ps1_ram_base, const PopsCheatEntry *cheats, uint16_t cheat_count) {
  if (!ps1_ram_base || !cheats || cheat_count == 0)
    return 0;
  /* One implementation, shared with the resident code that runs in POPS. */
  pops_resident_cheat_pass((uint8_t *)ps1_ram_base, cheats, cheat_count);
  return 0;
}

int pops_cheat_engine_tick_ex(void *ps1_ram_base, const PopsCheatEntry *cheats,
                             uint16_t cheat_count, uint32_t frame_count, uint8_t safe_mode) {
  if (!ps1_ram_base || !cheats || cheat_count == 0)
    return 0;

  (void)frame_count;
  if (pops_safe_mode_blocks((const uint8_t *)ps1_ram_base, safe_mode))
    return 0;

  return pops_cheat_engine_tick(ps1_ram_base, cheats, cheat_count);
}

int pops_apply_cheats(void *ps1_ram_base, const PopsCheatEntry *cheats, uint16_t cheat_count) {
  return pops_cheat_engine_tick(ps1_ram_base, cheats, cheat_count);
}

int pops_apply_igr_direct_exit(void *staged_core, size_t core_size) {
  if (!staged_core)
    return -EINVAL;
  if (core_size < (size_t)(0x00228a68 - POPS_CORE_BASE_ADDR + 4))
    return -ERANGE;
  uint32_t cur_5c = read_u32(staged_core, core_size, 0x00228a5c);
  uint32_t cur_60 = read_u32(staged_core, core_size, 0x00228a60);
  uint32_t cur_64 = read_u32(staged_core, core_size, 0x00228a64);
  uint32_t cur_68 = read_u32(staged_core, core_size, 0x00228a68);
  if (cur_5c == 0x24020001 && cur_60 == 0x10000015 &&
      cur_64 == 0x00000000 && cur_68 == 0x00000000)
    return 0;
  if (cur_5c != 0x3c110086 || cur_60 != 0x24030080 ||
      cur_64 != 0x2622a980 || cur_68 != 0x0000202d)
    return -EINVAL;
  write_u32(staged_core, core_size, 0x00228a5c, 0x24020001); /* li $v0, 1 */
  write_u32(staged_core, core_size, 0x00228a60, 0x10000015); /* b 0x00228ab8 */
  write_u32(staged_core, core_size, 0x00228a64, 0x00000000); /* nop */
  write_u32(staged_core, core_size, 0x00228a68, 0x00000000); /* nop */
  return 0;
}

int pops_apply_igr_pad_control(void *staged_core, size_t core_size) {
  if (!staged_core)
    return -EINVAL;
  if (core_size < (size_t)(0x002264f4 - POPS_CORE_BASE_ADDR + 4))
    return -ERANGE;
  uint32_t cur_4c4 = read_u32(staged_core, core_size, 0x002264c4);
  uint32_t cur_4f4 = read_u32(staged_core, core_size, 0x002264f4);
  if (cur_4c4 == 0x8c830004 && cur_4f4 == 0x30620060)
    return 0;
  if (cur_4c4 != 0x8c830000 || cur_4f4 != 0x30620020)
    return -EINVAL;
  write_u32(staged_core, core_size, 0x002264c4, 0x8c830004);
  write_u32(staged_core, core_size, 0x002264f4, 0x30620060);
  return 0;
}

int pops_apply_igr_exit(void *staged_core, size_t core_size) {
  uint8_t *bytes = (uint8_t *)staged_core;
  if (!bytes)
    return -EINVAL;
  if (core_size < (size_t)(0x0020c0a4 - POPS_CORE_BASE_ADDR + 4))
    return -ERANGE;
  size_t off = 0x0020c0a4 - POPS_CORE_BASE_ADDR;
  uint32_t current = 0;
  for (unsigned j = 0; j < 4; ++j)
    current |= (uint32_t)bytes[off + j] << (8 * j);
  if (current != 0x0c08b44c)
    return -EINVAL;
  return write_u32(staged_core, core_size, 0x0020c0a4, 0x0c08d8ae);
}

int pops_apply_iopcd_stack_size(void *staged_core, size_t core_size, uint8_t stack_size) {
  uint8_t *bytes = (uint8_t *)staged_core;
  if (!bytes)
    return -EINVAL;
  if (core_size < (size_t)(0x002fb599 - POPS_CORE_BASE_ADDR + 1))
    return -ERANGE;
  size_t off = 0x002fb599 - POPS_CORE_BASE_ADDR;
  if (bytes[off] != 0x08)
    return -EINVAL;
  return write_u8(staged_core, core_size, 0x002fb599, stack_size ? stack_size : 0x40);
}

int pops_apply_hdd_init_exit(void *staged_core, size_t core_size) {
  uint8_t *bytes = (uint8_t *)staged_core;
  if (!bytes)
    return -EINVAL;
  if (core_size < (size_t)(0x00200766 - POPS_CORE_BASE_ADDR + 2))
    return -ERANGE;
  size_t off = 0x00200766 - POPS_CORE_BASE_ADDR;
  uint16_t current = (uint16_t)bytes[off] | ((uint16_t)bytes[off + 1] << 8);
  if (current != 0x1040)
    return -EINVAL;
  return write_u16(staged_core, core_size, 0x00200766, 0x1000);
}

int pops_apply_vmc0_disable(void *staged_core, size_t core_size) {
  uint8_t *bytes = (uint8_t *)staged_core;
  if (!bytes)
    return -EINVAL;
  if (core_size < (size_t)(0x002007b4 - POPS_CORE_BASE_ADDR + 1))
    return -ERANGE;
  size_t off = 0x002007b4 - POPS_CORE_BASE_ADDR;
  if (bytes[off] != 0x01)
    return -EINVAL;
  return write_u8(staged_core, core_size, 0x002007b4, 0x00);
}

int pops_apply_vmc1_disable(void *staged_core, size_t core_size) {
  uint8_t *bytes = (uint8_t *)staged_core;
  if (!bytes)
    return -EINVAL;
  if (core_size < (size_t)(0x0020d0e0 - POPS_CORE_BASE_ADDR + 4))
    return -ERANGE;
  size_t off = 0x0020d0e0 - POPS_CORE_BASE_ADDR;
  uint32_t current = 0;
  for (unsigned j = 0; j < 4; ++j)
    current |= (uint32_t)bytes[off + j] << (8 * j);
  if (current != 0x1480ffc1)
    return -EINVAL;
  return write_u32(staged_core, core_size, 0x0020d0e0, 0x24040000);
}

int pops_apply_slbb_vcd_check_bypass(void *staged_core, size_t core_size) {
  uint8_t *bytes = (uint8_t *)staged_core;
  if (!bytes)
    return -EINVAL;
  if (core_size < (size_t)(0x0020085c - POPS_CORE_BASE_ADDR + 4))
    return -ERANGE;

  size_t off_834 = 0x00200834 - POPS_CORE_BASE_ADDR;
  size_t off_83c = 0x0020083c - POPS_CORE_BASE_ADDR;
  size_t off_85c = 0x0020085c - POPS_CORE_BASE_ADDR;

  uint32_t cur_834 = 0, cur_83c = 0, cur_85c = 0;
  for (unsigned j = 0; j < 4; ++j) {
    cur_834 |= (uint32_t)bytes[off_834 + j] << (8 * j);
    cur_83c |= (uint32_t)bytes[off_83c + j] << (8 * j);
    cur_85c |= (uint32_t)bytes[off_85c + j] << (8 * j);
  }

  if (cur_834 != 0x0c08b520 && cur_834 != 0x00000000)
    return -EINVAL;
  if (cur_83c != 0x0441000a && cur_83c != 0x1000000a)
    return -EINVAL;
  if (cur_85c != 0x1000fffa && cur_85c != 0x00000000)
    return -EINVAL;

  write_u32(staged_core, core_size, 0x00200834, 0x00000000);
  write_u32(staged_core, core_size, 0x0020083c, 0x1000000a);
  write_u32(staged_core, core_size, 0x0020085c, 0x00000000);
  return 0;
}

int pops_apply_bios_osd_disable(void *staged_core, size_t core_size) {
  uint8_t *bytes = (uint8_t *)staged_core;
  if (!bytes)
    return -EINVAL;
  if (core_size < (size_t)(0x002525b0 - POPS_CORE_BASE_ADDR + 2))
    return -ERANGE;
  size_t off = 0x002525b0 - POPS_CORE_BASE_ADDR;
  uint16_t cur = (uint16_t)bytes[off] | ((uint16_t)bytes[off + 1] << 8);
  if (cur != 0x1bfc && cur != 0x0648)
    return -EINVAL;
  return write_u16(staged_core, core_size, 0x002525b0, 0x0648);
}

int pops_apply_bios_osd_enable(void *staged_core, size_t core_size) {
  uint8_t *bytes = (uint8_t *)staged_core;
  if (!bytes)
    return -EINVAL;
  if (core_size < (size_t)(0x002525b0 - POPS_CORE_BASE_ADDR + 2))
    return -ERANGE;
  size_t off = 0x002525b0 - POPS_CORE_BASE_ADDR;
  uint16_t cur = (uint16_t)bytes[off] | ((uint16_t)bytes[off + 1] << 8);
  if (cur != 0x1bfc && cur != 0x0648)
    return -EINVAL;
  return write_u16(staged_core, core_size, 0x002525b0, 0x1bfc);
}

int pops_apply_slbb_vcd_path_redirect(void *staged_core, size_t core_size) {
  uint8_t *bytes = (uint8_t *)staged_core;
  if (!bytes)
    return -EINVAL;
  if (core_size < (size_t)(0x004ffe92 - POPS_CORE_BASE_ADDR))
    return -ERANGE;
  write_u8(staged_core, core_size, 0x004ffe8b, 0x31);
  write_u8(staged_core, core_size, 0x004ffe8e, 0x50);
  write_u8(staged_core, core_size, 0x004ffe8f, 0x4f);
  write_u16(staged_core, core_size, 0x004ffe90, 0x5350);
  return 0;
}

int pops_apply_resource_relink(void *staged_core, size_t core_size, int is_usb_flat) {
  uint8_t *bytes = (uint8_t *)staged_core;
  if (!bytes)
    return -EINVAL;
  if (core_size < (size_t)(0x004f8110 - POPS_CORE_BASE_ADDR))
    return -ERANGE;
  write_u16(staged_core, core_size, 0x00200784, 0x8000);
  write_u16(staged_core, core_size, 0x0020cf58, 0x8080);
  write_u16(staged_core, core_size, 0x0020c920, 0x8100);
  write_u16(staged_core, core_size, 0x0020cfec, 0x8100);
  write_u16(staged_core, core_size, 0x0020c8b8, 0x8100);
  const char *target = is_usb_flat ? "pfs1:/" : "pfs1:/POPS/";
  size_t len = strlen(target) + 1;
  memcpy(bytes + (0x004f8080 - POPS_CORE_BASE_ADDR), target, len);
  memcpy(bytes + (0x004f8100 - POPS_CORE_BASE_ADDR), target, len);
  return 0;
}

int pops_apply_exception_hook(void *staged_core, size_t core_size) {
  uint8_t *bytes = (uint8_t *)staged_core;
  if (!bytes)
    return -EINVAL;
  if (core_size < (size_t)(0x00232d0c - POPS_CORE_BASE_ADDR))
    return -ERANGE;
  return write_u32(staged_core, core_size, 0x00232d08, 0x0c518000);
}

int pops_apply_all_config_patches(void *staged_core, size_t core_size, const PopsConfig *cfg) {
  int result;
  int video_requested;
  if (!staged_core || !cfg)
    return -EINVAL;

  /* The original defers $FORCEPAL until after fix files, where PATCH's
   * disable-auto state can suppress it. Only $HDTVFIX runs at this stage. */
  video_requested = cfg->hdtv_fix;

  /* These are mutually dependent writes to the staged executable. Fail
   * before applying an otherwise valid compatibility mode when any selected
   * later helper would reject this memory window. */
  if (cfg->compat_modes & (1 << 7))
    return -ENOTSUP;
  if (cfg->video_mode > POPS_VMODE_240P)
    return -ENOTSUP;
  if ((video_requested || cfg->original_tokens || cfg->no_igr || cfg->igr_type) &&
      core_size < 0x250000)
    return -EINVAL;
  if (cfg->video_mode == POPS_VMODE_NTSC2PAL &&
      core_size < (size_t)(0x00502770 - POPS_CORE_BASE_ADDR + 4))
    return -ERANGE;
  if (cfg->igr_type > 6)
    return -EINVAL;

  result = display_config(staged_core, core_size, cfg, 0);
  if (result)
    return result;

  if (cfg->original_tokens & POPS_TOK_UNDO_MASK) {
    result = pops_apply_undo_tokens(staged_core, core_size, cfg->original_tokens);
    if (result)
      return result;
  }
  if (cfg->compat_modes) {
    result = pops_apply_compat_modes(staged_core, core_size, cfg->compat_modes);
    if (result)
      return result;
  }
  if (video_requested) {
    result = pops_apply_video_overrides(staged_core, core_size,
                                        POPS_VMODE_DEFAULT,
                                        cfg->hdtv_fix, 0, 0);
    if (result) return result;
  }
  if (cfg->original_tokens) {
    result = pops_apply_original_tokens(staged_core, core_size, cfg->original_tokens);
    if (result) return result;
  }
  result = pops_apply_display_config(staged_core, core_size, cfg);
  if (result) return result;
  if (cfg->no_vmc0) {
    result = pops_apply_vmc0_disable(staged_core, core_size);
    if (result) return result;
  }
  if (cfg->no_vmc1) {
    result = pops_apply_vmc1_disable(staged_core, core_size);
    if (result) return result;
  }
  if (cfg->no_igr || cfg->igr_type) {
    result = pops_apply_igr_original(staged_core, core_size, cfg->igr_type, cfg->no_igr);
    if (result) return result;
  }
  if (!cfg->no_igr) {
    if (core_size >= (size_t)(0x0020c0a4 - POPS_CORE_BASE_ADDR + 4)) {
      uint32_t cur = read_u32(staged_core, core_size, 0x0020c0a4);
      if (cur == 0x0c08b44c) {
        result = pops_apply_igr_exit(staged_core, core_size);
        if (result) return result;
      }
    }
    /* Without an $IGRn command keep launcHER's direct exit, which the user
     * confirmed on hardware; with one, the original writes above stand. */
    if (!cfg->igr_type && core_size >= (size_t)(0x00228a68 - POPS_CORE_BASE_ADDR + 4)) {
      uint32_t cur_5c = read_u32(staged_core, core_size, 0x00228a5c);
      if (cur_5c == 0x3c110086) {
        result = pops_apply_igr_direct_exit(staged_core, core_size);
        if (result) return result;
      }
    }
  }
  if (core_size >= (size_t)(0x002fb599 - POPS_CORE_BASE_ADDR + 1)) {
    uint8_t *b = (uint8_t *)staged_core;
    if (b[0x002fb599 - POPS_CORE_BASE_ADDR] == 0x08) {
      result = pops_apply_iopcd_stack_size(staged_core, core_size, 0x40);
      if (result) return result;
    }
  }
  if (core_size >= (size_t)(0x00200766 - POPS_CORE_BASE_ADDR + 2)) {
    uint8_t *b = (uint8_t *)staged_core;
    size_t off = 0x00200766 - POPS_CORE_BASE_ADDR;
    uint16_t cur = (uint16_t)b[off] | ((uint16_t)b[off + 1] << 8);
    if (cur == 0x1040) {
      result = pops_apply_hdd_init_exit(staged_core, core_size);
      if (result) return result;
    }
  }
  if (core_size >= (size_t)(0x002525b0 - POPS_CORE_BASE_ADDR + 2)) {
    size_t off = 0x002525b0 - POPS_CORE_BASE_ADDR;
    uint8_t *b = (uint8_t *)staged_core;
    uint16_t cur = (uint16_t)b[off] | ((uint16_t)b[off + 1] << 8);
    if (cfg->no_boot && cur == 0x0648) {
      result = pops_apply_bios_osd_enable(staged_core, core_size);
      if (result) return result;
    }
  }
  return 0;
}
