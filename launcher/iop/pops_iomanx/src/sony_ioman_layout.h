/* launcHER-owned, metadata-guarded migration of the two selected Sony layouts.
 * Original binary bytes are not included. See docs/POPS_IO_CONTRACT.md. */
#ifndef SONY_IOMAN_LAYOUT_H
#define SONY_IOMAN_LAYOUT_H
#include <stdint.h>
#include <string.h>
typedef struct {
  uint32_t devices[16], files[32][4];
  uint32_t device_source, file_source, linked;
} PopsLegacyIomanState;
typedef uint32_t (*PopsIomanRead32)(void *context, uint32_t address);
static int pops_legacy_ioman_snapshot(PopsIomanRead32 read, void *context,
    uint32_t base, unsigned version, uint32_t text, uint32_t data, uint32_t bss,
    PopsLegacyIomanState *output) {
  PopsLegacyIomanState state;
  uint32_t start, cursor, seen[16];
  unsigned count = 0, i, j;
  if (!read || !output || base < 0x800 || base >= 0x200000 || (base & 3)) return -1;
  memset(&state, 0, sizeof(state));
  if (version == 0x203 && text == 0x1e60 && data == 0x1f0 && bss == 0x290)
    state.linked = 1;
  else if (!(version == 0x201 && text == 0x1b90 && data == 0x180 && bss == 0x250))
    return -1;
  if (text + data + bss > 0x200000 - base) return -1;
  start = base + text + data;
  state.device_source = start + (state.linked ? 12 : 16);
  state.file_source = start + (state.linked ? 16 : 80);
  if (state.linked) {
    cursor = read(context, state.device_source);
    while (cursor) {
      if (count == 16 || cursor < start + 0x210 || cursor >= start + 0x290 ||
          ((cursor - start - 0x210) & 7)) return -1;
      for (j = 0; j < count; ++j) if (seen[j] == cursor) return -1;
      seen[count] = cursor;
      state.devices[count++] = read(context, cursor + 4);
      if (!state.devices[count - 1]) return -1;
      cursor = read(context, cursor);
    }
  } else {
    for (i = 0; i < 16; ++i) state.devices[i] = read(context, state.device_source + i * 4);
  }
  for (i = 0; i < 16; ++i)
    if (state.devices[i] && (state.devices[i] < 0x800 || state.devices[i] > 0x200000 - 20 ||
                             (state.devices[i] & 3))) return -1;
  for (i = 0; i < 32; ++i) {
    for (j = 0; j < 4; ++j) state.files[i][j] = read(context, state.file_source + i * 16 + j * 4);
    if (state.files[i][2]) {
      for (j = 0; j < 16 && state.devices[j] != state.files[i][2]; ++j) {}
      if (j == 16) return -1;
    }
  }
  *output = state;
  return 0;
}
#endif
