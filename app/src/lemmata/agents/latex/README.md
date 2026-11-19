# Lemmata LaTeX agent (for Claude Code)

One agent and one skill that write LaTeX for your paper from what Lemmata holds: results tables, paragraphs, captions.
You paste the result into Overleaf. The agent runs in your own Claude Code session on Opus (`model: opus` in its file;
change that line to use another model).

- Ask in Lemmata (sidebar → LaTeX → Ask your agent), then type `/lemmata-latex` in Claude Code; or
- ask in Claude Code directly: "use lemmata-latex to write the main results table with a caption".

What comes back is shown in Claude Code and kept on Lemmata's LaTeX page with a Copy button and a check: every decimal
number is looked up in your result files, environments and braces must close, citation keys are looked up. When your
results change later, a snippet whose numbers are no longer in the files is marked stale.

Install: `lemmata agents install /path/to/your/research-repo` (installs this and the paper agents).
