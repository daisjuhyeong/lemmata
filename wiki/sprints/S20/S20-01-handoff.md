---
type: handoff
owner_agent: lead
status: needs-qa
sources: ["founder chat 2026-11-12 22:06 KST"]
last_reviewed: 2026-11-12
---
# S20-01: next experiments, planned by Claude Code

Asked by Juhyeong (chat, 2026-11-12 22:06 KST): an option where Lemmata produces a Claude Code prompt to test an
experiment or run a further one, LLM-based for the best results.

## Design
The LLM is the researcher's own Claude Code, as with the project map and the confound check: the hub calls no model
(CLAUDE.md runtime rule). Two steps, and the researcher reviews between them:
1. **Plan with Claude Code** (Review claim panel, and each experiment's details) copies a short planning prompt.
   Claude Code calls `experiment_brief(target)`: the claim, its checklist gaps, how each experiment was made (scripts,
   settings, commands, datasets, methods), where ours is behind, open confounds, the base method and hoped conclusion,
   and what is already planned. It opens the files and calls `propose_experiments` with up to three proposals.
2. Lemmata keeps a proposal only if it has a valid kind, title, why, expected result and a prompt of 80+ characters,
   quotes at least one real file it builds on (quote found in that file), and its prompt names one of those files.
   Kept proposals show under **Next experiments** with why / expect / builds on (links to the lines) and the prompt
   in an editable box. **Copy prompt for Claude Code** copies it and marks it copied; Drop removes it.
   New drafts replace older drafts for the same target; copied prompts stay.

Target ids: `q:<claim id>` or `x:<experiment id>`, the same as the S19 VS Code links.

## Files
`app/src/lemmata/engine/plans.py` (new: brief, guide, checks, store `plans.json`), `engine/api.py` (plans,
plan_brief, propose_plans, set_plan), `server.py` (GET/POST `/api/plans`), `mcp.py` (two tools),
`web/research.js` (`rxPlanBox`, placed in the Review claim panel and experiment details), `web/app.css`.
No extension change: the VS Code tab loads the new page code from the hub.

## Verified
Python 172 passed / 2 skipped (new `test_map.test_plans`, `test_mcp.test_experiment_planning_tools`); extension unit
66; end-to-end 9/9. Screenshots on the map test project (local mode): `screenshots/review-next-experiments.png`,
`screenshots/experiment-next-experiments.png`.

## Not verified
- A real Claude Code session calling the two tools end to end (only tested through the MCP handler).
- Copy to clipboard inside a real VS Code webview (same `copyText` as the existing confound button).
- Quality of the plans: depends on the model; the checks only keep proposals grounded in real files.
