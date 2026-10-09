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

/* Apply all settings from a PopsConfig structure to the staged core */
int pops_apply_all_config_patches(void *staged_core, size_t core_size, const PopsConfig *cfg);

#ifdef __cplusplus
}
#endif

#endif /* POPS_MODES_PATCHES_H */
