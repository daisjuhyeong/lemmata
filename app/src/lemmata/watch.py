"""--watch: cheap change detection and rescan under the server lock.

Fingerprint per repo = git HEAD + `git status --porcelain` + mtimes of non-ignored files (never `.lemmata/`).
Rescans happen at most once per MIN_GAP seconds; a failing rescan is logged to stderr and the last good data stays.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

from lemmata.engine.tree import run_git

INTERVAL = 3.0
MIN_GAP = 3.0
HUB = ".lemmata"
MAX_FILES = 20000
SKIP_DIRS = {"node_modules", "__pycache__", ".git", HUB}


def _git_files(path):
    p = run_git(path, ["ls-files", "-z", "--cached", "--others", "--exclude-standard"], check=False)
    if p.returncode != 0:
        return None
    return [f for f in p.stdout.decode("utf-8", "replace").split("\0") if f and not f.startswith(HUB + "/")]


def _walk_files(path):
    out = []
    for dp, dns, fns in os.walk(path):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".")]
        out += [os.path.relpath(os.path.join(dp, f), path) for f in fns if not f.startswith(".")]
        if len(out) > MAX_FILES:
            break
    return out


def fingerprint(repos):
    """Hashable summary of the on-disk state of every repo; cheap enough to run every 3 s."""
    fp = []
    for r in repos:
        root = r["abs_path"]
        if not os.path.isdir(root):
            fp.append((r["id"], "missing"))
            continue
        head = status = None
        files = None
        if r.get("vcs") == "git":
            h = run_git(root, ["rev-parse", "HEAD"], check=False)
            head = h.stdout.decode("utf-8", "replace").strip() if h.returncode == 0 else None
            s = run_git(root, ["status", "--porcelain"], check=False)
            status = "\n".join(l for l in s.stdout.decode("utf-8", "replace").splitlines() if HUB + "/" not in l)
            files = _git_files(root)
        if files is None:
            files = _walk_files(root)
        mt = []
        for f in files[:MAX_FILES]:
            try:
                st = os.stat(os.path.join(root, f))
                mt.append((f, st.st_mtime_ns, st.st_size))
            except OSError:
                mt.append((f, None, None))
        fp.append((r["id"], head, status, hash(tuple(sorted(mt)))))
    return tuple(fp)


class Watcher(threading.Thread):
    def __init__(self, app, interval=INTERVAL, min_gap=MIN_GAP):
        super().__init__(name="lemmata-watch", daemon=True)
        self.app, self.interval, self.min_gap = app, interval, min_gap
        self.stop_event = threading.Event()
        self.rescans = 0
        self._last_scan = 0.0
        self._last_fp = self._fp()

    def _fp(self):
        try:
            return fingerprint(self.app.engine.project().get("repos", []))
        except Exception as e:  # never let a probe kill the watcher
            print("lemmata: watch: probe failed: %s" % e, file=sys.stderr, flush=True)
            return self._last_fp if hasattr(self, "_last_fp") else None

    def tick(self):
        """One poll. Returns True when a rescan was attempted."""
        fp = self._fp()
        if fp == self._last_fp:
            return False
        if time.monotonic() - self._last_scan < self.min_gap:
            return False
        if not self.app.lock.acquire(blocking=False):  # a manual scan or write is running; retry next tick
            return False
        try:
            self._last_scan = time.monotonic()
            try:
                self.app.engine.scan()
                self.rescans += 1
            except Exception as e:  # keep serving the last good scan
                print("lemmata: watch: rescan failed (keeping previous data): %s: %s" % (type(e).__name__, e), file=sys.stderr, flush=True)
        finally:
            self.app.lock.release()
        self._last_fp = fp  # the pre-scan fingerprint, so edits made during the scan trigger another one
        return True

    def run(self):
        while not self.stop_event.wait(self.interval):
            try:
                self.tick()
            except Exception as e:
                print("lemmata: watch: %s: %s" % (type(e).__name__, e), file=sys.stderr, flush=True)

    def stop(self):
        self.stop_event.set()
