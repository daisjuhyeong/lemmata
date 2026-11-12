---
type: task-card
owner_agent: lead
status: open, assigned to CTO (Agent 1)
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
- What changed:
- Open questions:
- Links:
