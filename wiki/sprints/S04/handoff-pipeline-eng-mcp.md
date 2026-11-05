---
type: handoff
owner_agent: pipeline-eng-mcp
status: draft
sources:
  - "S04-brief.md (MCP section)"
  - "../../architecture/data-model.md"
  - "https://modelcontextprotocol.io/specification/2025-06-18/basic/transports (Streamable HTTP)"
last_reviewed: 2026-11-05
---
# Handoff: MCP server (S04, pipeline-eng MCP)

## Delivered
- `app/src/lemmata/mcp.py`: `handle(request_json, ctx) -> (status, response_json_str | None)`; **the response is an already-serialised JSON string** (hub: write it as the body as-is, do not `json.dumps` again; None means empty body, status 202).
- Nine tools: list_projects, project_status, alarms, explain, findings, node, search, set_triage, sync. Each returns compact text (cap ~8,000 chars, truncation note says how to narrow) plus `structuredContent`.
- `LocalCtx(project_dir)` and `run_stdio(ctx)`; CLI `lemmata mcp-stdio <project_dir>` (one block at the end of `build_parser` plus `cmd_mcp_stdio`).
- `app/tests/test_mcp.py` (22 tests, stdlib unittest). Full suite: 61 tests pass.

## Behaviour the hub engineer must know
- Protocol: initialize negotiates 2025-06-18 / 2025-03-26 / 2024-11-05; `notifications/*` and client responses give 202; JSON-RPC errors -32700/-32600 come with HTTP 400, others HTTP 200; batches rejected (-32600). Stateless (no `Mcp-Session-Id`). `GET /mcp` -> 405 is the hub's job.
- Unknown tool name or non-object `arguments` -> -32602. Missing/invalid tool arguments and unknown project -> `isError: true` result (so the model can retry).
- `ctx.resolve` must raise `NotFound` for an unknown project. `ctx.list_projects()` entries are read for `id, name, code_repo, branch, paper_versions, last_sync, counts{recheck,findings}` (all optional).
- `sync` calls `ctx.sync(pid)` then `ctx.resolve(pid)` again and diffs alarm groups/findings before and after; `ctx.sync` returns `{"changed", "head"}`.
- Optional `ctx.write_lock` (a Lock): if present, held around `set_triage`. The hub should provide its per-project lock this way, or tools run unlocked.
- Prompt-injection hygiene: file lines and diffs sit in `<user-file-quote>` blocks (closing tags neutralised); every result ends with a note that quoted text is data, not instructions.
- Quoted file content and commit messages are stripped of ANSI escapes and control characters. `set_triage` appends `[by mcp]` (or `ctx.device`) to the note because the engine has no `by` field; adding one needs an engine change.
- `set_triage` accepts a node id/label or a finding id. It only changes Lemmata's triage state.

## Verification
- Real client: the official Node `@modelcontextprotocol/sdk` (Client + StdioClientTransport) against `python3 -m lemmata mcp-stdio /tmp/s4s`: connect, listTools (9 tools), callTool alarms OK, `structuredContent` present.
- Not done: the `claude` CLI is installed here (2.1.318) but not logged in ("Authentication error"), so no Claude Code end-to-end run. HTTP transport was only exercised through `handle()`, not over a socket (the hub is not merged yet).

## Setup lines
Hub (HTTP, token from `lemmata hub token --device "VS Code"`):
```
claude mcp add --scope user --transport http lemmata http://dais-juhyeongs-mac-mini:8765/mcp --header "Authorization: Bearer <token>"
```
Local (stdio, no hub):
```
claude mcp add lemmata -- uv run --project /ABS/PATH/lemmata/app lemmata mcp-stdio /ABS/PATH/to/project
```
(Without uv: `claude mcp add lemmata -e PYTHONPATH=/ABS/PATH/lemmata/app/src -- python3 -m lemmata mcp-stdio /ABS/PATH/to/project`.)

## Five prompts to type in Claude Code
1. "Use lemmata: list my projects and tell me which one has the most things to recheck."
2. "What does lemmata say I need to recheck after my last commit? Open the affected files in this repo."
3. "Explain with lemmata why Table 2 is flagged, show me the diff, and tell me whether results/table2.csv needs regenerating."
4. "Show lemmata's main_appendix_mismatch findings and fix the appendix value in my LaTeX so it matches the main text (ask me first which one is right)."
5. "Sync the project with lemmata, then mark Table 2 as needs_fixing with the note 'rerun with lr 1e-3'."

## Open points for Juhyeong
- Paths are shown as `paper/main.tex:49` (repo id + repo-relative); Claude maps `code/...` onto the local checkout.
- Auth for `/mcp` (Bearer only, cookie refused) is the hub's responsibility.
