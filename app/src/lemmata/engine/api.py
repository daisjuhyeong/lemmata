"""Engine facade: the only module server.py and cli.py import (data-model 13)."""
import copy
import time
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from . import alarms as alarmsmod
from . import analyze as analyzemod
from . import checks as checksmod
from . import claims as claimsmod
from . import experiments as expmod
from . import notation as notationmod
from . import numbers as numbersmod
from . import baselines as baselinesmod
from . import bench as benchmod
from . import texout as latexmod
from . import process as processmod
from . import graph as graphmod
from . import history as historymod
from . import manifest as manifestmod
from . import refs as refsmod
from . import store
from . import track as trackmod
from . import tree as treemod
from . import review as reviewmod
from . import plans as plansmod
from . import runs as runsmod
from . import sessions as sessionsmod
from . import setup as setupmod
from . import since as sincemod
from . import study as studymod
from . import survey as surveymod
from . import board as boardmod
from . import todo as todomod
from . import trail as trailmod
from . import venues as venuesmod
from . import triage as triagemod
from . import understand as undmod
from . import hypo as hypomod
from .errors import BadRequest, NotFound

VERSION = "0.1.0"


def now_iso():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


class Engine:
    def __init__(self, project_root, online=False):
        self.root = Path(project_root).expanduser().resolve()
        self.online = bool(online)
        self.hub = store.Hub(self.root)
        self._s = None

    # ------------------------------------------------------------------ scan
    def scan(self):
        t0 = time.time()
        self.hub.ensure()
        man = manifestmod.load_or_create(self.root, self.hub)
        store.check_schema(man, "lemmata.project")
        repos = manifestmod.resolve(self.root, man)
        trees, infos, hist = {}, {}, {}
        for r in repos:
            t = treemod.WorkTree(r["abs_path"], r["id"], r.get("git_subdir"))
            trees[r["id"]] = t
            info = {"id": r["id"], "role": r["role"], "path": r["path"], "abs_path": r["abs_path"],
                    "vcs": "git" if t.is_git else "none", "head": None, "branch": None, "dirty": False, "status": []}
            if t.is_git:
                info["head"], info["branch"] = treemod.head_info(r["abs_path"])
                info["status"] = treemod.status_entries(r["abs_path"])
                info["dirty"] = bool(info["status"])
                hist[r["id"]] = historymod.read_commits(r["abs_path"]) if info["head"] else []
            else:
                hist[r["id"]] = []
            infos[r["id"]] = info
        cache = refsmod.load(self.hub)
        tri = triagemod.load(self.hub)
        scanned_at = now_iso()
        G = graphmod.build(repos, trees, cache, tri["links"])
        if self.online and G.bib_entries:
            if refsmod.online_fill(G.bib_entries, cache, scanned_at):  # opt-in network access
                self.hub.write_json("cache/refs.json", cache)
                for e in G.bib_entries:
                    G.nodes["ref:" + e["key"]]["attrs"]["lookup"] = refsmod.lookup_state(cache, e)
        findings, fwarn = checksmod.run(G, trees)
        cps = self.hub.read_json("checkpoints.json", None)
        warnings = list(G.warnings) + (list(G.paper.warnings) if G.paper else [])
        warnings += [{"code": "finding_dropped", "message": m, "evidence": None} for m in fwarn]
        if cps is None and man.get("seed_checkpoint"):
            seed = man["seed_checkpoint"]
            try:
                cp = historymod.make_checkpoint(repos, infos, trees, G, cache, self.hub, seed.get("id", "cp1"), seed.get("note", ""),
                                                seed.get("created_at") or scanned_at, seed.get("at"), [])
                cps = {"schema": "lemmata.checkpoints/1", "active": cp["id"], "checkpoints": [cp]}
                self.hub.write_json("checkpoints.json", cps)
            except BadRequest as e:
                warnings.append({"code": "seed_checkpoint_failed", "message": str(e), "evidence": None})
        self._s = {"man": man, "repos": repos, "trees": trees, "infos": infos, "hist": hist, "cache": cache, "G": G,
                   "findings": findings, "cps": cps, "tri": tri, "warnings": warnings, "scanned_at": scanned_at,
                   "scan_seconds": None, "events": None, "alarms": None, "replay": None}
        self._recompute(scanned_at)
        self.hub.write_json("graph.json", self._graph_doc())
        self.hub.write_json("findings.json", findings)
        self._s["scan_seconds"] = round(time.time() - t0, 3)
        return self.project()

    def _active_cp(self):
        cps = self._s["cps"]
        if not cps:
            return None
        return next((c for c in cps["checkpoints"] if c["id"] == cps["active"]), None)

    def _recompute(self, now):
        s = self._s
        cp = self._active_cp()
        events, replay = historymod.build_events(s["repos"], s["infos"], s["hist"], cp, s["G"], now, s["cache"])
        s["events"], s["replay"] = events, replay
        s["alarms"] = alarmsmod.compute(cp, s["G"].nodes, s["G"].edge_list(), events, replay, now)
        self.hub.write_json("events.json", {"schema": "lemmata.events/1", "events": events})
        self.hub.write_json("alarms.json", s["alarms"])

    def _graph_doc(self):
        s = self._s
        return {"schema": "lemmata.graph/1", "scanned_at": s["scanned_at"], "nodes": s["G"].node_list(), "edges": s["G"].edge_list(),
                "warnings": s["warnings"]}

    def _ensure(self):
        if self._s is None:
            self.scan()
        return self._s

    # ------------------------------------------------------------------ reads
    def project(self):
        s = self._ensure()
        cp = self._active_cp()
        edges = s["G"].edges.values()
        return {
            "schema": "lemmata.project/1", "version": VERSION, "name": s["man"].get("name", self.root.name), "root": str(self.root),
            "repos": [{"id": i["id"], "role": i["role"], "path": i["path"], "abs_path": i["abs_path"], "vcs": i["vcs"],
                       "head": i["head"], "branch": i["branch"], "dirty": i["dirty"]} for i in (s["infos"][r["id"]] for r in s["repos"])],
            "scanned_at": s["scanned_at"],
            "counts": {"nodes": len(s["G"].nodes), "edges": len(s["G"].edges), "proposed": sum(1 for e in edges if e["status"] == "proposed"),
                       "events": len(s["events"]), "findings": len(s["findings"]["findings"]), "alarm_groups": len(s["alarms"]["groups"])},
            "checkpoint": {"id": cp["id"], "created_at": cp["created_at"], "note": cp["note"]} if cp else None,
            "capabilities": {"paper": s["G"].paper is not None, "online_lookup": self.online, "ask_ai": False, "research": True},
            "study": self._study_brief(), "sync": self.sync_state(),
            "warnings": s["warnings"],
        }

    def graph(self):
        self._ensure()
        return self._graph_doc()

    def events(self, after_checkpoint=False):
        s = self._ensure()
        evs = [e for e in s["events"] if e["after_checkpoint"]] if after_checkpoint else s["events"]
        return {"schema": "lemmata.events/1", "events": evs}

    def findings(self):
        return self._ensure()["findings"]

    def alarms(self):
        return self._ensure()["alarms"]

    def analyze(self, group_id, node_id):
        s = self._ensure()
        cp = self._active_cp()
        if cp is None:
            raise NotFound("no checkpoint")
        return analyzemod.analyze(group_id, node_id, s["alarms"], cp, s["G"].nodes, s["G"].edge_list(), s["trees"], self.hub, s["infos"])

    def checkpoints(self):
        s = self._ensure()
        cps = s["cps"]
        if not cps:
            return {"active": None, "checkpoints": []}
        return {"active": cps["active"], "checkpoints": [self._cp_summary(c) for c in reversed(cps["checkpoints"])]}

    def _cp_summary(self, c):
        out = {k: v for k, v in c.items() if k != "nodes"}
        out["node_count"] = len(c["nodes"])
        out["active"] = bool(self._s["cps"] and self._s["cps"]["active"] == c["id"])
        return out

    # ------------------------------------------------------------------ mutations
    def create_checkpoint(self, note="", at=None, created_at=None, cp_id=None, actor=None):
        if note is None:
            note = ""
        if not isinstance(note, str) or len(note) > 500:
            raise BadRequest("note must be a string of at most 500 characters")
        if at is not None and not isinstance(at, dict):
            raise BadRequest("'at' must be an object {repo: rev}")
        self.scan()   # a checkpoint snapshots the current working tree
        s = self._s
        existing = s["cps"]["checkpoints"] if s["cps"] else []
        if cp_id and any(c["id"] == cp_id for c in existing):
            raise BadRequest("checkpoint %s already exists" % cp_id)
        now = now_iso()
        cp = historymod.make_checkpoint(s["repos"], s["infos"], s["trees"], s["G"], s["cache"], self.hub, cp_id, note,
                                        created_at or now, at, existing)
        if actor:      # who made it, only when the request knows (a browser session); otherwise nothing is recorded
            cp["by"] = actor
        cps = {"schema": "lemmata.checkpoints/1", "active": cp["id"], "checkpoints": existing + [cp]}
        s["cps"] = cps
        self.hub.write_json("checkpoints.json", cps)
        self._recompute(now)
        return {"checkpoint": self._cp_summary(cp), "alarms": s["alarms"]}

    def triage(self):
        s = self._ensure()
        out = {"schema": "lemmata.triage/1", "entries": {}, "links": s["tri"]["links"]}
        for key, ent in s["tri"]["entries"].items():
            out["entries"][key] = triagemod.with_effective(ent, self._target_hash(ent["target_type"], ent["target_id"]))
        return out

    def _target_hash(self, target_type, target_id):
        s = self._s
        if target_type == "node":
            n = s["G"].nodes.get(target_id)
            return n["hash"] if n else None
        f = next((f for f in s["findings"]["findings"] if f["id"] == target_id), None)
        return f["fingerprint"] if f else None

    def set_triage(self, target_type, target_id, state, note="", by=None):
        s = self._ensure()
        if target_type not in ("node", "finding"):
            raise BadRequest("target_type must be 'node' or 'finding'")
        h = self._target_hash(target_type, target_id)
        if h is None:
            raise NotFound("unknown %s %r" % (target_type, target_id))
        ent = triagemod.set_entry(s["tri"], target_type, target_id, state, note, h, now_iso(), by)
        self.hub.write_json("triage.json", s["tri"])
        return {"entry": triagemod.with_effective(ent, h)}

    def decide_link(self, edge_id, decision):
        s = self._ensure()
        e = s["G"].edges.get(edge_id)
        if e is None:
            raise NotFound("unknown edge %r" % edge_id)
        if e["kind"] != "value_match":
            raise BadRequest("only proposed links can be decided")
        triagemod.set_decision(s["tri"], edge_id, decision, now_iso())
        e["status"] = decision
        e["propagates"] = e["kind"] in graphmod.PROPAGATING and e["status"] in ("detected", "approved")
        self.hub.write_json("triage.json", s["tri"])
        self.hub.write_json("graph.json", self._graph_doc())
        s["alarms"] = alarmsmod.compute(self._active_cp(), s["G"].nodes, s["G"].edge_list(), s["events"], s["replay"], now_iso())
        self.hub.write_json("alarms.json", s["alarms"])
        return {"edge": copy.deepcopy(e), "alarms": s["alarms"]}

    # ------------------------------------------------------------------ claims
    def claims(self):
        """The claims, each with its stage (hypothesis -> being tested -> finding / not supported), the experiments run
        because of it, and how its stage changed over time."""
        doc = self._claims_base()
        tests, meta, ext = {}, {}, False
        crit = self._criteria()
        if undmod.load(self.hub)["confirmed"]:
            E = self._exp_doc()
            ext = bool(E.get("extends"))
            vs = E["extends"]["base"]["name"] if ext else "the best other method"
            for sec in E["sections"]:
                if sec.get("claim_id"):
                    meta[sec["claim_id"]] = {"scope": {"extension": "new", "base": "original"}.get(sec.get("scope")), "ref": sec["label"]}
                    own = ext and sec.get("scope") != "base"      # re-checking the original paper's claim: its method against the others, as the paper did
                    tests[sec["claim_id"]] = [self._judged(self._outcome(x, own, vs if own else "the best other method"), x, sec, own, vs if own else "the best other method", crit)
                                              for x in sec["experiments"]]
        claimsmod.restage(doc, claimsmod.load(self.hub), tests, meta)
        self._hf_stages(doc)
        if self.study()["kind"] in ("benchmark", "survey"):      # no "ours" to be ahead or behind: say what would decide the claim instead (rule C10)
            for c in doc["claims"]:
                if not c.get("hypothesis") and c.get("stage_rule") == "C5":
                    c["stage_why"] = "%s. A benchmark claim is decided by its own test, and none is set for it yet." % c["stage_why"].replace(", none with a comparison yet.", " with results")
                    c["stage_rule"] = c["stage_rule_auto"] = "C10"
        # stages over time: what the stored results show for the past, then what Lemmata has recorded since it started watching
        log = self.hub.read_json("stages.json", None)
        if not isinstance(log, dict) or not isinstance(log.get("log"), dict):
            log = {"schema": "lemmata.stages/1", "log": {}}
        now, changed = now_iso(), False
        for c in ([doc["core"]] if doc["core"] else []) + [c for c in doc["claims"] if c["state"] != "rejected"]:
            rec = log["log"].setdefault(c["id"], [])
            if not rec or rec[-1]["stage"] != c["stage"]:
                rec.append({"t": now, "stage": c["stage"], "by": c["stage_by"]})
                del rec[:-200]
                changed = True
            t0 = processmod._t(rec[0]["t"])
            try:
                past = [p for p in claimsmod.replay(c.get("experiments") or []) if processmod._t(p["t"]) < t0]
            except TypeError:      # a time that cannot be read or compared: show only what was recorded
                past = []
            c["stages"] = [p for i, p in enumerate(past + rec) if i == 0 or (past + rec)[i - 1]["stage"] != p["stage"]][-40:]
        for c in doc["claims"]:
            for x in c.get("experiments") or []:
                x.pop("spark", None)
        if changed:
            self.hub.write_json("stages.json", log)
        return doc

    @staticmethod
    def _outcome(x, ext, vs):
        """One experiment as a claim sees it: did ours come out ahead, and is there anything to check before trusting it?"""
        state, gap = reviewmod._state(x, ext)
        tl, sp = x.get("tally") or {}, x.get("spark") or []
        return {"id": x["id"], "name": x["name"], "type": x["type"], "state": state, "gap": gap, "vs": vs, "connected": bool(x["connected"]),
                "check": bool(tl.get("differs") or tl.get("untraced") or any(p["kind"] == "bold" for p in x["problems"])),
                "stale": bool(x["stale"]), "last": x.get("last"), "first": next((p["t"] for p in sp if p.get("t")), None),
                "lower": (x.get("summary") or {}).get("lower"), "vs_base": bool(ext), "spark": sp}

    def _judged(self, out, x, sec, own, vs, crit):
        """A claim's view of an experiment under a criterion that is not the default: the criterion decides ahead / behind."""
        c, by = crit(sec, x)
        if c:
            l = self._link(x, own, vs, c, by)
            if l["criterion_by"] != "default" and out["connected"]:
                out["state"] = {"supports": "ahead", "contradicts": "behind"}.get(l["status"], "none")
                out["criterion"] = l["criterion"]
        return out

    def _exp_doc(self):
        """The Experiments document. With a confirmed map it is kept until the scan or a file behind it changes (the claims read it too)."""
        s = self._ensure()
        if not undmod.load(self.hub)["confirmed"]:
            return self._exp()

        def stamp(name):
            try:
                st = self.hub.path(name).stat()
                return (st.st_mtime_ns, st.st_size)
            except OSError:
                return None
        key = (id(s["G"]), s["scanned_at"]) + tuple(stamp(n) for n in ("map.json", "experiments.json", "claims.json", "runs.json", "study.json", "hypothesis.json"))
        c = getattr(self, "_exp_cache", None)
        if c is None or c[0] != key:
            c = self._exp_cache = (key, self._exp())
        return c[1]

    def _claims_base(self):
        s = self._ensure()
        doc = claimsmod.build(s["G"], s["alarms"], s["findings"], claimsmod.load(self.hub))
        doc["macros"] = notationmod.macros(s["G"].paper.lines) if s["G"].paper is not None else {}
        # a result file older than the code or settings behind it makes every claim resting on it a recheck
        stale = {r["node_id"]: r["newer"][0]["name"] for r in processmod.ledger(s["G"].nodes, s["G"].edge_list(), s["events"])["rows"]
                 if r["status"] == "stale"}
        if stale:
            for c in doc["claims"]:
                for sup in c["support"]:
                    hit = next((x for x in (sup.get("chain") or {}).get("results", []) + [sup.get("node_id")] if x in stale), None)
                    if hit and sup["how"] != "suggested":
                        sup["stale"] = sup["stale"] or "%s changed after %s was made" % (stale[hit], s["G"].nodes[hit]["name"])
                        c["recheck"] = c["recheck"] or sup["stale"]
            live = [c for c in doc["claims"] if c["state"] != "rejected"]
            doc["counts"]["recheck"] = sum(bool(c["recheck"]) for c in live)
            if doc["core"]:
                doc["core"]["recheck"] = next((c["recheck"] for c in live if c["recheck"]), None)
        return doc

    def _born(self):
        """-> born(node_id, loc): when a file first appeared in the history, or when a line of the paper was last written
        (git blame). None when unknown (no git history, e.g. a paper uploaded as a zip)."""
        s = self._ensure()
        cache = getattr(self, "_born_cache", None)
        if cache is None or cache[0] is not s["G"]:
            first = {}
            for ev in s["events"]:
                if ev.get("kind") != "commit" or not ev.get("time"):
                    continue
                for f in ev.get("files", []):
                    first.setdefault("file:%s/%s" % (ev["repo"], f["path"]), ev["time"])
                    if f["path"].startswith("runs/") and f["path"].endswith(".json"):
                        first.setdefault("run:%s/%s" % (ev["repo"], f["path"][5:-5]), ev["time"])
            cache = (s["G"], first, {})
            self._born_cache = cache
        _, first, blame = cache
        paper = next((i for i in s["infos"].values() if i["role"] == "paper"), None)

        def lines_of(path):
            if path not in blame:
                out = {}
                if paper and paper.get("vcs") == "git" and len(blame) < 40:
                    p = treemod.run_git(paper["abs_path"], ["blame", "--line-porcelain", "-w", "--", path], check=False)
                    if p.returncode == 0:
                        no, t, tz = 0, None, "+0000"
                        for ln in p.stdout.decode("utf-8", "replace").split("\n"):
                            if ln.startswith("author-time "):
                                t = int(ln[12:])
                            elif ln.startswith("author-tz "):
                                tz = ln[10:].strip()
                            elif ln.startswith("\t"):
                                no += 1
                                if t is not None:
                                    from datetime import datetime, timedelta, timezone
                                    off = (1 if tz[0] != "-" else -1) * timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5]))
                                    out[no] = datetime.fromtimestamp(t, timezone(off)).isoformat()
                blame[path] = out
            return blame[path]

        def born(nid, loc):
            if nid and nid in first:
                return first[nid]
            if loc and loc.get("path") and loc.get("line"):
                ls = lines_of(loc["path"])
                ts = [ls[i] for i in range(loc["line"], (loc.get("end_line") or loc["line"]) + 1) if i in ls]
                return min(ts, key=lambda x: processmod._t(x)) if ts else None
            return None
        return born

    def tree(self):
        s = self._ensure()
        t = claimsmod.tree(self.claims(), s["G"], self._born())
        notes = self._notes()["notes"]
        for n in t["nodes"]:
            nid = n.get("node_id")
            if nid:
                n["caveat"] = bool((notes.get(nid) or {}).get("caveat"))
                if n["kind"] in ("figure", "asset"):
                    n["img"] = self.asset_of(nid) is not None
        tl = self.timeline()
        t["marks"] = [{"time": st["end"], "title": st["title"], "summary": st["summary"], "decision": st["decision"], "id": st["id"]}
                      for st in tl["steps"] if st.get("end")]
        if t["marks"]:
            ts = sorted([m["time"] for m in t["marks"]] + ([t["span"]["start"], t["span"]["end"]] if t["span"] else []), key=processmod._t)
            t["span"] = {"start": ts[0], "end": ts[-1]}
        return t

    # ------------------------------------------------------------------ evidence (one figure, table or file)
    def _notes(self):
        d = self.hub.read_json("notes.json", None)
        return d if isinstance(d, dict) and isinstance(d.get("notes"), dict) else {"schema": "lemmata.notes/1", "notes": {}}

    def asset_of(self, node_id):
        """-> (repo id, path) of the picture behind a figure or asset node, or None."""
        s = self._ensure()
        n = s["G"].nodes.get(node_id)
        if not n:
            raise NotFound("unknown item %r" % node_id)
        cands = []
        if n["kind"] == "asset":
            cands.append(n)
        for e in s["G"].edges.values():
            if e["from"] == node_id and e["kind"] == "includes" and e["to"] in s["G"].nodes:
                cands.append(s["G"].nodes[e["to"]])
        for a in cands:
            ext = (a["loc"]["path"].rsplit(".", 1)[-1] if "." in a["loc"]["path"] else "").lower()
            if ext in ("png", "jpg", "jpeg", "svg", "pdf"):
                return a["repo"], a["loc"]["path"]
        return None

    def _github(self):
        """repo id -> 'https://github.com/owner/name/blob/<commit>/<folder>' (no credentials), where the origin is GitHub."""
        s = self._ensure()
        cache = getattr(self, "_gh_cache", None)
        if cache is None or cache[0] is not s["G"]:
            out = {}
            for rid, i in s["infos"].items():
                if i.get("vcs") != "git" or not i.get("head"):
                    continue
                p = treemod.run_git(i["abs_path"], ["remote", "get-url", "origin"], check=False)
                url = p.stdout.decode("utf-8", "replace").strip() if p.returncode == 0 else ""
                import re as _re
                m = _re.match(r"^(?:https://(?:[^@/]+@)?github\.com/|git@github\.com:|ssh://git@github\.com/)([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", url)
                if m:
                    out[rid] = "https://github.com/%s/%s/blob/%s/%s" % (m.group(1), m.group(2), i["head"], treemod.show_prefix(i["abs_path"]))
            cache = (s["G"], out)
            self._gh_cache = cache
        return cache[1]

    def evidence(self, node_id):
        s = self._ensure()
        G = s["G"]
        n = G.nodes.get(node_id)
        if not n:
            raise NotFound("unknown item %r" % node_id)
        gh = self._github()
        last = {}
        for ev in s["events"]:
            if ev.get("kind") == "commit":
                for f in ev.get("files", []):
                    last["file:%s/%s" % (ev["repo"], f["path"])] = {"time": ev.get("time"), "short": ev.get("short"), "subject": ev.get("subject")}

        def link(x):
            m = G.nodes[x]
            path = (m.get("loc") or {}).get("path")
            return {"node_id": x, "name": m["name"], "kind": m["kind"], "repo": m["repo"],
                    "github": gh[m["repo"]] + path if m["repo"] in gh and path and m["kind"] != "run" else None, "last": last.get(x)}
        ctx = claimsmod._Ctx(G, s["alarms"], s["findings"])
        ch = ctx.chain(node_id)
        chain = [link(x) for x in ch["results"] + ch["code"] + ch["settings"] + ch["runs"]]
        doc = self.claims()
        backs = []
        for c in doc["claims"]:
            if c["state"] == "rejected":
                continue
            for sup in c["support"]:
                ids = [sup.get("node_id")] + [x for v in (sup.get("chain") or {}).values() for x in v]
                if node_id in ids and sup["how"] != "suggested":
                    backs.append({"id": c["id"], "label": c["label"], "text": c["text"][:200], "status": c["status"]})
                    break
        stale = next((r for r in self.ledger()["rows"] if r["status"] == "stale" and (r["node_id"] == node_id or r["node_id"] in ch["results"])), None)
        a = n.get("attrs") or {}
        out = {"schema": "lemmata.evidence/1", "node": {"id": node_id, "name": n["name"], "kind": n["kind"], "repo": n["repo"], "loc": n.get("loc")},
               "caption": a.get("caption") or n.get("detail") or "", "image": self.asset_of(node_id) is not None,
               "self": link(node_id) if n["kind"] in ("result", "asset", "code", "config", "data") else None,
               "chain": chain, "connected": bool(ch["code"] or ch["runs"] or any(G.nodes[x]["kind"] != "asset" for x in ch["results"]))
               or n["kind"] in ("code", "config", "run", "data"),
               "typed_by_hand": bool(a.get("manual")), "backs": backs,
               "stale": {"file": stale["name"], "newer": stale["newer"][:3]} if stale else None,
               "note": self._notes()["notes"].get(node_id, {}), "table": None}
        if n["kind"] == "table" and G.paper is not None:
            out["table"] = claimsmod.table_rows(G.paper, node_id)
        return out

    def set_note(self, node_id, caveat=None, purpose=None):
        s = self._ensure()
        if node_id not in s["G"].nodes:
            raise NotFound("unknown item %r" % node_id)
        d = self._notes()
        e = dict(d["notes"].get(node_id, {}))
        for k, v in (("caveat", caveat), ("purpose", purpose)):
            if v is not None:
                if not isinstance(v, str) or len(v) > 2000:
                    raise BadRequest("%s must be at most 2000 characters" % k)
                e[k] = v.strip()
        e = {k: v for k, v in e.items() if v}
        if e:
            e["updated"] = now_iso()
            d["notes"][node_id] = e
        else:
            d["notes"].pop(node_id, None)
        self.hub.write_json("notes.json", d)
        return self.evidence(node_id)

    # ------------------------------------------------------------------ experiments, by question
    def _exp(self, detail=None):
        s = self._ensure()
        d = undmod.load(self.hub)
        m = d["confirmed"]
        if detail is not None and str(detail).startswith("map:") and not m:
            raise NotFound("unknown experiment %r" % detail)
        st = self.study()
        if m and (detail is None or str(detail).startswith("map:")):
            return trackmod.build(m, s["G"], s["trees"], s["infos"], s["events"], s["alarms"], s["findings"], self.ledger(),
                                  expmod.load(self.hub), self._github(), detail, "proposed" if d["proposed"] else "confirmed",
                                  study=self._exp_kind(st), roles=studymod.roles_of(m))
        doc = expmod.build(s["G"], s["trees"], s["infos"], s["events"], s["alarms"], s["findings"], self._claims_base(), self.ledger(),
                           expmod.load(self.hub), self._github(), detail, study=self._exp_kind(st), roles=studymod.roles_of(None))
        if detail is None:
            doc["map"] = {"state": "proposed" if d["proposed"] else "none"}
        return doc

    # ------------------------------------------------------------------ sync state (S29)
    def sync_state(self):
        """How the hub's last sync with GitHub went, or None for a local project. While it is failing, Lemmata's copy is
        behind GitHub: a commit or a file it does not have is not known to be missing."""
        d = self.hub.read_json("sync.json", None)
        if not isinstance(d, dict):
            return None
        return {k: d.get(k) for k in ("failing", "at", "last_ok", "since", "code", "message", "head", "fails")}

    def _behind(self):
        st = self.sync_state()
        return st if st and st.get("failing") else None

    def _study_brief(self):
        try:
            st = self.study()
            return {"kind": st["kind"], "by": st["by"], "word": st["word"]}
        except Exception:      # the project summary must never fail because of this
            return None

    # ------------------------------------------------------------------ key numbers (S29)
    def _numbers_ctx(self):
        s, files, src, has_paper = self._hf_ctx()
        hd = hypomod.load(self.hub)
        live = [h for h in hd["hypotheses"] if not h.get("archived")]
        C = self.claims()
        claims, known, taken = [], {}, set()
        nm = lambda t: expmod.norm(t or "")
        for i, h in enumerate(live):
            c = next((c for c in C["claims"] if c.get("hypothesis") == h["id"]), None)
            key = "h:" + h["id"]
            claims.append({"key": key, "label": h["id"], "text": h["statement"], "stage": (c or {}).get("stage"), "stage_why": (c or {}).get("stage_why"),
                           "tier": h.get("tier"), "claim_id": h.get("claim_id"), "order": i})
            for name in [h["id"], h.get("claim_id")] + list(h.get("aliases") or []):
                if nm(name):
                    known[nm(name)] = key
            taken.add(h.get("claim_id"))
        for j, c in enumerate(c for c in C["claims"] if c["state"] != "rejected" and c["id"] not in taken and not c.get("formal")):
            key = "c:" + c["id"]
            claims.append({"key": key, "label": c.get("ref") or c.get("short") or c["label"], "text": c["text"], "stage": c.get("stage"), "stage_why": c.get("stage_why"),
                           "tier": None, "claim_id": c["id"], "order": 1000 + j})
            for name in (c["id"], c.get("ref"), c.get("short"), c.get("label")):
                if nm(name) and nm(name) not in known:
                    known[nm(name)] = key
        return s, files, hd, live, claims, known

    def numbers(self):
        """The numbers the study rests on, by claim: each read again from its file and compared with what the report says."""
        s, files, hd, live, claims, known = self._numbers_ctx()
        made = {}
        for r in self.ledger()["rows"]:
            n = s["G"].nodes.get(r["node_id"]) or {}
            if (n.get("loc") or {}).get("path"):
                made[n["loc"]["path"]] = r
        doc = numbersmod.build(numbersmod.load(self.hub), files, claims, live, hd["experiments"], s["events"], made, self.runs(1000)["runs"], self.sync_state())
        doc["study"] = self._study_brief()
        return doc

    def numbers_brief(self):
        """What an agent needs to list the key numbers: the format, the claims, the report and the test tables."""
        s, files, hd, live, claims, known = self._numbers_ctx()
        src = self._hf_ctx()[2]
        return {"schema": "lemmata.numbers.brief/1", "guide": numbersmod.GUIDE,
                "claims": [{"claim": c["label"], "text": c["text"], "stage": c["stage"]} for c in claims],
                "report": src.get("report") or [], "notes": src.get("notes") or [], "test_tables": src.get("test_tables") or [],
                "result_files": [c for c in (undmod.clusters(undmod.result_files(s["G"]), s["trees"], limit=40))],
                "already": [{"id": n["id"], "claim": n["claim"], "label": n["label"], "file": n["file"]} for n in numbersmod.load(self.hub)["confirmed"]]}

    def propose_numbers(self, doc, by=None):
        """A list written by an agent (or by hand). Checked by rules, stored as a proposal; nothing counts until confirmed."""
        s, files, hd, live, claims, known = self._numbers_ctx()
        clean, report = numbersmod.verify(doc, files, known)
        st = numbersmod.load(self.hub)
        st.update(proposed=clean, report=report, proposed_at=now_iso(), proposed_by=(by or "agent")[:60])
        self.hub.write_json("numbers.json", st)
        return self.numbers()

    def decide_numbers(self, action, number=None):
        """confirm: the proposal joins the list. discard: the proposal is dropped. remove: one number leaves the list."""
        st = numbersmod.load(self.hub)
        if action == "confirm":
            if not st["proposed"]:
                raise NotFound("there is no proposed list to confirm")
            st.update(confirmed=numbersmod.merge(st["confirmed"], st["proposed"]), proposed=None, confirmed_at=now_iso())
        elif action == "discard":
            st.update(proposed=None, report=[])
        elif action == "remove":
            numbersmod.remove(st, number)
        else:
            raise BadRequest("action must be confirm, discard or remove")
        self.hub.write_json("numbers.json", st)
        return self.numbers()

    # ------------------------------------------------------------------ baselines (S30)
    def _baselines_setup(self):
        s = self._ensure()
        E = self.experiments()
        doc = setupmod.build(E, s["G"], s["trees"])
        self._setup_context(doc, E, s)
        return doc

    def baselines(self):
        """Every method the work is compared with: its paper, PDF, code, idea and published numbers, beside the project's own numbers."""
        return baselinesmod.build(baselinesmod.load(self.hub), self._baselines_setup())

    def baselines_brief(self):
        """What an agent needs to fill the baseline cards in: the format, the baselines, and what each still lacks."""
        return baselinesmod.brief(self.baselines())

    def propose_baselines(self, doc, by=None):
        """Cards written by an agent. Checked by rules, stored as a proposal; nothing counts until the researcher confirms."""
        setup = self._baselines_setup()
        st = baselinesmod.load(self.hub)
        known = baselinesmod.known_names(setup)
        for k, e in st["entries"].items():
            known.setdefault(expmod.norm(e["name"]), k)
        clean, report = baselinesmod.verify(doc, known, (by or "agent")[:60])
        st.update(proposed=clean or None, report=report, proposed_at=now_iso(), proposed_by=(by or "agent")[:60])
        self.hub.write_json("baselines.json", st)
        return baselinesmod.build(st, setup)

    def _baseline_key(self, name, setup, st, create=False):
        n = expmod.norm(name or "")
        if not n:
            raise BadRequest("name is missing")
        key = baselinesmod.known_names(setup).get(n)
        if key is None:
            key = next((k for k, e in list(st["entries"].items()) + list((st.get("proposed") or {}).items()) if k == n or expmod.norm(e["name"]) == n), None)
        if key is None:
            if not create:
                raise NotFound("unknown baseline %r" % name)
            key = n
        return key

    def save_baseline(self, name, fields):
        """The researcher's own edit of one card (it counts at once), or a new baseline to track that is not in the result files yet."""
        setup = self._baselines_setup()
        st = baselinesmod.load(self.hub)
        if len(st["entries"]) >= baselinesmod.MAX_ENTRIES:
            raise BadRequest("too many baselines (%d at most)" % baselinesmod.MAX_ENTRIES)
        key = self._baseline_key(name, setup, st, create=True)
        st, notes = baselinesmod.save(st, key, " ".join(str(name).split())[:80], fields or {})
        self.hub.write_json("baselines.json", st)
        out = baselinesmod.build(st, setup)
        out["notes"] = notes
        return out

    def decide_baselines(self, action, name=None):
        """confirm or discard what the agent proposed (all of it, or one baseline); remove one card."""
        setup = self._baselines_setup()
        st = baselinesmod.load(self.hub)
        key = self._baseline_key(name, setup, st) if name else None
        if action == "remove" and key is None:
            raise BadRequest("name is missing")
        st = baselinesmod.decide(st, action, key)
        self.hub.write_json("baselines.json", st)
        return baselinesmod.build(st, setup)

    # ------------------------------------------------------------------ LaTeX to paste (S31)
    def _latex_ctx(self):
        """(setup, claims, every number the project holds, the paper's citation keys or None when there is no bibliography)."""
        setup = self._baselines_setup()
        claims = self.claims()
        docs = [[x.get("grid") for x in setup.get("experiments") or []], [it.get("uses") for it in setup.get("items") or []],
                [e.get("published") for e in baselinesmod.load(self.hub)["entries"].values()]]
        for read in (self.numbers, self.hypothesis):
            try:
                docs.append(read())
            except Exception:      # a project without key numbers or without a hypothesis-first record still gets its tables
                pass
        G = self._ensure()["G"]
        bib = {e["key"] for e in G.bib_entries if e.get("key")} if G.bib_entries else None
        return setup, claims, latexmod.pool(*docs), bib

    def latex(self):
        """Tables built by rule from the result files, what the researcher asked an agent to write, and what was written, checked."""
        setup, claims, numbers, bib = self._latex_ctx()
        return latexmod.build(latexmod.load(self.hub), setup, claims, numbers, bib)

    def latex_request(self, kind, target=None, ask=None):
        """The researcher asks for a table, a paragraph or a caption. It waits for their own agent."""
        setup, claims, numbers, bib = self._latex_ctx()
        st = latexmod.load(self.hub)
        latexmod.add_request(st, kind, latexmod.find_target(target, latexmod.targets(setup, claims)), ask)
        self.hub.write_json("latex.json", st)
        return latexmod.build(st, setup, claims, numbers, bib)

    def latex_brief(self, request=None, kind=None, target=None, ask=None):
        """Everything an agent needs to write the LaTeX: the guide and the whole state of the project. For a stored request, or ad hoc."""
        setup, claims, numbers, bib = self._latex_ctx()
        st = latexmod.load(self.hub)
        if request:
            req = next((r for r in st["requests"] if r["id"] == request), None)
            if req is None:
                raise NotFound("unknown request %r" % request)
        else:
            if (kind or "other") not in latexmod.KINDS:
                raise BadRequest("kind must be one of: " + ", ".join(latexmod.KINDS))
            t = latexmod.find_target(target, latexmod.targets(setup, claims))
            req = {"id": None, "kind": kind or "other", "target": t, "ask": (ask or None), "status": "ad hoc"}
        extra = {"citation_keys": sorted(bib)[:400] if bib else [], "already_written": [{"id": x["id"], "kind": x["kind"], "title": x["title"]} for x in st["snippets"]][-30:]}
        try:
            n = self.numbers()
            extra["key_numbers"] = [{k: r.get(k) for k in ("id", "claim", "text", "says", "value", "now", "holds", "status", "file", "unit") if r.get(k) is not None} for r in (n.get("numbers") or n.get("rows") or [])][:200]
        except Exception:
            extra["key_numbers"] = []
        try:
            b = baselinesmod.build(baselinesmod.load(self.hub), setup)
            extra["baselines"] = [{"name": r["name"], "role": r["role"], "idea": r["entry"].get("intuition"), "falls_short": r["entry"].get("limit"), "ours_differs": r["entry"].get("differs"),
                                   "paper": {k: (r["entry"].get("paper") or {}).get(k) for k in ("title", "authors", "year", "venue")},
                                   "cited_as": [c["key"] for c in r["cited"]], "published": r["compare"]} for r in b["rows"]]
        except Exception:
            extra["baselines"] = []
        try:
            extra["notation"] = [{k: x.get(k) for k in ("symbol", "latex", "meaning", "name", "code") if x.get(k)} for x in (self.notation().get("symbols") or [])][:150]
        except Exception:
            extra["notation"] = []
        return latexmod.brief(req, setup, claims, extra)

    def submit_latex(self, doc, by=None):
        """LaTeX written by the researcher's agent. Kept with its sources and checked by rules; nothing is compiled or run."""
        setup, claims, numbers, bib = self._latex_ctx()
        st = latexmod.load(self.hub)
        snip = latexmod.add_snippet(st, doc, (by or "agent")[:60], numbers)
        self.hub.write_json("latex.json", st)
        out = latexmod.build(st, setup, claims, numbers, bib)
        out["submitted"] = snip["id"]
        return out

    def decide_latex(self, action, ident):
        setup, claims, numbers, bib = self._latex_ctx()
        st = latexmod.decide(latexmod.load(self.hub), action, ident)
        self.hub.write_json("latex.json", st)
        return latexmod.build(st, setup, claims, numbers, bib)

    # ------------------------------------------------------------------ the kind of study (S29, ADR-009)
    def study(self):
        """method (the work has a method of its own, "ours") or benchmark (it compares existing methods; nothing is "ours")."""
        s, files, src, has_paper = self._hf_ctx()
        hd = hypomod.load(self.hub)
        hf = hd["enabled"] if hd["enabled"] is not None else hypomod.wanted(src, has_paper)
        m = undmod.load(self.hub)["confirmed"]
        st = studymod.load(self.hub)
        out = studymod.resolve(st, m, hf, survey_hint=has_paper and self._no_work_files(s))
        out.update(word=studymod.WORDS[out["kind"]], kinds=[{"k": k, "word": studymod.WORDS[k]} for k in studymod.KINDS], chosen=st["kind"],
                   roles={r: list((m or {}).get("roles", {}).get(r) or []) for r in studymod.ROLES if (m or {}).get("roles", {}).get(r)},
                   map_study=(m or {}).get("study"), ours=((m or {}).get("method") or {}).get("name") if out["kind"] == "method" else None)
        if out["kind"] == "benchmark" and (m or {}).get("method"):
            out["note"] = "The confirmed map names %s as the work's own method. As a benchmark study it is listed with the other compared methods." % m["method"]["name"]
        return out

    @staticmethod
    def _no_work_files(s):
        """S37 rule Y5: every code repository holds no code and no result files (a markdown list of surveyed models, say)."""
        codes = [r for r in s["repos"] if r["role"] == "code"]
        if not codes:
            return False
        return all(studymod.no_work_files(s["trees"][r["id"]].list_files()) for r in codes)

    @staticmethod
    def _exp_kind(st):
        """A survey has no "ours": the experiment pages read it like a benchmark study."""
        return "benchmark" if st["kind"] == "survey" else st["kind"]

    def set_study(self, kind):
        st = studymod.choose(studymod.load(self.hub), kind, now_iso())
        self.hub.write_json("study.json", st)
        self._exp_cache = None
        return self.study()

    # ------------------------------------------------------------------ survey papers (S37, ADR-013)
    LIST_MD_MAX = 30

    def _survey_lists(self, s):
        """The supplementary repositories' markdown files: {path: text}, and which repository each came from."""
        files, repo_of = {}, {}
        for r in s["repos"]:
            if r["role"] != "code":
                continue
            t = s["trees"][r["id"]]
            for name in t.list_files():
                if not name.lower().endswith(".md") or name.count("/") > 1 or name.startswith(".lemmata/"):
                    continue
                if t.size(name) > surveymod.MAX_FILE_BYTES or len(files) >= self.LIST_MD_MAX:
                    continue
                data = t.read(name)
                if data is None:
                    continue
                key = name if name not in files else "%s/%s" % (r["id"], name)
                files[key] = data.decode("utf-8", "replace")
                repo_of[key] = (r["id"], name)
        return files, repo_of

    def _survey_core(self):
        """The comparison itself, cached per scan and baseline (marks are applied on top, every time)."""
        s = self._ensure()
        paper = next((r for r in s["repos"] if r["role"] == "paper"), None)
        st = surveymod.load(self.hub)
        if paper is None:
            return None, st
        src = surveymod.Source(paper["abs_path"])
        versions = src.versions()
        if st["baseline"] is None and versions:
            st["baseline"], st["baseline_at"] = versions[0]["sha"], now_iso()      # the first look: nothing has changed yet
            self.hub.write_json(surveymod.STORE, st)
        base = src.resolve(st["baseline"]) if st["baseline"] else None
        dirty = src.dirty()
        key = (s["scanned_at"], base, versions[0]["sha"] if versions else None, dirty)
        c = getattr(self, "_sv_cache", None)
        if c is not None and c[0] == key:
            return c[1], st
        md, repo_of = self._survey_lists(s)
        models, datasets, lplaces = surveymod.read_list(md)
        for p in lplaces:
            p["repo"], p["path"] = repo_of[p["path"]]
        base_files = src.tex_files(base) if base else {}
        head_files = src.tex_files(None)
        changes = surveymod.compare(base_files, head_files, lplaces, list(models))
        head_places = [p for f in sorted(head_files) for p in surveymod.places_of(f, head_files[f])]
        list_rows, mentions = surveymod.list_check(models, datasets, head_places)
        for r in list_rows:
            if r.get("source") == "list" and r["path"] in repo_of:
                r["repo"], r["path"] = repo_of[r["path"]]
            elif r.get("source") == "list":
                r["repo"] = next((v[0] for k, v in repo_of.items() if v[1] == r["path"]), None)
        core = {"paper_repo": paper["id"], "versions": versions, "base": base, "dirty": dirty, "changes": changes, "list_rows": list_rows,
                "models": len(models), "mentioned": sum(1 for v in mentions.values() if v), "datasets": len(datasets),
                "list_files": sorted({v[1] for v in repo_of.values()}), "tex_files": len(head_files),
                "places": len(head_places)}
        self._sv_cache = (key, core)
        return core, st

    def survey(self):
        """What else must change: every change since the confirmed version, and the places that still say the old words."""
        core, st = self._survey_core()
        kind = self.study()["kind"]
        if core is None:
            return {"schema": surveymod.SCHEMA, "state": "no_paper", "kind": kind, "changes": [], "list": {"rows": []}, "counts": {}}
        changes = copy.deepcopy(core["changes"])
        list_rows = copy.deepcopy(core["list_rows"])
        for ch in changes:
            for r in ch["rows"]:
                r["repo"] = r.pop("repo", None) or (core["paper_repo"] if r["source"] == "paper" else None)
            if ch.get("path") is not None:
                ch["repo"] = core["paper_repo"]
        for r in list_rows:
            if r.get("source") == "paper":
                r["repo"] = core["paper_repo"]
        rows = [r for ch in changes for r in ch["rows"]]
        surveymod.apply_marks(rows + list_rows, st["marks"])
        for ch in changes:
            ch["open"] = sum(1 for r in ch["rows"] if r["shown"] in ("differs", "still", "check"))
        by_sha = {v["sha"]: v for v in core["versions"]}
        base = by_sha.get(core["base"]) if core["base"] else None
        if core["base"] and not base:
            base = {"sha": core["base"], "short": core["base"][:7], "time": None, "author": None, "subject": "(older than the last %d versions)" % surveymod.MAX_VERSIONS}
        head = core["versions"][0] if core["versions"] else None
        newer = 0
        for v in core["versions"]:
            if v["sha"] == core["base"]:
                break
            newer += 1
        cnt = lambda pred: sum(1 for r in rows if pred(r))
        return {"schema": surveymod.SCHEMA, "state": "ok", "kind": kind, "paper_repo": core["paper_repo"],
                "baseline": base, "baseline_at": st.get("baseline_at"), "head": head, "dirty": core["dirty"], "newer": newer,
                "versions": [dict(v, is_base=v["sha"] == core["base"], is_head=i == 0) for i, v in enumerate(core["versions"][:60])],
                "changes": changes, "confirmed": st["confirmed"][-10:],
                "list": {"rows": list_rows, "models": core["models"], "mentioned": core["mentioned"], "datasets": core["datasets"], "files": core["list_files"],
                         "counts": {k: sum(1 for r in list_rows if r["kind"] == k and r["shown"] != "left") for k in ("add", "update", "not_in_paper", "two_lists", "dataset_model")}},
                "counts": {"changes": len(changes), "differs": cnt(lambda r: r["shown"] == "differs"), "still": cnt(lambda r: r["shown"] == "still"),
                           "check": cnt(lambda r: r["shown"] == "check"), "left": cnt(lambda r: r["shown"] == "left"),
                           "fixed": cnt(lambda r: r["mark"] == "fixed" and r["shown"] != "still"),
                           "list": sum(1 for r in list_rows if r["shown"] != "left" and r["kind"] != "not_in_paper"),      # the quiet rows are not counted
                           "places": core["places"], "tex_files": core["tex_files"]}}

    def survey_act(self, action, rev=None, row=None, state=None):
        """baseline (compare with this version) | mark (a row fixed, leave or open) | confirm (this version is right)."""
        core, st = self._survey_core()
        if core is None:
            raise BadRequest("this project has no paper yet")
        if action == "baseline":
            s = self._ensure()
            paper = next(r for r in s["repos"] if r["role"] == "paper")
            sha_ = surveymod.Source(paper["abs_path"]).resolve(rev)
            if not sha_:
                raise BadRequest("unknown version %r" % rev)
            st["baseline"], st["baseline_at"] = sha_, now_iso()
        elif action == "mark":
            surveymod.mark(st, row, state, now_iso())
        elif action == "confirm":
            if not core["versions"]:
                raise BadRequest("the paper has no version to confirm")
            st["confirmed"].append({"from": core["base"], "to": core["versions"][0]["sha"], "at": now_iso(),
                                    "open": sum(1 for ch in core["changes"] for r in ch["rows"])})
            st["confirmed"] = st["confirmed"][-50:]
            st["baseline"], st["baseline_at"], st["marks"] = core["versions"][0]["sha"], now_iso(), {}
        else:
            raise BadRequest("action must be baseline, mark or confirm")
        self.hub.write_json(surveymod.STORE, st)
        return self.survey()

    LINK_WORDS = ("supports", "contradicts", "inconclusive", "not_run")

    @staticmethod
    def _compare(x, crit, own, vs):
        """Evaluate a non-default criterion on the experiment's grid. -> (state, why) with state supports | contradicts | none."""
        g, sm = x.get("grid"), x.get("summary") or {}
        if not g or x.get("tuning"):
            return "none", "A search over settings: it has a best setting, not a comparison." if x.get("tuning") else "Its result files could not be read as a table."
        lower, target = bool(sm.get("lower")), sm.get("target")
        rows = g["rows"]
        orow = next((r for r in rows if r["label"] == sm.get("ours_label")), None)
        if orow is None:
            return "none", "Ours was not found in the results."
        comp = crit["compare"]
        if comp == "base":
            name = ((sm.get("base") or {}).get("label")) or (vs if own else None)
            crow = next((r for r in rows if name and expmod.norm(r["label"]) == expmod.norm(name)), None)
            label = name or "the base method"
        elif comp == "best_other":
            crow, label = "best", "the best other method"
        else:
            crow = next((r for r in rows if expmod.norm(r["label"]) == expmod.norm(comp)), None)
            label = comp
        if crow is None:
            return "none", "%s is not in these results." % label
        main = g["metric"]
        dcols = [c for c in g["cols"] if c != setupmod.AVG and setupmod._split(c, g)[0] not in (None, setupmod.AVG) and (setupmod._split(c, g)[1] == main or len(g["measures"]) <= 1)]
        head = sm.get("metric") if sm.get("metric") in g["cols"] else (dcols[0] if dcols else g["cols"][0])
        over = crit["over"]

        def pair(c):
            ov = orow["values"].get(c)
            if crow == "best":
                vals = [r["values"].get(c) for r in rows if r is not orow and r["values"].get(c) is not None]
                if not vals or ov is None:
                    return None
                key = (lambda v: abs(v - target)) if target is not None else (lambda v: v)
                cv = (min if (lower or target is not None) else max)(vals, key=key)
            else:
                cv = crow["values"].get(c)
            if ov is None or cv is None:
                return None
            if setupmod._better(ov, cv, lower, target):
                return 1
            return -1 if (crit["strict"] or setupmod._better(cv, ov, lower, target)) else 0

        if over == "average" and dcols:
            def mean(r):
                vs_ = [r["values"].get(c) for c in dcols if r["values"].get(c) is not None]
                return sum(vs_) / len(vs_) if vs_ else None
            ov = mean(orow)
            if crow == "best":
                cand = [m for m in (mean(r) for r in rows if r is not orow) if m is not None]
                key = (lambda v: abs(v - target)) if target is not None else (lambda v: v)
                cv = (min if (lower or target is not None) else max)(cand, key=key) if cand else None
            else:
                cv = mean(crow)
            if ov is None or cv is None:
                return "none", "Nothing to compare with %s." % label
            ok = setupmod._better(ov, cv, lower, target) or (not crit["strict"] and not setupmod._better(cv, ov, lower, target))
            return ("supports" if ok else "contradicts"), "Averaged over %d datasets, ours is %.4g and %s is %.4g." % (len(dcols), ov, label, cv)
        cols = [head] if over in ("main", "average") or not dcols else dcols
        res = [(c, pair(c)) for c in cols]
        res = [(c, r) for c, r in res if r is not None]
        if not res:
            return "none", "Nothing to compare with %s." % label
        wins = sum(1 for _, r in res if r >= 0)
        need = len(res) if over in ("all", "main", "average") else len(res) // 2 + 1
        how = "better than" if crit["strict"] else "at least as good as"
        if len(res) == 1:
            return ("supports" if wins else "contradicts"), "Ours is %s%s %s on %s." % ("" if wins else "not ", how, label, res[0][0])
        return ("supports" if wins >= need else "contradicts"), "Ours is %s %s on %d of %d datasets (%s needed)." % (how, label, wins, len(res), "all" if over == "all" else "most")

    @classmethod
    def _link(cls, x, own, vs, crit=None, by="default"):
        """One claim-experiment link (ADR-008 section 1): does this experiment support the claim? Rules L1-L4. Without a
        criterion the default applies: ours at least as good as the comparator on the main column (a tie counts as support)."""
        sm = x.get("summary") or {}
        dflt = {"compare": "base" if own else "best_other", "over": "main", "strict": False}
        crit = dict(dflt, **(crit or {}))
        custom = crit != dflt
        out = {"criterion": dict(crit, vs=vs, metric=sm.get("metric")), "criterion_by": by if custom or by != "default" else "default"}
        has_files = (x.get("files_n") or 0) > 0 if x.get("map") else bool(x.get("connected"))
        if not has_files:
            return dict(out, status="not_run", rule="L1", why="No result file yet.")
        if custom:
            state, why = cls._compare(x, crit, own, vs)
            if state == "none":
                return dict(out, status="inconclusive", rule="L2", why=why)
            return dict(out, status=state, rule="L3" if state == "supports" else "L4", why=why)
        state, gap = reviewmod._state(x, own)
        if state == "none":
            why = ("A search over settings: it has a best setting, not a comparison." if x.get("tuning")
                   else "Results exist, but ours could not be compared with %s." % vs)
            return dict(out, status="inconclusive", rule="L2", why=why)
        on = (" on %s" % sm["metric"]) if sm.get("metric") else ""
        g = ("%.4g" % abs(gap)) if isinstance(gap, (int, float)) else "?"
        if state == "behind":
            return dict(out, status="contradicts", rule="L4", why="Ours is behind %s by %s%s." % (vs, g, on), gap=gap)
        why = ("Ours is level with %s%s (a tie counts as support)." % (vs, on)) if state == "tie" else "Ours is ahead of %s by %s%s." % (vs, g, on)
        return dict(out, status="supports", rule="L3", why=why, gap=gap)

    @staticmethod
    def _link_test(x, c):
        """A claim-experiment link in a benchmark study (rule L5, ADR-009): nothing is "ours", so the experiment does not
        rank a method. The claim's own test decides, and every experiment that feeds it carries that verdict."""
        out = {"criterion": {"kind": "test"}, "criterion_by": "test"}
        has_files = (x.get("files_n") or 0) > 0 if x.get("map") else bool(x.get("connected"))
        if not has_files:
            return dict(out, status="not_run", rule="L1", why="Waiting for its result files." if x.get("waiting") else "No result file yet.")
        c = c or {}
        rule, stage, why = c.get("stage_rule"), c.get("stage"), c.get("stage_why") or ""
        name = c.get("hypothesis") or c.get("short") or "this claim"
        if not c.get("hypothesis"):
            return dict(out, status="inconclusive", rule="L5",
                        why="A benchmark study has no method of its own to rank. Give %s a test (a row of the project's test table) and that decides it." % name)
        if rule == "R1" or (rule == "R0" and stage == "finding"):
            return dict(out, status="supports", rule="L5", why="%s: its test is met. %s" % (name, why))
        if rule == "R2" or (rule == "R0" and stage == "refuted"):
            return dict(out, status="contradicts", rule="L5", why="%s: its test is not met. %s" % (name, why))
        return dict(out, status="inconclusive", rule="L5", why="%s has no verdict: %s." % (name, why.rstrip(".") or "no test rule yet"))

    def _criteria(self):
        """-> crit(section, experiment) -> (criterion or None, who set it): yours (experiments.json) wins over the confirmed map's."""
        m = undmod.load(self.hub)["confirmed"] or {}
        mapped = {"map:" + x["id"]: x.get("criteria") or {} for x in m.get("experiments", [])}
        mine = {k: e.get("criteria") or {} for k, e in expmod.load(self.hub)["entries"].items()}

        def crit(sec, x):
            cid = sec.get("claim_id") or sec["id"]
            c = (mine.get(x["id"]) or {}).get(cid)
            if c:
                return c, "you"
            c = (mapped.get(x["id"]) or {}).get(sec["id"])
            return (c, "confirmed") if c else (None, "default")
        return crit

    def experiments(self):
        E = self._exp_doc()
        C = self.claims()
        by = {c["id"]: c for c in C["claims"]}
        ext = bool(E.get("extends"))
        base = E["extends"]["base"]["name"] if ext else None
        links = dict.fromkeys(self.LINK_WORDS, 0)
        tested = set()
        crit = self._criteria()
        bench = E.get("study") == "benchmark"
        E["study_info"] = self.study()
        for sec in E["sections"]:      # each section is a claim: show where that claim stands
            cid = sec.get("claim_id") or sec["id"]
            c = by.get(cid)
            if c:
                sec.update(stage=c["stage"], stage_by=c["stage_by"], stage_why=c["stage_why"], short=c["short"], loc=c.get("loc"),
                           stage_rule=c.get("stage_rule"), hypothesis=c.get("hypothesis"), tier=c.get("tier"))
            # the link of each experiment to this claim; kept on the section, because one experiment can test two claims
            own = ext and sec.get("scope") != "base"
            if bench:
                sec["links"] = {x["id"]: self._link_test(x, c) for x in sec["experiments"]}
            else:
                sec["links"] = {x["id"]: self._link(x, own, base if own else "the best other method", *crit(sec, x)) for x in sec["experiments"]}
            sec["bar"] = dict.fromkeys(self.LINK_WORDS, 0)
            for l in sec["links"].values():
                sec["bar"][l["status"]] += 1
                if sec.get("kind") != "other":
                    links[l["status"]] += 1
            if sec["experiments"] and sec.get("kind") != "other":
                tested.add(cid)
        # the thesis: counts only, never a verdict (rule T1)
        core = C.get("core") or {}
        live = [c for c in C["claims"] if c["state"] != "rejected"]
        no_claim = sum(len(sec["experiments"]) for sec in E["sections"] if sec.get("kind") == "other") + len(E.get("unassigned") or [])
        E["thesis"] = {"text": core.get("text"), "abstract": core.get("abstract"), "loc": core.get("loc"), "state": core.get("state"), "rule": "T1",
                       "claims": len(live), "stages": {k: sum(1 for c in live if c["stage"] == k) for k in claimsmod.STAGES},
                       "links": links, "links_n": sum(links.values()),
                       "buckets": {"untested": sum(1 for c in live if c["id"] not in tested), "no_claim": no_claim},
                       "untested": [{"id": c["id"], "short": c.get("short"), "text": c["text"], "stage": c["stage"]} for c in live if c["id"] not in tested][:30]}
        return E

    def experiment(self, exp_id):
        return self._exp(exp_id)

    def setup(self):
        """The metrics, datasets and methods the experiments use, each with how every experiment uses it (S23)."""
        s = self._ensure()
        E = self.experiments()
        doc = setupmod.build(E, s["G"], s["trees"])
        doc["study_info"] = E.get("study_info")
        self._setup_context(doc, E, s)
        doc["board"] = self._board(doc, E)
        return doc

    def _board(self, doc, E):
        """S28: thesis <- claims <- experiments <- what was used, as one board at the top of Setup (rules only)."""
        H = self.hypothesis()
        hf = H["mode"] == "hypothesis_first"
        if hf and (H["experiments"] or any(not h.get("archived") for h in H["hypotheses"])):
            s, files, src, has_paper = self._hf_ctx()
            key = (id(s["G"]), s["scanned_at"], tuple((x["id"], tuple(x.get("deliverables") or ())) for x in H["experiments"]))
            c = getattr(self, "_bd_used", None)
            if c is None or c[0] != key:      # reading the steps' result tables is the slow part: once per scan
                c = self._bd_used = (key, {x["id"]: boardmod.read_step(files, x.get("deliverables")) for x in H["experiments"]})
            return boardmod.from_hypothesis(H, files, doc, c[1])
        return boardmod.from_setup(doc, E.get("thesis"), waiting=hf)

    def _runs_of(self, exps):
        """exps: [(experiment id, its result path or None)] -> ({id: [(run, fields, how)] oldest first}, {id: matchers}).
        A run belongs to an experiment when it wrote a file matching the experiment's result pattern (how "wrote"), when its
        command names the result folder ("names"), when it is another run of a script known to write these results ("script"),
        or when the researcher attached it by hand ("attached", S35). A run attached by hand counts for that experiment only."""
        pats = self._exp_patterns(undmod.load(self.hub))
        runs = (runsmod.load(self.hub).get("runs") or [])
        att = benchmod.load(self.hub)["attached"]
        out, matchers = {}, {}
        for xid, path in exps:
            ms = matchers[xid] = [sessionsmod.matcher(p_) for p_ in pats.get(xid) or ([path] if path else [])]
            probe = [{"id": xid, "_match": ms}]
            mine = []
            for r in runs:
                a = att.get(r.get("run_id"))
                if a:
                    if a == xid:
                        hit = sessionsmod.experiments_of(r, probe)
                        mine.append((r, hit[0][1] if hit else self._arg_fields(r), "attached"))
                    continue
                hit = sessionsmod.experiments_of(r, probe)
                if hit and (hit[0][2] == "wrote" or sessionsmod.read_command(r.get("command"))["type"] == "script"):
                    mine.append((r, hit[0][1], hit[0][2]))
            wrote = {sessionsmod.read_command(r.get("command")).get("script") for r, _, h in mine if h == "wrote"} - {None}
            have = {id(r) for r, _, _ in mine}
            for r in runs:            # another run of a script that is known to write these results (it may have failed before writing)
                rd = sessionsmod.read_command(r.get("command"))
                if id(r) not in have and not att.get(r.get("run_id")) and rd["type"] == "script" and rd.get("script") in wrote:
                    mine.append((r, self._arg_fields(r), "script"))
            mine.sort(key=lambda m: m[0].get("ended") or m[0].get("started") or "")
            out[xid] = mine
        return out, matchers

    @staticmethod
    def _arg_fields(run):
        rd = sessionsmod.read_command(run.get("command"))
        return {k: [v] for k, v in (rd.get("args") or {}).items() if k in ("dataset", "method", "seed") and isinstance(v, str)}

    def _setup_context(self, doc, E, s):
        """S26: for each experiment the where, how, when and who behind it (the why and what are its claim and protocol)."""
        full = {x["id"]: x for sec in E["sections"] for x in sec["experiments"]}
        led = {r["node_id"]: r for r in self.ledger()["rows"]}
        mine_of, ms_of = self._runs_of([(x["id"], ((full.get(x["id"]) or {}).get("result") or {}).get("path")) for x in doc["experiments"]])
        for x in doc["experiments"]:
            f = full.get(x["id"]) or {}
            res = f.get("result") or {}
            ms, mine = ms_of[x["id"]], mine_of[x["id"]]
            who, hosts, scripts = {}, [], []
            for r, _, _ in mine:
                w = sessionsmod.who_of(r)
                who[w] = who.get(w, 0) + 1
                if r.get("host") and r["host"] not in hosts:
                    hosts.append(r["host"])
                sc = sessionsmod.read_command(r.get("command")).get("script")
                if sc and sc not in scripts:
                    scripts.append(sc)
            row = led.get(res.get("node_id")) or {}
            folder = (ms[0][1] if ms else "") or (res.get("path") or "").rsplit("/", 1)[0]
            sp = [p_ for p_ in f.get("spark") or [] if p_.get("t")]
            made = row.get("made") or {}
            x["context"] = {
                "where": {"repo": f.get("repo"), "folder": folder or None, "hosts": hosts, "files_n": x.get("files_n")},
                "how": {"scripts": scripts[:4], "code": [c["name"] for c in row.get("code") or []][:4], "settings": [c["name"] for c in row.get("settings") or []][:4],
                        "command": next((r.get("command") for r, _, h in reversed(mine) if r.get("command") and h == "wrote"), None)},
                "when": {"first": sp[0]["t"] if sp else made.get("time"), "last": f.get("last") or made.get("time"), "updates": f.get("history_n") or len(sp), "stale": bool(f.get("stale"))},
                "who": {"runs": len(mine), "by": [{"who": k, "n": who[k]} for k in ("you", "agent", "watcher") if who.get(k)], "commit": made.get("short"), "subject": made.get("subject")},
                "runs": [{"id": r.get("run_id"), "t": r.get("ended") or r.get("started"), "who": sessionsmod.who_of(r), "host": r.get("host"), "command": (r.get("command") or "")[:400],
                          "sha": (r.get("git_sha") or "")[:7] or None, "dirty": bool(r.get("dirty")), "exit": r.get("exit_code"), "how": h, "fields": {k: v[:6] for k, v in fl.items()}}
                         for r, fl, h in mine[-12:]][::-1],
            }

    def set_experiment(self, exp_id, ours=None, metric=None, lower=None, measure=None, claim=None, criterion=None):
        s = self._ensure()
        st = expmod.load(self.hub)
        if claim is not None:      # the criterion for one claim-experiment link; {} or None-like clears it (back to the map's or the default)
            if not isinstance(claim, str) or claim not in {c["id"] for c in self.claims()["claims"]}:
                raise BadRequest("unknown claim %r" % claim)
            e = st["entries"].setdefault(exp_id, {})
            cs = e.setdefault("criteria", {})
            if criterion:
                cs[claim] = undmod.criterion(criterion)
            else:
                cs.pop(claim, None)
            if not cs:
                e.pop("criteria")
            self.hub.write_json("experiments.json", st)
            return self.experiments()
        m = undmod.load(self.hub)["confirmed"]
        known = {nid for nid, n in s["G"].nodes.items() if n["kind"] in ("table", "figure", "result", "data")} | {"map:" + x["id"] for x in (m or {}).get("experiments", [])}
        if str(exp_id).startswith("map:") and exp_id in known:      # in a mapped experiment the columns are datasets; the measure is the number read from each file
            e = st["entries"].setdefault(exp_id, {})
            for k, v in (("column", metric), ("metric", measure)):
                if v is not None:
                    if not isinstance(v, str) or len(v) > 200:
                        raise BadRequest("%s must be text" % k)
                    e[k] = v
                    if not v:
                        e.pop(k)
            metric = None
        expmod.decide(st, known, exp_id, ours, metric, lower)
        self.hub.write_json("experiments.json", st)
        return self._exp(exp_id)

    # ------------------------------------------------------------------ review: should I continue?
    def _numbers_by_claim(self, E):
        """Key-number counts per claim, for a benchmark study's checklist."""
        if E.get("study") != "benchmark":
            return None
        try:
            return {g["claim_id"]: g["counts"] for g in self.numbers()["groups"] if g.get("claim_id")}
        except Exception:      # the Review page must never fail because of this
            return {}

    def review(self, days=30, now=None):
        E = self.experiments()
        return reviewmod.build(E, reviewmod.load(self.hub), days, now, self._numbers_by_claim(E))

    def set_review(self, hoped=None, question=None, resolve=None, mine=None, days=30):
        E = self.experiments()
        st = reviewmod.load(self.hub)
        reviewmod.decide(st, {s["id"] for s in E["sections"]}, hoped, question, resolve, mine, now_iso())
        self.hub.write_json("review.json", st)
        return reviewmod.build(E, st, days, None, self._numbers_by_claim(E))

    def confound_brief(self):
        return reviewmod.brief(self._exp(), self._exp)

    def report_confounds(self, findings, by="agent"):
        s = self._ensure()
        E = self._exp()
        st = reviewmod.load(self.hub)
        notes = reviewmod.report(st, findings, E, s["trees"], by, now_iso())
        self.hub.write_json("review.json", st)
        return {"notes": notes, "review": reviewmod.build(E, st)}

    # ------------------------------------------------------------------ next experiments (S20: planned by the user's own agent)
    def plans(self):
        s = self._ensure()
        return plansmod.view(plansmod.load(self.hub), plansmod.files_of(s["trees"]))

    def plan_brief(self, target):
        E = self._exp()
        try:
            rv = reviewmod.build(E, reviewmod.load(self.hub))
        except Exception:
            rv = None
        return dict(plansmod.brief(E, rv, self._exp, target, plansmod.load(self.hub)), how_to_propose=plansmod.GUIDE)

    def propose_plans(self, target, proposals, by="agent"):
        s = self._ensure()
        st = plansmod.load(self.hub)
        notes = plansmod.propose(st, self._exp(), s["trees"], target, proposals, by, now_iso())
        self.hub.write_json("plans.json", st)
        return {"notes": notes, "plans": plansmod.view(st, plansmod.files_of(s["trees"]))["plans"]}

    def set_plan(self, plan_id, state=None, spec=None, title=None):
        s = self._ensure()
        st = plansmod.load(self.hub)
        plansmod.decide(st, plan_id, state, spec, title, now_iso())
        self.hub.write_json("plans.json", st)
        return plansmod.view(st, plansmod.files_of(s["trees"]))

    # ------------------------------------------------------------------ project map (phase 1: understand)
    def brief(self):
        s = self._ensure()
        return undmod.brief(s["G"], s["trees"], s["infos"], s["events"], self.claims())

    def project_map(self):
        s = self._ensure()
        d = undmod.load(self.hub)
        shown = d["proposed"] or d["confirmed"]
        return dict(d, coverage=undmod.coverage(shown, s["G"], s["trees"]) if shown else None,
                    state="proposed" if d["proposed"] else "confirmed" if d["confirmed"] else "none")

    def _propose(self, doc, by):
        s = self._ensure()
        m, report = undmod.verify(doc, s["G"], s["trees"], s["infos"], self.claims())
        d = undmod.load(self.hub)
        d.update(proposed=m, report=report, proposed_at=now_iso(), proposed_by=(by or "you")[:60])
        self.hub.write_json("map.json", d)
        return self.project_map()

    def propose_map(self, doc, by=None):
        """A map written by an agent (or by hand). Checked by rules, stored as a proposal; nothing uses it until confirmed."""
        return self._propose(doc, by or "agent")

    def draft_map(self):
        """A proposal made by rules alone, for when no agent has read the project."""
        s = self._ensure()
        doc = undmod.draft(s["G"], s["trees"], s["infos"], s["events"], self.claims())
        if self.study()["kind"] in ("benchmark", "survey"):
            doc.update(study="benchmark", method=None)
        return self._propose(doc, "rules")

    def edit_map(self, patch):
        d = undmod.load(self.hub)
        return self._propose(undmod.edit(d["proposed"] or d["confirmed"], patch), d.get("proposed_by") if d["proposed"] else "you")

    def discard_map(self):
        d = undmod.load(self.hub)
        d.update(proposed=None, report=[])
        self.hub.write_json("map.json", d)
        return self.project_map()

    def confirm_map(self, actor=None):
        """The researcher accepts the proposal. Its questions become claims (reusing the ones the paper already states)
        and each question is linked to the tables and figures its experiments feed."""
        s = self._ensure()
        d = undmod.load(self.hub)
        if not d["proposed"]:
            raise NotFound("there is no proposed map to confirm")
        m, report = undmod.verify(d["proposed"], s["G"], s["trees"], s["infos"], self.claims())
        if not m["experiments"]:
            raise BadRequest("this map has no experiment that passed checking; there is nothing to confirm")
        prev = {q["text"]: q.get("claim_id") for q in (d["confirmed"] or {}).get("questions", [])}
        st = claimsmod.load(self.hub)
        ids = self._claim_ids()
        for q in m["questions"]:
            cid = q.get("claim") if q.get("claim") in ids else prev.get(q["text"]) if prev.get(q["text"]) in ids else None
            if cid is None:
                cid = claimsmod.add_manual(st, q["text"], "question" if q["kind"] == "question" else "contribution")["id"]
                ids.add(cid)
            q["claim_id"] = cid
            for mm in st["manual"]:      # a claim made from the map carries the map's label (RQ1, E1 ...)
                if mm["id"] == cid:
                    mm["label"] = q["label"]
            for x in m["experiments"]:
                if q["id"] in x["tests"]:
                    for p in x["paper"]:
                        claimsmod.link(st, ids, s["G"].nodes, cid, p, True)
        self.hub.write_json("claims.json", st)
        d.update(confirmed=m, proposed=None, report=report, confirmed_at=now_iso(), confirmed_by=actor or None)
        self.hub.write_json("map.json", d)
        return self.project_map()

    # ------------------------------------------------------------------ hypothesis-first (S27)
    def _hf_ctx(self):
        s = self._ensure()
        files = hypomod.Files(s["trees"], s["infos"])
        key = (id(s["G"]), s["scanned_at"])
        c = getattr(self, "_hf_src", None)
        if c is None or c[0] != key:
            c = self._hf_src = (key, hypomod.detect(files))
        has_paper = s["G"].paper is not None and bool(getattr(s["G"].paper, "lines", None))
        return s, files, c[1], has_paper

    def hypothesis(self):
        """The research's problem, hypotheses, tests, deviations and the jobs waiting for the researcher's own LLM."""
        s, files, src, has_paper = self._hf_ctx()
        d = hypomod.load(self.hub)
        mode = d["enabled"] if d["enabled"] is not None else hypomod.wanted(src, has_paper)
        if hypomod.ensure_jobs(d, mode):
            self.hub.write_json("hypothesis.json", d)
        return hypomod.view(files, src, d, s["hist"], has_paper)

    def _hf_claims(self, d):
        """A confirmed hypothesis is a claim (one claim store, S17 stages); an archived one is a rejected claim."""
        st = claimsmod.load(self.hub)
        manual = {m["id"]: m for m in st["manual"]}
        changed = False
        for h in d["hypotheses"]:
            cid = h.get("claim_id")
            if h.get("confirmed") and not h.get("archived") and cid not in manual:
                m = claimsmod.add_manual(st, h["statement"], "contribution")
                m["label"] = h["id"]
                h["claim_id"], cid, changed = m["id"], m["id"], True
                manual[cid] = m
            if cid in manual:
                want = "rejected" if h.get("archived") else "confirmed" if h.get("confirmed") else "proposed"
                e = st["entries"].setdefault(cid, {})
                if e.get("state") != want or manual[cid].get("text") != h["statement"] or manual[cid].get("label") != h["id"]:
                    e["state"], manual[cid]["text"], manual[cid]["label"], changed = want, h["statement"], h["id"], True
        if changed:
            self.hub.write_json("claims.json", st)

    def _hf_stages(self, doc):
        """Claims made from hypotheses take their stage from the project's own test table (rules R0-R5), not from ours vs best."""
        try:
            d = hypomod.load(self.hub)
            if not d["hypotheses"]:
                return
            s, files, src, has_paper = self._hf_ctx()
            xs = {x["id"]: hypomod.experiment_status(files, x) for x in d["experiments"]}
        except Exception:      # the claims page must never fail because of this
            return
        by_claim = {h["claim_id"]: h for h in d["hypotheses"] if h.get("claim_id")}
        live = []
        for c in doc["claims"]:
            h = by_claim.get(c["id"])
            if h is not None:
                stg, rule, why, _ = hypomod.stage(files, d, h, xs)
                c.update(stage=stg, stage_auto=stg, stage_by="you" if rule == "R0" else "rule", stage_rule=rule, stage_rule_auto=rule,
                         stage_why=why, ref=h["id"], short=h["id"], hypothesis=h["id"], tier=h["tier"])
            if c["state"] != "rejected":
                live.append(c)
        doc["counts"]["stages"] = {k: sum(c["stage"] == k for c in live) for k in claimsmod.STAGES}

    def _hf_save(self, d):
        self._hf_claims(d)
        self.hub.write_json("hypothesis.json", d)

    def hypothesis_act(self, action, target=None, text=None, note=None, targets=None, fields=None, stage=None, prediction=None):
        d = hypomod.load(self.hub)
        msg = hypomod.act(d, action, target, text, note, targets, fields, stage, prediction)
        self._hf_save(d)
        return dict(self.hypothesis(), message=msg)

    def hypothesis_job(self, job_id):
        s, files, src, has_paper = self._hf_ctx()
        d = hypomod.load(self.hub)
        j = next((j for j in d["jobs"] if j["id"] == job_id), None)
        if j is None:
            raise NotFound("unknown job %r" % job_id)
        return hypomod.job_doc(d, j, src, s["man"].get("name", self.root.name))

    def submit_hypothesis_job(self, job_id, result, by=None):
        s, files, src, has_paper = self._hf_ctx()
        d = hypomod.load(self.hub)
        j, report = hypomod.submit(files, d, job_id, result, by or "agent")
        self._hf_save(d)
        return dict(self.hypothesis(), submitted=j, submit_report=report)

    def hypothesis_change(self, cs_id, decision, which=None):
        d = hypomod.load(self.hub)
        if decision == "accept":
            done, proposals = hypomod.accept(d, cs_id, which)
            if proposals:
                d.setdefault("proposals", []).append({"id": cs_id, "at": now_iso(), "ops": proposals})
            msg = "Applied: " + "; ".join(done) + (". %d change(s) the protocol does not say: download the proposal for your notes." % len(proposals) if proposals else ".")
        elif decision == "reject":
            msg = hypomod.reject(d, cs_id)
        else:
            raise BadRequest("decision must be accept or reject")
        self._hf_save(d)
        return dict(self.hypothesis(), message=msg)

    def hypothesis_proposal(self, cs_id):
        """The protocol change a change set implies, as a notes file for the researcher to commit (Lemmata never edits the protocol)."""
        d = hypomod.load(self.hub)
        p = next((p for p in d.get("proposals", []) if p["id"] == cs_id), None)
        if p is None:
            raise NotFound("no proposal for %r" % cs_id)
        cs = next((c for c in d["change_sets"] if c["id"] == cs_id), {})
        out = ["# Proposed protocol change (from Lemmata, %s)" % p["at"][:10], "",
               "Not applied to the protocol. Lemmata accepted these changes into its own view on %s; the protocol does not say them yet." % p["at"][:10], "",
               "What was understood: %s" % (cs.get("understood") or "-"), ""]
        for o in p["ops"]:
            what = o.get("target") or ", ".join(o.get("targets") or []) or (o.get("after") or {}).get("id")
            after = o.get("after")
            out += ["## %s %s" % (o["op"], what), "", "- Reason: %s" % (o.get("reason") or "-")]
            if isinstance(after, dict):
                out.append("- Statement: %s" % after.get("statement"))
            elif after is not None:
                out.append("- New value: %s" % (after if isinstance(after, str) else ", ".join(after)))
            if o.get("from"):
                out.append("- From the researcher's input: \"%s\"" % o["from"]["quote"])
            out.append("")
        return "\n".join(out)

    # ------------------------------------------------------------------ notation
    def notation(self):
        s = self._ensure()
        cache = getattr(self, "_nt_cache", None)
        st = notationmod.load(self.hub)
        key = (id(s["G"]), repr(sorted(st["entries"].items())))
        if cache is None or cache[0] != key:
            cache = (key, notationmod.build(s["G"].paper, s["G"].nodes, s["trees"], st, self._github()))
            self._nt_cache = cache
        return cache[1]

    def set_notation(self, symbol, meaning=None, ignore=None, link=None, unlink=None):
        known = {i["key"] for i in self.notation()["symbols"]}
        st = notationmod.load(self.hub)
        notationmod.decide(st, known, symbol, meaning, ignore, link, unlink)
        self.hub.write_json("notation.json", st)
        return self.notation()

    def _claim_ids(self):
        d = self._claims_base()
        return {c["id"] for c in d["claims"]} | ({"core"} if d["core"] else set())

    def set_claim(self, claim_id, state=None, text=None, note=None, stage=None):
        st = claimsmod.load(self.hub)
        claimsmod.decide(st, self._claim_ids(), claim_id, state, text, note, stage)
        self.hub.write_json("claims.json", st)
        return self.claims()

    def link_claim(self, claim_id, target, on=True):
        s = self._ensure()
        st = claimsmod.load(self.hub)
        claimsmod.link(st, self._claim_ids(), s["G"].nodes, claim_id, target, bool(on))
        self.hub.write_json("claims.json", st)
        return self.claims()

    def add_claim(self, text, kind="claim"):
        st = claimsmod.load(self.hub)
        claimsmod.add_manual(st, text, kind)
        self.hub.write_json("claims.json", st)
        return self.claims()

    def remove_claim(self, claim_id):
        st = claimsmod.load(self.hub)
        claimsmod.remove_manual(st, claim_id)
        self.hub.write_json("claims.json", st)
        return self.claims()

    def claims_markdown(self):
        s = self._ensure()
        return claimsmod.to_markdown(self.claims(), s["man"].get("name", self.root.name), now_iso()[:10])

    # ------------------------------------------------------------------ research process
    def _roles(self):
        return {r["id"]: r["role"] for r in self._ensure()["repos"]}

    def timeline(self):
        s = self._ensure()
        return processmod.timeline(s["events"], s["G"].nodes, self._roles(), self.claims())

    # ------------------------------------------------------------------ to-do and trail (S24 steps 4-5)
    def todo(self, today=None, _docs=None):
        """What to do next, by rule, each item with the page it opens (ADR-008 section 5.1)."""
        s = self._ensure()
        today = today or now_iso()[:10]
        d = undmod.load(self.hub)
        try:
            nums = self.numbers()
        except Exception:      # the to-do list must never fail because of this
            nums = None
        E, S = _docs or (self.experiments(), self.setup())
        try:      # drafts that wait for the researcher (S36); the to-do list must never fail because of them
            hypo = self.hypothesis()
        except Exception:
            hypo = None
        try:
            bl = self.baselines()
        except Exception:
            bl = None
        return todomod.build(E, self.claims(), S, self.tasks(), s["findings"], s["alarms"], self.plans(),
                             {"proposed": d.get("proposed")}, trailmod.load_deadlines(self.hub)["deadlines"], todomod.load(self.hub), today,
                             numbers=nums, sync=self.sync_state(), hypo=hypo, baselines=bl)

    # ------------------------------------------------------------------ the bench (S35, ADR-011): what VS Code shows
    def bench(self, today=None):
        """Runs, experiments, their setup and what to run next, as rows ready to draw (engine/bench.py)."""
        self._ensure()
        today = today or now_iso()[:10]
        E, S = self.experiments(), self.setup()
        ids = []
        for sec in E["sections"]:
            for x in sec["experiments"]:
                if x["id"] not in [i for i, _ in ids]:
                    ids.append((x["id"], (x.get("result") or {}).get("path")))
        mine_of, _ = self._runs_of(ids)
        return benchmod.build(E, S, self.todo(today, _docs=(E, S)), self.plans(), self.runs(400)["runs"], mine_of, today, self.project().get("name"))

    def attach_run(self, run_id, exp_id=None):
        """The researcher says which experiment a run belongs to (or, with no experiment, takes that back)."""
        self._ensure()
        E = self.experiments()
        st = benchmod.attach(benchmod.load(self.hub), {r.get("run_id") for r in runsmod.load(self.hub).get("runs") or []},
                             {x["id"] for sec in E["sections"] for x in sec["experiments"]}, run_id, exp_id)
        self.hub.write_json(benchmod.STORE, st)
        return self.bench()

    def since(self, viewer=None, mark=False):
        """What changed after this person last opened Home, newest first (S36). Nothing is stored unless mark is true, which
        records now as the last time they looked. viewer: the signed-in GitHub login on a hub, None for the local user."""
        self._ensure()
        store = sincemod.load(self.hub)
        now = now_iso()
        doc = sincemod.build(self.trail(), store["users"].get(sincemod.key_of(viewer)), now)
        if mark:
            self.hub.write_json("home_seen.json", sincemod.mark(store, viewer, now))
        return doc

    def snooze_todo(self, key, until=None):
        self._ensure()
        st = todomod.snooze(todomod.load(self.hub), key, until)
        self.hub.write_json("todo.json", st)
        return self.todo()

    def trail(self, start=None, end=None, today=None):
        """The time axis: what was done, day by day, and the deadlines ahead (ADR-008 section 5.2)."""
        s = self._ensure()
        C = self.claims()
        d = undmod.load(self.hub)
        exps, short = {}, {c["id"]: c.get("short") or c["label"] for c in C["claims"]}
        res = {nid for nid, n in s["G"].nodes.items() if n["kind"] in ("result", "data")}
        for sec in self.experiments()["sections"]:
            for x in sec["experiments"]:
                rec = exps.setdefault(x["id"], dict(x, _claims=[], _paths=[]))
                cid = sec.get("claim_id") or sec["id"]
                if sec.get("kind") != "other" and short.get(cid) and short[cid] not in rec["_claims"]:
                    rec["_claims"].append(short[cid])
        paths = {s["G"].nodes[n]["loc"]["path"] for n in res if s["G"].nodes[n].get("loc")}
        pats = self._exp_patterns(d)
        for rec in exps.values():
            rec["_paths"] = paths
            rec["_match"] = [sessionsmod.matcher(p_) for p_ in pats.get(rec["id"]) or ([rec["result"]["path"]] if (rec.get("result") or {}).get("path") else [])]
        return trailmod.build(s["events"], self.timeline()["steps"], self.hub.read_json("stages.json", None) or {}, C, runsmod.load(self.hub),
                              processmod.load_tasks(self.hub), d, self.checkpoints(), self.plans(), trailmod.load_deadlines(self.hub)["deadlines"],
                              self._github(), start, end, today or now_iso()[:10], list(exps.values()), s["repos"], sessionsmod.load_notes(self.hub))

    @staticmethod
    def _exp_patterns(d):
        """experiment id -> the result-file patterns the confirmed map gives it."""
        return {"map:%s" % x["id"]: [f for f in x.get("files") or [] if isinstance(f, str)] for x in ((d.get("confirmed") or {}).get("experiments") or [])}

    def session_note(self, sid, text=None, action=None, by="you"):
        """The one-line summary of a work session: an agent proposes, the researcher confirms, edits or removes (ADR-007)."""
        self._ensure()
        known = {x["id"] for x in self.trail()["sessions"]}
        st = sessionsmod.set_note(sessionsmod.load_notes(self.hub), known, sid, text, action, by, now_iso())
        self.hub.write_json("sessions.json", st)
        return self.trail()

    def set_deadline(self, date=None, title=None, target=None, remove=None, kind=None, venue=None):
        self._ensure()
        st = trailmod.set_deadline(trailmod.load_deadlines(self.hub), date, title, target, remove, kind, venue)
        self.hub.write_json("deadlines.json", st)
        return self.trail()

    def venue_lookup(self, name, year, fetch=None):
        """A conference's deadlines from the open deadline data (not stored until add_venue)."""
        return venuesmod.lookup(name, year, fetch) if fetch else venuesmod.lookup(name, year)

    def add_venue(self, name, year, kinds=None, fetch=None):
        self._ensure()
        found = self.venue_lookup(name, year, fetch)
        st = trailmod.add_venue(trailmod.load_deadlines(self.hub), found, kinds)
        self.hub.write_json("deadlines.json", st)
        return self.trail()

    def calendar(self, action=None):
        """The subscription link's secret token for this project's deadlines: create, revoke, or read."""
        self._ensure()
        st = self.hub.read_json("calendar.json", None)
        st = st if isinstance(st, dict) else {}
        if action == "create":
            st = {"token": secrets.token_urlsafe(24), "created": now_iso()}
            self.hub.write_json("calendar.json", st)
        elif action == "revoke":
            st = {}
            self.hub.write_json("calendar.json", st)
        elif action is not None:
            raise BadRequest("action must be create or revoke")
        return {"token": st.get("token"), "created": st.get("created"), "events": len(trailmod.load_deadlines(self.hub)["deadlines"])}

    def calendar_ics(self):
        self._ensure()
        return trailmod.ics(trailmod.load_deadlines(self.hub)["deadlines"], self.project().get("name") or "research")

    def ledger(self):
        s = self._ensure()
        return processmod.ledger(s["G"].nodes, s["G"].edge_list(), s["events"], self._claims_base())

    def tasks(self):
        s = self._ensure()
        return processmod.tasks_view(processmod.load_tasks(self.hub), s["G"].nodes, s["G"].edge_list())

    def add_feedback(self, text, source=None):
        s = self._ensure()
        st = processmod.load_tasks(self.hub)
        processmod.add_feedback(st, text, source, s["G"].nodes, s["G"].edge_list(), self.claims(), now_iso())
        self.hub.write_json("tasks.json", st)
        return self.tasks()

    def set_task(self, task_id, state=None, note=None, add_target=None, remove_target=None, text=None):
        s = self._ensure()
        st = processmod.load_tasks(self.hub)
        processmod.set_task(st, s["G"].nodes, task_id, state, note, add_target, remove_target, text, now_iso())
        self.hub.write_json("tasks.json", st)
        return self.tasks()

    def digest(self, days=7):
        s = self._ensure()
        if not isinstance(days, int) or not 1 <= days <= 90:
            raise BadRequest("days must be 1 to 90")
        d = processmod.digest(s["man"].get("name", self.root.name), self.timeline(), self.ledger(), self.claims(), self.tasks(),
                              s["alarms"], now_iso(), days)
        rows = self.runs(1000)["runs"]
        since = (datetime.now().astimezone() - timedelta(days=days)).replace(microsecond=0).isoformat()
        line = runsmod.digest_line(rows, since)
        if line:
            d["text"] += "\n" + line
            d["numbers"]["runs"] = sum(1 for r in rows if runsmod.newer(r.get("time"), since))
        return d

    # ------------------------------------------------------------------ runs logged outside GitHub (editor, agent)
    def runs(self, limit=200):
        s = self._ensure()
        return runsmod.view(runsmod.load(self.hub), s["G"].nodes, s["events"], self._roles(), limit, self._behind())

    def add_runs(self, runs, by=None):
        self._ensure()
        st = runsmod.load(self.hub)
        out = runsmod.add(st, runs, by, now_iso())
        self.hub.write_json("runs.json", st)
        return out

    def ask(self, question):
        s = self._ensure()
        return processmod.ask(question, s["G"].nodes, s["G"].edge_list(), self.claims(), self.timeline(), self.ledger(), self.tasks(), s["findings"])

    def export_bundle(self):
        s = self._ensure()
        return {"exported_at": now_iso(), "project": self.project(), "graph": self._graph_doc(), "events": self.events(),
                "findings": s["findings"], "alarms": s["alarms"], "checkpoints": self.checkpoints(), "triage": self.triage()}
