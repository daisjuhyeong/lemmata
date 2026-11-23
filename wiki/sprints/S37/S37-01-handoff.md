---
type: handoff
owner_agent: lead
status: phases 1, 2 and 3 built (rules), on s37-survey and next; phases 2b and 4 and the meaning pass not built; not on main
sources:
  - "S37-01-task.md (the card) ; ../../decisions/ADR-013-survey-papers.md"
  - "founder message in chat, 2026-11-23 17:34 KST: 'just make it.' (the lead built it in the chat session instead of waiting for the agent team)"
  - "code: app/src/lemmata/engine/survey.py (new), engine/api.py, engine/study.py, engine/understand.py, server.py, hub/overleaf.py, hub/routes.py, web/research.js, web/app.js, web/app.css, web/hub/hub.js ; tests: app/tests/test_survey.py (new), test_overleaf.py, test_study.py"
  - "https://github.com/daisjuhyeong/Online-Deep-Anomaly-Detection (README.md, Models.md, Dataset.md read 2026-11-23; used as test input for the list check)"
last_reviewed: 2026-11-23
---
# S37-01 handoff: survey papers

**Ready for the founder once the hub runs `next`:** on the hub's New project page, the owner sees **Overleaf (Git)**. Paste the
Git link from the Overleaf project's Integrations → Git, paste an Overleaf Git token the first time, pick the survey's GitHub
repository as the code repository, Create. The project reads as a Survey by rule Y5; **Changes to apply** is in the sidebar.

## What changed
| Part | What |
|---|---|
| Kind of study | `survey` added (`study.py`); rule Y5: paper + repositories with no code or result files. Experiment pages read it like a benchmark study. Maps cannot set it (`MAP_KINDS`) |
| Engine | `engine/survey.py`: places of a .tex file (sentences, table rows with cells, forest nodes with their path, headings, display maths; comments, verbatim and tikz skipped); versions of the paper folder (git, also a folder inside a larger repository; the working tree counts as the newest version); sentence-to-sentence pairing; word-level spans with articles trimmed; ripple rules term / fact / number / label; moved sentences are not changes; markdown tables of the code repositories as the model and dataset list; list check add / update / not in paper / two lists / dataset's model |
| API | `GET /api/survey`; `POST /api/survey` with `action` = `baseline` (rev), `mark` (row, state fixed / leave / open), `confirm`. Store `.lemmata/survey.json`. The first look sets the baseline to the newest version |
| Website | Page **Changes to apply** ("What else must change?"): the two versions compared (select another), Check for a new version, Confirm this version; per change the old → new words, before and after, and rows with the quote, the match underlined, where (opens the lines), table row / taxonomy tree / model list, Fixed / Leave as is / Undo; then **Model list on GitHub**. Sidebar group "Survey" with the count of open rows; a line at the top of Home; footer link in narrow windows |
| Hub | `parse_project` accepts `https://git@git.overleaf.com/<id>`, `https://git.overleaf.com/<id>`, the whole `git clone …` line; `GET/PUT /api/hub/overleaf/enabled` for the owner; the Overleaf routes answer the owner also through the public address (ADR-013 point 6, proposed); status carries `overleaf_enabled` for the owner; New project has an **Overleaf (Git)** choice for the owner with the link and token fields |

The Overleaf fetch itself is the S05 code, unchanged: every sync (default 5 minutes), at most once per 120 s per project, read only,
token only in git's environment.

## Checked
- Python suite: 301 tests OK (2 skipped), 14 new in `test_survey.py`: places, term / fact / number / label changes, moved
  sentences, list check, rule Y5, baseline / marks / fixed-but-still-differs / confirm, a paper folder inside a larger repository,
  and the hub end to end with the fake Overleaf: switch on, token, project from the `git@git.overleaf.com` link, kind survey,
  a new Overleaf commit, sync, survey shows 5 changes, mark, confirm, token absent from the output.
- With the real `Online-Deep-Anomaly-Detection` markdown (48 models): rows came out for the sample paper's ARCUS in both README.md
  and Models.md; the dataset check found two names that are not in the model list (`CybserCScope` in Dataset.md line 54,
  `Belacel etl al.` line 67), likely typos.
- Browser (Chrome headless, local server on a two-version sample): 1360, 760 and 420 px, no console errors, no sideways scroll.
  Screenshots: [survey-1360](screenshots/survey-1360.png), [survey-420](screenshots/survey-420.png), [home-1360](screenshots/home-1360.png).

## Not checked
- The real survey paper (not available to the build) and the real Overleaf: the first real fetch is the founder's.
- The hub's New project page in a browser (syntax checked only).
- The Mac mini hub; the VS Code extension (unchanged).
- How the rules behave on a 32-page paper: speed and how many rows. One scan of the sample takes well under a second.

## Not built (still on the card)
- Phase 2b: the agent drafts fixes, the founder approves a diff, the hub pushes one commit to Overleaf.
- The meaning pass through the researcher's own agent (MCP `ripple_brief` / `propose_ripples`).
- Phase 4: the Survey panel in VS Code.
- The six-part survey map confirmed by the researcher: the rules work without it (they read cite keys, list model names and
  symbols directly). The vocabulary mapping between the list's values and the paper's categories: only columns with the same
  header are compared.

## Open questions for the founder
1. ADR-013 point 6: may the owner save the Overleaf token through the public address? (Built that way; say no and it goes back
   to the private address only.)
2. Phase 2b next, or the VS Code panel first?
3. The two names in Dataset.md (`CybserCScope`, `Belacel etl al.`): typos to fix in the repository?
