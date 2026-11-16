---
type: architecture
owner_agent: cto
status: proposed
sources:
  - "../sprints/S24/S24-01-cto-benchmark-to-lemmata.md (facts table of the research report 'Lemmata UI Benchmark: Top-Down Thesis to Evidence Design and a VS Code Page Map', 2026-11-16, with its [P]/[3P]/[NV] marks and URLs)"
  - "https://reviewer3.com/ ; https://reviewer3.com/api-access ; https://manusights.com/blog/is-reviewer3-worth-it"
  - "https://research.google/blog/gemini-provides-automated-feedback-for-theoretical-computer-scientists-at-stoc-2026/ ; https://www.scriptbyai.com/deep-review-google/"
  - "https://www.refine.ink/faq ; https://www.refine.ink/blog/refine-5"
  - "https://paperreview.ai/tech-overview"
  - "https://gptzero.me/news/how-does-gptzeros-hallucination-check-detector-work-a-technical-report/"
  - "https://scite.ai/blog/how-do-i-use-the-scite-report-page"
  - "https://www.the-scientist.com/q-e-d-an-ai-tool-for-smarter-manuscript-review-73759"
  - "https://github.com/vmbennett/citation-check ; https://github.com/nnicholas-c/bib-check-agent"
  - "https://docs.wandb.ai/models/artifacts/explore-and-traverse-an-artifact-graph ; https://mlflow.org/docs/latest/ml/traditional-ml/tutorials/hyperparameter-tuning/notebooks/parent-child-runs/ ; https://github.com/treeverse/vscode-dvc"
  - "https://arxiv.org/pdf/2403.15236 (GSN) ; https://research.protocol.ai/blog/2023/discourse-graphs-and-the-future-of-science/index.html ; https://arxiv.org/pdf/2210.02034 (ORKG)"
  - "https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams"
  - "https://ibel-research-portal-demo.vercel.app (IBEL lab research portal demo, observed by the lead as the sample researcher, 2026-11-16; ../sprints/S24/S24-01b-ibel-portal-reference.md; founder chat 2026-11-16 11:01 KST)"
  - "Lemmata code on branch s24-topdown-evidence, read 2026-11-16 (for the 'Lemmata today' column): app/src/lemmata/engine/{claims,experiments,track,review,setup,understand,runs}.py, web/research.js, vscode/package.json"
last_reviewed: 2026-11-16
---
# How the benchmark tools are built, and what Lemmata takes from each

**Purpose.** This page sets out the front end and back end of the tools the research compared, so that [ADR-008](../decisions/ADR-008-top-down-evidence-spine.md) can borrow on purpose. Every product statement repeats the mark and the URL from the S24-01 task card. The CTO did not re-check any of it (no web access in this task).

Marks: **[P]** the product's own site, docs, paper or repo · **[3P]** third-party review · **[NV]** not verified. An item with no mark in the research is labelled *"(no mark)"* and treated as unverified.

## 1. Verdict first
- **What we take.** Lemmata takes a structure from the tools, not a feature. Show the verdict first, then let the reader drill down. Use a few fixed status words. Anchor every finding to a place. Roll status up from the leaves. Show "missing evidence" as a state. Compare results with a baseline. Navigate with a tree and read the detail in a rich view. Keep the core rule-based.
- **What the tools lack.** Only q.e.d is organised by claim, and its UI is [NV]. No experiment tracker has an object for "the conclusion these runs support". The research found that gap (task card, "Experiment trackers"). It is the gap Lemmata fills.
- **What we leave out.** Lemmata does not take LLM-written review prose, scores, or the running of the author's code.

## 2. Paper checkers

### 2.1 Front end
| Product | Page order and drill-down | Status words | How evidence is anchored | Source |
|---|---|---|---|---|
| Reviewer3 | Five named checks: Submission Screening (for editors), Reference Check, Fatal Flaws, Claim Review, Code Replication [P]. A competitor's review says it is one report ordered by severity [3P]. Drill-down: check → comment. | Exact labels [NV] | The API returns comments with severity tags and text anchors [P] | https://reviewer3.com/ · https://reviewer3.com/api-access · https://manusights.com/blog/is-reviewer3-worth-it |
| Google PAT (STOC) → Deep Review | STOC version: summary of contributions → potential mistakes (often per lemma or theorem) → minor corrections [P]. Deep Review: Overall Feedback → Detailed Feedback, filtered by major / minor / suggestion [3P]. | major / minor / suggestion [3P] | Comments point to sections or pages [3P] | https://research.google/blog/gemini-provides-automated-feedback-for-theoretical-computer-scientists-at-stoc-2026/ · https://www.scriptbyai.com/deep-review-google/ |
| Refine.ink | Overall Feedback, then comments in a panel beside the document (Refine Editor) [P/3P] | Labels [NV] | Each comment is anchored in the text; a concern with no anchor is dropped [P] | https://www.refine.ink/faq · https://www.refine.ink/blog/refine-5 |
| paperreview.ai | One templated review, with an optional 1-10 score. No drill-down [P]. | Score only [P] | Grounded in related arXiv papers [P] | https://paperreview.ai/tech-overview |
| GPTZero Hallucination Check | A table with one row per citation: # / citation / verdict / justification / potential match [P] | exist / exist with minor issues / fake / unsure / unknown [P] | Each row links to the matched source [P] | https://gptzero.me/news/how-does-gptzeros-hallucination-check-detector-work-a-technical-report/ |
| scite | Counts (supporting / contrasting / mentioning) → a filterable list of citation statements [P] | supporting / contrasting / mentioning [P] | The citing sentence is shown beside each label [P] | https://scite.ai/blog/how-do-i-use-the-scite-report-page |
| q.e.d Science | Claim tree → gaps per claim → suggested edits [P interview / 3P] | Labels and UI [NV] | Tied to the paper's experiments and cited literature [P interview / 3P]; the details are [NV] | https://www.the-scientist.com/q-e-d-an-ai-tool-for-smarter-manuscript-review-73759 |
| citation-check (open source) | A summary that separates "changed" from "flagged" | SUPPORTED / PARTLY SUPPORTED / NOT SUPPORTED / UNVERIFIABLE | A quote and page number with each label | https://github.com/vmbennett/citation-check (no mark; it is a repo, so read as [P]) |

### 2.2 Back end
| Product | Pipeline stages | Rule-based vs LLM | Stores, APIs | Source |
|---|---|---|---|---|
| Reviewer3 | Specialised reviewer agents run in parallel. Each has tools for citation, statistics and claim-evidence checks [P]. The reference check queries five scholarly databases [P]. Code Replication runs the code and compares its output with the paper [P]. | LLM agents with tools [P]. The split between rules and the model inside each tool is [NV]. | Web app, JSON API, MCP [P] | https://reviewer3.com/ · https://reviewer3.com/api-access |
| Google Deep Review | Splits the document into sections and reviews them in parallel. Then merges them and runs a cross-section consistency check with search grounding [3P]. | LLM (Gemini) [P for the STOC version; 3P for Deep Review] | "Copy Report" gives Markdown [3P]. Public since 2026-10-14 (no mark). | https://research.google/blog/gemini-provides-automated-feedback-for-theoretical-computer-scientists-at-stoc-2026/ · https://www.scriptbyai.com/deep-review-google/ |
| Refine.ink | Parallel compute per paper, about 30 minutes [P]. Recomputes values from the paper's own formulas [P]. | LLM. Whether the recomputation is symbolic or done by the model is [NV]. | Not described in the facts | https://www.refine.ink/faq · https://www.refine.ink/blog/refine-5 |
| paperreview.ai | PDF → Markdown → search queries → retrieve and summarise arXiv papers → templated review. Reads the first 15 pages [P]. | LLM with retrieval [P] | Not described | https://paperreview.ai/tech-overview |
| GPTZero | Matches citation metadata against retrieved sources [P] | Matching. The role of a model is not stated in the facts. | Not described | https://gptzero.me/news/how-does-gptzeros-hallucination-check-detector-work-a-technical-report/ |
| scite | A classifier over citation statements [P] | Trained classifier [P] | Not described | https://scite.ai/blog/how-do-i-use-the-scite-report-page |
| q.e.d Science | Not documented [NV] | [NV] | [NV] | https://www.the-scientist.com/q-e-d-an-ai-tool-for-smarter-manuscript-review-73759 |
| Bib Check Agent (open source) | A model-free Python checker runs first and needs two databases to agree. An agent then works only on the flagged entries. A reviewer agent then tries to refute each fix. | Rules first, LLM only on what the rules flag | Repo | https://github.com/nnicholas-c/bib-check-agent (no mark; a repo, read as [P]) |

## 3. Trackers, structures and VS Code
| Tool | Structure | Source |
|---|---|---|
| W&B | Project → runs table → run page. Reports. An artifact lineage graph that clusters groups of 5 or more nodes. A pinned baseline run [P]. | https://docs.wandb.ai/models/artifacts/explore-and-traverse-an-artifact-graph |
| MLflow | Experiment → runs table with expandable parent/child runs [P] | https://mlflow.org/docs/latest/ml/traditional-ml/tutorials/hyperparameter-tuning/notebooks/parent-child-runs/ |
| DVC VS Code extension | An activity-bar view with panels. The experiments table and plots open as editor tabs. Up to 7 experiments compared [P]. | https://github.com/treeverse/vscode-dvc |
| VS Code Test Explorer | A tree of items, each with a `uri` and a `range`. Pass/fail per leaf, rolled up to "x / y passed" [P]. | **No URL in the task card.** Not relied on until a source is added (see Open questions). |
| VS Code UX guidelines | As the research reports them: tree views for data, webviews only when needed, at most 3-5 views per container. GitHub Pull Requests uses a tree for the list and a webview for the detail. | **No URL; the research itself says to re-check the wording.** Treated as [NV]. |
| Goal Structuring Notation | goal → strategy → sub-goals → solution (evidence). A goal with no evidence is marked "undeveloped" [P]. | https://arxiv.org/pdf/2403.15236 |
| Discourse Graphs | question ← claim ← evidence, with "supports" / "opposes" [P] | https://research.protocol.ai/blog/2023/discourse-graphs-and-the-future-of-science/index.html |
| ORKG | contribution = research problem + method + results; a comparison table [P] | https://arxiv.org/pdf/2210.02034 |
| Mermaid | Renders on GitHub in Markdown [P]. The research reports built-in preview in VS Code 1.121 (2026-05-20); older versions and forks need the "Markdown Preview Mermaid Support" extension (no URL; [NV]). | https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams |

### 3.1 Lab research portal (IBEL demo), added by S24-01b
The lead observed this as the sample researcher. Every item is [P] at https://ibel-research-portal-demo.vercel.app (read 2026-11-16; S24-01b card). The lead did not read the Status board, Trend radar, Literature, Knowledge base, Topic finding, the gate page, the progress-history table, or the professor's and lab lead's screens.

| Part | Structure | Source |
|---|---|---|
| Shell | Left sidebar of sections, with Help, Manual and Settings at the bottom. Top bar: search, theme, language, notifications, user. A collapsible right panel and an AI-agent button. Roles (professor, lab lead, researcher, operator) see different screens [P]. | https://ibel-research-portal-demo.vercel.app |
| Home | Today's to-do, ordered "others are waiting on me → deadline near → professor confirmation", with counts. Each open item has a link to go and do it. Papers by stage, each with progress and the blocking reason. Upcoming deadlines (D-n) [P]. | same |
| Paper page | A horizontal strip of 9 stages with dates and gates between them. "Next to do" in one sentence with its deadline. A writing history with a count and the latest entry. Files in folders per stage [P]. | same |
| Calendar | A month grid. Event kinds are coloured chips that also act as filters. Events are **deadlines (the future)**, each naming its paper. A "next 60 days" list. ICS export or subscription [P]. | same |
| Weekly report | Week picker. Per paper: changed this week / to do / blocked. "No change this week" listed. Export [P]. | same |

**Boundary.** The portal is the **lab's view of papers moving through stages and gates**: who is waiting on whom, and which deadline is near. Lemmata is the **researcher's view of what lies behind one paper**: its claims, experiments, code, runs and LaTeX, and whether they agree, over time. They would meet at the paper stage where implementation and experiments happen. A portal "paper" would be one Lemmata project, and Lemmata's thesis counts would be the kind of detail that the portal's stage strip summarises in one step. This page proposes no integration.

The research marks these as not verified, and Lemmata does not rely on them: Neptune, Comet, Aim, ClearML, TensorBoard HParams, Elicit, Consensus, SciSpace, Kialo, Argdown, Connected Papers, Litmaps, Heptabase, NotebookLM, Manusights (as a product), PeerReviewAI, thesify, Paperpal Preflight, alphaXiv, YesNoError.

## 4. What Lemmata takes, what it does not, and why
Column "Lemmata today" describes this branch's code. It is not a claim about the product in that row.

| From | Lemmata takes | Lemmata does not take | Why | Lemmata today (code) |
|---|---|---|---|---|
| Reviewer3 | Findings grouped by named check, each with a severity and an anchor. One delivery model across web, JSON API and MCP. | Code Replication (running the author's code). Parallel LLM reviewer agents on the hub. | The hub runs no model and runs no user code (ADR-007; CLAUDE.md Runtime). Paper ↔ code checks are "Later, low priority" in CLAUDE.md. | Review page = named checks; findings = `/api/findings`; MCP tools exist (`mcp.py`) |
| Google PAT / Deep Review | Order: summary → major issues → minor. Severity filter. Markdown export. | Section-parallel LLM review with search grounding. | Same runtime rule. `claims.md` already exports Markdown. | `GET /api/claims.md` |
| Refine | **No anchor, no finding.** A detail panel beside the content. | A 30-minute LLM pass per paper. | The rule already holds: data-model §6.1 says a finding with no `path`+`line` is not emitted. | Evidence objects with `path`/`line` everywhere |
| paperreview.ai | Nothing structural. | A single templated review and a 1-10 score. | A score hides the evidence. The founder's request is to *see* how the thesis is backed. | — |
| GPTZero | **One row per item:** verdict, justification, matched source. A fixed word list with an explicit "unsure/unknown". | The word "fake". | The data-model wording ban forbids "fake". Lemmata says "could not be matched". | `reference_unmatched` finding |
| scite | **Counts first, then the list.** The supporting sentence shown beside each label. | A trained classifier. | Status must come from rules (S24-01 acceptance criteria). | Claim meter counts stages (`rxCoreCard`) |
| q.e.d | The claim as the organising object: claim → gaps → next step. | Its UI, which is [NV]. | The only checker organised by claim, but too little is verified to copy details. | Claims → Experiments sections; Review checklist; `plans.py` next steps |
| citation-check | Four support labels, each with a quote and a page. "Changed" kept apart from "flagged". | — | Matches "Lemmata drafts, I confirm": drafted (flagged) ≠ confirmed (changed). | Claim `state` proposed / confirmed |
| Bib Check Agent | **Rules first, agent only on what the rules flag, and a check on the agent's output.** | — | This is ADR-007's pattern (agent proposes, `verify()` drops what fails, the person confirms). | `understand.verify`, `review.report`, `plans.propose` |
| W&B | A pinned baseline: every result shown against one comparator. Lineage as a secondary lens. | Artifact-graph clustering. | The comparator is the heart of "supports". The graph is a lens, not the main view. | `summary.gap` vs best other or `base`; Graph page |
| MLflow | Parent/child rows: an experiment row that expands to its runs. | — | Same shape as a map experiment (a group of result files). | Map experiment = file pattern; tuning collapses into one row |
| DVC VS Code | An activity-bar container with a few panels; detail tables as editor tabs. | Plots inside VS Code. | Lemmata's detail already opens as one webview tab (S16). | Container `lemmata` with 2 tree views + 1 webview tab |
| Test Explorer | Tree items that carry a file and line; leaf status rolled up to "x / y". | — | It is the closest native pattern to Claim → Experiment → Run. The source is still to be added. | Alarms tree items open the file at the line |
| GSN | **"Undeveloped" as an explicit state** for a goal with no evidence. | The strategy node. | A claim with no experiment must be visible, not empty. | `counts.untested`; "Not tested yet" rows |
| Discourse Graphs | Links typed "supports" / "opposes". | — | Gives the link-status words. | `ahead` / `behind` per experiment |
| ORKG | Contribution = problem + method + results, compared in a table. | A shared public graph. | Matches Setup (method, dataset, metric) and the comparison grid. | `setup.py` items, `grid` per experiment |
| Mermaid | Diagrams in `docs/map/`. | — | Render on GitHub [P] and in the VS Code preview (version to verify). | — |
| IBEL portal (S24-01b) | **A to-do whose every item opens the page it is about**, ordered by who or what is waiting. **A time axis** for the research. **One home per researcher or research**, which others can open. Counts on the home ("changed / to do / blocked"). | Its stage-and-gate model and its 9 stages; its visual design and wording; the month grid as the main view; ICS export; the AI-agent button; roles. | Lemmata tracks claims and experiments, not submission gates. The founder wants the **trail of what was done** (looking back), while the portal's calendar holds deadlines (looking forward). The hub runs no model (ADR-007). S24-01b says to take patterns only. | Tasks (feedback with targets), Timeline steps, `stages.json`, History, Digest; read-only = exported snapshot only |

## 5. Consequences for Lemmata (decisions are in ADR-008)
- The **spine** is Thesis → Claim → (link with a criterion) → Experiment → Setup → result files, code, runs → paper location.
- **Status sits on the link**, not on the experiment. One experiment can test two claims with different criteria. Discourse Graphs type the link for the same reason.
- **Statuses are words from a fixed list.** Each carries the rule that produced it. Lemmata takes the "x / y" rollup from Test Explorer, the "undeveloped" state from GSN, and counts-first from scite.
- **The LLM drafts only.** The criterion is drafted in the project map by the researcher's own agent, checked by rules, and confirmed by the researcher. This follows the Bib Check Agent pattern and ADR-007.
