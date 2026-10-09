#include "cnf.h"
#include "common.h"
#include "dprintf.h"
#include "launch_args.h"
#include <ctype.h>
#include <init.h>
#include <ps2sdkapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <usbhdfsd-common.h>
#define NEWLIB_PORT_AWARE
#include "fileXio_rpc.h"

// The BDM drivers this build has: the name a driver reports for a massN: slot
// (USBMASS_IOCTL_GET_DRIVERNAME -- the names RiptOPL matches), the name it registers the same device
// under for launcHER's own paths (ps2sdk bdmfs_fatfs: the block device's path), and the device it is.
static const struct {
  const char *driver, *driverAlt, *name;
  DeviceType type;
} massDrivers[] = {
#ifdef USB
    {"usb", NULL, "usb", Device_USB},
#endif
#ifdef ATA
    {"ata", NULL, "ata", Device_ATA},
#endif
#ifdef MX4SIO
    {"sdc", "mx4sio", "mx4sio", Device_MX4SIO},
#endif
#ifdef ILINK
    {"sd", "ilink", "ilink", Device_iLink},
#endif
};
#define MASS_DRIVER_COUNT ((int)(sizeof(massDrivers) / sizeof(massDrivers[0])))
#define MASS_SLOTS        10 // bdmfs_fatfs mount slots, mass0: to mass9:

// Which massDrivers entry backs mass<slot>:, by asking the slot itself. -1 = nothing mounted there,
// or a driver launcHER does not load.
static int massSlotDriver(int slot) {
  char path[16], driver[32] = {0};

  snprintf(path, sizeof(path), "mass%d:/", slot);
  int dir = fileXioDopen(path);
  if (dir < 0)
    return -1;
  int res = fileXioIoctl2(dir, USBMASS_IOCTL_GET_DRIVERNAME, NULL, 0, driver, sizeof(driver) - 1);
  fileXioDclose(dir);
  if (res < 0)
    return -1;
  for (int i = 0; i < MASS_DRIVER_COUNT; i++) {
    if (!strcmp(driver, massDrivers[i].driver) || (massDrivers[i].driverAlt && !strcmp(driver, massDrivers[i].driverAlt)))
      return i;
  }
  DPRINTF("mass%d: is driver %s, which launcHER does not load\n", slot, driver);
  return -1;
}

// 1 when mass<slot>: holds rest, the path after the device's colon ("/APPS/.../launcHER.CNF").
static int massSlotHas(int slot, const char *rest) {
  char path[PATH_MAX];

  if (snprintf(path, sizeof(path), "mass%d:%s", slot, rest) >= (int)sizeof(path))
    return 0;
  FILE *file = fopen(path, "r");
  if (!file)
    return 0;
  fclose(file);
  return 1;
}

// OPL and RiptOPL start an APPS entry with argv[0] = massN:/..., whatever block device holds it: "mass"
// is only ps2sdk's connection-order name, shared by USB, the exFAT internal HDD, MX4SIO and i.Link.
// wLaunchELF passes the device's own name (ata0:/...) instead, which is why the same launcHER works
// from there. So do what RiptOPL does with its own massN: boot: load the BDM drivers and ask the slot
// which driver it is. path is rewritten to the name wLaunchELF would have passed -- <name><k>:, k
// counting the earlier slots of the same driver, which is how bdmfs numbers those names -- and type set
// to match, so the launch carries on exactly as one from there. UDPBD is left out: it would bring the
// network up just to ask.
static int resolveMassPath(char *path, size_t pathSize, DeviceType *type) {
  char rest[PATH_MAX];
  char *colon = strchr(path, ':');
  int slot = (path[4] >= '0' && path[4] <= '9') ? path[4] - '0' : 0;
  int driver = -1, k = 0;

  if (!colon || strlen(colon + 1) >= sizeof(rest))
    return -ENOENT;
  strcpy(rest, colon + 1);

  DeviceType all = Device_None;
  for (int i = 0; i < MASS_DRIVER_COUNT; i++)
    all |= massDrivers[i].type;
  int res = initModulesAny(all);
  if (res)
    return res;

  // A device registers a moment after its driver loads: keep asking, as for any other CNF
  for (int attempt = 0; attempt <= DELAY_ATTEMPTS && (driver = massSlotDriver(slot)) < 0; attempt++)
    sleep(1);
  if (driver < 0) {
    msg("Quickboot: mass%d: did not answer as a USB, exFAT HDD, MX4SIO or i.Link device\n", slot);
    return -ENODEV;
  }

  // This IOP numbers devices by its own connection order, which can differ from the loader's when
  // several are plugged in. launcHER's own folder settles it: if the slot we were handed does not hold
  // it, the mounted slot that does is the device the loader meant.
  if (!massSlotHas(slot, rest)) {
    for (int other = 0; other < MASS_SLOTS; other++) {
      int d;
      if (other != slot && (d = massSlotDriver(other)) >= 0 && massSlotHas(other, rest)) {
        slot = other;
        driver = d;
        break;
      }
    }
  }

  for (int earlier = 0; earlier < slot; earlier++) {
    if (massSlotDriver(earlier) == driver)
      k++;
  }
  if (snprintf(path, pathSize, "%s%d:%s", massDrivers[driver].name, k, rest) >= (int)pathSize)
    return -ENOENT;
  *type = massDrivers[driver].type;
  DPRINTF("mass%d: is %s -> %s\n", slot, massDrivers[driver].driver, path);
  return 0;
}

int handleQuickboot(char *cnfPath) {
  static const char quickbootName[] = "launcHER.CNF";
  char originalTarget[PATH_MAX];
  strncpy(originalTarget, cnfPath, sizeof(originalTarget) - 1);
  originalTarget[sizeof(originalTarget) - 1] = '\0';
  if (pops_is_xx_prefix(originalTarget))
    pops_set_active_xx_launch(1);
  if (pops_is_sb_prefix(originalTarget))
    pops_set_active_sb_launch(1);
  char resolvedPath[PATH_MAX] = {0};

  // When quickboot is entered through an ELF path, always load launcHER.CNF
  // from that ELF's directory. This keeps the config name stable even when
  // launcHER.elf is renamed for an OPL APPS entry (for example Soul Blade.ELF).
  char *ext = strrchr(cnfPath, '.');
  int isConfig = (ext && (!strcasecmp(ext, ".cnf") || !strcasecmp(ext, ".cfg")));

  if (!isConfig) {
    size_t prefixLen = 0;
    char *separator = strrchr(cnfPath, '/');
    char *bsep = strrchr(cnfPath, '\\');
    if (bsep && (!separator || bsep > separator))
      separator = bsep;

    if (separator) {
      prefixLen = (size_t)(separator - cnfPath) + 1;
    } else {
      // Also support device paths without a slash, such as mc0:BOOT.ELF.
      separator = strrchr(cnfPath, ':');
      if (separator)
        prefixLen = (size_t)(separator - cnfPath) + 1;
    }

    if (prefixLen > 0) {
      if (prefixLen + sizeof(quickbootName) > sizeof(resolvedPath))
        return -ENOENT;
      memcpy(resolvedPath, cnfPath, prefixLen);
      memcpy(resolvedPath + prefixLen, quickbootName, sizeof(quickbootName));
    } else {
      // Bare ELF title without directory or device (e.g. "Crash.ELF" or "PP.Crash.ELF").
      char baseTitle[64] = {0};
      int pfx = PREFIX_NONE;
      if (pops_is_pp_prefix(cnfPath)) {
        const char *pstart = strrchr(cnfPath, '/');
        const char *bstart = strrchr(cnfPath, '\\');
        if (bstart && (!pstart || bstart > pstart)) pstart = bstart;
        if (!pstart) pstart = strrchr(cnfPath, ':');
        pstart = pstart ? pstart + 1 : cnfPath;

        const char *dot = strrchr(pstart, '.');
        size_t blen = dot ? (size_t)(dot - pstart) : strlen(pstart);
        if (blen >= sizeof(baseTitle)) blen = sizeof(baseTitle) - 1;
        memcpy(baseTitle, pstart, blen);
        baseTitle[blen] = '\0';

        snprintf(resolvedPath, sizeof(resolvedPath), "hdd0:%s:pfs:/%s", baseTitle, quickbootName);
      } else {
        snprintf(resolvedPath, sizeof(resolvedPath), "hdd0:__.POPS:pfs:/%s", quickbootName);
      }
    }
  } else {
    // Explicit CNF/CFG paths still work exactly as supplied.
    if (strlen(cnfPath) >= sizeof(resolvedPath))
      return -ENOENT;
    strcpy(resolvedPath, cnfPath);
  }

  cnfPath = resolvedPath;

  int isHDD = 0;
  DeviceType dtype = guessDeviceType(cnfPath);
  if (dtype == Device_None) {
    dtype = guessDeviceType(originalTarget);
    if (dtype == Device_None && (pops_is_pp_prefix(originalTarget) || !strchr(originalTarget, ':')))
      dtype = Device_APA;
  }
  if (dtype == Device_APA)
    isHDD = 1;

  int res;
  if (isHDD) {
    dtype = Device_APA;
    res = initPFS(cnfPath, Device_None);
    if (res) {
      char candidates[16][512];
      int candidateCount = pops_resolve_candidate_targets(originalTarget, NULL, candidates, 16);
      for (int c = 0; c < candidateCount; ++c) {
        char *vcdArgv[1] = { candidates[c] };
        if (launchPath(1, vcdArgv) == 0)
          return 0;
      }
      return res;
    }
  } else {
    PopsBdmaMode bdmaMode = pops_detect_bdma_mode();
    if (bdmaMode == POPS_BDMA_MMCE) {
      dtype = Device_MMCE;
    } else if (bdmaMode == POPS_BDMA_ATA) {
      dtype = Device_ATA;
    } else if (bdmaMode == POPS_BDMA_MX4SIO) {
      dtype = Device_MX4SIO;
    } else if (bdmaMode == POPS_BDMA_ILINK) {
      dtype = Device_iLink;
    } else if (!isConfig && dtype == Device_USB && !strncmp(cnfPath, "mass", 4) &&
               (res = resolveMassPath(resolvedPath, sizeof(resolvedPath), &dtype))) {
      char candidates[16][512];
      int candidateCount = pops_resolve_candidate_targets(originalTarget, NULL, candidates, 16);
      for (int c = 0; c < candidateCount; ++c) {
        char *vcdArgv[1] = { candidates[c] };
        if (launchPath(1, vcdArgv) == 0)
          return 0;
      }
      return res;
    }
    if (dtype == Device_None)
      return -ENODEV;

    // Always reset IOP to a known state
    if ((res = initModules(dtype)))
      return res;
  }

  // Open the config file
  char launchTarget[PATH_MAX];
  strncpy(launchTarget, cnfPath, sizeof(launchTarget) - 1);
  launchTarget[sizeof(launchTarget) - 1] = '\0';

  cnfPath = normalizePath(cnfPath, dtype);
  if (!cnfPath) {
    if (isHDD)
      deinitPFS();
    return -ENOENT;
  }

  DPRINTF("Opening %s\n", cnfPath);
  FILE *file = fopen(cnfPath, "r");
  int delayAttempts = DELAY_ATTEMPTS; // Max number of attempts
  if (!isConfig && (pops_is_xx_prefix(originalTarget) || pops_is_sb_prefix(originalTarget) ||
                    pops_is_pp_prefix(originalTarget) || !strchr(originalTarget, ':'))) {
    delayAttempts = 1;
  }
  while (!file) {
    sleep(1);
    delayAttempts--;
    if (delayAttempts < 0) {
      /* If launcHER.CNF is absent, resolve matching or adjacent game VCD files */
      char candidates[16][512];
      int candidateCount = pops_resolve_candidate_targets(originalTarget, NULL, candidates, 16);

      for (int c = 0; c < candidateCount; ++c) {
        const char *cand = candidates[c];
        char probePath[PATH_MAX];
        if (isHDD) {
          const char *pfsSub = strstr(cand, ":pfs:/");
          if (!pfsSub)
            pfsSub = strstr(cand, ":pfs0:/");
          if (pfsSub) {
            snprintf(probePath, sizeof(probePath), "pfs0:%s", pfsSub + (pfsSub[5] == '0' ? 6 : 5));
          } else if (!strncmp(cand, "pfs", 3)) {
            snprintf(probePath, sizeof(probePath), "%s", cand);
          } else {
            probePath[0] = '\0';
          }
        } else {
          DeviceType candType = guessDeviceType(cand);
          int typeMatches = (candType == dtype) ||
            ((dtype == Device_USB || dtype == Device_ATA || dtype == Device_MX4SIO || dtype == Device_iLink) &&
             (candType == Device_USB || candType == Device_ATA || candType == Device_MX4SIO || candType == Device_iLink));
          if (typeMatches) {
            if (!strncmp(cand, "mass:/", 6)) {
              snprintf(probePath, sizeof(probePath), "mass0:%s", cand + 5);
            } else if (!strncmp(cand, "mx4sio:/", 8)) {
              snprintf(probePath, sizeof(probePath), "mx4sio0:%s", cand + 7);
            } else if (!strncmp(cand, "ata:/", 5)) {
              snprintf(probePath, sizeof(probePath), "ata0:%s", cand + 4);
            } else if (!strncmp(cand, "ilink:/", 7)) {
              snprintf(probePath, sizeof(probePath), "ilink0:%s", cand + 6);
            } else if (!strncmp(cand, "smb:/", 5)) {
              snprintf(probePath, sizeof(probePath), "smb0:%s", cand + 4);
            } else if (!strncmp(cand, "mmce:/", 6)) {
              snprintf(probePath, sizeof(probePath), "mmce0:%s", cand + 5);
            } else {
              snprintf(probePath, sizeof(probePath), "%s", cand);
            }
          } else {
            probePath[0] = '\0';
          }
        }

        if (probePath[0] && !tryFile(probePath)) {
          if (isHDD)
            deinitPFS();
          char *vcdArgv[1] = { (char *)cand };
          return launchPath(1, vcdArgv);
        }
      }

      /* Fall back to direct launches across devices */
      if (isHDD)
        deinitPFS();

      for (int c = 0; c < candidateCount; ++c) {
        char *vcdArgv[1] = { candidates[c] };
        int lres = launchPath(1, vcdArgv);
        if (lres == 0)
          return 0;
      }

      msg("Quickboot: Failed to open %s\n", cnfPath);
      return -ENODEV;
    }
    file = fopen(cnfPath, "r");
  }

  // Temporary path and argument lists
  linkedStr *targetPaths = NULL;
  linkedStr *targetArgs = NULL;
  int targetArgc = 1; // argv[0] is the ELF path

  char lineBuffer[PATH_MAX] = {0};
  char relpathBuffer[PATH_MAX] = {0};
  char *valuePtr = NULL;

  char *lastSlash = strrchr(launchTarget, '/');
  char *lastBslash = strrchr(launchTarget, '\\');
  if (lastBslash && (!lastSlash || lastBslash > lastSlash))
    lastSlash = lastBslash;
  if (lastSlash)
    *lastSlash = '\0';

  while (fgets(lineBuffer, sizeof(lineBuffer), file)) { // fgets returns NULL if EOF or an error occurs
    // Find the start of the value
    valuePtr = strchr(lineBuffer, '=');
    if (!valuePtr)
      continue;
    *valuePtr = '\0';

    // Trim whitespace and terminate the value
    do {
      valuePtr++;
    } while (isspace((int)*valuePtr));
    valuePtr[strcspn(valuePtr, "\r\n")] = '\0';

    if (!strncmp(lineBuffer, "boot", 4) && lastSlash) {
      if (strlen(valuePtr) > 0) {
        // Assemble full path
        snprintf(relpathBuffer, PATH_MAX - 1, "%s/%s", launchTarget, valuePtr);
        targetPaths = addStr(targetPaths, relpathBuffer);
      }
      continue;
    }
    if (!strncmp(lineBuffer, "path", 4)) {
      if ((strlen(valuePtr) > 0))
        targetPaths = addStr(targetPaths, valuePtr);
      continue;
    }
    if (!strncmp(lineBuffer, "arg", 3)) {
      if ((strlen(valuePtr) > 0)) {
        targetArgs = addStr(targetArgs, valuePtr);
        targetArgc++;
      }
      continue;
    }
  }
  fclose(file);
  if (isHDD)
    deinitPFS();

  // Build argv, freeing targetArgs
  char **targetArgv = malloc(targetArgc * sizeof(char *));
  linkedStr *tlstr;
  if (targetArgs) {
    tlstr = targetArgs;
    for (int i = 1; i < targetArgc; i++) {
      targetArgv[i] = tlstr->str;
      tlstr = tlstr->next;
      free(targetArgs);
      targetArgs = tlstr;
    }
    free(targetArgs);
  }

  // Parse arguments for global flags
  targetArgc = parseGlobalFlags(targetArgc, targetArgv);

  // Try every path
  tlstr = targetPaths;
  while (tlstr) {
    targetArgv[0] = tlstr->str;
    DPRINTF("Attempting to launch %s\n", tlstr->str);
    // If target path is valid, it'll never return from launchPath
    launchPath(targetArgc, targetArgv);
    free(tlstr->str);
    tlstr = tlstr->next;
    free(targetPaths);
    targetPaths = tlstr;
  }
  free(targetPaths);

  msg("Quickboot: all paths have been tried\n");
  return -ENODEV;
}
