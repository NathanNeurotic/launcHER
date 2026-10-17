#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../../launcher/iop/pops_iomanx/src/sony_ioman_layout.h"
static uint32_t ram[0x200000 / 4];
static unsigned reads;
static uint32_t read_word(void *context, uint32_t address) {
  (void)context; assert(address < sizeof(ram) && !(address & 3)); ++reads; return ram[address / 4];
}
static void word(uint32_t address, uint32_t value) { ram[address / 4] = value; }
int main(void) {
  const uint32_t base = 0x10000, bss203 = base + 0x2050, bss201 = base + 0x1d10;
  const uint32_t tty = 0x18000, rom = 0x19000;
  PopsLegacyIomanState state, before;
  word(bss203 + 12, bss203 + 0x210);
  word(bss203 + 0x210, bss203 + 0x218); word(bss203 + 0x214, tty);
  word(bss203 + 0x218, 0); word(bss203 + 0x21c, rom);
  word(bss203 + 16, 3); word(bss203 + 16 + 8, tty); /* live descriptor zero */
  word(bss203 + 16 + 31 * 16, 1); word(bss203 + 16 + 31 * 16 + 8, rom);
  assert(!pops_legacy_ioman_snapshot(read_word, NULL, base, 0x203, 0x1e60, 0x1f0, 0x290, &state));
  assert(state.linked && state.devices[0] == tty && state.devices[1] == rom);
  assert(state.files[0][0] == 3 && state.files[0][2] == tty && state.files[31][2] == rom);
  assert(state.device_source == bss203 + 12 && state.file_source == bss203 + 16);
  assert(ram[(bss203 + 16) / 4] == 3); /* snapshot never mutates source */
  before = state;
  word(bss203 + 0x218, bss203 + 0x210);
  assert(pops_legacy_ioman_snapshot(read_word, NULL, base, 0x203, 0x1e60, 0x1f0, 0x290, &state));
  assert(!memcmp(&state, &before, sizeof(state)));
  word(bss203 + 0x218, 0); word(bss203 + 0x214, 3);
  assert(pops_legacy_ioman_snapshot(read_word, NULL, base, 0x203, 0x1e60, 0x1f0, 0x290, &state));
  word(bss203 + 0x214, tty); word(bss203 + 12, 0x1ffffc);
  assert(pops_legacy_ioman_snapshot(read_word, NULL, base, 0x203, 0x1e60, 0x1f0, 0x290, &state));
  memset(ram, 0, sizeof(ram));
  word(bss201 + 16, tty); word(bss201 + 20, rom);
  word(bss201 + 80, 3); word(bss201 + 88, tty);
  word(bss201 + 80 + 31 * 16 + 8, rom);
  assert(!pops_legacy_ioman_snapshot(read_word, NULL, base, 0x201, 0x1b90, 0x180, 0x250, &state));
  assert(!state.linked && state.devices[1] == rom && state.files[31][2] == rom);
  word(bss201 + 88, 0x1a000);
  assert(pops_legacy_ioman_snapshot(read_word, NULL, base, 0x201, 0x1b90, 0x180, 0x250, &state));
  reads = 0;
  assert(pops_legacy_ioman_snapshot(read_word, NULL, base, 0x202, 0x1b90, 0x180, 0x250, &state));
  assert(pops_legacy_ioman_snapshot(read_word, NULL, base, 0x203, 0x1e60, 0x1f0, 0x291, &state));
  assert(pops_legacy_ioman_snapshot(read_word, NULL, 0x1ffffc, 0x203, 0x1e60, 0x1f0, 0x290, &state));
  assert(!reads);
  puts("Sony IOMAN layout PASS: linked/flat devices, all 32 descriptors, cycles, bounds and fail-atomic snapshots");
}
