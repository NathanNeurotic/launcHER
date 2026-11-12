#!/usr/bin/env python3
"""Run POPStarter r13's physical-disc code under Unicorn (external inputs only).

In the original a physical PS1 disc is not a mode anyone selects: it is what
the launch function does when no VCD was found (flag gp+0x3410 == 1 and its
"VCD found" local, 0x10b8($fp), still 0). This runs, as shipped:

  block        0x8766fc..0x876a40  the drive probe and its POPS writes
  scan         0x870150..0x870230  the IOP module scan for a name "cdvd_*"
  fingerprint  0x8ff0e4..0x914930  FUN_008ff0e4: the built-in list's 144 bytes
                                   (from a VCD, or from sectors 16 and 22) and
                                   the whole compare chain
  cdexit       0x8774c4..0x8774dc  sceCdInit(5) before the IOP work
  banner       0x878ab4..0x878d5c  the "POPS ENVIRONMENT" lines and the clear
                                   of POPS's name buffer 0x4f8000
  discs        0x8d5cf8..0x8d6b74  FUN_008d5cf8, the DISCS.TXT reader (only
                                   up to its first file call)
  probe12      0x875678..0x8757ec  the VCD probe of launch types 1 and 2
  probe0       0x875ab0..0x875fa4  the VCD probe of launch type 0
  probe3       0x875fa4..0x8766fc  the VCD probe of launch type 3 (XX., SB.)
                                   (the probes are where the flag is set to 1)

POPSTARTER MAIN and the POPS core are mapped at their own addresses. Only the
callees are modelled, by address:
  - the EE libcdvd entry points (sceCdInit 0x917b18, sceCdSync 0x9181c0,
    sceCdStatus 0x918478, sceCdGetDiskType 0x9183d8, sceCdDiskReady 0x917cc0,
    sceCdRead 0x917f80): arguments recorded, results chosen by the caller;
    a successful read stores the caller's 2,048 bytes for that LBA, a failed
    one stores nothing;
  - SifLoadModule 0x91c200, printf 0x915708, malloc 0x9190c8, memcpy
    0x918808 and memset 0x9188b8 (both use R5900 instructions Unicorn lacks);
  - the two calls the module scan makes (next module 0x914aa8, read IOP
    memory 0x914998): a caller-supplied list of module names;
  - file calls (mount 0x915e50, umount 0x915f50, open 0x916758 / 0x91ba70,
    close 0x916878 / 0x91bb38, lseek 0x916c08 / 0x91bdc8, read 0x9169b0 /
    0x91bbb8) and strlen 0x918e08: an in-memory table;
  - the fatal exit 0x8709f8 and the pfs unmount helper 0x8d7ff8: recorded;
  - the list entry dispatcher 0x8e00d0: its (id, mode) is recorded.
Everything else the windows execute is the original's own code, including its
two poke helpers (0x87c298 byte, 0x87c300 word) and the four thin file
wrappers after them (0x87c390..0x87c498). A call to anything not listed ends
the run with "left".

No memory-write hook is used: memory is compared after the run, so a result
lists every byte that changed anywhere outside the stack. Needs
POPSTARTER_TEST_ELF and POPS_TEST_ELF. Nothing here is a console run, and
the modelled callees say nothing about what a PS2 drive returns.
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
CORE_BASE = 0x200000
MEM_SIZE = 0x02000000
FRAME = 0x1E00000        # the launch function's $fp (its locals are above it)
FRAME_SPAN = 0x2000
STACK_LOW = FRAME - 0x10000
SCRATCH = 0x1D00000      # modelled IOP names, malloc results, string arguments
SCRATCH_SPAN = 0x20000
STOP = 0x1FF0000

# windows run as shipped: name -> (first instruction, end exclusive)
WINDOWS = {
    "block": (0x8766FC, 0x876A40),
    "scan": (0x870150, 0x870230),
    "helpers": (0x87C298, 0x87C4A0),   # byte/word pokes and four thin file wrappers
    "fingerprint": (0x8FF0E4, 0x914930),
    "cdexit": (0x8774C4, 0x8774DC),
    "banner": (0x878AB4, 0x878D5C),
    "discs": (0x8D5CF8, 0x8D6B74),
    "probe12": (0x875678, 0x8757EC),
    "probe0": (0x875AB0, 0x875FA4),
    "probe3": (0x875FA4, 0x8766FC),
}

NATIVES = {
    0x915708: "printf", 0x91C200: "SifLoadModule",
    0x917B18: "sceCdInit", 0x9181C0: "sceCdSync", 0x918478: "sceCdStatus",
    0x9183D8: "sceCdGetDiskType", 0x917CC0: "sceCdDiskReady", 0x917F80: "sceCdRead",
    0x918808: "memcpy", 0x9188B8: "memset", 0x9190C8: "malloc",
    0x914AA8: "smod_next", 0x914998: "smem_read",
    0x8D7FF8: "umount_pfs", 0x8709F8: "fatal_exit", 0x8E00D0: "apply_entry",
    0x915E50: "mount", 0x915F50: "umount", 0x916758: "open", 0x916878: "close",
    0x916C08: "lseek", 0x9169B0: "read", 0x91BDC8: "lseek_mass", 0x91BBB8: "read_mass",
    0x91BA70: "open_mass", 0x91BB38: "close_mass", 0x918E08: "strlen",
}
FINGERPRINT = 0x8FF0E4
FIRST_COMPARE = 0x8FF33C  # the 144 bytes are complete here

# gp-relative words
G_FLAG = 0x3410          # 1: no VCD found, physical disc
G_LAUNCH_TYPE = 0x3414
G_MASS = 0x3448          # 1 on XX. and SB. launches
G_AUTO = 0x385C          # built-in list level (preset byte 0x10002f)
G_QUIET = 0x38B0         # 1: no printf
G_LIST_ID = 0x38D8       # entry the compare chain found
G_SMB = 0x3888
G_CDVD_SEEN = -0x7FDC    # 0x9ae914: the scan found a "cdvd_*" module
G_REGION = 0x3CB0        # 0x9ba5a0: the four licence letters
G_SECTOR = 0x3CC0        # 0x9ba5b0: sector buffer, 0x1260 bytes cleared
G_READ_MODE = 0x3978     # 0x9ba268: sceCdRead mode, set at 0x870c20..0x870c34
G_SIG = 0x3970           # pointer to the 0x120-byte fingerprint buffer
G_VCD_PATH = 0x3470      # 0x9b9d60: the path the probes open
L_VCD_FOUND = 0x10B8     # locals of the launch function
L_STATUS = 0x1C
L_DISC_TYPE = 0x10D8
L_ARGV = 0x14
L_FD = 0x10B4

ALWAYS_LIVE_SRC, ALWAYS_LIVE_DST, ALWAYS_LIVE_SIZE = 0x983150, 0x232790, 0x738
SECTOR_SIZE = 2048


def s32(value):
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


def changed_runs(before, after):
    """[(address, bytes after)] for every run of bytes that differ."""
    out, start, prev = [], None, None
    for off in range(0, len(before), 0x1000):
        if before[off:off + 0x1000] == after[off:off + 0x1000]:
            continue
        for i in range(off, min(off + 0x1000, len(before))):
            if before[i] != after[i]:
                if start is None:
                    start = prev = i
                elif i != prev + 1:
                    out.append((start, after[start:prev + 1]))
                    start = i
                prev = i
    if start is not None:
        out.append((start, after[start:prev + 1]))
    return out


class Emulator:
    """One Unicorn instance, reused: every run starts from the same memory
    (MAIN as unpacked, the POPS core with the original's always-live block
    copied in as its launch function does at 0x874754, everything else 0)."""

    def __init__(self, core=None, main=None):
        from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
        if main is None:
            main = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
        if core is None:
            core = core_image(os.environ["POPS_TEST_ELF"])
        self.main = bytes(main)
        self.pristine_core = bytes(core)
        self.core = self.with_always_live(core)
        self.uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
        try:
            self.uc.ctl_set_cpu_model(5)  # UC_CPU_MIPS64_5KF, as the other tracers
        except Exception:
            pass
        self.uc.mem_map(0, MEM_SIZE)
        # Per-instruction callbacks only outside the windows: inside them the
        # original runs unobserved (the compare chain is about a million
        # instructions for a late entry).
        spans = sorted(WINDOWS.values())
        edge = BASE
        for lo, hi in spans:
            if lo > edge:
                self.uc.hook_add(UC_HOOK_CODE, self._code, begin=edge, end=lo - 4)
            edge = hi
        self.uc.hook_add(UC_HOOK_CODE, self._code, begin=edge, end=BASE + len(self.main))
        self.uc.hook_add(UC_HOOK_CODE, self._code, begin=STOP, end=STOP)
        # Single addresses inside the windows that still need a callback:
        # every window's end (one window may end where the next begins, and
        # emu_start's own end address is not honoured by code translated in
        # an earlier run), the fingerprint function's entry (a window and
        # also a callee of the others) and its first compare.
        self.inside = {hi for _, hi in spans} | {FINGERPRINT, FIRST_COMPARE}
        for addr in sorted(self.inside):
            if any(lo <= addr < hi for lo, hi in spans):
                self.uc.hook_add(UC_HOOK_CODE, self._code, begin=addr, end=addr)
        self.st = None

    def with_always_live(self, core):
        """The launch function copies 0x738 bytes from 0x983150 to POPS
        0x232790 (0x874754..0x874764) long before the block runs."""
        out = bytearray(core)
        src = ALWAYS_LIVE_SRC - BASE
        dst = ALWAYS_LIVE_DST - CORE_BASE
        out[dst:dst + ALWAYS_LIVE_SIZE] = self.main[src:src + ALWAYS_LIVE_SIZE]
        return bytes(out)

    # -- helpers ---------------------------------------------------------
    def _ret(self, value):
        from unicorn.mips_const import UC_MIPS_REG_PC, UC_MIPS_REG_RA, UC_MIPS_REG_V0
        self.uc.reg_write(UC_MIPS_REG_V0, value & 0xFFFFFFFFFFFFFFFF)
        self.uc.reg_write(UC_MIPS_REG_PC, self.uc.reg_read(UC_MIPS_REG_RA))

    def _cstr(self, addr):
        raw = bytes(self.uc.mem_read(addr, 256))
        return raw[:raw.index(0)].decode("latin-1")

    def _w(self, addr, value):
        self.uc.mem_write(addr, struct.pack("<I", value & 0xFFFFFFFF))

    def _r(self, addr):
        return struct.unpack("<I", self.uc.mem_read(addr, 4))[0]

    def _code(self, uc, addr, _size, _user):
        from unicorn.mips_const import (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2,
                                        UC_MIPS_REG_A3)
        st = self.st
        if addr == STOP or addr == st["until"]:
            st["end"] = "returned" if addr == STOP else "end"
            uc.emu_stop()
            return
        name = NATIVES.get(addr)
        if addr == FIRST_COMPARE:
            # the function clears its buffer before it returns
            st["sig"] = bytes(uc.mem_read(self._r(GP + G_SIG), 0x90))
            return
        if addr == FINGERPRINT and st["model_fingerprint"]:
            name = "fingerprint"
        elif addr in self.inside and any(lo <= addr < hi for lo, hi in WINDOWS.values()):
            return
        if name is None:
            st["end"] = "left"
            st["left"] = addr
            uc.emu_stop()
            return
        a = [uc.reg_read(r) & 0xFFFFFFFF for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1,
                                                    UC_MIPS_REG_A2, UC_MIPS_REG_A3)]
        log = st["log"]
        ret = 0
        if name == "printf":
            fmt = self._cstr(a[0])
            arg = None
            if "%d" in fmt:
                arg = s32(a[1])
            elif "%s" in fmt:
                arg = self._cstr(a[1])
            log.append(("printf", fmt, arg))
        elif name == "SifLoadModule":
            log.append((name, self._cstr(a[0]), a[1], a[2]))
            ret = st["load_result"]
        elif name == "sceCdInit":
            log.append((name, a[0]))
            ret = st["init_result"]
        elif name == "sceCdSync":
            log.append((name, a[0]))
        elif name == "sceCdStatus":
            log.append((name,))
            ret = st["status"]
        elif name == "sceCdGetDiskType":
            log.append((name,))
            ret = st["disc_type"]
        elif name == "sceCdDiskReady":
            log.append((name, a[0]))
            ret = st["ready_result"]
        elif name == "sceCdRead":
            mode = bytes(uc.mem_read(a[3], 4))
            data = st["sectors"].get(a[0]) if a[1] == 1 else None
            ok = data is not None and a[0] not in st["bad_lbas"]
            if ok:
                uc.mem_write(a[2], bytes(data)[:SECTOR_SIZE])
            log.append((name, a[0], a[1], a[2], mode.hex(), int(ok)))
            ret = 1 if ok else 0
        elif name == "memcpy":
            if a[2] > 0x100000:
                st["end"], st["left"] = "left", addr
                uc.emu_stop()
                return
            if a[2]:
                uc.mem_write(a[0], bytes(uc.mem_read(a[1], a[2])))
            log.append((name, a[0], a[1], a[2]))
            ret = a[0]
        elif name == "memset":
            if a[2] > 0x100000:
                st["end"], st["left"] = "left", addr
                uc.emu_stop()
                return
            if a[2]:
                uc.mem_write(a[0], bytes([a[1] & 0xFF]) * a[2])
            log.append((name, a[0], a[1] & 0xFF, a[2]))
            ret = a[0]
        elif name == "malloc":
            ret = SCRATCH + 0x10000
            # not cleared by malloc: make stale contents visible
            uc.mem_write(ret, b"\xA5" * a[0])
            log.append((name, a[0]))
        elif name == "smod_next":
            mods = st["modules"]
            if a[0] == 0:
                index = 0
            else:
                token = self._r(a[0])
                index = token - 0x800 if token else len(mods)
            if index >= len(mods):
                ret = 0
            else:
                self._w(a[1], 0x800 + index + 1 if index + 1 < len(mods) else 0)
                self._w(a[1] + 4, SCRATCH + index * 0x40)
                ret = 1
            log.append((name, index if ret else None))
        elif name == "smem_read":
            data = bytes(uc.mem_read(a[0], a[2]))
            uc.mem_write(a[1], data)
            log.append((name, data.split(b"\0", 1)[0].decode("latin-1"), a[2]))
            ret = a[2]
        elif name == "umount_pfs":
            log.append((name,))
        elif name == "fatal_exit":
            log.append((name,))
            st["end"] = "fatal"
            uc.emu_stop()
            return
        elif name == "apply_entry":
            log.append((name, a[0], a[1]))
        elif name == "fingerprint":
            log.append((name, s32(a[0]), a[1]))
            ret = 1
        elif name == "mount":
            path = self._cstr(a[1])
            ret = 0 if path in st["partitions"] else -19
            st["mounted"] = path if ret == 0 else None
            log.append((name, self._cstr(a[0]), path, a[2], ret))
        elif name == "umount":
            log.append((name, self._cstr(a[0])))
            st["mounted"] = None
        elif name == "strlen":
            ret = len(self._cstr(a[0]))
        elif name in ("open", "open_mass"):
            path = self._cstr(a[0])
            key = (st["mounted"], path)
            data = st["files"].get(key, st["files"].get(path))
            ret = -2
            if data is not None:
                ret = st["next_fd"]
                st["next_fd"] += 1
                st["fds"][ret] = [bytes(data), 0]
            log.append((name, path, a[1], ret))
        elif name in ("close", "close_mass"):
            log.append((name, s32(a[0])))
            st["fds"].pop(a[0], None)
        elif name in ("lseek", "lseek_mass"):
            entry = st["fds"].get(a[0])
            ret = -9
            if entry is not None and a[2] == 0:
                entry[1] = ret = a[1]
            log.append((name, s32(a[0]), a[1], a[2]))
        elif name in ("read", "read_mass"):
            entry = st["fds"].get(a[0])
            ret = -9
            if entry is not None:
                chunk = entry[0][entry[1]:entry[1] + a[2]]
                if chunk:
                    uc.mem_write(a[1], chunk)
                entry[1] += len(chunk)
                ret = len(chunk)
            log.append((name, s32(a[0]), a[1], a[2], ret))
        self._ret(ret)

    # -- one run -----------------------------------------------------------
    def run(self, start, until=None, *, core=None, gp=(), frame=(), strings=(),
            status=0, disc_type=0x10, sectors=None, bad_lbas=(), modules=(),
            load_result=1, init_result=1, ready_result=2, files=None,
            partitions=(), fds=None, model_fingerprint=True, args=(),
            count=20_000_000):
        """Run from `start` to `until` (or to the return address when None).

        gp: {gp offset: word}; frame: {$fp offset: word}; strings: {scratch
        offset: bytes}; args: up to four argument registers.
        sectors: {lba: 2,048 bytes} a successful sceCdRead stores; bad_lbas
        read as failures that store nothing. modules: IOP module names for
        the scan. files/partitions feed the modelled file calls; fds:
        {descriptor: bytes} already open when the run starts."""
        from unicorn.mips_const import (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2,
                                        UC_MIPS_REG_A3, UC_MIPS_REG_FP, UC_MIPS_REG_GP,
                                        UC_MIPS_REG_RA, UC_MIPS_REG_SP, UC_MIPS_REG_V0)
        uc = self.uc
        image = bytearray(MEM_SIZE)
        use = self.core if core is None else bytes(core)
        image[CORE_BASE:CORE_BASE + len(use)] = use
        image[BASE:BASE + len(self.main)] = self.main
        # what the launch function set up long before (0x870c20..0x870c34)
        image[GP + G_READ_MODE:GP + G_READ_MODE + 4] = bytes([0x20, 1, 0, 0])
        for offset, value in dict(gp).items():
            struct.pack_into("<I", image, GP + offset, value & 0xFFFFFFFF)
        for offset, value in dict(frame).items():
            struct.pack_into("<I", image, FRAME + offset, value & 0xFFFFFFFF)
        for index, name in enumerate(modules):
            raw = name.encode("latin-1") + b"\0"
            image[SCRATCH + index * 0x40:SCRATCH + index * 0x40 + len(raw)] = raw
        for offset, raw in dict(strings).items():
            image[SCRATCH + offset:SCRATCH + offset + len(raw)] = raw
        before = bytes(image)
        uc.mem_write(0, before)
        for reg in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3, UC_MIPS_REG_V0):
            uc.reg_write(reg, 0)
        for reg, value in zip((UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3), args):
            uc.reg_write(reg, value & 0xFFFFFFFF)
        uc.reg_write(UC_MIPS_REG_GP, GP)
        uc.reg_write(UC_MIPS_REG_FP, FRAME)
        uc.reg_write(UC_MIPS_REG_SP, FRAME)
        uc.reg_write(UC_MIPS_REG_RA, STOP)
        self.st = {"log": [], "end": None, "left": None, "until": until,
                   "status": status, "disc_type": disc_type,
                   "sectors": dict(sectors or {}), "bad_lbas": set(bad_lbas),
                   "modules": list(modules), "load_result": load_result,
                   "init_result": init_result, "ready_result": ready_result,
                   "files": dict(files or {}),
                   "fds": {fd: [bytes(data), 0] for fd, data in dict(fds or {}).items()},
                   "next_fd": 3 + len(fds or {}),
                   "partitions": set(partitions), "mounted": None,
                   "model_fingerprint": model_fingerprint, "sig": None}
        uc.emu_start(start, STOP if until is None else until, count=count)
        st = self.st
        if st["end"] is None:
            # emu_start's own `until` stops without a callback when the end
            # address lies inside a window
            from unicorn.mips_const import UC_MIPS_REG_PC
            pc = uc.reg_read(UC_MIPS_REG_PC) & 0xFFFFFFFF
            if pc == STOP:
                st["end"] = "returned"
            else:
                st["end"] = "end" if until is not None and pc == until else "budget"
        after = bytes(uc.mem_read(0, MEM_SIZE))
        core_end = CORE_BASE + len(use)
        core_runs, other_runs = [], []
        for addr, data in changed_runs(before, after):
            if STACK_LOW <= addr < FRAME + FRAME_SPAN or SCRATCH <= addr < SCRATCH + SCRATCH_SPAN:
                continue
            (core_runs if CORE_BASE <= addr < core_end else other_runs).append((addr, data))
        return {"end": st["end"], "left": st["left"], "log": st["log"], "sig": st["sig"],
                "prints": [(e[1], e[2]) for e in st["log"] if e[0] == "printf"],
                "calls": [e for e in st["log"] if e[0] not in ("printf",)],
                "core_before": use, "core": after[CORE_BASE:core_end],
                "core_writes": core_runs, "other_writes": other_runs,
                "ret": s32(uc.reg_read(UC_MIPS_REG_V0)),
                "gp": lambda offset, size=4: after[GP + offset:GP + offset + size],
                "frame": lambda offset: struct.unpack_from("<I", after, FRAME + offset)[0],
                "memory": after}

    # -- the windows ---------------------------------------------------------
    def block(self, *, status=0, disc_type=0x10, sector4=None, read_ok=True,
              modules=(), quiet=0, launch_type=0, mass=0, auto=0, flag=1,
              vcd_found=0, core=None, load_result=1, init_result=1, ready_result=2):
        """The drive probe, 0x8766fc..0x876a40."""
        sectors = {} if sector4 is None else {4: sector4}
        return self.run(WINDOWS["block"][0], WINDOWS["block"][1], core=core,
                        gp={G_FLAG: flag, G_QUIET: quiet, G_LAUNCH_TYPE: launch_type,
                            G_MASS: mass, G_AUTO: auto},
                        frame={L_VCD_FOUND: vcd_found},
                        status=status, disc_type=disc_type, sectors=sectors,
                        bad_lbas=() if read_ok else (4,), modules=modules,
                        load_result=load_result, init_result=init_result,
                        ready_result=ready_result)

    def fingerprint(self, *, flag=1, sector16=None, sector22=None, bad_lbas=(),
                    vcd=None, mass=0, quiet=1, mode=3, fd=3):
        """FUN_008ff0e4(fd, mode) with the compare chain as shipped.

        flag 1: the sectors come from the modelled drive (a missing or bad
        LBA is a failed read). flag 0: `vcd` is the open file `fd` names.
        The result has "sig" (the 144 bytes as the chain first saw them; the
        function clears its buffer before returning), "id" (the entry it
        handed to FUN_008e00d0, 0 for none) and "list_id" (gp+0x38d8)."""
        sectors = {}
        if sector16 is not None:
            sectors[16] = sector16
        if sector22 is not None:
            sectors[22] = sector22
        r = self.run(FINGERPRINT, None, gp={G_FLAG: flag, G_MASS: mass, G_QUIET: quiet},
                     sectors=sectors, bad_lbas=bad_lbas, args=(fd, mode),
                     fds={} if vcd is None else {fd: vcd},
                     model_fingerprint=False, count=40_000_000)
        applied = [e for e in r["log"] if e[0] == "apply_entry"]
        r["id"] = applied[0][1] if applied else 0
        r["applied"] = applied
        r["list_id"] = struct.unpack("<I", r["gp"](G_LIST_ID))[0]
        return r

    def cdexit(self, flag):
        """0x8774c4: sceCdInit(5) when the flag is 1."""
        return self.run(WINDOWS["cdexit"][0], WINDOWS["cdexit"][1], gp={G_FLAG: flag})

    def banner(self, *, flag=1, quiet=0, launch_type=0, mass=0, smb=0, core=None,
               partition=b"hdd0:__.POPS"):
        """The "POPS ENVIRONMENT" lines from the flag test at 0x878ab4."""
        return self.run(WINDOWS["banner"][0], WINDOWS["banner"][1], core=core,
                        gp={G_FLAG: flag, G_QUIET: quiet, G_LAUNCH_TYPE: launch_type,
                            G_MASS: mass, G_SMB: smb},
                        frame={L_ARGV: SCRATCH + 0x8000},
                        strings={0x8000: struct.pack("<I", SCRATCH + 0x8010),
                                 0x8010: partition + b"\0"})

    def discs(self, *, flag=1, quiet=0, scope=0):
        """FUN_008d5cf8(scope, folder), the DISCS.TXT reader."""
        return self.run(WINDOWS["discs"][0], None, gp={G_FLAG: flag, G_QUIET: quiet},
                        args=(scope, SCRATCH + 0x9000), strings={0x9000: b"GAME/\0"})

    def probe(self, launch_type, *, argv0, vcd_path, partitions=(), files=None, auto=0,
              quiet=0):
        """The VCD probe of one launch type.

        0: ten partitions, "hdd0:__.POPS" then "hdd0:__.POPS0".."hdd0:__.POPS9",
           written over argv[0]; vcd_path is the path it opens on each.
        1, 2: the partition argv[0] names; vcd_path as for 0.
        3 (XX., SB.): "mass:/POPS/<name>" then "mass:/POPS0/<name>" ..
           "mass:/POPS9/<name>"; vcd_path is the bare name, which the original
           takes from POPS 0x4f8003.
        files: {(partition, path): bytes} or {path: bytes}. The result adds
        "flag", "found", "argv0" and "path" (the last path it built)."""
        gp = {G_FLAG: 0, G_QUIET: quiet, G_AUTO: auto, G_LAUNCH_TYPE: launch_type}
        core = None
        if launch_type == 3:
            lo, hi = WINDOWS["probe3"]
            gp[G_MASS] = 1
            core = bytearray(self.core)
            at = 0x4F8003 - CORE_BASE
            core[at:at + len(vcd_path) + 1] = vcd_path + b"\0"
        else:
            lo, hi = WINDOWS["probe0" if launch_type == 0 else "probe12"]
            raw = vcd_path + b"\0"
            raw += bytes(-len(raw) % 4)
            for i in range(0, len(raw), 4):
                gp[G_VCD_PATH + i] = struct.unpack_from("<I", raw, i)[0]
        r = self.run(lo, hi, core=core, gp=gp, frame={L_ARGV: SCRATCH + 0x8000},
                     strings={0x8000: struct.pack("<I", SCRATCH + 0x8010),
                              0x8010: argv0 + b"\0"},
                     partitions=partitions, files=files)
        r["flag"] = struct.unpack("<I", r["gp"](G_FLAG))[0]
        r["found"] = r["frame"](L_VCD_FOUND)
        text = r["memory"][SCRATCH + 0x8010:SCRATCH + 0x8050]
        r["argv0"] = text[:text.index(0)]
        text = r["gp"](G_VCD_PATH, 0x100)
        r["path"] = text[:text.index(0)]
        return r


def show(label, r):
    print("=== %s -> %s%s" % (label, r["end"], " at %#x" % r["left"] if r["left"] else ""))
    for event in r["log"]:
        print("    ", event)
    for kind in ("core_writes", "other_writes"):
        for addr, data in r[kind]:
            print("     %s %#x: %s" % (kind[:-7], addr,
                                       data.hex() if len(data) <= 16 else "%d bytes" % len(data)))


def main():
    emu = Emulator()
    sector = bytearray(SECTOR_SIZE)
    sector[0x3C:0x40] = b"Euro"
    sector = bytes(sector)
    for label, kw in [
        ("PS1 CD 0x10", dict(disc_type=0x10, sector4=sector)),
        ("PS1 CD+DA 0x11", dict(disc_type=0x11, sector4=sector)),
        ("PS2 CD 0x12, a cdvd_ module is loaded", dict(disc_type=0x12, sector4=sector,
                                                       modules=("sifman", "cdvd_driver"))),
        ("PS2 CD+DA 0x13, the read fails", dict(disc_type=0x13, sector4=sector, read_ok=False)),
        ("PS2 DVD 0x14", dict(disc_type=0x14)),
        ("no disc 0x00 on an XX./SB. launch", dict(disc_type=0, mass=1)),
        ("status 1", dict(status=1)),
        ("quiet, PS1 CD, list level 3", dict(disc_type=0x10, sector4=sector, quiet=1, auto=3)),
    ]:
        show(label, emu.block(**kw))
    for flag in (0, 1, 2):
        show("sceCdInit(5) test, flag %d" % flag, emu.cdexit(flag))
        show("environment lines, flag %d" % flag, emu.banner(flag=flag))
        show("DISCS.TXT reader, flag %d" % flag, emu.discs(flag=flag))
    show("fingerprint, both reads fail", emu.fingerprint(bad_lbas=(16, 22), quiet=0))
    show("types 1/2 probe, partition missing",
         emu.probe(1, argv0=b"hdd0:PP.GAME", vcd_path=b"pfs0:/IMAGE0.VCD"))
    show("type 0 probe, nothing found",
         emu.probe(0, argv0=b"hdd0:__common/POPS/GAME.ELF", vcd_path=b"pfs0:/GAME.VCD"))
    show("type 3 probe, nothing found",
         emu.probe(3, argv0=b"mass:/POPS/XX.GAME.ELF", vcd_path=b"GAME.VCD"))


if __name__ == "__main__":
    main()
