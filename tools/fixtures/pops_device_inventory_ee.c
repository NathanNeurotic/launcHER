#include <kernel.h>
#include <sifrpc.h>
#include <loadfile.h>
#include <sbv_patches.h>
#include <smod.h>
#include <slib.h>
#include <smem.h>
#include <stdio.h>
#include <unistd.h>
#include <debug.h>
#include <sio.h>
#include <stdarg.h>
#include <string.h>
#define NEWLIB_PORT_AWARE
#include <fileXio_rpc.h>
#include "production_names.h"
static int screen_printf(const char *format, ...) {
  char text[512]; va_list ap; va_start(ap, format);
  int n = vsnprintf(text, sizeof(text), format, ap); va_end(ap);
  scr_printf("%s", text);
  if (n > 0) sio_write(text, (unsigned)n < sizeof(text) ? n : sizeof(text) - 1);
  return n;
}
#define printf screen_printf
#define puts(text) screen_printf("%s\n", text)
#define IRX(name) extern unsigned char name##_irx[]; extern unsigned int size_##name##_irx
IRX(iomanX); IRX(sio2man); IRX(mcman); IRX(mcserv); IRX(bdm); IRX(bdmfs_fatfs);
IRX(usbd_mini); IRX(usbmass_bd_mini); IRX(mmceman);
IRX(fileXio);
static iox_dirent_t entry __attribute__((aligned(64)));
static char selected_vcd[512];
static unsigned selected_size;
static int vcd_name(const char *name) {
  size_t n = strlen(name);
  return n >= 4 && name[n-4] == '.' &&
      (name[n-3] == 'v' || name[n-3] == 'V') &&
      (name[n-2] == 'c' || name[n-2] == 'C') &&
      (name[n-1] == 'd' || name[n-1] == 'D');
}
static void directory(const char *path) {
  scr_clear(); scr_setXY(0, 0);
  printf("POPS_INVENTORY directory=%s\n", path);
  int fd = fileXioDopen(path);
  if (fd < 0) { printf("POPS_INVENTORY dopen=%d\n", fd); return; }
  for (int n = 0; n < 128; ++n) {
    int r = fileXioDread(fd, &entry);
    if (r <= 0) break;
    entry.name[sizeof(entry.name) - 1] = 0;
    if (vcd_name(entry.name)) {
      printf("POPS_INVENTORY VCD=%s%s size=%u\n", path, entry.name, (unsigned)entry.stat.size);
      size_t path_length = strlen(path), name_length = strlen(entry.name);
      if (!selected_vcd[0] && path_length + name_length < sizeof(selected_vcd)) {
        memcpy(selected_vcd, path, path_length);
        memcpy(selected_vcd + path_length, entry.name, name_length + 1);
        selected_size = entry.stat.size;
      }
    }
  }
  printf("POPS_INVENTORY dclose=%d\n", fileXioDclose(fd));
}
static int load(const char *name, void *data, unsigned size) {
  int start = -99;
  printf("POPS_INVENTORY load=%s\n", name); fflush(stdout);
  int id = SifExecModuleBuffer(data, size, 0, NULL, &start);
  printf("POPS_INVENTORY loaded=%s id=%d start=%d\n", name, id, start); fflush(stdout);
  return id < 0 || start != 0;
}
#define LOAD(name) if (load(#name, name##_irx, size_##name##_irx)) goto fail
#define LOAD_MISSING(name) if (!smod_get_mod_by_name(MODULE_NAME_##name, &module)) { LOAD(name); }
int main(void) {
  smod_mod_info_t module;
  char name[96];
  init_scr(); sio_init(115200, 0, 0, 0, 0);
  sceSifInitRpc(0);
  int present = smod_get_next_mod(NULL, &module);
  for (unsigned n = 0; present && n < 128; ++n) {
    smem_read(module.name, name, sizeof(name)); name[sizeof(name) - 1] = 0;
    /* The rig's broad exception classifier mistakes Exception_Manager's
     * ordinary module name for a crash. Only list non-kernel modules here. */
    if (module.id >= 25) printf("POPS_INVENTORY module=%s id=%u\n", name, module.id);
    present = smod_get_next_mod(&module, &module);
  }
  sceSifInitRpc(0);
  sbv_patch_enable_lmb();
  /* ps2link normally has no storage drivers. Add the launcher's production
   * USB/MMCE stack once; preserve inherited network and device drivers. */
  if (!slib_get_exp_lib("iomanx", NULL)) { LOAD(iomanX); }
  LOAD_MISSING(fileXio);
  LOAD_MISSING(sio2man);
  LOAD_MISSING(mcman);
  LOAD_MISSING(mcserv);
  LOAD_MISSING(bdm);
  LOAD_MISSING(bdmfs_fatfs);
  LOAD_MISSING(usbd_mini);
  LOAD_MISSING(usbmass_bd_mini);
  LOAD_MISSING(mmceman);
  sleep(3);
  puts("POPS_INVENTORY scanning connected storage"); fflush(stdout);
  if (fileXioInit() < 0) goto fail;
  const char *paths[] = {"mass0:/", "mass0:/POPS/", "mass1:/POPS/", "mass2:/POPS/",
      "mmce0:/POPS/", "mmce1:/POPS/", "mc0:/POPS/", "mc1:/POPS/", "pfs0:/POPS/"};
  for (unsigned i = 0; i < sizeof(paths) / sizeof(paths[0]); ++i) directory(paths[i]);
  scr_clear(); scr_setXY(0, 0);
  puts("POPS_INVENTORY COMPLETE read-only");
  printf("POPS_INVENTORY selected=%s size=%u\n", selected_vcd[0] ? selected_vcd : "none", selected_size);
  puts("[ps2rig] exit=0");
  fflush(stdout); SleepThread(); return 0;
fail:
  puts("[ps2rig] exit=1"); fflush(stdout); SleepThread(); return 1;
}
