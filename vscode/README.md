# Lemmata for VS Code: the experiment bench

The Lemmata website is where you read, decide and write: the thesis, baselines, LaTeX, review, the trail. VS Code is where experiments run, so this extension shows only what you need there:

1. Was my run captured, and is it on the hub?
2. What is running, and what just finished?
3. What is this experiment for, and what is its setup?
4. Is this result in line with the last comparable one?
5. What should I run next?

It answers them in VS Code's own lists and status bar, not in a web page squeezed into a column. Every other page opens on the website, one click away (**Lemmata: Go to…**).

It also **logs the experiments you run**, because most of them never reach GitHub: commands in the integrated terminal, result files written by detached jobs, and commands run by Claude Code. See "Runs" below and `docs/RUN-CAPTURE.md` for the step-by-step set-up.

The extension only talks to your own Lemmata hub (the Mac mini). No telemetry, no third-party servers.

## Install

The packaged file is `vscode/lemmata-0.8.0.vsix`.

- Command line: `code --install-extension vscode/lemmata-0.8.0.vsix`
- Or in VS Code: Extensions view -> `...` menu (top right) -> **Install from VSIX...** -> pick the file.
- From 0.8.0 on, the extension asks the hub whether it has a newer version and offers to install it (see "Updates" below). The first install of 0.8.0 is still by hand, on every machine you use (with Remote-SSH: on the server).

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

A hub path such as `code/configs/default.yaml` is mapped onto the folder that matched that repo, so **Open the File** on a row opens your own checkout. A file of a repo you have not opened cannot be opened here; the row says so. To force a project, set `lemmata.project` to its hub project id.

## What you will see

Three lists in the Lemmata side bar (the beaker in the activity bar):

| List | Shows | On a row |
|---|---|---|
| **Now** | The runs on this machine, each in one group: Running, Not sent to the hub, Failed today, Not attached to an experiment, Finished today, On other machines today, Earlier | Click: open the run record. Right-click: **Attach to an Experiment…** |
| **Experiments** | Each claim, the experiments that test it, and under an experiment its setup in one line each: what it tests, the measure and its direction, datasets, methods, runs per result, the result per dataset, what is out of date, its files, its last runs | **Copy** a prompt for Claude Code, **Open in Setup**, **Open on the Website**, **Open the File** |
| **To run** (collapsed) | Planned experiments, results older than their code, results with a single run, under their experiment. Only for experiments that test a claim | **Copy** the run prompt, **Snooze…** (it also leaves the website's to-do list) |

- **One status-bar item.** `2 running · 1 not sent · 3 to run`. When a run ends it shows that run for five minutes: `fp 30, was 31.2 (lower is better) · Main comparison`. "Was" appears only when there is an earlier run of the same experiment with the same dataset, method, seed and measure; otherwise only the new number is shown. Nothing is coloured better or worse.
- **Lemmata: Go to…** is one picker for everything else: the three lists, the map, Setup and Thesis (in a tab), every website page (opens your browser), and the actions (send runs now, sync the hub with GitHub, set up the coding agent, add this repository, connect).
- **Eight commands in the Command Palette**: Connect to Server, Go to…, Refresh, Send Runs to the Hub Now, Set Up Coding Agent (Claude Code), Add This Repository, Open the Map (large), Disconnect.
- The hub prepares every row (its words, its tooltip, what it can do), so a change of wording or rules reaches VS Code when the hub updates, without reinstalling the extension.
- Refresh runs every 30 s (`lemmata.refreshSeconds`) while the window is in front, when the window gets focus, and after a run is sent.

**Left VS Code in 0.8.0** (they are on the website): the "Alarms and findings" list, the warnings in the Problems panel, Mark Reviewed / Needs fixing / Ignore, Why?, Set checkpoint, and the Home, Review, Claims and Trail pages in the tab.

## The map and the tab

**Lemmata: Open the Map (large)** shows the map alone (thesis, claims, experiments and what they use, with the lines between them) in a full editor tab. **Go to… → Map in its own window** moves that tab into a window of its own, for a second screen. In a narrow tab the map keeps its four columns and its lines and scrolls sideways.

The tab shows two pages of the hub, **Setup** and **Thesis**. A link to any other page opens that page in your browser.

- **It works over Remote-SSH.** The page has no network access of its own. Every request it makes is passed to the extension, which calls the hub with your token. Only the extension needs to reach the hub.
- **The token never enters the page**, and the page can only reach its own project: requests for other projects, tokens, devices or users are refused by the extension.
- File pages have an **Open in editor** link that opens the file beside the tab when its repository is open in the window. `.md` downloads open as a document; pictures open in an editor tab, which has its own zoom; web links open in your browser.
- It needs a hub that has this change (the tab says so when the hub is older). After a hub update, close the tab and open it again to get the new pages.

## Updates

The hub's own update does not rebuild this extension, so the packaged file is kept next to its source (`vscode/lemmata-<version>.vsix`) and the hub hands it out to signed-in devices. A few times a day the extension asks the hub which version it has. When the hub's is newer, it asks once per version: **Install** downloads the file from your hub, installs it and offers to reload the window; **Not now** stays quiet until the next version. **Go to… → Check the hub for a newer extension** asks at once.

## Runs

Every experiment logged in this repository is in the **Now** list: the command, the commit (`+changes` when the tree had uncommitted edits), the numbers it wrote, the experiment it belongs to, and whether the record has been sent to the hub. Click a run to open its record.

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
- **"Your hub is older than this extension"** in the Experiments list: update the hub (on the Mac mini: `lemmata hub update`, or let its auto-update run), then Refresh.
- **A run sits under "Not attached to an experiment"**: it wrote files or numbers that match no experiment's result files. Right-click it and choose **Attach to an Experiment…**; your choice counts at once and can be taken back the same way.
- **The map has no lines**: the hub is older than S35. Update the hub and reopen the tab.
- **Paper errors after Sync now**: the hub could not read the paper repo or folder (renamed, or you lost access). Reconnect it from the project page in Lemmata.
- Log: View -> Output -> "Lemmata". It never contains the token.

## Develop

```
cd vscode && npm install
npm run compile
npm test                    # unit tests (node's test runner)
npm run test:integration    # real hub + fake GitHub, needs python3 and git
npm run test:host           # optional: extension-host smoke test (downloads VS Code)
npx @vscode/vsce package    # -> lemmata-0.8.0.vsix
```
