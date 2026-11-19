---
type: readme
owner_agent: cto
status: draft
sources: []
last_reviewed: 2026-11-06
---
# decisions
Architecture decision records, ADR-NNN-title.md. Status proposed -> accepted only after Juhyeong approves.
- ADR-001 (MVP architecture) — exists only on the Mac mini; not in this clone; to be reconciled.
- [ADR-002: Localhost demo](ADR-002-localhost-demo.md) — proposed, 2026-11-04; supersedes nothing until ADR-001 is reconciled.
- [ADR-003: macOS desktop app](ADR-003-macos-desktop-app.md) — proposed, 2026-11-05.
- [ADR-004: Hub on the Mac mini over Tailscale](ADR-004-hub-on-mac-mini.md) — proposed, 2026-11-05.
- [ADR-005: No Overleaf; paper on GitHub, compiled locally](ADR-005-no-overleaf-paper-on-github.md) — proposed, 2026-11-06; supersedes the Overleaf parts of S05, amends ADR-004 Context.
- [ADR-008: Top-down evidence spine](ADR-008-top-down-evidence-spine.md) — proposed, 2026-11-16; Thesis → Claim → link (criterion, status) → Experiment; rule-made statuses; To-do, Trail, Home, shell.
- [ADR-009: Two kinds of study, and key numbers](ADR-009-study-kind-and-key-numbers.md) — proposed, 2026-11-19; method paper or benchmark study per project (rules Y1-Y4); a benchmark study has no "ours" (link rule L5, claim rule C10); key numbers traced to files; the hub says when its copy is behind.
- [ADR-010: Lemmata watches the agents; paper agents from PaperOrchestra; Baselines page](ADR-010-lemmata-watches-writing-agents.md) — accepted, 2026-11-19; no LaTeX tracking, LaTeX is made in Lemmata by the researcher's own agent; references looked up online by default; the researcher steers at the level of intuition, agents run in their own Claude Code, every stage leaves a record; a table of baselines with paper, PDF, code, idea and published numbers.
- [ADR-011: VS Code is the experiment bench](ADR-011-vscode-is-the-experiment-bench.md) — accepted, 2026-11-20; the website is where you read, decide and write; the hub prepares the rows; a run can be attached by hand; the extension offers its own update
