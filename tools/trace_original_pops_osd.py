#!/usr/bin/env python3
"""Execute r13's OSD.BIN handler with synthetic files and modelled services.

Only return codes, core bytes in memory, named flags and I/O metadata are
exposed to tests. Original message text is reduced to a reason code and is
never printed. No reference bytes are stored in this file.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trace_original_pops_user_bios as U  # noqa: E402

HANDLER = 0x87EB24
V1_ADDR, V1_CAP = 0x263C20, 0x4C000
V2_ADDR, V2_CAP = 0x262B80, 0x4D0A0
FLAGS = dict(U.FLAGS)
FLAGS.update({
    "integrity": 0x3890,
    "no_fix": 0x3458,
    "folder_checked": 0x3868,
    "game_opened": 0x38E0,
})
U.NATIVE = tuple(U.NATIVE) + ((0x8DC2C4, 0x8DC8E4),)


def make_osd(version=1, body_size=16, *, seed=0, modes=(), flag=0,
             load=None, entry=None, build=1, label=1, magic=b"PS-X OSD"):
    if load is None:
        load = 0x1F800000 if version == 1 else 0x12340000
    if entry is None:
        entry = 0x1F800000 if version == 1 else 0x56780000
    header = bytearray(64)
    header[:8] = magic
    header[0x0C] = version
    header[0x0E] = build
    struct.pack_into("<I", header, 0x10, load & 0xFFFFFFFF)
    struct.pack_into("<I", header, 0x14, entry & 0xFFFFFFFF)
    struct.pack_into("<I", header, 0x1C, body_size)
    header[0x20] = label
    header[0x38:0x38 + len(modes)] = bytes(modes)
    header[0x3C] = flag
    body = bytes((seed + i * 13 + i // 7) & 0xFF for i in range(body_size))
    return bytes(header) + body


def osd_path(scope, backend, game=b"GAME/"):
    return (b"mass:" if backend else b"pfs1:") + b"/POPS/" + (game if scope == 1 else b"") + b"OSD.BIN"


def get(core, address, width):
    return int.from_bytes(core[address - U.CORE_BASE:address - U.CORE_BASE + width], "little")


class Files(U._Files):
    def __init__(self, m, files, read_faults=None):
        super().__init__(m, files)
        self.read_faults = read_faults or {}
        self.read_number = 0

    def read(self, a, mass):
        which = "header" if self.read_number == 0 else "body"
        self.read_number += 1
        fd = self.fds[a[0]]
        requested = a[2]
        fault = self.read_faults.get(which)
        if isinstance(fault, int) and fault < 0:
            self.log.append(("read", which, requested, fault))
            return fault
        count = requested if fault is None else min(fault, requested)
        data = fd[0][fd[1]:fd[1] + count]
        fd[1] += len(data)
        self.m.uc.mem_write(a[1], bytes(data))
        self.log.append(("read", which, requested, len(data)))
        return len(data)


def _memory_helpers(m):
    def copy(a):
        data = m.uc.mem_read(a[1], a[2])
        m.uc.mem_write(a[0], bytes(data))
        return a[0]

    def clear(a):
        m.uc.mem_write(a[0], bytes([a[1] & 0xFF]) * a[2])
        return a[0]

    m.hooks[0x918808] = copy
    m.hooks[0x9188B8] = clear


def _reason(prints):
    rules = (
        (b"not an OSD replacement file", "NOT_FILE"),
        (b"not supported", "VERSION"),
        (b"invalid header data", "HEADER"),
        (b"invalid load address", "LOAD"),
        (b"invalid entrypoint", "ENTRY"),
        (b"size does not match", "SIZE"),
        (b"too big", "TOO_BIG"),
        (b"build identifier", "BUILD"),
        (b"does not have a label", "LABEL"),
    )
    for fragment, reason in rules:
        if any(fragment in text for text in prints):
            return reason
    return None


def run_osd(core, scope=0, backend=0, data=None, flags=None, game=b"GAME/",
            game_dir_ok=True, read_faults=None):
    m = U.machine()
    m.reset(core)
    m.put(U.GP + 0x3448, backend)
    m.put(U.GP + 0x3868, 1)
    m.put(U.GP + 0x3890, 1)
    m.put(U.GP + 0x38B0, 0)
    for name, value in (flags or {}).items():
        m.put(U.GP + (FLAGS[name] if isinstance(name, str) else name), value)
    m.uc.mem_write(U.NAME, game + b"\0")
    files = {} if data is None else {osd_path(scope, backend, game): bytes(data)}
    io = Files(m, files, read_faults)
    _memory_helpers(m)
    m.hooks[0x8D7E78] = lambda a: 1 if game_dir_ok else 0
    m.hooks[0x91BF80] = lambda a: 0 if game_dir_ok else -2
    m.hooks[0x8D8958] = lambda a: m.put(U.GP + 0x3868, 1) or 1
    m.uc.reg_write(m.R.UC_MIPS_REG_A0, scope)
    m.uc.reg_write(m.R.UC_MIPS_REG_A1, U.NAME)
    ret = m.run(HANDLER, U.SENTINEL, (HANDLER, 0x88019C))
    return {
        "ret": ret,
        "core": m.core(),
        "flags": {name: m.get(U.GP + off) for name, off in FLAGS.items()},
        "io": io.log,
        "reason": _reason(m.prints),
        "print_count": len(m.prints),
    }
