"""Review: "should I continue?" on one page. Rules only.

Three checks over the experiments document (is it moving, is it ahead, is there a paper today) and, per question,
a five-item completeness checklist. Four items are checked by rules. The fifth, confounds, is a job for the
researcher's own agent: it reports over MCP, the report is checked against the files, and it goes stale when a newer
result arrives. Nothing here calls a model.
"""
import re
from datetime import datetime, timedelta, timezone

from .errors import BadRequest, NotFound

SCHEMA = "lemmata.review/1"
WINDOWS = (30, 7, 1)
ITEMS = (("seeds", "More than one run"), ("baseline", "A baseline to compare with"), ("ablation", "An ablation or sensitivity study"),
         ("paper", "Paper table matches the files"), ("confounds", "Confounds checked"))

GUIDE = """How to check confounds for Lemmata.

For each question below, read its experiments (files, scripts, settings; open them if you have the repository) and ask
what else, other than the method, could explain the result: different tuning budgets or seeds for ours and the
baselines, test data used for model selection, a metric or threshold chosen after seeing results, unequal training
data or compute, preprocessing applied to only one side, results taken from different commits.

Then call report_confounds with:
{"findings": [{"question": "<question id>", "verdict": "clear" | "risk",
               "confounds": [{"text": "<one sentence: the confound and what would rule it out>",
                              "evidence": {"path": "<file>", "line": 12, "quote": "<a few words copied from that line>"}}]}]}

Rules Lemmata enforces: the question id must exist; "risk" needs at least one confound; every confound needs evidence
whose quote really is in that file (otherwise it is dropped). "clear" means you looked and found none; say so only if
you read the scripts and settings. Report every question you were given.
"""


def load(hub):
    d = hub.read_json("review.json", None)
    if not isinstance(d, dict):
        d = {}
    d.setdefault("hoped", "")
    d.setdefault("confounds", {})
    return d


def _when(s):
    try:
        t = datetime.fromisoformat(s)
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _state(x, extends):
    """ahead / behind / tie / none for one experiment, against the base when the work extends one."""
    sm = x.get("summary")
    if x.get("tuning") or not sm:
        return "none", None
    g = (sm.get("base") or {}).get("gap") if extends else sm.get("gap")
    return ("none" if g is None else "ahead" if g > 0 else "behind" if g < 0 else "tie"), g


def _behind_since(x):
    """The time from which ours has been worse than the best other in every stored version, or None."""
    sm, since = x.get("summary") or {}, None
    for p in reversed(x.get("spark") or []):
        if p.get("o") is None or p.get("b") is None or not p.get("t"):
            break
        if (p["o"] > p["b"]) if sm.get("lower") else (p["o"] < p["b"]):
            since = p["t"]
        else:
            break
    return since


def checklist(sec, extends, conf, last):
    """-> [{"k", "label", "state": done|todo|na|stale, "why"}] for one question."""
    xs = [x for x in sec["experiments"] if not x.get("tuning")]
    cmp_ = [x for x in xs if x.get("summary") and x["summary"].get("ours") is not None]
    out = []

    def item(k, state, why):
        out.append({"k": k, "label": dict(ITEMS)[k], "state": state, "why": why})
    single = [x["name"] for x in cmp_ if (x["summary"].get("n") or 1) <= 1]
    item("seeds", "done" if cmp_ and not single else "todo", "Every experiment has more than one run" if cmp_ and not single else
         ("One run only: " + ", ".join(single[:3])) if single else "No result to count runs in")
    if extends:
        has = [x for x in cmp_ if x["summary"].get("base")]
        item("baseline", "done" if has else "todo", "Compared with %s" % extends["name"] if has else "%s is in none of these results" % extends["name"])
    else:
        has = [x for x in cmp_ if x["summary"].get("baselines")]
        item("baseline", "done" if has else "todo", "Compared with %s" % ", ".join(has[0]["summary"]["baselines"][:3]) if has else "No other method in these results")
    abl = [x for x in xs if x.get("type") in ("ablation", "sensitivity") or re.search(r"ablat|sensitiv", (x.get("name", "") + " " + x.get("caption", "")).lower())]
    item("ablation", "done" if abl else "todo", abl[0]["name"] if abl else "No ablation or sensitivity experiment tests this")
    tal = [x for x in xs if x.get("tally")]
    if sec.get("scope") == "extension" and not tal:
        item("paper", "na", "The linked paper is the original; there is no table for this yet")
    else:
        bad = [x["name"] for x in tal if x["tally"]["differs"] or x["tally"]["untraced"]]
        ok = [x for x in tal if (x["tally"]["match"] + x["tally"]["rounding"]) and not (x["tally"]["differs"] or x["tally"]["untraced"])]
        item("paper", "done" if ok and not bad else "todo", "Every number traced" if ok and not bad else ("Numbers differ or are untraced: " + ", ".join(bad[:3])) if bad else "No paper table is linked")
    c = conf.get(sec["id"])
    if not c:
        item("confounds", "todo", "Not checked yet. Ask your agent.")
    else:
        stale = bool(last and c.get("at") and _when(last) and _when(c["at"]) and _when(last) > _when(c["at"]))
        open_ = [r for r in c.get("confounds", []) if not r.get("resolved")]
        st = "stale" if stale else "done" if c["verdict"] == "clear" or not open_ else "todo"
        item("confounds", st, "Results changed since the check" if stale else "Checked by %s, none found" % c.get("by", "agent") if c["verdict"] == "clear"
             else "All resolved" if not open_ else "%d open" % len(open_))
        out[-1]["report"] = c
    return out


def build(E, store, days=30, now=None):
    """E: the experiments document. -> the Review document."""
    if days not in WINDOWS:
        raise BadRequest("days must be one of %s" % ", ".join(map(str, WINDOWS)))
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    extends = (E.get("extends") or {}).get("base")
    rows, seen = [], {}
    for s in E["sections"]:
        if s["kind"] == "other":
            continue
        times = [t for t in (_when(x.get("last")) for x in s["experiments"]) if t]
        last = max(times).isoformat() if times else None
        states = []
        for x in s["experiments"]:
            k, g = _state(x, extends)
            states.append(k)
            if x["id"] not in seen and k != "none":
                seen[x["id"]] = {"id": x["id"], "name": x["name"], "state": k, "gap": g, "question": s["label"], "question_id": s["id"],
                                 "since": _behind_since(x) if k == "behind" and not extends else None}
        chk = checklist(s, extends, store["confounds"], last)
        counted = [c for c in chk if c["state"] != "na"]
        moved = bool(times and max(times) >= since)
        trend = "none" if not s["experiments"] else "moved" if moved else "stalled"
        rows.append({"id": s["id"], "claim_id": s.get("claim_id"), "label": s["label"], "text": s["text"], "scope": s.get("scope"), "kind": s["kind"],
                     "checklist": chk, "done": sum(1 for c in counted if c["state"] == "done"), "of": len(counted),
                     "complete": bool(counted) and all(c["state"] == "done" for c in counted) and bool(s["experiments"]),
                     "started": bool(s["experiments"]), "trend": trend, "last": last, "experiments": len(s["experiments"]),
                     "ahead": states.count("ahead"), "behind": states.count("behind")})
    # ours against each baseline, over every experiment that has both
    base_key = re.sub(r"[^a-z0-9]+", "", extends["name"].lower()) if extends else None
    base_keys = {re.sub(r"[^a-z0-9]+", "", n.lower()) for n in ([extends["name"]] + extends.get("aliases", []))} if extends else set()
    bl, done = {}, set()
    for s in E["sections"]:
        for x in s["experiments"]:
            sm = x.get("summary") or {}
            if x["id"] in done or x.get("tuning") or x.get("type") in ("ablation", "sensitivity") or not sm.get("vs"):      # variants of ours are not baselines
                continue
            done.add(x["id"])
            for v in sm["vs"]:
                key = re.sub(r"[^a-z0-9]+", "", v["label"].lower())
                key = base_key if key in base_keys else key
                b = bl.setdefault(key, {"name": extends["name"] if key == base_key else v["label"], "base": key == base_key, "ahead": 0, "behind": 0, "tie": 0, "experiments": []})
                st = "ahead" if v["gap"] > 0 else "behind" if v["gap"] < 0 else "tie"
                b[st] += 1
                b["experiments"].append({"id": x["id"], "name": x["name"], "state": st, "gap": v["gap"], "metric": sm.get("measure") or sm.get("metric"),
                                         "question": s["label"] if s["kind"] != "other" else None})
    baselines = sorted(bl.values(), key=lambda b: (not b["base"], -(b["ahead"] + b["behind"] + b["tie"]), b["name"].lower()))[:20]
    for b in baselines:
        b["of"] = b["ahead"] + b["behind"] + b["tie"]
        b["verdict"] = "ahead" if b["ahead"] > b["behind"] and b["ahead"] * 2 >= b["of"] else "behind" if b["behind"] > b["ahead"] else "mixed"
    beaten = [b for b in baselines if b["verdict"] == "ahead"]
    xs = list(seen.values())
    ahead, behind = [x for x in xs if x["state"] == "ahead"], [x for x in xs if x["state"] == "behind"]
    started = [r for r in rows if r["started"]]
    moved = [r for r in rows if r["trend"] == "moved"]
    complete = [r for r in rows if r["complete"]]
    span = "%d day%s" % (days, "" if days == 1 else "s")
    vs = extends["name"] if extends else "the best other method"
    ours = ((E.get("map") or {}).get("method") or {}).get("name") or "our method"
    period = {30: "the last 30 days", 7: "the last week", 1: "the last day"}[days]
    checks = [
        {"k": "moving", "q": "Any new results in %s?" % period, "help": "A question counts when one of its experiments got a new result file in this period.", "verdict": "none" if not started else "yes" if len(moved) * 2 >= len(rows) else "partly" if moved else "no",
         "line": "No experiment yet" if not started else "%d of %d questions moved in %s" % (len(moved), len(rows), span),
         "rows": [r["id"] for r in rows if r["trend"] != "moved"]},
        {"k": "ahead", "q": "How does %s compare with the baselines?" % ours,
         "help": "For each baseline: the experiments where %s scores better on that experiment's metric. Ahead of a baseline means better in more than half of them." % ours,
         "verdict": "none" if not baselines else "yes" if len(beaten) == len(baselines) else "partly" if beaten else "no",
         "line": "Nothing to compare yet" if not baselines else "Ahead of %d of %d baselines%s" % (len(beaten), len(baselines),
                 (" · %s %s" % ("ahead of" if baselines[0]["verdict"] == "ahead" else "not ahead of", baselines[0]["name"])) if extends and baselines[0]["base"] else ""),
         "rows": sorted({x["question_id"] for x in behind}), "behind": behind},
        {"k": "paper", "q": "Is the evidence enough to write the paper now?",
         "help": "A claim is fully backed when every item of its checklist is done: more than one run, a baseline, an ablation, a matching paper table, confounds checked.", "verdict": "none" if not rows else "yes" if len(complete) == len(rows) else "partly" if complete else "no",
         "line": "No question yet" if not rows else "%d of %d claims fully backed" % (len(complete), len(rows)),
         "rows": [r["id"] for r in rows if not r["complete"]]},
    ]
    return {"schema": SCHEMA, "days": days, "windows": list(WINDOWS), "checks": checks, "questions": rows, "hoped": store["hoped"],
            "supported": [{"label": r["label"], "text": r["text"]} for r in complete],
            "not_yet": [{"label": r["label"], "text": r["text"], "missing": [c["label"] for c in r["checklist"] if c["state"] in ("todo", "stale")]} for r in rows if not r["complete"]],
            "baselines": baselines, "ours": ours, "extends": E.get("extends"), "mapped": bool(E.get("unmapped") is not None)}


# ------------------------------------------------------------------ the agent's confound report
def brief(E, details):
    """What an agent needs to look for confounds: each question with its experiments' design. details(exp_id) -> full experiment."""
    out = []
    for s in E["sections"]:
        if s["kind"] == "other" or not s["experiments"]:
            continue
        xs = []
        for x in s["experiments"][:8]:
            try:
                d = details(x["id"]).get("design") or {}
            except Exception:
                d = {}
            sm = x.get("summary") or {}
            xs.append({"id": x["id"], "name": x["name"], "type": x.get("type"), "files": (x.get("result") or {}).get("path"), "metric": sm.get("measure") or sm.get("metric"),
                       "ours": sm.get("ours_label"), "methods": (sm.get("methods") or [])[:12], "runs": sm.get("n"),
                       "scripts": [i["name"] for i in d.get("scripts", [])], "settings": [i["name"] for i in d.get("settings", [])],
                       "values": {v["key"]: v["value"] for v in d.get("values", [])[:20]}, "commands": [r.get("command") for r in d.get("runs", []) if r.get("command")][:4]})
        out.append({"question": s["id"], "label": s["label"], "text": s["text"], "experiments": xs})
    return out


def report(store, findings, E, trees, by, at):
    """Check an agent's confound findings and store what holds. -> [notes]"""
    if not isinstance(findings, list) or not findings:
        raise BadRequest("findings must be a non-empty list")
    known = {s["id"] for s in E["sections"] if s["kind"] != "other"}
    notes = []
    sq = lambda t: re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()
    for f in findings[:40]:
        if not isinstance(f, dict) or f.get("question") not in known:
            notes.append("dropped: unknown question %r" % (f.get("question") if isinstance(f, dict) else f,))
            continue
        qid, kept = f["question"], []
        for c in (f.get("confounds") if isinstance(f.get("confounds"), list) else [])[:12]:
            ev = c.get("evidence") if isinstance(c, dict) and isinstance(c.get("evidence"), dict) else None
            text = " ".join(str(c.get("text") or "").split())[:400] if isinstance(c, dict) else ""
            path = str((ev or {}).get("path") or "").split(":", 1)[-1].lstrip("./")
            quote = " ".join(str((ev or {}).get("quote") or "").split())[:200]
            hit = None
            if text and path and sq(quote):
                for rid, tr in trees.items():
                    try:
                        if tr.has(path) and tr.size(path) <= 1000000:
                            lines = tr.read(path).decode("utf-8", "replace").split("\n")
                            i = next((i for i in range(len(lines)) if sq(quote) in sq(" ".join(lines[i:i + 3]))), None)
                            if i is not None:
                                hit = {"repo": rid, "path": path, "line": i + 1, "quote": quote}
                                break
                    except Exception:
                        pass
            if hit:
                kept.append({"text": text, "evidence": hit, "resolved": False})
            else:
                notes.append("dropped (%s): a confound whose quote is not in %r" % (qid, path or "no file"))
        verdict = f.get("verdict")
        if verdict == "risk" and not kept:
            notes.append("dropped (%s): verdict 'risk' with no confound that passed checking" % qid)
            continue
        if verdict not in ("clear", "risk"):
            notes.append("dropped (%s): verdict must be clear or risk" % qid)
            continue
        if verdict == "clear" and kept:
            verdict = "risk"
        store["confounds"][qid] = {"verdict": verdict, "confounds": kept, "by": by, "at": at}
        notes.append("kept (%s): %s, %d confound%s" % (qid, verdict, len(kept), "" if len(kept) == 1 else "s"))
    return notes


def decide(store, known, hoped=None, question=None, resolve=None, mine=None, at=None):
    if hoped is not None:
        if len(hoped) > 600:
            raise BadRequest("the hoped conclusion must be at most 600 characters")
        store["hoped"] = " ".join(hoped.split())
    if question is not None:
        if question not in known:
            raise NotFound("unknown question")
        c = store["confounds"].get(question)
        if mine is not None:      # the researcher checked it without an agent, or clears that mark
            if mine:
                store["confounds"][question] = {"verdict": "clear", "confounds": [], "by": "you", "at": at}
            else:
                store["confounds"].pop(question, None)
        elif resolve is not None:
            if not c or not (0 <= resolve < len(c["confounds"])):
                raise NotFound("unknown confound")
            c["confounds"][resolve]["resolved"] = not c["confounds"][resolve]["resolved"]
