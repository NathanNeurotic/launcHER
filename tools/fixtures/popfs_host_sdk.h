#ifndef POPFS_HOST_SDK_H
#define POPFS_HOST_SDK_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>
typedef int64_t s64;
#define IRX_ID(name, major, minor)
#define MODULE_RESIDENT_END 0
#define MODULE_NO_RESIDENT_END 1
#define FIO_O_RDONLY 1
#define FIO_S_IFDIR 0x1000
#define FIO_S_IRUSR 0x100
#define FIO_S_IWUSR 0x80
#define FIO_S_IXUSR 0x40
#define IOP_DT_FS 0x10
#define IOP_DT_FSEXT 0x10000000
typedef struct { unsigned mode; unsigned size; } iox_stat_t;
typedef struct { iox_stat_t stat; char name[256]; } iox_dirent_t;
typedef struct _file {
  int mode, unit;
  struct _device *device;
  void *privdata;
} iomanX_iop_file_t;
typedef struct _ops {
  int (*init)(struct _device *);
  int (*deinit)(struct _device *);
  int (*format)(iomanX_iop_file_t *, const char *, const char *, void *, int);
  int (*open)(iomanX_iop_file_t *, const char *, int, int);
  int (*close)(iomanX_iop_file_t *);
  int (*read)(iomanX_iop_file_t *, void *, int);
  int (*write)(iomanX_iop_file_t *, void *, int);
  int (*lseek)(iomanX_iop_file_t *, int, int);
  int (*ioctl)(iomanX_iop_file_t *, int, void *);
  int (*remove)(iomanX_iop_file_t *, const char *);
  int (*mkdir)(iomanX_iop_file_t *, const char *, int);
  int (*rmdir)(iomanX_iop_file_t *, const char *);
  int (*dopen)(iomanX_iop_file_t *, const char *);
  int (*dclose)(iomanX_iop_file_t *);
  int (*dread)(iomanX_iop_file_t *, iox_dirent_t *);
  int (*getstat)(iomanX_iop_file_t *, const char *, iox_stat_t *);
  int (*chstat)(iomanX_iop_file_t *, const char *, iox_stat_t *, unsigned);
  int (*rename)(iomanX_iop_file_t *, const char *, const char *);
  int (*chdir)(iomanX_iop_file_t *, const char *);
  int (*sync)(iomanX_iop_file_t *, const char *, int);
  int (*mount)(iomanX_iop_file_t *, const char *, const char *, int, void *, int);
  int (*umount)(iomanX_iop_file_t *, const char *);
  s64 (*lseek64)(iomanX_iop_file_t *, s64, int);
  int (*devctl)(iomanX_iop_file_t *, const char *, int, void *, unsigned, void *, unsigned);
  int (*symlink)(iomanX_iop_file_t *, const char *, const char *);
  int (*readlink)(iomanX_iop_file_t *, const char *, char *, unsigned);
  int (*ioctl2)(iomanX_iop_file_t *, int, void *, unsigned, void *, unsigned);
} iomanX_iop_device_ops_t;
typedef struct _device {
  const char *name;
  unsigned type, version;
  const char *desc;
  iomanX_iop_device_ops_t *ops;
} iomanX_iop_device_t;
#define IOMANX_RETURN_VALUE_IMPL(val) static int mock_ret_##val(void) { return -(val); }
#define IOMANX_RETURN_VALUE(val) ((void *)&mock_ret_##val)
int CpuSuspendIntr(int *state);
int CpuResumeIntr(int state);
int iomanX_AddDrv(iomanX_iop_device_t *);
int iomanX_open(const char *, int, ...);
int iomanX_close(int);
int iomanX_read(int, void *, int);
int iomanX_write(int, void *, int);
int iomanX_lseek(int, int, int);
s64 iomanX_lseek64(int, s64, int);
int iomanX_ioctl(int, int, void *);
int iomanX_ioctl2(int, int, void *, unsigned, void *, unsigned);
int iomanX_getstat(const char *, iox_stat_t *);
int iomanX_remove(const char *);
int iomanX_rename(const char *, const char *);
int iomanX_sync(const char *, int);
#endif
