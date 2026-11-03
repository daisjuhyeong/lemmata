# Lemmata — project rules (every agent reads this first)

Lemmata (working name): a pre-submission checker for ML paper authors. It checks that the main text,
appendix and references agree, and every finding links to its evidence. Course: AAA639 (Korea University).
Founder/CEO: Juhyeong. Agents propose; Juhyeong decides.

## Layout
- `raw/` — immutable sources (syllabus, interview transcripts, survey CSVs, papers). Read, never edit.
- `wiki/` — agent-written knowledge. `wiki/index.md` lists every page; `wiki/log.md` is append-only.
- `.claude/agents/` — role cards. Agent 1 = CTO.

## Rules
1. Every factual claim in wiki/ links to a file in raw/ or a URL. No source, no claim.
2. Every wiki page starts with frontmatter: type, owner_agent, status, sources, last_reviewed.
3. Write only in your own wiki folder; cross-folder changes go through a task card.
4. After any change: update wiki/index.md and append to wiki/log.md:
   `YYYY-MM-DD | agent | ingest/query/lint/build | files touched | note`
5. Operations: ingest (new source -> pages), query (answer from wiki, file good answers back),
   lint (stale pages, uncited claims, contradictions between ADRs and code).
6. Work starts from a task card in wiki/sprints/Sxx/ and ends with a handoff note. QA verifies before merge.
7. Feature branches only. Never push to main, never force-push.

## Reporting (Slack) — wiki/agents/reporting.md
- Ask for an approval, or say you are blocked, by writing `wiki/reports/outbox/<date>-<time>-<agent>-<slug>.md`
  (report_type: approval | blocked); then stop and wait. Finishing a task card ends with a `done` report.
- A hook posts the outbox to Juhyeong's Slack and moves it to wiki/reports/sent/. Never call Slack yourself.
- After Juhyeong answers, set `status: resolved` in the sent report and log it.
- No secrets, raw interview text, survey answers or personal data in a report; link the file.

## Needs Juhyeong's approval
ADRs, merges to main, anything published or posted, any spending, any use of user data,
interpretation of interviews.

## Scope (current)
MVP: reference existence check, main-text <-> appendix consistency, local HTML report.
Next: notation lint, citation-claim support, related-work coverage. Later (low priority): paper <-> GitHub code check, smoke tests.
Runtime: open-source Claude Code plugin run on each author's own Claude plan. Never route other users' work through Juhyeong's Max plan.
