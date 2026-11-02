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
 *
 * Controller IDs, $SET_TIMINGS and cheats run where POPStarter runs them:
 * from the nop at 0x0021a63c in POPS's GP1 write path, which POPStarter
 * turns into a jal to its own code (see pops_resident_hook_gp1). The
 * launcher no longer hooks VBLANK_START; the entry and hook_core remain.
 * Progressive mode selects a context-preserving bridge at the same site.
 *
 * POPStarter installs its resident code and that GP1 hook on every launch
 * (the in-game reset and the built-in list's chain calls live there), plus
 * nine guards around misaligned loads and stores (pops_resident_guards.S,
 * pops_resident_hook_guards), so launcHER installs its image, the GP1 hook
 * and the guards on every POPStarter-mode launch too. */

#include <stddef.h>
#include <stdint.h>
#include "pops_config.h"

#ifdef __cplusplus
extern "C" {
#endif

#define POPS_RESIDENT_BASE        UINT32_C(0x0143a000)
#define POPS_RESIDENT_LIMIT       UINT32_C(0x01460000)
#define POPS_RESIDENT_MAGIC       UINT32_C(0x5352484c) /* "LHRS" */
#define POPS_RESIDENT_VERSION     12

/* POPStarter's always-on guards (pops_resident_guards.S): the POPS words
 * that become "j stub", in the order the original writes them
 * (0x874864..0x874998). POPS_GUARD_204160 is the redirected branch; its
 * stub is the tail of POPS_GUARD_204178's. */
enum {
  POPS_GUARD_21C58C = 0,
  POPS_GUARD_21C768,
  POPS_GUARD_2082A0,
  POPS_GUARD_204AE0,
  POPS_GUARD_204178,
  POPS_GUARD_204160,
  POPS_GUARD_202250,
  POPS_GUARD_21C5DC,
  POPS_GUARD_21C5A8,
  POPS_GUARD_COUNT
};

/* POPS's VBLANK_START registration and handler (verified on the pinned core) */
#define POPS_VBLANK_LUI_ADDR      UINT32_C(0x0021b184)
#define POPS_VBLANK_ADDIU_ADDR    UINT32_C(0x0021b18c)
#define POPS_VBLANK_LUI_PRISTINE  UINT32_C(0x3c050022) /* lui   $a1, 0x22 */
#define POPS_VBLANK_ADDIU_PRISTINE UINT32_C(0x24a5cd68) /* addiu $a1, $a1, -0x3298 */
#define POPS_VBLANK_HANDLER       UINT32_C(0x0021cd68)

/* POPS's GP1 write path (0x0021a568, called by the GPU register handler at
 * 0x0020b4d8 for writes to 0x1f801814). With interrupts enabled it reaches
 * lui $v1,1 / nop / di; POPStarter r13 replaces that nop with
 * "jal 0x239490" (its pad checks, $SET_TIMINGS and cheat code), and so does
 * launcHER with a jal to its own entry. */
#define POPS_GP1_HOOK_ADDR        UINT32_C(0x0021a63c)
#define POPS_GP1_HOOK_PRISTINE    UINT32_C(0x00000000) /* nop */

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
  uint32_t gp1_entry;        /* cheats/$SET_TIMINGS: jal'd from 0x21a63c */
  uint32_t guard_entry[POPS_GUARD_COUNT]; /* always-on guards, no C call ABI */
} PopsResidentHeader;

#define POPS_RES_F_CHEATS         (1u << 0)
#define POPS_RES_F_DISPLAY        (1u << 1)
#define POPS_RES_F_PROGRESSIVE    (1u << 2)
#define POPS_RES_F_PAD_ID         (1u << 3)
#define POPS_RES_F_D2LS           (1u << 4)
#define POPS_RES_F_WIDESCREEN     (1u << 5)
#define POPS_RES_F_TIMINGS        (1u << 6)
#define POPS_RES_F_TIMINGS_SAVE   (1u << 7)
/* The built-in per-game list's resident work (pops_builtin_db.h), in the
 * original's chain order: breakpoint handler (its slot 0x232d08, after the
 * controller IDs), second LibCrypt code (slot 0x238d00, after $SET_TIMINGS),
 * game-fix code (slot 0x2397d8, just before the cheats). */
#define POPS_RES_F_BREAK_CALL     (1u << 8)  /* call POPS_BUILTIN_BREAK_ADDR */
#define POPS_RES_F_LIBCRYPT2      (1u << 9)  /* run libcrypt2_code */
#define POPS_RES_F_FIX_CALL       (1u << 10) /* call POPS_BUILTIN_FIX_ADDR */
#define POPS_RESIDENT_LIBCRYPT2_WORDS 23     /* 84 bytes of code, jr ra, nop */

/* $SET_TIMINGS: three POPS timing words, adjusted live with L1/L2/R1/R2.
 * The original keeps a copy of them at offset 0x800 of the slot 0 VMC
 * image POPS holds in RAM (signature "01->" then the three words) and
 * restores it once that image is loaded (its first word turns nonzero).
 * The launcher sets POPS_RES_F_TIMINGS_SAVE with it, so launcHER keeps that
 * copy the same way; without the flag the card copy is only read. */
#define POPS_TIMING_A_ADDR        UINT32_C(0x00502770) /* pad 2: +-1, R +-0x10 */
#define POPS_TIMING_B_OFFSET      0x33e0u /* scratchpad; pad 1 L1/L2 */
#define POPS_TIMING_C_OFFSET      0x33e4u /* scratchpad; pad 1 R1/R2 */
#define POPS_SCRATCHPAD_ADDR      UINT32_C(0x70000000)
#define POPS_VMC0_IMAGE_ADDR      UINT32_C(0x00507930)
#define POPS_TIMING_SAVE_ADDR     (POPS_VMC0_IMAGE_ADDR + 0x800u)
#define POPS_TIMING_SIGNATURE     UINT32_C(0x3e2d3130) /* "01->" */
/* Pad halfwords (active low) that adjust: exactly one button held. */
#define POPS_TIMING_PAD_L1        0xfbffu
#define POPS_TIMING_PAD_L2        0xfeffu
#define POPS_TIMING_PAD_R1        0xf7ffu
#define POPS_TIMING_PAD_R2        0xfdffu

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

/* Compiled cheat codes the resident holds (see pops_cheats_compile). */
#define POPS_CHEAT_COMPILED_MAX (2u * POPS_MAX_CHEATS + 4u)

typedef struct {
  uint64_t gs_display;   /* offset zero, read by the stackless display entry */
  uint32_t flags;        /* POPS_RES_F_* */
  uint32_t pops_vblank;  /* POPS's own VBLANK_START handler, always called */
  uint32_t ram_base_ptr; /* where POPS keeps its PS1 RAM base */
  uint32_t frame;        /* times the GP1 hook ran */
  uint16_t safe_mode;    /* POPS_SAFE_MODE_* cheat gate */
  uint16_t cheat_count;
  uint8_t pad_override;  /* bit n: port n reports pad_id[n] */
  uint8_t pad_id[2];
  uint8_t gte_divisor;   /* widescreen: 100, or 4 for $EYEFINITY */
  PopsCheatEntry cheats[POPS_CHEAT_COMPILED_MAX];
  uint8_t timings_ready; /* $SET_TIMINGS: VMC image seen, adjusting */
  uint8_t reserved[3];
  /* POPS_RES_F_LIBCRYPT2: the entry's 84 bytes of code (it falls through
   * in the original) followed by jr ra, nop; run in place. */
  uint32_t libcrypt2_code[POPS_RESIDENT_LIBCRYPT2_WORDS];
  /* The in-game reset: POPStarter's resident block (0x232ce8..0x232d08,
   * always live) stores this word to the EE scratchpad word 0 while the
   * port 0 buttons read exactly POPS_RESET_COMBO. The BIOS reset vector as
   * shipped; $RESET_WARMBOOT points it at the SystemErrorExit stub. */
  uint32_t reset_vector;
} PopsResidentConfig;

/* Port 0 buttons (active low) for the reset: SELECT + L2 + R2 + CROSS and
 * nothing else, the original's `lh 0x507002 == 0xbcfe`. */
#define POPS_RESET_COMBO          0xbcfeu
#define POPS_RESET_VECTOR_DEFAULT UINT32_C(0xbfc00000)

/* Where the codes write. ps1 is PS1 RAM (2 MiB); ee is EE address 0 and
 * ee_size how much of EE RAM PS2-format codes may touch (0: none); spr is
 * the EE scratchpad (16 KiB) and ps1spr POPS's PS1 scratchpad mapping
 * (1 KiB), 0 for none. On the console: POPS's PS1 RAM base, 0, 32 MiB,
 * POPS_CHEAT_SPR_ADDR and POPS_CHEAT_PS1SPR_ADDR. */
typedef struct {
  uintptr_t ps1;
  uintptr_t ee;
  uint32_t ee_size;
  uintptr_t spr;
  uintptr_t ps1spr;
} PopsCheatMemory;

/* One pass over the codes. PS1 codes: $80 16-bit write, $30 8-bit write,
 * $10/$20 writes, $D0..$D3 16-bit and $E0/$E1 8-bit conditionals that skip
 * the next `skip` (or 1) codes when false, $C0 master code that ends the
 * pass when false, $50 repeat of the next write. PS2-format codes
 * (POPS_CHEAT_EE/SPR/PS1SPR): writes, and conditionals that skip the next
 * code when false. Compiled codes (LOAD16, BNE, W32) use the k0/k1 model
 * described at pops_cheats_compile. Codes outside their memory are skipped
 * (POPStarter would fault there); misaligned ones are aligned down. */
void pops_resident_cheat_run(const PopsCheatMemory *mem, const PopsCheatEntry *cheats,
                             uint16_t count);

/* pops_resident_cheat_run with PS1 RAM only (ram = base of 2 MiB). */
void pops_resident_cheat_pass(uint8_t *ram, const PopsCheatEntry *cheats, uint16_t count);

/* Order the codes the way POPStarter r13 compiles them: the first $C0 moves
 * to the front and gates every code, later $C0s are dropped, a $50 applies
 * to the next PS1 write, a $D0 becomes a LOAD16 plus a BNE in front of the
 * next PS1 write ($0/$1/$2 writes in between run unconditionally and
 * change the compare; $S/$T writes there are dropped), PS2 conditionals
 * skip the next code and switch the rest of the file to POPStarter's reduced
 * loop (writes only; $S drops $T writes, $=/$! drop $S writes). out must hold POPS_CHEAT_COMPILED_MAX codes
 * (2 * count + 4); returns how many were written, 0 when it is too small. */
uint16_t pops_cheats_compile(const PopsCheatEntry *in, uint16_t count, PopsCheatEntry *out,
                             uint16_t capacity);

/* 1 when the selected gate holds, so the cheat pass is skipped this time. */
int pops_safe_mode_blocks(const uint8_t *ps1_ram, uint8_t safe_mode);

/* The cheat work done each time the GP1 hook runs, separate from the entry
 * so host tests can run it. Returns 1 when the codes ran this time. */
int pops_resident_frame(PopsResidentConfig *cfg, uint8_t *ram);

/* The same with every memory PS2-format codes can reach. */
int pops_resident_frame_mem(PopsResidentConfig *cfg, const PopsCheatMemory *mem);

/* Force the controller IDs selected by pad_override. state is the first of
 * the two per-port blocks (POPS_PAD_STATE_ADDR on the console). */
void pops_resident_pad_ids(const PopsResidentConfig *cfg, uint8_t *state);

/* $D2LS: swap the D-pad and the left stick in one raw pad reading of
 * `bytes` bytes. The stick drives the D-pad buttons (pressed beyond a
 * quarter of its travel) and their pressure bytes; the D-pad pressures
 * drive the stick. Readings without stick data (digital mode) are left
 * alone, and without pressure data the stick reads centred. */
void pops_resident_d2ls(uint8_t *pad, uint32_t bytes);

/* $SET_TIMINGS, once per frame. ee is where EE address 0 is mapped and spr
 * where the scratchpad is (0 and POPS_SCRATCHPAD_ADDR on the console).
 * Until the slot 0 VMC image is loaded it waits; on the frame it appears,
 * a saved copy is restored (or, with POPS_RES_F_TIMINGS_SAVE, a new one is
 * written). On later frames pad 1 alone holding L1/L2 adds 1/-1 to timing
 * B and R1/R2 to timing C; otherwise pad 2 alone holding L1/L2 adds 1/-1
 * and R1/R2 0x10/-0x10 to timing A. With POPS_RES_F_TIMINGS_SAVE each new
 * value is also copied to the VMC image. */
void pops_resident_timings(PopsResidentConfig *cfg, uintptr_t ee, uintptr_t spr);

/* Launcher side (pops_resident.c) */

/* Validate an embedded resident image for the fixed base. */
int pops_resident_check_image(const void *image, size_t image_len, PopsResidentHeader *out);

/* Fill a resident configuration from the parsed POPS configuration.
 * Returns 1 when the resident has work to do, 0 when it is not needed. */
int pops_resident_build_config(PopsResidentConfig *out, const PopsConfig *cfg);

/* Point POPS's VBLANK_START registration at the resident entry. All or
 * nothing: both words are checked before either is written. */
int pops_resident_hook_core(void *staged_core, size_t core_size, uint32_t entry);

/* Write "jal entry" over the nop at POPS_GP1_HOOK_ADDR, after checking the
 * words around it (lui $v1,1 before, di / sync.p / mfc0 Status after, and
 * the and/bnez that read $v1). Idempotent; anything else is -EILSEQ. */
int pops_resident_hook_gp1(void *staged_core, size_t core_size, uint32_t entry);

/* POPStarter's always-on guards: point the nine POPS_GUARD_* sites at the
 * image's stubs, "j stub" plus a nop over the word after it (at 0x204160
 * only the branch changes; its delay slot stays). Every site, the word
 * after it and the words the stubs return to or repeat are checked before
 * any is written. Idempotent; anything else is -EILSEQ. */
int pops_resident_hook_guards(void *staged_core, size_t core_size,
                              const PopsResidentHeader *hdr);

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
