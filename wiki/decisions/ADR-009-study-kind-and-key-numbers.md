---
type: adr
owner_agent: lead
status: proposed
sources:
  - "founder message in chat, 2026-11-19 16:27 KST: 'Currently, the temporal dependency project is working as a benchmark paper so for Lemmata, I would like to flexibily choose the option where it assists the research. For methodology work, it will use \"ours\" and focus on the performance of the model. For a benchmark paper, there will be findings that needs to be found through experiment, so there will be coarse experiments which needs closer organization. MCD extension work is closer to methodology research while temporal dependency work is closer to benchmark paper. Plan and update Lemmata'"
  - "https://github.com/daisjuhyeong/temporal_dependency/blob/short-exp/LEMMATA_EXPECTED.md (commit 458d573, attached to the same message): what Lemmata should be able to find, and the section 'Lemmata state (19 Nov 2026)'"
  - "ADR-007-project-map-two-phases.md (the map names 'ours'; what fails a rule is dropped; only the researcher confirms)"
  - "ADR-008-top-down-evidence-spine.md (link rules L1-L4 compare ours with a comparator; a tie counts as support)"
  - "../design/screens/S27-hypothesis-first.md (stage of a hypothesis from the project's own test table, rules R0-R5; step 12, report numbers against result files, not built)"
  - "code on branch s28-setup-board, read 2026-11-19: app/src/lemmata/engine/{understand,track,experiments,setup,review,todo,runs,hypo,api}.py, hub/projects.py, mcp.py, web/research.js"
  - "run of the s28 engine on temporal_dependency short-exp (458d573), 2026-11-19: Setup listed 201 methods and marked 34 of them 'ours' (datasets, test rows, synthetic cases among them)"
last_reviewed: 2026-11-19
---
# ADR-009: Two kinds of study (method paper, benchmark study), and key numbers

Status: **proposed**. Built on branch `s29-study-kind` from the chat session; this page is the written record for
Juhyeong's sign-off. Handoff: [S29-01](../sprints/S29/S29-01-handoff.md).

## Decision in short
1. **A project has a kind of study, chosen by the researcher**: *method paper* (it has an "ours") or *benchmark study*
   (it compares existing methods and has no "ours").
2. **A benchmark study is never given an "ours".** Its methods are "compared"; a row is a method only when its column
   names methods; a claim is decided by its own test, not by a method's rank.
3. **Key numbers**: the numbers a study rests on are listed by claim, read again from their committed files on every
   scan, and compared with what the report says. What cannot be traced is an open gap.
4. **Lemmata says when its own copy is behind.** A failed sync is recorded and named; "not in GitHub" is not claimed
   while syncing fails.

## Context
- Lemmata was built around a method paper. The project map names "ours" (ADR-007), a claim is supported when ours is at
  least as good as a comparator (ADR-008, L1-L4), and the Review asks "how does ours compare with the baselines?".
- `temporal_dependency` has no method of its own. It measures a property of benchmark datasets and tests three
  pre-registered hypotheses. On it, the s28 build:
  - listed 201 "methods" and marked 34 as "ours", because every label column of every result file was read as a list
    of methods (measured on 458d573; the project's own note counted 109 and 25 on an older copy);
  - warned, when its agent proposed a map without a method, that it would still guess an "ours";
  - dropped the experiments whose files its copy did not hold yet;
  - reported the logged runs as "not in github" although the cause was its own failed sync.
- The researcher wants to choose per project. `mcd_extension` stays a method paper.
- A benchmark study has many coarse experiments (steps, gates, checks) and its report quotes many numbers. The project
  wrote its own script and table to check that each quoted number is in a committed file (`LEMMATA_EXPECTED.md`).
  That check is what Lemmata is for, so Lemmata should do it.

## Decision

### 1. The kind of study (rules Y1-Y4, no model)
| Rule | When | Kind |
|---|---|---|
| Y1 | the researcher chose | their choice |
| Y2 | a confirmed map says `study`, or names a method | the map's |
| Y3 | no paper, and a protocol or a findings report (hypothesis-first) | benchmark |
| Y4 | otherwise | method |

- The page shows the kind, who set it, and a selector (Home, Thesis, Setup). "Let Lemmata decide" removes the choice.
- A kind set by rule Y3 or Y4 is marked as Lemmata's reading until the researcher confirms it.

### 2. A benchmark study
- **Map** (`lemmata.map/1`, two new fields): `study: "benchmark"` and `roles` (which column names the compared
  methods, the datasets, a group, a condition, a seed). `method`, `base`, `goal` and `criteria` are dropped with a
  reason. An experiment may give `row_column` (a table whose rows are tests, cases or sources) and `where` (only rows
  with these values, e.g. one shuffle variant of a long table).
- **Experiments**: no row is "ours". The summary is the field of what is compared (best, worst, median, how many).
  The caveats "Ours is a guess" and "Ours not found" do not exist.
- **Setup**: methods have the role *compared*. A row is a method only when its column has the method role (a `model`
  or `detector` column, or the map's own). Tests, cases, sources and groups are rows. Applies with and without a map.
- **Links (rule L5, added to ADR-008 L1-L4)**: an experiment linked to a claim carries the verdict of the claim's own
  test: test met → supports, test not met → contradicts (shown as "test not met", not in the error colour), no test or
  no verdict → inconclusive. L1 (no result file → not run) is unchanged.
- **Claims (rule C10)**: a map question that is not a hypothesis and has results stays "being tested", with the
  reason that a benchmark claim needs a test of its own.
- **Review**: the second question becomes "Have the tests decided the claims?". The checklist is: more than one run,
  every method on every dataset, a test fixed before the data, key numbers traced to a file, confounds checked.
- **To-do**: a claim its test does not support is a result, not a task.

A method paper is unchanged by all of the above.

### 3. Key numbers (`lemmata.numbers/1`)
- **One entry**: the claim it belongs to, the file, how it is read (one cell, or count / count of / share / mean /
  median / min / max / sum / all / any / distinct over rows that match conditions; a key of a JSON object), the text
  the report prints with its line, and an optional known gap.
- **Two phases, as ADR-007**: the researcher's own agent proposes (MCP `key_numbers` with `brief`, `propose_numbers`);
  rules check every entry against the files and drop what cannot be read; the researcher confirms. A confirmed
  proposal adds to the list.
- **Without anyone proposing**: the columns a hypothesis's test rule reports are listed as that hypothesis's numbers.
- **On every scan** each number is read again. Status: ok (agrees within the rounding the text used) · mismatch ·
  missing · gap · not compared.
- **Beside each number**: the commit that last wrote the file, the scripts the graph links to it, the logged runs
  that wrote it.
- **Open gaps**, by rule: a mismatch; a missing file or row; a known gap; a file in no commit; a file older than its
  code; a file no logged run wrote; a run on code not in GitHub; a run recorded with the commit that first held its
  results instead of its start commit.
- Nothing is recomputed from raw data. A number that only a script computes is a gap, by design.

### 4. Honest about what Lemmata cannot see
- The hub records each sync in the project's data (`sync.json`). A failed fetch is named: the saved sign-in is refused
  (sign in again), it covers public repositories only (allow private ones), GitHub will not serve this repository to
  it, or the branch is gone. The fix is in Lemmata's own pages; nothing on the hub computer is changed.
- While sync fails: the pages carry a note; a run on a commit Lemmata has not seen is "not pulled yet", not "not in
  GitHub"; a missing key number says it may only be missing here.
- A logged command that wrote no file, reported no number and did not fail is a *command*, not an experiment.
- A run logged after the fact may say `backfilled` and which commit it gives (`sha_basis`).
- An empty alarms or findings answer says what it rests on (no checkpoint, no paper).
- A map experiment marked `planned` is kept as *waiting* when its patterns match nothing, and looked for again at
  every scan. Without the mark it is dropped, as ADR-007 says.

## Options considered
- **One kind, and let "ours" be empty.** Smaller change, but every page keeps asking a question that has no answer,
  and the guess comes back wherever a default applies. Rejected.
- **Derive the kind only from the map.** Then nothing is right until an agent has mapped the project, which is when
  the wrong "ours" does the most damage. Kept as rule Y2, under the researcher's own choice.
- **Match the report's numbers to result files by rules alone** (S27 step 12). Works for numbers that sit in one cell;
  it cannot know that "3,254 of 3,294" is a count of rows, or which of two equal values is meant. Kept the two-phase
  design; the rule-only part is the test table's own row.

## Consequences
- ADR-007's map gains two optional fields; old maps read as before. ADR-008 gains L5; L1-L4 apply to method papers only.
- A method paper that is switched to benchmark loses "ours" on every page until switched back. Nothing is deleted.
- The quality of a key-number list depends on the agent that proposes it. The checker stops numbers that cannot be
  read; a number read from the wrong row but equal to the quoted one would pass. The researcher's confirmation is the
  safeguard, as for the map.
- A long table (one row per run) is now read whole by a mapped experiment (20,000 rows; it was 500).

## Needs Juhyeong
- Approve or change: the two kinds and their names; rule Y3 as the default for a hypothesis-first project; L5; the
  benchmark checklist on Review; Key numbers as a page of its own in the sidebar.
- `planned` experiments: keep them as an explicit mark, or keep every experiment whose files are missing?
- Merge to main.
