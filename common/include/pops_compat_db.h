#ifndef POPS_COMPAT_DB_H
#define POPS_COMPAT_DB_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
  const char *serial;
  const char *title;
  uint8_t default_modes; /* Bitmask of compatibility modes (1 << (mode - 1)) */
  uint8_t has_libcrypt;  /* 1 if title requires LibCrypt subchannel bypass */
  uint16_t libcrypt_key; /* 16-bit LibCrypt magic word key (0 if none) */
  uint32_t patch_offset; /* Target POPS address for custom patch (0 if none) */
  uint32_t patch_val;    /* 32-bit patch value */
} PopsCompatEntry;

/* Looks up title entry by serial (matches normalized "ABCD-12345" or raw "ABCD_123.45") */
const PopsCompatEntry *pops_compat_db_lookup(const char *serial);

/* Returns total number of registered entries in database */
size_t pops_compat_db_count(void);

/* Returns entry at index (0 <= index < count) */
const PopsCompatEntry *pops_compat_db_get(size_t index);

#ifdef __cplusplus
}
#endif

#endif /* POPS_COMPAT_DB_H */
