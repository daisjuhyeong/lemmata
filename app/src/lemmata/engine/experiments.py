"""Experiments, organised by what the paper set out to test.

question / hypothesis (a claim)  ->  experiment (a table or figure and the result file behind it)  ->  history (every
committed version of that result file, and the code / settings / evaluation changes between versions).

For each experiment: who is compared (ours, baselines), on what (datasets, metric), the main result, how it was made
(script, settings), whether the paper's table agrees with the result file cell by cell, and how the result moved over
time and after which change. Rules only: no language model, nothing is run. What Lemmata guesses (which row is "ours",
which metric is the main one, whether higher is better) is marked as a guess and can be corrected.
"""
import csv
import io
import json
import re

from . import code as codemod
from .claims import SUPPORT_REL, _Ctx, detex
from .errors import BadRequest, NotFound
from .tree import GitTree

SCHEMA = "lemmata.experiments/1"
LOWER_RE = re.compile(r"loss|error|\berr\b|mse|mae|rmse|mape|delay|time|latency|fpr|fnr|perplex|\bppl\b|dist|\bwer\b|\bcer\b|regret|fid\b", re.I)
LABEL_COLS = ("method", "model", "name", "detector", "approach", "algorithm", "system", "baseline", "variant", "setting", "config")
DATA_COLS = ("dataset", "data", "benchmark", "task", "corpus", "domain")
SEED_COLS = ("seed", "run", "fold", "trial", "rep", "repeat")
OURS_RE = re.compile(r"\b(ours?|proposed|this work|full model|full)\b", re.I)
NUM_RE = re.compile(r"^\s*([-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?)\s*(%)?\s*(?:(?:±|\+/-|\\pm|\+-)\s*(\d+(?:\.\d+)?))?\s*%?\s*$")
EVAL_PATH = re.compile(r"eval|metric|scor|benchmark", re.I)
DATA_PATH = re.compile(r"(^|/)data|dataset|loader|preprocess|split", re.I)
MAX_VERSIONS, MAX_BYTES = 30, 2 * 1024 * 1024


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def num(s):
    """'0.91', '91.2%', '0.91 ± 0.02' -> (value, std, is_percent, decimals) or None."""
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return float(s), None, False, None
    m = NUM_RE.match(str(s).replace("$", "").replace("\\%", "%"))
    if not m:
        return None
    txt = m.group(1).replace(",", ".") if m.group(1).count(",") == 1 and "." not in m.group(1) else m.group(1)
    try:
        v = float(txt)
    except ValueError:
        return None
    dec = len(txt.split(".")[1].split("e")[0].split("E")[0]) if "." in txt else 0
    return v, (float(m.group(3)) if m.group(3) else None), bool(m.group(2)) or "%" in str(s), dec


# ------------------------------------------------------------------ result files
def parse_result(path, data):
    """A result file -> {"cols": [...], "rows": [{"label", "values": {col: v}, "std": {col: s}, "n": {col: n}}], "seeds": bool} or None."""
    if data is None or len(data) > MAX_BYTES:
        return None
    text = data.decode("utf-8", "replace")
    recs = None
    low = path.lower()
    if low.endswith(".json"):
        try:
            d = json.loads(text)
        except ValueError:
            return None
        if isinstance(d, dict) and d and all(isinstance(v, dict) for v in d.values()):
            recs = [dict(v, **{"method": k}) for k, v in d.items()]
        elif isinstance(d, list) and d and all(isinstance(v, dict) for v in d):
            recs = d
        elif isinstance(d, dict):
            flat = {k: v for k, v in d.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
            recs = [flat] if flat else None
    elif low.endswith((".csv", ".tsv", ".txt")):
        try:
            dialect = csv.Sniffer().sniff(text[:4000], delimiters=",\t;|")
        except csv.Error:
            dialect = csv.excel_tab if low.endswith(".tsv") else csv.excel
        rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
        if len(rows) >= 2:
            head = [h.strip() for h in rows[0]]
            if all(num(h) is None for h in head if h):
                recs = [dict(zip(head, [c.strip() for c in r])) for r in rows[1:500]]
    if not recs:
        return None
    keys = []
    for r in recs:
        for k in r:
            if k not in keys:
                keys.append(k)
    is_num = {k: sum(num(r.get(k)) is not None for r in recs) >= max(1, 0.6 * sum(r.get(k) not in (None, "") for r in recs)) for k in keys}
    pick = lambda names: next((k for k in keys if norm(k) in names), None)
    seed = pick(SEED_COLS)
    dset = pick(DATA_COLS)
    label = pick(LABEL_COLS) or next((k for k in keys if not is_num[k] and k not in (seed, dset)), None)
    metrics = [k for k in keys if is_num[k] and k not in (seed, label, dset) and k != ""]
    if not metrics:
        return None
    groups, order = {}, []
    for r in recs:
        lab = str(r.get(label, "")).strip() if label else "result"
        ds = str(r.get(dset, "")).strip() if dset else ""
        for mt in metrics:
            got = num(r.get(mt))
            if got is None:
                continue
            col = ("%s · %s" % (ds, mt) if len(metrics) > 1 else ds) if ds else mt
            if lab not in groups:
                groups[lab] = {}
                order.append(lab)
            groups[lab].setdefault(col, []).append((got[0], got[1]))
    cols = []
    for lab in order:
        for c in groups[lab]:
            if c not in cols:
                cols.append(c)
    rows = []
    for lab in order:
        vals, stds, ns = {}, {}, {}
        for c, xs in groups[lab].items():
            vs = [x[0] for x in xs]
            mean = sum(vs) / len(vs)
            vals[c], ns[c] = mean, len(vs)
            stds[c] = (sum((v - mean) ** 2 for v in vs) / (len(vs) - 1)) ** 0.5 if len(vs) > 1 else xs[0][1]
        rows.append({"label": lab, "values": vals, "std": stds, "n": ns})
    datasets = sorted({str(r.get(dset)).strip() for r in recs if dset and r.get(dset)}) if dset else []
    return {"cols": cols, "rows": rows, "seeds": bool(seed) or any(n > 1 for r in rows for n in r["n"].values()), "datasets": datasets,
            "label_col": label, "metrics": metrics}


def lower_better(col):
    return bool(LOWER_RE.search(col or ""))


def pick_ours(table, hints, bold_labels=()):
    labels = [r["label"] for r in table["rows"]]
    for lab in labels:
        if OURS_RE.search(lab):
            return lab, "name"
    hn = [norm(h) for h in hints if len(norm(h)) >= 2]
    for lab in labels:
        if norm(lab) in hn:
            return lab, "paper"
    for lab in labels:
        if norm(lab) in {norm(b) for b in bold_labels}:
            return lab, "bold"
    return (labels[-1], "last row") if len(labels) > 1 else (labels[0], "only row") if labels else (None, None)


def summarise(table, ours, col, lower):
    """-> {ours, best: {label, value}, gap (positive = ours is better), rank, of}"""
    vals = [(r["label"], r["values"][col]) for r in table["rows"] if col in r["values"]]
    mine = next((v for l, v in vals if l == ours), None)
    others = [(l, v) for l, v in vals if l != ours]
    if mine is None:
        return None
    best = (min if lower else max)(others, key=lambda x: x[1]) if others else None
    order = sorted(vals, key=lambda x: x[1], reverse=not lower)
    rank = 1 + sum(1 for l, v in vals if (v < mine if lower else v > mine))
    gap = None if best is None else round((best[1] - mine) if lower else (mine - best[1]), 10)
    row = next(r for r in table["rows"] if r["label"] == ours)
    return {"ours": mine, "std": row["std"].get(col), "n": row["n"].get(col, 1), "best": {"label": best[0], "value": best[1]} if best else None,
            "gap": gap, "rank": rank, "of": len(vals), "order": [l for l, _ in order]}


# ------------------------------------------------------------------ the paper's table, cell by cell
def paper_cells(P, node_id):
    """Raw cells of the first tabular in a table float -> [[{"tex", "text", "value", "std", "pct", "dec", "bold"}]] or None."""
    u = next((x for x in P.units if x.get("id") == node_id), None)
    if not u:
        return None
    body = "\n".join(l.code for l in P.lines[u["begin"]:u["end"] + 1])
    m = re.search(r"\\begin\{(tabular[x*]?|tabu|longtable)\}(.*?)\\end\{\1\}", body, re.S)
    if not m:
        return None
    inner = re.sub(r"^\s*(?:\{[^{}]*\}|\[[^\]]*\])*(?:\{(?:[^{}]|\{[^{}]*\})*\})", "", m.group(2), count=1)
    inner = re.sub(r"\\(?:hline|toprule|midrule|bottomrule|centering|small|footnotesize|scriptsize)\b|\\(?:cline|cmidrule)(?:\([^)]*\))?\{[^}]*\}", " ", inner)
    out = []
    for raw in re.split(r"\\\\(?:\[[^\]]*\])?", inner):
        if not raw.strip():
            continue
        row = []
        for c in re.split(r"(?<!\\)&", raw):
            c = re.sub(r"\\multi(?:column|row)\{[^}]*\}\{[^}]*\}\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1", c).strip()
            bold = bool(re.search(r"\\(?:textbf|mathbf|bm|boldsymbol)\b|\\bf\b", c))
            plain = re.sub(r"\\(?:textbf|mathbf|bm|boldsymbol|underline|textit|emph)\s*\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1", c)
            plain = re.sub(r"\\bf\b|[{}]", "", plain).replace("\\pm", "±").replace("$", "").replace("\\%", "%").strip()
            got = num(plain)
            row.append({"tex": c[:80], "text": detex(c)[:60], "value": got[0] if got else None, "std": got[1] if got else None,
                        "pct": got[2] if got else False, "dec": got[3] if got else None, "bold": bold})
        out.append(row[:12])
        if len(out) >= 40:
            break
    return out or None


def align(cells, table):
    """Compare each number in the paper's table with the result file. -> (grid with status per cell, tally, problems)"""
    if not cells:
        return None, None, []
    headless = any(c["value"] is not None for c in cells[0][1:])      # no header row: every row is data, columns go by position
    head = [] if headless else cells[0]
    first = 0 if headless else 1
    width = max(len(r) for r in cells) - 1
    labels = {norm(r["label"]): r for r in table["rows"]} if table else {}
    cols = {norm(c): c for c in table["cols"]} if table else {}
    allvals = [v for r in table["rows"] for v in r["values"].values()] if table else []
    tally = {"match": 0, "rounding": 0, "differs": 0, "loose": 0, "untraced": 0}
    problems = []

    def cmp(p, dec, pct, v):
        cands = [v] + ([v * 100] if pct or abs(v) <= 1 < abs(p) else [])
        tol = 0.5 * 10 ** -(dec or 0)
        best = None
        for cnd in cands:
            d = abs(cnd - p)
            # rounding: less than one unit of the last printed digit away (truncated, or rounded the other way)
            st = "match" if d <= tol + 1e-9 else "rounding" if d < 2 * tol - 1e-9 else "differs"
            if best is None or ("match", "rounding", "differs").index(st) < ("match", "rounding", "differs").index(best[0]):
                best = (st, cnd)
        return best

    def col_for(j):
        h = norm(head[j]["text"]) if j < len(head) else ""
        if h in cols:
            return cols[h]
        hit = [c for k, c in cols.items() if h and (h in k or k in h)]
        if len(hit) == 1:
            return hit[0]
        return table["cols"][j - 1] if table and not h and width == len(table["cols"]) else None

    for i, row in enumerate(cells):
        rl = norm(row[0]["text"]) if row else ""
        r = (labels.get(rl) or next((v for k, v in labels.items() if rl and (rl in k or k in rl)), None)) if i >= first else None
        for j, c in enumerate(row):
            if c["value"] is None or i < first or j == 0:
                continue
            col = col_for(j)
            if r is not None and col and col in r["values"]:
                st, shown = cmp(c["value"], c["dec"], c["pct"], r["values"][col])
                c.update(status=st, file=r["values"][col], file_shown=shown, row=r["label"], col=col)
                if st == "differs":
                    problems.append({"kind": "differs", "row": r["label"], "col": col, "paper": c["text"], "file": r["values"][col]})
            elif any(cmp(c["value"], c["dec"], c["pct"], v)[0] == "match" for v in allvals):
                c.update(status="loose")
            else:
                c.update(status="untraced")
            tally[c["status"]] += 1
    # the bold number in a column should be the best one in that column
    for j in range(1, max(len(r) for r in cells)):
        colcells = [(i, r[j]) for i, r in enumerate(cells) if i >= first and j < len(r) and r[j]["value"] is not None]
        bold = [c for _, c in colcells if c["bold"]]
        if not bold or len(colcells) < 2:
            continue
        low = lower_better(head[j]["text"] if j < len(head) else "")
        best = (min if low else max)(c["value"] for _, c in colcells)
        for c in bold:
            if abs(c["value"] - best) > 1e-12:
                c["bold_wrong"] = True
                problems.append({"kind": "bold", "col": head[j]["text"] if j < len(head) else "", "paper": c["text"], "best": best})
    return cells, tally, problems


# ------------------------------------------------------------------ history of one result file
def _category(paths, kinds):
    cats = set()
    for p in paths:
        k = kinds.get(p)
        if k == "config":
            cats.add("settings")
        elif EVAL_PATH.search(p):
            cats.add("evaluation")
        elif DATA_PATH.search(p) or k == "data":
            cats.add("data")
        elif k == "code":
            cats.add("method")
    return sorted(cats)


def _config_diff(root, rid, rev, paths):
    out = []
    try:
        new, old = GitTree(root, rid, rev), GitTree(root, rid, rev + "~1")
        for p in paths[:4]:
            a = codemod.config_keys(p, (old.read(p) or b"").decode("utf-8", "replace")) if old.has(p) else {}
            b = codemod.config_keys(p, (new.read(p) or b"").decode("utf-8", "replace")) if new.has(p) else {}
            for k in sorted(set(a) | set(b)):
                va, vb = (a.get(k) or (None,))[0], (b.get(k) or (None,))[0]
                if va != vb:
                    out.append({"key": k.split(".")[-1], "from": va, "to": vb})
        new.close()
        old.close()
    except Exception:
        pass
    return out[:8]


def history(events, infos, nodes, rid, path, ours, col, lower):
    """Every committed version of a result file, with the changes made between versions.
    -> [{time, short, rev, ours, best, best_label, rank, ruler, delta, changes: [...], attribution, cats}]"""
    info = infos.get(rid) or {}
    if info.get("vcs") != "git":
        return []
    kinds = {n["loc"]["path"]: n["kind"] for n in nodes.values() if n.get("repo") == rid and n.get("loc")}
    commits = [e for e in events if e.get("kind") == "commit" and e.get("rev")]
    touching = [e for e in commits if e["repo"] == rid and any(f["path"] == path for f in e.get("files", []))][-MAX_VERSIONS:]
    out, prev_cols, prev_time, prev = [], None, None, None
    for ev in touching:
        try:
            t = GitTree(info["abs_path"], rid, ev["rev"])
            tab = parse_result(path, t.read(path))
            t.close()
        except Exception:
            tab = None
        s = summarise(tab, ours, col, lower) if tab and col in tab["cols"] else None
        step = {"time": ev["time"], "short": ev["short"], "rev": ev["rev"], "subject": ev.get("subject") or "",
                "ours": s["ours"] if s else None, "best": s["best"]["value"] if s and s["best"] else None,
                "best_label": s["best"]["label"] if s and s["best"] else None, "rank": s["rank"] if s else None, "of": s["of"] if s else None,
                "ruler": bool(tab and prev_cols is not None and set(tab["cols"]) != set(prev_cols)), "changes": [], "cats": []}
        # what changed in the code repositories since the previous version of this file (this commit included)
        cats = set()
        for c in commits:
            if c["time"] and (prev_time is None or c["time"] > prev_time) and c["time"] <= ev["time"] and infos.get(c["repo"], {}).get("role") != "paper":
                paths = [f["path"] for f in c.get("files", []) if f["path"] != path]
                ck = {p: (kinds.get(p) if c["repo"] == rid else None) or ("config" if p.endswith((".yaml", ".yml", ".toml", ".json", ".cfg", ".ini")) and "result" not in p
                          else "code" if p.endswith((".py", ".sh", ".ipynb", ".jl", ".r", ".R", ".cpp", ".c", ".rs")) else None) for p in paths}
                cc = _category([p for p in paths if ck.get(p)], ck)
                if not cc or prev_time is None:
                    continue
                keys = _config_diff(infos[c["repo"]]["abs_path"], c["repo"], c["rev"], [p for p in paths if ck.get(p) == "config"]) if "settings" in cc else []
                step["changes"].append({"short": c["short"], "subject": c.get("subject") or "", "time": c["time"], "cats": cc, "keys": keys,
                                        "files": [p for p in paths if ck.get(p)][:6]})
                cats |= set(cc)
        step["cats"] = sorted(cats)
        if step["ruler"]:
            step["cats"] = sorted(cats | {"evaluation"})
        step["delta"] = None if prev is None or step["ours"] is None or prev["ours"] is None or step["ruler"] else round(step["ours"] - prev["ours"], 10)
        step["attribution"] = ("first" if prev is None else "ruler" if step["ruler"] or "evaluation" in step["cats"] else "none" if not step["changes"]
                               else "single" if len(step["cats"]) == 1 and len(step["changes"]) == 1 else "bundled")
        if prev is not None and step["rank"] and prev.get("rank") and step["rank"] == 1 and prev["rank"] > 1:
            step["became_best"] = True
        if tab:
            prev_cols = tab["cols"]
        prev_time, prev = ev["time"], step
        out.append(step)
    return out


# ------------------------------------------------------------------ everything together
def load(hub):
    d = hub.read_json("experiments.json", None)
    if not isinstance(d, dict):
        d = {}
    d.setdefault("schema", SCHEMA)
    d.setdefault("entries", {})
    return d


def decide(store, known, exp_id, ours=None, metric=None, lower=None):
    if exp_id not in known:
        raise NotFound("unknown experiment %r" % exp_id)
    e = store["entries"].setdefault(exp_id, {})
    for k, v in (("ours", ours), ("metric", metric)):
        if v is not None:
            if not isinstance(v, str) or len(v) > 200:
                raise BadRequest("%s must be text" % k)
            if v:
                e[k] = v
            else:
                e.pop(k, None)
    if lower is not None:
        e["lower"] = bool(lower)
    return e


def build(G, trees, infos, events, alarms, findings, claims_doc, ledger, store, github=None, detail=None):
    """-> the Experiments document; with detail=<experiment id>, that one experiment in full."""
    P = G.paper
    ctx = _Ctx(G, alarms, findings)
    ents = (store or {}).get("entries", {})
    github = github or {}
    led = {r["node_id"]: r for r in ledger["rows"]}
    core = claims_doc.get("core") or {}
    hints = re.findall(r"\(([A-Z][A-Za-z0-9\-]{1,14})\)", (core.get("abstract") or "") + " " + (core.get("title") or ""))
    hints += [w for w in re.split(r"[:\s]", (core.get("title") or "")) [:1] if w[:1].isupper()]
    cache = {}

    def table_of(nid):
        if nid not in cache:
            n = G.nodes[nid]
            tr = trees.get(n["repo"])
            try:
                cache[nid] = parse_result(n["loc"]["path"], tr.read(n["loc"]["path"])) if tr and tr.size(n["loc"]["path"]) <= MAX_BYTES else None
            except Exception:
                cache[nid] = None
        return cache[nid]

    def experiment(exp_id, full=False):
        n = G.nodes[exp_id]
        e = ents.get(exp_id, {})
        paper_item = n["kind"] in ("table", "figure")
        ch = ctx.chain(exp_id)
        results = [x for x in ([exp_id] if not paper_item else ch["results"]) if G.nodes[x]["kind"] in ("result", "data")]
        res = next((x for x in results if table_of(x)), None)
        tab = table_of(res) if res else None
        cells = paper_cells(P, exp_id) if (P is not None and n["kind"] == "table") else None
        bold_labels = [r[0]["text"] for r in (cells or [])[1:] if any(c["bold"] for c in r[1:])]
        x = {"id": exp_id, "name": n["name"], "kind": n["kind"], "caption": (n.get("attrs") or {}).get("caption") or (n.get("detail") if paper_item else "") or "",
             "loc": n.get("loc"), "repo": n["repo"], "result": None, "connected": bool(results or ch["code"] or ch["runs"]),
             "image": n["kind"] == "figure", "summary": None, "tally": None, "problems": [], "caveats": [], "stale": None, "history_n": 0, "spark": []}
        if not paper_item:
            x["name"] = n["name"].rsplit("/", 1)[-1]
        row = led.get(res) if res else None
        if row and row["status"] == "stale":
            x["stale"] = {"file": row["name"], "newer": row["newer"][:3]}
            x["caveats"].append({"k": "stale", "t": "Result older than code"})
        if row and row["made"]:
            x["last"] = row["made"]["time"]
        if tab:
            col = e.get("metric") if e.get("metric") in tab["cols"] else tab["cols"][0]
            ours, how = (e["ours"], "you") if e.get("ours") in [r["label"] for r in tab["rows"]] else pick_ours(tab, hints, bold_labels)
            lower = e["lower"] if "lower" in e else lower_better(col)
            s = summarise(tab, ours, col, lower)
            rn = G.nodes[res]
            x["result"] = {"node_id": res, "name": rn["name"], "path": rn["loc"]["path"], "repo": rn["repo"],
                           "github": github[rn["repo"]] + rn["loc"]["path"] if rn["repo"] in github else None}
            x["summary"] = dict(s or {}, ours_label=ours, ours_by=how, metric=col, lower=lower, metric_by="you" if e.get("metric") in tab["cols"] else "first column",
                                methods=[r["label"] for r in tab["rows"]], baselines=[r["label"] for r in tab["rows"] if r["label"] != ours],
                                cols=tab["cols"], datasets=tab["datasets"] or ([c for c in tab["cols"]] if len(tab["cols"]) > 1 and tab["metrics"] and len(tab["metrics"]) == 1 and tab["datasets"] else []))
            hist = history(events, infos, G.nodes, rn["repo"], rn["loc"]["path"], ours, col, lower)
            x["history_n"] = len(hist)
            x["spark"] = [{"o": h["ours"], "b": h["best"], "r": h["ruler"], "c": bool(h["changes"])} for h in hist]
            if s and s["n"] <= 1 and s.get("std") is None:
                x["caveats"].append({"k": "seeds", "t": "One run, no spread"})
            if len(tab["cols"]) == 1 and not tab["datasets"]:
                x["caveats"].append({"k": "single", "t": "One metric column"})
            if any(h["ruler"] or "evaluation" in h["cats"] for h in hist[1:]):
                x["caveats"].append({"k": "ruler", "t": "Evaluation changed"})
            if how not in ("you", "name", "paper"):
                x["caveats"].append({"k": "guess", "t": "“Ours” is a guess"})
            if full:
                x["table"] = {"cols": tab["cols"], "rows": tab["rows"], "seeds": tab["seeds"]}
                x["history"] = hist
        if cells:
            grid, tally, problems = align(cells, tab)
            x["tally"], x["problems"] = tally, problems
            if any(p["kind"] == "bold" for p in problems):
                x["caveats"].append({"k": "bold", "t": "Bold is not best"})
            if full:
                x["cells"] = grid
        if not x["connected"]:
            x["caveats"].append({"k": "untraced", "t": "No result file"})
        x["attention"] = bool(x["stale"] or (x["tally"] and (x["tally"]["differs"] or x["tally"]["untraced"])) or not x["connected"]
                              or any(p["kind"] == "bold" for p in x["problems"]))
        if full:
            link = lambda i: {"node_id": i, "name": G.nodes[i]["name"], "kind": G.nodes[i]["kind"],
                              "github": github[G.nodes[i]["repo"]] + G.nodes[i]["loc"]["path"] if G.nodes[i]["repo"] in github and G.nodes[i]["kind"] != "run" else None}
            up = ctx.chain(res) if res else {"code": [], "settings": [], "runs": [], "results": []}
            code = list(dict.fromkeys(ch["code"] + up["code"]))
            settings = list(dict.fromkeys(ch["settings"] + up["settings"]))
            if not settings and res:     # nothing links a settings file to this result: show the repository's own settings files
                settings = sorted(i for i, m in G.nodes.items() if m["kind"] == "config" and m["repo"] == G.nodes[res]["repo"])[:2]
            x["design"] = {"scripts": [link(i) for i in code], "settings": [link(i) for i in settings],
                           "runs": [dict(link(i), command=G.nodes[i]["attrs"].get("command")) for i in dict.fromkeys(ch["runs"] + up["runs"])], "values": []}
            for i in settings[:3]:
                sn = G.nodes[i]
                try:
                    src = trees[sn["repo"]].read(sn["loc"]["path"]).decode("utf-8", "replace")
                    for k, (v, ln) in list(codemod.config_keys(sn["loc"]["path"], src).items())[:24]:
                        x["design"]["values"].append({"key": k, "value": v, "file": sn["name"]})
                except Exception:
                    pass
        return x

    # which experiments each question / hypothesis rests on
    def exp_ids(c):
        out = []
        for s in c["support"]:
            if s["how"] == "suggested":
                continue
            nid = s.get("node_id")
            if nid and nid in G.nodes and G.nodes[nid]["kind"] in ("table", "figure", "result"):
                if nid not in out:
                    out.append(nid)
        return out

    if detail is not None:
        if detail not in G.nodes or G.nodes[detail]["kind"] not in ("table", "figure", "result", "data"):
            raise NotFound("unknown experiment %r" % detail)
        x = experiment(detail, full=True)
        x["questions"] = [{"id": c["id"], "label": c["label"], "text": c["text"]} for c in claims_doc["claims"] if c["state"] != "rejected" and detail in exp_ids(c)]
        return x

    sections, used = [], set()
    order = {"question": 0, "contribution": 1, "claim": 1}
    for c in sorted([c for c in claims_doc["claims"] if c["state"] != "rejected"], key=lambda c: order.get(c["kind"], 2)):
        ids = exp_ids(c)
        if c.get("formal") and not ids:
            continue
        exps = [experiment(i) for i in ids]
        used |= set(ids)
        for x in exps:
            used.add((x.get("result") or {}).get("node_id"))
        sections.append({"id": c["id"], "kind": "question" if c["kind"] == "question" else "hypothesis", "label": c["label"], "text": c["text"],
                         "status": c["status"], "state": c["state"], "recheck": bool(c["recheck"]), "experiments": exps,
                         "suggested": [{"node_id": s["node_id"], "name": s["name"]} for s in c["support"] if s["how"] == "suggested" and s.get("node_id")]})
    loose = []
    for nid, n in G.nodes.items():
        if nid in used:
            continue
        if n["kind"] in ("table", "figure") and not (n.get("attrs") or {}).get("in_appendix") or (n["kind"] == "result" and nid in led and not led[nid]["used_by"]):
            loose.append(experiment(nid))
    allx = [x for s in sections for x in s["experiments"]] + loose
    return {"schema": SCHEMA, "sections": sections, "unassigned": loose,
            "counts": {"questions": len(sections), "untested": sum(1 for s in sections if not s["experiments"]), "experiments": len({x["id"] for x in allx}),
                       "attention": len({x["id"] for x in allx if x["attention"]}), "versions": sum(x["history_n"] for x in {x["id"]: x for x in allx}.values())}}
