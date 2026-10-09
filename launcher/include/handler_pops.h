#ifndef _HANDLER_POPS_H_
#define _HANDLER_POPS_H_

#include "common.h"

// Returns 1 if path points to a POPS target (e.g. .vcd file)
int isPopsTarget(const char *path);

// Launches a PS1 game using our external POPS backend
int launchPOPS(int argc, char *argv[]);

// Searches candidate locations for POPS dependencies (PAK or ELF+IOPRP)
int findPopsDependencies(const char *vcdPath, char *popsPath, size_t popsPathSize,
                         char *ioprpPath, size_t ioprpPathSize);

// Loads custom user modules (MODULE_0..9.IRX, peripheral IRXs, MODULES.TXT)
int pops_load_custom_modules(const char *vcdDir, const char *vmcDir);

// Loads SMB network protocol stack from memory card for SB. launches
int pops_load_smb_stack(const char *vcdDir, const char *vmcDir);

#endif
