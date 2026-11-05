"""Events (commit / run / worktree / snapshot / diverged), first-parent replay after the checkpoint,
message flags, and checkpoint snapshots."""
import re
from datetime import datetime

from . import graph as graphmod
from . import tree as treemod
from .errors import BadRequest

NO_CHANGE_RE = re.compile(
    r"no (functional |behavio(?:u)?r(?:al)? |output |numerical |result )?changes?|outputs? (are |is )?unchanged|"
    r"nothing (moved|changed)|byte[- ]identical|identical (outputs?|results)|refactor(?:ing)? only|cosmetic|"
    r"comments? only|no-op", re.I)
DERIVED_SUFFIXES = (".tex", ".bib", ".md")


def parse_time(s):
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def read_commits(path):
    """First-parent history, chronological: [{rev, time, message, subject, files:[{path,status,sha,mode}]}]."""
    fmt = "%x01%H%x00%cI%x00%B%x02"
    p = treemod.run_git(path, ["log", "--first-parent", "--no-renames", "--raw", "-r", "--no-abbrev", "--format=" + fmt, "HEAD"], check=False)
    if p.returncode != 0:
        return []
    out = []
    for rec in p.stdout.decode("utf-8", "replace").split("\x01")[1:]:
        head, _, rest = rec.partition("\x02")
        sha, when, msg = head.split("\x00", 2)
        files = []
        for line in rest.splitlines():
            if line.startswith(":") and "\t" in line:
                meta, fp = line.split("\t", 1)
                f = meta.split()
                files.append({"path": fp, "status": f[4][0], "sha": f[3], "mode": f[1]})
        msg = msg.strip()
        out.append({"rev": sha, "time": when, "message": msg, "subject": msg.split("\n", 1)[0], "files": files})
    out.reverse()
    return out


def flags_for(message, changed_count):
    if not changed_count:
        return []
    m = NO_CHANGE_RE.search(message or "")
    if not m:
        return []
    return [{"code": "message_claims_no_change", "confidence": "low", "phrase": m.group(0),
             "text": 'Message says "%s"; content changed in %d files.' % (m.group(0), changed_count)}]


def _short(rev):
    return rev[:7] if rev else None


def make_checkpoint(repos, infos, trees, G, cache, hub, cp_id, note, created_at, at, existing):
    """Build a checkpoint dict from the working tree (default) or from git revs (`at`)."""
    at = at or {}
    byid = {r["id"]: r for r in repos}
    revs = {}
    for rid, rev in at.items():
        if rid not in byid:
            raise BadRequest("unknown repo %r" % rid)
        if not infos[rid]["vcs"] == "git":
            raise BadRequest("repo %r is not a git repo; cannot checkpoint at a revision" % rid)
        full = treemod.rev_parse(infos[rid]["abs_path"], str(rev))
        if not full:
            raise BadRequest("revision %r not found in repo %r" % (rev, rid))
        revs[rid] = full
    snap = dict(trees)
    opened = []
    for rid, full in revs.items():
        t = treemod.GitTree(infos[rid]["abs_path"], rid, full)
        snap[rid] = t
        opened.append(t)
    try:
        Gs = graphmod.build(repos, snap, cache, {}, with_edges=False) if revs else G
        nodes = {}
        for n in Gs.node_list():
            path = n["loc"]["path"]
            tr = snap.get(n["repo"])
            blob = tr.blob_id(path) if (path and tr is not None) else None
            nodes[n["id"]] = {"hash": n["hash"], "kind": n["kind"], "repo": n["repo"], "path": path, "name": n["name"], "blob": blob}
        for rid, tr in snap.items():
            for p in tr.list_files():
                if p.startswith(".") or "/." in p or tr.size(p) > 1_000_000:
                    continue
                data = tr.read(p)
                if data is None or b"\0" in data[:8192]:
                    continue
                hub.put_blob(tr.blob_id(p), data)
    finally:
        for t in opened:
            t.close()
    crepos = {}
    for r in repos:
        rid = r["id"]
        if rid in revs:
            crepos[rid] = {"rev": revs[rid], "dirty": False}
        else:
            crepos[rid] = {"rev": infos[rid]["head"] if infos[rid]["vcs"] == "git" else None, "dirty": bool(infos[rid]["dirty"])}
    if not cp_id:
        nums = [int(c["id"][2:]) for c in existing if re.fullmatch(r"cp\d+", c["id"])]
        cp_id = "cp%d" % (max(nums) + 1 if nums else 1)
    return {"id": cp_id, "created_at": created_at, "note": note or "", "repos": crepos, "nodes": nodes}


def build_events(repos, infos, hist, cp, G, now_iso, cache):
    """-> (events, replay, internal) for the active checkpoint `cp` (or None).

    replay[repo_id] = [(event_id, {node_id: hash|None}), ...]  (states after each post-checkpoint event)
    """
    events = []
    replay = {}
    nodes = G.nodes
    h0 = {i: v["hash"] for i, v in cp["nodes"].items()} if cp else {}
    messages = {}
    for repo in repos:
        rid = repo["id"]
        info = infos[rid]
        commits = hist.get(rid, [])
        cp_repo = cp["repos"].get(rid) if cp else None
        cp_rev = cp_repo["rev"] if cp_repo else None
        idx = None
        mode = None   # post | diverged | snapshot | None
        if cp and cp_repo is not None:
            if info["vcs"] == "git":
                if cp_rev is None:
                    idx, mode = -1, "post"
                else:
                    pos = [i for i, c in enumerate(commits) if c["rev"] == cp_rev]
                    if pos:
                        idx, mode = pos[0], "post"
                    else:
                        mode = "diverged"
            else:
                mode = "snapshot"
        cevs = []
        for i, c in enumerate(commits):
            ev = {"id": "ev:commit:%s:%s" % (rid, c["rev"][:12]), "kind": "commit", "repo": rid, "rev": c["rev"], "short": _short(c["rev"]),
                  "time": c["time"], "subject": c["subject"], "files": [{"path": f["path"], "status": f["status"]} for f in c["files"]],
                  "at_checkpoint": bool(mode == "post" and idx is not None and idx >= 0 and i == idx),
                  "after_checkpoint": bool(mode == "post" and idx is not None and i > idx),
                  "changed_nodes": None, "flags": []}
            messages[ev["id"]] = c["message"]
            cevs.append(ev)
        events.extend(cevs)
        if mode is None:
            if info["dirty"]:
                events.append(_wt_event(rid, now_iso, info, False))
            continue
        # tracked ids for this repo
        tracked = {}
        for nid, n in nodes.items():
            if n["repo"] == rid:
                tracked[nid] = n["loc"]["path"]
        for nid, v in cp["nodes"].items():
            if v["repo"] == rid:
                tracked.setdefault(nid, v.get("path"))
        S_prev = {nid: h0.get(nid) for nid in tracked}
        states = []
        if mode == "post":
            post = commits[idx + 1:]
            blobmap = {}
            if cp_rev is not None:
                t0 = treemod.GitTree(info["abs_path"], rid, cp_rev)
                blobmap = {p: t0.blob_id(p) for p in t0.list_files()}
                t0.close()
            by_path = {}
            derived_ids = []
            for nid, p in tracked.items():
                if nid.startswith(("file:", "run:")) and p:
                    by_path.setdefault(p, []).append(nid)
                else:
                    derived_ids.append(nid)
            for j, c in enumerate(post):
                S = dict(S_prev)
                touched = False
                for f in c["files"]:
                    if f["status"] == "D":
                        blobmap.pop(f["path"], None)
                    elif f["mode"] != "160000":
                        blobmap[f["path"]] = f["sha"]
                    for nid in by_path.get(f["path"], ()):
                        S[nid] = ("blob:" + blobmap[f["path"]]) if f["path"] in blobmap else None
                    if f["path"].endswith(DERIVED_SUFFIXES):
                        touched = True
                if touched and derived_ids:
                    t = treemod.GitTree(info["abs_path"], rid, c["rev"])
                    try:
                        d = graphmod.derived_hashes(repo, t, cache)
                    finally:
                        t.close()
                    for nid in derived_ids:
                        S[nid] = d.get(nid)
                ev = cevs[idx + 1 + j]
                ev["changed_nodes"] = sorted(n for n in tracked if S[n] != S_prev[n] and (n in nodes))
                ev["_changed_all"] = sorted(n for n in tracked if S[n] != S_prev[n])
                states.append((ev["id"], S))
                S_prev = S
            S_cur = {nid: (nodes[nid]["hash"] if nid in nodes else None) for nid in tracked}
            wt = [nid for nid in tracked if S_cur[nid] != S_prev[nid]]
            if wt:
                ev = _wt_event(rid, now_iso, info, True)
                ev["changed_nodes"] = sorted(n for n in wt if n in nodes)
                ev["_changed_all"] = sorted(wt)
                events.append(ev)
                states.append((ev["id"], S_cur))
        else:
            S_cur = {nid: (nodes[nid]["hash"] if nid in nodes else None) for nid in tracked}
            ch = [nid for nid in tracked if S_cur[nid] != S_prev[nid]]
            if ch:
                kind = "snapshot" if mode == "snapshot" else "diverged"
                files = []
                for nid in ch:
                    p = tracked[nid]
                    if p and nid.startswith(("file:", "run:")):
                        files.append({"path": p, "status": "D" if S_cur[nid] is None else ("A" if S_prev[nid] is None else "M")})
                ev = {"id": "ev:%s:%s" % (kind, rid), "kind": kind, "repo": rid, "rev": None, "short": None, "time": now_iso,
                      "subject": "Non-git folder differs from the checkpoint" if kind == "snapshot" else "Checkpoint revision is not an ancestor of HEAD",
                      "files": sorted(files, key=lambda f: f["path"]), "at_checkpoint": False, "after_checkpoint": True,
                      "changed_nodes": sorted(n for n in ch if n in nodes), "_changed_all": sorted(ch), "flags": []}
                events.append(ev)
                states.append((ev["id"], S_cur))
        replay[rid] = states
    # run events
    cp_time = parse_time(cp["created_at"]) if cp else None
    changed_now = set()
    if cp:
        for nid, n in nodes.items():
            if n["repo"] in cp["repos"] and h0.get(nid) != n["hash"]:
                changed_now.add(nid)
    for rec in G.runs:
        t = parse_time(rec.get("started_at"))
        after = bool(cp_time and t and t.tzinfo and cp_time.tzinfo and t > cp_time)
        outs = []
        for p in rec["outputs"]:
            outs.append({"path": p, "status": "M"})
        events.append({"id": "ev:run:%s/%s" % (rec["repo"], rec["run_id"]), "kind": "run", "repo": rec["repo"], "rev": None, "short": None,
                       "time": rec.get("started_at") or "", "subject": "run %s: %s" % (rec["run_id"], rec["command"]),
                       "files": outs, "at_checkpoint": False, "after_checkpoint": after,
                       "changed_nodes": sorted(("file:%s/%s" % (rec["repo"], p["path"])) for p in outs
                                               if ("file:%s/%s" % (rec["repo"], p["path"])) in changed_now) if after else None,
                       "flags": []})
    # flags
    for ev in events:
        if ev["kind"] in ("commit", "worktree", "snapshot", "diverged"):
            cn = ev.get("_changed_all")
            n_changed = len(ev["changed_nodes"]) if ev["changed_nodes"] is not None else len(ev["files"])
            msg = messages.get(ev["id"], ev["subject"] if ev["kind"] == "commit" else "")
            if ev["kind"] == "commit":
                ev["flags"] = flags_for(msg, n_changed)
    internal = {ev["id"]: ev for ev in events}
    for ev in events:
        ev.pop("_changed_all", None)
    events.sort(key=lambda e: (_sort_time(e["time"]), e["id"]))
    return events, replay


def _sort_time(s):
    t = parse_time(s)
    if t is None:
        return (1, 0.0)
    if t.tzinfo is None:
        return (0, t.timestamp())
    return (0, t.timestamp())


def _wt_event(rid, now_iso, info, after):
    return {"id": "ev:worktree:%s" % rid, "kind": "worktree", "repo": rid, "rev": None, "short": None, "time": now_iso,
            "subject": "Uncommitted changes", "files": [{"path": p, "status": s} for s, p in info.get("status", [])],
            "at_checkpoint": False, "after_checkpoint": after, "changed_nodes": None, "flags": []}
