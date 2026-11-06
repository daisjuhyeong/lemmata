---
type: handoff
owner_agent: web-eng-a
status: draft
sources:
  - "S06-brief.md (section B)"
  - "../../design/screens/s06-obsidian-redesign.md"
  - "../../architecture/data-model.md"
  - "handoff-web-eng-hub.md (section 2, hubControls)"
last_reviewed: 2026-11-06
---
# S06 handoff (web-eng A): Obsidian-style project UI

Branch `s06-obsidian-ui`. Python suite 126 OK. Files: `app/src/lemmata/web/{index.html,app.js,app.css}` rewritten (one `app.js`, because export inlines only that file; sections numbered at the top). `web/hub/` untouched. No backend change; LaTeX snippets use `/api/file`.

## Built
Item model derived in the browser (spec 1); left explorer (Changes, Paper, Experiments, Code, Checks, History, search); tabs with back/forward; Changes cards (Why? chain + diff in words, Looks fine / Needs fixing + note / Ignore, Undo, Mark everything as looked at); Item page, Evidence page, Checks (with Suggested links approvals), History; Graph (hand-written canvas + force sim, no Cytoscape: sized Items, status rings + glyph badges, labels placed greedily, filters, depth slider, hover/click, double-click to show files, list view, pinning); right sidebar (Rests on / Supports / local graph / recent changes / outline); palette Ctrl+P, switcher Ctrl+O; first-run explainer; status bar; export report; read-only snapshot verified (banner, buttons disabled).
Hub mode: all in one block `hubControls()` (section 2 of app.js): paper status in words, Connect paper repo dialog (`paper-source` github, owner/name or URL, optional folder, plain error mapping), zip upload only when source is zip, Sync now, back to Projects. No Overleaf anywhere. Not run against mock_hub (only single-project mode and export were driven).

## Verified (Playwright 1440x900)
Fresh sample and the real repo (code-only); all views, no console errors. Golden story reads: card "You changed configs/default.yaml (learning rate 3e-4 → 1e-3)" with "3 things may need a second look: Table 2, the run train_main, results/table2.csv (not regenerated yet)". Screenshots `app/docs/screens/s06-sample-*.png`, `s06-real-*.png`, `s06-export-readonly.png`. Real repo `.lemmata/` deleted afterwards.

## Deviations / for review
1. Code-only project (no paper): README rows become Items so the graph is not empty (spec says they appear only under Code).
2. Shared items default to hidden when there are more than 12 (real repo was a hairball); toggle in Filters.
3. Spec status rule makes Items with warning checks "Needs a second look" at state 0 (Section 4, Appendix B, Section 5, Section 2), so the count is 5 things, not 3 changes.
4. Not done: `strings.js` split (strings are in one `T` object plus inline), dark theme, saved graph positions only for pinned items, keyboard Tab order in graph is basic, 1280px auto-collapse only on first visit. `vendor/cytoscape.min.js` is no longer referenced by index.html (server still inlines it if the tag exists; harmless).
5. Banned-word test forced wording "Something broke on our side".
6. `app/tests/shots_s05.py` still targets old Overleaf DOM (obsolete, noted by web-eng B).

## Follow-ups (done)
- Right sidebar merges rows per item with joined relations ("contains it · refers to it").
- hubControls() driven against a real hub + fake GitHub: `app/tests/shots_s06_hubmode.py` (pair, create with own paper repo, status "Paper: GitHub repo ✓ synced just now", Connect paper repo… to folder `paper/` of the code repo, bad repo shows plain error, new paper commit + Sync now gives a Changes card). Screenshots `s06-hubmode-*.png`. Nothing broke. After switching source the card reads "history of your paper was rewritten" (engine's diverged event), accurate but may surprise.
- `shots_s05.py` deleted.

## QA fixes (D1-D8)
- **D1** `server.py export_html`: embedded snapshot JSON escapes `&`, `<`, `>`, U+2028/2029 as `\uXXXX` (not only `</`). Test in `test_server.py` asserts none of these characters appear raw.
- **D2 rule (one number everywhere)**: "things to look at" = number of changes (alarm groups) in which at least one affected file or item is still not looked at (triage state unreviewed, or changed again after a mark). Same value in the Changes badge, the status bar, the summary line ("N things still to look at") and the hub projects list (`hub/projects.py todo_changes`, test `test_todo_changes_rule`). Items flagged only by checks now read "A check found something here. See the check" (link to the Checks tab).
- **D3** single-project server sends a CSP (`default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'`); UI unaffected, test added.
- **D4** labels: kept for the always-set after a selection; a short form ("Figure 2") is used when the long one does not fit, with below/right/left/above placement and wider circle spacing. Re-shot at 1280x800 (`s06-sample-graph-1280.png`): every item named.
- **D5-D8** paths keep their case; raw diff headers hidden (a "⋯" marks a gap); "1 file", "1 place", "1 setting"; the mark is "Last looked at" everywhere, scans read "Files read 2 min ago", "checks" only means findings.
