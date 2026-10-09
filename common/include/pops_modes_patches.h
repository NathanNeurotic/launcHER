#ifndef POPS_MODES_PATCHES_H
#define POPS_MODES_PATCHES_H

#include "pops_config.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Apply Compatibility Modes 1..8 to the staged POPS core */
int pops_apply_compat_modes(void *staged_core, size_t core_size, uint8_t modes_mask);

/* Apply Video Mode overrides (PAL/NTSC, 480p, 576p, HDTV fix, X/Y centering) */
int pops_apply_video_overrides(void *staged_core, size_t core_size,
                               uint8_t video_mode, uint8_t hdtv_fix,
                               int16_t x_offset, int16_t y_offset);

/* Apply texture smoothing ($SMOOTH) */
int pops_apply_smooth(void *staged_core, size_t core_size);

/* Apply recompiler throttling ($FASTMIPS, $SLOWMIPS) */
int pops_apply_throttling(void *staged_core, size_t core_size, uint8_t fast_mips, uint8_t slow_mips);

/* Force boot into the PS1 BIOS OSD Shell ($NOBOOT / $BIOS) */
int pops_apply_bios_shell(void *staged_core, size_t core_size);

/* Apply LibCrypt subchannel Q emulation bypass */
int pops_apply_libcrypt_bypass(void *staged_core, size_t core_size);

/* Apply GameShark / Action Replay cheats to PS1 RAM (0x01000000..0x01200000) */
int pops_apply_cheats(void *ps1_ram_base, const PopsCheatEntry *cheats, uint16_t cheat_count);

#define POPS_PAD_SELECT   0x0001
#define POPS_PAD_L3       0x0002
#define POPS_PAD_R3       0x0004
#define POPS_PAD_START    0x0008
#define POPS_PAD_UP       0x0010
#define POPS_PAD_RIGHT    0x0020
#define POPS_PAD_DOWN     0x0040
#define POPS_PAD_LEFT     0x0080
#define POPS_PAD_L2       0x0100
#define POPS_PAD_R2       0x0200
#define POPS_PAD_L1       0x0400
#define POPS_PAD_R1       0x0800
#define POPS_PAD_TRIANGLE 0x1000
#define POPS_PAD_CIRCLE   0x2000
#define POPS_PAD_CROSS    0x4000
#define POPS_PAD_SQUARE   0x8000

/* Universal In-Game Reset combo: L1 + L2 + R1 + R2 + SELECT + START */
#define POPS_IGR_COMBO    (POPS_PAD_L1 | POPS_PAD_L2 | POPS_PAD_R1 | POPS_PAD_R2 | POPS_PAD_SELECT | POPS_PAD_START)

/* Multi-disc hotkey swap combo: SELECT + L1 + R1 */
#define POPS_SWAP_COMBO   (POPS_PAD_SELECT | POPS_PAD_L1 | POPS_PAD_R1)

/* Detect In-Game Reset button combination (buttons_active_low: 0 = pressed) */
int pops_check_igr_combo(uint16_t buttons_active_low);

/* Detect Multi-disc swap button combination (buttons_active_low: 0 = pressed) */
int pops_check_disc_swap_combo(uint16_t buttons_active_low);

/* Generates 12-byte Subchannel Q data for a requested LBA with BCD MSF and LibCrypt key in CRC */
int pops_generate_subq(uint32_t lba, uint16_t libcrypt_key, uint8_t out_subq[12]);

/* Periodically evaluates and applies GameShark codes to guest PS1 RAM with 0xD0 conditional support */
int pops_cheat_engine_tick(void *ps1_ram_base, const PopsCheatEntry *cheats, uint16_t cheat_count);

/* Apply all settings from a PopsConfig structure to the staged core */
int pops_apply_all_config_patches(void *staged_core, size_t core_size, const PopsConfig *cfg);

#ifdef __cplusplus
}
#endif

#endif /* POPS_MODES_PATCHES_H */
