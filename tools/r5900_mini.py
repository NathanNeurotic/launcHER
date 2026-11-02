#!/usr/bin/env python3
"""A small R5900 (PS2 EE) interpreter and assembler for the few instructions
POPStarter's launch pokes, the misaligned-read guards and launcHER's POPS
trampoline use.

128-bit GPRs, where an instruction that is not MMI/LQ writes bits 0..63 only
and keeps bits 64..127 (as the R5900 does); branch delay slots; branch-likely;
an address error on a misaligned halfword, word or doubleword access (LQ/SQ
ignore the low four bits, as on the console); SYSCALL stops the run with a
Syscall exception (pc left on it, $v1 holds the number). Any other
instruction raises, so a test never runs something this model does not
cover. Pure Python, no third-party packages. Not a console test."""

M32 = (1 << 32) - 1
M64 = (1 << 64) - 1
M128 = (1 << 128) - 1


def sext32(value):
    value &= M32
    return (value - (1 << 32) if value & 0x80000000 else value) & M64


def sext16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


class AddressError(Exception):
    pass


class Syscall(Exception):
    """A SYSCALL was reached; the machine's pc is still on it."""
    def __init__(self, number, pc):
        super().__init__("syscall 0x%x at 0x%08x" % (number, pc))
        self.number, self.pc = number, pc


class Machine:
    def __init__(self):
        self.gpr = [0] * 32
        self.pages = {}
        self.stores = []        # (address, bytes) in program order
        self.natives = {}       # address -> function(machine); returns to $ra
        self.record = True      # False: do not keep self.stores (long loops)
        self.pc = 0
        self.steps = 0

    # Memory: sparse 4 KiB pages, 32-bit addresses, zero when never written.
    def read(self, addr, n):
        out = bytearray()
        while n > 0:
            a = addr & M32
            off = a & 0xFFF
            take = min(n, 4096 - off)
            page = self.pages.get(a >> 12)
            out += page[off:off + take] if page else bytes(take)
            addr, n = addr + take, n - take
        return bytes(out)

    def write(self, addr, data, record=False):
        data = bytes(data)
        if record and self.record:
            self.stores.append((addr & M32, data))
        pos = 0
        while pos < len(data):
            a = (addr + pos) & M32
            off = a & 0xFFF
            take = min(len(data) - pos, 4096 - off)
            page = self.pages.setdefault(a >> 12, bytearray(4096))
            page[off:off + take] = data[pos:pos + take]
            pos += take

    def u32(self, addr):
        return int.from_bytes(self.read(addr, 4), "little")

    def put32(self, addr, value):
        self.write(addr, (value & M32).to_bytes(4, "little"))

    # Registers.
    def lo(self, r):
        return self.gpr[r] & M64

    def set_lo(self, r, value):
        if r:
            self.gpr[r] = (self.gpr[r] & (M64 << 64)) | (value & M64)

    def set_full(self, r, value):
        if r:
            self.gpr[r] = value & M128

    def _ea(self, base, imm, align):
        addr = (self.lo(base) + sext16(imm)) & M32
        if addr % align:
            raise AddressError("misaligned %d-byte access at 0x%08x (pc 0x%08x)" % (align, addr, self.pc))
        return addr

    @staticmethod
    def is_control(word):
        op = word >> 26
        if op == 0:
            return (word & 63) in (8, 9)
        return op in (1, 2, 3, 4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17)

    def execute(self, word, pc):
        """Run one instruction. Returns None, or (taken, target, likely)."""
        op = word >> 26
        rs, rt, rd, sa, fn = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31, (word >> 6) & 31, word & 63
        imm = word & 0xFFFF
        if op == 0:
            if fn == 0:      # sll
                self.set_lo(rd, sext32(self.lo(rt) << sa))
            elif fn == 2:    # srl
                self.set_lo(rd, sext32((self.lo(rt) & M32) >> sa))
            elif fn == 3:    # sra
                v = self.lo(rt) & M32
                v -= (v & 0x80000000) << 1
                self.set_lo(rd, sext32(v >> sa))
            elif fn == 8:    # jr
                return True, self.lo(rs) & M32, False
            elif fn == 9:    # jalr
                target = self.lo(rs) & M32
                self.set_lo(rd, pc + 8)
                return True, target, False
            elif fn == 0x0A:  # movz
                if not self.lo(rt):
                    self.set_lo(rd, self.lo(rs))
            elif fn == 0x0B:  # movn
                if self.lo(rt):
                    self.set_lo(rd, self.lo(rs))
            elif fn == 0x0C:  # syscall
                raise Syscall(self.lo(3) & M32, pc)
            elif fn == 0x0F:  # sync
                pass
            elif fn == 0x21:  # addu
                self.set_lo(rd, sext32(self.lo(rs) + self.lo(rt)))
            elif fn == 0x23:  # subu
                self.set_lo(rd, sext32(self.lo(rs) - self.lo(rt)))
            elif fn == 0x24:
                self.set_lo(rd, self.lo(rs) & self.lo(rt))
            elif fn == 0x25:
                self.set_lo(rd, self.lo(rs) | self.lo(rt))
            elif fn == 0x26:
                self.set_lo(rd, self.lo(rs) ^ self.lo(rt))
            elif fn == 0x27:
                self.set_lo(rd, ~(self.lo(rs) | self.lo(rt)))
            elif fn == 0x2A:  # slt
                a, b = self.lo(rs), self.lo(rt)
                a -= (a & (1 << 63)) << 1
                b -= (b & (1 << 63)) << 1
                self.set_lo(rd, int(a < b))
            elif fn == 0x2B:  # sltu
                self.set_lo(rd, int(self.lo(rs) < self.lo(rt)))
            elif fn == 0x2D:  # daddu
                self.set_lo(rd, self.lo(rs) + self.lo(rt))
            elif fn == 0x38:  # dsll
                self.set_lo(rd, self.lo(rt) << sa)
            elif fn == 0x3A:  # dsrl
                self.set_lo(rd, self.lo(rt) >> sa)
            elif fn == 0x3B:  # dsra
                v = self.lo(rt)
                self.set_lo(rd, (v - ((v & (1 << 63)) << 1)) >> sa)
            elif fn == 0x3C:  # dsll32
                self.set_lo(rd, self.lo(rt) << (sa + 32))
            elif fn == 0x3E:  # dsrl32
                self.set_lo(rd, self.lo(rt) >> (sa + 32))
            elif fn == 0x3F:  # dsra32
                v = self.lo(rt)
                self.set_lo(rd, (v - ((v & (1 << 63)) << 1)) >> (sa + 32))
            else:
                raise NotImplementedError("SPECIAL funct 0x%02x at 0x%08x" % (fn, pc))
            return None
        if op in (2, 3):     # j / jal
            target = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
            if op == 3:
                self.set_lo(31, pc + 8)
            return True, target, False
        if op in (4, 5, 0x14, 0x15):  # beq / bne / beql / bnel
            equal = self.lo(rs) == self.lo(rt)
            taken = equal if op in (4, 0x14) else not equal
            return taken, (pc + 4 + (sext16(imm) << 2)) & M32, op >= 0x14
        if op == 9:          # addiu
            self.set_lo(rt, sext32(self.lo(rs) + sext16(imm)))
        elif op == 0x0C:     # andi
            self.set_lo(rt, self.lo(rs) & imm)
        elif op == 0x0D:     # ori
            self.set_lo(rt, self.lo(rs) | imm)
        elif op == 0x0E:     # xori
            self.set_lo(rt, self.lo(rs) ^ imm)
        elif op == 0x0F:     # lui
            self.set_lo(rt, sext32(imm << 16))
        elif op == 0x19:     # daddiu
            self.set_lo(rt, self.lo(rs) + sext16(imm))
        elif op == 0x1C:     # MMI: only pcpyld
            if fn == 0x09 and sa == 0x0E:
                self.set_full(rd, (self.lo(rs) << 64) | self.lo(rt))
            else:
                raise NotImplementedError("MMI 0x%08x at 0x%08x" % (word, pc))
        elif op == 0x1E:     # lq
            addr = (self.lo(rs) + sext16(imm)) & M32 & ~15
            self.set_full(rt, int.from_bytes(self.read(addr, 16), "little"))
        elif op == 0x1F:     # sq
            addr = (self.lo(rs) + sext16(imm)) & M32 & ~15
            self.write(addr, self.gpr[rt].to_bytes(16, "little"), True)
        elif op in (0x20, 0x24):  # lb / lbu
            v = self.read(self._ea(rs, imm, 1), 1)[0]
            self.set_lo(rt, (v - ((v & 0x80) << 1)) & M64 if op == 0x20 else v)
        elif op in (0x21, 0x25):  # lh / lhu
            v = int.from_bytes(self.read(self._ea(rs, imm, 2), 2), "little")
            self.set_lo(rt, (v - ((v & 0x8000) << 1)) & M64 if op == 0x21 else v)
        elif op in (0x23, 0x27):  # lw / lwu
            v = int.from_bytes(self.read(self._ea(rs, imm, 4), 4), "little")
            self.set_lo(rt, sext32(v) if op == 0x23 else v)
        elif op == 0x37:     # ld
            self.set_lo(rt, int.from_bytes(self.read(self._ea(rs, imm, 8), 8), "little"))
        elif op == 0x28:     # sb
            self.write(self._ea(rs, imm, 1), bytes([self.lo(rt) & 0xFF]), True)
        elif op == 0x29:     # sh
            self.write(self._ea(rs, imm, 2), (self.lo(rt) & 0xFFFF).to_bytes(2, "little"), True)
        elif op == 0x2B:     # sw
            self.write(self._ea(rs, imm, 4), (self.lo(rt) & M32).to_bytes(4, "little"), True)
        elif op == 0x3F:     # sd
            self.write(self._ea(rs, imm, 8), self.lo(rt).to_bytes(8, "little"), True)
        else:
            raise NotImplementedError("opcode 0x%02x (0x%08x) at 0x%08x" % (op, word, pc))
        return None

    def run(self, pc, stop, limit=100000):
        """Run from pc until the next instruction to run is at `stop`."""
        self.pc = pc & M32
        while self.pc != stop:
            if self.pc in self.natives:
                self.natives[self.pc](self)
                self.pc = self.lo(31) & M32
                continue
            self.steps += 1
            if self.steps > limit:
                raise RuntimeError("step limit at 0x%08x" % self.pc)
            word = self.u32(self.pc)
            branch = self.execute(word, self.pc)
            if branch is None:
                self.pc = (self.pc + 4) & M32
                continue
            taken, target, likely = branch
            if likely and not taken:
                self.pc = (self.pc + 8) & M32
                continue
            slot = self.u32(self.pc + 4)
            if self.is_control(slot):
                raise NotImplementedError("branch in a delay slot at 0x%08x" % (self.pc + 4))
            here = self.pc
            self.pc = (here + 4) & M32
            self.execute(slot, here + 4)
            self.pc = target if taken else (here + 8) & M32


# --- assembler for the guard stub source (common/src/pops_resident_guards.S)
# and launcHER's trampoline (launcher/src/pops_trampoline.S)

# Register names as the EE toolchain (mips64r5900el-ps2-elf, n32 ABI) reads
# them: $8..$11 are a4..a7 and $t0..$t3 are $12..$15.
REG = {"$%d" % i: i for i in range(32)}
REG.update({"$" + name: i for i, name in enumerate(
    "zero at v0 v1 a0 a1 a2 a3 a4 a5 a6 a7 t0 t1 t2 t3 "
    "s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra".split())})
REG["$s8"] = 30
SPECIAL = {"sll": 0, "srl": 2, "sra": 3, "dsll32": 0x3C, "dsrl32": 0x3E, "dsra32": 0x3F,
           "dsll": 0x38, "dsrl": 0x3A, "dsra": 0x3B}
THREE = {"or": 0x25, "and": 0x24, "addu": 0x21, "daddu": 0x2D, "xor": 0x26, "nor": 0x27,
         "slt": 0x2A, "sltu": 0x2B, "movz": 0x0A, "movn": 0x0B}
IMM = {"addiu": 9, "daddiu": 0x19, "andi": 0x0C, "ori": 0x0D, "xori": 0x0E}
MEM = {"lw": 0x23, "sw": 0x2B, "lb": 0x20, "lbu": 0x24, "lh": 0x21, "lhu": 0x25,
       "sb": 0x28, "sh": 0x29, "ld": 0x37, "sd": 0x3F, "lq": 0x1E, "sq": 0x1F}


def _num(text):
    return int(text, 0)


def strip_comments(source):
    out, i = [], 0
    while i < len(source):
        if source.startswith("/*", i):
            end = source.index("*/", i + 2)
            out.append("\n" * source.count("\n", i, end))
            i = end + 2
        elif source[i] == "#" and (i == 0 or source[i - 1] == "\n"):
            i = source.index("\n", i) if "\n" in source[i:] else len(source)
        else:
            out.append(source[i])
            i += 1
    return "".join(out)


def _expand(mnem, args):
    """GNU as's expansion of the pseudo-instructions used here, as the EE
    toolchain emits them ("move" is "or rd, rs, $zero")."""
    if mnem == "move":
        return [("or", [args[0], args[1], "$zero"])]
    if mnem == "b":
        return [("beq", ["$zero", "$zero", args[0]])]
    if mnem == "li":
        value = _num(args[1]) & M32
        if value < 0x8000 or value >= 0xFFFF8000:
            return [("addiu", [args[0], "$zero", str(value - (1 << 32) if value >> 31 else value)])]
        if value < 0x10000:
            return [("ori", [args[0], "$zero", str(value)])]
        hi = [("lui", [args[0], str(value >> 16)])]
        return hi + ([("ori", [args[0], args[0], str(value & 0xFFFF)])] if value & 0xFFFF else [])
    return [(mnem, args)]


def assemble(source, base):
    """Assemble the stub file's subset at `base`: (words, symbols).
    Two passes; numeric labels ("1:", "1f"/"1b") as in GNU as."""
    lines = []
    for raw in strip_comments(source).splitlines():
        line = raw.strip()
        while True:
            head = line.split(None, 1)[0] if line else ""
            if head.endswith(":"):
                lines.append(("label", head[:-1]))
                line = line[len(head):].strip()
                continue
            break
        if not line or line.startswith("."):
            continue
        mnem, _, rest = line.partition(" ")
        args = [a.strip() for a in rest.split(",")] if rest.strip() else []
        for insn in _expand(mnem, args):
            lines.append(("insn", insn))
    symbols, numeric = {}, []
    pc = base
    for kind, value in lines:
        if kind == "label":
            if value.isdigit():
                numeric.append((value, pc))
            else:
                symbols[value] = pc
        else:
            pc += 4
    words, pc = [], base

    def local(ref, here):
        name, direction = ref[:-1], ref[-1]
        cands = [a for n, a in numeric if n == name]
        if direction == "f":
            return min(a for a in cands if a > here)
        return max(a for a in cands if a <= here)

    def mem_operand(text):
        off, _, reg = text.partition("(")
        return REG[reg.rstrip(")")], _num(off or "0") & 0xFFFF

    for kind, value in lines:
        if kind == "label":
            continue
        mnem, a = value
        if mnem == "nop":
            w = 0
        elif mnem in SPECIAL:
            w = (REG[a[1]] << 16) | (REG[a[0]] << 11) | ((_num(a[2]) & 31) << 6) | SPECIAL[mnem]
        elif mnem in THREE:
            w = (REG[a[1]] << 21) | (REG[a[2]] << 16) | (REG[a[0]] << 11) | THREE[mnem]
        elif mnem in IMM:
            w = (IMM[mnem] << 26) | (REG[a[1]] << 21) | (REG[a[0]] << 16) | (_num(a[2]) & 0xFFFF)
        elif mnem == "lui":
            w = (0x0F << 26) | (REG[a[0]] << 16) | (_num(a[1]) & 0xFFFF)
        elif mnem in MEM:
            base_reg, off = mem_operand(a[1])
            w = (MEM[mnem] << 26) | (base_reg << 21) | (REG[a[0]] << 16) | off
        elif mnem in ("j", "jal"):
            target = symbols[a[0]] if a[0] in symbols else _num(a[0])
            if ((pc + 4) ^ target) & 0xF0000000:
                raise ValueError("jump out of region at 0x%08x" % pc)
            w = ((2 if mnem == "j" else 3) << 26) | ((target >> 2) & 0x03FFFFFF)
        elif mnem == "jr":
            w = (REG[a[0]] << 21) | 8
        elif mnem in ("bnez", "beqz", "beq", "bne"):
            ref = a[-1]
            target = local(ref, pc) if ref[-1] in "fb" and ref[:-1].isdigit() else symbols[ref]
            rt = REG[a[1]] if mnem in ("beq", "bne") else 0
            w = ((5 if mnem in ("bnez", "bne") else 4) << 26) | (REG[a[0]] << 21) | (rt << 16) | \
                (((target - pc - 4) >> 2) & 0xFFFF)
        elif mnem == "syscall":
            w = 0x0C
        elif mnem == "pcpyld":
            w = (0x1C << 26) | (REG[a[1]] << 21) | (REG[a[2]] << 16) | (REG[a[0]] << 11) | \
                (0x0E << 6) | 0x09
        else:
            raise NotImplementedError("assembler: %s" % mnem)
        words.append(w)
        pc += 4
    return words, symbols
