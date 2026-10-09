#include "launch_args.h"
#include <stdio.h>
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

static int str_iequal(const char *a, const char *b) {
  while (*a && *b) {
    char ca = (*a >= 'A' && *a <= 'Z') ? (char)(*a + ('a' - 'A')) : *a;
    char cb = (*b >= 'A' && *b <= 'Z') ? (char)(*b + ('a' - 'A')) : *b;
    if (ca != cb) return 0;
    ++a;
    ++b;
  }
  return !*a && !*b;
}

static void add_candidate(char candidates[][512], int max_candidates, int *count, const char *path) {
  int i;
  size_t len;
  if (!path || !path[0] || *count >= max_candidates) return;
  for (i = 0; i < *count; ++i) {
    if (path_equal(candidates[i], path)) return;
  }
  len = strlen(path);
  if (len >= 512) len = 511;
  memcpy(candidates[*count], path, len);
  candidates[*count][len] = '\0';
  (*count)++;
}

static void extract_base_name(const char *path, char *base, size_t base_size, int *has_prefix) {
  const char *name, *bname, *dot;
  size_t len;
  if (base && base_size > 0) base[0] = '\0';
  if (has_prefix) *has_prefix = 0;
  if (!path || !path[0]) return;

  name = strrchr(path, '/');
  bname = strrchr(path, '\\');
  if (bname && (!name || bname > name))
    name = bname;
  if (!name)
    name = strrchr(path, ':');
  name = name ? name + 1 : path;

  if (((name[0] == 'X' || name[0] == 'x') && (name[1] == 'X' || name[1] == 'x') && name[2] == '.') ||
      ((name[0] == 'S' || name[0] == 's') && (name[1] == 'B' || name[1] == 'b') && name[2] == '.')) {
    if (has_prefix) *has_prefix = 1;
    name += 3;
  }

  dot = strrchr(name, '.');
  len = dot ? (size_t)(dot - name) : strlen(name);
  if (len >= base_size) len = base_size - 1;
  if (base && base_size > 0) {
    memcpy(base, name, len);
    base[len] = '\0';
  }
}

static void extract_parent_dir(const char *path, char *dir, size_t dir_size) {
  const char *sep, *bsep, *colon;
  size_t len;
  if (dir && dir_size > 0) dir[0] = '\0';
  if (!path || !path[0]) return;
  sep = strrchr(path, '/');
  bsep = strrchr(path, '\\');
  if (bsep && (!sep || bsep > sep))
    sep = bsep;
  if (sep) {
    len = (size_t)(sep - path);
    if (len >= dir_size) len = dir_size - 1;
    memcpy(dir, path, len);
    dir[len] = '\0';
  } else {
    colon = strrchr(path, ':');
    if (colon) {
      len = (size_t)(colon - path) + 1;
      if (len >= dir_size) len = dir_size - 1;
      memcpy(dir, path, len);
      dir[len] = '\0';
    }
  }
}

static void extract_device_prefix(const char *path, char *dev, size_t dev_size) {
  const char *colon;
  size_t len;
  if (dev && dev_size > 0) dev[0] = '\0';
  if (!path || !path[0]) return;
  colon = strchr(path, ':');
  if (colon) {
    len = (size_t)(colon - path) + 1;
    if (len >= dev_size) len = dev_size - 1;
    memcpy(dev, path, len);
    dev[len] = '\0';
  }
}

int pops_resolve_candidate_targets(const char *launcher_path, const char *arg,
                                   char candidates[][512], int max_candidates) {
  int count = 0;
  char baseTitle[64] = {0};
  char dirBuf[384] = {0};
  char devPrefix[32] = {0};
  char buf[1024];
  int hasPrefix = 0;

  if (max_candidates <= 0 || !candidates)
    return 0;

  if (launcher_path && launcher_path[0]) {
    extract_parent_dir(launcher_path, dirBuf, sizeof(dirBuf));
    extract_device_prefix(launcher_path, devPrefix, sizeof(devPrefix));
  }

  if (arg && arg[0]) {
    const char *colon = strchr(arg, ':');
    const char *slash = strchr(arg, '/');
    const char *bslash = strchr(arg, '\\');
    const char *dot;
    if (bslash && (!slash || bslash < slash)) slash = bslash;

    if (colon && (!slash || colon < slash)) {
      dot = strrchr(arg, '.');
      if (dot && (str_iequal(dot, ".vcd") || str_iequal(dot, ".elf"))) {
        add_candidate(candidates, max_candidates, &count, arg);
      } else {
        snprintf(buf, sizeof(buf), "%.500s.VCD", arg);
        add_candidate(candidates, max_candidates, &count, buf);
        add_candidate(candidates, max_candidates, &count, arg);
      }
      return count;
    }

    extract_base_name(arg, baseTitle, sizeof(baseTitle), &hasPrefix);
    if (!baseTitle[0])
      return 0;

    if (slash) {
      if (devPrefix[0]) {
        snprintf(buf, sizeof(buf), "%s/%.400s", devPrefix, arg);
        add_candidate(candidates, max_candidates, &count, buf);
      }
      if (dirBuf[0]) {
        snprintf(buf, sizeof(buf), "%s/%.400s", dirBuf, arg);
        add_candidate(candidates, max_candidates, &count, buf);
      }
    }

    /* Without prefix and without CNF: default to POPS APA first */
    if (!hasPrefix) {
      snprintf(buf, sizeof(buf), "hdd0:__.POPS:pfs:/%s.VCD", baseTitle);
      add_candidate(candidates, max_candidates, &count, buf);
      add_candidate(candidates, max_candidates, &count, "hdd0:__.POPS:pfs:/IMAGE.VCD");
    }

    if (dirBuf[0]) {
      snprintf(buf, sizeof(buf), "%s/%s.VCD", dirBuf, baseTitle);
      add_candidate(candidates, max_candidates, &count, buf);
      snprintf(buf, sizeof(buf), "%s/IMAGE.VCD", dirBuf);
      add_candidate(candidates, max_candidates, &count, buf);
    }

    if (devPrefix[0]) {
      snprintf(buf, sizeof(buf), "%s/POPS/%s.VCD", devPrefix, baseTitle);
      add_candidate(candidates, max_candidates, &count, buf);
      snprintf(buf, sizeof(buf), "%s/POPS/IMAGE.VCD", devPrefix);
      add_candidate(candidates, max_candidates, &count, buf);
      snprintf(buf, sizeof(buf), "%s/%s.VCD", devPrefix, baseTitle);
      add_candidate(candidates, max_candidates, &count, buf);
    }

    snprintf(buf, sizeof(buf), "mass0:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mass0:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mc0:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mc1:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "hdd0:__.POPS:pfs:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);

    return count;
  }

  if (launcher_path && launcher_path[0]) {
    extract_base_name(launcher_path, baseTitle, sizeof(baseTitle), &hasPrefix);
    if (!baseTitle[0])
      return 0;

    /* Without prefix and without CNF: default to POPS APA first */
    if (!hasPrefix) {
      snprintf(buf, sizeof(buf), "hdd0:__.POPS:pfs:/%s.VCD", baseTitle);
      add_candidate(candidates, max_candidates, &count, buf);
      add_candidate(candidates, max_candidates, &count, "hdd0:__.POPS:pfs:/IMAGE.VCD");
    }

    if (dirBuf[0]) {
      snprintf(buf, sizeof(buf), "%s/%s.VCD", dirBuf, baseTitle);
      add_candidate(candidates, max_candidates, &count, buf);
      snprintf(buf, sizeof(buf), "%s/IMAGE.VCD", dirBuf);
      add_candidate(candidates, max_candidates, &count, buf);
    }

    if (devPrefix[0]) {
      snprintf(buf, sizeof(buf), "%s/POPS/%s.VCD", devPrefix, baseTitle);
      add_candidate(candidates, max_candidates, &count, buf);
      snprintf(buf, sizeof(buf), "%s/POPS/IMAGE.VCD", devPrefix);
      add_candidate(candidates, max_candidates, &count, buf);
      snprintf(buf, sizeof(buf), "%s/%s.VCD", devPrefix, baseTitle);
      add_candidate(candidates, max_candidates, &count, buf);
    }

    snprintf(buf, sizeof(buf), "mass0:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mass0:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mc0:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mc1:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "hdd0:__.POPS:pfs:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);

    return count;
  }

  return 0;
}

