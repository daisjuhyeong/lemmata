# Lemmata on two Macs: hub on the Mac mini, app on the MacBook

```
MacBook ── Tailscale ──► Mac mini (dais-juhyeongs-mac-mini:8765)
  Lemmata.app                  Lemmata hub (starts at login, keeps running)
  VS Code + Claude Code ──────►  /mcp
```
Both Macs must be signed in to the same Tailscale account (check: the Tailscale menu-bar icon shows "Connected" on both).

## 1. Mac mini: install the hub (once)
Needs `git`, `uv` (`brew install uv`) and the repo.
```
cd ~/work/lemmata && git fetch origin && git switch s04-hub-remote
cd app
uv run lemmata hub install      # starts now and at every login; data in ~/Lemmata
uv run lemmata hub status       # shows the address, e.g. http://dais-juhyeongs-mac-mini:8765
```
- macOS may ask whether Python may accept incoming network connections: click **Allow**.
- Logs: `~/Lemmata/hub/hub.log`. Stop/remove: `uv run lemmata hub uninstall`.
- After `git pull` with new code: `uv run lemmata hub uninstall && uv run lemmata hub install`.

## 2. Mac mini: get a pairing code (each time you add a device)
```
cd ~/work/lemmata/app && uv run lemmata hub pair-code
```
An 8-character code, valid for 10 minutes. From the MacBook you can also run it over SSH:
`ssh dais_juhyeong@dais-juhyeongs-mac-mini.local 'cd ~/work/lemmata/app && ~/.local/bin/uv run lemmata hub pair-code'`
(use `/opt/homebrew/bin/uv` if that is where uv lives).

## 3. MacBook: install the app
- **Download:** GitHub → `daisjuhyeong/lemmata` → Actions → the latest green **mac-app** run on `s04-hub-remote` → Artifacts → **Lemmata-macos-arm64** → open the `.dmg` → drag Lemmata to Applications.
- First launch: macOS blocks it once because it is not signed by Apple yet. System Settings → Privacy & Security → **Open Anyway** (or `xattr -dr com.apple.quarantine /Applications/Lemmata.app`).
- **Or build it on the MacBook:** install Rust once (`curl https://sh.rustup.rs -sSf | sh`), then `git clone -b s04-hub-remote https://github.com/daisjuhyeong/lemmata.git ~/lemmata && ~/lemmata/desktop/build-mac.sh` (about 10 minutes the first time).

## 4. MacBook: connect, pair, sign in, create a project
1. Open Lemmata → **Connect to Lemmata server** (prefilled `http://dais-juhyeongs-mac-mini:8765`) → Connect.
2. Enter the pairing code from step 2.
3. **Sign in with GitHub** → a code appears → **Open GitHub** → paste the code → Authorize "Lemmata (Juhyeong)". The first GitHub account to sign in becomes the hub's owner; no other account can sign in later.
4. **New project** → search `alarm-analyzer-eval` → pick it → drop the Overleaf zip (Overleaf: Menu → Download → Source) → **Create project**.
5. Later: **Upload paper zip** after each Overleaf edit you want tracked (each upload is a paper version on the timeline); code updates are pulled from GitHub every 5 minutes, or press **Sync now**.
6. References are checked offline by default. To look them up online (sends only bibliography titles/DOIs to OpenAlex and Crossref), turn on "Check references online" for the project.

## 5. VS Code + Claude Code: let Claude ask Lemmata
On the Mac mini (or over SSH), create a token for VS Code; it prints the full command:
```
cd ~/work/lemmata/app && uv run lemmata hub token --device "VS Code"
```
On the MacBook, run the printed line, which looks like:
```
claude mcp add --scope user --transport http lemmata http://dais-juhyeongs-mac-mini:8765/mcp --header "Authorization: Bearer <token>"
```
The token gives full access to the hub: keep it only in Claude Code's config. Revoke with `uv run lemmata hub devices` and `uv run lemmata hub revoke <device_id>`.

Then in Claude Code (VS Code), with your `alarm-analyzer-eval` checkout open, try:
1. "Use lemmata: list my projects and tell me which one has the most things to recheck."
2. "What does lemmata say I need to recheck after my last commit? Open the affected files in this repo."
3. "Explain with lemmata why Table 2 is flagged, show me the diff, and tell me whether the result file needs regenerating."
4. "Show lemmata's main_appendix_mismatch findings and fix the appendix value in my LaTeX so it matches the main text (ask me first which one is right)."
5. "Sync the project with lemmata, then mark Table 2 as needs_fixing with the note 'rerun with lr 1e-3'."

## If something doesn't work
| Symptom | Fix |
|---|---|
| App: "Can't reach the Mac mini" | Mac mini awake? Tailscale connected on both? `uv run lemmata hub status` on the mini; check `~/Lemmata/hub/hub.log` |
| Pairing code rejected | Codes expire after 10 minutes and lock after 5 wrong tries; make a new one |
| GitHub sign-in says the code expired | Click Retry; codes last about 15 minutes |
| `claude mcp list` shows lemmata failing | Token revoked or mistyped; make a new one with `hub token` |
| Repo list empty | Signed in with the wrong GitHub account; Sign out and sign in as daisjuhyeong |
