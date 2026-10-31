#ifndef LAUNCHER_POPS_VMC_H
#define LAUNCHER_POPS_VMC_H

/* Preserve existing raw 128 KiB cards; create only absent cards. Returns a
 * negative errno on failure. Existing files are never reformatted or resized. */
int pops_vmc_ensure(const char *path);

#endif
