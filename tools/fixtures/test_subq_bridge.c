/* Compile the real SubQ bridge policy with host mocks; contract tests for
 * the interception mechanism (not Sony IOPCD behavior, which is an open
 * hardware-traced gate). */
#include "../../launcher/iop/pops_iomanx/src/pops_subq_bridge.h"
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static char last_dev[16];
static int last_cmd, mock_result;
static uint8_t last_arg[8], mock_q[12];
static size_t last_arglen, last_buflen;

static int mock_devctl(const char *dev, int cmd, void *arg, size_t arglen, void *buf, size_t buflen) {
  strcpy(last_dev, dev);
  last_cmd = cmd;
  last_arglen = arglen;
  last_buflen = buflen;
  if (arg && arglen)
    memcpy(last_arg, arg, arglen);
  if (buf && buflen >= 12 && mock_result == 0)
    memcpy(buf, mock_q, 12);
  return mock_result;
}

int main(void) {
  uint8_t out[12];
  uint32_t lba = 0x00001234u;

  /* Unconfigured bridge intercepts nothing. */
  pops_subq_bridge_reset();
  assert(!pops_subq_bridge_configured());
  assert(!pops_subq_bridge_should_intercept("cdrom0:", 5));

  /* Policy installation and matching. */
  assert(pops_subq_bridge_configure("cdrom0", 5) == 0);
  assert(pops_subq_bridge_configured());
  assert(pops_subq_bridge_should_intercept("cdrom0:", 5));
  assert(pops_subq_bridge_should_intercept("cdrom0", 5));
  assert(!pops_subq_bridge_should_intercept("cdrom1:", 5));
  assert(!pops_subq_bridge_should_intercept("cdrom0:", 4));
  assert(!pops_subq_bridge_should_intercept("pops:", 5));
  assert(pops_subq_bridge_configure("", 5) == -EINVAL);
  assert(pops_subq_bridge_configure(NULL, 5) == -EINVAL);
  assert(pops_subq_bridge_configure("cdrom0", -1) == -EINVAL);

  /* The query path issues the documented popfs GET_SUBQ contract. */
  mock_result = 0;
  memset(mock_q, 0xAB, sizeof(mock_q));
  memset(out, 0, sizeof(out));
  assert(pops_subq_bridge_query(lba, out, sizeof(out), mock_devctl) == 0);
  assert(!strcmp(last_dev, "pops:") && last_cmd == 0x06);
  assert(last_arglen == 4);
  assert(memcmp(last_arg, &lba, 4) == 0);
  assert(last_buflen == 12);
  assert(memcmp(out, mock_q, 12) == 0);

  /* popfs failures (e.g. -ERANGE) propagate untouched. */
  mock_result = -34;
  assert(pops_subq_bridge_query(lba, out, sizeof(out), mock_devctl) == -34);

  /* A missing callback is rejected. */
  assert(pops_subq_bridge_query(lba, out, sizeof(out), NULL) == -EINVAL);

  puts("POPFS-iomanX SubQ bridge contract PASS: policy matching, popfs GET_SUBQ forwarding, error propagation");
  return 0;
}
