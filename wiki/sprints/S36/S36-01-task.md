---
type: task
owner_agent: lead
status: ready (founder approved the design and the four decisions on 2026-11-22 22:24 KST); not started
sources:
  - "../../decisions/ADR-012-design-system-and-your-turn.md (the decisions, accepted 2026-11-22 22:24 KST)"
  - "../../design/screens/S36-design-system.md (the rules, the exact token changes, the mapping onto app.css, the pages)"
  - "founder message in chat, 2026-11-22 22:24 KST: 'proceed with your recommendation'"
  - "founder message in chat, 2026-11-22 22:27 KST: 'you proceed it to the task card and it is going to be done automatically'"
  - "../../../app/src/lemmata/web/{tokens.css,app.css,app.js,research.js} and ../../../app/tests/test_s18_ui.py at commit bc26f66; line numbers are from that commit"
  - "../S31/S31-01-handoff.md (the dark theme and how the browser checks were run) ; ../S35/S35-02-task.md (the form of this card)"
last_reviewed: 2026-11-22
---
# S36-01 task card: the design system on the website (tokens and parts first, then Home, Thesis and Review)

Owner: CTO, who assigns the build (web-eng). Reviewer: QA, before any merge to main. Branch: `s36-design-system`, cut from
`next` at bc26f66; onto `next` after its tests pass, as with earlier sprints. Nothing goes to main without Juhyeong.

Read first: [S36-design-system.md](../../design/screens/S36-design-system.md). It has the purpose of Lemmata in five lines,
the ten rules, and every value. This card only says what to build and how to tell it is done.

## Goal
The website follows one rule set. The researcher sees, on every page, the question it answers and the answer; and one
colour, used for nothing else, shows what waits for them.

## Scope
Two phases. Phase 1 is CSS and class changes only and can go to `next` alone. Phase 2 changes three pages.

Out of scope: the layouts of Setup, Trail, Baselines, LaTeX and Settings beyond their page head; the storyline (S32 step
1); short dataset names and families; the focus chip, the jump box and table controls; any change to the VS Code
extension beyond acceptance line 9; any change to what the hub computes, except the two small additions named in lines 12 and 13.

## Acceptance, phase 1: tokens and parts
| # | What | Done when |
|---|---|---|
| 1 | Token values | `tokens.css` has, in `:root`, `--muted: #646F68`, `--warning: #B5823A`, `--fs-tag: 13px`, `--highlight-edge: #8A7431`, `--on-highlight: #1A1A1A`; in the dark block, `--warning: #B5823A`, `--highlight-edge: #c9b06a`, `--on-highlight: #1A1A1A`. No other value and no name changes. `desktop/launcher/tokens.css` is byte-identical (`test_launcher_copy_matches` still passes) |
| 2 | Contrast is tested | A new `app/tests/test_s36_ui.py` reads `tokens.css` and computes WCAG contrast: in both themes `--text`, `--text-secondary`, `--muted` and `--accent-dark` are at least 4.5:1 on each of `--bg`, `--bg-2`, `--surface`, `--surface-hover`; `--on-highlight` on `--highlight` is at least 4.5:1; `--success`, `--warning`, `--error` and `--highlight-edge` are at least 3:1 on `--bg`; the relative luminance of `--warning` and `--highlight` differs by at least 0.15. `test_tokens_define_the_dais_palette` still passes |
| 3 | Sand is your turn | In `app.css`, `var(--highlight)` appears only in `.btn.primary` and in the dots that mean "waits for the researcher" (today: `.rdot.d-highlight`, `.chip.proposed::before`, the `.rxt-dot` of `.rxt-li.att`, `.hf-branch.warn::before`, and the tree's waiting node). Each has a `--highlight-edge` border. The test in line 2 lists the allowed selectors and fails on any other use |
| 4 | Primary buttons | `.btn.primary` is `--highlight` with `--on-highlight` text and a 1px `--highlight-edge` edge. Each of the 13 `btn primary` call sites is either kept (it settles something that waits on the researcher: confirming a claim, a problem, a hypothesis, a proposed link) or made a plain `.btn`. The handoff lists all 13 with the choice and one reason each. No page shows more than one sand button outside a list of waiting items |
| 5 | State tags | `.chip` text is weight 600 at `--fs-tag` in `--text-secondary`; its dot is 8px; the default and the hypothesis dot are a hollow ring (no fill, 1px `--muted`). The state word is always shown beside the dot |
| 6 | No pale information | `--muted-light` is not used as a text colour for anything but placeholders and disabled controls (today: `#status`, `.sg.ok`, `.hf-tag` change to `--muted`); `--fs-11` and `--fs-12` (app.css:2, both 12px today, 114 uses) are 13px; the 19 literal sizes below 13px in `app.css` (11px, 11.5px, 12px, 12.8px) use `var(--fs-tag)`, except text that carries no information, which the handoff lists |
| 7 | Control edges | A plain `.btn`, `.chip-btn` and text inputs have a 1px `--muted` edge and no fill at rest. Hairlines between rows and under headings are unchanged |
| 8 | Nothing moves that should not | At 1360, 760 and 420px, light and dark, on the test project: no page scrolls sideways that did not before; the Setup board and the claims tree keep their lines |
| 9 | VS Code | The embedded tab still reads as before (`vscode/media/vscode.css` overrides hold). The hypothesis dot is a hollow ring there too. The extension's unit, integration and browser suites pass; its version changes only if its own files change |

## Acceptance, phase 2: Home, Thesis, Review
| # | What | Done when |
|---|---|---|
| 10 | Page head | Home, Thesis, Setup, Review and Trail each start with an `h1` that is the page's question and one line that answers it from counts the hub already returns (table in the design page, section 7). A zero is said in words. No paragraph of standing explanation shows by default on these pages; each moved behind a "?" link in its section |
| 11 | Home is a list | `pageDigest()` draws, in the reading column: the page head, **Needs you**, **Since you last looked**, **This month**. The `.hm-cards` tiles are gone. The to-do list that `rxTodoList()` draws stays reachable from a link in the answer line, with its count |
| 12 | Needs you | It lists only what the researcher can settle: proposed claims, problems, hypotheses and links to confirm, names to confirm, and feedback that has no task yet. Each row has the your-turn dot and words, one sentence that does not wrap at 1280px, and its buttons; a drafted claim can be confirmed from Home in one click and the row then leaves the list. If the hub's to-do items do not say which of them wait on a decision, add that field on the hub and name it in the handoff |
| 13 | Since you last looked | The hub stores, per signed-in user and project, when Home was last opened, and returns what changed after that, newest first. Each row says who (your agent, a run, Lemmata), one sentence, the time, and one link. Where the record does not say who made a change, the row shows its kind and no name; nothing is guessed. On a first visit the section covers the last 7 days and says so |
| 14 | This month | The calendar is the one on Home today. Clicking a day shows rows that say who did what, where and when; no raw logged command is shown at the first level |
| 15 | Thesis | Under the page head, the claims tree is drawn with straight vertical and horizontal lines; every node has its short name and its state as words beside it; node fills follow the design page, section 7. On the test project, `mcd_extension` and `temporal_dependency` no two labels overlap at 1280px, and below 1100px the tree scrolls inside its own frame while the page does not. A storyline section shows only where a confirmed storyline exists |
| 16 | Review | Four sections in this order: Mismatches, Stale, To confirm, Checked and fine (one row with its count, closed by default). A mismatch row states both sides in one sentence; open, it shows each compared method, then the project's own, then the difference, with "no run" in words for a missing cell. Every number opens its file |
| 17 | Sidebar | Only Home carries the sand dot, beside the count of items in Needs you. Every other count is a plain number in `--text-secondary` |
| 18 | The five look-ups | From Home, each within three clicks and without reading an explanation: the main method's result on one dataset; the experiments that back one claim; the file a chosen number came from; what was run on a chosen day; the datasets on which a baseline has no result |
| 19 | Nothing else breaks | The Python suite and the extension's suites pass |

## How to hand off
- A handoff note `S36-01-handoff.md` for phase 1, and `S36-02-handoff.md` for phase 2, each with: what changed, what was
  not checked, open questions.
- **Side by side.** For every page that changed, a screenshot before and after at 1360px, light and dark, in
  `wiki/sprints/S36/screenshots/`. Juhyeong approves by looking.
- **Name the reference.** One line for any pattern taken from somewhere (the DAIS site, the IBEL portal, Claude's settings, the canvas).
- Update `wiki/design/screens/S36-design-system.md` where the build had to differ from it, and say why.

## Not known when this card was written
- How the live site looks today. The card was written from the code at bc26f66, not from a running hub.
- Whether the to-do items and the Trail already carry what lines 12 and 13 need. If not, those lines say what to add or show instead.
- How the pages look on `mcd_extension` and `temporal_dependency`; neither repository was read.
