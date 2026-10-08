#include "pops_external.h"
#include <string.h>

#define EE_START UINT32_C(0x00100000)
#define EE_END UINT32_C(0x02000000)
#define SCRATCH_START UINT32_C(0x70000000)
#define SCRATCH_END UINT32_C(0x70004000)
#define HEADER_SIZE 64u

static uint16_t le16(const uint8_t *p) {
  return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t le32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static int ee_range(uint32_t address, uint32_t length) {
  return address >= EE_START && address < EE_END && length <= EE_END - address;
}

int pops_elf_inspect(const void *file, size_t size, PopsElfInfo *out) {
  const uint8_t *data = file;
  PopsElfInfo info = {0};
  uint32_t phoff;
  uint16_t count;
  int entry_found = 0;
  if (!data || !out || size < 52 || memcmp(data, "\177ELF", 4))
    return POPS_FILE_INVALID;
  if (data[4] != 1 || data[5] != 1 || data[6] != 1 ||
      le16(data + 16) != 2 || le16(data + 18) != 8 || le32(data + 20) != 1)
    return POPS_FILE_UNSUPPORTED;
  if (le16(data + 40) != 52 || le16(data + 42) != 32)
    return POPS_FILE_INVALID;
  phoff = le32(data + 28);
  count = le16(data + 44);
  if (!count || phoff < 52 || phoff > size || count > (size - phoff) / 32)
    return POPS_FILE_INVALID;
  info.entry = le32(data + 24);
  for (uint16_t i = 0; i < count; i++) {
    const uint8_t *p = data + phoff + (size_t)i * 32;
    uint32_t offset, address, filesz, memsz, align;
    if (le32(p) != 1)
      continue;
    offset = le32(p + 4);
    address = le32(p + 8);
    filesz = le32(p + 16);
    memsz = le32(p + 20);
    align = le32(p + 28);
    if (filesz > memsz || offset > size || filesz > size - offset)
      return POPS_FILE_INVALID;
    /* The reference POPS ELF has a zero-file-size scratchpad PT_LOAD.
     * Accept that BSS reservation, but never treat arbitrary MMIO as load RAM. */
    if (!memsz || (!ee_range(address, memsz) &&
        !(address >= SCRATCH_START && address < SCRATCH_END &&
          memsz <= SCRATCH_END - address && !filesz && !(le32(p + 24) & 1))))
      return POPS_FILE_RANGE;
    if (align > 1 && ((align & (align - 1)) || address % align != offset % align))
      return POPS_FILE_INVALID;
    /* The entry must point to aligned, file-backed executable instructions. */
    if ((le32(p + 24) & 1) && !(info.entry & 3) && info.entry >= address &&
        info.entry - address <= filesz && filesz - (info.entry - address) >= 4)
      entry_found = 1;
    for (uint16_t j = 0; j < i; j++) {
      const uint8_t *q = data + phoff + (size_t)j * 32;
      uint32_t other = le32(q + 8), other_size = le32(q + 20);
      if (le32(q) == 1 && address < (uint64_t)other + other_size &&
          other < (uint64_t)address + memsz)
        return POPS_FILE_RANGE;
    }
    info.load_segments++;
  }
  if (!info.load_segments || !entry_found)
    return POPS_FILE_INVALID;
  *out = info;
  return POPS_FILE_OK;
}

int pops_container_inspect(const void *file, size_t size, PopsContainer *out) {
  const uint8_t *data = file;
  PopsContainer result = {0};
  int trojan;
  if (!data || !out || size < HEADER_SIZE)
    return POPS_FILE_INVALID;
  trojan = !memcmp(data, "TROJAN_", 7) && data[7] >= '0' && data[7] <= '9';
  if (trojan) {
    result.slot = data[7] - '0';
  } else if (!memcmp(data, "PATCH_", 6) && data[6] >= '1' &&
             data[6] <= '9' && data[7] == 0) {
    result.slot = data[6] - '0';
  } else {
    return POPS_FILE_UNSUPPORTED;
  }
  result.control = le32(data + 8);
  result.flags = le32(data + 12);
  result.load = le32(data + 16);
  result.entry = le32(data + 20);
  result.hook = le32(data + 24);
  result.payload_size = le32(data + 28);
  memcpy(result.metadata, data + 32, sizeof(result.metadata));
  if (result.payload_size != size - HEADER_SIZE)
    return POPS_FILE_INVALID;
  if (result.flags != UINT32_C(0x00010001) && result.flags != UINT32_C(0x00010003) &&
      result.flags != UINT32_C(0x00010002))
    return POPS_FILE_UNSUPPORTED;
  if (trojan) {
    if ((result.control & UINT32_C(0xff00ffff)) ||
        (result.flags == UINT32_C(0x00010001) && result.control))
      return POPS_FILE_UNSUPPORTED;
    if (!result.payload_size || ((result.load | result.entry | result.hook |
                                result.payload_size) & 3))
      return POPS_FILE_INVALID;
    if (!ee_range(result.load, result.payload_size) || !ee_range(result.hook, 8) ||
        result.entry < result.load || result.entry - result.load >= result.payload_size)
      return POPS_FILE_RANGE;
    if (result.load < (uint64_t)result.hook + 8 &&
        result.hook < (uint64_t)result.load + result.payload_size)
      return POPS_FILE_RANGE;
    result.kind = POPS_CONTAINER_TROJAN;
  } else {
    if (result.entry || result.hook)
      return POPS_FILE_UNSUPPORTED;
    if (result.payload_size) {
      if (!ee_range(result.load, result.payload_size))
        return POPS_FILE_RANGE;
      result.kind = POPS_CONTAINER_DATA;
    } else {
      if (result.load)
        return POPS_FILE_INVALID;
      result.kind = POPS_CONTAINER_CONFIG;
    }
  }
  *out = result;
  return POPS_FILE_OK;
}

static int window_offset(uint32_t address, uint32_t length, uint32_t base,
                         size_t span, size_t *offset) {
  if (address < base || address - base > span || length > span - (address - base))
    return POPS_FILE_RANGE;
  *offset = address - base;
  return POPS_FILE_OK;
}

int pops_container_plan(const void *file, size_t size, uint32_t base,
                        size_t span, PopsContainerPlan *out) {
  PopsContainerPlan plan = {0};
  int status;
  if (!out)
    return POPS_FILE_INVALID;
  if (base < EE_START || base >= EE_END || span > EE_END - base)
    return POPS_FILE_RANGE;
  status = pops_container_inspect(file, size, &plan.container);
  if (status)
    return status;
  if (plan.container.kind != POPS_CONTAINER_CONFIG) {
    status = window_offset(plan.container.load, plan.container.payload_size,
                           base, span, &plan.payload_offset);
    if (status)
      return status;
    if (plan.container.kind == POPS_CONTAINER_TROJAN) {
      plan.hook_instruction = UINT32_C(0x0c000000) | (plan.container.entry >> 2);
      plan.hook_size = 4;
      uint32_t width = (plan.container.control >> 16) & 0xff;
      if ((plan.container.flags & 0xff) == 2 && width >= 1 && width <= 3) {
        plan.hook_instruction = UINT32_C(0x08000000) | (plan.container.entry >> 2);
        plan.hook_size = (uint8_t)(width * 4);
      }
      if (plan.container.load < (uint64_t)plan.container.hook + plan.hook_size &&
          plan.container.hook < (uint64_t)plan.container.load + plan.container.payload_size)
        return POPS_FILE_RANGE;
      status = window_offset(plan.container.hook, plan.hook_size > 8 ? 12 : 8,
                             base, span, &plan.hook_offset);
      if (status)
        return status;
    }
  }
  *out = plan;
  return POPS_FILE_OK;
}

static void write_le32(uint8_t *p, uint32_t value) {
  p[0] = (uint8_t)value;
  p[1] = (uint8_t)(value >> 8);
  p[2] = (uint8_t)(value >> 16);
  p[3] = (uint8_t)(value >> 24);
}

int pops_container_stage(const void *file, size_t size, uint32_t base,
                         void *memory, size_t span, const uint32_t *expected_hook,
                         size_t expected_count) {
  PopsContainerPlan plan;
  uintptr_t source = (uintptr_t)file, dest = (uintptr_t)memory;
  uint8_t *bytes = memory;
  int status;
  if (!memory)
    return POPS_FILE_INVALID;
  status = pops_container_plan(file, size, base, span, &plan);
  if (status)
    return status;
  if (plan.container.kind == POPS_CONTAINER_CONFIG)
    return POPS_FILE_UNSUPPORTED;
  /* A copy must not overwrite the container it is still consuming. */
  if (source <= dest ? dest - source < size : source - dest < span)
    return POPS_FILE_RANGE;
  if (plan.container.kind == POPS_CONTAINER_TROJAN) {
    size_t guard_count = plan.hook_size > 8 ? 3 : 2;
    if (!expected_hook || expected_count != guard_count)
      return POPS_FILE_INVALID;
    for (size_t i = 0; i < guard_count; i++) {
      if (le32(bytes + plan.hook_offset + i * 4) != expected_hook[i])
        return POPS_FILE_GUARD;
    }
  }
  memcpy(bytes + plan.payload_offset, (const uint8_t *)file + HEADER_SIZE,
         plan.container.payload_size);
  if (plan.container.kind == POPS_CONTAINER_TROJAN) {
    write_le32(bytes + plan.hook_offset, plan.hook_instruction);
    if (plan.hook_size > 4)
      memset(bytes + plan.hook_offset + 4, 0, plan.hook_size - 4);
  }
  return POPS_FILE_OK;
}

int pops_patch_options(const PopsContainer *container, PopsPatchOptions *out) {
  PopsPatchOptions options = {{0}, POPS_PATCH_VIDEO_NONE};
  if (!container || !out)
    return POPS_FILE_INVALID;
  if (container->kind != POPS_CONTAINER_CONFIG && container->kind != POPS_CONTAINER_DATA)
    return POPS_FILE_UNSUPPORTED;
  if (container->control > 7)
    return POPS_FILE_UNSUPPORTED;
  if (container->control & 1)
    memcpy(options.modes, container->metadata + 24, sizeof(options.modes));
  else if (le32(container->metadata + 24))
    return POPS_FILE_INVALID;
  switch (container->control & 6) {
  case 2:
    options.video = POPS_PATCH_VIDEO_PAL;
    break;
  case 4:
    options.video = POPS_PATCH_VIDEO_DISABLE_AUTO;
    break;
  case 6:
    options.video = POPS_PATCH_VIDEO_CONTROL6;
    break;
  }
  *out = options;
  return POPS_FILE_OK;
}
