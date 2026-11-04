---
type: task-card
owner_agent: pm
status: draft
sources: ["../../product/demo-spec.md", "founder decision, 1st presentation, 2026-11-03"]
last_reviewed: 2026-11-04
---
# Task: S02-01 Engine, sample generator, tests
- Goal: Build `app/src/rmap/engine/`: scan a LaTeX project and a git repo into a graph, events, findings and alarms; build the synthetic sample generator; ship tests. Stdlib only (plus the `git` binary), offline, no AI calls.
- Inputs: [demo-spec](../../product/demo-spec.md) (vocabulary, stories, Golden set); founder decisions in spec header.
- Acceptance criteria:
  1. `engine` exposes a documented JSON-serialisable API (graph, links with detected/proposed/approved/rejected state, checkpoints, alarms with groups, findings with `path:line` and quoted line, analyzer chain+diff). Agree schema with web-eng (S02-02) in the first day; write it to the handoff note. Covers US-02, US-04, US-05.
  2. Content-hash alarms: byte-identical vs checkpoint raises nothing (US-04.2); proposed links excluded from propagation (US-04.6, US-07.1); approving/rejecting recomputes (US-07.2-.4).
  3. Checkpoint store and triage store as local files in a gitignored state dir; triage resets to unreviewed on hash change and keeps history (US-03, US-06.1-.3).
  4. Ten integrity checks F01-F10 as in the Golden set, with neutral message templates (US-08 to US-12). Offline reference cache bundled; online lookup is opt-in, off by default (US-08.4).
  5. `app/samples/make_sample.py` builds the two-repo sample with history P1-P3, K1-K5, CP1 seeded, fixed commit dates, deterministic (US-14). Only stdlib + git; writes only to the target dir.
  6. Code-only mode works on `alarm-analyzer-eval`, paper checks reported as "not applicable" (US-13.1-.2, .4).
  7. `app/tests/` unit tests for each check, hash/alarm logic, link approval; all green with `python3 -m unittest`.
  8. No network call anywhere in engine (US-01.3, US-04.5); a test blocks sockets and runs the full pipeline.
- Owner: pipeline-eng
- Reviewer (QA): qa (S02-03)
- Budget (time/usage): PM proposal, 2 working days; no paid services.
- Done when: all criteria met on a feature branch, tests green, engine output on the sample equals `app/tests/golden.json` (S02-03), handoff note filled. Any change to node IDs or schema is told to QA and web-eng. Merge decided by Juhyeong.

## Handoff note
- What changed:
- Open questions:
- Links:
