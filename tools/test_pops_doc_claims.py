#!/usr/bin/env python3
"""Statements in the PR #23 status documents that a script can check.

The gap audit (docs/POPSTARTER_GAP_AUDIT_2026-11-11.md) and the documents
corrected from it carry addresses and counts. Two reviews found several of
them wrong, too strong or stale, and found that this file pinned less than
the audit said. Section 2b of the audit lists exactly what is checked here;
change that list and this file together.

Native: needs nothing. The CI coverage list in docs/CLOUD_CONTINUATION.md
against the steps the workflow files really run (a small parser for the
subset of YAML they use, itself tested on synthetic texts); one address for
the $USBDELAY_ handler in every document; every spot-check number cited in
the audit is defined there; withdrawn sentences are gone.

Original: needs POPSTARTER_TEST_ELF and capstone (and unicorn for the wrapper
run). Static reads of the original, and one bounded run of its embedded file
wrapper through tools/trace_original_pops_io.py, each compared with whole
phrases of the audit or the inventory. A variable that is set but cannot be
used is a failure, not a skip. These are host results, never a console
result.

Corpus: needs POPS_TROJAN_CORPUS (a folder holding community TROJAN_n.BIN /
PATCH_n.BIN files; nothing from it is stored here). File counts and the hook
word of each TROJAN header against the audit.

There is no Source class: this file reads no launch code.
"""
import hashlib
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
INVENTORY = ROOT / "docs" / "POPSTARTER_R13_INVENTORY.md"
CONTINUATION = ROOT / "docs" / "CLOUD_CONTINUATION.md"
WORKFLOWS = ROOT / ".github" / "workflows"

BASE = 0x870000
GP = 0x9b68f0
PRINT = 0x915708
FOLDER_CHECK = (0x8d8958, 0x8d8b14)          # FUN_008d8958, last instruction 0x8d8b10
BIOS_HANDLER = (0x88019c, 0x880a24)
OSD_HANDLER = (0x87eb24, 0x88019c)
IGR_SKIN = (0x87e464, 0x87eb24)
TROJAN_LOADER = (0x880a24, 0x881de8)
PATCH_LOADER = (0x881de8, 0x883270)          # up to the CHEATS.TXT parser
MAIN_FUNCTION = (0x870b78, 0x87c218)         # last instruction 0x87c214
CODE_AREA = (0x870000, 0x915000)
BLOCK_SOURCE, BLOCK_RUNS_AT, BLOCK_SIZE = 0x983150, 0x232790, 0x738
WRAPPER_FILE_OFFSET, WRAPPER_SIZE = 0xaf680, 2484
WRAPPER_DEVICE, WRAPPER_DLAY = 0x588, 0x420

# The hook slot each TROJAN_n.BIN of the community corpus uses, by file
# number (gap audit section 12). Addresses only; no file content.
SLOTS = {0: 0x2327d8, 1: 0x2327e0, 2: 0x2327e8, 3: 0x2327f0, 4: 0x232d08,
         5: 0x232d10, 6: 0x232d18, 7: 0x2327d0, 8: 0x232d20, 9: 0x232d28}


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


# ---------------------------------------------------------------------------
# A parser for the part of YAML the workflow files use: block mappings and
# sequences, plain and quoted scalars, flow sequences, block scalars (| and >)
# and comments. Not a general YAML parser; PyYAML is not a CI dependency.

def _strip_comment(line):
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def _scalar(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    if text.startswith("[") and text.endswith("]"):
        return [_scalar(part) for part in text[1:-1].split(",") if part.strip()]
    return text


def _split_key(content):
    """('key', 'rest') for a mapping line, else None."""
    match = re.match(r"""^((?:"[^"]*"|'[^']*'|[^:'"\s][^:]*?))\s*:(?:\s+(.*))?$""", content)
    if not match:
        return None
    return _scalar(match.group(1)), (match.group(2) or "")


def parse_yaml(text):
    raw = text.replace("\t", "    ").splitlines()
    lines = []                                   # (indent, content, raw index)
    for index, line in enumerate(raw):
        content = _strip_comment(line)
        if content.strip():
            lines.append((len(content) - len(content.lstrip(" ")), content.strip(), index))

    def block_scalar(pos, indent, style):
        start = lines[pos - 1][2] + 1 if pos > 0 else 0
        body, end = [], pos
        while end < len(lines) and lines[end][0] > indent:
            end += 1
        stop = lines[end][2] if end < len(lines) else len(raw)
        for line in raw[start:stop]:
            if line.strip():
                body.append(line)
        if body:
            cut = min(len(b) - len(b.lstrip(" ")) for b in body)
            body = [b[cut:] for b in body]
        joined = "\n".join(body) if style.startswith("|") else " ".join(b.strip() for b in body)
        return joined, end

    def node(pos, indent):
        if lines[pos][1] == "-" or lines[pos][1].startswith("- "):
            return sequence(pos, indent)
        return mapping(pos, indent)

    def value_after_key(pos, indent, rest):
        if rest[:1] in ("|", ">"):
            return block_scalar(pos + 1, indent, rest)
        if rest:
            return _scalar(rest), pos + 1
        if pos + 1 < len(lines):
            nxt_indent, nxt = lines[pos + 1][0], lines[pos + 1][1]
            if nxt_indent > indent:
                return node(pos + 1, nxt_indent)
            if nxt_indent == indent and (nxt == "-" or nxt.startswith("- ")):
                return sequence(pos + 1, indent)
        return None, pos + 1

    def mapping(pos, indent, first=None):
        result = {}
        while pos < len(lines):
            line_indent, content = (indent, first) if first is not None else lines[pos][:2]
            first = None
            if line_indent != indent or content == "-" or content.startswith("- "):
                break
            pair = _split_key(content)
            if pair is None:
                break
            key, rest = pair
            result[key], pos = value_after_key(pos, indent, rest)
        return result, pos

    def sequence(pos, indent):
        result = []
        while pos < len(lines) and lines[pos][0] == indent and \
                (lines[pos][1] == "-" or lines[pos][1].startswith("- ")):
            content = lines[pos][1][1:].strip()
            if not content:
                if pos + 1 < len(lines) and lines[pos + 1][0] > indent:
                    item, pos = node(pos + 1, lines[pos + 1][0])
                else:
                    item, pos = None, pos + 1
            elif _split_key(content) is not None:
                after_dash = lines[pos][1][1:]
                inner = indent + 1 + len(after_dash) - len(after_dash.lstrip(" "))
                item, pos = mapping(pos, inner, first=content)
            else:
                item, pos = _scalar(content), pos + 1
            result.append(item)
        return result, pos

    if not lines:
        return {}
    tree, _pos = node(0, lines[0][0])
    return tree


_RUNS = re.compile(r"^(?:python3?|py)(?:\s+-[A-Za-z]+)*\s+(?:\./)?tools/(test_\w+\.py)(?:\s|$)")


def _condition_runs(value):
    if value is None:
        return True
    text = str(value).strip()
    match = re.fullmatch(r"\$\{\{\s*(.*?)\s*\}\}", text)
    if match:
        text = match.group(1)
    return text in ("always()", "success()", "true")


def _not_continue_on_error(entry):
    return str(entry.get("continue-on-error", "false")).strip().lower() == "false"


def _triggers(tree):
    on = tree.get("on", tree.get("true"))
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return set(on)
    if isinstance(on, dict):
        return set(on)
    return set()


def steps_that_run(text):
    """{(job, test file name)} for steps that start a test on push or pull request.

    A test file counts when an uncommented line of a step's `run:` begins a
    command `python tools/<file>` (or `python3`, `py`), the step and its job
    have no `if:` other than always(), success() or true and no
    continue-on-error, the command is not followed by `||` on its line, and
    the workflow runs on push or pull_request.
    """
    tree = parse_yaml(text)
    if not isinstance(tree, dict) or not ({"push", "pull_request"} & _triggers(tree)):
        return set()
    found = set()
    jobs = tree.get("jobs") or {}
    for job_name, job in jobs.items():
        if not isinstance(job, dict) or not _condition_runs(job.get("if")) or not _not_continue_on_error(job):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict) or not _condition_runs(step.get("if")) or not _not_continue_on_error(step):
                continue
            run = step.get("run")
            if not isinstance(run, str):
                continue
            for line in run.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "||" in line:
                    continue
                for segment in re.split(r"&&|;", line):
                    match = _RUNS.match(segment.strip())
                    if match:
                        found.add((job_name, match.group(1)))
    return found


def workflow_coverage():
    """test file name -> set of (workflow file name, job) that run it."""
    runs = {p.name: set() for p in sorted(TOOLS.glob("test_*.py"))}
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        for job, name in steps_that_run(workflow.read_text(encoding="utf-8")):
            if name in runs:
                runs[name].add((workflow.name, job))
    return runs


def documented_coverage():
    text = CONTINUATION.read_text(encoding="utf-8")
    match = re.search(r"<!-- ci-coverage:begin -->(.*?)<!-- ci-coverage:end -->", text, re.S)
    if not match:
        return None
    nowhere, elsewhere, rest_in = set(), {}, None
    for line in match.group(1).splitlines():
        line = line.strip()
        names = set(re.findall(r"`(test_\w+\.py)`", line))
        if line.startswith("- Run by no workflow:"):
            nowhere |= names
        elif line.startswith("- Run by `"):
            workflow = re.match(r"- Run by `([\w.-]+\.yml)`, not by `build\.yml`:", line)
            if workflow:
                elsewhere.setdefault(workflow.group(1), set()).update(names)
        else:
            rest = re.match(r"- Every other `tools/test_\*\.py` file is a step of the `([\w-]+)` job in `([\w.-]+\.yml)`\.",
                            line)
            if rest:
                rest_in = (rest.group(2), rest.group(1))
    return nowhere, elsewhere, rest_in


SYNTHETIC = """\
name: t
on:
  push:
  pull_request:
jobs:
  host-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: a
        run: python tools/test_a.py
      - name: b {variant}
"""


class Native(unittest.TestCase):
    def test_ci_coverage_list_matches_the_workflows(self):
        documented = documented_coverage()
        self.assertIsNotNone(documented, "docs/CLOUD_CONTINUATION.md lost its ci-coverage block")
        nowhere, elsewhere, rest_in = documented
        self.assertEqual(rest_in, ("build.yml", "host-tests"), "the ci-coverage block lost its closing statement")
        runs = workflow_coverage()
        self.assertGreaterEqual(len(runs), 32)
        self.assertEqual(nowhere, {name for name, where in runs.items() if not where},
                         "test files run by no workflow differ from the documented list")
        actual_elsewhere, rest = {}, set()
        for name, where in runs.items():
            if rest_in in where:
                rest.add(name)
            elif where:
                for workflow, _job in where:
                    actual_elsewhere.setdefault(workflow, set()).add(name)
        self.assertEqual(elsewhere, actual_elsewhere,
                         "test files run only outside build.yml's host-tests job differ from the documented list")
        listed_elsewhere = set().union(*elsewhere.values()) if elsewhere else set()
        self.assertEqual(rest, set(runs) - nowhere - listed_elsewhere,
                         "a file the block counts as a host-tests step is not one")
        self.assertIn(rest_in, runs[Path(__file__).name], "this file must be a step of host-tests")

    def test_coverage_parser_reports_a_wrong_list(self):
        # The comparison above must be able to fail: a file the workflows run
        # must not be accepted in the "no workflow" set, and the reverse.
        runs = workflow_coverage()
        unrun = {name for name, where in runs.items() if not where}
        self.assertNotIn("test_launch_args.py", unrun)
        self.assertEqual(runs["test_launch_args.py"], {("launch-args.yml", "launch-args")})
        self.assertIn("test_pops_builtin_db.py", unrun)

    def test_step_parser(self):
        def ran(variant, base=SYNTHETIC):
            return {name for _job, name in steps_that_run(base.format(variant=variant))}
        self.assertEqual(ran("\n        run: python tools/test_b.py"), {"test_a.py", "test_b.py"})
        self.assertEqual(ran("\n        run: python3 -u tools/test_b.py --x"), {"test_a.py", "test_b.py"})
        self.assertEqual(ran("\n        run: |\n          set -e\n          python tools/test_b.py\n"),
                         {"test_a.py", "test_b.py"})
        self.assertEqual(ran("\n        run: cd . && python tools/test_b.py"), {"test_a.py", "test_b.py"})
        # A commented-out run line or step.
        self.assertEqual(ran("\n        # run: python tools/test_b.py"), {"test_a.py"})
        self.assertEqual(ran("\n#      - run: python tools/test_c.py"), {"test_a.py"})
        self.assertEqual(ran("\n        run: |\n          # python tools/test_b.py\n          true\n"), {"test_a.py"})
        # Conditions.
        self.assertEqual(ran("\n        if: false\n        run: python tools/test_b.py"), {"test_a.py"})
        self.assertEqual(ran("\n        if: ${{ false }}\n        run: python tools/test_b.py"), {"test_a.py"})
        self.assertEqual(ran("\n        if: github.event_name == 'push'\n        run: python tools/test_b.py"),
                         {"test_a.py"})
        self.assertEqual(ran("\n        if: always()\n        run: python tools/test_b.py"), {"test_a.py", "test_b.py"})
        self.assertEqual(ran("\n        continue-on-error: true\n        run: python tools/test_b.py"), {"test_a.py"})
        self.assertEqual(ran("\n        run: python tools/test_b.py || true"), {"test_a.py"})
        # A mention that does not run the file.
        self.assertEqual(ran("\n        run: echo \"python tools/test_b.py\""), {"test_a.py"})
        self.assertEqual(ran("\n        run: ls tools/test_b.py"), {"test_a.py"})
        # A job-level condition, and a workflow nobody pushes to.
        job_if = SYNTHETIC.replace("    runs-on: ubuntu-latest", "    if: false\n    runs-on: ubuntu-latest")
        self.assertEqual(ran("", job_if), set())
        manual = SYNTHETIC.replace("on:\n  push:\n  pull_request:\n", "on:\n  workflow_dispatch:\n")
        self.assertEqual(ran("", manual), set())
        flow = SYNTHETIC.replace("on:\n  push:\n  pull_request:\n", "on: [push, pull_request]\n")
        self.assertEqual(ran("", flow), {"test_a.py"})
        self.assertEqual(ran("", SYNTHETIC.replace("on:\n  push:\n  pull_request:\n", "on: push\n")), {"test_a.py"})

    def test_usbdelay_handler_address_is_cited_one_way(self):
        cited = usbdelay_handler_citations()
        self.assertGreaterEqual(len(cited), 2, "expected the audit and the inventory to cite it")
        self.assertEqual(len({address for _name, address in cited}), 1, cited)

    def test_cited_spot_checks_are_defined(self):
        text = AUDIT.read_text(encoding="utf-8")
        defined = [int(n) for n in re.findall(r"^\| S(\d+) \|", text, re.M)]
        self.assertEqual(sorted(defined), list(range(1, max(defined) + 1)), "spot-check rows are not contiguous")
        self.assertEqual(len(defined), len(set(defined)), "a spot-check number is defined twice")
        cited = {int(n) for n in re.findall(r"\bS(\d+)\b", text)}
        self.assertFalse(cited - set(defined), "cited but never defined: %s" % sorted(cited - set(defined)))

    def test_no_document_keeps_a_withdrawn_statement(self):
        withdrawn = ("Every banner `printf` is skipped",
                     "the fifteen call slots",
                     "The worktree `REPOP.worktrees/pr23` is at that commit",
                     "Use the worktree `REPOP.worktrees/pr23`",
                     "no outcome is fatal; the function returns 1",
                     "delays inside its USB/SMB file driver on first use",
                     "27 files, all exited 0 in both passes",
                     "BIOS handler: 14 call sites, 2 without the test")
        for path in documents():
            text = flat(path)
            for phrase in withdrawn:
                self.assertFalse(phrase in text, "%s keeps the withdrawn phrase %r" % (path.name, phrase))


ELF_SET = bool(os.environ.get("POPSTARTER_TEST_ELF"))
IMAGE = None
IMAGE_ERROR = None
if ELF_SET:
    try:
        import capstone  # noqa: F401
        import popstarter_r13_commands as COMMANDS
        import trace_original_pops_io as TRACE
        IMAGE = bytes(TRACE.decode_main(Path(os.environ["POPSTARTER_TEST_ELF"]).read_bytes()))
    except (Exception, SystemExit) as error:          # reported by Original.setUpClass
        IMAGE_ERROR = "%s: %s" % (type(error).__name__, error)
HAVE_UNICORN = False
if IMAGE is not None:
    try:
        import unicorn  # noqa: F401
        HAVE_UNICORN = True
    except Exception:
        pass


def word(address):
    return struct.unpack_from("<I", IMAGE, address - BASE)[0]


def jal(target):
    return 0x0c000000 | ((target >> 2) & 0x03ffffff)


def gp_word(op, reg, offset):
    """lw/sw reg,offset(gp) for op 0x23/0x2b."""
    return (op << 26) | (28 << 21) | (reg << 16) | (offset & 0xffff)


LI_V0_666 = 0x2402fd66
LI_V0_1 = 0x24020001


def c_string(address):
    start = address - BASE
    return IMAGE[start:IMAGE.index(b"\0", start)].decode("latin-1")


def print_format(site):
    """The format string of a print call: `addiu a0,gp,imm` just before it or in its delay slot."""
    for address in (site - 4, site + 4):
        value = word(address)
        if value >> 16 == 0x2784:
            imm = value & 0xffff
            return c_string(GP + (imm - 0x10000 if imm & 0x8000 else imm))
    return None


def print_call_census(low, high):
    """(call sites, those with no quiet-flag test before them) in [low, high).

    A site counts as tested when, in the 12 instructions before it, a
    `beq v1,v0` jumps past the call and `lw v1,0x38b0(gp)` stands one or two
    instructions before that branch. A pattern, not a flow analysis.
    """
    call = jal(PRINT)
    quiet = gp_word(0x23, 3, 0x38b0)
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


def census_phrase(label, low, high, formats=False):
    sites, untested = print_call_census(low, high)
    phrase = "%s: %s, %s without" % (label, "{:,}".format(len(sites)), "{:,}".format(len(untested)))
    if 0 < len(untested) <= 3:
        if formats:
            parts = ["`%#x`, format `%s`" % (s, print_format(s).replace("\n", "\\n")) for s in untested]
            phrase += " (%s)" % "; ".join(parts)
        else:
            phrase += " (%s)" % ", ".join("`%#x`" % s for s in untested)
    return phrase


def ticks(addresses):
    return ", ".join("`%#x`" % a for a in addresses)


@unittest.skipUnless(ELF_SET, "POPSTARTER_TEST_ELF not set")
class Original(unittest.TestCase):
    """What the audit and the inventory state, against the original's own bytes."""

    @classmethod
    def setUpClass(cls):
        if IMAGE is None:
            raise AssertionError("POPSTARTER_TEST_ELF is set but the image could not be used (%s)" % IMAGE_ERROR)
        cls.audit = flat(AUDIT)
        cls.inventory = flat(INVENTORY)

    def test_usbdelay_handler_address(self):
        chains = [address for address, text in COMMANDS.command_chains(IMAGE)
                  if text.startswith("$USBDELAY_")]
        self.assertEqual(chains, [0x89dbe0])
        self.assertEqual(word(0x89dbe4), 0x24020024)       # li v0,'$': the compare one word on
        self.assertIn("`tools/popstarter_r13_commands.py` prints `%#x`" % chains[0], self.audit)
        self.assertIn("the compare with `$` (`li v0,0x24`) is the next instruction, `0x89dbe4`", self.audit)
        for name, address in usbdelay_handler_citations():
            self.assertEqual(address, chains[0], name)

    def test_print_call_census_phrases(self):
        # S21, one whole phrase per range: count, number without the test
        # and, for one to three sites, the sites themselves.
        self.assertEqual(MAIN_FUNCTION[1], 0x87c218)
        self.assertEqual(word(MAIN_FUNCTION[1] - 8), 0x03e00008)           # jr ra; delay slot 0x87c214
        self.assertEqual(word(MAIN_FUNCTION[1]) >> 16, 0x27bd)             # the next function's frame
        frame = 0x10000 - (word(MAIN_FUNCTION[0]) & 0xffff)                 # addiu sp,sp,-frame
        self.assertEqual(word(MAIN_FUNCTION[0]) >> 16, 0x27bd)
        self.assertIn("The original's `main` is `%#x..%#x` (frame `%#x`;"
                      % (MAIN_FUNCTION[0], MAIN_FUNCTION[1] - 4, frame), self.audit)
        phrases = [census_phrase("BIOS handler", *BIOS_HANDLER, formats=True),
                   census_phrase("OSD handler", *OSD_HANDLER),
                   census_phrase("IGR skin function", *IGR_SKIN),
                   census_phrase("TROJAN loader", *TROJAN_LOADER),
                   census_phrase("`main` (`%#x..%#x`)" % (MAIN_FUNCTION[0], MAIN_FUNCTION[1] - 4), *MAIN_FUNCTION),
                   census_phrase("Whole code area `%#x..%#x`" % CODE_AREA, *CODE_AREA)]
        self.assertEqual(phrases[0], "BIOS handler: 14, 2 without (`0x8805b4`, format `DONE\\n`; "
                                     "`0x880984`, format `\\n`)")
        for phrase in phrases:
            self.assertIn(phrase, self.audit)
        # The gp+0x38b0 row.
        sites, untested = print_call_census(*CODE_AREA)
        bios = print_call_census(*BIOS_HANDLER)[1]
        row = ("by the pattern scan of S21, {:,} of the {:,} call sites stand behind this test and {:,} do not. "
               "Two of the {:,} are in the BIOS handler (`{}` at `{:#x}`, `{}` at `{:#x}`)").format(
            len(sites) - len(untested), len(sites), len(untested), len(untested),
            print_format(bios[0]).replace("\n", "\\n"), bios[0], print_format(bios[1]).replace("\n", "\\n"), bios[1])
        self.assertIn(row, self.audit)
        self.assertIn("Most print calls are skipped while it is 1, not all", self.audit)

    def test_pops_folder_check(self):
        # FUN_008d8958 (S32): returns 0 when gp+0x38dc or gp+0x3868 is 1 on
        # entry; otherwise sets gp+0x3868 first, then returns 1, or -666
        # with gp+0x38dc and gp+0x3460 set.
        low, high = FOLDER_CHECK
        self.assertEqual(word(high - 8), 0x03e00008)
        self.assertEqual([word(a) for a in (0x8d8968, 0x8d8978, 0x8d8990, 0x8d8994)],
                         [gp_word(0x23, 3, 0x38dc), gp_word(0x23, 3, 0x3868), 0x1000005a, 0xafc00030])
        self.assertEqual([word(a) for a in (0x8d8998, 0x8d899c)], [LI_V0_1, gp_word(0x2b, 2, 0x3868)])
        stores = {}
        for address in range(low, high, 4):
            value = word(address)
            if value >> 21 == (0x2b << 5) | 28:
                stores.setdefault(value & 0xffff, []).append(address)
        self.assertEqual(stores, {0x3868: [0x8d899c], 0x38dc: [0x8d8a20, 0x8d8ac0], 0x3460: [0x8d8a28, 0x8d8ac8]})
        self.assertEqual([a for a in range(low, high, 4) if word(a) == LI_V0_666], [0x8d8a2c, 0x8d8acc])
        callees = [word(a) for a in range(low, high, 4) if word(a) >> 26 == 3 and word(a) != jal(PRINT)]
        self.assertEqual(callees, [jal(0x8d7e78), jal(0x91bf80), jal(0x91be68)])
        self.assertIn("it returns 0 only when `gp+0x38dc` or `gp+0x3868` is 1 on entry; otherwise it sets "
                      "`gp+0x3868 = 1` first and returns 1, or -666 with `gp+0x38dc = 1` and `gp+0x3460 = 1`",
                      self.audit)
        # Its seven callers, in address order, as S32 and section 3a list them.
        callers = [a for a in range(*CODE_AREA, 4) if word(a) == jal(low)]
        self.assertEqual(callers, [0x873f9c, 0x87e49c, 0x87ec38, 0x880348, 0x880aac, 0x881e70, 0x8d4fac])
        self.assertIn("Callers: `0x873f9c` (`main`), `0x87e49c` (IGR skin), `0x87ec38` (OSD), `0x880348` (BIOS), "
                      "`0x880aac` (TROJAN), `0x881e70` (PATCH), `0x8d4fac` (the `VMCDIR.TXT` reader)", self.audit)
        self.assertIn("Seven call sites of `FUN_008d8958`: %s" % ", ".join(
            "`%#x` (%s)" % (a, n) for a, n in zip(callers, ("`main`", "IGR", "OSD", "BIOS", "TROJAN", "PATCH",
                                                          "VMCDIR reader"))), self.audit)
        # main's own check, skipped on gp+0x3888 != 0, and its other store.
        self.assertEqual([word(a) for a in (0x873f90, 0x873f94)], [gp_word(0x23, 2, 0x3888), 0x14400044])
        self.assertEqual(word(0x87425c), gp_word(0x2b, 2, 0x3868))
        self.assertEqual([a for a in range(*MAIN_FUNCTION, 4) if word(a) == gp_word(0x2b, 2, 0x3868)], [0x87425c])
        self.assertIn("(`jal 0x8d8958` at `0x873f9c`, skipped when `gp+0x3888 != 0`)", self.audit)
        self.assertIn("by `main` at `0x87425c`", self.audit)

    def test_minus_666_stores_of_the_loaders(self):
        loaders = (("IGR", IGR_SKIN), ("OSD", OSD_HANDLER), ("BIOS", BIOS_HANDLER),
                   ("TROJAN", TROJAN_LOADER), ("PATCH", PATCH_LOADER))
        parts = []
        for name, (low, high) in loaders:
            sites = [a for a in range(low, high, 4) if word(a) == LI_V0_666]
            parts.append("%s %s" % (name, ticks(sites)))
            # Each loader calls the folder check once and stores -666 after it.
            calls = [a for a in range(low, high, 4) if word(a) == jal(FOLDER_CHECK[0])]
            self.assertEqual(len(calls), 1, name)
            self.assertLess(calls[0], sites[0], name)
        self.assertIn("`-666` stores: " + "; ".join(parts), self.audit)

    def test_bios_handler_exits(self):
        # The POPS folder exit (section 4).
        self.assertEqual([word(a) for a in (0x880338, 0x880348, 0x880360, 0x880368, 0x880374, 0x880378)],
                         [gp_word(0x23, 3, 0x3868), jal(FOLDER_CHECK[0]), 0x8fc30000, 0x10620006,
                          gp_word(0x2b, 2, 0x38dc), LI_V0_666])
        self.assertEqual(0x880368 + 4 + 4 * 6, 0x880384)                   # the scope test skips the exit
        self.assertIn("the POPS folder exit (`0x880338..0x880380`). The handler reads `gp+0x3868` and, if it is "
                      "not 1, calls the POPS folder check `FUN_008d8958` (`jal` at `0x880348`). A result of 1 goes "
                      "on. Otherwise all games returns -666 (`sw` of 1 to `gp+0x38dc` at `0x880374`, `li v0,-666` "
                      "at `0x880378`) and the game scope goes on (the scope test at `0x880360..0x880368`)",
                      self.audit)
        # The game-folder exit after the once-flag.
        self.assertEqual(word(0x8804ec) & 0xffe0ffff, gp_word(0x23, 0, 0x38e0))   # lw ?,0x38e0(gp)
        self.assertEqual(word(0x880500) & 0xffe0ffff, gp_word(0x2b, 0, 0x38e0))   # sw ?,0x38e0(gp)
        self.assertEqual([word(a) for a in (0x880538, 0x880554, 0x880558, 0x880570, 0x8805a0, 0x8805a4)],
                         [jal(0x8d7e78), gp_word(0x2b, 2, 0x3460), LI_V0_666,
                          jal(0x91bf80), gp_word(0x2b, 2, 0x3460), LI_V0_666])
        self.assertIn("A missing folder sets `gp+0x3460 = 1` and returns -666 with nothing opened (`pfs1:` call at "
                      "`0x880538`, store at `0x880554`, `-666` at `0x880558`; `mass:` call at `0x880570`, store at "
                      "`0x8805a0`, `-666` at `0x8805a4`)", self.audit)
        self.assertIn("the handler reads the once-flag `gp+0x38e0` (`0x8804ec`)", self.audit)
        # The gates come first: each returns 0 before either exit and before
        # the once-flag is read, so only a call that passes them sets it.
        low, high = 0x8801b4, 0x880338
        gates, scope, returns = [], "any scope", 0
        for address in range(low, high, 4):
            value = word(address)
            if value == 0x8fc30000:                                     # lw v1,0(fp): the scope
                # beq v1,v0 skips the gate for scope 1 (game), bne for the others.
                scope = {0x1062: "all games", 0x1462: "game"}[word(address + 8) >> 16]
            elif value >> 16 == 0x8f83 and value & 0xffff != 0x38b0:    # lw v1,off(gp); 0x38b0 is the print switch
                gates.append((scope, value & 0xffff))
            elif value >> 16 == 0x1000:                                 # b: the shared return, v0 = 0xc0(fp)
                target = address + 4 + ((value & 0xffff) ^ 0x8000) * 4 - 0x8000 * 4
                if target == 0x880a0c:
                    self.assertEqual(word(address + 4), 0xafc000c0)    # sw zero,0xc0(fp) in the delay slot
                    returns += 1
        self.assertEqual([g for _s, g in gates], [0x38dc, 0x343c, 0x344c, 0x3878, 0x3430, 0x344c, 0x3460])
        self.assertEqual(returns, 6)        # one per gate test; the two 0x343c/0x344c loads share one
        loads = [a for a in range(*BIOS_HANDLER, 4) if word(a) & 0xffe0ffff == gp_word(0x23, 0, 0x38e0)]
        self.assertEqual(loads, [0x8804ec])
        phrase, last = [], None
        for scope, offset in gates:
            item = "`gp+%#x`" % offset
            if scope != last:
                phrase.append("%s %s" % (scope, item))
            else:
                phrase[-1] += ", " + item
            last = scope
        self.assertIn("Gates inside the handler, in this order, each returning 0 (`%#x..%#x`, before both exits): %s."
                      % (low, high - 4, "; ".join(phrase)), self.audit)
        self.assertIn("So a game-scope call that gets past the gates of the next row always leaves `gp+0x38e0 = 1`",
                      self.audit)

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
                         [gp_word(0x23, 3, 0x38dc), LI_V0_1, 0x14620003, 0xafc00008])
        # Then gp+0x3868, the folder check, and the -666 path that sets the abort flag.
        self.assertEqual([word(a) for a in (0x87e48c, 0x87e49c, 0x87e4b8, 0x87e4bc)],
                         [gp_word(0x23, 3, 0x3868), jal(FOLDER_CHECK[0]), gp_word(0x2b, 2, 0x38dc), LI_V0_666])
        self.assertIn("the function returns 0 at once and opens nothing (`0x87e474..0x87e488`)", self.audit)
        self.assertIn("it first runs the POPS folder check `FUN_008d8958` (`jal` at `0x87e49c`); a result other "
                      "than 1 sets the abort flag `gp+0x38dc = 1` and returns -666 (`0x87e4bc`)", self.audit)
        self.assertIn("At that call the check returns only 1 or -666", self.audit)
        self.assertIn("on a missing folder `gp+0x3460 = 1` (which skips every later current-game loader) as well "
                      "as `gp+0x38dc = 1`", self.audit)
        self.assertNotIn("no outcome is fatal; the function returns 1", self.audit)
        # The inventory's row.
        self.assertIn("it returns 0 without opening anything when the abort flag `gp+0x38dc` is set, and -666 "
                      "with that flag set after a failed POPS folder check, which also sets `gp+0x3460`",
                      self.inventory)

    def test_igr_skin_gates_sit_in_main(self):
        slot_refs = [(a, word(a) >> 26) for a in range(*MAIN_FUNCTION, 4)
                     if (word(a) >> 21) & 31 == 30 and word(a) & 0xffff == 0x1108
                     and word(a) >> 26 in (0x23, 0x2b)]
        self.assertEqual(slot_refs, [(0x870ce8, 0x2b), (0x8712ec, 0x2b), (0x876a90, 0x23)])
        self.assertEqual(word(0x8712d0), 0x3484002d)        # ori a0,a0,0x2d: preset 0x10002d
        self.assertEqual(word(0x876a84), gp_word(0x23, 2, 0x38dc))   # before the call
        self.assertEqual(word(0x876b18), jal(IGR_SKIN[0]))
        self.assertEqual(word(0x876b1c), 0)                 # delay slot: nothing reads v0
        self.assertEqual(word(0x876b20), gp_word(0x23, 2, 0x38dc))   # v0 overwritten at once
        self.assertIn("preset `0x10002d` equal to 1 sets the frame word `0x1108(fp)` (its only writers are "
                      "`0x870ce8`, zero, and `0x8712ec`). The call at `0x876b18` is skipped when `gp+0x38dc` is "
                      "nonzero (`0x876a84`) or that word is not 1 (`0x876a90`, its only reader). After the call "
                      "`main` reads `gp+0x38dc` (`0x876b20`), not the return value", self.audit)

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
        named = [int(x, 16) for x in re.findall(r"`(0x[0-9a-f]{6})`", statement)]
        # 0x8d4f84 is named there as the start of the VMCDIR.TXT reader, and
        # 0x8d5cf8..0x8d6b70 as a function range, not as sites.
        self.assertEqual([a for a in named if a not in (0x8d4f84, 0x8d5cf8, 0x8d6b70)], [0x870c58] + loads)

    def test_always_live_block_slot_pairs(self):
        block = IMAGE[BLOCK_SOURCE - BASE:BLOCK_SOURCE - BASE + BLOCK_SIZE]
        pairs = [BLOCK_RUNS_AT + off for off in range(0, BLOCK_SIZE - 4, 4)
                 if struct.unpack_from("<II", block, off) == (0x10000001, 0)]
        first = [a for a in pairs if a < 0x232800]
        second = [a for a in pairs if a >= 0x232800]
        self.assertEqual(first, list(range(0x2327d0, 0x2327f8, 8)))
        self.assertEqual(second, list(range(0x232d08, 0x232ec0, 8)))
        self.assertEqual(second[-1] + 16, BLOCK_RUNS_AT + BLOCK_SIZE)
        self.assertIn("60 pairs: 5 at `0x2327d0..0x2327f0` and 55 at `0x232d08..0x232eb8`, which is the end of "
                      "the block", self.audit)
        self.assertIn("The block holds %d such pairs (%d at `0x2327d0..0x2327f0`, %d at `0x232d08..0x232eb8`)"
                      % (len(pairs), len(first), len(second)), self.audit)
        # Section 12's slot list, entry by entry, against SLOTS.
        self.assertTrue(set(SLOTS.values()) <= set(pairs), "a slot is not an empty pair in the block")
        self.assertIn("Each hooks one of ten fixed call slots, one per file number: %s." % ", ".join(
            "%d `%#x`" % (n, SLOTS[n]) for n in range(10)), self.audit)

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
        # S28, section 9 and the inventory, in the words they use.
        self.assertIn("`thbase` 33 with argument 5,000,000", self.audit)
        self.assertIn("argument n x 1,000,000, once, before the first backend open, and none in six later "
                      "callbacks (10 of 10)", self.audit)
        self.assertIn("Read, seek and close called before any open make no `thbase` call; the first open after "
                      "them does (1 of 1)", self.audit)
        self.assertIn("It is called from device-table entry 3 only, once, on that entry's first call, before the "
                      "wrapper's own backend open, with n x 1,000,000 as its argument (5,000,000 if the word still "
                      "reads `DLAY`). Later calls of entry 3 and the read, seek and close entries do not call it",
                      self.audit)
        self.assertIn("the wrapper calls `thbase` import 33 once, with n x 1,000,000 (5,000,000 if unpatched), "
                      "before its first backend open and in none of the later callbacks run", self.inventory)


CORPUS = os.environ.get("POPS_TROJAN_CORPUS")


@unittest.skipUnless(CORPUS, "POPS_TROJAN_CORPUS not set")
class Corpus(unittest.TestCase):
    """S15 and section 12 against the corpus headers. Counts only; nothing is kept."""

    def test_counts_and_hooks(self):
        root = Path(CORPUS)
        self.assertTrue(root.is_dir(), "POPS_TROJAN_CORPUS is set but is not a folder: %s" % CORPUS)
        counts = {"TROJAN": 0, "PATCH": 0}
        distinct = {"TROJAN": set(), "PATCH": set()}
        hooks = {}
        for path in root.rglob("*"):
            match = re.fullmatch(r"(TROJAN|PATCH)_(\d)\.BIN", path.name, re.I)
            if not match or not path.is_file():
                continue
            kind, number = match.group(1).upper(), int(match.group(2))
            data = path.read_bytes()
            counts[kind] += 1
            distinct[kind].add(hashlib.sha256(data).digest())
            if kind == "TROJAN":
                self.assertGreaterEqual(len(data), 28, path.name)
                hooks.setdefault(number, set()).add(struct.unpack_from("<I", data, 24)[0])
        audit = flat(AUDIT)
        self.assertIn("{:,} TROJAN files, {:,} unique; {:,} PATCH files, {:,} unique".format(
            counts["TROJAN"], len(distinct["TROJAN"]), counts["PATCH"], len(distinct["PATCH"])), audit)
        self.assertIn("{:,} TROJAN files, {:,} unique by content; {:,} PATCH files, {:,} unique".format(
            counts["TROJAN"], len(distinct["TROJAN"]), counts["PATCH"], len(distinct["PATCH"])), audit)
        self.assertEqual(hooks, {n: {SLOTS[n]} for n in range(10)})


if __name__ == "__main__":
    unittest.main()
