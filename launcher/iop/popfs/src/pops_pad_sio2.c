/*
 * sio2man interposition for the resident pad-swap detector.
 *
 * IOP-only (not compiled into host contract tests). Follows the mmceman
 * sio2man_hook precedent: find the sio2man export table through loadcore,
 * replace the sio2_transfer export with a wrapper that snoops pad replies,
 * and relink existing import stubs so Sony's padman reaches the wrapper.
 *
 * The reply parser and swap timing are host-verified only at the state
 * machine level (tools/fixtures/test_popfs.c); the interposition itself
 * needs console validation (Phase 6 gate).
 */
#include "irx_imports.h"
#include <sio2man.h>
#include "pops_ioplib.h"
#include "pops_pad_swap.h"

/* ps2sdk sio2man export index of sio2_transfer (see mmceman's
 * m_25_psio2_transfer numbering). */
#define POPS_SIO2_TRANSFER_EXPORT 25

static int (*pops_original_sio2_transfer)(sio2_transfer_data_t *td);
static iop_library_t *pops_sio2man_lib;

static int pops_sio2man_find_cb(iop_library_t *lib, void *userdata)
{
  (void)userdata;
  pops_sio2man_lib = lib;
  return 1;
}

/* Translate one transfer reply buffer into a 16-bit active-low button word.
 * Standard pad replies carry the 0x5A marker followed by two button bytes,
 * optionally preceded by a 0xFF probe byte. Only the first few bytes are
 * considered so unrelated multi-device transfers stay ignored. */
static int pops_pad_reply_buttons(const sio2_transfer_data_t *td, uint16_t *buttons)
{
  const u8 *reply;
  u32 size, i;
  if (!td || !td->out || td->out_size < 4)
    return 0;
  reply = td->out;
  size = td->out_size;
  for (i = 0; i + 3 < size && i < 8; ++i) {
    if (reply[i] == 0x5A) {
      *buttons = (uint16_t)(reply[i + 1] | ((uint16_t)reply[i + 2] << 8));
      return 1;
    }
  }
  return 0;
}

static int pops_sio2_transfer_hook(sio2_transfer_data_t *td)
{
  pops_pad_swap *sw = pops_pad_swap_instance();
  if (sw && td) {
    uint16_t buttons = 0xFFFFu;
    int valid = pops_pad_reply_buttons(td, &buttons);
    pops_pad_swap_feed(sw, buttons, valid);
  }
  return pops_original_sio2_transfer(td);
}

int pops_pad_sio2_install(void)
{
  void *original;
  pops_sio2man_lib = NULL;
  if (pops_ioplib_iterate_by_name("sio2man", pops_sio2man_find_cb, NULL) != 1)
    return -1;
  if (!pops_sio2man_lib)
    return -1;
  original = pops_ioplib_hook_same_export_entries(pops_sio2man_lib,
                                                  POPS_SIO2_TRANSFER_EXPORT,
                                                  pops_sio2_transfer_hook);
  if (!original)
    return -1;
  pops_original_sio2_transfer = (int (*)(sio2_transfer_data_t *))original;
  pops_ioplib_relink_exports(pops_sio2man_lib);
  return 0;
}
