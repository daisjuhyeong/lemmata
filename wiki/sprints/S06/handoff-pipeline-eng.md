---
type: handoff
owner_agent: pipeline-eng
status: draft
sources:
  - "S06-brief.md section A"
  - "../S05/handoff-pipeline-eng.md"
last_reviewed: 2026-11-06
---
# S06 handoff (pipeline-eng): paper from a GitHub repo, Overleaf switched off

Branch `s06-obsidian-ui`. Section A of the [brief](S06-brief.md) implemented; suite: 124 tests OK (11 new in `app/tests/test_github_paper.py`; `test_overleaf.py` now sets `overleaf_enabled=True`).

## API
- `POST /api/hub/projects` accepts `paper_repo`, `paper_branch`, `paper_subdir`. `paper_branch`/`paper_subdir` without `paper_repo` -> 400; `paper_repo` together with `paper_overleaf` -> 400. No paper fields -> `{"kind":"zip"}` (the "default" kind is still zip when nothing is given; the UI should send `paper_repo`).
- `POST /api/hub/projects/<pid>/paper-source {"kind":"github","repo","branch"?,"subdir"?}`: clone into `tmp/pp-*` first, then atomic swap (old paper kept as `paper.prev-<time>`, rolled back on failure, manifest + project.json updated together). Response: `{kind, repo, branch, subdir?, head, versions}`.
- `paper_source` in project JSON: `{"kind":"github","repo","branch","subdir"?}` (branch is the real branch after clone).
- Sync (5-min loop, `POST /sync`, same per-project lock): `git fetch origin <branch>` + `merge --ff-only` in the separate paper clone; result in `paper` (`changed`, `head`, `source:"github"`, `error{code,message}` on failure; code sync still 200). No throttle (GitHub). If the subdir vanished upstream the fetch is not merged: `paper.error.code = paper_subdir_missing`.
- Validation: repo like code_repo; branch via `check-ref-format`; subdir relative, `/` only, no `.`/`..`/empty parts, no leading `-` or `/` or `~`, no control chars/colon/backslash, no `.git` alias, <= 200 chars (trailing `/` stripped), must be a folder after clone else 400 `paper_subdir_missing` (clone removed). Others: 404 `paper_repo_not_found`, 404 `paper_branch_not_found`, 413 `paper_too_large`, 409 `not_signed_in`.
- Zip upload while GitHub is the source -> 409 `paper_is_github` (like `paper_is_overleaf`). Switching a subdir source to zip imports the folder's files as a fresh one-commit repo; a whole-repo source just drops `origin`.

## Engine change (minimal)
Manifest repo entry may carry `"git_subdir": true` with `path` = `paper/<subdir>` (inside the clone). Then `WorkTree` treats the folder as git (`tree.py`: `in_work_tree`), `status_entries` and `read_commits` use `show_prefix` (status limited to the folder, log `--relative -- .`, i.e. history filtered to it), `analyze` reads `rev:./path`. Top-level repos behave exactly as before (prefix is empty). Tested: commit outside `paper/` does not create a paper cause and `paper_versions` stays; commit inside does.

## Overleaf flag
Hub config `overleaf_enabled` (default false). Off: every `/api/hub/overleaf/*` route, `paper_overleaf` on create and `kind:"overleaf"` on paper-source answer 404 `{"error":"feature_disabled"}` (after auth, so unauthenticated is still 401); `/api/hub/status` omits `overleaf_configured`; `_sync_paper` of an existing Overleaf project returns `skipped:"feature_disabled"` and never contacts Overleaf (loop included). Switching such a project to zip/github still works.

## For review
1. `{"error":"feature_disabled"}` is a bare string, unlike other errors (`{error:{code,message}}`), as the brief literally says; the web client must handle both.
2. Code-repo subdir needs `paper_repo` spelled out (no implicit default to the code repo).
3. Paper clone is shallow (depth 1000), like the code clone.
4. `app/tests/mock_hub.py` (web mock) still emulates Overleaf and has no github paper source; web-eng should add it.
5. Not run against real GitHub.
