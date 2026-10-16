#include "handler_smb.h"
#include "network_config.h"
#include "common.h"
#include <ps2smb.h>
#define NEWLIB_PORT_AWARE
#include <fileXio_rpc.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static int connected;
void launcher_smb_reset(void) { connected = 0; }

/* Network bootstrap files must be reachable before a share is mounted.
 * RiptOPL writes POPStarter network files in these memory-card directories. */
static int read_config(const char *name, char *out, size_t capacity) {
  static const char *const dirs[] = {
    "mc0:/POPSTARTER/", "mc1:/POPSTARTER/", "mc0:/POPS/", "mc1:/POPS/",
    "mc0:/SYS-CONF/", "mc1:/SYS-CONF/"
  };
  char path[80];
  for (unsigned i = 0; i < sizeof(dirs)/sizeof(dirs[0]); ++i) {
    snprintf(path, sizeof(path), "%s%s", dirs[i], name);
    int fd = open(path, O_RDONLY);
    if (fd < 0 && errno == ENOENT) {
      for (size_t j = strlen(dirs[i]); path[j]; ++j)
        if (path[j] >= 'A' && path[j] <= 'Z') path[j] += 'a' - 'A';
      fd = open(path, O_RDONLY);
    }
    if (fd < 0) {
      if (errno != ENOENT && errno != ENODEV && errno != ENXIO) return -errno;
      continue;
    }
    size_t used = 0;
    int result = 0;
    while (used < capacity) {
      ssize_t n = read(fd, out+used, capacity-used);
      if (n < 0) { result = -errno; break; }
      if (!n) break;
      used += (size_t)n;
    }
    if (close(fd) < 0 && !result) result = -errno;
    if (result) return result;
    return used == capacity ? -EFBIG : (int)used;
  }
  return -ENOENT;
}

char *initTCPIPArguments(uint32_t *length) {
  char text[128], packed[48];
  size_t size;
  int n = read_config("IPCONFIG.DAT", text, sizeof(text));
  if (n < 0 || !launcher_parse_tcpip_config(text, (size_t)n, packed, &size)) {
    msg("SMB: IPCONFIG.DAT must contain console IP, netmask and gateway\n");
    return NULL;
  }
  char *args = malloc(size);
  if (!args) return NULL;
  memcpy(args, packed, size);
  *length = (uint32_t)size;
  return args;
}

int launcher_smb_connect(void) {
  char text[1024];
  LauncherSmbConfig config;
  smbLogOn_in_t logon;
  smbOpenShare_in_t share;
  if (connected) return 0;
  int result = read_config("SMBCONFIG.DAT", text, sizeof(text));
  if (result < 0) return result;
  if (!launcher_parse_smb_config(text, (size_t)result, &config)) {
    memset(text, 0, sizeof(text));
    msg("SMB: Invalid SMBCONFIG.DAT\n");
    return -EINVAL;
  }
  memset(&logon, 0, sizeof(logon));
  memset(&share, 0, sizeof(share));
  memcpy(logon.serverIP, config.server, sizeof(logon.serverIP));
  logon.serverPort = config.port;
  memcpy(logon.User, config.user, sizeof(logon.User));
  memcpy(logon.Password, config.password, sizeof(logon.Password));
  logon.PasswordType = config.password[0] ? PLAINTEXT_PASSWORD : NO_PASSWORD;
  memcpy(share.ShareName, config.share, sizeof(share.ShareName));
  memcpy(share.Password, config.password, sizeof(share.Password));
  share.PasswordType = logon.PasswordType;
  result = fileXioDevctl("smb:", SMB_DEVCTL_LOGON, &logon, sizeof(logon), NULL, 0);
  if (result >= 0) {
    result = fileXioDevctl("smb:", SMB_DEVCTL_OPENSHARE, &share, sizeof(share), NULL, 0);
    if (result < 0)
      fileXioDevctl("smb:", SMB_DEVCTL_LOGOFF, NULL, 0, NULL, 0);
  }
  memset(text, 0, sizeof(text));
  memset(&config, 0, sizeof(config));
  memset(&logon, 0, sizeof(logon));
  memset(&share, 0, sizeof(share));
  if (result < 0) {
    msg("SMB: Login/share setup failed: %d\n", result);
    return result;
  }
  connected = 1;
  return 0;
}
