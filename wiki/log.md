# Log (append-only)
date | agent | operation | files touched | note
2026-11-02 | setup | build | repo skeleton, CLAUDE.md, 8 role cards, settings.json | created by Claude via linked chat
2026-11-03 | setup | build | .claude/agents/deck-marketer.md, growth-ir.md, wiki/presentations/{README,deck-playbook}.md, tools/deck/preview.py, raw/market/, raw/decks/2026-11-03-1st-deck/ | added deck-marketer agent (presentation + marketing); ingested market brief and 1st-deck snapshot
2026-11-03 | deck-marketer | build | wiki/presentations/2nd/{brief,outline,handoff}.md, 2nd/project/{deck.json,slides/cover,agenda,validation,screen,replay}.html, 2nd/preview/ | S01 practice run: 2차 발표 초안 (20장 outline, 5장 작성, 결과는 [확인 필요] 자리표시)
2026-11-03 | setup | build | deck-marketer.md, deck-playbook.md, tools/deck/preview.py, raw/course/ | practice-run feedback applied: per-presentation table, placeholder and partial-deck rules, positioning override, webfont + clipping checks; syllabus ingested
2026-11-03 | setup | build | CLAUDE.md, .claude/settings.json, wiki/agents/{reporting,handoff-protocol}.md, wiki/reports/, tools/report/slack.py, deck-marketer.md | Slack reporting: outbox files posted by Stop/SubagentStop hook, daily digest via cron
