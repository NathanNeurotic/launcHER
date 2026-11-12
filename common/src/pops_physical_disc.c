#include "pops_physical_disc.h"
#include "pops_config.h"
#include "pops_modes_patches.h"
#include <errno.h>
#include <string.h>

#define CORE_BASE UINT32_C(0x00200000)

/* POPS passes the image name to its disc layer's start-up call:
 * 0x200790 jal 0x210540, 0x200794 move a0,sp. The original replaces the
 * delay slot with daddu a0,zero,zero. */
#define CDINIT_ARG_ADDR UINT32_C(0x00200794)
#define CDINIT_ARG_SHIPPED UINT32_C(0x03a0202d)
#define CDINIT_ARG_NULL UINT32_C(0x0000202d)

#define NAME_ADDR UINT32_C(0x004f8000)
#define NAME_SIZE 0x80u

/* The $MUTE_CDDA sites and what Sony ships there (the values
 * $UNDO_MUTE_CDDA puts back). The writes themselves are
 * pops_apply_original_tokens' (POPS_TOK_MUTE_CDDA). */
typedef struct {
  uint32_t address;
  uint32_t shipped;
  uint8_t width;
} Site;
static const Site mute_sites[] = {
  {UINT32_C(0x0020f0b6), 0x02, 1},
  {UINT32_C(0x0020ebf2), 0x03, 1},
  {UINT32_C(0x0020f0e0), UINT32_C(0xae000014), 4},
};

static int accepted_type(int32_t disc_type) {
  return disc_type == POPS_PHYSICAL_TYPE_PS1_CD || disc_type == POPS_PHYSICAL_TYPE_PS1_CDDA ||
         disc_type == POPS_PHYSICAL_TYPE_PS2_CD || disc_type == POPS_PHYSICAL_TYPE_PS2_CDDA;
}

static int mutes_cdda(int32_t disc_type) {
  return disc_type == POPS_PHYSICAL_TYPE_PS1_CDDA || disc_type == POPS_PHYSICAL_TYPE_PS2_CDDA;
}

static uint32_t load_le(const uint8_t *core, uint32_t address, unsigned width) {
  const uint8_t *p = core + (address - CORE_BASE);
  uint32_t value = 0;
  for (unsigned i = 0; i < width; ++i)
    value |= (uint32_t)p[i] << (8 * i);
  return value;
}

static void store_le32(uint8_t *core, uint32_t address, uint32_t value) {
  uint8_t *p = core + (address - CORE_BASE);
  for (unsigned i = 0; i < 4; ++i)
    p[i] = (uint8_t)(value >> (8 * i));
}

static int fits(size_t core_size, uint32_t address, uint32_t width) {
  return (uint64_t)(address - CORE_BASE) + width <= (uint64_t)core_size;
}

int pops_physical_disc_plan(PopsPhysicalDiscPlan *plan, int32_t drive_status,
                            int32_t disc_type, const uint8_t *sector4, int read_ok) {
  if (!plan)
    return -EINVAL;
  memset(plan, 0, sizeof(*plan));
  plan->status = drive_status;
  if (drive_status == POPS_PHYSICAL_STATUS_REFUSED) {
    /* 0x8767cc: straight to "Cannot access (%d)!"; the disc type is never
     * asked for. */
    plan->fatal = POPS_PHYSICAL_FATAL_ACCESS;
    return 0;
  }
  plan->type_asked = 1;
  plan->disc_type = disc_type;
  if (!accepted_type(disc_type)) {
    plan->fatal = POPS_PHYSICAL_FATAL_NOT_PS1;
    return 0;
  }
  plan->sector_read = 1;
  plan->read_failed = read_ok ? 0 : 1;
  if (sector4)
    memcpy(plan->region, sector4 + POPS_PHYSICAL_LICENCE_OFFSET, sizeof(plan->region));
  plan->mute_cdda = mutes_cdda(disc_type) ? 1 : 0;
  return 0;
}

const char *pops_physical_disc_message(int fatal) {
  switch (fatal) {
  case POPS_PHYSICAL_FATAL_ACCESS:
    return "Cannot access (%d)!\n\n";
  case POPS_PHYSICAL_FATAL_NOT_PS1:
    return "NO PS1 CDROM!\n\n";
  default:
    return NULL;
  }
}

int pops_physical_disc_stage(void *staged_core, size_t core_size, int disc_type) {
  uint8_t *core = staged_core;
  int mute = mutes_cdda(disc_type);
  if (!core || !accepted_type(disc_type))
    return -EINVAL;
  if (!fits(core_size, CDINIT_ARG_ADDR, 4))
    return -ERANGE;
  if (mute)
    for (size_t i = 0; i < sizeof(mute_sites) / sizeof(mute_sites[0]); ++i)
      if (!fits(core_size, mute_sites[i].address, mute_sites[i].width))
        return -ERANGE;
  if (load_le(core, CDINIT_ARG_ADDR, 4) != CDINIT_ARG_SHIPPED)
    return -EILSEQ;
  if (mute)
    for (size_t i = 0; i < sizeof(mute_sites) / sizeof(mute_sites[0]); ++i)
      if (load_le(core, mute_sites[i].address, mute_sites[i].width) != mute_sites[i].shipped)
        return -EILSEQ;
  /* Every site is in range and as shipped, so neither write below can
   * fail part-way: the original's order, the NULL argument first. */
  store_le32(core, CDINIT_ARG_ADDR, CDINIT_ARG_NULL);
  if (mute)
    return pops_apply_original_tokens(core, core_size, POPS_TOK_MUTE_CDDA);
  return 0;
}

int pops_physical_disc_clear_name(void *staged_core, size_t core_size) {
  if (!staged_core)
    return -EINVAL;
  if (!fits(core_size, NAME_ADDR, NAME_SIZE))
    return -ERANGE;
  memset((uint8_t *)staged_core + (NAME_ADDR - CORE_BASE), 0, NAME_SIZE);
  return 0;
}

int pops_physical_disc_fingerprint(const uint8_t *sector16, const uint8_t *sector22,
                                   uint8_t out[POPS_PHYSICAL_SIG_SIZE]) {
  if (!out)
    return -EINVAL;
  memset(out, 0, POPS_PHYSICAL_SIG_SIZE);
  if (sector16) {
    memcpy(out, sector16 + 40, 0x30);
    memcpy(out + 0x30, sector16 + 808, 0x20);
  }
  if (sector22)
    memcpy(out + 0x50, sector22 + 56, 0x40);
  return 0;
}
