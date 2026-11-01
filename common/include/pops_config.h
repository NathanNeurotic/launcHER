#ifndef POPS_CONFIG_H
#define POPS_CONFIG_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum PopsVideoMode {
  POPS_VMODE_DEFAULT = 0,
  POPS_VMODE_PAL2NTSC,
  POPS_VMODE_NTSC2PAL,
  POPS_VMODE_NOPAL,
  POPS_VMODE_480P,
  POPS_VMODE_480I,
  POPS_VMODE_576P,
  POPS_VMODE_576I,
  POPS_VMODE_240P,
};

/* Disc region from the licence text in sector 4 (POPStarter reads VCD offset
 * 0x102514: "Euro", "Amer"/"of A" or "Inc."). */
enum PopsRegion {
  POPS_REGION_UNKNOWN = 0,
  POPS_REGION_EUROPE,
  POPS_REGION_AMERICA,
  POPS_REGION_JAPAN,
};

/* Fixed-value POPStarter r13 CHEATS.TXT commands whose writes land in the
 * POPS core itself (recovered from the original's command handlers). */
#define POPS_TOK_SCANLINES        (1u << 0)
#define POPS_TOK_SUBCDSTATUS      (1u << 1)
#define POPS_TOK_MUTE_CDDA        (1u << 2)
#define POPS_TOK_UNDO_MUTE_CDDA   (1u << 3)
#define POPS_TOK_MUTE_VAB         (1u << 4)
#define POPS_TOK_MUTE_ALL         (1u << 5)
#define POPS_TOK_CODECACHE_ADDON0 (1u << 6)
#define POPS_TOK_CODECACHE_ADDON1 (1u << 7)
#define POPS_TOK_CODECACHE_ADDON2 (1u << 8)
#define POPS_TOK_ROLLBACK         (1u << 9)
#define POPS_TOK_CACHE1           (1u << 10)
#define POPS_TOK_NOHDTVFIX        (1u << 11)
/* The $UNDO_* commands run before $COMPATIBILITY_0x in the original, so
 * they are applied by pops_apply_undo_tokens ahead of the compat modes. */
#define POPS_TOK_UNDO_COMPAT      (1u << 12)
#define POPS_TOK_UNDO_GAME_FIXES  (1u << 13)
#define POPS_TOK_UNDO_LIBCRYPT    (1u << 14)
#define POPS_TOK_UNDO_MASK        (POPS_TOK_UNDO_COMPAT | POPS_TOK_UNDO_GAME_FIXES | POPS_TOK_UNDO_LIBCRYPT)
#define POPS_TOK_COUNT            15

#define POPS_DISPLAY_X       0x01
#define POPS_DISPLAY_Y       0x02
#define POPS_DISPLAY_STRETCH 0x04
#define POPS_DISPLAY_CROP    0x08
#define POPS_DISPLAY_ALL     0x0f

#define POPS_MAX_DISCS    4
#define POPS_MAX_CHEATS   256

/* Cheat gates. POPStarter puts one test in front of its cheat codes and
 * skips them for that pass while it holds: $SAFEMODE while the PS1 RAM word
 * at 0x1ffea0 reads "STEM" (0x4d455453), otherwise $SAFEMODE2 while the
 * word at 0x1ffdf4 is 2. $SAFEMODE wins when both are set. */
#define POPS_SAFE_MODE_BOOT       0x01u /* $SAFEMODE */
#define POPS_SAFE_MODE_2          0x02u /* $SAFEMODE2 */
#define POPS_SAFE_MODE_BOOT_ADDR  0x001ffea0u
#define POPS_SAFE_MODE_BOOT_VALUE 0x4d455453u
#define POPS_SAFE_MODE_2_ADDR     0x001ffdf4u
#define POPS_SAFE_MODE_2_VALUE    2u


typedef struct {
  uint32_t address;
  uint32_t value;
  uint8_t type; /* POPS_CHEAT_* below, or a PS1 GameShark type: 0x80/0x10 (16-bit),
                 0x30/0x20 (8-bit), 0xD0..0xD3/0xE0..0xE1 (conditional),
                 0xC0 (master code), 0x50 (repeat: address = XXYY, value = step) */
  uint8_t cond; /* PS2-format codes: POPS_CHEAT_COND_* */
  uint8_t skip; /* conditionals: codes skipped when false (0 counts as 1) */
  uint8_t reserved;
} PopsCheatEntry;

/* Bits 0..20 of a PS1 code's address are the PS1 RAM address. */
#define POPS_CHEAT_ADDR_MASK  0x001FFFFFu

/* PS2-format codes, POPStarter style, type | size (0 byte, 1 half, 2 word):
 *   $0/$1/$2AAAAAAA VVVVVVVV  EE RAM write
 *   $S<size><cond>0OOOO VVVVVVVV  EE scratchpad (0x70000000 + 0..0x3FFF)
 *   $T<size><cond>00OOO VVVVVVVV  PS1 scratchpad as POPS maps it
 *                                  (0x5F800000 + 0..0x3FF)
 *   $=/$!AAAAAAA VVVVVVVV  EE RAM word equal / not equal (cond EQ / NE)
 * A conditional runs the next code only when it holds. */
#define POPS_CHEAT_EE         0x90u
#define POPS_CHEAT_SPR        0x94u
#define POPS_CHEAT_PS1SPR     0x98u
#define POPS_CHEAT_IS_PS2(t)  (((t) & 0xF0u) == 0x90u && ((t) & 3u) != 3u && (t) < 0x9Cu)
#define POPS_CHEAT_COND_NONE  0u
#define POPS_CHEAT_COND_EQ    1u
#define POPS_CHEAT_COND_NE    2u
#define POPS_CHEAT_SPR_ADDR   0x70000000u
#define POPS_CHEAT_PS1SPR_ADDR 0x5F800000u

/* Only in compiled code (pops_cheats_compile), modelling POPStarter's two
 * compare registers: LOAD16 is a $D0's load (k0 = signed RAM half, k1 =
 * value), BNE skips `skip` codes when k0 != k1, W32 is a 32-bit PS1 write
 * (a repeat's leftover store after a $2 code). */
#define POPS_CHEAT_BNE        0x01u
#define POPS_CHEAT_LOAD16     0x02u
#define POPS_CHEAT_W32        0x40u

typedef struct {
  /* Video settings */
  uint8_t video_mode;
  uint8_t hdtv_fix;
  int16_t x_offset;
  int16_t y_offset;
  /* $SMOOTH patches the core directly. widescreen is POPS_WIDESCREEN_*,
   * applied by the resident code; $DITHER_OFF is not a POPStarter command. */
  uint8_t smooth;
  uint8_t widescreen;
  uint8_t dither_off;

  /* Recorded but not applied: not POPStarter commands */
  uint8_t fast_mips;
  uint8_t slow_mips;

  /* System options */
  uint8_t no_boot;      /* $NOBOOT / $BIOS keeps the PS1 BIOS boot logo */
  uint8_t no_igr;       /* $NOIGR: POPStarter's IGR-off writes */
  uint8_t igr_type;     /* 0 = launcHER direct exit, 1..6 = $IGR0..$IGR5 */
  uint8_t safe_mode;    /* POPS_SAFE_MODE_* bits: $SAFEMODE, $SAFEMODE2; $NOSAFEMODE clears */
  uint8_t usb_delay;    /* $USBDELAY_# seconds */
  uint8_t no_vmc0;      /* $NOVMC0 disables Memory Card 0 emulation */
  uint8_t no_vmc1;      /* $NOVMC1 disables Memory Card 1 emulation */

  /* Compatibility modes bitmask: (1 << (mode - 1)) for Modes 1..8 */
  uint8_t compat_modes;

  /* Runtime core corrections bitmask: POPS_FIX_* (0x01..0x1F) */
  uint8_t runtime_corrections;

  /* Multi-disc support from DISCS.TXT */
  uint8_t disc_count;
  char discs[POPS_MAX_DISCS][128];

  /* Custom VMC directory from VMCDIR.TXT */
  char vmc_dir[128];

  /* Cheats from CHEATS.TXT */
  uint16_t cheat_count;
  PopsCheatEntry cheats[POPS_MAX_CHEATS];

  /* POPS_TOK_* commands from CHEATS.TXT */
  uint32_t original_tokens;
  /* Disc region (POPS_REGION_*); set by the launcher from the VCD */
  uint8_t disc_region;

  /* Original computed display commands. Explicit mask distinguishes zero
   * from absent. X/Y use the first valid command, as the original does. */
  uint16_t display_x, display_y, display_stretch, display_crop;
  uint8_t display_mask;
  uint8_t left_adjust; /* $LEFTADJ_1..255; zero is absent */

  /* Manual GS DISPLAY override: all six first-valid decimal values must
   * occur in one file. A later incomplete file keeps the previous override. */
  uint64_t gs_display;
  uint32_t gs_values[6]; /* DX, DY, MAGH, MAGV, DW, DH */
  uint8_t gs_mask;
  uint8_t gs_display_valid;
  uint8_t progressive_requested; /* $480p remains active across region commands */

  /* Pad commands, applied by the resident code (pops_resident.h). Bit n of
   * pad_override forces the controller ID that port n reports to the game
   * to pad_id[n]. Later commands overwrite earlier ones, as in the original:
   * $NOPADn sets ID 1, $PADnID_0Xhh sets hh, $D2LS sets 0x41 on both ports.
   * pad_d2ls swaps the D-pad and the left stick ($D2LS, $D2LS_ALT). */
  uint8_t pad_override;
  uint8_t pad_id[2];
  uint8_t pad_d2ls;

  /* $SET_TIMINGS: live timing adjust in the resident code (pops_resident.h). */
  uint8_t set_timings;

  /* $VCDID_n (1..4 decimal digits; the first one in the files wins, as the
   * original's handlers check gp+0x38d8 first): a built-in per-game entry
   * by hand (pops_builtin_db.h). It is used only when the disc fingerprint
   * matched nothing, which is also how the original behaves. */
  uint16_t vcdid;
  uint8_t vcdid_set;
  /* $SUBCDSTATUS seen: the original's gp+0x3458 flag, after which its
   * compatibility helper ignores modes 1, 2, 3 and 5. */
  uint8_t subcd_seen;

  /* Set by the launcher from the built-in entry it applied (PopsBuiltinPlan),
   * for the resident code: the entry id, the chain calls, and the second
   * LibCrypt code the chain runs. */
  uint16_t builtin_id;
  uint8_t builtin_fix_call;
  uint8_t builtin_break_call;
  uint8_t builtin_libcrypt2;
  uint8_t builtin_libcrypt2_code[84];
} PopsConfig;

/* $WIDESCREEN, $ULTRA_WIDESCREEN, $EYEFINITY: the last one in the files wins,
 * as each original handler rewrites all of the same sites. */
#define POPS_WIDESCREEN_NONE      0
#define POPS_WIDESCREEN_16_9      1 /* x * 75 / 100 */
#define POPS_WIDESCREEN_ULTRA     2 /* 16:9 plus a second x * 75 / 100 */
#define POPS_WIDESCREEN_EYEFINITY 3 /* x / 4 */

#define POPS_PAD_ID_NONE    0x01 /* what $NOPADn makes a port report */
#define POPS_PAD_ID_DIGITAL 0x41 /* PS1 digital pad */

/* Initialize configuration with factory defaults */
void pops_config_init(PopsConfig *cfg);

/* Parse a single configuration line (from PATCHES.TXT, MODES.TXT, or CHEATS.TXT) */
int pops_config_parse_line(PopsConfig *cfg, const char *line);

/* Parse a text file into configuration */
int pops_config_load_file(PopsConfig *cfg, const char *filepath);

/* Parse DISCS.TXT (up to 4 VCD filenames, 1 per line) */
int pops_config_load_discs(PopsConfig *cfg, const char *filepath);

/* Parse VMCDIR.TXT (single folder name) */
int pops_config_load_vmcdir(PopsConfig *cfg, const char *filepath);

/* Parse CHEATS.TXT (GameShark codes and $ directives) */
int pops_config_load_cheats(PopsConfig *cfg, const char *filepath);

/* Discovers and loads PATCHES.TXT, MODES.TXT, CHEATS.TXT, DISCS.TXT, VMCDIR.TXT
 * in memory-card, VCD root and title directories. VMCDIR redirects saves only. */
int pops_config_discover(PopsConfig *cfg, const char *vcd_dir, const char *game_base);

/* Import configuration from verified 32-byte POPStarter configuration table ($410 - $42F) */
int pops_config_load_table(PopsConfig *cfg, const uint8_t table[32]);

/* Export configuration to 32-byte POPStarter configuration table ($410 - $42F) */
void pops_config_export_table(const PopsConfig *cfg, uint8_t table[32]);

#ifdef __cplusplus
}
#endif

#endif /* POPS_CONFIG_H */
