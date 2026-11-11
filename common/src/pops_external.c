#include "pops_external.h"
#include <string.h>

#define EE_START UINT32_C(0x00100000)
#define EE_END UINT32_C(0x02000000)
#define SCRATCH_START UINT32_C(0x70000000)
#define SCRATCH_END UINT32_C(0x70004000)
#define HEADER_SIZE POPS_CONTAINER_HEADER_SIZE

static uint16_t le16(const uint8_t *p) {
  return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t le32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
         ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static int ee_range(uint32_t address, uint32_t length) {
  return address >= EE_START && address < EE_END && length <= EE_END - address;
}

int pops_elf_inspect(const void *file, size_t size, PopsElfInfo *out) {
  const uint8_t *data = file;
  PopsElfInfo info = {0};
  uint32_t phoff;
  uint16_t count;
  int entry_found = 0;
  if (!data || !out || size < 52 || memcmp(data, "\177ELF", 4))
    return POPS_FILE_INVALID;
  if (data[4] != 1 || data[5] != 1 || data[6] != 1 ||
      le16(data + 16) != 2 || le16(data + 18) != 8 || le32(data + 20) != 1)
    return POPS_FILE_UNSUPPORTED;
  if (le16(data + 40) != 52 || le16(data + 42) != 32)
    return POPS_FILE_INVALID;
  phoff = le32(data + 28);
  count = le16(data + 44);
  if (!count || phoff < 52 || phoff > size || count > (size - phoff) / 32)
    return POPS_FILE_INVALID;
  info.entry = le32(data + 24);
  for (uint16_t i = 0; i < count; i++) {
    const uint8_t *p = data + phoff + (size_t)i * 32;
    uint32_t offset, address, filesz, memsz, align;
    if (le32(p) != 1)
      continue;
    offset = le32(p + 4);
    address = le32(p + 8);
    filesz = le32(p + 16);
    memsz = le32(p + 20);
    align = le32(p + 28);
    if (filesz > memsz || offset > size || filesz > size - offset)
      return POPS_FILE_INVALID;
    /* The reference POPS ELF has a zero-file-size scratchpad PT_LOAD.
     * Accept that BSS reservation, but never treat arbitrary MMIO as load RAM. */
    if (!memsz || (!ee_range(address, memsz) &&
        !(address >= SCRATCH_START && address < SCRATCH_END &&
          memsz <= SCRATCH_END - address && !filesz && !(le32(p + 24) & 1))))
      return POPS_FILE_RANGE;
    if (align > 1 && ((align & (align - 1)) || address % align != offset % align))
      return POPS_FILE_INVALID;
    /* The entry must point to aligned, file-backed executable instructions. */
    if ((le32(p + 24) & 1) && !(info.entry & 3) && info.entry >= address &&
        info.entry - address <= filesz && filesz - (info.entry - address) >= 4)
      entry_found = 1;
    for (uint16_t j = 0; j < i; j++) {
      const uint8_t *q = data + phoff + (size_t)j * 32;
      uint32_t other = le32(q + 8), other_size = le32(q + 20);
      if (le32(q) == 1 && address < (uint64_t)other + other_size &&
          other < (uint64_t)address + memsz)
        return POPS_FILE_RANGE;
    }
    info.load_segments++;
  }
  if (!info.load_segments || !entry_found)
    return POPS_FILE_INVALID;
  *out = info;
  return POPS_FILE_OK;
}

int pops_container_inspect(const void *file, size_t size, PopsContainer *out) {
  const uint8_t *data = file;
  PopsContainer result = {0};
  int trojan;
  if (!data || !out || size < HEADER_SIZE)
    return POPS_FILE_INVALID;
  trojan = !memcmp(data, "TROJAN_", 7) && data[7] >= '0' && data[7] <= '9';
  if (trojan) {
    result.slot = data[7] - '0';
  } else if (!memcmp(data, "PATCH_", 6) && data[6] >= '0' &&
             data[6] <= '9' && data[7] == 0) {
    result.slot = data[6] - '0';
  } else {
    return POPS_FILE_UNSUPPORTED;
  }
  result.control = le32(data + 8);
  result.flags = le32(data + 12);
  result.load = le32(data + 16);
  result.entry = le32(data + 20);
  result.hook = le32(data + 24);
  result.payload_size = le32(data + 28);
  memcpy(result.metadata, data + 32, sizeof(result.metadata));
  if (result.payload_size != size - HEADER_SIZE)
    return POPS_FILE_INVALID;
  if (result.flags != UINT32_C(0x00010001) && result.flags != UINT32_C(0x00010003) &&
      result.flags != UINT32_C(0x00010002))
    return POPS_FILE_UNSUPPORTED;
  if (trojan) {
    if ((result.control & UINT32_C(0xff00ffff)) ||
        (result.flags == UINT32_C(0x00010001) && result.control))
      return POPS_FILE_UNSUPPORTED;
    if (!result.payload_size || ((result.load | result.entry | result.hook |
                                result.payload_size) & 3))
      return POPS_FILE_INVALID;
    if (!ee_range(result.load, result.payload_size) || !ee_range(result.hook, 8) ||
        result.entry < result.load || result.entry - result.load >= result.payload_size)
      return POPS_FILE_RANGE;
    if (result.load < (uint64_t)result.hook + 8 &&
        result.hook < (uint64_t)result.load + result.payload_size)
      return POPS_FILE_RANGE;
    result.kind = POPS_CONTAINER_TROJAN;
  } else {
    if (result.entry || result.hook)
      return POPS_FILE_UNSUPPORTED;
    if (result.payload_size) {
      if (!ee_range(result.load, result.payload_size))
        return POPS_FILE_RANGE;
      result.kind = POPS_CONTAINER_DATA;
    } else {
      if (result.load)
        return POPS_FILE_INVALID;
      result.kind = POPS_CONTAINER_CONFIG;
    }
  }
  *out = result;
  return POPS_FILE_OK;
}

int pops_trojan_verdict(const void *file, size_t size, unsigned slot,
                        unsigned fingerprint_builtin_id, PopsTrojanInfo *out) {
  const uint8_t *h = file;
  PopsTrojanInfo info = {0};
  uint32_t jump;
  if (!h || !out || slot > 9)
    return POPS_FILE_INVALID;
  if (size < POPS_TROJAN_MIN_FILE)
    return POPS_TROJAN_INVALID;
  if (memcmp(h, "TROJAN_", 7) || h[7] != '0' + slot)
    return POPS_TROJAN_INVALID;
  if (h[0x0c] < 1 || h[0x0c] > 3)
    return POPS_TROJAN_INVALID;
  if (h[0x08] | h[0x09] | h[0x0b] | h[0x0d] | h[0x0f] | h[0x1f])
    return POPS_TROJAN_INVALID;
  for (unsigned i = 0x34; i < 0x40; ++i)
    if (h[i])
      return POPS_TROJAN_INVALID;
  info.load = le32(h + 0x10);
  info.entry = le32(h + 0x14);
  info.hook = le32(h + 0x18);
  info.size = le32(h + 0x1c) & UINT32_C(0x00ffffff);
  if (!info.load || !info.entry)
    return POPS_TROJAN_INVALID;
  if ((uint64_t)info.size + HEADER_SIZE != size)
    return POPS_TROJAN_INVALID;
  if (!h[0x0e] || !h[0x20])
    return POPS_TROJAN_INVALID;
  if (h[0x0c] == 1 && h[0x0a])
    return POPS_TROJAN_INVALID;
  info.slot = (uint8_t)slot;
  info.format = h[0x0c];
  info.width = h[0x0a];
  jump = (info.entry >> 2) & UINT32_C(0x03ffffff);
  info.hook_words = 1;
  info.hook_word[0] = UINT32_C(0x0c000000) | jump;
  if (info.format == 2 && info.width >= 1 && info.width <= 3) {
    info.hook_words = info.width;
    info.hook_word[0] = UINT32_C(0x08000000) | jump;
  }
  *out = info;
  if (info.format == 3 && info.width < POPS_TROJAN_REVISION && fingerprint_builtin_id)
    return POPS_TROJAN_OUTDATED;
  return POPS_TROJAN_APPLY;
}

const char *pops_trojan_reason_text(unsigned reason) {
  switch (reason) {
  case POPS_TROJAN_NO_UNALIGNED:
    return "an address or the size is not a multiple of 4";
  case POPS_TROJAN_NO_ENTRY:
    return "its entry is outside its payload";
  case POPS_TROJAN_NO_RANGE:
    return "its payload loads outside the memory launcHER can host";
  case POPS_TROJAN_NO_HOOK:
    return "its hook is not a word launcHER can patch";
  case POPS_TROJAN_NO_SPACE:
    return "the payloads of this launch do not fit launcHER's holding memory";
  case POPS_TROJAN_NO_SLOT:
    return "it needs POPStarter's slot chain, which launcHER cannot offer here";
  case POPS_TROJAN_NO_480P:
    return "it uses POPStarter's 480p handler, which launcHER does not have";
  case POPS_TROJAN_NO_BLOCK2:
    return "it uses POPStarter code at 0x238a90..0x2397ef, which launcHER does not have";
  case POPS_TROJAN_NO_BUILTIN:
    return "it uses a built-in fix's code at 0x01410000";
  case POPS_TROJAN_NO_OWNED:
    return "it uses POPStarter code at 0x0143a000..0x014601ff, where launcHER keeps its own";
  case POPS_TROJAN_NO_BLOCK1:
    return "it uses POPStarter code at 0x232790..0x232ec7 outside the slots";
  case POPS_TROJAN_NO_MAIN:
    return "it uses POPStarter's own program, which is not in memory";
  default:
    return "unknown reason";
  }
}

static int trojan_within(uint32_t address, uint32_t base, uint32_t limit) {
  return address >= base && address < limit;
}

static int trojan_overlap(uint32_t address, uint32_t size, uint32_t base, uint32_t limit) {
  return size && address < limit && (uint64_t)address + size > base;
}

int pops_trojan_in_arena(uint32_t address, uint32_t size) {
  return size && address >= POPS_TROJAN_ARENA_BASE && address < POPS_TROJAN_ARENA_LIMIT &&
         size <= POPS_TROJAN_ARENA_LIMIT - address &&
         !trojan_overlap(address, size, POPS_TROJAN_OWNED_BASE, POPS_TROJAN_OWNED_LIMIT);
}

/* How a reference was made. */
enum { TROJAN_REF_CODE, TROJAN_REF_DATA, TROJAN_REF_VALUE };
#define TROJAN_POPS_GP UINT32_C(0x0050a670)

typedef struct {
  const uint8_t *payload;
  uint32_t load;
  uint32_t size;
  uint8_t *done;    /* one bit per payload word: read as code */
  uint8_t *pending; /* one bit per payload word: code to read */
  uint32_t lowest;  /* no pending word below this index */
  uint32_t flags;
  uint32_t value[32];
  uint8_t state[32]; /* 0: unknown, 1: lui only, 2: a whole constant */
} TrojanScan;

static uint32_t trojan_ref_flags(uint32_t address, int kind) {
  for (unsigned i = 0; i < 2; ++i) {
    uint32_t base = i ? POPS_TROJAN_SLOTS_B : POPS_TROJAN_SLOTS_A;
    if (trojan_within(address, base, base + POPS_TROJAN_SLOTS_SPAN))
      /* Jumping to the words after the slots continues the chain; reading
       * or changing them is reading or changing POPStarter's code. */
      return address - base >= POPS_TROJAN_SLOTS_HOOKS && kind == TROJAN_REF_DATA
                 ? POPS_TROJAN_REF_BLOCK1 : POPS_TROJAN_REF_SLOT;
  }
  if (trojan_within(address, POPS_TROJAN_BLOCK1_BASE, POPS_TROJAN_BLOCK1_LIMIT))
    return POPS_TROJAN_REF_BLOCK1;
  if (trojan_within(address, POPS_TROJAN_480P_BASE, POPS_TROJAN_480P_LIMIT))
    return POPS_TROJAN_REF_480P;
  if (trojan_within(address, POPS_TROJAN_BLOCK2_BASE, POPS_TROJAN_BLOCK2_LIMIT))
    return POPS_TROJAN_REF_BLOCK2;
  if (trojan_within(address, POPS_TROJAN_BUILTIN_BASE, POPS_TROJAN_ARENA_BASE))
    return POPS_TROJAN_REF_BUILTIN;
  if (trojan_within(address, POPS_TROJAN_OWNED_BASE, POPS_TROJAN_OWNED_LIMIT))
    return POPS_TROJAN_REF_OWNED;
  if (kind != TROJAN_REF_VALUE &&
      trojan_within(address, POPS_TROJAN_MAIN_BASE, POPS_TROJAN_MAIN_LIMIT))
    return POPS_TROJAN_REF_MAIN;
  return 0;
}

static void trojan_note(TrojanScan *s, uint32_t address, int kind) {
  if (address >= s->load && address - s->load < s->size) {
    uint32_t index = (address - s->load) / 4;
    if (kind == TROJAN_REF_CODE && !(address & 3) && !(s->done[index / 8] & (1u << (index & 7)))) {
      s->pending[index / 8] |= (uint8_t)(1u << (index & 7));
      if (index < s->lowest)
        s->lowest = index;
    }
    return;
  }
  s->flags |= trojan_ref_flags(address, kind);
}

/* A whole 32-bit constant: the j/jal word it may be, or a plain value. */
static void trojan_constant(TrojanScan *s, uint32_t value) {
  if (value >> 26 == 2 || value >> 26 == 3)
    trojan_note(s, (value & UINT32_C(0x03ffffff)) << 2, TROJAN_REF_CODE);
  else
    trojan_note(s, value, TROJAN_REF_VALUE);
}

static uint32_t trojan_s16(uint32_t word) {
  return (uint32_t)(int32_t)(int16_t)(word & 0xffff);
}

#define TROJAN_STEP_BRANCH 1 /* the next word is its delay slot */
#define TROJAN_STEP_STOP   2 /* nothing is read after the delay slot */

static int trojan_step(TrojanScan *s, uint32_t pc, uint32_t word) {
  uint32_t op = word >> 26, rs = (word >> 21) & 31, rt = (word >> 16) & 31;
  uint32_t rd = (word >> 11) & 31, imm = word & 0xffff, fn = word & 0x3f;
  if (!word)
    return 0;
  if (op == 0) {
    if (fn == 8) { /* jr */
      if (s->state[rs] == 2)
        trojan_note(s, s->value[rs], TROJAN_REF_CODE);
      return TROJAN_STEP_BRANCH | TROJAN_STEP_STOP;
    }
    if (fn == 9) { /* jalr */
      if (s->state[rs] == 2)
        trojan_note(s, s->value[rs], TROJAN_REF_CODE);
      memset(s->state, 0, sizeof(s->state));
      return TROJAN_STEP_BRANCH;
    }
    if (fn != 0x0c)
      s->state[rd] = 0;
    return 0;
  }
  if (op == 2 || op == 3) { /* j, jal */
    trojan_note(s, (pc & UINT32_C(0xf0000000)) | ((word & UINT32_C(0x03ffffff)) << 2),
                TROJAN_REF_CODE);
    return op == 2 ? TROJAN_STEP_BRANCH | TROJAN_STEP_STOP : TROJAN_STEP_BRANCH;
  }
  if (op == 1 || (op >= 4 && op <= 7) || (op >= 0x14 && op <= 0x17)) { /* branches */
    int always = (op == 4 && rs == rt) || (op == 6 && !rs) || (op == 1 && rt == 1 && !rs);
    trojan_note(s, pc + 4 + (trojan_s16(word) << 2), TROJAN_REF_CODE);
    return always ? TROJAN_STEP_BRANCH | TROJAN_STEP_STOP : TROJAN_STEP_BRANCH;
  }
  if (op == 0x0f) { /* lui */
    s->value[rt] = imm << 16;
    s->state[rt] = rt ? 1 : 0;
    return 0;
  }
  if (op == 0x09 || op == 0x0d || op == 0x08 || op == 0x19 || op == 0x18) {
    /* addiu, ori, addi, daddiu, daddi */
    if (s->state[rs] && (rs != rt || s->state[rs] == 1)) {
      uint32_t value = op == 0x0d ? s->value[rs] | imm : s->value[rs] + trojan_s16(word);
      s->value[rt] = value;
      s->state[rt] = rt ? 2 : 0;
      trojan_constant(s, value);
    } else if (!rs) {
      s->value[rt] = op == 0x0d ? imm : trojan_s16(word);
      s->state[rt] = rt ? 2 : 0;
    } else {
      s->state[rt] = 0;
    }
    return 0;
  }
  if (op == 0x0a || op == 0x0b || op == 0x0c || op == 0x0e) { /* slti, sltiu, andi, xori */
    s->state[rt] = 0;
    return 0;
  }
  {
    /* lb lh lwl lw lbu lhu lwr lwu ld lq ldl ldr lwc1; sb sh swl sw swr sd sq sdl sdr swc1 */
    int load = (op >= 0x20 && op <= 0x27) || op == 0x37 || op == 0x1e || op == 0x1a ||
               op == 0x1b || op == 0x31;
    int store = (op >= 0x28 && op <= 0x2b) || op == 0x2e || op == 0x3f || op == 0x1f ||
                op == 0x2c || op == 0x2d || op == 0x39;
    if (load || store) {
      if (rs == 28)
        trojan_note(s, TROJAN_POPS_GP + trojan_s16(word), TROJAN_REF_DATA);
      else if (s->state[rs])
        trojan_note(s, s->value[rs] + trojan_s16(word), TROJAN_REF_DATA);
      if (load && op != 0x31)
        s->state[rt] = 0;
      return 0;
    }
  }
  if (op == 0x10) /* COP0: mfc0, mtc0, eret, ei, di */
    return 0;
  s->state[rt] = 0;
  s->state[rd] = 0;
  return 0;
}

static int trojan_take(TrojanScan *s, uint32_t address) {
  /* Marks a word as read; 0 when it is outside the payload or was read. */
  uint32_t index;
  if (address < s->load || address - s->load >= s->size)
    return 0;
  index = (address - s->load) / 4;
  if (s->done[index / 8] & (1u << (index & 7)))
    return 0;
  s->done[index / 8] |= (uint8_t)(1u << (index & 7));
  return 1;
}

int pops_trojan_scan(const void *payload, uint32_t size, uint32_t load, uint32_t entry,
                     void *work, size_t work_size, uint32_t *flags) {
  TrojanScan s;
  uint32_t words = size / 4, map = (words + 7) / 8;
  if (!payload || !work || !flags || !size || ((size | load | entry) & 3) ||
      (uint64_t)load + size > UINT32_C(0xffffffff) || entry < load || entry - load >= size ||
      work_size < (size_t)map * 2)
    return POPS_FILE_INVALID;
  memset(&s, 0, sizeof(s));
  s.payload = payload;
  s.load = load;
  s.size = size;
  s.done = work;
  s.pending = s.done + map;
  memset(work, 0, (size_t)map * 2);
  s.lowest = words;
  trojan_note(&s, entry, TROJAN_REF_CODE);
  while (s.lowest < words) {
    /* The lowest address still to read, with nothing known about registers. */
    uint32_t index = s.lowest, pc;
    while (index < words && !(s.pending[index / 8] & (1u << (index & 7))))
      index = s.pending[index / 8] ? index + 1 : (index | 7) + 1;
    s.lowest = index;
    if (index >= words)
      break;
    s.pending[index / 8] &= (uint8_t)~(1u << (index & 7));
    pc = load + index * 4;
    memset(s.state, 0, sizeof(s.state));
    while (trojan_take(&s, pc)) {
      int step = trojan_step(&s, pc, le32(s.payload + (pc - load)));
      if (!(step & TROJAN_STEP_BRANCH)) {
        pc += 4;
        continue;
      }
      if (trojan_take(&s, pc + 4))
        (void)trojan_step(&s, pc + 4, le32(s.payload + (pc + 4 - load)));
      if (step & TROJAN_STEP_STOP)
        break;
      memset(s.state, 0, sizeof(s.state));
      pc += 8;
    }
  }
  *flags = s.flags;
  return POPS_FILE_OK;
}

int pops_trojan_copy_out(const PopsTrojanSet *set, uint8_t *ram, uint32_t ram_base,
                         uint32_t ram_limit, const PopsTrojanKeep *keep, unsigned keep_count) {
  if (!set || !ram || ram_limit < ram_base || (keep_count && !keep) ||
      set->payload_count > POPS_TROJAN_MAX_PAYLOADS || set->hold_used > set->hold_size ||
      (set->payload_count && !set->hold))
    return POPS_FILE_INVALID;
  for (unsigned i = 0; i < set->payload_count; ++i) {
    const PopsTrojanPayload *p = &set->payload[i];
    uintptr_t target;
    if ((p->address | p->size) & 3 || !pops_trojan_in_arena(p->address, p->size) ||
        p->address < ram_base || p->address > ram_limit || p->size > ram_limit - p->address ||
        p->hold > set->hold_used || p->size > set->hold_used - p->hold)
      return POPS_FILE_INVALID;
    for (unsigned k = 0; k < keep_count; ++k)
      if (keep[k].end < keep[k].start ||
          trojan_overlap(p->address, p->size, keep[k].start, keep[k].end))
        return POPS_FILE_INVALID;
    target = (uintptr_t)ram + (p->address - ram_base);
    if (target < (uintptr_t)set->hold + set->hold_size && (uintptr_t)set->hold < target + p->size)
      return POPS_FILE_INVALID;
  }
  for (unsigned i = 0; i < set->payload_count; ++i) {
    const PopsTrojanPayload *p = &set->payload[i];
    memcpy(ram + (p->address - ram_base), set->hold + p->hold, p->size);
  }
  return (int)set->payload_count;
}

static int window_offset(uint32_t address, uint32_t length, uint32_t base,
                         size_t span, size_t *offset) {
  if (address < base || address - base > span || length > span - (address - base))
    return POPS_FILE_RANGE;
  *offset = address - base;
  return POPS_FILE_OK;
}

int pops_container_plan(const void *file, size_t size, uint32_t base,
                        size_t span, PopsContainerPlan *out) {
  PopsContainerPlan plan = {0};
  int status;
  if (!out)
    return POPS_FILE_INVALID;
  if (base < EE_START || base >= EE_END || span > EE_END - base)
    return POPS_FILE_RANGE;
  status = pops_container_inspect(file, size, &plan.container);
  if (status)
    return status;
  if (plan.container.kind != POPS_CONTAINER_CONFIG) {
    status = window_offset(plan.container.load, plan.container.payload_size,
                           base, span, &plan.payload_offset);
    if (status)
      return status;
    if (plan.container.kind == POPS_CONTAINER_TROJAN) {
      plan.hook_instruction = UINT32_C(0x0c000000) | (plan.container.entry >> 2);
      plan.hook_size = 4;
      uint32_t width = (plan.container.control >> 16) & 0xff;
      if ((plan.container.flags & 0xff) == 2 && width >= 1 && width <= 3) {
        plan.hook_instruction = UINT32_C(0x08000000) | (plan.container.entry >> 2);
        plan.hook_size = (uint8_t)(width * 4);
      }
      if (plan.container.load < (uint64_t)plan.container.hook + plan.hook_size &&
          plan.container.hook < (uint64_t)plan.container.load + plan.container.payload_size)
        return POPS_FILE_RANGE;
      status = window_offset(plan.container.hook, plan.hook_size > 8 ? 12 : 8,
                             base, span, &plan.hook_offset);
      if (status)
        return status;
    }
  }
  *out = plan;
  return POPS_FILE_OK;
}

static void write_le32(uint8_t *p, uint32_t value) {
  p[0] = (uint8_t)value;
  p[1] = (uint8_t)(value >> 8);
  p[2] = (uint8_t)(value >> 16);
  p[3] = (uint8_t)(value >> 24);
}

int pops_container_stage(const void *file, size_t size, uint32_t base,
                         void *memory, size_t span, const uint32_t *expected_hook,
                         size_t expected_count) {
  PopsContainerPlan plan;
  uintptr_t source = (uintptr_t)file, dest = (uintptr_t)memory;
  uint8_t *bytes = memory;
  int status;
  if (!memory)
    return POPS_FILE_INVALID;
  status = pops_container_plan(file, size, base, span, &plan);
  if (status)
    return status;
  if (plan.container.kind == POPS_CONTAINER_CONFIG)
    return POPS_FILE_UNSUPPORTED;
  /* A copy must not overwrite the container it is still consuming. */
  if (source <= dest ? dest - source < size : source - dest < span)
    return POPS_FILE_RANGE;
  if (plan.container.kind == POPS_CONTAINER_TROJAN) {
    size_t guard_count = plan.hook_size > 8 ? 3 : 2;
    if (!expected_hook || expected_count != guard_count)
      return POPS_FILE_INVALID;
    for (size_t i = 0; i < guard_count; i++) {
      if (le32(bytes + plan.hook_offset + i * 4) != expected_hook[i])
        return POPS_FILE_GUARD;
    }
  }
  memcpy(bytes + plan.payload_offset, (const uint8_t *)file + HEADER_SIZE,
         plan.container.payload_size);
  if (plan.container.kind == POPS_CONTAINER_TROJAN) {
    write_le32(bytes + plan.hook_offset, plan.hook_instruction);
    if (plan.hook_size > 4)
      memset(bytes + plan.hook_offset + 4, 0, plan.hook_size - 4);
  }
  return POPS_FILE_OK;
}

int pops_patch_options(const PopsContainer *container, PopsPatchOptions *out) {
  PopsPatchOptions options = {{0}, POPS_PATCH_VIDEO_NONE};
  if (!container || !out)
    return POPS_FILE_INVALID;
  if (container->kind != POPS_CONTAINER_CONFIG && container->kind != POPS_CONTAINER_DATA)
    return POPS_FILE_UNSUPPORTED;
  if (container->control > 7)
    return POPS_FILE_UNSUPPORTED;
  if (container->control & 1)
    memcpy(options.modes, container->metadata + 24, sizeof(options.modes));
  else if (le32(container->metadata + 24))
    return POPS_FILE_INVALID;
  switch (container->control & 6) {
  case 2:
    options.video = POPS_PATCH_VIDEO_PAL;
    break;
  case 4:
    options.video = POPS_PATCH_VIDEO_DISABLE_AUTO;
    break;
  case 6:
    options.video = POPS_PATCH_VIDEO_CONTROL6;
    break;
  }
  *out = options;
  return POPS_FILE_OK;
}
