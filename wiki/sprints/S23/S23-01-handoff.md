---
type: handoff
owner_agent: lead
status: needs-qa
sources: ["founder chat 2026-11-13 14:28 KST"]
last_reviewed: 2026-11-13
---
# S23-01: Setup page (metrics, datasets, baselines, and how each experiment uses them)

Asked by Juhyeong (chat, 2026-11-13 14:28 KST): "a separate page just like claims, dedicated to details of the
experiment … evaluation metrics, datasets, baseline models … when I click them, I want to see how they are being
used in the experiment (… by connecting it in the graph)."

## What changed
- **New top-level page, Setup** (nav: Claims · Experiments · **Setup** · Digest · Review; also in the command palette
  and the VS Code tab, command **Lemmata: Open Setup**). The page uses the wide column (`#page.wide`, `--col-wide`).
- **Map, three columns.** Left: every metric, dataset and method found in the experiments' result files. Each has a
  one-line summary: a metric's direction and how often it is the main number; for a dataset, how often ours is best;
  for a method, its role (ours / extends / baseline / ablation variant) and how often it beats ours. Middle: the
  experiments. Right: the claims they test. Curves connect item → experiment → claim. A filter switches between
  All / Metrics / Datasets / Methods.
- **Click an item:** only what it connects to stays lit, and a panel opens with:
  - **How the experiments use it.**
    - Metric: main number, in the table, or recorded but never compared; its direction; ours vs the best other method.
    - Dataset: the metric used; ours, the best other method, the rank of ours, and which methods have no result on it.
    - Baseline: its number next to ours, how far ours is ahead, and one cell per dataset (red where it beats ours, outlined where it has no result).
    - Ours: its value and rank in each experiment.
  - **In the paper:** the lines that name it, with `file:line` links and the citations on those lines (titles from the .bib).
  - **In the code:** up to 4 code or settings files that name it, definitions first. In VS Code each opens in the editor.

  Click an experiment or a claim instead: it lists the items it is built on, grouped by kind, each clickable.
- **Checks per item** (rules only; flagged `!` on the map):
  - a metric read lower-better in one experiment and higher-better in another;
  - a metric recorded in the files but never compared;
  - a baseline with no result on some datasets ("No result on Weather");
  - one run per cell;
  - a baseline named in the paper but not cited on any line that names it;
  - a dataset or method the paper never names, or names only in the appendix.
- **Engine:** `engine/setup.py` builds the document from the Experiments document, so the two pages never disagree.
  Each experiment now carries a small `grid` (a row per method, a column per dataset, main metric, other measures)
  in `track.py` (map mode) and `experiments.py` (rule mode). In a search (`tuning`), the dataset and metric rows show
  the best setting rather than an "ours".
- **API / MCP:** `GET /api/setup` (also in exported snapshots); read-only MCP tool `setup` (filter `kind=metric|dataset|method`).
- **VS Code 0.6.0:** `setup` view; links `vscode://…/open?view=setup&sel=i:<item>` (selections `i:` and `c:` allowed
  besides `q:` and `x:`); the item panel on the website has **Open in VS Code**. Docs point at `lemmata-0.6.0.vsix`.

## Verified
Python 174 passed / 2 skipped (new `test_setup`: counts, roles, ours vs best per dataset, baseline gap and per-dataset
cells, paper line, claim → items, a deleted baseline result flagged as missing; `test_mcp_tools` calls `setup`;
`test_s18_ui` now pins the five-tab nav). Extension unit 68 (new link test). Browser on a synthetic project (the
`test_map` fixture with its map confirmed): overview, baseline, dataset, experiment and narrow (640px) views, with no
console errors. Screenshots in [screenshots/](screenshots/).

## Not verified
- Not run on `mcd_extension` or any real project; long item lists (30+ datasets) only reasoned about (the map grows
  taller; the panel scrolls).
- End-to-end extension tests not run in this session.
- Without a confirmed map the page works but is rough (each result file read on its own); it says so.

## Deploy
On branch `s23-experiment-setup` (stacked on S22). The hub runs it once its auto-update follows this branch
(`uv run lemmata hub autoupdate install --branch s23-experiment-setup`) or once it is merged into the followed one.
