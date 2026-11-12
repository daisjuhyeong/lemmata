# Lemmata for VS Code

Shows what Lemmata found in your ML paper and code where you edit: a status bar count, warnings on the exact lines, and a panel of alarms ("recheck this, something upstream changed") and findings (main text, appendix and references disagree).

Since 0.2.0 it also **logs the experiments you run**, because most of them never reach GitHub: commands in the integrated terminal, result files written by detached jobs, and commands run by Claude Code. See "Runs" below and `docs/RUN-CAPTURE.md` for the step-by-step set-up.

The extension only talks to your own Lemmata hub (the Mac mini). No telemetry, no third-party servers.

## Install

The packaged file is `vscode/lemmata-0.4.0.vsix`.

- Command line: `code --install-extension vscode/lemmata-0.4.0.vsix`
- Or in VS Code: Extensions view -> `...` menu (top right) -> **Install from VSIX...** -> pick the file.

Requires VS Code 1.93 or newer and `git` on your PATH. Run capture from the terminal needs VS Code's shell integration (on by default for bash, zsh, fish and PowerShell).

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

## The Lemmata tab (since 0.3.0)

**Lemmata: Open Lemmata (in a tab)**, or the button at the top of the panel, opens the hub's own pages inside VS Code: Review, the Claims tree, Experiments, Timeline, Tasks, Notation, Changes and the graph. **Open Review**, **Open Claims tree** and **Open Experiments** go straight to one page. It is the same app as the website, so what you edit here (a hoped conclusion, a confirmed claim, a checklist item) is saved on the hub.

- **It works over Remote-SSH.** The page has no network access of its own. Every request it makes is passed to the extension, which calls the hub with your token. Only the extension needs to reach the hub.
- **The token never enters the page**, and the page can only reach its own project: requests for other projects, tokens, devices or users are refused by the extension.
- File pages have an **Open in editor** link that opens the file beside the tab when its repository is open in the window. `.md` downloads open as a document; pictures open in an editor tab; web links open in your browser.
- The tab is at least 1024 px wide inside; in a narrower editor column it scrolls sideways.
- It needs a hub that has this change (the tab says so when the hub is older). After a hub update, close the tab and open it again to get the new pages.

## Runs

The **Runs** list (below "Alarms and findings") shows every experiment logged in this repository, newest first: the command, the commit (`+changes` when the tree had uncommitted edits), the numbers it wrote, and whether the record has been sent to the hub. Click a run to open its record.

Three sources write the same record, one JSON file per run in `<repo>/.lemmata/runs/`:

| Source | What it catches | How |
|---|---|---|
| Terminal | Commands you type in the integrated terminal (`python train.py`, `sbatch job.sh`, `bash run.sh`, also behind `cd x &&`, `uv run`, `CUDA_VISIBLE_DEVICES=0`) | VS Code shell integration: command, folder, exit code |
| Results watcher | Jobs that end outside the terminal (tmux, sbatch, overnight) | A metrics file appears or changes in a results folder |
| Coding agent | Commands Claude Code runs | A hook installed by **Lemmata: Set up coding agent (Claude Code)** |

A metrics file written while a run is going is attached to that run and its numbers are read (JSON: every number; CSV: a header and one row; JSONL: the last line). A file identical to the committed version is ignored (it came from `git pull`, not from a run).

**What leaves your machine:** the run record only: command, folder, host name, commit hash, hashes of the settings files named on the command line, metric names and values, and the paths of the files written. Never file contents, data or weights. With uncommitted changes, the patch is saved in `.lemmata/patches/` on your machine and only its hash is sent. `.lemmata/` is git-ignored.

**Where records go:** to the hub project whose code repository is this folder. Until the hub can be reached they wait locally (`not sent yet`) and are retried every minute; **Send runs to the hub now** retries at once and says why records are waiting.

Settings: `lemmata.runs.capture` (off switch), `lemmata.runs.commandPattern`, `lemmata.runs.resultFolders`, `lemmata.runs.metricFiles`.

**Remote-SSH:** the extension runs on the machine that has the files (the GPU server), so that machine must be able to reach the hub. If it cannot, records wait on the server. Either join the server to your tailnet, or forward the hub through your SSH connection (`ssh -R 8765:100.111.135.94:8765 <server>`), set `lemmata.serverUrl` to `http://127.0.0.1:8765` in the *Remote* settings and run **Connect to Server** once in that window.

## Troubleshooting

- **A run did not appear**: was the command typed in VS Code's integrated terminal, in a folder inside the workspace, and does the terminal show the shell-integration marks in its left gutter? Inside tmux or over a nested `ssh`, VS Code cannot see commands; the results watcher still logs the run when it writes a metrics file.
- **A result file was not picked up**: its path must match `lemmata.runs.resultFolders` and its name `lemmata.runs.metricFiles`. Add your own patterns in settings.
- **"not sent yet" does not go away**: run **Lemmata: Send runs to the hub now**; the message names the reason (not connected, this folder is not a hub project's code repository, or the hub cannot be reached from this machine).

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
npx @vscode/vsce package    # -> lemmata-0.4.0.vsix
```
