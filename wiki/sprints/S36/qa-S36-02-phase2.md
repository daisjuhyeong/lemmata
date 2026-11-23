---
type: qa-report
owner_agent: qa
status: follow-ups 2026-11-23: A PASS, B PASS on firing and dedup but PARTIAL on the phrase list (negation and except fire), C PARTIAL (the extension unit test s18.test.ts:91 breaks; FAQ text). Suite 276 OK. Earlier: re-check 2026-11-22 after fixes. Python 267 OK, 2 skipped; JS parses. Lines 10-17 PASS on the code (16 with one accepted gap); 18 not walked; 19 PASS for Python, and the extension suites should hold on reading but were not run. One new medium issue (co-author emails in the saved report). Merge waits on that fix, the handoff and Juhyeong.
sources:
  - "S36-01-task.md (acceptance lines 10-19)"
  - "../../design/screens/S36-design-system.md §3, §6, §7"
  - "S36-01-handoff.md (phase 1 context)"
  - "uncommitted working-tree diff on s36-design-system at 1d608f3: app/src/lemmata/engine/{api,todo,trail}.py, new engine/since.py, hub/routes.py, server.py, web/{app.css,app.js,research.js}, tests/test_s36_ui.py, new tests/test_s36_home.py"
  - "vscode/test/e2e/tab.test.ts, vscode/test/integration/views.test.ts, vscode/media/vscode.css, app/src/lemmata/engine/bench.py (read, not run)"
  - "builder's report: web-eng scratchpad s36-p2-report.md (read, not trusted)"
last_reviewed: 2026-11-22
---
# QA: S36-01 phase 2 (Home, Thesis, Review)

QA read the code and ran the Python suite and a JS parse check. Per the founder, the browser checks and the VS Code extension suites were **not run (founder skipped)**: this machine has no browser and no node. Every visual claim below comes from reading the code. None of it was seen on screen.

## Test runs
- **Python:** `PYTHONPATH=app/src:<pytest_stub> app/.venv/bin/python -m unittest discover -s app/tests -p 'test_*.py'`, run outside the sandbox. **Ran 258, OK, 2 skipped.** This matches the builder's count. The baseline was 241, so 17 tests are new: test_s36_home has 11 and test_s36_ui gained 6.
- **JS syntax:** JavaScriptCore `checkSyntax()` (`jsc` with a script calling `checkSyntax(path)`) passes on `app.js` and `research.js`. As a negative control, a broken file was rejected with `SyntaxError`, so the check does detect errors.
- **Engine probe** (scratchpad `timing.py`, on the `make_sample` project):
  - `todo()` takes 168 ms; `baselines()` alone takes 58 ms; `hypothesis()` is about 0 ms; `bench()` takes 175 ms.
  - The to-do item keys are now `act, due, group, key, kind, needs_you, rule, target, text, why`. Both new keys are additions; no existing key was removed or renamed.
  - `GET` (`since(mark=False)`) wrote no `home_seen.json`. `POST` wrote `{"users": {"9f896c6c9dc9": <time>}}`, which holds no login.
- **Extension unit, integration and browser suites:** not checked (founder skipped). They were read; see defect 1.

## Per line
| # | Verdict | Evidence |
|---|---|---|
| 10 Page head | **PARTIAL** | `RX_Q` and `rxPageHead` are at research.js:20-22, and each of the five page functions calls `rxPageHead(RX_Q.*)` (tested in test_s36_ui `test_each_page_starts_with_its_question`). Zeros are said in words (Home :1245ff, Thesis `rxThesisAnswer` :836, Review :1128ff, Setup :1802ff, Trail `trLastDay` :2071). The study line, tree legend, Needs-you, Mismatch and day-panel texts moved behind `?` (`rxHelp` :23). **Still shown by default:** the Thesis map hint "Click a claim to see the experiments…" (:833), the Setup no-map flag, and the map card's prompt hints; the builder lists these. Also, the Trail head says "Reading the history…" even when the load failed (:2078ff) |
| 11 Home is a list | **PASS** | `pageDigest` (:1245) draws the head, Needs you, Since you last looked and This month, in that order. `.hm-cards` and `.hm-card` are gone from js and css (tested). The link "All to-do (N)" (`#hm-todo-link`) opens `rxTodoList(0)` in place |
| 12 Needs you | **PASS** (code) | `needs_you` and `act` are on every item (todo.py:31-44). New kinds: problem, hypothesis, baseline (todo.py:68-78). Feedback counts only when it has no claim and no node (todo.py:54-56). Links come from the graph (`rxNeedsList` research.js:31). A row has the sand dot, "your turn", a single `.hm-line` line (nowrap and ellipsis, app.css:1164), and Confirm only where `act` exists (:1226). `rxSettle` (:1216) posts the same bodies as the existing buttons: `/api/claims {id,state}` as at :209; `/api/map/confirm` as at :735; `/api/hypothesis {action,target}` as `hfAct` at :2175; `/api/baselines {action,name}` as at :2513. It then calls `rxRefresh`, which reloads todo, so the row leaves. The 1280px no-wrap was not seen |
| 13 Since you last looked | **PASS** | **Storage:** `home_seen.json` in the project's own store. The key is `sha256("lemmata-home:"+login.lower())[:12]` (since.py:17-19), and no login is stored in clear (verified by the probe and by the test). **GET** records nothing (server.py:384, `mark=False`); **POST** records (server.py:552). **Hub:** `viewer = _user(dev)` is set only after `_own(pid, dev)` (routes.py:294-296) and is reset per request (:242). `_own` returns 404 to anyone but the project owner (routes.py:226, projects.py:316). There is no cross-project leak: each project has its own file and routes are owner-gated. POST goes through `_csrf`. **First visit:** a 7-day window and the note "You have not opened Home before…" (since.py:58-62, research.js:1245ff). **Who:** shown only from `by`; when it is missing, the row shows the kind word and no name (`_who` since.py:43-52, `rxSinceRow` :1239). **Saved report** (READONLY): no POST (`rxSinceLoad` :1233), and the page says so. See defects 5 and 7 |
| 14 This month | **PASS** | It is the same `trMonth` calendar. `trDayPanel` lists `ssDayRow` rows of Who, What, Where and When (:2046). **What** is the session title made by rules. The only fallback that copies entry titles uses non-run, non-commit entries (sessions.py:321, 450), so no raw command is shown at the first level. The logged commands stay inside the card |
| 15 Thesis | **PARTIAL** | **Lines:** each child draws its own `::after` vertical, and the last child stops at its elbow (app.css:708-709). This replaces the `--bg` cover strip, so the lines are straight in code. **State words** come from `stateWord` (:330) as `.rxt-state`. **Fills:** strong `--accent-vivid`, partial `--accent-light`, weak pale with a `--muted` ring, your turn sand plus edge, no experiment a hollow ring (`.noexp`). A recheck is now `--warning`, not sand, which follows rule 2. **Frame:** `.rx-treeframe` has `overflow-x:auto` below 1100px, with min-width 620 (app.css:1196). **Storyline:** none is drawn, and none exists, which is correct. **Not checked:** label overlap at 1280px on `mcd_extension` and `temporal_dependency`. **Gap:** the tree is drawn only when `RX.claims.has_paper` (research.js:860), so a hypothesis-first project with no paper gets no tree on Thesis (defect 3) |
| 16 Review | **PARTIAL** | The four sections are in order, and "Checked and fine" is a `<details>` closed unless `RX.rvFine`, with its count in the summary (:1128ff, tested). The open table follows the card: compared methods, then ours (weight 600), then the difference, and "no run" in words (`rxRvTable` :1098). **But:** see defect 4 |
| 17 Sidebar | **PASS** | `.sd-dot` is drawn only for `k === 'digest'` (app.js:2108), beside `rxNeedsList().length` (app.js:2116). `.sd-n` is `--text-secondary` (app.css diff). The secondary groups' counts are plain |
| 18 Five look-ups | **PARTIAL** (not walked) | The builder's paths are plausible from the code: Setup cell (1-2), Thesis section (1-2), Setup → number → file (3), Home day → row (1-2), All to-do → setup gap item (1). None was walked in a browser. Path 5 depends on the setup-gap to-do text naming the dataset |
| 19 Nothing else breaks | **FAIL** | Python passes. The extension's browser suite will fail when it runs (defect 1). The unit and integration suites look safe on reading: the to-do shape change only adds keys, and `bench.py:18` `TO_RUN` excludes the new kinds, so the "To run" rows and `views.test.ts:158` are unchanged |

**Sand (rule 2):**
- The allow-list test (test_s36_ui) passes with `.hm-dot` and `.sd-dot` added. Each has a `--highlight-edge` border (app.css:1171-1172).
- A grep of app.js and research.js finds no inline sand style and no hex value.
- Sand buttons on Home appear only in Needs you rows; `rxTodoList` and the digest box have none.
- One sand use outside "your turn" predates this change and sits outside the diff: decision commits on the Claims timeline use `plainChip('◆','Decision','proposed')` (research.js:499). See defect 10.

**VS Code tab (html.embed):**
- `BENCH_PAGES` is still `experiments, setup, item, node` (app.js:1993), so Home and its `POST /api/since` never run in the tab.
- The tree on Thesis is guarded by `!EMBED` (:860).
- Defects 1 and 2 concern the new head in the tab.

## Defects, by severity
1. **HIGH: the extension's browser test breaks.** `vscode/test/e2e/tab.test.ts:106` asserts that `.ptitle` innerText is `'Setup'`. The Setup h1 is now `RX_Q.setup` = "What was used?" (research.js:1802ff), so the S35 test "Setup and Thesis switch in the same tab" fails. Line 19 cannot pass. **Fix (CTO's call):**
   - either update the assertion to `'What was used?'` (test only, so the extension version need not change);
   - or keep the old one-word title in `EMBED` and show the question only on the website.

   Then run the extension suites before merge.
2. **MEDIUM: the tab's title no longer follows vscode.css.** `html.embed h1.ptitle.pq` (app.css:1202, three classes) outranks `html.embed h1.ptitle` in vscode.css:46 (two classes). The tab's heading becomes 20px instead of the 14px the extension sets, and an answer line at 15px is added. Line 9 ("the embedded tab still reads as before") regresses. **Fix:**
   - either drop the `.pq` size rules under `html.embed` so that vscode.css wins;
   - or write the size the tab should have in vscode.css (an extension change, so bump its version).
3. **MEDIUM: Thesis shows no tree without a paper.** research.js:860 requires `RX.claims.has_paper`, but the Claims page draws the tree even with no paper (research.js:261-264). A hypothesis-first project with no paper gets no tree under the head, which breaks line 15. **Fix:** drop the `has_paper` condition, or have the CTO record why it is there.
4. **MEDIUM: line 16 is only partly met.**
   - (a) "A mismatch row states both sides in one sentence" holds only for `differs`: the "paper says X, file says Y" text at todo.py:102, which also falls back to "%d numbers differ.", and partly for `number`. `bold`, `untraced`, `finding` and `contradicts` rows show their text and reason, not both sides.
   - (b) The open view shows the table only when the item targets an experiment (`x:`; `rxRvDetail` :1109). Findings and key numbers open without numbers side by side.
   - (c) "Every number opens its file": table numbers open the Setup trace panel (`rxOpenNumber` :1095), and the file is one more click away. The numbers in the "In the paper … the file says …" sentence are not links at all.

   **Fix:** make the sentence numbers into `rxOpenNumber` buttons. For `bold`, put the bold value and the best value in the sentence. Either have the trace open its file directly or record "number → trace → file" as an agreed departure. The design example "C3 says 'every dataset'; 2 of 6 have no run" needs a new rule, which is the builder's open question 2.
5. **LOW: the Trail's `by` field contains guesses.**
   - trail.py:121 marks a commit as made by an agent when any co-author string contains "claude". A human co-author called Claude or Claudia would be shown as "Your agent". **Fix:** match the Anthropic noreply address or `Claude <…@anthropic.com>`.
   - trail.py:169 and :171 mark the map confirmation and checkpoints as "You". Both can also be done from the CLI (`cli.py:270`) or with a bearer token (`server.py:606`), for example by an agent. The old text "by you" was already there, but it is now a who-column claim. **Fix:** record the actor when these are written, and leave `by` as null until it is recorded.
6. **LOW: `Engine.todo()` got slower and can write.** `Engine.todo()` now calls `baselines()` (+58 ms on the sample, about 35% of `todo()`) and `hypothesis()` (api.py:1439-1446). Both are in try/except, so they cannot raise. However, `hypothesis()` can write `hypothesis.json` (it creates the first `understand_problem` job; api.py:1261). So `GET /api/todo` and `GET /api/bench` (VS Code) can now cause that one-time write. It is idempotent and already happens on `GET /api/hypothesis`. **Fix:** optional. Either pass the S doc into the baselines build to save the second `setup.build`, or accept the cost; record it in the handoff either way.
7. **LOW: the hashed key is a pseudonym, not anonymity.** It is a 48-bit, fixed-salt hash of a public GitHub login, so a list of logins reverses it. It meets "not stored in clear"; it should not be called anonymous. On the hub, "per signed-in user" in practice means the project owner (projects are owner-only). Bearer-token clients (agents, VS Code) can also `POST /api/since` and mark the owner as having looked. A page reload marks again and empties the list. **Fix:** write this in the handoff. Optionally, accept the mark only from cookie (browser) sessions.
8. **LOW: the Thesis answer counts refuted claims as "in mismatch".** It uses the claim stage `refuted` (research.js:836ff). A refuted claim is not the same as a paper-versus-file mismatch, so this count can differ from Review's "Mismatches". **Fix:** count from the to-do `paper` group, or call the word "refuted".
9. **LOW: some line-10 explanations are still shown by default.** See line 10 (research.js:833 and the Setup texts).
10. **LOW, from before this change:** research.js:499 paints decision commits sand through `.chip.proposed`. Phase 1 line 3 should catch this: use a neutral chip.

## The builder's departures
| Departure | Judgement |
|---|---|
| Links come from the client graph, not from hub to-do items | **Acceptable.** The data is already on the page and the confirm path is the existing `decideLink`. Name it in the handoff |
| Feedback "no task yet" is read as an open task with no claim and no node | **Acceptable.** The engine always splits feedback into tasks. Juhyeong decides (builder's question 1) |
| `numbers`, `plan` and `baseline` count as Needs you | **Acceptable.** These are agent drafts that wait on the researcher. The card's "names to confirm" is not mapped explicitly; the CTO should say which kind it means |
| Home keeps a closed fifth block, "This week" (Slack/copy) | **Acceptable.** It is closed and keeps a feature |
| Review keeps a closed fifth block, "Should you continue?" | **Acceptable for now.** The four sections come first and in order. Juhyeong decides (builder's question 3) |
| The tree is on Thesis only on the website; `pageClaims` stays | **Acceptable** (the VS Code tab is the bench) |
| A recheck is `--warning`, not sand | **Acceptable, and required by rule 2** |
| "?" help covers some but not all standing text | **Not acceptable as complete.** Line 10 stays PARTIAL until the remaining texts move or are listed as kept, with a reason |
| `html.embed` head scaled to 20px | **Not acceptable as is** (defect 2) |
| No storyline is drawn | **Acceptable** (none exists) |

## What blocks the merge
1. Defect 1 (the extension's browser test). Fix it, then run the extension suites.
2. Defect 2 (the tab head) and defect 3 (the tree needs a paper).
3. A decision on defect 4: fix it, or record it as an accepted departure.
4. The card's handoff is not written: `S36-02-handoff.md` and the 1360px light and dark screenshots. The founder skipped the browser, so the screenshots need his explicit waiver in the handoff.

Nothing goes to main without Juhyeong.

## Re-check after fixes (2026-11-22)
This re-check follows the "Fixes after QA" section of the builder's report and the CTO's decisions on items 1-10. It was done by reading the code. The browser checks and the extension suites remain **not checked (founder skipped)**.

### Test runs
- **Python** (same command, outside the sandbox, with the stub path): **Ran 267, OK, 2 skipped**. That is 9 more tests than at the first check.
- **JS:** JavaScriptCore `checkSyntax` passes on `app.js` and `research.js`. The broken control file is still rejected.

### Earlier defects
| # | Verdict | Evidence |
|---|---|---|
| 1 Extension browser test | **FIXED** | In EMBED, `rxPageHead` returns only `h1.ptitle` with the one-word title (`RX_SHORT`, research.js:22-25). Setup in EMBED appends `h1.ptitle 'Setup'`, the study line, the behind-note and `rx-x-sum`, the same as HEAD 1d608f3 (research.js:1844 vs HEAD :1677). Thesis in EMBED rebuilds the old `row` with `h1.ptitle.grow 'Thesis'` and the view toggle (:865), the same as HEAD :818. `rxStudyLine` shows its `st-w` inline in EMBED (:123), as before. I read **every** assertion in `vscode/test/e2e/tab.test.ts` (:89-300) against this output: the `.ptitle` 'Setup' at :106; the band `.navtab` and `.navtab.on .navl` (app.js unchanged); the external page list at :119 (`BENCH_PAGES` unchanged, app.js:1993); the Setup cell trace `.su-g td .su-cb` → `.su-tr .su-st` at :133 (the `su-cb` click is unchanged, research.js:1647; it does not use the new `rxOpenNumber`); the map solo title 'Map' at :153; and the Thesis width probe `.rx-x-r` columns at :262-264 (the tree is `!EMBED`, :868). All should hold. `vscode/test/integration/*` relies only on additive fields and the unchanged `TO_RUN` |
| 2 Tab head size | **FIXED** | No `html.embed` rule for `.pghead`, `.pq` or `.pans` is left in app.css (grep count 0), so `vscode.css:46` applies again. A test checks this |
| 3 Tree needs a paper | **FIXED** | research.js:868: `!EMBED && RX.tree && RX.tree.nodes.length` |
| 4 Review | **PASS, with an accepted gap** | todo.py `add(..., sentence, cells, pair)` gives one both-sides sentence for differs, untraced (from the new `untraced_cells`), bold, contradicts, finding (main vs appendix) and key number. I checked the keys it reads: bold uses `col`, `paper` and `best` (experiments.py:288). `rxRvSentence` (:1143) makes the differs numbers into `rxOpenNumber` buttons. `rxRvDetail` (:1131) shows the table when the item names an experiment, otherwise a pair, otherwise words. `rxOpenNumber` (:1104) opens the file when exactly one matches, otherwise the trace. **Gap (accepted by the CTO):** the numbers in bold, untraced, contradicts and finding sentences are plain text, because the engine gives no cell for them. The "2 of 6 have no run" rule is not built |
| 5 Trail `by` | **FIXED** | An agent now requires a co-author address ending `@anthropic.com` (trail.py:121). The map-confirmed and checkpoint rows are "you" only when `confirmed_by`/`by == "you"` was recorded (trail.py:169-172). That is recorded only from a cookie session on the hub (`actor`, routes.py:297) or from the local UI (`getattr(self,"actor","you")`, server.py:525, 609). The CLI (`cli.py:270`) and bearer tokens, including VS Code's `client.checkpoint`, leave it null, and old records show the kind only. `actor` is reset per request (routes.py:243) |
| 6 todo cost | **Accepted** (CTO) | No change |
| 7 since marking | **FIXED** | POST marks only when `actor == "you"` (server.py:556). A bearer token gets the GET answer and writes nothing. The hub test covers both |
| 8 One mismatch source | **FIXED** | `rxMismatches()` (research.js:36) is used by both the Thesis answer (:848) and Review. Thesis leaves out the part when there is no to-do list |
| 9 Standing text | **PASS** | The map hint, the Setup trace hint and the Trail dates note moved behind "?". The texts left visible are state messages or cautions, and the builder lists them with reasons. The CTO accepted this |
| 10 Sand decision chip | **FIXED** | `plainChip('◆','Decision','ign')` (research.js:505) |

### New fields and consumers
- **`untraced_cells`** is added to each experiment (experiments.py:218-223, 493; track.py:265). It is kept out of `problems`, so `test_tree` and the page's problem list are unchanged. Nothing in `vscode/src` or `mcp.py` reads experiment keys by whitelist. The field is additive and **safe**.
- **To-do items** gain `sentence`, `cells` and `pair`. These are additive, and `bench.py` copies only the fields it names. **Safe.**
- **`coauthor_mails`** is a new commit and event key (history.py:43-44, 148). It is additive, and `read_commits` runs at every scan with no disk cache, so there is no stale-cache problem. **But it is a new exposure of personal data; see N1.**

### New defects
1. **MEDIUM (privacy): co-author email addresses now reach `/api/events` and the saved HTML report.** `events()` returns the raw event list (api.py:155-158). `server.py:148-157 snapshot()` writes `e.events()` into the exported report, which people share, for example with an advisor. Before this change an event carried only the author's *name* (`%an`, history.py:26), so this is new data. Co-author addresses can belong to people other than the researcher. CLAUDE.md puts any use of user data under Juhyeong's approval. **Fix:** do not carry the addresses. In `build_events`, store one boolean, e.g. `"agent_coauthor": any(m.endswith("@anthropic.com") for m in co_mail)`, and have trail.py read that. Alternatively, strip `coauthor_mails` from `events()` and from the snapshot. Then add a test that no "@" address appears in `snapshot()["events"]`.
2. **LOW:** on the website, Thesis with no experiments document draws an empty answer line (`rxPageHead(RX_Q.experiments, '')`, research.js:865). Say "Not available." as before.
3. **LOW, a note:** on the local server every request counts as "you" (no auth in local mode), so an agent calling the local API can still mark Home as seen or record a "you" confirmation. This is how the local server already works; write it in the handoff.

### Per line, re-check
| # | Verdict |
|---|---|
| 10 | **PASS** (code) |
| 11 | **PASS** |
| 12 | **PASS** (code; the 1280px no-wrap was not seen) |
| 13 | **PASS** (N3 is noted) |
| 14 | **PASS** |
| 15 | **PASS** on the code. The label overlap at 1280px on `mcd_extension` and `temporal_dependency` was not checked (no browser) |
| 16 | **PASS**, with the accepted gap in defect 4 |
| 17 | **PASS** |
| 18 | **Not walked.** The paths still make sense from the code, and number → file is now direct when there is one file |
| 19 | **PASS** for Python (267 OK). The extension unit, integration and browser suites were **not checked (founder skipped)**; on reading, they should pass |

### What still blocks the merge
1. N1: remove the co-author addresses from events and from the saved report, or get Juhyeong's explicit approval to keep them.
2. `S36-02-handoff.md`. It should cover the accepted gaps (defects 4 and 6, N3) and a written waiver from the founder for the screenshots and the extension suites.
3. Juhyeong's approval of the merge.

## Follow-ups after the founder's answers (2026-11-23)
This checks the uncommitted diff on top of 3294e34: todo.py, app.css, app.js, research.js and the two S36 tests. It was done by reading the code, plus Python probes of the rule function. The browser checks and the extension suites remain **not checked (founder skipped)**.

### Test runs
- **Python** (outside the sandbox, with the stub): **Ran 276, OK, 2 skipped**. This matches the builder's count.
- **JS:** jsc `checkSyntax` passes on `app.js` and `research.js`. The broken control file is still rejected.

### Per item
| Item | Verdict | Evidence |
|---|---|---|
| A. Feedback in Needs you | **PASS** | An item is `needs_you` when it points at a claim or at no target. A task that points only at a node stays in the to-do list with `act` null (todo.py:118-126). The claim-id fix: `cl0.get("id")` when the task view gives a dict (todo.py:118-119). **Done** posts the existing `/api/tasks {id, state:'done'}` (research.js:1131), the same call as the task card (:939), which reaches `server.py:595 set_task`. Done is a plain `.btn sm`, not sand (:1140) |
| B. Coverage rule: firing, dedup, counts only, silent cases | **PASS** | `coverage_items` (todo.py:38-70) handles each case. **Dedup:** dataset names are normalized across all linked experiments, and an experiment listed twice is counted once (probe: `A`/`B`/`b`/`C` across `a`, `b` and `a` again → 3 datasets, 1 missing, experiment ids `[a, b]`). **No linked experiment:** nothing fires (probe: empty section, no section). **Skipped:** benchmark studies, search grids, experiments with no "ours", rejected claims. **Wording:** the sentence is «C1 says “every dataset”; 1 of 3 have no run.», which is counts only. Group `paper`, so it reaches `rxMismatches()` → Review and the Thesis count. Snooze key `coverage:<claim>`. `bench.py` `TO_RUN` does not include `coverage`, so the VS Code To-run list is unchanged |
| B. Coverage rule: phrase list | **PARTIAL** | See defects F2 and F3. The probe results are below |
| C. The two closed blocks removed | **PARTIAL** | No dead calls are left: `rxDigestBox`, `rxDigestProse`, `rxReviewContinue`, `RX_VERDICT`, `RX_CONF_PROMPT`, `rxBaselineTable`, `nbSummary`, `/api/review`, `RX.review` and `rvDays` have no remaining uses in research.js or app.js. `ROW_KEYS` was trimmed. **But:** see F1 (the extension's unit test) and F4 (FAQ text) |
| C. Slack digest in Settings | **PASS** | `rxDigestSettings` (research.js:2462ff) is shown only when `HUB_ON && RX.hub && !READONLY` (:2501). `RX.hub` comes from `rxStartView`, which runs on the hub only (:2620). Every control is a plain `.btn`. It uses the same hub API: `POST /api/hub/projects/<id>/digest` with `webhook`, `enabled` and `weekday`; `set_digest` accepts exactly those, with weekday 0 = Monday, matching `RX_WEEKDAYS` (hub/projects.py:961-983). "Stop and forget" posts `{webhook:'', enabled:false}`, which removes the webhook and does not trip the "add a webhook first" guard. `/digest/send` is unchanged. Only F5 remains |
| VS Code tab | **PARTIAL** | The EMBED pages are untouched: no hunk touches `pageSetup` or `pageExperiments`, and Settings, Review and Home open on the website (`BENCH_PAGES`). `embed.test.ts:9` (`POST /api/review` allowed) is a pure function of `embed.ts` and still passes. **But** F1 breaks the extension's unit suite |

### Probe of `coverage_phrase` (QA's phrasings, not the builder's)
- **Match, correctly:** "every dataset"; "all 6 datasets" and "all six datasets"; "across all data sets"; "every benchmark"; "consistently across the evaluated benchmarks".
- **No match, correctly:** "all metrics"; "every seed"; "all baselines"; "on all but one dataset"; "on most datasets"; "across datasets"; "on all three image datasets" (a named subset).
- **False positives:**
  - "Ours is **not** better on every dataset" and "not best on all datasets": negation.
  - "Best on all datasets **except** Weather" and "On all datasets **but** Weather, ours leads": the exception is exactly the missing dataset.
  - "on all **synthetic** datasets": the claim names a subset, but the rule counts every dataset of the linked experiments.
  - "**Each task**'s model is tuned": `task` is in the noun list, and the word boundary before the `'s` lets the possessive match.
- **False negatives:**
  - Korean ("모든 데이터셋에서", "모든 dataset에서");
  - "on each of the datasets" and "on every one of the datasets";
  - "consistently outperforms baselines across datasets";
  - "all the UCI datasets" and "all real-world datasets" (a word that is not in the adjective list blocks the match).

### Defects, by severity
1. **F1 HIGH: the extension's unit suite breaks.** `vscode/test/unit/s18.test.ts:91` asserts that app.css's `@container app (max-width: 359px)` block contains `.rx-rv-r { grid-template-columns:32px minmax(0,1fr); }`. This change removed that rule (it was at app.css:805 in 3294e34). Line 19 fails again. **Fix:** delete that one assertion, because Review is no longer drawn in the tab and the `.rx-rv-r` rows are gone. It is a test-only change in `vscode/`, so the CTO decides on the version. Also, `vscode/media/vscode.css:79` (`.rx-rv-two`, `.rx-rv-checks`) and `:84` (`.hm-card`) now style nothing. That does no harm; tidy it whenever vscode.css next changes.
2. **F2 MEDIUM: negation and exceptions raise false mismatches.** "not … every dataset", "all datasets except X" and "all datasets but X" fire. The except/but case fires exactly when X is the missing dataset, so a correct claim shows as a mismatch on Review and in the Thesis count. **Fix:** do not fire when `not`, `n't` or `never` appears within the 4 words before the phrase, or when `except`, `but`, `other than` or `apart from` follows it within 3 words. Add these four phrasings to `test_phrases_that_do_not`.
3. **F3 LOW/MEDIUM: named subsets and the noun list.**
   - "all synthetic datasets" counts the real datasets too. **Fix:** when the phrase carries a qualifier (synthetic, real, public), either skip the claim or count only the datasets the map gives that family. Families are out of S36 scope, so skipping is the safe choice.
   - `task` and `tasks` with a possessive ("Each task's") match. **Fix:** require the noun not to be followed by `'s`, or drop `task`/`tasks` from the noun list.
   - The false negatives are acceptable for a fixed list; record them in the handoff. Korean is not covered: say so, since some of the authors write in Korean.
4. **F4 LOW: the FAQ still names a Home section that no longer exists.** Four FAQ entries still say “Next to do” on Home (research.js:2026, 2027, 2028, 2049; the last was edited in this change). Since phase 2, Home has "Needs you" and "All to-do (N)". **Fix:** replace it with "the to-do list (All to-do on Home)" or "Needs you", whichever is meant.
5. **F5 LOW: a dead button on the Settings page.** The section list always holds "Weekly Slack digest" (research.js:2486), so the jump button shows on a local server and in a saved report, where the section is absent. It then does nothing (`el` is null). **Fix:** build `SECS` with the digest entry only under the same `HUB_ON && RX.hub && !READONLY` condition.

### What still blocks the merge
1. F1: the extension unit test (`s18.test.ts:91`). Then run the extension suites.
2. F2: the negation and exception false positives in a rule that reports mismatches.
3. ~~N1~~ **resolved:** commit 3294e34 stores the boolean `agent_coauthor` in commits and events, not the addresses (history.py:44, :148).
4. `S36-02-handoff.md`, and Juhyeong's approval.

## Final re-check (2026-11-23)
This checks the uncommitted working tree on top of 3294e34, by reading the code, with probes and an extension-test stand-in. The Python suite was run by the lead, not re-run by QA. JS: jsc `checkSyntax` passes on `app.js` and `research.js`. The browser checks and the extension suites were **not run (founder skipped)**.

### Per item
| Item | Verdict | Evidence |
|---|---|---|
| F1 `.rx-rv-r` assertion | **FIXED** | `vscode/test/unit/s18.test.ts:91` was replaced by a comment. `vscode/.vscodeignore` ships only `out/src/**`, `media/**`, `package.json` and `README.md`, so tests are not in the .vsix and 0.8.0 stands |
| 1100px `@media`, which QA missed | **FIXED** | The rule is now `@container app (max-width: 1100px)` (app.css:1133). The guard in test_s36_ui.py:245-247 checks that app.css has no window-width `@media`. **QA's miss:** at the phase 2 check, QA read e2e `tab.test.ts` but not the extension's *unit* tests that regex-match app.css. `s18.test.ts` "three width modes" would have failed on 3294e34 |
| F2 negation and exceptions | **FIXED for English** | See the probe below |
| F3 qualifiers and possessive | **FIXED** | "all synthetic datasets", "all the UCI datasets", "all real-world datasets" and "all three image datasets" are silent; "Each task's model" is silent |
| F4 FAQ | **FIXED** | "Next to do", "This week" and "Should you continue" no longer appear. The entries now name "Needs you" and "All to-do" on Home (research.js:2026-2028) |
| F5 Settings jump entry | **FIXED** | The digest entry is spliced into `SECS` under the same `HUB_ON && RX.hub && !READONLY` condition as the section (research.js:2486-2487, :2502) |

### The extension's web-file assertions: QA's own stand-in
I did not rely on the lead's checker (27 lines). I translated, one for one, every assertion in `vscode/test/unit/s18.test.ts` and `link.test.ts` that reads `app.css`, `vscode.css` or `research.js` (31 checks; scratchpad `vsx_check.py`):
- vscode.css: no colours, the theme variables mapped, every selector scoped to `html.embed`, the dark-link rule;
- the three width modes: the container on `#app`, 700px and 359px in both stylesheets, no window-width `@media` in either;
- the narrow and medium grid rules;
- the claims tree rules per width;
- research.js's `vscode://lemmata-local.lemmata/open?pid=` link prefix, and `onUri` in package.json.

Results:
- **31 of 31 pass** on the working tree.
- **Negative control:** the same checker on 3294e34's app.css fails exactly one check, `@media (max-width:1100px)`, so the stand-in does catch this class of break.

The tests in other files that read files (bench, runs, capture) read only `vscode/src` and package.json, or their own temp folders.

**Integration and e2e tests against hub output changed this round:**
- No test reads the text of Home, Review or Settings. Those pages open on the website from the tab: e2e `tab.test.ts:116-119` asserts only the external URLs.
- `views.test.ts:255-257` reads `/api/todo` `items[].key` and `counts.snoozed`, which are unchanged; the new `coverage` and `xs` fields are additions.
- `hub.test.ts:169` `counts.total` is the *runs* document, not to-do.
- The Go-to labels at `views.test.ts:267` come from `vscode/src`.
- `embed.test.ts:9` (`POST /api/review` allowed) tests `embed.ts` only, and the hub route still exists.

Verdict: **should pass**. Not run.

### Probe of `coverage_phrase` (44 phrasings: the earlier set plus new ones)
- **Fires, correctly:** "every dataset"; "all 6 datasets" and "all six datasets"; "each of the datasets"; "every one of the datasets"; "across all data sets"; "every single dataset"; "every benchmark dataset"; "consistently across the evaluated benchmarks"; "consistently beats ADWIN on all datasets"; "With no tuning, ours wins on every dataset" (the "no" is outside the 4-word window); "모든 데이터셋에서 우수하다"; "모든 dataset에서"; "모든 데이터 세트에서 일관되게"; "각 데이터셋에서 MCD가 가장 좋다".
- **Silent, correctly:** all metrics; every seed; all baselines; all but one dataset; most datasets; across datasets; "not better on every dataset"; "not best on all datasets"; "doesn't win on every dataset"; "never worse on any dataset"; "all datasets except Weather"; "On all datasets but Weather"; "all datasets apart from Covtype"; the qualified subsets; "Each task's"; "모든 데이터셋에서 우수하지 않다"; "모든 데이터셋에서 Weather를 제외하고".
- **Remaining false positives:**
  - **R1:** "**Weather를 제외한** 모든 데이터셋에서 우수하다". Korean puts the exception *before* the phrase, and `_EXCEPTION` looks only after it. This fires exactly when Weather is the missing dataset, which is the same failure as F2.
  - **R2:** "**전체 데이터셋**에서 정확도가 높다" usually means "on the whole dataset" (one dataset), not every dataset.
  - **R3:** "각" has no word boundary, so "생**각 데이터셋**" matches. This is unlikely in a claim.
- **Remaining false negatives (silent, which is acceptable):** "every dataset, but it is slower" and "every dataset without extra tuning", because the exception words "but" and "without" also act as conjunctions; "each of the six datasets".
- Non-result sentences such as "Each dataset is split 80/20" and "All datasets are public" match the phrase. They fire only if they are a claim's text and the claim's experiments miss runs, which is acceptable.

### Defects, by severity
1. **R1 MEDIUM (Korean):** add a before-the-phrase Korean exception check: no `제외한|제외하고|빼고|외의` within about 20 characters before the match. Add "Weather를 제외한 모든 데이터셋에서 우수하다" to the silent cases.
2. **R2 LOW:** drop `전체` from the Korean quantifiers, or require a plural marker (`전체 데이터셋들`).
3. **R3 LOW:** require the start of the text or a non-Hangul character before `각`, e.g. `(?<![가-힣])각`.
4. **LOW, for the handoff:** list the fail-silent cases ("but", "without", "each of the N datasets").

### What still blocks the merge
- R1 (a correct Korean claim shows as a mismatch). R2 and R3 can go with it or later.
- `S36-02-handoff.md`. It should list the accepted gaps, the fail-silent cases, and the founder's waiver of the screenshots and the extension suites (not run on this machine).
- Juhyeong's approval of the merge.
