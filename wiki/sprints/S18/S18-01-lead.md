---
type: task-card
owner_agent: lead
status: built on branch s18-dais-ui, awaiting QA and Juhyeong's approval
sources:
  - "founder message in chat, 2026-11-12 15:53 KST: 'Regarding the UI, align it with the following website. https://dais.korea.ac.kr Overall, I want the UI to be direct, yet simple just like the structure of the website that I have given you.'"
  - "founder message in chat, 2026-11-12 15:55 KST: 'make the design for opening from the visual studio code differently so that the UI adapts to the VS studio code format (it is usually smaller than normal website).'"
  - "founder messages in chat, 2026-11-12 15:56 and 16:04 KST: 'Proceed and send it to the CTO agent'; 'Comply with option 1' (commit the spec and this card to a branch)"
  - "../../design/screens/S18-dais-ui.md"
last_reviewed: 2026-11-12
---
# Task S18-01: restyle Lemmata to the DAIS-aligned UI spec

- **Goal:** the website, the desktop app and the VS Code tab follow [the S18 UI style spec](../../design/screens/S18-dais-ui.md). It replaces the Ink/Paper palette, the S06 Obsidian redesign and the S13 clean-UI proposal.
- **Inputs:** the spec; `app/src/lemmata/web/{app.css,app.js,research.js,index.html}`, `web/hub/hub.css`, `desktop/launcher/launcher.css`; `vscode/src/{tab.ts,core/embed.ts}`, `vscode/media/embed.js`; reference site https://dais.korea.ac.kr.
- **Owner:** CTO (Agent 1) as lead; web engineer builds; designer updates `wiki/design/DESIGN.md` to the new tokens once the build is accepted.
- **Reviewer (QA):** QA agent, independent of the builder.
- **Budget (time/usage):** one sprint; no spending; no new dependencies beyond the two bundled font families.
- **Branch:** continue on `s18-dais-ui` (cut from `s07-public-site` at the S17 follow-up). Do not merge to main without Juhyeong's approval.

## Order of work
1. **Tokens and fonts.** Add `tokens.css`; bundle Source Serif 4 and Source Sans 3 locally with the Korean fallbacks; remove every other colour value from the CSS and JS.
2. **Shell.** Band, 800px column, at most four nav items, footer. Propose where each existing page that is not one of the four goes.
3. **Pages.** Convert Claims, Experiments, Digest, Review and the start page to *heading + rows*. Claims tree: circles on thin lines, vertical, two levels by default.
4. **Hub pages and the desktop launcher.** Same tokens and type.
5. **VS Code.** `vscode.css` applied in the embedded app (S16), editor theme mapping, the three width modes by container query, outline form of the Claims tree under 360px. Drop the 1024px minimum inside the tab.

## Acceptance criteria
- Every "Done when" line in the spec holds.
- No behaviour change: all existing Python, extension unit, integration and end-to-end tests pass; new tests cover the width modes and the embedded stylesheet switch.
- Security settings unchanged (CSP `default-src 'self'`, `frame-ancestors 'none'`, the S16 request bridge).
- Screenshots in the handoff note: website at 1280px (Claims, Experiments, Review, Digest, start page); VS Code tab at 300px and at full width, in a light and a dark theme.

## Open points the lead should raise, not decide silently
- The reference palette has low-contrast pairs (`--muted-light` on `--bg`, light text on the sage band). Report measured ratios and propose a fix if any text a user must read falls under 4.5:1.
- The VS Code tab now follows the editor theme instead of keeping Lemmata's colours (S16 kept them). Juhyeong was told this in chat on 2026-11-12 and has not objected; confirm in the report.
- Mapping of existing pages onto the four nav items.

## Done when
The acceptance criteria hold, QA has verified on the branch, and a report with the screenshots has gone to Juhyeong on Slack as `[approval needed]`.

## Handoff note
(web engineer for the CTO, 2026-11-12. Builds on an earlier, stopped draft: kept the tokens, fonts, shell, Digest page, vscode.css and the request-bridge-safe tab changes after review; redid the tree labels and nesting, the tab-label fitting, the Review and start-page layouts, and a test that broke on a stray folder; restored the start-view mapping the draft had changed.)

- **What changed:**
  - Tokens and fonts (step 1). `app/src/lemmata/web/tokens.css` holds the spec's palette and is the only file with colour values for the website, app and hub pages; `vscode/media/vscode.css` maps the editor theme and has no colour value of its own (the dark-link override uses `var(--accent-light)`, the same value as the spec's `#A7C1A8`). Source Serif 4 4.005R (Regular, Bold, Italic) and Source Sans 3 3.052R (variable, upright) are bundled as woff2; their SHA-256 match the files in Adobe's GitHub releases ([source-serif 4.005R](https://github.com/adobe-fonts/source-serif/releases/tag/4.005R), [source-sans 3.052R](https://github.com/adobe-fonts/source-sans/releases/tag/3.052R)), and the OFL files match each repo's `LICENSE.md`. Korean falls back to the DESIGN.md stacks (checked with Korean text in a heading and a row).
  - Shell (step 2): band, 800 px column, four nav items, footer. No sidebar, tab bar or 1024 px minimum.
  - Pages (step 3): Claims tree as circles on thin lines, vertical, core + claims open (two levels), labels are the claim code + six words (four in the medium mode), evidence and its trace (Table 2 → table2.csv) open on click; "Needs attention" rows; Experiments one section per claim with rows; Review checks as rows; new Digest page (this week, open tasks, history by week). Tags in brackets + 6 px dot.
  - Hub pages and launcher (step 4): band header; start page = band with tagline, one sentence, numbered steps as rows, the one sign-in button, then "Four ways" and "Before you sign in" as rows. Launcher uses the same tokens and fonts (its own copies; a test keeps them byte-equal).
  - VS Code (step 5): `vscode.css` added after `app.css` only in the tab; theme mapping per the spec (variable names checked against the installed VS Code's webview `index.html` and its Light/Dark Modern theme files); three width modes by container query on `#app`; Claims is an outline with arrows under 360 px; tabs shorten to a first letter only when they do not fit; arrow keys move between rows; figures max 160 px; equations scroll in their row; "Open on website" link. CSP (`default-src 'self'`, `frame-ancestors 'none'` on the hub; the tab's nonce CSP) and the S16 request bridge are unchanged.
  - Tests. Baseline at 8b427f5 on this machine: Python 162 passed / 2 skipped; extension unit 56/56; integration 10/10; end-to-end 6 skipped (Playwright is not installed here). Now: Python 169 passed / 2 skipped; unit 63/63; integration 10/10; end-to-end 7 skipped. New: `app/tests/test_s18_ui.py` (7 tests), `vscode/test/unit/s18.test.ts` (7 tests: stylesheet switch, no minimum width, CSP unchanged, theme mapping scoped to the tab, width modes, tree per mode, Digest view), one end-to-end width-mode test (skipped here). No existing test was changed. The end-to-end checks were instead run by hand in WebKit (below): modes at 300/500/1200 px, switching by resizing `#app` without a reload, no sideways scroll, "Open in editor" calls `openFile` with repo, path and line.
  - Screenshots: `screenshots/` (23 + launcher). Website at 1280 px: `website-{claims,experiments,review,digest,start}-1280.png`. VS Code tab: `vscode-{claims,experiments,review,digest}-{300,full}-{light,dark}.png` and `vscode-claims-500-{light,dark}.png`. **Not real VS Code:** the tab was rendered in WebKit (a small local WKWebView snapshot tool; no Chromium or Playwright on this machine) with `vscode.css`, the tab CSS and the `--vscode-*` values of Default Light Modern / Dark Modern from the installed VS Code, against `lemmata demo` (synthetic sample). The start page used a stubbed `/api/hub/status` (public mode).
- **Proposed mapping of pages onto the four nav items (implemented as proposed; Juhyeong decides):**

  | Nav item | Pages under it (nav item shown active) |
  |---|---|
  | Claims | Claims tree/list, Growth (timeline), Notation, Graph, an item's page, a file's page |
  | Experiments | Experiments |
  | Digest | Digest (new), Tasks, History, Ask |
  | Review | Review, Changes, Checks |
  | Footer links | Changes, Checks (n), History, Graph, Growth, Notation, Tasks, Ask, Search, Project menu (export, sync, hub controls), How Lemmata works. In VS Code: the same links plus "Open on website". Projects, account and sign-out stay in the hub's band. |

- **Contrast (WCAG 2.x, measured from tokens.css; ⚠ = under 4.5:1). No palette change applied.**

  | text \ background | `--bg` #fafcfb | `--bg-2` #e9f0ef | `--surface` #F3F7F4 | `--surface-hover` #EDF3EF |
  |---|---|---|---|---|
  | `--text` #1A1A1A | 16.89 | 15.06 | 16.10 | 15.47 |
  | `--text-secondary` #464f4a | 8.23 | 7.34 | 7.84 | 7.53 |
  | `--muted` #707B74 | 4.27 ⚠ | 3.81 ⚠ | 4.07 ⚠ | 3.91 ⚠ |
  | `--muted-light` #959f99 | 2.65 ⚠ | 2.36 ⚠ | 2.52 ⚠ | 2.43 ⚠ |
  | `--accent-dark` #50645b | 6.15 | 5.48 | 5.86 | 5.63 |
  | `--accent-vivid` #5e917e | 3.50 ⚠ | 3.12 ⚠ | 3.33 ⚠ | 3.20 ⚠ |
  | `--success` #6F9A76 | 3.11 ⚠ | 2.77 ⚠ | 2.96 ⚠ | 2.85 ⚠ |
  | `--warning` #C9A66B | 2.23 ⚠ | 1.99 ⚠ | 2.12 ⚠ | 2.04 ⚠ |
  | `--error` #B87474 | 3.52 ⚠ | 3.14 ⚠ | 3.36 ⚠ | 3.22 ⚠ |
  | `--highlight` #dac88e | 1.61 ⚠ | 1.44 ⚠ | 1.54 ⚠ | 1.48 ⚠ |

  Band (`--accent` #819A91): `--bg` text 2.93 ⚠ (title 32 px bold and nav 15 px), `--accent-pale` subtitle 2.17 ⚠, `--text` 5.77. VS Code: links `--accent-light` on Dark Modern #1F1F1F 8.51; editor link colours 6.31 (light) and 6.65 (dark).
  Where it matters: tags and captions use `--muted` (4.27); the footer state line and the band text are under 4.5. Status colours appear only as 6 px dots next to the word, so meaning does not rest on them. **Proposed fix (not applied):** `--muted` → #5f6a63 (5.47 on `--bg`, 4.87 on `--bg-2`), use `--muted` instead of `--muted-light` for any text, and either darken the band to #5e7a70 (`--bg` text 4.54; keep the subtitle in `--bg`) or keep the band and set its text in `--text` (5.77).
- **Open questions:**
  1. Contrast fix above: Juhyeong's call.
  2. The VS Code tab now follows the editor theme instead of Lemmata's colours (S16 kept them). Juhyeong was told in chat on 2026-11-12 and has not objected; please confirm.
  3. The page mapping above.
  4. Deviations from the spec: (a) `tokens.css` exists twice (web and desktop launcher) because the Tauri bundle cannot reach the web folder; a test keeps them identical. (b) The launcher's app icon `desktop/launcher/lemmata-icon.svg` still has the old navy/gold colours (an image asset, not CSS/JS); recolour is a designer task. (c) The Claims tree stays in the 800 px column (allowed up to 1100 px; a vertical outline does not need more). (d) The start page has four numbered steps, not three, because cutting the copy is a content decision; it also keeps "Four ways" and the privacy list as rows below the button. (e) The footer stays in VS Code as one line of links, because the pages that are not among the four nav items need a way in; settings and sign-out are not in it. (f) Experiments now opens on its table view (the spec's per-claim table) instead of the map; the map is one click away. (g) The website no longer blocks windows under 1024 px; the one-column layout works at any width. (h) The tab is a WebviewPanel (an editor tab), so the spec's sidebar mapping (`--vscode-sideBar-background`) has no view to apply to.
  5. Not verified here: a real VS Code window (Default Light/Dark Modern), the end-to-end tests (need Playwright and Chrome), and the hub's signed-in pages (projects list, new project) after the restyle; QA should run `npm run test:e2e` where Playwright exists.
- **Links:** commits 391f6ea, 0ac5654, 8464c7d, 401caed on `s18-dais-ui`; spec [S18-dais-ui.md](../../design/screens/S18-dais-ui.md); screenshots in [screenshots/](screenshots/).
