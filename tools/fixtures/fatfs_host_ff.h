#ifndef FATFS_HOST_FF_H
#define FATFS_HOST_FF_H
#include <stdint.h>
typedef uint8_t BYTE;
typedef uint16_t WORD;
typedef uint32_t DWORD;
typedef unsigned UINT;
typedef uint64_t FSIZE_t;
typedef struct { unsigned pdrv, csize; DWORD n_fatent; } FATFS;
typedef struct { FATFS *fs; FSIZE_t objsize; DWORD sclust; } FFOBJID;
typedef struct { FFOBJID obj; FSIZE_t fptr; } FIL;
typedef struct { FFOBJID obj; } DIR;
typedef struct { WORD fdate, ftime; FSIZE_t fsize; BYTE fattrib; char fname[256]; } FILINFO;
typedef enum {
  FR_OK, FR_DISK_ERR, FR_INT_ERR, FR_NOT_READY, FR_NO_FILE, FR_NO_PATH,
  FR_INVALID_NAME, FR_DENIED, FR_EXIST, FR_INVALID_OBJECT, FR_WRITE_PROTECTED,
  FR_INVALID_DRIVE, FR_NOT_ENABLED, FR_NO_FILESYSTEM, FR_MKFS_ABORTED,
  FR_TIMEOUT, FR_LOCKED, FR_NOT_ENOUGH_CORE, FR_TOO_MANY_OPEN_FILES,
  FR_INVALID_PARAMETER
} FRESULT;
#define FF_VOLUMES 10
#define FA_READ 1
#define FA_WRITE 2
#define FA_CREATE_NEW 4
#define FA_CREATE_ALWAYS 8
#define FA_OPEN_ALWAYS 16
#define FA_OPEN_APPEND 48
#define FA_OPEN_EXISTING 0
#define AM_DIR 16
#define AM_RDO 1
FRESULT f_mount(FATFS *, const char *, BYTE);
#define f_unmount(path) f_mount(NULL, path, 0)
FRESULT f_open(FIL *, const char *, BYTE);
FRESULT f_close(FIL *);
FRESULT f_read(FIL *, void *, UINT, UINT *);
FRESULT f_write(FIL *, const void *, UINT, UINT *);
FRESULT f_lseek(FIL *, FSIZE_t);
FRESULT f_unlink(const char *);
FRESULT f_mkdir(const char *);
FRESULT f_opendir(DIR *, const char *);
FRESULT f_closedir(DIR *);
FRESULT f_readdir(DIR *, FILINFO *);
FRESULT f_stat(const char *, FILINFO *);
FRESULT f_rename(const char *, const char *);
DWORD get_fat(FFOBJID *, DWORD);
uint64_t clst2sect(FATFS *, DWORD);
#endif
