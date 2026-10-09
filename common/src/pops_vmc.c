#include "pops_vmc.h"
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int io_error(void) { return errno ? -errno : -EIO; }

/* PS1 raw-card block 0: ID, 15 free entries, 20 absent broken-sector entries,
 * replacement/unused frames, and write-test frame. See psx-spx's card format. */
static void format_frame(unsigned index, uint8_t frame[128]) {
  unsigned i;
  memset(frame, 0, 128);
  if (index == 0 || index == 63) {
    frame[0] = 'M';
    frame[1] = 'C';
  } else if (index < 16) {
    frame[0] = 0xa0;
    frame[8] = frame[9] = 0xff;
  } else if (index < 36) {
    memset(frame, 0xff, 4);
  } else if (index < 63) {
    memset(frame, 0xff, 128);
    return;
  }
  for (i = 0; i < 127; ++i)
    frame[127] ^= frame[i];
}

int pops_vmc_ensure(const char *path) {
  char parent[1024];
  uint8_t frame[128];
  unsigned index;
  int fd, result;
  off_t size;
  const char *slash, *backslash;
  if (!path || !*path)
    return -EINVAL;
  if (strlen(path) >= sizeof(parent))
    return -ENAMETOOLONG;

  fd = open(path, O_RDONLY);
  if (fd >= 0) {
    size = lseek(fd, 0, SEEK_END);
    result = size < 0 ? io_error() : (size == 131072 ? 0 : -EINVAL);
    if (close(fd) < 0 && result == 0)
      result = io_error();
    return result;
  }
  /* An unreadable existing card must never be mistaken for a missing card. */
  if (errno != ENOENT)
    return io_error();

  slash = strrchr(path, '/');
  backslash = strrchr(path, '\\');
  if (backslash && (!slash || backslash > slash))
    slash = backslash;
  if (slash && slash != path && slash[-1] != ':') {
    size_t length = (size_t)(slash - path);
    memcpy(parent, path, length);
    parent[length] = '\0';
    if (mkdir(parent, 0777) < 0 && errno != EEXIST)
      return io_error();
  }

  /* O_EXCL also protects a card created between the read probe and creation. */
  fd = open(path, O_WRONLY | O_CREAT | O_EXCL, 0644);
  if (fd < 0)
    return io_error();
  result = 0;
  for (index = 0; index < 1024; ++index) {
    size_t offset = 0;
    format_frame(index, frame);
    while (offset < sizeof(frame)) {
      ssize_t written = write(fd, frame + offset, sizeof(frame) - offset);
      if (written < 0 && errno == EINTR)
        continue;
      if (written <= 0) {
        result = written < 0 ? io_error() : -EIO;
        break;
      }
      offset += (size_t)written;
    }
    if (result)
      break;
  }
  if (close(fd) < 0 && result == 0)
    result = io_error();
  /* Only this call's exclusively-created, incomplete file may be removed. */
  if (result)
    unlink(path);
  return result;
}
