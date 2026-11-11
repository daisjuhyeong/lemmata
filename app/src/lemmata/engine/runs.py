"""Runs logged from where the work happens (VS Code terminal, a results-folder watcher, a coding agent's hook).

Most experiments never reach GitHub, so the commit history alone misses them. A run manifest is a small record of one run:
the command, the commit it ran on, whether the tree had uncommitted changes, hashes of the settings files, the numbers
it wrote and the paths of the files it wrote. Only the manifest is sent to the hub: no code, data or weights.

Stored in <hub>/runs.json, newest last. Rules only: no language model, nothing is run.
"""
import re
from datetime import datetime

from .errors import BadRequest

SCHEMA = "lemmata.runs/1"
SOURCES = ("terminal", "watcher", "agent")
MAX_RUNS, MAX_BATCH = 5000, 50
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{5,79}$")
SHA_RE = re.compile(r"^[0-9a-f]{7,64}$")
HASH_RE = re.compile(r"^(sha256:)?[0-9a-f]{8,64}$")
TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def load(hub):
    d = hub.read_json("runs.json", None)
    if not isinstance(d, dict):
        d = {}
    d.setdefault("schema", SCHEMA)
    if not isinstance(d.get("runs"), list):
        d["runs"] = []
    return d


def _text(m, key, limit, required=False):
    v = m.get(key)
    if v is None or v == "":
        if required:
            raise BadRequest("run.%s is required" % key)
        return None
    if not isinstance(v, str):
        raise BadRequest("run.%s must be text" % key)
    return v[:limit]


def _files(m, key, limit):
    out = []
    v = m.get(key) or []
    if not isinstance(v, list):
        raise BadRequest("run.%s must be a list" % key)
    for f in v[:limit]:
        if not isinstance(f, dict) or not isinstance(f.get("path"), str) or not f["path"]:
            raise BadRequest("run.%s entries need a path" % key)
        h = f.get("hash")
        if h is not None and not (isinstance(h, str) and HASH_RE.match(h)):
            raise BadRequest("run.%s hash must be a hex digest" % key)
        out.append({"path": f["path"].replace("\\", "/")[:300], "hash": h})
    return out


def clean(m):
    """One manifest as sent by a client -> the stored form. Raises BadRequest; unknown fields are dropped."""
    if not isinstance(m, dict):
        raise BadRequest("each run must be an object")
    rid = m.get("run_id")
    if not isinstance(rid, str) or not ID_RE.match(rid):
        raise BadRequest("run_id must be 6 to 80 letters, digits or _ . : -")
    src = m.get("source")
    if src not in SOURCES:
        raise BadRequest("run.source must be one of %s" % ", ".join(SOURCES))
    sha = m.get("git_sha")
    if sha is not None and not (isinstance(sha, str) and SHA_RE.match(sha)):
        raise BadRequest("run.git_sha must be a commit hash")
    dirty = m.get("dirty")
    if dirty is not None and not isinstance(dirty, bool):
        raise BadRequest("run.dirty must be true, false or null")
    dh = m.get("diff_hash")
    if dh is not None and not (isinstance(dh, str) and HASH_RE.match(dh)):
        raise BadRequest("run.diff_hash must be a hex digest")
    code = m.get("exit_code")
    if code is not None and (not isinstance(code, int) or isinstance(code, bool)):
        raise BadRequest("run.exit_code must be a number or null")
    metrics = m.get("metrics") or {}
    if not isinstance(metrics, dict):
        raise BadRequest("run.metrics must be an object of numbers")
    nums = {}
    for k, v in list(metrics.items())[:200]:
        if isinstance(k, str) and isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf"):
            nums[k[:120]] = v
    out = {"run_id": rid, "source": src, "command": _text(m, "command", 2000), "cwd": _text(m, "cwd", 500), "host": _text(m, "host", 100),
           "git_sha": sha, "dirty": dirty, "diff_hash": dh, "configs": _files(m, "configs", 20), "metrics": nums,
           "artifacts": _files(m, "artifacts", 50), "started": _text(m, "started", 40), "ended": _text(m, "ended", 40),
           "exit_code": code, "note": _text(m, "note", 500)}
    for k in ("started", "ended"):
        if out[k] is not None and not TIME_RE.match(out[k]):
            raise BadRequest("run.%s must be an ISO time" % k)
    if not out["command"] and not out["artifacts"]:
        raise BadRequest("a run needs a command or at least one file it wrote")
    return out


def add(store, runs, by, now):
    """Insert or update by run_id (a later report of the same run, e.g. with its numbers, replaces the earlier one)."""
    if not isinstance(runs, list) or not runs:
        raise BadRequest("runs must be a non-empty list")
    if len(runs) > MAX_BATCH:
        raise BadRequest("at most %d runs per request" % MAX_BATCH)
    cleaned = [clean(m) for m in runs]          # validate everything before changing anything
    index = {r["run_id"]: i for i, r in enumerate(store["runs"])}
    added = updated = 0
    for r in cleaned:
        r["received"], r["by"] = now, by
        i = index.get(r["run_id"])
        if i is None:
            index[r["run_id"]] = len(store["runs"])
            store["runs"].append(r)
            added += 1
        else:
            old = store["runs"][i]
            r["received"] = old.get("received", now)
            if not r["metrics"] and old.get("metrics"):
                r["metrics"] = old["metrics"]
            store["runs"][i] = r
            updated += 1
    if len(store["runs"]) > MAX_RUNS:
        store["runs"] = store["runs"][-MAX_RUNS:]
    return {"added": added, "updated": updated, "total": len(store["runs"])}


def _when(r):
    return r.get("ended") or r.get("started") or r.get("received") or ""


def view(store, nodes, events, roles, limit=200):
    """-> {"schema", "runs": [...newest first], "counts"}.
    Each run also says whether its commit is one the hub has seen (``in_github``) and which of the files it wrote
    are result files the hub already tracks (``tracked``), so a local run can be tied to the paper items that use that file."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
        raise BadRequest("limit must be 1 to 1000")
    revs = [e["rev"] for e in events if e.get("kind") == "commit" and e.get("rev") and roles.get(e.get("repo")) != "paper"]
    by_path = {}
    for nid, n in nodes.items():
        if roles.get(n.get("repo")) != "paper" and n.get("loc") and n.get("kind") in ("result", "data", "config", "code"):
            by_path.setdefault(n["loc"]["path"], {"node_id": nid, "name": n["name"], "kind": n["kind"]})
    rows = []
    for r in sorted(store["runs"], key=_when, reverse=True):
        sha = r.get("git_sha")
        known = bool(sha) and any(v.startswith(sha) or sha.startswith(v) for v in revs)
        tracked = [dict(by_path[a["path"]], path=a["path"]) for a in r["artifacts"] if a["path"] in by_path and by_path[a["path"]]["kind"] in ("result", "data")]
        state = ("failed" if r.get("exit_code") not in (None, 0) else "uncommitted" if r.get("dirty") else "not in github" if sha and not known
                 else "in github" if known else "unknown commit")
        rows.append(dict(r, time=_when(r), in_github=known, tracked=tracked, state=state))
    c = {"total": len(rows), "failed": sum(1 for x in rows if x["state"] == "failed"), "uncommitted": sum(1 for x in rows if x["state"] == "uncommitted"),
         "not_in_github": sum(1 for x in rows if x["state"] == "not in github"), "in_github": sum(1 for x in rows if x["state"] == "in github"),
         "with_numbers": sum(1 for x in rows if x["metrics"])}
    return {"schema": SCHEMA, "runs": rows[:limit], "counts": c}


def newer(time_iso, since_iso):
    """Is time_iso at or after since_iso? Compares instants when both parse (clients and the hub may be in different time zones)."""
    try:
        a, b = datetime.fromisoformat(time_iso), datetime.fromisoformat(since_iso)
        if (a.tzinfo is None) == (b.tzinfo is None):
            return a >= b
    except (TypeError, ValueError):
        pass
    return (time_iso or "") >= (since_iso or "")


def digest_line(rows, since_iso):
    """One line for the weekly digest, or None when no run was logged in the window."""
    recent = [r for r in rows if newer(r.get("time"), since_iso)]
    if not recent:
        return None
    off = sum(1 for r in recent if r["state"] in ("uncommitted", "not in github"))
    failed = sum(1 for r in recent if r["state"] == "failed")
    bits = ["%d run%s logged from the editor or the coding agent" % (len(recent), "" if len(recent) == 1 else "s")]
    if off:
        bits.append("%d on code that is not in GitHub" % off)
    if failed:
        bits.append("%d failed" % failed)
    return "• " + ", ".join(bits)
