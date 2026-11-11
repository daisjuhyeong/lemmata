---
type: adr
owner_agent: lead
status: proposed
sources:
  - "founder message in chat, 2026-11-11 (screenshot of the Experiments page on mcd_extension: the 'No question' section full of raw result files): 'How are the RQs designed or extracted by Lemmata? There are too many results that are no related to the questions. Doing it manually would be too difficult. … Ours is the MCD, so the results should be around MCD. First lets design an architecture or framework of understanding the current work, maybe utilizing agents (LLMs) first phase, and then other changes are based off of LLM-free works.'"
  - "founder reply in chat, 2026-11-11 14:55 KST, to the two-phase design: 'I like the design. build it.'"
  - "CLAUDE.md (Runtime: each author's own Claude plan; never route other users' work through Juhyeong's Max plan)"
  - "code on branch s07-public-site: app/src/lemmata/engine/{understand.py, track.py, experiments.py, api.py}, app/src/lemmata/{mcp.py, server.py}, app/src/lemmata/web/{research.js, app.css}, app/tests/test_map.py"
  - "../sprints/S11/S11-brief.md (known limits that this decision answers)"
last_reviewed: 2026-11-11
---
# ADR-007: Understand once with an agent, then track with rules (the project map)

Status: **proposed** (Juhyeong approved the design in chat; this page is the written record for his sign-off). Sprint: [S12 brief](../sprints/S12/S12-brief.md).

## Context
- S11 found research questions only as literal `RQ1` labels and hypotheses only in the contributions list. A result joined a question only through a `% source:` comment or a sentence naming both. Each result file was one experiment, with "ours" and the metric guessed per file. On a real project this put every tuning and per-dataset file under "No question" (founder screenshot, see sources).
- Sorting hundreds of files by hand is not realistic. Rules alone cannot tell which runs answer which question. A language model can, but Lemmata's principle is that no model runs on the hub and nothing goes through the founder's plan.

## Decision
1. **Two phases.** Phase 1 "understand" produces a *project map* once per project. Phase 2 "track" applies the confirmed map on every scan with rules only.
2. **The map** (`lemmata.map/1`) holds: the method's name and aliases ("ours"), the questions and hypotheses with a quote from the paper each, the experiments (a file pattern with `{dataset}`, `{method}`, `{seed}` fields, a kind, a metric, the tables or figures it feeds, the questions it tests), and ignore patterns.
3. **Who writes it.** The researcher's own agent (Claude Code) through three MCP tools: `project_brief` (rule-made digest plus the format), `propose_map`, `project_map`. A rule-only draft exists for people without an agent. The hub runs no model.
4. **Rules check every entry.** A quote must be in the paper; a method name must appear in the paper or the result files; a pattern must match a file; a metric must be a real column; a table label must exist. What fails is dropped and reported back.
5. **Only the researcher confirms**, in the web UI. A proposal changes nothing. The agent has no confirm tool.
6. **Confirming** turns the map's questions into claims (reusing ones the paper already states) and links each to the tables its experiments feed, so the Claims tree and the Experiments page agree.
7. **Drift.** Files and main-text tables the map does not cover are listed as "Not in the map"; they are never guessed into a question.

## Consequences
- The Experiments page shows one row per experiment (a group of runs), "ours" is set once, tuning runs collapse into one row.
- Quality of Phase 1 depends on the agent the researcher uses; the checker stops invented quotes and files, not a wrong reading of a real quote. The researcher's confirmation is the safeguard.
- The map lives in Lemmata's project data (`.lemmata/map.json`), not yet in the author's repository. Writing it into the repo needs a push permission decision and is left open.

## Open (needs Juhyeong)
- Should the hub ever accept a user-supplied API key to run Phase 1 itself? Today: no.
- Should the map be committed to the author's repository so it travels with the work?
