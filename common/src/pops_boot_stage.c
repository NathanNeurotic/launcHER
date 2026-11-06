#include "pops_external.h"
#include <string.h>

static int overlaps(const void *left, size_t left_size,
                     const void *right, size_t right_size) {
  uintptr_t a = (uintptr_t)left, b = (uintptr_t)right;
  return a <= b ? b - a < left_size : a - b < right_size;
}

static int buffers_check(const PopsBootPlan *plan, const PopsBootBuffers *buffers,
                          const void *source, size_t source_size,
                          const void *iop_source, size_t iop_size) {
  const void *destinations[3];
  size_t lengths[3];
  size_t i, j;
  uint32_t ram_end = plan->bss_address + plan->bss_size;
  if (!buffers || !buffers->ram || !buffers->scratchpad || !buffers->iop)
    return POPS_FILE_INVALID;
  if (buffers->ram_base != 0x100000 ||
      buffers->ram_size > 0x2000000 - buffers->ram_base ||
      ram_end - buffers->ram_base > buffers->ram_size ||
      buffers->scratchpad_size < plan->scratchpad_size ||
      buffers->iop_size < plan->iop_size)
    return POPS_FILE_RANGE;
  destinations[0] = buffers->ram;
  destinations[1] = buffers->scratchpad;
  destinations[2] = buffers->iop;
  lengths[0] = ram_end - buffers->ram_base;
  lengths[1] = plan->scratchpad_size;
  lengths[2] = plan->iop_size;
  for (i = 0; i < 3; ++i) {
    if (overlaps(destinations[i], lengths[i], source, source_size) ||
        (iop_source && overlaps(destinations[i], lengths[i], iop_source, iop_size)))
      return POPS_FILE_RANGE;
    for (j = 0; j < i; ++j)
      if (overlaps(destinations[i], lengths[i], destinations[j], lengths[j]))
        return POPS_FILE_RANGE;
  }
  return POPS_FILE_OK;
}

static uint32_t read32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void clear_buffers(const PopsBootPlan *plan, const PopsBootBuffers *buffers) {
  memset(buffers->ram, 0, plan->bss_address + plan->bss_size - buffers->ram_base);
  memset(buffers->scratchpad, 0, plan->scratchpad_size);
}

int pops_boot_stage_pak(const void *decoded, size_t size, const PopsBootBuffers *buffers) {
  const uint8_t *bytes = decoded;
  PopsBootPlan plan;
  PopsBootBuffers local_buffers;
  int status = pops_boot_plan_pak(decoded, size, &plan);
  if (status)
    return status;
  if (!buffers)
    return POPS_FILE_INVALID;
  local_buffers = *buffers;
  buffers = &local_buffers;
  status = buffers_check(&plan, buffers, decoded, size, NULL, 0);
  if (status)
    return status;
  clear_buffers(&plan, buffers);
  memcpy((uint8_t *)buffers->ram + plan.core_address - buffers->ram_base,
         bytes, plan.core_size);
  memcpy(buffers->iop, bytes + plan.iop_offset, plan.iop_size);
  return POPS_FILE_OK;
}

int pops_boot_stage_elf(const void *elf, size_t elf_size, const void *iop,
                        size_t iop_size, const PopsBootBuffers *buffers) {
  const uint8_t *bytes = elf;
  PopsBootPlan plan;
  PopsBootBuffers local_buffers;
  uint32_t phoff;
  unsigned count, i;
  int status = pops_boot_plan_elf(elf, elf_size, iop, iop_size, &plan);
  if (status)
    return status;
  if (!buffers)
    return POPS_FILE_INVALID;
  local_buffers = *buffers;
  buffers = &local_buffers;
  status = buffers_check(&plan, buffers, elf, elf_size, iop, iop_size);
  if (status)
    return status;
  /* Exact known ELF identity fixes its validated segment map. Only the two
   * file-backed user-RAM segments need copies; BSS-only segments were cleared. */
  phoff = read32(bytes + 28);
  count = (unsigned)bytes[44] | ((unsigned)bytes[45] << 8);
  clear_buffers(&plan, buffers);
  for (i = 0; i < count; ++i) {
    const uint8_t *ph = bytes + phoff + i * 32;
    uint32_t length = read32(ph + 16);
    if (read32(ph) == 1 && length)
      memcpy((uint8_t *)buffers->ram + read32(ph + 8) - buffers->ram_base,
             bytes + read32(ph + 4), length);
  }
  memcpy(buffers->iop, iop, plan.iop_size);
  return POPS_FILE_OK;
}
