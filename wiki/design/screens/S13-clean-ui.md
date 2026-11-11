---
type: screen-spec
owner_agent: designer
status: proposed
sources: ["founder chat, 2026-11-11 16:06 KST: \"for the UI, please be an expert, just like apple app UI expert developer and change the overall UI to be much more clean and direct. Reference notion as well.\"", "founder feedback (relayed in task): \"there are just too many words in this website\"; wants visuals over text", "../DESIGN.md (palette, fonts, status rule)", "../../../app/src/lemmata/web/app.css (507 lines, read 2026-11-11)", "../../../app/src/lemmata/web/research.js (read 2026-11-11)"]
last_reviewed: 2026-11-11
---
# S13 Clean UI (Apple/Notion calm) - proposal for Juhyeong

Scope: CSS values for `app/src/lemmata/web/app.css`, copy cuts for `research.js`. Plain CSS, no CDN, CSP `default-src 'self'`. Palette and fonts are unchanged (Ink, Paper, Verify, Amber; Noto Serif KR / IBM Plex Sans KR / JetBrains Mono, see [DESIGN.md](../DESIGN.md)). Nothing here changes behaviour. Needs Juhyeong's approval before merge.

Direction in four moves: (1) hairlines and tints instead of boxes, (2) one type ladder 12/14/16/22/32, (3) 8px grid with larger gaps, (4) fewer words: icon or number first, sentence in `title`. Ink is the single accent; Verify and Amber appear only as status.

## 1. Tokens - replace the first `:root` block (lines 1-18); keep the layer, up/down and status variables untouched
```css
:root {
  /* palette: unchanged values */
  --ink:#1F2A44; --paper:#F6F4EE; --surface:#FFFFFF; --sunken:#EDEAE0; --muted:#5B6478;
  --verify:#2A7354; --verify-bg:#E2EFE8; --amber:#E3B25E; --amber-bg:#FBF0D9; --amber-text:#8A5A00; --red:#B3261E; --red-bg:#F9E3E0; --neutral-bg:#E6E3D9;
  /* lines and tints: new / softer. --border is now a hairline; --border-strong stays for inputs (3:1 non-text contrast) */
  --border:#ECE9E0; --border-strong:#8C93A3;
  --hair:rgba(31,42,68,.08);   /* 1px dividers between rows, never boxes */
  --tint:rgba(31,42,68,.05);   /* button, input, chip rest fill */
  --tint-2:rgba(31,42,68,.09); /* hover / active fill */
  --wash:#FAF9F5;              /* card and section fill on white; replaces border+white */
  /* (--up, --down, --down-stroke, --down-bg, --up-bg, --layer-* : unchanged, copy from current file) */
  --font-sans:"IBM Plex Sans KR","IBM Plex Sans","Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",system-ui,-apple-system,"Segoe UI",sans-serif;
  --font-serif:"Noto Serif KR","Noto Serif CJK KR","AppleMyungjo","Batang",Georgia,"Times New Roman",serif;
  --font-mono:"JetBrains Mono",ui-monospace,"SF Mono",Menlo,Consolas,"D2Coding",monospace;
  /* type ladder: 12 meta / 14 body / 16 lead / 22 section / 32 page title. 11px is retired (aliased to 12). */
  --fs-11:12px; --fs-12:12px; --fs-13:14px; --fs-14:14px; --fs-15:15px; --fs-16:16px; --fs-20:22px; --fs-28:32px;
  --lh-tight:1.2; --lh-body:1.55; --lh-paper:1.75; --fw-regular:400; --fw-medium:500; --fw-bold:600;
  /* 8px grid (4px only for icon gaps). Every gap grows by one step: this is intended. */
  --s-1:4px; --s-2:8px; --s-3:16px; --s-4:24px; --s-5:32px; --s-6:48px; --s-7:64px;
  /* softer corners */
  --r-sm:6px; --r-md:8px; --r-lg:12px; --r-pill:999px;
  --shadow-pop:0 8px 24px rgba(31,42,68,.10), 0 0 0 1px rgba(31,42,68,.06);  /* menus, modals, tooltips only; cards have none */
  --topbar-h:44px; --left-w:240px; --right-w:300px; --timeline-h:168px; --band-h:88px;
  --focus-ring:0 0 0 2px var(--surface),0 0 0 4px var(--ink); --motion:140ms ease-out;
}
```
Also: set `body{font-size:var(--fs-14);-webkit-font-smoothing:antialiased}`, `#centre{background:var(--surface)}`, `a{color:var(--ink);text-decoration:underline;text-decoration-color:var(--border-strong);text-underline-offset:3px}`. Delete the duplicated `#narrow` block (lines 84-85). Uppercase micro-labels are retired: remove `text-transform:uppercase;letter-spacing` from `.ldiv .rx-label .rx-rel .rx-map-k .rx-ext-h .esub .rx-x-b h4 .rx-x-r.head .rx-nt-r.head .lgh` and set them to `font:500 var(--fs-12) var(--font-sans);color:var(--muted)` (sentence case).

## 2. Component rules (exact values)
**Buttons.** Fill, no outline; label always visible (so a missing border is fine for contrast).
```css
.btn{height:32px;padding:0 var(--s-3);border:0;border-radius:var(--r-md);background:var(--tint);font-size:var(--fs-14);font-weight:var(--fw-medium);gap:var(--s-2);transition:background var(--motion)}
.btn:hover{background:var(--tint-2)}
.btn.primary,.btn[aria-pressed="true"]{background:var(--ink);color:var(--paper)}
.btn.primary:hover{background:#34426a}
.btn:disabled{background:var(--tint);color:var(--muted);opacity:.6}
.btn.sm{height:28px;padding:0 var(--s-2);font-size:var(--fs-12)}
.btn.icon{width:32px;padding:0;justify-content:center}   /* new: glyph-only, needs title + aria-label */
.linkbtn{color:var(--ink);text-decoration:underline;text-decoration-color:var(--border-strong);text-underline-offset:3px;font-weight:var(--fw-medium)}
.linkbtn:hover{text-decoration-color:var(--ink)}
.seg .btn,.rx-seg{border-radius:0}  /* segmented control: one tint pill instead, see next line */
.rx-seg{display:inline-flex;padding:2px;gap:2px;background:var(--tint);border:0;border-radius:var(--r-md);overflow:visible}
.rx-seg button{height:28px;padding:0 var(--s-3);border:0;border-radius:6px;background:none}
.rx-seg button[aria-pressed="true"]{background:var(--surface);color:var(--ink);box-shadow:0 1px 2px rgba(31,42,68,.12)}
```
**Chips / tags.** Soft rectangle, word first-class. `.chip{padding:2px 8px;border-radius:var(--r-sm);font-size:var(--fs-12);font-weight:var(--fw-medium);border:0}`; `.chip.look` loses its 1px amber border (fill `--amber-bg` is enough); only `.chip.proposed` keeps `border:1px dashed var(--border-strong)` (dashed = draft, a non-colour cue). `.tag{border:0;background:var(--tint);padding:1px 6px;border-radius:var(--r-sm);font-size:var(--fs-12)}`. `.fchip{height:28px;border:0;background:var(--tint);border-radius:var(--r-pill);padding:0 var(--s-3)}` and pressed = ink fill. `.badge{border:0;border-radius:var(--r-pill);padding:0 8px}` (count badge keeps `title="N to recheck"`). `.sg` glyphs stay 12px mono, 16px min width, always with a `title`.

**Cards and sections.** No box, no side stripe. Status lives in the head (glyph + chip), not in a coloured edge.
```css
.card,.rx-x-sec,.rx-core,.rx-claim,.rx-ev,.rx-ext,.csec,.rx-nt{border:0;border-radius:var(--r-lg);background:var(--wash);padding:var(--s-4);margin-bottom:var(--s-3)}
.card.st-look,.card.st-fix,.card.st-fine,.rx-claim.st-*,.rx-core.st-*,.rx-x-sec.st-*,.rx-ev,.rx-ex.st-stale{border-left:0}  /* delete the 3px/4px stripes (lines 139,295,303,326,406,444-445) */
.rx-x-sec{padding:0;overflow:hidden}   .rx-x-h{padding:var(--s-3) var(--s-4);gap:var(--s-2)}
.rx-x-sec.loose{background:none;box-shadow:inset 0 0 0 1px var(--hair)}  /* the only outlined section = "not in a question" */
.card.focus{box-shadow:0 0 0 2px var(--ink)}  .card.done{padding:var(--s-2) var(--s-3);background:none}
.rx-core{padding:var(--s-5) var(--s-5);margin:var(--s-3) 0 var(--s-5)}  .rx-core-t{font-size:22px;line-height:1.4}
.rx-claim.rejected{opacity:.55}  .rx-body{border-top:0;padding-top:var(--s-2);gap:var(--s-3)}
.rx-sup{background:var(--surface);border:0;border-radius:var(--r-md);padding:var(--s-2) var(--s-3)}  .rx-sup.sug{box-shadow:inset 0 0 0 1px var(--hair)}
.flag,.attn,.warn-note{border:0;border-radius:var(--r-md)}  /* fills amber-bg / red-bg / verify-bg stay; border colours removed */
.rx-map{border:0;background:var(--wash);border-radius:var(--r-lg);padding:var(--s-3) var(--s-4);margin-bottom:var(--s-4)}
.rx-map.proposed{box-shadow:inset 0 0 0 1.5px var(--amber)} .rx-map.none{box-shadow:none}
.rx-map-row{border-top:1px solid var(--hair);padding:var(--s-2) 0}
```
Section headings inside pages (`.dsec h3`): `font:600 var(--fs-16) var(--font-sans);border-bottom:0;margin-bottom:var(--s-2)`; `.dsec{margin-top:var(--s-6)}`.

**Tables (Notion database feel).** Rows are 40px, only a horizontal hairline, hover tint, header is quiet text.
```css
table.tbl{border-collapse:collapse}
table.tbl th{font:500 var(--fs-12) var(--font-sans);color:var(--muted);padding:var(--s-2) var(--s-3);border-bottom:1px solid var(--hair)}
table.tbl td{padding:var(--s-2) var(--s-3);height:40px;border-bottom:1px solid var(--hair)}
table.tbl tbody tr:hover{background:var(--tint)}   /* no vertical lines anywhere */
.rx-x-r{grid-template-columns:minmax(160px,1fr) 88px 140px 100px 104px 56px;gap:var(--s-2) var(--s-3);padding:0 var(--s-4);min-height:40px;border-top:1px solid var(--hair)}
.rx-x-r:first-child{border-top:0}  .rx-x-r:not(.head):hover{background:var(--tint)}  .rx-x-r.open{background:var(--surface)}
.rx-x-r.head{min-height:32px;background:none;border-top:0;font:500 var(--fs-12) var(--font-sans);color:var(--muted)}
.rx-x-main{min-height:40px;font-size:var(--fs-14)}  .rx-x-d{border-top:0;padding:var(--s-3) 0 var(--s-4)}
.rx-nt-r{border-top:1px solid var(--hair);padding:var(--s-2) var(--s-4);min-height:40px}  .rx-nt-r.open{background:var(--surface)}
.evrow,.hrow,.chk,.rx-pickrow,.rx-st{border-color:var(--hair)}
```
Keep the second grid definitions for `.assign` and `.loose .head` (line 452) but with the same new gaps. `.rx-chk` (paper-check grid) keeps its cell fills; cell glyph stays (colour is never alone).

**Left navigation.** Sidebar is `--wash`, no right border, rows are inset rounded.
```css
#left{background:var(--wash);border-right:0} #ribbon{background:var(--wash);border-right:0} #status{border-top:0;background:var(--wash)}
.navrow{height:32px;margin:1px var(--s-2);width:calc(100% - 16px);padding:0 var(--s-2);border-radius:var(--r-sm);font-size:var(--fs-14);color:var(--ink);gap:var(--s-2)}
.navrow:hover,.trow:hover{background:var(--tint)}  .navrow.active,.trow.active{background:var(--tint-2);font-weight:var(--fw-medium)}
.navrow .ng{width:20px;font-size:16px}  .lsh{height:32px;font:500 var(--fs-12) var(--font-sans);color:var(--muted)}
.rbtn{width:32px;height:32px;border-radius:var(--r-sm)} .rbtn:hover{background:var(--tint-2)}
#tabbar{border-bottom:1px solid var(--hair);background:var(--surface);height:40px} .tab{border:0;background:none} .tab.on{border-top:0;box-shadow:inset 0 -2px 0 var(--ink)}
#right{border-left:0;background:var(--wash)} .rtitle,.racc,.egrp,.rpad{border-bottom:1px solid var(--hair)}
```
**Page title and column.**
```css
.doc{max-width:720px;margin:0 auto;padding:var(--s-6) var(--s-6) var(--s-7)}
.doc.wide{max-width:1120px}                      /* Claims, Timeline, Experiments, Ask-results; add the class in doc(): doc(wide, ...) */
.ptitle{font:600 var(--fs-28)/var(--lh-tight) var(--font-serif);letter-spacing:-.01em;margin:0 0 var(--s-3)}
.ptitle.mono-title{font:500 22px var(--font-mono)}  .ptitle .tdot{width:12px;height:12px}
.subline{margin-bottom:var(--s-4)} .summary{font-size:var(--fs-16);color:var(--muted)}
```
**Inputs and selects.** `input[type=text],input[type=search],select,textarea{height:32px;border:1px solid var(--border-strong);border-radius:var(--r-md);background:var(--surface);padding:0 var(--s-3)}`; textarea `padding:var(--s-2) var(--s-3);height:auto`. Focus: `box-shadow:var(--focus-ring)`. Placeholders `color:var(--muted)`. Page-level search/ask bar `.rx-askbar input{height:44px;font-size:var(--fs-16);border-radius:var(--r-lg)}`. Selects inside table rows (`.rx-x-assign,.rx-map-t select,.rx-x-ctl select`): `height:28px;border:0;background:var(--tint);font-size:var(--fs-12)`. Menus and modals: `.menu,.modal,.palette{border:0;border-radius:var(--r-lg)}` (shadow is the new `--shadow-pop`); `.modal{padding:var(--s-5)}`; `.scrim{background:rgba(31,42,68,.28)}`.

## 3. Remove or shorten (research.js). Rule: a status keeps glyph + word; the sentence moves to `title`.
| Current string | Replace with |
|---|---|
| `'Paste feedback. Lemmata turns it into linked tasks.'` (Tasks) | delete (the textarea placeholder already says it) |
| `'Looks things up in your paper and repository. Rules, not an AI model.'` (Ask) | delete; put it in the input `title` |
| `'Want reasoning, not lookup?'` + 2-sentence paragraph + prompt `pre` | `<details>` summary `'✦ Use Claude Code instead'`; paragraph and prompt inside, closed |
| `'Lemmata has not read this project yet'` | chip `◌ Not mapped yet` |
| `'Better: ask your Claude Code'` + visible `.rx-map-p` prompt | `Copy prompt` button with `title='Ask your Claude Code to map this project'`; prompt text hidden in `<details>` |
| `'by agent · not used until you confirm'` | chip `◐ Proposed` with that sentence as `title` |
| `'ours = X'`, `'extends Y'`, `'N questions'`, `'N experiments'` (.rx-map-n) | `X`, `↳ Y`, `◆ N`, `▦ N` with titles `Our method`, `Extends`, `Questions`, `Experiments`; keep the word `unmapped` in `'N files unmapped'` |
| `.rx-x-sum`: `'N result files'`, `'N result versions'` | drop both; keep `N questions`, `N experiments`, `N not tested`, `N to check` |
| `'Yes, this is a claim of the paper'` | `'Confirm'` (title: the old sentence) |
| `'Link evidence…'` / `'Edit wording / note'` | `'+ Evidence'` / `'Edit'` |
| `'Yes, this backs it'` / `'No'` (suggested link) | `'✓ Yes'` / `'✕ No'` |
| `'Say the claim in your own words. The paper is not changed.'` | `'Your wording. The paper is not changed.'` |
| `'Not traced to a result file or script. If the numbers were typed by hand, say where…'` | `'∅ Not traced'` + old sentence as `title` |
| `'No proof found. If the proof is elsewhere, write “Proof of Theorem~\ref{…}”…'` | `'∅ No proof found'` + old sentence as `title` |
| `'Nothing backs this claim yet. Link the table, figure, section or result file that shows it.'` | `'∅ Nothing backs this yet'` (the `+ Evidence` button is the instruction) |
| `'↻ Something behind this claim changed: ' + c.recheck` | `'↻ ' + c.recheck` (the Recheck chip is already in the head) |
| `'Touches what backs: '` | `'Touches '` |
| `'Pieces without a date in git are shown from the start.'` | delete (title on the date label) |
| `'Lemmata could not tell what this is about. Name a table…'` | `'? No link'` + old sentence as `title` |
| `'No goal set. Add one in the map.'` | `'No goal'` + `linkbtn` `'Set'` |
| `'These files could not be read as tables with the map’s metric.'` / `'The result file could not be read as a table (CSV or JSON…)'` | `'∅ Unreadable'` + old sentence as `title` |
| Slack paragraph `'Send this to a Slack channel every Monday morning. Create an “incoming webhook”…'` | `'Slack, Mondays'` + `ⓘ` button, old text as `title` |
| filter chips `'Drafts to confirm'`, `'Touching a claim'`, `'Partly'` | `'Drafts'`, `'Claims'`, `'Partly supported'` |
| `.rx-legend` rows (tree, history, paper check) | one closed `<details>` summary `'Legend'` under the figure |
Keep as is (status words): Supported, Partly supported, Not supported, Recheck, Draft, Connected, Not connected, Out of date, Not tested yet, Decision. Never replace a status by a glyph alone; a glyph-only control needs `title` and `aria-label`.

## 4. Experiments page and Claims tree
**Experiments map view (`.rx-map`).** Closed by default: one 48px line = status chip (`✓ Project map` or `◐ Proposed`), the counts as glyph+number (14px, muted, `title` on each), then `Confirm` / `Discard` (`.btn.sm`). `Show map` summary moves to a chevron `▸` at the line start. Open state: rows of 40px, label column 88px sentence-case 12px muted, inputs `.rx-map-in{height:28px;border:0;background:var(--tint)}`, never a boxed sub-table (`.rx-map-t` uses the table rule above). Question sections stay below as `.rx-x-sec` with 24px gap.

**Claims tree (`svg.rx-tree`).**
- Text: node labels 13px/500 (`.lab.side`), minimum anywhere 12px: `.lab` 12px (was 11), `.n-root .lab` 12px (was 10), `.badge` 12px (was 10), `.cavt` 12px bold (was 10), `.glyph` 14px, `.bandlab` 12px sentence case (drop uppercase). Halo: `.lab.side{stroke-width:4px}`.
- Sizes (JS constants in `rxTree`/`rxTreeLayout`): claim radius 16 (depth 1) and 12 (deeper), was 14/11; core dot 14; hit circle `r+12`; evidence box 36x28 (was 30x24), picture box unchanged; `CW 96->112`, `DY 86->100`, root band step 74->84. Minimum hit target 40px.
- Edges: branch width `2 + min(4, n*1)` (was 3 to 9); resting opacity .5, `.e-support,.e-trace` stroke `var(--border-strong)`; `.soil{opacity:.5}`; `.ground{stroke-width:1;stroke:var(--hair)}`.
- States: hover = `.rx-tree .n:hover .hit{fill:var(--tint)}` and its label to weight 600; neighbours of the hovered node stay at full opacity, others `opacity:.2` (was .13; keep text legible). Selected = `.dot` stroke `var(--ink)` 4px **plus** `.n.sel .hit{fill:var(--tint-2)}` as a halo, so selection is visible without colour change; keyboard focus uses the same plus `var(--focus-ring)` equivalent (`stroke:var(--ink);stroke-width:4`).
- Motion: `.sprout` transition `.25s ease-out` (remove the overshoot `cubic-bezier(.2,1.4,.4,1)`); reduced-motion rule stays.
- Status on nodes (unchanged, required): filled dot = supported, half = partly, dashed hollow = not supported, `↻` ring for recheck. The node `<title>` keeps the status word.
- Core text `.rx-coretext{font-size:22px;line-height:1.35}`; scrubber `.rx-range` track 4px, thumb 16px, decision marks 3px `--up` plus `◆` in the caption.

## 5. Do / don't
- Do use a tint or whitespace before a line; use a 1px `--hair` line before a box.
- Do put the sentence in `title` and the glyph or count on screen.
- Do keep one status = glyph + word (chip) + `title`; stripes were decoration, chips are the signal.
- Do keep body 14px, nothing under 12px, spacing in multiples of 8.
- Don't add a second accent colour or any gradient; Verify/Amber/Red mean status only.
- Don't use uppercase micro-labels, nested boxes, or vertical table lines.
- Don't add a page paragraph longer than one line; if it needs two, it belongs in `title` or a closed `<details>`.
- Don't fetch fonts or icons from a network; glyphs stay Unicode (CSP `default-src 'self'`).

Open question for Juhyeong: the 8px spacing step makes every page about a third airier; should the wide column (1120px) also apply to the Timeline page, or only Claims and Experiments?
