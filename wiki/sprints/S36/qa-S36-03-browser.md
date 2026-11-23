---
type: qa-report
owner_agent: qa
status: re-check PASS (D1-D6, D9, D10, copy, R1, R2 fixed; D7-D8 left as before S36); mcd_extension and the hub title case not checked
sources:
  - "S36-03-task.md (line 4 browser check, line 5 defects) ; S36-01-task.md (lines 8, 12, 15, 16, 17)"
  - "before: git archive of bc26f66 (lead's scratchpad, before-bc26f66/app/src) ; after: working tree of s36-design-system at a349a64 + uncommitted S36-03 lines 1 and 3 (app.js, research.js, test_s36_ui.py), 2026-11-23"
  - "Playwright 1.60 + Chromium headless, installed by the lead in a session scratchpad outside the repo"
  - "../../../app/src/lemmata/web/research.js:841-849 (rxThesisAnswer), :333-335 (tree 'your turn'), ../../../app/src/lemmata/web/app.css:1103 (.hm-line), :1133 (.rx-treeframe)"
last_reviewed: 2026-11-23
---
# QA S36-03: browser check, before and after

## How it was run
- The `test_map` method-paper project was built separately by each code version's own `make_project`, then scanned and its map
  confirmed. Each version served it on a local port with `lemmata serve --port 0 --offline` from its own `app/src`. The import
  path was checked each run; the before run printed `before-bc26f66/app/src/lemmata/__init__.py`.
- Both runs used the same settings: viewport height 900, `device_scale_factor` 1, theme set through local storage, the
  first-visit intro marked as seen, and a fresh browser context for each shot. Before each shot the script deletes
  `home_seen.json`, so Home is always shown as a first visit.
- Scripts (QA's session scratchpad, not in the repo): `s36_capture.py`, `s36_build_project.py` and `s36_measure.py` in
  `/private/tmp/claude-501/-Users-dais-juhyeong-work-lemmata/8cd02ddb-5955-4d4d-a194-8e45af4bf615/scratchpad/`.
- Console errors: **0** in every visit, before and after (all pages × widths × themes, plus the measurement visits).

## Before / after at 1360px
| Page | Before light | After light | Before dark | After dark | After 760 / 420 (light) |
|---|---|---|---|---|---|
| Home | [b](screenshots/before-home-light.png) | [a](screenshots/after-home-light.png) | [b](screenshots/before-home-dark.png) | [a](screenshots/after-home-dark.png) | [760](screenshots/after-home-light-760.png) · [420](screenshots/after-home-light-420.png) |
| Thesis | [b](screenshots/before-thesis-light.png) | [a](screenshots/after-thesis-light.png) | [b](screenshots/before-thesis-dark.png) | [a](screenshots/after-thesis-dark.png) | [760](screenshots/after-thesis-light-760.png) · [420](screenshots/after-thesis-light-420.png) |
| Setup | [b](screenshots/before-setup-light.png) | [a](screenshots/after-setup-light.png) | [b](screenshots/before-setup-dark.png) | [a](screenshots/after-setup-dark.png) | [760](screenshots/after-setup-light-760.png) · [420](screenshots/after-setup-light-420.png) (both cut at 4000px) |
| Review | [b](screenshots/before-review-light.png) | [a](screenshots/after-review-light.png) | [b](screenshots/before-review-dark.png) | [a](screenshots/after-review-dark.png) | [760](screenshots/after-review-light-760.png) · [420](screenshots/after-review-light-420.png) |
| Trail | [b](screenshots/before-trail-light.png) | [a](screenshots/after-trail-light.png) | [b](screenshots/before-trail-dark.png) | [a](screenshots/after-trail-dark.png) | [760](screenshots/after-trail-light-760.png) · [420](screenshots/after-trail-light-420.png) |

Dark versions of the 760 and 420 shots are in the same folder (`after-<page>-dark-760.png`, `-420.png`).
Extra shots: [Settings with "What Lemmata keeps about you"](screenshots/after-settings-light.png) and
[Review with the mismatch opened](screenshots/after-review-open-light.png).

## Measurements (after, light)
| Check | Result |
|---|---|
| Sideways scroll (`scrollWidth > innerWidth`), 5 pages × 1360 / 760 / 420 | none, before or after (Setup's board and Thesis's tree scroll inside their own frames) |
| Home, Needs you rows (`.hm-row .hm-line`) at 1280 | 1 row; height 24 = line height, does not wrap, not cut (740px fits in 740px) |
| Review rows at 1280 | the mismatch sentence fits (536px); **the To confirm row is cut with "…"** (text 721px wide, box 460px) |
| Thesis tree at 1280 / 1000 / 760: overlaps between the boxes of labels, state words, counts and dots | **0 overlaps** (15 boxes, 4 rows). Labels are not cut by CSS; the "…" comes from `rxWords` (6 words) |
| Tree frame below 1100px | `.rx-treeframe` has `overflow-x:auto` at 1000 and 760 (not at 1280). On test_map the tree fits (952 / 712px), so nothing scrolls and the page does not scroll sideways. At 420 the tree scrolls inside the frame |
| Opened mismatch (Review) | compared methods, then MCD, then "Difference from the best other"; the mismatched cell is outlined; "Open it where it lives" |
| Settings | the sentence about what Lemmata keeps is shown under How Lemmata works |

## Defects (after)
| # | Sev. | Page | What | Where |
|---|---|---|---|---|
| D1 | **medium** | Thesis | The core message node has the sand your-turn dot and the words "your turn" (its state is `proposed`). Yet the answer line says "none waiting for you", Home's Needs you does not list it, and the sidebar does not count it. Either it waits for the researcher, and then Needs you, the answer line and the Home count should include it; or it does not, and it should not be sand. | `research.js:333` (`att`), `:848` (counts claims only through `cc.proposed`) |
| D2 | **medium** | Review, Home at 420 | Rows are cut with "…", and the cut can hide the point of the row. At 420 the mismatch sentence becomes "the paper says 44.0, the file sa…", so the number from the file is hidden (S36-01 line 16: both sides in one sentence). The Needs you / To confirm question is hidden at 420 on both pages, and on Review even at 1280/1360. | `.hm-line` (`app.css:1103`: `white-space:nowrap; text-overflow:ellipsis`); Review's narrower column |
| D3 | low | Thesis | The answer line puts a lowercase word at the start of a sentence: "…are backed. none stale, 1 in mismatch…". | `research.js:846` (the zero phrase "none stale" comes right after ". ") |
| D4 | low | Thesis | The thesis is shown twice: the tree root, then the older "Thesis main.tex:5 / 3 claims / 4 experiment links / Gaps" block right under it. There are two "Tree" links. | `pageExperiments` below `rxThesisTree` |
| D5 | low | all five | The content column does not line up across pages: Home, Thesis and Setup start at x=254 (full width), Review and Trail at x=316 (about 752px wide). The page heads move when you switch pages. | page wrappers of Review and Trail |
| D6 | low | Setup | Explanation that is always shown is still there by default: "Click a card to light its path to the thesis. A dashed card is not connected yet." under the board, and "You check. Lemmata cannot read this from the files." on every experiment (S36-01 line 10 includes Setup). | Setup board caption, the experiment checklist |
| D7 | low (already in before) | all at 420 | The floating narrow-window "Settings" button covers content (e.g. Thesis "0 claims with no experiment", the Trail rows). | `#sd-settings` in the narrow layout |
| D8 | low (already in before) | Thesis at 420 | In the experiment tables the "+5" / "+6" labels overlap "9 Oct" / "12 Oct". Claim titles wrap one word per line. | the claim tables in Thesis's Outline |
| D9 | low | Thesis at 420 | The core message is cut at the frame edge with no "…" and no sign that it scrolls ("Drift-aware detection with Monte Carlo"). Setup shows "Scroll sideways to see the whole map →"; Thesis has no such hint. | `.rx-treeframe` at 420 (`min-width:620px`) |
| D10 | low | Settings | Step [3] of How Lemmata works still says "Mark everything as looked at", which no page shows any more. | Settings, How Lemmata works |

Not seen: sand used for anything other than your turn, apart from D1. The inconclusive bars use the warning colour, which
can be told apart from sand. Also not seen: broken tree lines (the Thesis tree and the Setup board keep their lines at
all widths), unreadable text in dark, a page without a page head.

## Copy notes and questions
- "Section 2 mentions dropout ?": the "?" stands for a missing value in the paper and reads like a typo. It should say so in words.
- Review says "5 checks found nothing", and the sidebar says Checks 7. They may count different things; if so, say what each counts.
- The page footer "Last looked at: not yet" sits under "Since you last looked" (a first visit). These are two different
  records with nearly the same name.
- Shots depend on visit history: a second visit to Home shows "Nothing changed since you last looked". This is expected
  from S36-02. The script deletes `home_seen.json` before each shot so both themes show the same state.

## Acceptance
- **S36-01 line 8: passed on test_map.** No page scrolls sideways at 1360/760/420 in either version. The Setup board and the
  claims tree keep their lines.
- **S36-01 line 15: partly checked.** On test_map: no overlaps at 1280; the frame scrolls by itself below 1100px and the page
  does not. **`mcd_extension` and `temporal_dependency` were not checked.** The permission check denied the step that would
  serve a temporary project pointing read-only at `~/mcd_extension`, and QA did not try another way.
  `after-thesis-mcd-1280-light.png` does not exist.
- **S36-01 line 12 (one sentence that does not wrap at 1280): passed on Home.** On Review the To confirm row is cut, see D2.
- Merge: D1 and D2 are medium. QA recommends fixing them, or listing them with a reason in S36-03-handoff.md (S36-03
  line 5), before `next` goes to main.

## Not done
- The Playwright folder is still in the lead's scratchpad. S36-03 line 4 says to remove it after the after run; the lead
  owns it.
- The screenshots are not committed.

## Re-check (2026-11-23, after web-eng's fixes, uncommitted on `s36-design-system` over a349a64)
How: the after set was captured again into a fresh project (`proj-after2`), and every `after-*.png` was overwritten (1360, 760
and 420; light and dark). Settings and the opened mismatch were retaken. The checks below were measured with a new script,
`s36_recheck.py`, in the same scratchpad as the others. `app/tests/test_map.py` changed only in an assertion, so the
fixture is the same as before. QA looked at the 1360 shots in both themes and at the 760 and 420 shots of Thesis and Review.

| # | Check | Result | Evidence |
|---|---|---|---|
| D1 | The drafted core message is a Needs you row with Confirm; Home, the sidebar and Thesis count it; Confirm removes it | **PASS** | Row "Confirm the core message: Drift-aware detection with Monte Carlo Dropout" with Confirm on Home and in Review's To confirm. Home's answer line said "2 items wait for you", the sidebar badge 2, Thesis "1 waiting for you". After clicking Confirm: the row is gone, Home says 1 and the sidebar 1, Thesis "none waiting for you". The tree node's classes went from `att draft` to `st-partial`, its state from "your turn" to "being tested", its fill from `#dac88e` (sand) to `rgb(167,193,168)` |
| D2 | No information row is cut with "…"; at 1280 each sentence fits on one line; at 420 rows wrap and can be read in full | **PASS** | `.hm-line` no longer cuts with an ellipsis. At 1280, every visible row is 1 line with nothing overflowing (text width / column width): Needs you 466/740 and 425/740; mismatch 333/816; To confirm 466/740 and 425/740. At 420 they wrap to 2–3 lines with nothing overflowing; the mismatch shows "…the file says 46.00." in full |
| D3 | The answer line starts its sentence with a capital | **PASS** | "2 of 3 claims are backed. None stale, 1 in mismatch, …" |
| D4 | The thesis is not shown twice | **PASS** | The block under the tree keeps only its counts (no `.rx-th-t` title); there is one "Tree" link (the view switch) |
| D5 | Same left edge and width on all five pages | **PASS** | Page head at x=254, width 1052 on Home, Thesis, Setup, Review and Trail (`#page.wide` at x=230, width 1100) |
| D6 | Setup's two explanations sit behind "?" | **PASS** | "Click a card. (?)" under the board; each checklist says only "You check." and has one "?" (4 on the page); "cannot read this" is not shown by default |
| D9 | The tree shows a scroll hint where it scrolls | **PASS, with R1** | At 420 the frame scrolls and the hint "Scroll sideways to see the whole tree →" is shown. At 1280 and 1000 there is no hint |
| D10 | How Lemmata works, step 3 | **PASS** | It names Checks, Home, Review and the Checkpoint; "Mark everything as looked at" is gone |
| Copy | "with no value" / "things were checked and are fine" / "Checkpoint: none yet" | **PASS** | Checks: "…mentions dropout with no value…"; Needs you: "Section 2's dropout has no value; config.yaml sets 0.2. Same setting?"; Review: "5 things were checked and are fine."; footer: "Checkpoint: none yet" |
| Title | The local server's title goes to Home | **PASS** | From Thesis, clicking `#bt-home` opens Home ("What needs you today?"), the URL stays `/`, and `title` is "Home". **The hub case (title goes to `/`, "Your projects") cannot be run here**: there is no hub on this machine. Only the code was read (`titleGoesToProjects`) |
| D7, D8 | Floating Settings button at 420; table labels at 420 | not fixed, as agreed | already present before S36 (unchanged) |
| — | Console errors | **PASS** | 0 in every visit (capture and re-check) |
| — | Sideways scroll, 5 pages × 1360/760/420 | **PASS** | none |
| — | Tree overlaps at 1280/1000/760/420 | **PASS** | 0 of 15 boxes overlap |
| — | Sand only for your turn | **PASS** | Sand appears only on the Home dot, the your-turn dots, the Confirm buttons, and the drafted core message |

New, low:
- **R1 (low).** At 760 the tree hint "Scroll sideways to see the whole tree →" is shown, yet the frame does not scroll (the
  tree fits in 712px). The hint is tied to the window width (`@container app (max-width:760px)`), not to whether the tree
  actually overflows. [after-thesis-light-760.png](screenshots/after-thesis-light-760.png)
- **R2 (low).** On Setup, a checklist row whose reason is specific now reads only "You check.", and the reason moved behind
  "?". Example: Compute cost, "The numbers in the paper match the result files — You check." The reason "No paper table is
  linked to it" is information about this experiment, not standing explanation. Suggest keeping such a reason on the row.

**R1 and R2 re-check (2026-11-23, research.js:853-856 and :1537).** after-thesis-* and after-setup-* were captured again
into a fresh project (`proj-after3`), at 1360/760/420 in light and dark. They were measured with `s36_r1r2.py` (same scratchpad).
- **R1: PASS.** The tree hint now follows whether the frame overflows: hidden at 1360, 1280, 1000 and 760 (frame 1052, 1032, 952
  and 712px, nothing to scroll); shown at 420 (frame content 620px in 388px).
- **R2: PASS.** Compute cost reads "The numbers in the paper match the result files — You check. No paper table is linked to it."
  Rows with only the general reason keep "You check." and a "?" (3 on the page).
- Thesis and Setup: 0 console errors; no sideways scroll at 1360/760/420.
- QA looked at Thesis 760 light, Thesis 420 dark and Setup 1360 dark: they match the final code.

Not checked: mcd_extension and temporal_dependency (see above); the hub title case; the extension suites.

**Verdict: PASS.** D1–D6, D9, D10 and the copy fixes hold in the browser. D7 and D8 are left as agreed (already present
before S36). R1 and R2 are low and do not block. Nothing here blocks the merge to `next`; main still needs Juhyeong.
