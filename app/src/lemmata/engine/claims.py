"""Claim map: the paper's core message, the claims under it, and what backs each one.

Lemmata drafts; the researcher confirms. Nothing here uses a language model. Drafts come from the LaTeX
source (abstract, contribution lists, research questions, theorem-like environments) and support comes from
the dependency graph (tables/figures -> result files -> code -> runs) and from the LaTeX itself (proofs,
assumptions and lemmas a statement refers to). Decisions live in .lemmata/claims.json.

Vocabulary
  claim.state   proposed | confirmed | rejected          (the researcher's decision about the draft)
  claim.status  supported | partial | unsupported        (what the evidence says), plus claim.recheck
  support.how   detected | suggested | manual            (suggested links count only after they are accepted)
"""
import re

from . import latex as lx
from .errors import BadRequest, NotFound

SCHEMA = "lemmata.claims/1"
FORMAL = {"theorem": "Theorem", "lemma": "Lemma", "proposition": "Proposition", "corollary": "Corollary", "claim": "Claim"}
PREMISE = {"assumption": "Assumption", "definition": "Definition", "condition": "Condition", "hypothesis": "Hypothesis"}
ALIASES = {"thm": "theorem", "theo": "theorem", "lem": "lemma", "lemm": "lemma", "prop": "proposition", "cor": "corollary",
           "coro": "corollary", "assum": "assumption", "asm": "assumption", "ass": "assumption", "assump": "assumption",
           "defn": "definition", "def": "definition", "defi": "definition", "cond": "condition", "hyp": "hypothesis"}
NEWTHM_RE = re.compile(r"\\newtheorem\*?\{([A-Za-z*]+)\}(?:\[[^\]]*\])?\{([^}]+)\}")
BEGIN_RE = re.compile(r"\\begin\{([A-Za-z*]+)\}(?:\s*\[([^\]]*)\])?")
ITEM_RE = re.compile(r"\\item\b(?:\s*\[[^\]]*\])?")
CONTRIB_RE = re.compile(r"contribution|we (?:make|show|propose|prove|introduce|present|demonstrate|find)|our (?:main )?(?:results|findings)|"
                        r"in summary|summari[sz]e", re.I)
PROOF_OF_RE = re.compile(r"[Pp]roofs?\s+(?:of|for)\b[^.\n]{0,80}?\\(?:ref|cref|Cref|autoref)\*?\{([^}]+)\}")
STOP = set("a an and are as at be been by can do does for from has have how in into is it its of on or our than that the their then "
           "there these this to was we were what when where which while with without not no also both each more most new novel "
           "show shows shown propose proposed present paper method methods approach results result model models using use used "
           "based across over under between via such may might will than first second third one two three".split())
NUM_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?%?(?![\w.])")
SUPPORT_REL = ("traces_to", "includes", "generated_by", "value_match", "produced_by", "executes", "reads", "imports")


DISPLAY_RE = re.compile(r"\\begin\{(equation|align|gather|multline|eqnarray|alignat|flalign|displaymath)\*?\}(?:\{\d+\})?(.+?)\\end\{\1\*?\}", re.S)
MATH_SPLIT_RE = re.compile(r"(\$\$.+?\$\$|(?<!\\)\$.+?(?<!\\)\$|\\\(.+?\\\)|\\\[.+?\\\])", re.S)


def _display(m):
    body = re.sub(r"\\(?:label|tag)\{[^}]*\}|\\nonumber|\\notag", "", m.group(2)).strip()
    if m.group(1) in ("align", "eqnarray", "alignat", "flalign") or "\\\\" in body:
        body = "\\begin{aligned}%s\\end{aligned}" % body.replace("&=&", "&=")
    return "\\[" + body + "\\]"


def _detex_text(s):
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    s = re.sub(r"\\(?:cite[a-z]*|nocite)\*?(?:\[[^\]]*\])*\{[^}]*\}", "", s)
    s = re.sub(r"\\(?:ref|cref|Cref|autoref|eqref)\*?\{([^}]*)\}", lambda m: "[" + m.group(1) + "]", s)
    s = re.sub(r"\\(?:textbf|textit|emph|textsc|texttt|underline|mathrm|mathbf|mathcal|text)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\(?:begin|end)\{[^}]*\}", " ", s)
    s = re.sub(r"\\item\b", " ", s)
    s = s.replace("~", " ").replace("\\%", "%").replace("\\&", "&").replace("\\_", "_").replace("``", '"').replace("''", '"')
    s = re.sub(r"\\[,;:! ]", " ", s)
    return s


def detex(s):
    """LaTeX -> plain text good enough for a one-line statement. Math is kept as TeX between its delimiters ($...$, \\[...\\])
    so the app can typeset it; display environments become \\[...\\]."""
    s = DISPLAY_RE.sub(_display, s or "")
    parts = MATH_SPLIT_RE.split(s)
    for i, p in enumerate(parts):
        if i % 2:      # math
            parts[i] = re.sub(r"\s+", " ", re.sub(r"\\label\{[^}]*\}", "", p))
        else:
            parts[i] = _detex_text(p)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def cut(text, n):
    """Truncate without cutting a formula in half."""
    if len(text) <= n:
        return text
    t = text[:n]
    for m in MATH_SPLIT_RE.finditer(text):
        if m.start() < n < m.end():
            t = text[:m.start()]
            break
    return t.rstrip() + "…"


TITLE_RE = re.compile(r"\\title(?:\[[^\]]*\])?\{((?:[^{}]|\{[^{}]*\})*)\}")
ABBR_RE = re.compile(r"\b(e\.g|i\.e|et al|cf|vs|Fig|Figs|Eq|Eqs|Sec|Tab|resp|w\.r\.t|a\.k\.a|etc)\.\s")
AIM_RE = re.compile(r"\b(?:in this (?:paper|work|survey|study|article|review)|this (?:paper|work|survey|study|article|review) "
                    r"(?:\w+ )?(?:present|propos|introduc|show|provid|review|survey|stud|investigat|develop|argu|address|offer|examin)\w*|"
                    r"we (?:\w+ )?(?:propose|present|introduce|show|demonstrate|prove|develop|provide|argue|find|establish|derive|"
                    r"survey|review|study|investigate|identify|formali[sz]e|design|address|revisit)|our (?:main |key )?"
                    r"(?:contribution|finding|result|analysis|survey|method|approach|framework)s?\b|to this end|here,? we)", re.I)
BACKGROUND_RE = re.compile(r"^(?:however|recently|although|while|despite|traditionally|in recent years|nowadays|existing|previous|prior|"
                           r"most|many|current)\b|\b(?:has|have) (?:been|become|attracted|received|shown|emerged)\b|\bremains? (?:a|an|"
                           r"un|open|challeng)", re.I)


def sentences(text):
    t = ABBR_RE.sub(lambda m: m.group(0).replace(". ", ".\x00"), text or "")
    out = [x.replace("\x00", " ").strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z\"“(])", t)]
    return [x for x in out if len(x) > 20]


def pick_core(abstract, title="", contrib_words=()):
    """The sentence of the abstract that states what the paper does. Rules only: cue phrases ("we propose", "in this
    survey"), minus background cues, plus overlap with the contribution list. A suggestion; the researcher can reword it."""
    sents = sentences(abstract)
    if not sents:
        return title or (abstract or "")[:300]
    best, best_score = None, 0.0
    for i, st in enumerate(sents):
        sc = 3.0 * bool(AIM_RE.search(st)) - 2.0 * bool(BACKGROUND_RE.search(st))
        if contrib_words:
            w = words(st)
            sc += 2.0 * len(w & set(contrib_words)) / (len(w) or 1)
        sc -= 0.5 * len(NUM_RE.findall(st)) / 3.0
        sc -= 0.01 * i          # ties go to the earlier sentence
        if i == 0:
            sc -= 0.5           # first sentences are usually background
        if sc > best_score:
            best, best_score = st, sc
    if best is None or best_score < 1.0:
        return title or sents[-1]
    return best


def words(s):
    return {w for w in re.findall(r"[a-z][a-z0-9-]{2,}", MATH_SPLIT_RE.sub(" ", detex(s)).lower()) if w not in STOP}


def _canon_env(name, newthm):
    base = name.rstrip("*").lower()
    printed = newthm.get(name.rstrip("*"))
    if printed:
        p = printed.strip().lower()
        for k in list(FORMAL) + list(PREMISE):
            if p.startswith(k):
                return k
    base = ALIASES.get(base, base)
    return base if base in FORMAL or base in PREMISE or base == "proof" else None


def _blocks(P):
    """Theorem-like blocks, premises and proofs found in the flattened source."""
    lines = P.lines
    newthm = {}
    for ln in lines:
        for m in NEWTHM_RE.finditer(ln.code):
            newthm[m.group(1)] = m.group(2)
    out, counters, stack = [], {}, []
    for i, ln in enumerate(lines):
        for m in lx.ENV_RE.finditer(ln.code):
            which, name = m.group(1), m.group(2)
            kind = _canon_env(name, newthm)
            if not kind:
                continue
            if which == "begin":
                opt = BEGIN_RE.match(ln.code[m.start():])
                stack.append((name, kind, i, opt.group(2) if opt and opt.group(1) == name else None))
            elif stack and stack[-1][0] == name:
                _, kind, b, opt = stack.pop()
                body = "\n".join(l.code for l in lines[b:i + 1])
                labels = lx.LABEL_RE.findall(body)
                refs = [r.strip() for grp in lx.REF_RE.findall(body) for r in grp.split(",") if r.strip()]
                blk = {"kind": kind, "begin": b, "end": i, "title": detex(opt) if opt else None, "label": labels[0] if labels else None,
                       "refs": refs, "text": cut(detex(re.sub(r"^\s*\[[^\]]*\]", "", body.split("}", 1)[1] if "}" in body else body)), 600),
                       "in_appendix": P.appendix_idx is not None and b > P.appendix_idx, "raw_head": lines[b].code}
                if kind != "proof":
                    counters[kind] = counters.get(kind, 0) + 1
                    blk["number"] = counters[kind]
                out.append(blk)
    out.sort(key=lambda b: b["begin"])
    return out


def _contribution_items(P):
    """\\item texts of the first list that looks like a contribution list (introduction, or introduced by a cue sentence)."""
    lines = P.lines
    limit = P.appendix_idx if P.appendix_idx is not None else len(lines)
    intro = None
    for u in P.units:
        if u["kind"] == "section" and u.get("level", 1) == 1 and re.search(r"intro", u.get("title") or "", re.I):
            intro = (u["begin"], u["begin"])
            for v in P.units:
                if v["kind"] == "section" and v.get("level", 1) == 1 and v["begin"] > u["begin"]:
                    intro = (u["begin"], v["begin"])
                    break
            if intro[1] == intro[0]:
                intro = (u["begin"], limit)
            break
    stack, best = [], None
    for i, ln in enumerate(lines[:limit]):
        for m in lx.ENV_RE.finditer(ln.code):
            if m.group(2) not in ("itemize", "enumerate"):
                continue
            if m.group(1) == "begin":
                stack.append(i)
            elif stack:
                b = stack.pop()
                if stack:
                    continue  # nested list
                lead = " ".join(l.code for l in lines[max(0, b - 4):b + 1])
                cue = bool(CONTRIB_RE.search(lead))
                in_intro = bool(intro and intro[0] <= b < intro[1])
                score = (2 if cue else 0) + (1 if in_intro else 0)
                if score and (best is None or score > best[0]):
                    best = (score, b, i)
    if not best:
        return []
    _, b, e = best
    items, cur = [], None
    for i in range(b, e + 1):
        code = lines[i].code
        parts = ITEM_RE.split(code)
        if len(parts) > 1:
            if cur:
                cur["text"] += " " + parts[0]
            for p in parts[1:]:
                if cur:
                    cur["end"] = i if p is parts[1] and not parts[0].strip() else cur["end"]
                    items.append(cur)
                cur = {"begin": i, "end": i, "text": p}
        elif cur:
            cur["text"] += " " + code
            cur["end"] = i
    if cur:
        items.append(cur)
    for it in items:
        it["refs"] = [r.strip() for grp in lx.REF_RE.findall(it["text"]) for r in grp.split(",") if r.strip()]
        it["text"] = detex(it["text"])
    return [it for it in items if len(it["text"]) > 12]


def _loc(P, b, e=None):
    ln = P.lines[b]
    return {"path": ln.path, "line": ln.no, "end_line": P.lines[e].no if e is not None and P.lines[e].path == ln.path else ln.no}


class _Ctx:
    def __init__(self, G, alarms, findings):
        self.G = G
        self.nodes = G.nodes
        self.fwd = {}
        for e in G.edges.values():
            if e["kind"] in SUPPORT_REL and e["status"] in ("detected", "approved"):
                self.fwd.setdefault(e["from"], []).append(e)
        self.contains = {}
        for e in G.edges.values():
            if e["kind"] == "contains":
                self.contains.setdefault(e["from"], []).append(e["to"])
        self.stale = {}
        for g in (alarms or {}).get("groups", []):
            cause = g.get("cause") or {}
            why = cause.get("subject") or cause.get("kind") or "a change"
            for c in g.get("changed", []):
                self.stale.setdefault(c["node_id"], why)
            for d in g.get("downstream", []):
                if d.get("output_identical") is not True:
                    self.stale.setdefault(d["node_id"], why)
        self.findings = (findings or {}).get("findings", [])

    def chain(self, nid):
        """Files and runs a paper item rests on: {results, code, runs, settings} (node ids)."""
        seen, todo = {nid}, [nid]
        out = {"results": [], "code": [], "runs": [], "settings": []}
        while todo:
            cur = todo.pop()
            for e in self.fwd.get(cur, []):
                t = e["to"]
                if t in seen or t not in self.nodes:
                    continue
                seen.add(t)
                k = self.nodes[t]["kind"]
                key = "results" if k in ("result", "asset", "data") else "code" if k == "code" else "runs" if k == "run" else \
                    "settings" if k == "config" else None
                if key:
                    out[key].append(t)
                    todo.append(t)
        return out

    def floats_in(self, sec_id):
        out = []
        todo = [sec_id]
        while todo:
            for c in self.contains.get(todo.pop(), []):
                n = self.nodes.get(c)
                if not n:
                    continue
                if n["kind"] in ("figure", "table"):
                    out.append(c)
                elif n["kind"] == "section":
                    todo.append(c)
        return out


def _support_for_node(ctx, nid, relation, how, score=None):
    n = ctx.nodes[nid]
    s = {"node_id": nid, "kind": n["kind"], "name": n["name"], "detail": (n.get("detail") or "")[:160], "relation": relation, "how": how,
         "loc": n.get("loc"), "stale": None}
    if score is not None:
        s["score"] = round(score, 2)
    if n["kind"] in ("figure", "table", "section", "equation", "item"):
        ch = ctx.chain(nid)
        s["chain"] = ch
        # a figure's own image file is not evidence of where it came from: traced means a script, a run or a result file is behind it
        s["traced"] = bool(ch["code"] or ch["runs"] or any(ctx.nodes[x]["kind"] != "asset" for x in ch["results"]))
        for x in [nid] + ch["results"] + ch["code"] + ch["runs"] + ch["settings"]:
            if x in ctx.stale:
                s["stale"] = ctx.stale[x]
                break
    else:
        s["traced"] = n["kind"] in ("result", "data", "code", "run", "asset")
        if nid in ctx.stale:
            s["stale"] = ctx.stale[nid]
    return s


def draft(G, alarms=None, findings=None):
    """-> list of drafted claims (no user decisions applied)."""
    P = G.paper
    ctx = _Ctx(G, alarms, findings)
    claims = []
    if P is None:
        return claims, ctx
    label_node = {n["attrs"].get("tex_label"): nid for nid, n in G.nodes.items() if n.get("attrs") and n["attrs"].get("tex_label")}
    floats = [(nid, n) for nid, n in G.nodes.items() if n["kind"] in ("figure", "table")]
    float_words = {nid: words((n["attrs"].get("caption") or "") + " " + (n.get("detail") or "")) for nid, n in floats}

    def suggest(text, have):
        w = words(text)
        if len(w) < 2:
            return []
        out = []
        for nid, fw in float_words.items():
            if nid in have or not fw:
                continue
            inter = w & fw
            score = len(inter) / (len(fw) ** 0.5 * len(w) ** 0.5)
            if len(inter) >= 2 and score >= 0.25:
                out.append((score, nid))
        out.sort(reverse=True)
        return out[:3]

    # --- core message: one sentence picked from the abstract (the researcher can reword it); the whole abstract is kept too
    th = G.nodes.get("thesis")
    if th:
        tu = next((u for u in P.units if u["kind"] == "thesis"), None)
        full = detex(" ".join(l.code for l in P.lines[tu["begin"]:tu["end"] + 1])) if tu else th["attrs"].get("text", "")
        title = next((detex(m.group(1)) for l in P.lines for m in [TITLE_RE.search(l.code)] if m), "")
        contrib_words = set()
        for it in _contribution_items(P):
            contrib_words |= words(it["text"])
        claims.append({"id": "core", "kind": "core", "label": "Core message", "text": cut(pick_core(full, title, contrib_words), 600),
                       "abstract": full[:4000], "title": title[:300], "loc": th["loc"], "support": [], "children": []})

    # --- contributions
    for k, it in enumerate(_contribution_items(P), 1):
        sup, have = [], set()
        for r in it["refs"]:
            nid = label_node.get(r)
            if nid and nid not in have:
                have.add(nid)
                sup.append(_support_for_node(ctx, nid, "evidence", "detected"))
        claims.append({"id": "contrib:%d" % k, "kind": "contribution", "label": "Contribution %d" % k, "text": cut(it["text"], 600),
                       "loc": _loc(P, it["begin"], it["end"]), "support": sup, "_refs": it["refs"], "_have": have})

    # --- research questions
    for name, idx in sorted(P.rqs.items()):
        nid = "rq:" + name
        n = G.nodes.get(nid)
        if not n:
            continue
        sup, have = [], set()
        rq_rx = re.compile(r"\b%s\b" % re.escape(name).replace("RQ", r"RQ\s?"))
        text = n["attrs"].get("text", n["detail"])
        m = re.search(rq_rx.pattern + r"\}?\s*[:.)\-]*\s*(.+?[?])", detex(P.lines[idx].code)) if 0 <= idx < len(P.lines) else None
        if m:
            text = m.group(1).strip()          # the question itself, not the whole line it sits on
        for ln in P.lines:
            # only the sentences that name this question count, so "RQ1 is answered by Table 1. RQ2 by Table 2." splits correctly
            for sent in re.split(r"(?<=[.;?!])\s+", ln.code):
              if rq_rx.search(sent) and not re.search(r"\bRQ\s?\d+\b", rq_rx.sub("", sent)):
                for grp in lx.REF_RE.findall(sent):
                    for r in grp.split(","):
                        f = label_node.get(r.strip())
                        if f and f not in have and G.nodes[f]["kind"] in ("figure", "table"):
                            have.add(f)
                            sup.append(_support_for_node(ctx, f, "evidence", "detected"))
        for e in G.edges.values():
            if e["kind"] == "answers" and e["from"] == nid:
                for f in ctx.floats_in(e["to"]):
                    if f not in have:   # in a section that discusses the question, but not named with it: a suggestion only
                        have.add(f)
                        sup.append(_support_for_node(ctx, f, "evidence", "suggested", 0.5))
        claims.append({"id": nid, "kind": "question", "label": name, "text": cut(text, 600), "loc": n["loc"],
                       "support": sup, "_have": have, "_refs": []})

    # --- formal statements
    blocks = _blocks(P)
    by_label = {b["label"]: b for b in blocks if b["label"] and b["kind"] != "proof"}
    proofs = [b for b in blocks if b["kind"] == "proof"]
    proof_of = {}
    for i, ln in enumerate(P.lines):
        for m in PROOF_OF_RE.finditer(ln.code):
            proof_of.setdefault(m.group(1).strip(), i)
    statements = [b for b in blocks if b["kind"] in FORMAL]
    for b in statements:
        cid = "stmt:" + (b["label"] or "%s%d" % (b["kind"], b["number"]))
        name = "%s %d" % (FORMAL[b["kind"]], b["number"]) + (" (%s)" % b["title"] if b["title"] else "")
        sup, issues = [], []
        # proof: the proof environment right after the statement, or a "Proof of \ref{label}" anywhere
        pr = next((p for p in proofs if 0 <= p["begin"] - b["end"] <= 3), None)
        where = None
        if pr is None and b["label"] and b["label"] in proof_of:
            i = proof_of[b["label"]]
            pr = next((p for p in proofs if p["begin"] <= i <= p["end"] or 0 <= p["begin"] - i <= 3), None)
            where = i
        if pr is not None:
            sup.append({"node_id": None, "kind": "proof", "name": "Proof" + (" (appendix)" if pr["in_appendix"] else ""), "detail": cut(pr["text"], 160),
                        "relation": "proof", "how": "detected", "loc": _loc(P, pr["begin"], pr["end"]), "stale": None, "traced": True})
        elif where is not None:
            sup.append({"node_id": None, "kind": "proof", "name": "Proof section", "detail": detex(P.lines[where].code)[:160], "relation": "proof",
                        "how": "detected", "loc": _loc(P, where), "stale": None, "traced": True})
        else:
            issues.append("No proof found for this statement.")
        used = list(dict.fromkeys(b["refs"] + (pr["refs"] if pr else [])))
        for r in used:
            dep = by_label.get(r)
            if dep is None or dep is b:
                if r not in P.labels and r != b["label"]:
                    issues.append("Refers to [%s], which is not defined." % r)
                continue
            dname = "%s %d" % ((FORMAL.get(dep["kind"]) or PREMISE[dep["kind"]]), dep["number"])
            sup.append({"node_id": None, "kind": dep["kind"], "name": dname, "detail": cut(dep["text"], 160),
                        "relation": "assumes" if dep["kind"] in PREMISE else "uses", "how": "detected", "loc": _loc(P, dep["begin"], dep["end"]),
                        "stale": None, "traced": True, "claim_id": "stmt:" + dep["label"] if dep["kind"] in FORMAL else None})
        claims.append({"id": cid, "kind": b["kind"], "label": name, "text": b["text"], "loc": _loc(P, b["begin"], b["end"]),
                       "support": sup, "issues": issues, "formal": True, "in_appendix": b["in_appendix"]})

    # --- suggestions for empirical claims, numbers that are not traced
    stmt_by_label = {c["id"][5:]: c for c in claims if c.get("formal")}
    for c in claims:
        if c.get("formal") or c["kind"] == "core":
            continue
        have = c.pop("_have", set())
        for r in c.pop("_refs", None) or []:
            st = stmt_by_label.get(r)
            if st:   # "we prove ... (Theorem 1)": the claim rests on that statement and on its proof
                proved = any(x["relation"] == "proof" for x in st["support"]) and not st["issues"]
                c["support"].append({"node_id": None, "kind": st["kind"], "name": st["label"], "detail": st["text"][:160], "relation": "stated as",
                                     "how": "detected", "loc": st["loc"], "stale": None, "traced": proved, "claim_id": st["id"]})
                if not proved:
                    c.setdefault("issues", []).append("%s has no complete proof yet." % st["label"])
        for score, nid in suggest(c["text"], have):
            c["support"].append(_support_for_node(ctx, nid, "evidence", "suggested", score))
    # "[thm:bound]" -> "Theorem 1", "[tab:rank]" -> "Table 1": the names a reader would use
    names = {}
    for b in blocks:
        if b["label"] and b["kind"] != "proof":
            names[b["label"]] = "%s %d" % (FORMAL.get(b["kind"]) or PREMISE[b["kind"]], b["number"])
    for lab, nid in label_node.items():
        names.setdefault(lab, G.nodes[nid]["name"])

    def pretty(t):
        t = re.sub(r"\[([^\]\s]+)\]", lambda m: names.get(m.group(1), m.group(0)), t or "")
        t = re.sub(r"\b(Theorem|Lemma|Proposition|Corollary|Assumption|Definition|Table|Section|Appendix|Claim)s?\s+(?=\1 \d)", "", t)   # "Theorem Theorem 1"
        return re.sub(r"\bFig(?:ure|\.)\s+(?=Fig\. \d)", "", t)
    for c in claims:
        c["text"] = pretty(c["text"])
        for s_ in c["support"]:
            s_["detail"] = pretty(s_.get("detail"))
        c["issues"] = [i for i in c.get("issues", [])]
    for c in claims:
        c.setdefault("issues", [])
        loc = c.get("loc") or {}
        for f in ctx.findings:
            if f.get("check") != "untraced_number":
                continue
            for ev in f.get("evidence", []):
                if ev.get("path") == loc.get("path") and loc.get("line") and ev.get("line") and loc["line"] <= ev["line"] <= (loc.get("end_line") or loc["line"]):
                    c["issues"].append("A number here was not found in any result file: %s" % (ev.get("text") or "").strip()[:80])
                    break
    return claims, ctx


def _status(c):
    sup = [s for s in c["support"] if s["how"] != "suggested"]
    if c.get("formal"):
        has_proof = any(s["relation"] == "proof" for s in sup)
        st = "supported" if has_proof and not c["issues"] else "partial" if has_proof else "unsupported"
    elif c["kind"] == "core":
        st = c.get("_rollup") or "unsupported"
    else:
        traced = [s for s in sup if s.get("traced")]
        st = "supported" if traced and not c["issues"] else "partial" if sup else "unsupported"
    c["status"] = st
    c["recheck"] = next((s["stale"] for s in sup if s.get("stale")), None)


def build(G, alarms, findings, store):
    """Drafts merged with the researcher's decisions -> the claims document."""
    drafted, ctx = draft(G, alarms, findings)
    store = store or {}
    ents = store.get("entries", {})
    by_id = {c["id"]: c for c in drafted}
    for m in store.get("manual", []):
        if m["id"] not in by_id:
            c = {"id": m["id"], "kind": m.get("kind", "claim"), "label": m.get("label") or "Your claim", "text": m["text"], "loc": None,
                 "support": [], "issues": [], "manual": True}
            drafted.append(c)
            by_id[c["id"]] = c
    for c in drafted:
        e = ents.get(c["id"], {})
        c["state"] = e.get("state") or ("confirmed" if c.get("manual") else "proposed")
        c["note"] = e.get("note", "")
        if e.get("text"):
            c["drafted_text"], c["text"] = c["text"], e["text"]
        drop = set(e.get("unlinks", []))
        for s in c["support"]:
            key = s.get("node_id") or s["name"]
            if key in e.get("links", []) and s["how"] == "suggested":
                s["how"] = "manual"
        c["support"] = [s for s in c["support"] if (s.get("node_id") or s["name"]) not in drop]
        have = {s.get("node_id") for s in c["support"]}
        for nid in e.get("links", []):
            if nid in ctx.nodes and nid not in have:
                c["support"].append(_support_for_node(ctx, nid, "evidence", "manual"))
        c.setdefault("issues", [])
    core = by_id.get("core")
    rest = [c for c in drafted if c["id"] != "core"]
    for c in rest:
        _status(c)
    if core:
        live = [c for c in rest if c["state"] != "rejected"]
        core["children"] = [c["id"] for c in live]
        sts = [c["status"] for c in live]
        core["_rollup"] = "unsupported" if not sts else "supported" if all(s == "supported" for s in sts) else \
            "unsupported" if all(s == "unsupported" for s in sts) else "partial"
        _status(core)
        core.pop("_rollup", None)
        core["recheck"] = next((c["recheck"] for c in live if c["recheck"]), None)
    live = [c for c in rest if c["state"] != "rejected"]
    counts = {"total": len(live), "supported": sum(c["status"] == "supported" for c in live), "partial": sum(c["status"] == "partial" for c in live),
              "unsupported": sum(c["status"] == "unsupported" for c in live), "recheck": sum(bool(c["recheck"]) for c in live),
              "proposed": sum(c["state"] == "proposed" for c in live), "confirmed": sum(c["state"] == "confirmed" for c in live)}
    return {"schema": SCHEMA, "has_paper": G.paper is not None, "core": core, "claims": rest, "counts": counts}


def table_rows(P, node_id, max_rows=14, max_cols=9):
    """Cells of the first tabular in a table float, as plain text. Best effort; None when it cannot be read."""
    u = next((x for x in P.units if x.get("id") == node_id), None)
    if not u:
        return None
    body = "\n".join(l.code for l in P.lines[u["begin"]:u["end"] + 1])
    m = re.search(r"\\begin\{(tabular[x*]?|tabu|longtable)\}(.*?)\\end\{\1\}", body, re.S)
    if not m:
        return None
    inner = re.sub(r"^\s*(?:\{[^{}]*\}|\[[^\]]*\])*(?:\{(?:[^{}]|\{[^{}]*\})*\})", "", m.group(2), count=1)
    inner = re.sub(r"\\(?:hline|toprule|midrule|bottomrule|centering|small|footnotesize|scriptsize)\b|\\(?:cline|cmidrule)(?:\([^)]*\))?\{[^}]*\}", " ", inner)
    rows = []
    for raw in re.split(r"\\\\(?:\[[^\]]*\])?", inner):
        if not raw.strip():
            continue
        cells = [detex(re.sub(r"\\multi(?:column|row)\{[^}]*\}\{[^}]*\}\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1", c)) for c in re.split(r"(?<!\\)&", raw)]
        rows.append([c[:40] for c in cells[:max_cols]])
        if len(rows) >= max_rows:
            break
    return rows or None


# ------------------------------------------------------------------ tree (crown = what the paper says, roots = what backs it)
BAND = {"proof": 1, "assumption": 1, "definition": 1, "condition": 1, "hypothesis": 1, "table": 1, "figure": 1, "section": 1, "equation": 1,
        "item": 1, "result": 2, "asset": 2, "data": 2, "code": 3, "config": 3, "run": 4}
SHORT = {"contribution": "C", "question": "Q", "theorem": "Thm", "lemma": "Lem", "proposition": "Prop", "corollary": "Cor", "claim": "C",
         "assumption": "A", "definition": "Def", "condition": "Cond", "hypothesis": "H"}


def _short(c):
    m = re.search(r"(\d+)", c["label"])
    if c.get("manual"):
        return "+" + c["id"].split(":")[1]
    if c["kind"] == "question":
        return c["label"][:6]
    return "%s%s%s" % (SHORT.get(c["kind"], "C"), "" if len(SHORT.get(c["kind"], "C")) == 1 else " ", m.group(1) if m else "")


def tree(doc, G, born=None):
    """Nodes and edges for the research tree. born(node_id | loc) -> ISO time or None."""
    born = born or (lambda *_: None)
    nodes, edges, seen = [], [], {}
    core = doc.get("core")
    live = [c for c in doc["claims"] if c["state"] != "rejected"]
    by_id = {c["id"]: c for c in live}

    def add(nid, **kw):
        if nid in seen:
            return seen[nid]
        kw["id"] = nid
        seen[nid] = kw
        nodes.append(kw)
        return kw

    def edge(a, b, kind, how="detected", stale=False):
        if a != b and not any(e["from"] == a and e["to"] == b for e in edges):
            edges.append({"from": a, "to": b, "kind": kind, "how": how, "stale": bool(stale)})

    if core:
        add("core", layer="core", kind="core", short="", title=core["text"], status=core["status"], recheck=bool(core["recheck"]),
            state=core.get("state", "proposed"), born=born(None, core.get("loc")))
    # which claims hang under another claim ("stated as Theorem 1", "uses Lemma 2")
    parent = {}
    for c in live:
        for s_ in c["support"]:
            cid = s_.get("claim_id")
            if cid in by_id and cid != c["id"] and s_["how"] != "suggested":
                parent.setdefault(cid, c["id"])
    for c in live:
        add(c["id"], layer="claim", kind=c["kind"], short=_short(c), title=c["text"][:400], label=c["label"], status=c["status"],
            recheck=bool(c["recheck"]), state=c["state"], formal=bool(c.get("formal")), depth=0, born=born(None, c.get("loc")))
    for c in live:   # depth in the crown: 1 = directly under the core message
        d, cur, guard = 1, c["id"], 0
        while cur in parent and guard < 6:
            cur, d, guard = parent[cur], d + 1, guard + 1
        seen[c["id"]]["depth"] = d
        seen[c["id"]]["parent"] = parent.get(c["id"], "core" if core else None)
        if seen[c["id"]]["parent"]:
            edge(seen[c["id"]]["parent"], c["id"], "branch")
    in_tree = lambda n: n in G.nodes and G.nodes[n]["kind"] in BAND
    for c in live:
        real = 0
        for s_ in c["support"]:
            sug = s_["how"] == "suggested"
            if s_.get("claim_id") in by_id:
                if parent.get(s_["claim_id"]) != c["id"]:
                    edge(c["id"], s_["claim_id"], "uses", s_["how"])       # a second claim leaning on the same statement
                real += not sug
                continue
            nid = s_.get("node_id")
            if nid and in_tree(nid):
                n = G.nodes[nid]
                add(nid, layer="root", band=BAND[n["kind"]], kind=n["kind"], short=n["name"].split(" · ")[0][:14], title=n["name"],
                    node_id=nid, traced=bool(s_.get("traced")), born=born(nid, n.get("loc")))
                edge(c["id"], nid, "support", s_["how"], s_.get("stale"))
                if not sug:
                    real += 1
                    ch = s_.get("chain") or {}
                    members = [x for x in ch.get("results", []) + ch.get("code", []) + ch.get("runs", []) + ch.get("settings", []) if in_tree(x)
                               and not (n["kind"] == "figure" and G.nodes[x]["kind"] == "asset" and G.nodes[x]["repo"] == n["repo"])]
                    for x in members:
                        m = G.nodes[x]
                        add(x, layer="root", band=BAND[m["kind"]], kind=m["kind"], short=m["name"].rsplit("/", 1)[-1][:16], title=m["name"],
                            node_id=x, traced=True, born=born(x, None))
                    mset = set(members) | {nid}
                    linked = set()
                    for e in G.edges.values():
                        if e["kind"] in SUPPORT_REL and e["status"] in ("detected", "approved") and e["from"] in mset and e["to"] in mset:
                            edge(e["from"], e["to"], "trace", "detected", s_.get("stale"))
                            linked.add(e["to"])
                    for x in members:      # anything the graph did not link explicitly hangs from the paper item
                        if x not in linked:
                            edge(nid, x, "trace", "detected", s_.get("stale"))
            elif not nid:
                rid = "x:%s:%s" % (s_["kind"], s_["name"]) if s_["relation"] != "proof" else "x:proof:" + c["id"]
                add(rid, layer="root", band=1, kind=s_["kind"], short=s_["name"][:14] if s_["relation"] != "proof" else "Proof", title=s_["name"],
                    loc=s_.get("loc"), traced=True, born=born(None, s_.get("loc")))
                edge(c["id"], rid, "support", s_["how"])
                real += not sug
        if not real:
            mid = "missing:" + c["id"]
            add(mid, layer="root", band=1, kind="missing", short="?", title="Nothing backs this yet", traced=False, born=None)
            edge(c["id"], mid, "missing")
    shared = {}
    for e in edges:
        if e["kind"] == "support" and e["how"] != "suggested":
            shared[e["to"]] = shared.get(e["to"], 0) + 1
    for n in nodes:
        if n["layer"] == "root":
            n["shared"] = shared.get(n["id"], 0)
    times = sorted(n["born"] for n in nodes if n.get("born"))
    return {"schema": "lemmata.tree/1", "nodes": nodes, "edges": edges, "counts": doc["counts"],
            "span": {"start": times[0], "end": times[-1]} if times else None, "dated": len(times), "undated": len(nodes) - len(times)}


# ------------------------------------------------------------------ decisions
def load(hub):
    d = hub.read_json("claims.json", None)
    if not isinstance(d, dict):
        d = {}
    d.setdefault("schema", SCHEMA)
    d.setdefault("entries", {})
    d.setdefault("manual", [])
    return d


def decide(store, known_ids, cid, state=None, text=None, note=None):
    if cid not in known_ids:
        raise NotFound("unknown claim %r" % cid)
    e = store["entries"].setdefault(cid, {})
    if state is not None:
        if state not in ("proposed", "confirmed", "rejected"):
            raise BadRequest("state must be proposed, confirmed or rejected")
        e["state"] = state
    if text is not None:
        if not isinstance(text, str) or len(text) > 1200:
            raise BadRequest("text must be at most 1200 characters")
        e["text"] = text.strip()
    if note is not None:
        if not isinstance(note, str) or len(note) > 2000:
            raise BadRequest("note must be at most 2000 characters")
        e["note"] = note
    return e


def link(store, known_ids, nodes, cid, target, on=True):
    if cid not in known_ids:
        raise NotFound("unknown claim %r" % cid)
    if not isinstance(target, str) or not target or len(target) > 300:
        raise BadRequest("target is required")
    e = store["entries"].setdefault(cid, {})
    links, unlinks = e.setdefault("links", []), e.setdefault("unlinks", [])
    if on:
        if target not in nodes and target not in unlinks:
            raise NotFound("unknown item %r" % target)
        if target in unlinks:
            unlinks.remove(target)
        if target in nodes and target not in links:
            links.append(target)
    else:
        if target in links:
            links.remove(target)
        if target not in unlinks:
            unlinks.append(target)
    return e


def add_manual(store, text, kind="claim"):
    if not isinstance(text, str) or not text.strip() or len(text) > 1200:
        raise BadRequest("text must be 1 to 1200 characters")
    if len(store["manual"]) >= 200:
        raise BadRequest("too many claims")
    n = 1 + max([int(m["id"].split(":")[1]) for m in store["manual"]] or [0])
    m = {"id": "mine:%d" % n, "text": text.strip(), "kind": kind if kind in ("claim", "contribution", "question") else "claim"}
    store["manual"].append(m)
    return m


def remove_manual(store, cid):
    n = len(store["manual"])
    store["manual"] = [m for m in store["manual"] if m["id"] != cid]
    store["entries"].pop(cid, None)
    if len(store["manual"]) == n:
        raise NotFound("unknown claim %r" % cid)


# ------------------------------------------------------------------ export
MARK = {"supported": "supported", "partial": "partly supported", "unsupported": "NOT supported"}


def to_markdown(doc, project_name, when):
    out = ["# Claims: %s" % project_name, "", "Generated by Lemmata on %s. Statuses are computed from the repository; the wording and the"
           " confirmations are yours." % when, ""]
    core = doc.get("core")
    if core:
        out += ["## Core message", "", "> " + core["text"], "", "Status: **%s**" % MARK[core["status"]], ""]
    out += ["## Claims", ""]
    for c in doc["claims"]:
        if c["state"] == "rejected":
            continue
        out.append("### %s%s" % (c["label"], "" if c["state"] == "confirmed" else " (draft, not confirmed)"))
        out += ["", c["text"], "", "- Status: **%s**%s" % (MARK[c["status"]], " — recheck: %s" % c["recheck"] if c["recheck"] else "")]
        if c.get("loc"):
            out.append("- Where: `%s:%s`" % (c["loc"]["path"], c["loc"]["line"]))
        for s in c["support"]:
            if s["how"] == "suggested":
                continue
            w = " (`%s:%s`)" % (s["loc"]["path"], s["loc"]["line"]) if s.get("loc") and s["loc"].get("line") else ""
            ch = s.get("chain") or {}
            files = ", ".join("`%s`" % x.split("/", 1)[-1] for x in (ch.get("results", []) + ch.get("code", []))[:4])
            out.append("- %s: %s%s%s%s" % (s["relation"].capitalize(), s["name"], w, " <- " + files if files else "",
                                             "" if s.get("traced") else " — not traced to a result file or script"))
        for i in c["issues"]:
            out.append("- Issue: " + i)
        if c.get("note"):
            out.append("- Note: " + c["note"])
        out.append("")
    return "\n".join(out) + "\n"
