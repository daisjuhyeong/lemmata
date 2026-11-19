---
type: review
owner_agent: cto
status: proposed
sources:
  - "founder message in chat, 2026-11-20 00:32 KST (no file in raw/ yet): 'I was thinking how the website and the VS code extension should have difference purposes, just like how Claude code and Claude website is separate. Brainstorm into how VS code setup can be different so that it can used for assisting experiment focused materials. It would not need latex code or others, but it will need the focus of the setup and the experiment related features of Lemmata. The reason for this is to optimize the layout for VS code. There are too many features in the VS code, which hinders and rather confused the user of what they originally wanted to do. Also, for a map or a figure, since the vs code tab is smaller, it is not visible. Send this to CTO agent and brainstorm into improving the features for VS code, along with the UI and UX.'"
  - "lead's draft A to K, handed to the CTO in the same session, 2026-11-20"
  - "code on branch s30-baselines: vscode/package.json, vscode/src/extension.ts, vscode/src/runs.ts, vscode/src/tab.ts, vscode/src/core/{embed,client,load,model,runs}.ts, vscode/media/{embed.js,vscode.css}, vscode/README.md"
  - "code on branch s30-baselines: app/src/lemmata/server.py (route table), app/src/lemmata/engine/api.py (experiments, setup, _setup_context, _board, _exp_patterns, todo, runs), engine/runs.py, engine/setup.py, engine/todo.py, engine/sessions.py, engine/plans.py, engine/numbers.py (docstring), app/src/lemmata/mcp.py (tool list), app/src/lemmata/web/app.js (renderStatus, fitTabs), web/research.js (bdBoard, bdWire)"
  - "docs/AUTO-UPDATE.md line 39: 'The desktop app and the VS Code extension are not rebuilt by this.'"
  - "../S30/S30-brief.md ; ../../decisions/ADR-010-lemmata-watches-writing-agents.md ; ADR-006, ADR-007"
last_reviewed: 2026-11-20
---
# S35-01: CTO review of "VS Code as the experiment bench"

This is a review and a plan, not a task card. Building starts only from a task card with acceptance criteria
(section 6 gives draft "done when" lines for one). Nothing here is decided until Juhyeong approves the questions in section 7.

## 1. Verdict in one paragraph
I agree with the split. The website is where you read, decide and write. VS Code is the bench where runs happen. I
agree that the bench should use VS Code's own views (trees, status bar, CodeLens, diff editor) and not a web page.
I disagree on three points. (a) Do not keep two modes (`lemmata.focus: experiments | all`): make VS Code bench-only and
link out. (b) A native UI ships in the `.vsix`, which the hub's auto-update does not rebuild. So the hub must shape the
rows and the extension should only draw them; otherwise every wording change needs a reinstall on every GPU server.
(c) About a third of the draft is over-built for a first pass: gutter marks, number hovers, the Jobs view, and a line
written into the terminal, which VS Code may not allow. The map problem is mostly a hub-side layout bug (the board drops
its lines when its columns stack), so fix that once and it improves both the website and VS Code.

## 2. Facts from the code that change the picture
| # | Fact | Where | Consequence |
|---|---|---|---|
| 1 | The extension runs on the GPU server (`extensionKind: ["workspace"]`). Git, the results watcher, `.lemmata/runs/` and `.lemmata/patches/` are all local to it. | package.json; runs.ts `gitState`, `save` | Compare and diffs can read local git and patches directly. No hub call is needed for a run made on this machine. |
| 2 | Native trees, CodeLens and the status bar call the hub through `HubClient.req` in the extension host. They do not need the webview bridge (`allowedRequest` in core/embed.ts, media/embed.js). | core/client.ts | Native views are simpler and safer than the tab: the token never comes near a page, and nothing needs a path allow-list. |
| 3 | The tab does not ship its own UI. It downloads the hub's `app.js` and `research.js` (`LemmataTab.load`, `ASSETS`). The footer that lists every page is drawn by the hub (`renderStatus` in web/app.js, the `more` list). | tab.ts; app.js | Any "show fewer pages in VS Code" change is a **hub** change in app.js. It reaches VS Code via auto-update, with no reinstall. |
| 4 | The hub's auto-update does not rebuild the extension. | docs/AUTO-UPDATE.md:39 | Every native-UI change needs a new `.vsix` installed by hand on each Remote-SSH host. Today that is a real cost: it is the only part of Lemmata that does not update itself. |
| 5 | Runs are linked to experiments only inside `Engine._setup_context` (api.py), using `sessions.experiments_of` against the confirmed map's file patterns (`_exp_patterns`). `/api/runs` (runs.py `view`) does not say which experiment a run belongs to. With no confirmed map, no run is linked to anything. | api.py 1008-1053; runs.py `view` | The "Now" tree cannot group runs by experiment without calling the full `/setup` (heavy: it reads result tables). It needs a small new endpoint. |
| 6 | There is no write that attaches a run to an experiment. | server.py POST routes | "Attach to…" needs a new hub record. Per ADR-007, the researcher's attach is a confirmation and counts at once. |
| 7 | `/setup` already computes the checks the draft wants: a measure read in two directions, a method missing on some datasets, one run per cell (`setup.py` `checks` with `k` = direction, missing, seeds, coverage). `/todo` turns them into items (`setup_<k>`), plus `not_run`, `stale` ("Rerun X: code or settings changed after this result"), `seeds`, `plan`, and can snooze them (`POST /todo` `snooze_todo`). | setup.py 357-413; todo.py 62-121 | "To run" and the Problems entries need **no new rules**. Filter `/todo` by kind. |
| 8 | Planned experiments already exist: `experiment_brief`, `propose_experiments` (MCP), `/plans` GET and POST (keep, edit, drop), each with a run prompt. | plans.py; mcp.py 1402-1414 | Item H is mostly wiring. |
| 9 | A result's history is already on the experiment (`spark`, `history_n`, `last`, `stale` in `/experiments`; used in `_setup_context` "when"). | api.py 1042-1048 | "Is this in line with the last one" for committed results exists. For a fresh local run it does not: see 4.3. |
| 10 | The board (map) is four HTML columns with SVG wires. When the columns stack, `bdWire` draws no lines at all (`cols[1].left - cols[0].left < 40` returns early). | research.js 1594-1609 | In a narrow tab the map loses exactly what makes it a map: the connections. A bigger tab helps only until the columns stack again. |
| 11 | The embedded page polls `/api/project` every 5 s through the bridge, and the panel is created with `retainContextWhenHidden: true`, so it keeps polling while hidden. The extension also refreshes alarms, findings, graph and triage every 30 s (`loadModel`). | app.js `boot`; tab.ts `open`; core/load.ts | Adding `/setup` to the 30 s loop would be costly. One small `bench` call should replace it. |
| 12 | Today's Problems entries come from alarms (code lines) and findings (paper consistency) (`toDiagnostics`, model.ts). On a GPU server the paper repo is usually not open, so findings mostly do not show; alarms do. | model.ts 109-133 | Problems is already mostly experiment-shaped. Item B's "Problems only for experiment issues" is a filter, not a new feature. |

## 3. Item by item
"Hub" = what the hub must add. "Ext" = extension work. Verdict: keep, merge, move (to a later phase), or cut.

| Item | Uses today | Hub must add | Architecture notes | Verdict |
|---|---|---|---|---|
| A. Three trees: Now, Experiments, To run | Now: local `RunCapture.entries` (runs.ts). Experiments: `/experiments` sections, `/setup` protocol and context. To run: `/todo` + `/plans`. | `GET /p/<pid>/api/bench` (one call, see 5.1) that returns each recent run with its experiment(s) and fields (dataset, method, seed), and each experiment's setup rows. | Now has to merge local entries (not yet sent) with the hub's view, keyed by `run_id`. Trees cannot wrap text: one line per row, with full text in the tooltip. | **Keep**, but Now and To run first. Experiments tree in the same sprint only if `bench` lands. |
| B1. CodeLens at the top of a result file | `/experiments` result `path`; `mapPath` (core/mapping.ts) to turn a hub path into a local one. | Nothing beyond `bench`. | The hub knows the committed file; on the server the file is often newer and uncommitted. The lens must say which: "on GitHub: 2 days ago at a1b2c3 · here: changed since". CodeLens on CSV or JSON works with a file-pattern selector (to verify against the VS Code docs). | **Keep**, P2. |
| B2. CodeLens on a config or script | todo kind `stale`; ledger rows' `code` and `settings` in `_setup_context`. | Those are node **names** today (`c["name"]`), not paths. The hub must return paths. | Cheap once paths are there. | **Keep**, P2. |
| B3. Hover on a number | `/numbers` (key numbers have a file and a read rule). | A reverse index: file + cell -> key number, LaTeX snippet. | Locating a cell from a hover position in a CSV is fiddly and error-prone. | **Move** to later. |
| B4. Gutter marks on changed cells | Nothing: there is no "confirmed run" record. | A new concept. | Needs a cell-level diff of local vs committed, per file type. | **Cut.** The built-in git gutter already marks changed lines. |
| B5. Problems only for experiment issues | `toDiagnostics` (model.ts), `/todo` kinds. | Nothing. | Filter: drop findings whose location is in the paper repo; add `setup_direction`, `setup_missing`, `seeds` from `/todo` as Information entries on the result file. | **Keep**, P1 (small). |
| C. One line in the terminal when a run ends | `onDidEndTerminalShellExecution` (runs.ts `onEnd`). | Nothing. | I do not know of an API that writes output into a user's terminal: `Terminal.sendText` types input into the shell, which would be wrong; a terminal link provider can only make existing text clickable (to verify against the VS Code docs). | **Change**: show the line in the status bar for a few minutes ("fp 30.0, was 31.2 · Main comparison"), click opens Compare; a badge on the Lemmata icon (`TreeView.badge`, to verify). No pop-ups. |
| D. Compare two runs | Manifests (metrics, `git_sha`, `configs` with hashes, `diff_hash`); local `.lemmata/patches/<hash>.patch`. | Nothing for local runs. | Diff editor needs two URIs: add a content provider for `git show <sha>:<path>` (same pattern as the existing `lemmata-why` scheme in extension.ts) and call the built-in `vscode.diff` command. A run from another host has no patch here: say so. When a config was dirty, only the hash is known: show the two patches instead. | **Keep**, P2. The metrics table should be a virtual Markdown document, not a webview. |
| E. Setup card, six rows, 300 px | `_setup_context` already returns where, how, when, who and runs per experiment; protocol has metric, `lower`, datasets, methods, seeds. | Pre-formatted one-line rows (in `bench`). | As tree children of an experiment, not a separate panel. "Electricity: ours 30.0 · best other 38.0 (DDM)" is exactly the per-dataset `use()` data in setup.py. | **Merge into A** (children of the experiment row). |
| F. Big things: outline tree, "Open large", "Open on website" | `/setup` board (`_board`, board.py); thumbnails `/thumb`, images `/raw`; tab.ts `onOpen` already writes images to a temp file and opens them in VS Code's image viewer. | Fix `bdWire` and the board layout so that it scrolls sideways or scales instead of stacking (hub, web/research.js). | Figures written by a run are already in the workspace: open the local file, no hub call. Images in a hover (`MarkdownString`): whether file or `data:` URIs render there, and over Remote-SSH, is to verify against the VS Code docs. Moving a tab to its own window is a workbench command in recent VS Code (to verify the command id for 1.93). | **Keep**, but the outline tree **is** the Experiments tree (A); "Open large" = the existing tab locked to the board. Hover previews: later. |
| G. Command diet, 25 to about 8 | package.json has 25 commands; 7 are already hidden from the palette, so the palette shows 18. | Nothing. | Keep internal commands registered and hidden (`commandPalette` `when: false`), so tree actions still work. | **Keep**, P1. |
| H. Claude Code hand-offs | MCP `experiments`, `experiment_brief`, `propose_experiments`; `/plans` with run prompts. | Nothing. | The prompt is copied to the clipboard; the extension does not start Claude Code (to verify whether the Claude Code extension exposes a command that takes a prompt; do not depend on it). Runs by the agent already arrive as `source: agent`. | **Keep**, P2: it is cheap. |
| I. `lemmata.focus` setting | `LEMMATA_EMBED` in app.js. | app.js: a bench-only footer when embedded. | Two modes double the test matrix and keep the confusion one setting away. | **Change**: no setting. The tab shows only the board and Setup; every other page is "Open on website". |
| J. Walkthrough | `contributes.walkthroughs` (to verify the schema for 1.93). | Nothing. | The views' welcome text (`viewsWelcome`) already does part of this. | **Keep**, P3. |
| K. Jobs view (tmux, sbatch) | The results watcher sees a job only when it writes a metrics file. | Nothing. | Polling `squeue` or tmux sessions is per-cluster and brittle. | **Cut** in this form. See 5.4 for a smaller alternative. |

## 4. Where I disagree
1. **Two modes.** `lemmata.focus: experiments | all` keeps the problem one click away and doubles what QA must test.
   VS Code should be the bench only. Each tree row has "Open on website" for the rest. Cut the full-site tab.
2. **Native UI has a deploy cost the draft does not price.** Fact 4: the `.vsix` does not auto-update. If labels,
   rules and wording live in TypeScript, every change needs a manual install on each lab server. Rule I propose: the hub
   returns rows ready to show (label, description, tooltip, icon name, actions); the extension only draws them. This is
   also what lets the extension stay small.
3. **"Was 31.2" must compare like with like.** A run's numbers are flat keys from a metrics file (`parseMetrics`,
   core/runs.ts); an experiment's numbers come from committed result tables. Matching "fp" in a run to the "fp" column of
   Table 2 is a guess. Compare a run with the previous run of the **same experiment and same fields** (dataset, method,
   seed, from the map pattern) and the **same metric key**. When there is none, say nothing. Lemmata gives evidence, not
   verdicts, so no "better" or "worse" colour: show the direction ("lower is better") and the two numbers.
4. **Coverage gaps as "To run" will flood the list.** A missing dataset × method cell is often deliberate (a baseline
   that cannot run on a dataset). Turning every gap into a to-do recreates the "too many things" problem. Show gaps only
   for experiments linked to a claim, group them under their experiment, and let the researcher snooze (already on the
   hub: `POST /todo`).
5. **Over-built for now:** gutter marks (B4), number hovers (B3), the Jobs view (K), hover image previews. None of
   these answers one of the four questions better than a tree row and a click.
6. **The principle itself.** The four questions are right. I would add a fifth one in front of them, because it is
   where trust breaks first: "was my run captured, and is it on the hub?". Today that is a status bar beaker and a
   "not sent yet" word in the description. Now should make it the first thing you see.

## 5. What the draft missed
### 5.1 One bench endpoint, shaped for 300 px
`GET /p/<pid>/api/bench`: recent runs with their experiment, fields and "previous comparable run"; experiments with their
claim, one-line setup rows and latest result line; to-run items (todo kinds `not_run`, `stale`, `seeds`,
`setup_missing`, `setup_seeds`, `setup_direction`, `plan`, `contradicts`; paper kinds excluded); and a version number
so an older extension can say "update me". It replaces `/setup` in the 30 s loop. It runs no model (ADR-006).

### 5.2 Alarms become part of Experiments, not a tree of their own
The "Alarms and findings" tree is the website's Review in miniature. On the bench, an alarm matters as "this result is
older than the code it depends on". Show it as a marker on the experiment row ("stale: configs/default.yaml changed in
9f1c2e7") with Why? and triage in its context menu. Findings about the paper leave VS Code. Two trees remain visible by
default (Now, Experiments); To run is a third, collapsed.

### 5.3 Fix the map once, on the hub
The map is not invisible because the tab is small. It is invisible because `bdWire` stops drawing lines when the
columns stack (fact 10). Change the board to keep four columns and scroll sideways (or scale) below a width, and keep
the lines. This helps the website on a laptop too. Then "Open large" is just the tab showing the board.

### 5.4 A start signal for detached jobs, without a Jobs view
Instead of reading tmux or Slurm: a small `lemmata-run -- <command>` wrapper (or a line in the agent rules) that writes
the manifest at start and end, in the format runs.ts already reads. Overnight jobs then show under Now as "running"
before they write a file. Later, and only if the founder wants it.

### 5.5 Extension updates
Either the hub serves the current `.vsix` and the extension offers "A newer Lemmata extension is on your hub: install"
(one click, through VS Code's own install command, to verify), or we accept manual installs. Founder decision (7.4).

### 5.6 Housekeeping found while reading
- README.md says "The tab is at least 1024 px wide inside", but core/embed.ts says there is no minimum width since S18. Stale.
- package.json `description` still advertises the Review and Claims pages.
- S30-brief says "the VS Code extension has no command for the page or the install yet". Under this plan it should not
  get one: Baselines is a website page. Close that open item instead of building it.

## 6. Order and first sprint
Cut line: the 2nd presentation (MVP demo). Its date is not in the wiki (wiki/presentations/README.md has none), so
the cut is by phase: P1 alone is a usable, demo-able bench. If time is short, ship P1 and stop.

| Phase | What | Done when (testable) |
|---|---|---|
| **P1 (S35)** | 1. `GET /api/bench` on the hub with a unit test on the fixture project. | A test shows each recent run with its experiment id and fields when a confirmed map pattern matches, and `experiment: null` when none does; no paper-kind to-do items appear. |
| | 2. Now tree: today's runs from local entries merged with `bench`, grouped running / finished / failed / not attached / not sent. | In the host test, a planted manifest that is not yet sent shows under "not sent"; after sync, it moves under its experiment's name. |
| | 3. To run tree from `bench`, with "Copy prompt" (plans) and "Snooze" (`POST /todo`). | A `not_run` item and a draft plan appear; Snooze hides the item after a refresh and the hub's `/todo` no longer lists it. |
| | 4. Command diet: palette shows at most 8 Lemmata commands; one "Lemmata: Go to…" quick pick. | `package.json` test counts the commands visible in the palette (≤ 8); every removed command is still reachable from a tree or the quick pick, or is on the website. |
| | 5. Status bar: one item, "2 running · 1 new result", and the run-ended line for a few minutes. Remove the second item. | Ending a captured run in the host test changes the item text to the run's first metric and experiment; no notification is shown. |
| | 6. Hub, app.js: when embedded, the footer lists only Setup and "Open on website". | e2e tab test: the embedded page has no Baselines, LaTeX, Trail or Settings links. |
| | 7. Hub, research.js: the board keeps its lines below 700 px (scroll sideways). | A screenshot test at 600 px shows the wires drawn; the website at 1280 px looks as before. |
| **P2** | Experiments tree with setup rows (E merged in); stale markers from alarms (5.2); CodeLens on result files and configs; Compare with the diff editor; Claude Code hand-offs. | Opening a result file shows the lens with both the GitHub and the local state; Compare on two local runs opens the config diff in VS Code's diff editor; a run on another host says "patch not on this machine". |
| **P3** | "Open large" for the board; walkthrough; extension update offer (if 7.4 says yes). | A new user on a clean VS Code reaches "my run is attached" by following the walkthrough alone. |
| **Later** | Number hovers, hover figure previews, the run wrapper (5.4). | Each needs its own card. |

The first sprint needs a task card in `wiki/sprints/S35/` with these acceptance criteria and a QA reviewer before any
code is written. The lead or the PM writes it; I review it.

## 7. Decisions for Juhyeong (ADR-level)
1. **Is VS Code bench-only?** Everything outside runs, experiments, setup and what-to-run moves to the website, with
   no "show everything" setting. (Recommended: yes.)
2. **Do the paper findings leave VS Code entirely**, including the Problems panel, or stay when the paper folder is
   open? (Recommended: leave.)
3. **May a researcher attach a run to an experiment by hand**, stored on the hub and counting at once (ADR-007)? This
   adds a record to the data model.
4. **Should the extension offer its own updates from the hub**, since the hub's auto-update does not rebuild it? If no,
   each release is a manual `.vsix` install on every server.
5. **Board layout on the website:** may the board scroll sideways instead of stacking, on the website as well as in VS
   Code?
6. **The date of the 2nd presentation**, to set the cut line (P1 only, or P1 and P2).
