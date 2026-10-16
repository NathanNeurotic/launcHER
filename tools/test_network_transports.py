#!/usr/bin/env python3
"""Compile production network helpers/transport; inject stale ACKs and rediscovery."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
cc = os.environ.get("CC", "cc")
if not shutil.which(cc): raise SystemExit("C compiler required")
with tempfile.TemporaryDirectory(prefix="launcher-net-") as work:
    work = Path(work)
    (work/"irx.h").write_text("")
    (work/"tamtypes.h").write_text("#include <stdint.h>\ntypedef uint8_t u8;\n")
    (work/"iomanX.h").write_text('''#include <stdint.h>
typedef struct { uint32_t mode,attr,size,hisize; char ctime[8],atime[8],mtime[8]; } iox_stat_t;
''')
    (work/"fileXio_rpc.h").write_text("int fileXioDevctl(const char *,int,void *,unsigned,void *,unsigned);\n")
    (work/"msg.h").write_text("void msg(const char *,...);\n")
    (work/"bdm.h").write_text('''#include <stdint.h>
struct block_device {
 const char *name,*path; unsigned devNr,parNr; uint64_t sectorOffset,sectorCount;
 uint32_t sectorSize; void *priv;
 int (*read)(struct block_device *,uint64_t,void *,uint16_t);
 int (*write)(struct block_device *,uint64_t,const void *,uint16_t);
 void (*flush)(struct block_device *); int (*stop)(struct block_device *);
};
void bdm_connect_bd(struct block_device *);
void bdm_disconnect_bd(struct block_device *);
''')
    (work/"thevent.h").write_text('''#include <stdint.h>
typedef struct { int attr,option; uint32_t bits; } iop_event_t;
#define WEF_OR 1
#define WEF_CLEAR 0x10
int CreateEventFlag(iop_event_t *);
int DeleteEventFlag(int);
int SetEventFlag(int,uint32_t);
int iSetEventFlag(int,uint32_t);
int ClearEventFlag(int,uint32_t);
int WaitEventFlag(int,uint32_t,int,uint32_t *);
''')
    (work/"thbase.h").write_text('''#include <stdint.h>
typedef struct { uint32_t lo,hi; } iop_sys_clock_t;
void USec2SysClock(uint32_t,iop_sys_clock_t *);
int SetAlarm(iop_sys_clock_t *,unsigned int (*)(void *),void *);
int CancelAlarm(unsigned int (*)(void *),void *);
int DelayThread(int);
''')
    for name, sources, includes in [
      ("config", ["tools/fixtures/test_network_config.c", "common/src/network_config.c"],
       ["launcher/include", "launcher/iop/smbman/src"]),
      ("udprdma", ["tools/fixtures/test_udprdma.c"], ["launcher/iop/udpfs/udpfs/include",
        "launcher/iop/udpfs/common", "launcher/iop/udpfs/ministack/include", "launcher/iop/udpfs/smap/include"]),
      ("udpbd", ["tools/fixtures/test_udpbd.c"], ["launcher/iop/udpfs/udpbd/include",
        "launcher/iop/udpfs/common", "launcher/iop/udpfs/ministack/include", "launcher/iop/udpfs/smap/include"]),
      ("smb_session", ["tools/fixtures/test_smb_session.c", "launcher/src/handler_smb.c", "common/src/network_config.c"],
        ["launcher/include", "launcher/iop/smbman/include"]),
      ("udpfs_close", ["tools/fixtures/test_udpfs_close.c"], ["launcher/iop/udpfs/udpfs/include",
        "launcher/iop/udpfs/common", "launcher/iop/udpfs/ministack/include"]),
    ]:
        output = work/(name+(".exe" if os.name=="nt" else ""))
        args = [cc,"-std=c11","-Wall","-Wextra","-Wno-unused-parameter", "-I",str(work)]
        if name=="smb_session":
            args += ["-D_COMMON_H_", "-include",str(work/"msg.h"),
                     "-Dopen=fake_open", "-Dread=fake_read", "-Dclose=fake_close"]
        for path in includes: args += ["-I",str(ROOT/path)]
        args += [str(ROOT/s) for s in sources]+["-o",str(output)]
        subprocess.run(args,check=True)
        subprocess.run([str(output)],check=True,timeout=15)
