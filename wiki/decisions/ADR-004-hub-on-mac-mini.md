---
type: adr
owner_agent: cto
status: proposed
sources:
  - "../sprints/S04/S04-brief.md (lead, 2026-11-05; founder decisions 1-4 and the hub/MCP contract are normative there)"
  - "founder decisions in chat, 2026-11-05 18:09 KST (relayed by the lead; no file in raw/ yet)"
  - "ADR-003-macos-desktop-app.md ; ADR-002-localhost-demo.md ; ../architecture/desktop-architecture.md ; ../architecture/threat-model.md"
  - "code on branch s04-hub-remote, read 2026-11-05: app/src/lemmata/{server.py, engine/tree.py, engine/latex.py}; app/src/lemmata/hub/ does not exist yet"
  - "https://tailscale.com/kb/1312/serve ; https://tailscale.com/kb/1223/funnel ; https://tailscale.com/kb/1018/acls"
  - "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps ; https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app"
  - "https://modelcontextprotocol.io/specification/2025-06-18/basic/transports (Streamable HTTP, Origin validation)"
  - "https://git-scm.com/docs/git-config (core.hooksPath, core.symlinks, protocol.allow, http.<url>.extraHeader, GIT_CONFIG_COUNT)"
last_reviewed: 2026-11-05
---
# ADR-004: Lemmata hub on the Mac mini, reached over Tailscale

Status: **proposed** (Juhyeong approves). Amends [ADR-003](ADR-003-macos-desktop-app.md) (see "What this changes in ADR-003"). Companion page: [threat model](../architecture/threat-model.md). The contract is fixed by the lead in the [S04 brief](../sprints/S04/S04-brief.md). This ADR records it, gives the reasons and lists the changes I need before it ships. Changes are marked **(must-fix)** or **(proposal)**; both need the lead's OK and a note to QA.

Note on sources: I could not re-fetch the documentation URLs in this session. Claims that rest only on them are marked *verify*.

## Context
- Founder decisions of 2026-11-05 (brief): the app runs on the MacBook, the engine runs on the Mac mini as an always-on service, the network is Tailscale (installed on both), sign-in is GitHub only, inputs are a GitHub repo plus an uploaded Overleaf zip, and Claude Code in VS Code queries Lemmata over MCP.
- Until S03 the server bound **127.0.0.1 only** and touched only the user's own folders (ADR-002 Decision 8, ADR-003 "Security and privacy"). S04 is the first time Lemmata (a) listens on a network interface, (b) holds a credential (a GitHub token), (c) fetches and parses repositories that other people may have written, and (d) returns that text to an LLM agent that can run commands on the MacBook. The threat model is new, not a delta.
- Users: one owner (Juhyeong). The hub is single-owner by design. Letting any other person use Juhyeong's hub would be "use of user data" (CLAUDE.md) and needs his approval; it is out of scope here.
- Deadline: the 2nd presentation (MVP demo). The single-project app and CLI from S03 keep working and remain the fallback.

## Options
| Option | For | Against |
|---|---|---|
| **K. Keep local** (S03 app, engine on the MacBook) | Zero new attack surface; already built; no credential stored | Fails founder decision 1. The MacBook does the scan work and must stay awake for sync. No shared state for Claude Code across machines |
| **S. SSH tunnel** (`ssh -L 8765:127.0.0.1:8765 mini`; hub binds loopback) | Hub never listens on a network interface. Auth is the SSH key | The tunnel must be up before the app and Claude Code can connect; the Tauri app would have to manage an ssh child. Remote Login has to be enabled on the mini. "Connect to server" becomes "start a tunnel", which fails the "inputs must be simple" goal. Any local process on the MacBook can use the forwarded port |
| **T. Plain HTTP on the tailnet, app-level pairing + session tokens** (brief) | Matches the founder decisions. WireGuard encrypts the link, so plain HTTP is not sniffable. No extra processes. Pairing gives per-device revocation. Works for Claude Code with a Bearer header | The hub listens on a socket and does its own network guard, Host/Origin checks, CSRF defence and token store. Plain `http://` means no `Secure` cookies and a non-secure browser context |
| **TS. Tailscale Serve** (hub binds 127.0.0.1; `tailscale serve` gives `https://<mini>.<tailnet>.ts.net`) | HTTPS with a real certificate; nothing listens on 0.0.0.0; Serve adds `Tailscale-User-Login` identity headers that could replace pairing (*verify*) | Needs HTTPS certificates enabled for the tailnet and a Serve config on the mini (setup steps outside our CLI). Identity headers are forgeable by any local process that talks to the loopback port, so pairing tokens are still needed. Changes the URL engineers are building against |
| **TF. Tailscale Funnel** | Reachable from anywhere | Puts the hub on the **public internet**. Rejected outright |
| **H. Hosted backend** (cloud VM / PaaS) | Reachable without Tailscale; path to a multi-user product | Spending, a server holding manuscripts and GitHub tokens of users (user data, publishing: all need Juhyeong's approval), an ops burden, and a contradiction with the product promise that the author's work stays on the author's machines (CLAUDE.md "Runtime"). Not before launch |

## Decision
1. **Option T, as in the brief**, with the must-fix items below. TS is recorded as follow-up F1, because it removes the 0.0.0.0 listener and gives HTTPS, but it changes the URL and setup mid-sprint.
2. **Listen on the Tailscale address(es) and loopback, not 0.0.0.0** (must-fix, changes the brief). Binding 0.0.0.0 opens the port on the LAN and on any other interface, and the peer-range check is then the only guard. `100.64.0.0/10` is also the RFC 6598 shared space that some ISPs and routers use on the LAN side, so the range check alone can admit non-Tailscale peers. Detect the Tailscale IPs at start via `tailscale status --json` (as the brief already does for Host names); if Tailscale is not up yet (launchd starts before tailscaled has an address), retry every 5 s and serve loopback only meanwhile. Keep the peer check as a second layer.
3. **Refuse to run behind Funnel** (must-fix). Serve/Funnel traffic reaches the hub from 127.0.0.1 with `Host: <mini>.<tailnet>.ts.net`, which the brief's allow-list accepts, so the loopback exception would let internet traffic through to the pairing endpoint. At start, `tailscale funnel status --json` (or `serve status`): if any handler targets our port with Funnel on, log an error and exit. Also reject requests carrying the `Tailscale-Funnel-Request` header (*verify* header name).
4. **GitHub token: `repo` scope is accepted for S04 only** (the owner's own hub, the owner's own repos). OAuth Apps have no read-only scope for private repositories; `repo` grants **write** to code, collaborators and webhooks of every repo the owner can reach (GitHub scopes doc, *verify*). Before anyone other than Juhyeong signs in, or before the 3rd presentation (launch), replace it with a **GitHub App** with `Contents: read` and `Metadata: read` and device flow enabled (F2). Until then, the token must never leave the hub process except as an HTTP header to the configured GitHub host (threat model M4).
5. **Git runs hardened** for every clone/fetch/commit (must-fix): the token goes in via environment (`GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n`), scoped to the GitHub URL, not as `-c` on the command line; hooks off; symlinks checked out as plain files; no submodules; https only; LFS smudge off. Exact flags: [threat model §5](../architecture/threat-model.md).
6. **Engine file access is confined to the project root** (must-fix): `Tree.has`/`Tree.read` reject absolute paths, `..` components and any path whose `realpath` leaves the root. Today `WorkTree.read` (`engine/tree.py`) opens `os.path.join(root, path)` and follows symlinks, and `_resolve_input` (`engine/latex.py`) normalises `\input{../../x}` to a path outside the root. On the hub that means a repo can make Lemmata display `~/Lemmata/hub/github.json` in the UI and over MCP.
7. **MCP: Bearer only, Origin checked, write tools marked.** Keep the brief's "cookie not accepted on /mcp". Add: reject a request whose `Origin` header is present and not allowed (MCP spec requirement against DNS rebinding); read tools carry `annotations.readOnlyHint: true`; `set_triage` and `sync` carry `readOnlyHint: false` so Claude Code asks before calling them; every triage change records `by: "mcp:<device_id>"`.
8. **The setup line uses `--scope user`** (must-fix): `claude mcp add --scope user --transport http lemmata http://dais-juhyeongs-mac-mini:8765/mcp --header "Authorization: Bearer <token>"`. With `--scope project` the token would be written to `.mcp.json` inside the repo and pushed to GitHub.
9. **Single owner.** The first GitHub login binds the owner (brief). Hub data, tokens and projects are never shared with another person without Juhyeong's approval.

## Consequences
- **Availability.** A LaunchAgent in `gui/<uid>` only runs while Juhyeong is logged in on the mini. After a power cut the hub stays down until someone logs in (FileVault blocks auto-login). Acceptable for a demo; say so in the launcher's "Can't reach the Mac mini" text. A LaunchDaemon would run at boot but as root or a separate user, which needs its own review (F4).
- **macOS firewall.** If the application firewall is on, the first listen by the (unsigned) `python` in `sys.executable` may raise an "accept incoming connections" prompt on the mini's screen, which nobody sees on a headless mini (*verify* on the mini). QA checks this once on the real mini.
- **Cookies on the first navigation.** `SameSite=Strict` cookies are not sent on the top-level navigation from the Tauri launcher (`tauri://`) to `http://<mini>:8765/`. The hub page must decide "paired or not" with a `fetch('/api/hub/status')` after load (same-site, cookie sent), not from the navigation response, or the user will be asked to pair on every connect.
- **New data at rest on the mini:** manuscripts (`paper/`), code clones, the GitHub token, hashed session tokens, logs. They end up in Time Machine backups of the mini unless `~/Lemmata/hub/` is excluded (proposal: `tmutil addexclusion ~/Lemmata/hub` in `hub install`).
- **New data at rest on the MacBook:** the hub cookie (WebKit store of Lemmata.app) and the MCP Bearer token in plain text in `~/.claude.json` (Claude Code's user config). Both are revocable with `lemmata hub revoke`.
- **Engineering cost of the must-fix list:** about one engineer-day, almost all in `hub/` and `engine/tree.py`; no change to API shapes. If S04 runs late, the cut order (first cut → last) is: background 5-min sync loop (keep Sync now) → `sync` MCP tool → `set_triage` MCP tool → Tauri auto-reconnect → MCP entirely → hub mode entirely (demo on the S03 app). **Security must-fix items are not on the cut list**: if they are not done, hub mode does not ship.

## What this changes in ADR-003
- **Superseded in hub mode only:** ADR-003 "Security and privacy": "the server still binds 127.0.0.1 only" and "No network, unless the user opts in to `--online`". In hub mode the server listens on the Tailscale interface, and the hub makes outbound calls to GitHub (API + git over HTTPS) by design.
- **Superseded in hub mode only:** Decision 7 (navigation pinned to `127.0.0.1:<port>`). The window may also show the configured hub origin (exact scheme, host and port); everything else still opens in the default browser. The hub origin gets **no Tauri capability**, as Decision 6 already requires for the sidecar origin.
- **Closed for hub mode:** follow-up F6 (per-launch API token) is met by pairing tokens. It stays open for the local sidecar.
- **Unchanged:** single-project mode and the sidecar contract, the S03 cut order, signing, arm64, R1-R11. The writes-only-under-`.lemmata/` rule still holds for user folders; on the hub, Lemmata owns `~/Lemmata/` and writes the clones and the `paper/` repo there.

## Follow-ups
- F1. Tailscale Serve (HTTPS, loopback bind) instead of a tailnet listener. Its own small ADR.
- F2. GitHub App with read-only contents instead of the OAuth App `repo` scope. Required before launch. Note: GitHub App user tokens expire after 8 h by default and the refresh request needs the client secret (*verify*), so either opt out of expiry in the App settings or keep the secret on the mini only.
- F3. Bind requests to Tailscale identity (`tailscale whois <peer>` via the local API) and accept only peers owned by the owner's Tailscale login.
- F4. LaunchDaemon under a dedicated `_lemmata` user so a compromise of the hub is not a compromise of Juhyeong's login account.
- F5. Session token expiry (for example 90 days idle) and `hub token --expires`.

## Open questions for Juhyeong
1. Approve ADR-004, including "`repo` scope for S04 only, GitHub App before launch".
2. Is anyone else in your tailnet (other users, shared nodes)? If yes, the ACL in the threat model §6 is a must-do before the hub runs.
3. Is FileVault on the mini? (It decides whether the hub can come back after a power cut without you.)

## Approved by
(pending — Juhyeong, date)
