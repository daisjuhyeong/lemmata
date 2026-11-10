# Lemmata as a website other people can sign in to

The hub on the Mac mini can serve a public HTTPS address. People open the link, sign in with their own GitHub account, pick their own repositories and use Lemmata in the browser. No app, no Tailscale and no pairing code on their side. Your private hub address (`http://100.111.135.94:8765`) keeps working as before.

Decision record and risks: `wiki/decisions/ADR-006-public-multi-user-site.md`. Read its "Before you invite people" list first.

## 1. Update the hub (Mac mini)
```
cd ~/work/lemmata && git fetch && git checkout s07-public-site && git pull
launchctl kickstart -k gui/$(id -u)/com.lemmata.hub      # or stop and start `uv run lemmata hub serve`
```

## 2. Give the Mac mini a public HTTPS address
Pick one. Both forward to the hub on `127.0.0.1:8765`; the hub itself still listens only on loopback and Tailscale.

**A. Tailscale Funnel (free, stable address).** Funnel needs MagicDNS and HTTPS certificates switched on for the tailnet (Tailscale admin console → DNS). MagicDNS is currently off on yours, so turn both on first. Then on the Mac mini:
```
tailscale funnel --bg 8765
```
The command prints the address, for example `https://dais-juhyeongs-mac-mini.<tailnet>.ts.net`. Use that exact address in step 3. To stop: `tailscale funnel reset`.

**B. Cloudflare Tunnel.** `brew install cloudflared`, then `cloudflared tunnel --url http://127.0.0.1:8765` prints a `https://….trycloudflare.com` address. That quick address changes every time the tunnel restarts, so it suits a demo, not a link you hand out. A fixed address needs a domain on Cloudflare and a named tunnel.

## 3. Tell the hub its public address and who may sign in
```
cd ~/work/lemmata/app
uv run lemmata hub config --public-url https://<the address from step 2>
uv run lemmata hub config --invite their-github-name --invite another-name     # sign-up is invite-only by default
launchctl kickstart -k gui/$(id -u)/com.lemmata.hub
```
- `--signup invite` (default once a public URL is set): only you and the GitHub names you invited.
- `--signup open`: anyone with the link, up to `--max-users` (default 50). Each person can have 5 projects.
- `--public-url off`: private again. Also run `tailscale funnel reset`.

The first GitHub account that ever signed in to the hub (yours) stays the owner. Check with `uv run lemmata hub status` and `uv run lemmata hub users`.

## 4. What people see
1. The link opens a page that says what Lemmata is, how it works and what it stores.
2. **Sign in with GitHub**: they choose "private and public repositories" or "public repositories only", get a code, approve it on GitHub.
3. A short tutorial, ending with "How should Lemmata help you first?" (Claim map, Recheck inbox, Research timeline, Ask).
4. **New project**: pick the code repository, then the paper (a repository, a folder in the code repository, or the Overleaf source as a zip).
5. The project opens on the view they chose.

## 5. Staying signed in
- The browser session lasts a year. Signing out is never needed to fix GitHub problems.
- If GitHub stops accepting someone's saved sign-in (they revoked it, or an organisation expired it), the Projects page and the repository picker show **Reconnect GitHub**. It takes a few seconds, keeps the session and the half-filled form, and refuses a different GitHub account.
- A GitHub rate limit or an organisation's access rule is reported as that, with the wait time, not as "not connected".
- The repository list is cached for two minutes, so typing in the search box does not call GitHub.

## 6. Comparing the four start views (A/B)
Each new account is given one start view in turn, so the four groups stay the same size. People can change it in the tutorial or under Account; that change is recorded too. Lemmata counts, per start view: people, who made a project, confirmed a claim, added feedback, asked a question, changed their view, came back another day, and the answer to "Is this view helping?".
```
uv run lemmata hub ab          # table on the Mac mini
```
The same table is on the site under your name → Account (owner only). People are stored as a short hash, never by name, in `~/Lemmata/hub/events.jsonl`; no file names, text or code are recorded. With a handful of users the differences mean little: treat it as a prompt for interviews.

## 7. Their own Claude Code
Under Account, anyone can create a personal token and gets a ready command:
```
claude mcp add --scope user --transport http lemmata https://<address>/mcp --header "Authorization: Bearer <token>"
```
Their Claude Code then reads their Lemmata projects (claims, timeline, experiments, tasks, alarms) on their own plan. Lemmata itself calls no AI model.

## If something doesn't work
| What you see | Cause | Fix |
|---|---|---|
| "host not allowed" on the public address | `public_url` does not match the address in the browser, or the hub was not restarted | repeat step 3 with the exact address |
| The public address shows the pairing-code page | same as above | same |
| "This Lemmata site is invite-only" | their GitHub name is not on the list | `lemmata hub config --invite name`, restart |
| Hub refuses to start: "Tailscale Funnel exposes port…" | Funnel is on but no `public_url` is set | set it (step 3) or `tailscale funnel reset` |
| An organisation repository is missing from the list | the organisation restricts OAuth apps | an org owner approves "Lemmata (Juhyeong)", then "Refresh the list from GitHub" |
