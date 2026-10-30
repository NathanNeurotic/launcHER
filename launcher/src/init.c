#include "init.h"
#include <slib.h>
#include "ipconfig_smap.h"
#include "common.h"
#include "dprintf.h"
#include "pops_external.h"
#include "pops_bootstrap.h"
#include "launch_args.h"
#include "handler_pops.h"
#include "handler_smb.h"
#include <ctype.h>
#include <fcntl.h>
#include <iopcontrol.h>
#include <kernel.h>
#include <libcdvd.h>
#include <libpwroff.h>
#include <loadfile.h>
#include <ps2sdkapi.h>
#include <sbv_patches.h>
#include <sifrpc.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define NEWLIB_PORT_AWARE
#include "fileXio_rpc.h"
#include <io_common.h>

_Static_assert(POPS_PROXY_ARGS_MAX <= LF_ARG_MAX,
               "POPFS arguments must fit the SDK LOADFILE RPC packet");

// Macros for loading embedded IOP modules
#define IRX_DEFINE(mod)                                                                                                                              \
  extern unsigned char mod##_irx[] __attribute__((aligned(16)));                                                                                     \
  extern uint32_t size_##mod##_irx

// Defines moduleList entry for embedded and external modules
#define INT_MODULE(mod, argFunc, deviceType) {#mod, NULL, mod##_irx, &size_##mod##_irx, 0, NULL, deviceType, argFunc}
#define EXT_MODULE(mod, path, argFunc, deviceType) {#mod, path, NULL, NULL, 0, NULL, deviceType, argFunc}

// Embedded IOP modules
IRX_DEFINE(iomanX);
IRX_DEFINE(pops_iomanx);
IRX_DEFINE(fileXio);
IRX_DEFINE(sio2man);
IRX_DEFINE(mcman);
IRX_DEFINE(mcman_2000);
IRX_DEFINE(mcserv);
IRX_DEFINE(secrman);
IRX_DEFINE(popfs);

#ifdef MMCE
IRX_DEFINE(mmceman);
#endif

#if defined(ATA) || defined(APA)
#define DEV9
#define BDM
IRX_DEFINE(ata_bd);
#endif

#ifdef USB
#define BDM
IRX_DEFINE(usbd_mini);
IRX_DEFINE(usbmass_bd_mini);
#endif

#ifdef MX4SIO
#define BDM
IRX_DEFINE(mx4sio_bd_mini);
#endif

#ifdef ILINK
#define BDM
IRX_DEFINE(iLinkman);
IRX_DEFINE(IEEE1394_bd_mini);
#endif

#ifdef UDPBD
#define SMAP
#define BDM
IRX_DEFINE(udpbd);
#endif

#ifdef UDPFS
#define SMAP
IRX_DEFINE(udpfs_ioman);
#endif

#ifdef XFROM
#define DEV9
IRX_DEFINE(extflash);
IRX_DEFINE(xfromman);
#endif

#ifdef SMAP
#define DEV9
IRX_DEFINE(smap);
IRX_DEFINE(ministack);
#endif

#ifdef SMB
#define DEV9
IRX_DEFINE(netman);
IRX_DEFINE(smap_tcpip);
IRX_DEFINE(ps2ip_nm);
IRX_DEFINE(launcher_smbman);
#endif

#ifdef APA
#define DEV9
IRX_DEFINE(ps2hdd_osd);
IRX_DEFINE(ps2fs);
IRX_DEFINE(secrsif);
#endif

#ifdef CDROM
IRX_DEFINE(xparam);
#endif

#ifdef DEV9
IRX_DEFINE(ps2dev9);
#endif

#ifdef BDM
IRX_DEFINE(bdm);
IRX_DEFINE(bdmfs_fatfs);
#endif

#ifdef OSDM
IRX_DEFINE(poweroff);
#endif

#ifdef ENABLE_PRINTF
IRX_DEFINE(ppctty);
#endif

// Function used to initialize module arguments.
// Must set argLength and return non-null pointer to a argument string if successful.
// Returned pointer must point to dynamically allocated memory
typedef char *(*moduleArgFunc)(uint32_t *argLength);

typedef struct ModuleListEntry {
  char *name;                     // Module name
  char *path;                     // Module path for external modules
  unsigned char *irx;             // Pointer to IRX module
  uint32_t *size;                 // IRX size. Uses pointer to avoid compilation issues with internal modules
  uint32_t argLength;             // Total length of argument string
  char *argStr;                   // Module arguments
  DeviceType type;                // Target device
  moduleArgFunc argumentFunction; // Function used to initialize module arguments
} ModuleListEntry;

// Argument functions
char *initSMAPArguments(uint32_t *argLength);
char *initPS2HDDArguments(uint32_t *argLength);
char *initPS2FSArguments(uint32_t *argLength);

// List of modules to load
static ModuleListEntry moduleList[] = {
#ifdef ENABLE_PRINTF
    INT_MODULE(ppctty, NULL, Device_Basic | Device_Optional),
#endif
    INT_MODULE(iomanX, NULL, Device_Basic),
    INT_MODULE(fileXio, NULL, Device_Basic),
    INT_MODULE(sio2man, NULL, Device_Basic),
    INT_MODULE(mcman, NULL, Device_Basic),
    INT_MODULE(mcserv, NULL, Device_Basic),
#ifdef MMCE
    INT_MODULE(mmceman, NULL, Device_MMCE),
#endif
#ifdef DEV9
    INT_MODULE(ps2dev9, NULL, Device_ATA | Device_UDPBD | Device_APA | Device_UDPFS | Device_XFROM | Device_SMB),
#endif
#ifdef XFROM
    INT_MODULE(extflash, NULL, Device_XFROM),
    INT_MODULE(xfromman, NULL, Device_XFROM),
#endif
#ifdef SMAP
    INT_MODULE(smap, NULL, Device_UDPBD | Device_UDPFS),
    INT_MODULE(ministack, &initSMAPArguments, Device_UDPBD | Device_UDPFS),
#endif
#ifdef UDPFS
    INT_MODULE(udpfs_ioman, NULL, Device_UDPFS),
#endif
#ifdef SMB
    INT_MODULE(netman, NULL, Device_SMB),
    INT_MODULE(smap_tcpip, NULL, Device_SMB),
    INT_MODULE(ps2ip_nm, &initTCPIPArguments, Device_SMB),
    INT_MODULE(launcher_smbman, NULL, Device_SMB),
#endif
#ifdef BDM
    INT_MODULE(bdm, NULL, Device_BDM | Device_APA),
    INT_MODULE(bdmfs_fatfs, NULL, Device_BDM | Device_APA),
#endif
#ifdef UDPBD
    INT_MODULE(udpbd, NULL, Device_UDPBD),
#endif
#if defined(ATA) || defined(APA)
    /* ata_bd also serves USB-family launches: the test console's VCD
     * library lives on the internal HDD's FAT32 partition (enumerated
     * by ata_bd, mounted as mass0:), independent of the flaky USB
     * drives. Hardware without an HDD skips it via tolerance.
     * (docs/evidence/pops_hw_runs_2026-10-30.json run 0152) */
    INT_MODULE(ata_bd, NULL, Device_ATA | Device_APA | Device_USB),
#endif
#ifdef USB
    INT_MODULE(usbd_mini, NULL, Device_USB),
    INT_MODULE(usbmass_bd_mini, NULL, Device_USB),
#endif
#ifdef MX4SIO
    INT_MODULE(mx4sio_bd_mini, NULL, Device_MX4SIO),
#endif
#ifdef ILINK
    INT_MODULE(iLinkman, NULL, Device_iLink),
    INT_MODULE(IEEE1394_bd_mini, NULL, Device_iLink),
#endif
#ifdef APA
    INT_MODULE(ps2hdd_osd, &initPS2HDDArguments, Device_APA),
    INT_MODULE(ps2fs, &initPS2FSArguments, Device_APA),
    INT_MODULE(secrsif, NULL, Device_APA),
#endif
};
#define MODULE_COUNT sizeof(moduleList) / sizeof(ModuleListEntry)

static DeviceType currentDevice = Device_None;
// Set after initModulesAny: the IOP holds more drivers than any launch target asked for
static int forceIOPReset = 0;

static int loadModules(DeviceType device, int tolerant);
static int loadModuleList(DeviceType device, int tolerant, int sonySio2, int deferFileXioInit);
static int loadModuleListResident(DeviceType device, int tolerant, int sonySio2);

// Initializes IOP modules for given device type
int initModules(DeviceType device) { return loadModules(device, 0); }

int initModulesAny(DeviceType devices) {
  int ret = loadModules(devices, 1);
  forceIOPReset = 1;
  return ret;
}

static int loadModules(DeviceType device, int tolerant) {
  if ((device & Device_SMB) && (device & (Device_UDPFS | Device_UDPBD)))
    return -EINVAL; /* TCP/IP and ministack cannot own the same NIC. */
  if (!forceIOPReset && currentDevice && (currentDevice & device) == device)
    // Do nothing if the drivers are already loaded
    return 0;
  forceIOPReset = 0;

  if (currentDevice && !(currentDevice & (Device_APA | Device_ATA)) && !(currentDevice & (Device_APA | Device_ATA)))
    shutdownDEV9();

  /* BDM-family fast path (2026-10-30 hardware evidence): loading the
   * mini stack onto the LIVE IOP first matches the environment where
   * these USB drives enumerate reliably. The reset-first path leaves
   * every mass node unmounted on the test console (drive renumber plus
   * cold-enumeration failure; see docs/evidence/pops_hw_runs_2026-10-30.json).
   * Duplicate-load-safe: already-resident libraries are skipped. On any
   * failure the original reset path below still runs. */
  if (!forceIOPReset && (device & (Device_USB | Device_MX4SIO | Device_iLink))) {
    /* Cold-booted USB drives are not ready when the module stack
     * initializes; give them spin-up time before enumerating
     * (hardware evidence 2026-10-30: no device ever appears
     * without it, on an otherwise-working stack). */
    if (device & Device_USB)
      sleep(3);
    int liveRes = loadModuleListResident(device, tolerant, 0);
    if (!liveRes) {
      currentDevice |= device;
      return 0;
    }
    DPRINTF("BDM: live-stack load failed=%d; falling back to IOP reset\n", liveRes);
  }

  // Initialize the RPC manager and reboot the IOP
  sceSifInitRpc(0);
  while (!SifIopReset("", 0)) {
  };
  while (!SifIopSync()) {
  };

  // Initialize the RPC manager
  sceSifInitRpc(0);

  // Apply patches required to load modules from EE RAM
  sbv_patch_enable_lmb();
  sbv_patch_disable_prefix_check();
  if (currentDevice == Device_None)
    sbv_patch_fileio(); // Patch fileio only once

  return loadModuleList(device, tolerant, 0, 0);
}

/* This helper never resets the IOP. The POPS bootstrap must first reboot with
 * its identified external IOP image. fileXio has a separate RPC ID from Sony's
 * FILEIO; iomanX bridges legacy imports to the modern filesystem drivers. */
/* Library names registered by the production IRXs, for duplicate-safe loads
 * onto a live IOP. NULL = unknown; the module is loaded normally. */
static const char *residentLibraryName(const char *module) {
  static const struct { const char *mod; const char *lib; } map[] = {
    {"iomanX", "iomanx"}, {"fileXio", "fileXio"}, {"sio2man", "sio2man"},
    {"mcman", "mcman"}, {"mcserv", "mcserv"}, {"bdm", "bdm"},
    {"bdmfs_fatfs", "bdmfs_fatfs"}, {"usbd_mini", "usbd"},
    {"usbmass_bd_mini", "usbmass_bd_mini"}, {"ata_bd", "ata_bd"},
    {"mx4sio_bd_mini", "mx4sio_bd"}, {"iLinkman", "iLinkman"},
    {"IEEE1394_bd_mini", "IEEE1394_bd_mini"},
  };
  for (size_t i = 0; i < sizeof(map) / sizeof(map[0]); ++i)
    if (!strcmp(map[i].mod, module))
      return map[i].lib;
  return NULL;
}

static int loadModuleListResident(DeviceType device, int tolerant, int sonySio2) {
  for (int i = 0; i < MODULE_COUNT; ++i) {
    if (!(device & moduleList[i].type) && !(moduleList[i].type & Device_Basic))
      continue;
    const char *lib = residentLibraryName(moduleList[i].name);
    if (lib && slib_get_exp_lib(lib, NULL)) {
      DPRINTF("BDM: reusing resident %s\n", moduleList[i].name);
      continue;
    }
  }
  int ret = loadModuleList(device, 1, sonySio2, 1);
  if (ret)
    return ret;
  /* Probe-proven recipe: a quiet window with no EE RPC traffic before
   * fileXioInit; early binding correlates with lost USB enumeration on the
   * test console (docs/evidence/pops_hw_runs_2026-10-30.json run 0149). */
  sleep(3);
  return fileXioInit() < 0 ? -EIO : 0;
}

static int loadModuleList(DeviceType device, int tolerant, int sonySio2, int deferFileXioInit) {
  int ret = 0, iopret = 0;
  if ((device & Device_SMB) && (device & (Device_UDPFS | Device_UDPBD)))
    return -EINVAL;
#ifdef SMB
  launcher_smb_reset();
#endif
  currentDevice = Device_None; /* A partial initialization is never cached. */
  // Load modules
  for (int i = 0; i < MODULE_COUNT; i++) {
    ret = 0;
    iopret = 0;
    if (!(device & moduleList[i].type) && !(moduleList[i].type & Device_Basic))
      continue;
    if (sonySio2 && !strcmp(moduleList[i].name, "sio2man"))
      continue;
    /* A loose external IRX on a memory card does not mean that driver was
     * installed on the newly rebooted IOP. Preserve the normal USB stack
     * unless this is an explicit XX./BDMA opt-in; otherwise POPFS can start
     * with no live mass: device at all. Experimental XX behavior is retained. */
    if (sonySio2 && (device & Device_USB) && pops_get_active_xx_launch() &&
        pops_has_external_usb_modules() &&
        (!strcmp(moduleList[i].name, "usbd_mini") || !strcmp(moduleList[i].name, "usbmass_bd_mini"))) {
      DPRINTF("POPS: XX. USB opt-in: external driver override for %s\n", moduleList[i].name);
      continue;
    }

    // If module has an arugment function, execute it
    if (moduleList[i].argumentFunction != NULL) {
      moduleList[i].argStr = moduleList[i].argumentFunction(&moduleList[i].argLength);
      if (moduleList[i].argStr == NULL) {
        msg("ERROR: Failed to initialize arguments for module %s\n", moduleList[i].name);
        return -ENOENT;
      }
    }

    if (sonySio2 && !strcmp(moduleList[i].name, "mcman")) {
      /* The selected Sony SIO2 exports 2.3, requiring the SDK's remote
       * compatible card manager (including multitap ordinal 57, not 55).
       * The foreign image also needs the authentication dependency explicitly. */
      int secrResult = 0;
      DPRINTF("IOP: loading secrman (Sony=1)\n");
      ret = SifExecModuleBuffer(secrman_irx, size_secrman_irx, 0, NULL, &secrResult);
      DPRINTF("IOP: loaded secrman id=%d start=%d\n", ret, secrResult);
      if (ret < 0 || secrResult != 0)
        return ret < 0 ? ret : -EIO;
    }
    DPRINTF("IOP: loading %s (Sony=%d)\n", moduleList[i].name, sonySio2);
    /* Only the identified Sony IOP reset path needs the private legacy-state
     * migration. Normal launcher and Ember initialization retain SDK iomanX. */
    if (sonySio2 && !strcmp(moduleList[i].name, "iomanX"))
      ret = SifExecModuleBuffer(pops_iomanx_irx, size_pops_iomanx_irx, 0, NULL, &iopret);
    else if (sonySio2 && !strcmp(moduleList[i].name, "mcman"))
      ret = SifExecModuleBuffer(mcman_2000_irx, size_mcman_2000_irx, 0, NULL, &iopret);
    else if (moduleList[i].path)
      ret = SifLoadModule(moduleList[i].path, moduleList[i].argLength, moduleList[i].argStr);
    else
      ret = SifExecModuleBuffer(moduleList[i].irx, *moduleList[i].size, moduleList[i].argLength, moduleList[i].argStr, &iopret);
    DPRINTF("IOP: loaded %s id=%d start=%d\n", moduleList[i].name, ret, iopret);

    if (!deferFileXioInit && !strcmp(moduleList[i].name, "fileXio")) {
      int fxio_ret = fileXioInit();
      if (fxio_ret < 0) {
        msg("ERROR: Failed to initialize fileXio RPC: %d\n", fxio_ret);
        return fxio_ret;
      }
    }

    // Delay to prevent ps2hdd module from hanging
    if ((device & Device_APA) && !strcmp(moduleList[i].name, "ata_bd"))
      sleep(1);

    if (ret >= 0)
      ret = 0;
    /* For POPS/SMB, a failed IOP module's _start result can be negative even
     * when SifExecModuleBuffer itself returns a successful module ID.
     * Other generic launch behavior remains unchanged for compatibility. */
    if (iopret == 1 || ((sonySio2 || (device & Device_SMB)) && iopret < 0))
      ret = iopret;
    if (moduleList[i].type & Device_Optional)
      ret = 0;
    // initModulesAny: hardware this console lacks (no DEV9 for the exFAT HDD, no i.Link port) only
    // leaves that driver out
    if (tolerant && ret && !(moduleList[i].type & Device_Basic)) {
      DPRINTF("Skipping module %s: %d\n", moduleList[i].name, ret);
      ret = 0;
    }

    // Clean up arguments
    if (moduleList[i].argStr != NULL) {
      free(moduleList[i].argStr);
      moduleList[i].argStr = NULL;
      moduleList[i].argLength = 0;
    }

    if (ret) {
      msg("ERROR: Failed to initialize module %s: %d\n", moduleList[i].name, ret);
      return ret;
    }
  }

  ret = deferFileXioInit ? 0 : fileXioInit();
  if (ret < 0) {
    msg("POPS: Cannot bind fileXio after IOP reset: %d\n", ret);
    return ret;
  }
#ifdef SMB
  if (device & Device_SMB) {
    ret = launcher_smb_connect();
    if (ret) return ret;
  }
#endif
  currentDevice = device;
  return 0;
}

int initPopsServices(DeviceType devices, const void *core, size_t coreSize,
                     const char *proxyArguments, uint32_t argumentSize) {
  int ret, moduleResult = 0;
  /* A foreign IOPRP has replaced the regular launcher environment. If
   * any subsequent POPS stage fails and control returns to launcHER, a
   * normal launch must not treat the device cache as initialized. This
   * remains set even after loadModuleList updates currentDevice. */
  forceIOPReset = 1;
  if (!proxyArguments || !argumentSize || argumentSize > POPS_PROXY_ARGS_MAX ||
      proxyArguments[argumentSize - 1] != '\0')
    return -EINVAL;
  /* Boot planning and core patching already verified the pristine core. Check
   * the module we execute independently: EE patching changes the core hash. */
  ret = pops_core_sio2_identify(core, coreSize);
  if (ret)
    return -EINVAL;
  sceSifInitRpc(0);
  sbv_patch_enable_lmb();
  sbv_patch_disable_prefix_check();
  /* Load Sony's SIO2 once, before MMCE/memory-card services. POPS must skip
   * its first embedded-module call under POPS_CORE_STORAGE_BRIDGE. */
  ret = SifExecModuleBuffer((void *)((const unsigned char *)core + 0xcbbc0),
                           0x1999, 0, NULL, &moduleResult);
  if (ret < 0 || moduleResult != 0)
    return ret < 0 ? ret : -EIO;
  ret = loadModuleList(devices, 0, 1, 0);
  if (ret)
    return ret;
  moduleResult = 0;
  ret = SifExecModuleBuffer(popfs_irx, size_popfs_irx, argumentSize,
                           proxyArguments, &moduleResult);
  if (ret < 0 || moduleResult != 0)
    return ret < 0 ? ret : -EIO;
  return 0;
}

// Reboots the IOP and executes a path from ROM via LoadExecPS2
int execROMPath(int argc, char *argv[]) {
  sceSifInitRpc(0);
  while (!SifIopReset("", 0)) {
  };
  while (!SifIopSync()) {
  };
  sceSifExitRpc();
  SifLoadFileInit();

  if (argv) {
    int ret = 0;
    if (argv[0][3] == '1') { // rom1:
      ret = SifLoadModule("rom0:ADDDRV", 0, NULL);
    } else if (argv[0][3] == '2') // rom2:
      ret = SifLoadModule("rom0:ADDROM2", 0, NULL);

    if (ret < 0) {
      msg("ERROR: Failed to initialize module for %s: %d\n", argv[0], ret);
      return ret;
    }
  }

  argc--;
  LoadExecPS2(argv[0], argc, &argv[1]);
}

#ifdef OSDM
// Shuts down the console.
// Needs initModules(Device_Basic) to be called first
void shutdownPS2() {
  sceSifInitRpc(0);
  sceCdInit(SCECdINoD);
  SifExecModuleBuffer(poweroff_irx, size_poweroff_irx, 0, NULL, NULL);
  poweroffShutdown();
}
#endif

#ifdef CDROM
// Sets IOP emulation flags for Deckard consoles
// Needs initModules(Device_Basic) to be called first
void applyXPARAM(char *gameID) { SifExecModuleBuffer(xparam_irx, size_xparam_irx, strlen(gameID) + 1, gameID, NULL); }
#endif

// Argument functions
#if defined(UDPBD) || defined(UDPFS)
// Builds IP address argument for SMAP module
// using mc?:SYS-CONF/IPCONFIG.DAT from memory card
/* Read the first IPv4 token, not a fixed number of characters. The normal
 * IPCONFIG.DAT also contains netmask/gateway, while a 7-15 byte IP alone
 * remains valid. Preserve the original 19-byte SMAP argument allocation. */
char *initSMAPArguments(uint32_t *argLength) {
  static const char *const dirs[] = {
    "mc0:/POPSTARTER/", "mc1:/POPSTARTER/", "mc0:/POPS/", "mc1:/POPS/",
    "mc0:/SYS-CONF/", "mc1:/SYS-CONF/"
  };
  char path[80], ipAddr[16], contents[64];
  if (!argLength) return NULL;
  for (unsigned i = 0; i < sizeof(dirs)/sizeof(dirs[0]); ++i) {
    snprintf(path, sizeof(path), "%sIPCONFIG.DAT", dirs[i]);
    int fd = fileXioOpen(path, FIO_O_RDONLY, 0);
    if (fd < 0) {
      snprintf(path, sizeof(path), "%sipconfig.dat", dirs[i]);
      fd = fileXioOpen(path, FIO_O_RDONLY, 0);
    }
    if (fd < 0) continue;
    int n = fileXioRead(fd, contents, sizeof(contents));
    fileXioClose(fd);
    if (n <= 0 || !smap_parse_ipconfig(contents, (size_t)n, ipAddr))
      continue;
    char *argStr = calloc(19, sizeof(char));
    if (!argStr) return NULL;
    snprintf(argStr, 19, "ip=%s", ipAddr);
    *argLength = 19;
    return argStr;
  }
  msg("ERROR: No valid console IPv4 in IPCONFIG.DAT on mc0:/mc1:\n");
  return NULL;
}
#endif

#ifdef APA
// up to 4 descriptors, 20 buffers
static char ps2hddArguments[] = "-o"
                                "\0"
                                "4"
                                "\0"
                                "-n"
                                "\0"
                                "20";
// Sets arguments for PS2HDD modules
char *initPS2HDDArguments(uint32_t *argLength) {
  *argLength = sizeof(ps2hddArguments);

  char *argStr = malloc(sizeof(ps2hddArguments));
  memcpy(argStr, ps2hddArguments, sizeof(ps2hddArguments));
  return argStr;
}

// up to 10 descriptors, 40 buffers
char ps2fsArguments[] = "-o"
                        "\0"
                        "10"
                        "\0"
                        "-n"
                        "\0"
                        "40";
// Sets arguments for PS2HDD modules
char *initPS2FSArguments(uint32_t *argLength) {
  *argLength = sizeof(ps2fsArguments);

  char *argStr = malloc(sizeof(ps2fsArguments));
  memcpy(argStr, ps2fsArguments, sizeof(ps2fsArguments));
  return argStr;
}
#endif
