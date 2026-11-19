"""The bench (S35, ADR-011): what the VS Code extension shows, as rows that are ready to draw.

VS Code is where experiments are run, so it shows runs, experiments, their setup and what to run next, and nothing else.
The extension is the one part of Lemmata that does not update itself, so the wording and the rules stay here: every row
carries its label, description, tooltip and icon name, and says what can be done with it (open a file, open the website,
copy a prompt, snooze). The extension only draws rows and adds what it alone knows: the runs on its own machine.

Nothing here is new knowledge. The rows are read from the experiments, the Setup document, the to-do list, the planned
experiments and the logged runs. The one thing stored is which run the researcher attached to which experiment by hand
(bench.json). No model runs here (ADR-006).
"""
from .errors import BadRequest, NotFound

SCHEMA = "lemmata.bench/1"
VERSION = 1          # raise when a row needs something an older extension cannot draw
STORE = "bench.json"
# the to-do kinds that are about running something; everything about the paper stays on the website
TO_RUN = ("not_run", "stale", "seeds", "contradicts", "plan", "setup_missing", "setup_direction")
NEEDS_CLAIM = ("seeds", "setup_missing", "setup_direction")      # a gap in an experiment that backs no claim is often deliberate
ICONS = {"not_run": "circle-large-outline", "stale": "history", "seeds": "symbol-numeric", "contradicts": "warning", "plan": "lightbulb",
         "setup_missing": "circle-slash", "setup_direction": "arrow-swap"}


def load(hub):
    d = hub.read_json(STORE, None)
    if not isinstance(d, dict) or not isinstance(d.get("attached"), dict):
        d = {"schema": SCHEMA, "attached": {}}
    d["attached"] = {k: v for k, v in d["attached"].items() if isinstance(k, str) and isinstance(v, str)}
    return d


def attach(store, run_ids, exp_ids, run_id, exp_id):
    """The researcher says which experiment a run belongs to; it counts at once (ADR-007). An empty experiment undoes it."""
    if not isinstance(run_id, str) or run_id not in run_ids:
        raise NotFound("unknown run %r" % (run_id,))
    if exp_id in (None, ""):
        store["attached"].pop(run_id, None)
        return store
    if not isinstance(exp_id, str) or exp_id not in exp_ids:
        raise NotFound("unknown experiment %r" % (exp_id,))
    store["attached"][run_id] = exp_id
    if len(store["attached"]) > 5000:      # runs.json keeps the newest runs only; so does this
        for k in sorted(store["attached"])[:len(store["attached"]) - 5000]:
            store["attached"].pop(k)
    return store


# ---------------------------------------------------------------- small helpers
def num(v):
    """A number as a person would write it: at most four significant digits, no trailing zeros."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    if v != v or v in (float("inf"), float("-inf")):
        return str(v)
    if isinstance(v, int) or float(v).is_integer() and abs(v) < 1e15:
        return str(int(v))
    s = "%.4g" % v
    return s if "e" in s else s.rstrip("0").rstrip(".") if "." in s else s


def trunc(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def direction(lower):
    return "lower is better" if lower is True else "higher is better" if lower is False else "direction not set"


def names(xs, cap=6):
    xs = [str(x) for x in xs or []]
    return ", ".join(xs[:cap]) + (" and %d more" % (len(xs) - cap) if len(xs) > cap else "")


def _when(r):
    return r.get("ended") or r.get("started") or r.get("received") or ""


def _clock(t):
    return (t or "")[5:16].replace("T", " ")


def _fields_text(fl):
    return " ".join("%s=%s" % (k, ",".join(v[:3]) if isinstance(v, list) else v) for k, v in sorted((fl or {}).items()))


def _row(rid, label, description=None, tooltip=None, icon=None, **more):
    r = {"id": rid, "label": trunc(label, 120)}
    if description:
        r["description"] = trunc(description, 160)
    if tooltip:
        r["tooltip"] = str(tooltip)[:1500]
    if icon:
        r["icon"] = icon
    r.update({k: v for k, v in more.items() if v not in (None, [], {})})
    return r


# ---------------------------------------------------------------- runs
def _metric_of(run, x_metric):
    m = run.get("metrics") or {}
    if x_metric and isinstance(m.get(x_metric), (int, float)) and not isinstance(m.get(x_metric), bool):
        return x_metric
    return next((k for k, v in m.items() if isinstance(v, (int, float)) and not isinstance(v, bool)), None)


def _same_cell(a, fa, b, fb):
    """Two runs are comparable when the result pattern read the same fields from both (dataset, method, seed, ...), or,
    when the pattern names no field, when they are the same command. Anything else would compare unlike with unlike."""
    if fa or fb:
        return bool(fa) and fa == fb
    ca, cb = (a.get("command") or "").strip(), (b.get("command") or "").strip()
    return bool(ca) and ca == cb


def link_runs(mine_of, order, metric_of, lower_of, name_of):
    """mine_of: {experiment id: [(run, fields, how)] oldest first}. -> {run id: annotation}.
    A run that fits several experiments (two experiments read the same files) is shown under the first one that the
    researcher attached it to, then the first whose files it wrote, in the order of the Thesis page."""
    rank = {"attached": 0, "wrote": 1, "script": 2, "names": 3}
    best = {}
    for xi, xid in enumerate(order):
        for run, fields, how in mine_of.get(xid) or []:
            rid = run.get("run_id")
            if not rid:
                continue
            key = (rank.get(how, 9), 0 if _metric_of(run, metric_of.get(xid)) == metric_of.get(xid) and metric_of.get(xid) else 1, xi)
            if rid not in best or key < best[rid][0]:
                best[rid] = (key, xid, fields, how)
    out = {}
    for xid in order:
        mine = [(r, f) for r, f, _ in mine_of.get(xid) or [] if best.get(r.get("run_id"), (0, None))[1] == xid]
        for i, (run, fields) in enumerate(mine):
            rid = run["run_id"]
            _, _, _, how = best[rid]
            key = _metric_of(run, metric_of.get(xid))
            prev = None
            if key is not None:
                for old, of in reversed(mine[:i]):
                    v = (old.get("metrics") or {}).get(key)
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and _same_cell(run, fields, old, of):
                        prev = {"id": old["run_id"], "t": _when(old), "sha": (old.get("git_sha") or "")[:7] or None, "value": v}
                        break
            line = None
            if key is not None:
                line = "%s %s" % (key, num(run["metrics"][key]))
                if prev:
                    line += ", was %s" % num(prev["value"])
                    if key == metric_of.get(xid) and lower_of.get(xid) is not None:
                        line += " (%s)" % direction(lower_of[xid])
            out[rid] = {"x": xid, "name": name_of.get(xid) or xid, "how": how, "fields": {k: v[:6] for k, v in (fields or {}).items()},
                        "metric": key, "prev": prev, "line": line}
    return out


# ---------------------------------------------------------------- experiments
def _result_line(x):
    sm = x.get("summary") or {}
    if not isinstance(sm.get("ours"), (int, float)):
        return None
    bits = ["ours %s" % num(sm["ours"])]
    b = sm.get("best") or {}
    if isinstance(b.get("value"), (int, float)):
        bits.append("best other %s (%s)" % (num(b["value"]), b.get("label") or "?"))
    return " · ".join(bits)


def _per_dataset(x):
    """One line per dataset: ours and the best other method, read from the experiment's own grid."""
    sm, g = x.get("summary") or {}, x.get("grid") or {}
    ours, lower = sm.get("ours_label"), sm.get("lower")
    rows = [r for r in g.get("rows") or [] if isinstance(r.get("values"), dict)]
    mine = next((r for r in rows if r.get("label") == ours), None)
    if not mine or lower is None:
        return []
    out = []
    for ds in (g.get("datasets") or [])[:40]:
        v = mine["values"].get(ds)
        if not isinstance(v, (int, float)):
            continue
        others = [(r["values"][ds], r.get("label")) for r in rows if r is not mine and isinstance(r["values"].get(ds), (int, float))]
        text = "ours %s" % num(v)
        if others:
            bv, bl = (min if lower else max)(others, key=lambda o: o[0])
            text += " · best other %s (%s)" % (num(bv), bl)
        out.append((ds, text))
    return out


def _exp_row(x, sx, secs, link, mine, to_run_n, ann):
    """One experiment and, under it, its setup in one line each."""
    xid, P = x["id"], (sx or {}).get("protocol") or {}
    sm = x.get("summary") or {}
    ctx = (sx or {}).get("context") or {}
    res = x.get("result") or {}
    status = (link or {}).get("status")
    not_run = status == "not_run" or (not res.get("path") and not sm)
    site = {"view": "experiments", "sel": "x:" + xid}
    kids = []
    for sec in secs:
        kids.append(_row("%s|tests|%s" % (xid, sec["id"]), "Tests %s" % (sec.get("short") or sec.get("label") or "a claim"), sec.get("text"),
                         "%s\n\n%s" % (sec.get("text") or "", sec.get("stage_why") or ""), "target", site={"view": "experiments", "sel": "q:" + sec["id"]}))
    if not secs:
        kids.append(_row(xid + "|tests", "Tests no claim", "A result that backs no claim has no reason to be in the paper.", None, "warning", site=site))
    metric = P.get("metric") or sm.get("measure")
    lower = P.get("lower") if P else sm.get("lower")
    if metric:
        kids.append(_row(xid + "|measure", "Measure", "%s · %s" % (metric, direction(lower)),
                         "The number read from each result file, and which way is better. Set on the website (Setup).", "symbol-numeric"))
    if P.get("datasets"):
        kids.append(_row(xid + "|datasets", "Datasets", "%d · %s" % (len(P["datasets"]), names(P["datasets"])), ", ".join(map(str, P["datasets"])), "database"))
    ms = [m for m in P.get("methods") or [] if isinstance(m, dict)]
    if ms:
        kids.append(_row(xid + "|methods", "Methods", "%d · %s" % (len(ms), names([m["name"] + (" (ours)" if m.get("role") == "ours" else "") for m in ms])),
                         ", ".join(m["name"] for m in ms), "list-unordered"))
    seeds = P.get("seeds")
    if isinstance(seeds, list) and len(seeds) == 2 and all(isinstance(s, int) for s in seeds):
        lo, hi = seeds
        kids.append(_row(xid + "|seeds", "Runs per result", "one, so no spread can be reported" if hi <= 1 else str(lo) if lo == hi else "%d to %d" % (lo, hi),
                         None, "warning" if hi <= 1 else "symbol-numeric"))
    line = _result_line(x)
    per = _per_dataset(x)
    if line or per:
        col = sm.get("metric")
        kids.append(_row(xid + "|result", "Result", (line or "") + (" · on %s" % col if line and col else ""), None, "graph",
                         kids=[_row("%s|result|%s" % (xid, ds), ds, text) for ds, text in per]))
    for c in (sx or {}).get("checklist") or []:
        if c.get("a") == "no" and c.get("k") not in ("paper", "seeds", "current"):      # paper checks stay on the website; runs per result and out of date have their own rows
            kids.append(_row("%s|check|%s" % (xid, c.get("k")), "Check", c.get("why") or c.get("q"), "%s\n\n%s" % (c.get("q") or "", c.get("why") or ""), "warning", site=site))
    if x.get("stale"):
        kids.append(_row(xid + "|stale", "Out of date", x["stale"] if isinstance(x["stale"], str) else "The code or settings changed after this result was written.",
                         "Rerun it, or check that the change does not touch this result.", "history", site=site))
    where = ctx.get("where") or {}
    folder = where.get("folder") or (res.get("path") or "").rsplit("/", 1)[0]
    if res.get("path") or folder:
        n = where.get("files_n") or x.get("files_n")
        kids.append(_row(xid + "|files", "Files", "%s%s" % (folder or res.get("path"), " · %d files" % n if n else ""), res.get("path"), "folder",
                         open={"repo": res.get("repo") or x.get("repo") or "code", "path": res.get("path"), "line": 1} if res.get("path") else None))
    when = ctx.get("when") or {}
    who = ctx.get("who") or {}
    last = when.get("last") or x.get("last")
    if last:
        kids.append(_row(xid + "|when", "Last written", " · ".join(b for b in [last[:10], "%d update%s" % (when["updates"], "" if when["updates"] == 1 else "s") if when.get("updates") else None,
                                                                              "commit %s" % who["commit"] if who.get("commit") else None] if b), who.get("subject"), "calendar"))
    how = ctx.get("how") or {}
    if how.get("command") or how.get("scripts"):
        kids.append(_row(xid + "|how", "Made by", how.get("command") or ", ".join(how.get("scripts") or []), how.get("command"), "terminal",
                         copy={"what": "the command", "text": how["command"]} if how.get("command") else None))
    if mine:
        rk = []
        for run, fields, h in mine[-6:][::-1]:
            a = ann.get(run.get("run_id")) or {}
            rk.append(_row("%s|run|%s" % (xid, run.get("run_id")), _clock(_when(run)) or "run",
                           " · ".join(b for b in [run.get("host"), ((run.get("git_sha") or "")[:7] or "no commit") + ("+changes" if run.get("dirty") else ""),
                                                  _fields_text(fields), a.get("line") if a.get("x") == xid else None,
                                                  "failed (exit %s)" % run["exit_code"] if run.get("exit_code") not in (None, 0) else None,
                                                  "attached by you" if h == "attached" else None] if b),
                           run.get("command"), "error" if run.get("exit_code") not in (None, 0) else "pass", run=run.get("run_id")))
        kids.append(_row(xid + "|runs", "Runs", "%d logged" % len(mine), "Runs logged from the editor, the results watcher or the coding agent.", "beaker", kids=rk))
    desc = [b for b in ["out of date" if x.get("stale") else None, "not run yet" if not_run else None, line,
                        "%d to run" % to_run_n if to_run_n else None] if b]
    tip = [x.get("name") or xid, x.get("caption") or P.get("note") or "", "Tests: " + (", ".join(s.get("short") or s.get("label") or "" for s in secs) or "no claim")]
    if metric:
        tip.append("Measure: %s (%s)" % (metric, direction(lower)))
    return _row(xid, x.get("name") or xid, " · ".join(desc), "\n".join(t for t in tip if t), "history" if x.get("stale") else "circle-large-outline" if not_run else "beaker",
                x=xid, site=site, tab={"view": "setup", "sel": "x:" + xid}, kids=kids,
                copy={"what": "a prompt for Claude Code", "text": prompt(x, P, None, None)})


def prompt(x, P, text, why, project=None):
    """What to paste into Claude Code for one experiment. It names the Lemmata tools; the agent reads the brief itself."""
    metric, lower = (P or {}).get("metric") or (x.get("summary") or {}).get("measure"), (P or {}).get("lower")
    L = ["Lemmata experiment: %s (target x:%s)%s." % (x.get("name") or x["id"], x["id"], " in project %s" % project if project else "")]
    if text:
        L.append("To do: %s%s" % (text, (" " + why) if why else ""))
    L += ["Before running anything, call the Lemmata tool experiment_brief with target \"x:%s\" and read the scripts and settings it names." % x["id"]]
    if metric:
        L.append("The measure is %s (%s). Do not change the measure, its direction or any decision threshold." % (metric, direction(lower)))
    L += ["Run it the way the brief says it was made. A clean negative result is a successful run.",
          "Report the command, the commit, what you changed and the numbers. Lemmata's hook logs the run; do not edit result files by hand."]
    return "\n".join(L)


# ---------------------------------------------------------------- the document
def build(E, S, T, P, runs, mine_of, today, project=None):
    """E: experiments, S: Setup, T: to-do, P: planned experiments, runs: logged runs newest first (runs.view rows),
    mine_of: {experiment id: [(run, fields, how)]}. -> the bench document."""
    sx_of = {x["id"]: x for x in (S or {}).get("experiments") or []}
    order, x_of, secs_of, link_of = [], {}, {}, {}
    for sec in E.get("sections") or []:
        for x in sec.get("experiments") or []:
            if x["id"] not in x_of:
                x_of[x["id"]] = x
                order.append(x["id"])
                secs_of[x["id"]] = []
            if sec.get("kind") != "other":
                secs_of[x["id"]].append(sec)
                link_of.setdefault(x["id"], (sec.get("links") or {}).get(x["id"]))
    prot = {i: (sx_of.get(i) or {}).get("protocol") or {} for i in order}
    metric_of = {i: prot[i].get("metric") or (x_of[i].get("summary") or {}).get("measure") for i in order}
    lower_of = {i: prot[i].get("lower") if prot[i] else (x_of[i].get("summary") or {}).get("lower") for i in order}
    name_of = {i: x_of[i].get("name") or i for i in order}
    ann = link_runs(mine_of, order, metric_of, lower_of, name_of)

    # --- to run: the to-do items about running something, under their experiment
    plans = {str(p.get("id")): p for p in (P or {}).get("plans") or []}
    item_x = {it["id"]: [i for i in it.get("experiments") or [] if secs_of.get(i)] for it in (S or {}).get("items") or []}
    by_x, loose, seen_plans = {}, [], set()

    def exp_of(target):
        sel = str((target or {}).get("sel") or "")
        if sel.startswith("x:") and sel[2:] in x_of:
            return sel[2:]
        if sel.startswith("i:"):
            return next(iter(item_x.get(sel[2:]) or []), None)
        return None

    for it in (T or {}).get("items") or []:
        k = it.get("kind")
        if k not in TO_RUN:
            continue
        p = plans.get(it["key"].split(":", 1)[1]) if k == "plan" else None
        xid = exp_of(it.get("target")) or (exp_of({"sel": (p or {}).get("target")}) if p else None)
        if k in NEEDS_CLAIM and not (xid and secs_of.get(xid)):
            continue
        if p:
            seen_plans.add(str(p.get("id")))
        x = x_of.get(xid)
        text = (p or {}).get("title") or it["text"]
        row = _row(it["key"], text, it.get("why"), "%s\n\n%s%s" % (it["text"], it.get("why") or "", "\n\nRule: %s" % it["rule"] if it.get("rule") else ""),
                   ICONS.get(k, "circle-outline"), kind=k, snooze=it["key"], x=xid, due=it.get("due"),
                   site=it.get("target") if (it.get("target") or {}).get("view") in ("experiments", "setup") else None,
                   copy={"what": "the run prompt", "text": p["prompt"]} if p and p.get("prompt")
                   else {"what": "a prompt for Claude Code", "text": prompt(x, prot.get(xid), it["text"], it.get("why"), project)} if x else None)
        (by_x.setdefault(xid, []) if xid else loose).append(row)
    for pid, p in plans.items():      # a plan whose prompt was copied is being run: it stays until it is dropped on the website
        if pid in seen_plans or p.get("state") != "copied":
            continue
        xid = exp_of({"sel": p.get("target")})
        row = _row("plan:" + pid, p.get("title") or "Planned experiment", "prompt copied %s" % str(p.get("copied_at") or p.get("at") or "")[:10],
                   p.get("why"), "lightbulb", kind="plan", x=xid, site={"view": "experiments"},
                   copy={"what": "the run prompt", "text": p["prompt"]} if p.get("prompt") else None)
        (by_x.setdefault(xid, []) if xid else loose).append(row)
    to_run = list(loose)
    for xid in order:
        if by_x.get(xid):
            to_run.append(_row("x|" + xid, name_of[xid], "%d to run" % len(by_x[xid]), None, "beaker", x=xid, expanded=True, kids=by_x[xid],
                               site={"view": "experiments", "sel": "x:" + xid}))
    n_to_run = len(loose) + sum(len(v) for v in by_x.values())

    # --- experiments, under the claim each tests
    rows, placed = [], set()
    for sec in E.get("sections") or []:
        xs = [x for x in sec.get("experiments") or []]
        if not xs:
            continue
        kids = []
        for x in xs:
            kids.append(_exp_row(x, sx_of.get(x["id"]), secs_of[x["id"]], (sec.get("links") or {}).get(x["id"]) or link_of.get(x["id"]),
                                 mine_of.get(x["id"]) or [], len(by_x.get(x["id"]) or []), ann))
            placed.add(x["id"])
        other = sec.get("kind") == "other"
        label = "No claim" if other else "%s · %s" % (sec.get("short") or sec.get("label") or "Claim", trunc(sec.get("text"), 70))
        rows.append(_row("q|" + sec["id"], label, None if other else sec.get("stage"), None if other else "%s\n\n%s" % (sec.get("text") or "", sec.get("stage_why") or ""),
                         "question" if other else "target", expanded=True, kids=kids, site={"view": "experiments", "sel": "q:" + sec["id"]} if not other else None))

    # --- runs: what the hub knows about each, and today's runs for the machines that did not make them
    known = {r.get("run_id"): r for r in runs}
    elsewhere = []
    for r in runs:
        if _when(r)[:10] != today or r.get("kind") == "command":
            continue
        a = ann.get(r.get("run_id")) or {}
        failed = r.get("exit_code") not in (None, 0)
        elsewhere.append(_row(r["run_id"], r.get("command") or "Results watcher: %s" % ((r.get("artifacts") or [{}])[0].get("path") or ""),
                              " · ".join(b for b in [r.get("host"), _clock(_when(r)), a.get("name"), a.get("line"), "failed" if failed else None] if b),
                              r.get("command"), "error" if failed else "pass", run=r["run_id"], x=a.get("x")))
    unattached = sum(1 for r in runs[:200] if r.get("kind") != "command" and r.get("run_id") not in ann)
    return {"schema": SCHEMA, "version": VERSION, "today": today, "project": project,
            "runs": {rid: a for rid, a in ann.items() if rid in known},
            "elsewhere": elsewhere[:60],
            "experiments": rows,
            "to_run": to_run,
            "pick": [{"id": i, "label": name_of[i], "description": ", ".join(s.get("short") or s.get("label") or "" for s in secs_of[i]) or "no claim"} for i in order],
            "counts": {"experiments": len(order), "to_run": n_to_run, "stale": sum(1 for i in order if x_of[i].get("stale")),
                       "runs_today": len(elsewhere), "unattached": unattached, "snoozed": ((T or {}).get("counts") or {}).get("snoozed", 0)}}
