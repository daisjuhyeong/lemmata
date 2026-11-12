"""Next experiments, planned by the researcher's own coding agent (S20, structured in S21).

Lemmata does not call a model. It hands the agent a brief for one claim or one experiment (experiment_brief): what the
claim says, which checklist items are missing, how each experiment was made (scripts, settings, commands), where ours is
behind a baseline, and the confounds already found. The agent designs up to three experiments and submits each as a
structured spec (propose_experiments): goal, a decision rule fixed before running, files to read, files to leave alone,
steps, commands, where results go. Lemmata checks the spec against the repository, then renders the run prompt from it
with one fixed template, so every prompt has the same sections. The guards against known agent failures (invented
numbers, edited evaluation code, overwritten results, stopping early or never stopping) live in the template, not in
what the agent happened to write. The researcher can change any field; the prompt is rendered again from the fields.
Nothing runs until they paste it into Claude Code.

Sources for the template: wiki/sprints/S21/S21-01-handoff.md.
"""
import re
import secrets

from .errors import BadRequest, NotFound

SCHEMA = "lemmata.plans/2"
KINDS = ("rerun", "seeds", "baseline", "ablation", "sensitivity", "new", "fix")
MAX_PER_CALL = 3
STATES = ("draft", "copied", "dropped")
LISTS = {"context": 12, "protected": 12, "steps": 12, "run": 8, "stop": 6}        # list fields and their caps
TEXTS = {"goal": 400, "supports": 300, "against": 300, "inconclusive": 300, "smoke": 400, "results_to": 300, "budget": 200, "baseline_check": 300}
REQUIRED = ("goal", "supports", "against", "results_to")

EXAMPLE = """{"kind": "seeds", "title": "Two more seeds for the main comparison",
 "why": "Each method has two runs, so the gap to ADWIN could be seed noise.",
 "files": [{"path": "train.py", "quote": "p.add_argument(\\"--dataset\\")"}],
 "goal": "Find out whether MCD's lower false-positive count on the main comparison holds with four seeds instead of two.",
 "decision": {"supports": "MCD's mean fp is lower than ADWIN's and DDM's on every dataset, by more than one std over 4 seeds",
              "against": "MCD's mean fp is not lower than ADWIN's on two or more datasets",
              "inconclusive": "the gap is within one std on any dataset"},
 "context": [{"path": "train.py", "role": "entry point; takes --dataset and --method"}, {"path": "config.yaml", "role": "lr 0.01, dropout 0.2"}],
 "protected": ["detect.py", "eval/", "data/", "results/main/"],
 "steps": ["Add a --seed option to train.py (default 1) and pass it to numpy and torch. No other changes to train.py."],
 "smoke": "python train.py --dataset Electricity --method MCD --seed 3 --limit 200",
 "run": ["for s in 3 4; do for d in Electricity Weather Covtype; do for m in MCD ADWIN DDM; do python train.py --dataset $d --method $m --seed $s; done; done; done"],
 "results_to": "results/main/{dataset},y_{method}_seed{seed}.csv, the layout seeds 1 and 2 already use (new files only)",
 "baseline_check": "ADWIN on Electricity gives fp 43.5 (mean of seeds 1 and 2) within 2.0",
 "budget": "at most 18 runs and 3 hours"}"""

GUIDE = """How to plan the next experiment for Lemmata.

The brief above holds the target: the claim (or the experiment and the claim it tests), its checklist, how each
experiment was made, where ours is behind, and the confounds already found. Open and read every file you will cite.

Design at most three experiments, cheapest decisive one first. Rank by how much each would change how far the claim can
be trusted, per hour of compute: a missing checklist item (more than one run, a baseline, an ablation, a paper table
that matches its file), a stale result whose code changed, a baseline ours is behind on, an open confound, then anything
new. Reuse the project's own scripts, settings and result layout. Prefer the smallest change that answers the question.

Submit each experiment as a structured spec with propose_experiments. Lemmata turns the spec into the run prompt with a
fixed template, which already tells the runner to branch, plan, smoke-test, write a manifest, verify, stop and report.
So write only what is specific to this experiment, for a fresh Claude Code session that has never seen this
conversation: real paths, real options, real values.

Fields:
- kind: rerun | seeds | baseline | ablation | sensitivity | new | fix
- title (under 90 characters); why (which gap it closes, one or two sentences)
- files: at least one {path, quote} the experiment builds on; the quote is copied from that file and Lemmata checks it
- goal: one sentence, what the run finds out
- decision: {supports, against, inconclusive}, measurable thresholds fixed before running (metric, datasets, seeds,
  margin). "Should improve" is not a decision rule.
- context: [{path, role}] files the runner should read first, and what each is for
- protected: paths to leave unchanged so the new numbers stay comparable: evaluation and metric code, data loading and
  splits, baseline code and configs, existing result folders. At least one.
- steps: the code or config changes this experiment needs, one per item, each as small as possible
- smoke: a short command that checks the pipeline end to end on a tiny budget (optional, recommended)
- run: the exact command(s) for the full experiment, seeds included
- results_to: where the result files go and in which layout, so Lemmata picks them up; new files only
- baseline_check: a known value the runner should reproduce first, with a tolerance (optional, recommended)
- budget: a cap on runs or hours (optional)
- stop: extra stop conditions for this experiment (optional)

<example>
{"proposals": [EXAMPLE]}
</example>

Lemmata keeps a proposal only if the kind is valid; title, why, goal, decision (supports and against), protected,
steps, run and results_to are filled; and at least one file quote is really in its file. It flags, without dropping,
paths that are not in the repository and commands that use scripts it cannot find. New drafts replace older drafts for
the same target; plans the researcher already copied are kept. Plan only: do not change code or run anything.
""".replace("EXAMPLE", EXAMPLE)


def load(hub):
    d = hub.read_json("plans.json", None)
    if not isinstance(d, dict) or not isinstance(d.get("plans"), list):
        d = {"schema": SCHEMA, "plans": []}
    d["plans"] = [p for p in d["plans"] if isinstance(p, dict) and isinstance(p.get("spec"), dict)]     # S20 drafts had no spec
    return d


def _targets(E):
    """{target: (kind, section or experiment)} for every claim/question and experiment."""
    out = {}
    for s in E["sections"]:
        if s["kind"] != "other":
            out["q:" + s["id"]] = ("claim", s)
        for x in s["experiments"]:
            out.setdefault("x:" + x["id"], ("experiment", x))
    return out


def _claims_of(E, target):
    kind, obj = _targets(E)[target]
    return [obj] if kind == "claim" else [s for s in E["sections"] if s["kind"] != "other" and any(x["id"] == obj["id"] for x in s["experiments"])]


def _exp_brief(x, details):
    try:
        d = details(x["id"]) or {}
    except Exception:
        d = {}
    des = d.get("design") or {}
    sm = x.get("summary") or {}
    return {"id": x["id"], "name": x["name"], "type": x.get("type"), "result_file": (x.get("result") or {}).get("path"),
            "metric": sm.get("measure") or sm.get("metric"), "lower_is_better": bool(sm.get("lower")), "ours": sm.get("ours_label"),
            "ours_value": sm.get("ours"), "methods": (sm.get("methods") or [])[:12], "runs_per_method": sm.get("n"),
            "datasets": (sm.get("datasets") or sm.get("cols") or [])[:12],
            "others": [{"method": v["label"], "value": v["value"], "gap": v["gap"]} for v in (sm.get("vs") or [])][:8],
            "scripts": [i["name"] for i in des.get("scripts", [])][:8], "settings": [i["name"] for i in des.get("settings", [])][:6],
            "values": {v["key"]: v["value"] for v in des.get("values", [])[:24]},
            "commands": [r.get("command") for r in des.get("runs", []) if r.get("command")][:4],
            "stale": [c.get("t") for c in d.get("caveats", []) if c.get("k") == "stale"][:2],
            "paper": [p.get("name") for p in d.get("paper", [])][:4] if isinstance(d.get("paper"), list) else []}


def brief(E, review, details, target, store):
    """Everything the agent needs to plan for one target ('q:<claim>' or 'x:<experiment>'). Data only; the guide goes after it."""
    T = _targets(E)
    if target not in T:
        raise NotFound("unknown target %r: use 'q:<claim id>' or 'x:<experiment id>'" % target)
    kind, obj = T[target]
    rows = {r["id"]: r for r in (review or {}).get("questions", [])}

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
    return {"schema": "lemmata.plan_brief/2", "target": target, "kind": kind,
            "project": {"ours": (review or {}).get("ours"), "base_method": (ext.get("base") or {}).get("name") if isinstance(ext.get("base"), dict) else None,
                        "goal": ext.get("goal"), "hoped_conclusion": (review or {}).get("hoped") or None},
            "claims": [claim_part(s) for s in _claims_of(E, target)][:4],
            "experiments": [_exp_brief(x, details) for x in xs],
            "already_planned": [{"title": p["title"], "kind": p["kind"], "state": p["state"]} for p in store["plans"] if p["target"] == target and p["state"] != "dropped"]}


# ------------------------------------------------------------------ checking against the repository
def _sq(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def _rel(path):
    p = str(path or "").strip()
    if p.startswith(("/", "../", "~")):
        return ""
    p = p.split(":", 1)[-1] if re.match(r"^(code|paper):", p) else p
    while p.startswith("./"):
        p = p[2:]
    return p


def _find(trees, path, quote):
    path, q = _rel(path), _sq(quote)
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


def files_of(trees):
    out = set()
    for tr in (trees or {}).values():
        try:
            out |= set(tr.list_files())
        except Exception:
            pass
    return out


def _glob_rx(p):
    out, i = "", 0
    while i < len(p):
        if p.startswith("**", i):
            out, i = out + ".*", i + 2
        elif p[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif p[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(p[i]), i + 1
    return re.compile("^" + out + "($|/)")


def _exists(path, files):
    """'file' | 'dir' | 'glob' | None."""
    p = _rel(path).rstrip("/")
    if not p:
        return None
    if any(c in p for c in "*?"):
        rx = _glob_rx(p)
        return "glob" if any(rx.match(f) for f in files) else None
    if p in files:
        return "file"
    return "dir" if any(f.startswith(p + "/") for f in files) else None


def _text(v, n):
    return " ".join(str(v).split())[:n] if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ""


def _ctx_line(t):
    m = re.match(r"^\s*(\S+?)\s*(?:(?:—|–|:| - )\s*(.*))?$", t)
    return {"path": m.group(1)[:200], "role": " ".join((m.group(2) or "").split())[:160]} if m else None


def _list(k, v, n):
    if isinstance(v, str):
        v = v.split("\n")
    if not isinstance(v, list):
        return []
    out = []
    for x in v[:40]:
        if k == "context":
            e = {"path": _text(x.get("path"), 200), "role": _text(x.get("role"), 160)} if isinstance(x, dict) else _ctx_line(str(x)) if isinstance(x, str) and x.strip() else None
            if e and e["path"]:
                out.append(e)
        elif isinstance(x, (str, int, float)) and not isinstance(x, bool):
            t = str(x).strip()[:600 if k in ("run", "steps") else 300]
            if t:
                out.append(t)
    return out[:n]


def _spec(p, base=None):
    """A clean spec from an agent proposal or a researcher's edit (merged over `base`)."""
    s = dict(base or {})
    d = p.get("decision") if isinstance(p.get("decision"), dict) else {}
    for k, n in TEXTS.items():
        if k in p:
            s[k] = (str(p[k] or "").strip()[:n] if isinstance(p[k], str) else "") if k == "smoke" else _text(p[k], n)
        elif k in ("supports", "against", "inconclusive") and k in d:
            s[k] = _text(d[k], n)
    for k, n in LISTS.items():
        if k in p:
            s[k] = _list(k, p[k], n)
    for k in TEXTS:
        s.setdefault(k, "")
    for k in LISTS:
        s.setdefault(k, [])
    return s


def lint(spec, files):
    """Warnings for the researcher; they never block."""
    w = []
    for k, label in (("goal", "the goal"), ("supports", "when it supports the claim"), ("against", "when it counts against it"), ("results_to", "where results go")):
        if not spec.get(k):
            w.append("Missing " + label + ".")
    if not spec["protected"]:
        w.append("Nothing is protected: the runner may change evaluation code or results.")
    if not spec["run"]:
        w.append("No command to run.")
    for p in spec["protected"]:
        if files and not _exists(p, files):
            w.append("Protected path not in the repository: " + p)
    for c in spec["context"]:
        if files and not _exists(c["path"], files):
            w.append("File to read not in the repository: " + c["path"])
    made = " ".join(spec["steps"])
    for cmd in spec["run"] + ([spec["smoke"]] if spec["smoke"] else []):
        for tok in re.findall(r"[\w./-]+\.(?:py|sh|ipynb|R|jl)\b", cmd):
            if files and not _exists(tok, files) and tok.rsplit("/", 1)[-1] not in made:
                w.append("A command uses " + tok + ", which is not in the repository and no step creates it.")
    if re.search(r"\b(should|might|will)\s+(improve|help|be better|increase)\b", (spec.get("supports") or "").lower()):
        w.append("'Supports' is not measurable yet: name the metric, datasets and margin.")
    out = []
    for x in w:
        if x not in out:
            out.append(x)
    return out[:12]


def deny_rules(spec, files):
    """Claude Code permission rules that block its edit tools on the protected paths (for .claude/settings.local.json)."""
    out = []
    for p in spec["protected"]:
        r = _rel(p).rstrip("/")
        if not r:
            continue
        kind = _exists(r, files) if files else ("dir" if str(p).endswith("/") else "file")
        rule = "Edit(./%s)" % r if kind in ("file", "glob") or any(c in r for c in "*?") else "Edit(./%s/**)" % r
        if rule not in out:
            out.append(rule)
    return out


# ------------------------------------------------------------------ the prompt, rendered from the spec
def render(p):
    s, c = p["spec"], p.get("claim") or {}
    run_dir = ".lemmata/exp/" + p["id"]
    L = ['<experiment id="%s" kind="%s">' % (p["id"], p["kind"]), "", "<goal>", s["goal"] or "(goal not set)"]
    if c.get("text"):
        L.append('This tests the claim %s: "%s"' % (c.get("label") or "", c["text"]))
    if p.get("why"):
        L.append("Why it matters: " + p["why"])
    L += ["Test this fairly, not to confirm it: a clean negative or inconclusive result is a successful run.", "</goal>", "",
          "<decision_rule>", "Fixed before running. Do not change these thresholds after seeing results.",
          "- Supports the claim if: " + (s["supports"] or "(not set)"),
          "- Counts against it if: " + (s["against"] or "(not set)"),
          "- Inconclusive if: " + (s["inconclusive"] or "neither of the above holds"), "</decision_rule>", "",
          "<context>", "Read these before editing anything (paths from the repository root):"]
    seen = set()
    for f in p.get("files", []):
        seen.add(f["path"])
        role = next((x["role"] for x in s["context"] if _rel(x["path"]) == f["path"] and x["role"]), "")
        L.append('- %s:%d%s; it contains "%s"' % (f["path"], f["line"], (" (" + role + ")") if role else "", f["quote"]))
    for x in s["context"]:
        if _rel(x["path"]) not in seen:
            seen.add(_rel(x["path"]))
            L.append("- %s%s" % (x["path"], (" (" + x["role"] + ")") if x["role"] else ""))
    L += ["</context>", "", "<protected>", "Leave these unchanged, so the new numbers stay comparable with the existing ones:"]
    L += ["- " + x for x in s["protected"]] or ["- (none listed)"]
    L += ["Read existing result files, but never overwrite or delete them.",
          "If the experiment seems to need a change to any of these, stop and report why instead of changing them.", "</protected>", "",
          "<steps>", "1. Run `git status`, then create and switch to a branch `exp/%s`. Read the files in <context>." % p["id"],
          "2. Write a short plan (3 to 6 lines: what you will change, which commands, expected runtime), then continue."]
    n = 3
    for st in s["steps"]:
        L.append("%d. %s" % (n, st))
        n += 1
    if s["baseline_check"]:
        L.append("%d. Before the full run, reproduce this known value: %s. If it does not reproduce, stop and report." % (n, s["baseline_check"]))
        n += 1
    if s["smoke"]:
        L.append("%d. Smoke test: `%s`. Check that it writes a result file in the expected format." % (n, s["smoke"]))
        n += 1
    runs = s["run"] or ["(command not set)"]
    L.append("%d. Full run:%s" % (n, " `" + runs[0] + "`" if len(runs) == 1 else ""))
    n += 1
    if len(runs) > 1:
        L += ["   - `" + r + "`" for r in runs]
    if s["budget"]:
        L.append("   Budget: " + s["budget"].rstrip(".") + ".")
    L += ["%d. Compute the reported numbers from the saved result files with a script saved as %s/analyze.py, not by reading logs." % (n, run_dir), "</steps>", "",
          "<outputs>", "Result files: " + (s["results_to"] or "(not set)").rstrip(".") + ". Write new files only.",
          "Also write, under %s/:" % run_dir,
          "- manifest.json: per run, the command, git commit, config values, seed, start and end time, exit status, result file path",
          "- summary.csv: one row per method and seed, with the metric columns", "</outputs>", "",
          "<verification>", "Before reporting, check:",
          "- Every run in manifest.json exited with status 0, and its result file exists and is not empty.",
          "- `git diff --stat` shows no change to the protected paths.",
          "- The numbers in your report are exactly those analyze.py prints.", "</verification>", "",
          "<stop_conditions>", "Stop and write the report with status FAILED or BLOCKED, instead of continuing, if:",
          "- the same error comes back after two attempts to fix it;", "- the experiment would need a change to a protected path;"]
    if s["baseline_check"]:
        L.append("- the known value does not reproduce within its tolerance;")
    if s["budget"]:
        L.append("- the budget would be exceeded;")
    L += ["- " + x.rstrip(";.") + ";" for x in s["stop"]]
    L += ["Never put synthetic, placeholder or estimated numbers in place of results a completed run did not produce. Reporting a clear failure is a correct and useful outcome.",
          "</stop_conditions>", "", "<report_format>",
          "Status: COMPLETED | FAILED | BLOCKED",
          "Decision: SUPPORTS | AGAINST | INCONCLUSIVE (per <decision_rule>)",
          "Results: method by metric, mean ± std over seeds, from %s/summary.csv" % run_dir,
          "Evidence: the commands run and their exit codes; the result file paths",
          "Changes: each file edited, with a one-line reason; confirm the protected paths are untouched",
          "Deviations from the plan and anything surprising",
          "Next step: one line", "</report_format>", "", "</experiment>"]
    return "\n".join(L)


def view(store, files=None):
    files = files or set()
    out = []
    for p in store["plans"]:
        if p.get("state") == "dropped":
            continue
        q = dict(p)
        q["prompt"], q["lint"], q["deny"] = render(p), lint(p["spec"], files), deny_rules(p["spec"], files)
        out.append(q)
    return {"schema": SCHEMA, "plans": out}


def _claim_ref(E, target):
    cs = _claims_of(E, target)
    return {"label": cs[0]["label"], "text": " ".join(str(cs[0]["text"]).split())[:300]} if cs else None


def propose(store, E, trees, target, proposals, by, at):
    """Check an agent's proposals and keep what holds. -> [notes]"""
    if target not in _targets(E):
        raise NotFound("unknown target %r" % target)
    if not isinstance(proposals, list) or not proposals:
        raise BadRequest("proposals must be a non-empty list")
    files = files_of(trees)
    notes, kept = [], []
    for i, p in enumerate(proposals[:MAX_PER_CALL]):
        tag = "proposal %d" % (i + 1)
        if not isinstance(p, dict):
            notes.append("dropped (%s): not an object" % tag)
            continue
        kind, title, why = p.get("kind"), _text(p.get("title"), 90), _text(p.get("why"), 600)
        if kind not in KINDS:
            notes.append("dropped (%s): kind must be one of %s" % (tag, ", ".join(KINDS)))
            continue
        spec = _spec(p)
        missing = ([] if title else ["title"]) + ([] if why else ["why"]) + [k for k in REQUIRED if not spec[k]] + [k for k in ("protected", "steps", "run") if not spec[k]]
        if missing:
            notes.append("dropped (%s): missing %s (supports and against go in decision)" % (tag, ", ".join(missing)))
            continue
        hits = []
        for f in (p.get("files") if isinstance(p.get("files"), list) else [])[:6]:
            hit = _find(trees, (f or {}).get("path"), (f or {}).get("quote")) if isinstance(f, dict) else None
            if hit:
                hits.append(hit)
            else:
                notes.append("note (%s): file %r left out, its quote is not in it" % (tag, (f or {}).get("path") if isinstance(f, dict) else f))
        if not hits:
            notes.append("dropped (%s): no file whose quote is really in it" % tag)
            continue
        kept.append({"id": "p_" + secrets.token_hex(4), "target": target, "kind": kind, "title": title, "why": why, "files": hits, "spec": spec,
                     "claim": _claim_ref(E, target), "by": by, "at": at, "state": "draft", "edited": False})
        w = lint(spec, files)
        notes.append("kept (%s): %s%s" % (tag, title, (" · check: " + "; ".join(w[:4])) if w else ""))
    if len(proposals) > MAX_PER_CALL:
        notes.append("note: only the first %d proposals were read" % MAX_PER_CALL)
    if kept:   # new drafts replace old drafts for this target; copied plans stay
        store["plans"] = [x for x in store["plans"] if not (x["target"] == target and x["state"] == "draft")] + kept
        store["plans"] = store["plans"][-200:]
    return notes


def decide(store, plan_id, state=None, spec=None, title=None, at=None):
    """The researcher keeps, edits or drops a plan. `spec` holds only the fields that changed."""
    p = next((x for x in store["plans"] if x["id"] == plan_id), None)
    if not p:
        raise NotFound("unknown plan")
    if state is not None:
        if state not in STATES:
            raise BadRequest("state must be draft, copied or dropped")
        p["state"] = state
        if state == "copied":
            p["copied_at"] = at
    if spec is not None:
        if not isinstance(spec, dict) or not spec or any(k not in TEXTS and k not in LISTS for k in spec):
            raise BadRequest("spec may hold only these fields: " + ", ".join(list(TEXTS) + list(LISTS)))
        p["spec"], p["edited"] = _spec(spec, p["spec"]), True
    if title is not None:
        t = _text(title, 90)
        if not t:
            raise BadRequest("the title must not be empty")
        p["title"], p["edited"] = t, True
    return p
