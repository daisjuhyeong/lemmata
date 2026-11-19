# Notice

The agents in this folder are adapted from **PaperOrchestra**, © 2026 Google LLC, licensed under the Apache License,
Version 2.0 (`LICENSE-APACHE-2.0` in this folder). Source: https://github.com/google-research/paper-orchestra at
commit `d9bae99` (2026-11-15). Paper: Song, Song, Pfister, Yoon, *PaperOrchestra: A Multi-Agent Framework for Automated
AI Research Paper Writing*, arXiv:2604.05018. PaperOrchestra is not an officially supported Google product, and this
adaptation is not affiliated with or endorsed by Google.

| File here | Adapted from |
|---|---|
| `agents/paper-outline.md` | `methods/prompts/outline_agent.py` |
| `agents/paper-literature.md` | `methods/prompts/literature_review_agent.py`, `methods/agents/literature_review_agent.py` |
| `agents/paper-figures.md` | `methods/agents/plotting_agent.py` (the plan, critique and caption loop) |
| `agents/paper-sections.md` | `methods/prompts/section_writing_agent.py` |
| `agents/paper-revise.md` | `methods/prompts/content_refinement_agent.py`, `methods/prompts/format_agent.py` |
| `agents/paper-review.md`, `skills/lemmata-paper/SKILL.md` | the order of stages in `methods/paper_writer.py` |

## What was changed
The prompts were rewritten as Claude Code agents (2026-11-19). The structure of the stages and several rules are
PaperOrchestra's; the wording and the following are Lemmata's.

- **Inputs.** The agents read the project's confirmed claims, experiments, key numbers, baselines and notation from
  Lemmata instead of two hand-written files (`idea.md`, `experimental_log.md`).
- **A person approves the outline** before anything is written. The original runs from inputs to PDF without a stop.
- **Limitations.** The instruction never to state a limitation is removed. The agents must write limitations, keep
  them through revisions, and report results that did not support a claim.
- **Citations.** The requirement to cite at least 90% of the collected papers is removed; a paper is cited where a
  sentence needs it. Every kept reference is recorded with the reason it is cited and the index record that confirms it.
- **Figures.** Plots are drawn by scripts kept in the repository that read the committed result files. Model-written
  code is not executed inside a server, and results are not drawn by an image model.
- **Revision.** A revision is kept when it leaves the paper consistent with the evidence (it compiles, no new
  mismatch, no lost limitation), not when a simulated reviewer's score rises. The score is recorded only.
- **Requests for new experiments** are recorded as tasks instead of being ignored.
- **Records.** Every stage writes what it did, and from what, to `.lemmata/writing/`.
- **Left out.** The instruction to write as if with no prior knowledge (it served the original's benchmark), the
  instruction to fill in author names, the few-shot figure retrieval, and the reviewer rubric (the original takes it
  from AgentReview; the review form here was written for Lemmata).
- **Models.** The original calls Gemini or OpenAI models from its own process. These agents run in the researcher's
  own Claude Code session.
