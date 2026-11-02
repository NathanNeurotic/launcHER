#!/usr/bin/env python3
"""What POPStarter r13's recompiler hook and its $RECOMPILER_ADDON_0..4
commands do, and runners that check code against it (tools/r5900_mini.py
executes the code). Not a console test.

On every launch POPStarter writes "j <its block>; nop" over two loads in
POPS's recompiler epilogue (0x2075e8: ld $s2,0x20($sp) / ld $s3,0x28($sp)).
The block reads the flag word at PS1 0xb890 and runs what the commands put
in it: flag set, ADDON_1, then ADDON_2 and from there ADDON_0 (without
ADDON_2 the block ends there, so ADDON_0 is skipped); flag clear, ADDON_0.
It reloads $s0..$s5 from POPS's frame and returns to 0x2075f4 with
$ra = 0x2075f4. ADDON_3 and ADDON_4 instead turn POPS's two emit points
(0x206318 and 0x205d1c) into jumps to code that converts the emitted word
as ADDON_0 does and stores it with swr (ADDON_3 as 0, word, 0, 0; ADDON_4
the word alone). The model below is that, quirks included (each one is in
common/src/pops_resident_recompiler.S and docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md).
Used by tools/test_pops_launch_hooks.py, which runs launcHER's code (as
assembled here, and as built) and the original's own code against it."""
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r5900_mini import M32, M64, Machine, assemble, sext32  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "common/src/pops_resident_recompiler.S"
ABI = ROOT / "common/include/pops_resident_abi.h"
BASE, LIMIT = 0x0143A000, 0x01460000

HOOK, RESUME = 0x002075E8, 0x002075F4
HOOK_PRISTINE = (0xDFB20020, 0xDFB30028)      # ld $s2,0x20($sp) / ld $s3,0x28($sp)
START, LENGTH, FLAG = 0x0100B878, 0x0100B87C, 0x0100B890
PS1_RAM = 0x01000000
# POPS's emit points: where the code resumes, the register that holds the
# word, the register that points where it goes, and POPS's two words there.
EMITS = {0x00206318: (0x00206320, 2, 17, (0xAE220000, 0x26310004)),
         0x00205D1C: (0x00205D24, 4, 12, (0x00822025, 0xAD840000))}
# PopsResidentHeader.recompiler_emit order (POPS_EMIT_*).
EMIT_SYMBOLS = ["pops_resident_recompiler_addon3_206318", "pops_resident_recompiler_addon3_205d1c",
                "pops_resident_recompiler_addon4_206318", "pops_resident_recompiler_addon4_205d1c"]

BREAK7, BREAK6 = 0x0007000D, 0x0006000D
LI_T2_A0, LI_T2_B0, JR_T2, JR_RA = 0x240A00A0, 0x240A00B0, 0x01400008, 0x03E00008


def li_t1(n):
    return 0x24090000 | n


def abi_defines():
    """The numbers pops_resident_abi.h gives the assembly, by name."""
    text = ABI.read_text()
    return {m.group(1): int(m.group(2), 0)
            for m in re.finditer(r"^#define\s+(\w+)\s+(0x[0-9A-Fa-f]+|\d+)\b", text, re.M)}


DEFINES = abi_defines()
FLAGS_OFFSET = DEFINES["POPS_RESIDENT_FLAGS_OFFSET"]
F_ADDON = [DEFINES["POPS_RES_F_RECOMPILER_%d" % n] for n in range(3)]


def config_flags(addons):
    """PopsResidentConfig.flags for a set of commands (bit n: ADDON_n)."""
    return sum(F_ADDON[n] for n in range(3) if addons >> n & 1)


def assembled(base, config, save):
    """pops_resident_recompiler.S assembled at `base`, with
    pops_resident_config at `config` and pops_resident_recompiler_save at
    `save`: (words, {symbol: address})."""
    return assemble(SOURCE.read_text(), base,
                    {"pops_resident_config": config, "pops_resident_recompiler_save": save}, DEFINES)


def jump(target):
    return 0x08000000 | ((target >> 2) & 0x03FFFFFF)


# --- the model -------------------------------------------------------------

class Runaway(Exception):
    """A scan went past its end without stopping (the original does too)."""


def convert(word):
    """ADDON_0/3/4's change: a word in 0x8bff0001..0x8fffffff or
    0xabff0001..0xafffffff gets 0x0c000000 added (lw -> lwr, sw -> swr).
    Returns (word, whether it changed)."""
    w = word & M32
    if (w + 0x7400FFFF) & M32 <= 0x0400FFFE or (w + 0x5400FFFF) & M32 <= 0x0400FFFE:
        return (w + 0x0C000000) & M32, True
    return w, False


def swr(mem, addr, value):
    """SWR: the value's low bytes from `addr` to the end of its word."""
    addr &= M32
    mem.write(addr, (value & M32).to_bytes(4, "little")[:4 - (addr & 3)])


def model_block(mem, regs, addons):
    """One pass of the hook, from 0x2075e8 to 0x2075f4: changes `mem` (a
    Machine used for its memory) and returns the registers it leaves.
    Raises Runaway where the scan would not stop."""
    out = list(regs)

    def setlo(r, value):
        out[r] = (out[r] & (M64 << 64)) | (value & M64)

    def behind():                       # ADDON_0
        a2 = regs[6] & M32
        addr = (a2 - 0x800) & M32
        while True:
            word, changed = convert(mem.u32(addr))
            if changed:
                swr(mem, addr, word)
            addr = (addr + 4) & M32
            if addr == a2:
                break

    if mem.u32(FLAG):
        if addons & 2:                  # ADDON_1
            mem.write(START + 3, b"\0")
            addr = (mem.u32(START) + PS1_RAM) & M32
            length = mem.u32(LENGTH)
            mem.put32(FLAG, 0)
            end, seen = (addr + length) & M32, 0
            while True:
                seen += 1
                if seen > (length >> 2) + 1:
                    raise Runaway("ADDON_1 passed 0x%08x" % end)
                word = mem.u32(addr)
                if word in (BREAK7, BREAK6) and mem.read((addr - 5) & M32, 1)[0]:
                    mem.put32(addr, 0)
                    if word == BREAK7:  # the original skips the end check here
                        addr = (addr + 4) & M32
                        continue
                last = addr == end
                addr = (addr + 4) & M32
                if last:
                    break
        if addons & 4:                  # ADDON_2, then ADDON_0
            addr = (mem.u32(START) + PS1_RAM) & M32
            length = mem.u32(LENGTH)
            mem.write(START + 3, b"\0")
            mem.put32(FLAG, 0)
            end, seen = (addr + length) & M32, 0
            while True:
                seen += 1
                if seen > (length >> 2) + 1:
                    raise Runaway("ADDON_2 passed 0x%08x" % end)
                first = mem.u32(addr)
                hit = False
                if first in (LI_T2_A0, LI_T2_B0):
                    w4, w8 = mem.u32(addr + 4), mem.u32(addr + 8)
                    if first == LI_T2_A0:
                        hit = (w4 == JR_T2 and w8 == li_t1(0x3A)) or (w8 == JR_T2 and w4 == li_t1(0x3A))
                    else:
                        hit = (w4 == JR_T2 and w8 in (li_t1(0x38), li_t1(0x52), li_t1(0x5A))) or \
                              (w8 == JR_T2 and w4 == li_t1(0x38))
                        if not hit:     # the never-matching li-first B0:52 check
                            setlo(3, sext32(w8))
                            hit = w8 == JR_T2 and w4 == li_t1(0x5A)
                if hit:
                    mem.put32(addr, JR_RA)
                    mem.put32(addr + 4, 0)
                    mem.put32(addr + 8, 0)
                addr = (addr + 4) & M32
                if addr == end:
                    break
            if addons & 1:
                behind()
    elif addons & 1:
        behind()
    sp = regs[29] & M32
    for i in range(6):
        setlo(16 + i, int.from_bytes(mem.read(sp + 0x10 + 8 * i, 8), "little"))
    setlo(31, RESUME)
    return out


def model_emit(mem, regs, site, addon4, slot):
    """One run of the ADDON_3 (or, with `addon4`, ADDON_4) code from POPS's
    emit point `site` to where POPS resumes. `slot` is the 128-bit $gp the
    0x205d1c code last kept (what the 0x206318 code loads). Changes `mem`;
    returns (registers, slot)."""
    out = list(regs)

    def setlo(r, value):
        out[r] = (out[r] & (M64 << 64)) | (value & M64)

    _, value_reg, ptr_reg, _ = EMITS[site]
    if site == 0x00205D1C:
        setlo(4, out[4] | out[2])       # or $a0,$a0,$v0, the word the jump replaced
    word, changed = convert(out[value_reg])
    if changed:
        setlo(value_reg, sext32(word))
    ptr = out[ptr_reg] & M32
    for i, w in enumerate([word] if addon4 else [0, word, 0, 0]):
        swr(mem, ptr + 4 * i, w)
    if site == 0x00206318:
        setlo(17, sext32(ptr + (4 if addon4 else 16)))
        out[28] = slot
    else:
        if not addon4:
            setlo(12, sext32(ptr + 12))
        slot = regs[28]
    setlo(31, 0x01440000)
    return out, slot


# --- random states ---------------------------------------------------------

STACK, CODE_AREA, EMIT_AREA = 0x01FF0000, 0x00600000, 0x00700000
BOUNDARIES = [0x8BFF0000, 0x8BFF0001, 0x8FFFFFFF, 0x90000000, 0xABFF0000, 0xABFF0001,
              0xAFFFFFFF, 0xB0000000, 0x8C000000, 0xAC000000, 0x0BFF0001, 0xCBFF0001]
STUBS = ([(LI_T2_A0, JR_T2, li_t1(0x3A)), (LI_T2_A0, li_t1(0x3A), JR_T2)] +
         [(LI_T2_B0, JR_T2, li_t1(n)) for n in (0x38, 0x52, 0x5A)] +
         [(LI_T2_B0, li_t1(n), JR_T2) for n in (0x38, 0x52, 0x5A)])
NEAR = [(LI_T2_A0, JR_T2, li_t1(0x38)), (LI_T2_B0, JR_T2, li_t1(0x3A)), (LI_T2_A0, JR_T2, JR_T2),
        (LI_T2_B0, JR_T2, JR_T2), (LI_T2_B0, li_t1(0x5A), li_t1(0x5A)), (LI_T2_A0, li_t1(0x3A), li_t1(0x3A)),
        (LI_T2_B0, li_t1(0x52), 0x01400009), (LI_T2_B0, JR_T2, li_t1(0x53)), (LI_T2_A0 ^ 1, JR_T2, li_t1(0x3A))]


def code_word(rng):
    """A word for ADDON_0/3/4 to look at."""
    pick = rng.random()
    if pick < 0.3:
        lo, hi = rng.choice([(0x8BFF0001, 0x8FFFFFFF), (0xABFF0001, 0xAFFFFFFF)])
        return rng.randint(lo, hi)
    if pick < 0.4:
        return rng.choice(BOUNDARIES)
    if pick < 0.7:
        return (rng.choice([0x8C, 0xAC, 0x88, 0x98, 0xA8, 0xB8, 0x84, 0x94, 0x8F, 0xAF, 0x8B, 0xAB]) << 24) | \
            rng.getrandbits(24)
    return rng.getrandbits(32)


def random_regs(rng):
    return [0] + [rng.getrandbits(128) for _ in range(31)]


def setlo(regs, r, value):
    regs[r] = (regs[r] & (M64 << 64)) | (value & M64)


def block_case(rng, mem, addons):
    """Random registers and memory (written into `mem`) for one pass of the
    hook with `addons`; returns the registers."""
    regs = random_regs(rng)
    sp = STACK - 16 * rng.randrange(64)
    setlo(regs, 29, sext32(sp))
    for off in range(0, 0x50, 8):
        mem.write(sp + off, rng.getrandbits(64).to_bytes(8, "little"))
    a2 = CODE_AREA + 4 * rng.randrange(0x3FC00)
    setlo(regs, 6, sext32(a2))
    for addr in range(a2 - 0x810, a2 + 0x10, 4):
        mem.put32(addr, code_word(rng))
    # The loaded code ADDON_1/2 scan, near the kernel words at times.
    offset = (0xB878 - 4 * rng.randrange(24)) if rng.random() < 0.2 else 4 * rng.randrange(0x4000, 0x7C000)
    count = rng.randrange(1 if addons & 4 else 0, 40)
    region = PS1_RAM + offset
    for addr in range(region - 16, region + 4 * count + 16, 4):
        mem.put32(addr, rng.getrandbits(32) if rng.random() < 0.5 else rng.choice(STUBS + NEAR)[0])
    for _ in range(rng.randrange(count // 2 + 3)):
        addr = region + 4 * rng.randrange(-2, count + 2)
        kind = rng.random()
        if kind < 0.4:
            for i, w in enumerate(rng.choice(STUBS)):
                mem.put32(addr + 4 * i, w)
        elif kind < 0.6:
            for i, w in enumerate(rng.choice(NEAR)):
                mem.put32(addr + 4 * i, w if w != 0x01400009 else rng.getrandbits(32))
        else:
            mem.put32(addr, rng.choice([BREAK7, BREAK6]))
            top = 0 if rng.random() < 0.3 else rng.randrange(1, 256)
            mem.put32(addr - 8, (top << 24) | rng.getrandbits(24))
    top = rng.choice([0x00, 0x00, 0x80, 0xA0])
    if top and not mem.kseg:
        # Without kseg the address with the top byte kept is other memory:
        # what ADDON_2 alone scans there (and ADDON_1 must not).
        alias = region + (top << 24)
        for addr in range(alias - 16, alias + 4 * count + 16, 4):
            mem.put32(addr, rng.choice(STUBS)[rng.randrange(3)] if rng.random() < 0.3 else BREAK7)
    mem.put32(START, (top << 24) | offset)
    mem.put32(LENGTH, 4 * count)
    mem.put32(FLAG, 0 if rng.random() < 0.25 else rng.choice([1, 0x80000000, rng.getrandbits(32) | 1]))
    return regs


def emit_case(rng, mem, regs):
    """Random registers and memory for one emit; `regs` are changed in place."""
    for r in (2, 4):
        regs[r] = (rng.getrandbits(64) << 64) | (sext32(code_word(rng)) if rng.random() < 0.8
                                                 else rng.getrandbits(64))
    for r in (17, 12):
        ptr = EMIT_AREA + rng.randrange(0x10000) * 4 + (rng.randrange(1, 4) if rng.random() < 0.1 else 0)
        setlo(regs, r, sext32(ptr))
        for addr in range((ptr & ~3) - 4, (ptr & ~3) + 20, 4):
            mem.put32(addr, rng.getrandbits(32))


# --- runners ---------------------------------------------------------------

def machine(preload):
    """A Machine holding `preload` ({address: bytes}), kseg on, no store log."""
    m = Machine()
    m.kseg, m.record = True, False
    for addr, data in preload.items():
        m.write(addr, data)
    return m


def clone(m):
    c = Machine()
    c.kseg, c.record = m.kseg, False
    c.pages = {k: bytearray(v) for k, v in m.pages.items()}
    c.gpr = list(m.gpr)
    return c


def differences(a, b, skip=()):
    """Bytes where two machines' memories differ, outside the `skip` ranges."""
    zero = bytes(4096)
    out = []
    for page in sorted(set(a.pages) | set(b.pages)):
        pa, pb = a.pages.get(page, zero), b.pages.get(page, zero)
        if pa == pb:
            continue
        for i in range(4096):
            addr = page << 12 | i
            if pa[i] != pb[i] and not any(lo <= addr < hi for lo, hi in skip):
                out.append(addr)
    return out


def compare(where, got, want):
    for r in range(32):
        if got.gpr[r] != want[r]:
            raise AssertionError("%s: $%d = 0x%032x, want 0x%032x" % (where, r, got.gpr[r], want[r]))


def check_block(load, rng, trials, addon_sets=range(8), limit=200000):
    """Run the hook from 0x2075e8 with each set of commands in `addon_sets`
    (bit n: ADDON_n) on `trials` random states; `load(addons)` gives the
    memory to preload ({address: bytes}: the code, its configuration and
    the hooked words). Registers and all of memory must be the model's.
    Returns (runs, cases the model said would run away, which were skipped)."""
    runs = skipped = 0
    for addons in addon_sets:
        preload = load(addons)
        for trial in range(trials):
            base = machine(preload)
            base.kseg = rng.random() < 0.7
            regs = block_case(rng, base, addons)
            want_mem = clone(base)
            try:
                want = model_block(want_mem, regs, addons)
            except Runaway:
                skipped += 1
                continue
            got = clone(base)
            got.gpr = list(regs)
            got.steps = 0
            got.run(HOOK, RESUME, limit=limit)
            where = "addons %d, trial %d" % (addons, trial)
            compare(where, got, want)
            diff = differences(got, want_mem)
            if diff:
                raise AssertionError("%s: memory differs at %s" % (where, ", ".join("0x%08x" % a for a in diff[:8])))
            runs += 1
    return runs, skipped


def check_emit(load, gp_slot, scratch, rng, trials, variants=(8, 16, 24)):
    """Run POPS's two emit points with ADDON_3, ADDON_4 or both (`variants`,
    bit n: ADDON_n), `load(addons)` giving the memory to preload. Each trial
    is a few emits in a row, so the $gp slot (at `gp_slot`) carries over as
    on the console. Writes inside `scratch` (ranges) are the code's own and
    not compared. Returns the number of emits run."""
    runs = 0
    for addons in variants:
        preload = load(addons)
        addon4 = bool(addons & 16)
        for trial in range(trials):
            got = machine(preload)
            slot = rng.getrandbits(128) if rng.random() < 0.8 else 0
            got.write(gp_slot, slot.to_bytes(16, "little"))
            regs = random_regs(rng)
            for step in range(rng.randrange(1, 5)):
                emit_case(rng, got, regs)
                site = rng.choice(list(EMITS))
                want_mem = clone(got)
                want, slot = model_emit(want_mem, regs, site, addon4, slot)
                got.gpr = list(regs)
                got.steps = 0
                got.run(site, EMITS[site][0], limit=200)
                where = "addons %d, trial %d, emit %d at 0x%06x" % (addons, trial, step, site)
                compare(where, got, want)
                diff = differences(got, want_mem, scratch)
                if diff:
                    raise AssertionError("%s: memory differs at %s" % (where, ", ".join("0x%08x" % a for a in diff[:8])))
                # Carry on from what the code left, scratch included.
                regs = list(want)
                runs += 1
    return runs


# --- the original, installed by its own code ---------------------------------

MAIN_BASE, GP, MEMCPY, SENTINEL = 0x870000, 0x9B68F0, 0x918808, 0x00800000
ADDON_COPY = {0: 0x8D6F64, 1: 0x8D6FA4, 2: 0x8D6FE4}   # copy ADDON_n's code into the block
ADDON_POKES = {3: (0x893DD8, 0x893E20), 4: (0x894140, 0x894228)}
ORIGINAL_ENTRY = 0x0143A160
ORIGINAL_EMITS = {3: (0x0143A550, 0x0143A5E0), 4: (0x0143A550, 0x0143A5E0)}
ORIGINAL_GP_SLOT = 0x0143A6A0
ORIGINAL_SCRATCH = ((0x0143A670, 0x0143A6B0), (0x014430A0, 0x014430B0))
ORIGINAL_SPAN = (BASE, 0x01440000)      # the block copy ends at 0x143a160 + 0x5ea0


def original_install(main, addons, core=None):
    """Run the original's own launch code over a machine holding POPSTARTER's
    MAIN (`main`, decoded) and POPS's core (`core`, or just POPS's words at
    the sites): the block copy and the hook (0x8747e0..0x874830), then each
    command's code (ADDON_0..2 copy code into the block, ADDON_3/4 poke
    POPS and, for 4, the code). Returns the machine."""
    m = Machine()
    m.record = False
    m.write(MAIN_BASE, main)
    if core is not None:
        m.write(0x00200000, core)
    else:
        m.put32(HOOK, HOOK_PRISTINE[0])
        m.put32(HOOK + 4, HOOK_PRISTINE[1])
        for site, (_, _, _, words) in EMITS.items():
            m.put32(site, words[0])
            m.put32(site + 4, words[1])

    def memcpy(mm):
        dst, src, n = mm.lo(4) & M32, mm.lo(5) & M32, mm.lo(6) & M32
        mm.write(dst, mm.read(src, n))
        mm.set_lo(2, dst)
    m.natives[MEMCPY] = memcpy
    m.set_lo(28, GP)

    def run(start, stop):
        m.set_lo(29, 0x01FF0000)
        m.set_lo(30, 0x01FF0000)
        m.run(start, stop)
    run(0x8747E0, 0x874830)
    for n in (0, 1, 2):
        if addons >> n & 1:
            m.set_lo(31, SENTINEL)
            run(ADDON_COPY[n], SENTINEL)
    for n in (3, 4):
        if addons >> n & 1:
            run(*ADDON_POKES[n])
    return m


def original_loader(main):
    """load(addons) for check_block/check_emit: the original's block, code
    and hooked POPS words after its own install."""
    cache = {}

    def load(addons):
        if addons not in cache:
            m = original_install(main, addons)
            pre = {ORIGINAL_SPAN[0]: m.read(ORIGINAL_SPAN[0], ORIGINAL_SPAN[1] - ORIGINAL_SPAN[0])}
            for addr in [HOOK] + list(EMITS):
                pre[addr] = m.read(addr, 8)
            cache[addons] = pre
        return cache[addons]
    return load


if __name__ == "__main__":
    import time
    code, config, save = BASE + 0x400, BASE + 0x2000, BASE + 0x3000
    words, symbols = assembled(code, config, save)
    image = b"".join(w.to_bytes(4, "little") for w in words)

    def load(addons):
        pre = {code: image, config + FLAGS_OFFSET: config_flags(addons).to_bytes(4, "little"),
               HOOK: (jump(symbols["pops_resident_recompiler"])).to_bytes(4, "little") + bytes(4)}
        if addons & 24:
            pick = 2 if addons & 16 else 0
            for i, site in enumerate(EMITS):
                pre[site] = jump(symbols[EMIT_SYMBOLS[pick + i]]).to_bytes(4, "little") + bytes(4)
        return pre
    t = time.time()
    runs, skipped = check_block(load, random.Random(0x5245434F), 12)
    n = check_emit(load, save + 0x30, ((save, save + 0x40),), random.Random(0x454D4954), 60)
    print("assembled recompiler code vs model: PASS (%d passes, %d runaway cases skipped, %d emits, %.1fs)"
          % (runs, skipped, n, time.time() - t))
