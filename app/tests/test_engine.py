"""Engine tests (stdlib unittest). Run: PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_engine*.py'"""
import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))

from lemmata.engine.api import Engine  # noqa: E402
from lemmata.engine.errors import BadRequest, NotFound  # noqa: E402

_spec = importlib.util.spec_from_file_location("make_sample", str(APP / "samples" / "make_sample.py"))
make_sample = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_sample)

REAL_REPO = Path("/home/claude/alarm-analyzer-eval")
CFG = "file:code/configs/default.yaml"
PL1 = "tex:sec:setup|value_match|" + CFG
PL2 = "tex:app:hparams|value_match|" + CFG
BANNED = ("wrong", "fake", "fabricated", "mistake", "error by", "cheat")

# golden findings: id -> (file, substring that must be on the evidence line)
GOLDEN = {
    "reference_unmatched/smith2021ghost": ("refs.bib", "smith2021ghost"),
    "main_appendix_mismatch/learning_rate": ("main.tex", "learning rate"),
    "main_appendix_mismatch/batch_size": ("main.tex", "batch size"),
    "uncited_reference/unused2019": ("refs.bib", "unused2019"),
    "unreferenced_float/fig:arch": ("main.tex", "fig:arch"),
    "unreferenced_float/tab:ablation": ("main.tex", "tab:ablation"),
    "undefined_ref/fig:missing": ("main.tex", "fig:missing"),
    "undefined_cite/nobody2020": ("main.tex", "nobody2020"),
    "untraced_number/tex:sec:results#92.4": ("main.tex", "92.4"),
    "figure_without_provenance/tex:fig:qual": ("main.tex", "fig:qual"),
}


def fresh_sample():
    d = tempfile.mkdtemp(prefix="lemmata-test-")
    make_sample.build(d)
    return d


def head(repo):
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


class SampleCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = fresh_sample()
        cls.eng = Engine(cls.dir)
        cls.status = cls.eng.scan()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)


class TestGolden(SampleCase):
    def test_counts(self):
        c = self.status["counts"]
        self.assertEqual((c["findings"], c["proposed"], c["alarm_groups"]), (10, 2, 2))

    def test_findings_exact(self):
        f = self.eng.findings()
        self.assertEqual({x["id"] for x in f["findings"]}, set(GOLDEN))
        self.assertEqual([c["check"] for c in f["checks"]], [
            "reference_unmatched", "main_appendix_mismatch", "uncited_reference", "unreferenced_float", "undefined_ref",
            "undefined_cite", "untraced_number", "figure_without_provenance"])
        self.assertTrue(all(c["status"] == "ran" for c in f["checks"]))

    def test_evidence_matches_source_lines(self):
        for fd in self.eng.findings()["findings"]:
            self.assertGreaterEqual(len(fd["evidence"]), 1, fd["id"])
            for ev in fd["evidence"]:
                repo = {"paper": "paper", "code": "code"}[ev["repo"]]
                lines = (Path(self.dir) / repo / ev["path"]).read_text(encoding="utf-8").split("\n")
                self.assertEqual(lines[ev["line"] - 1].rstrip()[:300], ev["text"], fd["id"])
            f, sub = GOLDEN[fd["id"]]
            self.assertTrue(any(e["path"] == f and sub in e["text"] for e in fd["evidence"]), fd["id"])

    def test_mismatch_values(self):
        by = {x["id"]: x for x in self.eng.findings()["findings"]}
        d = by["main_appendix_mismatch/learning_rate"]["details"]
        self.assertEqual((d["main_value"], d["appendix_value"]), ("3e-4", "1e-3"))
        d = by["main_appendix_mismatch/batch_size"]["details"]
        self.assertEqual((d["main_value"], d["appendix_value"]), ("64", "128"))
        self.assertEqual({e["path"] for e in by["main_appendix_mismatch/learning_rate"]["evidence"]}, {"main.tex", "appendix.tex"})

    def test_negative_controls(self):
        ids = [x["id"] for x in self.eng.findings()["findings"]]
        text = " ".join(ids)
        for neg in ("vaswani2017attention", "devlin2019bert", "fig:curve", "tab:main", "tab:data", "sec:intro", "optimizer", "#0.871", "#0.912"):
            self.assertNotIn(neg, text, neg)

    def test_wording(self):
        for fd in self.eng.findings()["findings"]:
            for w in BANNED:
                self.assertNotIn(w, (fd["message"] + fd["title"]).lower())
        src = (APP / "src/lemmata/engine/checks.py").read_text(encoding="utf-8").lower()
        for w in BANNED:
            self.assertNotIn(w, src)

    def test_proposed_links(self):
        g = self.eng.graph()
        prop = {e["id"] for e in g["edges"] if e["status"] == "proposed"}
        self.assertEqual(prop, {PL1, PL2})
        self.assertTrue(all(not e["propagates"] for e in g["edges"] if e["status"] == "proposed"))

    def test_node_ids_and_layers(self):
        ids = {n["id"]: n for n in self.eng.graph()["nodes"]}
        for nid in (CFG, "run:code/train_main", "file:code/results/table2.csv", "tex:tab:main", "tex:app:hparams", "tex:sec:setup", "thesis", "rq:RQ1", "ref:vaswani2017attention"):
            self.assertIn(nid, ids)
        self.assertEqual(ids["tex:tab:main"]["name"], "Table 2")
        self.assertEqual(ids["tex:app:hparams"]["name"], "App. B Hyperparameters")
        self.assertEqual(ids["tex:sec:setup"]["name"], "§4 Experimental Setup")
        self.assertEqual([n["layer"] for n in ids.values() if n["id"] == "thesis"], [0])

    def test_alarm_state0(self):
        a = self.eng.alarms()
        self.assertEqual(a["checkpoint"]["id"], "cp1")
        self.assertEqual([g["display"] for g in a["groups"]], ["A1", "A2"])
        a1, a2 = a["groups"]
        self.assertEqual(a1["cause"]["repo"], "code")
        self.assertEqual(a1["cause"]["subject"], "change learning rate 3e-4 to 1e-3")
        self.assertEqual(a1["cause"]["files"], ["configs/default.yaml"])
        self.assertEqual([c["node_id"] for c in a1["changed"]], [CFG])
        self.assertEqual([(d["node_id"], d["depth"], d["output_identical"]) for d in a1["downstream"]],
                         [("run:code/train_main", 1, None), ("file:code/results/table2.csv", 2, True), ("tex:tab:main", 3, None)])
        self.assertEqual(a1["downstream"][0]["via"], "run:code/train_main|reads|" + CFG)
        self.assertEqual(a2["cause"]["repo"], "paper")
        self.assertEqual([c["node_id"] for c in a2["changed"]], ["tex:app:hparams"])
        self.assertEqual(a2["downstream"], [])
        self.assertEqual(a["summary"], {"groups": 2, "changed": 2, "removed": 0, "downstream": 3, "flagged_nodes": 5})
        flagged = {c["node_id"] for g in a["groups"] for c in g["changed"]} | {d["node_id"] for g in a["groups"] for d in g["downstream"]}
        self.assertFalse(any("eval.py" in n or "plot_curve" in n or "fig:curve" in n or "metrics" in n for n in flagged))

    def test_eval_edit_revert_is_hash_neutral(self):
        code = Path(self.dir) / "code"
        a = subprocess.run(["git", "-C", str(code), "rev-parse", "cp1:eval.py", "HEAD:eval.py"], capture_output=True, text=True).stdout.split()
        self.assertEqual(a[0], a[1])
        evs = {e["subject"]: e for e in self.eng.events()["events"] if e["kind"] == "commit" and e["repo"] == "code"}
        self.assertEqual(evs["tmp: edit comment in eval.py"]["changed_nodes"], ["file:code/eval.py"])
        self.assertEqual(evs["revert eval.py"]["changed_nodes"], ["file:code/eval.py"])
        self.assertEqual(self.eng.events(after_checkpoint=True)["events"][0]["subject"], "change learning rate 3e-4 to 1e-3")
        self.assertEqual([e["kind"] for e in self.eng.events()["events"] if e["kind"] in ("worktree", "diverged", "snapshot")], [])

    def test_analyze(self):
        a = self.eng.analyze("ev:commit:code:" + self.eng.alarms()["groups"][0]["id"].split(":")[-1], "tex:tab:main")
        self.assertEqual(a["chain"]["nodes"], [CFG, "run:code/train_main", "file:code/results/table2.csv", "tex:tab:main"])
        d = a["diffs"][0]
        self.assertIn("-learning_rate: 3.0e-4", d["unified"])
        self.assertIn("+learning_rate: 1.0e-3", d["unified"])
        self.assertIn("byte-identical", a["explanation"])
        self.assertFalse(a["ai"]["available"])
        with self.assertRaises(NotFound):
            self.eng.analyze("nope", "tex:tab:main")
        with self.assertRaises(NotFound):
            self.eng.analyze(self.eng.alarms()["groups"][1]["id"], "tex:tab:main")


class TestMutations(unittest.TestCase):
    def setUp(self):
        self.dir = fresh_sample()
        self.eng = Engine(self.dir)
        self.eng.scan()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def down(self, alarms):
        return [d["node_id"] for d in alarms["groups"][0]["downstream"]]

    def test_link_decisions_recompute(self):
        r = self.eng.decide_link(PL2, "approved")
        self.assertEqual(r["edge"]["status"], "approved")
        self.assertTrue(r["edge"]["propagates"])
        self.assertEqual(sorted(self.down(r["alarms"])), sorted(["run:code/train_main", "file:code/results/table2.csv", "tex:tab:main", "tex:app:hparams"]))
        self.assertEqual(r["alarms"]["groups"][1]["downstream"], [])
        r = self.eng.decide_link(PL1, "approved")
        self.assertIn("tex:sec:setup", self.down(r["alarms"]))
        self.assertEqual(len(self.down(r["alarms"])), 5)
        r = self.eng.decide_link(PL1, "rejected")
        self.assertNotIn("tex:sec:setup", self.down(r["alarms"]))
        self.assertEqual(self.eng.project()["counts"]["proposed"], 0)
        # persisted: a new engine (rescan) keeps the decisions and does not re-propose a rejected link
        e2 = Engine(self.dir)
        e2.scan()
        st = {e["id"]: e["status"] for e in e2.graph()["edges"] if e["kind"] == "value_match"}
        self.assertEqual(st, {PL1: "rejected", PL2: "approved"})
        self.assertEqual(e2.project()["counts"]["proposed"], 0)
        r = self.eng.decide_link(PL1, "proposed")
        self.assertEqual(r["edge"]["status"], "proposed")

    def test_bad_decisions(self):
        with self.assertRaises(BadRequest):
            self.eng.decide_link("tex:tab:main|traces_to|file:code/results/table2.csv", "approved")
        with self.assertRaises(NotFound):
            self.eng.decide_link("nope|value_match|nope", "approved")
        with self.assertRaises(BadRequest):
            self.eng.decide_link(PL1, "maybe")

    def test_new_checkpoint_zeroes_alarms_and_keeps_findings(self):
        before = self.eng.findings()
        r = self.eng.create_checkpoint("fresh")
        self.assertEqual(r["alarms"]["groups"], [])
        self.assertEqual(r["checkpoint"]["id"], "cp2")
        self.assertTrue(r["checkpoint"]["active"])
        self.assertEqual(self.eng.findings(), before)
        cps = self.eng.checkpoints()
        self.assertEqual([c["id"] for c in cps["checkpoints"]], ["cp2", "cp1"])
        self.assertEqual(cps["active"], "cp2")
        self.assertGreater(cps["checkpoints"][0]["node_count"], 20)

    def test_checkpoint_at_rev(self):
        r = self.eng.create_checkpoint("old", at={"code": "cp1"})
        self.assertEqual({g["cause"]["repo"] for g in r["alarms"]["groups"]}, {"code"})
        with self.assertRaises(BadRequest):
            self.eng.create_checkpoint("bad", at={"code": "no-such-rev"})
        with self.assertRaises(BadRequest):
            self.eng.create_checkpoint("bad", at={"nope": "HEAD"})

    def test_triage_persistence_and_outdated(self):
        r = self.eng.set_triage("node", "tex:tab:main", "needs_fixing", "rerun train with lr 1e-3")
        self.assertEqual(r["entry"]["effective_state"], "needs_fixing")
        self.eng.set_triage("finding", "uncited_reference/unused2019", "ignored", "")
        e2 = Engine(self.dir)
        e2.scan()
        t = e2.triage()["entries"]
        self.assertEqual(t["node:tex:tab:main"]["note"], "rerun train with lr 1e-3")
        self.assertFalse(t["node:tex:tab:main"]["outdated"])
        # content change -> back to unreviewed, history kept
        p = Path(self.dir) / "paper" / "main.tex"
        p.write_text(p.read_text(encoding="utf-8").replace("Main results on the benchmark", "Main results"), encoding="utf-8")
        e2.scan()
        t = e2.triage()["entries"]["node:tex:tab:main"]
        self.assertTrue(t["outdated"])
        self.assertEqual(t["effective_state"], "unreviewed")
        self.assertEqual(len(t["history"]), 1)
        # comment-only paper edits do not change hashes
        p.write_text(p.read_text(encoding="utf-8").replace("% source: code:results/table2.csv", "% source: code:results/table2.csv   "), encoding="utf-8")
        with self.assertRaises(NotFound):
            self.eng.set_triage("node", "nope", "reviewed")
        with self.assertRaises(BadRequest):
            self.eng.set_triage("node", "tex:tab:main", "bogus")

    def test_worktree_group(self):
        p = Path(self.dir) / "code" / "train.py"
        p.write_text(p.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
        self.eng.scan()
        a = self.eng.alarms()
        wt = [g for g in a["groups"] if g["cause"]["kind"] == "worktree"]
        self.assertEqual(len(wt), 1)
        self.assertEqual([c["node_id"] for c in wt[0]["changed"]], ["file:code/train.py"])
        self.assertIn("tex:tab:main", [d["node_id"] for d in wt[0]["downstream"]])
        # editing a file back to its checkpoint bytes raises nothing
        p.write_text(p.read_text(encoding="utf-8").replace("\n# edited\n", ""), encoding="utf-8")
        self.eng.scan()
        self.assertEqual([g for g in self.eng.alarms()["groups"] if g["cause"]["kind"] == "worktree"], [])

    def test_repos_stay_clean_and_hub_is_ignored(self):
        for r in ("paper", "code"):
            out = subprocess.run(["git", "-C", str(Path(self.dir) / r), "status", "--porcelain"], capture_output=True, text=True).stdout
            self.assertEqual(out, "")
        self.assertEqual((Path(self.dir) / ".lemmata" / ".gitignore").read_text(), "*\n")
        for name in ("graph", "events", "findings", "alarms", "checkpoints", "project"):
            self.assertTrue((Path(self.dir) / ".lemmata" / (name + ".json")).is_file(), name)

    def test_export_bundle(self):
        b = self.eng.export_bundle()
        for k in ("exported_at", "project", "graph", "events", "findings", "alarms", "checkpoints", "triage"):
            self.assertIn(k, b)


class TestDeterminism(unittest.TestCase):
    def test_two_builds_identical(self):
        a, b = fresh_sample(), fresh_sample()
        try:
            for r in ("paper", "code"):
                self.assertEqual(head(Path(a) / r), head(Path(b) / r))
            ea, eb = Engine(a), Engine(b)
            ea.scan()
            eb.scan()
            self.assertEqual(ea.findings(), eb.findings())
            strip = lambda al: {k: v for k, v in al.items() if k != "computed_at"}  # noqa: E731
            self.assertEqual(strip(ea.alarms()), strip(eb.alarms()))
            ga, gb = ea.graph(), eb.graph()
            self.assertEqual((ga["nodes"], ga["edges"]), (gb["nodes"], gb["edges"]))
            for r in ("paper", "code"):
                for rel in subprocess.run(["git", "-C", str(Path(a) / r), "ls-files"], capture_output=True, text=True).stdout.split():
                    self.assertEqual((Path(a) / r / rel).read_bytes(), (Path(b) / r / rel).read_bytes())
        finally:
            shutil.rmtree(a, ignore_errors=True)
            shutil.rmtree(b, ignore_errors=True)


class TestOffline(unittest.TestCase):
    def test_full_pipeline_with_sockets_blocked(self):
        d = fresh_sample()
        real = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo)

        def boom(*a, **k):
            raise AssertionError("network access attempted")
        socket.socket.connect = boom
        socket.socket.connect_ex = boom
        socket.create_connection = boom
        socket.getaddrinfo = boom
        try:
            e = Engine(d)  # online=False
            e.scan()
            e.alarms(), e.findings(), e.graph(), e.events()
            e.decide_link(PL2, "approved")
            e.analyze(e.alarms()["groups"][0]["id"], "tex:tab:main")
            e.set_triage("node", CFG, "reviewed", "ok")
            e.create_checkpoint("offline")
            e.export_bundle()
        finally:
            (socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo) = real
            shutil.rmtree(d, ignore_errors=True)


class TestCodeOnly(unittest.TestCase):
    def test_code_repo_alone(self):
        d = fresh_sample()
        try:
            c = Path(d) / "codeonly"
            shutil.copytree(Path(d) / "code", c)
            e = Engine(c)
            st = e.scan()
            self.assertFalse(st["capabilities"]["paper"])
            f = e.findings()
            self.assertTrue(all(x["status"] == "not_applicable" for x in f["checks"]))
            self.assertEqual(f["findings"], [])
            self.assertEqual(e.alarms()["groups"], [])
            self.assertIsNone(e.alarms()["checkpoint"])
            kinds = {n["kind"] for n in e.graph()["nodes"]}
            self.assertTrue({"code", "run", "config", "result"} <= kinds)
        finally:
            shutil.rmtree(d, ignore_errors=True)


@unittest.skipUnless(REAL_REPO.is_dir(), "real repo not available")
class TestRealRepoSmoke(unittest.TestCase):
    def test_scan_code_only(self):
        t = time.time()
        e = Engine(REAL_REPO)
        st = e.scan()
        self.assertLess(time.time() - t, 10)
        self.assertFalse(st["capabilities"]["paper"])
        g = e.graph()
        kinds = {}
        for n in g["nodes"]:
            kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
        self.assertGreater(kinds.get("code", 0), 100)
        self.assertEqual(kinds.get("item"), 16)
        ek = {}
        for x in g["edges"]:
            ek[x["kind"]] = ek.get(x["kind"], 0) + 1
        self.assertGreater(ek.get("imports", 0), 100)
        self.assertGreater(ek.get("generated_by", 0), 10)
        self.assertGreater(st["counts"]["events"], 100)
        self.assertTrue(all(c["status"] == "not_applicable" for c in e.findings()["checks"]))
        self.assertEqual(e.alarms()["groups"], [])
        flagged = [ev for ev in e.events()["events"] if ev["flags"]]
        self.assertTrue(any(f["flags"][0]["code"] == "message_claims_no_change" for f in flagged))
        out = subprocess.run(["git", "-C", str(REAL_REPO), "status", "--porcelain"], capture_output=True, text=True).stdout
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
