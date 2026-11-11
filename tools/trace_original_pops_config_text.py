#!/usr/bin/env python3
"""Run POPStarter r13's own text readers: CHEATS.TXT commands and VMCDIR.TXT.

Needs the external POPStarter MAIN (POPSTARTER_TEST_ELF) and Python's
Unicorn package. No original bytes are included or written: the MAIN is read
at run time, the same way trace_original_pops_io.py reads it.

scan_commands(text) runs the original's CHEATS.TXT section from the point
where the file text is in its buffer (0x883aa8) to the end of its command
pass (0x89e884), and reports what the pass recognised:

  events   (offset, name, length, effects) for every command it took, in
           file order. `name` is the literal its compare chain starts with
           ('$SMOOTH', '$DX_', '$PAD', '$?POS_' ...), `length` is the
           offset of the last text byte it read from the '$' (the
           terminator), `effects` counts the pokes, calls and gp stores it
           made before moving on.
  skips    (offset, columns) for every cheat code the pass stepped over
           (14 or 18 columns, left in the text for the later code passes).
  writes   (width, address, value) for every poke helper call.
  calls    (name, a0, a1) for the compatibility-mode function and the
           other helpers a handler calls.
  flags    gp-relative stores made during the pass: {offset: last value}.
  usb_delay  the byte at 0x100017 afterwards (the caller chooses what it
           holds before; POPStarter ships 1 there).

The pass, as its code reads (0x883aa8..0x89e75c):
  * the text is upper-cased in place (a..z only) and the buffer holds as
    many zero bytes after the text as the text is long;
  * at each index: a cheat code's columns are stepped over (0x885a20,
    0x885ccc, 0x885e28, 0x8860b4, 0x886360); otherwise each command's
    compare chain is tried in turn and the first that holds runs, zeroes
    the byte at the index and moves one byte on; otherwise the byte at the
    index is zeroed and the scan moves one byte on.
So a command is taken at any '$' not inside a cheat code's columns, whatever
precedes it. FUN_008e00d0 ($VCDID_n's built-in entry) and printf are not run.

vmcdir(text) runs the VMCDIR.TXT reader (FUN_008d4f84) with the file
services answered from `text`, and reports the two path buffers it rewrites.

This is bounded execution of two routines with synthetic inputs, not a POPS
boot or a console test.

    python tools/trace_original_pops_config_text.py '$SMOOTH$SCANLINES\\r\\n'
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_original_pops_io import decode_main  # noqa: E402

BASE = 0x870000
LIMIT = 0xA00000
GP = 0x9B68F0
BSS = (0x9B9D00, 0x9CCAC0)
FP = 0x1F80000
TEXT = 0x1E00000
CURSOR = 0x01A00000
START = 0x883AA8
LOOP = 0x885A04          # head of the command pass
LOOP_END = 0x89E75C      # the pass's exit
NO_MATCH = 0x89E754      # 'nothing here': zero the byte, one byte on
COMMANDS_DONE = 0x89E884  # after the manual-DISPLAY write that follows it
STOPS = (COMMANDS_DONE, 0x8D4E30, 0x8D4F6C)
USB_DELAY = 0x100017
POKES = {0x8DC8E4: 8, 0x8DC918: 16, 0x8DC94C: 32, 0x8DC97C: 64,
         0x87C298: 8, 0x87C2CC: 16, 0x87C300: 32, 0x87C330: 64,
         0x8D6B9C: 8, 0x8D6BD0: 16, 0x8D6C04: 32, 0x8D6C34: 64, 0x8D6C64: 128}
CALLS = {0x8DC2C4: "compat", 0x8D6DA4: "breakpoint", 0x8D6F64: "recompiler0",
         0x8D6FA4: "recompiler1", 0x8D6FE4: "recompiler2", 0x918808: "memcpy"}
SKIPPED = {0x8E00D0: "vcdid", 0x915708: "printf"}
CHEAT_SKIPS = {0x885CC4: 14, 0x885E20: 18, 0x8860AC: 18, 0x886358: 18, 0x8864DC: 18}

_IMAGE = None
_HANDLERS = None


def _image():
    global _IMAGE
    if _IMAGE is None:
        _IMAGE = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
    return _IMAGE


def _word(address):
    return struct.unpack_from("<I", _image(), address - BASE)[0]


def _sx16(value):
    return value - 0x10000 if value & 0x8000 else value


def _chain_test(address):
    """Decode one 'text[index + k] against a constant' test of the -O0 code.

    Returns (kind, k, constant, target, next_address) or None. The tests all
    start lw v1,0x98(fp); lw v0,0x94(fp); addu v0,v1,v0; [addiu v0,v0,k]."""
    if (_word(address), _word(address + 4), _word(address + 8)) != \
            (0x8FC30098, 0x8FC20094, 0x00621021):
        return None
    at, k = address + 12, 0
    word = _word(at)
    if word >> 16 == 0x2442:  # addiu v0,v0,k
        k, at = _sx16(word & 0xFFFF), at + 4
        word = _word(at)
    if word == 0x90430000:  # lbu v1,(v0); addiu v0,zero,C; bne/beq v1,v0
        load, branch = _word(at + 4), _word(at + 8)
        if load >> 16 == 0x2402 and branch >> 16 in (0x1462, 0x1062) and not _word(at + 12):
            return ("ne" if branch >> 16 == 0x1462 else "eq", k, load & 0xFFFF,
                    at + 12 + _sx16(branch & 0xFFFF) * 4, at + 16)
    elif word == 0x90420000:  # lbu v0,(v0); beqz / bnez / sltiu
        branch = _word(at + 4)
        if branch >> 16 in (0x1040, 0x1440) and not _word(at + 8):
            return ("z" if branch >> 16 == 0x1040 else "nz", k, 0,
                    at + 8 + _sx16(branch & 0xFFFF) * 4, at + 12)
        if branch >> 16 == 0x2C42:
            jump = _word(at + 8)
            if jump >> 16 in (0x1040, 0x1440) and not _word(at + 12):
                return ("ge" if jump >> 16 == 0x1040 else "lt", k, branch & 0xFFFF,
                        at + 12 + _sx16(jump & 0xFFFF) * 4, at + 16)
    return None


def chain_tests(start, end):
    """Every text test between two addresses: (address, kind, k, constant, target)."""
    out, at = [], start
    while at < end:
        test = _chain_test(at)
        if test:
            out.append((at,) + test[:4])
            at = test[4]
        else:
            at += 4
    return out


def handlers():
    """{back-edge address: name} for the command pass, read from the image.

    A handler ends in 'b LOOP'; its name is the run of
    'text[k] != C -> next handler' tests it starts with, with '?' where a
    position is left to a later test."""
    global _HANDLERS
    if _HANDLERS is not None:
        return _HANDLERS
    edges = []
    for at in range(LOOP, LOOP_END, 4):
        word = _word(at)
        if word >> 16 == 0x1000 and at + 4 + _sx16(word & 0xFFFF) * 4 == LOOP:
            edges.append(at)
    found, previous = {}, LOOP
    for edge in edges:
        if edge in CHEAT_SKIPS or edge == NO_MATCH:
            previous = edge
            continue
        name = {}
        for _, kind, k, constant, _ in chain_tests(previous, edge):
            if kind != "ne" or k in name:
                break
            name[k] = chr(constant)
        found[edge] = "".join(name.get(k, "?") for k in range(max(name) + 1)) if name else "?"
        previous = edge
    _HANDLERS = found
    return found


class CommandScan:
    def __init__(self):
        self.events = []
        self.skips = []
        self.writes = []
        self.calls = []
        self.flags = {}
        self.usb_delay = None
        self.text = b""

    def __repr__(self):
        return "CommandScan(events=%r, skips=%r, writes=%d, calls=%r, flags=%r, usb_delay=%r)" % (
            self.events, self.skips, len(self.writes), self.calls, self.flags, self.usb_delay)


def _machine():
    from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN
    from unicorn import mips_const as R

    uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
    try:
        uc.ctl_set_cpu_model(R.UC_CPU_MIPS64_5KF)
    except Exception:
        pass
    uc.mem_map(0, 0x02000000)
    uc.mem_write(BASE, bytes(_image()[: LIMIT - BASE]))
    uc.mem_write(BSS[0], b"\0" * (BSS[1] - BSS[0]))
    uc.reg_write(R.UC_MIPS_REG_GP, GP)
    return uc, R


class _EE:
    """The EE-only instructions these routines use, which Unicorn's MIPS64
    core lacks (as trace_original_pops_cheats.py models them)."""

    def __init__(self, uc, R):
        self.uc = uc
        self.R = R
        self.regs = [getattr(R, "UC_MIPS_REG_%d" % i) for i in range(32)]
        self.upper = [0] * 32

    def get(self, r):
        return self.uc.reg_read(self.regs[r]) & 0xFFFFFFFFFFFFFFFF

    @staticmethod
    def sx32(v):
        v &= 0xFFFFFFFF
        return v | 0xFFFFFFFF00000000 if v & 0x80000000 else v

    def step(self, addr, word):
        """Run one EE-only instruction; True when it was one."""
        u, R, regs, upper, get = self.uc, self.R, self.regs, self.upper, self.get
        op = word >> 26
        rs, rt, rd = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
        simm = _sx16(word & 0xFFFF)
        fn, sa = word & 63, (word >> 6) & 31
        if op == 0 and fn in (0x18, 0x19) and rd:
            a, b = get(rs) & 0xFFFFFFFF, get(rt) & 0xFFFFFFFF
            if fn == 0x18:
                a = a - (1 << 32) if a & 0x80000000 else a
                b = b - (1 << 32) if b & 0x80000000 else b
            prod = (a * b) & 0xFFFFFFFFFFFFFFFF
            u.reg_write(R.UC_MIPS_REG_LO, self.sx32(prod))
            u.reg_write(R.UC_MIPS_REG_HI, self.sx32(prod >> 32))
            u.reg_write(regs[rd], self.sx32(prod))
        elif op == 0x1C and fn == 0x09 and sa == 0x0E:  # pcpyld
            lo, hi = get(rt), get(rs)
            if rd:
                u.reg_write(regs[rd], lo)
                upper[rd] = hi
        elif op == 0x1C and fn == 0x29 and sa == 0x1B:  # pcpyh
            def rep(x):
                h = x & 0xFFFF
                return h | h << 16 | h << 32 | h << 48
            if rd:
                u.reg_write(regs[rd], rep(get(rt)))
                upper[rd] = rep(upper[rt])
        elif op == 0x1C and fn == 0x29 and sa == 0x0E:  # pcpyud
            if rd:
                u.reg_write(regs[rd], upper[rs])
                upper[rd] = upper[rt]
        elif op == 0x1C and fn == 0x29 and sa == 0x12:  # por
            if rd:
                u.reg_write(regs[rd], get(rs) | get(rt))
                upper[rd] = upper[rs] | upper[rt]
        elif op == 0x1C:
            raise RuntimeError("unmodelled MMI %#010x at %#x" % (word, addr))
        elif op == 0x1F:  # sq
            a = (get(rs) + simm) & 0xFFFFFFF0
            u.mem_write(a, struct.pack("<QQ", get(rt), upper[rt] if rt else 0))
        elif op == 0x1E:  # lq
            a = (get(rs) + simm) & 0xFFFFFFF0
            lo, hi = struct.unpack("<QQ", u.mem_read(a, 16))
            if rt:
                u.reg_write(regs[rt], lo)
                upper[rt] = hi
        else:
            return False
        u.reg_write(R.UC_MIPS_REG_PC, addr + 4)
        return True


def scan_commands(text: bytes | str, usb_delay: int = 1, gp_words=None, number: int = 0,
                  beyond: bytes = b"") -> CommandScan:
    """Run the original's command pass over one CHEATS.TXT text.

    usb_delay is what 0x100017 holds beforehand; gp_words {offset: value}
    presets gp-relative state (all zero otherwise, as a first file finds it
    with no built-in entry active). number is what the shared number
    temporary fp+0x90 holds when the pass starts: the function stores 0 there
    (0x883288) and, for the game's own file only, the length of the game's
    name (0x883430); nothing else writes it before the pass.

    beyond is what the heap holds right after the function's buffer. The
    buffer is malloc(2 * size) (0x8839f0) and the code zeroes its second
    half (0x883aa8), but a code test reads columns 9 and 14 from a '$', so
    in a file of a few bytes it reads past the 2 * size bytes. Zeros are
    written here after `beyond`."""
    from unicorn import UC_HOOK_CODE

    data = text.encode("latin-1") if isinstance(text, str) else bytes(text)
    if len(data) > 0x40000:
        raise ValueError("text too long")
    uc, R = _machine()
    image = _image()
    names = handlers()
    # The first half is the text; the second half is zeroed by the code
    # itself, so what is put there does not matter (0xA5 shows that it is).
    uc.mem_write(TEXT, data + b"\xa5" * len(data) + bytes(beyond) + b"\0" * 64)
    uc.mem_write(USB_DELAY, bytes([usb_delay & 0xFF]))

    def put(address, value):
        uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    def u32(address):
        return struct.unpack("<I", uc.mem_read(address, 4))[0]

    put(FP + 0x98, TEXT)
    put(FP + 0xE8, len(data))
    put(FP + 0xDC, CURSOR)
    put(FP + 0xE0, CURSOR)
    put(FP + 0x90, number)
    # Templates the section's prologue stores (0x883288..0x8832f4).
    put(FP + 0xB4, 0x875A0000)
    put(FP + 0xBC, 0x0808E52C)
    put(FP + 0xE4, 0x002397E8)
    put(GP + 0x38B0, 1)  # quiet
    for offset, value in (gp_words or {}).items():
        put(GP + offset, value)
    uc.reg_write(R.UC_MIPS_REG_FP, FP)
    uc.reg_write(R.UC_MIPS_REG_SP, FP - 0x100)

    ee = _EE(uc, R)
    out = CommandScan()
    state = {"index": 0, "reach": 0, "effects": 0}
    stopped, failure = [], []
    widths = {0x28: 8, 0x29: 16, 0x2B: 32, 0x3F: 64}

    def hook(u, addr, size, _):
        try:
            if addr in STOPS:
                stopped.append(addr)
                u.emu_stop()
                return
            if not BASE <= addr < LIMIT:
                raise RuntimeError("left the image at %#x" % addr)
            if addr == LOOP:
                state["index"] = u32(FP + 0x94)
                state["reach"] = state["effects"] = 0
            elif addr in names:
                out.events.append((state["index"], names[addr], state["reach"], state["effects"]))
            elif addr in CHEAT_SKIPS:
                out.skips.append((state["index"], CHEAT_SKIPS[addr]))
            elif addr in POKES:
                width = POKES[addr]
                value = u.reg_read(R.UC_MIPS_REG_A0) & 0xFFFFFFFFFFFFFFFF
                if width == 128:
                    value |= ee.upper[4] << 64
                else:
                    value &= (1 << width) - 1
                out.writes.append((width, u.reg_read(R.UC_MIPS_REG_A1) & 0xFFFFFFFF, value))
                state["effects"] += 1
            elif addr in CALLS:
                a = [u.reg_read(r) & 0xFFFFFFFF for r in
                     (R.UC_MIPS_REG_A0, R.UC_MIPS_REG_A1, R.UC_MIPS_REG_A2)]
                if CALLS[addr] == "memcpy":
                    if not FP - 0x1000 <= a[0] < FP + 0x1000:
                        out.calls.append(("memcpy", a[0], bytes(u.mem_read(a[1], a[2]))))
                        state["effects"] += 1
                else:
                    out.calls.append((CALLS[addr], a[0], a[1]))
                    state["effects"] += 1
            elif addr in SKIPPED:
                out.calls.append((SKIPPED[addr], u.reg_read(R.UC_MIPS_REG_A0) & 0xFFFFFFFF, 0))
                if SKIPPED[addr] != "printf":
                    state["effects"] += 1
                u.reg_write(R.UC_MIPS_REG_V0, 0)
                u.reg_write(R.UC_MIPS_REG_PC, u.reg_read(R.UC_MIPS_REG_RA) & 0xFFFFFFFF)
                return
            word = struct.unpack_from("<I", image, addr - BASE)[0]
            if LOOP <= addr < LOOP_END and word in (0x90430000, 0x90420000):
                reach = (u.reg_read(R.UC_MIPS_REG_V0) & 0xFFFFFFFF) - TEXT - state["index"]
                if reach > state["reach"]:
                    state["reach"] = reach
            op = word >> 26
            if op in widths and (word >> 21) & 31 == 28:  # store to offset(gp)
                value = ee.get((word >> 16) & 31) & ((1 << widths[op]) - 1)
                out.flags[_sx16(word & 0xFFFF)] = value
                state["effects"] += 1
            ee.step(addr, word)
        except Exception as exc:  # surface hook errors instead of a bare stop
            failure.append(exc)
            u.emu_stop()

    uc.hook_add(UC_HOOK_CODE, hook)
    uc.emu_start(START, 0xFFFFFFFF, count=200_000_000)
    if failure:
        raise failure[0]
    if not stopped:
        raise RuntimeError("the command pass did not finish")
    out.usb_delay = uc.mem_read(USB_DELAY, 1)[0]
    out.text = bytes(uc.mem_read(TEXT, len(data)))
    return out


VMCDIR = 0x8D4F84
VMCDIR_END = 0x00F00000
VMCDIR_HEAP = 0x01C00000
VMCDIR_PATHS = (0x4F8080, 0x4F8100)   # the two POPS path strings the reader rewrites
FILE_OPEN, FILE_SEEK, FILE_READ, FILE_CLOSE = 0x8D6C94, 0x8D6D64, 0x8D6D24, 0x8D6CF4
STRLEN, MEMCPY, MEMSET, PRINTF, MALLOC, STAT = 0x918E08, 0x918808, 0x9188B8, 0x915708, 0x9190C8, 0x91BF80


class VmcDir:
    def __init__(self):
        self.result = None      # the function's return value (signed)
        self.opens = []         # paths it opened, in order
        self.messages = []      # printf format addresses, in order
        self.paths = {}         # {POPS address: bytes up to the NUL} for each path it rewrote
        self.copies = []        # (address, bytes) for every copy outside its own frame
        self.flags = {}         # gp-relative stores {offset: last value}

    def __repr__(self):
        return "VmcDir(result=%r, opens=%r, messages=%r, paths=%r, flags=%r)" % (
            self.result, self.opens, [hex(m) for m in self.messages], self.paths, self.flags)


def vmcdir(text: bytes | str, game: bytes | str | None = None, before=None) -> VmcDir:
    """Run the original's VMCDIR.TXT reader (FUN_008d4f84) on one file.

    game None is the call for the file "for all games" (a0 = 0); a name is
    the call for that game's own file (a0 = 1, a1 = name). The launch is a
    USB one (gp+0x3448 = 1), so the file is mass:/POPS/[game/]VMCDIR.TXT and
    the file services are the plain open/seek/read/close ones, answered here
    from `text` (None: the file does not exist). before {address: bytes}
    presets the two POPS path strings."""
    from unicorn import UC_HOOK_CODE

    data = None if text is None else (text.encode("latin-1") if isinstance(text, str) else bytes(text))
    name = b"" if game is None else (game.encode("latin-1") if isinstance(game, str) else bytes(game))
    uc, R = _machine()
    image = _image()
    ee = _EE(uc, R)
    out = VmcDir()
    stack = FP
    name_at = 0x01B00000
    uc.mem_write(name_at, name + b"\0")
    for address, value in (before or {}).items():
        uc.mem_write(address, value)

    def put(address, value):
        uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    for offset, value in ((0x3868, 1), (0x3448, 1)):
        put(GP + offset, value)
    uc.reg_write(R.UC_MIPS_REG_SP, stack)
    uc.reg_write(R.UC_MIPS_REG_FP, stack)
    uc.reg_write(R.UC_MIPS_REG_RA, VMCDIR_END)
    uc.reg_write(R.UC_MIPS_REG_A0, 0 if game is None else 1)
    uc.reg_write(R.UC_MIPS_REG_A1, name_at)

    files, failure, done = {}, [], []
    widths = {0x28: 8, 0x29: 16, 0x2B: 32, 0x3F: 64}

    def arg(n):
        return uc.reg_read((R.UC_MIPS_REG_A0, R.UC_MIPS_REG_A1, R.UC_MIPS_REG_A2)[n]) & 0xFFFFFFFF

    def cstring(address):
        raw = bytes(uc.mem_read(address, 0x400))
        return raw[: raw.index(b"\0")]

    def leave(value):
        uc.reg_write(R.UC_MIPS_REG_V0, value & 0xFFFFFFFFFFFFFFFF)
        uc.reg_write(R.UC_MIPS_REG_PC, uc.reg_read(R.UC_MIPS_REG_RA) & 0xFFFFFFFF)

    def hook(u, addr, size, _):
        try:
            if addr == VMCDIR_END:
                done.append(1)
                u.emu_stop()
            elif addr == FILE_OPEN:
                path = cstring(arg(0))
                out.opens.append(path)
                if data is None:
                    leave(-2)
                else:
                    files[3 + len(files)] = [data, 0]
                    leave(2 + len(files))
            elif addr == FILE_SEEK:
                entry = files[arg(0)]
                offset = arg(1) - (1 << 32) if arg(1) & 0x80000000 else arg(1)
                entry[1] = offset if arg(2) == 0 else (len(entry[0]) + offset if arg(2) == 2 else entry[1] + offset)
                leave(entry[1])
            elif addr == FILE_READ:
                entry = files[arg(0)]
                chunk = entry[0][entry[1]: entry[1] + arg(2)]
                u.mem_write(arg(1), chunk)
                entry[1] += len(chunk)
                leave(len(chunk))
            elif addr == FILE_CLOSE:
                leave(0)
            elif addr == MALLOC:
                leave(VMCDIR_HEAP)
            elif addr == STAT:
                leave(0)
            elif addr == STRLEN:
                leave(len(cstring(arg(0))))
            elif addr == PRINTF:
                out.messages.append(arg(0))
                leave(0)
            elif addr == MEMSET:
                u.mem_write(arg(0), bytes([arg(1) & 0xFF]) * arg(2))
                leave(arg(0))
            elif addr == MEMCPY:
                to, chunk = arg(0), bytes(u.mem_read(arg(1), arg(2)))
                u.mem_write(to, chunk)
                if not (stack - 0x4000 <= to < stack + 0x1000 or VMCDIR_HEAP <= to < VMCDIR_HEAP + 0x100000):
                    out.copies.append((to, chunk))
                    if to in VMCDIR_PATHS:
                        out.paths[to] = chunk.split(b"\0")[0]
                leave(to)
            elif not BASE <= addr < LIMIT:
                raise RuntimeError("left the image at %#x" % addr)
            else:
                word = struct.unpack_from("<I", image, addr - BASE)[0]
                op = word >> 26
                if op in widths and (word >> 21) & 31 == 28:
                    out.flags[_sx16(word & 0xFFFF)] = ee.get((word >> 16) & 31) & ((1 << widths[op]) - 1)
                ee.step(addr, word)
        except Exception as exc:
            failure.append(exc)
            u.emu_stop()

    uc.hook_add(UC_HOOK_CODE, hook)
    uc.emu_start(VMCDIR, 0xFFFFFFFF, count=20_000_000)
    if failure:
        raise failure[0]
    if not done:
        raise RuntimeError("the VMCDIR.TXT reader did not return")
    value = uc.reg_read(R.UC_MIPS_REG_V0) & 0xFFFFFFFF
    out.result = value - (1 << 32) if value & 0x80000000 else value
    return out


def main(argv):
    if argv and argv[0] == "--vmcdir":
        for text in argv[1:]:
            text = text.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t").replace("\\0", "\0")
            print("== %r" % text)
            print("   %r" % vmcdir(text))
        return
    for text in argv:
        text = text.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t").replace("\\0", "\0")
        scan = scan_commands(text, usb_delay=0xEE)
        print("== %r" % text)
        for offset, name, length, effects in scan.events:
            print("   command at %d: %s, %d bytes, %d effects" % (offset, name, length, effects))
        for offset, columns in scan.skips:
            print("   cheat code at %d: %d columns" % (offset, columns))
        for width, address, value in scan.writes:
            print("   w%d[%#x]=%#x" % (width, address, value))
        for call in scan.calls:
            print("   call %s %r" % (call[0], call[1:]))
        print("   gp stores %s, 0x100017=%#x (was 0xee)" % (
            {hex(k): hex(v) for k, v in scan.flags.items()}, scan.usb_delay))


if __name__ == "__main__":
    main(sys.argv[1:])
