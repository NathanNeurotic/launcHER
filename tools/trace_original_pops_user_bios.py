#!/usr/bin/env python3
"""Run POPStarter r13's user BIOS.BIN loader and the code its flags gate.

External inputs only: POPSTARTER_TEST_ELF (the original, unpacked at run time
by trace_original_pops_io.decode_main) and, for the callers that want the
real core, POPS_TEST_ELF. No original byte is stored here or written out.

What is run, as shipped, under Unicorn (MIPS64 LE, 5KF, MAIN at 0x870000,
gp=0x9b68f0, a core image at 0x200000):

  handler()    FUN_0088019c (0x88019c..0x880a20), the BIOS.BIN loader, with
               its open/lseek/read/close calls modelled for both back ends
               (gp+0x3448 == 0: 0x916758/0x916c08/0x9169b0/0x916878;
               == 1: 0x91ba70/0x91bdc8/0x91bbb8/0x91bb38 behind the wrappers
               at 0x8d6c94..0x8d6da0, which run as shipped).
  main_gate()  the launch function's own tests in front of each call
               (0x876bb4..0x876ce0 all games, 0x876ea8..0x876fe0 game).
  shell()      the three PS1 BIOS shell edits (0x878f64..0x878fc4).
  region()     the region pass (0x879034..0x8795f0), PAL helper included.
  mode()       FUN_008dc2c4, the compatibility mode dispatcher.
  parser()     the CHEATS.TXT section (tools/trace_original_pops_cheats.py)
               with loader flags preset and a core image mapped.

Each returns the core afterwards (diff it against the one passed in; no
live memory-write hook is used) and the loader flags. A call to anything
that is not modelled stops the run with an error. Nothing here is a console
run.
"""
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_original_pops_io import decode_main  # noqa: E402

BASE = 0x870000
GP = 0x9B68F0
BSS = (0x9B9D00, 0x9CCAC0)
CORE_BASE = 0x200000
STACK = 0x1F00000
SENTINEL = 0x1FF0000
NAME = 0x1E00000

ROM_BASE = 0x24BC20
ROM_READ = 0x7FF90
ROM_MIN = 0x7FF8F
BRANCH_HALF = 0x20079A

# gp offsets of the loader state (docs/POPSTARTER_USER_BIOS.md).
FLAGS = {
    "bios_all": 0x38A4,
    "bios_game": 0x3B98,
    "osd_all_a": 0x343C,
    "osd_all_b": 0x3430,
    "osd_game_a": 0x3878,
    "osd_game_b": 0x344C,
    "osd_off": 0x3704,
    "abort": 0x38DC,          # shared "stop loading files" flag
    "game_dir_missing": 0x3460,
    "preset_osd_off": 0x3438,
}
# The eight preset compatibility slots main tests against 6.
PRESET_SLOTS = (0x3434, 0x3444, 0x38C8, 0x389C, 0x3708, 0x397C, 0x387C, 0x38D4)

PRINTF, STRLEN = 0x915708, 0x918E08
HANDLER = 0x88019C
# Helpers that run as shipped: peeks/pokes, I/O wrappers, the PAL helper,
# the OSD off/on helpers and the mode dispatcher's own pokes.
NATIVE = ((0x87C218, 0x87C330), (0x8D6B74, 0x8D6C94), (0x8D6C94, 0x8D6DA4),
          (0x8DC8E4, 0x8DC97C), (0x8DC218, 0x8DC2C4), (0x8DB97C, 0x8DBA90))

_IMAGE = None


def image():
    global _IMAGE
    if _IMAGE is None:
        _IMAGE = bytes(decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes()))
    return _IMAGE


def core_image(path=None):
    """The POPS core as launcHER stages it: one flat image from 0x200000."""
    data = Path(path or os.environ["POPS_TEST_ELF"]).read_bytes()
    phoff, = struct.unpack_from("<I", data, 0x1C)
    phnum, = struct.unpack_from("<H", data, 0x2C)
    segs = []
    for i in range(phnum):
        p_type, off, vaddr, _pa, filesz, _memsz = struct.unpack_from("<IIIIII", data, phoff + 32 * i)
        if p_type == 1 and filesz and CORE_BASE <= vaddr < 0x01000000:
            segs.append((vaddr, data[off:off + filesz]))
    end = max(va + len(b) for va, b in segs)
    img = bytearray(end - CORE_BASE)
    for va, b in segs:
        img[va - CORE_BASE:va - CORE_BASE + len(b)] = b
    return img


class Machine:
    """One Unicorn instance, reset before every run."""

    def __init__(self):
        from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
        from unicorn import mips_const as R
        self.R = R
        self.uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
        try:
            self.uc.ctl_set_cpu_model(R.UC_CPU_MIPS64_5KF)
        except Exception:
            pass
        self.uc.mem_map(0, 0x02000000)
        self.uc.hook_add(UC_HOOK_CODE, self._code)
        self.window = (0, 0)
        self.stop = SENTINEL
        self.hooks = {}
        self.error = None
        self.prints = []

    # -- state -----------------------------------------------------------
    def reset(self, core, flags=None):
        uc = self.uc
        uc.mem_write(BASE, image())
        uc.mem_write(BSS[0], bytes(BSS[1] - BSS[0]))
        uc.mem_write(STACK - 0x10000, bytes(0x10100))
        uc.mem_write(CORE_BASE, bytes(core))
        self.core_size = len(core)
        self.put(GP + 0x38B0, 0)  # not quiet: the messages are recorded
        for name, value in (flags or {}).items():
            self.put(GP + (FLAGS[name] if isinstance(name, str) else name), value)
        self.error = None
        self.prints = []
        self.hooks = {PRINTF: self._printf, STRLEN: lambda a: len(self.cstr(a[0]))}
        R = self.R
        uc.reg_write(R.UC_MIPS_REG_GP, GP)
        uc.reg_write(R.UC_MIPS_REG_SP, STACK - 0x4000)
        uc.reg_write(R.UC_MIPS_REG_FP, STACK - 0x4000)
        uc.reg_write(R.UC_MIPS_REG_RA, SENTINEL)

    def put(self, address, value):
        self.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    def get(self, address):
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def cstr(self, address, limit=400):
        out = bytearray()
        while len(out) < limit:
            byte = self.uc.mem_read(address + len(out), 1)[0]
            if not byte:
                break
            out.append(byte)
        return bytes(out)

    def flags(self):
        return {name: self.get(GP + off) for name, off in FLAGS.items()}

    def core(self):
        return bytearray(self.uc.mem_read(CORE_BASE, self.core_size))

    # -- execution -------------------------------------------------------
    def _printf(self, a):
        fmt = self.cstr(a[0])
        if b"%s" in fmt:
            fmt = fmt.replace(b"%s", self.cstr(a[1]), 1)
        self.prints.append(fmt)
        return 0

    def _code(self, uc, addr, size, _):
        R = self.R
        try:
            if addr == self.stop:
                uc.emu_stop()
                return
            if self.window[0] <= addr < self.window[1]:
                return
            hook = self.hooks.get(addr)
            if hook is None:
                if any(lo <= addr < hi for lo, hi in NATIVE):
                    return
                raise RuntimeError("unmodelled call or jump to %#x" % addr)
            args = [uc.reg_read(r) & 0xFFFFFFFF for r in
                    (R.UC_MIPS_REG_A0, R.UC_MIPS_REG_A1, R.UC_MIPS_REG_A2, R.UC_MIPS_REG_A3)]
            value = (hook(args) or 0) & 0xFFFFFFFF
            if value & 0x80000000:
                value |= 0xFFFFFFFF00000000
            uc.reg_write(R.UC_MIPS_REG_V0, value)
            uc.reg_write(R.UC_MIPS_REG_PC, uc.reg_read(R.UC_MIPS_REG_RA) & 0xFFFFFFFF)
        except Exception as exc:  # surface hook errors instead of a bare stop
            self.error = exc
            uc.emu_stop()

    def run(self, start, stop, window, count=20_000_000):
        self.window, self.stop = window, stop
        self.uc.emu_start(start, stop, count=count)
        if self.error:
            raise self.error
        pc = self.uc.reg_read(self.R.UC_MIPS_REG_PC) & 0xFFFFFFFF
        if pc != stop:
            raise RuntimeError("stopped at %#x, not %#x" % (pc, stop))
        value = self.uc.reg_read(self.R.UC_MIPS_REG_V0) & 0xFFFFFFFF
        return value - (1 << 32) if value & 0x80000000 else value


_MACHINE = None


def machine():
    global _MACHINE
    if _MACHINE is None:
        _MACHINE = Machine()
    return _MACHINE


class _Files:
    """open/lseek/read/close for both back ends; one file per path."""
    A = (0x916758, 0x916C08, 0x9169B0, 0x916878)
    B = (0x91BA70, 0x91BDC8, 0x91BBB8, 0x91BB38)

    def __init__(self, m, files, lseek_end=None):
        self.m, self.files, self.lseek_end = m, files, lseek_end
        self.fds, self.log = {}, []
        for table in (self.A, self.B):
            for addr, fn in zip(table, (self.open, self.lseek, self.read, self.close)):
                m.hooks[addr] = (lambda a, fn=fn, addr=addr: fn(a, addr in self.B))

    def open(self, a, mass):
        path = self.m.cstr(a[0])
        self.log.append(("open", "B" if mass else "A", path, a[1]))
        if path not in self.files:
            return -2
        fd = 3 + len(self.fds)
        self.fds[fd] = [self.files[path], 0]
        return fd

    def lseek(self, a, mass):
        f = self.fds[a[0]]
        offset = a[1] - (1 << 32) if a[1] & 0x80000000 else a[1]
        if a[2] == 2 and self.lseek_end is not None:
            self.log.append(("lseek", a[0], offset, a[2], self.lseek_end))
            return self.lseek_end  # what the driver reports, e.g. a failure
        f[1] = {0: offset, 1: f[1] + offset, 2: len(f[0]) + offset}[a[2]]
        self.log.append(("lseek", a[0], offset, a[2], f[1]))
        return f[1]

    def read(self, a, mass):
        f = self.fds[a[0]]
        data = f[0][f[1]:f[1] + a[2]]
        f[1] += len(data)
        self.m.uc.mem_write(a[1], bytes(data))
        self.log.append(("read", a[0], a[1], a[2], len(data)))
        return len(data)

    def close(self, a, mass):
        self.log.append(("close", a[0]))
        return 0


def bios_path(scope, backend, game=b"GAME/"):
    """The one path the original opens (no folder suffix: gp+0x381c == 0)."""
    return (b"mass:" if backend else b"pfs1:") + b"/POPS/" + (game if scope == 1 else b"") + b"BIOS.BIN"


def handler(core, scope, backend, data, flags=None, game=b"GAME/", lseek_end=None,
            game_dir_ok=True):
    """FUN_0088019c(scope, game). `data` None means no such file."""
    m = machine()
    m.reset(core, flags)
    m.put(GP + 0x3448, backend)
    m.put(GP + 0x3868, 1)  # POPS folder already inspected (FUN_008d8958 not needed)
    m.uc.mem_write(NAME, game + b"\0")
    files = {} if data is None else {bios_path(scope, backend, game): bytes(data)}
    io = _Files(m, files, lseek_end)
    m.hooks[0x8D7E78] = lambda a: 1 if game_dir_ok else 0      # pfs: game folder check
    m.hooks[0x91BF80] = lambda a: 0 if game_dir_ok else -2     # mass: getstat on it
    R = m.R
    m.uc.reg_write(R.UC_MIPS_REG_A0, scope)
    m.uc.reg_write(R.UC_MIPS_REG_A1, NAME)
    ret = m.run(HANDLER, SENTINEL, (HANDLER, 0x880A24))
    return {"ret": ret, "core": m.core(), "flags": m.flags(), "io": io.log, "prints": m.prints}


def main_gate(scope, flags=None, slots=None):
    """Does the launch function call the handler? Returns its (a0, a1) or None."""
    m = machine()
    m.reset(b"", flags)
    m.put(GP + 0x38B0, 1)  # quiet: no banner
    for off, value in (slots or {}).items():
        m.put(GP + off, value)
    calls = []
    m.hooks[HANDLER] = lambda a: calls.append((a[0], a[1])) or 0
    lo, hi = ((0x876EA8, 0x876FE0) if scope == 1 else (0x876BB4, 0x876CE0))
    m.run(lo, hi, (lo, hi))
    return calls[0] if calls else None


def shell(core, flags=None):
    m = machine()
    m.reset(core, flags)
    m.run(0x878F64, 0x878FC4, (0x878F64, 0x878FC4))
    return m.core()


def region(core, licence, force_pal=0, auto_disabled=0, selector=1, flags=None):
    """The region pass. licence: the four bytes at gp+0x3cb0."""
    if len(licence) != 4:
        raise ValueError("licence must be four bytes")
    m = machine()
    m.reset(core, flags)
    m.put(GP + 0x38B0, 1)
    m.put(GP + 0x38A0, force_pal)
    m.put(GP + 0x3864, auto_disabled)
    m.put(GP + 0x4FA0, selector)
    m.uc.mem_write(GP + 0x3CB0, bytes(licence))
    m.run(0x879034, 0x8795F0, (0x879034, 0x8795F0))
    return m.core()


def mode(core, number, flags=None, quiet=1):
    """FUN_008dc2c4(number): one compatibility mode, as PATCH files, built-in
    entries and the command all reach it. Returns (core, flags, messages);
    quiet=0 lets it print (gp+0x38b0)."""
    m = machine()
    m.reset(core, flags)
    m.put(GP + 0x38B0, quiet)
    m.uc.reg_write(m.R.UC_MIPS_REG_A0, number)
    m.run(0x8DC2C4, SENTINEL, (0x8DC2C4, 0x8DC8E4))
    return m.core(), m.flags(), list(m.prints)


def parser(text, core, flags=None):
    """The original CHEATS.TXT section over `core` with loader flags preset.

    Reuses trace_original_pops_cheats.compile_cheats; its machine is given
    the core and the flags just before it starts and read back when it
    stops (a wrapper around emu_start, no extra hook)."""
    import unicorn
    import trace_original_pops_cheats as T

    state = {}
    original = unicorn.Uc.emu_start

    def emu_start(self, begin, until, *args, **kwargs):
        if begin != T.START:
            return original(self, begin, until, *args, **kwargs)
        self.mem_write(CORE_BASE, bytes(core))
        for name, value in (flags or {}).items():
            self.mem_write(GP + FLAGS[name], struct.pack("<I", value))
        result = original(self, begin, until, *args, **kwargs)
        state["core"] = bytearray(self.mem_read(CORE_BASE, len(core)))
        state["flags"] = {name: struct.unpack("<I", self.mem_read(GP + off, 4))[0]
                          for name, off in FLAGS.items()}
        return result

    unicorn.Uc.emu_start = emu_start
    try:
        T.compile_cheats(text)
    finally:
        unicorn.Uc.emu_start = original
    return state["core"], state["flags"]


def _diff(before, after):
    out, i, n = [], 0, len(before)
    while i < n:
        if before[i] != after[i]:
            j = i
            while j < n and before[j] != after[j]:
                j += 1
            out.append((CORE_BASE + i, j - i))
            i = j
        else:
            i += 1
    return out


def main():
    core = core_image()
    print("core bytes:", hex(len(core)))
    rom = bytes((i * 7 + 3) & 0xFF or 1 for i in range(0x100000))
    for scope in (0, 1):
        for backend in (0, 1):
            for size in (None, 0, 0x7FF8E, 0x7FF8F, 0x7FF90, 0x80000, 0x100000):
                r = handler(core, scope, backend, None if size is None else rom[:size])
                d = _diff(core, r["core"])
                print("scope %d backend %d size %-8s ret %d flags %s changed %s io %s prints %s" % (
                    scope, backend, "absent" if size is None else hex(size), r["ret"],
                    {k: v for k, v in r["flags"].items() if v},
                    [(hex(a), hex(n)) for a, n in d][:4] + (["..."] if len(d) > 4 else []),
                    [e[:2] + tuple(hex(x) if isinstance(x, int) else x for x in e[2:]) for e in r["io"]],
                    [p.strip() for p in r["prints"]]))
    for scope in (0, 1):
        for name in FLAGS:
            r = handler(core, scope, 0, rom[:0x80000], {name: 1})
            print("scope %d preset %-16s ret %d loaded %s main calls %s" % (
                scope, name, r["ret"], any(e[0] == "read" for e in r["io"]),
                main_gate(scope, {name: 1}) is not None))
    for name in [None] + list(FLAGS):
        after = shell(core, {name: 1} if name else None)
        print("shell preset %-16s writes %s" % (name, [(hex(a), n) for a, n in _diff(core, after)]))


if __name__ == "__main__":
    main()
