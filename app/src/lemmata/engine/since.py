"""Since you last looked (S36, ADR-012, acceptance line 13): what changed in the project after the time this person last
opened Home, newest first. Built from the Trail's entries, so nothing is invented. The hub keeps, per project and per
signed-in person, the time Home was last opened (home_seen.json). The person is stored as a short hash, never as a name.
Who made a change is shown only where the record says so (Trail entry "by"); otherwise the row shows its kind alone."""
import hashlib
from datetime import datetime, timedelta

SCHEMA = "lemmata.since/1"
FIRST_DAYS = 7
MAX_ROWS = 60
MAX_USERS = 200
KIND_WORD = {"paper": "Paper", "code": "Code", "runs": "Run", "claims": "Claim", "feedback": "Feedback", "decisions": "Decision"}
WHO_WORD = {"you": "You", "agent": "Your agent", "run": "A run", "lemmata": "Lemmata", "person": None}


def key_of(viewer):
    """One short hash per signed-in person (GitHub login on a hub) or per machine (local mode, viewer None)."""
    return hashlib.sha256(("lemmata-home:" + (viewer or "local").lower()).encode()).hexdigest()[:12]


def load(hub):
    d = hub.read_json("home_seen.json", None)
    if not isinstance(d, dict) or not isinstance(d.get("users"), dict):
        d = {"schema": "lemmata.home_seen/1", "users": {}}
    return d


def mark(store, viewer, now):
    users = store["users"]
    users[key_of(viewer)] = now
    if len(users) > MAX_USERS:      # drop the oldest records
        for k in sorted(users, key=lambda k: users[k])[:len(users) - MAX_USERS]:
            users.pop(k)
    return store


def parse(t):
    """ISO time with or without an offset -> an aware datetime (no offset means this machine's own time)."""
    try:
        d = datetime.fromisoformat(str(t))
    except ValueError:
        return None
    return d if d.tzinfo else d.astimezone()


def _who(e):
    by = e.get("by")
    if not isinstance(by, dict) or not by.get("kind"):
        return {"kind": None, "name": None, "label": None}      # the record does not say: no name, no guess
    word = WHO_WORD.get(by["kind"])
    name = by.get("name")
    label = word if by["kind"] != "person" else name
    if by["kind"] in ("agent", "run") and name and name.strip().lower() not in ("agent", "the agent", "your agent"):
        label = "%s (%s)" % (word, name)
    return {"kind": by["kind"], "name": name, "label": label}


def build(trail, last, now, first_days=FIRST_DAYS):
    """trail: the Trail document. last: when this person last opened Home (ISO) or None. now: ISO. -> the Since document."""
    first = not last
    now_d = parse(now)
    since_d = parse(last) if last else None
    if since_d is None:
        first = True
        since_d = now_d - timedelta(days=first_days)
    rows = []
    for e in trail.get("entries") or []:
        t = parse(e.get("t"))
        if t is None or t <= since_d:
            continue
        rows.append({"t": e["t"], "kind": e["kind"], "kind_word": KIND_WORD.get(e["kind"], e["kind"]), "who": _who(e), "text": e.get("title") or "",
                     "ref": e.get("ref"), "target": e.get("target"), "at": e.get("at"), "_d": t})
    rows.sort(key=lambda r: r["_d"], reverse=True)
    for r in rows:
        r.pop("_d")
    return {"schema": SCHEMA, "since": since_d.isoformat(), "first_visit": first, "days": first_days if first else None, "last_opened": last,
            "now": now, "total": len(rows), "items": rows[:MAX_ROWS]}
