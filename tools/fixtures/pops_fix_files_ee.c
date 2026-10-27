/* Owned synthetic PATCH records. No Sony code, games, saves or IOP reset. */
#include "pops_modes_patches.h"
#include <kernel.h>
#include <sifrpc.h>
#include <debug.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* Generated from the independent original-write metadata, not production C. */
#include "expected_fix_results.h"
static uint8_t core[0x302e60] __attribute__((aligned(64)));
static uint8_t record[68];

static void word(uint8_t *p, uint32_t value) {
  for (unsigned i=0;i<4;++i) p[i]=(uint8_t)(value>>(8*i));
}
static void reset_core(void) {
  memset(core,0,sizeof(core));
  word(core+0x10318,0x8f828228);word(core+0x1032c,0x1443fffa);
  word(core+0x83c,0x0441000a);word(core+0x85c,0x1000fffa);
  word(core+0xde9c,0x0c0836ee);core[0x1af70]=0x64;word(core+0x525b0,0x1bfc);
}
static uint32_t checksum(const void *memory, size_t size) {
  const uint8_t *bytes=memory;uint32_t value=2166136261u;
  for(size_t i=0;i<size;++i) value=(value^bytes[i])*16777619u;
  return value;
}
static void patch(unsigned first, unsigned second) {
  memset(record,0,sizeof(record));memcpy(record,"PATCH_0",7);
  word(record+8,1);word(record+12,0x10001);
  memcpy(record+32,"owned",5);record[56]=first;record[57]=second;
}

int main(void) {
  static const unsigned modes[]={1,2,3,4,5,7};
  PopsFixContext context;
  unsigned cases=0;
  int result=0;
  sceSifInitRpc(0);
  init_scr();
  scr_printf("POPS_FIX_FILES_BEGIN synthetic_core=1 Sony_entry_executed=0\n");
  for(unsigned i=0;i<6&&!result;++i) {
    for(unsigned j=0;j<6&&!result;++j) {
      scr_printf("POPS_FIX_FILES_CASE first=%u second=%u\n",modes[i],modes[j]);
      reset_core();patch(modes[i],modes[j]);
      result=pops_fix_context_init(&context,core,sizeof(core),0);
      if(!result) result=pops_fix_stage(&context,core,sizeof(core),record,64,0,0);
      if(!result&&checksum(core,sizeof(core))!=expected_fix_results[i][j]) result=-100;
      if(!result) ++cases;
    }
  }
  if(!result) {
    uint32_t before=checksum(core,sizeof(core));
    uint32_t state=checksum(&context,sizeof(context));
    patch(8,1);word(record+16,0x220000);word(record+28,4);
    memcpy(record+64,"DATA",4);
    if(pops_fix_stage(&context,core,sizeof(core),record,sizeof(record),0,0)>=0||
       before!=checksum(core,sizeof(core))||state!=checksum(&context,sizeof(context))) result=-101;
    else ++cases;
  }
  scr_printf("POPS_FIX_FILES_%s cases=%u result=%d Sony_entry_executed=0\n",
         result?"FAIL":"PASS",cases,result);
  printf("POPS_FIX_FILES_%s cases=%u result=%d Sony_entry_executed=0\n",
         result?"FAIL":"PASS",cases,result);
  printf("[ps2rig] exit=%d\n",result?1:0);
  fflush(stdout);
  SleepThread();
  return result?1:0;
}
