---
type: adr
owner_agent: lead
status: proposed
sources:
  - "founder request and answers in chat, 2026-11-10 23:31 KST and 2026-11-11 (hosting: Mac mini + public tunnel; claims: Lemmata drafts, founder confirms; A/B: all four views; tools: timeline, feedback to tasks, digest, ledger). No file in raw/ yet"
  - "ADR-004-hub-on-mac-mini.md ; ADR-005-no-overleaf-paper-on-github.md ; ../architecture/threat-model.md"
  - "code on branch s07-public-site: app/src/lemmata/hub/{github.py, auth.py, guard.py, routes.py, projects.py, cli.py}, app/src/lemmata/engine/{claims.py, process.py}, app/tests/test_public.py"
  - "https://tailscale.com/docs/features/tailscale-funnel (fetched 2026-11-11: Funnel needs MagicDNS and HTTPS certificates; public ports 443, 8443, 10000; `tailscale funnel --bg <port>`; `tailscale funnel reset`)"
  - "https://tailscale.com/docs/reference/tailscale-cli/funnel (fetched 2026-11-11: --bg persists across restarts)"
last_reviewed: 2026-11-11
---
# ADR-006: A public, multi-user Lemmata site served from the Mac mini

Status: **proposed** (Juhyeong approves). Amends [ADR-004](ADR-004-hub-on-mac-mini.md): the hub was one owner, Tailscale only, pairing code. Setup: [docs/PUBLIC-SITE.md](../../docs/PUBLIC-SITE.md). Sprint: [S07 brief](../sprints/S07/S07-brief.md).

## Context
- Juhyeong wants to send a link to other researchers, who sign in with their own GitHub, connect their own repositories and use Lemmata in a browser. He chose to host it on the Mac mini behind a public tunnel (free, good for a lab pilot and the 2nd presentation).
- He reported having to sign out and in again when the repository picker said "GitHub is not connected". In the S06 code every 401 or 403 from GitHub (a revoked sign-in, a rate limit, an organisation rule) was mapped to that one message, the picker called GitHub on every keystroke, and the only way to renew a sign-in was to sign out. Which of these he hit on his machine is not known; all three are fixed.

## Decision
1. **Public mode is opt-in and set only on the Mac mini.** `lemmata hub config --public-url https://…`. Without it the hub behaves as in ADR-004 and still refuses Funnel requests. The value can never be set over HTTP (threat model M11 rule).
2. **Accounts are GitHub logins.** Sign-in on the public address uses the GitHub device flow (no client secret on the hub, as before) and needs no pairing code. Each account has its own token (`hub/users/<login>.json`, 0600); the owner's stays in `hub/github.json`. Pairing-code sessions are not accepted on the public address.
3. **Projects belong to one account.** Listing, opening, syncing, deleting and MCP access are filtered by owner; someone else's project answers 404, the same as a project that does not exist. Each project syncs with its owner's token. Projects made before S07 belong to the hub owner.
4. **Sign-up is invite-only by default** once a public URL is set (`--signup open` is available), with a cap on accounts (50) and projects per person (5), and rate limits on the unauthenticated sign-in endpoints.
5. **Sign-in choice:** "private and public repositories" (scope `repo read:user`) or "public repositories only" (`read:user`).
6. **Sign-in errors are told apart** (`github_token_invalid`, `github_rate_limited`, `github_forbidden`), the repository list is cached for two minutes per account, and **Reconnect GitHub** renews a sign-in inside the existing session. A reconnect approved as a different GitHub account is refused.
7. **No language model on the hub.** Claims, timeline, ledger, tasks, digest and Ask are rules over the LaTeX source, git history and the dependency graph. This keeps the CLAUDE.md rule "never route other users' work through Juhyeong's Max plan". Reasoning by a model happens in each person's own Claude Code over MCP, with a personal token they create under Account.
8. **A/B of the start view.** New accounts get claims / inbox / timeline / ask in turn. Events are counted per start view with the person stored as a salted hash; no file names, text or code. This is use of user data, so it needs Juhyeong's approval under CLAUDE.md; the landing page tells people what is counted.

## Consequences
- **Other people's private code is copied onto the Mac mini.** The hub never executes repository content and never pushes (unchanged), but the disk now holds third-party code and tokens. Anyone with access to the Mac mini's user account can read them.
- **The `repo` scope is broader than Lemmata needs.** It grants write access that Lemmata never uses. ADR-004 F2 (a GitHub App with `Contents: read`, chosen repositories only) is now a **must before any open sign-up**, not a later improvement. Registering a GitHub App is an action on Juhyeong's GitHub account.
- **Availability** is the Mac mini's: asleep or offline means the site is down.
- The Tauri app and the VS Code extension still use the private address and the pairing flow.

## Before you invite people (needs Juhyeong)
1. Approve this ADR and the A/B counting.
2. Keep `signup: invite` until the GitHub App replaces the OAuth app.
3. Turn on FileVault on the Mac mini and keep `~/Lemmata` out of cloud backups.
4. Tell invitees in one line what is stored and that they can delete their account (the landing page says it; say it in the invitation too).
5. Check Korea University's rules on storing other people's research code on a personal machine (compliance folder; not reviewed here).

## Not done in S07
- GitHub App (above). E-mail digests (Slack webhook only). Per-account disk quota beyond the 2 GB repository cap. Deleting a GitHub authorisation on GitHub's side when an account is deleted (the token is removed locally; the person revokes it under GitHub → Settings → Applications). QA by the QA agent: only the lead's own tests have run.
