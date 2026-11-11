---
type: task-card
owner_agent: lead
status: built, not yet QA-verified
sources:
  - "founder request in chat, 2026-11-11 12:54 KST, with a screenshot of the Claims page: the core message was cut mid-sentence; too many words; wants a research tree (core message at the top, evidence as roots, Yggdrasil as the image) and a timeline that shows the tree growing"
  - "design research report run in the same chat, 2026-11-11 (precedents: Lean blueprint dependency graph, argument maps, Kedro-Viz bands; union layout with fixed positions for time; cue-phrase picking of the aim sentence is a suggestion, not a fact). Not yet filed in raw/"
  - "code on branch s07-public-site: app/src/lemmata/engine/claims.py (pick_core, tree), engine/api.py (tree, _born), web/research.js (rxTree, rxScrubber), web/app.css, tests/test_tree.py"
last_reviewed: 2026-11-11
---
# S08 brief: Claims as a research tree

## Founder decisions
1. The core message must be a whole sentence that says what the paper does.
2. Fewer words. Show the structure: core message at the top, claims as branches, evidence as roots.
3. The timeline shows how branches and roots grew.

## What was built
- **Core message.** The bug: the abstract was cut at 200 characters. Now one sentence is picked from the abstract by rules (cue phrases such as "we propose", "in this survey"; background sentences and number-heavy sentences are marked down; overlap with the contribution list is marked up). Fallback: the title, then the last sentence. "Reword" lets the researcher replace it. The full abstract is kept under the card.
- **Tree (default view of Claims).** Crown: core message, claims under it, a theorem under the contribution that states it, a lemma under the theorem that uses it. Ground line. Roots in bands: paper items and proofs, then result files, then scripts and settings, then runs. Evidence shared by several claims is drawn once with a ×N badge. A claim with nothing behind it gets a "?" root.
- **Encoding.** Status by fill and outline as well as colour: full = supported, half = partly, hollow dashed = not supported. Dashed amber ring = recheck. Square = theorem or lemma. Dashed grey root line = suggested link. Branch thickness grows with the number of roots.
- **Interaction.** Hover lights up everything a node rests on and everything resting on it. Click a claim for its card (confirm, link evidence, reword). Click a root to open the file or the lines. Tree / List switch keeps the S07 list.
- **Timeline.** The same tree with a time slider, play button and step buttons. Positions never move; pieces appear. Ticks under the slider are the steps from the S07 timeline; decisions are taller.

## Added the same day (founder, 13:34 KST): pictures and an evidence card
- Figures in the tree show the actual picture. PNG, JPG and SVG are served as they are; a PDF figure is turned into a PNG of its first page with `pdftoppm` if installed, otherwise macOS `sips`, and cached in `.lemmata/thumbs`. This means the hub now runs a PDF converter on files from users' repositories (25 s limit, 20 MB cap). On a public site that is new attack surface; the CTO should review it against the threat model.
- Clicking a figure, table or result file opens a card: the picture (or the table's cells), the caption, the claims it backs, "Connected / Not connected" with each file behind it linked to GitHub at the commit Lemmata read, and two notes the researcher writes: "Meant to show" and "Caveat". A caveat puts a ! on the node. Notes are stored in `.lemmata/notes.json`.
- Correction to S07: a figure whose only link is its own image file used to count as traced. Now traced needs a script, a run or a result file.

## Known limits (tell users)
- Dates: a file is dated by its first commit; a paper item by `git blame` of its lines, which is when those lines were **last written**, not first written. A paper uploaded as a zip has no dates, so its claims are shown from the start and only the roots grow.
- The slider shows when pieces appeared. It does not replay past **status** (whether a claim was supported on a given day).
- The sentence picker is rule-based and unevaluated. Treat the core message as a suggestion.
- Large papers: no collapsing of big root bundles yet; the tree scrolls sideways.
