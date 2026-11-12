#ifndef LAUNCHER_SMB_OPEN_CONTRACT_H
#define LAUNCHER_SMB_OPEN_CONTRACT_H
/* Included after the target's O_* definitions (IOP flags differ from host).
 * FILE_CREATE fails atomically if a file exists, including when TRUNC is set. */
static inline unsigned launcher_smb_nt_disposition(int flags) {
    if ((flags & (O_CREAT | O_EXCL)) == (O_CREAT | O_EXCL)) return 2;
    if (flags & O_TRUNC) return (flags & O_CREAT) ? 5 : 4;
    return (flags & O_CREAT) ? 3 : 1;
}
/* SMB_COM_OPEN_ANDX: low bits = existing-file action; high bits = absent action. */
static inline unsigned launcher_smb_legacy_disposition(int flags) {
    if ((flags & (O_CREAT | O_EXCL)) == (O_CREAT | O_EXCL)) return 0x10;
    return ((flags & O_CREAT) ? 0x10 : 0) | ((flags & O_TRUNC) ? 2 : 1);
}
#endif
