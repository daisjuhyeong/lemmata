"""Trail (S24 step 5, ADR-008 section 5.2): the time axis of a research project. One list of dated entries, looking back,
merged from records Lemmata already keeps (commits, stage changes, logged runs, feedback, the map, checkpoints, plans),
plus deadlines ahead. Rules only."""
import re
import uuid

from .errors import BadRequest, NotFound

SCHEMA = "lemmata.trail/1"
KINDS = ("paper", "code", "runs", "claims", "feedback", "decisions")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_deadlines(hub):
    d = hub.read_json("deadlines.json", None)
    if not isinstance(d, dict) or not isinstance(d.get("deadlines"), list):
        d = {"schema": "lemmata.deadlines/1", "deadlines": []}
    return d


def set_deadline(store, date=None, title=None, target=None, remove=None):
    if remove is not None:
        n = len(store["deadlines"])
        store["deadlines"] = [d for d in store["deadlines"] if d["id"] != remove]
        if len(store["deadlines"]) == n:
            raise NotFound("unknown deadline %r" % remove)
        return store
    if not isinstance(date, str) or not DATE.match(date):
        raise BadRequest("date must be YYYY-MM-DD")
    if not isinstance(title, str) or not title.strip() or len(title) > 160:
        raise BadRequest("title must be 1 to 160 characters")
    if target is not None and (not isinstance(target, str) or len(target) > 200):
        raise BadRequest("target must be text")
    if len(store["deadlines"]) >= 200:
        raise BadRequest("too many deadlines")
    store["deadlines"].append({"id": "d" + uuid.uuid4().hex[:8], "date": date, "title": title.strip(), "target": target or None})
    store["deadlines"].sort(key=lambda d: d["date"])
    return store


def build(events, steps, stages, claims_doc, runs, tasks, mapdoc, checkpoints, plans, deadlines, github, start=None, end=None, today=None):
    """-> the Trail document: entries newest first, days, months (for the month grid), deadlines ahead."""
    out = []

    def add(t, kind, title, why=None, target=None, at=None, ref=None):
        if isinstance(t, str) and len(t) >= 10:
            out.append({"t": t, "day": t[:10], "kind": kind, "title": title, "why": why, "target": target, "at": at, "ref": ref})

    theme = {}
    for st in steps or []:
        for c in st.get("commits") or []:
            theme[c["event_id"]] = st
    for ev in events or []:
        if ev.get("kind") != "commit":
            continue
        st = theme.get(ev["id"]) or {}
        files = ev.get("files") or []
        role = st.get("role") or ("paper" if ev.get("repo") == "paper" else "code")
        n_res = (st.get("kinds") or {}).get("result", 0) if len(st.get("commits") or []) == 1 else 0
        gh = re.match(r"^(https://github\.com/[^/]+/[^/]+)(/|$)", str((github or {}).get(ev.get("repo")) or ""))
        add(ev["time"], "paper" if role == "paper" else "code", ev.get("subject") or "(no message)",
            "%d file%s in %s%s" % (len(files), "" if len(files) == 1 else "s", ev.get("repo"), (", %d result file%s" % (n_res, "" if n_res == 1 else "s")) if n_res else ""),
            {"view": "commit", "url": (gh.group(1) + "/commit/" + ev["rev"]) if gh else None},
            ref=ev.get("short"))
        if st.get("decision"):
            out[-1]["decision"] = True
    names = {c["id"]: (c.get("short") or c.get("label") or c["id"]) for c in (claims_doc.get("claims") or [])}
    if claims_doc.get("core"):
        names["core"] = "Thesis"
    words = {"hypothesis": "Hypothesis", "testing": "Being tested", "finding": "Finding", "refuted": "Not supported", "exploration": "Exploration"}
    for c in claims_doc.get("claims") or []:      # recorded stage changes, and before those what the stored results show
        cid, prev = c["id"], None
        for r in c.get("stages") or ((stages or {}).get("log") or {}).get(cid) or []:
            add(r["t"], "claims", "%s: %s" % (names[cid], words.get(r["stage"], r["stage"])) if prev is None else "%s: %s → %s" % (names[cid], words.get(prev, prev), words.get(r["stage"], r["stage"])),
                "Set by you." if r.get("by") == "you" else "From the stored results." if r.get("by") == "history" else "From the evidence.", {"view": "claims", "sel": cid}, at=r["t"])
            prev = r["stage"]
    for r in (runs or {}).get("runs") or []:
        t = r.get("ended") or r.get("started")
        add(t, "runs", (r.get("command") or "run")[:120], "on %s%s" % (r.get("host") or "?", "" if r.get("exit_code") in (0, None) else ", exit %s" % r.get("exit_code")), {"view": "runs", "id": r.get("run_id")})
    for b in (tasks or {}).get("batches") or []:
        n = sum(1 for t in (tasks.get("tasks") or []) if t.get("batch") == b["id"])
        add(b.get("created"), "feedback", "Feedback: %s" % (b.get("source") or "Feedback"), "%d task%s" % (n, "" if n == 1 else "s"), {"view": "tasks"})
    for t in (tasks or {}).get("tasks") or []:
        if t.get("done_at"):
            add(t["done_at"], "feedback", "Done: %s" % t["text"][:100], None, {"view": "tasks"})
    if mapdoc.get("proposed_at"):
        add(mapdoc["proposed_at"], "decisions", "Project map proposed", "by %s" % (mapdoc.get("proposed_by") or "the agent"), {"view": "experiments"})
    if mapdoc.get("confirmed_at"):
        add(mapdoc["confirmed_at"], "decisions", "Project map confirmed", "by you", {"view": "experiments"})
    for cp in (checkpoints or {}).get("checkpoints") or []:
        add(cp.get("created_at"), "decisions", "Marked everything as looked at", cp.get("note") or None, {"view": "changes"})
    for p in (plans or {}).get("plans") or [] if isinstance(plans, dict) else []:
        add(p.get("at"), "decisions", "Planned: %s" % str(p.get("title") or "an experiment")[:100], None, {"view": "experiments"})

    out.sort(key=lambda e: e["t"], reverse=True)
    counts = {k: sum(1 for e in out if e["kind"] == k) for k in KINDS}
    days = {}
    for e in out:
        d = days.setdefault(e["day"], dict.fromkeys(KINDS, 0))
        d[e["kind"]] += 1
    if start:
        out = [e for e in out if e["day"] >= start]
    if end:
        out = [e for e in out if e["day"] <= end]
    dl = sorted(deadlines or [], key=lambda d: d["date"])
    return {"schema": SCHEMA, "entries": out[:1500], "days": days, "counts": counts, "kinds": list(KINDS),
            "deadlines": dl, "ahead": [d for d in dl if not today or d["date"] >= today], "today": today,
            "first": min(days) if days else None, "last": max(days) if days else None}
