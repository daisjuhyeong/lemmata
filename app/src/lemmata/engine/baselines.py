"""Baselines (S30): one row per method the work is compared with, and where to check each one.

The result files say which methods were run (Setup, S23). They do not say what each method is. For every baseline
Lemmata keeps a small card the researcher can open:

    paper       title, authors, year, venue, a link to the paper and a link to its PDF
    code        the repository to run it from
    intuition   the idea of the method in a sentence or two, where it falls short, how the work differs from it
    published   the numbers its paper reports, each with the dataset, the measure and the table it is printed in

and puts those published numbers beside what the project measured itself: the baseline's number in the researcher's own
runs, and the number of the work's own method, on the same dataset and measure. Lemmata states the difference and gives
no verdict on it: whether a gap is a protocol difference or a failed reproduction is the researcher's reading.

Two ways in, as for the project map (ADR-007). The researcher types or pastes a field and it counts at once. The
researcher's own agent proposes cards; rules check their shape, and nothing counts until the researcher confirms.
Nothing here opens a link or calls a model: a link is checked by the researcher clicking it.
"""
import re
import time
from urllib.parse import urlsplit

from .errors import BadRequest, NotFound
from .experiments import norm, num
from .setup import AVG

SCHEMA = "lemmata.baselines/1"
ROLES = ("base", "baseline", "compared")          # the Setup roles that are baselines (not ours, not an ablation variant)
TEXT = {"intuition": 600, "limit": 400, "differs": 400, "notes": 1000}
PAPER_TEXT = {"title": 300, "authors": 300, "venue": 80}
LINKS = ("url", "pdf")
MAX_ENTRIES, MAX_PUBLISHED, MAX_URL = 80, 60, 400
FORGES = ("github.com", "gitlab.com", "huggingface.co", "bitbucket.org", "codeberg.org", "sourceforge.net", "zenodo.org")
PDF_RE = re.compile(r"(\.pdf($|[?#]))|(/pdf(/|\?|$))", re.I)
ARXIV_ABS = re.compile(r"^https://(?:www\.)?arxiv\.org/abs/([A-Za-z\-./0-9]+?)(?:v\d+)?/?$")
AVG_WORDS = {"average", "avg", "mean", "overall", "all"}
PARTS = ("paper", "pdf", "code", "intuition", "published")          # what a complete card has

GUIDE = """How to fill in a project's baselines for Lemmata.

A baseline is a method the project compares with. For each one the researcher wants to open, in one place: the paper
that introduced it and its PDF, the code to run it, the idea behind it, and the numbers its paper reports on the
datasets this project uses. Read the primary sources yourself, then call propose_baselines with:

{"baselines": [
  {"name": "ADWIN",
   "paper": {"title": "Learning from Time-Changing Data with Adaptive Windowing", "authors": "Bifet, Gavalda",
             "year": 2007, "venue": "SDM", "url": "https://...", "pdf": "https://.../paper.pdf"},
   "code": "https://github.com/...",
   "intuition": "Keeps a window of recent items and cuts it whenever two sub-windows differ by more than a bound.",
   "limit": "Assumes a one-dimensional stream of bounded values.",
   "differs": "Ours reads the model's own uncertainty instead of the input's mean.",
   "published": [{"dataset": "Electricity", "metric": "fp", "value": 38.0, "where": "Table 2",
                  "url": "https://.../paper.pdf", "note": "error rate, prequential, 1,000-item window"}]}
]}

Rules Lemmata enforces (what fails is dropped and reported back):
- name is a baseline of this project (see the list in this brief) or a new one you say the project should compare with.
- Every link is https. paper.url is the paper's own page (publisher, proceedings, arXiv, OpenReview); paper.pdf opens
  the PDF; code is the authors' repository when one exists, otherwise leave it out. Never invent a link.
- intuition, limit and differs are your own words, one or two sentences each. No copied abstract.
- A published number is a number printed in the baseline's own paper (or in a paper you name in url), with the table
  or section in where. Use this project's dataset and measure names so Lemmata can put it beside the project's runs.
  Say in note when the protocol differs (another split, another window, another version of the dataset).
- Leave out what you could not find. An empty field is shown as missing; a wrong one misleads.

This is a proposal. Only the researcher confirms it, on the Baselines page.
"""


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def load(hub):
    d = hub.read_json("baselines.json", None)
    if not isinstance(d, dict) or not str(d.get("schema", "")).startswith("lemmata.baselines/"):
        d = {}
    d.setdefault("schema", SCHEMA)
    d.setdefault("entries", {})
    d.setdefault("proposed", None)
    d.setdefault("report", [])
    return d


# ------------------------------------------------------------------ one card, checked
def _text(v, n):
    if v is None:
        return None
    if not isinstance(v, str):
        raise BadRequest("must be text")
    v = " ".join(v.split())
    return v[:n] or None


def link(v):
    """An https link, or None. Raises BadRequest on anything else: Lemmata shows links as things to click."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if not isinstance(v, str):
        raise BadRequest("a link must be text")
    v = v.strip()
    if len(v) > MAX_URL or re.search(r"[\s\"'<>\\^`{|}\x00-\x1f]", v):
        raise BadRequest("not a usable link")
    u = urlsplit(v)
    if u.scheme != "https" or not u.hostname or "." not in u.hostname or u.username or u.password:
        raise BadRequest("a link must start with https:// and name a site")
    return v


def host(url):
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _year(v):
    if v in (None, ""):
        return None
    try:
        y = int(str(v).strip())
    except ValueError:
        raise BadRequest("year must be a number")
    if not 1900 <= y <= int(time.strftime("%Y")) + 1:
        raise BadRequest("year %d is out of range" % y)
    return y


def _published(v, strict, where, note):
    out = []
    if v is None:
        return out
    if not isinstance(v, list):
        raise BadRequest("published must be a list")
    for i, p in enumerate(v[:MAX_PUBLISHED]):
        w = "%s.published[%d]" % (where, i)
        if not isinstance(p, dict):
            note("dropped", w, "must be an object")
            continue
        try:
            ds, mt = _text(p.get("dataset"), 80), _text(p.get("metric"), 60)
            raw = p.get("value")
            parsed = num(raw if isinstance(raw, (int, float)) and not isinstance(raw, bool) else str(raw if raw is not None else ""))
            if not ds or not mt:
                raise BadRequest("dataset and metric are both needed")
            if parsed is None:
                raise BadRequest("value %r is not a number" % (raw,))
            wh, nt = _text(p.get("where"), 120), _text(p.get("note"), 240)
            if strict and not wh:
                raise BadRequest("say where the paper prints it (where: \"Table 2\")")
            rec = {"dataset": ds, "metric": mt, "value": parsed[0], "text": _text(str(raw), 40), "percent": bool(parsed[2]), "where": wh, "url": link(p.get("url")), "note": nt}
        except BadRequest as e:
            note("dropped", w, str(e))
            continue
        if not any((o["dataset"], o["metric"], o["value"], o["where"]) == (rec["dataset"], rec["metric"], rec["value"], rec["where"]) for o in out):
            out.append(rec)
    if len(v) > MAX_PUBLISHED:
        note("note", where + ".published", "only the first %d numbers were read" % MAX_PUBLISHED)
    return out


def clean(raw, where, note, strict=False):
    """One card from untrusted input -> the stored form. A bad field is dropped with a reason; the rest is kept."""
    if not isinstance(raw, dict):
        raise BadRequest("must be an object")
    name = _text(raw.get("name"), 80)
    if not name or not norm(name):
        raise BadRequest("name is missing")
    e = {"name": name, "paper": {}, "code": None, "published": []}

    def field(key, fn, target, label):
        try:
            v = fn()
        except BadRequest as err:
            note("dropped", "%s.%s" % (where, label), str(err))
            return
        if v is not None:
            target[key] = v

    p = raw.get("paper") if isinstance(raw.get("paper"), dict) else {}
    if raw.get("paper") is not None and not isinstance(raw.get("paper"), dict):
        note("dropped", where + ".paper", "must be an object with title, authors, year, venue, url, pdf")
    for k, n in PAPER_TEXT.items():
        field(k, lambda k=k, n=n: _text(p.get(k), n), e["paper"], "paper." + k)
    field("year", lambda: _year(p.get("year")), e["paper"], "paper.year")
    for k in LINKS:
        field(k, lambda k=k: link(p.get(k)), e["paper"], "paper." + k)
    field("code", lambda: link(raw.get("code")), e, "code")
    for k, n in TEXT.items():
        field(k, lambda k=k, n=n: _text(raw.get(k), n), e, k)
    try:
        e["published"] = _published(raw.get("published"), strict, where, note)
    except BadRequest as err:
        note("dropped", where + ".published", str(err))
    # an arXiv page has its PDF at a fixed address: fill it in, and say so
    m = ARXIV_ABS.match(e["paper"].get("url") or "")
    if m and not e["paper"].get("pdf"):
        e["paper"]["pdf"] = "https://arxiv.org/pdf/" + m.group(1)
        e["paper"]["pdf_derived"] = True
    if e["paper"].get("pdf") and not PDF_RE.search(e["paper"]["pdf"]):
        note("note", where + ".paper.pdf", "this link does not look like a PDF; check that it opens one")
    if e.get("code") and host(e["code"]) not in FORGES:
        note("note", where + ".code", "%s is not a code host Lemmata knows; check that it is the repository" % host(e["code"]))
    return e


def verify(doc, known, by):
    """A proposed list -> ({key: card}, report). known: {normalised name or alias: key of the row it belongs to}."""
    report = []

    def note(level, where, why):
        report.append({"level": level, "where": where, "why": why})

    items = doc.get("baselines") if isinstance(doc, dict) else None
    if not isinstance(items, list):
        raise BadRequest("baselines must be a list")
    out = {}
    for i, raw in enumerate(items[:MAX_ENTRIES]):
        where = "baselines[%d]" % i
        try:
            e = clean(raw, where, note, strict=True)
        except BadRequest as err:
            note("dropped", where, str(err))
            continue
        key = known.get(norm(e["name"]))
        if key is None:
            key = norm(e["name"])
            note("note", where, "%s is not in the result files: listed as a baseline to consider, with no numbers of yours beside it" % e["name"])
        if key in out:
            note("dropped", where, "%s is listed twice; the first one is kept" % e["name"])
            continue
        if not (e["paper"] or e.get("code") or e["published"] or any(e.get(k) for k in TEXT)):
            note("dropped", where, "nothing to add for %s" % e["name"])
            continue
        e.update(by=by, at=now_iso())
        out[key] = e
    if len(items) > MAX_ENTRIES:
        note("note", "baselines", "only the first %d were read" % MAX_ENTRIES)
    return out, report


def merge(old, new):
    """A card laid over an older one: a field the new card states replaces the old; what it does not state stays."""
    if not old:
        return new
    e = dict(old)
    e["paper"] = dict(old.get("paper") or {})
    for k, v in (new.get("paper") or {}).items():
        e["paper"][k] = v
    if "pdf" in (new.get("paper") or {}) and not (new["paper"].get("pdf_derived")):
        e["paper"].pop("pdf_derived", None)
    for k in ("code",) + tuple(TEXT):
        if new.get(k) is not None:
            e[k] = new[k]
    if new.get("published"):
        seen = {(norm(p["dataset"]), norm(p["metric"]), p.get("where")) for p in new["published"]}
        e["published"] = [p for p in old.get("published") or [] if (norm(p["dataset"]), norm(p["metric"]), p.get("where")) not in seen] + new["published"]
    e.update(name=old.get("name") or new["name"], by=new.get("by"), at=new.get("at"))
    return e


def changed(old, new):
    """The fields a proposed card would add or change, for the before / after list."""
    out = []
    old = old or {"paper": {}, "published": []}
    for k in tuple(PAPER_TEXT) + ("year",) + LINKS:
        b, a = (old.get("paper") or {}).get(k), (new.get("paper") or {}).get(k)
        if a is not None and a != b:
            out.append({"field": "paper." + k, "before": b, "after": a})
    for k in ("code",) + tuple(TEXT):
        if new.get(k) is not None and new.get(k) != old.get(k):
            out.append({"field": k, "before": old.get(k), "after": new[k]})
    have = {(norm(p["dataset"]), norm(p["metric"]), p.get("where"), p["value"]) for p in old.get("published") or []}
    add = [p for p in new.get("published") or [] if (norm(p["dataset"]), norm(p["metric"]), p.get("where"), p["value"]) not in have]
    if add:
        out.append({"field": "published", "before": len(old.get("published") or []), "after": len(add), "numbers": add})
    return out


# ------------------------------------------------------------------ beside the project's own numbers
def _scale(pub, mine):
    """A paper prints 85.1 where a result file holds 0.851 (or the reverse): compare on the file's scale, and say so."""
    if mine is None or pub is None:
        return pub, False
    a, b = abs(pub), abs(mine)
    if a <= 1 < b <= 100:
        return pub * 100, True
    if b <= 1 < a <= 100:
        return pub / 100, True
    return pub, False


def _mine(item):
    """What the project measured for this method: one line per experiment, dataset and measure."""
    out = []
    for u in (item or {}).get("uses") or []:
        for c in u.get("cells") or []:
            if c.get("value") is None:
                continue
            out.append({"x": u["x"], "metric": u["metric"], "lower": bool(u.get("lower")), "dataset": c.get("dataset"), "column": c.get("column"),
                        "value": c["value"], "ours": c.get("ours"), "ours_label": u.get("ours_label"), "n": c.get("n")})
    return out


def _beside(pub, mine):
    """The project's own number for one published number: same measure, same dataset (or the average column)."""
    ds, mt = norm(pub["dataset"]), norm(pub["metric"])
    for m in mine:
        if norm(m["metric"]) != mt:
            continue
        if (m["dataset"] and norm(m["dataset"]) == ds) or (m["dataset"] is None and m["column"] == AVG and ds in AVG_WORDS):
            return m
    return None


def row(key, name, item, entry, proposal, exp_names):
    e = entry or {"name": name, "paper": {}, "code": None, "published": []}
    mine = _mine(item)
    comp = []
    for p in e.get("published") or []:
        m = _beside(p, mine)
        v, scaled = _scale(p["value"], m["value"] if m else None)
        comp.append({"dataset": p["dataset"], "metric": p["metric"], "published": p["value"], "text": p.get("text"), "where": p.get("where"), "url": p.get("url") or (e.get("paper") or {}).get("pdf") or (e.get("paper") or {}).get("url"),
                     "note": p.get("note"), "mine": m["value"] if m else None, "ours": m["ours"] if m else None, "ours_label": m["ours_label"] if m else None, "x": m["x"] if m else None,
                     "lower": m["lower"] if m else None, "scaled": scaled, "published_scaled": round(v, 10) if scaled else None,
                     "diff": round(m["value"] - v, 10) if m else None})
    pap = e.get("paper") or {}
    missing = [k for k, ok in (("paper", bool(pap.get("url") or pap.get("title"))), ("pdf", bool(pap.get("pdf"))), ("code", bool(e.get("code"))),
                               ("intuition", bool(e.get("intuition"))), ("published", bool(e.get("published")))) if not ok]
    xs = list(dict.fromkeys(m["x"] for m in mine))
    return {"key": key, "name": (item or {}).get("name") or e.get("name") or name, "aliases": (item or {}).get("aliases") or [], "role": (item or {}).get("role"),
            "in_results": item is not None, "item": (item or {}).get("id"), "entry": e, "has_entry": entry is not None,
            "code_host": host(e["code"]) if e.get("code") else None,
            "proposal": proposal, "changes": changed(entry, proposal) if proposal else [],
            "cited": ((item or {}).get("paper") or {}).get("cites") or [], "named": ((item or {}).get("paper") or {}).get("n") or 0,
            "experiments": [{"id": x, "name": exp_names.get(x) or x} for x in xs],
            "mine": mine, "compare": comp, "reproduced": sum(1 for c in comp if c["mine"] is not None), "missing": missing}


def known_names(setup):
    """{normalised name or alias: row key} for every baseline in the result files."""
    out = {}
    for it in (setup or {}).get("items") or []:
        if it.get("kind") == "method" and it.get("role") in ROLES:
            key = it["id"].split(":", 1)[1]
            for n in [it["name"]] + list(it.get("aliases") or []):
                out.setdefault(norm(n), key)
    return out


def build(store, setup):
    """The Baselines page: every baseline of the result files, then the ones the researcher tracks without results yet."""
    items = {it["id"].split(":", 1)[1]: it for it in (setup or {}).get("items") or [] if it.get("kind") == "method" and it.get("role") in ROLES}
    exp_names = {x["id"]: x["name"] for x in (setup or {}).get("experiments") or []}
    entries, proposed = store["entries"], store.get("proposed") or {}
    rows = [row(k, it["name"], it, entries.get(k), proposed.get(k), exp_names) for k, it in items.items()]
    for k in list(entries) + [p for p in proposed if p not in entries]:
        if k not in items:
            src = entries.get(k) or proposed[k]
            rows.append(row(k, src["name"], None, entries.get(k), proposed.get(k), exp_names))
    order = {"base": 0, "baseline": 1, "compared": 1, None: 2}
    rows.sort(key=lambda r: (order.get(r["role"], 2), r["name"].lower()))
    study = (setup or {}).get("study") or "method"
    counts = {"total": len(rows), "in_results": sum(1 for r in rows if r["in_results"]), "proposed": sum(1 for r in rows if r["proposal"]),
              "complete": sum(1 for r in rows if not r["missing"]), "numbers": sum(len(r["compare"]) for r in rows),
              "reproduced": sum(r["reproduced"] for r in rows)}
    for part in PARTS:
        counts[part] = sum(1 for r in rows if part not in r["missing"])
    ours = ((setup or {}).get("method") or {}).get("name") if study == "method" else None
    datasets = [it["name"] for it in (setup or {}).get("items") or [] if it.get("kind") == "dataset"]
    metrics = [it["name"] for it in (setup or {}).get("items") or [] if it.get("kind") == "metric"]
    return {"schema": SCHEMA, "study": study, "ours": ours, "rows": rows, "counts": counts, "datasets": datasets, "metrics": metrics,
            "proposed_by": store.get("proposed_by"), "proposed_at": store.get("proposed_at"), "report": store.get("report") or [],
            "mapped": bool((setup or {}).get("mapped"))}


def brief(view):
    """What an agent needs to fill the cards in: the format, the baselines and what each one still lacks."""
    return {"schema": "lemmata.baselines.brief/1", "guide": GUIDE, "study": view["study"], "ours": view["ours"], "datasets": view["datasets"], "metrics": view["metrics"],
            "baselines": [{"name": r["name"], "aliases": r["aliases"], "in_results": r["in_results"], "missing": r["missing"],
                           "cited_as": [c["title"] or c["key"] for c in r["cited"]],
                           "measured_on": sorted({m["dataset"] for m in r["mine"] if m["dataset"]}), "measures": sorted({m["metric"] for m in r["mine"]})}
                          for r in view["rows"]]}


# ------------------------------------------------------------------ changes
def save(store, key, name, fields, by="you"):
    """The researcher's own edit: it counts at once. A field given as "" or null is cleared; a field not given stays."""
    if not isinstance(fields, dict):
        raise BadRequest("fields must be an object")
    report = []
    raw = dict(fields, name=name)
    e = clean(raw, name, lambda level, where, why: report.append({"level": level, "where": where, "why": why}))
    dropped = [r for r in report if r["level"] == "dropped"]
    if dropped:
        raise BadRequest("%s: %s" % (dropped[0]["where"], dropped[0]["why"]))
    old = store["entries"].get(key)
    out = merge(old, e) if old else e
    p = fields.get("paper") if isinstance(fields.get("paper"), dict) else {}
    for k in tuple(PAPER_TEXT) + ("year",) + LINKS:          # an explicit empty value clears the field
        if k in p and p[k] in (None, ""):
            out["paper"].pop(k, None)
            if k == "pdf":
                out["paper"].pop("pdf_derived", None)
    for k in ("code",) + tuple(TEXT):
        if k in fields and fields[k] in (None, ""):
            out[k] = None
    if "published" in fields:                                 # the editor sends the whole list
        out["published"] = e["published"]
    out.update(name=(old or {}).get("name") or name, by=by, at=now_iso())
    store["entries"][key] = out
    return store, [r for r in report if r["level"] != "dropped"]


def decide(store, action, key=None):
    """confirm / discard the proposal (all of it, or one baseline); remove one card."""
    prop = store.get("proposed") or {}
    if action in ("confirm", "discard"):
        keys = [key] if key else list(prop)
        if not prop or (key and key not in prop):
            raise NotFound("there is no proposal to %s" % action if not key else "no proposal for that baseline")
        for k in keys:
            p = prop.pop(k)
            if action == "confirm":
                store["entries"][k] = merge(store["entries"].get(k), p)
        store["proposed"] = prop or None
        if not prop:
            store["report"] = []
        if action == "confirm":
            store["confirmed_at"] = now_iso()
    elif action == "remove":
        if key not in store["entries"]:
            raise NotFound("that baseline has no card")
        del store["entries"][key]
    else:
        raise BadRequest("action must be save, add, confirm, discard or remove")
    return store
