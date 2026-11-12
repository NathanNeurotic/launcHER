#ifndef LAUNCHER_POPS_BUILTIN_DB_H
#define LAUNCHER_POPS_BUILTIN_DB_H

/* POPStarter r13's built-in per-game list, carried as data generated from
 * the original by tools/gen_pops_builtin_db.py (docs/POPSTARTER_BUILTIN_DB.md).
 *
 * The original identifies the disc from 144 bytes of the VCD (sector 16
 * data 40..87 and 808..839, sector 22 data 56..119), compares them with its
 * stored fingerprints in program order, and applies the first match's entry.
 * `$VCDID_n` names an entry by hand and skips the scan. launcHER stores a
 * 64-bit FNV-1a hash of each fingerprint instead of the disc bytes.
 *
 * An entry is a list of operations in the original's order:
 *   CORE          write `len` bytes at `addr` in the POPS core
 *   EE            write `len` bytes at EE `addr` (the original installs game-fix
 *                 code at 0x01410000 and a breakpoint handler at 0x01460000)
 *   COMPAT        compatibility mode `arg` (1..7), the $COMPATIBILITY_0x code
 *   NOVMC1        memory card 1 off (the original's gp+0x38bc=2 helper)
 *   SUBCD         the original's gp+0x3458 flag: $SUBCDSTATUS's writes, and
 *                 compat modes 1/2/3/5 are skipped from then on
 *   NO_AUTO_PAL   the original's gp+0x4fa0=0: no automatic PAL for a
 *                 European disc
 *   FIX_CALL      call 0x01410000 from the resident chain before the cheats
 *                 (the original's jal at 0x2397d8)
 *   LIBCRYPT2_CODE 84 bytes of code the original keeps at 0x239780 (it falls
 *                 through at the end), run
 *                 after the controller-ID stores (the original's jump at
 *                 0x238d00); LIBCRYPT2_ON is that jump
 *   BREAK_CALL    POPS's exception path (0x232d08) calls 0x01460000
 *
 * $FAKELC sets the original's gp+0x3424, and 216 arms test it: while it is
 * set they jump over part of themselves, always one run of their
 * operations (lc_first/lc_count below). In 203 that is just the LibCrypt
 * write; 207..216 also lose their breakpoint handler and game-fix code;
 * 230 and 231 lose their game-fix code and 232 its sub-CD writes, flag and
 * game-fix code (those three write no LibCrypt code). The flag is only set
 * while the user's files are read, so it matters only for a $VCDID_n that
 * comes after a $FAKELC.
 * Not tested on a console. */

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define POPS_BUILTIN_MAX_ID 624
#define POPS_BUILTIN_SIG_SIZE 144
#define POPS_BUILTIN_FIX_ADDR UINT32_C(0x01410000)
#define POPS_BUILTIN_FIX_LIMIT UINT32_C(0x01420000)
#define POPS_BUILTIN_BREAK_ADDR UINT32_C(0x01460000)
#define POPS_BUILTIN_BREAK_LIMIT UINT32_C(0x01460200)
#define POPS_BUILTIN_LIBCRYPT2_SIZE 84

/* OR'd into an entry id given to pops_builtin_apply, pops_builtin_op_runs
 * or pops_fix_context_init_builtin: the entry runs as the original runs it
 * after a $FAKELC (gp+0x3424 set), without its lc_first/lc_count run. */
#define POPS_BUILTIN_AFTER_FAKELC 0x8000u
#define POPS_BUILTIN_ID(id) ((uint16_t)((id) & 0x7fffu))

enum {
  POPS_BUILTIN_OP_CORE = 0,
  POPS_BUILTIN_OP_EE,
  POPS_BUILTIN_OP_COMPAT,
  POPS_BUILTIN_OP_NOVMC1,
  POPS_BUILTIN_OP_SUBCD,
  POPS_BUILTIN_OP_NO_AUTO_PAL,
  POPS_BUILTIN_OP_FIX_CALL,
  POPS_BUILTIN_OP_LIBCRYPT2_CODE,
  POPS_BUILTIN_OP_LIBCRYPT2_ON,
  POPS_BUILTIN_OP_BREAK_CALL,
};

typedef struct {
  uint64_t hash;
  uint16_t id;
} PopsBuiltinSig;

typedef struct {
  uint16_t first; /* index into pops_builtin_ops */
  uint16_t count;
  /* The entry's own operations lc_first .. lc_first + lc_count - 1 are the
   * ones its arm jumps over while $FAKELC's flag is set; 0, 0: none. */
  uint8_t lc_first;
  uint8_t lc_count;
} PopsBuiltinEntry;

typedef struct {
  uint8_t kind;
  uint8_t arg;
  uint16_t len;
  uint32_t addr;
  uint32_t data; /* offset into pops_builtin_data */
} PopsBuiltinOp;

extern const uint16_t pops_builtin_sig_count;
extern const PopsBuiltinSig pops_builtin_sigs[];
extern const PopsBuiltinEntry pops_builtin_entries[POPS_BUILTIN_MAX_ID + 1];
extern const uint16_t pops_builtin_op_count;
extern const PopsBuiltinOp pops_builtin_ops[];
extern const uint32_t pops_builtin_data_size;
extern const uint8_t pops_builtin_data[];

/* What the entry asks of the launcher, collected while its core writes
 * are applied. */
typedef struct {
  uint16_t id;
  uint8_t compat_modes;   /* bit k-1: compatibility mode k */
  uint8_t subcd;          /* $SUBCDSTATUS writes; compat 1/2/3/5 after it skipped */
  uint8_t no_vmc1;
  uint8_t no_auto_pal;
  uint8_t fix_call;       /* resident chain calls POPS_BUILTIN_FIX_ADDR */
  uint8_t break_call;     /* exception path calls POPS_BUILTIN_BREAK_ADDR */
  uint8_t libcrypt2;      /* resident chain runs libcrypt2_code */
  uint8_t libcrypt2_code[POPS_BUILTIN_LIBCRYPT2_SIZE];
  uint32_t fix_size;      /* bytes installed at POPS_BUILTIN_FIX_ADDR */
  uint32_t break_size;    /* bytes installed at POPS_BUILTIN_BREAK_ADDR */
} PopsBuiltinPlan;

/* 64-bit FNV-1a of the fingerprint. */
uint64_t pops_builtin_hash(const uint8_t sig[POPS_BUILTIN_SIG_SIZE]);

/* First stored fingerprint equal to this one, in the original's order:
 * its id, or 0 for none. */
uint16_t pops_builtin_lookup(const uint8_t sig[POPS_BUILTIN_SIG_SIZE]);

/* Byte offsets of the three fingerprint parts inside a VCD whose data
 * sector n starts at image_offset + n * sector_size + data_offset
 * (lengths 0x30, 0x20, 0x40). */
void pops_builtin_sig_offsets(uint64_t image_offset, uint32_t sector_size,
                              uint32_t data_offset, uint64_t offsets[3]);

/* Apply entry `id` the way the original does for mode 3: core writes go to
 * the staged core (NULL: only the plan is filled), EE writes to `ee`, which
 * stands for EE addresses ee_base..ee_base+ee_size (NULL: sizes only), and
 * the rest into *plan. compat modes found
 * after a SUBCD op are dropped for k in 1,2,3,5, as FUN_008dc2c4 does.
 * `id` may carry POPS_BUILTIN_AFTER_FAKELC; plan->id is the entry alone.
 * Returns -ENOENT for an id with no entry, -ERANGE when a write does not
 * fit, 0 otherwise. */
int pops_builtin_apply(uint16_t id, void *staged_core, size_t core_size,
                       uint8_t *ee, uint32_t ee_base, size_t ee_size,
                       PopsBuiltinPlan *plan);

/* $BREAKPOINT0 / $BREAKPOINT1 (FUN_008d6da4 called with (0, 0) or (1, 1)):
 * the handler the original leaves at POPS_BUILTIN_BREAK_ADDR. Each call
 * copies the 292-byte template (the built-in entries' handler with its two
 * data words at 0x11c/0x120 still 0) and then stores over it:
 *   (0, 0): 0x000..0x01f run the scan only while PS1 RAM 0x1ffdf4 != 2,
 *           0x080 (the scan's end) branches to 0x120, where four words
 *           (0x120..0x12f, the last three past the 292 copied bytes) clear the gate's
 *           branch at 0x014 and return: one full scan, then never again;
 *   (1, 1): 0x000..0x01f run the scan only while the EE halfword at
 *           0x507002 is 0xdcfe
 *           (port 0 holding exactly SELECT+L2+R2+CIRCLE).
 * `breakpoint` is PopsConfig.breakpoint: the last command decides; the
 * words a $BREAKPOINT0 wrote past the copy stay when a $BREAKPOINT1 comes
 * after it, as in the original. Writes POPS_BREAKPOINT_SIZE bytes (or 292
 * when no $BREAKPOINT0 came) and returns that count, 0 when `breakpoint`
 * names none, -EINVAL/-ERANGE for bad arguments, -EILSEQ without a
 * template in the list. */
#define POPS_BREAKPOINT_TEMPLATE_SIZE 292
#define POPS_BREAKPOINT_SIZE 0x130
int pops_breakpoint_build(uint8_t breakpoint, uint8_t *out, size_t out_size);

/* The entry's operations in the original's order, all of them (a
 * POPS_BUILTIN_AFTER_FAKELC in `id` is ignored here: see
 * pops_builtin_op_runs); -ENOENT past the last id. */
int pops_builtin_entry_ops(uint16_t id, const PopsBuiltinOp **ops, unsigned *count);

/* 1 when operation n of the entry runs: always, except the entry's
 * lc_first/lc_count run when `id` carries POPS_BUILTIN_AFTER_FAKELC.
 * 0 for an id with no entry. */
int pops_builtin_op_runs(uint16_t id, unsigned n);

#ifdef __cplusplus
}
#endif

#endif
