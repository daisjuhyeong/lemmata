---
type: handoff
owner_agent: lead
status: needs-qa
sources:
  - "founder chat 2026-11-12 22:19 and 22:33 KST"
  - https://code.claude.com/docs/en/best-practices
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
  - https://www.anthropic.com/engineering/writing-tools-for-agents
  - https://arxiv.org/pdf/2505.19955
  - https://arxiv.org/abs/2510.20270
  - https://metr.org/blog/2025-06-05-recent-reward-hacking/
  - https://arxiv.org/abs/2504.01848
  - https://arxiv.org/pdf/2408.06292
  - https://arxiv.org/pdf/2305.04091v3
  - https://arxiv.org/abs/2310.11324
last_reviewed: 2026-11-12
---
# S21-01: structured experiment prompts

Asked by Juhyeong (chat, 2026-11-12): research how to prompt Claude Code well, then "go with the prompts and make a
structured prompt format for a user to fix if wanted". Builds on S20 (next experiments planned by Claude Code).

## What changed
- **Proposals are structured specs, not free text.** `propose_experiments` now takes goal; decision rule (supports,
  against, inconclusive); files to read; paths to leave unchanged; steps; smoke test; full-run commands; where results
  go; a known value to reproduce first; budget; extra stop conditions. Missing required fields drop the proposal.
- **Lemmata renders the prompt from the spec with one fixed template** (`engine/plans.py: render`), in XML sections:
  goal, decision_rule, context, protected, steps, outputs, verification, stop_conditions, report_format. The template
  carries the guards: branch first, plan then continue, smoke test, write new files only, manifest.json and
  summary.csv under `.lemmata/exp/<plan id>/`, numbers computed by a saved analyze.py, `git diff` on protected paths,
  stop after two failed fixes, FAILED/BLOCKED as a valid outcome, no synthetic numbers.
- **The researcher edits fields, not prose.** Each plan is a form ("Edit the experiment"); every change is saved and
  the prompt preview and warnings update in place. Warnings (never blocking): missing fields, paths not in the
  repository, commands that use scripts that do not exist and that no step creates, an unmeasurable "supports" rule.
- **Copy protection rules**: `{"permissions": {"deny": ["Edit(./…)"]}}` for the protected paths, for
  `.claude/settings.local.json`. The button's tooltip says these do not cover shell commands unless the sandbox is on.
- **Planning guide**: data first in the MCP reply, instructions after it; cheapest decisive experiment first; one
  worked example; fields explained; positive wording.
- S20 drafts (free-text prompts, no spec) are no longer shown.

## Why this shape (from the research report in the founder chat, 22:33 KST)
- Claude Code docs: give the agent a check to run and ask for evidence; put rules that cannot bend in deny rules or
  hooks; plain wording over capitals; a fresh session needs everything it cannot see.
- MLR-Bench (Claude Code reported placeholder results in 8 of 10 tasks, even when told not to), ImpossibleBench
  (Claude models cheated mainly by editing tests; read-only access helped), METR (reward hacking on research tasks):
  so protected paths, read-only rules, results read from files, and an endorsed failure path.
- PaperBench: stop conditions in both directions. Plan-and-Solve: plan, then execute. Sclar et al.: format changes
  move results, so one fixed format.
- My inference, not tested: the "test fairly, not to confirm" line, the section order, one example in the guide.
  These should be A/B tested on real briefs (share of runs with untouched protected paths, traceable numbers, honest
  FAILED reports).

## Verified
Python 172 passed / 2 skipped (`test_map.test_plans` rewritten for specs, rendering, edits, lints, deny rules);
extension unit 66; end-to-end 9/9. Browser: a field edit updates the preview and warnings without a reload; no page
errors; no sideways scroll at 420 px. Screenshots: `screenshots/plan-form.png`, `screenshots/plan-prompt.png`.

## Not verified
- A real Claude Code session producing specs through the two tools, and a real run of a rendered prompt.
- The deny-rule syntax inside a real `.claude/settings.local.json` (format taken from the Claude Code docs example).
