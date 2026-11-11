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
    (0x91ba70, 0x91bdc8, 0x91bbb8, 0x91bb38): a file table of SkinFile
    objects (below), which can also misbehave the way a device might;
  - memset (0x9188b8; it uses R5900 128-bit instructions Unicorn lacks);
  - the POPS-folder check FUN_008d8958, only reached when gp+0x3868 != 1.
No memory-write hook is used: the caller gets the whole core after the run
and every other byte of memory that changed. Needs POPSTARTER_TEST_ELF and
POPS_TEST_ELF. Nothing here is a console run.

SkinFile and Handle need no inputs and no Unicorn: tools/test_pops_igr_skin.py
drives launcHER's own reader with the same objects, so both sides see one
device model.
"""
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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

SEEK_SET, SEEK_CUR, SEEK_END = 0, 1, 2


class SkinFile:
    """One file as a device presents it. With only `data` it behaves.

    size      what a seek to the end returns instead of len(data). Negative
              is a failed size query: the position does not move.
    total     the most bytes the device ever delivers from one open handle,
              over all its reads (a device that stops for good).
    after     what a read returns once `total` is used up: 0, or a negative
              error.
    per_read  the most bytes one read call delivers (a device that hands the
              file over in pieces; asking again gets the next piece).
    rewind    what a seek to the start returns instead of 0; the position
              then stays where it was (at the end, after the size query).
    extra     added to the count a read returns when it delivered all that
              was asked for (a driver that over-reports; the bytes written
              are still the bytes asked for).
    """

    def __init__(self, data, size=None, total=None, after=0, per_read=None, rewind=None, extra=0):
        self.data = bytes(data)
        self.size, self.total, self.after = size, total, after
        self.per_read, self.rewind, self.extra = per_read, rewind, extra

    def open(self):
        return Handle(self)


def as_file(value):
    return value if isinstance(value, SkinFile) else SkinFile(value)


class Handle:
    def __init__(self, f):
        self.f, self.pos, self.delivered = f, 0, 0

    def lseek(self, offset, whence):
        f = self.f
        if whence == SEEK_END:
            if f.size is not None:
                if f.size >= 0:
                    self.pos = f.size + offset
                return f.size
            self.pos = len(f.data) + offset
        elif whence == SEEK_SET:
            if f.rewind is not None:
                return f.rewind
            self.pos = offset
        else:
            self.pos += offset
        return self.pos

    def read(self, want):
        """(count the call returns, bytes it stored)."""
        f = self.f
        if f.total is not None and self.delivered >= f.total:
            return f.after, b""
        n = want
        if f.per_read is not None:
            n = min(n, f.per_read)
        if f.total is not None:
            n = min(n, f.total - self.delivered)
        chunk = f.data[self.pos:self.pos + n] if self.pos >= 0 else b""
        self.pos += len(chunk)
        self.delivered += len(chunk)
        count = len(chunk)
        if f.extra and want and len(chunk) == want:
            count += f.extra
        return count, chunk


class Emulator:
    """One Unicorn instance, reused: run() restores the core and the flags."""

    def __init__(self, core):
        from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
        from trace_original_pops_io import decode_main
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
            f = st["files"].get(path)
            fd = -2
            if f is not None:
                fd = st["next_fd"]
                st["next_fd"] += 1
                st["fds"][fd] = as_file(f).open()
            log.append(("open", OPEN.index(addr), path, a1, fd))
            self._ret(fd)
        elif addr in LSEEK:
            offset = a1 - (1 << 32) if a1 & 0x80000000 else a1
            pos = st["fds"][a0].lseek(offset, a2)
            log.append(("lseek", a0, offset, a2, pos))
            self._ret(pos)
        elif addr in READ:
            count, chunk = st["fds"][a0].read(a2)
            if chunk:
                uc.mem_write(a1, chunk)
            log.append(("read", a0, a1, a2, count))
            self._ret(count)
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

    def run(self, files, backend=0, abort=0, checked=1, quiet=0, dircheck=1, core=None):
        """files: {full path: bytes or SkinFile}. Returns a dict with the
        return value, the call log, the core afterwards and what else
        changed in memory."""
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
                      "dircheck": dircheck}
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
    from trace_original_pops_warmboot import core_image
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
        ("size query returns -5, pfs",
         dict(files={PREFIX[0] + NAMES[1]: SkinFile(b"\x22" * 64, size=-5)})),
        ("each read delivers 10 of 64 bytes",
         dict(files={PREFIX[0] + NAMES[2]: SkinFile(b"\x33" * 64, per_read=10)})),
        ("the device stops for good after 10 of 64 bytes",
         dict(files={PREFIX[0] + NAMES[2]: SkinFile(b"\x33" * 64, total=10, after=-5)})),
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
