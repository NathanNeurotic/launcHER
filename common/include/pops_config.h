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
#define POPS_TOK_COUNT            12

#define POPS_DISPLAY_X       0x01
#define POPS_DISPLAY_Y       0x02
#define POPS_DISPLAY_STRETCH 0x04
#define POPS_DISPLAY_CROP    0x08
#define POPS_DISPLAY_ALL     0x0f

#define POPS_MAX_DISCS    4
#define POPS_MAX_CHEATS   256

typedef struct {
  uint32_t address;
  uint16_t value;
  uint8_t type; /* 0x80/0x10 (16-bit), 0x30/0x20 (8-bit), 0xD0..0xD3/0xE0..0xE1 (conditional) */
} PopsCheatEntry;

typedef struct {
  /* Video settings */
  uint8_t video_mode;
  uint8_t hdtv_fix;
  int16_t x_offset;
  int16_t y_offset;
  /* $SMOOTH patches the core directly. $WIDESCREEN still needs independent
   * resident code; $DITHER_OFF is not a POPStarter command. */
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
  uint8_t safe_mode;    /* $SAFEMODE delays cheat activation */
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
} PopsConfig;

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
