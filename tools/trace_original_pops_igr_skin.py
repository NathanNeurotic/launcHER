#!/usr/bin/env python3
"""Run POPStarter r13's IGR skin loader over a POPS core (external inputs only).

The loader is one function, FUN_0087e464 (0x87e464..0x87eb20), called once
from the launch function at 0x876b18. It opens IGR_BG.TM2, IGR_NO.TM2 and
IGR_YES.TM2 from the device's POPS folder ("pfs1:/POPS/" when gp+0x3448 is
0, "mass:/POPS/" when it is 1) and copies each over the TIM2 file Sony's
POPS embeds for its own in-game reset dialog.

This runs the function as shipped under Unicorn, with POPSTARTER MAIN and
the POPS core mapped at their own addresses. Only what it calls is modelled:
  - printf (0x915708): the format string is recorded;
  - the pfs backend's open/lseek/read/close (0x916758, 0x916c08, 0x9169b0,
    0x916878) and the calls the mass backend's four thin wrappers
    (0x8d6c94, 0x8d6d64, 0x8d6d24, 0x8d6cf4, run as shipped) end in
    (0x91ba70, 0x91bdc8, 0x91bbb8, 0x91bb38): an in-memory file table;
  - memset (0x9188b8; it uses R5900 128-bit instructions Unicorn lacks);
  - the POPS-folder check FUN_008d8958, only reached when gp+0x3868 != 1.
No memory-write hook is used: the caller gets the whole core after the run
and every other byte of memory that changed. Needs POPSTARTER_TEST_ELF and
POPS_TEST_ELF. Nothing here is a console run.
"""
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_original_pops_io import decode_main  # noqa: E402
from trace_original_pops_warmboot import core_image  # noqa: E402

BASE = 0x870000
GP = 0x9B68F0
FUNC = 0x87E464
FUNC_END = 0x87EB24
CORE_BASE = 0x200000
STACK = 0x1E00000
STOP = 0x1FF0000
MEM_SIZE = 0x02000000

PRINTF = 0x915708
MEMSET = 0x9188B8
DIRCHECK = 0x8D8958
# backend 0 (gp+0x3448 == 0) calls these directly; backend 1 goes through
# four wrappers that end in the second set.
OPEN, LSEEK, READ, CLOSE = (0x916758, 0x91BA70), (0x916C08, 0x91BDC8), (0x9169B0, 0x91BBB8), (0x916878, 0x91BB38)
WRAPPERS = (0x8D6C94, 0x8D6DA4)

FLAG_ABORT = 0x38DC    # shared "stop loading" flag; the loader returns 0 when it is 1
FLAG_CHECKED = 0x3868  # POPS folder already checked
FLAG_BACKEND = 0x3448  # 0: pfs1:/POPS/, 1: mass:/POPS/
FLAG_QUIET = 0x38B0    # 1: no printf

PREFIX = {0: "pfs1:/POPS/", 1: "mass:/POPS/"}
NAMES = ("IGR_BG.TM2", "IGR_NO.TM2", "IGR_YES.TM2")


class Emulator:
    """One Unicorn instance, reused: run() restores the core and the flags."""

    def __init__(self, core):
        from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
        self.main = bytes(decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes()))
        self.core = bytes(core)
        self.uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
        try:
            self.uc.ctl_set_cpu_model(5)  # UC_CPU_MIPS64_5KF, as the other tracers
        except Exception:
            pass
        self.uc.mem_map(0, MEM_SIZE)
        self.uc.hook_add(UC_HOOK_CODE, self._code)
        self.state = None

    def _ret(self, value):
        from unicorn.mips_const import UC_MIPS_REG_PC, UC_MIPS_REG_RA, UC_MIPS_REG_V0
        self.uc.reg_write(UC_MIPS_REG_V0, value & 0xFFFFFFFFFFFFFFFF)
        self.uc.reg_write(UC_MIPS_REG_PC, self.uc.reg_read(UC_MIPS_REG_RA))

    def _cstr(self, addr):
        raw = bytes(self.uc.mem_read(addr, 256))
        return raw[:raw.index(0)].decode("ascii", "replace")

    def _code(self, uc, addr, _size, _user):
        from unicorn.mips_const import UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2
        st = self.state
        if addr == STOP:
            uc.emu_stop()
            return
        if FUNC <= addr < FUNC_END or WRAPPERS[0] <= addr < WRAPPERS[1]:
            return
        a0, a1, a2 = (uc.reg_read(r) & 0xFFFFFFFF for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2))
        log = st["log"]
        if addr == PRINTF:
            log.append(("print", self._cstr(a0)))
            self._ret(0)
        elif addr in OPEN:
            path = self._cstr(a0)
            data = st["files"].get(path)
            fd = -2
            if data is not None:
                fd = st["next_fd"]
                st["next_fd"] += 1
                st["fds"][fd] = [bytes(data), 0]
            log.append(("open", OPEN.index(addr), path, a1, fd))
            self._ret(fd)
        elif addr in LSEEK:
            entry = st["fds"][a0]
            offset = a1 - (1 << 32) if a1 & 0x80000000 else a1
            if a2 == 2 and st["seek_end"] is not None:
                pos = st["seek_end"]           # a modelled failure of the size query
            else:
                pos = offset if a2 == 0 else (len(entry[0]) + offset if a2 == 2 else entry[1] + offset)
                entry[1] = pos
            log.append(("lseek", a0, offset, a2, pos))
            self._ret(pos)
        elif addr in READ:
            entry = st["fds"][a0]
            want = a2 if st["read_limit"] is None else min(a2, st["read_limit"])
            chunk = entry[0][entry[1]:entry[1] + want]
            if chunk:
                uc.mem_write(a1, chunk)
            entry[1] += len(chunk)
            log.append(("read", a0, a1, a2, len(chunk)))
            self._ret(len(chunk))
        elif addr in CLOSE:
            log.append(("close", a0))
            st["fds"].pop(a0, None)
            self._ret(0)
        elif addr == MEMSET:
            log.append(("memset", a0, a1 & 0xFF, a2))
            if a2 > 0x100000:
                st["error"] = "memset length %#x" % a2
                uc.emu_stop()
                return
            if a2:
                uc.mem_write(a0, bytes([a1 & 0xFF]) * a2)
            self._ret(a0)
        elif addr == DIRCHECK:
            log.append(("dircheck",))
            self._ret(st["dircheck"])
        else:
            st["error"] = "left the loader at %#x" % addr
            uc.emu_stop()

    def run(self, files, backend=0, abort=0, checked=1, quiet=0, dircheck=1,
            seek_end=None, read_limit=None, core=None):
        """files: {full path: bytes}. Returns a dict with the return value,
        the call log, the core afterwards and what else changed in memory.
        seek_end: value every lseek(fd, 0, SEEK_END) returns instead of the
        size; read_limit: most bytes one read delivers."""
        from unicorn.mips_const import UC_MIPS_REG_GP, UC_MIPS_REG_RA, UC_MIPS_REG_SP, UC_MIPS_REG_V0
        uc = self.uc
        before_core = self.core if core is None else bytes(core)
        uc.mem_write(0, bytes(CORE_BASE))
        uc.mem_write(CORE_BASE, before_core)
        uc.mem_write(BASE, self.main)
        uc.mem_write(STACK - 0x1000, bytes(0x1000))
        for flag, value in ((FLAG_ABORT, abort), (FLAG_CHECKED, checked),
                            (FLAG_BACKEND, backend), (FLAG_QUIET, quiet)):
            uc.mem_write(GP + flag, struct.pack("<I", value))
        before = bytes(uc.mem_read(0, MEM_SIZE))
        uc.reg_write(UC_MIPS_REG_GP, GP)
        uc.reg_write(UC_MIPS_REG_SP, STACK)
        uc.reg_write(UC_MIPS_REG_RA, STOP)
        self.state = {"files": files, "fds": {}, "next_fd": 3, "log": [], "error": None,
                      "dircheck": dircheck, "seek_end": seek_end, "read_limit": read_limit}
        uc.emu_start(FUNC, STOP, count=4_000_000)
        st = self.state
        if st["error"]:
            raise RuntimeError(st["error"])
        value = uc.reg_read(UC_MIPS_REG_V0) & 0xFFFFFFFF
        after = bytes(uc.mem_read(0, MEM_SIZE))
        core_end = CORE_BASE + len(before_core)
        outside = []
        for off in range(0, MEM_SIZE, 0x1000):
            if before[off:off + 0x1000] == after[off:off + 0x1000]:
                continue
            for i in range(off, off + 0x1000):
                if before[i] != after[i] and not (CORE_BASE <= i < core_end) and \
                        not (STACK - 0x1000 <= i < STACK):
                    outside.append(i)
        return {"ret": value - (1 << 32) if value & 0x80000000 else value,
                "log": st["log"],
                "prints": [e[1] for e in st["log"] if e[0] == "print"],
                "core": after[CORE_BASE:core_end],
                "outside": outside,
                "open_fds": sorted(st["fds"]),
                "abort": struct.unpack_from("<I", after, GP + FLAG_ABORT)[0]}


def changed_ranges(before, after, base=CORE_BASE):
    out, start = [], None
    for off in range(0, len(before), 0x1000):
        if before[off:off + 0x1000] == after[off:off + 0x1000]:
            continue
        for i in range(off, min(off + 0x1000, len(before))):
            if before[i] != after[i]:
                if start is None:
                    start = prev = i
                elif i != prev + 1:
                    out.append((base + start, base + prev + 1))
                    start = i
                prev = i
    if start is not None:
        out.append((base + start, base + prev + 1))
    return out


def main():
    core = core_image(os.environ["POPS_TEST_ELF"])
    emu = Emulator(core)
    cases = [
        ("no files, pfs", dict(files={}, backend=0)),
        ("no files, mass", dict(files={}, backend=1)),
        ("full-size files, pfs", dict(files={PREFIX[0] + NAMES[0]: b"\x11" * 0x4C300,
                                             PREFIX[0] + NAMES[1]: b"\x22" * 0x1DBC,
                                             PREFIX[0] + NAMES[2]: b"\x33" * 0x1DBC}, backend=0)),
        ("one byte too big, mass", dict(files={PREFIX[1] + NAMES[0]: b"\x11" * 0x4C301,
                                               PREFIX[1] + NAMES[1]: b"\x22" * 0x1DBD,
                                               PREFIX[1] + NAMES[2]: b"\x33" * 0x1DBD}, backend=1)),
        ("empty NO, pfs", dict(files={PREFIX[0] + NAMES[1]: b""}, backend=0)),
        ("abort flag set", dict(files={PREFIX[0] + NAMES[0]: b"\x11" * 16}, abort=1)),
        ("folder check fails", dict(files={PREFIX[0] + NAMES[0]: b"\x11" * 16}, checked=0, dircheck=-666)),
        ("size query returns -5, pfs", dict(files={PREFIX[0] + NAMES[1]: b"\x22" * 64}, seek_end=-5)),
        ("read delivers 10 of 64 bytes", dict(files={PREFIX[0] + NAMES[2]: b"\x33" * 64}, read_limit=10)),
    ]
    for title, kw in cases:
        r = emu.run(**kw)
        print("== %s: ret %d abort flag %d" % (title, r["ret"], r["abort"]))
        for e in r["log"]:
            print("   ", " ".join(hex(x) if isinstance(x, int) and x > 9 else repr(x) for x in e))
        print("    core ranges changed:", ["%#x..%#x" % ab for ab in changed_ranges(core, r["core"])])
        print("    other memory changed:", ["%#x" % a for a in r["outside"][:8]], len(r["outside"]))


if __name__ == "__main__":
    main()
