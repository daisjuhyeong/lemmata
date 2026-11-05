---
type: handoff
owner_agent: web-eng
status: done
sources:
  - "S05-brief.md (sections B and C)"
  - "handoff-pipeline-eng.md (error codes, sync shape)"
last_reviewed: 2026-11-05
---
# S05 handoff, web-eng (sections B and C)

## Done
**B. Hub UI** (`app/src/lemmata/web/hub/hub.js|css`, `web/app.js|css`; no innerHTML, no inline scripts)
- Hub page: "Overleaf" card (exact menu path, link to https://www.overleaf.com/user/settings, password field, Save / Replace / Remove; token never shown again). Project rows show "Overleaf" vs "Paper vN (zip)".
- New project step 2: "Overleaf project link" | "Drop a zip" toggle, Overleaf by default when `overleaf_configured`. The paper is attached with `POST .../paper-source` after the project is created (not via `paper_overleaf`), so a bad link leaves the project in place with Retry.
- Project top bar (hub mode): "Paper: Overleaf ✓ (synced N min ago)" for Overleaf projects (no upload button); zip projects get a "Paper: zip" button opening a dialog with "Upload paper zip" / "Connect Overleaf…". Sync toast reads `code`/`paper` and shows `paper.error`. Top bar tightened so it still fits at 1280 px.
- Screenshots: `app/docs/screens/s05-*.png` (7 files), made by `app/tests/shots_s05.py` against the updated `app/tests/mock_hub.py`.

**C. VS Code extension** (`vscode/`): connect + SecretStorage, status bar, remote matching, path mapping (with `..`/absolute path refusal), diagnostics with triage-aware severity, tree panel, commands (triage, Why? virtual document, Open in Lemmata, Refresh, Sync now, Set checkpoint with confirmation). Package: `vscode/lemmata-0.1.0.vsix` (README: `vscode/README.md`). Pure logic is in `src/core/` (no `vscode` import) so it is testable.

## Verified
- `cd vscode && npm run compile && npm test` : 19 unit tests pass.
- `npm run test:integration` : 8 tests pass against the real hub HTTP server (`lemmata.hub.routes`, in-process in `test/hub_fixture.py`), fake GitHub, token from `lemmata hub token`. Golden set confirmed: A1 = config, run train_main, table2.csv, Table 2; A2 = App. B; 5 to recheck; diagnostic lines checked against the checked-out files; findings land on the quoted lines; triage hides or escalates; checkpoint empties alarms; bad token = unauthorized, closed port = offline.
- `npx @vscode/vsce package` works. Python: 110 tests pass (`unittest discover`).

## Not tested
- Any VS Code GUI behaviour (tree, menus, status bar, input boxes). The extension-host smoke test (`npm run test:host`) is written but could not run: the proxy returns 403 for update.code.visualstudio.com, so VS Code cannot be downloaded.
- Real Overleaf and real GitHub; `Connect Overleaf` was tested only against the mock hub.
- In the integration fixture the paper's Overleaf link is faked by editing the project's `paper_source` in `project.json`; no Overleaf fetch happens.

## Contract notes and mismatches
- Alarm node file:line is not in `/alarms`; the extension also reads `/p/<pid>/api/graph` (node `loc`) and `/triage`. Nodes without a line (config, run, result files) are marked on line 1.
- Hub projects reached by Bearer on `/p/<pid>/api/*` worked as briefed. Triage keys are `node:<id>` and `finding:<id>`.
- The web UI's console shows a CSP "inline style" error on `/p/<pid>/` pages. It is not from my code (it does not appear on hub pages); probably the vendored graph library. Not investigated.
- `lemmata.project` override with no matching remote maps nothing (panel only).

## Install steps for Juhyeong
See `vscode/README.md`. Short: `code --install-extension vscode/lemmata-0.1.0.vsix`, then "Lemmata: Connect to Server" with `http://100.111.135.94:8765` and a token from `uv run lemmata hub token --device "VS Code"`.

## Log line (for the lead to append)
`2026-11-05 | web-eng | build | app/src/lemmata/web/{hub/*,app.js,app.css}, app/tests/{mock_hub,shots_s05}.py, app/docs/screens/s05-*.png, vscode/**, wiki/sprints/S05/handoff-web-eng.md | S05 B+C: Overleaf hub UI; VS Code extension 0.1.0 (19 unit + 8 integration tests; host smoke blocked by network)`
