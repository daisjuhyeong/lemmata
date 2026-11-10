---
type: task-card
owner_agent: lead
status: built, not yet QA-verified
sources:
  - "founder request in chat, 2026-11-10 23:31 KST, and answers 2026-11-11: hosting = Mac mini + public tunnel; claims = Lemmata drafts, I confirm; A/B = claim map, recheck inbox, research timeline, ask; tools = decision timeline, feedback to tasks, weekly digest, experiment ledger; paper change tracking paused (Overleaf free plan has no Git)"
  - "../../decisions/ADR-006-public-multi-user-site.md"
  - "../S06/S06-brief.md"
last_reviewed: 2026-11-11
---
# S07 brief: a site people can sign in to, and a claim map

## Founder decisions
1. Stop making me sign out and in again. Make a real website others can open, sign in to with GitHub, connect their repositories and use.
2. A tutorial at the start that says what Lemmata is and how to use it. A/B test the ways Lemmata can assist research.
3. Track how the research is done from GitHub and the LaTeX source. Tracking *changes* in the LaTeX is paused; the paper is read as a snapshot (GitHub or an Overleaf source zip).
4. Organise the core message and check whether it is backed by experiments, lemmas, proofs and assumptions.

## What was built (branch `s07-public-site`)
| Area | Files | What |
|---|---|---|
| Accounts, public mode | `hub/github.py, auth.py, guard.py, routes.py, projects.py, cli.py, config.py` | per-account tokens and projects, device-flow sign-in without pairing, invite/open sign-up, reconnect in place, distinct GitHub errors, repo-list cache, personal MCP tokens, account deletion |
| Claim map | `engine/claims.py`, `engine/api.py` | drafts from abstract, contribution list, RQs, theorem-like environments; support from proofs, assumptions, lemmas, and tables/figures traced to result files, scripts and runs; states proposed/confirmed/rejected; `claims.md` export |
| Research process | `engine/process.py` | decision timeline, experiment ledger (out-of-date results), feedback to tasks, weekly digest (Slack webhook), Ask (rule-based lookup) |
| API | `server.py` | `/api/claims[.md]`, `/claims/link|add|remove`, `/timeline`, `/ledger`, `/tasks`, `/feedback`, `/digest`, `/ask` |
| MCP | `mcp.py` | tools `claims`, `timeline`, `experiments`, `tasks`, `add_feedback` |
| Site | `web/hub/*` | landing page, tutorial with start-view choice, reconnect card, account page, A/B table for the owner |
| Project UI | `web/research.js`, `web/app.js`, `web/app.css` | tabs Claims, Timeline, Experiments, Tasks, Ask; opens on the chosen start view |
| Tests | `tests/test_public.py`, `tests/fake_github.py` | 6 new tests (134 total pass); browser walk-through against the fake GitHub |
| Docs | `docs/PUBLIC-SITE.md`, ADR-006 | setup and risks |

## Known limits (tell users)
- Claims are found by rules. A contribution list needs an `itemize`/`enumerate` in the introduction or after a sentence such as "Our contributions are"; theorem-like environments need standard names or a `\newtheorem`. A proof placed elsewhere is connected only if it says "Proof of Theorem~\ref{…}".
- "Suggested" evidence is word overlap between a claim and a caption. It never counts until accepted.
- "Out of date" compares commit times of a result file and the scripts/settings behind it. A rerun that produced identical output still needs a commit to clear it.
- A project without a paper has no drafted claims; claims can be written by hand.

## Open for the next sprint
- QA pass by the QA agent (XSS on the new pages, ownership checks, CSRF on the public origin, the sign-in rate limits).
- GitHub App instead of the OAuth app (ADR-006).
- Designer review of the landing page and Claims page against `wiki/design/DESIGN.md`.
- Korean strings.
- Notion: read a claims database (founder asked where claims could live; chosen answer was the repository file).
