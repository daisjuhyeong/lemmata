"""Content-hash alarms grouped by cause (data-model 8)."""
from collections import deque

OUTPUT_KINDS = ("result", "asset")


def empty(now_iso):
    return {"schema": "lemmata.alarms/1", "computed_at": now_iso, "checkpoint": None, "excluded_repos": [], "groups": [],
            "summary": {"groups": 0, "changed": 0, "removed": 0, "downstream": 0, "flagged_nodes": 0}}


def _propagating_forward(edges):
    fwd = {}
    rev = {}
    for e in edges:
        if e["propagates"]:
            fwd.setdefault(e["from"], []).append(e)
            rev.setdefault(e["to"], []).append(e)
    return fwd, rev


def downstream_of(seeds, edges_fwd, edges_rev):
    """BFS against edge direction. -> {node: (depth, via_edge_id)}."""
    dist = {s: 0 for s in seeds}
    dq = deque(seeds)
    while dq:
        x = dq.popleft()
        for e in edges_rev.get(x, ()):
            if e["from"] not in dist:
                dist[e["from"]] = dist[x] + 1
                dq.append(e["from"])
    out = {}
    for n, d in dist.items():
        if d == 0:
            continue
        cands = sorted(e["id"] for e in edges_fwd.get(n, ()) if dist.get(e["to"]) == d - 1)
        out[n] = (d, cands[0])
    return out


def compute(cp, nodes, edges, events, replay, now_iso):
    """nodes: id -> node dict; edges: list of edge dicts; events: list; replay: repo -> [(event_id, state)]."""
    out = empty(now_iso)
    if not cp:
        return out
    out["checkpoint"] = {"id": cp["id"], "created_at": cp["created_at"], "note": cp["note"]}
    cp_repos = set(cp["repos"])
    out["excluded_repos"] = sorted({n["repo"] for n in nodes.values()} - cp_repos)
    H0 = {i: v["hash"] for i, v in cp["nodes"].items() if v["repo"] in cp_repos}
    H = {i: n["hash"] for i, n in nodes.items() if n["repo"] in cp_repos}
    ev_by_id = {e["id"]: e for e in events}
    fwd, rev = _propagating_forward(edges)

    groups = {}   # event_id -> {"changed": [...], "removed": [...]}

    def cause_of(nid, repo):
        states = replay.get(repo, [])
        h0 = H0.get(nid)
        start = None
        prev = h0
        hs = []
        for j, (eid, S) in enumerate(states):
            h = S.get(nid)
            hs.append(h)
            if h != h0:
                if start is None:
                    start = j
            else:
                start = None
            prev = h
        if start is None:
            return None, []
        also = []
        for j in range(start + 1, len(states)):
            if hs[j] != hs[j - 1]:
                also.append(states[j][0])
        return states[start][0], also

    for nid, n in sorted(nodes.items()):
        if n["repo"] not in cp_repos:
            continue
        if nid not in H0:
            change = "added"
        elif H0[nid] != H[nid]:
            change = "content_changed"
        else:
            continue
        eid, also = cause_of(nid, n["repo"])
        if eid is None:
            continue
        g = groups.setdefault(eid, {"changed": [], "removed": []})
        g["changed"].append({"node_id": nid, "change": change, "hash_checkpoint": H0.get(nid), "hash_now": H[nid], "also_changed_in": also})
    for nid, v in sorted(cp["nodes"].items()):
        if v["repo"] in cp_repos and nid not in nodes:
            eid, also = cause_of(nid, v["repo"])
            if eid is None:
                continue
            g = groups.setdefault(eid, {"changed": [], "removed": []})
            g["removed"].append({"node_id": nid, "name": v.get("name"), "path": v.get("path"), "kind": v.get("kind")})

    items = []
    for eid, g in groups.items():
        ev = ev_by_id[eid]
        items.append((_key(ev), eid, g, ev))
    items.sort(key=lambda t: t[0])
    flagged = set()
    n_down = 0
    for i, (_, eid, g, ev) in enumerate(items, 1):
        seeds = [c["node_id"] for c in g["changed"]]
        dn = downstream_of(seeds, fwd, rev) if seeds else {}
        down = []
        for nid, (d, via) in dn.items():
            n = nodes[nid]
            oi = None
            if n["kind"] in OUTPUT_KINDS:
                oi = H0.get(nid) == n["hash"]
            down.append({"node_id": nid, "depth": d, "via": via, "output_identical": oi})
        down.sort(key=lambda x: (x["depth"], x["node_id"]))
        g["changed"].sort(key=lambda c: c["node_id"])
        flagged.update(seeds)
        flagged.update(x["node_id"] for x in down)
        n_down += len(down)
        out["groups"].append({
            "id": eid, "display": "A%d" % i,
            "cause": {"event_id": eid, "kind": ev["kind"], "repo": ev["repo"], "rev": ev["rev"], "short": ev["short"], "time": ev["time"],
                      "subject": ev["subject"], "files": [f["path"] for f in ev["files"]]},
            "changed": g["changed"], "removed": g["removed"], "downstream": down, "flags": ev.get("flags", [])})
    out["summary"] = {"groups": len(items), "changed": sum(len(g["changed"]) for _, _, g, _ in items),
                      "removed": sum(len(g["removed"]) for _, _, g, _ in items), "downstream": n_down, "flagged_nodes": len(flagged)}
    return out


def _key(ev):
    from .history import _sort_time
    return (_sort_time(ev["time"]), ev["id"])
