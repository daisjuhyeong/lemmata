"""To-do (S24 step 4, ADR-008 section 5.1): one list of what to do next, made by rules from what Lemmata already knows,
plus the open feedback tasks. Every item names what it is about (target) so the page can open it. Ordered by who or what
is waiting. Nothing here is stored except snoozes (todo.json); a rule item disappears when its rule stops firing."""
from .errors import BadRequest

SCHEMA = "lemmata.todo/1"
GROUPS = (("person", "Someone is waiting"), ("confirm", "Needs your confirmation"), ("paper", "The paper is wrong today"),
          ("stale", "Out of date"), ("gap", "Gaps"))
PAPER_CHECKS = ("main_appendix_mismatch", "undefined_ref", "undefined_cite", "reference_unmatched")


def load(hub):
    d = hub.read_json("todo.json", None)
    if not isinstance(d, dict) or not isinstance(d.get("snoozed"), dict):
        d = {"schema": SCHEMA, "snoozed": {}}
    return d


def snooze(store, key, until):
    if not isinstance(key, str) or not key or len(key) > 300:
        raise BadRequest("key must be text")
    if until in (None, ""):
        store["snoozed"].pop(key, None)
    elif isinstance(until, str) and len(until) >= 10 and until[4] == "-" and until[7] == "-":
        store["snoozed"][key] = until[:10]
    else:
        raise BadRequest("snooze_until must be a date (YYYY-MM-DD) or empty")
    return store


def build(E, C, S, tasks, findings, alarms, plans, mapdoc, deadlines, store, today, numbers=None, sync=None):
    """E: experiments doc, C: claims doc, S: setup doc. today: 'YYYY-MM-DD'. -> the To-do document.
    numbers: the Key numbers document; sync: the hub's sync state (S29)."""
    items = []
    bench = E.get("study") == "benchmark"

    def add(group, kind, key, text, why, target, rule):
        items.append({"key": kind + ":" + key, "kind": kind, "group": group, "text": text, "why": why, "target": target, "rule": rule})

    short = {c["id"]: c.get("short") or c["label"] for c in C.get("claims", [])}
    # 1. a person is waiting: feedback
    for t in tasks.get("tasks", []):
        if t.get("state") != "open":
            continue
        tg = (t.get("targets") or [{}])[0]
        cl = (t.get("claims") or [None])[0]
        target = {"view": "claims", "sel": cl} if cl else ({"view": "node", "id": tg["node_id"]} if tg.get("node_id") else {"view": "tasks"})
        add("person", "feedback", t["id"], t["text"][:200], "Feedback from %s." % (t.get("source") or "someone"), dict(target, task=t["id"]), "feedback is open")
    # 1b. Lemmata's copy is behind GitHub: everything below may be out of date
    if sync and sync.get("failing"):
        add("stale", "sync", "failing", "Sync with GitHub is failing", (sync.get("message") or "The last sync failed.")[:300], {"view": "digest"}, "sync failing since %s" % (sync.get("since") or "?")[:10])
    # 2. your confirmation
    if numbers and numbers.get("counts", {}).get("proposed"):
        add("confirm", "numbers", "proposed", "Confirm the %d proposed key numbers" % numbers["counts"]["proposed"], "A list of key numbers was proposed and is not confirmed yet.", {"view": "numbers"}, "key numbers proposed")
    if mapdoc.get("proposed"):
        add("confirm", "map", "proposed", "Confirm the proposed project map", "A map was proposed and is not confirmed yet.", {"view": "experiments"}, "map proposed")
    for c in C.get("claims", []):
        if c.get("state") == "proposed":
            add("confirm", "claim", c["id"], "Confirm or reject %s: %s" % (short[c["id"]], c["text"][:120]), "Lemmata drafted this claim.", {"view": "claims", "sel": c["id"]}, "claim is a draft")
    for p in plans.get("plans", []) if isinstance(plans, dict) else []:
        if p.get("state") == "draft":
            add("confirm", "plan", str(p.get("id")), "Review the planned experiment: %s" % str(p.get("title") or "")[:120], "A plan was drafted.", {"view": "experiments"}, "plan is a draft")
    # 3-5. per experiment (once each, whichever claims it tests)
    seen = set()
    for sec in E.get("sections", []):
        cid = sec.get("claim_id") or sec["id"]
        for x in sec["experiments"]:
            link = (sec.get("links") or {}).get(x["id"])
            if link and sec.get("kind") != "other" and link["status"] == "contradicts" and not bench:      # benchmark: a claim its test does not support is a result, not a task
                add("gap", "contradicts", cid + "|" + x["id"], "%s contradicts %s" % (x["name"], short.get(cid, sec["label"])), link["why"], {"view": "experiments", "sel": "x:" + x["id"]}, link["rule"])
            if link and sec.get("kind") != "other" and link["status"] == "not_run":
                add("gap", "not_run", cid + "|" + x["id"], "Run %s (planned for %s)" % (x["name"], short.get(cid, sec["label"])),
                    "Its result files are not in Lemmata's copy of the repository. Sync is failing, so they may only be not pulled yet." if sync and sync.get("failing") else "No result file yet.",
                    {"view": "experiments", "sel": "x:" + x["id"]}, "L1")
            if x["id"] in seen:
                continue
            seen.add(x["id"])
            tg = {"view": "experiments", "sel": "x:" + x["id"]}
            tl = x.get("tally") or {}
            if tl.get("differs"):
                p = next((p for p in x.get("problems") or [] if p.get("kind") == "differs"), None)
                add("paper", "differs", x["id"], "Paper and results disagree in %s" % x["name"],
                    ("%s, %s: the paper says %s, the file says %s." % (p.get("row"), p.get("col"), p.get("paper"), p.get("file"))) if p else "%d numbers differ." % tl["differs"], tg, "paper number differs")
            if tl.get("untraced"):
                add("paper", "untraced", x["id"], "%d paper numbers in %s are not in any result file" % (tl["untraced"], x["name"]), "They could not be traced.", tg, "paper number untraced")
            if any(p.get("kind") == "bold" for p in x.get("problems") or []):
                add("paper", "bold", x["id"], "Bold is not the best value in %s" % x["name"], "The bold cell is not the best in its column.", tg, "bold not best")
            if x.get("stale"):
                add("stale", "stale", x["id"], "Rerun %s" % x["name"], "The code or settings changed after this result was written.", tg, "result older than its code")
            if any(cv.get("k") == "seeds" for cv in x.get("caveats") or []):
                add("gap", "seeds", x["id"], "%s has one run only" % x["name"], "One run per cell: no spread.", tg, "one run")
    for f in (findings or {}).get("findings", []):
        if f.get("check") in PAPER_CHECKS:
            loc = f.get("loc") or {}
            add("paper", "finding", str(f.get("id") or f.get("check")), str(f.get("title") or f.get("message") or f["check"])[:160], str(f.get("message") or "")[:200],
                {"view": "checks", "loc": loc if loc.get("path") else None}, f["check"])
    # the numbers the report quotes (S29): a mismatch is the paper being wrong today; a number no file holds is a gap
    for g in (numbers or {}).get("groups", []):
        for n in g["numbers"]:
            if n["state"] == "proposed":
                continue
            tg = {"view": "numbers", "sel": n["id"]}
            if n["status"] == "mismatch":
                add("paper", "number", n["id"], "%s: the report and the file disagree (%s)" % (g["label"], n["label"][:80]), n["why"] or "", tg, "key number differs")
            elif n["status"] == "missing":
                add("gap", "number_missing", n["id"], "%s: %s cannot be read from %s" % (g["label"], n["label"][:80], n["file"]), n["why"] or "", tg, "key number missing")
            elif n["status"] == "gap":
                add("gap", "number_gap", n["id"], "%s: no file stores %s" % (g["label"], n["label"][:80]), n.get("gap") or "", tg, "key number with no file")
    n_alarm = ((alarms or {}).get("summary") or {}).get("flagged_nodes") or 0
    if n_alarm:
        add("stale", "changes", "alarms", "%d changed item%s to look at" % (n_alarm, "" if n_alarm == 1 else "s"), "Changed since you last looked.", {"view": "changes"}, "changes not looked at")
    th = E.get("thesis") or {}
    for c in th.get("untested") or []:
        add("gap", "untested", c["id"], "%s has no experiment" % (c.get("short") or "A claim"), c["text"][:160], {"view": "claims", "sel": c["id"]}, "claim with no experiment")
    if (th.get("buckets") or {}).get("no_claim"):
        n = th["buckets"]["no_claim"]
        add("gap", "no_claim", "all", "%d experiment%s test%s no claim" % (n, "" if n == 1 else "s", "s" if n == 1 else ""), "A result that backs no claim has no reason to be in the paper.", {"view": "experiments"}, "experiment with no claim")
    for it in (S or {}).get("items", []):
        for ch in it.get("checks") or []:
            if ch["k"] in ("missing", "direction"):
                add("gap", "setup_" + ch["k"], it["id"], "%s: %s" % (it["name"], ch["t"]), "Found on Setup.", {"view": "setup", "sel": "i:" + it["id"]}, "setup check")

    # deadlines order items inside a group; a deadline can name a target
    dl = sorted((d for d in (deadlines or []) if d.get("date", "") >= today), key=lambda d: d["date"])
    for it in items:
        sel = (it["target"] or {}).get("sel")
        it["due"] = next((d["date"] for d in dl if d.get("target") and d["target"] == sel), None)
    snoozed = (store or {}).get("snoozed", {})
    live, hidden = [], 0
    for it in items:
        until = snoozed.get(it["key"])
        if until and until > today:
            hidden += 1
            continue
        live.append(it)
    order = {g: i for i, (g, _) in enumerate(GROUPS)}
    live.sort(key=lambda it: (order[it["group"]], it["due"] or "9999", it["kind"]))
    return {"schema": SCHEMA, "items": live, "groups": [{"id": g, "label": l, "n": sum(1 for it in live if it["group"] == g)} for g, l in GROUPS],
            "counts": {"total": len(live), "snoozed": hidden}, "deadlines": dl[:20], "today": today}
