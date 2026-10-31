#include "pops_external.h"
#include "LzmaDec.h"
#include <stdlib.h>
#include <string.h>

static void *pak_alloc(ISzAllocPtr self, size_t size) {
  (void)self;
  return malloc(size);
}

static void pak_free(ISzAllocPtr self, void *address) {
  (void)self;
  free(address);
}

int pops_pak_inspect(const void *file, size_t size, uint32_t *decoded_size) {
  const uint8_t *bytes = file;
  uint32_t length;
  if (!bytes || !decoded_size || size < 8)
    return POPS_FILE_INVALID;
  if (size > POPS_PAK_MAX_SIZE)
    return POPS_FILE_RANGE;
  length = (uint32_t)bytes[0] | ((uint32_t)bytes[1] << 8) |
           ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 24);
  if (!length || length > POPS_PAK_MAX_SIZE)
    return POPS_FILE_RANGE;
  *decoded_size = length;
  return POPS_FILE_OK;
}

int pops_pak_decode(const void *file, size_t size, void *output, size_t capacity,
                    size_t *decoded_size) {
  /* lc=3, lp=0, pb=2, 8 MiB dictionary: original POPStarter decoder settings. */
  static const Byte properties[5] = {0x5d, 0, 0, 0x80, 0};
  static const ISzAlloc allocator = {pak_alloc, pak_free};
  const uint8_t *bytes = file;
  uintptr_t source = (uintptr_t)file, dest = (uintptr_t)output;
  uint32_t length;
  SizeT input_size, output_size;
  Byte *stream;
  ELzmaStatus finish;
  SRes result;
  int status = pops_pak_inspect(file, size, &length);
  if (status)
    return status;
  if (!output || !decoded_size)
    return POPS_FILE_INVALID;
  if (capacity < length ||
      (source <= dest ? dest - source < size : source - dest < length))
    return POPS_FILE_RANGE;
  input_size = size - 3;
  /* SDK dummy decoding needs up to 20 lookahead bytes. Only a single
   * zero flush byte may actually be consumed, and only with zero range code.
   * The measured IOX package ends in exactly that condition. */
  stream = malloc(input_size + 20);
  if (!stream)
    return POPS_FILE_NOMEM;
  /* PAK stores the initial range code as a little-endian word. LZMA consumes
   * it in big-endian order, after its mandatory zero initialization byte. */
  stream[0] = 0;
  stream[1] = bytes[7];
  stream[2] = bytes[6];
  stream[3] = bytes[5];
  stream[4] = bytes[4];
  memcpy(stream + 5, bytes + 8, size - 8);
  memset(stream + input_size, 0, 20);
  input_size += 20;
  output_size = length;
  result = LzmaDecode(output, &output_size, stream, &input_size, properties,
                      sizeof(properties), LZMA_FINISH_ANY, &finish, &allocator);
  free(stream);
  if (result == SZ_ERROR_MEM)
    return POPS_FILE_NOMEM;
  if (result != SZ_OK || output_size != length ||
      finish == LZMA_STATUS_NEEDS_MORE_INPUT ||
      (input_size > size - 3 &&
       (input_size != size - 2 || finish != LZMA_STATUS_MAYBE_FINISHED_WITHOUT_MARK)))
    return POPS_FILE_INVALID;
  *decoded_size = output_size;
  return POPS_FILE_OK;
}
