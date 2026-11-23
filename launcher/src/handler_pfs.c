#include "common.h"
#include "dprintf.h"
#include "init.h"
#include "loader.h"
#include <ps2sdkapi.h>
#include <stdio.h>
#include <string.h>

// Loads ELF from APA-formatted HDD
int handlePFS(int argc, char *argv[]) {
  if ((argv[0] == 0) || (strlen(argv[0]) < 4)) {
    msg("PFS: invalid argument\n");
    return -EINVAL;
  }

  char mountPart[256];
  const char *subPath = NULL;
  if (parseAPAPath(argv[0], mountPart, sizeof(mountPart), &subPath) != 0 || mountPart[0] == '\0') {
    msg("PFS: invalid path format\n");
    return -EINVAL;
  }

  int res = initPFS(argv[0], Device_None);
  if (res)
    return res;

  // Build PFS path
  char *elfPath = normalizePath(argv[0], Device_APA);
  if (!elfPath)
    return -ENODEV;

  // Make sure file exists and unmount the partition
  DPRINTF("Checking for %s\n", elfPath);
  res = tryFile(elfPath);
  deinitPFS();
  if (res)
    return -ENOENT;

  // Build canonical path as 'hdd0:<partition name>:pfs:/<path to ELF>'
  static char canonicalPath[PATH_MAX];
  if (subPath[0] == '/' || subPath[0] == '\\')
    subPath++;
  snprintf(canonicalPath, sizeof(canonicalPath), "%s:pfs:/%s", mountPart, subPath);
  argv[0] = canonicalPath;

  return LoadELFFromFile(argc, argv);
}
