#include "pops_external.h"
#include <stdint.h>

static int mock_identify_status = 0;

void test_set_mock_identify_status(int status) {
  mock_identify_status = status;
}

int pops_core_image_identify(const void *core, size_t size) {
  (void)core;
  (void)size;
  return mock_identify_status;
}

int pops_core_image_identify_baseline_patched(const void *core, size_t size) {
  (void)core;
  (void)size;
  return mock_identify_status;
}
