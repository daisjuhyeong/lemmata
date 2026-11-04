---
type: spec
owner_agent: pm
status: draft
sources: ["founder decision, 1st presentation, 2026-11-03 (no file in raw/ yet)"]
last_reviewed: 2026-11-04
---
# Demo spec, Sprint S02 (localhost demo of the MVP)

Product: Research Map (package/CLI `rmap`). For the 2nd presentation. Runs on Juhyeong's Mac, one command, opens http://localhost:8765 (default port; falls back to the next free port and prints the URL).

## Provenance and status
- Source of every story: **founder decision, 1st presentation, 2026-11-03**. This is NOT user evidence. No interview has been done; H1-H4 remain hypotheses and nothing here confirms them.
- Proposed defaults marked "(PM proposal)" are not founder decisions; Juhyeong confirms or changes them.
- Constraints (founder decision): Python stdlib-first, no npm build, fully offline, no AI call per commit, no AI cost to run. Layout: `app/src/rmap/engine/`, `app/src/rmap/server.py`, `web/`, `app/samples/make_sample.py`, `app/tests/`.
- Wording rule (founder decision): findings never accuse. Use "could not be matched", "differs", "not traced". Never "wrong", "fake", "fabricated", "error by author".

## Vocabulary
- **Node**: thesis, research question (RQ), section, figure, table, equation, number-claim, result file, code file, run, reference.
- **Link**: dependency edge. *Detected* = explicit in source (`\input`, `\includegraphics`, `\cite`, `\ref`, `% generated-by:` comment, script writes path). *Proposed* = inferred (number match, name similarity); not in the graph until the author approves.
- **Checkpoint**: researcher's own "last known good" snapshot (content hashes of every node in both repos).
- **Alarm** (core): set of nodes to recheck since the checkpoint, grouped by causing change; based on content hash of the node, so a change that leaves bytes identical to the checkpoint raises nothing.
- **Analyzer** (optional): for one alarm, the chain of links plus the diff.
- **Finding**: an integrity-check result with file:line evidence.

## User stories and acceptance criteria

Persona for all: "an ML author before a deadline".

### US-01 One-command launch
As an ML author before a deadline, I want to start the tool with one command and see it in my browser, so that I can try it without setup.
1. Given a fresh checkout and Python 3.10+ and git on a Mac, When I run the single documented command, Then a server starts and http://localhost:<port> is printed within 5 s.
2. Given the command ran, When the server is ready, Then the default browser opens that URL (flag `--no-open` disables this).
3. Given the network is disconnected, When I use any demo feature, Then everything works with no error (no CDN, no npm, no outbound request).
4. Given the default port is busy, When I launch, Then the next free port is used and the printed URL is correct.

### US-02 See the whole paper as an interactive graph
As an ML author before a deadline, I want one graph of my whole paper from thesis down to runs, so that I can see what depends on what.
1. Given the sample project, When I open the app, Then the main view is an interactive graph with layers in this order top to bottom: thesis, RQs, sections, figures/tables/equations, result files, code, runs.
2. Given the graph, When I click a node, Then a side panel shows its type, source file:line, and its upstream and downstream neighbours.
3. Given a node, When I choose "trace down" or "trace up", Then the path to runs (down) or to the thesis (up) is highlighted.
4. Given the graph, When I toggle "references", Then reference nodes and citation edges appear as an extra dimension and hide again when toggled off.
5. Given the paper and code are separate repos, When both are loaded, Then cross-repo links (for example Table 2 to `results/table2.csv`) appear in one graph with each node labelled by its repo.

### US-03 Set a checkpoint
As an ML author before a deadline, I want to mark my own "last known good" state, so that later alarms are relative to something I trust.
1. Given a loaded project with no checkpoint, When I click "Set checkpoint", Then the current content hashes of all nodes in both repos are stored locally with a timestamp and optional note.
2. Given a checkpoint exists, When I set a new one, Then alarms recompute against the new one and the old one stays listed (not deleted).
3. Given a checkpoint was just set, When the alarm view opens, Then it shows 0 alarms.
4. Given the sample project, When it loads for the first time, Then a seeded checkpoint CP1 already exists (see Golden set).

### US-04 Alarm: what must be rechecked
As an ML author before a deadline, I want a list of what to recheck since my checkpoint, grouped by the change that caused it, so that I do not re-read the whole paper.
1. Given CP1 and the sample history, When I open Alarms, Then the groups and node lists equal the Golden set exactly (A1 and A2, no others).
2. Given a change committed and then reverted so the file bytes equal the checkpoint (sample commits K4, K5 on `eval.py`), When alarms compute, Then nothing is raised for that file or its dependents.
3. Given an alarm group, When I view it, Then it shows the causing change (repo, commit, file, short hash), and the affected nodes in the graph are highlighted.
4. Given a node with only upstream changes, When alarms compute, Then it is listed as "downstream of" the cause, distinct from nodes whose own content changed.
5. Given alarms compute, When I check the run log, Then no AI/model call and no network call was made.
6. Given the sample with 2 proposed links unapproved, When alarms compute, Then proposed links contribute nothing to the alarm propagation (see US-07).

### US-05 Analyzer: why
As an ML author before a deadline, I want to open one alarm and see why, so that I can decide quickly whether it matters.
1. Given alarm A1, When I click "Analyze", Then I see the chain of links from the changed node to each affected node, in order.
2. Given alarm A1, When the analyzer is open, Then I see the diff of the causing change (`learning_rate: 3.0e-4` to `1.0e-3`) with file:line.
3. Given the analyzer is optional, When I never click it, Then alarms still work and no analyzer code runs.
4. Given the analyzer, When it renders, Then it uses no AI call (deterministic: links plus text diff).

### US-06 Triage per node
As an ML author before a deadline, I want to mark each flagged node reviewed, needs fixing, or ignore, with a note, so that I can work through the list and resume later.
1. Given an alarm node, When I choose reviewed, needs fixing, or ignore and type a note, Then the state and note are saved in a local file inside the project's state directory.
2. Given I restart the server, When I reopen the project, Then triage states and notes are unchanged.
3. Given a node is "reviewed", When its content hash changes again later, Then it returns to "unreviewed" and the earlier note is kept visible as history.
4. Given the alarm list, When I filter by triage state, Then only matching nodes show; counts per state are displayed.
5. Given any triage action, When it completes, Then nothing leaves the machine.

### US-07 Approve proposed links
As an ML author before a deadline, I want inferred links to wait for my approval, so that the tool never silently builds a wrong picture of my paper.
1. Given the sample, When the graph loads, Then exactly 2 proposed links (PL1, PL2, see Golden set) appear as dashed and are not counted in any alarm.
2. Given a proposed link, When I click Approve, Then it becomes a solid link, is stored locally, and alarms recompute immediately.
3. Given a proposed link, When I click Reject, Then it is hidden, stored as rejected, and is not proposed again.
4. Given PL2 is approved on the sample, When alarms recompute, Then Appendix B joins group A1 as downstream (Golden set, after-approval state).

### US-08 Reference and citation hygiene
As an ML author before a deadline, I want to know about bib entries that could not be matched, are uncited, or cites with no entry, so that my reference list is clean.
1. Given a bib entry absent from the bundled offline cache, When checks run, Then finding F01 "reference could not be matched" appears for `smith2021ghost` with refs.bib:line.
2. Given a bib entry never cited, When checks run, Then F04 appears for `unused2019`.
3. Given `\cite{nobody2020}` with no bib entry, When checks run, Then F08 appears with main.tex:line.
4. Given an online lookup option, When I have not enabled it, Then no request is made; enabling it is explicit and per run (not used in the demo).
5. Given bib entries present in the cache and cited (negative controls), When checks run, Then no finding is raised for them.

### US-09 Figure, table and label hygiene
As an ML author before a deadline, I want unreferenced figures/tables and undefined refs flagged, so that reviewers do not find them first.
1. Given a figure defined but never `\ref`'d (`fig:arch`), When checks run, Then F05 appears with file:line of the label.
2. Given a table defined but never referenced (`tab:ablation`), Then F06 appears.
3. Given `\ref{fig:missing}` with no label, Then F07 appears with the file:line of the `\ref`.
4. Given every other label is defined and used, Then no other F05-F07 finding appears.

### US-10 Main text versus appendix consistency
As an ML author before a deadline, I want numbers and hyperparameters that differ between main text and appendix flagged, so that the paper agrees with itself.
1. Given main text says learning rate 3e-4 and Appendix B says 1e-3, When checks run, Then F02 shows both values side by side with both file:line locations.
2. Given main text says batch size 64 and Appendix B says 128, Then F03 shows both.
3. Given hyperparameters that agree (for example optimizer Adam in both), Then no finding is raised.
4. Given F02, When I open it, Then it links to the graph nodes (Section 4, Appendix B) involved.

### US-11 Traceability of numbers and figures
As an ML author before a deadline, I want numbers and figures traced to result files and scripts, so that every claim has a source I can point to.
1. Given the main text states "92.4 F1", present in no result file, When checks run, Then F09 "number not traced to any result file" appears with main.tex:line.
2. Given `fig:qual` has no generating script or generated-by marker, Then F10 appears with file:line.
3. Given Table 2 values that match `results/table2.csv` (negative control) and `fig:curve` generated by `plot_curve.py`, Then no finding is raised for them.
4. Given a table whose values are traced (Table 2), When I select its node, Then the graph shows the path table, result file, run, code. (Numbers are not nodes; per QA 2026-11-04 the path is reached from the table or figure node, not from a single number.)

### US-12 Findings show evidence and never accuse
As an ML author before a deadline, I want each finding to show where it comes from in neutral language, so that I can trust and verify it.
1. Given any finding, When displayed, Then it shows at least one `path:line` and the quoted source line.
2. Given any finding text, When QA scans all message templates, Then none contains the words "wrong", "fake", "fabricated", "mistake", "error by", "cheat".
3. Given a finding, When I open the report, Then I can set its triage state (US-06) and jump to its node in the graph.
4. Given the checks run, When I export "HTML report", Then a single local HTML file lists all findings and alarms with evidence, and opens offline.

### US-13 Real repository mode (code-only)
As an ML author before a deadline, I want to point the tool at my own repo, so that I can see it on real work.
1. Given `alarm-analyzer-eval` (code-only), When I run `rmap open <path>` (PM proposal), Then the graph shows code files, result files and runs without error and without a paper layer.
2. Given no paper, When checks run, Then paper-dependent checks are shown as "not applicable (no paper)" and not as passed.
3. Given the Overleaf zip is later supplied, When I add it, Then the paper layer appears and links to code form without changing the code-only results.
4. Given the real repo, When the tool runs, Then it only reads the repo (no writes except its own state directory, which is gitignored).

### US-14 Reproducible synthetic sample
As the presenter, I want the sample project rebuilt identically every time, so that the demo never surprises me.
1. Given `app/samples/make_sample.py`, When run twice into empty directories, Then both outputs have identical file contents and identical findings and alarms.
2. Given the sample, Then it comprises two separate git repos (paper, code) with scripted histories and fixed commit timestamps.
3. Given the sample, When checks run, Then each of F01-F10 is triggered exactly once and the negative controls raise nothing.
4. Given make_sample.py, Then it needs only stdlib and the `git` binary and writes only to the target directory.

## Golden set (synthetic sample; QA authority is S02-03)

Node IDs below are working names; pipeline-eng may rename them but must tell QA, and QA updates `app/tests/golden.json`. File:line values are recorded by QA from the frozen generated files and must equal the actual lines. All findings must be reproducible from a clean build.

### Sample history (scripted)
Paper repo `paper/` (Overleaf-style: `main.tex`, `appendix.tex`, `refs.bib`, `figures/`): P1 initial draft; P2 add tables and figures; **CP1 seeded here**; P3 "appendix B: learning rate 1e-3".
Code repo `code/` (`train.py`, `eval.py`, `plot_curve.py`, `configs/default.yaml`, `results/table2.csv`, `results/metrics.json`): K1 initial training code; K2 add eval and plotting; **CP1 seeded here**; K3 "change learning rate 3e-4 to 1e-3" (config only; results not regenerated); K4 "tmp: edit comment in eval.py"; K5 "revert eval.py".

### Findings (exactly 10)
| ID | Check | Subject | Evidence |
|----|-------|---------|----------|
| F01 | reference could not be matched | bib key `smith2021ghost` | refs.bib:line |
| F02 | main/appendix differ | learning rate 3e-4 (main.tex Section 4) vs 1e-3 (appendix.tex Appendix B) | both lines |
| F03 | main/appendix differ | batch size 64 vs 128 | both lines |
| F04 | uncited bib entry | `unused2019` | refs.bib:line |
| F05 | unreferenced figure | `fig:arch` | label line |
| F06 | unreferenced table | `tab:ablation` | label line |
| F07 | undefined ref | `\ref{fig:missing}` | main.tex:line |
| F08 | undefined cite | `\cite{nobody2020}` | main.tex:line |
| F09 | number not traced to a result file | "92.4" F1 in main.tex | main.tex:line |
| F10 | figure with no generating script | `fig:qual` | label line |

Negative controls (must raise nothing): cached and cited keys (for example `vaswani2017attention`); agreeing hyperparameter (optimizer Adam); Table 2 baseline value "0.871" present in `results/table2.csv`; `fig:curve` generated by `plot_curve.py`; all other labels.

### Proposed links (exactly 2, unapproved at load)
- PL1: Section 4 learning-rate claim to `configs/default.yaml:learning_rate` (value match).
- PL2: Appendix B hyperparameter table to `configs/default.yaml` (value match).

### Alarms vs CP1
State 0 (as loaded, PL1 and PL2 unapproved), exactly 2 groups:
- **A1** cause: code repo K3, `configs/default.yaml`. Nodes: cause = `cfg:default.yaml` (changed); downstream = `run:train_main`, `file:results/table2.csv`, `tab:main` (Table 2). 3 downstream nodes.
- **A2** cause: paper repo P3, `appendix.tex`. Nodes: changed = `app:hparams` (Appendix B). 0 downstream nodes.
No alarm for `eval.py` or anything depending on it (K4+K5 byte-identical to CP1). No alarm for `plot_curve.py`/`fig:curve`.

State 1 (after approving PL2): A1 downstream = `run:train_main`, `file:results/table2.csv`, `tab:main`, `app:hparams` (4 nodes). A2 unchanged. Section 4 is still not in A1 (PL1 unapproved).
State 2 (after approving PL1 as well): A1 additionally lists `sec:setup` (Section 4) as downstream (5 nodes).
State 3 (after setting a new checkpoint): 0 alarms; F01-F10 unchanged (findings do not depend on checkpoints).

## 5-minute demo walkthrough (synthetic sample, presenter script)
Updated 2026-11-04 to the built UI, using [QA report section 5](../sprints/S02/qa-S02-localhost-demo.md) and [web-eng control names](../sprints/S02/handoff-web-eng.md). Product is "Research Map", CLI `rmap`, state folder `.rmap/`.

Setup before the audience arrives: run the command once and confirm the page loads at the printed URL (default http://127.0.0.1:8765). No cleanup needed: `rmap demo` rebuilds the sample in `~/rmap-demo` with CP1 seeded and empty triage on every run (unless `--keep`). Use a window at least 1280 CSS px wide if you can; from 1024 to 1279 px the side panels narrow, and below 1024 px the UI shows only a notice (QA D1, fixed by the lead). The F-numbers and PL1/PL2 are spec labels; the UI does not show them, so use the titles below.

| Time | Click / action | Say / show | Story |
|------|----------------|-----------|-------|
| 0:00 | In Terminal run `uv run --project app rmap demo` | "One command, offline, my own machine. No AI call per commit." Browser opens at the localhost URL. | US-01 |
| 0:30 | Look at the main graph, top to bottom | Bands: Thesis, Questions, Sections, Paper items (figures, tables, equations), Repo results, Runs, Code. Paper and code are separate repos, one graph (repo is shown in the side panel on selection). | US-02.1, .5 |
| 1:00 | Click Table 2; in the side panel click `Trace down` | Highlight from Table 2 to `results/table2.csv`, the run, the code. "Read top-down." Then click `train.py` and `Trace up`: "work bottom-up." | US-02.2-.3 |
| 1:30 | Click a citing section (for example Section 1), then toggle `References` | Reference column appears; citation edges show for the selected section. "Citations are an extra dimension." Toggle off. | US-02.4 |
| 1:45 | Open the top-bar `Checkpoint: CP1` popover, then the `Alarms` tab | "CP1 is my own last known good snapshot." The tab badge reads 5 (items); inside the tab "5 items in 2 groups". | US-03, US-04.1 |
| 2:15 | In `Alarms`, open group A1 ("change learning rate 3e-4 to 1e-3") | Cause: code commit K3. Changed config plus 3 downstream: run, `table2.csv`, Table 2. Click "Show in graph". "These need a recheck because their upstream changed." | US-04.3-.4 |
| 2:45 | Point at what is NOT listed | "I edited and reverted `eval.py`. Same bytes as the checkpoint, so no alarm." | US-04.2 |
| 3:00 | Click `Analyze` on the A1 header | Chain config, run, `table2.csv`, Table 2, plus the diff `learning_rate: 3.0e-4` to `1.0e-3`. Optional layer; the "Ask Claude" button is disabled in this demo. | US-05 |
| 3:30 | Open the `Links` tab, row "App. B Hyperparameters -> configs/default.yaml", click `Approve`; return to `Alarms` | "Inferred links wait for my approval." App. B now joins A1 (4 downstream). Leave the Section 4 link unapproved. Proposed links are drawn dashed in the graph (select App. B or use Show: Proposed links); approval itself is only in the `Links` tab. | US-07 |
| 3:50 | In `Alarms` select the Table 2 row; type the note "rerun train with lr 1e-3" first, then click `✕ Needs fixing`. Select App. B, click `✓✓ Reviewed` | Saved locally in `.rmap/`; filter counts update. | US-06 |
| 4:10 | Open the `Checks` tab, find the card "Learning rate differs..." (3rd card, after batch size), click `Open evidence` | Main text says 3e-4 (main.tex:33), appendix says 1e-3 (appendix.tex:7). Neutral wording: "differs". Click "§4 Experimental Setup -> graph". | US-10, US-12 |
| 4:30 | Scroll `Checks`; open the 1st card (reference could not be matched) and the 9th (number not traced) | "Reference could not be matched" (offline cache, refs.bib:21); "92.4 not traced to any result file" (main.tex:48). | US-08, US-11 |
| 4:50 | Click `Export HTML report` (top bar); say closing line | "Use AI, don't depend on AI." Next: Overleaf zip for my own repo `alarm-analyzer-eval` (code-only today). | US-12.4, US-13 |

Optional live-edit moment (not in the 5 minutes): edit `code/train.py` in `~/rmap-demo`, click Rescan; a new group "Uncommitted changes" appears. Do not edit `default.yaml` for this; it already changed in K3 and adds no new group.

Known deviations to keep off screen or mention honestly: sections are not in paper order; graph nodes have no repo label; the Section 4 evidence text may read "linked by you" for an unapproved link (QA D2).

Fallback if the live page fails: the exported HTML report from the last good run (keep a copy on the desktop; it opens offline).

## Open questions for Juhyeong
1. Port and command name: default 8765 and `./demo.sh` at the repo root, OK? (PM proposal)
2. Mac environment: Python version (3.10+ assumed) and `git` installed?
3. Should unapproved link PL1 stay unapproved in the walkthrough (current script) or be approved to show Section 4 joining A1?
4. Is there a file for the 1st presentation (slides/notes) to cite from raw/ so these stories meet rule 1?
