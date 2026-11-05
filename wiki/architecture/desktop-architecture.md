---
type: architecture
owner_agent: cto
status: proposed
sources:
  - "../sprints/S03/S03-brief.md (lead, 2026-11-05; architecture and sidecar contract are normative there)"
  - "../decisions/ADR-003-macos-desktop-app.md ; ../decisions/ADR-002-localhost-demo.md ; demo-architecture.md ; data-model.md"
  - "code on branch s03-mac-app, read 2026-11-05: app/src/lemmata/{cli.py, server.py, watch.py, gitbin.py, engine/tree.py, web/app.js}, app/packaging/*"
  - "CTO measurement 2026-11-05 (not in raw/): one-file build of app/packaging/lemmata-server.spec, PyInstaller 6.22.3, Python 3.10.20, Linux x86_64"
  - "https://v2.tauri.app/develop/sidecar/ ; https://v2.tauri.app/security/capabilities/ ; https://v2.tauri.app/distribute/sign/macos/"
  - "https://pyinstaller.org/en/stable/operating-mode.html ; https://support.apple.com/en-us/102445 ; https://git-scm.com/docs/git#Documentation/git.txt-GITOPTIONALLOCKS"
last_reviewed: 2026-11-05
---
# Desktop architecture (S03, Lemmata.app on macOS)

This page describes how `Lemmata.app` is put together and how it behaves at runtime. The decision and its reasons are in [ADR-003](../decisions/ADR-003-macos-desktop-app.md). The **sidecar contract is normative in the [S03 brief](../sprints/S03/S03-brief.md)**, and the brief wins on any conflict with this page. JSON shapes of the API: [data-model.md](data-model.md) (unchanged by S03, except the proposal in §6 R8). Items marked **(proposal)** are not part of the contract until the lead accepts them. Items marked *verify* rest on documentation I could not re-fetch this session.

## 1. Components
```
Lemmata.app  (bundle id ai.lemmata.app, arm64, ad-hoc signed)
│
├─ Contents/MacOS/<shell binary>           Tauri v2, Rust  [web-eng: desktop/src-tauri]
│   ├─ menus, window, folder dialogs (NSOpenPanel), Reveal in Finder, recent.json
│   ├─ git check (xcode-select -p → candidate git paths; never the bare shim)
│   ├─ Sidecar supervisor: spawn · read stdout JSON · drain stderr · SIGTERM-first stop
│   └─ Window "main"
│        ├─ launcher page  (bundled, tauri://…)   ── has Tauri IPC (capability "launcher")
│        └─ http://127.0.0.1:<port>/              ── NO Tauri IPC; ordinary web page
│                    ▲ navigation pinned to these two; anything else → default browser
│                    │
├─ Contents/MacOS/lemmata-server            PyInstaller one-file  [pipeline-eng: app/packaging]
│   bootloader (pid seen by Tauri)
│     └─ forks Python child (extracts to $TMPDIR/_MEIxxxx, deleted on clean exit)
│          cli.main → gitbin.ensure_git → make_sample.build (demo) → Engine.scan
│          → server.bind(127.0.0.1, port 0) → print ready JSON → serve_forever
│          ├─ thread lemmata-watch   (watch.py: poll 3 s → rescan under App.lock)
│          ├─ thread lemmata-parent  (exit ≤ 2 s after --parent-pid disappears)
│          └─ SIGTERM handler → srv.shutdown → exit 0
└─ Contents/Resources/…                     icon (designer), launcher assets
```
Data flow inside the window is the same as in ADR-002: the UI fetches `/api/*` from the sidecar. The shell never proxies API calls; it only owns the process and the window. The only additions are the 5 s auto-refresh poll of `/api/project` (`scanned_at`) and the "Updated · hh:mm" toast.

## 2. Process lifecycle
```
 double-click
   │
 [1] shell starts ── restore window size ── show launcher
   │
 [2] git check: xcode-select -p ok? → first working of /usr/bin/git, /opt/homebrew/bin/git, /usr/local/bin/git (--version)
   │     └─ none → launcher state GIT_MISSING (button runs `xcode-select --install`; "Check again")
   ▼
 [3] launcher: Open Project… | Open Sample | Recent (≤ 8, <app_data>/recent.json) | version | git line
   │  user picks
   ▼
 [4] stop previous sidecar if any (SIGTERM → wait ≤ 3 s for Terminated → hard kill → wait)
   │
 [5] spawn lemmata-server <open|demo> … --port 0 --no-open --ready-json --parent-pid <shell pid> --watch
   │     env: PATH prefixed with the git dir found in [2]; cwd = <app_data>
   │     launcher shows "Opening <name> — scanning…" + Cancel (→ SIGTERM)
   ▼
 [6] read stdout lines; ignore non-JSON lines; drain stderr into a 200-line ring + sidecar.log
   │   ├─ {"event":"ready",url,port,project,root} → [7]
   │   ├─ {"event":"error",code,message}         → launcher error state (§4)
   │   ├─ Terminated before ready                → launcher "engine stopped (exit N)" (§4)
   │   └─ 120 s without ready                    → SIGTERM, launcher "took too long" (§4)
   ▼
 [7] update recent.json with {name, root, paper?, code?, opened_at}; title "Lemmata — <project>"
     window.navigate(url)
   ▼
 [8] steady state
       sidecar: every 3 s fingerprint (HEAD + status --porcelain + mtimes, never .lemmata/) → rescan if changed
       web UI : every 5 s GET /api/project; scanned_at changed → reload data in place, keep tab/selection, toast
       Reload ⌘R reloads the page; File menu actions go to [4]
   ▼
 [9] Close Project ⌘W → [4] then show launcher      Quit ⌘Q → [4] then exit
     Shell crash → sidecar's parent watch fires → exits ≤ 2 s → bootloader removes _MEI
```
Rules for the shell (from the brief, made precise here):
- **Exactly one sidecar at a time.** Step [4] always completes before [5]. This matters for Reset Sample: the new process deletes `<app_data>/sample`, and the old watcher must not be alive to write `.lemmata/*.json` into it.
- **Stop = SIGTERM first.** `CommandChild::kill()` is a hard kill (*verify*). A hard kill of the bootloader orphans the Python child (R1, measured). Use `libc::kill(pid, SIGTERM)`, and only fall back to `kill()` after 3 s.
- `--parent-pid` is the shell's own pid, not the bootloader's.
- **Pass the root from `ready`** (absolute, resolved) to Reveal in Finder and to `recent.json`, not the path the dialog returned. They differ for symlinks and for `~`.

## 3. Sidecar contract timeline (as implemented in `cli.py`, 2026-11-05)
| Phase | stdout | stderr | Exit |
|---|---|---|---|
| argparse error | nothing | usage text | 2 (no JSON → shell handles as "stopped before ready") |
| git missing / folder missing / no project / sample refusal | one `error` line (`git_missing`, `not_found`, `no_project`, `not_sample`) | `lemmata: <message>` | 1 |
| scan or sample build raises | one `error` line `scan_failed` | message | 1 |
| port bind fails | one `error` line `bind_failed` | message | 1 |
| listening | one `ready` line, flushed | `lemmata: serving …` | — |
| watch rescan fails | nothing | `lemmata: watch: rescan failed (keeping previous data)…` | keeps serving the last good scan |
| SIGTERM / parent gone | nothing | `lemmata: parent process … gone` (if parent) | 0 |
`not_sample` and `bind_failed` are not in the brief's list of known codes. Rust shows `message` for any unknown code (proposal: the lead adds them).

## 4. Failure modes: what the user sees
| # | Situation | Detected by | User sees | Recovery |
|---|---|---|---|---|
| F1 | First launch of a downloaded or AirDropped copy (quarantined, not notarized) | macOS Gatekeeper | System alert saying Apple cannot verify the app (wording varies by macOS version) | System Settings → Privacy & Security → **Open Anyway** (macOS 15+; Control-click → Open no longer bypasses), or `xattr -dr com.apple.quarantine /Applications/Lemmata.app`. A locally built copy is not affected |
| F2 | No Command Line Tools, no Homebrew git | shell step [2] | Launcher: "Lemmata reads your project history with git. Install Apple's Command Line Tools to continue." [Install…] [Check again] | Apple installer. Then Check again, with no app restart |
| F3 | git disappears after launch (sidecar `git_missing`) | `error` JSON | Same as F2 | Same |
| F4 | Folder was moved or deleted (recent entry) | `not_found` | "This folder is no longer at <path>." [Remove from Recent] [Locate…] | Pick it again |
| F5 | Folder has no `.tex` and no git repo | `no_project` | "This folder has no LaTeX files and no git repository. Pick the folder that holds your paper and/or code." | Pick another folder, or use the advanced paper + code picker |
| F6 | Engine bug or unreadable repo | `scan_failed` | "Lemmata could not scan this project: <message>" [Show details] (stderr tail) [Try again] | Report with details. Sample still works |
| F7 | Sidecar exits before ready without JSON (crash, wrong architecture, bad signature) | `Terminated` before ready | "Lemmata's engine stopped before it was ready (exit N)." [Show details] | Reinstall. QA build checks R9 |
| F8 | No ready within 120 s | timer | "Opening <name> is taking unusually long." [Keep waiting] [Cancel] | Cancel → SIGTERM |
| F9 | Sidecar dies while the project is open | `Terminated` after ready | Window returns to the launcher: "The engine for <name> stopped unexpectedly." [Reopen] [Show details] | Reopen (state on disk in `.lemmata/` is intact; writes are atomic) |
| F10 | macOS asks for access to Documents, Desktop, Downloads or iCloud Drive | TCC | System prompt naming Lemmata | Allow. If denied, the scan fails as F6 with "Operation not permitted". Copy should name System Settings → Privacy & Security → Files and Folders |
| F11 | Watch rescan fails (half-written file, git busy) | sidecar stderr | Nothing new. The UI keeps the last good data and the next change retries | Automatic |
| F12 | Scan running when the user clicks Rescan | HTTP 409 `busy` | Existing "a scan is already running" message | Automatic |
| F13 | Export clicked | WKWebView download | With `on_download` registered: file in `~/Downloads`, revealed. **Without it: nothing happens (R3)** | Shell must register the handler |
| F14 | Link to an outside site (Help → GitHub, a URL in evidence) | navigation handler | Opens in the default browser; the app window stays on Lemmata | — |
| F15 | Window shows a blank page or an ATS error for `http://127.0.0.1` | QA on Mac | Blank window | Add `NSAppTransportSecurity → NSAllowsLocalNetworking = true` to Info.plist (*verify*; Tauri dev URLs on localhost normally load) |
| F16 | Shell crashes or is force-quit | sidecar parent watch | Nothing (no orphan server) | Relaunch |

## 5. File locations
| What | Where | Written by |
|---|---|---|
| App | `/Applications/Lemmata.app` (the user drags it from the `.dmg`; running from the mounted `.dmg` works but is translocated and read-only) | user |
| Sidecar | `Lemmata.app/Contents/MacOS/lemmata-server` (Tauri strips the target-triple suffix of `externalBin`, *verify*) | build |
| App data | `~/Library/Application Support/ai.lemmata.app/` → `recent.json` (last 8), `sample/` (Open/Reset Sample; contains `.lemmata-sample`), window state | shell, sidecar (`sample/` only) |
| Logs | `~/Library/Logs/ai.lemmata.app/sidecar.log` (proposal: stderr of the current sidecar, truncated at 1 MB on each spawn) | shell |
| Web view data | WebKit per-app store under `~/Library/` (cookies, `localStorage`). Per origin, and the origin changes with the port (R8) | WebKit |
| Project hub | `<project>/.lemmata/` (unchanged from ADR-002: manifest, derived JSON, triage, checkpoints, cache; `.gitignore` = `*`) | sidecar |
| Runtime temp | `$TMPDIR/_MEIxxxxxx` (under `/var/folders/…/T/`), about 9 MB+ per run, removed on clean exit | sidecar bootloader |
| Source paths in the repo | `desktop/src-tauri/` (Rust, `tauri.conf.json`, capabilities), `desktop/src-tauri/binaries/lemmata-server-aarch64-apple-darwin`, `desktop/launcher/`, `desktop/icons/lemmata-icon.svg`, `desktop/build-mac.sh`; `app/packaging/{lemmata-server.spec, lemmata_server.py, build_sidecar.sh}` | web-eng, pipeline-eng, designer |

## 6. Risks in the contract on macOS (detail for engineers and QA)
**R1 — two-process sidecar and hard kill (high; measured).** With one-file mode the bootloader forks a Python child. Measured: child PPID = bootloader. After `kill -9 <bootloader>`, the child had PPID 1, still answered `GET /api/health`, and exited only when the `--parent-pid` process ended. Its `_MEI*` folder stayed behind. After `kill -TERM <bootloader>`, the child was gone in 0.54 s and no `_MEI*` was left.
*Mitigation.* Shell: SIGTERM-first stop (§2). Sidecar **(proposal)**: in the parent-watch loop, also exit when `os.getppid()` differs from its value at startup. On macOS, `select.kqueue` with `KQ_FILTER_PROC`/`KQ_NOTE_EXIT` on the parent pid can replace the 0.5 s poll. Start the parent watch at the top of `main()`, before the first scan (today `_watch_parent` starts in `_serve`, after `Engine.scan()`). *Test (QA, Linux and Mac):* spawn with `--parent-pid` of a `sleep` process. `kill -9` the bootloader → the child must be gone within 2 s, and the port must refuse connections.

**R2 — git shim (medium).** On a Mac without the Command Line Tools, running `/usr/bin/git` pops up Apple's own install dialog. GUI apps get a minimal PATH. `gitbin.py` already handles this for the sidecar (`xcode-select -p` before trusting `/usr/bin/git`). The shell must use the same order and must not call a bare `git --version` at launch. The shell passes the found directory first on the sidecar's `PATH`.

**R3 — downloads in WKWebView (high for the demo; Export is the fallback).** Both export buttons are `<a href="/api/export" download>` (`app.js`). Register `on_download` on the window builder, set the destination to `~/Downloads/<file>` (avoid overwriting by adding ` (1)`), and reveal the file when it finishes. *Test:* click "Export HTML report" in the app, open the file offline.

**R4 — ready comes after the scan.** `cli.py` scans before `bind`, so time to ready = extraction + imports + full scan. The 120 s timeout and the "scanning…" state cover this. Do **not** move `ready` earlier: the window would show an empty UI. That would be a contract change.

**R5 — pipes must be drained.** If the shell stops reading the sidecar's output stream after `ready`, a full stderr pipe blocks the Python child on a log write, possibly while it holds `App.lock`, and the UI hangs. Drain both streams until `Terminated`. Parse stdout line by line and skip lines that are not JSON objects with `event`.

**R6 — exit without JSON.** argparse errors (exit 2), bootloader failures (bad signature, wrong architecture: "Bad CPU type in executable") and signals produce no JSON line. Treat `Terminated` before `ready` as F7.

**R7 — TCC folder prompts (expected; verify on the Mac).** Reading a project in a protected folder triggers a prompt attributed to the app. Because ad-hoc signatures change with each build, macOS may ask again after a rebuild. For the presentation, keep demo projects in `~/Projects/` and open each one once after the final install.

**R8 — browser-era copy inside the UI (low; visible in the demo).** The in-page picker tells the user to run `lemmata open` in a terminal, and its recent list lives in `localStorage` (`lemmata.recent`), which is per origin. The app's port changes every launch, so the list is always empty. **Proposal:** add `"embedded": true` to `GET /api/health` when `--ready-json` is set (additive; CTO edits data-model.md, note to QA). With it, the UI hides the recent card and says "Use File → Open Project… (⌘O)".

**R9 — architecture and signature of the bundled sidecar.** `build-mac.sh` must fail when `lipo -archs <sidecar>` ≠ `arm64`. After `cargo tauri build`, it runs `codesign --verify --strict --verbose=2 Lemmata.app` and smoke-tests the **bundled** copy: `Lemmata.app/Contents/MacOS/lemmata-server --version`, then `… demo --dir "$(mktemp -d)/s p a c e" --port 0 --no-open --ready-json` with a 30 s limit, expecting a `ready` line. The path with spaces mimics `Application Support`. `spctl --assess` is expected to **reject** (not notarized). Log its output; it is not a failure.

**R10 — Unicode normalisation of paths (medium for Korean file names).** Git on macOS reports precomposed (NFC) names (`core.precomposeUnicode`, default on macOS). A plain `os.walk` of a non-git folder returns names as stored, which can be decomposed (NFD) after unzipping or Finder renames. LaTeX sources typed in an editor are usually NFC. Nothing in `engine/` normalises today. **Proposal:** NFC-normalise repo-relative paths in `Tree.list_files`, `has`, `read` and `watch.py`, keeping a map to on-disk names for reads. *Test:* a non-git paper folder with an NFD-named `그림.png` included as `\includegraphics{그림}`.

**R11 — two app instances (low).** Two instances (for example, one from the DMG and one from Applications) would run two sidecars on the same project and race on `triage.json`. Use Tauri's single-instance plugin, or refuse when a live sidecar already holds `<project>/.lemmata/lock` (ADR-003 F7).

## 7. Security model (delta from demo-architecture §5)
- Unchanged: bind 127.0.0.1; Host and Origin checks; JSON content type on POST; 64 KB body cap; static files confined to `web/`; hidden paths refused; read-only git (`GIT_OPTIONAL_LOCKS=0`, `GIT_TERMINAL_PROMPT=0` in `engine/tree.py`); no network without `--online` (the app never passes it).
- New: a random port per launch. Tauri capabilities give IPC to the launcher only (the sidecar origin has none). Navigation is pinned to the launcher and the current sidecar origin. The shell never logs file contents (the stderr tail holds engine messages only). `restore_loader_env()` resets the `DYLD_*`/`LD_*` variables PyInstaller sets, so child `git` processes use the system loader.
- Still open: any local process can call the API (F6 token). There is no hardened runtime until notarization (F1).

## 8. Build pipeline (on the Mac; `desktop/build-mac.sh`)
1. Preflight: Xcode CLT (`xcode-select -p`), Rust (`rustc -vV`; host must be `aarch64-apple-darwin`), Python ≥ 3.10 or `uv`, `uname -m` = `arm64`.
2. Sidecar: `app/packaging/build_sidecar.sh`. It creates or uses `app/packaging/.venv`, installs PyInstaller, builds `lemmata-server.spec` (one-file, console, web assets as data, `collect_submodules("lemmata")`) and prints the path on its last line.
3. Assert `lipo -archs` = `arm64` (R9). Copy to `desktop/src-tauri/binaries/lemmata-server-aarch64-apple-darwin` (triple from `rustc -vV`).
4. `cargo install tauri-cli --version '^2'` if missing. `cargo tauri build --bundles app,dmg` with `bundle.macOS.signingIdentity = "-"` and `bundle.externalBin = ["binaries/lemmata-server"]`.
5. Verify (R9): `codesign --verify --strict`, run the bundled sidecar `--version` and the ready smoke test, and record sizes of `.app`, `.dmg` and sidecar (for ADR-003's estimate).
6. Print the paths of `Lemmata.app` and the `.dmg` under `desktop/src-tauri/target/release/bundle/{macos,dmg}/`.

CI and QA on Linux (per the brief): sidecar contract tests (ready/error lines, `--port 0`, SIGTERM, `--parent-pid`, the R1 kill test, watch → `scanned_at` changes) and `cargo check` of the shell. The macOS-only items (F1, F10, F13, F15, R7, R9) are checked by Juhyeong on the Mac against this list.

## 9. Measured and estimated numbers
| Item | Value | Basis |
|---|---|---|
| Sidecar size | 9.2 MB | measured, Linux x86_64, Python 3.10.20, PyInstaller 6.22.3, current spec |
| Ready, `demo` cold (build sample + scan) | 0.95 s | measured, same build |
| Ready, `demo --keep` | 0.40 s | measured, same build |
| SIGTERM → child gone | 0.54 s, temp folder removed | measured |
| `.app` / `.dmg` | 15–25 MB / 10–15 MB | estimate. QA replaces it with Mac numbers |
| Launch → graph, sample, warm, M2 | < 5 s | target (US-01.1) |
| First launch of a new build | slower (Gatekeeper/XProtect scan) | expected. QA measures |
