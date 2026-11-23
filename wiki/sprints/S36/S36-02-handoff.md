---
type: handoff
owner_agent: lead
status: phase 2 built, plus the founder's follow-ups (2026-11-23); QA passed by reading the code and running the Python suite; browser, screenshots and extension suites waived by the founder
sources:
  - "S36-01-task.md (acceptance lines 10-19) ; ../../design/screens/S36-design-system.md §6-7 ; ../../decisions/ADR-012-design-system-and-your-turn.md"
  - "S36-01-handoff.md (phase 1) ; qa-S36-02-phase2.md (QA report and re-check for this phase)"
  - "code on branch s36-design-system: app/src/lemmata/engine/{since.py (new),todo.py,trail.py,history.py,experiments.py,track.py,api.py}, app/src/lemmata/{server.py,hub/routes.py,fixture_engine.py}, app/src/lemmata/web/{research.js,app.js,app.css}, app/tests/{test_s36_home.py (new),test_s36_ui.py}"
  - "founder answer in chat, 2026-11-22: 'Skip browser and extension checks'"
  - "founder answers in chat, 2026-11-23: '1. Skip the browser check. 2. Confirm 3. Yes 4. Now 5.drop'"
  - "test runs on 2026-11-23 on the founder's Mac: Python 279 ran, OK, 2 skipped; JavaScriptCore checkSyntax passes on app.js and research.js; the 31 web-file checks of the extension unit tests, rerun in Python, hold"
last_reviewed: 2026-11-23
---
# S36-02 handoff: phase 2, Home, Thesis and Review (acceptance lines 10 to 19)

## What changed for the researcher
- **Every main page opens with its question and an answer line.** Home "What needs you today?", Thesis "Is each claim
  backed?", Setup "What was used?", Review "What disagrees?", Trail "What did you do, and when?". The answer line is built
  from counts the hub already returns, and a zero is said in words ("Nothing waits for you."). Explanations sit behind a "?"
  in their section.
- **Home is a list:** Needs you, Since you last looked, This month. The tiles are gone. "All to-do (N)" in the answer line
  opens the full to-do list in place.
- **Needs you** lists only what the researcher can settle: drafted claims, the proposed map, the problem and hypotheses,
  proposed baselines and names, proposed numbers and plans, suggested links, and feedback that Lemmata could not attach to a
  claim or node. Each row has the your-turn dot, one sentence that does not wrap, and its buttons. Confirm works in one click,
  and the row then leaves the list.
- **Since you last looked:** what changed since the last visit, newest first, saying who (your agent, a run, Lemmata, a
  person) only where the record says so. On a first visit it covers 7 days and says so.
- **This month:** the calendar as before. Clicking a day lists rows of who, what, where and when. Raw commands sit one
  click further down ("Show the records").
- **Thesis:** under the head, the claims tree with straight lines, a state word beside every node, and the fills from the design page.
  Below 1100px the tree scrolls inside its own frame. It no longer needs a paper.
- **Review:** Mismatches, Stale, To confirm, and Checked and fine (closed, with its count). Each mismatch is one sentence
  with both sides. Open, it shows the compared methods, then the project's own, then the difference, with "no run" in words.
  Numbers in the sentence and the table are links.
- **Sidebar:** only Home carries the sand dot, beside the Needs you count. Every other count is a plain number.

## How it is built
| Line | Where | What |
|---|---|---|
| 10 | `research.js` `RX_Q`, `rxPageHead()`, `rxHelp()` | The five questions; head and answer line; "?" help. In the VS Code tab (`EMBED`) the head is the old one-word `h1.ptitle` with no answer line, so the tab reads as before and `vscode/test/e2e/tab.test.ts` holds unchanged |
| 11 | `pageDigest()` | Head, Needs you, Since you last looked, This month. `.hm-cards` CSS removed |
| 12 | `engine/todo.py` (`needs_you`, `act`, `NEEDS_YOU`; new kinds `problem`, `hypothesis`, `baseline`), `rxNeedsList()`, `rxNeedsRow()`, `rxSettle()` | **New hub field:** every to-do item has `needs_you` (bool) and `act` (the one click that settles it, or null). Suggested links come from the page's graph (`S.graph.edges`) and use the existing `decideLink` |
| 13 | `engine/since.py` (new), `Engine.since()`, `GET`/`POST /api/since` (local server and hub), `trail.py` `by` | **New hub record:** `home_seen.json` per project, keyed by a 12-character hash of the GitHub login (`local` in local mode). GET reads; POST returns the unseen changes and records the visit, only for browser sessions (bearer tokens get the GET behaviour). Trail entries carry `by` only from the record: an agent = a co-author address ending `@anthropic.com` (kept as the boolean `agent_coauthor`, with no address stored); "you" only where a browser session wrote it; otherwise null, so the row shows its kind and no name |
| 14 | `trDayPanel()`, `ssDayRow()` | Rows of Who, What, Where and When; the raw records are one click down |
| 15 | `rxThesisTree()`, `rxTree()`, `app.css` `.rxt*`, `.rx-treeframe` | Each node draws its own vertical segment and elbow; `.rxt-state` holds the words; fills per design §7; a recheck is `--warning`, not sand; `@media (max-width:1100px)` frame scroll |
| 16 | `pageReview()`, `rxMismatches()`, `rxRvSentence()`, `rxRvDetail()`, `rxOpenNumber()`; `todo.py` `sentence`, `cells`, `pair`; `experiments.untraced_cells` | Four sections in order. Both-sides sentences for every mismatch kind. A number opens its file directly when exactly one file holds it, otherwise its trace on Setup |
| 17 | `app.js` `renderLeft()`, `navBadge`; `.sd-dot`, `.sd-n` | Sand only on Home |
| 19 | | Python suite passes; `vscode/` unchanged |

Allow-list in `test_s36_ui.py` gains `.hm-dot` (Needs you rows) and `.sd-dot` (sidebar), each with a `--highlight-edge` border.
Decision commits on the Claims timeline no longer borrow the sand `.chip.proposed`.

## Line 18: the five look-ups from Home (read from the code, not walked in a browser)
1. **The main method's result on one dataset:** Setup (1). The protocol sheet marks the project's own row "Ours" and has the datasets as columns. On a project with over 12 sheets, pick the step (2).
2. **The experiments behind one claim:** Thesis (1). The claim's section lists its experiments with a status word. Or click the claim in the tree (2).
3. **The file a chosen number came from:** Setup (1), click the number (2). If one file holds it, the file opens; otherwise the trace lists the files, and a click on one opens it (3). From Review: Mismatches (1), then the number in the sentence (2).
4. **What was run on a chosen day:** click the day in This month (1). The rows say who, what, where and when. Click a row (2) for its card.
5. **The datasets where a baseline has no result:** "All to-do" in the answer line (1). It lists items such as "ADWIN: No result on Weather". The same items show on Setup.

## Departures from the card, and why
- **Suggested links** come from the page's graph rather than a hub-side list. The data is already on the page, and the confirm path exists.
- **"Feedback that has no task yet"** does not exist in the engine, because feedback is split into tasks when it arrives. It is read as "an open task that Lemmata could not attach to a claim or node".
- **Review numbers:** in the bold, untraced, contradicts and finding sentences the numbers are plain text, because the engine gives them no cell to point at. The Average column holds several files, so it opens the trace. The design example "C3 says 'every dataset'; 2 of 6 have no run" is now built (founder's answer 4, below).
- **Standing text left visible:** state messages and cautions only (e.g. "No confirmed project map yet…", "Reading the experiments…", the venue-lookup caution). The builder's report has the full list.
- **No storyline section** is drawn, because no confirmed storyline exists yet (S32 step 1 is not built).
- **The tree is on the website only.** The VS Code tab keeps its own outline (ADR-011).
- **`Engine.todo()` now also builds hypotheses and baselines** (about +58 ms on the sample, about 35%). Each is in try/except. The first call can write `hypothesis.json` once, as `GET /api/hypothesis` already did. The VS Code bench calls it too. Accepted.

## Verified
- **Python:** 279 ran, OK, 2 skipped (268 at `3294e34`, before the follow-ups). Same command and `pytest.raises` stand-in as phase 1, run outside the sandbox.
- **JS:** `app.js` and `research.js` pass JavaScriptCore `checkSyntax`. The builder also ran the page functions against real engine output from the `test_map` project in a stubbed DOM under JavaScriptCore, with 0 errors. Confirm from Home posted `/api/claims {"id":"c1","state":"confirmed"}`.
- **QA by reading the code** ([qa-S36-02-phase2.md](qa-S36-02-phase2.md)), in two rounds:
  - The first round blocked on the VS Code test and heading, on a tree that needed a paper, on Review's sentences, on guessed authors, on agents marking Home as seen, and on a sand decision chip. All are fixed.
  - The re-check found that co-author email addresses would reach the saved HTML report. Now only a true/false flag is kept, and a test checks that no address appears in `/api/events` or the snapshot.
  - QA read every assertion of `vscode/test/e2e/tab.test.ts` and the integration tests against the new output, and expects them to hold.
  - The follow-ups (founder's answers) took three QA rounds: false matches in the coverage rule (negation, exceptions, subsets, Korean word order), stale FAQ text, a jump button with no section on a local server, and the `@media` break above. All are fixed.

## Not checked
- **Everything visual, and every screenshot.** The founder skipped browser checks on this Mac (no scriptable browser). So `screenshots/` has no before and after pairs, and none of these were seen: 1360, 1280, 1100, 760 and 420px, light and dark, wrapping of the one-sentence rows at 1280px, the tree lines and fills, the 1100px frame.
- **Labels in the tree on `mcd_extension` and `temporal_dependency`** (line 15). The second is not on this Mac.
- **The extension's unit, integration and browser suites.** There is no node here. Its shipped files did not change; one stale unit-test assertion was removed. The unit tests' 31 checks on the web files were rerun in Python.
- **Two people on a public hub.** This was tested only at the engine level: a private hub has only its owner, so "per signed-in user" there means the owner.
- **The local server treats every request as "you".** So an agent calling the local API can still mark Home as seen.
- **The hashed key is a pseudonym, not anonymity.** It is a fixed-salt hash of a public GitHub login.

## Founder's answers (chat, 2026-11-23) and what was done
| # | Question | Answer | Done |
|---|---|---|---|
| 1 | Browser check and screenshots before main | "Skip the browser check." | **Superseded the same day:** two chats had recorded different answers, and the founder then chose the Playwright check ([S36-03](S36-03-handoff.md), with before and after screenshots). The extension suites stay unrun (no node on this Mac) |
| 2 | `home_seen.json` (hashed GitHub login and last-opened time, per project) | "Confirm" | Kept as built |
| 3 | Feedback tasks that point at a claim in Needs you | "Yes" | An open feedback task needs you when it points at a claim or at nothing; one that points only at a file or experiment stays in the to-do list. Row: "C2: <task text>", with Done (the existing `/api/tasks` call) and Open (the claim). No Snooze: feedback has none today. Also fixed: the claim a task pointed at was passed on as an object, not its id |
| 4 | The claim-text rule | "Now" | Built (below) |
| 5 | The closed "This week" and "Should you continue?" blocks | "drop" | Both removed with their JS and CSS; the hub endpoints stay. **One exception (CTO):** the weekly Slack digest had no other control, so a saved webhook would have kept posting with no way to stop it. Its existing controls (URL, on/off, weekday, send now, stop and forget) moved unchanged to a "Weekly Slack digest" section in Settings, shown only on a hub |

### The coverage rule (answer 4)
- `engine/todo.py`, kind `coverage`, group `paper`, so it appears under Review → Mismatches and in the Thesis "in mismatch" count.
- **When it fires:** a non-rejected claim makes a universal statement over datasets ("every/each dataset", "all (N) datasets",
  "each of the datasets", "consistently … across (all) datasets", 모든/각 데이터셋), and the experiments linked to it have
  datasets with no result for the project's own method. Datasets are counted once by name across those experiments.
- **The sentence:** «C3 says "every dataset"; 2 of 6 have no run.» Counts only, no verdict. Opened, it lists the missing
  datasets and shows the side-by-side table with "no run".
- **When it stays silent:**
  - negation before the phrase ("does not win on every dataset");
  - an exception after it ("except", "but", "other than", "apart from", "excluding", "save for"), or before it in Korean (제외한, 제외하고, 빼고, 외의, 말고);
  - a qualifier that names a subset ("all synthetic datasets", "all the UCI datasets", "all three image datasets");
  - possessives ("each task's …"), and other nouns ("all metrics", "every seed", "all baselines");
  - claims with no linked experiment, full coverage, and benchmark studies with no "ours".
- **Known misses** (chosen: when unsure it stays silent): "on every dataset, but it is slower", "every dataset without extra
  tuning", "each of the six datasets".
- **Checked on:** the `test_map` fixture (fires when a result file is removed; silent otherwise). `~/mcd_extension` was loaded
  read-only (a temporary project with a symlink; that repo's git state was unchanged). It has no claims, so the rule had nothing to
  check. `temporal_dependency` is not on this Mac.

### What dropping the blocks removed from the website
The copy-for-a-meeting text; the three checks; the hoped conclusion; the claim questions; and the confound checkboxes (their
tools still work for an agent through MCP). The numbers comparing the project's own method with each baseline are still on
Baselines and Setup; the plan box is still on an experiment's page. Four FAQ answers that pointed at "Next to do" or "This
week" now point at "Needs you" and "All to-do".

### A fix to phase 2 in this round
`3294e34` (on `next`) broke the extension's unit test "three width modes", which forbids window-width `@media` in `app.css`. The
tree frame used `@media (max-width:1100px)`. It is now `@container app (max-width: 1100px)`, and a Python test guards this.
QA's earlier phase 2 check had read the extension's browser test but not its unit tests. The stale `.rx-rv-r` assertion in
`vscode/test/unit/s18.test.ts` was removed: Review rows are not in the tab, and tests are not packaged, so the extension stays 0.8.0.
All 31 checks in the extension's unit tests that read `app.css`, `vscode.css` or `research.js` were rerun in Python and hold.
The rest of those suites need node and were not run.

## References named
- Home as a list and the page heads follow the canvas the founder reviewed (design page, sources). No other pattern was borrowed.
