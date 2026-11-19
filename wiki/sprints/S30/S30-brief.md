---
type: task-card
owner_agent: cto
status: in-progress
sources:
  - "founder messages in chat, 2026-11-19 17:41, 17:53 and 17:59 KST (quoted in ../../decisions/ADR-010-lemmata-watches-writing-agents.md)"
  - "https://github.com/google-research/paper-orchestra at commit d9bae99, read in full 2026-11-19"
  - "../../decisions/ADR-010-lemmata-watches-writing-agents.md ; ADR-006, ADR-007, ADR-008, ADR-009"
  - "code on branch s30-baselines (stacked on s29-study-kind)"
last_reviewed: 2026-11-20
---
# Task: agents do the work, Lemmata shows it (S30 to S34)

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

## S31. Settings, LaTeX to paste, online references — built, needs QA
Asked in chat on 2026-11-19 23:53 KST. Handoff: [S31-01](../S31/S31-01-handoff.md).
| Step | What | Done when |
|---|---|---|
| 1 | **The title goes Home.** A **Settings** button at the bottom left opens one page: theme (system, light, dark), project, agents for Claude Code, how Lemmata works, the FAQ, and which build the hub runs. | From any page, the title returns to Home; the theme survives a reload. |
| 2 | **Baselines can be found**: sidebar, a link on Setup, the footer in narrow windows; Settings names the branch and commit the hub runs. | "I do not see the page" can be answered from the website. |
| 3 | **LaTeX to paste.** Tables by rule from the result files. Requests the researcher writes in Lemmata; the brief Lemmata builds; the LaTeX their agent hands back, kept with sources and checked (form, numbers against the files, citation keys); stale when the files change. `/api/latex`, MCP `latex` and `submit_latex`. | A table asked for in Lemmata comes back from Claude Code and is copied with one click; a wrong number is named. |
| 4 | **`lemmata-latex` agent on Opus** and the `/lemmata-latex` skill; `agent_kit` hands every agent file to Claude Code through the hub. | The agents are installed in a research repository on a GPU server with one prompt. |
| 5 | **References looked up online by default** on a served hub. | A new project on the hub shows matched references without a setting being touched. |

## S32. Steer at the level you can remember
| Step | What | Done when |
|---|---|---|
| 1 | **Storyline** at the top of Thesis: hook → gap → (their limit → our bridge) per line of work → claims. Extends the Problem record of S27. Agent drafts, researcher confirms. | A lab member can retell `temporal_dependency` from the storyline alone, and every sentence opens the evidence behind it. |
| 2 | **One observation per experiment**: a sentence with its numbers, drafted by the agent, numbers checked by rule against the files, confirmed by the researcher. | Changing a number in a copy of the result file marks the observation as disagreeing. |
| 3 | **Write from where you are.** A "LaTeX" action on every experiment, claim and baseline row that opens a request already filled in; a snippet shows on the experiment or claim it is about. | Asking for an experiment's table takes one click from Setup. |
| 4 | **Check what I pasted.** A box that takes a paragraph or table pasted back from Overleaf and runs the same checks. This replaces tracking of the paper's LaTeX. | A pasted table with one changed number names that number. |

## S33. See what the agents did
| Step | What | Done when |
|---|---|---|
| 1 | **Work records.** Read `.lemmata/writing/` (worklog, figures, reviews, rounds) like run manifests. Per snippet, section and figure: who wrote it, when, from which evidence; the agent's own account beside the real difference. | A planted case, "the agent says it clarified 3.2; a number in Table 2 also changed", appears on Review. |
| 2 | **Citation registry** from the agents' `citations.json` and the bibliography when there is one: who added each reference, why, where used, verified online or not, must-have or not. Every baseline, dataset and measure in Setup needs a must-have citation. | On `mcd_extension` every baseline and dataset shows cited / not cited / not verified. |
| 3 | **Two claim rules and limitation coverage**, applied to snippets and to pasted or uploaded text: "beats X" needs X in a result table; a later work is concurrent; every "not supported" claim and after-data deviation must be stated. | A `temporal_dependency` paragraph that omits H2 or H3 is flagged. |

## S34. Close the loop to submission
| Step | What | Done when |
|---|---|---|
| 1 | **Review to tasks.** Each review point sorted by rule into answerable from existing evidence or needs an experiment (To-do, with a structured prompt). Same sorter for advisor feedback. | A missing-ablation point becomes a task with a prompt. |
| 2 | **Submission gate.** The researcher downloads the Overleaf source as a zip and uploads it (the hub already takes a zip). One page tied to the venue deadline: claims backed, numbers traced, must-cites present, limitations stated, anonymity, page limit; snippets that are stale; venue rules as a `guidelines.md` per venue. | Each line is a rule with its evidence. |

## Later
- Short names for datasets and the direct-interaction rules (project doc of 2026-11-19, not started).
- A seeded-fault benchmark for the 2nd and 3rd presentations, and must-have citation recall as a metric.
- An importer for a finished PaperOrchestra run, if a demonstration is wanted (needs a paid Gemini or OpenAI key).

## Needs Juhyeong
Decided on 2026-11-19 23:53 KST: ADR-010 accepted; no LaTeX tracking, LaTeX is made in Lemmata instead; references
looked up online by default; order of the sprints left to the lead (the one above).

Done under "proceed with what you think is the best": a branch `next` that receives every sprint after its tests pass, for
the hub to follow, so that a new sprint needs no command on the Mac mini. It is a preview; main still needs QA and
Juhyeong. Say so if you would rather keep one branch per sprint on the hub.
