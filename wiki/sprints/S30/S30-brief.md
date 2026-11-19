---
type: task-card
owner_agent: cto
status: in-progress
sources:
  - "founder messages in chat, 2026-11-19 17:41, 17:53 and 17:59 KST (quoted in ../../decisions/ADR-010-lemmata-watches-writing-agents.md)"
  - "https://github.com/google-research/paper-orchestra at commit d9bae99, read in full 2026-11-19"
  - "../../decisions/ADR-010-lemmata-watches-writing-agents.md ; ADR-006, ADR-007, ADR-008, ADR-009"
  - "code on branch s30-baselines (stacked on s29-study-kind)"
last_reviewed: 2026-11-19
---
# Task: agents do the work, Lemmata shows it (S30 to S33)

- **Goal:** a researcher whose agents write code, run experiments and draft the paper can follow and steer that work
  from Lemmata at the level of intuition, and check any detail in one step.
- **Asked by:** Juhyeong, chat 2026-11-19. He approved the direction and asked for the plan to go to the CTO agent and
  for the work to start.
- **Owner:** CTO (plan, review). Built so far by the lead from the chat session.
- **Reviewer (QA):** QA agent, per sprint.
- **Rules that hold throughout:** no model on the hub; an agent proposes, rules check, the researcher confirms; every
  agent stage leaves a file; Lemmata gives evidence, not verdicts.

## S30. Baselines page and paper agents — built, needs QA
| Step | What | Done when |
|---|---|---|
| 1 | **Baselines page.** One row per compared method (from the result files, plus ones the researcher adds): paper and PDF link, code link, idea, where it falls short, how ours differs, and published numbers beside the project's own. The researcher's edit counts at once; an agent's card is a proposal. `/api/baselines`, MCP `baselines` and `propose_baselines`. | The researcher can open the PDF and the repository of every baseline from one table, and sees each published number next to the baseline's number in his own runs and his method's. |
| 2 | **Paper agents for Claude Code**, adapted from PaperOrchestra with a notice: outline, literature, figures, sections, review, revise, and the `/lemmata-paper` skill. `lemmata agents install <repo>`. | Installed into a research repository, `/lemmata-paper` stops for approval of the outline and each stage writes its record to `.lemmata/writing/`. |

Handoff: [S30-01](S30-01-handoff.md). Open: the VS Code extension has no command for the page or the install yet.

## S31. Steer at the level you can remember
| Step | What | Done when |
|---|---|---|
| 1 | **Storyline** at the top of Thesis: hook → gap → (their limit → our bridge) per line of work → claims. Extends the Problem record of S27 (gap, why it matters, approach, if solved) with the lines of work. Agent drafts, researcher confirms. | A lab member can retell `temporal_dependency` from the storyline alone, and every sentence opens the evidence behind it. |
| 2 | **One observation per experiment**: a sentence with its numbers, drafted by the agent, numbers checked by rule against the files (the S27 step 12 mechanism), confirmed by the researcher. | Changing a number in a copy of the result file marks the observation as disagreeing. |
| 3 | **Brief out, outline in.** `lemmata export materials` writes the brief the writing agents read (problem, claims with stages, setup, key numbers with their files, baselines). Lemmata reads `.lemmata/writing/outline.json`, links each bullet to a claim, run or number, and shows the outline for approval on the website as well as in Claude Code. | An outline bullet with no source is flagged; approving on the website sets `approved` for the agents. |

## S32. See what the agent wrote
Needs the paper's LaTeX in a repository Lemmata reads. Tracking of LaTeX changes has been paused since 2026-11-10;
Juhyeong decides whether to resume it.
| Step | What | Done when |
|---|---|---|
| 1 | **Work records.** Read `.lemmata/writing/worklog.jsonl`, `figures.json`, `reviews/`, `rounds/` like run manifests. Show per section, table and figure: who wrote it, when, from which evidence. Compute the difference between rounds by section and compare it with the agent's own account. | "The agent says it clarified 3.2; the difference also shows a changed number in Table 2" appears on Review for a planted case. |
| 2 | **Citation registry** from `citations.json` and the `.bib`: who added each reference, why, where it is used, verified or not, P0 or P1. Must-cite check: every baseline, dataset and measure in Setup has a P0 citation in the paper. | On `mcd_extension` every baseline and dataset shows cited / not cited / cited but not verified. |
| 3 | **Two claim rules.** A sentence that says the work beats a cited method needs that method as a row in a result table. A work dated after the project's cutoff is concurrent; a comparison against it is flagged. | Both fire on a planted sentence and stay silent on the unchanged paper. |
| 4 | **Limitation coverage.** Every claim at "not supported", every setting where ours is not best, every after-data deviation must be stated in the paper; a round that removes one is flagged. | On `temporal_dependency`, a draft that omits H2 or H3 fails. |

## S33. Close the loop to submission
| Step | What | Done when |
|---|---|---|
| 1 | **Review to tasks.** Read each review; sort every point by rule into answerable from existing evidence (with the run or number) or needs an experiment (to To-do, with the structured experiment prompt of S21). Same sorter for advisor feedback. | A review point about a missing ablation becomes a task with a prompt; one about a number already in the files links to it. |
| 2 | **Keep or revert by Lemmata's checks.** Per round: compiles, no new mismatch, no lost must-cite, no dropped limitation. The reviewer's score is shown as a line over rounds and decides nothing. | A round that raises the score and drops a limitation is marked "do not keep". |
| 3 | **Submission gate.** One page per project tied to the venue deadline: claims backed, numbers traced, must-cites present, limitations stated, anonymity, page limit, compiles. Venue rules as a `guidelines.md` beside each venue. | Each line is a rule with its evidence; nothing on the page is a model's opinion. |

## Later
- A seeded-fault benchmark for the 2nd and 3rd presentations (plant known faults in papers with public code, measure
  what Lemmata catches), and P0 citation recall as a metric.
- An importer for a finished PaperOrchestra run, if a demonstration is wanted (needs a paid Gemini or OpenAI key).
- Short names for datasets and the direct-interaction rules (project doc of 2026-11-19, not started).

## Needs Juhyeong
1. Approve ADR-010.
2. Resume LaTeX tracking for papers kept in GitHub (S32, S33)?
3. May the engine look references up online by default (OpenAlex and Crossref; today behind `--online`)?
4. Order of S31 to S33, if not the one above.
