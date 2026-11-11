---
type: task-card
owner_agent: lead
status: built, not yet QA-verified; LaunchAgent parts not run on macOS
sources:
  - "founder request in chat, 2026-11-11 13:55 KST: when a change is made, the CTO or another agent should run the terminal commands so the hub is updated; chat is for communicating, not for doing the work"
  - "terminal output pasted by the founder, 2026-11-11 12:42 to 12:43 KST: the Mac mini's working checkout was on agents/deck-marketer with uncommitted wiki edits, which blocked `git switch` and `git pull`"
  - "code on branch s07-public-site: app/src/lemmata/hub/update.py, hub/cli.py, hub/config.py, tests/test_update.py, docs/AUTO-UPDATE.md, .claude/agents/cto.md"
last_reviewed: 2026-11-11
---
# S10 brief: the hub deploys itself

- `lemmata hub autoupdate install` clones a deploy checkout under `~/Lemmata/deploy`, points the hub LaunchAgent at it (system Python + `PYTHONPATH`, no virtualenv) and adds a second LaunchAgent that runs `lemmata hub update` every 5 minutes.
- One pass: fetch, fast-forward only, start-up check, restart, health check, roll back on failure, log, optional Slack report, optional on-failure command.
- Tested on Linux with a local repository standing in for GitHub: good change deployed, broken change refused, change that fails after restart rolled back, credentials never stored. **Not tested:** the launchctl calls, on macOS.
- Setup and limits: `docs/AUTO-UPDATE.md`. The CTO role card now says who owns a failed deploy.
- Needs Juhyeong: which branch to follow (now `s07-public-site`; `main` after the open ADRs are approved and merged).
