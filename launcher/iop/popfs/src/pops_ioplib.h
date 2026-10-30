#ifndef POPS_IOPLIB_H
#define POPS_IOPLIB_H
/*
 * Minimal IOP export-table interposition helpers for popfs, following the
 * mmceman/ioplib approach (taken from the MX4SIO driver; all credits go to
 * maximus32 and the ps2dev project, Academic Free License v2.0).
 *
 * IOP-only: not compiled into the host contract tests.
 */
#include <irx.h>
#include <loadcore.h>

typedef int (*pops_ioplib_libiterate_cb_t)(iop_library_t *lib, void *userdata);

int pops_ioplib_iterate_by_name(const char *name, pops_ioplib_libiterate_cb_t cb, void *userdata);
unsigned int pops_ioplib_get_table_size(iop_library_t *lib);
void *pops_ioplib_hook_same_export_entries(iop_library_t *lib, unsigned int entry, void *func);
void pops_ioplib_relink_exports(iop_library_t *lib);

#endif /* POPS_IOPLIB_H */
