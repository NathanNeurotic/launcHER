#ifndef LAUNCHER_LAUNCH_ARGS_H
#define LAUNCHER_LAUNCH_ARGS_H

#include <stddef.h>

/* Validate argv and remove leading copies of the launcher's own path.
 * Preserve argv[0], especially its HDD partition identity. Returns -1 for
 * malformed input; explicit targets and all following arguments stay intact. */
int launcher_normalize_args(int argc, char **argv);

/* Resolves candidate VCD target paths from launcher binary name or explicit game argument.
 * Without an explicit prefix (XX./SB.) and without a CNF, defaults to POPS APA (hdd0:__.POPS:pfs:/).
 * Populates candidates array with null-terminated path strings.
 * Returns number of candidates generated. */
int pops_resolve_candidate_targets(const char *launcher_path, const char *arg,
                                   char candidates[][512], int max_candidates);

#endif

