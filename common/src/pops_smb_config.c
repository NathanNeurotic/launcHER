#include "pops_smb_config.h"

#include <string.h>

/* A transliteration of POPStarter r13's own two readers, statement for
 * statement where the order of its writes decides the result. Addresses in
 * the comments are in POPSTARTER MAIN as unpacked at 0x870000. */

static void put_int(unsigned char *at, int value) {
  unsigned int v = (unsigned int)value;
  at[0] = (unsigned char)v;
  at[1] = (unsigned char)(v >> 8);
  at[2] = (unsigned char)(v >> 16);
  at[3] = (unsigned char)(v >> 24);
}

void pops_smbconfig_defaults(unsigned char logon[POPS_SMB_LOGON_SIZE],
                             unsigned char share[POPS_SMB_SHARE_SIZE]) {
  static const char user[] = "POPStarter"; /* 0x8717b8 */
  memset(logon, 0, POPS_SMB_LOGON_SIZE);
  memset(share, 0, POPS_SMB_SHARE_SIZE);
  memcpy(logon + POPS_SMB_LOGON_USER, user, sizeof(user));
  put_int(logon + POPS_SMB_LOGON_PASSWORD_TYPE, -1);
  put_int(logon + POPS_SMB_LOGON_PORT, 445);
  put_int(share + POPS_SMB_SHARE_PASSWORD_TYPE, -1);
}

void pops_smb_echo_request(unsigned char echo[POPS_SMB_ECHO_SIZE]) {
  static const char text[] = "ALIVE ECHO TEST"; /* 0x871820 */
  memset(echo, 0, POPS_SMB_ECHO_SIZE);
  memcpy(echo, text, sizeof(text));
  put_int(echo + POPS_SMB_ECHO_LENGTH, (int)sizeof(text) - 1);
}

int pops_parse_ipconfig(unsigned char *text, int size, int *length) {
  int count = 0;
  int i;
  if (size < POPS_NETCONFIG_MIN_SIZE || size >= POPS_IPCONFIG_BUFFER)
    return POPS_NETCONFIG_SIZE; /* 0x8722f8 (mc0), 0x8723b8 (mc1) */
  text[size] = 0;
  /* 0x872480 counts, 0x872570 replaces: TAB is not a separator. */
  for (i = 0; i < size; ++i) {
    if (text[i] == ' ' || text[i] == '\r' || text[i] == '\n') {
      text[i] = 0;
      ++count;
    }
  }
  if (count < 2)
    return POPS_NETCONFIG_IP_SYNTAX; /* 0x872544 */
  *length = size - count; /* 0x872624 */
  return POPS_NETCONFIG_OK;
}

/* strcpy into a structure image. 0 when the original's write would pass the
 * end of the structure. */
static int copy_string(unsigned char *image, int image_size, int offset,
                       const unsigned char *text) {
  size_t n = strlen((const char *)text) + 1;
  if (n > (size_t)(image_size - offset))
    return 0;
  memcpy(image + offset, text, n);
  return 1;
}

/* A line feed that is not the last byte of the text. */
static int line_break(const unsigned char *text, int at) {
  return text[at] == '\n' && text[at + 1] != 0;
}

int pops_parse_smbconfig(unsigned char *text, int size,
                         unsigned char logon[POPS_SMB_LOGON_SIZE],
                         unsigned char share[POPS_SMB_SHARE_SIZE]) {
  int i, j, n, breaks = 0;

  pops_smbconfig_defaults(logon, share);
  if (size < POPS_NETCONFIG_MIN_SIZE || size >= POPS_SMBCONFIG_BUFFER)
    return POPS_NETCONFIG_SIZE; /* 0x872674 (mc0), 0x872734 (mc1) */
  /* The original's buffer is zero beyond the file. */
  memset(text + size, 0, (size_t)(POPS_SMBCONFIG_BUFFER - size));

  /* 0x87280c: a user name and a password need two line breaks. */
  for (j = 0; j < size; ++j)
    if (line_break(text, j))
      ++breaks;
  if (breaks >= 2) {
    put_int(logon + POPS_SMB_LOGON_PASSWORD_TYPE, 0); /* 0x87288c */
    for (i = 0; i < size; ++i) {
      if (!line_break(text, i))
        continue;
      ++i; /* first byte of the user name */
      for (j = i; j < size; ++j) {
        if (!line_break(text, j))
          continue;
        ++j; /* first byte of the password */
        text[j - 1] = 0;
        if (text[j - 2] == '\r')
          text[j - 2] = 0;
        if (!copy_string(logon, POPS_SMB_LOGON_SIZE, POPS_SMB_LOGON_USER, text + i))
          return POPS_NETCONFIG_OVERFLOW; /* 0x8729a0 */
        for (i = j; i < size; ++i) {
          if (text[i] == '\n') {
            text[i] = 0;
            if (text[i - 1] == '\r')
              text[i - 1] = 0;
            break;
          }
        }
        if (!copy_string(logon, POPS_SMB_LOGON_SIZE, POPS_SMB_LOGON_PASSWORD, text + j))
          return POPS_NETCONFIG_OVERFLOW; /* 0x872a50 */
        break;
      }
    }
  }

  for (j = 0; j < size; ++j) /* 0x872a84 */
    if (text[j] == '\r' || text[j] == '\n')
      text[j] = 0;

  /* 0x872b04: the shared folder follows the first space of the file. */
  for (j = 0; j < size; ++j) {
    if (text[j] != ' ')
      continue;
    text[j] = 0;
    /* A ':' inside the name starts the share's own password. The last
     * byte of the name is never looked at. */
    for (i = j; text[i + 1] != 0; ++i) {
      if (text[i] == ':') {
        text[i] = 0;
        if (!copy_string(share, POPS_SMB_SHARE_SIZE, POPS_SMB_SHARE_PASSWORD, text + i + 1))
          return POPS_NETCONFIG_OVERFLOW; /* 0x872bd4 */
        put_int(share + POPS_SMB_SHARE_PASSWORD_TYPE, 0);
        break;
      }
    }
    /* 0x872c30: strncpy of exactly the name's length, so no terminator is
     * written and a name over 255 bytes runs on into the password. */
    n = (int)strlen((const char *)text + j + 1);
    if (n > POPS_SMB_SHARE_SIZE)
      return POPS_NETCONFIG_OVERFLOW;
    memcpy(share + POPS_SMB_SHARE_NAME, text + j + 1, (size_t)n);
    break;
  }
  if (j == size)
    return POPS_NETCONFIG_NO_SHARE; /* 0x872c7c */

  if (strlen((const char *)text) >= 0x16)
    return POPS_NETCONFIG_SERVER_LENGTH; /* 0x872cc0 */

  /* 0x872cd0: a ':' in the first 17 bytes starts the port. */
  for (j = 0; j < 0x11; ++j) {
    int port = 0;
    if (text[j] != ':')
      continue;
    text[j] = 0;
    ++j;
    n = (int)strlen((const char *)text + j);
    if (n == 0 || n >= 6)
      return POPS_NETCONFIG_BAD_PORT;
    for (i = 0; i < n; ++i) {
      if (text[j + i] < '0' || text[j + i] > '9')
        return POPS_NETCONFIG_BAD_PORT;
      port = port * 10 + (text[j + i] - '0');
    }
    if (port > 0xffff)
      return POPS_NETCONFIG_BAD_PORT; /* 0x87327c */
    put_int(logon + POPS_SMB_LOGON_PORT, port);
    break;
  }

  /* 0x8732b8: the server is written last, again without a terminator; 17
   * to 21 bytes run on into the port and the first byte of the user. */
  n = (int)strlen((const char *)text);
  memcpy(logon + POPS_SMB_LOGON_SERVER, text, (size_t)n);
  return POPS_NETCONFIG_OK;
}

int pops_netconfig_path(unsigned index, const char *name, char *out, size_t capacity) {
  /* The original's two places first, then the launcher's: the same two with
   * a lower-case name, then its other memory-card directories. */
  static const char *const dirs[] = {"mc0:/POPSTARTER/", "mc1:/POPSTARTER/",
                                     "mc0:/POPSTARTER/", "mc1:/POPSTARTER/",
                                     "mc0:/POPS/", "mc0:/POPS/", "mc1:/POPS/", "mc1:/POPS/",
                                     "mc0:/SYS-CONF/", "mc0:/SYS-CONF/",
                                     "mc1:/SYS-CONF/", "mc1:/SYS-CONF/"};
  static const unsigned char lower[] = {0, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1};
  size_t dir_length, name_length, i;
  if (!name || !out || index >= sizeof(dirs) / sizeof(dirs[0]))
    return 0;
  dir_length = strlen(dirs[index]);
  name_length = strlen(name);
  if (dir_length + name_length + 1 > capacity)
    return 0;
  memcpy(out, dirs[index], dir_length);
  for (i = 0; i <= name_length; ++i) {
    char c = name[i];
    if (lower[index] && c >= 'A' && c <= 'Z')
      c = (char)(c + ('a' - 'A'));
    out[dir_length + i] = c;
  }
  return 1;
}
