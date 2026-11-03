---
type: protocol
owner_agent: deck-marketer
status: draft
sources: [raw/decks/2026-11-03-1st-deck/, raw/market/2026-11-03-market-brief.md, raw/course/AAA639-syllabus-2026-fall.pdf]
last_reviewed: 2026-11-03
---
# Deck playbook (deck-marketer)

What Juhyeong asked for while the 1st deck was built (2026-11-02/03), turned into rules.
Reference deck: `raw/decks/2026-11-03-1st-deck/` (27 main slides). Published copy: https://claude.ai/artifact/W2Lj1UFvUe67Rn1XUviqUb

## 0. Which presentation is it? (syllabus, raw/course/AAA639-syllabus-2026-fall.pdf)
| Deck | Week | Syllabus title | Spend most time on | Rubric items that weigh most | Appendix |
| --- | --- | --- | --- | --- | --- |
| 1차 | 5 | 문제 정의 & 기획서 | §1 story steps 1–5 (founder story, commonness, speed, why now, market and demand) | 1–4 | sources |
| 2차 | 10 | 디자인 & 서비스 개발 (weeks 6–9: 브랜딩/UI, UI 고도화, 개발 환경/백엔드, 서비스 통합) | 02–04: real screens, what was built, how agents built it, measured results | 5–8, plus evidence of results | 1차's market slides |
| 3차 | 15–16 | 서비스 런칭 & IR (weeks 11–14: 사용자 테스트, 비즈니스 모델, 피치 덱) | traction, business model, lean canvas, market and competitor analysis, the ask | 2–4 and 6 | build details |

Grading (syllabus): problem definition 10, solution design 30, presentation materials and delivery 50.

**Current focus (Juhyeong, 2026-11-03): only the 1차 presentation matters now, planned as a 30-minute talk.** Slide count
is not a constraint; depth is. Inside the 1차 deck, 2차 and 3차 appear only as a clear plan of *how* they will be done
(what gets built, measured and shown, with gates and dates), not as drafted decks.

## 1. Story (the order Juhyeong wants for 1차; reuse steps 1–3 as a 1-slide recap in later decks)
1. **Why I came up with this.** A concrete moment from his own research, in his words (e.g. 113 commits in 2 weeks with
   AI agents, and he could not say which figure was current). Then one real finding on his own paper.
2. **It is everyone's problem.** Global numbers (researchers, AI use, multinational submissions), not one lab.
3. **It got too fast to track.** Submission growth, verification falling behind, AI cannot check itself.
4. **Why now / why urgent.** A dated timeline; what changed in the last 12 months; what waiting a year costs.
5. **Market and demand.** Demand evidence (policy, penalties, usage of existing tools), size (TAM/SAM/SOM labelled as
   estimates), who pays how much, competition matrix, positioning, entry plan.
6. Social impact, then solution, product screens, design, development, service, business model, validation plan,
   risks, ask.

Course AAA639 requires four headings in this order: 01 문제 정의와 사회적 영향 · 02 AI 디자인(브랜딩 & UI) ·
03 AI 코딩(개발 환경과 백엔드) · 04 AI 코딩(서비스 통합). Put a 목차 slide after the cover with slide ranges.
Do not hide required content in the appendix; the appendix is only for Q&A material (sources, long tables).

## 2. Marketing checklist (fill brief.md before slides)
- Pain: trigger moment, cost (time, rejection, reputation), current workaround, why the workaround fails.
- Persona: role, field, stage, tools they already use (GitHub, Overleaf, W&B, Claude Code...).
- Job to be done, in one sentence the user would say.
- Who uses vs who pays (author vs lab/PI vs institution vs conference). Price anchors with sources.
- Why now: dated events only.
- Positioning: one line, then the 2–3 places we win and the places we do not.
- The weak spot (e.g. small author-paid market, free conference tool) and our answer. Say it on a slide.

## 3. Style: seminar, not slideware ("AI smell" list)
Juhyeong rejected the first version as "AI 냄새". What caused it, and what to do instead:
| Avoid | Do |
| --- | --- |
| The same frame on every slide (small coloured kicker + long serif sentence title + three rounded cards) | Vary layouts: big screenshot, bar chart, table, arrow chain, timeline, one big number, two columns |
| Rounded cards, pastel boxes, icons on everything | White background, thin rules, square boxes, one accent colour used sparingly |
| Slogans ("~합니다" mottos), parallel triplets, "·" and "—" everywhere | Plain spoken Korean, commas and slashes, short noun-phrase or one-claim titles |
| Text walls | One message per slide; 3–5 bullets max; numbers large, labels small |
| Numbers without a source | Source line bottom-left on every data slide; vendor/preprint flagged |
| Notes that read like a script | Notes in Juhyeong's voice, as he would say it in class |

Tokens: white `#FFFFFF`, text `#1B1B1B`, secondary `#666666`, rules `#D4D4D4`, accent green `#2A7354`,
"recheck" amber `#A86400`. Font: IBM Plex Sans KR everywhere (JetBrains Mono for code). Title 52px/600, body 26–30px,
never below 24px. Canvas 1920×1080, padding `96px 120px 140px`. Section tag top-right in grey (`01 문제`), page number
bottom-right, source bottom-left.

## 4. Deck file format (portable, publishable as a Claude Slides artifact)
```
<deck>/project/deck.json            {"v":4,"title":..., "order":[slide ids], "sections":{...}, "faces":{...}}
<deck>/project/slides/<id>.html     one <section id="<id>" data-transition="none" style="...">…<aside>notes</aside></section>
```
- Inline styles only, one `<section>` per file, all text ≥ 24px, images as `/_blob/<hash>` (already uploaded) or ask.
- Footer: `<div style="position:absolute;left:120px;right:120px;bottom:52px;display:flex;justify-content:space-between;align-items:baseline"><p style="font-size:24px;color:#8A8A8A">출처: …</p><p style="font-size:24px;color:#8A8A8A">N</p></div>`
- Copy the structure of any slide in `raw/decks/2026-11-03-1st-deck/project/slides/` rather than inventing new chrome.
- Glyphs: use ● △ – in tables (◐ does not render in Plex).
- Partial decks: `order` lists only slide files that exist; the outline carries the planned page numbers; when the deck
  is complete, page numbers follow `order`.
- Placeholders for facts that do not exist yet: text `[확인 필요: what is missing]` in `#666666` inside a dashed grey
  box (`border:2px dashed #AAAAAA`). Never amber: amber means "recheck" in the product.

## 5. Rubric (score 1–5 each in the handoff note)
1. Founder story: would a listener retell why he built it?
2. Commonness: is "everyone has this problem" shown with numbers from more than one country/source?
3. Urgency: is there a dated reason it must ship now?
4. Market honesty: estimates labelled, weak spot named and answered.
5. One message per slide: can each slide's title be read alone as the outline?
6. Evidence: every number has a source on the slide.
7. Voice: no item from the AI-smell list; notes sound like Juhyeong.
8. Fit: no overflow, nothing below 24px, no empty half-slide (checked in the preview contact sheet).

## 6. Facts you may reuse (with their sources)
Use `raw/market/2026-11-03-market-brief.md` and the reference deck. Re-check vendor figures before an IR pitch.
Open questions as of 2026-11-03: abstract says "311 series" vs repo README "231 scored series" (alarm-analyzer-eval);
the survey/interview results do not exist yet (H1–H4 untested).
