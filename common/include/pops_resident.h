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
 * display hook replaces the load at 0x21a094 and rejoins at 0x21a098.
 * Progressive mode selects a context-preserving bridge at the same site. */

#include <stddef.h>
#include <stdint.h>
#include "pops_config.h"

#ifdef __cplusplus
extern "C" {
#endif

#define POPS_RESIDENT_BASE        UINT32_C(0x0143a000)
#define POPS_RESIDENT_LIMIT       UINT32_C(0x01460000)
#define POPS_RESIDENT_MAGIC       UINT32_C(0x5352484c) /* "LHRS" */
#define POPS_RESIDENT_VERSION     5

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
  uint32_t progressive_entry; /* context-preserving progressive DISPLAY bridge */
  uint32_t pad_read_entry; /* $D2LS: start of POPS's pad read, no C call ABI */
  uint32_t pad_read_exit;  /* $D2LS: return of POPS's pad read, no C call ABI */
  uint32_t gte_scale_entry;  /* widescreen: MAC1 store at 0x2089a8, scale then divide */
  uint32_t gte_divide_entry; /* $EYEFINITY: same site, divide only */
  uint32_t gte_ultra_entry;  /* $ULTRA_WIDESCREEN: IR1 store at 0x208a2c */
} PopsResidentHeader;

#define POPS_RES_F_CHEATS         (1u << 0)
#define POPS_RES_F_DISPLAY        (1u << 1)
#define POPS_RES_F_PROGRESSIVE    (1u << 2)
#define POPS_RES_F_PAD_ID         (1u << 3)
#define POPS_RES_F_D2LS           (1u << 4)
#define POPS_RES_F_WIDESCREEN     (1u << 5)

/* Widescreen: POPS's GTE perspective transform (RTPS/RTPT, loop at
 * 0x00208900) stores MAC1 at 0x002089a8 (sw $t0,0x64($a0)) and IR1 at
 * 0x00208a2c (sw $t0,0x24($a0)); $t0 then feeds the screen X projection.
 * The resident stubs scale $t0 (x * 75 / gte_divisor, or x / gte_divisor)
 * at those stores. $v0/$v1 and LO/HI are dead there and are the only
 * clobbers. */
#define POPS_GTE_MAC1_STORE_ADDR  UINT32_C(0x002089a8)
#define POPS_GTE_MAC1_RESUME_ADDR UINT32_C(0x002089b0)
#define POPS_GTE_IR1_STORE_ADDR   UINT32_C(0x00208a2c)
#define POPS_GTE_IR1_RESUME_ADDR  UINT32_C(0x00208a34)
#define POPS_RESIDENT_GTE_DIVISOR_OFFSET 31

/* POPS keeps one 0x90-byte state block per controller port at 0x00507000.
 * The word at +0x34 is the controller ID its SIO emulation answers the
 * game with (0x0020c648/0x0020c64c/0x0020c6c8 on the pinned core); POPS
 * rewrites it when the real pad changes mode. Bytes +0..+19 receive the
 * raw pad data from its pad read at 0x00237798 (a2 = the state block). */
#define POPS_PAD_STATE_ADDR       UINT32_C(0x00507000)
#define POPS_PAD_STATE_STRIDE     0x90u
#define POPS_PAD_STATE_ID         0x34u

/* Pad read hook sites: the second instruction (addiu $v1,$zero,0x70, after
 * move $a3,$a0) and the final jr $ra (delay slot addiu $sp,$sp,0x30). */
#define POPS_PAD_READ_ENTRY_ADDR  UINT32_C(0x0023779c)
#define POPS_PAD_READ_RESUME_ADDR UINT32_C(0x002377a4)
#define POPS_PAD_READ_EXIT_ADDR   UINT32_C(0x0023780c)

typedef struct {
  uint64_t gs_display;   /* offset zero, read by the stackless display entry */
  uint32_t flags;        /* POPS_RES_F_* */
  uint32_t pops_vblank;  /* POPS's own VBLANK_START handler, always called */
  uint32_t ram_base_ptr; /* where POPS keeps its PS1 RAM base */
  uint32_t frame;        /* VBLANK_START count */
  uint16_t safe_delay;   /* $SAFEMODE: frames before cheats start */
  uint16_t cheat_count;
  uint8_t pad_override;  /* bit n: port n reports pad_id[n] */
  uint8_t pad_id[2];
  uint8_t gte_divisor;   /* widescreen: 100, or 4 for $EYEFINITY */
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

/* Force the controller IDs selected by pad_override. state is the first of
 * the two per-port blocks (POPS_PAD_STATE_ADDR on the console). */
void pops_resident_pad_ids(const PopsResidentConfig *cfg, uint8_t *state);

/* $D2LS: swap the D-pad and the left stick in one raw pad reading of
 * `bytes` bytes. The stick drives the D-pad buttons (pressed beyond a
 * quarter of its travel) and their pressure bytes; the D-pad pressures
 * drive the stick. Readings without stick data (digital mode) are left
 * alone, and without pressure data the stick reads centred. */
void pops_resident_d2ls(uint8_t *pad, uint32_t bytes);

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

/* $480p static setup after region/fix staging. All five sites are checked
 * before writes. interlace is li a0,0/1 or andi a0,s1,1. Unknown or conflicting
 * payload changes reject; the caller must discard that staged launch. */
int pops_resident_hook_progressive(void *staged_core, size_t core_size,
                                    uint32_t entry, uint32_t interlace);
uint32_t pops_resident_progressive_interlace(const PopsConfig *cfg);

/* Pad commands. Checks the pad state references for any pad command, and
 * for $D2LS points the pad read's entry and exit at the resident stubs.
 * All sites are checked before either word is written. */
int pops_resident_hook_pads(void *staged_core, size_t core_size, uint32_t flags,
                            uint32_t read_entry, uint32_t read_exit);

/* Widescreen family (POPS_WIDESCREEN_*). Points the MAC1 store at the scale
 * or divide entry and, for ULTRA only, the IR1 store at the ultra entry;
 * the other modes restore the IR1 store, like the original. All sites are
 * checked before any write. NONE checks and writes nothing. */
int pops_resident_hook_widescreen(void *staged_core, size_t core_size, uint8_t mode,
                                  const PopsResidentHeader *hdr);

/* Copy the image to dest (the resident base on the console), zero its data,
 * and write the configuration. dest_addr is the address dest stands for. */
int pops_resident_install(void *dest, size_t dest_len, uint32_t dest_addr,
                          const void *image, size_t image_len,
                          const PopsResidentConfig *rcfg);

#ifdef __cplusplus
}
#endif

#endif
