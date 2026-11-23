"""Survey papers (S37, ADR-013): when one sentence changes, every other place in the paper that says the same thing.

A survey has no experiments. Its facts repeat: a term, a symbol, a count, the category a surveyed model is put in, what a
cited paper is said to do. They appear in the text, the summary tables, the taxonomy tree and the captions. The researcher
edits one of them; this module lists the others.

    versions   The paper's history (Overleaf's Git, GitHub, or uploaded zips: all are git commits in the paper folder).
               The working tree counts as the newest version, so a local folder is checked on every save.
    baseline   The version the researcher last confirmed. Everything is compared with it. Confirming moves it.
    places     Sentences of the text, rows of tables, nodes of a forest tree, headings, display maths; and the rows of
               the supplementary repository's markdown tables (the model and dataset lists).
    changes    Places that differ between the baseline and now, paired sentence to sentence, with the words that changed.
    ripple     For each changed span (old words -> new words), the other places that still say the old words:
                 term change  (the new words are new to the paper, or the sentence names no model, cite or symbol):
                              every other place with the old words differs;
                 fact change  (the sentence is about something: a cite key, a listed model, a symbol): only places
                              about the same thing that still say the old words differ;
                 number       a changed number: places with the same number before the same word differ, the bare
                              number elsewhere is "check".
               A removed or renamed \\label that a \\ref still points to differs too.
    marks      Per row: fixed or leave as is. A row marked fixed that still differs comes back as such.
    list       The supplementary repository's markdown tables (README.md, Models.md, Dataset.md): models in the list
               the paper never names, models the paper surveys that the list lacks, and columns the paper and the list
               share where they disagree. The paper is the reference; Lemmata never writes to the repository.

Rules only, no language model. Nothing here writes to the paper or to the repository.
"""
import difflib
import hashlib
import os
import re

from .errors import BadRequest
from .tree import run_git

SCHEMA = "lemmata.survey/1"
STORE = "survey.json"
MAX_TEX_FILES = 400
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ROWS_PER_SPAN = 40
MAX_CHANGES = 300
MAX_VERSIONS = 200
MARKS = ("fixed", "leave")

STOP = set("""a an the of and or to in on for by with from as at is are was were be been being this that these those it its
which who whom whose than then there here we our us they their them he she his her not no nor but if so such into onto over
under also can may might must should would could will shall do does did done has have had having each either neither both
all any some more most less least very via per while when where how what why one two""".split())

TABULAR = {"tabular", "tabular*", "tabularx", "tabulary", "longtable", "longtable*", "supertabular", "xtabular", "NiceTabular", "tblr", "longtblr"}
DISPLAY = {"equation", "equation*", "align", "align*", "gather", "gather*", "multline", "multline*", "eqnarray", "eqnarray*", "displaymath", "flalign", "flalign*"}
FLOAT = {"figure", "figure*", "table", "table*"}
SKIP_ENV = {"comment", "verbatim", "lstlisting", "minted", "tikzpicture", "filecontents", "filecontents*"}
FOREST = {"forest"}
BREAK_ENV = {"itemize", "enumerate", "description", "abstract", "quote", "quotation", "center", "flushleft", "flushright", "minipage",
             "theorem", "lemma", "definition", "proposition", "corollary", "remark", "example", "proof", "assumption"}

ENV_RE = re.compile(r"\\(begin|end)\s*\{([A-Za-z*]+)\}")
CITE_RE = re.compile(r"\\(?:cite|citep|citet|citeauthor|citeyear|citealp|citealt|parencite|textcite|autocite|footcite|nocite)\*?(?:\[[^\]]*\])*\{([^}]*)\}")
REF_RE = re.compile(r"\\(?:ref|cref|Cref|autoref|eqref|pageref|vref|Vref|nameref)\*?\{([^}]*)\}")
LABEL_RE = re.compile(r"\\label\{([^}]*)\}")
HEAD_RE = re.compile(r"\\(part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?\s*(?:\[[^\]]*\])?\s*\{")
MATH_RE = re.compile(r"\$[^$]+\$")
SYM_RE = re.compile(r"\\(?:alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|vartheta|iota|kappa|lambda|mu|nu|xi|pi|rho|sigma|tau|upsilon|phi|varphi|chi|psi|omega|Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Upsilon|Phi|Psi|Omega|ell)(?![A-Za-z])(?:_\{?\\?[A-Za-z0-9]+\}?)?|(?<![\\A-Za-z])[A-Za-z]_\{?\\?[A-Za-z0-9]+\}?")
LEAD_RE = re.compile(r"(?:\s|\\(?:label|hline|toprule|midrule|bottomrule|cmidrule|addlinespace|noindent|centering|vspace|hspace|smallskip|medskip|bigskip|par|newline)\*?(?:\([^)]*\))?(?:\[[^\]]*\])?(?:\{[^{}]*\})?)*")
NUM_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w])")
STYLE_CMDS = ("emph", "textbf", "textit", "texttt", "textsc", "textsf", "textrm", "underline", "mbox", "text", "textnormal", "uline", "hl", "textup", "textmd", "bm", "mathbf", "mathrm")
ABBREV = ("e.g.", "i.e.", "et al.", "Fig.", "Figs.", "Eq.", "Eqs.", "Sec.", "Secs.", "Tab.", "vs.", "cf.", "etc.", "resp.", "approx.", "No.", "Ref.", "Refs.", "Dr.", "Prof.", "Thm.", "Def.", "Prop.", "Lem.", "Ch.", "Alg.", "Appx.", "w.r.t.")


def sha(*parts):
    return hashlib.sha1("\x1f".join(parts).encode("utf-8", "replace")).hexdigest()[:12]


# ------------------------------------------------------------------ text helpers
def strip_comment(line):
    """Drop a LaTeX comment (an unescaped %)."""
    i = 0
    while True:
        j = line.find("%", i)
        if j < 0:
            return line
        k, bs = j - 1, 0
        while k >= 0 and line[k] == "\\":
            bs += 1
            k -= 1
        if bs % 2 == 0:
            return line[:j]
        i = j + 1


def _arg_end(s, i):
    """s[i] == '{': index after the matching '}'."""
    depth = 0
    for k in range(i, len(s)):
        c = s[k]
        if c == "\\":
            continue
        if c == "{" and (k == 0 or s[k - 1] != "\\"):
            depth += 1
        elif c == "}" and (k == 0 or s[k - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return k + 1
    return len(s)


def plain(raw):
    """Readable text of a LaTeX fragment: styling unwrapped, cites and labels out, inline maths kept as written."""
    s = raw
    s = CITE_RE.sub(" ", s)
    s = LABEL_RE.sub(" ", s)
    s = REF_RE.sub(lambda m: " " + m.group(1).split(",")[0].strip() + " ", s)
    s = re.sub(r"\\(?:footnote|thanks)\s*\{", "(", s)
    for _ in range(4):
        s2 = re.sub(r"\\(?:%s)\s*\{([^{}]*)\}" % "|".join(STYLE_CMDS), r"\1", s)
        if s2 == s:
            break
        s = s2
    s = re.sub(r"\\(?:noindent|centering|par|newline|linebreak|smallskip|medskip|bigskip|hline|toprule|midrule|bottomrule|cmidrule(?:\([^)]*\))?(?:\{[^}]*\})?|item|maketitle|clearpage|newpage|raggedright)\b", " ", s)
    s = re.sub(r"\\(?:hspace|vspace|includegraphics|caption|subcaption|footnotemark|url|href)\*?(?:\[[^\]]*\])?", lambda m: " " if "caption" not in m.group(0) else "", s)
    s = s.replace("~", " ").replace("\\%", "%").replace("\\&", "&").replace("\\_", "_").replace("\\#", "#").replace("``", "\"").replace("''", "\"")
    s = re.sub(r"\\\\(?:\[[^\]]*\])?", " ", s)
    # inline maths stays as written (a symbol is searched as it is typed); everything else loses its braces
    out, last = [], 0
    for m in MATH_RE.finditer(s):
        out.append(re.sub(r"[{}]", "", s[last:m.start()]))
        out.append(re.sub(r"\s+", " ", m.group(0)))
        last = m.end()
    out.append(re.sub(r"[{}]", "", s[last:]))
    s = "".join(out)
    return re.sub(r"\s+", " ", s).strip()


def norm(t):
    return re.sub(r"\s+", " ", (t or "").lower()).strip()


def words(t):
    return re.findall(r"\$[^$]*\$|[A-Za-z0-9][A-Za-z0-9+\-_./']*|[^\sA-Za-z0-9]", t or "")


def symbols(raw):
    out = set()
    for m in MATH_RE.finditer(raw or ""):
        for x in SYM_RE.finditer(m.group(0)):
            out.add(re.sub(r"[{}\s]", "", x.group(0)))
    return out


def phrase_re(p):
    """Case-insensitive search for a phrase, whole words at its ends, any run of spaces inside."""
    parts = [re.escape(w) for w in p.split()]
    body = r"\s+".join(parts)
    pre = r"(?<![A-Za-z0-9])" if p[:1].isalnum() else ""
    post = r"(?![A-Za-z0-9])" if p[-1:].isalnum() else ""
    return re.compile(pre + body + post, re.I)


def is_term(p):
    ws = [w for w in re.findall(r"[A-Za-z0-9$\\_^{}+\-]+", p)]
    if not ws or len(ws) > 8:
        return False
    content = [w for w in ws if w.lower() not in STOP and not re.fullmatch(r"[\W_]+", w)]
    if not content:
        return False
    return any(len(w) >= 3 or w.startswith("$") or any(c.isdigit() for c in w) for w in content)


# ------------------------------------------------------------------ places
class Place(dict):
    pass


def _sentences(text):
    """Split prose into sentences; returns [(start, end)] offsets."""
    prot = text
    for a in ABBREV:
        prot = prot.replace(a, a.replace(".", "\x00"))
    prot = re.sub(r"(\d)\.(\d)", "\\1\x00\\2", prot)
    out, start = [], 0
    for m in re.finditer(r"[.!?](?=\s+(?:[A-Z\\$(\"`]|$))|[.!?]$", prot):
        end = m.end()
        out.append((start, end))
        start = end
    if start < len(text):
        out.append((start, len(text)))
    return [(a, b) for a, b in out if text[a:b].strip()]


def _split_cells(row):
    cells, cur, depth, i = [], [], 0, 0
    while i < len(row):
        c = row[i]
        if c == "\\" and i + 1 < len(row):
            cur.append(row[i:i + 2])
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if c == "&" and depth <= 0:
            cells.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    cells.append("".join(cur))
    return cells


def _forest_nodes(text, line_of):
    """Nodes of a forest tree: [(offset, own text, path of texts)]."""
    out, stack, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == "[":
            j, depth, buf = i + 1, 0, []
            while j < n:
                d = text[j]
                if d == "\\" and j + 1 < n:
                    buf.append(text[j:j + 2])
                    j += 2
                    continue
                if d == "{":
                    depth += 1
                elif d == "}":
                    depth -= 1
                elif depth <= 0 and d in ",[]":
                    break
                buf.append(d)
                j += 1
            own = plain("".join(buf)).strip()
            stack.append(own)
            if own:
                out.append((i, own, [x for x in stack if x]))
            # skip options after the comma up to the next bracket
            while j < n and text[j] not in "[]":
                if text[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                j += 1
            i = j
            continue
        if c == "]":
            if stack:
                stack.pop()
        i += 1
    return out


def places_of(path, text):
    """Every place of one .tex file, in order."""
    lines = (text or "").split("\n")
    code = [strip_comment(l) for l in lines]
    joined, starts = [], []
    pos = 0
    for l in code:
        starts.append(pos)
        joined.append(l)
        pos += len(l) + 1
    full = "\n".join(joined)

    def line_of(off):
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= off:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    out = []
    env_stack = []      # (name, begin offset)
    floats = []         # (begin, end, caption plain)
    buf_start = None

    def add(kind, a, b, raw, **kw):
        r = raw.strip()
        if not r:
            return
        lead = LEAD_RE.match(raw)       # the line of a place is where its words start, not a \label or \midrule before them
        p = Place(path=path, line=line_of(a + (lead.end() if lead else 0)), end=line_of(max(a, b - 1)), kind=kind, raw=r, plain=plain(r))
        p.update(kw)
        if p["plain"] or kind in ("row", "node"):
            out.append(p)

    def flush_prose(a, b):
        seg = full[a:b]
        if not seg.strip():
            return
        for blk in re.finditer(r"(?:(?!\n[ \t]*\n).)+", seg, re.S):
            ba = a + blk.start()
            btxt = blk.group(0)
            for sa, sb in _sentences(btxt):
                add("text", ba + sa, ba + sb, btxt[sa:sb])

    i, n = 0, len(full)
    prose_from = 0
    while i < n:
        m = ENV_RE.search(full, i)
        h = HEAD_RE.search(full, i)
        nxt = min([x.start() for x in (m, h) if x] or [n])
        if nxt >= n:
            break
        if h and h.start() == nxt:
            if not any(e[0] in SKIP_ENV | DISPLAY | TABULAR | FOREST for e in env_stack):
                flush_prose(prose_from, h.start())
                e = _arg_end(full, h.end() - 1)
                add("heading", h.start(), e, full[h.end():e - 1], level=h.group(1))
                prose_from = i = e
                continue
            i = h.end()
            continue
        kind, name = m.group(1), m.group(2)
        if kind == "begin":
            inner = env_stack[-1][0] if env_stack else None
            if inner not in SKIP_ENV | DISPLAY | TABULAR | FOREST:
                flush_prose(prose_from, m.start())
            e0 = m.end()
            om = re.match(r"\s*\[[^\]]*\]", full[e0:])
            if om and (name in FLOAT or name in BREAK_ENV) and "\n" not in om.group(0):
                e0 += om.end()
            env_stack.append((name, e0))
            prose_from = e0
            if name in FLOAT:
                floats.append([m.start(), None, ""])
            i = e0
            continue
        # end
        idx = next((k for k in range(len(env_stack) - 1, -1, -1) if env_stack[k][0] == name), None)
        if idx is None:
            i = m.end()
            continue
        ename, b0 = env_stack[idx]
        body = full[b0:m.start()]
        outer = [e[0] for e in env_stack[:idx]]
        if any(o in SKIP_ENV | DISPLAY | TABULAR | FOREST for o in outer):
            del env_stack[idx:]
            i = m.end()
            continue
        if ename in TABULAR:
            body2 = re.sub(r"^\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", "", body, count=1) if ename not in ("tabularx", "tabular*", "tabulary") else re.sub(r"^\s*\{[^{}]*\}\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", "", body, count=1)
            off0 = b0 + (len(body) - len(body2))
            header = None
            pos2 = 0
            for rm in re.finditer(r"(?:[^\\]|\\(?!\\)|\\\\(?=\\))*?(?:\\\\(?:\[[^\]]*\])?|$)", body2, re.S):
                seg = rm.group(0)
                if not seg.strip():
                    continue
                cells_raw = _split_cells(re.sub(r"\\\\(?:\[[^\]]*\])?\s*$", "", seg))
                cells = [plain(c) for c in cells_raw]
                if not any(cells):
                    continue
                a = off0 + rm.start()
                if header is None:
                    header = cells
                    add("row", a, off0 + rm.end(), seg, cells=cells, cells_raw=cells_raw, header=None, is_header=True)
                else:
                    add("row", a, off0 + rm.end(), seg, cells=cells, cells_raw=cells_raw, header=header, is_header=False)
                pos2 = rm.end()
        elif ename in FOREST:
            for off, own, path_ in _forest_nodes(body, None):
                a = b0 + off
                add("node", a, a + len(own), own, tree_path=path_, plain_override=" > ".join(path_))
            for p in out:
                if p.get("plain_override"):
                    p["plain"] = p.pop("plain_override")
        elif ename in DISPLAY:
            add("math", b0, m.start(), body)
        elif ename in SKIP_ENV:
            pass
        else:
            flush_prose(prose_from, m.start())
        if ename in FLOAT:
            for f in reversed(floats):
                if f[1] is None:
                    f[1] = m.end()
                    cm = re.search(r"\\caption\*?(?:\[[^\]]*\])?\s*\{", full[f[0]:f[1]])
                    if cm:
                        ca = f[0] + cm.end() - 1
                        f[2] = plain(full[ca + 1:_arg_end(full, ca) - 1])
                    break
        del env_stack[idx:]
        prose_from = i = m.end()
    flush_prose(prose_from, n)
    # tables and trees: say which float they sit in
    for p in out:
        if p["kind"] in ("row", "node", "text"):
            off = starts[p["line"] - 1]
            for f in floats:
                if f[1] and f[0] <= off < f[1]:
                    p["float"] = f[2][:160]
                    break
    for p in out:
        r = p["raw"]
        p["cites"] = sorted({k.strip() for m in CITE_RE.finditer(r) for k in m.group(1).split(",") if k.strip()})
        p["labels"] = sorted({m.group(1).strip() for m in LABEL_RE.finditer(r)})
        p["refs"] = sorted({k.strip() for m in REF_RE.finditer(r) for k in m.group(1).split(",") if k.strip()})
        p["syms"] = sorted(symbols(r))
        p["n"] = norm(p["plain"])
    return out


# ------------------------------------------------------------------ the supplementary lists (markdown tables)
MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")


def md_cell(c):
    c = MD_LINK.sub(r"\1", c)
    c = re.sub(r"[*_`]{1,3}", "", c)
    c = re.sub(r"<[^>]+>", "", c)
    return re.sub(r"\s+", " ", c).strip()


def md_tables(path, text):
    """Markdown tables of one file: [{path, line, header: [..], rows: [{line, cells}]}]."""
    lines = (text or "").split("\n")
    out, i = [], 0
    while i < len(lines) - 1:
        a, b = lines[i].strip(), lines[i + 1].strip()
        if a.startswith("|") and re.fullmatch(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?", b):
            header = [md_cell(c) for c in a.strip("|").split("|")]
            t = {"path": path, "line": i + 1, "header": header, "rows": []}
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                cells = [md_cell(c) for c in lines[j].strip().strip("|").split("|")]
                if any(cells):
                    t["rows"].append({"line": j + 1, "cells": cells, "raw": lines[j].strip()})
                j += 1
            out.append(t)
            i = j
        else:
            i += 1
    return out


def hnorm(h):
    return re.sub(r"[^a-z0-9]+", " ", (h or "").lower()).strip()


def vnorm(v):
    return re.sub(r"[^a-z0-9]+", "", (v or "").lower())


def read_list(files):
    """files: {path: text} of the supplementary repository's markdown. -> models, datasets, list places."""
    models, datasets, places = {}, [], []
    for path in sorted(files):
        for t in md_tables(path, files[path]):
            hs = [hnorm(x) for x in t["header"]]
            if hs and hs[0] in ("model", "models", "method", "name") and len(hs) >= 3:
                for r in t["rows"]:
                    name = r["cells"][0] if r["cells"] else ""
                    if not name or len(name) > 60:
                        continue
                    row = {h: (r["cells"][k] if k < len(r["cells"]) else "") for k, h in enumerate(hs)}
                    models.setdefault(name, []).append({"path": path, "line": r["line"], "row": row, "header": t["header"]})
                    places.append(Place(path=path, line=r["line"], end=r["line"], kind="list", raw=r["raw"], plain=" | ".join(x for x in r["cells"] if x),
                                        cites=[], labels=[], refs=[], syms=[], model=name))
            elif hs and hs[0] in ("dataset name", "dataset", "datasets"):
                mi = next((k for k, h in enumerate(hs) if h in ("models", "model", "used by")), None)
                for r in t["rows"]:
                    if not r["cells"] or not r["cells"][0]:
                        continue
                    used = [x.strip() for x in re.split(r",|;|\band\b", r["cells"][mi]) if x.strip()] if mi is not None and mi < len(r["cells"]) else []
                    datasets.append({"name": r["cells"][0], "path": path, "line": r["line"], "models": used})
                    places.append(Place(path=path, line=r["line"], end=r["line"], kind="list", raw=r["raw"], plain=" | ".join(x for x in r["cells"] if x),
                                        cites=[], labels=[], refs=[], syms=[], dataset=r["cells"][0]))
    for p in places:
        p["n"] = norm(p["plain"])
    return models, datasets, places


# ------------------------------------------------------------------ versions
class Source:
    """The paper folder's files at a commit, or as they are on disk now (rev None)."""

    def __init__(self, abs_path):
        self.abs = os.path.realpath(abs_path)
        p = run_git(self.abs, ["rev-parse", "--show-toplevel"], check=False)
        top = p.stdout.decode("utf-8", "replace").strip() if p.returncode == 0 else None
        self.top = os.path.realpath(top) if top else None
        self.prefix = os.path.relpath(self.abs, self.top).replace(os.sep, "/") if self.top else ""
        if self.prefix == ".":
            self.prefix = ""

    @property
    def is_git(self):
        return self.top is not None

    def git(self, args):
        p = run_git(self.top, args, check=False)
        return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else None

    def versions(self, n=MAX_VERSIONS):
        if not self.is_git:
            return []
        out = self.git(["log", "-n", str(n), "--format=%H%x1f%cI%x1f%an%x1f%s", "--"] + ([self.prefix] if self.prefix else ["."]))
        res = []
        for ln in (out or "").splitlines():
            parts = ln.split("\x1f")
            if len(parts) == 4:
                res.append({"sha": parts[0], "short": parts[0][:7], "time": parts[1], "author": parts[2], "subject": parts[3][:200]})
        return res

    def resolve(self, rev):
        if not self.is_git or not isinstance(rev, str) or not re.fullmatch(r"[0-9a-fA-F]{4,40}|HEAD", rev):
            return None
        out = self.git(["rev-parse", "--verify", "-q", rev + "^{commit}"])
        return out.strip() if out else None

    def dirty(self):
        if not self.is_git:
            return False
        out = self.git(["status", "--porcelain", "--"] + ([self.prefix] if self.prefix else ["."]))
        return bool(out and any(l[3:].endswith(".tex") for l in out.splitlines()))

    def tex_files(self, rev=None):
        """{path relative to the paper folder: text}"""
        out = {}
        if rev is None:
            for dp, dns, fns in os.walk(self.abs):
                dns[:] = sorted(d for d in dns if not d.startswith("."))
                for fn in sorted(fns):
                    if not fn.endswith(".tex"):
                        continue
                    fp = os.path.join(dp, fn)
                    if os.path.islink(fp) or os.path.getsize(fp) > MAX_FILE_BYTES:
                        continue
                    rel = os.path.relpath(fp, self.abs).replace(os.sep, "/")
                    try:
                        with open(fp, "rb") as f:
                            out[rel] = f.read().decode("utf-8", "replace")
                    except OSError:
                        continue
                    if len(out) >= MAX_TEX_FILES:
                        return out
            return out
        names = self.git(["ls-tree", "-r", "-z", "--full-name", "--name-only", rev, "--"] + ([self.prefix] if self.prefix else ["."]))
        for name in (names or "").split("\0"):
            if not name.endswith(".tex"):
                continue
            rel = name[len(self.prefix) + 1:] if self.prefix else name
            p = run_git(self.top, ["show", "%s:%s" % (rev, name)], check=False)
            if p.returncode != 0 or len(p.stdout) > MAX_FILE_BYTES:
                continue
            out[rel] = p.stdout.decode("utf-8", "replace")
            if len(out) >= MAX_TEX_FILES:
                break
        return out


# ------------------------------------------------------------------ comparing two versions
def _pair(B, H):
    """Changed places between two lists of places of one file: [(base place or None, head place or None)]."""
    sm = difflib.SequenceMatcher(None, [p["n"] for p in B], [p["n"] for p in H], autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        bs, hs = B[i1:i2], H[j1:j2]
        if op == "replace":
            used = set()
            for b in bs:
                best, bj = 0.0, None
                for k, hh in enumerate(hs):
                    if k in used:
                        continue
                    r = difflib.SequenceMatcher(None, b["n"], hh["n"], autojunk=False).ratio()
                    if r > best:
                        best, bj = r, k
                if bj is not None and best >= 0.45:
                    used.add(bj)
                    out.append((b, hs[bj]))
                else:
                    out.append((b, None))
            out += [(None, hh) for k, hh in enumerate(hs) if k not in used]
        elif op == "delete":
            out += [(b, None) for b in bs]
        else:
            out += [(None, hh) for hh in hs]
    return out


def spans(old, new):
    """Word-level differences: [(old words, new words)]."""
    a, b = words(old), words(new)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        ta, tb = _trim(a[i1:i2]), _trim(b[j1:j2])
        o, nw = " ".join(ta), " ".join(tb)
        o = re.sub(r"\s+([,.;:)\]])", r"\1", o)
        nw = re.sub(r"\s+([,.;:)\]])", r"\1", nw)
        out.append((o.strip(" ,.;:"), nw.strip(" ,.;:")))
    return [(o, nw) for o, nw in out if o or nw]


def _trim(ws):
    """Drop articles and other stop words at both ends of a changed span ("an error-based" -> "error-based")."""
    ws = list(ws)
    while len(ws) > 1 and (ws[0].lower() in STOP or re.fullmatch(r"[^\w$]+", ws[0])):
        ws.pop(0)
    while len(ws) > 1 and (ws[-1].lower() in STOP or re.fullmatch(r"[^\w$]+", ws[-1])):
        ws.pop()
    return ws


def variants_re(o):
    """The phrase, and for one plain word also its singular or plural."""
    if re.fullmatch(r"[A-Za-z][A-Za-z-]{2,}", o):
        alt = o[:-1] if o.lower().endswith("s") and not o.lower().endswith("ss") else o + "s"
        return re.compile(r"(?<![A-Za-z0-9])(?:%s|%s)(?![A-Za-z0-9])" % (re.escape(o), re.escape(alt)), re.I)
    return phrase_re(o)


def _entities(p, model_res):
    ents = set("cite:" + c for c in p.get("cites", []))
    ents |= set("sym:" + s for s in p.get("syms", []))
    if p.get("model"):
        ents.add("model:" + p["model"].lower())
    for name, rx in model_res:
        if rx.search(p.get("plain", "")):
            ents.add("model:" + name.lower())
    return ents


def _quote(p, n=240):
    t = p.get("plain") or ""
    return t if len(t) <= n else t[:n - 1] + "…"


def compare(base_files, head_files, list_places=(), models=()):
    """-> (changes, label rows)."""
    model_res = [(m, phrase_re(m)) for m in models if len(m) >= 2]
    B = {f: places_of(f, t) for f, t in base_files.items()}
    H = {f: places_of(f, t) for f, t in head_files.items()}
    all_head = [p for f in sorted(H) for p in H[f]]
    base_text = " \n ".join(p["n"] for f in B for p in B[f])
    pairs = []
    for f in sorted(set(B) | set(H)):
        pairs += _pair(B.get(f, []), H.get(f, []))
    # a sentence moved to another place is not a change
    dels = {}
    for b, hh in pairs:
        if b is not None and hh is None:
            dels.setdefault(b["n"], []).append(b)
    ins = {hh["n"] for b, hh in pairs if b is None and hh is not None}
    moved = {k for k in dels if k in ins}
    pairs = [(b, hh) for b, hh in pairs if not ((b is not None and hh is None and b["n"] in moved) or (b is None and hh is not None and hh["n"] in moved))]
    changed_head = {id(hh) for b, hh in pairs if hh is not None}
    pool = [p for p in all_head if id(p) not in changed_head] + list(list_places)
    for p in pool:
        p.setdefault("_ents", _entities(p, model_res))
    changes = []
    for b, hh in pairs[:MAX_CHANGES]:
        where = hh or b
        ch = {"id": sha(where["path"], (b or {}).get("n", ""), (hh or {}).get("n", "")), "path": where["path"], "line": where["line"],
              "kind": where["kind"], "float": where.get("float"), "old": _quote(b, 600) if b else "", "new": _quote(hh, 600) if hh else "",
              "what": "changed" if b and hh else "removed" if b else "added", "spans": [], "rows": []}
        if b and hh:
            ch["spans"] = [{"old": o, "new": nw} for o, nw in spans(b["plain"], hh["plain"])][:12]
            ents = _entities(hh, model_res) | _entities(b, model_res)
            seen = set()
            for sp in ch["spans"]:
                o, nw = sp["old"], sp["new"]
                if not o:
                    continue
                onum = NUM_RE.fullmatch(o.replace(" ", "")) and NUM_RE.fullmatch((nw or "").replace(" ", ""))
                if onum:
                    unit = _after(hh["plain"], nw) or _after(b["plain"], o)
                    sp["mode"] = "number"
                    rx = re.compile(r"(?<![\w.])" + re.escape(o) + r"(?![\w])")
                    for p in pool:
                        if p.get("kind") == "list":
                            continue
                        m = rx.search(p["plain"])
                        if not m:
                            continue
                        after = _after(p["plain"], o, m.start())
                        same_unit = bool(unit) and after == unit
                        _row(ch, seen, p, o, nw, "differs" if same_unit else "check",
                             ("Still says %s %s" % (o, unit)) if same_unit else ("The number %s appears here too" % o))
                    continue
                if not is_term(o):
                    continue
                rx = variants_re(o)
                newword = bool(nw) and not phrase_re(nw).search(base_text)
                term = newword or not ents
                sp["mode"] = "term" if term else "fact"
                for p in pool:
                    if term and p.get("kind") == "list":
                        continue      # the lists copy their descriptions from elsewhere; the paper's own wording is what must agree
                    if not rx.search(p["plain"]):
                        continue
                    if term:
                        _row(ch, seen, p, o, nw, "differs", "Still says “%s”" % o + ((" (now “%s”)" % nw) if nw else " (now removed)"))
                    else:
                        shared = ents & p["_ents"]
                        if shared:
                            about = _about(shared, p, hh)
                            _row(ch, seen, p, o, nw, "differs", "Still says “%s” about %s" % (o, about) + ((" (now “%s”)" % nw) if nw else ""))
        changes.append(ch)
    # labels: a \ref that points at a label the paper no longer has
    base_labels = {l for f in B for p in B[f] for l in p["labels"]}
    head_labels = {l for f in H for p in H[f] for l in p["labels"]}
    gone = sorted(base_labels - head_labels)
    for lab in gone:
        ch = {"id": sha("label", lab), "path": None, "line": None, "kind": "label", "float": None, "old": "\\label{%s}" % lab, "new": "",
              "what": "label", "spans": [{"old": lab, "new": "", "mode": "label"}], "rows": []}
        seen = set()
        for p in all_head:
            if lab in p["refs"]:
                _row(ch, seen, p, lab, "", "differs", "Refers to \\label{%s}, which the paper no longer defines" % lab)
        if ch["rows"]:
            changes.append(ch)
    return changes


def _about(shared, p, hh):
    """How to name what two places share: a model's name first, then a symbol, then a cite key."""
    for pre in ("model:", "sym:", "cite:"):
        xs = sorted(x for x in shared if x.startswith(pre))
        if xs:
            x = xs[0][len(pre):]
            if pre == "model:":
                m = phrase_re(x).search(hh.get("plain", "")) or phrase_re(x).search(p.get("plain", ""))
                return m.group(0) if m else x
            return x if pre == "sym:" else "\\cite{%s}" % x
    return "the same thing"


def _after(text, phrase, start=None):
    """The word right after `phrase` in `text` (lower case), or None."""
    if not phrase:
        return None
    if start is None:
        m = phrase_re(phrase).search(text) if phrase[:1].isalnum() or phrase[:1] == "$" else None
        if not m:
            i = text.find(phrase)
            if i < 0:
                return None
            end = i + len(phrase)
        else:
            end = m.end()
    else:
        end = start + len(phrase)
    m2 = re.match(r"\s*([A-Za-z][A-Za-z-]*)", text[end:])
    return m2.group(1).lower() if m2 else None


def _row(ch, seen, p, old, new, status, why):
    k = (p["path"], p["line"], p.get("kind"), p.get("n"))
    if k in seen:
        return
    if sum(1 for r in ch["rows"]) >= MAX_ROWS_PER_SPAN * 3:
        ch["more"] = ch.get("more", 0) + 1
        return
    seen.add(k)
    ch["rows"].append({"key": sha(ch["id"], p["path"], p.get("n", "")), "status": status, "path": p["path"], "line": p["line"], "end": p.get("end"),
                       "kind": p.get("kind"), "source": "list" if p.get("kind") == "list" else "paper", "repo": p.get("repo"), "float": p.get("float"),
                       "quote": _quote(p), "match": old, "now": new, "why": why})


# ------------------------------------------------------------------ the list against the paper
MODEL_HEADERS = {"model", "models", "method", "methods", "approach", "approaches", "framework", "frameworks", "detector", "detectors",
                 "algorithm", "algorithms", "odad model", "odad models", "name"}
AUTHOR_YEAR_RE = re.compile(r"\bet\s*al\b|\b(?:19|20)\d\d\b|\(|&| and ", re.I)


def list_check(models, datasets, head_places):
    """Rows: add (the paper surveys a model the list lacks), update (a shared column disagrees), check (the list names a
    model the paper never mentions; a dataset's model the list does not have)."""
    rows = []
    text_places = [p for p in head_places if p["kind"] in ("text", "row", "node", "heading")]
    found = {}
    for name in models:
        rx = phrase_re(name)
        hits = [p for p in text_places if rx.search(p["plain"])]
        found[name] = hits
        if not hits:
            e = models[name][0]
            rows.append({"key": sha("list-missing", name), "status": "check", "kind": "not_in_paper", "model": name, "path": e["path"], "line": e["line"],
                         "source": "list", "why": "The list names %s; the paper never does. Keep it if that is on purpose." % name})
    # models the paper surveys: first cells of table rows that cite something, bold names followed by a cite
    known = {vnorm(m) for m in models}
    cand = {}
    ds_names = {vnorm(d["name"]) for d in datasets}
    for p in head_places:
        # only a table whose first column names models (Model, Method, ...) says "this is a surveyed model"; a related-survey
        # table ("Abdulrahaman et al. (2025)") or a dataset table ("Annthyroid") is not a list of models
        if p["kind"] != "row" or p.get("is_header") or not p.get("cells_raw") or not p.get("header"):
            continue
        if hnorm(p["header"][0]) not in MODEL_HEADERS:
            continue
        c0 = p["cells_raw"][0]
        nm = plain(c0).strip(" ,;:")
        if not (1 <= len(nm) <= 40 and len(nm.split()) <= 4) or AUTHOR_YEAR_RE.search(nm) or vnorm(nm) in ds_names:
            continue
        cand.setdefault(nm, p)
    for nm, p in sorted(cand.items()):
        if vnorm(nm) in known or not vnorm(nm):
            continue
        rows.append({"key": sha("list-add", nm), "status": "differs", "kind": "add", "model": nm, "path": p["path"], "line": p["line"], "source": "paper",
                     "quote": _quote(p), "why": "The paper surveys %s; the list does not have it. Add a row for it." % nm})
    # shared columns: a paper table whose header names the same columns as the list
    for p in head_places:
        if p["kind"] != "row" or p.get("is_header") or not p.get("header"):
            continue
        hdr = [hnorm(x) for x in p["header"]]
        name_cell = p["cells"][0] if p["cells"] else ""
        model = next((m for m in models if vnorm(m) and vnorm(m) == vnorm(re.sub(r"\[[^\]]*\]", "", name_cell))), None)
        if not model:
            continue
        for e in models[model]:
            for k, h in enumerate(hdr):
                if k == 0 or not h or h not in e["row"] or k >= len(p["cells"]):
                    continue
                pv, lv = p["cells"][k], e["row"][h]
                if pv and lv and vnorm(pv) != vnorm(lv):
                    rows.append({"key": sha("list-upd", model, h, e["path"]), "status": "differs", "kind": "update", "model": model, "column": p["header"][k],
                                 "path": e["path"], "line": e["line"], "source": "list", "paper": {"path": p["path"], "line": p["line"], "value": pv}, "list_value": lv,
                                 "why": "%s, %s: the paper says “%s”, %s says “%s”. Update the list." % (model, p["header"][k], pv, e["path"], lv)})
    # the same model in two list files that disagree
    for m, es in models.items():
        if len(es) < 2:
            continue
        a = es[0]
        for b in es[1:]:
            if b["path"] == a["path"]:
                continue
            diff = [h for h in a["row"] if h in b["row"] and h not in ("resources", "paper title", "link", "links", "code") and vnorm(a["row"][h]) != vnorm(b["row"][h])]
            if diff:
                rows.append({"key": sha("list-two", m, a["path"], b["path"]), "status": "check", "kind": "two_lists", "model": m, "path": b["path"], "line": b["line"],
                             "source": "list", "why": "%s: %s and %s disagree on %s." % (m, a["path"], b["path"], ", ".join(diff[:4]))})
    known_l = {m.lower() for m in models}
    for d in datasets:
        for m in d["models"]:
            if m.lower() not in known_l and len(m) <= 40 and not re.search(r"et al|\(", m):
                rows.append({"key": sha("list-ds", d["name"], m), "status": "check", "kind": "dataset_model", "model": m, "path": d["path"], "line": d["line"],
                             "source": "list", "why": "Dataset %s lists %s as a model that uses it; the model list has no %s." % (d["name"], m, m)})
    return rows, {m: len(found[m]) for m in models}


# ------------------------------------------------------------------ store
def load(hub):
    d = hub.read_json(STORE, None)
    if not isinstance(d, dict):
        d = {}
    d.setdefault("schema", SCHEMA)
    d.setdefault("baseline", None)
    d.setdefault("baseline_at", None)
    d.setdefault("marks", {})
    d.setdefault("confirmed", [])
    return d


def mark(store, key, state, at):
    if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{12}", key):
        raise BadRequest("row must be a row key")
    if state in (None, "", "open"):
        store["marks"].pop(key, None)
    elif state in MARKS:
        store["marks"][key] = {"state": state, "at": at}
    else:
        raise BadRequest("state must be fixed, leave or open")
    return store


def apply_marks(rows, marks):
    for r in rows:
        m = marks.get(r["key"])
        r["mark"] = m["state"] if m else None
        if r["mark"] == "leave":
            r["shown"] = "left"
        elif r["mark"] == "fixed" and r["status"] == "differs":
            r["shown"] = "still"      # marked fixed, but the place still says the old words
        else:
            r["shown"] = r["status"]
    return rows


# ------------------------------------------------------------------ the survey map: claims and taxonomy (S37, founder 2026-11-23 18:08 KST)
# "For a survey, the claim is the most important thing, along with the taxonomy that is organizing. Use AI to fully understand
# the paper and re-organize the key claims." The researcher's own agent reads the whole paper and proposes the map; rules check
# every quote, cite key and model name against the paper; the researcher confirms. The hub calls no model.
MAP_STORE = "survey_map.json"
MAP_SCHEMA = "lemmata.surveymap/1"
CLAIM_KINDS = ("contribution", "finding", "position", "gap", "trend", "definition", "limitation", "future")
MAX_CLAIMS, MAX_AXES, MAX_CATS, MAX_MODELS, MAX_EV = 60, 8, 24, 300, 6
PAGE_CHARS = 90000

MAP_GUIDE = """You are reading a survey paper so that its author can see, at a glance, what the survey claims and how it is organised.
Read every page of the paper below (call survey_brief again with page=2, 3, ... until next_page is null). Then call
propose_survey_map with one JSON object:

{
  "thesis": "One or two sentences: what the survey as a whole argues or contributes.",
  "questions": [ {"id": "RQ1", "text": "the research question as the paper states it", "answer": "what the paper answers, in one or two sentences",
                  "where": [ {"path": "sec/intro.tex", "line": 42, "quote": "a short exact phrase from that line"} ]} ],
  "claims": [ {"id": "C1", "text": "one claim, in the paper's own terms, one sentence",
               "kind": "contribution | finding | position | gap | trend | definition | limitation | future",
               "question": "RQ1 (or null)",
               "where": [ {"path": ..., "line": ..., "quote": ...} ],          (1 to 6 places the paper states or supports it)
               "cites": ["bibkey", ...],                                       (cite keys that back it, as written in \\cite{})
               "taxonomy": ["A1.generative", ...]} ],                         (categories it is about, ids from "taxonomy")
  "taxonomy": [ {"id": "A1", "name": "the axis, e.g. Base model", "where": [...],
                 "categories": [ {"id": "A1.generative", "name": "Generative", "definition": "one sentence, as the paper defines it",
                                  "where": [...], "models": ["ARCUS", "METER", ...]} ]} ]
}

Rules:
- The key claims, not every sentence: what a reader must accept to accept the survey (its framing, its taxonomy, its findings
  per research question, the gaps and open problems it names). Usually 8 to 30. Re-organise them under the research questions;
  merge a claim the paper repeats in several sections into one claim with several "where".
- Quotes are short exact phrases (5 to 15 words) from the LaTeX source as shown, with its file and line. Lemmata drops any
  quote it cannot find, and any claim left without one.
- "taxonomy" is the paper's own organisation: each axis the paper classifies methods by, its categories and the models the
  paper puts in each, by the name the paper uses. A model may sit in one category per axis.
- Use only cite keys that appear in the paper. Do not invent claims the paper does not make; say "position" for the authors'
  opinions and "gap" for what they say is missing.
- This is a proposal. The author confirms it in Lemmata; nothing counts before that."""


def squash(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


class PaperText:
    """The paper's files as numbered lines, for quotes and for the brief."""

    def __init__(self, files):
        self.files = files
        self.lines = {f: t.split("\n") for f, t in files.items()}
        self._pl = {}

    def plain_lines(self, f):
        if f not in self._pl:
            self._pl[f] = [squash(plain(strip_comment(l))) for l in self.lines.get(f, [])]
        return self._pl[f]

    def find(self, ev):
        """{path, line, quote} -> the same with the line where the quote really is, or None."""
        if not isinstance(ev, dict):
            return None
        path = str(ev.get("path") or ev.get("file") or "").strip().lstrip("./")
        quote = " ".join(str(ev.get("quote") or "").split())[:300]
        q = squash(plain(quote))
        if not q or len(q) < 8:
            return None
        cands = [path] if path in self.lines else [f for f in self.lines if f.endswith("/" + path) or os.path.basename(f) == os.path.basename(path)] or list(self.lines)
        for f in cands:
            pl = self.plain_lines(f)
            line = ev.get("line") if isinstance(ev.get("line"), int) else None
            near = list(range(max(0, line - 10), min(len(pl), line + 10))) if line else []
            for i in near + [i for i in range(len(pl)) if i not in near]:
                if q in " ".join(pl[i:i + 4]):
                    first = " ".join(q.split()[:3])
                    hit = next((j for j in range(i, min(i + 4, len(pl))) if first in pl[j]), i)
                    return {"path": f, "line": hit + 1, "quote": quote}
        return None

    def pages(self):
        """Numbered text in pages of about PAGE_CHARS characters: [[(path, start, end, text)]]."""
        out, cur, size = [], [], 0
        for f in sorted(self.files, key=lambda x: (not x.lower().startswith("main"), x)):
            ls = self.lines[f]
            i = 0
            while i < len(ls):
                chunk, j, n = [], i, 0
                while j < len(ls) and n < PAGE_CHARS - size:
                    t = "%5d  %s" % (j + 1, ls[j])
                    chunk.append(t)
                    n += len(t) + 1
                    j += 1
                if chunk:
                    cur.append((f, i + 1, j, "\n".join(chunk)))
                    size += n
                i = j
                if size >= PAGE_CHARS:
                    out.append(cur)
                    cur, size = [], 0
        if cur:
            out.append(cur)
        return out


def _txt(v, n):
    return " ".join(v.split())[:n] if isinstance(v, str) and v.strip() else None


def _ident(v, fallback):
    v = str(v or "").strip()
    return v[:40] if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._\-]{0,39}", v) else fallback


def clean_map(doc, text, cite_keys, place_text):
    """Check a proposed map against the paper. -> (map, report). Dropped: quotes not in the paper, claims left without one,
    unknown cite keys, models the paper never names, references to unknown ids."""
    if not isinstance(doc, dict):
        raise BadRequest("the map must be an object; see survey_brief for the format")
    report = []

    def note(level, where, why):
        report.append({"level": level, "where": where, "why": why})

    def evs(items, where):
        ok = []
        for ev in (items if isinstance(items, list) else [])[:MAX_EV]:
            got = text.find(ev)
            if got:
                if not any(g["path"] == got["path"] and g["line"] == got["line"] for g in ok):
                    ok.append(got)
            else:
                note("dropped", where, "quote not found in the paper: %r" % str((ev or {}).get("quote", "") if isinstance(ev, dict) else ev)[:70])
        return ok

    out = {"schema": MAP_SCHEMA, "thesis": _txt(doc.get("thesis"), 600), "questions": [], "claims": [], "taxonomy": []}
    if not out["thesis"]:
        note("note", "thesis", "no thesis given")
    qids = set()
    for k, q in enumerate((doc.get("questions") or [])[:12] if isinstance(doc.get("questions"), list) else []):
        if not isinstance(q, dict) or not _txt(q.get("text"), 400):
            note("dropped", "questions[%d]" % k, "a question needs text")
            continue
        qid = _ident(q.get("id"), "RQ%d" % (k + 1))
        while qid in qids:
            qid += "'"
        qids.add(qid)
        out["questions"].append({"id": qid, "text": _txt(q.get("text"), 400), "answer": _txt(q.get("answer"), 800), "where": evs(q.get("where"), qid)})
    lowtext = place_text.lower()
    cat_ids = set()
    for a, ax in enumerate((doc.get("taxonomy") or [])[:MAX_AXES] if isinstance(doc.get("taxonomy"), list) else []):
        if not isinstance(ax, dict) or not _txt(ax.get("name"), 80):
            note("dropped", "taxonomy[%d]" % a, "an axis needs a name")
            continue
        aid = _ident(ax.get("id"), "A%d" % (a + 1))
        axis = {"id": aid, "name": _txt(ax.get("name"), 80), "where": evs(ax.get("where"), aid), "categories": []}
        for c, cat in enumerate((ax.get("categories") or [])[:MAX_CATS] if isinstance(ax.get("categories"), list) else []):
            if not isinstance(cat, dict) or not _txt(cat.get("name"), 80):
                note("dropped", "%s.categories[%d]" % (aid, c), "a category needs a name")
                continue
            cid = _ident(cat.get("id"), "%s.%d" % (aid, c + 1))
            while cid in cat_ids:
                cid += "'"
            cat_ids.add(cid)
            models = []
            for m in (cat.get("models") or [])[:MAX_MODELS] if isinstance(cat.get("models"), list) else []:
                m = _txt(m, 60) if isinstance(m, str) else None
                if not m:
                    continue
                if not phrase_re(m).search(place_text) and m.lower() not in lowtext:
                    note("dropped", cid, "model %r is not named in the paper" % m)
                    continue
                if m not in models:
                    models.append(m)
            axis["categories"].append({"id": cid, "name": _txt(cat.get("name"), 80), "definition": _txt(cat.get("definition"), 500),
                                       "where": evs(cat.get("where"), cid), "models": models})
        if axis["categories"]:
            out["taxonomy"].append(axis)
        else:
            note("dropped", aid, "an axis with no category")
    seen = set()
    for k, cl in enumerate((doc.get("claims") or [])[:MAX_CLAIMS] if isinstance(doc.get("claims"), list) else []):
        if not isinstance(cl, dict) or not _txt(cl.get("text"), 500):
            note("dropped", "claims[%d]" % k, "a claim needs text")
            continue
        cid = _ident(cl.get("id"), "C%d" % (k + 1))
        while cid in seen:
            cid += "'"
        seen.add(cid)
        where = evs(cl.get("where"), cid)
        if not where:
            note("dropped", cid, "no quote of this claim was found in the paper, so it was left out")
            continue
        kind = cl.get("kind") if cl.get("kind") in CLAIM_KINDS else "finding"
        if cl.get("kind") not in CLAIM_KINDS:
            note("note", cid, "kind %r is not one of %s; read as finding" % (cl.get("kind"), ", ".join(CLAIM_KINDS)))
        cites = []
        for c in (cl.get("cites") or [])[:40] if isinstance(cl.get("cites"), list) else []:
            if isinstance(c, str) and c.strip() in cite_keys:
                cites.append(c.strip())
            elif isinstance(c, str):
                note("dropped", cid, "cite key %r is not cited in the paper" % c[:40])
        q = cl.get("question")
        if q not in (None, "") and q not in qids:
            note("note", cid, "question %r is not one of the questions" % str(q)[:20])
            q = None
        tax = [t for t in (cl.get("taxonomy") or []) if isinstance(t, str) and t in cat_ids] if isinstance(cl.get("taxonomy"), list) else []
        out["claims"].append({"id": cid, "text": _txt(cl.get("text"), 500), "kind": kind, "question": q or None, "where": where,
                              "cites": cites, "taxonomy": tax})
    if not out["claims"]:
        raise BadRequest("no claim survived checking; every claim needs at least one quote that really is in the paper. %s" %
                         "; ".join("%s: %s" % (r["where"], r["why"]) for r in report[:5]))
    return out, report


def load_map(hub):
    d = hub.read_json(MAP_STORE, None)
    if not isinstance(d, dict):
        d = {}
    for k in ("proposed", "proposed_by", "proposed_at", "report", "confirmed", "confirmed_at", "confirmed_from"):
        d.setdefault(k, None)
    d["schema"] = MAP_SCHEMA
    return d


def claims_now(m, text):
    """Each claim of a confirmed map, and whether the sentences behind it are still in the paper."""
    out = []
    for cl in (m or {}).get("claims", []):
        gone = [ev for ev in cl["where"] if not text.find(ev)]
        out.append(dict(cl, state="changed" if gone else "in_step", gone=gone))
    return out


def taxonomy_now(m, head_places):
    """Where the paper places a model differently from the confirmed taxonomy: a place that names this model (and no other
    model of the taxonomy) and names another category of the same axis, but not the model's own."""
    rows = []
    axes = (m or {}).get("taxonomy", [])
    all_models = {mm for ax in axes for c in ax["categories"] for mm in c["models"]}
    mres = {mm: phrase_re(mm) for mm in all_models}
    for ax in axes:
        cres = {c["id"]: phrase_re(c["name"]) for c in ax["categories"]}
        for c in ax["categories"]:
            others = [o for o in ax["categories"] if o["id"] != c["id"]]
            for mm in c["models"]:
                for p in head_places:
                    if p["kind"] not in ("text", "row", "node"):
                        continue
                    t = p["plain"]
                    if not mres[mm].search(t) or any(mres[o].search(t) for o in all_models if o != mm and o.lower() != mm.lower()):
                        continue
                    if cres[c["id"]].search(t):
                        continue
                    hit = next((o for o in others if cres[o["id"]].search(t)), None)
                    if hit:
                        rows.append({"key": sha("tax", ax["id"], mm, p["path"], p.get("n", "")), "status": "differs", "axis": ax["name"], "model": mm,
                                     "category": c["name"], "said": hit["name"], "path": p["path"], "line": p["line"], "kind": p["kind"], "quote": _quote(p),
                                     "why": "%s is %s by the taxonomy (%s), but this place says %s." % (mm, c["name"], ax["name"], hit["name"])})
    return rows
