/* Real Sony IOP image + IOPCD, real SIF RPC, production IOMANX/fileXio/POPFS.
 * Only the storage medium is a controlled in-memory IOP driver. */
#include <kernel.h>
#include <iopcontrol.h>
#include <iopcontrol_special.h>
#include <loadfile.h>
#include <sbv_patches.h>
#include <sifrpc.h>
#include <stdio.h>
#include <sio.h>
#include <stdarg.h>
#include <string.h>
#include <stdint.h>
#ifdef POPS_BINDING_STARTUP_TRACE
#include <smem.h>
#include "diagnostic_popfs_irx.h"
#endif
#ifdef POPS_BINDING_CONSOLE_SCREEN
#include <debug.h>
#endif
#define NEWLIB_PORT_AWARE
#include <fileXio_rpc.h>
#include "pops_bootstrap.h"
#include "binding_backend_irx.h"

#define IRX(name) extern unsigned char name##_irx[]; extern unsigned int size_##name##_irx
IRX(iomanX); IRX(fileXio); IRX(popfs); IRX(sony_iopcd); IRX(sony_ioprp);
static SifRpcClientData_t cd __attribute__((aligned(64)));
static uint32_t request[32] __attribute__((aligned(64)));
static unsigned char reply[0x9740] __attribute__((aligned(64)));
static unsigned char bytes[1024] __attribute__((aligned(64)));
#ifndef POPS_BINDING_CONSOLE_SCREEN
static int reserved[2];
#endif
static int stage;

/* EE serial output survives IOP reset and appears in PCSX2's EE console. */
static int probe_printf(const char *format, ...) {
  char text[512]; va_list ap;
  va_start(ap, format);
  int length = vsnprintf(text, sizeof(text), format, ap);
  va_end(ap);
  if (length > 0) sio_write(text, (unsigned)length < sizeof(text) ? length : sizeof(text) - 1);
#ifdef POPS_BINDING_CONSOLE_SCREEN
  scr_printf("%s", text);
#endif
  return length;
}
#define printf probe_printf
#define puts(text) probe_printf("%s\n", text)

#ifdef POPS_BINDING_STARTUP_TRACE
static unsigned char worker_stack[16384] __attribute__((aligned(64)));
static volatile int worker_done, worker_id, worker_result;
static const char *worker_args;
static unsigned worker_length;
extern void *_gp;
static void load_worker(void *unused) {
  (void)unused;
  int start = -999;
  int id = SifExecModuleBuffer(diagnostic_popfs_irx, size_diagnostic_popfs_irx,
                              worker_length, worker_args, &start);
  worker_id = id; worker_result = start; worker_done = 1;
  ExitThread();
}
static void wake_main(s32 alarm, u16 ticks, void *common) {
  (void)alarm; (void)ticks; iWakeupThread((int)(uintptr_t)common);
}
static int trace_start(unsigned length, const char *args) {
  ee_thread_t thread = {0};
  worker_args = args; worker_length = length; worker_done = 0;
  thread.func = load_worker; thread.stack = worker_stack; thread.stack_size = sizeof(worker_stack);
  thread.gp_reg = &_gp; thread.initial_priority = 32;
  int id = CreateThread(&thread);
  if (id < 0) return id;
  StartThread(id, NULL);
  unsigned words[1024] __attribute__((aligned(64)));
  for (unsigned tick = 0; tick < 12; ++tick) {
    SetAlarm(16000, wake_main, (void *)(uintptr_t)GetThreadId()); SleepThread();
    unsigned found = 0;
    for (unsigned base = 0x1000; base < 0x200000; base += sizeof(words)) {
      smem_read((void *)(uintptr_t)base, words, sizeof(words));
      for (unsigned i = 0; i + 7 < 1024; ++i) if (words[i] == 0x504f5046 && words[i+1] == 0x44494147) {
        printf("POPS_IOP_BINDING trace tick=%u addr=%08x stage=%u value=%08x\n",
               tick, base + i * 4, words[i+2], words[i+3]); ++found;
      }
    }
    if (!found) printf("POPS_IOP_BINDING trace tick=%u no-loaded-marker\n", tick);
    if (worker_done) {
      printf("POPS_IOP_BINDING diagnostic-popfs id=%d start=%d\n", worker_id, worker_result);
      return worker_id < 0 ? worker_id : worker_result ? -1000 - worker_result : 0;
    }
  }
  return -4000; /* diagnostic timeout, no hardware acceptance */
}
#endif

static int load(const char *name, void *data, unsigned size, unsigned length, const char *args) {
  int result = -999;
  printf("POPS_IOP_BINDING load=%s\n", name); fflush(stdout);
  int id = SifExecModuleBuffer(data, size, length, args, &result);
  printf("POPS_IOP_BINDING module=%s id=%d start=%d\n", name, id, result); fflush(stdout);
  return id < 0 ? id : result ? -1000 - result : 0;
}
static int rpc(int function, void *send, int size, void *recv, int recv_size) {
  return sceSifCallRpc(&cd, function, 0, send, size, recv, recv_size, NULL, NULL);
}
static int fingerprint(const unsigned char *data, unsigned offset, unsigned length) {
  for (unsigned i = 0; i < length; ++i) if (data[i] != (offset + i) % 251u) return 0;
  return 1;
}
int main(void) {
  int result, fd;
  char args[512];
#ifdef POPS_BINDING_CONSOLE_SCREEN
  init_scr();
#endif
  sio_init(115200, 0, 0, 0, 0);
  printf("POPS_IOP_BINDING begin\n"); fflush(stdout);
  sceSifInitRpc(0);
  stage = 1;
  result = SifIopRebootBuffer(sony_ioprp_irx, size_sony_ioprp_irx);
  if (result <= 0) goto fail;
  while (!SifIopSync()) {}
  sceSifInitRpc(0);
  printf("POPS_IOP_BINDING foreign-reset-complete\n"); fflush(stdout);
  sbv_patch_enable_lmb();
  sbv_patch_disable_prefix_check();
  stage = 2;
  if ((result = load("production-iomanX", iomanX_irx, size_iomanX_irx, 0, NULL))) goto fail;
  stage = 3;
  if ((result = load("production-fileXio", fileXio_irx, size_fileXio_irx, 0, NULL))) goto fail;
  stage = 4;
  if ((result = load("controlled-backend", binding_backend_irx, size_binding_backend_irx, 0, NULL))) goto fail;
  stage = 5;
  int length = pops_format_proxy_args_mode(args, sizeof(args), "trace0:/disc",
      "trace0:/card0", "trace0:/card1", NULL, NULL, NULL, 1);
  if (length < 0) { result = length; goto fail; }
#ifdef POPS_BINDING_STARTUP_TRACE
  if ((result = trace_start(length, args))) goto fail;
#else
  if ((result = load("production-popfs", popfs_irx, size_popfs_irx, length, args))) goto fail;
#endif
  stage = 6;
  if ((result = fileXioInit()) < 0) goto fail;
#ifndef POPS_BINDING_CONSOLE_SCREEN
  /* PCSX2 IopBios.cpp write_HLE treats every imported write(fd=1) as
   * console output, even if Sony's file table allocated it to a real file.
   * Keep 0/1 occupied only in this emulator fixture, never in production. */
  for (unsigned i = 0; i < 2; ++i) {
    reserved[i] = fileXioOpen("trace0:/disc", 1, 0);
    if (reserved[i] < 0) { result = reserved[i]; goto fail; }
  }
  printf("POPS_IOP_BINDING emulator-reserved-fds=%d,%d\n", reserved[0], reserved[1]);
#endif
  const char *names[] = {"pops0:IMAGE.VCD", "pfs0:/IMAGE.VCD"};
  for (unsigned i = 0; i < 2; ++i) {
    fd = fileXioOpen(names[i], 1, 0);
    if (fd < 0) { result = fd; goto fail; }
    result = fileXioRead(fd, bytes, 1024);
    if (fileXioClose(fd) < 0 || result != 1024 || !fingerprint(bytes, 0, 1024)) goto fail;
  }
  printf("POPS_IOP_BINDING fileXio-aliases-pass\n"); fflush(stdout);
  stage = 7;
  if ((result = load("original-Sony-IOPCD", sony_iopcd_irx, size_sony_iopcd_irx, 0, NULL))) goto fail;
  memset(&cd, 0, sizeof(cd));
  while (!cd.server) if ((result = sceSifBindRpc(&cd, 0x435052, 0)) < 0) goto fail;
  stage = 8;
  request[0] = 0; /* original Sony file mode */
  if ((result = rpc(0x435052, request, 16, NULL, 0)) < 0) goto fail;
  memset(request, 0, sizeof(request));
  strcpy((char *)request, "pfs0:/IMAGE.VCD");
  if ((result = rpc(0x435053, request, 128, reply, 16)) < 0) goto fail;
  result = *(int *)reply;
  if (result != 1024) goto fail;
  if ((result = rpc(0x435055, NULL, 0, reply, 1024)) < 0 || !fingerprint(reply, 0, 1024)) goto fail;
  stage = 9;
  const uint32_t reads[][2] = {{0, 16}, {16, 16}, {1234, 16}, {4999, 2}, {5000, 1}};
  for (unsigned i = 0; i < 5; ++i) {
    unsigned offset = 0x100000u + reads[i][0] * 2352u;
    request[0] = reads[i][0]; request[1] = reads[i][1]; request[2] = 0;
    request[3] = offset; request[4] = 0;
    memset(reply, 0xcc, sizeof(reply));
    if ((result = rpc(0x435056, request, 20, reply, sizeof(reply))) < 0) goto fail;
    uint32_t *header = (uint32_t *)reply;
    if (header[0] != request[0] || header[1] != request[1] || header[4] != (offset & 511) ||
        !fingerprint(reply + 20 + header[4], offset, request[1] * 2352)) { result = -2000 - i; goto fail; }
    printf("POPS_IOP_BINDING sony-read lba=%lu count=%lu offset=%lu PASS\n",
        (unsigned long)request[0], (unsigned long)request[1], (unsigned long)offset); fflush(stdout);
  }
  if ((result = rpc(0x435054, NULL, 0, NULL, 0)) < 0) goto fail;
  stage = 10;
  /* Save data survives close/reopen on a controlled IOP memory medium. */
  for (unsigned test = 0; test < 4; ++test) {
    unsigned slot = test % 2;
    char name[32]; snprintf(name, sizeof(name), test < 2 ? "trace0:/card%u" : "pops0:SLOT%u.VMC", slot);
    fd = fileXioOpen(name, 3, 0);
    if (fd < 0) { result = fd; goto fail; }
    for (unsigned i = 0; i < sizeof(bytes); ++i) bytes[i] = (i + test * 71) % 253;
    int seek = fileXioLseek(fd, 4096, 0);
    int written = fileXioWrite(fd, bytes, sizeof(bytes));
    int closed = fileXioClose(fd);
    printf("POPS_IOP_BINDING card-write path=%s fd=%d seek=%d write=%d close=%d\n", name, fd, seek, written, closed);
    if (seek != 4096 || written != sizeof(bytes) || closed < 0) { result = -3000; goto fail; }
    fd = fileXioOpen(name, 3, 0);
    if (fd < 0 || fileXioLseek(fd, 4096, 0) != 4096 || fileXioRead(fd, bytes, sizeof(bytes)) != sizeof(bytes) ||
        fileXioClose(fd) < 0) { result = -3001; goto fail; }
    for (unsigned i = 0; i < sizeof(bytes); ++i) if (bytes[i] != (i + test * 71) % 253) {
      printf("POPS_IOP_BINDING card-mismatch slot=%u index=%u expected=%u actual=%u uncached=%u\n",
          slot, i, (i + test * 71) % 253, bytes[i], ((volatile unsigned char *)UNCACHED_SEG(bytes))[i]);
      result = -3002; goto fail;
    }
  }
#ifndef POPS_BINDING_CONSOLE_SCREEN
  for (unsigned i = 0; i < 2; ++i) if ((result = fileXioClose(reserved[i])) < 0) goto fail;
#endif
  puts("POPS_IOP_BINDING_PASS real_Sony_IOP=1 real_SIF_RPC=1 media=controlled");
  puts("[ps2rig] exit=0"); fflush(stdout); SleepThread(); return 0;
fail:
  printf("POPS_IOP_BINDING_FAIL stage=%d result=%d\n", stage, result);
  puts("[ps2rig] exit=1"); fflush(stdout); SleepThread(); return 1;
}
