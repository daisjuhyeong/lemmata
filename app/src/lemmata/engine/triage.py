"""Triage entries (node / finding) and link decisions persisted in triage.json (data-model 10)."""
from .errors import BadRequest

STATES = ("unreviewed", "reviewed", "needs_fixing", "ignored")
DECISIONS = ("approved", "rejected", "proposed")


def load(hub):
    t = hub.read_json("triage.json", None)
    if not t:
        return {"schema": "lemmata.triage/1", "entries": {}, "links": {}}
    t.setdefault("entries", {})
    t.setdefault("links", {})
    t["schema"] = "lemmata.triage/1"
    return t


def with_effective(entry, current_hash):
    e = dict(entry)
    outdated = entry.get("hash_at_triage") != current_hash
    if outdated:
        e["effective_state"], e["outdated"] = "unreviewed", True
    else:
        e["effective_state"], e["outdated"] = entry["state"], False
    return e


def set_entry(tri, target_type, target_id, state, note, current_hash, now, by=None):
    if state not in STATES:
        raise BadRequest("state must be one of %s" % ", ".join(STATES))
    note = note or ""
    if not isinstance(note, str) or len(note) > 2000:
        raise BadRequest("note must be a string of at most 2000 characters")
    key = "%s:%s" % (target_type, target_id)
    ent = tri["entries"].get(key)
    rec = {"state": state, "note": note, "at": now, "hash": current_hash, "by": by}
    if ent is None:
        ent = {"target_type": target_type, "target_id": target_id, "history": []}
    ent.update({"state": state, "note": note, "hash_at_triage": current_hash, "updated_at": now, "by": by})
    ent["history"].append(rec)
    tri["entries"][key] = ent
    return ent


def set_decision(tri, edge_id, decision, now):
    if decision not in DECISIONS:
        raise BadRequest("decision must be one of %s" % ", ".join(DECISIONS))
    ent = tri["links"].get(edge_id) or {"history": []}
    ent["decision"], ent["at"] = decision, now
    ent["history"].append({"decision": decision, "at": now})
    tri["links"][edge_id] = ent
    return ent
