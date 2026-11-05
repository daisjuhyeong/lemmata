# Log (append-only)
date | agent | operation | files touched | note
2026-11-02 | setup | build | repo skeleton, CLAUDE.md, 8 role cards, settings.json | created by Claude via linked chat
2026-11-04 | lead | build | branch s02-localhost-demo | S02 started from linked chat; cloud clone of GitHub main (Mac mini-only branches such as ADR-001 not included)
2026-11-04 | analyst | ingest | wiki/research/market/naming-screen-2026-11-04.md | Replacement name screen for Lemmata, rounds 1-2 (~33 candidates); shortlist Sivro/Antecedo/Nevra/Tavro; not a clearance
2026-11-04 | cto | build | wiki/decisions/ADR-002-localhost-demo.md, wiki/architecture/demo-architecture.md, wiki/architecture/data-model.md, READMEs | S02 localhost demo architecture + data/API contract (proposed; supersedes nothing until ADR-001 reconciled)
2026-11-04 | pm | build | wiki/product/README.md, wiki/product/demo-spec.md, wiki/sprints/S02/S02-01..04 | S02 demo spec (14 stories, 56 AC, golden set, walkthrough); founder-decision sources only
2026-11-04 | designer | build | wiki/design/DESIGN.md, wiki/design/screens/demo-screens.md | S02 tokens and screen specs (draft)
2026-11-04 | pipeline-eng | build | app/src/rmap/engine/*, app/samples/make_sample.py, app/tests/test_engine.py, handoff | engine + sample + tests; golden set F01-F10, A1/A2 pass; real-repo scan 0.57 s; --online untested
2026-11-04 | web-eng | build | app/pyproject.toml, app/src/rmap/{cli,server,fixture_engine}.py, app/src/rmap/web/*, app/tests/fixtures, app/docs/screens, handoff | server + UI (graph, alarms/analyzer, checks, links, checkpoints, export); 24 screenshots
2026-11-04 | lead | build | app/scripts/rename.py, app/branding.json, app/README.md, wiki/index.md | placeholder renamed to working name "Research Map" / rmap (Juhyeong chose to keep a placeholder); one-command rename script
2026-11-04 | qa | lint | wiki/sprints/S02/qa-S02-localhost-demo.md | S02 QA: golden set pass via HTTP; 33 tests pass on 3.13+3.10; offline, guards, export pass; verdict ship with caveats (D1, D2, walkthrough edits)
2026-11-04 | pm | build | wiki/product/demo-spec.md | walkthrough and US-11.4 aligned to built UI per QA report; command rmap demo
2026-11-04 | lead | build | app/src/rmap/{server.py,web/app.js,web/app.css,web/index.html}, wiki/sprints/S02/handoff-lead.md | fixed QA D1 (min width 1024), D2 (wording), D3 (proposed links drawn), D6/D7 (hidden paths refused); 33 tests pass; QA not re-run
2026-11-05 | lead | build | app/** (rename), wiki/sprints/S03/S03-brief.md | founder decisions: Tauri (not pywebview), name Lemmata, Apple Developer account later; S03 brief with sidecar contract
2026-11-05 | designer | build | desktop/icons/lemmata-icon.svg, wiki/design/screens/desktop-launcher.md | S03 app icon and launcher/menu copy
2026-11-05 | cto | build | wiki/decisions/ADR-003-macos-desktop-app.md, wiki/architecture/desktop-architecture.md | ADR-003 Tauri+sidecar (proposed); 11 macOS risks, R1 measured
2026-11-05 | pipeline-eng | build | app/src/lemmata/{cli,server,gitbin,watch}.py, samples/, app/packaging/*, app/tests/test_sidecar.py, handoff | sidecar contract, one-file PyInstaller build verified on Linux (9.4 MB, ready 0.6 s)
2026-11-05 | web-eng | build | desktop/**, app/src/lemmata/web/app.js, .gitignore, handoff | Tauri v2 shell compiles on Linux; headless spawn-ready-navigate verified; 5 s auto-refresh
2026-11-05 | lead | build | app/src/lemmata/cli.py, .github/workflows/mac-app.yml | parent-exit fix when stderr is closed; macOS CI build of Lemmata.dmg
2026-11-05 | lead | build | wiki/sprints/S04/S04-brief.md | founder decisions: app on MacBook, hub on Mac mini via Tailscale, GitHub-only sign-in (OAuth App client id registered), Overleaf zip upload, Claude Code via MCP
2026-11-05 | cto | build | wiki/decisions/ADR-004-hub-on-mac-mini.md, wiki/architecture/threat-model.md | ADR-004 proposed; threat model with 11 must-fix items (forwarded to engineers)
2026-11-05 | pipeline-eng-mcp | build | app/src/lemmata/mcp.py, cli.py, app/tests/test_mcp.py, handoff | MCP server, 9 tools, stdio entry, SDK handshake OK; CTO items 8-9
2026-11-05 | pipeline-eng-hub | build | app/src/lemmata/hub/*, server.py, cli.py, engine/tree.py, fake_github.py, test_hub.py, handoff | multi-project hub, pairing, GitHub device flow, zip ingest, sync, MCP route; CTO items 1-7,10,11
2026-11-05 | web-eng | build | web/hub/*, web/app.js, desktop/launcher/*, desktop/src-tauri/*, mock_hub.py, s04 screenshots, handoff | hub pages, API base, Tauri connect flow
2026-11-05 | lead | build | app/src/lemmata/hub/routes.py | CSP allows inline styles (vendored Cytoscape)
2026-11-05 | qa | lint | wiki/sprints/S04/qa-S04.md, wiki/index.md | S04 QA: block. 85 tests OK, e2e/browser/MCP SDK pass, golden set pass; M9 fails, M3/M6/M8 partial, new DoS via negative Content-Length (D2)
2026-11-05 | qa | lint | wiki/sprints/S04/qa-S04.md | S04 re-test: ship with caveats. 95 tests OK; M3/M6/M9 now pass, M8 passes except UI display of triage by; D2/D3/D6/D7/D8/D9/D11/D12 fixed; online_refs needs founder approval
2026-11-05 | pipeline-eng-hub | build | app/src/lemmata/hub/*, server.py, engine/tree.py, test_hub.py | QA round-1 fixes D1-D12 (negative Content-Length DoS, atomic zip ingest, .git aliases, Tailscale retry, Funnel header, online_refs opt-in); 95 tests
2026-11-05 | pipeline-eng-mcp | build | app/src/lemmata/mcp.py, engine/api.py, engine/triage.py | notice first, recursive cleaning, structured triage `by`
2026-11-05 | lead | build | docs/SETUP-two-macs.md, .github/workflows/mac-app.yml | two-Mac setup guide; CI builds the dmg for s04-hub-remote
2026-11-05 | lead | build | app/src/lemmata/hub/launchd.py, app/tests/test_hub.py | hub install without --data used None (crash on Mac mini); default to ~/Lemmata; 96 tests pass on 3.13 and 3.15
2026-11-05 | lead | build | app/src/lemmata/hub/guard.py, hub/cli.py, test_hub.py | hub under launchd did not detect Tailscale (CLI fails there) -> loopback only; detect Tailscale IPs from interfaces, cache names from interactive runs
