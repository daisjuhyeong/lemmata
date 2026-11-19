"""The bench (S35, ADR-011): what the VS Code extension shows. Standard library only."""
import datetime
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_map as tm  # noqa: E402
from lemmata.engine import bench as B  # noqa: E402
from lemmata.engine.api import Engine  # noqa: E402
from lemmata.engine.errors import NotFound  # noqa: E402
from lemmata.server import bind  # noqa: E402

PAPER_KINDS = {"differs", "untraced", "bold", "finding", "number", "number_missing", "number_gap", "feedback", "claim", "map", "numbers", "changes", "untested", "no_claim", "sync"}


def walk(rows):
    for r in rows:
        yield r
        yield from walk(r.get("kids") or [])


class BenchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "p")
        os.makedirs(self.root)
        tm.make_project(self.root)
        self.e = Engine(self.root)
        self.e.scan()
        self.e.propose_map(tm.agent)
        self.e.confirm_map()
        self.code = os.path.join(self.root, "code")
        base = datetime.datetime.now().astimezone().replace(hour=9, minute=0, second=0, microsecond=0)
        self.today = base.isoformat()[:10]
        self.at = lambda m: (base + datetime.timedelta(minutes=m)).isoformat()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_(self, n, minute, seed="3", fp=None, dataset="Covtype", **kw):
        d = dict(run_id="run-%03d" % n, source="terminal", command="python scripts/run_main.py --dataset %s --method MCD --seed %s" % (dataset, seed), cwd=self.code, host="srv",
                 git_sha="a" * 40, dirty=False, started=self.at(minute), ended=self.at(minute + 5), exit_code=0,
                 artifacts=[{"path": "results/main/%s,y_MCD_seed%s.csv" % (dataset, seed)}], metrics={"fp": fp} if fp is not None else {})
        d.update(kw)
        return d

    def test_runs_are_tied_to_their_experiment_and_compared_like_with_like(self):
        self.e.add_runs([
            self.run_(1, 0, fp=31.2),
            self.run_(2, 10, fp=30.0),                                   # the same cell again: comparable
            self.run_(3, 20, fp=44.0, dataset="Weather"),                # another dataset: nothing to compare with
            self.run_(4, 30, seed="4", fp=29.0),                         # another seed: nothing to compare with
            dict(run_id="run-005", source="terminal", command="python scripts/plot.py", cwd=self.code, host="srv", artifacts=[{"path": "figs/a.png"}],
                 started=self.at(40), ended=self.at(41), exit_code=0),   # writes no result file of any experiment
            dict(run_id="run-006", source="terminal", command="nvidia-smi", cwd=self.code, host="srv", started=self.at(50), ended=self.at(50), exit_code=0),
        ], "test")
        d = self.e.bench(self.today)
        self.assertEqual((d["schema"], d["version"]), (B.SCHEMA, B.VERSION))
        r = d["runs"]
        self.assertEqual(r["run-001"]["x"], "map:main")
        self.assertEqual(r["run-001"]["name"], "Main comparison")
        self.assertEqual(r["run-001"]["fields"], {"dataset": ["Covtype"], "method": ["MCD"], "seed": ["3"]})
        self.assertEqual(r["run-001"]["how"], "wrote")
        self.assertIsNone(r["run-001"]["prev"])
        self.assertEqual(r["run-001"]["line"], "fp 31.2")
        self.assertEqual(r["run-002"]["prev"]["id"], "run-001")
        self.assertEqual(r["run-002"]["line"], "fp 30, was 31.2 (lower is better)")      # the direction is shown, never a verdict
        self.assertIsNone(r["run-003"]["prev"])
        self.assertIsNone(r["run-004"]["prev"])
        self.assertNotIn("run-005", r)          # belongs to no experiment: the extension shows it as not attached
        self.assertNotIn("run-006", r)
        self.assertEqual(d["counts"]["unattached"], 1)                 # the plot; a bare command (nvidia-smi) is not an experiment
        ids = [x["id"] for x in d["elsewhere"]]
        self.assertIn("run-002", ids)
        self.assertNotIn("run-006", ids)
        row = next(x for x in d["elsewhere"] if x["id"] == "run-002")
        self.assertIn("Main comparison", row["description"])
        self.assertIn("was 31.2", row["description"])

    def test_experiments_carry_their_setup_one_line_each(self):
        self.e.add_runs([self.run_(1, 0, fp=31.2)], "test")
        d = self.e.bench(self.today)
        secs = d["experiments"]
        self.assertTrue(secs[0]["label"].startswith("C1 · "))
        x = next(r for r in walk(secs) if r["id"] == "map:main")
        self.assertEqual(x["label"], "Main comparison")
        self.assertEqual(x["site"], {"view": "experiments", "sel": "x:map:main"})
        self.assertEqual(x["tab"], {"view": "setup", "sel": "x:map:main"})
        self.assertIn("experiment_brief", x["copy"]["text"])
        self.assertIn('"x:map:main"', x["copy"]["text"])
        kid = {k["label"]: k for k in x["kids"]}
        self.assertEqual(kid["Measure"]["description"], "fp · lower is better")
        self.assertEqual(kid["Datasets"]["description"], "3 · Covtype, Electricity, Weather")
        self.assertEqual(kid["Methods"]["description"], "3 · ADWIN, DDM, MCD (ours)")
        self.assertEqual(kid["Runs per result"]["description"], "2")
        self.assertTrue(kid["Tests C1"]["description"].startswith("Is predictive uncertainty enough"))
        per = {k["label"]: k["description"] for k in kid["Result"]["kids"]}
        self.assertEqual(per["Electricity"], "ours 30 · best other 38 (DDM)")
        self.assertEqual(kid["Files"]["open"]["repo"], "code")
        self.assertTrue(kid["Files"]["open"]["path"].startswith("results/main/"))
        self.assertEqual(kid["Runs"]["kids"][0]["run"], "run-001")
        self.assertEqual([p["id"] for p in d["pick"]][:2], ["map:main", "map:tune"])
        for r in walk(secs):                              # every row can be drawn: an id and a label, nothing longer than a line
            self.assertTrue(r["id"] and r["label"] and len(r["label"]) <= 120 and len(r.get("description") or "") <= 160)
        self.assertEqual(len({r["id"] for r in walk(secs)}), len(list(walk(secs))))     # ids are unique: the tree keeps its place on refresh

    def test_to_run_holds_only_what_is_about_running_something(self):
        d = self.e.bench(self.today)
        kinds = {r["kind"] for r in walk(d["to_run"]) if r.get("kind")}
        self.assertTrue(kinds)
        self.assertFalse(kinds & PAPER_KINDS)             # "paper and results disagree" is on the to-do list, and stays on the website
        self.assertTrue(kinds <= set(B.TO_RUN))
        todo = {i["kind"] for i in self.e.todo(self.today)["items"]}
        self.assertIn("differs", todo)
        grp = next(r for r in d["to_run"] if r["id"] == "x|map:abl")
        seeds = next(k for k in grp["kids"] if k["kind"] == "seeds")
        self.assertEqual(seeds["snooze"], "seeds:map:abl")
        self.assertIn("experiment_brief", seeds["copy"]["text"])
        self.assertEqual(d["counts"]["to_run"], sum(1 for r in walk(d["to_run"]) if r.get("kind")))
        # snooze: the item leaves the bench and the hub's own list
        later = (datetime.date.fromisoformat(self.today) + datetime.timedelta(days=7)).isoformat()
        self.e.snooze_todo("seeds:map:abl", later)
        d2 = self.e.bench(self.today)
        self.assertNotIn("seeds:map:abl", [r["id"] for r in walk(d2["to_run"])])
        self.assertNotIn("seeds:map:abl", [i["key"] for i in self.e.todo(self.today)["items"]])
        self.assertEqual(d2["counts"]["snoozed"], 1)

    def test_a_run_can_be_attached_by_hand_and_that_counts_at_once(self):
        self.e.add_runs([self.run_(1, 0, fp=31.2),
                         dict(run_id="run-005", source="terminal", command="python scripts/plot.py", cwd=self.code, host="srv", artifacts=[{"path": "figs/a.png"}],
                              metrics={"fp": 36.0}, started=self.at(40), ended=self.at(41), exit_code=0)], "test")
        with self.assertRaises(NotFound):
            self.e.attach_run("nope", "map:abl")
        with self.assertRaises(NotFound):
            self.e.attach_run("run-005", "map:nope")
        d = self.e.attach_run("run-005", "map:abl")
        self.assertEqual((d["runs"]["run-005"]["x"], d["runs"]["run-005"]["how"]), ("map:abl", "attached"))
        self.assertEqual(d["counts"]["unattached"], 0)
        c = next(x for x in self.e.setup()["experiments"] if x["id"] == "map:abl")["context"]       # Setup on the website shows the same
        self.assertEqual([(r["id"], r["how"]) for r in c["runs"]], [("run-005", "attached")])
        # attaching a run that the rules gave to one experiment moves it: it counts for the chosen experiment only
        d = self.e.attach_run("run-001", "map:tune")
        self.assertEqual(d["runs"]["run-001"]["x"], "map:tune")
        main = next(x for x in self.e.setup()["experiments"] if x["id"] == "map:main")["context"]
        self.assertEqual(main["runs"], [])
        d = self.e.attach_run("run-001", None)             # taking it back returns the run to the rules
        self.assertEqual((d["runs"]["run-001"]["x"], d["runs"]["run-001"]["how"]), ("map:main", "wrote"))
        d = self.e.attach_run("run-005", "")
        self.assertNotIn("run-005", d["runs"])

    def test_a_planned_experiment_carries_its_run_prompt(self):
        good = {"kind": "seeds", "title": "Two more seeds", "why": "Only two runs per method.",
                "files": [{"path": "train.py", "quote": 'add_argument("--dataset")'}],
                "goal": "Check the fp gap holds with four seeds.",
                "decision": {"supports": "MCD mean fp below ADWIN on all 3 datasets by more than 1 std", "against": "not below on 2 or more datasets"},
                "context": [{"path": "train.py", "role": "entry point"}], "protected": ["detect.py", "results/main/"], "steps": ["Add --seed to train.py."],
                "smoke": "python train.py --dataset Electricity --seed 3", "run": ["python train.py --dataset Electricity --seed 3"],
                "results_to": "results/main/{dataset},y_{method}_seed{seed}.csv", "budget": "6 runs", "baseline_check": "ADWIN fp 43.5 within 2"}
        r = self.e.propose_plans("x:map:main", [good])
        self.assertEqual([p["title"] for p in r["plans"]], ["Two more seeds"], r["notes"])
        pid = r["plans"][0]["id"]
        d = self.e.bench(self.today)
        row = next(x for x in walk(d["to_run"]) if x.get("kind") == "plan")
        self.assertEqual((row["label"], row["x"], row["snooze"]), ("Two more seeds", "map:main", "plan:" + pid))
        self.assertIn('<experiment id="%s"' % pid, row["copy"]["text"])        # the plan's own prompt, not a generic one
        self.assertIn(row["id"], [k["id"] for k in next(g for g in d["to_run"] if g["id"] == "x|map:main")["kids"]])
        self.e.set_plan(pid, state="copied")               # handed to the agent: it stays, with its prompt, until it is dropped
        row = next(x for x in walk(self.e.bench(self.today)["to_run"]) if x.get("kind") == "plan")
        self.assertTrue(row["description"].startswith("prompt copied"))
        self.assertIn("<experiment", row["copy"]["text"])
        self.e.set_plan(pid, state="dropped")
        self.assertFalse([x for x in walk(self.e.bench(self.today)["to_run"]) if x.get("kind") == "plan"])

    def test_num(self):
        self.assertEqual([B.num(v) for v in (30.0, 31.25, 0.123456, 1234567.0, 5, 1e-7)], ["30", "31.25", "0.1235", "1234567", "5", "1e-07"])


class BenchRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        root = os.path.join(cls.tmp, "p")
        os.makedirs(root)
        tm.make_project(root)
        cls.e = Engine(root)
        cls.e.scan()
        cls.e.propose_map(tm.agent)
        cls.e.confirm_map()
        cls.e.add_runs([dict(run_id="run-001", source="terminal", command="python scripts/plot.py", cwd=root, started="2026-11-20T09:00:00+09:00", ended="2026-11-20T09:01:00+09:00",
                             exit_code=0, artifacts=[{"path": "figs/a.png"}])], "test")
        cls.srv = bind(cls.e, port=0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def req(self, method, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        h = {"Host": "127.0.0.1:%d" % self.port}
        if body is not None:
            h["Content-Type"] = "application/json"
        c.request(method, path, body=json.dumps(body).encode() if body is not None else None, headers=h)
        r = c.getresponse()
        out = json.loads(r.read() or b"null")
        c.close()
        return r.status, out

    def test_get_and_attach(self):
        s, d = self.req("GET", "/api/bench")
        self.assertEqual((s, d["schema"]), (200, B.SCHEMA))
        self.assertNotIn("run-001", d["runs"])
        s, d = self.req("POST", "/api/bench", {"action": "attach", "run": "run-001", "experiment": "map:abl"})
        self.assertEqual((s, d["runs"]["run-001"]["x"]), (200, "map:abl"))
        s, d = self.req("POST", "/api/bench", {"action": "attach", "run": "run-001", "experiment": "map:nope"})
        self.assertEqual(s, 404)
        s, d = self.req("POST", "/api/bench", {"action": "erase", "run": "run-001"})
        self.assertEqual(s, 400)


class ExtensionBuildTest(unittest.TestCase):
    def test_the_hub_offers_only_a_packaged_extension_that_matches_the_version(self):
        from lemmata.hub.routes import extension_build
        d = tempfile.mkdtemp()
        try:
            self.assertIsNone(extension_build(d))
            Path(d, "package.json").write_text(json.dumps({"version": "0.8.0"}))
            self.assertIsNone(extension_build(d))                       # source at 0.8.0 but no packaged file: nothing to offer
            Path(d, "lemmata-0.7.0.vsix").write_bytes(b"old")
            self.assertIsNone(extension_build(d))
            Path(d, "lemmata-0.8.0.vsix").write_bytes(b"zip")
            b = extension_build(d)
            self.assertEqual((b["version"], b["file"].name), ("0.8.0", "lemmata-0.8.0.vsix"))
            Path(d, "package.json").write_text(json.dumps({"version": "../x"}))
            self.assertIsNone(extension_build(d))
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
