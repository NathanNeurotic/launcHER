IOP_BIN = bdmfs_fatfs.irx
IOP_OBJS = main.o imports.o fs_driver.o diskio.o ff.o ffsystem.o ffunicode.o
IOP_SRC_DIR = $(CURDIR)/src/
IOP_INCS = -I$(CURDIR)/src -I$(CURDIR)/src/include -I$(FATFS_ROOT)/source/include
IOP_LIBS += -lgcc
include ../udpfs/Rules.make

vpath %.c $(FATFS_ROOT)/source/
$(IOP_OBJS_DIR)%.o: $(FATFS_ROOT)/source/%.c
	$(DIR_GUARD)
	$(IOP_C_COMPILE) -c $< -o $@

$(IOP_OBJS_DIR)fs_driver.o: src/include/fatfs_errno.h
