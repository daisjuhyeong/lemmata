"""LaunchAgent for the Mac mini: ai.lemmata.hub."""
from __future__ import annotations

import os
import plistlib
from lemmata.hub.config import default_data_dir
import subprocess
import sys
from pathlib import Path

LABEL = "ai.lemmata.hub"
PATH_ENV = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"


def plist_path():
    return Path("~/Library/LaunchAgents/%s.plist" % LABEL).expanduser()


def make_plist(data_dir, port):
    data_dir = (Path(data_dir).expanduser() if data_dir else default_data_dir()).resolve()
    log = str(data_dir / "hub" / "hub.log")
    return {"Label": LABEL,
            "ProgramArguments": [sys.executable, "-m", "lemmata", "hub", "serve", "--data", str(data_dir), "--port", str(port)],
            "RunAtLoad": True, "KeepAlive": True, "StandardOutPath": log, "StandardErrorPath": log,
            "EnvironmentVariables": {"PATH": PATH_ENV}, "WorkingDirectory": str(data_dir)}


def _lc(*args):
    return subprocess.run(["launchctl"] + list(args), capture_output=True, text=True)


def install(data_dir, port):
    from .config import DataDir
    DataDir(data_dir).ensure()
    p = plist_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(plistlib.dumps(make_plist(data_dir, port)))
    domain = "gui/%d" % os.getuid()
    _lc("bootout", "%s/%s" % (domain, LABEL))  # idempotent re-install
    r = _lc("bootstrap", domain, str(p))
    if r.returncode != 0:
        raise SystemExit("lemmata: launchctl bootstrap failed: %s" % (r.stderr.strip() or r.stdout.strip()))
    return p


def uninstall():
    _lc("bootout", "gui/%d/%s" % (os.getuid(), LABEL))
    p = plist_path()
    existed = p.exists()
    if existed:
        p.unlink()
    return existed
