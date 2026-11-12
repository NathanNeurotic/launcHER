#!/usr/bin/env python3
"""Python twin of the TROJAN payload scan (pops_trojan_scan, common/src/pops_external.c).

Written from the description in common/include/pops_external.h, not from
the C text, so the two can be compared word for word on synthetic programs
and on files a tester supplies. It holds no payload bytes.
"""
import struct

REF_SLOT, REF_BLOCK1, REF_480P, REF_BLOCK2 = 0x01, 0x02, 0x04, 0x08
REF_BUILTIN, REF_OWNED, REF_MAIN = 0x10, 0x20, 0x40
REF_NAMES = {REF_SLOT: 'slot chain', REF_BLOCK1: 'first part outside the slots',
             REF_480P: '480p handler', REF_BLOCK2: 'second part', REF_BUILTIN: 'built-in fix code',
             REF_OWNED: '0x0143a000..0x014601ff', REF_MAIN: 'POPStarter program'}
# Refusal order of pops_fix_stage_trojan; anything else left needs the slot chain only.
REFUSALS = (REF_480P, REF_BLOCK2, REF_BUILTIN, REF_OWNED, REF_BLOCK1, REF_MAIN)

SLOTS_A, SLOTS_B, SLOTS_SPAN, SLOTS_HOOKS = 0x2327d0, 0x232d08, 0x30, 0x28
SLOT_HOOKS = {7: 0x2327d0, 0: 0x2327d8, 1: 0x2327e0, 2: 0x2327e8, 3: 0x2327f0,
              4: 0x232d08, 5: 0x232d10, 6: 0x232d18, 8: 0x232d20, 9: 0x232d28}
ARENA = (0x01420000, 0x01600000)
OWNED = (0x0143a000, 0x01460200)
POPS_GP = 0x50a670
CODE, DATA, VALUE = range(3)
M32 = 0xffffffff
LOADS = {0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x37, 0x1e, 0x1a, 0x1b, 0x31}
STORES = {0x28, 0x29, 0x2a, 0x2b, 0x2e, 0x3f, 0x1f, 0x2c, 0x2d, 0x39}


def ref_flags(address, kind):
    for base in (SLOTS_A, SLOTS_B):
        if base <= address < base + SLOTS_SPAN:
            return REF_BLOCK1 if address - base >= SLOTS_HOOKS and kind == DATA else REF_SLOT
    if 0x232790 <= address < 0x232ec8:
        return REF_BLOCK1
    if 0x2394f0 <= address < 0x239758:
        return REF_480P
    if 0x238a90 <= address < 0x2397f0:
        return REF_BLOCK2
    if 0x01410000 <= address < 0x01420000:
        return REF_BUILTIN
    if OWNED[0] <= address < OWNED[1]:
        return REF_OWNED
    if kind != VALUE and 0x870000 <= address < 0xb00000:
        return REF_MAIN
    return 0


def s16(word):
    value = word & 0xffff
    return (value - 0x10000 if value & 0x8000 else value) & M32


def scan(payload, load, entry):
    """-> POPS_TROJAN_REF_* flags, or None where the C function refuses."""
    size = len(payload)
    if not size or (size | load | entry) & 3 or load + size > M32 or not load <= entry < load + size:
        return None
    words = struct.unpack('<%dI' % (size // 4), payload)
    done, pending = set(), {entry}
    flags = 0
    known = {}  # register -> (value, whole constant)

    def note(address, kind):
        nonlocal flags
        address &= M32
        if load <= address < load + size:
            if kind == CODE and not address & 3 and address not in done:
                pending.add(address)
            return
        flags |= ref_flags(address, kind)

    def constant(value):
        if value >> 26 in (2, 3):
            note((value & 0x03ffffff) << 2, CODE)
        else:
            note(value, VALUE)

    def setreg(register, value, whole):
        if register:
            known[register] = (value & M32, whole)

    def step(pc, word):
        """-> (the next word is a delay slot, nothing is read after it)"""
        op, rs, rt, rd = word >> 26, (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
        imm, fn = word & 0xffff, word & 0x3f
        if not word:
            return False, False
        if op == 0:
            if fn in (8, 9):
                if rs in known and known[rs][1]:
                    note(known[rs][0], CODE)
                if fn == 9:
                    known.clear()
                return True, fn == 8
            if fn != 0x0c:
                known.pop(rd, None)
            return False, False
        if op in (2, 3):
            note((pc & 0xf0000000) | ((word & 0x03ffffff) << 2), CODE)
            return True, op == 2
        if op == 1 or 4 <= op <= 7 or 0x14 <= op <= 0x17:
            note(pc + 4 + (s16(word) << 2), CODE)
            return True, (op == 4 and rs == rt) or (op == 6 and not rs) or \
                (op == 1 and rt == 1 and not rs)
        if op == 0x0f:
            known.pop(rt, None)
            setreg(rt, imm << 16, False)
            return False, False
        if op in (0x09, 0x0d, 0x08, 0x19, 0x18):
            if rs in known and (rs != rt or not known[rs][1]):
                value = known[rs][0] | imm if op == 0x0d else (known[rs][0] + s16(word)) & M32
                known.pop(rt, None)
                setreg(rt, value, True)
                constant(value)
            elif not rs:
                known.pop(rt, None)
                setreg(rt, imm if op == 0x0d else s16(word), True)
            else:
                known.pop(rt, None)
            return False, False
        if op in (0x0a, 0x0b, 0x0c, 0x0e):
            known.pop(rt, None)
            return False, False
        if op in LOADS or op in STORES:
            if rs == 28:
                note(POPS_GP + s16(word), DATA)
            elif rs in known:
                note(known[rs][0] + s16(word), DATA)
            if op in LOADS and op != 0x31:
                known.pop(rt, None)
            return False, False
        if op == 0x10:
            return False, False
        known.pop(rt, None)
        known.pop(rd, None)
        return False, False

    def take(address):
        if not load <= address < load + size or address in done:
            return False
        done.add(address)
        return True

    while pending:
        pc = min(pending)
        pending.discard(pc)
        known.clear()
        while take(pc):
            delay, stop = step(pc, words[(pc - load) // 4])
            if not delay:
                pc += 4
                continue
            if take(pc + 4):
                step(pc + 4, words[(pc + 4 - load) // 4])
            if stop:
                break
            known.clear()
            pc += 8
    return flags


def refusal(flags):
    """The first REF_* that makes launcHER refuse a payload, or 0."""
    for flag in REFUSALS:
        if flags & flag:
            return flag
    return 0


def in_arena(address, size):
    return bool(size) and ARENA[0] <= address and address + size <= ARENA[1] and \
        not (address < OWNED[1] and address + size > OWNED[0])
