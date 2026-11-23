---
type: task
owner_agent: lead
status: open, not started
sources:
  - "founder answer in chat, 2026-11-23, to open question 2 of S36-03-handoff.md ('D7 and D8 (narrow-window overlaps from before S36): a small follow-up card?'): 'sure'"
  - "qa-S36-03-browser.md (defects D7 and D8, seen at 420px and already present at bc26f66) ; screenshots/after-thesis-light-420.png"
  - "../S31/S31-01-handoff.md (the founder asked for Settings at the bottom left on 2026-11-19; windows without a sidebar got a fixed button there)"
  - "code at 570c471: app/src/lemmata/web/app.js:2068 (#setfab) and :2001 (BENCH_PAGES, the VS Code tab's pages) ; app.css:849-853 (no sidebar below 1000px), :1062-1067 (#setfab), :737-743 (the experiment table at 700px and below) ; research.js:524-533 (rxGapBar) and :891-895 (the claim head on Thesis)"
last_reviewed: 2026-11-23
---
# S36-04 task card: two narrow-window overlaps (D7, D8)

Owner: CTO, who assigns the build (web-eng). Reviewer: QA. Size: small; CSS and a few lines of JS, no engine change.
Branch: `s36-04-narrow`, from the head of `next`; onto `next` after its tests pass. Nothing goes to main without Juhyeong.

## Why
The S36-03 browser check found two overlaps at 420px. Both were already there at `bc26f66`, before S36, so S36-03 left them
([qa-S36-03-browser.md](qa-S36-03-browser.md), D7 and D8). The founder agreed to a small card for them (chat, 2026-11-23: "sure").

| # | What the check saw | Cause in the code (at `570c471`) |
|---|---|---|
| D7 | At 420px the floating "Settings" button covers content on every page | Below 1000px the sidebar is hidden (`app.css:849–853`), and `#setfab` (`app.js:2068`) is `position:fixed` at the bottom left (`app.css:1064–1067`), drawn on top of whatever scrolls past. `#status` is padded so the end of the page clears it, but rows in the middle pass under it. (qa's report names `#sd-settings`; that is the sidebar's item, hidden at this width) |
| D8a | In Thesis's experiment tables, "+5" and "+6" overlap the dates "9 Oct" and "12 Oct" | At 700px and below, the table's third column is 96px (`app.css:740`), but `rxGapBar` draws a fixed 132px SVG (`research.js:527`) with the label to the right of the bar, so it runs about 36px into the "Last" column |
| D8b | Claim titles in the same tables wrap one word per line | The claim head `.rx-x-h` (`research.js:892–895`) is one flex row: the claim's label, its state, the text, the link bar and the experiment count. At 420px the fixed parts leave the text about 100px |

Screenshot: [after-thesis-light-420.png](screenshots/after-thesis-light-420.png). It is a full-page capture, so the fixed
button is drawn where the first screen ended, in the middle of the page. In a real window it sits at the bottom left of the screen.

## Acceptance
| # | What | Done when |
|---|---|---|
| 1 | Settings covers nothing | Below 1000px, Settings stays at the bottom left and one click away on every page, as the founder asked in S31. It is no longer drawn on top of the page's text. The CTO's suggestion: a full-width strip at the bottom of the window, with a `--bg` background, a `--border` hairline on top and the button at its left, and the page padded by the strip's height. Text may pass out of view under the strip, as under any bar, but no row is left partly covered by a button. Shown in window screenshots (not full-page) at 760 and 420px, light and dark, on Home, Thesis, Setup, Review, Trail and Settings, at the top, middle and end of each page. If web-eng finds a better way that passes the same check, the handoff says why |
| 2 | The gap bar fits its column | At 1360, 760 and 420px the bar and its "+5" label stay inside the "Ours vs best other" cell, measured in the browser: their box does not meet the next cell's box. The number is not cut and not replaced with "…" (S36: no information is cut). Above 700px it looks as it does now |
| 3 | Claim titles read as a sentence | At 420px the claim text on Thesis gets at least 300px of width (for example on its own line under the label, state and count), and "2 experiments" stays on one line. At 1360px the head looks as it does now |
| 4 | The VS Code tab | The tab shows Thesis (`BENCH_PAGES`, S35), so lines 2 and 3 reach it: check them with `html.embed` at 420px. Line 1 does not (the tab draws no `#setfab`). `vscode/` stays unchanged, or its suites are run |
| 5 | Nothing else breaks | The Python suite passes, including `test_s36_ui.py` (sand only for "your turn") and the guard against window-width `@media` in `app.css`. JavaScriptCore parses `app.js` and `research.js`. No new console error, and no page scrolls sideways at 1360, 760 or 420px |

## How to hand off
`S36-04-handoff.md` with before and after window screenshots at 420px, light and dark, for lines 1 to 3, plus what was not
checked and open questions. Update `wiki/index.md` and `wiki/log.md`. Push to `s36-04-narrow`, then the same commit to `next`.

## Not known when this card was written
- **The browser check needs Playwright again.** The S36-03 copy was removed (by the founder, 2026-11-23). Installing it in a
  temporary folder outside the repository was approved for S36-03; this card assumes the same approval holds, and the permission
  check may ask again. The folder is removed afterwards.
- **Whether other pages have the same problem at 420px.** The S36-03 check opened only the five main pages and Settings. `rxGapBar`
  is also drawn through `research.js:546–547`, for projects that extend a base method. qa opens Baselines and Key numbers at
  420px and lists what it sees; fixing other pages is outside this card unless the cause is the same `rxGapBar`.
