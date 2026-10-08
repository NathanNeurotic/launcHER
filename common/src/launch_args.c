#include "launch_args.h"
#include <string.h>

static int path_equal(const char *a, const char *b) {
  while (*a && *b) {
    char left = *a == '\\' ? '/' : *a;
    char right = *b == '\\' ? '/' : *b;
    ++a;
    ++b;
    if (left != right) return 0;
  }
  return !*a && !*b;
}

static const char *pfs_path(const char *path, size_t *unit) {
  const char *p;
  if (strncmp(path, "pfs", 3)) return NULL;
  p = path + 3;
  *unit = 0;
  while (*p >= '0' && *p <= '9') {
    /* Keep the exact mount token when both paths explicitly name one. */
    ++*unit;
    ++p;
  }
  return *p == ':' ? p + 1 : NULL;
}

static int self_path(const char *self, const char *candidate) {
  const char *suffix, *left, *right;
  size_t self_unit, other_unit;
  if (path_equal(self, candidate)) return 1;
  /* Only a partition-qualified self path establishes identity for a bare
   * PFS alias. Never infer an HDD partition from pfsN or a matching basename. */
  if (strncmp(self, "hdd", 3)) return 0;
  suffix = strchr(self, ':');
  if (!suffix || !(suffix = strchr(suffix + 1, ':'))) return 0;
  ++suffix;
  left = pfs_path(suffix, &self_unit);
  right = pfs_path(candidate, &other_unit);
  if (!left || !right) return 0;
  if (self_unit && other_unit &&
      (self_unit != other_unit || strncmp(suffix + 3, candidate + 3, self_unit)))
    return 0;
  return path_equal(left, right);
}

int launcher_normalize_args(int argc, char **argv) {
  int i, remove = 0;
  if (argc < 1 || !argv || !argv[0] || !argv[0][0]) return -1;
  for (i = 1; i < argc; ++i)
    if (!argv[i]) return -1;
  while (remove + 1 < argc && self_path(argv[0], argv[remove + 1])) ++remove;
  for (i = 1; i < argc - remove; ++i) argv[i] = argv[i + remove];
  return argc - remove;
}
