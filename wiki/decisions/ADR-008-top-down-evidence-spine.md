---
type: adr
owner_agent: cto
status: approved
sources:
  - "../sprints/S24/S24-01-cto-benchmark-to-lemmata.md (founder chat 2026-11-16 10:43 and 10:54 KST, quoted there; research facts and proposals)"
  - "../architecture/benchmark-structures.md (what each benchmark tool does, with URLs and [P]/[3P]/[NV] marks)"
  - "../sprints/S24/S24-01b-ibel-portal-reference.md (founder chat 2026-11-16 11:01 KST; IBEL portal observed at https://ibel-research-portal-demo.vercel.app, [P])"
  - "ADR-006-public-multi-user-site.md (accounts, projects belong to one account, others get 404)"
  - "code read for S24-01b, 2026-11-16: engine/process.py (timeline, ledger, split_feedback, match_targets, also_check, add_feedback, tasks_view, set_task, digest), engine/api.py (claims: stages.json log; tree: marks; digest; runs), engine/claims.py (tree: born, span; decide has no timestamp), engine/plans.py (at), engine/understand.py via api (proposed_at, confirmed_at), web/research.js (pageTimeline with rxTree scrubber, pageTasks, rxTaskCard, pageDigest, rxDigestBox, rxDigestProse), web/app.js (pageHistory, pageChanges, READONLY = snapshot)"
  - "ADR-007-project-map-two-phases.md ; ../sprints/S23/S23-01-handoff.md ; ../sprints/S17/S17-brief.md ; ../design/screens/S18-dais-ui.md"
  - "code on branch s24-topdown-evidence, read 2026-11-16: app/src/lemmata/engine/claims.py (draft, pick_core, _status, STAGES, stage_of, _roll, restage), engine/track.py (build, experiment, sections, 'other'), engine/experiments.py (build, unassigned), engine/review.py (_state, checklist, build, hoped), engine/setup.py (build), engine/understand.py (TYPES, verify, map format), engine/runs.py (view), engine/process.py (ledger stale), engine/api.py (claims, experiments, experiment, setup, review, confirm_map, set_experiment), server.py (_api routes), mcp.py (tool list), web/app.js (NAV, NAV_OF, renderPage), web/research.js (pageClaims, rxCoreCard, pageExperiments, rxExpMap, rxExpRow, pageReview, pageSetup, RX_PAGES), vscode/package.json (views lemmata.panel, lemmata.runs), vscode/src/{extension.ts, runs.ts, tab.ts, core/embed.ts VIEWS, core/link.ts}"
last_reviewed: 2026-11-16
---
# ADR-008: A top-down evidence spine, Thesis → Claim → Experiment, with rule-made status on each link

Status: **proposed** (needs Juhyeong's approval; nothing is built). Task: [S24-01](../sprints/S24/S24-01-cto-benchmark-to-lemmata.md). Build plan: [S24-02](../sprints/S24/S24-02-build-plan.md). Diagrams: [docs/map/](../../docs/map/README.md).

## Decision in short
1. **Spine.** Thesis → Claim → *link (criterion, status)* → Experiment → Setup (dataset, metric, methods) → result files, scripts, settings, runs → paper location. **The Thesis is the existing core message (`claims.core`).** There is no new object.
2. **Status sits on the claim-experiment link**, because one experiment can test two claims. There are four words: **supports, contradicts, inconclusive, not run**. A fifth, **running**, comes later, once logged runs are joined to experiments. Stale and "to check" are flags, not statuses.
3. **Claims keep the S17 stage words** (Hypothesis, Being tested, Finding, Not supported, Exploration). The rules are today's rules, restated over link statuses and numbered so that each status can show its rule. **The Thesis shows counts only.**
4. **Criterion.** Every link has one. Until the agent drafts one and the researcher confirms it, the default criterion applies: today's rule, ours at least as good as the comparator on the main column. The source (default / drafted / confirmed) is always shown.
5. **Pages, in two phases.** Step 1 makes the Experiments page top-down and changes no nav. Phase 2 needs Juhyeong's approval. It merges Claims and Experiments into one **Thesis** page with two lenses (Outline, Tree) and turns Digest into a **Home** for the research. With a **Trail** tab added, the nav reads **Home · Thesis · Setup · Review · Trail**, five tabs as today (§5).
6. **VS Code.** A native tree view, **Thesis** (Thesis → Claim → Experiment → files at the line), goes first in the existing Lemmata container. The webview tab stays for the detail. No new status bar item: the existing one carries the counts.
7. **To-do.** One list made by rules from what Lemmata already knows, plus the feedback tasks. Every item opens the claim, experiment, setup item or paper line it is about. Items are ordered by who or what is waiting (§5.1).
8. **Trail.** A backward-looking time axis built from records that already exist: commits, runs, stage changes, map confirmations, feedback, checkpoints and plans. Deadlines are the only new input. Trail absorbs History and the Timeline step list. Clicking an entry opens the object as it was at that time, wherever the data allows (§5.2).
9. **Home and watching.** One page per research project: thesis counts, the next to-dos, the recent trail and the deadlines. Others watch through the exported read-only snapshot now, and later through an invite-only viewer role that needs approval (§5.3).
10. **Shell.** The website keeps the top band (S18, DAIS). In VS Code, the native Thesis tree is the sidebar. No left sidebar on the website (§5.4).

## Context
Juhyeong asked for the page "to be orchestrated Top-down style so that we can check how such thesis is backed up by the experiment done so far" (chat 2026-11-16 10:43, quoted in the task card). The research proposed a spine and statuses. Reading the code shows that part of the spine already exists, and that some of the research's starting points are not accurate.

| Research said | The code says (this branch) |
|---|---|
| "The thesis is not an object." | `claims.core` exists. It is the **core message**, drafted from the abstract by `claims.pick_core` and reworded through `POST /api/claims {id:"core", text}`. It has `children` (all live claims), a `stage` rolled up by `claims._roll`, and a stage meter (`rxCoreCard` on Claims). The Review page also holds a free-text **hoped conclusion** (`review.json` `hoped`). A map can carry a **goal** (`map.goal`, extensions only). |
| "Experiments starts from the method." | Only the **Map** view does: `rxExpMap` draws "Ours" (`E.map.method.name`) as the root. The **Table** view, which is the default (`RX.exView \|\| 'table'`), already has one section per claim, as S18 specified. |
| "Claims / Experiments / Setup are peers." | True. `NAV` in `web/app.js` has five tabs: Claims, Experiments, Setup, Digest, Review. |
| A status per experiment | Today it is **per experiment, not per link**. `review._state` gives ahead / behind / tie / none against the best other method, or against `base` when the work extends a paper and the claim is the extension's own. `claims.stage_of` turns these into the claim's stage. There is **no criterion** anywhere. |
| Two buckets | Both exist. In map mode: the section `id:"other"` ("No claim yet", `counts.no_claim`) and sections with `status:"unsupported"` (`counts.untested`). In rule mode: `unassigned`. Today they sit at the **bottom** of the page (`other` is last), or appear as "Not tested yet" inside each claim section. |
| Runs on the detail | Run **records in the repo** (`runs/<id>.json`) are graph nodes, and the detail shows them (`x.design.runs`). Runs **logged from VS Code or the agent** (`runs.json`, `engine/runs.py`) are **not joined to experiments**. `runs.view` only says which tracked result files a run wrote. "Running" (no `ended`) is known only to the VS Code Runs view (`vscode/src/runs.ts`). |

There are also too many status vocabularies today. A reader meets about nine of them:

| Where | Words |
|---|---|
| `claim.status` | supported / partial / unsupported |
| `claim.stage` | hypothesis / testing / finding / refuted / exploration (+ `recheck`) |
| map section `status` (`track.py`) | supported / partial / unsupported, but meaning "tested, nothing to check / something to check / not tested" (`WORD` in `pageExperiments`) |
| experiment state | ahead / behind / tie / none, plus `attention`, plus the glyphs ✓ ! ? in `rxExpRow` |
| Review checklist | done / todo / na / stale; check verdict yes / partly / no / none |
| baselines | ahead / behind / mixed |
| ledger | stale / unknown / current |
| logged runs | failed / uncommitted / not in github / in github / unknown commit |
| triage | reviewed / needs_fixing / ignored / unreviewed |

This ADR fixes the words for the spine only: thesis, claim, link. The other vocabularies stay where they are, but the spine pages do not show them as statuses.

## Options

### A. Where the thesis lives
| Option | What it means | For | Against |
|---|---|---|---|
| A1 New `Thesis` object (own store) | A new `thesis.json` holds a sentence confirmed by the student | Clean name | A third thesis next to core message and hoped conclusion; more to confirm |
| **A2 Reuse `claims.core` (recommended)** | The core message *is* the thesis. Step 1 adds counts to it in the Experiments document. | No new store. Already drafted, rewordable, and the parent of every claim (`core.children`). | The UI label says "Core message" (decision D2) |
| A3 Use the Review "hoped conclusion" | The student's own best-case sentence | Written by the student | Written *before* the results, on purpose (pre-registration). It is not what the paper claims. |

### B. Where status lives
| Option | For | Against |
|---|---|---|
| B1 Per experiment (today) | Already built | Wrong when one experiment tests two claims. `track.py` allows `tests: [q1, q2]`. |
| **B2 Per link, with a criterion (recommended)** | Matches Discourse Graphs' "supports / opposes" links. Each claim reads its own experiments against its own test. | Needs a criterion field, so the map format grows by one optional field |

### C. Pages
| Option | Nav | For | Against |
|---|---|---|---|
| C1 Keep five tabs; make Experiments top-down | Claims · Experiments · Setup · Digest · Review | No approval needed for the nav | Claims and Experiments still show the same claims twice |
| **C2 Phase 1 = C1, then merge Claims + Experiments into "Thesis" (recommended)** | Home · Thesis · Setup · Review · Trail (§5) | Back to S18's four tabs. One place answers "how is the thesis backed". | Needs Juhyeong's approval (S18 pinned the nav). Old links must keep working. |
| C3 Research's proposal: one hierarchy, three lenses (Evidence, Experiments table, Setup); all else under "More" | Evidence · More | Fewest tabs | Moves Review and Digest under "More", which goes against S18. Makes Setup a lens, which goes against S23 ("a separate page just like claims"). The name "Evidence" already means one node's chain (`GET /api/evidence`, `pageEvidence`, tab key `node`). |

### D. VS Code
| Option | For | Against |
|---|---|---|
| D1 Webview only (today: one tab with the hub's pages, `tab.ts`) | Built | No native navigation; narrow sidebar mode had to be designed by hand (S18 Part 2) |
| **D2 Native tree "Thesis" + webview tab for detail (recommended)** | The Test Explorer and GitHub Pull Requests pattern, as the research reports it (unverified wording). Arrow keys, collapse, open-at-line for free. | One more tree provider in `extension.ts` |
| D3 D2 plus a third status bar item | Always visible | There are already two items, recheck (`extension.ts`) and runs (`runs.ts`) |

## Decision
Options **A2, B2, C2, D2**, and for the shell **S1** (§5.4).

### 1. Status words and rules (rules only, no model)
Every status carries `rule` (an id below) and `why` (one sentence with the numbers). The UI shows the word as the bracket tag from S18 (`[supports]`). Clicking or hovering shows the rule and the sentence.

**Link: one claim, one experiment** (new; computed in `track.py` / `experiments.py`)

| Status | Rule | When |
|---|---|---|
| running | L0 *(later, step 6)* | A logged run whose written files match the experiment's file patterns has no end time, and no result file is newer than its start |
| not run | L1 | The experiment has no result file (`files_n == 0` in map mode, `connected == false` in rule mode) |
| inconclusive | L2 | Result files exist, but there is no comparison: a search (`type == "tuning"`); "ours" not found; the comparator not found; or no value on the criterion's metric and datasets |
| supports | L3 | The criterion is met |
| contradicts | L4 | The criterion is not met |

Flags shown beside the word, never instead of it:
- `[recheck]`: the code or settings changed after the result (`x.stale`, from `process.ledger`).
- `!` to check: the paper table differs or is untraced, or bold is not best (`x.attention` minus stale).
- guess: "ours" or the metric was guessed (existing `caveats` with `k:"guess"`).
- one run: existing caveat `seeds`.
- criterion source: `default` / `drafted` / `confirmed`.

**Criterion** (one per link). Fields:

| Field | Values | Default |
|---|---|---|
| `compare` | `best_other` · `base` · a method name in the result files | `base` if the work extends a paper and the claim is the extension's own, else `best_other` (today's choice in `api._outcome`) |
| `metric` | a column of the experiment's files | the experiment's main column (`summary.metric`) |
| `over` | `main` (the main column only) · `all` · `majority` · `average` (datasets) | `main` |
| `strict` | `true`: ours must be better · `false`: at least as good | `false` (today a tie does not count against a claim, `stage_of`) |

"Better" uses the experiment's direction (`lower`) or its `target`, as `setup._better` already does. With the default criterion, L3 and L4 give exactly today's ahead-or-tie vs behind, so **step 1 changes no claim's stage**.

**Claim** (existing words, `claims.STAGES` and `STAGE_WORD`; rules restated from `claims.stage_of`):

| Rule | When | Stage |
|---|---|---|
| C1 | The researcher set the stage (`claims.json` `entries[id].stage`) | That stage, shown as "set by you" with the rule result beside it |
| C2 | Formal statement (theorem, lemma, ...) | Proof complete → Finding; partial → Being tested; none → Hypothesis (unchanged) |
| C3 | No linked experiment | Old evidence status: traced → Finding, linked → Being tested, nothing → Hypothesis (unchanged) |
| C4 | Linked experiments, all **not run** | Hypothesis ("planned") |
| C5 | Some run, none decisive (only inconclusive / not run) | Being tested |
| C6 | Every decisive link **contradicts** | Not supported |
| C7 | Some support, some contradict | Being tested (mixed) |
| C8 | Every decisive link **supports**, one or more with `!` | Being tested ("check first") |
| C9 | Every decisive link **supports**, nothing to check | Finding |
| — | Exploration | Only through C1 |

The claim's `recheck` flag stays as it is today: it is set if any linked result is stale. "Decisive" means supports or contradicts. Evidence bar for each claim: counts of supports / contradicts / inconclusive / not run (+ running).

**Thesis**: counts only, rule T1. It shows the number of claims per stage, the number of links per status, and the two buckets:
- experiments linked to no claim;
- claims with no experiment.

It shows **no single verdict word**. `core.stage` stays in the API for the tree colouring and `claims.md`, but the thesis header does not show it (decision D5).

### 2. What happens to each current page
| Page (tab key, function) | Phase 1 (steps 1-7, no nav change) | Phase 2 (step 8, needs approval) |
|---|---|---|
| Claims (`claims`, `pageClaims`) | Unchanged, except that the stage tooltip shows the rule id | Becomes the **Tree** lens of Thesis (S18 node graph, "Needs attention", add claim, Growth) |
| Experiments (`experiments`, `pageExperiments`) | **Top-down Outline**: thesis header with counts, the two buckets at the top, claim groups with stage, evidence bar and paper anchor, experiment rows with link status. Map view root = thesis (method name as subtitle). | Becomes the **Outline** lens of Thesis (default lens) |
| Experiment detail (row expand, `rxExpDetail`; `GET /api/experiment`) | Adds: criterion and its source, the rule that gave the status, Setup chips | Same |
| Setup (`setup`, `pageSetup`) | Unchanged | Stays a top-level tab |
| Review (`review`, `pageReview`) | Unchanged. Its "Supported today" uses the same stages | Stays a top-level tab |
| Digest (`digest`) | "Open tasks" becomes **Next to do** (step 4); the "History" section reads the Trail (step 5) | Becomes **Home** (thesis counts, next to do, recent trail, deadlines, this week's digest and Slack setting) |
| Timeline / Growth (`timeline`) | The tree scrubber stays; the "Steps" list moves into Trail (step 5) | Growth = the time slider of Thesis → Tree; a Trail entry sets its date |
| Notation (`notation`) | Unchanged (under Claims) | Footer "More" link |
| Graph (`graph`) | Unchanged | Footer "More" |
| Tasks (`tasks`) | Stays as the feedback inbox; its open tasks also appear in To-do (step 4) | Under Home |
| History (`history`) | Becomes the Trail list (step 5); the key `history` opens it | **Trail** tab (`history` key kept as an alias) |
| Ask (`ask`) | Unchanged (under Digest) | Under Home |
| Changes, Checks (`changes`, `checks`) | Unchanged (under Review) | Unchanged |
| Item / node pages (`item`, `node`) | Unchanged | Unchanged |

Old links keep working in phase 2. The tab keys `claims` and `experiments` and the VS Code `view=claims` / `view=experiments` (`core/embed.ts` `VIEWS`) open the matching lens of Thesis.

### 3. VS Code layout
- **Container `lemmata`** (activity bar) holds three views. That is within the research's "3-5 per container", which is still [NV].
  1. **Thesis** (new `lemmata.thesis`): root = the thesis sentence, with the description "4 claims · 2 findings". Below it:
     - **Claim**: icon by stage, description "2 of 3 support".
     - **Experiment** (the link): icon by link status, description "+0.81 vs DLinear · F1".
     - **Leaves**: Paper location, Result files, Scripts, Settings, Runs. Each opens in the editor at the line through the existing `lemmata.openItem`.
     - **Two bucket nodes at the top**, shown only when not empty.
     - Clicking a claim or experiment opens the webview tab at `view=experiments&sel=q:<id>` / `x:<id>` (the link format in `core/link.ts`).
  2. **Alarms and findings** (`lemmata.panel`, unchanged).
  3. **Runs** (`lemmata.runs`, unchanged).
- **Webview tab** (`tab.ts`) unchanged: one tab, the hub's pages, for the detail.
- **Status bar**: no third item. The existing item reads "Lemmata: 2/4 claims found · 3 to recheck". The tooltip adds the link counts.
- **Data**: the tree reads `GET /api/experiments`, which already has sections, experiments and claim stages. Leaves are fetched on expand from `GET /api/experiment?id=`, which already has `design`. **No new route.**

### 4. Every element mapped to the code
| Element | Engine (file → document field) | API route | Web page | VS Code | Missing today |
|---|---|---|---|---|---|
| Thesis | `claims.py` `draft`/`pick_core` → `claims.core`; `restage` (`_roll`) | `GET /api/claims` (`core`), `POST /api/claims` `{id:"core", text}` | `rxCoreCard` on Claims | — | `thesis` block in the Experiments document: core text, loc, stage counts, link counts, bucket counts |
| Claim | `claims.py` `build`/`restage`; map questions → claims in `api.confirm_map` | `GET /api/claims`; `GET /api/experiments` `sections[]` | `pageClaims`, `renderSec` in `pageExperiments` | — | `stage_rule` (C1-C9) beside `stage_why` |
| Link | map mode: `understand.verify` → `experiments[].tests`; rule mode: claim `support` (`claims.json` `links`) → `experiments.build` `exp_ids` | `GET /api/experiments` `sections[].experiments[]` | `rxExpRow` | — | **`link` object: `status`, `rule`, `why`, `criterion`, `criterion_by`** |
| Criterion | none | none | none | — | **New optional field in the map** (`experiments[].criteria{<question id>: {...}}`), checked in `understand.verify`. Researcher's override in `experiments.json` `entries[<exp id>].criteria`. Set through `POST /api/experiment` (new optional `claim` + `criterion`). |
| Experiment | `track.py` `experiment()` (map), `experiments.py` `experiment()` (rules) | `GET /api/experiments`, `GET /api/experiment?id=` | `rxExpRow`, `rxExpDetail`, `rxExpMap` | — | per-link status (above) |
| Setup item | `setup.py` `build` from each experiment's `grid` | `GET /api/setup`; MCP `setup` | `pageSetup` | `view=setup&sel=i:` | Chips on rows: the row needs `grid.datasets` + `grid.metric`, which exist |
| Result file | graph `result` nodes; `process.ledger` | `GET /api/ledger`; `x.design.files` (map mode) | `rxLedgerList`, detail | open at line | — |
| Run (repo record) | graph `run` nodes (`runs/<id>.json`), `claims._Ctx.chain` | `x.design.runs` | detail | open | — |
| Run (logged) | `runs.py` `runs.json`, `view` | `GET /api/runs`, `POST /api/runs`; MCP `runs`, `log_run` | — | Runs tree (`runs.ts`) | **Join to experiments by file pattern; `running` state** (step 6) |
| Paper location | `x.paper`, `x.loc`, `claim.loc` | in the documents above | `rxWhere` | open .tex at line | — |
| Buckets | map: section `other` + `counts.no_claim`, sections with `status:"unsupported"` + `counts.untested`; rules: `unassigned` | `GET /api/experiments` | bottom of `pageExperiments` | — | Placement at the top; `thesis.buckets` counts |
| Rule shown | `claims.stage_of` returns `(stage, why)` | — | `rxStageChip` title | — | rule ids; a rule list in `claims.md` |

### 5. Researcher side: to-do, trail, home, shell (S24-01b)
Juhyeong pointed at a lab research portal and named what he likes there: a to-do whose items link to their page, a calendar as the time axis, and one page per researcher that others can watch (chat 2026-11-16 11:01, quoted in [S24-01b](../sprints/S24/S24-01b-ibel-portal-reference.md)). What the portal shows is [P] at https://ibel-research-portal-demo.vercel.app; the comparison is in [benchmark-structures §3.1](../architecture/benchmark-structures.md). Lemmata takes the patterns only, not the portal's stages, gates, look or words.

#### 5.1 To-do that opens its own page
**Today.** Tasks exist only as feedback. `process.add_feedback` splits pasted feedback into tasks. `match_targets` attaches the paper items, files and claims each one names, and `also_check` lists what rests on them. They are stored in `tasks.json` (open / done / dropped) and shown on Tasks (`pageTasks`) and in Digest "Open tasks". Rule-made gaps exist too, but each is scattered on its own page: stale results (ledger), untested claims, Setup checks, paper ≠ files (`tally`), unconfirmed drafts, Review checklist items, alarms to look at.

**Decision.** A new engine module `engine/todo.py` builds one list on every read. It uses rules only and has no store of its own, except that feedback tasks keep their state in `tasks.json`. Each item has `kind`, `text`, `why` (the rule), `target` (what opens), and `waiting_on` (the ordering group).

| Order | Waiting on | Items (source in the code) | Opens |
|---|---|---|---|
| 1 | **A person**: feedback | Open feedback tasks (`tasks.json`, `source` such as "Advisor meeting") | The task's first target (claim, table, file at line); else Tasks |
| 2 | **Your confirmation** | Proposed map (`map.json` `proposed`); claim drafts (`state: proposed`); drafted criteria not confirmed (step 3); plan drafts (`plans.json` `state: draft`) | Map card; the claim; the experiment row; the plan |
| 3 | **The paper is wrong today** | Paper number differs from or is not found in the result files (`x.tally.differs` / `untraced`); bold not best; integrity findings `main_appendix_mismatch`, `undefined_ref`, `undefined_cite`, `reference_unmatched` | The paper line (`.tex` at line) |
| 4 | **Evidence is out of date** | Stale result (ledger `status: stale`); confounds check stale (Review checklist `stale`); alarms with items not looked at | The experiment row; Review claim row; Changes |
| 5 | **A gap** | Claim with no experiment (`counts.untested`); experiment with no claim (`no_claim`); baseline with no result on a dataset (Setup check); one run only (`seeds` caveat); link that **contradicts** | The claim; the experiment; the Setup item (`sel=i:`) |

Inside each group, items with a deadline come first (nearest first), then the newest. Rule items disappear when their rule no longer fires. They can be snoozed, which is the only new state (`todo.json`, `{item key: until}`), but never marked done by hand.

#### 5.2 Time axis: a Trail looking back, with deadlines ahead
**Today.** Dated records already exist:

| Record | Where | Has a time |
|---|---|---|
| commits (paper and code), runs from repo records, worktree | `events.json` (`api.events`) | yes |
| steps (commits grouped by day and theme, with a "decision" mark and the claims touched) | `process.timeline` → `GET /api/timeline` | yes |
| claim stage changes, with `by` (evidence / you / history) | `stages.json` (written in `api.claims`); replay from result history | yes |
| logged runs | `runs.json` | yes |
| feedback batches and task done times | `tasks.json` `batches[].created`, `tasks[].done_at` | yes |
| map proposed and confirmed | `map.json` `proposed_at`, `confirmed_at` | yes |
| checkpoints ("everything looked at") | `checkpoints.json` | yes |
| plans proposed | `plans.json` `at` | yes |
| confounds reports | `review.json` `confounds[].at` | yes |
| paper lines last written | git blame (`api._born`) | yes |
| claim confirmed or rejected | `claims.json` `entries` | **no** |
| deadlines | — | **does not exist** |

They are shown in four places: History (`pageHistory`: events by day), Timeline (`pageTimeline`: the Growth tree scrubber plus the Steps list), Digest (the History section by week) and Changes (since the checkpoint).

**Decision.** A new engine module `engine/trail.py` merges the dated records into one list of entries: `{t, kind, title, why, target, at}`. It is served at `GET /api/trail?from=&to=` and as an MCP read-only tool `trail`. The page is a list of day rows grouped by week, newest first, with a thin week strip at the top to jump by date. This is not a month grid: S18 says "band, heading, rows". Filters by kind (paper, code, runs, claims, feedback, decisions) reuse the History and Timeline chips.

Clicking an entry opens the object as it was at that time, where the data allows:

| Entry | Opens |
|---|---|
| Stage change | Thesis → Tree with Growth set to that date (`RX.t`) |
| Result or run | The experiment row with that version highlighted in its history (`x.history`) |
| Commit | Its subject and files, and GitHub at that commit. `api._github` knows the GitHub origin but builds links at HEAD only, so a per-commit link is new. |
| Feedback | The task |

**Deadlines** are the only new data. `deadlines.json` holds `{id, date, title, target?}` entered by the researcher (`POST /api/deadlines`). They show at the top of Trail ("ahead") and on Home, and give To-do its date order. Claim confirm and reject get a timestamp (`entries[id].at` in `claims.json`), so that they can appear on the Trail.

Trail **absorbs** History (the page and the `history` key) and the Timeline "Steps" list. Growth stays as the tree's time slider. Changes stays under Review, because it is "since you last looked" and not a time axis. ICS export is left out for now.

#### 5.3 Home for one research, and watching it
**Today.**
- One hub account has several projects. The projects list at `/` is the per-researcher index (ADR-006 Decision 3).
- ADR-006 makes someone else's project answer **404**. There is no viewer role.
- The only way to let others watch is the **exported HTML report** (`GET /api/export`). It opens in a read-only mode (`READONLY = !!SNAP` in `web/app.js`), which hides every write button.
- Constraint from the founder: "the student is the main user, the tree is the PI's view".

**Decision.**
- **Home** (phase 2; until then the same sections sit on Digest, steps 4-5) shows:
  - the thesis sentence and its counts (the T1 block from §1);
  - the top of To-do (five items, by group);
  - the last seven days of Trail;
  - the next deadlines;
  - this week's digest with its Slack setting (from `rxDigestBox`).
- **The projects list at `/`** gains each project's thesis counts and the number of open to-dos. That is the "page per researcher".
- **Watching**, in three levels:

| Level | What | Status |
|---|---|---|
| W1 | Exported snapshot, now including Home and Trail | Exists (`/api/export`); add the two pages |
| W2 | **Viewer by GitHub login**: the owner adds a login to one project, and that person sees it read-only (GET only, the `READONLY` UI). The PI opens Thesis → Tree by default. | **Missing:** a project ACL (`viewers` in the project record, `hub/projects.py`), owner checks in `hub/routes.py` that allow GET for viewers and refuse POST and MCP writes, a UI to add or remove viewers, and an audit line |
| W3 | Public link | Not proposed |

W2 needs Juhyeong's approval. It is sharing of user data (CLAUDE.md). It also falls under ADR-006's must-do: a GitHub App before people beyond invitees sign in (viewers are sign-ins).

#### 5.4 Shell
| Option | Website | VS Code | For | Against |
|---|---|---|---|---|
| **S1 Top band with few tabs (recommended)** | S18 band; phase 2 tabs Home · Thesis · Setup · Review · Trail | The native Thesis tree is the sidebar (§3); the tab stays compact (S18 Part 2) | Keeps the DAIS look Juhyeong chose (S18). Same tab count as today (five). VS Code already gives a sidebar. | The S18 four-tab rule is already broken since S23. Five stays above it. |
| S2 Left sidebar on the website (as in the portal) | A sidebar with all pages | Same as S1 | Room for many pages; one click to anything | Goes against the S18 "one column, no sidebar" rule. It duplicates the VS Code sidebar. The 800px column shrinks. |
| S3 Top band plus a left outline only on Thesis, wide screens | S1, plus a collapsible claim outline beside the Outline lens | Same as S1 | Quick jumps inside a long thesis | A new component; S18 asks to simplify first |

## Consequences
- **To-do, Trail and Home come before any nav change.** Their sections first appear on Digest (steps 4-5), so they can be judged before D6, D12 and D14.
- **Step 1 builds with no new store and no nav change** ([S24-02](../sprints/S24/S24-02-build-plan.md) step 1). The founder gets a top-down Experiments page without a decision on D6.
- With the default criterion, no stage changes. The rules become visible and numbered, so a wrong stage can be traced to a rule.
- The map format gains one optional field, the criterion. Readers ignore unknown fields (data-model §0), but `understand.verify` drops unknown experiment fields today, so verify must learn it. The format text that `project_brief` gives the agent must say how to draft it.
- The coding agent drafts criteria but cannot confirm them. ADR-007 rule 5 already covers this: no confirm tool.
- Two thesis-like texts remain: core message (the paper's) and hoped conclusion (the student's, on Review). This is intended. Decision D9 asks whether the header shows both.
- **Deadline cut.** CLAUDE.md lists the MVP as reference existence check, main-text ↔ appendix consistency and an HTML report. This spine work is research-side. If the 2nd presentation (MVP demo) is close, ship steps 1-2 only. Steps 5-9 are cut first, in reverse order.
- S18 to S23 are not QA-approved. This ADR builds on their code, so a QA finding there can change step 1.

## Needs Juhyeong
- **D1** Approve the spine with the core message as the thesis (A2).
- **D2** UI label: keep "Core message", or rename it "Thesis" (code id stays `core`).
- **D3** Link words: supports / contradicts / inconclusive / not run (+ running later).
- **D4** Default criterion: a tie counts as support (today), or strict.
- **D5** Thesis header: counts only, with no stage word for the core message.
- **D6** Phase 2 nav: Home · Thesis · Setup · Review · Trail (Claims and Experiments merged into Thesis; Digest becomes Home; History becomes Trail).
- **D7** VS Code: a native Thesis tree first in the container; the status bar text changes.
- **D8** Is step 1 part of the 2nd presentation demo, given the MVP scope in CLAUDE.md?
- **D9** Show the hoped conclusion beside the thesis in the header, or keep it on Review only.
- **D10** To-do: the five waiting groups and their order (§5.1); snooze as the only manual state for rule items.
- **D11** Trail: a day-row list with a week strip rather than a month grid; deadlines as the one new input; History and the Timeline step list absorbed (§5.2).
- **D12** Home: Digest becomes Home in phase 2 (§5.3).
- **D13** Watching: W1 now; W2 (viewer by GitHub login) only after approval and the GitHub App from ADR-006 (§5.3). Use of user data.
- **D14** Shell: S1 (top band; VS Code tree as the sidebar) vs S2 (left sidebar) vs S3 (§5.4).

## Approved by
Juhyeong, 2026-11-16 (chat, about 11:20 KST), answered as four packages:

| Package | Decisions | Answer |
|---|---|---|
| A. Evidence model | D1, D2, D3, D4, D5, D9 | Approved as proposed: the core message is the thesis and is labelled "Thesis"; link words supports / contradicts / inconclusive / not run; a tie counts as support unless a stricter criterion is confirmed; the thesis shows counts only; the hoped conclusion stays on Review |
| B. Build now | D8 | Build steps 1-5 now (top-down Experiments page, rules shown, criteria, To-do and Trail on Digest) |
| C. Reshape | D6, D7, D10, D11, D12, D14 | Approved now: nav Home · Thesis · Setup · Review · Trail; top band kept (S1), no left sidebar; native VS Code Thesis tree; To-do groups and Trail form as proposed; Digest becomes Home |
| D. Watching | D13 | Exported snapshot now (W1). The invite-only viewer (W2) only after the GitHub App from ADR-006 and a check of Korea University's rules |

Amended 2026-11-16 14:10 KST (chat: the day panel's command lines are "random words"; answers "rules plus agent-drafted summaries", "extend it to 1 hr", "keep them hidden by default", "sure"): the Trail's unit (D11) becomes the work session, not the single record. A session answers when, who, where, what, why, how and result by rules; its one-line summary may be drafted by the researcher's own agent and counts only once he confirms it (same rule as the project map, ADR-007). Setup sheets start with the same six questions. Detail: [S26-01](../sprints/S26/S26-01-handoff.md).

Amended 2026-11-16 12:03 KST (chat: "How about following the IPEL lab website?"; asked which parts, he chose "Shell and Home"): D14 becomes S2 on the website in wide windows: a slim top bar and one left sidebar for every page, and Home as a dashboard. DAIS colours and type stay. VS Code and narrow windows keep the band with tabs.

Amended 2026-11-16 11:34 KST (chat: "the history section and the graph section is at the bottom of the page, but I want it at the sidebar"): D14 changes from S1 to a mix. The five main tabs stay in the band; the secondary pages (History, Growth, Changes, Graph, Notation, Checks, Tasks, Ask, Search, Project menu) move from the footer to a left sidebar on the website. In the VS Code tab and in windows narrower than 1000 px they stay in the footer.

Amended 2026-11-16 11:21 KST (chat: "Go. add a whole month view at the bottom."): building starts; the Trail keeps its day rows and gains a whole-month grid at the bottom (D11).

Not decided: whether step 1 is shown in the 2nd presentation demo (its date is still unknown). The Trail was approved as a day-row list; Juhyeong had said he liked the portal's calendar, so show him the Trail early in step 5.
