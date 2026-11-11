#!/usr/bin/env python3
"""Lemmata hook for Claude Code: log the experiments the coding agent runs.

Installed by the VS Code command "Lemmata: Set up coding agent" as <project>/.lemmata/hooks/log_run.py and registered in
.claude/settings.local.json for the Bash tool on PreToolUse, PostToolUse and PostToolUseFailure.

It reads the hook's JSON from stdin. When the command looks like an experiment (python train.py, sbatch job.sh, ...), it
writes a run manifest to <project>/.lemmata/runs/<run_id>.json: the command, the commit, whether there were uncommitted
changes, and hashes of the settings files named on the command line. The Lemmata extension sends that manifest to your
hub. It never reads data or weights, never sends anything itself, never blocks the agent and always exits 0.

Python 3.8+, standard library only.
"""
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime

LAUNCH = re.compile(
    r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*(?:(?:nohup|time|env|caffeinate)\s+)*(?:(?:uv|poetry|pdm|pixi|hatch)\s+run\s+|conda\s+run\s+(?:-\S+\s+\S+\s+)*)?"
    r"(?:python[0-9.]*|accelerate\s+launch|torchrun|sbatch|srun|julia|Rscript|(?:ba|z)?sh\s+\S+\.sh|\./\S+\.(?:sh|py))(?:\s|$)")
NOT_A_RUN = re.compile(
    r"(?:^|\s)python[0-9.]*\s+(?:-V\b|--version\b|-c\b|-m\s+(?:pip|venv|ensurepip|http\.server|pytest|unittest|ipykernel|jupyter|notebook|black|ruff|mypy|build|twine)\b)"
    r"|(?:^|\s)python[0-9.]*\s*$")
CONFIG = re.compile(r"^[\w./@+-]+\.(?:ya?ml|toml|json|cfg|ini|conf)$", re.I)
MAX_PATCH = 2 * 1024 * 1024


def segments(command):
    """'cd x && python train.py' -> the parts between &&, ;, || and |, so the launcher is found behind a cd."""
    return [s.strip() for s in re.split(r"&&|\|\||\||;|\n", command) if s.strip()]


def experiment(command):
    if not command or len(command) > 4000:
        return None
    pattern = os.environ.get("LEMMATA_RUN_PATTERN")
    try:
        launch = re.compile(pattern) if pattern else LAUNCH
    except re.error:
        launch = LAUNCH
    for seg in segments(command):
        if launch.search(seg) and not NOT_A_RUN.search(seg):
            return seg
    return None


def git(root, *args):
    try:
        r = subprocess.run(["git", "-C", root] + list(args), capture_output=True, timeout=8)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def iso(t):
    return datetime.fromtimestamp(t).astimezone().replace(microsecond=0).isoformat()


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def start(d, root, hub):
    command = (d.get("tool_input") or {}).get("command") or ""
    seg = experiment(command)
    if not seg:
        return
    now = time.time()
    cwd = d.get("cwd") or root
    head = git(root, "rev-parse", "HEAD")
    status = git(root, "status", "--porcelain", "--untracked-files=no")
    dirty = bool(status.strip()) if status is not None else None
    diff_hash = None
    if dirty:
        patch = git(root, "diff", "HEAD")
        if patch:
            diff_hash = sha(patch)
            if len(patch) <= MAX_PATCH:
                os.makedirs(os.path.join(hub, "patches"), exist_ok=True)
                with open(os.path.join(hub, "patches", diff_hash[7:23] + ".patch"), "wb") as f:
                    f.write(patch)
    configs = []
    for tok in seg.split():
        t = re.sub(r"^[^=\s]*=", "", tok).strip("\"'")
        if CONFIG.match(t) and ".." not in t:
            p = os.path.join(cwd, t)
            if os.path.isfile(p) and os.path.getsize(p) <= MAX_PATCH:
                with open(p, "rb") as f:
                    rel = os.path.relpath(p, root).replace(os.sep, "/")
                    configs.append({"path": rel, "hash": sha(f.read())})
    stamp = datetime.fromtimestamp(now).strftime("%Y-%m-%dT%H-%M-%S")
    run_id = stamp + "_" + hashlib.sha256(("%s\0%s\0%s" % (command, cwd, now)).encode()).hexdigest()[:4]
    man = {"run_id": run_id, "source": "agent", "command": command[:2000], "cwd": cwd, "host": socket.gethostname()[:100],
           "git_sha": head.decode().strip() if head else None, "dirty": dirty, "diff_hash": diff_hash, "configs": configs[:20], "metrics": {},
           "artifacts": [], "started": iso(now), "ended": None, "exit_code": None}
    os.makedirs(os.path.join(hub, "pending"), exist_ok=True)
    with open(os.path.join(hub, "pending", key(d) + ".json"), "w", encoding="utf-8") as f:
        json.dump(man, f)
    write(hub, man)


def key(d):
    k = d.get("tool_use_id") or hashlib.sha256(((d.get("tool_input") or {}).get("command") or "").encode()).hexdigest()
    return re.sub(r"[^A-Za-z0-9_-]", "", str(k))[:80] or "run"


def exit_code(d, failed):
    r = d.get("tool_response")
    if isinstance(r, dict):
        for k in ("exit_code", "exitCode", "returncode", "code"):
            v = r.get(k)
            if isinstance(v, int) and not isinstance(v, bool):
                return v
    return 1 if failed else None


def finish(d, hub, failed):
    p = os.path.join(hub, "pending", key(d) + ".json")
    if not os.path.isfile(p):
        return
    with open(p, "r", encoding="utf-8") as f:
        man = json.load(f)
    os.remove(p)
    current = os.path.join(hub, "runs", man["run_id"] + ".json")
    try:        # the extension may have added result files and numbers to the manifest while the command ran: keep them
        with open(current, "r", encoding="utf-8") as f:
            cur = json.load(f)
        if isinstance(cur, dict) and cur.get("run_id") == man["run_id"]:
            man = cur
    except (OSError, ValueError):
        pass
    background = bool((d.get("tool_input") or {}).get("run_in_background"))
    if not background:          # a background command has only been started: it has no end time or exit code yet
        man["ended"] = iso(time.time())
        man["exit_code"] = exit_code(d, failed)
    else:
        man["note"] = "started in the background"
    write(hub, man)


def write(hub, man):
    runs = os.path.join(hub, "runs")
    os.makedirs(runs, exist_ok=True)
    ignore = os.path.join(hub, ".gitignore")
    if not os.path.exists(ignore):
        with open(ignore, "w", encoding="utf-8") as f:
            f.write("*\n")
    tmp = os.path.join(runs, "." + man["run_id"] + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1)
    os.replace(tmp, os.path.join(runs, man["run_id"] + ".json"))


def main():
    try:
        d = json.load(sys.stdin)
        if not isinstance(d, dict) or d.get("tool_name") != "Bash":
            return
        root = os.environ.get("CLAUDE_PROJECT_DIR") or d.get("cwd") or os.getcwd()
        top = git(root, "rev-parse", "--show-toplevel")
        if top:
            root = top.decode().strip()
        hub = os.path.join(root, ".lemmata")
        event = d.get("hook_event_name")
        if event == "PreToolUse":
            start(d, root, hub)
        elif event in ("PostToolUse", "PostToolUseFailure"):
            finish(d, hub, event == "PostToolUseFailure")
    except Exception:       # a logging hook must never get in the agent's way
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
