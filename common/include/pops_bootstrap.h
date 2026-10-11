#ifndef LAUNCHER_POPS_BOOTSTRAP_H
#define LAUNCHER_POPS_BOOTSTRAP_H

#include <stddef.h>
#include <stdint.h>
#include "pops_external.h"

/* Fixed staging memory map on PS2 EE (32 MiB total main RAM).
 * Staging sits in high memory (>= 16 MiB), completely disjoint from POPS load/BSS
 * (0x00200000 - 0x00865940) and launcHER (0x00100000 - 0x00200000). */
#define POPS_STAGING_BASE        UINT32_C(0x01000000) /* 16 MiB */
#define POPS_STAGING_CAPACITY    UINT32_C(0x00800000) /* 8 MiB max staging buffer */

#define POPS_RAM_BASE            UINT32_C(0x00100000) /* 1 MiB */
#define POPS_CORE_ADDR           UINT32_C(0x00200000) /* 2 MiB */
#define POPS_ENTRY_ADDR          UINT32_C(0x00200008)
#define POPS_BSS_ADDR            UINT32_C(0x00502e60)
#define POPS_BSS_SIZE            UINT32_C(0x00362ae0) /* Ends at 0x00865940 */
#define POPS_SPAD_ADDR           UINT32_C(0x70000000)
#define POPS_SPAD_SIZE           UINT32_C(0x00003c30)

/* Low-memory trampoline in BIOS unused RAM (below 1 MiB). */
#define POPS_TRAMPOLINE_ADDR     UINT32_C(0x00084000)
#define POPS_TRAMPOLINE_ARGS     UINT32_C(0x00084200)

/* Proxy argument limit matching popfs. */
#define POPS_PROXY_ARGS_MAX      (6 * 256)

typedef struct {
  uint32_t entry;           /* Offset 0: Entrypoint (0x00200008) */
  uint32_t bss_address;     /* Offset 4: BSS start (0x00502e60) */
  uint32_t bss_size;        /* Offset 8: BSS size (0x00362ae0) */
  uint32_t scratchpad_size; /* Offset 12: Scratchpad size (0x00003c30) */
  uint32_t staging_core;    /* Offset 16: Staging buffer core address */
  uint32_t core_address;    /* Offset 20: Final core load address (0x00200000) */
  uint32_t core_size;       /* Offset 24: Core size (0x00302e60) */
  int32_t  argc;            /* Offset 28: argc (1) */
  uint32_t argv[4];         /* Offset 32..47: argv pointers (argv[0], etc.) */
  char     arg_strings[128];/* Offset 48..: Null-terminated argument strings */
} PopsTrampolineArgs;

/* Format packed proxy arguments for popfs: "popfs\0disc0\0card0\0card1\0[disc1..]\0".
 * Returns length of formatted buffer in bytes, or < 0 on error. */
int pops_format_proxy_args(char *buffer, size_t capacity,
                           const char *disc0, const char *card0, const char *card1,
                           const char *disc1, const char *disc2, const char *disc3);

/* Initialize PopsTrampolineArgs with validated addresses and arguments.
 * Ensures all pointers stay within low memory / bram. Returns 0 on success. */
int pops_trampoline_args_init(PopsTrampolineArgs *out, const PopsBootPlan *plan,
                              uint32_t staging_core, const char *game_arg);

/* Verify that staging and execution buffers are completely disjoint and valid. */
int pops_bootstrap_verify_layout(uint32_t staging_base, size_t staging_size,
                                 const PopsBootPlan *plan);

#endif
