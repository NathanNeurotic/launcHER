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
static iomanX_iop_device_t *registered_drivers[32];
static int fail_alias_add;

int CpuSuspendIntr(int *state) { *state = critical; critical = 1; return 0; }
int CpuResumeIntr(int state) { critical = state; return 0; }
iomanX_iop_device_t **iomanX_GetDeviceList(void) { return registered_drivers; }
int iomanX_AddDrv(iomanX_iop_device_t *driver) {
  if (fail_alias_add && !strcmp(driver->name, "pfs")) return -1;
  for (int i = 0; i < 32; ++i)
    if (!registered_drivers[i]) {
      registered_drivers[i] = driver;
      registered = driver;
      return 0;
    }
  return -1;
}
int iomanX_DelDrv(const char *name) {
  for (int i = 0; i < 32; ++i)
    if (registered_drivers[i] && !strcmp(registered_drivers[i]->name, name)) {
      registered_drivers[i] = NULL;
      return 0;
    }
  return -1;
}
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
  arguments[1] = "POPS0:/recursive";
  assert(popfs_start(4, arguments) == MODULE_NO_RESIDENT_END);
  arguments[1] = "PoPs:/recursive";
  assert(popfs_start(4, arguments) == MODULE_NO_RESIDENT_END);
  arguments[1] = "hdd0:PART:pops0:/recursive";
  assert(popfs_start(4, arguments) == MODULE_NO_RESIDENT_END);
  arguments[1] = "hdd0:PART:POPS:/recursive";
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

  /* With no alternative media, NEXT_DISC must report ENOENT and keep disc0
   * selected rather than returning a false success for a no-op. */
  char saved_second_disc[PATH_LIMIT];
  memcpy(saved_second_disc, paths[1], sizeof(saved_second_disc));
  paths[1][0] = 0;
  int unchanged_disc = -1;
  assert(ops->devctl(&file, "pops:", 0x07, NULL, 0, NULL, 0) == -ENOENT);
  assert(!ops->devctl(&file, "pops:", 0x02, NULL, 0, &unchanged_disc,
                      sizeof(unchanged_disc)) && unchanged_disc == 0);
  memcpy(paths[1], saved_second_disc, sizeof(saved_second_disc));

  next_open = 0; /* Descriptor zero must be represented and closed correctly. */
  assert(!ops->open(&file, "/disc/disc0", 1, 0644));
  assert(!strcmp(observed, arguments[1]) && open_flags == 1 && open_mode == 0644);
  assert(ops->deinit(registered) == -EBUSY);
  /* A still-open disc handle cannot be retargeted by swapping the alias.
   * Card descriptors may remain open during a disc change. */
  int requested = 1, selected = -1;
  assert(ops->devctl(&file, "pops:", 0x01, &requested, sizeof(requested), NULL, 0) == -EBUSY);
  assert(ops->devctl(&file, "pops:", 0x07, NULL, 0, NULL, 0) == -EBUSY);
  assert(!ops->devctl(&file, "pops:", 0x02, NULL, 0, &selected, sizeof(selected)));
  assert(selected == 0);
  assert(ops->read(&file, data, 32) == 7 && io_fd == 0 && io_size == 32 && data[6] == 0x5a);
  operation = 0;
  assert(ops->write(&file, data, 32) == -EROFS && operation == 0);
  assert(ops->lseek64(&file, INT64_C(0x100000123), 0) == INT64_C(0x100000123));
  assert(seek_offset == INT64_C(0x100000123));
  close_result = -EIO;
  assert(ops->close(&file) == -EIO && io_fd == 0);
  assert(!ops->deinit(registered) && ops->close(&file) == -EBADF);
  close_result = 0;

  /* The EE trampoline passes pops0:IMAGE.VCD, not /disc/disc0.
   * Legacy partition files use IMAGE0.VCD. Both share the same immutable
   * backend and obey the same active-disc switch semantics. */
  next_open = 17;
  assert(!ops->open(&file, "IMAGE.VCD", 1, 0));
  assert(!strcmp(observed, arguments[1]));
  assert(ops->write(&file, data, 1) == -EROFS);
  assert(!ops->close(&file));
  next_open = 18;
  assert(!ops->open(&file, "/IMAGE0.VCD", 1, 0));
  assert(!strcmp(observed, arguments[1]));
  assert(!ops->close(&file));
  assert(!ops->getstat(&file, "IMAGE.VCD", &stat));
  assert(!strcmp(observed, arguments[1]));
  assert(ops->remove(&file, "IMAGE.VCD") == -EROFS);
  assert(ops->open(&file, "IMAGE.VCD.bak", 1, 0) == -ENOENT);

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
  /* Card handles do not prohibit switching; only disc descriptors do. */
  assert(!ops->devctl(&file, "pops:", 0x01, &requested, sizeof(requested), NULL, 0));
  assert(!ops->devctl(&file, "pops:", 0x02, NULL, 0, &selected, sizeof(selected)));
  assert(selected == 1);
  next_open = 19;
  assert(!ops->open(&file, "IMAGE.VCD", 1, 0));
  assert(!strcmp(observed, arguments[4]));
  assert(!ops->close(&file));
  requested = 0;
  assert(!ops->devctl(&file, "pops:", 0x01, &requested, sizeof(requested), NULL, 0));
  assert(!ops->sync(&file, "pops1:", 0) && sync_calls == 4);

  assert(!ops->getstat(&file, "/ps1emu", &stat) && (stat.mode & FIO_S_IFDIR));
  assert(!ops->mkdir(&file, "/ps1emu", 0755));
  assert(!ops->getstat(&file, "/ps1emu/card0", &stat));
  assert(stat.size == 0x20000 && !strcmp(observed, arguments[2]));
  assert(ops->remove(&file, "/disc/disc0") == -EROFS);
  assert(ops->rename(&file, "/ps1emu/card0", "/ps1emu/card1") == -EXDEV);
  assert(ops->rename(&file, "/ps1emu/card0", "/ps1emu/card0.bak") == 7);
  assert(!ops->open(&file, "/disc/disc1", 1, 0) && !strcmp(observed, arguments[4]));
  assert(!ops->close(&file));

  /* Standard POPStarter memory card names resolve to the existing save pair. */
  next_open = 63;
  assert(!ops->open(&file, "SLOT0.VMC", 3, 0));
  assert(!strcmp(observed, arguments[2]));
  assert(!ops->close(&file));
  next_open = 64;
  assert(!ops->open(&file, "/SLOT1.VMC.bak", 3, 0));
  assert(!strcmp(observed, "mmce1:/POPS/Game/Card1.VMC.bak"));
  assert(!ops->close(&file));
  assert(ops->open(&file, "SLOT2.VMC", 1, 0) == -ENOENT);

  /* Devctl tray and disc commands */
  int disc = 1, query_disc = -1, query_lid = -1;
  assert(!ops->devctl(&file, "pops:", 0x03 /* OPEN_LID */, NULL, 0, NULL, 0));
  assert(!ops->devctl(&file, "pops:", 0x08 /* GET_LID */, NULL, 0, &query_lid, sizeof(query_lid)) && query_lid == 1);
  assert(ops->devctl(&file, "pops:", 0x01 /* SWAP_DISC */, &disc, 0, NULL, 0) == -EINVAL);
  assert(!ops->devctl(&file, "pops:", 0x01 /* SWAP_DISC */, &disc, sizeof(disc), NULL, 0));
  assert(!ops->devctl(&file, "pops:", 0x02 /* GET_DISC */, NULL, 0, &query_disc, sizeof(query_disc)) && query_disc == 1);
  assert(!ops->devctl(&file, "pops:", 0x04 /* CLOSE_LID */, NULL, 0, NULL, 0));
  assert(!ops->devctl(&file, "pops:", 0x08 /* GET_LID */, NULL, 0, &query_lid, sizeof(query_lid)) && query_lid == 0);

  /* Devctl LibCrypt and Subchannel Q */
  uint16_t key = 0x7C23; /* Resident Evil 3 key */
  assert(!ops->devctl(&file, "pops:", 0x05 /* SET_LIBCRYPT */, &key, sizeof(key), NULL, 0));
  uint32_t lba = 15;
  uint8_t subq[12] = {0};
  assert(ops->devctl(&file, "pops:", 0x06 /* GET_SUBQ */, &lba, 1, subq, sizeof(subq)) == -EINVAL);
  assert(!ops->devctl(&file, "pops:", 0x06 /* GET_SUBQ */, &lba, sizeof(lba), subq, sizeof(subq)));
  assert(subq[0] == 0x41 && subq[1] == 0x01 && subq[2] == 0x01);
  assert(subq[10] == 0x7C && subq[11] == 0x23);
  /* Standard data-sector Q: relative LBA 0, absolute 00:02:00 and
   * CRC16-CCITT = 0x2832 (known psx-spx reference frame). */
  key = 0;
  assert(!ops->devctl(&file, "pops:", 0x05, &key, sizeof(key), NULL, 0));
  lba = 0;
  assert(!ops->devctl(&file, "pops:", 0x06, &lba, sizeof(lba), subq, sizeof(subq)));
  const uint8_t expected_q[12] = {
      0x41, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x28, 0x32
  };
  assert(!memcmp(subq, expected_q, sizeof(subq)));
  lba = 75;
  assert(!ops->devctl(&file, "pops:", 0x06, &lba, sizeof(lba), subq, sizeof(subq)));
  assert(subq[3] == 0 && subq[4] == 1 && subq[5] == 0);
  assert(subq[7] == 0 && subq[8] == 3 && subq[9] == 0);

  assert(!ops->deinit(&device));

  /* A real PFS driver can sit past the first 16 legacy IOMAN slots.
   * The optional alias must not overwrite it. */
  char *alias_args[] = {"popfs+pfs", "mass7:/POPS/Game.VCD",
                         "udpfs:/saves/Card0.VMC", "mmce1:/POPS/Game/Card1.VMC"};
  assert(!iomanX_DelDrv("pops"));
  iomanX_iop_device_t real_pfs = {"pfs", IOP_DT_FS, 1, "genuine PFS", &operations};
  registered_drivers[24] = &real_pfs;
  assert(popfs_start(4, alias_args) == MODULE_NO_RESIDENT_END);
  assert(registered_drivers[24] == &real_pfs);
  registered_drivers[24] = NULL;

  /* Recursive PFS-backed paths are never accepted in virtual mode. */
  alias_args[1] = "hdd0:__common:pfs:/Game.VCD";
  assert(popfs_start(4, alias_args) == MODULE_NO_RESIDENT_END);
  alias_args[1] = "PFS0:/Game.VCD";
  assert(popfs_start(4, alias_args) == MODULE_NO_RESIDENT_END);
  alias_args[1] = "mass7:/POPS/Game.VCD";

  fail_alias_add = 1;
  assert(popfs_start(4, alias_args) == MODULE_NO_RESIDENT_END);
  assert(!registered_drivers[0]); /* rolls back our pops registration */
  fail_alias_add = 0;
  assert(popfs_start(4, alias_args) == MODULE_RESIDENT_END);
  assert(registered_drivers[0] == &device);
  assert(registered_drivers[1] == &virtual_pfs);
  assert(!virtual_pfs.ops->open(&file, "IMAGE.VCD", FIO_O_RDONLY, 0));
  assert(!virtual_pfs.ops->close(&file));
  assert(!iomanX_DelDrv("pfs"));
  assert(!iomanX_DelDrv("pops"));
  puts("POPFS production-driver contract PASS: paths, multi-disc, save backups, descriptor zero,");
  puts("short I/O, device errors, readonly discs, 64-bit seeks, devctl tray/disc, LibCrypt SubQ, and active-handle lifetime");
  return 0;
}
