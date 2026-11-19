"""LaTeX to paste (S31): tables, paragraphs and captions written from everything Lemmata holds about the project.

The paper lives in Overleaf, which Lemmata cannot read without a paid plan. So Lemmata does not track the paper's LaTeX;
it is where the LaTeX is made. Three parts:

    tables by rule   Every experiment's table of methods and datasets as a booktabs table, built from the result files
                     with no model. Exact, instant, ready to copy.
    requests         The researcher asks for something ("one table with the main results, ours last; a caption"). Lemmata
                     builds the brief: the claims and their stages, every experiment's numbers, the setup, the key numbers,
                     the baselines, the notation. The researcher's own agent (Claude Code) writes the LaTeX from it.
    snippets         What the agent hands back, kept with its sources. Rules check it: the environments and braces close;
                     every decimal number in it is a number the project's files hold; every citation key is known. When
                     the result files change later, a snippet whose numbers are no longer there is marked stale, which is
                     how the researcher learns that something already pasted into the paper is out of date.

Lemmata calls no model and never compiles or runs the LaTeX. A number it cannot find is reported, not refused: an
average or a difference the agent computed is legitimate, and the researcher should see that it was computed.
"""
import math
import re
import time

from .errors import BadRequest, NotFound
from .experiments import norm

SCHEMA = "lemmata.latex/1"
KINDS = {"table": "Table", "paragraph": "Paragraph", "caption": "Caption", "other": "Other"}
MAX_REQUESTS, MAX_SNIPPETS, MAX_LATEX, MAX_ASK = 40, 120, 20000, 800
WIDE = 12          # more columns than this and the table is turned (datasets down, methods across)

GUIDE = """How to write LaTeX for a Lemmata project.

The researcher pastes what you write straight into their paper, so it must be correct as it stands. Everything you need
is in this brief: the request, the claims and their stages, every experiment with its numbers, the setup (datasets,
measures and their direction, methods and their roles), the key numbers, the baselines and the notation.

Write, then call submit_latex with:
{"request": "<the request id, if there is one>", "kind": "table | paragraph | caption | other",
 "title": "What this is, in a few words",
 "latex": "<the LaTeX, complete: a whole table environment, or the paragraph, or the caption text>",
 "sources": ["map:main (results/main)", "key number h1-delta", "baseline card ADWIN, Table 2 of its paper"],
 "notes": "Anything the researcher should know: what you computed yourself, what you left out, what you were unsure of."}

Rules:
- Numbers. Copy every number exactly from the brief, with the rounding the project uses. Never write a result that is
  not in the brief. If you compute something yourself (an average, a difference, a rank), say so in notes.
- Tables. booktabs (\\toprule, \\midrule, \\bottomrule), no vertical lines. A caption that says what is measured, the
  direction (lower or higher is better) and what bold means. A \\label. The project's own method last, marked. The brief
  gives a table built by rule for each experiment; start from it and reorganise, merge or shorten as the request asks.
- Claims. Write a claim at the strength of its stage. "finding" is stated plainly; "not supported" is reported as a
  result; a hypothesis or an exploration is called one. Do not say the method beats one that is not in the tables.
- Symbols and names. Use the notation and the method, dataset and measure names of the brief.
- Citations. Use only the citation keys the brief lists. Where a citation is needed and no key exists, write
  \\cite{TODO-<name>} and list it in notes.
- Self-contained. No \\input, no custom macros that are not in the brief, no packages beyond booktabs, multirow,
  graphicx and amsmath. Say in notes which packages the snippet needs.
- One thing per submission. A table and its paragraph are two submissions.

Lemmata checks what you submit: environments and braces must close, every decimal number is looked up in the project's
files, every citation key is looked up. What it cannot find is shown to the researcher beside your snippet.
"""


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def load(hub):
    d = hub.read_json("latex.json", None)
    if not isinstance(d, dict) or not str(d.get("schema", "")).startswith("lemmata.latex/"):
        d = {}
    d.setdefault("schema", SCHEMA)
    d.setdefault("requests", [])
    d.setdefault("snippets", [])
    d.setdefault("seq", 0)
    return d


# ------------------------------------------------------------------ tables by rule
_ESC = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "\\": r"\textbackslash{}"}


def esc(text):
    """Plain text -> LaTeX text."""
    return "".join(_ESC.get(ch, ch) for ch in str(text))


def _decimals(values):
    """The number of decimals to print: as many as the most precise value has, four at most."""
    d = 0
    for v in values:
        if v is None:
            continue
        s = repr(float(v))
        if "e" in s or "E" in s:
            return 4
        frac = s.split(".", 1)[1] if "." in s else ""
        d = max(d, 0 if frac == "0" else len(frac))
    return min(d, 4)


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:40] or "table"


def table(exp):
    """One experiment of the Setup document -> a booktabs table, or None when it has no table of methods and columns."""
    grid, proto = exp.get("grid") or {}, exp.get("protocol") or {}
    rows, cols = grid.get("rows") or [], grid.get("cols") or []
    if not rows or not cols:
        return None
    lower = bool(proto.get("lower"))
    vals = [r["values"].get(c) for r in rows for c in cols]
    dec = max(_decimals(vals), 1) if any(isinstance(v, float) and not float(v).is_integer() for v in vals if v is not None) else _decimals(vals)
    fmt = lambda v: "--" if v is None else ("%." + str(dec) + "f") % v
    best = {}
    for c in cols:
        have = [r["values"].get(c) for r in rows if r["values"].get(c) is not None]
        if len(have) > 1:
            best[c] = min(have) if lower else max(have)
    cell = lambda r, c: (r"\textbf{%s}" % fmt(r["values"].get(c))) if c in best and r["values"].get(c) == best[c] else fmt(r["values"].get(c))
    ours = [r for r in rows if r.get("role") == "ours"]
    rest = [r for r in rows if r.get("role") != "ours"]
    label = lambda r: esc(r["label"]) + (" (ours)" if r.get("role") == "ours" else "")
    turned = len(cols) > WIDE and len(rows) <= WIDE
    lines = [r"\begin{table}[t]", r"\centering",
             r"\caption{%s: %s (%s is better)%s. Best in bold.}" % (esc(exp.get("name") or "Results"), esc(proto.get("metric") or "result"), "lower" if lower else "higher",
                                                                   (" on %d datasets" % len(grid.get("datasets") or [])) if len(grid.get("datasets") or []) > 1 else ""),
             r"\label{tab:%s}" % _slug(exp.get("name") or exp.get("id"))]
    if turned:                                        # many datasets: one per line, methods across
        order = rest + ours
        lines += [r"\begin{tabular}{l%s}" % ("c" * len(order)), r"\toprule", " & ".join(["Dataset"] + [label(r) for r in order]) + r" \\", r"\midrule"]
        lines += [" & ".join([esc(c)] + [cell(r, c) for r in order]) + r" \\" for c in cols]
    else:
        lines += [r"\begin{tabular}{l%s}" % ("c" * len(cols)), r"\toprule", " & ".join(["Method"] + [esc(c) for c in cols]) + r" \\", r"\midrule"]
        lines += [" & ".join([label(r)] + [cell(r, c) for c in cols]) + r" \\" for r in rest]
        if ours and rest:
            lines.append(r"\midrule")
        lines += [" & ".join([label(r)] + [cell(r, c) for c in cols]) + r" \\" for r in ours]
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    note = None
    if len(cols) > WIDE and not turned:
        note = "%d columns and %d rows: too wide for a page as it is. Ask your agent to group or split it." % (len(cols), len(rows))
    elif turned:
        note = "Turned: one dataset per line, because %d datasets do not fit across a page." % len(cols)
    return {"x": exp["id"], "name": exp.get("name") or exp["id"], "metric": proto.get("metric"), "lower": lower, "rows": len(rows), "cols": len(cols),
            "latex": "\n".join(lines) + "\n", "note": note, "needs": ["booktabs"]}


def tables(setup):
    return [t for t in (table(x) for x in (setup or {}).get("experiments") or []) if t]


# ------------------------------------------------------------------ the numbers the project holds
def _leaves(obj, out, depth=0):
    if depth > 12:
        return
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        if math.isfinite(obj):
            out.add(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _leaves(v, out, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _leaves(v, out, depth + 1)


def pool(*docs):
    """Every number in the given documents (experiment tables, per-method cells, key numbers, test results)."""
    out = set()
    for d in docs:
        _leaves(d, out)
    return out


_STRIP = [re.compile(p) for p in (
    r"(?<!\\)%.*",                                                         # comments
    r"\\(?:label|ref|eqref|cref|Cref|autoref|cite[a-zA-Z]*|includegraphics|input|bibliography)\*?(?:\[[^\]]*\])*\{[^}]*\}",
    r"\\begin\{(?:tabular|tabularx|array)\*?\}(?:\{[^}]*\})?(?:\[[^\]]*\])?\{[^}]*\}",   # column specifications
    r"\[\s*-?\d*\.?\d+\s*(?:pt|em|ex|cm|mm|in)\s*\]",                       # \\[2pt]
    r"\{\s*-?\d*\.?\d+\s*(?:pt|em|ex|cm|mm|in|\\linewidth|\\textwidth|\\columnwidth)\s*\}",
    r"(?:width|height|scale)\s*=\s*-?\d*\.?\d+\s*(?:\\linewidth|\\textwidth|\\columnwidth|pt|em|cm|mm|in)?",
    r"-?\d*\.?\d+\s*(?:\\linewidth|\\textwidth|\\columnwidth)",
)]
_NUM = re.compile(r"(?<![\w.])-?\d+\.\d+(?![\w.]*\d)|(?<![\w.])-?\d+(?=\s*\\%)")


def literals(latex):
    """The numbers a reader would take as results: decimals, and whole numbers followed by a percent sign."""
    text = latex
    for rx in _STRIP:
        text = rx.sub(" ", text)
    out = []
    for m in _NUM.finditer(text):
        s = m.group(0)
        if s not in out:
            out.append(s)
    return out[:400]


def held(lit, numbers):
    """Is this printed number one the project holds? Compared at the printed precision; a percentage may be a share."""
    try:
        v = float(lit)
    except ValueError:
        return False
    dec = len(lit.split(".", 1)[1]) if "." in lit else 0
    tol = 0.5 * 10 ** (-dec) + 1e-12
    for n in numbers:
        if abs(n - v) <= tol or abs(n * 100 - v) <= tol:
            return True
    return False


def structure(latex):
    """Problems of form a paste would trip over: an environment or a brace left open, another file pulled in."""
    out = []
    text = re.sub(r"(?<!\\)%.*", "", latex)
    stack = []
    for m in re.finditer(r"\\(begin|end)\{([^}]+)\}", text):
        if m.group(1) == "begin":
            stack.append(m.group(2))
        elif not stack or stack.pop() != m.group(2):
            out.append("\\end{%s} has no matching \\begin" % m.group(2))
            break
    else:
        if stack:
            out.append("\\begin{%s} is never closed" % stack[-1])
    bare = re.sub(r"\\[{}]", "", text)
    depth = 0
    for ch in bare:
        depth += ch == "{"
        depth -= ch == "}"
        if depth < 0:
            break
    if depth != 0:
        out.append("a brace is left open" if depth > 0 else "a closing brace has no opening one")
    if re.search(r"\\(?:input|include|write|openout|immediate|catcode)\b", text):
        out.append("it pulls in another file or writes one; a pasted snippet should stand alone")
    return out


def cite_keys(latex):
    out = []
    for m in re.finditer(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}", latex):
        for k in m.group(1).split(","):
            k = k.strip()
            if k and k not in out:
                out.append(k)
    return out


def check(snippet, numbers, bib_keys):
    """What the rules say about one snippet now. -> {status, numbers, found, unknown, stale, form, cites_unknown}"""
    lits = literals(snippet["latex"])
    found = [x for x in lits if held(x, numbers)]
    unknown = [x for x in lits if x not in found]
    was = set(snippet.get("found") or [])
    stale = [x for x in unknown if x in was]                      # it was in the files when this was written, and is not now
    form = structure(snippet["latex"])
    keys = cite_keys(snippet["latex"])
    todo = [k for k in keys if k.upper().startswith("TODO")]
    cites_unknown = None if bib_keys is None else [k for k in keys if k not in bib_keys and k not in todo]
    status = "stale" if stale else "check" if (form or unknown or todo or cites_unknown) else "ok"
    return {"status": status, "numbers": len(lits), "found": found, "unknown": unknown, "stale": stale, "form": form, "cites": keys,
            "cites_todo": todo, "cites_unknown": cites_unknown}


# ------------------------------------------------------------------ requests and snippets
def _text(v, n, what, required=False):
    if v is None or (isinstance(v, str) and not v.strip()):
        if required:
            raise BadRequest("%s is missing" % what)
        return None
    if not isinstance(v, str):
        raise BadRequest("%s must be text" % what)
    return v.strip()[:n]


def targets(setup, claims):
    """What a request can be about: the whole project, one experiment, one claim."""
    out = [{"type": "project", "id": None, "name": "The whole project"}]
    out += [{"type": "experiment", "id": x["id"], "name": x.get("name") or x["id"]} for x in (setup or {}).get("experiments") or []]
    out += [{"type": "claim", "id": c["id"], "name": "%s: %s" % (c.get("short") or c.get("label") or c["id"], (c.get("text") or "")[:90])} for c in (claims or {}).get("claims") or []]
    return out


def find_target(spec, known):
    """{type, id} or a name -> one of the known targets."""
    if spec in (None, "", "project") or (isinstance(spec, dict) and spec.get("type") in (None, "project")):
        return known[0]
    want = spec.get("id") if isinstance(spec, dict) else spec
    if not isinstance(want, str):
        raise BadRequest("target must name an experiment or a claim")
    for t in known[1:]:
        if t["id"] == want or norm(t["name"]) == norm(want) or norm(t["name"]).startswith(norm(want) + ":"):
            return t
    for t in known[1:]:
        if norm(want) and norm(want) in norm(t["name"]):
            return t
    raise NotFound("no experiment or claim called %r" % want)


def add_request(store, kind, target, ask):
    if kind not in KINDS:
        raise BadRequest("kind must be one of: " + ", ".join(KINDS))
    if sum(1 for r in store["requests"] if r["status"] == "open") >= MAX_REQUESTS:
        raise BadRequest("too many open requests; remove some first")
    store["seq"] += 1
    r = {"id": "r%d" % store["seq"], "kind": kind, "target": {"type": target["type"], "id": target["id"], "name": target["name"]},
         "ask": _text(ask, MAX_ASK, "ask"), "status": "open", "created": now_iso(), "snippets": []}
    store["requests"].append(r)
    return r


def add_snippet(store, doc, by, numbers):
    if not isinstance(doc, dict):
        raise BadRequest("the submission must be an object")
    latex = doc.get("latex")
    if not isinstance(latex, str) or not latex.strip():
        raise BadRequest("latex is missing")
    if len(latex) > MAX_LATEX:
        raise BadRequest("latex is too long (%d characters at most); submit one table or one paragraph at a time" % MAX_LATEX)
    if "\x00" in latex:
        raise BadRequest("latex contains a null character")
    kind = doc.get("kind") or "other"
    if kind not in KINDS:
        raise BadRequest("kind must be one of: " + ", ".join(KINDS))
    req = None
    if doc.get("request"):
        req = next((r for r in store["requests"] if r["id"] == doc["request"]), None)
        if req is None:
            raise NotFound("unknown request %r" % doc["request"])
    src = doc.get("sources") or []
    if not isinstance(src, list):
        raise BadRequest("sources must be a list")
    if len(store["snippets"]) >= MAX_SNIPPETS:
        raise BadRequest("too many snippets kept; remove the ones you no longer need")
    store["seq"] += 1
    latex = latex.replace("\r\n", "\n").strip("\n") + "\n"
    s = {"id": "s%d" % store["seq"], "request": req["id"] if req else None, "kind": kind,
         "title": _text(doc.get("title"), 140, "title") or (req["target"]["name"] if req else KINDS[kind]),
         "latex": latex, "notes": _text(doc.get("notes"), 800, "notes"),
         "sources": [" ".join(str(x).split())[:200] for x in src[:40] if isinstance(x, (str, int, float))],
         "by": by, "at": now_iso()}
    s["found"] = [x for x in literals(latex) if held(x, numbers)]          # what the files held when it was written
    store["snippets"].append(s)
    if req:
        req["snippets"].append(s["id"])
        req["status"] = "done"
    return s


def decide(store, action, ident):
    if action == "remove_snippet":
        if not any(s["id"] == ident for s in store["snippets"]):
            raise NotFound("unknown snippet %r" % ident)
        store["snippets"] = [s for s in store["snippets"] if s["id"] != ident]
        for r in store["requests"]:
            r["snippets"] = [x for x in r.get("snippets") or [] if x != ident]
    elif action == "remove_request":
        if not any(r["id"] == ident for r in store["requests"]):
            raise NotFound("unknown request %r" % ident)
        store["requests"] = [r for r in store["requests"] if r["id"] != ident]
    elif action == "reopen":
        r = next((r for r in store["requests"] if r["id"] == ident), None)
        if r is None:
            raise NotFound("unknown request %r" % ident)
        r["status"] = "open"
    else:
        raise BadRequest("action must be request, remove_snippet, remove_request or reopen")
    return store


def build(store, setup, claims, numbers, bib_keys):
    """The LaTeX page: tables by rule, what was asked, what was written and how it checks out now."""
    snips = []
    for s in reversed(store["snippets"]):
        c = check(s, numbers, bib_keys)
        snips.append({k: s.get(k) for k in ("id", "request", "kind", "title", "latex", "notes", "sources", "by", "at")} | {"check": c})
    reqs = [dict(r) for r in reversed(store["requests"])]
    tabs = tables(setup)
    counts = {"tables": len(tabs), "open": sum(1 for r in reqs if r["status"] == "open"), "snippets": len(snips),
              "ok": sum(1 for s in snips if s["check"]["status"] == "ok"), "check": sum(1 for s in snips if s["check"]["status"] == "check"),
              "stale": sum(1 for s in snips if s["check"]["status"] == "stale")}
    return {"schema": SCHEMA, "tables": tabs, "requests": reqs, "snippets": snips, "targets": targets(setup, claims), "kinds": KINDS, "counts": counts,
            "bib": bib_keys is not None}


def brief(request, setup, claims, extra):
    """Everything an agent needs for one request (or for an ad hoc one): the guide and the whole state of the project."""
    exps = []
    tid = request["target"]["id"] if request["target"]["type"] == "experiment" else None
    cid = request["target"]["id"] if request["target"]["type"] == "claim" else None
    for x in (setup or {}).get("experiments") or []:
        t = table(x)
        about = x["id"] == tid or (cid is not None and cid in (x.get("claims") or []))
        exps.append({"id": x["id"], "name": x.get("name"), "type": x.get("type"), "asked_about": about, "claims": x.get("claims") or [],
                     "protocol": x.get("protocol"), "grid": x.get("grid"), "context": {k: (x.get("context") or {}).get(k) for k in ("where", "when", "who")},
                     "table_by_rule": t["latex"] if t else None})
    exps.sort(key=lambda e: not e["asked_about"])
    cl = [{k: c.get(k) for k in ("id", "short", "label", "kind", "text", "stage", "stage_why", "status", "experiments")} | {"asked_about": c["id"] == cid}
          for c in (claims or {}).get("claims") or []]
    items = [{"kind": it["kind"], "name": it["name"], "role": it.get("role"), "lower": it.get("lower"), "aliases": it.get("aliases") or []}
             for it in (setup or {}).get("items") or []]
    out = {"schema": "lemmata.latex.brief/1", "guide": GUIDE, "request": request, "study": (setup or {}).get("study"), "ours": ((setup or {}).get("method") or {}).get("name"),
           "thesis": (claims or {}).get("core"), "claims": cl, "experiments": exps, "setup": items}
    out.update(extra or {})
    return out
