# Lemmata for VS Code

Shows what Lemmata found in your ML paper and code where you edit: a status bar count, warnings on the exact lines, and a panel of alarms ("recheck this, something upstream changed") and findings (main text, appendix and references disagree).

The extension only talks to your own Lemmata hub (the Mac mini). No telemetry, no third-party servers.

## Install

The packaged file is `vscode/lemmata-0.1.1.vsix`.

- Command line: `code --install-extension vscode/lemmata-0.1.1.vsix`
- Or in VS Code: Extensions view -> `...` menu (top right) -> **Install from VSIX...** -> pick the file.

Requires VS Code 1.90 or newer and `git` on your PATH.

## Connect

1. On the Mac mini, create a token:
   `cd ~/work/lemmata-hub/app && uv run lemmata hub token --device "VS Code"`
   (it is shown once; copy it).
2. In VS Code: Command Palette -> **Lemmata: Connect to Server**.
3. Server: `http://100.111.135.94:8765` (the default). Token: paste it.

The token is kept in VS Code's secret storage (your OS keychain), never in settings or files. The server address is the setting `lemmata.serverUrl`. **Lemmata: Disconnect** forgets the token on this computer; `lemmata hub revoke` on the Mac mini kills it everywhere.

## Which project is this?

For every folder in your workspace the extension reads its git remotes and matches them against your hub projects:

- `github.com/<owner>/<name>` equals the project's code repository, so that folder is the **code** repo;
- the project's paper comes from GitHub: a folder whose remote is the **paper repo** (`paper_source.repo`) is the **paper** folder. If the paper is a folder inside the code repo (the hub shows "the folder paper/ in your code repo"), the code folder is also the paper folder, and `paper/main.tex` is opened at `<code folder>/paper/main.tex` (the subfolder name comes from the hub project).

Overleaf remotes are not matched any more. (Only a project that was set up with Overleaf in an older version keeps that match, from its own data.)

A hub path such as `code/configs/default.yaml` or `paper/main.tex` is mapped onto the folder that matched that repo. Paths of a repo you have not opened are listed in the panel but get no squiggle. To force a project, set `lemmata.project` to its hub project id.

## What you will see

- **Status bar**: `Lemmata: 5 to recheck` (click to open the panel), `Lemmata: offline` when the server cannot be reached (the last results stay visible).
- **Problems / squiggles** (source "Lemmata"):
  - alarms: Warning at the item's file and line, "Recheck: Table 2 - 9f1c2e7 change learning rate 3e-4 to 1e-3 (downstream of configs/default.yaml)", code `A1`, `A2`...
  - findings: Warning or Information at every evidence line, code = the check name.
  - items you marked **Reviewed** or **Ignore** disappear; **Needs fixing** shows as an Error.
- **Lemmata panel** (activity bar): Alarms (groups, then items) and Findings (by check). Click an item to open the file at the line. Right-click for **Mark Reviewed / Needs fixing / Ignore** (optional note), **Why?** (read-only document with the chain and the diff) and **Open in Lemmata** (the web page). Toolbar: **Refresh**, **Sync now** (pull your code and paper from GitHub on the server), **Set checkpoint**.
- Refresh runs every 30 s (`lemmata.refreshSeconds`), when the window gets focus and when you save a file.

## Troubleshooting

- **"Lemmata: offline"**: is the hub running on the Mac mini, and Tailscale connected on this computer? Test `curl http://100.111.135.94:8765/api/hub/status`.
- **"token rejected"**: the token was revoked or mistyped. Create a new one and run Connect again.
- **"no project"**: no workspace folder has a GitHub remote that matches the code repo or the paper repo of a hub project. Check `git remote -v`, or set `lemmata.project`.
- **Items in the panel but no squiggles**: the repo is not open in this workspace (the row says so), or the clone is on an older commit than the server's (pull, or Sync now on the server and pull).
- **Paper errors after Sync now**: the hub could not read the paper repo or folder (renamed, or you lost access). Reconnect it from the project page in Lemmata.
- Log: View -> Output -> "Lemmata". It never contains the token.

## Develop

```
cd vscode && npm install
npm run compile
npm test                    # unit tests (node's test runner)
npm run test:integration    # real hub + fake GitHub, needs python3 and git
npm run test:host           # optional: extension-host smoke test (downloads VS Code)
npx @vscode/vsce package    # -> lemmata-0.1.1.vsix
```
