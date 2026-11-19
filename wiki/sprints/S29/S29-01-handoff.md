---
type: handoff
owner_agent: lead
status: needs-qa
sources: ["founder chat 2026-11-19 16:27 KST ('... I would like to flexibily choose the option where it assists the research. For methodology work, it will use \"ours\" and focus on the performance of the model. For a benchmark paper, there will be findings that needs to be found through experiment, so there will be coarse experiments which needs closer organization. ... Plan and update Lemmata')", "https://github.com/daisjuhyeong/temporal_dependency/blob/short-exp/LEMMATA_EXPECTED.md (commit 458d573; attached to the same message)", "../../decisions/ADR-009-study-kind-and-key-numbers.md", "../../decisions/ADR-007-project-map-two-phases.md", "../../decisions/ADR-008-top-down-evidence-spine.md", "S27-01-handoff.md", "S28-01-handoff.md"]
last_reviewed: 2026-11-19
---
# S29-01: method paper or benchmark study, key numbers, and a hub that says when it is behind

Asked by Juhyeong (chat, 2026-11-19): `temporal_dependency` is a benchmark paper and `mcd_extension` a methodology
paper; Lemmata should let him choose which way it assists. He attached `LEMMATA_EXPECTED.md`, the project's own list of
what Lemmata should find and what it is missing. Built from the chat session. Branch `s29-study-kind`, cut from
`s28-setup-board`. Nothing is merged to main. Decision record: [ADR-009](../../decisions/ADR-009-study-kind-and-key-numbers.md) (proposed).

## Reading of the request (decided by the lead; Juhyeong can change it)
- **One setting per project, two values**: *Method paper* and *Benchmark study*. The researcher sets it; until then a
  rule reads it (no paper and a protocol or findings report → benchmark).
- **"Coarse experiments which need closer organisation"** = one top-down path per hypothesis: its test, the experiments
  the map files under it, the numbers the report quotes for it, the runs that wrote those files, and what cannot be
  traced. That path is the Thesis page for one hypothesis, and the new Key numbers page for all of them.
- **`LEMMATA_EXPECTED.md` is the acceptance test.** Each item of its "Lemmata state" section was treated as a defect
  or a limit of Lemmata, listed below with what was done.

## What changed
- **The kind of study** (`engine/study.py`, new; `GET`/`POST /api/study`; MCP `study`).
  - Rules Y1-Y4: your choice, then the confirmed map, then "no paper and a protocol or report → benchmark", else method.
  - One line on Home, Thesis and Setup says the kind and who set it, with a selector.
- **Benchmark study: nothing is "ours".**
  - Map: `study: "benchmark"`, `roles` (which column names methods, datasets, a group, a condition, a seed),
    per experiment `row_column` and `where`. `method`, `base`, `goal`, `criteria` are dropped with a reason. A
    question can name a hypothesis by its label (`"claim": "H1"`).
  - Experiments: the summary is the field of what is compared (best, worst, median, count). No "ours is a guess".
  - Setup: methods are "compared"; a row is a method only when its column names methods. Tests, cases, sources and
    groups are rows. A long sheet shows 12 rows first; an experiment under a second claim is one line, not a second sheet.
  - Links: rule **L5**, the claim's own test decides. Shown as "test met", "test not met" (not in the error colour),
    "no verdict". Claims: rule **C10** for a map question with results and no test.
  - Review: "Have the tests decided the claims?" replaces "How does ours compare with the baselines?". Checklist:
    more than one run · every method on every dataset · a test fixed before the data · key numbers traced to a file ·
    confounds checked.
  - To-do: no "contradicts" task for a claim its test does not support.
- **Key numbers** (`engine/numbers.py`, new; `GET /api/numbers`, `GET /api/numbers/brief`, `POST /api/numbers`; MCP
  `key_numbers`, `propose_numbers`; page "Key numbers" in the sidebar and the footer).
  - By claim: what the report says (with its line), what the committed file holds now, the file, how the number is
    read, the last commit, the runs that wrote it. Status ok / mismatch / missing / gap / not compared.
  - Reads: one cell, count, count of, share, mean, median, min, max, sum, all, any, distinct; conditions with
    `== != < <= > >= in contains notnull isnull` and `or`; a key of a JSON object; `.csv`, `.tsv`, `.json`, gzipped too.
  - The agent proposes, rules check, the researcher confirms. The numbers of a hypothesis's own test are listed
    without a proposal.
  - "Open provenance gaps" at the bottom, by rule. To-do items for a proposal, a mismatch, a missing number, a gap.
  - The Thesis page shows a hypothesis's experiments and key numbers when it is opened; Review shows one strip.
- **Sync** (`hub/projects.py`): each sync is recorded in the project's `sync.json`. A failed fetch is named
  (`github_signin`, `github_scope`, `github_access`, `branch_not_found`) with the fix. While it fails, the pages carry
  a note, runs on unseen commits read "not pulled yet", and the footer says "Sync is failing".
- **Runs** (`engine/runs.py`): `kind` experiment or command; counts for both; `backfilled` and `sha_basis` kept. MCP
  `runs` lists experiments unless `commands=true`.
- **Map**: `planned: true` keeps an experiment whose files are not there yet as "waiting".
- **A mapped experiment reads a long table whole** (20,000 rows; it was 500, which cut `C_cells.csv` at 499 of 3,294).
- **MCP texts**: `alarms` and `findings` say what an empty answer rests on; `sync` says what failed; `project_status`
  shows the study and the sync state; `setup` and `project_map` speak of compared methods in a benchmark study.
- **FAQ**: three entries (no method of its own; where a report number comes from; "not in GitHub" while sync fails).

## `LEMMATA_EXPECTED.md`, item by item
| Item in "Lemmata state" | What it was | Now |
|---|---|---|
| Sync fails: "could not read Username" | The hub fetches with the owner's saved GitHub sign-in. git prints this when GitHub refuses that sign-in for the repository. The fix proposed in the file (SSH remote, `gh auth login`) cannot work: the hub's git allows only https and reads no user configuration. | The hub asks GitHub which of three causes it is and says so, with the fix (sign in again in Lemmata; allow private repositories). **Which cause it is on the Mac mini is not known from here.** |
| Every run shows as "not in github" | True only because the copy was behind. | "Not pulled yet (sync failing)", with a note on the pages and in the MCP tools. |
| Empty `alarms` or `findings` proves nothing | The tools did not say so for `findings`. | Both say what the empty answer rests on. |
| Nothing could be logged for Stage 0, gates 1-2, `analysis.py`, ... | No run record exists. | Not solved, and not solvable by Lemmata: listed per claim as "no logged run wrote these files; the commit is the only record". |
| The map assumes a method of its own; 109 "methods", 25 "ours" | Every label column was read as methods; one was guessed as "ours". | Benchmark study. On 458d573 without a map: 18 compared methods, 0 "ours" (it was 201 and 34 on the s28 engine). |
| Experiments dropped because the copy does not hold their files | ADR-007: a pattern that matches nothing is dropped. | `planned: true` keeps it as waiting. The real fix is a working sync. |
| The hook logs ad-hoc commands | Every Python command is a run. | Kept, and classed as a command; not counted or listed as an experiment. |
| Gap 7: backfilled runs carry the commit that first held the results | Not expressible. | `sha_basis: "results_commit"`; listed as an open gap per claim. |

## Checked
- **Tests**: `app/tests/test_study.py` (10, new: a small benchmark repo), `test_hub.test_sync_failure_is_named_and_recorded`
  (new). `test_map`, `test_mcp`, `test_runs` updated for the new map fields, tools and run counts. Full suite: 206 OK
  (2 skipped).
- **`temporal_dependency`, branch `short-exp` (458d573), on a local copy.** The problem, H1-H3 and H2b, a benchmark map
  and the key numbers were entered by the lead in the role of the researcher's LLM; **the Mac mini hub will show
  whatever is confirmed there.**
  - Stages: H1 finding, H2 and H3 not supported, H2b no verdict (as S27).
  - Map: `method` dropped with a reason; H1-H3 linked to the hypotheses by label; a planned step kept as waiting; an
    invented experiment dropped.
  - Step C: 18 methods × 61 datasets, 2 to 3 runs per cell, 3,254 runs in all (the rows marked ok in `C_cells.csv`).
  - Key numbers: the checks of `LEMMATA_EXPECTED.md` written as 84 entries. **75 agree with the file**, 9 are gaps
    (the 7 "derived" numbers no file stores, and its two known gaps: Gate 3 D3R, ARCUS clip). 0 mismatch. A number
    deliberately misquoted was reported as a mismatch; a wrong column and a wrong row were dropped.
  - The last commit Lemmata shows for a number's file is the one `LEMMATA_EXPECTED.md` lists, for all 65 numbers that
    could be paired by name.
  - With 11 runs logged as its notes describe them: 9 experiments, 2 commands; the runs appear under H1-H3; the gaps
    list names `tests.csv` as written by no logged run and the backfilled runs as lacking a start commit.
- **Browser** (Chrome, 1360, 760 and 420 px) on that project and on the sample method paper: Home, Thesis, Setup,
  Review, Key numbers, Trail, Claims, FAQ. No console errors, no sideways scroll of the page (long dataset names on a
  Setup sheet now wrap).
- **A method paper**: the existing tests on the sample and on the mapped fixture of `test_map` pass with three
  expectations updated (the map's field list, the tool list, the run counts); the documents gained fields, none was
  removed. Switching the sample to benchmark and back restores the same Setup counts (`test_study`).

## Screenshots
- [Home with the study line](screenshots/s29-home-study-line.png)
- [Thesis: H2 open, its experiments and key numbers](screenshots/s29-thesis-hypothesis-experiments-numbers.png)
- [Key numbers](screenshots/s29-key-numbers.png)
- [Review of a benchmark study](screenshots/s29-review-benchmark.png)
- [Setup: a compared method](screenshots/s29-setup-compared-method.png)
- [Setup of a method paper (unchanged, with the study line)](screenshots/s29-method-paper-setup.png)

## Not built, and limits
- **Not run on the Mac mini hub, on `mcd_extension`, or inside a real VS Code window.** The extension's own tests were
  not run (no extension file changed; the tab loads the hub's pages, so the new page and the study line appear there).
- No native VS Code view for Key numbers. The board (S28) is unchanged; it does not show key numbers.
- A number that needs arithmetic over two files (a verdict count that joins two tables, a Cliff's δ over a column) is
  not read. It is listed as a gap until a committed file stores it.
- Matching the report's numbers to files by rules alone (S27 step 12) is still not built.
- Key numbers of a paper project are not tied to the paper's tables; the paper-table check (S11) stays separate.
- The hook itself is not in this repository and was not changed; it still logs every Python command.
- Run-to-file matching is by path. A run that recorded no artifact paths is not tied to any number.

## For QA
- On the Mac mini: `uv run lemmata hub autoupdate install --branch s29-study-kind` (or fetch, check out and restart).
- Sync `temporal_dependency` once and read the message. Then follow it (most likely: sign in to GitHub again in
  Lemmata with private repositories allowed) and sync again; the footer must stop saying "Sync is failing".
- Check that `mcd_extension` still reads as a method paper with MCD as "ours" (rule Y2 from its confirmed map).
- Check the S18 contrast of the "test not met" chip and of the study line.

## Needs Juhyeong's decision
- ADR-009 (the two kinds, rule Y3 as default, L5, the benchmark checklist, Key numbers as its own page).
- In `temporal_dependency`: have your agent propose the map again with `"study": "benchmark"` and the key numbers
  (Key numbers → "Copy prompt for Claude Code"), then confirm both.
- Merge to main.
