#ifndef LAUNCHER_FATFS_ERRNO_H
#define LAUNCHER_FATFS_ERRNO_H
#include <errno.h>
#include "ff.h"

/* IOMAN/fileXio expose negative errno, never FatFs's unrelated ordinal codes. */
static int fatfs_result(FRESULT result)
{
    switch (result) {
        case FR_OK: return 0;
        case FR_NO_FILE:
        case FR_NO_PATH: return -ENOENT;
        case FR_NOT_READY: return -ENXIO;
        case FR_INVALID_NAME:
        case FR_INVALID_PARAMETER: return -EINVAL;
        case FR_DENIED: return -EACCES;
        case FR_EXIST: return -EEXIST;
        case FR_INVALID_OBJECT: return -EBADF;
        case FR_WRITE_PROTECTED: return -EROFS;
        case FR_INVALID_DRIVE:
        case FR_NOT_ENABLED:
        case FR_NO_FILESYSTEM: return -ENODEV;
        case FR_TIMEOUT: return -ETIMEDOUT;
        case FR_LOCKED: return -EBUSY;
        case FR_NOT_ENOUGH_CORE: return -ENOMEM;
        case FR_TOO_MANY_OPEN_FILES: return -EMFILE;
        case FR_DISK_ERR:
        case FR_INT_ERR:
        case FR_MKFS_ABORTED:
        default: return -EIO;
    }
}
#endif
