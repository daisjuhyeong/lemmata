"""project.json: load / create / resolve repos / seed checkpoint."""
import os
import re
from pathlib import Path

from .errors import BadRequest

REPO_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,15}$")


def detect_role(path):
    """paper if the folder holds a .tex file with \\documentclass (top level or one level down)."""
    p = Path(path)
    cands = list(p.glob("*.tex")) + list(p.glob("*/*.tex"))
    for f in cands[:50]:
        try:
            if "\\documentclass" in f.read_text(encoding="utf-8", errors="replace")[:20000]:
                return "paper"
        except OSError:
            pass
    return "code"


def load_or_create(root, hub):
    man = hub.read_json("project.json", None)
    if man is None:
        role = detect_role(root)
        man = {"schema": "rmap.project/1", "name": Path(root).name or "project",
               "repos": [{"id": role, "role": role, "path": "."}]}
        hub.write_json("project.json", man)
    return man


def resolve(root, man):
    repos = []
    seen = set()
    for r in man.get("repos", []):
        rid = r.get("id", "")
        if not REPO_ID_RE.match(rid) or rid in seen:
            raise BadRequest("invalid or duplicate repo id %r in project.json" % rid)
        if r.get("role") not in ("paper", "code"):
            raise BadRequest("repo %r: role must be 'paper' or 'code'" % rid)
        seen.add(rid)
        p = Path(r.get("path", "."))
        abs_ = (Path(root) / p) if not p.is_absolute() else p
        abs_ = Path(os.path.normpath(str(abs_)))
        if not abs_.is_dir():
            raise BadRequest("repo %r: folder %s does not exist" % (rid, abs_))
        repos.append({"id": rid, "role": r["role"], "path": r.get("path", "."), "abs_path": str(abs_),
                      "main_tex": r.get("main_tex"), "exclude": r.get("exclude") or []})
    if not repos:
        raise BadRequest("project.json lists no repos")
    if sum(1 for r in repos if r["role"] == "paper") > 1:
        raise BadRequest("at most one paper repo is supported")
    return repos
