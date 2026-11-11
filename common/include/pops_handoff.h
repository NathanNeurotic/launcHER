#ifndef LAUNCHER_POPS_HANDOFF_H
#define LAUNCHER_POPS_HANDOFF_H

#include <stddef.h>
#include <stdint.h>

/* The last step before the POPS trampoline: leave the EE kernel with one
 * thread, as POPStarter r13 has when it calls ExecPS2 (it has no
 * CreateThread or StartThread stub at all; see docs/POPSTARTER_HANDOFF_STATE.md).
 *
 * Why it matters. ExecPS2 terminates and deletes every thread but the
 * caller (EE kernel 0x800057e8, loop over ids 1..255). Terminating a thread
 * that is not DORMANT rebuilds its initial context at
 * stack + stack_size - 0x2a0 and stores gp, sp, fp and ra there
 * (0x80003bb8: +0x1c0, +0x1d0, +0x1e0, +0x1f0). launcHER has such a thread
 * (ps2sdk libkernel's helper, a 0x400-byte stack in launcHER's own BSS), and
 * by the time the trampoline calls ExecPS2 that memory belongs to POPS. So
 * the threads are terminated and deleted here, while their stacks are still
 * launcHER's: ExecPS2 then finds nothing to reset.
 *
 * The kernel keeps free thread slots in a first-in first-out queue
 * (0x80005b00 takes from one end, 0x80005bb0 adds to the other), so a slot
 * freed here would be handed out last and POPS's threads would get ids one
 * higher than after POPStarter. The slots are therefore put back in front,
 * in their old order: every free slot is taken once (DORMANT threads that
 * never run), then released with the retired ones first.
 *
 * Pure logic: the kernel is reached through the table below, so host tests
 * run it against a model of the thread table. */

#define POPS_HANDOFF_MAX_THREADS    256   /* ids 1..255; 0 is the kernel's idle thread */
#define POPS_HANDOFF_THS_DORMANT    0x10
#define POPS_HANDOFF_RESET_FRAME    UINT32_C(0x2a0) /* bytes below a stack's end the kernel rewrites */

/* Eight words the launcher leaves below 1 MiB, behind the trampoline's
 * arguments, for whoever reads RAM afterwards: magic, result, then the
 * report's six fields. No trace line can be printed after the threads are
 * gone. */
#define POPS_HANDOFF_REPORT_ADDR    UINT32_C(0x00084300)
#define POPS_HANDOFF_REPORT_MAGIC   UINT32_C(0x464f4850) /* "PHOF" */

typedef struct {
  int status;           /* 0: free slot; POPS_HANDOFF_THS_DORMANT: created, not started */
  uint32_t stack;
  uint32_t stack_size;
} PopsHandoffThread;

typedef struct {
  int (*self)(void *ctx);                                     /* GetThreadId */
  int (*refer)(void *ctx, int tid, PopsHandoffThread *out);   /* ReferThreadStatus; < 0: no such id */
  int (*terminate)(void *ctx, int tid);                       /* TerminateThread */
  int (*remove)(void *ctx, int tid);                          /* DeleteThread; < 0 on failure */
  int (*create)(void *ctx);                                   /* CreateThread of a DORMANT thread; < 0: no slot left */
} PopsHandoffKernel;

/* Memory that is already prepared for POPS when the threads are retired;
 * a thread whose reset frame lies in one of these is refused. */
typedef struct {
  uint32_t start;
  uint32_t end;         /* exclusive */
} PopsHandoffRange;

enum {
  POPS_HANDOFF_QUEUE_UNTOUCHED = 0,   /* no other thread: nothing was created or deleted */
  POPS_HANDOFF_QUEUE_RESTORED = 1,    /* first-in first-out queue, retired slots back in front */
  POPS_HANDOFF_QUEUE_AS_FOUND = 2     /* not the measured queue order: slots released in reverse */
};

typedef struct {
  int self;             /* the calling thread's id */
  int retired;          /* other threads terminated and deleted */
  int first_retired;    /* lowest id among them, 0 if none */
  int drained;          /* free slots taken and released for the queue order */
  int queue;            /* POPS_HANDOFF_QUEUE_* */
  int failed_tid;       /* thread id an error is about, 0 if none */
} PopsHandoffReport;

/* Returns 0 with every thread id but the caller's free. Errors (negative
 * errno values; the report names the thread):
 *   -EINVAL  bad arguments or a caller id outside 1..255
 *   -EFAULT  a thread's reset frame overlaps a protected range (nothing has
 *            been terminated yet when this is returned)
 *   -EBUSY   a thread could not be deleted, or a slot is still in use
 *   -EIO     the kernel handed out an id it should not have */
int pops_handoff_retire_threads(const PopsHandoffKernel *kernel, void *ctx,
                                const PopsHandoffRange *protect, size_t protect_count,
                                PopsHandoffReport *report);

#endif
