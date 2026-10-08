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
  if (i >= 4 && !strncmp(path, "pops", 4)) {
    size_t j;
    for (j = 4; j < i && path[j] >= '0' && path[j] <= '9'; ++j) {}
    if (j == i)
      return 0;
  }
  return 1;
}

int pops_format_proxy_args(char *buffer, size_t capacity,
                           const char *disc0, const char *card0, const char *card1,
                           const char *disc1, const char *disc2, const char *disc3) {
  const char *tokens[7];
  size_t token_count = 4;
  size_t offset = 0;
  size_t i;

  if (!buffer || capacity < 64 || !disc0 || !card0 || !card1)
    return POPS_FILE_INVALID;

  if (!is_valid_device_path(disc0) || !is_valid_device_path(card0) ||
      !is_valid_device_path(card1))
    return POPS_FILE_INVALID;

  tokens[0] = "popfs";
  tokens[1] = disc0;
  tokens[2] = card0;
  tokens[3] = card1;

  if (disc1 && is_valid_device_path(disc1)) {
    tokens[token_count++] = disc1;
    if (disc2 && is_valid_device_path(disc2)) {
      tokens[token_count++] = disc2;
      if (disc3 && is_valid_device_path(disc3))
        tokens[token_count++] = disc3;
    }
  }

  for (i = 0; i < token_count; ++i) {
    size_t len = strlen(tokens[i]) + 1;
    if (offset + len > capacity || offset + len > POPS_PROXY_ARGS_MAX)
      return POPS_FILE_RANGE;
    memcpy(buffer + offset, tokens[i], len);
    offset += len;
  }

  return (int)offset;
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
  uint32_t staging_end;

  if (!plan || staging_size == 0)
    return POPS_FILE_INVALID;

  if (staging_base < POPS_BSS_ADDR + POPS_BSS_SIZE)
    return POPS_FILE_RANGE;

  staging_end = staging_base + (uint32_t)staging_size;
  if (staging_end > UINT32_C(0x02000000))
    return POPS_FILE_RANGE;

  if (plan->core_address != POPS_CORE_ADDR ||
      plan->bss_address != POPS_BSS_ADDR ||
      plan->bss_size != POPS_BSS_SIZE)
    return POPS_FILE_RANGE;

  return POPS_FILE_OK;
}
