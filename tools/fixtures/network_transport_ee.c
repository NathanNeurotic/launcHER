/* Controlled filesystem test after a plain IOP reset. No Sony/game inputs. */
#include <kernel.h>
#include <iopcontrol.h>
#include <sifrpc.h>
#include <loadfile.h>
#include <sbv_patches.h>
#include <debug.h>
#include <sio.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#define NEWLIB_PORT_AWARE
#include <fileXio_rpc.h>
#include <io_common.h>
#include "handler_smb.h"

#define IRX(n) extern unsigned char n##_irx[]; extern unsigned int size_##n##_irx
IRX(iomanX); IRX(fileXio); IRX(sio2man); IRX(mcman); IRX(mcserv);
IRX(ps2dev9); IRX(netman); IRX(smap_tcpip); IRX(ps2ip_nm); IRX(launcher_smbman);
IRX(smap); IRX(ministack); IRX(udpfs_ioman); IRX(bdm); IRX(bdmfs_fatfs); IRX(udpbd);
IRX(udptty);
static int logger_ready;
static unsigned char copy_bytes[16384] __attribute__((aligned(64)));
static unsigned char verify_bytes[16384] __attribute__((aligned(64)));

static int report(const char *format,...) {
  char text[512];va_list ap;va_start(ap,format);
  int n=vsnprintf(text,sizeof(text),format,ap);va_end(ap);
  scr_printf("%s",text);
  if(n>0) {
    unsigned length=(unsigned)n<sizeof(text)?(unsigned)n:sizeof(text)-1;
    sio_write(text,length);
    if(logger_ready) fileXioWrite(1,text,length);
  }
  return n;
}
void msg(const char *format,...) {
  char text[256];va_list ap;va_start(ap,format);
  vsnprintf(text,sizeof(text),format,ap);va_end(ap);report("%s",text);
}
#define printf report
#include "fixture_io.h"

static int module(const char *name,void *data,unsigned size,unsigned length,const char *args) {
  int started=-99;
  report("NETWORK_STACK loading=%s\n",name);
  int id=SifExecModuleBuffer(data,size,length,args,&started);
  report("NETWORK_STACK loaded=%s id=%d start=%d\n",name,id,started);
  return id<0?id:(started? -EIO:0);
}
#define LOAD(n) do { result=module(#n,n##_irx,size_##n##_irx,0,NULL);if(result)goto done; } while(0)

int main(int argc,char **argv) {
  init_scr();sio_init(115200,0,0,0,0);
  int result=-EINVAL;
  if(argc!=3 || (strcmp(argv[1],"smb")&&strcmp(argv[1],"udpfs")&&strcmp(argv[1],"udpbd"))) goto done;
  int smb=!strcmp(argv[1],"smb"), udpfs=!strcmp(argv[1],"udpfs");
  if(strncmp(argv[2],smb?"smb0:/":(udpfs?"udpfs:/":"udpbd0:/"),smb?6:(udpfs?7:8))) goto done;
  report("NETWORK_STACK_RESET transport=%s no_Sony_inputs=1\n",argv[1]);
  sceSifInitRpc(0);
  while(!SifIopReset("",0)) {}
  while(!SifIopSync()) {}
  sceSifInitRpc(0);sbv_patch_enable_lmb();sbv_patch_disable_prefix_check();
  sbv_patch_fileio();
  LOAD(iomanX);LOAD(fileXio);LOAD(sio2man);LOAD(mcman);LOAD(mcserv);LOAD(ps2dev9);
  report("NETWORK_STAGE step=filexio_init\n");
  result=fileXioInit();
  report("NETWORK_STAGE step=filexio_init_ok result=%d\n",result);
  if(result<0) goto done;
  report("NETWORK_STAGE step=read_tcpip_args\n");
  uint32_t arg_size=0;
  char *args=initTCPIPArguments(&arg_size);
  if(!args) { report("NETWORK_STAGE_FAIL step=read_tcpip_args\n");result=-ENOENT;goto done; }
  report("NETWORK_STAGE step=read_tcpip_args_ok size=%u\n",(unsigned)arg_size);
  if(smb) {
    LOAD(netman);LOAD(smap_tcpip);
    result=module("ps2ip_nm",ps2ip_nm_irx,size_ps2ip_nm_irx,arg_size,args);
    free(args);if(result)goto done;
    report("NETWORK_STAGE step=ps2ip_nm_ready\n");
    LOAD(udptty);logger_ready=1;
    LOAD(launcher_smbman);
    report("NETWORK_STAGE step=smb_connect\n");
    launcher_smb_reset();result=launcher_smb_connect();
    report("NETWORK_STAGE step=smb_connect_result result=%d\n",result);
    if(result)goto done;
  } else {
    char mini_args[20];snprintf(mini_args,sizeof(mini_args),"ip=%s",args);free(args);
    LOAD(smap);
    result=module("ministack",ministack_irx,size_ministack_irx,strlen(mini_args)+1,mini_args);
    if(result)goto done;
    report("NETWORK_STAGE step=ministack_ready\n");
    LOAD(udptty);logger_ready=1;
    if(udpfs) { LOAD(udpfs_ioman); }
    else { LOAD(bdm);LOAD(bdmfs_fatfs);LOAD(udpbd); }
  }
  /* UDPBD registration follows an asynchronous info reply. Do not issue writes
   * until the server has advertised and the filesystem opens the fixture. */
  if(!smb&&!udpfs) sleep(2);
  report("NETWORK_STAGE step=fixture_test target=%s\n",argv[2]);
  result=network_fixture_test(argv[2]);
  report("NETWORK_STAGE step=fixture_test_done result=%d\n",result);
done:
  report("NETWORK_STACK_RESULT transport=%s result=%d fresh_IOP=1\n",argc>1?argv[1]:"invalid",result);
  report("[ps2rig] exit=%d\n",result?1:0);
  SleepThread();return result?1:0;
}
