"""Trail (S24 step 5, ADR-008 section 5.2): the time axis of a research project. One list of dated entries, looking back,
merged from records Lemmata already keeps (commits, stage changes, logged runs, feedback, the map, checkpoints, plans),
plus deadlines ahead. Rules only."""
import re
import uuid
from datetime import datetime, timedelta, timezone

from . import sessions as sessionsmod
from .errors import BadRequest, NotFound

SCHEMA = "lemmata.trail/1"
KINDS = ("paper", "code", "runs", "claims", "feedback", "decisions")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_deadlines(hub):
    d = hub.read_json("deadlines.json", None)
    if not isinstance(d, dict) or not isinstance(d.get("deadlines"), list):
        d = {"schema": "lemmata.deadlines/1", "deadlines": []}
    return d


DL_KINDS = ("milestone", "abstract", "paper", "decision", "journal")


def add_venue(store, found, kinds=None):
    """Store a conference's deadlines as looked up (venues.lookup). Replaces what was stored for the same venue and year."""
    key = "%s %s" % (found["venue"], found["year"])
    store["deadlines"] = [d for d in store["deadlines"] if d.get("venue") != key]
    n = 0
    for d in found["deadlines"]:
        if not d.get("date") or (kinds and d["kind"] not in kinds):
            continue
        store["deadlines"].append({"id": "d" + uuid.uuid4().hex[:8], "date": d["date"], "title": "%s: %s" % (key, d["label"].lower()), "target": None, "kind": d["kind"],
                                   "venue": key, "time": d.get("time"), "tz": d.get("tz"), "utc": d.get("utc"), "link": found.get("link"), "source": found.get("source"),
                                   "checked": datetime.now().astimezone().replace(microsecond=0).isoformat()})
        n += 1
    if not n:
        raise BadRequest("%s has no dated deadline yet (still to be announced). Add your own date for now." % key)
    store["deadlines"].sort(key=lambda d: d["date"])
    return store


def set_deadline(store, date=None, title=None, target=None, remove=None, kind=None, venue=None):
    if remove is not None:
        n = len(store["deadlines"])
        store["deadlines"] = [d for d in store["deadlines"] if d["id"] != remove and d.get("venue") != remove]
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
    if kind is not None and kind not in ("milestone", "journal"):
        raise BadRequest("kind must be milestone or journal; conference deadlines come from the venue lookup")
    if venue is not None and (not isinstance(venue, str) or len(venue) > 120):
        raise BadRequest("venue must be text")
    store["deadlines"].append({"id": "d" + uuid.uuid4().hex[:8], "date": date, "title": title.strip(), "target": target or None,
                               "kind": kind or "milestone", "venue": (venue or "").strip() or None})
    store["deadlines"].sort(key=lambda d: d["date"])
    return store


def _esc(t):
    t = str(t or "")
    for ch in (chr(92), ";", ","):
        t = t.replace(ch, chr(92) + ch)
    return t.replace(chr(10), chr(92) + "n")


def ics(deadlines, name, now=None):
    """The deadlines and milestones as an iCalendar file (RFC 5545): what Google, Apple and Outlook calendars subscribe to."""
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Lemmata//Deadlines//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:" + _esc("Lemmata: %s" % name)]
    for d in deadlines:
        out += ["BEGIN:VEVENT", "UID:%s@lemmata" % d["id"], "DTSTAMP:" + stamp]
        if d.get("utc"):
            t = datetime.strptime(d["utc"], "%Y-%m-%dT%H:%M:%SZ")
            out += ["DTSTART:" + t.strftime("%Y%m%dT%H%M%SZ"), "DTEND:" + t.strftime("%Y%m%dT%H%M%SZ")]
        else:
            day = datetime.strptime(d["date"], "%Y-%m-%d")
            out += ["DTSTART;VALUE=DATE:" + day.strftime("%Y%m%d"), "DTEND;VALUE=DATE:" + (day + timedelta(days=1)).strftime("%Y%m%d")]
        desc = " · ".join(x for x in [("%s %s at the venue" % (d.get("time"), d.get("tz"))) if d.get("tz") else None, d.get("link"), "Research: %s" % name] if x)
        out += ["SUMMARY:" + _esc(d["title"]), "DESCRIPTION:" + _esc(desc), "END:VEVENT"]
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


def build(events, steps, stages, claims_doc, runs, tasks, mapdoc, checkpoints, plans, deadlines, github, start=None, end=None, today=None, exps=None, repos=None, notes=None):
    """-> the Trail document: entries newest first, days, months (for the month grid), deadlines ahead."""
    out = []

    def add(t, kind, title, why=None, target=None, at=None, ref=None, by=None):
        """by: who made it, only where the record says so: {"kind": you|agent|run|lemmata|person, "name": text or None}. Never guessed."""
        if isinstance(t, str) and len(t) >= 10:
            out.append({"t": t, "day": t[:10], "kind": kind, "title": title, "why": why, "target": target, "at": at, "ref": ref, "by": by})

    res_paths = {p_ for x in exps or [] for p_ in x.get("_paths") or []}
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
        out[-1].update(repo=ev.get("repo"), author=ev.get("author"), coauthors=ev.get("coauthors") or [])
        if ev.get("agent_coauthor"):      # a Co-Authored-By line with an Anthropic address says an agent helped
            out[-1]["by"] = {"kind": "agent", "name": None}
        elif ev.get("author"):
            out[-1]["by"] = {"kind": "person", "name": ev["author"]}
        if st.get("decision"):
            out[-1]["decision"] = True
        # the detail shown when the day is opened: the files by kind, and what the commit did to each experiment's result
        grp = {"paper": [], "results": [], "code": []}
        for f in files:
            pth = f.get("path", "")
            grp["paper" if role == "paper" else "results" if pth in res_paths else "code"].append(pth)
        moved = []
        for x in exps or []:
            sp = x.get("spark") or []
            field = (x.get("summary") or {}).get("study") == "benchmark"      # no "ours": follow the best of what is compared
            k = "b" if field else "o"
            for i, pt in enumerate(sp):
                if pt.get("t") == ev["time"] and pt.get(k) is not None:
                    prev = next((q[k] for q in reversed(sp[:i]) if q.get(k) is not None), None)
                    moved.append({"x": x["id"], "name": x["name"], "claims": x.get("_claims") or [], "before": prev, "after": pt[k], "best_other": None if field else pt.get("b"),
                                  "field": field, "metric": (x.get("summary") or {}).get("metric"), "lower": (x.get("summary") or {}).get("lower")})
        out[-1]["detail"] = {"files": {k: v[:8] for k, v in grp.items() if v}, "files_n": {k: len(v) for k, v in grp.items() if v}, "results": moved,
                             "affects": [a_.get("label") or a_.get("id") for a_ in (st.get("affects") or []) if isinstance(a_, dict)][:6]}
    names = {c["id"]: (c.get("short") or c.get("label") or c["id"]) for c in (claims_doc.get("claims") or [])}
    if claims_doc.get("core"):
        names["core"] = "Thesis"
    words = {"hypothesis": "Hypothesis", "testing": "Being tested", "finding": "Finding", "refuted": "Not supported", "exploration": "Exploration"}
    for c in claims_doc.get("claims") or []:      # recorded stage changes, and before those what the stored results show
        cid, prev = c["id"], None
        for r in c.get("stages") or ((stages or {}).get("log") or {}).get(cid) or []:
            add(r["t"], "claims", "%s: %s" % (names[cid], words.get(r["stage"], r["stage"])) if prev is None else "%s: %s → %s" % (names[cid], words.get(prev, prev), words.get(r["stage"], r["stage"])),
                "Set by you." if r.get("by") == "you" else "From the stored results." if r.get("by") == "history" else "From the evidence.", {"view": "claims", "sel": cid}, at=r["t"],
                by={"kind": "you", "name": None} if r.get("by") == "you" else {"kind": "lemmata", "name": None})
            prev = r["stage"]
    for r in (runs or {}).get("runs") or []:
        t = r.get("ended") or r.get("started")
        add(t, "runs", (r.get("command") or "run")[:120], "on %s%s" % (r.get("host") or "?", "" if r.get("exit_code") in (0, None) else ", exit %s" % r.get("exit_code")), {"view": "runs", "id": r.get("run_id")}, by={"kind": "run", "name": r.get("host")})
        if isinstance(t, str) and len(t) >= 10:
            out[-1]["_run"] = r
    for b in (tasks or {}).get("batches") or []:
        n = sum(1 for t in (tasks.get("tasks") or []) if t.get("batch") == b["id"])
        add(b.get("created"), "feedback", "Feedback: %s" % (b.get("source") or "Feedback"), "%d task%s" % (n, "" if n == 1 else "s"), {"view": "tasks"})
    for t in (tasks or {}).get("tasks") or []:
        if t.get("done_at"):
            add(t["done_at"], "feedback", "Done: %s" % t["text"][:100], None, {"view": "tasks"})
    if mapdoc.get("proposed_at"):
        add(mapdoc["proposed_at"], "decisions", "Project map proposed", "by %s" % (mapdoc.get("proposed_by") or "the agent"), {"view": "experiments"}, by={"kind": "agent", "name": mapdoc.get("proposed_by")})
    if mapdoc.get("confirmed_at"):
        add(mapdoc["confirmed_at"], "decisions", "Project map confirmed", "by you" if mapdoc.get("confirmed_by") == "you" else None, {"view": "experiments"},
            by={"kind": "you", "name": None} if mapdoc.get("confirmed_by") == "you" else None)
    for cp in (checkpoints or {}).get("checkpoints") or []:
        add(cp.get("created_at"), "decisions", "Marked everything as looked at", cp.get("note") or None, {"view": "changes"}, by={"kind": "you", "name": None} if cp.get("by") == "you" else None)
    for p in (plans or {}).get("plans") or [] if isinstance(plans, dict) else []:
        add(p.get("at"), "decisions", "Planned: %s" % str(p.get("title") or "an experiment")[:100], None, {"view": "experiments"})

    sess = sessionsmod.build(out, exps or [], repos or [], notes)
    for e in out:
        e.pop("_run", None)
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
    sess = [x for x in sess if (not start or x["day"] >= start) and (not end or x["day"] <= end)]
    dl = sorted(deadlines or [], key=lambda d: d["date"])
    return {"schema": SCHEMA, "entries": out[:1500], "sessions": sess[:600], "gap_minutes": sessionsmod.GAP // 60, "days": days, "counts": counts, "kinds": list(KINDS),
            "deadlines": dl, "ahead": [d for d in dl if not today or d["date"] >= today], "today": today,
            "first": min(days) if days else None, "last": max(days) if days else None}
