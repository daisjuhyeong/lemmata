---
type: handoff
owner_agent: pipeline-eng
status: done
sources:
  - "S03-brief.md"
  - "../../../app/src/lemmata/cli.py"
last_reviewed: 2026-11-05
---
# S03 handoff: pipeline-eng (sidecar)

Done per brief, section "Sidecar contract": `--port 0`, `--ready-json`, `--parent-pid`, `--watch`, SIGTERM, git resolution, PyInstaller build, tests.

## Files
- `app/src/lemmata/cli.py`, `server.py` (edited); new `gitbin.py`, `watch.py`, `samples/` (package; `make_sample.py` moved here, `app/samples/make_sample.py` is a wrapper).
- `app/packaging/`: `lemmata_server.py`, `lemmata-server.spec`, `build_sidecar.sh`, `.gitignore`.
- `app/tests/test_sidecar.py` (7 tests; binary test skips if not built). Total 40 tests pass.

## Differences / additions the Rust side must know
- JSON lines are compact (`separators=(",",":")`), keys in order event,url,port,project,root.
- Extra error codes beyond the brief: `bind_failed`, `not_sample` (demo --dir exists, not a sample folder, not empty). Treat unknown codes generically. Any unexpected exception with --ready-json becomes `scan_failed`.
- Error JSON line is also echoed to stderr as `lemmata: <message>`.
- `no_project` = no `.lemmata/project.json`, no `.git`, no `.tex` within 3 levels, and no --paper/--code. `not_found` also fires for missing --paper/--code folders. `serve` on a folder without `.lemmata/project.json` is `no_project`.
- `git_missing` is checked for open/serve/demo/scan/checkpoint (not with --fixtures). git folder is prepended to PATH so engine subprocesses find it.
- `scanned_at` has one-second resolution (engine `now_iso`); watch rescans are >= 3 s apart so it always changes.
- Server change: engine GET endpoints now take the server lock, so a request during a rescan waits instead of seeing a half-built scan (found in testing: transient 500 on /api/project).
- --watch is ignored with --fixtures. SIGTERM exits 0; parent gone exits 0 (hard exit fallback after 1 s).
- Demo with empty existing --dir is allowed.

## Not verified here
macOS: `xcode-select -p` shim check and arm64 build are untested (Linux only). Build on the Mac with `app/packaging/build_sidecar.sh`.
