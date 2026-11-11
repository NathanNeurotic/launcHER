#!/usr/bin/env python3
"""Statements in the PR #23 status documents that a script can check.

The gap audit (docs/POPSTARTER_GAP_AUDIT_2026-11-11.md) and the documents
corrected from it carry addresses and counts. A review found several of them
wrong, too strong or stale; nothing read those documents mechanically. This
file checks the ones that can be checked.

Native: needs nothing. The CI coverage list in docs/CLOUD_CONTINUATION.md
against the workflow files; one address for the $USBDELAY_ handler in every
document; every spot-check number cited in the audit is defined there.

Original: needs POPSTARTER_TEST_ELF and capstone (and unicorn for the wrapper
run). Static reads of the original, and one bounded run of its embedded file
wrapper through tools/trace_original_pops_io.py, compared with what the audit
states. These are host results, never a console result.

There is no Source class: this change touches no launch code.
"""
import os
import re
import struct
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

AUDIT = ROOT / "docs" / "POPSTARTER_GAP_AUDIT_2026-11-11.md"
CONTINUATION = ROOT / "docs" / "CLOUD_CONTINUATION.md"
WORKFLOWS = ROOT / ".github" / "workflows"

BASE = 0x870000
PRINT = 0x915708
BIOS_HANDLER = (0x88019c, 0x880a24)
OSD_HANDLER = (0x87eb24, 0x88019c)
IGR_SKIN = (0x87e464, 0x87eb24)
TROJAN_LOADER = (0x880a24, 0x881de8)
MAIN_FUNCTION = (0x870b78, 0x87c21c)
CODE_AREA = (0x870000, 0x915000)
BLOCK_SOURCE, BLOCK_RUNS_AT, BLOCK_SIZE = 0x983150, 0x232790, 0x738
WRAPPER_FILE_OFFSET, WRAPPER_SIZE = 0xaf680, 2484
WRAPPER_DEVICE, WRAPPER_DLAY = 0x588, 0x420


def flat(path):
    """A document as one line: phrases are looked up regardless of wrapping."""
    return " ".join(path.read_text(encoding="utf-8").split())


def documents():
    files = [ROOT / "README.md", ROOT / "docs" / "pops-setup.html"]
    files += sorted((ROOT / "docs").glob("*.md"))
    return [p for p in files if p.is_file()]


def usbdelay_handler_citations():
    """(file name, address) for every 'handler `0x...`' beside '$USBDELAY_'."""
    found = []
    pattern = re.compile(r"[Hh]andler `(0x[0-9a-f]+)`")
    for path in documents():
        for line in path.read_text(encoding="utf-8").splitlines():
            for match in pattern.finditer(line):
                near = line[max(0, match.start() - 60):match.end() + 60]
                if "$USBDELAY_" in near:
                    found.append((path.name, int(match.group(1), 16)))
    return found


def workflow_coverage():
    """test file name -> set of workflow file names that run it."""
    runs = {p.name: set() for p in sorted(TOOLS.glob("test_*.py"))}
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        for name in re.findall(r"tools/(test_\w+\.py)", workflow.read_text(encoding="utf-8")):
            if name in runs:
                runs[name].add(workflow.name)
    return runs


def documented_coverage():
    text = CONTINUATION.read_text(encoding="utf-8")
    match = re.search(r"<!-- ci-coverage:begin -->(.*?)<!-- ci-coverage:end -->", text, re.S)
    if not match:
        return None
    nowhere, elsewhere, rest_in_build = set(), {}, False
    for line in match.group(1).splitlines():
        line = line.strip()
        names = set(re.findall(r"`(test_\w+\.py)`", line))
        if line.startswith("- Run by no workflow:"):
            nowhere |= names
        elif line.startswith("- Run by `"):
            workflow = re.match(r"- Run by `([\w.-]+\.yml)`, not by `build\.yml`:", line)
            if workflow:
                elsewhere.setdefault(workflow.group(1), set()).update(names)
        elif line.startswith("- Every other `tools/test_*.py` file is a step of the `host-tests` job"):
            rest_in_build = True
    return nowhere, elsewhere, rest_in_build


class Native(unittest.TestCase):
    def test_ci_coverage_list_matches_the_workflows(self):
        documented = documented_coverage()
        self.assertIsNotNone(documented, "docs/CLOUD_CONTINUATION.md lost its ci-coverage block")
        nowhere, elsewhere, rest_in_build = documented
        runs = workflow_coverage()
        self.assertGreaterEqual(len(runs), 26)
        self.assertEqual(nowhere, {name for name, where in runs.items() if not where},
                         "test files run by no workflow differ from the documented list")
        actual_elsewhere = {}
        for name, where in runs.items():
            if where and "build.yml" not in where:
                for workflow in where:
                    actual_elsewhere.setdefault(workflow, set()).add(name)
        self.assertEqual(elsewhere, actual_elsewhere,
                         "test files run only outside build.yml differ from the documented list")
        self.assertTrue(rest_in_build, "the ci-coverage block lost its closing statement")
        self.assertIn(Path(__file__).name, runs)
        self.assertIn("build.yml", runs[Path(__file__).name], "this file must be a CI step")

    def test_coverage_parser_reports_a_wrong_list(self):
        # The comparison above must be able to fail: a file the workflows run
        # must not be accepted in the "no workflow" set, and the reverse.
        runs = workflow_coverage()
        unrun = {name for name, where in runs.items() if not where}
        self.assertNotIn("test_launch_args.py", unrun)
        self.assertIn("launch-args.yml", runs["test_launch_args.py"])
        self.assertNotIn("build.yml", runs["test_launch_args.py"])

    def test_usbdelay_handler_address_is_cited_one_way(self):
        cited = usbdelay_handler_citations()
        self.assertGreaterEqual(len(cited), 2, "expected the audit and the inventory to cite it")
        self.assertEqual(len({address for _name, address in cited}), 1, cited)

    def test_cited_spot_checks_are_defined(self):
        text = AUDIT.read_text(encoding="utf-8")
        defined = {int(n) for n in re.findall(r"^\| S(\d+) \|", text, re.M)}
        self.assertEqual(defined, set(range(1, max(defined) + 1)), "spot-check rows are not contiguous")
        cited = {int(n) for n in re.findall(r"\bS(\d+)\b", text)}
        self.assertFalse(cited - defined, "cited but never defined: %s" % sorted(cited - defined))

    def test_no_document_keeps_a_withdrawn_statement(self):
        withdrawn = ("Every banner `printf` is skipped",
                     "the fifteen call slots",
                     "The worktree `REPOP.worktrees/pr23` is at that commit",
                     "Use the worktree `REPOP.worktrees/pr23`",
                     "no outcome is fatal; the function returns 1",
                     "delays inside its USB/SMB file driver on first use")
        for path in documents():
            text = flat(path)
            for phrase in withdrawn:
                self.assertNotIn(phrase, text, path.name)


HAVE = bool(os.environ.get("POPSTARTER_TEST_ELF"))
IMAGE = None
if HAVE:
    try:
        import capstone  # noqa: F401
        import popstarter_r13_commands as COMMANDS
        import trace_original_pops_io as TRACE
        IMAGE = TRACE.decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes())
    except (Exception, SystemExit):
        HAVE = False
HAVE_UNICORN = False
if HAVE:
    try:
        import unicorn  # noqa: F401
        HAVE_UNICORN = True
    except Exception:
        pass


def word(address):
    return struct.unpack_from("<I", IMAGE, address - BASE)[0]


def print_call_census(low, high):
    """(call sites, those with no quiet-flag test before them) in [low, high).

    A site counts as tested when, in the 12 instructions before it, a
    `beq v1,v0` jumps past the call and `lw v1,0x38b0(gp)` stands one or two
    instructions before that branch. A pattern, not a flow analysis.
    """
    call = 0x0c000000 | (PRINT >> 2)
    quiet = 0x8f8338b0
    sites, untested = [], []
    for site in range(low, high, 4):
        if word(site) != call:
            continue
        sites.append(site)
        tested = False
        for back in range(1, 13):
            address = site - 4 * back
            value = word(address)
            if value >> 16 == 0x1062:
                offset = value & 0xffff
                offset -= 0x10000 if offset & 0x8000 else 0
                if address + 4 + 4 * offset > site and quiet in (word(address - 4), word(address - 8)):
                    tested = True
                    break
        if not tested:
            untested.append(site)
    return sites, untested


@unittest.skipUnless(HAVE, "needs POPSTARTER_TEST_ELF and capstone")
class Original(unittest.TestCase):
    """What the audit states, against the original's own bytes."""

    @classmethod
    def setUpClass(cls):
        cls.audit = flat(AUDIT)

    def test_usbdelay_handler_address(self):
        chains = [address for address, text in COMMANDS.command_chains(IMAGE)
                  if text.startswith("$USBDELAY_")]
        self.assertEqual(chains, [0x89dbe0])
        self.assertEqual(word(0x89dbe4), 0x24020024)       # li v0,'$': the compare one word on
        for name, address in usbdelay_handler_citations():
            self.assertEqual(address, chains[0], name)

    def test_print_calls_and_the_quiet_flag(self):
        expected_rows = (("BIOS handler", BIOS_HANDLER), ("OSD handler", OSD_HANDLER),
                         ("IGR skin function", IGR_SKIN), ("TROJAN loader", TROJAN_LOADER),
                         ("`main`", MAIN_FUNCTION))
        for label, (low, high) in expected_rows:
            sites, untested = print_call_census(low, high)
            self.assertIn("%s: %d" % (label, len(sites)), self.audit)
            self.assertIn("%d without" % len(untested), self.audit)
            if 0 < len(untested) <= 3:
                for site in untested:
                    self.assertIn("`%#x`" % site, self.audit, label)
        sites, untested = print_call_census(*BIOS_HANDLER)
        self.assertEqual((len(sites), untested), (14, [0x8805b4, 0x880984]))
        self.assertIn("BIOS handler: 14 call sites, 2 without the test", self.audit)
        sites, untested = print_call_census(*CODE_AREA)
        self.assertEqual((len(sites), len(untested)), (2031, 145))
        self.assertIn("2,031, 145 without", self.audit)
        self.assertIn("1,886 of the 2,031 call sites", self.audit)
        self.assertIn("Most print calls are skipped while it is 1, not all", self.audit)

    def test_igr_skin_function_return_values(self):
        low, high = IGR_SKIN
        returns = set()
        for address in range(low, high, 4):
            if word(address) == 0xafc00008:                 # sw zero,8(fp)
                returns.add(0)
            elif word(address) == 0xafc20008:               # sw v0,8(fp)
                for back in (4, 8):
                    value = word(address - back)
                    if value >> 16 == 0x2402:               # li v0,imm
                        imm = value & 0xffff
                        returns.add(imm - 0x10000 if imm & 0x8000 else imm)
                        break
                else:
                    self.fail("return value at %#x is not a constant" % address)
        self.assertEqual(returns, {1, 0, -666})
        # The abort-flag test is the function's first decision and stores 0.
        self.assertEqual([word(a) for a in (0x87e474, 0x87e478, 0x87e47c, 0x87e488)],
                         [0x8f8338dc, 0x24020001, 0x14620003, 0xafc00008])
        # The -666 path sets the abort flag.
        self.assertEqual([word(a) for a in (0x87e4b8, 0x87e4bc)], [0xaf8238dc, 0x2402fd66])
        self.assertIn("the function returns 0 at once and opens nothing (`0x87e474..0x87e488`)", self.audit)
        self.assertIn("sets the abort flag `gp+0x38dc = 1` and returns -666", self.audit)
        self.assertNotIn("no outcome is fatal; the function returns 1", self.audit)

    def test_igr_skin_gates_sit_in_main(self):
        slot_refs = [(a, word(a) >> 26) for a in range(*MAIN_FUNCTION, 4)
                     if (word(a) >> 21) & 31 == 30 and word(a) & 0xffff == 0x1108
                     and word(a) >> 26 in (0x23, 0x2b)]
        self.assertEqual(slot_refs, [(0x870ce8, 0x2b), (0x8712ec, 0x2b), (0x876a90, 0x23)])
        self.assertEqual(word(0x8712d0), 0x3484002d)        # ori a0,a0,0x2d: preset 0x10002d
        self.assertEqual(word(0x876a84), 0x8f8238dc)        # lw v0,0x38dc(gp) before the call
        self.assertEqual(word(0x876b18), 0x0c000000 | (IGR_SKIN[0] >> 2))
        self.assertEqual(word(0x876b20), 0x8f8238dc)        # and again after it
        for phrase in ("`0x870ce8`", "`0x8712ec`", "`0x876a90`", "`0x876b20`"):
            self.assertIn(phrase, self.audit)

    def test_game_folder_once_flag_sites(self):
        loads, stores = [], []
        for address in range(*CODE_AREA, 4):
            value = word(address)
            if (value >> 21) & 31 == 28 and value & 0xffff == 0x38e0:
                if value >> 26 == 0x23:
                    loads.append(address)
                elif value >> 26 == 0x2b:
                    stores.append(address)
        self.assertEqual(loads, [0x87ee18, 0x8804ec, 0x880c90, 0x882050, 0x88348c, 0x8d5204, 0x8d5f04])
        self.assertEqual(stores, [0x870c58] + [a + 0x14 for a in loads])
        self.assertTrue(BIOS_HANDLER[0] <= 0x8804ec < BIOS_HANDLER[1])
        rows = [line for line in AUDIT.read_text(encoding="utf-8").splitlines()
                if line.startswith("| `0x38e0` |")]
        self.assertEqual(len(rows), 1)
        statement = rows[0].split("|")[2]
        named = {int(x, 16) for x in re.findall(r"`(0x[0-9a-f]{6})`", statement)}
        # 0x8d4f84 is named there as the start of the VMCDIR.TXT reader, not as a site.
        self.assertEqual(named - {0x8d4f84}, set(loads) | {0x870c58})

    def test_always_live_block_slot_pairs(self):
        block = IMAGE[BLOCK_SOURCE - BASE:BLOCK_SOURCE - BASE + BLOCK_SIZE]
        pairs = [BLOCK_RUNS_AT + off for off in range(0, BLOCK_SIZE - 4, 4)
                 if struct.unpack_from("<II", block, off) == (0x10000001, 0)]
        first = [a for a in pairs if a < 0x232800]
        second = [a for a in pairs if a >= 0x232800]
        self.assertEqual(first, list(range(0x2327d0, 0x2327f8, 8)))
        self.assertEqual(second, list(range(0x232d08, 0x232ec0, 8)))
        self.assertEqual(second[-1] + 16, BLOCK_RUNS_AT + BLOCK_SIZE)
        self.assertIn("The block holds %d such pairs (%d at `0x2327d0..0x2327f0`, %d at `0x232d08..0x232eb8`)"
                      % (len(pairs), len(first), len(second)), self.audit)
        row = re.search(r"Each hooks one of ten fixed call slots, one per file number: ([^.]*)\.", self.audit)
        self.assertIsNotNone(row)
        listed = [int(x, 16) for x in re.findall(r"\d `(0x[0-9a-f]+)`", row.group(1))]
        self.assertEqual(len(listed), 10)
        self.assertEqual(len(set(listed)), 10)
        self.assertTrue(set(listed) <= set(pairs), "a listed slot is not an empty pair in the block")

    @unittest.skipUnless(HAVE_UNICORN, "needs unicorn")
    def test_wrapper_delay_call(self):
        blob = IMAGE[WRAPPER_FILE_OFFSET:WRAPPER_FILE_OFFSET + WRAPPER_SIZE]
        self.assertEqual(IMAGE.count(b"DLAY"), 1)
        self.assertEqual(IMAGE.find(b"DLAY") + BASE, 0x91fb30)

        def run(patch, sequence):
            calls = []

            def imports(machine, imported, args):
                library, ordinal = imported
                if (library, ordinal) == ("sysclib", 23):
                    machine.uc.mem_write(args[0], machine.string(args[1]).encode("ascii") + b"\0")
                    calls.append("copy")
                    return args[0]
                if library == "thbase":
                    calls.append((ordinal, args[0]))
                    return 0
                if library == "thsemap":
                    calls.append("sema%d" % ordinal)
                    return 0
                self.assertEqual(library, "ioman")
                calls.append("backend open" if ordinal == 4 else "backend")
                return 7 if ordinal == 4 else 0
            machine = TRACE.Machine(TRACE.Module(blob, TRACE.WRAPPER_SHA), imports)
            self.assertEqual(bytes(machine.uc.mem_read(WRAPPER_DLAY, 4)), b"DLAY")
            table = machine.word(WRAPPER_DEVICE + 16)
            self.assertEqual(table, 0x544)
            if patch is not None:
                machine.uc.mem_write(WRAPPER_DLAY, bytes([patch, 0, 0, 0]))
            machine.put(TRACE.Machine.FILE, 0, 0, WRAPPER_DEVICE, 0)
            machine.uc.mem_write(TRACE.Machine.REQUEST, b"/IMAGE.VCD\0")
            per_call = []
            for entry in sequence:
                start = len(calls)
                extra = {3: (TRACE.Machine.REQUEST, 1), 4: (), 5: (TRACE.Machine.BUFFER, 512),
                         7: (0, 0)}[entry]
                machine.call(machine.word(table + 4 * entry), TRACE.Machine.FILE, *extra)
                per_call.append(calls[start:])
            return per_call

        for patch, micro in [(None, 5000000)] + [(n, n * 1000000) for n in range(10)]:
            per_call = run(patch, [3, 5, 7, 4, 3, 5, 4])
            self.assertEqual(per_call[0], ["copy", "sema8", (33, micro), "sema6", "backend open"], patch)
            later = [c for calls in per_call[1:] for c in calls if isinstance(c, tuple)]
            self.assertEqual(later, [], patch)
        per_call = run(3, [5, 7, 4, 3])
        self.assertEqual([[c for c in calls if isinstance(c, tuple)] for calls in per_call],
                         [[], [], [], [(33, 3000000)]])
        self.assertIn("`thbase` 33 with argument 5,000,000", self.audit)
        self.assertIn("argument n x 1,000,000, once, before the first backend open", self.audit)


if __name__ == "__main__":
    unittest.main()
