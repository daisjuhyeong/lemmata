"""Reference cache (cache/refs.json) and the optional --online lookup (OpenAlex, then Crossref)."""
import difflib
import json
import re
import urllib.parse
import urllib.request

SCHEMA = "rmap.refs/1"


def norm_title(t):
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def keys_for(entry):
    ks = []
    if entry.get("doi"):
        ks.append("doi:" + entry["doi"].lower())
    nt = norm_title(entry.get("title"))
    if nt:
        ks.append(nt)
    return ks


def load(hub):
    c = hub.read_json("cache/refs.json", None)
    if not c or not isinstance(c.get("entries"), dict):
        return {"schema": SCHEMA, "entries": {}}
    return c


def record_for(cache, entry):
    for k in keys_for(entry):
        r = cache["entries"].get(k)
        if r:
            return r
    return None


def lookup_state(cache, entry):
    r = record_for(cache, entry)
    if not r:
        return "unchecked"
    return r.get("status") if r.get("status") in ("matched", "not_found", "error") else "unchecked"


# ---- online (opt-in; NOT exercised by the offline tests / demo) ----------------------------------
def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "rmap/0.1 (reference check; local tool)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _accept(entry, title, year):
    ratio = difflib.SequenceMatcher(None, norm_title(entry["title"]), norm_title(title)).ratio()
    if ratio < 0.9:
        return False
    if entry.get("year") and year and abs(int(year) - int(entry["year"])) > 1:
        return False
    return True


def _openalex(entry):
    q = urllib.parse.urlencode({"search": entry["title"], "per-page": 5})
    for w in _get("https://api.openalex.org/works?" + q).get("results", []):
        if _accept(entry, w.get("title") or "", w.get("publication_year")):
            return {"title": w.get("title"), "year": w.get("publication_year"), "doi": (w.get("doi") or "").lower() or None, "url": w.get("id")}
    return None


def _crossref(entry):
    q = urllib.parse.urlencode({"query.bibliographic": entry["title"], "rows": 5})
    for w in _get("https://api.crossref.org/works?" + q).get("message", {}).get("items", []):
        title = (w.get("title") or [""])[0]
        issued = (w.get("issued", {}).get("date-parts") or [[None]])[0][0]
        if _accept(entry, title, issued):
            return {"title": title, "year": issued, "doi": (w.get("DOI") or "").lower() or None, "url": w.get("URL")}
    return None


def online_fill(entries, cache, now_iso):
    """Query entries missing from the cache (or recorded as error). Sequential, 10 s timeout.
    Network failures are recorded as status 'error', never as 'not_found'. Returns True if the cache changed."""
    changed = False
    for e in entries:
        if not e.get("title"):
            continue
        r = record_for(cache, e)
        if r and r.get("status") in ("matched", "not_found"):
            continue
        status, source, match, failed = "not_found", "openalex", None, 0
        for name, fn in (("openalex", _openalex), ("crossref", _crossref)):
            try:
                m = fn(e)
            except Exception:
                failed += 1
                continue
            if m:
                status, source, match = "matched", name, m
                break
        if status != "matched" and failed == 2:
            status, source = "error", "openalex"
        elif status != "matched":
            source = "crossref"
        cache["entries"][keys_for(e)[0]] = {"status": status, "source": source, "checked_at": now_iso, "match": match}
        changed = True
    return changed
