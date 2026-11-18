---
type: handoff
owner_agent: lead
status: needs-qa
sources: ["founder chat 2026-11-18 17:06 KST ('For setup, I want to build a flowchart ... so that I can actually see how the setup connects to the thesis. This should be at the top of the page. Maybe think of a kanban system.')", "wiki/decisions/ADR-008-top-down-evidence-spine.md (thesis → claims → experiments → setup)", "S25-01-handoff.md (the curve map was removed from Setup)", "S27-01-handoff.md (hypothesis-first mode)", "https://github.com/daisjuhyeong/temporal_dependency/tree/short-exp (commit 7beeeab)"]
last_reviewed: 2026-11-18
---
# S28-01: a board at the top of Setup (thesis ← claims ← experiments ← what was used)

Asked by Juhyeong (chat, 2026-11-18): a flowchart at the top of the Setup page that shows how the setup connects to
the thesis, in the manner of a kanban board. Built from the chat session. Branch `s28-setup-board`, cut from
`s27-hypothesis-first`. Nothing is merged to main.

## Reading of the request (decided by the lead; Juhyeong can change it)
- **Kanban = four columns of cards, one column per level**, not columns per status:
  Thesis (or Problem) · Claims (or Hypotheses) · Experiments (or Steps) · What was used. Status stays on the card
  as its tag (`[finding]`, `[done]`).
- **Thesis on the left**, so the board reads in the same top-down order as the rest of Lemmata (ADR-008).
- **Lines only for a path.** With nothing selected, thin lines join thesis, claims and experiments (few lines).
  Lines to the items are drawn for the selected card's path only (or for all when there are 24 or fewer), so the
  board does not become the curve map that S25 removed.

## What changed
- **Engine: `engine/board.py` (new), `board` inside `GET /api/setup`.** Rules only, no model.
  - *Paper project:* from the Setup document: thesis text, claims, experiments, items. A claim with no experiment
    and an experiment with no claim are kept and counted (`counts.claims_untested`, `experiments_no_claim`,
    `items_unreached`).
  - *Hypothesis-first project* (once a hypothesis or a step exists): problem, live hypotheses, the protocol's
    steps. For each step, "what was used" is read from its own deliverable tables (csv or tsv, plain or `.gz`) by column name:
    a method column (`model`, `method`, `detector` …), a dataset column (`dataset`, `source` …), a suite
    column (`group`, `suite` …), `seed`, a condition column (`variant` …), `status`, and metric columns with a
    known metric name (`auc_pr`, `f1` …).
    - One run = one (method, dataset, condition, seed). The same run in a part file and in the merged file counts
      once; a failed attempt that was repeated with success is not a failed run.
    - More than 8 datasets with a suite column: one card per suite (e.g. `TSB-AD-U`, up to 23 datasets).
    - No known metric name: one card "N measures" listing the numeric columns.
    - A tidy table (a `measure` column beside a `value` column): the measure names are that column's values. When a
      step has such a table, those names are its measures, and other tables' unnamed number columns are not added.
    - A compressed table up to 12 MB on disk is read as a stream, up to 96 MB of text; beyond that the step panel
      says it was read in part.
    - A metric named in a hypothesis's statement or test is marked "named in H2, H3".
    - Each step also lists the Setup sheets (result files) under its deliverables.
- **Web: the board is the first thing on Setup** (`bdBoard` in `web/research.js`, styles in `app.css`).
  - Click a card: its path to the thesis stays lit, the rest dims, lines join the path, and one sentence says it
    ("auc_pr is used in stepC and stepD, which test H2, H3 and H2b.").
  - A dashed card is not connected: an experiment that tests no claim, a claim nothing tests. The header counts them.
  - Below the board, a panel for the selected card: a step's runs (methods × datasets × seeds), failed runs, what it
    writes and needs; a method's datasets, seeds, runs and failed runs per step; a suite's dataset names.
    In a paper project an item opens the existing item section (paper and code lines) instead.
  - Selecting a claim or an experiment narrows the sheets below to its own.
  - Each kind shows 6 cards, then "+ n more"; over the cap, lit cards come first.
  - Under 640 px (VS Code side panel) the columns stack and the lines are hidden.
- **Hypothesis-first Setup page.** The rough per-file counts and the "no confirmed map" notice are not shown above
  the board. When more than 12 result files have a sheet, the page no longer opens on all of them: it says how many
  there are, a step shows its own, and "show all" lists everything as before.
- **FAQ:** "How does what I used connect to the thesis?". **Glossary:** "Board" in `docs/map/README.md`.
- Small fix: the "show these lines" dialog titled a path without a line as `path:undefined`.

## VS Code
The Lemmata tab loads `research.js` and `app.css` from the hub, so the board appears once the hub runs this branch.
No new extension version. Checked at 760 px and 420 px in a browser; not checked inside a real VS Code window.

## Checked
- `temporal_dependency`, branch `short-exp` (7beeeab), on a local copy. The problem, H1–H3, H2b and steps A–D were
  entered by the lead in the role of the researcher's LLM, as in S27; **the Mac mini hub will show whatever is
  confirmed there.**
  - Step C: 3,294 runs = 18 methods × 61 datasets × 3 seeds, 40 marked failed (matches `results/C_cells.csv`).
  - Step D: 1,620 runs, 18 failed, conditions blockorder, global, within (matches `results/D_cells.csv`).
  - Step A: 62 sources in three suites (22, 17, 23), 42 measures (the `measure` column of `A_dependence.csv.gz`).
  - Step B: 62 sources in the same three suites, 16 measures, read from `B_drift.csv.gz` (decided by Juhyeong,
    18:22 KST: compressed step tables are read).
  - Reading the two compressed tables (47 MB and 9 MB of text) adds about 1 s, once per scan.
- The mapped synthetic project of `test_map.py` (paper project, 3 claims, 4 experiments, 10 items) and the sample
  project (one claim with no experiment, one experiment with no claim: both dashed).
- Tests: `test_map.MapTest.test_board`, `test_hypo.HypoTest.test_board_from_the_steps_tables`. Full suite: 195 OK
  (2 skipped), also after the compressed-table change. No console errors at 1280, 760 and 420 px.

## Screenshots
- [Hypothesis-first project, nothing selected](screenshots/board-hypothesis-first.png)
- [A step selected](screenshots/board-step-selected.png) · [a metric selected](screenshots/board-metric-selected.png)
  · [Step B, read from a compressed table](screenshots/board-step-b-compressed.png)
- [Paper project, a dataset selected](screenshots/board-paper-dataset-selected.png)
- [760 px](screenshots/board-vscode-medium.png) · [420 px, stacked](screenshots/board-vscode-narrow.png)

## Not built
- Drag and drop. The cards are read from the files; moving one would have to change a claim–experiment link.
- Reading `.json` or `.parquet` step tables.
- The board in the MCP `setup` tool (it still lists the per-file items).
- In a hypothesis-first project, an item's paper and code lines (the item panel shows its use per step only).

## For QA
- On the Mac mini: `git fetch origin && git checkout s28-setup-board`, restart the hub, open Setup for
  `temporal_dependency` and for `mcd_extension`.
- Check that the lines redraw when the window or the VS Code panel is resized.
- Check the S18 contrast of the dimmed cards (opacity 0.4).

## Needs Juhyeong's decision
- Decided 2026-11-18 18:22 KST: the columns stay thesis first; compressed step tables are read.
- Merge to main.
