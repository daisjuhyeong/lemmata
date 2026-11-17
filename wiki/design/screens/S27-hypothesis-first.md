---
type: design-spec
owner_agent: lead
status: approved
sources: ["founder chat 2026-11-17 11:08-12:25 KST (hypothesis-first; validate the problem; delete, fix or combine; new input comprehended and applied; 'just you do the work and update')", "https://github.com/daisjuhyeong/temporal_dependency/tree/short-exp (protocol/short-experiment.md, FINDINGS.md, notes/2026-11-12-deviations.md, results/analysis/tests.csv, commit a0c6b2e)"]
last_reviewed: 2026-11-17
---
# S27: Hypothesis-first mode (spec, revision 3)

Built in [S27-01](../../sprints/S27/S27-01-handoff.md); what was built and what was not is listed there.

# Lemmata: Hypothesis-First Mode Build Instructions
*2026-11-17, revision 3. Hand this to the CTO agent. Build the steps in order; each has a "done when" test. Do not start a step until the previous one passes.*

*Test project: `daisjuhyeong/temporal_dependency`, branch **`short-exp`**, commit `a0c6b2e` or later. Not `main`.*

## What changed in revision 3
Revisions 1 and 2 were written from the `main` branch, which stops at the protocol draft of 2026-11-12. The research is on `short-exp`: a pre-registered design with hypotheses H1–H3, completed runs, and a findings report. Revision 3 corrects the spec to that state:

- **Tracked branch** is now a project setting (Step 1). Reading the default branch is the likely reason the Thesis page missed the hypotheses.
- **Hypothesis-first applies at any stage**, including a project that already has results.
- **The rule reads the project's own test table**; Lemmata does not recompute statistics (Step 7).
- **Evidence tier** (confirmatory, secondary, exploratory) and the **deviation log** are first-class (Steps 4 and 8).
- States use the stage names already in the code (S17): a hypothesis that fails its test is "not supported", not "refuted".
- All "done when" tests now use H1–H3 and the committed results.

## Why this exists
Lemmata builds the Thesis from paper LaTeX and run manifests. `temporal_dependency` has no paper. Its question, hypotheses, tests and results are in markdown and CSV files on a non-default branch, so the Thesis page has nothing to organise around.

Hypothesis-first mode makes the **protocol, the findings report and the researcher's own words** the source until a paper exists:

- The AI first states what problem the research is trying to solve. The researcher says whether that is right.
- The hypotheses come next. Every experiment exists because a hypothesis needs it.
- A hypothesis records what would count as support before the data arrive, and Lemmata shows whether that was respected.
- The researcher can correct the AI at any time in plain language; the AI works out what that changes and proposes it.
- The user's own LLM does all of this. Lemmata never calls a model.

## Principles
1. **Understand, then confirm, then rules.** The LLM drafts its understanding; the researcher validates it; later tracking is LLM-free (the existing two-phase design).
2. **Personal LLM only.** Lemmata posts jobs. The user's agent (Claude Code, or any agent that can read a file) does them on the user's plan, with its own web search.
3. **The agent proposes, the human decides.** Nothing the LLM returns changes the project until the researcher accepts it.
4. **Every retrieved fact carries its source**: URL or file path, exact quote, date. Lemmata checks the quote without an LLM.
5. **Nothing is lost.** Delete and Combine archive; they never erase. Every decision shows on the Trail.
6. **Extend, do not duplicate.** Map everything below onto the existing claim model, the S17 stages and the ADR-008 link statuses. Do not create a second claim store.

## Architecture

```
protocol/*.md ──────┐
FINDINGS.md ────────┤
notes/*.md ─────────┤
data/manifest ──────┼─> job (.lemmata/jobs/*.md) ──> user's own LLM ──> result
researcher input ───┘                                                      │
(.lemmata/inputs/*.md)                                  engine validates ──┘
                                                               │
                                              change set shown as before / after
                                                               │
                                     researcher: Confirm · Fix · Delete · Combine
                                                               │
results/analysis/tests.csv ──(rule, no LLM)──> stage ──> Thesis · Setup · To-do · Trail
```

## Data contracts

### Config additions (`.lemmata/config.yml`)
```yaml
mode: hypothesis_first            # default when `paper` is missing
branch: short-exp                 # tracked branch; see Step 1
hypothesis_source: ["protocol/*.md"]
report: ["FINDINGS.md"]           # the researcher's own write-up, if any
notes: ["notes/*.md"]
deviations: ["notes/*deviations*.md"]
datasets_manifest: "data/manifest.csv"
```

### Problem (one per project, the root of the Thesis page)
```yaml
problem:
  gap: "What is wrong or unknown today."
  why_it_matters: "Who relies on it, and what goes wrong because of it."
  approach: "What this research does about it."
  if_solved: "What changes if the research succeeds."
  origin: [{file: "FINDINGS.md", lines: "33-36", git_sha: "a0c6b2e"}]
  validity: unreviewed            # unreviewed | valid | not_valid
  confirmed: false
```

### Claim (added fields)
```yaml
id: H2
statement: "Across datasets, the TSAD-over-streaming advantage in AUC-PR grows with temporal dependence."
answers: "Which part of the problem this hypothesis addresses, in one sentence."
stance: held                      # held = the author's own hypothesis | tested = someone else's claim under test
tier: confirmatory                # confirmatory | secondary | exploratory
source: null                      # required when stance = tested: {cite, url, quote, locator, quote_check}
criterion:
  text: "Spearman rho between D1 and Delta, one-sided permutation test over source families, Holm over H1-H3"
  rule: null                      # machine-checkable form, see Step 7
  frozen: {file: "protocol/short-experiment.md", git_sha: "..."}   # the commit where it was fixed
tested_by: [stepA, stepC]
origin: {file: "protocol/short-experiment.md", lines: "18", git_sha: "a0c6b2e"}
stage: hypothesis                 # use the existing S17 stages: hypothesis | being tested | finding | not supported | exploration
result: null                      # filled by the rule: {estimate, interval, p, source_file, run}
validity: unreviewed              # unreviewed | valid | not_valid
confirmed: false
archived: null                    # {reason: deleted | merged, merged_into: H4, at: ...}
aliases: []                       # ids of claims merged into this one
```
Tier rules: only a `confirmatory` claim with a frozen criterion can become a `finding`. A `secondary` claim shows its numbers without a verdict. An `exploratory` result stays at stage `exploration` until a new frozen test exists for it.

### Planned or completed experiment
```yaml
id: stepC
title: "18 detectors x 61 datasets x 3 seeds"
deliverables: ["results/C/parts/", "results/C_cells.csv"]
acceptance: "gate or acceptance text from the protocol"
depends_on: [stepA]
tests_claims: [H2]
status: done                      # planned | running | done | failed | blocked
```
Status comes from the deliverable files and, when present, the project's own progress file. Run manifests attach to the experiment whose deliverable paths they write.

### Deviation (from the project's deviation log)
```yaml
id: D11
title: "Exploratory checks on the Step A reading; anomaly structure; INSECTS"
date: 2026-11-16
origin: {file: "notes/2026-11-12-deviations.md", lines: "289-352", git_sha: "a0c6b2e"}
affects: [H1]
timing: after_data                # before_data | after_data, relative to the first result file of the affected claim
```

### Researcher input
Free text the researcher gives Lemmata, saved as `.lemmata/inputs/<date>-<n>.md` and committed like any other file. It is a source in its own right: items drafted from it carry it as `origin`.

### Change set (what every LLM proposal looks like)
```yaml
change_set:
  trigger: {kind: fix | combine | delete | input | source_changed, ref: "..."}
  understood: "One line restating what the LLM understood."
  operations:
    - op: revise                  # add | revise | merge | archive | relink
      target: H2                  # problem | claim id | experiment id
      before: "..."
      after: "..."
      reason: "One sentence."
      from: {file: ".lemmata/inputs/2026-11-17-1.md", quote: "..."}
  not_in_protocol: []             # operations that the protocol does not say
```
Engine checks, without an LLM: every `target` exists; every `from.quote` is a substring of its file; an operation that changes a frozen criterion is marked as a deviation (Step 8).

### Job
```yaml
id: 2026-11-17_understand_a1
type: understand_problem
trigger: "project created"
inputs: [{file: "FINDINGS.md", git_sha: "a0c6b2e"}]
instructions: "..."               # plain language, self-contained
output_schema: {...}              # JSON schema of the result
status: open                      # open | submitted | accepted | rejected
```
Each job is also written as `.lemmata/jobs/<id>.md` (instructions, inputs and schema in one file), with the result expected at `.lemmata/jobs/<id>.result.json`. This is the agent-agnostic path: any LLM that can read and write a file can do the job.

Job types: `understand_problem`, `draft_hypotheses`, `revise`, `combine`, `comprehend_input`, `premise_check`, `provenance`, `evidence_from_notes`, `novelty_watch`, `published_baselines`.

---

## Part A: Understanding and structure

### Step 1. Mode, tracked branch and source detection
- `Lemmata: Init` and web project creation set `mode: hypothesis_first` when no paper path is given.
- **Tracked branch.** List the repository's branches with their last commit date. Preselect the most recently pushed one and let the researcher change it. On Home, warn when another branch is newer than the tracked one ("`short-exp` is 5 days ahead of `main`").
- Detect protocol, report, notes, a deviation log and a datasets manifest on the tracked branch.
- Creating the project must not require access to the Mac mini.

**Done when:** adding `temporal_dependency` preselects `short-exp`, lists `protocol/short-experiment.md`, `FINDINGS.md`, the notes, `notes/2026-11-12-deviations.md` and `data/manifest.csv` as sources, and switching to `main` shows the "newer branch" warning.

### Step 2. Job queue for the personal LLM
- Engine stores jobs; MCP tools `list_jobs`, `get_job(id)`, `submit_job_result(id, result)`.
- Mirror each job to `.lemmata/jobs/` as described above; the file watcher picks up `*.result.json`.
- Add a Claude Code command `/lemmata-jobs`: list open jobs, do each, submit. VS Code status bar: `Lemmata: 2 jobs waiting`.
- The engine validates every result against `output_schema` and rejects with a readable reason.

**Done when:** a test job is completed twice, once through MCP from Claude Code and once by editing the result file by hand, and both are accepted.

### Step 3. The AI states the problem; the researcher validates it
Job `understand_problem`, created when the project is added. The agent reads the hypothesis sources, the report, the notes and the README and returns the Problem record. Each field cites `origin` lines. The instructions tell the agent to write what the sources say, in plain words, and to leave a field empty with a note when the sources do not say it.

- Engine check: every `origin` line range exists at that commit.
- The researcher sees the four fields on one screen with the question **"Is this the problem you are solving?"** and the actions of Step 5.
- The problem is the gate. Hypotheses are drafted (Step 4) only after the problem is marked `valid`.

**Done when:** on `short-exp` the draft says, in substance: Parrino et al. attribute the gap between time-series and streaming anomaly detectors to "temporal characteristics" that they neither define nor measure; the research asks first whether temporal dependence exists in the benchmark datasets and whether time-series and streaming benchmarks differ in it, then whether it matters for detectors; it measures dependence against a row-shuffled copy of each series under a pre-registered design.

### Step 4. Draft the hypotheses under the confirmed problem
Job `draft_hypotheses`, created when the problem becomes `valid`. The agent returns hypotheses (each with `answers`, `stance`, `tier`, criterion text and where it was frozen), experiments with their status, and open questions. Each item carries `origin`.

- Works the same whether or not results exist. The agent does **not** report results; Step 7 reads them from files.
- Tier comes from the sources: what the protocol lists as primary is `confirmatory`, what it lists as secondary is `secondary`, and anything the report or the deviation log marks as decided after seeing data is `exploratory`.
- Everything lands as `[confirm]` with `validity: unreviewed`.
- If a hypothesis has no results yet and its criterion has no stated direction, the review screen asks for the researcher's prediction. A saved prediction is never overwritten; changes are appended with a date.

**Done when:** on `short-exp` the draft contains H1, H2 and H3 as `held`, `confirmatory`, with the §7 test of the protocol as criterion; H2b and the other §2 secondary items as `secondary`; the anomaly-structure and INSECTS results and the per-source verdict as `exploratory`; Steps A to D with their deliverables; and the links Step A → H1, Steps A and C → H2, Step D → H3.

### Step 5. Review actions: Confirm, Fix, Delete, Combine
The same four actions on the problem and on every claim. "Combine" needs two or more claims selected. Available on the website and in the VS Code Thesis tree (context menu).

| Action | What the researcher does | What happens |
|---|---|---|
| **Confirm** | One click, or "confirm all" | `validity: valid`, `confirmed: true`. No LLM. |
| **Fix** | Edits the text directly, or writes what is wrong in plain words ("this is not my point; the point is…") | A direct edit applies at once. Either way a `revise` job asks the LLM what else must change (criterion, `answers`, experiment links, other claims). The result is a change set. |
| **Delete** | One click plus an optional reason | The item is archived, not erased. Experiments that tested only this claim go to To-do as "no claim". Restorable from the Trail. No LLM. |
| **Combine** | Selects claims, optionally says how they relate | A `combine` job drafts one merged claim: statement, a criterion that keeps each original condition as a sub-condition, the union of `tested_by` and evidence. Originals are archived with `merged_into`; their ids become `aliases` so existing run links still resolve. |

Rules:
- Every LLM result is shown as a **before / after** list, one row per operation with its reason. The researcher accepts all, accepts some, or rejects. Nothing applies before that.
- Marking the problem `not_valid` and fixing it sets every claim under it to `[stale]` and creates one `revise` job for the whole tree.
- Deleting the problem is allowed only together with a new input (Step 6); a project cannot have an empty root.
- Fix or Combine on a claim whose criterion is frozen does not alter the frozen criterion. The merged or revised claim becomes `exploratory` unless every original was confirmatory and its test is unchanged, and the change is recorded as a deviation (Step 8).
- While a job is waiting for the LLM, the affected items show `[confirm]` and "waiting for your LLM"; the rest of the page stays usable.

**Done when:** on `short-exp`, (a) rewording H3 by hand produces a change set and marks the change as a deviation; (b) deleting H2b archives it and restore brings it back; (c) combining H2 and H3 into one "dependence matters for detectors" claim keeps both tests as sub-conditions, and results linked to H2 still resolve.

### Step 6. New input: the researcher tells Lemmata, the AI applies it
An input box on the Thesis page ("Tell Lemmata", one text field, no form) and a VS Code command `Lemmata: Tell`. This is how a hypothesis that exists only in the researcher's head gets in.

- The text is saved to `.lemmata/inputs/`.
- A `comprehend_input` job gives the LLM the input and the current structure. It returns a change set: what to add, revise, merge or archive, each operation quoting the sentence of the input it comes from, with the one-line `understood` shown above the details.
- A new hypothesis from input starts at stage `hypothesis` with no criterion. If results that bear on it already exist, it is `exploratory`, and Lemmata says so on the review screen.
- If an operation says something the protocol does not, it is listed under `not_in_protocol`. On acceptance, Lemmata writes a proposal to `notes/<date>-lemmata-proposal.md` in the research repo for the researcher to commit. It never edits a protocol file (the repo's own rule).
- If the input contradicts a confirmed item, the change set shows the conflict and offers: replace, keep both, or combine.

**Done when:** typing "I now think the anomalies, not the normal data, decide whether order matters" yields a restated understanding, a change set that adds an `exploratory` hypothesis linked to the problem and to the existing anomaly-structure result, and a proposal file in `notes/`; rejecting the change set leaves the project untouched.

### Step 7. Criteria and LLM-free stage
Lemmata reads the test table the project already produces. It does not recompute statistics.

```yaml
rule:
  file: "results/analysis/tests.csv"
  select: {test: "H2 (D1 vs Delta)"}
  conditions:
    - {column: p_holm_primary, op: "<", value: 0.05}
    - {column: estimate, op: ">", value: 0}
  report: [estimate, ci_lo, ci_hi, p_holm_primary]
```
- The `draft_hypotheses` job proposes the rule from the protocol's test section and the table's header; the researcher confirms it with the hypothesis.
- When the file appears or changes, the engine sets the stage: all conditions met → `finding`; otherwise → `not supported`; file missing → `hypothesis` or `being tested`. Follow ADR-008 for ties. A combined claim needs every sub-condition.
- `result` stores the reported columns, the file and its commit.
- No rule means the claim keeps its stage with the tag "no rule yet". The researcher may set the stage by hand with a note; that is shown as manual.
- If a project has no test table, the rule may point at any CSV or JSON value with the same `select` and `conditions` form.

**Done when:** on `short-exp`, with no LLM call, H1 shows `finding` (Cliff's δ 0.58, interval 0.24 to 0.87, Holm p 0.0002), and H2 and H3 show `not supported` (Holm p 0.24 each); changing one number in a copy of the file flips the stage.

### Step 8. Frozen design, deviations and source changes
- **Frozen.** A hypothesis source can be marked frozen (detected from its own text, confirmed by the researcher). The commit where each criterion first appeared is its `frozen` reference.
- **Deviations.** Parse the deviation log into Deviation records by heading. An `evidence_from_notes`-style job links each to the claims it affects; `timing` is computed from commit dates against the first result file of each affected claim, without an LLM.
- Each claim row shows its deviation count, split before and after data. Clicking lists them with dates and reasons.
- **Source changes.** On a change to a hypothesis source or the report, diff by section. Items whose `origin` lines changed become `[stale]`, with one `revise` job scoped to those sections. A change to a frozen file itself is shown as an error-level warning on Home.
- Unaffected items keep their confirmation.

**Done when:** on `short-exp`, D1 to D16 appear as Trail entries with their dates; D11 and D16 are marked "after data" and linked to the exploratory results; and replaying the last commit (`a0c6b2e`, which refocused `FINDINGS.md`) marks only the problem and the affected sections stale.

### Step 9. Views
Follow the DAIS style spec and the ADR-008 shell. Few words; details on click.

- **Thesis page**, top-down: problem (four short lines) → hypotheses grouped by tier (confirmatory first, exploratory last and visually lighter) → criterion and result → experiments. Each row shows stage, the result numbers, "tested by" and the deviation count. The "Tell Lemmata" box sits at the top.
- **Review screen**: the before / after list of Step 5, one primary action ("Accept").
- **Stage tags**: use the existing S17 tags. `not supported` is a neutral result, not an error: do not use the error colour.
- **Experiments** appear in the table as rows with status, before any run exists.
- **To-do / Home**: open questions, items waiting for confirmation, jobs waiting, experiments with "no claim", the newer-branch warning.
- **Trail**: every Confirm, Fix, Delete, Combine, input and deviation, with what the LLM had proposed.
- **VS Code Thesis tree**: same hierarchy, stage as the icon, the four actions in the context menu.

**Done when:** from the Thesis page alone, a reader can say what problem the project solves, that H1 held and H2 and H3 did not, which results are exploratory, and which steps produced each.

---

## Part B: Retrieval jobs
All use Step 2. The agent uses its own web search. Each result item must include `url` (or file), `quote`, `locator`, `retrieved_at`.

**Quote check (engine, no LLM).** Fetch the URL, normalise whitespace and case, and look for the quote as a substring. Set `quote_check` to `verified` or `not_found`. If the page cannot be fetched or parsed (PDF behind a login), set `unverified`; do not reject. Only `verified` items can be confirmed with one click; others need the researcher to open the source.

### Step 10. Premise check
One job for the problem's `gap` and one per `tested` claim: find where the cited source says it, and report whether the source states it as a finding, an assumption or a hypothesis.

**Done when:** the statement that Parrino et al. attribute the detector gap to temporal characteristics shows a source quote with a `verified` check, or an explicit "source does not say this".

### Step 11. Dataset provenance
One job per manifest row. If `order_provenance` is empty, draft it from the paper or repository (collection order, sorted, concatenated by class or concept, shuffled, synthetic). If it is filled, check it against the source and report agreement or conflict. Confirmed changes are proposed to the manifest; the researcher commits.

The Setup page shows the datasets as a table with provenance, its source and the check result.

**Done when:** the ARCUS datasets each show a provenance with a source quote, and a deliberately wrong cell in a copy of the manifest is reported as a conflict.

### Step 12. Evidence from notes and the report
Job on each new or changed notes or report file: extract statements with numbers that bear on a claim, as evidence records with file and lines. The quote check runs against the file at that commit. Evidence never changes a stage; only the rule does. Where the report gives a number that also sits in a results file, the engine compares the two and flags a mismatch.

**Done when:** every number in the `FINDINGS.md` summary that the engine can match to `results/analysis/tests.csv` is marked consistent, and editing one in a copy raises a mismatch on that line.

### Step 13. Novelty watch and published baselines
- `novelty_watch`: weekly, one job per project. Input: the confirmed problem and hypotheses. Output: papers that already answer this question or overlap, each with one sentence on the overlap. New items since last week go to the digest. Respect the user's venue preference when ranking (top venues first).
- `published_baselines`: one job per model–dataset pair with published numbers: metric, value, table locator. Shown beside the researcher's own result in the Review's side-by-side comparison, with the protocol difference stated when the metrics are not comparable.

**Done when:** a weekly job runs on schedule without anyone opening the Mac mini, and the ARCUS, METER and MemStream paper numbers appear beside the Step C results (the reproduction check the project's progress file lists as pending).

---

## Cost control
- Jobs are created only by these events: project created, problem confirmed, Fix, Combine, new input, source changed, deviation log changed, manifest row added, notes or report changed, weekly timer.
- Confirm, Delete and every stage computation never create a job.
- No job is created per commit or per run.
- Jobs are batched: `/lemmata-jobs` shows the count and types before starting.

## Not in this build
- Linking claims to paper sections once LaTeX exists (the claim keeps its id, so this can be added later).
- Launching experiments from a planned experiment.
- Tracking more than one branch per project at a time.
- Any server-side model call.
- Sharing beyond the existing exported snapshot.

## Notes for the building agent
- Read the current claim schema, the S17 stages and ADR-008 first, then report the field mapping before writing code.
- Check which branch Lemmata tracks for `temporal_dependency` today and report it; this spec assumes it is `main`.
- MCP and Claude Code command and hook formats change often. Check current docs; do not code from memory.
- Never write to the research repo without a visible proposal the researcher accepts (Steps 6 and 11).
- Report after each step with the "done when" result, in the Slack reporting structure already in use.
