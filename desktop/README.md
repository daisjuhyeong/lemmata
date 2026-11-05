# Lemmata desktop app (Tauri v2)

A thin native shell around the Python sidecar. The shell (Rust) owns the window, menus, folder dialogs, recent projects and the git check. The analysis engine runs as a bundled one-file binary `lemmata-server` (PyInstaller, built from `app/src/lemmata`) that serves the existing UI on `127.0.0.1:<random port>`; the window navigates there when the sidecar prints its ready line. Contract and behaviour: `wiki/sprints/S03/S03-brief.md`.

```
desktop/
  launcher/       static launcher page (frontendDist): HTML, CSS, JS, DESIGN.md tokens
  src-tauri/      Rust: main.rs, state.rs, sidecar.rs, commands.rs, menu.rs, recent.rs, git.rs, downloads.rs
  icons/          lemmata-icon.svg (designer) + generated icns/ico/png (`cargo tauri icon`)
  build-mac.sh    one-command build on the Mac
```

## Build Lemmata.dmg on a Mac (Apple silicon)
1. `xcode-select --install` (once), install Rust with rustup (once), and `brew install uv` (or have Python 3.10+).
2. `cd <repo> && git checkout s03-mac-app`
3. `./desktop/build-mac.sh`
4. The script prints the paths of `Lemmata.app` and `Lemmata.dmg` under `desktop/src-tauri/target/release/bundle/`.

For development: put a sidecar binary at `desktop/src-tauri/binaries/lemmata-server-<target-triple>` and run `cd desktop/src-tauri && cargo tauri dev`.

## First launch on another Mac (unsigned build)
The app is ad-hoc signed, not notarized. An app built locally on the same Mac is not quarantined and opens normally. A downloaded `.dmg` is quarantined:
- macOS 15 and later: right-click, Open no longer bypasses Gatekeeper. Open System Settings, Privacy and Security, scroll to the message about Lemmata and click Open Anyway.
- Or in Terminal: `xattr -dr com.apple.quarantine /Applications/Lemmata.app`
- macOS 12 to 14: right-click the app, Open, then Open again.

## Behaviour notes
- Closing, quitting and opening another project send SIGTERM to the sidecar and force-kill it after 3 s. The sidecar also gets `--parent-pid <app pid>` so it exits by itself if the app dies.
- The git check runs `xcode-select -p` first on macOS (and looks for Homebrew git), so merely launching Lemmata never triggers Apple's installer pop-up.
- Export HTML report (a download in the web UI) is saved to `~/Downloads` and revealed in Finder.
- Ready timeout is 120 s (first launch of a one-file binary can be slow).
- Window sizes: launcher 720x520; project 1440x900 default, min 1100x720, last project size remembered in `<app_data>/window.json`. Recent projects: `<app_data>/recent.json`.
- The sidecar page is a remote origin; capabilities grant it no IPC. Only the launcher can call the shell commands.
- Test hook: `LEMMATA_OPEN=sample` or `LEMMATA_OPEN=/path/to/folder` opens a project at startup (used for the headless Linux smoke test).

## Linux check (CI / dev)
`sudo apt install libwebkit2gtk-4.1-dev libgtk-3-dev librsvg2-dev libayatana-appindicator3-dev build-essential pkg-config`, copy any executable to `src-tauri/binaries/lemmata-server-x86_64-unknown-linux-gnu`, then `cd src-tauri && cargo build`.
