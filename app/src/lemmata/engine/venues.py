"""Venue deadlines (S25): look a conference up in the open ccf-deadlines data on GitHub and read its abstract and paper
deadlines. A plain lookup, no model. The data is community-kept, so every result carries its source and the venue's own
link, and the researcher confirms before anything is stored. Journals have no shared deadline: those are entered by hand."""
import re
import urllib.request
from datetime import datetime, timedelta, timezone

from .errors import BadRequest, NotFound

REPO = "ccfddl/ccf-deadlines"
RAW = "https://raw.githubusercontent.com/%s/main/%%s" % REPO
PAGE = "https://github.com/%s/blob/main/%%s" % REPO
KINDS = (("abstract_deadline", "abstract", "Abstract"), ("deadline", "paper", "Paper"), ("decision_deadline", "decision", "Decision"))


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "lemmata", "Accept": "application/vnd.github+json" if "api.github.com" in url else "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(2_000_000).decode("utf-8", "replace")


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


ALIAS = {"neurips": "nips", "kdd": "sigkdd", "www": "www", "thewebconf": "www"}
SUBS = ("AI", "DB", "NW", "SE", "CG", "HI", "DS", "SC", "CT", "MX")      # the folders of the data, most likely first


def find(name, fetch=_get):
    """-> (path, text) of the venue's file, trying each folder; None when no folder has it."""
    stem = re.sub(r"[^a-z0-9_-]", "", str(name or "").lower().replace(" ", ""))
    if not stem:
        return None
    for sub in [s_ for st_ in dict.fromkeys([stem, ALIAS.get(stem, stem)]) for s_ in [(st_, x) for x in SUBS]]:
        stem, sub = sub
        path = "conference/%s/%s.yml" % (sub, stem)
        try:
            return path, fetch(RAW % path)
        except Exception as e:
            if getattr(e, "code", None) == 404:
                continue
            raise
    return None


def parse(text):
    """The one YAML shape these files use, read line by line (no YAML library). -> {title, description, years: {year: {...}}}"""
    out = {"title": None, "description": None, "years": {}}
    cur, tl = None, None
    val = lambda l: l.split(":", 1)[1].strip().strip("'\"")
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        key = s.lstrip("- ").split(":", 1)[0].strip()
        if key == "title" and out["title"] is None:
            out["title"] = val(s)
        elif key == "description" and out["description"] is None:
            out["description"] = val(s)
        elif key == "year" and s.startswith("-"):
            try:
                cur = out["years"].setdefault(int(val(s)), {"timeline": [], "timezone": None, "link": None, "date": None, "place": None})
            except ValueError:
                cur = None
            tl = None
        elif cur is not None:
            if key in ("abstract_deadline", "deadline", "decision_deadline", "comment"):
                if s.startswith("-") or tl is None:
                    tl = {}
                    cur["timeline"].append(tl)
                tl[key] = val(s)
            elif key in ("timezone", "link", "date", "place"):
                cur[key] = val(s)
    return out


def _offset(tz):
    """'AoE' | 'UTC-12' | 'UTC+8' -> hours east of UTC, or None."""
    if not tz:
        return None
    if tz.strip().lower() == "aoe":
        return -12.0
    m = re.match(r"^(?:UTC|GMT)\s*([+-]\d{1,2})(?::?(\d{2}))?$", tz.strip(), re.I)
    if not m:
        return None
    h = int(m.group(1))
    return h + (int(m.group(2) or 0) / 60.0) * (1 if h >= 0 else -1)


def deadlines(doc, year, path=None):
    """-> [{kind, label, date, time, tz, utc, comment}] for one year; a 'TBD' date is returned with date None."""
    y = doc["years"].get(int(year))
    if y is None:
        raise NotFound("%s has no entry for %s yet (years listed: %s)" % (doc.get("title") or "this venue", year, ", ".join(str(k) for k in sorted(doc["years"])[-4:]) or "none"))
    off = _offset(y.get("timezone"))
    out = []
    for i, tl in enumerate(y["timeline"]):
        for key, kind, label in KINDS:
            raw = tl.get(key)
            if not raw:
                continue
            m = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2})(?::\d{2})?)?$", raw)
            utc = None
            if m and off is not None:
                local = datetime.strptime(m.group(1) + " " + (m.group(2) or "23:59"), "%Y-%m-%d %H:%M")
                utc = (local - timedelta(hours=off)).replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
            out.append({"kind": kind, "label": label + (" (round %d)" % (i + 1) if len(y["timeline"]) > 1 else ""), "date": m.group(1) if m else None, "time": (m.group(2) or "23:59") if m else None,
                        "tz": y.get("timezone"), "utc": utc, "raw": raw, "comment": tl.get("comment")})
    return {"venue": doc.get("title"), "full_name": doc.get("description"), "year": int(year), "link": y.get("link"), "when": y.get("date"), "place": y.get("place"),
            "deadlines": out, "source": PAGE % path if path else None, "source_name": "ccf-deadlines (community data)"}


def lookup(name, year, fetch=_get):
    if not isinstance(name, str) or not name.strip() or len(name) > 60:
        raise BadRequest("venue must be a short name, e.g. ICML")
    try:
        year = int(year)
    except (TypeError, ValueError):
        raise BadRequest("year must be a number")
    try:
        hit = find(name, fetch)
    except Exception as e:
        raise BadRequest("The deadline data could not be reached (%s). Enter the dates by hand, or try again." % type(e).__name__)
    if not hit:
        raise NotFound("No conference called %r in the deadline data. Use its short name (ICML, KDD, NeurIPS is 'nips'), or enter the dates by hand." % name.strip())
    return deadlines(parse(hit[1]), year, hit[0])
