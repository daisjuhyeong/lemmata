---
type: handoff
owner_agent: pipeline-eng-hub
status: draft
sources:
  - "S04-brief.md"
  - "../../architecture/data-model.md"
  - "../../../app/tests/test_hub.py"
last_reviewed: 2026-11-05
---
# Handoff: hub (S04, pipeline-eng hub)

## Delivered
- `app/src/lemmata/hub/`: config (defaults incl. client id `Ov23lij3uNF6pctpA6yH`), guard, auth, github, projects (git, zip ingest, sync, trash, `HubContext`/`LockedEngine`), sync loop, routes, launchd, cli.
- `server.py`: `Handler` is now a module-level class reading `self.app`; `make_handler(app)` subclasses it. Single-project behaviour unchanged (all S02/S03 tests pass).
- `lemmata hub {serve,install,uninstall,status,pair-code,token,devices,revoke,config}` in `cli.py`.
- `app/tests/fake_github.py` (device flow, /user, /user/repos, smart-HTTP git via `git http-backend`, rejects git requests without the Basic auth header) and `app/tests/test_hub.py`.
- `engine/tree.py` `WorkTree.has/read/size` refuse absolute paths, escapes, symlinked components (threat-model must-fix 1).

## Verified
- `PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_*.py'` : 85 tests OK.
- Real run on Linux against the fake GitHub: pair, sign in (device flow), repo list, create project (clone), upload zip twice (checkpoint between, number changed) -> alarm group `ev:commit:paper:...` appears, sync after a new upstream commit -> `changed: true` and a code alarm group; MCP `initialize`, `tools/call alarms`, `notifications/initialized` (202) through `/mcp` with a CLI-issued token and the real `lemmata.mcp`.
- Not verifiable here: real GitHub (this box's proxy blocks github.com/login/device/code; two attempts returned a proxy message, no user_code), Tailscale detection, launchd.

## Deviations / decisions
- Token to git via env `GIT_CONFIG_COUNT/KEY/VALUE` scoped `http.<github_web>/.extraHeader` (not `-c`), per CTO list.
- Git protocols: `protocol.allow=never`, https only. `LEMMATA_GIT_ALLOW_HTTP=1` allows http only when `github_web` is loopback (tests/e2e only). Unit tests set `projects.ALLOWED_PROTOCOLS`.
- `--template=<hub/empty-template>` instead of `--template=.` (an empty dir; `.` would copy from the working directory).
- Bind = loopback + Tailscale IPs on separate sockets (not 0.0.0.0); refuses to start if `tailscale funnel status` shows "Funnel on" with the port. Without Tailscale it warns and listens on loopback only. Peer CIDR check kept.
- Pairing code lives in `hub/pairing.json` (0600) so `hub pair-code` (separate process) and the server share it.
- No per-project Watcher: all mutations go through the hub, which rescans after upload/sync.
- Name resolution for MCP: exact pid wins; an ambiguous name raises `BadRequest` listing pids.
- Hub pages get CSP + nosniff + no-referrer. The project UI has no inline script/style markup, so it is unaffected; not browser-tested (web-eng/QA to check).
- `hub status` probes the configured port, not a `--port` override passed to `serve`.
- Zip: NUL in names cannot be tested (zipfile truncates); the check stays. Empty re-upload creates an empty commit (a version).
- mcp `handle()` returns `(status, json string|None)`; routes write the string as-is, `None` -> empty body.

## Open for CTO/QA
- Code repo symlinks are checked out as plain files (`core.symlinks=false`); engine reads refuse symlinks anyway.
- Origin must be `http://<allowed host>:<hub port>`; a reverse proxy on another port would need `allow_hosts` plus a code change.

## QA round 1 fixes (2026-11-05)
D1 token line with `--scope user` plus warning; D2 strict Content-Length (negative/non-numeric/missing -> 400 in `_body`, `_mcp`, zip route; hub sockets time out after 30 s, zip stream 120 s); D3/D8 zip: NFC/NFKC, Cf-stripped, trailing dot/space and `git~N` aliases of `.git` rejected, Cf names rejected, duplicates after NFC+casefold, file-vs-folder clash, 50 MB per-file cap; upload is atomic (throw-away index + `commit-tree`, paper/ swapped only afterwards, backup restore on failure); D6 Tailscale watcher thread (15 s) binds late-appearing addresses and refreshes the Host allowlist, `Tailscale-Funnel-Request` -> 403; D7 zip/IO errors -> 400 and data paths masked (`<data>`); D9 stricter `code_repo` regex; D10 engine git env via `tree.GIT_ENV_EXTRA` (set by the hub only); D11 `hub.js pairedOf()` uses `authenticated`; D12 JSON 405 + CSP for any other method (`send_error`); D5 per-project `online_refs` (default false), `PATCH /api/hub/projects/<pid>`, checkbox in the projects list, check status `not_checked` ("References not checked online") when no entry was looked up; triage writes pass `by="ui:<device_id>"` (only when the engine accepts `by`), MCP ctx exposes `device_id`.
