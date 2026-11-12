#!/usr/bin/env python3
"""What a TROJAN payload finds at POPStarter r13's ten slots, under
POPStarter's own GP1 chain and under launcHER's (pops_resident_gp1_chain in
common/src/pops_resident_engine.c), on tools/r5900_mini.py.

POPStarter's chain is its two resident parts as the launch places them (MAIN
0x983150 -> 0x232790, 0x738 bytes; MAIN 0x983890 -> 0x238a90, 0xd60 bytes),
entered at 0x239490, where its jal at 0x21a63c goes. launcHER's is the built
resident image, entered at the header's gp1_chain_entry, with the two runs
of slots in the core as pops_resident_hook_slot_chain writes them.

Every slot gets a stub, hooked the way the original's loader writes a hook
(`jal stub` for format 1, `j stub` for format 2). A stub overwrites k0 and
k1, as the entry code of every payload looked at does, and returns in one of
the three ways payloads do. At each stub, and at the return to 0x21a640,
every general register and the bytes the chain's own work changes are
recorded; `compare` requires both chains to give the same records.

Needs the user's POPSTARTER.ELF (POPSTARTER_TEST_ELF) for the original side
and a built resident image for launcHER's. Reads both, writes nothing. Not
a console test."""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r5900_mini import M32, M64, Machine, sext16, sext32  # noqa: E402

MAIN_BASE = 0x870000
CORE_BASE = 0x200000
BASE = 0x0143A000
BLOCK1 = (0x983150, 0x232790, 0x738)
BLOCK2 = (0x983890, 0x238A90, 0xD60)
ORIGINAL_ENTRY = 0x239490
RETURN = 0x21A640
# Hook addresses in chain order; the loader's slot number for each.
SLOTS = (0x2327D0, 0x2327D8, 0x2327E0, 0x2327E8, 0x2327F0,
         0x232D08, 0x232D10, 0x232D18, 0x232D20, 0x232D28)
SLOT_NUMBER = (7, 0, 1, 2, 3, 4, 5, 6, 8, 9)
EMPTY = (0x10000001, 0)
STUBS = 0x01500000
ARENA = 0x01420000
PAD = 0x00507000
EMODE, SCRATCH, LID, SCANLINES, BOOT = 0x70003390, 0x70000000, 0x0059C200, 0x0021E454, 0x01FFECB0
CD_INIT = 0x00210540
# Offsets in PopsResidentConfig (tools/test_pops_resident.py mirrors it).
CFG_FLAGS, CFG_VBLANK, CFG_RAM_BASE = 8, 12, 16
CFG_COUNT, CFG_CHEATS = 26, 32
CFG_RESET_VECTOR = 32 + (2 * 256 + 4) * 12 + 4 + 23 * 4
RAM_BASE_PTR, PS1_RAM, CHEAT_AT = 0x70003364, 0x40000000, 0x10
BREAK_HANDLER, BREAK_COUNT, F_BREAK_CALL = 0x01460000, 0x1204, 1 << 8
NAMES = ("zero at v0 v1 a0 a1 a2 a3 a4 a5 a6 a7 t0 t1 t2 t3 "
         "s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra HI LO").split()
K0, K1, RA = 26, 27, 31
# Offset of the emode checks in the chain entry (after its k0/k1 save).
EMODE_AT = 0x18
STYLES = ("jal", "j", "jra", "empty")


def _signed(value, bits=64):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


class Chain(Machine):
    """tools/r5900_mini.py's machine plus the instructions GCC uses in the
    resident's C code that it does not have: HI/LO, mult and div (with the
    R5900's three-operand mult), variable shifts, dsubu and the compares
    with zero. Anything else still raises."""

    def __init__(self):
        super().__init__()
        self.hi = self.lo_ = 0

    def execute(self, word, pc):
        op, fn = word >> 26, word & 63
        rs, rt, rd = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
        if op == 0:
            a, b = self.lo(rs), self.lo(rt)
            if fn == 4:       # sllv
                self.set_lo(rd, sext32(b << (a & 31)))
            elif fn == 6:     # srlv
                self.set_lo(rd, sext32((b & M32) >> (a & 31)))
            elif fn == 7:     # srav
                self.set_lo(rd, sext32(_signed(b, 32) >> (a & 31)))
            elif fn == 0x10:  # mfhi
                self.set_lo(rd, self.hi)
            elif fn == 0x11:  # mthi
                self.hi = a
            elif fn == 0x12:  # mflo
                self.set_lo(rd, self.lo_)
            elif fn == 0x13:  # mtlo
                self.lo_ = a
            elif fn in (0x18, 0x19):  # mult / multu, rd = LO on the R5900
                if fn == 0x18:
                    product = _signed(a, 32) * _signed(b, 32)
                else:
                    product = (a & M32) * (b & M32)
                self.lo_, self.hi = sext32(product), sext32(product >> 32)
                self.set_lo(rd, self.lo_)
            elif fn in (0x1A, 0x1B):  # div / divu
                if fn == 0x1A:
                    x, y = _signed(a, 32), _signed(b, 32)
                else:
                    x, y = a & M32, b & M32
                if y == 0:
                    quotient, remainder = (1 if fn == 0x1A and x < 0 else -1), x
                else:
                    quotient = abs(x) // abs(y) * (-1 if (x < 0) != (y < 0) else 1)
                    remainder = x - quotient * y
                self.lo_, self.hi = sext32(quotient), sext32(remainder)
            elif fn == 0x14:  # dsllv
                self.set_lo(rd, b << (a & 63))
            elif fn == 0x16:  # dsrlv
                self.set_lo(rd, b >> (a & 63))
            elif fn == 0x17:  # dsrav
                self.set_lo(rd, _signed(b) >> (a & 63))
            elif fn == 0x2F:  # dsubu
                self.set_lo(rd, a - b)
            else:
                return super().execute(word, pc)
            return None
        if op == 1 and rt in (0, 1, 2, 3):  # bltz / bgez / bltzl / bgezl
            negative = _signed(self.lo(rs)) < 0
            return (negative if rt in (0, 2) else not negative,
                    (pc + 4 + (sext16(word & 0xFFFF) << 2)) & M32, rt >= 2)
        if op in (6, 7, 0x16, 0x17):        # blez / bgtz / blezl / bgtzl
            positive = _signed(self.lo(rs)) > 0
            return (positive if op in (7, 0x17) else not positive,
                    (pc + 4 + (sext16(word & 0xFFFF) << 2)) & M32, op >= 0x16)
        return super().execute(word, pc)


def j(target):
    return 0x08000000 | ((target >> 2) & 0x03FFFFFF)


def jal(target):
    return 0x0C000000 | ((target >> 2) & 0x03FFFFFF)


def slot_words(style, index):
    """The two words of slot `index` (chain order) for a stub of `style`."""
    stub = STUBS + 0x40 * index
    if style == "empty":
        return EMPTY
    return (jal(stub) if style == "jal" else j(stub), 0)


def stub_words(style, index):
    hook = SLOTS[index]
    words = [0x3C1ADEAD, 0x375A0000 | index,   # lui k0, 0xdead ; ori k0, k0, index
             0x3C1BBEEF, 0x377B0000 | index]   # lui k1, 0xbeef ; ori k1, k1, index
    if style == "jal":
        words += [0x03E00008, 0]               # jr ra
    elif style == "j":
        words += [j(hook + 8), 0]              # ra untouched
    else:                                      # the hard-coded form: ra = hook + 8, jr ra
        words += [0x3C1F0000 | ((hook + 8) >> 16), 0x37FF0000 | ((hook + 8) & 0xFFFF),
                  0x03E00008, 0]
    return words


def stub_bytes(style, index):
    return b"".join(struct.pack("<I", w) for w in stub_words(style, index))


def run(machine, pc, stop, watch, limit=200000):
    """Machine.run with `watch`: address -> function called before the
    instruction there runs."""
    m = machine
    m.pc = pc & M32
    m.steps = 0
    while m.pc != stop:
        if m.pc in watch:
            watch[m.pc](m)
        if m.pc in m.natives:
            m.natives[m.pc](m)
            m.pc = m.lo(31) & M32
            continue
        m.steps += 1
        if m.steps > limit:
            raise RuntimeError("step limit at 0x%08x" % m.pc)
        branch = m.execute(m.u32(m.pc), m.pc)
        if branch is None:
            m.pc = (m.pc + 4) & M32
            continue
        taken, target, likely = branch
        if likely and not taken:
            m.pc = (m.pc + 8) & M32
            continue
        here = m.pc
        slot = m.u32(here + 4)
        if m.is_control(slot):
            raise NotImplementedError("branch in a delay slot at 0x%08x" % (here + 4))
        m.pc = (here + 4) & M32
        m.execute(slot, here + 4)
        m.pc = target if taken else (here + 8) & M32


def _memory(m):
    return (m.read(EMODE, 1)[0], m.u32(SCRATCH), struct.unpack("<H", m.read(LID, 2))[0],
            m.read(PAD + 0x28, 1)[0], m.read(PAD + 0xB8, 1)[0], m.u32(SCANLINES),
            m.read(PS1_RAM + CHEAT_AT, 1)[0], m.u32(BREAK_COUNT))


def _prepare(m, pad, styles, lid, emode, stubs=True):
    m.record = False
    m.write(PAD + 2, struct.pack("<H", pad))
    m.write(EMODE, bytes([emode]))
    m.write(LID, struct.pack("<H", lid))
    m.put32(SCANLINES, 0x8CA42158)
    m.write(BOOT, b"pops:/disc/disc0".ljust(0x60, b"\0"))
    for index, style in enumerate(styles):
        if stubs and style != "empty":
            m.write(STUBS + 0x40 * index, stub_bytes(style, index))
    m.swaps = []

    def cd_init(mm):
        mm.swaps.append(mm.lo(4) & M32)
        mm.set_lo(2, 0)

    m.natives[CD_INIT] = cd_init
    for r in range(1, 32):
        m.set_full(r, (0x0F0E0D0C0B0A0900 + r << 64) | 0x1122334400000000 | (0x01010101 * r))
    m.set_lo(28, 0x0050A670)
    m.set_lo(29, 0x01F7FF00)
    m.set_lo(31, 0x0021A644)  # the jal at 0x21a63c
    m.hi, m.lo_ = 0x4848484848484848, 0x4C4C4C4C4C4C4C4C
    m.given = tuple(m.gpr) + (m.hi, m.lo_)


def _go(m, entry, styles, stop=RETURN):
    records = []

    def at_stub(index):
        def record(mm):
            records.append((index, tuple(mm.lo(r) for r in range(32)) + (mm.hi, mm.lo_),
                            _memory(mm)))
        return record

    watch = {STUBS + 0x40 * index: at_stub(index)
             for index, style in enumerate(styles) if style != "empty"}
    run(m, entry, stop, watch)
    final = (tuple(m.gpr[r] for r in range(32)) + (m.hi, m.lo_), _memory(m), tuple(m.swaps))
    return records, final


def original(main, core, pad, styles, lid=0x0200, emode=0x55):
    """POPStarter's chain. `main`: its decoded MAIN image (0x870000);
    `core`: POPS's loaded image (0x200000) or None."""
    m = Chain()
    if core:
        m.write(CORE_BASE, core)
    for source, target, size in (BLOCK1, BLOCK2):
        m.write(target, main[source - MAIN_BASE:source - MAIN_BASE + size])
    m.put32(0x232D30, j(BLOCK2[1]))  # written at launch (0x874a18..)
    for index, style in enumerate(styles):
        if style != "empty":           # an unhooked slot is left as shipped
            m.put32(SLOTS[index], slot_words(style, index)[0])
            m.put32(SLOTS[index] + 4, 0)
    _prepare(m, pad, styles, lid, emode)
    return _go(m, ORIGINAL_ENTRY, styles)


def header(image):
    magic, version, size, file_size, image_size = struct.unpack_from("<IHHII", image, 0)
    if magic != 0x5352484C or size < 124 or file_size != len(image):
        raise ValueError("not a resident image with the slot chain entries")
    config = struct.unpack_from("<I", image, 20)[0]
    chain, resume_a, resume_b = struct.unpack_from("<3I", image, 112)
    return image_size, config, chain, resume_a, resume_b


def _resident(image, core, reset_vector, cheat, break_call=False):
    image_size, config, chain, resume_a, resume_b = header(image)
    m = Chain()
    if core:
        m.write(CORE_BASE, core)
    m.write(BASE, bytes(image) + bytes(image_size - len(image)))
    m.put32(config + CFG_VBLANK, 0x0021CD68)
    m.put32(config + CFG_RAM_BASE, RAM_BASE_PTR)
    m.put32(config + CFG_RESET_VECTOR, reset_vector)
    if cheat:  # one PS1 code, 30000010 005A, and POPS's RAM base stored
        m.put32(config + CFG_FLAGS, 1)
        m.write(config + CFG_COUNT, struct.pack("<H", 1))
        m.write(config + CFG_CHEATS, struct.pack("<IIBBBx", CHEAT_AT, 0x5A, 0x30, 0, 0))
        m.put32(RAM_BASE_PTR, PS1_RAM)
    if break_call:
        # A breakpoint handler that counts its calls (k0 and k1 only, as the
        # original's), and the flag the launcher sets for one.
        m.put32(config + CFG_FLAGS, m.u32(config + CFG_FLAGS) | F_BREAK_CALL)
        words = (0x3C1A0000, 0x8F5B0000 | BREAK_COUNT, 0x277B0001, 0xAF5B0000 | BREAK_COUNT,
                 0x03E00008, 0)
        m.write(BREAK_HANDLER, b"".join(struct.pack("<I", w) for w in words))
    return m, chain, resume_a, resume_b


def built(image, core, pad, styles, lid=0x0200, emode=0x55, reset_vector=0xBFC00000, cheat=False,
          break_call=None):
    """launcHER's chain: the built resident image and the two runs of slots
    as pops_resident_hook_slot_chain writes them. break_call: None, or the
    resident flag for a breakpoint handler is set and the slot at 0x232d08
    holds the call ("slot") or does not ("flag only")."""
    m, chain, resume_a, resume_b = _resident(image, core, reset_vector, cheat, bool(break_call))
    for run_index, resume in enumerate((resume_a, resume_b)):
        for i in range(5):
            index = 5 * run_index + i
            first, second = slot_words(styles[index], index)
            m.put32(SLOTS[index], first)
            m.put32(SLOTS[index] + 4, second)
        m.put32(SLOTS[5 * run_index] + 0x28, j(resume))
        m.put32(SLOTS[5 * run_index] + 0x2C, 0)
    if break_call == "slot":
        m.put32(SLOTS[5], jal(BREAK_HANDLER))
    _prepare(m, pad, styles, lid, emode)
    return _go(m, chain, styles) + (m.given,)


def legacy(image, core, pad, lid=0x0200, emode=0x55, reset_vector=0xBFC00000, cheat=False,
           break_call=False):
    """The image's GP1 entry for a launch without the slots (gp1_entry),
    which returns to the jal's $ra."""
    m, _, _, _ = _resident(image, core, reset_vector, cheat, break_call)
    _prepare(m, pad, ("empty",) * 10, lid, emode)
    entry = struct.unpack_from("<I", image, 52)[0]
    return _go(m, entry, ("empty",) * 10, stop=0x0021A644) + (m.given,)


def original_launched(core_after, arena_after, pad, styles, lid=0x0200, emode=0x55):
    '''POPStarter's chain on memory its own TROJAN loader left: the POPS
    image with its two parts placed and the hooks written (from 0x200000),
    and the payloads it copied (from ARENA).'''
    m = Chain()
    m.write(ARENA, arena_after)
    m.write(CORE_BASE, core_after)
    _prepare(m, pad, styles, lid, emode, stubs=False)
    return _go(m, ORIGINAL_ENTRY, styles)


def launched(image, staged_core, arena, pad, styles, lid=0x0200, emode=0x55,
             reset_vector=0xBFC00000):
    '''launcHER's chain as a launch leaves it: the staged core after
    pops_resident_hook_slot_chain, the payloads pops_trojan_copy_out placed
    (from ARENA), the resident image; entered where the jal at 0x21a63c
    points.'''
    m, chain, _, _ = _resident(image, None, reset_vector, False)
    image_bytes = m.read(BASE, header(image)[0])
    m.write(ARENA, arena)
    m.write(BASE, image_bytes)
    m.write(CORE_BASE, staged_core)
    word = m.u32(0x0021A63C)
    assert word == jal(chain), "0x21a63c is %#010x, not the jal to the chain entry" % word
    _prepare(m, pad, styles, lid, emode, stubs=False)
    return _go(m, chain, styles)


def cases():
    """(pad buttons, ten styles, lid, emode): the combos the chain acts on
    between the slots, and each way a payload returns, on every slot."""
    pads = (0xFFFF, 0xF6FE, 0xF9FE, 0xBCFE, 0xF5FE, 0xFAFE, 0xECFE, 0x0000)
    out = []
    for pad in pads:
        for style in ("jal", "j", "jra"):
            out.append((pad, (style,) * 10, 0x0200, 0x55))
        out.append((pad, ("jal", "empty", "j", "empty", "jra", "jra", "empty", "j", "empty", "jal"),
                    0x0200, 0x55))
        out.append((pad, ("empty", "j", "empty", "jra", "empty", "empty", "jal", "empty", "jra",
                          "empty"), 0x0200, 0x55))
    for index in range(10):  # one hooked slot at a time, each return form
        for style in ("jal", "j", "jra"):
            styles = ["empty"] * 10
            styles[index] = style
            out.append((0xBCFE if index % 2 else 0xF6FE, tuple(styles), 0x0200, 0x55))
    out.append((0xFFFF, ("empty",) * 10, 0x0200, 0x55))
    return out


def compare(image, main, core=None):
    """Runs every case on both chains. Returns (cases, slot records); raises
    AssertionError naming the first difference."""
    names = NAMES
    total = 0
    # The entry's emode checks (its 16 words after the k0/k1 save) are the
    # original's first 16 words of its first part, 0x232790..0x2327cf. Read
    # from the user's POPSTARTER.ELF here; nothing of it is kept in the tree.
    entry = header(image)[2] - BASE + EMODE_AT
    start = BLOCK1[0] - MAIN_BASE
    assert image[entry:entry + 64] == main[start:start + 64], \
        "the entry's emode checks are not the original's words"
    for pad, styles, lid, emode in cases():
        want = original(main, core, pad, styles, lid, emode)
        got = built(image, core, pad, styles, lid, emode)
        where = "pad %#06x, slots %s" % (pad, ",".join(styles))
        assert [r[0] for r in got[0]] == [r[0] for r in want[0]], \
            "%s: slot order %r, the original's %r" % (where, [r[0] for r in got[0]],
                                                      [r[0] for r in want[0]])
        assert [r[0] for r in want[0]] == [i for i, s in enumerate(styles) if s != "empty"], where
        for (index, regs, mem), (_, want_regs, want_mem) in zip(got[0], want[0]):
            for r in range(34):
                assert regs[r] == want_regs[r], "%s: %s at slot %d (hook %#x) is %#x, the original's %#x" % (
                    where, names[r], SLOT_NUMBER[index], SLOTS[index], regs[r], want_regs[r])
            assert mem == want_mem, "%s: memory at slot %d: %r, the original's %r" % (
                where, SLOT_NUMBER[index], mem, want_mem)
        for r in range(34):
            assert got[1][0][r] == want[1][0][r], "%s: %s at the return is %#x, the original's %#x" % (
                where, names[r], got[1][0][r], want[1][0][r])
        assert got[1][1:] == want[1][1:], "%s: memory at the return: %r, the original's %r" % (
            where, got[1][1:], want[1][1:])
        total += len(want[0])
    return len(cases()), total


def swap_frame(image, main, core=None, styles=("j",) * 10):
    """The one frame known to differ: the lid is open and the close combo is
    read, so POPStarter's block calls POPS's disc init between the two runs.
    Returns the register names that differ at the slots after it and at the
    return, and whether the chain's stores are equal."""
    want = original(main, core, 0x7CFE, styles, lid=0x1000)
    got = built(image, core, 0x7CFE, styles, lid=0x1000)
    assert len(want[1][2]) == 1 and len(got[1][2]) == 1, "one disc init each"
    assert [r[0] for r in got[0]] == [r[0] for r in want[0]]
    at_slots, at_return = {}, set()
    for (index, regs, _), (_, want_regs, _) in zip(got[0], want[0]):
        names = {NAMES[r] for r in range(34) if regs[r] != want_regs[r]}
        if names:
            at_slots[SLOT_NUMBER[index]] = names
    at_return = {NAMES[r] for r in range(34) if got[1][0][r] != want[1][0][r]}
    stores = all(g[2] == w[2] for g, w in zip(got[0], want[0])) and got[1][1] == want[1][1]
    return at_slots, at_return, stores


def _sext(value, bits):
    value &= (1 << bits) - 1
    return (value - (1 << bits) if value >> (bits - 1) else value) & M64


def self_check(image, core=None):
    """The built chain alone, against what the original's instructions
    around the slots are known to leave (compare() checks that knowledge
    against the original itself). Returns (cases, slot records)."""
    total = 0
    vector = 0xBFC0D8D0
    for pad, styles, lid, emode in cases():
        for cheat in (False, True):
            records, final, given = built(image, core, pad, styles, lid, emode, vector, cheat)
            where = "pad %#06x, slots %s" % (pad, ",".join(styles))
            hooked = [i for i, style in enumerate(styles) if style != "empty"]
            assert [r[0] for r in records] == hooked, "%s: slot order %r" % (where, [r[0] for r in records])
            ra = RETURN
            previous = None
            for index, regs, mem in records:
                style = styles[index]
                first_of_run = previous is None or (index >= 5) != (previous >= 5)
                if not first_of_run:
                    k0, k1 = _sext(0xDEAD0000 | previous, 32), _sext(0xBEEF0000 | previous, 32)
                elif index < 5:   # the emode checks
                    k0, k1 = _sext(pad, 16), _sext(0xF9FE, 16)
                    if pad == 0xF6FE:
                        k0, k1 = 0x70000000, _sext(0xF6FE, 16)
                    elif pad == 0xF9FE:
                        k0, k1 = 0x70000000, 1
                else:             # the reset check
                    k0, k1 = _sext(pad, 16), _sext(0xBCFE, 16)
                    if pad == 0xBCFE:
                        k0, k1 = 0x70000000, _sext(vector, 32)
                if style == "jal":
                    ra = SLOTS[index] + 8
                want = list(given[r] & M64 for r in range(32)) + list(given[32:])
                want[K0], want[K1], want[RA] = k0, k1, ra
                for r in range(34):
                    assert regs[r] == want[r], "%s: %s at slot %d is %#x, not %#x" % (
                        where, NAMES[r], SLOT_NUMBER[index], regs[r], want[r])
                if style == "jra":
                    ra = SLOTS[index] + 8
                # The chain's work around the slots: the emode checks before
                # the first run; the rest of the always-live block, the pad
                # flags and the reset store between the runs; cheats after.
                want_emode = {0xF6FE: 0, 0xF9FE: 1}.get(pad, emode)
                assert mem[0] == want_emode, "%s: emode at slot %d" % (where, SLOT_NUMBER[index])
                assert mem[3] == mem[4] == (1 if index >= 5 else 0), "%s: pad flags at slot %d" % (
                    where, SLOT_NUMBER[index])
                assert mem[1] == (vector if index >= 5 and pad == 0xBCFE else 0), \
                    "%s: reset store at slot %d" % (where, SLOT_NUMBER[index])
                assert mem[6] == 0, "%s: cheats ran before slot %d" % (where, SLOT_NUMBER[index])
                previous = index
            want = list(given)
            want[RA] = (given[RA] & (M64 << 64)) | RETURN
            for r in range(34):
                assert final[0][r] == want[r], "%s: %s at the return is %#x, not %#x" % (
                    where, NAMES[r], final[0][r], want[r])
            assert final[1][6] == (0x5A if cheat else 0), "%s: cheats after the slots" % where
            assert final[2] == (), where
            total += len(records)
    # With every slot empty the chain does what the image's other GP1 entry
    # does, on the disc swap frame too.
    frames = [(pad, 0x0200) for pad in (0xFFFF, 0xF6FE, 0xF9FE, 0xBCFE, 0xF5FE, 0xFAFE, 0xECFE, 0)]
    frames += [(0x7CFE, 0x1000), (0xFFFF, 0x1000)]
    for pad, lid in frames:
        for cheat in (False, True):
            chain = built(image, core, pad, ("empty",) * 10, lid, 0x55, vector, cheat)
            other = legacy(image, core, pad, lid, 0x55, vector, cheat)
            assert chain[1][1:] == other[1][1:], "pad %#06x: the two GP1 entries differ: %r, %r" % (
                pad, chain[1][1:], other[1][1:])
            for r in range(1, 34):
                if r != RA:
                    assert chain[1][0][r] == other[1][0][r] == chain[2][r], "pad %#06x: %s" % (pad, NAMES[r])
            assert len(chain[1][2]) == (1 if pad == 0x7CFE else 0), "disc init calls"
        # The breakpoint handler call is the slot's word under the chain and
        # a flag otherwise: once per pass either way, never from both.
        chain = built(image, core, pad, ("empty",) * 10, lid, 0x55, vector, True, "slot")
        other = legacy(image, core, pad, lid, 0x55, vector, True, True)
        assert chain[1][1][7] == 1 and chain[1][1:] == other[1][1:], \
            "pad %#06x: breakpoint handler calls %d, %d" % (pad, chain[1][1][7], other[1][1][7])
        idle = built(image, core, pad, ("empty",) * 10, lid, 0x55, vector, True, "flag only")
        assert idle[1][1][7] == 0, "pad %#06x: the chain called the handler from the flag" % pad
    return 2 * len(cases()), total


def main():
    if len(sys.argv) != 2:
        print("usage: [POPSTARTER_TEST_ELF=... [POPS_TEST_ELF=...]] pops_trojan_chain.py pops_resident.bin")
        return 2
    image = Path(sys.argv[1]).read_bytes()
    report(image)
    return 0


def report(image):
    """self_check, and compare when POPSTARTER_TEST_ELF is set; prints one
    line each (tools/check_pops_resident_image.py calls this)."""
    import os
    count, slots = self_check(image)
    print("resident TROJAN slot chain: PASS (%d cases, %d slot records: order, every register at "
          "each slot and at the return to 0x21a640, the work around the slots; same stores as "
          "the other GP1 entry with empty slots; emulated, not a console)" % (count, slots))
    if not os.environ.get("POPSTARTER_TEST_ELF"):
        return
    from trace_original_pops_io import decode_main
    main_image = decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
    core = None
    if os.environ.get("POPS_TEST_ELF"):
        from trace_original_pops_trojan import pops_core
        core = pops_core()
    count, slots = compare(image, main_image, core)
    at_slots, at_return, stores = swap_frame(image, main_image, core)
    print("original's chain vs the built TROJAN slot chain: PASS (%d cases, %d slot records, every "
          "register and the chain's stores equal; on the disc swap frame %s differ at slots %s "
          "and %s at the return, stores %s; emulated, not a console)" % (
              count, slots, "/".join(sorted(set().union(*at_slots.values()))) or "none",
              ",".join(str(n) for n in at_slots) or "none", "/".join(sorted(at_return)) or "none",
              "equal" if stores else "DIFFER"))


if __name__ == "__main__":
    sys.exit(main())
