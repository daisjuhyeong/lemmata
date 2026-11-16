---
type: task-card
owner_agent: lead
status: open
sources: ["founder chat 2026-11-16 10:43 and 10:54 KST", "Claude research report 'Lemmata UI Benchmark: Top-Down Thesis to Evidence Design and a VS Code Page Map' (2026-11-16)"]
last_reviewed: 2026-11-16
---
# Task S24-01: Turn the benchmark study into Lemmata's top-down structure (CTO)

- **Goal:** understand how the benchmark tools are built (front end and back end), and decide how Lemmata's pages and
  engine should be re-organized top-down so that one can check how the thesis is backed by the experiments done so far.
- **Asked by Juhyeong (chat):** "I want the page to be orchestrated Top-down style so that we can check how such thesis
  is backed up by the experiment done so far" (10:43) and "send it to the CTO agent who will understand the front-end
  and back-end structure of the benchmark like Reviewer3, Google's PAT/Deep Review, Refine, paperreview.ai, GPTZero and
  optimize it to Lemmata" (10:54). He also wants a flow chart of the Lemmata pages/format, viewable in VS Code, "so
  that we can discuss Lemmata without much misinterpretation".
- **Owner:** cto · **Reviewer:** qa (docs only; no code in this task) · **Decides:** Juhyeong.
- **Inputs:** the facts below; the code on this branch (`app/src/lemmata/engine/`, `web/`, `server.py`, `mcp.py`,
  `vscode/src/`); `wiki/architecture/`; ADR-007; `wiki/sprints/S23/S23-01-handoff.md`; `wiki/design/screens/S18-dais-ui.md`.

## Deliverables
1. `wiki/architecture/benchmark-structures.md`: for Reviewer3, Google PAT / Deep Review, Refine, paperreview.ai and
   GPTZero (plus q.e.d Science, scite, DVC's VS Code extension and the Test Explorer where useful): front end (page
   order, drill-down, status words, how evidence is anchored) and back end (pipeline stages, what is rule-based vs
   LLM, stores, APIs). One row each: what Lemmata takes, what it does not, and why. Keep the [P]/[3P]/[NV] marks.
   Do not present an [NV] or [3P] item as fact.
2. `wiki/decisions/ADR-008-top-down-evidence-spine.md` (status: proposed): the spine, the status vocabulary and
   rollup rules, what happens to the current pages (Claims, Experiments, Setup and the rest), and the VS Code layout.
   Give options and a recommendation. Map every element to the current code: which engine document, API route, web
   page and extension view it changes, and what data is missing today (e.g. a Thesis object, a criterion on each
   claim-experiment link).
3. `docs/map/README.md` plus five Mermaid files (`01-object-map.md` … `05-claim-status.md`) describing Lemmata
   **as it is on this branch** and, clearly separated, **as proposed**. They must render in the VS Code Markdown
   preview and on GitHub. Start with a glossary: one sentence per term and where it lives.
4. `wiki/sprints/S24/S24-02-build-plan.md`: ordered build steps, each with a "done when" test, sized so that the
   first step alone gives a usable top-down Experiments page.
5. A list of open research questions you could not settle from the facts below. You have no web access: do not
   guess. The lead will pass them to the analyst agent.

## Acceptance criteria
- Every factual statement about a benchmark tool carries a source URL from the list below (CLAUDE.md rule 1).
- Every proposed change names the file it touches. Nothing is built in this task.
- Status rules are rule-based (no LLM) and each status can show the rule that produced it.
- wiki/index.md and wiki/log.md updated.

## Facts from the research (2026-11-16)
Marks: [P] the product's own site, docs, paper or repo · [3P] third-party review · [NV] not verified.

### Paper checkers
| Product | Front end: structure and drill-down | Evidence anchoring · status words | Back end / mechanism | Source |
|---|---|---|---|---|
| Reviewer3 | Five named checks: Submission Screening (editors), Reference Check, Fatal Flaws, Claim Review, Code Replication [P]. One report ordered by severity [3P, from a competitor]. Check → comment | API returns comments with severity tags and text anchors [P]. Exact labels [NV] | Specialized reviewer agents in parallel, each with tools for citation, statistics and claim-evidence checks [P]. Reference check against five scholarly databases [P]. Code Replication runs the code and compares its output with the paper [P]. Web app, JSON API, MCP [P] | https://reviewer3.com/ · https://reviewer3.com/api-access · https://manusights.com/blog/is-reviewer3-worth-it |
| Google PAT → Deep Review | STOC version: summary of contributions → potential mistakes (often per lemma/theorem) → minor corrections [P]. Deep Review: Overall Feedback → Detailed Feedback, filter by major / minor / suggestion [3P] | Comments point to sections or pages [3P] · major / minor / suggestion [3P] | Splits the document into sections, reviews them in parallel, merges, then a cross-section consistency check with search grounding [3P]. "Copy Report" gives Markdown [3P]. Public since 2026-10-14 | https://research.google/blog/gemini-provides-automated-feedback-for-theoretical-computer-scientists-at-stoc-2026/ · https://www.scriptbyai.com/deep-review-google/ |
| Refine.ink | Overall Feedback, then comments in a panel beside the document (Refine Editor) [P/3P] | Each comment anchored in the text; concerns with no anchor are dropped [P]. Labels [NV] | Parallel compute per paper, about 30 min [P]. Recomputes values from the paper's own formulas [P] | https://www.refine.ink/faq · https://www.refine.ink/blog/refine-5 |
| paperreview.ai | One templated review, optional 1-10 score; no drill-down [P] | Grounded in related arXiv papers [P] | PDF → Markdown → search queries → retrieve and summarize arXiv papers → templated review; first 15 pages [P] | https://paperreview.ai/tech-overview |
| GPTZero Hallucination Check | Table, one row per citation: # / citation / verdict / justification / potential match [P] | Link to the matched source per row [P] · exist / exist with minor issues / fake / unsure / unknown [P] | Matches citation metadata against retrieved sources [P] | https://gptzero.me/news/how-does-gptzeros-hallucination-check-detector-work-a-technical-report/ |
| scite | Counts (supporting / contrasting / mentioning) → list of citation statements, filterable [P] | The citing sentence shown beside each label [P] | Classifier over citation statements [P] | https://scite.ai/blog/how-do-i-use-the-scite-report-page |
| q.e.d Science | Claim tree → gaps per claim → suggested edits [P interview / 3P]. The only checker organized by claim | Tied to the paper's experiments and cited literature. Labels and UI [NV] | Not documented [NV] | https://www.the-scientist.com/q-e-d-an-ai-tool-for-smarter-manuscript-review-73759 |

Open-source, same delivery model as Lemmata: citation-check (labels SUPPORTED / PARTLY SUPPORTED / NOT SUPPORTED /
UNVERIFIABLE, each with quote and page; summary separates "changed" from "flagged";
https://github.com/vmbennett/citation-check) and Bib Check Agent (a model-free Python checker first, needing two
databases to agree, then an agent only on flagged entries, then a reviewer that tries to refute each fix;
https://github.com/nnicholas-c/bib-check-agent).

### Experiment trackers, structures, VS Code
- W&B: project → runs table → run page; Reports; artifact lineage graph that clusters 5+ nodes; a pinned baseline
  run [P]. https://docs.wandb.ai/models/artifacts/explore-and-traverse-an-artifact-graph
- MLflow: experiment → runs table with expandable parent/child runs [P].
  https://mlflow.org/docs/latest/ml/traditional-ml/tutorials/hyperparameter-tuning/notebooks/parent-child-runs/
- DVC VS Code extension: activity-bar view with panels; experiments table and plots open as editor tabs; up to 7
  experiments compared [P]. https://github.com/treeverse/vscode-dvc
- None of the trackers has an object for "the conclusion these runs support".
- VS Code Test Explorer: tree of items with `uri` and `range`; pass/fail per leaf rolled up to "x / y passed" [P].
- VS Code UX guidelines (as reported by the research; re-check against the official pages before relying on the
  wording): tree views for data, webviews only when necessary, 3-5 views per container at most; GitHub Pull
  Requests = tree for the list, webview for the detail.
- Goal Structuring Notation: goal → strategy → sub-goals → solution (evidence); goals without evidence are marked
  "undeveloped" [P]. https://arxiv.org/pdf/2403.15236
- Discourse Graphs: question ← claim ← evidence, with "supports" / "opposes" [P].
  https://research.protocol.ai/blog/2023/discourse-graphs-and-the-future-of-science/index.html
- ORKG: contribution = research problem + method + results; comparison table [P]. https://arxiv.org/pdf/2210.02034
- Mermaid: renders on GitHub in Markdown [P]
  (https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams).
  The research reports built-in Mermaid preview in VS Code 1.121 (2026-05-20); older versions and forks need the
  "Markdown Preview Mermaid Support" extension. Verify on Juhyeong's VS Code.

### Patterns the smooth tools share
Verdict first, then drill down · a fixed vocabulary of 3-5 statuses · every finding anchored to a location · status
rolled up from leaf to root · an explicit "missing evidence" state · results always shown against a baseline · one
primary object per view · tree or list to navigate, rich view for detail · graph as a secondary lens ·
deterministic core with the LLM only drafting.

### What the research proposed for Lemmata (proposals to weigh, not decisions)
- **Spine:** Thesis → Claims → Experiments → Setup (dataset · baselines · metric) → Runs / code → Paper location.
  Today the thesis is not an object, Experiments starts from the method, and Claims / Experiments / Setup are peers.
- **Experiments page:** thesis header with counts; claims as group headers (status, evidence bar, paper anchor);
  experiments as rows ("ours vs best baseline, difference, dataset, metric", criterion met, seeds, last run); setup
  as chips; runs, code and paper location on the experiment's detail page. Two buckets always visible: experiments
  linked to no claim, and claims with no experiment.
- **Status:** a criterion on each claim-experiment link (drafted by the LLM pass, confirmed by the student).
  Experiment: supports / contradicts / inconclusive / running / not run. Claim: backed / partly backed / contradicted
  / untested. Thesis: counts only. "Criterion not set" and "stale" (code changed after the run) are visible states.
- **Navigation:** one hierarchy with three lenses (Evidence, Experiments table, Setup); the other pages under "More".
- **VS Code:** native tree Claim → Experiment → Run with status icons; one webview tab for detail; a status bar
  item; tree items open files at the line.
- **Page map:** Mermaid in `docs/map/`: object map, page hierarchy, website ↔ VS Code navigation, data flow,
  claim-status states.

### Not verified, do not rely on
Neptune, Comet, Aim, ClearML, TensorBoard HParams, Elicit, Consensus, SciSpace, Kialo, Argdown, Connected Papers,
Litmaps, Heptabase, NotebookLM, Manusights, PeerReviewAI, thesify, Paperpal Preflight, alphaXiv, YesNoError; the
exact severity labels of Reviewer3 and Refine; q.e.d's actual UI.

### Constraints that already hold
- Juhyeong's decisions: the claim is the root of why an experiment is run; "Lemmata drafts, I confirm"; LLM pass
  first, rule-based tracking after (ADR-007); the student is the main user, the tree is the PI's view; the UI follows
  the DAIS site (S18 spec), with a compact design for VS Code; S18 pinned four top-level tabs and S23 added a fifth
  (Setup), so changing the nav needs his approval.
- S18 to S23 are stacked and not QA-approved.

## Handoff note
(cto, 2026-11-16; covers S24-01 and the addendum S24-01b. Design only: no file under `app/` or `vscode/` changed. Nothing committed.)

- **What changed.** These are new files. Each lists the code it was read against.
  - `wiki/architecture/benchmark-structures.md`: front end and back end per tool, with marks and URLs kept; the IBEL portal row and the boundary paragraph (§3.1); one row per tool on what Lemmata takes, what it does not, and why.
  - `wiki/decisions/ADR-008-top-down-evidence-spine.md` (proposed): the spine; status per link; rules L0-L4, C1-C9, T1; criterion; the page fate table; VS Code layout; element → code map; §5 To-do, Trail, Home and watching, Shell; decisions D1-D14.
  - `docs/map/README.md` (glossary) and `01-object-map.md` … `05-claim-status.md`: Today and Proposed diagrams, 14 in all, every one rendered with mermaid-cli 11.16.0 with no syntax error. They were not opened in the VS Code preview or on GitHub.
  - `wiki/sprints/S24/S24-02-build-plan.md`: 9 steps, each with "done when". Step 1 alone gives a top-down Experiments page.
  - `wiki/index.md`, `wiki/log.md`, `wiki/architecture/README.md`, `wiki/decisions/README.md`: entries.
- **Corrections to the research's premises** (from the code): the thesis object exists (`claims.core`, "Core message"). The Experiments Table view (the default) is already grouped by claim; only the Map view starts from "Ours". Status is per experiment, with no criterion. Both buckets exist but sit at the bottom. Logged runs are not joined to experiments.
- **Open questions** (for the analyst unless marked):
  1. VS Code Test Explorer: an official URL for `TestItem` (`uri`, `range`) and for how pass / fail / skipped / errored roll up. Needed to cite it and to model "inconclusive".
  2. VS Code UX guidelines: the official wording on tree views vs webviews and on the number of views per container.
  3. Which VS Code version first has a built-in Mermaid Markdown preview (the research says 1.121, 2026-05-20), and which version Juhyeong runs (lead to ask him).
  4. Reviewer3 and Refine: their exact severity or label words.
  5. Google Deep Review: the source and mark for "public since 2026-10-14".
  6. q.e.d Science: what its claim tree and per-claim gaps actually look like (labels, levels, how a gap is tied to an experiment).
  7. citation-check: whether SUPPORTED / PARTLY SUPPORTED is decided by rules or by a model, and from what. This bears on the criterion design.
  8. Bib Check Agent: which two databases must agree, and how the refute step reports.
  9. W&B: how a pinned baseline is shown in the runs table (a difference column? a colour?). This bears on the "ours vs comparator" row.
  10. GSN: states other than "undeveloped" that the cited paper defines, as candidates for evidence states.
  11. IBEL portal (unread screens): the Status board, the progress-history table and the professor's view. How does a PI see one researcher? Are to-do items made by rules or entered by hand? How is the "writing history" filled?
  12. (lead) The date of the 2nd presentation, to place the cut line in S24-02.
  13. (lead / compliance) Korea University rules on letting others view a student's research data on the hub (ADR-006 "Before you invite people" item 5). This applies to the read-only viewer.
- **Links:** [benchmark-structures](../../architecture/benchmark-structures.md) · [ADR-008](../../decisions/ADR-008-top-down-evidence-spine.md) · [docs/map](../../../docs/map/README.md) · [S24-02 build plan](S24-02-build-plan.md) · addendum [S24-01b](S24-01b-ibel-portal-reference.md)
