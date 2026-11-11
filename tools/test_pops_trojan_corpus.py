#!/usr/bin/env python3
"""TROJAN_n.BIN files of a fix collection the user has, through launcHER's
rules and, with the reference inputs, through POPStarter r13's own loader.

Skipped unless POPS_TROJAN_CORPUS names a folder. Every TROJAN_<n>.BIN and
PATCH_<n>.BIN below it is read, never written or copied, and counted once
per content and slot number. Nothing of any collection is in this
repository: no bytes, no names, no hashes. The test prints counts only (a
failure names the file it failed on, on the machine that has it).

Native: launcHER's verdict, payload scan (C against its Python twin,
  tools/pops_trojan_model.py) and staging for each TROJAN file.
Original: the same files, one at a time, through the original's loader
  FUN_00880a24 under Unicorn (POPSTARTER_TEST_ELF, POPS_TEST_ELF, unicorn):
  same verdict; for a file launcHER loads, the same slot words and the same
  payload bytes at the same address, and no other byte changed.
OriginalPatch: each PATCH file through the original's FUN_00881de8 and
  through pops_fix_stage on the same POPS image: where launcHER applies the
  file, the whole image must be the original's. (The TROJAN work split the
  staging function; this is the check that PATCH files still come out the
  same.)

What a payload then does when the game runs is not tested here. Not a
console test.
"""
import collections
import ctypes as c
import hashlib
import os
from pathlib import Path
import re
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import pops_trojan_model as model  # noqa: E402
import test_pops_trojan as T  # noqa: E402

CORPUS = os.environ.get('POPS_TROJAN_CORPUS')
NAME = re.compile(r'^(TROJAN|PATCH)_([0-9])\.BIN$', re.IGNORECASE)
ARENA = 0x01420000
OWNED = (0x0143a000, 0x01460200)
_FILES = {}


def tearDownModule():
    T.tearDownModule()


def files(kind='TROJAN'):
    """[(path, slot, data, copies)], one per content and slot number."""
    if not _FILES:
        seen = {'TROJAN': {}, 'PATCH': {}}
        for path in sorted(Path(CORPUS).rglob('*')):
            match = NAME.match(path.name)
            if not match or not path.is_file():
                continue
            data = path.read_bytes()
            found = seen[match.group(1).upper()]
            key = (hashlib.sha256(data).digest(), int(match.group(2)))
            if key in found:
                found[key][3] += 1
            else:
                found[key] = [path, key[1], data, 1]
        for name, found in seen.items():
            _FILES[name] = [tuple(entry) for entry in found.values()]
    return _FILES[kind]


def hosted_class(session, result):
    if result == 0:
        return 'loaded'
    if result == T.SKIP_INVALID:
        return 'Invalid'
    if result == T.SKIP_OUTDATED:
        return 'Skipped (outdated)'
    return 'not loaded: ' + session.lib.pops_trojan_reason_text(session.state.reason).decode()


def report(title, counts, copies):
    print(title)
    for name, count in counts.most_common():
        print('  %5d files %6d copies  %s' % (count, copies[name], name))


@unittest.skipUnless(CORPUS, 'POPS_TROJAN_CORPUS not set')
class Native(T.Built):
    def test_scan_and_staging(self):
        self.assertTrue(Path(CORPUS).is_dir(), 'POPS_TROJAN_CORPUS is not a folder')
        entries = files()
        self.assertTrue(entries, 'no TROJAN_<n>.BIN below POPS_TROJAN_CORPUS')
        counts, copies = collections.Counter(), collections.Counter()
        without, formats, slot_hooks = collections.Counter(), collections.Counter(), 0
        for path, slot, data, n in entries:
            verdict, info = self.verdict(data, slot)
            session = T.Session(self, T.pristine(), hold=0x100000, offered=True)
            result = session.stage(data, slot)
            self.assertIn(result, (0, T.SKIP_INVALID, T.SKIP_OUTDATED, T.SKIP_UNHOSTED), path)
            self.assertEqual(result in (T.SKIP_INVALID, T.SKIP_OUTDATED), verdict != T.APPLY, path)
            name = hosted_class(session, result)
            counts[name] += 1
            copies[name] += n
            if verdict != T.APPLY:
                continue
            formats[(data[0x0c], data[0x0a], data[0x0e])] += 1
            payload = data[0x40:0x40 + info.size]
            slot_hook = info.hook in model.SLOT_HOOKS.values()
            slot_hooks += slot_hook
            # The scan, in C and in Python, on every payload it accepts.
            if not (info.size | info.load | info.entry) & 3 and \
                    info.load <= info.entry < info.load + info.size:
                self.assertEqual(self.scan(payload, info.load, info.entry),
                                 model.scan(payload, info.load, info.entry), path)
            if result == 0:
                self.assertEqual(session.state.refs & ~model.REF_SLOT, 0, path)
                if slot_hook:
                    self.assertEqual(session.state.chain, 1, path)
                    self.assertEqual(bytes(session.memory), bytes(T.pristine()), path)
                # The same file on a launch that cannot offer the slots.
                plain = T.Session(self, T.pristine(), hold=0x100000)
                again = plain.stage(data, slot)
                needs = slot_hook or session.state.refs & model.REF_SLOT
                self.assertEqual(again, T.SKIP_UNHOSTED if needs else 0, path)
                without['needs the slots' if needs else 'needs no slot'] += 1
            else:
                self.assertEqual(session.state.payload_count, 0, path)
                self.assertEqual(session.slot_words(), T.EMPTY_RUNS, path)
                self.assertEqual(bytes(session.memory), bytes(T.pristine()), path)
        total = sum(n for _, _, _, n in entries)
        print('TROJAN corpus: %d files by content and slot number, %d copies' % (len(entries), total))
        report('launcHER, slots offered:', counts, copies)
        print('  of the loaded: %s; hooks on one of the ten slots: %d of %d applied files' % (
            ', '.join('%d %s' % (v, k) for k, v in sorted(without.items())), slot_hooks,
            sum(formats.values())))
        print('  header (format, byte 0x0a, byte 0x0e): %s' % ', '.join(
            '%d x %r' % (v, k) for k, v in formats.most_common()))


@unittest.skipUnless(CORPUS and T.HAVE_ORIGINAL,
                     'POPS_TROJAN_CORPUS, POPSTARTER_TEST_ELF and POPS_TEST_ELF are optional inputs')
class Original(T.Built):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('unicorn is not installed')
        import pops_trojan_chain as chain
        import trace_original_pops_trojan as tracer
        from trace_original_pops_io import decode_main
        cls.tracer = tracer
        main = decode_main(Path(os.environ['POPSTARTER_TEST_ELF']).read_bytes())
        cls.core = tracer.pops_core()
        # The loader on a core that holds POPStarter's two parts, as the
        # launch places them: its slots are then the ten empty pairs.
        cls.loader = tracer.Loader()
        baseline = bytearray(cls.loader.baseline)
        for source, target, size in (chain.BLOCK1, chain.BLOCK2):
            baseline[target:target + size] = main[source - 0x870000:source - 0x870000 + size]
        cls.loader.baseline = bytes(baseline)

    def test_every_file_against_the_loader(self):
        words = {T.APPLY: 'APPLIED', T.INVALID: 'INVALID', T.OUTDATED: 'OUTDATED'}
        verdicts, loaded, refused = collections.Counter(), 0, 0
        for path, slot, data, _ in files():
            returned, events, after = self.loader.run({b'mass:/POPS/TROJAN_%d.BIN' % slot: data})
            self.assertEqual(returned, 1, path)
            verdict, info = self.verdict(data, slot)
            self.assertEqual(self.tracer.verdicts(events), [words[verdict]], path)
            verdicts[words[verdict]] += 1
            changed = self.loader.changed(after)
            if verdict != T.APPLY:
                self.assertEqual(changed, [], path)
                continue
            # What the original changed: the payload and the hook words.
            hook_end = info.hook + 4 * info.hook_words
            for start, end in changed:
                self.assertTrue(info.load <= start and end <= info.load + info.size or
                                info.hook <= start and end <= hook_end, (path, hex(start), hex(end)))
            self.assertEqual(after[info.load:info.load + info.size], data[0x40:0x40 + info.size], path)
            self.assertEqual(list(struct.unpack_from('<%dI' % info.hook_words, after, info.hook)),
                             list(info.hook_word)[:info.hook_words], path)
            session = T.Session(self, self.core, hold=0x100000, offered=True)
            if session.stage(data, slot) != 0:
                refused += 1
                self.assertEqual(bytes(session.memory), self.core, path)
                continue
            loaded += 1
            # launcHER's copy of the slots, its staged core and the payload
            # it will place are the original's bytes.
            runs = [list(struct.unpack_from('<10I', after, base)) for base in (0x2327d0, 0x232d08)]
            self.assertEqual(session.slot_words(), runs, path)
            expected = bytearray(self.core)
            for base in (0x2327d0 - T.BASE, 0x232d08 - T.BASE):   # not written before the install
                after_core = bytearray(after[T.BASE:T.BASE + T.SIZE])
                after_core[base:base + 0x28] = expected[base:base + 0x28]
                after = after[:T.BASE] + bytes(after_core) + after[T.BASE + T.SIZE:]
            for source, target, size in ((0, 0x232790, 0x738), (0, 0x238a90, 0xd60)):
                at = target - T.BASE   # POPStarter's two parts are not launcHER's
                after_core = bytearray(after[T.BASE:T.BASE + T.SIZE])
                after_core[at:at + size] = expected[at:at + size]
                after = after[:T.BASE] + bytes(after_core) + after[T.BASE + T.SIZE:]
            self.assertEqual(bytes(session.memory), after[T.BASE:T.BASE + T.SIZE], path)
            count, arena = session.copy_out(bytes(0x200000), ARENA, keep=[OWNED])
            self.assertEqual(count, session.state.payload_count, path)
            for address, size, _ in session.records():
                self.assertEqual(arena[address - ARENA:address - ARENA + size],
                                 after[address:address + size], path)
        print('TROJAN corpus vs the original loader: %d files, verdicts %s; %d loaded by launcHER '
              'with the original\'s slot words and payload bytes, %d applied there and not loaded '
              'here' % (sum(verdicts.values()), dict(verdicts), loaded, refused))


@unittest.skipUnless(CORPUS and T.HAVE_ORIGINAL,
                     'POPS_TROJAN_CORPUS, POPSTARTER_TEST_ELF and POPS_TEST_ELF are optional inputs')
class OriginalPatch(T.Built):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('unicorn is not installed')
        import trace_original_pops_trojan as tracer
        cls.tracer = tracer
        cls.core = tracer.pops_core()
        cls.loader = tracer.Loader()
        cls.lib.pops_fix_stage.argtypes = [c.POINTER(T.Context), c.c_void_p, c.c_size_t,
                                           c.c_void_p, c.c_size_t, c.c_uint, c.c_int]
        cls.lib.pops_fix_bind_progressive.argtypes = [c.POINTER(T.Context), c.c_void_p,
                                                      c.c_size_t, c.c_uint32, c.c_uint32]

    def test_every_patch_file_leaves_the_originals_image(self):
        entries = files('PATCH')
        if not entries:
            self.skipTest('no PATCH_<n>.BIN below POPS_TROJAN_CORPUS')
        same, refused, changed_bytes = 0, collections.Counter(), []
        for path, slot, data, _ in entries:
            returned, events, after = self.loader.run({b'mass:/POPS/PATCH_%d.BIN' % slot: data},
                                                      loader=self.tracer.PATCH_LOADER)
            self.assertEqual(returned, 1, path)
            session = T.Session(self, self.core, hold=0)
            self.assertEqual(self.lib.pops_fix_bind_progressive(
                c.byref(session.context), session.pointer, T.SIZE, 0x0143a100, 0x32240001), 0)
            result = self.lib.pops_fix_stage(c.byref(session.context), session.pointer, T.SIZE,
                                             data, len(data), slot, 0)
            self.assertLessEqual(result, 0, path)
            if result:
                refused[result] += 1
                self.assertEqual(bytes(session.memory), self.core, path)
                continue
            # The whole POPS image, and nothing the original changed outside it.
            self.assertEqual(bytes(session.memory), after[T.BASE:T.BASE + T.SIZE], path)
            for start, end in self.loader.changed(after):
                self.assertTrue(T.BASE <= start and end <= T.BASE + T.SIZE,
                                (path, hex(start), hex(end)))
            changed_bytes.append(sum(a != b for a, b in zip(session.memory, self.core)))
            same += 1
        print('PATCH corpus vs the original loader: %d files by content and slot number, %d copies; '
              '%d applied by launcHER with the whole POPS image equal to the original\'s '
              '(%d to %d changed bytes), not applied here: %s' % (
                  len(entries), sum(n for _, _, _, n in entries), same,
                  min(changed_bytes, default=0), max(changed_bytes, default=0),
                  dict(refused) or 'none'))


if __name__ == '__main__':
    unittest.main()
