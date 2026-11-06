---
type: adr
owner_agent: cto
status: proposed
sources:
  - "../sprints/S06/S06-brief.md (lead, 2026-11-06; founder decision 1 and section A are normative there)"
  - "founder decisions in chat, 2026-11-06 13:26 KST (relayed by the lead; no file in raw/ yet): no Overleaf subscription, paper on GitHub, zip fallback, Overleaf code dormant"
  - "../sprints/S05/S05-brief.md (Overleaf Git source, VS Code extension) ; ../sprints/S05/qa-S05.md"
  - "ADR-004-hub-on-mac-mini.md ; ../architecture/threat-model.md (M1, M4, M5, M11) ; ../architecture/overview.md"
  - "code on branch s06-obsidian-ui, read 2026-11-06: app/src/lemmata/hub/{config.py, projects.py, overleaf.py, guard.py, cli.py}, vscode/src/core/remotes.ts (matchProjects), desktop/src-tauri/src/server.rs (DEFAULT_URL). S06 section A is in progress (pipeline-eng); read, not tested"
  - "https://raw.githubusercontent.com/wiki/James-Yu/LaTeX-Workshop/Compile.md (fetched 2026-11-06: autoBuild.run values never/onSave/onFileChange, default onFileChange; latexmk is the default recipe; .latexmkrc use)"
  - "https://raw.githubusercontent.com/wiki/James-Yu/LaTeX-Workshop/View.md (fetched 2026-11-06: SyncTeX forward cmd+option+j on Mac; backward ctrl-click or double-click)"
  - "https://raw.githubusercontent.com/cli/cli/trunk/pkg/cmd/repo/create/create.go (fetched 2026-11-06: --private, --source, --push, --remote)"
  - "https://raw.githubusercontent.com/github/gitignore/main/TeX.gitignore (fetched 2026-11-06)"
  - "https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git-integration (not re-fetched; proxy refused)"
  - "https://www.tug.org/mactex/ ; https://www.tug.org/texlive/doc/tlmgr.html ; https://ctan.org/pkg/acmart ; https://ctan.org/pkg/latexdiff (not re-fetched; proxy refused)"
last_reviewed: 2026-11-06
---
# ADR-005: No Overleaf for now. The paper lives on GitHub and is compiled locally

Status: **proposed** (Juhyeong approves). Supersedes: **the Overleaf parts of the [S05 brief](../sprints/S05/S05-brief.md)** (section A, the Overleaf card and default in section B, and the `git.overleaf.com` remote matching in section C). It also amends [ADR-004](ADR-004-hub-on-mac-mini.md) Context ("inputs are a GitHub repo plus an uploaded Overleaf zip"). The contract is fixed by the lead in the [S06 brief](../sprints/S06/S06-brief.md) §A. This ADR records it and gives the reasons. Changes I need are marked **(must-fix)** or **(proposal)**. Both need the lead's OK and a note to QA. System picture after S06: [architecture overview](../architecture/overview.md).

Note on sources: Overleaf, TUG and CTAN pages could not be fetched this session (the proxy refused them). Claims that rest only on them are marked *verify*. The LaTeX Workshop, `gh` and gitignore claims come from the pages fetched on 2026-11-06 (sources list).

## Context
- **Founder decision (2026-11-06, S06 brief §1):** Juhyeong will not pay for Overleaf premium. S05 was built on the assumption that he had it ([S05 brief](../sprints/S05/S05-brief.md) §1). Overleaf's Git integration, the only way the hub can pull a paper from Overleaf without a manual step, is a premium feature. The S05 brief cites the Overleaf Git page for this; I could not re-fetch it (*verify*).
- **What Lemmata needs from the paper source.** It needs a **versioned** tree: every paper change becomes a commit with a time and a message, so alarms can say what changed and when. It also needs a tree that the **hub can pull on its own**: the 5-minute sync, with no human step. And every location should be a **line in a local file** that the VS Code extension can underline. A git repo the hub can clone meets all three.
- **What exists.** The hub already clones GitHub repos with the owner's token and the hardening from S04 (threat model M4, M5), and syncs them every 5 minutes. The `paper/` folder is already a git repo (`projects.py`; zip uploads commit into it). The S05 Overleaf path (`hub/overleaf.py`, token in `~/Lemmata/hub/overleaf.json`) passed QA after fixes ([qa-S05](../sprints/S05/qa-S05.md)). Section A is **in progress** on `s06-obsidian-ui`. A read on 2026-11-06 found:
  - `overleaf_enabled: False` in `config.py`;
  - `create(... paper_repo, paper_branch, paper_subdir)`, `set_paper_source(kind="github")`, `valid_subdir` and `_sync_github_paper` in `projects.py`;
  - `feature_disabled` 404s in `routes.py`.

  This ADR reviews that work against the brief. It is not a QA pass.
- **Deadline.** 2nd presentation (MVP demo). The paper source has to be boring and reliable. The UI redesign (S06 §B) is where the sprint risk sits.

## Options
| Option | For | Against |
|---|---|---|
| **O1. Overleaf Git integration** (S05, premium) | Already built and QA-passed. Co-authors keep the Overleaf editor, comments and track changes. Overleaf compiles, so no TeX install is needed | **Paid subscription: the founder said no.** Overleaf rate-limits git, so the hub fetches at most every 2 minutes. A second credential (Overleaf token) sits on the hub. The VS Code extension needs a separate Overleaf clone on the MacBook. The GitHub-sync variant is premium too (*verify*) |
| **O2. Zip uploads** (S04 flow, free Overleaf) | Free. Co-authors stay in Overleaf. Already built | A manual step each time (Overleaf: Download Source, then upload). People forget it, so alarms lag behind the real paper. One version per upload instead of per edit. No commit messages ("You changed…" has nothing to say). No local clone, so the VS Code extension has no paper folder to underline |
| **O3. Paper in its own GitHub repo** (e.g. private `daisjuhyeong/www27-paper`) | Free. Same pull path, token and hardening as the code. Per-edit history with messages. Can be shared with paper co-authors without exposing the code (and the reverse). The code repo can go public at camera-ready without dragging the draft history and reviewer replies along. The extension maps the paper by its GitHub remote | A TeX install on the MacBook (MacTeX about 4-5 GB, or BasicTeX plus packages; *verify* sizes). Co-authors need GitHub. No Overleaf-style track changes or inline comments. Two repos to clone and push |
| **O4. Paper as a subfolder of the code repo** (`paper/` in `alarm-analyzer-eval`) | Free. One repo, one clone, one push. One commit can change a result file and the table that quotes it together, and Lemmata sees them as one change | Co-authors of the paper get the code, and the reverse. Making the code public publishes the draft and its whole history (or you have to rewrite history). Commits that touch both parts show up on both timelines. The hub clones the code repo twice (brief: always a separate paper clone) |

## Decision
1. **The paper source is a GitHub repo (O3 or O4), pulled by the hub exactly like the code.** Kinds, as in the S06 brief §A: `github` (new, default), `zip` (fallback), `overleaf` (hidden). `{"kind":"github","repo":"owner/name","branch"?,"subdir"?}`. The paper has its own hardened clone under `~/Lemmata/projects/<pid>/paper/`, uses the same GitHub token, follows the same 5-minute sync and `POST /sync`, and is never pushed to. With `subdir`, the engine's paper root is that subfolder and the paper history is filtered to it.
2. **Recommended default: its own private repo (O3).** Use O4 only for a paper whose code repo will never be public and that has no paper-only co-authors. The New-project screen should offer O3 first (proposal for the designer).
3. **Writing and compiling happen on the MacBook only:** VS Code + LaTeX Workshop + MacTeX (`mactex-no-gui`) or BasicTeX with `latexmk` and `acmart`. Build on save, SyncTeX in the built-in PDF tab. **The hub never runs TeX.** It only reads the sources. That keeps "never executes repo content" true on the mini (`projects.py` module docstring).
4. **Zip upload stays as the fallback** (`kind: zip`), for a paper that still lives in someone's Overleaf.
5. **Overleaf code stays, dormant.** It is behind `overleaf_enabled` in the hub config, default `false`. When the flag is off, every Overleaf route returns 404 `feature_disabled`, `GET /api/hub/status` leaves out `overleaf_configured`, and no screen mentions Overleaf (brief §A, §B). Additions I need:
   - **(must-fix, already in the code)** When the flag is off, the sync loop **never contacts `git.overleaf.com`**. That includes projects whose `paper_source.kind` is still `overleaf` from S05. Such a project keeps its last paper; `_sync_paper` returns `skipped: "feature_disabled"`. QA verifies this with the fake Overleaf: zero requests. The UI offers "Connect a GitHub repo" or "Upload a zip" for such a project (designer).
   - **(must-fix)** The flag can be set only on the mini, by editing `~/Lemmata/hub/config.json` and restarting the hub. It can never be set through the HTTP API (same rule as `github_api`/`github_web`, threat model M11). The code has no HTTP route that writes config, which is correct. **(proposal)** Add `lemmata hub config --overleaf on|off` so nobody hand-edits JSON.
   - **(proposal)** Turning the flag off does not delete `overleaf.json`. Setup step: remove it, and revoke the token at Overleaf, if one was ever created (see Consequences, secrets).
   - **(proposal)** CI keeps running the Overleaf tests with the flag on, so the dormant code does not rot.
6. **Validation for the new fields (must-fix, extends threat model M11):**
   - `paper_repo` uses the same regex as `code_repo`.
   - `paper_branch` uses the same check as `branch`.
   - `paper_subdir`:
     - is relative, with no `..`, `.`, `.git` alias or empty component;
     - does not start with `/`, `-` or `~`;
     - is at most 200 characters.
   - After the clone, the subfolder's resolved path must be a folder strictly inside the clone. Otherwise the hub answers `400 paper_subdir_missing` and leaves no project behind.
   - The engine's root confinement (M1) uses the subfolder as its root.
   - The allowed host stays exactly the configured `github_web` over https.

   The code read on 2026-11-06 (`valid_subdir`, `_clone_paper` in `projects.py`) matches this. QA confirms that a symlinked `paper` folder inside the repo is refused (with `core.symlinks=false` it arrives as a file, so `is_dir` fails).

## Consequences
### For Juhyeong (solo, now)
- **One-time setup on the MacBook:**
  - Install TeX and LaTeX Workshop.
  - Move the paper out of Overleaf once: Download Source → unzip → `git init` → `gh repo create … --private --source . --push`.
  - Connect the repo in Lemmata.
  - Steps: [SETUP-two-macs §6-8](../../docs/SETUP-two-macs.md).
- **Daily loop:** edit → save (PDF rebuilds) → commit → push. Alarms appear after the next hub sync (≤ 5 min, or Sync now). An unpushed edit is invisible to the hub. That is intended: Lemmata tracks what is committed.
- **Better signal than zip:** every paper commit has a message and a time. The S06 "You changed …" cards can then name paper edits as precisely as code edits.
- **Claude Code can work on the paper directly.** It runs in the same VS Code window as the `.tex` files and asks Lemmata over MCP what to recheck (ADR-004 Decision 7 is unchanged).

### Co-authors who live in Overleaf
- **Best case:** they accept GitHub, edit in VS Code, or in GitHub's web editor for small fixes, and push to the paper repo. Add them as collaborators on the **paper** repo only (another reason for O3).
- **If a co-author keeps working in Overleaf**, there are three routes:
  - (a) They send changes, or a Download Source zip, and Juhyeong commits them. Lemmata sees one commit per hand-off.
  - (b) The project temporarily switches to `kind: zip`. This loses the GitHub link until it is switched back, so (a) is preferred.
  - (c) If a co-author's own account has Overleaf premium and owns the Overleaf project, turn `overleaf_enabled` on and use the S05 path. Whether a non-owner's Git token works on a premium owner's project is *verify*.
- **Never edit both at once.** Two live copies (Overleaf and GitHub) diverge, and there is no automatic merge back into Overleaf without premium GitHub sync. Pick one place where the paper is written, per paper.
- **Co-authors' repos run code on the MacBook.** `latexmk` reads a `.latexmkrc` in the project folder, and that file is Perl. The LaTeX Workshop wiki also documents adding `-shell-escape` there. With build on save, a co-author's `.latexmkrc` runs on Juhyeong's MacBook. So: review changes to `.latexmkrc` and to LaTeX Workshop settings in `.vscode/` in every pull, and do not turn on shell escape for a repo you do not control. The hub is not affected (Decision 3).
- **Org-owned paper repos:** if the paper repo belongs to a GitHub organisation that restricts OAuth Apps, the hub's sign-in token cannot see it until the org approves "Lemmata (Juhyeong)" (*verify*). The hub then answers `404 paper_repo_not_found`.

### Track changes, comments and history
- **Overleaf track changes and comments do not move to git.** Before Download Source, accept or reject every tracked change and copy out any open comment you still need. How the zip treats pending changes is not something to rely on (*verify*).
- **Replacements:**
  - `git diff --word-diff` and GitHub pull-request reviews for "what did my co-author change".
  - `latexdiff` (in MacTeX; BasicTeX: `sudo tlmgr install latexdiff`) for a marked-up PDF.
  - `\todo{}` (todonotes) or `% TODO` lines for inline notes.
- **Overleaf's history stays in Overleaf.** The GitHub repo starts at the import commit, and Lemmata's paper timeline starts there too. Labelled versions you may want later can be downloaded from Overleaf's History before leaving (*verify*). Earlier paper versions already on the hub, from zip uploads, are kept as `paper.prev-<time>/` when the source is switched (brief §A).
- The Overleaf project itself is left as is (read-only by convention). Do not delete it until the GitHub repo has been used for a while.

### Moving the paper out of Overleaf (once)
1. In Overleaf, resolve tracked changes and comments.
2. Menu → Download → Source (works on the free plan).
3. Unzip into `~/work/www27-paper`, `git init -b main`.
4. Add a LaTeX `.gitignore`: build outputs only. Ignore `/main.pdf`, never `*.pdf`, because figures are often PDF.
5. Compile once locally to confirm it builds, then the first commit.
6. `gh repo create daisjuhyeong/www27-paper --private --source . --push`.
7. In Lemmata: New project (code repo + paper repo), or switch an existing project's paper source to GitHub.

Exact commands: [SETUP-two-macs §7](../../docs/SETUP-two-macs.md).

### Secrets
- **No new secret.**
  - The hub's GitHub token (`~/Lemmata/hub/github.json`, 0600, scope `repo`) reads the private paper repo too. This widens what the `repo`-scope token is used for, not what it can do. ADR-004 F2 (GitHub App, `Contents: read`) is still required before launch and must cover both repos.
  - Pushing from the MacBook uses Juhyeong's own git/`gh` credentials on the MacBook, never the hub's token.
- **One secret to remove:** if an Overleaf Git token was ever saved, delete `~/Lemmata/hub/overleaf.json` on the mini and revoke the token in Overleaf → Account Settings → Git Integration.

### Engineering
- **VS Code extension gap (must-fix, not in the S06 brief).** `matchProjects` (`vscode/src/core/remotes.ts`) binds a folder as **paper** only by a `git.overleaf.com` remote. After S06 it must:
  - bind a GitHub remote equal to `paper_source.repo` as `paper`, and
  - for `subdir`, map hub paths `paper/<rel>` onto `<code folder>/<subdir>/<rel>`.

  The Overleaf branch is used only when `paper_source.kind == "overleaf"`. Until this lands, paper alarms appear in the panel but not as squiggles. Needs a task card for web-eng and a QA check.
- **App default URL (proposal).** `desktop/src-tauri/src/server.rs` still defaults to `http://dais-juhyeongs-mac-mini:8765`. MagicDNS is off, so that name does not resolve. Default it to `http://100.111.135.94:8765`, as the extension already does.
- **Subfolder dedupe (proposal).** With O4, one commit can appear both as a code change and as a paper change. The S06 "Changes" inbox should show it once ("You changed the learning rate and Table 2", commit 2836100).
- **Cost.** One more clone and fetch per project every 5 minutes (two with O4, from the same repo). This is small next to the scan. Dormant Overleaf code is about 75 lines in `overleaf.py` plus branches in `projects.py`/`routes.py`, kept tested.

### Scope and schedule
- **Cut order if S06 runs late** (first cut first):
  1. the `subdir` variant (O4),
  2. switching an existing project's source (`paper-source`); create a new project instead,
  3. the zip fallback in the new UI (it stays in the API).
- The own-repo path (O3) and the hidden Overleaf flag are the minimum for the demo.

## Follow-ups
- F1. GitHub App (ADR-004 F2) with read-only access to the code repo **and** the paper repo, before anyone else signs in.
- F2. Webhook or `git ls-remote` polling to cut the ≤ 5 min delay. Needs inbound reachability or more API calls. Not before launch.
- F3. If Overleaf premium is ever bought (spending → Juhyeong), turn the flag on. No code change.

## Open questions for Juhyeong
1. Approve ADR-005.
2. Paper repo name and owner: `daisjuhyeong/www27-paper`, private? Any co-author who must stay on Overleaf?
3. MacTeX (`mactex-no-gui`, large, everything included) or BasicTeX (small, packages added by hand)? I recommend MacTeX on the MacBook if the disk allows, because `acmart` pulls in many packages.
4. Was an Overleaf Git token ever saved on the hub? If yes, remove it (Consequences, secrets).

## Approved by
(pending — Juhyeong, date)
