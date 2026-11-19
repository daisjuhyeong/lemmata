---
type: adr
owner_agent: lead
status: accepted
sources:
  - "founder messages in chat, 2026-11-19: 17:41 KST ('Consider the work from google research ... analyze what we can take from here'); 17:53 KST ('I want Lemmata to assist and submit research papers with the help of an agent, which aligns with PaperOrchaestra, although it conflicts into to how an agent can help. I also use agents to do most of the works so Lemmata is closer to monitoring the works of the agents visible to a researcher so that they can fully understand and comprehend the research that is going on because one cannot memorize every mathematical proof, experiment, and results; only thing that can be memorized is the intuition of the study.'); 17:59 KST ('I agree with withdraw. For the reference, I want a separate section (page) where I can organize the baselines in a table with an option for me to check the paper's pdf, github code, and its intutition and published performance so that I can track it for our methodology. I want it to be reused as Claude code agents instead. Plan and send it to the CTO agent, and proceed with the work.'). No file in raw/ yet"
  - "founder message in chat, 2026-11-19 23:53 KST: 'for the decisions, proceed with what you think is the best. Also for Latex tracking, it is not available because I think tracking latex code from Overleaf needs a subscription. Rather, I want a skill for Lemmata to create such latex code for writing tables, paragraphs, captions that considers the whole context and every detail of the work that has been done so far. This should be with the help of an agent inside Lemmata linked with one's agent like claude. For me, I should be using my Opus model to generate latex code for summarizing or organizing my experimental results into latex code format so that I can directly copy and paste them. Yes look references up online by default.' No file in raw/ yet"
  - "https://github.com/google-research/paper-orchestra at commit d9bae99 (read in full 2026-11-19): README.md, methods/, methods/prompts/, autoraters/, utils/, LICENSE (Apache-2.0)"
  - "https://arxiv.org/abs/2604.05018 (abstract) and https://yiwen-song.github.io/paper_orchestra/ (project page), fetched 2026-11-19"
  - "https://code.claude.com/docs/en/sub-agents (fetched 2026-11-19: a subagent is a Markdown file with YAML frontmatter in .claude/agents/; fields name, description, tools, model; tools may name an MCP server as mcp__server__*)"
  - "ADR-006-public-multi-user-site.md (no language model on the hub) ; ADR-007-project-map-two-phases.md (an agent proposes, rules check, the researcher confirms) ; ADR-009-study-kind-and-key-numbers.md"
  - "code on branch s30-baselines: app/src/lemmata/engine/baselines.py, app/src/lemmata/agents/, app/tests/{test_baselines,test_agents}.py"
last_reviewed: 2026-11-19
---
# ADR-010: Lemmata watches the agents that do the research work; paper agents adapted from PaperOrchestra; a Baselines page

Status: **accepted** on 2026-11-19 23:53 KST. Juhyeong stated items 1 to 4 in chat and, asked to approve this record,
answered "for the decisions, proceed with what you think is the best". Items 6 to 8 were added from the same message. Plan and task card: [S30 brief](../sprints/S30/S30-brief.md). First build: [S30-01](../sprints/S30/S30-01-handoff.md).

## Context
- Juhyeong's own agents do most of the work of a project: code, runs, and the paper. A person cannot hold every
  proof, experiment and result; they hold the intuition of the study.
- PaperOrchestra (Google Cloud AI Research) turns an idea file and an experimental log into a paper with five LLM
  agents. In its code the researcher supplies the inputs and receives the PDF; nothing is approved in between, numbers
  are kept consistent by instruction only, and the revision prompt forbids stating limitations.

## Decision
1. **Lemmata's job is to make the agents' work visible and checkable to the researcher**, at the level of intuition
   first and with every detail one step below. Writing a paper with agents is in scope as something Lemmata watches
   and steers. This replaces the earlier wording "use AI, not depend on AI" as the product line.
2. **The hub still runs no model** (ADR-006). Agents run in the researcher's own Claude Code session.
3. **PaperOrchestra's prompts are reused as Claude Code agents**, shipped in `app/src/lemmata/agents/paper/` under
   Apache-2.0 with a notice of what was changed, and installed into a research repository with
   `lemmata agents install`. Changes that are not negotiable: a person approves the outline; limitations are written
   and kept; no citation quota; plots come from scripts that read committed files; a revision is kept on Lemmata's
   checks, not on a simulated reviewer's score; a request for a new experiment becomes a task.
4. **A Baselines page**: one row per compared method with its paper and PDF link, code link, the idea, where it falls
   short, how the work differs, and the numbers its paper reports beside what the project measured. The researcher's
   own edit counts at once; an agent's card is a proposal the researcher confirms. Lemmata opens no link and gives no
   verdict on a difference.
5. **Every agent stage leaves a record** in `.lemmata/writing/` of the research repository (outline, citations,
   figures, reviews, rounds, worklog). Lemmata will read these the way it reads run manifests (planned, S32).

6. **Lemmata does not track the paper's LaTeX.** The paper is in Overleaf, which cannot be read without a paid plan.
   Lemmata is instead where LaTeX is made: tables built by rule from the result files, and tables, paragraphs and
   captions the researcher asks for, written by their own agent from Lemmata's brief, kept with their sources and
   checked by rule (S31). A snippet whose numbers leave the result files is marked stale; that is how the researcher
   learns that something already pasted is out of date. A full check of the paper happens when the researcher uploads
   the Overleaf source as a zip, which the hub already accepts.
7. **The LaTeX agent runs on Opus** in the researcher's own Claude Code (`model: opus` in the agent file). The agent
   files reach Claude Code through the hub (`agent_kit`), so no checkout of Lemmata is needed on the research machine.
8. **References are looked up online by default** on a served hub (titles and DOIs to OpenAlex and Crossref). A project
   can turn it off; `lemmata hub config --online-refs off` turns the default off.

## Consequences
- Third-party text now lives in the repository. `NOTICE.md` and the licence must travel with the agent files; the
  installer copies both.
- The agents call the Lemmata MCP server by the name `lemmata`. A researcher who registered it under another name must
  edit the `tools` line.
- A published number on the Baselines page is as good as whoever typed it. The page shows who filled each card and
  links each number to its source so the researcher can check it; it does not verify it.
- CLAUDE.md's "Scope (current)" section predates this and should be updated by Juhyeong.

## Not decided here
- Whether the hub should follow one long-lived preview branch, so that a new sprint does not need a command on the Mac mini.
