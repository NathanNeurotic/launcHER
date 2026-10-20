#include "pops_read_trace.h"

#ifdef LAUNCHER_BOOT_TRACE
#include "dprintf.h"
#include "pops_external.h"
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define NEWLIB_PORT_AWARE
#include <fileXio_rpc.h>
#include <io_common.h>

int pops_read_filexio_trace(const char *path, void *buffer, size_t capacity) {
  unsigned char bounce[16384] __attribute__((aligned(64)));
  size_t total = 0;
  int result = 0;
  if (!path || !buffer || !capacity)
    return -EINVAL;
  int fd = fileXioOpen(path, FIO_O_RDONLY);
  if (fd < 0) {
    DPRINTF("POPS_XIO_FAIL stage=open result=%d\n", fd);
    return fd;
  }
  int64_t length = fileXioLseek64(fd, 0, SEEK_END);
  DPRINTF("POPS_XIO size_low=%u size_high=%u capacity=%u\n",
          (unsigned)(uint64_t)length, (unsigned)((uint64_t)length >> 32),
          (unsigned)capacity);
  if (length <= 0 || (uint64_t)length > capacity) {
    result = length < 0 ? (int)length : -EINVAL;
    DPRINTF("POPS_XIO_FAIL stage=size result=%d\n", result);
  } else {
    int64_t position = fileXioLseek64(fd, 0, SEEK_SET);
    if (position != 0) {
      result = position < 0 ? (int)position : -EIO;
      DPRINTF("POPS_XIO_FAIL stage=rewind result=%d\n", result);
    }
  }
  while (!result && total < (size_t)length) {
    size_t count = (size_t)length - total;
    if (count > sizeof(bounce))
      count = sizeof(bounce);
    /* Keep every RPC DMA target aligned, including after short reads. */
    int received = fileXioRead(fd, bounce, (int)count);
    if (received <= 0 || (size_t)received > count) {
      result = received < 0 ? received : -EIO;
      DPRINTF("POPS_XIO_FAIL stage=read result=%d offset=%u requested=%u returned=%d\n",
              result, (unsigned)total, (unsigned)count, received);
      break;
    }
    memcpy((unsigned char *)buffer + total, bounce, (size_t)received);
    total += (size_t)received;
  }
  int closed = fileXioClose(fd);
  if (!result && closed) {
    result = closed < 0 ? closed : -EIO;
    DPRINTF("POPS_XIO_FAIL stage=close result=%d bytes=%u\n", result, (unsigned)total);
  }
  if (!result) {
    uint8_t digest[32];
    char hex[65];
    result = pops_image_sha256(buffer, total, digest);
    if (!result) {
      static const char digits[] = "0123456789abcdef";
      for (unsigned i = 0; i < sizeof(digest); ++i) {
        hex[2*i] = digits[digest[i] >> 4];
        hex[2*i+1] = digits[digest[i] & 15];
      }
      hex[64] = '\0';
      DPRINTF("POPS_XIO complete bytes=%u sha256=%s\n", (unsigned)total, hex);
    }
  }
  return result;
}
#endif
