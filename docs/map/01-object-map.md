---
type: architecture
owner_agent: cto
status: proposed
sources:
  - "../../wiki/decisions/ADR-008-top-down-evidence-spine.md"
  - "code on branch s24-topdown-evidence, read 2026-11-16: engine/claims.py (core, children, support), engine/understand.py (map questions, experiments.tests), engine/api.py (confirm_map), engine/track.py (experiment, grid, design), engine/setup.py, engine/runs.py (view: tracked files), engine/review.py (hoped, checklist)"
last_reviewed: 2026-11-16
---
# 01 Object map: what backs what

Read from the top down. An arrow means "is backed by" or "is made of". Glossary: [README](README.md).

## Today (this branch)
- The core message is already the parent of every claim.
- An experiment reaches a claim in one of two ways. With a confirmed map, through the map question's `tests`. Without one, through the claim's support links to a paper table, figure or result file.
- Logged runs touch the spine only through the result files they wrote.

```mermaid
flowchart TD
  core["Core message (claims.core)"] -->|"children"| claim["Claim (claims.json + drafts)"]
  hoped["Hoped conclusion (review.json)"]
  mq["Map question (map.json)"] -->|"confirm_map makes"| claim
  claim -->|"map mode: question in tests"| mx["Map experiment (file pattern)"]
  claim -->|"rule mode: support link"| px["Paper table or figure"]
  mx -->|"paper"| px
  mx -->|"files"| rf["Result files"]
  px -->|"traces_to, includes"| rf
  mx -->|"grid"| su["Setup items: metric, dataset, method"]
  rf -->|"produced_by"| rr["Run record (runs/id.json)"]
  rr -->|"executes, reads"| cs["Scripts and settings"]
  lr["Logged run (runs.json)"] -.->|"wrote, tracked only"| rf
  rv["Review checklist"] -.->|"one per"| claim
```

The status sits on the **experiment** (ahead / behind / tie / none against the best other method or the base). The claim's stage is computed from those.

## Proposed (ADR-008)
- A **link** with a criterion and a status sits between claim and experiment.
- The thesis shows counts.
- Logged runs join experiments by file pattern (build step 6).

```mermaid
flowchart TD
  th["Thesis = core message (counts only)"] --> claim["Claim (stage + rule)"]
  th -.-> b1["Bucket: claims with no experiment"]
  th -.-> b2["Bucket: experiments with no claim"]
  claim --> link["Link: criterion + status + rule"]
  link --> x["Experiment"]
  x --> su["Setup: dataset, metric, comparator"]
  x --> rf["Result files"]
  x --> pl["Paper location (tex file, line)"]
  rf --> rr["Run record"]
  rr --> cs["Scripts and settings"]
  lr["Logged run"] -->|"matches file pattern"| x
```

| Object | Today | Proposed |
|---|---|---|
| Thesis | `claims.core`, with a stage rolled up by `_roll` | The same object; the header shows counts, no verdict word |
| Claim ↔ Experiment | `tests` (map) or support links (rules); no own status | `link {status, rule, why, criterion, criterion_by}` |
| Logged run ↔ Experiment | None | Joined by the experiment's file patterns; `running` state |
