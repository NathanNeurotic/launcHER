#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static uint8_t bytes[131072];
static int exists, probe_error, seek_error, close_error, create_race;
static int write_error, zero_write, interrupt_write, mkdir_error;
static size_t file_size, position, write_limit;
static int opens, writes, removals;

static int mock_open(const char *path, int flags, ...) {
  (void)path;
  ++opens;
  if (flags == O_RDONLY) {
    if (probe_error) { errno = probe_error; return -1; }
    if (!exists) { errno = ENOENT; return -1; }
    return 0; /* Descriptor zero must work. */
  }
  assert((flags & (O_CREAT | O_EXCL)) == (O_CREAT | O_EXCL));
  assert(!(flags & O_TRUNC));
  if (exists || create_race) { errno = EEXIST; return -1; }
  exists = 1;
  file_size = position = 0;
  return 0;
}
static off_t mock_lseek(int fd, off_t offset, int whence) {
  assert(fd == 0 && offset == 0 && whence == SEEK_END);
  if (seek_error) { errno = EIO; return -1; }
  return (off_t)file_size;
}
static int mock_close(int fd) {
  assert(fd == 0);
  if (close_error) { errno = EIO; return -1; }
  return 0;
}
static ssize_t mock_write(int fd, const void *buffer, size_t length) {
  assert(fd == 0);
  ++writes;
  if (interrupt_write) { interrupt_write = 0; errno = EINTR; return -1; }
  if (write_error) { errno = ENOSPC; return -1; }
  if (zero_write) return 0;
  if (length > write_limit) length = write_limit;
  assert(position + length <= sizeof(bytes));
  memcpy(bytes + position, buffer, length);
  position += length;
  file_size = position;
  return (ssize_t)length;
}
static int mock_mkdir(const char *path, mode_t mode) {
  (void)path; (void)mode;
  if (mkdir_error) { errno = mkdir_error; return -1; }
  return 0;
}
static int mock_unlink(const char *path) {
  (void)path;
  ++removals;
  exists = 0;
  return 0;
}
#define open mock_open
#define lseek mock_lseek
#define close mock_close
#define write mock_write
#define mkdir mock_mkdir
#define unlink mock_unlink
#include "../../common/src/pops_vmc.c"
#undef open
#undef lseek
#undef close
#undef write
#undef mkdir
#undef unlink

static void reset(void) {
  exists = probe_error = seek_error = close_error = create_race = 0;
  write_error = zero_write = interrupt_write = mkdir_error = 0;
  opens = writes = removals = 0;
  file_size = position = 0;
  write_limit = 128;
  memset(bytes, 0x5a, sizeof(bytes));
}
int main(void) {
  unsigned i, j;
  uint8_t checksum;
  reset();
  write_limit = 7; interrupt_write = 1;
  assert(pops_vmc_ensure("mass0:/POPS/Game/SLOT0.VMC") == 0);
  assert(exists && file_size == sizeof(bytes) && removals == 0);
  assert(bytes[0] == 'M' && bytes[1] == 'C' && bytes[127] == 14);
  for (i = 1; i < 16; ++i) {
    assert(bytes[i*128] == 0xa0);
    assert(bytes[i*128+8] == 255 && bytes[i*128+9] == 255);
  }
  for (i = 16; i < 36; ++i)
    for (j = 0; j < 4; ++j) assert(bytes[i*128+j] == 255);
  for (i = 0; i < 36; ++i) {
    checksum = 0;
    for (j = 0; j < 128; ++j) checksum ^= bytes[i*128+j];
    assert(checksum == 0);
  }
  assert(!memcmp(bytes, bytes+63*128, 128));
  for (i = 36*128; i < 63*128; ++i) assert(bytes[i] == 255);
  for (i = 8192; i < sizeof(bytes); ++i) assert(bytes[i] == 0);

  for (i = 0; i < 3; ++i) {
    reset(); exists = 1;
    file_size = i == 0 ? 131072 : (i == 1 ? 100 : 131073);
    assert(pops_vmc_ensure("card") == (i == 0 ? 0 : -EINVAL));
    assert(opens == 1 && writes == 0 && removals == 0);
    for (j = 0; j < sizeof(bytes); ++j) assert(bytes[j] == 0x5a);
  }
  reset(); exists = seek_error = 1;
  assert(pops_vmc_ensure("card") == -EIO && writes == 0 && removals == 0);
  reset(); probe_error = EACCES;
  assert(pops_vmc_ensure("card") == -EACCES && opens == 1);
  reset(); create_race = 1;
  assert(pops_vmc_ensure("card") == -EEXIST && writes == 0 && removals == 0);
  reset(); mkdir_error = EACCES;
  assert(pops_vmc_ensure("dir/card") == -EACCES && opens == 1);
  reset(); write_error = 1;
  assert(pops_vmc_ensure("card") == -ENOSPC && removals == 1 && !exists);
  reset(); zero_write = 1;
  assert(pops_vmc_ensure("card") == -EIO && removals == 1);
  reset(); close_error = 1;
  assert(pops_vmc_ensure("card") == -EIO && removals == 1);
  reset(); exists = close_error = 1; file_size = 131072;
  assert(pops_vmc_ensure("card") == -EIO && removals == 0 && writes == 0);
  puts("VMC production contracts PASS: card format, existing-file preservation, exclusive creation, short writes, EINTR and failure propagation");
  return 0;
}
