---
type: handoff
owner_agent: lead
status: needs-qa
sources:
  - "founder message in chat, 2026-11-19 23:53 KST ('Regarding the homepage, make the website so that when I click on Lemmata, it goes back to the original page. Also, on the bottom left, I want a button for settings that has all the FAQs, how the Lemmata works, and the dark/light mode, something like what Claude settings have. I can not see the baseline page on the side. Also, for the decisions, proceed with what you think is the best. Also for Latex tracking, it is not available ... I want a skill for Lemmata to create such latex code for writing tables, paragraphs, captions that considers the whole context and every detail of the work that has been done so far. This should be with the help of an agent inside Lemmata linked with one's agent like claude. For me, I should be using my Opus model ... so that I can directly copy and paste them. Yes look references up online by default.')"
  - "../S30/S30-brief.md (the task card; S31 section) ; ../../decisions/ADR-010-lemmata-watches-writing-agents.md (accepted)"
  - "https://code.claude.com/docs/en/sub-agents (fetched 2026-11-19: the model field of an agent file)"
  - "the hub at http://100.111.135.94:8765, looked at from the founder's browser on 2026-11-20 00:0x KST: /api/hub/status answered (version 0.1.0, private mode); the browser was not a paired device, so the pages themselves could not be read"
  - "code on branch s30-baselines: app/src/lemmata/engine/{texout,api}.py, server.py, mcp.py, cli.py, hub/{projects,config,cli,routes}.py, agents/, web/{app.js,research.js,app.css,tokens.css,hub/hub.js,hub/hub.css}, desktop/launcher/tokens.css, app/tests/{test_texout,test_agents,test_hub,test_mcp}.py"
last_reviewed: 2026-11-20
---
# S31-01: Settings and dark mode, the title goes Home, LaTeX to paste, online references by default

Asked by Juhyeong (chat, 2026-11-19 23:53 KST). Built from the chat session as further commits on `s30-baselines`
(not a new branch, so that one command on the Mac mini brings S30 and S31), and pushed to `next` as well. Nothing is
merged to main. Plan: [S30 brief](../S30/S30-brief.md), section S31.

## "I can not see the baseline page on the side"
Not reproduced, and not explained from here. In the code of `s30-baselines` the page is the first entry under Explore
in the sidebar. Three things can hide it, in order of likelihood:
1. **The hub has not updated to the branch.** It follows whichever branch was last given to
   `lemmata hub autoupdate install --branch …`. The hub answered from Juhyeong's browser, but that browser is not a
   paired device, so which build it runs could not be read.
2. **The window is 1000 px wide or less.** The sidebar is hidden there by design and its pages are footer links.
3. Not a stale script: the server sends `no-store`.

What S31 changes so this can be answered from the website: Settings → About names the branch and commit the hub runs;
Setup has a "Baselines →" link; narrow windows get a Settings button at the bottom left.

## What changed
### Shell
- **The title "Lemmata" is a button**: Home in a project, the project list on a hub with no project open.
- **Settings** (`pageSettings`): one page, six sections. Appearance (system, light, dark; kept in the browser; the VS
  Code tab follows the editor instead). Project (sync, export, paper source: what the Project menu held). Agents for
  Claude Code (a prompt that installs the agents; a link to LaTeX). How Lemmata works (the three steps and the
  walkthrough). FAQ (the whole FAQ, with its filter). About (the hub's branch, commit and last update, for a signed-in
  device).
- **Where the button is**: the foot of the sidebar, pinned to the bottom left; in windows without a sidebar, a fixed
  button at the bottom left. FAQ and "How Lemmata works" left the sidebar; the FAQ page itself still opens from search.
- **Dark set** in `tokens.css` under `:root[data-theme="dark"]`, same sage family. Two new tokens, `--on-accent` and
  `--on-accent-muted`, carry text on the header band (it used the page colour, which is dark in the dark set). The hub's
  own pages follow the same choice. The desktop launcher's copy of the tokens is kept identical.

### LaTeX to paste (`engine/texout.py`, new; the existing `engine/latex.py` is the LaTeX reader and is unchanged)
- **Tables by rule**: each experiment's table as booktabs LaTeX, from the Setup document, with no model. Best per
  column in bold by the measure's direction, the project's own method last, names escaped, missing cells as `--`,
  turned on its side when there are more than 12 datasets.
- **Requests**: kind (table, paragraph, caption, other), about (the project, an experiment, a claim), and the
  researcher's words. They wait for the researcher's agent.
- **The brief** (`latex_brief`): the guide, the request, the thesis, every claim with its stage, every experiment with
  its protocol, numbers and table by rule (the asked-about one first), the setup, the key numbers, the baseline cards
  with published numbers, the notation, the citation keys, what was already written.
- **Snippets** (`submit_latex`): kept with title, sources, notes, who and when. **Checked by rule each time the page
  is read**: environments and braces close; no other file is pulled in; every decimal number (and whole number with a
  percent sign) is looked up among the numbers the project holds (experiment tables, per-method cells, key numbers,
  hypothesis results, published numbers on baseline cards), at the printed precision; citation keys against the
  bibliography when there is one. A number that was found when the snippet was written and is not found now makes it
  **stale**.
- **Page**: sidebar → Work → LaTeX. Ask; open requests with a prompt for Claude Code; written snippets with status,
  the code and Copy; tables by rule with Copy.
- **API / MCP**: `GET /api/latex`, `POST /api/latex` (request, submit, remove, reopen). MCP `latex` (open requests; a
  request's brief; or an ad hoc brief) and `submit_latex` (answers with what the check found, so the agent can fix and
  resubmit).

### Agents
- `agents/latex/`: the `lemmata-latex` agent with `model: opus` (read-only tools and Lemmata's; it cannot edit the
  paper or the repository) and the `/lemmata-latex` skill.
- `lemmata agents install` now installs every kit by default (`--kit latex|paper|all`).
- MCP `agent_kit`: the agent files as paths and contents, so Claude Code on a GPU server can write them into `.claude/`
  with one prompt and no checkout of Lemmata. The licence and notice of the paper agents travel the same way.

### References online by default
- A served hub looks references up online (titles and DOIs to OpenAlex and Crossref) unless a project turns it off or
  the hub is configured with `--online-refs off`. A hub object built in code or in a test stays offline.
- Local `open`, `serve`, `scan` and `checkpoint` are online unless `--offline`.

## Verified
- Python: 224 passed, 2 skipped (8 new: `test_texout` 5, `test_agents` 1, `test_hub` 2).
- Browser (headless Chromium) on the `test_map` project at 1360, 760 and 420 px, light and dark: sidebar order with
  Baselines first under Explore and Settings at the bottom left; title → Home; Setup → Baselines; Settings sections,
  26 FAQ questions; theme switch, kept after reload; install prompt and a snippet copied to the clipboard; ask creates
  a request; a table by rule opens; the narrow-window Settings button opens Settings. No console errors, no sideways
  scroll. [Screenshots](screenshots/).

## Not verified
- **The Mac mini hub**: whether it has updated, the About row with real update data, the online lookup against the
  real services (tests replace the network call).
- `mcd_extension` and `temporal_dependency`: tables by rule on real result files, in particular the 61-dataset case.
- The agents in a real Claude Code session: that `model: opus` is honoured, that `agent_kit` output is written
  correctly, the quality of the LaTeX.
- VS Code: the tab has no Settings button of its own (it has the footer link) and does not use the dark set.
- The number check is coarse on purpose: a printed number counts as found if any number the project holds rounds to
  it. It catches a mistyped or invented number; it cannot tell that a correct number sits in the wrong cell.

## Mistake made and undone during the build
The new module was first written to `engine/latex.py`, which already exists (the LaTeX reader), and replaced it. The
import error showed it at once; the file was restored from git unchanged and the new module became `texout.py`.

## Deploy
On the Mac mini, once: `uv run lemmata hub autoupdate install --branch next`. `next` holds the same commits as
`s30-baselines` and will receive each later sprint, so the command is not needed again.
Agents: in Lemmata, Settings → Agents for Claude Code → Copy install prompt, pasted in Claude Code in the research
repository. Claude Code must be connected to Lemmata under the name `lemmata`.

## Open questions
- Keep `next` as the branch the hub follows (preview; main still needs QA and Juhyeong).
- Should stale snippets appear on Home's to-do list?
