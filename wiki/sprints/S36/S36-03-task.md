---
type: task
owner_agent: lead
status: built 2026-11-23, see S36-03-handoff.md (line 2 was already built in a349a64 as 'a claim or nothing', confirmed by the founder; line 6's decisions are in the handoff)
sources:
  - "founder message in chat, 2026-11-23 12:58 KST, answering the five open questions of S36-02-handoff.md as the chat had numbered them (the home_seen question first, then the handoff's questions 1 to 4): '1. Yes. this is important. 2. instal Playwright in a temporary folder on the Mac mini 3. Yes 4. and 5. let CTO agent decide.'"
  - "same message: 'Also, for the Lemmata homepage, if i am clicking the Lemmata button on the top left, then I will go back to the project selection slide, not the home button.'"
  - "S36-02-handoff.md (the five open questions, and what was not checked) ; S36-01-handoff.md (why no screenshots exist) ; S36-01-task.md (acceptance lines 8, 12, 13, 15)"
  - "../../../app/src/lemmata/web/app.js at commit 3294e34: the title button `#bt-home` (line 2056) and `goHome()` (lines 2078-2082)"
  - "../S31/S31-01-handoff.md (the title goes Home, asked for by the founder on 2026-11-19; reversed by this card for a hub with a project open)"
  - "../../../CLAUDE.md (any use of user data needs the founder's approval)"
last_reviewed: 2026-11-23
---
# S36-03 task card: the founder's answers, the title goes to the project list, and the browser check

Owner: CTO, who assigns the build (web-eng). Reviewer: QA. Branch: `s36-design-system`, from 3294e34; onto `next` after its
tests pass. Nothing goes to main without Juhyeong.

## The founder's answers (2026-11-23 12:58 KST)
| # | Question in S36-02-handoff.md | Answer |
|---|---|---|
| 5 | May the hub keep, per project, a hashed GitHub login and when Home was last opened (`home_seen.json`)? | **Yes.** "this is important" |
| 1 | Browser check and screenshots: another machine, or Playwright in a temporary folder on the Mac mini? | **Playwright in a temporary folder on the Mac mini** |
| 2 | Should Needs you also hold feedback tasks that already point at a claim? | **Yes** |
| 3 | Build the claim-text rule ("every dataset" against the runs) now or later? | **The CTO decides** |
| 4 | Keep or drop the closed "Should you continue?" block on Review and "This week" block on Home? | **The CTO decides** |

The chat listed the five questions in a different order from the handoff (the record question first), and the founder
answered by the chat's numbers. The first column above gives each question's number in the handoff.

New request in the same message: clicking "Lemmata" at the top left goes to the list of projects, not to Home.

## Acceptance
Build lines 1 to 3 first, so the screenshots of line 4 show them.

| # | What | Done when |
|---|---|---|
| 1 | The title goes to the project list | On a hub, outside the VS Code tab, clicking the title (`#bt-home`) opens the list of projects (`/`), with a project open or not. Its `title` and `aria-label` say so ("Your projects"). Home stays the first item of the sidebar and is the only way to Home. Where there is no list to go to (the local server without a hub) the title keeps going to Home, and in the VS Code tab it keeps going to Setup. The S31 comment above `goHome()` and section 6 of the design page say the new behaviour. A test covers the three cases |
| 2 | Needs you holds feedback that points at a claim | Open feedback tasks that already point at a claim or node appear in Needs you with `needs_you` true, each row naming the claim it is about and linking to it. The answer line and the sand count beside Home in the sidebar include them. A task that is done or snoozed leaves the list |
| 3 | `home_seen.json` is approved, and said | The handoff records the founder's approval with the quote above. Settings (How Lemmata works, or the FAQ) says in one sentence what is kept: a hashed GitHub login and the time Home was last opened, per project, to show what changed since. Nothing more is stored than S36-02 built |
| 4 | The browser check, with screenshots | Playwright and Chromium are installed in a temporary folder outside the repository on the Mac mini; nothing is added to `pyproject.toml` or `uv.lock`, and the folder is removed afterwards. "Before" pages come from a throwaway local server on a worktree at `bc26f66`, "after" from the branch head. For Home, Thesis, Setup, Review and Trail on the `test_map` project: pairs at 1360px, light and dark, plus the after pages at 760 and 420px, saved in `wiki/sprints/S36/screenshots/`. Where `mcd_extension` is on this Mac, its Thesis at 1280px too |
| 5 | What the check shows is fixed | Every defect seen (a row that wraps at 1280px, labels that overlap in the tree, a page that scrolls sideways, a broken line, unreadable text in dark) is fixed or listed with a reason in the handoff. S36-01 lines 8 and 15 are then marked checked or not |
| 6 | The CTO's two decisions | The handoff says, with one reason each: whether the claim-text rule is built now or later (if now, it gets its own task card and is not built under this one), and whether each of the two closed blocks stays or goes (if one goes, what replaces the feature it carried) |
| 7 | Nothing else breaks | The Python suite passes. `vscode/` is unchanged, or its suites are run |

## How to hand off
`S36-03-handoff.md` with what changed, the screenshots side by side, what was not checked, and open questions. Update
`wiki/index.md` and `wiki/log.md`. Push to `s36-design-system`, then the same commit to `next`.

## Not known when this card was written
- Whether Claude Code on the Mac mini will be allowed to install Playwright this time. On 2026-11-22 the permission check
  refused it (S36-01-handoff.md). The founder has now approved it, and may need to approve the prompt when it appears.
- How the live site looks. It was opened once from the chat's browser on 2026-11-23 and stayed on "Loading…" without styles,
  most likely because that browser blocked the page's scripts; this says nothing about the site itself.
