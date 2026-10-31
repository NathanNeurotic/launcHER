#include "pops_ioplib.h"
#include <intrman.h>

/* Vendored from mmceman's ioplib.c (ps2dev / maximus32, AFL 2.0); trimmed to
 * what the popfs pad-swap interposition needs. */
int pops_ioplib_iterate_by_name(const char *name, pops_ioplib_libiterate_cb_t cb, void *userdata)
{
    iop_library_t *libptr;
    int i;
    int count;

    count = 0;
    libptr = GetLoadcoreInternalData()->let_next;
    while (libptr != NULL) {
        for (i = 0; i < 8; i++) {
            if (libptr->name[i] != name[i])
                break;
        }
        if (i == 8) {
            count += 1;
            if (cb(libptr, userdata))
                break;
        }
        libptr = libptr->prev;
    }
    return count;
}

unsigned int pops_ioplib_get_table_size(iop_library_t *lib)
{
    void **exp;
    unsigned int size;

    exp = NULL;
    if (lib != NULL) {
        exp = lib->exports;
    }
    size = 0;

    if (exp != NULL)
        while (*exp++ != NULL)
            size++;

    return size;
}

void *pops_ioplib_hook_same_export_entries(iop_library_t *lib, unsigned int entry, void *func)
{
    int table_size;
    int oldstate;
    void *oldfunc;
    unsigned int i;

    table_size = (int)pops_ioplib_get_table_size(lib);
    if (entry >= (unsigned int)table_size)
        return NULL;

    CpuSuspendIntr(&oldstate);
    oldfunc = lib->exports[entry];
    for (i = 0; i < (unsigned int)table_size; i += 1)
        if (lib->exports[i] == oldfunc)
            lib->exports[i] = func;
    CpuResumeIntr(oldstate);

    return oldfunc;
}

void pops_ioplib_relink_exports(iop_library_t *lib)
{
    struct irx_import_table *table;
    struct irx_import_stub *stub;

    /* Rewrite every already-linked import stub so existing importers
     * (Sony's padman among them) reach the patched export. */
    for (table = lib->caller; table != NULL; table = table->next) {
        for (stub = (struct irx_import_stub *)table->stubs; stub->jump != 0; stub++) {
            stub->jump = 0x08000000 | (((u32)lib->exports[stub->fno] << 4) >> 6);
        }
    }
}
