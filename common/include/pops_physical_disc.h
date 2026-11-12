#ifndef LAUNCHER_POPS_PHYSICAL_DISC_H
#define LAUNCHER_POPS_PHYSICAL_DISC_H

/* POPStarter r13's physical PS1 disc launch, the part that needs no drive.
 *
 * In the original this is not a mode anyone selects. Its launch function
 * looks for the VCD; when none was found (gp+0x3410 == 1) the block at
 * 0x8766fc..0x876a40 turns to the disc drive:
 *
 *   IOP module scan for a name starting "cdvd_"; when there is none it
 *   loads rom0:CDVDMAN and rom0:CDVDFSV            (results not checked)
 *   sceCdInit(1), sceCdSync(0)                      (result not checked)
 *   sceCdStatus() == 1         -> "Cannot access (%d)!", fatal exit
 *   sceCdGetDiskType() not one of 0x10, 0x11, 0x12, 0x13
 *                              -> "NO PS1 CDROM!", fatal exit
 *   sector buffer zeroed, sceCdRead(4, 1, buffer)   (result not checked)
 *   region letters = buffer bytes 60..63
 *   POPS 0x200794 = 0x0000202d: the disc layer's start-up call gets NULL
 *                  in place of the image name
 *   types 0x11 and 0x13: the three $MUTE_CDDA writes
 *   four writes into the original's own always-live code (pops_resident's
 *   job here, see docs/POPSTARTER_PHYSICAL_DISC.md)
 *   built-in list level 1..4: fingerprint from sectors 16 and 22
 *
 * Everything is copied as measured, including what the original does not
 * check: a failed read of sector 4 is not an error and leaves four zero
 * letters, which its region pass then treats as an unknown region.
 *
 * Nothing here reads a drive and nothing calls these functions yet.
 * See docs/POPSTARTER_PHYSICAL_DISC.md. Not tested on a console. */

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define POPS_PHYSICAL_SECTOR_SIZE 2048
#define POPS_PHYSICAL_LICENCE_LBA 4     /* region letters at bytes 60..63 */
#define POPS_PHYSICAL_LICENCE_OFFSET 60
#define POPS_PHYSICAL_SIG_LBA_A 16      /* bytes 40..87 and 808..839 */
#define POPS_PHYSICAL_SIG_LBA_B 22      /* bytes 56..119 */
#define POPS_PHYSICAL_SIG_SIZE 144

/* The sceCdRead mode the original uses for every sector (its bytes
 * 20 01 00 00 at gp+0x3978): 32 tries, spindle control 1, 2,048-byte data. */
#define POPS_PHYSICAL_READ_TRYCOUNT 0x20
#define POPS_PHYSICAL_READ_SPINDLE 1
#define POPS_PHYSICAL_READ_PATTERN 0

/* The drive status the original refuses (the tray is open). */
#define POPS_PHYSICAL_STATUS_REFUSED 1

/* sceCdGetDiskType values the original accepts. */
#define POPS_PHYSICAL_TYPE_PS1_CD 0x10
#define POPS_PHYSICAL_TYPE_PS1_CDDA 0x11
#define POPS_PHYSICAL_TYPE_PS2_CD 0x12
#define POPS_PHYSICAL_TYPE_PS2_CDDA 0x13

enum {
  POPS_PHYSICAL_OK = 0,
  POPS_PHYSICAL_FATAL_ACCESS,  /* "Cannot access (%d)!" with the status */
  POPS_PHYSICAL_FATAL_NOT_PS1, /* "NO PS1 CDROM!" */
};

typedef struct {
  uint8_t fatal;       /* POPS_PHYSICAL_*; nonzero: the original exits */
  uint8_t type_asked;  /* it calls sceCdGetDiskType (not after a refused status) */
  uint8_t sector_read; /* it reads sector 4 (only for an accepted disc type) */
  uint8_t mute_cdda;   /* it makes the $MUTE_CDDA writes (types 0x11, 0x13) */
  uint8_t read_failed; /* the caller's read result was not success; the
                        * original never looks at it and neither does this */
  uint8_t region[4];   /* licence letters for pops_region_from_licence */
  int32_t status;      /* the value "Cannot access (%d)!" prints */
  int32_t disc_type;
} PopsPhysicalDiscPlan;

/* The original's decision for one probe of the drive.
 *   drive_status  what sceCdStatus returned
 *   disc_type     what sceCdGetDiskType returned (ignored when the status
 *                 is refused: the original never asks)
 *   sector4       the 2,048-byte buffer after the read of sector 4. The
 *                 original zeroes it before reading and uses bytes 60..63
 *                 whatever the read returned, so a caller must zero it too.
 *                 NULL stands for a buffer still all zero.
 *   read_ok       nonzero when that read reported success; recorded only
 * Both compares are on the whole 32-bit value, as in the original: status
 * 0x101 passes and type 0x110 is not a PS1 disc.
 * Returns 0 with *plan filled (a fatal outcome is plan->fatal, not an
 * error), or -EINVAL without a plan. */
int pops_physical_disc_plan(PopsPhysicalDiscPlan *plan, int32_t drive_status,
                            int32_t disc_type, const uint8_t *sector4, int read_ok);

/* The original's message for a fatal outcome, as a printf format: the one
 * for POPS_PHYSICAL_FATAL_ACCESS takes the status. NULL for anything else. */
const char *pops_physical_disc_message(int fatal);

/* The block's writes into Sony's POPS, on the staged core (a flat image of
 * POPS from 0x00200000):
 *   0x200794  0x03a0202d -> 0x0000202d
 *   types 0x11 and 0x13 only, through the $MUTE_CDDA writer:
 *   0x20f0b6  0x02 -> 0x00,  0x20ebf2  0x03 -> 0x00,
 *   0x20f0e0  0xae000014 -> 0
 * The original pokes without looking; this refuses unless every site it
 * is about to write still holds Sony's value. Its place in the original's
 * order is after the always-on changes and before the IGR skin, the
 * built-in entry and the user's files.
 * Returns 0, or with the core untouched:
 *   -EINVAL  no core, or a disc type the original does not accept
 *   -ERANGE  the core ends before a site it would write
 *   -EILSEQ  a site does not hold Sony's value */
int pops_physical_disc_stage(void *staged_core, size_t core_size, int disc_type);

/* The original's memset(0x4f8000, 0, 0x80) in physical mode (0x878c88,
 * after the user's files, before its region pass): POPS's buffer for the
 * image name. Sony ships it zero and launcHER does not write it, so this
 * changes nothing on a core staged by launcHER today.
 * Returns 0, -EINVAL without a core, -ERANGE when the core is too short. */
int pops_physical_disc_clear_name(void *staged_core, size_t core_size);

/* The 144 bytes the original compares with its built-in list, from the
 * two sector buffers of a physical disc (FUN_008ff0e4 with gp+0x3410 == 1):
 * sector 16 bytes 40..87 and 808..839, sector 22 bytes 56..119. They are
 * the same bytes its VCD path reads at 0x109340, 0x109640 and 0x10ca70, so
 * pops_builtin_lookup(out) names the same entry. A NULL sector stands for
 * a zeroed buffer, which is what the original compares after a failed read.
 * Returns 0, or -EINVAL without `out`. */
int pops_physical_disc_fingerprint(const uint8_t *sector16, const uint8_t *sector22,
                                   uint8_t out[POPS_PHYSICAL_SIG_SIZE]);

#ifdef __cplusplus
}
#endif

#endif
