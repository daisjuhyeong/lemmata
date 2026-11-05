---
type: task-card
owner_agent: lead
status: draft
sources:
  - "founder decisions in chat, 2026-11-05: Tauri (not pywebview), name Lemmata, Apple Developer account later"
  - "../../architecture/data-model.md"
  - "../S02/qa-S02-localhost-demo.md"
last_reviewed: 2026-11-05
---
# S03 brief: Lemmata as a macOS desktop app

Goal: Juhyeong double-clicks `Lemmata.app` (from a `.dmg`) on his M2 Mac mini or MacBook and works on a project: no Terminal, no `127.0.0.1` typing, no Python install.

## Founder decisions (2026-11-05)
1. Shell: **Tauri v2** (not pywebview, not Electron).
2. Name: **Lemmata** (slug `lemmata`; bundle id `ai.lemmata.app` proposed). Already applied to `app/`.
3. Apple Developer Program: **later**. Builds are ad-hoc signed (`signingIdentity: "-"`), not notarized; first launch needs right-click → Open or `xattr -cr`.

## Architecture (fixed by the lead; CTO records it as ADR-003)
```
Lemmata.app
├─ Tauri shell (Rust, desktop/src-tauri)       window, menus, folder dialogs, recent projects, git check
│   ├─ launcher page (desktop/launcher/)       bundled static HTML shown when no project is open
│   └─ spawns ──► sidecar `lemmata-server`     PyInstaller one-file binary of app/src/lemmata (bundled Python)
│                  └─ serves the existing UI + API on 127.0.0.1:<random port>
└─ window navigates to http://127.0.0.1:<port>/ once the sidecar reports ready
```
The existing engine, server and web UI are reused unchanged except for the sidecar contract below and auto-refresh.

## Sidecar contract (Rust ⇄ Python) — both sides build against exactly this
- Binary name in the bundle: `lemmata-server` (Tauri `externalBin: ["binaries/lemmata-server"]`, file on disk `desktop/src-tauri/binaries/lemmata-server-<target-triple>`, e.g. `-aarch64-apple-darwin`).
- Invocations (same argparse CLI as `lemmata`):
  - `lemmata-server open <project_dir> [--paper DIR] [--code DIR] --port 0 --no-open --ready-json --parent-pid <pid> --watch`
  - `lemmata-server demo --dir <app_data>/sample --keep --port 0 --no-open --ready-json --parent-pid <pid> --watch` (Open Sample)
  - `lemmata-server demo --dir <app_data>/sample --port 0 ...` without `--keep` (Reset Sample)
- `--port 0`: bind a free port on 127.0.0.1.
- `--ready-json`: after the server is listening, print exactly one line to **stdout** and flush:
  `{"event":"ready","url":"http://127.0.0.1:53817/","port":53817,"project":"<name>","root":"<abs path>"}`
  On a fatal error before ready: one line `{"event":"error","code":"<short_code>","message":"<human text>"}` and exit code ≠ 0. Known codes: `not_found` (folder missing), `no_project` (no .tex and no git repo found), `git_missing`, `scan_failed`. All other logs go to **stderr**.
- `--parent-pid <pid>`: the sidecar exits within 2 s after that process disappears (no orphan servers).
- `--watch`: poll the project every 3 s (cheap: git HEADs + `git status --porcelain` + mtimes of non-ignored files); on change, rescan under the server lock. `/api/project` exposes `scanned_at`; the web UI polls it every 5 s and refreshes its data in place (keeping selection and tab) when it changes, showing a quiet "Updated · <time>" toast.
- SIGTERM → clean shutdown.

## Shell behaviour
- Window: title "Lemmata — <project>", default 1440×900, min 1100×720, remembers size.
- Launcher (no project open): Open Project… (one folder that holds paper and/or code; advanced: pick paper folder and code folder separately), Open Sample, Recent Projects (last 8, stored in `<app_data>/recent.json`), version, git status line.
- Menus: Lemmata (About, Quit) · File (Open Project… ⌘O, Open Sample, Open Recent ▸, Reset Sample, Close Project ⌘W → back to launcher, Reveal Project in Finder) · View (Reload ⌘R, Actual Size/Zoom In/Zoom Out) · Window · Help (Lemmata on GitHub).
- Opening another project kills the previous sidecar first. Quitting kills the sidecar.
- git check at launch: `git --version`; if missing, the launcher shows "Lemmata reads your project history with git. Install Apple's Command Line Tools to continue." + button that runs `xcode-select --install`.
- Sidecar error → launcher shows the message, with "Show details" (stderr tail).
- `<app_data>` = Tauri `app_data_dir()` (`~/Library/Application Support/ai.lemmata.app/`).

## Build
- `desktop/build-mac.sh` (on the Mac): checks Xcode CLT, Rust (rustup) and Python ≥ 3.10/uv; builds the sidecar via `app/packaging/build_sidecar.sh`; copies it to `desktop/src-tauri/binaries/lemmata-server-$(rustc -vV | sed -n 's/host: //p')`; installs `tauri-cli` v2 with cargo if missing; runs `cargo tauri build --bundles app,dmg`; prints the paths of `Lemmata.app` and the `.dmg`.
- arm64 only for now.

## Owners
- CTO: ADR-003 + `wiki/architecture/desktop-architecture.md` (status proposed).
- pipeline-eng: sidecar flags in `app/src/lemmata/cli.py`/`server.py`, `app/src/lemmata/watch.py`, `app/packaging/` (PyInstaller entry + spec + `build_sidecar.sh`), tests.
- web-eng: `desktop/` (Tauri project, launcher page, menus, recent projects, git check, `build-mac.sh`, README), and the 5-second auto-refresh in `app/src/lemmata/web/app.js`.
- designer: app icon `desktop/icons/lemmata-icon.svg` (1024×1024) + launcher copy.
- QA: verify the sidecar contract and the Rust build on Linux; macOS build is checked by Juhyeong / CI.
