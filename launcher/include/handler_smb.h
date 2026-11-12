#ifndef LAUNCHER_HANDLER_SMB_H
#define LAUNCHER_HANDLER_SMB_H
#include <stdint.h>
char *initTCPIPArguments(uint32_t *length);
int launcher_smb_connect(void);
void launcher_smb_reset(void);
/* POPStarter's rules for IPCONFIG.DAT and SMBCONFIG.DAT are used only for a
 * PS1 launch whose SB. state is on (docs/POPSTARTER_SMB_CONFIG.md).
 * `popstarter` says whether the target being dispatched is one; every other
 * launch keeps the launcher's own rules whatever its name. Returns nonzero
 * when the loaded network modules were set up under the other rules, so they
 * must be loaded again for this target. */
int launcher_smb_set_target(int popstarter);
#endif
