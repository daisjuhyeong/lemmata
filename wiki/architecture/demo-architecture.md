---
type: architecture
owner_agent: cto
status: proposed
sources:
  - "../decisions/ADR-002-localhost-demo.md"
  - "data-model.md"
  - "../product/demo-spec.md"
  - "../sprints/S02/S02-01-pipeline-eng.md, ../sprints/S02/S02-02-web-eng.md"
  - "founder decisions, 1st presentation, 2026-11-03 (relayed by the lead; no file in raw/ yet)"
  - "local repo /home/claude/alarm-analyzer-eval @ baa9f7d (not in raw/)"
  - "https://docs.astral.sh/uv/ ; https://docs.python.org/3/library/http.server.html ; https://js.cytoscape.org/"
last_reviewed: 2026-11-04
---
# Demo architecture (S02, localhost MVP demo)

How the localhost demo for the 2nd presentation is built. Decision and scope cuts: [ADR-002](../decisions/ADR-002-localhost-demo.md). Exact JSON shapes and routes: [data-model.md](data-model.md); that page is the contract and wins on any conflict with this one. Stories and golden set: [demo-spec](../product/demo-spec.md).

## 1. Components
```
 Terminal: uv run --project app lemmata demo | open <dir> | scan <dir> | checkpoint <dir>
   │
   ▼
 cli.py ──(demo)──► samples/make_sample.py  ──► ~/lemmata-demo/{paper/.git, code/.git, .lemmata/project.json, .lemmata/cache/refs.json}
   │
   ├──► engine.Engine(project_root).scan()        [pure Python + git binary, no network unless --online]
   │       manifest → trees → nodes → edges/proposals → events/replay → alarms → checks
   │       └── writes <project>/.lemmata/{graph,events,findings,alarms}.json (+ checkpoints, triage on demand)
   │
   └──► server.py  ThreadingHTTPServer @127.0.0.1:8765 (next free if busy)
            ├── /            → web/index.html, app.js, app.css, vendor/cytoscape.min.js
            └── /api/*       → Engine facade (one lock around mutations)
                                   ▲
 Browser (offline) ── fetch JSON ──┘   graph · alarms · analyzer · findings · triage · checkpoints · timeline · export
```

## 2. Package layout and owners
```
app/
  pyproject.toml            [lead/web-eng] name=lemmata, requires-python>=3.10, dependencies=[], script lemmata=lemmata.cli:main, build backend hatchling
  README.md                 [web-eng] how to run (one command + zero-install fallback)
  src/lemmata/
    __init__.py             __version__ = "0.1.0"
    __main__.py             python -m lemmata → cli.main()
    cli.py                  [web-eng] subcommands demo / open / scan / checkpoint; port and browser handling
    server.py               [web-eng] routing, guards, static files, export, error mapping
    web/                    [web-eng] index.html, app.js, app.css, vendor/{cytoscape.min.js, LICENSE, README.md}
    engine/                 [pipeline-eng]
      api.py                Engine facade (the only import server.py and cli.py may use)
      errors.py             NotFound, BadRequest
      manifest.py           load/create project.json, seed_checkpoint
      store.py              hub IO, atomic writes, blob store, hub .gitignore
      tree.py               Tree interface: WorkTree(root) / GitTree(repo, rev); list_files, read, blob_id; git helpers
      classify.py           file → node kind (data-model §3.2)
      latex.py              flatten \input, units and ownership, labels, refs, cites, markers, numbers, hparam mentions
      bib.py                .bib entries with line numbers
      code.py               python imports, write calls, run records, README provenance, config keys
      graph.py              node/edge assembly, ids, hashes, value_match proposals, merge link decisions
      history.py            events, first-parent replay after the checkpoint, message flags
      alarms.py             data-model §8
      analyze.py            chain + diff + explanation
      checks.py             the 8 checks
      refs.py               refs cache; optional OpenAlex → Crossref lookup (urllib)
      triage.py             triage entries, effective state, link decisions
  samples/make_sample.py    [pipeline-eng] stdlib + git only; writes only to its target dir
  tests/                    unittest; [pipeline-eng] engine, [web-eng] server routes, [qa] golden.json
    fixtures/api/*.json     example payloads copied from data-model.md (web-eng starts here)
```
Rules:
- `server.py` and `cli.py` import only `lemmata.engine.api` and `lemmata.engine.errors`. The engine never imports the server.
- Third-party code is limited to the vendored front-end library. `web/vendor/README.md` records the version, source URL and licence.

## 3. Runtime flow
### 3.1 `lemmata demo [--dir ~/lemmata-demo] [--port 8765] [--no-open] [--keep] [--online]`
1. Unless `--keep`, delete `--dir` **only if it contains the marker file `.lemmata-sample`** (otherwise refuse), then run `make_sample.py <dir>` with `sys.executable`. It is located at `<package>/../../samples/make_sample.py`; if missing, print "demo needs a source checkout".
2. `make_sample.py` creates two git repos, `paper/` (P1–P3) and `code/` (K1–K5), with fixed identity, fixed dates and an isolated git config (`GIT_CONFIG_GLOBAL` → empty file, `GIT_CONFIG_NOSYSTEM=1`, `commit.gpgsign=false`), so the SHAs are identical on every run. It tags `cp1` at P2/K2 and writes `.lemmata/project.json` (with `seed_checkpoint`) and `.lemmata/cache/refs.json`.
3. `Engine(dir).scan()`: no `checkpoints.json` exists, so CP1 is seeded from the tags with its fixed `created_at`, and the full pipeline runs (3.3).
4. Start the server, print `lemmata: serving <name> at http://127.0.0.1:<port>  (Ctrl-C to stop)`, and open the browser unless `--no-open`.

### 3.2 `lemmata open <project_dir> [--paper DIR] [--code DIR] [--port] [--no-open] [--online]`
If `.lemmata/project.json` is missing, create it. With no flags, `<project_dir>` is a single repo `{"id":"code"|"paper","path":"."}`, with the role auto-detected (paper if it contains a `.tex` with `\documentclass`). `--paper` and `--code` add or replace repos. Then scan and serve. `lemmata scan <dir>` scans and prints a one-line summary (QA and CI). `lemmata checkpoint <dir> [--at repo=rev …] [--note TEXT]` creates a checkpoint.

### 3.3 Scan pipeline (Engine.scan)
1. **Manifest** → repo list. For each repo, build a `WorkTree`; check git (`git rev-parse`), HEAD, branch and dirty state.
2. **Nodes**: classify files and hash them (blob id); parse the paper (flatten → units → `sha256` of owned text); parse the bib; read run records; parse README provenance.
3. **Edges**: LaTeX edges and markers, run-record edges, imports, write calls, README `generated_by`; then `value_match` proposals; then merge link decisions from `triage.json` (statuses `approved`/`rejected`).
4. **Events**: `git log --first-parent` per repo (subject, body, files via `diff-tree --raw`), run events, a worktree event, and message flags.
5. **Seed checkpoint** if needed.
6. **Replay** (only events after the active checkpoint's rev): hash changed files from the diff-tree blob ids; re-parse the paper at a commit only if a `.tex`/`.bib` changed (`GitTree`). Fill `changed_nodes`.
7. **Alarms** (data-model §8), **checks** (§6; `refs.py` goes online only with `--online`).
8. Write `graph.json`, `events.json`, `findings.json` and `alarms.json` atomically; return the project status.

One `Tree` abstraction serves the working tree, a past commit (`--at`, replay) and the checkpoint, so the parser runs the same way everywhere.

### 3.4 UI (single page, plain JS, Cytoscape preset layout)
- **Graph** (default view). Nodes are placed by `layer` (y) and by barycentre order within a layer (x; 4 sweeps, computed in `app.js`). Each node shows its repo badge and `name`. References are hidden behind the "references" toggle and appear as a right-hand column. Proposed edges are dashed; rejected edges are hidden.
- **Side panel** on node click: kind, `repo:path:line`, upstream and downstream neighbours, triage control with note, and "trace down" / "trace up" (client-side BFS highlight).
- **Alarms panel**: groups A1…, each showing its cause (repo, short sha, subject, files, flags). Changed and downstream nodes are listed separately, `output_identical` is labelled in words, and the group's nodes are highlighted in the graph. Includes an "Analyze" button and triage filters with counts (client-side).
- **Analyzer drawer** (opens only on click): chain, diff, explanation, and a disabled "Ask Claude why" button labelled "not available in this demo".
- **Findings list**: check, message, evidence `path:line` plus quoted text, "show in graph", triage. Checks marked `not_applicable` are shown as such, never as passed.
- **Checkpoints panel**: "Set checkpoint" (note), list. **Timeline strip**: events after the checkpoint plus a checkpoint marker. **Rescan** and **Export HTML report** buttons.
- Control labels must match the PM walkthrough. Status is never shown by colour alone (designer rule). Visual tokens come from `wiki/design/DESIGN.md` when it exists.

## 4. Real vs stubbed in the demo
| Area | Status |
|---|---|
| LaTeX structure, labels, refs, cites, `\input`, `\includegraphics`, markers | Real (regex; no macro expansion) |
| Bib parsing, uncited/undefined checks | Real |
| Reference existence | Real from the cache; online lookup real but opt-in and **not used live**. The sample's cache is seeded (`source: "seed"`) |
| Content hashes, replay, alarms by cause, message flags | Real |
| Proposed links + approve/reject | Real (hyperparameter-name proposals only) |
| Main ↔ appendix consistency | Real for the hyperparameter dictionary only |
| Numeric trace, figure provenance | Real (rounding match; marker/README/run-record provenance) |
| Python imports, write calls, run records, README provenance | Real (run records exist only in the sample) |
| Analyzer chain + diff | Real, deterministic |
| "Ask Claude why" | **Stub** (HTTP 501, labelled) |
| Figure/section numbering | Approximate |
| Overleaf | Manual unzip to a folder, then `open --paper`; no sync |
| Tauri app, file watching, time travel, multi-project | Not built |

## 5. Security and privacy
- Binds 127.0.0.1 only. Host and Origin checks plus a JSON content type on POST (blocks DNS-rebinding and cross-site POSTs from other tabs). Static paths are confined to `web/`. Request bodies are capped at 64 KB.
- File writes happen only under `<project>/.lemmata/` (engine) or the sample target dir (`make_sample.py`). The tool never runs git commands that write (no commit, checkout or config changes in the user's repos); read-only git plumbing only.
- No network except opt-in `--online` (bib titles/DOIs → OpenAlex, Crossref). A test blocks sockets and runs the full pipeline (S02-01 AC8). No model or API calls anywhere; the runtime never touches anyone's Claude plan.

## 6. Performance targets (QA measures)
- Sample: `lemmata demo` reaches a served page in < 5 s on a Mac (US-01.1); a rescan takes < 2 s.
- `alarm-analyzer-eval` (~240 tracked files, 114 commits): scan < 10 s. Replay covers only commits after the checkpoint; diff-tree blob ids avoid reading file contents.
- UI stays interactive with ~300 nodes and ~500 edges.

## 7. Parallel build plan (one engineer per side)
| Step | pipeline-eng | web-eng |
|---|---|---|
| 0 | read data-model.md; scaffold `engine/api.py` that returns the fixture JSONs | `pyproject.toml`, `cli.py`, `server.py` routes + guards against fixtures |
| 1 | `tree.py`, `classify.py`, `latex.py`, `bib.py`, `graph.py` → real `/api/graph` | graph view, side panel, trace up/down, references toggle |
| 2 | `make_sample.py`, `history.py`, `alarms.py`, checkpoints, `analyze.py` | alarms panel, analyzer drawer, checkpoints, timeline strip |
| 3 | `checks.py`, `refs.py` (cache), `triage.py`, link decisions | findings list, triage controls, approve/reject, rescan |
| 4 | tests incl. socket block; README provenance; write calls; `--online` | export snapshot, read-only mode, wording scan |
Hand-off point: the facade signatures in data-model §13. Neither side changes a shape without a CTO edit to data-model.md and a note to QA (S02-03).

## 8. Demo runbook (for the presenter; PM owns the script)
- Sample: `uv run --project app lemmata demo` (fallback: `PYTHONPATH=app/src python3 -m lemmata demo`). Fresh state on every run; `--keep` preserves triage. Optional live moment: edit `~/lemmata-demo/code/configs/default.yaml`, then click Rescan to see a "worktree" alarm group.
- Real repo, code-only: `uv run --project app lemmata open /path/to/alarm-analyzer-eval`, then optionally `lemmata checkpoint /path/to/alarm-analyzer-eval --at code=<rev> --note "..."`. HEAD `baa9f7d` is the code-only release tree, so a checkpoint from 9/17 shows mass removals. For the prototype-comparable view, Juhyeong checks out `308dab9` into a separate folder himself (the tool does not run writing git commands).
- Paper layer later: unzip the Overleaf project, then `lemmata open <code repo> --paper <unzipped dir>`. Run once with `--online` before the talk to fill the reference cache.
- Prerequisites: Python ≥ 3.10 and git on the Mac; run once with network so `uv` can fetch Python and the build backend; after that, everything runs offline.
