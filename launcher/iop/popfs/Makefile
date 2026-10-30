IOP_BIN = popfs.irx
IOP_OBJS = popfs.o pops_pad_swap.o pops_trace.o pops_ioplib.o pops_pad_sio2.o imports.o
IOP_CFLAGS += -Wall -Wextra -Werror -DIOMANX_OLD_NAME_COMPATIBILITY=0 -DIOMANX_OLD_NAME_ADDDELDRV=0
# GCC 14 errors on the SDK import-table macro for 8-char module names ("loadcore");
# the macro does not mark the char[8] field nonstring. pops_iomanx ships the
# same import without -Werror. Keep the diagnostic, drop only the fatality.
IOP_CFLAGS += -Wno-error=unterminated-string-initialization

include ../udpfs/Rules.make
