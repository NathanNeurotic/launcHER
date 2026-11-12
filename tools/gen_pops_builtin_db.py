#!/usr/bin/env python3
"""Generate common/src/pops_builtin_db_data.c from POPStarter r13's own
built-in per-game list.

Needs the external POPStarter MAIN (POPSTARTER_TEST_ELF) and Unicorn. The
MAIN is read at run time; this script stores no original bytes itself.

What it does (docs/POPSTARTER_BUILTIN_DB.md):

- reads the 607 stored 144-byte disc fingerprints from the lookup chain
  (0x8ff33c..0x9148e8) in program order and keeps a 64-bit FNV-1a hash of
  each, not the disc bytes;
- runs the original FUN_008e00d0(id, 3) for every id 0..MAX_ID under
  Unicorn. Prints are skipped; the compatibility-mode helper (FUN_008dc2c4)
  and the memory card 1 helper (FUN_008dc12c) are recorded as operations;
  everything else (memcpy, poke8/poke32, the breakpoint helper
  FUN_008d6da4 and its 64/128-bit stores) runs as shipped and every byte
  it writes outside the MAIN image and the stack is recorded in order;
- sorts each write by where it lands: the POPS core, the two EE areas the
  original installs code in (0x01410000 game-fix code, 0x01460000
  breakpoint handler), or one of the original's own resident slots
  (0x232d08, 0x238d00, 0x239780..0x2397d7, 0x2397d8), which launcHER's
  resident code reproduces. Anything else stops the generator;
- runs every id again with $FAKELC's flag (gp+0x3424) set, as the original
  does for a $VCDID_n that comes after a $FAKELC. 216 arms test the flag
  and jump over part of themselves; the operations they leave out must be
  one run of the full list, stored per entry as lc_first/lc_count.

    POPSTARTER_TEST_ELF=... python tools/gen_pops_builtin_db.py [--check]

--check compares with the committed file instead of writing it.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_original_pops_io import decode_main  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "common" / "src" / "pops_builtin_db_data.c"

BASE = 0x870000
LIMIT = 0xA00000
GP = 0x9B68F0
FN = 0x8E00D0
FN_END = 0x8FF0E4
STACK = 0x1F00000
END = 0x00F00000
MAX_ID = 624
SIG_FIRST, SIG_END = 0x8FF33C, 0x9148E8
SIG_SIZE = 0x90

PRINT = 0x915708
COMPAT = 0x8DC2C4
NOVMC1 = 0x8DC12C

# Template buffers the routine edits in place before copying them.
SCRATCH = ((0x972300, 0x972380), (0x984C80, 0x984CA0))
GP_FLAGS = {0x38C0: "busy", 0x3458: "subcd", 0x38BC: "novmc1", 0x4FA0: "autopal"}
# $FAKELC's flag (set by its handler at 0x89ccb4, zeroed at 0x870c78). The
# 216 arms that read it skip part of themselves while it is set. The handler
# also clears template bytes 0x972370/74/75 before its copy; they are 0 in
# the image and the only template bytes any entry edits, so the flag is the
# only thing an entry run after it sees differently.
FAKELC_FLAG = 0x3424

CORE = (0x200000, 0x600000)
FIX_AREA = (0x01410000, 0x01420000)
BREAK_AREA = (0x01460000, 0x01460200)
SLOT_BREAK = 0x232D08
SLOT_LIBCRYPT2 = 0x238D00
LIBCRYPT2 = (0x239780, 0x2397D4)  # 84 bytes, falls through to the fix slot
SLOT_FIX = 0x2397D8
ORIGINAL_BLOB = ((0x232790, 0x232EC8), (0x238A90, 0x2397F0))

JAL_FIX = 0x0C504000      # jal 0x01410000
J_LIBCRYPT2 = 0x0808E5E0  # j 0x239780
JAL_BREAK = 0x0C518000    # jal 0x01460000

OP = {"core": 0, "ee": 1, "compat": 2, "novmc1": 3, "subcd": 4, "no_auto_pal": 5,
      "fix_call": 6, "libcrypt2_code": 7, "libcrypt2_on": 8, "break_call": 9}


def fnv1a64(data: bytes) -> int:
    h = 0xCBF29CE484222325
    for b in data:
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def image():
    return decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())


def signatures(img):
    """(id, fingerprint) in program order, as the lookup compares them."""
    def w(a):
        return struct.unpack_from("<I", img, a - BASE)[0]
    out, lui, sig = [], None, None
    a = SIG_FIRST
    while a < SIG_END:
        x = w(a)
        if x >> 16 == 0x3C02:
            lui = (x & 0xFFFF) << 16
        elif x >> 16 == 0x2442 and lui is not None:
            s = x & 0xFFFF
            sig = lui + (s - 0x10000 if s & 0x8000 else s)
            lui = None
        elif x >> 16 == 0x2402 and w(a + 4) == 0xAF8238D8:
            if sig is None:
                raise SystemExit("fingerprint without an address at %#x" % a)
            out.append((x & 0xFFFF, bytes(img[sig - BASE:sig - BASE + SIG_SIZE])))
            sig = None
        a += 4
    return out


def run_entry(img, n, mode=3, fakelc=False):
    """Ordered operations of FUN_008e00d0(n, mode) as ('write', addr, bytes),
    ('compat', k), ('novmc1', k) and ('flag', name, value). fakelc: run it
    with $FAKELC's flag set, as after a $FAKELC in the user's files."""
    from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS64, UC_MODE_LITTLE_ENDIAN
    from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn import mips_const as R

    uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS64 + UC_MODE_LITTLE_ENDIAN)
    try:
        uc.ctl_set_cpu_model(R.UC_CPU_MIPS64_5KF)
    except Exception:
        pass
    uc.mem_map(0, 0x02000000)
    uc.mem_write(BASE, bytes(img))
    uc.mem_write(GP + FAKELC_FLAG, struct.pack("<I", 1 if fakelc else 0))
    regs = [getattr(R, "UC_MIPS_REG_%d" % i) for i in range(32)]
    upper = [0] * 32
    ops = []
    failure = []

    def get(r):
        return uc.reg_read(regs[r]) & 0xFFFFFFFFFFFFFFFF

    def ret(u):
        u.reg_write(R.UC_MIPS_REG_V0, 0)
        u.reg_write(R.UC_MIPS_REG_PC, u.reg_read(R.UC_MIPS_REG_RA))

    def code(u, addr, size, _):
        try:
            if addr == END:
                return
            if addr == PRINT:
                return ret(u)
            if addr in (COMPAT, NOVMC1):
                a0 = u.reg_read(R.UC_MIPS_REG_A0) & 0xFFFFFFFF
                ops.append(("compat" if addr == COMPAT else "novmc1", a0))
                return ret(u)
            if not BASE <= addr < LIMIT:
                raise RuntimeError("left the image at %#x" % addr)
            word = struct.unpack("<I", u.mem_read(addr, 4))[0]
            op = word >> 26
            rs, rt, rd = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
            imm = word & 0xFFFF
            simm = imm - 0x10000 if imm & 0x8000 else imm
            fn, sa = word & 63, (word >> 6) & 31
            if op == 0x1C and fn == 0x09 and sa == 0x0E:  # pcpyld
                lo, hi = get(rt), get(rs)
                if rd:
                    u.reg_write(regs[rd], lo)
                    upper[rd] = hi
            elif op == 0x1C:
                raise RuntimeError("unmodelled MMI %#010x at %#x" % (word, addr))
            elif op == 0x1F:  # sq (mem_write from a hook fires no write hook)
                a = (get(rs) + simm) & 0xFFFFFFF0
                data = struct.pack("<QQ", get(rt), upper[rt] if rt else 0)
                u.mem_write(a, data)
                record(u, a, data)
            elif op == 0x1E:  # lq
                a = (get(rs) + simm) & 0xFFFFFFF0
                lo, hi = struct.unpack("<QQ", u.mem_read(a, 16))
                if rt:
                    u.reg_write(regs[rt], lo)
                    upper[rt] = hi
            else:
                return
            u.reg_write(R.UC_MIPS_REG_PC, addr + 4)
        except Exception as exc:
            failure.append(exc)
            u.emu_stop()

    def record(u, address, data):
        size = len(data)
        if STACK - 0x10000 <= address < STACK + 0x100:
            return
        if BASE <= address < LIMIT:
            off = address - GP
            if off in GP_FLAGS and size == 4:
                ops.append(("flag", GP_FLAGS[off], struct.unpack("<I", data)[0]))
                return
            if any(lo <= address and address + size <= hi for lo, hi in SCRATCH):
                return
            failure.append(RuntimeError("entry %d writes MAIN at %#x" % (n, address)))
            u.emu_stop()
            return
        ops.append(("write", address, data))

    def write(u, access, address, size, value, _):
        record(u, address, (value & ((1 << (8 * size)) - 1)).to_bytes(size, "little"))

    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_WRITE, write)
    uc.reg_write(R.UC_MIPS_REG_GP, GP)
    uc.reg_write(R.UC_MIPS_REG_SP, STACK)
    uc.reg_write(R.UC_MIPS_REG_A0, n)
    uc.reg_write(R.UC_MIPS_REG_A1, mode)
    uc.reg_write(R.UC_MIPS_REG_RA, END)
    uc.emu_start(FN, END, count=5_000_000)
    if failure:
        raise failure[0]
    # The original's memcpy and the breakpoint helper write their bytes in
    # no particular order; what matters is the memory they leave. Gather the
    # writes between two other operations into a sparse map (later bytes
    # win, as in the original) and emit them as address-ordered runs.
    joined, pending = [], {}

    def flush():
        run = None
        for a in sorted(pending):
            if run and run[0] + len(run[1]) == a:
                run[1].append(pending[a])
            else:
                if run:
                    joined.append(("write", run[0], bytes(run[1])))
                run = [a, bytearray([pending[a]])]
        if run:
            joined.append(("write", run[0], bytes(run[1])))
        pending.clear()

    for o in ops:
        if o[0] == "write":
            for i, b in enumerate(o[2]):
                pending[o[1] + i] = b
        else:
            flush()
            joined.append(o)
    flush()
    return joined


def inside(a, n, area):
    return area[0] <= a and a + n <= area[1]


def classify(n, raw):
    """Turn recorded effects into launcHER operations (kind, arg, addr, data)."""
    out = []
    for o in raw:
        kind = o[0]
        if kind == "compat":
            if not 1 <= o[1] <= 7:
                raise SystemExit("entry %d: compatibility mode %d" % (n, o[1]))
            out.append(("compat", o[1], 0, b""))
        elif kind == "novmc1":
            if o[1] != 2:
                raise SystemExit("entry %d: card helper argument %d" % (n, o[1]))
            out.append(("novmc1", 0, 0, b""))
        elif kind == "flag":
            name, value = o[1], o[2]
            if name == "busy":
                continue  # gp+0x38c0, cleared by every entry; nothing reads it after
            if name == "novmc1":
                if value != 2:
                    raise SystemExit("entry %d: gp+0x38bc=%d" % (n, value))
                continue  # paired with the helper call, recorded there
            if name == "subcd" and value == 1:
                out.append(("subcd", 0, 0, b""))
            elif name == "autopal" and value == 0:
                out.append(("no_auto_pal", 0, 0, b""))
            else:
                raise SystemExit("entry %d: %s=%d" % (n, name, value))
        else:
            a, data = o[1], o[2]
            word = struct.unpack("<I", data)[0] if len(data) == 4 else None
            if a == SLOT_FIX and word == JAL_FIX:
                out.append(("fix_call", 0, 0, b""))
            elif a == SLOT_LIBCRYPT2 and word == J_LIBCRYPT2:
                out.append(("libcrypt2_on", 0, 0, b""))
            elif a == SLOT_BREAK and word == JAL_BREAK:
                out.append(("break_call", 0, 0, b""))
            elif a == LIBCRYPT2[0] and len(data) == LIBCRYPT2[1] - LIBCRYPT2[0]:
                out.append(("libcrypt2_code", 0, 0, data))
            elif any(inside(a, len(data), r) or (a < r[1] and r[0] < a + len(data))
                     for r in ORIGINAL_BLOB):
                raise SystemExit("entry %d: unexpected write %#x+%d into the original's "
                                 "resident block" % (n, a, len(data)))
            elif inside(a, len(data), FIX_AREA) or inside(a, len(data), BREAK_AREA):
                out.append(("ee", 0, a, data))
            elif inside(a, len(data), CORE):
                out.append(("core", 0, a, data))
            else:
                raise SystemExit("entry %d: write %#x+%d lands nowhere launcHER "
                                 "knows" % (n, a, len(data)))
    return out


def check_code(n, ops):
    """The installed code must only touch k0/k1 (the original's chain keeps
    nothing else) and return with jr ra; checked on what launcHER calls."""
    calls = {o[0] for o in ops}
    need = []
    if "fix_call" in calls:
        need.append(FIX_AREA[0])
    if "break_call" in calls:
        need.append(BREAK_AREA[0])
    if "libcrypt2_on" in calls and "libcrypt2_code" not in calls:
        raise SystemExit("entry %d: LibCrypt slot without its code" % n)
    if "libcrypt2_code" in calls and "libcrypt2_on" not in calls:
        raise SystemExit("entry %d: LibCrypt code without its slot" % n)
    for target in need:
        if not any(o[0] == "ee" and o[2] == target for o in ops):
            raise SystemExit("entry %d: call to %#x with nothing installed there" % (n, target))


def build(img):
    sigs = signatures(img)
    if len(sigs) != 607:
        raise SystemExit("expected 607 fingerprints, found %d" % len(sigs))
    hashes = [(fnv1a64(s), i) for i, s in sigs]
    by_hash = {}
    for h, i in hashes:
        by_hash.setdefault(h, set()).add(i)
    # Different fingerprints must not share a hash (equal ones may).
    seen = {}
    for i, s in sigs:
        h = fnv1a64(s)
        if h in seen and seen[h] != s:
            raise SystemExit("FNV-1a collision between stored fingerprints")
        seen[h] = s
    entries, cuts = [], []
    for n in range(MAX_ID + 1):
        ops = classify(n, run_entry(img, n))
        check_code(n, ops)
        after = classify(n, run_entry(img, n, fakelc=True))
        check_code(n, after)
        cut = lc_cut(n, ops, after)
        entries.append(ops)
        cuts.append(cut)
    skipping = sum(1 for _, count in cuts if count)
    if skipping != 216:
        raise SystemExit("expected 216 entries that skip ops after $FAKELC, found %d" % skipping)
    return hashes, entries, cuts


def lc_cut(n, ops, after):
    """(first, count) with after == ops[:first] + ops[first + count:]: the run
    of operations the arm jumps over while $FAKELC's flag is set."""
    if after == ops:
        return 0, 0
    for first in range(len(ops)):
        for end in range(first + 1, len(ops) + 1):
            if ops[:first] + ops[end:] == after:
                if end > 255:
                    raise SystemExit("entry %d: cut past 255 operations" % n)
                return first, end - first
    raise SystemExit("entry %d: with $FAKELC set it is not the full entry minus one run" % n)


def emit(hashes, entries, cuts):
    pool = bytearray()
    where = {}

    def put(data):
        if data in where:
            return where[data]
        off = pool.find(data) if data else 0
        if off < 0:
            off = len(pool)
            pool.extend(data)
        where[data] = off
        return off

    rows, index = [], []
    for n, ops in enumerate(entries):
        index.append((len(rows), len(ops)))
        for kind, arg, addr, data in ops:
            rows.append((OP[kind], arg, len(data), addr, put(data) if data else 0))
    lines = []
    lines.append("/* Generated by tools/gen_pops_builtin_db.py from POPStarter r13's own")
    lines.append(" * built-in per-game list (FUN_008e00d0 and its lookup FUN_008ff0e4). Do")
    lines.append(" * not edit by hand: rerun the generator against the external MAIN.")
    lines.append(" * Disc fingerprints are kept as 64-bit FNV-1a hashes, not disc bytes.")
    lines.append(" * Entry rows: first op, op count, then the run of the entry's own ops")
    lines.append(" * (index in the entry, count) its arm skips after a $FAKELC; 0, 0: none.")
    lines.append(" * See docs/POPSTARTER_BUILTIN_DB.md. Not tested on a console. */")
    lines.append('#include "pops_builtin_db.h"')
    lines.append("")
    lines.append("const uint16_t pops_builtin_sig_count = %d;" % len(hashes))
    lines.append("const PopsBuiltinSig pops_builtin_sigs[%d] = {" % len(hashes))
    for h, i in hashes:
        lines.append("  {UINT64_C(0x%016x), %d}," % (h, i))
    lines.append("};")
    lines.append("")
    lines.append("const PopsBuiltinEntry pops_builtin_entries[POPS_BUILTIN_MAX_ID + 1] = {")
    for n, ((first, count), (lc_first, lc_count)) in enumerate(zip(index, cuts)):
        lines.append("  {%d, %d, %d, %d}, /* %d */" % (first, count, lc_first, lc_count, n))
    lines.append("};")
    lines.append("")
    lines.append("const uint16_t pops_builtin_op_count = %d;" % len(rows))
    lines.append("const PopsBuiltinOp pops_builtin_ops[%d] = {" % len(rows))
    for kind, arg, ln, addr, off in rows:
        lines.append("  {%d, %d, %d, 0x%08x, %d}," % (kind, arg, ln, addr, off))
    lines.append("};")
    lines.append("")
    lines.append("const uint32_t pops_builtin_data_size = %d;" % len(pool))
    lines.append("const uint8_t pops_builtin_data[%d] = {" % max(1, len(pool)))
    for i in range(0, len(pool), 16):
        lines.append("  " + " ".join("0x%02x," % b for b in pool[i:i + 16]))
    lines.append("};")
    return "\n".join(lines) + "\n"


def main(argv):
    text = emit(*build(image()))
    if "--check" in argv:
        if OUT.read_text() != text:
            raise SystemExit("%s is out of date" % OUT.relative_to(ROOT))
        print("up to date")
        return
    OUT.write_text(text)
    print("wrote %s (%d bytes)" % (OUT.relative_to(ROOT), len(text)))


if __name__ == "__main__":
    main(sys.argv[1:])
