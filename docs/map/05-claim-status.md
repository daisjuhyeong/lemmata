---
type: architecture
owner_agent: cto
status: proposed
sources:
  - "../../wiki/decisions/ADR-008-top-down-evidence-spine.md (§1 rules L0-L4, C1-C9, T1)"
  - "code on branch s24-topdown-evidence, read 2026-11-16: engine/claims.py (STAGES, STAGE_WORD, stage_of, _roll, restage, decide), engine/review.py (_state), engine/api.py (_outcome), engine/track.py (caveats, attention, stale)"
last_reviewed: 2026-11-16
---
# 05 Status words and the rules that set them

All of these are rules. No model sets a status, and each status can show the rule and one sentence of why.

## Today (this branch)
**Experiment state** (`review._state`, used through `api._outcome`). Against the base when the work extends a paper and the claim is the extension's own; otherwise against the best other method.

```mermaid
stateDiagram-v2
  state "none (no comparison)" as none
  state "ahead" as ahead
  state "tie" as tie
  state "behind" as behind
  [*] --> none : tuning, or no summary
  [*] --> ahead : gap above 0
  [*] --> tie : gap equals 0
  [*] --> behind : gap below 0
```

**Claim stage** (`claims.stage_of`). The researcher can overrule it (`stage_by: you`). Exploration is set only by the researcher.

```mermaid
stateDiagram-v2
  state "Hypothesis" as hyp
  state "Being tested" as testing
  state "Finding" as finding
  state "Not supported" as refuted
  state "Exploration" as explore
  [*] --> hyp : no evidence, or experiments planned with no results
  hyp --> testing : an experiment linked, or mixed results, or something to check
  testing --> finding : ahead or level in every compared experiment, nothing to check
  testing --> refuted : behind in every compared experiment
  finding --> testing : a new result is behind, or something to check
  refuted --> testing : a new result is ahead
  [*] --> explore : set by the researcher
```

The core message's stage today is `_roll`: the shared stage if all claims agree, else Being tested. Recheck is a separate flag, set when a result is older than its code or settings.

## Proposed (ADR-008)
**Link status**, one per claim and experiment, against that link's criterion. With the default criterion it gives today's result: supports = ahead or tie, contradicts = behind.

```mermaid
stateDiagram-v2
  state "not run (L1)" as notrun
  state "running (L0, step 6)" as running
  state "inconclusive (L2)" as inconc
  state "supports (L3)" as sup
  state "contradicts (L4)" as con
  [*] --> notrun : no result file
  notrun --> running : a logged run on these files has no end yet
  running --> inconc : files, but no comparison possible
  notrun --> inconc : files, but no comparison possible
  running --> sup : criterion met
  running --> con : criterion not met
  inconc --> sup : criterion met
  inconc --> con : criterion not met
  sup --> con : a newer result misses the criterion
  con --> sup : a newer result meets the criterion
```

Flags that never replace the word: `[recheck]` (stale), `!` (to check), guess, one run, criterion source (`default`, `drafted`, `confirmed`).

**Claim stage**, with the same words as today and numbered rules.

```mermaid
flowchart TD
  start["Claim"] --> q1{"C1: set by the researcher?"}
  q1 -->|"yes"| you["That stage, shown as set by you"]
  q1 -->|"no"| q2{"C2: formal statement?"}
  q2 -->|"yes"| proof["Proof rule: complete Finding, partial Being tested, none Hypothesis"]
  q2 -->|"no"| q3{"C3: any linked experiment?"}
  q3 -->|"no"| old["Old evidence status decides"]
  q3 -->|"yes"| q4{"C4: all links not run?"}
  q4 -->|"yes"| hyp["Hypothesis (planned)"]
  q4 -->|"no"| q5{"C5: any decisive link?"}
  q5 -->|"no"| t1["Being tested"]
  q5 -->|"yes"| q6{"C6: all decisive links contradict?"}
  q6 -->|"yes"| ref["Not supported"]
  q6 -->|"no"| q7{"C7: some contradict?"}
  q7 -->|"yes"| t2["Being tested (mixed)"]
  q7 -->|"no"| q8{"C8: any link with something to check?"}
  q8 -->|"yes"| t3["Being tested (check first)"]
  q8 -->|"no"| fin["C9: Finding"]
```

**Thesis (T1): counts only**, with no single word. For example: "4 claims: 2 Finding, 1 Being tested, 1 Hypothesis · 9 links: 6 supports, 1 contradicts, 1 inconclusive, 1 not run · 1 claim with no experiment · 2 experiments with no claim".

| Level | Today | Proposed |
|---|---|---|
| Experiment or link | ahead / tie / behind / none per experiment | supports / contradicts / inconclusive / not run (+ running) per link |
| Claim | the five stages, from `stage_of` | the same five, with rule ids C1-C9 |
| Thesis | `_roll` stage + stage meter | counts only (T1) |
