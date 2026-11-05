"""Find a working git binary for a GUI app (Finder-launched macOS apps get a minimal PATH)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

FALLBACKS = ("/usr/bin/git", "/opt/homebrew/bin/git", "/usr/local/bin/git")


def _clt_installed():
    """On macOS /usr/bin/git is a shim that opens an install dialog when Command Line Tools are missing."""
    try:
        return subprocess.run(["xcode-select", "-p"], capture_output=True, stdin=subprocess.DEVNULL, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _works(path, check_shim):
    if not (os.path.isfile(path) and os.access(path, os.X_OK)):
        return False
    if check_shim and os.path.realpath(path) == "/usr/bin/git" and not _clt_installed():
        return False
    try:
        return subprocess.run([path, "--version"], capture_output=True, stdin=subprocess.DEVNULL, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def find_git():
    """Absolute path of a usable git, or None. Never hangs on the macOS shim."""
    cands = []
    w = shutil.which("git")
    if w:
        cands.append(w)
    cands += [c for c in FALLBACKS if c not in cands]
    for c in cands:
        if _works(c, sys.platform == "darwin"):
            return c
    return None


def ensure_git():
    """Return the git path and put its folder first on PATH so every `git` subprocess finds it; None if missing."""
    g = find_git()
    if g:
        d = os.path.dirname(g)
        parts = os.environ.get("PATH", "").split(os.pathsep)
        if d not in parts:
            os.environ["PATH"] = os.pathsep.join([d] + [p for p in parts if p])
    return g


def restore_loader_env():
    """A PyInstaller bundle overrides LD_LIBRARY_PATH; restore the original for child processes such as git."""
    for k in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        orig = os.environ.get(k + "_ORIG")
        if orig is not None:
            os.environ[k] = orig
        elif getattr(sys, "frozen", False) and k in os.environ:
            del os.environ[k]
