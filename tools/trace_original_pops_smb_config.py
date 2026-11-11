#!/usr/bin/env python3
"""Run POPStarter r13's own SMB configuration code (external input only).

POPStarter's launch function reads two text files from a memory card on an
SB. launch, IPCONFIG.DAT and SMBCONFIG.DAT, and turns them into the argument
block for its network module and the three structures it later hands to the
SMB driver. This runs those blocks of the original as shipped, under
Unicorn, with POPSTARTER MAIN mapped at its own address:

  scan      0x8714bc..0x871658  SB. test of argv[0]
            0x871830..0x8719c4  XX. test of argv[0] (skipped in SB. mode)
  defaults  0x871788..0x871830  buffers cleared, default user, port, echo
  config    0x8722bc..0x87345c  IPCONFIG.DAT, then SMBCONFIG.DAT
  smap      0x873a1c..0x873bb4  ps2smap.irx read and started
  connect   0x874128..0x8742ec  LOGON, ECHO, OPENSHARE, POPS_IOX.PAK opens

Only what those blocks call is modelled, at the callee's first instruction:
  - printf (0x915708): format address, format and arguments are recorded;
  - the stop function (0x8709f8): the run ends, its caller is recorded;
  - file open/close/read/lseek (0x91ba70, 0x91bb38, 0x91bbb8, 0x91bdc8,
    reached through the four thin wrappers at 0x87c390..0x87c49c, which run
    as shipped): an in-memory file table;
  - memset, memcpy, strlen, strcpy, strncpy (0x9188b8, 0x918808, 0x918e08,
    0x918b30, 0x918c48): the C library meaning. The shipped routines use
    R5900 128-bit instructions Unicorn lacks; library_check() runs the
    shipped strlen/strcpy/strncpy on the in-repo R5900 interpreter and
    compares them with that meaning;
  - the allocator (0x9190c8), the module starter (0x91c248) and the device
    control call (0x9174f8): arguments recorded, a chosen value returned;
  - the R5900 three-operand `mult rd, rs, rt` (the port arithmetic).
No memory-write hook is used; every byte of the data area that differs after
a run is reported instead. Needs POPSTARTER_TEST_ELF. Not a console run, and
nothing here says what an IOP module does with what it is given.
"""
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_original_pops_io import decode_main  # noqa: E402

BASE = 0x870000
GP = 0x9B68F0
MEM_SIZE = 0x02000000
FRAME = 0x01E00000          # the launch function's frame (0x1630 bytes)
FRAME_SIZE = 0x1630
HEAP = 0x01A00000
DATA_END = 0x00A00000       # end of the area cleared and compared per run

SCAN_SB = (0x8714BC, 0x871658)
SCAN_XX = (0x871830, 0x8719C4)
DEFAULTS = (0x871788, 0x871830)
CONFIG = (0x8722BC, 0x87345C)
SMAP = (0x873A1C, 0x873BB4)
CONNECT = (0x874128, 0x8742EC)

PRINTF, FATAL = 0x915708, 0x8709F8
MEMCPY, MEMSET, STRCPY, STRNCPY, STRLEN = 0x918808, 0x9188B8, 0x918B30, 0x918C48, 0x918E08
FIO_OPEN, FIO_CLOSE, FIO_READ, FIO_LSEEK = 0x91BA70, 0x91BB38, 0x91BBB8, 0x91BDC8
ALLOC, START_MODULE, DEVCTL = 0x9190C8, 0x91C248, 0x9174F8
STUBS = (PRINTF, FATAL, MEMCPY, MEMSET, STRCPY, STRNCPY, STRLEN, FIO_OPEN, FIO_CLOSE,
         FIO_READ, FIO_LSEEK, ALLOC, START_MODULE, DEVCTL)
WRAPPERS = (0x87C390, 0x87C4A0)   # open/close/read/lseek pass-throughs, run as shipped

# Frame slots (offsets from $fp) and globals (offsets from $gp).
F_ARGV = 0x14
F_IP_TEXT, F_IP_LEN, F_IP_ABSENT = 0x30, 0x11C4, 0x10C8
F_SMB_TEXT, F_SMB_LEN = 0xB0, 0x1118
F_USER_SET, F_PASS_SET, F_SHAREPASS_SET = 0x10CC, 0x10D0, 0x10D4
G_MASS, G_SMB, G_QUIET, G_VERBOSE_SET = 0x3448, 0x3888, 0x38B0, 0x3858
G_LOGON, LOGON_SIZE = 0x3980, 0x218       # server[16] port user[256] password[256] type
G_SHARE, SHARE_SIZE = 0x3500, 0x204       # share[256] password[256] type
G_ECHO, ECHO_SIZE = 0x3710, 0x104         # text[256] length
G_FOLDER_CHECKED, G_CONNECTED = 0x3868, 0x3450

# Format strings the two readers print before stopping, by address.
MESSAGES = {
    0x9AF2E8: "ip-size-mc0", 0x9AF338: "ip-size-mc1", 0x9AF388: "ip-syntax",
    0x9AF3C0: "smb-size-mc0", 0x9AF410: "smb-size-mc1", 0x9AF440: "smb-missing",
    0x9AF498: "smb-no-share", 0x9AF4D0: "smb-server-length", 0x9AF500: "smb-bad-port",
}

IP_PATHS = ("mc0:/POPSTARTER/IPCONFIG.DAT", "mc1:/POPSTARTER/IPCONFIG.DAT")
SMB_PATHS = ("mc0:/POPSTARTER/SMBCONFIG.DAT", "mc1:/POPSTARTER/SMBCONFIG.DAT")
SMAP_PATHS = ("mc0:/POPSTARTER/ps2smap.irx", "mc1:/POPSTARTER/ps2smap.irx")

_IMAGE = None


def image():
    global _IMAGE
    if _IMAGE is None:
        _IMAGE = bytes(decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes()))
    return _IMAGE


def _word(addr):
    return struct.unpack_from("<I", image(), addr - BASE)[0]


def _is_branch(word):
    op, fn = word >> 26, word & 63
    return op in (1, 2, 3, 4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17) or (op == 0 and fn in (8, 9))


def _mult_sites(start, end):
    """Addresses of the three-operand mult/multu in a block."""
    sites = []
    for addr in range(start, end, 4):
        word = _word(addr)
        if word >> 26 == 0 and (word & 63) in (0x18, 0x19) and (word >> 11) & 31:
            if _is_branch(_word(addr - 4)):
                raise RuntimeError("three-operand mult in a delay slot at %#x" % addr)
            sites.append(addr)
    return sites


def call_targets(start, end):
    """Every jal target in a block (to prove the stub list is complete)."""
    return sorted({(_word(a) & 0x03FFFFFF) << 2 for a in range(start, end, 4)
                   if _word(a) >> 26 == 3})


class Emulator:
    """One Unicorn instance, reused; reset() restores the image and clears
    the data area, the frame and the heap."""

    def __init__(self):
        from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
        self.uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
        try:
            self.uc.ctl_set_cpu_model(5)  # UC_CPU_MIPS64_5KF, as the other tracers
        except Exception:
            pass
        self.uc.mem_map(0, MEM_SIZE)
        for addr in STUBS:
            self.uc.hook_add(UC_HOOK_CODE, self._stub, begin=addr, end=addr)
        blocks = (SCAN_SB, SCAN_XX, DEFAULTS, CONFIG, SMAP, CONNECT)
        self.mults = sorted({a for s, e in blocks for a in _mult_sites(s, e)})
        for addr in self.mults:
            self.uc.hook_add(UC_HOOK_CODE, self._mult, begin=addr, end=addr)
        for _start, end in blocks:
            self.uc.hook_add(UC_HOOK_CODE, self._end, begin=end, end=end)
        for start, end in blocks + (WRAPPERS,):
            for target in call_targets(start, end):
                inside = any(s <= target < e for s, e in blocks + (WRAPPERS,))
                if target not in STUBS and not inside:
                    raise RuntimeError("unmodelled call target %#x in %#x..%#x" % (target, start, end))
        self.state = None
        self.reset()

    # -- machine helpers
    def _r(self, name):
        from unicorn import mips_const as R
        return getattr(R, "UC_MIPS_REG_" + name)

    def reg(self, name):
        return self.uc.reg_read(self._r(name)) & 0xFFFFFFFF

    def u32(self, addr):
        return struct.unpack("<I", self.uc.mem_read(addr, 4))[0]

    def s32(self, addr):
        return struct.unpack("<i", self.uc.mem_read(addr, 4))[0]

    def put32(self, addr, value):
        self.uc.mem_write(addr, struct.pack("<I", value & 0xFFFFFFFF))

    def cstr(self, addr, limit=0x2000):
        raw = bytes(self.uc.mem_read(addr, limit))
        return raw[:raw.index(0)] if 0 in raw else raw

    def _ret(self, value):
        self.uc.reg_write(self._r("V0"), value & 0xFFFFFFFFFFFFFFFF)
        self.uc.reg_write(self._r("PC"), self.uc.reg_read(self._r("RA")))

    # -- hooks
    def _mult(self, uc, addr, _size, _user):
        word = self.u32(addr)
        rs, rt, rd = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
        regs = [self._r(str(i)) for i in (rs, rt, rd)]
        a, b = (uc.reg_read(r) & 0xFFFFFFFF for r in regs[:2])
        if word & 63 == 0x18:
            a = a - (1 << 32) if a & 0x80000000 else a
            b = b - (1 << 32) if b & 0x80000000 else b
        prod = (a * b) & 0xFFFFFFFFFFFFFFFF

        def sx(v):
            v &= 0xFFFFFFFF
            return v | 0xFFFFFFFF00000000 if v & 0x80000000 else v
        uc.reg_write(self._r("LO"), sx(prod))
        uc.reg_write(self._r("HI"), sx(prod >> 32))
        uc.reg_write(regs[2], sx(prod))
        uc.reg_write(self._r("PC"), addr + 4)

    def _end(self, uc, addr, _size, _user):
        if addr == self.state["end"]:
            self.state["ended"] = True
            uc.emu_stop()

    def _stub(self, uc, addr, _size, _user):
        st = self.state
        a0, a1, a2, a3 = (self.reg(n) for n in ("A0", "A1", "A2", "A3"))
        ra = self.reg("RA")
        log = st["log"]
        if addr == FATAL:
            st["fatal"] = ra - 8
            uc.emu_stop()
        elif addr == PRINTF:
            fmt = self.cstr(a0).decode("latin-1")
            values, args = [], [a1, a2, a3]
            pos = 0
            while "%" in fmt[pos:] and args:
                pos = fmt.index("%", pos) + 1
                kind = fmt[pos:pos + 1]
                value = args.pop(0)
                if kind == "s":
                    values.append(self.cstr(value))
                elif kind == "d":
                    values.append(value - (1 << 32) if value & 0x80000000 else value)
                else:
                    values.append(value)
            log.append(("print", a0, fmt, tuple(values)))
            self._ret(0)
        elif addr == MEMSET:
            if a2 > 0x100000:
                st["error"] = "memset length %#x" % a2
                uc.emu_stop()
                return
            if a2:
                uc.mem_write(a0, bytes([a1 & 0xFF]) * a2)
            log.append(("memset", a0, a1 & 0xFF, a2))
            self._ret(a0)
        elif addr == MEMCPY:
            if a2:
                uc.mem_write(a0, bytes(uc.mem_read(a1, a2)))
            log.append(("memcpy", a0, a1, a2))
            self._ret(a0)
        elif addr == STRLEN:
            self._ret(len(self.cstr(a0)))
        elif addr == STRCPY:
            text = self.cstr(a1)
            uc.mem_write(a0, text + b"\0")
            log.append(("strcpy", a0, len(text) + 1, ra - 8))
            self._ret(a0)
        elif addr == STRNCPY:
            text = self.cstr(a1)[:a2]
            if a2:
                uc.mem_write(a0, text + b"\0" * (a2 - len(text)))
            log.append(("strncpy", a0, a2, ra - 8))
            self._ret(a0)
        elif addr == FIO_OPEN:
            path = self.cstr(a0).decode("latin-1")
            data = st["files"].get(path)
            fd = st["open_result"](path) if data is None else st["next_fd"]
            if data is not None:
                st["next_fd"] += 1
                st["fds"][fd] = [bytes(data), 0]
            log.append(("open", path, a1, fd))
            self._ret(fd)
        elif addr == FIO_LSEEK:
            entry = st["fds"][a0]
            offset = a1 - (1 << 32) if a1 & 0x80000000 else a1
            pos = offset if a2 == 0 else (len(entry[0]) + offset if a2 == 2 else entry[1] + offset)
            entry[1] = pos
            log.append(("lseek", a0, offset, a2, pos))
            self._ret(pos)
        elif addr == FIO_READ:
            entry = st["fds"][a0]
            chunk = entry[0][entry[1]:entry[1] + a2]
            if chunk:
                uc.mem_write(a1, chunk)
            entry[1] += len(chunk)
            log.append(("read", a0, a1, a2, len(chunk)))
            self._ret(len(chunk))
        elif addr == FIO_CLOSE:
            st["fds"].pop(a0, None)
            log.append(("close", a0))
            self._ret(0)
        elif addr == ALLOC:
            here = st["heap"]
            st["heap"] = (here + a0 + 0x3F) & ~0x3F
            log.append(("alloc", a0, here))
            self._ret(here)
        elif addr == START_MODULE:
            t0 = self.reg("T0")
            block = bytes(uc.mem_read(a3, a2)) if a3 and a2 else b""
            log.append(("start", a0, a1, a2, a3, t0, block))
            self._ret(st["start_result"])
        elif addr == DEVCTL:
            t0, t1 = self.reg("T0"), self.reg("T1")
            name = self.cstr(a0).decode("latin-1")
            block = bytes(uc.mem_read(a2, a3)) if a2 and a3 else b""
            result = st["devctl_result"](a1)
            log.append(("devctl", name, a1, a2, a3, t0, t1, block, result))
            self._ret(result)

    # -- runs
    def reset(self):
        uc = self.uc
        main = image()
        uc.mem_write(BASE, main)
        uc.mem_write(BASE + len(main), b"\0" * (DATA_END - BASE - len(main)))
        uc.mem_write(FRAME - 0x1000, b"\0" * (FRAME_SIZE + 0x2000))
        self.state = {
            "log": [], "files": {}, "fds": {}, "next_fd": 3, "heap": HEAP, "fatal": None,
            "error": None, "end": None, "ended": False, "open_result": lambda path: -2, "start_result": 1,
            "devctl_result": lambda cmd: 0,
        }

    def run(self, block, limit=20_000_000):
        """Run one block from its start until its end, or the stop function."""
        uc, st = self.uc, self.state
        start, end = block
        st["fatal"] = None
        st["end"], st["ended"] = end, False
        uc.reg_write(self._r("GP"), GP)
        uc.reg_write(self._r("FP"), FRAME)
        uc.reg_write(self._r("SP"), FRAME)
        uc.reg_write(self._r("RA"), 0)
        uc.emu_start(start, 0xFFFFFFFF, count=limit)
        if st["error"]:
            raise RuntimeError(st["error"])
        if st["fatal"] is None and not st["ended"]:
            raise RuntimeError("block %#x..%#x did not end (pc %#x)" % (start, end, self.reg("PC")))
        return st["fatal"]

    def data(self):
        return bytes(self.uc.mem_read(BASE + len(image()), DATA_END - BASE - len(image())))

    def gp_bytes(self, offset, size):
        return bytes(self.uc.mem_read(GP + offset, size))


def scan(emu, argv0, quiet=1):
    """The original's SB. and XX. tests of argv[0]. Returns the three flags
    {mass, smb, quiet} it leaves; quiet is the profile's starting value (1 on
    the MAIN profile)."""
    emu.reset()
    uc = emu.uc
    text = bytes(argv0) + b"\0"
    uc.mem_write(HEAP, struct.pack("<I", HEAP + 0x100))
    uc.mem_write(HEAP + 0x100, text)
    emu.put32(FRAME + F_ARGV, HEAP)
    emu.put32(GP + G_QUIET, quiet)
    emu.run(SCAN_SB)
    if not emu.u32(GP + G_SMB):     # the XX. test is skipped in SB. mode (0x871834)
        emu.run(SCAN_XX)
    return {"mass": emu.u32(GP + G_MASS), "smb": emu.u32(GP + G_SMB),
            "quiet": emu.u32(GP + G_QUIET)}


def _split_logon(raw):
    return {"server": raw[:16], "port": struct.unpack_from("<i", raw, 16)[0],
            "user": raw[20:276], "password": raw[276:532],
            "password_type": struct.unpack_from("<i", raw, 532)[0]}


def _split_share(raw):
    return {"share": raw[:256], "share_password": raw[256:512],
            "share_password_type": struct.unpack_from("<i", raw, 512)[0]}


def configure(emu, files, sentinel=0):
    """Run the defaults block and the two readers with `files` ({path:
    bytes}) on the cards, in SB. mode with messages on (what the SB. test
    leaves, see scan()). `sentinel` fills the data area around the three
    structures before the readers run, so that a write outside them shows
    even when it stores a zero.

    Returns a dict:
      fatal        None, or the call site of the stop function
      message      key from MESSAGES of the last message before the stop
      prints       [(format address, format, values)]
      opens        [(path, mode, result)]
      ip_absent    1 when neither IPCONFIG.DAT opened
      ip_length    the length later passed with the block to ps2smap.irx
      ip_block     the 128-byte buffer the block is taken from
      logon, share, echo   the three structures, raw
      server, port, user, password, password_type, share, share_password,
      share_password_type  fields of logon and share
      copies       [(kind, destination, bytes written, call site)] of the
                   strcpy/strncpy calls made by the readers
      outside      {address: byte} of every data byte outside the three
                   structures that the readers changed
    """
    emu.reset()
    st = emu.state
    emu.put32(GP + G_MASS, 1)
    emu.put32(GP + G_SMB, 3)
    emu.put32(GP + G_QUIET, 0)
    emu.run(DEFAULTS)
    st["files"] = dict(files)
    st["log"] = []
    if sentinel:
        fill = bytes([sentinel])
        base = BASE + len(image())
        keep = [(GP + G_LOGON, LOGON_SIZE), (GP + G_SHARE, SHARE_SIZE), (GP + G_ECHO, ECHO_SIZE)]
        flags = [GP + G_MASS, GP + G_SMB, GP + G_QUIET]
        area = bytearray(emu.data())
        saved = {a: area[a - base:a - base + n] for a, n in keep}
        saved.update({a: area[a - base:a - base + 4] for a in flags})
        area[GP + 0x3400 - base:GP + 0x6000 - base] = fill * 0x2C00
        for a, chunk in saved.items():
            area[a - base:a - base + len(chunk)] = chunk
        emu.uc.mem_write(base, bytes(area))
    before = emu.data()
    fatal = emu.run(CONFIG)
    after = emu.data()
    base = BASE + len(image())
    inside = [(GP + G_LOGON, LOGON_SIZE), (GP + G_SHARE, SHARE_SIZE)]
    outside = {}
    for chunk in range(0, len(before), 4096):
        if before[chunk:chunk + 4096] == after[chunk:chunk + 4096]:
            continue
        for i in range(chunk, min(chunk + 4096, len(before))):
            if before[i] != after[i]:
                addr = base + i
                if not any(a <= addr < a + n for a, n in inside):
                    outside[addr] = after[i]
    log = st["log"]
    prints = [(e[1], e[2], e[3]) for e in log if e[0] == "print"]
    message = None
    if fatal is not None:
        for addr, _fmt, _values in reversed(prints):
            if addr in MESSAGES:
                message = MESSAGES[addr]
                break
    logon = emu.gp_bytes(G_LOGON, LOGON_SIZE)
    share = emu.gp_bytes(G_SHARE, SHARE_SIZE)
    out = {
        "fatal": fatal, "message": message, "prints": prints,
        "opens": [(e[1], e[2], e[3]) for e in log if e[0] == "open"],
        "ip_absent": emu.u32(FRAME + F_IP_ABSENT),
        "ip_length": emu.s32(FRAME + F_IP_LEN),
        "ip_block": bytes(emu.uc.mem_read(FRAME + F_IP_TEXT, 0x80)),
        "logon": logon, "share_raw": share, "echo": emu.gp_bytes(G_ECHO, ECHO_SIZE),
        "copies": [e for e in log if e[0] in ("strcpy", "strncpy")],
        "outside": outside,
    }
    out.update(_split_logon(logon))
    out.update(_split_share(share))
    return out


def start_smap(emu, ip_text, module=b"\x7fELF" + b"\0" * 60, card=0):
    """Run the readers with only IPCONFIG.DAT (`ip_text`, None for no file)
    and a valid SMBCONFIG.DAT, then the block that reads ps2smap.irx and
    starts it. Returns (argument length, argument pointer is NULL, argument
    bytes, module size passed), or None when the readers stopped first."""
    files = {SMB_PATHS[0]: b"192.168.0.2 SHARE"}
    if ip_text is not None:
        files[IP_PATHS[card]] = bytes(ip_text)
    emu.reset()
    st = emu.state
    emu.put32(GP + G_MASS, 1)
    emu.put32(GP + G_SMB, 3)
    emu.run(DEFAULTS)
    st["files"] = dict(files)
    st["files"][SMAP_PATHS[card]] = bytes(module)
    st["log"] = []
    if emu.run(CONFIG) is not None:
        return None
    st["log"] = []
    emu.run(SMAP)
    calls = [e for e in st["log"] if e[0] == "start"]
    if len(calls) != 1:
        raise RuntimeError("expected one module start, saw %d" % len(calls))
    _k, _ptr, size, arg_len, arg_ptr, _t0, block = calls[0]
    return arg_len, arg_ptr == 0, block, size


def connect(emu, logon=0, echo=0, openshare=0, opens_before_success=0):
    """Run the connect block. The three device-control results are given;
    the POPS_IOX.PAK open fails `opens_before_success` times, then succeeds
    (None: never). Returns a dict:
      calls      [(device, command, size, bytes, input pointer is the
                 structure's own address)] of the device-control calls
      opens      [(path, mode)] of the POPS_IOX.PAK opens
      fatal      None, or the call site of the stop function
      prints     [(format address, format, values)]
      connected, folder_checked   the two flags set on success"""
    emu.reset()
    st = emu.state
    emu.put32(GP + G_MASS, 1)
    emu.put32(GP + G_SMB, 3)
    emu.run(DEFAULTS)
    st["log"] = []
    results = {0xC0DE0002: logon, 0xC0DE0007: echo, 0xC0DE0005: openshare}
    st["devctl_result"] = lambda cmd: results[cmd]
    count = [0]

    def open_result(path):
        count[0] += 1
        if opens_before_success is not None and count[0] > opens_before_success:
            return 5
        return -2
    st["open_result"] = open_result
    st["fds"][5] = [b"", 0]
    fatal = emu.run(CONNECT, limit=5_000_000)
    log = st["log"]
    home = {0xC0DE0002: GP + G_LOGON, 0xC0DE0007: GP + G_ECHO, 0xC0DE0005: GP + G_SHARE}
    calls = [(e[1], e[2], e[4], e[7], e[3] == home.get(e[2]), (e[5], e[6]))
             for e in log if e[0] == "devctl"]
    return {"calls": calls, "opens": [(e[1], e[2]) for e in log if e[0] == "open"],
            "fatal": fatal, "prints": [(e[1], e[2], e[3]) for e in log if e[0] == "print"],
            "connected": emu.u32(GP + G_CONNECTED),
            "folder_checked": emu.u32(GP + G_FOLDER_CHECKED)}


def library_check(cases):
    """Run the shipped strlen, strcpy and strncpy on the in-repo R5900
    interpreter for each (text, count, alignments) case and compare with the
    C library meaning the Unicorn stubs use. Returns the number of
    comparisons made; raises on the first difference."""
    from r5900_mini import Machine, M64, M32

    class Mmi(Machine):
        def execute(self, word, pc):
            op = word >> 26
            rs, rt, rd, sa, fn = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31, (word >> 6) & 31, word & 63
            if op == 0 and fn == 0x2F:      # dsubu
                self.set_lo(rd, self.lo(rs) - self.lo(rt))
                return None
            if op == 0x1C and (fn, sa) != (0x09, 0x0E):
                a, b = self.gpr[rs], self.gpr[rt]
                if (fn, sa) == (0x08, 0x09):      # psubb
                    v = sum((((a >> i) - (b >> i)) & 0xFF) << i for i in range(0, 128, 8))
                elif (fn, sa) == (0x29, 0x13):    # pnor
                    v = ~(a | b)
                elif (fn, sa) == (0x09, 0x12):    # pand
                    v = a & b
                elif (fn, sa) == (0x29, 0x0E):    # pcpyud
                    v = (a >> 64) | ((b >> 64) << 64)
                else:
                    raise NotImplementedError("MMI %#010x at %#x" % (word, pc))
                self.set_full(rd, v)
                return None
            return Machine.execute(self, word, pc)

    main = image()
    done = 0
    for text, count, src_align, dst_align in cases:
        text = bytes(text)
        if 0 in text:
            raise ValueError("no NUL inside a case")
        for name in ("strlen", "strcpy", "strncpy"):
            m = Mmi()
            m.record = False
            m.write(0x918000, main[0x918000 - BASE:0x919000 - BASE])
            src = 0x01000000 + src_align
            dst = 0x01100000 + dst_align
            m.write(0x01000000 - 64, b"\xEE" * (len(text) + 256))
            m.write(src, text + b"\0")
            m.write(0x01100000 - 64, b"\xDD" * (max(len(text), count) + 256))
            m.set_lo(31, 0x00100000)
            if name == "strlen":
                m.set_lo(4, src)
                m.run(STRLEN, 0x00100000, limit=2_000_000)
                if m.lo(2) & M32 != len(text):
                    raise AssertionError("strlen(%r) = %d" % (text, m.lo(2)))
            else:
                m.set_lo(4, dst)
                m.set_lo(5, src)
                m.set_lo(6, count)
                m.run(STRCPY if name == "strcpy" else STRNCPY, 0x00100000, limit=2_000_000)
                if name == "strcpy":
                    want = text + b"\0"
                else:
                    want = text[:count] + b"\0" * (count - len(text[:count]))
                span = max(len(text), count) + 192
                got = m.read(0x01100000 - 64, span)
                model = bytearray(b"\xDD" * span)
                model[64 + dst_align:64 + dst_align + len(want)] = want
                if got != bytes(model):
                    raise AssertionError("%s(%r, %d) align %d/%d differs" %
                                         (name, text, count, src_align, dst_align))
                if m.lo(2) & M64 != dst:
                    raise AssertionError("%s return value" % name)
            done += 1
    return done


def main(argv):
    emu = Emulator()
    for arg in argv:
        text = arg.encode("latin-1").decode("unicode_escape").encode("latin-1")
        out = configure(emu, {SMB_PATHS[0]: text})
        print("== %r" % text)
        for key in ("fatal", "message", "server", "port", "user", "password", "password_type",
                    "share", "share_password", "share_password_type"):
            value = out[key]
            if isinstance(value, bytes):
                value = value.split(b"\0")[0]
            print("   %-20s %r" % (key, value))
        print("   outside writes       %d" % len(out["outside"]))


if __name__ == "__main__":
    main(sys.argv[1:])
