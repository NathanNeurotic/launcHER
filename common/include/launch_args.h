#ifndef LAUNCHER_LAUNCH_ARGS_H
#define LAUNCHER_LAUNCH_ARGS_H

/* Validate argv and remove leading copies of the launcher's own path.
 * Preserve argv[0], especially its HDD partition identity. Returns -1 for
 * malformed input; explicit targets and all following arguments stay intact. */
int launcher_normalize_args(int argc, char **argv);

#endif
