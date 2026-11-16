---
type: architecture
owner_agent: cto
status: proposed
sources:
  - "../../wiki/decisions/ADR-008-top-down-evidence-spine.md ; ../../wiki/decisions/ADR-007-project-map-two-phases.md"
  - "code on branch s24-topdown-evidence, read 2026-11-16: engine/api.py (scan, _exp, _exp_doc, claims, experiments, setup, review, confirm_map, digest, runs, add_runs), engine/understand.py (brief, verify, draft), engine/track.py (build), engine/experiments.py (build), engine/claims.py (build, restage, stage_of), engine/setup.py, engine/review.py, engine/process.py (ledger, timeline, digest, tasks), server.py (_api), mcp.py (tools)"
last_reviewed: 2026-11-16
---
# 04 Data flow: from the repositories to each page

## Today (this branch)
- The hub runs **no model**.
- The researcher's own Claude Code reads the brief and proposes a map over MCP. Rules check the map, and only the researcher confirms it, in the web UI (ADR-007).
- Every page is computed by rules from the scan plus the stored decisions.

```mermaid
flowchart TD
  repos["Paper repo and code repo (GitHub clone on the hub)"] --> scan["Scan: graph.py, checks.py, history.py"]
  scan --> G["Project graph, findings, events, alarms"]
  G --> brief["project_brief (rules)"]
  brief -->|"MCP"| agent["Researcher's Claude Code"]
  agent -->|"propose_map (MCP)"| verify["understand.verify (rules drop what fails)"]
  verify --> mp["map.json: proposed"]
  mp -->|"researcher clicks Confirm (POST /api/map/confirm)"| mc["map.json: confirmed, claims.json: questions become claims"]
  mc --> track["track.build: experiments from file patterns"]
  G --> rules["experiments.build (no map)"]
  track --> E["Experiments document"]
  rules --> E
  E --> cl["api.claims: restage with stage_of"]
  G --> cl
  E --> su["setup.build"]
  E --> rv["review.build"]
  G --> pr["process: ledger, timeline, digest, tasks"]
  vs["VS Code terminal, watcher, agent hook"] -->|"POST /api/runs"| rn["runs.json"]
  user["Researcher overrides: ours, metric, stage, links"] --> st["experiments.json, claims.json"]
  st --> E
  st --> cl
  cl --> api["HTTP API and MCP"]
  E --> api
  su --> api
  rv --> api
  pr --> api
  rn --> api
  api --> web["Web pages"]
  api --> ext["VS Code"]
  api --> mcp["MCP tools"]
```

## Proposed (ADR-008)
The new parts are drawn with the word "new":
- criteria in the map and their overrides (step 3);
- link rules and the thesis block (steps 1-2);
- To-do and Trail built from documents that already exist (steps 4-5);
- deadlines (step 5);
- the join of logged runs to experiments (step 6).

```mermaid
flowchart TD
  agent["Researcher's Claude Code"] -->|"propose_map with criteria (new field)"| verify["understand.verify: also checks criteria"]
  verify --> mp["map.json: proposed"]
  mp -->|"researcher confirms"| mc["map.json: confirmed"]
  over["Researcher edits a criterion (POST /api/experiment, new fields)"] --> xs["experiments.json: criteria per link"]
  mc --> track["track.build / experiments.build"]
  xs --> track
  rn["runs.json"] -->|"new: match by file pattern"| track
  track --> L["new: link status per claim and experiment (rules L0 to L4)"]
  L --> C["claims.stage_of over link statuses (rules C1 to C9)"]
  C --> T["new: thesis block, counts only (rule T1)"]
  L --> E["Experiments document"]
  C --> E
  T --> E
  E --> todo["new: todo.py (rules) + tasks.json"]
  E --> trail["new: trail.py (events, timeline, stages.json, runs, tasks, map, checkpoints, plans)"]
  dl["new: deadlines.json (researcher)"] --> trail
  dl --> todo
  E --> api["GET /api/experiments, /api/todo, /api/trail"]
  todo --> api
  trail --> api
  api --> web["Web: Outline, Home, Trail"]
  api --> tree["VS Code: Thesis tree"]
  api --> mcp["MCP: experiments, todo, trail (read-only)"]
```

| Stage | Who | Model? | Proposed change |
|---|---|---|---|
| Brief | Hub, rules | no | The brief text also explains how to draft a criterion |
| Map proposal | Researcher's own agent | yes, on their plan | May include `criteria` |
| Verify | Hub, rules | no | Checks each criterion: the metric is a column, the comparator is a method in the files, the question exists |
| Confirm | Researcher | no | Unchanged; the agent still has no confirm tool |
| Track and status | Hub, rules | no | Link status, stage rules, thesis block |
| To-do, Trail | Hub, rules | no | New, built from the documents above |
