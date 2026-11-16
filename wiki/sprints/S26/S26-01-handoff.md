---
type: handoff
owner_agent: lead
status: needs-qa
sources: ["founder chat 2026-11-16 13:5x KST (request with a screenshot of the 13 Nov day panel: 'How are these information even helpful? ... where, how, what, who, when is answered through clicking this. This should be applied to setup as well.')", "founder chat 2026-11-16 14:10 KST (answers: rules plus agent-drafted summaries; one-hour gap; inspection hidden by default; Setup header yes)", "wiki/decisions/ADR-007 (Lemmata drafts, I confirm)", "wiki/decisions/ADR-008-top-down-evidence-spine.md section 5.2"]
last_reviewed: 2026-11-16
---
# S26-01: a day as work sessions, and the six questions on Setup

## Why
The day panel listed every logged command as one line (`app/src/lemmata/engine/trail.py`, runs entries titled with
the first 120 characters of the command). A day with an agent at work was dozens of lines of shell text, and nothing
said what the work was for. Source: founder chat and screenshot, 2026-11-16.

## Built
- **Work sessions** (`app/src/lemmata/engine/sessions.py`, new). Records of one day (logged runs, commits, claim
  stage changes, feedback, decisions) are grouped into sessions: the same place, no gap longer than 60 minutes
  (`GAP`, founder's answer 2). A session never crosses midnight. Each session states:
  - **When**: start, end, minutes.
  - **Who**: you (terminal), the coding agent (run source `agent`, or a command run from the agent's scratch
    folder such as `/tmp/claude-*`), the file watcher; for commits the author and any `Co-Authored-By`
    (`engine/history.py` now reads the author name).
  - **Where**: host, folder relative to the repository, the commit the run was on and whether there were
    uncommitted changes. A folder named after the repository (`mcd_extension_rq2` next to `mcd_extension`)
    counts as a second copy of the same project.
  - **What**: each command is read by rules into one of: experiment run, script, analysis (inline Python),
    inspection, set-up, git, paper build, other. The card lists runs per script with failures, files written,
    commits and other records. Inspection commands are counted and hidden (answer 3).
  - **Why**: the experiments the session belongs to and the claims they test. A run belongs to an experiment
    when it wrote a file that matches the experiment's result pattern in the confirmed map (certain), or its
    command names the experiment's result folder (likely). Without either the card says "Lemmata cannot tell".
  - **How**: scripts, settings files, environment settings and arguments (dataset, method, seed first), parsed
    from the command text. No shell is run.
  - **Result**: results a commit moved (before → after, better or worse, ahead of the best other), numbers a
    run reported, files written, failures, uncommitted-changes warning, claim stage changes.
- **Summaries** (answer 1). The title is made by rules. A coding agent may draft one sentence through the MCP
  server (`sessions` to read, `session_summary` to propose; `app/src/lemmata/mcp.py`). It runs on the author's
  own Claude plan. A draft is shown as "draft by your agent" with Confirm / Edit / Discard; only the researcher
  confirms, and a confirmed summary is never replaced by a draft. The researcher can also write one. Stored in
  the hub file `sessions.json`. Route: `POST /api/session {id, text | action: confirm | remove}`.
- **Day panel, Trail list, Home** (`app/src/lemmata/web/research.js`, `app.css`). The day panel shows session
  cards with the raw records behind "Show the records". The Trail list shows one line per session; a click
  opens the card. "Last 7 days" on Home lists session titles and opens the day.
- **Setup** (answer 4). Each experiment sheet starts with a six-cell strip: Why (claim), What (the comparison),
  Where (server, result folder, file count), How (script, settings, last command), When (first and last result,
  how often it changed), Who (logged runs by you / agent / watcher). The trace of a number now has five
  labelled steps: what the paper says → where it comes from → how → who ran it → when. Data: `context` on each
  experiment from `Engine._setup_context` (`engine/api.py`).
- **VS Code**: nothing to install. The tab shows the hub's pages, so it changes when the hub updates. The
  end-to-end test now checks the session card in the tab.

## Checked
- `app`: 181 tests pass (new: `tests/test_map.py::test_sessions_and_summaries`).
- `vscode`: unit tests and 10 end-to-end tests pass.
- Browser check at 1440 px and 420 px on the fixture with six logged runs: no console errors, no sideways scroll.
  Screenshots in [screenshots/](screenshots/).

## Not checked, and limits
- Not seen on the real `mcd_extension` data: the browser pane is not signed in to the hub. The 13 Nov day was
  rebuilt only as a fixture.
- The why of a session depends on the confirmed project map. Runs that write files no mapped experiment claims
  (figures, scratch output) get "Lemmata cannot tell" until an agent or the researcher writes the summary.
- Runs carry no branch name, so Where shows the commit, not the branch.
- A summary is tied to the session's first record. If an earlier record of the same session is logged later,
  the session gets a new id and the summary no longer shows.
- Draft summaries are not yet a To-do item.
- QA has not verified S18 to S26.

## Needs Juhyeong
- Look at a real day on the hub after it updates, and say whether the rule-made titles are good enough to
  read without summaries.
