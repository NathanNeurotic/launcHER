#!/usr/bin/env python3
"""Run POPStarter r13's launch function and record every path it touches.

Needs the external POPStarter MAIN (POPSTARTER_TEST_ELF) and Python's Unicorn
package. Sony's POPS files are only needed by cases that let the original
load a POPS package (POPS_TEST_ELF, with POPS_IOX.PAK beside it when the
case wants the pack). No original bytes are included or written: both files
are read at run time, the same way trace_original_pops_io.py reads them.

What runs: the original's own `main` (0x870b78) from its first instruction,
with argc/argv as given, on an EE memory image holding the unpacked program
at 0x870000 and the packed file's loaded segment at 0x100000 (which carries
the preset block 0x100008..0x10002f). Every instruction of the program's own
code is executed. The statically linked library is not executed: each
library entry the program calls is replaced by a model (LIBRARY below), and
the models keep a small file system, mount table and heap. The R5900-only
instructions the program's own code uses (lq, sq, pcpyld, por, three-operand
mult/multu, and the float-register saves of two variadic wrappers) are
modelled in hooks, since Unicorn's MIPS64 core lacks them.

What is recorded, in order, each with the address of the calling `jal`:
open, close-less reads are not listed; mount, umount, getstat, chstat,
mkdir, devctl, write (sizes only), module loads and starts, IOP resets, the
physical-disc library calls, and how the run ended (fatal handler with its
call site, Exit, or the jump into POPS).

This is bounded execution of one function with a modelled library and
synthetic files. It is not an EE boot, an IOP, a storage device or a console
test: it shows which paths the original asks for and in which order, given
the answers the model returns.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_original_pops_io import decode_main  # noqa: E402

BASE = 0x870000
GP = 0x9B68F0
BSS = (0x9B9D00, 0x9CCAC0)
APP_TEXT = (0x870000, 0x914930)     # the program's own code
LIB_TEXT = (0x914930, 0x91F000)     # statically linked library, never run
MAIN = 0x870B78
MAIN_END = 0x87C218
FATAL = 0x8709F8
LAUNCHING = 0x879E5C                # first instruction of "LAUNCHING POPS"
POPS_JUMP = 0x87C1D8                # the one `j` in main: into POPS
LOADER_SEGMENT = 0x100000           # packed file offset 0x400 loads here
RAM = 0x02000000
# The original uses 0x01f0db20..0x01ff3190 as scratch and runs a copied
# routine at 0x01ff2bdc, so the stack has to sit where crt0 puts it: at the
# top of the 32 MB (SetupThread with stack -1, size 0x20000).
STACK_TOP = 0x01FFED00
ARGV = 0x01FFF000
RETURN = 0x01FFFF80
HEAP = 0x9CCAC0                     # crt0 gives the heap the end of .bss

# gp-relative state words reported with every trace.
STATE = {
    "launch_type": 0x3414,          # 0..3
    "mass_mode": 0x3448,            # 1 on XX. and SB.
    "smb_mode": 0x3888,             # 3 on SB.
    "physical_disc": 0x3410,
    "abort": 0x38DC,
    "folder_checked": 0x3868,
    "game_folder_missing": 0x3460,
    "suffix_in_use": 0x381C,
    "suffix_char": 0x38B8,
    "quiet": 0x38B0,
}

# The original copies its LZMA routine (0x5a4 bytes from 0x99de60) to the
# top of RAM and calls it there to unpack a POPS pack: at 0x01ff2c84 for
# POPS_IOX.PAK (call site 0x87d350) and 0x01ff2c88 for POPS.PAK (0x87d8a0).
# Run instruction by instruction it needs a hook per decoded bit, so the
# routine is modelled with Python's lzma, from the source and destination
# the copied code holds in its first two lui/ori pairs.
UNPACKERS = (0x01FF2C84, 0x01FF2C88)

# Two small delay loops in the program's own code (busy waits on a counter).
# They are skipped, not run: they touch no state but their own counter.
DELAYS = {0x870930: "delay_870930", 0x87098C: "delay_87098c"}

# Thin wrappers in the program's own code around the library's fio calls.
# When a library call comes from inside one, the wrapper's caller is the
# meaningful call site.
WRAPPERS = ((0x87C390, 0x87C3F0), (0x87C3F0, 0x87C420), (0x87C420, 0x87C460),
            (0x87C460, 0x87C4A0), (0x8D6C94, 0x8D6CF4), (0x8D6CF4, 0x8D6D24),
            (0x8D6D24, 0x8D6D64), (0x8D6D64, 0x8D6DA4))

ENOENT, EIO, EEXIST = 2, 5, 17


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _s32(value):
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


def _sx(value):
    value &= 0xFFFFFFFF
    return value | 0xFFFFFFFF00000000 if value & 0x80000000 else value


class Stop(Exception):
    """Raised inside a model to end the run with a reason."""

    def __init__(self, kind, **info):
        super().__init__(kind)
        self.kind = kind
        self.info = info


class Files:
    """The modelled storage: plain files, directories, HDD partitions.

    Names are canonical device paths:
        mass:/POPS/GAME.VCD
        mc0:/POPSTARTER/usbd.irx
        hdd0:__common:pfs:/POPS/POPS.ELF     (a file inside a partition)
    A pfsN: path is resolved through the mount table first. Comparison is
    exact, except on mass: where it ignores case (FAT). A value is bytes, or
    an int for a file of that many zero bytes (kept sparse).
    """

    def __init__(self, files=None, partitions=(), directories=()):
        self.files = {}
        self.dirs = set()
        self.partitions = set(partitions)
        self.mounts = {}
        self.written = {}
        for name, data in (files or {}).items():
            self.add(name, data)
        for name in directories:
            self._add_dir(self._key(name.rstrip("/")))

    @staticmethod
    def _key(name):
        device = name.split(":", 1)[0].lower()
        return name.upper() if device.startswith("mass") else name

    def _add_dir(self, key):
        while "/" in key:
            self.dirs.add(key)
            key = key.rsplit("/", 1)[0]

    def add(self, name, data):
        key = self._key(name)
        self.files[key] = data
        if name.startswith("hdd0:"):
            self.partitions.add(name.split(":pfs:", 1)[0])
        self._add_dir(key.rsplit("/", 1)[0])

    def resolve(self, path):
        """Path as the program gave it -> canonical name, or None."""
        device, _, rest = path.partition(":")
        if not _:
            return None
        rest = rest.replace("\\", "/")
        while "//" in rest:
            rest = rest.replace("//", "/")
        if not rest.startswith("/"):
            rest = "/" + rest
        if device.lower().startswith("pfs"):
            mounted = self.mounts.get(device.lower() + ":")
            if mounted is None:
                return None
            return "%s:pfs:%s" % (mounted, rest)
        if device.lower() == "mass0":
            device = "mass"             # usbhdfsd: mass: is unit 0
        return "%s:%s" % (device, rest)

    def lookup(self, path):
        name = self.resolve(path)
        if name is None:
            return None, None
        key = self._key(name)
        if key in self.files:
            return name, self.files[key]
        return name, None

    def is_dir(self, path):
        name = self.resolve(path)
        if name is None:
            return False
        key = self._key(name).rstrip("/")
        return key in self.dirs or key.endswith(":pfs:") or key.endswith(":")

    @staticmethod
    def size(data):
        return data if isinstance(data, int) else len(data)

    @staticmethod
    def read(data, offset, count):
        if isinstance(data, int):
            return bytes(max(0, min(count, data - offset)))
        return bytes(data[offset:offset + count])


def _printf(fmt, args):
    """Small printf for recorded messages (text only, never fed back)."""
    out, i, n = [], 0, 0
    while i < len(fmt):
        c = fmt[i]
        if c != "%":
            out.append(c)
            i += 1
            continue
        j = i + 1
        while j < len(fmt) and fmt[j] in "-+ #0123456789.l":
            j += 1
        if j >= len(fmt):
            break
        conv = fmt[j]
        spec = fmt[i:j].replace("l", "")
        if conv == "%":
            out.append("%")
        else:
            value = args(n)
            n += 1
            if conv == "s":
                out.append((spec + "s") % value("s"))
            elif conv in "di":
                out.append((spec + "d") % _s32(value("i")))
            elif conv in "uxXc":
                v = value("i") & 0xFFFFFFFF
                out.append(chr(v & 0xFF) if conv == "c" else (spec + conv) % v)
            else:
                out.append(fmt[i:j + 1])
        i = j + 1
    return "".join(out)


class Original:
    """One run of the original's main()."""

    def __init__(self, image, loader_segment, argv, files, *, preset=None,
                 fd_base=3, results=None, detail=False, watch=()):
        from unicorn import (Uc, UC_ARCH_MIPS, UC_MODE_MIPS64,
                             UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE)
        from unicorn import mips_const as R

        self.R = R
        self.files = files
        self.events = []
        self.prints = []
        self.fds = {}
        self.next_fd = fd_base
        self.heap = HEAP
        self.results = dict(results or {})
        self.detail = detail
        self.watch = tuple(watch)
        self.reached = set()
        self.modules = 0
        self.end = None
        self.upper = [0] * 32
        self.wrapper_site = None
        uc = self.uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
        try:
            uc.ctl_set_cpu_model(R.UC_CPU_MIPS64_5KF)
        except Exception:
            pass
        uc.mem_map(0, RAM)
        uc.mem_map(0x70000000, 0x4000)      # scratchpad, cleared before the jump
        uc.mem_write(LOADER_SEGMENT, bytes(loader_segment))
        uc.mem_write(BASE, bytes(image))
        uc.mem_write(BSS[0], b"\0" * (BSS[1] - BSS[0]))
        for offset, value in (preset or {}).items():
            require(0x100008 <= offset <= 0x10002F, "not a preset byte")
            uc.mem_write(offset, bytes([value & 0xFF]))
        self.regs = [getattr(R, "UC_MIPS_REG_%d" % i) for i in range(32)]

        # argv
        cursor = ARGV + 0x100
        pointers = []
        for text in argv:
            raw = text.encode("latin-1") + b"\0"
            uc.mem_write(cursor, raw)
            pointers.append(cursor)
            cursor += (len(raw) + 15) & ~15
        uc.mem_write(ARGV, struct.pack("<%dI" % (len(pointers) + 1), *pointers, 0))
        self.argc = len(argv)

        # One dispatcher, registered per address, so only those addresses
        # leave the translated code.
        self.table = {}
        for address, name in LIBRARY.items():
            self.table[address] = getattr(self, "lib_" + name)
        for address, name in DELAYS.items():
            self.table[address] = self.lib_delay
        for address in UNPACKERS:
            self.table[address] = self.lib_unpack
        self.table[FATAL] = self.at_fatal
        self.table[RETURN] = self.at_return
        self.table[POPS_JUMP] = self.at_pops_jump
        self.ee_ops = {}
        for address in range(APP_TEXT[0], APP_TEXT[1], 4):
            word, = struct.unpack_from("<I", image, address - BASE)
            op, fn, rd = word >> 26, word & 63, (word >> 11) & 31
            if (op in (0x1C, 0x1E, 0x1F, 0x31, 0x39) or word == 0xC or
                    (op == 0 and fn in (0x18, 0x19) and rd)):
                previous, = struct.unpack_from("<I", image, address - 4 - BASE)
                require(not self._is_branch(previous),
                        "R5900-only instruction in a delay slot at %#x" % address)
                self.ee_ops[address] = word
        self.failure = None

        def dispatch(u, address, size, _):
            try:
                handler = self.table.get(address)
                if handler is not None:
                    handler(address)
                elif address in self.ee_ops:
                    self.ee_op(address, self.ee_ops[address])
                elif LIB_TEXT[0] + 0x68 <= address < LIB_TEXT[1]:
                    raise RuntimeError("unmodelled library code at %#x (ra %#x)"
                                       % (address, self.reg(31)))
            except Stop as stop:
                self.end = dict(kind=stop.kind, **stop.info)
                u.emu_stop()
            except Exception as exc:  # surface model errors, not a bare stop
                self.failure = exc
                u.emu_stop()

        for address in list(self.table) + list(self.ee_ops):
            if not LIB_TEXT[0] + 0x68 <= address < LIB_TEXT[1]:
                uc.hook_add(UC_HOOK_CODE, dispatch, None, address, address)
        # Any other library address means a call this tool does not model.
        uc.hook_add(UC_HOOK_CODE, dispatch, None, LIB_TEXT[0] + 0x68, LIB_TEXT[1] - 1)

        uc.reg_write(R.UC_MIPS_REG_GP, GP)
        uc.reg_write(R.UC_MIPS_REG_SP, STACK_TOP)
        uc.reg_write(R.UC_MIPS_REG_FP, STACK_TOP)
        uc.reg_write(R.UC_MIPS_REG_RA, RETURN)
        uc.reg_write(R.UC_MIPS_REG_A0, self.argc)
        uc.reg_write(R.UC_MIPS_REG_A1, ARGV)

    # ---- machine helpers -------------------------------------------------

    @staticmethod
    def _is_branch(word):
        op, fn = word >> 26, word & 63
        return (op in (1, 2, 3, 4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17) or
                (op == 0 and fn in (8, 9)))

    def reg(self, index):
        return self.uc.reg_read(self.regs[index]) & 0xFFFFFFFF

    def reg64(self, index):
        return self.uc.reg_read(self.regs[index]) & 0xFFFFFFFFFFFFFFFF

    def arg(self, index):
        """EE ABI: eight integer argument registers a0..a3, t0..t3."""
        return self.reg(4 + index)

    def word(self, address):
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def put(self, address, value):
        self.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    def gp(self, offset):
        return self.word(GP + offset)

    def text(self, address, limit=1024):
        raw = bytes(self.uc.mem_read(address, min(limit, RAM - address)))
        end = raw.find(b"\0")
        require(end >= 0, "unterminated string at %#x" % address)
        return raw[:end].decode("latin-1")

    def ret(self, value=0):
        R = self.R
        self.uc.reg_write(R.UC_MIPS_REG_V0, _sx(value))
        self.uc.reg_write(R.UC_MIPS_REG_PC, self.reg(31))

    def site(self):
        """Address of the `jal` that made this library call."""
        site = self.reg(31) - 8
        for start, end in WRAPPERS:
            if start <= site < end:
                # Inside a wrapper: its own caller is saved in its frame.
                for at in range(start, start + 0x20, 4):
                    word = self.word(at)
                    if word >> 16 == 0xFFBF:  # sd ra, X(sp)
                        return (self.word(self.reg(29) + (word & 0xFFFF)) - 8) & 0xFFFFFFFF
        return site

    def log(self, op, **fields):
        event = {"op": op, "site": self.site()}
        event.update(fields)
        self.events.append(event)
        return event

    def scripted(self, op, key, default):
        """A result forced by the case: results[(op, key)] or results[op]."""
        for probe in ((op, key), op):
            if probe in self.results:
                value = self.results[probe]
                if isinstance(value, list):
                    return value.pop(0) if len(value) > 1 else value[0]
                return value
        return default

    # ---- R5900-only instructions in the program's own code ---------------

    def ee_op(self, address, word):
        R = self.R
        uc = self.uc
        op = word >> 26
        rs, rt, rd = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
        imm = word & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        fn, sa = word & 63, (word >> 6) & 31
        if word == 0xC:
            return self.syscall(address)
        if op == 0:  # mult/multu with a destination register
            a, b = self.reg(rs), self.reg(rt)
            if fn == 0x18:
                a, b = _s32(a), _s32(b)
            product = (a * b) & 0xFFFFFFFFFFFFFFFF
            uc.reg_write(R.UC_MIPS_REG_LO, _sx(product))
            uc.reg_write(R.UC_MIPS_REG_HI, _sx(product >> 32))
            uc.reg_write(self.regs[rd], _sx(product))
        elif op == 0x1C and fn == 0x09 and sa == 0x0E:  # pcpyld
            low, high = self.reg64(rt), self.reg64(rs)
            if rd:
                uc.reg_write(self.regs[rd], low)
                self.upper[rd] = high
        elif op == 0x1C and fn == 0x29 and sa == 0x12:  # por
            if rd:
                uc.reg_write(self.regs[rd], self.reg64(rs) | self.reg64(rt))
                self.upper[rd] = self.upper[rs] | self.upper[rt]
        elif op == 0x1C:
            raise RuntimeError("unmodelled MMI %#010x at %#x" % (word, address))
        elif op == 0x1F:  # sq
            at = (self.reg(rs) + simm) & 0xFFFFFFF0
            uc.mem_write(at, struct.pack("<QQ", self.reg64(rt) if rt else 0,
                                         self.upper[rt] if rt else 0))
        elif op == 0x1E:  # lq
            at = (self.reg(rs) + simm) & 0xFFFFFFF0
            low, high = struct.unpack("<QQ", uc.mem_read(at, 16))
            if rt:
                uc.reg_write(self.regs[rt], low)
                self.upper[rt] = high
        elif op in (0x31, 0x39):  # lwc1/swc1: float saves of variadic wrappers
            pass
        uc.reg_write(R.UC_MIPS_REG_PC, address + 4)

    def syscall(self, address):
        number = _s32(self.reg(3))
        if number == 4:
            self.events.append({"op": "Exit", "site": address})
            raise Stop("exit", site=address)
        self.events.append({"op": "syscall", "site": address, "number": number})
        self.uc.reg_write(self.R.UC_MIPS_REG_V0, 0)
        self.uc.reg_write(self.R.UC_MIPS_REG_PC, address + 4)

    # ---- how a run ends --------------------------------------------------

    def at_fatal(self, address):
        site = self.reg(31) - 8
        self.events.append({"op": "fatal", "site": site})
        raise Stop("fatal", site=site)

    def at_return(self, address):
        raise Stop("returned")

    def at_pops_jump(self, address):
        self.events.append({"op": "jump_to_pops", "site": address})
        raise Stop("pops", site=address)

    # ---- library models: C library ---------------------------------------

    def lib_delay(self, address):
        self.ret(0)

    def lib_unpack(self, address):
        import lzma

        def immediate(at):
            high, low = self.word(at), self.word(at + 4)
            require(high >> 26 == 0x0F and low >> 26 == 0x0D, "unexpected unpacker head")
            return ((high & 0xFFFF) << 16) | (low & 0xFFFF)
        source, target = immediate(address), immediate(address + 8)
        length, limit = self.word(source - 8), self.word(source - 8)
        require(0 < length <= 0x400000, "implausible unpacked length")
        stream = (b"\0" + bytes(self.uc.mem_read(source - 4, 4))[::-1] +
                  bytes(self.uc.mem_read(source, min(0x100000, RAM - source))))
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[{
            "id": lzma.FILTER_LZMA1, "dict_size": 8 << 20, "lc": 3, "lp": 0, "pb": 2}])
        try:
            data = decoder.decompress(stream, max_length=limit)
        except lzma.LZMAError:
            data = b""
        self.uc.mem_write(target, data)
        self.events.append({"op": "unpack", "site": self.reg(31) - 8, "source": source,
                            "target": target, "length": length, "produced": len(data)})
        # The original replaces the routine's `jr ra` (0x140 bytes after its
        # entry) with a `j` to its own register-restore sequence.
        leave = self.word(address + 0x140)
        require(leave >> 26 == 2 or leave == 0x03E00008, "unexpected unpacker exit")
        self.uc.reg_write(self.R.UC_MIPS_REG_PC,
                          (leave & 0x03FFFFFF) << 2 if leave >> 26 == 2 else self.reg(31))

    def lib_memcpy(self, address):
        dst, src, count = self.arg(0), self.arg(1), self.arg(2)
        if count:
            self.uc.mem_write(dst, bytes(self.uc.mem_read(src, count)))
        self.ret(dst)

    def lib_memset(self, address):
        dst, value, count = self.arg(0), self.arg(1), self.arg(2)
        if count:
            self.uc.mem_write(dst, bytes([value & 0xFF]) * count)
        self.ret(dst)

    def lib_strlen(self, address):
        self.ret(len(self.text(self.arg(0), 0x10000)))

    def lib_strcpy(self, address):
        dst = self.arg(0)
        self.uc.mem_write(dst, self.text(self.arg(1), 0x10000).encode("latin-1") + b"\0")
        self.ret(dst)

    def lib_strncpy(self, address):
        dst, count = self.arg(0), self.arg(2)
        raw = self.text(self.arg(1), 0x10000).encode("latin-1")[:count]
        self.uc.mem_write(dst, raw + b"\0" * (count - len(raw)))
        self.ret(dst)

    def lib_strncmp(self, address):
        count = self.arg(2)
        a = bytes(self.uc.mem_read(self.arg(0), count))
        b = bytes(self.uc.mem_read(self.arg(1), count))
        for x, y in zip(a, b):
            if x != y:
                return self.ret(x - y)
            if not x:
                break
        self.ret(0)

    def lib_malloc(self, address):
        size = (self.arg(0) + 15) & ~15
        at = (self.heap + 16 + 15) & ~15
        require(at + size < 0x01E00000, "modelled heap exhausted")
        self.heap = at + size
        self.ret(at)

    def _format(self, fmt_index):
        fmt = self.text(self.arg(fmt_index), 4096)

        def args(n):
            index = fmt_index + 1 + n

            def value(kind):
                raw = self.arg(index) if index < 8 else 0
                return self.text(raw, 512) if kind == "s" else raw
            return value
        return _printf(fmt, args)

    def lib_scr_printf(self, address):
        self.prints.append({"site": self.site(), "text": self._format(0)})
        self.ret(0)

    def lib_snprintf(self, address):
        text = self._format(2).encode("latin-1")[:max(0, self.arg(1) - 1)]
        self.uc.mem_write(self.arg(0), text + b"\0")
        self.ret(len(text))

    def lib_nop(self, address):
        self.ret(0)

    def lib_one(self, address):
        self.ret(1)

    def lib_minus_one(self, address):
        self.ret(-1)

    lib_SifDmaStat = lib_minus_one   # negative: the transfer has completed

    def lib_named(self, address):
        self.log(LIBRARY[address])
        self.ret(0)

    lib_scr_clear = lib_init_scr = lib_nop
    lib_SifInitRpc = lib_SifExitRpc = lib_nop
    lib_SifLoadFileInit = lib_SifLoadFileExit = lib_nop
    lib_SifInitIopHeap = lib_SifExitIopHeap = lib_nop
    lib_fioInit = lib_fioExit = lib_nop
    lib_fileXioInit = lib_fileXioExit = lib_nop
    lib_FlushCache = lib_SifSetReg = lib_nop
    lib_SifSetDma = lib_one          # a transfer id
    lib_SifInitCmd = lib_nop
    lib_SifIopSync = lib_one
    lib_sbv_patch_enable_lmb = lib_sbv_patch_disable_prefix_check = lib_named
    lib_fileXioStop = lib_named
    lib_SetVCommonHandler = lib_named
    lib_ResetEE = lib_SleepThread = lib_named
    lib_smem_read = lib_nop
    lib_smod_get_next_mod = lib_nop   # "no further module": the list is empty

    def lib_ExecPS2(self, address):
        self.log("ExecPS2", entry=self.arg(0), gp=self.arg(1), argc=self.arg(2))
        raise Stop("exec", site=self.site())

    def lib_ExecOSD(self, address):
        self.log("ExecOSD")
        raise Stop("osd", site=self.site())

    # ---- library models: SIF, modules ------------------------------------

    def lib_SifIopReset(self, address):
        self.log("SifIopReset", arg=self.text(self.arg(0)) if self.arg(0) else None)
        self.ret(1)

    def lib_SifLoadModule(self, address):
        path = self.text(self.arg(0))
        result = self.scripted("SifLoadModule", path, None)
        if result is None:
            self.modules += 1
            result = self.modules
        self.log("SifLoadModule", path=path, arg_len=self.arg(1), result=result)
        self.ret(result)

    def lib_SifLoadModuleBuffer(self, address):
        self.modules += 1
        self.log("SifLoadModuleBuffer", buffer=self.arg(0), result=self.modules)
        self.ret(self.modules)

    def lib_SifCallRpc(self, address):
        self.log("SifCallRpc", client=self.arg(0), function=self.arg(1),
                 send_size=self.arg(4))
        self.ret(0)

    def lib_SifAllocIopHeap(self, address):
        self.ret(0x00100000)

    def lib_SifExecModuleBuffer(self, address):
        buffer, size, arg_len, args, out = (self.arg(i) for i in range(5))
        result = self.scripted("SifExecModuleBuffer", buffer, None)
        if result is None:
            self.modules += 1
            result = self.modules
        argument = ""
        if arg_len and args:
            argument = bytes(self.uc.mem_read(args, min(arg_len, 256))).decode("latin-1")
        if out:
            self.put(out, self.scripted("module_start", buffer, 0))
        self.log("SifExecModuleBuffer", buffer=buffer, size=size, arg_len=arg_len,
                 args=argument, result=result)
        self.ret(result)

    # ---- library models: files -------------------------------------------

    def _open(self, api, path, flags):
        name, data = self.files.lookup(path)
        forced = self.scripted("open", path, None)
        if forced is not None:
            result = forced
        elif data is None and not (flags & 0x200):
            result = -ENOENT
        elif name is None:
            result = -ENOENT
        else:
            if data is None or flags & 0x400:
                data = bytearray()
                self.files.add(name, data)
                self.files.written[name] = data
            result = self.next_fd
            self.next_fd += 1
            self.fds[result] = [name, data, 0]
        self.log(api, path=path, flags=flags, resolved=name, result=result)
        return result

    def lib_fileXioOpen(self, address):
        self.ret(self._open("fileXioOpen", self.text(self.arg(0)), self.arg(1)))

    def lib_fioOpen(self, address):
        self.ret(self._open("fioOpen", self.text(self.arg(0)), self.arg(1)))

    def _close(self, address):
        fd = _s32(self.arg(0))
        known = self.fds.pop(fd, None)
        if self.detail:
            self.log(LIBRARY[address], path=known[0] if known else None, fd=fd)
        self.ret(0 if known else -9)

    def _read(self, address):
        fd, buffer, count = _s32(self.arg(0)), self.arg(1), self.arg(2)
        entry = self.fds.get(fd)
        if entry is None:
            return self.ret(-9)
        chunk = Files.read(entry[1], entry[2], count)
        if chunk:
            self.uc.mem_write(buffer, chunk)
        if self.detail:
            self.log(LIBRARY[address], path=entry[0], offset=entry[2], size=count,
                     buffer=buffer, result=len(chunk))
        entry[2] += len(chunk)
        self.ret(len(chunk))

    def _write(self, address):
        fd, buffer, count = _s32(self.arg(0)), self.arg(1), self.arg(2)
        entry = self.fds.get(fd)
        if entry is None:
            return self.ret(-9)
        data = entry[1]
        if not isinstance(data, bytearray):
            data = bytearray(Files.read(data, 0, Files.size(data)))
            entry[1] = data
            self.files.add(entry[0], data)
            self.files.written[entry[0]] = data
        chunk = bytes(self.uc.mem_read(buffer, count))
        data[entry[2]:entry[2] + count] = chunk
        entry[2] += count
        self.log(LIBRARY[address], path=entry[0], offset=entry[2] - count, size=count)
        self.ret(count)

    def _lseek(self, address):
        fd, offset, whence = _s32(self.arg(0)), _s32(self.arg(1)), self.arg(2)
        entry = self.fds.get(fd)
        if entry is None:
            return self.ret(-9)
        size = Files.size(entry[1])
        entry[2] = (offset, entry[2] + offset, size + offset)[whence]
        if self.detail:
            self.log(LIBRARY[address], path=entry[0], offset=offset, whence=whence,
                     result=entry[2])
        self.ret(entry[2])

    lib_fileXioClose = lib_fioClose = _close
    lib_fileXioRead = lib_fioRead = _read
    lib_fileXioWrite = lib_fioWrite = _write
    lib_fileXioLseek = lib_fioLseek = _lseek

    def _stat(self, api, path, buffer, wide):
        name, data = self.files.lookup(path)
        forced = self.scripted("getstat", path, None)
        if forced is not None:
            result = forced
        elif data is not None:
            size = Files.size(data)
            self.uc.mem_write(buffer, struct.pack("<3I", 0x2000 | 0x1FF, 0, size & 0xFFFFFFFF) +
                              b"\0" * 24 + struct.pack("<I", size >> 32) +
                              (b"\0" * 24 if wide else b""))
            result = 0
        elif self.files.is_dir(path):
            self.uc.mem_write(buffer, struct.pack("<3I", 0x1000 | 0x1FF, 0, 0) +
                              b"\0" * 28 + (b"\0" * 24 if wide else b""))
            result = 0
        else:
            result = -ENOENT
        self.log(api, path=path, resolved=name, result=result)
        self.ret(result)

    def lib_fileXioGetStat(self, address):
        self._stat("fileXioGetStat", self.text(self.arg(0)), self.arg(1), True)

    def lib_fioGetstat(self, address):
        self._stat("fioGetstat", self.text(self.arg(0)), self.arg(1), False)

    def lib_fileXioChStat(self, address):
        path = self.text(self.arg(0))
        self.log("fileXioChStat", path=path, resolved=self.files.resolve(path),
                 mask=self.arg(2), result=0)
        self.ret(0)

    def _mkdir(self, api, path):
        name = self.files.resolve(path)
        forced = self.scripted("mkdir", path, None)
        if forced is not None:
            result = forced
        elif name is None:
            result = -ENOENT
        elif self.files.is_dir(path):
            result = -EEXIST
        else:
            self.files._add_dir(self.files._key(name).rstrip("/"))
            result = 0
        self.log(api, path=path, resolved=name, result=result)
        self.ret(result)

    def lib_fileXioMkdir(self, address):
        self._mkdir("fileXioMkdir", self.text(self.arg(0)))

    def lib_fioMkdir(self, address):
        self._mkdir("fioMkdir", self.text(self.arg(0)))

    def lib_fileXioMount(self, address):
        point, device = self.text(self.arg(0)), self.text(self.arg(1))
        forced = self.scripted("mount", device, None)
        if forced is not None:
            result = forced
        elif device in self.files.partitions:
            self.files.mounts[point.lower()] = device
            result = 0
        else:
            result = -ENOENT
        self.log("fileXioMount", mountpoint=point, device=device,
                 flag=self.arg(2), result=result)
        self.ret(result)

    def lib_fileXioUmount(self, address):
        point = self.text(self.arg(0))
        result = 0 if self.files.mounts.pop(point.lower(), None) else -ENOENT
        self.log("fileXioUmount", mountpoint=point, result=result)
        self.ret(result)

    def lib_fileXioDevctl(self, address):
        name, command = self.text(self.arg(0)), self.arg(1)
        result = self.scripted("devctl", (name, command), 0)
        size = min(self.arg(3), 256)
        raw = bytes(self.uc.mem_read(self.arg(2), size)) if size and self.arg(2) else b""
        self.log("fileXioDevctl", name=name, command=command, arg_len=self.arg(3),
                 arg=raw.split(b"\0", 1)[0].decode("latin-1"), result=result)
        self.ret(result)

    # ---- library models: physical disc -----------------------------------

    def _cd(self, address):
        name = LIBRARY[address]
        result = self.scripted(name, None, {"sceCdInit": 1, "sceCdDiskReady": 2,
                                           "sceCdRead": 0, "sceCdSync": 0}.get(name, 0))
        self.log(name, args=[self.arg(0), self.arg(1)], result=result)
        self.ret(result)

    lib_sceCdInit = lib_sceCdDiskReady = lib_sceCdRead = lib_sceCdSync = _cd
    lib_sceCdGetDiskType = lib_sceCdStatus = _cd

    # ---- running ---------------------------------------------------------

    def run(self, stop_at=None, limit=400_000_000):
        if self.watch:
            from unicorn import UC_HOOK_BLOCK

            def block(u, address, size, _):
                self.reached.add(address)
            for low, high in self.watch:
                self.uc.hook_add(UC_HOOK_BLOCK, block, None, low, high - 1)
        if stop_at is not None:
            self.table[stop_at] = self.at_stop
            from unicorn import UC_HOOK_CODE
            self.uc.hook_add(UC_HOOK_CODE, self._dispatch_stop, None, stop_at, stop_at)
        try:
            self.uc.emu_start(MAIN, 0xFFFFFFFF, count=limit)
        except Exception as exc:
            if self.failure is None and self.end is None:
                self.failure = RuntimeError("%s at pc %#x (ra %#x)" % (
                    exc, self.uc.reg_read(self.R.UC_MIPS_REG_PC) & 0xFFFFFFFF, self.reg(31)))
        if self.failure is not None:
            self.end = {"kind": "error"}
            self.failure.report = self.report()
            raise self.failure
        if self.end is None:
            self.end = {"kind": "limit",
                        "site": self.uc.reg_read(self.R.UC_MIPS_REG_PC) & 0xFFFFFFFF}
        return self.report()

    def _dispatch_stop(self, u, address, size, _):
        self.end = {"kind": "stopped", "site": address}
        u.emu_stop()

    def at_stop(self, address):
        raise Stop("stopped", site=address)

    def report(self):
        state = {name: self.gp(offset) for name, offset in STATE.items()}
        return {"end": self.end, "state": state, "events": self.events,
                "prints": self.prints, "reached": sorted(self.reached),
                "written": {name: len(data) for name, data in self.files.written.items()}}


# Library entry -> model. Every library address the program's own code calls
# (74 targets, found by scanning every `jal` in 0x870000..0x914930) is here
# or is one of the two byte/word store helpers below, which are run as is.
LIBRARY = {
    0x914998: "smem_read",                  # copies from IOP RAM at 0xbc000000+a0
    0x914AA8: "smod_get_next_mod",          # IOP module list walk; modelled as empty
    0x914C60: "sbv_patch_enable_lmb",
    0x914E90: "sbv_patch_disable_prefix_check",
    0x9154D8: "init_scr", 0x915708: "scr_printf", 0x915988: "scr_clear",
    0x915A28: "fileXioInit", 0x915BB0: "fileXioExit", 0x915C20: "fileXioStop",
    0x915E50: "fileXioMount", 0x915F50: "fileXioUmount", 0x916120: "fileXioMkdir",
    0x916758: "fileXioOpen", 0x916878: "fileXioClose", 0x9169B0: "fileXioRead",
    0x916AC8: "fileXioWrite", 0x916C08: "fileXioLseek", 0x916E10: "fileXioChStat",
    0x916F20: "fileXioGetStat", 0x9174F8: "fileXioDevctl",
    0x917B18: "sceCdInit", 0x917CC0: "sceCdDiskReady", 0x917F80: "sceCdRead",
    0x9181C0: "sceCdSync", 0x9183D8: "sceCdGetDiskType", 0x918478: "sceCdStatus",
    0x918808: "memcpy", 0x9188B8: "memset", 0x918978: "strncmp",
    0x918B30: "strcpy", 0x918C48: "strncpy", 0x918E08: "strlen",
    0x918F80: "snprintf", 0x9190C8: "malloc",
    0x91AA70: "ResetEE", 0x91AA90: "ExecPS2", 0x91AAA0: "SetVCommonHandler",
    0x91AAF0: "SleepThread", 0x91AB70: "FlushCache", 0x91AB90: "SifDmaStat",
    0x91ABA0: "SifSetDma", 0x91ABB0: "SifSetReg", 0x91ABC0: "ExecOSD",
    0x91ACB0: "SifInitCmd", 0x91B0A8: "SifCallRpc",
    0x91B658: "SifInitRpc", 0x91B7C0: "SifExitRpc",
    0x91B908: "fioInit", 0x91BA18: "fioExit", 0x91BA70: "fioOpen",
    0x91BB38: "fioClose", 0x91BBB8: "fioRead", 0x91BCB8: "fioWrite",
    0x91BDC8: "fioLseek", 0x91BE68: "fioMkdir", 0x91BF80: "fioGetstat",
    0x91C0D0: "SifLoadFileInit", 0x91C1D0: "SifLoadFileExit",
    0x91C200: "SifLoadModule", 0x91C228: "SifLoadModuleBuffer",
    0x91C248: "SifExecModuleBuffer", 0x91C328: "SifInitIopHeap",
    0x91C430: "SifExitIopHeap", 0x91C440: "SifAllocIopHeap",
    0x91C528: "SifIopReset", 0x91C660: "SifIopSync",
}
# 0x914930 (store byte) and 0x914964 (store word) are plain leaf functions in
# the library's first 0x68 bytes; they are executed, not modelled.


_IMAGE = None


def _inputs():
    global _IMAGE
    if _IMAGE is None:
        packed = Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes()
        image = decode_main(packed)
        size, = struct.unpack_from("<I", packed, 0x34 + 16)
        offset, address = struct.unpack_from("<II", packed, 0x34 + 4)
        require(offset == 0x400 and address == LOADER_SEGMENT, "unexpected packed layout")
        _IMAGE = (image, packed[offset:offset + size])
    return _IMAGE


def trace(argv, files=None, *, partitions=(), directories=(), preset=None,
          results=None, stop_at=None, limit=400_000_000, watch=()):
    """Run the original's main() once and return the report.

    watch: (low, high) address ranges; the report's "reached" lists the
    basic-block starts inside them that were executed.
    """
    image, loader = _inputs()
    store = files if isinstance(files, Files) else Files(files, partitions, directories)
    run = Original(image, loader, list(argv), store, preset=preset, results=results,
                   watch=watch)
    return run.run(stop_at=stop_at, limit=limit)


# ---------------------------------------------------------------------------
# Readable form of a report
# ---------------------------------------------------------------------------

# Events that carry no path and say nothing about where files are looked for.
_SILENT = {"sbv_patch_enable_lmb", "sbv_patch_disable_prefix_check",
           "SetVCommonHandler", "ResetEE", "SleepThread", "syscall",
           "SifCallRpc", "fileXioStop"}
_LOOP_DIGIT = re.compile(r"(?:(?<=POPS)\d(?=/|$)|(?<=_)\d(?=\.(?:BIN|IRX)$))")


def _line(event):
    """One event -> (subject, result text) or None when it is not listed."""
    op = event["op"]
    if op in _SILENT:
        return None
    result = event.get("result")
    if op in ("fioOpen", "fileXioOpen"):
        subject = event["path"] + (" [create]" if event["flags"] & 0x200 else "")
        return subject, "ok" if result >= 0 else str(result)
    if op in ("fioGetstat", "fileXioGetStat", "fileXioChStat", "fioMkdir", "fileXioMkdir"):
        return event["path"], str(result)
    if op == "fileXioMount":
        return "%s = %s" % (event["mountpoint"], event["device"]), str(result)
    if op == "fileXioUmount":
        return event["mountpoint"], str(result)
    if op == "fileXioDevctl":
        text = " %r" % event["arg"] if event["arg"] else ""
        return "%s %#x%s" % (event["name"], event["command"], text), str(result)
    if op in ("fioWrite", "fileXioWrite"):
        return event["path"], "%#x bytes" % event["size"]
    if op == "SifIopReset":
        return repr(event["arg"]), ""
    if op == "SifLoadModule":
        return event["path"], "loaded"
    if op == "SifLoadModuleBuffer":
        return "buffer %#x" % event["buffer"], "loaded"
    if op == "SifExecModuleBuffer":
        return "%#x bytes" % event["size"], "started"
    if op == "unpack":
        return "to %#x" % event["target"], "%#x bytes" % event["produced"]
    if op.startswith("sceCd"):
        return "(%d, %d)" % tuple(event["args"]), str(result)
    if op == "ExecPS2":
        return "entry %#x gp %#x argc %d" % (event["entry"], event["gp"], event["argc"]), ""
    return "", ""                                   # Exit, fatal, ExecOSD


def summary(report, focus=None):
    """The report as ordered text lines: "<call site> <call> <subject> -> <result>".

    Consecutive calls that differ only in one loop digit (POPS0..POPS9,
    TROJAN_0..9, PATCH_0..9, MODULE_0..9) and have the same result are folded
    into one line with the digit range in braces; when their call sites
    differ, the first and last site are given. Consecutive writes to one file
    are added up, and a call repeated unchanged is listed once with its count. Descriptor numbers are not shown (an open is "ok").

    The last line says how the run ended: the fatal handler's caller, Exit,
    ExecPS2, or "stop" with the address the run was told to stop at.

    focus: when given, keep only lines containing one of these substrings,
    plus that last line.
    """
    rows = []                           # [sites, op, subject, result, digits]
    for event in report["events"]:
        line = _line(event)
        if line is None:
            continue
        subject, result = line
        op, site = event["op"], event["site"]
        if rows:
            last = rows[-1]
            if op in ("fioWrite", "fileXioWrite") and last[1] == op and last[2] == subject:
                last[3] = "%#x bytes" % (int(last[3].split()[0], 16) + event["size"])
                continue
            match = _LOOP_DIGIT.search(subject)
            if match and last[4] and last[1] == op and last[3] == result:
                pattern = subject[:match.start()] + "#" + subject[match.end():]
                if pattern == last[5] and int(match.group()) == last[4][-1] + 1:
                    last[0].append(site)
                    last[4].append(int(match.group()))
                    continue
        match = _LOOP_DIGIT.search(subject)
        rows.append([[site], op, subject, result,
                     [int(match.group())] if match else None,
                     subject[:match.start()] + "#" + subject[match.end():] if match else None])
    lines = []
    for sites, op, subject, result, digits, pattern in rows:
        where = "%06x" % sites[0]
        if digits and len(digits) > 1:
            subject = pattern.replace("#", "{%d..%d}" % (digits[0], digits[-1]))
            if len(set(sites)) > 1:
                where = "%06x..%06x" % (sites[0], sites[-1])
        text = "%s %s" % (where, op)
        if subject:
            text += " " + subject
        if result:
            text += " -> " + result
        if lines and lines[-1].split(" (", 1)[0] == text and not digits:
            head, _, count = lines[-1].partition(" (")
            lines[-1] = "%s (%d times)" % (text, int(count.split()[0]) + 1 if count else 2)
            continue
        lines.append(text)
    end = report["end"]
    if end["kind"] not in ("fatal", "exit", "exec"):
        lines.append("%06x %s" % (end.get("site", 0),
                                  "stop" if end["kind"] == "stopped" else end["kind"]))
    if focus is not None and lines:
        lines = [line for line in lines[:-1] if any(key in line for key in focus)] + lines[-1:]
    return lines


def vcd_tries(report):
    """Every disc-image location the run asked for, in order, as canonical
    names (a pfsN: path is given with the partition mounted at that moment)."""
    return [event["resolved"] or event["path"] for event in report["events"]
            if event["op"] in ("fioOpen", "fileXioOpen")
            and event["path"].upper().endswith(".VCD")]


# ---------------------------------------------------------------------------
# The fixed case list
# ---------------------------------------------------------------------------

# File contents: an int is that many zero bytes; "@NAME" is the real Sony file
# NAME (POPS.ELF is POPS_TEST_ELF itself, the others are looked for beside
# it); bytes are used as they are.
_ELF, _IOX, _PAK, _IOPRP = "@POPS.ELF", "@POPS_IOX.PAK", "@POPS.PAK", "@IOPRP252.IMG"
_VCD = 0x100000
_COMMON = "hdd0:__common:pfs:/POPS/"
USB_PACK = {"mass:/POPS/POPS_IOX.PAK": _IOX}
HDD_POPS = {_COMMON + "POPS.ELF": _ELF, _COMMON + "IOPRP252.IMG": _IOPRP}
SMB_TEXT = b"192.168.0.2 PS2SMB\r\nuser\r\npw\r\n"
SMB_MODULES = ("poweroff", "ps2dev9", "ps2ip", "ps2smap", "smbman")
SMB_STACK = dict({"mc0:/POPSTARTER/SMBCONFIG.DAT": SMB_TEXT},
                 **{"mc0:/POPSTARTER/%s.irx" % name: 0x1000 for name in SMB_MODULES})
ALL_POPS_PARTITIONS = tuple(["hdd0:__.POPS"] + ["hdd0:__.POPS%d" % i for i in range(10)])
TO_THE_END = "end"                      # run through to ExecPS2
_T72, _T73 = "T" * 72, "T" * 73


def _case(argv, files=None, partitions=(), directories=(), results=None,
          stop=LAUNCHING, focus=None, note=""):
    return {"argv": list(argv), "files": dict(files or {}), "partitions": tuple(partitions),
            "directories": tuple(directories), "results": results,
            "stop": None if stop == TO_THE_END else stop, "focus": focus, "note": note}


_F_VCD = (".VCD", "Mount", "sceCdGetDiskType", "GAME/", "GAME ")
_F_PACK = ("POPS_IOX", "POPS.PAK", "POPS.ELF", "IOPRP", "unpack")
_F_BOOT = ("POPS ", "POPS/ ", "__common", "CONFIG", ".irx", "Mkdir")

CASES = {
    # -- the four launch kinds, run through to ExecPS2 ----------------------
    "usb": _case(["mass:/POPS/XX.GAME.ELF"], {**USB_PACK, "mass:/POPS/GAME.VCD": _VCD},
                 stop=TO_THE_END, note="XX. launch, nothing optional present"),
    "hdd": _case(["hdd0:__common:pfs:/POPS/GAME.ELF"],
                 {**HDD_POPS, "hdd0:__.POPS:pfs:/GAME.VCD": _VCD},
                 stop=TO_THE_END, note="plain name: multi-game partition hdd0:__.POPS"),
    "hdd-pp": _case(["hdd0:PP.GAME:pfs:/PP.GAME.ELF"],
                    {**HDD_POPS, "hdd0:PP.GAME:pfs:/IMAGE0.VCD": _VCD},
                    stop=TO_THE_END, note="PP. name: one partition per game"),
    "smb": _case(["mass:/POPS/SB.GAME.ELF"],
                 {**USB_PACK, **SMB_STACK, "mass:/POPS/GAME.VCD": _VCD},
                 stop=TO_THE_END, note="SB. launch with a full network stack on mc0"),
    # -- per-game folder, memory cards, icon ---------------------------------
    "usb-folder": _case(["mass:/POPS/XX.GAME.ELF"],
                        {**USB_PACK, "mass:/POPS/GAME.VCD": _VCD,
                         "mass:/POPS/GAME/SLOT0.VMC": 0x20000,
                         "mass:/POPS/GAME/SLOT1.VMC": 0x20000},
                        note="game folder and both memory cards already there"),
    "hdd-folder": _case(["hdd0:__common:pfs:/POPS/GAME.ELF"],
                        {**HDD_POPS, "hdd0:__.POPS:pfs:/GAME.VCD": _VCD,
                         _COMMON + "GAME/icon.sys": 964, _COMMON + "GAME/list.ico": 16},
                        note="game folder with icon files already there"),
    # -- the ten-step retries ------------------------------------------------
    "usb-pops4": _case(["mass:/POPS/XX.GAME.ELF"], {**USB_PACK, "mass:/POPS4/GAME.VCD": _VCD},
                       directories=["mass:/POPS4/GAME"],
                       note="disc image only in mass:/POPS4, game folder present there"),
    "usb-no-vcd": _case(["mass:/POPS/XX.GAME.ELF"], USB_PACK, focus=_F_VCD,
                        note="no disc image anywhere, no PS1 disc"),
    "hdd-pops3": _case(["hdd0:__common:pfs:/POPS/GAME.ELF"],
                       {**HDD_POPS, "hdd0:__.POPS3:pfs:/GAME.VCD": _VCD},
                       partitions=["hdd0:__.POPS", "hdd0:__.POPS0", "hdd0:__.POPS1"],
                       focus=_F_VCD, note="disc image only in hdd0:__.POPS3; __.POPS2 absent"),
    "hdd-no-vcd": _case(["hdd0:__common:pfs:/POPS/GAME.ELF"], HDD_POPS,
                        partitions=ALL_POPS_PARTITIONS, focus=_F_VCD,
                        note="all eleven partitions exist, none has the image"),
    "hdd-pp-no-vcd": _case(["hdd0:PP.GAME:pfs:/PP.GAME.ELF"], HDD_POPS,
                           partitions=["hdd0:PP.GAME"], focus=_F_VCD,
                           note="single-game partition without IMAGE0.VCD: no retry"),
    # -- physical disc -------------------------------------------------------
    "usb-disc": _case(["mass:/POPS/XX.GAME.ELF"], USB_PACK,
                      results={"sceCdGetDiskType": 0x10}, focus=_F_VCD + ("sceCd",),
                      note="no image, disc type 0x10 reported"),
    "usb-tray": _case(["mass:/POPS/XX.GAME.ELF"], USB_PACK,
                      results={"sceCdStatus": 1}, focus=("sceCd",),
                      note="no image, drive status 1"),
    # -- what stops a launch before the image is looked for -----------------
    "usb-no-pops-folder": _case(["mass:/POPS/XX.GAME.ELF"], {}, focus=_F_BOOT),
    "hdd-no-common": _case(["hdd0:__common:pfs:/POPS/GAME.ELF"], {}, focus=_F_BOOT),
    "hdd-no-pops-folder": _case(["hdd0:__common:pfs:/POPS/GAME.ELF"], {},
                                partitions=["hdd0:__common"], focus=_F_BOOT),
    "smb-no-config": _case(["mass:/POPS/SB.GAME.ELF"], USB_PACK, focus=_F_BOOT),
    "smb-bad-config": _case(["mass:/POPS/SB.GAME.ELF"],
                            {**USB_PACK, "mc0:/POPSTARTER/SMBCONFIG.DAT": b"192.168.0.2\r\n"},
                            focus=_F_BOOT, note="first line has no space"),
    "smb-no-iox": _case(["mass:/POPS/SB.GAME.ELF"],
                        {**SMB_STACK, "mass:/POPS/POPS.PAK": _PAK, "mass:/POPS/GAME.VCD": _VCD},
                        focus=_F_PACK + ("Devctl",), note="only the older pack is there"),
    "smb-no-modules": _case(["mass:/POPS/SB.GAME.ELF"],
                            {**USB_PACK, "mc0:/POPSTARTER/SMBCONFIG.DAT": SMB_TEXT},
                            focus=_F_BOOT),
    # -- POPS package search and acceptance ----------------------------------
    "usb-pak": _case(["mass:/POPS/XX.GAME.ELF"],
                     {"mass:/POPS/POPS.PAK": _PAK, "mass:/POPS/GAME.VCD": _VCD}, focus=_F_PACK),
    "usb-elf": _case(["mass:/POPS/XX.GAME.ELF"],
                     {"mass:/POPS/POPS.ELF": _ELF, "mass:/POPS/IOPRP252.IMG": _IOPRP,
                      "mass:/POPS/GAME.VCD": _VCD}, focus=_F_PACK),
    "usb-iox-size": _case(["mass:/POPS/XX.GAME.ELF"],
                          {"mass:/POPS/POPS_IOX.PAK": 0xE50B9, "mass:/POPS/POPS.PAK": 0xE6241,
                           "mass:/POPS/POPS.ELF": 0x30530D}, focus=_F_PACK,
                          note="all three one byte too long"),
    "usb-elf-no-ioprp": _case(["mass:/POPS/XX.GAME.ELF"], {"mass:/POPS/POPS.ELF": _ELF},
                              focus=_F_PACK),
    "hdd-no-package": _case(["hdd0:__common:pfs:/POPS/GAME.ELF"],
                            {_COMMON + "POPS_IOX.PAK": _IOX, _COMMON + "POPS.PAK": _PAK},
                            focus=_F_PACK, note="only the two packs are there"),
    "hdd-ioprp-img": _case(["hdd0:__common:pfs:/POPS/GAME.ELF"],
                           {_COMMON + "POPS.ELF": _ELF, _COMMON + "IOPRP.IMG": _IOPRP,
                            "hdd0:__.POPS:pfs:/GAME.VCD": _VCD}, focus=_F_PACK,
                           note="the image under its second name"),
    "hdd-ioprp-zero": _case(["hdd0:__common:pfs:/POPS/GAME.ELF"],
                            {_COMMON + "POPS.ELF": _ELF, _COMMON + "IOPRP252.IMG": 0x40C11},
                            focus=_F_PACK, note="right size, wrong content"),
    "hdd-elf-zero": _case(["hdd0:__common:pfs:/POPS/GAME.ELF"],
                          {_COMMON + "POPS.ELF": 0x30530C, _COMMON + "IOPRP252.IMG": _IOPRP},
                          focus=_F_PACK, note="right size, wrong content"),
    # -- name length ---------------------------------------------------------
    "usb-72": _case(["mass:/POPS/XX.%s.ELF" % _T72],
                    {**USB_PACK, "mass:/POPS/%s.VCD" % _T72: _VCD}, focus=(".VCD",)),
    "usb-73": _case(["mass:/POPS/XX.%s.ELF" % _T73],
                    {**USB_PACK, "mass:/POPS/%s.VCD" % _T73: _VCD}, focus=(".VCD",)),
    "hdd-72": _case(["hdd0:__common:pfs:/POPS/%s.ELF" % _T72],
                    {**HDD_POPS, "hdd0:__.POPS:pfs:/%s.VCD" % _T72: _VCD}, focus=(".VCD",)),
    "hdd-73": _case(["hdd0:__common:pfs:/POPS/%s.ELF" % _T73],
                    {**HDD_POPS, "hdd0:__.POPS:pfs:/%s.VCD" % _T73: _VCD}, focus=(".VCD",)),
}

# argv[0] forms. Each is run with both POPS installations present, every
# partition it could ask for mountable, and no disc image anywhere, so the
# run walks its whole search and ends at the "no PS1 disc" stop; what it
# asked for is the measured search list of that form.
FORMS = (
    "mass:/POPS/XX.GAME.ELF", "mass:/XX.GAME.ELF", "mass:/POPS/xx.GAME.ELF",
    "mass:/POPS/Xx.GAME.ELF", "mass:/POPS/xX.GAME.ELF", "mass:/POPS/XX.Game.elf",
    "mass:\\POPS\\XX.GAME.ELF", "mass:XX.GAME.ELF", "mass0:/POPS/XX.GAME.ELF",
    "hdd0:__common:pfs:/POPS/XX.GAME.ELF", "XX.GAME.ELF", "GAME.ELF",
    "mass:/POPS/XX.GAME", "mass:/POPS/GAME.ELF", "mc0:/BOOT/GAME.ELF",
    "mass:/POPS/SB.GAME.ELF", "mass:/POPS/sb.GAME.ELF", "mc0:/POPSTARTER/SB.GAME.ELF",
    "mass:/APPS/PP.GAME.ELF", "mass:/APPS/__.GAME.ELF", "mass:/APPS/pp.GAME.ELF",
    "hdd0:__common:pfs:/POPS/GAME.ELF", "hdd0:PP.ALPHA:pfs:/PP.BETA.ELF",
    "hdd0:PP.ALPHA:pfs:/__.BETA.ELF", "hdd0:PP.ALPHA:pfs:/pp.BETA.ELF",
    "hdd0:PP.ALPHA:pfs:/SUB/PP.BETA.ELF", "hdd0:PP.ALPHA:pfs:/EXECUTE.KELF",
    "hdd0:PP.ALPHA:pfs:/EXECUTE.ELF", "hdd0:PP.ALPHA:pfs:/LAUNCHER.ELF",
    "hdd0:PP.ALPHA:pfs:/LAUNCHER.KELF", "hdd0:PP.ALPHA:pfs:/execute.kelf",
    "hdd0:PP.ALPHA:pfs:/SUB/EXECUTE.KELF", "hdd0:ALPHA:pfs:/EXECUTE.KELF",
    "hdd0:PP.ALPHA:PATINFO", "hdd0:__.ALPHA:PATINFO", "hdd0:ALPHA:PATINFO",
    "hdd0:PP.ALPHA:patinfo", "pfs0:/EXECUTE.KELF", "cdrom0:\\SLUS_000.00;1", None,
)
FORM_PARTITIONS = ALL_POPS_PARTITIONS + (
    "hdd0:PP.ALPHA", "hdd0:__.ALPHA", "hdd0:ALPHA", "hdd0:PP.BETA", "hdd0:__.BETA",
    "hdd0:PP.GAME", "hdd0:__.GAME")


def _content(spec):
    """A file spec -> bytes or int; None when a needed Sony file is absent."""
    if not isinstance(spec, str):
        return spec
    core = os.environ.get("POPS_TEST_ELF")
    if not core:
        return None
    path = Path(core) if spec == _ELF else Path(core).parent / spec[1:]
    return path.read_bytes() if path.is_file() else None


def missing_inputs(files):
    """Names of the Sony files a file table needs and this machine lacks."""
    return sorted({spec[1:] for spec in files.values()
                   if isinstance(spec, str) and _content(spec) is None})


def run_case(name, watch=()):
    """Run one entry of CASES; returns the report."""
    case = CASES[name]
    require(not missing_inputs(case["files"]), "inputs missing for case %s" % name)
    files = {path: _content(spec) for path, spec in case["files"].items()}
    return trace(case["argv"], files, partitions=case["partitions"],
                 directories=case["directories"], results=case["results"],
                 stop_at=case["stop"], watch=watch)


def run_form(argv0):
    """Run one argv[0] form (None: argc == 0) with nothing to find.

    Returns {"type", "mass", "smb", "tries", "end"}: the launch-type word,
    the two mode words, the ordered disc-image locations asked for, and how
    the run ended ("fatal 876a0c", "exit 8713c8", ...).
    """
    files = dict(USB_PACK, **HDD_POPS, **SMB_STACK)
    require(not missing_inputs(files), "inputs missing for the argv forms")
    files = {path: _content(spec) for path, spec in files.items()}
    report = trace([] if argv0 is None else [argv0], files, partitions=FORM_PARTITIONS,
                   stop_at=LAUNCHING)
    state, end = report["state"], report["end"]
    return {"type": state["launch_type"], "mass": state["mass_mode"],
            "smb": state["smb_mode"], "tries": vcd_tries(report),
            "end": "%s %06x" % (end["kind"], end.get("site", 0))}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("argv0", nargs="?", help="argv[0] to launch with")
    parser.add_argument("--file", action="append", default=[], metavar="NAME[=SIZE]",
                        help="a modelled file (canonical device path), zero-filled")
    parser.add_argument("--partition", action="append", default=[])
    parser.add_argument("--verbose", action="store_true",
                        help="non-quiet profile: record the program's messages")
    parser.add_argument("--stop-at", type=lambda s: int(s, 16))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--case", action="append", default=[],
                        help="run a named case of the fixed list (see --list)")
    parser.add_argument("--all-cases", action="store_true")
    parser.add_argument("--forms", action="store_true",
                        help="run every argv[0] form and print its search list")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--full", action="store_true",
                        help="with --case: every line, not the case's focus")
    args = parser.parse_args()
    if args.list:
        for name, case in CASES.items():
            print("%-20s %s  %s" % (name, case["argv"], case["note"]))
        return
    if args.forms:
        for form in FORMS:
            print(repr(form), json.dumps(run_form(form)))
        return
    if args.case or args.all_cases:
        for name in (list(CASES) if args.all_cases else args.case):
            case = CASES[name]
            print("== %s: %s" % (name, case["argv"]))
            if missing_inputs(case["files"]):
                print("   skipped, missing:", ", ".join(missing_inputs(case["files"])))
                continue
            report = run_case(name)
            for line in summary(report, None if args.full else case["focus"]):
                print("   " + line)
            state = report["state"]
            print("   state: type %d mass %d smb %d disc %d suffix %d %r quiet %d; written %s"
                  % (state["launch_type"], state["mass_mode"], state["smb_mode"],
                     state["physical_disc"], state["suffix_in_use"],
                     chr(state["suffix_char"]) if state["suffix_char"] else "",
                     state["quiet"],
                     {name: "%#x" % size for name, size in report["written"].items()}))
        return
    files = {}
    for item in args.file:
        name, _, size = item.partition("=")
        files[name] = int(size, 0) if size else 0
    report = trace([args.argv0] if args.argv0 is not None else [], files,
                   partitions=args.partition,
                   preset={0x100010: 0xFF} if args.verbose else None,
                   stop_at=args.stop_at)
    if args.json:
        print(json.dumps(report, indent=1))
        return
    for line in summary(report):
        print(line)
    for item in report["prints"]:
        print("print %#x %r" % (item["site"], item["text"]))
    print("end:", report["end"])
    print("state:", report["state"])


if __name__ == "__main__":
    main()
