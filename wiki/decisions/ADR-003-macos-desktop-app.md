---
type: adr
owner_agent: cto
status: proposed
sources:
  - "../sprints/S03/S03-brief.md (lead, 2026-11-05: architecture and sidecar contract, fixed)"
  - "founder decisions in chat, 2026-11-05 (relayed by the lead; no file in raw/ yet): Tauri v2, name Lemmata, Apple Developer account later"
  - "ADR-002-localhost-demo.md, ../architecture/demo-architecture.md, ../architecture/data-model.md"
  - "code on branch s03-mac-app, read 2026-11-05: app/src/lemmata/{cli.py, server.py, watch.py, gitbin.py, engine/tree.py, web/app.js}, app/packaging/{lemmata-server.spec, build_sidecar.sh, lemmata_server.py}"
  - "CTO measurement 2026-11-05 (this session, not in raw/): PyInstaller 6.22.3 one-file build of the spec above, Python 3.10.20, Linux x86_64; size, ready time, signal and orphan behaviour"
  - "PyInstaller 6.22.3 `--help` (local): `--bootloader-ignore-signals` text, 'rather than forwarding them to the child process'"
  - "https://v2.tauri.app/develop/sidecar/ ; https://v2.tauri.app/distribute/sign/macos/ ; https://v2.tauri.app/security/capabilities/"
  - "https://pyinstaller.org/en/stable/operating-mode.html ; https://pyinstaller.org/en/stable/usage.html"
  - "https://support.apple.com/en-us/102445 (Safely open apps on your Mac) ; https://developer.apple.com/news/?id=saqachfa (Updates to runtime protection in macOS Sequoia, 2024-08-06)"
  - "https://git-scm.com/docs/git#Documentation/git.txt-GITOPTIONALLOCKS ; https://git-scm.com/docs/git-config#Documentation/git-config.txt-coreprecomposeUnicode"
  - "https://docs.python.org/3/library/select.html#kqueue-objects ; https://pywebview.flowrl.com/ ; https://www.electronjs.org/docs/latest/"
last_reviewed: 2026-11-05
---
# ADR-003: Lemmata as a macOS desktop app (Tauri v2 shell + PyInstaller Python sidecar)

Status: **proposed** (Juhyeong approves). Supersedes: **the "how to launch" part of [ADR-002](ADR-002-localhost-demo.md) Decision 1 only** (see "Relation to ADR-002"). Companion page: [desktop architecture](../architecture/desktop-architecture.md). The architecture and the sidecar contract are fixed by the lead in the [S03 brief](../sprints/S03/S03-brief.md). This ADR records them, gives the reasons, and lists the macOS risks with a mitigation for each. It does not change the contract. Where I recommend a change, it is marked **(proposal)** and needs the lead's OK and a note to QA.

Note on sources: the outbound proxy refused the documentation URLs in this session, so I could not re-fetch them. Claims that rest only on them are marked *verify on the Mac*. The process, signal and size claims marked *measured* come from my own Linux build of the current spec (sources list).

## Context
- **Why an app.** In ADR-002 the launch is `uv run --project app lemmata demo` in a Terminal, followed by a browser tab on `127.0.0.1:8765` ([demo-architecture §8](../architecture/demo-architecture.md)). That requires Python ≥ 3.10, `uv`, a network fetch on first run and a source checkout. The S03 goal is: double-click `Lemmata.app` from a `.dmg`, with no Terminal, no `127.0.0.1` typing and no Python install ([S03 brief](../sprints/S03/S03-brief.md), Goal).
- **Why now.** The founder decided on 2026-11-05 to use Tauri v2, the name Lemmata, and ad-hoc signing for now (brief, "Founder decisions"). The engine, server and UI passed S02 QA ([qa-S02](../sprints/S02/qa-S02-localhost-demo.md)), so the code that would be wrapped is stable. Wrapping it now lets the 2nd presentation (MVP demo) open with a real app icon, and the CLI path stays as the fallback.
- **What exists.** The engine is about 2,800 lines of Python (`app/src/lemmata/engine/*.py`) and the UI is about 1,750 lines of plain JS (`web/app.js`), counted on 2026-11-05. The engineers are already building the sidecar flags (`--port 0`, `--ready-json`, `--parent-pid`, `--watch`), `watch.py`, `gitbin.py` and the PyInstaller spec against the brief.
- **Constraints carried over.** Everything stays offline except the opt-in `--online`. There are no model calls and nothing goes through Juhyeong's Claude plan. The server binds 127.0.0.1 only. The tool writes only under `<project>/.lemmata/` (ADR-002 Decisions 2, 7, 8; CLAUDE.md "Runtime").

## Options
| Option | For | Against |
|---|---|---|
| **O1. Tauri v2 shell + Python engine as a PyInstaller one-file sidecar** (brief) | Reuses engine, server and UI unchanged. The Rust code stays thin (window, menus, dialogs, process supervision). Uses the system WKWebView, so no bundled browser. Leaves a path to signing, auto-update and an in-process engine later | Two runtimes and two build chains (Rust + PyInstaller). One-file extraction on every launch. Process supervision across a **two-process** sidecar (see R1). A localhost server is still present |
| O2. Tauri with the engine rewritten in Rust | One process, smallest bundle, no Python, no localhost server (commands over Tauri IPC) | Rewrites about 2,800 lines and has to re-prove the S02 golden set. Cannot land before the 2nd presentation. Two engines would have to be kept equal during the transition |
| O3. pywebview (Python-only shell around WKWebView) | One runtime. The server can even run in-process | Rejected by the founder (2026-11-05). Packaging is still PyInstaller or py2app. Weaker native menu, dialog and update tooling than Tauri, and no route to a Rust engine |
| O4. Electron | Mature tooling, auto-update | Bundles Chromium and Node (an app on the order of 100 MB+, *verify*). Brings back the Node/npm toolchain that ADR-002 excluded. A second JS runtime only to host a page we already serve |
| O5. Keep localhost (status quo) | Zero work. Already QA-passed | Fails the S03 goal: Terminal, Python and uv are still required, and the user types an address or relies on `webbrowser.open` |

## Decision
1. **Shape O1**, exactly as in the brief. `Lemmata.app` contains the Tauri v2 shell (Rust, `desktop/src-tauri`), a bundled launcher page (`desktop/launcher/`) and the sidecar `lemmata-server`, a PyInstaller one-file build of `app/src/lemmata`. When the sidecar reports ready, the window navigates to `http://127.0.0.1:<port>/`.
2. **Sidecar contract** as in the brief: `open` / `demo` invocations, `--port 0`, a single `--ready-json` line on stdout (`ready` or `error` with codes `not_found`, `no_project`, `git_missing`, `scan_failed`), `--parent-pid`, `--watch`, and SIGTERM → clean shutdown. Logs go to stderr. Normative text lives in the brief; [desktop-architecture §3](../architecture/desktop-architecture.md) shows the timeline. *Observed:* the code also emits `bind_failed` and `not_sample`. Rust treats any unknown code as a generic error with the message shown (proposal: the lead adds both to the list of known codes).
3. **Bundle id** `ai.lemmata.app` (brief, proposed). `<app_data>` = `~/Library/Application Support/ai.lemmata.app/`.
4. **Signing**: ad-hoc (`signingIdentity: "-"`), not notarized, **arm64 only**.
5. **Stopping the sidecar is SIGTERM-first.** This is how the brief's "kill" (brief, Shell behaviour) has to be implemented. The shell sends SIGTERM to the sidecar pid, waits up to 3 s for the `Terminated` event, and only then hard-kills. A plain hard kill orphans the server (R1, measured).
6. **The sidecar's web origin gets no Tauri capability.** Only the bundled launcher may call Tauri commands (open dialog, recent, reveal). The page served from `127.0.0.1` runs as an ordinary web page with no IPC (Tauri capabilities scope by window and URL, *verify*).
7. **Navigation is pinned.** The window may show only the launcher and `http://127.0.0.1:<current port>/…`. Every other URL (GitHub in Help, links in evidence) opens in the default browser.
8. **The CLI remains** for development, QA, CI and as the presentation fallback. ADR-002's commands still work.

## Consequences
### Size and startup
- **Sidecar size, measured**: 9.2 MB (9,181,656 bytes) for the current spec on Linux x86_64 with Python 3.10. A macOS arm64 build should be of the same order (8–12 MB, *estimate*). The Tauri shell adds a few MB, because WKWebView is the system's. **Estimate**: `Lemmata.app` 15–25 MB, `.dmg` 10–15 MB. QA records the real numbers from the Mac build.
- **Startup, measured on Linux**: `demo` cold (extract, build sample, scan, bind) printed `ready` after 0.95 s. `demo --keep` took 0.40 s. Each launch extracts the runtime to a fresh `$TMPDIR/_MEI*` folder. On macOS the **first launch of each new build** is expected to be slower because Gatekeeper/XProtect scans new binaries (*verify*; QA measures cold and warm). A real repository adds its scan time (target < 10 s for `alarm-analyzer-eval`, demo-architecture §6), because `ready` comes **after** the first scan. The shell must therefore wait patiently (R4).
- **Target** (carried over from US-01.1): double-click to graph visible < 5 s for the sample, warm, on the M2.

### Signing and Gatekeeper
- Apple silicon requires every executable to be signed, and an ad-hoc signature is enough to run. Ad-hoc is not notarized, so **a copy that arrives with the quarantine attribute** (browser download, AirDrop, chat apps) is blocked at first launch.
- **The brief's "right-click → Open" is out of date.** From macOS 15 Sequoia, Control-click → Open no longer bypasses Gatekeeper. The user has to try once, then go to **System Settings → Privacy & Security → Open Anyway**, or run `xattr -dr com.apple.quarantine /Applications/Lemmata.app` (Apple sources above, *verify*). The launcher README and the designer's copy should say this.
- **A build made with `build-mac.sh` on the same Mac carries no quarantine attribute and opens normally.** For the presentation, build on the presenting Mac, or clear the attribute after copying.
- Ad-hoc signatures change with every build. macOS privacy grants (folder access, R7) may be asked for again after a rebuild.

### Platform
- **arm64 only.** It will not run on an Intel Mac. Before Juhyeong relies on the MacBook, confirm it is Apple silicon (`uname -m` → `arm64`). The sidecar's architecture follows the Python that `build_sidecar.sh` uses. If `uv` picks an x86_64 Python (for example, under a Rosetta shell), the file named `-aarch64-apple-darwin` will actually be x86_64. The build must assert the architecture (R9).

### Sidecar process lifecycle
- One sidecar per open project. Opening another project, Close Project, Reset Sample and Quit all stop the current sidecar first (SIGTERM-first, Decision 5). Reset Sample additionally waits until the old process has exited before the new one deletes the sample folder (R1).
- The PyInstaller one-file sidecar is **two processes**: the bootloader (the pid Tauri sees) and a Python child that does the work. This is *measured*: the child's PPID is the bootloader. The bootloader forwards catchable signals to the child (PyInstaller `--help` text), so SIGTERM works end to end (*measured*: child gone 0.54 s after SIGTERM to the bootloader, and the temp folder was removed). SIGKILL cannot be forwarded (R1).
- `--parent-pid` = the Tauri app's own pid (`std::process::id()`), **not** the bootloader pid.
- Crash paths: Tauri crashes → the sidecar exits within 2 s (parent-pid watch). Sidecar crashes → the shell receives `Terminated` and shows the launcher with the stderr tail ([desktop-architecture §4](../architecture/desktop-architecture.md)).

### Security and privacy (unchanged in substance from ADR-002)
- The server still binds **127.0.0.1 only**. The Host and Origin checks, the JSON content type on POST, the 64 KB body cap and the hidden-path refusal all stay (`server.py`). The port is now random per launch, which also makes DNS rebinding and cross-site guessing harder. The Host/Origin checks remain the actual guard.
- **No network**, unless the user opts in to `--online`. The app never passes `--online` in S03 (no UI for it), so the app is fully offline. No model calls, no telemetry, no auto-update.
- Any local process on the Mac can still call the API, as with ADR-002. Follow-up F6 adds a per-launch token.
- The sidecar's page has no Tauri IPC (Decision 6), so a bug in our web UI cannot reach the file system or the shell through Tauri.
- Writes: `<project>/.lemmata/` (unchanged), `<app_data>/` (recent list, sample, window state, logs) and the transient `$TMPDIR/_MEI*`. No writes to the user's repos, and git runs with `GIT_OPTIONAL_LOCKS=0` (already in `engine/tree.py`).

### Scope and schedule
- New work: the Rust shell, packaging, the watch loop and auto-refresh. If S03 runs late, the **cut order** (first cut → last) is: Reset Sample menu item → View zoom items → remembered window size → advanced paper/code picker → Recent Projects → auto-refresh (the Rescan button stays) → the app itself. The 2nd presentation then runs on the ADR-002 CLI, which already passed QA. We cut scope; we do not slip the presentation.

## Relation to ADR-002
- **Superseded:** Decision 1's launch mechanics for end users, that is the one Terminal command plus browser tab on port 8765 plus `webbrowser.open`. In the app, the user launches by double-click, the port is random, and the shell window replaces the browser tab.
- **Lifted from ADR-002's scope-cut list by the S03 brief** (an amendment, not a supersession): "Tauri" and "file watching (manual Rescan)". `--watch` polls every 3 s and the UI auto-refreshes every 5 s.
- **Unchanged:** the engine and server design (Decision 1 apart from launch), the hub folder, content-hash staleness, propagation rules, checks, offline-first references, the deterministic analyzer, rendering and export (Decisions 2–11), and every other scope cut.

## Risks in the contract on macOS, with mitigations
Full detail, owners and test steps: [desktop-architecture §6](../architecture/desktop-architecture.md).
| # | Risk | Mitigation |
|---|---|---|
| R1 | **One-file = two processes. A hard kill of the sidecar orphans the server.** *Measured*: after SIGKILL to the bootloader, the Python child was re-parented to pid 1 and kept answering `/api/health` until the `--parent-pid` process died. Its `_MEI*` temp folder was never removed. Tauri's child kill is a hard kill (*verify*). Every project switch would leak a server and about 9 MB. For Reset Sample, the orphan's watcher would write into the folder being rebuilt | Shell: SIGTERM → wait ≤ 3 s for `Terminated` → hard kill. Sidecar (proposal, additive): also exit when `os.getppid()` changes from its startup value (bootloader gone), and start the parent watch **before** the first scan, not after it (today it starts in `_serve`, after the scan) |
| R2 | `/usr/bin/git` on a Mac without Command Line Tools is a shim. Running `git --version` from Rust **opens Apple's install dialog by itself**, which doubles up with our button. A Finder-launched app's PATH lacks `/opt/homebrew/bin` | Rust mirrors `gitbin.py`: `xcode-select -p` first, then the candidates `/usr/bin/git` (only if CLT is present), `/opt/homebrew/bin/git`, `/usr/local/bin/git`. The sidecar already does the same through `ensure_git()` |
| R3 | **Downloads do nothing in the app.** "Export HTML report" is `<a href="/api/export" download>` (`app.js`), and WKWebView in Tauri needs an explicit download handler (*verify*) | Register Tauri's `on_download` on the window. Save to `~/Downloads/<name>-report.html` and reveal it in Finder. QA clicks both export buttons inside the app |
| R4 | `ready` is printed after the first full scan plus one-file extraction. A short Rust timeout reports a healthy large project as failed | Ready timeout ≥ 120 s. The launcher shows "Opening <project> — scanning…" with a Cancel button (SIGTERM). Stderr lines are shown as progress |
| R5 | The stdout/stderr pipes are not drained after `ready` → the pipe buffer fills → the sidecar blocks on a log write while holding the server lock → the UI freezes | Rust consumes the sidecar's event stream for its whole life. It keeps the last 200 stderr lines in memory (for "Show details") and writes them to `~/Library/Logs/ai.lemmata.app/sidecar.log`. Rust skips any stdout line that does not parse as `{"event":…}` instead of failing |
| R6 | Exit before `ready` **without** a JSON line (argparse error exit 2, a crash in the bootloader, a wrong-architecture binary) | Rust: process `Terminated` before `ready` → "Lemmata's engine stopped before it was ready (exit N)" plus Show details |
| R7 | **macOS privacy prompts (TCC)** for projects in Documents, Desktop, Downloads or iCloud Drive. An Overleaf zip unzipped in Downloads is the likely case. Ad-hoc rebuilds may re-ask (*verify*) | Expected. Copy in the launcher explains the prompt. For the demo, keep projects in `~/Projects/` (not protected) and open each one once after installing the final build |
| R8 | Web UI copy assumes a browser: the in-page picker says "run `lemmata open` in a terminal", and its recent list is in `localStorage`, which is keyed by origin. The port changes per launch, so the list is empty each time | Proposal (additive): `/api/health` gains `"embedded": true` when started with `--ready-json`. The UI then hides its recent list and points to File → Open Project… (⌘O). Requires a CTO edit to data-model.md and a note to QA |
| R9 | The architecture in the sidecar file name can be wrong (x86_64 Python under Rosetta). The bundler's re-sign can break the one-file archive | `build-mac.sh` asserts `lipo -archs` = `arm64` and runs `codesign --verify --strict` on the `.app`. Smoke test: `Lemmata.app/Contents/MacOS/lemmata-server --version` and a `demo --ready-json` run from inside the bundle |
| R10 | Hangul file names: git on macOS reports NFC (`core.precomposeUnicode`), while a non-git folder walk and LaTeX sources can be NFD or NFC. Path keys disagree → missing edges or phantom "changed" | Engine (proposal): normalise repo-relative paths to NFC at the `Tree` boundary and in `watch.py`. QA fixture with an NFD-named figure in a non-git paper folder |

## Follow-ups (not in S03)
- F1. **Notarization** after the Apple Developer Program purchase (spending → Juhyeong). Developer ID signing, hardened runtime (PyInstaller binaries need entitlements reviewed), `notarytool`, stapling. This removes the Gatekeeper friction and the TCC re-prompts.
- F2. **Universal build** (arm64 + x86_64): two sidecars and `lipo`, or a per-arch DMG. Only needed if an Intel user appears.
- F3. **Auto-update** (Tauri updater). Needs signing keys and a hosting decision ("anything published" → Juhyeong). This is the first network access the app would make, so it must stay opt-in.
- F4. **PyInstaller one-dir instead of one-file** if QA measures a slow cold start or `_MEI*` leaks. This needs a contract change (resource folder instead of `externalBin`), so it is the lead's call.
- F5. **Engine in-process** (Rust rewrite, or Python embedded through PyO3), which removes the localhost server and the sidecar lifecycle. Its own ADR, after launch.
- F6. **Per-launch API token** (shell → sidecar through env, set as a cookie on first navigation) so other local processes cannot drive the API.
- F7. **Single instance** (Tauri single-instance plugin) or a `.lemmata/lock`, so that two app instances never write the same `triage.json`.

## Open questions for Juhyeong
1. Approve ADR-003 (and the cut order above).
2. Bundle id `ai.lemmata.app` presumes the `lemmata.ai` domain. Changing it later moves `<app_data>` and resets macOS permissions. Keep it, or pick an id you control before the first shared build.
3. Is the MacBook Apple silicon? If not, F2 moves into S03, or the demo runs only on the M2.
4. Help → "Lemmata on GitHub" links to a public repo. Hide the item until publishing is approved.
5. Will the `.dmg` go to anyone else (classmates, IR audience)? That counts as publishing, and each recipient hits the Sequoia "Open Anyway" step.

## Approved by
(pending — Juhyeong, date)
