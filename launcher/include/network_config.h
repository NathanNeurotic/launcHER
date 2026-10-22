#ifndef LAUNCHER_NETWORK_CONFIG_H
#define LAUNCHER_NETWORK_CONFIG_H
#include <stddef.h>

typedef struct {
  char server[16];
  int port;
  char share[256], user[256], password[256];
} LauncherSmbConfig;

/* RiptOPL/POPStarter: "IPv4[:port] share\nuser\npassword\n".
 * Empty credential lines mean guest. Input is bounded and never logged. */
int launcher_parse_smb_config(const char *text, size_t size, LauncherSmbConfig *out);
/* SDK ps2ip-nm needs three separate NUL-terminated arguments. */
int launcher_parse_tcpip_config(const char *text, size_t size, char packed[48], size_t *length);
#endif
