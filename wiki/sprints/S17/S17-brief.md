---
type: task-card
owner_agent: lead
status: built, not yet QA-verified
sources:
  - "founder messages in chat, 2026-11-12 14:03, 14:07 and 14:10 KST: 'For the Claim explain why it is organized as RQ2, E1, S and etc.'; 'Can I just Combine them into the claims or question? Or ... start as a hypothesis and let it watch to grow ... after it was proved by experiments or mathematical organization'; 'Yes. I want this to be the root of why we are experimenting as well.'"
  - "code: app/src/lemmata/engine/{claims,api,track,experiments}.py, app/src/lemmata/{server,mcp}.py, app/src/lemmata/web/{research.js,app.css}, app/tests/test_map.py"
  - "../decisions/ADR-007-project-map-two-phases.md (the map's questions, scope and experiments this builds on)"
last_reviewed: 2026-11-12
---
# S17 brief: one claim, moving through stages; the claim is why an experiment exists

## What was built
- **One kind of item.** RQ1, E1, S, H2 and "Contribution 3" are all shown as claims, numbered C1, C2 ... (theorems and lemmas keep their names). The source's own label stays as a small reference on the card. With a base paper each claim carries a tag: **New** (the extension's) or **Original** (the base paper's, re-checked). New claims come first.
- **Stages** (`claim.stage`): Hypothesis -> Being tested -> Finding, or Not supported; plus Exploration, which only the researcher sets. Rules (`claims.stage_of`), no model:
  - a theorem or lemma: no proof = hypothesis, proof with open issues = being tested, complete proof = finding;
  - a claim with experiments: none has results = hypothesis; results but no comparison = being tested; behind in every compared experiment = not supported; behind in some = being tested; ahead or level in all but a paper-vs-file mismatch open = being tested; otherwise finding;
  - a claim with no experiments: the old evidence status decides (traced = finding, linked = being tested, nothing = hypothesis).
  - New claims are compared with the base method; Original claims with the best other method, as the base paper did.
- **The researcher can overrule** the stage per claim (select on the card; "from the evidence" hands it back). Stored in `.lemmata/claims.json` as `entries[id].stage`.
- **Stages over time.** Past stages of experiment-backed claims are read from the stored versions of their results (ours against the base or the best other, per day). From now on every change of stage is recorded in `.lemmata/stages.json`. The Timeline slider recolours each claim to its stage on that day.
- **Why we experiment.** Each claim lists the experiments run for it with the outcome of each; they are the first roots under the claim in the tree. Each experiment shows a "Why" line with its claim. An experiment that tests no claim is flagged ("Tests no claim") and counted on the Experiments page.
- Claims list is grouped by stage; the core message's meter counts stages; claims.md and the MCP `claims` tool report stages.

## Decisions taken without the founder (to confirm)
- The wording: Hypothesis, Being tested, Finding, Not supported, Exploration. "Caveat" stays the word for a note attached to evidence.
- A stale result does not move a finding back; it shows the Recheck mark. A mismatch between the paper's table and the files does move it back to Being tested.
- Tuning runs never count for or against a claim.
- The coding agent cannot set a stage (same rule as confirming).

## Known limits
- "Ahead of the other method" is taken as support for the claim. A claim that is not a comparison (a calibration target, a cost budget) needs the researcher's own call.
- The replay of past stages ignores paper-vs-file mismatches (they are only known for today) and is not available for claims backed only by a proof or by paper items.
- Checked in a browser on a synthetic extension project only, not on mcd_extension. QA agent has not verified.
