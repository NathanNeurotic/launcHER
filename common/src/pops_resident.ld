/* Flat layout for launcHER's POPS resident image (pops_resident.h). The
 * header must come first; everything after file_end is zeroed by the
 * launcher. */
ENTRY(pops_resident_vblank)

SECTIONS
{
  . = 0x0143a000;
  .text : {
    KEEP(*(.resident.head))
    *(.text .text.*)
  }
  .rodata : { *(.rodata .rodata.*) }
  .data : {
    *(.data .data.* .sdata .sdata.*)
    LONG(0x444e4524) /* end marker: keeps the section, so the file ends aligned */
    . = ALIGN(16);
  }
  _pops_resident_file_end = .;
  .bss (NOLOAD) : { *(.bss .bss.* .sbss .sbss.* COMMON) }
  . = ALIGN(16);
  _pops_resident_end = .;
  /DISCARD/ : { *(.comment) *(.note*) *(.MIPS.*) *(.reginfo) *(.pdr) *(.gnu.attributes) *(.mdebug.*) }
}
