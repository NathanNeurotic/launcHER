#ifndef _DPRINTF_H_
#define _DPRINTF_H_

#include <stdio.h>
#include <stdarg.h>

// printf implementation for EE SIO
int sio_printf(const char *format, ...);

#ifdef LAUNCHER_BOOT_TRACE
int boot_trace_printf(const char *format, ...);
int boot_trace_vprintf(const char *format, va_list args);
#define DPRINTF(x...) boot_trace_printf(x)
#elif defined(ENABLE_PRINTF)
#ifndef USE_EESIO
#define DPRINTF(x...) printf(x)
#else
#define DPRINTF(x...) sio_printf(x)
#endif
#else
#define DPRINTF(x...)
#endif

#endif
