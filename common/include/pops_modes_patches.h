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

/* Fix-file session after the identified core and initial config patches.
 * Retains expected bytes across ordered/repeated mode dispatch and explicit
 * external payload writes. No executable is entered and no live RAM is used.
 * Discard the staged core on any failure in a sequence of fix files. */
#define POPS_COMPAT_SITE_COUNT 39
typedef struct {
  uint32_t expected[POPS_COMPAT_SITE_COUNT];
  uint8_t video_auto_disabled;
  uint8_t video_custom_set;
} PopsFixContext;
int pops_fix_context_init(PopsFixContext *context, const void *staged_core,
                           size_t core_size, uint8_t initial_modes);
/* expected_trojan selects TROJAN versus PATCH; slot must match the filename.
 * PATCH data precedes its four mode bytes, in recorded order. Video actions
 * (PAL, disable-auto) and mode 6 are supported. Video actions 6/7 require
 * absent resident code; they and mode 8 fail before any payload/mode writes.
 * Context, input container and staged core must be disjoint. */
int pops_fix_stage(PopsFixContext *context, void *staged_core, size_t core_size,
                    const void *file, size_t file_size, unsigned slot,
                    int expected_trojan);

/* $FORCEPAL (POPS_VMODE_NTSC2PAL) PAL patch and $HDTVFIX. Every other
 * mode and nonzero offsets return -ENOTSUP: they have no grounded writes. */
int pops_apply_video_overrides(void *staged_core, size_t core_size,
                               uint8_t video_mode, uint8_t hdtv_fix,
                               int16_t x_offset, int16_t y_offset);

/* POPS_REGION_* from the 4 licence bytes at VCD offset 0x102514 */
int pops_region_from_licence(const char tag[4]);

/* POPStarter's region pass: auto PAL for European discs (unless $NOPAL,
 * $480p or a PATCH file disabled it) and the POPS/BIOS region letters.
 * Run after the fix files. */
int pops_apply_region(void *staged_core, size_t core_size, int region,
                      uint8_t video_mode, int auto_video_disabled);

/* Fixed-value POPStarter commands (POPS_TOK_* mask) */
int pops_apply_original_tokens(void *staged_core, size_t core_size, uint32_t tokens);

/* POPStarter $IGR0..$IGR5 (igr_type 1..6) or $NOIGR writes */
int pops_apply_igr_original(void *staged_core, size_t core_size,
                            uint8_t igr_type, uint8_t no_igr);

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

/* Alternate In-Game Reset combo ($IGR2): L1 + L2 + R1 + R2 + SELECT + CROSS */
#define POPS_IGR2_COMBO   (POPS_PAD_L1 | POPS_PAD_L2 | POPS_PAD_R1 | POPS_PAD_R2 | POPS_PAD_SELECT | POPS_PAD_CROSS)

/* Multi-disc hotkey swap combo: SELECT + L1 + R1 */
#define POPS_SWAP_COMBO   (POPS_PAD_SELECT | POPS_PAD_L1 | POPS_PAD_R1)

/* POPS filesystem devctl command codes */
#define POPS_DEVCTL_SWAP_DISC    0x01
#define POPS_DEVCTL_GET_DISC     0x02
#define POPS_DEVCTL_OPEN_LID     0x03
#define POPS_DEVCTL_CLOSE_LID    0x04
#define POPS_DEVCTL_SET_LIBCRYPT 0x05
#define POPS_DEVCTL_GET_SUBQ     0x06
#define POPS_DEVCTL_NEXT_DISC    0x07
#define POPS_DEVCTL_GET_LID      0x08

/* Safe mode boot frame delay threshold (approximately 3 seconds at 60Hz) */
#define POPS_SAFE_MODE_FRAME_DELAY 180

/* Detect In-Game Reset button combination (buttons_active_low: 0 = pressed) */
int pops_check_igr_combo(uint16_t buttons_active_low);

/* Detect In-Game Reset button combination with mode (0 = disabled, 1 = default, 2 = alternate) */
int pops_check_igr_combo_type(uint16_t buttons_active_low, uint8_t igr_type);

/* Detect Multi-disc swap button combination (buttons_active_low: 0 = pressed) */
int pops_check_disc_swap_combo(uint16_t buttons_active_low);

/* In-game multi-disc swap handler: verifies swap combo, opens lid, advances disc, closes lid */
int pops_handle_disc_swap(uint16_t buttons_active_low,
                          int (*devctl_fn)(const char *dev, int cmd, void *arg, size_t arglen, void *buf, size_t buflen));

/* Generates 12-byte Subchannel Q data for a requested LBA with BCD MSF and LibCrypt key in CRC */
int pops_generate_subq(uint32_t lba, uint16_t libcrypt_key, uint8_t out_subq[12]);

/* Queries CD-ROM Subchannel Q frame from popfs devctl bridge */
int pops_cdrom_read_subq(int (*devctl_fn)(const char *dev, int cmd, void *arg, size_t arglen, void *buf, size_t buflen),
                         uint32_t lba, uint8_t out_subq[12]);

/* Periodically evaluates and applies GameShark codes to guest PS1 RAM with conditional support */
int pops_cheat_engine_tick(void *ps1_ram_base, const PopsCheatEntry *cheats, uint16_t cheat_count);

/* Evaluates GameShark codes to guest PS1 RAM with conditional support and safe mode deferral */
int pops_cheat_engine_tick_ex(void *ps1_ram_base, const PopsCheatEntry *cheats,
                             uint16_t cheat_count, uint32_t frame_count, uint8_t safe_mode);


/* Direct clean IGR exit: rewires 0x00228a5c..0x00228a68 to set $v0 = 1 and branch to epilogue,
 * preserving pristine delay slot 0x00228a58 (move $v0, $zero) so normal gameplay returns 0,
 * while reset combo returns 1 triggering stock POPS audio/video shutdown and ExecOSD */
int pops_apply_igr_direct_exit(void *staged_core, size_t core_size);

/* Enable controller pad navigation and confirmation in native IGR prompt dialog:
 * rewires 0x002264c4 to read held buttons from 4($a0) instead of ephemeral 0($a0),
 * and rewires 0x002264f4 to accept either Circle (0x20) or Cross (0x40) to confirm */
int pops_apply_igr_pad_control(void *staged_core, size_t core_size);

/* Fix IGR exit method (FUN_008dbe08): rewires 0x0020c0a4 from 0x0c08b44c to 0x0c08d8ae */
int pops_apply_igr_exit(void *staged_core, size_t core_size);

/* Increase IOPCD stack size (FUN_008dbee4): rewires 0x002fb599 from 0x08 to stack_size (default 0x40 = 16 KiB) */
int pops_apply_iopcd_stack_size(void *staged_core, size_t core_size, uint8_t stack_size);

/* Patch HddInit failure exit (FUN_008dc0c0): rewires 0x00200766 from 0x1040 to 0x1000 */
int pops_apply_hdd_init_exit(void *staged_core, size_t core_size);

/* Disable Memory Card 0 emulation ($NOVMC0 / FUN_008dc12c(1)): rewires 0x002007b4 from 0x01 to 0x00 */
int pops_apply_vmc0_disable(void *staged_core, size_t core_size);

/* Disable Memory Card 1 emulation ($NOVMC1 / FUN_008dc12c(2)): rewires 0x0020d0e0 from 0x1480ffc1 to 0x24040000 */
int pops_apply_vmc1_disable(void *staged_core, size_t core_size);

/* Bypass SLBB-00001 VCD check (FUN_008dbcdc):
 * rewires 0x00200834 from 0x0c08b520 to 0x00000000,
 * 0x0020083c from 0x0441000a (or 0x1000000a) to 0x1000000a,
 * and 0x0020085c from 0x1000fffa (or 0x00000000) to 0x00000000 */
int pops_apply_slbb_vcd_check_bypass(void *staged_core, size_t core_size);

/* Disable built-in BIOS OSD shell (FUN_008db97c): rewires 0x002525b0 from 0x1bfc to 0x0648 */
int pops_apply_bios_osd_disable(void *staged_core, size_t core_size);

/* Re-enable built-in BIOS OSD shell (FUN_008dba20): rewires 0x002525b0 from 0x0648 to 0x1bfc */
int pops_apply_bios_osd_enable(void *staged_core, size_t core_size);

/* Patch SLBB-00001 VCD path to pfs1:/POPS/ (FUN_008dbd6c) */
int pops_apply_slbb_vcd_path_redirect(void *staged_core, size_t core_size);

/* Relink resource paths to pfs1:/ or pfs1:/POPS/ (FUN_008db7e4) */
int pops_apply_resource_relink(void *staged_core, size_t core_size, int is_usb_flat);

/* Install exception hook at 0x00232d08 (FUN_008d6da4) */
int pops_apply_exception_hook(void *staged_core, size_t core_size);

/* Apply all settings from a PopsConfig structure to the staged core */
int pops_apply_all_config_patches(void *staged_core, size_t core_size, const PopsConfig *cfg);

#ifdef __cplusplus
}
#endif

#endif /* POPS_MODES_PATCHES_H */
