"""Minimal .bib reader with line numbers."""
import hashlib
import re

ENTRY_RE = re.compile(r"^[ \t]*@(\w+)\s*([{(])\s*([^,\s{}()]+)\s*,", re.M)
SKIP_TYPES = {"comment", "string", "preamble"}


def _match_close(text, open_pos):
    opener = text[open_pos]
    closer = "}" if opener == "{" else ")"
    depth = 0
    i = open_pos
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(text) - 1


def _fields(body):
    out = {}
    i = 0
    n = len(body)
    name_re = re.compile(r"\s*,?\s*([A-Za-z][\w\-]*)\s*=\s*")
    while i < n:
        m = name_re.match(body, i)
        if not m:
            break
        name = m.group(1).lower()
        i = m.end()
        if i >= n:
            break
        if body[i] == "{":
            j = _match_close(body, i)
            val = body[i + 1:j]
            i = j + 1
        elif body[i] == '"':
            j = i + 1
            while j < n and body[j] != '"':
                j += 2 if body[j] == "\\" else 1
            val = body[i + 1:j]
            i = j + 1
        else:
            m2 = re.compile(r"[^,}\s]+").match(body, i)
            val = m2.group(0) if m2 else ""
            i = m2.end() if m2 else i + 1
        out[name] = val
    return out


def _clean(s):
    s = re.sub(r"[{}]", "", s or "")
    return re.sub(r"\s+", " ", s).strip()


def parse_bib(text, path):
    """-> list of entries: key, type, title, year, doi, line, text, hash."""
    entries = []
    seen = set()
    for m in ENTRY_RE.finditer(text):
        typ = m.group(1).lower()
        if typ in SKIP_TYPES:
            continue
        key = m.group(3)
        if key in seen:
            continue
        seen.add(key)
        open_pos = text.index(m.group(2), m.start(2))
        end = _match_close(text, open_pos)
        body = text[m.end():end]
        f = _fields(body)
        raw = text[m.start():end + 1]
        yr = re.search(r"\d{4}", f.get("year", ""))
        entries.append({
            "key": key, "type": typ, "path": path,
            "title": _clean(f.get("title")), "year": int(yr.group(0)) if yr else None,
            "doi": _clean(f.get("doi")).lower() or None,
            "line": text.count("\n", 0, m.start()) + 1,
            "line_text": text.splitlines()[text.count("\n", 0, m.start())].rstrip()[:300],
            "hash": "sha256:" + hashlib.sha256(re.sub(r"\s+", " ", raw).strip().encode("utf-8")).hexdigest(),
        })
    return entries
