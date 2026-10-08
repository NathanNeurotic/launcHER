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

#endif
