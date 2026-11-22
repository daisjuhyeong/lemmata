---
type: qa-report
owner_agent: qa
status: re-check 2026-11-22 — line 7 PASS, line 9 fix PASS with one low issue; suite 241 OK; merge waits only on the handoff (and Juhyeong)
sources:
  - "S36-01-task.md (acceptance lines 1-9)"
  - "../../design/screens/S36-design-system.md §4-5"
  - "working-tree diff on s36-design-system against ec3c249: app/src/lemmata/web/{tokens.css,app.css,app.js,research.js}, desktop/launcher/tokens.css, new app/tests/test_s36_ui.py"
  - "vscode/media/vscode.css (loads after app.css, vscode/src/core/embed.ts:81)"
last_reviewed: 2026-11-22
---
# QA: S36-01 phase 1 (tokens and parts)

QA read the code and ran the tests. Per the founder, no browser or VS Code extension checks were run: this machine has no browser and no node.

## Test run
`PYTHONPATH=app/src app/.venv/bin/python -m unittest discover -s app/tests -p 'test_*.py'`, run outside the sandbox because the sandbox blocks local port binding (inside it, test_sidecar fails on EPERM).
- **Ran 204, errors 4, failures 0, skipped 2. That leaves 198 passing.**
- The 4 errors are `ModuleNotFoundError: pytest`. test_map.py:5 imports pytest. test_baselines (:21), test_texout (:18) and test_bench (:16) import test_map, so they fail too. pytest is not in app/.venv. None of these four files, nor `lemmata/engine`, has changed since bc26f66 (`git diff --quiet bc26f66 --` holds). The errors therefore come from before this change. Note that the S35 handoff reports 234 passing, so this venv is not the one used for S35.
- test_s36_ui: 7/7 pass. `test_launcher_copy_matches` and `test_tokens_define_the_dais_palette` pass.

## Per line
| # | Verdict | Evidence |
|---|---|---|
| 1 | PASS | tokens.css:11,23-25,27,33 (light) and :65-68 (dark) match the card exactly. Only the two comments the design page asks for changed. No renames. `cmp` with desktop/launcher/tokens.css shows the files are identical |
| 2 | PASS | test_s36_ui.py computes what the card asks for: 4 foregrounds × 4 surfaces × 2 themes; on-highlight; 4 colours at ≥3:1 on --bg; a luminance gap of ≥0.15. QA recomputed with its own code: --muted on --bg-2 4.53 (tight), on --bg 5.08; on-highlight 10.47 / 8.21; edge 4.41 / 8.30; warning 3.28 / 5.21; luminance gap 0.32 light / 0.18 dark. These match §4. The test uses the old 0.03928 linearisation threshold, which makes no difference here |
| 3 | PASS, needs a handoff note | `var(--highlight)` appears only in app.css:555, 591, 610, 611 and 718, and each rule has a `--highlight-edge` border. app.js and research.js have no inline uses. **Deviation:** `.hf-branch.warn::before` (app.css:1034) went from sand to `--warning` and left the allow-list. The card lists it as a your-turn dot, but §5 allows the change for a dot that only means "look here". research.js:2148 shows it means "another branch has newer commits", so the change is right, but the handoff and design page must say so. The test checks only app.css, not inline styles in the JS (both are clean today) |
| 4 | PASS on the code, handoff missing | 10 primary sites remain: app.js:1637 (approve proposed link), research.js:159 (accept suggested link), :208 (Confirm claim), :712 (Confirm proposed map), :2067 (accept proposed hypothesis changes), :2075 (Confirm problem), :2122 (Confirm hypothesis), :2233 (Confirm proposed numbers), :2324 / :2359 (Confirm baseline card / all). Each one settles something that waits on the researcher. 28 sites became plain: Close/Save/Cancel modals, Ask, Copy prompt ×6, Next, Try again, Start tracking, Add dates, Fill in/Edit. **The card says 13 sites, but bc26f66 had about 38** once the `primary: true` modal buttons (app.js:192) are counted. No S36-01-handoff.md exists yet, so the list the card requires is missing. More than one sand button can show on one page (Baselines: "Confirm all" plus a per-card Confirm; Hypotheses: Problem, each hypothesis, Accept change), but they all sit among waiting items, which the card allows |
| 5 | PASS (static) | app.css:586 sets weight 600, `--fs-tag` and `--text-secondary`. :587 makes the dot 8px with a transparent fill and a 1px `--muted` ring. :592 and :595 make ign/plain/hypothesis/exploration hollow. No later `.chip` rule overrides these (:883 only adds lk- colours). Whether the state word always shows needs a browser |
| 6 | PASS, handoff must list exceptions | No `--muted-light` is left in app.css, app.js or research.js (#status :527, .sg.ok :604 and .hf-tag :1008 now use `--muted`). --fs-11 and --fs-12 are 13px (app.css:2; 118 uses). The sub-13px literals left are :355 `.rx-chk .cg`, :401/:451 `.rx-m-g`, :709 `.rxt-caret` and :750 `.rh .caret`. Carets are decoration. `.rx-m-g` sits beside words (research.js:48-49, 804). `.cg` (research.js:623) is a cell verdict glyph whose meaning lives only in the title and legend, so it is borderline. The handoff must list all four |
| 7 | **FAIL** | `.btn` :607, `.chip-btn` :625 and the generic inputs :627-628 are correct. But `.rx-pl-f input, .rx-pl-f textarea` (app.css:828) has the same specificity as `input[type=text]`, comes later, and keeps `--border` (a hairline) and a `--bg` fill. The plan-form inputs therefore miss the rule. `.chip-btn.st-*` (:626) keeps `--border-strong`; that is a chosen state, so it is acceptable. Hairlines are untouched |
| 8 | not checked (founder skipped) | — |
| 9 | Static check PASS with two small changes; suites not checked (founder skipped) | In the tab, `html.embed .btn.primary` (0,3,1) gets a transparent background from app.css:613 and its text and border colour from vscode.css:56. Both beat `.btn.primary` and `:hover` (0,3,0), so the outlined look holds. The hollow ring holds because vscode.css does not touch `::before`. Changes the tab will show: (a) `.chip` is now weight 600 there too, because vscode.css:49 sets only size and colour; (b) a plain `.btn` edge is now `--muted` (descriptionForeground) where it used to be the panel border; (c) primary buttons lose their hover fill, because :613 forces it transparent where it used to be `--surface-hover` |

Cascade: the `.btn.primary` rules at :25 and :414 were removed, so only :610-613 define it, and nothing later overrides it except `.btn:disabled` (:614), which correctly drops the sand from a disabled primary. `.btn[aria-pressed=true]` stays the same in all three layers (:25, :413, :609) and looks as before.

## Regressions
- Braces balance in app.css and tokens.css. The JS hunks only remove ` primary`, `primary: true, ` or `' primary'` and leave the syntax intact. One rewritten ternary simplifies cleanly: research.js:975 and :988 now always use `'btn sm'`.
- No hex or rgb colour was added outside the token files (grep of the added lines; test_no_hex passes).

## Defects, by severity
1. **Medium, blocks merge:** line 7. Give `.rx-pl-f input, .rx-pl-f textarea` (app.css:828) a 1px `--muted` edge and a transparent background.
2. **Medium, blocks merge:** S36-01-handoff.md is missing. It must list all ~38 primary sites with the choice and a reason (line 4), the glyph-only size exceptions (line 6), and the `.hf-branch.warn` → `--warning` change (line 3). The design page must also be updated for that change.
3. Low: VS Code tab changes (chip weight 600, plain-button edge colour, no hover on primary). Either accept them in the handoff or add `html.embed .chip { font-weight:400 }` and a hover rule in vscode.css. The latter would change the extension's files and so its version (line 9).
4. Low: `.rx-chk .cg` carries information below 13px with no word beside it.
5. Low (test): `--muted` on `--bg-2` passes at 4.53:1, just above the 4.5 floor. The allow-list test does not scan inline styles in the JS.

## Re-check (2026-11-22, after the lead's two fixes)
| Fix | Verdict | Evidence |
|---|---|---|
| Line 7: `.rx-pl-f` inputs | **PASS** | app.css:830 now has `border:1px solid var(--muted)` and `background:transparent`. In the tab, vscode.css `html.embed input[type=text]…` (0,2,2) still beats `.rx-pl-f input` (0,1,1), so the editor's input colours hold there |
| Line 9: embed rules at app.css:613–614 | **PASS, one low issue** | `html.embed .btn.primary` (0,3,1) has a transparent fill. `:hover` (0,4,1) has `--surface-hover`, as at bc26f66. vscode.css:56 `html.embed .btn.primary` (0,3,1) comes later and has more specificity than app.css `html.embed .btn` (0,2,1) and `.btn.primary:hover` (0,3,0), so it still sets the border and text colour. `html.embed .chip` (0,2,1) beats `.chip` and resets the weight to 400. vscode/ is untouched (`git status vscode/` is clean), so the extension version does not change |
| New issue (low) | in the tab only | `html.embed .btn { border-color:--border-strong }` (0,2,1) also beats `.btn[aria-pressed="true"]` (0,2,0). At bc26f66 a pressed toggle had an `--accent-dark` edge in the tab; now its edge is the panel colour. It applies to app.js:1775–1779 (graph toggles) and research.js:2407 (theme). Triage `.tri .btn[aria-pressed].s-*` (0,4,0) is not affected. Those pages are probably not in the bench-only tab. Fix: add `html.embed .btn[aria-pressed="true"] { border-color:var(--accent-dark); }`, or scope the edge rule to `:not([aria-pressed="true"])`. `.btn:disabled` also loses to it, but in the tab `--border` and `--border-strong` are the same value (vscode.css:15–16), so nothing changes |

**Suite** (outside the sandbox, with the lead's stub that provides only `pytest.raises`, which is semantically correct): **Ran 241, OK, skipped 2.** Without the stub it is 204 ran, 4 errors, as above. Follow-up for the repo: add pytest to the venv's dev dependencies, or change test_map to `assertRaises`, so that nobody needs a stub outside the repo.

**Verdict:** the code for phase 1 passes. Before the merge the handoff (open defect 2) still has to be written, and the pressed-toggle edge in the tab should be fixed or accepted there. The merge to main itself needs Juhyeong.
