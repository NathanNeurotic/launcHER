/* Owned payload only. Execute the actual production trampoline and kernel
 * ExecPS2 path without any Sony core, foreign IOP reset, game or save data. */
#include <kernel.h>
#include <sifrpc.h>
#include <debug.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "pops_bootstrap.h"
extern unsigned char child_irx[];
extern unsigned int size_child_irx;
extern unsigned char pops_trampoline_code[], pops_trampoline_code_end[];
static uint32_t word(const unsigned char *p) { uint32_t v; memcpy(&v,p,4);return v; }
static uint16_t half(const unsigned char *p) { uint16_t v; memcpy(&v,p,2);return v; }
int main(void) {
  sceSifInitRpc(0);
  init_scr();
  unsigned char *stage=(void *)POPS_STAGING_BASE;
  unsigned count=half(child_irx+44), stride=half(child_irx+42);
  uint32_t phoff=word(child_irx+28);
  if (size_child_irx<52 || memcmp(child_irx,"\177ELF",4) || stride<32 ||
      !count || count>32 || phoff>size_child_irx || count>(size_child_irx-phoff)/stride)
    goto fail;
  memset(stage,0,0x302e60);
  for (unsigned i=0;i<count;++i) {
    unsigned char *ph=child_irx+phoff+i*stride;
    if (word(ph)!=1) continue;
    uint32_t off=word(ph+4), addr=word(ph+8), files=word(ph+16), memory=word(ph+20);
    if (addr<POPS_CORE_ADDR || addr>POPS_BSS_ADDR || memory>POPS_BSS_ADDR-addr ||
        files>memory || off>size_child_irx || files>size_child_irx-off) goto fail;
    memcpy(stage+addr-POPS_CORE_ADDR,child_irx+off,files);
  }
  PopsTrampolineArgs *args=(void *)POPS_TRAMPOLINE_ARGS;
  memset(args,0,sizeof(*args));
  args->entry=word(child_irx+24);
  args->bss_address=POPS_BSS_ADDR; args->bss_size=POPS_BSS_SIZE;
  args->scratchpad_size=POPS_SPAD_SIZE;
  args->staging_core=POPS_STAGING_BASE;
  args->core_address=POPS_CORE_ADDR; args->core_size=0x302e60;
  args->argc=1; args->argv[0]=POPS_TRAMPOLINE_ARGS+48;
  strcpy(args->arg_strings,"pops0:IMAGE.VCD");
  size_t bytes=pops_trampoline_code_end-pops_trampoline_code;
  if (!bytes || bytes>0x180) goto fail;
  memcpy((void *)POPS_TRAMPOLINE_ADDR,pops_trampoline_code,bytes);
  FlushCache(0); FlushCache(2);
  printf("POPS_TRAMPOLINE parent entry=%08x code=%u disable_interrupts=%d\n",
      (unsigned)args->entry,(unsigned)bytes,PROBE_DISABLE_INTERRUPTS);
  fflush(stdout);
  if (PROBE_DISABLE_INTERRUPTS) DIntr();
  ((void (*)(void *))POPS_TRAMPOLINE_ADDR)(args);
fail:
  puts("POPS_TRAMPOLINE_FAIL parent"); puts("[ps2rig] exit=1");
  fflush(stdout); SleepThread();return 1;
}
