#ifndef LAUNCHER_HANDLER_SMB_H
#define LAUNCHER_HANDLER_SMB_H
#include <stdint.h>
char *initTCPIPArguments(uint32_t *length);
int launcher_smb_connect(void);
void launcher_smb_reset(void);
/* POPStarter's rules for IPCONFIG.DAT and SMBCONFIG.DAT are used only for a
 * PS1 launch whose name carries SB. (docs/POPSTARTER_SMB_CONFIG.md). `pops`
 * says whether the target being launched is a PS1 disc image; every other
 * launch keeps the launcher's own rules whatever its name. */
void launcher_smb_set_pops_target(int pops);
#endif
