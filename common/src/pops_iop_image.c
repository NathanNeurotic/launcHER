#include "pops_external.h"
#include <string.h>

static uint32_t read32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static uint16_t read16(const uint8_t *p) {
  return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

int pops_iop_image_inspect(const void *file, size_t size, PopsIopImage *out) {
  static const uint8_t reset[10] = {'R','E','S','E','T',0,0,0,0,0};
  static const uint8_t romdir[10] = {'R','O','M','D','I','R',0,0,0,0};
  static const uint8_t extinfo[10] = {'E','X','T','I','N','F','O',0,0,0};
  static const uint8_t zero[16] = {0};
  const uint8_t *bytes = file, *directory = NULL;
  PopsIopImage info = {0};
  size_t offset, data_offset = 0, ext_offset = 0;
  uint32_t count;
  if (!bytes || !out || size < 64)
    return POPS_FILE_INVALID;
  if (size > POPS_PAK_MAX_SIZE)
    return POPS_FILE_RANGE;
  /* RESET's padded extent locates its own directory, as ROMDRV/UDNL expect.
   * Bound the scan to 32 KiB, the ROMDRV reboot-image discovery window. */
  for (offset = 0; offset <= size - 48 && offset < 0x8000; offset += 16) {
    uint32_t reset_size = read32(bytes + offset + 12);
    if (!memcmp(bytes + offset, reset, 10) && reset_size <= offset &&
        offset - reset_size < 16 && !memcmp(bytes + offset + 16, romdir, 10) &&
        !memcmp(bytes + offset + 32, extinfo, 10)) {
      directory = bytes + offset;
      break;
    }
  }
  if (!directory)
    return POPS_FILE_INVALID;
  info.directory_offset = (uint32_t)offset;
  info.directory_size = read32(directory + 28);
  info.extinfo_size = read32(directory + 44);
  if (info.directory_size < 64 || (info.directory_size & 15) ||
      info.directory_size > size - offset)
    return POPS_FILE_INVALID;
  count = info.directory_size / 16;
  if (count > 512)
    return POPS_FILE_RANGE;
  if (memcmp(directory + (count - 1) * 16, zero, 16))
    return POPS_FILE_INVALID;
  for (offset = 0; offset < count - 1; ++offset) {
    const uint8_t *entry = directory + offset * 16;
    uint32_t length = read32(entry + 12);
    uint16_t ext = read16(entry + 10);
    size_t previous;
    if (!entry[0] || (ext & 3))
      return POPS_FILE_INVALID;
    for (previous = 0; previous < offset; ++previous)
      if (!memcmp(entry, directory + previous * 16, 10))
        return POPS_FILE_INVALID;
    if (data_offset > size || length > size - data_offset ||
        ext_offset > info.extinfo_size || ext > info.extinfo_size - ext_offset)
      return POPS_FILE_RANGE;
    data_offset += ((size_t)length + 15) & ~(size_t)15;
    ext_offset += ext;
  }
  if (ext_offset != info.extinfo_size)
    return POPS_FILE_INVALID;
  info.files = (uint16_t)(count - 1);
  *out = info;
  return POPS_FILE_OK;
}
