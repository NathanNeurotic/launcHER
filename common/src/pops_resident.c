#include "pops_resident.h"
#include "pops_builtin_db.h"
#include "pops_modes_patches.h"
#include <errno.h>
#include <string.h>

#define POPS_CORE_BASE UINT32_C(0x00200000)

static uint32_t get_u32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void put_u32(uint8_t *p, uint32_t v) {
  p[0] = (uint8_t)v;
  p[1] = (uint8_t)(v >> 8);
  p[2] = (uint8_t)(v >> 16);
  p[3] = (uint8_t)(v >> 24);
}

static int cheat_is_condition(uint8_t type) {
  return (type >= 0xD0 && type <= 0xD3) || type == 0xE0 || type == 0xE1;
}

static int cheat_is_write(uint8_t type) {
  return type == 0x80 || type == 0x30 || type == 0x10 || type == 0x20;
}

/* The PS1 store a repeat's leftover write uses after a PS2 write of this
 * size: sb, sh or sw. */
static uint8_t cheat_store_of_size(unsigned size) {
  return size == 0 ? 0x30 : size == 1 ? 0x80 : POPS_CHEAT_W32;
}

/* POPStarter emits each code as a few instructions that leave values in
 * k0/k1; a $D0 loads its compare into them and its branch is emitted only
 * in front of the next PS1 write. The compiled codes keep that shape:
 * LOAD16 for the $D0, BNE in front of the code it gates, so whatever runs
 * in between (PS2 writes) changes the compare exactly as it does there. */
uint16_t pops_cheats_compile(const PopsCheatEntry *in, uint16_t count, PopsCheatEntry *out,
                             uint16_t capacity) {
  int pending = 0; /* a $D0 branch waits for the next PS1 write */
  /* After a PS2 conditional, POPStarter compiles the rest of the file in a
   * reduced copy of its loop, one per kind of conditional, that knows only
   * writes: 0 (none yet), or the conditional's type (EE, SPR, PS1SPR). */
  unsigned nested = 0;
  uint16_t n = 0;
  int repeat = -1, stash = -1;

  /* Each code yields at most two compiled ones (a write may take a branch
   * in front), plus a repeat copy and the leftover expansion at the end. */
  if (!in || !out || capacity < 2u * count + 4u)
    return 0;
  for (uint16_t i = 0; i < count; ++i) {
    if (in[i].type == 0xC0) {
      out[n] = in[i];
      out[n].address &= POPS_CHEAT_ADDR_MASK;
      out[n].value &= 0xFFFFu;
      out[n++].skip = 0;
      break;
    }
  }

  uint8_t last_write = 0;
  for (uint32_t i = 0; i <= count; ++i) {
    PopsCheatEntry e;
    if (i == count) {
      /* A repeat with no write after it still expands, onto address 0 and
       * value 0, with the store of the last write before it (or none). */
      if (repeat < 0 || !last_write)
        break;
      memset(&e, 0, sizeof(e));
      e.type = last_write;
    } else {
      e = in[i];
      e.skip = 0;
    }
    if (POPS_CHEAT_IS_PS2(e.type)) {
      unsigned kind = e.type & 0xFCu;
      if (e.cond != POPS_CHEAT_COND_NONE) {
        /* Dropped behind a pending branch, a pending repeat, or an earlier
         * PS2 conditional. Its own branch is fixed: it skips the next code. */
        if (pending || repeat >= 0 || nested)
          continue;
        nested = kind;
        e.skip = 1;
        out[n++] = e;
        continue;
      }
      if (nested) {
        /* What each reduced loop still knows: EE writes always, $S writes
         * after a $S or $T conditional, $T writes after a $T or $=/$!. */
        if ((kind == POPS_CHEAT_SPR && nested == POPS_CHEAT_EE) ||
            (kind == POPS_CHEAT_PS1SPR && nested == POPS_CHEAT_SPR))
          continue;
      } else {
        /* Dropped while a repeat waits. A $0/$1/$2 write is placed even
         * between a $D0 and its branch; a $S/$T write there is dropped. */
        if (repeat >= 0 || (pending && kind != POPS_CHEAT_EE))
          continue;
      }
      last_write = cheat_store_of_size(e.type & 3u);
      out[n++] = e;
      continue;
    }
    e.address &= e.type == 0x50 ? 0xFFFFu : POPS_CHEAT_ADDR_MASK;
    e.value &= 0xFFFFu;
    if (cheat_is_condition(e.type)) {
      /* Dropped behind a pending branch, a pending repeat or a PS2
       * conditional. */
      if (pending || repeat >= 0 || nested)
        continue;
      pending = 1;
      e.type = POPS_CHEAT_LOAD16;
      out[n++] = e;
      /* POPStarter keeps the first repeat it skipped, and an emitted
       * conditional makes it the pending repeat for the code it gates. */
      if (stash >= 0) {
        repeat = stash;
        stash = -1;
      }
    } else if (e.type == 0x50) {
      if (nested)
        continue; /* after a PS2 conditional, repeats are ignored */
      if (repeat < 0)
        repeat = (int)i;
      else if (stash < 0)
        stash = (int)i; /* skipped while the first waits, kept for later */
    } else if (cheat_is_write(e.type) || e.type == POPS_CHEAT_W32) {
      last_write = e.type;
      int block = repeat >= 0 ? 2 : 1;
      if (pending) {
        PopsCheatEntry b;
        memset(&b, 0, sizeof(b));
        b.type = POPS_CHEAT_BNE;
        b.skip = (uint8_t)block;
        out[n++] = b;
        /* After a repeat block a leftover branch compares again, in front
         * of the next PS1 write: k0/k1 then hold the block's last write
         * (never equal), or the $D0's compare when the block wrote nothing. */
        pending = block == 2;
      }
      if (repeat >= 0) {
        out[n] = in[repeat];
        out[n].address &= 0xFFFFu;
        out[n].value &= 0xFFFFu;
        out[n++].skip = 0;
      }
      out[n++] = e;
      repeat = -1;
    }
    /* $C0 is hoisted above; anything else is not a code. */
  }
  return n;
}

int pops_resident_check_image(const void *image, size_t image_len, PopsResidentHeader *out) {
  const uint8_t *b = (const uint8_t *)image;
  if (!b || image_len < sizeof(PopsResidentHeader))
    return -EINVAL;

  PopsResidentHeader h;
  h.magic = get_u32(b);
  h.version = (uint16_t)(b[4] | (b[5] << 8));
  h.header_size = (uint16_t)(b[6] | (b[7] << 8));
  h.file_size = get_u32(b + 8);
  h.image_size = get_u32(b + 12);
  h.vblank_entry = get_u32(b + 16);
  h.config_addr = get_u32(b + 20);
  h.display_entry = get_u32(b + 24);
  h.progressive_entry = get_u32(b + 28);
  h.pad_read_entry = get_u32(b + 32);
  h.pad_read_exit = get_u32(b + 36);
  h.gte_scale_entry = get_u32(b + 40);
  h.gte_divide_entry = get_u32(b + 44);
  h.gte_ultra_entry = get_u32(b + 48);
  h.gp1_entry = get_u32(b + 52);
  for (unsigned i = 0; i < POPS_GUARD_COUNT; ++i)
    h.guard_entry[i] = get_u32(b + 56 + 4 * i);
  h.recompiler_entry = get_u32(b + 92);
  for (unsigned i = 0; i < POPS_EMIT_COUNT; ++i)
    h.recompiler_emit[i] = get_u32(b + 96 + 4 * i);
  h.gp1_chain_entry = get_u32(b + 112);
  h.gp1_resume_a = get_u32(b + 116);
  h.gp1_resume_b = get_u32(b + 120);

  if (h.magic != POPS_RESIDENT_MAGIC || h.version != POPS_RESIDENT_VERSION ||
      h.header_size != sizeof(PopsResidentHeader))
    return -EINVAL;
  if (h.file_size != image_len || h.file_size > h.image_size ||
      h.image_size > POPS_RESIDENT_LIMIT - POPS_RESIDENT_BASE)
    return -ERANGE;
  /* The entry must be code inside the image, word aligned. */
  if ((h.vblank_entry & 3) || h.vblank_entry < POPS_RESIDENT_BASE + h.header_size ||
      h.vblank_entry >= POPS_RESIDENT_BASE + h.file_size)
    return -ERANGE;
  if ((h.display_entry & 3) || h.display_entry < POPS_RESIDENT_BASE + h.header_size ||
      h.display_entry >= POPS_RESIDENT_BASE + h.file_size)
    return -ERANGE;
  if ((h.progressive_entry & 3) || h.progressive_entry < POPS_RESIDENT_BASE + h.header_size ||
      h.progressive_entry >= POPS_RESIDENT_BASE + h.file_size)
    return -ERANGE;
  if ((h.pad_read_entry & 3) || h.pad_read_entry < POPS_RESIDENT_BASE + h.header_size ||
      h.pad_read_entry >= POPS_RESIDENT_BASE + h.file_size)
    return -ERANGE;
  if ((h.pad_read_exit & 3) || h.pad_read_exit < POPS_RESIDENT_BASE + h.header_size ||
      h.pad_read_exit >= POPS_RESIDENT_BASE + h.file_size)
    return -ERANGE;
  const uint32_t gte[] = {h.gte_scale_entry, h.gte_divide_entry, h.gte_ultra_entry, h.gp1_entry};
  for (unsigned i = 0; i < 4; ++i) {
    if ((gte[i] & 3) || gte[i] < POPS_RESIDENT_BASE + h.header_size ||
        gte[i] >= POPS_RESIDENT_BASE + h.file_size)
      return -ERANGE;
  }
  for (unsigned i = 0; i < POPS_GUARD_COUNT; ++i) {
    if ((h.guard_entry[i] & 3) || h.guard_entry[i] < POPS_RESIDENT_BASE + h.header_size ||
        h.guard_entry[i] >= POPS_RESIDENT_BASE + h.file_size)
      return -ERANGE;
  }
  for (unsigned i = 0; i <= POPS_EMIT_COUNT; ++i) {
    uint32_t e = i < POPS_EMIT_COUNT ? h.recompiler_emit[i] : h.recompiler_entry;
    if ((e & 3) || e < POPS_RESIDENT_BASE + h.header_size || e >= POPS_RESIDENT_BASE + h.file_size)
      return -ERANGE;
  }
  const uint32_t chain[] = {h.gp1_chain_entry, h.gp1_resume_a, h.gp1_resume_b};
  for (unsigned i = 0; i < 3; ++i) {
    if ((chain[i] & 3) || chain[i] < POPS_RESIDENT_BASE + h.header_size ||
        chain[i] >= POPS_RESIDENT_BASE + h.file_size)
      return -ERANGE;
  }
  /* The configuration must fit inside the image, in its zeroed part or not,
   * 16-byte aligned: POPS DMAs the disc names straight from its slots. */
  if ((h.config_addr & 15) || h.config_addr < POPS_RESIDENT_BASE + h.header_size ||
      h.config_addr > POPS_RESIDENT_BASE + h.image_size - sizeof(PopsResidentConfig))
    return -ERANGE;

  if (out)
    *out = h;
  return 0;
}

int pops_resident_build_config(PopsResidentConfig *out, const PopsConfig *cfg) {
  if (!out || !cfg)
    return -EINVAL;
  memset(out, 0, sizeof(*out));
  out->pops_vblank = POPS_VBLANK_HANDLER;
  out->ram_base_ptr = POPS_PS1_RAM_BASE_PTR;

  if (cfg->gs_mask & ~0x3f || cfg->gs_display_valid > 1 || cfg->progressive_requested > 1)
    return -EINVAL;
  if (cfg->progressive_requested || cfg->video_mode == POPS_VMODE_480P)
    out->flags |= POPS_RES_F_PROGRESSIVE;
  if (cfg->gs_display_valid) {
    out->gs_display = cfg->gs_display;
    out->flags |= POPS_RES_F_DISPLAY;
  }

  if (cfg->pad_override & ~3u)
    return -EINVAL;
  if (cfg->pad_override) {
    out->flags |= POPS_RES_F_PAD_ID;
    out->pad_override = cfg->pad_override;
    out->pad_id[0] = cfg->pad_id[0];
    out->pad_id[1] = cfg->pad_id[1];
  }
  if (cfg->pad_d2ls)
    out->flags |= POPS_RES_F_D2LS;
  if (cfg->set_timings)
    out->flags |= POPS_RES_F_TIMINGS | POPS_RES_F_TIMINGS_SAVE;
  if (cfg->widescreen > POPS_WIDESCREEN_EYEFINITY)
    return -EINVAL;
  if (cfg->widescreen) {
    out->flags |= POPS_RES_F_WIDESCREEN;
    out->gte_divisor = cfg->widescreen == POPS_WIDESCREEN_EYEFINITY ? 4 : 100;
  }

  /* The built-in per-game entry's chain work (pops_builtin_db.h). */
  if (cfg->builtin_break_call)
    out->flags |= POPS_RES_F_BREAK_CALL;
  if (cfg->builtin_fix_call)
    out->flags |= POPS_RES_F_FIX_CALL;
  if (cfg->builtin_libcrypt2) {
    out->flags |= POPS_RES_F_LIBCRYPT2;
    memcpy(out->libcrypt2_code, cfg->builtin_libcrypt2_code, POPS_BUILTIN_LIBCRYPT2_SIZE);
    out->libcrypt2_code[POPS_BUILTIN_LIBCRYPT2_SIZE / 4] = 0x03e00008; /* jr ra */
    out->libcrypt2_code[POPS_BUILTIN_LIBCRYPT2_SIZE / 4 + 1] = 0;      /* nop */
  }
  /* $RECOMPILER_ADDON_0/1/2: what the recompiler hook runs. 3 and 4 are
   * jumps written into POPS (pops_resident_hook_recompiler_emit). */
  if (cfg->recompiler_addons & ~0x1fu)
    return -EINVAL;
  if (cfg->recompiler_addons & POPS_RECOMPILER_ADDON_0)
    out->flags |= POPS_RES_F_RECOMPILER_0;
  if (cfg->recompiler_addons & POPS_RECOMPILER_ADDON_1)
    out->flags |= POPS_RES_F_RECOMPILER_1;
  if (cfg->recompiler_addons & POPS_RECOMPILER_ADDON_2)
    out->flags |= POPS_RES_F_RECOMPILER_2;
  /* $NOVMC0 / $NOVMC1: the always-live block's per-pass card stores. A
   * built-in entry's card 1 off (builtin_no_vmc1) is only its core write,
   * as in the original, whose helper leaves the block's branch alone. */
  if (cfg->no_vmc0 > 1 || cfg->no_vmc1 > 1)
    return -EINVAL;
  if (cfg->no_vmc0)
    out->flags |= POPS_RES_F_NOVMC0;
  if (cfg->no_vmc1)
    out->flags |= POPS_RES_F_NOVMC1;
  /* The in-game reset's jump word: the BIOS reset vector, or the stub
   * $RESET_WARMBOOT found (pops_apply_reset_warmboot). */
  out->reset_vector = cfg->reset_vector ? cfg->reset_vector : POPS_RESET_VECTOR_DEFAULT;
  /* The in-game disc swap's slots, as DISCS.TXT left them; slot 0 selected
   * at first, as the original's ori starts out. Always live. */
  memcpy(out->disc_slot, cfg->disc_slot, sizeof(out->disc_slot));
  out->disc_selected = 0;

  uint16_t count = cfg->cheat_count;
  if (count > POPS_MAX_CHEATS)
    return -ERANGE;
  if (count) {
    out->flags |= POPS_RES_F_CHEATS;
    out->cheat_count = pops_cheats_compile(cfg->cheats, count, out->cheats, POPS_CHEAT_COMPILED_MAX);
    out->safe_mode = cfg->safe_mode & (POPS_SAFE_MODE_BOOT | POPS_SAFE_MODE_2);
  }
  return out->flags ? 1 : 0;
}

int pops_resident_hook_core(void *staged_core, size_t core_size, uint32_t entry) {
  uint8_t *core = (uint8_t *)staged_core;
  if (!core)
    return -EINVAL;
  if (core_size < POPS_VBLANK_ADDIU_ADDR - POPS_CORE_BASE + 4)
    return -ERANGE;
  if ((entry & 3) || entry < POPS_RESIDENT_BASE || entry >= POPS_RESIDENT_LIMIT)
    return -EINVAL;

  uint8_t *lui = core + (POPS_VBLANK_LUI_ADDR - POPS_CORE_BASE);
  uint8_t *addiu = core + (POPS_VBLANK_ADDIU_ADDR - POPS_CORE_BASE);
  uint16_t hi = (uint16_t)((entry + 0x8000) >> 16);
  uint16_t lo = (uint16_t)entry;
  uint32_t want_lui = 0x3c050000u | hi;
  uint32_t want_addiu = 0x24a50000u | lo;

  uint32_t cur_lui = get_u32(lui);
  uint32_t cur_addiu = get_u32(addiu);
  if (cur_lui == want_lui && cur_addiu == want_addiu)
    return 0;
  if (cur_lui != POPS_VBLANK_LUI_PRISTINE || cur_addiu != POPS_VBLANK_ADDIU_PRISTINE)
    return -EILSEQ;

  put_u32(lui, want_lui);
  put_u32(addiu, want_addiu);
  return 0;
}

int pops_resident_hook_gp1(void *staged_core, size_t core_size, uint32_t entry) {
  uint8_t *core = (uint8_t *)staged_core;
  static const uint32_t fixed[][2] = {
    {0x0021a630, 0x5060000b}, /* beql  $v1, $zero, 0x21a660 (EIE clear) */
    {0x0021a638, 0x3c030001}, /* lui   $v1, 1 */
    {0x0021a640, 0x42000039}, /* di (the jal's delay slot) */
    {0x0021a644, 0x0000040f}, /* sync.p */
    {0x0021a648, 0x40026000}, /* mfc0  $v0, Status */
    {0x0021a64c, 0x00431024}, /* and   $v0, $v0, $v1 */
  };
  if (!core)
    return -EINVAL;
  if ((entry & 3) || entry < POPS_RESIDENT_BASE || entry >= POPS_RESIDENT_LIMIT)
    return -EINVAL;
  if (core_size < 0x0021a650 - POPS_CORE_BASE)
    return -ERANGE;
  for (unsigned i = 0; i < sizeof(fixed) / sizeof(fixed[0]); ++i) {
    if (get_u32(core + fixed[i][0] - POPS_CORE_BASE) != fixed[i][1])
      return -EILSEQ;
  }
  uint8_t *site = core + POPS_GP1_HOOK_ADDR - POPS_CORE_BASE;
  uint32_t jal = 0x0c000000u | ((entry >> 2) & 0x03ffffffu);
  uint32_t cur = get_u32(site);
  if (cur != POPS_GP1_HOOK_PRISTINE && cur != jal)
    return -EILSEQ;
  put_u32(site, jal);
  return 0;
}

/* POPS's own bytes in the two runs (0x30 bytes each), as an FNV-1a sum:
 * part of its unreferenced function at 0x232790. */
#define SLOT_RUN_A_PRISTINE UINT32_C(0xa465b265)
#define SLOT_RUN_B_PRISTINE UINT32_C(0x0b521ce9)

static uint32_t slot_run_sum(const uint8_t *bytes) {
  uint32_t sum = UINT32_C(0x811c9dc5);
  for (unsigned i = 0; i < POPS_TROJAN_SLOTS_SPAN; ++i)
    sum = (sum ^ bytes[i]) * UINT32_C(0x01000193);
  return sum;
}

static int slot_chain_check(const uint8_t *core, size_t core_size, const PopsResidentHeader *h) {
  const uint32_t entries[] = {h->gp1_entry, h->gp1_chain_entry, h->gp1_resume_a, h->gp1_resume_b};
  for (unsigned i = 0; i < 4; ++i)
    if ((entries[i] & 3) || entries[i] < POPS_RESIDENT_BASE || entries[i] >= POPS_RESIDENT_LIMIT)
      return -EINVAL;
  if (core_size < POPS_TROJAN_SLOTS_B + POPS_TROJAN_SLOTS_SPAN - POPS_CORE_BASE)
    return -ERANGE;
  if (slot_run_sum(core + POPS_TROJAN_SLOTS_A - POPS_CORE_BASE) != SLOT_RUN_A_PRISTINE ||
      slot_run_sum(core + POPS_TROJAN_SLOTS_B - POPS_CORE_BASE) != SLOT_RUN_B_PRISTINE ||
      get_u32(core + POPS_GP1_HOOK_ADDR - POPS_CORE_BASE) !=
          (0x0c000000u | ((h->gp1_entry >> 2) & 0x03ffffffu)))
    return -EILSEQ;
  return 0;
}

int pops_resident_slot_chain_possible(const void *staged_core, size_t core_size,
                                      const PopsResidentHeader *header) {
  return staged_core && header && !slot_chain_check(staged_core, core_size, header);
}

int pops_resident_hook_slot_chain(void *staged_core, size_t core_size,
                                  const PopsResidentHeader *header, PopsTrojanSet *set,
                                  unsigned slot4) {
  uint8_t *core = staged_core;
  uint32_t first;
  if (!core || !header || !set || slot4 > POPS_SLOT4_RESET_STORE)
    return -EINVAL;
  if (!set->chain)
    return 0;
  if (!set->chain_offered)
    return -EINVAL;
  int res = slot_chain_check(core, core_size, header);
  if (res)
    return res;
  /* Every check is done. */
  first = slot4 == POPS_SLOT4_BREAK_CALL ? POPS_TROJAN_BREAK_CALL :
          slot4 == POPS_SLOT4_RESET_STORE ? POPS_TROJAN_SLOT_EMPTY : set->slot_word[1][0];
  set->slot_word[1][0] = first;
  for (unsigned run = 0; run < 2; ++run) {
    uint8_t *at = core + (run ? POPS_TROJAN_SLOTS_B : POPS_TROJAN_SLOTS_A) - POPS_CORE_BASE;
    uint32_t resume = run ? header->gp1_resume_b : header->gp1_resume_a;
    for (unsigned i = 0; i < POPS_TROJAN_SLOTS_HOOKS / 4; ++i)
      put_u32(at + 4 * i, set->slot_word[run][i]);
    put_u32(at + POPS_TROJAN_SLOTS_HOOKS, 0x08000000u | ((resume >> 2) & 0x03ffffffu));
    put_u32(at + POPS_TROJAN_SLOTS_HOOKS + 4, 0);
  }
  put_u32(core + POPS_GP1_HOOK_ADDR - POPS_CORE_BASE,
          0x0c000000u | ((header->gp1_chain_entry >> 2) & 0x03ffffffu));
  return 1;
}

/* POPStarter's always-on guards (0x874864..0x874998), in its order: the
 * word that becomes "j stub", POPS's word there, and POPS's word after it,
 * which becomes a nop, except at 0x204160, where it is the branch's delay
 * slot and stays. */
static const struct {
  uint32_t site, pristine, next;
  uint8_t keep_next;
} guard_sites[POPS_GUARD_COUNT] = {
  {0x0021c58c, 0x8c820000, 0x24840004, 0}, /* lw $v0,0($a0) / addiu $a0,$a0,4 */
  {0x0021c768, 0x8c440000, 0x24420004, 0}, /* lw $a0,0($v0) / addiu $v0,$v0,4 */
  {0x002082a0, 0x8c660000, 0x14c00003, 0}, /* lw $a2,0($v1) / bnez $a2,0x2082b4 */
  {0x00204ae0, 0x8c630000, 0x3c023c02, 0}, /* lw $v1,0($v1) / lui $v0,0x3c02 */
  {0x00204178, 0x8c650000, 0x00053e82, 0}, /* lw $a1,0($v1) / srl $a3,$a1,26 */
  {0x00204160, 0x10000006, 0x0040282d, 1}, /* b 0x20417c / move $a1,$v0 (kept) */
  {0x00202250, 0x03e00008, 0xac4a0000, 0}, /* jr $ra / sw $t2,0($v0) */
  {0x0021c5dc, 0xae052260, 0xae032270, 0}, /* sw $a1,0x2260($s0) / sw $v1,0x2270($s0) */
  {0x0021c5a8, 0xad422288, 0xad452260, 0}, /* sw $v0,0x2288($t2) / sw $a1,0x2260($t2) */
};

/* Words the stubs return to or repeat; the hooks leave them alone. */
static const uint32_t guard_context[][2] = {
  {0x0021c594, 0x00471824}, /* and   $v1, $v0, $a3 (0x21c58c resumes) */
  {0x0021c770, 0xafa20000}, /* sw    $v0, 0($sp) (0x21c768 resumes) */
  {0x002082a8, 0x00000000}, /* nop (the bnez's delay slot) */
  {0x002082ac, 0x0808207c}, /* j     0x2081f0 (word zero) */
  {0x002082b0, 0x24020001}, /* addiu $v0, $zero, 1 */
  {0x002082b4, 0x00c00008}, /* jr    $a2 (word nonzero) */
  {0x00204ae8, 0x34428001}, /* ori   $v0, $v0, 0x8001 (0x204ae0 resumes) */
  {0x00204180, 0x00051542}, /* srl   $v0, $a1, 21 (0x204178 resumes) */
  {0x00202238, 0x3c02e060}, /* lui   $v0, 0xe060: the store address... */
  {0x0020224c, 0x00431021}, /* addu  $v0, $v0, $v1 ...ends here */
  {0x0021c5e4, 0x42000038}, /* ei (0x21c5dc resumes) */
  {0x0021c5b0, 0xad432270}, /* sw    $v1, 0x2270($t2) (0x21c5a8 resumes) */
};

int pops_resident_hook_guards(void *staged_core, size_t core_size,
                              const PopsResidentHeader *hdr) {
  uint8_t *core = staged_core;
  if (!core || !hdr)
    return -EINVAL;
  for (unsigned i = 0; i < POPS_GUARD_COUNT; ++i) {
    uint32_t entry = hdr->guard_entry[i];
    if ((entry & 3) || entry < POPS_RESIDENT_BASE || entry >= POPS_RESIDENT_LIMIT)
      return -EINVAL;
  }
  if (core_size < 0x0021c770 + 4 - POPS_CORE_BASE)
    return -ERANGE;
  for (unsigned i = 0; i < sizeof(guard_context) / sizeof(guard_context[0]); ++i) {
    if (get_u32(core + guard_context[i][0] - POPS_CORE_BASE) != guard_context[i][1])
      return -EILSEQ;
  }
  for (unsigned i = 0; i < POPS_GUARD_COUNT; ++i) {
    const uint8_t *site = core + guard_sites[i].site - POPS_CORE_BASE;
    uint32_t jump = 0x08000000u | ((hdr->guard_entry[i] >> 2) & 0x03ffffffu);
    uint32_t next = guard_sites[i].keep_next ? guard_sites[i].next : 0;
    uint32_t cur = get_u32(site), cur_next = get_u32(site + 4);
    if (!(cur == guard_sites[i].pristine && cur_next == guard_sites[i].next) &&
        !(cur == jump && cur_next == next))
      return -EILSEQ;
  }
  for (unsigned i = 0; i < POPS_GUARD_COUNT; ++i) {
    uint8_t *site = core + guard_sites[i].site - POPS_CORE_BASE;
    put_u32(site, 0x08000000u | ((hdr->guard_entry[i] >> 2) & 0x03ffffffu));
    if (!guard_sites[i].keep_next)
      put_u32(site + 4, 0);
  }
  return 0;
}

/* POPS's recompiler epilogue around the hook (0x2075c4..0x2075f8): the
 * words the hook's code depends on. It returns to the $ra load, having
 * reloaded $s0..$s5 from the slots these loads read, and $a2 is where POPS
 * stores the block's last instruction. */
static const uint32_t recompiler_context[][2] = {
  {0x002075c4, 0xdfb50038}, /* ld    $s5, 0x38($sp) */
  {0x002075d8, 0xdfb00010}, /* ld    $s0, 0x10($sp) */
  {0x002075e0, 0xdfb10018}, /* ld    $s1, 0x18($sp) */
  {0x002075e4, 0x24c20004}, /* addiu $v0, $a2, 4 */
  {0x002075f0, 0xdfb40030}, /* ld    $s4, 0x30($sp) */
  {0x002075f4, 0xdfbf0040}, /* ld    $ra, 0x40($sp) (the hook returns here) */
  {0x002075f8, 0xacc30000}, /* sw    $v1, 0($a2) */
};

int pops_resident_hook_recompiler(void *staged_core, size_t core_size, uint32_t entry) {
  uint8_t *core = staged_core;
  if (!core)
    return -EINVAL;
  if ((entry & 3) || entry < POPS_RESIDENT_BASE || entry >= POPS_RESIDENT_LIMIT)
    return -EINVAL;
  if (core_size < 0x002075f8 + 4 - POPS_CORE_BASE)
    return -ERANGE;
  for (unsigned i = 0; i < sizeof(recompiler_context) / sizeof(recompiler_context[0]); ++i) {
    if (get_u32(core + recompiler_context[i][0] - POPS_CORE_BASE) != recompiler_context[i][1])
      return -EILSEQ;
  }
  uint8_t *site = core + POPS_RECOMPILER_HOOK_ADDR - POPS_CORE_BASE;
  uint32_t jump = 0x08000000u | ((entry >> 2) & 0x03ffffffu);
  uint32_t cur = get_u32(site), cur_next = get_u32(site + 4);
  if (!(cur == 0xdfb20020 && cur_next == 0xdfb30028) && /* ld $s2, 0x20 / ld $s3, 0x28 */
      !(cur == jump && cur_next == 0))
    return -EILSEQ;
  put_u32(site, jump);
  put_u32(site + 4, 0);
  return 0;
}

/* POPS's two emit points ($RECOMPILER_ADDON_3/4): the two words replaced,
 * and the words their code resumes with. */
static const struct {
  uint32_t site, pristine, next;
  uint32_t context[2][2];
} emit_sites[2] = {
  {POPS_EMIT_206318_ADDR, 0xae220000, 0x26310004, /* sw $v0,0($s1) / addiu $s1,$s1,4 */
   {{0x00206314, 0x00431025},   /* or    $v0, $v0, $v1 (the word) */
    {0x00206320, 0x8cc20000}}}, /* lw    $v0, 0($a2) (resume) */
  {POPS_EMIT_205D1C_ADDR, 0x00822025, 0xad840000, /* or $a0,$a0,$v0 / sw $a0,0($t4) */
   {{0x00205d24, 0x12cb0008},   /* beq   $s6, $t3, 0x205d48 (resume) */
    {0x00205d28, 0x258c0004}}}, /* addiu $t4, $t4, 4 (its delay slot) */
};

int pops_resident_hook_recompiler_emit(void *staged_core, size_t core_size,
                                       uint8_t addons, const PopsResidentHeader *hdr) {
  uint8_t *core = staged_core;
  if (!core || !hdr || (addons & ~0x1fu))
    return -EINVAL;
  if (!(addons & (POPS_RECOMPILER_ADDON_3 | POPS_RECOMPILER_ADDON_4)))
    return 0;
  for (unsigned i = 0; i < POPS_EMIT_COUNT; ++i) {
    uint32_t e = hdr->recompiler_emit[i];
    if ((e & 3) || e < POPS_RESIDENT_BASE || e >= POPS_RESIDENT_LIMIT)
      return -EINVAL;
  }
  if (core_size < 0x00206320 + 4 - POPS_CORE_BASE)
    return -ERANGE;
  /* ADDON_4 is ADDON_3's jumps plus changes to its code, so it wins. */
  unsigned pick = (addons & POPS_RECOMPILER_ADDON_4) ? POPS_EMIT_ADDON4_206318
                                                     : POPS_EMIT_ADDON3_206318;
  for (unsigned i = 0; i < 2; ++i) {
    const uint8_t *site = core + emit_sites[i].site - POPS_CORE_BASE;
    uint32_t cur = get_u32(site), cur_next = get_u32(site + 4);
    uint32_t j3 = 0x08000000u | ((hdr->recompiler_emit[POPS_EMIT_ADDON3_206318 + i] >> 2) & 0x03ffffffu);
    uint32_t j4 = 0x08000000u | ((hdr->recompiler_emit[POPS_EMIT_ADDON4_206318 + i] >> 2) & 0x03ffffffu);
    for (unsigned k = 0; k < 2; ++k) {
      if (get_u32(core + emit_sites[i].context[k][0] - POPS_CORE_BASE) != emit_sites[i].context[k][1])
        return -EILSEQ;
    }
    if (!(cur == emit_sites[i].pristine && cur_next == emit_sites[i].next) &&
        !((cur == j3 || cur == j4) && cur_next == 0))
      return -EILSEQ;
  }
  for (unsigned i = 0; i < 2; ++i) {
    uint8_t *site = core + emit_sites[i].site - POPS_CORE_BASE;
    put_u32(site, 0x08000000u | ((hdr->recompiler_emit[pick + i] >> 2) & 0x03ffffffu));
    put_u32(site + 4, 0);
  }
  return 0;
}

int pops_resident_install(void *dest, size_t dest_len, uint32_t dest_addr,
                          const void *image, size_t image_len,
                          const PopsResidentConfig *rcfg) {
  PopsResidentHeader h;
  if (!dest || !rcfg || dest_addr != POPS_RESIDENT_BASE)
    return -EINVAL;
  int res = pops_resident_check_image(image, image_len, &h);
  if (res)
    return res;
  if (dest_len < h.image_size)
    return -ERANGE;

  uint8_t *d = (uint8_t *)dest;
  memcpy(d, image, h.file_size);
  memset(d + h.file_size, 0, h.image_size - h.file_size);
  memcpy(d + (h.config_addr - dest_addr), rcfg, sizeof(*rcfg));
  return 0;
}

int pops_resident_hook_display(void *staged_core, size_t core_size, uint32_t entry) {
  uint8_t *core = staged_core;
  static const uint32_t sites[] = {0x21a094, 0x21a098, 0x23acb0, 0x23ad0c};
  if (!core || (entry & 3) || entry < POPS_RESIDENT_BASE || entry >= POPS_RESIDENT_LIMIT)
    return -EINVAL;
  if (core_size < sites[3] - POPS_CORE_BASE + 4)
    return -ERANGE;
  uint32_t jump = 0x08000000u | (entry >> 2);
  for (unsigned i = 0; i < 4; ++i) {
    uint32_t cur = get_u32(core + sites[i] - POPS_CORE_BASE);
    if (i == 0 ? (cur != 0xde050010 && cur != jump) :
        i == 1 ? cur != 0x3c031200 : (cur != 0x32240001 && cur != 0x24040001))
      return -EILSEQ;
  }
  put_u32(core + sites[0] - POPS_CORE_BASE, jump);
  /* Config staging already restores these for a complete manual file.
   * Preserve a later file's explicit HDTVFIX instead of undoing it here. */
  return 0;
}

uint32_t pops_resident_progressive_interlace(const PopsConfig *cfg) {
  if (!cfg)
    return 0;
  return cfg->hdtv_fix ? 0x24040001 :
           (cfg->original_tokens & POPS_TOK_NOHDTVFIX) ? 0x32240001 : 0x24040000;
}

int pops_resident_hook_progressive(void *staged_core, size_t core_size,
                                    uint32_t entry, uint32_t interlace) {
  uint8_t *core = staged_core;
  static const uint32_t sites[] = {0x21a094, 0x21a098, 0x21af94, 0x23acb0, 0x23ad0c};
  if (!core || (entry & 3) || entry < POPS_RESIDENT_BASE || entry >= POPS_RESIDENT_LIMIT ||
      (interlace != 0x24040000 && interlace != 0x24040001 && interlace != 0x32240001))
    return -EINVAL;
  if (core_size < sites[4] - POPS_CORE_BASE + 4)
    return -ERANGE;
  uint32_t jump = 0x08000000u | (entry >> 2);
  uint32_t expected_arg = interlace == 0x24040000 ? 0x32240001 : interlace;
  for (unsigned i = 0; i < 5; ++i) {
    uint32_t cur = i == 2 ? core[sites[i] - POPS_CORE_BASE] : get_u32(core + sites[i] - POPS_CORE_BASE);
    if (i == 0 ? (cur != 0xde050010 && cur != jump) :
        i == 1 ? cur != 0x3c031200 : i == 2 ? (cur != 2 && cur != 0x50) :
        (cur != expected_arg && cur != interlace))
      return -EILSEQ;
  }
  put_u32(core + sites[0] - POPS_CORE_BASE, jump);
  core[sites[2] - POPS_CORE_BASE] = 0x50;
  put_u32(core + sites[3] - POPS_CORE_BASE, interlace);
  put_u32(core + sites[4] - POPS_CORE_BASE, interlace);
  return 0;
}

int pops_resident_hook_pads(void *staged_core, size_t core_size, uint32_t flags,
                            uint32_t read_entry, uint32_t read_exit) {
  uint8_t *core = staged_core;
  /* The pad state references the resident code relies on. */
  static const uint32_t state_sites[][2] = {
    {0x0020c648, 0x3c070050}, /* lui   $a3, 0x50 */
    {0x0020c64c, 0x24e77000}, /* addiu $a3, $a3, 0x7000 */
    {0x0020c6c8, 0x8ce80034}, /* lw    $t0, 0x34($a3): the reported ID */
  };
  /* The pad read around the two hook words. */
  static const uint32_t read_sites[][2] = {
    {0x00237798, 0x0080382d}, /* move  $a3, $a0 */
    {0x002377a0, 0x2404001c}, /* addiu $a0, $zero, 0x1c */
    {0x00237810, 0x27bd0030}, /* addiu $sp, $sp, 0x30 (exit delay slot) */
  };
  if (!core)
    return -EINVAL;
  if (!(flags & (POPS_RES_F_PAD_ID | POPS_RES_F_D2LS)))
    return 0;
  if (core_size < POPS_PAD_READ_EXIT_ADDR + 8 - POPS_CORE_BASE)
    return -ERANGE;
  for (unsigned i = 0; i < 3; ++i) {
    if (get_u32(core + state_sites[i][0] - POPS_CORE_BASE) != state_sites[i][1])
      return -EILSEQ;
  }
  if (!(flags & POPS_RES_F_D2LS))
    return 0;

  if ((read_entry & 3) || read_entry < POPS_RESIDENT_BASE || read_entry >= POPS_RESIDENT_LIMIT ||
      (read_exit & 3) || read_exit < POPS_RESIDENT_BASE || read_exit >= POPS_RESIDENT_LIMIT)
    return -EINVAL;
  for (unsigned i = 0; i < 3; ++i) {
    if (get_u32(core + read_sites[i][0] - POPS_CORE_BASE) != read_sites[i][1])
      return -EILSEQ;
  }
  uint8_t *entry = core + POPS_PAD_READ_ENTRY_ADDR - POPS_CORE_BASE;
  uint8_t *ret = core + POPS_PAD_READ_EXIT_ADDR - POPS_CORE_BASE;
  uint32_t jump_entry = 0x08000000u | (read_entry >> 2);
  uint32_t jump_exit = 0x08000000u | (read_exit >> 2);
  uint32_t cur_entry = get_u32(entry), cur_exit = get_u32(ret);
  if ((cur_entry != 0x24030070 && cur_entry != jump_entry) ||
      (cur_exit != 0x03e00008 && cur_exit != jump_exit))
    return -EILSEQ;
  put_u32(entry, jump_entry);
  put_u32(ret, jump_exit);
  return 0;
}

int pops_resident_hook_widescreen(void *staged_core, size_t core_size, uint8_t mode,
                                  const PopsResidentHeader *hdr) {
  uint8_t *core = staged_core;
  /* Neighbours the stubs rely on: the delay slots they let run, the stores
   * they return to, and the next writes of $v0/$v1 (dead registers). */
  static const uint32_t fixed[][2] = {
    {0x002089ac, 0xac890068}, /* sw    $t1, 0x68($a0) (delay slot) */
    {0x002089b0, 0xac8a006c}, /* sw    $t2, 0x6c($a0) (resume) */
    {0x002089b8, 0x24028000}, /* addiu $v0, $zero, -0x8000 */
    {0x002089bc, 0x24037fff}, /* addiu $v1, $zero, 0x7fff */
    {0x00208a30, 0xac890028}, /* sw    $t1, 0x28($a0) (delay slot) */
    {0x00208a34, 0xac8a002c}, /* sw    $t2, 0x2c($a0) (resume) */
    {0x00208a38, 0x3402ffff}, /* ori   $v0, $zero, 0xffff */
    {0x00208a3c, 0x3c038006}, /* lui   $v1, 0x8006 */
  };
  if (!core || !hdr || mode > POPS_WIDESCREEN_EYEFINITY)
    return -EINVAL;
  if (mode == POPS_WIDESCREEN_NONE)
    return 0;
  const uint32_t entries[] = {hdr->gte_scale_entry, hdr->gte_divide_entry, hdr->gte_ultra_entry};
  for (unsigned i = 0; i < 3; ++i) {
    if ((entries[i] & 3) || entries[i] < POPS_RESIDENT_BASE || entries[i] >= POPS_RESIDENT_LIMIT)
      return -EINVAL;
  }
  if (core_size < POPS_GTE_IR1_STORE_ADDR + 0x14 - POPS_CORE_BASE)
    return -ERANGE;
  for (unsigned i = 0; i < sizeof(fixed) / sizeof(fixed[0]); ++i) {
    if (get_u32(core + fixed[i][0] - POPS_CORE_BASE) != fixed[i][1])
      return -EILSEQ;
  }
  uint32_t j_scale = 0x08000000u | (hdr->gte_scale_entry >> 2);
  uint32_t j_divide = 0x08000000u | (hdr->gte_divide_entry >> 2);
  uint32_t j_ultra = 0x08000000u | (hdr->gte_ultra_entry >> 2);
  uint8_t *mac1 = core + POPS_GTE_MAC1_STORE_ADDR - POPS_CORE_BASE;
  uint8_t *ir1 = core + POPS_GTE_IR1_STORE_ADDR - POPS_CORE_BASE;
  uint32_t cur = get_u32(mac1);
  if (cur != 0xac880064 && cur != j_scale && cur != j_divide)
    return -EILSEQ;
  cur = get_u32(ir1);
  if (cur != 0xac880024 && cur != j_ultra)
    return -EILSEQ;
  put_u32(mac1, mode == POPS_WIDESCREEN_EYEFINITY ? j_divide : j_scale);
  put_u32(ir1, mode == POPS_WIDESCREEN_ULTRA ? j_ultra : 0xac880024);
  return 0;
}
