#!/usr/bin/env python3
"""The last steps before POPS runs: one thread left, interrupts off.

POPStarter r13 calls ExecPS2 as the kernel's only thread (it has no
CreateThread or StartThread stub) and never overwrites its own code before
that call. launcHER has a second thread (ps2sdk's helper) and its trampoline
zeroes launcHER, so:
  - common/src/pops_handoff.c terminates and deletes every other thread
    before the trampoline runs (the EE kernel's ExecPS2 would otherwise
    rewrite each one's initial frame at stack + size - 0x2a0, in memory that
    is POPS's by then) and puts the kernel's free thread slots back in the
    order they had, so POPS's threads get the ids they get after POPStarter;
  - launcher/src/pops_trampoline.S turns interrupts off before its first
    store (launcHER's timer and SIF handlers are still registered while their
    code is zeroed).

Native: the C function against a model of the kernel's thread table and
free-slot queue, and the trampoline's source assembled and run by
tools/r5900_mini.py. Original (POPSTARTER_TEST_ELF): the facts about r13
this rests on, read from its MAIN image. Source: where the launcher calls
it. With POPS_HANDOFF_ELF (a linked launcher_unc.elf) the layout checker
tools/check_pops_handoff_layout.py must pass on it. The kernel behaviour the
model copies was read from the SCPH-39001 kernel and seen in an emulator
(docs/POPSTARTER_HANDOFF.md). Nothing here has run on a console."""
import ctypes as c
import errno
import os
import random
import struct
import subprocess
import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import r5900_mini as R  # noqa: E402

RUN, READY, WAIT, SUSPEND, DORMANT = 1, 2, 4, 8, 0x10
RESET_FRAME = 0x2A0
UNTOUCHED, RESTORED, AS_FOUND = 0, 1, 2
# What the launcher protects: everything it has prepared below 1 MiB and the
# staging area (staged core, built-in entry code, resident image).
PROTECT = ((0x00080000, 0x00100000), (0x01000000, 0x01800000))


class Thread(c.Structure):
    _fields_ = [("status", c.c_int), ("stack", c.c_uint32), ("stack_size", c.c_uint32)]


SELF_FN = c.CFUNCTYPE(c.c_int, c.c_void_p)
REFER_FN = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_int, c.POINTER(Thread))
TID_FN = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_int)
CREATE_FN = c.CFUNCTYPE(c.c_int, c.c_void_p)


class KernelOps(c.Structure):
    _fields_ = [("self", SELF_FN), ("refer", REFER_FN), ("terminate", TID_FN),
                ("remove", TID_FN), ("create", CREATE_FN)]


class Range(c.Structure):
    _fields_ = [("start", c.c_uint32), ("end", c.c_uint32)]


class Report(c.Structure):
    _fields_ = [("self", c.c_int), ("retired", c.c_int), ("first_retired", c.c_int),
                ("drained", c.c_int), ("queue", c.c_int), ("failed_tid", c.c_int)]

    def fields(self):
        return (self.self, self.retired, self.first_retired, self.drained, self.queue, self.failed_tid)


def build():
    out = Path(tempfile.mkdtemp())
    lib = out / ("pops_handoff.dll" if os.name == "nt" else "pops_handoff.so")
    subprocess.run(["gcc", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-I", str(ROOT / "common/include"), str(ROOT / "common/src/pops_handoff.c"),
                    "-o", str(lib)], check=True)
    lib = c.CDLL(str(lib))
    lib.pops_handoff_retire_threads.argtypes = [c.POINTER(KernelOps), c.c_void_p, c.POINTER(Range),
                                                c.c_size_t, c.POINTER(Report)]
    lib.pops_handoff_retire_threads.restype = c.c_int
    return lib


LIB = build()


class Kernel:
    """The EE kernel's thread table as the calls the launcher makes see it
    (SCPH-39001): 256 slots, id 0 the idle thread; CreateThread (0x80003c50)
    takes a free slot from one end of the free list (0x80005b00) and
    DeleteThread (0x80002fc0, DORMANT threads only) puts it back at the other
    (0x80005bb0); TerminateThread (0x80003140) of a thread that is not
    DORMANT rebuilds its initial frame in the top 0x2a0 bytes of its stack
    (0x80003bb8). `fifo=False` models a last-in first-out pool instead."""

    DORMANT_STACK = (0x002018D0, 0x400)

    def __init__(self, self_id=1, fifo=True, free=None):
        self.status = [0] * 256
        self.stack = [0] * 256
        self.size = [0] * 256
        self.self_id = self_id
        self.status[0] = READY
        self.status[self_id] = RUN
        self.fifo = fifo
        self.free = deque(free if free is not None else [i for i in range(1, 256) if i != self_id])
        self.log = []        # ("terminate" | "delete" | "create", id)
        self.frames = []     # (start, end) the kernel rewrote
        self.fail_delete = set()
        self.fail_terminate = set()
        self.create_script = []   # ids to hand out instead of the next free one

    def add(self, status, stack, size):
        tid = self.free.popleft()
        self.status[tid], self.stack[tid], self.size[tid] = status, stack, size
        return tid

    # The five calls.
    def k_self(self, _ctx):
        return self.self_id

    def k_refer(self, _ctx, tid, out):
        if not 0 <= tid < 256:
            return -1
        out[0].status, out[0].stack, out[0].stack_size = self.status[tid], self.stack[tid], self.size[tid]
        return 0

    def k_terminate(self, _ctx, tid):
        if not 0 < tid < 256 or tid == self.self_id or self.status[tid] in (0, DORMANT):
            return -1
        if tid in self.fail_terminate:
            return -1
        end = self.stack[tid] + self.size[tid]
        self.frames.append((end - RESET_FRAME, end))
        self.status[tid] = DORMANT
        self.log.append(("terminate", tid))
        return 0

    def k_remove(self, _ctx, tid):
        if not 0 < tid < 256 or tid == self.self_id or self.status[tid] != DORMANT or tid in self.fail_delete:
            return -1
        self.status[tid] = 0
        if self.fifo:
            self.free.append(tid)
        else:
            self.free.appendleft(tid)
        self.log.append(("delete", tid))
        return 0

    def k_create(self, _ctx):
        if self.create_script:
            tid = self.create_script.pop(0)
            if tid in self.free:
                self.free.remove(tid)
                self.status[tid] = DORMANT
            self.log.append(("create", tid))
            return tid
        if not self.free:
            return -1
        tid = self.free.popleft()
        self.status[tid] = DORMANT
        self.stack[tid], self.size[tid] = self.DORMANT_STACK
        self.log.append(("create", tid))
        return tid

    def others(self):
        return [i for i in range(1, 256) if i != self.self_id and self.status[i]]

    def ops(self):
        self._keep = (SELF_FN(self.k_self), REFER_FN(self.k_refer), TID_FN(self.k_terminate),
                      TID_FN(self.k_remove), CREATE_FN(self.k_create))
        return KernelOps(*self._keep)


def retire(kernel, protect=PROTECT):
    ops, report = kernel.ops(), Report(9, 9, 9, 9, 9, 9)
    ranges = (Range * max(len(protect), 1))(*[Range(lo, hi) for lo, hi in protect])
    result = LIB.pops_handoff_retire_threads(c.byref(ops), None, ranges, len(protect), c.byref(report))
    return result, report


class Native(unittest.TestCase):
    def test_launcher_as_measured(self):
        """launcHER at the handoff, as dumped from the emulator: thread 1
        running, ps2sdk's helper as thread 2 (WAIT, a 0x400-byte stack in
        launcHER's BSS), the kernel's free slots 3..255 in order."""
        k = Kernel()
        self.assertEqual(k.add(WAIT, 0x00206AC0, 0x400), 2)
        result, report = retire(k)
        self.assertEqual(result, 0)
        self.assertEqual(report.fields(), (1, 1, 2, 254, RESTORED, 0))
        self.assertEqual(k.others(), [])
        # As before thread 2 existed: POPS's first CreateThread gets id 2.
        self.assertEqual(list(k.free), list(range(2, 256)))
        self.assertEqual(k.log[:2], [("terminate", 2), ("delete", 2)])
        # The one frame the kernel rewrote is in launcHER's own BSS, written
        # before the trampoline hands that memory to POPS.
        self.assertEqual(k.frames, [(0x00206AC0 + 0x400 - 0x2A0, 0x00206AC0 + 0x400)])
        self.assertEqual(k.log.count(("delete", 2)), 2)   # once retired, once as a placeholder

    def test_no_other_thread_touches_nothing(self):
        k = Kernel()
        before = list(k.free)
        result, report = retire(k)
        self.assertEqual(result, 0)
        self.assertEqual(report.fields(), (1, 0, 0, 0, UNTOUCHED, 0))
        self.assertEqual((k.log, k.frames, list(k.free)), ([], [], before))

    def test_a_dormant_thread_is_deleted_without_a_frame_write(self):
        k = Kernel()
        tid = k.add(DORMANT, 0x01000000, 0x1000)      # even inside a protected range
        result, report = retire(k)
        self.assertEqual((result, report.retired, report.queue), (0, 1, RESTORED))
        self.assertEqual(k.frames, [])
        self.assertEqual(k.log[0], ("delete", tid))
        self.assertEqual(k.others(), [])

    def test_every_thread_goes_and_the_queue_is_as_before_them(self):
        rng = random.Random(0x48414E44)
        for case in range(300):
            self_id = rng.choice([1, 1, 1, rng.randrange(1, 256)])
            free = [i for i in range(1, 256) if i != self_id]
            if case % 3 == 0:
                rng.shuffle(free)                     # a kernel with a history
            k = Kernel(self_id, True, free)
            for _ in range(rng.randrange(1, 12 if case % 5 else 254)):
                if not k.free:
                    break
                size = rng.choice([0x400, 0x1000, 0x4000, 0x20000])
                k.add(rng.choice([READY, WAIT, SUSPEND, WAIT | SUSPEND, DORMANT]),
                      rng.randrange(0x00100000, 0x00F00000, 16), size)
            threads, free_before = k.others(), list(k.free)
            dormant = [t for t in threads if k.status[t] == DORMANT]
            result, report = retire(k)
            self.assertEqual(result, 0, case)
            self.assertEqual(k.others(), [], case)
            self.assertEqual(k.status[self_id], RUN)
            self.assertEqual(report.fields(), (self_id, len(threads), threads[0], 254, RESTORED, 0), case)
            # Retired slots in front (lowest id first), the rest behind them
            # in the order they already had.
            self.assertEqual(list(k.free), threads + free_before, case)
            # Each thread: terminated (unless DORMANT) and deleted at once,
            # all of them before the first placeholder is created.
            first_create = k.log.index(next(e for e in k.log if e[0] == "create"))
            expect = []
            for t in threads:
                expect += ([] if t in dormant else [("terminate", t)]) + [("delete", t)]
            self.assertEqual(k.log[:first_create], expect, case)
            self.assertEqual(len(k.frames), len(threads) - len(dormant))
            for lo, hi in k.frames:
                for plo, phi in PROTECT:
                    self.assertFalse(lo < phi and plo < hi, case)

    def test_a_last_in_first_out_pool_is_left_as_found(self):
        rng = random.Random(0x4C49464F)
        for case in range(100):
            free = list(range(2, 256))
            rng.shuffle(free)
            k = Kernel(1, False, free)
            for _ in range(rng.randrange(2, 9)):
                k.add(rng.choice([READY, WAIT, DORMANT]), rng.randrange(0x00100000, 0x00F00000, 16), 0x1000)
            threads, free_before = k.others(), list(k.free)
            result, report = retire(k)
            self.assertEqual(result, 0, case)
            self.assertEqual(k.others(), [], case)
            self.assertEqual((report.retired, report.drained, report.queue), (len(threads), 254, AS_FOUND), case)
            # What plain deletes leave: the last one deleted comes out first.
            self.assertEqual(list(k.free), threads[::-1] + free_before, case)

    def test_a_frame_in_prepared_memory_is_refused_before_anything_changes(self):
        cases = [  # (stack, size, refused)
            (0x01000000, 0x1000, True),                   # in the staged core
            (0x017FF000, 0x1000, True),                   # the last page of the staging area
            (0x01800000, 0x1000, False),                  # just above it
            (0x00FFF000, 0x1000, False),                  # frame ends where the staging area starts
            (0x00FFF004, 0x1000, True),                   # four bytes in
            (0x00FFE000, 0x2000 - 0x10, False),           # ends 16 bytes below
            (0x01800000, 0x2A0, False),                   # frame starts at the area's end
            (0x000FF000, 0x800, True),                    # below 1 MiB: trampoline, arguments, its stack
            (0x0007F000, 0x1000, False),                  # frame ends at 0x80000
            (0x000FFE00, 0x4A0, False),                   # frame starts at 0x100000
            (0xFFFFFF00, 0x400, False),                   # wraps: 64-bit sums, no range reached
            (0x00206AC0, 0x400, False),                   # where it is in launcHER
        ]
        for stack, size, refused in cases:
            k = Kernel()
            k.add(WAIT, 0x00300000, 0x1000)
            bad = k.add(WAIT, stack, size)
            k.add(READY, 0x00400000, 0x1000)
            before = (list(k.status), list(k.free))
            result, report = retire(k)
            if refused:
                self.assertEqual(result, -errno.EFAULT, hex(stack))
                self.assertEqual(report.fields(), (1, 0, 0, 0, UNTOUCHED, bad), hex(stack))
                self.assertEqual((k.log, k.frames), ([], []), hex(stack))
                self.assertEqual((list(k.status), list(k.free)), before, hex(stack))
            else:
                self.assertEqual((result, report.retired, k.others()), (0, 3, []), hex(stack))
        # An empty or reversed range protects nothing; no ranges at all is fine.
        for protect in (((0x01000000, 0x01000000),), ((0x01800000, 0x01000000),), ()):
            k = Kernel()
            k.add(WAIT, 0x01000000, 0x1000)
            self.assertEqual(retire(k, protect)[0], 0)

    def test_a_thread_that_cannot_be_deleted_is_an_error(self):
        k = Kernel()
        k.add(WAIT, 0x00300000, 0x1000)
        stuck = k.add(WAIT, 0x00310000, 0x1000)
        k.fail_delete.add(stuck)
        result, report = retire(k)
        self.assertEqual((result, report.failed_tid, report.retired), (-errno.EBUSY, stuck, 0))
        self.assertEqual(k.others(), [stuck])
        self.assertNotIn("create", [e[0] for e in k.log])
        # One the kernel will not terminate stays as it is, so its delete fails too.
        k = Kernel()
        stuck = k.add(WAIT, 0x00300000, 0x1000)
        k.fail_terminate.add(stuck)
        result, report = retire(k)
        self.assertEqual((result, report.failed_tid, k.status[stuck]), (-errno.EBUSY, stuck, WAIT))

    def test_a_placeholder_that_cannot_be_deleted_is_an_error(self):
        k = Kernel()
        k.add(WAIT, 0x00300000, 0x1000)
        k.fail_delete.add(77)
        result, report = retire(k)
        self.assertEqual((result, report.failed_tid, report.retired, report.drained),
                         (-errno.EBUSY, 77, 1, 254))
        self.assertEqual(k.others(), [77])            # everything else was still released

    def test_a_wrong_id_from_the_kernel_is_an_error(self):
        for bad in (0, 1, 256, 1000, 5):              # idle, the caller, out of range, a repeat
            k = Kernel()
            k.add(WAIT, 0x00300000, 0x1000)
            k.create_script = [3, 4, 5, bad]
            result, report = retire(k)
            self.assertEqual((result, report.failed_tid, report.drained), (-errno.EIO, bad, 3), bad)
            self.assertEqual(report.queue, AS_FOUND)
            self.assertEqual(k.others(), [], bad)     # the three it took were given back
            self.assertEqual(k.log[-3:], [("delete", 5), ("delete", 4), ("delete", 3)], bad)

    def test_bad_arguments(self):
        k = Kernel()
        ops, report = k.ops(), Report(9, 9, 9, 9, 9, 9)
        ranges = (Range * 1)(Range(0, 0))
        call = LIB.pops_handoff_retire_threads
        self.assertEqual(call(None, None, ranges, 1, c.byref(report)), -errno.EINVAL)
        self.assertEqual(report.fields(), (0, 0, 0, 0, 0, 0))        # cleared first
        self.assertEqual(call(c.byref(ops), None, ranges, 1, None), -errno.EINVAL)
        self.assertEqual(call(c.byref(ops), None, None, 1, c.byref(report)), -errno.EINVAL)
        self.assertEqual(call(c.byref(ops), None, None, 0, c.byref(report)), 0)
        for name, kind in (("self", SELF_FN), ("refer", REFER_FN), ("terminate", TID_FN),
                           ("remove", TID_FN), ("create", CREATE_FN)):
            broken = k.ops()
            setattr(broken, name, kind())
            self.assertEqual(call(c.byref(broken), None, ranges, 1, c.byref(report)), -errno.EINVAL, name)
        for self_id in (0, -1, 256, 1 << 20):
            k = Kernel()
            k.self_id = self_id
            k.add(WAIT, 0x00300000, 0x1000)
            result, report = retire(k)
            self.assertEqual((result, k.log), (-errno.EINVAL, []), self_id)

    def test_header_constants(self):
        h = (ROOT / "common/include/pops_handoff.h").read_text()
        for line in ("#define POPS_HANDOFF_MAX_THREADS    256",
                     "#define POPS_HANDOFF_THS_DORMANT    0x10",
                     "#define POPS_HANDOFF_RESET_FRAME    UINT32_C(0x2a0)",
                     "#define POPS_HANDOFF_REPORT_ADDR    UINT32_C(0x00084300)",
                     "#define POPS_HANDOFF_REPORT_MAGIC   UINT32_C(0x464f4850)"):
            self.assertIn(line, h)
        boot = (ROOT / "common/include/pops_bootstrap.h").read_text()
        # The report sits behind the trampoline's arguments (0x84200 + 176 bytes).
        self.assertIn("#define POPS_TRAMPOLINE_ARGS     UINT32_C(0x00084200)", boot)
        self.assertIn("char     arg_strings[128];", boot)
        self.assertIn("#define POPS_STAGING_BASE        UINT32_C(0x01000000)", boot)
        self.assertIn("#define POPS_STAGING_CAPACITY    UINT32_C(0x00800000)", boot)


TRAMPOLINE = ROOT / "launcher/src/pops_trampoline.S"
TRAMP_ADDR, TRAMP_ARGS, STAGING, CORE = 0x00084000, 0x00084200, 0x01000000, 0x00200000
EIE = 0x00010000
DI, SYSCALL = 0x42000039, 0x0000000C
STORE_OPS = (0x28, 0x29, 0x2B, 0x2E, 0x3F, 0x1F, 0x2A, 0x2C, 0x2D, 0x38, 0x39, 0x3D)


class Watched(R.Machine):
    """Counts the trampoline's stores made while interrupts are enabled."""

    def __init__(self):
        super().__init__()
        self.record = False
        self.stores_enabled = 0
        self.stores_disabled = 0

    def write(self, addr, data, record=False):
        if record:
            if self.status & EIE:
                self.stores_enabled += 1
            else:
                self.stores_disabled += 1
        super().write(addr, data, record)


def trampoline_machine(misses=0):
    words, _ = R.assemble(TRAMPOLINE.read_text(), TRAMP_ADDR)
    m = Watched()
    m.di_misses = misses
    m.write(TRAMP_ADDR, b"".join(w.to_bytes(4, "little") for w in words))
    core = bytes(range(256)) * 4
    # PopsTrampolineArgs as pops_trampoline_args_init writes them, with a
    # short BSS so the run stays small (the clears are tools/test_pops_launch_hooks.py's).
    args = struct.pack("<IIIIIIIi4I", 0x00200008, 0x0086FF00, 0x100, 0x3C30, STAGING, CORE, len(core),
                       1, TRAMP_ARGS + 48, 0, 0, 0)
    m.write(TRAMP_ARGS, args + b"pops0:IMAGE.VCD\0")
    m.write(STAGING, core)
    m.gpr[4] = TRAMP_ARGS
    return m, words, core


class Trampoline(unittest.TestCase):
    def run_to_exec(self, misses):
        m, _words, core = trampoline_machine(misses)
        calls, pc = [], TRAMP_ADDR
        while True:
            try:
                m.run(pc, 0xFFFFFFFC, limit=4000000)
            except R.Syscall as call:
                calls.append((call.number, m.status & EIE, m.lo(29) & R.M32))
                if call.number == 7:
                    return m, calls, core
                pc = call.pc + 4

    def test_interrupts_are_off_before_the_first_store(self):
        for misses in (0, 1, 7):
            m, calls, core = self.run_to_exec(misses)
            self.assertEqual(m.stores_enabled, 0, misses)
            self.assertGreater(m.stores_disabled, 0x4000 // 4 + 0x100000 // 4)
            # FlushCache(0), FlushCache(2), ExecPS2: interrupts still off, on
            # the trampoline's own stack below 1 MiB.
            self.assertEqual(calls, [(0x64, 0, 0x0008FFF0), (0x64, 0, 0x0008FFF0), (7, 0, 0x0008FFF0)], misses)
            self.assertEqual(m.di_misses, 0)
            self.assertEqual(m.read(CORE, len(core)), core)
            # Nothing but EIE changed in Status.
            self.assertEqual(m.status, 0x70030C11 & ~EIE)

    def test_a_di_that_never_takes_never_reaches_a_store(self):
        m, _words, _core = trampoline_machine(1 << 30)
        with self.assertRaises(RuntimeError):         # the model's step limit, still in the loop
            m.run(TRAMP_ADDR, 0xFFFFFFFC, limit=20000)
        self.assertEqual((m.stores_enabled, m.stores_disabled), (0, 0))
        self.assertTrue(TRAMP_ADDR <= m.pc < TRAMP_ADDR + 0x30, hex(m.pc))

    def test_di_comes_first_in_the_code(self):
        _m, words, _core = trampoline_machine()
        at = words.index(DI)
        self.assertEqual(words.count(DI), 1)
        first_store = min(i for i, w in enumerate(words) if (w >> 26) in STORE_OPS)
        first_syscall = words.index(SYSCALL)
        self.assertLess(at, first_store)
        self.assertLess(at, first_syscall)
        # move $s0,$a0 / li $sp / di: the stack is the trampoline's own before
        # interrupts go off, and nothing before the di touches memory.
        self.assertEqual(at, 3)
        self.assertEqual(words[1] >> 16, 0x3C1D)       # lui $sp
        # ps2sdk's DI(): di, sync.p, mfc0 Status, test EIE, loop back to the di.
        self.assertEqual(words[at + 1:at + 3], [0x0000040F, 0x400C6000])
        self.assertEqual(words[at + 5] >> 16, 0x1580)  # bnez $t0
        self.assertEqual(R.sext16(words[at + 5] & 0xFFFF), -6)
        self.assertNotIn(0x42000038, words)            # no ei: ExecPS2 leaves EIE clear as well
        self.assertLessEqual(4 * len(words), 0x180)

    def test_the_model_follows_the_user_mode_rule(self):
        m = R.Machine()
        self.assertEqual(m.status, 0x70030C11)         # user mode, EDI and EIE set
        m.execute(DI, 0)
        self.assertEqual(m.status, 0x70020C11)
        m.execute(0x42000038, 0)
        self.assertEqual(m.status, 0x70030C11)
        m.status = 0x70010C11                          # user mode without EDI: di does nothing
        m.execute(DI, 0)
        self.assertEqual(m.status, 0x70010C11)
        m.status = 0x70010C01                          # kernel mode
        m.execute(DI, 0)
        self.assertEqual(m.status, 0x70000C01)


def original_image():
    import gen_pops_builtin_db as G
    return bytes(G.image())


@unittest.skipUnless(os.environ.get("POPSTARTER_TEST_ELF"), "POPSTARTER_TEST_ELF not set")
class Original(unittest.TestCase):
    """What launcHER's handoff is measured against, in r13's MAIN image
    (loaded at 0x870000)."""

    BASE = 0x870000

    @classmethod
    def setUpClass(cls):
        img = original_image()
        cls.words = struct.unpack("<%dI" % (len(img) // 4), img[:len(img) // 4 * 4])

    def word(self, addr):
        return self.words[(addr - self.BASE) // 4]

    def stubs(self):
        out = {}
        for i in range(len(self.words) - 1):
            if (self.words[i] & 0xFFFF0000) == 0x24030000 and self.words[i + 1] == SYSCALL:
                out.setdefault(self.words[i] & 0xFFFF, []).append(self.BASE + 4 * i)
        return out

    def test_popstarter_cannot_create_a_thread(self):
        stubs = self.stubs()
        # CreateThread 0x20, DeleteThread 0x21, StartThread 0x22, ExitThread
        # 0x23 is there (crt0), TerminateThread 0x25: no stub, so POPStarter
        # is the kernel's only thread when it calls ExecPS2.
        for number in (0x20, 0x21, 0x22, 0x25):
            self.assertNotIn(number, stubs, hex(number))
        self.assertEqual(stubs[7][0], 0x91AA90)        # ExecPS2
        self.assertEqual(stubs[0x64][1], 0x91AB70)     # FlushCache

    def test_popstarter_enters_pops_with_one_exec(self):
        jal = lambda target: 0x0C000000 | (target >> 2)
        # memset(0x100000, 0, 0x100000), then FlushCache(0), FlushCache(2) ...
        self.assertEqual([self.word(a) for a in (0x87C160, 0x87C164, 0x87C168, 0x87C16C)],
                         [jal(0x91AB70), 0x0000202D, jal(0x91AB70), 0x24040002])
        # ... six calls (file and SIF services closed and opened again; not
        # copied by launcHER) and ExecPS2(0x00200000, 0, 1, argv).
        self.assertEqual([self.word(a) for a in range(0x87C1C0, 0x87C1D4, 4)],
                         [0x3C040020, 0x0000282D, 0x24060001, jal(0x91AA90), 0x8FC70014])
        calls = [a for a in range(0x87C170, 0x87C1A0, 8)]
        self.assertEqual([self.word(a) >> 26 for a in calls], [3] * 6)
        # No di, no ei, no Status write between the last clear and the call:
        # POPStarter's handlers stay live and its code intact up to ExecPS2.
        tail = [self.word(a) for a in range(0x87C138, 0x87C1D4, 4)]
        for w in tail:
            self.assertNotIn(w, (DI, 0x42000038))
            self.assertNotEqual(w & 0xFFE0F800, 0x40806000)   # mtc0 $x, Status
        # The call is not reached twice: one jal to the ExecPS2 stub here, one
        # in the ELF loader path at 0x8704d8.
        self.assertEqual([self.BASE + 4 * i for i, w in enumerate(self.words) if w == jal(0x91AA90)],
                         [0x8704D8, 0x87C1CC])

    def test_the_vcommon_restore_is_off_in_the_shipped_build(self):
        # Before ExecPS2 POPStarter calls SetVCommonHandler(8, 0x80000280)
        # (syscall 0xe) when preset byte 0x10000c of its ELF is 1; it is 0.
        self.assertEqual([self.word(a) for a in (0x87C1A0, 0x87C1A4, 0x87C1A8)],
                         [0x8F833818, 0x24020001, 0x14620005])
        self.assertEqual(self.word(0x91AAA0), 0x2403000E)
        elf = Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes()
        phoff, = struct.unpack_from("<I", elf, 0x1C)
        _type, offset, vaddr = struct.unpack_from("<III", elf, phoff)
        self.assertEqual(vaddr, 0x00100000)
        self.assertEqual(elf[offset + 0x0C], 0)


class Source(unittest.TestCase):
    def test_threads_are_retired_right_before_the_jump(self):
        src = (ROOT / "launcher/src/handler_pops.c").read_text()
        body = src[src.index("int launchPOPS("):]
        order = ["res = pops_resident_install(",
                 "memcpy((void *)POPS_TRAMPOLINE_ADDR",
                 "FlushCache(2);",
                 'DPRINTF("POPS: Transferring control to trampoline',
                 "#ifdef LAUNCHER_BOOT_TRACE_STOP_BEFORE_HANDOFF",
                 "res = popsHandoffRetireThreads();",
                 "((void (*)(void *))POPS_TRAMPOLINE_ADDR)((void *)POPS_TRAMPOLINE_ARGS);"]
        at = [body.index(s) for s in order]
        self.assertEqual(at, sorted(at))
        for s in order[5:]:
            self.assertEqual(src.count(s), 1, s)
        # Between the retire call and the jump: its error check, nothing else.
        # No trace line, RPC or wait may follow the retire call.
        between = body[at[5] + len(order[5]):at[6]]
        code = "\n".join(line for line in between.splitlines()
                         if line.strip() and not line.strip().startswith(("/*", "*")))
        self.assertEqual(code.split(), 'if (res) { msg("POPS: Handoff thread cleanup failed: %d\\n", res); '
                                       'return res; }'.split())
        # The preflight stop (diagnostic builds) returns before it.
        stop = body[at[4]:at[5]]
        self.assertIn("SleepThread();\n  return 0;\n#endif", stop)

    def test_glue_gives_the_kernel_calls_and_the_prepared_ranges(self):
        glue = (ROOT / "launcher/src/pops_handoff_ee.c").read_text()
        for call in ("GetThreadId()", "ReferThreadStatus(tid, &info)", "TerminateThread(tid)",
                     "DeleteThread(tid)", "CreateThread(&thread)"):
            self.assertEqual(glue.count(call), 1, call)
        self.assertNotIn("StartThread", glue)          # the placeholders never run
        self.assertIn("{UINT32_C(0x00080000), UINT32_C(0x00100000)},", glue)
        self.assertIn("{POPS_STAGING_BASE, POPS_STAGING_BASE + POPS_STAGING_CAPACITY},", glue)
        self.assertIn("(volatile int32_t *)POPS_HANDOFF_REPORT_ADDR", glue)
        for other in ("printf", "DPRINTF", "msg(", "SifCallRpc", "WaitSema", "SleepThread", "malloc"):
            self.assertNotIn(other, glue, other)

    def test_both_sources_are_built(self):
        cmake = (ROOT / "launcher/CMakeLists.txt").read_text()
        self.assertEqual(cmake.count("src/pops_handoff_ee.c"), 1)
        self.assertEqual(cmake.count("../common/src/pops_handoff.c"), 1)
        self.assertEqual(cmake.count("src/pops_trampoline.S"), 1)

    def test_trampoline_says_what_it_relies_on(self):
        text = TRAMPOLINE.read_text()
        self.assertLess(text.index("li      $sp, 0x0008fff0"), text.index("\n    di\n"))
        self.assertLess(text.index("\n    di\n"), text.index("sw      $zero, 0($t0)"))
        self.assertEqual(sum(1 for line in text.splitlines() if line.strip() == "syscall"), 3)


@unittest.skipUnless(os.environ.get("POPS_HANDOFF_ELF"), "POPS_HANDOFF_ELF not set")
class BuiltImage(unittest.TestCase):
    def test_linked_launcher_passes_the_layout_check(self):
        run = subprocess.run([sys.executable, str(ROOT / "tools/check_pops_handoff_layout.py"),
                              os.environ["POPS_HANDOFF_ELF"]], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("handoff layout: OK", run.stdout)


if __name__ == "__main__":
    unittest.main()
