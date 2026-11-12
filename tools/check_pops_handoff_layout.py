#!/usr/bin/env python3
"""Check a linked launcher (launcher_unc.elf) for what the POPS handoff needs.

    python tools/check_pops_handoff_layout.py build/launcher/launcher_unc.elf

Exit 0 and a last line "handoff layout: OK", or exit 1 and the failed checks.
No Sony file is read; the ELF may be stripped (the release link is).

Checked (failures):
  1. the launcher loads inside 0x00100000..0x01000000: above the low memory
     that holds the trampoline, its arguments and its stack, below the
     staging area (the handoff's protected ranges, launcher/src/pops_handoff_ee.c);
  2. the trampoline in the image is launcher/src/pops_trampoline.S as
     tools/r5900_mini.py assembles it, once, and fits the launcher's size
     check (0x180 bytes);
  3. in it, interrupts go off (di) before the first store and syscall;
  4. the kernel calls the thread retirement makes are linked as plain
     syscall stubs and something calls each: CreateThread 0x20, DeleteThread
     0x21, TerminateThread 0x25, GetThreadId 0x2f, ReferThreadStatus 0x30;
  5. the retirement's report word (0x464f4850, common/include/pops_handoff.h)
     is built in code exactly once, so the glue is in the image.

Reported, not failed: how many call sites create threads and register
interrupt handlers (each is something the handoff has to retire or mask), and,
when the ELF has symbols (DEBUG builds), where ps2sdk's helper thread stack,
the launcher's placeholder stack and the SIF command receive buffer lie
relative to the memory POPS takes (0x00200000..0x00870000). A thread stack
there is safe because the threads are terminated before the trampoline runs;
the SIF buffer is listed because nothing moves it (docs/POPSTARTER_HANDOFF.md).

Static checks of one build's bytes. Not a boot, not a console test."""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r5900_mini as R  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TRAMP_ADDR, TRAMP_MAX = 0x00084000, 0x180
LOW, STAGING = 0x00100000, 0x01000000
POPS_LO, POPS_HI = 0x00200000, 0x00870000
RESET_FRAME = 0x2A0
MAGIC = 0x464F4850
DI, SYSCALL = 0x42000039, 0x0000000C
STORE_OPS = (0x28, 0x29, 0x2B, 0x2E, 0x3F, 0x1F, 0x2A, 0x2C, 0x2D, 0x38, 0x39, 0x3D)
NEEDED = {0x20: "CreateThread", 0x21: "DeleteThread", 0x25: "TerminateThread",
          0x2F: "GetThreadId", 0x30: "ReferThreadStatus"}
COUNTED = {0x20: "CreateThread", 0x10: "AddIntcHandler", 0x12: "AddDmacHandler"}


class Elf:
    def __init__(self, data):
        if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
            raise ValueError("not a 32-bit little-endian ELF")
        self.data = data
        e_phoff, e_shoff = struct.unpack_from("<II", data, 0x1C)
        e_phentsize, e_phnum, e_shentsize, e_shnum, _ = struct.unpack_from("<HHHHH", data, 0x2A)
        self.segments = []      # (vaddr, offset, filesz, memsz, flags)
        for i in range(e_phnum):
            p_type, p_offset, p_vaddr, _pa, p_filesz, p_memsz, p_flags = \
                struct.unpack_from("<7I", data, e_phoff + i * e_phentsize)
            if p_type == 1 and p_memsz:
                self.segments.append((p_vaddr, p_offset, p_filesz, p_memsz, p_flags))
        self.symbols = {}
        for i in range(e_shnum):
            sh = struct.unpack_from("<10I", data, e_shoff + i * e_shentsize)
            if sh[1] != 2:      # SHT_SYMTAB
                continue
            _n, _t, _f, _a, offset, size, link, _i, _al, entsize = sh
            str_off = struct.unpack_from("<10I", data, e_shoff + link * e_shentsize)[4]
            for pos in range(offset, offset + size, entsize or 16):
                st_name, st_value, st_size, st_info, _o, st_shndx = struct.unpack_from("<IIIBBH", data, pos)
                if st_name and st_shndx and (st_info & 15) in (0, 1, 2):
                    end = data.index(b"\0", str_off + st_name)
                    self.symbols.setdefault(data[str_off + st_name:end].decode("ascii", "replace"),
                                            (st_value, st_size))

    def vaddr_of(self, file_offset):
        for vaddr, offset, filesz, _memsz, _flags in self.segments:
            if offset <= file_offset < offset + filesz:
                return vaddr + file_offset - offset
        return None

    def code(self):
        """(vaddr, words) of every executable segment."""
        out = []
        for vaddr, offset, filesz, _memsz, flags in self.segments:
            if flags & 1:
                n = filesz // 4
                out.append((vaddr, struct.unpack_from("<%dI" % n, self.data, offset)))
        return out


def check(path):
    elf = Elf(Path(path).read_bytes())
    failures, notes = [], []
    code = elf.code()

    # 1. Where the launcher loads.
    lo = min(s[0] for s in elf.segments)
    hi = max(s[0] + s[3] for s in elf.segments)
    notes.append("image 0x%08x..0x%08x" % (lo, hi))
    if lo < LOW or hi > STAGING:
        failures.append("the launcher's image 0x%08x..0x%08x leaves 0x%08x..0x%08x"
                        % (lo, hi, LOW, STAGING))

    # 2. The trampoline is the assembled source.
    words, symbols = R.assemble((ROOT / "launcher/src/pops_trampoline.S").read_text(), TRAMP_ADDR)
    blob = b"".join(w.to_bytes(4, "little") for w in words)
    hits, pos = [], elf.data.find(blob)
    while pos >= 0:
        hits.append(pos)
        pos = elf.data.find(blob, pos + 1)
    where = [elf.vaddr_of(h) for h in hits]
    if len(hits) != 1 or where[0] is None:
        failures.append("the assembled trampoline (%d bytes) is in the image %d time(s), expected once"
                        % (len(blob), len(hits)))
    else:
        notes.append("trampoline %d bytes at 0x%08x" % (len(blob), where[0]))
    if len(blob) > TRAMP_MAX or symbols["pops_trampoline_code_end"] - symbols["pops_trampoline_code"] != len(blob):
        failures.append("the trampoline is %d bytes, over the launcher's limit of %d" % (len(blob), TRAMP_MAX))
    for name, value in (("pops_trampoline_code", where[0] if len(where) == 1 else None),):
        if name in elf.symbols and value is not None and elf.symbols[name][0] != value:
            failures.append("%s is at 0x%08x, the assembled code at 0x%08x" % (name, elf.symbols[name][0], value))

    # 3. Interrupts off before the first store and syscall.
    stores = [i for i, w in enumerate(words) if (w >> 26) in STORE_OPS]
    if words.count(DI) != 1 or not stores or SYSCALL not in words or \
            words.index(DI) > min(stores[0], words.index(SYSCALL)):
        failures.append("the trampoline does not turn interrupts off before its first store and syscall")

    # 4. Kernel calls, as syscall stubs with a caller.
    stubs, targets = {}, {}
    for vaddr, seg in code:
        for i in range(len(seg) - 1):
            w = seg[i]
            if (w & 0xFFFF0000) == 0x24030000 and seg[i + 1] == SYSCALL:
                stubs.setdefault(w & 0xFFFF, []).append(vaddr + 4 * i)
            if (w >> 26) in (2, 3):
                target = ((vaddr + 4 * i + 4) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
                targets[target] = targets.get(target, 0) + 1
    for number, name in sorted(NEEDED.items()):
        addrs = stubs.get(number, [])
        calls = sum(targets.get(a, 0) for a in addrs)
        if not addrs:
            failures.append("no %s stub (syscall 0x%x) in the image" % (name, number))
        elif not calls:
            failures.append("nothing calls the %s stub at 0x%08x" % (name, addrs[0]))
    for number, name in sorted(COUNTED.items()):
        notes.append("%s (syscall 0x%x): %d call site(s)"
                     % (name, number, sum(targets.get(a, 0) for a in stubs.get(number, []))))

    # 5. The report's magic word is loaded in code once.
    magic = 0
    for _vaddr, seg in code:
        for i, w in enumerate(seg):
            if (w >> 26) == 0x0F and (w & 0xFFFF) == MAGIC >> 16:
                rt = (w >> 16) & 31
                for v in seg[i + 1:i + 9]:
                    low = (v >> 26) in (0x09, 0x0D) and (v & 0xFFFF) == (MAGIC & 0xFFFF)   # addiu or ori
                    if low and ((v >> 21) & 31) == rt:
                        magic += 1
                        break
    if magic != 1:
        failures.append("the handoff report word 0x%08x is built %d time(s) in code, expected once" % (MAGIC, magic))

    # Symbols, when the build kept them.
    def place(name, label, size=None, frame=False):
        if name not in elf.symbols:
            return
        addr, sym_size = elf.symbols[name]
        size = size or sym_size
        lo_, hi_ = (addr + size - RESET_FRAME, addr + size) if frame else (addr, addr + size)
        inside = lo_ < POPS_HI and POPS_LO < hi_
        notes.append("%s %s 0x%08x..0x%08x: %s" % (
            label, "reset frame" if frame else "at", lo_, hi_,
            "inside the memory POPS takes" if inside else "outside the memory POPS takes"))

    if elf.symbols:
        place("stack", "ps2sdk helper thread stack,", 0x400, frame=True)
        place("dormantStack", "placeholder thread stack,", 0x400, frame=True)
        place("pktbuf", "SIF command receive buffer")
    else:
        notes.append("no symbol table (release link): stack and SIF buffer addresses not listed")
    return failures, notes


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    try:
        failures, notes = check(argv[1])
    except (OSError, ValueError, struct.error) as exc:
        print("handoff layout: cannot read %s: %s" % (argv[1], exc))
        return 1
    for note in notes:
        print("handoff layout: " + note)
    for failure in failures:
        print("handoff layout: FAILED: " + failure)
    if failures:
        return 1
    print("handoff layout: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
