"""Runs logged outside GitHub. Run: PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_runs.py'"""
import http.client
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))

from lemmata import mcp  # noqa: E402
from lemmata.engine import runs as runsmod  # noqa: E402
from lemmata.engine.api import Engine  # noqa: E402
from lemmata.engine.errors import BadRequest  # noqa: E402
from lemmata.samples.make_sample import build  # noqa: E402
from lemmata.server import bind  # noqa: E402


def run(i=1, **kw):
    r = {"run_id": "2026-11-11T21-04-%02d_a3f9" % i, "source": "terminal", "command": "python train.py --seed %d" % i, "cwd": "/home/u/proj",
         "host": "gpu-03", "git_sha": "9c1e2ab", "dirty": True, "diff_hash": "sha256:" + "ab" * 32,
         "configs": [{"path": "configs/default.yaml", "hash": "sha256:" + "cd" * 32}], "metrics": {"f1": 0.851, "auroc": 0.912},
         "artifacts": [{"path": "outputs/s1/metrics.json", "hash": None}], "started": "2026-11-11T21:04:%02d+09:00" % i,
         "ended": "2026-11-11T21:09:%02d+09:00" % i, "exit_code": 0}
    r.update(kw)
    return r


class StoreTest(unittest.TestCase):
    def test_clean_keeps_known_fields_only(self):
        c = runsmod.clean(run(extra="x", metrics={"f1": 0.9, "bad": "text", "nan": float("nan"), "flag": True}))
        self.assertNotIn("extra", c)
        self.assertEqual(c["metrics"], {"f1": 0.9})

    def test_clean_rejects_bad_input(self):
        for bad in (run(run_id="../x"), run(source="web"), run(git_sha="zzz"), run(dirty="yes"), run(exit_code="0"), run(started="yesterday"),
                    run(command=None, artifacts=[]), run(artifacts=[{"hash": "ab" * 8}]), run(diff_hash="not-hex"), "text"):
            with self.assertRaises(BadRequest):
                runsmod.clean(bad)

    def test_add_upserts_and_keeps_numbers(self):
        st = {"runs": []}
        self.assertEqual(runsmod.add(st, [run(1), run(2)], "ui:d1", "t0"), {"added": 2, "updated": 0, "total": 2})
        out = runsmod.add(st, [run(1, metrics={}, exit_code=1)], "ui:d1", "t1")
        self.assertEqual(out, {"added": 0, "updated": 1, "total": 2})
        self.assertEqual(st["runs"][0]["metrics"], {"f1": 0.851, "auroc": 0.912})     # a later report without numbers keeps the earlier ones
        self.assertEqual(st["runs"][0]["received"], "t0")
        self.assertEqual(st["runs"][0]["exit_code"], 1)

    def test_add_is_all_or_nothing(self):
        st = {"runs": []}
        with self.assertRaises(BadRequest):
            runsmod.add(st, [run(1), run(2, source="web")], None, "t0")
        self.assertEqual(st["runs"], [])
        with self.assertRaises(BadRequest):
            runsmod.add(st, [run(i % 60, run_id="2026-11-11T21-04-00_%04d" % i) for i in range(runsmod.MAX_BATCH + 1)], None, "t0")
        with self.assertRaises(BadRequest):
            runsmod.add(st, [], None, "t0")


class EngineRunsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="lemmata-runs-")
        cls.root = Path(cls.tmp) / "sample"
        build(cls.root)
        cls.eng = Engine(cls.root)
        cls.eng.scan()
        cls.srv = bind(cls.eng, port=18795)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def j(self, method, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        data = json.dumps(body).encode() if body is not None else None
        c.request(method, path, body=data, headers={"Host": "127.0.0.1:%d" % self.port, "Content-Type": "application/json"})
        r = c.getresponse()
        out = json.loads(r.read())
        c.close()
        return r.status, out

    def test_1_empty(self):
        s, d = self.j("GET", "/api/runs")
        self.assertEqual(s, 200)
        self.assertEqual(d["counts"]["total"], 0)

    def test_2_post_then_list(self):
        head = next(e["rev"] for e in self.eng.events()["events"] if e.get("kind") == "commit" and e.get("rev") and e["repo"] == "code")
        result = next(n["loc"]["path"] for n in self.eng.graph()["nodes"] if n["kind"] == "result")
        s, d = self.j("POST", "/api/runs", {"runs": [run(1), run(2, git_sha=head[:10], dirty=False, artifacts=[{"path": result}]),
                                                     run(3, exit_code=2, metrics={})]})
        self.assertEqual((s, d["added"], d["total"]), (201, 3, 3))
        s, d = self.j("GET", "/api/runs")
        by = {r["run_id"][-7:-5]: r for r in d["runs"]}
        self.assertEqual([r["run_id"][-7:-5] for r in d["runs"]], ["03", "02", "01"])       # newest first
        self.assertEqual((by["01"]["state"], by["02"]["state"], by["03"]["state"]), ("uncommitted", "in github", "failed"))
        self.assertTrue(by["02"]["in_github"])
        self.assertEqual([t["path"] for t in by["02"]["tracked"]], [result])                # tied to a result file the hub tracks
        self.assertEqual(by["01"]["tracked"], [])
        self.assertEqual(d["counts"], {"total": 3, "failed": 1, "uncommitted": 1, "not_in_github": 0, "in_github": 1, "with_numbers": 2})
        self.assertTrue((self.root / ".lemmata" / "runs.json").is_file())

    def test_3_bad_post_changes_nothing(self):
        s, d = self.j("POST", "/api/runs", {"runs": [run(9, source="web")]})
        self.assertEqual(s, 400)
        self.assertEqual(self.j("POST", "/api/runs", {})[0], 400)
        self.assertEqual(self.j("GET", "/api/runs")[1]["counts"]["total"], 3)

    def test_4_digest_mentions_runs(self):
        d = self.eng.digest(7)
        self.assertEqual("runs" in d["numbers"], "logged from the editor" in d["text"])
        self.assertTrue(runsmod.newer("2026-11-11T01:00:00+09:00", "2026-11-10T16:00:00+00:00"))     # same instant or later, across time zones
        self.assertFalse(runsmod.newer("2026-11-11T01:00:00+09:00", "2026-11-10T17:00:00+00:00"))
        st = runsmod.load(self.eng.hub)
        rows = runsmod.view(st, {}, [], {})["runs"]       # no commit history given: run 02 counts as not in GitHub too
        line = runsmod.digest_line(rows, "2026-11-10T00:00:00+09:00")
        self.assertEqual(line, "• 3 runs logged from the editor or the coding agent, 2 on code that is not in GitHub, 1 failed")
        self.assertIsNone(runsmod.digest_line(rows, "2027-01-01T00:00:00+09:00"))

    def test_5_mcp_tools(self):
        ctx = mcp.LocalCtx(self.root)

        def call(name, args):
            st, out = mcp.handle(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}), ctx)
            return json.loads(out)["result"]
        pid = ctx.list_projects()[0]["id"]
        r = call("runs", {"project": pid})
        self.assertFalse(r["isError"])
        self.assertIn("3 runs logged", r["content"][0]["text"])
        self.assertIn("<user-file-quote>", r["content"][0]["text"])
        self.assertEqual(len(call("runs", {"project": pid, "contains": "seed 2"})["structuredContent"]["runs"]), 1)
        self.assertTrue(call("runs", {"project": pid, "limit": 0})["isError"])
        r = call("log_run", {"project": pid, "run": run(4, source="terminal")})
        self.assertFalse(r["isError"])
        self.assertEqual(r["structuredContent"]["total"], 4)
        logged = next(x for x in call("runs", {"project": pid})["structuredContent"]["runs"] if x["run_id"].endswith("04_a3f9"))
        self.assertEqual((logged["source"], logged["by"]), ("agent", "mcp:local"))            # the tool sets the source itself
        self.assertTrue(call("log_run", {"project": pid, "run": {"run_id": "x"}})["isError"])


if __name__ == "__main__":
    unittest.main()
