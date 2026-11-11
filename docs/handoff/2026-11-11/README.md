# Reports kept for the November 11 handoff

Start with [../../PR23_HANDOFF_2026-11-11.md](../../PR23_HANDOFF_2026-11-11.md).

These files are the reports each piece of work left when its stage ended,
copied as written. They are working notes, not verified statements: an
author's report says what the author believes it measured, and a review says
what an independent reader found when checking it. Where a review and an
author's report disagree, the review is the later word unless a later
"answer" file says otherwise. Nothing in them was run on a console unless a
line says so.

Paths were shortened: `<scratch>` was a temporary folder that no longer
exists (scripts named there are gone unless they are in the two folders
below), `<workspace>` is the folder that held the checkouts, repository
files are given relative to the repository root.

| Piece | Files |
| --- | --- |
| Handoff defect (`ExecPS2` rewrites POPS code) | [static analysis](handoff-defect-static.md), [emulator runs](handoff-defect-emulator.md) |
| TROJAN_n.BIN | [design](trojan-design.md). No author's report and no review: the work on `pr23/trojan` was stopped first |
| CHEATS.TXT, `$USBDELAY_n`, VMCDIR.TXT | [author](cfg-text-author.md), [review 1](cfg-text-review-1.md) |
| User BIOS.BIN | [author](bios-bin-author.md), [review 1](bios-bin-review-1.md), [answer](bios-bin-fix-1.md) |
| IGR skin | [author](igr-skin-author.md), [review 1](igr-skin-review-1.md), [answer](igr-skin-fix-1.md) |
| Gap audit and status documents | [author](docs-author.md), [review 1](docs-review-1.md), [answer](docs-fix-1.md), [review 2, not answered](docs-review-2.md) |
| Physical PS1 disc, host part | [author](disc-author.md). Not reviewed |
| SMB config files | None: stopped before the author reported. See `docs/POPSTARTER_SMB_CONFIG.md` |
| Path table | None: stopped before the author reported |
| REPOP batch 26 | [author](repop-author.md), [review 1](repop-review-1.md), [answer](repop-fix-1.md) |

Two folders of scripts:

- [emulator-harness/](emulator-harness/REPORT.md): the scripts behind the
  PCSX2 runs and a report of what they showed. They need a private copy of
  the emulator, a BIOS and disk images; none of those is in the repository.
- [handoff-fix-scratch/](handoff-fix-scratch/runs.log): the build, run and
  comparison scripts of the unfinished handoff fix on `pr23/handoff`, and its
  run log. They refer to folders that no longer exist and are kept to show
  what was done, not to be run as they are.

Some reports quote text proposed for the PR description or for shared
documents ("doc updates"). That text was written for the state at the time
and was not applied.
