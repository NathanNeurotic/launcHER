#include "handler_smb.h"
#include "network_config.h"
#include "common.h"
#include "launch_args.h"
#include "pops_smb_config.h"
#include <ps2smb.h>
#define NEWLIB_PORT_AWARE
#include <fileXio_rpc.h>
#include <io_common.h>
#include <errno.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

static int connected;
static int popsTarget;
void launcher_smb_reset(void) { connected = 0; }
void launcher_smb_set_pops_target(int pops) { popsTarget = pops; }
/* POPStarter's rules: a PS1 target and an SB. name, both. */
static int sb_rules(void) { return popsTarget && pops_get_active_sb_launch(); }

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
    int fd = fileXioOpen(path, FIO_O_RDONLY, 0);
    if (fd < 0) {
      for (size_t j = strlen(dirs[i]); path[j]; ++j)
        if (path[j] >= 'A' && path[j] <= 'Z') path[j] += 'a' - 'A';
      fd = fileXioOpen(path, FIO_O_RDONLY, 0);
    }
    if (fd < 0) continue;
    size_t used = 0;
    int result = 0;
    while (used < capacity) {
      int n = fileXioRead(fd, out + used, (int)(capacity - used));
      if (n < 0) { result = n; break; }
      if (!n) break;
      used += (size_t)n;
    }
    int close_ret = fileXioClose(fd);
    if (close_ret < 0 && !result) result = close_ret;
    if (result) return result;
    return used == capacity ? -EFBIG : (int)used;
  }
  return -ENOENT;
}

/* An SB. launch reads the two files the way POPStarter r13 does: its two
 * places first, and the first file that opens is the file. Returns the
 * number of bytes read, `capacity` standing for that many or more. */
static int read_sb_config(const char *name, unsigned char *out, int capacity) {
  char path[80];
  for (unsigned i = 0; pops_netconfig_path(i, name, path, sizeof(path)); ++i) {
    int fd = fileXioOpen(path, FIO_O_RDONLY, 0);
    if (fd < 0) continue;
    int used = 0, result = 0;
    while (used < capacity) {
      int n = fileXioRead(fd, out + used, capacity - used);
      if (n < 0) { result = n; break; }
      if (!n) break;
      used += n;
    }
    int close_ret = fileXioClose(fd);
    if (close_ret < 0 && !result) result = close_ret;
    return result ? result : used;
  }
  return -ENOENT;
}

/* POPStarter's rules (common/src/pops_smb_config.c). Without the file its
 * network module is started with no arguments at all. */
static char *sb_tcpip_arguments(uint32_t *length) {
  unsigned char text[POPS_IPCONFIG_BUFFER];
  int size = 0;
  memset(text, 0, sizeof(text));
  int n = read_sb_config("IPCONFIG.DAT", text, sizeof(text));
  if (n < 0 && n != -ENOENT) {
    msg("SMB: Cannot read IPCONFIG.DAT: %d\n", n);
    return NULL;
  }
  if (n >= 0) {
    int error = pops_parse_ipconfig(text, n, &size);
    if (error) {
      msg(error == POPS_NETCONFIG_SIZE ? "SMB: Cannot load IPCONFIG.DAT (7 to 127 bytes)\n"
                                       : "SMB: IPCONFIG.DAT syntax error\n");
      return NULL;
    }
  }
  /* A NULL return is an error to the caller; a zero length passes nothing. */
  char *args = malloc(size ? (size_t)size : 1);
  if (!args) return NULL;
  args[0] = 0;
  memcpy(args, text, (size_t)size);
  *length = (uint32_t)size;
  return args;
}

static const char *sb_config_error(int error) {
  switch (error) {
    case POPS_NETCONFIG_SIZE: return "cannot load (7 to 4095 bytes)";
    case POPS_NETCONFIG_NO_SHARE: return "syntax error, no shared folder name";
    case POPS_NETCONFIG_SERVER_LENGTH: return "syntax error, server address too long";
    case POPS_NETCONFIG_BAD_PORT: return "syntax error, bad port";
    case POPS_NETCONFIG_OVERFLOW: return "a name or password is too long";
    default: return "invalid";
  }
}

static int sb_connect(void) {
  unsigned char text[POPS_SMBCONFIG_BUFFER];
  smbLogOn_in_t logon;
  smbOpenShare_in_t share;
  smbEcho_in_t echo;
  _Static_assert(sizeof(logon) == POPS_SMB_LOGON_SIZE, "smbLogOn_in_t layout");
  _Static_assert(sizeof(share) == POPS_SMB_SHARE_SIZE, "smbOpenShare_in_t layout");
  _Static_assert(sizeof(echo) == POPS_SMB_ECHO_SIZE, "smbEcho_in_t layout");
  int result = read_sb_config("SMBCONFIG.DAT", text, sizeof(text));
  if (result == -ENOENT)
    msg("SMB: SMBCONFIG.DAT not found on a memory card\n");
  if (result < 0) return result;
  int error = pops_parse_smbconfig(text, result, (unsigned char *)&logon, (unsigned char *)&share);
  memset(text, 0, sizeof(text));
  if (error) {
    memset(&logon, 0, sizeof(logon));
    memset(&share, 0, sizeof(share));
    msg("SMB: SMBCONFIG.DAT: %s\n", sb_config_error(error));
    return -EINVAL;
  }
  /* The original's order (0x874128..0x8741a0): log on, echo, open the share,
   * each stopping the launch on a negative result. NOT TESTED on a console. */
  result = fileXioDevctl("smb:", SMB_DEVCTL_LOGON, &logon, sizeof(logon), NULL, 0);
  if (result >= 0) {
    pops_smb_echo_request((unsigned char *)&echo);
    result = fileXioDevctl("smb:", SMB_DEVCTL_ECHO, &echo, sizeof(echo), NULL, 0);
    if (result >= 0)
      result = fileXioDevctl("smb:", SMB_DEVCTL_OPENSHARE, &share, sizeof(share), NULL, 0);
    if (result < 0)
      fileXioDevctl("smb:", SMB_DEVCTL_LOGOFF, NULL, 0, NULL, 0);
  }
  memset(&logon, 0, sizeof(logon));
  memset(&share, 0, sizeof(share));
  if (result < 0) {
    msg("SMB: Login/share setup failed: %d\n", result);
    return result;
  }
  connected = 1;
  return 0;
}

char *initTCPIPArguments(uint32_t *length) {
  if (sb_rules())
    return sb_tcpip_arguments(length);
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
  if (sb_rules())
    return sb_connect();
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
