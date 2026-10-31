#ifndef POPS_RESIDENT_H
#define POPS_RESIDENT_H

/* launcHER's own resident code for POPS.
 *
 * POPStarter keeps code in EE RAM while POPS runs and that is what its
 * cheat engine, pad and video commands need. This is an independent
 * implementation, not a copy: it is linked at a fixed address in the range
 * POPS leaves alone (the original uses the same range for its own code),
 * installed just before handoff, and reached through guarded hooks in POPS.
 *
 * The hook: POPS registers its VBLANK_START handler (0x0021cd68) with
 * AddIntcHandler at 0x0021b190, loading the address with
 * lui $a1,0x22 / addiu $a1,$a1,-0x3298 at 0x0021b184 and 0x0021b18c. Those
 * two words are pointed at pops_resident_vblank instead, which does its work
 * and then calls POPS's handler, so POPS behaves as before. The separate
 * display hook replaces the load at 0x21a094 and rejoins at 0x21a098. */

#include <stddef.h>
#include <stdint.h>
#include "pops_config.h"

#ifdef __cplusplus
extern "C" {
#endif

#define POPS_RESIDENT_BASE        UINT32_C(0x0143a000)
#define POPS_RESIDENT_LIMIT       UINT32_C(0x01460000)
#define POPS_RESIDENT_MAGIC       UINT32_C(0x5352484c) /* "LHRS" */
#define POPS_RESIDENT_VERSION     2

/* POPS's VBLANK_START registration and handler (verified on the pinned core) */
#define POPS_VBLANK_LUI_ADDR      UINT32_C(0x0021b184)
#define POPS_VBLANK_ADDIU_ADDR    UINT32_C(0x0021b18c)
#define POPS_VBLANK_LUI_PRISTINE  UINT32_C(0x3c050022) /* lui   $a1, 0x22 */
#define POPS_VBLANK_ADDIU_PRISTINE UINT32_C(0x24a5cd68) /* addiu $a1, $a1, -0x3298 */
#define POPS_VBLANK_HANDLER       UINT32_C(0x0021cd68)

/* POPS stores its PS1 RAM base (0x40000000, TLB-mapped) at 0x0021af98:
 * sw $s2, 0x2274($s0) with $s0 = 0x700010f0. Reading it at run time keeps
 * the resident code independent of how POPS maps that RAM. */
#define POPS_PS1_RAM_BASE_PTR     UINT32_C(0x70003364)
#define POPS_PS1_RAM_SIZE         UINT32_C(0x00200000)

/* Header at POPS_RESIDENT_BASE, first bytes of the resident image. */
typedef struct {
  uint32_t magic;
  uint16_t version;
  uint16_t header_size;
  uint32_t file_size;    /* bytes present in the image */
  uint32_t image_size;   /* bytes the resident occupies, including zeroed data */
  uint32_t vblank_entry; /* address of pops_resident_vblank */
  uint32_t config_addr;  /* address of the PopsResidentConfig */
  uint32_t display_entry; /* mid-function GS DISPLAY hook; no C call ABI */
} PopsResidentHeader;

#define POPS_RES_F_CHEATS         (1u << 0)
#define POPS_RES_F_DISPLAY        (1u << 1)

typedef struct {
  uint64_t gs_display;   /* offset zero, read by the stackless display entry */
  uint32_t flags;        /* POPS_RES_F_* */
  uint32_t pops_vblank;  /* POPS's own VBLANK_START handler, always called */
  uint32_t ram_base_ptr; /* where POPS keeps its PS1 RAM base */
  uint32_t frame;        /* VBLANK_START count */
  uint16_t safe_delay;   /* $SAFEMODE: frames before cheats start */
  uint16_t cheat_count;
  PopsCheatEntry cheats[POPS_MAX_CHEATS];
} PopsResidentConfig;

/* One pass over the codes against PS1 RAM (ram = base of 2 MiB).
 * $80 16-bit write, $30 8-bit write, $10/$20 kept as writes like before,
 * $D0..$D3 16-bit and $E0/$E1 8-bit conditionals that run the next code
 * only when true. Codes outside PS1 RAM are skipped. */
void pops_resident_cheat_pass(uint8_t *ram, const PopsCheatEntry *cheats, uint16_t count);

/* Per-frame work, separate from the interrupt entry so host tests can run it.
 * Returns 1 when the codes ran this frame. */
int pops_resident_frame(PopsResidentConfig *cfg, uint8_t *ram);

/* Launcher side (pops_resident.c) */

/* Validate an embedded resident image for the fixed base. */
int pops_resident_check_image(const void *image, size_t image_len, PopsResidentHeader *out);

/* Fill a resident configuration from the parsed POPS configuration.
 * Returns 1 when the resident has work to do, 0 when it is not needed. */
int pops_resident_build_config(PopsResidentConfig *out, const PopsConfig *cfg);

/* Point POPS's VBLANK_START registration at the resident entry. All or
 * nothing: both words are checked before either is written. */
int pops_resident_hook_core(void *staged_core, size_t core_size, uint32_t entry);

/* Manual DISPLAY override at 0x21a094. Guard the displaced load, delay slot
 * and both interlace argument sites before writing the hook. The image
 * entry sets a1 to gs_display, restores v0=0x12000000, then jumps to 0x21a098. */
int pops_resident_hook_display(void *staged_core, size_t core_size, uint32_t entry);

/* Copy the image to dest (the resident base on the console), zero its data,
 * and write the configuration. dest_addr is the address dest stands for. */
int pops_resident_install(void *dest, size_t dest_len, uint32_t dest_addr,
                          const void *image, size_t image_len,
                          const PopsResidentConfig *rcfg);

#ifdef __cplusplus
}
#endif

#endif
