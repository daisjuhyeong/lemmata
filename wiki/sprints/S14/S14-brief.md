---
type: task-card
owner_agent: lead
status: built, not yet QA-verified
sources:
  - "https://nicholas.carlini.com/writing/2026/how-to-win-a-best-paper-award.html (the advice the page is built around: one core idea, kill weak projects, answer the sceptic, best-case conclusion first)"
  - "founder messages in chat, 2026-11-11 19:15 and 19:17 KST: completeness checklist 'Yes'; 'I like the idea of the should I continue view, where one page per project shows the three checkmarks'; best-case conclusion 'Yes'; confounds: 'Keep it and make it become a job for one's ai agent'; '30 days is good enough, although make an option for 1 week, 1 day view'"
  - "code on branch s07-public-site: app/src/lemmata/engine/{review.py, api.py, track.py, experiments.py}, app/src/lemmata/{mcp.py, server.py}, app/src/lemmata/web/{research.js, app.js, app.css}, app/tests/test_map.py"
last_reviewed: 2026-11-11
---
# S14 brief: Review page ("should I continue?")

## What was built
- **Three checks**, each one word plus one line: Is it moving (questions with a new result in the period), Is it ahead (experiments ahead of the base, or of the best other method), Is there a paper today (claims with a complete checklist). Clicking a check filters the questions to what produced it.
- **Period switch**: 30 days (default), 1 week, 1 day.
- **Checklist per question**, five items: more than one run, a baseline, an ablation or sensitivity study, paper table matches the files, confounds checked. The first four are rules. "Paper table" is not counted for an extension's question when the linked paper is the original.
- **Confounds as an agent job**: MCP tools `confound_brief` and `report_confounds`. Each reported confound must quote a real file line or it is dropped. The item goes back to "check again" when a newer result arrives. The researcher ticks confounds off as resolved, or marks "I checked it myself".
- **Hoped conclusion** (typed by the researcher) next to "Supported today" (claims whose checklist is complete; the rest listed struck through with what is missing).
- API: `GET /api/review?days=`, `POST /api/review`.

## Different from the sketch shown in chat
- "Supported today" lists whole claims. It does not strike individual words out of the hoped sentence; rules cannot map words to claims.
- "Behind since" is shown only when the comparison is with the best other method; with a base method the history of the base is not stored yet.

## Verified
- 153 unit tests pass; browser walk-through on the synthetic project. Not run on mcd_extension; no real agent has reported confounds; QA has not reviewed.
