---
type: architecture
owner_agent: cto
status: proposed
sources:
  - "../../wiki/decisions/ADR-008-top-down-evidence-spine.md"
  - "../../wiki/design/screens/S18-dais-ui.md (four-tab rule) ; ../../wiki/sprints/S23/S23-01-handoff.md (fifth tab, Setup)"
  - "code on branch s24-topdown-evidence, read 2026-11-16: web/app.js (NAV, NAV_OF, renderPage, footer links), web/research.js (RX_PAGES, pageExperiments with Table and Map views, rxExpMap, rxExpRow, rxExpDetail, rxMapCard, rxUnmapped)"
last_reviewed: 2026-11-16
---
# 02 Page hierarchy

## Today (this branch)
There are five tabs in the band (`NAV` in `web/app.js`). Every other page belongs to one tab (`NAV_OF`), which then shows as active. Those pages are reached from links on that tab or from the footer.

```mermaid
flowchart TD
  band["Band: five tabs"] --> C["Claims"]
  band --> E["Experiments"]
  band --> S["Setup"]
  band --> D["Digest"]
  band --> R["Review"]
  C --> C1["Timeline (Growth)"]
  C --> C2["Notation"]
  C --> C3["Graph"]
  C --> C4["Item and node pages"]
  E --> E1["Map card (project map)"]
  E --> E2["Table view: one section per claim"]
  E --> E3["Map view: Ours, then claims, then experiments"]
  E2 --> E4["Row expand: experiment detail"]
  E --> E5["No claim yet, Not in the map, All result files"]
  D --> D1["Tasks"]
  D --> D2["History"]
  D --> D3["Ask"]
  R --> R1["Changes (alarms)"]
  R --> R2["Checks (integrity findings)"]
```

Today's Experiments page, from top to bottom (Table view, the default): map card → "extends" line (if any) → counts line → one section per claim (stage chip, then experiment rows) → "No claim yet" → "Not in the map" → "All result files".

## Proposed, step 1: the top-down Experiments page (no nav change)

```mermaid
flowchart TD
  h["Thesis header: core message, claim counts by stage, link counts"] --> bk["Two buckets, always shown: claims with no experiment, experiments with no claim"]
  bk --> g["Claim group header: stage word, evidence bar, paper anchor"]
  g --> row["Experiment row: status word, ours vs comparator, gap, dataset and metric, seeds, last result"]
  row --> det["Row expand: criterion and its source, rule and why, setup chips, result files, scripts, settings, runs, paper location"]
  g --> g2["Next claim group"]
  det --> mc["Map card and Not in the map, moved below the claims"]
```

## Proposed, steps 4 and 5: To-do and Trail on today's tabs (no nav change)
Digest's "Open tasks" becomes **Next to do**, and its "History" section, the History page and the Timeline "Steps" list become the **Trail**.

```mermaid
flowchart TD
  D["Digest (today's tab)"] --> td["Next to do: waiting on a person, your confirmation, paper wrong today, out of date, gaps"]
  D --> tw["This week (digest prose, Slack)"]
  D --> trl["Trail: day rows by week, deadlines ahead"]
  td -->|"each item opens"| tgt["Claim, experiment row, setup item, tex line, task"]
  trl -->|"each entry opens, at that date"| tgt2["Tree at that date, experiment version, commit, task"]
  D --> T1["Tasks (feedback inbox)"]
  D --> A1["Ask"]
```

## Proposed, phase 2 (needs Juhyeong's approval, decisions D6, D12, D14)
- Claims and Experiments become one tab, **Thesis**, with two lenses.
- Digest becomes **Home** for the research.
- History becomes **Trail**.
- There are five tabs, as today. The shell stays a top band (option S1).
- Old tab keys and VS Code links (`claims`, `experiments`, `digest`, `history`) open the matching place.

```mermaid
flowchart TD
  pj["Projects list: one row per research, thesis counts, open to-dos"] --> band["Band: five tabs"]
  band --> H["Home"]
  band --> T["Thesis"]
  band --> S["Setup"]
  band --> R["Review"]
  band --> TR["Trail"]
  H --> H1["Thesis sentence and counts"]
  H --> H2["Next to do, top five"]
  H --> H3["Last seven days of the trail"]
  H --> H4["Deadlines"]
  H --> H5["This week and Slack"]
  H --> H6["Tasks and Ask"]
  T --> T1["Outline lens (default): the step 1 page"]
  T --> T2["Tree lens: claims graph, Needs attention, Growth slider"]
  T1 --> T3["Row expand: experiment detail"]
  R --> R1["Changes"]
  R --> R2["Checks"]
  TR --> TR1["Filter: paper, code, runs, claims, feedback, decisions"]
  more["Footer: More"] --> M1["Notation"]
  more --> M2["Graph"]
  v["Viewer, read-only (W2, needs approval)"] -.-> H
```

| Today | Phase 2 |
|---|---|
| Claims (tab) | Thesis → Tree lens |
| Experiments (tab) | Thesis → Outline lens |
| Digest (tab) | Home |
| History (under Digest) | Trail (tab) |
| Timeline | Growth slider in Thesis → Tree; its Steps list in Trail |
| Tasks, Ask | Under Home |
| Setup, Review (tabs) | Unchanged |
| Notation, Graph | Footer "More" |
