---
type: task-card
owner_agent: pm
status: ready
sources: [wiki/presentations/deck-playbook.md, raw/decks/2026-11-03-1st-deck/, raw/market/2026-11-03-market-brief.md, raw/course/AAA639-syllabus-2026-fall.pdf, wiki/presentations/2nd/review-2026-11-03.md]
last_reviewed: 2026-11-03
---
# Task: 1차 발표를 30분 발표로 다듬기 + 2차·3차 실행 계획
- Goal: the 1st-deck snapshot (27 main slides) becomes a 30-minute 1차 presentation. Juhyeong's priorities: why he came up
  with the idea, that it is every researcher's problem, that it got too fast to track, why it must ship now, market and demand.
- Inputs: raw/decks/2026-11-03-1st-deck/ (start from it, keep its style), the market brief, the syllabus, the playbook.
- Audience / time: AAA639 class and instructor, 30 minutes. Slide count is free.
- Acceptance criteria:
  - wiki/presentations/1st-30min/brief.md: pain points with their cost, personas (user and payer), JTBD, current
    workarounds (git diff, notes, Makefile, DVC) and why they fail, why now, weak spots and answers. Sources on every claim.
  - outline.md: one sentence per slide with minutes per section adding to about 30.
  - A section "앞으로 어떻게 할지": 2차 (what is built, how alarm precision is measured on the 113 commits, how interviews
    and the survey are run) and 3차 (launch, pilot users, IR), with gates and dates from the syllabus. A plan, not results.
  - Interview guide and survey recruiting messages (Slack, KakaoTalk, email) for the change-tracking direction, because
    the old wiki/research/interviews/interview-template.md asks about the old positioning. Put them in
    wiki/presentations/1st-30min/recruiting/ and flag them for PM.
  - project/: deck.json + every new or changed slide in the deck format; untouched slides listed by id in outline.md.
  - Preview checked; export PPTX/PDF to wiki/presentations/1st-30min/export/ for Slack.
  - handoff.md with rubric scores and missing facts; a `done` report with the PDF link.
- Owner: deck-marketer · Reviewer: Juhyeong
- Done when: the files above exist, nothing is invented, and the done report is in the outbox.
