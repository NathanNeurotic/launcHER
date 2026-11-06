/* launcHER resident code for POPS (see pops_resident.h).
 *
 * Built twice: into the launcher and host tests for the per-frame logic, and
 * on its own with POPS_RESIDENT_IMAGE as a flat image linked at
 * POPS_RESIDENT_BASE (pops_resident.ld). The image build is freestanding:
 * no libc, no $gp (-G0), small stack, because the entry runs as an EE
 * interrupt handler while POPS owns the machine. */

#include "pops_resident.h"
#include "pops_builtin_db.h"

#define CHEAT_U8(a)  (*(volatile uint8_t *)(a))
#define CHEAT_U16(a) (*(volatile uint16_t *)(a))
#define CHEAT_U32(a) (*(volatile uint32_t *)(a))

static int64_t sext32(uint32_t v) {
  return (int64_t)(int32_t)v;
}

/* PS1 RAM as POPStarter addresses it: EE 0x01000000 + address. */
#define CHEAT_EE_PS1 0x01000000u

static void cheat_write(const PopsCheatMemory *mem, uint8_t type, uint32_t addr, uint32_t val) {
  unsigned size;
  uintptr_t at;
  if (type == 0x80 || type == 0x10)
    size = 2;
  else if (type == 0x30 || type == 0x20)
    size = 1;
  else if (type == POPS_CHEAT_W32)
    size = 4;
  else
    return;
  addr &= ~(uint32_t)(size - 1u);
  if (addr + size <= POPS_PS1_RAM_SIZE)
    at = mem->ps1 + addr;
  else if (mem->ee_size && addr < mem->ee_size - CHEAT_EE_PS1 - size + 1u &&
           mem->ee_size >= CHEAT_EE_PS1 + size)
    /* A repeat can carry the address past PS1 RAM (quirk 8); POPStarter's
     * store then lands in the EE RAM above it, and so does this one. */
    at = mem->ee + CHEAT_EE_PS1 + addr;
  else
    return;
  if (size == 2)
    CHEAT_U16(at) = (uint16_t)val;
  else if (size == 1)
    CHEAT_U8(at) = (uint8_t)val;
  else
    CHEAT_U32(at) = val;
}

/* A PS2-format code's memory: its base, how far it reaches, and the EE
 * address POPStarter loads into k0 (lui) for it. */
static int cheat_ps2_place(const PopsCheatMemory *mem, const PopsCheatEntry *e, uintptr_t *at,
                           uint32_t *ee_addr) {
  unsigned size = 1u << (e->type & 3u);
  uint32_t addr = e->address & ~(size - 1u);
  uintptr_t base;
  uint32_t limit, ee_base;
  switch (e->type & 0xFCu) {
  case POPS_CHEAT_EE:
    base = mem->ee, limit = mem->ee_size, ee_base = 0;
    break;
  case POPS_CHEAT_SPR:
    base = mem->spr, limit = mem->spr ? 0x4000u : 0, ee_base = POPS_CHEAT_SPR_ADDR;
    break;
  default:
    base = mem->ps1spr, limit = mem->ps1spr ? 0x400u : 0, ee_base = POPS_CHEAT_PS1SPR_ADDR;
    break;
  }
  if (addr >= limit || limit - addr < size)
    return 0;
  *at = base + addr;
  *ee_addr = ee_base + addr;
  return 1;
}

void pops_resident_cheat_run(const PopsCheatMemory *mem, const PopsCheatEntry *cheats,
                             uint16_t count) {
  uintptr_t ram = mem->ps1;
  /* POPStarter's compare registers. */
  int64_t k0 = 0, k1 = 0;
  uint16_t i = 0;
  if (!ram)
    return;
  while (i < count) {
    const PopsCheatEntry *e = &cheats[i];
    uint32_t addr = e->address & POPS_CHEAT_ADDR_MASK;
    uint32_t skip = e->skip ? e->skip : 1;
    uint8_t type = e->type;
    uint32_t val = e->value;

    if (POPS_CHEAT_IS_PS2(type)) {
      uintptr_t at;
      uint32_t ee_addr;
      if (!cheat_ps2_place(mem, e, &at, &ee_addr)) {
        i += e->cond ? 2 : 1; /* out of reach: the code and what it gates */
        continue;
      }
      if (e->cond == POPS_CHEAT_COND_NONE) {
        if ((type & 3u) == 0)
          CHEAT_U8(at) = (uint8_t)val;
        else if ((type & 3u) == 1)
          CHEAT_U16(at) = (uint16_t)val;
        else
          CHEAT_U32(at) = val;
        /* lui k0, (address + 0x8000) >> 16; lui/ori k1, value */
        k0 = sext32((ee_addr + 0x8000u) & 0xFFFF0000u);
        k1 = sext32(val);
        i++;
        continue;
      }
      /* lb/lh/lw k0 (signed), lui/ori k1, value; bne (EQ) or beq (NE)
       * over the next code. */
      if ((type & 3u) == 0)
        k0 = (int8_t)CHEAT_U8(at);
      else if ((type & 3u) == 1)
        k0 = (int16_t)CHEAT_U16(at);
      else
        k0 = (int32_t)CHEAT_U32(at);
      k1 = sext32(val);
      int holds = e->cond == POPS_CHEAT_COND_EQ ? k0 == k1 : k0 != k1;
      i += holds ? 1 : 2;
      continue;
    }

    if (type == POPS_CHEAT_BNE) {
      i += k0 != k1 ? 1 + skip : 1;
      continue;
    }

    if (type == POPS_CHEAT_LOAD16) {
      /* lh k0 and addiu k1, both sign-extended, so they compare equal
       * exactly when the halves match. */
      k0 = addr + 2 <= POPS_PS1_RAM_SIZE ? (int16_t)CHEAT_U16(ram + (addr & ~1U)) : 0;
      k1 = (int16_t)(uint16_t)val;
      i++;
      continue;
    }

    if (type == 0xC0) {
      /* POPStarter loads the half signed and the value unsigned, so a
       * master code value of 0x8000 or more never matches. */
      if (addr + 2 > POPS_PS1_RAM_SIZE)
        return;
      k0 = (int16_t)CHEAT_U16(ram + (addr & ~1U));
      k1 = (uint16_t)val;
      if (k0 != k1)
        return;
      i++;
      continue;
    }

    if (type >= 0xD0 && type <= 0xD3) {
      int cond = 0;
      if (addr + 2 <= POPS_PS1_RAM_SIZE) {
        uint16_t cur = CHEAT_U16(ram + (addr & ~1U));
        uint16_t v16 = (uint16_t)val;
        if (type == 0xD0)
          cond = (cur == v16);
        else if (type == 0xD1)
          cond = (cur != v16);
        else if (type == 0xD2)
          cond = (cur < v16);
        else
          cond = (cur > v16);
      }
      i += cond ? 1 : 1 + skip;
      continue;
    }

    if (type == 0xE0 || type == 0xE1) {
      int cond = 0;
      if (addr + 1 <= POPS_PS1_RAM_SIZE) {
        uint8_t cur = CHEAT_U8(ram + addr);
        cond = (type == 0xE0) ? (cur == (uint8_t)val) : (cur != (uint8_t)val);
      }
      i += cond ? 1 : 1 + skip;
      continue;
    }

    if (type == 0x50) {
      /* $5000XXYY ZZZZ: the next write XX times, the address up YY bytes
       * and the value up ZZZZ each time, copied with POPStarter's two bugs.
       * Address: it keeps the low half as a running sum and adds another
       * 64 KB to the high half on every step once that sum passes 0xFFFF,
       * so after crossing a 64 KB boundary each later write lands 64 KB
       * further up. Value: it builds "ori k1,zero,value" from the running
       * sum; from 0x20000 up the excess changes the instruction's register
       * field, k1 keeps its last value and the store repeats it. */
      if (i + 1 < count) {
        const PopsCheatEntry *t = &cheats[i + 1];
        uint32_t a16 = e->address & 0xFFFFu;
        uint32_t times = (a16 >> 8) & 0xFF, step = a16 & 0xFF;
        uint32_t base = t->address & POPS_CHEAT_ADDR_MASK;
        uint32_t high = base & ~UINT32_C(0xFFFF), low = base & 0xFFFF;
        uint32_t sum = t->value & 0xFFFFu;
        uint16_t kv = (uint16_t)sum;
        for (uint32_t k = 0; k < times; ++k) {
          if (k) {
            low += step;
            if (low > 0xFFFF)
              high += 0x10000;
            sum += val & 0xFFFFu;
          }
          if (sum < 0x20000)
            kv = (uint16_t)sum;
          uint32_t at = high + (low & 0xFFFF);
          cheat_write(mem, t->type, at, kv);
          k0 = 0x01000000 + (int64_t)at;
          k1 = kv;
        }
        i += 2;
      } else {
        i++;
      }
      continue;
    }

    cheat_write(mem, type, addr, val);
    k0 = 0x01000000 + (int64_t)addr;
    k1 = type == POPS_CHEAT_W32 ? (int64_t)val : (int64_t)(uint16_t)val;
    i++;
  }
}

void pops_resident_cheat_pass(uint8_t *ram, const PopsCheatEntry *cheats, uint16_t count) {
  PopsCheatMemory mem = {(uintptr_t)ram, 0, 0, 0, 0};
  pops_resident_cheat_run(&mem, cheats, count);
}

int pops_safe_mode_blocks(const uint8_t *ram, uint8_t safe_mode) {
  if (safe_mode & POPS_SAFE_MODE_BOOT)
    return *(const volatile uint32_t *)(ram + POPS_SAFE_MODE_BOOT_ADDR) == POPS_SAFE_MODE_BOOT_VALUE;
  if (safe_mode & POPS_SAFE_MODE_2)
    return *(const volatile uint32_t *)(ram + POPS_SAFE_MODE_2_ADDR) == POPS_SAFE_MODE_2_VALUE;
  return 0;
}

int pops_resident_frame_mem(PopsResidentConfig *cfg, const PopsCheatMemory *mem) {
  if (cfg->frame != UINT32_MAX)
    cfg->frame++;
  if (!(cfg->flags & POPS_RES_F_CHEATS) || !mem->ps1 || !cfg->cheat_count)
    return 0;
  if (pops_safe_mode_blocks((const uint8_t *)mem->ps1, (uint8_t)cfg->safe_mode))
    return 0;
  pops_resident_cheat_run(mem, cfg->cheats, cfg->cheat_count);
  return 1;
}

int pops_resident_frame(PopsResidentConfig *cfg, uint8_t *ram) {
  PopsCheatMemory mem = {(uintptr_t)ram, 0, 0, 0, 0};
  return pops_resident_frame_mem(cfg, &mem);
}

void pops_resident_pad_ids(const PopsResidentConfig *cfg, uint8_t *state) {
  for (unsigned port = 0; port < 2; ++port) {
    if (cfg->pad_override & (1u << port))
      *(volatile uint8_t *)(state + port * POPS_PAD_STATE_STRIDE + POPS_PAD_STATE_ID) =
          cfg->pad_id[port];
  }
}

/* Raw pad data: [2..3] buttons, active low (bit 4 up, 5 right, 6 down,
 * 7 left); [6] left stick X, [7] left stick Y (0 = left/up); [8..11]
 * pressure of right, left, up, down (0 = released). */
static uint8_t d2ls_pressure_low(uint8_t axis) {
  return axis < 0x7f ? (uint8_t)((0x7f - axis) << 1) : 0;
}

static uint8_t d2ls_pressure_high(uint8_t axis) {
  return axis > 0x80 ? (uint8_t)((axis - 0x80) << 1) : 0;
}

static uint8_t d2ls_axis(uint8_t low, uint8_t high) {
  if (high)
    return (uint8_t)(0x80 + (high >> 1));
  if (low)
    return (uint8_t)(0x7f - (low >> 1));
  return 0x80;
}

void pops_resident_d2ls(uint8_t *pad, uint32_t bytes) {
  if (bytes < 8)
    return;
  uint8_t lx = pad[6], ly = pad[7];
  uint8_t right = 0, left = 0, up = 0, down = 0;
  if (bytes >= 12) {
    right = pad[8];
    left = pad[9];
    up = pad[10];
    down = pad[11];
  }

  uint8_t dpad = 0xf0; /* released */
  if (ly < 0x41)
    dpad &= (uint8_t)~0x10;
  if (lx >= 0xbf)
    dpad &= (uint8_t)~0x20;
  if (ly >= 0xbf)
    dpad &= (uint8_t)~0x40;
  if (lx < 0x41)
    dpad &= (uint8_t)~0x80;
  pad[2] = (uint8_t)((pad[2] & 0x0f) | dpad);

  pad[8] = d2ls_pressure_high(lx);
  pad[9] = d2ls_pressure_low(lx);
  pad[10] = d2ls_pressure_low(ly);
  pad[11] = d2ls_pressure_high(ly);
  pad[6] = d2ls_axis(left, right);
  pad[7] = d2ls_axis(up, down);
}

/* POPStarter's always-live block (0x232790..0x232cb0), statement for
 * statement; its five empty slots between the emode checks and the lid
 * (0x2327d0..0x2327f0) do nothing in r13 and have no counterpart here. */
#define HOTKEY_BUTTONS(mem) (*(volatile uint16_t *)((mem)->pad + 2))

void pops_resident_hotkeys(PopsResidentConfig *cfg, const PopsHotkeyMemory *mem) {
  volatile uint8_t *emode = (volatile uint8_t *)mem->emode;
  volatile uint16_t *lid = (volatile uint16_t *)mem->lid;
  uint16_t buttons = HOTKEY_BUTTONS(mem);
  if (buttons == POPS_COMBO_EMODE_0)
    *emode = 0;
  else if (buttons == POPS_COMBO_EMODE_1)
    *emode = 1;

  if (HOTKEY_BUTTONS(mem) == POPS_COMBO_LID_OPEN)
    *lid = POPS_LID_OPEN;
  *(volatile uint8_t *)(mem->pad + POPS_PAD_STATE_FLAG) = 1;
  *(volatile uint8_t *)(mem->pad + POPS_PAD_STATE_STRIDE + POPS_PAD_STATE_FLAG) = 1;

  /* Into POPS's code, without flushing the caches, as the original does. */
  if (HOTKEY_BUTTONS(mem) == POPS_COMBO_SCANLINES_ON)
    *(volatile uint32_t *)mem->scanlines = POPS_SCANLINES_ON;
  if (HOTKEY_BUTTONS(mem) == POPS_COMBO_SCANLINES_OFF)
    *(volatile uint32_t *)mem->scanlines = POPS_SCANLINES_OFF;

  if (HOTKEY_BUTTONS(mem) == POPS_COMBO_LID_CLOSE && *lid == POPS_LID_OPEN) {
    *lid = POPS_LID_CLOSED;
    mem->cd_init((const char *)cfg->disc_slot[cfg->disc_selected & (POPS_MAX_DISCS - 1)]);
  }

  if (HOTKEY_BUTTONS(mem) == POPS_COMBO_DISC_1)
    cfg->disc_selected = 0;
  if (HOTKEY_BUTTONS(mem) == POPS_COMBO_DISC_2)
    cfg->disc_selected = 1;
  if (HOTKEY_BUTTONS(mem) == POPS_COMBO_DISC_3)
    cfg->disc_selected = 2;
  if (HOTKEY_BUTTONS(mem) == POPS_COMBO_DISC_4)
    cfg->disc_selected = 3;

  /* An empty slot (first word zero) takes POPS's boot path, 0x60 bytes. */
  for (unsigned slot = 0; slot < POPS_MAX_DISCS; ++slot) {
    volatile uint32_t *to = (volatile uint32_t *)cfg->disc_slot[slot];
    const volatile uint32_t *from = (const volatile uint32_t *)mem->boot_path;
    if (*to)
      continue;
    for (unsigned word = 0; word < POPS_DISC_SLOT_SIZE / 4; ++word)
      to[word] = from[word];
  }

  /* $NOVMC0 / $NOVMC1 (0x232c90 / 0x232ca0, branches their handlers turn
   * on): a byte store, so the rest of the state word stays. */
  if (cfg->flags & POPS_RES_F_NOVMC0)
    *(volatile uint8_t *)mem->card_state = 0;
  if (cfg->flags & POPS_RES_F_NOVMC1)
    *(volatile uint8_t *)(mem->card_state + POPS_CARD_STATE_STRIDE) = 0;
}

#define TIMING_WORD(addr) (*(volatile uint32_t *)(addr))

static void timing_set(volatile uint32_t *word, uint32_t value, uintptr_t copy, int save) {
  *word = value;
  if (save)
    TIMING_WORD(copy) = value;
}

void pops_resident_timings(PopsResidentConfig *cfg, uintptr_t ee, uintptr_t spr) {
  if (!(cfg->flags & POPS_RES_F_TIMINGS))
    return;
  int save = (cfg->flags & POPS_RES_F_TIMINGS_SAVE) != 0;
  volatile uint32_t *a = &TIMING_WORD(ee + POPS_TIMING_A_ADDR);
  volatile uint32_t *b = &TIMING_WORD(spr + POPS_TIMING_B_OFFSET);
  volatile uint32_t *t = &TIMING_WORD(spr + POPS_TIMING_C_OFFSET);
  uintptr_t copy = ee + POPS_TIMING_SAVE_ADDR;

  if (!cfg->timings_ready) {
    if (!TIMING_WORD(ee + POPS_VMC0_IMAGE_ADDR))
      return;
    if (*(volatile uint16_t *)copy == (uint16_t)POPS_TIMING_SIGNATURE) {
      *a = TIMING_WORD(copy + 4);
      *b = TIMING_WORD(copy + 8);
      *t = TIMING_WORD(copy + 12);
    } else if (save) {
      TIMING_WORD(copy) = POPS_TIMING_SIGNATURE;
      TIMING_WORD(copy + 4) = *a;
      TIMING_WORD(copy + 8) = *b;
      TIMING_WORD(copy + 12) = *t;
    }
    cfg->timings_ready = 1;
    return;
  }

  uint16_t pad = *(volatile uint16_t *)(ee + POPS_PAD_STATE_ADDR + 2);
  if (pad == POPS_TIMING_PAD_L1)
    timing_set(b, *b + 1, copy + 8, save);
  else if (pad == POPS_TIMING_PAD_L2)
    timing_set(b, *b - 1, copy + 8, save);
  else if (pad == POPS_TIMING_PAD_R1)
    timing_set(t, *t + 1, copy + 12, save);
  else if (pad == POPS_TIMING_PAD_R2)
    timing_set(t, *t - 1, copy + 12, save);
  else {
    pad = *(volatile uint16_t *)(ee + POPS_PAD_STATE_ADDR + POPS_PAD_STATE_STRIDE + 2);
    if (pad == POPS_TIMING_PAD_L1)
      timing_set(a, *a + 1, copy + 4, save);
    else if (pad == POPS_TIMING_PAD_L2)
      timing_set(a, *a - 1, copy + 4, save);
    else if (pad == POPS_TIMING_PAD_R1)
      timing_set(a, *a + 0x10, copy + 4, save);
    else if (pad == POPS_TIMING_PAD_R2)
      timing_set(a, *a - 0x10, copy + 4, save);
  }
}

#ifdef POPS_RESIDENT_IMAGE

typedef int (*PopsIntcHandler)(int cause);
void pops_resident_pad_read_entry(void);
void pops_resident_pad_read_exit(void);
void pops_resident_pad_read_done(int32_t bytes);

int pops_resident_vblank(int cause);
void pops_resident_gp1(void);
void pops_resident_gp1_work(void);
void pops_resident_display(void);
void pops_resident_progressive(void);
extern char _pops_resident_file_end[];
extern char _pops_resident_end[];

/* Filled by the launcher after the image is copied (lives in .bss). */
PopsResidentConfig pops_resident_config;
_Static_assert(offsetof(PopsResidentConfig, gs_display) == 0, "display entry ABI");
/* POPS DMAs the disc name straight from a slot (sceSifCallRpc, 0x80 bytes). */
_Static_assert(offsetof(PopsResidentConfig, disc_slot) % 16 == 0, "disc slot DMA alignment");
_Static_assert(offsetof(PopsResidentConfig, disc_tail) ==
               offsetof(PopsResidentConfig, disc_slot) + sizeof(((PopsResidentConfig *)0)->disc_slot),
               "disc slot DMA tail");

/* Independent stackless bridge for POPS's mid-function load. v0 and a1 are
 * the only clobbers; v0 is restored before the stock continuation. No gp,
 * stack, callback or compiler-generated function prologue is involved. */
__asm__(".set push\n.set noreorder\n.text\n.align 2\n"
        ".globl pops_resident_display\npops_resident_display:\n"
        "lui $v0, %hi(pops_resident_config)\n"
        "ld $a1, %lo(pops_resident_config)($v0)\n"
        "j 0x0021a098\n"
        "lui $v0, 0x1200\n.set pop\n");

/* Saved by the pad read entry stub: the state block being filled. */
uint32_t pops_resident_pad_buffer;

/* $D2LS stubs around POPS's pad read (0x00237798). The entry replaces
 * addiu $v1,$zero,0x70, whose value it restores, and only borrows $v1. The
 * exit replaces the final jr $ra after its delay slot has popped the frame,
 * keeps the result in $v0, and returns to POPS's caller. */
__asm__(".set push\n.set noreorder\n.text\n.align 2\n"
        ".globl pops_resident_pad_read_entry\npops_resident_pad_read_entry:\n"
        "lui $v1, %hi(pops_resident_pad_buffer)\n"
        "sw $a2, %lo(pops_resident_pad_buffer)($v1)\n"
        "j 0x002377a4\n"
        "addiu $v1, $zero, 0x70\n"
        ".globl pops_resident_pad_read_exit\npops_resident_pad_read_exit:\n"
        "addiu $sp, $sp, -16\n"
        "sd $ra, 0($sp)\n"
        "sd $v0, 8($sp)\n"
        "jal pops_resident_pad_read_done\n"
        "move $a0, $v0\n"
        "ld $ra, 0($sp)\n"
        "ld $v0, 8($sp)\n"
        "jr $ra\n"
        "addiu $sp, $sp, 16\n.set pop\n");

void pops_resident_pad_read_done(int32_t bytes) {
  uint32_t buf = pops_resident_pad_buffer;
  if (!(pops_resident_config.flags & POPS_RES_F_D2LS) || bytes <= 0)
    return;
  if (buf != POPS_PAD_STATE_ADDR && buf != POPS_PAD_STATE_ADDR + POPS_PAD_STATE_STRIDE)
    return;
  pops_resident_d2ls((uint8_t *)buf, (uint32_t)bytes);
}

/* Widescreen stubs inside POPS's GTE perspective transform. They are
 * jumped to in place of a store, after its delay slot has run, and use only
 * $v0, $v1 and LO/HI (dead at both sites). x * 75 is formed from shifts so
 * the product wraps to 32 bits the same way a 32-bit multiply does; the
 * quotient truncates toward zero. A zero divisor leaves x unscaled.
 *   scale:  x = x * 75 / divisor, store MAC1, resume at 0x2089b0
 *   divide: x = x / divisor (the $EYEFINITY entry), same store and resume
 *   ultra:  x = x * 75 / divisor at the IR1 store; like the original, the
 *           result goes to MAC1 (0x64) and the stock IR1 store is not made;
 *           resume at 0x208a34.
 * POPS's $t0 is register 8 (o32 naming); this toolchain's EABI calls $8
 * "a4", so the stubs name it by number. */
#define GTE_DIV_STR2(x) #x
#define GTE_DIV_STR(x) GTE_DIV_STR2(x)
#define GTE_DIVISOR "pops_resident_config+" GTE_DIV_STR(POPS_RESIDENT_GTE_DIVISOR_OFFSET)
_Static_assert(offsetof(PopsResidentConfig, gte_divisor) == POPS_RESIDENT_GTE_DIVISOR_OFFSET,
               "widescreen stub ABI");
#define GTE_TIMES_75 \
  "sll $v0, $8, 6\n" \
  "sll $v1, $8, 3\n" \
  "addu $v0, $v0, $v1\n" \
  "sll $v1, $8, 1\n" \
  "addu $v0, $v0, $v1\n" \
  "addu $8, $v0, $8\n"
#define GTE_DIVIDE(label) \
  "lui $v1, %hi(" GTE_DIVISOR ")\n" \
  "lbu $v1, %lo(" GTE_DIVISOR ")($v1)\n" \
  "beqz $v1, " label "\n" \
  "nop\n" \
  "div $zero, $8, $v1\n" \
  "mflo $8\n"
void pops_resident_gte_scale(void);
void pops_resident_gte_divide(void);
void pops_resident_gte_ultra(void);
__asm__(".set push\n.set noreorder\n.text\n.align 2\n"
        ".globl pops_resident_gte_scale\npops_resident_gte_scale:\n"
        GTE_TIMES_75
        ".globl pops_resident_gte_divide\npops_resident_gte_divide:\n"
        GTE_DIVIDE("1f")
        "1:\n"
        "j 0x002089b0\n"
        "sw $8, 0x64($a0)\n"
        ".globl pops_resident_gte_ultra\npops_resident_gte_ultra:\n"
        GTE_TIMES_75
        GTE_DIVIDE("2f")
        "2:\n"
        "j 0x00208a34\n"
        "sw $8, 0x64($a0)\n"
        ".set pop\n");

/* POPStarter's recompiler hook and $RECOMPILER_ADDON_0..4,
 * pops_resident_recompiler.S. It reads the flags by their offset. */
void pops_resident_recompiler(void);
void pops_resident_recompiler_addon3_206318(void);
void pops_resident_recompiler_addon3_205d1c(void);
void pops_resident_recompiler_addon4_206318(void);
void pops_resident_recompiler_addon4_205d1c(void);
_Static_assert(offsetof(PopsResidentConfig, flags) == POPS_RESIDENT_FLAGS_OFFSET,
               "recompiler hook ABI");
_Static_assert(sizeof(((PopsResidentConfig *)0)->flags) == 4, "recompiler hook ABI");
/* Where the ADDON_3/4 code keeps $k0, $k1 and $at (shared) and the $gp the
 * 0x205d1c code finds, 16 bytes each for sq/lq. Zero at install, so $gp is
 * zero after the 0x206318 code until the 0x205d1c code has run once, as in
 * the original. */
uint64_t pops_resident_recompiler_save[8] __attribute__((aligned(16)));

/* POPStarter's always-on guards, pops_resident_guards.S. */
void pops_resident_guard_21c58c(void);
void pops_resident_guard_21c768(void);
void pops_resident_guard_2082a0(void);
void pops_resident_guard_204ae0(void);
void pops_resident_guard_204178(void);
void pops_resident_guard_204160(void);
void pops_resident_guard_202250(void);
void pops_resident_guard_21c5dc(void);
void pops_resident_guard_21c5a8(void);

__attribute__((section(".resident.head"), used))
const PopsResidentHeader pops_resident_header = {
  POPS_RESIDENT_MAGIC,
  POPS_RESIDENT_VERSION,
  sizeof(PopsResidentHeader),
  (uint32_t)_pops_resident_file_end - POPS_RESIDENT_BASE,
  (uint32_t)_pops_resident_end - POPS_RESIDENT_BASE,
  (uint32_t)pops_resident_vblank,
  (uint32_t)&pops_resident_config,
  (uint32_t)pops_resident_display,
  (uint32_t)pops_resident_progressive,
  (uint32_t)pops_resident_pad_read_entry,
  (uint32_t)pops_resident_pad_read_exit,
  (uint32_t)pops_resident_gte_scale,
  (uint32_t)pops_resident_gte_divide,
  (uint32_t)pops_resident_gte_ultra,
  (uint32_t)pops_resident_gp1,
  {
    (uint32_t)pops_resident_guard_21c58c,
    (uint32_t)pops_resident_guard_21c768,
    (uint32_t)pops_resident_guard_2082a0,
    (uint32_t)pops_resident_guard_204ae0,
    (uint32_t)pops_resident_guard_204178,
    (uint32_t)pops_resident_guard_204160,
    (uint32_t)pops_resident_guard_202250,
    (uint32_t)pops_resident_guard_21c5dc,
    (uint32_t)pops_resident_guard_21c5a8,
  },
  (uint32_t)pops_resident_recompiler,
  {
    (uint32_t)pops_resident_recompiler_addon3_206318,
    (uint32_t)pops_resident_recompiler_addon3_205d1c,
    (uint32_t)pops_resident_recompiler_addon4_206318,
    (uint32_t)pops_resident_recompiler_addon4_205d1c,
  },
};

/* No longer hooked by the launcher: everything it did now runs from the GP1
 * entry below, where POPStarter does it. Kept so the header stays valid. */
int pops_resident_vblank(int cause) {
  return ((PopsIntcHandler)pops_resident_config.pops_vblank)(cause);
}

/* Where POPStarter runs its checks and cheat code: POPS's GP1 write path
 * (0x21a568, reached from the GPU register handler 0x20b4d8 when the game
 * writes 0x1f801814) posts the command and, when interrupts are enabled,
 * reaches the nop at 0x21a63c. POPStarter puts "jal 0x239490" there;
 * launcHER puts "jal pops_resident_gp1". The di after it runs in the delay
 * slot, as in the original, so this code runs with interrupts disabled, on
 * the POPS thread's own stack. POPS still needs v1 (0x10000) afterwards;
 * every caller-saved register, HI and LO are kept so POPS sees no change.
 * The original keeps only k0/k1, which its code alone uses. */
__asm__(".set push\n.set noreorder\n.set noat\n.text\n.align 2\n"
        ".globl pops_resident_gp1\npops_resident_gp1:\n"
        "addiu $sp, $sp, -0xa0\n"
        "sd $1, 0x00($sp)\n"
        "sd $2, 0x08($sp)\n"
        "sd $3, 0x10($sp)\n"
        "sd $4, 0x18($sp)\n"
        "sd $5, 0x20($sp)\n"
        "sd $6, 0x28($sp)\n"
        "sd $7, 0x30($sp)\n"
        "sd $8, 0x38($sp)\n"
        "sd $9, 0x40($sp)\n"
        "sd $10, 0x48($sp)\n"
        "sd $11, 0x50($sp)\n"
        "sd $12, 0x58($sp)\n"
        "sd $13, 0x60($sp)\n"
        "sd $14, 0x68($sp)\n"
        "sd $15, 0x70($sp)\n"
        "sd $24, 0x78($sp)\n"
        "sd $25, 0x80($sp)\n"
        "sd $31, 0x88($sp)\n"
        "mfhi $8\n"
        "mflo $9\n"
        "sd $8, 0x90($sp)\n"
        "jal pops_resident_gp1_work\n"
        "sd $9, 0x98($sp)\n"
        "ld $8, 0x90($sp)\n"
        "ld $9, 0x98($sp)\n"
        "mthi $8\n"
        "mtlo $9\n"
        "ld $1, 0x00($sp)\n"
        "ld $2, 0x08($sp)\n"
        "ld $3, 0x10($sp)\n"
        "ld $4, 0x18($sp)\n"
        "ld $5, 0x20($sp)\n"
        "ld $6, 0x28($sp)\n"
        "ld $7, 0x30($sp)\n"
        "ld $8, 0x38($sp)\n"
        "ld $9, 0x40($sp)\n"
        "ld $10, 0x48($sp)\n"
        "ld $11, 0x50($sp)\n"
        "ld $12, 0x58($sp)\n"
        "ld $13, 0x60($sp)\n"
        "ld $14, 0x68($sp)\n"
        "ld $15, 0x70($sp)\n"
        "ld $24, 0x78($sp)\n"
        "ld $25, 0x80($sp)\n"
        "ld $31, 0x88($sp)\n"
        "jr $31\n"
        "addiu $sp, $sp, 0xa0\n"
        ".set pop\n");

/* In POPStarter's chain order: its always-live block (0x232790..0x232cb0:
 * pad hotkeys, in-game disc swap, slot copies, the $NOVMC0/1 stores), the
 * controller ID stores (0x232cb0..), the built-in list's breakpoint handler
 * (slot 0x232d08), the $SET_TIMINGS check (0x238a90), the second LibCrypt
 * code (slot 0x238d00, code at 0x239780), the game-fix code (slot
 * 0x2397d8), then the cheat code
 * (0x2397e8). The three built-in pieces are the original's own MIPS,
 * copied by the launcher; they use k0/k1 (two of them t6) and return with
 * jr ra, and gp is still POPS's, as in the original, since nothing here
 * changes it. */
typedef void (*PopsBuiltinCode)(void);
void pops_resident_gp1_work(void) {
  PopsResidentConfig *cfg = &pops_resident_config;
  uint32_t base = *(volatile uint32_t *)cfg->ram_base_ptr;
  PopsHotkeyMemory keys = {POPS_PAD_STATE_ADDR, POPS_EMODE_ADDR, POPS_LID_ADDR,
                           POPS_SCANLINES_ADDR, POPS_BOOT_PATH_ADDR, POPS_CARD_STATE_ADDR,
                           (int (*)(const char *))POPS_CD_INIT_ADDR};
  pops_resident_hotkeys(cfg, &keys);
  if (cfg->flags & POPS_RES_F_PAD_ID)
    pops_resident_pad_ids(cfg, (uint8_t *)POPS_PAD_STATE_ADDR);
  /* The original's reset block right after its controller-ID stores: while
   * port 0 reads exactly the combo, the PS1 jump word (scratchpad 0) is set
   * to the reset vector. Always on, as in its resident block. */
  if (*(volatile uint16_t *)(POPS_PAD_STATE_ADDR + 2) == POPS_RESET_COMBO)
    *(volatile uint32_t *)POPS_SCRATCHPAD_ADDR = cfg->reset_vector;
  if (cfg->flags & POPS_RES_F_BREAK_CALL)
    ((PopsBuiltinCode)POPS_BUILTIN_BREAK_ADDR)();
  pops_resident_timings(cfg, 0, POPS_SCRATCHPAD_ADDR);
  if (cfg->flags & POPS_RES_F_LIBCRYPT2)
    ((PopsBuiltinCode)cfg->libcrypt2_code)();
  if (cfg->flags & POPS_RES_F_FIX_CALL)
    ((PopsBuiltinCode)POPS_BUILTIN_FIX_ADDR)();
  PopsCheatMemory mem = {base, 0, 0x02000000u, POPS_CHEAT_SPR_ADDR, POPS_CHEAT_PS1SPR_ADDR};
  pops_resident_frame_mem(cfg, &mem);
}

#endif
