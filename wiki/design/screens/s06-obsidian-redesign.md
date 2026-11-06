---
type: screen-spec
owner_agent: designer
status: draft
sources:
  - "../../sprints/S06/S06-brief.md (founder decisions 2026-11-06, section B)"
  - "../DESIGN.md (palette, type, status chips, lineage styling)"
  - "../../architecture/data-model.md (sections 3, 7, 8, 9, 10, 12)"
  - "../../product/demo-spec.md (sample project: learning rate 3e-4 to 1e-3, Table 2, Appendix B)"
  - "../../../app/docs/screens/01-graph.png (current UI, separate bands)"
  - "https://obsidian.md (UI baseline named by the founder)"
last_reviewed: 2026-11-06
---
# S06 screen spec: an Obsidian-style UI anyone can read

Proposal for Juhyeong's approval. For one web engineer, plain HTML/CSS/JS plus canvas/SVG, no build step, offline. Keeps the API in [data-model.md](../../architecture/data-model.md); everything below is derived in the browser. Palette and fonts: [DESIGN.md](../DESIGN.md), unchanged. The old band graph ([01-graph.png](../../../app/docs/screens/01-graph.png)) is replaced.

Reading rules for this page: "UI word" = what the user sees. Text in `code` that is a path, number or sentence template is exact copy. `{x}` is a placeholder. English only for now; the engineer puts all strings in one `strings.js` object so Korean can follow.

---
## 1. Item model (UI only)

### 1.1 Which nodes become Items
An **Item** is something the paper says. Source node kinds ([§3.2](../../architecture/data-model.md)):

| Node kind | Becomes | UI kind word |
|---|---|---|
| `thesis` | Item | Main claim |
| `rq` | Item | Research question |
| `section` (level 1 and 2, main and appendix) | Item | Section / Appendix |
| `figure` | Item | Figure |
| `table` | Item | Table |
| `equation` | Item | Equation |
| `item` (README provenance placeholder) | Merged into the figure/table/appendix Item with the same number (`paper_ref` "Fig. 5" = Figure 5); if none matches it is Evidence of nothing and shows only under Code as "Listed in README, not found in the paper" | (not an Item) |
| `reference` | Item only when the "References" toggle is on (graph) or the Checks view needs it; otherwise not shown | Reference |
| `asset`, `result`, `run`, `code`, `config`, `data`, `doc` | **Evidence** of one or more Items, or a Shared item (1.2) | see 1.2 |

### 1.2 Absorption rule (the decision)
For every non-paper node `n`, compute `F(n)` = the set of Items that depend on `n`: Items whose paper node reaches `n` by following edges with effective `propagates: true` in the `from → to` direction (`includes, generated_by, traces_to, produced_by, executes, reads, imports`; `value_match` only once approved; `proposed` and `rejected` ignored). Structure edges (`contains, answers, refs, cites`) never absorb.

1. `|F(n)| = 1`: `n` is **Evidence** of that Item. It has no circle of its own.
2. `|F(n)| >= 2`: `n` becomes a **Shared item** (small circle, kind word "Shared code" for `code/config/run`, "Shared data" for `result/asset/data/doc`). **Decision: one small Shared item per such node, not a copy in each Item.** Each Item that uses it lists it in its Evidence as a link row "Shared code: configs/default.yaml, also used by Appendix B". Why: (a) a change to a shared file is one thing that touches several Items, so it must exist once to carry one status and one card; copies would show the same change as several unrelated evidence rows with their own, possibly diverging, statuses and would double-count in size; (b) it keeps the graph honest: this is exactly where "what does it affect?" has an answer worth seeing; (c) it matches the founder's "Shared code" item. Cost: a few extra small circles; they can be hidden with a filter.
3. `|F(n)| = 0`: inherit. If `n` depends (`n → m`) on a node `m` that is Evidence of Item X, `n` becomes Evidence of X (example: `results/metrics.json`, produced by the same run as Table 2, is evidence of Table 2). Repeat until stable. If still empty, `n` is **Unused by the paper** and appears only in the Code explorer (and in the graph only when "Files not used by the paper" is on).
4. A run (`run`) with `|F| = 1` is Evidence "Run"; its script (`executes`) is Evidence "Script"; configs/data it reads are Evidence "Settings" / "Data". Nodes that are Evidence only through a Shared item (e.g. `train.py` imported by a shared helper) follow rule 1-3 normally.

Worked example (sample, state 0): `configs/default.yaml`, `run train_main`, `results/table2.csv`, `train.py` all reach only Table 2, so they are Evidence of Table 2. After approving the Appendix B link (value_match), `configs/default.yaml` has `F = {Table 2, Appendix B}` and becomes the Shared item "configs/default.yaml" (Shared code). `eval.py` and `plot_curve.py` each feed one Item or none, so they are Evidence or Unused.

Implementation: build once after `/api/graph` and `/api/alarms` load, in `model.js`: `items[]`, `evidenceOf[itemId][]`, `itemOf[nodeId]` (Evidence node to Item ids), `itemEdges[]`.

### 1.3 Item-level edges (for graph, right sidebar)
Between Items, de-duplicated, never showing ids:
- structure edges as-is between Item paper nodes: `contains` ("is part of"), `answers` ("is answered in"), `refs` ("refers to");
- Item to Shared item: "rests on";
- Item to Reference: "cites" (only when References are on).
Direction as in the data: `from` rests on `to`. "Supports" = incoming, "Rests on" = outgoing.

### 1.4 Item status (computed per Item, one word)
Inputs for Item `I` and its set `N(I)` = its paper node plus all its Evidence nodes: alarms ([§8](../../architecture/data-model.md): membership in `changed` or `downstream` of any group), triage ([§10](../../architecture/data-model.md), `effective_state`, with `outdated` meaning unreviewed again), findings (`nodes` containing the paper node, plus the finding's triage).

Per node `x` in `N(I)`: `s(x)` = `Needs fixing` if effective_state is needs_fixing; `Needs a second look` if `x` is in an alarm group and effective_state is unreviewed; `Looks fine` if in an alarm group and reviewed; `Ignored` if in an alarm group and ignored; else none. Per finding `f` on the Item with severity `warning`: `Needs a second look` if effective_state unreviewed, `Needs fixing` if needs_fixing, else none (`info` findings never change status; they add to the check count).

**Item status = first match in this order:** Needs fixing, Needs a second look, Looks fine (all flagged nodes reviewed, at least one), Ignored (all flagged nodes ignored), otherwise **Up to date** (nothing changed since last checked). Chip table (words and glyphs reuse [DESIGN.md](../DESIGN.md#status-chips)):

| UI status | Glyph | Replaces DESIGN.md word | Fill / text |
|---|---|---|---|
| Up to date | ✓ | Confirmed | --verify-bg / --verify |
| Needs a second look | ↻ | Recheck | --amber-bg / --amber-text |
| Looks fine | ✓✓ | Reviewed | --verify-bg / --verify |
| Needs fixing | ✕ | Needs fixing | --red-bg / --red |
| Ignored | – | Ignored | --neutral-bg / --muted |

Separate small chip beside status: `{n} checks` (neutral, "!" glyph) when the Item has findings of any severity. Checks that are `info` therefore stay visible without raising the status. "Mismatch", "Not traced", "Could not be matched" chips remain as the per-check chips inside Checks.

Triage action on a Change card or Item page writes `POST /api/triage` for every node of the affected set that is in an alarm group (target_type `node`); on a finding it writes target_type `finding`. States map: Looks fine = `reviewed`, Needs fixing = `needs_fixing`, Ignore = `ignored`, and "Reset to not looked at" = `unreviewed`.

### 1.5 Item importance (size)
`links(I)` = number of distinct Items connected by an Item-level edge (either direction). `I = links + 0.5 * evidenceCount`. This reads as "how many things connect to it", matching both the founder wording (things rest on it) and Obsidian's sizing by connections. Radius in graph pixels (zoom 1): `r = max(16, 16 + 32 * sqrt(I / I_max))`, with the Main claim at least 36 and Shared items `max(12, 0.75 * r)`. Minimum diameter 24 px meets DESIGN.md hit-target rule. Items whose status is not Up to date get no size change (status is the ring, not the size).

---
## 2. Global layout (1440 x 900 reference; minimum 1024 wide)

```
+----+----------------+------------------------------------------+------------------+
|    | 260 left       | centre (flex)                            | 300 right        |
| 44 | sidebar        | tab bar 36px                             | sidebar          |
| rib|                +------------------------------------------+                  |
| bon|                | page / graph                             |                  |
|    |                |                                          |                  |
+----+----------------+------------------------------------------+------------------+
| status bar 24px: Last checked ... | things to look at | sync                        |
+---------------------------------------------------------------------------------+
```
- Ribbon 44 px wide, `--sunken` background, 1px `--border` right edge. Top to bottom (icon = plain Unicode glyph, 28 x 28 hit area, tooltip + `aria-label` carry the word): Changes (✎ glyph "◔"), Search ("⌕", opens quick switcher), Graph ("◉"), Command palette ("⌘"). Bottom: Sync ("⟳"), Help ("?"), Project menu ("⋯": project name, Export report, Upload paper as zip (only if paper source is zip), Show "How Lemmata works", Hide/Show sidebars).
- Left sidebar 260 px (`--left-w`), right sidebar 300 px (override `--right-w: 300px`). Both `--paper` background, 1px `--border` inner edge, collapsible: buttons in the tab bar ends and shortcuts ⌘\ (left), ⌘⇧\ (right). Collapse animates width over `--motion` to 0. Remembered in localStorage. Resizable by dragging the inner edge between 220-380 px (left) and 260-420 px (right).
- Centre: `--surface`. Tab bar 36 px: back/forward arrows (⌘[ / ⌘]), tabs, "+" opens quick switcher. Tab = glyph + title (max 24 chars, ellipsis) + "×". Active tab has `--surface` fill and 2px `--ink` top border; inactive `--paper`. Click item reuses the current non-Graph tab; ⌘-click or middle-click opens a new tab. Changes and Graph tabs are singletons and not closable by accident (× asks nothing; they reopen from the ribbon). Max 8 tabs; the least recently used item tab closes first. Open tabs restore on reload.
- Status bar 24 px, `--sunken`, `--fs-12`, `--muted`. Left: `Last checked: today 13:30` (click opens Mark-as-looked-at dialog), `3 things to look at` (click opens Changes), `10 checks` (click opens Checks). Right: `Synced 5 min ago` + `Sync now`, and while running `Checking your files…`.
- Below 1280 px the right sidebar starts collapsed; below 1024 px show the existing notice only.
- Light theme only in this sprint. A dark variant would remap `--ink`/`--paper`/`--surface` and is deferred.

Fonts: UI `--font-sans` 13 px; Item page titles `--font-serif` 28 px; paper snippets and the outline of sections `--font-serif`; paths, hashes, numbers `--font-mono` with tabular numerals.

---
## 3. Views

### 3.1 Left sidebar (explorer)
Top: search field, placeholder `Search items, files and checks`, ⌘O focuses it. Typing filters all trees live and shows a flat "Results" list (Items first, then files, then checks), max 50 rows, with kind word beside each.

Below, six rows (14 px, 32 px tall):
1. `Changes` + count badge `3` (amber fill `--amber-bg` with word "3 new" in tooltip) opens the Changes tab. Badge = number of change cards not yet fully looked at.
2. `Paper` (tree, expanded by default): Main claim, `Research questions` group, then sections in paper order (sort by `attrs.number`: numbers ascending, then A, B, ...; "Appendix" divider before letters; ties by `loc.line`), each with its subsections, figures, tables and equations as children. Row = status glyph (left) + title (serif for Sections) + at right, for collapsed parents, `↻ 2` roll-up of children needing a look. Footer toggle `Only things to look at` (default off). Click opens the Item page.
3. `Experiments` (tree): a group per script that runs execute (`executes` target), group title `Experiment: train.py`; rows are runs, `train_main · 30 Sep 14:00`, status glyph of the Item it is evidence for. Click opens that Item's page scrolled to the run row. Runs not used by any Item open a plain Evidence page (3.9).
4. `Code` (tree of folders): files of every code repo (`code`, `config`, `data`, `doc`, `result`, `asset`, `run` records hidden). Row = file name; second line in `--muted` 11 px: `Part of Table 2` / `Shared by Table 2 and Appendix B` / `Not used by the paper`. Click opens the Item page (or the Evidence page for unused files).
5. `Checks` + count badge: opens the Checks tab.
6. `History`: opens the History tab.

Each tree row hover shows a 1-line tooltip with the plain-language status ("Needs a second look: configs/default.yaml changed 2 days ago").

### 3.2 Landing view: Changes tab (default)
Tab title `Changes since 2 Oct`. Date = checkpoint `created_at`, absolute day.

Structure (max content width 760 px, centred, 24 px padding):
1. Title (serif 28): `What changed since you last looked`
2. Sub-line: `Last checked: today 13:30 · note "{note}"` (note only if set) · button `Mark everything as looked at`.
3. Summary strip, one sentence: `{c} changes · {i} items may need a second look · {k} checks about your paper` with each part a link (cards, first card, Checks tab). With zero: see empty state.
4. Filter chips with counts: `All 3`, `Not looked at 2`, `Needs fixing 1`, `Looks fine 0`, `Ignored 0`. A card's state = worst state over its affected items.
5. Day headers (`Today`, `Yesterday`, `2 Oct`), newest change first. One **card per change** (= one alarm group, [§8](../../architecture/data-model.md)); a change that touched several files stays one card.

**Card anatomy** (surface, 1px border, radius 6, 16 px padding, no shadow):
- Line 1, cause sentence (templates in 4.2), 14 px medium; the time as muted suffix.
- Line 2, consequence sentence (templates in 4.3): `3 things may need a second look: Table 2, the run train_main, results/table2.csv (not regenerated yet)`.
- Affected list: Items first, each a row `[status chip] Table 2 — Main results   Section 5`, then under it indented, muted, the evidence on the way (`the run train_main`, `results/table2.csv · not regenerated yet`). The caused-by-file row is shown first in the list as `Changed: configs/default.yaml` (neutral chip `Changed`).
- Optional flag banner (amber-bg): from event flags, text in 4.2.
- Buttons row: `Why?` (toggle, expands inline: the chain as a vertical stepped list in plain words, then the diff in a mono block; loads `/api/analyze` for the first affected node, shows `Loading the reason…` meanwhile), `Looks fine`, `Needs fixing`, `Ignore`, spacer, `Open Table 2` (primary affected Item; `Open items` menu when more than one).
- `Needs fixing` reveals a one-line input `Add a note (optional)` with `Save` / `Cancel`. The note is attached to every node.
- After triage the card collapses to one line: chip + cause sentence + `Undo` (resets to unreviewed). Partial state: chip `Partly looked at (2 of 4)`.
- Card ids, `A1`, commit hash only in the cause line's secondary text: `commit 2836100` (mono, muted, selectable; click copies).

**Mark everything as looked at** opens a dialog (modal, 420 px):
- Title: `Mark everything as looked at?`
- Body: `Lemmata will start counting changes from now. Your notes and Looks fine / Needs fixing marks are kept. Earlier marks stay in History.`
- Optional field: `Add a note to this mark (optional)`.
- Buttons: `Cancel`, `Mark everything as looked at` (primary, Ink fill).
- Result (`POST /api/checkpoints`): toast `Done. Last checked: today 13:30.` and Changes shows the empty state.

Empty states:
- No change since checkpoint: icon "✓" + `Nothing has changed since 2 Oct, 13:30.` / `Everything Lemmata knows about is as you left it.` / links `See your checks (10)` and `Open the graph`.
- No checkpoint yet (`checkpoint: null`): `You haven't set a starting point yet.` / `Lemmata needs to know when you last felt sure about your paper. It will then list everything that changes after that.` / primary `Start tracking from now`.
- First load while scanning: skeleton cards (3 grey 96 px blocks) and text `Reading your paper and code…`.

### 3.3 Item page (tab)
Reading width 720 px, serif title. Sections top to bottom, each a heading (13 px bold, uppercase never) so the Outline in the right sidebar lists them:
1. **Title row**: `Table 2 — Main results` (name + detail), kind label `Table in Section 5` (muted, sans), status chip, check chip `1 check`. Right: `Open graph around this item`.
2. **Why it needs attention** (only if status is not Up to date): amber/red-tinted block with the status sentence (4.4) and `Why?` expander (chain + diff) and triage buttons `Looks fine` / `Needs fixing` / `Ignore` plus note field `Your note`.
3. **What this is**: one sentence from 4.5.
4. **Evidence** (heading `Behind this item`): grouped lists, each row = glyph, mono path or name, status chip, muted `changed 2 days ago · commit 2836100` or `not changed`. Groups only when non-empty, in this order: `Results and figures` (result/asset), `Scripts` (code), `Runs`, `Settings` (config), `Data` (data/doc), `Shared with other items` (links to Shared items: `configs/default.yaml · also used by Appendix B`). Row click expands inline to show diff vs last checked (only for changed nodes) or `Not changed since last checked`. Row actions: `Copy path`. If no evidence: `Nothing behind this item yet. If it comes from a result file or script, add a note in the LaTeX source like % source: results/table2.csv.` with `Show example` toggling a mono snippet.
5. **Where it appears in the paper** (heading `In your paper`): `main.tex line 88` mono, then a serif-less mono block with the first source line(s) available from edge or finding evidence `text`, or the caption when none. Engine note: the API has no source-file endpoint; if only the caption is available show it as `Caption: "…"`. Request to CTO (optional): `GET /api/source?repo&path&from&to`.
6. **Checks about this item**: finding sentences (4.6) with `Open evidence` that jumps to Checks.
7. **What changed here** (heading `History`): events from `/api/events` whose `changed_nodes` intersect `N(I)` (when `changed_nodes` is null, fall back to events whose `files[].path` equals an Evidence path), newest first, sentences from 4.2; `Nothing has changed here since the start` when empty.
8. **Notes**: textarea `Your note`, saved via triage note; shown as typed. History of earlier notes under `Earlier notes`.

Shared item page: same, but sections 4 becomes `Used by` (Items list) and 3 reads `A file that several parts of your paper rest on.` Evidence page (3.9) for unused files.

### 3.4 Graph tab
Canvas 2D (with SVG overlay for focus rings and tooltips). Toolbar over the canvas (top-left, 36 px): search field `Find an item`, `Whole paper | Around this item` toggle, `Filters` button, `List view`, `Re-arrange`, zoom `−` `+` `Fit`. Legend bottom-left (always visible, words): `✓ Up to date  ↻ Needs a second look  ✕ Needs fixing  ✓✓ Looks fine  – Ignored`, `Circle size = how many things connect to it`, and when an item is selected `▲ Rests on (blue, solid)  ▼ Supports (orange, dashed)`.

**Nodes.** One circle per Item (1.5 sizing). Fill = kind tint (`--layer-thesis-t` Main claim, `--layer-question-t` RQ, `--layer-section-t` Section, `--layer-paper-t` Figure/Table/Equation, `--layer-code-t` Shared code, `--layer-result-t` Shared data, `--layer-reference-t` Reference). Kind is also a glyph centred in the circle (Main claim "◆", Research question "?", Section "§", Figure "▣", Table "▦", Equation "∑", Shared "{ }", Reference "[ ]"), so kind never depends on colour. Ring: 2 px `--border-strong` when Up to date; status ring otherwise: ↻ 3 px `--amber` plus dashed pattern (6 4); ✕ 3 px `--red` solid double line; ✓✓ 3 px `--verify`; Ignored 1 px `--muted` dotted. Plus a 14 px status badge (white disc with glyph, `--fs-11`) at the upper right. Selected: 3 px `--ink` outer ring.

**Layout (force-directed, hand-written, no library needed up to ~300 underlying nodes; items are far fewer):** forces: link attraction (target length `60 + 0.6 * (r_a + r_b)`), many-body repulsion (strength `-(120 + 12 * r)`), centring, and collision radius `r + 8` (so circles never overlap). Run 250 ticks before first paint, then keep alpha-decay animation to rest in about 1 s. Seed from a deterministic ring (angle = index, radius by kind order Main claim, RQ, Section, Figure/Table/Equation, Shared) so reloads and screenshots look the same. Dragging pins a node (pinned = small "•" mark; double-click unpins). Positions persist in localStorage per project. `Re-arrange` clears pins.

**Labels (first glance readable).**
- Font 13 px sans (12 px for r < 20), 3 px halo in `--paper` for legibility, placed below the circle, max 26 chars then "…". Full title on hover.
- Always shown: the top `N = max(8, ceil(0.2 * items))` (cap 16) by importance; every Item whose status is not Up to date (label adds a second line with the status word, e.g. `Table 2 · needs a second look`); the selected Item and its direct neighbours; hovered Item and neighbours.
- Others: shown when `r * zoom >= 14`, in importance order, only if their label rectangle does not overlap an already placed label or circle (greedy, recomputed when layout settles and after zoom/pan end). Label priority wins over smaller circles.
- Minimum on-screen label size 11 px, never scaled below that.
- Result at fit-all zoom: the Main claim, RQs, big sections and flagged items are named; the rest appear as the user zooms in.

**Filters** (Filters popover, checkboxes, `--r-lg`, 280 px): 
- `Show`: `Sections`, `Figures, tables and equations`, `Shared code and data`, `References` (default off), `Files behind items` (default off: shows each Item's Evidence as small satellite dots r 6, labelled on hover only), with sub-toggles `Code`, `Runs`, `Results and data`, `Settings`.
- `Files not used by the paper` (default off).
- `Only things that changed` (default off): dims every Item that is Up to date.
- `Depth` slider 1-3 (enabled only in `Around this item`, default 2).
- Expand per item: double-click an Item, or the `+ Show files behind this` button in its hover card, expands its Evidence as satellites in place; `−` collapses.

**Interaction.** Hover: node and direct neighbours stay, others to 0.15 opacity, edges of hovered node coloured by direction (`--up` solid, `--down-stroke` dashed, 2 px); tooltip card (surface, `--shadow-pop`): title, kind label, status chip, `{n} connections`. Click: opens the Item page in a new tab and selects it (right sidebar updates). Click empty space: clears selection. Drag a node: moves/pins. Scroll: zoom 0.25-4 around cursor. Drag background: pan. Default edge: 1 px `--border-strong` at 40% opacity, no arrows. Keyboard: Tab moves through Items in importance order (focus ring `--focus-ring`), arrows jump to nearest connected Item, Enter opens, `Esc` clears, `/` focuses search. `List view` replaces the canvas by a sortable table (Item, Kind, Status, Connections) for screen readers.

**Local graph.** `Around this item` and the right-sidebar mini graph show the selected Item and Items within `Depth` hops, same drawing rules, no filters.

### 3.5 Right sidebar (300 px)
Accordion sections for the open Item (Obsidian's link panels). Section header 13 px bold + count, collapsible.
1. `Rests on` (outgoing links): rows = the Item's direct evidence top level (`results/table2.csv`, then its script/config) and Shared items and referenced Items; each with glyph, name, relation in muted text (`built from`, `uses`, `part of`). Empty: `Nothing. This item stands on its own.`
2. `Supports` (backlinks): Items that rest on or contain it, relation (`contains it`, `refers to it`). Empty: `Nothing else rests on this yet.`
3. `Local graph`: 276 x 200 canvas; click a node to open; `Depth` stepper 1-3; `Open in Graph tab`.
4. `Recent changes`: up to 5 sentences (4.2) with `See all in History`.
5. `Outline`: the headings of the open Item page; click scrolls.
Section 1-2 rows are clickable (open Item); hover highlights in local graph. With the Changes tab open (no Item): `Open an item to see what it rests on and what rests on it.` With the Graph tab: the hovered or selected Item's sections, same content.

### 3.6 Paper outline
The left Paper tree (3.1). Extra behaviour: keyboard arrows navigate, Enter opens, `*` expands all. Roll-up chip on collapsed parents: `↻ 2` (glyph + number, tooltip `2 items need a second look`). Appendix divider labelled `Appendix`. References are not in this tree.

### 3.7 Experiments
Left tree only (3.1 item 3). Run row tooltip: `train_main — python train.py --config configs/default.yaml — started 30 Sep 14:00`. Empty: `No runs recorded yet. Lemmata finds runs from files like runs/train_main.json.` with `How to record a run` link that opens a short help popover (the run-record format of data-model §11.1 in plain words).

### 3.8 Code
Left tree only (3.1 item 4). Empty: `No code connected. Connect your code repo in the project menu.`

### 3.9 Evidence page (for files and runs that are not Items)
Title = path, kind sentence (`A script in your code. It is not used by anything in the paper yet.`), `Used by` list, `Changed since last checked` diff if any, `Copy path`. Shown only from Code, Experiments or search.

### 3.10 Checks tab
Title `Checks`; sub-line `Things Lemmata found by reading your paper and code. A check is a suggestion to look, not a verdict.` Top chips: `All 10`, `Needs a second look 8`, `Looks fine 0`, `Needs fixing 0`, `Ignored 0`, plus the checks that did not run: `Not checked 1`.

Sections (collapsible, with counts), title = plain name of the check ([§6.2](../../architecture/data-model.md)):
`Numbers that differ between text and appendix`, `References that could not be matched`, `Cited things that do not exist`, `References nobody cites`, `Figures and tables never mentioned`, `Links to things that do not exist`, `Numbers not found in any result file`, `Figures with no known source`.
Each finding card: status chip, sentence (4.6), evidence list `main.tex line 57 — "We train with a learning rate of …"` (mono, quote), the Items it concerns as links (`Section 4`, `Appendix B`), buttons `Looks fine`, `Needs fixing`, `Ignore`, `Open evidence`. If a check did not run: `Not checked: no paper connected` (never shown as passed, neutral chip `Not checked`).

**Suggested links** (last section, heading `Suggested links`, sub-text `Lemmata noticed matches between your paper and your files. Nothing is linked until you say so.`): one row per `proposed` edge (`value_match`), sentence from 4.7, buttons `Yes, link them` (approved), `No, don't suggest this` (rejected), after deciding `Undo` (proposed). A rejected one is listed under `Hidden suggestions (1)` with `Bring back`. Empty: `No suggestions right now.` Approving updates statuses immediately (alarms recompute) and shows a toast `Linked. Appendix B now rests on configs/default.yaml.`

### 3.11 History tab
Vertical timeline, newest first, by day. Rows: time, glyph (commit "●", run "▲", unsaved changes "◌", mark "⚑"), sentence from 4.2, repo word (`code` / `paper`), short hash mono. A horizontal rule labelled `Last checked: 2 Oct, 13:30` sits at the checkpoint; events above it have the muted tag `Since then`, below `Before`. Earlier marks are listed as `⚑ You marked everything as looked at · "{note}"`. Filters: `All`, `Code`, `Paper`, `Runs`. Empty: `No history yet.`

### 3.12 Command palette (⌘P / Ctrl+P) and quick switcher (⌘O)
Centered modal 560 px, input `Type a command or an item`, results 8 rows with keyboard hints. Commands (exact names): `Go to Changes`, `Go to Graph`, `Go to Checks`, `Go to History`, `Open item…` (same as quick switcher ⌘O, fuzzy over Items and files), `Mark everything as looked at`, `Mark this item as Looks fine`, `Mark this item as Needs fixing`, `Ignore this item`, `Sync now`, `Show files behind items`, `Toggle left sidebar`, `Toggle right sidebar`, `Export report (HTML)`, `How Lemmata works`. Disabled commands show a reason (`No item open`). Esc closes. Shortcuts: ⌘[ back, ⌘] forward, ⌘W close tab, ⌘1-9 tab, `g c` Changes, `g g` Graph.

### 3.13 First-run explainer
Modal 560 px, shown once (localStorage `lemmata.seen_intro`), also from Help. Three steps with Back / Next / `Skip`, dots `1 of 3`:
1. Title `Lemmata keeps track of your paper and your code.` Body: `It reads your paper and the code and results behind it, and remembers how they fit together.`
2. Title `When something changes, it tells you what it affects.` Body: `Change a setting or a script and Lemmata lists the tables, figures and sections that may no longer match. You don't have to watch it. Open it when you need it.`
3. Title `You decide what is fine.` Body: `For each change, choose Looks fine, Needs fixing or Ignore. When you are happy, press "Mark everything as looked at" and Lemmata counts from there.` Final button `Show me what changed`.

### 3.14 States (all views)
- Loading: skeleton blocks, status bar `Reading your paper and code…`; Graph shows `Arranging your items…` over a spinner-free pulse.
- Scan running (409 `busy`): toast `Lemmata is already checking your files. Try again in a moment.`
- Server unreachable: full-centre `Can't reach Lemmata.` / `The local server isn't answering. Check that Lemmata is still running, then try again.` / `Try again`.
- Request failed (500): toast `Something went wrong on our side. Your files and marks are unchanged.` with `Details` (shows `error.message`).
- Read-only export snapshot: top banner `Read-only snapshot from {date}. You can look around but not change anything.`, all action buttons disabled with that tooltip.
- Paper not connected: Paper tree shows `No paper connected yet.` + `Connect your paper` (opens the project menu). Checks that need a paper show `Not checked`.
- Sync failed (hub): status bar `Sync failed · Try again`.
- Unknown error in graph (canvas unsupported): fall back to List view.

---
## 4. Copy and templates

### 4.1 Glossary (internal term to UI word)
| Internal | UI word |
|---|---|
| node | item (paper things), file or run (evidence) |
| edge / `propagates` | "rests on" / "supports" |
| upstream / downstream | rests on / supports |
| alarm, alarm group | "needs a second look" / a change (card) |
| checkpoint | "last checked" (the mark: "Mark everything as looked at") |
| finding | check |
| check `status: ran / not_applicable` | checked / not checked |
| triage `reviewed` / `needs_fixing` / `ignored` / `unreviewed` | Looks fine / Needs fixing / Ignore / Not looked at |
| `outdated` triage | `Changed again since you marked it` |
| analyzer / chain | "Why?" |
| `proposed` / `approved` / `rejected` link | suggested link / linked / hidden suggestion |
| `value_match` | suggested link |
| layer, kind, repo, hub, scan, hash | not shown. Use: "kind word", "paper / code", "project", "sync", "check your files", never shown |
| `event` commit/run/worktree/snapshot/diverged | change / run / unsaved changes / copy changed / history rewritten |
| run | run (with a one-line help) |
| evidence (finding) | where it is written |
Never show: `tex:`, `file:`, `ev:`, `run:`, `A1`, `node`, `edge`, `layer`, `hub mode`, `hash`, `propagate`, `downstream`, `upstream`. Wording ban from [data-model §6.2](../../architecture/data-model.md): never `wrong, fake, fabricated, mistake, error by, cheat`.

### 4.2 Change sentences (cause line)
Time = `today 13:30`, `yesterday`, `{n} days ago` (up to 14), else `{d} {Mon}`; absolute time in tooltip. Short hash after the time: `· commit 2836100`.
- Config file, one key changed (read from the `/api/analyze` diff: first `-key: v` / `+key: v` pair; key humanised, underscores to spaces): `You changed {path} ({key} {old} → {new}) · {time} · commit {short}`. Example: `You changed configs/default.yaml (learning rate 3e-4 → 1e-3) · 2 days ago · commit 2836100`. Number display: `3.0e-4` shown as `3e-4`.
- Config file, several keys: `You changed {n} settings in {path} · …`. Diff unavailable: `You changed {path} · …`.
- Code file: `You edited {path} · …`. Several files: `You edited {n} files in {repo-word} (train.py, eval.py and 1 more) · …`.
- Result/data file: `Your file {path} changed · …`. Added: `You added {path}`. Removed: `You removed {path}`.
- Paper unit: `You edited {Item title} in your paper ({path}) · …`. Several: `You edited {n} places in your paper`.
- Commit message as fallback tail: `{subject}` in quotes, muted, under the sentence, only on expand.
- Run: `A run finished: {run id} · {time}`.
- Worktree: `You have changes in {repo-word} that are not saved to git yet · {time}`.
- Snapshot: `Your {repo-word} files differ from when you last checked`.
- Diverged: `The history of your {repo-word} was rewritten since you last checked, so everything there is listed here.`
- Flag `message_claims_no_change`: `The commit message says "{phrase}", but content changed in {n} files.`
- `repo-word`: `code` or `paper`.

### 4.3 Consequence sentences
- `{n} things may need a second look: {a}, {b}, {c}` (`and {m} more`), `n = 1`: `1 thing may need a second look: {a}`. List order: Items by importance, then evidence by distance. Evidence names: `the run {id}`, `{path}`; suffix ` (not regenerated yet)` when the file is downstream with `output_identical: true`, ` (regenerated, content differs)` when `false`.
- Only the changed thing, nothing downstream: `Nothing else rests on this yet.` (as for Appendix B in state 0).
- Item rows reason line: `Rests on {path}, which changed {time}.` / `Changed {time}.`
- Nothing identical changed (reverted): not shown (no alarm), but History shows the commits.

### 4.4 Item status sentence
- Up to date: `Nothing behind this item has changed since you last looked.`
- Needs a second look: `Something this item rests on changed {time}: {cause short}. {consequence}.` e.g. `Something this item rests on changed 2 days ago: you changed configs/default.yaml (learning rate 3e-4 → 1e-3). results/table2.csv has not been regenerated yet.`
- Needs fixing: `You marked this as needing a fix{ on {date}}.` + note.
- Looks fine: `You marked this as looking fine on {date}.` and, if outdated: `It changed again since then, so Lemmata asks you to look again.`
- Ignored: `You chose to ignore this item.`

### 4.5 "What this is" per kind
- Table: `A table in {Section title}. It is built from {primary result path}, produced by {script} on {run}.` Pieces drop when absent: `A table in Section 5. It is not linked to a result file yet.`
- Figure: `A figure in {Section}. It is made by {script} from {result path}.` / `A figure in {Section}. You said it is drawn by hand.` (manual).
- Equation: `An equation in {Section}.`
- Section: `Section {number} of your paper. It contains {k} figures, tables or equations.`
- Main claim: `The abstract of your paper. {k} research questions and {m} sections rest under it.`
- Research question: `A research question your paper states. It is discussed in {Section list}.`
- Shared code/data: `A file that {n} parts of your paper rest on: {Item list}.`
- Reference: `A cited work. Cited in {Section list}.`

### 4.6 Check sentences ([§6.2](../../architecture/data-model.md) checks)
- `reference_unmatched`: `The reference "{title}" ({key}) could not be matched in OpenAlex or Crossref. Check its title, year or DOI.` Chip `Could not be matched`.
- `main_appendix_mismatch`: `{Learning rate} differs: the main text says {3e-4} and the appendix says {1e-3}.` Chip `Differs`. Sub-lines `main.tex line 57`, `appendix.tex line 14`.
- `uncited_reference`: `{key} is in your bibliography but nothing cites it.`
- `unreferenced_float`: `{Figure 1} is never mentioned in the text.` / unlabelled: `{Figure 1} has no label, so it cannot be mentioned in the text.`
- `undefined_ref`: `The text refers to "{fig:missing}", but nothing in the paper has that name.`
- `undefined_cite`: `The text cites "{nobody2020}", which is not in your bibliography.`
- `untraced_number`: `The number {92.4} in {Section 5} was not found in any of your result files.` Chip `Not traced`.
- `figure_without_provenance`: `{Figure 3} has no script or note saying where it comes from.`
- Not run: `Not checked: {note}` (note mapped: `no paper connected`, `no appendix found`).

### 4.7 Suggested link sentence
`{Item A} mentions {learning rate 1e-3}, and {path} sets {learning rate} to {1.0e-3}. Should Lemmata treat them as the same setting?` Taken from edge `reason` (`learning_rate: paper 1e-3, config 1.0e-3`). Confidence word shown: `Suggested`.

### 4.8 Buttons and headings (list)
`Mark everything as looked at`, `Looks fine`, `Needs fixing`, `Ignore`, `Why?`, `Open {Item}`, `Undo`, `Sync now`, `Show files behind items`, `Open graph around this item`, `Yes, link them`, `No, don't suggest this`, `Bring back`, `Export report (HTML)`, `Upload paper as zip` (fallback, project menu only), `Try again`, `Skip`, `Next`, `Back`, `Start tracking from now`, `Show me what changed`. Headings: `What changed since you last looked`, `Checks`, `History`, `Behind this item`, `In your paper`, `Checks about this item`, `Notes`, `Rests on`, `Supports`, `Local graph`, `Recent changes`, `Outline`, `Suggested links`.
Time words: `just now`, `{n} min ago`, `today 13:30`, `yesterday`, `{n} days ago`, `{d} {Mon}`.

---
## 5. Tokens
Reuse [DESIGN.md](../DESIGN.md#tokens) unchanged (palette, type, spacing, chips, lineage colours). Additions, all derived from existing palette values:
```css
:root {
  --ribbon-w: 44px;         /* ribbon */
  --right-w: 300px;         /* overrides 380px */
  --tab-h: 36px;
  --status-h: 24px;
  --bg-ribbon:  var(--sunken);
  --bg-sidebar: var(--paper);
  --bg-centre:  var(--surface);
  --node-r-min: 16px;       /* graph circle, zoom 1 */
  --node-r-max: 48px;
  --node-r-main-min: 36px;
  --node-r-shared-min: 12px;
  --node-r-evidence: 6px;
  --graph-edge: var(--border-strong);   /* at 40% opacity */
  --graph-halo: var(--paper);           /* label halo, 3px */
}
```
Unused from DESIGN.md in the new UI: `--timeline-h`, `--band-h`, `--layer-run*`, `--layer-result*` apart from Shared data tint. Status is never colour alone: glyph in a badge plus a word in every list, tooltip, label (flagged items) and legend; ring style also varies (solid, dashed amber, double red, dotted grey). Direction is blue solid / orange dashed plus the words "Rests on" / "Supports".

---
## 6. Wireframes

### 6.1 Changes
```
+--+--------------+----------------------------------------------------+---------------+
|◔ |[Search...  ]|[Changes since 2 Oct ×][Graph]                  [+] |               |
|⌕ |Changes   [3]|----------------------------------------------------|Open an item to|
|◉ |> Paper       | What changed since you last looked                 |see what it    |
|⌘ |> Experiments | Last checked: today 13:30  [Mark everything as     |rests on and   |
|  |> Code        |                              looked at]            |what rests on  |
|  |Checks    [10]| 3 changes · 5 items may need a second look · 10    |it.            |
|  |History       |   checks                                           |               |
|  |              | [All 3][Not looked at 2][Needs fixing 1] ...       |               |
|⟳ |              | Today                                              |               |
|? |              | +------------------------------------------------+ |               |
|⋯ |              | |You changed configs/default.yaml (learning rate | |               |
|  |              | |3e-4 → 1e-3) · 2 days ago · commit 2836100      | |               |
|  |              | |3 things may need a second look: Table 2, the   | |               |
|  |              | |run train_main, results/table2.csv (not regen.) | |               |
|  |              | | [↻ Needs a second look] Table 2 — Main results | |               |
|  |              | | [Why?][Looks fine][Needs fixing][Ignore] [Open]| |               |
|  |              | +------------------------------------------------+ |               |
+--+--------------+----------------------------------------------------+---------------+
| Last checked: today 13:30 · 3 things to look at · 10 checks      Synced 5 min ago    |
+----------------------------------------------------------------------------------------+
```
### 6.2 Item page
```
+--+--------------+----------------------------------------------------+---------------+
|  | Paper        |[Changes][Graph][Table 2 — Main results ×]          | Rests on (2)  |
|  |  §4 Setup    |----------------------------------------------------|  results/..csv|
|  |   ↻ Table 2  | Table 2 — Main results                             |  train.py     |
|  |  §5 Results  | Table in Section 5   [↻ Needs a second look] [1 chk]| Supports (2)  |
|  |              | +----------------------------------------------+   |  §5 contains  |
|  |              | | Something this item rests on changed 2 days  |   | Local graph   |
|  |              | | ago: ... [Why?] [Looks fine][Needs fixing]   |   |   (o)-(O)-(o) |
|  |              | +----------------------------------------------+   | Recent changes|
|  |              | What this is                                       |  You changed..|
|  |              | A table in Section 5. It is built from ...         | Outline       |
|  |              | Behind this item                                   |  What this is |
|  |              |  Results: results/table2.csv   [↻ Not regenerated] |  Behind...    |
|  |              |  Scripts: train.py   Runs: train_main  Settings: ..|               |
|  |              | In your paper   main.tex line 88  | ...snippet...  |               |
+--+--------------+----------------------------------------------------+---------------+
```
### 6.3 Graph
```
+--+--------------+----------------------------------------------------+---------------+
|  | (left tree)  |[Changes][Graph ×][Table 2 ×]                       | Rests on      |
|  |              | [Find an item][Whole|Around][Filters][List][Fit]   | Supports      |
|  |              |            (RQ1)        (RQ2)                      | Local graph   |
|  |              |       (§3)   ╲   ◆ Main claim ╱  (§1 Intro)        |               |
|  |              |         ╲       ( ◆ )      ╱                       |               |
|  |              |   [§4 Setup]----(▦ Table 2 ↻)---(§5 Results)      |               |
|  |              |   [{ } configs/default.yaml · Shared code]         |               |
|  |              |   Table 2 · needs a second look                    |               |
|  | legend: ✓ Up to date  ↻ Needs a second look  ✕ Needs fixing ...   |               |
+--+--------------+----------------------------------------------------+---------------+
```
