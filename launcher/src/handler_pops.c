#include "handler_pops.h"
#include "launch_args.h"
#include "common.h"
#include "dprintf.h"
#include "init.h"
#include "handler_smb.h"
#include "pops_external.h"
#include "pops_bootstrap.h"
#include "pops_vcd.h"
#include "pops_vmc.h"
#include "pops_config.h"
#include "pops_compat_db.h"
#include "pops_modes_patches.h"
#include "pops_read_trace.h"
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
  if (fd < 0) {
    int result = errno ? -errno : -EIO;
    DPRINTF("POPS_READ_FAIL stage=open result=%d path=%s\n", result, path);
    return result;
  }

  off_t sz = lseek(fd, 0, SEEK_END);
  DPRINTF("POPS_READ size_low=%u size_high=%u capacity=%u path=%s\n",
          (unsigned)(uint64_t)sz, (unsigned)((uint64_t)sz >> 32),
          (unsigned)max_size, path);
  if (sz <= 0 || (size_t)sz > max_size) {
    int result = sz < 0 ? (errno ? -errno : -EIO) : -EINVAL;
    DPRINTF("POPS_READ_FAIL stage=size result=%d\n", result);
    close(fd);
    return result;
  }
  off_t position = lseek(fd, 0, SEEK_SET);
  if (position != 0) {
    int result = position < 0 && errno ? -errno : -EIO;
    DPRINTF("POPS_READ_FAIL stage=rewind result=%d position_low=%u position_high=%u\n",
            result, (unsigned)(uint64_t)position,
            (unsigned)((uint64_t)position >> 32));
    close(fd);
    return result;
  }

  size_t total = 0;
  while (total < (size_t)sz) {
    size_t chunk = (size_t)sz - total;
    if (chunk > 65536)
      chunk = 65536;
    ssize_t n = read(fd, (char *)buffer + total, chunk);
    if (n <= 0 || (size_t)n > chunk) {
      int result = n < 0 && errno ? -errno : -EIO;
      DPRINTF("POPS_READ_FAIL stage=read result=%d offset=%u requested=%u returned=%d\n",
              result, (unsigned)total, (unsigned)chunk, (int)n);
      close(fd);
      return result;
    }
    total += (size_t)n;
  }
  /* PS2SDK libcglue preserves nonnegative driver close return values. */
  int closed = close(fd);
  if (closed < 0) {
    int result = errno ? -errno : -EIO;
    DPRINTF("POPS_READ_FAIL stage=close result=%d returned=%d errno=%d bytes=%u\n",
            result, closed, errno, (unsigned)total);
    return result;
  }
  DPRINTF("POPS_READ close_result=%d bytes=%u\n", closed, (unsigned)total);
  DPRINTF("POPS_READ complete bytes=%u\n", (unsigned)total);

  if (out_size)
    *out_size = total;
  return 0;
}

/* A failed dependency remains fatal. A trace-only second read compares the
 * independent fileXio RPC route; its bytes must never authorize a handoff. */
static int readPopsDependency(const char *path, void *buffer, size_t max_size,
                               size_t *out_size) {
  int result = readFullFile(path, buffer, max_size, out_size);
#ifdef LAUNCHER_BOOT_TRACE
  if (result) {
    DPRINTF("POPS_READ_COMPARE original_result=%d\n", result);
    pops_read_filexio_trace(path, buffer, max_size);
    DPRINTF("POPS_READ_COMPARE original_result=%d retained; Sony_entry_not_executed=1\n", result);
  }
#endif
  return result;
}

/* The archived MAIN calls root TROJAN, root PATCH, title TROJAN, title PATCH
 * (0x876d6c/0x876e00/0x877078/0x877118). Slot order is 0..9 in both loaders.
 * These are explicit external fix files, never files from VMCDIR redirection.
 * The staged executable is discarded by the caller on any failure. */
static int pops_stage_fix_files(void *stagedCore, size_t coreSize,
                                 const char *vcdDir, const char *titleDir,
                                 uint8_t initialModes) {
  PopsFixContext context;
  int result = pops_fix_context_init(&context, stagedCore, coreSize, initialModes);
  if (result)
    return result;
  const char *dirs[] = {vcdDir, titleDir};
  for (unsigned scope = 0; scope < 2; ++scope) {
    for (unsigned kind = 0; kind < 2; ++kind) {
      for (unsigned slot = 0; slot < 10; ++slot) {
        char path[PATH_MAX];
        size_t size = 0;
        void *buffer = (void *)0x01f00000;
        int length = snprintf(path, sizeof(path), "%s%s_%u.BIN", dirs[scope],
                                kind ? "PATCH" : "TROJAN", slot);
        if (length < 0 || (size_t)length >= sizeof(path))
          return -ENAMETOOLONG;
        result = readFullFile(path, buffer, 0x100000, &size);
        if (result == -ENOENT)
          continue;
        if (!result)
          result = pops_fix_stage(&context, stagedCore, coreSize, buffer, size,
                                   slot, !kind);
        if (result) {
          msg("POPS: Fix file rejected %s (%d)\n", path, result);
          return result;
        }
        DPRINTF("POPS: Applied %s\n", path);
      }
    }
  }
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

/* The embedded stack is owned by init.c and reconnected after every reset.
 * These arguments remain for callers; bootstrap files must be on a card. */
int pops_load_smb_stack(const char *vcdDir, const char *vmcDir) {
  (void)vcdDir; (void)vmcDir;
#ifdef SMB
  return launcher_smb_connect();
#else
  return -ENODEV;
#endif
}

/* Explicit manifest lines must not be silently shortened into another
 * IRX filename. Keep absent optional entries nonfatal for compatibility. */
static int pops_manifest_load_line(char *line, const char *directory) {
  char path[PATH_MAX];
  char *name = line;
  while (*name && isspace((unsigned char)*name)) ++name;
  char *end = name + strlen(name);
  while (end > name && isspace((unsigned char)end[-1])) *--end = '\0';
  if (!*name || *name == '#' || *name == ';')
    return 0;
  int length;
  if (strchr(name, ':') || name[0] == '/' || name[0] == '\\')
    length = snprintf(path, sizeof(path), "%s", name);
  else
    length = snprintf(path, sizeof(path), "%s%s", directory, name);
  if (length < 0 || (size_t)length >= sizeof(path))
    return -ENAMETOOLONG;
  if (!tryFile(path)) {
    int module = SifLoadModule(path, 0, NULL);
    if (module < 0)
      DPRINTF("POPS: Optional manifest IRX %s failed to start (%d)\n", path, module);
  }
  return 0;
}

/* One bounded parser for both MODULES.TXT and IRX.TXT. */
static int pops_manifest_load_file(const char *path, const char *directory) {
  int fd = open(path, O_RDONLY);
  if (fd < 0)
    return fd;
  char line[256], ch;
  size_t used = 0;
  ssize_t n = 0;
  int error = 0;
  while ((n = read(fd, &ch, 1)) == 1) {
    if (ch == '\r' || ch == '\n') {
      if (used) {
        line[used] = '\0';
        error = pops_manifest_load_line(line, directory);
        if (error)
          break;
        used = 0;
      }
    } else {
      if (used == sizeof(line) - 1) {
        error = -EOVERFLOW;
        break;
      }
      line[used++] = ch;
    }
  }
  if (!error && n < 0)
    error = -EIO;
  if (!error && used) {
    line[used] = '\0';
    error = pops_manifest_load_line(line, directory);
  }
  if (close(fd) < 0 && !error)
    error = -EIO;
  return error;
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
    int length = snprintf(vcdIrxDir, sizeof(vcdIrxDir), "%sIRX/", vcdDir);
    if (length < 0 || (size_t)length >= sizeof(vcdIrxDir))
      return -ENAMETOOLONG;
    searchDirs[dirCount++] = vcdIrxDir;
  }

  searchDirs[dirCount++] = "mc0:/POPSTARTER/";
  searchDirs[dirCount++] = "mc1:/POPSTARTER/";
  searchDirs[dirCount++] = "mc0:/POPS/";
  searchDirs[dirCount++] = "mc1:/POPS/";

  /* 1. Load sequential custom modules: MODULE_0.IRX .. MODULE_9.IRX */
  for (int slot = 0; slot <= 9; ++slot) {
    for (int d = 0; d < dirCount; ++d) {
      int length = snprintf(modPath, sizeof(modPath), "%sMODULE_%d.IRX", searchDirs[d], slot);
      if (length < 0 || (size_t)length >= sizeof(modPath))
        return -ENAMETOOLONG;
      if (!tryFile(modPath)) {
        DPRINTF("POPS: Loading custom module %s\n", modPath);
        int res = SifLoadModule(modPath, 0, NULL);
        DPRINTF("POPS: Custom module %s start returned %d\n", modPath, res);
        (void)res;
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
      int length = snprintf(modPath, sizeof(modPath), "%s%s",
                            searchDirs[d], peripheralDrivers[p]);
      if (length < 0 || (size_t)length >= sizeof(modPath))
        return -ENAMETOOLONG;
      if (!tryFile(modPath)) {
        DPRINTF("POPS: Loading peripheral driver %s\n", modPath);
        int res = SifLoadModule(modPath, 0, NULL);
        DPRINTF("POPS: Peripheral driver %s start returned %d\n", modPath, res);
        (void)res;
        break;
      }
    }
  }

  /* 3. Load optional user manifests in the original directory order. */
  static const char *manifestNames[] = {"MODULES.TXT", "IRX.TXT"};
  for (int m = 0; m < 2; ++m) {
    for (int d = 0; d < dirCount; ++d) {
      int length = snprintf(modPath, sizeof(modPath), "%s%s",
                            searchDirs[d], manifestNames[m]);
      if (length < 0 || (size_t)length >= sizeof(modPath))
        return -ENAMETOOLONG;
      if (tryFile(modPath))
        continue;
      int status = pops_manifest_load_file(modPath, searchDirs[d]);
      if (status) {
        msg("POPS: Invalid or unreadable module manifest %s (%d)\n",
            modPath, status);
        return status;
      }
    }
  }

  return 0;
}

static int pops_probe_live_storage(int virtualPfs, uint32_t pvdSampleOffset) {
  const char *paths[] = {"pops0:IMAGE.VCD", "pops0:SLOT0.VMC",
                         "pops0:SLOT1.VMC", "pfs0:IMAGE.VCD",
                         "pfs0:SLOT0.VMC", "pfs0:SLOT1.VMC"};
  int count = virtualPfs ? 6 : 3;
  /* Compare actual bytes, not just successful opens. This catches a
   * legacy PFS path unexpectedly selecting another disc or driver. */
  uint8_t first_disc[2][16] = {{0}};
  int discSamples = pvdSampleOffset ? 2 : 1;
  for (int i = 0; i < count; ++i) {
    int fd = fileXioOpen(paths[i], i % 3 ? FIO_O_RDWR : FIO_O_RDONLY);
    if (fd < 0)
      return fd;
    int status = 0;
    if (i % 3 == 0) {
      char check[16] __attribute__((aligned(64)));
      /* A header alone may be identical across distinct VCDs. When ISO
       * metadata was recognized also compare the volume-identifier bytes.
       * Keep the EE DMA target aligned for every short positive read. */
      for (int sample = 0; sample < discSamples && !status; ++sample) {
        int remaining = sizeof(check);
        uint8_t received[sizeof(check)];
        size_t copied = 0;
        if (sample) {
          int offset = (int)pvdSampleOffset; /* validated below 2 MiB */
          int position = fileXioLseek(fd, offset, SEEK_SET);
          if (position != offset) {
            status = position < 0 ? position : -EIO;
            break;
          }
        }
        while (remaining > 0) {
          int n = fileXioRead(fd, check, remaining);
          if (n <= 0 || n > remaining) {
            status = n < 0 ? n : -EIO;
            break;
          }
          memcpy(received + copied, check, (size_t)n);
          copied += (size_t)n;
          remaining -= n;
        }
        if (!status) {
          if (i == 0)
            memcpy(first_disc[sample], received, sizeof(first_disc[sample]));
          else if (virtualPfs && i == 3 &&
                   memcmp(first_disc[sample], received,
                          sizeof(first_disc[sample])) != 0)
            status = -EIO;
        }
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
    res = pops_load_smb_stack(NULL, NULL);
    if (res) return res;
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
  int virtualPfs = device != Device_APA;
  int argLen = pops_format_proxy_args_mode(proxyArgs, sizeof(proxyArgs),
                                           discArgs[0], card0Path, card1Path,
                                           discArgs[1], discArgs[2], discArgs[3],
                                           virtualPfs);
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
    res = readPopsDependency(popsPath, POPS_LOAD_RAW_BUF, POPS_LOAD_MAX_SIZE, &rawSize);
    if (res) {
      msg("POPS: Failed reading %s: %d\n", popsPath, res);
      return res;
    }

#ifdef LAUNCHER_BOOT_TRACE_STOP_AFTER_DEPENDENCIES
    msg("POPS_DEPENDENCIES_PASS package_bytes=%u staging=0 VMC_creation=0 Sony_entry=0\n",
        (unsigned)rawSize);
    SleepThread();
    return 0;
#endif
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
    res = readPopsDependency(popsPath, POPS_LOAD_RAW_BUF, POPS_LOAD_MAX_SIZE, &elfSize);
    if (res) {
      msg("POPS: Failed reading %s: %d\n", popsPath, res);
      return res;
    }
    res = readPopsDependency(ioprpPath, POPS_LOAD_IOP_BUF, POPS_IOP_MAX_SIZE, &iopSize);
    if (res) {
      msg("POPS: Failed reading %s: %d\n", ioprpPath, res);
      return res;
    }

#ifdef LAUNCHER_BOOT_TRACE_STOP_AFTER_DEPENDENCIES
    msg("POPS_DEPENDENCIES_PASS elf_bytes=%u iop_bytes=%u staging=0 VMC_creation=0 Sony_entry=0\n",
        (unsigned)elfSize, (unsigned)iopSize);
    SleepThread();
    return 0;
#endif
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

  /* Sony's selected IOPCD lives in the verified staged core, not the loose
   * IOPRP ROMDIR. Verify its complete identity and report its actual imports
   * before any core/config/TROJAN writes or IOP reset. Import declarations
   * alone do not establish console execution or a filesystem mount protocol. */
  {
    uint64_t legacyOps = 0, extendedOps = 0;
    res = pops_core_iopcd_probe_io_ordinals((const void *)stagedCore,
                                            plan.core_size, &legacyOps,
                                            &extendedOps);
    if (res) {
      msg("POPS: Embedded IOPCD identity/import inspection failed: %d\n", res);
      return res;
    }
    DPRINTF("POPS: Verified core-embedded IOPCD I/O ordinals ioman=%08X:%08X iomanX=%08X:%08X (declarations only)\n",
            (unsigned)(legacyOps >> 32), (unsigned)legacyOps,
            (unsigned)(extendedOps >> 32), (unsigned)extendedOps);
  }

  /* Retain the separate read-only ROMDIR diagnostics for other dependency
   * images; absence here does not mean the core-embedded IOPCD is missing. */
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
      uint64_t legacyOps = 0, extendedOps = 0;
      int operationStatus = pops_iop_image_probe_io_ordinals(
          rebootIop, plan.iop_size, "IOPCD", &legacyOps, &extendedOps);
      if (!operationStatus)
        DPRINTF("POPS: IOPCD declared I/O ordinals ioman=%08X:%08X iomanX=%08X:%08X (NOT execution proof)\n",
                (unsigned)(legacyOps >> 32), (unsigned)legacyOps,
                (unsigned)(extendedOps >> 32), (unsigned)extendedOps);
      (void)legacyOps;
      (void)extendedOps;
      (void)operationStatus;
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

  /* Stage opt-in runtime core corrections when configured */
  if (cfg.runtime_corrections) {
    res = pops_core_runtime_corrections_stage(POPS_CORE_ADDR, (void *)stagedCore,
                                              plan.core_size, cfg.runtime_corrections);
    if (res) {
      msg("POPS: Runtime corrections staging failed: %d\n", res);
      return res;
    }
    DPRINTF("POPS: Applied runtime corrections mask=0x%02X\n", (unsigned)cfg.runtime_corrections);
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

  /* Preserve original root/title and TROJAN/PATCH ordering. */
  res = pops_stage_fix_files((void *)stagedCore, plan.core_size, vcdDir,
                              gameConfigDir, cfg.compat_modes);
  if (res)
    return res;

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

  /* Stop on malformed manifests rather than accidentally executing an
   * unrelated IRX selected by a silently truncated filename. */
  res = pops_load_custom_modules(vcdDir, vmcDir);
  if (res) {
    msg("POPS: Optional IRX manifest/path handling failed: %d\n", res);
    return res;
  }

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
  /* Sample the ISO9660 volume ID at PVD byte 40, only after the
   * metadata inspector established bounded supported sector geometry. */
  uint32_t pvdSample = 0;
  if (vcdInfo.root_lba && vcdInfo.pvd_lba == 16 &&
      (vcdInfo.sector_size == POPS_VCD_RAW_SECTOR_SIZE ||
       vcdInfo.sector_size == POPS_VCD_ISO_SECTOR_SIZE) &&
      vcdInfo.image_offset <= POPS_VCD_HEADER_SIZE &&
      vcdInfo.data_offset <= 24) {
    pvdSample = vcdInfo.image_offset + 16 * vcdInfo.sector_size +
                vcdInfo.data_offset + 40;
  }
  res = pops_probe_live_storage(virtualPfs, pvdSample);
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

#ifdef LAUNCHER_BOOT_TRACE_STOP_BEFORE_HANDOFF
  /* Opt-in acceptance boundary: all production initialization, disc/card
   * probes and trampoline setup passed. Sony code has not executed yet. */
  DPRINTF("POPS_PREFLIGHT_PASS Sony_entry_not_executed=1\n");
  SleepThread();
  return 0;
#endif

  /* Execute trampoline below 1 MiB, which stages core, clears RAM, and enters POPS */
  ((void (*)(void *))POPS_TRAMPOLINE_ADDR)((void *)POPS_TRAMPOLINE_ARGS);

  return 0;
}
