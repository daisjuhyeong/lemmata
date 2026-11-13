"""Setup (S23): the metrics, datasets and methods the experiments use, and how each experiment uses them.

Read from the Experiments document (each experiment carries a small "grid": a row per method, a column per dataset,
the main metric and the other measures in its files), so the Setup page never disagrees with the Experiments page.
For every item: which experiments use it and in what role, which claims those experiments test, where the paper and
the code mention it, and a few checks (a metric read in two directions, a baseline missing on some datasets, a dataset
or method the paper never names). Rules only: no language model, nothing is run.
"""
import re

from .claims import detex
from .experiments import norm
from .latex import CITE_RE

SCHEMA = "lemmata.setup/1"
AVG = "Average"
MAX_HITS, MAX_CODE_BYTES, MAX_SCAN_FILES = 4, 400 * 1024, 400
KINDS = ("metric", "dataset", "method")


def _key(kind, name):
    return kind + ":" + (norm(name) or name.strip().lower())


def _better(a, b, lower, target):
    """Is value a better than value b? None when either is missing."""
    if a is None or b is None:
        return None
    if target is not None:
        a, b = abs(a - target), abs(b - target)
    return a < b if lower else a > b


def _rank(vals, v, lower, target):
    """1-based rank of v among vals (ties share the better rank)."""
    return 1 + sum(1 for o in vals if _better(o, v, lower, target))


def _split(col, g):
    """A grid column -> (dataset or None, metric). The Average column -> (AVG, metric)."""
    if col == AVG:
        return AVG, g["metric"]
    if " · " in col:
        ds, mt = col.rsplit(" · ", 1)
        return ds, mt
    if col in g["datasets"]:
        return col, g["metric"]
    return None, col


def _tokens(name, aliases=()):
    out = []
    for n in [name] + list(aliases or []):
        t = " ".join(str(n or "").lower().split())
        if len(t) >= 2 and t not in out:
            out.append(t)
    return out


def _word_re(tok):
    variants = {tok, tok.replace("-", "_"), tok.replace("_", "-"), tok.replace(" ", "_"), tok.replace(" ", "-")}
    alt = "|".join(re.escape(v) for v in sorted(variants, key=len, reverse=True))
    return re.compile(r"(?<![a-z0-9])(?:%s)(?![a-z0-9])" % alt)


def _code_re(tok):
    """In code a short name ("fp", "ae") must be a string or a keyword, or it matches every file pointer."""
    if len(tok) > 3:
        return _word_re(tok)
    v = re.escape(tok)
    return re.compile(r"""["']%s["']|(?<![a-z0-9_.])%s\s*=(?!=)|\.%s\b|\b%s_(?:score|loss|metric)\b""" % (v, v, v, v))


def _snippet(code):
    t = detex(code)
    t = re.sub(r"\s*\\\\\s*(\\hline)?\s*$", "", t)
    return re.sub(r"\s*&\s*", " · ", t).strip()[:180]


def mentions(items, P, bib, nodes, trees):
    """Where the paper and the code name each item. items: {key: {"tokens": [...]}} -> fills item["paper"], item["code"]."""
    titles = {e["key"]: e for e in (bib or [])}
    pats = {k: [_word_re(t) for t in it["tokens"]] for k, it in items.items()}
    cpats = {k: [_code_re(t) for t in it["tokens"]] for k, it in items.items()}
    for it in items.values():
        it["paper"] = {"n": 0, "lines": [], "cites": [], "appendix_only": False, "main_n": 0}
        it["code"] = {"n": 0, "hits": []}
    if P is not None:
        start = next((i for i, l in enumerate(P.lines) if "\\begin{document}" in l.code), -1) + 1
        app = P.appendix_idx
        for idx in range(start, len(P.lines)):
            ln = P.lines[idx]
            low = ln.code.lower()
            if not low.strip():
                continue
            for k, it in items.items():
                if not any(t in low for t in it["tokens"]) or not any(p.search(low) for p in pats[k]):
                    continue
                pp = it["paper"]
                pp["n"] += 1
                in_app = app is not None and idx >= app
                if not in_app:
                    pp["main_n"] += 1
                if len(pp["lines"]) < MAX_HITS:
                    pp["lines"].append({"path": ln.path, "line": ln.no, "repo": P.repo, "text": _snippet(ln.code), "appendix": in_app})
                for m in CITE_RE.finditer(ln.code):
                    for key in m.group(1).split(","):
                        key = key.strip()
                        if key and key != "*" and key not in [c["key"] for c in pp["cites"]] and len(pp["cites"]) < 3:
                            e = titles.get(key) or {}
                            pp["cites"].append({"key": key, "title": e.get("title") or None, "year": e.get("year")})
        for it in items.values():
            it["paper"]["appendix_only"] = bool(it["paper"]["n"]) and not it["paper"]["main_n"]
    scanned = 0
    for nid, n in sorted(nodes.items()):
        if n["kind"] not in ("code", "config") or n["repo"] not in trees or scanned >= MAX_SCAN_FILES:
            continue
        path = n["loc"]["path"]
        tr = trees[n["repo"]]
        try:
            if tr.size(path) > MAX_CODE_BYTES:
                continue
            src = tr.read(path).decode("utf-8", "replace")
        except Exception:
            continue
        scanned += 1
        low_all = src.lower()
        live = [k for k, it in items.items() if any(t in low_all or t.replace(" ", "_") in low_all for t in it["tokens"])]
        if not live:
            continue
        for no, line in enumerate(src.splitlines(), 1):
            low = line.lower()
            for k in live:
                if not any(p.search(low) for p in cpats[k]):
                    continue
                c = items[k]["code"]
                c["n"] += 1
                score = 2 if re.search(r"^\s*(def|class|function|const|let|var)\b", line) else 1 if n["kind"] == "config" else 0
                c["hits"].append({"repo": n["repo"], "path": path, "line": no, "text": line.strip()[:160], "score": score, "kind": n["kind"]})
    for it in items.values():
        hits = sorted(it["code"]["hits"], key=lambda h: (-h["score"], h["path"], h["line"]))
        seen, keep = set(), []
        for hh in hits:              # one line per file, definitions first
            if hh["path"] in seen:
                continue
            seen.add(hh["path"])
            keep.append({k: hh[k] for k in ("repo", "path", "line", "text", "kind")})
            if len(keep) >= MAX_HITS:
                break
        it["code"] = {"n": it["code"]["n"], "files": len({h["path"] for h in it["code"]["hits"]}), "hits": keep}


def build(E, G=None, trees=None):
    """E: the Experiments document (Engine.experiments()). -> the Setup document."""
    trees = trees or {}
    method = (E.get("map") or {}).get("method") or None
    base = (E.get("extends") or {}).get("base") or None
    ours_names = {norm(n) for n in ([method["name"]] + list(method.get("aliases") or [])) if norm(n)} if method else set()
    base_names = {norm(n) for n in ([base["name"]] + list(base.get("aliases") or [])) if norm(n)} if base else set()

    claims, xs, x_claims = {}, {}, {}
    for s in E.get("sections", []):
        cid = s.get("claim_id") or (None if s.get("kind") == "other" else s.get("id"))
        if cid and cid not in claims:
            claims[cid] = {"id": cid, "label": s.get("short") or s["label"], "ref": s["label"], "text": s["text"], "stage": s.get("stage"),
                           "status": s.get("status"), "scope": s.get("scope"), "experiments": []}
        for x in s["experiments"]:
            xs.setdefault(x["id"], x)
            if cid:
                x_claims.setdefault(x["id"], [])
                if cid not in x_claims[x["id"]]:
                    x_claims[x["id"]].append(cid)
                if x["id"] not in claims[cid]["experiments"]:
                    claims[cid]["experiments"].append(x["id"])
    for x in E.get("unassigned", []):
        xs.setdefault(x["id"], x)

    items, order = {}, []

    def item(kind, name, **kw):
        k = _key(kind, name)
        if k not in items:
            items[k] = dict({"id": k, "kind": kind, "name": name, "aliases": [], "uses": [], "experiments": [], "claims": [], "checks": []}, **kw)
            order.append(k)
        elif name != items[k]["name"] and name not in items[k]["aliases"]:
            items[k]["aliases"].append(name)
        return items[k]

    def use(it, x, **u):
        u["x"] = x["id"]
        it["uses"].append(u)
        if x["id"] not in it["experiments"]:
            it["experiments"].append(x["id"])
        for c in x_claims.get(x["id"], []):
            if c not in it["claims"]:
                it["claims"].append(c)

    exps = []
    for xid, x in xs.items():
        g, sm = x.get("grid"), x.get("summary") or {}
        rec = {"id": xid, "name": x["name"], "type": x.get("type") or x.get("kind"), "claims": x_claims.get(xid, []), "attention": bool(x.get("attention")),
               "items": [], "connected": bool(x.get("connected")), "files_n": x.get("files_n")}
        exps.append(rec)
        if not g:
            continue
        lower, target = bool(sm.get("lower")), sm.get("target")
        ours = sm.get("ours_label")
        tuning = bool(g.get("tuning"))
        main = g["metric"]
        # columns of the main metric, by dataset
        by_ds = {}
        for col in g["cols"]:
            ds, mt = _split(col, g)
            if mt == main or len(g["measures"]) <= 1:
                by_ds.setdefault(ds, col)
        ds_cols = [(ds, c) for ds, c in by_ds.items() if ds not in (None, AVG)]
        head_col = sm.get("metric") if sm.get("metric") in g["cols"] else (by_ds.get(AVG) or (ds_cols[0][1] if ds_cols else g["cols"][0]))
        rows = g["rows"]
        val = lambda r, c: r["values"].get(c)
        orow = next((r for r in rows if r["label"] == ours), None)

        # metric
        m = item("metric", main)
        others = [r for r in rows if r is not orow]
        best_other = None
        if orow is not None and not tuning:
            cand = [(r["label"], val(r, head_col)) for r in others if val(r, head_col) is not None]
            if cand:
                bo = min(cand, key=lambda t: abs(t[1] - target) if target is not None else t[1]) if (lower or target is not None) else max(cand, key=lambda t: t[1])
                best_other = {"label": bo[0], "value": bo[1]}
        if tuning:      # a search: no "ours", only the best setting tried
            orow = None
        tb = (x.get("tuning") or {}).get("best") if tuning else None
        use(m, x, role="main", lower=lower, target=target, column=head_col, datasets=[d for d, _ in ds_cols], tuning=tuning,
            ours=val(orow, head_col) if orow else None, ours_label=ours if orow else None, best_other=best_other, best_setting=tb,
            rank=sm.get("rank") if orow else None, methods=len(rows), runs=len(rows) if tuning else None)
        rec["items"].append(m["id"])
        rec["main_metric"] = m["id"]
        for mt in g.get("measures") or []:
            if mt == main or norm(mt) == norm(main):
                continue
            mm = item("metric", mt)
            in_table = any(_split(c, g)[1] == mt for c in g["cols"])
            use(mm, x, role="compared" if in_table else "recorded", lower=None, target=None)
            rec["items"].append(mm["id"])

        # datasets
        for ds, col in ds_cols:
            d = item("dataset", ds)
            vals = [(r["label"], val(r, col)) for r in rows if val(r, col) is not None]
            ov = val(orow, col) if orow else None
            bo, bs = None, None
            if tuning and vals:
                pick = (lambda t: abs(t[1] - target)) if target is not None else (lambda t: t[1])
                bs = (min if (lower or target is not None) else max)(vals, key=pick)
            if not tuning:
                cand = [t for t in vals if t[0] != ours]
                if cand:
                    pick = (lambda t: abs(t[1] - target)) if target is not None else (lambda t: t[1])
                    bo = (min if (lower or target is not None) else max)(cand, key=pick)
            missing = [r["label"] for r in rows if val(r, col) is None] if not tuning else []
            use(d, x, metric=main, column=col, lower=lower, target=target, tuning=tuning, runs=len(vals) if tuning else None,
                ours=ov, ours_label=ours if orow else None, best_other={"label": bo[0], "value": bo[1]} if bo else None,
                best_setting={"label": bs[0], "value": bs[1]} if bs else None,
                rank=_rank([v for _, v in vals], ov, lower, target) if ov is not None else None, methods=len(vals), missing=missing[:12],
                seeds=(orow or {}).get("n", {}).get(col) if orow else None)
            rec["items"].append(d["id"])

        # methods (not for a search: its rows are settings)
        if tuning:
            continue
        cols = [c for _, c in ds_cols] or [head_col]
        ablation = (x.get("type") or "") == "ablation"
        for r in rows:
            if r["label"] in ("", "result") and len(rows) == 1:      # a file with no method column: nothing to name
                continue
            nm = norm(r["label"])
            is_ours_here = r["label"] == ours
            role = "ours" if nm in ours_names or (not method and is_ours_here) else "base" if nm in base_names else "variant" if ablation else "baseline"
            mi = item("method", r["label"], role=role)
            if role in ("ours", "base"):
                mi["role"] = role
            elif mi.get("role") == "variant" and role == "baseline":
                mi["role"] = "baseline"
            cells, wins, cmp = [], 0, 0
            for c in cols:
                ds = _split(c, g)[0]
                v, ov = val(r, c), (val(orow, c) if orow else None)
                b = None if is_ours_here else _better(v, ov, lower, target)
                if b is not None:
                    cmp += 1
                    wins += 1 if b else 0
                cells.append({"dataset": ds if ds not in (None, AVG) else None, "column": c, "value": v, "ours": None if is_ours_here else ov,
                              "better": b, "n": r["n"].get(c)})
            hv, hov = val(r, head_col), (val(orow, head_col) if orow else None)
            gap = None      # how far ours is ahead of this method (negative: behind)
            if not (is_ours_here or hv is None or hov is None):
                gap = round(abs(hv - target) - abs(hov - target) if target is not None else (hv - hov) if lower else (hov - hv), 10)
            use(mi, x, ours_here=is_ours_here, ours_label=ours if orow else None, metric=main, column=head_col, lower=lower, target=target,
                value=hv, ours=None if is_ours_here else hov, gap=gap, wins=wins, compared=cmp, cells=cells, methods=len(rows),
                missing=[cl["dataset"] for cl in cells if cl["value"] is None and cl["dataset"]],
                rank=_rank([val(o, head_col) for o in rows if val(o, head_col) is not None], hv, lower, target) if hv is not None else None,
                runs=max([n for n in r["n"].values() if n] or [0]) or None)
            rec["items"].append(mi["id"])
        rec["items"] = list(dict.fromkeys(rec["items"]))

    # where the paper and the code name each item
    for it in items.values():
        it["tokens"] = _tokens(it["name"], it["aliases"] + (list(method.get("aliases") or []) if method and it.get("role") == "ours" and it["kind"] == "method" else [])
                               + (list(base.get("aliases") or []) if base and it.get("role") == "base" and it["kind"] == "method" else []))
    if G is not None:
        mentions(items, getattr(G, "paper", None), getattr(G, "bib_entries", None), G.nodes, trees)
    else:
        for it in items.values():
            it["paper"], it["code"] = {"n": 0, "lines": [], "cites": [], "appendix_only": False, "main_n": 0}, {"n": 0, "files": 0, "hits": []}
    has_paper = G is not None and getattr(G, "paper", None) is not None

    # one-line summaries and checks
    for it in items.values():
        it.pop("tokens", None)
        U = it["uses"]
        if it["kind"] == "metric":
            mains = [u for u in U if u["role"] == "main"]
            dirs = {("target %g" % u["target"]) if u.get("target") is not None else ("lower" if u["lower"] else "higher") for u in mains}
            it["direction"] = next(iter(dirs)) if len(dirs) == 1 else ("mixed" if dirs else None)
            it["main_in"] = len({u["x"] for u in mains})
            if len(dirs) > 1:
                it["checks"].append({"k": "direction", "t": "Read as " + " in some experiments, ".join(sorted(d + "-is-better" if not d.startswith("target") else "closer-to-" + d[7:] for d in dirs)) + " in others"})
            if not mains:
                it["checks"].append({"k": "unused", "t": "Recorded in the files, never compared"})
        elif it["kind"] == "dataset":
            cmpd = [u for u in U if u.get("ours") is not None and u.get("best_other")]
            it["ours_best"] = sum(1 for u in cmpd if u["rank"] == 1)
            it["compared"] = len(cmpd)
            it["metrics"] = list(dict.fromkeys(u["metric"] for u in U))
            miss = sorted({m for u in U for m in u.get("missing") or []})
            if miss:
                it["checks"].append({"k": "missing", "t": "Not run for " + ", ".join(miss[:4]) + (" and %d more" % (len(miss) - 4) if len(miss) > 4 else "")})
        else:
            others = [u for u in U if not u["ours_here"]]
            it["wins"] = sum(u["wins"] for u in others)
            it["compared"] = sum(u["compared"] for u in others)
            miss = sorted({d for u in U for d in u["missing"]})
            if miss:
                it["checks"].append({"k": "missing", "t": "No result on " + ", ".join(miss[:4]) + (" and %d more" % (len(miss) - 4) if len(miss) > 4 else "")})
            if U and all((u.get("runs") or 0) <= 1 for u in U):
                it["checks"].append({"k": "seeds", "t": "One run per cell"})
            if it.get("role") == "baseline" and it["paper"]["n"] and not it["paper"]["cites"]:
                it["checks"].append({"k": "cite", "t": "Not cited on any line that names it"})
        if has_paper and not it["paper"]["n"] and it["kind"] != "metric" and it.get("role") not in ("variant",):
            it["checks"].append({"k": "paper", "t": "The paper never names it"})
        elif has_paper and it["paper"]["appendix_only"]:
            it["checks"].append({"k": "appendix", "t": "Named only in the appendix"})

    rank_role = {"ours": 0, "base": 1, "baseline": 2, "variant": 3}
    ordered = sorted((items[k] for k in order), key=lambda it: (KINDS.index(it["kind"]), rank_role.get(it.get("role"), 0), -len(it["experiments"]), it["name"].lower()))
    for cid, c in claims.items():
        c["items"] = list(dict.fromkeys(i for xid in c["experiments"] for rec in exps if rec["id"] == xid for i in rec["items"]))
    counts = {k: sum(1 for it in ordered if it["kind"] == k) for k in KINDS}
    counts["baselines"] = sum(1 for it in ordered if it.get("role") == "baseline")
    counts["checks"] = sum(1 for it in ordered if it["checks"])
    counts["experiments"] = len(exps)
    counts["without_files"] = sum(1 for r in exps if not r["items"])
    return {"schema": SCHEMA, "method": method, "base": base, "items": ordered, "experiments": exps,
            "claims": [c for c in claims.values() if c["experiments"]], "counts": counts, "mapped": E.get("unmapped") is not None, "has_paper": has_paper}
