"""S31 tests: LaTeX to paste (tables by rule, requests for the researcher's agent, snippets checked against the files).
Run: PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_texout*.py'"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))
sys.path.insert(0, str(APP / "tests"))

from lemmata.engine import texout as tx  # noqa: E402
from lemmata.engine.api import Engine  # noqa: E402
from lemmata.engine.errors import BadRequest, NotFound  # noqa: E402
from lemmata import mcp  # noqa: E402
from test_map import agent, make_project  # noqa: E402

GOOD = r"""\begin{table}[t]
\centering
\caption{False positives (lower is better). Best in bold.} % 99.9 in a comment is not a result
\label{tab:main}
\begin{tabular}{p{0.3\linewidth}ccc}
\toprule
Method & Covtype & Electricity & Weather \\[2.5pt]
\midrule
ADWIN~\cite{bifet2007} & 52.0 & 41.0 & 37.5 \\
MCD (ours) & \textbf{46.0} & \textbf{30.0} & \textbf{29.5} \\
\bottomrule
\end{tabular}
\end{table}"""


class TexOutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        make_project(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        for f in ("map.json", "claims.json", "experiments.json", "stages.json", "baselines.json", "latex.json"):
            p = Path(self.tmp, ".lemmata", f)
            if p.exists():
                p.unlink()
        self.e = Engine(self.tmp)
        self.e.scan()
        self.e.propose_map(agent)
        self.e.confirm_map()

    def test_table_by_rule(self):
        d = self.e.latex()
        t = next(x for x in d["tables"] if x["x"] == "map:main")
        tex = t["latex"]
        self.assertEqual((t["metric"], t["lower"], t["rows"], t["cols"]), ("fp", True, 3, 3))
        self.assertIn(r"\caption{Main comparison: fp (lower is better) on 3 datasets. Best in bold.}", tex)
        self.assertIn(r"ADWIN & 52.0 & 41.0 & 37.5 \\", tex)                       # the numbers of the result files, as they are
        self.assertIn(r"MCD (ours) & \textbf{46.0} & \textbf{30.0} & \textbf{29.5} \\", tex)   # lower is better: the lowest is bold; ours last
        self.assertLess(tex.index("DDM &"), tex.index(r"MCD (ours)"))
        self.assertEqual(tx.structure(tex), [])
        self.assertEqual(tx.check({"latex": tex}, tx.pool([x.get("grid") for x in self.e._baselines_setup()["experiments"]]), None)["status"], "ok")
        # higher is better, a missing cell, a name that needs escaping, no method of its own
        exp = {"id": "x", "name": "A_B 50%", "protocol": {"metric": "F1", "lower": False}, "grid": {"cols": ["d_1", "d2"], "datasets": ["d_1", "d2"], "rows": [
            {"label": "m&m", "role": "compared", "values": {"d_1": 0.8, "d2": None}}, {"label": "k", "role": "compared", "values": {"d_1": 0.815, "d2": 0.5}}]}}
        tex = tx.table(exp)["latex"]
        self.assertIn(r"\caption{A\_B 50\%: F1 (higher is better) on 2 datasets. Best in bold.}", tex)
        self.assertIn(r"m\&m & 0.800 & -- \\", tex)
        self.assertIn(r"k & \textbf{0.815} & 0.500 \\", tex)                       # one value in a column: nothing to call best
        self.assertNotIn("(ours)", tex)
        # many datasets: turned, one per line
        cols = ["s%02d" % i for i in range(20)]
        wide = {"id": "w", "name": "Wide", "protocol": {"metric": "auc", "lower": False}, "grid": {"cols": cols, "datasets": cols, "rows": [
            {"label": "a", "role": "baseline", "values": {c: 1.0 for c in cols}}, {"label": "b", "role": "ours", "values": {c: 2.0 for c in cols}}]}}
        t = tx.table(wide)
        self.assertIn("Turned", t["note"])
        self.assertIn(r"Dataset & a & b (ours) \\", t["latex"])
        self.assertIsNone(tx.table({"id": "n", "grid": {"rows": [], "cols": []}}))

    def test_numbers_read_from_latex(self):
        lits = tx.literals(GOOD)
        self.assertEqual(lits, ["52.0", "41.0", "37.5", "46.0", "30.0", "29.5"])   # not the comment, the column width, the row spacing or the key
        self.assertEqual(tx.literals(r"up by 12\% and 3.5 points; see \ref{tab:2.1}, width=0.8\linewidth, 5 seeds"), ["12", "3.5"])
        nums = {41.0, 0.385, -2.25}
        self.assertTrue(tx.held("41.0", nums))
        self.assertTrue(tx.held("0.39", nums))                                    # at the printed precision
        self.assertTrue(tx.held("38.5", nums))                                    # a share printed as a percentage
        self.assertTrue(tx.held("-2.3", nums))
        self.assertFalse(tx.held("41.6", nums))
        self.assertEqual(tx.structure(r"\begin{table}\begin{tabular}{l} a \end{tabular}"), [r"\begin{table} is never closed"])
        self.assertEqual(tx.structure(r"\textbf{a"), ["a brace is left open"])
        self.assertEqual(tx.structure(r"a \} b \{ c"), [])                         # escaped braces are text
        self.assertTrue(tx.structure(r"\input{other}"))
        self.assertEqual(tx.cite_keys(r"\citep[see][]{a2020, b21} and \cite{TODO-ddm}"), ["a2020", "b21", "TODO-ddm"])

    def test_ask_write_check_and_go_stale(self):
        d = self.e.latex_request("table", "Main comparison", "Main results, ours last, with a caption")
        r = d["requests"][0]
        self.assertEqual((r["id"], r["status"], r["target"]["id"], d["counts"]["open"]), ("r1", "open", "map:main", 1))
        self.assertEqual(self.e.latex_request("paragraph", {"type": "claim", "id": "mine:1"}, None)["requests"][0]["target"]["type"], "claim")
        self.assertEqual(self.e.latex_request("caption", None, "x")["requests"][0]["target"]["type"], "project")
        for bad in (("poem", None), ("table", "No such experiment")):
            with self.assertRaises((BadRequest, NotFound)):
                self.e.latex_request(*bad, None)
        # the brief holds the whole state of the project, the asked-about experiment first, with its table by rule
        b = self.e.latex_brief("r1")
        self.assertIn("submit_latex", b["guide"])
        self.assertEqual((b["request"]["ask"], b["ours"], b["study"]), ("Main results, ours last, with a caption", "MCD", "method"))
        self.assertEqual([(x["id"], x["asked_about"]) for x in b["experiments"]][0], ("map:main", True))
        self.assertEqual(len(b["experiments"]), 4)
        self.assertIn(r"\toprule", b["experiments"][0]["table_by_rule"])
        self.assertTrue(any(c["id"] == "mine:1" and c["stage"] for c in b["claims"]))
        self.assertTrue({"metric", "dataset", "method"} <= {i["kind"] for i in b["setup"]})
        for k in ("key_numbers", "baselines", "notation", "citation_keys", "already_written"):
            self.assertIn(k, b)
        json.dumps(b)
        self.assertEqual(self.e.latex_brief(kind="table", target="Compute cost", ask="cost")["request"]["status"], "ad hoc")
        # the agent hands it in: kept, the request is done, the numbers are in the files
        d = self.e.submit_latex({"request": "r1", "kind": "table", "title": "Main results", "latex": GOOD, "sources": ["map:main"], "notes": "booktabs"}, "agent")
        s = d["snippets"][0]
        self.assertEqual((s["id"], s["by"], s["check"]["status"], s["check"]["numbers"], s["check"]["unknown"], s["check"]["cites_unknown"]), (d["submitted"], "agent", "ok", 6, [], None))
        self.assertEqual(next(r for r in d["requests"] if r["id"] == "r1")["status"], "done")
        # a number that is in no file, an open environment, a citation still to fill in
        bad = GOOD.replace("52.0", "51.3").replace(r"\end{table}", "").replace("bifet2007", "TODO-adwin")
        d = self.e.submit_latex({"kind": "table", "latex": bad}, "agent")
        k = d["snippets"][0]["check"]
        self.assertEqual((k["status"], k["unknown"], k["form"], k["cites_todo"]), ("check", ["51.3"], [r"\begin{table} is never closed"], ["TODO-adwin"]))
        self.assertEqual((d["counts"]["ok"], d["counts"]["check"], d["counts"]["stale"]), (1, 1, 0))
        # the results change after the snippet was written: it is stale, and says which number
        st = tx.load(self.e.hub)
        first = next(s for s in st["snippets"] if s["title"] == "Main results")
        k = tx.check(first, tx.pool([52.0, 41.0, 37.5, 46.0, 30.0]), None)          # 29.5 is gone from the files
        self.assertEqual((k["status"], k["stale"]), ("stale", ["29.5"]))
        for doc in ({}, {"latex": ""}, {"latex": "x", "kind": "poem"}, {"latex": "x", "request": "r99"}, {"latex": "x" * 20001}, {"latex": "x", "sources": "y"}):
            with self.assertRaises((BadRequest, NotFound)):
                self.e.submit_latex(doc, "agent")
        d = self.e.decide_latex("remove_snippet", d["snippets"][0]["id"])
        self.assertEqual(d["counts"]["snippets"], 1)
        d = self.e.decide_latex("reopen", "r1")
        self.assertEqual(next(r for r in d["requests"] if r["id"] == "r1")["status"], "open")
        d = self.e.decide_latex("remove_request", "r1")
        self.assertNotIn("r1", [r["id"] for r in d["requests"]])
        with self.assertRaises(NotFound):
            self.e.decide_latex("remove_snippet", "s99")
        with self.assertRaises(BadRequest):
            self.e.decide_latex("explode", "s1")
        self.assertEqual(Engine(self.tmp).latex()["counts"]["snippets"], 1)        # kept in the hub folder

    def test_published_numbers_of_a_baseline_count_as_held(self):
        self.e.save_baseline("ADWIN", {"published": [{"dataset": "Airlines", "metric": "fp", "value": 12.75, "where": "Table 2"}]})
        d = self.e.submit_latex({"kind": "paragraph", "latex": r"ADWIN reports 12.75 on Airlines; we measure 41.0 on Electricity and 77.7 nowhere."}, "agent")
        self.assertEqual(d["snippets"][0]["check"]["unknown"], ["77.7"])

    def test_mcp_tools(self):
        ctx = mcp.LocalCtx(self.tmp)
        tools = {t["name"]: t for t in mcp.TOOLS}
        pid = ctx.list_projects()[0]["id"]
        self.assertTrue(tools["latex"]["annotations"]["readOnlyHint"])
        self.assertFalse(tools["submit_latex"]["annotations"]["readOnlyHint"])
        self.e.latex_request("table", "Main comparison", "ours last")
        text, data, hint = tools["latex"]["fn"](ctx, {"project": pid})
        self.assertIn("request r1: a table about Main comparison: ours last", text)
        text, data, hint = tools["latex"]["fn"](ctx, {"project": pid, "request": "r1"})
        self.assertIn("How to write LaTeX for a Lemmata project", text)
        self.assertIn("table_by_rule", text)
        self.assertEqual(data["request"]["id"], "r1")
        text, data, hint = tools["latex"]["fn"](ctx, {"project": pid, "kind": "caption", "ask": "one caption"})   # asked directly, about the whole project
        self.assertEqual(data["request"]["target"]["type"], "project")
        text, data, hint = tools["submit_latex"]["fn"](ctx, {"project": pid, "request": "r1", "kind": "table", "latex": GOOD.replace("41.0", "40.1"), "title": "Main"})
        self.assertIn("Lemmata's check: check (6 decimal number(s) read, 5 found", text)
        self.assertIn("Not found in the files: 40.1", text)
        with self.assertRaises(mcp._Fail):
            tools["submit_latex"]["fn"](ctx, {"project": pid})


if __name__ == "__main__":
    unittest.main()
