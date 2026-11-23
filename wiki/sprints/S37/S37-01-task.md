---
type: task
owner_agent: lead
status: ready (founder decided the workflow and the panel on 2026-11-23 17:16 KST); not started
sources:
  - "founder message in chat, 2026-11-23 17:12 KST: 'If I were to organize a survey paper without experiment section, how would Lemmata work? I want to use Lemmata so that whenever I make a change to a sentence or so, the change is checked across the page so that I can see where else I need to apply the change. I am writing it on overleaf latex, and if I need to pay for the updated latex, I can consider using visual studio code for monitoring the change, and I can just copy and paste the fixed version to overleaf latex code to compile it.'"
  - "founder message in chat, 2026-11-23 17:16 KST: 'Since I am using a free version of Overleaf (although I am using the invited version of the paid subsription), I would write in VS code and past into Overleaf. Regarding the extension, make a separate panel for Survey, so that it focuses more on the writing in latex code, rather than experiments. Although the key taxonomy, table, figures are considered in Lemmata.'"
  - "../../decisions/ADR-011-vscode-is-the-experiment-bench.md (VS Code is the experiment bench; paper findings leave VS Code; the hub prepares the rows) ; ../../decisions/ADR-009-study-kind-and-key-numbers.md (kinds of study) ; ../../decisions/ADR-006-public-multi-user-site.md (no model on the hub)"
  - "code at the head of next (399fbda): app/src/lemmata/engine/{latex.py (units, labels, refs, cites, numbers), notation.py (glossary, rules only), study.py (KINDS, WORDS), texout.py (snippets, stale numbers)}, app/src/lemmata/watch.py (change detection), vscode/package.json 0.8.0 (views lemmata.now, lemmata.experiments, lemmata.torun)"
  - "https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization (read 2026-11-23): Git integration and GitHub sync are premium features on Overleaf Cloud"
  - "https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git-integration (read 2026-11-23): Git integration 'will only be available if the project owner has a paid subscription'"
  - "https://docs.overleaf.com/getting-started/free-and-premium-plans/plan-limits.md (read 2026-11-23): compile timeout 10 s on the free plan, 240 s on premium"
last_reviewed: 2026-11-23
---
# S37-01 task card: survey papers, the ripple check, and a Survey panel in VS Code

Owner: CTO, who splits the build (pipeline-eng: engine and MCP; web-eng: VS Code panel and the website's list). Reviewer: QA.
Branch: `s37-survey`, from the head of `next`; onto `next` after its tests pass. Nothing goes to main without Juhyeong.

## Why
Juhyeong writes a survey (no experiment section) in LaTeX. When he edits one sentence, he wants Lemmata to show every other
place in the paper that says the same thing and may now disagree. A survey repeats the same facts in many places:
the taxonomy figure, the summary tables, the method write-ups, the intro, the discussion and the conclusion.

Lemmata today assumes experiments (ADR-009: method paper or benchmark study), and ADR-011 took paper findings out of
VS Code. Neither fits a survey.

## Decided by the founder (2026-11-23 17:16 KST)
1. **The paper is written in VS Code, in a git repository, and pasted into Overleaf to compile.** VS Code is the only place
   the text is edited. Overleaf is not read by Lemmata (Git and GitHub sync are premium; his own account is free).
2. **The VS Code extension gets a separate Survey panel, focused on the LaTeX writing, not experiments.**
3. **The key taxonomy, tables and figures are part of what Lemmata checks.**

The CTO writes **ADR-013** recording these three points as accepted (source: the message above). It amends ADR-011 for
survey projects only: for them, VS Code is the writing bench and the experiment views are not shown. For method papers
and benchmark studies, ADR-011 is unchanged. Anything the ADR adds beyond the three points is "proposed" until Juhyeong says yes.

## What to build

### Phase 1: the survey kind and its map (engine, rules)
- **A third kind of study, `survey`** in `study.py` (word: "Survey"). No "ours", no runs, no key numbers from result files.
  Default rule: a project with a paper and no experiment folders, results or run manifests is offered as a survey; the
  researcher confirms. Setting it by hand works as for the other two kinds.
- **The survey map.** Proposed by the researcher's own agent (as in ADR-007: the agent reads the whole paper once; MCP
  `survey_brief` then `propose_survey_map`), checked by rules, confirmed by the researcher. Six parts:

  | Part | What it holds | Example from his survey |
  |---|---|---|
  | Terms | a canonical term and the variants it replaced | "subsequence" (not "block", "segment"); "dependency" |
  | Notation | reuse `notation.py`: symbol, meaning, where defined | $q_\tau$; η anomaly threshold; γ drift threshold |
  | Taxonomy | the axes, their categories, and each surveyed paper's place on each axis | ARCUS: generative or approximative; error-based or distribution-based |
  | Counts | a number the paper states about itself, with every place it appears | papers reviewed; per-year counts in the pgfplots chart |
  | Research questions | RQ → the paragraphs that answer it | RQ1 to RQ3 in the intro, discussion, conclusion |
  | Paper statements | per cite key, what the survey says that paper does | "X uses the Mann-Whitney U test" |

- **Taxonomy, tables and figures are read from the source, not the PDF.** The taxonomy figure (a Forest + TikZ tree)
  gives category → leaves; each table gives its rows (cite key → the values in its columns); a pgfplots chart gives its
  data points. A cite key or name that appears in a figure or table is linked to the same key in the text.
- **The baseline** is the confirmed map at a commit. Confirming a change moves the baseline forward.

### Phase 2: the ripple check
- **On every save (rules only, from `watch.py`):** compare the working file with the baseline, unit by unit
  (`latex.py` units). For each changed unit, take what it touches: macros, symbols, map terms (and their old variants),
  cite keys, labels, numbers, and taxonomy category words next to a cite key. List every other unit, table row, figure
  leaf or chart point that holds the same thing. Each row gets a status: **differs** (the same thing now says something
  else), **check** (the same thing appears; the rules cannot tell), **agrees**.
- **On commit, or when asked, the meaning pass:** for changes that share no word with the places they affect ("ARCUS is
  now distribution-based" vs a table cell "error-based"), the researcher's own agent gets a brief (MCP `ripple_brief`:
  the changed units, the map, the candidate places) and returns places with a one-line reason (`propose_ripples`). Rules
  check that each place exists and quote its line. The hub calls no model (ADR-006).
- **Each row can be marked fixed or "leave as is"** (stored on the hub, counts at once, can be taken back). When every row
  of a change is closed, the change can be confirmed into the baseline.
- **Paste record.** VS Code is the source and Overleaf the copy, so Lemmata records what was pasted: a "Copy for Overleaf"
  command copies the whole current file to the clipboard and records file + commit. A list "Not pasted yet" shows files
  changed since their last copy. (Whole files, not snippets, so the two copies cannot drift sentence by sentence.)

### Phase 3: the Survey panel in VS Code
- Shown only when the project's kind is `survey`; for a survey, the experiment views (`lemmata.now`, `lemmata.experiments`,
  `lemmata.torun`) are hidden. For other kinds nothing changes.
- Views:
  1. **Changes to apply**: one group per change ("§4.2 l.118: ARCUS → distribution-based"), its rows below with status;
     clicking a row opens the file at that line. Fixed / leave as is on each row.
  2. **Taxonomy**: axes → categories → papers. Clicking a paper lists every line, table row and figure leaf that places it,
     and marks any that disagree.
  3. **Tables and figures**: each float by label and caption; rows or leaves that are out of step with the text.
  4. **Terms and notation**: canonical terms and symbols; uses of a replaced variant; meanings that disagree.
  5. **Not pasted yet**: files changed since their last copy, with the copy button.
- The hub prepares the rows; the extension only draws them (ADR-011 item 6): `GET /p/<pid>/api/survey`.
- Bump the extension to 0.9.0 and commit the packaged file, so the hub offers the update (ADR-011 item 4).
- The website's Review page shows the same "Changes to apply" list for a survey project; no new website page.

## Acceptance
| # | What | Done when |
|---|---|---|
| 1 | Survey kind | A fixture survey (a small acmart paper with a Forest taxonomy, two tables, one pgfplots chart, three RQs, no experiments) is offered as a survey; method and benchmark fixtures are still classified as before |
| 2 | Map | The fixture's map has all six parts after an agent proposal and a confirmation; the taxonomy is read from the Forest code, table rows from the tabular, chart points from pgfplots |
| 3 | Term change | Replacing "subsequence" with "segment" in one sentence lists every other use as **differs** within one watch cycle, with no model call |
| 4 | Category change | Changing one paper's category in the text lists its table cell and its taxonomy leaf as **differs** by rules where the category word is next to the cite key, and through the meaning pass otherwise |
| 5 | Count change | Changing "87 papers" in the abstract lists the other places the count appears and the chart's total if it no longer matches |
| 6 | Notation | Redefining γ in one place lists its other definitions and uses (reusing `notation.py`) |
| 7 | Close and confirm | Fixed / leave as is persist on the hub; confirming moves the baseline; the next save checks against it |
| 8 | Paste record | "Copy for Overleaf" copies the whole file and records it; editing the file puts it back in "Not pasted yet" |
| 9 | Panel | In a real VS Code window (or the extension's test host), a survey project shows the five views and no experiment views; a method project shows the 0.8.0 views unchanged |
| 10 | Cost | No model call on the hub; the meaning pass runs only on commit or when asked, and the handoff states its token cost on the fixture |
| 11 | Nothing else breaks | Python suite, extension suite (needs node), `test_s36_ui.py` all pass |

## How to hand off
`S37-01-handoff.md` per phase, with screenshots of the panel on the fixture, what was not checked, and open questions.
Update `wiki/index.md` and `wiki/log.md`.

## Not known when this card was written
- **Which repository holds the survey.** Juhyeong names it; the card's checks run on the fixture first, then on his survey.
- **Whether Overleaf's Git integration is already open to him.** Overleaf ties it to the project owner's plan, and he is
  invited to a project on a paid plan. If the Overleaf project's menu shows **Git**, he could clone it and push from VS
  Code, and the paste step (and the paste record) would not be needed. He checks this; until then the card assumes paste.
- **How regular the Forest code is.** His taxonomy is a large Forest + TikZ tree; if rules cannot read it reliably, the
  agent proposes the taxonomy from it once and rules check only that every leaf's cite key exists.
- **Compile.** The free plan's compile timeout is 10 s. If the survey stops compiling on Overleaf, LaTeX Workshop in
  VS Code with a local TeX install compiles it; that is the researcher's setup, not part of this card.
