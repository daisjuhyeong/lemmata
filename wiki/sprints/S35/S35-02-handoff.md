---
type: handoff
owner_agent: lead
status: needs-qa
sources:
  - "S35-02-task.md (the acceptance lines) ; ../../decisions/ADR-011-vscode-is-the-experiment-bench.md"
  - "code on branch s30-baselines: app/src/lemmata/engine/{bench,api}.py, app/src/lemmata/{server.py,hub/routes.py}, app/src/lemmata/web/{app.js,research.js,app.css}, app/tests/test_bench.py"
  - "code on branch s30-baselines: vscode/src/{extension,runs}.ts, vscode/src/core/{bench,client}.ts, vscode/media/vscode.css, vscode/package.json, vscode/README.md, vscode/test/{unit/bench.test.ts,unit/capture.test.ts,integration/views.test.ts,integration/hub.test.ts,e2e/tab.test.ts,host/suite.ts}, vscode/lemmata-0.8.0.vsix"
  - "https://code.visualstudio.com/api/references/commands (read 2026-11-20): workbench.extensions.installExtension takes a VSIX resource uri"
  - "test runs on 2026-11-20 in the cloud workspace: Python 234 passed, 2 skipped; extension unit 78, integration 24, browser 10 passed; the extension-host smoke test could not run (VS Code cannot be downloaded there)"
  - "screenshots/ and lists-sample-project.txt in this folder"
last_reviewed: 2026-11-20
---
# S35-02 handoff: VS Code is the experiment bench (extension 0.8.0)

## What changed for the researcher
- **Three lists** in the Lemmata side bar: **Now** (the runs on this machine, grouped), **Experiments** (claim →
  experiment → its setup, one line each) and **To run** (collapsed). The old "Alarms and findings" and "Runs" lists
  are gone. What the lists look like for the sample project: [lists-sample-project.txt](lists-sample-project.txt).
- **One status-bar item**: `2 running · 1 not sent · 3 to run`; when a run ends, `fp 30, was 31.2 (lower is better) ·
  Main comparison` for five minutes.
- **Eight commands** in the palette, and **Lemmata: Go to…** for everything else, including every website page.
- **The tab shows Setup and Thesis only.** Every other page opens in the browser, on that page.
- **The map keeps its lines** in a narrow window and scrolls sideways
  ([600 px](screenshots/map-600.png), [scrolled right](screenshots/map-600-scrolled-right.png),
  [1280 px, as before](screenshots/map-1280.png)). **Open the Map (large)** shows the map alone in a full tab; Go to… →
  **Map in its own window** moves that tab out.
- **Attach to an Experiment…** on a run, and **Snooze…** on a to-run item.
- **The extension offers its own update** when the hub holds a newer one.

## How it is built
| Part | Where | Notes |
|---|---|---|
| The rows | `engine/bench.py`, `Engine.bench()` | Built from the experiments, Setup, the to-do list, the planned experiments and the logged runs. Every row has id, label, description, tooltip, icon name and what it offers (`open`, `site`, `tab`, `copy`, `snooze`). No new rules; no model |
| Run → experiment | `Engine._runs_of()` | The linking that Setup already did, moved into one helper used by Setup and the bench. A run attached by hand counts for that experiment only |
| Attach | `bench.json`, `POST /bench` | `{action: "attach", run, experiment}`; an empty experiment takes it back |
| Like with like | `bench.link_runs` | Same experiment, same fields, same measure. With no field in the pattern, the same command line |
| To run | `bench.TO_RUN` | The to-do kinds about running something. Gaps (`seeds`, `setup_*`) only for experiments that test a claim. A plan carries its own prompt; other items carry a short prompt that names `experiment_brief` |
| Bench-only tab | `web/app.js` (`BENCH_PAGES`, `openOnSite`) | Decided on the hub, so it also applies to an extension that is still 0.7.0 |
| Website links | `web/app.js` `goFromLink` | `<hub>/p/<pid>/#go=<page>&sel=<q:… \| x:… \| i:…>`; read whether or not `=` and `&` arrive percent-encoded |
| The map | `web/research.js` (`.bd-sc`, `RX.suMap`), `web/app.css` | Below 760 px the board keeps a width of 720 px inside a frame that scrolls |
| The lists | `vscode/src/extension.ts` (`RowTree`, `Controller`), `vscode/src/core/bench.ts` | The extension checks every row the hub sends (text cleaned, paths that leave the repository refused, tooltips plain text), adds the local runs, and draws |
| Update | `hub/routes.py` `extension_build`, `GET /api/hub/extension.vsix`, `Controller.checkExtension` | The hub offers only a packaged file whose name carries the version in `vscode/package.json`. Signed-in devices only. The extension installs it with `workbench.extensions.installExtension` after the researcher clicks Install |

## Acceptance, line by line
| # | Result | Shown by |
|---|---|---|
| 1 | met | `test_bench.py::test_runs_are_tied_to_their_experiment_and_compared_like_with_like`, `::test_to_run_holds_only_what_is_about_running_something` |
| 2 | met | same test: another dataset and another seed give no "was" |
| 3 | met | `::test_a_run_can_be_attached_by_hand_and_that_counts_at_once`; route test; `views.test.ts` "Attach" |
| 4 | met | `bench.test.ts` "nowRows"; `views.test.ts` "Now" |
| 5 | met | `::test_experiments_carry_their_setup_one_line_each`; `views.test.ts` "an experiment that tests two claims" |
| 6 | met | `::test_a_planned_experiment_carries_its_run_prompt`; `views.test.ts` "To run" (snooze through the real hub) |
| 7 | met | `bench.test.ts` "the command palette shows at most 8", "every contributed command is registered" |
| 8 | met in the stand-in | `bench.test.ts` "barOf", "flashOf"; `views.test.ts` "a run that ends" |
| 9 | met | `tab.test.ts` "Setup and Thesis switch in the same tab; every other page opens on the website" |
| 10 | met | `tab.test.ts` "the map keeps its lines in a narrow tab" (420 px); screenshots at 600 px |
| 11 | met | same test |
| 12 | met on the hub side; the install itself not run | `test_bench.py::ExtensionBuildTest`; `hub.test.ts` "the hub names the extension it can hand out"; `bench.test.ts` "newer" |
| 13 | met | see the test runs in the sources |

## Not verified
- **In a real VS Code window.** VS Code could not be downloaded in the workspace, so the extension-host smoke test
  did not run. The whole extension was run against a real hub with a stand-in for the VS Code API
  (`vscode/test/integration/views.test.ts`): activation, the three lists, every row action, Go to…, the status bar.
  What a stand-in cannot show: how the lists look, the inline icons on a row, the badge on the side-bar icon, the
  welcome texts, moving the map to its own window, and installing the update. **First thing to check on a real machine.**
- **Remote-SSH.** The update writes the file on the machine the extension runs on and hands VS Code its path. That
  this installs on the server side over Remote-SSH is not confirmed.
- **The map's lines in a real editor theme.** The headless browser has no VS Code theme colours, so the lines are
  counted in the test, not seen. They now take the editor's text colour at 55% so no theme can hide them.
- **On the Mac mini, on `mcd_extension` and `temporal_dependency`.** Nothing here ran against the real hub or real projects.
- **How long the bench request takes on a real project.** On the fixture it is 0.06 s. It builds Setup and the to-do
  list, as the website's Home does. The extension asks every 30 s only while its window is in front, and at most once
  in ten seconds on focus.

## What was removed from VS Code
The "Alarms and findings" list, the warnings in the Problems panel, Mark Reviewed / Needs fixing / Ignore, Why?, Set
checkpoint, Open in the browser, the seven "Open …" commands, Show runs, Refresh runs, Open the run record (now a click
on a run). All of these exist on the website. `vscode/src/core/{model,load,why}.ts` and their tests are kept but
unused (ADR-011, Consequences).

## Open
1. A browser test for Home, Review and the Trail on the website: they were only tested through the tab.
2. The next card (S35-01 phases 2 and 3): lines above result files and configs, Compare in the diff editor, Problems
   entries for experiment issues, a walkthrough, the start signal for overnight jobs.
3. S30-brief's open item "the VS Code extension has no command for the Baselines page" is closed by ADR-011: Baselines
   is a website page, reached from Go to….
4. QA has not reviewed this.

## To use it
1. The hub updates itself if it follows `next` (`uv run lemmata hub autoupdate install --branch next`, once, on the Mac mini).
2. Install 0.8.0 by hand this one time, on each machine where you run experiments (with Remote-SSH, in the remote window):
   `code --install-extension vscode/lemmata-0.8.0.vsix`. Later versions are offered by the extension itself.
