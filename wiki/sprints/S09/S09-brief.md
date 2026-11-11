---
type: task-card
owner_agent: lead
status: built, not yet QA-verified
sources:
  - "founder request in chat, 2026-11-11 13:44 KST: equations are LaTeX code and must be shown as equations; add a notation consistency check with a glossary, checked across the paper and aligned with the functions and code on GitHub"
  - "https://katex.org (KaTeX 0.16.47, MIT licence; bundled under app/src/lemmata/web/vendor/katex with its LICENSE file, fetched from the npm registry 2026-11-11)"
  - "code on branch s07-public-site: app/src/lemmata/engine/notation.py, engine/claims.py (detex keeps math), engine/api.py, server.py, mcp.py, web/research.js, web/vendor/katex/, tests/test_tree.py"
last_reviewed: 2026-11-11
---
# S09 brief: typeset math, and a notation glossary checked against the paper and the code

## What was built
- **Math is typeset.** Claims, theorem statements, captions, table cells and the core message keep their TeX between `$…$` / `\[…\]` and the app renders it with KaTeX, bundled in the repo (no CDN, works offline). The paper's own `\newcommand`, `\def` and `\DeclareMathOperator` macros are passed to the renderer. The single-file HTML export has no renderer and shows the TeX source.
- **Notation tab.** One row per symbol: the symbol, what it means, the name in the code, how often it is used.
  - Symbols are read from all math in the paper (Greek letters, decorated letters such as `\mathcal{L}`, `\hat{y}`, bold variants treated as one, worded subscripts such as `L_{rec}` kept as part of the name, zero-argument user macros).
  - Meanings come from sentences around the symbol: "where $w$ is the …", "$\tau$ denotes the …", "let $L$ denote …", "the … is written as $\ell$", "a window of size $w$", "the learning rate $\eta$".
  - Checks: one symbol with two meanings; two symbols with one meaning; a value stated in the paper that differs from the value in the code.
  - Code: Python files are parsed (never run) for function names, parameters and defaults, variables, argparse options; config files for keys and values. A code name is **suggested** when its words match the meaning ("window size" and `window_size`, "learning rate" and `lr`) or it is the Greek letter's name. The researcher accepts or rejects each suggestion; accepted links carry a GitHub link.
  - The researcher can set the meaning, pick one of the found meanings, or hide a symbol.
- MCP tool `notation`.

## Known limits (tell users)
- Rules, not understanding. A meaning phrased in an unusual way is missed and the symbol shows "—". Index letters (i, j, t) are listed only when used three times or more.
- "Two meanings" is raised when two found meanings share no content word. A symbol reused on purpose in another section (for example in the appendix) will be flagged; the researcher picks the meaning or hides the symbol.
- A paper/code value difference is shown as "Paper ≠ code?" while the link is only suggested, and as "Paper ≠ code" once accepted.
- Only Python and YAML/JSON/TOML-style config files are read for code names.
- KaTeX does not support every LaTeX package; an unsupported command is shown as its source in amber.
