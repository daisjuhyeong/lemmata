# Lemmata on two Macs: hub on the Mac mini, app and paper on the MacBook

```
MacBook ──────────── Tailscale ─────────────► Mac mini  http://100.111.135.94:8765
  VS Code: paper + code, LaTeX Workshop          Lemmata hub (starts at login, keeps running)
           Lemmata extension, Claude Code ──────►  /p/<pid>/api, /mcp
  Lemmata.app ──────────────────────────────────►  pages
     │ git push                                        ▲ pulls every 5 min (never pushes)
     ▼                                                 │
  GitHub: code repo (alarm-analyzer-eval) + paper repo (www27-paper) ──┘
```
The whole picture with data flows and where secrets live is in `wiki/architecture/overview.md`. The decision to keep the paper on GitHub instead of Overleaf is in `wiki/decisions/ADR-005-no-overleaf-paper-on-github.md`.

**Address.** MagicDNS is off on this tailnet, so use the IP everywhere: **`http://100.111.135.94:8765`**. Names such as `dais-juhyeongs-mac-mini` do not resolve.

**Tailscale.** Both Macs must be signed in to the same Tailscale account. Check: the Tailscale menu-bar icon shows "Connected" on both.

**Order of the steps:**
1. Hub (§1–2)
2. App (§3–4)
3. Paper tools (§5)
4. Paper repo (§6)
5. Lemmata project (§7)
6. VS Code extension and Claude Code (§8)

## 1. Mac mini: install the hub (once)
You need `git`, `uv` (`brew install uv`) and the repo.
```
cd ~/work/lemmata && git fetch origin && git switch s06-obsidian-ui
cd app
uv run lemmata hub install      # starts now and at every login; data in ~/Lemmata
uv run lemmata hub status       # lists the URLs; the one to use is http://100.111.135.94:8765/
```
- macOS may ask whether Python may accept incoming network connections. Click **Allow**.
- Logs are in `~/Lemmata/hub/hub.log`. To stop and remove the hub: `uv run lemmata hub uninstall`.
- After a `git pull` that brings new code, reinstall: `uv run lemmata hub uninstall && uv run lemmata hub install`.
- Overleaf is switched off (`overleaf_enabled` is false by default). If you saved an Overleaf Git token in S05:
  1. Delete it: `rm -f ~/Lemmata/hub/overleaf.json`.
  2. Revoke it in Overleaf → Account Settings → Git Integration.

## 2. Mac mini: get a pairing code (each time you add a device)
```
cd ~/work/lemmata/app && uv run lemmata hub pair-code
```
This prints an 8-character code, valid for 10 minutes. You can also run it from the MacBook over SSH through Tailscale:
`ssh dais_juhyeong@100.111.135.94 'cd ~/work/lemmata/app && ~/.local/bin/uv run lemmata hub pair-code'`
(use `/opt/homebrew/bin/uv` if that is where uv lives).

## 3. MacBook: install the app
- **Download:**
  1. On GitHub, open `daisjuhyeong/lemmata` → Actions.
  2. Pick the latest green **mac-app** run on `s06-obsidian-ui` → Artifacts → **Lemmata-macos-arm64**.
  3. Open the `.dmg` and drag Lemmata to Applications.
- **First launch:** macOS blocks the app once because Apple has not signed it yet. Go to System Settings → Privacy & Security → **Open Anyway**. Or run `xattr -dr com.apple.quarantine /Applications/Lemmata.app`.
- **Or build it on the MacBook:**
  1. Install Rust once: `curl https://sh.rustup.rs -sSf | sh`.
  2. Run `git clone -b s06-obsidian-ui https://github.com/daisjuhyeong/lemmata.git ~/lemmata && ~/lemmata/desktop/build-mac.sh`. The first build takes about 10 minutes.

## 4. MacBook: connect, pair, sign in
1. Open Lemmata → **Connect to Lemmata server**. Replace the prefilled name with **`http://100.111.135.94:8765`** → Connect.
2. Enter the pairing code from step 2.
3. **Sign in with GitHub** → a code appears → **Open GitHub** → paste the code → Authorize "Lemmata (Juhyeong)". The first GitHub account that signs in becomes the hub's owner. No other account can sign in later. This one sign-in covers both the code repo and the paper repo.

## 5. MacBook: write and compile the paper in VS Code (once)
The paper is written and compiled on the MacBook. The hub only reads the sources from GitHub and never runs TeX.

**Install TeX.** Pick one:
- **MacTeX without the GUI apps** (recommended: everything included, several GB):
  ```
  brew install --cask mactex-no-gui
  ```
- **BasicTeX** (small, but you add packages yourself):
  ```
  brew install --cask basictex
  # open a NEW terminal, then:
  sudo tlmgr update --self
  sudo tlmgr install latexmk acmart
  ```
  With BasicTeX, a build may stop with ``File `something.sty' not found``. Find the package that contains the file with `tlmgr search --global --file something.sty`, then run `sudo tlmgr install <package>`. Repeat until the paper builds. `acmart` needs several of these.

Then open a **new** terminal and check: `which latexmk pdflatex` should print paths under `/Library/TeX/texbin/`.

**Install LaTeX Workshop.** In VS Code: Extensions → search "LaTeX Workshop" (James Yu) → Install. Or run `code --install-extension James-Yu.latex-workshop`. After installing TeX, **quit VS Code completely (⌘Q) and reopen it** so it picks up the new PATH.

**Build on save and SyncTeX.** Open the user settings JSON (⌘⇧P → "Preferences: Open User Settings (JSON)") and add:
```json
"latex-workshop.latex.autoBuild.run": "onSave",
"latex-workshop.view.pdf.viewer": "tab",
"latex-workshop.view.pdf.internal.synctex.keybinding": "double-click"
```
- **Build:** saving a `.tex` file builds the paper with `latexmk`, LaTeX Workshop's default recipe. To build by hand: ⌘⌥B, or the TeX icon in the activity bar → Build LaTeX project.
- **View:** ⌘⌥V, or the preview icon at the top right of a `.tex` file. The PDF opens in a VS Code tab and refreshes after each build.
- **Source to PDF:** ⌘⌥J ("SyncTeX from cursor") jumps to the place in the PDF.
- **PDF to source:** double-click a spot in the PDF to jump to the source line. This works because of the setting above; the default is Ctrl-click.
- **Root file:** LaTeX Workshop finds the main file by its `\documentclass`. In section files you can add `%!TEX root = ../main.tex` as the first line.
- **Errors:** the Problems panel lists them. The full log is under View → Output → "LaTeX Compiler".

**Safety.** `latexmk` runs any `.latexmkrc` file in the paper folder, and that file can contain arbitrary code. When VS Code asks whether you trust a folder's authors, say yes only for your own repos. Look at changes to `.latexmkrc` in what co-authors push.

## 6. Move the paper out of Overleaf (once)
1. **In Overleaf, clean up first.** Use the Review panel to accept or reject every tracked change. Copy out any comment you still need: comments and tracked changes do not survive the move. Your Overleaf history stays in Overleaf. Leave the Overleaf project untouched afterwards and do not edit in two places.
2. **Download.** Overleaf → Menu (top left) → Download → **Source**. This gives a `.zip` and works on the free plan.
3. **Make a git repo** (replace the zip name with yours):
   ```
   mkdir -p ~/work/www27-paper && cd ~/work/www27-paper
   unzip ~/Downloads/<your-overleaf-project>.zip
   ls          # main.tex etc. should be here; if everything sits in one subfolder, move its contents up
   git init -b main
   ```
4. **Add a LaTeX `.gitignore`.** It covers build outputs only. Do **not** ignore `*.pdf`, because figures are often PDFs. Ignore only the compiled paper, and change `main` if your root file has another name.
   ```
   cat > .gitignore <<'EOF'
   # LaTeX build outputs
   *.aux
   *.bbl
   *.bcf
   *.blg
   *.fdb_latexmk
   *.fls
   *.lof
   *.log
   *.lot
   *.nav
   *.out
   *.run.xml
   *.snm
   *.synctex
   *.synctex.gz
   *.synctex(busy)
   *.synctex.gz(busy)
   *.toc
   *.vrb
   *.xdv
   *.dvi
   _minted*/
   # the compiled paper (figures stay tracked)
   /main.pdf
   # macOS
   .DS_Store
   EOF
   ```
5. **Build once to check, then commit:**
   ```
   latexmk -pdf main.tex        # or open the folder in VS Code and save main.tex
   git add -A && git status     # no .aux/.log files and no main.pdf in the list
   git commit -m "Import paper from Overleaf"
   ```
6. **Create the private GitHub repo and push** (`gh` is GitHub's CLI: `brew install gh`):
   ```
   gh auth status || gh auth login
   gh repo create daisjuhyeong/www27-paper --private --source . --push
   ```
   GitHub refuses single files over 100 MB. If a push fails on that, shrink or drop the file and commit again.
7. **From now on:** edit in VS Code → save (the PDF rebuilds) → commit → push. Lemmata sees a change once it is **pushed**.

**Paper as a folder of the code repo instead.** Copy the unzipped files into `alarm-analyzer-eval/paper/` with the same `.gitignore` (put it in `paper/`), then commit and push in the code repo. Skip `gh repo create`. Use this only if the code repo will never become public and no co-author should get the paper without the code: making the code public would publish the draft and its history.

**Co-authors still on Overleaf.** Give them access to the paper repo on GitHub, or have them send you their Overleaf Download Source zip. You then copy their changes in and commit them yourself, so Lemmata sees one commit per hand-off.

## 7. Connect the paper repo in Lemmata
In Lemmata (app, or `http://100.111.135.94:8765/` in a browser on the MacBook):
1. **New project**.
2. **Code:** search `alarm-analyzer-eval` → pick it.
3. **Paper:**
   - **GitHub repo** → search `www27-paper` → pick it. The branch is optional; the default branch is used.
   - Or **Folder in the code repo** → `paper`.
   - The zip upload is only a fallback, for a paper that still lives in someone's Overleaf.
4. **Create project.** The hub clones both repos. From then on it pulls them every 5 minutes, or when you press **Sync now**.

The exact button labels follow the S06 design (`wiki/design/screens/s06-obsidian-redesign.md`).

**Existing project with a zip paper.** Open it → paper source → **Connect a GitHub repo** → pick `www27-paper` (or a folder). The old paper is kept on the mini as `projects/<pid>/paper.prev-<time>/`.

**References.** They are checked offline by default. To look them up online, turn on "Check references online" for the project. This sends only bibliography titles and DOIs to OpenAlex and Crossref.

## 8. VS Code: the Lemmata extension and Claude Code
**Open both repos in one window:** File → Open Folder `~/work/alarm-analyzer-eval`, then File → Add Folder to Workspace `~/work/www27-paper`. Save the workspace (File → Save Workspace As…) **outside** both repos. The extension recognises each folder by its GitHub remote.

**Create two device tokens** on the Mac mini (or over SSH as in §2). `--host` makes the printed command use the IP:
```
cd ~/work/lemmata/app
uv run lemmata hub token --device "VS Code extension" --host 100.111.135.94
uv run lemmata hub token --device "Claude Code" --host 100.111.135.94
```
Each token is shown once.

**Extension:**
1. Install it: `code --install-extension ~/lemmata/vscode/lemmata-0.2.0.vsix`, or Extensions → `...` → Install from VSIX….
2. ⌘⇧P → **Lemmata: Connect to Server**.
3. Server: `http://100.111.135.94:8765` (the default).
4. Token: paste the first token.

The status bar then shows e.g. "Lemmata: 5 to recheck". More detail: `vscode/README.md`.

**Claude Code:** run the line printed for the second token. It looks like this:
```
claude mcp add --scope user --transport http lemmata http://100.111.135.94:8765/mcp --header "Authorization: Bearer <token>"
```
Always use `--scope user`. Never use `--scope project`: it writes the token into the repo's `.mcp.json`, which then gets pushed. The token gives full access to the hub. Revoke tokens with `uv run lemmata hub devices` and `uv run lemmata hub revoke <device_id>`.

Then, in Claude Code with both folders open, try:
1. "Use lemmata: list my projects and tell me which one has the most things to recheck."
2. "What does lemmata say I need to recheck after my last commit? Open the affected files in this workspace."
3. "Explain with lemmata why Table 2 is flagged, show me the diff, and tell me whether the result file needs regenerating."
4. "Show lemmata's main_appendix_mismatch findings and fix the appendix value in the paper repo so it matches the main text (ask me first which one is right)."
5. "Sync the project with lemmata, then mark Table 2 as needs_fixing with the note 'rerun with lr 1e-3'."

## If something doesn't work
| Symptom | Fix |
|---|---|
| App: "Can't reach the Mac mini" | Is the address `http://100.111.135.94:8765` (not a name)? Is the Mac mini awake? Is Tailscale connected on both? Run `uv run lemmata hub status` on the mini and check `~/Lemmata/hub/hub.log`. Test from the MacBook: `curl http://100.111.135.94:8765/api/hub/status` |
| Pairing code rejected | Codes expire after 10 minutes and lock after 5 wrong tries. Make a new one |
| GitHub sign-in says the code expired | Click Retry. Codes last about 15 minutes |
| `claude mcp list` shows lemmata failing | The token was revoked or mistyped, or the URL uses a name instead of the IP. Make a new token with `hub token --host 100.111.135.94` |
| Repo list empty, or `paper_repo_not_found` | You signed in with the wrong GitHub account (sign out, sign in as daisjuhyeong), or the repo name is wrong, or the repo belongs to an organisation that has not approved "Lemmata (Juhyeong)" |
| `paper_subdir_missing` | That folder does not exist on that branch of the code repo. Check the name (`paper`, not `/paper`) and that it is pushed |
| Pushed, but Lemmata shows nothing new | Wait up to 5 minutes or press Sync now. Check that the push really happened: `git status -sb` should not say "ahead" |
| VS Code: "latexmk: command not found" | Quit VS Code with ⌘Q and reopen it. Check `ls /Library/TeX/texbin/latexmk`. With BasicTeX: `sudo tlmgr install latexmk` |
| ``File `acmart.cls' not found`` or another `.sty` | BasicTeX: `sudo tlmgr install acmart`, or the package that `tlmgr search --global --file <file>` names |
| PDF does not jump to the source | Build once after adding the settings (SyncTeX data is written by the build). Use double-click in the PDF tab, and ⌘⌥J in the source |
| Paper alarms in the Lemmata panel but no squiggles in the paper | The paper folder is not open in this workspace, or your clone is behind the hub (pull). Extension 0.1.0 matches only Overleaf paper remotes, so GitHub paper repos get squiggles only once the update from ADR-005 ships |
