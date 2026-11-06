#!/usr/bin/env python3
"""What POPStarter r13's nine misaligned-read guards must do, and a runner
that checks a set of stubs against it (tools/r5900_mini.py executes them).

POPStarter rewrites the same nine POPS places on every launch (0x874864..
0x874998): a load or store becomes a jump into its resident code, which
forces the base register to a word boundary and then does what POPS did
(the 0x202250 store is instead moved into 0x00c70000..0x00c7ffff, and the
branch at 0x204160 is redirected). The model below is that: POPS's own
instructions, the alignment, and the scratch values the original leaves in
three registers. Used by tools/test_pops_launch_hooks.py and
tools/check_pops_resident_image.py. Not a console test."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r5900_mini import M32, M64, AddressError, Machine, assemble, sext32

ROOT = Path(__file__).resolve().parent.parent
STUBS = ROOT / "common/src/pops_resident_guards.S"
BASE, LIMIT = 0x0143A000, 0x01460000

# POPS_GUARD_* order (common/include/pops_resident.h): site, POPS's word,
# POPS's next word, whether that next word stays (only the branch at
# 0x204160 keeps its delay slot), and the stub's symbol.
SITES = [
    (0x0021C58C, 0x8C820000, 0x24840004, False, "pops_resident_guard_21c58c"),
    (0x0021C768, 0x8C440000, 0x24420004, False, "pops_resident_guard_21c768"),
    (0x002082A0, 0x8C660000, 0x14C00003, False, "pops_resident_guard_2082a0"),
    (0x00204AE0, 0x8C630000, 0x3C023C02, False, "pops_resident_guard_204ae0"),
    (0x00204178, 0x8C650000, 0x00053E82, False, "pops_resident_guard_204178"),
    (0x00204160, 0x10000006, 0x0040282D, True, "pops_resident_guard_204160"),
    (0x00202250, 0x03E00008, 0xAC4A0000, False, "pops_resident_guard_202250"),
    (0x0021C5DC, 0xAE052260, 0xAE032270, False, "pops_resident_guard_21c5dc"),
    (0x0021C5A8, 0xAD422288, 0xAD452260, False, "pops_resident_guard_21c5a8"),
]
# Words the stubs return to or repeat (left alone by the hooks).
CONTEXT = {0x0021C594: 0x00471824, 0x0021C770: 0xAFA20000, 0x002082A8: 0x00000000,
           0x002082AC: 0x0808207C, 0x002082B0: 0x24020001, 0x002082B4: 0x00C00008,
           0x00204AE8: 0x34428001, 0x00204180: 0x00051542, 0x00202238: 0x3C02E060,
           0x0020224C: 0x00431021, 0x0021C5E4: 0x42000038, 0x0021C5B0: 0xAD432270}
RA_SENTINEL = 0x00202318
LOAD_AREAS = (0x00100000, 0x20100000, 0x80100000, 0x00C00000)


def assembled_stubs(base=0x0143B000):
    """The stub file assembled at `base`: (words, {symbol: address})."""
    return assemble(STUBS.read_text(), base)


def expect(index, regs, word_at):
    """Registers (128-bit), stores and the next PC the original leaves.
    Raises AddressError where the console would take one."""
    out = list(regs)

    def setlo(r, value):
        out[r] = (out[r] & (M64 << 64)) | (value & M64)

    stores = []
    lo32 = lambda r: regs[r] & M32
    if index == 0:            # lw $v0,0($a0) / addiu $a0,$a0,4
        a = lo32(4) & ~3
        setlo(2, sext32(word_at(a))); setlo(4, sext32(a + 4)); nxt = 0x0021C594
    elif index == 1:          # lw $a0,0($v0) / addiu $v0,$v0,4
        a = lo32(2) & ~3
        setlo(4, sext32(word_at(a))); setlo(2, sext32(a + 4)); nxt = 0x0021C770
    elif index == 2:          # lw $a2,0($v1) / bnez $a2,0x2082b4
        a = lo32(3) & ~3
        w = word_at(a)
        setlo(3, sext32(a)); setlo(6, sext32(w)); nxt = 0x002082B4 if w else 0x002082AC
    elif index == 3:          # lw $v1,0($v1) / lui $v0,0x3c02
        a = lo32(3) & ~3
        setlo(3, sext32(word_at(a))); setlo(2, 0x3C020000); nxt = 0x00204AE8
    elif index == 4:          # lw $a1,0($v1) / srl $a3,$a1,26
        a = lo32(3) & ~3
        w = word_at(a)
        setlo(3, sext32(a)); setlo(5, sext32(w)); setlo(7, w >> 26); nxt = 0x00204180
    elif index == 5:          # b (delay slot move $a1,$v0) to the srl
        setlo(5, regs[2] & M64); setlo(7, lo32(2) >> 26); nxt = 0x00204180
    elif index == 6:          # jr $ra / sw $t2,0($v0), moved into 0x00c7xxxx
        addr = 0x00C70000 | (regs[2] & 0xFFFF)
        if addr & 3:
            raise AddressError("misaligned store")
        out[2] = addr                       # all 128 bits (the original's lq)
        setlo(16, 0x01440000)               # scratch
        stores = [(addr, lo32(10).to_bytes(4, "little"))]
        nxt = regs[31] & M32
    elif index == 7:          # sw $a1,0x2260($s0) / sw $v1,0x2270($s0)
        a = lo32(16) & ~3
        setlo(16, sext32(a)); setlo(2, 0xFFFFFFFC)
        stores = [((a + 0x2260) & M32, lo32(5).to_bytes(4, "little")),
                  ((a + 0x2270) & M32, lo32(3).to_bytes(4, "little"))]
        nxt = 0x0021C5E4
    elif index == 8:          # sw $v0,0x2288($t2) / sw $a1,0x2260($t2)
        a = lo32(10) & ~3
        setlo(10, sext32(a)); setlo(16, 0xFFFFFFFC)
        stores = [((a + 0x2288) & M32, lo32(2).to_bytes(4, "little")),
                  ((a + 0x2260) & M32, lo32(5).to_bytes(4, "little"))]
        nxt = 0x0021C5B0
    else:
        raise IndexError(index)
    return out, stores, nxt


BASE_REG = {0: 4, 1: 2, 2: 3, 3: 3, 4: 3, 7: 16, 8: 10}


def random_state(index, rng):
    regs = [0] + [rng.getrandbits(128) for _ in range(31)]
    if index in BASE_REG:
        r = BASE_REG[index]
        addr = rng.choice(LOAD_AREAS) + rng.randrange(0x40000)
        regs[r] = (regs[r] & ~M32) | addr
    if index == 6:
        regs[31] = (regs[31] & ~M64) | RA_SENTINEL
        if rng.random() < 0.9:
            regs[2] &= ~3
    return regs


def check_stubs(core_words, image, image_base, rng, trials=300, own_scratch=None):
    """Run each guard from its POPS site, where `core_words` (address ->
    word) holds the hooked words, with `image` loaded at `image_base`, on
    random registers and memory; compare with expect(). Stores inside
    BASE..LIMIT are the stub's own scratch: allowed only inside
    `own_scratch` (a range), and never compared. Returns the run count."""
    runs = 0
    for index in range(len(SITES)):
        for _ in range(trials):
            m = Machine()
            m.write(image_base, image)
            for addr, word in core_words.items():
                m.put32(addr, word)
            regs = random_state(index, rng)
            m.gpr = list(regs)
            words = {}
            if index in BASE_REG and index < 5:
                a = regs[BASE_REG[index]] & M32 & ~3
                words[a] = 0 if rng.random() < 0.25 else rng.getrandbits(32)
                m.put32(a, words[a])
            word_at = lambda a: words[a]
            try:
                want = expect(index, regs, word_at)
            except AddressError:
                want = None
            site = SITES[index][0]
            try:
                m.run(site, want[2] if want else RA_SENTINEL, limit=64)
            except AddressError:
                if want is None:
                    runs += 1
                    continue
                raise
            if want is None:
                raise AssertionError("guard %d: expected an address error" % index)
            regs_out, stores, nxt = want
            got = [(a, b) for a, b in m.stores if not BASE <= a < LIMIT]
            mine = [(a, b) for a, b in m.stores if BASE <= a < LIMIT]
            for a, b in mine:
                if not own_scratch or not (own_scratch[0] <= a and a + len(b) <= own_scratch[1]):
                    raise AssertionError("guard %d stores into the resident at 0x%08x" % (index, a))
            if m.pc != nxt:
                raise AssertionError("guard %d: next pc 0x%08x, want 0x%08x" % (index, m.pc, nxt))
            for r in range(32):
                if m.gpr[r] != regs_out[r]:
                    raise AssertionError("guard %d: $%d = 0x%032x, want 0x%032x"
                                         % (index, r, m.gpr[r], regs_out[r]))
            if got != stores:
                raise AssertionError("guard %d: stores %r, want %r" % (index, got, stores))
            runs += 1
    return runs


def hooked_words(entries):
    """The words a hook leaves at each site (and the word after it), given
    the stub entry per guard, plus the context words."""
    words = dict(CONTEXT)
    for (site, _, nxt, keep, _), entry in zip(SITES, entries):
        words[site] = 0x08000000 | ((entry >> 2) & 0x03FFFFFF)
        words[site + 4] = nxt if keep else 0
    return words


if __name__ == "__main__":
    words, symbols = assembled_stubs()
    image = b"".join(w.to_bytes(4, "little") for w in words)
    n = check_stubs(hooked_words([symbols[s[4]] for s in SITES]), image, 0x0143B000,
                    random.Random(0x47554152))
    print("assembled guard stubs vs model: PASS (%d runs)" % n)
