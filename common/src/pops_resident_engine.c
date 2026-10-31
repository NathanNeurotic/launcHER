/* launcHER resident code for POPS (see pops_resident.h).
 *
 * Built twice: into the launcher and host tests for the per-frame logic, and
 * on its own with POPS_RESIDENT_IMAGE as a flat image linked at
 * POPS_RESIDENT_BASE (pops_resident.ld). The image build is freestanding:
 * no libc, no $gp (-G0), small stack, because the entry runs as an EE
 * interrupt handler while POPS owns the machine. */

#include "pops_resident.h"

void pops_resident_cheat_pass(uint8_t *ram, const PopsCheatEntry *cheats, uint16_t count) {
  uint16_t i = 0;
  while (i < count) {
    uint32_t addr = cheats[i].address & 0x001FFFFF;
    uint8_t type = cheats[i].type;
    uint16_t val = cheats[i].value;

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
      i += cond ? 1 : 2;
      continue;
    }

    if (type == 0xE0 || type == 0xE1) {
      int cond = 0;
      if (addr + 1 <= POPS_PS1_RAM_SIZE) {
        uint8_t cur = *(volatile uint8_t *)(ram + addr);
        cond = (type == 0xE0) ? (cur == (uint8_t)val) : (cur != (uint8_t)val);
      }
      i += cond ? 1 : 2;
      continue;
    }

    if (type == 0x80 || type == 0x10) {
      if (addr + 2 <= POPS_PS1_RAM_SIZE)
        *(volatile uint16_t *)(ram + (addr & ~1U)) = val;
    } else if (type == 0x30 || type == 0x20) {
      if (addr + 1 <= POPS_PS1_RAM_SIZE)
        *(volatile uint8_t *)(ram + addr) = (uint8_t)val;
    }
    i++;
  }
}

int pops_resident_frame(PopsResidentConfig *cfg, uint8_t *ram) {
  if (cfg->frame != UINT32_MAX)
    cfg->frame++;
  if (!(cfg->flags & POPS_RES_F_CHEATS) || !ram || !cfg->cheat_count)
    return 0;
  if (cfg->frame <= cfg->safe_delay)
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

#ifdef POPS_RESIDENT_IMAGE

typedef int (*PopsIntcHandler)(int cause);
void pops_resident_pad_read_entry(void);
void pops_resident_pad_read_exit(void);
void pops_resident_pad_read_done(int32_t bytes);

int pops_resident_vblank(int cause);
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
};

int pops_resident_vblank(int cause) {
  PopsResidentConfig *cfg = &pops_resident_config;
  uint32_t base = *(volatile uint32_t *)cfg->ram_base_ptr;
  if (cfg->flags & POPS_RES_F_PAD_ID)
    pops_resident_pad_ids(cfg, (uint8_t *)POPS_PAD_STATE_ADDR);
  pops_resident_frame(cfg, (uint8_t *)base);
  return ((PopsIntcHandler)cfg->pops_vblank)(cause);
}

#endif
