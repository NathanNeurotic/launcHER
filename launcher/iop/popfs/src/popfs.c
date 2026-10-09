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
static int active_disc;
static int lid_open;

static void count_add(int delta) {
  int state;
  CpuSuspendIntr(&state);
  active += delta;
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
  /* Prevent forwarding back into this namespace, including pops0:/... . */
  if (i >= 4 && !strncmp(path, "pops", 4)) {
    size_t j;
    for (j = 4; j < i && path[j] >= '0' && path[j] <= '9'; ++j) {}
    if (j == i)
      return 0;
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
  if (!strncmp(relative, "disc/disc", 9) && relative[9] >= '0' &&
      relative[9] < '0' + DISC_COUNT && !relative[10]) {
    index = relative[9] - '0';
    if (index == 0 && active_disc > 0 && active_disc < DISC_COUNT && paths[active_disc][0])
      index = active_disc;
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

static int bridge_open(iomanX_iop_file_t *file, const char *name, int flags, int mode) {
  char backing[PATH_LIMIT];
  int index, fd;
  if (file->unit < 0 || file->unit > 1)
    return -ENODEV;
  index = resolve(name, backing);
  if (index < 0)
    return index == -1 ? -EISDIR : index;
  if (index < DISC_COUNT && flags != FIO_O_RDONLY)
    return -EROFS;
  if (index < DISC_COUNT && lid_open)
    return -ENODEV;
  count_add(1); /* Reserve before the underlying open can block. */
  fd = iomanX_open(backing, flags, mode);
  if (fd < 0) {
    count_add(-1);
    return fd;
  }
  file->privdata = (void *)(((uintptr_t)(fd + 1) << 1) | (index < DISC_COUNT));
  return 0;
}

static int bridge_close(iomanX_iop_file_t *file) {
  int fd = file_fd(file), result;
  if (fd < 0)
    return fd;
  result = iomanX_close(fd);
  /* IOMANX consumes a descriptor even when the driver's close reports failure.
   * Preserve that error, but do not leave an unreachable active handle. */
  file->privdata = NULL;
  count_add(-1);
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
  return index < 0 ? index : iomanX_getstat(backing, stat);
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

#define POPS_DEVCTL_SWAP_DISC 0x01
#define POPS_DEVCTL_GET_DISC  0x02
#define POPS_DEVCTL_OPEN_LID  0x03
#define POPS_DEVCTL_CLOSE_LID 0x04

static int bridge_devctl(iomanX_iop_file_t *file, const char *devname, int cmd,
                         void *arg, unsigned int arglen, void *buf, unsigned int buflen) {
  (void)file; (void)devname; (void)arglen; (void)buflen;
  switch (cmd) {
    case POPS_DEVCTL_SWAP_DISC:
      if (arg) {
        int disc = *(int *)arg;
        if (disc >= 0 && disc < DISC_COUNT && paths[disc][0]) {
          active_disc = disc;
          return 0;
        }
      }
      return -EINVAL;
    case POPS_DEVCTL_GET_DISC:
      if (buf && buflen >= sizeof(int)) {
        *(int *)buf = active_disc;
        return 0;
      }
      return -EINVAL;
    case POPS_DEVCTL_OPEN_LID:
      lid_open = 1;
      return 0;
    case POPS_DEVCTL_CLOSE_LID:
      lid_open = 0;
      return 0;
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

int _start(int argc, char **argv) {
  int i, result;
  if (argc < 4 || argc > 7 || !argv)
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
  return result < 0 ? MODULE_NO_RESIDENT_END : MODULE_RESIDENT_END;
}

#ifdef POPS_HOST_TEST
iomanX_iop_device_t *popfs_test_device(void) { return &device; }
#endif
