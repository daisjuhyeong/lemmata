"""Engine facade: the only module server.py and cli.py import (data-model 13)."""
import copy
import time
from datetime import datetime
from pathlib import Path

from . import alarms as alarmsmod
from . import analyze as analyzemod
from . import checks as checksmod
from . import graph as graphmod
from . import history as historymod
from . import manifest as manifestmod
from . import refs as refsmod
from . import store
from . import tree as treemod
from . import triage as triagemod
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
            t = treemod.WorkTree(r["abs_path"], r["id"])
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
            "capabilities": {"paper": s["G"].paper is not None, "online_lookup": self.online, "ask_ai": False},
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

    def export_bundle(self):
        s = self._ensure()
        return {"exported_at": now_iso(), "project": self.project(), "graph": self._graph_doc(), "events": self.events(),
                "findings": s["findings"], "alarms": s["alarms"], "checkpoints": self.checkpoints(), "triage": self.triage()}
