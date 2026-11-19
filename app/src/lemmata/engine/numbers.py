"""Key numbers (S29): the numbers a study rests on, each traced to the file that stores it.

A benchmark study is a list of findings, and each finding is a handful of numbers quoted in the report: an effect size,
an interval, a corrected p, a count of runs that finished. For every such number Lemmata keeps

    claim      which hypothesis or question it belongs to
    file       the committed result file that stores it
    read       how it is read from that file (one cell, or a count / share / median over rows; rules only)
    quoted     what the report says, with the line it says it on

and on every scan reads the file again and says: ok (the file agrees with the report, within the rounding the report
used), mismatch, missing (the file or the row is not in Lemmata's copy of the repository), gap (the researcher knows no
file stores it yet), or unquoted (nothing to compare with). Beside each number: the commit that last wrote the file,
the script that names it and the logged runs that wrote it. What cannot be traced is listed as an open gap.

Two phases, as for the project map (ADR-007): the researcher's own agent proposes the list, rules check every entry
against the files, and the researcher confirms. The numbers of a hypothesis's own test (hypo.py) are listed without
anyone proposing them. No language model runs here; nothing is recomputed from raw data.
"""
import csv
import gzip
import io
import json
import re
import statistics

from .errors import BadRequest, NotFound
from .hypo import check_quote, rel

SCHEMA = "lemmata.numbers/1"
AGGS = ("value", "count", "count_of", "share", "mean", "median", "min", "max", "sum", "all", "any", "distinct")
OPS = ("==", "!=", "<", "<=", ">", ">=", "in", "contains", "notnull", "isnull")
STATUSES = ("ok", "mismatch", "missing", "gap", "unquoted")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,59}$")
NUM_RE = re.compile(r"^[\s~≈<>=]*([-+−]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*(%)?\s*$")
MAX_NUMBERS, MAX_PLAIN, MAX_GZ, MAX_TEXT, MAX_ROWS = 300, 16_000_000, 12_000_000, 96_000_000, 400_000
TRUE, FALSE = {"true", "yes", "1"}, {"false", "no", "0"}

GUIDE = """How to list a project's key numbers for Lemmata.

A key number is a number the report or the notes quote as a result: an effect size, an interval bound, a corrected p,
a median, how many runs finished. Read the report (FINDINGS.md or the paper) and the result files, then call
propose_numbers with:

{"numbers": [
  {"id": "h1-delta", "claim": "H1", "label": "Cliff's delta, D1, time-series vs streaming",
   "file": "results/analysis/tests.csv",
   "read": {"agg": "value", "column": "estimate", "where": [{"column": "test", "op": "==", "value": "H1 (D1)"}]},
   "quoted": {"text": "0.58", "path": "FINDINGS.md", "line": 41, "quote": "<a few words copied from that line>"}},
  {"id": "stepC-cells-ok", "claim": "H2", "label": "Step C: runs that finished",
   "file": "results/C_cells.csv",
   "read": {"agg": "count_of", "where": [{"column": "status", "op": "==", "value": "ok"}]},
   "quoted": {"text": "3254 of 3294", "path": "FINDINGS.md", "line": 120, "quote": "..."}},
  {"id": "arcus-clip5", "claim": null, "label": "ARCUS with inputs clipped to +-5",
   "file": "results/gates/arcus_clip.csv", "read": {"agg": "value", "column": "auc_roc", "where": [{"column": "clip", "op": "==", "value": "5"}]},
   "quoted": {"text": "0.887", "path": "FINDINGS.md", "line": 88, "quote": "..."},
   "gap": "The script that made it is not committed; no committed file holds the number."}
]}

Rules Lemmata enforces (what fails is dropped and reported back):
- "claim": the id of a hypothesis ("H1"), a claim's label, or null for a number that belongs to none (a gate, a check).
- "file": a result file in the repository (.csv, .tsv, .json; .csv.gz and .tsv.gz are read too). A file that is not
  there yet is kept and shown as missing; give "gap" with the reason when you know no committed file holds the number.
- "read": how to get the number from the file, with no arithmetic of your own.
    agg "value": one cell; "where" must select exactly one row. For a .json object use "key": "gates.G-D1" instead of a column.
    agg "count": the rows that match "where". "count_of": "<matching> of <rows>", with "among" as an optional filter
    for the rows counted as the total. "share": matching / total.
    agg "mean", "median", "min", "max", "sum": over "column", for the rows that match "where".
    agg "all" / "any": whether "column" is true in all / any matching rows (for a .json object: "keys": ["gates.G-D1", ...]).
    agg "distinct": how many different values "column" has in the matching rows.
    "where" and "among": [{"column", "op", "value"}] with op one of == != < <= > >= in contains notnull isnull;
    every condition must hold. For "one of these": {"or": [{...}, {...}]}. True and False are written "True", "False".
- "quoted": the number as the report prints it ("0.58", "3254 of 3294", "True"), with the file and line and a short
  quote that really is on that line. Lemmata compares with the rounding the text used: "0.58" matches 0.5841.
- Do not list a number no file stores as if a file stored it. If the report quotes a number that is only computed in a
  script or a notebook, list it with "gap" (where it is computed) and "read": null; "file" may then name the file it is
  derived from, or be left out. That gap is what the list is for.
- A proposal adds to the confirmed list (same id: replaced). The researcher confirms; you cannot.
"""


# ------------------------------------------------------------------ storage
def load(hub):
    d = hub.read_json("numbers.json", None)
    if not isinstance(d, dict) or not str(d.get("schema", "")).startswith("lemmata.numbers/"):
        d = {}
    d.setdefault("schema", SCHEMA)
    d.setdefault("confirmed", [])
    d.setdefault("proposed", None)
    d.setdefault("report", [])
    return d


# ------------------------------------------------------------------ reading a file
def _text(v, n, what, required=True):
    if not isinstance(v, str) or not v.strip():
        if required:
            raise BadRequest("%s is missing" % what)
        return None
    return " ".join(v.split())[:n]


def num(v):
    """A cell or a quoted text -> a float, or None. '0.58', '−0.05', '12%' (as 12), True/False are not numbers."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if v == v else None
    m = NUM_RE.match(str(v))
    if not m:
        return None
    try:
        x = float(m.group(1).replace("−", "-"))
    except ValueError:
        return None
    return x if x == x else None


def truth(v):
    if isinstance(v, bool):
        return v
    t = str(v).strip().lower()
    return True if t in TRUE else False if t in FALSE else None


class Reader:
    """Result files as rows, read once per build. A table is a list of {column: text}; a .json object stays an object."""

    def __init__(self, files):
        self.files, self.cache = files, {}

    def get(self, path):
        """-> (kind, data, why): kind "rows" | "object" | None."""
        path = rel(path)
        if path not in self.cache:
            self.cache[path] = self._read(path)
        return self.cache[path]

    def _read(self, path):
        rid, path = self.files.find(path)
        if rid is None:
            return None, None, "%s is not in Lemmata's copy of the repository" % path
        t = self.files.trees[rid]
        low = path.lower()
        gz = low.endswith(".gz")
        try:
            size = t.size(path)
            if size > (MAX_GZ if gz else MAX_PLAIN):
                return None, None, "%s is too large to read (%d MB)" % (path, size // 1_000_000)
            raw = t.read(path)
            if gz:
                with gzip.GzipFile(fileobj=io.BytesIO(raw)) as f:
                    raw = f.read(MAX_TEXT + 1)
                if len(raw) > MAX_TEXT:
                    return None, None, "%s is too large to read once unpacked" % path
                low = low[:-3]
            text = raw.decode("utf-8", "replace")
        except Exception as e:
            return None, None, "%s could not be read (%s)" % (path, type(e).__name__)
        if low.endswith(".json"):
            try:
                d = json.loads(text)
            except ValueError:
                return None, None, "%s is not valid JSON" % path
            if isinstance(d, list) and all(isinstance(r, dict) for r in d):
                return "rows", d[:MAX_ROWS], None
            if isinstance(d, dict) and isinstance(d.get("rows"), list) and all(isinstance(r, dict) for r in d["rows"]):
                return "rows", d["rows"][:MAX_ROWS], None
            if isinstance(d, dict):
                return "object", d, None
            return None, None, "%s holds neither rows nor an object" % path
        if low.endswith((".csv", ".tsv", ".txt")):
            dialect = "excel-tab" if low.endswith(".tsv") else "excel"
            rows = []
            for r in csv.DictReader(io.StringIO(text), dialect=dialect):
                rows.append(r)
                if len(rows) >= MAX_ROWS:
                    break
            if not rows:
                return None, None, "%s has no rows" % path
            return "rows", rows, None
        return None, None, "%s is not a table Lemmata reads (.csv, .tsv, .json, or those gzipped)" % path


def _key(obj, path):
    """'gates.G-D1' in a JSON object -> (found, value)."""
    cur = obj
    for part in str(path).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return False, None
    return True, cur


def _match(row, conds):
    for c in conds or []:
        if "or" in c:      # one of these must hold
            if not any(_match(row, [alt]) for alt in c["or"]):
                return False
            continue
        v = row.get(c["column"])
        op = c["op"]
        empty = v is None or str(v).strip() == "" or str(v).strip().lower() in ("nan", "none", "null")
        if op == "notnull":
            if empty:
                return False
            continue
        if op == "isnull":
            if not empty:
                return False
            continue
        if op == "in":
            if str(v).strip() not in c["value"]:
                return False
            continue
        if op == "contains":
            if empty or not any(part in str(v) for part in c["value"]):
                return False
            continue
        a, b = num(v), num(c["value"])
        if op in ("==", "!="):
            same = (a == b) if a is not None and b is not None else str(v).strip() == str(c["value"]).strip()
            if same != (op == "=="):
                return False
            continue
        if a is None or b is None or not {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]:
            return False
    return True


def _conds(v, cols, where, what, loose=False):
    """[{column, op, value}] checked against the file's columns. loose: the file is not there yet, so columns cannot be checked."""
    out = []
    for c in (v if isinstance(v, list) else [])[:8]:
        if isinstance(c, dict) and isinstance(c.get("or"), list):
            alts = _conds(c["or"], cols, where, what, loose)
            if len(alts) < 2 or any("or" in a for a in alts):
                raise BadRequest("%s: \"or\" needs two or more plain conditions" % what)
            out.append({"or": alts})
            continue
        if not isinstance(c, dict) or not isinstance(c.get("column"), str) or c.get("op", "==") not in OPS:
            raise BadRequest("%s: each condition needs a column and an op (%s)" % (what, " ".join(OPS)))
        if not loose and c["column"] not in cols:
            raise BadRequest("%s: %r is not a column of the file (columns: %s)" % (what, c["column"][:40], ", ".join(sorted(cols)[:10])))
        op, val = c.get("op", "=="), c.get("value")
        if op in ("in", "contains"):
            val = [val] if op == "contains" and isinstance(val, str) else val
            if not isinstance(val, list) or not val:
                raise BadRequest("%s: op %r needs a list of values" % (what, op))
            val = [str(a).strip()[:80] for a in val[:40] if str(a).strip()]
        elif op in ("notnull", "isnull"):
            val = None
        elif isinstance(val, bool):
            val = "True" if val else "False"
        elif isinstance(val, (int, float)):
            val = val
        elif isinstance(val, str):
            val = val.strip()[:120]
        else:
            raise BadRequest("%s: the condition on %r needs a value" % (what, c["column"][:40]))
        out.append({"column": c["column"][:120], "op": op, "value": val})
    return out


def fmt(v):
    """A number as it is shown: four significant digits, whole numbers whole."""
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, (int, float)):
        if v != v:
            return "nan"
        if float(v).is_integer() and abs(v) < 1e15:
            return str(int(v))
        return "%.4g" % v
    return str(v)


def read(reader, n):
    """Read one key number from its file. -> {found (text), value, why} with found None when it cannot be read."""
    r = n["read"]
    if r is None:
        return {"found": None, "value": None, "why": "No file stores this number.", "absent": False}
    kind, data, why = reader.get(n["file"])
    if kind is None:
        return {"found": None, "value": None, "why": why, "absent": True}
    agg = r["agg"]
    if kind == "object":
        keys = [r["key"]] if r.get("key") else r.get("keys") or []
        if not keys:
            return {"found": None, "value": None, "why": "%s is one JSON object: the number needs a \"key\" such as gates.G-D1" % n["file"]}
        got = [_key(data, k) for k in keys]
        lost = [k for k, (ok, _) in zip(keys, got) if not ok]
        if lost:
            return {"found": None, "value": None, "why": "%s has no key %s" % (n["file"], ", ".join(lost[:3])), "absent": True}
        vals = [v for _, v in got]
        if agg in ("all", "any"):
            ts = [truth(v) for v in vals]
            if any(t is None for t in ts):
                return {"found": None, "value": None, "why": "not every key holds true or false"}
            v = all(ts) if agg == "all" else any(ts)
            return {"found": fmt(v), "value": v, "why": None}
        if len(vals) != 1:
            return {"found": None, "value": None, "why": "agg %r reads one key" % agg}
        v = vals[0]
        return {"found": fmt(v) if not isinstance(v, (dict, list)) else None, "value": v if not isinstance(v, (dict, list)) else None,
                "why": None if not isinstance(v, (dict, list)) else "the key holds an object, not a number"}
    rows = data
    col = r.get("column")
    if col and rows and col not in rows[0]:
        return {"found": None, "value": None, "why": "%s has no column %r" % (n["file"], col), "absent": True}
    hits = [x for x in rows if _match(x, r.get("where"))]
    if agg == "value":
        if len(hits) != 1:
            return {"found": None, "value": None, "why": "%d rows of %s match; one cell needs exactly one row" % (len(hits), n["file"]), "absent": not hits}
        v = hits[0].get(col)
        x = num(v)
        if x is not None:
            return {"found": fmt(x), "value": x, "why": None}
        return {"found": str(v).strip() if v is not None and str(v).strip() else None, "value": str(v).strip() if v is not None else None,
                "why": None if v is not None and str(v).strip() else "the cell is empty"}
    if agg == "count":
        return {"found": str(len(hits)), "value": len(hits), "why": None}
    if agg in ("count_of", "share"):
        total = [x for x in rows if _match(x, r.get("among"))]
        part = [x for x in total if _match(x, r.get("where"))]
        if agg == "count_of":
            return {"found": "%d of %d" % (len(part), len(total)), "value": "%d of %d" % (len(part), len(total)), "why": None}
        if not total:
            return {"found": None, "value": None, "why": "no row to take a share of"}
        return {"found": fmt(len(part) / len(total)), "value": len(part) / len(total), "why": None}
    if agg == "distinct":
        v = len({str(x.get(col)).strip() for x in hits if x.get(col) is not None and str(x.get(col)).strip()})
        return {"found": str(v), "value": v, "why": None}
    if agg in ("all", "any"):
        ts = [truth(x.get(col)) for x in hits]
        if not hits or any(t is None for t in ts):
            return {"found": None, "value": None, "why": "no matching row" if not hits else "column %r is not true/false in every matching row" % col}
        v = all(ts) if agg == "all" else any(ts)
        return {"found": fmt(v), "value": v, "why": None}
    xs = [a for a in (num(x.get(col)) for x in hits) if a is not None]
    if not xs:
        return {"found": None, "value": None, "why": "no number in column %r for the matching rows" % col, "absent": not hits}
    v = {"mean": lambda: sum(xs) / len(xs), "median": lambda: statistics.median(xs), "min": lambda: min(xs), "max": lambda: max(xs), "sum": lambda: sum(xs)}[agg]()
    return {"found": fmt(v), "value": v, "why": None, "rows": len(xs)}


def agrees(quoted, value):
    """Does the file's value agree with the text the report printed? Numbers within the rounding the text used
    ("0.58" covers 0.575 to 0.585; a percentage also against the share); anything else as the same words."""
    if quoted is None or value is None:
        return None
    q = re.sub(r"(?<=\d)[,\u202f\u2009](?=\d{3}(?!\d))", "", " ".join(str(quoted).split()))      # "3,254 of 3,294" is 3254 of 3294
    if isinstance(value, bool):
        return truth(q) is not None and truth(q) == value
    m = NUM_RE.match(q)
    v = value if isinstance(value, (int, float)) else num(value)
    if not m and truth(q) is not None and truth(value) is not None:
        return truth(q) == truth(value)
    if m and v is not None:
        txt = m.group(1).replace("−", "-")
        p = float(txt)
        mant = txt.lower().split("e")[0]
        dec = len(mant.split(".")[1]) if "." in mant else 0
        scale = 10 ** int(txt.lower().split("e")[1]) if "e" in txt.lower() else 1
        tol = 0.5 * 10 ** -dec * scale
        cands = [v] + ([v * 100] if m.group(2) else [])
        return any(abs(c - p) <= tol * (1 + 1e-9) + 1e-12 for c in cands)
    return re.sub(r"\s+", " ", q).strip().lower() == re.sub(r"\s+", " ", str(value)).strip().lower()


# ------------------------------------------------------------------ verify a proposal
def verify(doc, files, known_claims):
    """A proposed list -> (clean entries, report). known_claims: {name in any spelling: claim key}; an unknown claim is kept as none."""
    items = doc.get("numbers") if isinstance(doc, dict) else doc
    if not isinstance(items, list) or not items:
        raise BadRequest("the proposal must be {\"numbers\": [...]} with at least one entry")
    report, out, seen = [], [], set()
    note = lambda level, where, why: report.append({"level": level, "where": where, "why": why})
    reader = Reader(files)
    if len(items) > MAX_NUMBERS:
        note("dropped", "numbers", "only the first %d are kept; %d more were ignored" % (MAX_NUMBERS, len(items) - MAX_NUMBERS))
    for i, n in enumerate(items[:MAX_NUMBERS]):
        where = "number %s" % (n.get("id") if isinstance(n, dict) and n.get("id") else i + 1)
        try:
            if not isinstance(n, dict):
                raise BadRequest("not an object")
            nid = n.get("id") if isinstance(n.get("id"), str) and ID_RE.match(n["id"]) else None
            if not nid:
                raise BadRequest("id must be a short name (letters, digits, - _ . :)")
            if nid in seen:
                raise BadRequest("the id %r is used twice" % nid)
            path = rel(n.get("file"))
            gap = _text(n.get("gap"), 300, "gap", False)
            if not path and not (gap and n.get("read") is None):
                raise BadRequest("file is missing")
            if n.get("read") is None and gap:      # a number no file stores: nothing to read, only the gap to keep in sight
                q = n.get("quoted")
                q = {"text": str(q)} if isinstance(q, (str, int, float)) and not isinstance(q, bool) else q if isinstance(q, dict) else {}
                quoted = None
                if q.get("text") is not None and str(q["text"]).strip():
                    ev = check_quote(files, {"path": q.get("path"), "line": q.get("line"), "quote": q.get("quote") or str(q["text"])}) if q.get("path") else None
                    quoted = {"text": " ".join(str(q["text"]).split())[:80], "path": (ev or {}).get("path"), "line": (ev or {}).get("line"), "quote": (ev or {}).get("quote")}
                claim, ckey = n.get("claim"), None
                if isinstance(claim, str) and claim.strip():
                    ckey = known_claims.get(re.sub(r"[^a-z0-9]+", "", claim.lower()))
                out.append({"id": nid, "claim": ckey, "label": _text(n.get("label") or nid, 160, "label"), "file": path, "read": None, "quoted": quoted,
                            "gap": gap, "note": _text(n.get("note"), 300, "note", False)})
                seen.add(nid)
                continue
            r = n.get("read") if isinstance(n.get("read"), dict) else {}
            agg = r.get("agg", "value")
            if agg not in AGGS:
                raise BadRequest("read.agg must be one of %s" % ", ".join(AGGS))
            kind, data, why = reader.get(path)
            loose = kind is None
            cols = set(data[0]) if kind == "rows" and data else set()
            rd = {"agg": agg}
            if kind == "object" or (loose and (r.get("key") or r.get("keys"))):
                keys = [r["key"]] if isinstance(r.get("key"), str) else [k for k in (r.get("keys") or []) if isinstance(k, str)][:20]
                if not keys:
                    raise BadRequest("%s is one JSON object: give read.key (e.g. \"gates.G-D1\")" % path)
                if agg not in ("value", "all", "any"):
                    raise BadRequest("a JSON object is read with agg value, all or any")
                rd["key" if len(keys) == 1 and agg == "value" else "keys"] = keys[0] if len(keys) == 1 and agg == "value" else keys
            else:
                col = r.get("column")
                if agg not in ("count", "count_of", "share"):
                    if not isinstance(col, str) or not col.strip():
                        raise BadRequest("read.column is missing")
                    if not loose and col not in cols:
                        raise BadRequest("%r is not a column of %s (columns: %s)" % (col[:40], path, ", ".join(sorted(cols)[:10])))
                    rd["column"] = col[:120]
                rd["where"] = _conds(r.get("where"), cols, where, "where", loose)
                if agg in ("count_of", "share"):
                    rd["among"] = _conds(r.get("among"), cols, where, "among", loose)
            q = n.get("quoted")
            quoted = None
            if isinstance(q, (str, int, float)) and not isinstance(q, bool):
                q = {"text": str(q)}
            if isinstance(q, dict) and q.get("text") is not None and str(q["text"]).strip():
                quoted = {"text": " ".join(str(q["text"]).split())[:80], "path": None, "line": None, "quote": None}
                if q.get("path"):
                    ev = check_quote(files, {"path": q.get("path"), "line": q.get("line"), "quote": q.get("quote") or str(q["text"])})
                    if ev:
                        quoted.update(path=ev["path"], line=ev["line"], quote=ev["quote"])
                    else:
                        note("warning", where, "the quote %r is not in %s; the quoted text is kept without its line" % (str(q.get("quote") or q["text"])[:50], str(q.get("path"))[:80]))
            claim = n.get("claim")
            ckey = None
            if isinstance(claim, str) and claim.strip():
                ckey = known_claims.get(re.sub(r"[^a-z0-9]+", "", claim.lower()))
                if ckey is None:
                    note("warning", where, "the claim %r is not a hypothesis or a claim of this project; listed under no claim" % claim[:40])
            entry = {"id": nid, "claim": ckey, "label": _text(n.get("label") or nid, 160, "label"), "file": path, "read": rd, "quoted": quoted,
                     "gap": gap, "note": _text(n.get("note"), 300, "note", False)}
            if loose:
                note("waiting" if not gap else "gap", where, (why or "the file cannot be read") + ("; kept and looked for again at every scan" if not gap else "; kept as a known gap"))
            else:
                got = read(reader, entry)
                if got["found"] is None and not gap:
                    raise BadRequest(got["why"] or "the number cannot be read")
                if quoted and got["found"] is not None and agrees(quoted["text"], got["value"]) is False and not gap:
                    note("warning", where, "the report says %s, the file holds %s: kept, and shown as a mismatch" % (quoted["text"], got["found"]))
            out.append(entry)
            seen.add(nid)
        except BadRequest as e:
            note("dropped", where, str(e))
    if not out:
        raise BadRequest("no number survived checking: " + "; ".join(r["why"] for r in report[:3]))
    return out, report


def merge(confirmed, proposed):
    """A confirmed proposal adds to the list; an entry with the same id is replaced in place."""
    by = {n["id"]: n for n in proposed}
    out = [by.pop(n["id"], n) for n in confirmed]
    return out + list(by.values())


def remove(store, nid):
    for key in ("proposed", "confirmed"):
        if any(n["id"] == nid for n in store.get(key) or []):
            store[key] = [n for n in store[key] if n["id"] != nid]
            if key == "proposed" and not store[key]:
                store["proposed"] = None
            return store
    raise NotFound("unknown key number %r" % nid)


# ------------------------------------------------------------------ the numbers of a hypothesis's own test
def from_tests(hypotheses):
    """Every hypothesis with a test rule already names its numbers: the columns the rule reports, in its row of the test table."""
    out = []
    for h in hypotheses:
        if h.get("archived"):
            continue
        rules = ([h["criterion"]["rule"]] if (h.get("criterion") or {}).get("rule") else []) + list(h.get("sub_rules") or [])
        for k, rule in enumerate(rules):
            where = [{"column": c, "op": "==", "value": v} for c, v in rule["select"].items()]
            for col in rule.get("report") or []:
                out.append({"id": "test:%s:%s%s" % (h["id"], col, "" if k == 0 else ":%d" % (k + 1)), "claim": "h:" + h["id"], "label": "%s (the test's own row)" % col,
                            "file": rule["file"], "read": {"agg": "value", "column": col, "where": where}, "quoted": None, "gap": None, "note": None, "auto": True})
    return out


# ------------------------------------------------------------------ the document
def _artifact_hits(run, path):
    return any(a.get("path") == path or str(a.get("path") or "").endswith("/" + path) for a in run.get("artifacts") or [])


def _under(path, prefixes):
    return any(path == p or path.startswith(p.rstrip("/") + "/") for p in prefixes)


def build(store, files, claims, hypotheses, steps, events, made, runs, sync=None):
    """-> the Key numbers document.
    claims: [{key, label, text, stage, order}] every claim a number can belong to; hypotheses: live hypothesis records;
    steps: hypothesis-first experiments ({id, deliverables, tests_claims}); events: the commit events; made: {path: the
    result-file ledger's row} (the code behind a file); runs: the logged runs (runs.view rows); sync: the hub's sync state."""
    reader = Reader(files)
    last = {}
    for ev in events:
        if ev.get("kind") == "commit":
            for f in ev.get("files", []):
                last[f["path"]] = {"short": ev.get("short"), "time": ev.get("time"), "subject": (ev.get("subject") or "")[:100]}
    made = made or {}
    confirmed = list(store.get("confirmed") or [])
    proposed = list(store.get("proposed") or [])
    auto = [n for n in from_tests(hypotheses) if not any(c["file"] == n["file"] and c["read"] == n["read"] for c in confirmed + proposed)]
    behind = bool(sync and sync.get("failing"))

    def one(n, state):
        got = read(reader, n)
        q = (n.get("quoted") or {}).get("text")
        if got["found"] is None:
            status = "gap" if n.get("gap") else "missing"
            why = got["why"]
            if status == "missing" and behind and got.get("absent"):
                why = "%s. Lemmata's copy of the repository is behind GitHub (sync is failing), so this may only be missing here" % why
        else:
            same = agrees(q, got["value"]) if q is not None else None
            status = "unquoted" if same is None else "ok" if same else ("gap" if n.get("gap") else "mismatch")
            why = None if same is not False else "The report says %s; the file holds %s." % (q, got["found"])
        row = made.get(n["file"]) or {}
        wrote = [r for r in runs if _artifact_hits(r, n["file"])]
        return dict(n, state=state, found=got["found"], status=status, why=why, commit=last.get(n["file"]),
                    scripts=[c["name"] for c in row.get("code") or []][:4], stale=row.get("status") == "stale",
                    runs=[{"run_id": r["run_id"], "state": r["state"], "sha": (r.get("git_sha") or "")[:7] or None, "time": r.get("time")} for r in wrote[:4]],
                    runs_n=len(wrote))

    rows = [one(n, "confirmed") for n in confirmed] + [one(n, "test") for n in auto] + [one(n, "proposed") for n in proposed if not any(c["id"] == n["id"] for c in confirmed)]
    replaced = [n["id"] for n in proposed if any(c["id"] == n["id"] for c in confirmed)]
    by_claim = {c["key"]: dict(c, numbers=[], runs=[]) for c in claims}
    none = {"key": None, "label": "No claim", "text": "Gates, checks and other numbers that belong to no hypothesis.", "stage": None, "order": 10 ** 6, "numbers": [], "runs": []}
    for r in rows:
        (by_claim.get(r["claim"]) or none)["numbers"].append(r)
    # the runs behind each claim: the ones that wrote a number's file, and (hypothesis-first) the ones that wrote its steps' deliverables
    for g in list(by_claim.values()) + [none]:
        fs = {n["file"] for n in g["numbers"]}
        pre = [d for x in steps or [] if g["key"] and g["key"][2:] in (x.get("tests_claims") or []) and g["key"].startswith("h:") for d in x.get("deliverables") or []]
        seen = set()
        for r in runs:
            arts = [str(a.get("path") or "") for a in r.get("artifacts") or []]
            if r["run_id"] in seen or not (any(_artifact_hits(r, f) for f in fs) or any(_under(a, pre) or any(a.endswith("/" + p.rstrip("/")) or ("/" + p.rstrip("/") + "/") in a for p in pre) for a in arts)):
                continue
            seen.add(r["run_id"])
            g["runs"].append({"run_id": r["run_id"], "state": r["state"], "sha": (r.get("git_sha") or "")[:7] or None, "time": r.get("time"),
                              "command": (r.get("command") or "")[:160], "note": (r.get("note") or "")[:200] or None, "exit": r.get("exit_code"),
                              "sha_basis": r.get("sha_basis"), "kind": r.get("kind")})
        g["runs"] = g["runs"][:30]
        g["counts"] = {s: sum(1 for n in g["numbers"] if n["status"] == s) for s in STATUSES}
    groups = sorted((g for g in by_claim.values() if g["numbers"] or g["runs"]), key=lambda g: g["order"]) + ([none] if none["numbers"] else [])
    # what cannot be traced, as a list to work through
    gaps = []
    for g in groups:
        for n in g["numbers"]:
            who = "%s · %s" % (g["label"], n["label"])
            if n["status"] == "mismatch":
                gaps.append({"k": "mismatch", "number": n["id"], "claim": g["key"], "t": "%s: %s" % (who, n["why"])})
            elif n["status"] == "missing":
                gaps.append({"k": "missing", "number": n["id"], "claim": g["key"], "t": "%s: %s." % (who, (n["why"] or "cannot be read").rstrip("."))})
            elif n["status"] == "gap":
                gaps.append({"k": "gap", "number": n["id"], "claim": g["key"], "t": "%s: %s" % (who, n["gap"])})
            if n["status"] in ("ok", "unquoted", "mismatch") and not n["commit"]:
                gaps.append({"k": "uncommitted", "number": n["id"], "claim": g["key"], "t": "%s: %s is in the working copy but in no commit Lemmata has seen." % (who, n["file"])})
            if n["stale"]:
                gaps.append({"k": "stale", "number": n["id"], "claim": g["key"], "t": "%s: the code behind %s changed after the file was written." % (who, n["file"])})
        no_run = sorted({n["file"] for n in g["numbers"] if n["found"] is not None and not n["runs_n"]})
        if no_run:
            gaps.append({"k": "no_run", "claim": g["key"], "files": no_run[:12],
                         "t": "%s: no logged run wrote %s. The commit is the only record of how %s made." % (
                             g["label"], ", ".join(no_run[:3]) + (" and %d more" % (len(no_run) - 3) if len(no_run) > 3 else ""), "it was" if len(no_run) == 1 else "they were")})
        off = [r for r in g["runs"] if r["state"] in ("not in github", "uncommitted", "unknown commit")]
        if off and not behind:
            gaps.append({"k": "run_code", "claim": g["key"], "runs": [r["run_id"] for r in off[:8]],
                         "t": "%s: %d run%s on code that is not in GitHub (%s)." % (g["label"], len(off), "" if len(off) == 1 else "s", ", ".join(r["run_id"] for r in off[:3]))})
        basis = [r for r in g["runs"] if r.get("sha_basis") == "results_commit"]
        if basis:
            gaps.append({"k": "start_commit", "claim": g["key"], "runs": [r["run_id"] for r in basis[:8]],
                         "t": "%s: %d run%s recorded with the commit that first held the results, not the commit the run started from." % (g["label"], len(basis), "" if len(basis) == 1 else "s")})
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}
    counts.update(total=len(rows), confirmed=len(confirmed), proposed=len(proposed), from_tests=len(auto), gaps=len(gaps),
                  runs=len({r["run_id"] for g in groups for r in g["runs"]}))
    return {"schema": SCHEMA, "state": "proposed" if proposed else "confirmed" if confirmed else "tests" if auto else "none",
            "groups": groups, "gaps": gaps, "counts": counts, "report": store.get("report") or [], "replaces": replaced,
            "proposed_by": store.get("proposed_by"), "proposed_at": store.get("proposed_at"), "confirmed_at": store.get("confirmed_at"),
            "behind": {"since": sync.get("since"), "why": sync.get("message"), "head": sync.get("head")} if behind else None}
