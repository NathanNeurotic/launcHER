# docs-3: answers to review 2 (docs3-review2.md)

Branch `pr23/docs-3`, worktree <workspace>/launcHER.worktrees/docs-3.
Base of this round 39b9977. New commits, pushed (no force):

- b18a698 docs(pops): IGR order note limited to the skin's place, SMB not traced, correction dates, fatal-exit length words, 330 not refused
- ef5bcbf docs(pops): TROJAN user text matches the merged loader (367 of 509 loaded, skips logged)

Only Markdown and HTML changed. No C, header, CMake, workflow or test file,
so no container build was needed. Host only. NOT TESTED on a console.

## Findings

| # | Finding | Answer |
|---|---|---|
| 1 | IGR doc: "This is the original's order" under a table whose later rows are launcHER's order | Fixed. docs/POPSTARTER_IGR_SKIN.md now says the skin's place (after the built-in entry, before the user's files) is the original's. Inside and after `pops_stage_user_files` the rows give launcHER's order: the original loads both `BIOS.BIN` files before the commands, launcHER runs the commands first (link to POPSTARTER_USER_BIOS.md, difference 1, checked: its item 1 "The commands run before the files"). |
| 2 | README / pops-setup.html: "until the skin was merged" | Fixed: "until after the skin was merged; corrected on `pr23/docs-3`". Checked: `git show 173d5de:README.md` and `origin/pr23/integ:README.md` both still have the "not implemented" line, and both setup pages still have "no effect". |
| 3 | User docs state "same place only when the `.VCD` is in `mass:/POPS/`" while the IGR doc leaves SB. open | Fixed in both files: "(for SMB launches, which device the original's `mass:` names was not traced)". Matches the IGR doc's SB. paragraph (line 142..151). |
| 4 | PHYSICAL_DISC.md fatal-exit list leaves out two stores | Fixed. My own capstone read of the decoded MAIN (`decode_main` from tools/trace_original_pops_io.py, script `<scratch>/docs3/fatal_exit.py`): 0x870a88 `lw a2,0x33ac(gp)` / `jal 0x9188b8`, 0x870aa0 `lw a2,0x33b0(gp)` / `jal 0x9188b8`, 0x870aac `sw zero,0x33ac(gp)`, 0x870ab0 `sw zero,0x33b0(gp)`, 0x870ab4..0x870ac8 `0x9188b8(0x1ff000, 0, 0x303e60)`. The doc now says: two clears whose lengths are the words `gp+0x33ac` and `gp+0x33b0`, then both words cleared (0x870aac, 0x870ab0), then `0x9188b8(0x1ff000, 0, 0x303e60)`. Still marked "read from the code, not run". |
| 5 | Author report: "36 of 36" and "its own fresh TMP folder" | Agreed. A correction note was appended to docs3-author.md: 35 tracked files, 35 of 35 rc=0; one fresh folder per invocation in that round. This round's runner (`<scratch>/docs3/run_fix2.sh`) makes one fresh folder per test file. |
| 6 | bios-bin-fix-1.md note: "The other 330 launch" | Fixed: "The other 330 are not refused (`pops_stage_user_files` returns 0 on the host; no launch was run)". |

Also fixed, from the review's "not this track" list (stale user-facing text,
cheap): README.md and docs/pops-setup.html still said every community TROJAN
file is rejected and stops the launch. That was true before the TROJAN merge.
At this tree `pops_stage_fix_files` (launcher/src/handler_pops.c 464..481)
logs and `continue`s on `POPS_FIX_SKIP_INVALID`, `_OUTDATED` and `_UNHOSTED`,
and returns for `result < 0` ("Fix file rejected"). `pops_read_trojan`
returns -errno / -EIO on a failed payload read. The new text gives the
measured counts from `tools/test_pops_trojan_corpus.py`, run on this tree
with POPS_TROJAN_CORPUS: 509 files, 367 loaded, 142 not loaded (120 + 17 +
5), 509 of 509 applied by the original's loader; PATCH 10 of 10 applied.
It says some failures still stop the launch, and that what a loaded payload
does while the game runs was not run anywhere. It links
docs/POPSTARTER_TROJAN.md and adds a "corrected on `pr23/docs-3`" note.

Not done, as the task says: the BIOS review's major finding (built-in entry
+ `$UNDO_COMPATIBILITY_CODES`, 294 of 624 refused) is an owner decision.
`common/include/pops_modes_patches.h:50` still says "The size test
(0x8803d0)"; the right address is 0x88089c. That is a C header comment, so
it is left for a track that may change C.

## Tests (host only, one at a time, from the worktree root)

Runner: `<scratch>/docs3/run_fix2.sh`, one fresh TMP/TEMP/TMPDIR per file
under `<scratch>/tmp-fix2-<label>-<test>`. Logs `<scratch>/docs3/fix2-*.log`.

| Run | Files | Result |
|---|---|---|
| after commit b18a698's edits, without inputs | doc_claims, igr_skin, user_bios, physical_disc | 4 of 4 rc=0: OK (skipped=11), OK (skipped=21), OK (skipped=13, expected failures=1), OK (skipped=18) |
| same, with the three reference inputs | same 4 | 4 of 4 rc=0 (doc_claims OK, igr_skin OK; user_bios and physical_disc print their PASS lines last) |
| full suite, without inputs (what CI does), same tree | all 35 tracked `tools/test_*.py` | 35 of 35 rc=0 |
| after the TROJAN text, without inputs | doc_claims, trojan, trojan_corpus | 3 of 3 rc=0 |
| same, with inputs | same 3 | 3 of 3 rc=0; corpus counts as above |

The full suite was not re-run after the TROJAN text change. That change
touches README.md and pops-setup.html only, and test_pops_doc_claims.py
is the only test that reads either; it was run both ways after the change.

`<scratch>` = <scratch>.

## Checks

No AI attribution in the diff or the commit messages. No email address
written. No binary, byte table or hash. Not touched: EMBER, tags, releases,
codex/popstarter-replacement, docs/POPSTARTER_QUIRKS_TO_FIX_LATER.md,
docs/PR23_HANDOFF_2026-11-11.md. The historical reports keep their text;
only the appended correction note in bios-bin-fix-1.md was changed.
