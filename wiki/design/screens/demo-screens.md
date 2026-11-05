---
type: screen-spec
owner_agent: designer
status: draft
sources: ["founder brief to designer, 2026-11-04 (task message, S02 localhost demo)", "../DESIGN.md"]
last_reviewed: 2026-11-04
---
# Lemmata screens (demo, desktop >= 1280px, plain HTML/CSS/JS + SVG)

Tokens: [DESIGN.md](../DESIGN.md). Copy is English; `{x}` marks a template variable. Tone: factual, never accusing. Findings say "could not be matched", "does not agree", "no source found", never "fake", "fabricated", "wrong".

Below 1280px: show one full-page notice, "Lemmata needs a window at least 1280 px wide. Widen the window to continue."

## 0. App shell (main view grid)
```
+--------------------------------------------------------------+ topbar 44px
| Lemmata  project: sample-paper v7  [Graph|Alarms|Checks|Links]  [/ Search]  scan status |
+----------+---------------------------------------+-----------+
| Outline  | Graph (SVG, 8 bands)                  | Detail    |
| 260px    | flex (>= 620px at 1280)               | 380px     |
|          |                                       |           |
|          +---------------------------------------+           |
|          | Timeline 168px                        |           |
+----------+---------------------------------------+-----------+
```
- Tabs in topbar switch the centre+right area: Graph (default), Alarms, Checks, Links. Outline stays. Timeline shows only with Graph and Alarms.
- Link queue tab shows a count badge, Alarms a count badge, Checks a count badge; each badge has a word via aria-label ("12 to recheck").
- Right panel collapses with `]`, outline with `[` (graph gets the width).
- Global keys: `/` focus search, `F` fit graph, `Esc` clear selection/close, `G` `A` `C` `L` jump to Graph/Alarms/Checks/Links tabs (when no input focused), `?` shortcut sheet.
- Global error banner (under topbar): "Scan data could not be read. {reason}. [Rescan] [Choose another folder]".

## 1. Project picker / scan screen
Route `/`. Centred column 640px on Paper.
- Title (serif 28): "Open a project"
- Sub (muted 14): "Lemmata reads your paper, code and run logs on this computer. Nothing is uploaded."
- Card A: "Project folder". Text field (mono) placeholder "/path/to/your/paper-repo", button "Choose folder…" (browser: opens a path input dialog since localhost cannot browse; helper text "Paste the folder path that contains your .tex files and code.").
- Card B: "Bundled sample" with one line "A small ML paper with planted inconsistencies, for trying Lemmata." Button "Use sample".
- Recent projects list (up to 5): name, path (mono), "last scanned {relative time}". Empty: "No recent projects."
- Primary button "Run scan" (disabled until a folder is set; tooltip when disabled: "Choose a folder or the sample first").
- Scan progress (replaces buttons while running): stepped list, each with state glyph and word.
  1. "Reading LaTeX sources" 2. "Reading references" 3. "Reading code and result files" 4. "Reading git history" 5. "Reading run logs" 6. "Building the graph" 7. "Running checks".
  Each step: `○ Waiting` / `◐ Running {n}/{m}` / `✓ Done` / `✕ Failed`. Overall bar with text "Step {k} of 7".
  Live counts (mono): "{n} sections · {n} figures and tables · {n} equations · {n} references · {n} code files · {n} runs · {n} commits".
- Done: "Scan finished in {s} s. {n} items to recheck, {n} findings, {n} proposed links to review." Button "Open graph" (primary). Secondary "Scan again".
- Errors (inline, red text with ✕ and word "Error"):
  - Path missing: "Error: that folder was not found. Check the path and try again."
  - No .tex: "No LaTeX files were found in this folder. Lemmata needs at least one .tex file. [Choose another folder]"
  - Not git: "This folder has no git history. You can still scan, but the timeline will show paper versions and runs only. [Scan anyway] [Choose another folder]"
  - Partial failure: "Scan finished with {n} step(s) incomplete: {step names}. Results may be partial. [Open graph anyway] [Retry failed steps]"
- Keys: `Enter` runs scan, `Esc` cancels a running scan (confirm: "Stop the scan? Nothing has been saved. [Stop] [Keep scanning]").

## 2. Graph (main view)
Region: centre column, height = viewport - 44 - 168.
**Bands.** 8 horizontal bands, 88px each (scroll vertically if taller than region; default fit). Left margin 120px band label column (sticky): "Thesis", "Questions", "Sections", "References", "Paper items", "Repo results", "Code", "Runs". Each label shows the layer colour stripe, name, and node count in mono: "Code 42". Band background alternates Paper / `--sunken` at 40%.
**Nodes.** Rounded rect `--r-md`, min 24px tall, width by label (max 160px, ellipsis, full label in tooltip). 4px left stripe in layer colour, layer glyph (T, Q, §, R, F/T/E for figure/table/equation, ▤ result, { } code, ▶ run) so layer is not by colour alone. Status bar + glyph per DESIGN.md chips. Label font 12px sans; paths mono.
**Groups.** A group node (e.g. folder `src/models/`) is a dashed-border rect with "▸ src/models/ (14)" ; click chevron or press `Enter` to expand/collapse; `Shift+click` on band label collapses/expands the whole band. A collapsed group aggregates status: shows the worst status word, e.g. "↻ 3 Recheck".
**Edges.** Thin 1px `--border-strong` curves, drawn only for hovered/selected lineage by default (toggle "Show all edges", off by default). Full graph at rest shows only band structure and nodes.
**Selection.** Click node: that node gets 3px ink outline. Lineage computed transitively: upstream nodes ("Rests on") 2px blue solid outline + edges; downstream ("Supports") 2px orange dashed. Others opacity .25. Counter chip on canvas top-left: "Rests on {n} · Supports {n}". Right panel opens. Legend bottom-left: "▲ Rests on (blue, solid)  ▼ Supports (orange, dashed)  ↻ Recheck  ✕ Needs fixing  ✓✓ Reviewed".
**Toolbar** (top-right of canvas): search field "Search nodes  /", filter menu "Show: All · Recheck only · Needs fixing · Proposed links", buttons "Fit  F", "Expand all", "Collapse all", zoom − / + (also wheel + ctrl, drag to pan).
**Hover tooltip** (node): "{label}\n{layer} · {path}:{line}\n{status word}" .
**States.**
- Loading: skeleton bands with text "Building graph…".
- Empty (no nodes): "The graph is empty. Lemmata did not find a thesis, sections or results to connect. [Back to scan]".
- Error: "The graph could not be drawn. {reason}. [Rescan]".
- No matches for search/filter: "No nodes match “{query}”. [Clear filter]".
- Checkpoint view: nodes changed since the checkpoint carry Recheck; if no checkpoint set: banner "Set a Last known good checkpoint on the timeline to see what to recheck."
**Keys.** Arrow keys move selection to nearest node (Left/Right siblings in band, Up/Down parent/child band); `Enter` toggles group; `U` highlight only upstream, `D` only downstream, `B` both (default); `R` mark Reviewed, `X` Needs fixing, `I` Ignore (apply to selected, same as triage buttons); `Esc` clear selection; `F` fit; `+`/`-` zoom; `0` reset zoom.

## 3. Outline (left, 260px)
- Header (serif 14): "Paper outline". Sub (muted 12): "{n} items to recheck" in total, mono n.
- Tree of sections from LaTeX (`\section`, `\subsection`, appendix grouped under "Appendix"): indent 12px per level; title in serif 13px, truncated; right-aligned count chip: "↻ 3" with aria-label "3 to recheck"; zero shows nothing (not "0"). Sections with needs-fixing show "✕ 1" too.
- Click section: selects its node in graph and scrolls the graph to centre it. Double click: opens the section's LaTeX preview in the right panel.
- Filter row at top: toggle "Only sections to recheck".
- Empty: "No sections found. Check that your main .tex file uses \section."
- Loading: "Reading outline…".
- Keys: Up/Down move, Enter select, Left/Right collapse/expand.

## 4. Detail panel (right, 380px)
Empty state: "Select a node in the graph to see what it rests on, what it supports, and where the evidence is."
Selected state, top to bottom:
1. **Header.** Layer glyph + label (serif 20 for sections/questions, mono for files), layer name, status chip. Path:line (mono, click copies; tooltip "Copy path"). Button "Open in editor" (uses `file:line` link; tooltip "Opens in your default editor if it supports file links").
2. **Lineage summary.** "▲ Rests on {n}" and "▼ Supports {n}" expandable lists (node label, layer, status chip); clicking an item re-selects it.
3. **Preview** (by node type; each with a caption of the source `file:lines`):
   - Paper paragraph: LaTeX excerpt, mono 12px, line numbers gutter muted, the referenced lines tinted `--amber-bg` and given a "Changed" word marker in the gutter when changed since checkpoint. "Show rendered text" toggle uses serif 16.
   - Code/result file: first 30 lines ("File head"), line numbers, "Show all {n} lines".
   - Figure: image if available; else placeholder "No image available. {path} is not a bitmap or was not found."
   - Commit/diff: unified diff, added/removed lines marked with "+"/"−" signs (not colour alone).
   - Run: config summary and metrics table (mono), run id, date.
4. **Evidence locations.** Heading "Evidence". List: `{file}:{line}` (mono) + one-line reason, e.g. "cited in main.tex:212 as Table 2", "written by scripts/eval.py:88". Empty: "No evidence locations recorded for this node."
5. **Triage.** Segmented control with three buttons and icon+word: "✓✓ Reviewed", "✕ Needs fixing", "– Ignore". Current choice shown pressed. Note field (label "Note (kept in .lemmata/triage.json)", placeholder "Why? e.g. rerun planned for Friday"), button "Save note". Saved toast: "Saved". Note: triage is stored locally with the commit hash; copy near the control: "If this node changes again, it returns to Recheck."
- Loading: skeleton + "Loading preview…". Error: "Preview unavailable: {reason}. Evidence locations are still listed."
- Keys within the panel: `Tab` order header, lineage, preview, evidence, triage; `R`/`X`/`I` triage shortcuts also work when focus is in graph or panel but not in the note field.

## 5. Timeline (bottom, 168px)
- Horizontal time axis, three lanes labelled left (80px column): "Commits", "Paper versions", "Runs". Events are 10px marks; shape differs per lane (● commit, ◆ paper version, ▲ run) so lanes are not by colour alone. Axis ticks 11px mono dates.
- Two handles (vertical lines spanning lanes, draggable, keyboard-operable with arrows when focused):
  - "Last known good" (flag at top, ink fill, label "Last known good · {short hash or date}"), default = latest paper version marked submitted, else the oldest event.
  - "Now" (label "Now · {short hash}"), default = HEAD. "Now" cannot precede the checkpoint.
  - Range between handles shaded `--amber-bg` with text "{n} commits · {n} items to recheck".
- Hover event: tooltip "{short hash} {subject}\n{author} · {date}\n{n} files changed".
- Click commit: selects it, shows its blast radius: graph highlights all nodes whose lineage includes files changed in that commit (amber outline + ↻), and a strip appears above the timeline: "Commit {hash}: {n} files changed → {n} nodes affected. [Show in Alarms] [Clear]".
- Context menu / buttons on the selected event: "Set as Last known good", "Set as Now".
- Controls: "Zoom to range", "Reset". Keys: `[`/`]` not used here; `,` and `.` step selected event previous/next; `K` set checkpoint at selected event; `N` set Now at selected event.
- Empty: "No history found. Without git history, the timeline shows only paper versions and runs."
- Loading: "Reading history…". Error: "History could not be read: {reason}."
- Changing a handle recomputes alarms; show "Recomputing…" for the badge.

## 6. Alarms
Tab "Alarms". Replaces graph and detail with a list (centre 620px+) and the chain view (right 380px; same column as detail).
- Heading (serif 20): "To recheck since {checkpoint label}". Sub: "{n} items in {n} commits".
- Grouped by cause commit: group header "{short hash} · {subject} · {author} · {date}" with count chip "↻ {n}". Collapsible; expanded by default for the first 3.
- Row: status chip, node label, layer name, path:line (mono), and a one-line reason, e.g. "Table 2 reads results/table2.csv, which changed in this commit."
- Low-confidence row: chip "? Low confidence" plus message: "Commit message says “{msg}”, but {n} lines of {file} changed. Lemmata is not sure this affects {node}." Filter chip "Low confidence only".
- Row click: opens chain in right panel; button "Show in graph".
- **Chain ("Why")**: vertical list from cause to affected node: 
  `commit {hash} → {file}:{line} changed → {intermediate node} → … → {affected node}`; each step: node label, layer, evidence `file:line`, and the link's origin word: "Direct" (parsed), "Approved" (author approved), "Proposed" is never used in a chain. Heading "Why this needs a recheck". Footer buttons: "✓✓ Reviewed", "✕ Needs fixing", "– Ignore" (same as triage).
- Empty (no checkpoint): "Set a Last known good checkpoint on the timeline to list what changed after it." Empty (none): "Nothing to recheck since {checkpoint}. Everything downstream of your changes was reviewed or unaffected."
- Loading: "Tracing changes…". Error: "Alarms could not be computed: {reason}. [Retry]".
- Keys: Up/Down rows, `Enter` open chain, `R`/`X`/`I` triage, `Space` collapse group, `Esc` close chain.

## 7. Checks report
Tab "Checks". Centre list (left half) + evidence pane (right half) when a finding is open; total width = centre+right (about 1000px at 1280).
- Heading: "Checks". Sub: "{n} findings. Each one links to the text that caused it." Filter row: kind dropdown (All kinds), status (Open / Reviewed / Needs fixing / Ignored), search.
- Finding card: kind label, message, locations (mono), status chip, [Open evidence].
- **Finding kinds and message templates** (wording never accuses):
  1. Reference could not be matched: "Reference “{key}” ({title}, {year}) could not be matched to a record in {sources searched}. Check the title, authors and year." Chip "? Could not be matched".
  2. Text and appendix disagree: "{Claim} differs between main text and appendix: {value A} at {file}:{line} and {value B} at {file}:{line}." Chip "≠ Mismatch".
  3. Unreferenced figure/table: "{Figure 3} is defined at {file}:{line} but is not referenced in the text."
  4. Uncited entry: "Bibliography entry “{key}” is not cited anywhere in the text."
  5. Undefined reference: "\\ref{{label}} at {file}:{line} has no matching \\label."
  6. Number not traced: "The value {number} at {file}:{line} was not found in any result file. {n} close values were found in {file}." Chip "∅ Not traced".
  7. Figure with no generating script: "{Figure 2} uses {path}, but no script that writes this file was found." Chip "∅ Not traced".
- **Side-by-side evidence pane** (two columns, 50/50, each with caption `file:lines`, mono, line numbers, relevant lines tinted and marked with word "Here"): left "In the paper" / right "In the {source}" (variants: "In the appendix", "In the result file", "In the reference record", "In the code"). Below: "What was compared" one line, and triage controls.
- Reference check footnote (always shown on those findings): "A match depends on the sources searched. A reference that is real but missing from them will also appear here."
- Empty: "No findings. All checks passed on this scan. This does not guarantee the paper is correct." Loading: "Running checks…". Error: "Checks could not be completed: {reason}. [Retry]".
- Buttons: "Export report (HTML)" (tooltip: "Saves a local HTML file you can share. It includes the evidence shown here.").
- Keys: Up/Down findings, `Enter` open evidence, `R`/`X`/`I`, `Esc` close pane.

## 8. Link approval queue
Tab "Links". Table of proposed links; proposals are not in the graph, lineage or alarms until approved.
- Heading: "Proposed links". Sub: "Lemmata suggests these connections from names, text and code references. They affect nothing until you approve them."
- Columns: checkbox, From (label, layer, path:line mono), arrow "→", To (same), "How it was found" (word label: "Heuristic: matching name" / "Heuristic: path in text" / "AI suggestion"), Confidence (word + number: "High 0.91", "Medium 0.62", "Low 0.31"), Evidence (`file:line`, click opens preview in a right-hand panel with both ends).
- Row actions: "Approve", "Reject". Bulk bar on selection: "Approve {n}", "Reject {n}". Rejected links stay hidden and are listed under tab filter "Rejected" with action "Restore".
- Filter: All · Heuristic · AI suggestion · Rejected; sort by confidence.
- Confirm on approving a Low-confidence link: "Approve a low-confidence link? It will be used when Lemmata traces what to recheck. [Approve] [Cancel]".
- After approve: toast "Link approved. {n} alarms updated." with "Undo".
- "Preview in graph": temporarily draws the proposed edge as dashed grey with label "Proposed".
- Empty: "No proposed links. Every link in the graph was found directly in your files." Loading: "Finding possible links…". Error: "Links could not be loaded: {reason}. [Retry]".
- Keys: Up/Down, `Space` toggle checkbox, `A` approve, `D` reject (in this tab only), `Enter` preview.

## 9. Shared components and copy
- Toast (bottom-centre, 4s, ink on surface, with Undo when relevant). Modals: `--r-lg`, `Esc` closes, focus trapped, initial focus on the safe button.
- Tooltips: appear after 400ms, dark ink background, paper text, 12px.
- Shortcut sheet (`?`), heading "Keyboard shortcuts": two columns listing keys above (`/` Search · `F` Fit · `Esc` Clear · `G A C L` Switch tab · `[ ]` Toggle panels · `R X I` Triage · `U D B` Lineage direction · `K N` Timeline handles · `,` `.` Step events).
- Status words are used verbatim from DESIGN.md: Confirmed, Recheck, Reviewed, Needs fixing, Ignored, Low confidence, Proposed, Could not be matched, Mismatch, Not traced.
- Accessibility: all regions are landmarks ("Outline", "Graph", "Details", "Timeline"); graph nodes `role="button"` with aria-label "{label}, {layer}, {status word}".
- Persistence: triage and approvals are saved locally by the app; copy never implies upload.
