"""Regex-level LaTeX reader: flatten \\input, units + ownership, labels, refs, cites, markers, numbers."""
import hashlib
import posixpath
import re
from collections import namedtuple

Line = namedtuple("Line", "path no raw code comment")

FLOAT_ENVS = {"figure", "figure*", "table", "table*"}
EQ_ENVS = {"equation", "equation*", "align", "align*", "gather", "gather*", "multline", "multline*", "eqnarray", "eqnarray*"}
ENV_RE = re.compile(r"\\(begin|end)\{([A-Za-z*]+)\}")
INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
SEC_RE = re.compile(r"\\(sub)?section(\*?)\s*(?:\[[^\]]*\])?\s*\{")
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
REF_RE = re.compile(r"\\(?:ref|cref|Cref|autoref|eqref|pageref|vref|Vref)\*?\{([^}]*)\}")
CITE_RE = re.compile(r"\\(?:cite|citep|citet|citeauthor|citeyear|nocite|citealp|citealt|parencite|textcite)\*?(?:\[[^\]]*\])*\{([^}]*)\}")
NOCITE_RE = re.compile(r"\\nocite\{([^}]*)\}")
GRAPHICS_RE = re.compile(r"\\includegraphics\*?(?:\[[^\]]*\])?\{([^}]+)\}")
MARKER_RE = re.compile(r"^\s*(generated-by|source)\s*:\s*(.+?)\s*$", re.I)
RQ_RE = re.compile(r"\bRQ\s?(\d+)\b")
UNOWNED_RE = re.compile(r"^\s*\\(?:end\{document\}|begin\{document\}|bibliography\{|bibliographystyle\{|appendix\b|maketitle\b)")
APPENDIX_RE = re.compile(r"\\appendix\b")
IMG_EXT = ["", ".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg"]

HP_ALIASES = {
    "learning_rate": r"learning[ _-]?rate|lr",
    "batch_size": r"batch[ _-]?size",
    "epochs": r"epochs",
    "weight_decay": r"weight[ _-]?decay",
    "dropout": r"dropout",
    "warmup_steps": r"warm-?up[ _-]steps",
    "optimizer": r"optimizer",
    "seed": r"seed",
}
HP_RE = {k: re.compile(r"(?<![A-Za-z\\])(?:%s)(?![A-Za-z])" % v, re.I) for k, v in HP_ALIASES.items()}
OPT_RE = re.compile(r"\b(AdamW|Adam|SGD|RMSprop|Adagrad)\b", re.I)
NUM_RE = re.compile(r"(?P<m>\d+(?:\.\d+)?|\.\d+)(?:\s*(?:\\times|\\cdot|×)\s*10\^\{?\s*(?P<e1>[-+\u2212]?\d+)\s*\}?|(?P<e2>[eE][-+]?\d+))?")
NUM_STRIP_RE = re.compile(
    r"\\(?:ref|cref|Cref|eqref|autoref|label|cite\w*|input|include|includegraphics|bibliography\w*)\*?(?:\[[^\]]*\])*\{[^}]*\}"
    r"|\d*\.?\d+\s*\\(?:linewidth|textwidth|columnwidth|textheight|hsize|vsize)\b|\d*\.?\d+\s*(?:pt|cm|mm|em|ex|in)\b")
TABSPEC_RE = re.compile(r"\\begin\{(?:tabular|tabularx|array|longtable|tabular\*)\}(?:\[[^\]]*\])?\{[^}]*\}")
DECIMAL_RE = re.compile(r"(?<![\w.])(\d+\.\d+)(?:\\?%)?(?![\w.])")


def strip_comment(line):
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == "\\":
            i += 2
            continue
        if c == "%":
            return line[:i], line[i + 1:]
        i += 1
    return line, None


def norm_hash(codes):
    out = []
    for c in codes:
        c = re.sub(r"\s+", " ", c).strip()
        if c:
            out.append(c)
    return "sha256:" + hashlib.sha256("\n".join(out).encode("utf-8")).hexdigest()


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def balanced(text, start):
    """text[start] == '{' -> (inner, end_index) with brace matching."""
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i
        i += 1
    return text[start + 1:], len(text)


def parse_number(s):
    """'3\\times10^{-4}' / '3e-4' / '0.0003' -> float or None."""
    m = NUM_RE.search(s)
    if not m:
        return None
    v = float(m.group("m"))
    e = m.group("e1") or m.group("e2")
    if e:
        e = e.replace("\u2212", "-")
        e = e.lstrip("eE")
        v *= 10 ** int(e)
    return v


def fmt_number(v):
    if v == 0:
        return "0"
    if abs(v) < 0.01:
        mant, exp = ("%.6e" % v).split("e")
        mant = mant.rstrip("0").rstrip(".")
        return "%se%d" % (mant, int(exp))
    return "%g" % v


def alias_value(name, code, end):
    """First value after the alias end on the same line: float, optimizer word, or None."""
    rest = code[end:]
    if name == "optimizer":
        m = OPT_RE.search(rest)
        return m.group(1) if m else None
    m = NUM_RE.search(rest)
    if not m:
        return None
    return parse_number(rest[m.start():])


class Paper:
    pass


def _resolve_input(tree, base_dir, cur_dir, name):
    for d in (base_dir, cur_dir):
        for cand in (name, name + ".tex"):
            p = posixpath.normpath(posixpath.join(d, cand))
            if tree.has(p) and p.endswith(".tex"):
                return p
    return None


def _flatten(tree, path, base_dir, out, state, warnings, depth=0, stack=()):
    data = tree.read(path)
    if data is None:
        return
    text = data.decode("utf-8", "replace")
    raws = re.split(r"\r\n|\n|\r", text)
    if raws and raws[-1] == "":
        raws.pop()
    cur_dir = posixpath.dirname(path)
    for no, raw in enumerate(raws, 1):
        code, comment = strip_comment(raw)
        in_float_before = state["float"] > 0
        for m in ENV_RE.finditer(code):
            if m.group(2) in FLOAT_ENVS:
                state["float"] += 1 if m.group(1) == "begin" else -1
                state["float"] = max(state["float"], 0)
        m = INPUT_RE.search(code)
        if m and not (in_float_before or state["float"] > 0):
            target = _resolve_input(tree, base_dir, cur_dir, m.group(1).strip())
            if target is None or target in stack or depth > 8:
                warnings.append({"code": "input_missing", "message": "\\input{%s} not found" % m.group(1),
                                 "evidence": {"repo": tree.repo_id, "path": path, "line": no, "text": raw.rstrip()[:300], "role": "input", "page": None}})
                out.append(Line(path, no, raw, code, comment))
                continue
            _flatten(tree, target, base_dir, out, state, warnings, depth + 1, stack + (path,))
            rest = code[:m.start()] + code[m.end():]
            if rest.strip():
                out.append(Line(path, no, rest, rest, comment))
            continue
        out.append(Line(path, no, raw, code, comment))


def _matching_spans(lines):
    spans = []
    stack = []
    for idx, ln in enumerate(lines):
        for m in ENV_RE.finditer(ln.code):
            name = m.group(2)
            if m.group(1) == "begin":
                stack.append((name, idx))
            else:
                for k in range(len(stack) - 1, -1, -1):
                    if stack[k][0] == name:
                        spans.append((name, stack[k][1], idx))
                        del stack[k:]
                        break
    return spans


def parse_paper(tree, main_path, repo_id):
    P = Paper()
    P.repo = repo_id
    P.main = main_path
    P.warnings = []
    lines = []
    _flatten(tree, main_path, posixpath.dirname(main_path), lines, {"float": 0}, P.warnings)
    P.lines = lines
    n = len(lines)
    P.appendix_idx = next((i for i, l in enumerate(lines) if APPENDIX_RE.search(l.code)), None)
    spans = _matching_spans(lines)

    owner = [None] * n          # unit key per line
    units = []                  # dicts

    def new_unit(**kw):
        kw["key"] = len(units)
        kw.setdefault("owned", [])
        kw.setdefault("parent", None)
        kw.setdefault("label", None)
        units.append(kw)
        return kw

    # thesis
    abstract = next(((b, e) for (nm, b, e) in spans if nm == "abstract"), None)
    thesis = None
    if abstract:
        thesis = new_unit(kind="thesis", begin=abstract[0], end=abstract[1])

    # sections (sequential)
    cur_sec = cur_sub = None
    base_owner = [None] * n
    for idx, ln in enumerate(lines):
        m = SEC_RE.search(ln.code)
        if m and not (abstract and abstract[0] <= idx <= abstract[1]):
            title, _ = balanced(ln.code, m.end() - 1)
            title = re.sub(r"\s+", " ", re.sub(r"\\[A-Za-z]+\s*", "", title).replace("{", "").replace("}", "")).strip()
            level = 2 if m.group(1) else 1
            u = new_unit(kind="section", begin=idx, level=level, starred=bool(m.group(2)), title=title,
                         in_appendix=P.appendix_idx is not None and idx > P.appendix_idx)
            if level == 1:
                cur_sec, cur_sub = u, None
                u["parent"] = thesis["key"] if thesis else None
            else:
                cur_sub = u
                u["parent"] = cur_sec["key"] if cur_sec else (thesis["key"] if thesis else None)
            base_owner[idx] = u["key"]
        else:
            cur = cur_sub or cur_sec
            base_owner[idx] = cur["key"] if cur else None
    for idx in range(n):
        owner[idx] = None if UNOWNED_RE.match(lines[idx].code) else base_owner[idx]

    # floats, equations
    overlays = []
    for (nm, b, e) in spans:
        if nm in FLOAT_ENVS:
            u = new_unit(kind="figure" if nm.startswith("figure") else "table", env=nm, begin=b, end=e,
                         parent=base_owner[b], in_appendix=P.appendix_idx is not None and b > P.appendix_idx)
            overlays.append((e - b, u))
        elif nm in EQ_ENVS and any(LABEL_RE.search(lines[i].code) for i in range(b, e + 1)):
            u = new_unit(kind="equation", env=nm, begin=b, end=e, parent=base_owner[b],
                         in_appendix=P.appendix_idx is not None and b > P.appendix_idx)
            overlays.append((e - b, u))
    if thesis:
        overlays.append((thesis["end"] - thesis["begin"] + 10 ** 6, thesis))  # applied first (outermost)
    for _, u in sorted(overlays, key=lambda t: -t[0]):
        for i in range(u["begin"], u["end"] + 1):
            owner[i] = u["key"]
    for idx, k in enumerate(owner):
        if k is not None:
            units[k]["owned"].append(idx)
    P.owner = owner
    P.units = units

    # labels
    P.labels = {}
    P.label_lines = {}
    for idx, ln in enumerate(lines):
        for m in LABEL_RE.finditer(ln.code):
            lab = m.group(1).strip()
            k = owner[idx]
            if lab in P.labels:
                P.warnings.append({"code": "duplicate_label", "message": "label %s defined twice" % lab, "evidence": P.ev(idx, "label")})
                continue
            P.labels[lab] = (k, idx)
            if k is not None and units[k]["label"] is None:
                units[k]["label"] = lab

    # ids
    used = set()
    ordinal = {}
    secslug = {}

    def uniq(base):
        cand, c = base, 1
        while cand in used:
            c += 1
            cand = "%s~%d" % (base, c)
        used.add(cand)
        return cand

    for u in sorted(units, key=lambda x: x["begin"]):
        k = u["kind"]
        if k == "thesis":
            u["id"] = uniq("thesis")
        elif u.get("label"):
            u["id"] = uniq("tex:" + u["label"])
        elif k == "section":
            u["id"] = uniq("tex:section@" + slugify(u["title"]))
        elif k in ("figure", "table"):
            path = lines[u["begin"]].path
            ordinal[(k, path)] = ordinal.get((k, path), 0) + 1
            u["id"] = uniq("tex:%s@%s#%d" % (k, path, ordinal[(k, path)]))
        else:
            u["id"] = uniq("tex:equation@%s#%d" % (lines[u["begin"]].path, u["begin"] + 1))

    # numbering, names, details
    fig = tab = eq = 0
    msec = asec = 0
    last_top = None
    for u in sorted(units, key=lambda x: x["begin"]):
        if u["kind"] != "section":
            continue
        if u["level"] == 1:
            if u["starred"]:
                u["number"] = None
            elif u["in_appendix"]:
                asec += 1
                u["number"] = chr(64 + asec)
            else:
                msec += 1
                u["number"] = str(msec)
            last_top = u
            subc = 0
        else:
            if u["starred"] or last_top is None or last_top.get("number") is None:
                u["number"] = None
            else:
                subc += 1
                u["number"] = "%s.%d" % (last_top["number"], subc)
    for u in sorted(units, key=lambda x: x["begin"]):
        k = u["kind"]
        if k == "figure":
            fig += 1
            u["number"] = str(fig)
        elif k == "table":
            tab += 1
            u["number"] = str(tab)
        elif k == "equation":
            if not u["env"].endswith("*"):
                eq += 1
                u["number"] = str(eq)
            else:
                u["number"] = None
    for u in units:
        k = u["kind"]
        body = "\n".join(lines[i].code for i in range(u["begin"], u["end"] + 1)) if "end" in u else ""
        if k == "thesis":
            inner = " ".join(lines[i].code.strip() for i in range(u["begin"] + 1, u["end"]))
            u["name"], u["detail"] = "Thesis", "Abstract"
            u["text"] = re.sub(r"\s+", " ", inner).strip()[:200]
        elif k == "section":
            num = u.get("number")
            if num is None:
                u["name"] = u["title"]
            elif u["in_appendix"]:
                u["name"] = "App. %s %s" % (num, u["title"])
            else:
                u["name"] = "\u00a7%s %s" % (num, u["title"])
            u["detail"] = u["title"]
        elif k in ("figure", "table"):
            u["name"] = ("Fig. " if k == "figure" else "Table ") + u["number"]
            cap = ""
            i = body.find("\\caption")
            if i >= 0:
                j = body.find("{", i)
                if j >= 0:
                    cap = balanced(body, j)[0]
            cap = re.sub(r"\\label\{[^}]*\}", "", cap)
            u["caption"] = re.sub(r"\s+", " ", cap).strip()
            u["detail"] = u["caption"][:120]
        else:
            u["name"] = "Eq. " + u["number"] if u.get("number") else "Equation"
            u["detail"] = u.get("label") or ""
        codes = [lines[i].code for i in u["owned"]]
        u["hash"] = norm_hash(codes)
        u["end_line"] = max([lines[i].no for i in u["owned"] if lines[i].path == lines[u["begin"]].path] or [lines[u["begin"]].no])

    P.by_id = {u["id"]: u for u in units}

    # refs, cites
    P.refs, P.cites, P.nocite_all = [], [], False
    for idx, ln in enumerate(lines):
        for m in REF_RE.finditer(ln.code):
            for lab in m.group(1).split(","):
                if lab.strip():
                    P.refs.append((lab.strip(), idx))
        for m in CITE_RE.finditer(ln.code):
            is_no = ln.code[m.start():m.start() + 7] == "\\nocite"
            for key in m.group(1).split(","):
                key = key.strip()
                if not key:
                    continue
                if is_no and key == "*":
                    P.nocite_all = True
                elif key != "*":
                    P.cites.append((key, idx))

    # includes
    P.includes = []
    for idx, ln in enumerate(lines):
        for m in GRAPHICS_RE.finditer(ln.code):
            P.includes.append(("graphics", m.group(1).strip(), idx))
        m = INPUT_RE.search(ln.code)
        k = owner[idx]
        if m and k is not None and units[k]["kind"] in ("figure", "table"):
            P.includes.append(("input", m.group(1).strip(), idx))

    # markers
    P.markers = []
    for idx, ln in enumerate(lines):
        if ln.comment is None:
            continue
        m = MARKER_RE.match(ln.comment)
        if not m:
            continue
        k = owner[idx]
        if k is None or units[k]["kind"] not in ("figure", "table", "equation"):
            for j in range(idx + 1, min(idx + 4, n)):
                kk = owner[j]
                if kk is not None and units[kk]["kind"] in ("figure", "table", "equation") and units[kk]["begin"] == j:
                    k = kk
                    break
        if k is None:
            continue
        toks = [t.strip() for t in m.group(2).split(",") if t.strip()]
        P.markers.append((m.group(1).lower(), toks, idx, k))
    for kind, toks, idx, k in P.markers:
        if kind == "generated-by" and any(t.lower() == "manual" for t in toks):
            units[k]["manual"] = True

    # RQs
    P.rqs = {}
    P.rq_mentions = {}
    for idx, ln in enumerate(lines):
        for m in RQ_RE.finditer(ln.code):
            name = "RQ" + m.group(1)
            P.rqs.setdefault(name, idx)
            P.rq_mentions.setdefault(name, set())
            if owner[idx] is not None:
                P.rq_mentions[name].add(owner[idx])

    # hyperparameter mentions
    P.hparams = []   # (name, idx, value)
    for idx, ln in enumerate(lines):
        if owner[idx] is None:
            continue
        scan = TABSPEC_RE.sub(lambda m: " " * len(m.group(0)), ln.code)
        for name, rx in HP_RE.items():
            for m in rx.finditer(scan):
                P.hparams.append((name, idx, alias_value(name, scan, m.end())))
    hp_lines = {h[1] for h in P.hparams}

    # numbers
    math_idx = set()
    for (nm, b, e) in spans:
        if nm in EQ_ENVS:
            math_idx.update(range(b, e + 1))
    P.numbers = []
    for idx, ln in enumerate(lines):
        if owner[idx] is None or idx in math_idx or idx in hp_lines or "\\[" in ln.code or "$$" in ln.code:
            continue
        code = NUM_STRIP_RE.sub(" ", ln.code)
        for m in DECIMAL_RE.finditer(code):
            P.numbers.append((m.group(1), idx))
    return P


def _ev(self, idx, role):
    ln = self.lines[idx]
    return {"repo": self.repo, "path": ln.path, "line": ln.no, "text": ln.raw.rstrip()[:300], "role": role, "page": None}


Paper.ev = _ev


def resolve_graphics(tree, main_path, raw):
    base = posixpath.dirname(main_path)
    for ext in IMG_EXT:
        p = posixpath.normpath(posixpath.join(base, raw + ext))
        if tree.has(p):
            return p
    return None
