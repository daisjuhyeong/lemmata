---
type: handoff
owner_agent: web-eng
status: draft
sources:
  - "../../architecture/data-model.md"
  - "../../architecture/demo-architecture.md"
  - "../../decisions/ADR-002-localhost-demo.md"
  - "../../design/DESIGN.md"
  - "../../design/screens/demo-screens.md"
  - "../../product/demo-spec.md"
  - "S02-02-web-eng.md"
  - "https://js.cytoscape.org/"
  - "https://registry.npmjs.org/cytoscape/-/cytoscape-3.34.4.tgz"
last_reviewed: 2026-11-04
---
# Handoff: S02-02 server and UI (web-eng)

Branch `s02-localhost-demo` (no git run by me). Product name is the literal placeholder `lemmata` / `Lemmata` everywhere.

## What changed (all under `app/`, plus this note)
- `pyproject.toml` (hatchling, stdlib-only, script `lemmata`), `README.md`, `src/lemmata/{__init__,__main__,cli,server,fixture_engine,engine_errors}.py`.
- `src/lemmata/web/`: `index.html`, `app.css` (DESIGN.md tokens verbatim), `app.js` (about 1,700 lines, no build), `vendor/` (Cytoscape.js 3.34.4 from the npm tarball, MIT, sha256 in `vendor/README.md`). No CDN, no web fonts.
- `tests/fixtures/api/*.json` + `tests/fixtures/files/**` (hand-built sample following data-model section 14; regenerate with `tests/fixtures/build_fixtures.py`), `tests/test_server.py` (10 tests: routes, guards, 64 KB cap, path confinement, export, banned wording).
- `docs/screens/*.png`: 24 screenshots at deviceScaleFactor 1 (1440x900), from the real engine on the generated sample (01-10, 15-22), the real `alarm-analyzer-eval` copy (11-14), the 300-node fixture (24), narrow notice (23).

## How to run
```
uv run --project app lemmata demo                  # real engine, builds ~/lemmata-demo
PYTHONPATH=app/src python3 -m lemmata demo         # zero-install
lemmata open <dir> | serve <dir> | scan <dir> | checkpoint <dir> --at code=<rev> --note "..."
lemmata demo --fixtures[=large]                    # UI on fixture data (no engine needed)
```
Verified: `uv run --project app lemmata --version`, `pip install -e app` in a clean venv, demo on the generated sample, `open` on a copy of `alarm-analyzer-eval` (242 nodes, 481 edges, scan 0.6 s, UI load 0.8 s, select 17 ms, 20 zoom/pan steps under 1 ms of script time).

## Real engine vs fixtures
Everything works against the real `Engine`: graph, lineage, alarms, analyzer, checkpoints, triage (persisted in `.lemmata/triage.json`), link approve/reject with alarm recompute, checks and side-by-side evidence, export, rescan, code-only repo. Fixtures are only for development; the low-confidence (`message_claims_no_change`) alarm row was seen only on the `large` fixture because the sample has no flagged commit.

## Walkthrough control names (demo-spec step to UI)
"Checkpoint panel" = top bar `Checkpoint: CP1 ▾` popover (note field, `Set checkpoint`, list). "Findings" = the `Checks` tab (designer's name). `Trace down` / `Trace up` buttons in the detail panel. `References` toggle. `Analyze` on each alarm group header. `Approve` / `Reject` in the `Links` tab. `Export HTML report` in the top bar. Triage buttons `✓✓ Reviewed`, `✕ Needs fixing`, `– Ignore`.

## Contract conflicts and decisions (data-model.md won)
1. **Layer order**: contract has runs at layer 5, code at 6; DESIGN/PM list code before runs. Bands follow the contract (Thesis, Questions, Sections, Paper items, Repo results, Runs, Code). References are a right-hand column behind the toggle.
2. **Trace direction**: demo-spec "trace down" (Table 2 to code) is the contract's upstream = DESIGN "Rests on" (blue, solid); "trace up" = "Supports" (orange, dashed). Buttons carry both words. DESIGN's glyph `▲ Rests on` points up although the thing rested on sits lower in the graph; a design question.
3. **No file-content route in the contract**, yet previews and evidence context need file lines. I added read-only `GET /api/file` (text lines) and `GET /api/raw` (png/jpg/svg) in `server.py`, confined to the repo roots from `/api/project` (no `.lemmata`, 1 MB cap). The export embeds the needed excerpts. Please bless or reject.
4. **Export** is built by `server.py` from the facade GETs plus precomputed analyses (up to 400) and file excerpts; `Engine.export_bundle()` is not used.
5. **Links**: no confidence on edges in the contract, so the confidence column and "AI suggestion" filter are omitted; filters are Proposed / Approved / Rejected / All. Approved shows a `✓ Approved` chip (not in DESIGN's word list).
6. **Timeline**: dragging handles and "Set as Now" are cut (ADR: no time travel). "Last known good" is set from a commit via `POST /api/checkpoints {at:{repo:rev}}`; the other repo then uses its working tree (explained in the confirm dialog). The `Set as Now` button is shown disabled with a reason.
7. **Picker**: one project per server (ADR), so the folder field is read-only with the `lemmata open` hint, "Use sample" is a hint to run `lemmata demo`, and scan progress is one request (steps shown as Done afterwards, not live).

## Known gaps (cut or not done)
- Graph nodes are canvas elements: arrow keys, outline and search give keyboard access, but nodes have no per-node ARIA labels.
- `Esc` does not cancel a running scan; no `Shift+click` band collapse hint beyond a tooltip; no `Space`/`A`/`D` row keys on Links; no `,` `.` timeline stepping.
- Dense history (113 commits) overlaps marks on the timeline; `Zoom to range` only works once a checkpoint exists.
- Auto-grouping: files are grouped by folder (top-level folder when a layer has over 40 nodes) and collapsed by default on big layers; groups are not nested.
- Contrast ratios from DESIGN.md were not re-measured with a tool.
- `app/uv.lock` was created by `uv run`; keep or delete.

## Open questions
- Keep the read-only `/api/file` and `/api/raw` extension (item 3), or move file reading into the engine facade?
- Should the real engine also return a confidence for proposed links?
- Is `Checks` (designer) or `Findings` (PM script) the tab name for the live demo?
