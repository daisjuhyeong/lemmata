---
type: architecture
owner_agent: cto
status: proposed
sources:
  - "../decisions/ADR-002-localhost-demo.md"
  - "../product/demo-spec.md (golden set, stories US-01..US-14)"
  - "founder decisions, 1st presentation, 2026-11-03 (relayed by the lead; no file in raw/ yet)"
  - "local repo /home/claude/alarm-analyzer-eval @ baa9f7d: experiments/README.md (provenance table format; not in raw/)"
  - "https://git-scm.com/book/en/v2/Git-Internals-Git-Objects (blob id = sha1 of 'blob <len>\\0' + bytes)"
  - "https://docs.python.org/3/library/http.server.html"
last_reviewed: 2026-11-04
---
# Data model and API contract (S02 localhost demo)

**This is the contract two engineers build against in parallel.** pipeline-eng produces these shapes (engine, hub files); web-eng consumes them (server, UI). Change it only through the CTO, and tell QA, because `app/tests/golden.json` depends on ids. Placeholders: package/CLI `rmap`, schema prefix `rmap.` (the lead renames both). Architecture: [demo-architecture](demo-architecture.md). Decision: [ADR-002](../decisions/ADR-002-localhost-demo.md).

Example values below use the synthetic sample. Commit SHAs and hashes are illustrative.

## 0. Conventions (apply everywhere)
- JSON is UTF-8, written with `ensure_ascii=False` and `indent=1`. Readers ignore unknown fields. Every hub file has a `"schema": "rmap.<thing>/1"` field; a reader refuses an unknown major version.
- **Times**: ISO 8601 with offset, seconds precision (`2026-10-02T10:00:00+09:00`). Commit times use the committer date (`%cI`).
- **Paths**: repo-relative POSIX (`configs/default.yaml`), never absolute, except `abs_path` fields in `/api/project`.
- **Repo ids**: `^[a-z][a-z0-9_-]{0,15}$`, e.g. `paper` and `code`.
- **Ids are opaque strings.** Clients never parse them and always URL-encode them in query strings. Uniqueness comes from how ids are built (formats below).
- **Hashes** are strings `<algo>:<hex>`, compared for equality only:
  - `blob:<40 hex>`: git blob id of the raw file bytes (sha1 of `"blob <len>\0" + bytes`). Computed in Python for working-tree and non-git files, and read from git (`ls-tree` / `diff-tree --raw`) for commits.
  - `sha256:<64 hex>`: derived nodes (paper units, references, README items) over normalised text (see §3.3).
- **Line numbers** are 1-based. Every `loc`/evidence `line` is ≥ 1, or `null` for a whole file.
- **Determinism**: lists are sorted as stated per type. Volatile fields (`scanned_at`, `computed_at`, `exported_at`, and `created_at` of non-seeded checkpoints) are excluded from golden comparison.
- **Evidence object** (used by findings and edges):
```json
{"repo": "paper", "path": "main.tex", "line": 57, "text": "We train with a learning rate of $3\\times10^{-4}$ and batch size 64.", "role": "main", "page": null}
```
`text` is the exact source line, right-stripped and truncated to 300 chars. `role` is a short string listed per check/edge kind. `page` is always `null` in the demo (no PDF).

## 1. Hub folder `<project_root>/.rmap/`
| File | Kind | Written by | Notes |
|---|---|---|---|
| `.gitignore` | fixed | engine | content `*\n` |
| `project.json` | user/manifest | `rmap open`, `make_sample.py` | §2 |
| `graph.json` | derived | scan | §3, §4 (edge `status` already merged with link decisions) |
| `events.json` | derived | scan | §5 |
| `findings.json` | derived | scan | §6 |
| `alarms.json` | derived | scan, checkpoint, link decision | §8 |
| `checkpoints.json` | user state | checkpoint | §7 |
| `triage.json` | user state | triage, link decision | §10 |
| `cache/refs.json` | cache | `make_sample.py`, `--online` scan | §6.2 |
| `cache/blobs/<hex>` | cache | checkpoint | raw bytes of text files ≤ 1 MB at checkpoint time, named by blob hex; used for diffs |

Writes are atomic (`<file>.tmp` then `os.replace`). Scans skip `.rmap/` and never write outside it. Deleting `checkpoints.json` and `triage.json` resets user state; the next scan re-seeds the checkpoint from `seed_checkpoint` if present.

## 2. Project manifest `project.json`
```json
{
 "schema": "rmap.project/1",
 "name": "Sample: tiny transformer",
 "repos": [
  {"id": "paper", "role": "paper", "path": "paper", "main_tex": "main.tex", "exclude": []},
  {"id": "code",  "role": "code",  "path": "code",  "exclude": []}
 ],
 "seed_checkpoint": {"id": "cp1", "note": "CP1: draft v2 validated", "created_at": "2026-10-01T18:00:00+09:00", "at": {"paper": "cp1", "code": "cp1"}}
}
```
- `role`: `paper` | `code` (at most one `paper` repo in the demo). `path` is relative to the project root or absolute; `"."` means the project root itself (real-repo case).
- `main_tex` is optional. Auto-detection: the `.tex` file with both `\documentclass` and `\begin{document}`; prefer `main.tex`, else the first alphabetically.
- `exclude`: optional list of glob patterns (`fnmatch`, repo-relative), e.g. `["models/**"]`.
- `seed_checkpoint` is optional (the sample uses it). `at` values are any git rev (tags `cp1` here). It is used once, only when `checkpoints.json` does not exist.
- Code-only real repo: `{"schema":"rmap.project/1","name":"alarm-analyzer-eval","repos":[{"id":"code","role":"code","path":"."}]}`. Adding the paper later appends `{"id":"paper","role":"paper","path":"/Users/.../www27-paper"}`.

## 3. Nodes
### 3.1 Shape
```json
{
 "id": "tex:tab:main",
 "kind": "table",
 "layer": 3,
 "repo": "paper",
 "name": "Table 2",
 "detail": "Main results on the benchmark",
 "loc": {"path": "main.tex", "line": 88, "end_line": 101},
 "hash": "sha256:5f2c0d9e7b1a4c3e8d6f0a2b4c6d8e0f1a3b5c7d9e1f3a5b7c9d1e3f5a7b9c1d",
 "attrs": {"tex_label": "tab:main", "number": "2", "in_appendix": false, "caption": "Main results on the benchmark"}
}
```
`name` is a short display label. `detail` is a caption, title or command (≤ 120 chars, may be `""`). `loc.line`/`end_line` are `null` for whole-file nodes. `attrs` holds per-kind optional fields (§3.2). Order in `graph.nodes`: by `layer` (references last), then `id`.

### 3.2 Kinds, layers, id formats
| kind | layer | id format | from | attrs (optional) |
|---|---|---|---|---|
| `thesis` | 0 | `thesis` | `abstract` environment | `text` (≤ 200 chars) |
| `rq` | 1 | `rq:<RQn>` e.g. `rq:RQ1` | each distinct `RQ\s?\d+` token; loc = first occurrence | `text` |
| `section` | 2 | `tex:<label>` or `tex:section@<slug>` (`~2`, `~3` for duplicate slugs) | `\section`, `\subsection` (and starred) | `tex_label`, `level` (1, 2), `number` (`"4"`, `"B"`, `"B.1"`, null), `in_appendix`, `title` |
| `figure` | 3 | `tex:<label>` or `tex:figure@<path>#<n>` | `figure`, `figure*` | `tex_label`, `number`, `in_appendix`, `caption`, `manual` (bool), `assets` (paths) |
| `table` | 3 | `tex:<label>` or `tex:table@<path>#<n>` | `table`, `table*` | as figure |
| `equation` | 3 | `tex:<label>` | labelled `equation`/`align`/`gather`/`multline` | `tex_label`, `number` |
| `item` | 3 | `item:<repo>/<slug>` e.g. `item:code/fig-5` | README provenance row (code side; paper placeholder) | `paper_ref` (`"Fig. 5"`), `source_row` |
| `asset` | 4 | `file:<repo>/<path>` | `.png .jpg .jpeg .pdf .svg .eps`, and files `\input` inside a float | `size`, `binary`, `ext` |
| `result` | 4 | `file:<repo>/<path>` | data files under an output dir, or listed as a run output / write target | `size`, `binary`, `ext` |
| `run` | 5 | `run:<repo>/<run_id>` | run record `runs/<run_id>.json` (§11.1) | `command`, `started_at` |
| `code` | 6 | `file:<repo>/<path>` | `.py .sh .ipynb .R .jl .m` | `size`, `ext` |
| `config` | 6 | `file:<repo>/<path>` | `.yaml .yml .toml .ini .cfg`, and `.json` under a dir named `config*`/`conf*` | `size`, `ext` |
| `data` | 6 | `file:<repo>/<path>` | other `.csv .tsv .json .jsonl .txt .npz .npy .pkl .gz .parquet` | `size`, `binary`, `ext` |
| `doc` | 6 | `file:<repo>/<path>` | `.md .rst` not under an output dir | `size`, `ext` |
| `reference` | `null` | `ref:<bibkey>` | `.bib` entries | `bib_key`, `title`, `year`, `doi`, `lookup` (`matched`, `not_found`, `unchecked`, `error`) |

- **Output dir**: any path segment in `results, result, outputs, output, out, figures, figs, plots, tables, logs`.
- **Files that are not nodes**: `.tex .bib .cls .sty .bst` (the paper is represented by its units); hidden paths; `.rmap/`; files > 50 MB; `runs/*.json` run records (they become `run` nodes); anything matched by `exclude`; extensions not listed above. For git repos the file set is `git ls-files` plus untracked, non-ignored files (`--others --exclude-standard`). Non-git repos are walked.
- **Slug**: lowercase, non-alphanumerics collapsed to `-`, trimmed (`"Experimental Setup"` → `experimental-setup`). `<n>` in unlabelled float ids is the 1-based ordinal of that environment kind within its file.
- **Display `name`**: `Thesis`, `RQ1`, `§4 Experimental setup`, `App. B Hyperparameters`, `Fig. 1`, `Table 2`, `Eq. 3`, `Fig. 5 (README)`, the repo-relative path for files, `run train_main`, `[vaswani2017attention]`.
- **Numbering** (approximate): `\section` counter 1..n in the main part and A, B, … after `\appendix`. `figure`/`figure*` share one counter, likewise `table`/`table*`, with no reset at `\appendix`.
- **Unit ownership**: every line of the flattened paper (after following `\input`/`\include` of `.tex` files *outside* floats) belongs to exactly one innermost unit: float or labelled display equation > subsection > section > thesis (abstract). A `\label` belongs to the unit it sits in. `loc` is the unit's first line (the `\section`/`\begin` line); `end_line` is its last owned line in the same file.

### 3.3 Hash rules
- File-backed kinds (`asset result code config data doc`): `blob:` of the raw bytes. `run`: `blob:` of its record file.
- `thesis`, `rq`, `section`, `figure`, `table`, `equation`: `sha256:` of the unit's **owned lines**, joined with `\n`, after (1) removing LaTeX comments (unescaped `%` to end of line), (2) collapsing whitespace runs to one space, (3) dropping empty lines. Comment-only edits therefore never change a paper node.
- `rq`: hash of the normalised first-occurrence line. `reference`: `sha256:` of the entry text with whitespace collapsed. `item`: `sha256:` of the README row text.

## 4. Edges
### 4.1 Shape
Direction is fixed: **`from` depends on `to`**. Reading top-down follows edges `from → to`. Staleness travels against the arrow.
```json
{
 "id": "tex:tab:main|traces_to|file:code/results/table2.csv",
 "from": "tex:tab:main",
 "to": "file:code/results/table2.csv",
 "kind": "traces_to",
 "status": "detected",
 "propagates": true,
 "evidence": [{"repo": "paper", "path": "main.tex", "line": 89, "text": "% source: code:results/table2.csv", "role": "marker", "page": null}],
 "reason": null
}
```
- `id` = `<from>|<kind>|<to>`. Duplicate detections merge into one edge with combined evidence.
- `status`: `detected` (explicit in source), `proposed` (heuristic, awaiting the author), `approved`, `rejected` (author decision from `triage.json`; a rejected edge stays in `graph.json` so it is not re-proposed, and the UI hides it).
- `propagates` (effective) = the kind propagates **and** `status` ∈ {`detected`, `approved`}. The UI draws `proposed` edges dashed.
- `reason`: human-readable string for `proposed`/`approved` value matches, else `null`.
- Order in `graph.edges`: by `id`.

### 4.2 Edge kinds
| kind | from → to | propagates | detected from | evidence role |
|---|---|---|---|---|
| `contains` | thesis→rq, thesis→level-1 section, section→subsection, section→float/equation | no | structure | `structure` (child loc) |
| `answers` | rq → section whose owned text mentions it | no | text | `mention` |
| `refs` | unit → unit owning the label | no | `\ref \cref \Cref \autoref \eqref \pageref` (comma lists) | `ref` |
| `cites` | unit → reference | no | `\cite \citep \citet \citeauthor \citeyear \nocite` (comma lists) | `cite` |
| `includes` | figure/table/section → asset | yes | `\includegraphics{…}`; `\input{…}` inside a float | `include` |
| `generated_by` | figure/table/item → code | yes | marker `% generated-by: <ref>`; README provenance row | `marker`, `readme` |
| `traces_to` | unit → result/data/doc | yes | marker `% source: <ref>` | `marker` |
| `produced_by` | result/asset → run or code | yes | run record `outputs`; literal path in a write call in Python | `run_record`, `write_call` |
| `executes` | run → code | yes | run record `script` | `run_record` |
| `reads` | run → config/data | yes | run record `inputs` | `run_record` |
| `imports` | code → code | yes | Python `import`/`from … import`, resolved to repo files | `import` |
| `value_match` | section/table → config | yes, once approved | hyperparameter-name match (§11.3); always created `proposed` | `main`/`appendix` + `config` |

## 5. Events (`events.json`)
```json
{
 "schema": "rmap.events/1",
 "events": [
  {
   "id": "ev:commit:code:9f1c2e7a4b3d",
   "kind": "commit",
   "repo": "code",
   "rev": "9f1c2e7a4b3d5f6a7b8c9d0e1f2a3b4c5d6e7f80",
   "short": "9f1c2e7",
   "time": "2026-10-03T10:00:00+09:00",
   "subject": "change learning rate 3e-4 to 1e-3",
   "files": [{"path": "configs/default.yaml", "status": "M"}],
   "at_checkpoint": false,
   "after_checkpoint": true,
   "changed_nodes": ["file:code/configs/default.yaml"],
   "flags": []
  }
 ]
}
```
- `kind`: `commit` (first-parent history of each git repo, all commits) | `run` (from run records; `time` = `started_at`, `files` = outputs) | `worktree` (uncommitted changes, `time` = scan time, at most one per repo) | `snapshot` (non-git repo differs from the checkpoint) | `diverged` (the checkpoint rev is not an ancestor of HEAD; all that repo's changes are grouped here).
- Id formats: `ev:commit:<repo>:<sha12>`, `ev:run:<repo>/<run_id>`, `ev:worktree:<repo>`, `ev:snapshot:<repo>`, `ev:diverged:<repo>`.
- `files[].status`: `A M D R T` (from `git diff-tree --raw -r --no-renames`, so `R` does not occur in the demo).
- `changed_nodes`: node ids whose hash changed in this event versus its predecessor; computed only for `after_checkpoint` events, otherwise `null`.
- `flags`: `[{"code": "message_claims_no_change", "confidence": "low", "phrase": "byte-identical", "text": "Message says \"byte-identical\"; content changed in 3 files."}]`. The flag is set when the full message (subject + body) matches the no-change phrase list (case-insensitive: `no (functional |behavio(u)?r(al)? |output |numerical |result )?changes?`, `outputs? (are |is )?unchanged`, `nothing (moved|changed)`, `byte[- ]identical`, `identical (outputs?|results)`, `refactor(ing)? only`, `cosmetic`, `comments? only`, `no-op`) **and** content changed. Content changed means `changed_nodes` is non-empty, or, when it is `null`, `files` is non-empty.
- Order: by `time`, then `id`.

## 6. Findings (`findings.json`)
### 6.1 Shape
```json
{
 "schema": "rmap.findings/1",
 "checks": [
  {"check": "reference_unmatched", "title": "Reference could not be matched", "status": "ran", "count": 1, "note": "offline cache: 5 matched, 1 could not be matched, 0 not checked"},
  {"check": "untraced_number", "title": "Number not traced to a result file", "status": "ran", "count": 1, "note": ""}
 ],
 "findings": [
  {
   "id": "main_appendix_mismatch/learning_rate",
   "check": "main_appendix_mismatch",
   "severity": "warning",
   "title": "Main text and appendix differ",
   "message": "Learning rate differs between the main text (3e-4, main.tex:57) and the appendix (1e-3, appendix.tex:14).",
   "nodes": ["tex:sec:setup", "tex:app:hparams"],
   "evidence": [
    {"repo": "paper", "path": "main.tex", "line": 57, "text": "We train with a learning rate of $3\\times10^{-4}$ and batch size 64.", "role": "main", "page": null},
    {"repo": "paper", "path": "appendix.tex", "line": 14, "text": "Learning rate & $1\\times10^{-3}$ \\\\", "role": "appendix", "page": null}
   ],
   "details": {"name": "learning_rate", "main_value": "3e-4", "appendix_value": "1e-3"},
   "fingerprint": "sha256:0c4e…"
  }
 ]
}
```
- `checks[].status`: `ran` | `not_applicable` (with `note`, e.g. `"no paper repo"` or `"no \\appendix found"`). All 8 checks are always listed, in the table order below.
- `severity`: `warning` | `info`. `fingerprint` = `sha256:` over `check`, `id`, and each evidence `text`; triage uses it to detect that a finding changed.
- **Invariant**: `evidence` has ≥ 1 item with `path` and `line` ≥ 1, otherwise the finding is not emitted (a scan warning is logged instead).
- Order: by check order, then `id`.

### 6.2 Checks in scope
| check | severity | id format | evidence roles | golden (demo-spec) |
|---|---|---|---|---|
| `reference_unmatched` | warning | `reference_unmatched/<bibkey>` | `bib_entry` | F01 |
| `main_appendix_mismatch` | warning | `main_appendix_mismatch/<canonical name>` | `main`, `appendix` | F02, F03 |
| `uncited_reference` | info | `uncited_reference/<bibkey>` | `bib_entry` | F04 |
| `unreferenced_float` | info | `unreferenced_float/<label or node id>` | `label` (or `begin` if unlabelled) | F05, F06 |
| `undefined_ref` | warning | `undefined_ref/<label>` | `ref` (one per use) | F07 |
| `undefined_cite` | warning | `undefined_cite/<key>` | `cite` (one per use) | F08 |
| `untraced_number` | info | `untraced_number/<node id>#<value>` | `number` | F09 |
| `figure_without_provenance` | info | `figure_without_provenance/<node id>` | `label` (or `begin`) | F10 |

Rules (the minimum pipeline-eng must implement; anything smarter is out of scope):
- `reference_unmatched`: the entry's cache record (key = normalised title: lowercase alphanumerics only; DOI lowercased if present) has `status: "not_found"`. Missing record → counted as "not checked", **no finding**. `details.lookup` = the cache record. Message: `Reference could not be matched: "<title>" (<key>) was not found in OpenAlex or Crossref (lookup <date>).`
- Cache `cache/refs.json`: `{"schema":"rmap.refs/1","entries":{"<norm title or doi:…>":{"status":"matched|not_found|error","source":"openalex|crossref|seed","checked_at":"…","match":{"title":"…","year":2017,"doi":"…","url":"…"}|null}}}`. Online match: difflib ratio of normalised titles ≥ 0.9, and |year difference| ≤ 1 when both years exist. Query OpenAlex first, Crossref second; 10 s timeout; sequential requests.
- `main_appendix_mismatch`: canonical names and aliases are `learning_rate` (learning rate, lr), `batch_size` (batch size), `epochs` (epochs), `weight_decay` (weight decay), `dropout` (dropout), `warmup_steps` (warmup steps), `optimizer` (optimizer; values Adam, AdamW, SGD, RMSprop, Adagrad), `seed` (seed). A value is the first number or optimizer word after the alias on the same line (prose or a `&` table row). Normalise `3\times10^{-4}`, `3e-4`, `3.0e-4` and `0.0003` to a float; strings are compared case-insensitively. Main = before `\appendix`, appendix = after. If a name occurs in both parts, compare the first occurrence in each; differ → one finding.
- `uncited_reference`: a bib key never cited; `\nocite{*}` disables the check (`note`).
- `unreferenced_float`: a figure or table whose label no `\ref`-family command targets, or a float with no `\label` at all.
- `undefined_ref` / `undefined_cite`: target label or key not defined (commented-out lines ignored).
- `untraced_number`: candidates are plain decimals `\d+\.\d+` (optionally followed by `\%`) in prose and table rows of the paper. Excluded: display math, command arguments (`\ref{}`, `\cite{}`, `\label{}`, `\includegraphics[...]`, lengths such as `0.8\linewidth`), and lines that carry a hyperparameter alias. A value v with d decimals is **traced** if some number x in a text file of kind `result`/`data`/`doc`/`config` (≤ 2 MB, any repo) satisfies `round(x, d) == v` or `round(100*x, d) == v`. Untraced → finding on the owning unit.
- `figure_without_provenance`: a figure with no propagating path to a `code` or `run` node, and not marked `% generated-by: manual`.
- Wording ban (QA scans the templates): never `wrong`, `fake`, `fabricated`, `mistake`, `error by`, `cheat`.

## 7. Checkpoints (`checkpoints.json`)
```json
{
 "schema": "rmap.checkpoints/1",
 "active": "cp1",
 "checkpoints": [
  {
   "id": "cp1",
   "created_at": "2026-10-01T18:00:00+09:00",
   "note": "CP1: draft v2 validated",
   "repos": {"paper": {"rev": "4a1b…40hex", "dirty": false}, "code": {"rev": "7c2d…40hex", "dirty": false}},
   "nodes": {
    "file:code/configs/default.yaml": {"hash": "blob:1d3e…", "kind": "config", "repo": "code", "path": "configs/default.yaml", "name": "configs/default.yaml"},
    "tex:app:hparams": {"hash": "sha256:9b0a…", "kind": "section", "repo": "paper", "path": "appendix.tex", "name": "App. B Hyperparameters"}
   }
  }
 ]
}
```
- Ids are `cp1`, `cp2`, … (next integer). `active` is always the newest; older checkpoints are kept and listed.
- Creation: from the working tree by default (`rev` = HEAD, `dirty` = whether the worktree differs from HEAD; `rev: null` for non-git). With `at: {"code": "<rev>"}`, the repos named are hashed at that rev via git (400 for non-git or invalid revs); the others use the working tree. All text files ≤ 1 MB of the snapshot are copied to `cache/blobs/` for the analyzer diff.
- **Summary** form (used by the API): every field except `nodes`, plus `"node_count": 312` and `"active": true|false`.

## 8. Alarms (`alarms.json`) — normative algorithm
```json
{
 "schema": "rmap.alarms/1",
 "computed_at": "2026-11-04T15:00:00+09:00",
 "checkpoint": {"id": "cp1", "created_at": "2026-10-01T18:00:00+09:00", "note": "CP1: draft v2 validated"},
 "excluded_repos": [],
 "groups": [
  {
   "id": "ev:commit:code:9f1c2e7a4b3d",
   "display": "A1",
   "cause": {"event_id": "ev:commit:code:9f1c2e7a4b3d", "kind": "commit", "repo": "code", "rev": "9f1c2e7a…", "short": "9f1c2e7", "time": "2026-10-03T10:00:00+09:00", "subject": "change learning rate 3e-4 to 1e-3", "files": ["configs/default.yaml"]},
   "changed": [{"node_id": "file:code/configs/default.yaml", "change": "content_changed", "hash_checkpoint": "blob:1d3e…", "hash_now": "blob:8f0b…", "also_changed_in": []}],
   "removed": [],
   "downstream": [
    {"node_id": "run:code/train_main", "depth": 1, "via": "run:code/train_main|reads|file:code/configs/default.yaml", "output_identical": null},
    {"node_id": "file:code/results/table2.csv", "depth": 2, "via": "file:code/results/table2.csv|produced_by|run:code/train_main", "output_identical": true},
    {"node_id": "tex:tab:main", "depth": 3, "via": "tex:tab:main|traces_to|file:code/results/table2.csv", "output_identical": null}
   ],
   "flags": []
  },
  {
   "id": "ev:commit:paper:2b7e5d1c9a0f", "display": "A2",
   "cause": {"event_id": "ev:commit:paper:2b7e5d1c9a0f", "kind": "commit", "repo": "paper", "rev": "2b7e5d1c…", "short": "2b7e5d1", "time": "2026-10-04T09:00:00+09:00", "subject": "appendix B: learning rate 1e-3", "files": ["appendix.tex"]},
   "changed": [{"node_id": "tex:app:hparams", "change": "content_changed", "hash_checkpoint": "sha256:9b0a…", "hash_now": "sha256:44c1…", "also_changed_in": []}],
   "removed": [], "downstream": [], "flags": []
  }
 ],
 "summary": {"groups": 2, "changed": 2, "removed": 0, "downstream": 3, "flagged_nodes": 5}
}
```
When no checkpoint exists, `checkpoint` is `null` and `groups` is `[]`.

Algorithm (the engine must match this; QA derives the golden set from it):
1. Let CP be the active checkpoint, H0 = `CP.nodes[*].hash`, and H = current node hashes. Repos absent from `CP.repos` are listed in `excluded_repos` and ignored.
2. **Changed** = current nodes n (repo in CP) with `H0[n]` missing (`change: "added"`) or `H0[n] != H[n]` (`change: "content_changed"`). **Removed** = ids in H0 with no current node (entry `{"node_id","name","path","kind"}`).
3. **Cause**, per repo: E1…Ek are the repo's events after the CP rev in order (first-parent commits, then `worktree` if dirty). Non-git repos get a single `snapshot` event. If the CP rev is not an ancestor of HEAD, a single `diverged` event is used. Let h_j be the node's hash after E_j (h_0 = H0, h_k = H). The cause is E_i with the smallest i such that h_j ≠ h_0 for all j ≥ i. `also_changed_in` lists later E_j (j > i) with h_j ≠ h_{j−1}. Derived nodes are re-hashed at a commit only if their source files changed in it.
4. **Groups**: one per cause event that has changed or removed nodes. For each group, `downstream` = every node that reaches one of the group's changed nodes by following edges with effective `propagates: true` in the `from → to` direction, minus that group's changed nodes. Each entry has: `depth` (BFS distance), `via` (the first edge on one shortest path from the node towards the changed set; ties broken by edge id), and `output_identical` (`true`/`false` for kinds `result`/`asset`, i.e. whether the node's hash equals H0; `null` otherwise). A node may appear in several groups, and a node changed in one group may be downstream in another.
5. The edges used are those of the **current** scan only. `flags` = the cause event's flags.
6. Order: groups by cause `time`, then `id`; `display` = `A1`, `A2`, … in that order. `changed` by `node_id`; `downstream` by `depth`, then `node_id`.
7. Recompute triggers: scan, create checkpoint, link decision. A link decision reruns only steps 4–6.

## 9. Analyzer (`GET /api/analyze`)
```json
{
 "group_id": "ev:commit:code:9f1c2e7a4b3d",
 "node_id": "tex:tab:main",
 "chain": {
  "nodes": ["file:code/configs/default.yaml", "run:code/train_main", "file:code/results/table2.csv", "tex:tab:main"],
  "edges": ["run:code/train_main|reads|file:code/configs/default.yaml", "file:code/results/table2.csv|produced_by|run:code/train_main", "tex:tab:main|traces_to|file:code/results/table2.csv"]
 },
 "diffs": [
  {"node_id": "file:code/configs/default.yaml", "repo": "code", "path": "configs/default.yaml", "from_label": "checkpoint cp1", "to_label": "now", "binary": false, "truncated": false,
   "unified": "--- a/configs/default.yaml (cp1)\n+++ b/configs/default.yaml (now)\n@@ -2 +2 @@\n-learning_rate: 3.0e-4\n+learning_rate: 1.0e-3\n"}
 ],
 "explanation": "configs/default.yaml changed in 9f1c2e7 (\"change learning rate 3e-4 to 1e-3\"). run train_main reads it. results/table2.csv is produced by run train_main and is byte-identical to the checkpoint (not regenerated, or regenerated identically). Table 2 traces to results/table2.csv.",
 "ai": {"available": false, "label": "Ask Claude why — not available in this demo"}
}
```
- `chain` runs from a changed node of the group to `node_id` (the shortest over propagating edges; ties broken by edge id). If `node_id` itself changed, `chain.nodes = [node_id]` and `edges = []`.
- `diffs`: one per changed node on the chain, checkpoint version (from `cache/blobs/`, or `git show <cp rev>:<path>` if no blob is stored) vs now, with 2 lines of context. For paper units, the diff is of the containing file. `binary: true` → `unified: ""`. Over 400 lines → cut, `truncated: true`.
- `explanation` is built from fixed per-kind phrases (`reads` → "reads", `produced_by` → "is produced by", `traces_to` → "traces to", `includes` → "includes", `generated_by` → "is generated by", `executes` → "runs", `imports` → "imports", `value_match` → "was linked by you to"). No model call.

## 10. Triage and link decisions (`triage.json`)
```json
{
 "schema": "rmap.triage/1",
 "entries": {
  "node:tex:tab:main": {
   "target_type": "node", "target_id": "tex:tab:main",
   "state": "needs_fixing", "note": "rerun train with lr 1e-3",
   "hash_at_triage": "sha256:5f2c…", "updated_at": "2026-11-04T15:03:00+09:00",
   "history": [{"state": "needs_fixing", "note": "rerun train with lr 1e-3", "at": "2026-11-04T15:03:00+09:00", "hash": "sha256:5f2c…"}]
  }
 },
 "links": {
  "tex:app:hparams|value_match|file:code/configs/default.yaml": {"decision": "approved", "at": "2026-11-04T15:02:00+09:00", "history": [{"decision": "approved", "at": "2026-11-04T15:02:00+09:00"}]}
 }
}
```
- Entry key `<target_type>:<target_id>`. `target_type`: `node` | `finding`. `state`: `unreviewed` | `reviewed` | `needs_fixing` | `ignored`. A missing entry means `unreviewed`. `note` ≤ 2000 chars. `hash_at_triage` = the node's `hash`, or the finding's `fingerprint`.
- **Effective state** (computed on read, never stored): `effective_state` = `unreviewed` with `outdated: true` when the target's current hash ≠ `hash_at_triage`; otherwise `effective_state = state` and `outdated: false`. `history` is append-only and stays visible.
- `links[edge_id].decision`: `approved` | `rejected` | `proposed` (undo). Only edges created as `proposed` can be decided.

## 11. Input conventions the scanner recognises
### 11.1 Run record `<code repo>/runs/<run_id>.json`
```json
{"schema": "rmap.run/1", "run_id": "train_main", "started_at": "2026-09-30T14:00:00+09:00", "command": "python train.py --config configs/default.yaml",
 "script": "train.py", "inputs": ["configs/default.yaml"], "outputs": ["results/table2.csv", "results/metrics.json"]}
```
Creates node `run:code/train_main`, edges `executes` (→ script), `reads` (→ each input), `produced_by` (each output →), and event `ev:run:code/train_main`. Paths are repo-relative; missing targets are skipped with a scan warning.

### 11.2 LaTeX markers (comment lines inside a unit's span, or within 3 lines before its `\begin`)
- `% generated-by: <ref>[, <ref>…]` → `generated_by` edges. `% generated-by: manual` → `attrs.manual = true` (exempt from `figure_without_provenance`).
- `% source: <ref>[, <ref>…]` → `traces_to` edges.
- `<ref>` = `<repo_id>:<path>` or a bare `<path>`. A bare path is resolved in the paper repo first, then each code repo; if it is ambiguous or missing, no edge is made and a scan warning is logged.

### 11.3 Value-match proposals (the only heuristic links in the demo)
For each paper unit (section/table) whose owned text mentions a hyperparameter alias (§6.2), and each `config` node defining a key with the same canonical name, the engine proposes one `value_match` edge per (unit, config file) pair. The key is the last component of the dotted path, lowercased, with `-` → `_`; alias `lr` is accepted. `reason` example: `"learning_rate: paper 1e-3, config 1.0e-3; batch_size: paper 128, config 128"`; evidence = the unit's mention lines + the config line. YAML is read with a minimal `key: value` reader (indentation → dotted keys, scalars only); JSON with `json`; TOML with `tomllib` when available (Python ≥ 3.11), otherwise skipped.

### 11.4 Python imports and write calls
- Imports: `import a.b`, `from a.b import c`, and relative imports. Candidates are tried in order: `<repo>/a/b.py`, `<repo>/a/b/__init__.py`, `<repo>/src/a/b.py`, then the importing file's directory and each parent up to the repo root; `from a import c` also tries `a/c.py`. The first hit wins; unresolved names are third-party and ignored.
- Write calls: a string literal with an output extension that resolves to an existing repo file, on a line containing `savefig`, `to_csv`, `to_json`, `write_text`, `json.dump`, `np.save`, `torch.save`, or `open(` with a `"w"` mode → `produced_by` (file → script).

### 11.5 README provenance tables
In any `*.md` file: a Markdown table whose header has one column matching `/paper|figure|fig|table|item/i` and one matching `/script|code|source|file/i`. Each row splits the paper cell on `,` into items (`Fig. 5` → `item:code/fig-5`, `Table 1` → `item:code/table-1`, `App. B` → `item:code/app-b`). Every backticked `.py`/`.sh` token in the script cell becomes a `generated_by` target. Paths are resolved against the README's directory, then the directory of the row's first resolved script, then a unique basename match in the repo. On `alarm-analyzer-eval@baa9f7d` this yields items for Fig. 1, 3–10, Tables 1, 2, 3, 5 and App. B, D.1, F.

## 12. HTTP API
Base `http://127.0.0.1:<port>`. JSON responses use `Content-Type: application/json; charset=utf-8` and `Cache-Control: no-store`.
**Errors** use one shape: `{"error": {"code": "<code>", "message": "<text>"}}`. Codes: 400 `bad_request`, 403 `forbidden`, 404 `not_found`, 405 `method_not_allowed`, 409 `busy` (a scan is running), 413 `too_large`, 500 `internal`, 501 `not_implemented`.
**Guards**: bind 127.0.0.1 only; reject a `Host` other than `127.0.0.1:<port>` or `localhost:<port>` (403); POST requires `Content-Type: application/json`, a body ≤ 64 KB, and an `Origin` (if sent) equal to the server origin (403). Static paths are resolved inside `web/` (no `..`).

| # | Method | Path | Query / body | 200 response |
|---|---|---|---|---|
| 1 | GET | `/` and `/<file>` | — | static files from `web/` (`/` → `index.html`); 404 otherwise |
| 2 | GET | `/api/health` | — | `{"ok": true, "version": "0.1.0"}` |
| 3 | GET | `/api/project` | — | Project status (below) |
| 4 | POST | `/api/scan` | `{}` | Project status, after a full rescan (uses the server's `--online` setting) |
| 5 | GET | `/api/graph` | — | `{"schema":"rmap.graph/1","scanned_at":…,"nodes":[Node],"edges":[Edge]}` |
| 6 | GET | `/api/events` | `after_checkpoint=1` (optional filter) | `{"schema":"rmap.events/1","events":[Event]}` |
| 7 | GET | `/api/findings` | — | `{"schema":"rmap.findings/1","checks":[…],"findings":[Finding]}` |
| 8 | GET | `/api/alarms` | — | Alarms (§8) |
| 9 | GET | `/api/analyze` | `group=<group id>&node=<node id>` (both required) | Analysis (§9); 404 if the group is unknown or the node is not in that group's changed/downstream lists |
| 10 | GET | `/api/checkpoints` | — | `{"active":"cp1","checkpoints":[Checkpoint summary]}` (newest first) |
| 11 | POST | `/api/checkpoints` | `{"note": "<≤500 chars>", "at": {"<repo>": "<rev>"} \| null}` | **201** `{"checkpoint": Checkpoint summary, "alarms": Alarms}` |
| 12 | GET | `/api/triage` | — | `{"schema":"rmap.triage/1","entries":{key: Entry + "effective_state","outdated"},"links":{…}}` |
| 13 | POST | `/api/triage` | `{"target_type":"node"\|"finding","target_id":"…","state":"unreviewed"\|"reviewed"\|"needs_fixing"\|"ignored","note":"…"}` | `{"entry": Entry + "effective_state","outdated"}`; 404 for an unknown target |
| 14 | POST | `/api/links/decide` | `{"edge_id":"…","decision":"approved"\|"rejected"\|"proposed"}` | `{"edge": Edge, "alarms": Alarms}`; 400 if the edge was not created as `proposed` |
| 15 | GET | `/api/export` | — | `text/html; charset=utf-8`, `Content-Disposition: attachment; filename="<project-name>-report.html"`; single file (see below) |
| 16 | POST | `/api/ask` | `{"group_id":"…","node_id":"…"}` | always **501** `{"error":{"code":"not_implemented","message":"Ask Claude why runs on your own Claude Code later; not available in this demo."}}` |

**Project status** (routes 3, 4):
```json
{
 "schema": "rmap.project/1", "version": "0.1.0", "name": "Sample: tiny transformer", "root": "/Users/juhyeong/rmap-demo",
 "repos": [
  {"id": "paper", "role": "paper", "path": "paper", "abs_path": "/Users/juhyeong/rmap-demo/paper", "vcs": "git", "head": "2b7e5d1c…", "branch": "main", "dirty": false},
  {"id": "code", "role": "code", "path": "code", "abs_path": "/Users/juhyeong/rmap-demo/code", "vcs": "git", "head": "c81f0a2e…", "branch": "main", "dirty": false}
 ],
 "scanned_at": "2026-11-04T15:00:00+09:00",
 "counts": {"nodes": 34, "edges": 61, "proposed": 2, "events": 9, "findings": 10, "alarm_groups": 2},
 "checkpoint": {"id": "cp1", "created_at": "2026-10-01T18:00:00+09:00", "note": "CP1: draft v2 validated"},
 "capabilities": {"paper": true, "online_lookup": false, "ask_ai": false},
 "warnings": [{"code": "marker_target_missing", "message": "% source: results/old.csv not found", "evidence": {"repo": "paper", "path": "main.tex", "line": 120, "text": "% source: results/old.csv", "role": "marker", "page": null}}]
}
```
**Export file**: `index.html` with `app.css`, `app.js` and `vendor/*.js` inlined, plus `<script type="application/json" id="rmap-snapshot">{"exported_at":…,"project":…,"graph":…,"events":…,"findings":…,"alarms":…,"checkpoints":…,"triage":…}</script>`. Every `</` in the JSON is written as `<\/`. On load, the UI uses the snapshot if the element exists and becomes read-only (POST controls disabled and labelled "Read-only snapshot").

## 13. Engine facade (the only seam; `rmap/engine/api.py`)
```python
class Engine:
    def __init__(self, project_root: str | Path, online: bool = False) -> None: ...
    def scan(self) -> dict: ...                      # full pipeline, writes hub files, returns Project status
    def project(self) -> dict: ...                   # routes 3
    def graph(self) -> dict: ...                     # 5
    def events(self, after_checkpoint: bool = False) -> dict: ...  # 6
    def findings(self) -> dict: ...                  # 7
    def alarms(self) -> dict: ...                    # 8
    def analyze(self, group_id: str, node_id: str) -> dict: ...   # 9
    def checkpoints(self) -> dict: ...               # 10
    def create_checkpoint(self, note: str = "", at: dict[str, str] | None = None,
                          created_at: str | None = None, cp_id: str | None = None) -> dict: ...  # 11 → {"checkpoint","alarms"}
    def triage(self) -> dict: ...                    # 12
    def set_triage(self, target_type: str, target_id: str, state: str, note: str = "") -> dict: ...  # 13
    def decide_link(self, edge_id: str, decision: str) -> dict: ...  # 14 → {"edge","alarms"}
    def export_bundle(self) -> dict: ...             # 15 data part
# rmap/engine/errors.py: class NotFound(Exception), class BadRequest(Exception)  → server maps to 404 / 400
```
The engine is thread-safe only behind the server's single lock: the server holds one `threading.Lock` around `scan`, `create_checkpoint`, `set_triage` and `decide_link`. GETs return the last computed dicts. Until the engine lands, web-eng develops against `app/tests/fixtures/api/*.json` (copies of the examples in this page).

## 14. Golden-set id mapping (for PM and QA)
| demo-spec name | contract id |
|---|---|
| `cfg:default.yaml` | `file:code/configs/default.yaml` |
| `run:train_main` | `run:code/train_main` |
| `file:results/table2.csv` | `file:code/results/table2.csv` |
| `tab:main` | `tex:tab:main` |
| `app:hparams` | `tex:app:hparams` |
| `sec:setup` | `tex:sec:setup` |
| PL1 / PL2 | `tex:sec:setup\|value_match\|file:code/configs/default.yaml` / `tex:app:hparams\|value_match\|file:code/configs/default.yaml` |
| A1 / A2 | groups with `display` `A1` / `A2` |
| F01…F10 | check codes in §6.2 |

For the golden set to follow from §8, the sample must satisfy:
- (a) Appendix B's hyperparameters sit in prose or a bare `tabular` owned by `tex:app:hparams`, not inside a labelled float.
- (b) Only Section 4 and Appendix B mention hyperparameter aliases.
- (c) Every float is labelled, and `fig:arch` carries `% generated-by: manual`.
- (d) `tex:tab:main` has `% source: code:results/table2.csv`, and no other `% source:` marker reaches a `run:code/train_main` output.
- (e) `fig:curve` carries `% generated-by: code:plot_curve.py`.
- (f) `cache/refs.json` records `smith2021ghost` as `not_found` and every other cited key as `matched`.
- (g) The `eval.py` edits K4/K5 restore identical bytes.
