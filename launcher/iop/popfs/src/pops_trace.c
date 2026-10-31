#include "pops_trace.h"
#include "irx_imports.h"
#include <errno.h>

/* Trace state: -1 = not initialized, 0 = disabled (open failed or no
 * device), >0 = file descriptor. */
static int pops_trace_fd = -1;
static int pops_trace_events = 0;
static char pops_trace_path[32];

void pops_trace_reset(void)
{
  if (pops_trace_fd > 0)
    iomanX_close(pops_trace_fd);
  pops_trace_fd = -1;
  pops_trace_events = 0;
  pops_trace_path[0] = 0;
}

void pops_trace_init(const char *disc0_path)
{
  size_t i;
  if (!disc0_path)
    return;
  for (i = 0; i < sizeof(pops_trace_path) - 16 && disc0_path[i]; ++i) {
    pops_trace_path[i] = disc0_path[i];
    if (disc0_path[i] == ':') {
      ++i;
      break;
    }
  }
  if (i == 0 || pops_trace_path[i - 1] != ':')
    return;
  pops_trace_path[i] = 0;
  /* iomanX imported string helpers only go through what the module links;
   * build the suffix manually to stay within the existing imports. */
  {
    static const char suffix[] = "popfs_trace.log";
    size_t j;
    for (j = 0; j < sizeof(suffix); ++j)
      pops_trace_path[i + j] = suffix[j];
  }
  pops_trace_fd = -1; /* opened lazily on first event */
}

static void pops_trace_u32(char *out, size_t out_size, uint32_t value)
{
  char tmp[10];
  size_t n = 0, k;
  if (value == 0) {
    if (out_size > 1)
      out[0] = '0', out[1] = 0;
    return;
  }
  while (value && n < sizeof(tmp)) {
    tmp[n++] = (char)('0' + value % 10);
    value /= 10;
  }
  if (n >= out_size)
    n = out_size - 1;
  for (k = 0; k < n; ++k)
    out[k] = tmp[n - 1 - k];
  out[n] = 0;
}

void pops_trace_event(const char *kind, uint32_t a, uint32_t b, uint32_t c)
{
  char line[96];
  char na[11], nb[11], nc[11];
  size_t pos = 0;

  if (pops_trace_path[0] == 0)
    return;
  if (pops_trace_events >= POPS_TRACE_EVENT_LIMIT)
    return;
  if (pops_trace_fd == -1) {
    pops_trace_fd = iomanX_open(pops_trace_path,
                                FIO_O_WRONLY | FIO_O_CREAT | FIO_O_APPEND, 0644);
    if (pops_trace_fd < 0) {
      pops_trace_fd = 0; /* disabled */
      return;
    }
  } else if (pops_trace_fd == 0) {
    return;
  }

  pops_trace_u32(na, sizeof(na), a);
  pops_trace_u32(nb, sizeof(nb), b);
  pops_trace_u32(nc, sizeof(nc), c);

#define PUT(s) do { const char *p_ = (s); while (*p_ && pos < sizeof(line) - 1) line[pos++] = *p_++; } while (0)
  PUT("POPFS event=");
  PUT(kind);
  PUT(" a="); PUT(na);
  PUT(" b="); PUT(nb);
  PUT(" c="); PUT(nc);
  PUT("\n");
#undef PUT
  line[pos] = 0;

  (void)iomanX_write(pops_trace_fd, line, (int)pos);
  pops_trace_events++;
}
