#ifndef LAUNCHER_POPS_EXTERNAL_H
#define LAUNCHER_POPS_EXTERNAL_H

#include <stddef.h>
#include <stdint.h>

/* External file inspection and guarded buffer staging; no IOP setup or execution. */
enum {
  POPS_FILE_OK = 0,
  POPS_FILE_INVALID = -1,
  POPS_FILE_UNSUPPORTED = -2,
  POPS_FILE_RANGE = -3,
  POPS_FILE_GUARD = -4,
  POPS_FILE_NOMEM = -5
};

typedef struct {
  uint32_t entry;
  uint16_t load_segments;
} PopsElfInfo;

/* Validate a complete, external ELF32 little-endian MIPS executable. */
int pops_elf_inspect(const void *file, size_t size, PopsElfInfo *out);

/* Length-framed POPS PAK stream: not an ELF, and no image identity guarantee.
 * Cap allocation/output at 8 MiB. Caller owns the output buffer; discard its
 * contents on any decode error (decoding can have written a partial result).
 * Output length is assigned only on success. Source and output must not alias.
 * Original packages omit LZMA's end marker; exact declared length is required.
 */
#define POPS_PAK_MAX_SIZE UINT32_C(0x00800000)
int pops_pak_inspect(const void *file, size_t size, uint32_t *decoded_size);
int pops_pak_decode(const void *file, size_t size, void *output, size_t capacity,
                    size_t *decoded_size);

typedef struct {
  uint32_t directory_offset;
  uint32_t directory_size;
  uint32_t extinfo_size;
  uint16_t files;
} PopsIopImage;

/* Validate ROMDIR, EXTINFO and all file extents of an external reboot image.
 * Structural success does not establish the modules' versions or compatibility.
 * The final file need not have alignment padding beyond its actual data. */
int pops_iop_image_inspect(const void *file, size_t size, PopsIopImage *out);

/* Find the exact ROMDIR payload extent for a named IOP module without
 * modifying the verified reboot image. Not finding a module is allowed:
 * the original POPS core may embed/load some IRXs itself. */
int pops_iop_image_find_module(const void *file, size_t size, const char *name,
                               size_t *module_offset, size_t *module_size);

/* Read-only hints from NUL-terminated module strings, NOT proof that an
 * imported library or file path is executed. Only checks exact ROMDIR module
 * bounds, never scans other modules or invents a missing IOPCD. */
enum {
  POPS_IOSTRING_IOMAN  = 1u << 0,
  POPS_IOSTRING_IOMANX = 1u << 1,
  POPS_IOSTRING_PFS    = 1u << 2,
  POPS_IOSTRING_POPS   = 1u << 3
};
int pops_iop_image_probe_io_strings(const void *file, size_t size,
                                    const char *module, uint32_t *flags);

/* Recognize ps2sdk IRX IMPORT_MAGIC (0x41e00000) plus exact 8-byte
 * library name inside a validated ROMDIR module. Unlike arbitrary string
 * hints, these are actual import-table descriptors; they do not prove
 * that a particular import stub was called during runtime. */
enum {
  POPS_IOIMPORT_IOMAN  = 1u << 0,
  POPS_IOIMPORT_IOMANX = 1u << 1
};
int pops_iop_image_probe_io_imports(const void *file, size_t size,
                                    const char *module, uint32_t *imports);

/* Inventory actual complete IRX import jump-stub indices (0..63)
 * inside a validated ROMDIR module. These are declarations, NOT evidence
 * of executed IOPCD calls. Outputs stay unchanged on failure. */
int pops_iop_image_probe_io_ordinals(const void *file, size_t size,
                                     const char *module, uint64_t *legacy,
                                     uint64_t *extended);

/* The same bounded import-stub scan for a standalone module payload. Caller
 * establishes its identity/extent first; a match is not execution evidence. */
int pops_iop_module_probe_io_ordinals(const void *module, size_t size,
                                      uint64_t *legacy, uint64_t *extended);

typedef enum {
  POPS_SOURCE_LOOSE_ELF,
  POPS_SOURCE_DECODED_PAK
} PopsBootSource;

typedef enum {
  POPS_IOP_LOOSE_252,
  POPS_IOP_PACKED_252,
  POPS_IOP_PACKED_2305A
} PopsIopVariant;

typedef struct {
  PopsBootSource source;
  PopsIopVariant iop_variant;
  uint32_t entry;
  uint32_t core_address;
  uint32_t core_size;
  uint32_t bss_address;
  uint32_t bss_size;
  uint32_t scratchpad_size;
  uint32_t iop_offset; /* In decoded PAK; zero for a separate loose image. */
  uint32_t iop_size;
} PopsBootPlan;

/* SHA256 of bounded dependency images; no allocation. Digest assigned on success. */
int pops_image_sha256(const void *file, size_t size, uint8_t digest[32]);
int pops_core_image_identify(const void *core, size_t size);
/* Identify only the embedded Sony SIO2 module after guarded core patching.
 * Boot planning must still identify the full unmodified core first. */
int pops_core_sio2_identify(const void *core, size_t size);
/* Identify the selected core's complete embedded Sony IOPCD by SHA256 before
 * inventorying its I/O imports. EE patches outside the module are allowed;
 * full pristine-core identity remains a boot-planning prerequisite.
 * Output masks are unchanged on failure; this does not load/execute a module. */
int pops_core_iopcd_probe_io_ordinals(const void *core, size_t size,
                                      uint64_t *legacy, uint64_t *extended);

enum {
  POPS_CORE_HDD_CHECK = 1u << 0,
  POPS_CORE_CDROM_LICENSE = 1u << 1,
  POPS_CORE_EXCEPTION_BREAKPOINTS = 1u << 2,
  POPS_CORE_POWER_OFF = 1u << 3,
  POPS_CORE_DELCRO = 1u << 4,
  POPS_CORE_MODULE_ERRORS = 1u << 5,
  POPS_CORE_STORAGE_BRIDGE = 1u << 6,
  POPS_CORE_ALL = (1u << 7) - 1
};

/* Measured original writes and an optional launcHER storage redirect, into a
 * caller-owned buffer only. The redirect requires configured backing volumes
 * and the proxy to be available before POPS entry. Requires
 * the complete, unmodified reference core. Apply selected groups once, together,
 * before Trojan/game-specific patches. All guards precede all writes; no cache
 * operations, runtime callbacks, path/IOP/storage/VMC setup or boot readiness. */
int pops_core_patches_stage(uint32_t base, void *memory, size_t span, uint32_t groups);

enum {
  POPS_FIX_TEXTURE_WINDOW   = 1u << 0,
  POPS_FIX_GPU_DMA_ZERO     = 1u << 1,
  POPS_FIX_CDDA_SETMODE     = 1u << 2,
  POPS_FIX_SPU_ENABLE_RESET = 1u << 3,
  POPS_FIX_GTE_RES1         = 1u << 4,
  POPS_FIX_ALL              = (1u << 5) - 1
};

/* Stage optional, transactionally-guarded core runtime corrections
 * (assessed from PSXCore / community research). Validates complete reference
 * core identity and all expected instruction guards before applying any write.
 * Does not conflict with or alter the baseline POPStarter patch groups. */
int pops_core_runtime_corrections_stage(uint32_t base, void *memory, size_t span, uint32_t mask);

/* Identify the measured reference core and dependency sets by exact SHA256.
 * Unknown/mutated images fail closed. No writes, reboot, runtime patches or
 * module compatibility claim. Output remains unchanged on failure. */
int pops_boot_plan_pak(const void *decoded, size_t size, PopsBootPlan *out);
int pops_boot_plan_elf(const void *elf, size_t elf_size, const void *iop,
                       size_t iop_size, PopsBootPlan *out);

typedef struct {
  uint32_t ram_base;
  void *ram;
  size_t ram_size;
  void *scratchpad;
  size_t scratchpad_size;
  void *iop;
  size_t iop_size;
} PopsBootBuffers;

/* Prepare caller-owned buffers after exact identity checks. Source ranges and
 * all three destination ranges must be disjoint. All checks precede writes.
 * Clear the reference ELF's low RAM reservation, core BSS and scratchpad BSS;
 * keep the IOP reboot image separate. No live-memory/cache/IOP operations. */
int pops_boot_stage_pak(const void *decoded, size_t size, const PopsBootBuffers *buffers);
int pops_boot_stage_elf(const void *elf, size_t elf_size, const void *iop,
                        size_t iop_size, const PopsBootBuffers *buffers);

typedef enum {
  POPS_CONTAINER_TROJAN,
  POPS_CONTAINER_CONFIG,
  POPS_CONTAINER_DATA
} PopsContainerKind;

typedef struct {
  PopsContainerKind kind;
  uint8_t slot;
  uint32_t control; /* Offset 0x08: PATCH actions or Trojan width/version control. */
  uint32_t flags;   /* Offset 0x0c: retain as one 32-bit word. */
  uint32_t load;
  uint32_t entry;
  uint32_t hook;
  uint32_t payload_size;
  uint8_t metadata[32]; /* Not just a string: PATCH records contain binary data. */
} PopsContainer;

/* Recognizes TROJAN_0..9 and PATCH_1..9 containers, including data-only PATCHes.
 * Output is unchanged on error. A CONFIG success is not an executable payload. */
int pops_container_inspect(const void *file, size_t size, PopsContainer *out);

typedef struct {
  PopsContainer container;
  size_t payload_offset; /* Destination offset from the supplied staging base. */
  size_t hook_offset;    /* TROJAN only: beginning of the displaced 8 bytes. */
  uint32_t hook_instruction;
  uint8_t hook_size;     /* Actual write size: 4, 8 or 12 bytes. */
} PopsContainerPlan;

/* Validate that the entire payload and hook fit a caller-owned memory window.
 * CONFIG records have neither a copy nor a hook. Hook encoding follows the
 * type/width dispatch in original POPStarter FUN_00880a24. */
int pops_container_plan(const void *file, size_t size, uint32_t base,
                        size_t span, PopsContainerPlan *out);

/* Stage into a caller-owned buffer. For TROJANs the caller must supply 2 guard
 * words (3 for a 12-byte hook) from its verified image/patch-order profile.
 * Every check runs before any destination write. CONFIG records are rejected:
 * they must be consumed as options, not silently treated as applied patches.
 * No cache operations or execution; the live-memory backend is not wired yet. */
int pops_container_stage(const void *file, size_t size, uint32_t base,
                         void *memory, size_t span, const uint32_t *expected_hook,
                         size_t expected_count);

typedef enum {
  POPS_PATCH_VIDEO_NONE,
  POPS_PATCH_VIDEO_PAL,
  POPS_PATCH_VIDEO_DISABLE_AUTO,
  POPS_PATCH_VIDEO_CONTROL6 /* Exact original writes known; user-facing meaning unverified. */
} PopsPatchVideo;

typedef struct {
  uint8_t modes[4];
  PopsPatchVideo video;
} PopsPatchOptions;

/* Decode PATCH control values 0..7 and mode bytes at file offsets 0x38..0x3b,
 * following FUN_00881de8. Returns intent; does not apply POPS memory patches. */
int pops_patch_options(const PopsContainer *container, PopsPatchOptions *out);

#endif
