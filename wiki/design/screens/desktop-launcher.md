---
type: screen-spec
owner_agent: designer
status: draft
sources: ["../../sprints/S03/S03-brief.md", "../DESIGN.md", "founder decisions in chat, 2026-11-05 (name Lemmata, Tauri)"]
last_reviewed: 2026-11-05
---
# Desktop launcher and menus (S03)

Proposal for Juhyeong's approval. Tokens are from [DESIGN.md](../DESIGN.md). Behaviour is defined in [S03-brief.md](../../sprints/S03/S03-brief.md); this page only fixes layout and copy. Icon: `desktop/icons/lemmata-icon.svg` (three-band dependency graph converging on one thesis node; one Verify node, one Amber "recheck" node).

## Window
- Size 720 x 520 default (launcher only; the project window is 1440 x 900), centred, not resizable below 640 x 480. Background `--paper`. Title bar: "Lemmata".
- One centred column, max width 480 px, top padding `--s-7`. No shadows. Offline: system fonts per `--font-*` stacks.

## Layout (top to bottom)
1. Icon 64 x 64 (the SVG), `--s-3` gap, title "Lemmata" in `--font-serif` `--fs-28`, `--ink`.
2. Tagline, `--fs-14`, `--muted`: "Check that your paper's claims rest on evidence."
3. Actions row, `--s-5` above: primary button "Open Project…" (fill `--ink`, text `--paper`, `--r-md`, `--fs-14`, height 36); secondary button "Open Sample" (fill `--surface`, 1px `--border-strong`, text `--ink`). Gap `--s-3`.
4. Helper line under actions, `--fs-12`, `--muted`: "Choose one folder that holds your paper, your code, or both."
5. Disclosure link `--fs-12`, `--up`, underlined: "Choose paper and code folders separately". Expands two rows, each with a label, a read-only path in `--font-mono` and a "Choose…" button: "Paper folder (.tex)" and "Code folder (git)", plus a button "Open".
6. Section heading `--fs-12` uppercase 600 `--muted`, `--s-6` above: "RECENT PROJECTS".
7. Recent list: up to 8 rows, 40 px tall, `--surface`, 1px `--border`. Each row: project name (`--fs-13`, `--ink`), path in `--font-mono` `--fs-12` `--muted`, middle-truncated, and on the right "Opened <relative time>", e.g. "Opened 2 days ago". Hover `--sunken`; keyboard focus uses `--focus-ring`. If a folder no longer exists, row text is `--muted`, shows chip "? Not found" (`--amber-text` on `--amber-bg`) and clicking removes it after the confirm "Remove from recent projects?" [Remove] [Cancel].
8. Footer line, bottom of window, `--fs-12`, `--muted`: "Lemmata 0.1.0 · git 2.39.5" (version values filled in at run time; mono for the numbers). All status is also in words, never colour alone.

## States

### Empty (no recent projects)
Recent section is replaced by a `--sunken` well, `--fs-13`, `--muted`, centred:
- Title: "No projects yet"
- Body: "Open a folder with your paper to begin, or try the sample first."

### Git missing
Shown above the actions, full column width, `--amber-bg` with 1px `--amber` border, `--r-md`, padding `--s-4`. Text `--ink`, leading chip "↻ Setup needed" is not used (that word is Recheck); use chip "∅ git not found" (`--amber-text` on `--amber-bg`).
- Heading: "Git is not installed"
- Body: "Lemmata reads your project history with git. Install Apple's Command Line Tools to continue."
- Button: "Install Command Line Tools" (runs `xcode-select --install`).
- After clicking, the button is disabled and the line below reads "Waiting for the installer. Return here when it finishes." plus link "Check again".
- While git is missing, "Open Project…" and "Open Sample" are disabled; tooltip: "Install git first."
- Footer git part reads "git not found".

### Sidecar error
Shown in place of the git banner, `--red-bg` with 1px `--red` border, chip "✕ Could not open" (`--red` on `--red-bg`).
- Heading: "Lemmata could not open this project"
- Body is the sidecar `message` verbatim, then a friendly line by code:
  - `not_found`: "That folder no longer exists."
  - `no_project`: "No LaTeX files or git repository were found in that folder. Choose the folder that holds your paper or code."
  - `git_missing`: show the Git missing state instead.
  - `scan_failed`: "Lemmata could not read this project. Your files were not changed."
  - any other or crash: "The Lemmata engine stopped unexpectedly. Your files were not changed."
- Buttons: "Show details" (toggle, becomes "Hide details"), "Try again", "Choose another folder…".
- Details panel: `--sunken` well, `--font-mono` `--fs-12`, max height 160 px, scrollable, selectable; shows the last lines of the engine log. Small button "Copy details" (confirms "Copied").
- Focus moves to the heading when the error appears; announce with `role="alert"`.

### Opening (transient)
Buttons disabled, line `--fs-13` `--muted`: "Opening <project name>…". If longer than 10 s add: "Still working. Large projects take longer the first time."

## First-launch note (unsigned build)
Not part of the launcher; for the README or DMG window: "If macOS says Lemmata cannot be opened, right-click the app and choose Open, then Open again."

## Menu labels (from the brief)
- **Lemmata**: About Lemmata · Quit Lemmata (⌘Q)
- **File**: Open Project… (⌘O) · Open Sample · Open Recent ▸ (list of up to 8, then separator, "Clear Menu") · Reset Sample · Close Project (⌘W) · Reveal Project in Finder
- **View**: Reload (⌘R) · Actual Size (⌘0) · Zoom In (⌘+) · Zoom Out (⌘−)
- **Window**: Minimize · Zoom
- **Help**: Lemmata on GitHub
- Disabled with no project open: Close Project, Reveal Project in Finder, Reload. "Reset Sample" confirm dialog: title "Reset the sample project?", body "This replaces the sample with a fresh copy. Your own projects are not affected.", buttons "Reset Sample" and "Cancel".
- Window title with a project: "Lemmata — <project>".
- Quiet toast after auto-refresh (web UI): "Updated · <time>".

## Icon notes
- Bands top-down: thesis (large Ink node), two middle nodes (Verify green, Ink), three bottom nodes (Ink, Amber with Ink ring, Ink). 6 nodes, line width 52 of 1024, body 824 px inset 100, radius 185 per the Apple grid.
- The Amber node's Ink ring keeps it visible on Paper (amber alone is about 1.8:1). Colour identifies the nodes only; the icon carries no status meaning on its own.
- Check legibility at 16 x 16 and 32 x 32 after export; lines thin out at 16 px, nodes should still read as a triangle of dots. Open decision for Juhyeong: whether to drop the middle band at small sizes.
