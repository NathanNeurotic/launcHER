#include <assert.h>
#include <stdio.h>
#include "fatfs_host_sdk.h"
#include "ff.h"
#include "../../launcher/iop/pops_fatfs/src/fs_driver.c"

static FRESULT injected;
static BYTE opened_mode;
static int existing;
static unsigned writes, stored = 0x5a;
static FATFS volume;
int CreateSema(iop_sema_t *s) { (void)s; return 1; }
int DeleteSema(int id) { (void)id; return 0; }
int WaitSema(int id) { (void)id; return 0; }
int SignalSema(int id) { (void)id; return 0; }
int iomanX_AddDrv(iop_device_t *d) { (void)d; return 0; }
int iomanX_DelDrv(const char *n) { (void)n; return 0; }
FRESULT f_mount(FATFS *fs, const char *p, BYTE b) { (void)fs;(void)p;(void)b;return injected; }
FRESULT f_open(FIL *f, const char *p, BYTE mode) {
  (void)p; opened_mode=mode;
  if (injected) return injected;
  if (existing && (mode & FA_CREATE_NEW)) return FR_EXIST;
  if (mode & FA_CREATE_ALWAYS) stored=0;
  f->obj.fs=&volume; return FR_OK;
}
FRESULT f_close(FIL *f) { f->obj.fs=NULL; return injected; }
FRESULT f_read(FIL *f, void *b, UINT n, UINT *out) { (void)f;(void)b;(void)n;*out=3;return injected; }
FRESULT f_write(FIL *f, const void *b, UINT n, UINT *out) { (void)f;(void)b;(void)n;writes++;*out=3;return injected; }
FRESULT f_lseek(FIL *f, FSIZE_t off) { f->fptr=off;return injected; }
FRESULT f_unlink(const char *p) { (void)p;return injected; }
FRESULT f_mkdir(const char *p) { (void)p;return injected; }
FRESULT f_opendir(DIR *d, const char *p) { (void)p;if(!injected)d->obj.fs=&volume;return injected; }
FRESULT f_closedir(DIR *d) { d->obj.fs=NULL;return injected; }
FRESULT f_readdir(DIR *d, FILINFO *f) { (void)d;memset(f,0,sizeof(*f));return injected; }
FRESULT f_stat(const char *p, FILINFO *f) { (void)p;memset(f,0,sizeof(*f));return injected; }
FRESULT f_rename(const char *p, const char *n) { (void)p;(void)n;return injected; }
DWORD get_fat(FFOBJID *f, DWORD c) { (void)f;return c+1; }
uint64_t clst2sect(FATFS *f, DWORD c) { (void)f;return c; }

int main(void) {
  iop_file_t fd={0}; iox_stat_t st; iox_dirent_t entry; char data[8];
  FIL file={0}; DIR dir={0};
  const int errors[]={0,EIO,EIO,ENXIO,ENOENT,ENOENT,EINVAL,EACCES,EEXIST,
    EBADF,EROFS,ENODEV,ENODEV,ENODEV,EIO,ETIMEDOUT,EBUSY,ENOMEM,EMFILE,EINVAL};
  fd.device=&fs_driver;
  InitFS();
  for (unsigned i=0;i<sizeof(errors)/sizeof(errors[0]);i++) {
    injected=(FRESULT)i;
    assert(fatfs_result(injected)==-errors[i]);
    if (!i) continue;
    assert(fs_open(&fd,"missing",O_RDONLY,0)==-errors[i]);
    assert(fd.privdata==NULL);
    assert(fs_getstat(&fd,"missing",&st)==-errors[i]);
    assert(fs_remove(&fd,"missing")==-errors[i]);
    assert(fs_mkdir(&fd,"missing",0)==-errors[i]);
    assert(fs_rename(&fd,"old","new")==-errors[i]);
    assert(fs_dopen(&fd,"missing")==-errors[i]);
    assert(fd.privdata==NULL);
    fd.privdata=&file;
    assert(fs_read(&fd,data,sizeof(data))==-errors[i]);
    assert(fs_write(&fd,data,sizeof(data))==-errors[i]);
    assert(fs_lseek64(&fd,0,SEEK_SET)==-errors[i]);
    assert(fs_close(&fd)==-errors[i]);
    assert(fd.privdata==NULL);
    fd.privdata=&dir;
    assert(fs_dread(&fd,&entry)==-errors[i]);
    assert(fs_dclose(&fd)==-errors[i]);
    assert(fd.privdata==NULL);
  }
  assert(fatfs_result((FRESULT)1234)==-EIO);
  assert(fs_dclose(&fd)==-EBADF);
  injected=FR_OK; existing=1;
  unsigned writes_before= writes;
  assert(fs_open(&fd,"existing-save",O_WRONLY|O_CREAT|O_EXCL|O_TRUNC|O_APPEND,0)==-EEXIST);
  assert(opened_mode==(FA_WRITE|FA_CREATE_NEW));
  assert(stored==0x5a && writes==writes_before);
  existing=0;
  assert(fs_open(&fd,"new-save",O_WRONLY|O_CREAT|O_EXCL,0)==1);
  assert(fs_write(&fd,data,sizeof(data))==3);
  assert(fs_read(&fd,data,sizeof(data))==3);
  assert(fs_close(&fd)==0);
  assert(fs_dopen(&fd,"dir")==0);
  assert(fs_dread(&fd,&entry)==0); /* Successful empty directory: EOF. */
  assert(fs_dclose(&fd)==0);
  puts("FatFs filesystem error propagation and exclusive-create contracts: PASS");
  return 0;
}
