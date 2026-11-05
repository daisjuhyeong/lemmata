---
type: task-card
owner_agent: lead
status: draft
sources:
  - "founder decisions in chat, 2026-11-05 20:19-20:25 KST"
  - "../S04/S04-brief.md"
  - "https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git-integration"
last_reviewed: 2026-11-05
---
# S05 brief: paper straight from Overleaf, and Lemmata inside VS Code

## Founder decisions (2026-11-05)
1. Juhyeong has Overleaf premium (Git integration works). The paper must come **directly from Overleaf** — no more zip uploads.
2. Build a **VS Code extension** that shows Lemmata's alarms and findings where he edits. (Notion: not now.)
3. Context: hub runs on the Mac mini at `http://100.111.135.94:8765` (MagicDNS is off on his tailnet, so the IP is the address that works); the MCP connection for Claude Code (S04) stays as is.

## A. Overleaf as a paper source (pipeline-eng, hub)
- Overleaf Git: remote `https://git.overleaf.com/<project_id>` (project id = 24 hex chars from `https://www.overleaf.com/project/<id>`). Auth: username `git`, password = an Overleaf **Git authentication token** (Overleaf → Account Settings → Git Integration → Generate token). One token per hub, stored in `~/Lemmata/hub/overleaf.json` (0600, created 0600), never in `.git/config`, argv or logs — passed exactly like the GitHub token (env `GIT_CONFIG_*` extraHeader `Authorization: Basic base64("git:" + token)` scoped to `https://git.overleaf.com/`), with all S04 git hardening.
- API:
  - `PUT /api/hub/overleaf/token {"token": "..."}` → verifies nothing yet, stores it → `{"configured": true}`; `DELETE /api/hub/overleaf/token`; `GET /api/hub/status` gains `"overleaf_configured": bool`.
  - `POST /api/hub/projects/<pid>/paper-source {"kind": "overleaf", "project": "<url or 24-hex id>"}` → validates the id, clones Overleaf into a fresh dir with the hardened git, replaces `paper/` atomically (old paper repo moved to `projects/<pid>/paper.prev-<time>/`), rescans → `{"kind":"overleaf","project_id","head","versions"}`. Errors: `overleaf_token_missing`, `overleaf_auth_failed` (401/403 from Overleaf: "token missing or expired, or the project isn't yours/shared"), `overleaf_not_found`. `{"kind": "zip"}` switches back (keeps the current tree as the zip repo).
  - `POST /api/hub/projects` accepts optional `"paper_overleaf": "<url or id>"` to set it at creation.
  - Project JSON (`GET /api/hub/projects`) gains `"paper_source": {"kind": "zip"|"overleaf", "project_id"?: "..."}`.
- Sync: the existing 5-minute loop and `POST /sync` fetch **both** code (GitHub) and paper (Overleaf); Overleaf's own commits become paper versions on the timeline. `sync` returns `{"code": {"changed","head"}, "paper": {"changed","head"}}` (keep the old top-level `changed`/`head` for the code repo for compatibility). Never push to Overleaf. Overleaf rate-limits git; don't fetch more often than every 2 minutes per project.
- Allowed git host for Overleaf: exactly `git.overleaf.com` over https.
- Tests with a fake Overleaf (reuse the fake GitHub's git-http-backend approach, Basic auth with user `git`).

## B. Hub UI for Overleaf (web-eng, small)
- Hub page: "Overleaf" card under the GitHub sign-in: paste token (with the exact Overleaf menu path and a link to `https://www.overleaf.com/user/settings`), Save / Remove. Never re-display the token.
- New project screen: step 2 becomes "Paper: [Overleaf project link]  or  [drop a zip]"; default Overleaf when a token is configured.
- Project top bar (under `/p/<pid>/`, hub mode): "Paper: Overleaf ✓ (synced 3 min ago)" with "Connect Overleaf…" when it's still a zip project; "Upload paper zip" only for zip projects.

## C. VS Code extension (web-eng)
Folder `vscode/` (TypeScript, no runtime deps beyond the VS Code API; build with `npm run compile`; package with `npx @vscode/vsce package` → `lemmata-<ver>.vsix`). Publisher `lemmata-local`, name `lemmata`, display name "Lemmata", engines vscode ^1.90.
- **Connect:** command "Lemmata: Connect to Server" asks for the server URL (default `http://100.111.135.94:8765`) and a token (from `lemmata hub token --device "VS Code"`; the same kind of token Claude Code uses). Token in VS Code SecretStorage, URL in settings `lemmata.serverUrl`. Status bar item "Lemmata: 5 to recheck" (click → panel), "Lemmata: offline" when unreachable.
- **Which project:** for each workspace folder, read its git remotes (`git config --get-regexp ^remote\..*\.url`) and match `github.com[:/]owner/name(.git)?` against the hub projects' `code_repo`, and `git.overleaf.com/<id>` against `paper_source.project_id`. Setting `lemmata.project` overrides. Map hub paths `code/<rel>` and `paper/<rel>` onto the workspace folder that matched that repo; paths for an unmatched repo are shown in the panel but not as diagnostics.
- **Diagnostics (the core):** every 30 s (and on window focus and file save), fetch `/p/<pid>/api/alarms` and `/p/<pid>/api/findings` with `Authorization: Bearer`. Publish:
  - alarms: Warning at the node's file:line, message "Recheck: <node> — <cause short sha> <cause subject> (<changed|downstream of …>)", source "Lemmata", code = group display (A1…).
  - findings: Warning/Information per finding severity at each evidence location, message = the finding message, source "Lemmata", code = check name.
  - Triage state "reviewed"/"ignored" hides the diagnostic; "needs_fixing" keeps it as Error.
- **Panel:** activity-bar view "Lemmata" with a tree: Alarms (groups → nodes) and Findings (by check → items). Click → open file at line. Context menu: Mark Reviewed / Needs fixing / Ignore (POST `/p/<pid>/api/triage` with Bearer; note optional via input box), "Why?" (GET analyze → read-only virtual document with the chain and the diff), "Open in Lemmata" (opens the hub page in the browser). Commands: Refresh, Sync now (POST `/api/hub/projects/<pid>/sync`), Set checkpoint (POST `/p/<pid>/api/checkpoints` with a note).
- **Security:** only http(s) to the configured server; token never logged; quoted repo text is shown as plain text (no markdown rendering of untrusted content in hovers); no telemetry.
- **Tests:** unit tests (node's built-in test runner) for remote matching, path mapping, alarm/finding → diagnostic conversion, and an integration test against a real `lemmata hub serve` + fake GitHub (create a project, take the generated sample's code repo, then check the diagnostics computed for a checkout of it). Downloading VS Code for `@vscode/test-electron` is optional; if the network blocks it, say so.

## Owners
- pipeline-eng: A (+ tests, handoff `wiki/sprints/S05/handoff-pipeline-eng.md`).
- web-eng: B and C (+ tests, handoff `wiki/sprints/S05/handoff-web-eng.md`, install steps for Juhyeong).
- QA afterwards: Overleaf token handling (no leaks), sync of both repos, extension diagnostics against the hub.
