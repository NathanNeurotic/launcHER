#!/usr/bin/env python3
"""Progressive arithmetic candidate: host and optional original/compiled EE.

This does not install a resident progressive hook. External original bytes
stay in memory. POPSTARTER_TEST_ELF and an EE compiler plus Unicorn enable
the full component comparison; neither is needed for native regressions.
"""
import ctypes as c
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import tempfile
import unittest

from trace_original_pops_display import OriginalDisplay

ROOT = Path(__file__).resolve().parents[1]
CC = os.environ.get('POPS_EE_CC') or shutil.which('mips64r5900el-ps2-elf-gcc')


class State(c.Structure):
    _fields_ = [(n, c.c_uint64) for n in ('fallback_display', 'display', 'scratch')] + [
        (n, c.c_uint32) for n in ('source_32a8', 'source_32ac', 'source_32b0', 'source_32bc',
                                'blocked', 'dy', 'dx', 'dw', 'dh', 'magh', 'magv',
                                'timing_502770', 'timing_23ac08')
    ] + [(n, c.c_uint8) for n in ('region', 'mode_21af94', 'mode_70003300', 'reserved')]


def record(state):
    return {name: getattr(state, name) for name, _ in State._fields_}


FIELDS = {
    'fallback_display': (0x70003290, 8), 'source_32a8': (0x700032a8, 4),
    'source_32ac': (0x700032ac, 4), 'source_32b0': (0x700032b0, 4),
    'source_32bc': (0x700032bc, 4), 'blocked': (0x85a9ac, 4), 'region': (0x127ff52, 1),
    'scratch': (0x502680, 8), 'magh': (0x502688, 4), 'dx': (0x50268c, 4),
    'dy': (0x502690, 4), 'dh': (0x502694, 4), 'dw': (0x502698, 4), 'magv': (0x50269c, 4),
    'timing_502770': (0x502770, 4), 'timing_23ac08': (0x23ac08, 4),
    'mode_21af94': (0x21af94, 1), 'mode_70003300': (0x70003300, 1),
}


def memory_for(state):
    memory = {}
    for name, (address, width) in FIELDS.items():
        data = int(getattr(state, name)).to_bytes(width, 'little')
        memory.update((address + i, byte) for i, byte in enumerate(data))
    return memory


def cases():
    rng = random.Random(0x2394f0)
    result = []
    widths = (0, 255, 256, 257, 320, 384, 512, 640, 641, 0xffffffff)
    for width in widths:
        for region in (ord('E'), ord('A')):
            for blocked in (0, 1, 0xffffffff):
                for edge in (0, 1, 0x7fffffff, 0x80000000, 0xffffffff):
                    s = State()
                    for name, typ in State._fields_:
                        setattr(s, name, rng.getrandbits(c.sizeof(typ) * 8))
                    s.source_32bc, s.region, s.blocked = width, region, blocked
                    s.source_32a8, s.source_32ac, s.source_32b0 = edge, edge, edge
                    result.append(s)
    for _ in range(128):
        s = State()
        for name, typ in State._fields_:
            setattr(s, name, rng.getrandbits(c.sizeof(typ) * 8))
        s.blocked = rng.choice((0, 0, 0, 1))
        s.source_32bc = rng.choice(widths)
        s.region = rng.choice((0, ord('E'), ord('A'), ord('I'), 255))
        result.append(s)
    return result


class ProgressiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        output = Path(cls.tmp.name) / ('progressive.dll' if os.name == 'nt' else 'progressive.so')
        subprocess.run(['gcc', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I', str(ROOT / 'common/include'),
                        str(ROOT / 'common/src/pops_progressive.c'), '-o', str(output)], check=True)
        cls.lib = c.CDLL(str(output))
        cls.lib.pops_progressive_update.argtypes = [c.POINTER(State)]
        cls.lib.pops_progressive_update.restype = None
        live_output = Path(cls.tmp.name) / ('live.dll' if os.name == 'nt' else 'live.so')
        subprocess.run(['gcc', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-DPOPS_PROGRESSIVE_TEST_IO', '-I', str(ROOT / 'common/include'),
                        str(ROOT / 'common/src/pops_progressive.c'),
                        str(ROOT / 'tools/fixtures/pops_progressive_host_io.c'),
                        '-o', str(live_output)], check=True)
        cls.live = c.CDLL(str(live_output))
        cls.read_cb = c.CFUNCTYPE(c.c_uint64, c.c_uint32, c.c_uint)
        cls.write_cb = c.CFUNCTYPE(None, c.c_uint32, c.c_uint64, c.c_uint)
        cls.live.pops_progressive_test_io.argtypes = [cls.read_cb, cls.write_cb]
        cls.live.pops_progressive_live.restype = c.c_uint64

    @classmethod
    def tearDownClass(cls):
        if os.name == 'nt':
            c.windll.kernel32.FreeLibrary.argtypes = [c.c_void_p]
            c.windll.kernel32.FreeLibrary(cls.lib._handle)
            c.windll.kernel32.FreeLibrary(cls.live._handle)
        cls.tmp.cleanup()

    def test_known_widths_region_scaling_and_fallback(self):
        for width, magh, dx, dw in ((256, 4, 320, 1280), (320, 3, 320, 1280),
                                    (384, 2, 384, 1152), (512, 1, 444, 1024),
                                    (640, 1, 320, 1280)):
            for region, dy in ((ord('E'), 61), (ord('A'), 183)):
                s = State(source_32a8=123, source_32ac=2560, source_32b0=240,
                          source_32bc=width, region=region)
                self.lib.pops_progressive_update(c.byref(s))
                self.assertEqual((s.magh, s.dx, s.dw, s.dy, s.dh, s.magv),
                                 (magh, dx, dw, dy, 480, 1))
                expected = (479 << 44) | ((dw - 1) << 32) | (1 << 27) | (magh << 23) | (dy << 12) | dx
                self.assertEqual(s.display, expected)
        s = State(source_32bc=321, fallback_display=0x123456789abcdef0, dx=9, dw=10)
        self.lib.pops_progressive_update(c.byref(s))
        self.assertEqual((s.display, s.dx, s.dw, s.magh), (0x123456789abcdef0, 9, 10, 0))
        self.assertEqual((s.mode_21af94, s.mode_70003300, s.timing_502770, s.timing_23ac08),
                         (0x50, 0x50, 0x8a3a2, 0x69403))

    def test_blocked_only_selects_fallback(self):
        for s in cases():
            s.blocked = 1
            expected = record(s)
            expected['display'] = s.fallback_display
            self.lib.pops_progressive_update(c.byref(s))
            self.assertEqual(record(s), expected)

    def native_live(self, state):
        memory, writes, faults = memory_for(state), [], []
        @self.read_cb
        def read(address, width):
            if width not in (1, 4, 8) or any(address + i not in memory for i in range(width)):
                faults.append(('read', address, width))
                return 0
            return int.from_bytes(bytes(memory[address + i] for i in range(width)), 'little')
        @self.write_cb
        def write(address, value, width):
            if width not in (1, 4, 8) or any(address + i not in memory for i in range(width)):
                faults.append(('write', address, width))
                return
            value &= (1 << (width * 8)) - 1
            writes.append([address, value, width])
            memory.update((address + i, byte) for i, byte in enumerate(value.to_bytes(width, 'little')))
        self.live.pops_progressive_test_io(read, write)
        display = self.live.pops_progressive_live()
        self.assertEqual(faults, [])
        return display, memory, writes

    def test_live_adapter_state_and_no_writes_when_blocked(self):
        for s in cases():
            expected = State.from_buffer_copy(s)
            self.lib.pops_progressive_update(c.byref(expected))
            display, memory, writes = self.native_live(s)
            self.assertEqual(display, expected.display)
            self.assertEqual(memory, memory_for(expected))
            if s.blocked:
                self.assertEqual(writes, [])

    @unittest.skipUnless(os.environ.get('POPSTARTER_TEST_ELF'), 'optional external POPStarter MAIN')
    def test_original_live_write_order(self):
        original = OriginalDisplay(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())
        inputs = cases()
        for s in inputs:
            expected = original.progressive(record(s), with_writes=True)
            display, memory, writes = self.native_live(s)
            self.assertEqual(display, expected['state']['display'])
            self.assertEqual(writes, expected['writes'])
            expected_state = State(**expected['state'])
            self.assertEqual(memory, memory_for(expected_state))
        print(f'Original progressive live ordered writes vs native adapter PASS: {len(inputs)} cases')

    @unittest.skipUnless(CC and os.environ.get('POPSTARTER_TEST_ELF'), 'optional EE compiler and original MAIN')
    def test_original_live_vs_compiled_ee(self):
        try:
            import unicorn as u
            from unicorn import mips_const as r
        except ImportError:
            self.skipTest('optional Unicorn')
        output = Path(self.tmp.name) / 'progressive-live.elf'
        subprocess.run([CC, '-O2', '-G0', '-fno-pic', '-mno-abicalls', '-ffreestanding',
                        '-fno-builtin', '-nostdlib', '-nostartfiles', '-Wall', '-Wextra', '-Werror',
                        '-Wl,-Ttext=0x140000', '-Wl,-e,pops_progressive_live',
                        '-I', str(ROOT / 'common/include'), str(ROOT / 'common/src/pops_progressive.c'),
                        '-o', str(output)], check=True, capture_output=True)
        elf = output.read_bytes()
        entry, phoff = struct.unpack_from('<II', elf, 24)
        ents, count = struct.unpack_from('<HH', elf, 42)
        segments = []
        for i in range(count):
            kind, off, va, _, size, memory, _, _ = struct.unpack_from('<8I', elf, phoff + i * ents)
            if kind == 1:
                self.assertLessEqual(va + memory, 0x2000000)
                segments.append((va, elf[off:off + size]))
        original = OriginalDisplay(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())
        inputs = cases()
        stack, stop = 0x1efff0, 0x1f0000
        for s in inputs:
            measured = original.progressive(record(s), with_writes=True)
            mu = u.Uc(u.UC_ARCH_MIPS, u.UC_MODE_MIPS64 | u.UC_MODE_LITTLE_ENDIAN)
            mu.mem_map(0, 0x2000000)
            mu.mem_map(0x70000000, 0x4000)
            for va, data in segments:
                mu.mem_write(va, data)
            for name, (address, width) in FIELDS.items():
                mu.mem_write(address, int(getattr(s, name)).to_bytes(width, 'little'))
            expected = bytearray(mu.mem_read(0, 0x2000000))
            expected_scratch = bytearray(mu.mem_read(0x70000000, 0x4000))
            for address, value, width in measured['writes']:
                if address >= 0x70000000:
                    at, target = address - 0x70000000, expected_scratch
                else:
                    at, target = address, expected
                target[at:at + width] = value.to_bytes(width, 'little')
            saved = {}
            for name in ('S0', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'FP', 'GP'):
                reg = getattr(r, 'UC_MIPS_REG_' + name)
                saved[reg] = 0x12340000 + reg
                mu.reg_write(reg, saved[reg])
            mu.reg_write(r.UC_MIPS_REG_SP, stack)
            mu.reg_write(r.UC_MIPS_REG_RA, stop)
            mu.emu_start(entry, stop, count=10000)
            self.assertEqual(mu.reg_read(r.UC_MIPS_REG_PC), stop)
            self.assertEqual(mu.reg_read(r.UC_MIPS_REG_V0), measured['state']['display'])
            self.assertEqual(mu.reg_read(r.UC_MIPS_REG_SP), stack)
            for reg, value in saved.items():
                self.assertEqual(mu.reg_read(reg), value)
            actual = bytes(mu.mem_read(0, 0x2000000))
            self.assertEqual(actual[:stack - 0x400], expected[:stack - 0x400])
            self.assertEqual(actual[stack:], expected[stack:])
            self.assertEqual(bytes(mu.mem_read(0x70000000, 0x4000)), expected_scratch)
        print(f'Original progressive live final memory vs compiled EE PASS: {len(inputs)} cases')

    @unittest.skipUnless(os.environ.get('POPSTARTER_TEST_ELF'), 'optional external POPStarter MAIN')
    def test_original_progressive_state(self):
        original = OriginalDisplay(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())
        inputs = cases()
        for s in inputs:
            expected = original.progressive(record(s))
            self.lib.pops_progressive_update(c.byref(s))
            self.assertEqual(record(s), expected)
        print(f'Original progressive state vs native candidate PASS: {len(inputs)} cases')

    @unittest.skipUnless(CC and os.environ.get('POPSTARTER_TEST_ELF'), 'optional EE compiler and original MAIN')
    def test_original_progressive_vs_compiled_ee(self):
        try:
            import unicorn as u
            from unicorn import mips_const as r
        except ImportError:
            self.skipTest('optional Unicorn')
        output = Path(self.tmp.name) / 'progressive.elf'
        subprocess.run([CC, '-O2', '-G0', '-fno-pic', '-mno-abicalls', '-ffreestanding',
                        '-fno-builtin', '-nostdlib', '-nostartfiles', '-Wall', '-Wextra', '-Werror',
                        '-Wl,-Ttext=0x140000', '-Wl,-e,pops_progressive_update',
                        '-I', str(ROOT / 'common/include'), str(ROOT / 'common/src/pops_progressive.c'),
                        '-o', str(output)], check=True, capture_output=True)
        elf = output.read_bytes()
        entry, phoff = struct.unpack_from('<II', elf, 24)
        ents, count = struct.unpack_from('<HH', elf, 42)
        segments = []
        for i in range(count):
            kind, off, va, _, size, memory, _, _ = struct.unpack_from('<8I', elf, phoff + i * ents)
            if kind == 1:
                self.assertLessEqual(va + memory, 0x200000)
                segments.append((va, elf[off:off + size]))
        addr, stop, stack = 0x110000, 0x1f0000, 0x1efff0
        original = OriginalDisplay(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())
        inputs = cases()
        for s in inputs:
            # Fresh CPU state per input. No memory-write hook: Unicorn 2.1.4
            # faults on a taken branch with SD in its delay slot when that
            # hook is installed. Audit every mapped byte after execution.
            mu = u.Uc(u.UC_ARCH_MIPS, u.UC_MODE_MIPS64 | u.UC_MODE_LITTLE_ENDIAN)
            mu.mem_map(0, 0x200000)
            for va, data in segments:
                mu.mem_write(va, data)
            pcs = []
            mu.hook_add(u.UC_HOOK_CODE, lambda uc, pc, size, data: pcs.append(pc))
            expected = original.progressive(record(s))
            mu.mem_write(addr - 16, b'\xa5' * (c.sizeof(State) + 32))
            mu.mem_write(addr, bytes(s))
            saved = {}
            for name in ('S0', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'FP', 'GP'):
                reg = getattr(r, 'UC_MIPS_REG_' + name)
                saved[reg] = 0x12340000 + reg
                mu.reg_write(reg, saved[reg])
            mu.reg_write(r.UC_MIPS_REG_A0, addr)
            mu.reg_write(r.UC_MIPS_REG_SP, stack)
            mu.reg_write(r.UC_MIPS_REG_RA, stop)
            memory_before = bytes(mu.mem_read(0, 0x200000))
            try:
                mu.emu_start(entry, stop, count=10000)
            except u.UcError as exc:
                pc = mu.reg_read(r.UC_MIPS_REG_PC)
                word = bytes(mu.mem_read(pc, 4)).hex()
                raise AssertionError(f'compiled EE stopped at {pc:#x}, instruction {word}, PCs {pcs[-12:]}, RA {mu.reg_read(r.UC_MIPS_REG_RA):#x}, input {record(s)}') from exc
            self.assertEqual(mu.reg_read(r.UC_MIPS_REG_PC), stop)
            self.assertEqual(mu.reg_read(r.UC_MIPS_REG_SP), stack)
            for reg, value in saved.items():
                self.assertEqual(mu.reg_read(reg), value)
            actual = State.from_buffer_copy(mu.mem_read(addr, c.sizeof(State)))
            self.assertEqual(record(actual), expected)
            self.assertEqual(bytes(mu.mem_read(addr - 16, 16)), b'\xa5' * 16)
            self.assertEqual(bytes(mu.mem_read(addr + c.sizeof(State), 16)), b'\xa5' * 16)
            memory_after = bytes(mu.mem_read(0, 0x200000))
            self.assertEqual(memory_before[:addr], memory_after[:addr])
            self.assertEqual(memory_before[addr + c.sizeof(State):], memory_after[addr + c.sizeof(State):])
        print(f'Original progressive state vs compiled EE PASS: {len(inputs)} cases (modeled original 64-bit view)')


if __name__ == '__main__':
    unittest.main()
