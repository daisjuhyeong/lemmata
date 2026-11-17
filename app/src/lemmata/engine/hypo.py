"""S27, hypothesis-first mode: the research's own question, hypotheses and tests are the source until a paper exists.

    detect   (rules)  which files hold the protocol, the report, the notes, the deviation log and the test tables
    jobs     (rules)  what the researcher's own LLM is asked to do; Lemmata never calls a model
    submit   (rules)  every answer is checked against the files (quotes must be there, files must exist); what fails is dropped
    act      (person) Confirm, Fix, Delete, Combine, Tell; an LLM proposal only changes the project when the researcher accepts it
    assess   (rules)  each hypothesis's stage, read from the project's own test table; deviations and their timing from the log

Stages are the S17 words (claims.STAGES). Nothing here reaches the network or a language model.
"""
import csv
import io
import json
import re
import time

from .errors import BadRequest, NotFound

SCHEMA = "lemmata.hypothesis/1"
TIERS = ("confirmatory", "secondary", "exploratory")
STANCES = ("held", "tested")
PROBLEM_FIELDS = ("gap", "why_it_matters", "approach", "if_solved")
PROBLEM_WORDS = {"gap": "Gap", "why_it_matters": "Why it matters", "approach": "Approach", "if_solved": "If it works"}
JOB_TYPES = ("understand_problem", "draft_hypotheses", "revise", "combine", "comprehend_input", "premise_check")
OPS = ("add", "revise", "merge", "archive", "relink")
REVISABLE = ("statement", "answers", "tier", "stance", "criterion_text", "tested_by")
COND_OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
            "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{0,23}$")
DATE_RE = re.compile(r"(20\d\d-\d\d-\d\d)")
DEV_HEAD_RE = re.compile(r"^##\s+(D\d+)[.:]?\s*(.*?)\s*$")
HYP_REF_RE = re.compile(r"\b(H\d+[a-z]?)\b")
MAX_FILE, MAX_LIST = 2_000_000, 40

SOURCES = (
    ("hypothesis_source", (r"^protocol/[^/]+\.md$", r"^(?:PROTOCOL|PREREGISTRATION|preregistration)\.md$")),
    ("report", (r"^(?:FINDINGS|RESULTS|REPORT)\.md$",)),
    ("deviations", (r"(?:^|/)[^/]*deviation[^/]*\.md$",)),
    ("notes", (r"^notes/[^/]+\.md$",)),
    ("datasets_manifest", (r"^data/manifest\.csv$",)),
    ("progress", (r"^PROGRESS\.md$",)),
    ("readme", (r"^README\.md$",)),
    ("test_tables", (r"(?:^|/)tests?\.csv$",)),
)


def rel(p):
    """A repository path without a leading ./ (a plain lstrip would eat the dot of .lemmata/...)."""
    p = str(p or "").strip()
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ------------------------------------------------------------------ files
class Files:
    """Read access to the research repositories (every repo but the paper), first match wins."""

    def __init__(self, trees, infos):
        roles = {i["id"]: i["role"] for i in infos.values()}
        self.order = sorted(trees, key=lambda r: (roles.get(r) == "paper", r))
        self.trees = trees
        self._lines = {}

    def listing(self):
        out = []
        for rid in self.order:
            try:
                out += [(rid, p) for p in self.trees[rid].list_files()]
            except Exception:
                pass
        return out

    def find(self, path):
        path = rel(path)
        for rid in self.order:
            try:
                if self.trees[rid].has(path):
                    return rid, path
            except Exception:
                pass
        return None, path

    def lines(self, path):
        rid, path = self.find(path)
        if rid is None:
            return None
        if path not in self._lines:
            t = self.trees[rid]
            raw = t.read(path) if t.size(path) <= MAX_FILE else None
            self._lines[path] = raw.decode("utf-8", "replace").split("\n") if raw is not None else None
        return self._lines[path]

    def exists_prefix(self, path):
        """A deliverable is a file or a folder: True when the file exists or some file lies under the folder."""
        path = rel(path)
        if not path:
            return False
        if self.find(path)[0]:
            return True
        pre = path.rstrip("/") + "/"
        return any(p.startswith(pre) for _, p in self.listing())


def detect(files):
    """-> {kind: [paths]} for every source kind found in the research repositories."""
    out = {k: [] for k, _ in SOURCES}
    for _, p in files.listing():
        for kind, pats in SOURCES:
            if any(re.search(rx, p) for rx in pats):
                if kind == "notes" and "deviation" in p.lower():
                    continue
                out[kind].append(p)
                break
    for k in out:
        out[k] = sorted(dict.fromkeys(out[k]))[:MAX_LIST]
    return out


def wanted(src, has_paper):
    """Hypothesis-first is the default for a project without a paper that has a protocol or a findings report."""
    return not has_paper and bool(src["hypothesis_source"] or src["report"])


# ------------------------------------------------------------------ quotes
def squash(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def check_quote(files, ev, extra=None):
    """One piece of evidence {path, line, quote} -> the checked entry (line corrected to where the quote is) or None.
    extra: {path: text} for texts that are not files in the repository (the researcher's input)."""
    if not isinstance(ev, dict):
        return None
    path = rel(ev.get("path") or ev.get("file"))
    quote = " ".join(str(ev.get("quote") or "").split())[:240]
    if not path or not quote:
        return None
    lines = (extra or {}).get(path, "").split("\n") if path in (extra or {}) else files.lines(path)
    if lines is None:
        return None
    q = squash(quote)
    if not q:
        return None
    line = ev.get("line") if isinstance(ev.get("line"), int) and 1 <= ev.get("line") <= len(lines) else None
    near = list(range(max(0, line - 8), min(len(lines), line + 8))) if line else []
    for i in near + [i for i in range(len(lines)) if i not in near]:
        if q in squash(" ".join(lines[i:i + 4])):
            first = " ".join(q.split()[:3])
            hit = next((j for j in range(i, min(i + 4, len(lines))) if first in squash(lines[j])), i)
            return {"path": path, "line": hit + 1, "quote": quote}
    return None


def _evidence(files, items, where, report, need=False, extra=None, cap=6):
    ok = []
    for ev in (items if isinstance(items, list) else [])[:cap]:
        got = check_quote(files, ev, extra)
        if got:
            ok.append(got)
        else:
            report.append({"level": "dropped", "where": where, "why": "evidence %r is not in %s" % (
                str((ev or {}).get("quote", ""))[:60] if isinstance(ev, dict) else ev, (ev or {}).get("path", "?") if isinstance(ev, dict) else "?")})
    if need and not ok:
        raise BadRequest("no evidence survived checking (a path and a short quote that really is in that file)")
    return ok


def _text(v, n, what, required=True):
    if v is None or (isinstance(v, str) and not v.strip()):
        if required:
            raise BadRequest("%s is missing" % what)
        return None
    if not isinstance(v, str):
        raise BadRequest("%s must be text" % what)
    return " ".join(v.split())[:n]


# ------------------------------------------------------------------ test tables (no model)
def read_table(files, path):
    rid, path = files.find(path)
    if rid is None:
        return None
    t = files.trees[rid]
    if t.size(path) > MAX_FILE:
        return None
    raw = t.read(path).decode("utf-8", "replace")
    if path.endswith(".json"):
        try:
            d = json.loads(raw)
        except ValueError:
            return None
        return [r for r in (d if isinstance(d, list) else d.get("rows", []) if isinstance(d, dict) else []) if isinstance(r, dict)]
    dialect = "excel-tab" if path.endswith(".tsv") else "excel"
    return list(csv.DictReader(io.StringIO(raw), dialect=dialect))


def num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def check_rule(files, rule, where, report):
    """A machine-checkable criterion: {file, select: {column: value}, conditions: [{column, op, value}], report: [columns]}."""
    if rule is None:
        return None
    if not isinstance(rule, dict):
        report.append({"level": "dropped", "where": where, "why": "the rule must be an object"})
        return None
    path = rel(rule.get("file"))
    rows = read_table(files, path) if path else None
    if rows is None:
        report.append({"level": "dropped", "where": where, "why": "the rule's file %r does not exist or cannot be read" % path[:80]})
        return None
    cols = set(rows[0]) if rows else set()
    sel = rule.get("select") if isinstance(rule.get("select"), dict) else {}
    sel = {str(k): str(v) for k, v in list(sel.items())[:4]}
    for k in sel:
        if k not in cols:
            report.append({"level": "dropped", "where": where, "why": "select column %r is not in %s (columns: %s)" % (k, path, ", ".join(sorted(cols)[:10]))})
            return None
    hits = [r for r in rows if all(str(r.get(k, "")).strip() == v for k, v in sel.items())]
    if len(hits) != 1:
        report.append({"level": "dropped", "where": where, "why": "select %s matches %d rows of %s; it must match exactly one" % (json.dumps(sel), len(hits), path)})
        return None
    conds = []
    for c in (rule.get("conditions") if isinstance(rule.get("conditions"), list) else [])[:6]:
        if not isinstance(c, dict) or c.get("column") not in cols or c.get("op") not in COND_OPS or num(c.get("value")) is None:
            report.append({"level": "dropped", "where": where, "why": "condition %s: needs a real column, an op (%s) and a number" % (json.dumps(c)[:80], " ".join(COND_OPS))})
            return None
        conds.append({"column": c["column"], "op": c["op"], "value": num(c["value"])})
    if not conds:
        report.append({"level": "dropped", "where": where, "why": "the rule has no condition"})
        return None
    rep = [c for c in (rule.get("report") if isinstance(rule.get("report"), list) else []) if c in cols][:6]
    return {"file": path, "select": sel, "conditions": conds, "report": rep or [c["column"] for c in conds]}


def evaluate(files, rule):
    """-> {met: True|False|None, values, why, file}. None when the file or the row is missing (not run yet)."""
    rows = read_table(files, rule["file"])
    if rows is None:
        return {"met": None, "values": {}, "why": "%s does not exist yet" % rule["file"], "file": rule["file"]}
    hits = [r for r in rows if all(str(r.get(k, "")).strip() == v for k, v in rule["select"].items())]
    if len(hits) != 1:
        return {"met": None, "values": {}, "why": "%s has %d rows for %s" % (rule["file"], len(hits), json.dumps(rule["select"])), "file": rule["file"]}
    r = hits[0]
    vals = {c: num(r.get(c)) if num(r.get(c)) is not None else r.get(c) for c in rule["report"]}
    parts, met = [], True
    for c in rule["conditions"]:
        v = num(r.get(c["column"]))
        ok = v is not None and COND_OPS[c["op"]](v, c["value"])
        met = met and ok
        parts.append("%s %s %s %s (is %s)" % (c["column"], c["op"], _fmt(c["value"]), "✓" if ok else "✗", _fmt(v)))
    return {"met": met, "values": vals, "why": "; ".join(parts), "file": rule["file"]}


def _fmt(v):
    if isinstance(v, float):
        return ("%.4f" % v).rstrip("0").rstrip(".") if abs(v) >= 1e-3 or v == 0 else "%.1e" % v
    return str(v)


# ------------------------------------------------------------------ verify answers
def verify_problem(files, doc):
    report = []
    if not isinstance(doc, dict):
        raise BadRequest("the problem must be an object with %s" % ", ".join(PROBLEM_FIELDS))
    out, n_ev = {}, 0
    for k in PROBLEM_FIELDS:
        v = doc.get(k)
        if isinstance(v, str):
            v = {"text": v}
        if not isinstance(v, dict) or not (v.get("text") or "").strip():
            out[k] = {"text": None, "note": _text((v or {}).get("note") if isinstance(v, dict) else None, 200, "note", False) or "the sources do not say", "evidence": []}
            continue
        ev = _evidence(files, v.get("evidence"), PROBLEM_WORDS[k], report)
        n_ev += len(ev)
        out[k] = {"text": _text(v["text"], 600, PROBLEM_WORDS[k]), "evidence": ev}
    if not any(out[k]["text"] for k in PROBLEM_FIELDS):
        raise BadRequest("the problem is empty")
    if not n_ev:
        raise BadRequest("no field of the problem has evidence that survived checking")
    return out, report


def verify_hypothesis(files, h, where, report, frozen_files=(), extra=None, need_evidence=True):
    if not isinstance(h, dict):
        raise BadRequest("not an object")
    hid = h.get("id") if isinstance(h.get("id"), str) and ID_RE.match(h["id"]) else None
    if not hid:
        raise BadRequest("id must be a short name such as H1")
    stance = h.get("stance") if h.get("stance") in STANCES else "held"
    tier = h.get("tier") if h.get("tier") in TIERS else "exploratory"
    crit = h.get("criterion") if isinstance(h.get("criterion"), dict) else {}
    frozen = None
    fz = crit.get("frozen") if isinstance(crit.get("frozen"), dict) else None
    if fz and fz.get("file"):
        p = rel(fz["file"])
        if files.find(p)[0]:
            frozen = {"file": p}
        else:
            report.append({"level": "dropped", "where": where, "why": "frozen file %r does not exist" % p[:80]})
    if tier == "confirmatory" and not frozen:
        report.append({"level": "warning", "where": where, "why": "confirmatory, but no frozen design file: it can be tested, never a finding, until one is named"})
    src = None
    if stance == "tested":
        s = h.get("source") if isinstance(h.get("source"), dict) else {}
        src = {"cite": _text(s.get("cite"), 200, "source cite", False), "url": _text(s.get("url"), 300, "source url", False),
               "quote": _text(s.get("quote"), 300, "source quote", False), "locator": _text(s.get("locator"), 80, "source locator", False),
               "quote_check": "unverified"}
    ev = _evidence(files, h.get("evidence") or h.get("origin"), where, report, need=need_evidence, extra=extra)
    out = {"id": hid, "statement": _text(h.get("statement") or h.get("text"), 600, "statement"),
           "answers": _text(h.get("answers"), 300, "answers", False), "stance": stance, "tier": tier, "source": src,
           "criterion": {"text": _text(crit.get("text"), 400, "criterion text", False),
                         "rule": check_rule(files, crit.get("rule"), where, report), "frozen": frozen},
           "tested_by": [t for t in (h.get("tested_by") if isinstance(h.get("tested_by"), list) else []) if isinstance(t, str)][:8],
           "evidence": ev}
    return out


def verify_experiment(files, x, where, report):
    if not isinstance(x, dict):
        raise BadRequest("not an object")
    xid = x.get("id") if isinstance(x.get("id"), str) and ID_RE.match(x["id"]) else None
    if not xid:
        raise BadRequest("id must be a short name such as stepA")
    dl = []
    for p in (x.get("deliverables") if isinstance(x.get("deliverables"), list) else [])[:12]:
        if isinstance(p, str) and p.strip():
            dl.append(rel(p))
    return {"id": xid, "title": _text(x.get("title") or xid, 120, "title"), "deliverables": dl,
            "acceptance": _text(x.get("acceptance"), 300, "acceptance", False),
            "depends_on": [d for d in (x.get("depends_on") if isinstance(x.get("depends_on"), list) else []) if isinstance(d, str)][:6],
            "tests_claims": [d for d in (x.get("tests_claims") if isinstance(x.get("tests_claims"), list) else []) if isinstance(d, str)][:8],
            "evidence": _evidence(files, x.get("evidence"), where, report)}


def verify_draft(files, doc):
    if not isinstance(doc, dict):
        raise BadRequest("the answer must be an object with hypotheses, experiments and questions")
    report, hyps, exps, qs = [], [], [], []
    for i, h in enumerate((doc.get("hypotheses") if isinstance(doc.get("hypotheses"), list) else [])[:MAX_LIST]):
        where = "hypothesis %s" % (h.get("id") if isinstance(h, dict) else i + 1)
        try:
            v = verify_hypothesis(files, h, where, report)
            if any(x["id"] == v["id"] for x in hyps):
                raise BadRequest("the id %r is used twice" % v["id"])
            hyps.append(v)
        except BadRequest as e:
            report.append({"level": "dropped", "where": where, "why": str(e)})
    for i, x in enumerate((doc.get("experiments") if isinstance(doc.get("experiments"), list) else [])[:MAX_LIST]):
        where = "experiment %s" % (x.get("id") if isinstance(x, dict) else i + 1)
        try:
            v = verify_experiment(files, x, where, report)
            if any(y["id"] == v["id"] for y in exps):
                raise BadRequest("the id %r is used twice" % v["id"])
            exps.append(v)
        except BadRequest as e:
            report.append({"level": "dropped", "where": where, "why": str(e)})
    for i, q in enumerate((doc.get("questions") if isinstance(doc.get("questions"), list) else [])[:20]):
        try:
            qs.append({"text": _text((q or {}).get("text") if isinstance(q, dict) else q, 300, "question"),
                       "evidence": _evidence(files, (q or {}).get("evidence") if isinstance(q, dict) else None, "question %d" % (i + 1), report)})
        except BadRequest as e:
            report.append({"level": "dropped", "where": "question %d" % (i + 1), "why": str(e)})
    ids = {h["id"] for h in hyps}
    for x in exps:
        bad = [t for t in x["tests_claims"] if t not in ids]
        if bad:
            report.append({"level": "warning", "where": "experiment %s" % x["id"], "why": "tests %s, which is not a hypothesis here" % ", ".join(bad)})
        x["tests_claims"] = [t for t in x["tests_claims"] if t in ids]
    xids = {x["id"] for x in exps}
    for h in hyps:
        h["tested_by"] = [t for t in h["tested_by"] if t in xids] or [x["id"] for x in exps if h["id"] in x["tests_claims"]]
    if not hyps:
        raise BadRequest("no hypothesis survived checking")
    return {"hypotheses": hyps, "experiments": exps, "questions": qs}, report


def verify_change_set(files, doc, d, extra=None):
    """A proposal: {understood, operations: [{op, target, field, before, after, reason, from: {path, quote}}], not_in_protocol}."""
    if not isinstance(doc, dict):
        raise BadRequest("the change set must be an object")
    report, ops = [], []
    live = {h["id"]: h for h in d["hypotheses"] if not h.get("archived")}
    known = set(live) | {"problem"} | {x["id"] for x in d["experiments"]}
    for i, o in enumerate((doc.get("operations") if isinstance(doc.get("operations"), list) else [])[:20]):
        where = "operation %d" % (i + 1)
        try:
            if not isinstance(o, dict) or o.get("op") not in OPS:
                raise BadRequest("op must be one of %s" % ", ".join(OPS))
            op = {"op": o["op"], "reason": _text(o.get("reason"), 300, "reason", False) or ""}
            fr = o.get("from") if isinstance(o.get("from"), dict) else None
            op["from"] = check_quote(files, fr, extra) if fr else None
            if fr and not op["from"]:
                report.append({"level": "warning", "where": where, "why": "its 'from' quote is not in %s" % fr.get("path", "?")})
            if o["op"] == "add":
                h = verify_hypothesis(files, o.get("after"), where, report, extra=extra, need_evidence=False)
                if h["id"] in live:
                    raise BadRequest("%s already exists; use revise" % h["id"])
                op["after"] = h
            elif o["op"] == "merge":
                ts = [t for t in (o.get("targets") if isinstance(o.get("targets"), list) else []) if t in live]
                if len(ts) < 2:
                    raise BadRequest("merge needs two or more existing hypotheses in 'targets'")
                h = verify_hypothesis(files, o.get("after"), where, report, extra=extra, need_evidence=False)
                op.update(targets=ts, after=h)
            else:
                t = o.get("target")
                if t not in known:
                    raise BadRequest("unknown target %r" % t)
                op["target"] = t
                if o["op"] == "revise":
                    if t == "problem":
                        if o.get("field") not in PROBLEM_FIELDS:
                            raise BadRequest("a problem revision names a field: %s" % ", ".join(PROBLEM_FIELDS))
                    elif o.get("field") not in REVISABLE:
                        raise BadRequest("field must be one of %s" % ", ".join(REVISABLE))
                    op["field"] = o["field"]
                    after = o.get("after")
                    if op["field"] == "tested_by":
                        after = [a for a in (after if isinstance(after, list) else []) if isinstance(a, str)][:8]
                    elif op["field"] == "tier" and after not in TIERS or op["field"] == "stance" and after not in STANCES:
                        raise BadRequest("%s must be one of %s" % (op["field"], ", ".join(TIERS if op["field"] == "tier" else STANCES)))
                    else:
                        after = _text(after, 600, "after")
                    op["after"] = after
                    op["before"] = _current(d, t, op["field"])
                elif o["op"] == "relink":
                    op["after"] = [a for a in (o.get("after") if isinstance(o.get("after"), list) else []) if isinstance(a, str)][:8]
                    op["before"] = (live.get(t) or {}).get("tested_by")
            ops.append(op)
        except BadRequest as e:
            report.append({"level": "dropped", "where": where, "why": str(e)})
    if not ops:
        raise BadRequest("no operation survived checking")
    nip = [i for i in (doc.get("not_in_protocol") if isinstance(doc.get("not_in_protocol"), list) else []) if isinstance(i, int) and 0 <= i < len(ops)]
    return {"understood": _text(doc.get("understood"), 300, "understood", False) or "", "operations": ops, "not_in_protocol": nip}, report


def _current(d, target, field):
    if target == "problem":
        p = (d["problem"].get("confirmed") or d["problem"].get("proposed") or {}).get(field) or {}
        return p.get("text")
    h = next((h for h in d["hypotheses"] if h["id"] == target), None)
    if h is None:
        return None
    if field == "criterion_text":
        return h["criterion"].get("text")
    return h.get(field)


# ------------------------------------------------------------------ store
def load(hub):
    d = hub.read_json("hypothesis.json", None)
    if not isinstance(d, dict) or not str(d.get("schema", "")).startswith("lemmata.hypothesis/1"):
        d = {}
    d["schema"] = SCHEMA
    d.setdefault("enabled", None)          # None: decided by detect(); True / False: the researcher's choice
    d.setdefault("problem", {"proposed": None, "confirmed": None, "validity": "unreviewed", "report": []})
    for k in ("hypotheses", "experiments", "questions", "change_sets", "jobs", "inputs", "log", "own_deviations", "report"):
        d.setdefault(k, [])
    return d


def log(d, what, target=None, note=None, by="you", proposal=None):
    d["log"].append({"t": now_iso(), "what": what, "target": target, "note": (note or "")[:300], "by": by, **({"proposal": proposal} if proposal else {})})
    del d["log"][:-500]


def new_job(d, typ, trigger, target=None, note=None, ref=None):
    """Queue a job for the researcher's LLM. One open job per (type, target): a newer trigger replaces the note."""
    if typ not in JOB_TYPES:
        raise BadRequest("unknown job type")
    for j in d["jobs"]:
        if j["status"] == "open" and j["type"] == typ and j.get("target") == target:
            j.update(trigger=trigger, note=note or j.get("note"), ref=ref or j.get("ref"), updated=now_iso())
            return j
    n = 1 + max([int(j["id"].rsplit("-", 1)[1]) for j in d["jobs"] if re.match(r".*-\d+$", j["id"])] or [0])
    j = {"id": "job-%d" % n, "type": typ, "trigger": trigger, "target": target, "note": (note or "")[:1200] or None, "ref": ref,
         "status": "open", "created": now_iso()}
    d["jobs"].append(j)
    del d["jobs"][:-200]
    return j


def _hyp(d, hid, live=True):
    h = next((h for h in d["hypotheses"] if h["id"] == hid), None)
    if h is None or (live and h.get("archived")):
        raise NotFound("unknown hypothesis %r" % hid)
    return h


def _fresh(h, by):
    h = dict(h)
    h.update(validity="unreviewed", confirmed=False, archived=None, aliases=h.get("aliases") or [], by=by, at=now_iso(),
             stage_set=None, prediction=h.get("prediction") or [])
    return h


def apply_draft(d, draft, report, by):
    """A draft replaces the hypotheses nobody has confirmed yet; confirmed ones stay (a draft with the same id is ignored)."""
    keep = [h for h in d["hypotheses"] if h.get("confirmed") or h.get("archived")]
    ids = {h["id"] for h in keep}
    d["hypotheses"] = keep + [_fresh(h, by) for h in draft["hypotheses"] if h["id"] not in ids]
    d["experiments"] = draft["experiments"] or d["experiments"]
    d["questions"] = draft["questions"] or d["questions"]
    d["report"] = report


def submit(files, d, job_id, result, by="agent"):
    j = next((j for j in d["jobs"] if j["id"] == job_id), None)
    if j is None:
        raise NotFound("unknown job %r" % job_id)
    if j["status"] != "open":
        raise BadRequest("job %s is %s, not open" % (job_id, j["status"]))
    extra = _input_texts(d)
    if j["type"] == "understand_problem":
        p, report = verify_problem(files, result.get("problem") if isinstance(result, dict) and "problem" in result else result)
        d["problem"].update(proposed=p, report=report, proposed_at=now_iso(), proposed_by=by[:60], validity="unreviewed")
        log(d, "problem proposed", "problem", by=by)
    elif j["type"] == "draft_hypotheses":
        draft, report = verify_draft(files, result)
        apply_draft(d, draft, report, by)
        log(d, "hypotheses drafted", None, "%d hypotheses, %d experiments" % (len(draft["hypotheses"]), len(draft["experiments"])), by=by)
    elif j["type"] in ("revise", "combine", "comprehend_input"):
        cs, report = verify_change_set(files, result, d, extra)
        n = 1 + max([int(c["id"].split("-")[1]) for c in d["change_sets"]] or [0])
        cs.update(id="cs-%d" % n, job=j["id"], trigger={"kind": j["type"], "ref": j.get("ref") or j.get("target")}, state="open",
                  created=now_iso(), by=by[:60], report=report)
        d["change_sets"].append(cs)
        del d["change_sets"][:-100]
        log(d, "change proposed", j.get("target"), cs["understood"], by=by)
    elif j["type"] == "premise_check":
        h = _hyp(d, j["target"])
        r = result if isinstance(result, dict) else {}
        verdict = r.get("states_it_as") if r.get("states_it_as") in ("finding", "assumption", "hypothesis", "not_stated") else None
        if verdict is None:
            raise BadRequest("states_it_as must be finding, assumption, hypothesis or not_stated")
        h["source"] = dict(h.get("source") or {}, cite=_text(r.get("cite"), 200, "cite", False) or (h.get("source") or {}).get("cite"),
                           url=_text(r.get("url"), 300, "url", False), quote=_text(r.get("quote"), 300, "quote", False),
                           locator=_text(r.get("locator"), 80, "locator", False), states_it_as=verdict,
                           quote_check="unverified", retrieved_at=_text(r.get("retrieved_at"), 40, "retrieved_at", False) or now_iso()[:10])
        log(d, "premise checked", h["id"], verdict, by=by)
        report = []
    else:
        raise BadRequest("this job type cannot be submitted")
    j.update(status="done", done=now_iso(), by=by[:60], dropped=len([r for r in report if r["level"] == "dropped"]))
    return j, report


def _input_texts(d):
    return {".lemmata/inputs/%s.md" % i["id"]: i["text"] for i in d["inputs"]}


# ------------------------------------------------------------------ the researcher's actions
def act(d, action, target=None, text=None, note=None, targets=None, fields=None, stage=None, prediction=None):
    """Confirm · Fix · Delete · Restore · Combine · Tell · stage · predict. Returns a short message. Never calls a model;
    where a model is needed it queues a job for the researcher's own LLM."""
    if action == "enable":
        d["enabled"] = bool(target != "off")
        log(d, "hypothesis-first %s" % ("on" if d["enabled"] else "off"))
        return "Hypothesis-first mode is %s." % ("on" if d["enabled"] else "off")
    if action == "tell":
        t = _text(text, 4000, "text")
        n = 1 + len(d["inputs"])
        iid = "%s-%d" % (now_iso()[:10], n)
        d["inputs"].append({"id": iid, "text": t, "at": now_iso()})
        new_job(d, "comprehend_input", "new input", target=None, note=t, ref=".lemmata/inputs/%s.md" % iid)
        log(d, "input", None, t[:200])
        return "Saved. Your LLM will read it and propose what to change; nothing changes until you accept."
    if action == "combine":
        ts = [t for t in (targets or []) if isinstance(t, str)]
        for t in ts:
            _hyp(d, t)
        if len(ts) < 2:
            raise BadRequest("select two or more hypotheses to combine")
        new_job(d, "combine", "combine " + " + ".join(ts), target=",".join(ts), note=_text(note, 600, "note", False))
        log(d, "combine asked", ",".join(ts), note)
        return "Your LLM will draft one combined hypothesis; you review it before anything changes."
    if target == "problem":
        p = d["problem"]
        if action == "confirm":
            if not (p.get("proposed") or p.get("confirmed")):
                raise NotFound("there is no problem statement to confirm")
            p.update(confirmed=p.get("proposed") or p["confirmed"], proposed=None, validity="valid", confirmed_at=now_iso())
            log(d, "problem confirmed", "problem")
            if not any(h.get("confirmed") for h in d["hypotheses"]) and not any(not h.get("archived") for h in d["hypotheses"]):
                new_job(d, "draft_hypotheses", "problem confirmed")
            return "Confirmed. Your LLM can now draft the hypotheses under it."
        if action == "fix":
            cur = dict(p.get("proposed") or p.get("confirmed") or {k: {"text": None, "evidence": []} for k in PROBLEM_FIELDS})
            changed = []
            for k, v in (fields or {}).items():
                if k in PROBLEM_FIELDS and isinstance(v, str):
                    cur[k] = dict(cur.get(k) or {}, text=_text(v, 600, k, False), edited=True)
                    changed.append(k)
            p.update(proposed=cur, validity="not_valid" if note and not changed else "unreviewed")
            if p.get("confirmed") and (changed or note):
                p["confirmed"] = None
            for h in d["hypotheses"]:
                if not h.get("archived"):
                    h["stale"] = "the problem was changed"
            new_job(d, "revise", "problem fixed", target="problem", note=_text(note, 1200, "note", False) or "edited: " + ", ".join(changed))
            log(d, "problem fixed", "problem", note or ", ".join(changed))
            return "Saved. Every hypothesis under it is marked stale; your LLM will propose what else must change."
        if action == "not_valid":
            p["validity"] = "not_valid"
            new_job(d, "understand_problem", "marked not valid", note=_text(note, 1200, "note", False))
            log(d, "problem not valid", "problem", note)
            return "Marked not valid. Fix it here, or say what is wrong and your LLM will try again."
        if action == "delete":
            if not (text or "").strip():
                raise BadRequest("deleting the problem needs a new input that says what the problem is")
            p.update(proposed=None, confirmed=None, validity="unreviewed")
            act(d, "tell", text=text)
            new_job(d, "understand_problem", "problem deleted", note=text)
            log(d, "problem deleted", "problem", text)
            return "Deleted. Your LLM will state the problem again from your input."
        raise BadRequest("unknown action for the problem")
    h = _hyp(d, target, live=action != "restore")
    if action == "confirm":
        h.update(validity="valid", confirmed=True, confirmed_at=now_iso(), stale=None)
        log(d, "confirmed", h["id"])
        return "Confirmed %s." % h["id"]
    if action == "fix":
        changed = []
        if isinstance(text, str) and text.strip() and text.strip() != h["statement"]:
            changed.append(("statement", h["statement"], _text(text, 600, "statement")))
            h["statement"] = changed[-1][2]
        for k, v in (fields or {}).items():
            if k == "answers" and isinstance(v, str):
                changed.append((k, h.get("answers"), _text(v, 300, k, False)))
                h["answers"] = changed[-1][2]
            elif k == "criterion_text" and isinstance(v, str):
                changed.append((k, h["criterion"].get("text"), _text(v, 400, k, False)))
                h["criterion"]["text"] = changed[-1][2]
        if h["criterion"].get("frozen") and changed:
            own_deviation(d, h, "; ".join("%s changed" % c[0] for c in changed), touches_test=any(c[0] == "criterion_text" for c in changed))
        h.update(validity="unreviewed" if not changed else h["validity"], stale=None)
        new_job(d, "revise", "fixed " + h["id"], target=h["id"],
                note="\n".join(["%s: %r -> %r" % c for c in changed] + ([note] if note else [])) or None)
        log(d, "fixed", h["id"], note or "; ".join(c[0] for c in changed))
        return "Saved. Your LLM will propose what else must change (criterion, links, other hypotheses)."
    if action == "delete":
        h["archived"] = {"reason": "deleted", "at": now_iso(), "note": _text(note, 300, "note", False)}
        log(d, "deleted", h["id"], note)
        return "Deleted %s. It is archived; restore it from the Trail." % h["id"]
    if action == "restore":
        if not h.get("archived"):
            raise BadRequest("%s is not archived" % h["id"])
        if h["archived"].get("reason") == "merged":
            m = next((x for x in d["hypotheses"] if x["id"] == h["archived"].get("merged_into") and not x.get("archived")), None)
            if m:
                raise BadRequest("%s was merged into %s; delete or split %s first" % (h["id"], m["id"], m["id"]))
        h["archived"] = None
        log(d, "restored", h["id"])
        return "Restored %s." % h["id"]
    if action == "stage":
        if stage not in (None, "auto", "hypothesis", "testing", "finding", "refuted", "exploration"):
            raise BadRequest("stage must be hypothesis, testing, finding, refuted, exploration or auto")
        h["stage_set"] = None if stage in (None, "auto") else {"stage": stage, "note": _text(note, 300, "note", False), "at": now_iso()}
        log(d, "stage set", h["id"], stage)
        return "Stage of %s set." % h["id"]
    if action == "predict":
        if prediction not in ("supported", "not_supported", "mixed"):
            raise BadRequest("prediction must be supported, not_supported or mixed")
        h.setdefault("prediction", []).append({"outcome": prediction, "note": _text(note, 300, "note", False), "at": now_iso()})
        log(d, "prediction", h["id"], prediction)
        return "Prediction recorded. Earlier predictions are kept."
    if action == "premise":
        if h["stance"] != "tested":
            raise BadRequest("only a claim of someone else (stance tested) has a premise to check")
        new_job(d, "premise_check", "check premise", target=h["id"])
        return "Your LLM will look up where the source says it."
    raise BadRequest("unknown action %r" % action)


def own_deviation(d, h, what, touches_test=False):
    n = 1 + len(d["own_deviations"])
    dev = {"id": "L%d" % n, "title": what[:200], "date": now_iso()[:10], "affects": [h["id"]], "by": "Lemmata", "test_changed": bool(touches_test)}
    d["own_deviations"].append(dev)
    if touches_test and h["tier"] == "confirmatory":
        h["tier_was"], h["tier"] = h["tier"], "exploratory"
    log(d, "deviation", h["id"], what)
    return dev


def accept(d, cs_id, which=None):
    """Apply all (which None) or some (indexes) of a change set's operations."""
    cs = next((c for c in d["change_sets"] if c["id"] == cs_id), None)
    if cs is None:
        raise NotFound("unknown change set %r" % cs_id)
    if cs["state"] != "open":
        raise BadRequest("this change set is already %s" % cs["state"])
    idx = list(range(len(cs["operations"]))) if which is None else [i for i in which if isinstance(i, int) and 0 <= i < len(cs["operations"])]
    if not idx:
        raise BadRequest("choose at least one change")
    done = []
    for i in idx:
        done.append(_apply(d, cs["operations"][i], cs))
    cs.update(state="accepted" if len(idx) == len(cs["operations"]) else "partly accepted", accepted=idx, decided=now_iso())
    log(d, "change accepted", None, "; ".join(done), proposal=cs["id"])
    proposals = [cs["operations"][i] for i in idx if i in cs.get("not_in_protocol", [])]
    return done, proposals


def reject(d, cs_id):
    cs = next((c for c in d["change_sets"] if c["id"] == cs_id), None)
    if cs is None:
        raise NotFound("unknown change set %r" % cs_id)
    cs.update(state="rejected", decided=now_iso())
    log(d, "change rejected", None, cs.get("understood"), proposal=cs["id"])
    return "Rejected. Nothing changed."


def _apply(d, op, cs):
    if op["op"] == "add":
        h = _fresh(op["after"], cs.get("by") or "agent")
        if any(x["id"] == h["id"] and not x.get("archived") for x in d["hypotheses"]):
            raise BadRequest("%s already exists" % h["id"])
        if cs["trigger"]["kind"] == "comprehend_input" and h["criterion"].get("rule") is None and _has_results(d, h):
            h["tier"] = "exploratory"
        h["origin_input"] = cs["trigger"].get("ref")
        d["hypotheses"].append(h)
        return "added %s" % h["id"]
    if op["op"] == "merge":
        origs = [_hyp(d, t) for t in op["targets"]]
        h = _fresh(op["after"], cs.get("by") or "agent")
        h["aliases"] = sorted(set(op["targets"]) | {a for o in origs for a in o.get("aliases") or []})
        h["sub_rules"] = [o["criterion"]["rule"] for o in origs if o["criterion"].get("rule")]
        h["tested_by"] = list(dict.fromkeys(h["tested_by"] + [t for o in origs for t in o["tested_by"]]))
        same = all(o["tier"] == "confirmatory" for o in origs) and h["criterion"].get("rule") is None
        h["tier"] = "confirmatory" if same else "exploratory"
        h["criterion"]["frozen"] = origs[0]["criterion"].get("frozen") if same else None
        for o in origs:
            o["archived"] = {"reason": "merged", "merged_into": h["id"], "at": now_iso()}
            if o["criterion"].get("frozen"):
                own_deviation(d, o, "merged into %s" % h["id"])
        d["hypotheses"].append(h)
        return "merged %s into %s" % (", ".join(op["targets"]), h["id"])
    if op["op"] == "archive":
        if op["target"] == "problem":
            raise BadRequest("the problem cannot be archived by a proposal")
        _hyp(d, op["target"])["archived"] = {"reason": "deleted", "at": now_iso(), "note": op.get("reason")}
        return "archived %s" % op["target"]
    if op["op"] == "relink":
        _hyp(d, op["target"])["tested_by"] = op["after"]
        return "relinked %s" % op["target"]
    if op["op"] == "revise":
        if op["target"] == "problem":
            p = d["problem"]
            cur = p.get("confirmed") or p.get("proposed")
            if not cur:
                raise BadRequest("there is no problem statement to revise")
            cur[op["field"]] = dict(cur.get(op["field"]) or {}, text=op["after"], edited=True)
            p["validity"] = "unreviewed"
            return "revised the problem's %s" % op["field"]
        h = _hyp(d, op["target"])
        if op["field"] == "criterion_text":
            h["criterion"]["text"] = op["after"]
            if h["criterion"].get("frozen"):
                own_deviation(d, h, "criterion changed by a proposal", touches_test=True)
        else:
            h[op["field"]] = op["after"]
            if h["criterion"].get("frozen") and op["field"] in ("statement", "tier"):
                own_deviation(d, h, "%s changed by a proposal" % op["field"])
        h["validity"], h["stale"] = "unreviewed", None
        return "revised %s %s" % (h["id"], op["field"])
    raise BadRequest("unknown operation")


def _has_results(d, h):
    return bool(h.get("tested_by"))


# ------------------------------------------------------------------ assess (no model)
def deviations(files, src, d, first_data):
    """The deviation log, one record per '## Dn.' heading, with the hypotheses it names and whether it came after their data."""
    live = {h["id"] for h in d["hypotheses"]} | {a for h in d["hypotheses"] for a in h.get("aliases") or []}
    out = []
    for path in src.get("deviations") or []:
        lines = files.lines(path) or []
        cur = None
        for i, ln in enumerate(lines):
            m = DEV_HEAD_RE.match(ln)
            if m:
                cur = {"id": m.group(1), "title": m.group(2)[:200], "path": path, "line": i + 1, "body": [], "date": None}
                dm = DATE_RE.search(ln)
                cur["date"] = dm.group(1) if dm else None
                out.append(cur)
            elif cur is not None:
                if ln.startswith("## "):
                    cur = None
                    continue
                cur["body"].append(ln)
                if cur["date"] is None and len(cur["body"]) <= 6:
                    dm = DATE_RE.search(ln)
                    cur["date"] = dm.group(1) if dm else None
    for dv in out:
        body = "\n".join(dv.pop("body"))
        dv["end_line"] = dv["line"] + body.count("\n") + 1
        named = {m for m in HYP_REF_RE.findall(dv["title"] + "\n" + body) if m in live}
        cites = re.compile(r"\b%s\b" % re.escape(dv["id"]))      # a hypothesis that names this deviation (e.g. "decided after seeing the data, D11")
        named |= {h["id"] for h in d["hypotheses"] if cites.search(" ".join(str(x or "") for x in (h.get("statement"), h.get("answers"), h["criterion"].get("text"))))}
        dv["affects"] = sorted(named)
        dv["timing"] = {}
        for hid in dv["affects"]:
            fd = first_data.get(hid)
            dv["timing"][hid] = None if not (fd and dv["date"]) else "after_data" if dv["date"] >= fd else "before_data"
        dv["after_data"] = any(v == "after_data" for v in dv["timing"].values())
    for dv in d.get("own_deviations") or []:
        out.append(dict(dv, path=None, line=None, timing={h: "after_data" for h in dv["affects"]}, after_data=True))
    return out


def first_data_dates(hist, d):
    """hypothesis id -> the day the first result behind it was committed (YYYY-MM-DD), from the commit history."""
    exps = {x["id"]: x for x in d["experiments"]}
    first = {}
    commits = sorted((c for cs in hist.values() for c in cs or []), key=lambda c: c.get("time") or "")
    for h in d["hypotheses"]:
        paths = [p for t in h.get("tested_by") or [] for p in (exps.get(t) or {}).get("deliverables", [])]
        if h["criterion"].get("rule"):
            paths.append(h["criterion"]["rule"]["file"])
        for c in commits:
            if any(f["path"] == p or f["path"].startswith(p.rstrip("/") + "/") for f in c.get("files", []) for p in paths):
                first[h["id"]] = (c.get("time") or "")[:10]
                break
    return first


def frozen_shas(hist, h):
    """The commit where the frozen design file first appeared."""
    fz = h["criterion"].get("frozen")
    if not fz:
        return None
    for c in sorted((c for cs in hist.values() for c in cs or []), key=lambda c: c.get("time") or ""):
        if any(f["path"] == fz["file"] for f in c.get("files", [])):
            return {"sha": (c.get("rev") or "")[:7], "day": (c.get("time") or "")[:10]}
    return None


def experiment_status(files, x):
    if not x["deliverables"]:
        return "planned"
    have = [files.exists_prefix(p) for p in x["deliverables"]]
    return "done" if all(have) else "running" if any(have) else "planned"


def stage(files, d, h, exps_status):
    """-> (stage, rule id, why, result). R0 set by you · R1 finding · R2 not supported · R3 tested, no verdict · R4 not run · R5 exploratory."""
    if h.get("stage_set"):
        return h["stage_set"]["stage"], "R0", "set by you" + (": " + h["stage_set"]["note"] if h["stage_set"].get("note") else ""), None
    if h["tier"] == "exploratory":
        res = evaluate(files, h["criterion"]["rule"]) if h["criterion"].get("rule") else None
        return "exploration", "R5", "exploratory: decided after seeing data, or no frozen test", res
    rules = [h["criterion"]["rule"]] if h["criterion"].get("rule") else []
    rules += h.get("sub_rules") or []
    ran = any(exps_status.get(t) in ("done", "running") for t in h.get("tested_by") or [])
    if not rules:
        return ("testing" if ran else "hypothesis"), "R4", "no rule yet" + ("; its experiments have results" if ran else ""), None
    res = [evaluate(files, r) for r in rules]
    joined = {"met": None if any(r["met"] is None for r in res) else all(r["met"] for r in res),
              "values": {k: v for r in res for k, v in r["values"].items()}, "why": " · ".join(r["why"] for r in res), "file": res[0]["file"],
              "parts": res if len(res) > 1 else None}
    if joined["met"] is None:
        return ("testing" if ran else "hypothesis"), "R4", joined["why"], joined
    if h["tier"] == "secondary":
        return "testing", "R3", "secondary: numbers shown, no verdict", joined
    if not h["criterion"].get("frozen"):
        return "testing", "R3", "the test was not frozen before the data, so it cannot make a finding", joined
    return ("finding", "R1", joined["why"], joined) if joined["met"] else ("refuted", "R2", joined["why"], joined)


def view(files, src, d, hist, has_paper):
    """The whole hypothesis-first document for the page, the MCP tools and the claims."""
    mode = d["enabled"] if d["enabled"] is not None else wanted(src, has_paper)
    xs = {x["id"]: experiment_status(files, x) for x in d["experiments"]}
    first = first_data_dates(hist, d)
    devs = deviations(files, src, d, first)
    hyps = []
    for h in d["hypotheses"]:
        st, rule, why, res = stage(files, d, h, xs)
        dv = [x for x in devs if h["id"] in x["affects"] or any(a in x["affects"] for a in h.get("aliases") or [])]
        hyps.append(dict(h, stage=st, stage_rule=rule, stage_why=why, result=res, frozen_at=frozen_shas(hist, h),
                         deviations={"before": sum(1 for x in dv if x["timing"].get(h["id"]) == "before_data"),
                                     "after": sum(1 for x in dv if x["timing"].get(h["id"]) == "after_data"),
                                     "ids": [x["id"] for x in dv]},
                         first_data=first.get(h["id"])))
    order = {t: i for i, t in enumerate(TIERS)}
    hyps.sort(key=lambda h: (bool(h.get("archived")), order.get(h["tier"], 9)))
    live = [h for h in hyps if not h.get("archived")]
    open_jobs = [j for j in d["jobs"] if j["status"] == "open"]
    return {"schema": SCHEMA, "mode": "hypothesis_first" if mode else "paper", "enabled": d["enabled"], "sources": src,
            "problem": d["problem"], "hypotheses": hyps, "experiments": [dict(x, status=xs[x["id"]]) for x in d["experiments"]],
            "questions": d["questions"], "deviations": devs, "report": d["report"],
            "change_sets": [c for c in d["change_sets"] if c["state"] == "open"],
            "jobs": open_jobs, "inputs": d["inputs"][-20:], "log": d["log"][-80:],
            "counts": {"stages": {s: sum(h["stage"] == s for h in live) for s in ("hypothesis", "testing", "finding", "refuted", "exploration")},
                       "live": len(live), "unreviewed": sum(h["validity"] == "unreviewed" for h in live) + (d["problem"]["validity"] == "unreviewed" and bool(d["problem"].get("proposed"))),
                       "jobs": len(open_jobs), "change_sets": sum(c["state"] == "open" for c in d["change_sets"]),
                       "deviations_after": sum(1 for x in devs if x["after_data"])}}


def ensure_jobs(d, mode):
    """In hypothesis-first mode the first job is to state the problem."""
    if mode and not d["problem"].get("proposed") and not d["problem"].get("confirmed") and not any(j["type"] == "understand_problem" and j["status"] == "open" for j in d["jobs"]):
        new_job(d, "understand_problem", "project added")
        return True
    return False


# ------------------------------------------------------------------ what the LLM is told
GUIDES = {
    "understand_problem": """State the problem this research is trying to solve, from the sources only.
Read the hypothesis sources, the report, the README and the notes listed below (open the files themselves).
Return {"problem": {"gap": F, "why_it_matters": F, "approach": F, "if_solved": F}} where each F is
{"text": "<one or two plain sentences>", "evidence": [{"path": "<file>", "line": <n>, "quote": "<a few words copied from that line>"}]}.
- Write what the sources say, in plain words. Do not add what they do not say.
- When the sources do not say it, give {"text": "", "note": "the sources do not say"} for that field.
- Every quote must really be in that file; Lemmata drops evidence it cannot find.""",
    "draft_hypotheses": """Draft the hypotheses under the confirmed problem (below), from the sources.
Return {"hypotheses": [H...], "experiments": [X...], "questions": [{"text": "...", "evidence": [...]}]}.
H = {"id": "H1", "statement": "<the hypothesis as the protocol states it>", "answers": "<which part of the problem it addresses, one sentence>",
     "stance": "held" (the author's own) | "tested" (someone else's claim under test, then add "source": {"cite": "..."}),
     "tier": "confirmatory" (listed as primary / pre-registered) | "secondary" (listed as secondary) | "exploratory" (decided after seeing data),
     "criterion": {"text": "<the test as the protocol states it>", "frozen": {"file": "<the design file that froze it>"},
                   "rule": {"file": "<the project's own test table, e.g. results/analysis/tests.csv>", "select": {"<column>": "<value naming this test's row>"},
                            "conditions": [{"column": "<column>", "op": "<", "value": 0.05}], "report": ["<columns to show>"]}},
     "tested_by": ["<experiment ids>"], "evidence": [{"path": "...", "line": n, "quote": "..."}]}
X = {"id": "stepA", "title": "...", "deliverables": ["<result files or folders it writes>"], "acceptance": "...", "depends_on": [], "tests_claims": ["H1"], "evidence": [...]}
- Do NOT report results; Lemmata reads them from the test table with your rule.
- The rule must match exactly one row of the table; its conditions must be the protocol's own decision rule (e.g. corrected p below alpha, effect in the stated direction).
- Leave "rule" out when the project has no table for that hypothesis.""",
    "revise": """The researcher fixed something (below). Propose what else must change so the project stays consistent.
Return a change set: {"understood": "<one line: what you understood>", "operations": [OP...], "not_in_protocol": [<indexes of operations the protocol does not say>]}.
OP = {"op": "revise", "target": "<H id or problem>", "field": "statement|answers|tier|stance|criterion_text|tested_by" (problem: gap|why_it_matters|approach|if_solved), "after": "...", "reason": "<one sentence>"}
   | {"op": "relink", "target": "<H id>", "after": ["<experiment ids>"], "reason": "..."}
   | {"op": "archive", "target": "<H id>", "reason": "..."}
   | {"op": "add", "after": H, "reason": "..."} | {"op": "merge", "targets": ["H2", "H3"], "after": H, "reason": "..."}
- Propose only what follows from the fix. Do not change a frozen test unless the fix says so; Lemmata records any such change as a deviation.
- An empty change is fine: {"understood": "...", "operations": []} is refused, so then explain in "understood" and propose one revise of "answers".""",
    "combine": """The researcher wants to combine the hypotheses named below into one.
Return a change set with one operation: {"op": "merge", "targets": [<their ids>], "after": H, "reason": "..."} (H as in draft_hypotheses).
- The merged statement must keep what each original claims. Keep each original test as a sub-condition: Lemmata carries their rules over.
- Give the merged hypothesis a new id (e.g. "H23").""",
    "comprehend_input": """The researcher told Lemmata something (below, saved at the path given as 'ref'). Work out what it changes.
Return a change set as in 'revise'. Every operation must quote the sentence of the input it comes from:
"from": {"path": "<ref>", "quote": "<words copied from the input>"}.
- Start with "understood": one line restating what you understood, so the researcher can spot a misunderstanding.
- A new hypothesis from the input has no test yet; if results bearing on it already exist, say so in its reason.
- List under not_in_protocol the operations that say something the protocol does not.""",
    "premise_check": """The hypothesis below is someone else's claim under test. Find where the cited source says it.
Return {"cite": "...", "url": "<a link to the source>", "quote": "<the source's own words, under 25 words>", "locator": "<section or page>",
"states_it_as": "finding" | "assumption" | "hypothesis" | "not_stated", "retrieved_at": "<YYYY-MM-DD>"}.
- If the source does not say it, return states_it_as "not_stated" with what it does say.""",
}


def job_doc(d, j, src, project_name=""):
    """Everything an LLM needs to do one job, as data, and as one markdown file it can be handed."""
    ctx = {"sources": src}
    if j["type"] != "understand_problem":
        ctx["problem"] = d["problem"].get("confirmed") or d["problem"].get("proposed")
        ctx["hypotheses"] = [{k: h.get(k) for k in ("id", "statement", "answers", "stance", "tier", "criterion", "tested_by", "aliases", "validity")}
                             for h in d["hypotheses"] if not h.get("archived")]
        ctx["experiments"] = d["experiments"]
    if j["type"] == "premise_check":
        h = _hyp(d, j["target"])
        ctx["hypothesis"] = {"id": h["id"], "statement": h["statement"], "source": h.get("source")}
    out = {"id": j["id"], "type": j["type"], "trigger": j["trigger"], "target": j.get("target"), "note": j.get("note"), "ref": j.get("ref"),
           "instructions": GUIDES[j["type"]], "context": ctx,
           "submit": "Call the Lemmata MCP tool submit_hypothesis_job with project, job=%s and result=<your JSON>, or paste the JSON into Lemmata." % j["id"]}
    md = ["# Lemmata job %s: %s" % (j["id"], j["type"].replace("_", " ")), "", "Project: %s. Trigger: %s." % (project_name, j["trigger"]), ""]
    if j.get("note"):
        md += ["## What the researcher said", "", j["note"], ""]
    if j.get("ref"):
        md += ["Saved at: `%s`" % j["ref"], ""]
    md += ["## What to do", "", GUIDES[j["type"]], "", "## Context", "", "```json", json.dumps(ctx, ensure_ascii=False, indent=1), "```", "",
           "## How to hand it back", "", out["submit"]]
    out["markdown"] = "\n".join(md)
    return out
