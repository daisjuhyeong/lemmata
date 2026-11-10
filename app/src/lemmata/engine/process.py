"""Research-process tools built on the scan: decision timeline, experiment ledger, feedback -> tasks, digest, ask.

All of it is deterministic (rules over git history and the dependency graph). No language model is called."""
import re
from datetime import datetime, timedelta

from .claims import detex, words
from .errors import BadRequest, NotFound

THEMES = [
    ("revert", re.compile(r"\brevert|roll ?back|undo\b", re.I), "Went back on an earlier change"),
    ("metric", re.compile(r"\bmetric|score|f1|auc|accuracy|precision|recall|evaluation protocol|eval(uation)? (set|split)\b", re.I), "Changed how results are measured"),
    ("baseline", re.compile(r"\bbaseline|compar(e|ison)|competitor|sota\b", re.I), "Changed the comparison"),
    ("data", re.compile(r"\bdataset|data ?split|preprocess|filter(ed|ing)?|benchmark|corpus\b", re.I), "Changed the data"),
    ("ablation", re.compile(r"\bablation|ablate|sensitivity\b", re.I), "Ablation work"),
    ("fix", re.compile(r"\bfix(es|ed)?|bug|typo|correct(ed|ion)?\b", re.I), "Fixes"),
    ("refactor", re.compile(r"\brefactor|clean ?up|rename|reorgani[sz]e|format|lint\b", re.I), "Housekeeping"),
]
DECISION_RE = re.compile(r"\b(switch(ed)? to|replace[sd]?|instead of|drop(ped)?|remove[sd]?|no longer|change[sd]? .{0,40}\bto\b|use .{0,30} instead|"
                         r"revert|adopt(ed)?|decide[sd]?|final(i[sz]e)?)\b", re.I)
KIND_TITLE = {"config": "Changed settings", "result": "New or changed results", "code": "Changed code", "paper": "Edited the paper",
              "run": "Recorded a run", "doc": "Updated notes", "asset": "Changed figures", "data": "Changed data files"}
REF_PATTERNS = [
    (re.compile(r"\b(?:table|tab\.?)\s*(\d+)\b", re.I), "table"), (re.compile(r"\b(?:figure|fig\.?)\s*(\d+)\b", re.I), "figure"),
    (re.compile(r"\b(?:section|sec\.?|§)\s*(\d+(?:\.\d+)*)\b", re.I), "section"),
    (re.compile(r"\b(?:appendix|app\.?)\s*([A-Z])\b"), "appendix"),
]
STMT_RE = re.compile(r"\b(theorem|lemma|proposition|corollary|assumption|definition)\s*(\d+)\b", re.I)


def _t(s):
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _file_kind(nodes, repo, role, path):
    n = nodes.get("file:%s/%s" % (repo, path))
    if n:
        return n["kind"]
    if path.startswith("runs/") and path.endswith(".json"):
        return "run"
    if role == "paper" or path.endswith((".tex", ".bib")):
        return "paper"
    return None


# ------------------------------------------------------------------ decision timeline
def timeline(events, nodes, repo_roles, claims_doc=None):
    """Commits grouped into readable steps (same repo, same day, same theme)."""
    support_of = {}
    for c in ([claims_doc["core"]] if claims_doc and claims_doc.get("core") else []) + (claims_doc["claims"] if claims_doc else []):
        for s in c.get("support", []):
            if s["how"] == "suggested":
                continue
            ch = s.get("chain") or {}
            for nid in [s.get("node_id")] + ch.get("results", []) + ch.get("code", []) + ch.get("runs", []) + ch.get("settings", []):
                if nid:
                    support_of.setdefault(nid, set()).add(c["id"])
    steps, started = [], set()
    for ev in events:
        if ev.get("kind") != "commit":
            continue
        repo, role = ev["repo"], repo_roles.get(ev["repo"], "code")
        kinds = {}
        touched = set()
        for f in ev.get("files", []):
            k = _file_kind(nodes, repo, role, f["path"])
            if k:
                kinds[k] = kinds.get(k, 0) + 1
            touched.add("file:%s/%s" % (repo, f["path"]))
        touched |= set(ev.get("changed_nodes") or [])
        theme, title = None, None
        for key, rx, ttl in THEMES:
            if rx.search(ev.get("subject") or ""):
                theme, title = key, ttl
                break
        if theme is None:
            top = max(kinds, key=lambda k: (k == "config", k == "result", kinds[k])) if kinds else None
            theme, title = (top or "other"), KIND_TITLE.get(top, "Other changes")
        decision = bool(DECISION_RE.search(ev.get("subject") or "")) or "config" in kinds or theme in ("metric", "baseline", "data", "revert")
        if ev["repo"] not in started:   # the first commit of a repository adds everything at once: a start, not a decision
            started.add(ev["repo"])
            if ev.get("files") and all(f.get("status") == "A" for f in ev["files"]):
                theme, title, decision = "start", "Started the %s" % ("paper" if role == "paper" else "code repository"), False
        day = (ev.get("time") or "")[:10]
        aff = sorted({c for n in touched for c in support_of.get(n, ())})
        last = steps[-1] if steps else None
        if last and last["repo"] == repo and last["day"] == day and last["theme"] == theme:
            last["commits"].append(_commit(ev))
            last["end"] = ev.get("time")
            last["decision"] = last["decision"] or decision
            last["affects"] = sorted(set(last["affects"]) | set(aff))
            for k, v in kinds.items():
                last["kinds"][k] = last["kinds"].get(k, 0) + v
            last["after_checkpoint"] = last["after_checkpoint"] or bool(ev.get("after_checkpoint"))
        else:
            steps.append({"id": "step:" + ev["id"].split(":", 1)[1], "repo": repo, "role": role, "day": day, "start": ev.get("time"), "end": ev.get("time"),
                          "theme": theme, "title": title, "decision": decision, "kinds": dict(kinds), "commits": [_commit(ev)], "affects": aff,
                          "after_checkpoint": bool(ev.get("after_checkpoint"))})
    for s in steps:
        subj = [c["subject"] for c in s["commits"]]
        s["summary"] = subj[0] if len(subj) == 1 else "%s (+%d more)" % (subj[0], len(subj) - 1)
    return {"schema": "lemmata.timeline/1", "steps": steps, "decisions": sum(1 for s in steps if s["decision"])}


def _commit(ev):
    return {"event_id": ev["id"], "short": ev.get("short"), "subject": ev.get("subject") or "", "time": ev.get("time"),
            "files": len(ev.get("files", [])), "flags": ev.get("flags", [])}


# ------------------------------------------------------------------ experiment ledger
def ledger(nodes, edges, events, claims_doc=None):
    """One row per result file: what made it, with which settings, when, who relies on it, and whether it is out of date."""
    last = {}
    for ev in events:
        if ev.get("kind") != "commit":
            continue
        for f in ev.get("files", []):
            last["file:%s/%s" % (ev["repo"], f["path"])] = (ev.get("time"), ev.get("short"), ev.get("subject"))
            if f["path"].startswith("runs/") and f["path"].endswith(".json"):
                last["run:%s/%s" % (ev["repo"], f["path"][5:-5])] = (ev.get("time"), ev.get("short"), ev.get("subject"))
    fwd, rev = {}, {}
    for e in edges:
        if e["status"] in ("detected", "approved"):
            fwd.setdefault(e["from"], []).append(e)
            rev.setdefault(e["to"], []).append(e)
    claim_of = {}
    for c in (claims_doc["claims"] if claims_doc else []):
        if c["state"] == "rejected":
            continue
        for s in c.get("support", []):
            if s["how"] == "suggested":
                continue
            for nid in (s.get("chain") or {}).get("results", []) + ([s["node_id"]] if s.get("node_id") else []):
                claim_of.setdefault(nid, []).append({"id": c["id"], "label": c["label"]})

    def upstream(nid):
        seen, todo, out = {nid}, [nid], []
        while todo:
            for e in fwd.get(todo.pop(), []):
                if e["kind"] in ("produced_by", "generated_by", "executes", "reads", "imports") and e["to"] not in seen and e["to"] in nodes:
                    seen.add(e["to"])
                    out.append(e["to"])
                    todo.append(e["to"])
        return out

    rows = []
    for nid, n in nodes.items():
        if n["kind"] != "result" and not (n["kind"] == "asset" and any(e["kind"] in ("produced_by", "generated_by") for e in fwd.get(nid, []))):
            continue
        ups = upstream(nid)
        made = last.get(nid)
        newer = []
        for u in ups:
            lu = last.get(u)
            if made and lu and _t(lu[0]) and _t(made[0]) and _t(lu[0]) > _t(made[0]):
                newer.append({"node_id": u, "name": nodes[u]["name"], "kind": nodes[u]["kind"], "time": lu[0], "short": lu[1], "subject": lu[2]})
        used_by = [{"node_id": e["from"], "name": nodes[e["from"]]["name"], "kind": nodes[e["from"]]["kind"]}
                   for e in rev.get(nid, []) if e["kind"] in ("traces_to", "includes", "value_match") and e["from"] in nodes]
        runs = [u for u in ups if nodes[u]["kind"] == "run"]
        claims = []
        for x in [nid] + [u["node_id"] for u in used_by]:
            for c in claim_of.get(x, []):
                if c not in claims:
                    claims.append(c)
        rows.append({
            "node_id": nid, "name": n["name"], "repo": n["repo"], "kind": n["kind"],
            "made": {"time": made[0], "short": made[1], "subject": made[2]} if made else None,
            "runs": [{"node_id": r, "name": nodes[r]["name"], "command": nodes[r]["attrs"].get("command"), "started_at": nodes[r]["attrs"].get("started_at")} for r in runs],
            "code": [{"node_id": u, "name": nodes[u]["name"]} for u in ups if nodes[u]["kind"] == "code"],
            "settings": [{"node_id": u, "name": nodes[u]["name"]} for u in ups if nodes[u]["kind"] == "config"],
            "used_by": used_by, "claims": claims,
            "status": "stale" if newer else "unknown" if not ups else "current", "newer": sorted(newer, key=lambda x: x["time"], reverse=True),
        })
    order = {"stale": 0, "unknown": 1, "current": 2}
    rows.sort(key=lambda r: (order[r["status"]], r["name"]))
    return {"schema": "lemmata.ledger/1", "rows": rows,
            "counts": {"stale": sum(r["status"] == "stale" for r in rows), "unknown": sum(r["status"] == "unknown" for r in rows),
                       "current": sum(r["status"] == "current" for r in rows), "unused": sum(not r["used_by"] for r in rows)}}


# ------------------------------------------------------------------ feedback -> tasks
def split_feedback(text):
    """One task per bullet, numbered line or sentence."""
    text = text.replace("\r", "")
    parts = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(?:[-*•·]|\d+[.)]|\[\s?\]|\(\d+\))\s+(.*)$", line)
        if m:
            parts.append(m.group(1).strip())
        elif len(text.split("\n")) > 1 and len(line) < 400:
            parts.append(line)
        else:
            parts += [s.strip() for s in re.split(r"(?<=[.!?。])\s+", line) if s.strip()]
    return [p for p in parts if len(p) >= 6][:60]


def match_targets(text, nodes, claims_doc):
    """Paper items, files and claims a piece of feedback points at."""
    hits, seen = [], set()

    def add(nid, why):
        if nid in nodes and nid not in seen:
            seen.add(nid)
            n = nodes[nid]
            hits.append({"node_id": nid, "name": n["name"], "kind": n["kind"], "why": why})

    low = text.lower()
    for rx, kind in REF_PATTERNS:
        for m in rx.finditer(text):
            num = m.group(1)
            for nid, n in nodes.items():
                a = n.get("attrs") or {}
                if kind in ("table", "figure") and n["kind"] == kind and str(a.get("number")) == num and not a.get("in_appendix"):
                    add(nid, "named")
                elif kind == "section" and n["kind"] == "section" and str(a.get("number")) == num and not a.get("in_appendix"):
                    add(nid, "named")
                elif kind == "appendix" and n["kind"] == "section" and str(a.get("number")) == num and a.get("in_appendix"):
                    add(nid, "named")
    for nid, n in nodes.items():
        if n["kind"] in ("code", "config", "result", "data", "asset", "doc"):
            base = n["name"].rsplit("/", 1)[-1].lower()
            if len(base) > 4 and base in low:
                add(nid, "named")
        elif n["kind"] == "section":
            title = ((n.get("attrs") or {}).get("title") or "").lower()
            if len(title) > 5 and title in low:
                add(nid, "named")
    cl = []
    w = words(text)
    for c in (claims_doc["claims"] if claims_doc else []):
        if c["state"] == "rejected":
            continue
        m = STMT_RE.search(text)
        named = bool(m and c["label"].lower().startswith("%s %s" % (m.group(1).lower(), m.group(2))))
        cw = words(c["text"])
        inter = w & cw
        score = len(inter) / ((len(w) * len(cw)) ** 0.5) if w and cw else 0
        if named or (len(inter) >= 2 and score >= 0.3):
            cl.append({"id": c["id"], "label": c["label"], "why": "named" if named else "similar wording", "score": round(1.0 if named else score, 2)})
    cl.sort(key=lambda x: -x["score"])
    return hits, cl[:3]


def also_check(targets, nodes, edges):
    """Things that rest on (or feed) the targets: change one, recheck these."""
    rev, fwd = {}, {}
    for e in edges:
        if e.get("propagates"):
            rev.setdefault(e["to"], []).append(e["from"])
            fwd.setdefault(e["from"], []).append(e["to"])
    seen = {t["node_id"] for t in targets}
    out, todo = [], [(t["node_id"], 0) for t in targets]
    while todo:
        cur, d = todo.pop(0)
        if d >= 3:
            continue
        for nxt in rev.get(cur, []) + (fwd.get(cur, []) if d == 0 else []):
            if nxt in seen or nxt not in nodes:
                continue
            seen.add(nxt)
            n = nodes[nxt]
            out.append({"node_id": nxt, "name": n["name"], "kind": n["kind"], "depth": d + 1})
            todo.append((nxt, d + 1))
    return out[:12]


def load_tasks(hub):
    d = hub.read_json("tasks.json", None)
    if not isinstance(d, dict):
        d = {}
    d.setdefault("schema", "lemmata.tasks/1")
    d.setdefault("tasks", [])
    d.setdefault("batches", [])
    return d


def add_feedback(store, text, source, nodes, edges, claims_doc, now):
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise BadRequest("feedback must be 1 to 20000 characters")
    if source is not None and (not isinstance(source, str) or len(source) > 120):
        raise BadRequest("source must be at most 120 characters")
    parts = split_feedback(text)
    if not parts:
        raise BadRequest("no feedback items found")
    bid = "fb%d" % (1 + len(store["batches"]))
    store["batches"].append({"id": bid, "source": (source or "").strip() or "Feedback", "created": now, "text": text.strip()[:20000]})
    n0 = 1 + max([int(t["id"][1:]) for t in store["tasks"]] or [0])
    made = []
    for i, p in enumerate(parts):
        targets, cl = match_targets(p, nodes, claims_doc)
        t = {"id": "t%d" % (n0 + i), "batch": bid, "text": p, "state": "open", "created": now, "done_at": None, "note": "",
             "targets": targets, "claims": cl}
        store["tasks"].append(t)
        made.append(t)
    return made


def tasks_view(store, nodes, edges):
    out = []
    src = {b["id"]: b for b in store["batches"]}
    for t in store["tasks"]:
        v = dict(t)
        v["targets"] = [x for x in t["targets"] if x["node_id"] in nodes]
        v["also_check"] = also_check(v["targets"], nodes, edges) if t["state"] == "open" else []
        b = src.get(t["batch"]) or {}
        v["source"], v["batch_created"] = b.get("source"), b.get("created")
        out.append(v)
    return {"schema": "lemmata.tasks/1", "tasks": out, "batches": [{k: b[k] for k in ("id", "source", "created")} for b in store["batches"]],
            "counts": {"open": sum(t["state"] == "open" for t in out), "done": sum(t["state"] == "done" for t in out)}}


def set_task(store, nodes, tid, state=None, note=None, add_target=None, remove_target=None, text=None, now=None):
    t = next((x for x in store["tasks"] if x["id"] == tid), None)
    if t is None:
        raise NotFound("unknown task %r" % tid)
    if state is not None:
        if state not in ("open", "done", "dropped"):
            raise BadRequest("state must be open, done or dropped")
        t["state"] = state
        t["done_at"] = now if state != "open" else None
    if note is not None:
        if not isinstance(note, str) or len(note) > 2000:
            raise BadRequest("note must be at most 2000 characters")
        t["note"] = note
    if text is not None:
        if not isinstance(text, str) or not text.strip() or len(text) > 1000:
            raise BadRequest("text must be 1 to 1000 characters")
        t["text"] = text.strip()
    if add_target:
        if add_target not in nodes:
            raise NotFound("unknown item %r" % add_target)
        if all(x["node_id"] != add_target for x in t["targets"]):
            n = nodes[add_target]
            t["targets"].append({"node_id": add_target, "name": n["name"], "kind": n["kind"], "why": "added by you"})
    if remove_target:
        t["targets"] = [x for x in t["targets"] if x["node_id"] != remove_target]
    return t


# ------------------------------------------------------------------ digest
def digest(project, tl, led, claims_doc, tasks, alarms, now_iso, days=7):
    now = _t(now_iso) or datetime.now().astimezone()
    since = now - timedelta(days=days)
    recent = [s for s in tl["steps"] if _t(s["end"]) and _t(s["end"]) >= since]
    commits = sum(len(s["commits"]) for s in recent)
    decisions = [s for s in recent if s["decision"]]
    cc = claims_doc["counts"]
    weak = [c for c in claims_doc["claims"] if c["state"] != "rejected" and (c["status"] != "supported" or c["recheck"])]
    stale = [r for r in led["rows"] if r["status"] == "stale"]
    open_tasks = [t for t in tasks["tasks"] if t["state"] == "open"]
    recheck = sum(len(g.get("changed", [])) + len(g.get("downstream", [])) for g in (alarms or {}).get("groups", []))
    L = ["*%s — the last %d days*" % (project, days), ""]
    L.append("• %d commit%s in %d step%s%s" % (commits, "" if commits == 1 else "s", len(recent), "" if len(recent) == 1 else "s",
                                             ", %d of them decisions" % len(decisions) if decisions else ""))
    for s in decisions[:5]:
        L.append("    – %s: %s (%s)" % (s["day"], s["summary"], s["title"].lower()))
    L.append("• Claims: %d supported, %d partly, %d not supported%s" % (cc["supported"], cc["partial"], cc["unsupported"],
                                                                      ", %d still drafts" % cc["proposed"] if cc["proposed"] else ""))
    for c in weak[:5]:
        L.append("    – %s: %s%s" % (c["label"], {"supported": "supported", "partial": "partly supported", "unsupported": "not supported"}[c["status"]],
                                     " — recheck after “%s”" % c["recheck"] if c["recheck"] else ""))
    if stale:
        L.append("• %d result file%s older than the code or settings behind %s:" % (len(stale), "" if len(stale) == 1 else "s", "it" if len(stale) == 1 else "them"))
        for r in stale[:5]:
            L.append("    – %s (changed since: %s)" % (r["name"], ", ".join(x["name"] for x in r["newer"][:2])))
    L.append("• %d open task%s from feedback, %d thing%s to recheck" % (len(open_tasks), "" if len(open_tasks) == 1 else "s", recheck, "" if recheck == 1 else "s"))
    for t in open_tasks[:5]:
        L.append("    – %s" % t["text"][:120])
    return {"schema": "lemmata.digest/1", "generated_at": now_iso, "days": days, "text": "\n".join(L),
            "numbers": {"commits": commits, "steps": len(recent), "decisions": len(decisions), "claims": cc, "stale_results": len(stale),
                        "open_tasks": len(open_tasks), "recheck": recheck}}


# ------------------------------------------------------------------ ask (search with rules, not a model)
def ask(q, nodes, edges, claims_doc, tl, led, tasks, findings):
    if not isinstance(q, str) or not q.strip() or len(q) > 500:
        raise BadRequest("question must be 1 to 500 characters")
    low = q.lower()
    w = words(q)
    answers = []
    all_claims = ([claims_doc["core"]] if claims_doc.get("core") else []) + claims_doc["claims"]

    def claim_card(c):
        return {"type": "claim", "id": c["id"], "title": c["label"], "text": c["text"][:300], "status": c["status"], "recheck": c["recheck"],
                "support": [{"name": s["name"], "relation": s["relation"], "how": s["how"], "node_id": s.get("node_id"), "traced": s.get("traced")}
                            for s in c["support"]][:8], "issues": c["issues"][:4]}

    targets, cl = match_targets(q, nodes, claims_doc)
    intent = None
    if re.search(r"\b(unsupported|not supported|weak|missing (proof|evidence)|no (proof|evidence)|gaps?)\b", low):
        intent = "gaps"
        for c in all_claims:
            if c["id"] != "core" and c["state"] != "rejected" and c["status"] != "supported":
                answers.append(claim_card(c))
    elif re.search(r"\b(stale|out of date|outdated|old results?|rerun|re-run)\b", low):
        intent = "stale"
        for r in led["rows"]:
            if r["status"] == "stale":
                answers.append({"type": "result", "id": r["node_id"], "title": r["name"],
                                "text": "Older than: " + ", ".join("%s (%s)" % (x["name"], (x["time"] or "")[:10]) for x in r["newer"][:3]),
                                "used_by": [u["name"] for u in r["used_by"]]})
    elif re.search(r"\b(what changed|recent(ly)?|last week|this week|history|decisions?|timeline)\b", low):
        intent = "changes"
        for s in [s for s in reversed(tl["steps"]) if s["decision"] or "decision" not in low][:8]:
            answers.append({"type": "step", "id": s["id"], "title": "%s — %s" % (s["day"], s["title"]), "text": s["summary"], "affects": s["affects"]})
    elif re.search(r"\b(todo|to-do|tasks?|feedback|advisor)\b", low):
        intent = "tasks"
        for t in tasks["tasks"]:
            if t["state"] == "open":
                answers.append({"type": "task", "id": t["id"], "title": t["text"][:120], "text": "From: %s" % (t.get("source") or "feedback"),
                                "targets": [x["name"] for x in t["targets"]]})
    elif re.search(r"\b(depend\w*|rests? on|relies on|rely on|affect\w*|impact\w*|breaks?|if i change|downstream|uses?)\b", low) and targets:
        intent = "impact"
        for t in targets[:3]:
            dn = also_check([t], nodes, edges)
            answers.append({"type": "impact", "id": t["node_id"], "title": "If %s changes" % t["name"],
                            "text": ("Recheck: " + ", ".join(x["name"] for x in dn)) if dn else "Nothing in the paper is linked to it.",
                            "nodes": [x["node_id"] for x in dn]})
    if intent is None or not answers:
        intent = intent or "search"
        scored = []
        for c in all_claims:
            cw = words(c["text"] + " " + c["label"])
            s = len(w & cw)
            if any(x["id"] == c["id"] for x in cl):
                s += 3
            if s:
                scored.append((s + 0.5, claim_card(c)))
        for t in targets:
            n = nodes[t["node_id"]]
            scored.append((4, {"type": "item", "id": t["node_id"], "title": n["name"], "text": (n.get("detail") or "")[:300], "kind": n["kind"]}))
        for nid, n in nodes.items():
            if n["kind"] in ("figure", "table", "section"):
                s = len(w & words((n.get("detail") or "") + " " + n["name"]))
                if s >= 2 and all(a[1].get("id") != nid for a in scored):
                    scored.append((s, {"type": "item", "id": nid, "title": n["name"], "text": (n.get("detail") or "")[:300], "kind": n["kind"]}))
        for f in (findings or {}).get("findings", []):
            s = len(w & words(f.get("message") or ""))
            if s >= 2:
                scored.append((s - 0.5, {"type": "check", "id": f["id"], "title": "Check", "text": (f.get("message") or "")[:300]}))
        scored.sort(key=lambda x: -x[0])
        answers = [a for _, a in scored[:8]]
    prompt = ("Use the lemmata MCP tools on this project to answer: %s\nStart from the claims and their support; quote file paths and line "
              "numbers for everything you say, and tell me where the evidence is missing instead of guessing." % q.strip())
    return {"schema": "lemmata.ask/1", "question": q.strip(), "intent": intent, "answers": answers, "ai": False, "claude_prompt": prompt}
