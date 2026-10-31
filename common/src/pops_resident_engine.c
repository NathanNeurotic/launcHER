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

#ifdef POPS_RESIDENT_IMAGE

typedef int (*PopsIntcHandler)(int cause);

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
};

int pops_resident_vblank(int cause) {
  PopsResidentConfig *cfg = &pops_resident_config;
  uint32_t base = *(volatile uint32_t *)cfg->ram_base_ptr;
  pops_resident_frame(cfg, (uint8_t *)base);
  return ((PopsIntcHandler)cfg->pops_vblank)(cause);
}

#endif
