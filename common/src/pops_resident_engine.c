/* launcHER resident code for POPS (see pops_resident.h).
 *
 * Built twice: into the launcher and host tests for the per-frame logic, and
 * on its own with POPS_RESIDENT_IMAGE as a flat image linked at
 * POPS_RESIDENT_BASE (pops_resident.ld). The image build is freestanding:
 * no libc, no $gp (-G0), small stack, because the entry runs as an EE
 * interrupt handler while POPS owns the machine. */

#include "pops_resident.h"

static void cheat_write(uint8_t *ram, uint8_t type, uint32_t addr, uint16_t val) {
  if (type == 0x80 || type == 0x10) {
    if (addr + 2 <= POPS_PS1_RAM_SIZE)
      *(volatile uint16_t *)(ram + (addr & ~1U)) = val;
  } else if (type == 0x30 || type == 0x20) {
    if (addr + 1 <= POPS_PS1_RAM_SIZE)
      *(volatile uint8_t *)(ram + addr) = (uint8_t)val;
  }
}

void pops_resident_cheat_pass(uint8_t *ram, const PopsCheatEntry *cheats, uint16_t count) {
  uint16_t i = 0;
  while (i < count) {
    uint32_t addr = cheats[i].address & POPS_CHEAT_ADDR_MASK;
    uint32_t skip = cheats[i].address >> POPS_CHEAT_SKIP_SHIFT;
    uint8_t type = cheats[i].type;
    uint16_t val = cheats[i].value;
    if (!skip)
      skip = 1;

    if (type == 0xC0) {
      /* POPStarter loads the half signed and the value unsigned, so a
       * master code value of 0x8000 or more never matches. */
      if (val >= 0x8000 || addr + 2 > POPS_PS1_RAM_SIZE ||
          *(volatile uint16_t *)(ram + (addr & ~1U)) != val)
        return;
      i++;
      continue;
    }

    if (type >= 0xD0 && type <= 0xD3) {
      int cond = 0;
      if (addr + 2 <= POPS_PS1_RAM_SIZE) {
        uint16_t cur = *(volatile uint16_t *)(ram + (addr & ~1U));
        if (type == 0xD0)
          cond = (cur == val);
        else if (type == 0xD1)
          cond = (cur != val);
        else if (type == 0xD2)
          cond = (cur < val);
        else
          cond = (cur > val);
      }
      i += cond ? 1 : 1 + skip;
      continue;
    }

    if (type == 0xE0 || type == 0xE1) {
      int cond = 0;
      if (addr + 1 <= POPS_PS1_RAM_SIZE) {
        uint8_t cur = *(volatile uint8_t *)(ram + addr);
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
        uint32_t times = (addr >> 8) & 0xFF, step = addr & 0xFF;
        uint32_t base = t->address & POPS_CHEAT_ADDR_MASK;
        uint32_t high = base & ~UINT32_C(0xFFFF), low = base & 0xFFFF;
        uint32_t sum = t->value;
        uint16_t k1 = t->value;
        for (uint32_t k = 0; k < times; ++k) {
          if (k) {
            low += step;
            if (low > 0xFFFF)
              high += 0x10000;
            sum += val;
          }
          if (sum < 0x20000)
            k1 = (uint16_t)sum;
          cheat_write(ram, t->type, high + (low & 0xFFFF), k1);
        }
        i += 2;
      } else {
        i++;
      }
      continue;
    }

    cheat_write(ram, type, addr, val);
    i++;
  }
}

int pops_safe_mode_blocks(const uint8_t *ram, uint8_t safe_mode) {
  if (safe_mode & POPS_SAFE_MODE_BOOT)
    return *(const volatile uint32_t *)(ram + POPS_SAFE_MODE_BOOT_ADDR) == POPS_SAFE_MODE_BOOT_VALUE;
  if (safe_mode & POPS_SAFE_MODE_2)
    return *(const volatile uint32_t *)(ram + POPS_SAFE_MODE_2_ADDR) == POPS_SAFE_MODE_2_VALUE;
  return 0;
}

int pops_resident_frame(PopsResidentConfig *cfg, uint8_t *ram) {
  if (cfg->frame != UINT32_MAX)
    cfg->frame++;
  if (!(cfg->flags & POPS_RES_F_CHEATS) || !ram || !cfg->cheat_count)
    return 0;
  if (pops_safe_mode_blocks(ram, (uint8_t)cfg->safe_mode))
    return 0;
  pops_resident_cheat_pass(ram, cfg->cheats, cfg->cheat_count);
  return 1;
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

/* In POPStarter's chain order: the controller ID stores (0x232cb0..), then
 * the $SET_TIMINGS check (0x238a90), then the cheat code (0x2397e8). */
void pops_resident_gp1_work(void) {
  PopsResidentConfig *cfg = &pops_resident_config;
  uint32_t base = *(volatile uint32_t *)cfg->ram_base_ptr;
  if (cfg->flags & POPS_RES_F_PAD_ID)
    pops_resident_pad_ids(cfg, (uint8_t *)POPS_PAD_STATE_ADDR);
  pops_resident_timings(cfg, 0, POPS_SCRATCHPAD_ADDR);
  pops_resident_frame(cfg, (uint8_t *)base);
}

#endif
