---
type: task
owner_agent: lead
status: ready (founder decided the workflow and the panel on 2026-11-23 17:16 KST; inputs revised 17:22 KST; Overleaf Git found available 17:32 KST); not started
sources:
  - "founder message in chat, 2026-11-23 17:12 KST: 'If I were to organize a survey paper without experiment section, how would Lemmata work? I want to use Lemmata so that whenever I make a change to a sentence or so, the change is checked across the page so that I can see where else I need to apply the change. I am writing it on overleaf latex, and if I need to pay for the updated latex, I can consider using visual studio code for monitoring the change, and I can just copy and paste the fixed version to overleaf latex code to compile it.'"
  - "founder message in chat, 2026-11-23 17:16 KST: 'Since I am using a free version of Overleaf (although I am using the invited version of the paid subsription), I would write in VS code and past into Overleaf. Regarding the extension, make a separate panel for Survey, so that it focuses more on the writing in latex code, rather than experiments. Although the key taxonomy, table, figures are considered in Lemmata.'"
  - "founder message in chat, 2026-11-23 17:22 KST: 'Also, the github is NOT the main hub for the survey. The writing is. https://github.com/daisjuhyeong/Online-Deep-Anomaly-Detection/tree/main This is the github of the survey but this is to list down the models that I have surveyed for further details. Since the main claim are in the writing regard the github as a supplementary tool. Although there is a markdown file for details on the dataset, models, which has to be updated as more models are being handled. Also, from what I am thinking, I can use the github to include additional test that I have done for the survey (this is inside the latex code). I think it is better for me to input the latex code zip into Lemmata by myself, and you tell me when ready'"
  - "founder message in chat, 2026-11-23 17:29 KST: 'But donwloading and uploading the zip everytime I write something sounds inefficient.'"
  - "founder message in chat, 2026-11-23 17:32 KST, after opening Integrations → Git in the Overleaf project '[Survey] Recent Frontiers and Trends in Online Deep Anomaly Detection' (owner thedaislab): the dialog shows a git clone command for https://git.overleaf.com/<project id>, so Git integration is open to him on this project although his own account is on the free plan"
  - "https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git-integration/git-integration-authentication-tokens (read 2026-11-23): tokens are generated in Account Settings or from the project's Git dialog; username 'git', the token as the password; tokens expire after one year; at most 10 tokens; the page says nothing on rate limits or push conflicts"
  - "https://github.com/daisjuhyeong/Online-Deep-Anomaly-Detection at main (read 2026-11-23): README.md (awesome list; per-year model tables with columns Model, Paper Title, Venue, General Type, Base Model, Concept Drift Detection, Availability of Label, Streaming Method, Target Anomaly, Anomaly Score, Model Update, Resources), Models.md (the same tables, links left as '#'; 48 models in each, the same rows on 2026-11-23), Dataset.md (Dataset Name, Number of Instances, Number of Features, Anomaly Rate, Description, Data Type, Models, URL)"
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

Lemmata today assumes experiments (ADR-009: method paper or benchmark study) and a GitHub repository as the hub, and
ADR-011 took paper findings out of VS Code. None of this fits a survey.

## Decided by the founder (2026-11-23, 17:16 and 17:22 KST)
1. **The writing is the hub, not GitHub.** The main claims are in the LaTeX. The survey's GitHub repository
   (`daisjuhyeong/Online-Deep-Anomaly-Detection`) is a supplementary tool.
2. **The paper reaches Lemmata through Overleaf's Git, with no manual step.** He keeps writing and compiling in Overleaf.
   His own account is free, but the survey's Overleaf project (owner thedaislab) offers Git: the Integrations → Git dialog
   shows a clone command (17:32 KST). Uploading a zip after every edit was rejected as inefficient (17:29 KST); a zip upload
   stays only as a fallback for projects without Overleaf Git, and for a first look.
3. **The VS Code extension gets a separate Survey panel, focused on the LaTeX writing, not experiments.**
4. **The key taxonomy, tables and figures are part of what Lemmata checks.**
5. **The GitHub repository has two jobs:** its markdown files list the surveyed models and datasets and must be updated
   as more models are handled; and it may hold additional tests done for the survey, whose results are reported in the LaTeX.

The CTO writes **ADR-013** recording these five points as accepted (sources: the messages above). It amends ADR-011 for
survey projects only: for them, VS Code is the writing bench and the experiment views are not shown; the project's hub is
its paper (pulled from Overleaf's Git), with a GitHub repository attached as a supplement. For method papers and benchmark studies, ADR-011 is
unchanged. Anything the ADR adds beyond the five points is "proposed" until Juhyeong says yes.

## What to build

### Phase 1: a survey project that follows Overleaf (engine, rules)
- **A third kind of study, `survey`** in `study.py` (word: "Survey"). No "ours", no runs, no key numbers from result files.
  A project whose paper has no experiment folders is offered as a survey; the researcher confirms.
- **Creating a survey project needs no GitHub repository.** New project → "Paper from Overleaf (Git)": the researcher pastes
  the project's Git URL (`https://git.overleaf.com/<id>`) and an Overleaf Git token, which he generates himself in Overleaf
  (Account Settings, or Generate token in the project's Git dialog). A GitHub repository can be attached afterwards as the
  supplement (Phase 3).
- **The token.** Stored on the hub like the GitHub sign-in (never in a repository, a log, a page or a brief; shown only as
  "set, expires <date>"). Overleaf's Git takes the username `git` and the token as the password; tokens expire after one
  year, so the hub warns 30 days before and names the expiry in the sync message. The hub's git accepts only https and
  ignores user git settings (S29), so the credential is passed per command, not through a credential helper of the user.
- **Pulling.** The hub clones once into `.lemmata/paper/` and fetches every 5 minutes while the project is open on the
  website or in VS Code, and every 30 minutes otherwise, plus a "Check now" button. Each new Overleaf commit is a version;
  the Trail shows them. Overleaf's history is translated into git by Overleaf, so commits may bundle several edits and may
  not name who made them: the version shows what changed, and "who" only where the commit says so. A failed fetch is named
  as in S29 (token refused, token expired, project not found, Overleaf unreachable) and pages say "behind" while it lasts.
- **Fallback: a zip upload** ("Upload the paper (LaTeX zip)") for papers whose Overleaf project has no Git. Each upload is a
  numbered version (`.lemmata/paper/v<N>/`, with the upload time and the zip's hash).
- **Safe unpacking (zip fallback).** Paths that leave the folder (`..`, absolute paths, links) are refused; a size cap for the zip and for
  the unpacked total; only text sources (`.tex`, `.bib`, `.sty`, `.cls`, `.bst`, `.txt`, `.md`, `.csv`, `.dat`) are parsed,
  images are kept as files for figure previews. Lemmata never compiles or runs anything from the zip. The main file is
  found by `\documentclass`; if there are several, the researcher picks one.
- **The survey map.** Proposed by the researcher's own agent from the first version (as in ADR-007: MCP `survey_brief`, then
  `propose_survey_map`), checked by rules, confirmed by the researcher. Six parts:

  | Part | What it holds | Example from his survey |
  |---|---|---|
  | Terms | a canonical term and the variants it replaced | "subsequence" (not "block", "segment"); "dependency" |
  | Notation | reuse `notation.py`: symbol, meaning, where defined | $q_\tau$; η anomaly threshold; γ drift threshold |
  | Taxonomy | the axes, their categories, and each surveyed model's place on each axis | ARCUS: generative or approximative; error-based or distribution-based |
  | Counts | a number the paper states about itself, with every place it appears | papers reviewed; per-year counts in the pgfplots chart |
  | Research questions | RQ → the paragraphs that answer it | RQ1 to RQ3 in the intro, discussion, conclusion |
  | Model statements | per surveyed model (cite key and name), what the survey says it does | "StrAEm++DD uses the Mann-Whitney U test" |

- **Taxonomy, tables and figures are read from the source, not a PDF.** The taxonomy figure (a Forest + TikZ tree) gives
  category → leaves; each table gives its rows (cite key or model name → the values in its columns); a pgfplots chart gives
  its data points. A name or cite key in a figure or table is linked to the same model in the text.
- **The baseline** is the confirmed map at a version (an Overleaf commit, or an upload). Confirming a change moves the baseline forward.

### Phase 2: the ripple check, per version
- **When a new version arrives (rules only):** compare it with the last confirmed version, unit by unit (`latex.py` units).
  List the changed units first ("what you changed": file, line, old and new text). For each changed unit, take what it
  touches: macros, symbols, map terms (and their old variants), cite keys, model names, labels, numbers, and taxonomy
  category words next to a model. List every other unit, table row, figure leaf or chart point that holds the same thing,
  with a status: **differs** (the same thing now says something else), **check** (the same thing appears; the rules cannot
  tell), **agrees**. Places that already disagreed before this version are listed apart, so a new version does not bury them.
- **The meaning pass, when the researcher asks:** for changes that share no word with the places they affect ("ARCUS is
  now distribution-based" vs a table cell "error-based"), the researcher's own agent gets a brief (MCP `ripple_brief`: the
  changed units, the map, the candidate places) and returns places with a one-line reason (`propose_ripples`). Rules check
  that each place exists and quote its line. The hub calls no model (ADR-006).
- **Each row can be marked fixed or "leave as is"** (stored on the hub, counts at once, can be taken back). A row marked
  fixed is checked again at the next version. When every row of a change is closed, the change can be confirmed into the baseline.
- **Every row quotes its line** (file, line number, the sentence with the matched part marked) so it can be found in
  Overleaf with its search.

### Phase 2b: applying the fixes, after the researcher approves
- For rows marked **differs**, the researcher can ask his own agent to draft the edit (MCP `fix_brief` → `propose_fixes`:
  per row, the old text and the new text, with a one-line reason). The hub calls no model.
- Lemmata shows all proposed edits of a change as one diff. The researcher approves all, some or none. A row he answers
  "leave as is" gets no edit. Nothing is written without that approval.
- **Approved edits are pushed back to Overleaf as one commit** on `main` (Overleaf's Git accepts pushes to `main` only),
  with a message naming the change and the rows. Before pushing, the hub fetches: if Overleaf moved since the version the
  edits were drafted on, it applies the edits only where the old text is still exactly there, and lists the rest as "changed
  in Overleaf since; draft again". Never a force push, never a merge that rewrites someone else's text. Co-authors edit the
  same Overleaf project, so this rule matters more than speed.
- For the zip fallback, approved edits come back as the changed files only, to upload into the Overleaf project over the old ones.

### Phase 3: the GitHub repository as a supplement (rules, paper → GitHub only)
- **Attaching it:** Settings of a survey project → "Supplementary repository". Lemmata reads it; it never writes to it.
- **Model list.** Lemmata reads the model tables in `README.md` and `Models.md` (header row with `Model`) and `Dataset.md`
  (header row with `Dataset Name`). The paper is the reference; the markdown is what gets updated:
  - a model the paper surveys (taxonomy leaf, table row or write-up) that no markdown table lists → **add to the list**;
  - a listed model whose columns disagree with the paper's taxonomy or tables (for example Concept Drift Detection
    "Error-based" in the list, "distribution-based" in the paper) → **update the list**, quoting both;
  - a listed model the paper no longer mentions → **check** (it may be kept on purpose);
  - `README.md` and `Models.md` rows for the same model that disagree with each other → **check** (on 2026-11-23 both hold
    the same 48 rows);
  - a dataset the paper names for a model that `Dataset.md` does not list for it, and the other way round → **check**.
  The vocabularies differ (the list says "AE", "Approximation", "Generative Model (VAE)"; the paper's axes say generative /
  approximative): the survey map holds the mapping between list values and the paper's categories, proposed by the agent
  and confirmed by the researcher, before any "update the list" row is shown.
- **For each "add" or "update" row, an editable prompt for the researcher's agent** (as in S20/S21) that edits the markdown
  table rows in the repository. The researcher runs it; Lemmata only checks the result at the next sync.
- **Additional tests.** If the repository holds code or result files for tests done for the survey, numbers in the LaTeX
  are traced to them with the existing key-number rules (S29: ok, mismatch, missing, gap). A test with no file behind its
  number is a gap, not an error.

### Phase 4: the Survey panel in VS Code, and the website
- The extension shows the Survey panel only when the project's kind is `survey`; for a survey, the experiment views
  (`lemmata.now`, `lemmata.experiments`, `lemmata.torun`) are hidden. For other kinds nothing changes.
- Views:
  1. **Changes to apply**: one group per change ("§4.2 l.118: ARCUS → distribution-based"), its rows below with status
     and the quoted line. Fixed / leave as is on each row. If the paper's folder is open in VS Code, a row opens the file
     at that line; otherwise it shows the quote.
  2. **Taxonomy**: axes → categories → models. Clicking a model lists every line, table row and figure leaf that places it,
     plus its row in the GitHub list, and marks any that disagree.
  3. **Tables and figures**: each float by label and caption; rows or leaves that are out of step with the text.
  4. **Terms and notation**: canonical terms and symbols; uses of a replaced variant; meanings that disagree.
  5. **Model list (GitHub)**: the add / update / check rows of Phase 3; a row opens the markdown file at the model's row.
  6. **Source**: where the paper comes from (Overleaf Git, with the last fetch time and "Check now"; or the last upload,
     with "Upload a new version (zip)"), and the token's expiry.
- The hub prepares the rows; the extension only draws them (ADR-011 item 6): `GET /p/<pid>/api/survey`.
- Bump the extension to 0.9.0 and commit the packaged file, so the hub offers the update (ADR-011 item 4).
- The website: "Paper from Overleaf (Git)" and the zip fallback on the new-project page; the source and its state on the
  survey project's Home; the approval diff of Phase 2b on Review; the same "Changes to apply" list on
  Review; the model-list rows on Setup. No new page.

## Acceptance
| # | What | Done when |
|---|---|---|
| 1 | Survey project | A fixture survey in a local git repository standing in for Overleaf's Git (a small acmart paper with a Forest taxonomy, two tables, one pgfplots chart, three RQs, no experiments, one figure image) creates a survey project with no GitHub repository, and so does the same paper as a zip; method and benchmark projects are classified as before |
| 2 | Safe unpacking | Zips with `../x.tex`, an absolute path, a symlink, and one over the size cap are refused with a plain message; nothing is written outside the version folder |
| 3 | Map | The fixture's map has all six parts after an agent proposal and a confirmation; the taxonomy is read from the Forest code, table rows from the tabular, chart points from pgfplots |
| 4 | Term change | A new commit with "subsequence" replaced by "segment" in one sentence lists every other use as **differs**, with no model call |
| 5 | Category change | A new commit changing one model's category in the text lists its table cell and its taxonomy leaf as **differs** by rules where the category word is next to the model, and through the meaning pass otherwise |
| 6 | Count change | Changing "87 papers" in the abstract lists the other places the count appears, and the chart's total if it no longer matches |
| 7 | Notation | Redefining γ in one place lists its other definitions and uses (reusing `notation.py`) |
| 8 | Close and confirm | Fixed / leave as is persist on the hub; a row marked fixed that still differs at the next version comes back; confirming moves the baseline |
| 9 | GitHub list | With a fixture repository copied from `Online-Deep-Anomaly-Detection`'s three markdown files: a model only in the paper → add; a changed drift column → update (after the vocabulary mapping is confirmed); a dataset missing from `Dataset.md` → check. Lemmata writes nothing to the repository |
| 10 | Panel | In a real VS Code window (or the extension's test host), a survey project shows the six views and no experiment views; a method project shows the 0.8.0 views unchanged |
| 11 | Cost | No model call on the hub; the meaning pass runs only when asked, and the handoff states its token cost on the fixture |
| 12 | Nothing else breaks | Python suite, extension suite (needs node), `test_s36_ui.py` all pass |
| 13 | Token and fetch | The token never appears in a page, a log, `wiki/`, a brief or a commit (grep the hub folder and the test output for it); an expired or wrong token gives the named message, not a stack trace; fetching every 5 minutes runs no rescan when nothing changed |
| 14 | Fixes go back safely | On the fixture: approved edits arrive as one commit on `main`; an edit whose old text was changed meanwhile by another commit is not applied and is listed as "draft again"; a rejected push is reported, never forced |
| 15 | Ready for the founder | On the Mac mini hub, after the hub's update, the new-project page offers "Paper from Overleaf (Git)". The handoff's first line says so, so the lead can tell Juhyeong it is ready |

## How to hand off
`S37-01-handoff.md` per phase, with screenshots of the source setup, the ripple list, the approval diff and the panel on the
fixture, what was not checked, and open questions. Update `wiki/index.md` and `wiki/log.md`. Line 15 is what the founder waits
for: he connects the survey's Overleaf project only after it. The build never connects to his real Overleaf project itself:
tests use the local stand-in, and the first real fetch and the first real push are his.

## Not known when this card was written
- **Overleaf's Git limits.** Overleaf's token page names no rate limit; the 5-minute fetch is a guess. If Overleaf refuses or
  slows fetches, the hub backs off and says so; the handoff reports what was seen on the first real day.
- **The other Overleaf projects.** Git is open on the survey project because of its owner's plan. Other projects he is
  invited to may or may not have it; the zip fallback covers those.
- **How regular the Forest code is.** His taxonomy is a large Forest + TikZ tree; if rules cannot read it reliably, the
  agent proposes the taxonomy from it once and rules check only that every leaf names a known model.
- **Where the additional tests will live in the repository.** None are there on 2026-11-23 (only the three markdown files).
  Phase 3's last item is built against a fixture and checked on the real repository when they appear.
