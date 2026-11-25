---
type: handoff
owner_agent: lead
status: built in the chat session on branch s38-home-goal-map (from next f84d7eb); not on next, not on main; not checked on the Mac mini hub or on the real mcd_extension project
sources:
  - "founder message in chat, 2026-11-25 21:50 KST, with a screenshot of the Thesis Map view of mcd_extension: 'I want this to be in the main page in the home page. I want the statement or the goal of the research in the top, but bigger. Also for the map, I like what it says \"new claims\" column where there are numbers that states the current status. But I want to organize this neater. For the headlines, make the fonts bigger but briefer. (or just leave it as Claim 1, Claim 2) Also for the results or why for the status, I want a pop-up to see such reasons and why, which is currently the most right column. Make the corresponding changes'"
  - "code: app/src/lemmata/web/research.js (rxClaimName, rxMapData, rxClaimState, rxClaimMap, rxClaimPop, rxExpMap, rxGoalHead, pageDigest), app/src/lemmata/web/app.js (modal: opts.cls), app/src/lemmata/web/app.css (section S38)"
  - "screenshots/ (sample project built from app/tests/test_map.py's fixture, with an extension map)"
last_reviewed: 2026-11-25
---
# S38-01 handoff: the goal on top of Home, the claim map as cards, results in a pop-up

No task card: the founder asked for the change directly and the lead built it in the chat session (as for S37-01).

## What changed
1. **Home starts with the research goal, large.** The map's goal (or, without one, the thesis) is the page's heading at 32px,
   with "Research goal · <ours> extends <base>" above it in small type. "What needs you today?" and its answer follow under the map.
   A project with no goal and no thesis, a survey project, and the VS Code tab keep the Home they had.
2. **The claim map is on Home, under the goal.** One line of counts (experiments, ahead of the base, to check), then the claims
   as cards in a grid under "New claims" and "Original paper, re-checked" (or "Claims" when the work extends nothing).
3. **A card is brief.** Headline "Claim 1" (22px; from the short name C1; H1 becomes "Hypothesis 1"), the state in words,
   two lines of the claim at most, the ahead/behind bar with "4 of 5 ahead", and "! n" when experiments need a check.
   The left edge is green for a finding and red for not supported.
4. **Results and reasons are a pop-up.** Clicking a card opens a dialog: the full claim, "Why it has this state" (the rule's own
   sentence, stage_why), and "Results": one row per experiment with ahead/behind, against which method, and the gap. A row
   opens that experiment's detail in place. Esc, Close, or a click outside closes it and focus returns to the card.
5. **Thesis's Map view shows the same cards.** The three-column drawing (root, claims, experiments) and its lines are gone.
   Links that name a claim or an experiment (`q:` / `x:`, used by VS Code and "Open this experiment") still show it under the cards.

## Checked
- Python suite 306 OK (2 skipped); extension unit suite 78 pass.
- Browser (Chromium, sample project): Home at 1360 and 420 wide, light and dark; pop-up opens, a result row expands,
  Esc closes and focus returns; Thesis Map view; no console errors, no sideways overflow.

## Not checked
- The real mcd_extension project (17 experiments, 9 claims) and the Mac mini hub.
- The Tauri app and a real VS Code window.
- A benchmark study and a hypothesis-first project on Home (the code paths are the same as the old map's; no fixture was run).

## Open
- The old map's styles (`.rx-m-root`, `.rx-m-q`, `.rx-m-x`, `.rx-m-edges`, `.rx-m-scope`) are now unused in app.css; left in place, to remove in a cleanup.
- Proposed, for the founder to decide: whether Home should also keep a link "Open the full Thesis" beside the map.
