/* Model absent PS2 memory-card roots on a host where ':' is not a valid
 * filename character. All other file operations use the host C library. */
#include <stdio.h>
#include <errno.h>
#include <string.h>
#undef fopen
extern FILE *fopen(const char *path, const char *mode);
FILE *pops_test_fopen(const char *path, const char *mode) {
  if (!strncmp(path, "mc0:", 4) || !strncmp(path, "mc1:", 4)) {
    errno = ENOENT;
    return NULL;
  }
  return fopen(path, mode);
}
