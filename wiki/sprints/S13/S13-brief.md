---
type: task-card
owner_agent: lead
status: built, not yet QA-verified
sources:
  - "founder message in chat, 2026-11-11 16:06 KST: 'The map is not a map that is visible. Make an interactive map where I can actually click onto the RQs or hypothesis and check the progress of our MCD. … be an expert, just like apple app UI expert developer and change the overall UI to be much more clean and direct. Reference notion as well. … regarding the tree in the claims, make it so that the design adjusts its size. As of now, it is too small.'"
  - "../../design/screens/S13-clean-ui.md (designer agent's spec, status proposed)"
  - "code on branch s07-public-site: app/src/lemmata/web/{research.js, app.css}, app/src/lemmata/engine/{claims.py, api.py}"
last_reviewed: 2026-11-11
---
# S13 brief: clickable experiments map, clean UI, tree that resizes

## What was built
- **Experiments map** (default view; Table is the other tab). Left: our method, what it extends, the goal, and a bar of how many experiments are ahead of the base. Middle: one card per question or hypothesis with its own ahead/behind bar. Right: one pill per experiment (▲ ahead, ▼ behind, = level, · no comparison, ! to check). Click a question: its experiments light up and its table opens below. Click an experiment: its detail opens below.
- **Clean UI** from the designer's spec: tokens (hairlines, tints, 12/14/16/22/32 type, 8px grid, softer corners), buttons and chips as fills, cards without borders or side stripes, table rows with hairlines and hover, wash-coloured side panels, wider page column for visual pages, helper sentences cut or moved into tooltips.
- **Claims tree**: drawn at natural size or larger (never shrunk below it), fits the page width up to 1.6x, with − / Fit / + buttons and scrolling; larger nodes, labels at least 12px; nodes made from the map show the map's label (RQ1, E1) instead of "+1".

## Not done from the spec
- Not every copy cut in the spec's table was applied (Slack paragraph, some warning sentences). The map card is not yet a one-line bar.
- Hub pages (project list, account) were not restyled.

## Verified
- 152 unit tests pass; browser walk-through on the synthetic project with no page errors. Not checked on mcd_extension, on Safari, or by QA.
