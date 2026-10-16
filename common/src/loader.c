#include "loader.h"
#include "dprintf.h"
#include <elf.h>
#include <errno.h>
#include <iopcontrol.h>
#include <kernel.h>
#include <loadfile.h>
#include <sifrpc.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

// Based on PS2SDK elf-loader
extern uint8_t loader_elf[];
extern int size_loader_elf;

static char loaderArg[11] = "-la=\0\0\0\0\0\0\0";
static char elfMemArg[22] = {0};
static char ioprpMemArg[22] = {0};

/* launcHER is a headless bootstrap and must not initialize gsKit solely
 * for an animation. At the irreversible ELF handoff, display the GS black
 * background instead of a stale parent framebuffer. This preserves the
 * parent's GS registers if ExecPS2 fails and returns, and leaves video-mode
 * setup to the destination. Do not touch the IOP, SIO2 or loader arguments. */
static uint64_t holdBlackForExec(uint64_t *previousBackground)
{
  volatile uint64_t *const pmode = (volatile uint64_t *)0x12000000;
  volatile uint64_t *const bgcolor = (volatile uint64_t *)0x120000e0;
  uint64_t previousMode = *pmode;
  *previousBackground = *bgcolor;
  *bgcolor = 0;
  *pmode = previousMode & ~UINT64_C(3); /* disable both display read circuits */
  return previousMode;
}

static void restoreGSAfterFailedExec(uint64_t previousMode, uint64_t previousBackground)
{
  *(volatile uint64_t *)0x120000e0 = previousBackground;
  *(volatile uint64_t *)0x12000000 = previousMode;
}

// Loads and executes the embedded loader with provided arguments
int executeLoader(int argc, char *argv[]) {
  Elf32_Ehdr *eh;
  Elf32_Phdr *eph;
  void *pdata;
  int i;

  DPRINTF("Starting the embedded ELF loader with argc = %d\n", argc);
  for (i = 0; i < argc; i++)
    DPRINTF("argv[%d] = %s\n", i, argv[i]);

  eh = (Elf32_Ehdr *)loader_elf;
  if (memcmp(&eh->e_ident[0], ELFMAG, SELFMAG))
    __builtin_trap();

  eph = (Elf32_Phdr *)(loader_elf + eh->e_phoff);

  // Scan through the ELF's program headers and copy them into RAM
  for (i = 0; i < eh->e_phnum; i++) {
    if (eph[i].p_type != PT_LOAD)
      continue;

    pdata = (void *)(loader_elf + eph[i].p_offset);
    memcpy((void *)eph[i].p_vaddr, pdata, eph[i].p_filesz);
  }

  FlushCache(0);
  FlushCache(2);

  /* Only mask the display once the child is loaded into EE RAM. Games and
   * GUI applications restore their own PMODE during GS initialization. */
  uint64_t previousBackground;
  uint64_t previousMode = holdBlackForExec(&previousBackground);
  int result = ExecPS2((void *)eh->e_entry, NULL, argc, argv);
  restoreGSAfterFailedExec(previousMode, previousBackground);
  return result;
}

// Loads ELF from file specified in argv[0]
int loadELF(LoadOptions *options) {
  int argPos = 4; // Account for "-la="
  int argc = 0;

  // Basic arguments
  if (options->resetIOP) {
    loaderArg[argPos++] = 'R';
    argc = 1;
  }
  if (options->skipArgv0) {
    loaderArg[argPos++] = 'A';
    argc = 1;
  }
  if (options->dev9ShutdownType == ShutdownType_HDD) {
    loaderArg[argPos++] = 'N';
    argc = 1;
  } else if (options->dev9ShutdownType == ShutdownType_None) {
    loaderArg[argPos++] = 'D';
    argc = 1;
  }

  // IOPRP
  if (options->ioprpMem || options->ioprpPath) {
    loaderArg[argPos++] = 'I';
    argc = (argc == 0) ? 2 : argc + 1;

    if (options->ioprpMem)
      sprintf(ioprpMemArg, "mem:%08lX:%08lX", (uint32_t)options->ioprpMem, (uint32_t)options->ioprpSize);
  }

  // In-memory ELF
  if (options->elfMem) {
    loaderArg[argPos++] = 'E';
    argc = (argc == 0) ? 2 : argc + 1;

    sprintf(elfMemArg, "mem:%08lX:%08lX", (uint32_t)options->elfMem, (uint32_t)options->elfSize);
  }

  // eGSM
  if (options->eGSM) {
    loaderArg[argPos++] = 'G';
    argc = (argc == 0) ? 2 : argc + 1;
  }

  char **argv = options->argv;
  if (argc != 0) {
    argv = malloc((argc + options->argc) * sizeof(char *));
    // Copy the original arguments
    for (int i = 0; i < options->argc; i++)
      argv[i] = options->argv[i];

    // Add loader arguments (ELF, IOPRP, GSM argument order is important)
    int argvOffset = argc;
    argc += options->argc;

    // ELF argument
    if (elfMemArg[0] != '\0')
      argv[argc - (argvOffset--)] = elfMemArg;

    // IOPRP argument
    if (ioprpMemArg[0] != '\0')
      argv[argc - (argvOffset--)] = ioprpMemArg;
    else if (options->ioprpPath)
      argv[argc - (argvOffset--)] = options->ioprpPath;

    // GSM argument
    if (options->eGSM)
      argv[argc - (argvOffset--)] = options->eGSM;

    // Loader arguments
    argv[argc - argvOffset] = loaderArg;
  } else
    argc = options->argc;

  return executeLoader(argc, argv);
}
