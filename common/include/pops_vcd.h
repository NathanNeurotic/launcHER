#ifndef POPS_VCD_H
#define POPS_VCD_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define POPS_VCD_RAW_SECTOR_SIZE  2352
#define POPS_VCD_ISO_SECTOR_SIZE  2048
#define POPS_VCD_SERIAL_MAX       32

typedef struct {
  uint32_t sector_size;
  uint32_t data_offset;
  uint32_t pvd_lba;
  uint32_t root_lba;
  uint32_t root_size;
  char raw_serial[POPS_VCD_SERIAL_MAX];
  char normalized_serial[POPS_VCD_SERIAL_MAX];
} PopsVcdInfo;

/* Normalize a raw PS1 serial (e.g. "SLUS_008.70;1" or "SLUS_008.70" -> "SLUS-00870") */
int pops_vcd_normalize_serial(const char *raw, char *normalized, size_t norm_size);

/* Inspect a VCD stream via read and seek callbacks (allocation-free, works on host and PS2) */
typedef int (*PopsVcdReadFn)(void *user, void *buf, size_t count);
typedef int64_t (*PopsVcdSeekFn)(void *user, int64_t offset, int whence);

int pops_vcd_inspect_stream(void *user, PopsVcdReadFn read_fn, PopsVcdSeekFn seek_fn,
                            PopsVcdInfo *info);

/* Inspect a VCD file descriptor */
int pops_vcd_inspect_fd(int fd, PopsVcdInfo *info);

/* Inspect a VCD file by path */
int pops_vcd_inspect_path(const char *path, PopsVcdInfo *info);

#ifdef __cplusplus
}
#endif

#endif /* POPS_VCD_H */
