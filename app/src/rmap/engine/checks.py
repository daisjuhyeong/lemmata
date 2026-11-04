"""The 8 integrity checks (data-model 6). Neutral wording; every finding carries evidence."""
import hashlib
import math
import re
from collections import deque

from . import latex as lx
from . import refs as refsmod

CHECKS = [
    ("reference_unmatched", "Reference could not be matched", "warning"),
    ("main_appendix_mismatch", "Main text and appendix differ", "warning"),
    ("uncited_reference", "Reference not cited in the text", "info"),
    ("unreferenced_float", "Figure or table not referenced in the text", "info"),
    ("undefined_ref", "Reference to a label that is not defined", "warning"),
    ("undefined_cite", "Citation without a bibliography entry", "warning"),
    ("untraced_number", "Number not traced to a result file", "info"),
    ("figure_without_provenance", "Figure without a generating script", "info"),
]
NUM_TXT = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
MAX_TXT = 2_000_000


def fingerprint(check, fid, evidence):
    h = hashlib.sha256()
    for part in [check, fid] + [e["text"] for e in evidence]:
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


def _reachable_kinds(G, start):
    fwd = {}
    for e in G.edges.values():
        if e["propagates"]:
            fwd.setdefault(e["from"], []).append(e["to"])
    seen, dq = {start}, deque([start])
    kinds = set()
    while dq:
        x = dq.popleft()
        for y in fwd.get(x, ()):
            if y not in seen:
                seen.add(y)
                kinds.add(G.nodes[y]["kind"])
                dq.append(y)
    return kinds


def _text_numbers(G, trees):
    xs = []
    files = 0
    for n in G.nodes.values():
        if n["kind"] in ("result", "data", "doc", "config"):
            data = trees[n["repo"]].read(n["loc"]["path"])
            if data is None or len(data) > MAX_TXT:
                continue
            files += 1
            for m in NUM_TXT.finditer(data.decode("utf-8", "replace")):
                try:
                    xs.append(float(m.group(0)))
                except ValueError:
                    pass
    return xs, files


def run(G, trees):
    P = G.paper
    meta = {c: t for c, t, _ in CHECKS}
    sev = {c: s for c, _, s in CHECKS}
    findings, notes, status, warnings = [], {}, {}, []

    def emit(check, fid, message, nodes, evidence, details=None):
        ev = [e for e in evidence if e and e.get("path") and isinstance(e.get("line"), int) and e["line"] >= 1]
        if not ev:
            warnings.append("finding %s/%s dropped: no evidence" % (check, fid))
            return
        findings.append({"id": "%s/%s" % (check, fid), "check": check, "severity": sev[check], "title": meta[check],
                         "message": message, "nodes": nodes, "evidence": ev, "details": details or {},
                         "fingerprint": fingerprint(check, "%s/%s" % (check, fid), ev)})

    for c, _, _ in CHECKS:
        status[c], notes[c] = "ran", ""
    if P is None:
        for c, _, _ in CHECKS:
            status[c], notes[c] = "not_applicable", "no paper repo"
    else:
        prepo = G.paper_repo["id"]
        entries = G.bib_entries
        keys = {e["key"] for e in entries}
        cache = getattr(G, "cache", {"entries": {}})
        # reference_unmatched
        if not entries:
            status["reference_unmatched"] = status["uncited_reference"] = status["undefined_cite"] = "not_applicable"
            notes["reference_unmatched"] = notes["uncited_reference"] = notes["undefined_cite"] = "no .bib entries found"
        else:
            cnt = {"matched": 0, "not_found": 0, "unchecked": 0}
            for e in entries:
                st = refsmod.lookup_state(cache, e)
                if st == "matched":
                    cnt["matched"] += 1
                elif st == "not_found":
                    cnt["not_found"] += 1
                    rec = refsmod.record_for(cache, e)
                    emit("reference_unmatched", e["key"],
                         'Reference could not be matched: "%s" (%s) was not found in OpenAlex or Crossref (lookup %s).' % (
                             e["title"], e["key"], (rec.get("checked_at") or "")[:10] or "date unknown"),
                         ["ref:" + e["key"]], [{"repo": prepo, "path": e["path"], "line": e["line"], "text": e["line_text"], "role": "bib_entry", "page": None}],
                         {"lookup": rec})
                else:
                    cnt["unchecked"] += 1
            notes["reference_unmatched"] = "offline cache: %d matched, %d could not be matched, %d not checked" % (
                cnt["matched"], cnt["not_found"], cnt["unchecked"])
            # uncited
            if P.nocite_all:
                notes["uncited_reference"] = "\\nocite{*} present; check disabled"
            else:
                cited = {k for k, _ in P.cites}
                for e in entries:
                    if e["key"] not in cited:
                        emit("uncited_reference", e["key"], 'Reference "%s" is in the bibliography but is not cited in the text.' % e["key"],
                             ["ref:" + e["key"]], [{"repo": prepo, "path": e["path"], "line": e["line"], "text": e["line_text"], "role": "bib_entry", "page": None}])
            # undefined cites
            uses = {}
            for k, idx in P.cites:
                if k not in keys:
                    uses.setdefault(k, []).append(idx)
            for k in sorted(uses):
                nodes = sorted({G.units[P.owner[i]] for i in uses[k] if P.owner[i] is not None})
                emit("undefined_cite", k, 'Citation key "%s" has no entry in the bibliography.' % k, nodes,
                     [P.ev(i, "cite") for i in uses[k][:10]])
        # main/appendix
        if P.appendix_idx is None:
            status["main_appendix_mismatch"], notes["main_appendix_mismatch"] = "not_applicable", "no \\appendix found"
        else:
            for name in lx.HP_ALIASES:
                main = next(((i, v) for n, i, v in P.hparams if n == name and i < P.appendix_idx and v is not None), None)
                app = next(((i, v) for n, i, v in P.hparams if n == name and i > P.appendix_idx and v is not None), None)
                if not main or not app:
                    continue
                a, b = main[1], app[1]
                same = (a.lower() == b.lower()) if isinstance(a, str) else math.isclose(a, b, rel_tol=1e-9, abs_tol=0.0)
                if same:
                    continue
                fa = a if isinstance(a, str) else lx.fmt_number(a)
                fb = b if isinstance(b, str) else lx.fmt_number(b)
                lm, la = P.lines[main[0]], P.lines[app[0]]
                label = name.replace("_", " ").capitalize()
                nodes = [G.units[P.owner[i]] for i in (main[0], app[0]) if P.owner[i] is not None]
                emit("main_appendix_mismatch", name,
                     "%s differs between the main text (%s, %s:%d) and the appendix (%s, %s:%d)." % (label, fa, lm.path, lm.no, fb, la.path, la.no),
                     nodes, [P.ev(main[0], "main"), P.ev(app[0], "appendix")],
                     {"name": name, "main_value": fa, "appendix_value": fb})
        # unreferenced floats
        used = {lab for lab, _ in P.refs}
        for u in P.units:
            if u["kind"] not in ("figure", "table"):
                continue
            word = "Figure" if u["kind"] == "figure" else "Table"
            if u["label"] is None:
                emit("unreferenced_float", u["id"], '%s at %s:%d (%s) has no label, so it cannot be referenced in the text.' % (
                    word, P.lines[u["begin"]].path, P.lines[u["begin"]].no, u["name"]), [u["id"]], [P.ev(u["begin"], "begin")])
            elif u["label"] not in used:
                emit("unreferenced_float", u["label"], '%s "%s" (%s) is not referenced in the text.' % (word, u["label"], u["name"]),
                     [u["id"]], [P.ev(P.labels[u["label"]][1], "label")])
        # undefined refs
        uses = {}
        for lab, idx in P.refs:
            if lab not in P.labels:
                uses.setdefault(lab, []).append(idx)
        for lab in sorted(uses):
            nodes = sorted({G.units[P.owner[i]] for i in uses[lab] if P.owner[i] is not None})
            emit("undefined_ref", lab, 'Reference to "%s" has no matching label.' % lab, nodes, [P.ev(i, "ref") for i in uses[lab][:10]])
        # untraced numbers
        xs, nfiles = _text_numbers(G, trees)
        index = {}
        found = {}
        for val, idx in P.numbers:
            d = len(val.split(".")[1])
            if d not in index:
                index[d] = {round(x, d) for x in xs} | {round(100 * x, d) for x in xs}
            if float(val) in index[d]:
                continue
            k = P.owner[idx]
            if k is None:
                continue
            found.setdefault((G.units[k], val), []).append(idx)
        for (nid, val), idxs in sorted(found.items()):
            emit("untraced_number", "%s#%s" % (nid, val),
                 'Number %s in "%s" could not be traced to a result file (searched %d text files).' % (val, G.nodes[nid]["name"], nfiles),
                 [nid], [P.ev(i, "number") for i in idxs[:5]])
        # figures without provenance
        for u in P.units:
            if u["kind"] != "figure" or u.get("manual"):
                continue
            if _reachable_kinds(G, u["id"]) & {"code", "run"}:
                continue
            ev = P.ev(P.labels[u["label"]][1], "label") if u["label"] else P.ev(u["begin"], "begin")
            emit("figure_without_provenance", u["id"],
                 'Figure "%s" (%s) has no generating script or generated-by marker.' % (u["label"] or u["id"], u["name"]), [u["id"]], [ev])
    findings.sort(key=lambda f: ([c for c, _, _ in CHECKS].index(f["check"]), f["id"]))
    out_checks = []
    for c, title, _ in CHECKS:
        out_checks.append({"check": c, "title": title, "status": status[c],
                           "count": sum(1 for f in findings if f["check"] == c), "note": notes[c]})
    return {"schema": "rmap.findings/1", "checks": out_checks, "findings": findings}, warnings
