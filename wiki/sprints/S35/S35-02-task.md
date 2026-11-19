---
type: task
owner_agent: lead
status: done
sources:
  - "../../decisions/ADR-011-vscode-is-the-experiment-bench.md (the decisions, accepted 2026-11-20 00:41 KST)"
  - "S35-01-cto-review-vscode-bench.md, section 6 (the first sprint and its 'done when' lines) and section 5 (what the draft missed)"
  - "founder message in chat, 2026-11-20 00:41 KST: 'Go with your recommendation. Dont mind when the next presentation is. we are focusing our best as of now.'"
last_reviewed: 2026-11-20
---
# S35-02 task card: VS Code becomes the experiment bench (phase 1, and the Experiments list from phase 2)

Owner: lead (in chat). Reviewer: QA, before any merge to main. Branch: `s30-baselines` (and `next`). Written with the
build on 2026-11-20, from the CTO's section 6; the acceptance lines below are the CTO's, made exact.

## Scope
Phase 1 of [S35-01](S35-01-cto-review-vscode-bench.md), plus three things pulled forward because the bench request gives
them at little cost or a decision asked for them: the Experiments list (the outline that stands in for the map), attaching a
run by hand (decision 3), and the extension's own update (decision 4).

Out of scope, for the next card: lines above result files and configs, comparing two runs in the diff editor,
experiment-only entries in the Problems panel, a walkthrough, a start signal for overnight jobs.

## Acceptance
| # | What | Done when |
|---|---|---|
| 1 | `GET /p/<pid>/api/bench` on the hub | Each recent run carries its experiment and the fields the result pattern read when a confirmed map pattern matches, and is absent when none does. No to-do item about the paper appears. A unit test on the fixture project shows both |
| 2 | Like with like | "was X" appears only against an earlier run of the same experiment, same fields, same measure; another dataset or seed gives no comparison; no verdict word or colour |
| 3 | Attach by hand | `POST /p/<pid>/api/bench {action: attach}` stores the choice; the run then counts for that experiment only, on the bench and on Setup; an empty experiment takes it back |
| 4 | Now | A run that is not sent stands under "Not sent to the hub"; once sent it stands under its group with its experiment's name; every run is in exactly one group |
| 5 | Experiments | Claim → experiment → setup, one line each; an experiment under two claims is drawn under both without an id clash |
| 6 | To run | A not-run or out-of-date experiment and a planned experiment appear; Copy gives the plan's own prompt; Snooze hides the item on the bench and on the hub's to-do list |
| 7 | Command diet | The palette shows at most 8 Lemmata commands; every other command is reached from a row, a list's title bar, a welcome link, the status bar or "Go to…"; nothing contributed is unregistered |
| 8 | One status-bar item | Running, not sent and to run in one item; when a run ends, its line for five minutes; no pop-up |
| 9 | The tab is bench-only | The embedded page shows Thesis and Setup in its band and only "Open on website" in its footer; any other page opens in the browser at `#go=<page>` |
| 10 | The map keeps its lines | At 600 px and 420 px the four columns stay side by side, the lines are drawn, the board scrolls inside its own frame and the page does not scroll sideways; at 1280 px it looks as before |
| 11 | The map alone | "Open the Map (large)" shows the board with no result sheets under it; "Open Setup" shows the whole page again |
| 12 | Update offer | The hub names a packaged extension only when a file for that exact version exists, and hands it to signed-in devices only; the extension offers a strictly newer version, once |
| 13 | Nothing else breaks | The Python suite, the extension's unit, integration and browser suites pass |
