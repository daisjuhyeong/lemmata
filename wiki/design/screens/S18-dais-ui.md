---
type: screen-spec
owner_agent: designer
status: approved direction (founder, chat 2026-11-12); build not started
sources:
  - "founder message in chat, 2026-11-12 15:53 KST: 'Regarding the UI, align it with the following website. https://dais.korea.ac.kr Overall, I want the UI to be direct, yet simple just like the structure of the website that I have given you.'"
  - "founder message in chat, 2026-11-12 15:55 KST: 'make the design for opening from the visual studio code differently so that the UI adapts to the VS studio code format (it is usually smaller than normal website).'"
  - "founder message in chat, 2026-11-12 15:56 KST: 'Proceed and send it to the CTO agent'"
  - "https://dais.korea.ac.kr and https://dais.korea.ac.kr/styles.css (computed styles and :root variables read in a browser, 2026-11-12)"
  - "../DESIGN.md (v0.1 tokens, superseded by this page once built)"
  - "../../sprints/S16/S16-brief.md (the VS Code tab shows the hub's own web app; 1024 px minimum; does not follow the editor theme)"
  - "../../sprints/S17/S17-brief.md (claim stages)"
last_reviewed: 2026-11-12
---
# S18 UI style spec: align with dais.korea.ac.kr

Replaces all earlier UI styling direction: the Ink/Paper palette in [DESIGN.md](../DESIGN.md), the [S06 Obsidian redesign](s06-obsidian-redesign.md) and the [S13 clean UI](S13-clean-ui.md) proposal. Part 1 covers the website and the desktop app. Part 2 is a separate, compact design for the VS Code tab and views. Task card: [S18-01](../../sprints/S18/S18-01-lead.md).

## What to copy from the reference
The DAIS site is direct because of five things. Lemmata does the same five.

1. **One column.** Content is a single centred column, 800px max. No sidebar, no dashboard grid.
2. **One band.** A flat sage header holds the title, one subtitle line and the nav. Nothing else is coloured.
3. **Four nav items, text only.** No icons, no dropdowns. The active item gets an underline.
4. **Sections are a serif heading with a hairline under it.** No cards, no shadows, no rounded panels.
5. **Content is rows.** One line per item, a small muted tag at the left (`[2026.11]`), a 1px line between rows.

Rule for any new screen: if it cannot be built from *band, heading, rows*, simplify the screen before adding a new component.

---

# Part 1: Website and app

## Tokens
One file (`tokens.css`), nothing else. No hex values anywhere else in the code. Values are the DAIS site's own `:root` variables.

```css
:root {
  --bg: #fafcfb;            /* page */
  --bg-2: #e9f0ef;
  --surface: #F3F7F4;       /* selected row, detail panel */
  --surface-hover: #EDF3EF; /* row hover */
  --text: #1A1A1A;
  --text-secondary: #464f4a;
  --muted: #707B74;
  --muted-light: #959f99;   /* tags, footer */
  --border: #CCD6D0;        /* all hairlines */
  --border-strong: #B8C5BE;
  --accent: #819A91;        /* header band */
  --accent-dark: #50645b;   /* links, active states on light bg */
  --accent-vivid: #5e917e;  /* graph nodes: strong */
  --accent-light: #A7C1A8;
  --accent-pale: #D4DDD6;   /* graph nodes: weak; text on band */
  --highlight: #dac88e;     /* the one item needing attention */
  --success: #6F9A76;
  --warning: #C9A66B;
  --error: #B87474;
}
```

Contrast: `--muted-light` on `--bg` and `--bg` on `--accent` are the reference site's own pairs and are low. Re-check with a tool; use `--muted` for any tag a user must read to act, and keep band text at 14.4px or larger.

## Type
| Use | Font | Size / weight |
|---|---|---|
| Page title (in band) | Source Serif 4 | 32px / 700, colour `--bg` |
| Subtitle (in band) | Source Serif 4 italic | 14.4px / 400, colour `--accent-pale` |
| Section heading | Source Serif 4 | 20px / 700 |
| Body, rows, nav | Source Sans 3 | 15px / 400, line-height 1.75 (nav 500) |
| Row tag, footer | Source Sans 3 | 12.8px, colour `--muted-light` |
| Code, hashes, run ids | system monospace | 13px |

- Fallbacks: `Georgia, serif` and `"Helvetica Neue", Helvetica, Arial, sans-serif`.
- Korean must still render (DESIGN.md rule): after the Latin fonts, each stack continues with the Korean-capable fonts of the current stacks in DESIGN.md (Noto Serif KR for serif, IBM Plex Sans KR for sans, then Apple SD Gothic Neo, Malgun Gothic, Noto Sans KR).
- No font files are in the repo today (the app names fonts and falls back to system ones). Add Source Serif 4 and Source Sans 3 as local woff2 files (both are under the SIL Open Font License; keep the licence file beside them). No remote font request (CSP `default-src 'self'`; the VS Code webview allows no network).

## Layout shell
```
┌──────────────────────────────────────────────┐
│  band (--accent), full width                 │
│        Lemmata                               │
│        <project name>, <repo>                │
│     Claims │ Experiments │ Digest │ Review   │
└──────────────────────────────────────────────┘
        column: max-width 800px, centred
        padding 42px 24px 96px
        ...sections...
        footer: 12.8px, --muted-light
```
- Band: title centred, subtitle under it, nav centred at the bottom edge. Nav links are `--bg` text, padding `4px 16px 2px`, thin vertical dividers between items, active item has a 2px `--accent-pale` bottom border.
- At most four top-level nav items: **Claims, Experiments, Digest, Review**. Every other existing page (tasks, Ask, project map, notation, Projects, settings, sign-out) moves under one of the four as a section, or into the footer as a plain link. The lead proposes the mapping in the handoff note.
- The Claims tree is the only element allowed to break the 800px column (up to 1100px, still centred).

## Components
**Section heading.** Serif 20px, margin `42px 0 8px`, padding-bottom 6px, `1px solid --border` underneath.

**Row.** `display:flex`, padding `6px 0`, 1px `--border` line between rows. Left: tag in brackets, fixed width, muted (date, run label, claim stage). Right: one sentence. Hover: `--surface-hover`. Click expands the detail in place under the row; no modal, no new page.

**Table (Experiments).** Same as rows with columns. Header row in 12.8px `--muted`, no fill, no vertical lines, numbers right-aligned in monospace. One section heading per claim, its experiments as rows below.

**State.** Shown as the bracket tag plus a 6px dot, never as a filled badge or coloured row. Status is still never colour alone (DESIGN.md rule): the word in the tag carries it. Use the S17 stage names as they are in the code.

| Stage or state | Tag | Dot |
|---|---|---|
| Hypothesis / exploration | `[hypothesis]` / `[exploration]` | `--accent-pale` |
| Being tested | `[being tested]` | `--accent-light` |
| Finding (backed) | `[finding]` | `--success` |
| Not supported / mismatch | `[not supported]` / `[mismatch]` | `--error` |
| Stale evidence, recheck | `[recheck]` | `--warning` |
| Needs the user's confirmation | `[confirm]` | `--highlight` |

**Detail panel.** Background `--surface`, 1px `--border`, no radius above 2px, no shadow. Contents are again rows.

**Buttons and links.** Links: `--accent-dark`, underline on hover. Primary action: text button with a 1px `--border-strong` outline; hover fills `--surface-hover`. At most one primary action per screen. No filled coloured buttons.

**Claims tree.** Takes its look from the node-and-line graphic on the DAIS home page: circles on thin lines, on the page background.
- Nodes are circles only. Size = importance (core message largest). Fill runs from `--accent-pale` (weak support) to `--accent-vivid` (strong support). A node needing attention uses `--highlight`.
- Edges: 1px `--border-strong`. No arrowheads, no edge labels.
- Labels: Source Sans 13px beside the node, max 6 words. Everything else appears in the detail panel on click.
- Layout is vertical (core message at top, evidence below), collapsed to two levels by default, expand on click. This also answers "the tree is too wide" (founder, 2026-11-12).

**Figures and equations.** Inline in the detail panel at column width, with a 12.8px muted caption row. No frames.

## Per screen
| Screen | Built from |
|---|---|
| Claims | Tree (wide column), then a "Needs attention" section of rows |
| Experiments | One section per claim, table of experiments, in-place expand for details and history |
| Digest | Plain prose in the column, section headings per week, every line a link |
| Review | One section per check, each a list of rows |
| Start / tutorial | Band, one sentence of what Lemmata does, three numbered rows, one "Sign in with GitHub" button |

## Remove
Sidebars, cards, drop shadows, gradients, rounded corners over 2px, icons in navigation, filled badges and chips, modals, emoji, layer colours, any colour not in the token list, any second accent colour.

---

# Part 2: VS Code (compact design)

The VS Code tab is not the website shrunk down. It keeps the same idea (*heading, rows*) but takes its size, fonts and background from the editor. Since S16 the tab shows the hub's own web app, so this is one more stylesheet (`vscode.css`) and a few layout switches that apply when `window.LEMMATA_EMBED` is set, not a second copy of the pages. It replaces the S16 behaviour "keeps its 1024 px minimum and scrolls sideways".

## What changes from Part 1
| | Website | VS Code |
|---|---|---|
| Header | Sage band with title and subtitle | None. VS Code shows the tab title. |
| Navigation | Four links in the band | One sticky row of four text tabs, 12px |
| Width | Fixed 800px column | Fluid, fills the view; three width modes below |
| Background and text | DAIS light palette | The editor's own theme (light or dark) |
| Body font | Source Sans 3, 15px | The editor's UI font and size (about 13px) |
| Row height | Padding 6px, line-height 1.75 | Padding 3px, line-height 1.5 |
| Claims tree | Node-and-line graph | Outline list when narrow, graph when wide |
| Footer | Settings, sign-out | None. These are VS Code commands. |

## Theme mapping
Neutral colours follow the editor theme, so Lemmata looks native in light and dark. The DAIS sage and the state colours stay, since they carry meaning.

```css
/* vscode.css: overrides tokens.css in the embedded app */
:root {
  --bg: var(--vscode-editor-background);
  --surface: var(--vscode-editorWidget-background);
  --surface-hover: var(--vscode-list-hoverBackground);
  --text: var(--vscode-foreground);
  --muted: var(--vscode-descriptionForeground);
  --muted-light: var(--vscode-descriptionForeground);
  --border: var(--vscode-panel-border);
  --border-strong: var(--vscode-panel-border);
  /* kept from DAIS: --accent, --accent-vivid, --accent-light, --accent-pale,
     --highlight, --success, --warning, --error */
}
body.vscode-dark { --accent-dark: #A7C1A8; }  /* links readable on dark */
body { font-family: var(--vscode-font-family); font-size: var(--vscode-font-size); }
code { font-family: var(--vscode-editor-font-family); }
```
In a sidebar or panel view use `--vscode-sideBar-background` for `--bg`. Check the current VS Code webview theming docs for the variable names before coding; do not code from memory.

## Type
| Use | Font | Size |
|---|---|---|
| Section heading | Source Serif 4, 700 | 14px, 1px hairline under it, margin `16px 0 4px` |
| Rows, tabs | editor UI font | editor size (13px), tabs 12px |
| Tags, captions | editor UI font | 11px, `--muted` |

The serif section heading is the one visual link back to the website. Everything else uses the editor's fonts.

## Three width modes
Use CSS container queries on the app root, not the window size, because the same page can sit in a sidebar, a split or a full editor tab.

**Narrow, under 360px (sidebar).**
- Padding 8px 12px.
- Row: state dot, then one line of text cut with an ellipsis. No bracket tag on screen; the stage word is in the tooltip and in the accessible name.
- Experiments: two columns only (name, main metric). All other fields appear in the in-place expand.
- Claims: an indented outline. Each claim is a row with its dot, evidence indented below, collapse arrows as in the file explorer. No graph.
- Tabs show as four short words; if they do not fit, the active one shows in full and the others shorten to their first letter.

**Medium, 360 to 700px (wide sidebar, bottom panel, split editor).**
- Padding 12px 16px.
- Row: dot, bracket tag, sentence (may wrap to two lines).
- Experiments: four columns (name, metric, commit, time).
- Claims: the vertical graph, two levels, labels cut to 4 words.

**Wide, over 700px (full editor tab).**
- Same as Part 1 minus the band and footer: content capped at 800px and centred, full Experiments table, full Claims tree.

## Behaviour specific to VS Code
- Expanding a row happens in place, as on the website.
- File, line, commit and `.tex` places keep the S16 behaviour: they open in the editor beside the tab.
- Figures show as thumbnails at most 160px high; clicking opens the image in an editor tab.
- Equations render at the view's font size and scroll sideways inside their own row instead of widening the view.
- One "Open on website" link at the bottom of each page for the full-size version.
- No sideways scrolling of the page itself in any mode.
- Hover and selection use the editor's list colours; arrow keys move between rows and Enter expands, as in the file explorer.

## Per view
| View | Narrow | Wide |
|---|---|---|
| Claims | Outline list with dots | Vertical graph + "Needs attention" rows |
| Experiments | Name + metric, expand for the rest | Full table per claim |
| Digest | Headings and prose, no change | Same, capped at 800px |
| Review | Collapsible sections of rows, counts in the heading | Same, all open |

---

## Done when
**Website and app**
- Every colour in the code resolves to a token (a search for `#` colour values finds only `tokens.css` and the one override in `vscode.css`; vendored KaTeX excepted).
- Each of the four screens fits the *band, heading, rows* rule, and a screenshot placed next to dais.korea.ac.kr reads as the same family.
- The Claims tree shows a whole project without sideways scrolling at 1280px width.
- Korean text renders in headings and rows.

**VS Code**
- All four pages are usable at 300px width with no sideways scrolling and no cut-off controls.
- Widening the tab from narrow to wide switches the mode without a reload.
- The pages look correct in a light theme and a dark theme (Default Light Modern, Default Dark Modern).
- Clicking a file or line place still opens it in the editor.
