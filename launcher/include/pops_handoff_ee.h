#ifndef _POPS_HANDOFF_EE_H_
#define _POPS_HANDOFF_EE_H_

/* Terminates and deletes every EE thread but the caller and puts the
 * kernel's free thread slots back in order (common/include/pops_handoff.h).
 * The last call before the POPS trampoline: after it nothing may wait on
 * another thread, an alarm or an RPC. Returns 0, or a negative errno value
 * with every prepared area untouched. */
int popsHandoffRetireThreads(void);

#endif
