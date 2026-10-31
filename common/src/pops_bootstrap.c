#include "pops_bootstrap.h"
#include <string.h>

static int is_valid_device_path(const char *path) {
  size_t len, i;
  if (!path || !(len = strlen(path)) || len >= 256 - 4)
    return 0;
  for (i = 0; i < len && path[i] != ':'; ++i) {
    if (!((path[i] >= 'a' && path[i] <= 'z') ||
          (path[i] >= 'A' && path[i] <= 'Z') ||
          (path[i] >= '0' && path[i] <= '9') || path[i] == '_'))
      return 0;
  }
  if (!i || i == len || !path[i + 1])
    return 0;
  /* A nested popsN: token would feed the bridge back into itself,
   * e.g. hdd0:PART:pops0:/image. Reject every device-token boundary. */
  for (const char *part = path; *part; ++part) {
    if (part != path && part[-1] != ':') continue;
    if (strlen(part) < 5) continue;
    if ((part[0] == 'p' || part[0] == 'P') &&
        (part[1] == 'o' || part[1] == 'O') &&
        (part[2] == 'p' || part[2] == 'P') &&
        (part[3] == 's' || part[3] == 'S')) {
      const char *q = part + 4;
      while (*q >= '0' && *q <= '9') ++q;
      if (*q == ':') return 0;
    }
  }
  return 1;
}

/* Avoid accidentally using a save image as a disc or as another card's
 * .bak file. Mirror popfs IOP module-initialization alias rejection so these
 * invalid requests fail before VMC creation and the external IOP reset. */
static int is_card_alias(const char *card, const char *other) {
  size_t card_len = strlen(card), other_len = strlen(other);
  if (!strcmp(card, other))
    return 1;
  if (card_len == other_len + 4 &&
      !strncmp(card, other, other_len) && !strcmp(card + other_len, ".bak"))
    return 1;
  if (other_len == card_len + 4 &&
      !strncmp(other, card, card_len) && !strcmp(other + card_len, ".bak"))
    return 1;
  return 0;
}

/* A virtual PFS alias must never be its own backend; include HDD paths
 * such as hdd0:PART:pfs:/... and numbered pfsN: mount names. */
static int uses_pfs(const char *path) {
  const char *p;
  for (p = path; p && *p; ++p) {
    const char *q;
    if (p != path && p[-1] != ':') continue;
    if (!p[1] || !p[2]) continue;
    if (!((p[0] == 'p' || p[0] == 'P') &&
          (p[1] == 'f' || p[1] == 'F') &&
          (p[2] == 's' || p[2] == 'S'))) continue;
    q = p + 3;
    while (*q >= '0' && *q <= '9') ++q;
    if (*q == ':') return 1;
  }
  return 0;
}

int pops_format_proxy_args_mode(char *buffer, size_t capacity,
                                const char *disc0, const char *card0, const char *card1,
                                const char *disc1, const char *disc2, const char *disc3,
                                int virtual_pfs) {
  const char *tokens[7];
  size_t token_count = 4;
  size_t offset = 0;
  size_t i;

  if (!buffer || capacity < 64 || !disc0 || !card0 || !card1 ||
      (virtual_pfs != 0 && virtual_pfs != 1))
    return POPS_FILE_INVALID;

  if (!is_valid_device_path(disc0) || !is_valid_device_path(card0) ||
      !is_valid_device_path(card1))
    return POPS_FILE_INVALID;

  tokens[0] = virtual_pfs ? "popfs+pfs" : "popfs";
  tokens[1] = disc0;
  tokens[2] = card0;
  tokens[3] = card1;

  /* Optional discs must be contiguous and individually valid. Dropping a bad
   * entry silently would change the game's disc mapping after IOP reboot. */
  if ((disc2 && !disc1) || (disc3 && !disc2) ||
      (disc1 && !is_valid_device_path(disc1)) ||
      (disc2 && !is_valid_device_path(disc2)) ||
      (disc3 && !is_valid_device_path(disc3)))
    return POPS_FILE_INVALID;
  if (disc1) tokens[token_count++] = disc1;
  if (disc2) tokens[token_count++] = disc2;
  if (disc3) tokens[token_count++] = disc3;

  /* Prevent recursive IOP opens if the virtual pfs: namespace is enabled.
   * This check precedes all writes to the argument packet. */
  if (virtual_pfs) {
    for (i = 1; i < token_count; ++i)
      if (uses_pfs(tokens[i]))
        return POPS_FILE_INVALID;
  }

  /* card0/card1 must not overlap a disc, each other, or the other
   * backing path's backup. Keep the IOP driver as a second defense. */
  for (i = 2; i <= 3; ++i) {
    size_t j;
    for (j = 1; j < token_count; ++j) {
      if (i != j && is_card_alias(tokens[i], tokens[j]))
        return POPS_FILE_INVALID;
    }
  }

  /* Validate the entire packed size before writing any arguments. A late
   * overflow must not expose a partially constructed module argument list. */
  for (i = 0; i < token_count; ++i) {
    size_t len = strlen(tokens[i]) + 1;
    if (len > capacity - offset || len > POPS_PROXY_ARGS_MAX - offset)
      return POPS_FILE_RANGE;
    offset += len;
  }
  offset = 0;
  for (i = 0; i < token_count; ++i) {
    size_t len = strlen(tokens[i]) + 1;
    memcpy(buffer + offset, tokens[i], len);
    offset += len;
  }

  return (int)offset;
}

int pops_format_proxy_args(char *buffer, size_t capacity,
                           const char *disc0, const char *card0, const char *card1,
                           const char *disc1, const char *disc2, const char *disc3) {
  return pops_format_proxy_args_mode(buffer, capacity, disc0, card0, card1,
                                      disc1, disc2, disc3, 0);
}

int pops_trampoline_args_init(PopsTrampolineArgs *out, const PopsBootPlan *plan,
                              uint32_t staging_core, const char *game_arg) {
  const char *arg = (game_arg && game_arg[0] != '\0') ? game_arg : "pops0:IMAGE.VCD";
  size_t arg_len;

  if (!out || !plan || !staging_core)
    return POPS_FILE_INVALID;

  if (plan->entry != POPS_ENTRY_ADDR && plan->entry != POPS_CORE_ADDR)
    return POPS_FILE_RANGE;

  if (plan->core_address != POPS_CORE_ADDR || plan->core_size == 0 ||
      plan->bss_address != POPS_BSS_ADDR || plan->bss_size == 0)
    return POPS_FILE_RANGE;

  arg_len = strlen(arg);
  if (arg_len >= sizeof(out->arg_strings))
    return POPS_FILE_RANGE;

  memset(out, 0, sizeof(*out));
  out->entry = plan->entry;
  out->bss_address = plan->bss_address;
  out->bss_size = plan->bss_size;
  out->scratchpad_size = plan->scratchpad_size;
  out->staging_core = staging_core;
  out->core_address = plan->core_address;
  out->core_size = plan->core_size;
  out->argc = 1;

  memcpy(out->arg_strings, arg, arg_len + 1);

  /* argv[0] points to arg_strings inside the trampoline args structure in bram */
  out->argv[0] = POPS_TRAMPOLINE_ARGS + (uint32_t)offsetof(PopsTrampolineArgs, arg_strings);
  out->argv[1] = 0;

  return POPS_FILE_OK;
}

int pops_bootstrap_verify_layout(uint32_t staging_base, size_t staging_size,
                                 const PopsBootPlan *plan) {
  if (!plan || staging_size == 0)
    return POPS_FILE_INVALID;

  /* Subtract only after checking the base; adding/casting size to uint32_t
   * would permit >=4 GiB sizes to wrap and appear safely inside EE RAM. */
  if (staging_base < POPS_BSS_ADDR + POPS_BSS_SIZE ||
      staging_base >= UINT32_C(0x02000000) ||
      staging_size > UINT32_C(0x02000000) - staging_base)
    return POPS_FILE_RANGE;

  if (plan->core_address != POPS_CORE_ADDR ||
      plan->bss_address != POPS_BSS_ADDR ||
      plan->bss_size != POPS_BSS_SIZE)
    return POPS_FILE_RANGE;

  return POPS_FILE_OK;
}
