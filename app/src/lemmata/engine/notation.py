"""Notation: a glossary of the symbols a paper uses, what each one means, where meanings disagree, and which name in
the code each symbol corresponds to.

Rules only, no language model. Symbols come from the math in the LaTeX source; meanings from the sentences around them
("where $w$ is the window size", "the learning rate $\\eta$", "let $L$ denote ..."); code names from Python files
(parameters, variables, argparse options) and config files. Links to code are suggestions until the researcher accepts
them. Decisions live in .lemmata/notation.json.
"""
import ast
import bisect
import re

from . import code as codemod
from .errors import BadRequest, NotFound

SCHEMA = "lemmata.notation/1"
GREEK = set("alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu xi pi varpi rho varrho sigma "
            "varsigma tau upsilon phi varphi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega ell".split())
DECOR = {"mathbf": "mathbf", "boldsymbol": "mathbf", "bm": "mathbf", "mathcal": "mathcal", "mathbb": "mathbb", "mathfrak": "mathfrak",
         "mathsf": "mathsf", "mathscr": "mathscr", "hat": "hat", "widehat": "hat", "tilde": "tilde", "widetilde": "tilde", "bar": "bar",
         "overline": "bar", "vec": "vec", "dot": "dot", "ddot": "ddot"}
TEXTCMD = {"text", "mathrm", "textrm", "textbf", "textit", "operatorname", "mathit", "texttt", "textsc", "mbox", "label", "tag", "begin", "end",
           "ref", "eqref", "cite"}
MATH_RE = re.compile(r"\$\$(.+?)\$\$|(?<!\\)\$(.+?)(?<!\\)\$|\\\((.+?)\\\)|\\\[(.+?)\\\]|"
                     r"\\begin\{(equation|align|gather|multline|eqnarray|alignat|flalign|displaymath)\*?\}(.+?)\\end\{\5\*?\}", re.S)
TOKEN_RE = re.compile(r"\\([A-Za-z]+)|([A-Za-z]+)|(\{)|(\})|(_|\^)|(.)", re.S)
STOPW = set("the a an of in for to by with that which where and or at on from as when if then is are be we our this these those its "
            "each every any all some such given".split())
NP = r"((?:[a-z][a-z\-]*\s){0,6}?[a-z][a-z\-]*)"
END = r"(?=\s*(?:[,.;:)]|\u27e6|$)|\s+(?:and|that|which|where|with|is|are|to|at|on|by|from|as|when|if|such|used|we|in|for|while|so)\b)"
ABBR = {"lr": ["learning", "rate"], "num": ["number"], "n": ["number"], "dim": ["dimension"], "dims": ["dimension"], "thr": ["threshold"],
        "thresh": ["threshold"], "win": ["window"], "prob": ["probability"], "temp": ["temperature"], "coef": ["coefficient"],
        "coeff": ["coefficient"], "bs": ["batch", "size"], "len": ["length"], "std": ["standard", "deviation"], "eps": ["epsilon"],
        "lam": ["lambda"], "lmbda": ["lambda"], "lambd": ["lambda"], "wd": ["weight", "decay"], "max": ["maximum"], "min": ["minimum"],
        "seq": ["sequence"], "emb": ["embedding"], "embed": ["embedding"], "hid": ["hidden"], "iters": ["iteration"], "iter": ["iteration"],
        "epochs": ["epoch"], "steps": ["step"], "sz": ["size"], "cnt": ["count"], "freq": ["frequency"], "var": ["variance"]}
GENERIC = set("parameter hyperparameter variable constant term quantity vector matrix scalar function number index point element "
              "symbol factor coefficient".split())
MAX_PY, MAX_PY_BYTES = 400, 300 * 1024


# ------------------------------------------------------------------ macros
def _group(s, i):
    """s[i] == '{' -> (content, index after the matching '}')."""
    depth, j = 0, i
    while j < len(s):
        if s[j] == "{" and (j == 0 or s[j - 1] != "\\"):
            depth += 1
        elif s[j] == "}" and s[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)


def macros(lines):
    """\\newcommand / \\renewcommand / \\def / \\DeclareMathOperator -> {"\\name": "expansion"} (KaTeX's macro format)."""
    out = {}
    for ln in lines:
        c = ln.code
        for m in re.finditer(r"\\(?:re|provide)?newcommand\*?\s*\{?\s*(\\[A-Za-z]+)\s*\}?\s*(?:\[(\d)\])?\s*(?:\[[^\]]*\])?\s*(?=\{)", c):
            body, _ = _group(c, m.end())
            out[m.group(1)] = body
        for m in re.finditer(r"\\def\s*(\\[A-Za-z]+)\s*(?:#\d)*\s*(?=\{)", c):
            body, _ = _group(c, m.end())
            out[m.group(1)] = body
        for m in re.finditer(r"\\DeclareMathOperator(\*?)\s*\{\s*(\\[A-Za-z]+)\s*\}\s*(?=\{)", c):
            body, _ = _group(c, m.end())
            out[m.group(2)] = ("\\operatorname*{%s}" if m.group(1) else "\\operatorname{%s}") % body
        if len(out) > 400:
            break
    return {k: v[:300] for k, v in out.items() if len(v) <= 300}


# ------------------------------------------------------------------ symbols in a piece of math
def symbols(tex, user_macros=()):
    """-> [(key, start, end)] for the symbols in a math string. key is canonical TeX: x, \\alpha, \\mathcal{L}, \\hat{y}, L_{rec}."""
    toks = [(m.lastindex, m.group(m.lastindex), m.start(), m.end()) for m in TOKEN_RE.finditer(tex)]
    out, i, n = [], 0, len(toks)

    def skip_group(j):
        if j < n and toks[j][0] == 3:
            d = 0
            while j < n:
                d += toks[j][0] == 3
                d -= toks[j][0] == 4
                j += 1
                if d == 0:
                    break
        return j

    def atom(j):
        """One base symbol starting at token j -> (key, next j) or (None, j)."""
        if j >= n:
            return None, j
        kind, val = toks[j][0], toks[j][1]
        if kind == 1:
            if val in GREEK:
                return "\\" + val, j + 1
            if val in DECOR:
                k = j + 1
                if k < n and toks[k][0] == 3:
                    inner, k2 = atom(k + 1)
                    if inner and k2 < n and toks[k2][0] == 4:
                        return "\\%s{%s}" % (DECOR[val], inner), k2 + 1
                    return None, skip_group(k)
                inner, k2 = atom(k)
                return ("\\%s{%s}" % (DECOR[val], inner), k2) if inner else (None, k)
            if "\\" + val in user_macros and val not in TEXTCMD:
                return "\\" + val, j + 1
            return None, j
        if kind == 2:
            if len(val) == 1:
                return val, j + 1
            if val.isupper() and len(val) <= 4:
                return val, j + 1          # PA, TP, KL: one named quantity
        return None, j

    while i < n:
        kind, val, a, b = toks[i]
        if kind == 1 and val in TEXTCMD:
            i = skip_group(i + 1)
            continue
        if kind == 2 and len(val) == 2 and val.islower():      # "dx", "xy": two letters
            out += [(val[0], a, a + 1), (val[1], a + 1, b)]
            i += 1
            continue
        key, j = atom(i)
        if key is None:
            i = max(j, i + 1) if j > i else i + 1
            continue
        end = toks[j - 1][3]
        # a worded subscript is part of the name: L_{\text{rec}}, F_{PA}
        if j + 1 < n and toks[j][1] == "_":
            k = j + 1
            sub = None
            if toks[k][0] == 3:
                k2 = skip_group(k)
                inner = tex[toks[k][3]:toks[k2 - 1][2]]
                w = re.sub(r"\\(?:text|mathrm|textrm|mathit|operatorname)\s*", "", inner).replace("{", "").replace("}", "").strip()
                if re.fullmatch(r"[A-Za-z][A-Za-z\- ]{1,20}", w) and not (len(w) == 1):
                    sub, j, end = w, k2, toks[k2 - 1][3]
            elif toks[k][0] == 2 and len(toks[k][1]) >= 2 and toks[k][1].isupper():
                sub, j, end = toks[k][1], k + 1, toks[k][3]
            if sub:
                key = "%s_{\\mathrm{%s}}" % (key, sub)
        out.append((key, a, end))
        i = j
    return out


# ------------------------------------------------------------------ the paper
def _norm_meaning(t):
    w = [x for x in re.findall(r"[a-z][a-z\-]*", t.lower())]
    while w and w[0] in ("the", "a", "an", "our", "its", "each", "some", "given", "corresponding", "total", "overall"):
        w = w[1:]
    while w and w[-1] in STOPW:
        w = w[:-1]
    if w and len(w[-1]) > 3 and w[-1].endswith("s") and not w[-1].endswith("ss"):
        w[-1] = w[-1][:-1]
    return " ".join(w)


def _stem(x):
    x = re.sub(r"(?<=[a-z]{3})iz(?=[eai])", "is", x)      # regularization = regularisation (but not "size")
    return x[:-1] if len(x) > 3 and x.endswith("s") and not x.endswith("ss") else x


def _content(t):
    return {_stem(x) for x in t.split() if x not in STOPW and len(x) > 1}


def _same(a, b):
    """Two meaning phrases that say the same thing: equal content words, or one contains the other ("segment length", "length of an anomaly segment")."""
    A, B = _content(a), _content(b)
    if not A or not B:
        return False
    small, big = (A, B) if len(A) <= len(B) else (B, A)
    return A == B or (len(small) >= 2 and small <= big)


def scan_paper(P):
    """-> (symbols: {key: {...}}, macros)"""
    lines = P.lines
    mac = macros(lines)
    start = next((i for i, l in enumerate(lines) if "\\begin{document}" in l.code), -1) + 1
    body = lines[start:]
    offs, pos = [], 0
    for l in body:
        offs.append(pos)
        pos += len(l.code) + 1
    text = "\n".join(l.code for l in body)

    def loc(off):
        i = bisect.bisect_right(offs, off) - 1
        l = body[max(i, 0)]
        return {"path": l.path, "line": l.no}, start + max(i, 0)

    app = P.appendix_idx
    syms = {}

    def sym(key):
        return syms.setdefault(key, {"key": key, "uses": 0, "first": None, "meanings": [], "values": [], "lines": set(), "appendix_uses": 0})

    spans = []          # (start, end, inner, [symbols])
    for m in MATH_RE.finditer(text):
        inner = next(g for g in (m.group(1), m.group(2), m.group(3), m.group(4), m.group(6)) if g is not None)
        ss = symbols(inner, mac)
        spans.append((m.start(), m.end(), inner, ss))
        l, idx = loc(m.start())
        for key, a, b in ss:
            s = sym(key)
            s["uses"] += 1
            s["lines"].add((l["path"], l["line"]))
            s["first"] = s["first"] or l
            if app is not None and idx > app:
                s["appendix_uses"] += 1
        # "w = 100": a value stated in the paper
        for vm in re.finditer(r"(?:^|[,;(\s])\s*([^=<>,;]{1,30}?)\s*=\s*(-?\d+(?:\.\d+)?(?:e-?\d+)?)\s*(\\?%)?(?=\s*(?:$|[,;.)\s]|\\))", inner):
            ks = symbols(vm.group(1), mac)
            if len(ks) == 1 and not re.search(r"[+\-*/]|\\frac|\\sum", vm.group(1)):
                sym(ks[0][0])["values"].append({"value": vm.group(2) + ("%" if vm.group(3) else ""), "loc": l})
    # prose with each math span replaced by a marker; single-symbol spans are what definitions attach to
    parts, last, single = [], 0, {}
    for i, (a, b, inner, ss) in enumerate(spans):
        parts.append(text[last:a])
        keys = {k for k, _, _ in ss}
        if len(keys) == 1 and len(re.sub(r"[\s{}_^]|\\[A-Za-z]+|[A-Za-z0-9,]", "", inner)) <= 2:
            single[i] = next(iter(keys))
        parts.append("\u27e6%d\u27e7" % i)
        last = b
    parts.append(text[last:])
    prose = "".join(parts)
    prose = re.sub(r"\\(?:emph|textit|textbf|textsc)\{([^{}]*)\}", r"\1", prose)
    prose = re.sub(r"\\(?:cite[a-z]*|ref|cref|Cref|eqref|label)\*?(?:\[[^\]]*\])*\{[^}]*\}", " ", prose).replace("~", " ")
    prose_l = re.sub(r"[ \t]+", " ", prose.replace("\n", " ")).lower()
    # offsets in prose_l are not offsets in text: locate a marker's span through its index
    M = r"\u27e6(\d+)\u27e7"
    pats = [
        ("is", re.compile(M + r"\s+(?:is|are|denotes?|represents?|stands for|refers to|indicates?|be)\s+((?:the|a|an|our)\s+)?" + NP + END)),
        ("of-size", re.compile(r"\b([a-z][a-z\-]*)\s+of\s+(size|length|dimension|width|rate|radius|order|degree)\s+" + M)),
        ("let", re.compile(r"(?:let|denote|define)\s+(?:by\s+)?" + M + r"\s+(?:be|denote|represent|as)\s+(?:the|a|an)?\s*" + NP + END)),
        ("denoted", re.compile(r"(?:the|a|an)\s+" + NP + r"\s*,?\s*(?:is\s+|are\s+)?(?:denoted|written|represented)\s+(?:by|as)\s+" + M)),
        ("denote-by", re.compile(r"denote\s+(?:the|a|an)\s+" + NP + r"\s+(?:by|as)\s+" + M)),
        ("apposition", re.compile(r"\b(?:the|a|an|each|every|with|of|per|given)\s+((?:[a-z][a-z\-]*\s){0,3}?[a-z][a-z\-]*)\s+" + M)),
    ]
    for how, rx in pats:
        for m in rx.finditer(prose_l):
            if how == "is":
                gi, phrase = m.group(1), m.group(3)
                if not m.group(2) and (len(phrase.split()) < 2 or re.search(r"(?:ed|ing|ly)$", phrase.split()[0])):
                    continue                      # "is fixed", "is set to": a statement, not a definition
            elif how == "of-size":
                gi, phrase = m.group(3), m.group(1) + " " + m.group(2)
            else:
                gi, phrase = (m.group(1), m.group(2)) if how == "let" else (m.group(2), m.group(1))
            i = int(gi)
            if i not in single:
                continue
            words = phrase.split()
            if how == "apposition":
                while words and words[0] in STOPW:
                    words = words[1:]
                if not words or words[-1] in STOPW or any(w in STOPW for w in words) or words[-1] in ("where", "value", "values", "case", "equation") \
                        or (len(words) == 1 and words[0] in GENERIC) \
                        or re.search(r"(?:i[sz]es|ifies|uses|takes|gives|returns|computes|outputs|predicts|learns|maps|has|have|let|set)$", words[-1]):
                    continue
            mean = _norm_meaning(" ".join(words))
            if not mean or len(mean) < 3 or mean in ("set", "following", "same", "one", "function of", "defined", "then", "not", "also", "given"):
                continue
            l, idx = loc(spans[i][0])
            s = sym(single[i])
            if not any(x["text"] == mean and x["loc"] == l for x in s["meanings"]):
                s["meanings"].append({"text": mean, "loc": l, "how": how, "in_appendix": app is not None and idx > app, "_at": spans[i][0]})
    for s in syms.values():
        s["meanings"].sort(key=lambda x: x.pop("_at"))
    return syms, mac


# ------------------------------------------------------------------ the code
def _tokens(name):
    parts = re.findall(r"[A-Za-z][a-z]*|[A-Z]+(?![a-z])|\d+", name.replace("-", "_"))
    out = []
    for p in parts:
        p = p.lower()
        out += ABBR.get(p, [p])
    return [_stem(x) for x in out]


def _const(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return repr(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)):
        return "-" + repr(node.operand.value)
    return None


def scan_code(nodes, trees):
    """Names in the code a symbol could correspond to -> [{id, name, kind, repo, path, line, value, tokens}]."""
    out, seen, n_py = [], set(), 0

    def add(name, kind, repo, path, line, value=None):
        if not name or name.startswith("__") or name in ("self", "cls", "args", "kwargs"):
            return
        iid = "%s:%s:%s" % (repo, path, name)
        if iid in seen:
            if value is not None:
                for o in out:
                    if o["id"] == iid and o["value"] is None:
                        o["value"] = value
            return
        seen.add(iid)
        out.append({"id": iid, "name": name, "kind": kind, "repo": repo, "path": path, "line": line, "value": value, "tokens": _tokens(name)})

    for nid, n in sorted(nodes.items()):
        if n["kind"] not in ("code", "config") or n["repo"] not in trees:
            continue
        path = n["loc"]["path"]
        tr = trees[n["repo"]]
        try:
            if tr.size(path) > MAX_PY_BYTES:
                continue
            src = tr.read(path).decode("utf-8", "replace")
        except Exception:
            continue
        if n["kind"] == "config":
            for dotted, (val, ln) in codemod.config_keys(path, src).items():
                add(dotted.split(".")[-1], "setting", n["repo"], path, ln, val if re.fullmatch(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", str(val)) else None)
            continue
        if not path.endswith(".py") or n_py >= MAX_PY:
            continue
        n_py += 1
        try:
            mod = ast.parse(src)
        except (SyntaxError, ValueError, RecursionError):
            continue
        for node in ast.walk(mod):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                add(node.name, "function", n["repo"], path, node.lineno)
                a = node.args
                pos = a.posonlyargs + a.args
                defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
                for arg, d in list(zip(pos, defaults)) + list(zip(a.kwonlyargs, a.kw_defaults)):
                    add(arg.arg, "parameter", n["repo"], path, arg.lineno, _const(d) if d is not None else None)
            elif isinstance(node, ast.ClassDef):
                add(node.name, "class", n["repo"], path, node.lineno)
            elif isinstance(node, ast.Assign) and len(node.targets) == 1:
                t = node.targets[0]
                if isinstance(t, ast.Name):
                    add(t.id, "variable", n["repo"], path, node.lineno, _const(node.value))
                elif isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                    add(t.attr, "variable", n["repo"], path, node.lineno, _const(node.value))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
                flag = next((x.value for x in node.args if isinstance(x, ast.Constant) and isinstance(x.value, str) and x.value.startswith("--")), None)
                if flag:
                    dflt = next((_const(k.value) for k in node.keywords if k.arg == "default"), None)
                    add(flag[2:].replace("-", "_"), "option", n["repo"], path, node.lineno, dflt)
        if len(out) > 20000:
            break
    return out


KIND_RANK = {"setting": 0, "option": 1, "parameter": 2, "variable": 3, "function": 4, "class": 5}


def _candidates(key, meaning, idents):
    base = re.sub(r"\\(?:mathbf|mathcal|mathbb|mathfrak|mathsf|mathscr|hat|tilde|bar|vec|dot|ddot)\{(.+)\}", r"\1", key.split("_{")[0])
    greek = base[1:].lower() if base.startswith("\\") else None
    sub = re.search(r"_\{\\mathrm\{(.+?)\}\}", key)
    M = _content(meaning) if meaning else set()
    out = []
    for it in idents:
        T = set(it["tokens"])
        score = 0.0
        if M and T:
            T = {next((m_ for m_ in M if len(t) >= 3 and m_.startswith(t)), t) for t in T}     # "seg" ~ "segment", "reg" ~ "regularisation"
            inter = M & T
            if inter:
                score = len(inter) / len(M | T)
                if T <= M and len(T) >= 2 or T == M:
                    score = max(score, 0.9 if T == M else 0.7)
        if greek and (it["tokens"] == [greek] or it["name"].lower() in (greek, greek + "_")):
            score = max(score, 0.85)
        if sub and sub.group(1).lower() in it["name"].lower() and len(sub.group(1)) >= 2 and base.lower().strip("\\") and M & T:
            score = max(score, 0.7)
        if not greek and len(base) == 1 and it["name"] == base and it["kind"] in ("parameter", "variable", "setting", "option"):
            score = max(score, 0.45 if not M else 0.5)
        if score >= 0.45:
            out.append((score, it))
    out.sort(key=lambda x: (-x[0], KIND_RANK.get(x[1]["kind"], 9), x[1]["path"], x[1]["line"] or 0))
    best, names = [], set()
    for sc, it in out:
        if it["name"] in names:
            continue
        names.add(it["name"])
        best.append((sc, it))
        if len(best) >= 3:
            break
    return best


# ------------------------------------------------------------------ the glossary
def _num(v):
    try:
        return float(str(v).rstrip("%"))
    except ValueError:
        return None


def build(P, nodes, trees, store, github=None):
    store = store or {}
    ents = store.get("entries", {})
    if P is None:
        return {"schema": SCHEMA, "has_paper": False, "symbols": [], "issues": [], "macros": {}, "counts": {"symbols": 0, "defined": 0, "issues": 0, "linked": 0}}
    syms, mac = scan_paper(P)
    idents = scan_code(nodes, trees)
    by_id = {i["id"]: i for i in idents}
    github = github or {}
    out, issues = [], []
    by_meaning = {}
    for key, s in syms.items():
        e = ents.get(key, {})
        ms = s["meanings"]
        counts = {}                       # the meaning stated most often; on a tie, the one stated first
        for m in ms:
            hit = next((t for t in counts if _same(t, m["text"])), m["text"])
            counts[hit] = counts.get(hit, 0) + 1
        auto = max(counts, key=lambda t: (counts[t], -min(i for i, m in enumerate(ms) if _same(m["text"], t)))) if counts else None
        meaning = e.get("meaning") or auto
        if not ms and s["uses"] < 3 and not e:
            continue                                  # a symbol used once or twice with no stated meaning is noise
        item = {"key": key, "tex": key, "meaning": meaning, "meaning_by": "you" if e.get("meaning") else ("paper" if auto else None),
                "meanings": ms[:12], "uses": s["uses"], "first": s["first"], "lines": len(s["lines"]), "appendix_only": s["uses"] == s["appendix_uses"] and s["uses"] > 0,
                "values": s["values"][:6], "ignored": bool(e.get("ignore")), "code": [], "issues": []}
        # one symbol, two meanings
        distinct = []
        for m in ms:
            if not any(_same(m["text"], d["text"]) or _content(m["text"]) & _content(d["text"]) for d in distinct):
                distinct.append(m)
        if len(distinct) > 1 and not e.get("meaning") and not item["ignored"]:
            item["issues"].append({"kind": "conflict", "meanings": distinct[:4]})
        # code
        drop = set(e.get("unlinks", []))
        have = set()
        for iid in e.get("links", []):
            if iid in by_id:
                have.add(iid)
                item["code"].append(dict(by_id[iid], how="you", score=1.0))
        for sc, it in _candidates(key, meaning, idents):
            if it["id"] not in have and it["id"] not in drop and it["name"] not in {c["name"] for c in item["code"]}:
                item["code"].append(dict(it, how="suggested", score=round(sc, 2)))
        for c in item["code"]:
            c.pop("tokens", None)
            c["github"] = github[c["repo"]] + c["path"] + ("#L%d" % c["line"] if c["line"] else "") if c["repo"] in github else None
            # the paper states a value and the code has another one
            if (c["how"] == "you" or c["score"] >= 0.7) and c["value"] is not None:
                for v in item["values"]:
                    a, b = _num(v["value"]), _num(c["value"])
                    if a is not None and b is not None and abs(a - b) > 1e-9 * max(1.0, abs(a), abs(b)) and not item["ignored"]:
                        item["issues"].append({"kind": "value", "confirmed": c["how"] == "you", "paper": v, "code": {k: c[k] for k in ("name", "path", "line", "value", "github")}})
                        break
        if meaning and not item["ignored"]:
            by_meaning.setdefault(meaning, []).append(item)
        out.append(item)
    # one meaning, two symbols
    defined = [i for items in by_meaning.values() for i in items]
    for i in defined:
        others = [o["key"] for o in defined if o is not i and _same(i["meaning"], o["meaning"]) and len(_content(i["meaning"])) >= 2
                  and re.sub(r"_\{.*$", "", o["key"]) != re.sub(r"_\{.*$", "", i["key"])]
        if others:
            i["issues"].append({"kind": "synonym", "meaning": i["meaning"], "others": others})
    # the same letter plain and decorated (x and \mathbf{x})
    keys = {i["key"] for i in out}
    for i in out:
        m = re.fullmatch(r"\\(mathbf|hat|tilde|bar|vec)\{(.+)\}", i["key"])
        if m and m.group(1) == "mathbf" and m.group(2) in keys and not i["ignored"]:
            i["issues"].append({"kind": "variant", "others": [m.group(2)]})
    for i in out:
        for x in i["issues"]:
            issues.append(dict(x, symbol=i["key"]))
    order = {"conflict": 0, "value": 1, "synonym": 2, "variant": 3}
    issues.sort(key=lambda x: (order[x["kind"]], x["symbol"]))
    out.sort(key=lambda i: (not i["issues"], i["meaning"] is None, -(i["uses"])))
    return {"schema": SCHEMA, "has_paper": True, "symbols": out, "issues": issues, "macros": mac,
            "counts": {"symbols": len(out), "defined": sum(1 for i in out if i["meaning"]), "issues": len(issues),
                       "linked": sum(1 for i in out if any(c["how"] == "you" for c in i["code"])),
                       "suggested": sum(1 for i in out if any(c["how"] == "suggested" for c in i["code"]) and not any(c["how"] == "you" for c in i["code"]))},
            "code_names": len(idents)}


# ------------------------------------------------------------------ decisions
def load(hub):
    d = hub.read_json("notation.json", None)
    if not isinstance(d, dict):
        d = {}
    d.setdefault("schema", SCHEMA)
    d.setdefault("entries", {})
    return d


def decide(store, known, key, meaning=None, ignore=None, link=None, unlink=None):
    if key not in known:
        raise NotFound("unknown symbol %r" % key)
    e = store["entries"].setdefault(key, {})
    if meaning is not None:
        if not isinstance(meaning, str) or len(meaning) > 200:
            raise BadRequest("meaning must be at most 200 characters")
        if meaning.strip():
            e["meaning"] = meaning.strip()
        else:
            e.pop("meaning", None)
    if ignore is not None:
        e["ignore"] = bool(ignore)
    for val, add_to, rm_from in ((link, "links", "unlinks"), (unlink, "unlinks", "links")):
        if val is not None:
            if not isinstance(val, str) or not val or len(val) > 500:
                raise BadRequest("bad code name")
            if val in e.get(rm_from, []):
                e[rm_from].remove(val)
            if val not in e.setdefault(add_to, []):
                e[add_to].append(val)
    return e
