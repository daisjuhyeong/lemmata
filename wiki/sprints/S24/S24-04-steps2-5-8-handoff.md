---
type: handoff
owner_agent: lead
status: needs-qa
sources: ["founder chat 2026-11-16 12:02 KST (\"build the other steps\") and 12:03 KST (\"How about following the IPEL lab website?\", answered: shell and Home)", "../../decisions/ADR-008-top-down-evidence-spine.md", "S24-02-build-plan.md", "S24-01b-ibel-portal-reference.md"]
last_reviewed: 2026-11-16
---
# S24-04: steps 2, 3, 4, 5 and 8

## Built
- **Step 2, rules shown.** `claims.stage_of` returns the rule (C2-C9); a stage you set is C1. The stage chip's hover,
  `claims.md` and the MCP `claims` tool name the rule. MCP `claims` also gives each link's status, rule and sentence.
- **Step 3, criterion per link.** Fields: `compare` (best other, base, or a method name), `over` (main column, every
  dataset, most datasets, the average), `strict`. Sources, in order: yours (`experiments.json`, set in the row's
  "Supports when" line), the confirmed map's (`experiments[].criteria`, checked by `understand.verify`), the default.
  A non-default criterion also decides the claim's stage. Not built: choosing another metric column (the main one is
  used), and a separate "drafted" state (a map criterion counts once the map is confirmed).
- **Step 4, To-do.** `engine/todo.py`, `GET /api/todo`, `POST /api/todo` (snooze only), MCP `todo`. Groups in order:
  someone is waiting, needs your confirmation, the paper is wrong today, out of date, gaps. Each item opens its target.
- **Step 5, Trail.** `engine/trail.py`, `GET /api/trail`, `POST /api/deadlines`, MCP `trail`. The History page is now
  the Trail: deadlines ahead, filter by kind, day rows by week, and **a whole-month grid at the bottom** (dots per
  kind, deadlines in red, click a day to jump to it). Claim stage entries open the claim. Commit links to GitHub are
  built but untested (the fixture has no GitHub origin).
- **Step 8, shell and Home, after the IBEL portal** (Juhyeong chose "Shell and Home"; DAIS colours and type kept).
  - Website, wide windows: a slim top bar (name, project, search) and one left sidebar with every page: Home,
    Thesis, Setup, Review, Trail, then Explore and Work.
  - VS Code tab and windows under 1000 px: the band with five tabs, as before, now Home · Thesis · Setup · Review · Trail.
  - **Thesis** = the Experiments page (Outline, Map) and the Claims page (Tree, List) joined by one switch.
  - **Home** = the old Digest key: thesis counts, Next to do, Deadlines, Last 7 days, This week. It is the start page.
  - Old keys (`claims`, `experiments`, `digest`, `history`) and VS Code links still open the matching page.

## Not built
- Step 6 (a "running" status from logged runs), step 7 (native VS Code Thesis tree), step 9 (viewer).
- The projects list does not yet show thesis counts per project.
- Exported snapshots include To-do and Trail data, but this was not opened in a browser.

## Verified
Python 179 passed / 2 skipped (new: `test_stage_rule_ids`, `test_criterion`, `test_todo_and_trail`; nav test updated).
Extension unit 68. Browser on the fixture at 1440 px and 800 px: Home, a to-do item opening its experiment, Trail,
month grid (previous month, click a day), a stage entry opening the claim, the criterion changed in place; no
console errors. Screenshots: `home.png`, `thesis-criterion.png`, `trail-shell.png`, `narrow-800.png`.

## Not verified
Any real project; the hub's multi-project pages with the new shell; end-to-end extension tests; QA.
