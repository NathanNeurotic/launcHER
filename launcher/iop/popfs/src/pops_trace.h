#ifndef POPS_TRACE_H
#define POPS_TRACE_H
/*
 * Sony-phase event trace for the popfs IOP bridge.
 *
 * ps2link dies at the foreign IOP reboot, so nothing printed during Sony
 * execution reaches the host. popfs survives on the IOP and can write a
 * bounded event log to the backing device instead; a later probe run reads
 * the log file. Events recorded: Subchannel-Q requests (LibCrypt evidence),
 * pad-swap fires, and EE-driven NEXT_DISC switches.
 *
 * All calls are best-effort: a failed open disables tracing, never the
 * caller. The log is bounded (POPS_TRACE_EVENT_LIMIT) to protect the device.
 */
#include <stddef.h>
#include <stdint.h>

/* Configure the trace target from the disc0 backing path ("mass2:/x/y" ->
 * "mass2:popfs_trace.log"). Call once from module start; safe to skip. */
void pops_trace_init(const char *disc0_path);
void pops_trace_reset(void);

void pops_trace_event(const char *kind, uint32_t a, uint32_t b, uint32_t c);

#define POPS_TRACE_EVENT_LIMIT 128

#endif /* POPS_TRACE_H */
