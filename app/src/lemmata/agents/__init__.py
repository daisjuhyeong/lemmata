"""Agent kits that Lemmata ships for the researcher's own coding agent (S30).

`paper/` holds Claude Code agents adapted from PaperOrchestra (Apache-2.0; see paper/NOTICE.md). Nothing here runs a
model: the files are copied into a research repository and run in the researcher's own Claude Code session.
"""
from pathlib import Path

KITS = {"paper": "Draft and revise a paper in stages (six agents and the /lemmata-paper skill), adapted from PaperOrchestra"}
ROOT = Path(__file__).resolve().parent


def plan(kit, target):
    """[(source file, destination file)] for installing a kit into a repository's .claude folder."""
    if kit not in KITS:
        raise ValueError("unknown kit %r (known: %s)" % (kit, ", ".join(sorted(KITS))))
    src, dst = ROOT / kit, Path(target) / ".claude"
    out = [(p, dst / "agents" / p.name) for p in sorted((src / "agents").glob("*.md"))]
    out += [(p, dst / "skills" / p.relative_to(src / "skills")) for p in sorted((src / "skills").rglob("*.md"))]
    out += [(src / n, dst / ("lemmata-%s-agents" % kit) / n) for n in ("NOTICE.md", "README.md", "LICENSE-APACHE-2.0")]
    return out


def install(kit, target, force=False):
    """Copy a kit into <target>/.claude. An existing file is left alone unless force. -> (written, kept)."""
    target = Path(target).expanduser()
    if not target.is_dir():
        raise ValueError("%s is not a folder" % target)
    written, kept = [], []
    for src, dst in plan(kit, target):
        if dst.exists() and not force and dst.read_bytes() != src.read_bytes():
            kept.append(dst)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        written.append(dst)
    return written, kept
