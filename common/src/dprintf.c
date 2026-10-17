#include "dprintf.h"
#include <debug.h>
#include <sio.h>
#include <stdarg.h>
#include <stdio.h>

#ifdef LAUNCHER_BOOT_TRACE
extern void initScreen(void);
int boot_trace_vprintf(const char *format, va_list args) {
  static char history[10][256];
  static unsigned next, count;
  char text[1024];
  int size = vsnprintf(text, sizeof(text), format, args);
  snprintf(history[next], sizeof(history[next]), "%s", text);
  next = (next + 1) % 10;
  if (count < 10) ++count;
  initScreen();
  scr_clear(); scr_setXY(0, 2);
  for (unsigned i = 0; i < count; ++i)
    scr_printf("%s", history[(next + 10 - count + i) % 10]);
  if (size > 0) sio_write(text, (unsigned)size < sizeof(text) ? size : sizeof(text)-1);
  return size;
}
int boot_trace_printf(const char *format, ...) {
  va_list args;
  va_start(args, format);
  int size = boot_trace_vprintf(format, args);
  va_end(args);
  return size;
}
#endif

// printf implementation for EE SIO
int sio_printf(const char *format, ...) {
  static char buf[1024];
  va_list args;
  int size;

  va_start(args, format);
  size = vsnprintf(buf, 1024, format, args);
  va_end(args);

  sio_write(buf, size);

  return size;
}
