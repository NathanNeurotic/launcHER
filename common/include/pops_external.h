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
int pops_core_image_identify_baseline_patched(const void *core, size_t size);
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

/* Every container is a 64-byte header followed by exactly payload_size bytes
 * of payload: the payload's first byte is at this offset in the file. */
#define POPS_CONTAINER_HEADER_SIZE 64u

/* Recognizes TROJAN_0..9 and PATCH_1..9 containers, including data-only PATCHes.
 * Output is unchanged on error. A CONFIG success is not an executable payload.
 * Its TROJAN rules are launcHER's own strict ones, not POPStarter's: the fix
 * file path (pops_fix_stage_trojan) uses pops_trojan_verdict below. */
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

/* TROJAN_n.BIN as POPStarter r13's loader reads it (FUN_00880a24), in its
 * rule order. A file is "Invalid" when: it is shorter than 0x44 bytes; bytes
 * 0..7 are not "TROJAN_" plus the digit of the file being read; byte 0x0c
 * (format) is not 1, 2 or 3; any of bytes 0x08, 0x09, 0x0b, 0x0d, 0x0f, 0x1f
 * or 0x34..0x3f is nonzero; the load or the entry address is zero; 0x40 plus
 * the 24-bit size at 0x1c is not the file size; byte 0x0e is zero (any other
 * value passes); byte 0x20, the first of the name, is zero; or the format is
 * 1 and byte 0x0a is nonzero. A format 3 file whose byte 0x0a is below
 * POPS_TROJAN_REVISION is "Skipped (outdated)" when the disc matched an
 * entry of the built-in list by fingerprint (a $VCDID_n is read later and
 * does not count). Alignment, ranges, a hook of 0 and where the entry lies
 * are not checked there; whether launcHER can host such a file is a
 * separate question (pops_fix_stage_trojan). */
#define POPS_TROJAN_MIN_FILE 0x44u
#define POPS_TROJAN_REVISION 6u /* the original's gp+0x345c, set at 0x870d9c */
enum {
  POPS_TROJAN_APPLY = 0,
  POPS_TROJAN_INVALID = 1,
  POPS_TROJAN_OUTDATED = 2
};

typedef struct {
  uint8_t slot;
  uint8_t format;     /* byte 0x0c */
  uint8_t width;      /* byte 0x0a: format 2 hook width, format 3 revision */
  uint8_t hook_words; /* words written at the hook: 1, 2 or 3 */
  uint32_t load;
  uint32_t entry;
  uint32_t hook;
  uint32_t size;      /* payload bytes, from file offset 0x40 */
  /* What the original writes at the hook: "jal entry", or for format 2 with
   * width 1, 2 or 3 "j entry" followed by width - 1 zero words. */
  uint32_t hook_word[3];
} PopsTrojanInfo;

/* POPS_TROJAN_APPLY, POPS_TROJAN_INVALID or POPS_TROJAN_OUTDATED; negative
 * for a null argument or a slot above 9. `out` is written unless the file
 * is Invalid. fingerprint_builtin_id: the built-in entry the disc's
 * fingerprint selected, 0 for none. */
int pops_trojan_verdict(const void *file, size_t size, unsigned slot,
                        unsigned fingerprint_builtin_id, PopsTrojanInfo *out);

/* Where POPStarter r13 keeps things a TROJAN payload can depend on. It
 * overwrites two parts of the POPS core with code of its own: 0x232790..
 * 0x232ec8 (reached from POPS's GP1 path) and 0x238a90..0x2397f0. Ten
 * two-word slots in the first part are what TROJAN files hook: five from
 * 0x2327d0 and five from 0x232d08, each "beq zero,zero,+1; nop" until a
 * file writes "jal entry" over it; the two words after each five are where
 * its code goes on. launcHER has none of that code in the POPS core. */
#define POPS_TROJAN_BLOCK1_BASE  UINT32_C(0x00232790)
#define POPS_TROJAN_BLOCK1_LIMIT UINT32_C(0x00232ec8)
#define POPS_TROJAN_BLOCK2_BASE  UINT32_C(0x00238a90)
#define POPS_TROJAN_BLOCK2_LIMIT UINT32_C(0x002397f0)
#define POPS_TROJAN_480P_BASE    UINT32_C(0x002394f0) /* its 480p handler, inside the second part */
#define POPS_TROJAN_480P_LIMIT   UINT32_C(0x00239758)
#define POPS_TROJAN_SLOTS_A      UINT32_C(0x002327d0)
#define POPS_TROJAN_SLOTS_B      UINT32_C(0x00232d08)
#define POPS_TROJAN_SLOTS_SPAN   0x30u /* five slots and the two words after them */
#define POPS_TROJAN_SLOTS_HOOKS  0x28u /* the five slots */
#define POPS_TROJAN_SLOT_EMPTY   UINT32_C(0x10000001) /* beq zero,zero,+1: on to the next slot */
#define POPS_TROJAN_BREAK_CALL   UINT32_C(0x0c518000) /* jal 0x01460000, a built-in entry's word at 0x232d08 */
#define POPS_TROJAN_MAIN_BASE    UINT32_C(0x00870000) /* POPStarter's own program */
#define POPS_TROJAN_MAIN_LIMIT   UINT32_C(0x00b00000)
#define POPS_TROJAN_BUILTIN_BASE UINT32_C(0x01410000) /* a built-in entry's fix code */
/* Memory above the POPS image where every TROJAN payload of the examined
 * files loads (0x01431000..0x0152c3c0). launcHER hosts a payload anywhere
 * in the arena except its own resident image and the breakpoint handler
 * after it (the "owned" part). */
#define POPS_TROJAN_ARENA_BASE   UINT32_C(0x01420000)
#define POPS_TROJAN_ARENA_LIMIT  UINT32_C(0x01600000)
#define POPS_TROJAN_OWNED_BASE   UINT32_C(0x0143a000)
#define POPS_TROJAN_OWNED_LIMIT  UINT32_C(0x01460200)

/* What a payload's code refers to, from pops_trojan_scan. */
#define POPS_TROJAN_REF_SLOT     0x01u /* the slot words, or a jump to the words after them */
#define POPS_TROJAN_REF_BLOCK1   0x02u /* anything else in POPStarter's first part */
#define POPS_TROJAN_REF_480P     0x04u
#define POPS_TROJAN_REF_BLOCK2   0x08u /* the second part outside the 480p handler */
#define POPS_TROJAN_REF_BUILTIN  0x10u
#define POPS_TROJAN_REF_OWNED    0x20u /* POPStarter's code where launcHER's resident image is */
#define POPS_TROJAN_REF_MAIN     0x40u /* a jump, load or store into POPStarter's program */

/* Bytes of work memory pops_trojan_scan needs for a payload of `size` bytes. */
#define POPS_TROJAN_SCAN_WORK(size) ((((size) / 4u + 7u) / 8u) * 2u)

/* Follows the payload's code from `entry` and from every address in the
 * payload that a jump it contains or builds can reach, and reports which of
 * the places above it names: direct j/jal, constants made by lui with
 * ori/addiu/addi/daddiu/daddi (a constant that is itself a j/jal word counts
 * as that jump: payloads install such words into POPS), loads and stores
 * through such a constant or through gp (POPS's 0x50a670), and jr/jalr of
 * one. Constants are forgotten at every branch and call. This is a static
 * reading: an address the payload computes any other way is not seen, so a
 * clean result is not proof that a payload needs nothing of POPStarter's.
 * The payload's own range never counts. Returns 0 with *flags set, or
 * POPS_FILE_INVALID for a bad argument, a size or address that is not a
 * multiple of 4, an entry outside the payload or too little work memory. */
int pops_trojan_scan(const void *payload, uint32_t size, uint32_t load, uint32_t entry,
                     void *work, size_t work_size, uint32_t *flags);

/* Why launcHER does not load a file POPStarter would apply. POPStarter
 * copies any payload to any address and writes any hook; launcHER loads
 * only what it can place without damaging POPS or itself, and only when
 * nothing the payload names is missing. */
enum {
  POPS_TROJAN_HOSTED = 0,
  POPS_TROJAN_NO_UNALIGNED, /* load, entry, hook or size not a multiple of 4 */
  POPS_TROJAN_NO_ENTRY,     /* entry outside the payload */
  POPS_TROJAN_NO_RANGE,     /* payload not wholly in the core or in the arena, or over POPStarter's parts */
  POPS_TROJAN_NO_HOOK,      /* hook outside the POPS core, inside the payload, or in POPStarter's parts but not a slot */
  POPS_TROJAN_NO_SPACE,     /* more payloads or payload bytes than one launch can hold */
  POPS_TROJAN_NO_SLOT,      /* needs the slot chain and it cannot be offered, or its hook words run past the slots */
  POPS_TROJAN_NO_480P,      /* names POPStarter's 480p handler */
  POPS_TROJAN_NO_BLOCK2,    /* names POPStarter's second part */
  POPS_TROJAN_NO_BUILTIN,   /* names a built-in entry's fix code */
  POPS_TROJAN_NO_OWNED,     /* names POPStarter's code at 0x0143a000..0x014601ff */
  POPS_TROJAN_NO_BLOCK1,    /* names POPStarter's first part outside the slots */
  POPS_TROJAN_NO_MAIN       /* names POPStarter's program */
};

/* A short English clause for a POPS_TROJAN_NO_* value, for the launch log. */
const char *pops_trojan_reason_text(unsigned reason);

/* A payload that loads above the POPS image. Its bytes wait in the set's
 * holding memory until the launch hands over (pops_trojan_copy_out). */
#define POPS_TROJAN_MAX_PAYLOADS 20u /* ten root files and ten of the game */
typedef struct {
  uint32_t address;
  uint32_t size;
  uint32_t hold; /* offset in the holding memory */
} PopsTrojanPayload;

/* One launch's TROJAN state, shared by every TROJAN_n.BIN of both scopes.
 * pops_trojan_set_init it, then set the holding memory and the work
 * memory. Without holding memory no payload above the image is hosted;
 * without work memory (POPS_TROJAN_SCAN_WORK of the payload) no file is.
 * slot_word is what POPStarter would have in its two runs of slots after
 * the files so far: a file that hooks a slot changes the copy here, never
 * the POPS core, and the launcher installs the copy when the launch can
 * offer the chain (chain_offered, set by the caller before the first file;
 * pops_resident_hook_slot_chain installs it). */
typedef struct {
  uint16_t fingerprint_id; /* built-in entry picked by the disc's fingerprint, 0: none */
  uint8_t reason;          /* POPS_TROJAN_NO_* of the last unhosted file */
  uint8_t payload_count;
  uint32_t refs;           /* POPS_TROJAN_REF_* of the last scanned file */
  uint8_t *hold;
  uint32_t hold_size;
  uint32_t hold_used;
  void *work;
  uint32_t work_size;
  uint8_t chain_offered;   /* the launch can install the slot chain */
  uint8_t chain;           /* a hosted file hooks a slot or names one */
  uint32_t slot_word[2][POPS_TROJAN_SLOTS_HOOKS / 4]; /* from 0x2327d0, from 0x232d08 */
  PopsTrojanPayload payload[POPS_TROJAN_MAX_PAYLOADS];
} PopsTrojanSet;

/* Zeroes the set and fills both runs with empty slots. fingerprint_break:
 * the fingerprint's built-in entry has a breakpoint handler, whose call
 * POPStarter writes at 0x232d08 before it reads any TROJAN file. */
void pops_trojan_set_init(PopsTrojanSet *set, unsigned fingerprint_id, int fingerprint_break);

/* Whether [address, address + size) is arena memory launcHER can give a payload. */
int pops_trojan_in_arena(uint32_t address, uint32_t size);

/* A range the copy must leave alone, [start, end). */
typedef struct {
  uint32_t start;
  uint32_t end;
} PopsTrojanKeep;

/* Copies every held payload to its address, in the order the files were
 * read (a later file wins where two overlap, as with the original's
 * memcpy). `ram` is the memory at address `ram_base`, valid up to
 * `ram_limit`. Before the first byte is written every record is checked
 * again: inside the arena, inside the given memory, off every `keep`
 * range, and inside the holding memory, which no destination may touch.
 * Returns the number of payloads copied, or POPS_FILE_INVALID with nothing
 * written. */
int pops_trojan_copy_out(const PopsTrojanSet *set, uint8_t *ram, uint32_t ram_base,
                         uint32_t ram_limit, const PopsTrojanKeep *keep, unsigned keep_count);

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
