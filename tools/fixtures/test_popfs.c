/* Compile the production driver with API mocks; these are contract tests,
 * not a substitute for Sony IOPCD/IOMANX or console execution. */
#include "popfs_host_sdk.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdarg.h>
#define _start popfs_start
#include "../../launcher/iop/popfs/src/popfs.c"

static int calls, next_open, close_result, io_result = 7;
static int io_fd, io_size, open_flags, open_mode, operation, critical;
static int sync_calls;
static s64 seek_offset;
static char observed[256], destination[256];
static iomanX_iop_device_t *registered;

int CpuSuspendIntr(int *state) { *state = critical; critical = 1; return 0; }
int CpuResumeIntr(int state) { critical = state; return 0; }
int iomanX_AddDrv(iomanX_iop_device_t *driver) { registered = driver; return 0; }
int iomanX_open(const char *path, int flags, ...) {
  va_list args;
  assert(!critical);
  va_start(args, flags); open_mode = va_arg(args, int); va_end(args);
  strcpy(observed, path); open_flags = flags; ++calls;
  return next_open;
}
int iomanX_close(int fd) { io_fd = fd; return close_result; }
int iomanX_read(int fd, void *buffer, int size) {
  io_fd = fd; io_size = size; operation = 1;
  if (io_result > 0 && size >= io_result) memset(buffer, 0x5a, io_result);
  return io_result;
}
int iomanX_write(int fd, void *buffer, int size) {
  (void)buffer; io_fd = fd; io_size = size; operation = 2; return io_result;
}
int iomanX_lseek(int fd, int offset, int whence) {
  (void)whence; io_fd = fd; seek_offset = offset; return offset;
}
s64 iomanX_lseek64(int fd, s64 offset, int whence) {
  (void)whence; io_fd = fd; seek_offset = offset; return offset;
}
int iomanX_ioctl(int fd, int cmd, void *arg) { (void)cmd; (void)arg; io_fd = fd; return io_result; }
int iomanX_ioctl2(int fd, int cmd, void *arg, unsigned len, void *out, unsigned outlen) {
  (void)cmd; (void)arg; (void)len; (void)out; (void)outlen; io_fd = fd; return io_result;
}
int iomanX_getstat(const char *name, iox_stat_t *stat) {
  strcpy(observed, name); stat->size = 0x20000; return io_result < 0 ? io_result : 0;
}
int iomanX_remove(const char *name) { strcpy(observed, name); return io_result; }
int iomanX_rename(const char *old, const char *name) {
  strcpy(observed, old); strcpy(destination, name); return io_result;
}
int iomanX_sync(const char *name, int flag) {
  (void)flag;
  assert(!strcmp(name, "udpfs:") || !strcmp(name, "mmce1:"));
  ++sync_calls;
  return io_result;
}

int main(void) {
  char *arguments[] = {"popfs", "mass7:/POPS/Game.VCD", "udpfs:/saves/Card0.VMC",
                        "mmce1:/POPS/Game/Card1.VMC", "pfs0:/disc/Second.VCD"};
  iomanX_iop_file_t file = {0};
  iomanX_iop_device_ops_t *ops;
  char data[32], too_long[300];
  iox_stat_t stat;
  int saved;

  assert(popfs_start(3, arguments) == MODULE_NO_RESIDENT_END);
  saved = 1; arguments[1] = "pops1:/recursive";
  assert(popfs_start(4, arguments) == MODULE_NO_RESIDENT_END);
  arguments[saved] = "mass7:/POPS/Game.VCD";
  arguments[2] = arguments[1];
  assert(popfs_start(5, arguments) == MODULE_NO_RESIDENT_END);
  arguments[2] = "udpfs:/saves/Card0.VMC";
  arguments[1] = "udpfs:/saves/Card0.VMC.bak";
  assert(popfs_start(5, arguments) == MODULE_NO_RESIDENT_END);
  arguments[1] = "mass7:/POPS/Game.VCD";
  assert(popfs_start(5, arguments) == MODULE_RESIDENT_END);
  assert(registered && !strcmp(registered->name, "pops"));
  ops = registered->ops;

  next_open = 0; /* Descriptor zero must be represented and closed correctly. */
  assert(!ops->open(&file, "/disc/disc0", 1, 0644));
  assert(!strcmp(observed, arguments[1]) && open_flags == 1 && open_mode == 0644);
  assert(ops->deinit(registered) == -EBUSY);
  assert(ops->read(&file, data, 32) == 7 && io_fd == 0 && io_size == 32 && data[6] == 0x5a);
  operation = 0;
  assert(ops->write(&file, data, 32) == -EROFS && operation == 0);
  assert(ops->lseek64(&file, INT64_C(0x100000123), 0) == INT64_C(0x100000123));
  assert(seek_offset == INT64_C(0x100000123));
  close_result = -EIO;
  assert(ops->close(&file) == -EIO && io_fd == 0);
  assert(!ops->deinit(registered) && ops->close(&file) == -EBADF);
  close_result = 0;

  calls = 0;
  assert(ops->open(&file, "/disc/disc0", 3, 0) == -EROFS);
  assert(ops->open(&file, "/disc/disc2", 1, 0) == -ENOENT);
  assert(ops->open(&file, "/ps1emu/../disc/disc0", 1, 0) == -ENOENT);
  assert(ops->open(&file, "/disc/disc01", 1, 0) == -ENOENT);
  assert(ops->open(&file, "/ps1emu", 1, 0) == -EISDIR);
  memset(too_long, 'x', sizeof(too_long)); too_long[299] = 0;
  assert(ops->open(&file, too_long, 1, 0) == -ENAMETOOLONG && calls == 0);
  file.unit = 2;
  assert(ops->open(&file, "/disc/disc0", 1, 0) == -ENODEV && calls == 0);
  assert(ops->getstat(&file, "/ps1emu", &stat) == -ENODEV);
  file.unit = 1;
  next_open = -ENODEV;
  assert(ops->open(&file, "/ps1emu/card0", 3, 0644) == -ENODEV);
  assert(calls == 1 && !ops->deinit(registered)); /* No retry on another device. */

  next_open = 42;
  assert(!ops->open(&file, "\\ps1emu\\card1.bak", 0x203, 0644));
  assert(!strcmp(observed, "mmce1:/POPS/Game/Card1.VMC.bak"));
  assert(ops->write(&file, data, 32) == 7 && io_fd == 42 && operation == 2);
  io_result = -EIO;
  assert(ops->sync(&file, "pops1:", 0) == -EIO && sync_calls == 2);
  assert(ops->read(&file, data, 32) == -EIO && ops->write(&file, data, 32) == -EIO);
  assert(ops->ioctl(&file, 123, NULL) == -EIO);
  assert(ops->ioctl2(&file, 123, NULL, 0, NULL, 0) == -EIO);
  assert(ops->read(&file, data, -1) == -EINVAL && ops->write(&file, NULL, 1) == -EINVAL);
  assert(!ops->close(&file));
  io_result = 7;
  assert(!ops->sync(&file, "pops1:", 0) && sync_calls == 4);

  assert(!ops->getstat(&file, "/ps1emu", &stat) && (stat.mode & FIO_S_IFDIR));
  assert(!ops->mkdir(&file, "/ps1emu", 0755));
  assert(!ops->getstat(&file, "/ps1emu/card0", &stat));
  assert(stat.size == 0x20000 && !strcmp(observed, arguments[2]));
  assert(ops->remove(&file, "/disc/disc0") == -EROFS);
  assert(ops->rename(&file, "/ps1emu/card0", "/ps1emu/card1") == -EXDEV);
  assert(ops->rename(&file, "/ps1emu/card0", "/ps1emu/card0.bak") == 7);
  assert(!strcmp(observed, arguments[2]) && !strcmp(destination, "udpfs:/saves/Card0.VMC.bak"));
  assert(!ops->open(&file, "/disc/disc1", 1, 0) && !strcmp(observed, arguments[4]));
  assert(!ops->close(&file) && !ops->deinit(registered));
  puts("POPFS production-driver contract PASS: paths, multi-disc, save backups, descriptor zero,");
  puts("short I/O, device errors, readonly discs, 64-bit seeks and active-handle lifetime");
  return 0;
}
