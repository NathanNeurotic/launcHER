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

#define PREFIX_NONE 0
#define PREFIX_XX   1
#define PREFIX_SB   2

static void extract_base_name(const char *path, char *base, size_t base_size, int *prefix_type) {
  const char *name, *bname, *dot;
  size_t len;
  if (base && base_size > 0) base[0] = '\0';
  if (prefix_type) *prefix_type = PREFIX_NONE;
  if (!path || !path[0]) return;

  name = strrchr(path, '/');
  bname = strrchr(path, '\\');
  if (bname && (!name || bname > name))
    name = bname;
  if (!name)
    name = strrchr(path, ':');
  name = name ? name + 1 : path;

  if ((name[0] == 'X' || name[0] == 'x') && (name[1] == 'X' || name[1] == 'x') && name[2] == '.') {
    if (prefix_type) *prefix_type = PREFIX_XX;
    name += 3;
  } else if ((name[0] == 'S' || name[0] == 's') && (name[1] == 'B' || name[1] == 'b') && name[2] == '.') {
    if (prefix_type) *prefix_type = PREFIX_SB;
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

PopsBdmaMode pops_parse_bdma_mode(const char *str) {
  if (!str) return POPS_BDMA_NONE;
  while (*str && (*str == ' ' || *str == '\t' || *str == '\r' || *str == '\n'))
    ++str;
  if (!*str || *str == '#' || *str == ';') return POPS_BDMA_NONE;

  char tok[32];
  size_t i = 0;
  while (*str && *str != ' ' && *str != '\t' && *str != '\r' && *str != '\n' &&
         *str != '#' && *str != ';' && i < sizeof(tok) - 1) {
    tok[i++] = *str++;
  }
  tok[i] = '\0';

  if (str_iequal(tok, "ATA") || str_iequal(tok, "ATA0") || str_iequal(tok, "ATA1") ||
      str_iequal(tok, "EXFAT") || str_iequal(tok, "HDD") || str_iequal(tok, "INTERNAL_HDD") ||
      str_iequal(tok, "SATA") || str_iequal(tok, "IDE")) {
    return POPS_BDMA_ATA;
  }
  if (str_iequal(tok, "MX4SIO") || str_iequal(tok, "MX4SIO0") || str_iequal(tok, "MX4SIO1") ||
      str_iequal(tok, "MC2SIO") || str_iequal(tok, "MC2SIO0") || str_iequal(tok, "MC2SIO1")) {
    return POPS_BDMA_MX4SIO;
  }
  if (str_iequal(tok, "MMCE") || str_iequal(tok, "MMCE0") || str_iequal(tok, "MMCE1") ||
      str_iequal(tok, "SD")) {
    return POPS_BDMA_MMCE;
  }
  if (str_iequal(tok, "USB") || str_iequal(tok, "USB0") || str_iequal(tok, "USB1") ||
      str_iequal(tok, "USBEXFAT") || str_iequal(tok, "FAT32") ||
      str_iequal(tok, "MASS") || str_iequal(tok, "MASS0") || str_iequal(tok, "MASS1")) {
    return POPS_BDMA_USB;
  }
  if (str_iequal(tok, "BDMA") || str_iequal(tok, "GENERIC") || str_iequal(tok, "ALL")) {
    return POPS_BDMA_GENERIC;
  }
  return POPS_BDMA_NONE;
}

static char s_bdma_test_root[384] = {0};

void pops_set_bdma_test_root(const char *root) {
  if (root && root[0]) {
    strncpy(s_bdma_test_root, root, sizeof(s_bdma_test_root) - 1);
    s_bdma_test_root[sizeof(s_bdma_test_root) - 1] = '\0';
  } else {
    s_bdma_test_root[0] = '\0';
  }
}

PopsBdmaMode pops_detect_bdma_mode(void) {
  char path[1024];
  char line[64];
  FILE *f;
  size_t m, d, drv;

  static const char *marker_files[] = {
    "bdma_mode.txt",
    ".pldr_bdma_mode",
    "bdma_device.txt",
    "bdma.cfg"
  };
  static const char *dirs[] = {
    "mc0:/POPSTARTER/",
    "mc1:/POPSTARTER/",
    "mc0:/POPS/",
    "mc1:/POPS/"
  };

  /* 1. Marker files */
  if (s_bdma_test_root[0]) {
    for (m = 0; m < sizeof(marker_files)/sizeof(marker_files[0]); ++m) {
      snprintf(path, sizeof(path), "%s/POPSTARTER/%s", s_bdma_test_root, marker_files[m]);
      f = fopen(path, "r");
      if (!f) {
        snprintf(path, sizeof(path), "%s/%s", s_bdma_test_root, marker_files[m]);
        f = fopen(path, "r");
      }
      if (f) {
        if (fgets(line, sizeof(line), f)) {
          fclose(f);
          PopsBdmaMode mode = pops_parse_bdma_mode(line);
          if (mode != POPS_BDMA_NONE) return mode;
        } else {
          fclose(f);
        }
      }
    }
  } else {
    for (d = 0; d < sizeof(dirs)/sizeof(dirs[0]); ++d) {
      for (m = 0; m < sizeof(marker_files)/sizeof(marker_files[0]); ++m) {
        snprintf(path, sizeof(path), "%s%s", dirs[d], marker_files[m]);
        f = fopen(path, "r");
        if (f) {
          if (fgets(line, sizeof(line), f)) {
            fclose(f);
            PopsBdmaMode mode = pops_parse_bdma_mode(line);
            if (mode != POPS_BDMA_NONE) return mode;
          } else {
            fclose(f);
          }
        }
      }
    }
  }

  /* 2. Driver presence */
  static const char *driver_files[] = {
    "bdm_assault.irx",
    "BDM.IRX",
    "USBD.IRX",
    "USBHDFSD.IRX"
  };

  if (s_bdma_test_root[0]) {
    for (drv = 0; drv < sizeof(driver_files)/sizeof(driver_files[0]); ++drv) {
      snprintf(path, sizeof(path), "%s/POPSTARTER/%s", s_bdma_test_root, driver_files[drv]);
      f = fopen(path, "r");
      if (!f) {
        snprintf(path, sizeof(path), "%s/%s", s_bdma_test_root, driver_files[drv]);
        f = fopen(path, "r");
      }
      if (f) {
        fclose(f);
        return POPS_BDMA_GENERIC;
      }
    }
  } else {
    for (d = 0; d < sizeof(dirs)/sizeof(dirs[0]); ++d) {
      for (drv = 0; drv < sizeof(driver_files)/sizeof(driver_files[0]); ++drv) {
        snprintf(path, sizeof(path), "%s%s", dirs[d], driver_files[drv]);
        f = fopen(path, "r");
        if (f) {
          fclose(f);
          return POPS_BDMA_GENERIC;
        }
      }
    }
  }

  return POPS_BDMA_NONE;
}

int pops_resolve_candidate_targets_bdma(const char *launcher_path, const char *arg,
                                        char candidates[][512], int max_candidates,
                                        PopsBdmaMode bdma_mode) {
  int count = 0;
  char baseTitle[64] = {0};
  char dirBuf[384] = {0};
  char devPrefix[32] = {0};
  char buf[1024];
  int prefix_type = PREFIX_NONE;
  int launcher_prefix = PREFIX_NONE;

  if (max_candidates <= 0 || !candidates)
    return 0;

  if (launcher_path && launcher_path[0]) {
    extract_parent_dir(launcher_path, dirBuf, sizeof(dirBuf));
    extract_device_prefix(launcher_path, devPrefix, sizeof(devPrefix));
    extract_base_name(launcher_path, NULL, 0, &launcher_prefix);
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

    extract_base_name(arg, baseTitle, sizeof(baseTitle), &prefix_type);
    if (!baseTitle[0])
      return 0;

    if (prefix_type == PREFIX_NONE && launcher_prefix != PREFIX_NONE) {
      prefix_type = launcher_prefix;
    }

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
  } else if (launcher_path && launcher_path[0]) {
    extract_base_name(launcher_path, baseTitle, sizeof(baseTitle), &prefix_type);
    if (!baseTitle[0])
      return 0;
  } else {
    return 0;
  }

  /* Dispatch candidates based on prefix and BDMA mode */
  if (prefix_type == PREFIX_NONE) {
    /* No prefix and no CNF: default to POPS APA partition first */
    snprintf(buf, sizeof(buf), "hdd0:__.POPS:pfs:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    add_candidate(candidates, max_candidates, &count, "hdd0:__.POPS:pfs:/IMAGE.VCD");

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

  if (prefix_type == PREFIX_SB) {
    /* SB. prefix: SMB network share priority */
    snprintf(buf, sizeof(buf), "smb0:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "smb0:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "smb:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);

    if (dirBuf[0]) {
      snprintf(buf, sizeof(buf), "%s/%s.VCD", dirBuf, baseTitle);
      add_candidate(candidates, max_candidates, &count, buf);
    }

    snprintf(buf, sizeof(buf), "mass0:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "hdd0:__.POPS:pfs:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    return count;
  }

  /* prefix_type == PREFIX_XX: BDMA-aware resolution */
  if (bdma_mode == POPS_BDMA_ATA) {
    /* ATA / Internal exFAT HDD backend */
    snprintf(buf, sizeof(buf), "ata:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    add_candidate(candidates, max_candidates, &count, "ata:/POPS/IMAGE.VCD");
    snprintf(buf, sizeof(buf), "ata:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "ata0:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "ata0:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    if (dirBuf[0] && !strncmp(dirBuf, "ata", 3)) {
      snprintf(buf, sizeof(buf), "%s/%s.VCD", dirBuf, baseTitle);
      add_candidate(candidates, max_candidates, &count, buf);
      snprintf(buf, sizeof(buf), "%s/IMAGE.VCD", dirBuf);
      add_candidate(candidates, max_candidates, &count, buf);
    }
  } else if (bdma_mode == POPS_BDMA_MX4SIO) {
    /* MX4SIO / MC2SIO backend */
    snprintf(buf, sizeof(buf), "mx4sio:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    add_candidate(candidates, max_candidates, &count, "mx4sio:/POPS/IMAGE.VCD");
    snprintf(buf, sizeof(buf), "mx4sio:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mx4sio0:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mx4sio0:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    if (dirBuf[0] && !strncmp(dirBuf, "mx4sio", 6)) {
      snprintf(buf, sizeof(buf), "%s/%s.VCD", dirBuf, baseTitle);
      add_candidate(candidates, max_candidates, &count, buf);
      snprintf(buf, sizeof(buf), "%s/IMAGE.VCD", dirBuf);
      add_candidate(candidates, max_candidates, &count, buf);
    }
  } else if (bdma_mode == POPS_BDMA_MMCE) {
    /* MMCE backend */
    snprintf(buf, sizeof(buf), "mmce0:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    add_candidate(candidates, max_candidates, &count, "mmce0:/POPS/IMAGE.VCD");
    snprintf(buf, sizeof(buf), "mmce0:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mmce1:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    add_candidate(candidates, max_candidates, &count, "mmce1:/POPS/IMAGE.VCD");
    snprintf(buf, sizeof(buf), "mmce1:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
  } else if (bdma_mode == POPS_BDMA_GENERIC) {
    /* Generic BDMA driver presence: probe USB, ATA, MX4SIO, MMCE */
    snprintf(buf, sizeof(buf), "mass0:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mass0:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "ata:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "ata:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mx4sio:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mx4sio:/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mmce0:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
    snprintf(buf, sizeof(buf), "mmce1:/POPS/%s.VCD", baseTitle);
    add_candidate(candidates, max_candidates, &count, buf);
  }

  /* Adjacent directory and device prefix priorities (standard for USB/local launches) */
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

  /* Standard USB mass storage paths */
  snprintf(buf, sizeof(buf), "mass0:/POPS/%s.VCD", baseTitle);
  add_candidate(candidates, max_candidates, &count, buf);
  snprintf(buf, sizeof(buf), "mass0:/%s.VCD", baseTitle);
  add_candidate(candidates, max_candidates, &count, buf);
  snprintf(buf, sizeof(buf), "mass1:/POPS/%s.VCD", baseTitle);
  add_candidate(candidates, max_candidates, &count, buf);

  /* Memory card and APA fallbacks */
  snprintf(buf, sizeof(buf), "mc0:/POPS/%s.VCD", baseTitle);
  add_candidate(candidates, max_candidates, &count, buf);
  snprintf(buf, sizeof(buf), "mc1:/POPS/%s.VCD", baseTitle);
  add_candidate(candidates, max_candidates, &count, buf);
  snprintf(buf, sizeof(buf), "hdd0:__.POPS:pfs:/%s.VCD", baseTitle);
  add_candidate(candidates, max_candidates, &count, buf);

  return count;
}

int pops_resolve_candidate_targets(const char *launcher_path, const char *arg,
                                   char candidates[][512], int max_candidates) {
  PopsBdmaMode mode = pops_detect_bdma_mode();
  return pops_resolve_candidate_targets_bdma(launcher_path, arg, candidates, max_candidates, mode);
}
