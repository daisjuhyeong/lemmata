---
type: architecture
owner_agent: cto
status: proposed
sources:
  - "../../wiki/decisions/ADR-008-top-down-evidence-spine.md"
  - "code on branch s24-topdown-evidence, read 2026-11-16: vscode/package.json (container lemmata; views lemmata.panel 'Alarms and findings', lemmata.runs 'Runs'; commands lemmata.openTab.*), vscode/src/extension.ts (Controller tree, diagnostics, status bar, registerUriHandler), vscode/src/runs.ts (Runs tree, status bar), vscode/src/tab.ts (webview tab with the hub's pages), vscode/src/core/link.ts (vscode://lemmata-local.lemmata/open?pid&view&sel), vscode/src/core/embed.ts (VIEWS)"
last_reviewed: 2026-11-16
---
# 03 Website and VS Code navigation

## Today (this branch)
- VS Code has one Lemmata container with two native tree views, two status bar items, squiggles (diagnostics), and one webview tab.
- The webview tab shows the hub's own pages.
- The website opens VS Code through a `vscode://` link.

```mermaid
flowchart LR
  subgraph web["Website (hub)"]
    wp["Pages: Claims, Experiments, Setup, Digest, Review"]
    ov["Open in VS Code button"]
  end
  subgraph vsc["VS Code"]
    ab["Activity bar: Lemmata"] --> t1["Tree: Alarms and findings"]
    ab --> t2["Tree: Runs"]
    sb1["Status bar: n to recheck"]
    sb2["Status bar: runs today"]
    tab["Webview tab: the same hub pages"]
    ed["Editor at file and line"]
    dg["Squiggles in tex files"]
  end
  ov -->|"vscode link: pid, view, sel"| tab
  t1 -->|"click item"| ed
  t2 -->|"open run record"| ed
  tab -->|"file and line links"| ed
  sb1 --> t1
  sb2 --> t2
  cmd["Commands: Open Review, Claims, Experiments, Setup"] --> tab
  tab -->|"Open on website"| wp
```

The link format is `vscode://lemmata-local.lemmata/open?pid=<project>&view=<page>&sel=<q:… | x:… | i:… | c:…>`. `view` is one of `VIEWS`: review, claims, experiments, setup, digest, timeline, tasks, notation, changes, graph, ask.

## Proposed (ADR-008, build step 7; website tabs as in phase 2, step 8)
- A native **Thesis** tree goes first in the container.
- Tree leaves open files at the line.
- A claim or an experiment opens its detail in the existing webview tab.
- No new status bar item; the first one carries the counts.

```mermaid
flowchart LR
  subgraph vsc["VS Code"]
    ab["Activity bar: Lemmata"] --> th["Tree: Thesis (new)"]
    ab --> t1["Tree: Alarms and findings"]
    ab --> t2["Tree: Runs"]
    th --> cl["Claim node: stage icon, n of m support"]
    cl --> lk["Experiment node: status icon, gap vs comparator"]
    lk --> lf["Leaves: paper location, result files, scripts, settings, runs"]
    lf -->|"open at line"| ed["Editor"]
    cl -->|"view experiments, sel q"| tab["Webview tab: detail"]
    lk -->|"view experiments, sel x"| tab
    sb1["Status bar: claims found, to recheck"] --> th
  end
  subgraph web["Website (hub)"]
    home["Home: thesis counts, to-do, trail, deadlines"]
    wp["Thesis outline page"]
    tr["Trail"]
    pj["Projects list: one row per research"]
    pj --> home
    home -->|"to-do item"| wp
    home -->|"trail entry"| tr
    tr -->|"entry at that date"| wp
  end
  wp -->|"Open in VS Code"| tab
  tab -->|"Open on website"| wp
  viewer["Viewer, read-only (needs approval)"] -.->|"GET only"| home
```

| Piece | Today | Proposed |
|---|---|---|
| Views in container | 2 (Alarms and findings, Runs) | 3 (Thesis, Alarms and findings, Runs) |
| Status bar | "Lemmata: n to recheck" + runs item | "Lemmata: 2/4 claims found · n to recheck" + runs item |
| `VIEWS` keys | review, claims, experiments, setup, digest, timeline, tasks, notation, changes, graph, ask | the same, plus `trail` and `home` (old keys stay as aliases) |
| Data for the tree | — | `GET /api/experiments` (nodes), `GET /api/experiment?id=` on expand (leaves); no new route |
