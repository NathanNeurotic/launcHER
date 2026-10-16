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
#include <errno.h>
#define NEWLIB_PORT_AWARE
#include <fileXio_rpc.h>
#include <io_common.h>
#include "production_names.h"
#include "pops_vcd.h"
#include "pops_config.h"
#include "network_config.h"
#include "handler_smb.h"
static int screen_printf(const char *format, ...) {
  char text[512]; va_list ap; va_start(ap, format);
  int n = vsnprintf(text, sizeof(text), format, ap); va_end(ap);
  scr_printf("%s", text);
  if (n > 0) sio_write(text, (unsigned)n < sizeof(text) ? n : sizeof(text) - 1);
  /* This probe preserves ps2link, so retain a machine-readable network log. */
  fputs(text, stdout); fflush(stdout);
  return n;
}
#define printf screen_printf
#define puts(text) screen_printf("%s\n", text)
void msg(const char *format, ...) {
  char text[256]; va_list ap; va_start(ap,format);
  vsnprintf(text,sizeof(text),format,ap); va_end(ap);
  screen_printf("%s",text);
}
#define IRX(name) extern unsigned char name##_irx[]; extern unsigned int size_##name##_irx
IRX(iomanX); IRX(sio2man); IRX(mcman); IRX(mcserv); IRX(bdm); IRX(bdmfs_fatfs);
IRX(usbd_mini); IRX(usbmass_bd_mini); IRX(mmceman);
IRX(mx4sio_bd_mini); IRX(ata_bd);
IRX(fileXio);
IRX(launcher_smbman);
static iox_dirent_t entry __attribute__((aligned(64)));
static char selected_vcd[512];
static unsigned selected_size;
static char directories[96][512];
static unsigned depths[96], directory_count, directory_next;
static unsigned scanned, entries, errors, limited;
static int vcd_name(const char *name) {
  size_t n = strlen(name);
  return n >= 4 && name[n-4] == '.' &&
      (name[n-3] == 'v' || name[n-3] == 'V') &&
      (name[n-2] == 'c' || name[n-2] == 'C') &&
      (name[n-1] == 'd' || name[n-1] == 'D');
}
static void enqueue(const char *parent, const char *name, unsigned depth) {
  size_t a = strlen(parent), b = strlen(name);
  if (depth > 4 || directory_count == 96 || a + b + 2 > sizeof(directories[0])) { ++limited; return; }
  char candidate[512];
  char *out = candidate;
  memcpy(out, parent, a); memcpy(out + a, name, b);
  if (b && name[b-1] != '/') out[a + b++] = '/';
  out[a+b] = 0;
  for (unsigned i = 0; i < directory_count; ++i) if (!strcmp(candidate, directories[i])) return;
  memcpy(directories[directory_count], candidate, a+b+1);
  depths[directory_count++] = depth;
}
static void directory(const char *path, unsigned depth) {
  scr_clear(); scr_setXY(0, 0);
  printf("POPS_INVENTORY directory=%s\n", path);
  int fd = fileXioDopen(path);
  if (fd < 0) { printf("POPS_INVENTORY dopen=%d\n", fd); ++errors; return; }
  ++scanned;
  for (int n = 0; n < 256; ++n) {
    memset(&entry, 0, sizeof(entry));
    int r = fileXioDread(fd, &entry);
    if (r <= 0) { printf("POPS_INVENTORY dread=%d entries=%d\n", r, n); if (r < 0) ++errors; break; }
    ++entries;
    entry.name[sizeof(entry.name) - 1] = 0;
    if (n < 16 || !depth || strstr(path, "/POPS/") || strstr(path, "/EMBER/") || strstr(path, "/VCD/"))
      printf("POPS_INVENTORY entry=%s mode=%08x size=%u\n", entry.name, (unsigned)entry.stat.mode, (unsigned)entry.stat.size);
    if (FIO_S_ISDIR(entry.stat.mode) && strcmp(entry.name, ".") && strcmp(entry.name, ".."))
      enqueue(path, entry.name, depth + 1);
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
static int inspect_read(void *user, void *buf, size_t count) {
  return fileXioRead(*(int *)user, buf, count);
}
static int64_t inspect_seek(void *user, int64_t offset, int whence) {
  return fileXioLseek64(*(int *)user, offset, whence);
}
static void inspect(const char *path) {
  static char text[8193] __attribute__((aligned(64)));
  iox_stat_t stat;
  int result = fileXioGetStat(path, &stat);
  printf("POPS_INSPECT path=%s stat=%d size=%u\n", path, result, result < 0 ? 0 : (unsigned)stat.size);
  if (result < 0) return;
  int fd = fileXioOpen(path, 1, 0);
  printf("POPS_INSPECT open=%d\n", fd);
  if (fd < 0) return;
  if (vcd_name(path)) {
    PopsVcdInfo info = {0};
    result = pops_vcd_inspect_stream(&fd, inspect_read, inspect_seek, &info);
    printf("POPS_INSPECT vcd=%d serial=%s sector=%u data=%u image=%u root=%u\n",
        result, info.normalized_serial, (unsigned)info.sector_size,
        (unsigned)info.data_offset, (unsigned)info.image_offset, (unsigned)info.root_lba);
  } else if (strstr(path, ".TXT")) {
    result = fileXioRead(fd, text, sizeof(text)-1);
    printf("POPS_INSPECT text-read=%d hex=", result);
    for (int i = 0; i < result && i < 64; ++i) printf("%02x", (unsigned char)text[i]);
    puts("");
  }
  printf("POPS_INSPECT close=%d\n", fileXioClose(fd));
}

/* Test staging is explicit, creates a fresh directory, and never opens an
 * existing destination for writing. Verify every copied byte after closing. */
static unsigned char copy_bytes[65536] __attribute__((aligned(64)));
static unsigned char verify_bytes[65536] __attribute__((aligned(64)));
static int copy_test_file(const char *source, const char *dest) {
  iox_stat_t stat;
  int in = -1, out = -1, result = -1;
  if (fileXioGetStat(source, &stat) < 0 || stat.hisize || !stat.size) return -1;
  unsigned total = 0, size = stat.size;
  printf("POPS_STAGE copy=%s -> %s size=%u\n", source, dest, size);
  in = fileXioOpen(source, 1, 0);
  if (in < 0) goto done;
  out = fileXioOpen(dest, 2 | 0x200, 0666); /* FIO_O_WRONLY | FIO_O_CREAT */
  if (out < 0) goto done;
  while (total < size) {
    unsigned chunk = size - total;
    if (chunk > sizeof(copy_bytes)) chunk = sizeof(copy_bytes);
    int got = fileXioRead(in, copy_bytes, chunk);
    if (got <= 0 || (unsigned)got > chunk || fileXioWrite(out, copy_bytes, got) != got) goto done;
    total += got;
    if (!(total % (8u * 1024 * 1024))) printf("POPS_STAGE copied=%u/%u\n", total, size);
  }
  if (fileXioClose(out) < 0) { out = -1; goto done; } out = -1;
  if (fileXioClose(in) < 0) { in = -1; goto done; } in = -1;
  if (fileXioGetStat(dest, &stat) < 0 || stat.hisize || stat.size != size) goto done;
  in = fileXioOpen(source, 1, 0); out = fileXioOpen(dest, 1, 0);
  if (in < 0 || out < 0) goto done;
  total = 0;
  while (total < size) {
    unsigned chunk = size - total;
    if (chunk > sizeof(copy_bytes)) chunk = sizeof(copy_bytes);
    int got = fileXioRead(in, copy_bytes, chunk);
    if (got <= 0 || (unsigned)got > chunk || fileXioRead(out, verify_bytes, got) != got ||
        memcmp(copy_bytes, verify_bytes, got)) goto done;
    total += got;
  }
  result = 0;
done:
  if (in >= 0 && fileXioClose(in) < 0) result = -1;
  if (out >= 0 && fileXioClose(out) < 0) result = -1;
  printf("POPS_STAGE copy-result=%d verified=%u\n", result, total);
  return result;
}
static int stage_test(const char *vcd, const char *pops_dir, const char *dest_dir) {
  const char prefix[] = "ata0:/LAUNCHER-TEST-";
  size_t a = strlen(dest_dir), b = strlen(pops_dir);
  if (strncmp(dest_dir, prefix, sizeof(prefix)-1) || a >= 128 || a <= sizeof(prefix) ||
      dest_dir[a-1] != '/' || b >= 128 || !b || pops_dir[b-1] != '/' ||
      strstr(dest_dir, "..")) return -1;
  /* Only a single new child of the ATA root is allowed. */
  const char *slash = strchr(dest_dir + sizeof(prefix)-1, '/');
  if (!slash || slash != dest_dir + a-1) return -1;
  char directory[128], source[256], dest[256];
  memcpy(directory, dest_dir, a-1); directory[a-1] = 0;
  int result = fileXioMkdir(directory, 0777);
  printf("POPS_STAGE new-directory=%s result=%d\n", directory, result);
  if (result != 0) return -1; /* refuse reuse, including any existing test dir */
  snprintf(dest, sizeof(dest), "%sTEST.VCD", dest_dir);
  if (copy_test_file(vcd, dest)) return -1;
  const char *files[] = {"POPS.ELF", "IOPRP252.IMG"};
  for (unsigned i = 0; i < 2; ++i) {
    snprintf(source, sizeof(source), "%s%s", pops_dir, files[i]);
    snprintf(dest, sizeof(dest), "%s%s", dest_dir, files[i]);
    if (copy_test_file(source, dest)) return -1;
  }
  return 0;
}
static int verify_fatfs(const char *path) {
  const char prefix[] = "ata0:/LAUNCHER-TEST-";
  const char *child;
  if (strncmp(path, prefix, sizeof(prefix)-1) || strlen(path) >= 256 || strstr(path, ".."))
    return -1;
  child = strchr(path + sizeof(prefix)-1, '/');
  if (!child || strncmp(child+1, "FATFS-", 6) || strchr(child+1, '/') || strchr(child+1, ':'))
    return -1;
  /* Create only an explicit fresh diagnostic file; never replace an old file. */
  int fd = fileXioOpen(path, 2 | 0x200 | 0x800, 0666);
  printf("POPS_FATFS create=%d path=%s\n", fd, path);
  if (fd < 0) return -1;
  for (unsigned i=0; i<8192; ++i) copy_bytes[i]=(unsigned char)(i*37u+11u);
  int wrote = fileXioWrite(fd, copy_bytes, 8192);
  int closed = fileXioClose(fd);
  if (wrote != 8192 || closed < 0) return -1;
  /* EXCL must win even over simultaneous TRUNC and APPEND. */
  int collision = fileXioOpen(path, 2 | 0x200 | 0x800 | 0x400 | 0x100, 0666);
  printf("POPS_FATFS collision=%d expected=%d\n", collision, -EEXIST);
  if (collision >= 0) fileXioClose(collision);
  if (collision != -EEXIST) return -1;
  fd = fileXioOpen(path, 1, 0);
  if (fd < 0) return -1;
  int got = fileXioRead(fd, verify_bytes, 8192);
  int eof = fileXioRead(fd, verify_bytes+8192, 1);
  closed = fileXioClose(fd);
  printf("POPS_FATFS readback=%d eof=%d close=%d\n", got, eof, closed);
  if (got != 8192 || eof != 0 || closed < 0 || memcmp(copy_bytes,verify_bytes,8192))
    return -1;
  puts("POPS_FATFS PASS exclusive-create close-reopen byte-compare");
  return 0;
}
/* Only report presence/validity and endpoint metadata, never credentials or
 * raw file contents. No server connection, config write or IOP reset. */
static void network_config_report(void) {
  const char *dirs[] = {"mc0:/POPSTARTER/", "mc1:/POPSTARTER/", "mc0:/POPS/",
    "mc1:/POPS/", "mc0:/SYS-CONF/", "mc1:/SYS-CONF/"};
  const char *names[] = {"IPCONFIG.DAT", "ipconfig.dat", "SMBCONFIG.DAT", "smbconfig.dat"};
  char path[96], text[1024];
  unsigned ip_found = 0, smb_found = 0;
  for (unsigned d = 0; d < sizeof(dirs)/sizeof(dirs[0]); ++d) {
    for (unsigned f = 0; f < sizeof(names)/sizeof(names[0]); ++f) {
      snprintf(path,sizeof(path),"%s%s",dirs[d],names[f]);
      int fd = fileXioOpen(path,1,0);
      if (fd < 0) continue;
      int n = fileXioRead(fd,text,sizeof(text));
      int closed = fileXioClose(fd), valid = 0;
      if (n > 0 && n < sizeof(text) && closed >= 0) {
        if (f < 2) {
          char packed[48]; size_t length;
          valid = launcher_parse_tcpip_config(text,(size_t)n,packed,&length);
          if (valid) { ++ip_found;printf("POPS_NETWORK_CONFIG console_ip=%s\n",packed); }
        } else {
          LauncherSmbConfig config;
          valid = launcher_parse_smb_config(text,(size_t)n,&config);
          if (valid) {
            ++smb_found;
            printf("POPS_NETWORK_CONFIG server=%s port=%d share=%s\n",config.server,config.port,config.share);
          }
          memset(&config,0,sizeof(config));
        }
      }
      memset(text,0,sizeof(text));
      printf("POPS_NETWORK_CONFIG path=%s bytes=%d valid=%d\n",path,n,valid);
    }
  }
  printf("POPS_NETWORK_CONFIG_COMPLETE ip_files=%u smb_files=%u read_only=1\n",ip_found,smb_found);
}

/* Restricted to a newly host-created LAUNCHER-NET-* folder. Existing collision
 * and data files are owned fixtures; never accept a game/save directory here. */
static int network_fixture_test(const char *root) {
  const char *folder = strstr(root,":/LAUNCHER-NET-");
  if (!folder || strlen(root) > 400) return -EINVAL;
  folder += 2;
  for (const char *p = folder; *p; ++p) {
    if (*p == '/' && !p[1]) continue;
    if ((*p >= 'A' && *p <= 'Z') || (*p >= '0' && *p <= '9') || *p == '-' || *p == '_') continue;
    return -EINVAL;
  }
  char path[512];
  for (int sample = 0; sample < 2; ++sample) {
    unsigned seed = sample ? 0x73 : 0x31;
    snprintf(path,sizeof(path),"%s%s",root,sample ? "EXISTING.BIN" : "FIXTURE.BIN");
    int fd = fileXioOpen(path,FIO_O_RDONLY,0);
    if (fd < 0) return fd;
    int got = fileXioRead(fd,verify_bytes,8192);
    int size = fileXioLseek(fd,0,SEEK_END);
    int closed = fileXioClose(fd);
    if (got != 8192 || size != 8192 || closed < 0) return -EIO;
    for (unsigned i = 0; i < 8192; ++i)
      if (verify_bytes[i] != (unsigned char)(i*17+seed)) return -EIO;
    if (sample) {
      fd = fileXioOpen(path,FIO_O_WRONLY|FIO_O_CREAT|FIO_O_EXCL|FIO_O_TRUNC,0666);
      printf("POPS_NETWORK_FILES exclusive_collision=%d\n",fd);
      if (fd >= 0) { fileXioClose(fd);return -EIO; }
      if (fd != -EEXIST) return fd;
      fd = fileXioOpen(path,FIO_O_RDONLY,0);
      if (fd < 0) return fd;
      got = fileXioRead(fd,verify_bytes,8192); closed = fileXioClose(fd);
      if (got != 8192 || closed < 0) return -EIO;
      for (unsigned i = 0; i < 8192; ++i)
        if (verify_bytes[i] != (unsigned char)(i*17+seed)) return -EIO;
    }
  }
  snprintf(path,sizeof(path),"%sNEW.BIN",root);
  int fd = fileXioOpen(path,FIO_O_WRONLY|FIO_O_CREAT|FIO_O_EXCL,0666);
  if (fd < 0) return fd;
  for (unsigned i = 0; i < 8192; ++i) copy_bytes[i] = (unsigned char)(i*17+0xa9);
  int written = fileXioWrite(fd,copy_bytes,8192);
  int closed = fileXioClose(fd);
  printf("POPS_NETWORK_FILES written=%d close=%d\n",written,closed);
  if (written != 8192 || closed < 0) return -EIO;
  fd = fileXioOpen(path,FIO_O_RDONLY,0);
  if (fd < 0) return fd;
  int got = fileXioRead(fd,verify_bytes,8192);
  int seek = fileXioLseek(fd,4096,SEEK_SET);
  int partial = fileXioRead(fd,verify_bytes+8192,32);
  closed = fileXioClose(fd);
  if (got != 8192 || seek != 4096 || partial != 32 || closed < 0 ||
      memcmp(copy_bytes,verify_bytes,8192) || memcmp(copy_bytes+4096,verify_bytes+8192,32)) return -EIO;
  printf("POPS_NETWORK_FILES_PASS bytes=8192 exclusive_create=1 close_reopen=1 seek=1\n");
  return 0;
}

int main(int argc, char **argv) {
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
  if ((argc == 2 && !strcmp(argv[1], "--smb-read-only")) ||
      (argc == 3 && !strcmp(argv[1], "--smb-files"))) {
    if (fileXioInit() < 0) goto fail;
    LOAD_MISSING(launcher_smbman);
    int result = launcher_smb_connect();
    printf("POPS_SMB_READ_ONLY session=%d inherited_tcpip=1\n",result);
    if (!result && argc == 3) result = network_fixture_test(argv[2]);
    if (!result && argc == 2) {
      int fd = fileXioDopen("smb0:/");
      printf("POPS_SMB_READ_ONLY root=%d\n",fd);
      if (fd < 0) result = fd;
      else {
        for (unsigned n = 0; n < 16; ++n) {
          memset(&entry,0,sizeof(entry));
          int r = fileXioDread(fd,&entry);
          if (r < 0) result = r;
          if (r <= 0) break;
          printf("POPS_SMB_READ_ONLY entry=%s size=%u\n",entry.name,entry.stat.size);
        }
        int closed = fileXioDclose(fd);
        if (!result && closed < 0) result = closed;
      }
    }
    printf("POPS_SMB_RESULT result=%d read_only=%d inherited_tcpip=1\n",result,argc==2);
    printf("[ps2rig] exit=%d\n",result ? 1 : 0);
    fflush(stdout); SleepThread(); return result ? 1 : 0;
  }
  if (argc == 2 && !strcmp(argv[1], "--network-config")) {
    if (fileXioInit() < 0) goto fail;
    network_config_report();
    puts("[ps2rig] exit=0"); fflush(stdout); SleepThread(); return 0;
  }
  LOAD_MISSING(bdm);
  LOAD_MISSING(bdmfs_fatfs);
  LOAD_MISSING(usbd_mini);
  LOAD_MISSING(usbmass_bd_mini);
  LOAD_MISSING(mmceman);
  /* Missing optional hardware must not suppress inventory of live devices.
   * Retain ps2link's DEV9 implementation; do not replace its network stack. */
  if (!smod_get_mod_by_name(MODULE_NAME_ata_bd, &module) && slib_get_exp_lib("dev9", NULL))
    load("ata_bd", ata_bd_irx, size_ata_bd_irx);
  if (!smod_get_mod_by_name(MODULE_NAME_mx4sio_bd_mini, &module))
    load("mx4sio_bd_mini", mx4sio_bd_mini_irx, size_mx4sio_bd_mini_irx);
  sleep(3);
  puts("POPS_INVENTORY scanning connected storage"); fflush(stdout);
  if (fileXioInit() < 0) goto fail;
  if (argc == 3 && !strcmp(argv[1], "--verify-fatfs")) {
    int result = verify_fatfs(argv[2]);
    printf("[ps2rig] exit=%d\n", result ? 1 : 0);
    fflush(stdout); SleepThread(); return result ? 1 : 0;
  }
  if (argc == 4 && !strcmp(argv[1], "--inspect-config")) {
    static PopsConfig cfg;
    scr_clear(); scr_setXY(0, 0);
    pops_config_init(&cfg);
    int result = pops_config_discover(&cfg, argv[2], argv[3]);
    printf("POPS_CONFIG result=%d vmcdir=%s modes=%u cheats=%u discs=%u\n",
        result, cfg.vmc_dir, cfg.compat_modes, cfg.cheat_count, cfg.disc_count);
    printf("[ps2rig] exit=%d\n", result ? 1 : 0);
    fflush(stdout); SleepThread(); return result ? 1 : 0;
  }
  if (argc == 5 && !strcmp(argv[1], "--stage-test")) {
    scr_clear(); scr_setXY(0, 0);
    int result = stage_test(argv[2], argv[3], argv[4]);
    scr_clear(); scr_setXY(0, 0);
    printf("POPS_STAGE result=%d directory=%s\n", result, argv[4]);
    printf("[ps2rig] exit=%d\n", result ? 1 : 0);
    fflush(stdout); SleepThread(); return result ? 1 : 0;
  }
  if (argc > 1 && !strcmp(argv[1], "--inspect")) {
    scr_clear(); scr_setXY(0, 0);
    for (int i = 2; i < argc; ++i) inspect(argv[i]);
    puts("POPS_INSPECT COMPLETE read-only");
    puts("[ps2rig] exit=0"); fflush(stdout); SleepThread(); return 0;
  }
  const char *roots[] = {"mass0:/", "mass1:/", "mass2:/", "mass3:/", "mass4:/", "mass5:/", "mmce0:/", "mmce1:/", "mc0:/", "mc1:/"};
  for (unsigned i = 0; i < sizeof(roots) / sizeof(roots[0]); ++i) {
    directory_count = directory_next = 0;
    enqueue(roots[i], "POPS", 1); enqueue(roots[i], "VCD", 1);
    enqueue(roots[i], "EMBER/games", 2); enqueue(roots[i], "", 0);
    while (directory_next < directory_count) {
      unsigned index = directory_next++;
      directory(directories[index], depths[index]);
    }
  }
  scr_clear(); scr_setXY(0, 0);
  puts("POPS_INVENTORY COMPLETE read-only");
  printf("POPS_INVENTORY selected=%s size=%u\n", selected_vcd[0] ? selected_vcd : "none", selected_size);
  printf("POPS_INVENTORY directories=%u entries=%u errors=%u limited=%u\n", scanned, entries, errors, limited);
  puts("[ps2rig] exit=0");
  fflush(stdout); SleepThread(); return 0;
fail:
  puts("[ps2rig] exit=1"); fflush(stdout); SleepThread(); return 1;
}
