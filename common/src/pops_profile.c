#include "pops_external.h"
#include <string.h>

static uint32_t rotate(uint32_t word, unsigned count) {
  return (word >> count) | (word << (32 - count));
}

static void sha_block(uint32_t state[8], const uint8_t block[64]) {
  static const uint32_t constants[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
  };
  uint32_t schedule[64], work[8];
  unsigned i;
  for (i = 0; i < 16; ++i) {
    const uint8_t *p = block + i * 4;
    schedule[i] = ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
                  ((uint32_t)p[2] << 8) | (uint32_t)p[3];
  }
  for (; i < 64; ++i) {
    uint32_t x = schedule[i - 15], y = schedule[i - 2];
    schedule[i] = schedule[i - 16] + schedule[i - 7] +
      (rotate(x, 7) ^ rotate(x, 18) ^ (x >> 3)) +
      (rotate(y, 17) ^ rotate(y, 19) ^ (y >> 10));
  }
  memcpy(work, state, sizeof(work));
  for (i = 0; i < 64; ++i) {
    uint32_t a = work[0], b = work[1], c = work[2];
    uint32_t e = work[4], f = work[5], g = work[6];
    uint32_t first = work[7] + (rotate(e, 6) ^ rotate(e, 11) ^ rotate(e, 25)) +
                     ((e & f) ^ (~e & g)) + constants[i] + schedule[i];
    uint32_t second = (rotate(a, 2) ^ rotate(a, 13) ^ rotate(a, 22)) +
                      ((a & b) ^ (a & c) ^ (b & c));
    memmove(work + 1, work, 7 * sizeof(uint32_t));
    work[4] += first;
    work[0] = first + second;
  }
  for (i = 0; i < 8; ++i)
    state[i] += work[i];
}

int pops_image_sha256(const void *file, size_t size, uint8_t digest[32]) {
  const uint8_t *bytes = file;
  uint32_t state[8] = {0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
                       0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
  uint8_t tail[64] = {0};
  uint64_t bits = (uint64_t)size * 8;
  size_t remaining = size;
  unsigned i;
  if (!digest || (!file && size))
    return POPS_FILE_INVALID;
  /* These hashes identify bounded dependency images, not arbitrary streams. */
  if (size > POPS_PAK_MAX_SIZE)
    return POPS_FILE_RANGE;
  while (remaining >= 64) {
    sha_block(state, bytes);
    bytes += 64;
    remaining -= 64;
  }
  if (remaining)
    memcpy(tail, bytes, remaining);
  tail[remaining] = 0x80;
  if (remaining >= 56) {
    sha_block(state, tail);
    memset(tail, 0, sizeof(tail));
  }
  for (i = 0; i < 8; ++i)
    tail[63 - i] = (uint8_t)(bits >> (i * 8));
  sha_block(state, tail);
  for (i = 0; i < 32; ++i)
    digest[i] = (uint8_t)(state[i / 4] >> (24 - (i % 4) * 8));
  return POPS_FILE_OK;
}

static int matches(const void *file, size_t size, const char *expected) {
  static const char digits[] = "0123456789abcdef";
  uint8_t digest[32];
  unsigned i;
  if (pops_image_sha256(file, size, digest))
    return 0;
  for (i = 0; i < 32; ++i)
    if (digits[digest[i] >> 4] != expected[i * 2] ||
        digits[digest[i] & 15] != expected[i * 2 + 1])
      return 0;
  return 1;
}

#define CORE_SIZE UINT32_C(0x00302e60)
static const char core_hash[] =
  "38ecd425324a1244e90ae68b927496b9af511fd0ed89761199fb6eb699e71ab0";
static const char elf_hash[] =
  "59df3389c4df88a572daa720b05507c52c34eddfa0031a6fbeec55e0c2d0fcb1";

static int iop_profile(const void *file, size_t size, int loose,
                        PopsIopVariant *variant) {
  PopsIopImage info;
  int status = pops_iop_image_inspect(file, size, &info);
  if (status)
    return status;
  if (loose && size == 265233 && matches(file, size,
      "3338b238d84d7d586b716677e3a1c03b2088b882ecfa17f91fc33798931ca3ba")) {
    *variant = POPS_IOP_LOOSE_252;
  } else if (!loose && size == 265233 && matches(file, size,
      "efe68299cc4f5ab84343c77c1cdc80d87421b6c8074060e9440e2fc942e0dc09")) {
    *variant = POPS_IOP_PACKED_252;
  } else if (!loose && size == 245081 && matches(file, size,
      "38d3c1a87d874ed964bbd631a6ea2975b35ee52ecbdba839ee6b2ee2f5993c23")) {
    *variant = POPS_IOP_PACKED_2305A;
  } else {
    return POPS_FILE_UNSUPPORTED;
  }
  return POPS_FILE_OK;
}

static PopsBootPlan reference_plan(void) {
  PopsBootPlan plan = {0};
  plan.entry = 0x00200008;
  plan.core_address = 0x00200000;
  plan.core_size = CORE_SIZE;
  plan.bss_address = 0x00502e60;
  plan.bss_size = 0x00362ae0;
  plan.scratchpad_size = 0x3c30;
  return plan;
}

int pops_boot_plan_pak(const void *decoded, size_t size, PopsBootPlan *out) {
  const uint8_t *bytes = decoded;
  PopsBootPlan plan = reference_plan();
  int status;
  if (!bytes || !out)
    return POPS_FILE_INVALID;
  if (size != CORE_SIZE + 265233 && size != CORE_SIZE + 245081)
    return POPS_FILE_UNSUPPORTED;
  if (!matches(bytes, CORE_SIZE, core_hash))
    return POPS_FILE_GUARD;
  status = iop_profile(bytes + CORE_SIZE, size - CORE_SIZE, 0, &plan.iop_variant);
  if (status)
    return status;
  plan.source = POPS_SOURCE_DECODED_PAK;
  plan.iop_offset = CORE_SIZE;
  plan.iop_size = (uint32_t)(size - CORE_SIZE);
  *out = plan;
  return POPS_FILE_OK;
}

int pops_boot_plan_elf(const void *elf, size_t elf_size, const void *iop,
                       size_t iop_size, PopsBootPlan *out) {
  PopsElfInfo info;
  PopsBootPlan plan = reference_plan();
  int status;
  if (!out)
    return POPS_FILE_INVALID;
  status = pops_elf_inspect(elf, elf_size, &info);
  if (status)
    return status;
  if (elf_size != 3166988 || !matches(elf, elf_size, elf_hash))
    return POPS_FILE_GUARD;
  status = iop_profile(iop, iop_size, 1, &plan.iop_variant);
  if (status)
    return status;
  plan.source = POPS_SOURCE_LOOSE_ELF;
  plan.iop_size = (uint32_t)iop_size;
  *out = plan;
  return POPS_FILE_OK;
}
