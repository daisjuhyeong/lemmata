---
type: handoff
owner_agent: web-eng-b
status: draft
sources:
  - "S06-brief.md (sections A, B)"
  - "handoff-pipeline-eng.md"
  - "../../design/screens/s06-obsidian-redesign.md"
last_reviewed: 2026-11-06
---
# S06 handoff (web-eng B): hub pages, mock hub, VS Code, Mac app default, CLI flag

Branch `s06-obsidian-ui`. Python suite 126 OK (2 new in `app/tests/test_hub_cli.py`); vscode `npm run compile && npm test` (27) and `npm run test:integration` (9, one new) pass; `cargo build --offline` warning-free.

## 1. Hub pages (`app/src/lemmata/web/hub/`)
- `hub.js` / `hub.css` restyled calmer (sunken top bar, hairline cards, quiet segmented control). All Overleaf UI removed (token card, link field, hints). No innerHTML; styles only via CSSOM or classes.
- Projects list: each row says "Code: owner/name (main)", then the paper in words ("Paper: GitHub repo owner/name", "Paper: the folder paper/ in your code repo (GitHub)", "Paper: uploaded zip, version 3", "No paper yet"), last synced, "Nothing to look at" / "N things to look at", "N checks about your paper". A project whose stored source is still `overleaf` reads "Paper: Overleaf project (no longer supported here)" (data only).
- New project: step 1 pick the code repo; step 2 "Where is the LaTeX source of your paper?" with three choices: "A GitHub repo of its own" (picker; sends `paper_repo` + `paper_branch`), "A folder in the code repo" (text field, default `paper`; sends `paper_repo` = code repo + `paper_subdir`), "Upload a zip instead". Help text names VS Code and the setup guide `docs/SETUP-two-macs.md` (plain path, not a link; CTO may want a real link).
- API errors: client handles both `{error:{code,message}}` and the bare `{"error":"feature_disabled"}`; plain-language messages for `paper_repo_not_found`, `paper_branch_not_found`, `paper_subdir_missing`, `paper_too_large`.
- Screenshots (1100x760, Playwright, script `app/tests/shots_s06_hub.py`): `app/docs/screens/s06-hub-{pair,signin,empty,new-repo,new-folder,new-zip,new-error,projects}.png`. I viewed new-repo and projects.
- If the create call fails because the paper part is invalid, the whole create shows an error with Back (I assumed the hub validates before it keeps the project; if it keeps a half-created project the user would see it in the list on retry).

## 2. hubControls() - NOT DONE (does not exist in app.js yet)
`grep hubControls app.js` found nothing, so I did not touch app.js. Needed (replaces the S05 `paperSrcChip`/`connectOverleaf` block, ~app.js lines 867-935):
- Data: `HUBINFO = {kind: ps.kind, repo: ps.repo, subdir: ps.subdir, last_sync}` from `/api/hub/projects`; drop `overleaf_configured`.
- Text: kind `github` -> `Paper: GitHub repo ✓ synced 3 min ago` (own repo) or `Paper: folder paper/ in your code repo ✓ synced 3 min ago`; kind `zip` -> `Paper: zip (upload new version)` (click opens the file picker); `overleaf` is shown as zip-like "Paper: old setting" with only "Connect paper repo…".
- Buttons: `Sync now` (`POST /api/hub/projects/<pid>/sync`; toast reads `r.paper.changed/.error`, never says Overleaf), `Connect paper repo…`, `← Projects` (href `/`).
- Dialog "Connect paper repo": field `owner/name` (accept a github.com URL, strip to owner/name), optional folder, then `POST /api/hub/projects/<pid>/paper-source {"kind":"github","repo","branch"?,"subdir"?}`; map errors like `PLAIN` in hub.js (404 `paper_repo_not_found`, 400 `paper_subdir_missing`, 409 `not_signed_in`, 409 `paper_is_github` on zip upload while GitHub is the source: hide the zip input in github mode).

## 3. `app/tests/mock_hub.py`
Overleaf off by default: routes under `/api/hub/overleaf/*`, `paper_overleaf`, and `kind:"overleaf"` answer 404 `{"error":"feature_disabled"}`; status omits `overleaf_configured` (hook `POST /__mock/overleaf {"enabled":true}` turns it on). Supports `paper_repo/paper_branch/paper_subdir` on create and `paper-source {kind:"github"}` with `paper_repo_not_found` (not in the fake repo list, one is `daisjuhyeong/www27-paper`), `paper_subdir_missing` (subdir `missing`), `not_signed_in`; zip upload after github -> 409 `paper_is_github`. `shots_s05.py` is obsolete (drives Overleaf UI); left in place.

## 4. VS Code extension (`vscode/`, version 0.1.1, `lemmata-0.1.1.vsix` rebuilt; 0.1.0 file left, delete if unwanted)
- `matchProjects`: paper folder = folder whose GitHub remote equals `paper_source.repo`; `Binding.subdirs.paper` = `paper_source.subdir`; if the paper repo is the code repo, one folder is both code and paper. Overleaf remote matching only when `paper_source.kind == "overleaf"`.
- `mapPath(folders, repo, rel, subdirs?)`: `paper/<rel>` -> `<folder>/<subdir>/<rel>`; the server-provided subdir gets the same escape checks as paths (`..`, absolute, backslash refused). `toDiagnostics` and the extension pass `subdirs`.
- Tests: new unit tests (own repo, subdir, zip, Overleaf only from data, hostile subdir) and an integration test with a real hub scan and a monorepo checkout (`docs/paper/main.tex` squiggle lands on `\begin{table`). Fixture now marks the sample project's paper as GitHub `alice/demo-paper`.
- README updated (matching rules, sync wording). Not run: `npm run test:host` (downloads VS Code).

## 5. Mac app
`desktop/src-tauri/src/server.rs` `DEFAULT_URL` and the error example, and `desktop/launcher/index.html` input value, now `http://100.111.135.94:8765`. Note: the launcher shows it as the field's value (as before), not an HTML placeholder attribute.

## 6. CLI
`lemmata hub config --overleaf on|off` sets `overleaf_enabled`; `app/tests/test_hub_cli.py`.

## For review
1. Help text mentions `docs/SETUP-two-macs.md` as plain text.
2. Hub pages were not run in the Mac app WebView; same CSP as before.
3. hubControls is the open item (section 2).
