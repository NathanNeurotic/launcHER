/* Native EE probe for original FUN_00210090. Original code is supplied only
 * by the ignored, locally generated project. Track lookup/RPC/semaphores and
 * logging are doubles; no external storage or save file is opened. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <kernel.h>

extern void pops_probe_install_original(void);
extern uint32_t pops_probe_call(uint32_t lba);

#define REQUEST ((volatile uint32_t *)(uintptr_t)0x0059f680u)
#define LAST_SECTOR (*(volatile uint32_t *)(uintptr_t)0x0050289cu)
#define TRACK_FLAG (*(volatile uint8_t *)(uintptr_t)0x005a8ddeu)

static uint32_t expected_lba, expected_count;
static unsigned rpc_calls, track_calls, waits, signals, errors;
static int failed, force_rpc_mismatch;

int pops_probe_track(void *toc, uint32_t lba) {
  ++track_calls;
  if ((uintptr_t)toc != 0x005a8dc0u || lba != expected_lba) failed = 1;
  return 1;
}
int pops_probe_wait(int sema) { (void)sema; ++waits; return 0; }
int pops_probe_signal(int sema) { (void)sema; ++signals; return 0; }
int pops_probe_log(const char *fmt, uint32_t actual, uint32_t wanted) {
  (void)fmt; (void)actual; (void)wanted; ++errors; return 0;
}
int pops_probe_rpc(void *client, int command, int mode, uint32_t *send,
                   int send_bytes, uint32_t *recv, int recv_bytes, void *callback) {
  ++rpc_calls;
  uint32_t expected_offset = 0x100000u + expected_lba * 2352u;
  if ((uintptr_t)client != 0x005a91c0u || command != 0x435056 || mode != 0 ||
      (uintptr_t)send != 0x0059f680u || send != recv || send_bytes != 20 ||
      recv_bytes != 0x9740 || callback != NULL || send[0] != expected_lba ||
      send[1] != expected_count || send[2] != 0 || send[3] != expected_offset ||
      waits != rpc_calls || signals != rpc_calls - 1) failed = 1;
  printf("POPS_EE_IO_REQUEST lba=%lu count=%lu byte_offset=%lu\n",
         (unsigned long)send[0], (unsigned long)send[1], (unsigned long)send[3]);
  recv[4] = expected_offset & 511u; /* controlled IOP response: leading skip */
  if (force_rpc_mismatch) recv[1] = 0;
  return 0;
}

static void reset(uint32_t lba, uint32_t last) {
  memset((void *)REQUEST, 0, 0x9740);
  LAST_SECTOR = last;
  TRACK_FLAG = 0x40; /* controlled data-track result from lookup double */
  expected_lba = lba;
  expected_count = last - lba + 1u;
  if (expected_count > 16u) expected_count = 16u;
  rpc_calls = track_calls = waits = signals = errors = 0;
  force_rpc_mismatch = 0;
}

int main(void) {
  pops_probe_install_original();
  const uint32_t cases[][2] = {{0, 1000}, {16, 1000}, {1234, 5000},
                               {4999, 5000}, {5000, 5000}};
  unsigned completed = 0;
  for (unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
    reset(cases[i][0], cases[i][1]);
    uint32_t expected = 0x0059f694u + ((0x100000u + expected_lba * 2352u) & 511u);
    uint32_t actual = pops_probe_call(expected_lba);
    if (actual != expected || rpc_calls != 1 || track_calls != 1 || waits != 1 ||
        signals != 1 || errors || failed) goto fail;
    ++completed;
  }
  reset(1234, 5000);
  uint32_t first = pops_probe_call(1234);
  if (!first || pops_probe_call(1237) != first + 3u * 2352u || rpc_calls != 1 ||
      track_calls != 1 || waits != 1 || signals != 1 || errors || failed) goto fail;
  ++completed;
  reset(1234, 5000);
  force_rpc_mismatch = 1;
  if (pops_probe_call(1234) != 0 || REQUEST[0] != 0 || REQUEST[1] != 0 ||
      rpc_calls != 1 || errors != 1 || waits != 1 || signals != 1 || failed) goto fail;
  ++completed;
  printf("POPS_EE_IO_REQUEST_PASS cases=%u original_R5900=1 services=modeled\n", completed);
  fflush(stdout);
  SleepThread();
  return 0;
fail:
  printf("POPS_EE_IO_REQUEST_FAIL completed=%u rpc=%u track=%u wait=%u signal=%u errors=%u failed=%d\n",
         completed, rpc_calls, track_calls, waits, signals, errors, failed);
  fflush(stdout);
  SleepThread();
  return 1;
}
