---
type: task-card
owner_agent: lead
status: built, not yet QA-verified
sources:
  - "founder message in chat, 2026-11-11 21:28 KST: 'focus on the perspective of a student as its main tool, including the digest, and from the PI's perspective of the tree. I agree with the fact that most of the experiments arent in Github, which emphasizes the need for connecting it to visual studio code'"
  - "founder message in chat, 2026-11-11 21:41 KST: 'Build it and guide me step by step on how I can implement Lemmata in visual studio code'"
  - "https://code.visualstudio.com/api/references/vscode-api (window.onDidStartTerminalShellExecution, onDidEndTerminalShellExecution; stable since 1.93)"
  - "https://code.claude.com/docs/en/hooks (PreToolUse / PostToolUse / PostToolUseFailure input on stdin, tool_use_id, CLAUDE_PROJECT_DIR)"
  - "code: app/src/lemmata/engine/runs.py, engine/api.py, server.py, mcp.py, app/tests/test_runs.py; vscode/src/runs.ts, vscode/src/core/runs.ts, vscode/media/hooks/log_run.py, vscode/test/unit/{runs,capture}.test.ts, vscode/test/integration/hub.test.ts"
last_reviewed: 2026-11-11
---
# S15 brief: run capture in VS Code and the coding agent

## What was built
- **One record format, three writers.** `<repo>/.lemmata/runs/<run_id>.json`: command, cwd, host, commit, dirty flag, hash of the uncommitted patch, hashes of settings files named on the command line, metric values, paths of files written, start, end, exit code.
  - Terminal: VS Code shell-integration events (extension 0.2.0).
  - Results watcher: metrics files appearing in results folders; attached to the run that was going, or logged as a detached job.
  - Coding agent: a Claude Code hook (`.lemmata/hooks/log_run.py`, stdlib Python), installed by the command "Lemmata: Set up coding agent (Claude Code)".
- **Hub.** `GET /api/runs`, `POST /api/runs` (stored in `<hub>/runs.json`). Each run is labelled failed / uncommitted / not in github / in github, and tied to result files the hub already tracks.
- **MCP.** `runs` (read, filter by command, path, metric or commit) and `log_run`.
- **Digest.** One extra line when runs were logged in the period.
- **Extension.** "Runs" list, status-bar count, send-now command, four settings, guide in `docs/RUN-CAPTURE.md`.

## Decisions taken without the founder (to confirm)
- Run records are git-ignored (`.lemmata/.gitignore` = `*`), not committed. They reach the hub over the API.
- The extension is declared `extensionKind: workspace`: under Remote-SSH it runs on the server, so the server must reach the hub.
- The hook goes in `.claude/settings.local.json` (personal), not the shared `.claude/settings.json`.
- Minimum VS Code is now 1.93 (was 1.90).

## Not built
- No web page shows the runs. Experiments, Review and the Claims tree do not use them yet.
- No link from a run to a paper table cell; no notebook, W&B or MLflow import.

## Verified
- 162 Python tests pass (9 new). 50 extension unit tests pass (26 new), including the hook run for real against a temporary git repository and the capture logic run against a stand-in for the VS Code API. 10 integration tests pass (1 new: a run posted with a hub token to a real hub, read back as "in github" and tied to a tracked result file).
- **Not verified:** the extension has not been run inside a real VS Code window (the test host could not be downloaded in the build environment), so the terminal events, the file watcher wiring and the set-up dialogs are untested in the editor. Not run with a real Claude Code session: the shape of `tool_response` for Bash and whether a non-zero exit fires PostToolUse or PostToolUseFailure were not confirmed (the hook handles both). Not tried over Remote-SSH. Not run on mcd_extension. QA has not reviewed.
