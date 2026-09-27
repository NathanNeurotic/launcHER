#include "common.h"
#include "cnf.h"
#include "dprintf.h"
#include "game_id.h"
#include "handlers.h"
#include "init.h"
#include "loader.h"
#include <ctype.h>
#include <debug.h>
#include <fcntl.h>
#include <kernel.h>
#include <ps2sdkapi.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define NEWLIB_PORT_AWARE
#include <fileXio_rpc.h>
#include <hdd-ioctl.h>
#include <io_common.h>

static int isScreenInited = 0;
char pathbuffer[PATH_MAX];

void initScreen() {
  if (isScreenInited)
    return;

  init_scr();
  scr_setCursor(0);
  scr_printf(".\n\n\n\n"); // To avoid messages being hidden by overscan
  isScreenInited = 1;
}

// Prints a message to the screen and console
void msg(const char *str, ...) {
  va_list args;
  va_start(args, str);

  initScreen();

  scr_vprintf(str, args);

  va_end(args);
}

// Prints a message to the screen and console and exits
void fail(const char *str, ...) {
  va_list args;
  va_start(args, str);

  initScreen();

  scr_vprintf(str, args);

  va_end(args);

  sleep(10);

  char *argv[1] = {"BootIllegal"};
  ExecOSD(1, argv);
}

// Tests if file exists by opening it
int tryFile(char *filepath) {
  int fd = open(filepath, O_RDONLY);
  if (fd < 0) {
    return fd;
  }
  close(fd);
  return 0;
}

// Launches ELF from any generic device without path normalization and delays
int handleGenericPath(DeviceType device, int argc, char *argv[]) {
  if ((argv[0] == 0) || (strlen(argv[0]) < 5)) {
    msg("Generic: invalid argument\n");
    return -EINVAL;
  }

  // Initialize device modules
  int res = initModules(device);
  if (res)
    return res;

  if (tryFile(argv[0]))
    return -ENOENT;

  return LoadELFFromFile(argc, argv);
}

// Attempts to launch ELF from device and path in path
int launchPath(int argc, char *argv[]) {
  int ret = 0;
  switch (guessDeviceType(argv[0])) {
  case Device_MemoryCard:
    ret = handleMC(argc, argv);
    break;
#ifdef MMCE
  case Device_MMCE:
    ret = handleMMCE(argc, argv);
    break;
#endif
#ifdef USB
  case Device_USB:
    ret = handleBDM(Device_USB, argc, argv);
    break;
#endif
#ifdef ATA
  case Device_ATA:
    ret = handleBDM(Device_ATA, argc, argv);
    break;
#endif
#ifdef MX4SIO
  case Device_MX4SIO:
    ret = handleBDM(Device_MX4SIO, argc, argv);
    break;
#endif
#ifdef ILINK
  case Device_iLink:
    ret = handleBDM(Device_iLink, argc, argv);
    break;
#endif
#ifdef UDPBD
  case Device_UDPBD:
    ret = handleBDM(Device_UDPBD, argc, argv);
    break;
#endif
#ifdef UDPFS
  case Device_UDPFS:
    ret = handleUDPFS(argc, argv);
    break;
#endif
#ifdef APA
  case Device_APA:
    if (strstr(argv[0], ":PATINFO"))
      ret = handlePATINFO(argc, argv);
    else
      ret = handlePFS(argc, argv);
    break;
#endif
#ifdef CDROM
  case Device_CDROM:
    ret = handleCDROM(argc, argv);
    break;
#endif
#ifdef XFROM
  case Device_XFROM:
    ret = handleGenericPath(Device_XFROM, argc, argv);
    break;
#endif
  case Device_ROM:
    ret = execROMPath(argc, argv);
    break;
  default:
    return -ENODEV;
  }

  return ret;
}

// Checks if a substring looks like a PFS mount token (e.g. pfs:, pfs0:, pfs0/)
static int isPfsToken(const char *s) {
  if (!s || strncasecmp(s, "pfs", 3) != 0)
    return 0;
  const char *t = s + 3;
  while (*t >= '0' && *t <= '9')
    t++;
  return (*t == ':' || *t == '/' || *t == '\\');
}

// Parses an APA/PFS path to extract the mount partition (e.g. "hdd0:+OPL")
// and the relative path inside the partition.
int parseAPAPath(const char *path, char *mountPart, size_t partSize, const char **pfsSubPath) {
  if (!path || !path[0])
    return -EINVAL;

  char hddPrefix[8] = "hdd0:";
  const char *p = path;

  // Check if it begins with hdd<unit>:
  if (!strncmp(p, "hdd", 3)) {
    const char *colon = strchr(p, ':');
    if (colon) {
      size_t unitLen = (size_t)(colon - p) + 1;
      if (unitLen < sizeof(hddPrefix)) {
        memcpy(hddPrefix, p, unitLen);
        hddPrefix[unitLen] = '\0';
      }
      p = colon + 1;
    }
  }

  // If path started with "pfs" directly (e.g. pfs0:/path), there is no partition info in path
  if (!strncmp(p, "pfs", 3)) {
    if (mountPart && partSize > 0)
      mountPart[0] = '\0';
    if (pfsSubPath) {
      const char *colon = strchr(p, ':');
      *pfsSubPath = colon ? colon + 1 : p;
    }
    return 0;
  }

  // p points to the start of the partition name (e.g. "+OPL" or "__.EMBER").
  // Find where the partition name ends. Delimiters:
  // 1. ':' (e.g. "+OPL:pfs:/...", "+OPL:pfs0:/...", "+OPL:/...", "+OPL:")
  // 2. '/' or '\\' (e.g. "+OPL/APPS/...")
  // 3. "pfs" mount token without preceding colon (e.g. "+OPLpfs0:/...")
  // 4. '\0' (end of string)
  const char *partStart = p;
  while (*partStart == '/' || *partStart == '\\')
    partStart++;
  const char *partEnd = NULL;

  const char *colon = strchr(partStart, ':');
  const char *slash = strchr(partStart, '/');
  const char *bslash = strchr(partStart, '\\');
  if (bslash && (!slash || bslash < slash))
    slash = bslash;

  // Search for pfs mount token (e.g. pfs:, pfs0:, pfs0/)
  const char *pfsToken = NULL;
  const char *cur = partStart;
  while ((cur = strstr(cur, "pfs")) != NULL) {
    if (cur > partStart && isPfsToken(cur)) {
      pfsToken = cur;
      break;
    }
    cur += 3;
  }

  // Determine the earliest valid delimiter
  if (colon)
    partEnd = colon;
  if (slash && (!partEnd || slash < partEnd))
    partEnd = slash;
  if (pfsToken && (!partEnd || pfsToken < partEnd))
    partEnd = pfsToken;

  if (!partEnd)
    partEnd = partStart + strlen(partStart);

  size_t partLen = (size_t)(partEnd - partStart);
  if (partLen == 0)
    return -EINVAL;

  if (mountPart && partSize > 0) {
    snprintf(mountPart, partSize, "%s%.*s", hddPrefix, (int)partLen, partStart);
  }

  // Advance past any delimiter, ":pfs", "pfs", digits, and colon to find the subpath
  const char *sub = partEnd;
  if (*sub == ':')
    sub++;

  if (!strncasecmp(sub, "pfs", 3)) {
    sub += 3;
    while (*sub >= '0' && *sub <= '9')
      sub++;
    if (*sub == ':')
      sub++;
  }

  if (pfsSubPath) {
    *pfsSubPath = sub;
  }

  return 0;
}

// Attempts to guess device type from path
DeviceType guessDeviceType(char *path) {
  if (!strncmp("mc", path, 2)) {
    return Device_MemoryCard;
#ifdef MMCE
  } else if (!strncmp("mmce", path, 4)) {
    return Device_MMCE;
#endif
#ifdef USB
  } else if (!strncmp("mass", path, 4) || !strncmp("usb", path, 3)) {
    return Device_USB;
#endif
#ifdef ATA
  } else if (!strncmp("ata", path, 3)) {
    return Device_ATA;
#endif
#ifdef MX4SIO
  } else if (!strncmp("mx4sio", path, 6)) {
    return Device_MX4SIO;
#endif
#ifdef ILINK
  } else if (!strncmp("ilink", path, 5)) {
    return Device_iLink;
#endif
#ifdef UDPBD
  } else if (!strncmp("udpbd", path, 5)) {
    return Device_UDPBD;
#endif
#ifdef UDPFS
  } else if (!strncmp("udpfs", path, 5)) {
    return Device_UDPFS;
#endif
#ifdef APA
  } else if (!strncmp("hdd", path, 3) || path[0] == '+' || !strncmp("pfs", path, 3) || !strncmp("__", path, 2) || strstr(path, ":pfs")) {
    return Device_APA;
#endif
#ifdef CDROM
  } else if (!strncmp("cdrom", path, 5)) {
    return Device_CDROM;
#endif
#ifdef XFROM
  } else if (!strncmp("xfrom", path, 5)) {
    return Device_XFROM;
#endif
  } else if (!strncmp("rom", path, 3))
    return Device_ROM;

  return Device_None;
}

// Attempts to convert launcher-specific path into a valid device path
char *normalizePath(char *path, DeviceType type) {
  pathbuffer[0] = '\0';
  switch (type) {
  case Device_APA: {
    const char *subPath = NULL;
    if (parseAPAPath(path, NULL, 0, &subPath) == 0 && subPath && subPath[0] != '\0') {
      if (subPath[0] == '/' || subPath[0] == '\\')
        snprintf(pathbuffer, sizeof(pathbuffer), "%s%s", PFS_MOUNTPOINT, subPath);
      else
        snprintf(pathbuffer, sizeof(pathbuffer), "%s/%s", PFS_MOUNTPOINT, subPath);
    } else {
      if (path[0] == '/' || path[0] == '\\')
        snprintf(pathbuffer, sizeof(pathbuffer), "%s%s", PFS_MOUNTPOINT, path);
      else
        snprintf(pathbuffer, sizeof(pathbuffer), "%s/%s", PFS_MOUNTPOINT, path);
    }
    for (char *c = pathbuffer + strlen(PFS_MOUNTPOINT); *c; c++) {
      if (*c == '\\')
        *c = '/';
    }
    break;
  }
  case Device_MemoryCard:
  case Device_MMCE:
  case Device_CDROM:
  case Device_UDPFS:
  case Device_ATA:
  case Device_XFROM:
  case Device_MX4SIO:
  case Device_iLink:
  case Device_UDPBD:
    strncat(pathbuffer, path, PATH_MAX - 6);
    break;
  // BDM USB
  case Device_USB:
    char devNumber = path[3]; // usb
    if (devNumber == 's')     // mass
      devNumber = path[4];
    // Get relative ELF path from argv[0]
    path = strchr(path, ':');
    if (!path)
      return NULL;

    path++;

    strcpy(pathbuffer, USB_MOUNTPOINT);
    if (((devNumber > '0') && (devNumber <= '9')) || (devNumber == '?'))
      pathbuffer[4] = devNumber;

    if (path[0] != '/')
      strcat(pathbuffer, "/");
    strncat(pathbuffer, path, PATH_MAX - sizeof(USB_MOUNTPOINT) - 1);
    break;
  default:
    return NULL;
  }
  return pathbuffer;
}

// Mounts the partition specified in path
int mountPFS(char *path) {
#ifndef APA
  return -ENODEV;
#else
  char mountPart[256];
  if (parseAPAPath(path, mountPart, sizeof(mountPart), NULL) != 0 || mountPart[0] == '\0') {
    return -ENODEV;
  }

  // Mount the partition
  DPRINTF("Mounting %s to %s\n", mountPart, PFS_MOUNTPOINT);
  int res = fileXioMount(PFS_MOUNTPOINT, mountPart, FIO_MT_RDONLY);
  if (res)
    return -ENODEV;

  return 0;
#endif
}

// Initializes APA-formatted HDD and mounts the partition if specified
int initPFS(char *path, DeviceType additionalDevices) {
#ifndef APA
  return -ENODEV;
#else
  int res;
  // Reset IOP
  if ((res = initModules(Device_APA | additionalDevices)))
    return res;

  char hddDev[8] = "hdd0:";
  if (path && !strncmp(path, "hdd1", 4))
    strncpy(hddDev, "hdd1:", sizeof(hddDev));

  // Wait for IOP to initialize device driver
  DPRINTF("Waiting for HDD to become available\n");
  for (int attempts = 0; attempts < DELAY_ATTEMPTS; attempts++) {
    res = open(hddDev, O_DIRECTORY | O_RDONLY);
    if (res >= 0) {
      close(res);
      break;
    }
    sleep(1);
  }
  if (res < 0)
    return -ENODEV;

  if (!path)
    return 0;
  return mountPFS(path);
#endif
}

// Unmounts the partition
void deinitPFS() {
#ifdef APA
  fileXioDevctl(PFS_MOUNTPOINT, PDIOC_CLOSEALL, NULL, 0, NULL, 0);
  fileXioSync(PFS_MOUNTPOINT, FXIO_WAIT);
  fileXioUmount(PFS_MOUNTPOINT);
#endif
}

// Puts HDD in idle mode and powers off the dev9 device
void shutdownDEV9() {
#if defined(APA) || defined(ATA)
  // Unmount the partition (if mounted)
  fileXioUmount("pfs0:");
  // Immediately put HDDs into idle mode
  fileXioDevctl("hdd0:", HDIOC_IDLEIMM, NULL, 0, NULL, 0);
  fileXioDevctl("hdd1:", HDIOC_IDLEIMM, NULL, 0, NULL, 0);
  // Turn off dev9
  fileXioDevctl("dev9x:", DDIOC_OFF, NULL, 0, NULL, 0);
#endif
}

// Parses the launcher argv for global flags.
// Returns the new argc
int parseGlobalFlags(int argc, char *argv[]) {
  if (argc < 2)
    return argc;

  char *valuePtr = NULL;
  for (int i = argc - 1; i > 0; i--) {
    // Find the start of the value
    valuePtr = strchr(argv[i], '=');
    if (valuePtr) {
      // Trim whitespace and terminate the value
      do {
        valuePtr++;
      } while (isspace((int)*valuePtr));
      valuePtr[strcspn(valuePtr, "\r\n")] = '\0';
    }

    if (valuePtr && !strncmp(argv[i], "-gsm=", 5)) {
      // eGSM argument
      settings.gsmArgument = strdup(valuePtr);
      DPRINTF("Applying eGSM options: %s\n", settings.gsmArgument);
      argc--;
    } else if (!strcmp(argv[i], "-xosd")) {
      settings.flags |= FLAG_BOOT_OSD;
      settings.deviceHint = Device_XFROM;
      DPRINTF("Setting OSD flag and applying XFROM hint\n");
    } else if (!strcmp(argv[i], "-osd")) {
      settings.flags |= FLAG_BOOT_OSD;
      settings.deviceHint = Device_MemoryCard;
      DPRINTF("Setting OSD flag\n");
      argc--;
    } else if (!strcmp(argv[i], "-hosd")) {
      settings.flags |= FLAG_BOOT_HOSD;
      settings.deviceHint = Device_APA;
      DPRINTF("Setting HOSD flag\n");
      argc--;
    } else if (!strcmp(argv[i], "-appid")) {
      settings.flags |= FLAG_APP_GAMEID;
      DPRINTF("Enabling game ID for apps\n");
      argc--;
    } else if (!strcmp(argv[i], "-patinfo")) {
      settings.flags |= FLAG_BOOT_PATINFO;
      DPRINTF("Setting PATINFO flag\n");
      argc--;
    } else if (!strcmp(argv[argc - 1], "-skip_argv0")) {
      settings.flags |= FLAG_SKIP_ARGV;
      argc--;
      DPRINTF("Will not pass argv[0] to the target ELF\n");
    } else if (valuePtr && !strncmp(argv[i], "-titleid=", 9)) {
      settings.titleID = strdup(valuePtr);
      DPRINTF("Using custom title ID: %s\n", settings.titleID);
      argc--;
    } else if (valuePtr && !strncmp(argv[i], "-dev9=", 6)) {
      if (!strcmp(valuePtr, "NICHDD"))
        settings.dev9ShutdownType = ShutdownType_None;
      else if (!strcmp(valuePtr, "NIC"))
        settings.dev9ShutdownType = ShutdownType_HDD;
      DPRINTF("DEV9 Shutdown Type: %d\n", settings.dev9ShutdownType);
      argc--;
    } else
      break; // Exit to preserve application arguments
  }

  return argc;
}

int LoadELFFromFile(int argc, char *argv[]) {
  if (settings.titleID || (settings.flags & FLAG_APP_GAMEID)) {
    char *titleID = settings.titleID;
    if (!titleID)
      titleID = generateTitleID(argv[0]);
    if (titleID) {
      DPRINTF("Title ID is %s\n", titleID);
      gsDisplayGameID(titleID);
    }
  } else
    // Always reset GS
    gsDisplayGameID(NULL);

  LoadOptions opts = {
      .argc = argc,
      .argv = argv,
      .dev9ShutdownType = settings.dev9ShutdownType,
  };
  if (settings.flags & FLAG_SKIP_ARGV)
    opts.skipArgv0 = 1;
  if (settings.gsmArgument)
    opts.eGSM = settings.gsmArgument;

  return loadELF(&opts);
}
