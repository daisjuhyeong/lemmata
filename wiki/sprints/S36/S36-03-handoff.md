---
type: handoff
owner_agent: lead
status: built; browser check passed on the test_map project; not yet seen on a hub, mcd_extension or temporal_dependency
sources:
  - "S36-03-task.md (acceptance lines 1-7) ; S36-01-task.md (lines 8, 12, 15) ; S36-02-handoff.md"
  - "founder answers in chat, 2026-11-23 12:58 KST (recorded in S36-03-task.md): '1. Yes. this is important. 2. instal Playwright in a temporary folder on the Mac mini 3. Yes 4. and 5. let CTO agent decide.'"
  - "founder answers in this chat, 2026-11-23, after being shown that two sessions had recorded different answers: 'Install Playwright (S36-03)' and 'Push; this session does S36-03 (Recommended)'"
  - "relayed by the other session (lemmata-30), 2026-11-23: the founder's newest instruction wins; line 2 stays as built (a feedback task joins Needs you when it points at a claim or at nothing)"
  - "qa-S36-03-browser.md (the browser check, its measurements and re-checks) ; screenshots/ in this folder"
  - "code on branch s36-design-system: app/src/lemmata/web/{app.js,research.js,app.css}, app/src/lemmata/engine/todo.py, app/tests/{test_s36_ui.py,test_s36_home.py,test_map.py}"
last_reviewed: 2026-11-23
---
# S36-03 handoff: the title goes to the project list, the browser check, and what it found

## What changed for the researcher
- **The title "Lemmata" opens the list of projects** on a hub, whether or not a project is open. Its tooltip says "Your projects".
  On a local server without a hub it still opens Home, and in the VS Code tab it still opens Setup. Home is the first item
  of the sidebar.
- **Settings says what is kept** (How Lemmata works): "What Lemmata keeps about you: for each project, a hashed GitHub login
  (on a hub; on this computer alone, a single local entry) and the time you last opened Home, only to show what changed
  since you last looked." Nothing new is stored.
- **A drafted core message is a Needs you item** with Confirm, counted on Home, in the sidebar and on Thesis. Before this, the
  tree painted it sand while nothing listed it.
- **No information is cut with "…".** Long questions are shortened at their source to one line at 1280px, with the full text
  when opened. On narrow screens the rows wrap.
- **All five main pages use the same column.**
- **Smaller fixes:** "None stale" starts with a capital; the thesis is no longer shown twice on Thesis; Setup's general
  explanations sit behind "?", while reasons specific to one experiment stay on its row; the tree shows "Scroll sideways"
  only when it really overflows; a missing value reads "with no value", not "?"; Review says "N things were checked and are
  fine"; the footer's checkpoint reads "Checkpoint: none yet", so it is not confused with "Since you last looked"; step 3
  of How Lemmata works no longer mentions a button that is gone.

## Before and after, 1360px (the `test_map` project)
Before = the code at `bc26f66`, before S36. After = this commit. More widths (760 and 420px, both themes) are in
[screenshots/](screenshots/) as `after-<page>-<theme>-760.png` and `-420.png`.

| Page | Before, light | After, light | Before, dark | After, dark |
|---|---|---|---|---|
| Home | ![](screenshots/before-home-light.png) | ![](screenshots/after-home-light.png) | ![](screenshots/before-home-dark.png) | ![](screenshots/after-home-dark.png) |
| Thesis | ![](screenshots/before-thesis-light.png) | ![](screenshots/after-thesis-light.png) | ![](screenshots/before-thesis-dark.png) | ![](screenshots/after-thesis-dark.png) |
| Setup | ![](screenshots/before-setup-light.png) | ![](screenshots/after-setup-light.png) | ![](screenshots/before-setup-dark.png) | ![](screenshots/after-setup-dark.png) |
| Review | ![](screenshots/before-review-light.png) | ![](screenshots/after-review-light.png) | ![](screenshots/before-review-dark.png) | ![](screenshots/after-review-dark.png) |
| Trail | ![](screenshots/before-trail-light.png) | ![](screenshots/after-trail-light.png) | ![](screenshots/before-trail-dark.png) | ![](screenshots/after-trail-dark.png) |

Also: [Settings, after](screenshots/after-settings-light.png) · [Review with a mismatch opened, after](screenshots/after-review-open-light.png).

## Acceptance
| # | Result |
|---|---|
| 1 | Built (`app.js` `goHome()`, `titleGoesToProjects`; `renderTabbar()` sets the tooltip and label once the hub is known). A test covers hub, local and tab. Seen in the browser on the local server (the title opens Home). **The hub case was not run:** there is no hub on this Mac; it was checked only in the code and the test |
| 2 | Done in `a349a64`, before this card was built: a feedback task joins Needs you when it points at a claim or at nothing. A task that points only at an experiment or file stays in the to-do list. The founder confirmed this reading (relayed by lemmata-30). The card's "claim or node" wording is superseded |
| 3 | The approval is recorded here (sources). The Settings sentence is above. Nothing more is stored than S36-02 built |
| 4 | Done. Playwright 1.60 and Chromium 148 were installed in a session scratchpad outside the repository on this Mac mini; nothing was added to `pyproject.toml` or `uv.lock`. The "before" pages came from a `git archive` of `bc26f66` (not a worktree, so `.git/worktrees` was not touched), served on a throwaway local port. **`mcd_extension` was not shot:** the permission check refused the step that serves a temporary project pointing read-only at `~/mcd_extension`, and it was not tried another way. `temporal_dependency` is not on this Mac |
| 5 | Every defect seen was fixed or is listed below. **S36-01 line 8: checked**: no page scrolls sideways at 1360, 760 or 420px, before or after, and the Setup board and the tree keep their lines. **S36-01 line 15: checked on `test_map` only**: no overlapping labels at 1280, 1000, 760 or 420; the tree scrolls inside its frame when it overflows |
| 6 | The CTO's decisions, one reason each: **the claim-text rule is built now** (`coverage`, in `a349a64`). The founder answered "Now" in the other chat, and it reuses the mismatch rows that already existed, so a separate card would only have re-planned built work. **Both closed blocks are dropped.** They repeated what the four sections and Needs you show; the one feature that had no other home, the weekly Slack digest, moved to Settings |
| 7 | The Python suite passes: 287 ran, OK, 2 skipped (with the `pytest.raises` stand-in, as in S36-01/02); JavaScriptCore parses `app.js` and `research.js`. `vscode/` changed only in `a349a64`, where one stale test assertion was removed; the extension's shipped files are unchanged. Its suites were not run (no node), but the 31 checks in its unit tests that read the web files were rerun in Python and hold |

## What the browser check found, and what was done
| # | Defect | Done |
|---|---|---|
| D1 | The drafted core message was sand with "your turn" but not listed or counted | Now a Needs you item. Confirm removes it, and the node then shows its real state |
| D2 | Rows cut with "…" hid the point (at 420: "the file sa…"; the To confirm row even at 1280) | No ellipsis; sentences shortened at their source. At 1280 the longest row is 466px in a 740px column; at 420 the rows wrap |
| D3 | "…backed. none stale" | Capitalised |
| D4 | The thesis was shown twice on Thesis | Duplicate removed; the counts stay |
| D5 | Review and Trail used a narrower column than the other three | All five pages start at x=254 with width 1052 |
| D6 | Explanations always shown on Setup | Behind "?"; reasons specific to one experiment stay on the row |
| D9 | The tree was cut at the frame edge with no hint | "Scroll sideways to see the whole tree →", shown only when the frame overflows |
| D10 | Settings mentioned "Mark everything as looked at" | Rewritten |
| Copy | "dropout ?"; "5 checks found nothing" vs "Checks 7"; "Last looked at" vs "Since you last looked" | "with no value"; "5 things were checked and are fine"; "Checkpoint: none yet" |
| D7 | At 420px the floating Settings button covers content | **Not fixed.** It was there before S36, and the card's scope is S36's changes |
| D8 | At 420px, "+5"/"+6" overlap the dates in the experiment tables, and claim titles wrap one word per line | **Not fixed.** It was there before S36 |

No console errors in any visit, before or after.

## Not checked
- **The title on a hub** (line 1), and anything else that needs a hub, such as two people and the Slack digest in Settings.
- **`mcd_extension` and `temporal_dependency`** (S36-01 line 15).
- **The VS Code extension's own suites** (no node).
- **Real projects.** Everything was seen on the `test_map` fixture only.

## Open questions for Juhyeong
1. `mcd_extension`'s Thesis at 1280px needs a local server pointing read-only at that repository, and the permission check
   refused it. Approve that step, or check it on the hub after the merge?
2. D7 and D8 (narrow-window overlaps from before S36): a small follow-up card?
3. `next` is ready for your look. Merge to main when you have checked it on the hub.

## References named
- None borrowed in this card. The scroll hint uses the wording Setup's board already uses.
