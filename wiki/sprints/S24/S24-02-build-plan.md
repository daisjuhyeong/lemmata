---
type: build-plan
owner_agent: cto
status: approved
sources:
  - "../../decisions/ADR-008-top-down-evidence-spine.md (proposed; this plan builds it)"
  - "S24-01-cto-benchmark-to-lemmata.md ; S24-01b-ibel-portal-reference.md (founder chat 2026-11-16 10:43, 10:54, 11:01 KST)"
  - "code on branch s24-topdown-evidence, read 2026-11-16 (files named per step)"
last_reviewed: 2026-11-16
---
# S24-02 Build plan: the top-down evidence spine

**Approved by Juhyeong 2026-11-16 (see ADR-008, Approved by): build steps 1-5 now; steps 6-8 are approved to follow; step 9 waits for the GitHub App and the university-rules check.** Originally: nothing here starts before Juhyeong approves ADR-008, or at least the decisions a step names. Each step is one task card, one handoff note and a QA pass (CLAUDE.md rule 6). Steps 1-7 change no nav. Steps 8-9 need explicit approval.

**Cut line for the 2nd presentation (MVP demo).** Ship steps 1-2. If time is short, ship step 1 alone: it is usable by itself. Cut steps 9 → 5 first, in reverse order. The date of the 2nd presentation is not in the facts I had (see the S24-01 handoff, Open questions).

| # | Step | Needs decision | Size |
|---|---|---|---|
| 1 | Top-down Experiments page (default criterion) | D1, D3, D5 | M |
| 2 | Rules shown on every status | — | S |
| 3 | Criterion on each link (drafted, confirmed) | D4 | M |
| 4 | To-do from rules, on Digest | D10 | M |
| 5 | Trail and deadlines, replacing History | D11 | M |
| 6 | Logged runs joined to experiments; "running" | — | S |
| 7 | VS Code Thesis tree | D7 | M |
| 8 | Nav and shell, phase 2: Home · Thesis · Setup · Review · Trail | D6, D12, D14 | M |
| 9 | Read-only viewer by GitHub login | D13 + ADR-006 GitHub App | L |

---

## Step 1: top-down Experiments page
**Goal:** open Experiments and read, from the top down, how the thesis is backed, with no new store and no nav change.

**Files**
- `app/src/lemmata/engine/api.py`: in `experiments()`, add `E["thesis"]`. It holds the core text, `loc`, claim counts per stage, link counts per status, and bucket counts. It reads `self.claims()["core"]` and `counts.stages`.
- `app/src/lemmata/engine/track.py` and `engine/experiments.py`: on each experiment inside a section, add `link = {status, rule, why, criterion, criterion_by: "default"}`. The status is computed from `review._state` with the comparator rule of `api._outcome`:
  - ahead or tie → supports (L3);
  - behind → contradicts (L4);
  - none → inconclusive (L2);
  - no result file → not run (L1).
- `app/src/lemmata/web/research.js`, `pageExperiments` (Table view):
  - a thesis header with counts and an evidence bar;
  - the two buckets moved to the top and always shown, with 0 when empty;
  - each claim header gets its stage chip, an evidence bar and a paper anchor (`rxWhere(loc)`);
  - `rxExpRow` shows the link word as the bracket tag (`[supports]`), with the `why` in its title.
- `rxExpMap`: the root shows the thesis, with the method name as a subtitle.
- `app/src/lemmata/web/app.css`: bracket tags and the bar, tokens only (S18).

**Done when**
- `test_map` (new cases): on the synthetic map fixture, every experiment in a section has a `link.status` among the four words. The stage of every claim is **the same as before the change** (snapshot of `claims()` stages before and after). The thesis counts add up to the number of live claims and links.
- One experiment that tests two claims shows a link on each.
- A claim with no experiment is counted in `thesis.buckets.untested`. An experiment with no claim is counted in `thesis.buckets.no_claim`.
- Browser on the `test_map` fixture: the header, buckets and groups appear in that order at 1280 px and at 640 px, with no console errors. A screenshot goes into the handoff.
- `test_s18_ui` still passes: there are still five tabs.

## Step 2: rules shown on every status
**Files**
- `engine/claims.py`: `stage_of` returns `(stage, why, rule)` with `rule` in C2-C9; `restage` stores `stage_rule`. C1 is set where the researcher's stage wins. `to_markdown` lists each rule.
- `engine/track.py`, `engine/experiments.py`: rule ids L1-L4 (already in the step 1 `link`).
- `web/research.js`: `rxStageChip` and the link tag show "rule C7: …" on hover or expand.
- MCP `claims` and `experiments` tools (`mcp.py`) carry the rule ids.

**Done when**
- One unit test per rule C2-C9 and L1-L4, each built from a minimal claim, with the expected stage and rule id.
- `claims.md` names the rule for every claim.

## Step 3: criterion on each link
**Files**
- `engine/understand.py`:
  - map format text in `brief` (the block shown to the agent): optional `experiments[].criteria{<question id>: {compare, metric, over, strict}}`;
  - `verify` checks it: the metric is a real column, the comparator is a method in the files or `best_other` / `base`, and the question id is one the experiment `tests`. Whatever fails is dropped and reported.
- `engine/experiments.py` (`load`, `decide`): `entries[<exp id>].criteria[<claim id>]` holds the researcher's override.
- `engine/api.py` `set_experiment`, and `server.py` `POST /api/experiment`: new optional `claim` and `criterion`.
- `engine/track.py`, `engine/experiments.py`: evaluate the criterion with `over` = main / all / majority / average, using `setup._better` for direction and target. `criterion_by` = default / drafted / confirmed / you.
- `web/research.js` `rxExpDetail`: show the criterion and edit it in place.

**Done when**
- A drafted criterion with an unknown column is dropped by `verify` with a note.
- A confirmed map with `strict: true` turns a tie into contradicts for that link only. The same experiment's link to another claim keeps its own criterion.
- With no criteria at all, the stages equal the step 1 snapshot.
- The agent cannot confirm a criterion: MCP has no tool for it (test in `test_map.py` `test_mcp_tools`).

## Step 4: To-do from rules, on Digest
**Files**
- New `engine/todo.py`. It builds items from the Experiments document, claims, `process.ledger`, `review.build`, `setup.build` checks, findings, the alarms "to look at" count, `map.json`, `plans.json` and `tasks.json`. Items are grouped by `waiting_on` (person, confirmation, paper, stale, gap; ADR-008 §5.1) and each carries a `target` (`q:`, `x:`, `i:`, a node id, or `{repo, path, line}`).
- `engine/api.py`: `todo()`.
- `server.py`: `GET /api/todo`; `POST /api/todo {key, snooze_until}` → `.lemmata/todo.json`.
- `mcp.py`: read-only tool `todo`.
- `web/research.js` `pageDigest`: "Open tasks" becomes "Next to do". Each row is bracket tag, sentence, and target; clicking it opens the target through `openTab` and the selection.

**Done when**
- Fixture tests: one item of each kind appears when its rule fires and disappears when it no longer fires (for example, refreshing a stale result removes the stale item). Groups come out in order, and a snoozed item is hidden until its date.
- Every item has a target that opens a page, checked by a browser test that clicks the first item of each kind.
- Tasks still works as the feedback inbox.

## Step 5: Trail and deadlines
**Files**
- New `engine/trail.py`. It merges `events`, `process.timeline` steps, `stages.json`, `runs.json`, `tasks.json` (batches, done_at), `map.json` (proposed_at, confirmed_at), `checkpoints.json`, `plans.json` (at), `review.json` confounds (at) and new `deadlines.json`. Each entry is `{t, kind, title, why, target, at}`.
- `engine/claims.py` `decide`: record `at` on state changes.
- `engine/api.py`: `trail(start, end)`, `set_deadline`.
- `server.py`: `GET /api/trail?from=&to=`, `POST /api/deadlines`.
- `mcp.py`: read-only `trail`.
- `web/app.js` `pageHistory`: becomes the Trail. It shows day rows by week, a week strip, filter chips (paper, code, runs, claims, feedback, decisions) and "Ahead" deadlines at the top.
- `web/research.js`: the Digest "History" section reads it, and `pageTimeline` drops its Steps list and links to Trail.
- Entry clicks:
  - stage change → Claims tree with `RX.t` set;
  - result → experiment row with that version marked;
  - commit → GitHub at that commit (new link built from `api._github`'s origin).

**Done when**
- Fixture: every record kind in the table of ADR-008 §5.2 appears once, in time order. A deadline shows in "Ahead" and orders the To-do.
- Clicking a stage-change entry opens the tree recoloured to that date (browser test).
- Old `openTab('history')` and VS Code `view=history` links still open the page. Note: `history` is not in `VIEWS` today. Step 5 adds `trail` and keeps `history` working on the website.

## Step 6: logged runs joined to experiments
**Files**
- `engine/api.py` `_exp`: pass `runsmod.load(self.hub)` to `trackmod.build`.
- `engine/track.py`: match each logged run's `artifacts[].path` against the experiment's patterns (`und.compile_pattern`), and add `x.logged_runs`. Set L0 running when a matching run has no `ended`, and no matching result file is newer than its start.
- `web/research.js` `rxExpDetail`: a "Logged runs" list.

**Done when**
- Fixture: a manifest with no `ended` on a matching path shows "running". The same manifest with `ended` shows the earlier rule's status. A non-matching manifest is ignored.

## Step 7: VS Code Thesis tree
**Files**
- `vscode/package.json`: view `lemmata.thesis` "Thesis", first in container `lemmata`.
- `vscode/src/extension.ts`: a tree provider over `GET /api/experiments`, with leaves fetched lazily from `GET /api/experiment?id=`. Leaves open through `lemmata.openItem`. Claim and experiment nodes open the tab (`tab.ts` `open(..., 'experiments', 'q:'|'x:')`). The status bar text becomes "Lemmata: n/m claims found · k to recheck".
- `vscode/src/core/`: a pure model builder plus a unit test, following `model.ts`.

**Done when**
- A unit test of the model builder covers thesis, claims, links, leaves, icons by status and the empty-bucket nodes.
- Host test: clicking a result-file leaf opens it at the line.
- The container has three views.

## Step 8: nav and shell, phase 2 (only after D6, D12, D14)
**Files**
- `web/app.js`: `NAV` becomes Home · Thesis · Setup · Review · Trail, with `NAV_OF` updated. The keys `claims`, `experiments`, `digest`, `history` and `timeline` become aliases.
- `web/research.js`: `pageThesis` has two lenses (Outline = step 1 page, Tree = `pageClaims` tree). `pageHome` holds thesis counts, top five to-dos, the last seven days of the trail, deadlines, `rxDigestBox`, and links to Tasks and Ask.
- `vscode/src/core/embed.ts` `VIEWS`: add `home`, `thesis`, `trail`; keep the old keys. `core/link.ts` accepts them.
- `hub` projects list: each row shows its thesis counts and open to-dos.
- `test_s18_ui`: pins the new nav.

**Done when**
- Every old link (website `openTab` keys, `vscode://…&view=claims|experiments|digest`) lands on the matching lens or page.
- The S18 VS Code checks pass at 300 px (no sideways scroll).
- Juhyeong signs off on screenshots.

## Step 9: read-only viewer (only after D13 and the GitHub App from ADR-006)
**Files**
- `hub/projects.py`: `viewers: [login]` per project.
- `hub/routes.py`: viewers get GET routes only. POST routes and MCP writes return 403, and an unknown project still returns 404.
- `web/app.js`: viewers get the `READONLY` mode; the PI lands on Thesis → Tree.
- An audit line per viewer visit in `hub.log`.
- The export (`/api/export`) includes Home and Trail.

**Done when**
- `test_hub` and `test_public`: a viewer can read every GET route of that project and nothing of others. Every POST and every MCP write is refused. Removing a viewer cuts access on the next request.
- The threat model is updated by the CTO before the build.
