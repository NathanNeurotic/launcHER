#include <irx.h>
#include <loadcore.h>

#include "main.h"
#include "udpbd.h"

IRX_ID(MODNAME, 0x1, 0x0);

int _start(int argc, char *argv[])
{
    (void)argc; (void)argv;
    if (udpbd_init() != 0) return MODULE_NO_RESIDENT_END;
    return MODULE_RESIDENT_END;
}
