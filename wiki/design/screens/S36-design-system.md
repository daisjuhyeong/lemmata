---
type: screen-spec
owner_agent: designer
status: approved (founder, chat 2026-11-22 22:24 KST); phase 1 built 2026-11-22, phase 2 not started
sources:
  - "founder message in chat, 2026-11-22 16:20 KST: 'Consider the youtube links to make the Claude design for my Lemmata webiste UI/UX https://www.youtube.com/watch?v=-JabKCzBf4s, https://www.youtube.com/watch?v=9RUcYdww138 Check and report what changes can be made to Lemmata'"
  - "founder message in chat, 2026-11-22 16:28 KST: 'Proceed and let me see the updated UI/UX page considering the purpose of Lemmata. Send this to CTO agent so that they have the context of the Lemmata.'"
  - "founder message in chat, 2026-11-22 22:24 KST, after opening the canvas: 'proceed with your recommendation'"
  - "founder message in chat, 2026-11-22 22:27 KST: 'you proceed it to the task card and it is going to be done automatically'"
  - "https://claude.ai/artifact/HxEcaEyC5TyewftJjPuEQ8 (Lemmata Design System, made 2026-11-22; private to the founder)"
  - "https://claude.ai/artifact/2sZ1A8uRwM7E7NiHDYL6vY (canvas with Home, Thesis and Review, sample data; private to the founder)"
  - "https://www.youtube.com/watch?v=-JabKCzBf4s (Eric Park; description and auto-generated Korean captions read 2026-11-22)"
  - "https://www.youtube.com/watch?v=9RUcYdww138 (IDEAiPlus; description and auto-generated Korean captions read 2026-11-22)"
  - "../../../app/src/lemmata/web/tokens.css, app.css, app.js, research.js at commit bc26f66 (branch next); line numbers below are from that commit"
  - "S18-dais-ui.md (the 2026-11-12 spec this page replaces for the website; its VS Code part stays)"
  - "../../decisions/ADR-008-top-down-evidence-spine.md (Home, Thesis, Setup, Review, Trail; the sidebar shell) ; ../../decisions/ADR-011-vscode-is-the-experiment-bench.md (the website is where you read, decide and write)"
  - "https://www.w3.org/TR/WCAG21/#contrast-minimum and #non-text-contrast (4.5:1 for text, 3:1 for large text and for graphics and control edges); every ratio on this page was computed on 2026-11-22 with that document's relative-luminance formula"
last_reviewed: 2026-11-22
---
# S36 design system: one question per page, and one colour that means "your turn"

Decision record: [ADR-012](../../decisions/ADR-012-design-system-and-your-turn.md). Task card: [S36-01](../../sprints/S36/S36-01-task.md).
This page replaces Part 1 (website and app) of [S18-dais-ui.md](S18-dais-ui.md). Part 2 of S18 (VS Code) stays.

**Not checked.** The live site was not opened: the hub was not reachable from the chat session. The canvas was written to its
format's rules and reviewed by the founder; its author did not render it. Where the canvas and this page differ, this page
is the source. The canvas uses the sample project's numbers plus invented sample rows.

## 1. What Lemmata is for
- Agents run most of the experiments and write most of the drafts. The researcher holds the intuition of the study, not every
  proof, run and number (founder, 2026-11-19, recorded in ADR-010).
- Lemmata keeps one picture: each claim, the evidence under it, and what changed since the researcher last looked. It shows
  evidence and gives no verdict. An agent proposes, rules check, the researcher confirms.
- The website is opened for a minute or two between other work. It is where the researcher reads, decides and writes (ADR-011).

So a page has two jobs: answer the question the researcher came with, and show the few things only they can settle.

## 2. Why the S18 spec no longer covers the site
S18 says one column, one band, four nav items, no sidebar. Since then the site gained a left sidebar and Home (ADR-008), the
calendar, the Setup board (S28), Baselines (S30), LaTeX, Settings and a dark theme (S31). None of these has a written rule.

Three things were taken from the two videos the founder named:
1. Fix the rules first and build every screen from them (IDEAiPlus).
2. Keep the main action's colour for that action only, and write that down as a rule (Eric Park).
3. Show old and new side by side, and name the reference a pattern came from (Eric Park).

Not taken: decorative styles, illustrations, avatars, and paid reference libraries.

## 3. The ten rules
1. **A page answers one question.** The heading is the question; the first line is the answer with its numbers.
2. **Sand means it is your turn.** `--highlight` fills the one action only the researcher can take, and marks the items
   waiting for them. It is used for nothing else.
3. **State is a dot and a word.** Hollow ring: hypothesis. `--success`: backed. `--warning`: stale. `--error`: mismatch.
   `--highlight`: your turn. No filled badges, no coloured rows.
4. **The action sits on the row.** What waits for the researcher carries its own Confirm, Fix or Snooze.
5. **Three levels.** A short name, one line on expand, full detail with sources. Detail opens in place.
6. **Every number links to its file.**
7. **Lemmata speaks only when the researcher has to act.** Checks and notes live on Review.
8. **Information is never smaller than 13px or paler than `--muted`.**
9. **Hairlines, not boxes.** No cards, no shadows, no gradients, no corner above 2px, no icons in navigation, no emoji.
10. **Every colour and size is a token.** A hex value outside the token files is a bug. (`app.css`, `app.js` and
    `research.js` hold none at bc26f66; keep it so.)

Rules 1, 5, 6 and 7 are B1, B2, B3 and B7 of the direct-UI package the founder asked for on 2026-11-19 (interactions that
serve what the user wants, not what Lemmata wants to show). B4 (focus chip), B5 (tables belong to the researcher), B6 (jump box) and B8
(empty states) still hold; they are not part of S36.

## 4. Tokens: the exact changes to `tokens.css`
Token names, font stacks (with their Korean fallbacks), `--col`, `--col-wide`, `--radius` and `--motion` stay as they are.
Apply the same changes to `desktop/launcher/tokens.css`, which carries the same values.

### Light (`:root`)
| Token | At bc26f66 | S36 | Why |
|---|---|---|---|
| `--muted` | `#707B74` | `#646F68` | Dates, captions and table headers. 4.27:1 on `--bg` and 3.81:1 on `--bg-2` before; 5.08:1 and 4.53:1 now |
| `--warning` | `#C9A66B` | `#B5823A` | The stale dot was 2.23:1 on `--bg` and close to `--highlight` in lightness; now 3.28:1 and clearly darker |
| `--fs-tag` | `12.8px` | `13px` | Rule 8 |
| `--highlight-edge` | (none) | `#8A7431` | 1px edge of the your-turn button and dot. `--highlight` alone is 1.61:1 on `--bg`; the edge is 4.41:1 |
| `--on-highlight` | (none) | `#1A1A1A` | Text on `--highlight`, 10.47:1 |

Comments to change in the file: `--highlight` becomes "your turn: the primary action's fill, and the dot of items waiting
for the researcher; nothing else". `--muted-light` becomes "placeholder and disabled text only" (it is 2.65:1 on `--bg`).

### Dark (`:root[data-theme="dark"]`)
Founder's decision 4: the shipped dark values stay wherever they pass. They were checked: `--text`, `--text-secondary`,
`--muted` and `--accent-dark` are between 5.13:1 and 14.77:1 on `--bg`, `--bg-2`, `--surface` and `--surface-hover`.
One value changes and two are added.

| Token | At bc26f66 | S36 | Why |
|---|---|---|---|
| `--warning` | `#d3b074` | `#B5823A` | Shipped `--warning` and `--highlight` (`#c9b06a`) have almost the same lightness (relative luminance 0.46 and 0.45), so a stale dot and a your-turn dot cannot be told apart. The new value is 5.21:1 on `--bg` with luminance 0.26 |
| `--highlight-edge` | (none) | `#c9b06a` | Same as `--highlight`: on the dark page the fill already reads (8.30:1) |
| `--on-highlight` | (none) | `#1A1A1A` | 8.21:1 on `#c9b06a` |

`--muted-light` in dark (`#7b8882`) is 4.77:1 on `--bg` but 3.64:1 on `--surface-hover`: placeholder and disabled only, as in light.

## 5. How the rules land on the classes that exist
Do not add a second set of classes. Change the ones in `app.css`. Section 8 gives reference values only.

| Rule | Where it is today (bc26f66) | Change |
|---|---|---|
| 2 | `.btn.primary` fills with `--text` (app.css:25 and :414). 13 `btn primary` call sites in `app.js` and `research.js` | `.btn.primary`: background `--highlight`, text `--on-highlight`, 1px `--highlight-edge`. Then go through the 13 call sites: `primary` stays only where the button settles something that waits on the researcher (Confirm at research.js:208, :2075, :2122; approving a proposed link at app.js:1637). Every other one becomes a plain `.btn` (examples seen: the Ask button, "Copy prompt for Claude Code", the tutorial's Next). List all 13 with the choice in the handoff |
| 2 | `--highlight` as a dot fill: `.rdot.d-highlight` (:558), `.chip.proposed::before` (:594), `.rxt-li.att … .rxt-dot` (:718), `.hf-branch.warn::before` (:1034) | Keep the fill; the border becomes `--highlight-edge`. Check each still means "waits for the researcher"; one that only means "look here" takes `--warning` or no colour |
| 2 | `.btn[aria-pressed="true"]` fills with `--text` (:27, :414) | Stays. A pressed toggle is a state, not a your-turn action |
| 3, 8 | `.chip` text is weight 400 at `--fs-tag` (:589); the dot is 6px (:590) | Weight 600, colour `--text-secondary` (already so at :596); dot 8px |
| 3 | The default dot and `.chip.stg-hypothesis::before` fill with `--accent-pale` and a `--border-strong` edge (:590, :598): 1.35:1 and 1.73:1 on `--bg` | A hollow ring: no fill, 1px `--muted`. Hollow means not backed yet |
| 8 | `--muted-light` colours text in `#status` (:528), `.sg.ok` (:605) and `.hf-tag` (:1008); `.hf-tag` also has a literal `12.8px` | `--muted`, and `var(--fs-tag)` |
| 8 | `--fs-11` and `--fs-12` are both 12px (:2) and are used 114 times; 19 rules set a literal size below 13px | Both become 13px; the literal sizes use `var(--fs-tag)`. Check the pages at 1360, 760 and 420px afterwards: rows that fitted on one line may wrap |
| 9 | Control edges use `--border-strong` (`.btn` :23, `.chip-btn` :292), which is 1.73:1 on `--bg` | Edges of buttons, inputs and chips that can be pressed: `--muted`. Hairlines between rows and under headings keep `--border` and `--border-strong` |
| 9 | Buttons at :412 have no edge and a `--surface-hover` fill | Plain button: no fill, 1px `--muted` edge, fill `--surface-hover` on hover |

### Where the phase 1 build differs from this section (2026-11-22, [S36-01 handoff](../../sprints/S36/S36-01-handoff.md))
- The `.btn` rules that take effect are the third layer (app.css:610 at bc26f66), which drew `.btn.primary` and the pressed toggle as an `--accent-dark` outline, not a fill in `--text`. Sand went into that layer; the pressed toggle keeps its outline.
- There were 37 primary sites, not 13 (10 are dialog buttons with `primary: true`); 10 kept, 27 plain.
- `.hf-branch.warn::before` means "the branch has newer commits", so it takes `--warning`, not sand.
- The VS Code tab keeps its S35 look through four `html.embed` rules in `app.css`, so `vscode/` and the extension version are unchanged.

## 6. The shell
```
┌────────────┬─────────────────────────────────────────────────────┐
│ Lemmata    │ <project>   <repo> · last scan            [Jump to…]│
│            ├─────────────────────────────────────────────────────┤
│ Home    ●2 │        What needs you today?            (serif)     │
│ Thesis     │        2 items wait for you. 3 things changed…      │
│ Setup      │                                                     │
│ Review   3 │        Needs you  2                                 │
│ Trail      │        ─────────────────────────────────────────    │
│ …          │        ● your turn   C4 was drafted…  [Confirm][Fix]│
│ Settings   │        column --col, centred                        │
└────────────┴─────────────────────────────────────────────────────┘
```
- The shell stays as built: sidebar (`renderLeft()`, app.js:2098), title goes Home, Settings at the bottom left.
- In the sidebar only Home may carry the sand dot, beside its count of items waiting for the researcher. Every other count
  stays a plain number in `--text-secondary`.
- The sage band (`--accent`) stays where it is today. Do not put new small text on it: `--on-accent` on `--accent` is 2.93:1 in light.

## 7. Pages
Each page begins with a **page head**: an `h1` that is the question, then one line that answers it from counts the hub
already returns. A zero is said in words ("Nothing disagrees."). Standing explanation paragraphs move behind a "?" link in
the section they explain.

| Page (tab key) | Question | The answer line says |
|---|---|---|
| Home (`digest`) | What needs you today? | How many items wait for the researcher, how many things changed since the last visit, the next deadline |
| Thesis (`experiments`) | Is each claim backed? | How many claims are backed, stale, in mismatch, waiting, without an experiment |
| Setup (`setup`) | What was used? | How many datasets, methods and measures |
| Review (`review`) | What disagrees? | How many mismatches, stale results and items to confirm, and how many checks found nothing |
| Trail (`history`) | What did you do, and when? | The last working day in one sentence |

### Home
Today `pageDigest()` (research.js:1117) draws the project name, the thesis head, the calendar, then tiles (`.hm-cards`:
Next to do, Deadlines, Last 7 days) and "This week". It becomes a list in the reading column, in this order:

| Section | Holds | Row |
|---|---|---|
| **Needs you** | Only what the researcher can settle: a drafted claim or link to confirm, a name to confirm, advisor feedback without tasks | your-turn dot and the words "your turn", one sentence, then the buttons that settle it. The only place on Home with sand buttons |
| **Since you last looked** | What agents, runs and Lemmata changed since the last visit, newest first | The left column says who (your agent, a run, Lemmata), then one sentence, the time, one link |
| **This month** | The calendar that is there today, and the deadlines by venue name | Clicking a day lists who did what, where and when, as rows under the calendar |

"Next to do" items that are not decisions (experiments to run, results to refresh) are not lost: the list that
`rxTodoList()` draws today stays reachable from a link in the answer line, with its count.

### Thesis
1. Page head.
2. The storyline rows (hook, gap, bridge) only where a confirmed storyline exists. The storyline itself is S32 step 1 and is not part of S36.
3. The claims tree: thesis on top, claims under it, evidence under each claim, joined by straight vertical and horizontal
   lines. Node fill: `--accent-vivid` strong support, `--accent-light` partial, `--accent-pale` with a 1px `--muted` ring
   weak, `--highlight` with its edge your turn, hollow ring no experiment. Every node has its short name and its state as
   words beside it. Below 1100px the tree scrolls sideways inside its own frame.
4. The claims as rows. An open row shows the rule in one sentence, the numbers as a table with the project's own method
   last and in weight 600, and its actions.

### Review
Four sections in this order: **Mismatches**, **Stale**, **To confirm**, **Checked and fine** (one row with the count,
closed by default). A mismatch row states both sides in one sentence ("C3 says 'every dataset'; 2 of 6 have no run"). Open,
it shows the numbers side by side (each compared method, then ours, then the difference), with "no run" in words where a
cell is missing.

## 8. Reference values
The canvas was drawn with this stylesheet. Use it to read sizes, spacing and weights. Do not ship these class names.

```css
.lm-question { font-family: var(--font-serif); font-size: 28px; line-height: 34px; font-weight: 700; margin: 0; }
.lm-answer   { font-size: 17px; line-height: 26px; color: var(--text-secondary); margin: 8px 0 0; }
.lm-answer b { color: var(--text); font-weight: 600; }
.lm-section  { font-family: var(--font-serif); font-size: 20px; line-height: 28px; font-weight: 700; margin: 42px 0 0; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
.lm-row      { display: grid; grid-template-columns: 116px minmax(0, 1fr) auto; column-gap: 16px; align-items: baseline; padding: 8px; border-bottom: 1px solid var(--border); font-size: 15px; line-height: 24px; }
.lm-row:hover { background: var(--surface-hover); }
.lm-row[data-open="true"] { background: var(--surface); border-bottom-color: transparent; }
.lm-row .lm-line { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lm-tag      { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; line-height: 18px; font-weight: 600; color: var(--text-secondary); }
.lm-dot      { width: 8px; height: 8px; border-radius: 50%; border: 1px solid transparent; }
.lm-dot--hypothesis { border-color: var(--muted); background: transparent; }
.lm-dot--proved   { background: var(--success); }
.lm-dot--stale    { background: var(--warning); }
.lm-dot--mismatch { background: var(--error); }
.lm-dot--turn     { background: var(--highlight); border-color: var(--highlight-edge); }
.lm-meta     { font-size: 13px; line-height: 18px; color: var(--muted); }
.lm-btn      { font-size: 13px; line-height: 18px; font-weight: 600; padding: 5px 12px; border-radius: var(--radius); border: 1px solid var(--muted); background: transparent; color: var(--text); }
.lm-btn:hover { background: var(--surface-hover); }
.lm-btn--turn { background: var(--highlight); color: var(--on-highlight); border-color: var(--highlight-edge); }
.lm-detail   { background: var(--surface); border-bottom: 1px solid var(--border); padding: 4px 16px 16px 140px; }
.lm-table th { font-size: 13px; font-weight: 400; color: var(--muted); text-align: left; padding: 8px; border-bottom: 1px solid var(--border-strong); }
.lm-table td { padding: 6px 8px; border-bottom: 1px solid var(--border); }
.lm-table td.r { text-align: right; font-family: var(--font-mono); font-size: 13px; font-variant-numeric: tabular-nums; }
.lm-table tr.ours td { font-weight: 600; }
.lm-table td.best { text-decoration: underline; text-underline-offset: 3px; }
```

## 9. VS Code
Unchanged (ADR-011). Two things carry over: the same state words, and hypothesis drawn as a hollow ring. `vscode/media/vscode.css`
maps `--muted` and `--muted-light` to the editor's own colours, so the token changes above do not reach it.

## 10. Two working rules for UI work from now on
1. **Side by side.** A handoff that changes a page includes a screenshot of that page before and after at 1360px, light and dark.
2. **Name the reference.** When a pattern is borrowed, say from where and what was taken, in one line.
