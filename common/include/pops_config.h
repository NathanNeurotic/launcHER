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
};

#define POPS_MAX_DISCS    4
#define POPS_MAX_CHEATS   256

typedef struct {
  uint32_t address;
  uint16_t value;
  uint8_t type; /* 0x80 (16-bit), 0x30 (8-bit), 0xD0 (conditional) */
} PopsCheatEntry;

typedef struct {
  /* Video settings */
  uint8_t video_mode;
  uint8_t hdtv_fix;
  int16_t x_offset;
  int16_t y_offset;
  uint8_t smooth;

  /* Engine throttling */
  uint8_t fast_mips;
  uint8_t slow_mips;

  /* System options */
  uint8_t no_boot;  /* $NOBOOT / $BIOS forces PS1 BIOS OSD shell */
  uint8_t no_igr;   /* $NOIGR disables In-Game Reset */

  /* Compatibility modes bitmask: (1 << (mode - 1)) for Modes 1..8 */
  uint8_t compat_modes;

  /* Multi-disc support from DISCS.TXT */
  uint8_t disc_count;
  char discs[POPS_MAX_DISCS][128];

  /* Custom VMC directory from VMCDIR.TXT */
  char vmc_dir[128];

  /* Cheats from CHEATS.TXT */
  uint16_t cheat_count;
  PopsCheatEntry cheats[POPS_MAX_CHEATS];
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
 * in candidate directories (game VCD directory and VMC directory). */
int pops_config_discover(PopsConfig *cfg, const char *vcd_dir, const char *game_base);

#ifdef __cplusplus
}
#endif

#endif /* POPS_CONFIG_H */
