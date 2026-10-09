#include "handler_pops.h"
#include "common.h"
#include "dprintf.h"
#include "init.h"
#include "pops_external.h"
#include "pops_bootstrap.h"
#include "pops_vcd.h"
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
#define POPS_LOAD_IOP_BUF   ((void *)0x01400000)
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

int findPopsDependencies(const char *vcdPath, char *popsPath, size_t popsPathSize,
                         char *ioprpPath, size_t ioprpPathSize) {
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

static int ensureVmcFile(const char *path) {
  int fd = open(path, O_RDONLY);
  if (fd >= 0) {
    off_t sz = lseek(fd, 0, SEEK_END);
    close(fd);
    if (sz >= 131072)
      return 0;
  }

  /* Ensure parent directory exists before creating card image */
  char dir[PATH_MAX];
  extractDirectory(path, dir, sizeof(dir));
  if (dir[0]) {
    size_t dlen = strlen(dir);
    if (dlen > 1 && (dir[dlen - 1] == '/' || dir[dlen - 1] == '\\'))
      dir[dlen - 1] = '\0';
    mkdir(dir, 0777);
  }

  /* Create formatted 128 KiB standard PS1 Memory Card image */
  fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
  if (fd < 0)
    return fd;

  uint8_t frame[128] = {0};
  frame[0] = 0x4D; /* 'M' */
  frame[1] = 0x43; /* 'C' */
  frame[127] = 0x0E; /* XOR checksum: 0x4D ^ 0x43 */

  if (write(fd, frame, sizeof(frame)) != (ssize_t)sizeof(frame)) {
    close(fd);
    return -EIO;
  }

  memset(frame, 0, sizeof(frame));
  for (int i = 1; i < 1024; ++i) {
    if (write(fd, frame, sizeof(frame)) != (ssize_t)sizeof(frame)) {
      close(fd);
      return -EIO;
    }
  }

  close(fd);
  return 0;
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

int launchPOPS(int argc, char *argv[]) {
  if (argc < 1 || !argv || !argv[0] || !argv[0][0]) {
    msg("POPS: Invalid launch arguments\n");
    return -EINVAL;
  }

  const char *vcdPath = argv[0];
  DeviceType device = guessDeviceType(vcdPath);

  DPRINTF("POPS: Target disc %s (device %d)\n", vcdPath, device);

  /* Verify target disc existence */
  if (tryFile((char *)vcdPath)) {
    msg("POPS: Cannot open target VCD: %s\n", vcdPath);
    return -ENOENT;
  }

  char popsPath[PATH_MAX] = {0};
  char ioprpPath[PATH_MAX] = {0};
  int res = findPopsDependencies(vcdPath, popsPath, sizeof(popsPath),
                                 ioprpPath, sizeof(ioprpPath));
  if (res) {
    msg("POPS: Missing POPS dependencies\n(POPS.PAK, POPS_IOX.PAK or POPS.ELF+IOPRP252.IMG)\n");
    return -ENOENT;
  }

  DPRINTF("POPS: Using emulator %s\n", popsPath);

  /* Inspect target VCD ISO9660 filesystem for game serial */
  PopsVcdInfo vcdInfo;
  memset(&vcdInfo, 0, sizeof(vcdInfo));
  if (pops_vcd_inspect_path(vcdPath, &vcdInfo) == 0 && vcdInfo.normalized_serial[0]) {
    DPRINTF("POPS: Detected serial %s (raw %s)\n", vcdInfo.normalized_serial, vcdInfo.raw_serial);
  }

  /* Resolve directory, base name, and game configuration */
  char vcdDir[PATH_MAX] = {0};
  char gameBase[128] = {0};
  char card0Path[PATH_MAX] = {0};
  char card1Path[PATH_MAX] = {0};

  extractDirectory(vcdPath, vcdDir, sizeof(vcdDir));
  extractGameBase(vcdPath, gameBase, sizeof(gameBase));

  PopsConfig cfg;
  pops_config_init(&cfg);
  pops_config_discover(&cfg, vcdDir, gameBase);

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

  /* Resolve VMC destination directory */
  char vmcDir[PATH_MAX] = {0};
  if (cfg.vmc_dir[0]) {
    if (strchr(cfg.vmc_dir, ':')) {
      snprintf(vmcDir, sizeof(vmcDir), "%.800s", cfg.vmc_dir);
    } else {
      snprintf(vmcDir, sizeof(vmcDir), "%.700s%.128s/", vcdDir, cfg.vmc_dir);
    }
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
        snprintf(vmcDir, sizeof(vmcDir), "%.800s", vcdDir);
        foundVmc = 1;
      } else {
        snprintf(testPath, sizeof(testPath), "%sSLOT0.VMC", vcdDir);
        if (!tryFile(testPath)) {
          snprintf(vmcDir, sizeof(vmcDir), "%.800s", vcdDir);
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

  /* Ensure backing save images exist before handoff */
  ensureVmcFile(card0Path);
  ensureVmcFile(card1Path);

  /* Map multi-disc paths from DISCS.TXT */
  char discPaths[POPS_MAX_DISCS][PATH_MAX];
  const char *discArgs[POPS_MAX_DISCS] = { vcdPath, NULL, NULL, NULL };
  strncpy(discPaths[0], vcdPath, sizeof(discPaths[0]) - 1);

  if (cfg.disc_count > 1) {
    for (int d = 1; d < cfg.disc_count && d < POPS_MAX_DISCS; ++d) {
      if (strchr(cfg.discs[d], ':') || cfg.discs[d][0] == '/' || cfg.discs[d][0] == '\\') {
        snprintf(discPaths[d], sizeof(discPaths[d]), "%s", cfg.discs[d]);
      } else {
        snprintf(discPaths[d], sizeof(discPaths[d]), "%s%s", vcdDir, cfg.discs[d]);
      }
      discArgs[d] = discPaths[d];
      DPRINTF("POPS: Disc %d mapped to %s\n", d + 1, discPaths[d]);
    }
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
    res = readFullFile(ioprpPath, POPS_LOAD_IOP_BUF, POPS_LOAD_MAX_SIZE, &iopSize);
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
    buffers.iop = (void *)((uintptr_t)POPS_STAGE_BUF + plan.core_size);
    buffers.iop_size = plan.iop_size;

    res = pops_boot_stage_elf(POPS_LOAD_RAW_BUF, elfSize, POPS_LOAD_IOP_BUF,
                              iopSize, &buffers);
    if (res) {
      msg("POPS: Failed staging loose boot buffers: %d\n", res);
      return res;
    }

    rebootIop = buffers.iop;
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

  /* Check for game TROJAN_0..9 fixes in game, VMC, and memory card directories */
  char trojanPath[PATH_MAX];
  const char *trojanDirs[6];
  int trojanDirCount = 0;
  if (vcdDir && vcdDir[0])
    trojanDirs[trojanDirCount++] = vcdDir;
  if (vmcDir && vmcDir[0] && (!vcdDir || strcmp(vcdDir, vmcDir) != 0))
    trojanDirs[trojanDirCount++] = vmcDir;
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
        if (!readFullFile(trojanPath, trojanBuf, 0x100000, &trojanSize)) {
          PopsContainer trojanCont;
          if (!pops_container_inspect(trojanBuf, trojanSize, &trojanCont) &&
              trojanCont.kind == POPS_CONTAINER_TROJAN) {
            uint32_t expected[3] = {0};
            /* Read expected hook words from staged core */
            if (trojanCont.hook >= POPS_CORE_ADDR &&
                trojanCont.hook + 12 <= POPS_CORE_ADDR + plan.core_size) {
              uint32_t hookOff = trojanCont.hook - POPS_CORE_ADDR;
              memcpy(expected, (const char *)stagedCore + hookOff, sizeof(expected));
              pops_container_stage(trojanBuf, trojanSize, POPS_CORE_ADDR,
                                   (void *)stagedCore, plan.core_size, expected, 3);
              DPRINTF("POPS: Applied %s\n", trojanPath);
            }
          }
        }
      }
    }
  }

  /* Stage GameShark cheats to guest PS1 RAM (delayed if $SAFEMODE is active) */
  if (cfg.cheat_count > 0 && !cfg.safe_mode) {
    DPRINTF("POPS: Staging %u GameShark cheats to guest PS1 RAM\n", cfg.cheat_count);
    pops_apply_cheats((void *)0x01000000, cfg.cheats, cfg.cheat_count);
  } else if (cfg.cheat_count > 0 && cfg.safe_mode) {
    DPRINTF("POPS: Safe mode active: postponing initial RAM cheat staging\n");
  }

  /* Reboot IOP with verified external IOPRP image */
  DPRINTF("POPS: Rebooting IOP with external image (%u bytes)\n", plan.iop_size);
  res = SifIopRebootBuffer((void *)rebootIop, plan.iop_size);
  if (!res && !(res = SifIopRebootBufferEncrypted((void *)rebootIop, plan.iop_size))) {
    msg("POPS: IOP reboot failed\n");
    return -EIO;
  }
  while (!SifIopSync()) {}

  /* Format proxy arguments for popfs */
  char proxyArgs[POPS_PROXY_ARGS_MAX];
  int argLen = pops_format_proxy_args(proxyArgs, sizeof(proxyArgs),
                                      discArgs[0], card0Path, card1Path,
                                      discArgs[1], discArgs[2], discArgs[3]);
  if (argLen <= 0) {
    msg("POPS: Failed formatting proxy arguments\n");
    return -EINVAL;
  }

  /* Initialize post-reboot storage and popfs */
  res = initPopsServices(device, stagedCore, plan.core_size, proxyArgs, (uint32_t)argLen);
  if (res) {
    msg("POPS: Failed initializing services: %d\n", res);
    return res;
  }

  /* Load user-supplied custom IRX modules and peripheral drivers */
  pops_load_custom_modules(vcdDir, vmcDir);

  /* Apply USB delay if configured */
  if (cfg.usb_delay > 0) {
    DPRINTF("POPS: USB delay requested: %u seconds\n", cfg.usb_delay);
    sleep(cfg.usb_delay);
  }

  /* Forward verified LibCrypt magic key to popfs for Subchannel Q emulation */
  if (compat && compat->has_libcrypt && compat->libcrypt_key != 0) {
    uint16_t lkey = compat->libcrypt_key;
    fileXioDevctl("pops:", 0x05 /* POPS_DEVCTL_SET_LIBCRYPT */, &lkey, sizeof(lkey), NULL, 0);
    DPRINTF("POPS: Configured popfs LibCrypt subchannel emulation (key 0x%04X)\n", lkey);
  }

  if (device == Device_APA)
    mountPFS((char *)vcdPath);

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
