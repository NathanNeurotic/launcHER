/* Host stand-ins for everything launcher/src/handler_smb.c calls: files on
 * the memory cards, the SMB driver's device-control call, the on-screen
 * message and the SB. launch flag. Every call is appended to a text trace
 * that tools/test_pops_smb_config.py reads back. */
#include <errno.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "handler_smb.h"

#define MAX_FILES 16
static struct {
  char path[96];
  unsigned char *data;
  int size;
} files[MAX_FILES];
static int file_count, sb_launch, read_chunk, read_error, close_error;
static int open_fd = -1, open_file, open_pos, next_fd;
static struct {
  unsigned cmd;
  int result;
} results[8];
static int result_count;
static char trace[1 << 18];
static size_t trace_len;

static void note(const char *fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  if (trace_len < sizeof(trace) - 1) {
    int n = vsnprintf(trace + trace_len, sizeof(trace) - trace_len, fmt, ap);
    if (n > 0)
      trace_len += (size_t)n < sizeof(trace) - trace_len ? (size_t)n : sizeof(trace) - trace_len - 1;
  }
  va_end(ap);
}

void host_reset(void) {
  for (int i = 0; i < file_count; ++i)
    free(files[i].data);
  file_count = sb_launch = read_chunk = read_error = close_error = result_count = 0;
  open_fd = -1;
  next_fd = 3;
  trace_len = 0;
  trace[0] = 0;
  launcher_smb_reset();
}

void host_clear_trace(void) {
  trace_len = 0;
  trace[0] = 0;
}

int host_add_file(const char *path, const unsigned char *data, int size) {
  if (file_count == MAX_FILES || strlen(path) >= sizeof(files[0].path))
    return -1;
  strcpy(files[file_count].path, path);
  files[file_count].data = malloc(size ? (size_t)size : 1);
  memcpy(files[file_count].data, data, (size_t)size);
  files[file_count].size = size;
  return file_count++;
}

void host_set_sb(int active) { sb_launch = active; }
void host_set_read_chunk(int bytes) { read_chunk = bytes; }
void host_set_read_error(int error) { read_error = error; }
void host_set_close_error(int error) { close_error = error; }
void host_set_result(unsigned cmd, int result) {
  results[result_count].cmd = cmd;
  results[result_count++].result = result;
}
const char *host_trace(void) { return trace; }

/* initTCPIPArguments: -1 for NULL, else the length; the bytes go to `out`. */
int host_tcpip(unsigned char *out, int capacity) {
  uint32_t length = 0xABCD1234u;
  char *args = initTCPIPArguments(&length);
  if (!args) {
    note("tcpip NULL\n");
    return -1;
  }
  note("tcpip %u\n", (unsigned)length);
  if ((int)length <= capacity)
    memcpy(out, args, length);
  free(args);
  return (int)length;
}

int host_connect(void) {
  int result = launcher_smb_connect();
  note("connect %d\n", result);
  return result;
}

int pops_get_active_sb_launch(void) { return sb_launch; }

int fileXioOpen(const char *path, int flags, ...) {
  for (int i = 0; i < file_count; ++i) {
    if (!strcmp(files[i].path, path)) {
      open_fd = next_fd++;
      open_file = i;
      open_pos = 0;
      note("open %s %d = %d\n", path, flags, open_fd);
      return open_fd;
    }
  }
  note("open %s %d = %d\n", path, flags, -ENOENT);
  return -ENOENT;
}

int fileXioRead(int fd, void *buffer, int size) {
  int n;
  if (fd != open_fd) {
    note("read on a closed file\n");
    return -EBADF;
  }
  if (read_error) {
    note("read %d = %d\n", size, read_error);
    return read_error;
  }
  n = files[open_file].size - open_pos;
  if (n > size)
    n = size;
  if (read_chunk && n > read_chunk)
    n = read_chunk;
  memcpy(buffer, files[open_file].data + open_pos, (size_t)n);
  open_pos += n;
  note("read %d = %d\n", size, n);
  return n;
}

int fileXioClose(int fd) {
  note("close %s\n", fd == open_fd ? "ok" : "unknown");
  open_fd = -1;
  return close_error;
}

int fileXioDevctl(const char *name, int cmd, void *arg, unsigned arglen, void *out, unsigned outlen) {
  int result = 0;
  note("devctl %s %08x %u", name, (unsigned)cmd, arglen);
  for (unsigned i = 0; arg && i < arglen; ++i)
    note("%s%02x", i ? "" : " ", ((unsigned char *)arg)[i]);
  for (int i = 0; i < result_count; ++i)
    if (results[i].cmd == (unsigned)cmd)
      result = results[i].result;
  note(" out=%d/%u = %d\n", out != NULL, outlen, result);
  return result;
}

void msg(const char *fmt, ...) {
  va_list ap;
  char line[256];
  va_start(ap, fmt);
  vsnprintf(line, sizeof(line), fmt, ap);
  va_end(ap);
  note("msg %s", line);
}
