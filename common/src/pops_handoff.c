#include "pops_handoff.h"
#include "pops_bootstrap.h"

#include <errno.h>
#include <string.h>

/* What lives below 1 MiB until ExecPS2, in this order and apart: the
 * trampoline (at most 0x180 bytes, checked in launchPOPS and by
 * tools/check_pops_handoff_layout.py), its arguments, the report words, then
 * the trampoline's stack, which starts at 0x0008fff0 and grows down. A
 * change to any of these addresses or to PopsTrampolineArgs that makes two
 * of them overlap fails the build here (and the host build of this file). */
_Static_assert(POPS_TRAMPOLINE_ADDR + 0x180 <= POPS_TRAMPOLINE_ARGS,
               "the trampoline would run into its arguments");
_Static_assert(POPS_TRAMPOLINE_ARGS + sizeof(PopsTrampolineArgs) <= POPS_HANDOFF_REPORT_ADDR,
               "the trampoline's arguments would run into the handoff report words");
_Static_assert(POPS_HANDOFF_REPORT_ADDR + 8 * sizeof(int32_t) <= UINT32_C(0x0008fff0),
               "the handoff report words would run into the trampoline's stack");

static int thread_in_use(const PopsHandoffKernel *kernel, void *ctx, int tid, PopsHandoffThread *out) {
  PopsHandoffThread local;
  if (!out)
    out = &local;
  memset(out, 0, sizeof(*out));
  if (kernel->refer(ctx, tid, out) < 0)
    return 0;
  return out->status != 0;
}

/* The kernel rewrites [stack + size - 0x2a0, stack + size) of a thread it
 * terminates. 64-bit sums: a wild stack or size must not wrap past a range. */
static int frame_overlaps(const PopsHandoffThread *thread, const PopsHandoffRange *protect, size_t count) {
  uint64_t end = (uint64_t)thread->stack + thread->stack_size;
  uint64_t start = end > POPS_HANDOFF_RESET_FRAME ? end - POPS_HANDOFF_RESET_FRAME : 0;
  size_t i;
  for (i = 0; i < count; ++i) {
    if (protect[i].start < protect[i].end && start < protect[i].end && protect[i].start < end)
      return 1;
  }
  return 0;
}

int pops_handoff_retire_threads(const PopsHandoffKernel *kernel, void *ctx,
                                const PopsHandoffRange *protect, size_t protect_count,
                                PopsHandoffReport *report) {
  uint8_t retired[POPS_HANDOFF_MAX_THREADS];
  uint8_t created[POPS_HANDOFF_MAX_THREADS];
  uint8_t seen[POPS_HANDOFF_MAX_THREADS];
  PopsHandoffThread thread;
  int nretired = 0, ncreated = 0, result = 0, fifo, tid, i;

  if (report)
    memset(report, 0, sizeof(*report));
  if (!kernel || !report || !kernel->self || !kernel->refer || !kernel->terminate ||
      !kernel->remove || !kernel->create || (protect_count && !protect))
    return -EINVAL;

  report->self = kernel->self(ctx);
  if (report->self < 1 || report->self >= POPS_HANDOFF_MAX_THREADS)
    return -EINVAL;

  /* Look first: nothing is terminated if one of the frames the kernel would
   * rewrite lies in memory that is already prepared for POPS. A DORMANT
   * thread is only deleted, which writes nothing. */
  for (tid = 1; tid < POPS_HANDOFF_MAX_THREADS; ++tid) {
    if (tid == report->self || !thread_in_use(kernel, ctx, tid, &thread))
      continue;
    if (thread.status != POPS_HANDOFF_THS_DORMANT && frame_overlaps(&thread, protect, protect_count)) {
      report->failed_tid = tid;
      return -EFAULT;
    }
  }

  /* The kernel's own loop bound (ExecPS2, 0x80005858): ids 1..255. A thread
   * that is not DORMANT is terminated first; DeleteThread takes DORMANT
   * threads only, so its result covers both calls. */
  for (tid = 1; tid < POPS_HANDOFF_MAX_THREADS; ++tid) {
    if (tid == report->self || !thread_in_use(kernel, ctx, tid, &thread))
      continue;
    if (thread.status != POPS_HANDOFF_THS_DORMANT)
      kernel->terminate(ctx, tid);
    if (kernel->remove(ctx, tid) < 0) {
      report->failed_tid = tid;
      return -EBUSY;
    }
    retired[nretired++] = (uint8_t)tid;
  }
  report->retired = nretired;
  report->first_retired = nretired ? retired[0] : 0;

  if (nretired) {
    /* Take every free slot, in the order the kernel hands them out. */
    memset(seen, 0, sizeof(seen));
    while (ncreated < POPS_HANDOFF_MAX_THREADS - 1) {
      int id = kernel->create(ctx);
      if (id < 0)
        break;
      if (id < 1 || id >= POPS_HANDOFF_MAX_THREADS || id == report->self || seen[id]) {
        report->failed_tid = id;
        result = -EIO;
        break;
      }
      seen[id] = 1;
      created[ncreated++] = (uint8_t)id;
    }
    report->drained = ncreated;

    /* First-in first-out (what the kernel was measured to do): the slots
     * freed above come out last, in the order they were freed. Release them
     * first and the rest behind them, and the queue is what it was before
     * launcHER's threads existed. Anything else: release in reverse, which
     * leaves a last-in first-out pool exactly as it was found. */
    fifo = !result && ncreated >= nretired &&
           !memcmp(created + (ncreated - nretired), retired, (size_t)nretired);
    if (fifo) {
      for (i = ncreated - nretired; i < ncreated; ++i)
        if (kernel->remove(ctx, created[i]) < 0 && !result) {
          report->failed_tid = created[i];
          result = -EBUSY;
        }
      for (i = 0; i < ncreated - nretired; ++i)
        if (kernel->remove(ctx, created[i]) < 0 && !result) {
          report->failed_tid = created[i];
          result = -EBUSY;
        }
      report->queue = POPS_HANDOFF_QUEUE_RESTORED;
    } else {
      for (i = ncreated - 1; i >= 0; --i)
        if (kernel->remove(ctx, created[i]) < 0 && !result) {
          report->failed_tid = created[i];
          result = -EBUSY;
        }
      report->queue = POPS_HANDOFF_QUEUE_AS_FOUND;
    }
  }

  /* Whatever happened above, POPS must not inherit a thread or a lost slot. */
  for (tid = 1; tid < POPS_HANDOFF_MAX_THREADS; ++tid) {
    if (tid != report->self && thread_in_use(kernel, ctx, tid, NULL)) {
      if (!result) {
        report->failed_tid = tid;
        result = -EBUSY;
      }
      break;
    }
  }
  return result;
}
