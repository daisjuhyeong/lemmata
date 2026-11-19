---
type: handoff
owner_agent: lead
status: needs-qa
sources:
  - "founder chat 2026-11-19 17:59 KST ('... I want a separate section (page) where I can organize the baselines in a table with an option for me to check the paper's pdf, github code, and its intutition and published performance so that I can track it for our methodology. I want it to be reused as Claude code agents instead. Plan and send it to the CTO agent, and proceed with the work.')"
  - "S30-brief.md (the task card and plan) ; ../../decisions/ADR-010-lemmata-watches-writing-agents.md (proposed)"
  - "https://github.com/google-research/paper-orchestra at commit d9bae99 (Apache-2.0), read in full 2026-11-19"
  - "https://code.claude.com/docs/en/sub-agents (fetched 2026-11-19: agent file format)"
  - "code on branch s30-baselines: app/src/lemmata/engine/baselines.py, engine/api.py, server.py, mcp.py, cli.py, agents/, web/{research.js,app.js,app.css}, app/tests/{test_baselines,test_agents,test_mcp}.py"
last_reviewed: 2026-11-19
---
# S30-01: the Baselines page, and paper agents for Claude Code

Asked by Juhyeong (chat, 2026-11-19 17:59 KST). Built from the chat session on branch `s30-baselines`, cut from
`s29-study-kind`. Nothing is merged to main. Plan: [S30 brief](S30-brief.md). Decision record:
[ADR-010](../../decisions/ADR-010-lemmata-watches-writing-agents.md) (proposed).

## What changed
### Baselines page (`engine/baselines.py`, new)
- **Rows.** Every method of the result files whose Setup role is base, baseline or compared (not ours, not an ablation
  variant), then baselines the researcher added before running them.
- **A card per row**, kept in the hub folder as `baselines.json`: paper (title, authors, year, venue, link, PDF link),
  code link, the idea, where it falls short, how ours differs (method papers only), notes, and published numbers
  (dataset, measure, value, where it is printed, link, protocol note).
- **Published beside measured.** Each published number is matched by dataset and measure to the baseline's number in
  the project's own runs and to the number of the project's method, and the difference is shown. No verdict. When the
  paper prints 0.38 and the result file holds 41.0 the comparison is made on the file's scale and the page says so.
  The project's numbers with nothing published beside them are listed under the same table.
- **Two ways in.** The researcher's own edit counts at once (`POST /api/baselines {action: "save"}`). An agent's cards
  are a proposal checked by rules (`propose_baselines`): links must be https with a host, a published number must be
  a number and must say where it is printed, a name not in the result files is kept as "a baseline to consider".
  What fails is dropped with a reason; the researcher confirms all or one baseline at a time, with a before / after
  list per field.
- **Rules only.** Lemmata opens no link and calls no model. An arXiv abstract link gets its PDF link filled in
  (fixed address) and marked as derived. A PDF link that does not look like one and a code link on an unknown host
  get a note, not a refusal.
- **Where.** Sidebar → Explore → Baselines; footer link in narrow windows and in the VS Code tab; search box
  ("Go to Baselines"). Counts as part of Setup in the top bar. In exported snapshots (read-only).
- **API / MCP.** `GET /api/baselines`, `GET /api/baselines/brief`, `POST /api/baselines` (save, confirm, discard,
  remove, or a list to propose). MCP `baselines` (read; `name=` for one, `brief=true` for the format) and
  `propose_baselines`.

### Paper agents (`app/src/lemmata/agents/paper/`, new)
- Six Claude Code agents and one skill, adapted from PaperOrchestra's prompts: `paper-outline`, `paper-literature`,
  `paper-figures`, `paper-sections`, `paper-review`, `paper-revise`, and `/lemmata-paper`.
- `NOTICE.md` names the source, the commit, each adapted file and every change; the Apache-2.0 text is beside it.
- What differs from the original, in one line each: inputs come from Lemmata's tools; the researcher approves the
  outline; limitations are written and kept; no citation quota; every kept reference is verified in a bibliographic
  index and recorded with its reason; plots come from kept scripts that read committed files; a revision is kept on
  consistency checks, not on the reviewer's score; a request for a new experiment becomes a task; every stage writes a
  record to `.lemmata/writing/`.
- `lemmata agents install <research repo>` copies them into `.claude/agents/`, `.claude/skills/lemmata-paper/` and
  `.claude/lemmata-paper-agents/` (notice and licence). A file the researcher changed is kept unless `--force`.
- The literature agent also fills the baseline cards through `propose_baselines`.

## Verified
- Python: 216 passed, 2 skipped (10 new: `test_baselines` 7, `test_agents` 3; `test_mcp` pins the two new tools).
  - rows from the result files; the researcher's edit, clearing a field, replacing the numbers; refused links and
    numbers; a baseline tracked before it is run; proposal, dropped and noted entries, confirm one, discard the rest;
    link rules; both MCP tools through the local context; the brief; the page as plain JSON.
  - agent files: frontmatter, tool lists, every named Lemmata tool exists, the removed instructions are absent and the
    replaced ones present, the notice and licence; the installer and the CLI.
- Browser (headless Chromium) on the `test_map` project with its map confirmed, at 1360, 760 and 420 px: table, open
  row, proposal with before / after, confirm, edit and save, a refused http link (the form stays open), add a
  baseline. No sideways scroll. The only console message is the expected 400 of the refused save.
  [Screenshots](screenshots/).

## Not verified
- Not run on the Mac mini hub, on `mcd_extension` or on `temporal_dependency`. On a benchmark study the rows are the
  compared methods and the "ours" column is hidden; that path is covered by reasoning and by the page code, not by a
  test on a real benchmark project.
- The agents were not run end to end in Claude Code. Their files are checked for form and for the rules they must
  state, not for the quality of a paper they produce.
- A real VS Code window. The tab reaches the page through its footer link; there is no `Open Baselines` command and
  no install command in the extension yet (the `.vsix` was not rebuilt).
- The desktop app's bundled server does not include the agent files (they are package data of the source checkout and
  the wheel).

## Deploy
On branch `s30-baselines` (stacked on S29). The hub runs it once its auto-update follows this branch
(`uv run lemmata hub autoupdate install --branch s30-baselines`) or once it is merged into the followed one.
To install the agents into a research repository, from a checkout of this branch:
`cd app && uv run lemmata agents install /path/to/research-repo`.

## Open questions
- Approve ADR-010.
- Should a card's published numbers also be checked against the paper by the engine (it would need to fetch and read
  the PDF), or stay the researcher's click?
- The agents assume the MCP server is registered as `lemmata`.
