#include "pops_vcd.h"
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>

static const uint8_t s_cd_sync[12] = {
    0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00
};

static uint32_t read_u32_le(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

int pops_vcd_normalize_serial(const char *raw, char *normalized, size_t norm_size) {
  if (!raw || !normalized || norm_size < 12)
    return -EINVAL;

  /* Skip any device/directory prefix e.g. "cdrom0:\" or "/" */
  const char *start = raw;
  const char *slash = strrchr(start, '/');
  const char *bslash = strrchr(start, '\\');
  if (bslash && (!slash || bslash > slash))
    slash = bslash;
  if (!slash) {
    const char *colon = strchr(start, ':');
    if (colon)
      start = colon + 1;
  } else {
    start = slash + 1;
  }

  while (*start == ' ' || *start == '\t')
    start++;

  /* Find end before ';', newline, or whitespace */
  const char *end = start;
  while (*end && *end != ';' && *end != '\r' && *end != '\n' && *end != ' ')
    end++;

  size_t len = (size_t)(end - start);
  if (len == 0 || len >= 64)
    return -EINVAL;

  char temp[64];
  size_t tpos = 0;
  for (size_t i = 0; i < len && tpos < sizeof(temp) - 1; ++i) {
    char c = start[i];
    if (isalnum((unsigned char)c) || c == '_' || c == '-' || c == '.') {
      temp[tpos++] = (char)toupper((unsigned char)c);
    }
  }
  temp[tpos] = '\0';

  /* Check standard PS1 serial format: ABCD_123.45 (11 chars) */
  if (tpos == 11 && temp[4] == '_' && temp[8] == '.') {
    if (norm_size < 11)
      return -ENAMETOOLONG;
    /* Convert ABCD_123.45 to ABCD-12345 */
    normalized[0] = temp[0];
    normalized[1] = temp[1];
    normalized[2] = temp[2];
    normalized[3] = temp[3];
    normalized[4] = '-';
    normalized[5] = temp[5];
    normalized[6] = temp[6];
    normalized[7] = temp[7];
    normalized[8] = temp[9];
    normalized[9] = temp[10];
    normalized[10] = '\0';
    return 0;
  }

  /* Check already normalized format: ABCD-12345 (10 chars) */
  if (tpos == 10 && temp[4] == '-') {
    if (norm_size <= 10)
      return -ENAMETOOLONG;
    memcpy(normalized, temp, 11);
    return 0;
  }

  /* Fallback: copy cleaned string */
  if (tpos >= norm_size)
    tpos = norm_size - 1;
  memcpy(normalized, temp, tpos);
  normalized[tpos] = '\0';
  return 0;
}

int pops_vcd_inspect_stream(void *user, PopsVcdReadFn read_fn, PopsVcdSeekFn seek_fn,
                            PopsVcdInfo *info) {
  if (!user || !read_fn || !seek_fn || !info)
    return -EINVAL;

  memset(info, 0, sizeof(*info));

  /* 1. Detect sector layout by reading first sector header */
  uint8_t header[32];
  if (seek_fn(user, 0, SEEK_SET) < 0)
    return -EIO;
  if (read_fn(user, header, sizeof(header)) != (int)sizeof(header))
    return -EIO;

  uint32_t sector_size = POPS_VCD_RAW_SECTOR_SIZE;
  uint32_t data_offset = 24; /* Mode 2 Form 1 default */

  if (!memcmp(header, s_cd_sync, 12)) {
    uint8_t mode = header[15];
    if (mode == 1) {
      data_offset = 16;
    } else {
      data_offset = 24;
    }
    sector_size = POPS_VCD_RAW_SECTOR_SIZE;
  } else {
    /* ISO 2048-byte sector mode */
    sector_size = POPS_VCD_ISO_SECTOR_SIZE;
    data_offset = 0;
  }

  info->sector_size = sector_size;
  info->data_offset = data_offset;
  info->pvd_lba = 16;

  /* 2. Read Primary Volume Descriptor (LBA 16) */
  int64_t pvd_file_offset = (int64_t)16 * sector_size + data_offset;
  if (seek_fn(user, pvd_file_offset, SEEK_SET) < 0)
    return -EIO;

  uint8_t pvd[2048];
  if (read_fn(user, pvd, sizeof(pvd)) != (int)sizeof(pvd))
    return -EIO;

  /* Verify PVD volume descriptor: Type 1, Identifier "CD001" */
  if (pvd[0] != 0x01 || memcmp(&pvd[1], "CD001", 5) != 0) {
    /* If failed and was raw 2352, try alternative offset 16 */
    if (sector_size == POPS_VCD_RAW_SECTOR_SIZE && data_offset != 16) {
      data_offset = 16;
      pvd_file_offset = (int64_t)16 * sector_size + data_offset;
      if (seek_fn(user, pvd_file_offset, SEEK_SET) < 0 ||
          read_fn(user, pvd, sizeof(pvd)) != (int)sizeof(pvd) ||
          pvd[0] != 0x01 || memcmp(&pvd[1], "CD001", 5) != 0) {
        return -EINVAL;
      }
      info->data_offset = data_offset;
    } else {
      return -EINVAL;
    }
  }

  /* Root directory record is located at PVD offset 156 (0x9C) */
  const uint8_t *root_record = &pvd[156];
  uint32_t root_lba = read_u32_le(&root_record[2]);
  uint32_t root_size = read_u32_le(&root_record[10]);

  info->root_lba = root_lba;
  info->root_size = root_size;

  if (root_size == 0 || root_lba == 0)
    return -EINVAL;

  /* 3. Search root directory for SYSTEM.CNF */
  uint32_t sys_lba = 0;
  uint32_t sys_size = 0;
  int found = 0;

  uint32_t sectors_to_read = (root_size + 2047) / 2048;
  if (sectors_to_read > 16)
    sectors_to_read = 16; /* Bounded directory scan */

  uint8_t dir_buf[2048];
  for (uint32_t s = 0; s < sectors_to_read && !found; ++s) {
    int64_t dir_offset = (int64_t)(root_lba + s) * sector_size + data_offset;
    if (seek_fn(user, dir_offset, SEEK_SET) < 0)
      break;
    if (read_fn(user, dir_buf, sizeof(dir_buf)) != (int)sizeof(dir_buf))
      break;

    uint32_t pos = 0;
    while (pos < sizeof(dir_buf) && !found) {
      uint8_t record_len = dir_buf[pos];
      if (record_len == 0 || pos + record_len > sizeof(dir_buf))
        break;

      uint8_t name_len = dir_buf[pos + 32];
      const char *name = (const char *)&dir_buf[pos + 33];
      uint8_t flags = dir_buf[pos + 25];

      /* Not a directory */
      if (!(flags & 0x02) && name_len >= 10) {
        if (!strncasecmp(name, "SYSTEM.CNF", 10)) {
          sys_lba = read_u32_le(&dir_buf[pos + 2]);
          sys_size = read_u32_le(&dir_buf[pos + 10]);
          found = 1;
          break;
        }
      }

      pos += record_len;
    }
  }

  if (!found || sys_lba == 0 || sys_size == 0)
    return -ENOENT;

  /* 4. Read and parse SYSTEM.CNF */
  int64_t sys_offset = (int64_t)sys_lba * sector_size + data_offset;
  if (seek_fn(user, sys_offset, SEEK_SET) < 0)
    return -EIO;

  uint32_t read_len = sys_size > 2048 ? 2048 : sys_size;
  char cnf_buf[2048];
  int nread = read_fn(user, cnf_buf, read_len);
  if (nread <= 0)
    return -EIO;
  cnf_buf[nread < 2048 ? nread : 2047] = '\0';

  /* Search for "BOOT" */
  char *boot_line = strstr(cnf_buf, "BOOT");
  if (!boot_line)
    boot_line = strstr(cnf_buf, "boot");
  if (!boot_line)
    return -ENOENT;

  char *eq = strchr(boot_line, '=');
  if (!eq)
    return -EINVAL;
  eq++;

  while (*eq == ' ' || *eq == '\t')
    eq++;

  /* Find end of line */
  char *line_end = strpbrk(eq, "\r\n");
  if (line_end)
    *line_end = '\0';

  /* Save raw and normalized serials */
  strncpy(info->raw_serial, eq, sizeof(info->raw_serial) - 1);
  info->raw_serial[sizeof(info->raw_serial) - 1] = '\0';

  return pops_vcd_normalize_serial(eq, info->normalized_serial,
                                  sizeof(info->normalized_serial));
}

typedef struct {
  int fd;
} FdStream;

static int fd_read(void *user, void *buf, size_t count) {
  FdStream *s = (FdStream *)user;
  return (int)read(s->fd, buf, count);
}

static int64_t fd_seek(void *user, int64_t offset, int whence) {
  FdStream *s = (FdStream *)user;
  return (int64_t)lseek(s->fd, (off_t)offset, whence);
}

int pops_vcd_inspect_fd(int fd, PopsVcdInfo *info) {
  if (fd < 0 || !info)
    return -EINVAL;
  FdStream s = { fd };
  return pops_vcd_inspect_stream(&s, fd_read, fd_seek, info);
}

int pops_vcd_inspect_path(const char *path, PopsVcdInfo *info) {
  if (!path || !info)
    return -EINVAL;
  int fd = open(path, O_RDONLY);
  if (fd < 0)
    return -errno;
  int ret = pops_vcd_inspect_fd(fd, info);
  close(fd);
  return ret;
}
