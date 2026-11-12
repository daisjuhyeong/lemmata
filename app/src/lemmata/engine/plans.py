"""Next experiments, planned by the researcher's own coding agent (S20).

Lemmata does not call a model. It hands the agent a brief for one claim or one experiment (experiment_brief): what the
claim says, which checklist items are missing, how each experiment was made (scripts, settings, commands), where ours is
behind a baseline, and the confounds already found. The agent designs up to three experiments and submits them with
propose_experiments, each with a complete prompt a fresh Claude Code session can run. Lemmata checks every proposal
against the repository (each must quote a real file it builds on) and keeps the rest as drafts. The researcher reads,
edits and copies a prompt; nothing runs until they paste it into Claude Code.
"""
import re
import secrets

from .errors import BadRequest, NotFound

SCHEMA = "lemmata.plans/1"
KINDS = ("rerun", "seeds", "baseline", "ablation", "sensitivity", "new", "fix")
MAX_PER_CALL = 3
STATES = ("draft", "copied", "dropped")

GUIDE = """How to plan the next experiment for Lemmata.

Read the target below: the claim (or the experiment and the claim it tests), its checklist, how each experiment was
made, where ours is behind, and the confounds already found. Open the scripts and settings it names. Then design at
most three experiments that would most change how far the claim can be trusted, in this order of value: a missing
checklist item (more than one run, a baseline, an ablation, a paper table that matches its file), a stale result whose
code changed, a baseline ours is behind on, a confound that is still open, then anything new the claim needs.

Each experiment must reuse the project's own scripts, settings and result layout, so its output lands where Lemmata
already looks. Prefer the smallest change that answers the question.

Then call propose_experiments with:
{"target": "<the same target>",
 "proposals": [{"kind": "rerun" | "seeds" | "baseline" | "ablation" | "sensitivity" | "new" | "fix",
                "title": "<under 90 characters>",
                "why": "<which gap this closes, one or two sentences>",
                "expected": "<what result would support the claim, and what would count against it>",
                "files": [{"path": "<a file it builds on>", "quote": "<a few words copied from that file>"}],
                "prompt": "<complete instructions for a fresh Claude Code session; see below>"}]}

The prompt is what the researcher pastes into Claude Code, so it must stand alone: the goal in one sentence; the exact
files to change or create; the command(s) to run, with seeds; where the results are written; what must not change
(the paper, other experiments' result files, the evaluation code unless that is the point); and to stop and report the
numbers when done. Write it for this repository, with its real paths and options, not generic advice.

Rules Lemmata enforces: the target must exist; at most three proposals; every proposal needs a kind, title, why,
expected and prompt; at least one file whose quote is really in that file; the prompt must name at least one of those
files. Proposals that fail are dropped. Earlier drafts for the same target are replaced; prompts the researcher already
copied are kept. Never run anything yourself when asked only to plan.
"""


def load(hub):
    d = hub.read_json("plans.json", None)
    if not isinstance(d, dict) or not isinstance(d.get("plans"), list):
        d = {"schema": SCHEMA, "plans": []}
    return d


def view(store):
    return {"schema": SCHEMA, "plans": [p for p in store["plans"] if p.get("state") != "dropped"]}


def _targets(E):
    """{target: (kind, section or experiment)} for every claim/question and experiment."""
    out = {}
    for s in E["sections"]:
        if s["kind"] != "other":
            out["q:" + s["id"]] = ("claim", s)
        for x in s["experiments"]:
            out.setdefault("x:" + x["id"], ("experiment", x))
    return out


def _exp_brief(x, details):
    try:
        d = details(x["id"]) or {}
    except Exception:
        d = {}
    des = d.get("design") or {}
    sm = x.get("summary") or {}
    out = {"id": x["id"], "name": x["name"], "type": x.get("type"), "result_file": (x.get("result") or {}).get("path"),
           "metric": sm.get("measure") or sm.get("metric"), "lower_is_better": bool(sm.get("lower")), "ours": sm.get("ours_label"),
           "ours_value": sm.get("ours"), "methods": (sm.get("methods") or [])[:12], "runs_per_method": sm.get("n"),
           "datasets": (sm.get("datasets") or sm.get("cols") or [])[:12],
           "scripts": [i["name"] for i in des.get("scripts", [])][:8], "settings": [i["name"] for i in des.get("settings", [])][:6],
           "values": {v["key"]: v["value"] for v in des.get("values", [])[:24]},
           "commands": [r.get("command") for r in des.get("runs", []) if r.get("command")][:4],
           "behind": [{"baseline": v["label"], "theirs": v["value"], "gap": v["gap"]} for v in (sm.get("vs") or []) if v["gap"] < 0][:6],
           "stale": [c.get("t") for c in d.get("caveats", []) if c.get("k") == "stale"][:2],
           "paper": [p.get("name") for p in d.get("paper", [])][:4] if isinstance(d.get("paper"), list) else []}
    return out


def brief(E, review, details, target, store):
    """Everything the agent needs to plan for one target ('q:<claim>' or 'x:<experiment>')."""
    T = _targets(E)
    if target not in T:
        raise NotFound("unknown target %r: use 'q:<claim id>' or 'x:<experiment id>' from the experiments list" % target)
    kind, obj = T[target]
    rows = {r["id"]: r for r in (review or {}).get("questions", [])}
    claims = [obj] if kind == "claim" else [s for s in E["sections"] if s["kind"] != "other" and any(x["id"] == obj["id"] for x in s["experiments"])]

    def claim_part(s):
        r = rows.get(s["id"]) or {}
        conf = next((c for c in r.get("checklist", []) if c.get("k") == "confounds"), None)
        rep = (conf or {}).get("report") or {}
        return {"id": s["id"], "label": r.get("label") or s["label"], "text": s["text"], "stage": r.get("stage"), "scope": s.get("scope"),
                "checklist": [{"item": c["label"], "state": c["state"], "why": c["why"]} for c in r.get("checklist", [])],
                "open_confounds": [c["text"] for c in rep.get("confounds", []) if not c.get("resolved")][:8],
                "experiments": [x["name"] for x in s["experiments"]][:12]}

    xs = obj["experiments"][:6] if kind == "claim" else [obj]
    ext = E.get("extends") or {}
    return {"schema": "lemmata.plan_brief/1", "target": target, "kind": kind,
            "project": {"ours": ((review or {}).get("ours")), "base_method": (ext.get("base") or {}).get("name") if isinstance(ext.get("base"), dict) else None,
                        "goal": ext.get("goal"), "hoped_conclusion": (review or {}).get("hoped") or None},
            "claims": [claim_part(s) for s in claims][:4],
            "experiments": [_exp_brief(x, details) for x in xs],
            "already_planned": [{"title": p["title"], "kind": p["kind"], "state": p["state"]} for p in store["plans"] if p["target"] == target and p["state"] != "dropped"]}


def _sq(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def _find(trees, path, quote):
    path = str(path or "").split(":", 1)[-1].lstrip("./")
    q = _sq(quote)
    if not path or len(q) < 4:
        return None
    for rid, tr in trees.items():
        try:
            if tr.has(path) and tr.size(path) <= 2000000:
                lines = tr.read(path).decode("utf-8", "replace").split("\n")
                i = next((i for i in range(len(lines)) if q in _sq(lines[i])), None)                  # the line itself, or
                if i is None:
                    i = next((i for i in range(len(lines)) if q in _sq(" ".join(lines[i:i + 3]))), None)      # a quote across a line break
                if i is not None:
                    return {"repo": rid, "path": path, "line": i + 1, "quote": " ".join(str(quote).split())[:200]}
        except Exception:
            pass
    return None


def _txt(v, n):
    return " ".join(str(v or "").split())[:n] if isinstance(v, str) else ""


def propose(store, E, trees, target, proposals, by, at):
    """Check an agent's proposals and keep what holds. -> [notes]"""
    if target not in _targets(E):
        raise NotFound("unknown target %r" % target)
    if not isinstance(proposals, list) or not proposals:
        raise BadRequest("proposals must be a non-empty list")
    notes, kept = [], []
    for i, p in enumerate(proposals[:MAX_PER_CALL]):
        tag = "proposal %d" % (i + 1)
        if not isinstance(p, dict):
            notes.append("dropped (%s): not an object" % tag)
            continue
        kind, title, why, expected = p.get("kind"), _txt(p.get("title"), 90), _txt(p.get("why"), 600), _txt(p.get("expected"), 600)
        prompt = p.get("prompt") if isinstance(p.get("prompt"), str) else ""
        prompt = prompt.replace("\r\n", "\n").strip()[:8000]
        if kind not in KINDS:
            notes.append("dropped (%s): kind must be one of %s" % (tag, ", ".join(KINDS)))
            continue
        if not (title and why and expected and len(prompt) >= 80):
            notes.append("dropped (%s): needs a title, why, expected and a prompt of at least 80 characters" % tag)
            continue
        files = []
        for f in (p.get("files") if isinstance(p.get("files"), list) else [])[:6]:
            hit = _find(trees, (f or {}).get("path"), (f or {}).get("quote")) if isinstance(f, dict) else None
            if hit:
                files.append(hit)
            else:
                notes.append("note (%s): file %r left out, its quote is not in it" % (tag, (f or {}).get("path") if isinstance(f, dict) else f))
        if not files:
            notes.append("dropped (%s): no file whose quote is really in it" % tag)
            continue
        if not any(f["path"] in prompt or f["path"].rsplit("/", 1)[-1] in prompt for f in files):
            notes.append("dropped (%s): the prompt names none of its files (%s)" % (tag, ", ".join(f["path"] for f in files)))
            continue
        kept.append({"id": "p_" + secrets.token_hex(4), "target": target, "kind": kind, "title": title, "why": why, "expected": expected,
                     "files": files, "prompt": prompt, "by": by, "at": at, "state": "draft", "edited": False})
        notes.append("kept (%s): %s" % (tag, title))
    if len(proposals) > MAX_PER_CALL:
        notes.append("note: only the first %d proposals were read" % MAX_PER_CALL)
    if kept:   # new drafts replace old drafts for this target; copied prompts stay
        store["plans"] = [x for x in store["plans"] if not (x["target"] == target and x["state"] == "draft")] + kept
        store["plans"] = store["plans"][-200:]
    return notes


def decide(store, plan_id, state=None, prompt=None, at=None):
    p = next((x for x in store["plans"] if x["id"] == plan_id), None)
    if not p:
        raise NotFound("unknown plan")
    if state is not None:
        if state not in STATES:
            raise BadRequest("state must be draft, copied or dropped")
        p["state"] = state
        if state == "copied":
            p["copied_at"] = at
    if prompt is not None:
        prompt = prompt.replace("\r\n", "\n").strip()
        if not 1 <= len(prompt) <= 8000:
            raise BadRequest("the prompt must be 1 to 8000 characters")
        p["prompt"], p["edited"] = prompt, True
    return p
