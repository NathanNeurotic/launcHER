#!/usr/bin/env python3
"""Run POPStarter r13's TROJAN_n.BIN loader on given files (external inputs only).

The loader is FUN_00880a24 (a0 = scope: 0 all games, 1 one game; a1 = the
game's folder name). It builds the ten paths itself, opens each, reads a
0x50-byte header, prints "Invalid" or "Skipped (outdated)" and goes on, or
copies the payload with memcpy straight to the header's load address and
writes the hook word(s), then prints "Hooked :". It returns 1 whatever
happened.

This runs it as shipped under Unicorn, with POPSTARTER MAIN at 0x870000 and
the POPS core at 0x200000. Only printf, strlen, memcpy, memset, malloc and
the device file calls are modelled. What it changed is measured by comparing
all 32 MiB with the memory before the call, never by a live write hook.
Needs POPSTARTER_TEST_ELF, POPS_TEST_ELF and unicorn. Nothing here is a
console run.
"""
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_original_pops_io import decode_main  # noqa: E402

BASE = 0x870000
GP = 0x9B68F0
CORE_BASE = 0x200000
CORE_SIZE = 0x302E60
TROJAN_LOADER = 0x880A24
PATCH_LOADER = 0x881DE8  # PATCH_n.BIN, same arguments and file calls
MEM = 0x02000000
STACK = 0x01F80000
HEAP = 0x01A00000
HEAP_SIZE = 0x00400000
RETURN = 0x00100000  # parked return address, outside every image
FILL = 0xA5
M32 = 0xFFFFFFFF

# The original's own state the loader reads (gp offsets).
GP_DISABLED = 0x38DC   # 1: every fix-file loader returns at once
GP_HDD = 0x3448        # 0: pfs1:, 1: mass:
GP_REVISION = 0x345C   # 6, set at 0x870d9c
GP_BUILTIN = 0x38D8    # built-in entry the fingerprint matcher selected
GP_MALLOC = 0x4FBC     # the payload buffer, never freed

# Library and device calls in MAIN that are modelled, by address.
PRINTF, STRLEN, MEMCPY, MEMSET, MALLOC = 0x915708, 0x918E08, 0x918808, 0x9188B8, 0x9190C8
FILE_CALLS = {"open": (0x8D6C94, 0x916758), "lseek": (0x8D6D64, 0x916C08),
              "read": (0x8D6D24, 0x9169B0), "close": (0x8D6CF4, 0x916878)}
GETSTAT, DIRCHECK = 0x91BF80, 0x8D7E78


def pops_core(path=None):
    """The POPS core as launcHER stages it: one flat image from 0x200000."""
    data = Path(path or os.environ["POPS_TEST_ELF"]).read_bytes()
    phoff, = struct.unpack_from("<I", data, 0x1C)
    phnum, = struct.unpack_from("<H", data, 0x2C)
    core = bytearray(CORE_SIZE)
    for i in range(phnum):
        p_type, off, vaddr, _pa, filesz = struct.unpack_from("<5I", data, phoff + 32 * i)
        if p_type == 1 and filesz and CORE_BASE <= vaddr < CORE_BASE + CORE_SIZE:
            core[vaddr - CORE_BASE:vaddr - CORE_BASE + filesz] = data[off:off + filesz]
    return bytes(core)


class Loader:
    def __init__(self, main_elf=None, pops_elf=None):
        from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
        import unicorn.mips_const as mc
        self.mc = mc
        main = decode_main(Path(main_elf or os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
        self.uc = uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
        try:
            uc.ctl_set_cpu_model(5)  # UC_CPU_MIPS64_5KF, as the other tracers
        except Exception:
            pass
        uc.mem_map(0, MEM)
        image = bytearray([FILL]) * MEM
        image[CORE_BASE:CORE_BASE + CORE_SIZE] = pops_core(pops_elf)
        image[BASE:BASE + len(main)] = main
        image[BASE + len(main):0xB00000] = bytes(0xB00000 - BASE - len(main))
        self.baseline = bytes(image)
        self.files = {}
        self.handles = {}
        self.events = []
        self.args = (mc.UC_MIPS_REG_A0, mc.UC_MIPS_REG_A1, mc.UC_MIPS_REG_A2, mc.UC_MIPS_REG_A3)
        natives = {PRINTF: self._printf, STRLEN: self._strlen, MEMCPY: self._memcpy,
                   MEMSET: self._memset, MALLOC: self._malloc, GETSTAT: self._getstat,
                   DIRCHECK: self._dircheck}
        for name, addresses in FILE_CALLS.items():
            for address in addresses:
                natives[address] = getattr(self, "_" + name)

        def hook(u, address, _size, _user):
            fn = natives.get(address)
            if fn is not None:
                fn([u.reg_read(r) & M32 for r in self.args])
                u.reg_write(mc.UC_MIPS_REG_PC, u.reg_read(mc.UC_MIPS_REG_RA))

        for address in natives:
            uc.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)

    def _string(self, at):
        out = bytearray()
        while True:
            byte = self.uc.mem_read(at + len(out), 1)
            if byte == b"\0":
                return bytes(out)
            out += byte

    def _ret(self, value):
        value &= M32
        self.uc.reg_write(self.mc.UC_MIPS_REG_V0, value | 0xFFFFFFFF00000000 if value >> 31 else value)

    def _printf(self, a):
        self.events.append(("msg", self._string(a[0]).decode("latin1").strip()))
        self._ret(0)

    def _strlen(self, a):
        self._ret(len(self._string(a[0])))

    def _memcpy(self, a):
        data = bytes(self.uc.mem_read(a[1], a[2])) if a[2] else b""
        self.events.append(("memcpy", a[0], a[2], data))
        if data:
            self.uc.mem_write(a[0], data)
        self._ret(a[0])

    def _memset(self, a):
        self.events.append(("memset", a[0], a[2], a[1] & 0xFF))
        if a[2]:
            self.uc.mem_write(a[0], bytes([a[1] & 0xFF]) * a[2])
        self._ret(a[0])

    def _malloc(self, a):
        self.events.append(("malloc", a[0]))
        assert a[0] <= HEAP_SIZE, "malloc %#x" % a[0]
        self._ret(HEAP)

    def _open(self, a):
        path = self._string(a[0])
        self.events.append(("open", path))
        if path in self.files:
            handle = 3 + len(self.handles)
            self.handles[handle] = [self.files[path], 0]
            self._ret(handle)
        else:
            self._ret(-2)

    def _lseek(self, a):
        entry = self.handles[a[0]]
        offset = a[1] - (1 << 32) if a[1] >> 31 else a[1]
        entry[1] = offset if a[2] == 0 else (len(entry[0]) + offset if a[2] == 2 else entry[1] + offset)
        self._ret(entry[1])

    def _read(self, a):
        entry = self.handles[a[0]]
        data = entry[0][entry[1]:entry[1] + a[2]]
        if data:
            self.uc.mem_write(a[1], data)
        entry[1] += len(data)
        self.events.append(("read", a[1], a[2], len(data)))
        self._ret(len(data))

    def _close(self, a):
        self.events.append(("close", a[0]))
        self._ret(0)

    def _getstat(self, a):
        self.events.append(("getstat", self._string(a[0])))
        self._ret(0)

    def _dircheck(self, a):
        self.events.append(("dircheck", self._string(a[0])))
        self._ret(1)

    def run(self, files, scope=0, title=b"", hdd=False, builtin=0, loader=TROJAN_LOADER):
        """files: {path bytes: data}. -> (return value, events, memory after)."""
        mc, uc = self.mc, self.uc
        uc.mem_write(0, self.baseline)
        self.files, self.handles, self.events = dict(files), {}, []
        state = {GP_DISABLED: 0, 0x3460: 0, 0x3868: 1, GP_HDD: 0 if hdd else 1, 0x381C: 0,
                 0x38B8: 0, 0x38E0: 0, 0x38B0: 0, GP_REVISION: 6, GP_BUILTIN: builtin,
                 0x3864: 0, 0x4FA0: 1, 0x38D0: 0, 0x3898: 0, 0x38A0: 0}
        for offset, value in state.items():
            uc.mem_write(GP + offset, struct.pack("<I", value & M32))
        title_at = STACK + 0x1000
        uc.mem_write(title_at, title + b"\0")
        self.before = bytes(uc.mem_read(0, MEM))
        for reg in range(mc.UC_MIPS_REG_0 + 1, mc.UC_MIPS_REG_0 + 32):
            uc.reg_write(reg, 0)
        uc.reg_write(mc.UC_MIPS_REG_GP, GP)
        uc.reg_write(mc.UC_MIPS_REG_SP, STACK)
        uc.reg_write(mc.UC_MIPS_REG_FP, STACK)
        uc.reg_write(mc.UC_MIPS_REG_RA, RETURN)
        uc.reg_write(mc.UC_MIPS_REG_A0, scope)
        uc.reg_write(mc.UC_MIPS_REG_A1, title_at)
        uc.emu_start(loader, RETURN, count=200_000_000)
        assert uc.reg_read(mc.UC_MIPS_REG_PC) & M32 == RETURN, "the loader did not return"
        return uc.reg_read(mc.UC_MIPS_REG_V0) & M32, self.events, bytes(uc.mem_read(0, MEM))

    def changed(self, after, page=0x1000):
        """Changed [start, end) ranges outside the loader's stack, heap and gp data."""
        out = []
        for at in range(0, MEM, page):
            if STACK - 0x10000 <= at < STACK + 0x2000 or HEAP <= at < HEAP + HEAP_SIZE or \
                    BASE <= at < 0xB00000:
                continue
            a, b = self.before[at:at + page], after[at:at + page]
            if a == b:
                continue
            i = 0
            while i < page:
                if a[i] == b[i]:
                    i += 1
                    continue
                j = i
                while j < page and a[j] != b[j]:
                    j += 1
                if out and out[-1][1] == at + i:
                    out[-1] = (out[-1][0], at + j)
                else:
                    out.append((at + i, at + j))
                i = j
        return out


def verdicts(events):
    """One word per file the loader read, in order: APPLIED, INVALID, OUTDATED."""
    out = []
    for kind, *rest in events:
        if kind != "msg":
            continue
        text = rest[0]
        if text.startswith("Hooked"):
            out.append("APPLIED")
        elif text == "Invalid":
            out.append("INVALID")
        elif text.startswith("Skipped"):
            out.append("OUTDATED")
    return out


def main():
    loader = Loader()
    for name in sys.argv[1:]:
        data = Path(name).read_bytes()
        slot = int(Path(name).name[7])
        result, events, after = loader.run({b"mass:/POPS/TROJAN_%d.BIN" % slot: data})
        print("%s: returned %d, %s, changed %s" % (
            name, result, verdicts(events),
            ", ".join("%#x..%#x" % r for r in loader.changed(after))))


if __name__ == "__main__":
    main()
