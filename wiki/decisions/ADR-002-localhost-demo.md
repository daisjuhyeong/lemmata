---
type: adr
owner_agent: cto
status: proposed
sources:
  - "founder decisions, 1st presentation, 2026-11-03 (relayed by the lead on 2026-11-04; no file in raw/ yet)"
  - "../product/demo-spec.md (PM, S02 stories and golden set)"
  - "../sprints/S02/S02-01-pipeline-eng.md, ../sprints/S02/S02-02-web-eng.md"
  - "local repo /home/claude/alarm-analyzer-eval @ baa9f7d: README.md, experiments/README.md, .gitignore; commit 9995dc8 (not in raw/)"
  - "https://docs.python.org/3/library/http.server.html (ThreadingHTTPServer)"
  - "https://git-scm.com/book/en/v2/Git-Internals-Git-Objects (blob ids are content hashes)"
  - "https://js.cytoscape.org/ (Cytoscape.js, MIT licence)"
  - "https://docs.openalex.org/ , https://www.crossref.org/documentation/retrieve-metadata/rest-api/"
last_reviewed: 2026-11-04
---
# ADR-002: Localhost demo for the 2nd presentation (local Python server + static UI + hub folder)

Status: **proposed** (Juhyeong approves). Supersedes: **nothing**. ADR-001 (MVP architecture) exists only on the Mac mini and is not in this clone; until it is reconciled, this ADR stands on its own and does not override ADR-001. Where the two conflict, Juhyeong decides and one of them is amended.

Companion pages: [demo architecture](../architecture/demo-architecture.md), [data model and API contract](../architecture/data-model.md).

## Context
- Founder decisions at the 1st presentation (2026-11-03) changed the product. It is now a researcher's guide ("use AI, don't depend on AI") that tracks paper, code and experiments as a **dependency graph over time**. Alarms are content-based and AI is used only on request. The product name is not chosen yet: "the product", package/CLI `rmap`.
- The 2nd presentation is the MVP demo. Juhyeong needs one command on his Mac that opens `http://localhost:<port>`, works offline, and survives a 5-minute live walkthrough ([demo-spec](../product/demo-spec.md)).
- A static single-HTML prototype exists (founder's figures, relayed by the lead; not re-measured by me): 279 nodes, 424 links, 113 commits on `alarm-analyzer-eval` plus his WWW'27 paper. Its staleness came from **commit times, not content**. Commit `9995dc8` changed 3 scripts, and its message says all nine committed single-panel PNGs are byte-identical (verified from `git show 9995dc8`), yet the prototype still flagged 7 nodes.
- Triage and link approval must persist, so a static HTML page alone is not enough: something has to write state.
- Constraints from the lead: code in `app/`; Python ≥ 3.10, standard library first; no Node/npm build; offline (no CDN); hub folder `.rmap/` inside the scanned project; staleness by content hash; reference lookup offline from a cache, `--online` optional; every finding carries evidence; two demo projects (synthetic sample, real `alarm-analyzer-eval`); deterministic analyzer with the "Ask Claude why" action stubbed.
- `CLAUDE.md` still says "Runtime: open-source Claude Code plugin" and lists the old MVP scope. `wiki/vision/vision.md` still describes an "AI pre-reviewer". Both predate the 2026-11-03 decisions (see Consequences).

## Options
### A. Runtime shape
| Option | For | Against |
|---|---|---|
| A1. Extend the static single-HTML prototype (regenerate per scan) | Already exists; zero server | Cannot persist triage or approvals without a server or manual file juggling; no rescan button |
| **A2. Local Python stdlib server (`ThreadingHTTPServer`) + plain HTML/JS UI + hub folder** | One process, no installs beyond Python and git; persistence through POST; the engine is reusable as the Tauri backend later | Hand-written HTTP routing; some security care needed for a local server |
| A3. Tauri Mac app now | The eventual delivery target | Needs a Rust toolchain and signing; too much for this deadline |
| A4. Claude Code plugin emitting an HTML report (the old CLAUDE.md runtime) | Matches the old plan | Read-only; puts AI at the centre, which contradicts "no AI per commit" |
| A5. FastAPI/Flask + React/Vite | Familiar | Third-party dependencies and an npm build, both banned by the constraints |

### B. Staleness signal
| Option | Against |
|---|---|
| B1. Commit timestamps (prototype) | Flags byte-identical files; this is the `9995dc8` problem |
| B2. File mtimes | Not stable across checkouts; non-deterministic for the sample |
| **B3. Content hashes** (git blob id for files; sha256 of normalised owned text for paper units) | Needs a per-commit replay to name the causing commit, but that is cheap with `git diff-tree` |

### C. Graph rendering
| Option | Against |
|---|---|
| **C1. Cytoscape.js, vendored single file (MIT), preset layout computed in our JS** | About 400 KB vendored file |
| C2. Hand-written SVG | Pan, zoom and hit-testing take hours we do not have |
| C3. D3 | More code than C1 for the same result |

## Decision
1. **Runtime A2.** `rmap` is a Python package with an `engine/` (pure functions over a project folder) and a thin `server.py` that binds **127.0.0.1 only** and serves `web/` plus a JSON API. One command: `uv run --project app rmap demo`, which builds the synthetic sample, scans it, serves it on port 8765 (or the next free port) and opens the browser. Zero-install fallback: `PYTHONPATH=app/src python3 -m rmap demo`.
2. **Hub folder** `.rmap/` at the project root holds `project.json` (manifest), the derived files `graph.json`, `events.json`, `findings.json` and `alarms.json`, the user-state files `checkpoints.json` and `triage.json` (node and finding triage, plus link decisions), and `cache/` (`refs.json`, `blobs/`). It writes its own `.gitignore` containing `*`, so the scanned repo's `git status` stays clean and the user's `.gitignore` is never edited. The tool writes nowhere else. Whether the hub should later be committed (Tauri plan) is a future ADR.
3. **Staleness B3** with these rules (normative text in [data-model §8](../architecture/data-model.md)):
   - A node is **changed** if its hash now differs from the active checkpoint's hash, or if the node is new.
   - A node is **downstream** if it depends, transitively, on a changed node through a *propagating* edge whose status is `detected` or `approved`.
   - Byte-identical content is never "changed", however many commits touched it. This covers edit-then-revert, regenerate-identical and comment-only paper edits.
   - The **cause** of a change is the first commit of the final run of commits in which the node differs from the checkpoint. Alarms are grouped by cause.
   - A commit whose message claims "no change" while content changed gets a `message_claims_no_change` flag with confidence `low`.
4. **Only dependency edges propagate**: `includes`, `generated_by`, `traces_to`, `produced_by`, `executes`, `reads`, `imports`, and approved `value_match`. Structural edges (`contains`, `answers`, `refs`, `cites`) are shown but do not propagate. Otherwise every edit would flag the whole paper. Proposed links (heuristics, later AI) are drawn dashed and propagate nothing until the author approves them.
5. **Identical outputs stay listed (safe default).** A produced file (`result`/`asset`) downstream of a change whose bytes equal the checkpoint is still listed, marked `output_identical: true` ("producer changed; output bytes unchanged — not regenerated, or regenerated identically"). Git cannot tell those two cases apart. Stopping propagation there would hide the sample's main story: config changed, `results/table2.csv` not regenerated, Table 2 out of date. Effect on `9995dc8`: the byte-identical PNGs are no longer reported as *changed*, and the commit is flagged. Whether its dependents still appear downstream depends on which detected edges reach them; QA measures this rather than us assuming it. Juhyeong decides whether to keep this default (question 1).
6. **Checks in scope** (8 check codes, covering the PM's F01–F10): `reference_unmatched`, `main_appendix_mismatch`, `uncited_reference`, `unreferenced_float`, `undefined_ref`, `undefined_cite`, `untraced_number`, `figure_without_provenance`. Every finding carries at least one `{repo, path, line, text}` evidence item; any finding without one is dropped. Wording is neutral ("could not be matched", "differs", "not traced").
7. **References offline-first.** F01 fires only from a *recorded* failed lookup in `.rmap/cache/refs.json`. Entries absent from the cache count as "not checked", never as findings. `--online` (opt-in, per run) queries OpenAlex, then Crossref, and writes the results to the cache. The sample ships its own cache.
8. **Analyzer is deterministic**: the edge chain (BFS over propagating edges), a unified diff of checkpoint vs now from the checkpoint blob store, and a template sentence. "Ask Claude why" is a visible button that returns HTTP 501 with the label "not available in this demo". No model call anywhere; no network unless `--online`.
9. **Rendering C1**: Cytoscape.js vendored under `web/vendor/` with its licence and version noted. Layered top-down layout by `layer`. References are hidden by default and toggled as a side column.
10. **Provenance sources** (all `detected`): LaTeX (`\includegraphics`, `\input` inside floats, `\ref`/`\cite` families), comment markers `% generated-by:` / `% source:`, run records `runs/<id>.json`, Python imports, literal output paths in write calls, and README tables mapping paper items to scripts (as in `alarm-analyzer-eval/experiments/README.md`). The scanner works on a code-only project; paper checks then report `not_applicable`.
11. **Export**: `GET /api/export` returns one self-contained HTML file (inlined JS, CSS, vendor library and a JSON snapshot) that opens offline, read-only. This is the "local HTML report" and the demo fallback.

## Explicit scope cuts (not in the demo)
- Notation lint, citation-claim support, related-work coverage, paper aesthetics, paper ↔ GitHub smoke tests (later roadmap items).
- Any AI call (the "Ask Claude why" button is a stub), Tauri, Overleaf sync or API (the user unzips manually), PDF parsing, LaTeX macro expansion (`\newcommand` labels and numbers are missed), `.ipynb` content parsing (notebooks are hashed as files only).
- Numbers as graph nodes. `untraced_number` is a finding on the containing section or table; trace paths are shown from the table node. This changes the wording of PM story US-11.4.
- Value-match proposals for numbers (only hyperparameter-name proposals exist), merging README "Fig. N" items with real paper figures, rename detection (a rename is a removal plus an addition), side branches (first-parent history only), activating an older checkpoint (list only), file watching (manual Rescan), time travel (viewing the graph at a past commit), multiple projects per server, auth, multi-user.
- Automatic `\label` numbering is approximate (simple counters); numbers shown are for orientation, not citation.

**Cut order if the build runs late** (cut first → last): online lookup → literal write-path detection → timeline strip → README provenance (the real-repo demo then shows imports and alarms only) → export (fallback becomes screenshots). The sample walkthrough P0 (graph, alarms, analyzer, triage, approvals, 8 checks) is not cut; if even that slips, the PM walkthrough loses its "Approve PL2" step before anything else.

## Consequences
- Positive: one process, no third-party Python dependencies; same engine for CLI, server, tests and a future Tauri shell; alarms are reproducible and explainable from content alone; triage and approvals survive restarts; the demo is deterministic (fixed commit dates, fixed identity, sorted outputs).
- Negative: regex-level LaTeX parsing will miss macro-heavy papers; the `output_identical` rule keeps some noise on real repos (triage absorbs it); the vendored library is a third-party file in our repo; a localhost server needs Host/Origin checks (in the contract).
- Privacy: everything stays on the machine except opt-in `--online`, which sends bib titles and DOIs to OpenAlex and Crossref (CLAUDE.md "use of user data": Juhyeong approves).
- Follow-ups needing Juhyeong (I cannot edit these files): `CLAUDE.md` Scope and Runtime lines and `wiki/vision/vision.md` predate this decision; ADR-001 needs reconciling; a later ADR covers committing the hub folder (Tauri).
- Parallel work: pipeline-eng owns `engine/` and `samples/`; web-eng owns `server.py`, `cli.py` and `web/`. The only seam is the `Engine` facade and the JSON shapes in data-model.md. A schema change needs a data-model.md edit by the CTO and a note to QA.

## Open questions for Juhyeong
1. Keep listing byte-identical outputs downstream (`output_identical: true`, recommended), or stop propagation at them (quieter on `9995dc8`, but hides "results not regenerated")?
2. Layer order: the founder's order puts code above runs; the dependency order is result → run → code. I propose runs at layer 5 and code at layer 6 (a one-line UI constant).
3. The demo command (`uv run --project app rmap demo`), sample location `~/rmap-demo`, port 8765. `uv` may need network once to fetch Python ≥ 3.10 and the build backend.
4. Real-repo demo state: HEAD `baa9f7d` is the code-only release tree (outputs removed). Comparing a 9/17 checkpoint with HEAD shows mass removals; a separate checkout at `308dab9` gives the prototype-comparable view.
5. Approve `--online` reference lookup as a use of the author's own data, and run it once before the demo for the real paper.

## Approved by
(pending — Juhyeong, date)
