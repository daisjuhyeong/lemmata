---
type: task-card
owner_agent: pm
status: draft
sources: ["../../product/demo-spec.md", "founder decision, 1st presentation, 2026-11-03"]
last_reviewed: 2026-11-04
---
# Task: S02-02 Server and UI
- Goal: Build `app/src/rmap/server.py` (stdlib `http.server`, JSON API over the engine) and `web/` (static HTML/JS/CSS, no npm build, no CDN) that shows the interactive graph, alarms, analyzer, triage, link approval, findings and HTML export.
- Inputs: [demo-spec](../../product/demo-spec.md); engine API schema from S02-01 (agree in the first day; until then code against the stories and a fixture JSON).
- Acceptance criteria:
  1. Server starts on 8765 or next free port, prints the URL, opens the browser unless `--no-open` (US-01.1, .2, .4). Works fully offline; all assets vendored or hand-written (US-01.3).
  2. Graph view: layered top-down, node click panel with file:line and neighbours, trace up/down highlighting, references toggle, repo label per node (US-02.1-.5).
  3. Checkpoint panel: set (with note), list, new checkpoint clears alarms (US-03).
  4. Alarm view: groups by cause, causing change shown, changed vs downstream distinguished, highlights in graph (US-04.1, .3, .4).
  5. Analyzer drawer opened only on click: chain and diff (US-05).
  6. Triage controls with note, persistence across restart, filters and counts (US-06).
  7. Proposed links dashed; Approve and Reject buttons; alarms refresh without page reload (US-07).
  8. Findings list with path:line, quoted line, link to node, triage; export a single offline HTML report (US-12.1, .3, .4).
  9. Wording: UI strings contain none of the banned words in US-12.2.
  10. Presenter walkthrough in the demo-spec can be followed click by click on the sample with every labelled control present and named as in the script.
- Owner: web-eng
- Reviewer (QA): qa (S02-03)
- Budget (time/usage): PM proposal, 2 working days; no paid services.
- Done when: criteria met on a feature branch; QA completes the full walkthrough in under 5 minutes in a clean browser profile with network off; handoff note filled. Merge decided by Juhyeong.

## Handoff note
- What changed:
- Open questions:
- Links:
