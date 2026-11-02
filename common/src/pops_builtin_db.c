/* POPStarter r13's built-in per-game list: lookup and entry application.
 * The data (common/src/pops_builtin_db_data.c) is generated from the
 * original by tools/gen_pops_builtin_db.py; see docs/POPSTARTER_BUILTIN_DB.md
 * and pops_builtin_db.h. Not tested on a console. */
#include <errno.h>
#include <string.h>
#include "pops_builtin_db.h"
#include "pops_config.h"
#include "pops_modes_patches.h"

#define CORE_BASE UINT32_C(0x00200000)

uint64_t pops_builtin_hash(const uint8_t sig[POPS_BUILTIN_SIG_SIZE]) {
  uint64_t h = UINT64_C(0xcbf29ce484222325);
  for (unsigned i = 0; i < POPS_BUILTIN_SIG_SIZE; ++i) {
    h ^= sig[i];
    h *= UINT64_C(0x100000001b3);
  }
  return h;
}

uint16_t pops_builtin_lookup(const uint8_t sig[POPS_BUILTIN_SIG_SIZE]) {
  if (!sig)
    return 0;
  uint64_t h = pops_builtin_hash(sig);
  /* Program order, first match wins, as FUN_008ff0e4 compares them. */
  for (unsigned i = 0; i < pops_builtin_sig_count; ++i)
    if (pops_builtin_sigs[i].hash == h)
      return pops_builtin_sigs[i].id;
  return 0;
}

void pops_builtin_sig_offsets(uint64_t image_offset, uint32_t sector_size,
                              uint32_t data_offset, uint64_t offsets[3]) {
  /* The original reads VCD offsets 0x109340, 0x109640 and 0x10ca70 of a
   * raw image behind its 1 MiB header: sector 16 data 40 and 808, sector
   * 22 data 56. */
  uint64_t s16 = image_offset + 16u * (uint64_t)sector_size + data_offset;
  uint64_t s22 = image_offset + 22u * (uint64_t)sector_size + data_offset;
  offsets[0] = s16 + 40;
  offsets[1] = s16 + 808;
  offsets[2] = s22 + 56;
}

int pops_builtin_entry_ops(uint16_t id, const PopsBuiltinOp **ops, unsigned *count) {
  id = POPS_BUILTIN_ID(id);
  if (id > POPS_BUILTIN_MAX_ID)
    return -ENOENT;
  const PopsBuiltinEntry *e = &pops_builtin_entries[id];
  if ((unsigned)e->first + e->count > pops_builtin_op_count ||
      (unsigned)e->lc_first + e->lc_count > e->count)
    return -EILSEQ;
  *ops = &pops_builtin_ops[e->first];
  *count = e->count;
  return 0;
}

int pops_builtin_op_runs(uint16_t id, unsigned n) {
  uint16_t entry = POPS_BUILTIN_ID(id);
  if (entry > POPS_BUILTIN_MAX_ID)
    return 0;
  if (!(id & POPS_BUILTIN_AFTER_FAKELC))
    return 1;
  const PopsBuiltinEntry *e = &pops_builtin_entries[entry];
  /* The arm's bnez on gp+0x3424 jumps over exactly this run. */
  return n < e->lc_first || n >= (unsigned)e->lc_first + e->lc_count;
}

static int fits(uint64_t addr, uint32_t len, uint64_t base, uint64_t size) {
  return addr >= base && addr - base <= size && len <= size - (addr - base);
}

int pops_builtin_apply(uint16_t id, void *staged_core, size_t core_size,
                       uint8_t *ee, uint32_t ee_base, size_t ee_size,
                       PopsBuiltinPlan *plan) {
  const PopsBuiltinOp *ops;
  unsigned count;
  int result = pops_builtin_entry_ops(id, &ops, &count);
  if (result)
    return result;
  if (!plan)
    return -EINVAL;
  memset(plan, 0, sizeof(*plan));
  plan->id = POPS_BUILTIN_ID(id);
  /* Bounds first, so a rejected entry changes nothing. */
  for (unsigned i = 0; i < count; ++i) {
    const PopsBuiltinOp *op = &ops[i];
    if ((uint64_t)op->data + op->len > pops_builtin_data_size)
      return -EILSEQ;
    if (op->kind == POPS_BUILTIN_OP_CORE && staged_core &&
        !fits(op->addr, op->len, CORE_BASE, core_size))
      return -ERANGE;
    /* ee_size, not ee: on the console the EE buffer is address 0. */
    if (op->kind == POPS_BUILTIN_OP_EE && ee_size &&
        !fits(op->addr, op->len, ee_base, ee_size))
      return -ERANGE;
    if (op->kind == POPS_BUILTIN_OP_LIBCRYPT2_CODE && op->len != POPS_BUILTIN_LIBCRYPT2_SIZE)
      return -EILSEQ;
    if (op->kind == POPS_BUILTIN_OP_COMPAT && (op->arg < 1 || op->arg > 7))
      return -EILSEQ;
    if (op->kind > POPS_BUILTIN_OP_BREAK_CALL)
      return -EILSEQ;
  }
  for (unsigned i = 0; i < count; ++i) {
    const PopsBuiltinOp *op = &ops[i];
    const uint8_t *src = pops_builtin_data + op->data;
    if (!pops_builtin_op_runs(id, i))
      continue; /* skipped after a $FAKELC */
    switch (op->kind) {
    case POPS_BUILTIN_OP_CORE:
      if (staged_core)
        memcpy((uint8_t *)staged_core + (op->addr - CORE_BASE), src, op->len);
      break;
    case POPS_BUILTIN_OP_EE:
      if (ee_size)
        memcpy(ee + (op->addr - ee_base), src, op->len);
      if (op->addr == POPS_BUILTIN_FIX_ADDR)
        plan->fix_size = op->len;
      else if (op->addr == POPS_BUILTIN_BREAK_ADDR)
        plan->break_size = op->len;
      break;
    case POPS_BUILTIN_OP_COMPAT:
      /* FUN_008dc2c4: modes 1, 2, 3 and 5 do nothing once gp+0x3458 is set. */
      if (plan->subcd && (op->arg == 1 || op->arg == 2 || op->arg == 3 || op->arg == 5))
        break;
      plan->compat_modes |= (uint8_t)(1u << (op->arg - 1));
      if (staged_core) {
        result = pops_compat_mode_write(staged_core, core_size, op->arg);
        if (result)
          return result;
      }
      break;
    case POPS_BUILTIN_OP_NOVMC1:
      plan->no_vmc1 = 1;
      break;
    case POPS_BUILTIN_OP_SUBCD:
      plan->subcd = 1;
      break;
    case POPS_BUILTIN_OP_NO_AUTO_PAL:
      plan->no_auto_pal = 1;
      break;
    case POPS_BUILTIN_OP_FIX_CALL:
      plan->fix_call = 1;
      break;
    case POPS_BUILTIN_OP_LIBCRYPT2_CODE:
      memcpy(plan->libcrypt2_code, src, POPS_BUILTIN_LIBCRYPT2_SIZE);
      break;
    case POPS_BUILTIN_OP_LIBCRYPT2_ON:
      plan->libcrypt2 = 1;
      break;
    case POPS_BUILTIN_OP_BREAK_CALL:
      plan->break_call = 1;
      break;
    }
  }
  if ((plan->fix_call && !plan->fix_size) || (plan->break_call && !plan->break_size) ||
      (plan->libcrypt2 && !plan->libcrypt2_code[0] && !plan->libcrypt2_code[1]))
    return -EILSEQ;
  return 0;
}

/* A 128-bit store as the original's 0x8d8cb8 (sq) makes it, given the four
 * words in address order. */
static void put_words(uint8_t *out, uint32_t at, const uint32_t *words, unsigned count) {
  for (unsigned i = 0; i < count; ++i) {
    uint32_t w = words[i];
    out[at + 4 * i] = (uint8_t)w;
    out[at + 4 * i + 1] = (uint8_t)(w >> 8);
    out[at + 4 * i + 2] = (uint8_t)(w >> 16);
    out[at + 4 * i + 3] = (uint8_t)(w >> 24);
  }
}

int pops_breakpoint_build(uint8_t breakpoint, uint8_t *out, size_t out_size) {
  /* FUN_008d6da4(0, 0): 0x8d6e00..0x8d6ea0. */
  static const uint32_t bp0_head[8] = {
    0x3c1a0120, /* lui  k0, 0x120 */
    0x8f5afdf4, /* lw   k0, -0x20c(k0)   PS1 RAM 0x1ffdf4 */
    0x3c1b0000, /* lui  k1, 0 */
    0x377b0002, /* ori  k1, k1, 2 */
    0x00000000, /* nop */
    0x175b0002, /* bne  k0, k1, 0x020    scan */
    0x00000000, /* nop */
    0x03e00008, /* jr   ra */
  };
  static const uint32_t bp0_end = 0x10000027; /* at 0x080: b 0x120 */
  static const uint32_t bp0_tail[4] = {
    0x3c1a0146, /* lui  k0, 0x146 */
    0xaf400014, /* sw   zero, 0x14(k0)   clears the bne at 0x014 */
    0x03e00008, /* jr   ra */
    0x00000000, /* nop */
  };
  /* FUN_008d6da4(1, 1): 0x8d6ecc..0x8d6f14 (the second store is por zero). */
  static const uint32_t bp1_head[8] = {
    0x3c1a0050, /* lui  k0, 0x50 */
    0x875a7002, /* lh   k0, 0x7002(k0)   EE 0x507002 */
    0x241bdcfe, /* li   k1, -0x2302 */
    0x175b001c, /* bne  k0, k1, 0x080    return */
    0, 0, 0, 0,
  };
  const PopsBuiltinOp *ops = NULL;
  unsigned count = 0;
  int last0 = breakpoint & POPS_BREAKPOINT_0;
  int last1 = breakpoint & POPS_BREAKPOINT_1;
  if (!last0 && !last1)
    return 0;
  if (last0 && last1)
    return -EINVAL;
  if (!out)
    return -EINVAL;
  int seen0 = last0 || (breakpoint & POPS_BREAKPOINT_0_SEEN);
  size_t size = seen0 ? POPS_BREAKPOINT_SIZE : POPS_BREAKPOINT_TEMPLATE_SIZE;
  if (out_size < size)
    return -ERANGE;
  /* The template: any built-in breakpoint handler (all copy the same
   * 292 bytes from 0x96bde0) with the two words the entry adds cleared. */
  for (uint16_t id = 0; id <= POPS_BUILTIN_MAX_ID && !ops; ++id) {
    const PopsBuiltinOp *eops;
    unsigned ecount;
    if (pops_builtin_entry_ops(id, &eops, &ecount))
      continue;
    for (unsigned i = 0; i < ecount; ++i) {
      if (eops[i].kind == POPS_BUILTIN_OP_EE && eops[i].addr == POPS_BUILTIN_BREAK_ADDR &&
          eops[i].len == POPS_BREAKPOINT_TEMPLATE_SIZE &&
          (uint64_t)eops[i].data + eops[i].len <= pops_builtin_data_size) {
        ops = &eops[i];
        count = 1;
        break;
      }
    }
  }
  if (!count)
    return -EILSEQ;
  memset(out, 0, size);
  if (seen0) /* the words a $BREAKPOINT0 left past the copy */
    put_words(out, 0x120, bp0_tail, 4);
  memcpy(out, pops_builtin_data + ops->data, POPS_BREAKPOINT_TEMPLATE_SIZE);
  memset(out + 0x11c, 0, 8);
  if (last0) {
    put_words(out, 0x000, bp0_head, 8);
    put_words(out, 0x080, &bp0_end, 1);
    put_words(out, 0x120, bp0_tail, 4);
  } else {
    put_words(out, 0x000, bp1_head, 8);
  }
  return (int)size;
}
