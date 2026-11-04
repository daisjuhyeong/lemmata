---
type: design-system
owner_agent: designer
status: draft
sources: ["founder brief to designer, 2026-11-04 (task message, S02 localhost demo); palette and fonts fixed by designer role card"]
last_reviewed: 2026-11-04
---
# Research Map design system (v0.1, desktop >= 1280px)

Proposal for Juhyeong's approval. Screens: [demo-screens.md](screens/demo-screens.md).
Contrast ratios are WCAG relative-luminance values computed by hand against Paper #F6F4EE (L about 0.90); the engineer should re-check with a tool before release.

## Rationale (short)
- Calm and dense: Paper background, Ink text, hairline borders, almost no shadow. Colour is rare, so when it appears it means something.
- Status is never colour alone. Every status = colour + word + icon character (table below). Direction (upstream/downstream) = colour + word + line style (solid vs dashed) + arrow label.
- Amber #E3B25E fails as text on Paper (about 1.8:1). Use it only as a fill with Ink text (about 7:1), or use the darker `--amber-text` for text.
- Offline: no web fonts fetched. Fonts are named first, then system fallbacks; the engineer may bundle woff2 files locally later.
- Korean text must render: every stack ends in a Korean-capable system font.

## Tokens
```css
:root {
  /* core palette */
  --ink:        #1F2A44;  /* text, 12.8:1 on paper */
  --paper:      #F6F4EE;  /* app background */
  --surface:    #FFFFFF;  /* panels, cards, popovers */
  --sunken:     #EDEAE0;  /* wells, code blocks, table stripes */
  --border:     #D9D5C8;  /* hairlines (decorative; not relied on for meaning) */
  --border-strong: #8C93A3; /* input borders, handles; 3:1 on paper */
  --muted:      #5B6478;  /* secondary text, 5.4:1 on paper */

  /* status */
  --verify:     #2A7354;  /* confirmed / reviewed; 5.2:1 on paper (text ok) */
  --verify-bg:  #E2EFE8;  /* chip fill; ink text 11:1 */
  --amber:      #E3B25E;  /* recheck fill only; ink on amber 7.3:1 */
  --amber-bg:   #FBF0D9;  /* chip fill */
  --amber-text: #8A5A00;  /* recheck text/icon; 5.4:1 on paper */
  --red:        #B3261E;  /* needs fixing; 5.9:1 on paper (text ok) */
  --red-bg:     #F9E3E0;  /* chip fill */
  --neutral-bg: #E6E3D9;  /* ignored / unknown chip fill */

  /* direction in lineage */
  --up:         #2B5FA8;  /* upstream "rests on"; 5.8:1 text-safe */
  --up-bg:      #E1EAF6;
  --down:       #A84A0A;  /* downstream "supports"; 5.2:1 text-safe */
  --down-stroke:#CF6A22;  /* graph lines only (about 3.3:1, non-text) */
  --down-bg:    #FAE6D6;

  /* layer colours: stroke (4px stripe + border) / tint (node fill). Always paired with the layer name/glyph. */
  --layer-thesis:    #1F2A44;  --layer-thesis-t:    #E4E6EC;
  --layer-question:  #3F4F8A;  --layer-question-t:  #E3E7F4;
  --layer-section:   #5B6478;  --layer-section-t:   #E8E9EC;
  --layer-reference: #7A5C99;  --layer-reference-t: #EEE8F4;
  --layer-paper:     #B0562E;  --layer-paper-t:     #F6E6DD;
  --layer-result:    #2A7354;  --layer-result-t:    #E2EFE8;
  --layer-code:      #1F6E80;  --layer-code-t:      #DDEEF2;
  --layer-run:       #7A6A1F;  --layer-run-t:       #F1ECD3;

  /* type */
  --font-sans:  "IBM Plex Sans KR", "IBM Plex Sans", "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-serif: "Noto Serif KR", "Noto Serif CJK KR", "AppleMyungjo", "Batang", Georgia, "Times New Roman", serif;
  --font-mono:  "JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, "D2Coding", monospace;

  --fs-11: 11px;  /* axis ticks, badges (uppercase only, never body) */
  --fs-12: 12px;  /* meta, captions, chips */
  --fs-13: 13px;  /* default UI text, lists */
  --fs-14: 14px;  /* panel body, buttons */
  --fs-16: 16px;  /* paper preview (serif) */
  --fs-20: 20px;  /* screen titles (serif) */
  --fs-28: 28px;  /* picker title (serif) */
  --lh-tight: 1.25; --lh-body: 1.5; --lh-paper: 1.7;
  --fw-regular: 400; --fw-medium: 500; --fw-bold: 600;

  /* spacing (4px base) */
  --s-1: 4px; --s-2: 8px; --s-3: 12px; --s-4: 16px; --s-5: 24px; --s-6: 32px; --s-7: 48px;

  /* radii and elevation */
  --r-sm: 3px;   /* chips, inputs */
  --r-md: 6px;   /* cards, nodes, buttons */
  --r-lg: 10px;  /* modals, popovers */
  --shadow-pop: 0 4px 16px rgba(31,42,68,.14);  /* popovers/modals only */

  /* layout */
  --topbar-h: 44px;
  --left-w: 260px;
  --right-w: 380px;
  --timeline-h: 168px;
  --band-h: 88px;

  /* focus */
  --focus-ring: 0 0 0 2px var(--paper), 0 0 0 4px var(--ink);
  --motion: 120ms ease-out;
}
@media (prefers-reduced-motion: reduce) { :root { --motion: 0ms; } }
```

## Usage rules
- Body: `--font-sans` 13-14px. Paper text (LaTeX excerpts, section titles in outline): `--font-serif`. All identifiers, paths, hashes, line numbers, counts in tables: `--font-mono`, with `font-variant-numeric: tabular-nums`.
- Screen titles and the picker title: serif. Never serif below 13px.
- Panels `--surface` with 1px `--border`; app background `--paper`. No gradients.
- Minimum hit target 28x28 px (dense desktop tool); graph nodes at least 24px tall.

## Status chips
Chip = 12px text, `--r-sm`, 2px/8px padding, icon character then word. Icon characters are plain Unicode so no icon font is needed. Word is always visible (not tooltip only).

| Status | Icon | Word | Text colour | Fill |
|---|---|---|---|---|
| Confirmed (in sync at checkpoint) | ✓ | Confirmed | --verify | --verify-bg |
| Recheck | ↻ | Recheck | --amber-text | --amber-bg (border 1px --amber) |
| Reviewed (author triage) | ✓✓ | Reviewed | --verify | --verify-bg |
| Needs fixing | ✕ | Needs fixing | --red | --red-bg |
| Ignored | – | Ignored | --muted | --neutral-bg |
| Low confidence | ? | Low confidence | --ink | --surface, dashed 1px --amber-text border |
| Proposed link | + | Proposed | --ink | --surface, dashed 1px --border-strong |
| Could not be matched | ? | Could not be matched | --amber-text | --amber-bg |
| Mismatch | ≠ | Mismatch | --red | --red-bg |
| Not traced | ∅ | Not traced | --amber-text | --amber-bg |

Distinguishing low confidence from Recheck: different word, different icon, dashed border. On graph nodes a recheck node carries an amber 3px bottom bar plus the "↻" glyph; needs-fixing a red bar plus "✕"; reviewed a green bar plus "✓✓".

## Lineage styling (selected node)
- Upstream ("Rests on"): `--up` solid 2px edges, label "▲ Rests on" at band margin, node outline `--up` 2px.
- Downstream ("Supports"): `--down-stroke` dashed (6 4) 2px edges, label "▼ Supports", node outline `--down` 2px.
- Selected node: 3px `--ink` outline. Non-lineage nodes: opacity 0.25, not removed (keeps layout stable); edges hidden.
- Legend (always visible bottom-left of graph): "▲ Rests on (upstream, solid blue)" / "▼ Supports (downstream, dashed orange)".

## Focus states
- Any focusable element: `outline: none; box-shadow: var(--focus-ring)` on `:focus-visible`. SVG nodes: `tabindex=0`, same ring drawn as an extra 2px offset rect.
- Selected is not the same as focused; selected persists with the 3px outline plus a "Selected" aria-label.
- Disabled: `--muted` text, no pointer, and a tooltip stating why.

## Open design decisions (for Juhyeong)
1. Layer order. Proposed top-down: Thesis, Question, Section, Reference, Paper item, Result, Code, Run. References as their own band is a simplification of "extra dimension"; alternative is a right-hand lane.
2. Product name replaces every `Research Map`; wordmark not designed yet.
