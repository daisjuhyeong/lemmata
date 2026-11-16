---
type: handoff
owner_agent: lead
status: needs-qa
sources: ["founder chat 2026-11-16 12:31 KST (request) and 12:32 KST (answers: subscription link; deadlines and milestones only; replace the curve map; order approved)", "https://github.com/ccfddl/ccf-deadlines (deadline data, read 2026-11-16)", "https://neurips.cc/Conferences/2022/PaperInformation/PaperChecklist (checklist questions)"]
last_reviewed: 2026-11-16
---
# S25-01: Setup as a protocol sheet, calendar on Home, venue deadlines, calendar link

## Built
- **Setup, top-down** (`engine/setup.py`, `web/research.js`). The curve map is gone. Per claim, one sheet per
  experiment: the link word, the protocol (metric and direction, datasets, methods with roles, runs per result,
  paper table), a coverage grid (methods × datasets, value, ×runs, best in bold, missing cells outlined), and a
  checklist of six questions (coverage, more than one run, paper matches files, results newer than code; "data splits
  and hyperparameters stated" and "compute stated" are marked "you check" because Lemmata cannot read them).
  Clicking a number opens its trace: 1 the paper cell and whether it matches, 2 the result files averaged into it,
  3 the script and settings found, 4 the last commit that wrote it. Clicking a metric, dataset or method filters the
  sheets to it and shows where the paper and code name it (the S23 panel).
- **Calendar on Home.** The month grid sits under the thesis header. Clicking a day opens a panel: each commit with
  the experiments whose result it moved (claim tested, before → after, better or worse, best other), the files by
  kind, claim stage changes with their source, and deadlines with the count of open to-dos.
- **Venue deadlines** (`engine/venues.py`). A conference is looked up by short name and year in the ccf-deadlines
  files on GitHub (`conference/<folder>/<name>.yml`, read line by line; no YAML library, no model). The result is
  shown with its source and the venue's own link; nothing is stored until "Add these dates". "TBD" entries are shown
  as not announced. Journals and own dates are entered by hand (kind `journal` or `milestone`).
- **Calendar link.** `GET /api/calendar.ics` (download) and a subscription link `/cal/<project>/<token>.ics` served
  by the hub without a session; the token (24 random bytes) is made and revoked by the owner. Only deadlines and own
  dates are in the file.
- **Fix:** the POST routes `/api/todo` and `/api/deadlines` from S24 were missing from the server's allowed list, so
  Snooze and Add deadline failed on the page. They are allowed now, with `/api/venue` and `/api/calendar`.

## Not built
- Weekly automatic re-check of a stored venue's dates (re-adding the venue refreshes them).
- A venue index: an unknown short name gives "not found" without suggestions. Aliases: neurips → nips, kdd → sigkdd
  (the second is a guess, not checked).

## Verified
Python 180 passed / 2 skipped (new `test_venues_calendar_and_sheet` with a fake fetch; `test_hub` covers the feed:
404 before a link exists, 200 with the token and no session, 404 for a wrong token, another project or after
revoke). Extension unit 68. Browser on the fixture: Setup sheet and trace; live lookup of ICML 2027 from GitHub;
journal date added; Home calendar and day panel; no console errors.

## Not verified
- Google Calendar actually subscribing to the link (needs the hub's public address).
- The feed under Tailscale Funnel: a private hub refuses Funnel requests, so the link works only once the hub has a
  public URL configured.
- Any real project. QA.

## Added 12:44 KST: the same pages in VS Code (extension 0.7.0)
Juhyeong: "apply this to VS code as well and I want to see the updates on both vs code and website".
- The VS Code tab shows the hub's pages, so Home, Thesis, Setup and Trail appear there once the hub runs this branch.
  Extension changes: views `history` and `trail`; commands **Open Home** (`lemmata.openTab.digest`) and **Open Trail**
  (`lemmata.openTab.history`); "Open Experiments" is now titled **Open Thesis**. Wide pages use the editor's width.
- In the tab there is no left sidebar (the five tabs stay in a row), and the calendar link is made on the website
  (the tab cannot be reached by Google). Commit links in the trail open in the browser.
- Fixed in the Setup trace: an experiment read from a paper table showed "in undefined" and "no result file".
- `test/e2e/tab.test.ts` opens Home (with a day), Setup (with a traced number) and Trail in the real tab against a real
  hub; all 10 end-to-end tests pass. Screenshots `screenshots/vscode-*.png` (the test webview has no VS Code theme, so
  borders are missing there; inside VS Code they come from the theme).
