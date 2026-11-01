#include "pops_config.h"
#include "pops_external.h"
#include "dprintf.h"
#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Largest config file read; POPStarter files are a few KB. */
#define POPS_CONFIG_FILE_MAX (1u << 20)

static FILE *open_config(const char *path) {
  FILE *file = fopen(path, "r");
  int error = errno;
  DPRINTF("POPS config: %s open=%d errno=%d\n", path, file != NULL, file ? 0 : error);
  errno = error;
  return file;
}

void pops_config_init(PopsConfig *cfg) {
  if (!cfg)
    return;
  memset(cfg, 0, sizeof(*cfg));
  cfg->video_mode = POPS_VMODE_DEFAULT;
}

static int parse_directives(PopsConfig *cfg, const char *line);

static int is_hex_string(const char *s, size_t len) {
  for (size_t i = 0; i < len; ++i) {
    if (!isxdigit((unsigned char)s[i]))
      return 0;
  }
  return 1;
}

/* CHEATS.TXT codes, read the way POPStarter r13's cheat section reads them
 * (traced with its own compiler under emulation, tools/trace_original_pops_cheats.py).
 * It scans the text for '$' anywhere, case folded, and takes a code when
 * the 14 characters from the '$' match a fixed column layout:
 *   $TTAAAAAA VVVV  where position 9 is a space and position 14 is CR, LF,
 *   NUL, a space or the next '$'.
 * TT is 80/30 (16/8-bit write), D0 (16-bit equal), C0 (master code) with
 * the address high nibble 0 or 1, or the whole word is 5000XXYY (repeat).
 * A character that is not hex counts as 0. Anything else is skipped, not an
 * error, and the scan moves on one character; a '#' does not hide a code.
 * Other GameShark types (10, 20, D1..D3, E0, E1) are skipped, as there. */
static unsigned cheat_nibble(char c) {
  if (c >= '0' && c <= '9')
    return (unsigned)(c - '0');
  c = (char)toupper((unsigned char)c);
  if (c >= 'A' && c <= 'F')
    return (unsigned)(c - 'A' + 10);
  return 0;
}

static uint32_t cheat_hex(const char *s, unsigned digits) {
  uint32_t v = 0;
  while (digits--)
    v = (v << 4) | cheat_nibble(*s++);
  return v;
}

static int cheat_digit_in(char c, char hi) {
  return c >= '0' && c <= hi;
}

/* POPStarter r13's code columns (its scan at 0x885a04): a code is '$', a
 * type, its address, a space at column 9 and a value. PS1 codes have a
 * 4-digit value, so column 14 ends them (CR, LF, NUL, space or the next
 * '$'); PS2-format codes have an 8-digit value, so column 14 must not end
 * them. Non-hex digits count as 0. Returns the code's length (14 or 18),
 * or 0 when this is not a code. */
static int cheat_code_at(const char *text, PopsCheatEntry *entry) {
  char c[19];
  unsigned i = 0;
  for (; i < sizeof(c) && text[i]; ++i)
    c[i] = (char)toupper((unsigned char)text[i]);
  for (; i < sizeof(c); ++i)
    c[i] = '\0';
  if (c[0] != '$' || c[9] != ' ')
    return 0;
  memset(entry, 0, sizeof(*entry));
  int ends = c[14] == '\r' || c[14] == '\n' || c[14] == '\0' || c[14] == ' ' || c[14] == '$';

  if (!ends) {
    entry->value = cheat_hex(c + 10, 8);
    if (cheat_digit_in(c[1], '2')) {
      entry->type = (uint8_t)(POPS_CHEAT_EE | (unsigned)(c[1] - '0'));
      entry->address = cheat_hex(c + 2, 7);
      return 18;
    }
    if ((c[1] == 'S' || c[1] == 'T') && cheat_digit_in(c[2], '2') && cheat_digit_in(c[3], '2') &&
        c[4] == '0') {
      if (c[1] == 'S' && cheat_digit_in(c[5], '3')) {
        entry->type = (uint8_t)(POPS_CHEAT_SPR | (unsigned)(c[2] - '0'));
        entry->address = cheat_hex(c + 5, 4);
      } else if (c[1] == 'T' && c[5] == '0' && cheat_digit_in(c[6], '3')) {
        entry->type = (uint8_t)(POPS_CHEAT_PS1SPR | (unsigned)(c[2] - '0'));
        entry->address = cheat_hex(c + 6, 3);
      } else {
        return 0;
      }
      entry->cond = (uint8_t)(c[3] - '0');
      return 18;
    }
    if ((c[1] == '=' || c[1] == '!') && cheat_digit_in(c[2], '1')) {
      entry->type = (uint8_t)(POPS_CHEAT_EE | 2u);
      entry->cond = c[1] == '=' ? POPS_CHEAT_COND_EQ : POPS_CHEAT_COND_NE;
      entry->address = cheat_hex(c + 2, 7);
      return 18;
    }
    return 0;
  }

  entry->value = cheat_hex(c + 10, 4);
  if (c[1] == '5' && c[2] == '0' && c[3] == '0' && c[4] == '0') {
    entry->type = 0x50;
    entry->address = cheat_hex(c + 5, 4); /* XX count, YY address step */
    return 14;
  }
  if (c[3] != '0' && c[3] != '1')
    return 0;
  if (c[2] != '0' || (c[1] != '8' && c[1] != '3' && c[1] != 'D' && c[1] != 'C'))
    return 0;
  entry->type = (uint8_t)(cheat_nibble(c[1]) << 4);
  entry->address = cheat_hex(c + 3, 6);
  return 14;
}

static int scan_cheats(PopsConfig *cfg, const char *text) {
  while (*text) {
    PopsCheatEntry entry;
    int len = *text == '$' ? cheat_code_at(text, &entry) : 0;
    if (!len) {
      ++text;
      continue;
    }
    if (cfg->cheat_count >= POPS_MAX_CHEATS)
      return -EOVERFLOW;
    cfg->cheats[cfg->cheat_count++] = entry;
    /* A code ends at column 14 (PS1) or 18 (PS2), which may be the next '$'. */
    for (int i = 0; i < len && *text; ++i)
      ++text;
  }
  return 0;
}

/* Original commands accept decimal digits only, with bounded digit counts.
 * Do not let strtol accept a sign, suffix or overflow as a display patch. */
static int display_decimal32(const char *text, unsigned digits, unsigned maximum,
                               uint32_t *value) {
  unsigned n = 0, result = 0;
  while (*text) {
    if (*text < '0' || *text > '9' || ++n > digits)
      return 0;
    result = result * 10 + (unsigned)(*text++ - '0');
  }
  if (!n || result > maximum)
    return 0;
  *value = result;
  return 1;
}

static int display_decimal(const char *text, unsigned digits, unsigned maximum,
                             uint16_t *value) {
  uint32_t result;
  if (!display_decimal32(text, digits, maximum, &result))
    return 0;
  *value = (uint16_t)result;
  return 1;
}

static int parse_single_directive(PopsConfig *cfg, const char *token) {
  if (!cfg || !token || !*token)
    return 0;

  static const char *const gs_commands[] = {
    "$DX_", "$DY_", "$MAGH_", "$MAGV_", "$DW_", "$DH_"
  };
  for (unsigned i = 0; i < 6; ++i) {
    size_t n = strlen(gs_commands[i]);
    if (!strncasecmp(token, gs_commands[i], n)) {
      uint32_t value;
      if (!(cfg->gs_mask & (1u << i)) &&
          display_decimal32(token + n, 5, 99999, &value)) {
        cfg->gs_values[i] = value;
        cfg->gs_mask |= (uint8_t)(1u << i);
        if (cfg->gs_mask == 0x3f) {
          /* Original unsigned 32-bit DW/DH subtraction and 64-bit ORs.
           * Do not silently mask inputs to the nominal GS field widths. */
          cfg->gs_display = (uint64_t)(uint32_t)(cfg->gs_values[5] - 1) << 44 |
                            (uint64_t)(uint32_t)(cfg->gs_values[4] - 1) << 32 |
                            (uint64_t)cfg->gs_values[3] << 27 |
                            (uint64_t)cfg->gs_values[2] << 23 |
                            (uint64_t)cfg->gs_values[1] << 12 | cfg->gs_values[0];
          cfg->gs_display_valid = 1;
          cfg->hdtv_fix = 0;
          cfg->original_tokens |= POPS_TOK_NOHDTVFIX;
        }
      }
      return 1;
    }
  }

  if (!strcasecmp(token, "$480p")) {
    cfg->video_mode = POPS_VMODE_480P;
    cfg->progressive_requested = 1;
    if (cfg->gs_mask != 0x3f) {
      cfg->gs_display_valid = 0;
      cfg->hdtv_fix = 0;
      cfg->original_tokens &= ~POPS_TOK_NOHDTVFIX;
    }
    return 1;
  }
  /* Not POPStarter commands; no grounded POPS writes exist for them. */
  if (!strcasecmp(token, "$480i") || !strcasecmp(token, "$576p") ||
      !strcasecmp(token, "$576i") || !strcasecmp(token, "$240p") ||
      !strncasecmp(token, "$VMODE", 6)) {
    DPRINTF("POPS config: %s is not a POPStarter command; ignored\n", token);
    return 0;
  }
  /* POPS runs NTSC unless the PAL patch is applied, so "PAL to NTSC" is
   * the original's $NOPAL: keep a European disc at 60 Hz. */
  if (!strcasecmp(token, "$NOPAL") || !strcasecmp(token, "$PAL2NTSC") ||
      !strcasecmp(token, "$FORCENTSC")) {
    cfg->video_mode = POPS_VMODE_NOPAL;
    return 1;
  }
  if (!strcasecmp(token, "$FORCEPAL") || !strcasecmp(token, "$NTSC2PAL")) {
    cfg->video_mode = POPS_VMODE_NTSC2PAL;
    return 1;
  }
  if (!strcasecmp(token, "$HDTVFIX")) {
    /* A complete manual DISPLAY in this file restores these sites at EOF,
     * even when HDTVFIX occurs later in the file. A later file may set it. */
    if (cfg->gs_mask != 0x3f) {
      cfg->hdtv_fix = 1;
      cfg->original_tokens &= ~POPS_TOK_NOHDTVFIX;
    }
    return 1;
  }
  if (!strcasecmp(token, "$SMOOTH")) {
    cfg->smooth = 1;
    return 1;
  }
  if (!strncasecmp(token, "$LEFTADJ_", 9)) {
    uint16_t value;
    if (display_decimal(token + 9, 3, 255, &value) && value)
      cfg->left_adjust = (uint8_t)value;
    return 1;
  }
  if (!strncasecmp(token, "$DWSTRETCH_", 11)) {
    uint16_t value;
    if (display_decimal(token + 11, 4, 9999, &value)) {
      cfg->display_stretch = value;
      cfg->display_mask |= POPS_DISPLAY_STRETCH;
    }
    return 1;
  }
  if (!strncasecmp(token, "$DWCROP_", 8)) {
    uint16_t value;
    if (display_decimal(token + 8, 4, 9999, &value)) {
      cfg->display_crop = value;
      cfg->display_mask |= POPS_DISPLAY_CROP;
    }
    return 1;
  }
  if (!strcasecmp(token, "$WIDESCREEN")) {
    cfg->widescreen = POPS_WIDESCREEN_16_9;
    return 1;
  }
  if (!strcasecmp(token, "$ULTRA_WIDESCREEN")) {
    cfg->widescreen = POPS_WIDESCREEN_ULTRA;
    return 1;
  }
  if (!strcasecmp(token, "$EYEFINITY")) {
    cfg->widescreen = POPS_WIDESCREEN_EYEFINITY;
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
  if (!strcasecmp(token, "$NOIGR")) {
    cfg->no_igr = 1;
    cfg->igr_type = 0;
    return 1;
  }
  if (!strncasecmp(token, "$IGR", 4) && token[4] >= '0' && token[4] <= '5' &&
      !token[5]) {
    cfg->no_igr = 0;
    cfg->igr_type = (uint8_t)(token[4] - '0' + 1);
    return 1;
  }
  {
    static const struct {
      const char *name;
      uint32_t flag;
    } tokens[] = {
      {"$SCANLINES", POPS_TOK_SCANLINES},
      {"$SUBCDSTATUS", POPS_TOK_SUBCDSTATUS},
      {"$MUTE_CDDA", POPS_TOK_MUTE_CDDA},
      {"$UNDO_MUTE_CDDA", POPS_TOK_UNDO_MUTE_CDDA},
      {"$MUTE_VAB", POPS_TOK_MUTE_VAB},
      {"$MUTE_ALL", POPS_TOK_MUTE_ALL},
      {"$CODECACHE_ADDON_0", POPS_TOK_CODECACHE_ADDON0},
      {"$CODECACHE_ADDON_1", POPS_TOK_CODECACHE_ADDON1},
      {"$CODECACHE_ADDON_2", POPS_TOK_CODECACHE_ADDON2},
      {"$ROLLBACK", POPS_TOK_ROLLBACK},
      {"$CACHE1", POPS_TOK_CACHE1},
      {"$NOHDTVFIX", POPS_TOK_NOHDTVFIX},
      {"$UNDO_COMPATIBILITY_CODES", POPS_TOK_UNDO_COMPAT},
      {"$UNDO_GAME_FIXES", POPS_TOK_UNDO_GAME_FIXES},
      {"$UNDO_LIBCRYPT_FIX", POPS_TOK_UNDO_LIBCRYPT},
    };
    for (size_t i = 0; i < sizeof(tokens) / sizeof(tokens[0]); ++i) {
      if (!strcasecmp(token, tokens[i].name)) {
        cfg->original_tokens |= tokens[i].flag;
        if (tokens[i].flag == POPS_TOK_NOHDTVFIX)
          cfg->hdtv_fix = 0;
        return 1;
      }
    }
  }
  /* Cheat gates (pops_modes_patches.h). The original keeps one flag per
   * command; $NOSAFEMODE clears both. */
  if (!strcasecmp(token, "$SAFEMODE")) {
    cfg->safe_mode |= POPS_SAFE_MODE_BOOT;
    return 1;
  }
  if (!strcasecmp(token, "$SAFEMODE2")) {
    cfg->safe_mode |= POPS_SAFE_MODE_2;
    return 1;
  }
  if (!strcasecmp(token, "$NOSAFEMODE")) {
    cfg->safe_mode = 0;
    return 1;
  }
  /* Pad commands. The original's handlers write the same two per-port
   * values (override on/off and the ID byte), so the last command wins. */
  if (!strncasecmp(token, "$NOPAD", 6) && (token[6] == '0' || token[6] == '1') && !token[7]) {
    unsigned port = (unsigned)(token[6] - '0');
    cfg->pad_override |= (uint8_t)(1u << port);
    cfg->pad_id[port] = POPS_PAD_ID_NONE;
    return 1;
  }
  if (!strcasecmp(token, "$D2LS")) {
    cfg->pad_override = 3;
    cfg->pad_id[0] = cfg->pad_id[1] = POPS_PAD_ID_DIGITAL;
    cfg->pad_d2ls = 1;
    return 1;
  }
  if (!strcasecmp(token, "$D2LS_ALT")) {
    /* Keeps the real controller ID when the swap was already requested;
     * otherwise any earlier override now reports a digital pad. */
    if (cfg->pad_d2ls)
      cfg->pad_override = 0;
    cfg->pad_id[0] = cfg->pad_id[1] = POPS_PAD_ID_DIGITAL;
    cfg->pad_d2ls = 1;
    return 1;
  }
  if (!strncasecmp(token, "$PAD", 4) && (token[4] == '0' || token[4] == '1') &&
      !strncasecmp(token + 5, "ID_0X", 5)) {
    /* Exactly two hex digits; anything else is ignored like the original. */
    if (strlen(token) == 12 && is_hex_string(token + 10, 2)) {
      unsigned port = (unsigned)(token[4] - '0');
      cfg->pad_override |= (uint8_t)(1u << port);
      cfg->pad_id[port] = (uint8_t)strtoul(token + 10, NULL, 16);
    }
    return 1;
  }
  if (!strcasecmp(token, "$SET_TIMINGS")) {
    cfg->set_timings = 1;
    return 1;
  }
  if (!strcasecmp(token, "$NOVMC0")) {
    cfg->no_vmc0 = 1;
    return 1;
  }
  if (!strcasecmp(token, "$NOVMC1")) {
    cfg->no_vmc1 = 1;
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
    uint16_t value;
    if (!(cfg->display_mask & POPS_DISPLAY_X) &&
        display_decimal(token + 6, 5, 65535, &value)) {
      cfg->display_x = value;
      cfg->display_mask |= POPS_DISPLAY_X;
    }
    cfg->x_offset = (int16_t)strtol(token + 6, NULL, 10);
    return 1;
  }
  if (!strncasecmp(token, "$YPOS_", 6)) {
    uint16_t value;
    if (!(cfg->display_mask & POPS_DISPLAY_Y) &&
        display_decimal(token + 6, 5, 65535, &value)) {
      cfg->display_y = value;
      cfg->display_mask |= POPS_DISPLAY_Y;
    }
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
  if (!strcasecmp(token, "$FIX_TEXTURE_WINDOW")) {
    cfg->runtime_corrections |= POPS_FIX_TEXTURE_WINDOW;
    return 1;
  }
  if (!strcasecmp(token, "$FIX_GPU_DMA") || !strcasecmp(token, "$FIX_GPU_DMA_ZERO")) {
    cfg->runtime_corrections |= POPS_FIX_GPU_DMA_ZERO;
    return 1;
  }
  if (!strcasecmp(token, "$FIX_CDDA") || !strcasecmp(token, "$FIX_CDDA_SETMODE")) {
    cfg->runtime_corrections |= POPS_FIX_CDDA_SETMODE;
    return 1;
  }
  if (!strcasecmp(token, "$FIX_SPU_RESET") || !strcasecmp(token, "$FIX_SPU_ENABLE_RESET")) {
    cfg->runtime_corrections |= POPS_FIX_SPU_ENABLE_RESET;
    return 1;
  }
  if (!strcasecmp(token, "$FIX_GTE_RES1")) {
    cfg->runtime_corrections |= POPS_FIX_GTE_RES1;
    return 1;
  }
  if (!strcasecmp(token, "$FIX_ALL") || !strcasecmp(token, "$CORE_FIXES") ||
      !strcasecmp(token, "$PSXCORE_FIXES")) {
    cfg->runtime_corrections |= POPS_FIX_ALL;
    return 1;
  }
  return 0;
}

int pops_config_parse_line(PopsConfig *cfg, const char *line) {
  if (!cfg || !line)
    return -EINVAL;
  int result = scan_cheats(cfg, line);
  return result ? result : parse_directives(cfg, line);
}

static int parse_directives(PopsConfig *cfg, const char *line) {
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

static int load_config_file(PopsConfig *cfg, const char *filepath, int optional_global) {
  if (!cfg || !filepath)
    return -EINVAL;

  FILE *f = open_config(filepath);
  if (!f) {
    int result = errno ? -errno : -EIO;
    /* Only an optional global location that could not be opened is absent.
     * A device removed during reading must still fail after a successful open. */
    if (optional_global && (result == -ENOENT || result == -ENODEV || result == -ENXIO))
      return 0;
    return result;
  }

  cfg->gs_mask = 0; /* The original's six acceptance flags are file-local. */

  /* Read the whole file: POPStarter scans its text for codes as one stream,
   * then the directives are taken line by line. */
  size_t size = 0, capacity = 0;
  char *text = NULL;
  int result = 0;
  for (;;) {
    if (capacity - size < 1024 + 16) {
      if (capacity >= POPS_CONFIG_FILE_MAX) {
        result = -EFBIG;
        break;
      }
      size_t grown = capacity ? capacity * 2 : 4096;
      char *bigger = (char *)realloc(text, grown);
      if (!bigger) {
        result = -ENOMEM;
        break;
      }
      text = bigger;
      capacity = grown;
    }
    size_t got = fread(text + size, 1, capacity - size - 16, f);
    size += got;
    if (!got)
      break;
  }
  if (!result && ferror(f))
    result = errno ? -errno : -EIO;
  if (fclose(f) && !result)
    result = errno ? -errno : -EIO;
  if (!result && text) {
    memset(text + size, 0, 16);
    result = scan_cheats(cfg, text);
  }

  char *line = text;
  while (!result && line && line < text + size) {
    char *end = memchr(line, '\n', (size_t)(text + size - line));
    size_t length = end ? (size_t)(end - line) : (size_t)(text + size - line);
    if (length > 254) {
      result = -EOVERFLOW;
      break;
    }
    line[length] = '\0';
    while (length && line[length - 1] == '\r')
      line[--length] = '\0';
    result = parse_directives(cfg, line);
    line += (end ? (size_t)(end - line) + 1 : length + 1);
  }
  free(text);
  return result;
}

int pops_config_load_file(PopsConfig *cfg, const char *filepath) {
  return load_config_file(cfg, filepath, 0);
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
  f = open_config(filepath);
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
  f = open_config(filepath);
  if (!f)
    return errno ? -errno : -EIO;
  if (fgets(line, sizeof(line), f)) {
    char *start = trim_line(line);
    size_t length = strlen(start);
    if (length > 103)
      result = -EOVERFLOW;
    else if (strpbrk(start, "/\\:") || !strcmp(start, ".") ||
             !strcmp(start, ".."))
      result = -EINVAL;
    else {
      char extra[2];
      if (fgets(extra, sizeof(extra), f))
        result = -EINVAL;
    }
    if (!result && *start)
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
    result = load_config_file(cfg, path, 1);
    if (result)
      return result;

    snprintf(path, sizeof(path), "%sMODES.TXT", globalDirs[g]);
    result = load_config_file(cfg, path, 1);
    if (result)
      return result;

    snprintf(path, sizeof(path), "%sCHEATS.TXT", globalDirs[g]);
    result = load_config_file(cfg, path, 1);
    if (result)
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
  cfg->usb_delay = table[3];
  for (int i = 0; i < 8; ++i) {
    if (table[8 + i]) {
      cfg->compat_modes |= (1 << i);
    }
  }
  cfg->no_boot = (table[17] != 0);
  if (table[18] == 0) {
    cfg->no_igr = 1;
  }
  cfg->igr_type = table[20];
  if (table[26] == 0x02) {
    cfg->video_mode = POPS_VMODE_480P;
    cfg->progressive_requested = 1;
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
  if (cfg->usb_delay > 0) {
    table[3] = cfg->usb_delay;
  }
  for (int i = 0; i < 8; ++i) {
    if (cfg->compat_modes & (1 << i)) {
      table[8 + i] = 0x01;
    }
  }
  table[17] = cfg->no_boot ? 0x01 : 0x00;
  if (cfg->no_igr) {
    table[18] = 0x00;
  }
  table[20] = cfg->igr_type ? cfg->igr_type : 0x01;
  if (cfg->progressive_requested || cfg->video_mode == POPS_VMODE_480P) {
    table[26] = 0x02;
  } else if (cfg->video_mode == POPS_VMODE_NOPAL) {
    table[26] = 0x00;
  }
}

