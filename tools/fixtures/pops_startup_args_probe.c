/* Execute only the original parser prefix, stopping before runtime init.
 * Sony code/data is supplied by the local-only preparer, never committed. */
#include <kernel.h>
#include <stdio.h>
#include <string.h>
extern void pops_startup_install(void);
extern void pops_startup_call(int argc,char **argv);
int main(void) {
  pops_startup_install();
  char *inputs[]={"pops0:IMAGE.VCD","pfs0:IMAGE.VCD",
      "hdd0:PART:pfs0:/POPS/Tekken.VCD","pops0:IMAGE","IMAGE.VCD"};
  const char *names[]={"VCD","VCD","VCD","",""};
  const char *routes[]={"pops0:IMAGE.VCD","pfs0:IMAGE.VCD","hdd0:PART","",""};
  int failed=0;
  for(unsigned i=0;i<sizeof(inputs)/sizeof(inputs[0]);++i) {
    memset((void *)0x5030c8,0,768);
    pops_startup_call(1,&inputs[i]);
    printf("POPS_STARTUP_ARGS input=%s name=%s route=%s\n",inputs[i],
        (char *)0x5030c8,(char *)0x5031c8);
    if(strcmp((char *)0x5030c8,names[i]) || strcmp((char *)0x5031c8,routes[i])) failed=1;
  }
  memset((void *)0x5030c8,0,768);
  pops_startup_call(0,NULL);
  if (failed || *(char *)0x5030c8 || *(char *)0x5031c8) {
    puts("POPS_STARTUP_ARGS_FAIL measured output mismatch"); puts("[ps2rig] exit=1");
  } else {
    puts("POPS_STARTUP_ARGS_PASS bounded parser prefix, runtime init not executed");
    puts("[ps2rig] exit=0");
  }
  fflush(stdout); SleepThread();return 0;
}
