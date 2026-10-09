#ifndef LAUNCHER_LAUNCH_ARGS_H
#define LAUNCHER_LAUNCH_ARGS_H

#include <stddef.h>

/* Validate argv and remove leading copies of the launcher's own path.
 * Preserve argv[0], especially its HDD partition identity. Returns -1 for
 * malformed input; explicit targets and all following arguments stay intact. */
int launcher_normalize_args(int argc, char **argv);

/* BDMA storage backend modes recognized from bdma_mode.txt marker or driver presence */
typedef enum {
  POPS_BDMA_NONE = 0,
  POPS_BDMA_USB,
  POPS_BDMA_ATA,
  POPS_BDMA_MX4SIO,
  POPS_BDMA_MMCE,
  POPS_BDMA_GENERIC
} PopsBdmaMode;

/* Parses BDMA mode string (e.g. "ATA", "EXFAT", "MX4SIO", "MMCE", "USB", "FAT32") */
PopsBdmaMode pops_parse_bdma_mode(const char *str);

/* Sets optional root directory override for BDMA detection (used in tests) */
void pops_set_bdma_test_root(const char *root);

/* Checks if BDMA is present in memory card directories (mc0:/POPSTARTER/, mc1:/POPSTARTER/, etc.) */
PopsBdmaMode pops_detect_bdma_mode(void);

/* Checks if path or title filename contains the XX. prefix */
int pops_is_xx_prefix(const char *path);

/* Global tracker for active XX. launch context */
void pops_set_active_xx_launch(int active);
int pops_get_active_xx_launch(void);

/* Resolves candidate VCD target paths from launcher binary name or explicit game argument.
 * Without an explicit prefix (XX./SB.) and without a CNF, defaults to POPS APA (hdd0:__.POPS:pfs:/).
 * With XX. prefix, checks if BDMA is present and routes to the active BDM storage backend.
 * Populates candidates array with null-terminated path strings.
 * Returns number of candidates generated. */
int pops_resolve_candidate_targets(const char *launcher_path, const char *arg,
                                   char candidates[][512], int max_candidates);

/* Explicit BDMA mode variant for testing and customized dispatch */
int pops_resolve_candidate_targets_bdma(const char *launcher_path, const char *arg,
                                        char candidates[][512], int max_candidates,
                                        PopsBdmaMode bdma_mode);

#endif
