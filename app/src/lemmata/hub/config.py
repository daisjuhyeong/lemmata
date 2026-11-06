"""Data directory layout, hub config and 0600/0700 file helpers."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

DEFAULT_PORT = 8765
DEFAULT_CLIENT_ID = "Ov23lij3uNF6pctpA6yH"  # public OAuth App client id (Device Flow); there is no secret
DEFAULTS = {
    "port": DEFAULT_PORT,
    "github_client_id": DEFAULT_CLIENT_ID,
    "github_api": "https://api.github.com",
    "github_web": "https://github.com",
    "overleaf_git": "https://git.overleaf.com",
    "overleaf_enabled": False,
    "overleaf_min_interval": 120,
    "allow_hosts": [],
    "owner": None,
    "sync_interval": 300,
}


def default_data_dir():
    return Path(os.environ.get("LEMMATA_HOME") or "~/Lemmata").expanduser()


def write_private(path, data, mode=0o600):
    """Atomic write with the final mode set before the content lands (no world-readable window)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


class DataDir:
    def __init__(self, root=None):
        self.root = Path(root).expanduser() if root else default_data_dir()
        self.hub = self.root / "hub"
        self.projects = self.root / "projects"
        self.trash = self.root / "trash"
        self.tmp = self.root / "tmp"

    def ensure(self):
        for d in (self.root, self.hub, self.projects, self.trash, self.tmp):
            d.mkdir(mode=0o700, parents=True, exist_ok=True)  # private at creation; never chmod'ed afterwards
        return self

    @property
    def config_path(self):
        return self.hub / "config.json"

    @property
    def tokens_path(self):
        return self.hub / "tokens.json"

    @property
    def github_path(self):
        return self.hub / "github.json"

    @property
    def overleaf_path(self):
        return self.hub / "overleaf.json"

    @property
    def log_path(self):
        return self.hub / "hub.log"


class Config:
    def __init__(self, data: DataDir):
        self.data = data

    def load(self):
        c = dict(DEFAULTS)
        c.update(read_json(self.data.config_path, {}) or {})
        return c

    def update(self, **kw):
        c = read_json(self.data.config_path, {}) or {}
        c.update({k: v for k, v in kw.items() if v is not None or k == "owner"})
        write_private(self.data.config_path, json.dumps(c, indent=1) + "\n")
        return self.load()
