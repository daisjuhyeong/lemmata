# Lemmata in VS Code: logging the runs that never reach GitHub

Most experiments are never committed. They run in a terminal, on a GPU server, or through a coding agent, and the numbers end up in a results folder. This guide sets up Lemmata so those runs are logged where they happen and show up in the hub, for you and for Claude Code.

What you end up with:

- every `python train.py` you type in VS Code's terminal is logged with its commit, settings and numbers;
- jobs that finish elsewhere (tmux, sbatch) are logged when they write a metrics file;
- experiments Claude Code runs are logged by a hook;
- Claude Code can answer "which run produced this number?" from the log, through the hub's `runs` tool;
- the weekly digest says how many runs were logged and how many were on code that is not in GitHub.

Only the run record leaves your machine: command, commit hash, hashes of settings files, metric values, file paths. Never code, data or weights.

## Step 1. Update the hub (Mac mini)

The hub needs the new `/api/runs` route and the `runs` / `log_run` MCP tools.

1. Get this change onto the branch the hub follows (`s07-public-site` today), then push.
2. Wait about 5 minutes for the auto-update, or run it now: `cd ~/work/lemmata/app && uv run lemmata hub update`.
3. Check: `curl -H "Authorization: Bearer <token>" http://100.111.135.94:8765/p/<project id>/api/runs` returns `{"schema": "lemmata.runs/1", "runs": [], ...}`. A `404 unknown route` means the hub is still on the old code.

## Step 2. Install the extension (the machine where you run experiments)

1. `code --install-extension vscode/lemmata-0.4.0.vsix` (or Extensions → `...` → **Install from VSIX...**). With Remote-SSH, install it in the remote window: it must run where the files are.
2. If you have not connected before: Command Palette → **Lemmata: Connect to Server**, paste a token (`uv run lemmata hub token --device "VS Code"` on the Mac mini).
3. Open your code repository as the workspace folder. The status bar should read `Lemmata: N to recheck`, not `no project`.

## Step 3. Check that terminal capture works

1. Open the integrated terminal (`` Ctrl+` ``) in the repository.
2. Run any experiment command, for example `python train.py --config configs/default.yaml`.
3. Open the Lemmata panel in the activity bar. Under **Runs** the command appears with the time and the commit; while it runs it says `running`.
4. When it ends, the row shows the exit state. If the run wrote a metrics file into a results folder, its numbers are on the row (`f1=0.851 ...`).
5. After a few seconds `not sent yet` disappears: the record is on the hub.

If nothing appears, see Troubleshooting in `vscode/README.md` (most often: the command ran inside tmux, or shell integration is off).

## Step 4. Tell Lemmata where your results are (only if needed)

Out of the box it watches `results/`, `outputs/`, `output/`, `runs/`, `logs/`, `experiments/`, `exp/`, `checkpoints/` for files named like `*metric*.json`, `*result*.json`, `*eval*.csv`, `summary.json`. If your project writes elsewhere, add it in Settings (workspace):

```json
{
  "lemmata.runs.resultFolders": ["results/**", "save/**"],
  "lemmata.runs.metricFiles": ["*metric*.json", "final.json", "scores_*.csv"]
}
```

For a job you start in tmux or with sbatch, nothing more is needed: when it writes a metrics file, a row "Results watcher: <file>" appears with the commit the repository was on.

## Step 5. Set up the coding agent (Claude Code)

1. Command Palette → **Lemmata: Set up coding agent (Claude Code)**. It asks before writing, then:
   - copies the hook to `.lemmata/hooks/log_run.py` (git-ignored);
   - registers it in `.claude/settings.local.json` (your personal, uncommitted Claude Code settings; existing entries are kept);
   - offers to add a short "## Lemmata" section to `CLAUDE.md` (rules for the agent: use the log, do not guess; say what depends on code before editing it).
2. Connect Claude Code to the hub, once per machine. The command is copied for you; put a real token in place of `<token>`:
   ```
   claude mcp add --scope user --transport http lemmata http://100.111.135.94:8765/mcp --header "Authorization: Bearer <token>"
   ```
   Keep `--scope user`, so the token never lands in the repository.
3. Restart Claude Code in that repository (hooks are read at start). `/hooks` should list the Lemmata hook for Bash; `/mcp` should list `lemmata`.

## Step 6. Check the agent

1. Ask Claude Code to run an experiment ("run eval.py on the test split").
2. The run appears under **Runs** with the robot icon, and is sent to the hub.
3. Ask: "Using Lemmata, which run produced f1 = 0.851?" The agent should call the `runs` tool and answer with a run id, commit and command.

## Step 7. Daily use

- Work as usual. Look at **Runs** when you need to know what you ran, on which commit, with which settings.
- `+changes` on a row means the run used uncommitted code. The exact patch is in `.lemmata/patches/` on that machine.
- The weekly digest on the hub now includes a line such as "12 runs logged from the editor or the coding agent, 7 on code that is not in GitHub".
- To stop logging in one workspace: set `lemmata.runs.capture` to `false`.

## What this does not do yet

- The hub's web pages do not show the runs yet (API, MCP tool and digest only). The Experiments page still reads result files from GitHub.
- Notebooks, Weights & Biases and MLflow are not read.
- Runs are not linked to a table cell in the paper. A run that wrote a result file the hub tracks is tied to that file (`tracked`), which is the starting point for that link.
