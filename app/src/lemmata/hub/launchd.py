"""LaunchAgent for the Mac mini: ai.lemmata.hub."""
from __future__ import annotations

import os
import plistlib
from lemmata.hub.config import default_data_dir
import subprocess
import sys
import time
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


def temp_data(data_dir) -> bool:
    """True for a data folder inside the system's temporary space. The background service must never run from one:
    macOS deletes it, and the hub then rejects every device token (2026-11-12: a test pointed the live hub at one)."""
    import tempfile
    d = Path(data_dir).expanduser().resolve()
    roots = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve(), Path("/private/var/folders"), Path("/var/folders").resolve()}
    return any(d == r or r in d.parents for r in roots) and not os.environ.get("LEMMATA_ALLOW_TEMP_SERVICE")


def install(data_dir, port):
    from .config import DataDir
    if temp_data(data_dir):
        raise SystemExit("lemmata: refusing to run the background hub from a temporary folder (%s). Use your real data folder, e.g. ~/Lemmata." % data_dir)
    DataDir(data_dir).ensure()
    p = plist_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(plistlib.dumps(make_plist(data_dir, port)))
    domain = "gui/%d" % os.getuid()
    _stop(domain)  # idempotent re-install
    # bootstrap right after bootout can fail with "5: Input/output error" while launchd is still
    # tearing the old job down; retry for a few seconds before giving up.
    for attempt in range(8):
        r = _lc("bootstrap", domain, str(p))
        if r.returncode == 0:
            return p
        time.sleep(1.5)
        _stop(domain)
    raise SystemExit("lemmata: launchctl bootstrap failed: %s\n"
                     "Try: launchctl bootout %s/%s; sleep 5; lemmata hub install"
                     % ((r.stderr.strip() or r.stdout.strip()), domain, LABEL))


def _stop(domain):
    """bootout the job and wait (up to ~10 s) until launchd no longer knows it."""
    _lc("bootout", "%s/%s" % (domain, LABEL))
    for _ in range(20):
        if _lc("print", "%s/%s" % (domain, LABEL)).returncode != 0:
            return
        time.sleep(0.5)


def uninstall():
    _stop("gui/%d" % os.getuid())
    p = plist_path()
    existed = p.exists()
    if existed:
        p.unlink()
    return existed
