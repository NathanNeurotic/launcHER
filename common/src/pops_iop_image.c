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

/* The ROMDIR validator above establishes that every padded data extent fits
 * in the image, that names do not repeat and that the final entry terminates.
 * Use exactly that validated layout to locate an individual module by its
 * 10-byte ROMDIR name, without searching arbitrary binary substrings. */
int pops_iop_image_find_module(const void *file, size_t size, const char *name,
                               size_t *module_offset, size_t *module_size) {
  PopsIopImage info;
  uint8_t query[10] = {0};
  const uint8_t *directory;
  size_t data_offset = 0;
  size_t length;
  int status;
  if (!file || !name || !module_offset || !module_size)
    return POPS_FILE_INVALID;
  length = strlen(name);
  if (!length || length > sizeof(query))
    return POPS_FILE_INVALID;
  memcpy(query, name, length);
  status = pops_iop_image_inspect(file, size, &info);
  if (status)
    return status;
  directory = (const uint8_t *)file + info.directory_offset;
  for (unsigned i = 0; i < info.files; ++i) {
    const uint8_t *entry = directory + i * 16;
    size_t entry_size = read32(entry + 12);
    if (!memcmp(entry, query, sizeof(query))) {
      if (!entry_size)
        return POPS_FILE_UNSUPPORTED;
      *module_offset = data_offset;
      *module_size = entry_size;
      return POPS_FILE_OK;
    }
    data_offset += (entry_size + 15) & ~(size_t)15;
  }
  return POPS_FILE_UNSUPPORTED;
}

/* For a known IOPRP, collect bounded string-only evidence for the
 * IOPCD/ioman hypothesis. These flags cannot prove runtime import binding:
 * a dead string or an unpacked ELF's metadata may contain the same token. */
static int module_has_literal(const uint8_t *bytes, size_t size,
                              const char *literal) {
  size_t length = strlen(literal);
  if (length + 1 > size)
    return 0;
  for (size_t i = 0; i <= size - length - 1; ++i) {
    if (!memcmp(bytes + i, literal, length) &&
        bytes[i + length] == 0 &&
        (i == 0 || bytes[i - 1] == 0))
      return 1;
  }
  return 0;
}

static int module_has_path(const uint8_t *bytes, size_t size,
                           const char *literal) {
  size_t length = strlen(literal);
  if (length > size)
    return 0;
  for (size_t i = 0; i <= size - length; ++i) {
    if (!memcmp(bytes + i, literal, length) &&
        (i == 0 || bytes[i - 1] == 0))
      return 1;
  }
  return 0;
}

int pops_iop_image_probe_io_strings(const void *file, size_t size,
                                    const char *module, uint32_t *flags) {
  size_t offset = 0, module_size = 0;
  uint32_t detected = 0;
  int status;
  if (!file || !module || !flags)
    return POPS_FILE_INVALID;
  status = pops_iop_image_find_module(file, size, module,
                                      &offset, &module_size);
  if (status)
    return status;
  if (offset > size || module_size > size - offset)
    return POPS_FILE_RANGE;
  const uint8_t *bytes = (const uint8_t *)file + offset;
  if (module_has_literal(bytes, module_size, "ioman"))
    detected |= POPS_IOSTRING_IOMAN;
  if (module_has_literal(bytes, module_size, "iomanX") ||
      module_has_literal(bytes, module_size, "iomanx"))
    detected |= POPS_IOSTRING_IOMANX;
  if (module_has_path(bytes, module_size, "pfs0:") ||
      module_has_path(bytes, module_size, "pfs1:") ||
      module_has_path(bytes, module_size, "pfs:"))
    detected |= POPS_IOSTRING_PFS;
  if (module_has_path(bytes, module_size, "pops0:") ||
      module_has_path(bytes, module_size, "pops:"))
    detected |= POPS_IOSTRING_POPS;
  *flags = detected;
  return POPS_FILE_OK;
}

/* ps2sdk iop/kernel/include/irx.h defines the packed IRX import table:
 * magic (0x41e00000), next (4), version (2), mode (2), name[8].
 * Report only a full header inside the selected ROMDIR module's real
 * payload, never a matching name from another module or image padding.
 * A present table is stronger evidence than an ASCII string but does not
 * show which jump stub Sony's IOPCD actually executes. */
int pops_iop_image_probe_io_imports(const void *file, size_t size,
                                    const char *module, uint32_t *imports) {
  static const uint8_t legacy[8] = {'i','o','m','a','n',0,0,0};
  static const uint8_t extended[8] = {'i','o','m','a','n','x',0,0};
  static const uint8_t extended_caps[8] = {'i','o','m','a','n','X',0,0};
  size_t offset = 0, module_size = 0;
  uint32_t mask = 0;
  int status;
  if (!file || !module || !imports)
    return POPS_FILE_INVALID;
  status = pops_iop_image_find_module(file, size, module,
                                      &offset, &module_size);
  if (status)
    return status;
  if (offset > size || module_size > size - offset)
    return POPS_FILE_RANGE;
  const uint8_t *bytes = (const uint8_t *)file + offset;
  for (size_t i = 0; module_size >= 20 && i <= module_size - 20; i += 4) {
    if (read32(bytes + i) != UINT32_C(0x41e00000))
      continue;
    const uint8_t *name = bytes + i + 12;
    if (!memcmp(name, legacy, sizeof(legacy)))
      mask |= POPS_IOIMPORT_IOMAN;
    if (!memcmp(name, extended, sizeof(extended)) ||
        !memcmp(name, extended_caps, sizeof(extended_caps)))
      mask |= POPS_IOIMPORT_IOMANX;
  }
  *imports = mask;
  return POPS_FILE_OK;
}
