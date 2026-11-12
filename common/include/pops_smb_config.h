#ifndef POPS_SMB_CONFIG_H
#define POPS_SMB_CONFIG_H

#include <stddef.h>

/* POPStarter r13's rules for the two network files of an SB. launch,
 * IPCONFIG.DAT and SMBCONFIG.DAT (its launch function, 0x8722bc..0x87345c).
 * Pure buffer logic: nothing here opens a file or talks to a driver.
 * Rules, addresses and evidence: docs/POPSTARTER_SMB_CONFIG.md. */

/* The original reads IPCONFIG.DAT into a 128-byte buffer and SMBCONFIG.DAT
 * into a 4096-byte one, and accepts a file of 7 bytes up to one less than
 * the buffer. */
#define POPS_IPCONFIG_BUFFER 128
#define POPS_SMBCONFIG_BUFFER 4096
#define POPS_NETCONFIG_MIN_SIZE 7

/* The driver structures the original fills, as byte images (ps2smb.h:
 * smbLogOn_in_t, smbOpenShare_in_t, smbEcho_in_t). */
#define POPS_SMB_LOGON_SIZE 0x218
#define POPS_SMB_LOGON_SERVER 0x000 /* char[16] */
#define POPS_SMB_LOGON_PORT 0x010   /* int */
#define POPS_SMB_LOGON_USER 0x014   /* char[256] */
#define POPS_SMB_LOGON_PASSWORD 0x114 /* char[256] */
#define POPS_SMB_LOGON_PASSWORD_TYPE 0x214 /* int */
#define POPS_SMB_SHARE_SIZE 0x204
#define POPS_SMB_SHARE_NAME 0x000   /* char[256] */
#define POPS_SMB_SHARE_PASSWORD 0x100 /* char[256] */
#define POPS_SMB_SHARE_PASSWORD_TYPE 0x200 /* int */
#define POPS_SMB_ECHO_SIZE 0x104
#define POPS_SMB_ECHO_LENGTH 0x100  /* int */

enum {
  POPS_NETCONFIG_OK = 0,
  /* The file is shorter than 7 bytes or does not fit its buffer. */
  POPS_NETCONFIG_SIZE,
  /* IPCONFIG.DAT: fewer than two space, CR or LF bytes. */
  POPS_NETCONFIG_IP_SYNTAX,
  /* SMBCONFIG.DAT: no space, so no shared folder name. */
  POPS_NETCONFIG_NO_SHARE,
  /* SMBCONFIG.DAT: 22 or more bytes before the first space. */
  POPS_NETCONFIG_SERVER_LENGTH,
  /* SMBCONFIG.DAT: the text after the server's ':' is not 1..5 decimal
   * digits, or is above 65535. */
  POPS_NETCONFIG_BAD_PORT,
  /* SMBCONFIG.DAT: a name or password long enough that the original writes
   * past the end of its driver structure, into unrelated globals. Not
   * reproduced: the file is refused instead. */
  POPS_NETCONFIG_OVERFLOW
};

/* IPCONFIG.DAT. `text` holds `size` file bytes and has room for
 * POPS_IPCONFIG_BUFFER; pass POPS_IPCONFIG_BUFFER as `size` for any file
 * that large or larger. On POPS_NETCONFIG_OK the argument block the original
 * hands its network module is the first *length bytes of `text` (every
 * space, CR and LF turned into NUL). *length is the file size minus the
 * number of those bytes, as the original computes it, so the block ends
 * that many bytes before the end of the text. */
int pops_parse_ipconfig(unsigned char *text, int size, int *length);

/* SMBCONFIG.DAT. `text` holds `size` file bytes and has room for
 * POPS_SMBCONFIG_BUFFER; pass POPS_SMBCONFIG_BUFFER as `size` for any file
 * that large or larger. `logon` and `share` receive the two driver
 * structures exactly as the original leaves them, starting from its
 * defaults (pops_smbconfig_defaults). `text` is consumed. */
int pops_parse_smbconfig(unsigned char *text, int size,
                         unsigned char logon[POPS_SMB_LOGON_SIZE],
                         unsigned char share[POPS_SMB_SHARE_SIZE]);

/* The values the original sets before it reads either file (0x871788..):
 * no server, port 445, its default user name, no passwords. */
void pops_smbconfig_defaults(unsigned char logon[POPS_SMB_LOGON_SIZE],
                             unsigned char share[POPS_SMB_SHARE_SIZE]);

/* The echo request the original sends between logging on and opening the
 * share (set at 0x871818..0x87182c). */
void pops_smb_echo_request(unsigned char echo[POPS_SMB_ECHO_SIZE]);

/* Where an SB. launch looks for a network file, in order. `name` is
 * "IPCONFIG.DAT" or "SMBCONFIG.DAT". Candidates 0 and 1 are the original's
 * (POPS_NETCONFIG_ORIGINAL_PATHS); the rest are the launcher's own extra
 * places. Returns 0 when `index` is past the last candidate or the path
 * does not fit. The first candidate that opens is the file: the original
 * never tries the second card after a file it could open but not accept. */
#define POPS_NETCONFIG_ORIGINAL_PATHS 2
int pops_netconfig_path(unsigned index, const char *name, char *out, size_t capacity);

#endif
