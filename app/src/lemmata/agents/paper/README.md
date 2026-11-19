# Lemmata paper agents (for Claude Code)

Six agents and one skill that draft and revise a research paper in stages, from what Lemmata holds about the project.
They run in your own Claude Code session, on your own plan. Lemmata's hub runs no model.

| Agent | Does |
|---|---|
| `paper-outline` | Plans the paper from the confirmed claims, experiments and numbers. You approve the plan. |
| `paper-literature` | Finds and verifies references, records why each is cited, proposes the baseline cards, writes Introduction and Related Work. |
| `paper-figures` | Draws each planned figure with a script that reads your result files, and keeps the script. |
| `paper-sections` | Writes the remaining sections, with every number taken from a file and limitations stated. |
| `paper-review` | Reviews the draft as a conference reviewer would. |
| `paper-revise` | Answers the review; keeps a revision only if the paper stays consistent with the evidence; formatting pass. |

The skill `/lemmata-paper` runs them in order and stops where you have to decide.

## Install into a research repository
```
lemmata agents install /path/to/your/research-repo
```
This copies the agents to `.claude/agents/` and the skill to `.claude/skills/lemmata-paper/` in that repository, and
the notice and licence to `.claude/lemmata-paper-agents/`. It overwrites nothing unless you pass `--force`. Claude
Code must already be connected to Lemmata (`claude mcp add ... lemmata ...`); the agents call its tools as
`mcp__lemmata__*`.

Then, in Claude Code in that repository: `/lemmata-paper`, or ask for one stage ("use paper-outline to plan the paper").

## What it leaves behind
`.lemmata/writing/` in the research repository: `outline.json`, `citations.json`, `figures.json`,
`reviews/review_v<N>.json`, `rounds/v<N>/` and `worklog.jsonl`. These are the records Lemmata reads to show what the
agents did.

## What it does not do
It does not commit, push or submit. It does not start experiments. It does not write a result that is in no committed
file. It does not remove a limitation.

Adapted from PaperOrchestra (Google LLC, Apache-2.0). See `NOTICE.md` for the source and for what was changed.
