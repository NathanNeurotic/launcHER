#include "network_config.h"
#include "ipconfig_smap.h"
#include <string.h>
#include <stdio.h>

static int space(char c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; }

/* inet_addr treats leading zeroes as octal. Our text format uses decimal
 * dotted quads, so canonicalize before passing addresses to the SDK. */
static int ipv4(const char *text, size_t size, char out[16]) {
  char candidate[16];
  if (!smap_parse_ipconfig(text, size, candidate)) return 0;
  size_t pos = 0, used = 0;
  for (int part = 0; part < 4; ++part) {
    unsigned octet = 0;
    while (candidate[pos] >= '0' && candidate[pos] <= '9')
      octet = octet * 10 + (unsigned)(candidate[pos++] - '0');
    used += (size_t)snprintf(out+used, 16-used, "%s%u", part ? "." : "", octet);
    if (candidate[pos] == '.') ++pos;
  }
  return 1;
}

static int line(const char *text, size_t size, size_t *pos, char *out, size_t cap) {
  size_t n = 0;
  while (*pos < size && text[*pos] != '\r' && text[*pos] != '\n') {
    unsigned char c = (unsigned char)text[(*pos)++];
    if (c < 32 || n + 1 >= cap) return 0;
    out[n++] = (char)c;
  }
  out[n] = 0;
  if (*pos < size && text[*pos] == '\r') ++*pos;
  if (*pos < size && text[*pos] == '\n') ++*pos;
  return 1;
}

int launcher_parse_smb_config(const char *text, size_t size, LauncherSmbConfig *out) {
  LauncherSmbConfig cfg;
  char first[296], host[24];
  size_t pos = 0, i = 0, n = 0;
  if (!text || !out || !size || memchr(text, 0, size)) return 0;
  memset(&cfg, 0, sizeof(cfg));
  cfg.port = 445;
  if (!line(text, size, &pos, first, sizeof(first))) return 0;
  while (first[i] == ' ' || first[i] == '\t') ++i;
  while (first[i] && first[i] != ' ' && first[i] != '\t') {
    if (n + 1 >= sizeof(host)) return 0;
    host[n++] = first[i++];
  }
  host[n] = 0;
  char *port = strchr(host, ':');
  if (port) {
    *port++ = 0;
    unsigned value = 0;
    if (!*port) return 0;
    while (*port) {
      if (*port < '0' || *port > '9') return 0;
      value = value * 10 + (unsigned)(*port++ - '0');
      if (value > 65535) return 0;
    }
    if (!value) return 0;
    cfg.port = (int)value;
  }
  if (!ipv4(host, strlen(host), cfg.server)) return 0;
  while (first[i] == ' ' || first[i] == '\t') ++i;
  n = strlen(first + i);
  while (n && (first[i+n-1] == ' ' || first[i+n-1] == '\t')) --n;
  if (!n || n >= sizeof(cfg.share)) return 0;
  for (size_t j = 0; j < n; ++j)
    if (first[i+j] == '/' || first[i+j] == '\\' || first[i+j] == ':') return 0;
  memcpy(cfg.share, first+i, n);
  if (!line(text, size, &pos, cfg.user, sizeof(cfg.user)) ||
      !line(text, size, &pos, cfg.password, sizeof(cfg.password))) return 0;
  while (pos < size) if (!space(text[pos++])) return 0;
  *out = cfg;
  return 1;
}

int launcher_parse_tcpip_config(const char *text, size_t size, char packed[48], size_t *length) {
  char result[48];
  size_t pos = 0, used = 0;
  if (!text || !packed || !length || !size || memchr(text, 0, size)) return 0;
  for (int token = 0; token < 3; ++token) {
    char ip[16];
    while (pos < size && space(text[pos])) ++pos;
    size_t start = pos;
    while (pos < size && !space(text[pos])) ++pos;
    if (start == pos || !ipv4(text+start, pos-start, ip)) return 0;
    size_t n = strlen(ip)+1;
    memcpy(result+used, ip, n);
    used += n;
  }
  while (pos < size) if (!space(text[pos++])) return 0;
  memcpy(packed, result, used);
  *length = used;
  return 1;
}
