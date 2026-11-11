#!/usr/bin/env python3
"""Kernel and hardware state of a run that was parked at POPS's first
instruction, and a comparison of two such runs.

  python park_cmp.py RUN_A [RUN_B]

Each run folder holds ee_80000000_100000.bin (kernel RAM), and optionally
ee_70000000_4000.bin (scratch folder), ee_00200000_302e60.bin and the hardware
register dumps ee_1000f000_20.bin (INTC), ee_1000e000_20.bin (DMAC),
ee_1000c000_10.bin (D5/SIF0), ee_1000c400_10.bin (D6/SIF1) and
ee_1000{0000,0800,1000,1800}_20.bin (timers 0..3).
Kernel layout as in handoff-vdyn/kstate.py (SCPH-39001): TCBs at 0x8001a480,
0x4c bytes each, free-slot list head at 0x8001a068 ({next, prev}; CreateThread
takes head->prev, DeleteThread inserts at head->next), argument buffer at
0x80015388.
"""
import os
import struct
import sys

TCB, TCB_SIZE, FREE_HEAD = 0x8001A480, 0x4C, 0x8001A068


def load(run, name):
    path = os.path.join(run, name)
    return open(path, "rb").read() if os.path.isfile(path) else None


def state(run):
    k = load(run, "ee_80000000_100000.bin")
    u32 = lambda a: struct.unpack_from("<I", k, a - 0x80000000)[0]
    out = {"run": os.path.basename(run.rstrip("/\\"))}
    out["current"] = u32(0x8001536C)
    out["count"] = u32(0x8001A060)
    out["in_use"] = [(i, u32(TCB + i * TCB_SIZE + 8)) for i in range(256) if u32(TCB + i * TCB_SIZE + 8)]
    order, node, guard = [], u32(FREE_HEAD + 4), 0
    while node != FREE_HEAD and TCB <= node < TCB + 256 * TCB_SIZE and guard < 300:
        order.append((node - TCB) // TCB_SIZE)
        node = u32(node + 4)
        guard += 1
    out["free_order"] = order
    lists = {}
    for title, base, count in (("INTC", 0x80018CD8, 15), ("DMAC", 0x80018D90, 16)):
        for c in range(count):
            n = u32(base + c * 0xC + 8)
            if n:
                lists["%s %d" % (title, c)] = n
    out["handlers"] = lists
    odd = []
    for n in range(0x8C):
        v = u32(0x80014D00 + 4 * n)
        if v and not (0x80000000 <= v < 0x80074000 or 0xA0000000 <= v < 0xA0074000):
            odd.append("%#x:%08x" % (n, v))
    out["syscalls_outside_rom"] = odd
    args = k[0x15388:0x15388 + 0x100]
    out["arg_buffer"] = [s.decode("ascii", "replace") for s in args.split(b"\0") if s][:6]
    t = TCB + out["current"] * TCB_SIZE
    out["current_tcb"] = "entry %08x entry_ %08x stack %08x size %#x gp %08x prio %d" % (
        u32(t + 0xC), u32(t + 0x30), u32(t + 0x3C), u32(t + 0x40), u32(t + 0x14),
        struct.unpack_from("<H", k, t + 0x18 - 0x80000000)[0])
    spad = load(run, "ee_70000000_4000.bin")
    out["scratch folder_nonzero_bytes"] = None if spad is None else sum(1 for b in spad if b)
    core = load(run, "ee_00200000_302e60.bin")
    if core:
        out["entry_words"] = " ".join("%08x" % w for w in struct.unpack_from("<4I", core, 0))
        bss = None
    hw = {}
    for name, label, offs in (("ee_1000f000_20.bin", "INTC", ((0x00, "I_STAT"), (0x10, "I_MASK"))),
                              ("ee_1000e000_20.bin", "DMAC", ((0x00, "D_CTRL"), (0x10, "D_STAT"))),
                              ("ee_1000c000_10.bin", "D5", ((0x00, "D5_CHCR"),)),
                              ("ee_1000c400_10.bin", "D6", ((0x00, "D6_CHCR"),)),
                              ("ee_10000000_20.bin", "T0", ((0x10, "T0_MODE"),)),
                              ("ee_10000800_20.bin", "T1", ((0x10, "T1_MODE"),)),
                              ("ee_10001000_20.bin", "T2", ((0x10, "T2_MODE"),)),
                              ("ee_10001800_20.bin", "T3", ((0x10, "T3_MODE"),))):
        d = load(run, name)
        if d:
            for off, reg in offs:
                hw[reg] = "%08x" % struct.unpack_from("<I", d, off)[0]
    out["hw"] = hw
    out["kernel"] = k
    return out


def show(s):
    print("== %s" % s["run"])
    print("  current thread %d, thread count %d, slots in use (id:status) %s"
          % (s["current"], s["count"], " ".join("%d:%#x" % x for x in s["in_use"])))
    print("  current TCB: %s" % s["current_tcb"])
    print("  free slots %d; CreateThread would hand out, in order: %s ... %s"
          % (len(s["free_order"]), s["free_order"][:8], s["free_order"][-3:]))
    print("  registered INTC/DMAC handlers: %s" % (s["handlers"] or "none"))
    print("  syscall table entries outside the ROM kernel: %s" % " ".join(s["syscalls_outside_rom"]))
    print("  kernel argument buffer strings: %s" % s["arg_buffer"])
    print("  scratch folder non-zero bytes: %s" % s["scratch folder_nonzero_bytes"])
    print("  words at 0x200000: %s" % s.get("entry_words"))
    print("  hardware: %s" % " ".join("%s=%s" % kv for kv in s["hw"].items()))


def main():
    a = state(sys.argv[1])
    show(a)
    if len(sys.argv) < 3:
        return
    b = state(sys.argv[2])
    show(b)
    print("== comparison")
    for key in ("current", "count", "in_use", "free_order", "handlers", "syscalls_outside_rom", "arg_buffer",
                "scratch folder_nonzero_bytes", "hw"):
        print("  %-26s %s" % (key, "same" if a[key] == b[key] else "DIFFERENT"))
    ka, kb = a["kernel"], b["kernel"]
    pages = {}
    for off in range(0, 0x80000, 4):
        if ka[off:off + 4] != kb[off:off + 4]:
            pages[off >> 12] = pages.get(off >> 12, 0) + 1
    print("  kernel RAM 0x80000000..0x80080000: %d differing words in %d pages"
          % (sum(pages.values()), len(pages)))
    for page in sorted(pages):
        print("    0x%08x: %d" % (0x80000000 + (page << 12), pages[page]))
    # TCB table apart: which fields of which slots differ.
    diff_slots = []
    for i in range(256):
        lo = 0x1A480 + i * TCB_SIZE
        if ka[lo:lo + TCB_SIZE] != kb[lo:lo + TCB_SIZE]:
            diff_slots.append(i)
    print("  TCB slots whose bytes differ: %d (%s%s)" % (len(diff_slots), diff_slots[:12],
                                                         " ..." if len(diff_slots) > 12 else ""))


main()
