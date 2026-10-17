#include <kernel.h>
#include <debug.h>
#include <stdio.h>
#include <string.h>
static const unsigned initialized=0x13579bdf;
static volatile unsigned zeroed[128];
int main(int argc,char **argv) {
  init_scr();
  int bad=argc!=1 || !argv || !argv[0] || strcmp(argv[0],"pops0:IMAGE.VCD") ||
      initialized!=0x13579bdf;
  for(unsigned i=0;i<128;++i) if(zeroed[i]) bad=1;
  printf("POPS_TRAMPOLINE child argc=%d arg=%s\n",argc,argv&&argv[0]?argv[0]:"null");
  scr_printf("POPS_TRAMPOLINE_%s owned child entered argc=%d\n",bad?"FAIL":"PASS",argc);
  printf("POPS_TRAMPOLINE_%s owned child entered\n",bad?"FAIL":"PASS");
  printf("[ps2rig] exit=%d\n",bad?1:0);
  fflush(stdout); SleepThread();return bad?1:0;
}
