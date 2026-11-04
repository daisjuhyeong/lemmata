"""Node/edge assembly (data-model 3, 4, 11)."""
import fnmatch
import posixpath
import re

from . import bib as bibmod
from . import code as codemod
from . import latex as lx
from . import refs as refsmod
from .classify import BINARY_EXT, classify, ext_of, is_run_record

LAYERS = {"thesis": 0, "rq": 1, "section": 2, "figure": 3, "table": 3, "equation": 3, "item": 3,
          "asset": 4, "result": 4, "run": 5, "code": 6, "config": 6, "data": 6, "doc": 6, "reference": None}
PROPAGATING = {"includes", "generated_by", "traces_to", "produced_by", "executes", "reads", "imports", "value_match"}
TEXT_KINDS = {"result", "data", "doc", "config"}


class Graph:
    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.warnings = []
        self.paper = None          # latex.Paper
        self.paper_repo = None
        self.bib_entries = []
        self.units = {}            # unit key -> node id

    # -- output -------------------------------------------------------------------------------
    def node_list(self):
        return sorted(self.nodes.values(), key=lambda n: (1 if n["layer"] is None else 0, n["layer"] if n["layer"] is not None else 0, n["id"]))

    def edge_list(self):
        return [self.edges[k] for k in sorted(self.edges)]


def mk_node(id_, kind, repo, name, path=None, line=None, end_line=None, detail="", hash_=None, attrs=None):
    return {"id": id_, "kind": kind, "layer": LAYERS[kind], "repo": repo, "name": name, "detail": (detail or "")[:120],
            "loc": {"path": path, "line": line, "end_line": end_line}, "hash": hash_, "attrs": attrs or {}}


def find_main(tree, hint=None):
    if hint and tree.has(hint):
        return hint
    cands = []
    for p in tree.list_files():
        if p.endswith(".tex") and not p.startswith("."):
            data = tree.read(p)
            if data is None:
                continue
            t = data.decode("utf-8", "replace")
            if "\\documentclass" in t and "\\begin{document}" in t:
                cands.append(p)
    if not cands:
        return None
    for p in cands:
        if posixpath.basename(p) == "main.tex" and "/" not in p:
            return p
    return sorted(cands)[0]


def _excluded(path, patterns):
    return any(fnmatch.fnmatch(path, pat) for pat in patterns or [])


# ------------------------------------------------------------------ paper + items (also used by replay)
def paper_nodes(repo, tree, cache):
    """-> (nodes list, Paper|None, bib_entries, include_targets)."""
    rid = repo["id"]
    main = find_main(tree, repo.get("main_tex"))
    if main is None:
        return [], None, [], []
    P = lx.parse_paper(tree, main, rid)
    nodes = []
    for u in P.units:
        ln = P.lines[u["begin"]]
        loc = dict(path=ln.path, line=ln.no, end_line=u["end_line"])
        k = u["kind"]
        attrs = {}
        if k == "thesis":
            attrs = {"text": u["text"]}
        elif k == "section":
            attrs = {"tex_label": u["label"], "level": u["level"], "number": u.get("number"),
                     "in_appendix": u["in_appendix"], "title": u["title"]}
        elif k in ("figure", "table"):
            attrs = {"tex_label": u["label"], "number": u["number"], "in_appendix": u["in_appendix"],
                     "caption": u["caption"], "manual": bool(u.get("manual")), "assets": []}
        else:
            attrs = {"tex_label": u["label"], "number": u.get("number")}
        nodes.append(mk_node(u["id"], k, rid, u["name"], detail=u["detail"], hash_=u["hash"], attrs=attrs, **loc))
    for name, idx in sorted(P.rqs.items()):
        ln = P.lines[idx]
        text = re.sub(r"\s+", " ", ln.code).strip()
        nodes.append(mk_node("rq:" + name, "rq", rid, name, ln.path, ln.no, ln.no, text, lx.norm_hash([ln.code]), {"text": text[:200]}))
    entries = []
    for p in tree.list_files():
        if p.endswith(".bib") and not p.startswith("."):
            data = tree.read(p)
            if data is not None:
                entries += bibmod.parse_bib(data.decode("utf-8", "replace"), p)
    seen = set()
    uniq_entries = []
    for e in entries:
        if e["key"] in seen:
            continue
        seen.add(e["key"])
        uniq_entries.append(e)
        nodes.append(mk_node("ref:" + e["key"], "reference", rid, "[%s]" % e["key"], e["path"], e["line"], None, e["title"], e["hash"],
                             {"bib_key": e["key"], "title": e["title"], "year": e["year"], "doi": e["doi"],
                              "lookup": refsmod.lookup_state(cache, e)}))
    inc = []
    for kind, raw, idx in P.includes:
        if kind == "graphics":
            path = lx.resolve_graphics(tree, main, raw)
        else:
            ln = P.lines[idx]
            path = None
            for d in (posixpath.dirname(main), posixpath.dirname(ln.path)):
                for cand in (raw, raw + ".tex"):
                    p = posixpath.normpath(posixpath.join(d, cand))
                    if tree.has(p):
                        path = p
                        break
                if path:
                    break
        inc.append((kind, raw, idx, path))
    return nodes, P, uniq_entries, inc


def item_rows(repo, tree, fileset):
    rows = []
    for p in sorted(fileset):
        if ext_of(p) in ("md", "rst") and not p.startswith(".") and p.endswith(".md"):
            data = tree.read(p)
            if data is None or b"|" not in data:
                continue
            for r in codemod.readme_tables(p, data.decode("utf-8", "replace"), fileset):
                r["path"] = p
                rows.append(r)
    return rows


def item_nodes(repo, rows):
    rid = repo["id"]
    out = {}
    for r in rows:
        for ref, slug in r["items"]:
            nid = "item:%s/%s" % (rid, slug)
            if nid not in out:
                out[nid] = mk_node(nid, "item", rid, "%s (README)" % ref, r["path"], r["line"], r["line"], r["text"].strip().strip("|").strip(),
                                   r["hash"], {"paper_ref": ref, "source_row": r["text"].strip()})
    return list(out.values())


def derived_hashes(repo, tree, cache=None):
    """id -> hash for non-file nodes of one repo at a tree (used by replay)."""
    out = {}
    if repo["role"] == "paper":
        nodes, _, _, _ = paper_nodes(repo, tree, cache or {"entries": {}})
        for n in nodes:
            out[n["id"]] = n["hash"]
    fs = set(tree.list_files())
    for n in item_nodes(repo, item_rows(repo, tree, fs)):
        out[n["id"]] = n["hash"]
    return out


# ------------------------------------------------------------------ build
def build(repos, trees, cache, decisions, with_edges=True):
    G = Graph()
    cache = cache or {"entries": {}}
    G.cache = cache
    decisions = decisions or {}
    filesets = {}
    # 1. file-backed nodes and run records
    runs = []
    for repo in repos:
        rid, tree = repo["id"], trees[repo["id"]]
        fs = set()
        for p in tree.list_files():
            if _excluded(p, repo.get("exclude")):
                continue
            fs.add(p)
            size = tree.size(p)
            if is_run_record(p):
                raw = tree.read(p)
                rec = codemod.read_run_record(raw, p) if raw is not None else None
                if rec:
                    rec["repo"] = rid
                    rec["blob"] = tree.blob_id(p)
                    runs.append(rec)
                continue
            kind = classify(p, size)
            if not kind:
                continue
            ext = ext_of(p)
            attrs = {"size": size, "ext": ext}
            if kind in ("asset", "result", "data"):
                attrs["binary"] = ext in BINARY_EXT
            G.nodes["file:%s/%s" % (rid, p)] = mk_node("file:%s/%s" % (rid, p), kind, rid, p, p, None, None, "", "blob:" + tree.blob_id(p), attrs)
        filesets[rid] = fs
    for rec in runs:
        base = "run:%s/%s" % (rec["repo"], rec["run_id"])
        nid, c = base, 1
        while nid in G.nodes:
            c += 1
            nid = "%s~%d" % (base, c)
        rec["node_id"] = nid
        G.nodes[nid] = mk_node(nid, "run", rec["repo"], "run " + rec["run_id"], rec["path"], None, None, rec["command"],
                               "blob:" + rec["blob"], {"command": rec["command"], "started_at": rec["started_at"]})
    G.runs = runs
    # 2. paper
    inc_targets = []
    P = None
    for repo in repos:
        if repo["role"] != "paper" or G.paper is not None:
            continue
        tree = trees[repo["id"]]
        nodes, P, entries, inc = paper_nodes(repo, tree, cache)
        if P is None:
            G.warnings.append({"code": "no_main_tex", "message": "paper repo %s has no main .tex file" % repo["id"], "evidence": None})
            continue
        G.paper, G.paper_repo, G.bib_entries = P, repo, entries
        G.paper_tree = tree
        for n in nodes:
            G.nodes[n["id"]] = n
        for u in P.units:
            G.units[u["key"]] = u["id"]
        for kind, raw, idx, path in inc:
            if path is None:
                if kind == "graphics":
                    G.warnings.append({"code": "asset_missing", "message": "%s not found" % raw, "evidence": P.ev(idx, "include")})
                continue
            nid = "file:%s/%s" % (repo["id"], path)
            if nid not in G.nodes:
                tr = trees[repo["id"]]
                G.nodes[nid] = mk_node(nid, "asset", repo["id"], path, path, None, None, "", "blob:" + tr.blob_id(path),
                                       {"size": tr.size(path), "ext": ext_of(path), "binary": False})
            inc_targets.append((idx, nid))
            k = P.owner[idx]
            if k is not None and P.units[k]["kind"] in ("figure", "table"):
                a = G.nodes[G.units[k]]["attrs"]["assets"]
                if path not in a:
                    a.append(path)
    # 3. items
    all_items = []
    for repo in repos:
        rows = item_rows(repo, trees[repo["id"]], filesets[repo["id"]])
        for n in item_nodes(repo, rows):
            G.nodes.setdefault(n["id"], n)
        all_items.append((repo, rows))
    if not with_edges:
        return G

    def add_edge(frm, to, kind, ev, status="detected", reason=None):
        if frm not in G.nodes or to not in G.nodes or frm == to:
            return None
        eid = "%s|%s|%s" % (frm, kind, to)
        e = G.edges.get(eid)
        if e is None:
            e = {"id": eid, "from": frm, "to": to, "kind": kind, "status": status, "propagates": False, "evidence": [], "reason": reason}
            G.edges[eid] = e
        if ev and ev not in e["evidence"]:
            e["evidence"].append(ev)
        return e

    def struct_ev(nid):
        n = G.nodes[nid]
        P_ = G.paper
        txt = ""
        if n["loc"]["line"] and P_:
            for ln in P_.lines:
                if ln.path == n["loc"]["path"] and ln.no == n["loc"]["line"]:
                    txt = ln.raw.rstrip()[:300]
                    break
        return {"repo": n["repo"], "path": n["loc"]["path"], "line": n["loc"]["line"], "text": txt, "role": "structure", "page": None}

    if P is not None:
        rid = G.paper_repo["id"]
        thesis_id = next((u["id"] for u in P.units if u["kind"] == "thesis"), None)
        for u in P.units:
            if u["parent"] is not None:
                add_edge(G.units[u["parent"]], u["id"], "contains", struct_ev(u["id"]))
        if thesis_id:
            for name in P.rqs:
                add_edge(thesis_id, "rq:" + name, "contains", P.ev(P.rqs[name], "structure"))
        for name, ukeys in P.rq_mentions.items():
            for k in sorted(ukeys):
                u = P.units[k]
                if u["kind"] != "section":
                    continue
                for i in u["owned"]:
                    if re.search(r"\bRQ\s?%s\b" % name[2:], P.lines[i].code):
                        add_edge("rq:" + name, u["id"], "answers", P.ev(i, "mention"))
                        break
        for lab, idx in P.refs:
            k = P.owner[idx]
            tgt = P.labels.get(lab)
            if k is None or tgt is None or tgt[0] is None or tgt[0] == k:
                continue
            add_edge(G.units[k], G.units[tgt[0]], "refs", P.ev(idx, "ref"))
        for key, idx in P.cites:
            k = P.owner[idx]
            if k is not None:
                add_edge(G.units[k], "ref:" + key, "cites", P.ev(idx, "cite"))
        for idx, nid in inc_targets:
            k = P.owner[idx]
            if k is not None:
                add_edge(G.units[k], nid, "includes", P.ev(idx, "include"))
        # markers
        code_repos = [r["id"] for r in repos if r["id"] != rid]
        repo_ids = {r["id"] for r in repos}
        for kind, toks, idx, k in P.markers:
            for tok in toks:
                if tok.lower() == "manual":
                    continue
                target = None
                if ":" in tok and tok.split(":", 1)[0] in repo_ids:
                    r_, p_ = tok.split(":", 1)
                    cand = ["file:%s/%s" % (r_, posixpath.normpath(p_.lstrip("/")))]
                else:
                    p_ = posixpath.normpath(tok.lstrip("/"))
                    cand = ["file:%s/%s" % (r_, p_) for r_ in [rid] + code_repos]
                hits = [c for c in cand if c in G.nodes]
                if len(hits) == 1:
                    target = hits[0]
                if target is None:
                    G.warnings.append({"code": "marker_target_missing" if not hits else "marker_target_ambiguous",
                                       "message": "%% %s: %s %s" % (kind, tok, "not found" if not hits else "is ambiguous"),
                                       "evidence": P.ev(idx, "marker")})
                    continue
                add_edge(G.units[k], target, "generated_by" if kind == "generated-by" else "traces_to", P.ev(idx, "marker"))

    # run records
    for rec in G.runs:
        rid_, nid = rec["repo"], rec["node_id"]
        rtree = trees[rid_]

        ev_base = {"repo": rid_, "path": rec["path"], "line": 1, "text": (rtree.read(rec["path"]) or b"").decode("utf-8", "replace").splitlines()[0][:300] if rtree.read(rec["path"]) else "", "role": "run_record", "page": None}
        for what, paths in (("script", [rec["script"]] if rec["script"] else []), ("reads", rec["inputs"]), ("outputs", rec["outputs"])):
            for p in paths:
                p = posixpath.normpath(p)
                tid = "file:%s/%s" % (rid_, p)
                if tid not in G.nodes:
                    G.warnings.append({"code": "run_target_missing", "message": "run %s: %s not found" % (rec["run_id"], p), "evidence": ev_base})
                    continue
                if what == "script":
                    add_edge(nid, tid, "executes", ev_base)
                elif what == "reads":
                    add_edge(nid, tid, "reads", ev_base)
                else:
                    add_edge(tid, nid, "produced_by", ev_base)

    # python imports + write calls
    for repo in repos:
        rid_, tree = repo["id"], trees[repo["id"]]
        fs = filesets[rid_]
        for p in sorted(fs):
            if not p.endswith(".py"):
                continue
            nid = "file:%s/%s" % (rid_, p)
            if nid not in G.nodes:
                continue
            data = tree.read(p)
            if data is None:
                continue
            src = data.decode("utf-8", "replace")
            lines = src.splitlines()
            for tgt, ln in codemod.python_imports(p, src, fs):
                tid = "file:%s/%s" % (rid_, tgt)
                add_edge(nid, tid, "imports", {"repo": rid_, "path": p, "line": ln, "text": lines[ln - 1].rstrip()[:300], "role": "import", "page": None})
            for out, ln in codemod.write_calls(p, src, fs):
                add_edge("file:%s/%s" % (rid_, out), nid, "produced_by",
                         {"repo": rid_, "path": p, "line": ln, "text": lines[ln - 1].rstrip()[:300], "role": "write_call", "page": None})

    # README provenance
    for repo, rows in all_items:
        rid_ = repo["id"]
        for r in rows:
            for ref, slug in r["items"]:
                iid = "item:%s/%s" % (rid_, slug)
                for sp in r["scripts"]:
                    add_edge(iid, "file:%s/%s" % (rid_, sp), "generated_by",
                             {"repo": rid_, "path": r["path"], "line": r["line"], "text": r["text"].rstrip()[:300], "role": "readme", "page": None})

    # value_match proposals
    if P is not None:
        configs = []
        for n in G.nodes.values():
            if n["kind"] == "config":
                data = trees[n["repo"]].read(n["loc"]["path"])
                if data is None or len(data) > 2_000_000:
                    continue
                text = data.decode("utf-8", "replace")
                keys = {}
                for dotted, (val, ln) in codemod.config_keys(n["loc"]["path"], text).items():
                    nm = codemod.canonical_key(dotted)
                    if nm in lx.HP_ALIASES and nm not in keys:
                        keys[nm] = (val, ln)
                if keys:
                    configs.append((n, keys, text.splitlines()))
        for u in P.units:
            if u["kind"] not in ("section", "table"):
                continue
            ment = {}
            for name, idx, val in P.hparams:
                if P.owner[idx] != u["key"]:
                    continue
                if name not in ment or (ment[name][1] is None and val is not None):
                    ment[name] = (idx, val)
            if not ment:
                continue
            for cn, keys, clines in configs:
                common = sorted(set(ment) & set(keys))
                if not common:
                    continue
                parts, evs = [], []
                for nm in common:
                    idx, val = ment[nm]
                    pv = (lx.fmt_number(val) if isinstance(val, float) else val) if val is not None else "?"
                    parts.append("%s: paper %s, config %s" % (nm, pv, keys[nm][0]))
                    evs.append(P.ev(idx, "appendix" if u.get("in_appendix") else "main"))
                    cl = keys[nm][1]
                    evs.append({"repo": cn["repo"], "path": cn["loc"]["path"], "line": cl, "text": clines[cl - 1].rstrip()[:300] if cl <= len(clines) else "", "role": "config", "page": None})
                e = None
                for ev in evs:
                    e = add_edge(u["id"], cn["id"], "value_match", ev, status="proposed", reason="; ".join(parts))
    # decisions + propagation flag
    for eid, e in G.edges.items():
        d = decisions.get(eid)
        if e["kind"] == "value_match" and d and d.get("decision") in ("approved", "rejected", "proposed"):
            e["status"] = d["decision"]
        e["propagates"] = e["kind"] in PROPAGATING and e["status"] in ("detected", "approved")
        e["evidence"] = e["evidence"][:12]
    return G
