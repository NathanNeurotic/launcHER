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

/* FUN_008dc2c4: once $SUBCDSTATUS (or a built-in entry) set gp+0x3458,
 * modes 1, 2, 3 and 5 do nothing; 4, 6 and 7 still apply. */
static void add_compat_mode(PopsConfig *cfg, int mode) {
  if (mode < 1 || mode > 8)
    return;
  if (cfg->subcd_seen && (mode == 1 || mode == 2 || mode == 3 || mode == 5))
    return;
  cfg->compat_modes |= (uint8_t)(1 << (mode - 1));
}

/* ------------------------------------------------------------------------
 * CHEATS.TXT commands, recognised the way POPStarter r13's command pass
 * recognises them (FUN_00883270, loop 0x885a04..0x89e75c), measured with
 * its own code under emulation (tools/trace_original_pops_config_text.py,
 * docs/POPSTARTER_CONFIG_TEXT.md). The pass works on the whole file as one
 * run of bytes, with a..z folded to A..Z and zeros after the end:
 *   - at each byte, a cheat code's 14 or 18 columns are stepped over;
 *   - otherwise each command's compare chain is tried in a fixed order, and
 *     the first that holds runs; then the scan moves ONE byte on.
 * There are no lines, comments or tokens: a command is taken at any '$'
 * outside a code's columns, whatever precedes it, when its name is followed
 * by CR, LF, NUL, a space or '$' (a TAB does not end a command).
 * ------------------------------------------------------------------------ */

static int command_end(unsigned char c) {
  return c == '\r' || c == '\n' || c == '\0' || c == ' ' || c == '$';
}

static int command_between(unsigned char c, unsigned char low, unsigned char high) {
  return c >= low && c <= high;
}

/* The pass's five code tests (0x885a20, 0x885ccc, 0x885e28, 0x8860b4,
 * 0x886360): how many columns it steps over at t, or 0. A $C0 master code
 * is not stepped over here (the original finds it in an earlier pass). */
static unsigned command_code_columns(const unsigned char *t) {
  if (t[0] != '$' || t[9] != ' ')
    return 0;
  if (command_end(t[14])) {
    if (t[2] != '0')
      return 0;
    if ((t[1] == '3' || t[1] == '8' || t[1] == 'D') && (t[3] == '0' || t[3] == '1'))
      return 14;
    if (t[1] == '5' && t[3] == '0' && t[4] == '0')
      return 14;
    return 0;
  }
  if (command_between(t[1], '0', '2'))
    return 18;
  if (t[1] == 'S' && command_between(t[2], '0', '2') && command_between(t[3], '0', '2') &&
      t[4] == '0' && command_between(t[5], '0', '3'))
    return 18;
  if (t[1] == 'T' && command_between(t[2], '0', '2') && command_between(t[3], '0', '2') &&
      t[4] == '0' && t[5] == '0' && command_between(t[6], '0', '3'))
    return 18;
  if ((t[1] == '=' || t[1] == '!') && (t[2] == '0' || t[2] == '1'))
    return 18;
  return 0;
}

/* 1..most decimal digits and then a terminator: the value, or -1. */
static int32_t command_number(const unsigned char *t, unsigned most) {
  int32_t value = 0;
  unsigned n = 0;
  while (n < most && command_between(t[n], '0', '9'))
    value = value * 10 + (t[n++] - '0');
  return n && command_end(t[n]) ? value : -1;
}

/* Two hex digits (A..F: the text is upper case by now), or -1. */
static int command_hex_byte(const unsigned char *t) {
  int value = 0;
  for (unsigned i = 0; i < 2; ++i) {
    if (command_between(t[i], '0', '9'))
      value = value << 4 | (t[i] - '0');
    else if (command_between(t[i], 'A', 'F'))
      value = value << 4 | (t[i] - 'A' + 10);
    else
      return -1;
  }
  return value;
}

/* Commands that are a name and nothing else. */
static void apply_plain_command(PopsConfig *cfg, const char *name) {
  if (!strcmp(name, "$NOPAL")) {
    /* 0x89860c: one store, gp+0x4fa0 = 0 (no automatic PAL for a European
     * disc). The forced-PAL word of an earlier $FORCEPAL (gp+0x38a0) stays,
     * and the region pass tests that one first (0x879034): $FORCEPAL and
     * then $NOPAL is still forced PAL. */
    if (!cfg->forced_pal)
      cfg->video_mode = POPS_VMODE_NOPAL;
    return;
  }
  if (!strcmp(name, "$HDTVFIX")) {
    /* A complete manual DISPLAY in this file restores these sites at EOF,
     * even when HDTVFIX occurs later in the file. A later file may set it. */
    if (cfg->gs_mask != 0x3f) {
      cfg->hdtv_fix = 1;
      cfg->original_tokens &= ~POPS_TOK_NOHDTVFIX;
    }
    return;
  }
  if (!strcmp(name, "$SMOOTH")) {
    cfg->smooth = 1;
    return;
  }
  if (!strcmp(name, "$WIDESCREEN")) {
    cfg->widescreen = POPS_WIDESCREEN_16_9;
    return;
  }
  if (!strcmp(name, "$ULTRA_WIDESCREEN")) {
    cfg->widescreen = POPS_WIDESCREEN_ULTRA;
    return;
  }
  if (!strcmp(name, "$EYEFINITY")) {
    cfg->widescreen = POPS_WIDESCREEN_EYEFINITY;
    return;
  }
  if (!strcmp(name, "$NOIGR")) {
    cfg->no_igr = 1;
    cfg->igr_type = 0;
    return;
  }
  if (!strncmp(name, "$IGR", 4)) {
    cfg->no_igr = 0;
    cfg->igr_type = (uint8_t)(name[4] - '0' + 1);
    return;
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
      if (!strcmp(name, tokens[i].name)) {
        cfg->original_tokens |= tokens[i].flag;
        if (tokens[i].flag == POPS_TOK_NOHDTVFIX)
          cfg->hdtv_fix = 0;
        if (tokens[i].flag == POPS_TOK_SUBCDSTATUS)
          cfg->subcd_seen = 1;
        if (tokens[i].flag == POPS_TOK_UNDO_LIBCRYPT)
          cfg->fakelc &= (uint8_t)~POPS_FAKELC_LAST; /* it restores $FAKELC's bytes */
        return;
      }
    }
  }
  /* $RESET_WARMBOOT (0x8923a4): a flag, gp+0x3894, read by the launch
   * function after the region pass (pops_apply_reset_warmboot). */
  if (!strcmp(name, "$RESET_WARMBOOT")) {
    cfg->reset_warmboot = 1;
    return;
  }
  /* $LOAD_PADMAN (0x89d770) and $KILL_PADMAN (0x89d9a8): flags only
   * (gp+0x38a8, gp+0x3870), read after the IOP reset. */
  if (!strcmp(name, "$LOAD_PADMAN")) {
    cfg->load_padman = 1;
    return;
  }
  if (!strcmp(name, "$KILL_PADMAN")) {
    cfg->kill_padman = 1;
    return;
  }
  /* $FAKELC (0x89caf0): writes POPS's LibCrypt loop at once (applied after
   * the $UNDO_ writes, unless a $UNDO_LIBCRYPT_FIX came later) and sets
   * gp+0x3424, never cleared, which a later $VCDID_n's entry tests. */
  if (!strcmp(name, "$FAKELC")) {
    cfg->fakelc |= POPS_FAKELC_LAST;
    if (!cfg->vcdid_set)
      cfg->fakelc |= POPS_FAKELC_BEFORE_VCDID;
    return;
  }
  /* $ORIGINAL_OPCODES (0x894254): flag only (gp+0x38c4). */
  if (!strcmp(name, "$ORIGINAL_OPCODES")) {
    cfg->original_opcodes = 1;
    return;
  }
  /* $RECOMPILER_ADDON_0..4 (0x89316c, 0x893494, 0x8937bc, 0x893ae4,
   * 0x893e4c): flags; the resident code does their work (pops_config.h). */
  if (!strncmp(name, "$RECOMPILER_ADDON_", 18)) {
    cfg->recompiler_addons |= (uint8_t)(1u << (name[18] - '0'));
    return;
  }
  /* $BREAKPOINT0 (0x8960c4) and $BREAKPOINT1 (0x896310): each one, where
   * it stands in the file, calls FUN_008d6da4(0, 0) or (1, 1), which
   * copies the breakpoint handler afresh and edits it; so the last one
   * decides, except for three words only $BREAKPOINT0 writes past the copy
   * (pops_breakpoint_build). */
  if (!strcmp(name, "$BREAKPOINT0")) {
    cfg->breakpoint = POPS_BREAKPOINT_0 | POPS_BREAKPOINT_0_SEEN;
    return;
  }
  if (!strcmp(name, "$BREAKPOINT1")) {
    cfg->breakpoint = (uint8_t)((cfg->breakpoint & POPS_BREAKPOINT_0_SEEN) | POPS_BREAKPOINT_1);
    return;
  }
  /* Pad commands. The original's handlers write the same two per-port
   * values (override on/off and the ID byte), so the last command wins. */
  if (!strncmp(name, "$NOPAD", 6)) {
    unsigned port = (unsigned)(name[6] - '0');
    cfg->pad_override |= (uint8_t)(1u << port);
    cfg->pad_id[port] = POPS_PAD_ID_NONE;
    return;
  }
  if (!strcmp(name, "$D2LS")) {
    cfg->pad_override = 3;
    cfg->pad_id[0] = cfg->pad_id[1] = POPS_PAD_ID_DIGITAL;
    cfg->pad_d2ls = 1;
    return;
  }
  if (!strcmp(name, "$D2LS_ALT")) {
    /* Keeps the real controller ID when the swap was already requested;
     * otherwise any earlier override now reports a digital pad. */
    if (cfg->pad_d2ls)
      cfg->pad_override = 0;
    cfg->pad_id[0] = cfg->pad_id[1] = POPS_PAD_ID_DIGITAL;
    cfg->pad_d2ls = 1;
    return;
  }
  if (!strcmp(name, "$SET_TIMINGS")) {
    cfg->set_timings = 1;
    return;
  }
  if (!strcmp(name, "$NOVMC0")) {
    cfg->no_vmc0 = 1;
    return;
  }
  if (!strcmp(name, "$NOVMC1"))
    cfg->no_vmc1 = 1;
}

/* $XPOS_n / $YPOS_n's write: nothing above 65535, and the first one that
 * writes wins (gp+0x34f0 / gp+0x3974). */
static int apply_position(PopsConfig *cfg, int y, uint32_t value) {
  uint8_t bit = y ? POPS_DISPLAY_Y : POPS_DISPLAY_X;
  if (value > 0xffff || (cfg->display_mask & bit))
    return 0;
  if (y) {
    cfg->display_y = (uint16_t)value;
    cfg->y_offset = (int16_t)value;
  } else {
    cfg->display_x = (uint16_t)value;
    cfg->x_offset = (int16_t)value;
  }
  cfg->display_mask |= bit;
  return 1;
}

enum {
  CMD_PLAIN,    /* name, terminator */
  CMD_OPCODES,  /* $ORIGINAL_OPCODES: the terminator is tested two columns late */
  CMD_FORCEPAL, /* name, terminator; does nothing once a $480P was taken */
  CMD_GS,       /* $DX_ $DY_ $MAGH_ $MAGV_ $DW_ $DH_: 1..5 digits, once per file */
  CMD_480P,     /* "$480", 'P', terminator */
  CMD_LEFTADJ,  /* 1..3 digits */
  CMD_VCDID,    /* 1..4 digits, until one was not 0 */
  CMD_PADID,    /* "$PAD", 0 or 1, "ID_0X", two bytes, terminator */
  CMD_POSITION, /* '$', any byte, "POS_", 1..5 digits */
  CMD_STRETCH,  /* 1..4 digits */
  CMD_CROP,     /* 1..4 digits */
  CMD_SAFEMODE, /* $SAFEMODE / $SAFEMODE2: only while neither is on */
  CMD_NOSAFEMODE, /* only while one is on */
  CMD_USBDELAY, /* "$USBDELAY_", one digit, terminator */
  CMD_COMPAT,   /* "$COMPATIBILITY_0X", two bytes, terminator */
};

typedef struct {
  const char *name;
  uint8_t length;
  uint8_t kind;
  uint8_t arg;
} PopsCommand;

#define CMD(name, kind, arg) {name, (uint8_t)(sizeof(name) - 1), kind, arg}

/* The original's handlers in its own order, named by the literal each
 * compare chain starts with (the address is where the handler ends). */
static const PopsCommand pops_commands[] = {
  CMD("$SMOOTH", CMD_PLAIN, 0),                   /* 0x8866a0 */
  CMD("$DX_", CMD_GS, 0),                         /* 0x888048 */
  CMD("$DY_", CMD_GS, 1),                         /* 0x8899f0 */
  CMD("$MAGH_", CMD_GS, 2),                       /* 0x88b3d8 */
  CMD("$MAGV_", CMD_GS, 3),                       /* 0x88cdc0 */
  CMD("$DW_", CMD_GS, 4),                         /* 0x88e768 */
  CMD("$DH_", CMD_GS, 5),                         /* 0x890110 */
  CMD("$480", CMD_480P, 0),                       /* 0x89030c */
  CMD("$LEFTADJ_", CMD_LEFTADJ, 0),               /* 0x890a34 */
  CMD("$SCANLINES", CMD_PLAIN, 0),                /* 0x890c48 */
  CMD("$VCDID_", CMD_VCDID, 0),                   /* 0x891e98 */
  CMD("$SUBCDSTATUS", CMD_PLAIN, 0),              /* 0x892118 */
  CMD("$RESET_WARMBOOT", CMD_PLAIN, 0),           /* 0x8923c0 */
  CMD("$MUTE_CDDA", CMD_PLAIN, 0),                /* 0x8925f0 */
  CMD("$MUTE_VAB", CMD_PLAIN, 0),                 /* 0x892820 */
  CMD("$CODECACHE_ADDON_0", CMD_PLAIN, 0),        /* 0x892b34 */
  CMD("$CODECACHE_ADDON_1", CMD_PLAIN, 0),        /* 0x892e44 */
  CMD("$CODECACHE_ADDON_2", CMD_PLAIN, 0),        /* 0x893158 */
  CMD("$RECOMPILER_ADDON_0", CMD_PLAIN, 0),       /* 0x893480 */
  CMD("$RECOMPILER_ADDON_1", CMD_PLAIN, 0),       /* 0x8937a8 */
  CMD("$RECOMPILER_ADDON_2", CMD_PLAIN, 0),       /* 0x893ad0 */
  CMD("$RECOMPILER_ADDON_3", CMD_PLAIN, 0),       /* 0x893e38 */
  CMD("$RECOMPILER_ADDON_4", CMD_PLAIN, 0),       /* 0x894240 */
  CMD("$ORIGINAL_OPCODES", CMD_OPCODES, 0),       /* 0x894528 */
  CMD("$UNDO_COMPATIBILITY_CODES", CMD_PLAIN, 0), /* 0x894aa4 */
  CMD("$UNDO_GAME_FIXES", CMD_PLAIN, 0),          /* 0x894da0 */
  CMD("$UNDO_LIBCRYPT_FIX", CMD_PLAIN, 0),        /* 0x895150 */
  CMD("$UNDO_MUTE_CDDA", CMD_PLAIN, 0),           /* 0x895424 */
  CMD("$WIDESCREEN", CMD_PLAIN, 0),               /* 0x89567c */
  CMD("$ULTRA_WIDESCREEN", CMD_PLAIN, 0),         /* 0x895994 */
  CMD("$EYEFINITY", CMD_PLAIN, 0),                /* 0x895bcc */
  CMD("$ROLLBACK", CMD_PLAIN, 0),                 /* 0x895e54 */
  CMD("$SET_TIMINGS", CMD_PLAIN, 0),              /* 0x8960bc */
  CMD("$BREAKPOINT0", CMD_PLAIN, 0),              /* 0x896308 */
  CMD("$BREAKPOINT1", CMD_PLAIN, 0),              /* 0x896554 */
  CMD("$NOVMC0", CMD_PLAIN, 0),                   /* 0x896704 */
  CMD("$NOVMC1", CMD_PLAIN, 0),                   /* 0x8968c4 */
  CMD("$NOPAD0", CMD_PLAIN, 0),                   /* 0x896a84 */
  CMD("$NOPAD1", CMD_PLAIN, 0),                   /* 0x896c44 */
  CMD("$D2LS", CMD_PLAIN, 0),                     /* 0x896e28 */
  CMD("$D2LS_ALT", CMD_PLAIN, 0),                 /* 0x8970ac */
  CMD("$IGR0", CMD_PLAIN, 0),                     /* 0x897264 */
  CMD("$IGR1", CMD_PLAIN, 0),                     /* 0x89741c */
  CMD("$IGR2", CMD_PLAIN, 0),                     /* 0x8975d4 */
  CMD("$IGR3", CMD_PLAIN, 0),                     /* 0x897788 */
  CMD("$IGR4", CMD_PLAIN, 0),                     /* 0x89793c */
  CMD("$IGR5", CMD_PLAIN, 0),                     /* 0x897af0 */
  CMD("$NOIGR", CMD_PLAIN, 0),                    /* 0x897ca8 */
  CMD("$PAD", CMD_PADID, 0),                      /* 0x8982b4 */
  CMD("$MUTE_ALL", CMD_PLAIN, 0),                 /* 0x8984a4 */
  CMD("$NOPAL", CMD_PLAIN, 0),                    /* 0x898628 */
  CMD("$FORCEPAL", CMD_FORCEPAL, 0),              /* 0x89882c */
  CMD("$?POS_", CMD_POSITION, 0),                 /* 0x89a2d0 */
  CMD("$DWSTRETCH_", CMD_STRETCH, 0),             /* 0x89b604 */
  CMD("$DWCROP_", CMD_CROP, 0),                   /* 0x89c918 */
  CMD("$CACHE1", CMD_PLAIN, 0),                   /* 0x89cae8 */
  CMD("$FAKELC", CMD_PLAIN, 0),                   /* 0x89ccc0 */
  CMD("$SAFEMODE", CMD_SAFEMODE, POPS_SAFE_MODE_BOOT), /* 0x89cec8 */
  CMD("$SAFEMODE2", CMD_SAFEMODE, POPS_SAFE_MODE_2),   /* 0x89d0f0 */
  CMD("$NOSAFEMODE", CMD_NOSAFEMODE, 0),          /* 0x89d34c */
  CMD("$HDTVFIX", CMD_PLAIN, 0),                  /* 0x89d534 */
  CMD("$NOHDTVFIX", CMD_PLAIN, 0),                /* 0x89d75c */
  CMD("$LOAD_PADMAN", CMD_PLAIN, 0),              /* 0x89d994 */
  CMD("$KILL_PADMAN", CMD_PLAIN, 0),              /* 0x89dbcc */
  CMD("$USBDELAY_", CMD_USBDELAY, 0),             /* 0x89e13c */
  CMD("$COMPATIBILITY_0X", CMD_COMPAT, 0),        /* 0x89e734 */
};

/* One handler at t (a '$'). Returns 0 when it does not take the text
 * (another handler may), else 1; *effect says whether it did anything.
 * *value is the original's fp+0x90, one temporary all the number commands
 * share: see CMD_POSITION. */
static int run_command(PopsConfig *cfg, const PopsCommand *command, const unsigned char *t,
                       uint32_t *value, int *effect) {
  const unsigned char *rest = t + command->length;
  int32_t number;
  *effect = 0;
  if (command->kind == CMD_POSITION) {
    if (memcmp(t + 2, "POS_", 4))
      return 0;
  } else if (memcmp(t, command->name, command->length)) {
    return 0;
  }

  switch (command->kind) {
  case CMD_PLAIN:
    if (!command_end(*rest))
      return 0;
    apply_plain_command(cfg, command->name);
    *effect = 1;
    return 1;
  case CMD_OPCODES:
    /* The original tests column 19, not 17: any two bytes may follow the
     * name, and '$ORIGINAL_OPCODES' + LF + a command is not taken. */
    if (!command_end(rest[2]))
      return 0;
    apply_plain_command(cfg, command->name);
    *effect = 1;
    return 1;
  case CMD_FORCEPAL:
    /* 0x8987f0: the handler's three stores (gp+0x38a0, the forced-PAL flag
     * the region pass reads at 0x879034, and gp+0x38d0, gp+0x3898) are
     * skipped when gp+0x3864 is set. $480P sets it (0x8902a4); the only
     * store of zero there is the start-up clear (0x870c90), so after a
     * $480P, in this file or an earlier one, the command is taken and
     * does nothing. progressive_requested is that
     * word as far as the text goes; pops_config.h says what else sets it
     * in the original. */
    if (!command_end(*rest))
      return 0;
    if (!cfg->progressive_requested) {
      cfg->video_mode = POPS_VMODE_NTSC2PAL;
      cfg->forced_pal = 1;
      *effect = 1;
    }
    return 1;
  case CMD_GS:
    /* Once a value is in (fp+0xfc..0x110, one per command, per file), the
     * handler is not tried again. A complete set of six is the manual GS
     * DISPLAY (written after the pass, 0x89e75c). */
    if (cfg->gs_mask & (1u << command->arg))
      return 0;
    number = command_number(rest, 5);
    if (number < 0)
      return 1;
    cfg->gs_values[command->arg] = (uint32_t)number;
    cfg->gs_mask |= (uint8_t)(1u << command->arg);
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
    *effect = 1;
    return 1;
  case CMD_480P:
    if (rest[0] != 'P' || !command_end(rest[1]))
      return 0;
    /* 0x89028c..0x8902ac: the forced-PAL and automatic-PAL words are
     * cleared, the 480p word set. */
    cfg->video_mode = POPS_VMODE_480P;
    cfg->progressive_requested = 1;
    cfg->forced_pal = 0;
    if (cfg->gs_mask != 0x3f) {
      cfg->gs_display_valid = 0;
      cfg->hdtv_fix = 0;
      cfg->original_tokens &= ~POPS_TOK_NOHDTVFIX;
    }
    *effect = 1;
    return 1;
  case CMD_LEFTADJ:
    number = command_number(rest, 3);
    if (number < 0)
      return 1;
    *value = (uint32_t)number;
    if (number >= 1 && number <= 255) {
      cfg->left_adjust = (uint8_t)number;
      *effect = 1;
    }
    return 1;
  case CMD_VCDID:
    /* Handlers 0x890f4c/0x8912e4/0x8917f0/0x891e78, one per digit count.
     * The first command wins: the handler is not tried once gp+0x38d8 is
     * set. $VCDID_0 stores 0 there, so the next one still runs. */
    if (cfg->vcdid_set)
      return 0;
    number = command_number(rest, 4);
    if (number < 0)
      return 1;
    cfg->vcdid = (uint16_t)number;
    cfg->vcdid_set = number != 0;
    *effect = 1;
    return 1;
  case CMD_PADID: {
    int id;
    if ((rest[0] != '0' && rest[0] != '1') || memcmp(rest + 1, "ID_0X", 5) ||
        !command_end(rest[8]))
      return 0;
    id = command_hex_byte(rest + 6);
    if (id < 0)
      return 1;
    *value = (uint32_t)id;
    cfg->pad_override |= (uint8_t)(1u << (rest[0] - '0'));
    cfg->pad_id[rest[0] - '0'] = (uint8_t)id;
    *effect = 1;
    return 1;
  }
  case CMD_POSITION:
    /* "$?POS_": the second byte is only looked at after the digits. A
     * number that is not 1..5 digits and a terminator leaves fp+0x90 as
     * the last number command left it ($LEFTADJ_, $?POS_, $DWSTRETCH_,
     * $DWCROP_, $PADnID_0X, $COMPATIBILITY_0X), and $XPOS_ / $YPOS_ then
     * write THAT value. */
    number = command_number(rest, 5);
    if (number >= 0)
      *value = (uint32_t)number;
    if (t[1] == 'X' || t[1] == 'Y')
      *effect = apply_position(cfg, t[1] == 'Y', *value);
    return 1;
  case CMD_STRETCH:
  case CMD_CROP:
    number = command_number(rest, 4);
    if (number < 0)
      return 1;
    *value = (uint32_t)number;
    if (command->kind == CMD_STRETCH) {
      cfg->display_stretch = (uint16_t)number;
      cfg->display_mask |= POPS_DISPLAY_STRETCH;
    } else {
      cfg->display_crop = (uint16_t)number;
      cfg->display_mask |= POPS_DISPLAY_CROP;
    }
    *effect = 1;
    return 1;
  case CMD_SAFEMODE:
    /* Neither handler is tried while one of the two is on (fp+0xec,
     * fp+0xf0): the first in a file decides. */
    if (cfg->safe_mode || !command_end(*rest))
      return 0;
    cfg->safe_mode = command->arg;
    *effect = 1;
    return 1;
  case CMD_NOSAFEMODE:
    /* Not tried unless one is on (gp+0x386c). */
    if (!cfg->safe_mode || !command_end(*rest))
      return 0;
    cfg->safe_mode = 0;
    *effect = 1;
    return 1;
  case CMD_USBDELAY:
    /* Exactly one digit and a terminator; the original stores the digit
     * in the byte at 0x100017 and leaves fp+0x90 alone. The last one in
     * the files wins. Anything else ("$USBDELAY_12", "$USBDELAY5") is not
     * a command. */
    if (rest[0] < '0' || rest[0] > '9' || !command_end(rest[1]))
      return 0;
    cfg->usb_delay = (uint8_t)(rest[0] - '0');
    cfg->usb_delay_set = 1;
    *effect = 1;
    return 1;
  case CMD_COMPAT: {
    int mode;
    if (!command_end(rest[2]))
      return 0;
    mode = command_hex_byte(rest);
    if (mode < 0)
      return 1;
    *value = (uint32_t)mode;
    /* FUN_008dc2c4 does nothing for a mode outside 1..7. */
    if (mode <= 7)
      add_compat_mode(cfg, mode);
    *effect = 1;
    return 1;
  }
  }
  return 0;
}

/* Tokens that are launcHER's own: POPStarter r13 has none of them. They
 * keep launcHER's earlier line rules: tokens are split at white space and a
 * token starting with '#' or ';' ends its line. The byte classes are spelt
 * out: the C library's isspace/isdigit follow the locale for bytes above
 * 0x7f, which a host test process and the EE build need not share. */
static int token_space(unsigned char c) {
  return c == ' ' || (c >= '\t' && c <= '\r'); /* TAB LF VT FF CR */
}

static int token_digit(unsigned char c) {
  return c >= '0' && c <= '9';
}

static void apply_launcher_token(PopsConfig *cfg, const char *token) {
  /* Not POPStarter commands; no grounded POPS writes exist for them. */
  if (!strcasecmp(token, "$480i") || !strcasecmp(token, "$576p") ||
      !strcasecmp(token, "$576i") || !strcasecmp(token, "$240p") ||
      !strncasecmp(token, "$VMODE", 6)) {
    DPRINTF("POPS config: %s is not a POPStarter command; ignored\n", token);
    return;
  }
  /* POPS runs NTSC unless the PAL patch is applied, so "PAL to NTSC" sets
   * POPS_VMODE_NOPAL: keep a European disc at 60 Hz. It is not quite the
   * original's $NOPAL: it does not test forced_pal, so it undoes an
   * earlier $FORCEPAL ("$FORCEPAL $PAL2NTSC" is no PAL), where $NOPAL
   * does not ("$FORCEPAL $NOPAL" is forced PAL). Whether these tokens
   * stay is an owner decision (docs/POPSTARTER_CONFIG_TEXT.md). */
  if (!strcasecmp(token, "$PAL2NTSC") || !strcasecmp(token, "$FORCENTSC")) {
    cfg->video_mode = POPS_VMODE_NOPAL;
    return;
  }
  if (!strcasecmp(token, "$NTSC2PAL")) {
    cfg->video_mode = POPS_VMODE_NTSC2PAL;
    return;
  }
  if (!strcasecmp(token, "$DITHER_OFF") || !strcasecmp(token, "$NODITHER")) {
    cfg->dither_off = 1;
    return;
  }
  if (!strcasecmp(token, "$FASTMIPS")) {
    cfg->fast_mips = 1;
    return;
  }
  if (!strcasecmp(token, "$SLOWMIPS")) {
    cfg->slow_mips = 1;
    return;
  }
  if (!strcasecmp(token, "$NOBOOT") || !strcasecmp(token, "$BIOS")) {
    cfg->no_boot = 1;
    return;
  }
  if (!strncasecmp(token, "$MODE", 5) && token_digit((unsigned char)token[5])) {
    add_compat_mode(cfg, (int)strtol(token + 5, NULL, 10));
    return;
  }
  if (token_digit((unsigned char)*token) && token[1] == '\0') {
    add_compat_mode(cfg, *token - '0');
    return;
  }
  if (!strcasecmp(token, "$FIX_TEXTURE_WINDOW")) {
    cfg->runtime_corrections |= POPS_FIX_TEXTURE_WINDOW;
    return;
  }
  if (!strcasecmp(token, "$FIX_GPU_DMA") || !strcasecmp(token, "$FIX_GPU_DMA_ZERO")) {
    cfg->runtime_corrections |= POPS_FIX_GPU_DMA_ZERO;
    return;
  }
  if (!strcasecmp(token, "$FIX_CDDA") || !strcasecmp(token, "$FIX_CDDA_SETMODE")) {
    cfg->runtime_corrections |= POPS_FIX_CDDA_SETMODE;
    return;
  }
  if (!strcasecmp(token, "$FIX_SPU_RESET") || !strcasecmp(token, "$FIX_SPU_ENABLE_RESET")) {
    cfg->runtime_corrections |= POPS_FIX_SPU_ENABLE_RESET;
    return;
  }
  if (!strcasecmp(token, "$FIX_GTE_RES1")) {
    cfg->runtime_corrections |= POPS_FIX_GTE_RES1;
    return;
  }
  if (!strcasecmp(token, "$FIX_ALL") || !strcasecmp(token, "$CORE_FIXES") ||
      !strcasecmp(token, "$PSXCORE_FIXES"))
    cfg->runtime_corrections |= POPS_FIX_ALL;
}

/* Copies the run of non-blank bytes at *at (up to a NUL or `size`) to
 * token + length and moves *at past the whole run. Returns the new token
 * length, or 0 when the run does not fit: a run longer than a token can
 * hold is no token at all, and its tail is not read as another one. */
static size_t launcher_token_run(const unsigned char *text, size_t size, size_t *at,
                                 char token[64], size_t length) {
  int fits = 1;
  while (*at < size && text[*at] && !token_space(text[*at])) {
    if (length < 63)
      token[length++] = (char)text[*at];
    else
      fits = 0;
    ++*at;
  }
  token[length] = '\0';
  return fits ? length : 0;
}

/* The next launcHER token at or after *position: its offset, or `size`
 * when there is none. "MODE n" / "$MODE n" on one line comes back as the
 * token "$MODEn". */
static size_t next_launcher_token(const unsigned char *text, size_t size, size_t *position,
                                  char token[64]) {
  size_t at = *position, start;
  for (;;) {
    while (at < size && text[at] && token_space(text[at]))
      ++at;
    if (at >= size)
      break;
    if (!text[at] || text[at] == '#' || text[at] == ';') {
      while (at < size && text[at] != '\n')
        ++at;
      continue;
    }
    start = at;
    if (!launcher_token_run(text, size, &at, token, 0))
      continue;
    if (!strcasecmp(token, "MODE") || !strcasecmp(token, "$MODE")) {
      size_t digit = at;
      while (digit < size && text[digit] != '\n' && token_space(text[digit]))
        ++digit;
      if (digit < size && token_digit(text[digit])) {
        memcpy(token, "$MODE", 5);
        at = digit;
        if (!launcher_token_run(text, size, &at, token, 5))
          continue;
      }
    }
    *position = at;
    return start;
  }
  *position = size;
  return size;
}

int pops_config_parse_text(PopsConfig *cfg, const char *text, size_t size, uint32_t value,
                           PopsConfigTrace trace, void *trace_context) {
  unsigned char *upper;
  char token[64];
  size_t i, token_position = 0, token_at;
  int result;
  if (!cfg || (!text && size))
    return -EINVAL;
  if (size > POPS_CONFIG_FILE_MAX)
    return -EFBIG;
  /* The original's buffer holds as many zero bytes after the text as the
   * text is long; no test here reads more than 32 bytes ahead. */
  upper = (unsigned char *)malloc(size + 32);
  if (!upper)
    return -ENOMEM;
  for (i = 0; i < size; ++i) {
    unsigned char c = (unsigned char)text[i];
    upper[i] = c >= 'a' && c <= 'z' ? (unsigned char)(c - 0x20) : c;
  }
  memset(upper + size, 0, 32);

  result = scan_cheats(cfg, (const char *)upper);

  token_at = result ? size : next_launcher_token(upper, size, &token_position, token);
  for (i = 0; !result && i < size;) {
    const unsigned char *t = upper + i;
    unsigned columns;
    /* launcHER's own tokens, in file order with the original's commands. */
    while (token_at <= i && token_at < size) {
      apply_launcher_token(cfg, token);
      token_at = next_launcher_token(upper, size, &token_position, token);
    }
    if (*t != '$') {
      ++i;
      continue;
    }
    columns = command_code_columns(t);
    if (columns) {
      if (trace)
        trace(trace_context, i, NULL, (int)columns);
      i += columns;
      continue;
    }
    for (size_t k = 0; k < sizeof(pops_commands) / sizeof(pops_commands[0]); ++k) {
      int effect;
      if (run_command(cfg, &pops_commands[k], t, &value, &effect)) {
        if (trace)
          trace(trace_context, i, pops_commands[k].name, effect);
        break;
      }
    }
    ++i;
  }
  while (!result && token_at < size) {
    apply_launcher_token(cfg, token);
    token_at = next_launcher_token(upper, size, &token_position, token);
  }
  free(upper);
  return result;
}

int pops_config_parse_line(PopsConfig *cfg, const char *line) {
  if (!cfg || !line)
    return -EINVAL;
  return pops_config_parse_text(cfg, line, strlen(line), 0, NULL, NULL);
}

/* Read a whole config file and close it. On success *out holds *out_size
 * bytes followed by 16 zero bytes, or is NULL for an empty file. */
static int read_config_text(FILE *f, char **out, size_t *out_size) {
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
  if (result) {
    free(text);
    text = NULL;
    size = 0;
  } else if (text) {
    memset(text + size, 0, 16);
  }
  *out = text;
  *out_size = size;
  return result;
}

/* `value` is what the original's shared number temporary (fp+0x90) holds
 * when the command pass starts: 0 for a file "for all games", the length
 * of its game-name string for the game's own CHEATS.TXT (0x883430). */
static int load_config_file(PopsConfig *cfg, const char *filepath, int optional_global,
                            uint32_t value) {
  if (!cfg || !filepath)
    return -EINVAL;

  /* Every byte counts in the command pass (a CR may be what ends a
   * command), so no text-mode translation where the host has one. */
  FILE *f = fopen(filepath, "rb");
  int error = errno;
  DPRINTF("POPS config: %s open=%d errno=%d\n", filepath, f != NULL, f ? 0 : error);
  errno = error;
  if (!f) {
    int result = errno ? -errno : -EIO;
    /* Only an optional global location that could not be opened is absent.
     * A device removed during reading must still fail after a successful open. */
    if (optional_global && (result == -ENOENT || result == -ENODEV || result == -ENXIO))
      return 0;
    return result;
  }

  cfg->gs_mask = 0; /* The original's six acceptance flags are file-local. */

  /* Read the whole file: POPStarter scans its text as one run of bytes,
   * with no line limit (pops_config_parse_text). */
  size_t size;
  char *text;
  int result = read_config_text(f, &text, &size);
  if (!result && text)
    result = pops_config_parse_text(cfg, text, size, value, NULL, NULL);
  free(text);
  return result;
}

int pops_config_load_file(PopsConfig *cfg, const char *filepath) {
  return load_config_file(cfg, filepath, 0, 0);
}

static int finish_file(FILE *file, int result) {
  if (!result && ferror(file))
    result = errno ? -errno : -EIO;
  if (fclose(file) && !result)
    result = errno ? -errno : -EIO;
  return result;
}

void pops_config_parse_discs(PopsConfig *cfg, char *text, size_t size) {
  size_t i, line = 0;
  if (!size)
    return;
  /* Any of these anywhere and the file is ignored: the slots keep what they
   * held, as the original's early return leaves them. */
  for (i = 0; i < size; ++i)
    if (text[i] == '\\' || text[i] == '/' || text[i] == ':')
      return;
  text[size] = '\0';
  for (i = 0; i < size; ++i)
    if (text[i] == '\r' || text[i] == '\n')
      text[i] = '\0';
  for (i = 0; i < size && line < POPS_MAX_DISCS; ++i) {
    size_t length;
    if (!text[i])
      continue;
    length = strlen(text + i);
    if (length >= POPS_DISC_LINE_MAX) {
      memset(cfg->disc_slot, 0, sizeof(cfg->disc_slot));
      break;
    }
    /* "pfs0:/", the line and one NUL; the slot's other bytes stay. */
    memcpy(cfg->disc_slot[line], POPS_DISC_SLOT_PREFIX, sizeof(POPS_DISC_SLOT_PREFIX) - 1);
    memcpy(cfg->disc_slot[line] + sizeof(POPS_DISC_SLOT_PREFIX) - 1, text + i, length);
    cfg->disc_slot[line][sizeof(POPS_DISC_SLOT_PREFIX) - 1 + length] = 0;
    i += length;
    ++line;
  }
  for (cfg->disc_count = 0; cfg->disc_count < POPS_MAX_DISCS &&
                            cfg->disc_slot[cfg->disc_count][0];)
    ++cfg->disc_count;
}

int pops_config_load_discs(PopsConfig *cfg, const char *filepath) {
  char *text;
  size_t size;
  int result;
  FILE *f;
  if (!cfg || !filepath)
    return -EINVAL;
  f = open_config(filepath);
  if (!f)
    return errno ? -errno : -EIO;
  result = read_config_text(f, &text, &size);
  if (!result && text)
    pops_config_parse_discs(cfg, text, size);
  free(text);
  return result;
}

int pops_config_parse_vmcdir(PopsConfig *cfg, const char *text, size_t size) {
  size_t length = 0;
  if (!cfg || (!text && size))
    return 0;
  /* 0x9b1a90: a file of 104 bytes or more is not used. */
  if (size >= POPS_VMCDIR_FILE_MAX)
    return 0;
  /* 0x9b1ac0: neither is one with any of these anywhere, a line end
   * after the name and bytes after a NUL included. */
  for (size_t i = 0; i < size; ++i)
    if (text[i] == '\r' || text[i] == '\n' || text[i] == '/' || text[i] == '\\' || text[i] == ':')
      return 0;
  /* The name is every byte up to a NUL or the end, as it stands. */
  while (length < size && text[length])
    ++length;
  memcpy(cfg->vmc_dir, text, length);
  cfg->vmc_dir[length] = '\0';
  cfg->vmc_dir_set = 1;
  return 1;
}

int pops_config_load_vmcdir(PopsConfig *cfg, const char *filepath) {
  char text[POPS_VMCDIR_FILE_MAX];
  size_t size = 0;
  int result = 0;
  FILE *f;
  if (!cfg || !filepath)
    return -EINVAL;
  /* Binary: a CR counts. */
  f = fopen(filepath, "rb");
  {
    int error = errno;
    DPRINTF("POPS config: %s open=%d errno=%d\n", filepath, f != NULL, f ? 0 : error);
    errno = error;
  }
  if (!f)
    return errno ? -errno : -EIO;
  /* POPS_VMCDIR_FILE_MAX bytes are enough to know the file is too long. */
  while (size < sizeof(text)) {
    size_t got = fread(text + size, 1, sizeof(text) - size, f);
    if (!got)
      break;
    size += got;
  }
  result = finish_file(f, 0);
  if (!result)
    pops_config_parse_vmcdir(cfg, text, size);
  return result;
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
    result = load_config_file(cfg, path, 1, 0);
    if (result)
      return result;

    snprintf(path, sizeof(path), "%sMODES.TXT", globalDirs[g]);
    result = load_config_file(cfg, path, 1, 0);
    if (result)
      return result;

    snprintf(path, sizeof(path), "%sCHEATS.TXT", globalDirs[g]);
    result = load_config_file(cfg, path, 1, 0);
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
    /* The original's game-name string (gp+0x38f0) is the folder name and a
     * '/' (0x874ddc..0x8750e4), and its length is where the reader's shared
     * number starts (0x883430). */
    result = load_config_file(cfg, path, 0, (uint32_t)strlen(subfolder) + 1);
    if (result && result != -ENOENT)
      return result;

    /* The original reads POPS/DISCS.TXT ("for all games") and then the
     * game's own over it, slot by slot. */
    snprintf(path, sizeof(path), "%s%s/DISCS.TXT", vcd_dir, subfolder);
    result = pops_config_load_discs(cfg, path);
    if (result && result != -ENOENT)
      return result;
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
    /* 0x871208..0x871218: the start-up's own clear of the forced-PAL word. */
    cfg->video_mode = POPS_VMODE_480P;
    cfg->progressive_requested = 1;
    cfg->forced_pal = 0;
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

