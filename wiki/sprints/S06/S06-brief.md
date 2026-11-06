---
type: task-card
owner_agent: lead
status: draft
sources:
  - "founder decisions in chat, 2026-11-06 13:26 KST"
  - "../S05/S05-brief.md"
  - "https://obsidian.md (UI baseline named by the founder)"
last_reviewed: 2026-11-06
---
# S06 brief: no Overleaf for now, and an Obsidian-style UI anyone can read

## Founder decisions (2026-11-06)
1. **No Overleaf subscription.** Remove Overleaf from the current architecture and UI. The paper lives in a **GitHub repo** (written and compiled locally in VS Code with LaTeX Workshop + a TeX install) and Lemmata pulls it exactly like the code. Zip upload stays as a fallback. The S05 Overleaf code stays in the repo but is switched off (config flag, default off) and hidden from every screen.
2. **Redesign the web UI** (served by the hub at `/` and `/p/<pid>/`, also inside the Mac app) so that someone **without background knowledge** understands it.
   - Purpose: an assistant that **keeps track of changes during the research**. The user does *not* watch it all the time; they look **when needed**. So the first screen answers "what changed since I last looked, and what does it affect?".
   - **Baseline: Obsidian** (obsidian.md): left sidebar (explorer), centre with tabs (a readable page per item, and a graph view), right sidebar (links to / linked from, local graph, outline), command palette, quiet chrome. **Keep our palette** (DESIGN.md: Ink, Paper, Verify, Amber, upstream blue, downstream orange).
   - **Graph:** the main nodes must be **bigger** and readable at first glance. GitHub commits, repo result files and paper items must **not look like separate worlds**: integrate them. A paper figure/table/claim and the result file, script and runs behind it read as **one item** ("Figure 7 — domain drift") with its evidence inside; code, runs and files appear when you open or expand that item, not as separate bands by default.
   - Plain language everywhere: no internal ids (`tex:fig:…`, `ev:commit:…`), no jargon like "node", "edge", "layer", "hub mode" in default views. Commits read as "You changed the learning rate (2 days ago, commit 2836100)".

## A. Paper from a GitHub repo (pipeline-eng)
- Project paper source kinds: `github` (new, default), `zip` (fallback), `overleaf` (hidden; only when `overleaf_enabled` is true in hub config, default false — every Overleaf route returns 404 `feature_disabled` and status omits `overleaf_configured` when off).
- `github` source: `{"kind":"github","repo":"owner/name","branch"?,"subdir"?}`. The paper may be its **own repo** (e.g. `daisjuhyeong/www27-paper`) **or a folder inside the code repo** (`repo` = the code repo, `subdir` = `paper`). Always a separate hardened clone under `projects/<pid>/paper/` (same GitHub token, same hardening, same 5-minute sync and `POST /sync`); with `subdir`, the engine's paper root is that subfolder (history filtered to it).
- API: `POST /api/hub/projects` accepts `"paper_repo"`, `"paper_branch"`, `"paper_subdir"`; `POST /api/hub/projects/<pid>/paper-source {"kind":"github","repo",...}` switches (atomic, old paper kept as `paper.prev-<time>`); `paper_source` in project JSON reflects it; sync response `paper` part covers it.
- Tests with the fake GitHub (both own-repo and subdir cases), full suite green.

## B. UI redesign (designer → web-eng)
Designer writes `wiki/design/screens/s06-obsidian-redesign.md` first (layout with px, components, exact plain-language copy, states, keyboard), then web-eng implements it in `app/src/lemmata/web/` (project UI) and `app/src/lemmata/web/hub/` (projects list), keeping the existing API (data-model.md) — derive the integrated items in the browser:
- **Item model (UI only):** an *Item* is a paper-facing thing — thesis, research question, claim/section, figure, table, equation/theorem. Each Item absorbs the non-paper nodes that only feed it (result files, the scripts that produced them, their runs, config files) as its **Evidence**; shared code (used by several Items) becomes a small "Shared code" item. References are an optional toggle.
- **Left sidebar (explorer):** "Changes" (inbox: what changed since you last looked — count badge), "Paper" (outline: sections → items), "Experiments" (runs grouped by experiment), "Code" (folders), "Checks" (integrity findings, in plain words), "History" (timeline). Search on top.
- **Centre, default tab "Changes since <date>":** cards like "You changed `configs/default.yaml` (learning rate 3e-4 → 1e-3) · 2 days ago — 3 things may need a second look: Table 2, the training run, results/table2.csv (not regenerated yet)". Each card: Why? (chain + diff, plain words), Mark as checked / Needs fixing / Ignore, Open item. "Mark everything as looked at" sets the checkpoint ("Last checked: today 13:30").
- **Centre, Item page:** title ("Table 2 — main results"), status chip, one-sentence explanation of what it is ("A table in Section 4 of your paper. It is built from results/table2.csv, produced by train.py on run train_main."), Evidence list, where it appears in the paper (LaTeX snippet), history of changes that touched it, notes.
- **Centre, Graph tab (Obsidian graph view):** force-directed, **Items as large labelled circles** (size by importance = how many things rest on it), evidence collapsed inside Items; colour by status (ok / to recheck / needs fixing — colour + word/icon), filters (show code, show references, show runs), local-graph depth slider, hover highlights neighbours, click opens the Item page. Smooth with ~300 underlying nodes.
- **Right sidebar:** "Rests on" / "Supports" lists (Obsidian's outgoing/backlinks) for the open Item, a small **local graph**, and the item's recent changes.
- **Command palette** (⌘P / Ctrl+P): open item, mark checked, sync, set checkpoint. Quick switcher ⌘O.
- **First-run help:** a dismissible 3-step explainer ("Lemmata watches your paper and code. When something changes, it lists what may need a second look. You decide what's fine.").
- Keep: export, triage, link approvals (move to Checks → "Suggested links"), checkpoint, sync, paper upload (zip fallback only).
- Light theme by default using the Paper/Ink palette; a dark variant is welcome but optional.
- Screenshots of every view at 1440×900 to `app/docs/screens/s06-*.png`.

## C. Architecture docs (CTO)
`wiki/decisions/ADR-005-no-overleaf-paper-on-github.md` (proposed: supersedes the Overleaf parts of S05; paper on GitHub + local compile; zip fallback; Overleaf code dormant) and update `docs/SETUP-two-macs.md` with the paper-repo setup (MacTeX or BasicTeX + LaTeX Workshop, moving the paper out of Overleaf once, connecting it in Lemmata) and an architecture overview diagram `wiki/architecture/overview.md` of the whole system as it stands (MacBook app, VS Code + Claude Code + Lemmata extension, Mac mini hub, GitHub code and paper repos, Tailscale).
