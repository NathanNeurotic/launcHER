#ifndef _INIT_H_
#define _INIT_H_

#include "common.h"

// Reboots the IOP and executes a path from ROM via LoadExecPS2
int execROMPath(int argc, char *argv[]);

// Shuts down the console. Needs initModules(Device_Basic) to be called first.
void shutdownPS2();

// Sets IOP emulation flags for Deckard consoles. Needs initModules(Device_Basic) to be called first
void applyXPARAM(char *gameID);

// Initializes IOP modules for given device type
int initModules(DeviceType device);

// Loads the drivers for every device type in `devices` at once, skipping a block device driver whose
// hardware is absent instead of failing. Used to find launcHER.CNF behind a generic massN: path. The
// next initModules always reboots the IOP, so a launch target still gets exactly its own drivers.
int initModulesAny(DeviceType devices);

#endif
