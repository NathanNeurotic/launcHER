#include "cnf.h"
#include "common.h"
#include "dprintf.h"
#include <ctype.h>
#include <init.h>
#include <ps2sdkapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// The name each BDM block device driver registers its devices under (ps2sdk bdmfs_fatfs uses the
// driver's block_device path), and the launcher device it is.
static const struct {
  const char *name;
  DeviceType type;
} massDevices[] = {
#ifdef USB
    {"usb", Device_USB},
#endif
#ifdef ATA
    {"ata", Device_ATA},
#endif
#ifdef MX4SIO
    {"mx4sio", Device_MX4SIO},
#endif
#ifdef ILINK
    {"ilink", Device_iLink},
#endif
};
#define MASS_DEVICE_COUNT (sizeof(massDevices) / sizeof(massDevices[0]))
#define MASS_UNITS 4 // devices (or partitions) looked at per driver

// OPL and RiptOPL start an APPS entry with argv[0] = massN:/..., whatever block device holds it: USB,
// the exFAT internal HDD, MX4SIO and i.Link all share ps2sdk's generic "mass" name. wLaunchELF passes
// the device's own name (ata0:/..., mx4sio0:/...) instead, which is why the same launcHER works from
// there. A mass path therefore cannot choose the drivers: load all of them, find the file on whichever
// device has it and rewrite path to that device's own name, setting type. UDPBD is left out: it would
// bring the network up just to look.
static int findMassFile(char *path, size_t pathSize, DeviceType *type) {
  char relPath[PATH_MAX];
  char *colon = strchr(path, ':');
  if (!colon || strlen(colon + 1) >= sizeof(relPath))
    return -ENOENT;
  strcpy(relPath, colon + 1);

  DeviceType all = Device_None;
  for (size_t i = 0; i < MASS_DEVICE_COUNT; i++)
    all |= massDevices[i].type;
  int res = initModulesAny(all);
  if (res)
    return res;

  // Devices appear a moment after their drivers load: keep looking, as for any other CNF
  for (int attempt = 0; attempt <= DELAY_ATTEMPTS; attempt++) {
    for (size_t i = 0; i < MASS_DEVICE_COUNT; i++) {
      for (int unit = 0; unit < MASS_UNITS; unit++) {
        if (snprintf(path, pathSize, "%s%d:%s%s", massDevices[i].name, unit, (relPath[0] == '/') ? "" : "/", relPath) >= (int)pathSize)
          return -ENOENT;
        FILE *probe = fopen(path, "r");
        if (probe) {
          fclose(probe);
          *type = massDevices[i].type;
          DPRINTF("Found %s\n", path);
          return 0;
        }
      }
    }
    sleep(1);
  }
  msg("Quickboot: %s was not found on any USB, exFAT HDD, MX4SIO or i.Link device\n", relPath);
  return -ENODEV;
}

int handleQuickboot(char *cnfPath) {
  static const char quickbootName[] = "launcHER.CNF";
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

    if (prefixLen + sizeof(quickbootName) > sizeof(resolvedPath))
      return -ENOENT;

    memcpy(resolvedPath, cnfPath, prefixLen);
    memcpy(resolvedPath + prefixLen, quickbootName, sizeof(quickbootName));
  } else {
    // Explicit CNF/CFG paths still work exactly as supplied.
    if (strlen(cnfPath) >= sizeof(resolvedPath))
      return -ENOENT;
    strcpy(resolvedPath, cnfPath);
  }

  cnfPath = resolvedPath;

  int isHDD = 0;
  DeviceType dtype = guessDeviceType(cnfPath);
  if (dtype == Device_APA)
    isHDD = 1;

  int res;
  int foundByName = 0;
  if (isHDD) {
    dtype = Device_APA;
    if ((res = initPFS(cnfPath, Device_None)))
      return res;
  } else if (!isConfig && dtype == Device_USB && !strncmp(cnfPath, "mass", 4)) {
    // launcHER's own folder, named the generic massN: way (an OPL/RiptOPL APPS launch): find which
    // device it really is. An explicit CNF path keeps launcHER's own meaning of mass, USB.
    if ((res = findMassFile(resolvedPath, sizeof(resolvedPath), &dtype)))
      return res;
    foundByName = 1;
  } else {
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

  // A path findMassFile found is already the live device name (usb0:, ata0:, ...)
  if (!foundByName)
    cnfPath = normalizePath(cnfPath, dtype);
  if (!cnfPath) {
    if (isHDD)
      deinitPFS();
    return -ENOENT;
  }

  DPRINTF("Opening %s\n", cnfPath);
  FILE *file = fopen(cnfPath, "r");
  int delayAttempts = DELAY_ATTEMPTS; // Max number of attempts
  while (!file) {
    sleep(1);
    delayAttempts--;
    if (delayAttempts < 0) {
      msg("Quickboot: Failed to open %s\n", cnfPath);
      if (isHDD)
        deinitPFS();
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
