---
type: architecture
owner_agent: cto
status: proposed
sources:
  - "../../wiki/decisions/ADR-008-top-down-evidence-spine.md (the proposal these diagrams draw)"
  - "../../wiki/sprints/S24/S24-01-cto-benchmark-to-lemmata.md (task; founder asked for a flow chart viewable in VS Code, chat 2026-11-16)"
  - "code on branch s24-topdown-evidence, read 2026-11-16: app/src/lemmata/engine/{api,claims,experiments,track,review,setup,understand,runs,process}.py, app/src/lemmata/{server,mcp}.py, app/src/lemmata/web/{app,research}.js, vscode/package.json, vscode/src/{extension,runs,tab}.ts, vscode/src/core/{embed,link}.ts"
  - "https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams (Mermaid renders on GitHub [P])"
last_reviewed: 2026-11-16
---
# Lemmata page and object map

Five diagrams that let us talk about Lemmata without mixing up words. Each file has **Today (this branch)**, which is what the code on `s24-topdown-evidence` does, and **Proposed**, which is [ADR-008](../../wiki/decisions/ADR-008-top-down-evidence-spine.md) and is not built.

| File | Shows |
|---|---|
| [01-object-map.md](01-object-map.md) | The objects and how they back each other: thesis, claims, experiments, setup, files, runs |
| [02-page-hierarchy.md](02-page-hierarchy.md) | Tabs, the pages under them, the proposed top-down Experiments page, To-do and Trail, and the phase 2 nav with Home |
| [03-website-vscode-nav.md](03-website-vscode-nav.md) | How the website and VS Code reach each other |
| [04-data-flow.md](04-data-flow.md) | From the repositories to each page, and where the agent and the researcher come in |
| [05-claim-status.md](05-claim-status.md) | The status words and the rules that set them |

**Viewing.** GitHub renders Mermaid in Markdown [P] (URL in sources). The research reports that VS Code 1.121 has the Mermaid preview built in, and that older versions need the "Markdown Preview Mermaid Support" extension. That is not verified: check it on your VS Code (open a file, then Ctrl/Cmd+Shift+V). The diagrams were checked with mermaid-cli 11.16.0 (`mmdc`) on 2026-11-16. All 14 render with no syntax error. They were not opened in the VS Code preview or on GitHub.

## Glossary
One sentence per term, then where it lives. "Page" is the website tab key (`openTab('<key>')` in `web/app.js`, `RX_PAGES` in `web/research.js`). The same keys work in the VS Code tab (`VIEWS` in `vscode/src/core/embed.ts`). Terms marked *(proposed)* do not exist in the code yet.

### Spine
| Term | Meaning | Page | API route | Engine file |
|---|---|---|---|---|
| **Thesis** | The paper's one main message. In the code it is the **core message** (`id: "core"`), drafted from the abstract and reworded by the researcher. Every claim hangs under it. | Claims (top card, `rxCoreCard`); *(proposed)* header of Experiments | `GET /api/claims` → `core`; `POST /api/claims {id:"core", text}` | `engine/claims.py` (`pick_core`, `draft`, `build`) |
| **Claim** | One statement the work makes, such as a contribution, a research question or a theorem. It is drafted from the paper or made from a confirmed map question, and the researcher confirms or rejects it. | Claims; Experiments (one section per claim) | `GET /api/claims`, `POST /api/claims`, `/api/claims/link`, `/claims/add`, `/claims/remove` | `engine/claims.py` |
| **Question** | An entry of the project map (RQ, hypothesis, contribution) with a quote from the paper. Confirming the map turns each question into a claim. | Experiments (map card) | `GET /api/map` | `engine/understand.py` |
| **Stage** | Where a claim stands: Hypothesis, Being tested, Finding, Not supported, or Exploration (only the researcher sets Exploration). It is set by rules from the claim's experiments, and the researcher can overrule it. | Claims, Experiments, Review (chip) | in `GET /api/claims` (`stage`, `stage_by`, `stage_why`) | `engine/claims.py` (`STAGES`, `stage_of`, `restage`) |
| **Evidence status** | An older, second word on each claim: supported / partial / unsupported, meaning whether its paper items trace to result files. It still decides the stage of a claim with no experiment. | Claims (list) | `GET /api/claims` (`status`) | `engine/claims.py` (`_status`) |
| **Link** *(proposed)* | The pair "this claim is tested by this experiment", with its own criterion and status. Today the pair exists, as map `tests` or claim support links, but it has no criterion or status. | Experiments rows | `GET /api/experiments` (`sections[].experiments[].link`) | `engine/track.py`, `engine/experiments.py` |
| **Criterion** *(proposed)* | What "supports" means for one link: the comparator, the metric, which datasets, and whether a tie counts. The agent drafts it in the map, the researcher confirms it, and a default applies until then. | Experiments row detail | `POST /api/experiment` (new fields) | `engine/understand.py` (verify), `engine/track.py` |
| **Link status** *(proposed)* | supports / contradicts / inconclusive / not run (later also running), each with the rule that set it. | Experiments rows | as Link | as Link |
| **Experiment** | A group of result files that answers something. With a confirmed map it is a file pattern (`map:<id>`) of type main / ablation / sensitivity / tuning / efficiency / analysis / other. Without one, it is a paper table or figure, or a single result file. | Experiments (rows; expand = detail) | `GET /api/experiments`, `GET /api/experiment?id=`, `POST /api/experiment` | `engine/track.py` (map), `engine/experiments.py` (rules) |
| **Ours / base / baseline** | "Ours" is the method the work proposes (set once in the map). "Base" is the method of the paper being extended, if any. A baseline is any other method in the same results. | Experiments, Setup, Review | in the documents above | `engine/track.py` (`ours_of`, `names_match`), `engine/experiments.py` (`pick_ours`) |
| **Setup item** | One metric, dataset or method found in the experiments' result files, with how each experiment uses it. | Setup | `GET /api/setup`; MCP `setup` | `engine/setup.py` (built from each experiment's `grid`) |
| **Study** | The kind of study a project is: *method paper* (it has an "ours", ranked against baselines) or *benchmark study* (it compares existing methods; nothing is "ours", and a claim is decided by its own test). Set by the researcher; until then by the confirmed map, then by a rule. | Home, Thesis, Setup (one line) | `GET`/`POST /api/study`; MCP `study` | `engine/study.py` (rules Y1-Y4) |
| **Compared method** | In a benchmark study, a method named by a column with the method role (`model`, `detector`, or the map's `roles`). A test, a case, a source or a group is a row, not a method. | Setup, Thesis rows | in `GET /api/setup` (`role: compared`) | `engine/setup.py`, `engine/track.py` |
| **Key number** | A number the report quotes, with the committed file that stores it and how it is read from it. Read again at every scan: ok, mismatch, missing, gap or not compared. Proposed by the researcher's agent, checked by rules, confirmed by the researcher; a hypothesis's test lists its own. | Key numbers; a hypothesis on Thesis; Review | `GET /api/numbers`, `POST /api/numbers`; MCP `key_numbers`, `propose_numbers` | `engine/numbers.py` (rules only) |
| **Provenance gap** | Something about a key number that cannot be traced: no file stores it, no logged run wrote its file, the file is in no commit, a run's start commit is unknown. | Key numbers (bottom), To-do | `gaps` in `GET /api/numbers` | `engine/numbers.py` |
| **Sync state** | How the hub's last sync with GitHub went. While it fails, Lemmata's copy is behind and says so instead of calling a run or a file missing. | a note on Home, Thesis, Setup, Review, Key numbers; the footer | `sync` in `GET /api/project` | `hub/projects.py` (`_sync_mark`, `_fetch_error`) |
| **Board** | The top of Setup: four columns of cards, thesis (or problem) ← claims ← experiments ← what was used. Click a card to light its path; a dashed card is not connected. In a hypothesis-first project the cards are the problem, the hypotheses, the protocol's steps, and what each step's own result tables name. | Setup (top) | `board` inside `GET /api/setup` | `engine/board.py` (rules only) |
| **Grid** | A small table per experiment: a row per method, a column per dataset, the main metric and the other measures. Setup reads it. | (inside Experiments and Setup) | in `GET /api/experiments` | `engine/track.py`, `engine/experiments.py` |
| **Result file** | A data file the code wrote (under `results/`, `outputs/`, ...). It is a node of the project graph, and the ledger says whether it is newer than the code behind it. | Experiments ("All result files"), item pages | `GET /api/ledger`, `GET /api/graph` | `engine/graph.py`, `engine/process.py` (`ledger`) |
| **Run (record)** | A `runs/<id>.json` file in the code repository. It becomes a `run` node linking a script, settings and outputs. | Experiment detail ("Runs") | in `GET /api/experiment` (`design.runs`) | `engine/graph.py`, `engine/claims.py` (`_Ctx.chain`) |
| **Run (logged)** | A manifest of one run made in the VS Code terminal, a results-folder watcher or the coding agent's hook: command, commit, numbers, files written. It is sent to the hub. It is **not linked to experiments today.** | VS Code Runs view; Digest line | `GET /api/runs`, `POST /api/runs`; MCP `runs`, `log_run` | `engine/runs.py`; `vscode/src/runs.ts` |
| **Paper location** | The `.tex` file and line of a claim, table or figure. It opens in the editor in VS Code. | everywhere a place is shown (`rxWhere`) | `loc` fields | `engine/latex.py`, `engine/graph.py` |
| **Recheck / stale** | A result file is older than the code or settings behind it, so every experiment and claim resting on it needs a recheck. | Experiments (`↻ old`), Claims (Recheck) | `x.stale`, `claim.recheck` | `engine/process.py` (`ledger`), `engine/api.py` (`_claims_base`) |
| **To check (`!`)** | Something in an experiment needs a look before you trust it: the paper table differs from or is not found in the files, bold is not the best, there is no result file, or it is stale. | Experiments rows | `x.attention` | `engine/track.py`, `engine/experiments.py` |
| **Buckets** | Experiments linked to no claim ("No claim yet") and claims with no experiment ("Not tested yet"). | Experiments | `counts.no_claim`, `counts.untested`, `unassigned` | `engine/track.py`, `engine/experiments.py` |

### Around the spine
| Term | Meaning | Page | API route | Engine file |
|---|---|---|---|---|
| **Project map** | What the researcher's own agent understood about the project: the method's name, the questions, which files form which experiment. Rules check it, and **only the researcher confirms it** (ADR-007). | Experiments (map card) | `GET /api/map`, `POST /api/map`, `/map/draft`, `/map/edit`, `/map/confirm`, `/map/discard`; MCP `project_brief`, `project_map`, `propose_map` | `engine/understand.py`; stored in `.lemmata/map.json` |
| **Review** | The "should I continue?" page: three checks (moving? ahead? enough to write?), one five-item checklist per claim, ours against each baseline, and next-experiment plans. | Review | `GET /api/review`, `POST /api/review`; MCP `confound_brief`, `report_confounds` | `engine/review.py` |
| **Checklist** | Per claim on Review: more than one run, a baseline, an ablation, a paper table that matches the files, and confounds checked. Each item is done / todo / na / stale. | Review | in `GET /api/review` | `engine/review.py` (`checklist`) |
| **Hoped conclusion** | The researcher's best-case conclusion, written before the results are in. It is not the thesis. | Review | `POST /api/review {hoped}` | `engine/review.py` |
| **Plan** | A next experiment proposed by the researcher's agent and kept, edited or dropped by the researcher. | Review (claim row), experiment detail | `GET /api/plans`, `POST /api/plans`; MCP `experiment_brief`, `propose_experiments` | `engine/plans.py` |
| **Finding (integrity)** | An automatic check result on the paper, such as an unmatched reference, a main-text/appendix mismatch or an undefined ref. **Not the same as the stage "Finding".** | Checks (under Review); VS Code "Alarms and findings" | `GET /api/findings`; MCP `findings` | `engine/checks.py` |
| **Alarm** | Something changed since the checkpoint, and these paper items depend on it. | Changes (under Review); VS Code "Alarms and findings" | `GET /api/alarms`; MCP `alarms` | `engine/alarms.py` |
| **Checkpoint** | A saved "everything was fine here" state that alarms are measured from. | footer, VS Code command | `GET/POST /api/checkpoints` | `engine/history.py` |
| **Digest** | A short weekly summary in prose: what moved, what is stale, and tasks. | Digest | `GET /api/digest` | `engine/process.py` (`digest`) |
| **Timeline / Growth** | How the claims tree grew and changed stage over time. | Timeline (under Claims) | `GET /api/timeline`, `GET /api/tree` | `engine/process.py`, `engine/claims.py` (`tree`) |
| **Notation** | A glossary of the paper's symbols, with uses that disagree. | Notation (under Claims) | `GET /api/notation` | `engine/notation.py` |
| **Evidence (one node)** | The chain behind one paper item: result files, code, settings, runs, and the claims it backs. **Not the spine.** | node page (`pageEvidence`) | `GET /api/evidence?node=` | `engine/api.py` (`evidence`) |
| **Task** | One point of pasted feedback (from an advisor meeting, say), with the paper items, files and claims it names. It is open, done or dropped. | Tasks (under Digest) | `GET /api/tasks`, `POST /api/feedback`, `POST /api/tasks`; MCP `tasks`, `add_feedback` | `engine/process.py` (`add_feedback`, `match_targets`, `tasks_view`) |
| **History** | Every commit and run by day, with the checkpoint line. | History (under Digest) | `GET /api/events` | `engine/history.py`; page `pageHistory` in `web/app.js` |
| **Changes** | What changed since the checkpoint and what rests on it ("since you last looked"). | Changes (under Review) | `GET /api/alarms` | `engine/alarms.py` |
| **To-do** *(proposed)* | One list made by rules (drafts to confirm, paper ≠ files, stale results, gaps) plus the open feedback tasks. Each item opens its own page and is ordered by who or what is waiting. | Digest "Next to do" (step 4), then Home | `GET /api/todo` *(new)* | `engine/todo.py` *(new)* |
| **Trail** *(proposed)* | The time axis looking back: commits, runs, stage changes, map confirmations, feedback, checkpoints and plans as day rows, with deadlines ahead. Clicking an entry opens the object as it was then. | History becomes Trail (step 5), then a tab | `GET /api/trail` *(new)* | `engine/trail.py` *(new)* |
| **Deadline** *(proposed)* | A date the researcher enters, such as a submission or an advisor meeting, optionally tied to a claim or experiment. | Trail, Home | `POST /api/deadlines` *(new)* | `.lemmata/deadlines.json` *(new)* |
| **Home** *(proposed)* | One page for one research: thesis counts, next to-dos, recent trail, deadlines, this week's digest. | *(phase 2)* replaces Digest | — | — |
| **Viewer** *(proposed)* | A GitHub login the owner lets see one project read-only (for example the PI). Today the only way to let others watch is the exported HTML snapshot. | all pages, read-only | `GET` only | `hub/projects.py`, `hub/routes.py` *(new checks)* |
| **Lens** *(proposed)* | Two views of the same objects inside one page: the Outline (table) and the Tree (graph) of Thesis. | *(phase 2)* Thesis | — | — |
