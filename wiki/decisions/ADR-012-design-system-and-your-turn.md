---
type: adr
owner_agent: lead
status: accepted
sources:
  - "founder message in chat, 2026-11-22 16:20 KST: 'Consider the youtube links to make the Claude design for my Lemmata webiste UI/UX https://www.youtube.com/watch?v=-JabKCzBf4s, https://www.youtube.com/watch?v=9RUcYdww138 Check and report what changes can be made to Lemmata'"
  - "founder message in chat, 2026-11-22 16:28 KST: 'Proceed and let me see the updated UI/UX page considering the purpose of Lemmata. Send this to CTO agent so that they have the context of the Lemmata.'"
  - "founder message in chat, 2026-11-22 22:24 KST, answering the four decisions below after opening the canvas: 'proceed with your recommendation'"
  - "founder message in chat, 2026-11-22 22:27 KST: 'you proceed it to the task card and it is going to be done automatically'"
  - "../design/screens/S36-design-system.md (the rules, the token changes with their computed contrast, the mapping onto app.css at bc26f66)"
  - "../design/screens/S18-dais-ui.md (the 2026-11-12 spec, superseded for the website)"
  - "ADR-008-top-down-evidence-spine.md (Home, the sidebar shell) ; ADR-010-lemmata-watches-writing-agents.md (the researcher steers at the level of intuition) ; ADR-011-vscode-is-the-experiment-bench.md (the website is where you read, decide and write)"
  - "https://claude.ai/artifact/HxEcaEyC5TyewftJjPuEQ8 and https://claude.ai/artifact/2sZ1A8uRwM7E7NiHDYL6vY (the design system and the canvas the founder reviewed; private to him)"
last_reviewed: 2026-11-22
---
# ADR-012: One design system for the website; a page answers one question; sand means "your turn"

Status: **accepted** on 2026-11-22 22:24 KST. Juhyeong was shown the design system and a canvas with Home, Thesis and
Review, was asked four questions with a recommended answer each, and answered "proceed with your recommendation".
Build: [S36-01](../sprints/S36/S36-01-task.md). Nothing is built yet.

## Context
- The website's only written style rules are in [S18-dais-ui.md](../design/screens/S18-dais-ui.md) (2026-11-12): one column, one
  band, four nav items, no sidebar. The site has since gained a sidebar and Home (ADR-008), the Setup board, Baselines,
  LaTeX, Settings and a dark theme. S18 does not describe any of them.
- S18 has no filled button in a colour of its own. `.btn.primary` fills with `--text` and is used at thirteen call sites in
  `app.js` and `research.js` at bc26f66, from confirming a claim to "Next" in the tutorial. The one thing only
  the researcher can do does not look different from the rest.
- State tags are the smallest and palest text on a row (12.8px; `--muted-light` is 2.65:1 on `--bg`), and `--muted` is
  4.27:1 on `--bg`. In the dark theme `--warning` and `--highlight` have almost the same lightness.
- Juhyeong asked for the website's UI/UX to be made with Claude Design, with two videos as method references. Both say the
  same thing: settle the rules before the screens.

## Options
1. Keep S18 and patch each page as it comes up. Cheapest now; the pages keep drifting.
2. Rewrite S18 as prose again. Covers the new pages, but the founder approves by reading, not by looking.
3. **A design system kept as tokens, rules and drawn screens, approved by looking at a canvas, then built onto the classes
   that exist.** Chosen.

## Decision
1. **The rules of [S36-design-system.md](../design/screens/S36-design-system.md), section 3, are the website's rules.** S18
   Part 1 is superseded; S18 Part 2 (VS Code) stays.
2. **Sand is the one your-turn colour** (founder's decision 1). `--highlight` fills the action only the researcher can take
   and marks the items waiting for them, each with a `--highlight-edge` line. It is used for nothing else. `.btn.primary`
   takes this look and is kept only on such actions.
3. **Home is a list, not tiles** (decision 2): Needs you, Since you last looked, This month.
4. **The claims tree uses straight lines, with each node's name and state in words beside it** (decision 3).
5. **Dark theme: the shipped values stay wherever they pass contrast** (decision 4). Checked on 2026-11-22: all shipped
   text colours pass; one value changes (`--warning`, because it cannot be told from `--highlight`) and two are added.
6. **Every page opens with its question and the answer in one line.**
7. **UI handoffs show before and after side by side, and name any reference a pattern was taken from.**

Items 6 and 7 were not among the four numbered questions. They were in the report and the canvas Juhyeong read before
answering, and are recorded here so the build has one place to point to.

## Consequences
- `--muted`, `--warning` and `--fs-tag` change value, and two tokens are added. No token is renamed.
- Some buttons lose the filled look. This is intended: the fill now carries a meaning.
- Home needs to know when the researcher last looked, and who made each change (an agent, a run, the hub). Where the hub
  does not record one of these yet, the task card says what to show instead.
- The design system and the canvas are Claude artifacts private to Juhyeong. The repository copy in `wiki/design/screens/`
  is the one agents read. If the two differ, the repository copy holds.
- Not decided here: the layouts of Setup, Trail, Baselines, LaTeX and Settings beyond their page head; the focus chip, the
  jump box and table controls of the 2026-11-19 direct-UI package; short dataset names.
