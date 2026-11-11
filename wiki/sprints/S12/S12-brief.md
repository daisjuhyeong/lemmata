---
type: task-card
owner_agent: lead
status: built, not yet QA-verified
sources:
  - "founder message in chat, 2026-11-11, with a screenshot of the flooded 'No question' section on mcd_extension (quoted in ADR-007)"
  - "founder reply in chat, 2026-11-11 14:55 KST: 'I like the design. build it.'"
  - "../../decisions/ADR-007-project-map-two-phases.md"
  - "code on branch s07-public-site: app/src/lemmata/engine/{understand.py, track.py, experiments.py, api.py}, app/src/lemmata/{mcp.py, server.py}, app/src/lemmata/web/{research.js, app.css}, app/tests/{test_map.py, test_mcp.py}"
last_reviewed: 2026-11-11
---
# S12 brief: the project map (understand with an agent, track with rules)

## What was built
- **Brief** (`engine/understand.py: brief`). Rules pack the project for a reader: paper outline, stated questions and contributions, tables and figures with their first rows, result files grouped by folder shape and columns (with the parts of file names that vary), scripts with options, settings, recent commits.
- **Map and checker** (`verify`). Format and rules as in ADR-007. The report lists every dropped entry and why.
- **Rule-only draft** (`draft`). One experiment per file group, kind guessed from the name, method from the title. For use before an agent has read the project.
- **Tracking** (`engine/track.py`). For each experiment: files matching the patterns are folded into one table (row per method, column per dataset, runs averaged, an Average column), "ours" from the map, paper check against the linked table, history as the last commit of each day that touched the group. Tuning experiments show the best setting and the number tried.
- **MCP tools**: `project_brief` (parts: overview, paper, files, code), `propose_map`, `project_map`.
- **Web**: a map card on the Experiments page (not read yet / proposed, with review and Confirm / confirmed), kind tags and file counts on rows, a "Not in the map" tray with Ignore, measure and dataset pickers in the detail.
- **API**: `GET /api/map`, `GET /api/brief`, `POST /api/map`, `/api/map/draft`, `/api/map/edit`, `/api/map/confirm`, `/api/map/discard`.

## How to use it
1. In Claude Code with the Lemmata MCP server connected, paste the prompt shown on the Experiments page ("Use Lemmata to understand the project …").
2. Open Experiments, review the proposed map, fix kinds or questions, press Confirm.
3. From then on every sync re-sorts results by the map with no model.

## Verified
- 150 unit tests pass on Linux (7 new in `tests/test_map.py`), and a browser walk-through on a synthetic project with 33 result files in three naming schemes. Before: 35 rows under "No question". After: 3 questions, 4 experiments, 1 file not in the map.

## Not verified / known limits
- **Not run on `mcd_extension` or any real repository**, and no real agent has produced a map yet; the test map was written by hand in the agent's format.
- QA agent has not reviewed. Hub (multi-user) routes were not separately tested for the new endpoints; they reuse the per-project handler.
- One experiment reads files from one repository. Result files must be CSV/TSV/JSON tables. At most 300 files per experiment and 15 days of history are read.
- When the map is confirmed again, claims added by an earlier confirmation are reused by exact text; a reworded question creates a new claim and leaves the old one.
- The Average column is a plain mean over datasets; it is not what every paper reports.
