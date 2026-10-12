#include "handler_pops.h"
#include "launch_args.h"
#include "common.h"
#include "dprintf.h"
#include "init.h"
#include "pops_external.h"
#include "pops_bootstrap.h"
#include "pops_vcd.h"
#include "pops_vmc.h"
#include "pops_config.h"
#include "pops_compat_db.h"
#include "pops_modes_patches.h"
#include <ctype.h>
#include <fcntl.h>
#include <kernel.h>
#include <iopcontrol.h>
#include <iopcontrol_special.h>
#include <loadfile.h>
#include <ps2sdkapi.h>
#include <sifrpc.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#define NEWLIB_PORT_AWARE
#include <fileXio_rpc.h>
#include <io_common.h>

extern const char pops_trampoline_code[];
extern const char pops_trampoline_code_end[];

#define POPS_LOAD_RAW_BUF   ((void *)0x01800000)
#define POPS_LOAD_IOP_BUF   ((void *)0x01780000)
#define POPS_STAGE_IOP_BUF  ((void *)0x01700000)
#define POPS_IOP_MAX_SIZE   0x00080000
#define POPS_STAGE_BUF      ((void *)POPS_STAGING_BASE)
#define POPS_LOAD_MAX_SIZE  (8 * 1024 * 1024)

int isPopsTarget(const char *path) {
  if (!path)
    return 0;
  const char *dot = strrchr(path, '.');
  if (!dot)
    return 0;
  return !strcasecmp(dot, ".vcd");
}

static void extractDirectory(const char *path, char *dir, size_t dir_size) {
  if (!path || !dir || dir_size == 0)
    return;
  dir[0] = '\0';
  const char *slash = strrchr(path, '/');
  const char *bslash = strrchr(path, '\\');
  if (bslash && (!slash || bslash > slash))
    slash = bslash;
  if (!slash)
    slash = strrchr(path, ':');

  if (slash) {
    size_t len = (size_t)(slash - path) + 1;
    if (len >= dir_size)
      len = dir_size - 1;
    memcpy(dir, path, len);
    dir[len] = '\0';
  }
}

static void extractGameBase(const char *path, char *base, size_t base_size) {
  if (!path || !base || base_size == 0)
    return;
  base[0] = '\0';
  const char *start = strrchr(path, '/');
  const char *bstart = strrchr(path, '\\');
  if (bstart && (!start || bstart > start))
    start = bstart;
  if (!start)
    start = strrchr(path, ':');
  start = start ? start + 1 : path;

  /* Strip POPStarter launcher prefixes like XX. or SB. */
  if (!strncasecmp(start, "XX.", 3) || !strncasecmp(start, "SB.", 3))
    start += 3;

  const char *dot = strrchr(start, '.');
  size_t len = dot ? (size_t)(dot - start) : strlen(start);
  if (len >= base_size)
    len = base_size - 1;
  memcpy(base, start, len);
  base[len] = '\0';
}

static int findPopsDependenciesForMode(const char *vcdPath, char *popsPath,
                                       size_t popsPathSize, char *ioprpPath,
                                       size_t ioprpPathSize, int requireIox) {
  char vcdDir[PATH_MAX] = {0};
  char devPrefix[16] = {0};
  char testPath[PATH_MAX] = {0};
  char testIop[PATH_MAX] = {0};

  extractDirectory(vcdPath, vcdDir, sizeof(vcdDir));

  const char *colon = strchr(vcdPath, ':');
  if (colon && (size_t)(colon - vcdPath + 2) < sizeof(devPrefix)) {
    size_t dlen = (size_t)(colon - vcdPath) + 1;
    memcpy(devPrefix, vcdPath, dlen);
    devPrefix[dlen] = '\0';
  }

  /* Candidate directories to search for POPS packages / binaries */
  const char *searchDirs[8];
  int searchCount = 0;

  if (vcdDir[0])
    searchDirs[searchCount++] = vcdDir;

  char devPops[PATH_MAX] = {0};
  if (devPrefix[0]) {
    snprintf(devPops, sizeof(devPops), "%s/POPS/", devPrefix);
    searchDirs[searchCount++] = devPops;
  }

  searchDirs[searchCount++] = "mc0:/POPSTARTER/";
  searchDirs[searchCount++] = "mc1:/POPSTARTER/";
  searchDirs[searchCount++] = "mc0:/POPS/";
  searchDirs[searchCount++] = "mc1:/POPS/";
  searchDirs[searchCount++] = "hdd0:__.POPS:pfs:/";

  for (int d = 0; d < searchCount; ++d) {
    const char *dir = searchDirs[d];
    if (!dir || !dir[0])
      continue;

    /* 1. Try POPS_IOX.PAK */
    snprintf(testPath, sizeof(testPath), "%sPOPS_IOX.PAK", dir);
    if (!tryFile(testPath)) {
      snprintf(popsPath, popsPathSize, "%s", testPath);
      if (ioprpPath && ioprpPathSize > 0)
        ioprpPath[0] = '\0';
      return 0;
    }

    /* The original r13 network mode requires the IOX package, even when
     * a legacy POPS.PAK or loose HDD installation is available. Check every
     * candidate directory for IOX before reporting the missing dependency. */
    if (requireIox)
      continue;

    /* 2. Try POPS.PAK */
    snprintf(testPath, sizeof(testPath), "%sPOPS.PAK", dir);
    if (!tryFile(testPath)) {
      snprintf(popsPath, popsPathSize, "%s", testPath);
      if (ioprpPath && ioprpPathSize > 0)
        ioprpPath[0] = '\0';
      return 0;
    }

    /* 3. Try POPS.ELF + IOPRP252.IMG */
    snprintf(testPath, sizeof(testPath), "%sPOPS.ELF", dir);
    snprintf(testIop, sizeof(testIop), "%sIOPRP252.IMG", dir);
    if (!tryFile(testPath) && !tryFile(testIop)) {
      snprintf(popsPath, popsPathSize, "%s", testPath);
      if (ioprpPath && ioprpPathSize > 0)
        snprintf(ioprpPath, ioprpPathSize, "%s", testIop);
      return 0;
    }
  }

  return -ENOENT;
}

int findPopsDependencies(const char *vcdPath, char *popsPath, size_t popsPathSize,
                         char *ioprpPath, size_t ioprpPathSize) {
  return findPopsDependenciesForMode(vcdPath, popsPath, popsPathSize,
                                      ioprpPath, ioprpPathSize, 0);
}

static int readFullFile(const char *path, void *buffer, size_t max_size, size_t *out_size) {
  int fd = open(path, O_RDONLY);
  if (fd < 0)
    return fd;

  off_t sz = lseek(fd, 0, SEEK_END);
  if (sz <= 0 || (size_t)sz > max_size) {
    close(fd);
    return -EINVAL;
  }
  lseek(fd, 0, SEEK_SET);

  size_t total = 0;
  while (total < (size_t)sz) {
    size_t chunk = (size_t)sz - total;
    if (chunk > 65536)
      chunk = 65536;
    ssize_t n = read(fd, (char *)buffer + total, chunk);
    if (n <= 0) {
      close(fd);
      return -EIO;
    }
    total += (size_t)n;
  }
  close(fd);

  if (out_size)
    *out_size = total;
  return 0;
}

/* Driver names within one role are alternatives, not additional modules.
 * Search installed locations and start at most one successful IRX per role.
 * An explicit XX. mode may need several DIFFERENT roles (e.g. DEV9 + ATA).
 * A failed optional driver never counts as installed; final storage probing
 * still decides whether the requested VCD/card backends can actually open. */
static int pops_load_bdma_group(const char *role, const char *const *names,
                                size_t nameCount, const char *const *dirs, int dirCount) {
  char path[PATH_MAX];
  (void)role; /* DPRINTF can compile away in non-debug builds. */
  for (size_t n = 0; n < nameCount; ++n) {
    for (int d = 0; d < dirCount; ++d) {
      int length = snprintf(path, sizeof(path), "%s%s", dirs[d], names[n]);
      if (length < 0 || (size_t)length >= sizeof(path)) {
        DPRINTF("POPS: BDMA %s candidate path too long\n", role);
        continue;
      }
      if (tryFile(path))
        continue;
      int module = SifLoadModule(path, 0, NULL);
      if (module >= 0) {
        DPRINTF("POPS: BDMA %s installed from %s (module %d)\n", role, path, module);
        return 1;
      }
      DPRINTF("POPS: BDMA %s failed to load %s (%d), trying alternative\n",
              role, path, module);
    }
  }
  return 0;
}

#define POPS_BDMA_NAMES(array) (sizeof(array) / sizeof((array)[0]))

static int pops_load_bdma_drivers(const char *vcdDir, const char *vmcDir, PopsBdmaMode mode) {
  const char *dirs[8];
  int dirCount = 0;
  int loaded = 0;
  char irxDir[PATH_MAX] = {0};
  if (vmcDir && vmcDir[0]) dirs[dirCount++] = vmcDir;
  if (vcdDir && vcdDir[0] && (!vmcDir || strcmp(vcdDir, vmcDir)))
    dirs[dirCount++] = vcdDir;
  if (vcdDir && vcdDir[0]) {
    int n = snprintf(irxDir, sizeof(irxDir), "%sIRX/", vcdDir);
    if (n > 0 && (size_t)n < sizeof(irxDir))
      dirs[dirCount++] = irxDir;
  }
  dirs[dirCount++] = "mc0:/POPSTARTER/";
  dirs[dirCount++] = "mc1:/POPSTARTER/";
  dirs[dirCount++] = "mc0:/POPS/";
  dirs[dirCount++] = "mc1:/POPS/";

  static const char *const bdm[] = {"BDM.IRX", "bdm.irx"};
  loaded += pops_load_bdma_group("BDM", bdm, POPS_BDMA_NAMES(bdm), dirs, dirCount);
  if (mode == POPS_BDMA_MX4SIO || mode == POPS_BDMA_GENERIC) {
    static const char *const mx4[] = {"MX4SIO.IRX", "mx4sio.irx", "mx4sio_bd.irx"};
    loaded += pops_load_bdma_group("MX4SIO", mx4, POPS_BDMA_NAMES(mx4), dirs, dirCount);
  }
  if (mode == POPS_BDMA_ATA || mode == POPS_BDMA_GENERIC) {
    static const char *const dev9[] = {"ps2dev9.irx", "PS2DEV9.IRX", "DEV9.IRX"};
    static const char *const ata[] = {"ATA.IRX", "ata.irx", "ata_bd.irx"};
    loaded += pops_load_bdma_group("DEV9", dev9, POPS_BDMA_NAMES(dev9), dirs, dirCount);
    loaded += pops_load_bdma_group("ATA", ata, POPS_BDMA_NAMES(ata), dirs, dirCount);
  }
  if (mode == POPS_BDMA_MMCE || mode == POPS_BDMA_GENERIC) {
    static const char *const mmce[] = {"MMCE.IRX", "mmce.irx", "mmceman.irx"};
    loaded += pops_load_bdma_group("MMCE", mmce, POPS_BDMA_NAMES(mmce), dirs, dirCount);
  }
  if (mode == POPS_BDMA_USB || mode == POPS_BDMA_GENERIC) {
    static const char *const usbCore[] = {"USBD.IRX", "usbd.irx"};
    static const char *const usbFs[] = {"USBHDFSD.IRX", "usbhdfsd.irx"};
    static const char *const usbBd[] = {"usbd_bd_assault.irx"};
    loaded += pops_load_bdma_group("USBD", usbCore, POPS_BDMA_NAMES(usbCore), dirs, dirCount);
    loaded += pops_load_bdma_group("USB filesystem", usbFs, POPS_BDMA_NAMES(usbFs), dirs, dirCount);
    loaded += pops_load_bdma_group("USB BD bridge", usbBd, POPS_BDMA_NAMES(usbBd), dirs, dirCount);
  }
  static const char *const bridge[] = {
    "bdm_assault.irx", "BDM_ASSAULT.IRX", "bdma.irx", "BDMA.IRX"
  };
  loaded += pops_load_bdma_group("BDMA bridge", bridge,
                                 POPS_BDMA_NAMES(bridge), dirs, dirCount);
  return loaded;
}

#undef POPS_BDMA_NAMES

/* Helper to read IPCONFIG.DAT text from candidate folders */
static int pops_read_ipconfig(const char *searchDirs[], int dirCount, char *outIp, size_t outSize) {
  char path[PATH_MAX];
  if (!outIp || outSize == 0) return -EINVAL;
  outIp[0] = '\0';

  for (int d = 0; d < dirCount; ++d) {
    snprintf(path, sizeof(path), "%sIPCONFIG.DAT", searchDirs[d]);
    int fd = open(path, O_RDONLY);
    if (fd < 0) {
      snprintf(path, sizeof(path), "%sipconfig.dat", searchDirs[d]);
      fd = open(path, O_RDONLY);
    }
    if (fd >= 0) {
      char buf[128];
      ssize_t n = read(fd, buf, sizeof(buf) - 1);
      close(fd);
      if (n > 0) {
        buf[n] = '\0';
        char *start = buf;
        while (*start && isspace((unsigned char)*start)) start++;
        char *end = start + strlen(start);
        while (end > start && isspace((unsigned char)*(end - 1))) {
          *(--end) = '\0';
        }
        if (start[0]) {
          strncpy(outIp, start, outSize - 1);
          outIp[outSize - 1] = '\0';
          return 0;
        }
      }
    }
  }

  static const char *sysConf[] = { "mc0:/SYS-CONF/IPCONFIG.DAT", "mc1:/SYS-CONF/IPCONFIG.DAT" };
  for (int s = 0; s < 2; ++s) {
    int fd = open(sysConf[s], O_RDONLY);
    if (fd >= 0) {
      char buf[128];
      ssize_t n = read(fd, buf, sizeof(buf) - 1);
      close(fd);
      if (n > 0) {
        buf[n] = '\0';
        char *start = buf;
        while (*start && isspace((unsigned char)*start)) start++;
        char *end = start + strlen(start);
        while (end > start && isspace((unsigned char)*(end - 1))) {
          *(--end) = '\0';
        }
        if (start[0]) {
          strncpy(outIp, start, outSize - 1);
          outIp[outSize - 1] = '\0';
          return 0;
        }
      }
    }
  }

  return -ENOENT;
}

int pops_load_smb_stack(const char *vcdDir, const char *vmcDir) {
  char modPath[PATH_MAX];
  const char *searchDirs[8];
  int dirCount = 0;

  if (vmcDir && vmcDir[0])
    searchDirs[dirCount++] = vmcDir;

  if (vcdDir && vcdDir[0] && (!vmcDir || strcmp(vcdDir, vmcDir) != 0))
    searchDirs[dirCount++] = vcdDir;

  char vcdIrxDir[PATH_MAX] = {0};
  if (vcdDir && vcdDir[0]) {
    snprintf(vcdIrxDir, sizeof(vcdIrxDir), "%sIRX/", vcdDir);
    searchDirs[dirCount++] = vcdIrxDir;
  }

  searchDirs[dirCount++] = "mc0:/POPSTARTER/";
  searchDirs[dirCount++] = "mc1:/POPSTARTER/";
  searchDirs[dirCount++] = "mc0:/POPS/";
  searchDirs[dirCount++] = "mc1:/POPS/";

  /* 1. DEV9 network device driver */
  static const char *dev9Drivers[] = { "PS2DEV9.IRX", "ps2dev9.irx", "DEV9.IRX", "dev9.irx" };
  int loadedDev9 = 0;
  for (int i = 0; i < 4; ++i) {
    for (int d = 0; d < dirCount; ++d) {
      snprintf(modPath, sizeof(modPath), "%s%s", searchDirs[d], dev9Drivers[i]);
      if (!tryFile(modPath)) {
        DPRINTF("POPS: Loading DEV9 module %s\n", modPath);
        int module = SifLoadModule(modPath, 0, NULL);
        if (module < 0) {
          DPRINTF("POPS: DEV9 load rejected %s (%d)\n", modPath, module);
          continue;
        }
        loadedDev9 = 1;
        break;
      }
    }
    if (loadedDev9) break;
  }

  /* 2. SMAP network adapter driver */
  static const char *smapDrivers[] = { "SMAP.IRX", "smap.irx", "PS2SMAP.IRX", "ps2smap.irx" };
  int loadedSmap = 0;
  for (int i = 0; i < 4; ++i) {
    for (int d = 0; d < dirCount; ++d) {
      snprintf(modPath, sizeof(modPath), "%s%s", searchDirs[d], smapDrivers[i]);
      if (!tryFile(modPath)) {
        DPRINTF("POPS: Loading SMAP module %s\n", modPath);
        int module = SifLoadModule(modPath, 0, NULL);
        if (module < 0) {
          DPRINTF("POPS: SMAP load rejected %s (%d)\n", modPath, module);
          continue;
        }
        loadedSmap = 1;
        break;
      }
    }
    if (loadedSmap) break;
  }

  /* Read IPCONFIG.DAT for static IP arguments */
  char ipConfig[128] = {0};
  pops_read_ipconfig(searchDirs, dirCount, ipConfig, sizeof(ipConfig));
  uint32_t ipArgLen = ipConfig[0] ? (uint32_t)(strlen(ipConfig) + 1) : 0;
  char *ipArgPtr = ipConfig[0] ? ipConfig : NULL;

  /* 3. PS2IP TCP/IP stack driver */
  static const char *ps2ipDrivers[] = { "PS2IP.IRX", "ps2ip.irx" };
  int loadedPs2ip = 0;
  for (int i = 0; i < 2; ++i) {
    for (int d = 0; d < dirCount; ++d) {
      snprintf(modPath, sizeof(modPath), "%s%s", searchDirs[d], ps2ipDrivers[i]);
      if (!tryFile(modPath)) {
        DPRINTF("POPS: Loading PS2IP module %s (args: %s)\n", modPath, ipArgPtr ? ipArgPtr : "none");
        int module = SifLoadModule(modPath, ipArgLen, ipArgPtr);
        if (module < 0) {
          DPRINTF("POPS: PS2IP load rejected %s (%d)\n", modPath, module);
          continue;
        }
        loadedPs2ip = 1;
        break;
      }
    }
    if (loadedPs2ip) break;
  }

  /* 4. SMBMAN SMB protocol client driver */
  static const char *smbmanDrivers[] = { "SMBMAN.IRX", "smbman.irx" };
  int loadedSmbman = 0;
  for (int i = 0; i < 2; ++i) {
    for (int d = 0; d < dirCount; ++d) {
      snprintf(modPath, sizeof(modPath), "%s%s", searchDirs[d], smbmanDrivers[i]);
      if (!tryFile(modPath)) {
        DPRINTF("POPS: Loading SMBMAN module %s\n", modPath);
        int module = SifLoadModule(modPath, 0, NULL);
        if (module < 0) {
          DPRINTF("POPS: SMBMAN load rejected %s (%d)\n", modPath, module);
          continue;
        }
        loadedSmbman = 1;
        break;
      }
    }
    if (loadedSmbman) break;
  }

  /* 5. PS2NETFS network filesystem driver */
  static const char *ps2netfsDrivers[] = { "PS2NETFS.IRX", "ps2netfs.irx" };
  int loadedNetfs = 0;
  for (int i = 0; i < 2; ++i) {
    for (int d = 0; d < dirCount; ++d) {
      snprintf(modPath, sizeof(modPath), "%s%s", searchDirs[d], ps2netfsDrivers[i]);
      if (!tryFile(modPath)) {
        DPRINTF("POPS: Loading PS2NETFS module %s\n", modPath);
        int module = SifLoadModule(modPath, 0, NULL);
        if (module < 0) {
          DPRINTF("POPS: PS2NETFS load rejected %s (%d)\n", modPath, module);
          continue;
        }
        loadedNetfs = 1;
        break;
      }
    }
    if (loadedNetfs) break;
  }

  /* Allow SMB session handshake and share mount to stabilize */
  sleep(1);

  return (loadedNetfs || loadedSmbman) ? 0 : -ENOENT;
}

int pops_load_custom_modules(const char *vcdDir, const char *vmcDir) {
  char modPath[PATH_MAX];
  const char *searchDirs[8];
  int dirCount = 0;

  if (vmcDir && vmcDir[0])
    searchDirs[dirCount++] = vmcDir;

  if (vcdDir && vcdDir[0] && (!vmcDir || strcmp(vcdDir, vmcDir) != 0))
    searchDirs[dirCount++] = vcdDir;

  char vcdIrxDir[PATH_MAX] = {0};
  if (vcdDir && vcdDir[0]) {
    snprintf(vcdIrxDir, sizeof(vcdIrxDir), "%sIRX/", vcdDir);
    searchDirs[dirCount++] = vcdIrxDir;
  }

  searchDirs[dirCount++] = "mc0:/POPSTARTER/";
  searchDirs[dirCount++] = "mc1:/POPSTARTER/";
  searchDirs[dirCount++] = "mc0:/POPS/";
  searchDirs[dirCount++] = "mc1:/POPS/";

  /* 1. Load sequential custom modules: MODULE_0.IRX .. MODULE_9.IRX */
  for (int slot = 0; slot <= 9; ++slot) {
    for (int d = 0; d < dirCount; ++d) {
      snprintf(modPath, sizeof(modPath), "%sMODULE_%d.IRX", searchDirs[d], slot);
      if (!tryFile(modPath)) {
        DPRINTF("POPS: Loading custom module %s\n", modPath);
        int res = SifLoadModule(modPath, 0, NULL);
        DPRINTF("POPS: Module %s loaded (res %d)\n", modPath, res);
        break;
      }
    }
  }

  /* 2. Load named peripheral drivers */
  static const char *peripheralDrivers[] = {
    "USBMOUSE.IRX",
    "USB_MOUSE.IRX",
    "USBKBD.IRX",
    "USBGUN.IRX",
    "GUNCON.IRX",
    "MULTITAP.IRX",
    "DS3.IRX",
    "DS4.IRX",
    "PADMAN.IRX",
    "SIO2MAN.IRX"
  };
  int numDrivers = (int)(sizeof(peripheralDrivers) / sizeof(peripheralDrivers[0]));

  for (int p = 0; p < numDrivers; ++p) {
    for (int d = 0; d < dirCount; ++d) {
      snprintf(modPath, sizeof(modPath), "%s%s", searchDirs[d], peripheralDrivers[p]);
      if (!tryFile(modPath)) {
        DPRINTF("POPS: Loading peripheral driver %s\n", modPath);
        int res = SifLoadModule(modPath, 0, NULL);
        DPRINTF("POPS: Driver %s loaded (res %d)\n", modPath, res);
        break;
      }
    }
  }

  /* 3. Load modules from manifest files: MODULES.TXT / IRX.TXT */
  static const char *manifestNames[] = { "MODULES.TXT", "IRX.TXT" };
  for (int m = 0; m < 2; ++m) {
    for (int d = 0; d < dirCount; ++d) {
      snprintf(modPath, sizeof(modPath), "%s%s", searchDirs[d], manifestNames[m]);
      if (!tryFile(modPath)) {
        DPRINTF("POPS: Reading module manifest %s\n", modPath);
        int fd = open(modPath, O_RDONLY);
        if (fd >= 0) {
          char lineBuf[256];
          int lineIdx = 0;
          char ch;
          while (read(fd, &ch, 1) == 1) {
            if (ch == '\r' || ch == '\n') {
              if (lineIdx > 0) {
                lineBuf[lineIdx] = '\0';
                char *s = lineBuf;
                while (*s && isspace((unsigned char)*s))
                  s++;
                if (*s && *s != '#' && *s != ';') {
                  char target[PATH_MAX];
                  if (strchr(s, ':') || *s == '/' || *s == '\\') {
                    snprintf(target, sizeof(target), "%s", s);
                  } else {
                    snprintf(target, sizeof(target), "%s%s", searchDirs[d], s);
                  }
                  if (!tryFile(target)) {
                    DPRINTF("POPS: Manifest loading %s\n", target);
                    int res = SifLoadModule(target, 0, NULL);
                    DPRINTF("POPS: Manifest loaded %s (res %d)\n", target, res);
                  }
                }
                lineIdx = 0;
              }
            } else if (lineIdx < (int)sizeof(lineBuf) - 1) {
              lineBuf[lineIdx++] = ch;
            }
          }
          if (lineIdx > 0) {
            lineBuf[lineIdx] = '\0';
            char *s = lineBuf;
            while (*s && isspace((unsigned char)*s))
              s++;
            if (*s && *s != '#' && *s != ';') {
              char target[PATH_MAX];
              if (strchr(s, ':') || *s == '/' || *s == '\\') {
                snprintf(target, sizeof(target), "%s", s);
              } else {
                snprintf(target, sizeof(target), "%s%s", searchDirs[d], s);
              }
              if (!tryFile(target)) {
                DPRINTF("POPS: Manifest loading %s\n", target);
                int res = SifLoadModule(target, 0, NULL);
                DPRINTF("POPS: Manifest loaded %s (res %d)\n", target, res);
              }
            }
          }
          close(fd);
        }
      }
    }
  }

  return 0;
}

static int pops_probe_live_storage(void) {
  const char *paths[] = {"pops0:IMAGE.VCD", "pops0:SLOT0.VMC",
                         "pops0:SLOT1.VMC"};
  for (int i = 0; i < 3; ++i) {
    int fd = fileXioOpen(paths[i], i ? FIO_O_RDWR : FIO_O_RDONLY);
    if (fd < 0)
      return fd;
    int status = 0;
    if (i == 0) {
      char check[16] __attribute__((aligned(64)));
      int remaining = sizeof(check);
      /* IOP storage backends may return partial positive reads. Probe
       * actual delivery to EOF/error, keeping the destination aligned. */
      while (remaining > 0) {
        int n = fileXioRead(fd, check, remaining);
        if (n <= 0 || n > remaining) {
          status = n < 0 ? n : -EIO;
          break;
        }
        remaining -= n;
      }
    }
    int closed = fileXioClose(fd);
    if (!status && closed < 0)
      status = closed;
    if (status)
      return status;
  }
  return 0;
}

int launchPOPS(int argc, char *argv[]) {
  if (argc < 1 || !argv || !argv[0] || !argv[0][0]) {
    msg("POPS: Invalid launch arguments\n");
    return -EINVAL;
  }

  const char *vcdPath = argv[0];
  int res;
  const int directXx = pops_is_xx_prefix(vcdPath);
  const int directSb = pops_is_sb_prefix(vcdPath);
  if (directXx || directSb) {
    /* An explicit prefix on the selected target overrides an earlier
     * resolver context, never enabling XX and SB simultaneously. */
    pops_set_active_xx_launch(directXx);
    pops_set_active_sb_launch(directSb);
  }

  DeviceType device = guessDeviceType(vcdPath);

  char resolvedVcd[PATH_MAX];
  strncpy(resolvedVcd, vcdPath, sizeof(resolvedVcd) - 1);
  resolvedVcd[sizeof(resolvedVcd) - 1] = '\0';

  if (device == Device_APA) {
    char *norm = normalizePath(resolvedVcd, Device_APA);
    if (norm) {
      res = initPFS(resolvedVcd, Device_None);
      if (res) {
        msg("POPS: Failed mounting APA game partition: %d\n", res);
        return res;
      }
      strncpy(resolvedVcd, norm, sizeof(resolvedVcd) - 1);
      resolvedVcd[sizeof(resolvedVcd) - 1] = '\0';
    }
  } else {
    char *norm = normalizePath(resolvedVcd, device);
    if (norm) {
      strncpy(resolvedVcd, norm, sizeof(resolvedVcd) - 1);
      resolvedVcd[sizeof(resolvedVcd) - 1] = '\0';
    }
  }

  int isSbLaunch = pops_get_active_sb_launch() || (device == Device_SMB);
  if (isSbLaunch) {
    DPRINTF("POPS: Active SB. launch detected\n");
    pops_load_smb_stack(NULL, NULL);
  }

  vcdPath = resolvedVcd;

  PopsBdmaMode bdmaMode = pops_detect_bdma_mode();
  int useBdma = pops_get_active_xx_launch() && (bdmaMode != POPS_BDMA_NONE);
  if (useBdma) {
    DPRINTF("POPS: Active XX. launch with BDMA detected (mode %d)\n", bdmaMode);
  }

  DPRINTF("POPS: Target disc %s (device %d)\n", vcdPath, device);

  /* Verify target disc existence */
  if (tryFile((char *)vcdPath)) {
    msg("POPS: Cannot open target VCD: %s\n", vcdPath);
    return -ENOENT;
  }

  char popsPath[PATH_MAX] = {0};
  char ioprpPath[PATH_MAX] = {0};
  res = findPopsDependenciesForMode(vcdPath, popsPath, sizeof(popsPath),
                                     ioprpPath, sizeof(ioprpPath), isSbLaunch);
  if (res) {
    if (isSbLaunch)
      msg("POPS: SMB launch requires POPS_IOX.PAK (IOPRP2305A).\n");
    else
      msg("POPS: Missing POPS dependencies\n(POPS.PAK, POPS_IOX.PAK or POPS.ELF+IOPRP252.IMG)\n");
    return -ENOENT;
  }

  DPRINTF("POPS: Using emulator %s\n", popsPath);

  /* Inspect target VCD ISO9660 filesystem for game serial */
  PopsVcdInfo vcdInfo;
  memset(&vcdInfo, 0, sizeof(vcdInfo));
  res = pops_vcd_inspect_path(vcdPath, &vcdInfo);
  /* An absent/nonstandard SYSTEM.CNF does not prove the disc unusable, but
   * a short read or a VCD smaller than its declared sector count does. */
  if (res == -EIO) {
    msg("POPS: VCD read or declared sector extent failed: %s\n", vcdPath);
    return res;
  }
  if (!res && vcdInfo.normalized_serial[0]) {
    DPRINTF("POPS: Detected serial %s (raw %s)\n", vcdInfo.normalized_serial, vcdInfo.raw_serial);
  }

  /* Resolve directory, base name, and game configuration */
  char vcdDir[PATH_MAX] = {0};
  char gameBase[128] = {0};
  char card0Path[PATH_MAX] = {0};
  char card1Path[PATH_MAX] = {0};

  extractDirectory(vcdPath, vcdDir, sizeof(vcdDir));
  extractGameBase(vcdPath, gameBase, sizeof(gameBase));

  /* The config path must never be silently shortened into another title. */
  if (strlen(vcdDir) + strlen(gameBase) + 2 > PATH_MAX) {
    msg("POPS: Game configuration path is too long\n");
    return -ENAMETOOLONG;
  }
  char gameConfigDir[PATH_MAX];
  snprintf(gameConfigDir, sizeof(gameConfigDir), "%s%s/", vcdDir, gameBase);

  PopsConfig cfg;
  pops_config_init(&cfg);
  res = pops_config_discover(&cfg, vcdDir, gameBase);
  if (res) {
    msg("POPS: Cannot load game configuration: %d\n", res);
    return res;
  }
  if (cfg.cheat_count) {
    msg("POPS: Enabled cheats require a resident runtime engine, which is not implemented.\n");
    return -ENOTSUP;
  }

  /* Look up known compatibility modes and LibCrypt bypass */
  const char *matchSerial = vcdInfo.normalized_serial[0] ? vcdInfo.normalized_serial : gameBase;
  const PopsCompatEntry *compat = pops_compat_db_lookup(matchSerial);
  if (compat) {
    DPRINTF("POPS: Matched title in DB: %s (%s), default_modes=0x%02X, libcrypt=%d\n",
            compat->title, compat->serial, compat->default_modes, compat->has_libcrypt);
    if (cfg.compat_modes == 0 && compat->default_modes != 0) {
      cfg.compat_modes = compat->default_modes;
    }
  }

  /* All card candidates below fit within vcdDir + one optional folder +
   * one basename + extension. Reject the whole operation if any may
   * truncate: an abbreviated VMC path could collide with another game's
   * save and must never be used. Account for two longest name components,
   * the folder separator, .VMC[0-1]/SLOT[0-1].VMC and the NUL byte. */
  size_t longestName = strlen(gameBase);
  if (strlen(vcdInfo.normalized_serial) > longestName)
    longestName = strlen(vcdInfo.normalized_serial);
  if (strlen(cfg.vmc_dir) > longestName)
    longestName = strlen(cfg.vmc_dir);
  if (strlen(vcdDir) + 2 * longestName + 16 >= PATH_MAX) {
    msg("POPS: Virtual memory card paths exceed the device path limit\n");
    return -ENAMETOOLONG;
  }

  /* Resolve VMC destination directory */
  char vmcDir[PATH_MAX] = {0};
  if (cfg.vmc_dir[0]) {
    /* VMCDIR is already validated as one relative folder name. */
    snprintf(vmcDir, sizeof(vmcDir), "%s%s/", vcdDir, cfg.vmc_dir);
  } else {
    /* Probe candidate VMC locations:
     * 1. Subfolder <vcdDir>/<gameBase>/ (standard POPStarter convention)
     * 2. Subfolder <vcdDir>/<serial>/
     * 3. Flat in <vcdDir>/
     * 4. Default to subfolder <vcdDir>/<gameBase>/ if no existing saves are present
     */
    char testPath[PATH_MAX];
    int foundVmc = 0;

    /* 1. Try game subfolder <gameBase>/ */
    snprintf(testPath, sizeof(testPath), "%s%s/SLOT0.VMC", vcdDir, gameBase);
    if (!tryFile(testPath)) {
      snprintf(vmcDir, sizeof(vmcDir), "%s%s/", vcdDir, gameBase);
      foundVmc = 1;
    } else {
      snprintf(testPath, sizeof(testPath), "%s%s/%s.VMC0", vcdDir, gameBase, gameBase);
      if (!tryFile(testPath)) {
        snprintf(vmcDir, sizeof(vmcDir), "%s%s/", vcdDir, gameBase);
        foundVmc = 1;
      }
    }

    /* 2. Try serial subfolder <serial>/ */
    if (!foundVmc && vcdInfo.normalized_serial[0]) {
      snprintf(testPath, sizeof(testPath), "%s%s/SLOT0.VMC", vcdDir, vcdInfo.normalized_serial);
      if (!tryFile(testPath)) {
        snprintf(vmcDir, sizeof(vmcDir), "%s%s/", vcdDir, vcdInfo.normalized_serial);
        foundVmc = 1;
      }
    }

    /* 3. Try flat in vcdDir */
    if (!foundVmc) {
      const char *sbase = vcdInfo.normalized_serial[0] ? vcdInfo.normalized_serial : gameBase;
      snprintf(testPath, sizeof(testPath), "%s%s.VMC0", vcdDir, sbase);
      if (!tryFile(testPath)) {
        snprintf(vmcDir, sizeof(vmcDir), "%s", vcdDir);
        foundVmc = 1;
      } else {
        snprintf(testPath, sizeof(testPath), "%sSLOT0.VMC", vcdDir);
        if (!tryFile(testPath)) {
          snprintf(vmcDir, sizeof(vmcDir), "%s", vcdDir);
          foundVmc = 1;
        }
      }
    }

    /* 4. Default to game subfolder */
    if (!foundVmc) {
      snprintf(vmcDir, sizeof(vmcDir), "%s%s/", vcdDir, gameBase);
    }
  }

  const char *vmcBase = vcdInfo.normalized_serial[0] ? vcdInfo.normalized_serial : gameBase;
  char testCard[PATH_MAX];

  /* Resolve card 0 */
  snprintf(testCard, sizeof(testCard), "%sSLOT0.VMC", vmcDir);
  if (!tryFile(testCard)) {
    snprintf(card0Path, sizeof(card0Path), "%s", testCard);
  } else {
    snprintf(testCard, sizeof(testCard), "%s%s.VMC0", vmcDir, vmcBase);
    if (!tryFile(testCard)) {
      snprintf(card0Path, sizeof(card0Path), "%s", testCard);
    } else {
      snprintf(testCard, sizeof(testCard), "%s%s.VMC0", vmcDir, gameBase);
      if (!tryFile(testCard)) {
        snprintf(card0Path, sizeof(card0Path), "%s", testCard);
      } else {
        if (strcmp(vmcDir, vcdDir) != 0) {
          snprintf(card0Path, sizeof(card0Path), "%sSLOT0.VMC", vmcDir);
        } else {
          snprintf(card0Path, sizeof(card0Path), "%s%s.VMC0", vmcDir, vmcBase);
        }
      }
    }
  }

  /* Resolve card 1 */
  snprintf(testCard, sizeof(testCard), "%sSLOT1.VMC", vmcDir);
  if (!tryFile(testCard)) {
    snprintf(card1Path, sizeof(card1Path), "%s", testCard);
  } else {
    snprintf(testCard, sizeof(testCard), "%s%s.VMC1", vmcDir, vmcBase);
    if (!tryFile(testCard)) {
      snprintf(card1Path, sizeof(card1Path), "%s", testCard);
    } else {
      snprintf(testCard, sizeof(testCard), "%s%s.VMC1", vmcDir, gameBase);
      if (!tryFile(testCard)) {
        snprintf(card1Path, sizeof(card1Path), "%s", testCard);
      } else {
        if (strcmp(vmcDir, vcdDir) != 0) {
          snprintf(card1Path, sizeof(card1Path), "%sSLOT1.VMC", vmcDir);
        } else {
          snprintf(card1Path, sizeof(card1Path), "%s%s.VMC1", vmcDir, vmcBase);
        }
      }
    }
  }

  /* Map multi-disc paths from DISCS.TXT */
  char discPaths[POPS_MAX_DISCS][PATH_MAX];
  const char *discArgs[POPS_MAX_DISCS] = { vcdPath, NULL, NULL, NULL };
  strncpy(discPaths[0], vcdPath, sizeof(discPaths[0]) - 1);

  if (cfg.disc_count > 1) {
    for (int d = 1; d < cfg.disc_count && d < POPS_MAX_DISCS; ++d) {
      int length;
      if (strchr(cfg.discs[d], ':') || cfg.discs[d][0] == '/' || cfg.discs[d][0] == '\\') {
        length = snprintf(discPaths[d], sizeof(discPaths[d]), "%s", cfg.discs[d]);
      } else {
        length = snprintf(discPaths[d], sizeof(discPaths[d]), "%s%s", vcdDir, cfg.discs[d]);
      }
      if (length < 0 || (size_t)length >= sizeof(discPaths[d])) {
        msg("POPS: Disc %d path is too long\n", d + 1);
        return -ENAMETOOLONG;
      }
      if (tryFile(discPaths[d])) {
        msg("POPS: Disc %d not readable: %s\n", d + 1, discPaths[d]);
        return -ENOENT;
      }
      discArgs[d] = discPaths[d];
      DPRINTF("POPS: Disc %d mapped to %s\n", d + 1, discPaths[d]);
    }
  }

  /* Reject invalid disc/save backend paths before staging, creating cards or
   * triggering the irreversible external IOP reboot. */
  /* Format proxy arguments for popfs */
  char proxyArgs[POPS_PROXY_ARGS_MAX];
  int argLen = pops_format_proxy_args(proxyArgs, sizeof(proxyArgs),
                                      discArgs[0], card0Path, card1Path,
                                      discArgs[1], discArgs[2], discArgs[3]);
  if (argLen <= 0) {
    msg("POPS: Failed formatting proxy arguments\n");
    return -EINVAL;
  }

  PopsBootPlan plan;
  size_t rawSize = 0;
  const void *stagedCore = POPS_STAGE_BUF;
  const void *rebootIop = NULL;

  const char *dot = strrchr(popsPath, '.');
  int isPak = dot && !strcasecmp(dot, ".pak");

  if (isPak) {
    res = readFullFile(popsPath, POPS_LOAD_RAW_BUF, POPS_LOAD_MAX_SIZE, &rawSize);
    if (res) {
      msg("POPS: Failed reading %s: %d\n", popsPath, res);
      return res;
    }

    size_t decodedSize = 0;
    res = pops_pak_decode(POPS_LOAD_RAW_BUF, rawSize, POPS_STAGE_BUF,
                          POPS_STAGING_CAPACITY, &decodedSize);
    if (res) {
      msg("POPS: Failed decoding %s: %d\n", popsPath, res);
      return res;
    }

    res = pops_boot_plan_pak(POPS_STAGE_BUF, decodedSize, &plan);
    if (res) {
      msg("POPS: Invalid PAK package %s: %d\n", popsPath, res);
      return res;
    }

    rebootIop = (const void *)((uintptr_t)POPS_STAGE_BUF + plan.iop_offset);
  } else {
    /* Loose POPS.ELF + IOPRP252.IMG */
    size_t elfSize = 0, iopSize = 0;
    res = readFullFile(popsPath, POPS_LOAD_RAW_BUF, POPS_LOAD_MAX_SIZE, &elfSize);
    if (res) {
      msg("POPS: Failed reading %s: %d\n", popsPath, res);
      return res;
    }
    res = readFullFile(ioprpPath, POPS_LOAD_IOP_BUF, POPS_IOP_MAX_SIZE, &iopSize);
    if (res) {
      msg("POPS: Failed reading %s: %d\n", ioprpPath, res);
      return res;
    }

    res = pops_boot_plan_elf(POPS_LOAD_RAW_BUF, elfSize, POPS_LOAD_IOP_BUF, iopSize, &plan);
    if (res) {
      msg("POPS: Invalid POPS.ELF or IOPRP: %d\n", res);
      return res;
    }

    /* Stage ELF load segments into staging buffer */
    PopsBootBuffers buffers;
    buffers.ram_base = 0x100000;
    buffers.ram = (void *)((uintptr_t)POPS_STAGE_BUF - (POPS_CORE_ADDR - 0x100000));
    buffers.ram_size = plan.bss_address + plan.bss_size - 0x100000;
    buffers.scratchpad = (void *)0x01f80000;
    buffers.scratchpad_size = plan.scratchpad_size;
    /* The translated low-RAM/core/BSS staging span ends at 0x01665940.
     * Keep both IOP source and destination above that span and below raw ELF
     * input at 0x01800000. Neither may alias RAM cleared by boot_stage_elf. */
    buffers.iop = POPS_STAGE_IOP_BUF;
    buffers.iop_size = POPS_IOP_MAX_SIZE;

    res = pops_boot_stage_elf(POPS_LOAD_RAW_BUF, elfSize, POPS_LOAD_IOP_BUF,
                              iopSize, &buffers);
    if (res) {
      msg("POPS: Failed staging loose boot buffers: %d\n", res);
      return res;
    }

    rebootIop = buffers.iop;
  }

  /* This is a read-only diagnostic, not a PFS wrapper: EE paths in the
   * verified core are already patched to pops:, while original IOPCD may
   * independently reference legacy ioman/pfs0:. Expose which modules the
   * selected ROMDIR actually contains to narrow the hardware trace. */
  {
    size_t moduleOffset = 0, moduleSize = 0;
    int found = pops_iop_image_find_module(rebootIop, plan.iop_size, "IOPCD",
                                           &moduleOffset, &moduleSize);
    if (!found) {
      uint32_t ioStrings = 0;
      int scan = pops_iop_image_probe_io_strings(rebootIop, plan.iop_size,
                                                 "IOPCD", &ioStrings);
      DPRINTF("POPS: IOPRP IOPCD ROMDIR module offset=%u size=%u\n",
              (unsigned)moduleOffset, (unsigned)moduleSize);
      if (!scan)
        DPRINTF("POPS: IOPCD bounded ASCII hints: ioman=%d iomanX=%d pfs=%d pops=%d (not import proof)\n",
                !!(ioStrings & POPS_IOSTRING_IOMAN),
                !!(ioStrings & POPS_IOSTRING_IOMANX),
                !!(ioStrings & POPS_IOSTRING_PFS),
                !!(ioStrings & POPS_IOSTRING_POPS));
      uint32_t imports = 0;
      int importStatus = pops_iop_image_probe_io_imports(
          rebootIop, plan.iop_size, "IOPCD", &imports);
      if (!importStatus)
        DPRINTF("POPS: IOPCD IRX import tables: legacy-ioman=%d iomanX=%d (execution unverified)\n",
                !!(imports & POPS_IOIMPORT_IOMAN),
                !!(imports & POPS_IOIMPORT_IOMANX));
    } else
      DPRINTF("POPS: No standalone IOPCD in selected IOPRP (%d); EE embedded module may load it\n", found);
  }

  /* Verify staging memory layout */
  res = pops_bootstrap_verify_layout(POPS_STAGING_BASE, plan.core_size + plan.iop_size, &plan);
  if (res) {
    msg("POPS: Staging layout verification failed: %d\n", res);
    return res;
  }

  /* Stage all core patches into staging core */
  res = pops_core_patches_stage(POPS_CORE_ADDR, (void *)stagedCore, plan.core_size, POPS_CORE_ALL);
  if (res) {
    msg("POPS: Core patch verification failed: %d\n", res);
    return res;
  }

  /* Apply compatibility modes and user directive patches */
  res = pops_apply_all_config_patches((void *)stagedCore, plan.core_size, &cfg);
  if (res) {
    msg("POPS: Applying config patches failed: %d\n", res);
    return res;
  }

  /* Apply LibCrypt bypass if title requires it and mode 6 is not already set */
  if (compat && compat->has_libcrypt && !(cfg.compat_modes & (1 << 5))) {
    DPRINTF("POPS: Applying LibCrypt bypass for %s\n", compat->serial);
    pops_apply_libcrypt_bypass((void *)stagedCore, plan.core_size);
  }

  /* Apply title-specific database patch if registered */
  if (compat && compat->patch_offset >= POPS_CORE_ADDR &&
      compat->patch_offset + 4 <= POPS_CORE_ADDR + plan.core_size) {
    uint32_t off = compat->patch_offset - POPS_CORE_ADDR;
    *(uint32_t *)((uint8_t *)stagedCore + off) = compat->patch_val;
    DPRINTF("POPS: Applied DB title patch at 0x%08X = 0x%08X\n",
            compat->patch_offset, compat->patch_val);
  }

  /* Save redirection must not redirect title fixes. */
  char trojanPath[PATH_MAX];
  const char *trojanDirs[6];
  int trojanDirCount = 0;
  if (vcdDir && vcdDir[0])
    trojanDirs[trojanDirCount++] = vcdDir;
  trojanDirs[trojanDirCount++] = gameConfigDir;
  trojanDirs[trojanDirCount++] = "mc0:/POPSTARTER/";
  trojanDirs[trojanDirCount++] = "mc1:/POPSTARTER/";
  trojanDirs[trojanDirCount++] = "mc0:/POPS/";
  trojanDirs[trojanDirCount++] = "mc1:/POPS/";

  for (int td = 0; td < trojanDirCount; ++td) {
    for (int slot = 0; slot <= 9; ++slot) {
      snprintf(trojanPath, sizeof(trojanPath), "%sTROJAN_%d.BIN", trojanDirs[td], slot);
      if (!tryFile(trojanPath)) {
        size_t trojanSize = 0;
        void *trojanBuf = (void *)0x01f00000;
        PopsContainerPlan trojanPlan;
        uint32_t expected[3] = {0};
        size_t guardWords;

        res = readFullFile(trojanPath, trojanBuf, 0x100000, &trojanSize);
        if (res) {
          msg("POPS: Cannot read TROJAN %s: %d\n", trojanPath, res);
          return res;
        }
        res = pops_container_plan(trojanBuf, trojanSize, POPS_CORE_ADDR,
                                  plan.core_size, &trojanPlan);
        if (res || trojanPlan.container.kind != POPS_CONTAINER_TROJAN ||
            trojanPlan.container.slot != slot) {
          msg("POPS: Invalid TROJAN slot/contents in %s\n", trojanPath);
          return res ? res : -EINVAL;
        }

        /* The stager requires two guard words for ordinary 4/8-byte hooks,
         * three only for 12-byte hooks. Passing three to every TROJAN caused
         * ordinary patches to be silently rejected and falsely logged. */
        guardWords = trojanPlan.hook_size > 8 ? 3 : 2;
        memcpy(expected, (const uint8_t *)stagedCore + trojanPlan.hook_offset,
               guardWords * sizeof(expected[0]));
        res = pops_container_stage(trojanBuf, trojanSize, POPS_CORE_ADDR,
                                   (void *)stagedCore, plan.core_size,
                                   expected, guardWords);
        if (res) {
          msg("POPS: TROJAN stage rejected %s: %d\n", trojanPath, res);
          return res;
        }
        DPRINTF("POPS: Applied %s\n", trojanPath);
      }
    }
  }

  /* Check the unreturnable trampoline before touching save images or
   * rebooting the IOP. Keep the actual low-RAM argument write immediately
   * before handoff, because it must remain valid through the foreign reset. */
  PopsTrampolineArgs handoffCheck;
  res = pops_trampoline_args_init(&handoffCheck, &plan,
                                   (uint32_t)(uintptr_t)stagedCore,
                                   "pops0:IMAGE.VCD");
  if (res) {
    msg("POPS: Trampoline argument preflight failed: %d\n", res);
    return res;
  }
  size_t handoffCodeSize = (size_t)(pops_trampoline_code_end - pops_trampoline_code);
  if (!handoffCodeSize || handoffCodeSize > 0x180) {
    msg("POPS: Trampoline code size is invalid before reboot\n");
    return -EINVAL;
  }

  /* Prepare card images only after external dependency identity and every
   * selected core/TROJAN patch has been validated. Failed preflight never
   * creates empty saves or touches existing cards. */
  /* The initial APA mount was deliberately read-only for inspection.
   * Newly created SLOT images require write access *before* the external
   * IOP reset (the later writable remount alone is too late). */
  if (device == Device_APA) {
    res = remountPFSWritable((char *)argv[0]);
    if (res) {
      msg("POPS: APA remount for new VMCs failed: %d\n", res);
      return res;
    }
  }

  /* Ensure backing save images exist before handoff */
  res = pops_vmc_ensure(card0Path);
  if (res) {
    msg("POPS: Cannot prepare card %s: %d\n", card0Path, res);
    return res;
  }
  res = pops_vmc_ensure(card1Path);
  if (res) {
    msg("POPS: Cannot prepare card %s: %d\n", card1Path, res);
    return res;
  }

  /* Reboot IOP with verified external IOPRP image */
  DPRINTF("POPS: Rebooting IOP with external image (%u bytes)\n", plan.iop_size);
  res = SifIopRebootBuffer((void *)rebootIop, plan.iop_size);
  /* PS2SDK reports success as a positive value and can return -1 on
   * failed ROMDRV staging. The old !res check treated -1 as success and
   * then waited for a reboot that never actually completed. */
  if (res <= 0) {
    DPRINTF("POPS: Plain IOP reboot failed (%d), trying encrypted path\n", res);
    res = SifIopRebootBufferEncrypted((void *)rebootIop, plan.iop_size);
    if (res <= 0) {
      msg("POPS: IOP reboot failed (plain/encrypted)\n");
      return -EIO;
    }
  }
  while (!SifIopSync()) {}

  /* Initialize post-reboot storage and popfs */
  res = initPopsServices(device, stagedCore, plan.core_size, proxyArgs, (uint32_t)argLen);
  if (res) {
    msg("POPS: Failed initializing services: %d\n", res);
    return res;
  }

  /* If this is an XX. launch with BDMA present, load and utilize the BDMA modules */
  if (useBdma) {
    DPRINTF("POPS: Loading BDMA modules for XX. launch\n");
    int loadedBdma = pops_load_bdma_drivers(vcdDir, vmcDir, bdmaMode);
    DPRINTF("POPS: External BDMA roles successfully installed: %d\n", loadedBdma);
    (void)loadedBdma;
  }

  /* If this is an SB. launch or SMB device, load the SMB network stack */
  if (isSbLaunch) {
    DPRINTF("POPS: Loading SMB stack for SB. launch\n");
    res = pops_load_smb_stack(vcdDir, vmcDir);
    if (res) {
      msg("POPS: Required SMB driver stack unavailable after reboot: %d\n", res);
      return res;
    }
  }

  /* Load user-supplied custom IRX modules and peripheral drivers */
  pops_load_custom_modules(vcdDir, vmcDir);

  /* Apply USB delay if configured */
  if (cfg.usb_delay > 0) {
    DPRINTF("POPS: USB delay requested: %u seconds\n", cfg.usb_delay);
    sleep(cfg.usb_delay);
  }

  /* IOP reboot invalidates the previous APA mount. Mount read/write
   * before checking virtual saves; a read-only mount would make every VMC
   * write fail despite the images existing on disk. Other ELF loads stay RO. */
  if (device == Device_APA) {
    res = mountPFSWritable((char *)argv[0]);
    if (res) {
      msg("POPS: Post-reboot APA remount failed: %d\n", res);
      return res;
    }
  }

  /* Check the real IOP storage route before handing off to Sony POPS. */
  res = pops_probe_live_storage();
  if (res) {
    msg("POPS: Post-reboot disc/VMC check failed: %d\n", res);
    return res;
  }

  /* Forward verified LibCrypt magic key to popfs for Subchannel Q emulation */
  if (compat && compat->has_libcrypt && compat->libcrypt_key != 0) {
    uint16_t lkey = compat->libcrypt_key;
    res = fileXioDevctl("pops:", 0x05 /* POPS_DEVCTL_SET_LIBCRYPT */,
                        &lkey, sizeof(lkey), NULL, 0);
    if (res < 0) {
      msg("POPS: Failed to install required LibCrypt key: %d\n", res);
      return res;
    }
    DPRINTF("POPS: Configured popfs LibCrypt subchannel emulation (key 0x%04X)\n", lkey);
  }

  /* Set up low-memory execution trampoline below 1 MiB */
  PopsTrampolineArgs *targs = (PopsTrampolineArgs *)POPS_TRAMPOLINE_ARGS;
  res = pops_trampoline_args_init(targs, &plan, (uint32_t)(uintptr_t)stagedCore, "pops0:IMAGE.VCD");
  if (res) {
    msg("POPS: Trampoline setup failed: %d\n", res);
    return res;
  }

  size_t trampolineCodeSize = (size_t)(pops_trampoline_code_end - pops_trampoline_code);
  if (trampolineCodeSize == 0 || trampolineCodeSize > 0x180) {
    msg("POPS: Invalid trampoline code size\n");
    return -EINVAL;
  }

  memcpy((void *)POPS_TRAMPOLINE_ADDR, pops_trampoline_code, trampolineCodeSize);

  FlushCache(0);
  FlushCache(2);

  DPRINTF("POPS: Transferring control to trampoline at 0x%08X\n", (uint32_t)POPS_TRAMPOLINE_ADDR);

  /* Execute trampoline below 1 MiB, which stages core, clears RAM, and enters POPS */
  ((void (*)(void *))POPS_TRAMPOLINE_ADDR)((void *)POPS_TRAMPOLINE_ARGS);

  return 0;
}
