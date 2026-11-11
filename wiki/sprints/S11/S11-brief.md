---
type: task-card
owner_agent: lead
status: built, not yet QA-verified
sources:
  - "founder request in chat, 2026-11-11 14:09 KST: experiments as a table or database, a row per thing tested, click for details (main results, baselines, datasets, design, whether the result agrees with the LaTeX table or figure), results over time, and after which change in the method the model improved"
  - "founder instruction in chat, 2026-11-11 14:31 KST: make the sections based on the research questions and/or hypotheses"
  - "design research report run in the same chat, 2026-11-11 (rows are questions, not runs; step chart of ours against best baseline with change markers; never join a line across a change of metric; credit a gain to a change only when it was the only change; cell-by-cell paper check with rounding-aware tolerance as in statcheck, https://statcheck.io ; hide unchanged columns as in `dvc exp show --only-changed`, https://doc.dvc.org/command-reference/exp/show ). Not yet filed in raw/"
  - "code on branch s07-public-site: app/src/lemmata/engine/experiments.py, engine/claims.py (RQ text and references), engine/api.py, server.py, web/research.js, web/app.css, tests/test_tree.py, tests/test_public.py"
last_reviewed: 2026-11-11
---
# S11 brief: Experiments, organised by research question and hypothesis

## What was built
- **Sections.** One per research question (RQ1, RQ2 …) and one per hypothesis (each contribution or hand-written claim). A section with no experiment says "Not tested yet". Results no question points to sit in "No question", with a "Tests…" picker to assign them.
- **Rows.** One per experiment: a table or figure in the paper with the result file behind it. Columns: metric, ours against the best other method (bar), the result over time (sparkline), paper check tally, last run.
- **Detail (click a row).**
  - Result: every method on the chosen metric, ours highlighted. The researcher can change the metric, which direction is better, and which row is "ours".
  - Design: result file, script, what it is compared with, datasets or columns, settings, which questions it tests.
  - History: every committed version of the result file as a step chart (ours solid, best other dashed), with a marker for each change in between: method ◆, settings ●, data ▲, evaluation ⟂. Below, one line per version: value, change since the previous version, the commits and changed settings (`window 50→100`), rank, and "★ became best".
  - Paper check: the paper's table with a mark in each cell: ✓ matches, ≈ rounded differently, ✕ differs, ~ value is in the file but elsewhere, ? not found. Also flags a bold number that is not the best in its column.
- **Honesty rules.** A gain is tied to one change only when one commit of one kind sits between two versions; otherwise the step says "several changes at once". When the evaluation code or the result columns changed, the step says "evaluation changed: not comparable" and the line is broken.
- Research-question text is now the question itself, and a table counts for a question only when the same sentence names both.

## Known limits (tell users)
- An experiment is found through a result file that is a table: CSV/TSV, or JSON with one record per method. Other formats show "could not be read".
- History is the git history of that result file. Results that were never committed, or were overwritten between commits, are not in it. This is not a run tracker.
- "Ours" is guessed from the row name ("ours", "proposed"), a name in the paper's title or abstract, the bold row, else the last row. The main metric defaults to the first column. Both can be set per experiment.
- Change kinds come from file paths (`eval`, `metric` → evaluation; `data`, `loader` → data; config files → settings; other code → method).
- Datasets are read from a `dataset` column or the column names; baselines from the other rows. There is no free-text "how it was designed" beyond script, settings and columns.
- Figures: linked or not linked only; numbers inside a picture are not checked.
- No seed-noise test: the "one run, no spread" warning is shown, but a small gain is not automatically called noise.
