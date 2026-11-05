---
type: handoff
owner_agent: web-eng
status: draft
sources:
  - "S03-brief.md"
  - "../../design/screens/desktop-launcher.md"
  - "../../design/DESIGN.md"
last_reviewed: 2026-11-05
---
# S03 handoff: web engineer

## Delivered
- `desktop/` Tauri v2 project (see `desktop/README.md`): shell modules, launcher page, icons generated from the designer's SVG, `build-mac.sh`.
- `app/src/lemmata/web/app.js`: 5 s auto-refresh (`/api/project` poll, skipped while the document is hidden or a dialog is open; reloads data in place keeping tab, selection, graph pan/zoom and scroll; toast "Updated · HH:MM").
- `.gitignore`: `desktop/src-tauri/target/`, `binaries/*`, `gen/`, `app/dist/`, `app/build/`, plus `app/packaging/{dist,build,.venv}/`.

## Verified on Linux
- `cargo build` in `desktop/src-tauri`: zero warnings.
- Headless (xvfb) with the real PyInstaller binary: `LEMMATA_OPEN=sample` -> spawn -> ready line -> window navigates and the Lemmata graph renders (screenshot checked). Launcher and the sidecar-error panel also rendered.
- `PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_*.py'`: 40 tests OK. `node --check app.js` OK.

## Not verified (Mac only, or not exercised)
macOS build, dmg, ad-hoc signing, native menu look, folder dialogs, Reveal in Finder, xcode-select flow, download handler, graceful quit path (SIGTERM then 3 s kill) and Open Another Project, window size memory, auto-refresh in a live browser.

## Findings for the pipeline engineer
- Sidecar does not exit after parent death when its stderr pipe is already closed (reproduced: app killed with -9 leaves the server running; reproduced in isolation with a closed stderr pipe). `_watch_parent` prints to stderr before shutting down; BrokenPipeError kills the watcher thread before `os._exit`. Wrap the print in try/except (and make other logging tolerant).
- `build_sidecar.sh` writes to `app/packaging/dist/`, not `app/dist/`.

## Decisions I made
- Launcher window is 720x520 (designer spec), switching to 1440x900 (min 1100x720) for a project; the brief's size applies to the project window.
- Split open (advanced) passes the paper folder, else code folder, as the positional `project_dir`.
- Window state is hand-rolled (no window-state plugin) because sizes differ between launcher and project.
- Test hook env `LEMMATA_OPEN` (documented in README).
- Window is created in `setup` (config `create:false`) to attach `on_download`.
