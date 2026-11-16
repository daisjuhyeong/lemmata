---
type: task-card
owner_agent: lead
status: open
sources: ["founder chat 2026-11-16 11:01 KST", "https://ibel-research-portal-demo.vercel.app (demo, entered as the sample researcher, read 2026-11-16)"]
last_reviewed: 2026-11-16
---
# Task S24-01b (addendum to S24-01): the IBEL research portal as a UI reference

## What Juhyeong said (chat, 11:01 KST)
- Reference: https://ibel-research-portal-demo.vercel.app, a research portal for a lab (IBEL, Korea University).
- He likes **the to-do list and how each item links to its dedicated page**.
- He likes **the calendar page**: "I can actually incorporate the time axis into our research", so a researcher can
  "track (just like a cookie crumble) what they have done".
- The difference he draws: Lemmata is "the more lower-level researcher-side assistant tool that is linked with VS
  code, latex code for writing, and overall experiment and writing alignment with time-axis, flexible to be updated
  along with various feedbacks and changes".
- Where it should end up: "the page to be dedicated for a researcher, where such individual research can be viewed
  as a whole, and others can watch it as well."
- "Consider the UI of this page through the CTO agent for our Lemmata."

## What the portal shows (observed in the demo; all [P], same URL)
The portal manages a lab's **papers through submission**, not experiments or code. Roles: professor, lab lead,
researcher, operator; each sees different screens.

| Part | What it shows |
|---|---|
| Shell | Left sidebar: Home, Status board, My papers, Weekly report, My schedule, Trend radar, Literature, Lab knowledge base, Topic finding; Help, Manual, Settings at the bottom. Top bar: search (Ctrl K), light/dark, KO/EN, notifications, user. Right edge: a collapsible panel and an AI-agent button |
| Home (`/`) | Greeting and date · a "first week" checklist with progress (3/5) where each open item has a "go do it" link · **Today's to-do**, ordered "others are waiting on me → deadline near → professor confirmation", with counts "my turn 0 · waiting 2" · **My papers by stage**: one card per paper with status chip, stage (e.g. 1st Review), progress 8/9, and the blocking reason ("waiting for professor's G4 decision", "in review, day 51") · **Upcoming deadlines** with D-2 / D-34 · rising topics · lab totals |
| My papers (`/papers`) | Table: title, stage, status, journal, my role, gate, next date, against schedule ("on track" / "resubmission decision needed"), pin. Views: list / **progress-history table**. Sort: default, deadline, last changed |
| Paper page (`/papers/9`) | Breadcrumb · title, status chip, journal, authors, deadline chip · a **horizontal stage strip of 9 stages with dates and gates G1-G5 between them**; done stages ticked, the current one highlighted; "Overview: now stage 7" · action buttons (edit, change stage, change status, invite, open editor, see gate) · **Next to do** (one sentence, with the deadline and a link to the gate) · recommended schedule counted back from graduation · **writing history: "13 entries · latest: G4 internal review (date)"** · abstract · members with roles · files in numbered folders per stage · linked mail summary |
| My schedule (`/calendar`) | Month grid · five event kinds as coloured chips that also filter (paper deadline, recommended stage deadline, internal review, journal deadline, awaiting confirmation) · events are **deadlines, i.e. the future**; each names its paper · list "next 60 days" · export as ICS or a subscription link |
| Weekly report (`/reports/weekly`) | Week picker (W47, W46, …) · counts (papers, changed this week, to-do, blocked) · per paper: **changed this week / to do / blocked** ("professor decision waiting 10 days") · "no change this week: 2 papers" · private memo · export Markdown, PDF, Notion |

Not read: Status board, Trend radar, Literature, Knowledge base, Topic finding, the gate page, the progress-history
table, and the professor's and lab lead's screens.

## What the CTO should do with it (add to the S24-01 deliverables)
1. In `benchmark-structures.md`, add the portal as one more row, and one paragraph on the boundary: the portal is
   the lab's view of papers moving through stages and gates; Lemmata is the researcher's view of the claims,
   experiments, code and LaTeX behind one paper. Say where they would meet (a paper's stage "implementation and
   experiments" is where Lemmata lives) without proposing an integration.
2. In ADR-008, decide how these four ideas fit the top-down spine, each mapped to what Lemmata already has
   (Tasks, Timeline, Changes, History, Growth, Digest, run manifests, the decision timeline). Read that code first:
   - **To-do that links to its dedicated page.** Each item opens the claim, experiment, setup item or paper line it
     is about, and is ordered by who or what is waiting. Where do items come from by rule (stale result, untested
     claim, missing baseline result, criterion not set, paper number differs from the run, advisor feedback)?
   - **Time axis as a calendar, looking back.** The portal's calendar holds deadlines. Juhyeong wants the trail of
     what was done. Propose a calendar or timeline whose entries come from data Lemmata already records (runs,
     commits, confirmed claims and stage changes, paper edits, feedback), plus deadlines; clicking an entry opens
     the object at that point in time. Say which existing page it replaces or absorbs.
   - **One page per researcher / per research.** A home that shows one research project as a whole (thesis and
     claim counts, next to do, recent trail, upcoming deadlines) and a read-only view that others (PI, lab mates)
     can open. Tie it to what ADR-006 already decided about sign-in and sharing; state what is missing.
   - **Shell.** The portal uses a left sidebar; Lemmata's S18 spec uses a top bar with few tabs, aligned to the DAIS
     site. Give options and a recommendation; this changes the nav, so it is Juhyeong's decision.
3. Add the calendar/trail, the to-do and the researcher home to the "Proposed" diagrams in `docs/map/`
   (page hierarchy and navigation), and to the build plan with their order relative to the top-down Experiments page.
4. Do not copy the portal's visual design, wording or stage model. Take the patterns only.
