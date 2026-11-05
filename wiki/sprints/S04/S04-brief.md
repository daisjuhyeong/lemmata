---
type: task-card
owner_agent: lead
status: draft
sources:
  - "founder decisions in chat, 2026-11-05 18:09 KST"
  - "../S03/S03-brief.md"
  - "../../architecture/data-model.md"
last_reviewed: 2026-11-05
---
# S04 brief: Lemmata hub on the Mac mini, app on the MacBook, GitHub sign-in, Claude Code via MCP

## Founder decisions (2026-11-05)
1. The **app runs on the MacBook**; the **engine runs on the Mac mini** as an always-on service. Network: **Tailscale** (already installed and connected on both).
2. Sign-in: **GitHub only**. Signing in is also the GitHub connection (one step).
3. Inputs must be simple: pick a **GitHub repo** from a list; the paper comes from an **uploaded Overleaf source zip** (no Overleaf Git).
4. VS Code: **Claude Code can query Lemmata** (MCP). No other VS Code features this sprint.

## Architecture
```
MacBook                                   Mac mini (Tailscale: dais-juhyeongs-mac-mini)
Lemmata.app (Tauri)  ── http over Tailscale ──►  lemmata hub  (launchd LaunchAgent, port 8765)
  "Connect to server"                            ├─ hub pages + API  /, /api/hub/*
  navigates to the hub URL                       ├─ per-project UI + API  /p/<pid>/ , /p/<pid>/api/*  (existing UI/API)
VS Code + Claude Code ── http + Bearer ──────────►├─ MCP endpoint  /mcp
                                                 └─ ~/Lemmata/  (data dir)
                                                      hub/config.json, hub/tokens.json, hub/github.json (0600), hub/hub.log
                                                      projects/<pid>/project.json, code/ (git clone), paper/ (local git repo, one commit per uploaded zip), .lemmata/
```
The existing single-project mode (`lemmata open/demo/serve`, the S03 local sidecar) keeps working unchanged.

## Network guard (hub mode)
- Listen on `0.0.0.0:8765` (configurable), but accept a TCP connection only if the peer address is loopback or in Tailscale ranges `100.64.0.0/10` or `fd7a:115c:a1e0::/48`; others are closed immediately.
- Allowed `Host` values: `localhost`, `127.0.0.1`, the Mac mini's Tailscale IPs and MagicDNS names (short and full `*.ts.net`), detected at start via `tailscale status --json` (CLI at `tailscale` on PATH or `/Applications/Tailscale.app/Contents/MacOS/Tailscale`); plus `--allow-host` extras. Origin check: same rule.
- Every route except `GET /api/hub/status`, `POST /api/hub/pair`, and the static files of the pairing/sign-in page requires a session: cookie `lemmata_session` (HttpOnly, SameSite=Strict, Path=/) **or** `Authorization: Bearer <token>`.

## Pairing and sessions
- `lemmata hub pair-code` (and the hub's start-up log line) shows a one-time pairing code: 8 characters from `ABCDEFGHJKMNPQRSTUVWXYZ23456789`, valid 10 minutes, max 5 wrong attempts per code.
- `POST /api/hub/pair {"code": "...", "device": "MacBook"}` → `200 {"token": "<43-char urlsafe>", "device_id": "dev_..."}` and sets the session cookie. Tokens are stored hashed (sha256) in `tokens.json` with device name and created/last-used times. `lemmata hub devices` lists and `lemmata hub revoke <device_id>` revokes.
- MCP clients use a token from `lemmata hub token --device "VS Code"`, which prints a new token once.

## GitHub sign-in (device flow)
- `config.json` holds `github_client_id` (an OAuth App with Device Flow enabled; no client secret anywhere). Scopes: `repo read:user`.
- `POST /api/hub/github/start` → `{"user_code","verification_uri","expires_in","interval"}`; `GET /api/hub/github/poll` → `{"state":"pending"|"ok"|"denied"|"expired"|"error","user":{"login","name","avatar_url"}?}`. On `ok`, the token is saved to `github.json` (0600) and the GitHub login becomes the hub **owner**; a later sign-in by a different GitHub account is refused (`403 not_owner`). `POST /api/hub/github/logout` deletes `github.json`.
- `GET /api/hub/github/repos?q=` → `{"repos":[{"full_name","private","default_branch","pushed_at","description"}]}` (affiliation owner,collaborator,organization_member; sorted by pushed_at; filtered by q).
- git over HTTPS with the token passed per command as `-c http.extraHeader="Authorization: Basic <base64(x-access-token:TOKEN)>"`; the token is never written into `.git/config` or logs.
- GitHub base URLs are configurable (`github_api`, `github_web`) so tests run against a local fake GitHub.

## Projects
- `GET /api/hub/projects` → `{"projects":[{"id","name","code_repo","branch","paper_versions","last_sync","scanned_at","counts":{"recheck","findings"}}]}`
- `POST /api/hub/projects {"name"?, "code_repo":"owner/name", "branch"?}` → clones (depth 1000) into `projects/<pid>/code`, creates `paper/` as an empty git repo, writes project.json (repos `code` and `paper`), scans → `201 {project}`. `pid` = slug of the repo name + 4 random hex chars.
- `POST /api/hub/projects/<pid>/paper` with body = the Overleaf zip (`Content-Type: application/zip`, max 100 MB): safe unzip (reject absolute paths, `..`, symlinks; max 5,000 files and 500 MB unpacked; strip a single top-level folder if present) into a temp dir, replace `paper/`'s working tree with it, `git add -A && git commit -m "Overleaf upload <ISO time>"` with author "Lemmata <lemmata@localhost>" → rescan → `{"version": n, "commit": "<sha>", "files": n}`. Each upload is a paper version on the timeline.
- `POST /api/hub/projects/<pid>/sync` → `git fetch` + fast-forward the clone's branch, rescan → `{"changed": bool, "head": "<sha>"}`. A background loop syncs every project every 5 minutes and the existing watch loop rescans on change.
- `DELETE /api/hub/projects/<pid>` → moves the folder to `~/Lemmata/trash/` (no hard delete).
- Per-project UI at `/p/<pid>/` and its existing API at `/p/<pid>/api/...` (same shapes as data-model.md §12). The web UI computes its API base from `location.pathname` so it works both at `/` (single-project mode) and `/p/<pid>/`.

## MCP (Claude Code in VS Code)
- Endpoint `POST /mcp`, MCP "Streamable HTTP" transport, JSON responses only (no SSE needed): handle `initialize` (protocolVersion echo of the client's if supported else "2025-06-18"; serverInfo `{"name":"lemmata","version"}`; capabilities `{"tools":{}}`), `notifications/initialized` (→ 202, empty), `ping`, `tools/list`, `tools/call`. `GET /mcp` → 405. Auth: Bearer token (cookie not accepted on /mcp).
- Tools (results as `content: [{"type":"text","text": <compact readable text>}]` plus `structuredContent` with the JSON):
  - `list_projects()`
  - `project_status(project)` — counts, checkpoint, last sync, paper versions
  - `alarms(project)` — groups with cause commit/upload and affected nodes (file:line)
  - `explain(project, node, group?)` — analyzer chain + diff
  - `findings(project, check?)` — integrity findings with evidence
  - `node(project, query)` — find a node by id or label; returns what it rests on / supports with file:line
  - `search(project, query, limit=20)`
  - `set_triage(project, node, state, note?)` — reviewed | needs_fixing | ignored | unreviewed
  - `sync(project)` — pull GitHub, rescan, return what changed
  `project` accepts the pid or the project name or the GitHub repo name. Paths are repo-relative so Claude can map them onto its local checkout.
- Setup line for the user (printed by `lemmata hub token --device "VS Code"`):
  `claude mcp add --transport http lemmata http://dais-juhyeongs-mac-mini:8765/mcp --header "Authorization: Bearer <token>"`

## Running it on the Mac mini
- `lemmata hub serve [--data ~/Lemmata] [--port 8765]`
- `lemmata hub install` writes `~/Library/LaunchAgents/ai.lemmata.hub.plist` (ProgramArguments = the current `sys.executable -m lemmata hub serve --data ...`, KeepAlive, RunAtLoad, logs to `~/Lemmata/hub/hub.log`, PATH including /opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin) and loads it with `launchctl bootstrap gui/$(id -u)`; `lemmata hub uninstall` reverses it. `lemmata hub status` prints URL(s), owner, projects, devices.
- `lemmata hub config --github-client-id Ov23li...` sets the client id.

## MacBook app (Tauri)
- Launcher gets **Connect to Lemmata server** (URL field prefilled `http://dais-juhyeongs-mac-mini:8765`, remembered) next to the existing local options. Connecting navigates the main window to the hub URL; the hub's own page handles pairing and GitHub sign-in (the webview keeps the cookie). Menu: File → Connect to Server…, Disconnect (back to launcher). On launch, if a server was used last time, reconnect automatically; if unreachable, show "Can't reach the Mac mini. Is it on, and is Tailscale connected on both Macs?" with Retry and Use locally.

## Owners
- CTO: ADR-004 + threat model `wiki/architecture/threat-model.md` for hub mode (network exposure, tokens, GitHub token storage, zip ingest, MCP write tool); fold findings back to the lead quickly.
- pipeline-eng (hub): `app/src/lemmata/hub/` (config, guard, auth, github, projects, sync, routes, launchd), server.py refactor for path-prefixed multi-project routing, `lemmata hub ...` CLI, fake-GitHub test server, tests.
- pipeline-eng (mcp): `app/src/lemmata/mcp.py` + tests, against the interface `ctx.list_projects() -> list[dict]`, `ctx.resolve(project) -> (pid, Engine)` raising `NotFound`, `ctx.sync(pid) -> dict`.
- web-eng: hub pages in `app/src/lemmata/web/hub/` (pairing → GitHub sign-in with code display → projects list → New project: repo picker + zip drop → open), API base in `app.js`, "Upload paper zip" and "Sync now" in the project top bar when served by a hub, Tauri connect flow in `desktop/`.
- QA: end-to-end on Linux with the fake GitHub: pair, sign in, create project from a repo, upload a zip, alarms after a second upload, MCP via a real MCP client handshake (`claude` CLI if available, otherwise raw JSON-RPC), guard tests.
