---
type: handoff
owner_agent: pipeline-eng
status: draft
sources:
  - "S05-brief.md section A"
  - "../../architecture/threat-model.md (M4, M5, M10)"
  - "https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git-integration"
last_reviewed: 2026-11-05
---
# S05 handoff (pipeline-eng): Overleaf as paper source

Branch `s05-overleaf-vscode`. Section A of the [brief](S05-brief.md) is implemented as written; no route or field was renamed.

## What changed
- `app/src/lemmata/hub/overleaf.py` (new): token store `~/Lemmata/hub/overleaf.json` (written by `write_private`: temp file fchmod 0600 before content, atomic rename; hub dir 0700), `parse_project` (full `https://www.overleaf.com/project/<24hex>` URL, `overleaf.com`, scheme-less `www.overleaf.com/...`, or bare id; `/read/...` share links rejected with "Use the project link from your Overleaf dashboard, not a share link."), `Overleaf.base()`.
- `projects.py`: `git()` takes `user=` (Overleaf uses `git`, GitHub keeps `x-access-token`); `Manager.set_paper_source`, `_overleaf_clone`, `_overleaf_git` (error mapping), `_sync_paper`; `create(..., paper_overleaf)`; `summary` adds `paper_source`; `sync` returns `{changed, head, code:{changed,head}, paper:{changed,head,source[,skipped|error]}}`.
- `routes.py`: `PUT/DELETE /api/hub/overleaf/token`, `POST /api/hub/projects/<pid>/paper-source`, `overleaf_configured` in `GET /api/hub/status`, `paper_overleaf` on `POST /api/hub/projects`, `do_PUT`.
- `config.py`: `overleaf_path`, config keys `overleaf_git` (default `https://git.overleaf.com`) and `overleaf_min_interval` (default 120 s).
- `github.py`: `scrub` also removes the base64 form of `git:<token>`; `git_auth_header(token, user)`.
- Tests: `app/tests/fake_overleaf.py`, `app/tests/test_overleaf.py` (13 tests); one assertion in `test_hub.py::test_funnel_header_and_other_methods` changed because PUT is now a real method (unauthenticated PUT -> 401).

## Behaviour worth knowing
- Switch to Overleaf: clone into `~/Lemmata/tmp/ol-*` first; only after a successful clone is `paper/` renamed to `projects/<pid>/paper.prev-<YYYYmmdd-HHMMSS>` and the clone renamed to `paper/` (rolled back if the second rename fails). A failed clone (auth, 404, no token) leaves the project untouched. Then rescan.
- Switch to zip: the current tree stays as the zip repo; `origin` is removed from `paper/.git`; no more Overleaf fetches.
- Sync: code (GitHub) as before; then paper: `git fetch origin HEAD` + `merge --ff-only`, never a push. At most one Overleaf fetch per project per `overleaf_min_interval` (120 s; the last attempt time is in `project.json` as `overleaf_last_fetch`, failures count too). A throttled call returns `paper.skipped = "rate_limited"`. An Overleaf error (expired token, 429, rewritten history) goes into `paper.error {code,message}`; the code sync still answers 200.
- Security: token only in the git child's env (`GIT_CONFIG_KEY_0=http.<base>/.extraHeader`), all S04 flags (hooks off, `protocol.allow=never`, https only, `http.followRedirects=false`, `credential.helper=`, `core.symlinks=false`, no submodules, no system/global config). Overleaf base URL is `https://git.overleaf.com` unless config sets a loopback URL (tests); any other host in config is ignored. `scrub` covers hub log lines and 500 bodies.

## Deviations / decisions for review
1. HTTP status codes were not in the brief: `overleaf_token_missing` 409, `overleaf_auth_failed` 502 (not 401, which the UI treats as "pair this device"), `overleaf_not_found` 404, bad id/share link 400 `bad_request`.
2. `POST .../paper` (zip upload) while Overleaf is the source returns 409 `paper_is_overleaf` (otherwise local commits would break the next fast-forward). Not in the brief.
3. The sync loop still only runs when GitHub is signed in (unchanged condition).
4. `PUT` now reaches the dispatcher; other unknown PUT paths answer 401/404/405 like other methods.
5. Not verified against real Overleaf (no token/network here): the 401/403/404 mapping rests on git's messages ("returned error: 40x", "Authentication failed", "terminal prompts disabled"). QA with the real token should confirm each case once.

## Verified
- `PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_*.py'` -> 110 tests OK (13 new).
- Live: `lemmata hub serve --host 127.0.0.1` against both fakes (driver in /tmp, not committed): pair, GitHub sign-in, PUT token (file mode 0600), create with `paper_overleaf` URL, checkpoint, commit on fake Overleaf, background loop (3 s) -> alarm `ev:commit:paper:<sha>`, POST /sync new shape, `ps` shows no token, switch back to zip, token found only in `overleaf.json`.
