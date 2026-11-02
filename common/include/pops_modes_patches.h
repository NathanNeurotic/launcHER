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
#define POPS_PATCH_PAL_SITE_COUNT 4
#define POPS_PATCH_RESIDENT_SITE_COUNT 4
typedef struct {
  uint32_t expected[POPS_COMPAT_SITE_COUNT];
  uint32_t video_expected[POPS_PATCH_PAL_SITE_COUNT];
  uint8_t video_auto_disabled;
  uint8_t video_custom_set;
  uint32_t resident_entry;
  uint32_t resident_expected[POPS_PATCH_RESIDENT_SITE_COUNT];
  uint8_t progressive_set;
} PopsFixContext;
int pops_fix_context_init(PopsFixContext *context, const void *staged_core,
                           size_t core_size, uint8_t initial_modes);
/* Production text configuration has already been staged; $FORCEPAL is still
 * deferred. Preserve $480p's original disable-PAL state. $NOPAL suppresses
 * the later automatic region pass, not an explicit PATCH PAL action. */
int pops_fix_context_init_video(PopsFixContext *context, const void *staged_core,
                                 size_t core_size, uint8_t initial_modes,
                                 uint8_t initial_video_mode);
/* Bind an entry from a validated owned image before processing any files.
 * Unbound sessions continue to reject actions 6/7. initial_interlace is the
 * already-staged text argument (pristine ANDI or HDTVFIX's LI a0,1). */
int pops_fix_bind_progressive(PopsFixContext *context, const void *staged_core,
                              size_t core_size, uint32_t entry, uint32_t initial_interlace);
/* After a PATCH installed progressive output, reject a later conflicting
 * payload instead of silently replacing its static hook/mode/argument writes. */
int pops_fix_require_progressive(const PopsFixContext *context, const void *staged_core,
                                 size_t core_size);
/* Final video pass after ordered fix files. Validate tracked sites, then
 * apply forced/European PAL as allowed by the original state. An unread
 * licence can use UNKNOWN here: this function never changes region letters. */
int pops_fix_finalize_video(PopsFixContext *context, void *staged_core,
                             size_t core_size, int region, uint8_t video_mode);
/* expected_trojan selects TROJAN versus PATCH; slot must match the filename.
 * PATCH data precedes its four mode bytes, in recorded order. Video actions
 * (PAL, disable-auto) and mode 6 are supported. Video actions 6/7 still need
 * verified resident/session dispatch; they and mode 8 fail before writes.
 * Context, input container and staged core must be disjoint. */
int pops_fix_stage(PopsFixContext *context, void *staged_core, size_t core_size,
                    const void *file, size_t file_size, unsigned slot,
                    int expected_trojan);

/* Direct $FORCEPAL (POPS_VMODE_NTSC2PAL) and $HDTVFIX writes. $480p uses the
 * separate resident installer; progressive/unsupported modes and nonzero
 * offsets return -ENOTSUP here. NOPAL requests leave video unchanged here. */
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

/* $UNDO_COMPATIBILITY_CODES, $UNDO_GAME_FIXES, $UNDO_LIBCRYPT_FIX: the
 * original handlers' core writes. Run before the compat modes. Writes the
 * original makes inside its own resident blob are not POPS code here and
 * are left out. */
int pops_apply_undo_tokens(void *staged_core, size_t core_size, uint32_t tokens);

/* $SMOOTH, $LEFTADJ_, $XPOS_/$YPOS_, $DWSTRETCH_ and $DWCROP_. All
 * selected sites are checked before writes; no resident code is required. */
int pops_apply_display_config(void *staged_core, size_t core_size, const PopsConfig *cfg);

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

/* As pops_cheat_engine_tick, skipped while the safe mode gate holds.
 * frame_count is unused (kept for the existing callers). */
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

/* One compatibility mode's writes (FUN_008dc2c4 mode k, 1..7) with no
 * check of the current bytes, the way the original's built-in per-game
 * list applies them before any command runs. */
int pops_compat_mode_write(void *staged_core, size_t core_size, uint8_t mode);

/* $RESET_WARMBOOT: POPStarter r13's pass at 0x8795f0..0x879cf4, run after
 * the region pass when gp+0x3894 is set. It walks POPS's embedded PS1 BIOS
 * ROM copy downward from POPS_WARMBOOT_SCAN_TOP to (not including)
 * POPS_WARMBOOT_ROM_BASE looking for the BIOS call stubs
 *   addiu $t2, $zero, 0xA0|0xB0|0xC0 ; jr $t2 ; addiu $t1, $zero, func
 * and rewrites a fixed list of them to A0:A0 (_boot, a warm boot): A0
 * stubs get the function byte, B0/C0 stubs the table byte and the function
 * byte. For each A0:3A (SystemErrorExit) stub it also records the stub's
 * address, the last one found (lowest address) winning; that address
 * becomes what the in-game reset combo makes the PS1 jump to
 * (PopsResidentConfig.reset_vector), in place of the BIOS reset vector.
 * The original computes the stub's PS1 ROM address (p - 0x24bc20 +
 * 0xbfc00000) and then stores p, the EE address inside POPS's ROM copy;
 * *exit_vector is that p, as there (quirk 26).
 * Returns 1 with *exit_vector set when such a stub was found, 0 with
 * *exit_vector = 0 when not, -ERANGE when the core does not reach the ROM
 * copy. The stub bytes are rewritten exactly as the original's pokes. */
#define POPS_WARMBOOT_ROM_BASE  UINT32_C(0x0024bc20)
#define POPS_WARMBOOT_SCAN_TOP  UINT32_C(0x002cbb4c)
int pops_apply_reset_warmboot(void *staged_core, size_t core_size, uint32_t *exit_vector);

/* $LOAD_PADMAN / $KILL_PADMAN: POPStarter r13 after its IOP reset
 * (0x87aba8..0x87ac64). POPS starts its embedded padman_hsync (ELF image at
 * POPS_PADMAN_IRX_ADDR) with `jal 0x2001d8` at 0x200358; both commands make
 * that word 0 and the high half of the `bgezl` after it (0x200362) 0x1000,
 * so the error branch becomes an unconditional branch past it. The original
 * pokes without checking what is there. $LOAD_PADMAN additionally starts
 * the module from the core image itself, POPS_PADMAN_IRX_SIZE bytes (the
 * original's length, 11 bytes past the ELF's end), no arguments, fatal on
 * an ID <= 0. The start is skipped when a MODULE_n.IRX named "padman" was
 * read (gp+0x3824, POPS_MODULE_IRX_PADMAN below). Returns 0, -EINVAL,
 * -ERANGE. */
#define POPS_PADMAN_CALL_SITE  UINT32_C(0x00200358)
#define POPS_PADMAN_IRX_ADDR   UINT32_C(0x002cd560)
#define POPS_PADMAN_IRX_SIZE   UINT32_C(0x0000adf0)
int pops_apply_padman(void *staged_core, size_t core_size);

/* MODULE_0..9.IRX: POPStarter r13 reads each from the game device's POPS
 * folder before its IOP reset (0x8777c4..), ignores one under
 * POPS_MODULE_IRX_MIN_SIZE bytes, and checks the IOP module name at file
 * offset POPS_MODULE_IRX_NAME_AT (FUN_008d7024). The check is an else-if
 * chain of prefix compares (no terminator check), first match wins. A match
 * on a module POPS starts itself makes POPS's start a no-op with the same two
 * pokes as $KILL_PADMAN (call word 0, high half of the next word 0x1000).
 * Only the sio2man and padman flags are read again by the original; the rest
 * are set and never read, so they are not kept here. "IOX/File_Manager_Rpc"
 * can never match because "IOX/File_Manager" is checked first (quirk).
 *
 * pops_module_irx_name_apply: `irx`/`irx_size` is the readable buffer; bytes
 * past it read as 0 (the original reads past a small buffer into heap).
 * ORs POPS_MODULE_IRX_* into *flags. Returns 0, -EINVAL, -ERANGE.
 *
 * pops_module_irx_args: after the reset each module starts from its buffer
 * in slot order, fatal on an ID <= 0; a name beginning "hdd" gets
 * "-o 8 -n 128" (12 bytes), "pfs" gets "-m 8 -o 8 -n 127" (17 bytes), all
 * others none (only three bytes are compared). Returns the argument length,
 * *args set to the bytes or NULL. */
#define POPS_MODULE_IRX_SLOTS     10
#define POPS_MODULE_IRX_MIN_SIZE  17
#define POPS_MODULE_IRX_NAME_AT   0x8e
#define POPS_MODULE_IRX_NAME_MAX  20
#define POPS_MODULE_IRX_SIO2MAN   0x1u
#define POPS_MODULE_IRX_PADMAN    0x2u
int pops_module_irx_name_apply(void *staged_core, size_t core_size,
                               const void *irx, size_t irx_size, unsigned *flags);
int pops_module_irx_args(const void *irx, size_t irx_size, const char **args);

/* POPStarter r13's opcode pass (0x87c4a0), run before the IOP reset on every
 * launch unless $ORIGINAL_OPCODES (gp+0x38c4, checked at 0x87a64c). It walks
 * seven ranges of POPS (POPS_OPCODE_PASS_RANGES, inclusive ends) in steps of
 * 4, reading the 16-bit value at each address: a value 0x8c00..0x8fff or
 * 0xac00..0xafff (the upper half of lw / sw) gets 0xc00 added (lwr / swr);
 * otherwise a value 0x3c01..0x3c1f (lui rt, with rs 0) has the same test and
 * change applied to the 16 bits just before it (the lui's immediate: POPS's
 * recompiler builds lw/sw from such templates). The first range starts at
 * an odd halfword (0x200c62), the other six at word boundaries, as in the
 * original. Returns the number of halfwords changed, or -EINVAL / -ERANGE
 * when the core does not reach the last range. */
#define POPS_OPCODE_PASS_LAST UINT32_C(0x004f677f)
int pops_apply_opcode_pass(void *staged_core, size_t core_size);

/* pops_fix_context_init_video after built-in entry `builtin_id` (0: none)
 * was applied to the staged core: the entry's compatibility modes and core
 * writes are replayed over the expected site values, in the entry's order,
 * before initial_modes. Computed from the entry data, not from live bytes. */
int pops_fix_context_init_builtin(PopsFixContext *context, const void *staged_core,
                                  size_t core_size, uint16_t builtin_id,
                                  uint8_t initial_modes, uint8_t initial_video_mode);

/* Install exception hook at 0x00232d08 (FUN_008d6da4) */
int pops_apply_exception_hook(void *staged_core, size_t core_size);

/* Apply all settings from a PopsConfig structure to the staged core */
int pops_apply_all_config_patches(void *staged_core, size_t core_size, const PopsConfig *cfg);

#ifdef __cplusplus
}
#endif

#endif /* POPS_MODES_PATCHES_H */
