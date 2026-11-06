#!/usr/bin/env python3
"""Execute pinned external Sony IOPCD and POPStarter wrapper with modeled I/O.

No original binary bytes are included or emitted. Requires Python's Unicorn
package only for execution. This is bounded MIPS IOP execution with synthetic
services, not an EE boot, real IOP kernel, storage device or console test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
from pathlib import Path
import struct

MAIN_SHA = "734c813e8e8ec2c6729ec5e15dd46ab696e90deeade8d0b2ca3ad03782781aa1"
UNPACKED_SHA = "185177c28aaef30ad1e00697ad7b6de22b55bd855253ab4ede8b1ab2dfb08aee"
POPS_SHA = "59df3389c4df88a572daa720b05507c52c34eddfa0031a6fbeec55e0c2d0fcb1"
WRAPPER_SHA = "c08a41c98301009bfd0d277dd974e244536fe0ec37df880501a919829ac21c0c"
IOPCD_SHA = "ccdd60e1408b7dbc4a65e9fdad53b671e7acdb69fc5acc72704a952feacd58ae"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def signed(word):
    return (word & 0x7fffffff) - (word & 0x80000000)


def decode_main(packed):
    require(len(packed) == 167700 and digest(packed) == MAIN_SHA,
            "requires the pinned POPSLoader MAIN profile (not an arbitrary r13)")
    payload = packed[0x5f0:]
    length, = struct.unpack_from("<I", payload)
    require(length == 0x149cac, "unexpected decoded size")
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[{
        "id": lzma.FILTER_LZMA1, "dict_size": 8 << 20,
        "lc": 3, "lp": 0, "pb": 2,
    }])
    unpacked = decoder.decompress(b"\0" + payload[4:8][::-1] + payload[8:],
                                  max_length=length)
    require(len(unpacked) == length and digest(unpacked) == UNPACKED_SHA,
            "decoded MAIN differs from the bounded original-decoder result")
    return unpacked


class Module:
    """Pinned IRX only. Load at its original zero-based link addresses.

    No general relocation loader is claimed: original text/data addresses and
    GP are preserved at link base zero, so base relocations add zero. Imports
    are intercepted at their declared stubs instead of resolving an IOP kernel.
    """
    def __init__(self, blob, expected_sha):
        require(digest(blob) == expected_sha, "unrecognized IOP module")
        require(blob[:6] == b"\x7fELF\x01\x01" and
                struct.unpack_from("<HH", blob, 16) == (0xff80, 8),
                "expected ELF32 little-endian IOP MIPS")
        self.blob = blob
        at = struct.unpack_from("<I", blob, 32)[0]
        entry_size, count = struct.unpack_from("<HH", blob, 46)
        require(entry_size == 40 and 0 < count <= 64 and
                at + count * 40 <= len(blob), "invalid section table")
        self.sections = [struct.unpack_from("<10I", blob, at + i * 40)
                         for i in range(count)]
        for s in self.sections:
            require(s[3] + s[5] <= 0x10000, "unexpected loaded section size")
            if s[1] != 8:
                require(s[4] + s[5] <= len(blob), "truncated file section")
        iopmod = next(s for s in self.sections if s[1] == 0x70000080)
        self.entry, self.gp = struct.unpack_from("<II", blob, iopmod[4] + 4)
        self.imports = {}
        for s in self.sections:
            if not s[2] & 4:
                continue
            for off in range(s[4], s[4] + s[5] - 19, 4):
                if struct.unpack_from("<I", blob, off)[0] != 0x41e00000:
                    continue
                name = blob[off + 12:off + 20].rstrip(b"\0").decode("ascii")
                cursor = off + 20
                while cursor + 8 <= s[4] + s[5]:
                    jump, ordinal = struct.unpack_from("<II", blob, cursor)
                    if jump != 0x03e00008 or ordinal & 0xffff0000 != 0x24000000:
                        break
                    self.imports[s[3] + cursor - s[4]] = (name, ordinal & 0xffff)
                    cursor += 8
        self.symbols = {}
        for s in self.sections:
            if s[1] != 2:
                continue
            require(s[9] == 16 and s[5] % 16 == 0 and s[6] < count,
                    "invalid symbol table")
            strings_section = self.sections[s[6]]
            require(strings_section[1] == 3, "invalid symbol string table")
            strings = blob[strings_section[4]:strings_section[4] + strings_section[5]]
            for off in range(s[4], s[4] + s[5], 16):
                name, value, size, info, _, index = struct.unpack_from("<IIIBBH", blob, off)
                end = strings.find(b"\0", name)
                require(end >= name, "invalid symbol name")
                if name:
                    self.symbols[strings[name:end].decode("ascii")] = value


class Machine:
    STOP, STACK, FILE, REQUEST, BUFFER = 0x1f0000, 0x1e0000, 0x100000, 0x101000, 0x110000

    def __init__(self, module, handler):
        import unicorn
        from unicorn import mips_const as regs
        self.regs = regs
        self.module = module
        self.uc = unicorn.Uc(unicorn.UC_ARCH_MIPS,
                             unicorn.UC_MODE_MIPS32 | unicorn.UC_MODE_LITTLE_ENDIAN)
        self.uc.mem_map(0, 0x200000)
        for s in module.sections:
            if s[2] & 2 and s[1] != 8 and s[5]:
                self.uc.mem_write(s[3], module.blob[s[4]:s[4] + s[5]])
        self.uc.reg_write(regs.UC_MIPS_REG_GP, module.gp)

        def hook(uc, address, size, unused):
            imported = module.imports.get(address)
            if imported:
                args = [uc.reg_read(getattr(regs, f"UC_MIPS_REG_A{i}")) for i in range(4)]
                result = handler(self, imported, args)
                uc.reg_write(regs.UC_MIPS_REG_V0, result & 0xffffffff)
                uc.reg_write(regs.UC_MIPS_REG_PC, uc.reg_read(regs.UC_MIPS_REG_RA))
        self.uc.hook_add(unicorn.UC_HOOK_CODE, hook)

    def word(self, address):
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def put(self, address, *words):
        self.uc.mem_write(address, struct.pack("<" + "I" * len(words),
                                             *(n & 0xffffffff for n in words)))

    def string(self, address):
        raw = bytes(self.uc.mem_read(address, 256))
        require(b"\0" in raw, "unterminated modeled path")
        return raw.split(b"\0", 1)[0].decode("ascii")

    def call(self, address, *args):
        regs = self.regs
        self.uc.reg_write(regs.UC_MIPS_REG_SP, self.STACK)
        self.uc.reg_write(regs.UC_MIPS_REG_RA, self.STOP)
        for i, value in enumerate(args):
            self.uc.reg_write(getattr(regs, f"UC_MIPS_REG_A{i}"), value & 0xffffffff)
        self.uc.emu_start(address, self.STOP, timeout=2_000_000, count=100_000)
        require(self.uc.reg_read(regs.UC_MIPS_REG_PC) == self.STOP,
                "original callback did not return within the execution bound")
        return signed(self.uc.reg_read(regs.UC_MIPS_REG_V0))


class OriginalRoute:
    """Execute original callbacks; replace only imported kernel/backend services."""
    def __init__(self, wrapper, iopcd):
        self.events = []
        self.backend_fd = 7
        self.logical_fd = 11
        self.position = 0
        self.open_result = self.backend_fd
        self.seek_result = None
        self.read_result = None
        self.close_result = 0
        self.wrapper = Machine(wrapper, self.wrapper_import)
        self.sony = Machine(iopcd, self.sony_import)
        # Original device descriptor and operations table at link base zero.
        dev = 0x588
        require(self.wrapper.string(self.wrapper.word(dev)) == "pfs", "wrong wrapper device")
        require(self.wrapper.word(dev + 4) == 0x10, "wrong legacy filesystem type")
        self.ops = self.wrapper.word(dev + 16)
        require([self.wrapper.word(self.ops + n * 4) for n in range(3, 9)] ==
                [0xd4, 0x154, 0x178, 0x19c, 0x1c0, 0x9c], "changed wrapper callbacks")
        # Initialize actual file object's device field; other fields start zero.
        self.wrapper.put(Machine.FILE, 0, 0, dev, 0)

    def callback(self, index, *args):
        return self.wrapper.call(self.wrapper.word(self.ops + index * 4), Machine.FILE, *args)

    def wrapper_import(self, machine, imported, args):
        lib, ordinal = imported
        if lib == "sysclib" and ordinal == 23:  # strcpy, bounded by our supplied fixture
            text = machine.string(args[1]).encode("ascii") + b"\0"
            machine.uc.mem_write(args[0], text)
            return args[0]
        if lib == "thsemap" and ordinal in (6, 8):
            return 0  # signal/wait on an uncontended modeled semaphore
        if lib == "thbase" and ordinal == 33:
            return 0  # DelayThread; no wall-clock sleep in this probe
        require(lib == "ioman", f"unexpected wrapper import {imported}")
        if ordinal == 4:
            self.events.append({"op": "open", "path": machine.string(args[0]), "flags": args[1]})
            self.position = 0
            return self.open_result
        require(args[0] == self.backend_fd, "original wrapper lost backing descriptor")
        if ordinal == 5:
            self.events.append({"op": "close", "fd": args[0]})
            return self.close_result
        if ordinal == 8:
            offset, whence = signed(args[1]), args[2]
            self.events.append({"op": "lseek", "fd": args[0], "offset": offset, "whence": whence})
            self.position = offset
            return offset if self.seek_result is None else self.seek_result
        if ordinal in (6, 7):
            op = "read" if ordinal == 6 else "write"
            self.events.append({"op": op, "fd": args[0], "offset": self.position, "size": args[2]})
            result = args[2] if self.read_result is None else self.read_result
            require(result <= args[2], "modeled backend exceeds supplied buffer")
            if result > 0 and ordinal == 6:
                # Synthetic file bytes fingerprint absolute positions.
                data = bytes((self.position + i) % 251 for i in range(result))
                machine.uc.mem_write(args[1], data)
                self.position += result
            return result
        raise ValueError(f"unmodeled wrapper import {imported}")

    def sony_import(self, machine, imported, args):
        lib, ordinal = imported
        if lib == "stdio" and ordinal == 4:
            return 0  # modeled printf, no format dereference required
        require(lib == "ioman", f"unexpected Sony import {imported}")
        if ordinal == 4:
            path = machine.string(args[0])
            require(path.startswith("pfs0:/"), "unexpected Sony file namespace")
            self.wrapper.uc.mem_write(Machine.REQUEST, path[5:].encode("ascii") + b"\0")
            result = self.callback(3, Machine.REQUEST, args[1])
            return result if result < 0 else self.logical_fd
        require(args[0] == self.logical_fd, "Sony lost logical file descriptor")
        if ordinal == 5:
            return self.callback(4)
        if ordinal == 8:
            return self.callback(7, args[1], args[2])
        if ordinal == 6:
            result = self.callback(5, Machine.BUFFER, args[2])
            if result > 0:
                machine.uc.mem_write(args[1], bytes(self.wrapper.uc.mem_read(Machine.BUFFER, result)))
            return result
        raise ValueError(f"unmodeled Sony import {imported}")

    def open_disc(self):
        self.sony.uc.mem_write(Machine.REQUEST, b"pfs0:/IMAGE.VCD\0")
        pointer = self.sony.call(self.sony.module.symbols["ServerFunc"], 0x435053, Machine.REQUEST, 16)
        return signed(self.sony.word(pointer))

    def read_sectors(self, byte_offset, count=1, lba=16):
        self.sony.put(Machine.REQUEST, lba, count, 0, byte_offset, 0)
        result = self.sony.call(self.sony.module.symbols["rdsector"], self.logical_fd,
                                Machine.REQUEST, Machine.BUFFER)
        return result, self.sony.word(Machine.REQUEST + 16)


def trace(main, pops):
    unpacked = decode_main(main)
    require(len(pops) == 3166988 and digest(pops) == POPS_SHA,
            "requires the pinned external Sony POPS ELF")
    wrapper = Module(unpacked[0xaf680:0xaf680 + 2484], WRAPPER_SHA)
    iopcd = Module(pops[0xfb820:0xfb820 + 15951], IOPCD_SHA)
    require(iopcd.symbols.get("rdsector") == 0x554 and
            iopcd.symbols.get("ServerFunc") == 0x804, "changed Sony symbols")
    require({imp for imp in iopcd.imports.values() if imp[0] == "ioman"} ==
            {("ioman", n) for n in (4, 5, 6, 8)}, "changed Sony filesystem imports")
    cases = []

    route = OriginalRoute(wrapper, iopcd)
    require(route.open_disc() == 1024, "original disc-open/TOC read failed")
    require(route.events == [{"op": "open", "path": "mass:/POPS/IMAGE.VCD", "flags": 1},
                             {"op": "read", "fd": 7, "offset": 0, "size": 1024}],
            "changed original open/TOC sequence")
    cases.append({"case": "open-and-TOC", "events": route.events.copy()})

    requests = [(offset, count, 16, "controlled byte-offset stimulus")
                for offset, count in [(0, 1), (0x400, 1), (0x100000, 1),
                    (0x100000 + 16 * 2352 + 24, 1), (0x123457, 16),
                    (0x100000, 16), (0x100100, 16), (0x100000, 2)]]
    # Recorded unchanged R5900 FUN_00210090 request fields, measured with
    # both GCC and LLVM probe harnesses in PCSX2. Transport remains modeled.
    requests += [(offset, count, lba, "native EE probe observation") for lba, count, offset in [
        (0, 16, 1048576), (16, 16, 1086208), (1234, 16, 3950944),
        (4999, 2, 12806224), (5000, 1, 12808576)]]
    for offset, count, lba, source in requests:
        route.events.clear()
        result, skip = route.read_sectors(offset, count, lba)
        aligned = offset & ~511
        length = (count * 2352 + (offset & 511) + 512) & ~511
        require(result == length and skip == offset & 511, "changed Sony read geometry")
        require(route.events == [{"op": "lseek", "fd": 7, "offset": aligned, "whence": 0},
                                 {"op": "read", "fd": 7, "offset": aligned, "size": length}],
                "original wrapper modified Sony byte offsets")
        actual = bytes(route.sony.uc.mem_read(Machine.BUFFER, length))
        require(actual == bytes((aligned + i) % 251 for i in range(length)),
                "original read did not forward synthetic backing bytes")
        cases.append({"case": "rdsector", "requested_byte_offset": offset,
                      "requested_lba": lba, "request_source": source,
                      "requested_sector_count": count, "returned_bytes": result,
                      "reported_skip": skip, "events": route.events.copy()})

    for seek_error in (-5, -9):
        route.events.clear()
        route.seek_result = seek_error
        result, _ = route.read_sectors(0x100000)
        require(result == seek_error and len(route.events) == 1, "seek error did not propagate")
        cases.append({"case": "seek-error", "result": result, "events": route.events.copy()})
    route.seek_result = None
    for read_result in (-5, 0, 100, 2352):
        route.events.clear()
        route.read_result = read_result
        result, _ = route.read_sectors(0x100000)
        require(result == read_result, "read result did not propagate")
        cases.append({"case": "read-result", "result": result, "events": route.events.copy()})
    for open_result in (-2, -5):
        failed = OriginalRoute(wrapper, iopcd)
        failed.open_result = open_result
        require(failed.open_disc() == open_result and len(failed.events) == 1,
                "failed open performed a read or lost its error")
        cases.append({"case": "open-error", "result": open_result, "events": failed.events})
    for close_result in (0, -5):
        closing = OriginalRoute(wrapper, iopcd)
        require(closing.open_disc() == 1024, "close fixture did not open")
        closing.events.clear()
        closing.close_result = close_result
        closing.sony.call(iopcd.symbols["ServerFunc"], 0x435054, Machine.REQUEST, 0)
        require(closing.events == [{"op": "close", "fd": 7}] and
                signed(closing.sony.word(iopcd.symbols["fd.16"])) == -1,
                "original close did not release logical descriptor")
        cases.append({"case": "close", "backend_result": close_result,
                      "events": closing.events})
    zero = OriginalRoute(wrapper, iopcd)
    zero.backend_fd = zero.open_result = 0
    require(zero.open_disc() == 1024 and zero.events[1]["fd"] == 0,
            "original wrapper failed to preserve descriptor zero")
    cases.append({"case": "descriptor-zero", "events": zero.events})
    short = OriginalRoute(wrapper, iopcd)
    short.read_result = 512
    require(short.open_disc() == 512 and [e["op"] for e in short.events] ==
            ["open", "read", "close"], "short TOC did not close the disc")
    cases.append({"case": "short-TOC", "result": 512, "events": short.events})
    return {
        "main_sha256": MAIN_SHA, "decoded_sha256": UNPACKED_SHA,
        "pops_elf_sha256": POPS_SHA, "wrapper_sha256": WRAPPER_SHA,
        "iopcd_sha256": IOPCD_SHA, "case_count": len(cases), "cases": cases,
        "execution": "original MIPS32 IOP code at link base zero; bounded callbacks",
        "modeled_services": ["legacy IOMAN descriptor routing", "synthetic backend bytes/results",
                             "uncontended semaphores", "DelayThread", "printf", "strcpy"],
        "limits": "Synthetic file-mode requests; no EE caller, actual IOP kernel, physical medium, "
                  "CDDA, save persistence, runtime mount sequence or console boot is exercised.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--popstarter", type=Path, required=True, help="external archived MAIN ELF")
    parser.add_argument("--pops-elf", type=Path, required=True, help="external selected Sony POPS.ELF")
    parser.add_argument("--json", type=Path, help="metadata-only output; never contains binary bytes")
    args = parser.parse_args()
    report = trace(args.popstarter.read_bytes(), args.pops_elf.read_bytes())
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Original IOPCD + embedded wrapper: {report['case_count']} bounded cases PASS")
    print(report["limits"])


if __name__ == "__main__":
    main()
