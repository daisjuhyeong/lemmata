---
type: qa-report
owner_agent: qa
status: draft
sources:
  - "../../product/demo-spec.md (stories US-01..US-14, golden set, walkthrough)"
  - "../../architecture/data-model.md (contract, section 14 id mapping)"
  - "../../architecture/demo-architecture.md (section 5 security, section 6 performance, section 8 runbook)"
  - "handoff-pipeline-eng.md, handoff-web-eng.md (claims verified here, not taken as facts)"
  - "S02-03-qa.md (task card)"
  - "QA runs in this session, 2026-11-04, branch s02-localhost-demo (commands below; artefacts in /tmp/qa-*)"
  - "local repo /home/claude/alarm-analyzer-eval @ baa9f7d (not in raw/)"
last_reviewed: 2026-11-04
---
# QA report: S02 localhost demo (Research Map / `rmap`)

## Verdict: ship for the demo with caveats (no blocker)
Everything the demo depends on works and matches the golden set when checked over the HTTP API. That covers 10/10 findings with the exact file:line, 2 unapproved proposed links, A1/A2, the eval.py revert, approval states 1 and 2, the new-checkpoint state 3, and triage after a restart. The 33 unit tests pass on Python 3.13 and on Python 3.10. Builds are byte-identical across three runs. The tool works fully offline. The localhost guards hold and the exported report opens offline.

Fix before the talk: D1 (the UI disappears below 1280 px, which includes browser zoom) and D2 (the UI says "linked by you" about a link the author has not approved). PM must also update the walkthrough script (section 5). Merging to main still needs Juhyeong's approval.

## 1. What was run
| Step | Command / method | Result |
|---|---|---|
| Clean install | `python3 -m venv /tmp/qa-venv && /tmp/qa-venv/bin/pip install -e app` | OK, 4.3 s; `rmap --version` -> `rmap 0.1.0` |
| Demo (pip) | `rmap demo --no-open --dir /tmp/qa-sample --port 8790` | URL printed 0.35 s after launch |
| Demo (uv, documented) | `uv run --project app rmap demo --dir /tmp/qa-uv-sample --port 8790` (8790 busy; `UV_PROJECT_ENVIRONMENT` pointed to /tmp so the repo stayed untouched; `$BROWSER` stub) | fell back to 8791, printed URL correct, browser stub received `http://127.0.0.1:8791` |
| Python 3.10 | `uv python install 3.10` (3.10.20); tests and `uv run --python 3.10 ... rmap demo` | 33/33 tests OK (5.1 s); demo serves; all GET routes 200 |
| Tests on 3.13 | `PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_*.py'` | 33/33 OK (4.5 s) |
| Zero-install fallback | `PYTHONPATH=app/src python3 -m rmap demo --no-open ...` | serves |
| Ctrl-C | demo in a pty, send `^C` | prints `rmap: stopped`, exits |
| Browser | Playwright Chromium, 1440x900, deviceScaleFactor 1 | 0 console errors, 0 non-localhost requests, 0 failed requests |
| Offline | `unshare -n` (loopback only): build, scan, serve, UI, analyze, export | all work; strace shows 0 `socket()` calls for build+scan+analyze+checkpoint |

Performance: the graph draws 0.9 s after page load on the sample and 0.74 s on the real repo. Rescanning the sample takes under 0.3 s. Scanning the real repo with `rmap scan` takes 0.63-0.71 s wall time (target is under 10 s). Every UI action finished in under 1 s.

## 2. Golden set (fresh sample; checked over the HTTP API, not through the engine tests)
I read the expected line numbers by hand from the generated `paper/main.tex`, `paper/appendix.tex` and `paper/refs.bib`.

| Item | Expected | Actual (`/api/findings`, `/api/graph`, `/api/alarms`) | Result |
|---|---|---|---|
| F01 | `reference_unmatched/smith2021ghost`, refs.bib:21 | refs.bib:21 | pass |
| F02 | `main_appendix_mismatch/learning_rate`, main.tex:33 (3e-4) vs appendix.tex:7 (1e-3) | same | pass |
| F03 | `main_appendix_mismatch/batch_size`, main.tex:33 (64) vs appendix.tex:8 (128) | same (listed before F02; the engine orders by id) | pass |
| F04 | `uncited_reference/unused2019`, refs.bib:26 | refs.bib:26 | pass |
| F05 | `unreferenced_float/fig:arch`, main.tex:29 | main.tex:29 | pass |
| F06 | `unreferenced_float/tab:ablation`, main.tex:77 | main.tex:77 | pass |
| F07 | `undefined_ref/fig:missing`, main.tex:61 | main.tex:61 | pass |
| F08 | `undefined_cite/nobody2020`, main.tex:21 | main.tex:21 | pass |
| F09 | `untraced_number/tex:sec:results#92.4`, main.tex:48 | main.tex:48 | pass |
| F10 | `figure_without_provenance/tex:fig:qual`, main.tex:72 | main.tex:72 | pass |
| Count | exactly 10 | 10; all 8 checks `ran` | pass |
| Evidence text | equals source line | 10/10 finding lines and 51/51 edge-evidence lines equal the file (independent script) | pass |
| PL1, PL2 | exactly 2, `proposed`, `propagates: false` | `tex:sec:setup\|value_match\|...default.yaml`, `tex:app:hparams\|value_match\|...default.yaml` | pass |
| A1 | cause code K3 `configs/default.yaml`; changed `file:code/configs/default.yaml`; downstream `run:code/train_main`, `file:code/results/table2.csv`, `tex:tab:main` | cause 2836100; downstream depths 1/2/3; table2.csv `output_identical: true` | pass |
| A2 | cause paper P3 `appendix.tex`; changed `tex:app:hparams`; 0 downstream | cause 02c7676; exact | pass |
| eval.py K4+K5 | nothing raised | events 93e7978 and 784a21a list `file:code/eval.py` in changed_nodes; no group | pass |
| State 1 (approve PL2) | A1 downstream 4 (+ `tex:app:hparams`) | 4, via the approved `value_match` edge | pass |
| State 2 (approve PL1 too) | A1 downstream 5 (+ `tex:sec:setup`) | 5 | pass |
| State 3 (new checkpoint) | 0 groups, findings unchanged | cp2, 0 groups, findings byte-equal | pass |
| Triage after restart | unchanged | `rmap demo --keep` restart: 3 entries, notes and link decisions unchanged | pass |

Commit SHAs for `golden.json` (same on all three builds): paper P1 296ce7e, P2 92a5afd (cp1), P3 02c7676; code K1 fe00549, K2 4470a61 (cp1), K3 2836100, K4 93e7978, K5 784a21a. The code SHAs differ from the pipeline handoff (460abec / 17acc92b), most likely because the rename changed the committed run-record schema string. The paper SHAs are unchanged.

## 3. Acceptance criteria
| AC | Status | Evidence |
|---|---|---|
| US-01.1 | pass (Linux) | URL printed in 0.35 s (pip) and 0.40 s (uv); not timed on a Mac |
| US-01.2 | pass (Linux) | `$BROWSER` stub opened the printed URL; `--no-open` suppresses it |
| US-01.3 | pass | everything works in a namespace with no outside network; 0 foreign requests |
| US-01.4 | pass | 8790 busy -> 8791, printed URL correct |
| US-02.1 | **fail as written** | bands are Thesis, Questions, Sections, Paper items, Repo results, **Runs, Code**; the spec says code before runs (the contract puts runs at layer 5 and code at 6) |
| US-02.2 | pass | Table 2 panel: kind, `paper` chip, main.tex:49, Rests on 4 / Supports 4 |
| US-02.3 | pass | Trace down from Table 2 highlights table2.csv, the run, train.py and the config; Trace up from train.py reaches Thesis |
| US-02.4 | partial | toggle shows/hides 6 reference nodes; citation edges appear only when a citing node is selected (0 drawn on toggle) |
| US-02.5 | partial | cross-repo edge Table 2 -> results/table2.csv is in one graph; graph nodes carry **no repo label** (the repo shows only in the side panel) |
| US-03.1 | pass | "Set checkpoint" stored cp2: 33 hashes, timestamp, note |
| US-03.2 | pass | cp1 stays listed under cp2 and cp3 |
| US-03.3 | pass | "Nothing to recheck since CP2"; the API returns 0 groups |
| US-03.4 | pass | CP1 seeded, 2026-10-01T18:00:00+09:00 |
| US-04.1 | pass | A1 and A2 only (section 2) |
| US-04.2 | pass | eval.py never appears in alarms or alarm UI |
| US-04.3 | pass | header: short SHA, subject, repo, date, files; "Show in graph" highlights the 4 A1 nodes |
| US-04.4 | pass | rows read "changed" vs "downstream (depth n)" |
| US-04.5 | pass | no sockets (strace); `/api/ask` returns 501 |
| US-04.6 | pass | proposed edges have `propagates: false`; A1 has 3 downstream nodes |
| US-05.1 | pass | chain: config -> run train_main -> results/table2.csv -> Table 2 |
| US-05.2 | pass (note) | diff `learning_rate: 3.0e-4` -> `1.0e-3` with file name and hunk `@@ -1,4 +1,4 @@`; no explicit `file:line` label |
| US-05.3 | pass | request log shows no `/api/analyze` call until Analyze is clicked |
| US-05.4 | pass | `ai.available: false`; button reads "Ask Claude why — not available in this demo" |
| US-06.1 | pass | state and note written to `.rmap/triage.json` (UI and API) |
| US-06.2 | pass | unchanged after restart |
| US-06.3 | pass (API) | editing Appendix B gives `unreviewed` + `outdated: true` with history kept; reverting restores `reviewed` |
| US-06.4 | pass | filter buttons show Recheck 3, Needs fixing 1, Reviewed 1; the "Needs fixing" filter lists only Table 2 |
| US-06.5 | pass | 0 non-localhost requests in the whole walkthrough |
| US-07.1 | partial | exactly 2 proposed links, counted in no alarm; **not drawn on load**; drawn dotted with a "Proposed" label only when an end node is selected or with Show: Proposed links |
| US-07.2 | pass | Approve -> `approved`, `propagates: true`, alarms in the same response, stored |
| US-07.3 | pass | Reject -> hidden, stored, still `rejected` after rescan; Restore works |
| US-07.4 | pass | App. B joins A1 (depth 1, "link approved by you") |
| US-08.1 / .2 / .3 | pass | refs.bib:21 / refs.bib:26 / main.tex:21 |
| US-08.4 | pass | no request without `--online`; with `--online` and no network, lookups are stored as `error`, not `not_found` |
| US-08.5 | pass | the 4 cached, cited keys raise nothing |
| US-09.1-.4 | pass | main.tex:29, :77, :61; no other F05-F07 |
| US-10.1-.4 | pass | side-by-side main.tex:33 / appendix.tex:7 and :8; Adam raises nothing; buttons "§4 Experimental Setup -> graph" and "App. B Hyperparameters -> graph" |
| US-11.1-.3 | pass | main.tex:48, main.tex:72; 0.871 and fig:curve raise nothing |
| US-11.4 | **fail** | numbers are not nodes, so a traced number cannot be clicked; the path is reachable only from the Table 2 node |
| US-12.1 | pass | every card shows path:line; the evidence pane quotes the line |
| US-12.2 | pass | 0 banned words in engine/server/web source, hub JSON, rendered UI text and the export |
| US-12.3 | pass | triage control and "-> graph" in the finding panel |
| US-12.4 | pass | one 622 KB HTML file; opens from `file://` offline; read-only (controls disabled, "Read-only snapshot"); 0 console errors |
| US-13.1 | partial | code-only open works without errors (242 nodes); the repo has no run records or tracked results, so none can be shown; README items appear in a "Paper items" band |
| US-13.2 | pass (weak) | all 8 checks say "Not applicable (no paper repo)", but only inside a collapsed "Status of all 8 checks"; the headline says "0 findings" |
| US-13.3 | not testable | no Overleaf zip. Partial check: adding `--paper` to a copy keeps all 242 code nodes and 481 edges unchanged |
| US-13.4 | pass | `git status` clean, `.rmap/` self-ignored, `GIT_OPTIONAL_LOCKS=0`, no file outside `.rmap/` written |
| US-14.1 | pass | 3 builds (pip 3.13, uv 3.13, uv 3.10): identical trees, SHAs, hub JSON (volatile fields excluded) and blobs |
| US-14.2 | pass | two git repos, fixed committer dates |
| US-14.3 | pass | F01-F10 once each; negative controls raise nothing |
| US-14.4 | pass | stdlib imports only; `GIT_CONFIG_GLOBAL=/dev/null`; writes only into the target folder |

## 4. Safety and privacy
| Check | Result |
|---|---|
| Bind | 127.0.0.1 only (`/proc/net/tcp`); connecting via host IP 192.0.2.2 is refused |
| Host header | `evil.com`, `evil.com:8790`, `127.0.0.1` (no port), wrong port -> 403; `localhost:<port>` -> 200 |
| POST Origin | foreign origin, `null`, `localhost:<other port>` -> 403; `text/plain` or form body -> 400; 70 KB body -> 413; no CORS headers; OPTIONS -> 501 |
| `/api/file`, `/api/raw` | `../`, `..%2F`, `../../../etc/passwd`, absolute, `//`, NUL, unknown repo, symlink to /etc/passwd, symlink to `.rmap/triage.json`, dir symlink to `.rmap`, `loop/.rmap/...`, direct `.rmap/...` -> all refused. **Served: `.env`, `.git/config`** (D6) |
| Static | traversal (`/../`, `%2e%2e`, `..%2f`) -> 404 |
| Network | 0 sockets without `--online` (strace); full UI works inside `unshare -n` |
| User repo | sample and real repo `git status` clean; `.rmap/` ignored via its own `.gitignore` |
| `rmap demo --dir` | refuses to delete a folder without `.rmap-sample` (the file inside was kept) |

## 5. Walkthrough (demo-spec, click by click) — mismatches for PM
| Time | Spec says | What exists |
|---|---|---|
| 0:00 | browser opens at the localhost URL | opens `http://127.0.0.1:8765`; the command is `uv run --project app rmap demo` (there is no `./demo.sh`). The setup step "delete the state directory" is unnecessary: `rmap demo` rebuilds fresh unless `--keep` |
| 0:30 | "thesis, RQs, sections, figures/tables, result files, code, runs"; separate repos in one graph | bands read Thesis, Questions, Sections, Paper items, Repo results, **Runs, Code**; nodes carry no repo label to point at; section nodes are not in paper order (§3, App. A, §1, §2, §5, …) |
| 1:00 | Table 2 -> "trace down"; train.py -> "trace up" | works; buttons are in the side panel. After Trace down the toolbar shows "▲ Rests on" pressed (arrow points up) |
| 1:30 | toggle "references": citations appear | the `References` button shows a reference column; citation edges appear only after clicking a citing section (e.g. §1) |
| 1:45 | open Checkpoint panel; "Alarms show 2 groups" | top bar `Checkpoint: CP1 ▾` popover; the Alarms tab badge shows **5** (items); "5 items in 2 groups" is visible only in the Alarms tab |
| 2:15 | alarm A1 "learning rate changed in config" | A1 is labelled with the commit subject "change learning rate 3e-4 to 1e-3"; lists the changed config plus 3 downstream |
| 2:45 | eval.py not listed | true |
| 3:00 | Analyze on A1 | `Analyze` on the A1 header; chain + diff + explanation shown |
| 3:30 | "open the dashed link PL2 in the graph, click Approve" | **no clickable or visible dashed link in the graph**. Use the `Links` tab, row "App. B Hyperparameters -> configs/default.yaml", `Approve`, then go back to `Alarms` to show App. B in A1. No "PL1/PL2" labels exist |
| 3:50 | Table 2 "needs fixing" + note; App. B "reviewed" | in Alarms select the row, type the note in the right panel **first**, then click `✕ Needs fixing` (otherwise use `Save note`); `✓✓ Reviewed` for App. B; counts update |
| 4:10 | "Open Findings, click F02" | the tab is **`Checks`**; there are no F-numbers; F02 is the **3rd** card ("Learning rate differs…") after batch size; click `Open evidence`, then "§4 Experimental Setup -> graph". The side panel then shows the D2 text |
| 4:30 | open F01 and F09 | 1st and 9th cards (scroll) |
| 4:50 | Export HTML report | top bar `Export HTML report` (the Checks tab also has "Export report (HTML)" for the same action); the browser saves `sample--tiny-transformer-report.html`, which opens offline |
| runbook (arch §8) | "edit `configs/default.yaml`, Rescan -> a worktree alarm group" | **no new group**: the config already changed in K3, so the edit goes into A1's `also_changed_in`. Editing `train.py` does create A3 "Uncommitted changes" |

## 6. Real repository (`/home/claude/alarm-analyzer-eval` @ baa9f7d, code-only)
- `rmap scan`: 242 nodes (203 code, 16 README items, 13 doc, 8 data, 2 config), 481 edges (448 imports, 29 generated_by, 4 produced_by), 113 events (first-parent; 114 commits in total), 0 findings, 0 alarm groups (no checkpoint), 0 warnings. Wall time 0.63-0.71 s. This matches the handoffs.
- `rmap open --port 8795`: served in 0.73 s; UI loads with 0 console errors and 0 foreign requests. The graph draws 29 elements (folders collapsed). Alarms say "Set a Last known good checkpoint…". Checks show 8 x not applicable.
- README provenance: 16 items (Fig. 1, 3-10, Tables 1, 2, 3, 5, App. B, D.1, F). All 29 `generated_by` targets exist and match the README rows. Example: **Fig. 7 -> `experiments/RQ3_consistency/f4_combined.py` is correct**, and Fig. 8/10 -> `RQ3_consistency/f6_operating_point.py` + `f5_windows.py` is also correct. Eight of the 29 come from parenthetical helper mentions ("label-built predictions", "window re-fits", "variants") but are labelled "is generated by", the same as the main script (D13).
- `git status` stays clean. **`.rmap/` was not removed.** It was created at 14:12 by a server I did not start (PID 2410, `python3 -m rmap open /home/claude/alarm-analyzer-eval --port 8766`, cwd the lemmata repo) and was rewritten by the unit tests (D8). Deleting it under a running server would break that server. Stop PID 2410 first, then `rm -rf /home/claude/alarm-analyzer-eval/.rmap`.

## 7. Precision and false positives
- Sample checks: 10/10 true positives, 0 false positives; all negative controls raise nothing.
- Reference checker: 1/1 on the sample, but only because the cache is seeded (`source: seed`). **Precision on real references is unmeasured**: OpenAlex/Crossref were not reachable here, and the online path has only been tested for failures (recorded as `error`).
- No-change message flag on the real repo: 24/113 commits flagged ("no-op" 13, "byte-identical" 9, "no change" 1, "nothing moved" 1). Reading each message, about 19/24 are real "outputs did not change" claims. Five are not: "not a no-op", "rather than a no-op", "no-op-while-alive", "needed NO change", and "note string is byte-identical to …". The flags only show as "Low confidence" in alarms, which needs a checkpoint.
- README provenance: 29/29 edges point at the files the README names (see D13).

## 8. Defects, most severe first
| # | Severity | Defect | Reproduction |
|---|---|---|---|
| D1 | Medium (demo risk) | Below 1280 CSS px the whole UI is replaced by "needs a window at least 1280 px wide". That includes browser zoom: 125% on a 1440 px screen is 1152 CSS px. At 1280x720 the top-bar buttons are clipped and the legend overlaps the Code band | Open the app in a 1279x800 window (or zoom to 125% at 1440 px) -> notice only. Screenshots `6x-viewport-*.png` |
| D2 | Medium (wording, visible at 4:10) | The side-panel Evidence says "§4 Experimental Setup was linked by you to configs/default.yaml (proposed)" for an **unapproved** heuristic link. `app.js` `evidenceFor()` applies `EDGE_PHRASE.value_match` ("was linked by you to") whatever the status | `rmap demo` -> Checks -> "Learning rate differs…" -> Open evidence -> "§4 Experimental Setup -> graph" -> Evidence section |
| D3 | Medium (walkthrough) | Proposed links are not shown or clickable in the graph on load (US-07.1 partial), so walkthrough step 3:30 cannot be done as written | Load the app; 0 edges are drawn; edges have no tap handler |
| D4 | Low-Medium | Graph nodes have no repo label (US-02.5; arch §3.4 says "Each node shows its repo badge") | Load the graph; labels are glyph + name only |
| D5 | Low | Band order puts Runs above Code; spec and script say code, then runs (US-02.1). Needs a PM/CTO decision | Load the graph |
| D6 | Low (hardening) | `/api/file` serves any file under a repo root, including hidden ones. Same-origin only (Host check, no CORS), but the route is not in the contract. Suggest limiting it to graph-node paths | `curl "http://127.0.0.1:<port>/api/file?repo=code&path=.git/config"` -> 200 |
| D7 | Low (macOS only, from reading the code) | `safe_path` excludes `.rmap` by exact-case path part. On the Mac's default case-insensitive disk, `path=.RMAP/triage.json` would probably be served for a repo at path `.` | Not reproducible on Linux; check on the Mac |
| D8 | Low (process) | `TestRealRepoSmoke` scans `/home/claude/alarm-analyzer-eval` in place and leaves `.rmap/` there (S02-03 AC8 says "on a copy") | Run the test suite; `.rmap/*.json` mtimes update |
| D9 | Low (doc) | The runbook's "edit default.yaml -> worktree alarm group" moment does not happen (section 5) | Edit `code/configs/default.yaml`, Rescan -> still 2 groups |
| D10 | Low (wording) | The "✓ Confirmed" chip marks nodes that are merely unchanged since the checkpoint; §4 shows "Confirmed" while it has F02/F03. Design question | Select §4 in the graph |
| D11 | Low | Code-only mode: the Checks headline says "0 findings … from the checks that ran" when none ran; the outline says "No sections found. Check that your main .tex file uses \section" | `rmap open <code repo>` -> Checks, outline |
| D12 | Low | No-change flag false positives (section 7); the flag text reads "content changed in 1 files" | Real repo events e.g. 1c479d7, d1c8370 |
| D13 | Nit | README helper scripts are shown as "is generated by"; findings show F03 before F02; the reference check note says "offline cache" even with `--online`; export filename has a double hyphen | as described |

## 9. Not testable here
macOS specifics: launch time under 5 s, the default browser opening, the case-insensitive `.RMAP` path (D7), and port behaviour next to macOS services. Also untested: projector resolution, real OpenAlex/Crossref lookups (no network), Overleaf zip paper -> code links (US-13.3), and presenter timing per walkthrough step.

## 10. Open items on the S02-03 card
- AC1 `app/tests/golden.json` was **not written** in this pass; the caller did not ask for it. The section 2 table and SHAs are ready to turn into it on a feature branch.
- AC2-AC8 are covered above. AC9: the mismatches in section 5 and D3/D5 go to PM.

Screenshots: `/tmp/qa-shots/` (01-22 walkthrough, 30-34 offline export, 40-44 real repo, 50 offline, 6x viewports).
