---
type: handoff
owner_agent: lead
status: needs-qa
sources: ["founder chat 2026-11-12 21:40 KST"]
last_reviewed: 2026-11-12
---
# S19-01: open experiments in VS Code; baselines side by side

Asked by Juhyeong (chat, 2026-11-12 21:40 KST): open a claim's experiments in VS Code from the Review, and make the
baseline comparison easier to check against the main method. He chose "both" ways of opening and "side-by-side numbers".

## What changed
- **Review, baselines.** An opened baseline is a table: experiment, metric (with ↑/↓), ours, the baseline, gap.
  The hub adds `ours`, `ours_label`, `value`, `label`, `col`, `lower`, `target` to each experiment of
  `review.baselines[].experiments[]` (`engine/review.py`). The table scrolls sideways inside its box when narrow.
- **VS Code tab, experiment details.** "Open in editor" buttons for the experiment's scripts (up to 4), settings files
  (up to 3) and result file, through the existing `openFile` bridge (`rxEditorRow`, research.js).
- **Website → VS Code.** "Open in VS Code" on the Review's claim panel and on each experiment's details (website only).
  Link: `vscode://lemmata-local.lemmata/open?pid=…&view=experiments&sel=q:…|x:…`. The extension's URI handler
  (`vscode/src/core/link.ts`, `openFromLink` in extension.ts) checks pid, view and sel, requires the project on the
  connected hub, and opens the Lemmata tab with that claim or experiment selected (`rxGoto`). It never changes anything.
- Extension 0.4.0 (`vscode/lemmata-0.4.0.vsix`, replaces 0.3.0; docs updated).

## Verified
Python 170 passed / 2 skipped; extension unit 66 (new `link.test.ts`); end-to-end 9/9 with Chrome (new S19 test:
link selection reaches the page, an experiment's file opens through the bridge, no vscode:// links inside the tab).
Screenshots: `screenshots/review-baseline-table-{1280,360}.png` (test project, local mode).

## Not verified
- A real VS Code window: the URI handler under Remote-SSH (the link goes to the most recently focused window).
- The "Open in VS Code" button on the hub website was not rendered (the screenshot project runs in local mode, which
  has no project id, so the button is hidden there by design).
