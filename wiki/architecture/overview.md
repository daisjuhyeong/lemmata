---
type: architecture
owner_agent: cto
status: proposed
sources:
  - "../sprints/S06/S06-brief.md (lead, 2026-11-06) ; ../sprints/S05/S05-brief.md ; ../sprints/S04/S04-brief.md ; ../sprints/S03/S03-brief.md"
  - "../decisions/ADR-003-macos-desktop-app.md ; ../decisions/ADR-004-hub-on-mac-mini.md ; ../decisions/ADR-005-no-overleaf-paper-on-github.md"
  - "threat-model.md (assets, M1-M11) ; desktop-architecture.md ; data-model.md"
  - "code on branch s06-obsidian-ui, read 2026-11-06: app/src/lemmata/hub/{config.py (DataDir, DEFAULTS), launchd.py (LABEL ai.lemmata.hub, RunAtLoad, KeepAlive), guard.py (bind_addresses), cli.py (cmd_token), projects.py}, vscode/package.json (lemmata.serverUrl default, application scope), vscode/src/core/remotes.ts, desktop/src-tauri/src/server.rs"
  - "../../docs/SETUP-two-macs.md ; ../../vscode/README.md"
  - "https://raw.githubusercontent.com/wiki/James-Yu/LaTeX-Workshop/Compile.md ; https://raw.githubusercontent.com/wiki/James-Yu/LaTeX-Workshop/View.md (fetched 2026-11-06)"
last_reviewed: 2026-11-06
---
# Architecture overview: the whole system after S06

This page shows the whole system on one picture, for anyone new to the project. Decisions and reasons: [ADR-003](../decisions/ADR-003-macos-desktop-app.md) (desktop app), [ADR-004](../decisions/ADR-004-hub-on-mac-mini.md) (hub on the Mac mini), [ADR-005](../decisions/ADR-005-no-overleaf-paper-on-github.md) (paper on GitHub, no Overleaf). Details:
- API shapes: [data-model.md](data-model.md)
- app internals: [desktop-architecture.md](desktop-architecture.md)
- attacks and mitigations: [threat-model.md](threat-model.md)
- step-by-step install: [SETUP-two-macs](../../docs/SETUP-two-macs.md)

State: this is the system **as S06 specifies it**. On 2026-11-06 the GitHub paper source (S06 §A) is in progress and the Obsidian-style UI (S06 §B) is not built yet. Overleaf is switched off (`overleaf_enabled=false`) and is not drawn.

## Diagram
```
 MacBook (Juhyeong edits here)                                           GitHub (github.com)
┌──────────────────────────────────────────────────────────┐          ┌───────────────────────────────┐
│ VS Code                                                  │ (1) push │ daisjuhyeong/alarm-analyzer-  │
│  ├─ paper repo clone  (~/work/www27-paper)               │─────────►│   eval        code repo       │
│  │    LaTeX Workshop ── latexmk ── MacTeX/BasicTeX       │  (own    │ daisjuhyeong/www27-paper      │
│  │    build on save -> PDF tab, SyncTeX  (all local)     │   git/gh │   paper repo (private)        │
│  ├─ code repo clone   (~/work/alarm-analyzer-eval)       │   creds) │   (or paper/ inside code repo)│
│  ├─ Lemmata extension  -- squiggles, panel, triage --┐   │          │ OAuth App "Lemmata (Juhyeong)"│
│  └─ Claude Code  ── MCP client ─────────────────────┐│   │          │   device-flow sign-in         │
│                                                     ││   │          └──────────────┬────────────────┘
│ Lemmata.app (Tauri) -- window onto the hub pages -┐ ││   │                         │ (2) hardened fetch,
│   (local sidecar mode still there: ADR-003)       │ ││   │                         │ every 5 min or Sync now,
└───────────────────────────────────────────────────┼─┼┼───┘                         │ with the hub's token
          (5) cookie session (pages, /api)          │ ││ (5) Bearer /p/<pid>/api/*   │
                    (5) Bearer /mcp ────────────────┼─┘│                             │
                                                    ▼  ▼                             ▼
   ═══════════ Tailscale tailnet (WireGuard). Hub = http://100.111.135.94:8765. MagicDNS off. Funnel off ═══════
                                                    │
┌───────────────────────────────────────────────────▼──────────────────────────────────────────────────────┐
│ Mac mini: Lemmata hub  (`python -m lemmata hub serve`, LaunchAgent ai.lemmata.hub, KeepAlive)            │
│   listens on 127.0.0.1 + 100.111.135.94 :8765 only   ·   guard: Host/Origin, pairing, sessions          │
│   sync loop ── (3) rescan engine ── alarms + findings ── (4) served to app / extension / MCP            │
│   ~/Lemmata/  hub/ (config, github.json, tokens.json, hub.log)                                           │
│               projects/<pid>/ code/  paper/  paper.prev-*/  .lemmata/ (triage, checkpoints, scans)       │
│   optional, per project: reference titles/DOIs -> OpenAlex, Crossref ("Check references online")         │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Components
**MacBook: Lemmata.app.**
- What it is: the Tauri v2 shell from ADR-003 (bundle `ai.lemmata.app`, arm64, ad-hoc signed).
- In hub mode it is a window onto the hub's pages, `http://100.111.135.94:8765/` (projects list) and `/p/<pid>/` (one project). It talks to the hub with a session cookie it got by pairing once.
- It stores only the server address (`~/Library/Application Support/ai.lemmata.app/server.json`) and the WebKit cookie store.
- The hub page has no Tauri IPC, so a bug in the web UI cannot reach the MacBook's files (ADR-003 Decision 6).
- The old single-project mode (local Python sidecar on `127.0.0.1:<random>`) remains as the offline and presentation fallback.
- Known gap: the app's built-in default address is still the MagicDNS name. Type the IP until it is changed (ADR-005, Engineering).

**MacBook: VS Code with LaTeX Workshop.**
- This is where the paper is written and compiled (ADR-005). LaTeX Workshop runs `latexmk` (its default recipe) against MacTeX or BasicTeX.
- It builds on save, shows the PDF in a VS Code tab, and links source and PDF with SyncTeX: ⌘⌥J goes from the cursor to the PDF; Ctrl-click or double-click in the PDF goes back to the source.
- Compiling never leaves the MacBook and the hub never runs TeX.
- Caveat: `latexmk` executes a repo's `.latexmkrc`, so a co-author's repo can run code on the MacBook on build (ADR-005).

**MacBook: the Lemmata extension.**
- It shows the hub's alarms and findings where you edit:
  - a status-bar count;
  - warnings on the exact line;
  - a panel with Mark checked / Needs fixing / Ignore, Why? and Sync now.
- Every 30 s, on focus and on save, it reads `/p/<pid>/api/alarms` and `/findings` with a Bearer token.
- The token sits in VS Code SecretStorage (the macOS keychain), bound to the server origin. The address is the machine-wide setting `lemmata.serverUrl` (default `http://100.111.135.94:8765`; a repo's `.vscode/settings.json` cannot change it).
- It finds the project by matching a workspace folder's git remote to the hub project's repos. After S06 it must also match the GitHub **paper** repo and the `subdir` case (ADR-005 must-fix; today it matches only Overleaf remotes for the paper).

**MacBook: Claude Code + MCP.**
- Claude Code runs in VS Code on Juhyeong's own Claude plan.
- It reaches the hub's MCP endpoint `http://100.111.135.94:8765/mcp` with a Bearer token, registered with `claude mcp add --scope user`, so the token lives in `~/.claude.json` and never in a repo's `.mcp.json`.
- Read tools (projects, alarms, findings, why) are marked read-only. `set_triage` and `sync` are write tools that Claude Code asks about before calling (ADR-004 Decision 7).
- Claude can edit the `.tex` and code files in the same window. Lemmata itself never calls a model.

**Mac mini: the Lemmata hub.**
- The always-on engine. It is the Python package `lemmata`, started as `hub serve` by the LaunchAgent `ai.lemmata.hub` (`~/Library/LaunchAgents/ai.lemmata.hub.plist`, RunAtLoad + KeepAlive). It therefore runs while Juhyeong is logged in on the mini (ADR-004).
- It listens on loopback and its Tailscale address only, never `0.0.0.0`, and refuses to run behind Funnel.
- For each project it keeps two hardened git clones, `code/` and `paper/` (hooks off, symlinks as files, https only, token in env scoped to github.com; threat model M4, M5). When the paper is a folder of the code repo, `paper/` is a second clone of the code repo and the paper root is the subfolder.
- It pulls both every 5 minutes or on Sync now, rescans, and computes:
  - **alarms**: "this changed; these things rest on it";
  - **findings**: main text vs appendix vs references.
- It stores triage and checkpoints under `projects/<pid>/.lemmata/` and serves the web UI, the REST API and MCP.
- All data lives under `~/Lemmata/` (0700).

**GitHub.**
- It holds the two repos:
  - the **code repo** (`daisjuhyeong/alarm-analyzer-eval`);
  - the **paper repo**, its own private repo such as `daisjuhyeong/www27-paper` (recommended), or a `paper/` folder in the code repo.
- It also provides **sign-in**: the hub uses GitHub's device flow with the public OAuth App client id (no client secret exists). The first account that signs in becomes the hub's only owner.
- The resulting token has `repo` scope for now, until the GitHub App with read-only contents replaces it (ADR-004 F2). It lets the hub list and clone both repos.
- The hub only reads from GitHub. It never pushes. Pushes come from the MacBook with Juhyeong's own credentials.
- GitHub Actions also builds the app's `.dmg` (`mac-app` workflow).

**Tailscale.**
- A private WireGuard network between the two Macs, signed in to the same Tailscale account.
- The hub's address is **`http://100.111.135.94:8765`**. MagicDNS is off on this tailnet, so names like `dais-juhyeongs-mac-mini` do not resolve and the IP is what works everywhere (S05 brief §3).
- Plain HTTP is acceptable because the tunnel is encrypted. The hub's own pairing and tokens are still required, because any device on the tailnet can reach the port (threat model T15; ACLs in §6).
- Funnel must stay off. The hub checks for it and exits.

## Data flows
1. **Edit → push** (MacBook → GitHub). Edit `.tex` or code in VS Code, save (the PDF rebuilds locally), commit, push. Only pushed commits exist for Lemmata.
2. **Hub sync** (GitHub → Mac mini). Every 5 minutes, or on Sync now from the app, the extension or Claude, the hub runs a hardened `git fetch` of `code/` and `paper/` with its GitHub token and fast-forwards. A zip upload (fallback) instead commits into `paper/`.
3. **Rescan → alarms.** The engine re-reads the trees, rebuilds the graph (paper items ↔ result files ↔ scripts ↔ configs), compares against the last checkpoint and produces alarms and findings. Optional: reference titles and DOIs go to OpenAlex and Crossref, only if "Check references online" is on.
4. **Look when needed** (Mac mini → MacBook, over Tailscale):
   - the app shows "Changes since you last looked" (S06 UI);
   - the extension underlines the affected lines;
   - Claude Code answers "what do I need to recheck?" over MCP.
5. **Triage back** (MacBook → Mac mini). Mark checked / Needs fixing / Ignore, Set checkpoint and Sync now from any of the three are written on the hub. MCP changes are recorded as `by: "mcp:<device_id>"`. Nothing flows back to GitHub.
6. **Sign-in and pairing (once).**
   - Pairing: the app enters a pairing code made on the mini (`lemmata hub pair-code`) and gets a session.
   - GitHub sign-in: you approve "Lemmata (Juhyeong)" on github.com in a browser on the MacBook, and the hub stores the token.
   - The extension and Claude Code get device tokens from `lemmata hub token --device …` on the mini.

## What runs where
| Machine | Runs | Never runs |
|---|---|---|
| MacBook | Lemmata.app, VS Code + LaTeX Workshop + TeX, the Lemmata extension, Claude Code, git/`gh`, Tailscale | The hub (except the old single-project sidecar mode) |
| Mac mini | Lemmata hub (LaunchAgent), git, Tailscale | TeX, repo scripts, hooks, any code from the repos; model calls |
| GitHub | Repo hosting, OAuth sign-in, Actions build of the app | Anything of Lemmata's analysis |

## Where secrets live
| Secret | Where | Notes |
|---|---|---|
| GitHub token for the hub (`repo` scope) | Mac mini `~/Lemmata/hub/github.json` (0600, dir 0700) | Passed to git through env only, scoped to github.com. Keychain storage is threat model N1 |
| Device/session tokens | Hashes in `~/Lemmata/hub/tokens.json` (mini). Plaintext in the MacBook's WebKit store (app cookie), VS Code SecretStorage (extension) and `~/.claude.json` (Claude Code, user scope) | Revoke with `lemmata hub devices` / `hub revoke <id>` on the mini |
| Pairing code | CLI output on the mini, `hub.log` | 8 characters, 10 minutes, 5 tries |
| Juhyeong's own git/`gh` credentials | MacBook (macOS keychain via `gh auth login` / git credential helper) | Used for pushing. The hub never sees them |
| Overleaf Git token (dormant) | `~/Lemmata/hub/overleaf.json`, only if one was saved in S05 | Delete it and revoke it at Overleaf (ADR-005) |
| Tailscale node keys | Tailscale app on each Mac | Managed by Tailscale |
| OAuth client id | `config.py` default | Public, not a secret |
