---
type: handoff
owner_agent: lead
status: draft
sources:
  - "qa-S02-localhost-demo.md"
  - "handoff-pipeline-eng.md"
  - "handoff-web-eng.md"
  - "../../architecture/data-model.md"
  - "../../research/market/naming-screen-2026-11-04.md"
last_reviewed: 2026-11-04
---
# Handoff: S02-04 lead (rename, QA fixes, packaging)

## Name
Juhyeong chose to keep a placeholder for now (2026-11-04). Working name **Research Map**, slug `rmap` (package `app/src/rmap/`, CLI `rmap`, hub folder `.rmap/`), recorded in `app/branding.json`. The UI shows a "working name" tag beside the brand. When the name is chosen: `python3 app/scripts/rename.py --slug <slug> --display "<Name>"` (use `--dry-run` first). The shortlist so far is in [naming-screen-2026-11-04](../../research/market/naming-screen-2026-11-04.md). The lead checked npm and PyPI for Sivro, Antecedo, Nevra and Tavro (all free on 2026-11-04). "Nevra" collides with the RPM term NEVRA (name-epoch-version-release-architecture), so it is a poor choice for developer search results.

## QA defects fixed by the lead after the QA run
| QA id | Fix | Where |
|---|---|---|
| D1 | Full-page notice now only below 1024 px; from 1024 to 1279 px the side panels narrow (200/320 px), and the top bar hides the scan time and the working-name tag | `web/app.css`, `web/index.html` |
| D2 | Proposed `value_match` links read "shares a value with" (was "was linked by you to") | `web/app.js` EDGE_PHRASE |
| D3 | Proposed links are drawn dotted with a "Proposed" label in the default graph view | `web/app.js` edge class logic |
| D6, D7 | `/api/file` and `/api/raw` refuse any path with a hidden component (`.git`, `.rmap`, `.env`, …), which also covers `.RMAP` on case-insensitive disks | `server.py` `safe_path` |

Checked after the fixes: 33/33 tests pass; `/api/file?repo=code&path=.git/config` → 404, `train.py` → 200; screenshots at 1440 and 1152 px have no console errors. QA did not re-run after these fixes.

## Still open (not fixed)
- D4 graph nodes carry no repo label; D5 Runs band sits above Code (contract order; Juhyeong's earlier order had code above runs).
- D8 engine tests write `.rmap/` into the real repo they smoke-test.
- D9–D13 low/nit items in the QA report; `golden.json` (S02-03 AC1) not written.
- `--online` reference lookup is untested (no network in the build sandbox).
- Not tested on macOS: launch, browser auto-open, case-insensitive paths.
- Paper layer for alarm-analyzer-eval waits for the Overleaf source zip.

## Needs Juhyeong
1. Approve or change ADR-002 (proposed) and reconcile it with ADR-001, which exists only on the Mac mini.
2. Layer order: runs above code (contract) or code above runs.
3. Keep listing byte-identical outputs under a change (CTO recommends yes; it carries the "results not regenerated" story).
4. Keep the read-only `/api/file` and `/api/raw` routes web-eng added beyond the contract.
5. Approve `--online` lookups (OpenAlex, Crossref) as a use of his own data.
6. CLAUDE.md Scope/Runtime and vision.md are out of date with the 1st-presentation repositioning.
7. Merge to main.
