"""Work sessions (S26): a day's records grouped so that one card answers who, where, what, why, how, when and with what result.
A session is activity in one place with no gap longer than GAP. Rules only; the one-line summary may be drafted by the
researcher's own coding agent and is shown as a draft until the researcher confirms it (ADR-007: Lemmata drafts, I confirm)."""
import hashlib
import os
import re
import shlex
from datetime import datetime, timezone

from .errors import BadRequest, NotFound

SCHEMA = "lemmata.sessions/1"
GAP = 3600          # seconds without a record before a new session starts (founder, chat 2026-11-16 14:10 KST: one hour)
TYPES = ("run", "script", "analysis", "inspection", "setup", "git", "writing", "other")
TYPE_WORD = {"run": "experiment run", "script": "script", "analysis": "analysis", "inspection": "inspection", "setup": "set-up", "git": "git", "writing": "paper build", "other": "other"}

INSPECT = {"ls", "ll", "cat", "head", "tail", "less", "more", "pgrep", "ps", "grep", "egrep", "rg", "ag", "find", "fd", "wc", "du", "df", "nvidia-smi", "gpustat", "top", "htop",
           "tree", "stat", "file", "which", "whereis", "echo", "printf", "pwd", "squeue", "sacct", "sinfo", "jobs", "watch", "date", "hostname", "whoami", "env", "printenv", "free",
           "uptime", "id", "diff", "md5sum", "sha256sum", "jq", "column", "sort", "uniq", "cut", "awk", "sed", "nproc", "lscpu", "type", "test", "true", "sleep", "wait", "realpath", "basename", "dirname", "readlink", "lsof", "ss", "netstat"}
SETUP = {"pip", "pip3", "conda", "mamba", "apt", "apt-get", "brew", "npm", "pnpm", "yarn", "mkdir", "module", "tmux", "screen", "chmod", "chown", "ln", "touch", "rm", "rmdir", "kill", "pkill", "killall",
         "scp", "rsync", "wget", "curl", "cp", "mv", "tar", "unzip", "zip", "gzip", "gunzip", "gdown", "huggingface-cli", "aws", "gsutil", "docker", "ssh"}
WRITING = {"latexmk", "pdflatex", "xelatex", "lualatex", "bibtex", "biber", "tectonic", "pandoc"}
RUNNERS = {"python", "python3", "bash", "sh", "zsh", "accelerate", "torchrun", "sbatch", "srun", "Rscript", "julia", "node", "make", "jupyter", "papermill", "pytest", "mpirun", "ipython"}
WRAPPERS = {"sudo", "nohup", "time", "exec", "stdbuf", "nice", "ionice", "command", "xvfb-run", "setsid", "caffeinate", "unbuffer"}
GIT_LOOK = {"status", "log", "diff", "show", "branch", "remote", "rev-parse", "ls-files", "blame", "describe", "worktree", "config", "tag", "reflog", "shortlog", "ls-tree", "cat-file", "grep"}
SCRATCH = re.compile(r"(^|/)(tmp/claude-[^/]*|\.claude(/|$)|scratchpad(/|$))")
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
KEYS = ("dataset", "data", "method", "model", "variant", "seed", "task", "exp", "experiment", "config", "family")


def parse_time(t):
    try:
        d = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _tokens(seg):
    try:
        return shlex.split(seg, posix=True)
    except ValueError:
        return seg.split()


def read_command(cmd):
    """One shell command line -> {type, script, args, env, cd, inline}. A rule-based reading: no shell is run."""
    cmd = str(cmd or "").strip()
    out = {"type": "other", "script": None, "args": {}, "env": {}, "cd": None, "inline": False}
    head = cmd.split("\n", 1)[0]
    heredoc = "<<" in head
    segs = [x.strip() for x in re.split(r"\s*(?:&&|\|\||;)\s*", head.split("<<", 1)[0] if heredoc else head) if x.strip()]
    chosen = None
    for seg in segs:                     # the first part that does something: skip cd, export, source, set
        tk = _tokens(seg.split("|", 1)[0])
        while tk and (ASSIGN.match(tk[0]) or tk[0] in WRAPPERS):
            if ASSIGN.match(tk[0]):
                k, _, v = tk[0].partition("=")
                out["env"][k] = v
            tk = tk[1:]
        if not tk:
            continue
        if tk[0] == "cd" and len(tk) > 1:
            out["cd"] = tk[1]
            continue
        if tk[0] == "export":
            for a in tk[1:]:
                if ASSIGN.match(a):
                    k, _, v = a.partition("=")
                    out["env"][k] = v
            continue
        if tk[0] in ("source", ".", "set", "unset", "ulimit", "umask", "alias", "conda") and (tk[0] != "conda" or (len(tk) > 1 and tk[1] in ("activate", "deactivate"))):
            continue
        if tk[0] == "timeout" and len(tk) > 2:
            tk = tk[2:]
        if tk[0] == "uv" and len(tk) > 2 and tk[1] == "run":
            tk = tk[2:]
            while tk and tk[0].startswith("-"):
                tk = tk[2:] if tk[0] in ("--with", "--project", "--python", "-p") else tk[1:]
        if tk:
            chosen = tk
            break
    if not chosen:
        out["type"] = "setup" if (out["cd"] or out["env"]) else "other"
        return out
    prog = os.path.basename(chosen[0])
    rest = chosen[1:]
    if prog == "git":
        sub = next((a for a in rest if not a.startswith("-")), "")
        out["type"] = "inspection" if sub in GIT_LOOK else "git"
        return out
    if re.match(r"^python[0-9.]*$", prog):
        prog = "python"
    if prog in ("python", "ipython") and (heredoc or (rest and rest[0] in ("-", "-c"))):
        out["type"], out["inline"] = "analysis", True
        return out
    if prog in INSPECT:
        out["type"] = "inspection"
        return out
    if prog in WRITING:
        out["type"] = "writing"
        return out
    if prog in SETUP or (prog == "uv" and rest and rest[0] in ("sync", "add", "pip", "venv", "lock", "remove")):
        out["type"] = "setup"
        return out
    script, args = None, rest
    if prog in RUNNERS:
        i = 0
        while i < len(rest):
            a = rest[i]
            if a == "-m" and i + 1 < len(rest):
                script, args = rest[i + 1], rest[i + 2:]
                break
            if a == "launch" and prog == "accelerate":
                i += 1
                continue
            if not a.startswith("-"):
                script, args = a, rest[i + 1:]
                break
            i += 1
    elif re.search(r"\.(py|sh|R|jl|ipynb)$", chosen[0]) or chosen[0].startswith("./"):
        script = chosen[0]
    if script is None and prog not in RUNNERS:
        return out
    out["type"], out["script"] = "script", script or prog
    i = 0
    while i < len(args):                 # --key value, --key=value, key=value (hydra)
        a = args[i]
        if a.startswith("--") and "=" in a:
            k, _, v = a[2:].partition("=")
            out["args"][k] = v
        elif a.startswith("-") and len(a) > 1 and not a[1:].replace(".", "").isdigit():
            k = a.lstrip("-")
            if i + 1 < len(args) and not (args[i + 1].startswith("-") and not args[i + 1][1:].replace(".", "").isdigit()):
                out["args"][k] = args[i + 1]
                i += 1
            else:
                out["args"][k] = True
        elif ASSIGN.match(a) or re.match(r"^[\w.]+=", a):
            k, _, v = a.partition("=")
            out["args"][k] = v
        i += 1
    return out


def matcher(pattern):
    """A result-file pattern from the project map ('results/main/{dataset}_{method}_seed{seed}.csv', 'results/abl_*.csv')
    -> (regex over a path's tail, the folder that is fixed in the pattern)."""
    rx, i = "", 0
    for m in re.finditer(r"\{(\w+)\}|\*\*/?|\*", pattern):
        rx += re.escape(pattern[i:m.start()])
        rx += ("(?P<%s>[^/]+?)" % m.group(1)) if m.group(1) else ".*" if m.group(0).startswith("**") else "[^/]*"
        i = m.end()
    rx += re.escape(pattern[i:])
    fixed = re.split(r"[{*]", pattern, maxsplit=1)[0]
    fixed = fixed.rsplit("/", 1)[0] if "/" in fixed else ""
    try:
        return re.compile(r"(?:^|/)" + rx + "$"), fixed
    except re.error:                    # the same field twice in one pattern
        return re.compile(r"(?:^|/)" + re.sub(r"\(\?P<\w+>", "(?:", rx) + "$"), fixed


def experiments_of(run, exps):
    """Which experiments a logged run belongs to: it wrote a file matching the experiment's result pattern (certain), or its
    command names the experiment's result folder (likely). -> [(experiment, fields, how)]"""
    out = []
    arts = [a.get("path") or "" for a in run.get("artifacts") or []]
    text = "%s %s" % (run.get("command") or "", run.get("cwd") or "")
    for x in exps:
        fields, how = {}, None
        for rx, fixed in x.get("_match") or []:
            for p in arts:
                m = rx.search(p)
                if m:
                    how = "wrote"
                    for k, v in m.groupdict().items():
                        if v and v not in fields.setdefault(k, []):
                            fields[k].append(v)
            if how is None and fixed and "/" in fixed and (fixed + "/") in text + "/":
                how = "names"
        if how:
            out.append((x, fields, how))
    return out


def who_of(run):
    if run.get("source") == "agent" or SCRATCH.search(run.get("cwd") or "") or SCRATCH.search(run.get("command") or ""):
        return "agent"
    return "watcher" if run.get("source") == "watcher" else "you"


def place_of(run, repos, read):
    """-> (key, label, scratch). The key groups a session; a folder named after a repository (a git worktree or second clone,
    e.g. mcd_extension_rq2 next to mcd_extension) counts as that repository."""
    cwd = (run.get("cwd") or "").rstrip("/")
    if read.get("cd") and not os.path.isabs(read["cd"]):
        cwd = os.path.normpath(os.path.join(cwd or "/", read["cd"])) if cwd else read["cd"]
    elif read.get("cd"):
        cwd = read["cd"].rstrip("/")
    if not cwd or SCRATCH.search(cwd):
        return None, "the agent's scratch folder" if cwd else None, True
    for r in repos:
        root = (r.get("abs_path") or "").rstrip("/")
        if root and (cwd == root or cwd.startswith(root + "/")):
            rel = cwd[len(root):].strip("/")
            return r["id"], os.path.basename(root) + ("/" + rel if rel else ""), False
    parts = [p for p in cwd.split("/") if p]
    for r in repos:
        base = os.path.basename((r.get("abs_path") or "").rstrip("/"))
        for i, p in enumerate(parts):
            if base and p != base and re.match(r"^%s[-_.]" % re.escape(base), p):
                return r["id"], "/".join(parts[i:]) + " (a second copy of %s)" % base, False
    return "dir:" + cwd, "/".join(parts[-2:]) if parts else cwd, False


def _plural(n, word, s="s"):
    return "%d %s%s" % (n, word, "" if n == 1 else s)


def _dur(a, b):
    m = int(round(max(0, (b - a).total_seconds()) / 60))
    return m


def load_notes(hub):
    d = hub.read_json("sessions.json", None)
    if not isinstance(d, dict) or not isinstance(d.get("notes"), dict):
        d = {"schema": SCHEMA, "notes": {}}
    return d


def set_note(store, known, sid, text=None, action=None, by="you", now=None):
    """The one-line summary of a session. An agent may only propose; the researcher confirms, edits or removes."""
    if sid not in known:
        raise NotFound("unknown session %r" % sid)
    cur = store["notes"].get(sid)
    if action == "remove":
        if not cur:
            raise NotFound("this session has no summary")
        del store["notes"][sid]
        return store
    if action == "confirm":
        if not cur:
            raise NotFound("this session has no summary to confirm")
        if by != "you":
            raise BadRequest("only the researcher confirms a summary")
        cur.update(state="confirmed", confirmed_at=now)
        return store
    if not isinstance(text, str) or not text.strip() or len(text) > 300:
        raise BadRequest("summary must be 1 to 300 characters: one sentence saying what the session was for")
    text = " ".join(text.split())
    if by != "you":
        if cur and cur.get("state") == "confirmed":
            raise BadRequest("the researcher already confirmed a summary for this session; it is not replaced by a draft")
        store["notes"][sid] = {"text": text, "by": "agent", "state": "proposed", "at": now}
    else:
        store["notes"][sid] = {"text": text, "by": "you", "state": "confirmed", "at": now, "confirmed_at": now}
    return store


def build(entries, exps, repos, notes=None, gap=GAP):
    """entries: the Trail's entries (runs carry '_run'; commits carry repo, author, detail). -> sessions, newest first."""
    notes = (notes or {}).get("notes") or {}
    recs = []
    for e in entries:
        t = parse_time(e["t"])
        if t is None:
            continue
        r = {"e": e, "t": t, "end": t, "key": None, "scratch": False, "ts": e["t"]}
        run = e.get("_run")
        if run:
            r["read"] = read_command(run.get("command"))
            r["who"] = who_of(run)
            r["key"], r["place"], r["scratch"] = place_of(run, repos, r["read"])
            st = parse_time(run.get("started"))
            if st and st <= t and st.astimezone(t.tzinfo).date() == t.date():
                r["t"], r["ts"] = st, st.astimezone(t.tzinfo).isoformat()
            r["x"] = experiments_of(run, exps)
            tp = r["read"]["type"]
            if run.get("source") == "watcher" and not run.get("command"):
                tp = "run"
            elif tp == "script" and (r["x"] and any(h == "wrote" for _, _, h in r["x"]) or run.get("metrics")):
                tp = "run"
            elif tp in ("analysis", "other", "inspection") and any(h == "wrote" for _, _, h in r["x"]):
                tp = "run"
            r["type"] = tp
            if tp not in ("run", "script"):      # an analysis that only names the result folder read it; looking at it is not part of the experiment
                r["x"] = [(x, f, h if h == "wrote" else "reads") for x, f, h in r["x"]] if tp == "analysis" else [m for m in r["x"] if m[2] == "wrote"]
        elif e["kind"] in ("paper", "code"):
            r["key"] = e.get("repo")
        recs.append(r)
    recs.sort(key=lambda r: r["t"])

    open_, sessions = {}, []          # key -> the session still open for that place
    last = None
    for r in recs:
        day = r["e"]["day"]
        s = None
        if r["key"] is not None:
            c = open_.get(r["key"])
            if c and c["day"] == day and (r["t"] - c["end"]).total_seconds() <= gap:
                s = c
            elif last and last["day"] == day and last["key"] is None and (r["t"] - last["end"]).total_seconds() <= gap:
                s = last                 # a session that so far had no place takes this one
                s["key"] = r["key"]
        elif last and last["day"] == day and (r["t"] - last["end"]).total_seconds() <= gap:
            s = last
        if s is None:
            s = {"day": day, "key": r["key"], "recs": [], "start": r["t"], "end": r["t"], "end_s": r["e"]["t"]}
            sessions.append(s)
        s["recs"].append(r)
        if r["end"] >= s["end"]:
            s["end"], s["end_s"] = r["end"], r["e"]["t"]
        open_[s["key"]] = s
        last = s

    out = []
    for s in sessions:
        runs = [r for r in s["recs"] if r["e"].get("_run")]
        commits = [r for r in s["recs"] if r["e"]["kind"] in ("paper", "code")]
        others = [r for r in s["recs"] if not r["e"].get("_run") and r["e"]["kind"] not in ("paper", "code")]
        first = s["recs"][0]["e"]
        ref = (first.get("_run") or {}).get("run_id") or first.get("ref") or first["t"] + first["title"]
        sid = "s" + hashlib.sha1(("%s|%s" % (s["day"], ref)).encode("utf-8")).hexdigest()[:10]

        # who
        who = {}
        for r in runs:
            who[r["who"]] = who.get(r["who"], 0) + 1
        authors = []
        for r in commits:
            a = r["e"].get("author")
            lab = (a or "a commit") + (", with " + ", ".join(r["e"].get("coauthors")[:2]) if r["e"].get("coauthors") else "")
            if lab not in authors:
                authors.append(lab)
        who_out = [{"who": k, "n": who[k]} for k in ("you", "agent", "watcher") if who.get(k)]

        # where
        hosts, places, shas, dirty = [], {}, [], False
        for r in runs:
            run = r["e"]["_run"]
            if run.get("host") and run["host"] not in hosts:
                hosts.append(run["host"])
            if r.get("place") and not r["scratch"]:
                places[r["place"]] = places.get(r["place"], 0) + 1
            if run.get("git_sha") and run["git_sha"][:7] not in shas:
                shas.append(run["git_sha"][:7])
            dirty = dirty or bool(run.get("dirty"))
        for r in commits:
            lab = r["e"].get("repo")
            if lab and not any(p.split("/")[0] == lab for p in places) and not runs:
                places[lab] = places.get(lab, 0) + 1

        # what was run, by type; the experiments it belongs to; how
        counts = dict.fromkeys(TYPES, 0)
        scripts, env, args, configs, xs, files, metrics, failed = {}, {}, {}, [], {}, {}, {}, 0
        for r in runs:
            run, rd, tp = r["e"]["_run"], r["read"], r["type"]
            counts[tp] += 1
            bad = run.get("exit_code") not in (None, 0)
            if bad and tp != "inspection":
                failed += 1
            if rd.get("script") and tp in ("run", "script"):
                sc = scripts.setdefault(rd["script"], {"name": rd["script"], "n": 0, "failed": 0})
                sc["n"] += 1
                sc["failed"] += 1 if bad else 0
            if tp in ("run", "script"):
                for k, v in rd["env"].items():
                    env.setdefault(k, v)
                for k, v in rd["args"].items():
                    vs = args.setdefault(k, [])
                    if v is not True and str(v) not in vs:
                        vs.append(str(v))
                    if isinstance(v, str) and re.search(r"\.(ya?ml|json|toml|cfg|ini)$", v) and v not in configs:
                        configs.append(v)
            for c in run.get("configs") or []:
                if c.get("path") and c["path"] not in configs:
                    configs.append(c["path"])
            for x, fields, how in r["x"]:
                rec = xs.setdefault(x["id"], {"id": x["id"], "name": x["name"], "claims": x.get("_claims") or [], "how": how, "fields": {}, "runs": 0})
                rec["runs"] += 1
                rank = ("wrote", "names", "reads")
                rec["how"] = min(rec["how"], how, key=rank.index)
                for k, v in fields.items():
                    for one in v:
                        if one not in rec["fields"].setdefault(k, []):
                            rec["fields"][k].append(one)
            tracked = any(h == "wrote" for _, _, h in r["x"])
            for a in run.get("artifacts") or []:
                d = os.path.dirname(a.get("path") or "") or "."
                f = files.setdefault(d, {"dir": d, "n": 0, "tracked": False, "names": []})
                f["n"] += 1
                f["tracked"] = f["tracked"] or tracked
                if len(f["names"]) < 4:
                    f["names"].append(os.path.basename(a.get("path") or ""))
            for k, v in (run.get("metrics") or {}).items():
                metrics[k] = v
        moved = []
        for r in commits:
            for m in (r["e"].get("detail") or {}).get("results") or []:
                moved.append(m)
                xs.setdefault(m["x"], {"id": m["x"], "name": m["name"], "claims": m.get("claims") or [], "how": "commit", "fields": {}, "runs": 0})
        claims = []
        for x in xs.values():
            for c in x["claims"]:
                if c not in claims:
                    claims.append(c)
        hidden = counts["inspection"]

        # what: plain lines, and a rule-made title
        what = []
        for sc in sorted(scripts.values(), key=lambda v: -v["n"])[:4]:
            what.append("%s of %s%s" % (_plural(sc["n"], "run"), sc["name"], (", %d failed" % sc["failed"]) if sc["failed"] else ""))
        if counts["analysis"]:
            what.append("%s (Python typed straight into the shell, not a saved script)" % _plural(counts["analysis"], "inline analysis", ""))
        if counts["writing"]:
            what.append(_plural(counts["writing"], "paper build"))
        if counts["setup"]:
            what.append("%s (installing, copying or moving files)" % _plural(counts["setup"], "set-up command"))
        if counts["git"]:
            what.append(_plural(counts["git"], "git command"))
        if counts["other"]:
            what.append(_plural(counts["other"], "other command"))
        n_files = sum(f["n"] for f in files.values())
        if n_files:
            top = sorted(files.values(), key=lambda f: -f["n"])
            what.append("wrote %s to %s%s" % (_plural(n_files, "file"), top[0]["dir"] + "/", " and %d more folder%s" % (len(top) - 1, "" if len(top) == 2 else "s") if len(top) > 1 else ""))
        for r in commits[:4]:
            what.append("commit %s: %s" % (r["e"].get("ref") or "", r["e"]["title"]))
        if len(commits) > 4:
            what.append("and %d more commits" % (len(commits) - 4))
        for r in others[:5]:
            what.append(r["e"]["title"] + (" (%s)" % r["e"]["why"].rstrip(".") if r["e"].get("why") else ""))
        if hidden:
            what.append("%s (looking at files or processes; hidden below)" % _plural(hidden, "inspection command"))

        named = sorted(xs.values(), key=lambda x: (("wrote", "names", "commit", "reads").index(x["how"]), -x["runs"]))
        if named and any(x["how"] != "commit" for x in named):
            title = {"wrote": "Ran ", "names": "Ran ", "reads": "Analysed the results of ", "commit": "Updated "}[named[0]["how"]] + named[0]["name"] + (" and %d more" % (len(named) - 1) if len(named) > 1 else "")
        elif commits:
            title = commits[-1]["e"]["title"] + (" and %d more commit%s" % (len(commits) - 1, "" if len(commits) == 2 else "s") if len(commits) > 1 else "")
        elif scripts:
            top = sorted(scripts.values(), key=lambda v: -v["n"])
            title = "Ran %s%s" % (os.path.basename(top[0]["name"]), " and %d more script%s" % (len(top) - 1, "" if len(top) == 2 else "s") if len(top) > 1 else "")
        elif counts["analysis"]:
            title = "Analysis: %s" % _plural(counts["analysis"], "inline Python script")
        elif counts["writing"]:
            title = "Built the paper"
        elif others:
            title = others[-1]["e"]["title"] + (" and %d more" % (len(others) - 1) if len(others) > 1 else "")
        elif counts["setup"] or counts["git"] or counts["other"]:
            title = "Set-up and housekeeping: %s" % _plural(counts["setup"] + counts["git"] + counts["other"], "command")
        else:
            title = "Looked around: %s" % _plural(hidden, "inspection command")

        # why
        if claims:
            why = {"claims": claims, "text": "Tests %s." % ", ".join(claims), "known": True}
        elif xs:
            why = {"claims": [], "text": "%s tests no claim yet." % named[0]["name"], "known": False}
        elif commits:
            why = {"claims": [], "text": "From the commit message: %s" % commits[-1]["e"]["title"], "known": True}
        else:
            why = {"claims": [], "text": "Lemmata cannot tell: nothing here wrote a result file of a mapped experiment.", "known": False}

        # result
        notes_out = []
        if failed:
            notes_out.append("%s failed (a non-zero exit code)." % _plural(failed, "command"))
        tracked_n = sum(f["n"] for f in files.values() if f["tracked"])
        if tracked_n:
            notes_out.append("%s belong%s to a mapped experiment." % (_plural(tracked_n, "result file"), "s" if tracked_n == 1 else ""))
        if runs and not n_files and not metrics and not commits:
            notes_out.append("No result file and no number was recorded.")
        if dirty:
            notes_out.append("Run with uncommitted changes, so the commit alone does not reproduce it.")
        for r in others:
            if r["e"]["kind"] == "claims":
                notes_out.append(r["e"]["title"] + ".")

        cmds = []
        for r in runs:
            run = r["e"]["_run"]
            cmds.append({"t": r["e"]["t"], "type": r["type"], "who": r["who"], "command": (run.get("command") or "(files seen by the results watcher)")[:600], "exit": run.get("exit_code"),
                         "id": run.get("run_id"), "hidden": r["type"] == "inspection"})
        ents = []
        for r in commits + others:
            e = dict(r["e"])
            e.pop("_run", None)
            ents.append(e)
        ents.sort(key=lambda e: e["t"])
        note = notes.get(sid)
        kinds = sorted({r["e"]["kind"] for r in s["recs"]})
        out.append({
            "id": sid, "day": s["day"], "start": s["recs"][0]["ts"], "end": s["end_s"],
            "minutes": _dur(s["start"], s["end"]), "kinds": kinds, "n": len(s["recs"]),
            "title": note["text"] if note else title, "rule_title": title, "note": dict(note) if note else None,
            "who": who_out, "authors": authors,
            "where": {"hosts": hosts, "places": [{"name": k, "n": v} for k, v in sorted(places.items(), key=lambda kv: -kv[1])][:4], "shas": shas[:3], "dirty": dirty,
                      "scratch": sum(1 for r in runs if r["scratch"])},
            "what": what, "counts": {k: v for k, v in counts.items() if v}, "commits": len(commits),
            "why": why, "experiments": [{"id": x["id"], "name": x["name"], "claims": x["claims"], "how": x["how"], "fields": {k: v[:8] for k, v in x["fields"].items()}} for x in named[:6]],
            "how": {"scripts": sorted(scripts.values(), key=lambda v: -v["n"])[:6], "configs": configs[:6], "env": [{"key": k, "value": v[:120]} for k, v in list(env.items())[:6]],
                    "args": [{"key": k, "values": v[:8]} for k, v in sorted(args.items(), key=lambda kv: (kv[0].split(".")[-1] not in KEYS, kv[0])) if v][:8]},
            "result": {"moved": moved[:8], "files": sorted(files.values(), key=lambda f: (not f["tracked"], -f["n"]))[:5], "files_n": n_files,
                       "metrics": [{"key": k, "value": v} for k, v in list(metrics.items())[:8]], "failed": failed, "notes": notes_out},
            "commands": cmds[-60:], "commands_n": len(cmds), "hidden_n": hidden, "entries": ents,
        })
    out.sort(key=lambda s: s["start"], reverse=True)
    return out


def brief(s):
    """A session as plain text: what an agent reads before it drafts the one-line summary."""
    lines = ["%s · %s %s–%s (%d min) · %s" % (s["id"], s["day"], s["start"][11:16], s["end"][11:16], s["minutes"], "summary: " + s["note"]["state"] if s.get("note") else "no summary yet")]
    lines.append("  title by rule: " + s["rule_title"])
    if s["who"] or s["authors"]:
        lines.append("  who: " + ", ".join(["%s ×%d" % (w["who"], w["n"]) for w in s["who"]] + ["commit by " + a for a in s["authors"]]))
    w = s["where"]
    if w["hosts"] or w["places"]:
        lines.append("  where: " + ", ".join(w["hosts"]) + (" in " + ", ".join(p["name"] for p in w["places"]) if w["places"] else ""))
    lines += ["  what: " + x for x in s["what"]]
    lines.append("  why: " + s["why"]["text"])
    for c in s["commands"][-12:]:
        if not c["hidden"]:
            lines.append("  $ " + c["command"][:300].replace("\n", " ⏎ "))
    return "\n".join(lines)
