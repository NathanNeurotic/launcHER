#include "pops_subq_bridge.h"
#include <errno.h>
#include <string.h>

static char pops_subq_prefix[16];
static int pops_subq_cmd = -1;

int pops_subq_bridge_configure(const char *device_prefix, int cmd)
{
    size_t len;
    if (!device_prefix || cmd < 0)
        return -EINVAL;
    len = strlen(device_prefix);
    if (len == 0 || len >= sizeof(pops_subq_prefix))
        return -EINVAL;
    memcpy(pops_subq_prefix, device_prefix, len + 1);
    pops_subq_cmd = cmd;
    return 0;
}

void pops_subq_bridge_reset(void)
{
    pops_subq_prefix[0] = 0;
    pops_subq_cmd = -1;
}

int pops_subq_bridge_configured(void)
{
    return pops_subq_prefix[0] != 0 && pops_subq_cmd >= 0;
}

int pops_subq_bridge_should_intercept(const char *name, int cmd)
{
    size_t len;
    if (!pops_subq_bridge_configured() || !name || cmd != pops_subq_cmd)
        return 0;
    len = strlen(pops_subq_prefix);
    if (strncmp(name, pops_subq_prefix, len) != 0)
        return 0;
    /* Accept the bare prefix or a device unit suffix ("cdrom0" / "cdrom0:"). */
    return name[len] == 0 || name[len] == ':';
}

int pops_subq_bridge_query(uint32_t lba, void *buf, size_t buflen,
                           pops_subq_devctl_fn fn)
{
    if (!fn || !buf)
        return -EINVAL;
    return fn(POPS_SUBQ_BRIDGE_POPFS_DEV, POPS_SUBQ_BRIDGE_POPFS_GET_SUBQ,
              &lba, sizeof(lba), buf, buflen);
}
