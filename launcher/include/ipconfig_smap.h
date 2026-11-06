#ifndef LAUNCHER_IPCONFIG_SMAP_H
#define LAUNCHER_IPCONFIG_SMAP_H
#include <stddef.h>

/* IPCONFIG.DAT starts with the console's dotted-quad IP address, optionally
 * followed by the netmask/gateway. Never assume the file is terminated, or
 * that the first token is 15 characters long. Pure helper for EE and host. */
static inline int smap_parse_ipconfig(const char *text, size_t length, char out[16]) {
  char candidate[16];
  size_t i = 0, copied = 0;
  unsigned dots = 0, digits = 0, octet = 0;
  if (!text || !out) return 0;
  while (i < length && (text[i] == ' ' || text[i] == '\t' ||
                        text[i] == '\r' || text[i] == '\n')) ++i;
  while (i < length) {
    char ch = text[i];
    if (ch == 0 || ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n')
      break;
    if (copied >= sizeof(candidate) - 1) return 0;
    if (ch == '.') {
      if (!digits || dots == 3) return 0;
      ++dots;
      digits = octet = 0;
    } else if (ch >= '0' && ch <= '9') {
      octet = octet * 10 + (unsigned)(ch - '0');
      if (++digits > 3 || octet > 255) return 0;
    } else return 0;
    candidate[copied++] = ch;
    ++i;
  }
  if (dots != 3 || !digits) return 0;
  candidate[copied] = '\0';
  for (i = 0; i <= copied; ++i) out[i] = candidate[i];
  return 1;
}
#endif
