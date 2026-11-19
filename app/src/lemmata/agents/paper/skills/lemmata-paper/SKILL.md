---
name: lemmata-paper
description: Draft or revise a research paper with the Lemmata paper agents, in stages the researcher can follow and steer. Use when the researcher asks to write, draft, restructure or revise the paper for a project that Lemmata tracks.
---
# Writing a paper with the Lemmata paper agents

Six agents write the paper in stages. You run the stages, stop where the researcher has to decide, and leave a record
of each stage in `.lemmata/writing/` so that Lemmata can show what was done, from what, and what changed.

The researcher keeps the intuition of the study in their head and cannot hold every proof, run and number. Your job is
to let them steer at that level and to make every detail checkable. Say plainly what you did and what you are unsure of.

## Before the first stage
1. Check that the Lemmata tools answer for this project (`list_projects`, `project_status`). If they do not, stop and
   say how to connect (`claude mcp add ... lemmata ...`, see Lemmata's docs).
2. Call `study`, `hypotheses`, `claims` and `key_numbers`. If the problem or the claims are not confirmed in Lemmata,
   say so and ask the researcher to confirm them first: an outline built on an unconfirmed thesis will be wrong.
3. Find the paper's LaTeX file, its `.bib` file and the venue's template and rules. Ask if you cannot tell which venue.
4. Make `.lemmata/writing/` if it is missing.

## The stages
| # | Stage | Agent | Stops for the researcher? |
|---|---|---|---|
| 1 | Outline | `paper-outline` | **Yes.** Show the storyline (hook, gap, each line of work with its limit and the bridge, the claims with their stages) and the section plan. Ask for changes. Set `approved` in `outline.json` only when they say yes. |
| 2 | Literature and figures | `paper-literature`, `paper-figures`, at the same time | Report what could not be found or traced. The baseline cards wait for the researcher on Lemmata's Baselines page. |
| 3 | Sections | `paper-sections` | Report numbers that had no source and sentences the agent was unsure of. |
| 4 | Review and revise | `paper-review`, then `paper-revise`; at most three rounds | **Yes, at the end.** Show each round's scores, what was fixed, and the list of points that need a new experiment. |
| 5 | Formatting | `paper-revise`, formatting pass | Report the status of every figure and table and the page count. |

Run one stage at a time. Give each agent the paths it needs, not a summary of the paper.

## Rules that hold in every stage
- **Lemmata is the source of truth** for claims, numbers, baselines and notation. Nothing is written from memory of the
  field or of an earlier draft.
- **A result that is not in a committed file is not written.** It is reported.
- **Limitations are written and stay written.** No stage removes one to improve a score.
- **Only verified references are cited.**
- **Do not commit, push, merge or submit anything unless the researcher asks.** Rounds are kept as copies under
  `.lemmata/writing/rounds/`. Submission is the researcher's act.
- Do not start experiments. A point that needs one becomes a task.

## The record
`.lemmata/writing/` holds: `outline.json`, `citations.json`, `figures.json`, `reviews/review_v<N>.json`,
`rounds/v<N>/` (the paper after each round) and `worklog.jsonl` (one line per stage or section: who, from what, what
they say they did, the checks, the outcome). Do not delete or rewrite earlier lines of the worklog.

## When everything is done
Tell the researcher, in this order:
1. What exists now (sections written, figures made, references cited) and whether it compiles within the page limit.
2. What they must look at themselves: the baseline cards to confirm, references that could not be verified, numbers
   with no source, sentences flagged as unsure.
3. What the review still criticises, and which points need a new experiment.
4. That the draft is theirs to read and change before anyone else sees it.
