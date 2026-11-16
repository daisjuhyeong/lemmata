---
type: handoff
owner_agent: lead
status: needs-qa
sources: ["founder chat 2026-11-16 11:21 KST (\"Go. add a whole month view at the bottom.\")", "../../decisions/ADR-008-top-down-evidence-spine.md", "S24-02-build-plan.md step 1"]
last_reviewed: 2026-11-16
---
# S24-03: step 1, the top-down Experiments page

## What changed
- **Engine (`engine/api.py`, `experiments()`):**
  - Each section (claim) carries `links[<experiment id>] = {status, rule, why, criterion, criterion_by}` and a `bar` of
    counts. Status is one of supports / contradicts / inconclusive / not_run, from rules L1-L4 with the default
    criterion (ours at least as good as the comparator on the main column; a tie counts as support). The link sits on
    the section because one experiment can test two claims. (The build plan named `track.py`; the comparator choice
    lives in `api.py` beside `_outcome`, so the link is computed there with the same inputs.)
  - `E["thesis"]`: the core message text and paper location, claims per stage, links per status, and two buckets:
    claims with no experiment (listed) and experiments with no claim. Counts only, no verdict word (rule T1).
- **Experiments page (`web/research.js`, `web/app.css`):**
  - Thesis header first: the sentence, its paper line, claims by stage, an evidence bar of the links, and the two
    gap buckets (always shown, 0 when empty; a non-empty bucket opens its list).
  - Each claim header: stage chip, paper anchor when known, an evidence bar.
  - Each experiment row starts with the link word as a bracket tag (`[supports]`); hovering shows the sentence and
    the rule.
  - The project map card moved below the claims. The Map view's root box shows the thesis, with the method under it.
  - The page uses the wide column, as Setup does. Legends now have spacing (they had no style).
- No nav change, no new store, no change to any claim's stage.

## Verified
Python 176 passed / 2 skipped (new `test_links_and_thesis`: every link has a word and a rule, stages equal before
and after, thesis counts add up, one experiment on two claims has a link on each, both buckets counted;
`test_link_rules`: L1-L4). Extension unit 68. Browser on the `test_map` fixture at 1280 px and 640 px, Table and Map
views, row expanded: header → claim groups → map card in that order, no console errors.
Screenshots: [screenshots/](screenshots/).

## Not verified
- Not run on `mcd_extension` or any real project. End-to-end extension tests not run.
- At 640 px the "ours vs" bar's number can touch the "Last" column. This was so before this step.
- Contradicts and not-run rows were tested by rule, not seen in the browser (the fixture has none).

## Next
Step 2 (rule ids on claim stages and in MCP), then steps 3-5. Step 5's Trail gets a whole-month grid at the bottom
(recorded in the build plan).

## Added 11:34 KST: left sidebar
Juhyeong: "the history section and the graph section is at the bottom of the page, but I want it at the sidebar".
- `web/app.js`: `buildShell` wraps the page in `#body` with an `aside#side` (website only, not the VS Code tab);
  `renderLeft` (a no-op since S18) now draws three groups (Look back: History, Growth, Changes · Explore: Graph,
  Notation, Checks · Work: Tasks, Ask, Search) plus Project menu and How Lemmata works, with the current page marked
  and counts for Changes, Checks and Tasks.
- `web/app.css`: the sidebar is sticky; below 1000 px (container query) it hides and the footer links come back.
  The footer's state line (last looked at, sync) stays at the bottom.
- Checked in the browser at 1440 px (Experiments, History, Graph) and 900 px; no console errors. Screenshots
  `sidebar-*.png`.

## Checked on the live hub (11:40 KST)
The hub at 100.111.135.94:8765 was already serving step 1: its `app.js`, `research.js` and `app.css` have exactly the
lengths of this branch's files at commit b3c6f3c. Project data was not checked (the browser pane is not signed in).
