"""Code-side readers: python imports, write calls, run records, README provenance tables, config keys."""
import ast
import warnings
import hashlib
import json
import posixpath
import re

WRITE_WORDS = ("savefig", "to_csv", "to_json", "write_text", "json.dump", "np.save", "torch.save")
OUT_LITERAL_RE = re.compile(r"""["']([^"'\n]+\.(?:png|pdf|svg|jpg|jpeg|eps|csv|tsv|json|jsonl|txt|npz|npy|pkl|pt|parquet))["']""")
WMODE_RE = re.compile(r"""["']wb?["']""")


# ---------------------------------------------------------------- imports
def _candidates(mod_parts, file_dir, repo_root_prefix=""):
    rel = "/".join(mod_parts)
    base_dirs = [""]
    if True:
        base_dirs.append("src")
    d = file_dir
    chain = []
    while True:
        chain.append(d)
        if d == "":
            break
        d = posixpath.dirname(d)
    out = []
    for b in base_dirs:
        pre = posixpath.join(b, rel) if b else rel
        out += [pre + ".py", posixpath.join(pre, "__init__.py")]
    for d in chain:
        pre = posixpath.join(d, rel) if d else rel
        out += [pre + ".py", posixpath.join(pre, "__init__.py")]
    return out


def python_imports(path, source, fileset):
    """-> list of (target_path, lineno). Third-party / unresolved names are ignored."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    file_dir = posixpath.dirname(path)
    found = []

    def first(parts, rel_dir=None):
        if rel_dir is not None:
            pre = posixpath.join(rel_dir, *parts) if parts else rel_dir
            for c in (pre + ".py", posixpath.join(pre, "__init__.py")):
                c = posixpath.normpath(c)
                if c in fileset:
                    return c
            return None
        for c in _candidates(parts, file_dir):
            c = posixpath.normpath(c)
            if c in fileset:
                return c
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                t = first(a.name.split("."))
                if t:
                    found.append((t, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            parts = node.module.split(".") if node.module else []
            if node.level:
                d = file_dir
                for _ in range(node.level - 1):
                    d = posixpath.dirname(d)
                t = first(parts, d) if parts else None
                base = (posixpath.join(d, *parts) if parts else d)
                subs = [first([a.name], base) for a in node.names]
            else:
                t = first(parts) if parts else None
                subs = []
                if parts:
                    for a in node.names:
                        subs.append(first(parts + [a.name]))
            if t:
                found.append((t, node.lineno))
            for s in subs:
                if s:
                    found.append((s, node.lineno))
    out = []
    seen = set()
    for t, ln in found:
        if t != path and (t, ln) not in seen:
            seen.add((t, ln))
            out.append((t, ln))
    return out


# ---------------------------------------------------------------- write calls
def write_calls(path, source, fileset):
    """-> list of (output_path, lineno) for literal output paths on write-call lines."""
    out = []
    file_dir = posixpath.dirname(path)
    for no, line in enumerate(source.splitlines(), 1):
        if not (any(w in line for w in WRITE_WORDS) or ("open(" in line and WMODE_RE.search(line))):
            continue
        for m in OUT_LITERAL_RE.finditer(line):
            lit = m.group(1)
            for cand in (posixpath.normpath(lit), posixpath.normpath(posixpath.join(file_dir, lit))):
                if cand in fileset and cand != path:
                    out.append((cand, no))
                    break
    return out


# ---------------------------------------------------------------- run records
def read_run_record(raw_bytes, rel_path):
    try:
        d = json.loads(raw_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(d, dict):
        return None
    run_id = str(d.get("run_id") or posixpath.splitext(posixpath.basename(rel_path))[0])
    return {
        "run_id": run_id, "path": rel_path, "command": str(d.get("command") or ""),
        "started_at": d.get("started_at"), "script": d.get("script"),
        "inputs": [str(x) for x in d.get("inputs") or []], "outputs": [str(x) for x in d.get("outputs") or []],
    }


# ---------------------------------------------------------------- README provenance
_PAPER_COL = re.compile(r"paper|figure|fig|table|item", re.I)
_CODE_COL = re.compile(r"script|code|source|file", re.I)
_TICK = re.compile(r"`([^`]+\.(?:py|sh))`")


def _cells(line):
    s = line.strip()
    if not s.startswith("|"):
        return None
    s = s.strip("|")
    return [c.strip() for c in s.split("|")]


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def readme_tables(path, text, fileset):
    """-> list of rows {items:[(ref,slug)], scripts:[resolved paths], line, text}."""
    lines = text.splitlines()
    rows = []
    i = 0
    base = posixpath.dirname(path)
    by_base = {}
    for f in fileset:
        by_base.setdefault(posixpath.basename(f), []).append(f)
    while i + 1 < len(lines):
        head = _cells(lines[i])
        sep = _cells(lines[i + 1])
        if head and sep and all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in sep if c != "") and len(head) >= 2:
            pc = next((k for k, c in enumerate(head) if _PAPER_COL.search(c)), None)
            sc = next((k for k, c in enumerate(head) if k != pc and _CODE_COL.search(c)), None)
            j = i + 2
            if pc is not None and sc is not None:
                while j < len(lines) and _cells(lines[j]):
                    cells = _cells(lines[j])
                    if len(cells) > max(pc, sc):
                        paper_cell = cells[pc]
                        refs = [r.strip().strip("`") for r in paper_cell.split(",") if r.strip()]
                        scripts, first_dir = [], None
                        for tok in _TICK.findall(cells[sc]):
                            tok = tok.strip()
                            cands = [posixpath.normpath(posixpath.join(base, tok))]
                            if first_dir is not None:
                                cands.append(posixpath.normpath(posixpath.join(first_dir, tok)))
                            res = next((c for c in cands if c in fileset), None)
                            if res is None:
                                same = by_base.get(posixpath.basename(tok), [])
                                if len(same) == 1:
                                    res = same[0]
                            if res and res not in scripts:
                                scripts.append(res)
                                if first_dir is None:
                                    first_dir = posixpath.dirname(res)
                        if refs:
                            rows.append({"items": [(r, _slug(r)) for r in refs], "scripts": scripts,
                                         "line": j + 1, "text": lines[j].rstrip(),
                                         "hash": "sha256:" + hashlib.sha256(re.sub(r"\s+", " ", lines[j]).strip().encode("utf-8")).hexdigest()})
                    j += 1
            i = j
        else:
            i += 1
    return rows


# ---------------------------------------------------------------- config keys
def _scalar(v):
    v = v.strip()
    if " #" in v:
        v = v.split(" #", 1)[0].strip()
    return v.strip("'\"")


def config_keys(path, text):
    """-> {dotted_key: (value_str, line_no)} for scalars."""
    ext = posixpath.splitext(path)[1].lower()
    out = {}
    if ext in (".yaml", ".yml"):
        stack = []
        for no, raw in enumerate(text.splitlines(), 1):
            if not raw.strip() or raw.lstrip().startswith(("#", "-")):
                continue
            m = re.match(r"^(\s*)([A-Za-z0-9_.\-]+)\s*:\s*(.*)$", raw)
            if not m:
                continue
            ind, key, val = len(m.group(1)), m.group(2), m.group(3)
            while stack and stack[-1][0] >= ind:
                stack.pop()
            val = _scalar(val)
            if val == "" or val.startswith("#"):
                stack.append((ind, key))
            else:
                out[".".join([k for _, k in stack] + [key])] = (val, no)
    elif ext == ".json":
        try:
            d = json.loads(text)
        except ValueError:
            return out
        lines = text.splitlines()

        def line_of(k):
            for no, l in enumerate(lines, 1):
                if re.search(r'"%s"\s*:' % re.escape(k), l):
                    return no
            return 1

        def walk(o, pre):
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, pre + [str(k)])
            elif isinstance(o, (str, int, float, bool)) and pre:
                out[".".join(pre)] = (str(o), line_of(pre[-1]))
        walk(d, [])
    elif ext == ".toml":
        try:
            import tomllib
        except ImportError:
            return out
        try:
            d = tomllib.loads(text)
        except Exception:
            return out
        lines = text.splitlines()

        def line_of_t(k):
            for no, l in enumerate(lines, 1):
                if re.match(r"\s*%s\s*=" % re.escape(k), l):
                    return no
            return 1

        def walk_t(o, pre):
            if isinstance(o, dict):
                for k, v in o.items():
                    walk_t(v, pre + [str(k)])
            elif isinstance(o, (str, int, float, bool)) and pre:
                out[".".join(pre)] = (str(o), line_of_t(pre[-1]))
        walk_t(d, [])
    return out


def canonical_key(dotted):
    last = dotted.split(".")[-1].lower().replace("-", "_")
    return "learning_rate" if last == "lr" else last
