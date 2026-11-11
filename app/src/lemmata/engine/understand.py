"""Phase 1, "understand": the project map.

    brief   (rules)  what is in the project, short enough for a language model to read in one go
    propose (agent)  a project map written by the researcher's own agent (Claude Code over MCP), or a rule-only draft
    verify  (rules)  every entry of a proposed map is checked against the files; what cannot be checked is dropped
    confirm (person) the researcher accepts the map; only a confirmed map is used

The map says what "ours" is called, which questions and hypotheses the work tests, and which result files form which
experiment (a file pattern, not one file). Phase 2 (track.py) applies a confirmed map on every scan with no model.
No language model runs in this module or anywhere in the engine.
"""
import posixpath
import re

from . import code as codemod
from .claims import detex
from .errors import BadRequest, NotFound
from .experiments import DATA_COLS, LABEL_COLS, MAX_BYTES, SEED_COLS, norm, num, records

SCHEMA = "lemmata.map/1"
TYPES = ("main", "ablation", "sensitivity", "tuning", "efficiency", "analysis", "other")
TABLE_EXT = (".csv", ".tsv", ".json", ".txt")
NOTE_EXT = (".md", ".txt", ".rst", ".tex", ".org")
FIELD_RE = re.compile(r"\{([a-z][a-z0-9_]{0,23})\}")
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{0,39}$")
MAX_READ, MAX_PATTERN = 400, 200
TYPE_HINT = (("tuning", r"tun|hyper|search|sweep|grid|optuna"), ("ablation", r"ablat"), ("sensitivity", r"sensitiv|robust|vary"),
             ("efficiency", r"time|speed|memory|latency|efficien|runtime|cpu|gpu"), ("main", r"main|overall|benchmark|compar"))


# ------------------------------------------------------------------ file patterns
def compile_pattern(pat):
    """'results/{dataset}/run_{seed}.csv' -> (regex, [field names]). '*' stays inside one folder, '**' crosses folders,
    '{name}' captures one part of a name. Kept simple on purpose: no nested quantifiers, so matching cannot blow up."""
    if not isinstance(pat, str) or not pat.strip() or len(pat) > MAX_PATTERN:
        raise BadRequest("a file pattern must be 1 to %d characters" % MAX_PATTERN)
    pat = pat.strip().lstrip("./")
    out, fields = "", []
    for tok in re.split(r"(\{[a-z][a-z0-9_]{0,23}\}|\*\*/?|\*|\?)", pat):
        if not tok:
            continue
        m = FIELD_RE.fullmatch(tok)
        if m:
            if m.group(1) in fields or len(fields) >= 8:
                raise BadRequest("a file pattern can name at most 8 different {fields}")
            fields.append(m.group(1))
            out += "(?P<%s>[^/]+?)" % m.group(1)
        elif tok.startswith("**"):
            out += "(?:.*/)?" if tok.endswith("/") else ".*"
        elif tok == "*":
            out += "[^/]*"
        elif tok == "?":
            out += "[^/]"
        else:
            out += re.escape(tok)
    return re.compile("^" + out + "$"), fields


def result_files(G):
    """Every file that could hold results -> [(repo, path, node id)], sorted."""
    out = []
    for nid, n in G.nodes.items():
        p = (n.get("loc") or {}).get("path")
        if n["kind"] in ("result", "data") and p and p.lower().endswith(TABLE_EXT):
            out.append((n["repo"], p, nid))
    return sorted(out)


def match_files(patterns, files):
    """-> [(repo, path, node id, {field: value})] for files matching any pattern (first pattern wins)."""
    regs = []
    for p in patterns or []:
        try:
            regs.append(compile_pattern(p)[0])
        except BadRequest:
            pass
    out = []
    for repo, path, nid in files:
        for rx in regs:
            m = rx.match(path)
            if m:
                out.append((repo, path, nid, m.groupdict()))
                break
    return out


def _names_in(files, trees, limit=MAX_READ):
    """Every word that names something in the result files: file-name parts, column names, and text cells of every row."""
    out = set()
    for repo, path, _ in files[:limit]:
        out |= {norm(t) for t in re.split(r"[/,_=. ]", path) if t}
        out |= {norm(t) for t in re.split(r"[/,_= ]", path) if t}
        try:
            recs = records(path, trees[repo].read(path)) if trees[repo].size(path) <= MAX_BYTES else None
        except Exception:
            recs = None
        for r in (recs or [])[:500]:
            for k, v in r.items():
                out.add(norm(str(k)))
                if isinstance(v, str) and num(v) is None:
                    out.add(norm(v))
    out.discard("")
    return out


# ------------------------------------------------------------------ brief
def _tokens(name):
    stem, ext = posixpath.splitext(name)
    return re.split(r"([,_= ]|-(?=\D))", stem) + [ext]


def _generalise(paths):
    """Paths that share a shape -> (pattern with * where they differ, [[values seen at each * ...]])."""
    split = [[_tokens(seg) for seg in p.split("/")] for p in paths]
    if len({tuple(len(seg) for seg in s) for s in split}) != 1:
        d = {posixpath.dirname(p) for p in paths}
        ext = posixpath.splitext(paths[0])[1]
        return (d.pop() + "/" if len(d) == 1 and "" not in d else "**/" if len(d) > 1 else "") + "*" + ext, []
    out, varying = [], []
    for si in range(len(split[0])):
        seg = ""
        for ti in range(len(split[0][si])):
            vals = [s[si][ti] for s in split]
            if len(set(vals)) == 1:
                seg += vals[0]
            else:
                if not seg.endswith("*"):
                    seg += "*"
                    varying.append([])
                for v in vals:
                    if v not in varying[-1] and len(varying[-1]) < 8:
                        varying[-1].append(v)
        out.append(seg)
    return "/".join(out), varying


def clusters(files, trees, limit=60):
    """Group result files that look like runs of the same experiment: same folder shape, same columns.
    -> [{pattern, repo, n, examples, columns, rows (two sample rows), varies}]"""
    groups, order, read = {}, [], 0
    for repo, path, nid in files:
        cols, sample = None, []
        if read < MAX_READ:
            read += 1
            try:
                tr = trees.get(repo)
                recs = records(path, tr.read(path)) if tr and tr.size(path) <= MAX_BYTES else None
            except Exception:
                recs = None
            if recs:
                cols = tuple(str(k) for k in recs[0])[:24]
                sample = [{str(k): str(v)[:40] for k, v in list(r.items())[:12]} for r in recs[:2]]
        d = re.sub(r"\d+", "#", posixpath.dirname(path))
        shape = tuple(len(_tokens(seg)) for seg in path.split("/"))
        key = (repo, d, posixpath.splitext(path)[1].lower(), cols, shape if cols is None else None)
        if key not in groups:
            groups[key] = {"repo": repo, "paths": [], "columns": list(cols or []), "rows": sample, "nodes": []}
            order.append(key)
        groups[key]["paths"].append(path)
        groups[key]["nodes"].append(nid)
    out = []
    for key in order:
        g = groups[key]
        pattern, varies = _generalise(g["paths"]) if len(g["paths"]) > 1 else (g["paths"][0], [])
        out.append({"pattern": pattern, "repo": g["repo"], "n": len(g["paths"]), "examples": g["paths"][:4], "columns": g["columns"],
                    "rows": g["rows"], "varies": varies[:6], "nodes": g["nodes"]})
    out.sort(key=lambda c: (-c["n"], c["pattern"]))
    return out[:limit]


def brief(G, trees, infos, events, claims_doc):
    """What the project holds, as plain data: the paper's outline and stated claims, its tables and figures, the result
    files grouped by shape, the scripts with their options, the settings, and the recent history."""
    P = G.paper
    core = claims_doc.get("core") or {}
    paper = {"title": core.get("title") or "", "abstract": (core.get("abstract") or "")[:1800], "sections": [], "stated": [], "floats": []}
    for n in G.nodes.values():
        loc = n.get("loc") or {}
        if n["kind"] == "section" and (n.get("attrs") or {}).get("level") == 1:
            paper["sections"].append({"name": n["name"], "path": loc.get("path"), "line": loc.get("line")})
        elif n["kind"] in ("table", "figure"):
            a = n.get("attrs") or {}
            f = {"id": n["id"], "name": n["name"], "label": a.get("tex_label"), "caption": (a.get("caption") or n.get("detail") or "")[:240],
                 "path": loc.get("path"), "line": loc.get("line"), "appendix": bool(a.get("in_appendix"))}
            if n["kind"] == "table" and P is not None:
                from .experiments import paper_cells
                cells = paper_cells(P, n["id"]) or []
                f["head"] = [[c["text"] for c in r[:8]] for r in cells[:3]]
            paper["floats"].append(f)
    for c in claims_doc.get("claims", []):
        if c.get("formal") or c["state"] == "rejected":
            continue
        loc = c.get("loc") or {}
        paper["stated"].append({"claim": c["id"], "kind": c["kind"], "label": c["label"], "text": c["text"][:400], "path": loc.get("path"), "line": loc.get("line")})
    paper["sections"].sort(key=lambda s: (s["path"] or "", s["line"] or 0))
    files = result_files(G)
    cl = clusters(files, trees)
    for c in cl:
        c.pop("nodes", None)
    scripts, settings = [], []
    for n in sorted(G.nodes.values(), key=lambda n: n["id"]):
        p = (n.get("loc") or {}).get("path")
        if not p or n["repo"] not in trees:
            continue
        if n["kind"] == "code" and len(scripts) < 60:
            try:
                src = trees[n["repo"]].read(p).decode("utf-8", "replace") if trees[n["repo"]].size(p) <= 300000 else ""
            except Exception:
                src = ""
            opts = list(dict.fromkeys(re.findall(r"add_argument\(\s*['\"](--?[\w\-]+)", src)))[:20]
            writes = list(dict.fromkeys(re.findall(r"['\"]([\w./{}\-]*\.(?:csv|tsv|json))['\"]", src)))[:6]
            scripts.append({"path": p, "repo": n["repo"], "options": opts, "mentions_files": writes})
        elif n["kind"] == "config" and len(settings) < 6:
            try:
                keys = codemod.config_keys(p, trees[n["repo"]].read(p).decode("utf-8", "replace"))
            except Exception:
                keys = {}
            settings.append({"path": p, "repo": n["repo"], "values": {k: v[0] for k, v in list(keys.items())[:30]}})
    roles = {i["id"]: i["role"] for i in infos.values()}
    commits = [e for e in events if e.get("kind") == "commit" and roles.get(e["repo"]) != "paper"][-30:]
    history = [{"day": (e.get("time") or "")[:10], "short": e.get("short"), "subject": (e.get("subject") or "")[:100],
                "files": len(e.get("files", []))} for e in commits]
    return {"schema": "lemmata.brief/1", "paper": paper, "result_files": {"total": len(files), "groups": cl}, "scripts": scripts,
            "settings": settings, "history": history, "repos": [{"id": i["id"], "role": i["role"]} for i in infos.values()]}


GUIDE = """How to write a project map for Lemmata.

Read the brief (and, if you have the repository open, the paper and the code themselves). Then call propose_map with:

{
  "method": {"name": "<the name the paper gives its own method>", "aliases": ["<other spellings used in result files or code>"],
             "evidence": [{"path": "main.tex", "line": 12, "quote": "<a few words copied from that line>"}]},
  "base": {"name": "<only for an extension: the method of the paper being extended>", "aliases": [], "evidence": []},
  "goal": "<only for an extension: one sentence, the new target the extension aims at>",
  "questions": [
    {"id": "q1", "kind": "question" | "hypothesis", "label": "RQ1",
     "text": "<one full sentence: what the paper sets out to show>",
     "claim": "<optional: the 'claim' id from the brief when the paper already states it>",
     "scope": "base | extension (only with a base: does it check the original paper's claim, or the extension's new one?)",
     "evidence": [{"path": "main.tex", "line": 40, "quote": "<words copied from the paper>"}]}
  ],
  "experiments": [
    {"id": "main", "name": "<short name>", "type": "main|ablation|sensitivity|tuning|efficiency|analysis|other",
     "tests": ["q1"],
     "files": ["results/{dataset}/{method}_seed{seed}.csv"],
     "metric": "<column name of the main number>", "lower": false, "target": null,
     "method_column": "<optional: column that names the method>", "dataset_column": "<optional>",
     "paper": ["tab:main"], "note": "<one line: what is varied, what is held fixed>"}
  ],
  "ignore": ["logs/**", "**/debug_*.csv"]
}

Rules Lemmata enforces (anything that fails is dropped and reported back to you):
- Every question needs evidence: a path and line and a short quote that really is there, in the paper or in the
  researcher's own notes (.md, .txt, .rst, .tex, .org anywhere in the repositories). Prefer the paper.
- When neither direction is right ("close to 0 is best"), set "target" to that value; lower/higher is then ignored.
- The method name or an alias must appear in the paper or in the result files (file names, columns or cells).
- Extending an earlier paper: when the linked paper describes the method being extended (not the new work), set
  "method" to the extension as it is named in the result files, "base" to the original method, and "goal" to the new
  target. Questions quoted from the paper are the original's claims (scope "base", to reproduce); questions from the
  notes are the extension's (scope "extension"). Experiments then compare ours with the base as well as the others.
- An experiment's files are patterns: * within a folder, ** across folders, {dataset} {method} {seed} or any other
  {field} for the part of a file name that encodes it. Each pattern must match at least one existing file.
- "metric" must be a real column of those files. "paper" lists table or figure labels (or ids from the brief).
- Put hyperparameter searches in type "tuning" and point them at the question they served. Put scratch output in "ignore".
- An experiment is a group of runs that answers one thing, not one file. Prefer few experiments.
- Do not invent questions the paper does not make. If a result serves no question, leave "tests" empty.
"""


# ------------------------------------------------------------------ verify
def _text(v, n, what):
    if not isinstance(v, str) or not v.strip():
        raise BadRequest("%s is missing" % what)
    return " ".join(v.split())[:n]


def _squash(s):
    return re.sub(r"[^a-z0-9]+", " ", detex(s or "").lower()).strip()


def verify(doc, G, trees, infos, claims_doc):
    """Check a proposed map against the project. -> (clean map, report). Nothing that fails a rule survives."""
    if not isinstance(doc, dict):
        raise BadRequest("the map must be a JSON object")
    report = []
    note = lambda level, where, why: report.append({"level": level, "where": where, "why": why})
    files = result_files(G)
    roles = {i["id"]: i["role"] for i in infos.values()}
    order = sorted(trees, key=lambda r: roles.get(r) != "paper")
    cache = {}

    def lines_of(path):
        path = (path or "").split(":", 1)[-1].lstrip("./")
        if path not in cache:
            cache[path] = None
            for rid in order:
                try:
                    if trees[rid].has(path) and trees[rid].size(path) <= MAX_BYTES:
                        cache[path] = (rid, trees[rid].read(path).decode("utf-8", "replace").split("\n"))
                        break
                except Exception:
                    pass
        return path, cache[path]

    def evidence(items, where, need_paper=False):
        ok = []
        for ev in capped(items, 6, where, "evidence entries"):
            if not isinstance(ev, dict):
                continue
            path, got = lines_of(str(ev.get("path") or ""))
            if got is None:
                note("dropped", where, "evidence points at %r, which does not exist" % path)
                continue
            rid, lines = got
            line = ev.get("line") if isinstance(ev.get("line"), int) and 1 <= ev.get("line") <= len(lines) else None
            quote = " ".join(str(ev.get("quote") or "").split())[:200]
            source = "paper" if roles.get(rid) == "paper" else "notes" if path.lower().endswith(NOTE_EXT) else None
            if need_paper and (source is None or not quote):
                note("dropped", where, "evidence must quote the paper or a notes file (%s)" % ", ".join(NOTE_EXT))
                continue
            if quote:
                q = _squash(quote)
                near = range(max(0, line - 6), min(len(lines), line + 6)) if line else range(len(lines))
                hit = next((i for i in near if q and q in _squash(" ".join(lines[i:i + 3]))), None)
                if hit is None and line:
                    hit = next((i for i in range(len(lines)) if q and q in _squash(" ".join(lines[i:i + 3]))), None)
                if hit is None:
                    note("dropped", where, "the quote %r is not in %s" % (quote[:50], path))
                    continue
                first = " ".join(q.split()[:3])
                line = 1 + next((j for j in range(hit, min(hit + 3, len(lines))) if first in _squash(lines[j])), hit)
            ok.append(dict({"repo": rid, "path": path, "line": line, "quote": quote}, **({"source": source} if need_paper else {})))
        return ok

    def capped(items, n, where, what):
        items = items if isinstance(items, list) else []
        if len(items) > n:
            note("dropped", where, "only the first %d %s are kept; %d more were ignored" % (n, what, len(items) - n))
        return items[:n]

    out = {"schema": SCHEMA, "method": None, "base": None, "goal": None, "questions": [], "experiments": [], "ignore": []}
    for k in sorted(set(doc) - {"schema", "method", "base", "goal", "questions", "experiments", "ignore", "proposed_by"}):
        note("dropped", "map", "unknown field %r (the map has: method, base, goal, questions, experiments, ignore)" % str(k)[:30])
    for k in sorted(set(doc.get("method") or {}) - {"name", "aliases", "evidence", "note"} if isinstance(doc.get("method"), dict) else []):
        note("dropped", "method", "unknown field %r inside method%s" % (str(k)[:30], "; base and goal go at the top level of the map" if k in ("base", "goal") else ""))
    # method (ours) and, for an extension, the method of the paper being extended (base)
    hay = _squash(" ".join(l.code for l in G.paper.lines)) if G.paper is not None else ""
    labels = _names_in(files, trees)
    seen = lambda name: (" " + _squash(name) + " ") in (" " + hay + " ") or norm(name) in labels

    def named(m, where):
        if not (isinstance(m, dict) and isinstance(m.get("name"), str) and m["name"].strip()):
            return None
        name = _text(m["name"], 60, "%s name" % where)
        als = [a for a in dict.fromkeys(_text(a, 60, "alias") for a in capped(m.get("aliases") or [], 8, where, "aliases") if isinstance(a, str) and a.strip()) if a != name]
        for a in [a for a in als if not seen(a)]:
            note("dropped", where, "the alias %r appears neither in the paper nor in the result files" % a)
        als = [a for a in als if seen(a)]
        if seen(name) or als:
            return {"name": name, "aliases": als, "evidence": evidence(m.get("evidence"), where)}
        note("dropped", where, "the name %r appears neither in the paper nor in the result files" % name)
        return None

    out["method"] = named(doc.get("method"), "method")
    if out["method"] is None and not (isinstance(doc.get("method"), dict) and doc["method"].get("name")):
        note("warning", "method", "no method name given: “ours” will be guessed for every experiment")
    if doc.get("base") is not None:
        out["base"] = named(doc.get("base"), "base")
        if out["base"] and out["method"] and norm(out["base"]["name"]) == norm(out["method"]["name"]):
            note("dropped", "base", "the base method has the same name as ours")
            out["base"] = None
    if doc.get("goal") is not None and not isinstance(doc.get("goal"), str):
        note("dropped", "goal", "the goal must be one sentence of plain text")
    if isinstance(doc.get("goal"), str) and doc["goal"].strip():
        out["goal"] = " ".join(doc["goal"].split())[:300]
        if not out.get("base"):
            note("warning", "goal", "a goal is set but no base method: the goal is kept, nothing is compared with a base")
    # questions and hypotheses
    claim_ids = {c["id"] for c in claims_doc.get("claims", [])}
    qids = set()
    for i, q in enumerate(capped(doc.get("questions"), 20, "questions", "questions")):
        where = "question %s" % (q.get("id") if isinstance(q, dict) else i + 1)
        try:
            qid = q.get("id") if isinstance(q.get("id"), str) and ID_RE.match(q["id"]) else "q%d" % (i + 1)
            if qid in qids:
                raise BadRequest("the id %r is used twice" % qid)
            text = _text(q.get("text"), 500, "text")
            ev = evidence(q.get("evidence"), where, need_paper=True)
            if not ev:
                raise BadRequest("no evidence in the paper or notes survived checking")
            kind = "question" if q.get("kind") == "question" else "hypothesis"
            claim = q.get("claim") if q.get("claim") in claim_ids else None
            if q.get("claim") and not claim:
                note("warning", where, "the claim id %r does not exist; treated as a new statement" % q.get("claim"))
            n_same = sum(1 for x in out["questions"] if x["kind"] == kind) + 1
            label = _text(q["label"], 24, "label") if isinstance(q.get("label"), str) and q["label"].strip() else ("RQ%d" if kind == "question" else "H%d") % n_same
            source = "paper" if any(e["source"] == "paper" for e in ev) else "notes"
            scope = q.get("scope") if q.get("scope") in ("base", "extension") else ("base" if source == "paper" else "extension") if out.get("base") else None
            out["questions"].append({"id": qid, "kind": kind, "label": label, "text": text, "claim": claim, "evidence": ev, "source": source, "scope": scope})
            qids.add(qid)
        except (BadRequest, AttributeError) as e:
            note("dropped", where, str(e) if isinstance(e, BadRequest) else "not an object")
    # experiments
    by_label = {}
    for n in G.nodes.values():
        if n["kind"] in ("table", "figure"):
            by_label[n["id"].lower()] = n["id"]
            by_label[n["name"].lower()] = n["id"]
            if (n.get("attrs") or {}).get("tex_label"):
                by_label[n["attrs"]["tex_label"].lower()] = n["id"]
    xids, claimed = set(), {}
    for i, x in enumerate(capped(doc.get("experiments"), 60, "experiments", "experiments")):
        where = "experiment %s" % (x.get("id") if isinstance(x, dict) else i + 1)
        try:
            xid = x.get("id") if isinstance(x.get("id"), str) and ID_RE.match(x["id"]) else "x%d" % (i + 1)
            if xid in xids:
                raise BadRequest("the id %r is used twice" % xid)
            pats = []
            for p in capped(x.get("files"), 24, where, "file patterns"):
                try:
                    compile_pattern(p)
                except BadRequest as e:
                    note("dropped", where, "pattern %r: %s" % (str(p)[:60], e))
                    continue
                if match_files([p], files):
                    pats.append(p.strip().lstrip("./"))
                else:
                    note("dropped", where, "the pattern %r matches no result file" % p[:80])
            paper = []
            for ref in capped(x.get("paper"), 8, where, "paper items"):
                nid = by_label.get(str(ref).lower()) or by_label.get("tex:" + str(ref).lower())
                if nid and nid not in paper:
                    paper.append(nid)
                elif not nid:
                    note("dropped", where, "the paper has no table or figure %r" % str(ref)[:40])
            if not pats and not paper:
                raise BadRequest("it points at no existing result file and no table or figure")
            hit = match_files(pats, files)
            cols = set()
            for repo, path, nid, _ in hit[:5]:
                try:
                    recs = records(path, trees[repo].read(path)) or []
                except Exception:
                    recs = []
                cols |= {str(k) for r in recs[:3] for k in r}
            col = lambda k: x.get(k) if isinstance(x.get(k), str) and x.get(k) in cols else None
            for k in ("metric", "method_column", "dataset_column"):
                if x.get(k) and not col(k) and pats:
                    note("warning", where, "%s %r is not a column of its files (columns: %s)" % (k.replace("_", " "), str(x.get(k))[:40], ", ".join(sorted(cols)[:8]) or "none"))
            tests = [t for t in (x.get("tests") if isinstance(x.get("tests"), list) else []) if t in qids]
            for t in (x.get("tests") if isinstance(x.get("tests"), list) else []):
                if t not in qids:
                    note("warning", where, "it names question %r, which is not in the map" % str(t)[:30])
            for repo, path, nid, _ in hit:
                claimed.setdefault(nid, []).append(xid)
            out["experiments"].append({"id": xid, "name": _text(x.get("name") or xid, 60, "name"), "type": x.get("type") if x.get("type") in TYPES else "other",
                                       "tests": list(dict.fromkeys(tests)), "files": pats, "metric": col("metric"),
                                       "lower": x.get("lower") if isinstance(x.get("lower"), bool) else None, "method_column": col("method_column"),
                                       "target": x.get("target") if isinstance(x.get("target"), (int, float)) and not isinstance(x.get("target"), bool) else None,
                                       "dataset_column": col("dataset_column"),
                                       "ours": _text(x["ours"], 60, "ours") if isinstance(x.get("ours"), str) and x["ours"].strip() else None,
                                       "paper": paper, "note": " ".join(str(x.get("note") or "").split())[:300], "matched": len(hit)})
            xids.add(xid)
        except (BadRequest, AttributeError) as e:
            note("dropped", where, str(e) if isinstance(e, BadRequest) else "not an object")
    twice = sorted({", ".join(v) for v in claimed.values() if len(v) > 1})
    for pair in twice[:5]:
        note("warning", "experiments", "some files belong to more than one experiment: %s" % pair)
    for p in capped(doc.get("ignore"), 40, "ignore", "ignore patterns"):
        try:
            compile_pattern(p)
            out["ignore"].append(p.strip().lstrip("./"))
        except BadRequest as e:
            note("dropped", "ignore", "pattern %r: %s" % (str(p)[:60], e))
    if not out["experiments"]:
        note("warning", "experiments", "no experiment survived checking")
    return out, report


# ------------------------------------------------------------------ rule-only draft (no agent)
def _name(c):
    folder = posixpath.basename(posixpath.dirname(c["examples"][0]))
    if folder and folder.lower() not in ("results", "result", "outputs", "output", "out", "tables", "logs", "data") and "*" not in posixpath.dirname(c["pattern"]):
        return folder[:60]
    stem = posixpath.commonprefix([posixpath.basename(p) for p in c["examples"]]).rsplit(".", 1)[0].strip("_-, =")
    return (stem or re.sub(r"[*=]+", " ", posixpath.basename(c["pattern"]).rsplit(".", 1)[0]).strip("_-, ") or c["pattern"])[:60]


def draft(G, trees, infos, events, claims_doc):
    """A first map made by rules alone: the stated questions and contributions, one experiment per group of result files.
    Rough on purpose; it exists so the page is usable before an agent has read the project."""
    core = claims_doc.get("core") or {}
    title = core.get("title") or ""
    names = re.findall(r"\(([A-Z][A-Za-z0-9\-]{1,14})\)", (core.get("abstract") or "") + " " + title)
    head = re.split(r"[:\s]", title.strip())[:1]
    names += [w for w in head if w[:1].isupper() and (w.isupper() or ":" in title)]
    doc = {"method": {"name": names[0]} if names else None, "questions": [], "experiments": [], "ignore": []}
    paper_repo = next((i["id"] for i in infos.values() if i["role"] == "paper"), None)
    src = {}
    for c in claims_doc.get("claims", []):
        loc = c.get("loc") or {}
        if c.get("formal") or c["state"] == "rejected" or c["kind"] not in ("question", "contribution", "claim") or not loc.get("line") or paper_repo not in trees:
            continue
        if loc["path"] not in src:
            try:
                src[loc["path"]] = trees[paper_repo].read(loc["path"]).decode("utf-8", "replace").split("\n")
            except Exception:
                src[loc["path"]] = []
        raw = _squash(" ".join(src[loc["path"]][loc["line"] - 1:loc["line"] + 2])).split()
        mine = _squash(c["text"]).split()
        at = next((i for i in range(len(raw)) if raw[i:i + 4] == mine[:4]), 0)      # quote the paper's own words for this claim
        doc["questions"].append({"id": re.sub(r"[^A-Za-z0-9]+", "", c["id"]) or "q", "kind": "question" if c["kind"] == "question" else "hypothesis",
                                 "label": c["label"], "text": c["text"], "claim": c["id"],
                                 "evidence": [{"path": loc["path"], "line": loc["line"], "quote": " ".join(raw[at:at + 6])}], "_claim": c})
    cl = clusters(result_files(G), trees)
    used_by = {}
    for e in G.edges.values():
        if e["to"] in G.nodes and e["from"] in G.nodes and G.nodes[e["from"]]["kind"] in ("table", "figure"):
            used_by.setdefault(e["to"], []).append(e["from"])
    for i, c in enumerate(cl[:30]):
        base = re.sub(r"[^a-z0-9]+", " ", c["pattern"].lower())
        typ = next((t for t, rx in TYPE_HINT if re.search(rx, base)), "other")
        paper = list(dict.fromkeys(p for n in c["nodes"] for p in used_by.get(n, [])))[:4]
        tests = [q["id"] for q in doc["questions"] if any(s.get("node_id") in paper and s["how"] != "suggested" for s in q["_claim"]["support"])]
        numeric = [k for k in c["columns"] if c["rows"] and num(c["rows"][0].get(k)) is not None and norm(k) not in SEED_COLS + LABEL_COLS + DATA_COLS]
        doc["experiments"].append({"id": "x%d" % (i + 1), "name": _name(c), "type": typ,
                                   "tests": tests, "files": [c["pattern"]], "metric": numeric[0] if numeric else None, "paper": paper})
    for q in doc["questions"]:
        q.pop("_claim")
    return doc


# ------------------------------------------------------------------ storage and edits
def load(hub):
    d = hub.read_json("map.json", None)
    if not isinstance(d, dict) or not str(d.get("schema", "")).startswith("lemmata.map/1"):
        d = {}
    d.setdefault("schema", SCHEMA)
    for k in ("confirmed", "proposed"):
        d.setdefault(k, None)
    d.setdefault("report", [])
    return d


def edit(m, patch):
    """Small corrections a person makes while reviewing a map. Returns the raw map to verify again."""
    if not isinstance(m, dict):
        raise NotFound("there is no map to change")
    if not isinstance(patch, dict):
        raise BadRequest("the change must be an object")
    m = {k: (dict(v) if isinstance(v, dict) else [dict(x) if isinstance(x, dict) else x for x in v] if isinstance(v, list) else v) for k, v in m.items()}
    if "method" in patch:
        name = patch["method"]
        if not isinstance(name, str) or len(name) > 60:
            raise BadRequest("the method name must be text")
        old = m.get("method") or {}
        m["method"] = {"name": name.strip(), "aliases": [a for a in [old.get("name")] + (old.get("aliases") or []) if a and a != name.strip()],
                       "evidence": old.get("evidence") or []} if name.strip() else None
    if "base" in patch:
        name = patch["base"]
        if not isinstance(name, str) or len(name) > 60:
            raise BadRequest("the base method name must be text")
        old = m.get("base") or {}
        m["base"] = {"name": name.strip(), "aliases": [a for a in [old.get("name")] + (old.get("aliases") or []) if a and a != name.strip()],
                     "evidence": old.get("evidence") or []} if name.strip() else None
        if m["base"] is None:
            for q in m["questions"]:
                q["scope"] = None
    if "goal" in patch:
        if not isinstance(patch["goal"], str) or len(patch["goal"]) > 300:
            raise BadRequest("the goal must be at most 300 characters")
        m["goal"] = patch["goal"].strip() or None
    if "question" in patch:
        p = patch["question"]
        q = next((q for q in m["questions"] if isinstance(p, dict) and q["id"] == p.get("id")), None)
        if q is None:
            raise NotFound("unknown question")
        if p.get("scope") not in ("base", "extension", None):
            raise BadRequest("scope must be base or extension")
        q["scope"] = p.get("scope")
    if "remove" in patch:
        kind, _, rid = str(patch["remove"]).partition(":")
        if kind not in ("experiment", "question") or not any(x["id"] == rid for x in m[kind + "s"]):
            raise NotFound("unknown %s" % patch["remove"])
        m[kind + "s"] = [x for x in m[kind + "s"] if x["id"] != rid]
        if kind == "question":
            for x in m["experiments"]:
                x["tests"] = [t for t in x["tests"] if t != rid]
    if "experiment" in patch:
        p = patch["experiment"]
        x = next((x for x in m["experiments"] if isinstance(p, dict) and x["id"] == p.get("id")), None)
        if x is None:
            raise NotFound("unknown experiment")
        if "type" in p:
            if p["type"] not in TYPES:
                raise BadRequest("type must be one of %s" % ", ".join(TYPES))
            x["type"] = p["type"]
        if "tests" in p:
            if not isinstance(p["tests"], list):
                raise BadRequest("tests must be a list of question ids")
            x["tests"] = [t for t in p["tests"] if isinstance(t, str)]
        for k in ("metric", "name"):
            if isinstance(p.get(k), str):
                x[k] = p[k]
        if isinstance(p.get("lower"), bool):
            x["lower"] = p["lower"]
    if "ignore" in patch:
        pat = patch["ignore"]
        compile_pattern(pat)
        if pat not in m["ignore"]:
            m["ignore"] = m["ignore"] + [pat.strip().lstrip("./")]
    # stored evidence already carries repo and line; verify() accepts that shape again
    return m


def coverage(m, G, trees):
    """What a map does not cover: result files no experiment or ignore pattern matches, and main-text tables and figures
    no experiment feeds. -> {"files": [clusters], "paper": [...], "n_files", "matched"}"""
    files = result_files(G)
    exps = (m or {}).get("experiments", [])
    taken = {f[2] for x in exps for f in match_files(x["files"], files)} | {f[2] for f in match_files((m or {}).get("ignore", []), files)}
    loose = [f for f in files if f[2] not in taken]
    cl = clusters(loose, trees, limit=40)
    for c in cl:
        c.pop("rows", None)
        c.pop("nodes", None)
    used = {p for x in exps for p in x["paper"]}
    paper = [{"node_id": n["id"], "name": n["name"], "kind": n["kind"], "caption": ((n.get("attrs") or {}).get("caption") or n.get("detail") or "")[:120]}
             for n in G.nodes.values() if n["kind"] in ("table", "figure") and not (n.get("attrs") or {}).get("in_appendix") and n["id"] not in used]
    return {"files": cl, "n_files": len(loose), "matched": len(files) - len(loose), "total": len(files), "paper": paper}
