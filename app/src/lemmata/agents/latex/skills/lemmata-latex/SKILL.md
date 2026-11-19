---
name: lemmata-latex
description: Write LaTeX for the paper from Lemmata (results tables, paragraphs, captions) so it can be pasted into Overleaf. Use when the researcher asks for LaTeX of their results or claims, or types /lemmata-latex.
---
# LaTeX from Lemmata

The researcher's paper is in Overleaf, which Lemmata cannot read. So the LaTeX is made here, from everything Lemmata
holds about the project, and kept in Lemmata with a check on its numbers.

1. Check that the Lemmata tools answer for this project (`list_projects`). If they do not, say how to connect and stop.
2. Hand the work to the `lemmata-latex` agent (it runs on Opus):
   - if the researcher asked for something in this conversation, pass their words on as the `ask`;
   - otherwise have it call `latex` and write every open request.
3. For each piece the agent hands in, show the researcher the LaTeX in a code block, then one line on what Lemmata's
   check found (numbers not in the files, citations to fill in).
4. End with what still needs the researcher: computed values to confirm, `\cite{TODO-…}` keys, tables that had to be
   turned or split.

If the `lemmata-latex` agent is not installed, do the same work yourself following the same rules: only the brief of
the `latex` tool, exact numbers, one piece per `submit_latex`.

Nothing here edits the paper or the repository.
