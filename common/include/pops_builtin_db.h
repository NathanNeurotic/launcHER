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
 * Returns -ENOENT for an id with no entry, -ERANGE when a write does not
 * fit, 0 otherwise. */
int pops_builtin_apply(uint16_t id, void *staged_core, size_t core_size,
                       uint8_t *ee, uint32_t ee_base, size_t ee_size,
                       PopsBuiltinPlan *plan);

/* The entry's operations in the original's order; -ENOENT past the last id. */
int pops_builtin_entry_ops(uint16_t id, const PopsBuiltinOp **ops, unsigned *count);

#ifdef __cplusplus
}
#endif

#endif
