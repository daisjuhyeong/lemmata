---
type: handoff
owner_agent: pipeline-eng
status: draft
sources:
  - "../../architecture/data-model.md (contract)"
  - "../../architecture/demo-architecture.md"
  - "../../decisions/ADR-002-localhost-demo.md"
  - "../../product/demo-spec.md (golden set)"
  - "S02-01-pipeline-eng.md (task card)"
  - "local repo /home/claude/alarm-analyzer-eval @ baa9f7d (not in raw/); scan numbers below measured in this session"
last_reviewed: 2026-11-04
---
# Handoff: S02-01 engine, sample generator, tests (pipeline-eng)

## What changed
- `app/src/rmap/engine/`: `api.py` (facade, data-model §13 exactly), `errors.py`, `manifest.py`, `store.py`, `tree.py`, `classify.py`, `latex.py`, `bib.py`, `code.py`, `graph.py`, `history.py`, `alarms.py`, `analyze.py`, `checks.py`, `refs.py`, `triage.py`. Stdlib plus the `git` binary only; about 3,500 lines.
- `app/samples/make_sample.py`: deterministic two-repo sample (paper P1-P3, code K1-K5), fixed identity/dates, isolated git config, tags `cp1`, writes `.rmap/project.json` (with `seed_checkpoint`), `.rmap/cache/refs.json` and a `.rmap-sample` marker. Writes only inside its target dir.
- `app/tests/test_engine.py`: 23 tests (golden set, evidence-vs-source lines, approvals, checkpoints, triage persistence + outdated, hash/revert, determinism across two builds, socket-blocked full pipeline, code-only mode, wording scan, real-repo smoke).
- Did not touch: `pyproject.toml`, `__init__.py`, `cli.py`, `server.py`, `web/`, `tests/fixtures/`, `wiki/index.md`, `wiki/log.md`. No git commands run in the repo.

## How to run
```
python3 app/samples/make_sample.py /tmp/rmap-sample
PYTHONPATH=app/src python3 -m rmap scan /tmp/rmap-sample      # web-eng CLI
PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_engine*.py'   # 23 tests, about 4 s
PYTHONPATH=app/src python3 -c "from rmap.engine.api import Engine; e=Engine('/tmp/rmap-sample'); e.scan(); print(e.alarms())"
```

## Golden set: expected vs actual (fresh sample, all pass)
| Item | Expected | Actual |
|---|---|---|
| F01 | `reference_unmatched/smith2021ghost`, refs.bib | refs.bib:21 |
| F02 | learning rate 3e-4 vs 1e-3 | main.tex:33 / appendix.tex:7 |
| F03 | batch size 64 vs 128 | main.tex:33 / appendix.tex:8 |
| F04 | `uncited_reference/unused2019` | refs.bib:26 |
| F05 | `unreferenced_float/fig:arch` | main.tex:29 |
| F06 | `unreferenced_float/tab:ablation` | main.tex:77 |
| F07 | `undefined_ref/fig:missing` | main.tex:61 |
| F08 | `undefined_cite/nobody2020` | main.tex:21 |
| F09 | `untraced_number/tex:sec:results#92.4` | main.tex:48 |
| F10 | `figure_without_provenance/tex:fig:qual` | main.tex:72 |
| PL1, PL2 | exactly 2 proposed, non-propagating | both present, `propagates: false` |
| A1 (K3, 460abec) | changed config; downstream run, table2.csv (`output_identical: true`), Table 2 | exact |
| A2 (P3) | changed `tex:app:hparams`; 0 downstream | exact |
| eval.py K4+K5 | nothing raised | events list it (changed_nodes), alarms do not |
| After approving PL2 / PL1 | A1 downstream 4 / 5 nodes | 4 / 5 |
| New checkpoint | 0 alarms, findings unchanged | cp2, 0 groups, findings equal |
Line numbers are generated from the frozen files; QA should record them from the committed sample. Commit hashes are stable (code HEAD `17acc92b...`, paper HEAD `02c76768...` on this machine/git 2.43; the determinism test compares two builds).

## Real-repo scan (`alarm-analyzer-eval` @ baa9f7d, code-only)
242 nodes (203 code, 16 README items, 13 doc, 8 data, 2 config), 481 edges (448 imports, 29 generated_by from the README table, 4 produced_by from write calls), 113 events (first-parent; `git log | wc` shows 114 commits), scan 0.57 s (target < 10 s). README items are exactly Fig. 1, 3-10, Tables 1, 2, 3, 5, App. B, D.1, F (16). All 8 checks report `not_applicable` ("no paper repo"). `git status` of the repo stays clean (hub is self-ignored). The message-flag fires on commits such as a30f1d0 ("byte-identical"); the phrase list also matches "no-op" often (per contract), which may be noisy.

## Contract conflicts and judgment calls
1. **Run record example (§11.1) vs golden set**: the example lists `results/metrics.json` as a run output, which would add a 4th downstream node to A1 (golden says exactly 3). The sample's run record lists only `results/table2.csv`; `metrics.json` is an orphan result (and `eval.py`'s write target).
2. **Table numbering**: demo-spec calls `tab:main` "Table 2". The sample therefore has an extra labelled `tab:data` (Table 1, integers only, referenced) before it, and `tab:ablation` is Table 3.
3. **Finding order/numbering**: data-model §6.1 orders by check then id, so `batch_size` (F03) lists before `learning_rate` (F02). Ids are stable; display numbers F01-F10 are a PM label, not an engine field.
4. **Analyzer diff example** shows `@@ -2 +2 @@` (no context) while the text says 2 lines of context; I follow the text (`@@ -1,4 +1,4 @@`).
5. **Checkpoint node entries** carry an extra `blob` field (hex of the containing file's git blob, used for diffs of paper units). Additive; readers ignore unknown fields.
6. **Hyperparameter alias scan** ignores `\begin{tabular}{...}` column specs, otherwise a `{lr}` spec counts as a "learning rate" mention (a real-paper false positive; would break golden constraint (b)).
7. **Triage `outdated`** follows the letter of §10 (state != hash match => `unreviewed` + `outdated: true`), including for an explicit `unreviewed` entry.
8. `graph.json` has an extra top-level `warnings` list (same shape as the project status warnings).
9. `create_checkpoint` runs a fresh scan first so "from the working tree" is current.
10. demo-spec F-table says "Section 4" for sec:setup; numbering is approximate (§4 holds because Introduction, Related Work, Method precede it).

## Known gaps
- `--online` lookup (OpenAlex then Crossref) is implemented in `refs.py` but **untested** (no network in the sandbox). Failures are recorded as `error`, never `not_found`.
- No timeline/time-travel; run events carry `changed_nodes` only for outputs differing from the checkpoint.
- LaTeX: regex-level; macros, `\newcommand` labels, `\subimport`, `.ipynb` content not parsed. `value_match` proposals exist for hyperparameter names only.
- TOML configs need Python >= 3.11 (`tomllib`); skipped on 3.10.
- Replay is first-parent only; a checkpoint rev off the first-parent line yields a `diverged` event.
- Not tested on Python 3.10 or macOS (only 3.13 / Linux here).
- Stray `__pycache__` dirs under `app/` should be gitignored by the lead.

## Open questions
- Keep `output_identical` listing (ADR-002 Q1)? Implemented as specified; on `9995dc8`-style cases QA should measure the downstream list.
- Should `no-op` stay in the no-change phrase list given its hit rate on the real repo?

## Log line (for lead)
`2026-11-04 | pipeline-eng | build | app/src/rmap/engine/*, app/samples/make_sample.py, app/tests/test_engine.py, wiki/sprints/S02/handoff-pipeline-eng.md | S02-01 engine + sample + tests; golden set F01-F10, A1/A2 pass; real-repo scan 0.57 s; --online untested`
