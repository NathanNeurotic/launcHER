#include "irx_imports.h"
#include <errno.h>
#include <stdint.h>

IRX_ID("launcHER_POP_filesystem", 1, 0);

#define PATH_LIMIT 256
#define DISC_COUNT 4
#define PATH_COUNT (DISC_COUNT + 2)

/* Module arguments: disc0, card0, card1, optional disc1/disc2/disc3.
 * Backing paths are explicit; massN is never interpreted as USB identity.
 * No fallback to another image/device on an open or I/O failure. */
static char paths[PATH_COUNT][PATH_LIMIT];
static unsigned active;
static unsigned active_disc_handles;
static int active_disc;
static int lid_open;

/* Reserve a disc descriptor before I/O starts, including a pending open.
 * A disc change cannot retarget an already-open underlying file descriptor. */
static void count_add(int delta, int is_disc) {
  int state;
  CpuSuspendIntr(&state);
  active += delta;
  if (is_disc)
    active_disc_handles += delta;
  CpuResumeIntr(state);
}

static int valid_backend(const char *path) {
  size_t length, i;
  if (!path || !(length = strlen(path)) || length >= PATH_LIMIT - 4)
    return 0;
  for (i = 0; i < length && path[i] != ':'; ++i) {
    if (!((path[i] >= 'a' && path[i] <= 'z') ||
          (path[i] >= 'A' && path[i] <= 'Z') ||
          (path[i] >= '0' && path[i] <= '9') || path[i] == '_'))
      return 0;
  }
  if (!i || i == length || !path[i + 1])
    return 0;
  /* Disallow both direct and nested forwarding back into popsN: . */
  for (const char *part = path; *part; ++part) {
    if (part != path && part[-1] != ':') continue;
    if (strlen(part) < 5) continue;
    if ((part[0] == 'p' || part[0] == 'P') &&
        (part[1] == 'o' || part[1] == 'O') &&
        (part[2] == 'p' || part[2] == 'P') &&
        (part[3] == 's' || part[3] == 'S')) {
      const char *q = part + 4;
      while (*q >= '0' && *q <= '9') ++q;
      if (*q == ':') return 0;
    }
  }
  return 1;
}

/* Returns the configured path index; -1 denotes the virtual save directory. */
static int resolve(const char *name, char output[PATH_LIMIT]) {
  char normalized[PATH_LIMIT];
  const char *relative;
  size_t i, length;
  int index, backup = 0;
  if (!name)
    return -EINVAL;
  if ((length = strlen(name)) >= PATH_LIMIT)
    return -ENAMETOOLONG;
  for (i = 0; i <= length; ++i)
    normalized[i] = name[i] == '\\' ? '/' : name[i];
  relative = normalized[0] == '/' ? normalized + 1 : normalized;
  if (!strcmp(relative, "ps1emu") || !strcmp(relative, "ps1emu/"))
    return -1;
  /* The POPS trampoline passes pops0:IMAGE.VCD, while the sector proxy also
   * exposes /disc/disc0. Keep both names on the identical read-only backing
   * descriptor; IMAGE0.VCD covers the legacy per-partition launch filename.
   * This does not emulate Sony's separate pfs0: namespace. */
  if (!strcmp(relative, "IMAGE.VCD") || !strcmp(relative, "IMAGE0.VCD")) {
    index = 0;
    if (active_disc > 0 && active_disc < DISC_COUNT && paths[active_disc][0])
      index = active_disc;
  } else if (!strncmp(relative, "IMAGE", 5) &&
             relative[5] >= '1' && relative[5] < '0' + DISC_COUNT &&
             !strcmp(relative + 6, ".VCD")) {
    /* Historical partition-installed multi-disc layouts use IMAGE1.VCD
     * and later numbered images. These map directly to configured slots.
     * Preserve legacy dynamic IMAGE0/IMAGE aliases until IOPCD is traced. */
    index = relative[5] - '0';
  } else if (!strncmp(relative, "disc/disc", 9) && relative[9] >= '0' &&
             relative[9] < '0' + DISC_COUNT && !relative[10]) {
    index = relative[9] - '0';
    if (index == 0 && active_disc > 0 && active_disc < DISC_COUNT && paths[active_disc][0])
      index = active_disc;
  } else if (!strncmp(relative, "SLOT", 4) &&
             (relative[4] == '0' || relative[4] == '1') &&
             (!strcmp(relative + 5, ".VMC") || !strcmp(relative + 5, ".VMC.bak"))) {
    index = DISC_COUNT + relative[4] - '0';
    backup = !strcmp(relative + 5, ".VMC.bak");
  } else if (!strncmp(relative, "ps1emu/card", 11) &&
             (relative[11] == '0' || relative[11] == '1') &&
             (!relative[12] || !strcmp(relative + 12, ".bak"))) {
    index = DISC_COUNT + relative[11] - '0';
    backup = relative[12] != 0;
  } else {
    return -ENOENT;
  }
  if (!paths[index][0])
    return -ENOENT;
  length = strlen(paths[index]);
  memcpy(output, paths[index], length + 1);
  if (backup)
    memcpy(output + length, ".bak", 5);
  return index;
}

static int file_fd(const iomanX_iop_file_t *file) {
  return file->privdata ? (int)(((uintptr_t)file->privdata >> 1) - 1) : -EBADF;
}

static int bridge_init(iomanX_iop_device_t *device) { (void)device; return 0; }
static int bridge_deinit(iomanX_iop_device_t *device) {
  int state, busy;
  (void)device;
  CpuSuspendIntr(&state);
  busy = active != 0;
  CpuResumeIntr(state);
  return busy ? -EBUSY : 0;
}

/* A read-only Sony CD file may be opened with asynchronous/nonblocking
 * qualifiers. These do not grant write access; create/truncate/append and
 * any unexpected flag remain forbidden for disc-backed descriptors. */
static int disc_read_only_flags(int flags) {
  const int permitted = FIO_O_RDONLY | FIO_O_NBLOCK | FIO_O_NOWAIT;
  return (flags & (FIO_O_RDONLY | FIO_O_WRONLY)) == FIO_O_RDONLY &&
         (flags & ~permitted) == 0;
}

static int bridge_open(iomanX_iop_file_t *file, const char *name, int flags, int mode) {
  char backing[PATH_LIMIT];
  int index, fd, state, error = 0;
  if (file->unit < 0 || file->unit > 1)
    return -ENODEV;
  /* Reopening the same IOMANX file object would orphan the first backing
   * descriptor and permanently pin the active-disc count. */
  if (file->privdata)
    return -EBUSY;
  /* Resolve the disc0 alias and reserve the handle in the same critical
   * section. Otherwise a concurrent SWAP_DISC could retarget the alias
   * between resolution and reservation, leaving the old image open while
   * active_disc already names the new one. Never hold this lock during I/O. */
  CpuSuspendIntr(&state);
  index = resolve(name, backing);
  if (index < 0)
    error = index == -1 ? -EISDIR : index;
  else if (index < DISC_COUNT && !disc_read_only_flags(flags))
    error = -EROFS;
  else if (index < DISC_COUNT && lid_open)
    error = -ENODEV;
  else {
    ++active;
    if (index < DISC_COUNT)
      ++active_disc_handles;
  }
  CpuResumeIntr(state);
  if (error)
    return error;
  fd = iomanX_open(backing, flags, mode);
  if (fd < 0) {
    count_add(-1, index < DISC_COUNT);
    return fd;
  }
  file->privdata = (void *)(((uintptr_t)(fd + 1) << 1) | (index < DISC_COUNT));
  return 0;
}

static int bridge_close(iomanX_iop_file_t *file) {
  int fd = file_fd(file), result;
  int is_disc;
  if (fd < 0)
    return fd;
  is_disc = ((uintptr_t)file->privdata & 1) != 0;
  result = iomanX_close(fd);
  /* IOMANX consumes a descriptor even when the driver's close reports failure.
   * Preserve that error, but do not leave an unreachable active handle. */
  file->privdata = NULL;
  count_add(-1, is_disc);
  return result;
}

static int bridge_read(iomanX_iop_file_t *file, void *buffer, int size) {
  int fd = file_fd(file);
  if (fd < 0) return fd;
  if (size < 0 || (!buffer && size)) return -EINVAL;
  return iomanX_read(fd, buffer, size);
}
static int bridge_write(iomanX_iop_file_t *file, void *buffer, int size) {
  int fd = file_fd(file);
  if (fd < 0) return fd;
  if ((uintptr_t)file->privdata & 1) return -EROFS;
  if (size < 0 || (!buffer && size)) return -EINVAL;
  return iomanX_write(fd, buffer, size);
}
static int bridge_seek(iomanX_iop_file_t *file, int offset, int whence) {
  int fd = file_fd(file);
  return fd < 0 ? fd : iomanX_lseek(fd, offset, whence);
}
static s64 bridge_seek64(iomanX_iop_file_t *file, s64 offset, int whence) {
  int fd = file_fd(file);
  return fd < 0 ? fd : iomanX_lseek64(fd, offset, whence);
}
static int bridge_ioctl(iomanX_iop_file_t *file, int command, void *argument) {
  int fd = file_fd(file);
  return fd < 0 ? fd : iomanX_ioctl(fd, command, argument);
}
static int bridge_ioctl2(iomanX_iop_file_t *file, int command, void *argument,
                         unsigned arg_size, void *output, unsigned out_size) {
  int fd = file_fd(file);
  return fd < 0 ? fd : iomanX_ioctl2(fd, command, argument, arg_size, output, out_size);
}
static int bridge_stat(iomanX_iop_file_t *file, const char *name, iox_stat_t *stat) {
  char backing[PATH_LIMIT];
  int index;
  if (file->unit < 0 || file->unit > 1) return -ENODEV;
  if (!stat) return -EINVAL;
  index = resolve(name, backing);
  if (index == -1) {
    memset(stat, 0, sizeof(*stat));
    stat->mode = FIO_S_IFDIR | FIO_S_IRUSR | FIO_S_IWUSR | FIO_S_IXUSR;
    return 0;
  }
  if (index < 0) return index;
  int status = iomanX_getstat(backing, stat);
  if (!status && index < DISC_COUNT)
    stat->mode &= ~(FIO_S_IWUSR | FIO_S_IWGRP | FIO_S_IWOTH);
  return status;
}
static int bridge_mkdir(iomanX_iop_file_t *file, const char *name, int mode) {
  char backing[PATH_LIMIT];
  int index = resolve(name, backing);
  (void)mode;
  if (file->unit < 0 || file->unit > 1) return -ENODEV;
  return index == -1 ? 0 : (index < 0 ? index : -EEXIST);
}
static int bridge_remove(iomanX_iop_file_t *file, const char *name) {
  char backing[PATH_LIMIT];
  int index = resolve(name, backing);
  if (file->unit < 0 || file->unit > 1) return -ENODEV;
  if (index < 0) return index == -1 ? -EISDIR : index;
  return index < DISC_COUNT ? -EROFS : iomanX_remove(backing);
}
static int bridge_rename(iomanX_iop_file_t *file, const char *old, const char *name) {
  char source[PATH_LIMIT], destination[PATH_LIMIT];
  int from = resolve(old, source), to = resolve(name, destination);
  if (file->unit < 0 || file->unit > 1) return -ENODEV;
  if (from < 0 || to < 0) return -EINVAL;
  if (from < DISC_COUNT || to < DISC_COUNT) return -EROFS;
  /* Save slots are independent; only rename a card and its own backup. */
  if (from != to) return -EXDEV;
  return iomanX_rename(source, destination);
}

static int bridge_sync(iomanX_iop_file_t *file, const char *name, int flag) {
  char backing[PATH_LIMIT];
  int i, first_error = 0;
  (void)name;
  if (file->unit < 0 || file->unit > 1) return -ENODEV;
  /* Attempt both save volumes even if the first sync fails. Do not report an
   * unsupported backend flush as success. File close errors also propagate. */
  for (i = DISC_COUNT; i < PATH_COUNT; ++i) {
    size_t j;
    int result;
    for (j = 0; paths[i][j] != ':'; ++j) backing[j] = paths[i][j];
    backing[j] = ':';
    backing[j + 1] = 0;
    result = iomanX_sync(backing, flag);
    if (result < 0 && !first_error) first_error = result;
  }
  return first_error;
}

#define POPS_DEVCTL_SWAP_DISC    0x01
#define POPS_DEVCTL_GET_DISC     0x02
#define POPS_DEVCTL_OPEN_LID     0x03
#define POPS_DEVCTL_CLOSE_LID    0x04
#define POPS_DEVCTL_SET_LIBCRYPT 0x05
#define POPS_DEVCTL_GET_SUBQ     0x06
#define POPS_DEVCTL_NEXT_DISC    0x07
#define POPS_DEVCTL_GET_LID      0x08

/* Red Book Subchannel Q CRC-16/CCITT, init 0, inverted, big-endian.
 * Standard data-track Q uses track-relative MSF and absolute LBA+150 MSF.
 * See psx-spx CD-ROM format (Q positional frames). */
static uint16_t pops_subq_crc(const uint8_t q[12]) {
  uint16_t crc = 0;
  for (int i = 0; i < 10; ++i) {
    crc ^= (uint16_t)q[i] << 8;
    for (int bit = 0; bit < 8; ++bit)
      crc = (uint16_t)((crc << 1) ^ ((crc & 0x8000) ? 0x1021 : 0));
  }
  return (uint16_t)~crc;
}

static uint8_t pops_bcd(uint32_t n) {
  return (uint8_t)(((n / 10) << 4) | (n % 10));
}

static uint16_t active_libcrypt_key = 0;

static int bridge_devctl(iomanX_iop_file_t *file, const char *devname, int cmd,
                         void *arg, unsigned int arglen, void *buf, unsigned int buflen) {
  (void)file; (void)devname;
  switch (cmd) {
    case POPS_DEVCTL_SWAP_DISC:
      if (arg && arglen >= sizeof(int)) {
        int state, busy, disc;
        /* Devctl buffers need not be naturally aligned on MIPS. */
        memcpy(&disc, arg, sizeof(disc));
        if (disc < 0 || disc >= DISC_COUNT || !paths[disc][0])
          return -EINVAL;
        CpuSuspendIntr(&state);
        busy = active_disc_handles != 0;
        if (!busy)
          active_disc = disc;
        CpuResumeIntr(state);
        return busy ? -EBUSY : 0;
      }
      return -EINVAL;
    case POPS_DEVCTL_GET_DISC:
      if (buf && buflen >= sizeof(int)) {
        int state, disc;
        CpuSuspendIntr(&state);
        disc = active_disc;
        CpuResumeIntr(state);
        memcpy(buf, &disc, sizeof(disc));
        return 0;
      }
      return -EINVAL;
    case POPS_DEVCTL_OPEN_LID:
      lid_open = 1;
      return 0;
    case POPS_DEVCTL_CLOSE_LID:
      lid_open = 0;
      return 0;
    case POPS_DEVCTL_GET_LID:
      if (buf && buflen >= sizeof(int)) {
        int state, lid;
        CpuSuspendIntr(&state);
        lid = lid_open;
        CpuResumeIntr(state);
        memcpy(buf, &lid, sizeof(lid));
        return 0;
      }
      return -EINVAL;
    case POPS_DEVCTL_SET_LIBCRYPT:
      if (arg && arglen >= sizeof(uint16_t)) {
        uint16_t key;
        memcpy(&key, arg, sizeof(key));
        active_libcrypt_key = key;
        return 0;
      }
      return -EINVAL;
    case POPS_DEVCTL_NEXT_DISC: {
      int state, next, old, busy;
      CpuSuspendIntr(&state);
      old = active_disc;
      next = (old + 1) % DISC_COUNT;
      while (next != old && !paths[next][0])
        next = (next + 1) % DISC_COUNT;
      busy = active_disc_handles != 0;
      if (!busy && paths[next][0])
        active_disc = next;
      CpuResumeIntr(state);
      if (busy)
        return -EBUSY;
      /* A single-disc configuration must not acknowledge a swap to
       * the same disc. The caller needs a reliable no-alternate signal. */
      return next != old && paths[next][0] ? 0 : -ENOENT;
    }
    case POPS_DEVCTL_GET_SUBQ:
      if (arg && arglen < sizeof(uint32_t))
        return -EINVAL;
      if (buf && buflen >= 12) {
        uint32_t lba = 0;
        uint8_t *out_subq = (uint8_t *)buf;
        if (arg)
          memcpy(&lba, arg, sizeof(lba));
        /* Both Q time fields are two-digit BCD minutes. Reject positions
         * past absolute 99:59:74 instead of wrapping LBA+150 or emitting
         * corrupted track time and CRC. Never modify output on failure. */
        if (lba > UINT32_C(449849))
          return -ERANGE;
        memset(out_subq, 0, 12);
        out_subq[0] = 0x41; /* Track 1, Mode 1 data */
        out_subq[1] = 0x01;
        out_subq[2] = 0x01;
        uint32_t relative_seconds = lba / 75;
        uint32_t absolute_seconds = (lba + 150) / 75;
        out_subq[3] = pops_bcd(relative_seconds / 60);
        out_subq[4] = pops_bcd(relative_seconds % 60);
        out_subq[5] = pops_bcd(lba % 75);
        out_subq[6] = 0;
        out_subq[7] = pops_bcd(absolute_seconds / 60);
        out_subq[8] = pops_bcd(absolute_seconds % 60);
        out_subq[9] = pops_bcd((lba + 150) % 75);
        uint16_t crc = pops_subq_crc(out_subq);
        out_subq[10] = (uint8_t)(crc >> 8);
        out_subq[11] = (uint8_t)crc;
        if (active_libcrypt_key != 0 && lba >= 12 && lba <= 20) {
          out_subq[10] = (uint8_t)(active_libcrypt_key >> 8);
          out_subq[11] = (uint8_t)(active_libcrypt_key & 0xFF);
        }
        return 0;
      }
      return -EINVAL;
    default:
      return -EINVAL;
  }
}

IOMANX_RETURN_VALUE_IMPL(ENOSYS);
static iomanX_iop_device_ops_t operations = {
  .init = bridge_init, .deinit = bridge_deinit,
  .format = IOMANX_RETURN_VALUE(ENOSYS), .open = bridge_open,
  .close = bridge_close, .read = bridge_read, .write = bridge_write,
  .lseek = bridge_seek, .ioctl = bridge_ioctl, .remove = bridge_remove,
  .mkdir = bridge_mkdir, .rmdir = IOMANX_RETURN_VALUE(ENOSYS),
  .dopen = IOMANX_RETURN_VALUE(ENOSYS), .dclose = IOMANX_RETURN_VALUE(ENOSYS),
  .dread = IOMANX_RETURN_VALUE(ENOSYS), .getstat = bridge_stat,
  .chstat = IOMANX_RETURN_VALUE(ENOSYS), .rename = bridge_rename,
  .chdir = IOMANX_RETURN_VALUE(ENOSYS), .sync = bridge_sync,
  .mount = IOMANX_RETURN_VALUE(ENOSYS), .umount = IOMANX_RETURN_VALUE(ENOSYS),
  .lseek64 = bridge_seek64, .devctl = bridge_devctl,
  .symlink = IOMANX_RETURN_VALUE(ENOSYS), .readlink = IOMANX_RETURN_VALUE(ENOSYS),
  .ioctl2 = bridge_ioctl2
};
static iomanX_iop_device_t device = {
  "pops", IOP_DT_FS | IOP_DT_FSEXT, 1, "launcHER POPS filesystem bridge", &operations
};
static iomanX_iop_device_t virtual_pfs = {
  "pfs", IOP_DT_FS | IOP_DT_FSEXT, 1, "launcHER non-APA virtual PFS alias", &operations
};

/* The shipped ps2sdk iomanX.irx has the legacy IOMAN hook and a
 * 32-slot device table. Its array-backed AddDrv does NOT detect duplicates. */
#define POPFS_DEVICE_SLOTS 32
static int driver_name_in_use(const char *name) {
  iomanX_iop_device_t **list = iomanX_GetDeviceList();
  int i;
  if (!list) return 1;
  for (i = 0; i < POPFS_DEVICE_SLOTS; ++i)
    if (list[i] && !strcmp(list[i]->name, name)) return 1;
  return 0;
}

static int pfs_backing(const char *path) {
  const char *p;
  for (p = path; p && *p; ++p) {
    const char *q;
    if (p != path && p[-1] != ':') continue;
    if (!p[1] || !p[2]) continue;
    if (!((p[0] == 'p' || p[0] == 'P') &&
          (p[1] == 'f' || p[1] == 'F') &&
          (p[2] == 's' || p[2] == 'S'))) continue;
    q = p + 3;
    while (*q >= '0' && *q <= '9') ++q;
    if (*q == ':') return 1;
  }
  return 0;
}

int _start(int argc, char **argv) {
  int i, result, alias;
  /* MODLOAD supplies the loader filename at argv[0] ("LBbyEE" for
   * SifExecModuleBuffer). Our explicitly packed mode starts at argv[1]. */
  if (argc < 5 || argc > 8 || !argv || !argv[0])
    return MODULE_NO_RESIDENT_END;
  --argc;
  ++argv;
  if (argc < 4 || argc > 7 || !argv || !argv[0])
    return MODULE_NO_RESIDENT_END;
  alias = !strcmp(argv[0], "popfs+pfs");
  if (!alias && strcmp(argv[0], "popfs"))
    return MODULE_NO_RESIDENT_END;
  /* A foreign pfs driver is never overwritten or unregistered. */
  if (driver_name_in_use("pops") || (alias && driver_name_in_use("pfs")))
    return MODULE_NO_RESIDENT_END;
  for (i = 1; i < argc; ++i)
    if (!argv[i] || !valid_backend(argv[i]) || (alias && pfs_backing(argv[i])))
      return MODULE_NO_RESIDENT_END;
  memset(paths, 0, sizeof(paths));
  for (i = 1; i < argc; ++i) {
    int index = i == 1 ? 0 : (i < 4 ? DISC_COUNT + i - 2 : i - 3);
    if (!valid_backend(argv[i]))
      return MODULE_NO_RESIDENT_END;
    memcpy(paths[index], argv[i], strlen(argv[i]) + 1);
  }
  /* Reject exact slot/disc aliases, including a save path equal to another
   * configured path's backup. Shared-card policy needs an explicit future mode. */
  for (i = DISC_COUNT; i < PATH_COUNT; ++i) {
    int j;
    for (j = 0; j < PATH_COUNT; ++j) {
      size_t length, card_length;
      if (i == j || !paths[j][0]) continue;
      length = strlen(paths[j]);
      card_length = strlen(paths[i]);
      if (!strcmp(paths[i], paths[j]) ||
          (!strncmp(paths[i], paths[j], length) && !strcmp(paths[i] + length, ".bak")) ||
          (!strncmp(paths[j], paths[i], card_length) && !strcmp(paths[j] + card_length, ".bak")))
        return MODULE_NO_RESIDENT_END;
    }
  }
  result = iomanX_AddDrv(&device);
  if (result < 0)
    return MODULE_NO_RESIDENT_END;
  if (alias && iomanX_AddDrv(&virtual_pfs) < 0) {
    /* Roll back only our own fresh registration. Never delete foreign PFS. */
    iomanX_DelDrv("pops");
    return MODULE_NO_RESIDENT_END;
  }
  return MODULE_RESIDENT_END;
}

#ifdef POPS_HOST_TEST
iomanX_iop_device_t *popfs_test_device(void) { return &device; }
#endif
