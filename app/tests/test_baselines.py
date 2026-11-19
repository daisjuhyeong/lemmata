"""S30 tests: the Baselines page (paper, PDF, code, idea and published numbers of every compared method).
Run: PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_baselines*.py'

Uses the method-paper project of test_map (MCD against ADWIN and DDM on three streams). Nothing here opens a link or
calls a model: cards are typed the way the researcher would, or proposed the way the researcher's own agent would."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))
sys.path.insert(0, str(APP / "tests"))

from lemmata.engine import baselines as bl  # noqa: E402
from lemmata.engine.api import Engine  # noqa: E402
from lemmata.engine.errors import BadRequest, NotFound  # noqa: E402
from lemmata import mcp  # noqa: E402
from test_map import agent, make_project  # noqa: E402

ADWIN = {"paper": {"title": "Learning from Time-Changing Data with Adaptive Windowing", "authors": "Bifet, Gavalda", "year": "2007", "venue": "SDM",
                   "url": "https://arxiv.org/abs/1234.56789v2"},
         "code": "https://github.com/example/adwin", "intuition": "Keeps a window of recent items and cuts it when two halves differ.",
         "published": [{"dataset": "Electricity", "metric": "fp", "value": "0.38", "where": "Table 2", "note": "prequential"},
                       {"dataset": "Airlines", "metric": "fp", "value": 12.5, "where": "Table 2"}]}


class BaselinesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        make_project(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        for f in ("map.json", "claims.json", "experiments.json", "stages.json", "baselines.json"):
            p = Path(self.tmp, ".lemmata", f)
            if p.exists():
                p.unlink()
        self.e = Engine(self.tmp)
        self.e.scan()
        self.e.propose_map(agent)
        self.e.confirm_map()

    def row(self, d, key):
        return next(r for r in d["rows"] if r["key"] == key)

    def test_rows_come_from_the_result_files(self):
        d = self.e.baselines()
        self.assertEqual((d["study"], d["ours"]), ("method", "MCD"))
        self.assertEqual([(r["key"], r["role"], r["in_results"]) for r in d["rows"]], [("adwin", "baseline", True), ("ddm", "baseline", True)])   # not ours, not the ablation variant
        r = self.row(d, "adwin")
        self.assertEqual(r["missing"], list(bl.PARTS))
        self.assertFalse(r["has_entry"])
        self.assertEqual([x["id"] for x in r["experiments"]], ["map:main", "map:cost"])
        el = next(m for m in r["mine"] if m["dataset"] == "Electricity" and m["metric"] == "fp")
        self.assertEqual((el["value"], el["ours"], el["ours_label"], el["lower"]), (41.0, 30.0, "MCD", True))
        self.assertEqual({k: d["counts"][k] for k in ("total", "in_results", "complete", "pdf", "numbers", "proposed")},
                         {"total": 2, "in_results": 2, "complete": 0, "pdf": 0, "numbers": 0, "proposed": 0})
        self.assertEqual(d["datasets"], ["Electricity", "Weather", "Covtype"])

    def test_your_own_edit_counts_at_once(self):
        d = self.e.save_baseline("adwin", ADWIN)                                   # any spelling of the name finds the row
        r = self.row(d, "adwin")
        p = r["entry"]["paper"]
        self.assertEqual((p["year"], p["pdf"], p["pdf_derived"]), (2007, "https://arxiv.org/pdf/1234.56789", True))   # an arXiv page has its PDF at a fixed address
        self.assertEqual((r["entry"]["by"], r["code_host"], r["missing"], r["has_entry"]), ("you", "github.com", [], True))
        el, air = r["compare"]
        # the paper prints 0.38 where the result file holds 41.0: compared on the file's scale, and said
        self.assertEqual((el["mine"], el["ours"], el["scaled"], el["published_scaled"], el["diff"], el["x"]), (41.0, 30.0, True, 38.0, 3.0, "map:main"))
        self.assertEqual((air["mine"], air["diff"], air["scaled"]), (None, None, False))                                 # a dataset the project did not run
        self.assertEqual((el["url"], el["where"]), ("https://arxiv.org/pdf/1234.56789", "Table 2"))                      # the number links to the paper's PDF
        self.assertEqual((d["counts"]["numbers"], d["counts"]["reproduced"], d["counts"]["complete"]), (2, 1, 1))
        # a field left out stays; an empty one is cleared; the list of numbers is replaced as a whole
        d = self.e.save_baseline("ADWIN", {"limit": "One-dimensional input only.", "code": "", "published": [ADWIN["published"][0]]})
        r = self.row(d, "adwin")
        self.assertEqual((r["entry"]["limit"], r["entry"]["code"], r["entry"]["intuition"][:5], len(r["compare"])), ("One-dimensional input only.", None, "Keeps", 1))
        self.assertIn("code", r["missing"])
        self.assertEqual(Engine(self.tmp).baselines()["rows"][0]["entry"]["limit"], "One-dimensional input only.")      # kept in the hub folder
        # a link that is not https, a number that is not one: refused, nothing saved
        for bad in ({"code": "http://github.com/x/y"}, {"paper": {"pdf": "javascript:alert(1)"}}, {"paper": {"url": "https://user:pw@site.org/p"}},
                    {"published": [{"dataset": "Weather", "metric": "fp", "value": "high"}]}, {"paper": {"year": "20007"}}):
            with self.assertRaises(BadRequest):
                self.e.save_baseline("ADWIN", bad)
        self.assertEqual(self.row(self.e.baselines(), "adwin")["entry"]["code"], None)

    def test_track_a_baseline_before_it_is_run(self):
        d = self.e.save_baseline("KSWIN", {})
        r = self.row(d, "kswin")
        self.assertEqual((r["in_results"], r["role"], r["mine"], r["has_entry"]), (False, None, [], True))
        self.assertEqual([x["key"] for x in d["rows"]], ["adwin", "ddm", "kswin"])                                       # after the ones with results
        d = self.e.decide_baselines("remove", "KSWIN")
        self.assertEqual(len(d["rows"]), 2)
        with self.assertRaises(NotFound):
            self.e.decide_baselines("remove", "KSWIN")
        with self.assertRaises(NotFound):
            self.e.decide_baselines("remove", "DDM")                                                                     # in the result files, but it has no card to empty

    def test_an_agent_proposes_and_you_confirm(self):
        self.e.save_baseline("ADWIN", {"intuition": "Mine."})
        doc = {"baselines": [
            {"name": "DDM", "paper": {"title": "Learning with Drift Detection", "url": "http://not-https.org/ddm", "pdf": "https://site.org/view/17"},
             "code": "https://example.org/ddm", "intuition": "Watches the error rate of the model.",
             "published": [{"dataset": "Weather", "metric": "fp", "value": 35}, {"dataset": "Weather", "metric": "fp", "value": 35.0, "where": "Table 3"}]},
            {"name": "ADWIN", "intuition": "The agent's wording.", "limit": "One dimension."},
            {"name": "Page-Hinkley", "intuition": "A cumulative sum test."},
            {"name": "DDM", "intuition": "again"}, {"name": "Nothing"}, "not an object"]}
        d = self.e.propose_baselines(doc, "agent")
        why = {r["where"]: (r["level"], r["why"]) for r in d["report"]}
        self.assertEqual(why["baselines[0].paper.url"][0], "dropped")                    # not https
        self.assertEqual(why["baselines[0].published[0]"][0], "dropped")                 # an agent must say which table
        self.assertEqual(why["baselines[0].paper.pdf"][0], "note")                       # does not look like a PDF
        self.assertEqual(why["baselines[0].code"][0], "note")                            # not a known code host
        self.assertEqual(why["baselines[2]"][0], "note")                                 # not in the result files: a baseline to consider
        self.assertEqual((why["baselines[3]"][0], why["baselines[4]"][0], why["baselines[5]"][0]), ("dropped",) * 3)
        self.assertEqual(d["counts"]["proposed"], 3)
        # nothing counts yet
        self.assertEqual(self.row(d, "adwin")["entry"]["intuition"], "Mine.")
        self.assertEqual(self.row(d, "ddm")["has_entry"], False)
        self.assertEqual([c["field"] for c in self.row(d, "ddm")["changes"]], ["paper.title", "paper.pdf", "code", "intuition", "published"])
        ch = {c["field"]: c for c in self.row(d, "adwin")["changes"]}
        self.assertEqual((ch["intuition"]["before"], ch["intuition"]["after"], ch["limit"]["before"]), ("Mine.", "The agent's wording.", None))
        self.assertEqual(self.row(d, "pagehinkley")["in_results"], False)
        # confirm one, discard the rest
        d = self.e.decide_baselines("confirm", "DDM")
        r = self.row(d, "ddm")
        self.assertEqual((r["entry"]["by"], r["proposal"], r["compare"][0]["mine"], r["compare"][0]["diff"], d["counts"]["proposed"]), ("agent", None, 35.0, 0.0, 2))
        d = self.e.decide_baselines("discard")
        self.assertEqual((d["counts"]["proposed"], d["report"], self.row(d, "adwin")["entry"]["intuition"], len(d["rows"])), (0, [], "Mine.", 2))
        with self.assertRaises(NotFound):
            self.e.decide_baselines("confirm")
        with self.assertRaises(BadRequest):
            self.e.propose_baselines({"baselines": "x"})
        with self.assertRaises(BadRequest):
            self.e.decide_baselines("explode")

    def test_link_rules(self):
        self.assertEqual(bl.link(" https://openreview.net/pdf?id=abc "), "https://openreview.net/pdf?id=abc")
        self.assertIsNone(bl.link(""))
        for bad in ("ftp://x.org/a", "https://localhost/a", "https://x.org/a b", "https://x.org/<script>", "//x.org/a", "https://" + "a" * 500 + ".org"):
            with self.assertRaises(BadRequest):
                bl.link(bad)
        self.assertTrue(bl.PDF_RE.search("https://aclanthology.org/2020.acl-main.1.pdf"))
        self.assertTrue(bl.PDF_RE.search("https://arxiv.org/pdf/2101.00001"))
        self.assertFalse(bl.PDF_RE.search("https://arxiv.org/abs/2101.00001"))

    def test_mcp_tools(self):
        self.e.save_baseline("ADWIN", ADWIN)

        ctx = mcp.LocalCtx(self.tmp)
        tools = {t["name"]: t for t in mcp.TOOLS}
        self.assertTrue(tools["baselines"]["annotations"]["readOnlyHint"])
        self.assertFalse(tools["propose_baselines"]["annotations"]["readOnlyHint"])
        pid = ctx.list_projects()[0]["id"]
        text, data, hint = tools["baselines"]["fn"](ctx, {"project": pid})
        self.assertIn("ADWIN (baseline): complete", text)
        self.assertIn("published fp on Electricity: 0.38 (Table 2); measured here 41.0 (difference +3, published read on the file's scale); ours 30.0", text)
        self.assertIn("DDM (baseline): missing paper, pdf, code, intuition, published", text)
        text, data, hint = tools["baselines"]["fn"](ctx, {"project": pid, "brief": True})
        self.assertIn("propose_baselines", text)
        self.assertEqual([b["name"] for b in data["baselines"] if b["missing"]], ["DDM"])
        text, data, hint = tools["propose_baselines"]["fn"](ctx, {"project": pid, "baselines": [{"name": "DDM", "intuition": "Watches the error rate."}]})
        self.assertIn("1 proposed card(s) wait for the researcher", text)
        self.assertIn("Only the researcher can confirm", text)
        with self.assertRaises(mcp._Fail):
            tools["propose_baselines"]["fn"](ctx, {"project": pid, "baselines": "x"})

    def test_snapshot_and_brief(self):
        self.e.save_baseline("ADWIN", ADWIN)
        b = self.e.baselines_brief()
        self.assertIn("propose_baselines", b["guide"])
        ad = next(x for x in b["baselines"] if x["name"] == "ADWIN")
        self.assertEqual((ad["missing"], ad["measured_on"], ad["measures"]), ([], ["Covtype", "Electricity", "Weather"], ["CPU_Time", "fp"]))
        json.dumps(self.e.baselines())                                                    # the page is plain JSON (it goes into exported snapshots)


if __name__ == "__main__":
    unittest.main()
