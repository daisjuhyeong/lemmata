"""Phase 2, "track": apply a confirmed project map. Rules only.

Each experiment of the map is a group of result files. On every scan the files matching its patterns are read and
folded into one table (a row per method, a column per dataset, runs averaged), "ours" is the map's method, and the
result is compared with the paper's table and followed through the git history. Files the map does not cover are
counted, never guessed at.
"""
from . import code as codemod
from . import understand as und
from .claims import _Ctx
from .errors import NotFound
from .experiments import DATA_COLS, LABEL_COLS, SEED_COLS, align, history, lower_better, norm, num, paper_cells, pick_ours, records, summarise
from .tree import GitTree

SCHEMA = "lemmata.experiments/2"
MAX_FILES, MAX_DAYS = 300, 15
ORDER = {t: i for i, t in enumerate(("main", "ablation", "sensitivity", "analysis", "efficiency", "other", "tuning"))}
AVG = "Average"


def combine(found, read, spec, tuning=False):
    """Fold the files of one experiment into one table.
    found: [(path, {field: value})]; read(path) -> bytes. -> table like experiments.parse_result, plus "metric_by"."""
    cells, methods, datasets, metric, metric_by, n_files, measures = {}, [], [], spec.get("metric"), "map", 0, []
    for path, fields in found[:MAX_FILES]:
        try:
            recs = records(path, read(path))
        except Exception:
            recs = None
        if not recs:
            continue
        n_files += 1
        keys = list(dict.fromkeys(str(k) for r in recs for k in r))
        pick = lambda names: next((k for k in keys if norm(k) in names), None)
        mcol = spec.get("method_column") if spec.get("method_column") in keys else pick(LABEL_COLS)
        dcol = spec.get("dataset_column") if spec.get("dataset_column") in keys else pick(DATA_COLS)
        for k in keys:
            if k not in measures and k not in (mcol, dcol) and norm(k) not in SEED_COLS and num(recs[0].get(k)) is not None:
                measures.append(k)
        if metric not in keys:
            if spec.get("metric"):
                continue                      # this file does not carry the experiment's metric
            metric = next((k for k in keys if k not in (mcol, dcol) and norm(k) not in SEED_COLS and num(recs[0].get(k)) is not None), None)
            metric_by = "first number column"
            if metric is None:
                continue
        extra = {k: v for k, v in fields.items() if k not in ("method", "dataset", "seed")}
        for r in recs:
            got = num(r.get(metric))
            if got is None:
                continue
            if tuning:      # a search: one row per setting tried
                lab = ", ".join("%s=%s" % kv for kv in sorted(extra.items())) or str(r.get(mcol, "")).strip() or fields.get("method") or path.rsplit("/", 1)[-1]
            else:
                lab = fields.get("method") or (str(r.get(mcol, "")).strip() if mcol else "") or spec.get("fallback") or "result"
            ds = fields.get("dataset") or (str(r.get(dcol, "")).strip() if dcol else "")
            if lab not in methods:
                methods.append(lab)
            if ds and ds not in datasets:
                datasets.append(ds)
            cells.setdefault((lab, ds or metric), []).append(got[0])
    if not cells:
        return None
    cols = datasets or [metric]
    rows = []
    for lab in methods:
        vals, stds, ns = {}, {}, {}
        for c in cols:
            xs = cells.get((lab, c))
            if not xs:
                continue
            mean = sum(xs) / len(xs)
            vals[c], ns[c] = mean, len(xs)
            stds[c] = (sum((v - mean) ** 2 for v in xs) / (len(xs) - 1)) ** 0.5 if len(xs) > 1 else None
        if len(cols) > 1 and vals:
            vals[AVG], ns[AVG], stds[AVG] = sum(vals.values()) / len(vals), min(ns.values()), None
        rows.append({"label": lab, "values": vals, "std": stds, "n": ns})
    return {"cols": ([AVG] if len(cols) > 1 else []) + cols, "rows": rows, "seeds": any(n > 1 for r in rows for n in r["n"].values()),
            "datasets": datasets, "metrics": [metric], "metric": metric, "measures": measures[:24], "metric_by": metric_by, "files": n_files}


def toward(tab, target):
    """For "closer to <target> is better": the same table with each value replaced by its distance to the target."""
    if tab is None or target is None:
        return tab
    rows = [dict(r, values={c: abs(v - target) for c, v in r["values"].items()}) for r in tab["rows"]]
    return dict(tab, rows=rows)


def ours_of(table, method, spec, chosen, bold=()):
    labels = [r["label"] for r in table["rows"]]
    if chosen in labels:
        return chosen, "you"
    if spec.get("ours") in labels:
        return spec["ours"], "map"
    names = [norm(n) for n in ([method["name"]] + method.get("aliases", []) if method else []) if norm(n)]
    for lab in labels:
        if norm(lab) in names:
            return lab, "map"
    hit = [lab for lab in labels if any(len(n) >= 3 and n in norm(lab) for n in names)]
    if hit:
        return min(hit, key=len), "map"
    return pick_ours(table, [], bold)


def names_match(labels, who, skip=None):
    names = [norm(n) for n in ([who["name"]] + who.get("aliases", []) if who else []) if norm(n)]
    cands = [l for l in labels if l != skip]
    exact = [l for l in cands if norm(l) in names]
    if exact:
        return exact[0]
    loose = [l for l in cands if any(len(n) >= 3 and n in norm(l) for n in names)]
    return min(loose, key=len) if loose else None


def build(m, G, trees, infos, events, alarms, findings, ledger, store, github=None, detail=None, state=None):
    """-> the Experiments document driven by the map; with detail=<'map:id'>, that one experiment in full."""
    P, github = G.paper, github or {}
    ctx = _Ctx(G, alarms, findings)
    ents = (store or {}).get("entries", {})
    led = {r["node_id"]: r for r in ledger["rows"]}
    files = und.result_files(G)
    method, base = m.get("method"), m.get("base")
    qs = {q["id"]: q for q in m["questions"]}

    def experiment(spec, full=False):
        xid = "map:" + spec["id"]
        e = ents.get(xid, {})
        hit = und.match_files(spec["files"], files)
        repo = hit[0][0] if hit else None
        hit = [f for f in hit if f[0] == repo]
        tuning = spec["type"] == "tuning"
        sp = dict(spec, metric=e.get("metric") or spec.get("metric"), fallback=method["name"] if method else None)
        tr = trees.get(repo)
        tab = combine([(p, f) for _, p, _, f in hit], tr.read, sp, tuning) if tr and hit else None
        papers = [p for p in spec["paper"] if p in G.nodes]
        tnode = next((p for p in papers if G.nodes[p]["kind"] == "table"), None)
        cells = paper_cells(P, tnode) if (P is not None and tnode) else None
        bold = [r[0]["text"] for r in (cells or [])[1:] if any(c["bold"] for c in r[1:])]
        x = {"id": xid, "name": spec["name"], "kind": "group", "type": spec["type"], "caption": spec.get("note") or "", "map": True,
             "loc": G.nodes[tnode].get("loc") if tnode else None, "repo": repo, "result": None, "connected": bool(hit), "image": False,
             "summary": None, "tally": None, "problems": [], "caveats": [], "stale": None, "history_n": 0, "spark": [], "files_n": len(hit),
             "paper": [{"node_id": p, "name": G.nodes[p]["name"], "kind": G.nodes[p]["kind"]} for p in papers], "tests": spec["tests"]}
        stale = [led[n] for _, _, n, _ in hit if n in led and led[n]["status"] == "stale"]
        if stale:
            x["stale"] = {"file": stale[0]["name"] + (" and %d more" % (len(stale) - 1) if len(stale) > 1 else ""), "newer": stale[0]["newer"][:3]}
            x["caveats"].append({"k": "stale", "t": "Result older than code"})
        made = [led[n]["made"]["time"] for _, _, n, _ in hit if n in led and led[n].get("made")]
        if made:
            x["last"] = max(made)
        if hit:
            x["result"] = {"node_id": hit[0][2], "name": ", ".join(spec["files"]), "path": ", ".join(spec["files"]), "repo": repo, "github": None}
        if tab:
            col = e.get("column") if e.get("column") in tab["cols"] else tab["cols"][0]
            target = spec.get("target")
            lower = True if target is not None else e["lower"] if "lower" in e else spec["lower"] if spec.get("lower") is not None else lower_better(tab["metric"])
            raw, tab = tab, toward(tab, target)
            if tuning:
                vals = [(r["label"], r["values"][col]) for r in tab["rows"] if col in r["values"]]
                best = (min if lower else max)(vals, key=lambda v: v[1]) if vals else None
                x["tuning"] = {"runs": len(vals), "best": {"label": best[0], "value": best[1]} if best else None, "metric": tab["metric"], "lower": lower}
                ours, how, s = (best[0] if best else None), "best setting", None
            else:
                ours, how = ours_of(tab, method, spec, e.get("ours"), bold)
                s = summarise(tab, ours, col, lower)
                bl = names_match([r["label"] for r in tab["rows"]], base, ours) if base else None
                if s and bl:
                    bv = next((r["values"].get(col) for r in tab["rows"] if r["label"] == bl), None)
                    if bv is not None:
                        s["base"] = {"label": bl, "value": bv, "gap": round((bv - s["ours"]) if lower else (s["ours"] - bv), 10)}
            x["summary"] = dict(s or {"ours": None, "gap": None, "best": None}, ours_label=ours, ours_by=how, metric=col, measure=tab["metric"] if target is None else "|%s − %g|" % (tab["metric"], target), measures=tab["measures"],
                                lower=lower, target=target, metric_by=tab["metric_by"] if not e.get("metric") else "you", methods=[r["label"] for r in tab["rows"]],
                                baselines=[] if tuning else [r["label"] for r in tab["rows"] if r["label"] != ours], cols=tab["cols"], datasets=tab["datasets"])
            rx = [und.compile_pattern(p) for p in spec["files"]]

            def table_at(ev):
                t = GitTree(infos[repo]["abs_path"], repo, ev["rev"])
                try:
                    found = [(p, mm.groupdict()) for p in t.list_files() for mm in [next((r.match(p) for r, _ in rx if r.match(p)), None)] if mm]
                    return toward(combine(found, t.read, sp, tuning), target)
                finally:
                    t.close()

            def per_day(evs):      # the last commit of each day that touched the group
                last = {}
                for ev in evs:
                    last[(ev.get("time") or "")[:10]] = ev
                return list(last.values())[-MAX_DAYS:]
            hist = history(events, infos, G.nodes, repo, None, ours, col, lower, is_result=lambda p: any(r.match(p) for r, _ in rx),
                           table_at=table_at, versions=per_day) if not tuning else []
            x["history_n"] = len(hist)
            x["spark"] = [{"o": h["ours"], "b": h["best"], "r": h["ruler"], "c": bool(h["changes"])} for h in hist]
            if not tuning:
                if s and s["n"] <= 1 and s.get("std") is None:
                    x["caveats"].append({"k": "seeds", "t": "One run, no spread"})
                if any(h["ruler"] or "evaluation" in h["cats"] for h in hist[1:]):
                    x["caveats"].append({"k": "ruler", "t": "Evaluation changed"})
                if how not in ("you", "map", "name"):
                    x["caveats"].append({"k": "guess", "t": "“Ours” is a guess"})
                if s is None:
                    x["caveats"].append({"k": "guess", "t": "“Ours” not found in these files"})
            if tab["metric_by"] != "map" and not e.get("metric"):
                x["caveats"].append({"k": "guess", "t": "Metric is a guess"})
            if full:
                x["table"] = {"cols": raw["cols"], "rows": raw["rows"][:60], "seeds": raw["seeds"]}
                x["history"] = hist
        elif hit:
            x["caveats"].append({"k": "untraced", "t": "Files could not be read as tables"})
        if cells:
            grid, tally, problems = align(cells, raw if tab else None, x["summary"]["lower"] if x["summary"] and x["summary"].get("target") is None else None)
            if x["summary"] and x["summary"].get("target") is not None:     # "best" in a column is the value nearest the target: skip the bold check
                problems = [p for p in problems if p["kind"] != "bold"]
            x["tally"], x["problems"] = tally, problems
            if any(p["kind"] == "bold" for p in problems):
                x["caveats"].append({"k": "bold", "t": "Bold is not best"})
            if full:
                x["cells"] = grid
        if not hit:
            x["caveats"].append({"k": "untraced", "t": "No result file"})
        x["attention"] = bool(x["stale"] or (x["tally"] and (x["tally"]["differs"] or x["tally"]["untraced"])) or not hit
                              or any(p["kind"] == "bold" for p in x["problems"]))
        if full:
            link = lambda i: {"node_id": i, "name": G.nodes[i]["name"], "kind": G.nodes[i]["kind"],
                              "github": github[G.nodes[i]["repo"]] + G.nodes[i]["loc"]["path"] if G.nodes[i]["repo"] in github and G.nodes[i]["kind"] != "run" else None}
            code, settings, runs = [], [], []
            for _, _, n, _ in hit[:12]:
                ch = ctx.chain(n)
                code += ch["code"]
                settings += ch["settings"]
                runs += ch["runs"]
            code, settings, runs = [list(dict.fromkeys(v)) for v in (code, settings, runs)]
            if not settings and repo:
                settings = sorted(i for i, mm in G.nodes.items() if mm["kind"] == "config" and mm["repo"] == repo)[:2]
            x["design"] = {"scripts": [link(i) for i in code[:8]], "settings": [link(i) for i in settings[:4]],
                           "runs": [dict(link(i), command=G.nodes[i]["attrs"].get("command")) for i in runs[:6]], "values": [],
                           "files": [{"node_id": n, "path": p, "fields": f} for _, p, n, f in hit[:40]]}
            for i in settings[:3]:
                sn = G.nodes[i]
                try:
                    src = trees[sn["repo"]].read(sn["loc"]["path"]).decode("utf-8", "replace")
                    for k, (v, ln) in list(codemod.config_keys(sn["loc"]["path"], src).items())[:24]:
                        x["design"]["values"].append({"key": k, "value": v, "file": sn["name"]})
                except Exception:
                    pass
            x["questions"] = [{"id": qs[t].get("claim_id") or qs[t]["id"], "label": qs[t]["label"], "text": qs[t]["text"]} for t in spec["tests"] if t in qs]
        return x

    if detail is not None:
        spec = next((x for x in m["experiments"] if "map:" + x["id"] == detail), None)
        if spec is None:
            raise NotFound("unknown experiment %r" % detail)
        return experiment(spec, full=True)

    built = {x["id"]: experiment(x) for x in m["experiments"]}
    key = lambda x: (ORDER.get(x["type"], 9), x["name"].lower())
    sections = []
    for q in m["questions"]:
        exps = sorted((built[x["id"]] for x in m["experiments"] if q["id"] in x["tests"]), key=key)
        real = [x for x in exps if x["type"] != "tuning"]
        status = "unsupported" if not real else "partial" if any(x["attention"] for x in real) else "supported"
        sections.append({"id": q["id"], "claim_id": q.get("claim_id"), "kind": q["kind"], "source": q.get("source", "paper"), "scope": q.get("scope"), "label": q["label"], "text": q["text"], "status": status,
                         "state": "confirmed", "recheck": any(x["stale"] for x in exps), "experiments": exps, "suggested": [], "evidence": q["evidence"][:2]})
    if base:     # the extension's own questions first, then the original paper's claims it re-checks
        sections.sort(key=lambda s_: {"extension": 0, None: 1, "base": 2}.get(s_.get("scope"), 1))
    rest = sorted((built[x["id"]] for x in m["experiments"] if not x["tests"]), key=key)
    if rest:
        sections.append({"id": "other", "claim_id": None, "kind": "other", "label": "Other", "text": "Experiments the map ties to no question", "status": "partial",
                         "state": "confirmed", "recheck": False, "experiments": rest, "suggested": [], "evidence": []})
    cov = und.coverage(m, G, trees)
    allx = list(built.values())
    return {"schema": SCHEMA, "sections": sections, "unassigned": [], "unmapped": cov,
            "extends": {"base": base, "goal": m.get("goal")} if base else None,
            "map": {"state": state or "confirmed", "method": method, "questions": len(m["questions"]), "experiments": len(m["experiments"])},
            "counts": {"questions": len(m["questions"]), "untested": sum(1 for s in sections if s["kind"] != "other" and s["status"] == "unsupported"),
                       "experiments": len(allx), "attention": sum(1 for x in allx if x["attention"]), "versions": sum(x["history_n"] for x in allx),
                       "files": cov["matched"], "unmapped": cov["n_files"]}}
