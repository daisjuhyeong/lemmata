---
type: handoff
owner_agent: lead
status: needs-qa
sources: ["founder chat 2026-11-17 11:08-12:25 KST", "../../design/screens/S27-hypothesis-first.md", "https://github.com/daisjuhyeong/temporal_dependency/tree/short-exp (commit a0c6b2e)"]
last_reviewed: 2026-11-17
---
# S27-01: Hypothesis-first mode

Asked by Juhyeong (chat, 2026-11-17): Lemmata's thesis for `temporal_dependency` was not organised around the hypothesis he
already had. He wants the AI first to understand what problem the research is trying to solve and the researcher to say
whether it is valid; if not, to delete or fix it, or combine it with others; and any new input to be comprehended by the
AI and applied to Lemmata. The CTO agent could not be started from the chat, so this was built from the chat session
("just you do the work and update", 12:25 KST). Spec: [S27 hypothesis-first](../../design/screens/S27-hypothesis-first.md).

Branch `s27-hypothesis-first`, cut from `s24-topdown-evidence` (the latest work, S24-S26). Nothing is merged to main.

## What changed
- **Engine: `engine/hypo.py` (new).** Detects the protocol, report, notes, deviation log, datasets manifest and test
  tables in the research repo. Keeps `hypothesis.json`: the problem, hypotheses, experiments, jobs, change sets, inputs
  and a log. No model, no network.
- **Jobs for the researcher's own LLM.** Six job types: state the problem, draft hypotheses, revise after a fix,
  combine, comprehend an input, check a premise. Every answer is checked against the files before it is stored: quotes
  must be in the file (the line is corrected to where the quote really is), rule files must exist, a rule must select
  exactly one row. What fails is dropped and reported.
- **The problem is the gate.** The first job states the problem (gap, why it matters, approach, if it works) with
  quotes. The Thesis page asks "Is this the problem you are solving?". Hypotheses are drafted only after Confirm.
- **Confirm · Fix · Delete · Combine · Tell.** Confirm needs no model. Fix applies the edit at once and asks the LLM what
  else must change. Delete archives (restorable). Combine asks the LLM for one merged hypothesis that keeps each
  original test as a sub-condition; the originals are archived with `merged_into` and their ids become aliases. Tell
  saves the text as an input; the LLM restates what it understood and proposes a change set, each operation quoting the
  input. Every LLM proposal is a before/after list; the researcher accepts all, some, or rejects. Problem: Confirm, Fix,
  Not valid, Delete (only together with a new input).
- **Stage by rule from the project's own test table (no model).** R0 set by you · R1 test met → Finding · R2 test not
  met → Not supported · R3 tested, no verdict (secondary, or test not frozen) · R4 not run / no rule · R5 exploratory.
  Only a confirmatory hypothesis with a frozen design file can become a Finding. A combined hypothesis needs every
  sub-condition.
- **One claim store.** A confirmed hypothesis becomes a claim (label = its id); its stage, rule and reason come from the
  rule above, so the Thesis counts, Claims tree and MCP `claims` agree. An archived hypothesis is a rejected claim.
- **Deviations.** The project's own log is parsed by `## Dn.` heading, with date. A deviation affects a hypothesis it
  names (H1, H2 …) or one that names it (e.g. "D11" in an exploratory hypothesis's test). Timing per hypothesis: before
  or after the first commit of that hypothesis's result files. Lemmata adds its own deviation (L1, L2 …) when a fix,
  merge or proposal touches a frozen hypothesis; changing a frozen test makes it exploratory.
- **Protocol never edited.** A change the protocol does not say yields a proposal file (`/api/hypothesis/proposal.md`)
  for the researcher's `notes/`, following the repo's own rule.
- **Tracked branch (hub).** `GET /api/hub/projects/<pid>/branch` lists branches and the ones newer than the tracked one;
  `POST` fetches and checks out another branch, then rescans. The Thesis page shows "Tracking main · short-exp has newer
  commits [Track it]".
- **API:** `GET /api/hypothesis`, `/api/hypothesis/job?id=`, `/api/hypothesis/job.md?id=`, `/api/hypothesis/proposal.md?id=`;
  `POST /api/hypothesis` (action), `/api/hypothesis/submit`, `/api/hypothesis/change`.
- **MCP:** `hypotheses`, `hypothesis_job`, `submit_hypothesis_job`. In Claude Code: "do Lemmata's jobs for this project".
- **Web:** the Thesis page opens with the hypothesis-first section when the project is in that mode: Tell box, jobs
  waiting (Copy job, .md, Paste answer), proposed changes, Problem, hypotheses grouped by tier, archived, experiments,
  deviations, open questions. The paper-based thesis follows under "From the result files" when result files exist.

## Mode
Hypothesis-first is on by default for a project with no paper that has a protocol or a findings report. Either way the
researcher can switch it (`POST /api/hypothesis {action:"enable", target:"on"|"off"}`; no button yet).

## Field mapping onto the existing model
| Spec | Code |
|---|---|
| Problem | `hypothesis.json` `problem` (not `claims.core`: core is drafted from an abstract, and this project has none) |
| Claim `stage` (S17 words) | `claims.STAGES`: hypothesis, testing (Being tested), finding, refuted (Not supported), exploration |
| Claim | a manual claim (`claims.add_manual`, kind contribution, label = hypothesis id); `api._hf_stages` sets stage, `stage_by: rule`, `stage_rule` R0-R5 |
| Archived | claim state `rejected` |
| ADR-008 link statuses | not used: these hypotheses are judged by the project's own test table, not ours-vs-best per experiment |
| Job file mirror in the repo (`.lemmata/jobs/`) | replaced by MCP plus a downloadable job `.md` and "Paste answer": the hub's clone is read-only and the researcher's LLM runs elsewhere |

## Done-when results (test project `temporal_dependency`, branch `short-exp`, a0c6b2e)
Run locally on a copy of the repo; the jobs were answered by me in the role of the researcher's LLM.

| Step | Result |
|---|---|
| 1 Mode, branch, sources | Pass. Sources: `protocol/short-experiment.md` (+ v0.2 protocol), `FINDINGS.md`, 5 notes, `notes/2026-11-12-deviations.md`, `data/manifest.csv`, `results/analysis/tests.csv`. Branch switch and "newer" warning tested in `test_hub` with the fake GitHub; **not yet run on the Mac mini hub**. |
| 2 Job queue | Pass via API and MCP tools; job `.md` download and paste-back in the web. File mirror in the repo: not built (see mapping). |
| 3 Problem | Pass. Draft states the Parrino gap, the question, the shuffled-copy method; "If it works" left empty because the sources do not say it. A bad quote is refused. |
| 4 Hypotheses | Pass. H1-H3 confirmatory, H2b secondary, the anomaly-structure result exploratory, Parrino's claim as `tested`; Step A → H1, A+C → H2, D → H3. A hypothesis with an invented quote is dropped; a rule matching no row is dropped. |
| 5 Review actions | Pass. (a) rewording H3 makes a change set and deviation L1, tier stays confirmatory; (b) H2b delete/restore; (c) H2+H3 → H23 keeps both tests, aliases H2, H3. |
| 6 Tell | Pass. "I now think the anomalies…" → restated understanding, an exploratory H4 quoting the input, a proposal file; reject leaves everything unchanged. |
| 7 Rule stage | Pass with no model: H1 Finding (δ 0.584, CI 0.244-0.872, Holm p 0.00024); H2, H3 Not supported (Holm p 0.243); H2b Being tested, no verdict. Changing one number flips the stage (`test_hypo`). |
| 8 Deviations | Partly. D1-D16 parsed with dates; D11 after data for H1-H3 and linked to the exploratory result; D15 after data. **D16 is linked to nothing** until a hypothesis names it (the per-source verdict is not drafted as a hypothesis). Source-change diffing (stale by changed section) **not built**. |
| 9 Views | Website: pass (screenshots). VS Code native Thesis tree with the four actions: **not built**; the VS Code tab shows the same web page. |
| 10 Premise check | Job and storage built; the URL quote check is **not built** (stored as `unverified`). |
| 11 Provenance, 12 report-vs-table numbers, 13 novelty watch and published baselines | **Not built.** |

## Tests
- `app/tests/test_hypo.py` (10 tests, a synthetic repo with a frozen protocol, a deviation log and a test table).
- `test_hub.HubTest.test_tracked_branch_newer_and_switch`.
- Full suite: 193 tests OK (2 skipped), including the S18 colour-token check.

## Screenshots
- [Thesis page, problem waiting for review](screenshots/s27-problem-review.png)
- [Thesis page, proposed change, problem, hypotheses with H1 open](screenshots/s27-thesis-hypotheses.png)

## For QA
- On the Mac mini: `git fetch origin && git checkout s27-hypothesis-first`, restart the hub, open `temporal_dependency`,
  switch it to `short-exp` from the Thesis page, then in Claude Code ask it to do Lemmata's jobs.
- Check the hub fetch with `--depth 1000` on a branch with long history, and that `sync` fast-forwards after a switch.
- Check the S18 contrast of the `[tag]` text in the new rows.

## Needs Juhyeong's decision
- Merge to main.
- Whether to build Steps 9 (VS Code tree actions), 10-13 next, and whether the per-source verdict (D16) should be its own
  exploratory hypothesis.
