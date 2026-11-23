---
type: adr
owner_agent: lead
status: accepted (points 1 to 5, founder in chat 2026-11-23); point 6 proposed
sources:
  - "founder messages in chat, 2026-11-23 17:12, 17:16, 17:22, 17:29 and 17:32 KST, quoted in ../sprints/S37/S37-01-task.md"
  - "founder message in chat, 2026-11-23 17:34 KST, after hearing that the build had not started: 'just make it.'"
  - "ADR-009-study-kind-and-key-numbers.md (kinds of study) ; ADR-011-vscode-is-the-experiment-bench.md (VS Code is the experiment bench) ; ADR-006-public-multi-user-site.md (no model on the hub)"
  - "https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git-integration (read 2026-11-23): Git integration is available if the project owner has a paid subscription"
last_reviewed: 2026-11-23
---
# ADR-013: Survey papers: the writing is the hub; edit one sentence, see every place that still says the old words

Status: points 1 to 5 **accepted** on 2026-11-23 (the founder's own words, quoted in [S37-01](../sprints/S37/S37-01-task.md)).
Point 6 is **proposed**: it was built in S37-01 so the founder can work from the public address, and needs his yes.

## Context
Juhyeong writes a survey with no experiment section (ODAD, in Overleaf). A survey repeats its facts: a term, a symbol, a
count, the category a surveyed model sits in. They appear in the text, the summary tables, the taxonomy and the captions.
He wants to edit one sentence and see where else the change must be applied. ADR-009 knew only method papers and benchmark
studies; ADR-011 took paper findings out of VS Code; Overleaf had been dropped in S06 as a paid feature. The survey's Overleaf
project, owned by the lab's account, turned out to offer Git (Integrations → Git shows a clone link), because Overleaf ties
Git to the project owner's plan.

## Decision
1. **A third kind of study, survey.** No "ours", no runs. Chosen by the researcher, or by rule Y5: a paper next to repositories
   that hold no code and no result files.
2. **The writing is the hub.** The paper's versions are what Lemmata compares. The survey's GitHub repository is a supplement:
   its model and dataset tables are read against the paper; the paper is the reference; Lemmata never writes to it.
3. **The paper comes from Overleaf's Git** when the project offers it; a zip upload stays as the fallback. The hub only reads
   from Overleaf.
4. **Changes to apply**: every change since the version the researcher confirmed, each with the places that still say the
   old words. Rules only, no model: a replaced term is looked for everywhere in the paper; a fact about a model, a cited paper
   or a symbol only where the same model, paper or symbol appears (text, table rows, forest nodes, the GitHub lists); a number
   before the same word; a removed label still referenced. Each row can be marked fixed or left as is; confirming a version
   moves the comparison forward.
5a. **For a survey, the claims and the taxonomy come first** (founder, 18:08 KST). The researcher's own agent reads the whole paper
   (MCP `survey_brief`) and proposes the thesis, the research questions, the key claims with quotes, and the taxonomy
   (`propose_survey_map`); rules check every quote, cite key and model name; the researcher confirms. For a survey the Thesis page
   shows this map, which claims rest on sentences that changed, and where the paper places a model in another category.
5. **VS Code gets a separate Survey panel** focused on the writing (not built yet; S37-01 phase 4). ADR-011 stays as it is
   for method papers and benchmark studies.
6. (proposed) **The hub's owner may switch Overleaf on and save the Overleaf Git token from the website, also through the
   public address.** Until S37 these routes answered only on the private address. The owner's session is a GitHub sign-in over
   https; every other account still gets 404; the token is still never echoed back.

## Consequences
- Experiment pages read a survey like a benchmark study (nothing is "ours").
- A project map cannot set "survey" (MAP_KINDS stays method and benchmark).
- Applying fixes back to Overleaf (S37-01 phase 2b), the meaning pass through the researcher's agent, and the VS Code panel
  are later steps of the same card.
