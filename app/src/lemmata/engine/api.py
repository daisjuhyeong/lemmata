"""Engine facade: the only module server.py and cli.py import (data-model 13)."""
import copy
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import alarms as alarmsmod
from . import analyze as analyzemod
from . import checks as checksmod
from . import claims as claimsmod
from . import experiments as expmod
from . import notation as notationmod
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
from . import triage as triagemod
from . import understand as undmod
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
    def create_checkpoint(self, note="", at=None, created_at=None, cp_id=None):
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
        if undmod.load(self.hub)["confirmed"]:
            E = self._exp_doc()
            ext = bool(E.get("extends"))
            vs = E["extends"]["base"]["name"] if ext else "the best other method"
            for sec in E["sections"]:
                if sec.get("claim_id"):
                    meta[sec["claim_id"]] = {"scope": {"extension": "new", "base": "original"}.get(sec.get("scope")), "ref": sec["label"]}
                    own = ext and sec.get("scope") != "base"      # re-checking the original paper's claim: its method against the others, as the paper did
                    tests[sec["claim_id"]] = [self._outcome(x, own, vs if own else "the best other method") for x in sec["experiments"]]
        claimsmod.restage(doc, claimsmod.load(self.hub), tests, meta)
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
        key = (id(s["G"]), s["scanned_at"]) + tuple(stamp(n) for n in ("map.json", "experiments.json", "claims.json", "runs.json"))
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
        if m and (detail is None or str(detail).startswith("map:")):
            return trackmod.build(m, s["G"], s["trees"], s["infos"], s["events"], s["alarms"], s["findings"], self.ledger(),
                                  expmod.load(self.hub), self._github(), detail, "proposed" if d["proposed"] else "confirmed")
        doc = expmod.build(s["G"], s["trees"], s["infos"], s["events"], s["alarms"], s["findings"], self._claims_base(), self.ledger(),
                           expmod.load(self.hub), self._github(), detail)
        if detail is None:
            doc["map"] = {"state": "proposed" if d["proposed"] else "none"}
        return doc

    def experiments(self):
        E = self._exp_doc()
        by = {c["id"]: c for c in self.claims()["claims"]}
        for sec in E["sections"]:      # each section is a claim: show where that claim stands
            c = by.get(sec.get("claim_id") or sec["id"])
            if c:
                sec.update(stage=c["stage"], stage_by=c["stage_by"], stage_why=c["stage_why"], short=c["short"])
        return E

    def experiment(self, exp_id):
        return self._exp(exp_id)

    def set_experiment(self, exp_id, ours=None, metric=None, lower=None, measure=None):
        s = self._ensure()
        st = expmod.load(self.hub)
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
    def review(self, days=30, now=None):
        return reviewmod.build(self.experiments(), reviewmod.load(self.hub), days, now)

    def set_review(self, hoped=None, question=None, resolve=None, mine=None, days=30):
        E = self.experiments()
        st = reviewmod.load(self.hub)
        reviewmod.decide(st, {s["id"] for s in E["sections"]}, hoped, question, resolve, mine, now_iso())
        self.hub.write_json("review.json", st)
        return reviewmod.build(E, st, days)

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
        return plansmod.view(plansmod.load(self.hub))

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
        return {"notes": notes, "plans": plansmod.view(st)["plans"]}

    def set_plan(self, plan_id, state=None, prompt=None):
        st = plansmod.load(self.hub)
        plansmod.decide(st, plan_id, state, prompt, now_iso())
        self.hub.write_json("plans.json", st)
        return plansmod.view(st)

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
        return self._propose(undmod.draft(s["G"], s["trees"], s["infos"], s["events"], self.claims()), "rules")

    def edit_map(self, patch):
        d = undmod.load(self.hub)
        return self._propose(undmod.edit(d["proposed"] or d["confirmed"], patch), d.get("proposed_by") if d["proposed"] else "you")

    def discard_map(self):
        d = undmod.load(self.hub)
        d.update(proposed=None, report=[])
        self.hub.write_json("map.json", d)
        return self.project_map()

    def confirm_map(self):
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
        d.update(confirmed=m, proposed=None, report=report, confirmed_at=now_iso())
        self.hub.write_json("map.json", d)
        return self.project_map()

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
        return runsmod.view(runsmod.load(self.hub), s["G"].nodes, s["events"], self._roles(), limit)

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
