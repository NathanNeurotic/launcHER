#ifndef FATFS_HOST_SDK_H
#define FATFS_HOST_SDK_H
#include "popfs_host_sdk.h"
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef iomanX_iop_file_t iop_file_t;
typedef iomanX_iop_device_t iop_device_t;
typedef iomanX_iop_device_ops_t iop_device_ops_t;
#define AddDrv iomanX_AddDrv
#define DelDrv iomanX_DelDrv
#define O_RDONLY FIO_O_RDONLY
#define O_WRONLY FIO_O_WRONLY
#define O_CREAT FIO_O_CREAT
#define O_TRUNC FIO_O_TRUNC
#define O_APPEND FIO_O_APPEND
#define O_EXCL FIO_O_EXCL
#define FIO_S_IROTH 4
#define FIO_S_IXOTH 1
#define FIO_S_IFREG 0x2000
typedef struct { int initial, max, option, attr; } iop_sema_t;
int CreateSema(iop_sema_t *s);
int DeleteSema(int id);
int WaitSema(int id);
int SignalSema(int id);
struct block_device {
  char *name, *path;
  unsigned devNr;
  u64 sectorOffset;
  int (*stop)(struct block_device *);
};
typedef struct { u64 sector; unsigned count; } bd_fragment_t;
#define USBMASS_IOCTL_RENAME 0
#define USBMASS_IOCTL_GET_CLUSTER 1
#define USBMASS_IOCTL_GET_LBA 2
#define USBMASS_IOCTL_GET_DRIVERNAME 3
#define USBMASS_IOCTL_CHECK_CHAIN 4
#define USBMASS_IOCTL_GET_FRAGLIST 5
#define USBMASS_IOCTL_GET_DEVICE_NUMBER 6
#define USBMASS_DEVCTL_STOP_UNIT 0
#define USBMASS_DEVCTL_STOP_ALL 1
#endif
