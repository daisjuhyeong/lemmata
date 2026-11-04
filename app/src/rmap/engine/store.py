"""Hub folder IO (<project>/.rmap/): atomic JSON writes, blob store, hub .gitignore."""
import json
import os
from pathlib import Path

HUB_NAME = ".rmap"


class Hub:
    def __init__(self, root):
        self.root = Path(root)
        self.dir = self.root / HUB_NAME

    def ensure(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        gi = self.dir / ".gitignore"
        if not gi.exists():
            gi.write_text("*\n", encoding="utf-8")
        return self.dir

    def path(self, *parts):
        return self.dir.joinpath(*parts)

    def exists(self, name):
        return self.path(name).is_file()

    def read_json(self, name, default=None):
        p = self.path(name)
        if not p.is_file():
            return default
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, name, obj):
        self.ensure()
        p = self.path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
            f.write("\n")
        os.replace(tmp, p)

    # blob store: raw bytes named by git blob hex
    def put_blob(self, hexid, data):
        p = self.path("cache", "blobs", hexid)
        if p.exists():
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, p)

    def get_blob(self, hexid):
        p = self.path("cache", "blobs", hexid)
        return p.read_bytes() if p.is_file() else None


def check_schema(obj, prefix):
    """Refuse an unknown major version of a hub file."""
    s = (obj or {}).get("schema", "")
    if s and not s.startswith(prefix + "/1"):
        raise ValueError("unsupported schema %r (expected %s/1)" % (s, prefix))
    return obj
