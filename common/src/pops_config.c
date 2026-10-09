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

int pops_config_parse_line(PopsConfig *cfg, const char *line) {
  if (!cfg || !line)
    return -EINVAL;

  /* Skip leading whitespace */
  while (*line && isspace((unsigned char)*line))
    line++;

  /* Ignore empty lines and comments */
  if (!*line || *line == '#' || *line == ';')
    return 0;

  /* Handle '$' configuration commands */
  if (*line == '$') {
    if (!strcasecmp(line, "$480p")) {
      cfg->video_mode = POPS_VMODE_480P;
      return 0;
    }
    if (!strcasecmp(line, "$480i")) {
      cfg->video_mode = POPS_VMODE_480I;
      return 0;
    }
    if (!strcasecmp(line, "$576p")) {
      cfg->video_mode = POPS_VMODE_576P;
      return 0;
    }
    if (!strcasecmp(line, "$576i")) {
      cfg->video_mode = POPS_VMODE_576I;
      return 0;
    }
    if (!strcasecmp(line, "$PAL2NTSC")) {
      cfg->video_mode = POPS_VMODE_PAL2NTSC;
      return 0;
    }
    if (!strcasecmp(line, "$NTSC2PAL")) {
      cfg->video_mode = POPS_VMODE_NTSC2PAL;
      return 0;
    }
    if (!strcasecmp(line, "$NOPAL")) {
      cfg->video_mode = POPS_VMODE_NOPAL;
      return 0;
    }
    if (!strcasecmp(line, "$HDTVFIX")) {
      cfg->hdtv_fix = 1;
      return 0;
    }
    if (!strcasecmp(line, "$SMOOTH")) {
      cfg->smooth = 1;
      return 0;
    }
    if (!strcasecmp(line, "$FASTMIPS")) {
      cfg->fast_mips = 1;
      return 0;
    }
    if (!strcasecmp(line, "$SLOWMIPS")) {
      cfg->slow_mips = 1;
      return 0;
    }
    if (!strcasecmp(line, "$NOBOOT") || !strcasecmp(line, "$BIOS")) {
      cfg->no_boot = 1;
      return 0;
    }
    if (!strcasecmp(line, "$NOIGR")) {
      cfg->no_igr = 1;
      return 0;
    }
    if (!strncasecmp(line, "$XPOS_", 6)) {
      cfg->x_offset = (int16_t)strtol(line + 6, NULL, 10);
      return 0;
    }
    if (!strncasecmp(line, "$YPOS_", 6)) {
      cfg->y_offset = (int16_t)strtol(line + 6, NULL, 10);
      return 0;
    }
    if (!strncasecmp(line, "$COMPATIBILITY_0x0", 18)) {
      int mode = (int)strtol(line + 18, NULL, 16);
      if (mode >= 1 && mode <= 8) {
        cfg->compat_modes |= (uint8_t)(1 << (mode - 1));
        return 0;
      }
    }
    if (!strncasecmp(line, "$COMPATIBILITY_0x", 17)) {
      int mode = (int)strtol(line + 17, NULL, 16);
      if (mode >= 1 && mode <= 8) {
        cfg->compat_modes |= (uint8_t)(1 << (mode - 1));
        return 0;
      }
    }
    if (!strncasecmp(line, "$MODE", 5)) {
      int mode = (int)strtol(line + 5, NULL, 10);
      if (mode >= 1 && mode <= 8) {
        cfg->compat_modes |= (uint8_t)(1 << (mode - 1));
        return 0;
      }
    }
    return 0;
  }

  /* Handle bare digits for compatibility modes in MODES.TXT (e.g. "1", "2", "3") */
  if (isdigit((unsigned char)*line)) {
    int mode = (int)strtol(line, NULL, 10);
    if (mode >= 1 && mode <= 8) {
      cfg->compat_modes |= (uint8_t)(1 << (mode - 1));
      return 0;
    }
  }

  if (!strncasecmp(line, "MODE ", 5) && isdigit((unsigned char)line[5])) {
    int mode = (int)strtol(line + 5, NULL, 10);
    if (mode >= 1 && mode <= 8) {
      cfg->compat_modes |= (uint8_t)(1 << (mode - 1));
      return 0;
    }
  }

  /* Handle GameShark / Action Replay cheat codes: e.g. "8009A120 0004" */
  char code1[32], code2[32];
  if (sscanf(line, "%31s %31s", code1, code2) == 2) {
    if (strlen(code1) == 8 && strlen(code2) == 4) {
      if (cfg->cheat_count < POPS_MAX_CHEATS) {
        uint32_t raw_addr = (uint32_t)strtoul(code1, NULL, 16);
        uint16_t val = (uint16_t)strtoul(code2, NULL, 16);
        uint8_t type = (uint8_t)(raw_addr >> 24);
        uint32_t addr = raw_addr & 0x001FFFFF; /* 2MB PS1 RAM mask */

        cfg->cheats[cfg->cheat_count].address = addr;
        cfg->cheats[cfg->cheat_count].value = val;
        cfg->cheats[cfg->cheat_count].type = type;
        cfg->cheat_count++;
        return 0;
      }
    }
  }

  return 0;
}

int pops_config_load_file(PopsConfig *cfg, const char *filepath) {
  if (!cfg || !filepath)
    return -EINVAL;

  FILE *f = fopen(filepath, "r");
  if (!f)
    return -ENOENT;

  char line[256];
  while (fgets(line, sizeof(line), f)) {
    char *end = line + strlen(line) - 1;
    while (end >= line && (*end == '\r' || *end == '\n'))
      *end-- = '\0';
    pops_config_parse_line(cfg, line);
  }

  fclose(f);
  return 0;
}

int pops_config_load_discs(PopsConfig *cfg, const char *filepath) {
  if (!cfg || !filepath)
    return -EINVAL;

  FILE *f = fopen(filepath, "r");
  if (!f)
    return -ENOENT;

  char line[256];
  cfg->disc_count = 0;
  while (fgets(line, sizeof(line), f) && cfg->disc_count < POPS_MAX_DISCS) {
    char *start = line;
    while (*start && isspace((unsigned char)*start))
      start++;
    char *end = start + strlen(start) - 1;
    while (end >= start && isspace((unsigned char)*end))
      *end-- = '\0';

    if (*start && *start != '#' && *start != ';') {
      strncpy(cfg->discs[cfg->disc_count], start, sizeof(cfg->discs[cfg->disc_count]) - 1);
      cfg->discs[cfg->disc_count][sizeof(cfg->discs[cfg->disc_count]) - 1] = '\0';
      cfg->disc_count++;
    }
  }

  fclose(f);
  return 0;
}

int pops_config_load_vmcdir(PopsConfig *cfg, const char *filepath) {
  if (!cfg || !filepath)
    return -EINVAL;

  FILE *f = fopen(filepath, "r");
  if (!f)
    return -ENOENT;

  char line[256];
  if (fgets(line, sizeof(line), f)) {
    char *start = line;
    while (*start && isspace((unsigned char)*start))
      start++;
    char *end = start + strlen(start) - 1;
    while (end >= start && isspace((unsigned char)*end))
      *end-- = '\0';

    if (*start) {
      strncpy(cfg->vmc_dir, start, sizeof(cfg->vmc_dir) - 1);
      cfg->vmc_dir[sizeof(cfg->vmc_dir) - 1] = '\0';
    }
  }

  fclose(f);
  return 0;
}

int pops_config_load_cheats(PopsConfig *cfg, const char *filepath) {
  return pops_config_load_file(cfg, filepath);
}

int pops_config_discover(PopsConfig *cfg, const char *vcd_dir, const char *game_base) {
  if (!cfg)
    return -EINVAL;

  char path[512];

  /* 1. Try PATCHES.TXT in game directory */
  if (vcd_dir && vcd_dir[0]) {
    snprintf(path, sizeof(path), "%sPATCHES.TXT", vcd_dir);
    pops_config_load_file(cfg, path);

    snprintf(path, sizeof(path), "%sMODES.TXT", vcd_dir);
    pops_config_load_file(cfg, path);

    snprintf(path, sizeof(path), "%sCHEATS.TXT", vcd_dir);
    pops_config_load_cheats(cfg, path);

    snprintf(path, sizeof(path), "%sDISCS.TXT", vcd_dir);
    pops_config_load_discs(cfg, path);

    snprintf(path, sizeof(path), "%sVMCDIR.TXT", vcd_dir);
    pops_config_load_vmcdir(cfg, path);
  }

  /* 2. Try VMC subfolder <game_base>/ (or custom vmc_dir) */
  const char *subfolder = cfg->vmc_dir[0] ? cfg->vmc_dir : game_base;
  if (vcd_dir && vcd_dir[0] && subfolder && subfolder[0]) {
    snprintf(path, sizeof(path), "%s%s/PATCHES.TXT", vcd_dir, subfolder);
    pops_config_load_file(cfg, path);

    snprintf(path, sizeof(path), "%s%s/MODES.TXT", vcd_dir, subfolder);
    pops_config_load_file(cfg, path);

    snprintf(path, sizeof(path), "%s%s/CHEATS.TXT", vcd_dir, subfolder);
    pops_config_load_cheats(cfg, path);

    if (cfg->disc_count == 0) {
      snprintf(path, sizeof(path), "%s%s/DISCS.TXT", vcd_dir, subfolder);
      pops_config_load_discs(cfg, path);
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

