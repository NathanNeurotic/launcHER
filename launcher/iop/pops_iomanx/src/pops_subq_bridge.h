#ifndef POPS_SUBQ_BRIDGE_H
#define POPS_SUBQ_BRIDGE_H
/*
 * LibCrypt Subchannel-Q bridge for pops_iomanx.
 *
 * Policy: while configured, iomanX_devctl(name, cmd, ...) pairs matching the
 * registered device prefix and command are answered from popfs's existing
 * POPS_DEVCTL_GET_SUBQ handler instead of reaching the registered device.
 * The Q frames carry the LibCrypt key that the launcher forwarded with
 * POPS_DEVCTL_SET_LIBCRYPT (see launcher/src/handler_pops.c).
 *
 * Evidence status (2026-10-30): the Q generator, the key forwarding, and
 * this interception mechanism are host-verified. The intercepted device name
 * and command constant are a documented hypothesis for Sony's IOPCD
 * subchannel path; a hardware trace must confirm or retarget them (open
 * gate, see docs/evidence/pops_resident_lifecycle.md). The module loads with
 * the bridge configured and can be reconfigured at runtime through
 * pops_subq_bridge_configure().
 */
#include <stddef.h>
#include <stdint.h>

/* popfs devctl contract (launcher/iop/popfs/src/popfs.c). */
#define POPS_SUBQ_BRIDGE_POPFS_DEV "pops:"
#define POPS_SUBQ_BRIDGE_POPFS_GET_SUBQ 0x06

typedef int (*pops_subq_devctl_fn)(const char *dev, int cmd, void *arg,
                                   size_t arglen, void *buf, size_t buflen);

/* Install or replace the interception policy. prefix is matched exactly or
 * followed by ':'. Returns 0 on success, -EINVAL on malformed input. */
int pops_subq_bridge_configure(const char *device_prefix, int cmd);
void pops_subq_bridge_reset(void);
int pops_subq_bridge_configured(void);
int pops_subq_bridge_should_intercept(const char *name, int cmd);

/* Answer one Subchannel-Q request through the supplied devctl function,
 * which the iomanX layer implements as a normal iomanX_devctl call against
 * the popfs device. Returns the devctl result (0 on a 12-byte Q frame). */
int pops_subq_bridge_query(uint32_t lba, void *buf, size_t buflen,
                           pops_subq_devctl_fn fn);

#endif /* POPS_SUBQ_BRIDGE_H */
