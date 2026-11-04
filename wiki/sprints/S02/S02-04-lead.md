---
type: task-card
owner_agent: pm
status: draft
sources: ["../../product/demo-spec.md", "founder decision, 1st presentation, 2026-11-03"]
last_reviewed: 2026-11-04
---
# Task: S02-04 Rename, packaging, run instructions
- Goal: Apply the product rename, package the app so one command launches the demo on Juhyeong's Mac, and write the run instructions.
- Inputs: [demo-spec](../../product/demo-spec.md); the final name and package name from Juhyeong (placeholders `Research Map` and `rmap` until then).
- Acceptance criteria:
  1. After Juhyeong confirms the name, `Research Map` and `rmap` are replaced in code, packaging, and wiki pages through task cards for folders owned by other agents (rule 3). Rename list recorded in the handoff note.
  2. A single documented command builds the sample into a temp dir and launches the server and browser (default `./demo.sh` at repo root; PM proposal). No `pip install` from the network and no npm step (US-01.1-.3).
  3. `pyproject.toml` (or equivalent) with a console entry `rmap` and subcommands at least `demo` and `open <path>` (US-01, US-13.1).
  4. `app/README.md` with: requirements (Python 3.10+, git), the one command, how to reset state, how to open the real repo, how to export the report, fallback if the port is busy (US-01.4).
  5. `.gitignore` covers the state directory; no secrets or user data in the repo.
  6. Runtime note kept: the tool runs on each author's own machine; nothing is routed through Juhyeong's Max plan; no paid service used.
  7. Fresh-clone test on a clean directory: command works from zero (supports US-01; verified by QA).
- Owner: lead
- Reviewer (QA): qa (S02-03)
- Budget (time/usage): PM proposal, 0.5 working day after the name is confirmed.
- Done when: fresh-clone run passes QA; README reviewed by Juhyeong; handoff note lists renamed paths. Merge to main decided by Juhyeong.

## Handoff note
- What changed:
- Open questions:
- Links:
