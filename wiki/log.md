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
