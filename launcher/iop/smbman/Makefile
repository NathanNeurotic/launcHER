IOP_BIN = launcher_smbman.irx
IOP_OBJS = smbman.o smb_fio.o smb.o poll.o auth.o des.o md4.o imports.o
IOP_SRC_DIR = $(CURDIR)/src/
IOP_INCS = -I$(CURDIR)/src -I$(CURDIR)/include
IOP_LIBS += -lgcc
include ../udpfs/Rules.make
$(IOP_OBJS_DIR)smb.o: src/smb_open_contract.h
