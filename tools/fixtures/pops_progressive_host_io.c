#include <stdint.h>

typedef uint64_t (*ReadFn)(uint32_t address, unsigned width);
typedef void (*WriteFn)(uint32_t address, uint64_t value, unsigned width);
static ReadFn reader;
static WriteFn writer;

void pops_progressive_test_io(ReadFn read_fn, WriteFn write_fn) {
  reader = read_fn;
  writer = write_fn;
}

uint64_t pops_progressive_read(uint32_t address, unsigned width) {
  return reader(address, width);
}

void pops_progressive_write(uint32_t address, uint64_t value, unsigned width) {
  writer(address, value, width);
}
