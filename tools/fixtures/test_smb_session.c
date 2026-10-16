#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <ps2smb.h>
#include "handler_smb.h"

static const char *config = "192.168.1.100:1445 PS2SMB\nuser\npassword\n";
static size_t offset;
static unsigned commands[8], failure;
static int calls;
int fileXioOpen(const char *path, int flags, ...) {
    (void)flags;
    if (!strstr(path,"SMBCONFIG.DAT")) return -ENOENT;
    offset=0;return 7;
}
int fileXioRead(int fd, void *buffer, int size) {
    assert(fd==7);
    size_t n=strlen(config)-offset;if(n>(size_t)size)n=(size_t)size;
    memcpy(buffer,config+offset,n);offset+=n;return (int)n;
}
int fileXioClose(int fd) { assert(fd==7);return 0; }
void msg(const char *fmt,...) { (void)fmt; }
int fileXioDevctl(const char *name,int cmd,void *arg,unsigned arglen,void *out,unsigned outlen) {
    (void)out;(void)outlen;
    assert(!strcmp(name,"smb:"));assert(calls<8);commands[calls++]=cmd;
    if((unsigned)cmd==SMB_DEVCTL_LOGON) {
      smbLogOn_in_t *p=arg;assert(arglen==sizeof(*p));
      assert(!strcmp(p->serverIP,"192.168.1.100")&&p->serverPort==1445);
      assert(!strcmp(p->User,"user")&&!strcmp(p->Password,"password"));
      assert(p->PasswordType==PLAINTEXT_PASSWORD);
    } else if((unsigned)cmd==SMB_DEVCTL_OPENSHARE) {
      smbOpenShare_in_t *p=arg;assert(arglen==sizeof(*p));assert(!strcmp(p->ShareName,"PS2SMB"));
    } else assert((unsigned)cmd==SMB_DEVCTL_LOGOFF);
    return (unsigned)cmd==failure ? -EACCES : 0;
}
int main(void) {
    assert(launcher_smb_connect()==0);
    assert(calls==2&&commands[0]==SMB_DEVCTL_LOGON&&commands[1]==SMB_DEVCTL_OPENSHARE);
    assert(launcher_smb_connect()==0&&calls==2);
    launcher_smb_reset(); calls=0; failure=SMB_DEVCTL_OPENSHARE;
    assert(launcher_smb_connect()==-EACCES&&calls==3&&commands[2]==SMB_DEVCTL_LOGOFF);
    calls=0;failure=SMB_DEVCTL_LOGON;
    assert(launcher_smb_connect()==-EACCES&&calls==1);
    calls=0;failure=0;config="invalid configuration\n";
    assert(launcher_smb_connect()==-EINVAL&&calls==0);
    puts("SMB login/share ordering, failure rollback and reset PASS");return 0;
}
