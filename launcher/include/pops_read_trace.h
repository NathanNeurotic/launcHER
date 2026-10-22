#ifndef LAUNCHER_POPS_READ_TRACE_H
#define LAUNCHER_POPS_READ_TRACE_H

#include <stddef.h>

#ifdef LAUNCHER_BOOT_TRACE
/* Read-only diagnostic comparison after a failed POSIX dependency read.
 * Caller discards buffer even on success. No boot authorization or fallback.
 * Requires initialized fileXio in blocking mode; does not load/reset modules. */
int pops_read_filexio_trace(const char *path, void *buffer, size_t capacity);
#endif

#endif
