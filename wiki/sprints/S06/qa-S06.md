---
type: qa-report
owner_agent: qa
status: draft
sources:
  - "S06-brief.md (contract)"
  - "../../design/screens/s06-obsidian-redesign.md"
  - "handoff-pipeline-eng.md, handoff-web-eng-ui.md, handoff-web-eng-hub.md (claims verified here, not taken as facts)"
  - "../../architecture/threat-model.md (T10 / M7)"
  - "../S04/qa-S04.md, ../S05/qa-S05.md (method, golden script)"
  - "code on branch s06-obsidian-ui @ 7c53a42: app/src/lemmata/web/{app.js,index.html}, web/hub/hub.js, server.py (export_html), hub/{projects,routes}.py, cli.py"
last_reviewed: 2026-11-06
---
# QA report: S06 paper on GitHub + Obsidian-style UI (branch `s06-obsidian-ui`, commit 7c53a42)

## Verdict: **ship with caveats**
- **No XSS.** Hostile repo text was injected in single-project mode (no CSP) and in hub mode (real hub CSP). No payload executed.
- **GitHub paper source is hardened.** Every bad subdir, repo and branch value is refused, and the token stays out of argv and the clone config.
- **Overleaf is off by default.** `hub config --overleaf on` turns it back on.
- **Tests and golden set are green.**
- **Main caveats:**
  - D1: an exported report goes blank on one specific string. This is old code, not new in S06.
  - D2: the "things to look at" counts disagree across screens. That hurts the plain-language goal.
- Merging to main still needs Juhyeong's approval.

## 1. Tests
| Suite | Result |
|---|---|
| `PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_*.py'` | **126 OK** (29.9 s) |
| `cd vscode && npm ci && npm run compile` | OK (npm audit: dev-only advisories, as in S05) |
| `npm test` | **27/27** |
| `npm run test:integration` | **9/9** |
| Golden set via API (`/tmp/qa-s04/scripts/golden.py` on a fresh `demo --dir /tmp/qa6`) | **PASS**: all 10 findings at the right file:line, 2 proposed links, 2 alarm groups (config -> run -> table2.csv -> Table 2; appendix lr) |

## 2. Security of the rewritten UI (threat model T10/M7)
**Code review.**
- `app.js` (2,207 lines) and `hub/hub.js` have no `innerHTML`, `insertAdjacentHTML`, `outerHTML`, `document.write`, `DOMParser`, `srcdoc`, `eval` or `new Function`.
- All text goes through `h()`, which uses `textContent` or text nodes.
- Attribute names are static. The only `href` values are constants or `apiUrl('/api/export')`, plus GitHub's `verification_uri` in hub.js (unchanged since S04).
- The graph is drawn on a canvas, so labels go through `fillText`. Tooltips are built with `h()`.

**Attack.** Driver: `/tmp/qa-s06/scripts/xss.py`.
- I planted `<img src=x onerror=alert(1)>`, `javascript:` links and `<svg onload>` in:
  - code: a commit subject, the author name, a file name, a YAML comment
  - paper: a commit subject, a figure file name, `\caption{…\href{javascript:…}…\url{javascript:…}}`, `\section{Results <img…>}`
  - hub: the repo descriptions
- The driver walked every view:
  - Changes, with every Why? opened
  - every explorer row and its item or file page
  - the Graph, with a 40 px hover sweep and a double-click
  - the Ctrl+P and Ctrl+O lists, searching for the payload and opening the result
  - Checks and History
- After each step it scanned the DOM for `on*` attributes, `javascript:`/`data:` URLs, and any new `img`/`svg`/`script`/`iframe`.

| Mode | Dialogs | Injected DOM | CSP violations | Notes |
|---|---|---|---|---|
| Single project (`lemmata open`, 127.0.0.1:8782, **no CSP header**) | 0 | 0 | n/a | Payload shown as literal text (e.g. "Figure 2 · Validation <img src=x onerror=alert(1)> \href{javascript:…") |
| Hub `/p/<pid>/` (own paper repo, and paper folder in the code repo), real `routes.CSP` | 0 | 0 | 0 | One 401 console error during the crawl; I did not find its source (D9) |
| Hub `/` and New project (descriptions with payload) | 0 | 0 | 0 | Shown as text |
| Exported report (`/api/export`) | 0 | 0 | n/a | Blank page (D1) |

## 3. GitHub paper source and Overleaf flag
Driver: `/tmp/qa-s06/scripts/hub.py`. It runs the real `Hub` and `make_hub_server` against `FakeGitHub`. Git is wrapped so every argv is logged.

**Subdir validation (create and `paper-source`).** All of these were refused with 400 `bad_request`:
- path escapes: `../x`, `paper/../../etc`, `/etc`, `~root`, `a\b`, `C:/x`, `a//b`, `./paper`
- flag-like: `-x`, `--upload-pack=touch /tmp/qa6pwn`
- git aliases: `.git`, `paper/.git`, `.GIT`, `git~1`
- bad characters: `a\nb`, `a:b`, a zero-width space
- length and spacing: 201 chars, leading or trailing space
- wrong type: a list, an integer

Other subdir results:
- `nope` and a path that is a file (`paper/main.tex`) both give 400 `paper_subdir_missing` and leave no project behind.
- `paper/` is accepted and stored as `paper`.

**Repo and branch validation.**
- `paper_repo` is refused (400) for `../evil`, `-x/y`, `alice`, `alice/x/y`, `alice/x.git`, a URL, `a..b`, `--upload-pack=x/y` and a list.
- `paper_branch` is refused (400) for `-x`, `--upload-pack=…`, `a..b`, `a b`, `a~1`, `refs/../x`, `@{-1}`, 300 chars and `HEAD:x`.
- `paper_subdir` without `paper_repo` gives 400.
- No `/tmp/qa6pwn` file was created.

**Token.**
- 205 git argv lines were logged; the token (raw or Basic-encoded) appears in **0** of them.
- The paper clone's `.git/config` holds only the plain origin URL.
- The only file in the data dir containing the token is `hub/github.json`, which is where it is meant to be stored.
- The paper clone uses the full hardened flag set: `core.hooksPath=/dev/null`, `core.symlinks=false`, `protocol.allow=never`, `http.followRedirects=false`, and so on.

**Sync.**
- **Own-repo project:** after hostile commits in both repos, sync returned `paper {changed:true, source:"github"}`, and the alarms showed one code group and one paper group.
- **Subdir project:** after a commit to `paper/`, the alarms showed one paper group.

**Overleaf off by default.**
- GET, PUT and DELETE on `/api/hub/overleaf/token`, `paper_overleaf` on create, and `kind:"overleaf"` on `paper-source` all return 404 `{"error":"feature_disabled"}`.
- `/api/hub/status` has no `overleaf_configured`.
- After `lemmata hub config --data D --overleaf on`, status shows `overleaf_configured` again and the token PUT returns 200.
- `--overleaf off` writes `overleaf_enabled: false`.

## 4. Defects (ranked)
1. **D1 (medium, old code in `server.py export_html`, not new in S06):**
   - **Effect:** if any text in the snapshot contains `<!--<script`, the exported report opens as a blank page. Commit subjects come from any co-author, so one of them can break the report for everyone.
   - **Cause:** the snapshot JSON escapes only `</`. The parser then enters the "script data double escaped" state, so the snapshot `<script>` swallows `app.js`.
   - **Repro:** commit with the subject `x <!--<script> y`, `GET /api/export`, open the file. The page shows one script and nothing on screen. Control export: 2 scripts, UI renders.
   - **Fix:** `json.dumps(...).replace("<", "\\u003c")`.
   - There is no code execution: an attacker cannot close the script tag.
2. **D2 (medium, plain language):** the counts disagree across screens.
   - On a fresh sample:
     - Changes badge: "2"
     - Changes heading: "2 changes · 5 items may need a second look"
     - status bar: "5 things to look at"
   - For the same hub project:
     - hub list: "10 things to look at"
     - status bar inside the project: "6 things to look at"
   - Section 2 Related Work, Section 4 and Appendix B are marked "Needs a second look" because of checks (handoff deviation 3). No Changes card explains this, so a non-expert cannot find out why.
   - **Repro:** `demo --dir /tmp/qa6`, compare the badge, heading and status bar.
3. **D3 (low):** in single-project mode (`lemmata demo` / `lemmata open`) the server sends no CSP header, so if an XSS bug ever appears there is nothing to stop it. The server is loopback only and the UI is clean today. **Repro:** `curl -sI 127.0.0.1:8781/`.
4. **D4 (low, graph readability):** the main labels are readable at 1440×900 with nothing selected, but there are three problems.
   - **Labels look swapped:** "Figure 2 · Validation cur…" sits next to the circle with the table icon, and "Table 3 · Ablation of the…" next to the circle with the figure icon.
   - **Labels missing at 1280×800:** Figure 2 and Table 1 have no label.
   - **Labels hidden after a selection:** once an item is open, only it and its neighbours keep labels, so the biggest circle (Main claim) shows only "◆".
   - Long titles are cut to about 25 characters.
   - Shots: `/tmp/qa-s06/shots/walk-1440-graph-fresh.png`, `walk-1280x800-graph.png`, `walk-1440x900-graph.png`.
5. **D5 (low):** sentence-casing capitalises file paths in Why?. It reads "Configs/default.yaml changed." and "Results/table2.csv is produced by the run train_main." **Repro:** open Why? on the config card.
6. **D6 (low):** the Why? diff shows raw unified-diff headers: `--- a/appendix.tex (cp1)`, `+++ b/appendix.tex (now)`, `@@ -5,5 +5,5 @@`. `cp1` is an internal checkpoint id.
7. **D7 (low):** the grammar is wrong for a count of 1. It reads "You edited 1 files in paper (…)". **Repro:** commit one file plus a tex change to the paper.
8. **D8 (low):** the status bar uses "checked" for two different things. "Last checked: 1 Oct, 18:00" is the checkpoint, and "Checked 9 min ago" is the last scan.
9. **D9 (info):** one 401 console error appeared during the hub-mode crawl. I did not find which request caused it; a plain page load and the menu do not reproduce it.

## 5. Jargon a non-expert sees in the default views (fresh sample, 1440×900)
I scanned the visible text and all `title`, `aria-label` and `placeholder` values. "node", "edge", "layer", "tex:", "ev:" and "hub mode" do **not** appear in any of them. What remains:
- **Why? diff:** `--- a/… (cp1)`, `+++ b/… (now)`, `@@ … @@` (D6).
- **Checks:** "Concerns: smith2021ghost" uses a raw BibTeX key.
- **Commit ids** appear everywhere ("commit 0d9f787", tooltip "Click to copy the commit id"). They follow the brief's format, but nothing says what a commit is.
- **Right sidebar relation words:** "built from", "made by", "run", "settings", "contains it · refers to it". "Rests on" and "Supports" are only explained by the graph legend.
- **Local graph:** "Depth 1" and its −/+ buttons, with no explanation. On the Graph tab the same control is labelled "How many steps away to show", but only in aria-label.
- **Labels with no explanation:** "Sync now", and "Last checked" vs "Checked … ago" (D8).
- **Raw names:** "the run train_main" and the LaTeX snippets (`\label{tab:main}`, `% source: code:results/table2.csv`). These are the user's own names, so they are acceptable.
- **Golden story:** reads as the brief asks: "You changed configs/default.yaml (learning rate 3e-4 → 1e-3) · 3 Oct · commit 0d9f787 — 3 things may need a second look: Table 2, the run train_main, results/table2.csv (not regenerated yet)".

## 6. Not verified here
- The Mac app WebView (WebKit) under the CSP.
- Real GitHub, including a large paper repo.
- `npm run test:host`.
- Keyboard-only navigation of the graph.

## 7. Artefacts
- Scripts: `/tmp/qa-s06/scripts/{xss,hub,hubhome,walk,exp}.py`.
- Logs: `/tmp/qa-s06/{pytest,npmci,compile,unit,integ,hub}.out` and `gitwrap/argv.log`.
- Shots: `/tmp/qa-s06/shots/`.
- Hostile sample: `/tmp/qa6-evil`. Fresh sample: `/tmp/qa6`.
- Servers: I stopped the demo (8781), `open` (8782) and the in-process hub. I changed no code.
