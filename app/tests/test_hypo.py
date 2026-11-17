"""S27 hypothesis-first tests. Run: PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p 'test_hypo*.py'

A small research repo with a frozen protocol, a findings report, a deviation log and a test table. The jobs are answered
the way the researcher's own LLM would answer them; nothing here calls a model."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))

from lemmata.engine.api import Engine  # noqa: E402
from lemmata.engine.errors import BadRequest  # noqa: E402

PROTOCOL = """# Short experiment: pre-registered design

- **Frozen before any model is run.** Changes go in notes/ as deviations.

## Hypotheses (primary)

| | Hypothesis |
|---|---|
| H1 | Time-series benchmarks carry more temporal dependence than streaming benchmarks. |
| H2 | The detector gap grows with temporal dependence. |

Secondary: H2b, the streaming advantage grows with drift.
"""
FINDINGS = """# Is there temporal dependence in anomaly-detection benchmarks?

## Question

Parrino et al. attribute the gap between time-series and streaming detectors to temporal characteristics,
without defining or measuring them. The question is whether temporal dependence exists in the benchmark datasets.
"""
DEVIATIONS = """# Deviations

## D1. Slicing of long streams (2026-11-10)
Before any result. Affects H1.

## D2. Exploratory checks (2026-11-20)
After the results; touches H1 and H2.
"""
TESTS = "test,estimate,p_holm\nH1 (D1),0.58,0.0002\nH2 (D1 vs Delta),0.19,0.24\nH2b,−0.05,0.62\n"


def git(cwd, *args, date=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    subprocess.run(["git", "-c", "commit.gpgsign=false"] + list(args), cwd=cwd, env=env, check=True, capture_output=True)


def problem():
    return {"gap": {"text": "The gap is attributed to temporal characteristics nobody measured.",
                    "evidence": [{"path": "FINDINGS.md", "line": 5, "quote": "without defining or measuring them"}]},
            "why_it_matters": {"text": "", "note": "not stated"},
            "approach": {"text": "Measure whether temporal dependence exists in the benchmarks.",
                         "evidence": [{"path": "FINDINGS.md", "line": 6, "quote": "whether temporal dependence exists"}]},
            "if_solved": "A measured property instead of a label."}


def rule(sel):
    return {"file": "results/tests.csv", "select": {"test": sel}, "conditions": [{"column": "p_holm", "op": "<", "value": 0.05}, {"column": "estimate", "op": ">", "value": 0}],
            "report": ["estimate", "p_holm"]}


def draft():
    fz = {"file": "protocol/short.md"}
    return {"hypotheses": [
        {"id": "H1", "statement": "Time-series benchmarks carry more temporal dependence than streaming benchmarks.", "tier": "confirmatory",
         "criterion": {"text": "one-sided test, Holm", "frozen": fz, "rule": rule("H1 (D1)")}, "tested_by": ["stepA"],
         "evidence": [{"path": "protocol/short.md", "line": 9, "quote": "carry more temporal dependence"}]},
        {"id": "H2", "statement": "The detector gap grows with temporal dependence.", "tier": "confirmatory",
         "criterion": {"text": "Spearman, Holm", "frozen": fz, "rule": rule("H2 (D1 vs Delta)")}, "tested_by": ["stepC"],
         "evidence": [{"path": "protocol/short.md", "line": 10, "quote": "The detector gap grows"}]},
        {"id": "H2b", "statement": "The streaming advantage grows with drift.", "tier": "secondary",
         "criterion": {"text": "Spearman", "frozen": fz, "rule": rule("H2b")}, "evidence": [{"path": "protocol/short.md", "quote": "grows with drift"}]},
        {"id": "H9", "statement": "Invented.", "evidence": [{"path": "protocol/short.md", "quote": "this sentence is not there"}]},
        {"id": "H8", "statement": "Bad rule.", "criterion": {"rule": dict(rule("H1 (D1)"), select={"test": "nope"})},
         "evidence": [{"path": "protocol/short.md", "quote": "Frozen before any model is run"}]}],
        "experiments": [{"id": "stepA", "title": "Dependence", "deliverables": ["results/A.csv"], "tests_claims": ["H1"]},
                        {"id": "stepC", "title": "Detectors", "deliverables": ["results/C"], "tests_claims": ["H2"]}]}


class HypoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lemmata-hypo-")
        root = Path(self.tmp)
        code = root / "code"
        (code / "protocol").mkdir(parents=True)
        (code / "notes").mkdir()
        (code / "results" / "C").mkdir(parents=True)
        git(code, "init", "-q", "-b", "main")
        (code / "protocol" / "short.md").write_text(PROTOCOL)
        (code / "FINDINGS.md").write_text(FINDINGS)
        git(code, "add", "-A")
        git(code, "commit", "-q", "-m", "protocol", date="2026-11-12T10:00:00+0900")
        (code / "notes" / "2026-11-12-deviations.md").write_text(DEVIATIONS)
        (code / "results" / "A.csv").write_text("x\n1\n")
        (code / "results" / "C" / "p.csv").write_text("x\n1\n")
        (code / "results" / "tests.csv").write_text(TESTS)
        git(code, "add", "-A")
        git(code, "commit", "-q", "-m", "results", date="2026-11-16T10:00:00+0900")
        (root / "paper").mkdir()
        (root / ".lemmata").mkdir()
        (root / ".lemmata" / "project.json").write_text(json.dumps({"schema": "lemmata.project/1", "name": "t", "repos": [
            {"id": "paper", "role": "paper", "path": "paper"}, {"id": "code", "role": "code", "path": "code"}]}))
        self.root, self.code = root, code
        self.e = Engine(root)
        self.e.scan()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ready(self):
        e = self.e
        j = e.hypothesis()["jobs"][0]
        e.submit_hypothesis_job(j["id"], {"problem": problem()})
        d = e.hypothesis_act("confirm", "problem")
        j = next(j for j in d["jobs"] if j["type"] == "draft_hypotheses")
        return e.submit_hypothesis_job(j["id"], draft())

    def test_detect_and_first_job(self):
        d = self.e.hypothesis()
        self.assertEqual(d["mode"], "hypothesis_first")
        self.assertEqual(d["sources"]["hypothesis_source"], ["protocol/short.md"])
        self.assertEqual(d["sources"]["deviations"], ["notes/2026-11-12-deviations.md"])
        self.assertEqual(d["sources"]["test_tables"], ["results/tests.csv"])
        self.assertEqual([j["type"] for j in d["jobs"]], ["understand_problem"])
        self.assertIn("## What to do", self.e.hypothesis_job(d["jobs"][0]["id"])["markdown"])

    def test_problem_needs_real_quotes(self):
        j = self.e.hypothesis()["jobs"][0]
        bad = {"gap": {"text": "x", "evidence": [{"path": "FINDINGS.md", "quote": "words that are not there"}]}}
        with self.assertRaises(BadRequest):
            self.e.submit_hypothesis_job(j["id"], {"problem": bad})
        d = self.e.submit_hypothesis_job(j["id"], {"problem": problem()})
        p = d["problem"]["proposed"]
        self.assertEqual(p["gap"]["evidence"][0]["line"], 6, "the line is corrected to where the quote really is")
        self.assertIsNone(p["why_it_matters"]["text"])
        self.assertEqual(d["problem"]["validity"], "unreviewed")
        self.assertFalse([j for j in d["jobs"] if j["type"] == "draft_hypotheses"], "hypotheses wait for the problem")

    def test_stages_from_the_test_table(self):
        d = self.ready()
        drop = {r["where"] for r in d["submit_report"] if r["level"] == "dropped"}
        self.assertIn("hypothesis H9", drop)
        H = {h["id"]: h for h in d["hypotheses"]}
        self.assertNotIn("H9", H)
        self.assertIsNone(H["H8"]["criterion"]["rule"])
        self.assertEqual((H["H1"]["stage"], H["H1"]["stage_rule"]), ("finding", "R1"))
        self.assertEqual((H["H2"]["stage"], H["H2"]["stage_rule"]), ("refuted", "R2"))
        self.assertEqual((H["H2b"]["stage"], H["H2b"]["stage_rule"]), ("testing", "R3"))
        self.assertAlmostEqual(H["H1"]["result"]["values"]["estimate"], 0.58)
        self.assertEqual(H["H1"]["frozen_at"]["day"], "2026-11-12")
        # flipping one number flips the stage, with no model
        (self.code / "results" / "tests.csv").write_text(TESTS.replace("0.19,0.24", "0.19,0.01"))
        H = {h["id"]: h for h in self.e.hypothesis()["hypotheses"]}
        self.assertEqual(H["H2"]["stage"], "finding")

    def test_claims_take_the_rule_stage(self):
        self.ready()
        for hid in ("H1", "H2"):
            self.e.hypothesis_act("confirm", hid)
        cl = {c.get("hypothesis"): c for c in self.e.claims()["claims"] if c.get("hypothesis")}
        self.assertEqual((cl["H1"]["stage"], cl["H1"]["stage_rule"]), ("finding", "R1"))
        self.assertEqual(cl["H2"]["stage"], "refuted")
        self.e.hypothesis_act("delete", "H2", note="x")
        states = {c["label"]: c["state"] for c in self.e.claims()["claims"] if c.get("label") in ("H1", "H2")}
        self.assertEqual(states["H2"], "rejected")
        self.e.hypothesis_act("restore", "H2")
        self.assertEqual({c["label"]: c["state"] for c in self.e.claims()["claims"] if c.get("label") == "H2"}["H2"], "confirmed")

    def test_deviations_and_timing(self):
        d = self.ready()
        dv = {x["id"]: x for x in d["deviations"]}
        self.assertEqual(dv["D1"]["timing"]["H1"], "before_data")
        self.assertEqual(dv["D2"]["timing"]["H1"], "after_data")
        self.assertEqual(sorted(dv["D2"]["affects"]), ["H1", "H2"])
        h1 = next(h for h in d["hypotheses"] if h["id"] == "H1")
        self.assertEqual((h1["deviations"]["before"], h1["deviations"]["after"]), (1, 1))

    def test_fix_records_a_deviation_and_asks_the_llm(self):
        self.ready()
        d = self.e.hypothesis_act("fix", "H1", text="Time-series benchmarks carry more lag-1 dependence than streaming ones.")
        h1 = next(h for h in d["hypotheses"] if h["id"] == "H1")
        self.assertEqual(h1["tier"], "confirmatory", "a reworded statement with the same test stays confirmatory")
        self.assertIn("L1", h1["deviations"]["ids"])
        j = next(j for j in d["jobs"] if j["type"] == "revise")
        d = self.e.submit_hypothesis_job(j["id"], {"understood": "u", "operations": [{"op": "revise", "target": "H1", "field": "answers", "after": "a", "reason": "r"}]})
        cs = d["change_sets"][0]
        self.assertEqual(cs["operations"][0]["before"], None)
        d = self.e.hypothesis_change(cs["id"], "accept")
        self.assertEqual(next(h for h in d["hypotheses"] if h["id"] == "H1")["answers"], "a")
        d = self.e.hypothesis_act("fix", "H2", fields={"criterion_text": "a different test"})
        self.assertEqual(next(h for h in d["hypotheses"] if h["id"] == "H2")["tier"], "exploratory", "changing a frozen test makes it exploratory")

    def test_combine_keeps_both_tests(self):
        self.ready()
        d = self.e.hypothesis_act("combine", targets=["H1", "H2"], note="both")
        j = next(j for j in d["jobs"] if j["type"] == "combine")
        d = self.e.submit_hypothesis_job(j["id"], {"understood": "u", "operations": [{"op": "merge", "targets": ["H1", "H2"], "reason": "r",
                                                   "after": {"id": "H12", "statement": "Dependence exists and matters.", "tier": "confirmatory",
                                                             "criterion": {"frozen": {"file": "protocol/short.md"}}}}]})
        d = self.e.hypothesis_change(d["change_sets"][0]["id"], "accept")
        H = {h["id"]: h for h in d["hypotheses"]}
        self.assertEqual(H["H1"]["archived"]["merged_into"], "H12")
        self.assertEqual(H["H12"]["aliases"], ["H1", "H2"])
        self.assertEqual(H["H12"]["stage"], "refuted", "a combined claim needs every sub-condition")
        self.assertEqual(sorted(H["H12"]["tested_by"]), ["stepA", "stepC"])
        with self.assertRaises(BadRequest):
            self.e.hypothesis_act("restore", "H1")

    def test_tell_quotes_the_input_and_reject_changes_nothing(self):
        self.ready()
        d = self.e.hypothesis_act("tell", text="I now think the anomalies decide whether order matters.")
        j = next(j for j in d["jobs"] if j["type"] == "comprehend_input")
        cs = {"understood": "anomalies decide", "not_in_protocol": [0], "operations": [{"op": "add", "reason": "new", "from": {"path": j["ref"], "quote": "the anomalies decide"},
              "after": {"id": "H4", "statement": "Anomalies decide whether order matters.", "tier": "exploratory"}}]}
        d = self.e.submit_hypothesis_job(j["id"], cs)
        c = d["change_sets"][0]
        self.assertEqual(c["operations"][0]["from"]["quote"], "the anomalies decide")
        before = json.dumps(d["hypotheses"], sort_keys=True)
        d = self.e.hypothesis_change(c["id"], "reject")
        self.assertEqual(json.dumps(d["hypotheses"], sort_keys=True), before)
        d = self.e.hypothesis_act("tell", text="again: the anomalies decide.")
        j = next(j for j in d["jobs"] if j["type"] == "comprehend_input")
        d = self.e.submit_hypothesis_job(j["id"], dict(cs, operations=[dict(cs["operations"][0], **{"from": {"path": j["ref"], "quote": "the anomalies decide"}})]))
        d = self.e.hypothesis_change(d["change_sets"][-1]["id"], "accept")
        self.assertIn("H4", {h["id"] for h in d["hypotheses"]})
        self.assertIn("Proposed protocol change", self.e.hypothesis_proposal(d["change_sets"] and d["change_sets"][-1]["id"] or "cs-2"))

    def test_problem_delete_needs_a_new_input(self):
        self.ready()
        with self.assertRaises(BadRequest):
            self.e.hypothesis_act("delete", "problem")
        d = self.e.hypothesis_act("delete", "problem", text="The problem is benchmark labels, not detectors.")
        self.assertIsNone(d["problem"]["confirmed"])
        self.assertTrue(any(j["type"] == "understand_problem" for j in d["jobs"]))

    def test_paper_projects_stay_in_paper_mode(self):
        (self.root / "paper" / "main.tex").write_text("\\documentclass{article}\\begin{document}\\title{T}\\begin{abstract}We show X.\\end{abstract}\\end{document}\n")
        git(self.root / "paper", "init", "-q")
        self.e.scan()
        self.assertEqual(self.e.hypothesis()["mode"], "paper")
        d = self.e.hypothesis_act("enable", "on")
        self.assertEqual(d["mode"], "hypothesis_first")


if __name__ == "__main__":
    unittest.main()
