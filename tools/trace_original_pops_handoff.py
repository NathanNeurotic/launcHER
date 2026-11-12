#!/usr/bin/env python3
"""Run the last part of POPStarter r13's launch, up to its ExecPS2 (external inputs only).

The tail of r13's launch function, MAIN 0x87c0d4..0x87c1d0, is what runs
between the last IOP-side action and the jump into POPS: Status to kernel
mode, memset of the whole scratchpad, Status back to user mode, memset of
POPS's BSS up to r13's own code, memset of 0x100000..0x200000, memset of r13's
own staging buffer, FlushCache(0), FlushCache(2), six file/SIF service calls
(closed and opened again), SetVCommonHandler when a preset byte asks for it,
and ExecPS2 through the syscall-7 stub.

This runs that code as shipped under Unicorn, with POPSTARTER MAIN mapped at
0x870000. Only what it calls is modelled, and each call is recorded:
  - the two Status helpers 0x8706a8 (read) and 0x8706d0 (write): Status is a
    value the caller passes in, a write stores it;
  - memset (0x9188b8; it uses R5900 128-bit instructions Unicorn lacks);
  - the FlushCache stub (0x91ab70);
  - fioExit 0x91ba18, SifExitRpc 0x91b7c0, SifInitRpc 0x91b658,
    SifLoadFileInit 0x91c0d0, SifInitCmd 0x91acb0, fioInit 0x91b908;
  - the SetVCommonHandler stub (0x91aaa0) and the ExecPS2 stub (0x91aa90),
    which ends the run with its four arguments.
Any other call ends the run with an error. The thread table is not modelled:
r13 has no CreateThread, StartThread, TerminateThread or DeleteThread stub at
all (tools/test_pops_handoff.py checks that on the same image), so it reaches
this code as the kernel's only thread.

Needs POPSTARTER_TEST_ELF and unicorn. Nothing here is a console run."""
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE = 0x870000
GP = 0x9B68F0
START = 0x87C0D4            # after the last IOP-side action and the optional delay
TAIL_END = 0x87C1D8         # the dead jump after the ExecPS2 call
MEM_SIZE = 0x02000000
SPAD, SPAD_SIZE = 0x70000000, 0x4000
STACK = 0x01FF0000
FRAME = 0x01FE8000          # main's frame pointer; argv is read from 0x14(fp)

STATUS_GET, STATUS_SET = 0x8706A8, 0x8706D0
MEMSET = 0x9188B8
FLUSHCACHE = 0x91AB70
SETVCOMMON = 0x91AAA0
EXECPS2 = 0x91AA90
SERVICES = {0x91BA18: "fioExit", 0x91B7C0: "SifExitRpc", 0x91B658: "SifInitRpc",
            0x91C0D0: "SifLoadFileInit", 0x91ACB0: "SifInitCmd", 0x91B908: "fioInit"}

GP_STAGING_SIZE = 0x28E0    # gp offset of the size r13 clears at 0x972390
GP_VCOMMON = 0x3818         # 1: SetVCommonHandler(8, 0x80000280) before ExecPS2


class Tail:
    """One Unicorn instance; run() maps a fresh memory image each time."""

    def __init__(self):
        from trace_original_pops_io import decode_main
        self.main = bytes(decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes()))

    def run(self, fill=0xA5, status=0x70030C11, staging_size=0x1000, vcommon=0, argv=0x01FE9000):
        """Returns {"log": [...], "exec": (a0, a1, a2, a3), "status": last Status,
        "mem": callable(lo, hi) -> bytes, "fill": fill}. Memory below MAIN and
        the scratchpad start filled with `fill`."""
        from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
        from unicorn.mips_const import (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3,
                                        UC_MIPS_REG_GP, UC_MIPS_REG_SP, UC_MIPS_REG_FP, UC_MIPS_REG_PC,
                                        UC_MIPS_REG_RA, UC_MIPS_REG_V0)
        uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
        try:
            uc.ctl_set_cpu_model(5)  # UC_CPU_MIPS64_5KF, as the other tracers
        except Exception:
            pass
        uc.mem_map(0, MEM_SIZE)
        uc.mem_map(SPAD, 0x10000)
        uc.mem_write(0x00080000, bytes([fill]) * (BASE - 0x00080000))
        uc.mem_write(SPAD, bytes([fill]) * 0x10000)
        uc.mem_write(BASE, self.main)
        uc.mem_write(GP + GP_STAGING_SIZE, struct.pack("<I", staging_size))
        uc.mem_write(GP + GP_VCOMMON, struct.pack("<I", vcommon))
        uc.mem_write(FRAME + 0x14, struct.pack("<I", argv))
        state = {"log": [], "exec": None, "status": status, "error": None}

        def ret(value=0):
            uc.reg_write(UC_MIPS_REG_V0, value & 0xFFFFFFFFFFFFFFFF)
            uc.reg_write(UC_MIPS_REG_PC, uc.reg_read(UC_MIPS_REG_RA))

        def code(_uc, addr, _size, _user):
            if START <= addr < TAIL_END:
                return
            a = [uc.reg_read(r) & 0xFFFFFFFF for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1,
                                                         UC_MIPS_REG_A2, UC_MIPS_REG_A3)]
            log = state["log"]
            if addr == STATUS_GET:
                log.append(("status_get",))
                ret(state["status"])
            elif addr == STATUS_SET:
                log.append(("status_set", a[0]))
                state["status"] = a[0]
                ret(0)
            elif addr == MEMSET:
                log.append(("memset", a[0], a[1] & 0xFF, a[2], state["status"]))
                if a[2] > 0x00800000:
                    state["error"] = "memset length %#x" % a[2]
                    uc.emu_stop()
                    return
                if a[2]:
                    uc.mem_write(a[0], bytes([a[1] & 0xFF]) * a[2])
                ret(a[0])
            elif addr == FLUSHCACHE:
                log.append(("FlushCache", a[0]))
                ret(0)
            elif addr in SERVICES:
                log.append((SERVICES[addr], a[0]))
                ret(0)
            elif addr == SETVCOMMON:
                log.append(("SetVCommonHandler", a[0], a[1]))
                ret(0)
            elif addr == EXECPS2:
                log.append(("ExecPS2", a[0], a[1], a[2], a[3]))
                state["exec"] = tuple(a)
                uc.emu_stop()
            else:
                state["error"] = "left the tail at %#x" % addr
                uc.emu_stop()

        uc.hook_add(UC_HOOK_CODE, code)
        uc.reg_write(UC_MIPS_REG_GP, GP)
        uc.reg_write(UC_MIPS_REG_SP, STACK)
        uc.reg_write(UC_MIPS_REG_FP, FRAME)
        uc.reg_write(UC_MIPS_REG_RA, 0)
        uc.emu_start(START, TAIL_END, count=1_000_000)
        if state["error"]:
            raise RuntimeError(state["error"])
        if state["exec"] is None:
            raise RuntimeError("the tail did not reach ExecPS2")
        return {"log": state["log"], "exec": state["exec"], "status": state["status"],
                "mem": lambda lo, hi: bytes(uc.mem_read(lo, hi - lo)), "fill": fill}


def main():
    r = Tail().run()
    for entry in r["log"]:
        print("   ", " ".join(hex(x) if isinstance(x, int) and x > 9 else repr(x) for x in entry))
    print("ExecPS2(%#x, %#x, %#x, %#x)" % r["exec"])


if __name__ == "__main__":
    main()
