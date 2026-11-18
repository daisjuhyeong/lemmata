"""Board (S28): how what was used reaches the thesis, as four columns of cards.

    Thesis  <-  Claims  <-  Experiments  <-  What was used (metrics, datasets, methods)

The Setup page shows it at the top (founder, chat 2026-11-18: "a flowchart ... so that I can actually see how the
setup connects to the thesis ... think of a kanban system"). Two sources, one shape:

- a paper project: the Setup document itself (claims, experiments and items it already holds) and the thesis text;
- a hypothesis-first project: the problem, the hypotheses and the protocol's steps, and for each step what its own
  result tables name (a "model" column, a "dataset" column, metric columns).

Rules only: no language model, nothing is run. A card that does not reach the thesis is kept and marked, because that
gap is what the board is for.
"""
import csv
import io
import re

from .experiments import norm
from .hypo import rel

SCHEMA = "lemmata.board/1"
KINDS = ("metric", "dataset", "method", "condition")
MAX_FILES, MAX_FILE, MAX_BYTES, MAX_NAMES = 120, 2_000_000, 24_000_000, 60

# columns of a long result table (one row per run), by header name; the first one present wins
METHOD_COLS = ("model", "method", "detector", "algorithm", "algo", "approach", "baseline", "learner", "classifier", "system")
DATASET_COLS = ("dataset", "benchmark", "task", "corpus", "source", "stream", "series", "data")
GROUP_COLS = ("group", "suite", "collection", "benchmark", "family", "category", "domain")
SEED_COLS = ("seed", "run", "trial", "rep", "repeat", "fold")
COND_COLS = ("variant", "condition", "setting", "perturbation", "shuffle", "ablation")
STATUS_COLS = ("status", "state")
FAILED = {"error", "failed", "fail", "crashed", "oom", "timeout", "killed"}
METRIC_RE = re.compile(
    r"^(?:best|mean|avg|test|val|final)?(?:auc|auroc|auprc|aucroc|aucpr|rocauc|prauc|ap|map|f1|f1pa|paf1|bestf1|fscore|f1score|vusroc|vuspr|precision|recall|"
    r"acc|accuracy|top1|top5|mse|mae|rmse|mape|smape|r2|loss|nll|ppl|perplexity|bleu|rouge[l12]?|ndcg\d*|mrr|hits\d+|iou|miou|dice|psnr|ssim|fid|"
    r"errorrate|fpr|fnr|tpr|eer|wer|cer|delay|regret)$")
MAX_GROUPS = 8


def _status_word(status):
    return {"done": "done", "running": "running", "planned": "planned"}.get(status, status or "planned")


# ------------------------------------------------------------------ a paper project: from the Setup document
def from_setup(S, thesis, waiting=False):
    """S: the Setup document; thesis: Experiments()['thesis']. -> the board."""
    claims = [{"id": c["id"], "label": c["label"], "text": c["text"], "stage": c.get("stage"), "stage_why": c.get("stage_why"), "stage_rule": c.get("stage_rule"),
               "stage_by": c.get("stage_by"), "experiments": list(c["experiments"]), "links": {x: l["status"] for x, l in (c.get("links") or {}).items()}} for c in S["claims"]]
    have = {c["id"] for c in claims}
    for c in (thesis or {}).get("untested") or []:      # a claim nothing tests yet has no section, so Setup does not list it
        if c["id"] not in have:
            claims.append({"id": c["id"], "label": c.get("short") or "", "text": c["text"], "stage": c.get("stage"), "experiments": [], "links": {}})
    exps = [{"id": x["id"], "name": x["name"], "type": x.get("type"), "claims": list(x["claims"]), "items": list(x["items"]), "sheet": bool(x.get("protocol")),
             "sheets": [x["id"]] if x.get("protocol") else [], "attention": bool(x.get("attention"))} for x in S["experiments"] if x.get("protocol") or x["claims"]]
    shown = {x["id"] for x in exps}
    items = [{"id": it["id"], "kind": it["kind"], "name": it["name"], "role": it.get("role"), "experiments": [x for x in it["experiments"] if x in shown],
              "checks": len(it.get("checks") or []), "detail": True} for it in S["items"]]
    T = thesis or {}
    return _finish({"schema": SCHEMA, "mode": "paper", "rough": not S.get("mapped"), "waiting": bool(waiting),
                    "thesis": {"kind": "thesis", "text": T.get("text"), "state": T.get("state"), "missing": None if T.get("text") else "No core message yet. It is drafted from the abstract on Thesis."},
                    "claims": claims, "experiments": exps, "items": items})


# ------------------------------------------------------------------ a hypothesis-first project
def _files_of(files, deliverables):
    """The readable tables of a step: each deliverable is a file or a folder."""
    out, listing = [], None
    for p in deliverables or []:
        p = rel(p)
        if not p:
            continue
        if files.find(p)[0]:
            out.append(p)
            continue
        if listing is None:
            listing = sorted(q for _, q in files.listing())
        pre = p.rstrip("/") + "/"
        out += [q for q in listing if q.startswith(pre)]
    return [p for p in dict.fromkeys(out) if p.lower().endswith((".csv", ".tsv"))]


def _first(header, names):
    by = {norm(h): h for h in header}
    return next((by[n] for n in names if n in by), None)


def read_step(files, deliverables):
    """What one step's result tables name. -> {"methods": {name: {...}}, "datasets": {...}, "metrics": [...], ...}"""
    methods, datasets, conds, seeds, metrics, measures, cells = {}, {}, {}, set(), {}, {}, {}
    rows_n = failed = read = skipped = total = 0
    paths = _files_of(files, deliverables)
    for p in paths:
        rid, path = files.find(p)
        if rid is None:
            continue
        t = files.trees[rid]
        try:
            size = t.size(path)
        except Exception:
            size = None
        if size is None or size > MAX_FILE or read >= MAX_FILES or total + size > MAX_BYTES:
            skipped += 1
            continue
        try:
            raw = t.read(path).decode("utf-8", "replace")
        except Exception:
            skipped += 1
            continue
        read += 1
        total += size
        rd = csv.reader(io.StringIO(raw), dialect="excel-tab" if path.endswith(".tsv") else "excel")
        try:
            header = [h.strip() for h in next(rd)]
        except (StopIteration, csv.Error):
            continue
        idx = {h: i for i, h in enumerate(header)}
        mc, dc, sc, cc, stc = (_first(header, n) for n in (METHOD_COLS, DATASET_COLS, SEED_COLS, COND_COLS, STATUS_COLS))
        gc = _first([h for h in header if h != dc], GROUP_COLS)
        role = {mc, dc, sc, cc, stc, gc} - {None}
        mcols = [h for h in header if h not in role and METRIC_RE.match(norm(h))]
        ocols = [h for h in header if h not in role and h not in mcols]
        got = lambda r, c: (r[idx[c]].strip() if c is not None and idx[c] < len(r) else "")
        seen_num = set()
        try:
            for r in rd:
                if not r:
                    continue
                m, d, g, s, c = got(r, mc), got(r, dc), got(r, gc), got(r, sc), got(r, cc)
                # one run = one (method, dataset, condition, seed); a failed attempt that was later repeated with success is not a failed run
                key = (m, g, d, c, s) if (m or d) else ("row", path, tuple(r))
                cells[key] = cells.get(key, False) or got(r, stc).lower() not in FAILED
                for h in mcols + ocols:
                    if h in seen_num:
                        continue
                    v = got(r, h)
                    if v:
                        try:
                            float(v)
                        except ValueError:
                            continue
                        seen_num.add(h)
        except csv.Error:
            pass
        for h in mcols:
            if h in seen_num:
                metrics.setdefault(h, []).append(p)
        for h in ocols:
            if h in seen_num:
                measures.setdefault(h, []).append(p)
    plain = lambda k: k[0] == "row" and len(k) == 3
    keyed = any(not plain(k) for k in cells)        # runs are counted when the tables name them; plain rows only when none does
    for key, ok in cells.items():
        if plain(key):
            rows_n += not keyed
            failed += (not ok) and not keyed
            continue
        rows_n += 1
        failed += not ok
        m, g, d, c, sd = key
        if sd:
            seeds.add(sd)
        if m:
            e = methods.setdefault(m, {"rows": 0, "failed": 0, "datasets": set(), "seeds": set()})
            e["rows"] += 1
            e["failed"] += not ok
            if d:
                e["datasets"].add((g, d))
            if sd:
                e["seeds"].add(sd)
        if d:
            e = datasets.setdefault((g or None, d), {"name": d, "rows": 0, "group": g or None, "methods": set()})
            e["rows"] += 1
            if m:
                e["methods"].add(m)
        if c:
            conds[c] = conds.get(c, 0) + 1
    return {"methods": methods, "datasets": datasets, "conditions": conds, "seeds": len(seeds), "metrics": metrics, "measures": measures,
            "rows": rows_n, "failed": failed, "files": paths, "read": read, "skipped": skipped}


def from_hypothesis(H, files, S=None, used=None):
    """H: hypo.view(); files: hypo.Files; S: the Setup document (to find each step's sheets); used: {step id: read_step()}."""
    P = H["problem"]
    cur = P.get("confirmed") or P.get("proposed") or {}
    txt = lambda k: ((cur.get(k) or {}).get("text") if isinstance(cur.get(k), dict) else cur.get(k)) or None
    thesis = {"kind": "problem", "text": txt("gap"), "approach": txt("approach"), "state": P.get("validity"),
              "missing": None if txt("gap") else "The problem is not stated yet. It is the first job on Thesis."}
    live = [h for h in H["hypotheses"] if not h.get("archived")]
    hid = {h["id"] for h in live}
    alias = {a: h["id"] for h in live for a in h.get("aliases") or []}
    steps = H["experiments"]
    tests = {x["id"]: [alias.get(c, c) for c in x.get("tests_claims") or []] for x in steps}
    for h in live:                      # a link may be written on either side
        for xid in h.get("tested_by") or []:
            if xid in tests and h["id"] not in tests[xid]:
                tests[xid].append(h["id"])
    claims = [{"id": h["id"], "label": h["id"], "text": h["statement"], "stage": h.get("stage"), "stage_why": h.get("stage_why"), "stage_rule": h.get("stage_rule"),
               "stage_by": "you" if h.get("stage_rule") == "R0" else "rule", "tier": h.get("tier"), "confirmed": bool(h.get("confirmed")),
               "experiments": [x["id"] for x in steps if h["id"] in tests[x["id"]]], "links": {}} for h in live]
    sheets = _sheets(S, steps)
    items, order, exps = {}, [], []
    words = {h["id"]: norm(h["statement"] + " " + ((h.get("criterion") or {}).get("text") or "")) for h in live}

    def item(kind, name, **kw):
        k = kind + ":" + norm(name)
        if k not in items:
            items[k] = dict({"id": k, "kind": kind, "name": name, "experiments": [], "uses": [], "checks": 0, "detail": False}, **kw)
            order.append(k)
        return items[k]

    def use(it, xid, **u):
        if xid not in it["experiments"]:
            it["experiments"].append(xid)
            it["uses"].append(dict(u, x=xid))

    for x in steps:
        U = (used or {}).get(x["id"]) or read_step(files, x.get("deliverables"))
        ids = []
        named = [h for h in tests[x["id"]] if h in hid]
        for m, paths in U["metrics"].items():
            it = item("metric", m, named_by=[])
            for h in named:
                if norm(m) and norm(m) in words[h] and h not in it["named_by"]:
                    it["named_by"].append(h)
            use(it, x["id"], files=len(paths))
            ids.append(it["id"])
        if not U["metrics"] and U["measures"]:
            n = len(U["measures"])
            it = item("metric", "measures of " + x["id"], named_by=[], names=sorted(U["measures"])[:MAX_NAMES], n=n, summary=True)
            it["name"] = "%d measure%s" % (n, "" if n == 1 else "s")
            use(it, x["id"], files=U["read"])
            ids.append(it["id"])
        D = U["datasets"]                 # keyed by (group, name): two suites may hold a dataset of the same name
        groups = {}
        for (g, d), e in D.items():
            groups.setdefault(g, []).append(d)
        grouped = len(D) > MAX_GROUPS and None not in groups and 1 < len(groups) <= MAX_GROUPS
        if grouped:
            for g, ds in groups.items():
                it = item("dataset", g, group=True, names=[])
                it["names"] += [d for d in sorted(ds) if d not in it["names"]]
                use(it, x["id"], datasets=len(ds), names=sorted(ds)[:MAX_NAMES], methods=len(set().union(*[D[(g, d)]["methods"] for d in ds])))
                ids.append(it["id"])
        else:
            for (g, d), e in D.items():
                it = item("dataset", d)
                use(it, x["id"], methods=len(e["methods"]), rows=e["rows"])
                ids.append(it["id"])
        for m, e in U["methods"].items():
            it = item("method", m)
            use(it, x["id"], datasets=len(e["datasets"]), seeds=len(e["seeds"]), rows=e["rows"], failed=e["failed"])
            if e["failed"]:
                it["checks"] += 1
                it["failed"] = it.get("failed", 0) + e["failed"]
            ids.append(it["id"])
        if len(U["conditions"]) > 1:
            for c, n in U["conditions"].items():
                it = item("condition", c)
                use(it, x["id"], rows=n)
                ids.append(it["id"])
        exps.append({"id": x["id"], "name": x.get("title") or x["id"], "type": "step", "status": _status_word(x.get("status")), "claims": [h for h in tests[x["id"]] if h in hid],
                     "items": list(dict.fromkeys(ids)), "sheet": False, "sheets": sheets.get(x["id"], []), "deliverables": list(x.get("deliverables") or []),
                     "depends_on": list(x.get("depends_on") or []), "acceptance": x.get("acceptance"),
                     "used": {"methods": len(U["methods"]), "datasets": len(D), "seeds": U["seeds"], "rows": U["rows"], "failed": U["failed"], "files": U["read"], "skipped": U["skipped"],
                              "conditions": sorted(U["conditions"])[:12]},
                     "attention": bool(U["failed"])})
    for it in items.values():
        if it.get("names") is not None:
            it["names"] = it["names"][:MAX_NAMES]
    return _finish({"schema": SCHEMA, "mode": "hypothesis_first", "rough": False, "waiting": False, "thesis": thesis, "claims": claims, "experiments": exps,
                    "items": [items[k] for k in order]})


def _sheets(S, steps):
    """The Setup sheets (one per result file) that lie under each step's deliverables."""
    out = {}
    if not S:
        return out
    paths = []
    for x in S["experiments"]:
        if x.get("protocol") and x["id"].startswith("file:"):
            p = x["id"][5:]
            paths.append((x["id"], p, p.split("/", 1)[1] if "/" in p else p))      # with and without the repository's folder
    for st in steps:
        pres = [rel(d) for d in st.get("deliverables") or [] if rel(d)]
        hit = [xid for xid, full, short in paths if any(q == d or q.startswith(d.rstrip("/") + "/") for d in pres for q in (full, short))]
        if hit:
            out[st["id"]] = hit
    return out


def _finish(B):
    """Counts of what reaches the thesis and what does not."""
    reach_c = {c["id"] for c in B["claims"]}
    reach_x = {x["id"] for x in B["experiments"] if any(c in reach_c for c in x["claims"])}
    used = {i for x in B["experiments"] for i in x["items"]}
    reach_i = {i for x in B["experiments"] if x["id"] in reach_x for i in x["items"]}
    order = {k: n for n, k in enumerate(KINDS)}
    B["items"] = sorted([it for it in B["items"] if it["id"] in used], key=lambda it: (order.get(it["kind"], 9), 0 if it.get("named_by") else 1))
    B["counts"] = {"claims": len(B["claims"]), "experiments": len(B["experiments"]), "items": len(B["items"]),
                   "by_kind": {k: sum(it["kind"] == k for it in B["items"]) for k in KINDS},
                   "claims_untested": sum(1 for c in B["claims"] if not c["experiments"]),
                   "experiments_no_claim": len(B["experiments"]) - len(reach_x),
                   "items_unreached": sum(1 for it in B["items"] if it["id"] not in reach_i)}
    return B
