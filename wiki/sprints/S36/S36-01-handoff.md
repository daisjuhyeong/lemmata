---
type: handoff
owner_agent: lead
status: phase 1 built; QA passed by reading the code and running the Python suite; browser and extension checks not run (founder's decision)
sources:
  - "S36-01-task.md (acceptance lines 1-9) ; ../../design/screens/S36-design-system.md ; ../../decisions/ADR-012-design-system-and-your-turn.md"
  - "code on branch s36-design-system: app/src/lemmata/web/{tokens.css,app.css,app.js,research.js}, desktop/launcher/tokens.css, app/tests/test_s36_ui.py"
  - "qa-S36-01-phase1.md (QA report for this phase)"
  - "founder answer in chat, 2026-11-22: 'Skip browser and extension checks' (this Mac has no scriptable browser and no node; installing Playwright was refused by the permission check)"
  - "test run on 2026-11-22 on the founder's Mac: Python 241 ran, OK, 2 skipped"
last_reviewed: 2026-11-22
---
# S36-01 handoff: phase 1, tokens and parts (acceptance lines 1 to 9)

## What changed for the researcher
- **Sand means your turn.** Primary buttons are sand (`--highlight`) with dark text (`--on-highlight`) and a 1px
  `--highlight-edge` edge, and only 10 are left: the Confirm, Yes and Accept buttons that settle something waiting on the
  researcher. The other 27 are plain buttons.
- **State tags are readable.** `.chip` text is weight 600, 13px, `--text-secondary`. The dot is 8px. The default,
  hypothesis, exploration, ignored and plain dots are a hollow ring (1px `--muted`).
- **Nothing small or pale.** `--fs-11`, `--fs-12` and `--fs-tag` are 13px, and literal sizes under 13px use `var(--fs-tag)`.
  The few exceptions are glyphs, listed below. `--muted-light` is no longer used as a text colour (`#status`, `.sg.ok` and `.hf-tag` use `--muted`).
- **Control edges.** Plain `.btn`, `.chip-btn`, text inputs, selects and textareas have a 1px `--muted` edge and no fill at rest.
  Hairlines between rows and under headings are unchanged.
- **Darker stale colour.** In both themes the stale dot (`--warning`, `#B5823A`) is now clearly darker than sand.

## How it is built
| Line | Where | What |
|---|---|---|
| 1 | `web/tokens.css`, `desktop/launcher/tokens.css` (byte-identical) | `:root`: `--muted #646F68`, `--warning #B5823A`, `--fs-tag 13px`, new `--highlight-edge #8A7431` and `--on-highlight #1A1A1A`. Dark: `--warning #B5823A`, `--highlight-edge #c9b06a`, `--on-highlight #1A1A1A`. Two comments rewritten (`--highlight`, `--muted-light`). No renames |
| 2 | `app/tests/test_s36_ui.py` (7 tests) | WCAG contrast from `tokens.css` in both themes (the dark block inherits from `:root`). Allow-list for `var(--highlight)`, with each allowed rule checked for `--highlight-edge`. Floor on literal sizes under 13px in `app.css`, outside the glyph exceptions. No hex colour in `app.css`, `app.js` or `research.js`. Against bc26f66, 5 of the 7 tests fail |
| 3 | `app.css` | `var(--highlight)` appears only in `.btn.primary`, `.btn.primary:hover`, `.rdot.d-highlight`, `.chip.proposed::before` and `.rxt-li.att > .rxt-row .rxt-dot`, each with a `--highlight-edge` border |
| 4 | `app.js`, `research.js`, `app.css:610–613` | See the table below |
| 5 | `app.css` `.chip` rules (around :586–598) | Weight 600, `--fs-tag`, `--text-secondary`, 8px dot, hollow ring. The state word was already drawn beside every chip dot and still is |
| 6 | `app.css:2` and 19 rules | `--fs-11` and `--fs-12` are 13px. Two SVG chart labels (`.rx-gap .gl`, `.rx-hist .ax`, which were `font:10px`) also became `--fs-tag`, because they carry numbers |
| 7 | `app.css` input, `.btn` and `.chip-btn` rules, `.rx-pl-f` inputs | 1px `--muted` edge, `transparent` at rest, hover `--surface-hover` |
| 9 | `app.css:613–616`, scoped to `html.embed` | The VS Code tab keeps its earlier look. See "Departures" |

### The primary buttons (line 4): 37 sites
The card said 13. The real count at bc26f66 was 37: 27 set `btn primary` in the class string (some of them only under a
condition), and 10 are dialog buttons with `primary: true`, drawn by `modal()` (`app.js:192`).

**Kept (10)**: each settles something waiting on the researcher.
| Site | Label | Reason |
|---|---|---|
| app.js:1637 | Yes, link them | settles a proposed link |
| research.js:159 | ✓ Yes | a suggested link waiting on the researcher |
| research.js:208 | Confirm | confirms a claim |
| research.js:712 | Confirm | confirms the proposed map |
| research.js:2067 | Accept | accepts a proposed change to a hypothesis |
| research.js:2075 | Confirm | confirms the problem |
| research.js:2122 | Confirm | confirms a hypothesis |
| research.js:2233 | Confirm | confirms a proposed baseline |
| research.js:2324 | Confirm | confirms a proposed baseline name (one per row, in a list of waiting items) |
| research.js:2359 | Confirm all | confirms the whole proposal |

**Made plain (27)**: they start, save, dismiss or copy something, and nothing waits on them.
| Site | Label | Reason |
|---|---|---|
| app.js:299 (dialog) | Connect | starts an action; nothing waits |
| app.js:371 (dialog) | Close | dismisses |
| app.js:794 (dialog) | Close | dismisses |
| app.js:815 (dialog) | Mark everything as looked at | the researcher's own action |
| app.js:1269 | Save | saves a note |
| app.js:1281 | Start tracking from now | the researcher's own action |
| app.js:2137 | Try again | recovery |
| app.js:2296 | Next | tutorial navigation |
| app.js:2296 | Show me what changed | tutorial navigation |
| research.js:120 (dialog) | Close | dismisses |
| research.js:186 (dialog) | Save | an edit |
| research.js:703 | Copy prompt for Claude Code | helper |
| research.js:975 | Copy prompt for Claude Code | helper (was primary under a condition) |
| research.js:988 | Plan with Claude Code | helper (was primary under a condition) |
| research.js:1047 | Copy confound check for Claude Code | helper |
| research.js:1067 | Add | the researcher's own input |
| research.js:1172 | Ask | the researcher's own question |
| research.js:1805 | Add these N dates | the researcher's own action |
| research.js:2019 (dialog) | Save | an edit |
| research.js:2029 (dialog) | Save | an edit |
| research.js:2036 (dialog) | Save | an edit |
| research.js:2043 (dialog) | Close | dismisses |
| research.js:2238 | Copy prompt for Claude Code | helper |
| research.js:2314 | Save | an edit |
| research.js:2338 | Edit / Fill in | an edit |
| research.js:2475 | Ask | the researcher's own question |
| research.js:2479 | Copy prompt for Claude Code | helper |

"No page shows more than one sand button outside a list of waiting items": the problem's Confirm (:2075) and a hypothesis's
Confirm (:2122) can appear on the same page. Both were treated as part of the list of items waiting on the researcher.

### Sizes left under 13px (line 6): text that carries no information
`.rxt-caret`, `.rh .caret` (open and close carets) and `.rx-m-g` (`app.css:403`, `:454`; the ahead and behind glyph on map
nodes). These are glyphs, not words. A borderline case is `.rx-chk .cg`: a one-character verdict glyph in a table cell,
whose meaning sits in the cell's title and the legend. It is listed as an open question below.

## Departures from the card, and why
1. **The `.btn` rule that takes effect.** `app.css` stacks three `.btn` layers (around :23, :412 and :610). Only the last
   one takes effect, and at bc26f66 it drew `.btn.primary` as an `--accent-dark` outline, not a fill in `--text`. The sand rule is in that last layer.
   The dead primary declarations in the earlier layers were removed. The pressed toggle (`.btn[aria-pressed="true"]`) looks as it did before.
2. **`.hf-branch.warn::before` is `--warning`, not sand.** It means "the tracked branch has newer commits" (research.js:2148),
   which is "look here", not "waits for the researcher". The design page (§5) foresees this case. The card listed it as a sand dot.
3. **The tree's "waiting node" is the `.rxt-li.att` dot.** The card listed them as two items; they are one rule.
4. **The counts.** The card said 13 primary sites; there were 37. It said 114 uses of `--fs-11`/`--fs-12`; there are 118.
   Its 19 literal sizes are 19 rules holding 24 declarations.
5. **The VS Code tab (line 9) is held in `app.css`, not `vscode/`.** The tab loads the hub's `app.css`, then `vscode/media/vscode.css`.
   Without a fix, the primary button would have been sand with the editor's link-blue text, and chips, edges and hover would have changed too.
   Rules scoped to `html.embed` (`app.css:613–616`) keep the tab as it was in S35: primary transparent with its hover fill,
   `--border-strong` edges, an `--accent-dark` edge on pressed toggles, and chips at weight 400. With this approach the extension's files do not change, so its version stays
   0.8.0. A new `.vsix` would have needed node, which this Mac lacks. The hollow ring reaches the tab (`--muted` maps to the editor's description colour).

## Verified
- **Python:** 241 ran, OK, 2 skipped. Command: `PYTHONPATH=app/src:<pytest stub> app/.venv/bin/python -m unittest discover -s app/tests -p 'test_*.py'`,
  run outside the sandbox (which blocks local ports). `app/.venv` has no pytest, and `test_map.py` imports it only for `pytest.raises`.
  A 9-line stand-in for `pytest.raises`, kept outside the repo, lets `test_map`, `test_baselines`, `test_bench` and `test_texout`
  load. Without it those four modules error on import, on this tree and on bc26f66 alike. The one pytest-style function in `test_map`
  (it takes `tmp_path`) is not collected by unittest.
- **QA by reading the code:** lines 1–7 and the cascade. See [qa-S36-01-phase1.md](qa-S36-01-phase1.md). QA first failed line 7
  on `.rx-pl-f` inputs, which are now fixed, and raised the VS Code tab changes, now held as in departure 5.

## Not checked
- **Line 8 and every screenshot** (later done in [S36-03](S36-03-handoff.md): line 8 passed on `test_map`). This Mac has no browser that can be driven from a script. Installing Playwright and
  Chromium into a temporary folder was refused by the permission check, and the founder then chose to skip browser checks. So there are **no before and after
  screenshots** in `screenshots/`, and nothing was seen at 1360, 760 or 420px in light or dark. The main risk: with 12px text now
  13px, rows that fitted on one line may wrap, mostly in the Setup board, the tree labels and the calendar's `.tm-due`.
- **Line 9's suites.** There is no node, so the extension's unit, integration and browser suites did not run. Its files did not change.
- **The hub's own pages.** `hub/hub.css` has its own `.btn.primary` rules (:31, :152), and `hub/hub.js` has about 10 `btn primary`
  sites. They are outside the card and were left as they are.
- **Inline styles in JS.** The allow-list test reads `app.css` only.

## Open questions for Juhyeong
1. Should screenshots and the browser check be run before this goes from `next` to main? They need a machine with Chromium,
   or approval to install Playwright in a temporary folder here.
2. `.rx-chk .cg` (a one-character verdict glyph in table cells, under 13px): enlarge it, or add the word beside it in phase 2?
3. Can the problem's Confirm and a hypothesis's Confirm both be sand on the same page, or should the problem's be plain?

## References named
- None borrowed in this phase. The values come from the design page, which credits the IDEAiPlus and Eric Park videos (rules first; one colour for the main action).
