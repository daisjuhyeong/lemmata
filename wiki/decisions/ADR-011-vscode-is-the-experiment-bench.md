---
type: adr
owner_agent: lead
status: accepted
sources:
  - "founder message in chat, 2026-11-20 00:32 KST: 'I was thinking how the website and the VS code extension should have difference purposes, just like how Claude code and Claude website is separate. ... It would not need latex code or others, but it will need the focus of the setup and the experiment related features of Lemmata. ... There are too many features in the VS code, which hinders and rather confused the user of what they originally wanted to do. Also, for a map or a figure, since the vs code tab is smaller, it is not visible.'"
  - "founder message in chat, 2026-11-20 00:41 KST, answering the six decisions of S35-01 section 7: 'Go with your recommendation. Dont mind when the next presentation is. we are focusing our best as of now.'"
  - "../sprints/S35/S35-01-cto-review-vscode-bench.md (the CTO's review of the lead's draft, with the facts from the code)"
  - "../../docs/AUTO-UPDATE.md, section Limits: the hub's update does not rebuild the VS Code extension"
  - "https://code.visualstudio.com/api/references/commands (read 2026-11-20): workbench.extensions.installExtension takes an extension id or a VSIX resource uri"
  - "ADR-006-public-multi-user-site.md (no language model on the hub) ; ADR-007-project-map-two-phases.md (the researcher's own confirmation counts at once)"
last_reviewed: 2026-11-20
---
# ADR-011: VS Code is the experiment bench; the website is where you read, decide and write

Status: **accepted** on 2026-11-20 00:41 KST. Juhyeong was asked the six questions of
[S35-01 section 7](../sprints/S35/S35-01-cto-review-vscode-bench.md) with a recommended answer for five of them and
answered "Go with your recommendation". The sixth (the date of the 2nd presentation) he set aside: "Dont mind when the
next presentation is." Items 6 and 7 below were not among the numbered questions: they were in the plan he read before
answering (the CTO's changes to the draft), and are recorded here so the build has one place to point to. First build: [S35-02](../sprints/S35/S35-02-handoff.md).

## Context
- The extension (0.7.0) had 25 commands, two lists ("Alarms and findings", "Runs") and a tab that showed the whole
  website in an editor column. Juhyeong found that this hides what he came to VS Code to do, and that a map or a
  figure cannot be read in so small a tab.
- VS Code is open on the machine where experiments run (with Remote-SSH: the GPU server). The paper is usually not open there.
- The extension is the one part of Lemmata that the hub's update does not rebuild.

## Decision
1. **VS Code is the bench only.** It shows runs, experiments, their setup and what to run next, and answers five
   questions: was my run captured and sent; what is running or just finished; what is this experiment for and what is
   its setup; is this result in line with the last comparable one; what should I run next. There is no "show
   everything" setting. Every other page is on the website, one click away.
2. **Findings about the paper leave VS Code entirely**, the Problems panel included. So do triage (Reviewed, Needs
   fixing, Ignore), "Why?" and Set checkpoint. A result that is older than its code is shown on its experiment.
3. **A researcher may attach a run to an experiment by hand.** The choice is stored on the hub, counts at once
   (ADR-007), counts for that experiment only, and can be taken back.
4. **The extension offers its own update from the hub.** The packaged file is committed next to its source; the hub
   hands it to signed-in devices; the extension asks once per version and installs only when the researcher says so.
5. **The map scrolls sideways instead of stacking**, on the website as well as in VS Code, so it keeps its lines at
   any width.
6. **The hub prepares the rows; the extension only draws them** (the CTO's rule). Labels, descriptions, tooltips,
   icon names and what a row can do come from `GET /p/<pid>/api/bench`. A change of wording or rules then reaches VS
   Code with the hub's own update.
7. **A result is compared like with like, and never judged.** "Was 31.2" is shown only against an earlier run of the
   same experiment with the same fields (dataset, method, seed, as the result pattern reads them) and the same
   measure. The direction is named ("lower is better"); nothing is coloured better or worse.

## Consequences
- The embedded tab shows two pages, Setup and Thesis. This is decided in the hub's `app.js`, so an extension that is
  still 0.7.0 also loses the other pages in its tab as soon as the hub updates; its two lists keep working.
- An extension that is 0.8.0 on a hub older than S35 shows its runs, and one line in Experiments saying the hub is older.
- Home, Review and the Trail are no longer exercised by the extension's browser test (they were tested through the
  tab). They need a browser test of their own on the website.
- `vscode/src/core/{model,load,why}.ts` are no longer used by the extension. They are kept, with their tests, for one
  sprint in case a "Why?" on an out-of-date experiment is built; otherwise they are to be deleted.
- Whoever changes `vscode/` bumps the version and commits the newly packaged file, or no update is offered.

## Not decided here
In-editor lines above result files and configs, comparing two runs in the diff editor, experiment-only entries in the
Problems panel, a first-use walkthrough, and a start signal for overnight jobs (S35-01 phases 2 and 3).
