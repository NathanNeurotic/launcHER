#ifndef LAUNCHER_HANDLER_SMB_H
#define LAUNCHER_HANDLER_SMB_H
#include <stdint.h>
char *initTCPIPArguments(uint32_t *length);
int launcher_smb_connect(void);
void launcher_smb_reset(void);
#endif
