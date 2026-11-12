#include "pops_handoff_ee.h"
#include "pops_bootstrap.h"
#include "pops_handoff.h"
#include <kernel.h>
#include <stdint.h>
#include <string.h>

/* Stack for the DORMANT threads that only exist to put the kernel's free
 * slots back in order. They are never started; CreateThread writes an
 * initial frame into it and nothing else ever does. */
static unsigned char dormantStack[0x400] __attribute__((aligned(16)));

static void dormantEntry(void *arg) {
  (void)arg;
}

static int kernelSelf(void *ctx) {
  (void)ctx;
  return GetThreadId();
}

static int kernelRefer(void *ctx, int tid, PopsHandoffThread *out) {
  ee_thread_status_t info;
  int status;
  (void)ctx;
  memset(&info, 0, sizeof(info));
  status = ReferThreadStatus(tid, &info);
  if (status < 0)
    return status;
  out->status = status;
  out->stack = (uint32_t)(uintptr_t)info.stack;
  out->stack_size = (uint32_t)info.stack_size;
  return 0;
}

static int kernelTerminate(void *ctx, int tid) {
  (void)ctx;
  return TerminateThread(tid);
}

static int kernelRemove(void *ctx, int tid) {
  (void)ctx;
  return DeleteThread(tid);
}

static int kernelCreate(void *ctx) {
  ee_thread_t thread;
  (void)ctx;
  memset(&thread, 0, sizeof(thread));
  thread.func = dormantEntry;
  thread.stack = dormantStack;
  thread.stack_size = sizeof(dormantStack);
  thread.gp_reg = &_gp;
  thread.initial_priority = 64;
  return CreateThread(&thread);
}

int popsHandoffRetireThreads(void) {
  static const PopsHandoffKernel kernel = {kernelSelf, kernelRefer, kernelTerminate,
                                           kernelRemove, kernelCreate};
  /* Prepared before this runs and never rewritten: the trampoline, its
   * arguments and stack below 1 MiB, and the staged core with the built-in
   * entry's code, the resident image and the breakpoint handler above it. */
  static const PopsHandoffRange protect[] = {
    {UINT32_C(0x00080000), UINT32_C(0x00100000)},
    {POPS_STAGING_BASE, POPS_STAGING_BASE + POPS_STAGING_CAPACITY},
  };
  PopsHandoffReport report;
  int res = pops_handoff_retire_threads(&kernel, NULL, protect,
                                        sizeof(protect) / sizeof(protect[0]), &report);
  /* Left below 1 MiB for whoever reads RAM afterwards (emulator dumps): no
   * trace line can follow, the thread and RPC services are gone. */
  volatile int32_t *out = (volatile int32_t *)POPS_HANDOFF_REPORT_ADDR;
  out[0] = (int32_t)POPS_HANDOFF_REPORT_MAGIC;
  out[1] = res;
  out[2] = report.self;
  out[3] = report.retired;
  out[4] = report.first_retired;
  out[5] = report.drained;
  out[6] = report.queue;
  out[7] = report.failed_tid;
  return res;
}
