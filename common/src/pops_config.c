#include "pops_config.h"
#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void pops_config_init(PopsConfig *cfg) {
  if (!cfg)
    return;
  memset(cfg, 0, sizeof(*cfg));
  cfg->video_mode = POPS_VMODE_DEFAULT;
}

static int is_hex_string(const char *s, size_t len) {
  for (size_t i = 0; i < len; ++i) {
    if (!isxdigit((unsigned char)s[i]))
      return 0;
  }
  return 1;
}

static int try_parse_cheat(PopsConfig *cfg, const char *tok1, const char *tok2) {
  if (*tok1 != '$')
    return 0; /* Removing '$' disables a POPStarter code. */
  const char *p1 = tok1 + 1;
  if (strlen(p1) != 8 || strlen(tok2) != 4)
    return 0;
  if (!is_hex_string(p1, 8) || !is_hex_string(tok2, 4))
    return 0;

  uint32_t raw_addr = (uint32_t)strtoul(p1, NULL, 16);
  uint16_t val = (uint16_t)strtoul(tok2, NULL, 16);
  uint8_t type = (uint8_t)(raw_addr >> 24);

  if (type != 0x80 && type != 0x10 && type != 0x30 && type != 0x20 &&
      type != 0xD0 && type != 0xD1 && type != 0xD2 && type != 0xD3 &&
      type != 0xE0 && type != 0xE1) {
    return -ENOTSUP;
  }

  if (cfg->cheat_count < POPS_MAX_CHEATS) {
    cfg->cheats[cfg->cheat_count].address = raw_addr & 0x001FFFFF;
    cfg->cheats[cfg->cheat_count].value = val;
    cfg->cheats[cfg->cheat_count].type = type;
    cfg->cheat_count++;
    return 1;
  }
  return -EOVERFLOW;
}

static int parse_single_directive(PopsConfig *cfg, const char *token) {
  if (!cfg || !token || !*token)
    return 0;

  if (!strcasecmp(token, "$480p")) {
    cfg->video_mode = POPS_VMODE_480P;
    return 1;
  }
  if (!strcasecmp(token, "$480i")) {
    cfg->video_mode = POPS_VMODE_480I;
    return 1;
  }
  if (!strcasecmp(token, "$576p")) {
    cfg->video_mode = POPS_VMODE_576P;
    return 1;
  }
  if (!strcasecmp(token, "$576i")) {
    cfg->video_mode = POPS_VMODE_576I;
    return 1;
  }
  if (!strcasecmp(token, "$240p")) {
    cfg->video_mode = POPS_VMODE_240P;
    return 1;
  }
  if (!strcasecmp(token, "$PAL2NTSC") || !strcasecmp(token, "$FORCENTSC")) {
    cfg->video_mode = POPS_VMODE_PAL2NTSC;
    return 1;
  }
  if (!strcasecmp(token, "$NTSC2PAL") || !strcasecmp(token, "$FORCEPAL")) {
    cfg->video_mode = POPS_VMODE_NTSC2PAL;
    return 1;
  }
  if (!strcasecmp(token, "$NOPAL")) {
    cfg->video_mode = POPS_VMODE_NOPAL;
    return 1;
  }
  if (!strncasecmp(token, "$VMODE_", 7) || !strncasecmp(token, "$VMODE", 6)) {
    const char *num_str = (!strncasecmp(token, "$VMODE_", 7)) ? token + 7 : token + 6;
    int vm = (int)strtol(num_str, NULL, 10);
    if (vm >= POPS_VMODE_DEFAULT && vm <= POPS_VMODE_240P) {
      cfg->video_mode = (uint8_t)vm;
      return 1;
    }
  }
  if (!strcasecmp(token, "$HDTVFIX")) {
    cfg->hdtv_fix = 1;
    return 1;
  }
  if (!strcasecmp(token, "$SMOOTH")) {
    cfg->smooth = 1;
    return 1;
  }
  if (!strcasecmp(token, "$WIDESCREEN")) {
    cfg->widescreen = 1;
    return 1;
  }
  if (!strcasecmp(token, "$DITHER_OFF") || !strcasecmp(token, "$NODITHER")) {
    cfg->dither_off = 1;
    return 1;
  }
  if (!strcasecmp(token, "$FASTMIPS")) {
    cfg->fast_mips = 1;
    return 1;
  }
  if (!strcasecmp(token, "$SLOWMIPS")) {
    cfg->slow_mips = 1;
    return 1;
  }
  if (!strcasecmp(token, "$NOBOOT") || !strcasecmp(token, "$BIOS")) {
    cfg->no_boot = 1;
    return 1;
  }
  if (!strcasecmp(token, "$NOIGR") || !strcasecmp(token, "$IGR0")) {
    cfg->no_igr = 1;
    cfg->igr_type = 0;
    return 1;
  }
  if (!strcasecmp(token, "$IGR1")) {
    cfg->no_igr = 0;
    cfg->igr_type = 1;
    return 1;
  }
  if (!strcasecmp(token, "$IGR2")) {
    cfg->no_igr = 0;
    cfg->igr_type = 2;
    return 1;
  }
  if (!strcasecmp(token, "$SAFEMODE")) {
    cfg->safe_mode = 1;
    return 1;
  }
  if (!strncasecmp(token, "$USBDELAY_", 10)) {
    cfg->usb_delay = (uint8_t)strtol(token + 10, NULL, 10);
    return 1;
  }
  if (!strncasecmp(token, "$USBDELAY", 9) && isdigit((unsigned char)token[9])) {
    cfg->usb_delay = (uint8_t)strtol(token + 9, NULL, 10);
    return 1;
  }
  if (!strncasecmp(token, "$XPOS_", 6)) {
    cfg->x_offset = (int16_t)strtol(token + 6, NULL, 10);
    return 1;
  }
  if (!strncasecmp(token, "$YPOS_", 6)) {
    cfg->y_offset = (int16_t)strtol(token + 6, NULL, 10);
    return 1;
  }
  if (!strncasecmp(token, "$COMPATIBILITY_0x0", 18)) {
    int mode = (int)strtol(token + 18, NULL, 16);
    if (mode >= 1 && mode <= 8) {
      cfg->compat_modes |= (uint8_t)(1 << (mode - 1));
      return 1;
    }
  }
  if (!strncasecmp(token, "$COMPATIBILITY_0x", 17)) {
    int mode = (int)strtol(token + 17, NULL, 16);
    if (mode >= 1 && mode <= 8) {
      cfg->compat_modes |= (uint8_t)(1 << (mode - 1));
      return 1;
    }
  }
  if (!strncasecmp(token, "$MODE", 5) && isdigit((unsigned char)token[5])) {
    int mode = (int)strtol(token + 5, NULL, 10);
    if (mode >= 1 && mode <= 8) {
      cfg->compat_modes |= (uint8_t)(1 << (mode - 1));
      return 1;
    }
  }
  if (isdigit((unsigned char)*token)) {
    int mode = (int)strtol(token, NULL, 10);
    if (mode >= 1 && mode <= 8 && token[1] == '\0') {
      cfg->compat_modes |= (uint8_t)(1 << (mode - 1));
      return 1;
    }
  }
  return 0;
}

int pops_config_parse_line(PopsConfig *cfg, const char *line) {
  if (!cfg || !line)
    return -EINVAL;

  const char *p = line;
  char token[64];
  char next_token[64];

  while (*p && isspace((unsigned char)*p))
    p++;

  if (!*p || *p == '#' || *p == ';')
    return 0;

  int len1 = 0;
  while (*p && !isspace((unsigned char)*p) && len1 < (int)sizeof(token) - 1) {
    token[len1++] = *p++;
  }
  token[len1] = '\0';

  while (*p && isspace((unsigned char)*p))
    p++;

  if (*p && *p != '#' && *p != ';') {
    const char *save_p = p;
    int len2 = 0;
    while (*p && !isspace((unsigned char)*p) && len2 < (int)sizeof(next_token) - 1) {
      next_token[len2++] = *p++;
    }
    next_token[len2] = '\0';

    int cheat_result = try_parse_cheat(cfg, token, next_token);
    if (cheat_result)
      return cheat_result < 0 ? cheat_result : 0;

    if ((!strcasecmp(token, "MODE") || !strcasecmp(token, "$MODE")) &&
        isdigit((unsigned char)*next_token)) {
      int mode = (int)strtol(next_token, NULL, 10);
      if (mode >= 1 && mode <= 8) {
        cfg->compat_modes |= (uint8_t)(1 << (mode - 1));
      }
      goto loop_remaining;
    }

    parse_single_directive(cfg, token);
    p = save_p;
  } else {
    parse_single_directive(cfg, token);
  }

loop_remaining:
  while (*p) {
    while (*p && isspace((unsigned char)*p))
      p++;
    if (!*p || *p == '#' || *p == ';')
      break;

    int tlen = 0;
    while (*p && !isspace((unsigned char)*p) && tlen < (int)sizeof(token) - 1) {
      token[tlen++] = *p++;
    }
    token[tlen] = '\0';

    while (*p && isspace((unsigned char)*p))
      p++;

    if ((!strcasecmp(token, "MODE") || !strcasecmp(token, "$MODE")) &&
        *p && isdigit((unsigned char)*p)) {
      const char *save_p = p;
      int nlen = 0;
      while (*p && !isspace((unsigned char)*p) && nlen < (int)sizeof(next_token) - 1) {
        next_token[nlen++] = *p++;
      }
      next_token[nlen] = '\0';
      int mode = (int)strtol(next_token, NULL, 10);
      if (mode >= 1 && mode <= 8) {
        cfg->compat_modes |= (uint8_t)(1 << (mode - 1));
        continue;
      }
      p = save_p;
    }

    parse_single_directive(cfg, token);
  }

  return 0;
}

int pops_config_load_file(PopsConfig *cfg, const char *filepath) {
  if (!cfg || !filepath)
    return -EINVAL;

  FILE *f = fopen(filepath, "r");
  if (!f)
    return errno ? -errno : -EIO;

  char line[256];
  int result = 0;
  while (fgets(line, sizeof(line), f)) {
    size_t length = strlen(line);
    if (length == sizeof(line) - 1 && line[length - 1] != '\n') {
      result = -EOVERFLOW;
      break;
    }
    while (length && (line[length - 1] == '\r' || line[length - 1] == '\n'))
      line[--length] = '\0';
    result = pops_config_parse_line(cfg, line);
    if (result)
      break;
  }
  if (!result && ferror(f))
    result = errno ? -errno : -EIO;
  if (fclose(f) && !result)
    result = errno ? -errno : -EIO;
  return result;
}

/* Trim without forming a pointer before an empty line's buffer. */
static char *trim_line(char *line) {
  char *start = line, *end;
  while (*start && isspace((unsigned char)*start))
    ++start;
  end = start + strlen(start);
  while (end > start && isspace((unsigned char)end[-1]))
    *--end = '\0';
  return start;
}

static int finish_file(FILE *file, int result) {
  if (!result && ferror(file))
    result = errno ? -errno : -EIO;
  if (fclose(file) && !result)
    result = errno ? -errno : -EIO;
  return result;
}

int pops_config_load_discs(PopsConfig *cfg, const char *filepath) {
  char line[256];
  int result = 0;
  FILE *f;
  if (!cfg || !filepath)
    return -EINVAL;
  f = fopen(filepath, "r");
  if (!f)
    return errno ? -errno : -EIO;
  cfg->disc_count = 0;
  while (fgets(line, sizeof(line), f)) {
    char *start;
    size_t length = strlen(line);
    if (length == sizeof(line) - 1 && line[length - 1] != '\n') {
      result = -EOVERFLOW;
      break;
    }
    start = trim_line(line);
    if (!*start || *start == '#' || *start == ';')
      continue;
    if (cfg->disc_count == POPS_MAX_DISCS ||
        strlen(start) >= sizeof(cfg->discs[0])) {
      result = -EOVERFLOW;
      break;
    }
    strcpy(cfg->discs[cfg->disc_count++], start);
  }
  return finish_file(f, result);
}

int pops_config_load_vmcdir(PopsConfig *cfg, const char *filepath) {
  char line[256];
  int result = 0;
  FILE *f;
  if (!cfg || !filepath)
    return -EINVAL;
  f = fopen(filepath, "r");
  if (!f)
    return errno ? -errno : -EIO;
  if (fgets(line, sizeof(line), f)) {
    char *start = trim_line(line);
    if (strlen(start) >= sizeof(cfg->vmc_dir))
      result = -EOVERFLOW;
    else if (*start)
      strcpy(cfg->vmc_dir, start);
  }
  return finish_file(f, result);
}

int pops_config_load_cheats(PopsConfig *cfg, const char *filepath) {
  return pops_config_load_file(cfg, filepath);
}

int pops_config_discover(PopsConfig *cfg, const char *vcd_dir, const char *game_base) {
  if (!cfg)
    return -EINVAL;

  char path[512];
  int result;

  /* 1. Try global configuration in memory cards (mc0:/POPSTARTER/, mc1:/POPSTARTER/, mc0:/POPS/) */
  static const char *globalDirs[] = {
    "mc0:/POPSTARTER/", "mc1:/POPSTARTER/", "mc0:/POPS/", "mc1:/POPS/"
  };
  for (int g = 0; g < 4; ++g) {
    snprintf(path, sizeof(path), "%sPATCHES.TXT", globalDirs[g]);
    result = pops_config_load_file(cfg, path);
    if (result && result != -ENOENT)
      return result;

    snprintf(path, sizeof(path), "%sMODES.TXT", globalDirs[g]);
    result = pops_config_load_file(cfg, path);
    if (result && result != -ENOENT)
      return result;

    snprintf(path, sizeof(path), "%sCHEATS.TXT", globalDirs[g]);
    result = pops_config_load_cheats(cfg, path);
    if (result && result != -ENOENT)
      return result;
  }

  /* 2. Try PATCHES.TXT in game directory */
  if (vcd_dir && vcd_dir[0]) {
    snprintf(path, sizeof(path), "%sPATCHES.TXT", vcd_dir);
    result = pops_config_load_file(cfg, path);
    if (result && result != -ENOENT)
      return result;

    snprintf(path, sizeof(path), "%sMODES.TXT", vcd_dir);
    result = pops_config_load_file(cfg, path);
    if (result && result != -ENOENT)
      return result;

    snprintf(path, sizeof(path), "%sCHEATS.TXT", vcd_dir);
    result = pops_config_load_cheats(cfg, path);
    if (result && result != -ENOENT)
      return result;

    snprintf(path, sizeof(path), "%sDISCS.TXT", vcd_dir);
    result = pops_config_load_discs(cfg, path);
    if (result && result != -ENOENT)
      return result;

    snprintf(path, sizeof(path), "%sVMCDIR.TXT", vcd_dir);
    result = pops_config_load_vmcdir(cfg, path);
    if (result && result != -ENOENT)
      return result;
  }

  /* VMCDIR redirects saves only. Fixes and cheats stay in the title folder. */
  const char *subfolder = game_base;
  if (vcd_dir && vcd_dir[0] && subfolder && subfolder[0]) {
    snprintf(path, sizeof(path), "%s%s/VMCDIR.TXT", vcd_dir, subfolder);
    result = pops_config_load_vmcdir(cfg, path);
    if (result && result != -ENOENT)
      return result;

    snprintf(path, sizeof(path), "%s%s/PATCHES.TXT", vcd_dir, subfolder);
    result = pops_config_load_file(cfg, path);
    if (result && result != -ENOENT)
      return result;

    snprintf(path, sizeof(path), "%s%s/MODES.TXT", vcd_dir, subfolder);
    result = pops_config_load_file(cfg, path);
    if (result && result != -ENOENT)
      return result;

    snprintf(path, sizeof(path), "%s%s/CHEATS.TXT", vcd_dir, subfolder);
    result = pops_config_load_cheats(cfg, path);
    if (result && result != -ENOENT)
      return result;

    if (cfg->disc_count == 0) {
      snprintf(path, sizeof(path), "%s%s/DISCS.TXT", vcd_dir, subfolder);
      result = pops_config_load_discs(cfg, path);
      if (result && result != -ENOENT)
        return result;
    }
  }

  return 0;
}

int pops_config_load_table(PopsConfig *cfg, const uint8_t table[32]) {
  if (!cfg || !table)
    return -EINVAL;

  cfg->hdtv_fix = (table[2] != 0);
  for (int i = 0; i < 8; ++i) {
    if (table[8 + i]) {
      cfg->compat_modes |= (1 << i);
    }
  }
  cfg->no_boot = (table[17] != 0);
  if (table[18] == 0) {
    cfg->no_igr = 1;
  }
  if (table[26] == 0x02) {
    cfg->video_mode = POPS_VMODE_480P;
  } else if (table[26] == 0x00) {
    cfg->video_mode = POPS_VMODE_NOPAL;
  }
  return 0;
}

void pops_config_export_table(const PopsConfig *cfg, uint8_t table[32]) {
  if (!cfg || !table)
    return;

  static const uint8_t defaults[32] = {
    0xFF, 0x00, 0x00, 0x02, 0x40, 0x00, 0x03, 0x01,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
    0x01, 0x00, 0x01, 0x01, 0x01, 0x01, 0x01, 0x03
  };
  memcpy(table, defaults, 32);

  table[2] = cfg->hdtv_fix ? 0x01 : 0x00;
  for (int i = 0; i < 8; ++i) {
    if (cfg->compat_modes & (1 << i)) {
      table[8 + i] = 0x01;
    }
  }
  table[17] = cfg->no_boot ? 0x01 : 0x00;
  if (cfg->no_igr) {
    table[18] = 0x00;
  }
  if (cfg->video_mode == POPS_VMODE_480P) {
    table[26] = 0x02;
  } else if (cfg->video_mode == POPS_VMODE_NOPAL) {
    table[26] = 0x00;
  }
}

